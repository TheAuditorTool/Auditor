"""SQL-based SQL injection vulnerability detector.

This module detects SQL injection vulnerabilities by querying the indexed database
instead of traversing AST structures.
"""

import sqlite3
from typing import List, Dict, Any, Set
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


def detect_sql_injection_patterns(db_path: str) -> List[Dict[str, Any]]:
    """
    Detect SQL injection vulnerabilities using SQL queries.
    
    This function queries the indexed database to find:
    - String formatting in SQL queries (.format, %, f-strings)
    - Direct concatenation in SQL queries (+ operator)
    - Unsafe query construction patterns
    - Missing parameterization in database operations
    
    Args:
        db_path: Path to the repo_index.db database
        
    Returns:
        List of security findings in StandardFinding format
    """
    findings = []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Pattern 1: String formatting with .format() containing SQL
        findings.extend(_find_format_sql_injection(cursor))
        
        # Pattern 2: F-strings with SQL queries
        findings.extend(_find_fstring_sql_injection(cursor))
        
        # Pattern 3: String concatenation in SQL queries
        findings.extend(_find_concatenation_sql_injection(cursor))
        
        # Pattern 4: % formatting with SQL
        findings.extend(_find_percent_sql_injection(cursor))
        
        # Pattern 5: Direct user input in execute() calls
        findings.extend(_find_direct_input_sql_injection(cursor))
        
        # Pattern 6: Dynamic query construction
        findings.extend(_find_dynamic_query_construction(cursor))
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error detecting SQL injection patterns: {e}")
    
    return findings


def _find_format_sql_injection(cursor) -> List[Dict[str, Any]]:
    """Find SQL queries using .format() string formatting."""
    findings = []
    
    # SQL keywords to detect
    sql_keywords = [
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 
        'ALTER', 'EXEC', 'EXECUTE', 'FROM', 'WHERE', 'JOIN'
    ]
    
    # Find .format() calls
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%.format%'
    """)
    
    format_calls = cursor.fetchall()
    
    for file, line, func, args in format_calls:
        if not args:
            continue
            
        # Check if the string being formatted contains SQL keywords
        args_upper = args.upper() if args else ""
        contains_sql = any(keyword in args_upper for keyword in sql_keywords)
        
        if contains_sql:
            findings.append({
                'rule_id': 'sql-injection-format',
                'message': 'SQL query using .format() string formatting - vulnerable to injection',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'critical',
                'category': 'security',
                'confidence': 'high',
                'description': 'Use parameterized queries instead of string formatting. Never construct SQL queries with .format().'
            })
    
    # Also check assignments that might be SQL queries
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%.format(%'
          AND ({})
    """.format(' OR '.join([f"a.source_expr LIKE '%{kw}%'" for kw in sql_keywords])))
    
    formatted_assignments = cursor.fetchall()
    
    for file, line, var, expr in formatted_assignments:
        findings.append({
            'rule_id': 'sql-injection-format',
            'message': f'SQL query "{var}" constructed with .format() - injection risk',
            'file': file,
            'line': line,
            'column': 0,
            'severity': 'critical',
            'category': 'security',
            'confidence': 'high',
            'description': 'String formatting in SQL query construction. Use parameterized queries with ? or %s placeholders.'
        })
    
    return findings


def _find_fstring_sql_injection(cursor) -> List[Dict[str, Any]]:
    """Find SQL queries using f-strings."""
    findings = []
    
    sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE']
    
    # F-strings are harder to detect from database, look for patterns
    # Check assignments with f-string patterns and SQL keywords
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE 'f"%' OR a.source_expr LIKE "f'%")
          AND ({})
    """.format(' OR '.join([f"a.source_expr LIKE '%{kw}%'" for kw in sql_keywords])))
    
    fstring_queries = cursor.fetchall()
    
    for file, line, var, expr in fstring_queries:
        findings.append({
            'rule_id': 'sql-injection-fstring',
            'message': f'SQL query using f-string - extremely dangerous for injection',
            'file': file,
            'line': line,
            'column': 0,
            'severity': 'critical',
            'category': 'security',
            'confidence': 'high',
            'description': 'Never use f-strings for SQL queries. Use parameterized queries with placeholders.'
        })
    
    return findings


def _find_concatenation_sql_injection(cursor) -> List[Dict[str, Any]]:
    """Find SQL queries using string concatenation."""
    findings = []
    
    sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE']
    
    # Find assignments with SQL keywords and + operator
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%+%'
          AND ({})
    """.format(' OR '.join([f"a.source_expr LIKE '%{kw}%'" for kw in sql_keywords])))
    
    concatenated_queries = cursor.fetchall()
    
    for file, line, var, expr in concatenated_queries:
        # Check if it's likely string concatenation (has quotes)
        if '"' in expr or "'" in expr:
            findings.append({
                'rule_id': 'sql-injection-concatenation',
                'message': 'SQL query using string concatenation - vulnerable to injection',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'critical',
                'category': 'security',
                'confidence': 'high',
                'description': 'String concatenation in SQL queries is dangerous. Use parameterized queries instead.'
            })
    
    return findings


def _find_percent_sql_injection(cursor) -> List[Dict[str, Any]]:
    """Find SQL queries using % string formatting."""
    findings = []
    
    sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE']
    
    # Find % formatting in SQL contexts
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%\\%%\\%%'
          AND ({})
    """.format(' OR '.join([f"a.source_expr LIKE '%{kw}%'" for kw in sql_keywords])))
    
    percent_queries = cursor.fetchall()
    
    for file, line, var, expr in percent_queries:
        # Check if it's the dangerous % formatting (not %s which is safe for some drivers)
        if '% (' in expr or '% {' in expr or '% [' in expr:
            findings.append({
                'rule_id': 'sql-injection-percent',
                'message': 'SQL query using % string formatting - injection vulnerability',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'critical',
                'category': 'security',
                'confidence': 'high',
                'description': 'Use parameterized queries with placeholders, not % string formatting.'
            })
    
    return findings


def _find_direct_input_sql_injection(cursor) -> List[Dict[str, Any]]:
    """Find execute() calls with direct user input."""
    findings = []
    
    # Common user input sources
    input_sources = [
        'request.args', 'request.form', 'request.json', 'request.data',
        'req.body', 'req.query', 'req.params',
        'input(', 'raw_input(', 'sys.argv'
    ]
    
    # Find database execute calls
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%execute%' 
               OR f.callee_function LIKE '%executemany%'
               OR f.callee_function LIKE '%executescript%'
               OR f.callee_function LIKE '%query%'
               OR f.callee_function LIKE '%raw%')
    """)
    
    execute_calls = cursor.fetchall()
    
    for file, line, func, args in execute_calls:
        if not args:
            continue
            
        # Check if arguments contain user input
        args_lower = args.lower() if args else ""
        contains_input = any(source in args_lower for source in input_sources)
        
        if contains_input:
            findings.append({
                'rule_id': 'sql-injection-direct-input',
                'message': 'Database execute with direct user input - severe injection risk',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'critical',
                'category': 'security',
                'confidence': 'high',
                'description': 'Never pass user input directly to execute(). Always use parameterized queries with placeholders.'
            })
        
        # Check for string operations in execute
        elif any(op in args for op in ['.format(', '% ', ' + ', 'f"', "f'"]):
            findings.append({
                'rule_id': 'sql-injection-unsafe-execute',
                'message': 'Database execute with string manipulation - likely injection vulnerability',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'critical',
                'category': 'security',
                'confidence': 'high',
                'description': 'Use parameterized queries: execute("SELECT * FROM users WHERE id = ?", [user_id])'
            })
    
    return findings


def _find_dynamic_query_construction(cursor) -> List[Dict[str, Any]]:
    """Find dynamic SQL query construction patterns."""
    findings = []
    
    # Patterns indicating dynamic query building
    dynamic_patterns = [
        'query =', 'sql =', 'stmt =', 'command =',
        'query +=', 'sql +=', 'stmt +=', 'command +='
    ]
    
    sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE', 'JOIN']
    
    # Find assignments that build queries dynamically
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.target_var LIKE '%query%' 
               OR a.target_var LIKE '%sql%'
               OR a.target_var LIKE '%stmt%'
               OR a.target_var LIKE '%command%')
          AND a.source_expr LIKE '%+%'
    """)
    
    dynamic_queries = cursor.fetchall()
    
    for file, line, var, expr in dynamic_queries:
        # Check if it contains SQL keywords
        expr_upper = expr.upper() if expr else ""
        if any(kw in expr_upper for kw in sql_keywords):
            findings.append({
                'rule_id': 'sql-injection-dynamic-query',
                'message': f'Dynamic SQL query construction in "{var}" - injection prone',
                'file': file,
                'line': line,
                'column': 0,
                'severity': 'high',
                'category': 'security',
                'confidence': 'medium',
                'description': 'Avoid building SQL queries dynamically. Use query builders or ORMs with proper escaping.'
            })
    
    # Find query builders that might be unsafe
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%build_query%'
           OR f.callee_function LIKE '%construct_query%'
           OR f.callee_function LIKE '%make_query%'
    """)
    
    query_builders = cursor.fetchall()
    
    for file, line, func, args in query_builders:
        findings.append({
            'rule_id': 'sql-injection-query-builder',
            'message': f'Custom query builder {func} - verify it properly escapes inputs',
            'file': file,
            'line': line,
            'column': 0,
            'severity': 'medium',
            'category': 'security',
            'confidence': 'medium',
            'description': 'Ensure query builder properly parameterizes or escapes all user inputs.'
        })
    
    return findings


def find_sql_injection(tree: Any) -> List[Dict[str, Any]]:
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
        findings = detect_sql_injection_patterns(db_path)
        for finding in findings:
            print(f"{finding['file']}:{finding['line']} - {finding['message']}")