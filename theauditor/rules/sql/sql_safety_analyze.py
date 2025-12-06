"""SQL Safety Analyzer - CWE-20, CWE-404, CWE-667, CWE-770.

Detects SQL safety and reliability issues:
1. UPDATE/DELETE without WHERE clause (data destruction risk)
2. Unbounded SELECT queries (memory exhaustion)
3. SELECT * queries (over-fetching)
4. Large IN clauses (performance)
5. Transactions without rollback handling
6. Nested transactions (deadlock risk)
7. Connection leaks
8. Queries on potentially unindexed fields
"""

import re

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q
from theauditor.rules.sql.utils import register_regexp, truncate

METADATA = RuleMetadata(
    name="sql_safety",
    category="security",
    target_extensions=[".py", ".js", ".ts", ".mjs", ".cjs", ".java", ".go"],
    exclude_patterns=[
        "node_modules/",
        ".venv/",
        "__pycache__/",
        "frontend/",
        "client/",
        "migrations/",
        "test/",
        "tests/",
        "__tests__/",
    ],
    execution_scope="database",
    primary_table="sql_queries",
)


AGGREGATE_FUNCTIONS = frozenset(
    [
        "COUNT(",
        "MAX(",
        "MIN(",
        "SUM(",
        "AVG(",
        "GROUP BY",
        "DISTINCT",
        "HAVING",
    ]
)


TRANSACTION_KEYWORDS = frozenset(
    [
        "transaction",
        "begin",
        "start_transaction",
        "beginTransaction",
        "BEGIN",
        "START TRANSACTION",
        "db.transaction",
        "sequelize.transaction",
        "withTransaction",
        "startTransaction",
    ]
)


POTENTIALLY_UNINDEXED_FIELDS = frozenset(
    [
        "email",
        "username",
        "status",
        "created_at",
        "updated_at",
        "name",
        "title",
        "description",
        "type",
        "state",
        "phone",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect SQL safety issues in indexed codebase.

    Args:
        context: Provides db_path and other context

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    findings: list[StandardFinding] = []

    with RuleDB(context.db_path, METADATA.name) as db:
        register_regexp(db.conn)

        findings.extend(_check_update_without_where(db))
        findings.extend(_check_delete_without_where(db))

        findings.extend(_check_unbounded_queries(db))
        findings.extend(_check_select_star(db))
        findings.extend(_check_large_in_clauses(db))
        findings.extend(_check_unindexed_fields(db))

        findings.extend(_check_transactions_without_rollback(db))
        findings.extend(_check_nested_transactions(db))
        findings.extend(_check_connection_leaks(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_update_without_where(db: RuleDB) -> list[StandardFinding]:
    """Find UPDATE statements without WHERE clause."""
    findings = []
    seen = set()

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text")
        .where("command = ?", "UPDATE")
        .where("query_text IS NOT NULL")
        .where("file_path NOT LIKE ?", "%test%")
        .where("file_path NOT LIKE ?", "%migration%")
        .where("query_text NOT REGEXP ?", r"\bWHERE\b")
        .order_by("file_path, line_number")
    )

    for file_path, line_number, query_text in rows:
        key = f"{file_path}:{line_number}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="sql-safety-update-no-where",
                message="UPDATE without WHERE clause affects all rows - data destruction risk",
                file_path=file_path,
                line=line_number,
                severity=Severity.CRITICAL,
                category=METADATA.category,
                snippet=truncate(query_text, 100),
                cwe_id="CWE-20",
            )
        )

    return findings


def _check_delete_without_where(db: RuleDB) -> list[StandardFinding]:
    """Find DELETE statements without WHERE clause."""
    findings = []
    seen = set()

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text")
        .where("command = ?", "DELETE")
        .where("query_text IS NOT NULL")
        .where("file_path NOT LIKE ?", "%test%")
        .where("file_path NOT LIKE ?", "%migration%")
        .where("query_text NOT REGEXP ?", r"\b(WHERE|TRUNCATE)\b")
        .order_by("file_path, line_number")
    )

    for file_path, line_number, query_text in rows:
        key = f"{file_path}:{line_number}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="sql-safety-delete-no-where",
                message="DELETE without WHERE clause removes all rows - data destruction risk",
                file_path=file_path,
                line=line_number,
                severity=Severity.CRITICAL,
                category=METADATA.category,
                snippet=truncate(query_text, 100),
                cwe_id="CWE-20",
            )
        )

    return findings


def _check_unbounded_queries(db: RuleDB) -> list[StandardFinding]:
    """Find SELECT queries without LIMIT that might return large datasets."""
    findings = []
    seen = set()

    safe_tokens = [r"\bLIMIT\b", r"\bTOP\s+\d"]
    for agg in AGGREGATE_FUNCTIONS:
        safe_tokens.append(re.escape(agg))
    safe_pattern = "|".join(safe_tokens)

    sql, params = Q.raw(
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
        [safe_pattern],
    )

    rows = db.execute(sql, params)

    for file_path, line_number, query_text, tables in rows:
        key = f"{file_path}:{line_number}"
        if key in seen:
            continue
        seen.add(key)

        query_upper = query_text.upper()

        if "JOIN" in query_upper or (tables and "," in tables):
            severity = Severity.HIGH
        else:
            severity = Severity.MEDIUM

        findings.append(
            StandardFinding(
                rule_name="sql-safety-unbounded-query",
                message="SELECT without LIMIT - potential memory exhaustion with large datasets",
                file_path=file_path,
                line=line_number,
                severity=severity,
                category="performance",
                snippet=truncate(query_text, 100),
                cwe_id="CWE-770",
            )
        )

    return findings


def _check_select_star(db: RuleDB) -> list[StandardFinding]:
    """Find SELECT * queries that fetch unnecessary columns."""
    findings = []
    seen = set()

    sql, params = Q.raw(
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
          AND sq.query_text REGEXP '\\bSELECT\\s+\\*\\b'
        GROUP BY sq.file_path, sq.line_number, sq.query_text
        ORDER BY sq.file_path, sq.line_number
        """,
        [],
    )

    rows = db.execute(sql, params)

    for file_path, line_number, query_text, tables in rows:
        key = f"{file_path}:{line_number}"
        if key in seen:
            continue
        seen.add(key)

        table_list = tables.split(",") if tables else []
        severity = Severity.MEDIUM if len(table_list) > 1 else Severity.LOW

        findings.append(
            StandardFinding(
                rule_name="sql-safety-select-star",
                message="SELECT * fetches all columns - specify needed columns for better performance",
                file_path=file_path,
                line=line_number,
                severity=severity,
                category="performance",
                snippet=truncate(query_text, 100),
                cwe_id="CWE-770",
            )
        )

    return findings


def _check_large_in_clauses(db: RuleDB) -> list[StandardFinding]:
    """Find queries with large IN clauses that could be inefficient."""
    findings = []

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text", "command")
        .where("command != ?", "UNKNOWN")
        .where("command IS NOT NULL")
        .where("query_text IS NOT NULL")
        .where("file_path NOT LIKE ?", "%test%")
        .where("file_path NOT LIKE ?", "%migration%")
        .where("query_text REGEXP ?", r"\sIN\s*\(")
        .order_by("file_path, line_number")
    )

    for file_path, line_number, query_text, command in rows:
        query_upper = query_text.upper()
        in_pos = query_upper.find(" IN (")
        if in_pos == -1:
            in_pos = query_upper.find(" IN(")

        if in_pos == -1:
            continue

        paren_start = in_pos + 4 if " IN(" in query_upper else in_pos + 5
        paren_count = 1
        pos = paren_start + 1

        while pos < len(query_text) and paren_count > 0:
            if query_text[pos] == "(":
                paren_count += 1
            elif query_text[pos] == ")":
                paren_count -= 1
            pos += 1

        if pos <= paren_start:
            continue

        in_content = query_text[paren_start : pos - 1]
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
                message=f"{command} with large IN clause ({comma_count + 1} values) - consider temp table or JOIN",
                file_path=file_path,
                line=line_number,
                severity=severity,
                category="performance",
                snippet=truncate(query_text, 100),
                cwe_id="CWE-770",
            )
        )

    return findings


def _check_unindexed_fields(db: RuleDB) -> list[StandardFinding]:
    """Find queries on potentially unindexed fields (heuristic-based)."""
    findings = []
    seen = set()

    sql, params = Q.raw(
        """
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
        """,
        [],
    )

    rows = db.execute(sql, params)

    for file_path, line_number, query_text, _command, _tables in rows:
        query_lower = query_text.lower()

        for field in POTENTIALLY_UNINDEXED_FIELDS:
            if f" {field} =" in query_lower or f".{field} =" in query_lower:
                if "limit" in query_lower or " id " in query_lower or " id=" in query_lower:
                    continue

                key = f"{file_path}:{line_number}"
                if key in seen:
                    continue
                seen.add(key)

                findings.append(
                    StandardFinding(
                        rule_name="sql-safety-unindexed-field",
                        message=f'Query filtering on potentially unindexed field "{field}" - consider adding index',
                        file_path=file_path,
                        line=line_number,
                        severity=Severity.LOW,
                        category="performance",
                        snippet=truncate(query_text, 100),
                        cwe_id="CWE-770",
                    )
                )
                break

    return findings


def _check_transactions_without_rollback(db: RuleDB) -> list[StandardFinding]:
    """Find transactions that lack rollback in error handlers."""
    findings = []

    sql, params = Q.raw(
        """
        WITH transaction_events AS (
            SELECT file, line, callee_function
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%migration%'
              AND callee_function REGEXP '(?i)(transaction|begin|beginTransaction|startTransaction)'
        ),
        rollback_events AS (
            SELECT file, line
            FROM function_call_args
            WHERE callee_function REGEXP '(?i)rollback'
        ),
        error_handlers AS (
            SELECT path as file, line
            FROM symbols
            WHERE type IN ('except_handler', 'catch_clause', 'finally_clause')
        )
        SELECT t1.file, t1.line, t1.callee_function
        FROM transaction_events t1
        LEFT JOIN rollback_events t2
            ON t1.file = t2.file
            AND t2.line BETWEEN t1.line AND (t1.line + 50)
        INNER JOIN error_handlers eh
            ON t1.file = eh.file
            AND eh.line BETWEEN (t1.line - 5) AND (t1.line + 50)
        WHERE t2.file IS NULL
        ORDER BY t1.file, t1.line
        """,
        [],
    )

    rows = db.execute(sql, params)

    for file, line, func in rows:
        findings.append(
            StandardFinding(
                rule_name="sql-safety-transaction-no-rollback",
                message=f"Transaction {func}() has error handling but no rollback",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="reliability",
                snippet=f"{func}(...)",
                cwe_id="CWE-667",
            )
        )

    return findings


def _check_nested_transactions(db: RuleDB) -> list[StandardFinding]:
    """Find nested transaction starts that could cause deadlocks."""
    findings = []

    sql, params = Q.raw(
        """
        WITH trans_stream AS (
            SELECT
                file,
                line,
                callee_function,
                CASE
                    WHEN callee_function REGEXP '(?i)(transaction|begin|beginTransaction|startTransaction)' THEN 'START'
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
        """,
        [],
    )

    rows = db.execute(sql, params)

    for file, line, func, next_func, next_type, next_line in rows:
        if next_type == "START" and next_line and (next_line - line < 100):
            findings.append(
                StandardFinding(
                    rule_name="sql-safety-nested-transaction",
                    message=f"Potential nested transaction (heuristic) - {next_func}() after {func}() - verify control flow manually",
                    file_path=file,
                    line=next_line,
                    severity=Severity.LOW,
                    category="reliability",
                    snippet=f"{next_func}(...) after {func}(...)",
                    cwe_id="CWE-667",
                )
            )

    return findings


def _check_connection_leaks(db: RuleDB) -> list[StandardFinding]:
    """Find database connections opened but not closed."""
    findings = []

    sql, params = Q.raw(
        """
        WITH connection_opens AS (
            SELECT file, line, callee_function
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%migration%'
              AND callee_function REGEXP '(?i)(connect|createConnection|getConnection|createPool)'
        ),
        connection_closes AS (
            SELECT file, line
            FROM function_call_args
            WHERE callee_function REGEXP '(?i)(close|end|release|destroy|disconnect)'
        ),
        context_managers AS (
            SELECT path as file, line
            FROM symbols
            WHERE type IN ('with_statement', 'using_statement')
        )
        SELECT c1.file, c1.line, c1.callee_function
        FROM connection_opens c1
        LEFT JOIN connection_closes c2
            ON c1.file = c2.file
            AND c2.line BETWEEN c1.line AND (c1.line + 100)
        LEFT JOIN context_managers cm
            ON c1.file = cm.file
            AND cm.line BETWEEN (c1.line - 2) AND (c1.line + 2)
        WHERE c2.file IS NULL
          AND cm.file IS NULL
        ORDER BY c1.file, c1.line
        """,
        [],
    )

    rows = db.execute(sql, params)

    for file, line, func in rows:
        findings.append(
            StandardFinding(
                rule_name="sql-safety-connection-leak",
                message=f"Database connection {func}() opened but not closed - resource leak",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="reliability",
                snippet=f"{func}(...)",
                cwe_id="CWE-404",
            )
        )

    return findings
