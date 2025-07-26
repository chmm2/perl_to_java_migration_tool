import os
import sys
import subprocess
import json
import argparse
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

def convert_sets_to_lists(obj):
    if isinstance(obj, dict):
        return {k: convert_sets_to_lists(v) for k, v in obj.items()}
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, list):
        return [convert_sets_to_lists(i) for i in obj]
    else:
        return obj

def ensure_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

def find_perl_files(path, recursive=True):
    perl_files = []
    if os.path.isfile(path):
        if path.endswith(('.pl', '.pm', '.perl')):
            perl_files.append(path)
    elif os.path.isdir(path):
        if recursive:
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.endswith(('.pl', '.pm', '.perl')):
                        perl_files.append(os.path.join(root, file))
        else:
            for file in os.listdir(path):
                if file.endswith(('.pl', '.pm', '.perl')):
                    file_path = os.path.join(path, file)
                    if os.path.isfile(file_path):
                        perl_files.append(file_path)
    return perl_files

def parse_perl_file_to_blocks(file_path):
    """
    Splits a file into a sequence of 'global_scope' and 'package' blocks.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []

    blocks = []
    current_block = {'type': 'global_scope', 'lines': []}
    inside_package = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#!'):
            continue

        pkg_match = re.match(r'^\s*package\s+([^;]+);?', stripped)
        if pkg_match:
            # Finalize the previous block if it has any content.
            if any(l.strip() for l in current_block['lines']):
                blocks.append(current_block)

            pkg_name = pkg_match.group(1).strip()
            current_block = {'type': 'package', 'name': pkg_name, 'lines': []}
            inside_package = True
            continue

        current_block['lines'].append(line)

    # Append the final block if it has content.
    if any(l.strip() for l in current_block['lines']):
        blocks.append(current_block)

    return blocks

def parse_block_content(lines, package_name=None):
    """
    Separates a block's lines into definitions (methods), use statements, and executable code.
    """
    use_statements = []
    methods = []
    execution_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        use_match = re.match(r'^\s*(use|no)\s+([^;]+);?', stripped)
        if use_match:
            use_statements.append({
                "type": "UseStatement",
                "module": use_match.group(2).strip(),
            })
            i += 1
            continue

        if stripped.startswith('sub '):
            sub_match = re.match(r'sub\s+([^\s{]+)', stripped)
            if sub_match and '{' in line:
                sub_name = sub_match.group(1)
                start_line_index = i
                brace_count = line.count('{') - line.count('}')

                while brace_count > 0 and i + 1 < len(lines):
                    i += 1
                    line = lines[i]
                    brace_count += line.count('{') - line.count('}')

                sub_lines = lines[start_line_index : i + 1]
                full_sub = "".join(sub_lines)
                first_brace = full_sub.find('{')
                last_brace = full_sub.rfind('}')
                body = full_sub[first_brace + 1:last_brace].strip() if first_brace != -1 else ''

                param_match = re.search(r'my\s*\(([^)]+)\)\s*=\s*@_', body)
                parameters = [p.strip() for p in param_match.group(1).split(',')] if param_match else []

                methods.append({
                    "type": "SubDefinition",
                    "name": sub_name,
                    "parameters": parameters,
                    "body": body,
                    "package": package_name,
                    "full_name": f"{package_name}::{sub_name}" if package_name else sub_name
                })

                i += 1
                continue

        execution_lines.append(line)
        i += 1

    return use_statements, methods, execution_lines

def create_ast_from_file(perl_file):
    """
    Builds the final, detailed AST by processing the blocks from a file.
    """
    raw_blocks = parse_perl_file_to_blocks(perl_file)
    if not raw_blocks:
        return None

    packages = []
    global_scope_block = None
    top_level_use = []

    def has_code(lines):
        return any(l.strip() and not l.strip().startswith('#') for l in lines)

    for block in raw_blocks:
        use_statements, methods, execution_lines = parse_block_content(block['lines'], block.get('name'))

        for stmt in use_statements:
            stmt['source_file'] = perl_file

        if block['type'] == 'package':
            package_script_block = None
            if has_code(execution_lines):
                package_script_block = {
                    "type": "ScriptExecution",
                    "body": "".join(execution_lines).strip(),
                    "source_file": perl_file
                }

            packages.append({
                "type": "PackageDeclaration",
                "name": block['name'],
                "use_statements": use_statements,
                "methods": methods,
                "script_execution": package_script_block,
                "source_file": perl_file
            })

        elif block['type'] == 'global_scope':
            top_level_use.extend(use_statements)
            global_scope_block = {
                "type": "GlobalScope",
                "body": "".join(execution_lines).strip(),
                "source_file": perl_file
            }
            if methods:
                global_scope_block["functions"] = methods

    return {
        "type": "PerlFile",
        "source_file": perl_file,
        "use_statements": top_level_use,
        "packages": packages,
        "global_scope": global_scope_block
    }

def analyze_cross_file_calls(combined_ast):
    """
    Analyze function calls across files and create cross-file relationships.
    """
    # Build global function registry
    global_functions = {}
    package_to_file = {}
    
    # First pass: collect all functions and their locations
    for file_ast in combined_ast["files"]:
        file_path = file_ast["source_file"]
        
        for package in file_ast.get("packages", []):
            package_name = package["name"]
            package_to_file[package_name] = file_path
            
            for method in package.get("methods", []):
                full_name = method["full_name"]
                global_functions[full_name] = {
                    "file": file_path,
                    "package": package_name,
                    "method_name": method["name"],
                    "short_call_patterns": [
                        method["name"],  # direct call
                        f"{package_name}::{method['name']}",  # full package call
                        f"$obj->{method['name']}",  # object method call
                    ]
                }
    
    # Second pass: analyze function calls
    cross_file_calls = []
    
    for file_ast in combined_ast["files"]:
        source_file = file_ast["source_file"]
        
        # Analyze calls in package script execution
        for package in file_ast.get("packages", []):
            if package.get("script_execution") and package["script_execution"].get("body"):
                calls = find_function_calls_in_code(
                    package["script_execution"]["body"], 
                    global_functions, 
                    source_file,
                    package["name"]
                )
                cross_file_calls.extend(calls)
            
            # Analyze calls in methods
            for method in package.get("methods", []):
                if method.get("body"):
                    calls = find_function_calls_in_code(
                        method["body"], 
                        global_functions, 
                        source_file,
                        package["name"],
                        method["full_name"]
                    )
                    cross_file_calls.extend(calls)
        
        # Analyze calls in global scope
        if file_ast.get("global_scope") and file_ast["global_scope"].get("body"):
            calls = find_function_calls_in_code(
                file_ast["global_scope"]["body"], 
                global_functions, 
                source_file,
                "global"
            )
            cross_file_calls.extend(calls)
    
    # Add cross-file calls to the combined AST
    combined_ast["cross_file_calls"] = cross_file_calls
    combined_ast["global_function_registry"] = global_functions
    
    return combined_ast

def find_function_calls_in_code(code, global_functions, caller_file, caller_package, caller_method=None):
    """
    Find function calls in code and determine if they are cross-file calls.
    """
    calls = []
    
    # Common Perl function call patterns
    patterns = [
        r'(\w+(?:::\w+)*)->\s*(\w+)\s*\(',  # Object method calls: $obj->method()
        r'(\w+(?:::\w+)*)::\s*(\w+)\s*\(',   # Package function calls: Package::function()
        r'(\w+)\s*\(',                       # Direct function calls: function()
        r'(\w+(?:::\w+)*)->\s*new\s*\(',     # Constructor calls: Package->new()
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, code, re.MULTILINE)
        for match in matches:
            if len(match.groups()) == 2:
                # Object method or package function call
                package_or_obj = match.group(1)
                method_name = match.group(2)
                
                # Check if this is a cross-file call
                possible_full_names = [
                    f"{package_or_obj}::{method_name}",
                    method_name  # For object calls where package_or_obj is a variable
                ]
                
                for full_name in possible_full_names:
                    if full_name in global_functions:
                        target_info = global_functions[full_name]
                        if target_info["file"] != caller_file:
                            calls.append({
                                "type": "CrossFileCall",
                                "caller_file": caller_file,
                                "caller_package": caller_package,
                                "caller_method": caller_method,
                                "target_file": target_info["file"],
                                "target_package": target_info["package"],
                                "target_method": target_info["method_name"],
                                "target_full_name": full_name,
                                "call_pattern": match.group(0),
                                "call_type": "object_method" if "->" in match.group(0) else "package_function"
                            })
                        break
            
            elif len(match.groups()) == 1:
                # Direct function call or constructor
                func_call = match.group(1)
                
                if "->new" in match.group(0):
                    # Constructor call
                    constructor_name = f"{func_call}::new"
                    if constructor_name in global_functions:
                        target_info = global_functions[constructor_name]
                        if target_info["file"] != caller_file:
                            calls.append({
                                "type": "CrossFileCall",
                                "caller_file": caller_file,
                                "caller_package": caller_package,
                                "caller_method": caller_method,
                                "target_file": target_info["file"],
                                "target_package": target_info["package"],
                                "target_method": "new",
                                "target_full_name": constructor_name,
                                "call_pattern": match.group(0),
                                "call_type": "constructor"
                            })
                else:
                    # Direct function call - check if it exists in global functions
                    for full_name, target_info in global_functions.items():
                        if target_info["method_name"] == func_call and target_info["file"] != caller_file:
                            calls.append({
                                "type": "CrossFileCall",
                                "caller_file": caller_file,
                                "caller_package": caller_package,
                                "caller_method": caller_method,
                                "target_file": target_info["file"],
                                "target_package": target_info["package"],
                                "target_method": target_info["method_name"],
                                "target_full_name": full_name,
                                "call_pattern": match.group(0),
                                "call_type": "direct_function"
                            })
                            break
    
    return calls

def analyze_dependencies(combined_ast):
    """Analyze dependencies, looking for 'use' statements at both file and package level."""
    dependencies = defaultdict(set)
    package_definitions = {}
    all_use_statements = []

    for file_ast in combined_ast["files"]:
        file_path = file_ast["source_file"]
        all_use_statements.extend(file_ast.get("use_statements", []))

        for pkg_decl in file_ast.get("packages", []):
            package_definitions[pkg_decl["name"]] = {
                "file": file_path,
                "methods": [m["name"] for m in pkg_decl["methods"]]
            }

            all_use_statements.extend(pkg_decl.get("use_statements", []))

    for use_stmt in all_use_statements:
        module = use_stmt["module"]
        simple_module = module.split()[0]
        file_of_use = use_stmt["source_file"]

        if simple_module in package_definitions:
            dependencies[file_of_use].add(package_definitions[simple_module]["file"])

    return dict(dependencies), package_definitions

def combine_asts(file_asts):
    """Combine multiple file ASTs into a single comprehensive AST."""
    combined_ast = {
        "type": "ProjectAST",
        "files": file_asts,
        "metadata": {
            "total_files": len(file_asts),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    }

    dependencies, package_definitions = analyze_dependencies(combined_ast)
    combined_ast["dependencies"] = dependencies
    combined_ast["package_definitions"] = package_definitions

    return combined_ast

def process_single_file(perl_file, verbose=False):
    """Process a single Perl file and return its AST."""
    try:
        if verbose:
            print(f"Processing {perl_file}...")
        ast = create_ast_from_file(perl_file)
        if ast is None:
            return {"file": perl_file, "status": "failed", "error": "Failed to create AST", "ast": None}
        return {"file": perl_file, "status": "success", "ast": ast}
    except Exception as e:
        return {"file": perl_file, "status": "failed", "error": str(e), "ast": None}

def process_files_batch(perl_files, max_workers=4, verbose=False):
    """Process multiple Perl files in parallel."""
    results = []
    successful_asts = []
    successful = 0
    failed = 0

    print(f"Processing {len(perl_files)} Perl files...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(process_single_file, perl_file, verbose): perl_file for perl_file in perl_files}

        for future in as_completed(future_to_file):
            result = future.result()
            results.append(result)

            if result["status"] == "success":
                successful += 1
                successful_asts.append(result["ast"])
                if verbose:
                    print(f"✓ {result['file']}")
            else:
                failed += 1
                print(f"✗ {result['file']}: {result['error']}")

    return results, successful_asts, successful, failed

def create_summary_report(results, combined_ast, ast_dir):
    """Create a summary report of the batch processing and combined AST."""
    package_defs = combined_ast.get("package_definitions", {})
    total_packages = len(package_defs)
    total_methods = sum(len(info.get("methods", [])) for info in package_defs.values())

    total_use_statements = 0
    for f in combined_ast.get("files", []):
        total_use_statements += len(f.get("use_statements", []))
        for pkg in f.get("packages", []):
            total_use_statements += len(pkg.get("use_statements", []))

    dependency_count = sum(len(deps) for deps in combined_ast.get("dependencies", {}).values())
    cross_file_calls = len(combined_ast.get("cross_file_calls", []))

    summary = {
        "processing_summary": {
            "total_files": len(results),
            "successful": sum(1 for r in results if r["status"] == "success"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "ast_summary": {
            "total_packages": total_packages,
            "total_methods": total_methods,
            "total_use_statements": total_use_statements,
            "total_dependencies": dependency_count,
            "cross_file_calls": cross_file_calls
        },
        "package_overview": {
            pkg: {"file": info["file"], "method_count": len(info.get("methods", []))}
            for pkg, info in package_defs.items()
        },
        "dependency_graph": combined_ast.get("dependencies", {}),
        "cross_file_calls_summary": {
            "total_calls": cross_file_calls,
            "unique_file_pairs": len(set((call["caller_file"], call["target_file"]) 
                                      for call in combined_ast.get("cross_file_calls", []))),
            "call_types": {}
        },
        "failed_files": [{"file": r["file"], "error": r["error"]} for r in results if r["status"] == "failed"]
    }

    # Summarize call types
    call_types = defaultdict(int)
    for call in combined_ast.get("cross_file_calls", []):
        call_types[call.get("call_type", "unknown")] += 1
    summary["cross_file_calls_summary"]["call_types"] = dict(call_types)

    summary_file = os.path.join(ast_dir, "project_summary.json")
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    return summary_file

def main():
    parser = argparse.ArgumentParser(description='Parse Perl files and generate combined AST with cross-file relationship analysis')
    parser.add_argument('path', nargs='?', default='examples',
                        help='Path to Perl file or directory containing Perl files (default: examples)')
    parser.add_argument('-o', '--output', default='AST',
                        help='Directory to save AST output (default: AST)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('-r', '--recursive', action='store_true', default=True,
                        help='Search for Perl files recursively in directories (default: True)')
    parser.add_argument('--no-recursive', action='store_false', dest='recursive',
                        help='Disable recursive search')
    parser.add_argument('-j', '--jobs', type=int, default=os.cpu_count() or 4,
                        help='Number of parallel jobs for processing (default: number of CPUs)')
    parser.add_argument('--individual', action='store_true',
                        help='Also save individual AST files for each Perl file')

    args = parser.parse_args()

    ast_dir = args.output
    ensure_directory(ast_dir)

    print(f"Searching for Perl files in: {args.path}")
    perl_files = find_perl_files(args.path, args.recursive)

    if not perl_files:
        print(f"No Perl files found in {args.path}")
        sys.exit(1)

    print(f"Found {len(perl_files)} Perl files")

    start_time = time.time()

    results, successful_asts, successful, failed = process_files_batch(
        perl_files, args.jobs, args.verbose
    )

    if not successful_asts:
        print("\nNo files were successfully parsed. Exiting.")
        sys.exit(1)

    print(f"\nCombining ASTs from {len(successful_asts)} files...")
    combined_ast = combine_asts(successful_asts)

    # Add cross-file call analysis
    print("Analyzing cross-file function calls...")
    combined_ast = analyze_cross_file_calls(combined_ast)

    combined_ast_file = os.path.join(ast_dir, "combined_project_ast.json")
    with open(combined_ast_file, 'w') as f:
        json.dump(convert_sets_to_lists(combined_ast), f, indent=2)

    if args.individual:
        individual_dir = os.path.join(ast_dir, "individual_files")
        ensure_directory(individual_dir)
        for result in results:
            if result["status"] == "success":
                base_name = os.path.basename(result["file"]).replace('.', '_')
                individual_file = os.path.join(individual_dir, f"{base_name}_ast.json")
                with open(individual_file, 'w') as f:
                    json.dump(convert_sets_to_lists(result["ast"]), f, indent=2)

    end_time = time.time()

    summary_file = create_summary_report(results, convert_sets_to_lists(combined_ast), ast_dir)

    print(f"\n--- Processing completed in {end_time - start_time:.2f} seconds ---")
    print(f"Results: {successful} successful, {failed} failed")
    print(f"Combined AST contains:")
    print(f" - {len(combined_ast.get('package_definitions', {}))} packages")
    
    total_use_statements = sum(
        len(f.get("use_statements", [])) + sum(len(p.get("use_statements", [])) for p in f.get("packages", []))
        for f in combined_ast.get("files", [])
    )
    print(f" - {total_use_statements} total 'use' statements")
    print(f" - {sum(len(deps) for deps in combined_ast.get('dependencies', {}).values())} internal dependencies identified")
    print(f" - {len(combined_ast.get('cross_file_calls', []))} cross-file function calls detected")

    print(f"\nFiles saved:")
    print(f" - Combined AST: {combined_ast_file}")
    print(f" - Summary report: {summary_file}")

    if args.individual:
        print(f" - Individual ASTs: {individual_dir}")

    if failed > 0:
        print(f"\nFailed files:")
        for result in results:
            if result["status"] == "failed":
                print(f" - {result['file']}: {result['error']}")

    # Display cross-file call summary
    cross_file_calls = combined_ast.get("cross_file_calls", [])
    if cross_file_calls:
        print(f"\nCross-file call summary:")
        call_types = defaultdict(int)
        file_pairs = set()
        for call in cross_file_calls:
            call_types[call.get("call_type", "unknown")] += 1
            file_pairs.add((call["caller_file"], call["target_file"]))
        
        print(f" - Total cross-file calls: {len(cross_file_calls)}")
        print(f" - Unique file pairs: {len(file_pairs)}")
        print(f" - Call types: {dict(call_types)}")

if __name__ == "__main__":
    main()
