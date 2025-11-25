"""SQL Injection Detection.

Detects SQL injection vulnerabilities from raw patterns captured
during indexing.

Schema-driven enforcement (v1.3+):
- SQL queries table populated during indexing
- No fallback regex patterns
- No runtime file scanning
"""


import re
import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity
from theauditor.indexer.schema import build_query


# ============================================================================
# REGEXP ADAPTER - Enable regex in SQLite queries
# ============================================================================
def _regexp_adapter(expr: str, item: str) -> bool:
    """Adapter to let SQLite use Python's regex engine.

    Usage in SQL: WHERE column REGEXP 'pattern'
    """
    if item is None:
        return False
    return re.search(expr, item, re.IGNORECASE) is not None

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

    # Register regex adapter for SQL REGEXP operator
    conn.create_function("REGEXP", 2, _regexp_adapter)

    cursor = conn.cursor()

    # ========================================================================
    # CHECK 1: SQL QUERIES WITH INTERPOLATION
    # ========================================================================
    # FIXED: Moved interpolation pattern check to SQL with REGEXP

    # Build regex for interpolation patterns
    # Escape special regex chars in patterns like ${, %(, etc.
    interpolation_tokens = []
    for pattern in patterns.INTERPOLATION_PATTERNS:
        interpolation_tokens.append(re.escape(pattern))

    interpolation_regex = '|'.join(interpolation_tokens)

    # Use raw SQL to leverage REGEXP - build_query can't do complex WHERE
    cursor.execute("""
        SELECT file_path, line_number, query_text
        FROM sql_queries
        WHERE has_interpolation = 1
          AND file_path NOT LIKE '%test%'
          AND file_path NOT LIKE '%migration%'
          AND query_text REGEXP ?
        ORDER BY file_path, line_number
    """, (interpolation_regex,))

    for file, line, query_text in cursor.fetchall():
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
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
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
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
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
    # FIXED: Used JOIN to eliminate N+1 query explosion

    # Single query with JOIN: Find assignments of request data to SQL variables
    # that are then used in execute/query function calls
    cursor.execute("""
        WITH tainted_vars AS (
            SELECT file, target_var, source_expr
            FROM assignments
            WHERE (source_expr LIKE '%request.%' OR source_expr LIKE '%req.%')
              AND target_var REGEXP '(?i)(sql|query|stmt|command)'
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%migration%'
        )
        SELECT f.file, f.line, f.callee_function, t.target_var, t.source_expr
        FROM function_call_args f
        INNER JOIN tainted_vars t
            ON f.file = t.file
            AND (f.callee_function LIKE '%execute%' OR f.callee_function LIKE '%query%')
            AND f.argument_expr LIKE '%' || t.target_var || '%'
        ORDER BY f.file, f.line
    """)

    for file, line, func, var, expr in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='sql-injection-user-input',
            message=f'User input from {expr[:30]} used in SQL {func}',
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
            # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
            #       Move filtering logic to SQL WHERE clause for efficiency
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
        # TODO: PYTHON FILTERING DETECTED - 'if/continue' pattern found
        #       Move filtering logic to SQL WHERE clause for efficiency
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