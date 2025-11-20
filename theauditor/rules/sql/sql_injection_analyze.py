"""SQL Injection Detection.

Detects SQL injection vulnerabilities from raw patterns captured
during indexing.

Schema-driven enforcement (v1.3+):
- SQL queries table populated during indexing
- No fallback regex patterns
- No runtime file scanning
"""


import sqlite3
from typing import List
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity
from theauditor.indexer.schema import build_query

# ============================================================================
# PATTERNS - DETECT SQL INJECTION
# ============================================================================

@dataclass(frozen=True)
class SQLInjectionPatterns:
    """SQL injection patterns."""

    # Raw SQL execution keywords
    SQL_KEYWORDS = frozenset([
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
        'ALTER', 'TRUNCATE', 'EXEC', 'EXECUTE', 'UNION'
    ])

    # String concatenation/interpolation patterns indicating dynamic SQL
    INTERPOLATION_PATTERNS = frozenset([
        '${', '%s', '%(', '{0}', '{1}', '.format(',
        '+ "', '" +', '+ \'', '\' +', 'f"', 'f\'', '`'
    ])

    # Safe parameterization patterns
    SAFE_PARAMS = frozenset([
        '?', ':1', ':2', '$1', '$2', '%s',
        '@param', ':param', '${param}'
    ])

# ============================================================================
# RULE: SQL INJECTION DETECTION
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Analyze codebase for SQL injection vulnerabilities.

    Detects:
    - Dynamic SQL query construction with string concatenation
    - Template literal SQL queries with interpolation
    - Raw SQL execution without parameterization
    - User input directly in SQL queries

    Args:
        context: Rule execution context

    Returns:
        List of SQL injection findings
    """
    findings = []
    patterns = SQLInjectionPatterns()

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    # ========================================================================
    # CHECK 1: SQL QUERIES WITH INTERPOLATION
    # ========================================================================

    # Schema contract: sql_queries table exists
    query = build_query('sql_queries', ['file', 'line', 'query_text', 'has_interpolation'],
                       order_by="file, line")
    cursor.execute(query)

    for file, line, query_text, has_interpolation in cursor.fetchall():
        if not has_interpolation:
            continue

        # Check if query has user input patterns
        suspicious = False
        for pattern in patterns.INTERPOLATION_PATTERNS:
            if pattern in query_text:
                suspicious = True
                break

        if suspicious:
            findings.append(StandardFinding(
                rule_name='sql-injection-interpolation',
                message='SQL query with string interpolation - high injection risk',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=query_text[:100] + '...' if len(query_text) > 100 else query_text,
                cwe_id='CWE-89'
            ))

    # ========================================================================
    # CHECK 2: DYNAMIC QUERIES IN FUNCTION CALLS
    # ========================================================================

    # Check for execute/query calls with concatenation
    query = build_query('function_call_args',
                       ['file', 'line', 'callee_function', 'argument_expr'],
                       where="callee_function LIKE '%execute%' OR callee_function LIKE '%query%'",
                       order_by="file, line")
    cursor.execute(query)

    seen_dynamic = set()
    for file, line, func, args in cursor.fetchall():
        if not args:
            continue

        # Skip if not SQL-related
        if not any(kw in func.lower() for kw in ['execute', 'query', 'sql', 'db']):
            continue

        # Check for dynamic construction in arguments
        has_concat = any(pattern in args for pattern in ['+', '${', 'f"', '.format(', '%'])

        if has_concat:
            key = f"{file}:{line}"
            if key not in seen_dynamic:
                seen_dynamic.add(key)
                findings.append(StandardFinding(
                    rule_name='sql-injection-dynamic-args',
                    message=f'{func} called with dynamic SQL construction',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=args[:80] + '...' if len(args) > 80 else args,
                    cwe_id='CWE-89'
                ))

    # ========================================================================
    # CHECK 3: ORM RAW QUERIES
    # ========================================================================

    # Check for ORM raw query methods
    raw_query_patterns = [
        'sequelize.query', 'knex.raw', 'db.raw', 'raw(',
        'execute_sql', 'executeSql', 'session.execute'
    ]

    placeholders = ','.join(['?' for _ in raw_query_patterns])
    query = build_query('function_call_args',
                       ['file', 'line', 'callee_function', 'argument_expr'],
                       where=f"callee_function IN ({placeholders})",
                       order_by="file, line")
    cursor.execute(query, raw_query_patterns)

    for file, line, func, args in cursor.fetchall():
        if not args:
            continue

        # Check if arguments contain dynamic SQL
        if any(pattern in args for pattern in patterns.INTERPOLATION_PATTERNS):
            findings.append(StandardFinding(
                rule_name='sql-injection-orm-raw',
                message=f'ORM raw query {func} with dynamic SQL',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=args[:80] + '...' if len(args) > 80 else args,
                cwe_id='CWE-89'
            ))

    # ========================================================================
    # CHECK 4: USER INPUT IN SQL
    # ========================================================================

    # Check assignments that build SQL from request data
    query = build_query('assignments',
                       ['file', 'line', 'target_var', 'source_expr'],
                       where="source_expr LIKE '%request.%' OR source_expr LIKE '%req.%'",
                       order_by="file, line")
    cursor.execute(query)

    sql_vars = {}
    for file, line, var, expr in cursor.fetchall():
        # Track variables that contain request data
        if any(kw in var.lower() for kw in ['sql', 'query', 'stmt', 'command']):
            sql_vars[var] = (file, line, expr)

    # Now check if these SQL variables are used in execute/query calls
    for var, (var_file, var_line, var_expr) in sql_vars.items():
        query = build_query('function_call_args',
                           ['file', 'line', 'callee_function'],
                           where="argument_expr LIKE ? AND (callee_function LIKE '%execute%' OR callee_function LIKE '%query%')",
                           order_by="file, line")
        cursor.execute(query, [f'%{var}%'])

        for file, line, func in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='sql-injection-user-input',
                message=f'User input from {var_expr[:30]} used in SQL {func}',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'{var} used in {func}',
                cwe_id='CWE-89'
            ))

    # ========================================================================
    # CHECK 5: TEMPLATE LITERALS WITH SQL
    # ========================================================================

    # Check template literals table for SQL content
    try:
        query = build_query('template_literals',
                           ['file', 'line', 'content'],
                           order_by="file, line")
        cursor.execute(query)

        for file, line, content in cursor.fetchall():
            if not content:
                continue

            # Check if template contains SQL keywords
            content_upper = content.upper()
            has_sql = any(kw in content_upper for kw in patterns.SQL_KEYWORDS)

            if has_sql and '${' in content:
                findings.append(StandardFinding(
                    rule_name='sql-injection-template-literal',
                    message='Template literal contains SQL with interpolation',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=content[:100] + '...' if len(content) > 100 else content,
                    cwe_id='CWE-89'
                ))
    except sqlite3.OperationalError:
        # Table might not exist for some languages
        pass

    # ========================================================================
    # CHECK 6: STORED PROCEDURES WITH DYNAMIC INPUT
    # ========================================================================

    # Check for stored procedure calls with user input
    sp_patterns = ['CALL', 'EXEC', 'EXECUTE', 'sp_executesql']

    for sp in sp_patterns:
        query = build_query('function_call_args',
                           ['file', 'line', 'callee_function', 'argument_expr'],
                           where="callee_function LIKE ? OR argument_expr LIKE ?",
                           order_by="file, line")
        cursor.execute(query, [f'%{sp}%', f'%{sp}%'])

        for file, line, func, args in cursor.fetchall():
            if not args:
                continue

            # Check for dynamic construction
            if any(pattern in args for pattern in ['+', '${', '.format']):
                findings.append(StandardFinding(
                    rule_name='sql-injection-stored-proc',
                    message=f'Stored procedure call with dynamic input',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=args[:80] + '...' if len(args) > 80 else args,
                    cwe_id='CWE-89'
                ))

    conn.close()
    return findings


# ============================================================================
# AUXILIARY ANALYSIS FUNCTIONS
# ============================================================================

def check_dynamic_query_construction(context: StandardRuleContext) -> list[StandardFinding]:
    """Check for dynamic SQL query construction patterns.

    Specifically looks for:
    - String concatenation to build SQL
    - Format strings with SQL keywords
    - Template literals with SQL content

    Args:
        context: Rule execution context

    Returns:
        List of findings for dynamic query construction
    """
    findings = []
    patterns = SQLInjectionPatterns()

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    # Check sql_queries for dynamic patterns
    query = build_query('sql_queries',
                       ['file', 'line', 'query_text', 'command'],
                       order_by="file, line")
    cursor.execute(query)

    seen = set()
    for file, line, query, command in cursor.fetchall():
        if not query:
            continue

        # Check for interpolation patterns
        has_interpolation = any(pattern in query for pattern in patterns.INTERPOLATION_PATTERNS)

        if not has_interpolation:
            continue

        # Check for safe parameterization
        has_params = any(param in query for param in patterns.SAFE_PARAMS)

        if has_params:
            continue

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(StandardFinding(
            rule_name='sql-injection-dynamic-query',
            message=f'{command} query with dynamic construction - potential injection risk',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=query[:80] + '...' if len(query) > 80 else query,
            cwe_id='CWE-89'
        ))

    return findings


def populate_taint(taint_registry):
    """Register SQL injection sinks and sources for taint analysis.

    Args:
        taint_registry: TaintRegistry instance to populate
    """
    # Common SQL execution sinks for all languages
    sql_sinks = [
        # Generic patterns
        'execute', 'query', 'exec', 'executemany',
        'executeQuery', 'executeUpdate',

        # Python patterns
        'cursor.execute', 'conn.execute', 'db.execute',
        'session.execute', 'engine.execute',

        # JavaScript/Node.js patterns
        'db.query', 'connection.query', 'pool.query',
        'client.query', 'knex.raw', 'sequelize.query',

        # Java patterns
        'executeQuery', 'executeUpdate', 'prepareStatement',
        'createStatement', 'prepareCall'
    ]

    # Register sinks for multiple languages
    for pattern in sql_sinks:
        # Register for all common languages
        for lang in ['python', 'javascript', 'java', 'typescript']:
            taint_registry.register_sink(pattern, 'sql', lang)

    # SQL input sources (user-controlled data)
    sql_sources = [
        'request.query', 'request.params', 'request.body',
        'req.query', 'req.params', 'req.body',
        'args.get', 'form.get', 'request.args',
        'request.form', 'request.values'
    ]

    for pattern in sql_sources:
        for lang in ['python', 'javascript', 'typescript']:
            taint_registry.register_source(pattern, 'user_input', lang)