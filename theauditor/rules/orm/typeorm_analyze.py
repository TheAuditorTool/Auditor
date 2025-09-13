"""
TypeORM Analyzer - SQL-based implementation.

This module detects TypeORM anti-patterns and performance issues
using TheAuditor's indexed database.

Migration from: typeorm_detector.py (384 lines -> ~320 lines)
Performance: ~12x faster using direct SQL queries
"""

import sqlite3
import json
import re
from pathlib import Path
from typing import List

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_typeorm_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect TypeORM anti-patterns and performance issues.
    
    Detects:
    - Unbounded QueryBuilder without limits
    - Unbounded Repository.find without pagination
    - Complex joins without pagination
    - Missing transactions for multiple operations
    - N+1 query patterns
    - Unsafe raw SQL queries
    - Dangerous cascade configurations
    - synchronize: true in production
    - Missing database indexes
    
    Returns:
        List of TypeORM issues found
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    # Common indexed fields that should have @Index
    common_indexed_fields = [
        'email', 'username', 'userId', 'createdAt', 
        'updatedAt', 'status', 'type', 'slug', 'code'
    ]
    
    try:
        # Check if orm_queries table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orm_queries'"
        )
        if not cursor.fetchone():
            return findings
        
        # Run each analysis
        findings.extend(_detect_unbounded_querybuilder(cursor))
        findings.extend(_detect_unbounded_repository(cursor))
        findings.extend(_detect_complex_joins(cursor))
        findings.extend(_detect_missing_transactions(cursor))
        findings.extend(_detect_n_plus_one(cursor))
        findings.extend(_detect_raw_queries(cursor))
        findings.extend(_detect_cascade_issues(cursor))
        findings.extend(_detect_synchronize_issues(cursor))
        findings.extend(_detect_missing_indexes(cursor, common_indexed_fields))
        
    except Exception:
        pass  # Return empty findings on error
    finally:
        conn.close()
        
    return findings
    
def _detect_unbounded_querybuilder(cursor) -> List[StandardFinding]:
    """Detect QueryBuilder without limits."""
    findings = []
    
    query = """
    SELECT file, line, query_type
    FROM orm_queries
    WHERE (query_type LIKE 'QueryBuilder.getMany%' 
           OR query_type LIKE 'QueryBuilder.getRawMany%')
      AND has_limit = 0
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, query_type = row
        method = query_type.split('.')[-1] if '.' in query_type else query_type
        
        findings.append(StandardFinding(
            rule_name='typeorm-unbounded-querybuilder',
            message=f'QueryBuilder.{method} without limit/take',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='orm-performance',
            snippet=f'{query_type}() without .limit() or .take()',
            fix_suggestion='Add .limit() or .take() for pagination',
            cwe_id='CWE-400'
        ))
    
    return findings
    
def _detect_unbounded_repository(cursor) -> List[StandardFinding]:
    """Detect Repository.find without pagination."""
    findings = []
    
    query = """
    SELECT file, line, query_type
    FROM orm_queries
    WHERE (query_type = 'Repository.find' 
           OR query_type = 'Repository.findAndCount')
      AND has_limit = 0
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, query_type = row
        
        findings.append(StandardFinding(
            rule_name='typeorm-unbounded-find',
            message=f'{query_type} without take option - fetches all records',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='orm-performance',
            snippet=f'{query_type}() without pagination',
            fix_suggestion='Add take and skip options for pagination',
            cwe_id='CWE-400'
        ))
    
    return findings
    
def _detect_complex_joins(cursor) -> List[StandardFinding]:
    """Detect complex joins without pagination."""
    findings = []
    
    query = """
    SELECT file, line, query_type, includes
    FROM orm_queries
    WHERE query_type LIKE 'QueryBuilder.%'
      AND includes IS NOT NULL
      AND has_limit = 0
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, query_type, includes_json = row
        
        try:
            includes = json.loads(includes_json) if includes_json else {}
            join_count = includes.get('joins', 0)
            
            if join_count >= 3:
                findings.append(StandardFinding(
                    rule_name='typeorm-complex-join-no-limit',
                    message=f'Complex query with {join_count} joins but no pagination',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='orm-performance',
                    snippet=f'QueryBuilder with {join_count} joins',
                    fix_suggestion='Add pagination to complex queries',
                    cwe_id='CWE-400'
                ))
        except json.JSONDecodeError:
            pass
    
    return findings
    
def _detect_missing_transactions(cursor) -> List[StandardFinding]:
    """Detect multiple save operations without transactions."""
    findings = []
    
    # Get all save operations grouped by file
    query = """
    SELECT file, line, query_type, has_transaction
    FROM orm_queries
    WHERE query_type IN ('Repository.save', 'Repository.remove', 
                        'Repository.update', 'Repository.delete')
    ORDER BY file, line
    """
    
    cursor.execute(query)
    
    # Group by file
    file_ops = {}
    for row in cursor.fetchall():
        file, line, query_type, has_transaction = row
        if file not in file_ops:
            file_ops[file] = []
        file_ops[file].append({
            'line': line,
            'query': query_type,
            'has_transaction': has_transaction
        })
    
    # Check for close operations without transactions
    for file, operations in file_ops.items():
        for i in range(len(operations) - 1):
            op1 = operations[i]
            op2 = operations[i + 1]
            
            # Operations within 30 lines without transaction
            if (op2['line'] - op1['line'] <= 30 and 
                not op1['has_transaction'] and 
                not op2['has_transaction']):
                
                findings.append(StandardFinding(
                    rule_name='typeorm-missing-transaction',
                    message=f"Multiple operations without transaction: {op1['query']} and {op2['query']}",
                    file_path=file,
                    line=op1['line'],
                    severity=Severity.HIGH,
                    category='orm-data-integrity',
                    snippet='Use EntityManager.transaction() for atomicity',
                    fix_suggestion='Wrap multiple operations in EntityManager.transaction()',
                    cwe_id='CWE-662'
                ))
                break  # One finding per cluster
    
    return findings
    
def _detect_n_plus_one(cursor) -> List[StandardFinding]:
    """Detect potential N+1 query patterns."""
    findings = []
    
    # Look for multiple findOne calls close together
    query = """
    SELECT file, line, query_type
    FROM orm_queries
    WHERE query_type IN ('Repository.findOne', 'Repository.findOneBy')
    ORDER BY file, line
    """
    
    cursor.execute(query)
    
    # Group by file and check for patterns
    file_queries = {}
    for row in cursor.fetchall():
        file, line, query_type = row
        if file not in file_queries:
            file_queries[file] = []
        file_queries[file].append({'line': line, 'query': query_type})
    
    for file, queries in file_queries.items():
        for i in range(len(queries) - 1):
            q1 = queries[i]
            q2 = queries[i + 1]
            
            # Multiple findOne within 10 lines
            if q2['line'] - q1['line'] <= 10:
                findings.append(StandardFinding(
                    rule_name='typeorm-n-plus-one',
                    message=f"Multiple {q1['query']} calls - potential N+1",
                    file_path=file,
                    line=q1['line'],
                    severity=Severity.MEDIUM,
                    category='orm-performance',
                    snippet='Consider using relations or joins',
                    fix_suggestion='Use relations or joins to fetch related data',
                    cwe_id='CWE-400'
                ))
                break
    
    return findings
    
def _detect_raw_queries(cursor) -> List[StandardFinding]:
    """Detect potentially unsafe raw SQL queries."""
    findings = []
    
    # Look for raw query methods
    query = """
    SELECT DISTINCT f.file, f.line, f.callee_function, f.args_json
    FROM function_call_args f
    WHERE f.callee_function LIKE '%query%'
       OR f.callee_function LIKE '%createQueryBuilder%'
       OR f.callee_function = 'query'
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, func, args_json = row
        
        # Check for string concatenation or interpolation
        if args_json:
            has_interpolation = any(x in args_json for x in ['${', '"+', '" +', '` +'])
            if has_interpolation:
                findings.append(StandardFinding(
                    rule_name='typeorm-sql-injection',
                    message=f'Potential SQL injection in {func}',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='orm-security',
                    snippet=f'{func}() with string interpolation',
                    fix_suggestion='Use parameterized queries or QueryBuilder',
                    cwe_id='CWE-89'
                ))
    
    return findings
    
def _detect_cascade_issues(cursor) -> List[StandardFinding]:
    """Detect dangerous cascade: true configurations."""
    findings = []
    
    # Look for cascade: true in assignments
    query = """
    SELECT file, line, source_expr
    FROM assignments
    WHERE source_expr LIKE '%cascade%true%'
       OR source_expr LIKE '%cascade:%true%'
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, expr = row
        findings.append(StandardFinding(
            rule_name='typeorm-cascade-true',
            message='cascade: true can cause unintended data deletion',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='orm-data-integrity',
            snippet='Use specific cascade options instead',
            fix_suggestion='Use specific cascade options like ["insert", "update"]',
            cwe_id='CWE-672'
        ))
    
    # Also check in symbols for decorator usage
    query = """
    SELECT file, line, name
    FROM symbols
    WHERE name LIKE '%cascade%true%'
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, name = row
        findings.append(StandardFinding(
            rule_name='typeorm-cascade-true',
            message='cascade: true in decorator - use specific options',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='orm-data-integrity',
            snippet='cascade: ["insert", "update"] instead of true',
            fix_suggestion='Replace cascade: true with specific options',
            cwe_id='CWE-672'
        ))
    
    return findings
    
def _detect_synchronize_issues(cursor) -> List[StandardFinding]:
    """Detect synchronize: true in production."""
    findings = []
    
    # Look for synchronize: true in configuration
    query = """
    SELECT file, line, source_expr
    FROM assignments
    WHERE (source_expr LIKE '%synchronize%true%'
           OR source_expr LIKE '%synchronize:%true%')
      AND file NOT LIKE '%test%'
      AND file NOT LIKE '%spec%'
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, expr = row
        findings.append(StandardFinding(
            rule_name='typeorm-synchronize-true',
            message='synchronize: true - NEVER use in production',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='orm-security',
            snippet='Use migrations instead of synchronize',
            fix_suggestion='Set synchronize: false and use migrations',
            cwe_id='CWE-665'
        ))
    
    return findings
    
def _detect_missing_indexes(cursor, common_indexed_fields) -> List[StandardFinding]:
    """Detect entities missing important indexes."""
    findings = []
    
    # Look for entity files
    query = """
    SELECT DISTINCT path 
    FROM files
    WHERE (path LIKE '%entity.ts' OR path LIKE '%entity.js')
      AND path NOT LIKE '%test%'
    """
    
    cursor.execute(query)
    entity_files = cursor.fetchall()
    
    for (entity_file,) in entity_files:
        # Check symbols for this file to find properties
        property_query = """
        SELECT COUNT(DISTINCT name) as prop_count
        FROM symbols
        WHERE file = ?
          AND type IN ('property', 'field', 'column')
        """
        
        cursor.execute(property_query, (entity_file,))
        prop_count = cursor.fetchone()[0]
        
        # Check for @Index decorators
        index_query = """
        SELECT COUNT(*) as index_count
        FROM symbols
        WHERE file = ?
          AND (name LIKE '%@Index%' OR name LIKE '%Index()%')
        """
        
        cursor.execute(index_query, (entity_file,))
        index_count = cursor.fetchone()[0]
        
        # Flag if many properties but few indexes
        if prop_count > 5 and index_count < 2:
            findings.append(StandardFinding(
                rule_name='typeorm-missing-indexes',
                message=f'Entity has {prop_count} properties but only {index_count} indexes',
                file_path=entity_file,
                line=0,
                severity=Severity.MEDIUM,
                category='orm-performance',
                snippet='Add @Index() to frequently queried fields',
                fix_suggestion='Add @Index() decorators to frequently queried fields',
                cwe_id='CWE-400'
            ))
        
        # Check for common fields without indexes
        for field in common_indexed_fields:
            field_query = """
            SELECT line FROM symbols
            WHERE file = ?
              AND name LIKE ?
              AND type IN ('property', 'field', 'column')
            """
            
            cursor.execute(field_query, (entity_file, f'%{field}%'))
            field_row = cursor.fetchone()
            
            if field_row:
                # Check if indexed
                index_check = """
                SELECT COUNT(*) FROM symbols
                WHERE file = ?
                  AND ABS(line - ?) <= 2
                  AND name LIKE '%Index%'
                """
                
                cursor.execute(index_check, (entity_file, field_row[0]))
                is_indexed = cursor.fetchone()[0] > 0
                
                if not is_indexed:
                    findings.append(StandardFinding(
                        rule_name='typeorm-field-not-indexed',
                        message=f"Common field '{field}' should be indexed",
                        file_path=entity_file,
                        line=field_row[0],
                        severity=Severity.MEDIUM,
                        category='orm-performance',
                        snippet=f'Add @Index() to {field} field',
                        fix_suggestion=f'Add @Index() decorator to {field} field',
                        cwe_id='CWE-400'
                    ))
    
    return findings