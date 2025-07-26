#!/usr/bin/env python3

"""
Fixed Neo4j writer with improved storage for agent compatibility.
"""

import os
import json
import logging
from neo4j import GraphDatabase
from typing import Dict, Any, List
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Neo4jWriter:
    def __init__(self):
        """Initialize Neo4j connection with consistent password."""
        self.uri = os.getenv('NEO4J_URI', 'neo4j://127.0.0.1:7687')
        self.user = os.getenv('NEO4J_USER', 'neo4j')
        # Use consistent password - change this to match your actual password
        self.password = os.getenv('NEO4J_PASSWORD', 'chris098')  # Changed from 00900p009
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        
        # Test connection
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Connected to Neo4j successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
        logger.info("Neo4j connection closed")

    def clear_database(self):
        """Clear all data."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("Database cleared")

    def _clean_value(self, value: Any) -> Any:
        """Clean values for Neo4j storage with better handling."""
        if isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            # Don't truncate method bodies too aggressively
            return value[:5000] if len(value) > 5000 else value
        elif isinstance(value, list):
            # Store as JSON but don't truncate unless very large
            json_str = json.dumps(value)
            return json_str[:2000] if len(json_str) > 2000 else json_str
        elif isinstance(value, dict):
            json_str = json.dumps(value)
            return json_str[:2000] if len(json_str) > 2000 else json_str
        else:
            return str(value)[:2000]

    def _extract_filename(self, file_path: str) -> str:
        """Extract just the filename without extension from a file path."""
        base_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        return name_without_ext

    def _normalize_id(self, text: str) -> str:
        """Normalize text for consistent ID generation."""
        return text.replace('/', '_').replace('.', '_').replace(' ', '_').replace('\\', '_').replace('::', '_')

    def _transform_perl_ast(self, ast_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform Perl AST into Neo4j-compatible nodes and relationships."""
        nodes = []
        relationships = []

        # Process each file
        for file_data in ast_data.get('files', []):
            file_path = file_data['source_file']
            file_id = f"file_{self._normalize_id(file_path)}"
            
            # Create file node
            file_name = self._extract_filename(file_path)
            file_properties = {
                'source_file': file_path,
                'file_type': file_data.get('type', 'PerlFile'),
                'name': file_name
            }
            
            # Add global scope information
            if file_data.get('global_scope'):
                file_properties['has_global_scope'] = True
                if file_data['global_scope'].get('body'):
                    file_properties['global_scope_body'] = self._clean_value(file_data['global_scope']['body'])
            else:
                file_properties['has_global_scope'] = False
            
            nodes.append({
                'id': file_id,
                'type': 'FILE',
                'name': file_name,
                'properties': file_properties
            })

            # Process file-level use statements
            for use_stmt in file_data.get('use_statements', []):
                use_id = f"use_{self._normalize_id(use_stmt['module'])}_{file_id}"
                
                nodes.append({
                    'id': use_id,
                    'type': 'USE_STATEMENT',
                    'name': use_stmt['module'],
                    'properties': {
                        'module': use_stmt['module'],
                        'source_file': use_stmt.get('source_file', file_path),
                        'type': use_stmt.get('type', 'UseStatement')
                    }
                })

                relationships.append({
                    'from_id': file_id,
                    'to_id': use_id,
                    'type': 'USES_MODULE',
                    'properties': {}
                })

            # Process packages
            for package in file_data.get('packages', []):
                package_id = f"package_{file_id}_{self._normalize_id(package['name'])}"
                
                # Create package node with comprehensive properties
                package_properties = {
                    'name': package['name'],
                    'source_file': package['source_file'],
                    'type': package.get('type', 'PackageDeclaration')
                }
                
                # Add method information
                if package.get('methods'):
                    method_names = [method.get('name', '') for method in package['methods']]
                    package_properties['method_names'] = json.dumps(method_names)
                    package_properties['method_count'] = len(package['methods'])
                else:
                    package_properties['method_count'] = 0
                
                # Add script execution info
                if package.get('script_execution'):
                    package_properties['has_script_execution'] = True
                    if package['script_execution'].get('body'):
                        package_properties['script_body'] = self._clean_value(package['script_execution']['body'])
                else:
                    package_properties['has_script_execution'] = False

                nodes.append({
                    'id': package_id,
                    'type': 'PACKAGE',
                    'name': package['name'],
                    'properties': package_properties
                })

                # Create file->package relationship
                relationships.append({
                    'from_id': file_id,
                    'to_id': package_id,
                    'type': 'CONTAINS_PACKAGE',
                    'properties': {}
                })

                # Process package-level use statements
                for use_stmt in package.get('use_statements', []):
                    use_id = f"use_{self._normalize_id(use_stmt['module'])}_{package_id}"
                    
                    nodes.append({
                        'id': use_id,
                        'type': 'USE_STATEMENT',
                        'name': use_stmt['module'],
                        'properties': {
                            'module': use_stmt['module'],
                            'source_file': use_stmt.get('source_file', package['source_file']),
                            'type': use_stmt.get('type', 'UseStatement')
                        }
                    })

                    relationships.append({
                        'from_id': package_id,
                        'to_id': use_id,
                        'type': 'USES_MODULE',
                        'properties': {}
                    })

                # Process methods with full body preservation
                for method in package.get('methods', []):
                    method_id = f"method_{package_id}_{self._normalize_id(method['name'])}"
                    
                    method_properties = {
                        'name': method['name'],
                        'full_name': method.get('full_name', f"{package['name']}::{method['name']}"),
                        'package': method.get('package', package['name']),
                        'type': method.get('type', 'SubDefinition'),
                        'source_file': package['source_file']
                    }
                    
                    # Store parameters properly
                    if method.get('parameters'):
                        if isinstance(method['parameters'], list):
                            method_properties['parameters'] = json.dumps(method['parameters'])
                            method_properties['parameter_count'] = len(method['parameters'])
                        else:
                            method_properties['parameters'] = str(method['parameters'])
                            method_properties['parameter_count'] = 0
                    else:
                        method_properties['parameters'] = '[]'
                        method_properties['parameter_count'] = 0
                    
                    # Store method body without aggressive truncation
                    if method.get('body'):
                        method_properties['body'] = self._clean_value(method['body'])
                        method_properties['body_length'] = len(method['body'])
                        method_properties['has_body'] = True
                    else:
                        method_properties['body'] = ''
                        method_properties['body_length'] = 0
                        method_properties['has_body'] = False

                    nodes.append({
                        'id': method_id,
                        'type': 'METHOD',
                        'name': method['name'],
                        'properties': method_properties
                    })

                    relationships.append({
                        'from_id': package_id,
                        'to_id': method_id,
                        'type': 'HAS_METHOD',
                        'properties': {}
                    })

                # Process script execution as separate node
                if package.get('script_execution'):
                    script_data = package['script_execution']
                    script_id = f"script_{package_id}"
                    
                    script_properties = {
                        'type': script_data.get('type', 'ScriptExecution'),
                        'source_file': script_data.get('source_file', package['source_file']),
                        'name': f"script_{package['name']}"
                    }
                    
                    if script_data.get('body'):
                        script_properties['body'] = self._clean_value(script_data['body'])
                        script_properties['body_length'] = len(script_data['body'])
                    else:
                        script_properties['body'] = ''
                        script_properties['body_length'] = 0
                    
                    nodes.append({
                        'id': script_id,
                        'type': 'SCRIPT_EXECUTION',
                        'name': f"script_{package['name']}",
                        'properties': script_properties
                    })

                    relationships.append({
                        'from_id': package_id,
                        'to_id': script_id,
                        'type': 'HAS_SCRIPT',
                        'properties': {}
                    })

        # Process cross-file calls
        for call in ast_data.get('cross_file_calls', []):
            caller_method_id = self._generate_method_caller_id(call)
            target_method_id = self._generate_method_target_id(call)
            
            relationships.append({
                'from_id': caller_method_id,
                'to_id': target_method_id,
                'type': 'CALLS_METHOD',
                'properties': {
                    'call_type': call.get('call_type', 'unknown'),
                    'call_pattern': call.get('call_pattern', ''),
                    'caller_file': call.get('caller_file', ''),
                    'target_file': call.get('target_file', ''),
                    'caller_package': call.get('caller_package', ''),
                    'target_package': call.get('target_package', ''),
                    'is_cross_file': True
                }
            })

        # Aggregate relationships
        aggregated_relationships = self.aggregate_relationships(relationships)

        return {
            'nodes': nodes,
            'relationships': aggregated_relationships
        }

    def _generate_method_caller_id(self, call):
        """Generate consistent method ID for the calling method."""
        caller_file = self._normalize_id(call.get('caller_file', ''))
        caller_package = self._normalize_id(call.get('caller_package', ''))
        
        if call.get('caller_method'):
            caller_method = self._normalize_id(call.get('caller_method', '').split('::')[-1])
            package_id = f"package_file_{caller_file}_{caller_package}"
            return f"method_{package_id}_{caller_method}"
        else:
            package_id = f"package_file_{caller_file}_{caller_package}"
            return f"script_{package_id}"

    def _generate_method_target_id(self, call):
        """Generate consistent method ID for the target method."""
        target_file = self._normalize_id(call.get('target_file', ''))
        target_package = self._normalize_id(call.get('target_package', ''))
        target_method = self._normalize_id(call.get('target_method', ''))
        
        package_id = f"package_file_{target_file}_{target_package}"
        return f"method_{package_id}_{target_method}"

    def aggregate_relationships(self, relationships):
        """Aggregate relationships to ensure only one relationship per unique node pair."""
        aggregated = defaultdict(lambda: {
            'count': 0, 
            'properties': {}, 
            'call_patterns': set(),
            'call_types': set()
        })
        
        for rel in relationships:
            key = (rel['from_id'], rel['to_id'], rel['type'])
            aggregated[key]['count'] += 1
            
            if not aggregated[key]['properties']:
                aggregated[key]['properties'] = rel.get('properties', {}).copy()
            
            props = rel.get('properties', {})
            if 'call_pattern' in props:
                aggregated[key]['call_patterns'].add(props['call_pattern'])
            if 'call_type' in props:
                aggregated[key]['call_types'].add(props['call_type'])
        
        result = []
        for (from_id, to_id, rel_type), data in aggregated.items():
            props = data['properties'].copy()
            props['call_count'] = data['count']
            
            if data['call_patterns']:
                props['call_patterns'] = json.dumps(list(data['call_patterns']))
            if data['call_types']:
                props['call_types'] = json.dumps(list(data['call_types']))
                props['call_type'] = list(data['call_types'])[0]
            
            result.append({
                'from_id': from_id,
                'to_id': to_id,
                'type': rel_type,
                'properties': props
            })
        
        logger.info(f"Aggregated {len(relationships)} relationships into {len(result)} unique relationships")
        return result

    def _create_node_batch(self, session, nodes: List[Dict[str, Any]]):
        """Create nodes in batch for better performance."""
        nodes_by_type = {}
        for node in nodes:
            node_type = node.get('type', 'UNKNOWN')
            if node_type not in nodes_by_type:
                nodes_by_type[node_type] = []
            nodes_by_type[node_type].append(node)

        for node_type, type_nodes in nodes_by_type.items():
            batch_data = []
            for node in type_nodes:
                props = node.get('properties', {})
                clean_props = {k: self._clean_value(v) for k, v in props.items()}
                clean_props.update({
                    'id': node.get('id', ''),
                    'name': node.get('name', 'unnamed')
                })
                batch_data.append(clean_props)

            query = f"""
            UNWIND $batch as props
            CREATE (n:{node_type})
            SET n = props
            """
            session.run(query, batch=batch_data)
            logger.info(f"Created {len(batch_data)} {node_type} nodes")

    def _create_relationships_batch(self, session, relationships: List[Any]):
        """Create relationships in batch."""
        rels_by_type = {}
        for rel in relationships:
            rel_type = rel.get('type', 'RELATED_TO')
            if rel_type not in rels_by_type:
                rels_by_type[rel_type] = []
            rels_by_type[rel_type].append(rel)

        for rel_type, type_rels in rels_by_type.items():
            batch_data = []
            for rel in type_rels:
                props = rel.get('properties', {})
                clean_props = {k: self._clean_value(v) for k, v in props.items()}
                batch_data.append({
                    'from_id': rel.get('from_id', ''),
                    'to_id': rel.get('to_id', ''),
                    'props': clean_props
                })

            query = f"""
            UNWIND $batch as rel
            MATCH (from {{id: rel.from_id}})
            MATCH (to {{id: rel.to_id}})
            CREATE (from)-[r:{rel_type}]->(to)
            SET r = rel.props
            """
            session.run(query, batch=batch_data)
            logger.info(f"Created {len(batch_data)} {rel_type} relationships")

    def _create_perl_interactions(self, session):
        """Create meaningful interactions for Perl code."""
        query = """
        MATCH (p:PACKAGE)-[:HAS_METHOD]->(m1:METHOD)
        MATCH (p)-[:HAS_METHOD]->(m2:METHOD)
        WHERE m1 <> m2 AND m1.body IS NOT NULL AND m2.name IS NOT NULL
        AND m1.body CONTAINS m2.name
        MERGE (m1)-[r:INTRA_METHOD_CALL]->(m2)
        ON CREATE SET r.type = 'subroutine_call', r.call_count = 1
        ON MATCH SET r.call_count = r.call_count + 1
        """
        session.run(query)
        logger.info("Created intra-method call relationships")

    def _manage_indexes(self, session):
        """Manage database indexes."""
        try:
            # Create indexes for better query performance
            indexes = [
                "CREATE INDEX file_source_file IF NOT EXISTS FOR (f:FILE) ON (f.source_file)",
                "CREATE INDEX file_name IF NOT EXISTS FOR (f:FILE) ON (f.name)",
                "CREATE INDEX package_name IF NOT EXISTS FOR (p:PACKAGE) ON (p.name)",
                "CREATE INDEX method_name IF NOT EXISTS FOR (m:METHOD) ON (m.name)",
                "CREATE INDEX method_full_name IF NOT EXISTS FOR (m:METHOD) ON (m.full_name)",
                "CREATE INDEX use_module IF NOT EXISTS FOR (u:USE_STATEMENT) ON (u.module)",
                "CREATE INDEX node_id IF NOT EXISTS FOR (n) ON (n.id)"
            ]
            
            for index_query in indexes:
                session.run(index_query)
            
            logger.info("Successfully created/updated indexes")
            return True
        except Exception as e:
            logger.error(f"Error managing indexes: {e}")
            return False

    def store_ast(self, ast: Dict[str, Any]) -> bool:
        """Store AST in Neo4j."""
        try:
            if ast.get('type') == 'ProjectAST' and 'files' in ast:
                transformed_ast = self._transform_perl_ast(ast)
                nodes = transformed_ast['nodes']
                relationships = transformed_ast['relationships']
            else:
                nodes = ast.get('nodes', [])
                relationships = ast.get('relationships', [])

            logger.info(f"Storing {len(nodes)} nodes and {len(relationships)} relationships")
            
            self.clear_database()
            
            with self.driver.session() as session:
                self._create_node_batch(session, nodes)
                self._create_relationships_batch(session, relationships)
                self._create_perl_interactions(session)
                self._manage_indexes(session)

            # Verify storage
            with self.driver.session() as session:
                node_count = session.run("MATCH (n) RETURN count(n) as count").single()['count']
                rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
                logger.info(f"Successfully stored: {node_count} nodes, {rel_count} relationships")
            
            return True
            
        except Exception as e:
            logger.error(f"Storage failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_agent_queries(self):
        """Test the queries that agents will use."""
        logger.info("Testing agent-compatible queries...")
        
        with self.driver.session() as session:
            # Test file listing query
            files_query = """
            MATCH (f:FILE) 
            WHERE f.source_file IS NOT NULL 
            RETURN DISTINCT f.source_file AS file_path 
            ORDER BY file_path
            """
            files_result = session.run(files_query)
            files = [record['file_path'] for record in files_result]
            logger.info(f"Found {len(files)} files: {files}")
            
            if files:
                # Test file data query for first file
                test_file = files[0]
                file_data_query = """
                MATCH (f:FILE)
                WHERE f.source_file = $file_path
                
                OPTIONAL MATCH (f)-[:CONTAINS_PACKAGE]->(p:PACKAGE)
                OPTIONAL MATCH (p)-[:HAS_METHOD]->(m:METHOD)
                OPTIONAL MATCH (f)-[:USES_MODULE]->(u:USE_STATEMENT)
                OPTIONAL MATCH (p)-[:HAS_SCRIPT]->(s:SCRIPT_EXECUTION)
                
                WITH f, p, 
                     collect(DISTINCT {
                         name: m.name, 
                         body: COALESCE(m.body, ''),
                         parameters: COALESCE(m.parameters, '[]'),
                         id: m.id
                     }) AS methods,
                     collect(DISTINCT {
                         module: u.module,
                         name: COALESCE(u.name, u.module)
                     }) AS imports,
                     collect(DISTINCT {
                         name: s.name,
                         id: s.id
                     }) AS scripts
                
                RETURN f.source_file AS filePath,
                       f.name AS fileName,
                       f.file_type AS fileType,
                       collect(DISTINCT {
                           packageName: p.name, 
                           methods: CASE WHEN p IS NOT NULL THEN methods ELSE [] END,
                           scripts: CASE WHEN p IS NOT NULL THEN scripts ELSE [] END
                       }) AS packages,
                       imports
                """
                
                result = session.run(file_data_query, file_path=test_file).single()
                if result:
                    data = dict(result)
                    logger.info(f"Test query successful for {test_file}")
                    logger.info(f"Packages: {len(data.get('packages', []))}")
                    logger.info(f"Imports: {len(data.get('imports', []))}")
                else:
                    logger.warning(f"No data returned for {test_file}")

def main():
    """Main function for testing."""
    writer = Neo4jWriter()
    
    try:
        # Load and store AST
        ast_file = r'AST\combined_project_ast.json'
        if os.path.exists(ast_file):
            with open(ast_file, 'r') as f:
                ast = json.load(f)
            
            success = writer.store_ast(ast)
            
            if success:
                print("✅ Storage successful!")
                writer.test_agent_queries()
            else:
                print("❌ Storage failed!")
        else:
            print(f"❌ AST file not found: {ast_file}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        writer.close()

if __name__ == "__main__":
    main()