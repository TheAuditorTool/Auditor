"""Parser for Prisma schema files.

This module provides parsing of schema.prisma files to extract
models, fields, datasource configuration, and security-relevant settings.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional


class PrismaSchemaParser:
    """Parser for Prisma schema.prisma files."""
    
    def __init__(self):
        """Initialize the Prisma schema parser."""
        pass
    
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a schema.prisma file and extract models, fields, and datasource info.
        
        Args:
            file_path: Path to the schema.prisma file
            
        Returns:
            Dictionary with parsed Prisma schema information:
            {
                'models': [
                    {
                        'name': 'User',
                        'fields': [
                            {
                                'name': 'id',
                                'type': 'Int',
                                'is_indexed': True,
                                'is_unique': True,
                                'is_relation': False
                            }
                        ]
                    }
                ],
                'datasource': {
                    'provider': 'postgresql',
                    'url': 'env("DATABASE_URL")',
                    'connection_limit': None  # Or a number if specified
                }
            }
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._parse_schema(content)
            
        except FileNotFoundError:
            return {'error': f'File not found: {file_path}', 'models': [], 'datasource': {}}
        except PermissionError:
            return {'error': f'Permission denied: {file_path}', 'models': [], 'datasource': {}}
        except Exception as e:
            return {'error': f'Error parsing file: {str(e)}', 'models': [], 'datasource': {}}
    
    def parse_content(self, content: str, file_path: str = 'unknown') -> Dict[str, Any]:
        """
        Parse Prisma schema content string.
        
        Args:
            content: schema.prisma content as string
            file_path: Optional file path for reference
            
        Returns:
            Dictionary with parsed Prisma schema information
        """
        try:
            return self._parse_schema(content)
        except Exception as e:
            return {'error': f'Parsing error: {str(e)}', 'models': [], 'datasource': {}}
    
    def _parse_schema(self, content: str) -> Dict[str, Any]:
        """
        Parse the actual schema content.
        
        Args:
            content: Prisma schema content
            
        Returns:
            Dictionary with models and datasource configuration
        """
        result = {
            'models': [],
            'datasource': {}
        }
        
        # Parse datasource block
        datasource_match = re.search(
            r'datasource\s+\w+\s*\{([^}]*)\}',
            content,
            re.DOTALL | re.IGNORECASE
        )
        
        if datasource_match:
            datasource_content = datasource_match.group(1)
            result['datasource'] = self._parse_datasource(datasource_content)
        
        # Parse models
        model_pattern = re.compile(
            r'model\s+(\w+)\s*\{([^}]*)\}',
            re.DOTALL
        )
        
        for match in model_pattern.finditer(content):
            model_name = match.group(1)
            model_content = match.group(2)
            
            model = {
                'name': model_name,
                'fields': self._parse_fields(model_content)
            }
            
            result['models'].append(model)
        
        return result
    
    def _parse_datasource(self, content: str) -> Dict[str, Any]:
        """
        Parse datasource configuration block.
        
        Args:
            content: Content inside datasource { } block
            
        Returns:
            Dictionary with datasource configuration
        """
        datasource = {
            'provider': None,
            'url': None,
            'connection_limit': None
        }
        
        # Extract provider
        provider_match = re.search(r'provider\s*=\s*["\']([^"\']+)["\']', content)
        if provider_match:
            datasource['provider'] = provider_match.group(1)
        
        # Extract URL
        url_match = re.search(r'url\s*=\s*([^\n]+)', content)
        if url_match:
            url_value = url_match.group(1).strip()
            datasource['url'] = url_value
            
            # Check if connection_limit is specified in the URL
            # Common patterns:
            # - ?connection_limit=10
            # - &connection_limit=10
            # - connection_limit=10 (in env variable)
            limit_match = re.search(r'connection_limit=(\d+)', url_value)
            if limit_match:
                datasource['connection_limit'] = int(limit_match.group(1))
        
        return datasource
    
    def _parse_fields(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse fields within a model block.
        
        Args:
            content: Content inside model { } block
            
        Returns:
            List of field dictionaries
        """
        fields = []
        lines = content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('//'):
                continue
            
            # Skip block attributes (@@)
            if line.startswith('@@'):
                continue
            
            # Parse field: fieldName Type @attributes
            field_match = re.match(r'^(\w+)\s+(\w+(?:\[\])?(?:\?)?)', line)
            if field_match:
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                
                field = {
                    'name': field_name,
                    'type': field_type,
                    'is_indexed': False,
                    'is_unique': False,
                    'is_relation': False
                }
                
                # Check for attributes
                if '@id' in line:
                    field['is_indexed'] = True
                    field['is_unique'] = True
                
                if '@unique' in line:
                    field['is_unique'] = True
                    field['is_indexed'] = True  # Unique implies indexed
                
                if '@index' in line:
                    field['is_indexed'] = True
                
                if '@relation' in line:
                    field['is_relation'] = True
                
                # Check if it's a relation type (starts with capital letter, not a primitive)
                primitives = ['String', 'Int', 'BigInt', 'Float', 'Boolean', 'DateTime', 'Json', 'Bytes', 'Decimal']
                if field_type and field_type[0].isupper() and field_type.replace('[]', '').replace('?', '') not in primitives:
                    field['is_relation'] = True
                
                fields.append(field)
        
        # Check for composite indexes
        for line in lines:
            line = line.strip()
            if line.startswith('@@index'):
                # Extract field names from composite index
                # @@index([field1, field2])
                index_match = re.search(r'@@index\s*\(\s*\[([^\]]+)\]', line)
                if index_match:
                    indexed_fields = index_match.group(1).split(',')
                    for indexed_field in indexed_fields:
                        indexed_field = indexed_field.strip().strip('"').strip("'")
                        # Mark these fields as indexed
                        for field in fields:
                            if field['name'] == indexed_field:
                                field['is_indexed'] = True
            
            elif line.startswith('@@unique'):
                # Extract field names from composite unique
                # @@unique([field1, field2])
                unique_match = re.search(r'@@unique\s*\(\s*\[([^\]]+)\]', line)
                if unique_match:
                    unique_fields = unique_match.group(1).split(',')
                    for unique_field in unique_fields:
                        unique_field = unique_field.strip().strip('"').strip("'")
                        # Mark these fields as unique and indexed
                        for field in fields:
                            if field['name'] == unique_field:
                                field['is_unique'] = True
                                field['is_indexed'] = True
        
        return fields
    
    def find_security_issues(self, schema_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze parsed schema for security and performance issues.
        
        Args:
            schema_data: Parsed schema data
            
        Returns:
            Dictionary of security findings
        """
        issues = {
            'missing_indexes': [],
            'connection_pool_issues': [],
            'findings': []
        }
        
        # Check connection pool configuration
        datasource = schema_data.get('datasource', {})
        connection_limit = datasource.get('connection_limit')
        
        if connection_limit is None:
            issues['connection_pool_issues'].append({
                'type': 'missing_connection_limit',
                'severity': 'medium',
                'description': 'No connection_limit specified in datasource URL - using default which may be too high'
            })
            issues['findings'].append({
                'type': 'missing_connection_limit',
                'severity': 'medium',
                'description': 'No connection_limit specified - defaults can cause pool exhaustion'
            })
        elif connection_limit > 20:
            issues['connection_pool_issues'].append({
                'type': 'high_connection_limit',
                'severity': 'high',
                'value': connection_limit,
                'description': f'Connection limit {connection_limit} is too high - can cause database overload'
            })
            issues['findings'].append({
                'type': 'high_connection_limit',
                'severity': 'high',
                'value': connection_limit,
                'description': f'Connection limit {connection_limit} exceeds recommended maximum of 20'
            })
        
        # Check for models without any indexes
        for model in schema_data.get('models', []):
            indexed_fields = [f for f in model['fields'] if f['is_indexed']]
            
            if not indexed_fields:
                issues['missing_indexes'].append({
                    'model': model['name'],
                    'severity': 'medium',
                    'description': f'Model {model["name"]} has no indexed fields - queries will be slow'
                })
                issues['findings'].append({
                    'type': 'no_indexes',
                    'severity': 'medium',
                    'model': model['name'],
                    'description': f'Model {model["name"]} has no indexed fields'
                })
        
        return issues