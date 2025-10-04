"""SQL Safety Analyzer - Phase 2 Clean Implementation.

Database-first detection using ONLY indexed data. No AST traversal, no file I/O.
Focuses on SQL safety patterns: missing WHERE, unbounded queries, transaction issues.

Truth Courier Design: Reports facts about SQL patterns, not recommendations.
"""

import sqlite3
from typing import List
from dataclasses import dataclass
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, RuleMetadata


# ============================================================================
# RULE METADATA - Phase 3B Addition (2025-10-02)
# ============================================================================
METADATA = RuleMetadata(
    name="sql_safety",
    category="sql",
    target_extensions=['.py', '.js', '.ts', '.mjs', '.cjs'],
    exclude_patterns=['frontend/', 'client/', 'migrations/', 'test/', '__tests__/'],
    requires_jsx_pass=False
)


@dataclass(frozen=True)
class SQLSafetyPatterns:
    """Finite pattern sets for SQL safety detection - no regex."""

    # DML commands that need WHERE clauses
    DML_COMMANDS: frozenset = frozenset([
        'UPDATE', 'DELETE'
    ])

    # Aggregate functions (don't need LIMIT)
    AGGREGATE_FUNCTIONS: frozenset = frozenset([
        'COUNT(', 'MAX(', 'MIN(', 'SUM(', 'AVG(', 'GROUP BY'
    ])

    # Transaction-related keywords
    TRANSACTION_KEYWORDS: frozenset = frozenset([
        'transaction', 'begin', 'start_transaction', 'beginTransaction',
        'BEGIN', 'START TRANSACTION', 'db.transaction', 'sequelize.transaction'
    ])

    # Rollback indicators
    ROLLBACK_KEYWORDS: frozenset = frozenset([
        'rollback', 'ROLLBACK', '.rollback('
    ])

    # Commit indicators
    COMMIT_KEYWORDS: frozenset = frozenset([
        'commit', 'COMMIT', '.commit('
    ])


def find_sql_safety_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect SQL safety issues using database queries.

    Detection strategy:
    1. Query sql_queries for UPDATE/DELETE without WHERE
    2. Query sql_queries for SELECT without LIMIT
    3. Query function_call_args for transaction patterns
    4. Check for missing rollback in transaction scope
    5. Detect SELECT *
    6. Find connection leaks
    7. Detect nested transactions
    8. Find large IN clauses
    9. Detect unindexed field queries

    Args:
        context: Rule execution context with db_path

    Returns:
        List of SQL safety findings
    """
    findings = []

    if not context.db_path:
        return findings

    patterns = SQLSafetyPatterns()
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Primary detection: sql_queries table (clean data only)
        findings.extend(_find_update_without_where(cursor))
        findings.extend(_find_delete_without_where(cursor))
        findings.extend(_find_unbounded_queries(cursor))
        findings.extend(_find_select_star(cursor))
        findings.extend(_find_large_in_clauses(cursor))
        findings.extend(_find_missing_db_indexes(cursor))

        # Secondary detection: function_call_args for transactions
        findings.extend(_find_transactions_without_rollback(cursor, patterns))
        findings.extend(_find_nested_transactions(cursor, patterns))
        findings.extend(_find_connection_leaks(cursor))

    finally:
        conn.close()

    return findings


def _find_update_without_where(cursor) -> List[StandardFinding]:
    """Find UPDATE statements without WHERE clause."""
    findings = []

    # Query CLEAN sql_queries only
    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file_path, line_number, query_text
        FROM sql_queries
        WHERE command = 'UPDATE'
          AND query_text NOT LIKE '%WHERE%'
          AND query_text NOT LIKE '%where%'
        ORDER BY file_path, line_number
        LIMIT 15
    """)

    seen = set()

    for file, line, query in cursor.fetchall():
        # Double-check no WHERE clause
        query_upper = query.upper()
        if 'WHERE' in query_upper:
            continue

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(StandardFinding(
            rule_name='sql-safety-update-no-where',
            message='UPDATE without WHERE clause affects all rows',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='security',
            snippet=query[:100] + '...' if len(query) > 100 else query,
            cwe_id='CWE-89'
        ))

    return findings


def _find_delete_without_where(cursor) -> List[StandardFinding]:
    """Find DELETE statements without WHERE clause."""
    findings = []

    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file_path, line_number, query_text
        FROM sql_queries
        WHERE command = 'DELETE'
          AND query_text NOT LIKE '%WHERE%'
          AND query_text NOT LIKE '%where%'
          AND query_text NOT LIKE '%TRUNCATE%'
        ORDER BY file_path, line_number
        LIMIT 15
    """)

    seen = set()

    for file, line, query in cursor.fetchall():
        query_upper = query.upper()
        if 'WHERE' in query_upper or 'TRUNCATE' in query_upper:
            continue

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(StandardFinding(
            rule_name='sql-safety-delete-no-where',
            message='DELETE without WHERE clause removes all rows',
            file_path=file,
            line=line,
            severity=Severity.CRITICAL,
            category='security',
            snippet=query[:100] + '...' if len(query) > 100 else query,
            cwe_id='CWE-89'
        ))

    return findings


def _find_unbounded_queries(cursor) -> List[StandardFinding]:
    """Find SELECT queries without LIMIT that might return large datasets."""
    findings = []

    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file_path, line_number, query_text, tables
        FROM sql_queries
        WHERE command = 'SELECT'
          AND query_text NOT LIKE '%LIMIT%'
          AND query_text NOT LIKE '%limit%'
          AND query_text NOT LIKE '%TOP %'
        ORDER BY file_path, line_number
        LIMIT 30
    """)

    seen = set()
    aggregate_patterns = ['COUNT(', 'MAX(', 'MIN(', 'SUM(', 'AVG(', 'GROUP BY']

    for file, line, query, tables in cursor.fetchall():
        query_upper = query.upper()

        # Skip aggregate queries
        if any(agg in query_upper for agg in aggregate_patterns):
            continue

        # Check if it's a potentially large result set (has JOIN or multiple tables)
        if 'JOIN' in query_upper or (tables and ',' in tables):
            severity = Severity.HIGH
        else:
            severity = Severity.MEDIUM

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(StandardFinding(
            rule_name='sql-safety-unbounded-query',
            message='SELECT without LIMIT - potential memory issue with large datasets',
            file_path=file,
            line=line,
            severity=severity,
            category='performance',
            snippet=query[:100] + '...' if len(query) > 100 else query,
            cwe_id='CWE-770'
        ))

    return findings


def _find_select_star(cursor) -> List[StandardFinding]:
    """Find SELECT * queries that fetch unnecessary columns."""
    findings = []

    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file_path, line_number, query_text, tables
        FROM sql_queries
        WHERE command = 'SELECT'
          AND (query_text LIKE '%SELECT *%' OR query_text LIKE '%select *%')
        ORDER BY file_path, line_number
        LIMIT 25
    """)

    seen = set()

    for file, line, query, tables in cursor.fetchall():
        query_upper = query.upper()

        # Confirm it's really SELECT *
        if 'SELECT *' not in query_upper and 'SELECT  *' not in query_upper:
            continue

        # Multiple tables = higher severity
        table_list = tables.split(',') if tables else []
        severity = Severity.MEDIUM if len(table_list) > 1 else Severity.LOW

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(StandardFinding(
            rule_name='sql-safety-select-star',
            message='SELECT * query fetches all columns - specify needed columns',
            file_path=file,
            line=line,
            severity=severity,
            category='performance',
            snippet=query[:100] + '...' if len(query) > 100 else query,
            cwe_id='CWE-770'
        ))

    return findings


def _find_transactions_without_rollback(cursor, patterns: SQLSafetyPatterns) -> List[StandardFinding]:
    """Find transactions that lack rollback in error handlers."""
    findings = []

    # Find transaction starts in function_call_args
    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE (callee_function LIKE '%transaction%'
               OR callee_function LIKE '%begin%'
               OR callee_function LIKE '%BEGIN%')
        ORDER BY file, line
    """)

    transactions = cursor.fetchall()

    for file, line, func in transactions:
        # Check for rollback within ±50 lines (proximity search)
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args
            WHERE file = ?
              AND line BETWEEN ? AND ?
              AND (callee_function LIKE '%rollback%' OR callee_function LIKE '%ROLLBACK%')
        """, (file, line, line + 50))

        has_rollback = cursor.fetchone()[0] > 0

        if not has_rollback:
            # Check for error handling nearby (try/catch/except)
            cursor.execute("""
                SELECT COUNT(*)
                FROM symbols
                WHERE file = ?
                  AND line BETWEEN ? AND ?
                  AND (name LIKE '%catch%' OR name LIKE '%except%' OR name LIKE '%finally%')
            """, (file, line - 5, line + 50))

            has_error_handling = cursor.fetchone()[0] > 0

            # Only flag if there's error handling but no rollback
            if has_error_handling:
                findings.append(StandardFinding(
                    rule_name='sql-safety-transaction-no-rollback',
                    message='Transaction without rollback in error handling path',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='reliability',
                    snippet=f'{func}(...)',
                    cwe_id='CWE-667'
                ))

    return findings


def _find_connection_leaks(cursor) -> List[StandardFinding]:
    """Find database connections opened but not closed."""
    findings = []

    # Find connection opens
    # NOTE: frontend/test filtering handled by METADATA
    cursor.execute("""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE (callee_function LIKE '%connect%'
               OR callee_function LIKE '%createConnection%'
               OR callee_function LIKE '%getConnection%')
        ORDER BY file, line
        LIMIT 30
    """)

    connections = cursor.fetchall()

    for file, line, func in connections:
        # Check for close/end/release within 100 lines
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args
            WHERE file = ?
              AND line BETWEEN ? AND ?
              AND (callee_function LIKE '%close%'
                   OR callee_function LIKE '%end%'
                   OR callee_function LIKE '%release%'
                   OR callee_function LIKE '%destroy%')
        """, (file, line, line + 100))

        has_close = cursor.fetchone()[0] > 0

        if not has_close:
            # Check for context manager (with/using)
            cursor.execute("""
                SELECT COUNT(*)
                FROM symbols
                WHERE file = ?
                  AND line BETWEEN ? AND ?
                  AND (name LIKE '%with %' OR name LIKE '%using%')
            """, (file, line - 2, line + 2))

            has_context = cursor.fetchone()[0] > 0

            if not has_context:
                findings.append(StandardFinding(
                    rule_name='sql-safety-connection-leak',
                    message='Database connection opened but not closed',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='reliability',
                    snippet=f'{func}(...)',
                    cwe_id='CWE-404'
                ))

    return findings


def _find_nested_transactions(cursor, patterns: SQLSafetyPatterns) -> List[StandardFinding]:
    """Find nested transaction starts that could cause deadlocks."""
    findings = []

    # Find all transaction starts grouped by file
    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file, line, callee_function
        FROM function_call_args
        WHERE (callee_function LIKE '%transaction%'
               OR callee_function LIKE '%begin%'
               OR callee_function LIKE '%BEGIN%')
        ORDER BY file, line
    """)

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
                    FROM function_call_args
                    WHERE file = ?
                      AND line > ? AND line < ?
                      AND (callee_function LIKE '%commit%' OR callee_function LIKE '%rollback%')
                """, (file, line1, line2))

                has_commit_between = cursor.fetchone()[0] > 0

                if not has_commit_between and (line2 - line1) < 100:  # Within 100 lines
                    findings.append(StandardFinding(
                        rule_name='sql-safety-nested-transaction',
                        message='Nested transaction detected - potential deadlock risk',
                        file_path=file,
                        line=line2,
                        severity=Severity.HIGH,
                        category='reliability',
                        snippet=f'{func2}(...)',
                        cwe_id='CWE-667'
                    ))

    return findings


def _find_large_in_clauses(cursor) -> List[StandardFinding]:
    """Find queries with large IN clauses that could be inefficient."""
    findings = []

    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE (query_text LIKE '%IN (%' OR query_text LIKE '%in (%')
          AND command != 'UNKNOWN'
          AND LENGTH(query_text) > 150
        ORDER BY file_path, line_number
        LIMIT 25
    """)

    for file, line, query, command in cursor.fetchall():
        # Count items in IN clause by counting commas
        query_upper = query.upper()
        in_pos = query_upper.find(' IN (')

        if in_pos == -1:
            in_pos = query_upper.find(' IN(')

        if in_pos != -1:
            # Extract the IN clause content
            paren_start = in_pos + 4 if ' IN(' in query_upper else in_pos + 5
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
                elif comma_count > 20:
                    severity = Severity.MEDIUM
                elif comma_count > 10:
                    severity = Severity.LOW
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


def _find_missing_db_indexes(cursor) -> List[StandardFinding]:
    """Find queries on potentially unindexed fields (heuristic-based)."""
    findings = []

    # Common unindexed field patterns
    unindexed_patterns = ['email', 'username', 'status', 'created_at', 'updated_at']

    # NOTE: frontend/test/migration filtering handled by METADATA
    cursor.execute("""
        SELECT file_path, line_number, query_text, command, tables
        FROM sql_queries
        WHERE command = 'SELECT'
          AND query_text LIKE '%WHERE%'
        ORDER BY file_path, line_number
        LIMIT 30
    """)

    seen = set()

    for file, line, query, command, tables in cursor.fetchall():
        query_lower = query.lower()

        # Check if WHERE clause uses common unindexed fields
        for field in unindexed_patterns:
            if f' {field} =' in query_lower or f'.{field} =' in query_lower:
                # Skip if it's a primary key or has LIMIT
                if 'limit' in query_lower or ' id ' in query_lower:
                    continue

                key = f"{file}:{line}"
                if key in seen:
                    continue
                seen.add(key)

                findings.append(StandardFinding(
                    rule_name='sql-safety-unindexed-field',
                    message=f'Query using potentially unindexed field "{field}"',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='performance',
                    snippet=query[:100] + '...' if len(query) > 100 else query,
                    cwe_id='CWE-770'
                ))
                break  # One finding per query

    return findings