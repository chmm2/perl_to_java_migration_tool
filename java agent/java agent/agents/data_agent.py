# data_agent.py
"""
Enhanced AST-only data agent with comprehensive script pattern detection.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from neo4j import GraphDatabase
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Settings
from state import AgentState


class Neo4jHandler:
    """Enhanced Neo4j handler with comprehensive AST analysis and script pattern detection."""
    
    def __init__(self, settings: Settings):
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri, 
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        try:
            self.driver.verify_connectivity()
            self._discover_schema()
        except Exception as e:
            logging.error(f"Failed to connect to Neo4j: {e}")
            raise

    def _discover_schema(self):
        """Discover the actual database schema"""
        with self.driver.session() as session:
            try:
                labels_result = session.run("CALL db.labels() YIELD label RETURN label")
                self.node_labels = [record['label'] for record in labels_result]
                
                rel_result = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
                self.relationship_types = [record['relationshipType'] for record in rel_result]
                
                logging.info(f"Available node labels: {self.node_labels}")
                logging.info(f"Available relationship types: {self.relationship_types}")
            except Exception as e:
                logging.warning(f"Schema discovery failed: {e}")
                self.node_labels = []
                self.relationship_types = []

    def get_comprehensive_file_data(self, file_path: str) -> Dict[str, Any]:
        """Get comprehensive file data with advanced script pattern detection."""
        try:
            return self._get_enhanced_file_data(file_path)
        except Exception as e:
            logging.error(f"Enhanced data retrieval failed for {file_path}: {e}")
            return self._create_intelligent_fallback(file_path)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=8))
    def _get_enhanced_file_data(self, file_path: str) -> Dict[str, Any]:
        """Enhanced data retrieval with comprehensive AST analysis."""
        with self.driver.session() as session:
            # Comprehensive query to get all possible AST information
            query = """
            MATCH (f:FILE)
            WHERE f.source_file = $file_path OR f.name = $file_path
            
            // Get all nodes connected to this file
            OPTIONAL MATCH (f)-[r1]-(n1)
            OPTIONAL MATCH (f)-[r2]-(n2)-[r3]-(n3)
            OPTIONAL MATCH (f)-[r4]-(n4)-[r5]-(n5)-[r6]-(n6)
            
            // Get packages and their details
            OPTIONAL MATCH (f)-[:CONTAINS_PACKAGE]->(p:PACKAGE)
            OPTIONAL MATCH (p)-[:HAS_METHOD]->(m:METHOD)
            OPTIONAL MATCH (m)-[:HAS_PARAMETER]->(param)
            OPTIONAL MATCH (m)-[:ACCESSES_FIELD]->(field)
            OPTIONAL MATCH (m)-[:CALLS]->(called_method)
            
            // Get use statements and imports
            OPTIONAL MATCH (f)-[:USES_MODULE]->(u:USE_STATEMENT)
            
            // Get script executions and control structures
            OPTIONAL MATCH (p)-[:HAS_SCRIPT]->(s:SCRIPT_EXECUTION)
            OPTIONAL MATCH (f)-[:CONTAINS]->(stmt)
            
            // Get any variables or constants
            OPTIONAL MATCH (f)-[:DECLARES]->(var)
            
            RETURN f.source_file AS filePath,
                   f.name AS fileName,
                   f.file_type AS fileType,
                   
                   // Package information
                   collect(DISTINCT {
                       name: p.name,
                       type: labels(p)[0]
                   }) AS packages,
                   
                   // Method information
                   collect(DISTINCT {
                       name: m.name,
                       full_name: m.full_name,
                       body: m.body,
                       parameters: m.parameters,
                       return_type: m.return_type,
                       start_line: m.start_line,
                       end_line: m.end_line,
                       id: m.id
                   }) AS methods,
                   
                   // Import information
                   collect(DISTINCT {
                       module: u.module,
                       name: u.name,
                       type: u.type
                   }) AS imports,
                   
                   // Script execution patterns
                   collect(DISTINCT {
                       name: s.name,
                       body: s.body,
                       type: labels(s)[0],
                       id: s.id
                   }) AS scripts,
                   
                   // All connected nodes for pattern analysis
                   collect(DISTINCT {
                       labels: labels(n1),
                       properties: properties(n1),
                       relationship: type(r1)
                   }) AS allNodes,
                   
                   // Statement and control structure information
                   collect(DISTINCT {
                       labels: labels(stmt),
                       properties: properties(stmt)
                   }) AS statements,
                   
                   // Variable declarations
                   collect(DISTINCT {
                       labels: labels(var),
                       properties: properties(var)
                   }) AS variables
            """
            
            result = session.run(query, file_path=file_path).single()
            if not result:
                raise ValueError(f"No data found for file: {file_path}")
            
            # Convert result to comprehensive data structure
            raw_data = dict(result)
            enhanced_data = self._analyze_and_enhance_data(raw_data, file_path)
            return enhanced_data

    def _analyze_and_enhance_data(self, raw_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Analyze raw AST data and enhance with intelligent pattern detection."""
        
        # Extract and clean basic information
        file_info = {
            'filePath': self._safe_get(raw_data, 'filePath', file_path),
            'fileName': self._safe_get(raw_data, 'fileName', file_path.split('/')[-1]),
            'fileType': self._safe_get(raw_data, 'fileType', 'perl')
        }
        
        # Process packages
        packages_raw = self._safe_get(raw_data, 'packages', [])
        packages = self._process_packages(packages_raw)
        
        # Process methods
        methods_raw = self._safe_get(raw_data, 'methods', [])
        methods = self._process_methods(methods_raw)
        
        # Process imports
        imports_raw = self._safe_get(raw_data, 'imports', [])
        imports = self._process_imports(imports_raw)
        
        # Process scripts and statements
        scripts_raw = self._safe_get(raw_data, 'scripts', [])
        statements_raw = self._safe_get(raw_data, 'statements', [])
        all_nodes_raw = self._safe_get(raw_data, 'allNodes', [])
        
        # Detect application patterns
        app_patterns = self._detect_application_patterns(
            file_info, packages, methods, imports, scripts_raw, statements_raw, all_nodes_raw
        )

        # Determine the file's fundamental archetype.
        file_archetype = 'module'  # Default to module
        if file_info.get('fileName', '').endswith('.pl') and len(methods) < 2:
            # A .pl file with few or no subroutines is a script.
            file_archetype = 'script'

        # Build enhanced structure
        enhanced_data = {
            **file_info,
            'file_archetype': file_archetype,  # Add the new field to the payload
            'packages': self._build_package_structure(packages, methods, app_patterns),
            'imports': imports,
            'importModules': [imp.get('module', '') for imp in imports if imp.get('module')],
            'totalMethods': len(methods),
            'applicationPatterns': app_patterns,
            'designPatterns': self._infer_design_patterns(methods, app_patterns),
            'javaImports': self._determine_java_imports(imports, app_patterns),
            'synthesizedContent': self._create_enhanced_content(
                file_info, packages, methods, imports, app_patterns
            ),
            'conversionStrategy': self._determine_conversion_strategy(file_info, app_patterns, methods),
            'qualityMetrics': self._calculate_quality_metrics(packages, methods, imports, app_patterns)
        }
        
        return enhanced_data

    def _detect_application_patterns(self, file_info: Dict, packages: List, methods: List, 
                                   imports: List, scripts: List, statements: List, 
                                   all_nodes: List) -> Dict[str, Any]:
        """Detect high-level application patterns from AST data."""
        
        patterns = {
            'isScript': file_info.get('fileName', '').endswith('.pl'),
            'isModule': file_info.get('fileName', '').endswith('.pm'),
            'hasMainLoop': False,
            'hasUserInput': False,
            'hasInteractiveMenu': False,
            'hasFileOperations': False,
            'hasDatabaseOperations': False,
            'hasNetworking': False,
            'applicationType': 'unknown',
            'controlStructures': [],
            'ioPatterns': [],
            'businessDomain': 'general'
        }
        
        # Analyze imports for patterns
        import_modules = [imp.get('module', '').lower() for imp in imports if imp.get('module')]
        
        # Detect interactive patterns
        if any('stdin' in str(node.get('properties', {})).lower() for node in all_nodes):
            patterns['hasUserInput'] = True
        
        # Detect loop patterns
        loop_indicators = ['while', 'for', 'loop', 'stdin', 'input']
        if any(indicator in str(all_nodes).lower() for indicator in loop_indicators):
            patterns['hasMainLoop'] = True
        
        # Detect menu patterns
        menu_indicators = ['menu', 'choice', 'option', 'select']
        if any(indicator in str(all_nodes).lower() for indicator in menu_indicators):
            patterns['hasInteractiveMenu'] = True
        
        # Detect I/O patterns
        if any(io_mod in import_modules for io_mod in ['file', 'io', 'path']):
            patterns['hasFileOperations'] = True
            patterns['ioPatterns'].append('file_operations')
        
        # Detect database patterns
        if any(db_mod in import_modules for db_mod in ['dbi', 'database', 'sql']):
            patterns['hasDatabaseOperations'] = True
            patterns['ioPatterns'].append('database_operations')
        
        # Detect business domain
        domain_keywords = {
            'employee': ['employee', 'manager', 'staff', 'hr'],
            'financial': ['account', 'payment', 'invoice', 'finance'],
            'inventory': ['product', 'stock', 'inventory', 'warehouse'],
            'customer': ['customer', 'client', 'contact', 'crm'],
            'system': ['system', 'admin', 'config', 'util']
        }
        
        all_text = ' '.join([
            str(import_modules),
            str([pkg.get('name', '') for pkg in packages]),
            str([method.get('name', '') for method in methods])
        ]).lower()
        
        for domain, keywords in domain_keywords.items():
            if any(keyword in all_text for keyword in keywords):
                patterns['businessDomain'] = domain
                break
        
        # Determine application type
        if patterns['isScript']:
            if patterns['hasInteractiveMenu'] and patterns['hasUserInput']:
                patterns['applicationType'] = 'interactive_cli'
            elif patterns['hasMainLoop']:
                patterns['applicationType'] = 'service_script'
            elif patterns['hasFileOperations']:
                patterns['applicationType'] = 'batch_processor'
            else:
                patterns['applicationType'] = 'simple_script'
        else:
            if len(methods) > 5:
                patterns['applicationType'] = 'complex_module'
            elif any(method.get('name') == 'new' for method in methods):
                patterns['applicationType'] = 'object_class'
            else:
                patterns['applicationType'] = 'utility_module'
        
        return patterns

    def _determine_conversion_strategy(self, file_info: Dict, app_patterns: Dict, methods: List) -> Dict[str, Any]:
        """Determine the optimal conversion strategy based on detected patterns."""
        
        strategy = {
            'primaryApproach': 'single_class',
            'codeGenerationStyle': 'standard',
            'requiredComponents': [],
            'complexity': 'medium'
        }
        
        app_type = app_patterns.get('applicationType', 'unknown')
        
        if app_type == 'interactive_cli':
            strategy.update({
                'primaryApproach': 'cli_application',
                'codeGenerationStyle': 'interactive',
                'requiredComponents': ['scanner', 'menu_system', 'user_input_handler', 'main_loop'],
                'complexity': 'high'
            })
        elif app_type == 'service_script':
            strategy.update({
                'primaryApproach': 'service_application',
                'codeGenerationStyle': 'daemon',
                'requiredComponents': ['main_loop', 'signal_handlers', 'logging'],
                'complexity': 'high'
            })
        elif app_type == 'batch_processor':
            strategy.update({
                'primaryApproach': 'batch_application',
                'codeGenerationStyle': 'procedural',
                'requiredComponents': ['file_processor', 'error_handler'],
                'complexity': 'medium'
            })
        elif app_type == 'object_class':
            strategy.update({
                'primaryApproach': 'oop_class',
                'codeGenerationStyle': 'object_oriented',
                'requiredComponents': ['constructor', 'getters', 'setters', 'business_methods'],
                'complexity': 'medium'
            })
        
        # Add domain-specific components
        domain = app_patterns.get('businessDomain', 'general')
        if domain == 'employee':
            strategy['requiredComponents'].extend(['employee_operations', 'data_validation'])
        elif domain == 'financial':
            strategy['requiredComponents'].extend(['calculation_methods', 'data_validation', 'audit_trail'])
        
        return strategy

    def _process_packages(self, packages_raw: List) -> List[Dict]:
        """Process and clean package information."""
        packages = []
        for pkg in packages_raw:
            if isinstance(pkg, dict) and pkg.get('name'):
                packages.append({
                    'name': pkg['name'],
                    'type': pkg.get('type', 'PACKAGE')
                })
        return packages

    def _process_methods(self, methods_raw: List) -> List[Dict]:
        """Process and clean method information."""
        methods = []
        for method in methods_raw:
            if isinstance(method, dict) and method.get('name'):
                methods.append({
                    'name': method['name'],
                    'fullName': method.get('full_name', method['name']),
                    'body': method.get('body', ''),
                    'parameters': method.get('parameters', '[]'),
                    'returnType': method.get('return_type', 'void'),
                    'startLine': method.get('start_line', 0),
                    'endLine': method.get('end_line', 0),
                    'id': method.get('id', '')
                })
        return methods

    def _process_imports(self, imports_raw: List) -> List[Dict]:
        """Process and clean import information."""
        imports = []
        for imp in imports_raw:
            if isinstance(imp, dict) and imp.get('module'):
                imports.append({
                    'module': imp['module'],
                    'name': imp.get('name', imp['module']),
                    'type': imp.get('type', 'USE_STATEMENT')
                })
        return imports

    def _build_package_structure(self, packages: List, methods: List, app_patterns: Dict) -> List[Dict]:
        """Build enhanced package structure with intelligent organization."""
        
        if not packages and not methods:
            # Create default structure for scripts
            file_name = app_patterns.get('fileName', 'Unknown')
            base_name = file_name.replace('.pl', '').replace('.pm', '')
            
            return [{
                'packageName': base_name.capitalize(),
                'isOOP': False,
                'methods': [],
                'scripts': [],
                'estimatedFields': [],
                'classType': app_patterns.get('applicationType', 'utility'),
                'applicationPatterns': app_patterns
            }]
        
        package_structures = []
        
        for pkg in packages:
            # Find methods belonging to this package
            pkg_methods = [method for method in methods if self._method_belongs_to_package(method, pkg)]
            
            # Analyze class characteristics
            class_analysis = self._analyze_class_characteristics(pkg, pkg_methods, app_patterns)
            
            package_structure = {
                'packageName': pkg['name'],
                'isOOP': class_analysis['isOOP'],
                'methods': pkg_methods,
                'scripts': [],
                'estimatedFields': class_analysis['estimatedFields'],
                'classType': class_analysis['classType'],
                'applicationPatterns': app_patterns,
                'classCharacteristics': class_analysis
            }
            
            package_structures.append(package_structure)
        
        # If no packages but have methods, create default package
        if not package_structures and methods:
            default_analysis = self._analyze_class_characteristics({}, methods, app_patterns)
            
            package_structures.append({
                'packageName': 'DefaultPackage',
                'isOOP': default_analysis['isOOP'],
                'methods': methods,
                'scripts': [],
                'estimatedFields': default_analysis['estimatedFields'],
                'classType': default_analysis['classType'],
                'applicationPatterns': app_patterns,
                'classCharacteristics': default_analysis
            })
        
        return package_structures

    def _analyze_class_characteristics(self, package: Dict, methods: List, app_patterns: Dict) -> Dict:
        """Analyze characteristics of a class based on its methods and patterns."""
        
        method_names = [method.get('name', '') for method in methods]
        
        characteristics = {
            'isOOP': False,
            'hasConstructor': False,
            'hasGetters': False,
            'hasSetters': False,
            'hasBusinessMethods': False,
            'estimatedFields': [],
            'classType': 'utility',
            'complexity': 'low'
        }
        
        # Analyze methods
        getters = [name for name in method_names if name.startswith('get_')]
        setters = [name for name in method_names if name.startswith('set_')]
        constructors = [name for name in method_names if name in ['new', 'init']]
        
        characteristics['hasConstructor'] = len(constructors) > 0
        characteristics['hasGetters'] = len(getters) > 0
        characteristics['hasSetters'] = len(setters) > 0
        characteristics['hasBusinessMethods'] = len([n for n in method_names if not n.startswith(('get_', 'set_', '_'))]) > 0
        
        # Determine if OOP
        characteristics['isOOP'] = (
            characteristics['hasConstructor'] or 
            characteristics['hasGetters'] or 
            characteristics['hasSetters'] or
            len(methods) > 3
        )
        
        # Estimate fields from getters/setters
        estimated_fields = set()
        for getter in getters:
            field_name = getter[4:]  # Remove 'get_'
            if field_name:
                estimated_fields.add(field_name)
        
        for setter in setters:
            field_name = setter[4:]  # Remove 'set_'
            if field_name:
                estimated_fields.add(field_name)
        
        characteristics['estimatedFields'] = [
            {'name': field, 'type': 'String', 'source': 'getter_setter_analysis'}
            for field in estimated_fields
        ]
        
        # Determine class type
        if app_patterns.get('applicationType') == 'interactive_cli':
            characteristics['classType'] = 'cli_application'
        elif 'manager' in package.get('name', '').lower():
            characteristics['classType'] = 'manager'
        elif characteristics['hasConstructor'] and characteristics['hasGetters']:
            characteristics['classType'] = 'entity'
        elif len(methods) > 5:
            characteristics['classType'] = 'service'
        else:
            characteristics['classType'] = 'utility'
        
        # Determine complexity
        if len(methods) > 10:
            characteristics['complexity'] = 'high'
        elif len(methods) > 5:
            characteristics['complexity'] = 'medium'
        else:
            characteristics['complexity'] = 'low'
        
        return characteristics

    def _method_belongs_to_package(self, method: Dict, package: Dict) -> bool:
        """Determine if a method belongs to a specific package."""
        # This would be enhanced based on AST relationship data
        return True  # For now, assume all methods belong to all packages

    def _infer_design_patterns(self, methods: List, app_patterns: Dict) -> List[str]:
        """Infer design patterns from methods and application patterns."""
        patterns = []
        
        method_names = [method.get('name', '') for method in methods]
        
        # Factory pattern
        if 'new' in method_names or any('create' in name.lower() for name in method_names):
            patterns.append('Factory')
        
        # Builder pattern
        if len([name for name in method_names if name.startswith('set_')]) > 2:
            patterns.append('Builder')
        
        # Manager pattern
        if any('manage' in name.lower() or 'add' in name.lower() or 'remove' in name.lower() for name in method_names):
            patterns.append('Manager')
        
        # CLI pattern
        if app_patterns.get('applicationType') == 'interactive_cli':
            patterns.append('Command')
            patterns.append('State')
        
        return patterns

    def _determine_java_imports(self, imports: List, app_patterns: Dict) -> List[str]:
        """Determine required Java imports based on Perl imports and patterns."""
        java_imports = set(['java.util.*'])
        
        # Based on Perl imports
        for imp in imports:
            module = imp.get('module', '').lower()
            if 'dbi' in module or 'database' in module:
                java_imports.update(['java.sql.*', 'javax.sql.*'])
            elif 'file' in module or 'io' in module:
                java_imports.update(['java.io.*', 'java.nio.file.*'])
            elif 'time' in module or 'date' in module:
                java_imports.add('java.time.*')
            elif 'json' in module:
                java_imports.add('com.fasterxml.jackson.core.*')
        
        # Based on application patterns
        if app_patterns.get('hasUserInput'):
            java_imports.add('java.util.Scanner')
        
        if app_patterns.get('applicationType') == 'interactive_cli':
            java_imports.update(['java.util.Scanner', 'java.io.Console'])
        
        if app_patterns.get('hasFileOperations'):
            java_imports.update(['java.io.*', 'java.nio.file.*'])
        
        return list(java_imports)

    def _create_enhanced_content(self, file_info: Dict, packages: List, methods: List, 
                               imports: List, app_patterns: Dict) -> str:
        """Create enhanced synthetic content based on comprehensive analysis."""
        
        lines = []
        
        # Add file header
        lines.append(f"# Enhanced content for {file_info.get('fileName', 'unknown')}")
        lines.append(f"# Application type: {app_patterns.get('applicationType', 'unknown')}")
        lines.append(f"# Business domain: {app_patterns.get('businessDomain', 'general')}")
        lines.append("")
        
        # Add imports
        for imp in imports:
            module = imp.get('module', '')
            if module:
                lines.append(f"use {module};")
        
        if imports:
            lines.append("")
        
        # Add packages and methods
        for pkg in packages:
            pkg_name = pkg.get('name', pkg.get('packageName', ''))
            if pkg_name:
                lines.append(f"package {pkg_name};")
                lines.append("")
                
                pkg_methods = pkg.get('methods', methods)
                for method in pkg_methods:
                    method_name = method.get('name', '')
                    if method_name:
                        lines.append(f"sub {method_name} {{")
                        lines.append("    # Method implementation")
                        lines.append("}")
                        lines.append("")
        
        # Add application pattern indicators
        if app_patterns.get('hasMainLoop'):
            lines.append("# Main application loop detected")
        
        if app_patterns.get('hasUserInput'):
            lines.append("# User input handling detected")
        
        if app_patterns.get('hasInteractiveMenu'):
            lines.append("# Interactive menu system detected")
        
        return '\n'.join(lines) if lines else '# No content available'

    def _calculate_quality_metrics(self, packages: List, methods: List, imports: List, app_patterns: Dict) -> Dict:
        """Calculate quality metrics for the detected code structure."""
        
        return {
            'complexity_score': min(len(methods), 10),
            'package_count': len(packages),
            'method_count': len(methods),
            'import_count': len(imports),
            'has_main_logic': app_patterns.get('hasMainLoop', False),
            'application_completeness': self._assess_completeness(app_patterns, methods),
            'conversion_confidence': self._assess_conversion_confidence(packages, methods, imports)
        }

    def _assess_completeness(self, app_patterns: Dict, methods: List) -> float:
        """Assess how complete the application appears to be."""
        score = 0.5  # Base score
        
        if app_patterns.get('applicationType') != 'unknown':
            score += 0.2
        
        if len(methods) > 0:
            score += 0.2
        
        if app_patterns.get('hasMainLoop'):
            score += 0.1
        
        return min(score, 1.0)

    def _assess_conversion_confidence(self, packages: List, methods: List, imports: List) -> float:
        """Assess confidence in conversion quality."""
        score = 0.3  # Base score
        
        if len(packages) > 0:
            score += 0.2
        
        if len(methods) > 0:
            score += 0.3
        
        if len(imports) > 0:
            score += 0.2
        
        return min(score, 1.0)

    def _safe_get(self, data: Dict, key: str, default=None):
        """Safely get value from dictionary with None filtering."""
        try:
            value = data.get(key, default)
            if value is None:
                return default
            if isinstance(value, list):
                return [item for item in value if item is not None]
            return value
        except (KeyError, TypeError, AttributeError):
            return default

    def _create_intelligent_fallback(self, file_path: str) -> Dict[str, Any]:
        """Create intelligent fallback data when AST queries fail."""
        
        file_name = file_path.split('/')[-1].split('\\')[-1]
        base_name = file_name.replace('.pm', '').replace('.pl', '')
        is_script = file_name.endswith('.pl')
        
        # Infer patterns from filename and type
        app_patterns = {
            'isScript': is_script,
            'isModule': not is_script,
            'applicationType': 'interactive_cli' if 'main' in base_name.lower() and is_script else 'utility_module',
            'businessDomain': 'employee' if 'employee' in base_name.lower() else 'general',
            'hasUserInput': 'main' in base_name.lower() and is_script,
            'hasMainLoop': 'main' in base_name.lower() and is_script,
            'hasInteractiveMenu': 'main' in base_name.lower() and is_script
        }
        
        return {
            'filePath': file_path,
            'fileName': file_name,
            'fileType': 'perl',
            'packages': [{
                'packageName': base_name.capitalize(),
                'isOOP': not is_script,
                'methods': [{'name': 'defaultMethod'}] if not is_script else [],
                'estimatedFields': [],
                'classType': app_patterns['applicationType'],
                'applicationPatterns': app_patterns
            }],
            'imports': [],
            'importModules': [],
            'totalMethods': 0 if is_script else 1,
            'applicationPatterns': app_patterns,
            'designPatterns': [],
            'javaImports': ['java.util.*', 'java.util.Scanner'] if is_script else ['java.util.*'],
            'synthesizedContent': f'# Fallback content for {base_name}',
            'conversionStrategy': self._determine_conversion_strategy({'fileName': file_name}, app_patterns, []),
            'qualityMetrics': {
                'complexity_score': 1,
                'conversion_confidence': 0.3,
                'application_completeness': 0.3
            }
        }

    def get_available_files(self) -> List[str]:
        """Get all available files from Neo4j."""
        try:
            with self.driver.session() as session:
                query = """
                MATCH (f:FILE) 
                WHERE f.source_file IS NOT NULL 
                RETURN DISTINCT f.source_file AS file_path 
                ORDER BY file_path
                """
                result = session.run(query)
                files = [record['file_path'] for record in result if record['file_path']]
                logging.info(f"Found {len(files)} files in database")
                return files
        except Exception as e:
            logging.error(f"Failed to get available files: {e}")
            return []

    def close(self):
        """Close the database connection."""
        try:
            self.driver.close()
        except Exception as e:
            logging.error(f"Error closing Neo4j connection: {e}")


class DataRetrievalAgent:
    """Enhanced data retrieval agent with comprehensive pattern detection."""
    
    def __init__(self, neo4j_handler: Neo4jHandler):
        self.neo4j_handler = neo4j_handler

    def __call__(self, state: AgentState) -> AgentState:
        """
        Enhanced Data Retrieval: Comprehensive AST analysis with pattern detection.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with enhanced structured data and application patterns
        """
        try:
            # Get comprehensive data with pattern detection
            state.structured_data = self.neo4j_handler.get_comprehensive_file_data(state.file_path)
            
            # Use enhanced synthetic content
            state.perl_content = state.structured_data.get('synthesizedContent', '')
            
            # Log comprehensive analysis results
            app_patterns = state.structured_data.get('applicationPatterns', {})
            conversion_strategy = state.structured_data.get('conversionStrategy', {})
            
            logging.info(f"✅ Enhanced AST analysis for: {state.file_path}")
            logging.info(f"📱 Application Type: {app_patterns.get('applicationType', 'unknown')}")
            logging.info(f"🏢 Business Domain: {app_patterns.get('businessDomain', 'general')}")
            logging.info(f"🔄 Conversion Strategy: {conversion_strategy.get('primaryApproach', 'unknown')}")
            logging.info(f"📦 Packages: {len(state.structured_data.get('packages', []))}")
            logging.info(f"🔧 Methods: {state.structured_data.get('totalMethods', 0)}")
            logging.info(f"📥 Imports: {len(state.structured_data.get('imports', []))}")
            
            # Add pattern insights to translation notes
            if app_patterns.get('hasUserInput'):
                state.translation_notes.append("Detected user input handling patterns")
            if app_patterns.get('hasInteractiveMenu'):
                state.translation_notes.append("Detected interactive menu system")
            if app_patterns.get('hasMainLoop'):
                state.translation_notes.append("Detected main execution loop")
            
        except Exception as e:
            error_msg = f"Enhanced data retrieval failed for {state.file_path}: {e}"
            state.errors.append(error_msg)
            logging.error(error_msg)
            
            # Create emergency fallback with basic pattern detection
            state.structured_data = self.neo4j_handler._create_intelligent_fallback(state.file_path)
            state.perl_content = state.structured_data.get('synthesizedContent', '# Emergency fallback')
            
        return state