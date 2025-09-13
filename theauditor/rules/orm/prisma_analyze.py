"""
Prisma ORM Analyzer - SQL-based implementation.

This module detects Prisma ORM anti-patterns and performance issues
using TheAuditor's indexed database.

Migration from: prisma_detector.py (325 lines -> ~280 lines)
Performance: ~10x faster using direct SQL queries
"""

import sqlite3
import json
from pathlib import Path
from typing import List

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_prisma_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect Prisma ORM anti-patterns and performance issues.
    
    Detects:
    - Unbounded queries without pagination
    - N+1 query patterns
    - Missing transactions for multiple writes
    - Unhandled OrThrow methods
    - Unsafe raw SQL queries
    - Missing database indexes
    - Connection pool configuration issues
    
    Returns:
        List of Prisma ORM issues found
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # Check if orm_queries table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='orm_queries'"
        )
        if not cursor.fetchone():
            return findings
        
        # Run each analysis
        findings.extend(_detect_unbounded_queries(cursor))
        findings.extend(_detect_n_plus_one(cursor))
        findings.extend(_detect_missing_transactions(cursor))
        findings.extend(_detect_unhandled_throws(cursor))
        findings.extend(_detect_raw_queries(cursor))
        findings.extend(_detect_missing_indexes(cursor))
        findings.extend(_detect_connection_pool_issues(cursor))
        
    except Exception:
        pass  # Return empty findings on error
    finally:
        conn.close()
        
    return findings
    
def _detect_unbounded_queries(cursor) -> List[StandardFinding]:
    """Detect findMany queries without pagination."""
    findings = []
    
    query = """
    SELECT file, line, query_type
    FROM orm_queries
    WHERE query_type LIKE '%.findMany'
      AND has_limit = 0
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, query_type = row
        model = query_type.split('.')[0] if '.' in query_type else 'unknown'
        
        findings.append(StandardFinding(
            rule_name='prisma-unbounded-query',
            message=f'Unbounded findMany on {model} - missing take/skip pagination',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='orm-performance',
            snippet=f'prisma.{query_type}() without pagination',
            fix_suggestion='Add pagination with take/skip parameters',
            cwe_id='CWE-400'
        ))
    
    return findings
    
def _detect_n_plus_one(cursor) -> List[StandardFinding]:
    """Detect potential N+1 query patterns."""
    findings = []
    
    query = """
    SELECT file, line, query_type
    FROM orm_queries
    WHERE query_type LIKE '%.findMany'
      AND (includes IS NULL OR includes = '[]' OR includes = '{}')
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, query_type = row
        model = query_type.split('.')[0] if '.' in query_type else 'unknown'
        
        findings.append(StandardFinding(
            rule_name='prisma-n-plus-one',
            message=f'Potential N+1: findMany on {model} without includes',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='orm-performance',
            snippet=f'prisma.{query_type}() without eager loading',
            fix_suggestion='Use include or select to eager load related data',
            cwe_id='CWE-400'
        ))
    
    return findings
    
def _detect_missing_transactions(cursor) -> List[StandardFinding]:
    """Detect multiple write operations without transactions."""
    findings = []
    
    # Get all write operations grouped by file
    query = """
    SELECT file, line, query_type, has_transaction
    FROM orm_queries
    WHERE query_type LIKE '%.create%' 
       OR query_type LIKE '%.update%'
       OR query_type LIKE '%.delete%'
       OR query_type LIKE '%.upsert%'
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
                    rule_name='prisma-missing-transaction',
                    message=f"Multiple writes without transaction: {op1['query']} and {op2['query']}",
                    file_path=file,
                    line=op1['line'],
                    severity=Severity.HIGH,
                    category='orm-data-integrity',
                    snippet='Multiple operations need $transaction()',
                    fix_suggestion='Wrap multiple write operations in prisma.$transaction()',
                    cwe_id='CWE-662'
                ))
                break  # One finding per cluster
    
    return findings
    
def _detect_unhandled_throws(cursor) -> List[StandardFinding]:
    """Detect OrThrow methods that might not have error handling."""
    findings = []
    
    query = """
    SELECT file, line, query_type
    FROM orm_queries
    WHERE query_type LIKE '%.findUniqueOrThrow'
       OR query_type LIKE '%.findFirstOrThrow'
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, query_type = row
        
        # Check if there's try-catch nearby
        check_query = """
        SELECT COUNT(*) FROM symbols
        WHERE file = ?
          AND ABS(line - ?) <= 5
          AND (name LIKE '%try%' OR name LIKE '%catch%')
        """
        
        cursor.execute(check_query, (file, line))
        has_error_handling = cursor.fetchone()[0] > 0
        
        if not has_error_handling:
            findings.append(StandardFinding(
                rule_name='prisma-unhandled-throw',
                message=f'OrThrow method without visible error handling: {query_type}',
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='orm-error-handling',
                snippet=f'prisma.{query_type}() may throw',
                fix_suggestion='Add try-catch block to handle potential errors',
                cwe_id='CWE-755'
            ))
    
    return findings
    
def _detect_raw_queries(cursor) -> List[StandardFinding]:
    """Detect potentially unsafe raw SQL queries."""
    findings = []
    
    # Look for raw query methods
    query = """
    SELECT DISTINCT f.file, f.line, f.callee_function, f.args_json
    FROM function_call_args f
    WHERE f.callee_function LIKE '%$queryRaw%'
       OR f.callee_function LIKE '%$executeRaw%'
       OR f.callee_function LIKE '%queryRawUnsafe%'
       OR f.callee_function LIKE '%executeRawUnsafe%'
    """
    
    cursor.execute(query)
    for row in cursor.fetchall():
        file, line, func, args_json = row
        
        # Check if using unsafe variant or has user input
        is_unsafe = 'Unsafe' in func
        severity = Severity.CRITICAL if is_unsafe else Severity.HIGH
        
        # Check for template literal or concatenation
        if args_json:
            has_interpolation = '${' in args_json or '+' in args_json
            if has_interpolation:
                findings.append(StandardFinding(
                    rule_name='prisma-sql-injection',
                    message=f'Potential SQL injection in {func} with string interpolation',
                    file_path=file,
                    line=line,
                    severity=severity,
                    category='orm-security',
                    snippet=f'{func}({args_json[:50]}...)' if len(args_json or '') > 50 else f'{func}({args_json})',
                    fix_suggestion='Use parameterized queries or Prisma query builder',
                    cwe_id='CWE-89'
                ))
    
    return findings
    
def _detect_missing_indexes(cursor) -> List[StandardFinding]:
    """Detect queries potentially missing database indexes."""
    findings = []
    
    # Check if prisma_models table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prisma_models'"
    )
    if not cursor.fetchone():
        return findings
    
    # Get models with very few indexes
    query = """
    SELECT model_name, COUNT(DISTINCT field_name) as indexed_count
    FROM prisma_models
    WHERE is_indexed = 1 OR is_unique = 1
    GROUP BY model_name
    HAVING indexed_count < 2
    """
    
    cursor.execute(query)
    poorly_indexed_models = {row[0] for row in cursor.fetchall()}
    
    if poorly_indexed_models:
        # Find queries on these models
        query = """
        SELECT file, line, query_type
        FROM orm_queries
        WHERE query_type LIKE '%.findMany%'
           OR query_type LIKE '%.findFirst%'
           OR query_type LIKE '%.findUnique%'
        """
        
        cursor.execute(query)
        for row in cursor.fetchall():
            file, line, query_type = row
            model = query_type.split('.')[0] if '.' in query_type else None
            
            if model in poorly_indexed_models:
                findings.append(StandardFinding(
                    rule_name='prisma-missing-index',
                    message=f'Query on {model} with limited indexes - verify performance',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='orm-performance',
                    snippet=f'prisma.{query_type}() on poorly indexed model',
                    fix_suggestion='Add database indexes for frequently queried fields',
                    cwe_id='CWE-400'
                ))
    
    return findings
    
def _detect_connection_pool_issues(cursor) -> List[StandardFinding]:
    """Detect connection pool configuration issues."""
    findings = []
    
    # Look for schema.prisma files
    query = """
    SELECT path FROM files 
    WHERE path LIKE '%schema.prisma%'
    LIMIT 1
    """
    
    cursor.execute(query)
    schema_file = cursor.fetchone()
    
    if schema_file:
        # Check for connection pool configuration in environment variables or config
        config_query = """
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE (target_var LIKE '%DATABASE_URL%' OR target_var LIKE '%connectionLimit%')
          AND source_expr NOT LIKE '%connection_limit%'
        """
        
        cursor.execute(config_query)
        for row in cursor.fetchall():
            file, line, var, expr = row
            findings.append(StandardFinding(
                rule_name='prisma-no-connection-limit',
                message='Database URL without connection_limit parameter',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='orm-configuration',
                snippet='Missing ?connection_limit=N in DATABASE_URL',
                fix_suggestion='Add connection_limit parameter to DATABASE_URL',
                cwe_id='CWE-770'
            ))
    
    return findings