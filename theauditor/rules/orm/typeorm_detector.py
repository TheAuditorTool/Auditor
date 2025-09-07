"""Database-aware TypeORM anti-pattern detection rule.

This module queries the orm_queries table to detect common TypeORM anti-patterns
including unbounded queries, cascade issues, and production misconfigurations.
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import List, Dict, Any


def find_typeorm_issues(db_path: str, taint_registry=None) -> List[Dict[str, Any]]:
    """
    Analyze TypeORM queries for performance anti-patterns and security issues.
    
    Detects:
    - QueryBuilder chains without limits/take
    - Potentially dangerous cascade: true options
    - Synchronize: true in production (via config detection)
    - Missing indexes on commonly queried fields
    - Complex joins without proper pagination
    
    Args:
        db_path: Path to repo_index.db
        taint_registry: Optional TaintRegistry to populate with TypeORM patterns
        
    Returns:
        List of findings in normalized format compatible with Finding dataclass
    """
    findings = []
    
    # Register TypeORM-specific sinks if registry provided
    if taint_registry:
        # SQL injection sinks
        taint_registry.register_sink("createQueryBuilder", "sql", "javascript")
        taint_registry.register_sink("query", "sql", "javascript")
        taint_registry.register_sink("manager.query", "sql", "javascript")
        taint_registry.register_sink("connection.query", "sql", "javascript")
        taint_registry.register_sink("getRepository().query", "sql", "javascript")
    
    # Connect to database
    if not Path(db_path).exists():
        return findings
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if orm_queries table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='orm_queries'"
    )
    if not cursor.fetchone():
        # Table doesn't exist, might be no ORM usage or not indexed yet
        conn.close()
        return findings
    
    # Query all ORM queries that look like TypeORM patterns
    cursor.execute(
        """
        SELECT file, line, query_type, includes, has_limit, has_transaction
        FROM orm_queries
        WHERE query_type LIKE 'Repository.%' OR query_type LIKE 'QueryBuilder.%'
        ORDER BY file, line
        """
    )
    orm_queries = cursor.fetchall()
    
    # Track multi-operation contexts for transaction detection
    file_operations = {}
    
    for file, line, query_type, includes_json, has_limit, has_transaction in orm_queries:
        # Parse includes if present
        includes = None
        if includes_json:
            try:
                includes = json.loads(includes_json)
            except json.JSONDecodeError:
                pass
        
        # Detection 1: QueryBuilder without limits
        if query_type.startswith('QueryBuilder.') and not has_limit:
            # Check if it's a query that returns multiple results
            method = query_type.split('.')[-1] if '.' in query_type else query_type
            if method in ['getMany', 'getRawMany', 'getManyAndCount']:
                findings.append({
                    'pattern_name': 'TYPEORM_UNBOUNDED_QUERYBUILDER',
                    'message': f'QueryBuilder {method} without limit/take - can cause memory issues',
                    'file': file,
                    'line': line,
                    'column': 0,
                    'severity': 'high',
                    'snippet': f'{query_type}() without .limit() or .take()',
                    'category': 'performance',
                    'match_type': 'database',
                    'framework': 'typeorm',
                    'details': {
                        'query_type': query_type,
                        'recommendation': 'Add .limit(n) or .take(n) to QueryBuilder chain before executing'
                    }
                })
        
        # Detection 2: Complex joins without pagination
        if includes and isinstance(includes, dict):
            join_count = includes.get('joins', 0)
            if join_count >= 3 and not has_limit:
                findings.append({
                    'pattern_name': 'TYPEORM_COMPLEX_JOIN_NO_LIMIT',
                    'message': f'Complex query with {join_count} joins but no pagination',
                    'file': file,
                    'line': line,
                    'column': 0,
                    'severity': 'high',
                    'snippet': f'QueryBuilder with {join_count} joins and no limit',
                    'category': 'performance',
                    'match_type': 'database',
                    'framework': 'typeorm',
                    'details': {
                        'query_type': query_type,
                        'join_count': join_count,
                        'recommendation': 'Complex joins should use pagination to avoid memory issues'
                    }
                })
        
        # Detection 3: Repository.find without pagination
        if query_type == 'Repository.find' and not has_limit:
            findings.append({
                'pattern_name': 'TYPEORM_UNBOUNDED_FIND',
                'message': 'Repository.find() without take option - fetches all records',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'medium',
                'snippet': 'repository.find() without take option',
                'category': 'performance',
                'match_type': 'database',
                'framework': 'typeorm',
                'details': {
                    'query_type': query_type,
                    'recommendation': 'Add { take: n } option to limit results'
                }
            })
        
        # Detection 4: Multiple saves without transaction
        if query_type == 'Repository.save':
            if file not in file_operations:
                file_operations[file] = []
            
            file_operations[file].append({
                'line': line,
                'query_type': query_type,
                'has_transaction': has_transaction
            })
        
        # Detection 5: Potential N+1 - findOne in potential loop context
        if query_type in ['Repository.findOne', 'Repository.findOneBy']:
            # This is a heuristic - if there are multiple findOne calls close together
            # it might indicate a loop
            if file not in file_operations:
                file_operations[file] = []
            
            # Check if there's another findOne within 10 lines
            similar_queries = [
                q for q in file_operations.get(file, []) 
                if q['query_type'] == query_type and abs(q['line'] - line) <= 10
            ]
            
            if similar_queries:
                findings.append({
                    'pattern_name': 'TYPEORM_POTENTIAL_N_PLUS_ONE',
                    'message': f'Multiple {query_type} calls close together - potential N+1 pattern',
                    'file': file,
                    'line': line,
                    'column': 0,
                    'severity': 'medium',
                    'snippet': f'Multiple {query_type} within 10 lines',
                    'category': 'performance',
                    'match_type': 'database',
                    'framework': 'typeorm',
                    'details': {
                        'query_type': query_type,
                        'recommendation': 'Use relations option or QueryBuilder with joins to fetch related data'
                    }
                })
    
    # Detection 6: Multiple saves without transaction
    for file, operations in file_operations.items():
        save_ops = [op for op in operations if op['query_type'] == 'Repository.save']
        
        if len(save_ops) >= 2:
            # Sort by line number
            save_ops.sort(key=lambda x: x['line'])
            
            # Check for operations within 30 lines of each other
            for i in range(len(save_ops) - 1):
                op1 = save_ops[i]
                op2 = save_ops[i + 1]
                
                # If operations are close together and neither has transaction
                if (op2['line'] - op1['line'] <= 30 and 
                    not op1['has_transaction'] and not op2['has_transaction']):
                    
                    findings.append({
                        'pattern_name': 'TYPEORM_MISSING_TRANSACTION',
                        'message': 'Multiple save operations without transaction - data consistency risk',
                        'file': file,
                        'line': op1['line'],
                        'column': 0,
                        'severity': 'high',
                        'snippet': f"Multiple save operations at lines {op1['line']} and {op2['line']}",
                        'category': 'data_integrity',
                        'match_type': 'database',
                        'framework': 'typeorm',
                        'details': {
                            'operations': ['save', 'save'],
                            'lines': [op1['line'], op2['line']],
                            'recommendation': 'Use EntityManager.transaction() or QueryRunner for atomic operations'
                        }
                    })
                    break  # Only report once per cluster
    
    # Detection 7: Missing @Index on frequently queried fields
    # This is a simplified check - looks for entities without proper indexing
    cursor.execute(
        """
        SELECT DISTINCT file FROM orm_queries 
        WHERE query_type LIKE 'Repository.%'
        """
    )
    repo_files = cursor.fetchall()
    
    for (repo_file,) in repo_files:
        # Try to find corresponding entity file
        entity_path = repo_file.replace('repository.', 'entity.').replace('Repository.', 'Entity.')
        if not entity_path.endswith('entity.ts') and not entity_path.endswith('entity.js'):
            # Try common patterns
            entity_path = repo_file.replace('.ts', '.entity.ts').replace('.js', '.entity.js')
        
        # Check if entity file exists
        cursor.execute(
            """
            SELECT path FROM files 
            WHERE path LIKE ? OR path LIKE ?
            """,
            (f'%{Path(entity_path).stem}%entity%', f'%{Path(repo_file).stem.replace("repository", "")}%entity%')
        )
        entity_files = cursor.fetchall()
        
        for (entity_file,) in entity_files:
            full_path = Path(db_path).parent / entity_file
            if full_path.exists():
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        # Count @Index decorators
                        index_count = content.count('@Index')
                        
                        # Count properties (simplified - looks for property declarations)
                        property_pattern = re.compile(r'^\s*(@Column|@PrimaryGeneratedColumn|@PrimaryColumn).*\n\s*(\w+)\s*:', re.MULTILINE)
                        properties = property_pattern.findall(content)
                        property_count = len(properties)
                        
                        # If there are many properties but few indexes, flag it
                        if property_count > 5 and index_count < 2:
                            findings.append({
                                'pattern_name': 'TYPEORM_MISSING_INDEXES',
                                'message': f'Entity has {property_count} properties but only {index_count} indexes - queries may be slow',
                                'file': entity_file,
                                'line': 0,
                                'column': 0,
                                'severity': 'medium',
                                'snippet': f'{property_count} properties, {index_count} @Index decorators',
                                'category': 'performance',
                                'match_type': 'database',
                                'framework': 'typeorm',
                                'details': {
                                    'property_count': property_count,
                                    'index_count': index_count,
                                    'recommendation': 'Add @Index() decorators to frequently queried fields for better performance'
                                }
                            })
                        
                        # Check for common queryable fields without indexes
                        common_indexed_fields = ['email', 'username', 'userId', 'createdAt', 'updatedAt', 'status', 'type']
                        for field_name in common_indexed_fields:
                            # Check if field exists but not indexed
                            field_pattern = re.compile(rf'^\s*(@Column.*\n\s*)?{field_name}\s*:', re.MULTILINE | re.IGNORECASE)
                            index_pattern = re.compile(rf'@Index.*{field_name}|@Index\(\)\s*\n\s*(@Column.*\n\s*)?{field_name}', re.IGNORECASE)
                            
                            if field_pattern.search(content) and not index_pattern.search(content):
                                findings.append({
                                    'pattern_name': 'TYPEORM_COMMON_FIELD_NOT_INDEXED',
                                    'message': f'Common queryable field "{field_name}" is not indexed',
                                    'file': entity_file,
                                    'line': 0,
                                    'column': 0,
                                    'severity': 'medium',
                                    'snippet': f'{field_name} field without @Index',
                                    'category': 'performance',
                                    'match_type': 'database',
                                    'framework': 'typeorm',
                                    'details': {
                                        'field': field_name,
                                        'recommendation': f'Add @Index() decorator to {field_name} field as it is commonly used in queries'
                                    }
                                })
                        
                except Exception:
                    # Skip files that can't be read
                    pass
    
    # Detection 8: Check for cascade and synchronize configuration issues
    # This would require parsing entity decorators, which we'll check in files table
    cursor.execute(
        """
        SELECT path FROM files 
        WHERE (ext = '.ts' OR ext = '.js') 
        AND (path LIKE '%entity%' OR path LIKE '%model%')
        """
    )
    entity_files = cursor.fetchall()
    
    # For each entity file, check if we can detect dangerous patterns
    # Note: This is a simplified check - in production would need proper decorator parsing
    for (entity_file,) in entity_files:
        full_path = Path(db_path).parent / entity_file
        if full_path.exists():
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Check for cascade: true (dangerous in production)
                    if 'cascade: true' in content or 'cascade:true' in content:
                        # Find the line number
                        lines = content.split('\n')
                        for i, line in enumerate(lines, 1):
                            if 'cascade: true' in line or 'cascade:true' in line:
                                findings.append({
                                    'pattern_name': 'TYPEORM_CASCADE_TRUE',
                                    'message': 'cascade: true detected - can cause unintended data deletion',
                                    'file': entity_file,
                                    'line': i,
                                    'column': 0,
                                    'severity': 'high',
                                    'snippet': line.strip()[:100],
                                    'category': 'data_integrity',
                                    'match_type': 'database',
                                    'framework': 'typeorm',
                                    'details': {
                                        'recommendation': 'Use specific cascade options like ["insert", "update"] instead of true'
                                    }
                                })
                                break  # Report once per file
                    
                    # Check for synchronize: true (dangerous in production)
                    if 'synchronize: true' in content or 'synchronize:true' in content:
                        lines = content.split('\n')
                        for i, line in enumerate(lines, 1):
                            if 'synchronize: true' in line or 'synchronize:true' in line:
                                findings.append({
                                    'pattern_name': 'TYPEORM_SYNCHRONIZE_TRUE',
                                    'message': 'synchronize: true detected - NEVER use in production',
                                    'file': entity_file,
                                    'line': i,
                                    'column': 0,
                                    'severity': 'critical',
                                    'snippet': line.strip()[:100],
                                    'category': 'security',
                                    'match_type': 'database',
                                    'framework': 'typeorm',
                                    'details': {
                                        'recommendation': 'Use migrations instead of synchronize in production environments'
                                    }
                                })
                                break  # Report once per file
                    
            except Exception:
                # Skip files that can't be read
                pass
    
    conn.close()
    return findings