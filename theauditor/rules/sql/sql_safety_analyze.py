"""SQL Safety Analyzer - Pure Database Implementation.

This module detects SQL safety issues using ONLY indexed database data.
NO AST TRAVERSAL. NO FILE I/O. Just efficient SQL queries against the sql_queries table.

The sql_queries table contains 4,723 actual SQL queries with:
- file_path: Where the query is located
- line_number: Line in source file
- query_text: The actual SQL query text
- command: Type of query (SELECT, INSERT, UPDATE, DELETE)
- tables: Tables referenced in the query
"""

import sqlite3
from typing import List
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_sql_safety_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect SQL safety issues using indexed SQL queries.
    
    Returns:
        List of SQL safety findings
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # First check if we have SQL queries indexed
        cursor.execute("SELECT COUNT(*) FROM sql_queries")
        query_count = cursor.fetchone()[0]
        
        if query_count == 0:
            # No SQL queries indexed, fallback to function call analysis
            findings.extend(_find_safety_issues_in_function_calls(cursor))
        else:
            # Primary analysis using actual SQL queries
            findings.extend(_find_update_without_where(cursor))
            findings.extend(_find_delete_without_where(cursor))
            findings.extend(_find_select_star_queries(cursor))
            findings.extend(_find_unbounded_queries(cursor))
            findings.extend(_find_large_in_clauses(cursor))
            findings.extend(_find_missing_transactions(cursor))
            findings.extend(_find_inefficient_joins(cursor))
            findings.extend(_find_n_plus_one_queries(cursor))
        
        # Secondary analysis using function calls and symbols
        findings.extend(_find_transactions_without_rollback(cursor))
        findings.extend(_find_nested_transactions(cursor))
        findings.extend(_find_connection_leaks(cursor))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# PRIMARY DETECTION: Using sql_queries table
# ============================================================================

def _find_update_without_where(cursor) -> List[StandardFinding]:
    """Find UPDATE statements without WHERE clause in actual SQL queries."""
    findings = []
    seen_files = set()
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE command = 'UPDATE'
          AND (file_path LIKE '%backend%' OR file_path LIKE '%server%' OR file_path LIKE '%api%')
          AND file_path NOT LIKE '%frontend%'
          AND file_path NOT LIKE '%.tsx'
          AND file_path NOT LIKE '%.jsx'
          AND query_text NOT LIKE '%WHERE%'
          AND query_text NOT LIKE '%where%'
        ORDER BY file_path, line_number
        LIMIT 10
    """)
    
    for file, line, query, command in cursor.fetchall():
        # Dedupe by file
        if file in seen_files:
            continue
        seen_files.add(file)
        
        # Double-check it's really missing WHERE
        query_upper = query.upper()
        if 'WHERE' not in query_upper:
            findings.append(StandardFinding(
                rule_name='sql-safety-update-no-where',
                message='UPDATE without WHERE clause will affect ALL rows',
                file_path=file,
                line=line,
                severity=Severity.HIGH,  # Not always critical
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                cwe_id='CWE-89'
            ))
    
    return findings


def _find_delete_without_where(cursor) -> List[StandardFinding]:
    """Find DELETE statements without WHERE clause in actual SQL queries."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE command = 'DELETE'
          AND query_text NOT LIKE '%WHERE%'
          AND query_text NOT LIKE '%where%'
          AND query_text NOT LIKE '%TRUNCATE%'
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command in cursor.fetchall():
        # Double-check it's really missing WHERE
        query_upper = query.upper()
        if 'WHERE' not in query_upper and 'TRUNCATE' not in query_upper:
            findings.append(StandardFinding(
                rule_name='sql-safety-delete-no-where',
                message='DELETE without WHERE clause will delete ALL rows',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                cwe_id='CWE-89'
            ))
    
    return findings


def _find_select_star_queries(cursor) -> List[StandardFinding]:
    """Find SELECT * usage in actual SQL queries."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, command, tables
        FROM sql_queries
        WHERE command = 'SELECT'
          AND (query_text LIKE '%SELECT *%'
               OR query_text LIKE '%select *%'
               OR query_text LIKE '%SELECT%*%FROM%')
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command, tables in cursor.fetchall():
        # Check if it's really SELECT *
        query_upper = query.upper()
        if 'SELECT *' in query_upper or 'SELECT\t*' in query_upper.replace(' ', '\t'):
            # Check table size hint from tables column
            table_list = tables.split(',') if tables else []
            severity = Severity.MEDIUM if len(table_list) > 1 else Severity.LOW
            
            findings.append(StandardFinding(
                rule_name='sql-safety-select-star',
                message='SELECT * query - specify needed columns for better performance',
                file_path=file,
                line=line,
                severity=severity,
                category='performance',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                cwe_id='CWE-770'
            ))
    
    return findings


def _find_unbounded_queries(cursor) -> List[StandardFinding]:
    """Find SELECT queries without LIMIT clause in actual SQL queries."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, command, tables
        FROM sql_queries
        WHERE command = 'SELECT'
          AND query_text NOT LIKE '%LIMIT%'
          AND query_text NOT LIKE '%limit%'
          AND query_text NOT LIKE '%TOP%'
          AND query_text NOT LIKE '%COUNT(%'
          AND query_text NOT LIKE '%MAX(%'
          AND query_text NOT LIKE '%MIN(%'
          AND query_text NOT LIKE '%SUM(%'
          AND query_text NOT LIKE '%AVG(%'
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command, tables in cursor.fetchall():
        query_upper = query.upper()
        # Skip aggregate queries
        if not any(agg in query_upper for agg in ['COUNT(', 'MAX(', 'MIN(', 'SUM(', 'AVG(', 'GROUP BY']):
            # Check if it's a potentially large result set
            if 'JOIN' in query_upper or (tables and ',' in tables):
                severity = Severity.HIGH  # Joins without LIMIT are dangerous
            else:
                severity = Severity.MEDIUM
            
            findings.append(StandardFinding(
                rule_name='sql-safety-unbounded-query',
                message='SELECT query without LIMIT - potential memory issue with large datasets',
                file_path=file,
                line=line,
                severity=severity,
                category='performance',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                cwe_id='CWE-770'
            ))
    
    return findings


def _find_large_in_clauses(cursor) -> List[StandardFinding]:
    """Find queries with large IN clauses that could be inefficient."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE (query_text LIKE '%IN (%' OR query_text LIKE '%in (%')
          AND LENGTH(query_text) > 200
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command in cursor.fetchall():
        # Count items in IN clause
        query_upper = query.upper()
        in_pos = query_upper.find(' IN (')
        if in_pos != -1:
            # Extract the IN clause content
            paren_start = in_pos + 4
            paren_count = 1
            pos = paren_start + 1
            while pos < len(query) and paren_count > 0:
                if query[pos] == '(':
                    paren_count += 1
                elif query[pos] == ')':
                    paren_count -= 1
                pos += 1
            
            if pos > paren_start:
                in_content = query[paren_start:pos-1]
                # Count commas to estimate values
                comma_count = in_content.count(',')
                
                if comma_count > 50:
                    severity = Severity.HIGH
                    threshold = "50+"
                elif comma_count > 20:
                    severity = Severity.MEDIUM
                    threshold = "20+"
                elif comma_count > 10:
                    severity = Severity.LOW
                    threshold = "10+"
                else:
                    continue
                
                findings.append(StandardFinding(
                    rule_name='sql-safety-large-in-clause',
                    message=f'{command} query with large IN clause ({comma_count + 1} values)',
                    file_path=file,
                    line=line,
                    severity=severity,
                    category='performance',
                    snippet=query[:100] + '...' if len(query) > 100 else query,
                    cwe_id='CWE-770'
                ))
    
    return findings


def _find_missing_transactions(cursor) -> List[StandardFinding]:
    """Find multiple DML operations without transaction boundaries."""
    findings = []
    
    # Find files with multiple UPDATE/DELETE/INSERT operations
    cursor.execute("""
        SELECT file_path, COUNT(*) as dml_count
        FROM sql_queries
        WHERE command IN ('UPDATE', 'DELETE', 'INSERT')
        GROUP BY file_path
        HAVING COUNT(*) > 3
        ORDER BY dml_count DESC
    """)
    
    high_dml_files = cursor.fetchall()
    
    for file, dml_count in high_dml_files:
        # Check if this file has transaction management
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args
            WHERE file = ?
              AND (callee_function LIKE '%begin%'
                   OR callee_function LIKE '%transaction%'
                   OR callee_function LIKE '%commit%')
        """, (file,))
        
        has_transactions = cursor.fetchone()[0] > 0
        
        if not has_transactions and dml_count > 5:
            # Get sample line for reporting
            cursor.execute("""
                SELECT MIN(line_number)
                FROM sql_queries
                WHERE file_path = ?
                  AND command IN ('UPDATE', 'DELETE', 'INSERT')
            """, (file,))
            
            first_line = cursor.fetchone()[0]
            
            findings.append(StandardFinding(
                rule_name='sql-safety-missing-transaction',
                message=f'File has {dml_count} DML operations without transaction management',
                file_path=file,
                line=first_line,
                severity=Severity.HIGH,
                category='reliability',
                snippet=f'{dml_count} UPDATE/DELETE/INSERT operations',
                cwe_id='CWE-667'
            ))
    
    return findings


def _find_inefficient_joins(cursor) -> List[StandardFinding]:
    """Find queries with multiple JOINs that might be inefficient."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, tables
        FROM sql_queries
        WHERE command = 'SELECT'
          AND (query_text LIKE '%JOIN%JOIN%JOIN%'
               OR query_text LIKE '%join%join%join%')
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, tables in cursor.fetchall():
        # Count number of JOINs
        query_upper = query.upper()
        join_count = query_upper.count(' JOIN ') + query_upper.count(' LEFT JOIN ') + query_upper.count(' RIGHT JOIN ') + query_upper.count(' INNER JOIN ')
        
        if join_count >= 5:
            severity = Severity.HIGH
            message = f'Query with {join_count} JOINs - likely performance issue'
        elif join_count >= 3:
            severity = Severity.MEDIUM
            message = f'Query with {join_count} JOINs - consider optimization'
        else:
            continue
        
        findings.append(StandardFinding(
            rule_name='sql-safety-excessive-joins',
            message=message,
            file_path=file,
            line=line,
            severity=severity,
            category='performance',
            snippet=query[:100] + '...' if len(query) > 100 else query,
            cwe_id='CWE-770'
        ))
    
    return findings


def _find_n_plus_one_queries(cursor) -> List[StandardFinding]:
    """Find potential N+1 query patterns."""
    findings = []
    
    # Look for files with many similar SELECT queries
    cursor.execute("""
        SELECT file_path, tables, COUNT(*) as query_count, MIN(line_number) as first_line
        FROM sql_queries
        WHERE command = 'SELECT'
          AND tables IS NOT NULL
          AND tables != ''
        GROUP BY file_path, tables
        HAVING COUNT(*) > 5
        ORDER BY query_count DESC
    """)
    
    for file, tables, count, first_line in cursor.fetchall():
        # Check if these queries are in close proximity (likely in a loop)
        cursor.execute("""
            SELECT line_number
            FROM sql_queries
            WHERE file_path = ?
              AND command = 'SELECT'
              AND tables = ?
            ORDER BY line_number
            LIMIT 10
        """, (file, tables))
        
        lines = [row[0] for row in cursor.fetchall()]
        
        # Check if lines are close together (within 50 lines)
        if len(lines) >= 3:
            max_gap = max(lines[i+1] - lines[i] for i in range(len(lines)-1))
            
            if max_gap < 50:  # Queries are close together, likely in a loop
                findings.append(StandardFinding(
                    rule_name='sql-safety-n-plus-one',
                    message=f'Potential N+1 query pattern: {count} similar SELECT queries on {tables}',
                    file_path=file,
                    line=first_line,
                    severity=Severity.HIGH,
                    category='performance',
                    snippet=f'{count} SELECT queries on table: {tables}',
                    cwe_id='CWE-770'
                ))
    
    return findings


# ============================================================================
# SECONDARY DETECTION: Using function_call_args and symbols
# ============================================================================

def _find_safety_issues_in_function_calls(cursor) -> List[StandardFinding]:
    """Fallback detection using function calls when sql_queries is empty."""
    findings = []
    
    # Find execute/query calls with dangerous patterns
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%execute%'
               OR f.callee_function LIKE '%query%')
          AND (f.argument_expr LIKE '%UPDATE%SET%'
               OR f.argument_expr LIKE '%DELETE%FROM%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        if args:
            args_upper = args.upper()
            if 'UPDATE' in args_upper and 'WHERE' not in args_upper:
                findings.append(StandardFinding(
                    rule_name='sql-safety-update-no-where-fallback',
                    message='UPDATE without WHERE clause detected',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                    cwe_id='CWE-89'
                ))
            elif 'DELETE' in args_upper and 'WHERE' not in args_upper:
                findings.append(StandardFinding(
                    rule_name='sql-safety-delete-no-where-fallback',
                    message='DELETE without WHERE clause detected',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                    cwe_id='CWE-89'
                ))
    
    return findings


def _find_transactions_without_rollback(cursor) -> List[StandardFinding]:
    """Find transactions that lack rollback in error handlers."""
    findings = []
    
    # Transaction start patterns
    transaction_patterns = [
        'begin', 'start_transaction', 'begin_transaction', 'beginTransaction',
        'START TRANSACTION', 'BEGIN', 'autocommit(False)', 'autocommit(0)'
    ]
    
    # Find transaction starts
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE ({})
        ORDER BY f.file, f.line
    """.format(' OR '.join([f"f.callee_function LIKE '%{pattern}%'" for pattern in transaction_patterns])))
    
    transactions = cursor.fetchall()
    
    for file, line, func, args in transactions:
        # Check if there's error handling nearby (try/catch/finally)
        # Look for rollback within ±50 lines
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args f2
            WHERE f2.file = ?
              AND f2.line BETWEEN ? AND ?
              AND f2.callee_function LIKE '%rollback%'
        """, (file, line, line + 50))
        
        has_rollback = cursor.fetchone()[0] > 0
        
        if not has_rollback:
            # Check if there's a try block structure nearby
            cursor.execute("""
                SELECT COUNT(*)
                FROM symbols s
                WHERE s.file = ?
                  AND s.line BETWEEN ? AND ?
                  AND (s.name LIKE '%except%' OR s.name LIKE '%catch%' OR s.name LIKE '%finally%')
            """, (file, line - 10, line + 50))
            
            has_error_handling = cursor.fetchone()[0] > 0
            
            if has_error_handling:
                findings.append(StandardFinding(
                    rule_name='transaction-not-rolled-back',
                    message='Transaction without rollback in error path',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='reliability',
                    snippet=f'{func}()',
                    cwe_id='CWE-667'
                ))
    
    return findings


def _find_nested_transactions(cursor) -> List[StandardFinding]:
    """Find nested transaction starts that could cause deadlocks."""
    findings = []
    
    transaction_patterns = ['begin', 'start_transaction', 'beginTransaction', 'BEGIN', 'START TRANSACTION']
    
    # Get all transaction starts grouped by file
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE ({})
        ORDER BY f.file, f.line
    """.format(' OR '.join([f"f.callee_function LIKE '%{pattern}%'" for pattern in transaction_patterns])))
    
    transactions = cursor.fetchall()
    
    # Group by file
    file_transactions = {}
    for file, line, func in transactions:
        if file not in file_transactions:
            file_transactions[file] = []
        file_transactions[file].append((line, func))
    
    # Check for nested transactions (multiple starts without commits between)
    for file, trans_list in file_transactions.items():
        if len(trans_list) > 1:
            for i in range(len(trans_list) - 1):
                line1, func1 = trans_list[i]
                line2, func2 = trans_list[i + 1]
                
                # Check if there's a commit between them
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM function_call_args f
                    WHERE f.file = ?
                      AND f.line > ? AND f.line < ?
                      AND (f.callee_function LIKE '%commit%' OR f.callee_function LIKE '%rollback%')
                """, (file, line1, line2))
                
                has_commit_between = cursor.fetchone()[0] > 0
                
                if not has_commit_between and (line2 - line1) < 100:  # Within 100 lines
                    findings.append(StandardFinding(
                        rule_name='nested-transaction',
                        message='Nested transaction detected - potential deadlock risk',
                        file_path=file,
                        line=line2,
                        severity=Severity.HIGH,
                        category='reliability',
                        snippet=f'{func2}()',
                        cwe_id='CWE-667'
                    ))
    
    return findings


def _find_connection_leaks(cursor) -> List[StandardFinding]:
    """Find potential database connection leaks."""
    findings = []
    
    # Find connection opens without corresponding closes
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.callee_function LIKE '%connect%'
           OR f.callee_function LIKE '%createConnection%'
           OR f.callee_function LIKE '%getConnection%'
        ORDER BY f.file, f.line
    """)
    
    connections = cursor.fetchall()
    
    for file, line, func in connections:
        # Check if there's a close/end/release within reasonable distance
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args f2
            WHERE f2.file = ?
              AND f2.line BETWEEN ? AND ?
              AND (f2.callee_function LIKE '%close%'
                   OR f2.callee_function LIKE '%end%'
                   OR f2.callee_function LIKE '%release%'
                   OR f2.callee_function LIKE '%destroy%')
        """, (file, line, line + 100))
        
        has_close = cursor.fetchone()[0] > 0
        
        if not has_close:
            # Check for using/with context manager patterns
            cursor.execute("""
                SELECT COUNT(*)
                FROM symbols s
                WHERE s.file = ?
                  AND s.line BETWEEN ? AND ?
                  AND (s.name LIKE '%with%' OR s.name LIKE '%using%')
            """, (file, line - 2, line + 2))
            
            has_context_manager = cursor.fetchone()[0] > 0
            
            if not has_context_manager:
                findings.append(StandardFinding(
                    rule_name='sql-safety-connection-leak',
                    message='Database connection opened but not closed',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='reliability',
                    snippet=f'{func}()',
                    cwe_id='CWE-404'
                ))
    
    return findings


