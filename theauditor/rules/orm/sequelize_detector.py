"""Database-aware Sequelize ORM anti-pattern detection rule.

This module queries the orm_queries table to detect common Sequelize anti-patterns
and performance issues that can severely degrade application performance.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any


def find_sequelize_issues(db_path: str, taint_registry=None) -> List[Dict[str, Any]]:
    """
    Analyze Sequelize ORM queries for performance anti-patterns and security issues.
    
    Detects:
    - Death queries: { include: [{ all: true, nested: true }] }
    - N+1 queries from missing includes
    - Multi-table operations missing transactions
    - findOrCreate race conditions
    - Unbounded queries without limits
    
    Args:
        db_path: Path to repo_index.db
        taint_registry: Optional TaintRegistry to populate with Sequelize patterns
        
    Returns:
        List of findings in normalized format compatible with Finding dataclass
    """
    findings = []
    
    # Register Sequelize-specific sinks if registry provided
    if taint_registry:
        # SQL injection sinks
        taint_registry.register_sink("sequelize.query", "sql", "javascript")
        taint_registry.register_sink("models.sequelize.query", "sql", "javascript")
        taint_registry.register_sink("db.sequelize.literal", "sql", "javascript")
        taint_registry.register_sink("Sequelize.literal", "sql", "javascript")
        
        # Path traversal sinks (file operations)
        taint_registry.register_sink("sequelize.import", "path", "javascript")
    
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
    
    # Query all ORM queries
    cursor.execute(
        """
        SELECT file, line, query_type, includes, has_limit, has_transaction
        FROM orm_queries
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
        
        # Detection 1: Death query pattern - include all with nested
        if includes and isinstance(includes, dict):
            if includes.get('all') and includes.get('nested'):
                findings.append({
                    'pattern_name': 'SEQUELIZE_DEATH_QUERY',
                    'message': f'Death query detected: include all with nested at {query_type}',
                    'file': file,
                    'line': line,
                    'column': 0,
                    'severity': 'critical',
                    'snippet': f'{query_type}({{ include: [{{ all: true, nested: true }}] }})',
                    'category': 'performance',
                    'match_type': 'database',
                    'framework': 'sequelize',
                    'details': {
                        'query_type': query_type,
                        'recommendation': 'Never use { all: true, nested: true }. Specify exact relations needed.'
                    }
                })
        
        # Detection 2: findAll without includes (potential N+1)
        if query_type == 'findAll' and not includes:
            findings.append({
                'pattern_name': 'SEQUELIZE_POTENTIAL_N_PLUS_ONE',
                'message': f'findAll without includes - potential N+1 query pattern',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'high',
                'snippet': f'{query_type}() without includes',
                'category': 'performance',
                'match_type': 'database',
                'framework': 'sequelize',
                'details': {
                    'query_type': query_type,
                    'recommendation': 'Add include option to eager load related data and avoid N+1 queries'
                }
            })
        
        # Detection 3: Unbounded queries without limit
        if query_type in ['findAll', 'findAndCountAll'] and not has_limit:
            findings.append({
                'pattern_name': 'SEQUELIZE_UNBOUNDED_QUERY',
                'message': f'Unbounded {query_type} without limit - can cause memory issues',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'medium',
                'snippet': f'{query_type}() without limit',
                'category': 'performance',
                'match_type': 'database',
                'framework': 'sequelize',
                'details': {
                    'query_type': query_type,
                    'recommendation': 'Add limit option to prevent fetching too many records'
                }
            })
        
        # Detection 4: findOrCreate race condition
        if query_type == 'findOrCreate' and not has_transaction:
            findings.append({
                'pattern_name': 'SEQUELIZE_FINDORCREATE_RACE',
                'message': 'findOrCreate without transaction - race condition vulnerability',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'high',
                'snippet': f'{query_type}() without transaction',
                'category': 'security',
                'match_type': 'database',
                'framework': 'sequelize',
                'details': {
                    'query_type': query_type,
                    'recommendation': 'Wrap findOrCreate in a transaction to prevent race conditions'
                }
            })
        
        # Track operations per file for multi-table transaction detection
        if file not in file_operations:
            file_operations[file] = []
        
        # Track write operations for transaction detection
        if query_type in ['create', 'update', 'destroy', 'bulkCreate', 'bulkUpdate']:
            file_operations[file].append({
                'line': line,
                'query_type': query_type,
                'has_transaction': has_transaction
            })
    
    # Detection 5: Multi-table operations without transaction
    # Check for multiple write operations close together without transaction
    for file, operations in file_operations.items():
        if len(operations) >= 2:
            # Sort by line number
            operations.sort(key=lambda x: x['line'])
            
            # Check for operations within 20 lines of each other
            for i in range(len(operations) - 1):
                op1 = operations[i]
                op2 = operations[i + 1]
                
                # If operations are close together and neither has transaction
                if (op2['line'] - op1['line'] <= 20 and 
                    not op1['has_transaction'] and not op2['has_transaction']):
                    
                    findings.append({
                        'pattern_name': 'SEQUELIZE_MISSING_TRANSACTION',
                        'message': 'Multiple write operations without transaction - data consistency risk',
                        'file': file,
                        'line': op1['line'],
                        'column': 0,
                        'severity': 'high',
                        'snippet': f"Multiple operations: {op1['query_type']} and {op2['query_type']}",
                        'category': 'security',
                        'match_type': 'database',
                        'framework': 'sequelize',
                        'details': {
                            'operations': [op1['query_type'], op2['query_type']],
                            'recommendation': 'Wrap related write operations in a transaction for atomicity'
                        }
                    })
                    break  # Only report once per cluster
    
    conn.close()
    return findings