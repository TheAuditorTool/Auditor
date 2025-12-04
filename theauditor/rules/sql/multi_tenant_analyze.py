"""Multi-Tenant Security Analyzer - Phase 2 Clean Implementation."""

import re
import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext


def _regexp_adapter(expr: str, item: str) -> bool:
    """Adapter to let SQLite use Python's regex engine."""
    if item is None:
        return False
    try:
        return re.search(expr, item, re.IGNORECASE) is not None
    except Exception:
        return False


METADATA = RuleMetadata(
    name="multi_tenant",
    category="sql",
    target_extensions=[".py", ".js", ".ts", ".mjs", ".cjs", ".sql"],
    exclude_patterns=["frontend/", "client/", "test/", "__tests__/"],
    execution_scope="database")


@dataclass(frozen=True)
class MultiTenantPatterns:
    """Finite pattern sets for multi-tenant detection - no regex."""

    SENSITIVE_TABLES: frozenset = frozenset(
        [
            "products",
            "orders",
            "inventory",
            "customers",
            "users",
            "locations",
            "transfers",
            "invoices",
            "payments",
            "shipments",
            "accounts",
            "transactions",
            "balances",
            "billing",
            "subscriptions",
            "zones",
            "batches",
            "plants",
            "harvests",
            "workers",
            "facilities",
        ]
    )

    TENANT_FIELDS: frozenset = frozenset(
        ["facility_id", "tenant_id", "organization_id", "company_id", "store_id", "account_id"]
    )

    RLS_CONTEXT: frozenset = frozenset(
        [
            "SET LOCAL app.current_facility_id",
            "SET LOCAL app.current_tenant_id",
            "SET LOCAL app.current_account_id",
            "current_setting",
        ]
    )

    SUPERUSER_NAMES: frozenset = frozenset(
        ["postgres", "root", "admin", "superuser", "sa", "administrator"]
    )

    TRANSACTION_KEYWORDS: frozenset = frozenset(
        [
            "transaction",
            "sequelize.transaction",
            "db.transaction",
            "begin",
            "BEGIN",
            "start_transaction",
        ]
    )


def find_multi_tenant_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect multi-tenant security issues using database queries."""
    findings = []

    if not context.db_path:
        return findings

    patterns = MultiTenantPatterns()
    conn = sqlite3.connect(context.db_path)

    conn.create_function("REGEXP", 2, _regexp_adapter)

    cursor = conn.cursor()

    try:
        findings.extend(_find_queries_without_tenant_filter(cursor, patterns))
        findings.extend(_find_rls_policies_without_using(cursor, patterns))
        findings.extend(_find_direct_id_access(cursor, patterns))
        findings.extend(_find_bulk_operations_without_tenant(cursor, patterns))
        findings.extend(_find_cross_tenant_joins(cursor, patterns))
        findings.extend(_find_subquery_without_tenant(cursor, patterns))

        findings.extend(_find_missing_rls_context(cursor, patterns))
        findings.extend(_find_raw_query_without_transaction(cursor, patterns))
        findings.extend(_find_superuser_connections(cursor, patterns))

        findings.extend(_find_orm_missing_tenant_scope(cursor, patterns))

    finally:
        conn.close()

    return findings


def _find_queries_without_tenant_filter(
    cursor, patterns: MultiTenantPatterns
) -> list[StandardFinding]:
    """Find queries on sensitive tables without tenant filtering."""
    findings = []

    sensitive_pattern = "|".join(re.escape(t) for t in patterns.SENSITIVE_TABLES)
    tenant_pattern = "|".join(re.escape(f) for f in patterns.TENANT_FIELDS)

    cursor.execute(
        """
        SELECT sq.file_path, sq.line_number, sq.query_text, sq.command,
               GROUP_CONCAT(sqt.table_name) as tables
        FROM sql_queries sq
        LEFT JOIN sql_query_tables sqt
            ON sq.file_path = sqt.query_file
            AND sq.line_number = sqt.query_line
        WHERE sq.command != 'UNKNOWN'
          AND sq.command IS NOT NULL
          AND sq.file_path NOT LIKE '%migration%'
          AND sq.file_path NOT LIKE '%test%'
          AND (sqt.table_name REGEXP ? OR sq.query_text REGEXP ?)
          AND sq.query_text NOT REGEXP ?
        GROUP BY sq.file_path, sq.line_number, sq.query_text, sq.command
        ORDER BY sq.file_path, sq.line_number
    """,
        (sensitive_pattern, sensitive_pattern, tenant_pattern),
    )

    for file, line, query, command, tables in cursor.fetchall():
        query_lower = query.lower()

        if "where" in query_lower:
            severity = Severity.HIGH
            message = (
                f"{command} on sensitive table ({tables or 'unknown'}) without tenant filtering"
            )
        else:
            severity = Severity.CRITICAL
            message = f"{command} on sensitive table ({tables or 'unknown'}) with NO WHERE clause - cross-tenant leak"

        findings.append(
            StandardFinding(
                rule_name="multi-tenant-missing-filter",
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="security",
                snippet=query[:100] + "..." if len(query) > 100 else query,
                cwe_id="CWE-863",
            )
        )

    return findings


def _find_rls_policies_without_using(
    cursor, patterns: MultiTenantPatterns
) -> list[StandardFinding]:
    """Find CREATE POLICY statements without proper USING clause."""
    findings = []

    cursor.execute("""
        SELECT file_path, line_number, query_text
        FROM sql_queries
        WHERE command != 'UNKNOWN'
        ORDER BY file_path, line_number
    """)

    for file, line, query in cursor.fetchall():
        query_upper = query.upper()
        if "CREATE POLICY" not in query_upper and "create policy" not in query.lower():
            continue

        if "USING" not in query_upper:
            findings.append(
                StandardFinding(
                    rule_name="multi-tenant-rls-no-using",
                    message="CREATE POLICY without USING clause for row filtering",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    snippet=query[:100] + "..." if len(query) > 100 else query,
                    cwe_id="CWE-863",
                )
            )
        else:
            query_lower = query.lower()
            has_tenant_check = any(field in query_lower for field in patterns.TENANT_FIELDS)
            has_current_setting = "current_setting" in query_lower

            if not (has_tenant_check or has_current_setting):
                findings.append(
                    StandardFinding(
                        rule_name="multi-tenant-rls-weak-using",
                        message="RLS policy USING clause missing tenant field validation",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=query[:100] + "..." if len(query) > 100 else query,
                        cwe_id="CWE-863",
                    )
                )

    return findings


def _find_direct_id_access(cursor, patterns: MultiTenantPatterns) -> list[StandardFinding]:
    """Find queries accessing records by ID without tenant validation."""
    findings = []

    tenant_pattern = "|".join(re.escape(f) for f in patterns.TENANT_FIELDS)

    cursor.execute(
        """
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE command IN ('SELECT', 'UPDATE', 'DELETE')
          AND file_path NOT LIKE '%migration%'
          AND file_path NOT LIKE '%test%'
          AND query_text REGEXP '\\bWHERE\\s+("|`)?id("|`)?\\s*='
          AND query_text NOT REGEXP ?
        ORDER BY file_path, line_number
    """,
        (tenant_pattern,),
    )

    for file, line, query, command in cursor.fetchall():
        findings.append(
            StandardFinding(
                rule_name="multi-tenant-direct-id-access",
                message=f"{command} by ID without tenant validation - potential cross-tenant access",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="security",
                snippet=query[:100] + "..." if len(query) > 100 else query,
                cwe_id="CWE-863",
            )
        )

    return findings


def _find_missing_rls_context(cursor, patterns: MultiTenantPatterns) -> list[StandardFinding]:
    """Find transactions without SET LOCAL for RLS context."""
    findings = []

    context_pattern = r"(?i)(set\s+local|current_setting).*(facility_id|tenant_id|account_id)"

    cursor.execute(
        """
        WITH transaction_starts AS (
            SELECT file, line, callee_function
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%migration%'
              AND callee_function REGEXP '(?i)(transaction|begin)'
        ),
        context_setters AS (
            SELECT file, line
            FROM function_call_args
            WHERE argument_expr REGEXP ?
            UNION
            SELECT file_path as file, line_number as line
            FROM sql_queries
            WHERE query_text REGEXP ?
        )
        SELECT t1.file, t1.line, t1.callee_function
        FROM transaction_starts t1
        LEFT JOIN context_setters t2
            ON t1.file = t2.file
            AND t2.line BETWEEN t1.line AND (t1.line + 30)
        WHERE t2.file IS NULL
        ORDER BY t1.file, t1.line
    """,
        (context_pattern, context_pattern),
    )

    for file, line, func in cursor.fetchall():
        findings.append(
            StandardFinding(
                rule_name="multi-tenant-missing-rls-context",
                message="Transaction without SET LOCAL app.current_facility_id",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="security",
                snippet=f"{func}(...)",
                cwe_id="CWE-863",
            )
        )

    return findings


def _find_superuser_connections(cursor, patterns: MultiTenantPatterns) -> list[StandardFinding]:
    """Find usage of superuser database connections that bypass RLS."""
    findings = []

    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, var, expr in cursor.fetchall():
        var_upper = var.upper()
        if not (
            "DB_USER" in var_upper
            or "DATABASE_USER" in var_upper
            or "POSTGRES_USER" in var_upper
            or "PG_USER" in var_upper
        ):
            continue

        expr_lower = expr.lower()

        for superuser in patterns.SUPERUSER_NAMES:
            if superuser in expr_lower:
                findings.append(
                    StandardFinding(
                        rule_name="multi-tenant-bypass-rls-superuser",
                        message=f'Using superuser "{superuser}" bypasses RLS policies',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="security",
                        snippet=f'{var} = "{superuser}"',
                        cwe_id="CWE-250",
                    )
                )
                break

    return findings


def _find_raw_query_without_transaction(
    cursor, patterns: MultiTenantPatterns
) -> list[StandardFinding]:
    """Find raw SQL queries executed outside transaction context."""
    findings = []

    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
        ORDER BY file, line
    """)

    raw_queries = []
    for file, line, func, args in cursor.fetchall():
        func_lower = func.lower()
        if ".query" in func_lower or ".raw" in func_lower:
            raw_queries.append((file, line, func, args))
            if len(raw_queries) >= 30:
                break

    for file, line, func, args in raw_queries:
        cursor.execute(
            """
            SELECT callee_function
            FROM function_call_args
            WHERE file = ?
              AND line BETWEEN ? AND ?
              AND callee_function IS NOT NULL
        """,
            (file, line - 30, line + 5),
        )

        transaction_count = 0
        for (nearby_func,) in cursor.fetchall():
            func_lower = nearby_func.lower()
            if "transaction" in func_lower or "begin" in func_lower:
                transaction_count += 1

        in_transaction = transaction_count > 0

        if not in_transaction:
            args_lower = (args or "").lower()
            has_sensitive = any(table in args_lower for table in patterns.SENSITIVE_TABLES)

            if has_sensitive:
                findings.append(
                    StandardFinding(
                        rule_name="multi-tenant-raw-query-no-transaction",
                        message="Raw SQL on sensitive table outside transaction - RLS context may not apply",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=f"{func}(...)",
                        cwe_id="CWE-863",
                    )
                )

    return findings


def _find_orm_missing_tenant_scope(cursor, patterns: MultiTenantPatterns) -> list[StandardFinding]:
    """Find ORM queries without tenant filtering using orm_queries table."""
    findings = []

    sensitive_pattern = "|".join(re.escape(t) for t in patterns.SENSITIVE_TABLES)
    tenant_pattern = "(?i)(facility_id|tenant_id|account_id)"

    cursor.execute(
        """
        SELECT o.file, o.line, o.query_type
        FROM orm_queries o
        LEFT JOIN assignments a
            ON o.file = a.file
            AND a.line BETWEEN (o.line - 5) AND (o.line + 5)
            AND a.source_expr REGEXP ?
        WHERE o.query_type IS NOT NULL
          AND o.file NOT LIKE '%test%'
          AND o.file NOT LIKE '%migration%'
          AND o.query_type REGEXP '(?i)\\.(findall|findone)'
          AND o.query_type REGEXP ?
          AND a.file IS NULL
        ORDER BY o.file, o.line
    """,
        (tenant_pattern, sensitive_pattern),
    )

    seen = set()

    for file, line, query_type in cursor.fetchall():
        model_name = query_type.split(".")[0] if "." in query_type else query_type

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                rule_name="multi-tenant-orm-no-tenant-scope",
                message=f"ORM query on {model_name} without tenant filtering",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="security",
                snippet=query_type,
                cwe_id="CWE-863",
            )
        )

    return findings


def _find_bulk_operations_without_tenant(
    cursor, patterns: MultiTenantPatterns
) -> list[StandardFinding]:
    """Find bulk INSERT/UPDATE/DELETE operations without tenant field."""
    findings = []

    sensitive_pattern = "|".join(re.escape(t) for t in patterns.SENSITIVE_TABLES)
    tenant_pattern = "|".join(re.escape(f) for f in patterns.TENANT_FIELDS)

    cursor.execute(
        """
        SELECT sq.file_path, sq.line_number, sq.query_text, sq.command,
               GROUP_CONCAT(sqt.table_name) as tables
        FROM sql_queries sq
        LEFT JOIN sql_query_tables sqt
            ON sq.file_path = sqt.query_file
            AND sq.line_number = sqt.query_line
        WHERE sq.command IN ('INSERT', 'UPDATE', 'DELETE')
          AND sq.file_path NOT LIKE '%migration%'
          AND sq.file_path NOT LIKE '%test%'
          AND (sqt.table_name REGEXP ? OR sq.query_text REGEXP ?)
          AND sq.query_text NOT REGEXP ?
        GROUP BY sq.file_path, sq.line_number, sq.query_text, sq.command
        ORDER BY sq.file_path, sq.line_number
    """,
        (sensitive_pattern, sensitive_pattern, tenant_pattern),
    )

    for file, line, query, command, _tables in cursor.fetchall():
        if command == "INSERT":
            severity = Severity.HIGH
            message = "Bulk INSERT without tenant field - data will be unfiltered"
        elif command == "UPDATE":
            severity = Severity.CRITICAL
            message = "Bulk UPDATE without tenant field - cross-tenant data leak"
        else:
            severity = Severity.CRITICAL
            message = "Bulk DELETE without tenant field - cross-tenant data deletion"

        findings.append(
            StandardFinding(
                rule_name="multi-tenant-bulk-operation-no-tenant",
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="security",
                snippet=query[:100] + "..." if len(query) > 100 else query,
                cwe_id="CWE-863",
            )
        )

    return findings


def _find_cross_tenant_joins(cursor, patterns: MultiTenantPatterns) -> list[StandardFinding]:
    """Find JOINs between tables without tenant field in ON clause."""
    findings = []

    cursor.execute("""
        SELECT sq.file_path, sq.line_number, sq.query_text, sq.command,
               GROUP_CONCAT(sqt.table_name) as tables
        FROM sql_queries sq
        LEFT JOIN sql_query_tables sqt
            ON sq.file_path = sqt.query_file
            AND sq.line_number = sqt.query_line
        WHERE sq.command = 'SELECT'
          AND sq.file_path NOT LIKE '%migration%'
          AND sq.file_path NOT LIKE '%test%'
          AND sq.query_text REGEXP '(?i)\\bJOIN\\b'
          AND sq.query_text REGEXP '(?i)\\bON\\b'
        GROUP BY sq.file_path, sq.line_number, sq.query_text, sq.command
        ORDER BY sq.file_path, sq.line_number
    """)

    for file, line, query, _command, _tables in cursor.fetchall():
        query_lower = query.lower()

        on_start = query_lower.find(" on ")
        if on_start != -1:
            on_clause = query[on_start : on_start + 200]

            has_tenant_in_on = any(field in on_clause.lower() for field in patterns.TENANT_FIELDS)

            if not has_tenant_in_on:
                findings.append(
                    StandardFinding(
                        rule_name="multi-tenant-cross-tenant-join",
                        message="JOIN without tenant field in ON clause - potential cross-tenant data leak",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=query[:100] + "..." if len(query) > 100 else query,
                        cwe_id="CWE-863",
                    )
                )

    return findings


def _find_subquery_without_tenant(cursor, patterns: MultiTenantPatterns) -> list[StandardFinding]:
    """Find subqueries on sensitive tables without tenant filtering."""
    findings = []

    sensitive_pattern = "|".join(re.escape(t) for t in patterns.SENSITIVE_TABLES)

    cursor.execute(
        """
        SELECT file_path, line_number, query_text, command
        FROM sql_queries
        WHERE command = 'SELECT'
          AND file_path NOT LIKE '%migration%'
          AND file_path NOT LIKE '%test%'
          AND query_text REGEXP '(?i)\\(\\s*SELECT'
          AND query_text REGEXP ?
        ORDER BY file_path, line_number
    """,
        (sensitive_pattern,),
    )

    for file, line, query, _command in cursor.fetchall():
        query_lower = query.lower()

        subquery_start = query_lower.find("(select")
        if subquery_start != -1:
            subquery_end = query_lower.find(")", subquery_start)
            if subquery_end != -1:
                subquery = query_lower[subquery_start:subquery_end]

                has_where = "where" in subquery
                has_tenant = any(field in subquery for field in patterns.TENANT_FIELDS)

                if has_where and not has_tenant:
                    findings.append(
                        StandardFinding(
                            rule_name="multi-tenant-subquery-no-tenant",
                            message="Subquery on sensitive table without tenant filtering",
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category="security",
                            snippet=query[:100] + "..." if len(query) > 100 else query,
                            cwe_id="CWE-863",
                        )
                    )
                elif not has_where:
                    findings.append(
                        StandardFinding(
                            rule_name="multi-tenant-subquery-no-where",
                            message="Subquery on sensitive table without WHERE clause",
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="security",
                            snippet=query[:100] + "..." if len(query) > 100 else query,
                            cwe_id="CWE-863",
                        )
                    )

    return findings
