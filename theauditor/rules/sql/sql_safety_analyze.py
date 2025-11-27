"""SQL Safety Analyzer - Phase 2 Clean Implementation.

Database-first detection using ONLY indexed data. No AST traversal, no file I/O.
Focuses on SQL safety patterns: missing WHERE, unbounded queries, transaction issues.

Truth Courier Design: Reports facts about SQL patterns, not recommendations.
"""

import re
import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext


def _regexp_adapter(expr: str, item: str) -> bool:
    """Adapter to let SQLite use Python's regex engine.

    Usage in SQL: WHERE column REGEXP 'pattern'
    """
    if item is None:
        return False
    try:
        return re.search(expr, item, re.IGNORECASE) is not None
    except Exception:
        return False


METADATA = RuleMetadata(
    name="sql_safety",
    category="sql",
    target_extensions=[".py", ".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=["frontend/", "client/", "migrations/", "test/", "__tests__/"],
    requires_jsx_pass=False,
    execution_scope="database",
)


@dataclass(frozen=True)
class SQLSafetyPatterns:
    """Finite pattern sets for SQL safety detection - no regex."""

    DML_COMMANDS: frozenset = frozenset(["UPDATE", "DELETE"])

    AGGREGATE_FUNCTIONS: frozenset = frozenset(
        ["COUNT(", "MAX(", "MIN(", "SUM(", "AVG(", "GROUP BY"]
    )

    TRANSACTION_KEYWORDS: frozenset = frozenset(
        [
            "transaction",
            "begin",
            "start_transaction",
            "beginTransaction",
            "BEGIN",
            "START TRANSACTION",
            "db.transaction",
            "sequelize.transaction",
        ]
    )

    ROLLBACK_KEYWORDS: frozenset = frozenset(["rollback", "ROLLBACK", ".rollback("])

    COMMIT_KEYWORDS: frozenset = frozenset(["commit", "COMMIT", ".commit("])

    UNINDEXED_FIELD_PATTERNS: frozenset = frozenset(
        ["email", "username", "status", "created_at", "updated_at"]
    )


def find_sql_safety_issues(context: StandardRuleContext) -> list[StandardFinding]:
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

    conn.create_function("REGEXP", 2, _regexp_adapter)

    cursor = conn.cursor()

    try:
        findings.extend(_find_update_without_where(cursor))
        findings.extend(_find_delete_without_where(cursor))
        findings.extend(_find_unbounded_queries(cursor, patterns))
        findings.extend(_find_select_star(cursor))
        findings.extend(_find_large_in_clauses(cursor))
        findings.extend(_find_missing_db_indexes(cursor, patterns))

        findings.extend(_find_transactions_without_rollback(cursor, patterns))
        findings.extend(_find_nested_transactions(cursor, patterns))
        findings.extend(_find_connection_leaks(cursor))

    finally:
        conn.close()

    return findings


def _find_update_without_where(cursor) -> list[StandardFinding]:
    """Find UPDATE statements without WHERE clause.

    FIXED: Moved WHERE check to SQL (was hiding bugs with LIMIT).
    Uses word boundary regex to avoid matching 'somewhere' or 'elsewhere'.
    """
    findings = []

    cursor.execute("""
        SELECT file_path, line_number, query_text
        FROM sql_queries
        WHERE command = 'UPDATE'
          AND query_text IS NOT NULL
          AND file_path NOT LIKE '%test%'
          AND file_path NOT LIKE '%migration%'
          AND query_text NOT REGEXP '\\bWHERE\\b'
        ORDER BY file_path, line_number
    """)

    seen = set()

    for file, line, query in cursor.fetchall():
        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="sql-safety-update-no-where",
                message="UPDATE without WHERE clause affects all rows",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="security",
                snippet=query[:100] + "..." if len(query) > 100 else query,
                cwe_id="CWE-89",
            )
        )

    return findings


def _find_delete_without_where(cursor) -> list[StandardFinding]:
    """Find DELETE statements without WHERE clause.

    FIXED: Moved WHERE/TRUNCATE checks to SQL (was hiding bugs with LIMIT).
    """
    findings = []

    cursor.execute("""
        SELECT file_path, line_number, query_text
        FROM sql_queries
        WHERE command = 'DELETE'
          AND query_text IS NOT NULL
          AND file_path NOT LIKE '%test%'
          AND file_path NOT LIKE '%migration%'
          AND query_text NOT REGEXP '\\b(WHERE|TRUNCATE)\\b'
        ORDER BY file_path, line_number
    """)

    seen = set()

    for file, line, query in cursor.fetchall():
        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="sql-safety-delete-no-where",
                message="DELETE without WHERE clause removes all rows",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="security",
                snippet=query[:100] + "..." if len(query) > 100 else query,
                cwe_id="CWE-89",
            )
        )

    return findings


def _find_unbounded_queries(cursor, patterns: SQLSafetyPatterns) -> list[StandardFinding]:
    """Find SELECT queries without LIMIT that might return large datasets.

    FIXED: Moved LIMIT/aggregate checks to SQL (was hiding bugs with LIMIT).
    """
    findings = []

    safe_tokens = [r"\bLIMIT\b", r"\bTOP\s+\d"]
    for agg in patterns.AGGREGATE_FUNCTIONS:
        safe_tokens.append(re.escape(agg))

    safe_pattern = "|".join(safe_tokens)

    cursor.execute(
        """
        SELECT sq.file_path, sq.line_number, sq.query_text,
               GROUP_CONCAT(sqt.table_name) as tables
        FROM sql_queries sq
        LEFT JOIN sql_query_tables sqt
            ON sq.file_path = sqt.query_file
            AND sq.line_number = sqt.query_line
        WHERE sq.command = 'SELECT'
          AND sq.query_text IS NOT NULL
          AND sq.file_path NOT LIKE '%test%'
          AND sq.file_path NOT LIKE '%migration%'
          AND sq.query_text NOT REGEXP ?
        GROUP BY sq.file_path, sq.line_number, sq.query_text
        ORDER BY sq.file_path, sq.line_number
    """,
        (safe_pattern,),
    )

    seen = set()

    for file, line, query, tables in cursor.fetchall():
        query_upper = query.upper()

        if "JOIN" in query_upper or (tables and "," in tables):
            severity = Severity.HIGH
        else:
            severity = Severity.MEDIUM

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="sql-safety-unbounded-query",
                message="SELECT without LIMIT - potential memory issue with large datasets",
                file_path=file,
                line=line,
                severity=severity,
                category="performance",
                snippet=query[:100] + "..." if len(query) > 100 else query,
                cwe_id="CWE-770",
            )
        )

    return findings


def _find_select_star(cursor) -> list[StandardFinding]:
    """Find SELECT * queries that fetch unnecessary columns.

    FIXED: Moved SELECT * check to SQL with regex (handles whitespace variations).
    """
    findings = []

    cursor.execute("""
        SELECT sq.file_path, sq.line_number, sq.query_text,
               GROUP_CONCAT(sqt.table_name) as tables
        FROM sql_queries sq
        LEFT JOIN sql_query_tables sqt
            ON sq.file_path = sqt.query_file
            AND sq.line_number = sqt.query_line
        WHERE sq.command = 'SELECT'
          AND sq.query_text IS NOT NULL
          AND sq.file_path NOT LIKE '%test%'
          AND sq.file_path NOT LIKE '%migration%'
          AND sq.query_text REGEXP '\\bSELECT\\s+\\*\\b'
        GROUP BY sq.file_path, sq.line_number, sq.query_text
        ORDER BY sq.file_path, sq.line_number
    """)

    seen = set()

    for file, line, query, tables in cursor.fetchall():
        table_list = tables.split(",") if tables else []
        severity = Severity.MEDIUM if len(table_list) > 1 else Severity.LOW

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="sql-safety-select-star",
                message="SELECT * query fetches all columns - specify needed columns",
                file_path=file,
                line=line,
                severity=severity,
                category="performance",
                snippet=query[:100] + "..." if len(query) > 100 else query,
                cwe_id="CWE-770",
            )
        )

    return findings


def _find_transactions_without_rollback(
    cursor, patterns: SQLSafetyPatterns
) -> list[StandardFinding]:
    """Find transactions that lack rollback in error handlers.

    FIXED: Used Anti-Join pattern to eliminate N+1 query explosion.
    Single query finds transactions WITHOUT matching rollbacks.
    """
    findings = []

    cursor.execute("""
        WITH transaction_events AS (
            SELECT file, line, callee_function
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%migration%'
              AND callee_function REGEXP '(?i)(transaction|begin)'
        ),
        rollback_events AS (
            SELECT file, line
            FROM function_call_args
            WHERE callee_function REGEXP '(?i)rollback'
        )
        SELECT t1.file, t1.line, t1.callee_function
        FROM transaction_events t1
        LEFT JOIN rollback_events t2
            ON t1.file = t2.file
            AND t2.line BETWEEN t1.line AND (t1.line + 50)
        WHERE t2.file IS NULL
        ORDER BY t1.file, t1.line
    """)

    candidates = cursor.fetchall()

    for file, line, func in candidates:
        cursor.execute(
            """
            SELECT name
            FROM symbols
            WHERE path = ?
              AND line BETWEEN ? AND ?
              AND name IS NOT NULL
              AND name REGEXP '(?i)(catch|except|finally)'
        """,
            (file, line - 5, line + 50),
        )

        has_error_handling = len(cursor.fetchall()) > 0

        if has_error_handling:
            findings.append(
                StandardFinding(
                    rule_name="sql-safety-transaction-no-rollback",
                    message="Transaction without rollback in error handling path",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="reliability",
                    snippet=f"{func}(...)",
                    cwe_id="CWE-667",
                )
            )

    return findings


def _find_connection_leaks(cursor) -> list[StandardFinding]:
    """Find database connections opened but not closed.

    FIXED: Used Anti-Join pattern to eliminate N+1 query explosion.
    """
    findings = []

    cursor.execute("""
        WITH connection_opens AS (
            SELECT file, line, callee_function
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%migration%'
              AND callee_function REGEXP '(?i)(connect|createconnection|getconnection)'
        ),
        connection_closes AS (
            SELECT file, line
            FROM function_call_args
            WHERE callee_function REGEXP '(?i)(close|end|release|destroy)'
        )
        SELECT c1.file, c1.line, c1.callee_function
        FROM connection_opens c1
        LEFT JOIN connection_closes c2
            ON c1.file = c2.file
            AND c2.line BETWEEN c1.line AND (c1.line + 100)
        WHERE c2.file IS NULL
        ORDER BY c1.file, c1.line
    """)

    candidates = cursor.fetchall()

    for file, line, func in candidates:
        cursor.execute(
            """
            SELECT name
            FROM symbols
            WHERE path = ?
              AND line BETWEEN ? AND ?
              AND name IS NOT NULL
              AND name REGEXP '(?i)(with |using)'
        """,
            (file, line - 2, line + 2),
        )

        has_context = len(cursor.fetchall()) > 0

        if not has_context:
            findings.append(
                StandardFinding(
                    rule_name="sql-safety-connection-leak",
                    message="Database connection opened but not closed",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="reliability",
                    snippet=f"{func}(...)",
                    cwe_id="CWE-404",
                )
            )

    return findings


def _find_nested_transactions(cursor, patterns: SQLSafetyPatterns) -> list[StandardFinding]:
    """Find nested transaction starts that could cause deadlocks.

    FIXED: Used window function (LEAD) to eliminate Python grouping and N+1 queries.
    """
    findings = []

    cursor.execute("""
        WITH trans_stream AS (
            SELECT
                file,
                line,
                callee_function,
                CASE
                    WHEN callee_function REGEXP '(?i)(transaction|begin)' THEN 'START'
                    WHEN callee_function REGEXP '(?i)(commit|rollback)' THEN 'END'
                    ELSE 'OTHER'
                END as type
            FROM function_call_args
            WHERE callee_function REGEXP '(?i)(transaction|begin|commit|rollback)'
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%migration%'
        )
        SELECT
            file,
            line,
            callee_function,
            LEAD(callee_function) OVER (PARTITION BY file ORDER BY line) as next_func,
            LEAD(type) OVER (PARTITION BY file ORDER BY line) as next_type,
            LEAD(line) OVER (PARTITION BY file ORDER BY line) as next_line
        FROM trans_stream
        WHERE type = 'START'
    """)

    for file, line, func, next_func, next_type, next_line in cursor.fetchall():
        if next_type == "START" and next_line and (next_line - line < 100):
            findings.append(
                StandardFinding(
                    rule_name="sql-safety-nested-transaction",
                    message="Nested transaction detected - potential deadlock risk",
                    file_path=file,
                    line=next_line,
                    severity=Severity.HIGH,
                    category="reliability",
                    snippet=f"{next_func}(...) nested inside {func}(...)",
                    cwe_id="CWE-667",
                )
            )

    return findings


def _find_large_in_clauses(cursor) -> list[StandardFinding]:
    """Find queries with large IN clauses that could be inefficient.

    FIXED: Moved IN clause check to SQL (was hiding bugs with LIMIT 25).
    """
    findings = []

    cursor.execute("""
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE command != 'UNKNOWN'
          AND query_text IS NOT NULL
          AND LENGTH(query_text) > 150
          AND file_path NOT LIKE '%test%'
          AND file_path NOT LIKE '%migration%'
          AND query_text REGEXP '\\sIN\\s*\\('
        ORDER BY file_path, line_number
    """)

    for file, line, query, command in cursor.fetchall():
        query_upper = query.upper()
        in_pos = query_upper.find(" IN (")

        if in_pos == -1:
            in_pos = query_upper.find(" IN(")

        if in_pos != -1:
            paren_start = in_pos + 4 if " IN(" in query_upper else in_pos + 5
            paren_count = 1
            pos = paren_start + 1

            while pos < len(query) and paren_count > 0:
                if query[pos] == "(":
                    paren_count += 1
                elif query[pos] == ")":
                    paren_count -= 1
                pos += 1

            if pos > paren_start:
                in_content = query[paren_start : pos - 1]

                comma_count = in_content.count(",")

                if comma_count > 50:
                    severity = Severity.HIGH
                elif comma_count > 20:
                    severity = Severity.MEDIUM
                elif comma_count > 10:
                    severity = Severity.LOW
                else:
                    continue

                findings.append(
                    StandardFinding(
                        rule_name="sql-safety-large-in-clause",
                        message=f"{command} query with large IN clause ({comma_count + 1} values)",
                        file_path=file,
                        line=line,
                        severity=severity,
                        category="performance",
                        snippet=query[:100] + "..." if len(query) > 100 else query,
                        cwe_id="CWE-770",
                    )
                )

    return findings


def _find_missing_db_indexes(cursor, patterns: SQLSafetyPatterns) -> list[StandardFinding]:
    """Find queries on potentially unindexed fields (heuristic-based).

    FIXED: Moved WHERE check to SQL (was hiding bugs with LIMIT 30).
    """
    findings = []

    cursor.execute("""
        SELECT sq.file_path, sq.line_number, sq.query_text, sq.command,
               GROUP_CONCAT(sqt.table_name) as tables
        FROM sql_queries sq
        LEFT JOIN sql_query_tables sqt
            ON sq.file_path = sqt.query_file
            AND sq.line_number = sqt.query_line
        WHERE sq.command = 'SELECT'
          AND sq.query_text IS NOT NULL
          AND sq.file_path NOT LIKE '%test%'
          AND sq.file_path NOT LIKE '%migration%'
          AND sq.query_text REGEXP '\\bWHERE\\b'
        GROUP BY sq.file_path, sq.line_number, sq.query_text, sq.command
        ORDER BY sq.file_path, sq.line_number
    """)

    seen = set()

    for file, line, query, command, tables in cursor.fetchall():
        query_lower = query.lower()

        for field in patterns.UNINDEXED_FIELD_PATTERNS:
            if f" {field} =" in query_lower or f".{field} =" in query_lower:
                if "limit" in query_lower or " id " in query_lower:
                    continue

                key = f"{file}:{line}"
                if key in seen:
                    continue
                seen.add(key)

                findings.append(
                    StandardFinding(
                        rule_name="sql-safety-unindexed-field",
                        message=f'Query using potentially unindexed field "{field}"',
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="performance",
                        snippet=query[:100] + "..." if len(query) > 100 else query,
                        cwe_id="CWE-770",
                    )
                )
                break

    return findings
