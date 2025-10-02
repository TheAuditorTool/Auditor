"""SQL Injection Analyzer - Phase 2 Clean Implementation.

Database-first detection using ONLY indexed data. No AST traversal, no file I/O.
Filters out garbage (97.6% UNKNOWN) and queries clean sources: function_call_args.

Truth Courier Design: Reports facts about SQL construction patterns, not recommendations.
"""

import sqlite3
from typing import List
from dataclasses import dataclass
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# ============================================================================
# RULE METADATA - Phase 3B Addition (2025-10-02)
# ============================================================================
METADATA = RuleMetadata(
    name="sql_injection",
    category="sql",
    target_extensions=['.py', '.js', '.ts', '.mjs', '.cjs'],
    exclude_patterns=['frontend/', 'client/', 'migrations/', 'test/', '__tests__/'],
    requires_jsx_pass=False
)


@dataclass(frozen=True)
class SQLInjectionPatterns:
    """Finite pattern sets for SQL injection detection - no regex."""

    # String interpolation indicators (dangerous)
    INTERPOLATION_PATTERNS: frozenset = frozenset([
        '.format(', '{0}', '{1}', '{2}', '{}',
        'f"', "f'", 'F"', "F'",
        ' + ', '||', '${', '`${',
        '%s', '%d', '%(', ' % '
    ])

    # SQL keywords that indicate query construction
    SQL_KEYWORDS: frozenset = frozenset([
        'SELECT', 'INSERT', 'UPDATE', 'DELETE',
        'DROP', 'CREATE', 'ALTER', 'EXEC',
        'UNION', 'FROM', 'WHERE', 'JOIN'
    ])

    # SQL execution methods
    EXECUTION_METHODS: frozenset = frozenset([
        '.query', '.execute', '.executemany', '.executescript',
        '.raw', 'sequelize.query', 'db.query', 'knex.raw'
    ])

    # Safe parameterization indicators
    SAFE_PARAMS: frozenset = frozenset([
        '?', '$1', '$2', ':param', '@param',
        'replacements:', 'bind:', 'values:'
    ])


def find_sql_injection(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect SQL injection vulnerabilities using database queries.

    Detection strategy:
    1. Query function_call_args for .query()/.execute() calls
    2. Check if SQL contains string interpolation patterns
    3. Exclude if parameterization detected
    4. Filter out frontend/, migrations/, tests/

    Args:
        context: Rule execution context with db_path

    Returns:
        List of SQL injection findings
    """
    findings = []

    if not context.db_path:
        return findings

    patterns = SQLInjectionPatterns()
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Check table availability (graceful degradation)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        available_tables = {row[0] for row in cursor.fetchall()}

        if 'function_call_args' not in available_tables:
            return findings  # Cannot run without function_call_args table

        # Primary detection: function_call_args with SQL execution methods
        findings.extend(_find_format_injection(cursor, patterns))
        findings.extend(_find_fstring_injection(cursor, patterns))
        findings.extend(_find_concatenation_injection(cursor, patterns))
        findings.extend(_find_template_literal_injection(cursor, patterns))

        # Secondary detection: sql_queries table (only clean data)
        findings.extend(_find_dynamic_query_construction(cursor, patterns))

    finally:
        conn.close()

    return findings


def _find_format_injection(cursor, patterns: SQLInjectionPatterns) -> List[StandardFinding]:
    """Find .format() usage in SQL queries."""
    findings = []

    # Query for .query/.execute calls containing .format()
    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%.query%' OR callee_function LIKE '%.execute%')
          AND argument_expr LIKE '%.format(%'
        ORDER BY file, line
    """)

    seen = set()

    for file, line, func, args in cursor.fetchall():
        if not args:
            continue

        # Check if it contains SQL keywords
        args_upper = args.upper()
        has_sql = any(keyword in args_upper for keyword in patterns.SQL_KEYWORDS)

        if not has_sql:
            continue

        # Check if parameterized (safe)
        has_params = any(param in args for param in patterns.SAFE_PARAMS)

        if has_params:
            continue  # Parameterized queries are safe

        # Dedupe by file:line
        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(StandardFinding(
            rule_name='sql-injection-format',
            message='SQL query using .format() - potential injection risk',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='security',
            snippet=args[:80] + '...' if len(args) > 80 else args,
            cwe_id='CWE-89'
        ))

    return findings


def _find_fstring_injection(cursor, patterns: SQLInjectionPatterns) -> List[StandardFinding]:
    """Find f-string usage in SQL queries."""
    findings = []

    # Query for SQL execution with f-strings
    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%.query%' OR callee_function LIKE '%.execute%')
          AND (argument_expr LIKE '%f"%' OR argument_expr LIKE "%f'%")
        ORDER BY file, line
    """)

    seen = set()

    for file, line, func, args in cursor.fetchall():
        if not args:
            continue

        args_upper = args.upper()
        has_sql = any(keyword in args_upper for keyword in patterns.SQL_KEYWORDS)

        if not has_sql:
            continue

        has_params = any(param in args for param in patterns.SAFE_PARAMS)

        if has_params:
            continue

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(StandardFinding(
            rule_name='sql-injection-fstring',
            message='SQL query using f-string interpolation - potential injection risk',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='security',
            snippet=args[:80] + '...' if len(args) > 80 else args,
            cwe_id='CWE-89'
        ))

    return findings


def _find_concatenation_injection(cursor, patterns: SQLInjectionPatterns) -> List[StandardFinding]:
    """Find string concatenation in SQL queries."""
    findings = []

    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%.query%' OR callee_function LIKE '%.execute%')
          AND (argument_expr LIKE '% + %' OR argument_expr LIKE '%||%')
        ORDER BY file, line
    """)

    seen = set()

    for file, line, func, args in cursor.fetchall():
        if not args:
            continue

        args_upper = args.upper()
        has_sql = any(keyword in args_upper for keyword in patterns.SQL_KEYWORDS)

        if not has_sql:
            continue

        # Check for safe concatenation (string literals only)
        # If contains variable names between operators, it's dangerous
        if (' + ' in args or '||' in args):
            has_params = any(param in args for param in patterns.SAFE_PARAMS)

            if has_params:
                continue

            key = f"{file}:{line}"
            if key in seen:
                continue
            seen.add(key)

            findings.append(StandardFinding(
                rule_name='sql-injection-concatenation',
                message='SQL query using string concatenation - potential injection risk',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=args[:80] + '...' if len(args) > 80 else args,
                cwe_id='CWE-89'
            ))

    return findings


def _find_template_literal_injection(cursor, patterns: SQLInjectionPatterns) -> List[StandardFinding]:
    """Find template literal interpolation in SQL queries (JavaScript/TypeScript)."""
    findings = []

    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%.query%' OR callee_function LIKE '%.execute%' OR callee_function LIKE '%.raw%')
          AND argument_expr LIKE '%${%'
          AND (file LIKE '%.js' OR file LIKE '%.ts')
        ORDER BY file, line
    """)

    seen = set()

    for file, line, func, args in cursor.fetchall():
        if not args:
            continue

        args_upper = args.upper()
        has_sql = any(keyword in args_upper for keyword in patterns.SQL_KEYWORDS)

        if not has_sql:
            continue

        # Check for parameterization
        has_params = any(param in args for param in patterns.SAFE_PARAMS)

        if has_params:
            continue

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(StandardFinding(
            rule_name='sql-injection-template-literal',
            message='SQL query using template literal ${} - potential injection risk',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='security',
            snippet=args[:80] + '...' if len(args) > 80 else args,
            cwe_id='CWE-89'
        ))

    return findings


def _find_dynamic_query_construction(cursor, patterns: SQLInjectionPatterns) -> List[StandardFinding]:
    """Find dynamic query construction in sql_queries table (clean data only)."""
    findings = []

    # Only query CLEAN sql_queries (exclude UNKNOWN)
    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE command != 'UNKNOWN'
          AND command IS NOT NULL
          AND (query_text LIKE '%.format(%'
               OR query_text LIKE '%f"%'
               OR query_text LIKE "%f'%"
               OR query_text LIKE '% + %')
        ORDER BY file_path, line_number
        LIMIT 20
    """)

    seen = set()

    for file, line, query, command in cursor.fetchall():
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