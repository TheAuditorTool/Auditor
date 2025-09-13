"""SQL-based SQL safety analyzer.

This module detects SQL safety issues by querying the indexed database
instead of traversing AST structures.
"""

import sqlite3
import re
from typing import List, Dict, Any, Set
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


def detect_sql_safety_patterns(db_path: str) -> List[Dict[str, Any]]:
    """
    Detect SQL safety issues using SQL queries.
    
    This function queries the indexed database to find:
    - Transactions without rollback in error paths
    - Queries on potentially unindexed fields
    - Unbounded SELECT queries without LIMIT
    - Nested transactions (deadlock risk)
    - UPDATE/DELETE without WHERE clause
    - SELECT * usage
    
    Args:
        db_path: Path to the repo_index.db database
        
    Returns:
        List of security findings in StandardFinding format
    """
    findings = []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Pattern 1: Transactions without rollback in error handlers
        findings.extend(_find_transactions_without_rollback(cursor))
        
        # Pattern 2: Unbounded queries (SELECT without LIMIT)
        findings.extend(_find_unbounded_queries(cursor))
        
        # Pattern 3: Nested transactions
        findings.extend(_find_nested_transactions(cursor))
        
        # Pattern 4: UPDATE without WHERE clause
        findings.extend(_find_update_without_where(cursor))
        
        # Pattern 5: DELETE without WHERE clause
        findings.extend(_find_delete_without_where(cursor))
        
        # Pattern 6: SELECT * usage
        findings.extend(_find_select_star_queries(cursor))
        
        # Pattern 7: Queries on commonly unindexed fields
        findings.extend(_find_unindexed_field_queries(cursor))
        
        # Pattern 8: Large IN clauses
        findings.extend(_find_large_in_clauses(cursor))
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error detecting SQL safety patterns: {e}")
    
    return findings


def _find_transactions_without_rollback(cursor) -> List[Dict[str, Any]]:
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
                findings.append({
                    'rule_id': 'transaction-not-rolled-back',
                    'message': 'Transaction without rollback in error path',
                    'file': file,
                    'line': line,
                    'column': 0,
                    'severity': 'high',
                    'category': 'reliability',
                    'confidence': 'medium',
                    'description': 'Add rollback in except/catch or finally block to prevent locked transactions on errors.'
                })
    
    return findings


def _find_unbounded_queries(cursor) -> List[Dict[str, Any]]:
    """Find SELECT queries without LIMIT clause."""
    findings = []
    
    # Find SQL query strings in assignments and function calls
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%SELECT%'
          AND a.source_expr LIKE '%FROM%'
    """)
    
    select_queries = cursor.fetchall()
    
    for file, line, var, expr in select_queries:
        if expr:
            expr_upper = expr.upper()
            # Check if it has LIMIT or TOP
            if 'LIMIT' not in expr_upper and 'TOP' not in expr_upper:
                # Check if it's a COUNT query (which doesn't need LIMIT)
                if 'COUNT(' not in expr_upper and 'COUNT(*)' not in expr_upper:
                    findings.append({
                        'rule_id': 'unbounded-query',
                        'message': 'SELECT query without LIMIT clause',
                        'file': file,
                        'line': line,
                        'column': 0,
                        'severity': 'medium',
                        'category': 'performance',
                        'confidence': 'high',
                        'description': 'Add LIMIT to prevent memory issues with large result sets. Consider pagination for user-facing queries.'
                    })
    
    # Also check function call arguments
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%query%' OR f.callee_function LIKE '%execute%')
          AND f.argument_expr LIKE '%SELECT%'
          AND f.argument_expr LIKE '%FROM%'
    """)
    
    query_calls = cursor.fetchall()
    
    for file, line, func, args in query_calls:
        if args:
            args_upper = args.upper()
            if 'LIMIT' not in args_upper and 'TOP' not in args_upper:
                if 'COUNT(' not in args_upper:
                    findings.append({
                        'rule_id': 'unbounded-query',
                        'message': 'Database query without LIMIT clause',
                        'file': file,
                        'line': line,
                        'column': 0,
                        'severity': 'medium',
                        'category': 'performance',
                        'confidence': 'high',
                        'description': 'Consider adding LIMIT to prevent fetching entire tables into memory.'
                    })
    
    return findings


def _find_nested_transactions(cursor) -> List[Dict[str, Any]]:
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
                    findings.append({
                        'rule_id': 'nested-transaction',
                        'message': 'Nested transaction detected - potential deadlock risk',
                        'file': file,
                        'line': line2,
                        'column': 0,
                        'severity': 'high',
                        'category': 'reliability',
                        'confidence': 'medium',
                        'description': 'Avoid nested transactions. Use savepoints or restructure code to prevent deadlocks.'
                    })
    
    return findings


def _find_update_without_where(cursor) -> List[Dict[str, Any]]:
    """Find UPDATE statements without WHERE clause."""
    findings = []
    
    # Pattern for UPDATE without WHERE
    update_pattern = re.compile(r'\bUPDATE\s+\S+\s+SET\s+', re.IGNORECASE)
    
    # Check assignments containing UPDATE
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%UPDATE%'
          AND a.source_expr LIKE '%SET%'
    """)
    
    update_queries = cursor.fetchall()
    
    for file, line, var, expr in update_queries:
        if expr and update_pattern.search(expr):
            if 'WHERE' not in expr.upper():
                findings.append({
                    'rule_id': 'missing-where-clause-update',
                    'message': 'UPDATE without WHERE clause will affect ALL rows',
                    'file': file,
                    'line': line,
                    'column': 0,
                    'severity': 'critical',
                    'category': 'security',
                    'confidence': 'high',
                    'description': 'Add WHERE clause to target specific rows. Updating all rows is rarely intentional.'
                })
    
    # Check function calls with UPDATE
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_expr LIKE '%UPDATE%'
          AND f.argument_expr LIKE '%SET%'
    """)
    
    update_calls = cursor.fetchall()
    
    for file, line, func, args in update_calls:
        if args and update_pattern.search(args):
            if 'WHERE' not in args.upper():
                findings.append({
                    'rule_id': 'missing-where-clause-update',
                    'message': 'UPDATE query without WHERE clause - dangerous',
                    'file': file,
                    'line': line,
                    'column': 0,
                    'severity': 'critical',
                    'category': 'security',
                    'confidence': 'high',
                    'description': 'This will update every row in the table. Add WHERE clause or use explicit UPDATE ALL if intentional.'
                })
    
    return findings


def _find_delete_without_where(cursor) -> List[Dict[str, Any]]:
    """Find DELETE statements without WHERE clause."""
    findings = []
    
    # Pattern for DELETE without WHERE
    delete_pattern = re.compile(r'\bDELETE\s+FROM\s+\S+', re.IGNORECASE)
    
    # Check assignments containing DELETE
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%DELETE%'
          AND a.source_expr LIKE '%FROM%'
    """)
    
    delete_queries = cursor.fetchall()
    
    for file, line, var, expr in delete_queries:
        if expr and delete_pattern.search(expr):
            expr_upper = expr.upper()
            if 'WHERE' not in expr_upper and 'TRUNCATE' not in expr_upper:
                findings.append({
                    'rule_id': 'missing-where-clause-delete',
                    'message': 'DELETE without WHERE clause will delete ALL rows',
                    'file': file,
                    'line': line,
                    'column': 0,
                    'severity': 'critical',
                    'category': 'security',
                    'confidence': 'high',
                    'description': 'Add WHERE clause to target specific rows. Use TRUNCATE if you really want to delete all rows.'
                })
    
    # Check function calls with DELETE
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_expr LIKE '%DELETE%'
          AND f.argument_expr LIKE '%FROM%'
    """)
    
    delete_calls = cursor.fetchall()
    
    for file, line, func, args in delete_calls:
        if args and delete_pattern.search(args):
            args_upper = args.upper()
            if 'WHERE' not in args_upper and 'TRUNCATE' not in args_upper:
                findings.append({
                    'rule_id': 'missing-where-clause-delete',
                    'message': 'DELETE query without WHERE clause - will delete entire table',
                    'file': file,
                    'line': line,
                    'column': 0,
                    'severity': 'critical',
                    'category': 'security',
                    'confidence': 'high',
                    'description': 'This is equivalent to TRUNCATE. Add WHERE clause or use TRUNCATE TABLE if intentional.'
                })
    
    return findings


def _find_select_star_queries(cursor) -> List[Dict[str, Any]]:
    """Find SELECT * usage."""
    findings = []
    
    # Pattern for SELECT *
    select_star_pattern = re.compile(r'SELECT\s+\*\s+FROM', re.IGNORECASE)
    
    # Check assignments
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%SELECT%*%FROM%'
           OR a.source_expr LIKE '%SELECT *%'
    """)
    
    select_star_queries = cursor.fetchall()
    
    for file, line, var, expr in select_star_queries:
        if expr and select_star_pattern.search(expr):
            findings.append({
                'rule_id': 'select-star-query',
                'message': 'SELECT * query - specify needed columns',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'low',
                'category': 'performance',
                'confidence': 'high',
                'description': 'List specific columns for better performance, reduced network traffic, and protection against schema changes.'
            })
    
    # Check function calls
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.argument_expr LIKE '%SELECT%*%FROM%'
           OR f.argument_expr LIKE '%SELECT *%'
    """)
    
    select_star_calls = cursor.fetchall()
    
    for file, line, func, args in select_star_calls:
        if args and select_star_pattern.search(args):
            findings.append({
                'rule_id': 'select-star-query',
                'message': 'Avoid SELECT * in production code',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'low',
                'category': 'performance',
                'confidence': 'high',
                'description': 'Explicitly list columns to improve query performance and maintainability.'
            })
    
    return findings


def _find_unindexed_field_queries(cursor) -> List[Dict[str, Any]]:
    """Find queries on commonly unindexed fields (heuristic)."""
    findings = []
    
    # Common fields that are often not indexed
    common_unindexed = [
        'email', 'username', 'user_id', 'created_at', 'updated_at', 
        'status', 'type', 'category', 'description', 'name'
    ]
    
    # Check WHERE clauses
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%WHERE%'
          AND (a.source_expr LIKE '%SELECT%' OR a.source_expr LIKE '%UPDATE%' OR a.source_expr LIKE '%DELETE%')
    """)
    
    where_queries = cursor.fetchall()
    
    for file, line, expr in where_queries:
        if expr:
            expr_lower = expr.lower()
            for field in common_unindexed:
                # Look for patterns like WHERE field = or WHERE field IN
                if f'where {field}' in expr_lower or f'where {field} ' in expr_lower:
                    findings.append({
                        'rule_id': 'missing-db-index-hint',
                        'message': f'Query on potentially unindexed field: {field}',
                        'file': file,
                        'line': line,
                        'column': 0,
                        'severity': 'medium',
                        'category': 'performance',
                        'confidence': 'low',
                        'description': f'Consider adding index on {field} if queries are slow. Use EXPLAIN to verify.'
                    })
                    break
    
    return findings


def _find_large_in_clauses(cursor) -> List[Dict[str, Any]]:
    """Find queries with large IN clauses that could be inefficient."""
    findings = []
    
    # Pattern for IN clause with many values
    in_pattern = re.compile(r'\bIN\s*\([^)]{100,}\)', re.IGNORECASE)
    
    # Check assignments
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%IN (%'
          AND LENGTH(a.source_expr) > 200
    """)
    
    in_queries = cursor.fetchall()
    
    for file, line, expr in in_queries:
        if expr and in_pattern.search(expr):
            # Count commas to estimate number of values
            in_match = in_pattern.search(expr)
            if in_match:
                in_clause = in_match.group()
                comma_count = in_clause.count(',')
                if comma_count > 10:
                    findings.append({
                        'rule_id': 'large-in-clause',
                        'message': f'Large IN clause with ~{comma_count + 1} values',
                        'file': file,
                        'line': line,
                        'column': 0,
                        'severity': 'medium',
                        'category': 'performance',
                        'confidence': 'high',
                        'description': 'Consider using a temporary table or JOIN instead of large IN clauses for better performance.'
                    })
    
    return findings


def register_taint_patterns(taint_registry):
    """Register SQL-related patterns with the taint analysis registry.
    
    This maintains compatibility with the taint analyzer.
    """
    # SQL execution functions as sinks
    SQL_EXECUTION_SINKS = [
        "execute", "executemany", "query", "exec", "execSQL",
        "db.query", "db.execute", "cursor.execute",
        "sequelize.query", "knex.raw", "pool.query"
    ]
    
    for pattern in SQL_EXECUTION_SINKS:
        taint_registry.register_sink(pattern, "sql", "any")
    
    # Transaction operations
    TRANSACTION_SINKS = [
        "begin", "start_transaction", "commit", "rollback",
        "BEGIN", "COMMIT", "ROLLBACK"
    ]
    
    for pattern in TRANSACTION_SINKS:
        taint_registry.register_sink(pattern, "transaction", "any")


def find_sql_safety_issues(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """
    Compatibility wrapper for AST-based callers.
    
    This function is called by universal_detector but we ignore the AST tree
    and query the database instead.
    """
    # This would need access to the database path
    # In real implementation, this would be configured
    return []


# For direct CLI usage
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        findings = detect_sql_safety_patterns(db_path)
        for finding in findings:
            print(f"{finding['file']}:{finding['line']} - {finding['message']}")