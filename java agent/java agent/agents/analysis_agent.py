# analysis_agent.py
"""
Robust Perl analysis agent with comprehensive error handling.
"""

import logging
from typing import Dict, List, Any

from config import EnhancedGroqLLM
from state import AgentState


class PerlAnalysisAgent:
    """Agent responsible for analyzing Perl code structure and patterns."""
    
    def __init__(self, llm: EnhancedGroqLLM):
        self.llm = llm

    async def __call__(self, state: AgentState) -> AgentState:
        """
        Perl Analysis Agent: Robustly analyzes Perl structure.
        
        Args:
            state: Current agent state with structured data
            
        Returns:
            Updated state with analysis results
        """
        if state.errors:
            logging.warning("Continuing analysis despite previous errors")

        try:
            # Extract metadata robustly from structured data
            packages_data = state.structured_data.get('packages', [])
            package_names = []
            all_methods = []

            # Safely extract package and method data
            for pkg in packages_data:
                if isinstance(pkg, dict):
                    pkg_name = pkg.get('packageName', '')
                    if pkg_name:
                        package_names.append(pkg_name)
                    methods = pkg.get('methods', [])
                    if isinstance(methods, list):
                        for method in methods:
                            if isinstance(method, dict):
                                method_name = method.get('name', '')
                                if method_name:
                                    all_methods.append(method_name)

            # Extract imports
            import_modules = []
            if 'importModules' in state.structured_data:
                import_modules = state.structured_data.get('importModules', [])
            else:
                imports = state.structured_data.get('imports', [])
                if isinstance(imports, list):
                    for imp in imports:
                        if isinstance(imp, dict):
                            module = imp.get('module', '')
                            if module:
                                import_modules.append(module)

            logging.info(f"📊 Analysis Input - Packages: {len(package_names)}, Methods: {len(all_methods)}, Imports: {len(import_modules)}")

            # Prepare structured AST input for LLM
            analysis_input = {
                "packages": package_names,
                "methods": all_methods,
                "imports": import_modules,
                "file_type": state.structured_data.get('fileType', 'unknown'),
                "application_patterns": state.structured_data.get('applicationPatterns', {})
            }

            try:
                # The LLM call now receives structured data, not a string of Perl code.
                state.perl_analysis = await self.llm.analyze_perl_structure(
                    analysis_input
                )
                logging.info("✅ LLM analysis from structured data completed successfully")
            except Exception as e:
                logging.warning(f"LLM analysis failed: {e}, using AST-based analysis")
                state.perl_analysis = self._create_comprehensive_ast_analysis(
                    package_names, all_methods, import_modules, state.structured_data
                )

            # Enhance analysis with AST insights
            self._enhance_analysis_with_ast(state)

            # Validate and log analysis results
            subroutines_count = len(state.perl_analysis.get('subroutines', []))
            logging.info(f"🎯 Analysis Results - Subroutines: {subroutines_count}")

        except Exception as e:
            error_msg = f"Perl analysis failed: {e}"
            state.errors.append(error_msg)
            logging.error(error_msg)
            state.perl_analysis = self._create_robust_fallback_analysis(state)

        return state
    
    def _create_comprehensive_ast_analysis(self, packages: List[str], methods: List[str], imports: List[str], structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive analysis from AST metadata."""
        
        # Create detailed subroutines
        subroutines = []
        for method in methods:
            if method:
                # Determine method characteristics
                parameters = []
                parameter_types = []
                purpose = f"Method {method}"
                returns = "void"
                
                if method == 'new':
                    parameters = ["class", "args"]
                    parameter_types = ["String", "HashMap<String, Object>"]
                    purpose = "Constructor method - creates new instance"
                    returns = "Object"
                elif method.startswith('get_'):
                    field_name = method[4:]
                    parameters = ["self"]
                    parameter_types = ["Object"]
                    purpose = f"Getter method for {field_name} property"
                    returns = "String"
                elif method.startswith('set_'):
                    field_name = method[4:]
                    parameters = ["self", "value"]
                    parameter_types = ["Object", "String"]
                    purpose = f"Setter method for {field_name} property"
                    returns = "Object"
                elif method.startswith('is_') or method.startswith('has_'):
                    parameters = ["self"]
                    parameter_types = ["Object"]
                    purpose = f"Boolean check method"
                    returns = "boolean"
                else:
                    parameters = ["self", "args"]
                    parameter_types = ["Object", "Object[]"]
                    purpose = f"Business logic method {method}"
                    returns = "Object"
                
                subroutine = {
                    "name": method,
                    "parameters": parameters,
                    "parameter_types": parameter_types,
                    "purpose": purpose,
                    "returns": returns,
                    "return_description": f"Returns {returns}",
                    "complexity": "medium" if method == 'new' else "low",
                    "perl_specifics": ["uses @_", "blessed object"] if method == 'new' else ["uses @_"],
                    "java_method_signature": self._create_java_signature(method, parameters, parameter_types, returns),
                    "conversion_notes": [f"Convert Perl {method} to Java method"]
                }
                subroutines.append(subroutine)
        
        # Create global variables from estimated fields
        global_variables = []
        for pkg_data in structured_data.get('packages', []):
            estimated_fields = pkg_data.get('estimatedFields', [])
            for field in estimated_fields:
                if isinstance(field, dict):
                    global_variables.append({
                        "name": field.get('name', 'unknown'),
                        "perl_type": "scalar",
                        "java_type": field.get('type', 'String'),
                        "scope": "instance",
                        "purpose": f"Instance variable {field.get('name', 'unknown')}",
                        "initialization": "null",
                        "access_pattern": "mutable"
                    })
        
        # Determine object model
        is_oop = len(packages) > 0 or 'new' in methods
        
        # Create comprehensive analysis
        analysis = {
            "subroutines": subroutines,
            "global_variables": global_variables,
            "object_model": {
                "is_oop": is_oop,
                "inheritance_chain": packages,
                "constructor_pattern": "new" if 'new' in methods else "custom",
                "instance_variables": [var["name"] for var in global_variables],
                "java_class_design": "Single class with proper encapsulation and methods"
            },
            "main_flow": f"AST-based analysis: {len(packages)} packages, {len(methods)} methods",
            "perl_features": self._analyze_perl_features(imports, methods),
            "imports_needed": self._determine_java_imports(imports, methods),
            "conversion_strategy": {
                "approach": "single_class" if len(packages) <= 1 else "multiple_classes",
                "design_patterns": structured_data.get('designPatterns', []),
                "error_handling": "exceptions"
            },
            "conversion_notes": [
                f"Comprehensive AST analysis completed",
                f"Found {len(methods)} methods across {len(packages)} packages",
                f"Estimated {len(global_variables)} instance variables",
                "Ready for Java code generation"
            ],
            "risk_assessment": {
                "complexity_score": min(max(len(methods), 2), 8),
                "conversion_risks": ["ast_only_conversion"] if not imports else ["module_dependencies"],
                "mitigation_strategies": ["comprehensive_testing", "incremental_conversion"]
            }
        }
        
        return analysis
    
    def _create_java_signature(self, method: str, params: List[str], param_types: List[str], returns: str) -> str:
        """Create Java method signature."""
        java_method_name = self._to_camel_case(method)
        
        # Create parameter list
        param_list = []
        for i, param in enumerate(params):
            if i < len(param_types):
                param_type = param_types[i]
            else:
                param_type = "Object"
            
            if param != "self":  # Skip 'self' parameter in Java
                param_list.append(f"{param_type} {param}")
        
        param_str = ", ".join(param_list)
        
        # Constructor special case
        if method == 'new':
            return f"public {java_method_name}({param_str})"
        else:
            return f"public {returns} {java_method_name}({param_str})"
    
    def _analyze_perl_features(self, imports: List[str], methods: List[str]) -> List[Dict[str, Any]]:
        """Analyze Perl-specific features for Java conversion."""
        features = []
        
        # Standard imports
        standard_imports = ['strict', 'warnings', 'FindBin', 'lib']
        for imp in imports:
            if any(std in imp for std in standard_imports):
                features.append({
                    "feature": f"use {imp}",
                    "usage_context": "Standard Perl pragma",
                    "frequency": "high",
                    "java_approach": "No equivalent needed" if imp in ['strict', 'warnings'] else "Use Java classpath",
                    "complexity": "trivial",
                    "libraries_needed": []
                })
        
        # OOP features
        if 'new' in methods:
            features.append({
                "feature": "blessed_objects",
                "usage_context": "Object construction with bless",
                "frequency": "high",
                "java_approach": "Use standard Java constructors",
                "complexity": "moderate",
                "libraries_needed": []
            })
        
        # Method patterns
        getters = [m for m in methods if m.startswith('get_')]
        setters = [m for m in methods if m.startswith('set_')]
        
        if getters or setters:
            features.append({
                "feature": "accessor_methods",
                "usage_context": f"{len(getters)} getters, {len(setters)} setters",
                "frequency": "high",
                "java_approach": "Standard Java getter/setter methods",
                "complexity": "trivial",
                "libraries_needed": []
            })
        
        return features
    
    def _determine_java_imports(self, imports: List[str], methods: List[str]) -> List[str]:
        """Determine required Java imports."""
        java_imports = ["java.util.*"]
        
        # Based on Perl imports
        for imp in imports:
            if 'DBI' in imp or 'database' in imp.lower():
                java_imports.append("java.sql.*")
            elif 'File' in imp or 'file' in imp.lower():
                java_imports.append("java.io.*")
                java_imports.append("java.nio.file.*")
            elif 'Time' in imp or 'Date' in imp:
                java_imports.append("java.time.*")
        
        # Based on methods
        if any(m.startswith('get_') or m.startswith('set_') for m in methods):
            if "java.util.*" not in java_imports:
                java_imports.append("java.util.*")
        
        return list(set(java_imports))
    
    def _create_robust_fallback_analysis(self, state: AgentState) -> Dict[str, Any]:
        """Create robust fallback analysis when all else fails."""
        file_name = state.file_path.split('/')[-1].split('\\')[-1]
        base_name = file_name.replace('.pm', '').replace('.pl', '')
        
        return {
            "subroutines": [{
                "name": "defaultMethod",
                "parameters": [],
                "parameter_types": [],
                "purpose": f"Generated method for {base_name}",
                "returns": "void",
                "return_description": "No return value",
                "complexity": "low",
                "perl_specifics": [],
                "java_method_signature": "public void defaultMethod()",
                "conversion_notes": ["Fallback method generated"]
            }],
            "global_variables": [],
            "object_model": {
                "is_oop": True,
                "inheritance_chain": [base_name],
                "constructor_pattern": "new",
                "instance_variables": [],
                "java_class_design": f"Simple {base_name} class"
            },
            "main_flow": "Fallback analysis due to processing errors",
            "perl_features": [],
            "imports_needed": ["java.util.*", "java.io.*"],
            "conversion_strategy": {
                "approach": "single_class",
                "design_patterns": [],
                "error_handling": "exceptions"
            },
            "conversion_notes": [
                "Fallback analysis used due to errors",
                "Manual review recommended"
            ],
            "risk_assessment": {
                "complexity_score": 3,
                "conversion_risks": ["fallback_analysis", "incomplete_data"],
                "mitigation_strategies": ["manual_review", "testing"]
            }
        }
    
    def _enhance_analysis_with_ast(self, state: AgentState):
        """Enhance the analysis with additional AST insights."""
        if not state.perl_analysis:
            return
            
        # Add AST-specific insights
        ast_insights = []
        
        total_methods = state.structured_data.get('totalMethods', 0)
        if total_methods > 0:
            ast_insights.append(f"AST Analysis: {total_methods} methods detected")
        
        design_patterns = state.structured_data.get('designPatterns', [])
        if design_patterns:
            ast_insights.append(f"Design Patterns: {', '.join(design_patterns)}")
        
        # Add to conversion notes
        if ast_insights:
            state.perl_analysis.setdefault('conversion_notes', []).extend(ast_insights)
        
        # Add AST validation info
        state.perl_analysis['ast_validation'] = {
            'total_methods_detected': total_methods,
            'packages_analyzed': len(state.structured_data.get('packages', [])),
            'design_patterns_found': len(design_patterns),
            'analysis_mode': 'AST_ONLY'
        }
    
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