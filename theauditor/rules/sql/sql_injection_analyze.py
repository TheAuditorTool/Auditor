"""SQL Injection Detector - Pure Database Implementation.

This module detects SQL injection vulnerabilities using ONLY indexed database data.
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


def find_sql_injection_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect SQL injection vulnerabilities using indexed SQL queries.
    
    Returns:
        List of SQL injection findings
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
            findings.extend(_find_sql_injection_in_function_calls(cursor))
        else:
            # Primary analysis using actual SQL queries
            findings.extend(_find_string_concatenation_in_queries(cursor))
            findings.extend(_find_format_string_in_queries(cursor))
            findings.extend(_find_fstring_patterns_in_queries(cursor))
            findings.extend(_find_dynamic_table_names(cursor))
            findings.extend(_find_unparameterized_user_input(cursor))
            findings.extend(_find_order_by_injection(cursor))
            findings.extend(_find_like_injection(cursor))
        
        # Secondary analysis using assignments and function calls
        findings.extend(_find_query_building_patterns(cursor))
        findings.extend(_find_unsafe_orm_usage(cursor))
        
    finally:
        conn.close()
    
    return findings


# ============================================================================
# PRIMARY DETECTION: Using sql_queries table
# ============================================================================

def _find_string_concatenation_in_queries(cursor) -> List[StandardFinding]:
    """Find SQL queries with string concatenation patterns."""
    findings = []
    seen_patterns = set()  # For deduplication
    
    # Look for concatenation patterns in actual SQL queries
    # EXCLUDE UNKNOWN commands and frontend files
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE command != 'UNKNOWN'
          AND command IS NOT NULL
          AND (file_path LIKE '%backend%' OR file_path LIKE '%server%' OR file_path LIKE '%api%')
          AND file_path NOT LIKE '%frontend%'
          AND file_path NOT LIKE '%client%'
          AND file_path NOT LIKE '%.tsx'
          AND file_path NOT LIKE '%.jsx'
          AND (query_text LIKE '%||%'
               OR query_text LIKE '%+%'
               OR query_text LIKE '%${%')
        ORDER BY file_path, line_number
        LIMIT 50
    """)
    
    for file, line, query, command in cursor.fetchall():
        # Deduplicate by file + pattern type
        pattern_key = f"{file}:{command}:concatenation"
        if pattern_key in seen_patterns:
            continue
        seen_patterns.add(pattern_key)
        
        # Check for common concatenation patterns that indicate injection
        if '||' in query or '+' in query or '${' in query:
            # Try to identify if it's user input concatenation
            query_lower = query.lower()
            if any(pattern in query_lower for pattern in ['where', 'and', 'or', 'having']):
                findings.append(StandardFinding(
                    rule_name='sql-injection-concatenation',
                    message=f'SQL {command} query using string concatenation - injection risk',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,  # Not always CRITICAL
                    category='security',
                    snippet=query[:100] + '...' if len(query) > 100 else query,
                    fix_suggestion='Use parameterized queries with placeholders (?, :param, %s)',
                    cwe_id='CWE-89'
                ))
    
    return findings


def _find_format_string_in_queries(cursor) -> List[StandardFinding]:
    """Find SQL queries using format strings."""
    findings = []
    
    # Look for format string patterns in SQL queries
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE query_text LIKE '%.format(%'
           OR query_text LIKE '%{}%'
           OR query_text LIKE '%{0}%'
           OR query_text LIKE '%{1}%'
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command in cursor.fetchall():
        if '{' in query and '}' in query:
            findings.append(StandardFinding(
                rule_name='sql-injection-format',
                message=f'SQL {command} query using format strings - severe injection risk',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                fix_suggestion='Never use .format() or {} placeholders for SQL. Use parameterized queries',
                cwe_id='CWE-89'
            ))
    
    return findings


def _find_fstring_patterns_in_queries(cursor) -> List[StandardFinding]:
    """Find f-string patterns in SQL queries."""
    findings = []
    
    # F-strings leave telltale patterns like variable interpolation
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE query_text LIKE '%f"%'
           OR query_text LIKE "%f'%"
           OR (query_text LIKE '%{%' AND query_text LIKE '%}%')
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command in cursor.fetchall():
        pattern_key = f"{file}:{command}:fstring"
        if pattern_key in seen_patterns:
            continue
        seen_patterns.add(pattern_key)
        
        # Check for f-string indicators
        if (query.startswith('f"') or query.startswith("f'") or 
            ('{' in query and '}' in query and not query.count('{') == query.count('{}'))):

            findings.append(StandardFinding(
                rule_name='sql-injection-fstring',
                message=f'SQL {command} query using f-string interpolation - critical vulnerability',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                fix_suggestion='F-strings in SQL are extremely dangerous. Use parameterized queries',
                cwe_id='CWE-89'
            ))
    
    return findings


def _find_dynamic_table_names(cursor) -> List[StandardFinding]:
    """Find queries with dynamic table/column names."""
    findings = []
    
    # Look for patterns indicating dynamic table/column names
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE (query_text LIKE '%FROM %{%' 
               OR query_text LIKE '%FROM %||%'
               OR query_text LIKE '%FROM %+%'
               OR query_text LIKE '%INSERT INTO %{%'
               OR query_text LIKE '%UPDATE %{%'
               OR query_text LIKE '%ALTER TABLE %{%')
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='sql-injection-dynamic-identifier',
            message=f'Dynamic table/column name in {command} query - injection vector',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=query[:100] + '...' if len(query) > 100 else query,
            fix_suggestion='Use allowlisted table/column names, never user input',
            cwe_id='CWE-89'
        ))
    
    return findings


def _find_unparameterized_user_input(cursor) -> List[StandardFinding]:
    """Find queries with likely user input patterns."""
    findings = []
    
    # Common user input variable patterns
    user_input_patterns = [
        '%user%', '%input%', '%request%', '%req%', '%param%',
        '%arg%', '%data%', '%form%', '%body%', '%query%'
    ]
    
    # Build the WHERE clause for all patterns
    where_conditions = " OR ".join([f"query_text LIKE '{pattern}'" for pattern in user_input_patterns])
    
    cursor.execute(f"""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE ({where_conditions})
          AND query_text NOT LIKE '%?%'
          AND query_text NOT LIKE '%:1%'
          AND query_text NOT LIKE '%$1%'
          AND query_text NOT LIKE '%%s%'
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command in cursor.fetchall():
        # Additional check for actual user input patterns
        query_lower = query.lower()
        if any(p.strip('%') in query_lower for p in user_input_patterns):
            findings.append(StandardFinding(
                rule_name='sql-injection-user-input',
                message=f'{command} query with user input but no parameter placeholders',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=query[:100] + '...' if len(query) > 100 else query,
                fix_suggestion='Use parameterized queries: execute("SELECT * WHERE id = ?", [user_id])',
                cwe_id='CWE-89'
            ))
    
    return findings


def _find_order_by_injection(cursor) -> List[StandardFinding]:
    """Find ORDER BY clauses with dynamic content."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE query_text LIKE '%ORDER BY%'
          AND (query_text LIKE '%${%'
               OR query_text LIKE '%+%'
               OR query_text LIKE '%||%'
               OR query_text LIKE '%format%')
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='sql-injection-order-by',
            message='Dynamic ORDER BY clause - classic injection point',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=query[:100] + '...' if len(query) > 100 else query,
            fix_suggestion='Use allowlisted column names for ORDER BY, never user input directly',
            cwe_id='CWE-89'
        ))
    
    return findings


def _find_like_injection(cursor) -> List[StandardFinding]:
    """Find LIKE clauses without proper escaping."""
    findings = []
    
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE query_text LIKE '%LIKE%'
          AND (query_text LIKE '%${%'
               OR query_text LIKE '%+%'
               OR query_text LIKE '%||%'
               OR query_text LIKE '%format%')
          AND query_text NOT LIKE '%ESCAPE%'
        ORDER BY file_path, line_number
    """)
    
    for file, line, query, command in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='sql-injection-like',
            message='LIKE clause with dynamic input and no ESCAPE - pattern injection risk',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='security',
            snippet=query[:100] + '...' if len(query) > 100 else query,
            fix_suggestion='Escape % and _ in user input or use ESCAPE clause',
            cwe_id='CWE-89'
        ))
    
    return findings


# ============================================================================
# SECONDARY DETECTION: Using function_call_args and assignments
# ============================================================================

def _find_sql_injection_in_function_calls(cursor) -> List[StandardFinding]:
    """Fallback detection using function calls when sql_queries is empty."""
    findings = []
    
    # Find execute/query calls with string operations
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%execute%'
               OR f.callee_function LIKE '%query%'
               OR f.callee_function LIKE '%raw%')
          AND (f.argument_expr LIKE '%+%'
               OR f.argument_expr LIKE '%.format%'
               OR f.argument_expr LIKE '%f"%'
               OR f.argument_expr LIKE "%f'%"
               OR f.argument_expr LIKE '%$%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        if args and any(op in args for op in ['+', '.format', 'f"', "f'", '$']):
            findings.append(StandardFinding(
                rule_name='sql-injection-function-call',
                message=f'{func} with string manipulation - likely SQL injection',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                fix_suggestion='Use parameterized queries, not string operations',
                cwe_id='CWE-89'
            ))
    
    return findings


def _find_query_building_patterns(cursor) -> List[StandardFinding]:
    """Find dynamic query construction in assignments."""
    findings = []
    
    # Find query building patterns
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.target_var LIKE '%query%'
               OR a.target_var LIKE '%sql%'
               OR a.target_var LIKE '%stmt%')
          AND (a.source_expr LIKE '%SELECT%'
               OR a.source_expr LIKE '%INSERT%'
               OR a.source_expr LIKE '%UPDATE%'
               OR a.source_expr LIKE '%DELETE%')
          AND (a.source_expr LIKE '%+%'
               OR a.source_expr LIKE '%.format%'
               OR a.source_expr LIKE '%f"%'
               OR a.source_expr LIKE "%f'%")
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, expr in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='sql-injection-query-building',
            message=f'Dynamic SQL construction in {var} - injection prone',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{var} = {expr[:50]}...' if len(expr) > 50 else f'{var} = {expr}',
            fix_suggestion='Use query builders or ORMs with proper escaping',
            cwe_id='CWE-89'
        ))
    
    # Find incremental query building (query += ...)
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%+=%'
          AND (a.target_var LIKE '%query%'
               OR a.target_var LIKE '%sql%'
               OR a.target_var LIKE '%where%')
        ORDER BY a.file, a.line
    """)
    
    for file, line, var, expr in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='sql-injection-incremental-build',
            message=f'Incremental SQL building in {var} - high injection risk',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{var} += ...',
            fix_suggestion='Avoid building SQL incrementally. Use parameterized queries',
            cwe_id='CWE-89'
        ))
    
    return findings


def _find_unsafe_orm_usage(cursor) -> List[StandardFinding]:
    """Find unsafe ORM usage patterns."""
    findings = []
    
    # Find raw() or rawQuery() calls
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%.raw%'
               OR f.callee_function LIKE '%rawQuery%'
               OR f.callee_function LIKE '%knex.raw%'
               OR f.callee_function LIKE '%sequelize.query%')
          AND f.argument_expr NOT LIKE '%?%'
          AND f.argument_expr NOT LIKE '%::%'
          AND f.argument_expr NOT LIKE '%$%'
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        if args and not any(placeholder in args for placeholder in ['?', '::', '$']):
            findings.append(StandardFinding(
                rule_name='sql-injection-orm-raw',
                message=f'ORM raw query without placeholders in {func}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                fix_suggestion='Use bind parameters even in raw ORM queries',
                cwe_id='CWE-89'
            ))
    
    # Find whereRaw or havingRaw without bindings
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%whereRaw%'
               OR f.callee_function LIKE '%havingRaw%'
               OR f.callee_function LIKE '%orderByRaw%')
          AND f.param_name = 'arg0'
          AND (f.argument_expr LIKE '%+%'
               OR f.argument_expr LIKE '%${%')
        ORDER BY f.file, f.line
    """)
    
    for file, line, func, args in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='sql-injection-orm-where-raw',
            message=f'Unsafe {func} with string concatenation',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
            fix_suggestion=f'Use {func}("column = ?", [value]) with bindings',
            cwe_id='CWE-89'
        ))
    
    return findings