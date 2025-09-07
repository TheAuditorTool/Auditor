"""Database-aware Prisma ORM anti-pattern detection rule.

This module queries both the orm_queries and prisma_models tables to detect
common Prisma anti-patterns and performance issues including missing indexes,
unbounded queries, and missing transactions.
"""

import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any

# Import the Prisma schema parser
try:
    from theauditor.parsers.prisma_schema_parser import PrismaSchemaParser
    HAS_PRISMA_PARSER = True
except ImportError:
    HAS_PRISMA_PARSER = False


def find_prisma_issues(db_path: str, taint_registry=None) -> List[Dict[str, Any]]:
    """
    Analyze Prisma ORM queries for performance anti-patterns and security issues.
    
    Detects:
    - findMany queries without pagination (take/skip)
    - Nested write operations without transactions
    - Queries filtering on non-indexed fields
    - Missing includes causing potential N+1
    - Connection pool exhaustion risks
    
    Args:
        db_path: Path to repo_index.db
        taint_registry: Optional TaintRegistry to populate with Prisma patterns
        
    Returns:
        List of findings in normalized format compatible with Finding dataclass
    """
    findings = []
    
    # Register Prisma-specific sinks if registry provided
    if taint_registry:
        # SQL injection sinks (raw queries)
        taint_registry.register_sink("prisma.$queryRaw", "sql", "javascript")
        taint_registry.register_sink("prisma.$executeRaw", "sql", "javascript")
        taint_registry.register_sink("prisma.$queryRawUnsafe", "sql", "javascript")
        taint_registry.register_sink("prisma.$executeRawUnsafe", "sql", "javascript")
    
    # Connect to database
    if not Path(db_path).exists():
        return findings
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if required tables exist
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='orm_queries'"
    )
    if not cursor.fetchone():
        conn.close()
        return findings
    
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prisma_models'"
    )
    has_prisma_models = cursor.fetchone() is not None
    
    # Query all ORM queries that look like Prisma patterns
    cursor.execute(
        """
        SELECT file, line, query_type, includes, has_limit, has_transaction
        FROM orm_queries
        WHERE query_type LIKE '%.%'
        ORDER BY file, line
        """
    )
    orm_queries = cursor.fetchall()
    
    # Load Prisma model index information if available
    indexed_fields = {}
    if has_prisma_models:
        cursor.execute(
            """
            SELECT model_name, field_name, is_indexed
            FROM prisma_models
            WHERE is_indexed = 1 OR is_unique = 1
            """
        )
        for model_name, field_name, is_indexed in cursor.fetchall():
            if model_name not in indexed_fields:
                indexed_fields[model_name] = set()
            indexed_fields[model_name].add(field_name.lower())
    
    # Track multi-operation contexts for transaction detection
    file_operations = {}
    
    for file, line, query_type, includes_json, has_limit, has_transaction in orm_queries:
        # Only process Prisma-style queries (model.method pattern)
        if '.' not in query_type:
            continue
        
        parts = query_type.split('.')
        if len(parts) != 2:
            continue
        
        model_name = parts[0]
        method_name = parts[1]
        
        # Parse includes if present
        includes = None
        if includes_json:
            try:
                includes = json.loads(includes_json)
            except json.JSONDecodeError:
                pass
        
        # Detection 1: findMany without pagination
        if method_name == 'findMany' and not has_limit:
            findings.append({
                'pattern_name': 'PRISMA_UNBOUNDED_QUERY',
                'message': f'Unbounded findMany query on {model_name} - missing take/skip pagination',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'high',
                'snippet': f'prisma.{query_type}() without take/skip',
                'category': 'performance',
                'match_type': 'database',
                'framework': 'prisma',
                'details': {
                    'model': model_name,
                    'method': method_name,
                    'recommendation': 'Add take and skip parameters for pagination to prevent memory issues'
                }
            })
        
        # Detection 2: findMany without includes (potential N+1)
        if method_name == 'findMany' and not includes:
            findings.append({
                'pattern_name': 'PRISMA_POTENTIAL_N_PLUS_ONE',
                'message': f'findMany on {model_name} without includes - potential N+1 query pattern',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'medium',
                'snippet': f'prisma.{query_type}() without includes',
                'category': 'performance',
                'match_type': 'database',
                'framework': 'prisma',
                'details': {
                    'model': model_name,
                    'method': method_name,
                    'recommendation': 'Use include to eager load related data and avoid N+1 queries'
                }
            })
        
        # Detection 3: Write operations without transaction
        if method_name in ['create', 'createMany', 'update', 'updateMany', 'delete', 'deleteMany', 'upsert']:
            if file not in file_operations:
                file_operations[file] = []
            
            file_operations[file].append({
                'line': line,
                'model': model_name,
                'method': method_name,
                'has_transaction': has_transaction
            })
        
        # Detection 4: findFirst/findUnique without proper error handling hint
        if method_name in ['findUniqueOrThrow', 'findFirstOrThrow']:
            findings.append({
                'pattern_name': 'PRISMA_UNHANDLED_THROW',
                'message': f'{method_name} on {model_name} - ensure error handling is in place',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'low',
                'snippet': f'prisma.{query_type}()',
                'category': 'error_handling',
                'match_type': 'database',
                'framework': 'prisma',
                'details': {
                    'model': model_name,
                    'method': method_name,
                    'recommendation': 'Wrap in try-catch or use non-throwing variant if appropriate'
                }
            })
    
    # Detection 5: Multi-write operations without transaction
    for file, operations in file_operations.items():
        if len(operations) >= 2:
            # Sort by line number
            operations.sort(key=lambda x: x['line'])
            
            # Check for operations within 30 lines of each other
            for i in range(len(operations) - 1):
                op1 = operations[i]
                op2 = operations[i + 1]
                
                # If operations are close together and neither has transaction
                if (op2['line'] - op1['line'] <= 30 and 
                    not op1['has_transaction'] and not op2['has_transaction']):
                    
                    findings.append({
                        'pattern_name': 'PRISMA_MISSING_TRANSACTION',
                        'message': f'Multiple write operations without transaction - {op1["model"]}.{op1["method"]} and {op2["model"]}.{op2["method"]}',
                        'file': file,
                        'line': op1['line'],
                        'column': 0,
                        'severity': 'high',
                        'snippet': f'Multiple operations: {op1["method"]} and {op2["method"]}',
                        'category': 'data_integrity',
                        'match_type': 'database',
                        'framework': 'prisma',
                        'details': {
                            'operations': [f'{op1["model"]}.{op1["method"]}', f'{op2["model"]}.{op2["method"]}'],
                            'recommendation': 'Wrap related write operations in prisma.$transaction() for atomicity'
                        }
                    })
                    break  # Only report once per cluster
    
    # Detection 6: Queries on non-indexed fields (if schema information available)
    if has_prisma_models and indexed_fields:
        # Re-scan queries looking for filter patterns
        cursor.execute(
            """
            SELECT file, line, query_type
            FROM orm_queries
            WHERE query_type LIKE '%.findMany%' OR query_type LIKE '%.findFirst%'
            """
        )
        
        for file, line, query_type in cursor.fetchall():
            if '.' in query_type:
                model_name = query_type.split('.')[0]
                
                # Check if this model has indexed fields defined
                if model_name in indexed_fields:
                    # This is a simplified check - in production would need to parse the where clause
                    # For now, we flag queries on models with few indexes as potentially problematic
                    if len(indexed_fields[model_name]) < 2:  # Model has very few indexes
                        findings.append({
                            'pattern_name': 'PRISMA_MISSING_INDEX_HINT',
                            'message': f'Query on {model_name} - model has limited indexes, verify query performance',
                            'file': file,
                            'line': line,
                            'column': 0,
                            'severity': 'low',
                            'snippet': f'prisma.{query_type}()',
                            'category': 'performance',
                            'match_type': 'database',
                            'framework': 'prisma',
                            'details': {
                                'model': model_name,
                                'indexed_fields': list(indexed_fields[model_name]),
                                'recommendation': 'Ensure queries filter on indexed fields for better performance'
                            }
                        })
    
    # Detection 7: Connection pool exhaustion (check schema.prisma)
    if HAS_PRISMA_PARSER:
        # Look for schema.prisma files
        cursor.execute(
            """
            SELECT path FROM files 
            WHERE path LIKE '%schema.prisma%'
            """
        )
        schema_files = cursor.fetchall()
        
        for (schema_file,) in schema_files:
            full_path = Path(db_path).parent / schema_file
            if full_path.exists():
                try:
                    parser = PrismaSchemaParser()
                    schema_data = parser.parse_file(full_path)
                    
                    # Check datasource configuration
                    datasource = schema_data.get('datasource', {})
                    connection_limit = datasource.get('connection_limit')
                    
                    if connection_limit is None:
                        findings.append({
                            'pattern_name': 'PRISMA_NO_CONNECTION_LIMIT',
                            'message': 'No connection_limit specified in Prisma datasource - using default which may be too high',
                            'file': schema_file,
                            'line': 0,
                            'column': 0,
                            'severity': 'high',
                            'snippet': 'datasource without connection_limit parameter',
                            'category': 'performance',
                            'match_type': 'database',
                            'framework': 'prisma',
                            'details': {
                                'recommendation': 'Add ?connection_limit=10 to your DATABASE_URL or datasource url',
                                'default_limit': 'Defaults vary by provider (often 50-100)',
                                'suggested_limit': '10-20 connections for typical applications'
                            }
                        })
                    elif connection_limit > 20:
                        findings.append({
                            'pattern_name': 'PRISMA_HIGH_CONNECTION_LIMIT',
                            'message': f'Connection limit {connection_limit} is too high - can cause database overload',
                            'file': schema_file,
                            'line': 0,
                            'column': 0,
                            'severity': 'high',
                            'snippet': f'connection_limit={connection_limit}',
                            'category': 'performance',
                            'match_type': 'database',
                            'framework': 'prisma',
                            'details': {
                                'current_limit': connection_limit,
                                'recommended_max': 20,
                                'recommendation': 'Reduce connection_limit to 20 or less unless you have specific scaling requirements'
                            }
                        })
                    
                except Exception:
                    # Skip if parser fails
                    pass
    
    conn.close()
    return findings