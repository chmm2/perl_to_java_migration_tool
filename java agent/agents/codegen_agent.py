# codegen_agent.py
"""
FIXED: Enhanced code generation agents for robust Perl-to-Java conversion.
"""

import logging
from pathlib import Path
from typing import List, Dict

from config import EnhancedGroqLLM
from state import AgentState


class CodeGenerationAgent:
    """FIXED: Agent responsible for generating comprehensive Java code from Perl analysis."""
    
    def __init__(self, llm: EnhancedGroqLLM):
        self.llm = llm

    async def __call__(self, state: AgentState) -> AgentState:
        """
        FIXED: Code Generation Agent with improved script/module handling.
        """
        if state.errors and "scaffold" not in " ".join(state.errors):
            logging.warning("Proceeding with code generation despite previous errors")

        try:
            class_name = self._generate_class_name(state.file_path)
            
            # FIXED: Improved archetype detection with better fallbacks
            file_archetype = self._determine_file_archetype(state)
            
            logging.info(f"🎯 File archetype determined: {file_archetype}")
            
            # FIXED: Better script handling logic
            if file_archetype == 'script':
                logging.info(f"📝 Generating main method scaffold for script: {class_name}")
                state.java_code = self._generate_comprehensive_main_scaffold(class_name, state)
                state.translation_notes.append("Generated comprehensive main method scaffold for procedural script")
                
                # FIXED: Validate the generated scaffold
                if self._validate_generated_code(state.java_code):
                    logging.info(f"✅ Script scaffold validation passed: {len(state.java_code)} chars")
                    return state
                else:
                    logging.warning("⚠️ Script scaffold failed validation, generating emergency fallback")
                    state.java_code = self._generate_emergency_script_fallback(class_name, state)
                    return state
            
            # FIXED: Enhanced module processing
            logging.info(f"🏭 Processing as module/class: {class_name}")
            
            # Extract better metadata for code generation
            packages_data = state.structured_data.get('packages', [])
            method_count = self._count_total_methods(packages_data)
            subroutines = state.perl_analysis.get('subroutines', [])
            
            logging.info(f"📊 Analysis data - Packages: {len(packages_data)}, Methods: {method_count}, Subroutines: {len(subroutines)}")
            
            # FIXED: Better LLM generation with fallbacks
            java_code = None
            
            # Try LLM generation first if we have good analysis data
            if len(subroutines) > 0 or method_count > 0:
                try:
                    logging.info("🤖 Attempting LLM-based code generation...")
                    java_code = await self.llm.generate_java_class(
                        class_name=class_name,
                        perl_content=state.perl_content or "# Synthesized from AST data",
                        analysis_data=state.perl_analysis,
                        packages=[p.get('packageName', '') for p in packages_data],
                        method_count=method_count
                    )
                    
                    if self._validate_generated_code(java_code):
                        logging.info(f"✅ LLM generation successful: {len(java_code)} chars")
                        state.java_code = java_code
                        state.translation_notes.append("Generated using advanced LLM analysis")
                        return state
                    else:
                        logging.warning("⚠️ LLM generated invalid code, falling back to comprehensive scaffold")
                        java_code = None
                        
                except Exception as e:
                    logging.warning(f"🔄 LLM generation failed: {e}, using comprehensive scaffold")
                    java_code = None
            
            # FIXED: Generate comprehensive scaffold if LLM failed or no analysis data
            if not java_code:
                logging.info("📝 Generating comprehensive scaffold from analysis data")
                state.java_code = self._generate_comprehensive_scaffold(class_name, state)
                state.translation_notes.append("Generated comprehensive scaffold from AST analysis")
            
            # FIXED: Final validation with better error handling
            if not self._validate_generated_code(state.java_code):
                logging.warning("⚠️ Generated code failed final validation")
                if len(state.java_code) < 50:
                    # Code is too short, generate emergency fallback
                    state.java_code = self._generate_emergency_class_fallback(class_name, state)
                    state.translation_notes.append("Used emergency fallback due to validation failure")
                else:
                    # Code exists but has issues, try to fix minor problems
                    state.java_code = self._apply_basic_fixes(state.java_code, class_name)
                    state.translation_notes.append("Applied basic fixes to generated code")
            
            lines_count = len(state.java_code.split('\n'))
            logging.info(f"📊 Final generation: {len(state.java_code)} characters ({lines_count} lines)")
                
        except Exception as e:
            error_msg = f"Code generation failed: {e}"
            state.errors.append(error_msg)
            logging.error(error_msg, exc_info=True)
            
            # FIXED: Better emergency handling
            class_name = self._generate_class_name(state.file_path)
            if state.file_path.endswith('.pl'):
                state.java_code = self._generate_emergency_script_fallback(class_name, state)
            else:
                state.java_code = self._generate_emergency_class_fallback(class_name, state)
                
        return state
    
    def _determine_file_archetype(self, state: AgentState) -> str:
        """FIXED: Determine file archetype with better logic."""
        # Check explicit archetype first
        explicit_archetype = state.structured_data.get('file_archetype')
        if explicit_archetype in ['script', 'module']:
            return explicit_archetype
        
        # Check file extension
        file_path = state.file_path
        if file_path.endswith('.pl'):
            # .pl files are usually scripts, but check if they have substantial OOP structure
            packages = state.structured_data.get('packages', [])
            methods = []
            for pkg in packages:
                if isinstance(pkg, dict):
                    pkg_methods = pkg.get('methods', [])
                    if isinstance(pkg_methods, list):
                        methods.extend(pkg_methods)
            
            # If .pl file has multiple methods/packages, treat as module
            if len(methods) > 3 or len(packages) > 1:
                return 'module'
            else:
                return 'script'
        elif file_path.endswith('.pm'):
            return 'module'
        
        # Fallback: analyze content
        app_patterns = state.structured_data.get('applicationPatterns', {})
        if app_patterns.get('isScript', False) and not app_patterns.get('isModule', False):
            return 'script'
        
        return 'module'  # Default to module
    
    def _count_total_methods(self, packages_data: List[Dict]) -> int:
        """Count total methods across all packages."""
        total = 0
        for pkg in packages_data:
            if isinstance(pkg, dict):
                methods = pkg.get('methods', [])
                if isinstance(methods, list):
                    total += len(methods)
        return total
    
    def _generate_comprehensive_main_scaffold(self, class_name: str, state: AgentState) -> str:
        """FIXED: Generate comprehensive main method scaffold for scripts."""
        file_name = Path(state.file_path).name
        app_patterns = state.structured_data.get('applicationPatterns', {})
        imports_needed = state.perl_analysis.get('imports_needed', ['java.util.*', 'java.io.*'])
        
        # Build comprehensive scaffold
        java_lines = [
            "/*",
            f" * Converted Perl Script: {file_name}",
            " * Generated using AST-only analysis",
            f" * Application Type: {app_patterns.get('applicationType', 'script')}",
            " *",
            " * IMPLEMENTATION REQUIRED:",
            " * - Translate Perl script logic to main method",
            " * - Add error handling as appropriate", 
            " * - Implement any required helper methods",
            " */"
        ]
        
        # Add imports
        for imp in sorted(set(imports_needed)):
            if imp:
                java_lines.append(f"import {imp};")
        
        java_lines.extend([
            "",
            f"public class {class_name} {{",
            ""
        ])
        
        # Add instance variables if detected
        packages_data = state.structured_data.get('packages', [])
        estimated_fields = []
        for pkg in packages_data:
            if isinstance(pkg, dict):
                fields = pkg.get('estimatedFields', [])
                if isinstance(fields, list):
                    estimated_fields.extend(fields)
        
        if estimated_fields:
            java_lines.append("    // Instance variables (inferred from analysis)")
            for field in estimated_fields[:5]:  # Limit to avoid clutter
                if isinstance(field, dict):
                    field_name = field.get('name', 'unknown')
                    field_type = field.get('type', 'String')
                    java_lines.append(f"    private {field_type} {field_name};")
            java_lines.append("")
        
        # Add constructor if we have fields
        if estimated_fields:
            java_lines.extend([
                "    /**",
                "     * Constructor",
                "     */",
                f"    public {class_name}() {{",
                "        // Initialize variables as needed"
            ])
            
            for field in estimated_fields[:5]:
                if isinstance(field, dict):
                    field_name = field.get('name', 'unknown')
                    field_type = field.get('type', 'String')
                    if field_type == 'String':
                        java_lines.append(f"        this.{field_name} = \"\";")
                    elif field_type in ['int', 'Integer']:
                        java_lines.append(f"        this.{field_name} = 0;")
                    else:
                        java_lines.append(f"        this.{field_name} = null;")
            
            java_lines.extend([
                "    }",
                ""
            ])
        
        # Add helper methods if detected in analysis
        subroutines = state.perl_analysis.get('subroutines', [])
        if subroutines:
            for sub in subroutines[:3]:  # Add a few key methods
                if isinstance(sub, dict):
                    method_name = sub.get('name', 'helperMethod')
                    if method_name and method_name != 'main':
                        java_method_name = self._to_camel_case(method_name)
                        java_lines.extend([
                            "    /**",
                            f"     * Helper method: {method_name}",
                            "     */",
                            f"    private void {java_method_name}() {{",
                            f"        // TODO: Implement {method_name} logic from Perl",
                            "        System.out.println(\"Executing " + method_name + "\");",
                            "    }",
                            ""
                        ])
        
        # Add comprehensive main method
        java_lines.extend([
            "    /**",
            "     * Main method - Entry point for the converted Perl script",
            "     */",
            "    public static void main(String[] args) {",
            f"        {class_name} instance = new {class_name}();",
            ""
        ])
        
        # Add application-specific logic based on patterns
        if app_patterns.get('hasUserInput', False):
            java_lines.extend([
                "        // User input handling detected in original script",
                "        Scanner scanner = new Scanner(System.in);",
                ""
            ])
        
        if app_patterns.get('hasInteractiveMenu', False):
            java_lines.extend([
                "        // Interactive menu system detected",
                "        boolean running = true;",
                "        while (running) {",
                "            System.out.println(\"Menu options:\");",
                "            System.out.println(\"1. Option 1\");",
                "            System.out.println(\"2. Option 2\");", 
                "            System.out.println(\"3. Exit\");",
                "            System.out.print(\"Choose option: \");",
                "            ",
                "            // TODO: Implement menu logic from original Perl script",
                "            running = false; // Temporary - implement proper exit condition",
                "        }",
                ""
            ])
        elif app_patterns.get('hasMainLoop', False):
            java_lines.extend([
                "        // Main processing loop detected in original script",
                "        // TODO: Implement main loop logic from Perl",
                ""
            ])
        
        # Add method calls if we generated helper methods
        if subroutines:
            java_lines.append("        // Execute helper methods")
            for sub in subroutines[:3]:
                if isinstance(sub, dict):
                    method_name = sub.get('name', 'helperMethod')
                    if method_name and method_name != 'main':
                        java_method_name = self._to_camel_case(method_name)
                        java_lines.append(f"        instance.{java_method_name}();")
            java_lines.append("")
        
        java_lines.extend([
            "        System.out.println(\"Perl script conversion completed.\");",
            "        System.out.println(\"TODO: Implement actual script logic\");",
            "    }",
            "}"
        ])
        
        return '\n'.join(java_lines)
    
    def _generate_comprehensive_scaffold(self, class_name: str, state: AgentState) -> str:
        """FIXED: Generate comprehensive Java class scaffold from analysis data."""
        try:
            # Extract comprehensive analysis data
            subroutines = state.perl_analysis.get('subroutines', [])
            global_variables = state.perl_analysis.get('global_variables', [])
            imports_needed = state.perl_analysis.get('imports_needed', ['java.util.*'])
            packages_data = state.structured_data.get('packages', [])
            
            java_lines = [
                "/*",
                f" * Converted from Perl: {Path(state.file_path).name}",
                " * Generated using comprehensive AST analysis",
                " *",
                " * This is a scaffold with method signatures and basic structure.",
                " * Implementation details need to be added based on original Perl logic.",
                " */"
            ]
            
            # Add imports
            for imp in sorted(set(imports_needed)):
                if imp:
                    java_lines.append(f"import {imp};")
            
            if imports_needed:
                java_lines.append("")
            
            # Add class declaration
            java_lines.extend([
                f"public class {class_name} {{",
                ""
            ])
            
            # Add instance variables from multiple sources
            all_fields = []
            
            # From global variables analysis
            if global_variables:
                all_fields.extend(global_variables)
            
            # From package estimated fields
            for pkg in packages_data:
                if isinstance(pkg, dict):
                    estimated_fields = pkg.get('estimatedFields', [])
                    if isinstance(estimated_fields, list):
                        all_fields.extend(estimated_fields)
            
            if all_fields:
                java_lines.append("    // Instance variables")
                seen_fields = set()
                for field in all_fields:
                    if isinstance(field, dict):
                        field_name = field.get('name', 'unknown')
                        field_type = field.get('java_type') or field.get('type', 'String')
                        if field_name and field_name not in seen_fields:
                            java_lines.append(f"    private {field_type} {field_name};")
                            seen_fields.add(field_name)
                java_lines.append("")
            
            # Add constructor
            has_constructor = any(sub.get('name') == 'new' for sub in subroutines if isinstance(sub, dict))
            if not has_constructor:
                java_lines.extend([
                    "    /**",
                    "     * Default constructor",
                    "     */",
                    f"    public {class_name}() {{",
                    "        // Initialize instance variables",
                ])
                
                # Initialize fields
                seen_fields = set()
                for field in all_fields:
                    if isinstance(field, dict):
                        field_name = field.get('name', 'unknown')
                        field_type = field.get('java_type') or field.get('type', 'String')
                        if field_name and field_name not in seen_fields:
                            if field_type == 'String':
                                java_lines.append(f"        this.{field_name} = \"\";")
                            elif field_type in ['int', 'Integer']:
                                java_lines.append(f"        this.{field_name} = 0;")
                            elif field_type in ['boolean', 'Boolean']:
                                java_lines.append(f"        this.{field_name} = false;")
                            else:
                                java_lines.append(f"        this.{field_name} = null;")
                            seen_fields.add(field_name)
                
                java_lines.extend([
                    "    }",
                    ""
                ])
            
            # Add methods from subroutines
            if subroutines:
                for sub in subroutines:
                    if isinstance(sub, dict):
                        method_lines = self._generate_comprehensive_method(sub, class_name)
                        java_lines.extend(method_lines)
                        java_lines.append("")
            else:
                # Generate methods from package data
                for pkg in packages_data:
                    if isinstance(pkg, dict):
                        methods = pkg.get('methods', [])
                        if isinstance(methods, list):
                            for method in methods:
                                if isinstance(method, dict):
                                    method_name = method.get('name', '')
                                    if method_name:
                                        basic_method = self._generate_basic_method(method_name, method)
                                        java_lines.extend(basic_method)
                                        java_lines.append("")
                
                # If still no methods, add a default one
                if not any(pkg.get('methods') for pkg in packages_data):
                    java_lines.extend([
                        "    /**",
                        "     * Default method",
                        "     */",
                        "    public void defaultMethod() {",
                        "        System.out.println(\"Method implementation needed\");",
                        "    }",
                        ""
                    ])
            
            # Close class
            java_lines.append("}")
            
            return '\n'.join(java_lines)
            
        except Exception as e:
            logging.error(f"Comprehensive scaffold generation failed: {e}")
            return self._generate_emergency_class_fallback(class_name, state)
    
    def _generate_comprehensive_method(self, subroutine: Dict, class_name: str) -> List[str]:
        """FIXED: Generate comprehensive method implementation."""
        method_lines = []
        
        try:
            method_name = subroutine.get('name', 'defaultMethod')
            parameters = subroutine.get('parameters', [])
            parameter_types = subroutine.get('parameter_types', [])
            returns = subroutine.get('returns', 'void')
            purpose = subroutine.get('purpose', f'Implementation of {method_name}')
            
            # Convert method name to Java convention
            java_method_name = self._to_camel_case(method_name)
            
            # Handle constructor
            if method_name == 'new':
                java_method_name = class_name
                returns = ""  # Constructors don't have return types
            
            # Create parameter list (skip 'self' parameter)
            param_list = []
            for i, param in enumerate(parameters):
                if param and param != 'self':
                    param_type = parameter_types[i] if i < len(parameter_types) else 'Object'
                    param_list.append(f"{param_type} {param}")
            
            param_str = ", ".join(param_list)
            
            # Add comprehensive javadoc
            method_lines.extend([
                "    /**",
                f"     * {purpose}",
                "     *"
            ])
            
            for param in param_list:
                param_name = param.split()[-1]
                method_lines.append(f"     * @param {param_name} method parameter")
            
            if returns and returns != 'void':
                method_lines.append(f"     * @return {returns}")
            
            method_lines.extend([
                "     */",
            ])
            
            # Create method signature
            if method_name == 'new':
                method_lines.append(f"    public {java_method_name}({param_str}) {{")
            else:
                method_lines.append(f"    public {returns} {java_method_name}({param_str}) {{")
            
            # Add comprehensive method body
            if method_name == 'new':
                # Constructor implementation
                method_lines.extend([
                    "        // Constructor implementation",
                    "        // TODO: Initialize instance variables based on Perl constructor logic",
                    "        super();",
                ])
                if param_list:
                    method_lines.append("        // Process constructor parameters")
                    for param in param_list:
                        param_name = param.split()[-1]
                        method_lines.append(f"        // TODO: Handle parameter '{param_name}'")
            elif method_name.startswith('get_'):
                # Getter method
                field_name = method_name[4:]
                method_lines.extend([
                    f"        // Getter for {field_name}",
                    f"        // TODO: Return appropriate field value",
                    f"        return this.{field_name};  // TODO: Ensure field exists"
                ])
            elif method_name.startswith('set_'):
                # Setter method
                field_name = method_name[4:]
                method_lines.extend([
                    f"        // Setter for {field_name}",
                    f"        // TODO: Set appropriate field value"
                ])
                if param_list:
                    param_name = param_list[0].split()[-1]
                    method_lines.append(f"        this.{field_name} = {param_name};  // TODO: Ensure field exists")
                else:
                    method_lines.append(f"        // TODO: Set {field_name} value")
                
                if returns != 'void':
                    method_lines.append("        return this;")
            elif method_name.startswith('is_') or method_name.startswith('has_'):
                # Boolean method
                method_lines.extend([
                    f"        // Boolean check: {method_name}",
                    "        // TODO: Implement boolean logic from Perl",
                    "        return true; // TODO: Replace with actual logic"
                ])
            else:
                # Regular business method
                method_lines.extend([
                    f"        // Business method: {method_name}",
                    f"        // TODO: Implement {method_name} logic from Perl"
                ])
                
                if param_list:
                    method_lines.append("        // Process method parameters:")
                    for param in param_list:
                        param_name = param.split()[-1]
                        method_lines.append(f"        // TODO: Use parameter '{param_name}'")
                
                method_lines.append("        ")
                
                # Add appropriate return statement
                if returns and returns != 'void':
                    if returns == 'String':
                        method_lines.append("        return \"TODO: Return appropriate string\";")
                    elif returns in ['int', 'Integer']:
                        method_lines.append("        return 0; // TODO: Return appropriate integer")
                    elif returns in ['boolean', 'Boolean']:
                        method_lines.append("        return false; // TODO: Return appropriate boolean")
                    else:
                        method_lines.append("        return null; // TODO: Return appropriate object")
                else:
                    method_lines.append("        // Method completed")
            
            method_lines.append("    }")
            
        except Exception as e:
            logging.error(f"Method generation failed for {subroutine}: {e}")
            method_lines = [
                "    /**",
                "     * Method generation failed",
                "     */",
                "    public void errorMethod() {",
                "        System.err.println(\"Method generation encountered errors\");",
                "    }"
            ]
        
        return method_lines
    
    def _generate_basic_method(self, method_name: str, method_data: Dict) -> List[str]:
        """Generate a basic method from minimal method data."""
        java_method_name = self._to_camel_case(method_name)
        
        return [
            "    /**",
            f"     * Method: {method_name}",
            "     */",
            f"    public void {java_method_name}() {{",
            f"        // TODO: Implement {method_name} from Perl",
            f"        System.out.println(\"Executing {method_name}\");",
            "    }"
        ]
    
    def _generate_emergency_script_fallback(self, class_name: str, state: AgentState) -> str:
        """FIXED: Emergency fallback for script files."""
        return f"""import java.util.*;
import java.io.*;

/**
 * Emergency fallback for script: {Path(state.file_path).name}
 * Code generation encountered errors - manual implementation required
 */
public class {class_name} {{
    
    public static void main(String[] args) {{
        System.out.println("Script conversion requires manual implementation");
        System.out.println("Original file: {Path(state.file_path).name}");
        
        // TODO: Implement script logic here
        // Refer to original Perl script for functionality
    }}
}}"""
    
    def _generate_emergency_class_fallback(self, class_name: str, state: AgentState) -> str:
        """FIXED: Emergency fallback for class files."""
        return f"""import java.util.*;

/**
 * Emergency fallback for class: {Path(state.file_path).name}
 * Code generation encountered errors - manual implementation required
 */
public class {class_name} {{
    
    /**
     * Default constructor
     */
    public {class_name}() {{
        // Default constructor
    }}
    
    /**
     * Default method - replace with actual methods from Perl
     */
    public void defaultMethod() {{
        System.out.println("Class conversion requires manual implementation");
    }}
    
    /**
     * Main method for testing
     */
    public static void main(String[] args) {{
        {class_name} instance = new {class_name}();
        instance.defaultMethod();
    }}
}}"""
    
    def _generate_class_name(self, file_path: str) -> str:
        """Generate appropriate Java class name from file path."""
        try:
            base_name = Path(file_path).stem.replace(" ", "_").replace("-", "_")
            # Convert to PascalCase
            class_name = ''.join(word.capitalize() for word in base_name.split('_'))
            # Ensure it starts with a letter and contains only valid characters
            if not class_name or not class_name[0].isalpha():
                class_name = "Generated" + class_name
            # Remove any non-alphanumeric characters and ensure it's valid
            class_name = ''.join(c for c in class_name if c.isalnum())
            return class_name if class_name else "DefaultClass"
        except Exception:
            return "DefaultClass"
    
    def _validate_generated_code(self, java_code: str) -> bool:
        """FIXED: Validate that generated Java code is reasonable."""
        if not java_code or len(java_code) < 20:
            return False
        
        # Check for basic Java class structure
        if not any(java_code.strip().startswith(prefix) for prefix in ['import', 'public class', 'class', '/*', '//']):
            return False
        
        # Check for class declaration
        if 'class ' not in java_code:
            return False
        
        # Check for balanced braces (basic validation)
        open_braces = java_code.count('{')
        close_braces = java_code.count('}')
        
        # Must have braces and they must be balanced
        if open_braces == 0 or open_braces != close_braces:
            return False
        
        # Check for reasonable content length
        if len(java_code) < 50:
            return False
        
        return True
    
    def _apply_basic_fixes(self, java_code: str, class_name: str) -> str:
        """FIXED: Apply basic fixes to generated code."""
        if not java_code:
            return self._generate_emergency_class_fallback(class_name, None)
        
        lines = java_code.split('\n')
        fixed_lines = []
        
        # Add basic imports if missing
        has_imports = any(line.strip().startswith('import ') for line in lines)
        has_class = any('class ' in line for line in lines)
        
        if not has_imports and has_class:
            fixed_lines.extend([
                "import java.util.*;",
                "import java.io.*;",
                ""
            ])
        
        # Process each line
        for line in lines:
            # Fix missing semicolons on simple statements
            stripped = line.strip()
            if (stripped and 
                not stripped.endswith((';', '{', '}', '*/')) and
                not stripped.startswith(('import ', 'package ', 'public class', 
                                       'private class', '//', '/*', '*', 'public ', 'private ')) and
                not any(keyword in stripped for keyword in ['if ', 'for ', 'while ', 'try ', 'catch '])):
                if '=' in stripped or 'return' in stripped:
                    if not stripped.endswith(';'):
                        line = line.rstrip() + ';'
            
            fixed_lines.append(line)
        
        result = '\n'.join(fixed_lines)
        
        # Fix unbalanced braces
        open_braces = result.count('{')
        close_braces = result.count('}')
        if open_braces > close_braces:
            result += '\n' + '}' * (open_braces - close_braces)
        
        return result
    
    def _to_camel_case(self, snake_str: str) -> str:
        """Convert snake_case to camelCase."""
        if not snake_str:
            return "defaultMethod"
        
        # Handle special cases
        if snake_str == 'new':
            return snake_str  # Keep constructor name
        
        components = snake_str.split('_')
        if not components or not components[0]:
            return "defaultMethod"
        
        # First component lowercase, rest capitalize
        result = components[0].lower()
        for component in components[1:]:
            if component:
                result += component.capitalize()
        
        return result if result else "defaultMethod"


class CodeFixerAgent:
    """FIXED: Agent responsible for fixing Java compilation errors."""
    
    def __init__(self, llm: EnhancedGroqLLM):
        self.llm = llm

    async def __call__(self, state: AgentState) -> AgentState:
        """
        FIXED: Code Fixer Agent with better error handling.
        """
        state.fix_attempts += 1
        
        if not state.java_code:
            logging.warning("No Java code to fix")
            return state
        
        try:
            if state.errors and state.fix_attempts <= 2:
                # FIXED: Better error categorization and fixing
                error_types = self._categorize_errors(state.errors)
                
                if error_types['class_name_errors']:
                    # Fix class name errors specifically
                    class_name = self._extract_target_class_name(state.file_path)
                    try:
                        fixed_code = await self.llm.fix_class_name_error(
                            state.java_code, class_name
                        )
                        
                        if fixed_code and "class" in fixed_code.lower():
                            state.java_code = fixed_code
                            state.errors = []
                            logging.info("✅ Fixed class name error")
                            return state
                    except Exception as e:
                        logging.warning(f"LLM class name fix failed: {e}")
                
                if error_types['compilation_errors']:
                    # Try to fix compilation errors
                    try:
                        fixed_code = await self.llm.fix_java_code(
                            state.java_code, error_types['compilation_errors']
                        )
                        if fixed_code and "class" in fixed_code.lower():
                            # Validate the fix didn't break anything
                            if len(fixed_code) > len(state.java_code) * 0.5:  # Not too much shrinkage
                                state.java_code = fixed_code
                                state.errors = []
                                logging.info("✅ Fixed compilation errors with LLM")
                                return state
                    except Exception as e:
                        logging.warning(f"LLM compilation fix failed: {e}")
                
                # FIXED: Apply programmatic fixes as fallback
                logging.info("Applying programmatic fixes...")
                original_length = len(state.java_code)
                state.java_code = self._apply_comprehensive_fixes(state.java_code)
                new_length = len(state.java_code)
                
                if new_length > original_length * 0.8:  # Not too much shrinkage
                    state.errors = []
                    logging.info(f"✅ Applied programmatic fixes: {original_length} -> {new_length} chars")
                else:
                    logging.warning("Programmatic fixes caused too much code loss")
            else:
                # FIXED: Final attempt with comprehensive fixes
                state.java_code = self._apply_comprehensive_fixes(state.java_code)
                state.errors = []
                
        except Exception as e:
            logging.error(f"Code fixing failed: {e}")
            # Keep original code rather than breaking it further
            logging.info("Keeping original code due to fixing errors")
        
        logging.info(f"Code fixing attempt {state.fix_attempts} completed")
        return state
    
    def _categorize_errors(self, errors: List[str]) -> Dict[str, List[str]]:
        """Categorize errors for targeted fixing."""
        categorized = {
            'class_name_errors': [],
            'compilation_errors': [],
            'syntax_errors': [],
            'other_errors': []
        }
        
        for error in errors:
            error_lower = error.lower()
            if 'must be defined in its own file' in error_lower:
                categorized['class_name_errors'].append(error)
            elif any(keyword in error_lower for keyword in ['syntax', 'expected', 'illegal']):
                categorized['syntax_errors'].append(error)
            elif any(keyword in error_lower for keyword in ['cannot', 'undefined', 'not found']):
                categorized['compilation_errors'].append(error)
            else:
                categorized['other_errors'].append(error)
        
        return categorized
    
    def _apply_comprehensive_fixes(self, java_code: str) -> str:
        """FIXED: Apply comprehensive programmatic fixes."""
        if not java_code:
            return java_code
        
        # Start with basic fixes
        fixed_code = java_code
        
        # Add basic imports if missing
        if not any(line.strip().startswith('import ') for line in fixed_code.split('\n')):
            fixed_code = "import java.util.*;\nimport java.io.*;\n\n" + fixed_code
        
        # Fix unbalanced braces
        open_braces = fixed_code.count('{')
        close_braces = fixed_code.count('}')
        if open_braces > close_braces:
            fixed_code += '\n' + '}' * (open_braces - close_braces)
        elif close_braces > open_braces:
            # Remove excess closing braces
            excess = close_braces - open_braces
            for _ in range(excess):
                # Remove the last standalone closing brace
                fixed_code = fixed_code.rsplit('\n}', 1)
                if len(fixed_code) == 2:
                    fixed_code = fixed_code[0] + '\n' + fixed_code[1]
                else:
                    fixed_code = fixed_code[0]
        
        # Fix missing semicolons and other syntax issues
        lines = fixed_code.split('\n')
        fixed_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines, comments, and control structures
            if not stripped or stripped.startswith(('import ', 'package ', '//', '/*', '*', 'public class', 'private class')):
                fixed_lines.append(line)
                continue
            
            # Skip lines that should not have semicolons
            if stripped.endswith(('{', '}', '*/')) or any(keyword in stripped for keyword in ['if ', 'for ', 'while ', 'try ', 'catch ', 'else']):
                fixed_lines.append(line)
                continue
            
            # Add semicolons to statements that need them
            if any(pattern in stripped for pattern in ['=', 'return ', 'throw ', 'break', 'continue']):
                if not stripped.endswith(';'):
                    line = line.rstrip() + ';'
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _extract_target_class_name(self, file_path: str) -> str:
        """Extract target class name from file path."""
        try:
            base_name = Path(file_path).stem.replace(" ", "_").replace("-", "_")
            class_name = ''.join(word.capitalize() for word in base_name.split('_'))
            if not class_name or not class_name[0].isalpha():
                class_name = "Generated" + class_name
            return ''.join(c for c in class_name if c.isalnum()) or "DefaultClass"
        except Exception:
            return "DefaultClass"