"""Multi-Tenant Security Analyzer - CWE-863.

Detects multi-tenancy isolation violations:
1. Queries on sensitive tables without tenant filtering
2. RLS policies without proper USING clause
3. Direct ID access without tenant validation
4. Bulk operations without tenant scope
5. Cross-tenant JOINs
6. Subqueries without tenant filtering
7. Missing RLS context in transactions
8. Superuser connections bypassing RLS
9. ORM queries without tenant scope
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
    name="multi_tenant",
    category="security",
    target_extensions=[".py", ".js", ".ts", ".mjs", ".cjs", ".sql"],
    exclude_patterns=[
        "node_modules/",
        ".venv/",
        "__pycache__/",
        "frontend/",
        "client/",
        "test/",
        "tests/",
        "__tests__/",
        "migrations/",
        "seeds/",
        "fixtures/",
    ],
    execution_scope="database",
    primary_table="sql_queries",
)


SENSITIVE_TABLES = frozenset(
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
        "documents",
        "files",
        "messages",
        "notifications",
        "settings",
        "profiles",
        "permissions",
        "roles",
        "audit_logs",
        "events",
    ]
)


TENANT_FIELDS = frozenset(
    [
        "facility_id",
        "tenant_id",
        "organization_id",
        "company_id",
        "store_id",
        "account_id",
        "org_id",
        "workspace_id",
        "client_id",
        "team_id",
        "site_id",
        "branch_id",
        "merchant_id",
    ]
)


RLS_CONTEXT_PATTERNS = frozenset(
    [
        "SET LOCAL app.current_facility_id",
        "SET LOCAL app.current_tenant_id",
        "SET LOCAL app.current_account_id",
        "SET LOCAL app.current_org_id",
        "current_setting",
        "set_config",
    ]
)


SUPERUSER_NAMES = frozenset(
    [
        "postgres",
        "root",
        "admin",
        "superuser",
        "sa",
        "administrator",
        "dba",
        "sysadmin",
        "master",
    ]
)


TRANSACTION_KEYWORDS = frozenset(
    [
        "transaction",
        "sequelize.transaction",
        "db.transaction",
        "begin",
        "start_transaction",
        "withTransaction",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect multi-tenant security issues in indexed codebase.

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

        findings.extend(_check_queries_without_tenant_filter(db))
        findings.extend(_check_rls_policies(db))
        findings.extend(_check_direct_id_access(db))
        findings.extend(_check_bulk_operations(db))
        findings.extend(_check_cross_tenant_joins(db))
        findings.extend(_check_subqueries(db))
        findings.extend(_check_missing_rls_context(db))
        findings.extend(_check_superuser_connections(db))
        findings.extend(_check_raw_query_outside_transaction(db))
        findings.extend(_check_orm_missing_tenant(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_queries_without_tenant_filter(db: RuleDB) -> list[StandardFinding]:
    """Find queries on sensitive tables without tenant filtering."""
    findings = []

    sensitive_pattern = "|".join(re.escape(t) for t in SENSITIVE_TABLES)
    tenant_pattern = "|".join(re.escape(f) for f in TENANT_FIELDS)

    sql, params = Q.raw(
        """
        SELECT sq.file_path, sq.line_number, sq.query_text, sq.command,
               GROUP_CONCAT(sqt.table_name) as tables
        FROM sql_queries sq
        LEFT JOIN sql_query_tables sqt
            ON sq.file_path = sqt.query_file
            AND sq.line_number = sqt.query_line
        WHERE sq.command IS NOT NULL
          AND sq.command != 'UNKNOWN'
          AND sq.file_path NOT LIKE '%migration%'
          AND sq.file_path NOT LIKE '%test%'
          AND sq.file_path NOT LIKE '%seed%'
          AND sq.file_path NOT LIKE '%fixture%'
          AND (sqt.table_name REGEXP ? OR sq.query_text REGEXP ?)
          AND sq.query_text NOT REGEXP ?
        GROUP BY sq.file_path, sq.line_number, sq.query_text, sq.command
        ORDER BY sq.file_path, sq.line_number
        """,
        [sensitive_pattern, sensitive_pattern, tenant_pattern],
    )

    rows = db.execute(sql, params)

    for file_path, line_number, query_text, command, tables in rows:
        query_lower = query_text.lower()

        if "where" in query_lower:
            severity = Severity.MEDIUM
            message = f"{command} on sensitive table ({tables or 'unknown'}) without explicit tenant filter (IDOR risk)"
        else:
            severity = Severity.CRITICAL
            message = f"{command} on sensitive table ({tables or 'unknown'}) with NO WHERE clause - data leak"

        findings.append(
            StandardFinding(
                rule_name="multi-tenant-missing-filter",
                message=message,
                file_path=file_path,
                line=line_number,
                severity=severity,
                category=METADATA.category,
                snippet=truncate(query_text, 100),
                cwe_id="CWE-863",
            )
        )

    return findings


def _check_rls_policies(db: RuleDB) -> list[StandardFinding]:
    """Find CREATE POLICY statements without proper USING clause."""
    findings = []

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text")
        .where("command IS NOT NULL")
        .where("command != ?", "UNKNOWN")
        .order_by("file_path, line_number")
    )

    for file_path, line_number, query_text in rows:
        query_upper = query_text.upper()

        if "CREATE POLICY" not in query_upper:
            continue

        if "USING" not in query_upper:
            findings.append(
                StandardFinding(
                    rule_name="multi-tenant-rls-no-using",
                    message="CREATE POLICY without USING clause for row filtering",
                    file_path=file_path,
                    line=line_number,
                    severity=Severity.CRITICAL,
                    category=METADATA.category,
                    snippet=truncate(query_text, 100),
                    cwe_id="CWE-863",
                )
            )
        else:
            query_lower = query_text.lower()
            has_tenant_check = any(field in query_lower for field in TENANT_FIELDS)
            has_current_setting = "current_setting" in query_lower

            if not (has_tenant_check or has_current_setting):
                findings.append(
                    StandardFinding(
                        rule_name="multi-tenant-rls-weak-using",
                        message="RLS policy USING clause missing tenant field validation",
                        file_path=file_path,
                        line=line_number,
                        severity=Severity.HIGH,
                        category=METADATA.category,
                        snippet=truncate(query_text, 100),
                        cwe_id="CWE-863",
                    )
                )

    return findings


def _check_direct_id_access(db: RuleDB) -> list[StandardFinding]:
    """Find queries accessing records by ID without tenant validation."""
    findings = []

    tenant_pattern = "|".join(re.escape(f) for f in TENANT_FIELDS)

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text", "command")
        .where("command IN (?, ?, ?)", "SELECT", "UPDATE", "DELETE")
        .where("file_path NOT LIKE ?", "%migration%")
        .where("file_path NOT LIKE ?", "%test%")
        .where("query_text REGEXP ?", r'\bWHERE\s+["`]?id["`]?\s*=')
        .where("query_text NOT REGEXP ?", tenant_pattern)
        .order_by("file_path, line_number")
    )

    for file_path, line_number, query_text, command in rows:
        findings.append(
            StandardFinding(
                rule_name="multi-tenant-direct-id-access",
                message=f"{command} by ID without tenant validation - potential cross-tenant access",
                file_path=file_path,
                line=line_number,
                severity=Severity.HIGH,
                category=METADATA.category,
                snippet=truncate(query_text, 100),
                cwe_id="CWE-863",
            )
        )

    return findings


def _check_bulk_operations(db: RuleDB) -> list[StandardFinding]:
    """Find bulk INSERT/UPDATE/DELETE without tenant field."""
    findings = []

    sensitive_pattern = "|".join(re.escape(t) for t in SENSITIVE_TABLES)
    tenant_pattern = "|".join(re.escape(f) for f in TENANT_FIELDS)

    sql, params = Q.raw(
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
        [sensitive_pattern, sensitive_pattern, tenant_pattern],
    )

    rows = db.execute(sql, params)

    for file_path, line_number, query_text, command, _tables in rows:
        if command == "INSERT":
            severity = Severity.HIGH
            message = "Bulk INSERT without tenant field - data will be unfiltered"
        elif command == "UPDATE":
            severity = Severity.CRITICAL
            message = "Bulk UPDATE without tenant field - cross-tenant data modification"
        else:
            severity = Severity.CRITICAL
            message = "Bulk DELETE without tenant field - cross-tenant data deletion"

        findings.append(
            StandardFinding(
                rule_name="multi-tenant-bulk-no-tenant",
                message=message,
                file_path=file_path,
                line=line_number,
                severity=severity,
                category=METADATA.category,
                snippet=truncate(query_text, 100),
                cwe_id="CWE-863",
            )
        )

    return findings


def _check_cross_tenant_joins(db: RuleDB) -> list[StandardFinding]:
    """Find JOINs between tables without tenant field in ON clause."""
    findings = []

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text", "command")
        .where("command = ?", "SELECT")
        .where("file_path NOT LIKE ?", "%migration%")
        .where("file_path NOT LIKE ?", "%test%")
        .where("query_text REGEXP ?", r"(?i)\bJOIN\b")
        .where("query_text REGEXP ?", r"(?i)\bON\b")
        .order_by("file_path, line_number")
    )

    for file_path, line_number, query_text, _command in rows:
        query_lower = query_text.lower()

        on_start = query_lower.find(" on ")
        if on_start == -1:
            continue

        on_clause = query_text[on_start : on_start + 200]
        has_tenant_in_on = any(field in on_clause.lower() for field in TENANT_FIELDS)

        if not has_tenant_in_on:
            findings.append(
                StandardFinding(
                    rule_name="multi-tenant-cross-tenant-join",
                    message="JOIN without tenant field in ON clause - potential cross-tenant data leak",
                    file_path=file_path,
                    line=line_number,
                    severity=Severity.HIGH,
                    category=METADATA.category,
                    snippet=truncate(query_text, 100),
                    cwe_id="CWE-863",
                )
            )

    return findings


def _check_subqueries(db: RuleDB) -> list[StandardFinding]:
    """Find subqueries on sensitive tables without tenant filtering."""
    findings = []

    sensitive_pattern = "|".join(re.escape(t) for t in SENSITIVE_TABLES)

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text", "command")
        .where("command = ?", "SELECT")
        .where("file_path NOT LIKE ?", "%migration%")
        .where("file_path NOT LIKE ?", "%test%")
        .where("query_text REGEXP ?", r"(?i)\(\s*SELECT")
        .where("query_text REGEXP ?", sensitive_pattern)
        .order_by("file_path, line_number")
    )

    for file_path, line_number, query_text, _command in rows:
        query_lower = query_text.lower()

        subquery_start = query_lower.find("(select")
        if subquery_start == -1:
            continue

        subquery_end = query_lower.find(")", subquery_start)
        if subquery_end == -1:
            continue

        subquery = query_lower[subquery_start:subquery_end]
        has_where = "where" in subquery
        has_tenant = any(field in subquery for field in TENANT_FIELDS)

        if has_where and not has_tenant:
            findings.append(
                StandardFinding(
                    rule_name="multi-tenant-subquery-no-tenant",
                    message="Subquery on sensitive table without tenant filtering",
                    file_path=file_path,
                    line=line_number,
                    severity=Severity.HIGH,
                    category=METADATA.category,
                    snippet=truncate(query_text, 100),
                    cwe_id="CWE-863",
                )
            )
        elif not has_where:
            findings.append(
                StandardFinding(
                    rule_name="multi-tenant-subquery-no-where",
                    message="Subquery on sensitive table without WHERE clause",
                    file_path=file_path,
                    line=line_number,
                    severity=Severity.CRITICAL,
                    category=METADATA.category,
                    snippet=truncate(query_text, 100),
                    cwe_id="CWE-863",
                )
            )

    return findings


def _check_missing_rls_context(db: RuleDB) -> list[StandardFinding]:
    """Find transactions without SET LOCAL for RLS context."""
    findings = []

    context_pattern = (
        r"(?i)(set\s+local|current_setting|set_config).*(facility_id|tenant_id|account_id|org_id)"
    )

    sql, params = Q.raw(
        """
        WITH transaction_starts AS (
            SELECT file, line, callee_function
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND file NOT LIKE '%test%'
              AND file NOT LIKE '%migration%'
              AND callee_function REGEXP '(?i)(transaction|begin|withTransaction)'
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
        [context_pattern, context_pattern],
    )

    rows = db.execute(sql, params)

    for file, line, func in rows:
        findings.append(
            StandardFinding(
                rule_name="multi-tenant-missing-rls-context",
                message=f"Transaction {func}() without SET LOCAL for tenant context",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category=METADATA.category,
                snippet=f"{func}(...)",
                cwe_id="CWE-863",
            )
        )

    return findings


def _check_superuser_connections(db: RuleDB) -> list[StandardFinding]:
    """Find usage of superuser database connections that bypass RLS."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, var, expr in rows:
        var_upper = var.upper()

        is_db_user_var = any(
            kw in var_upper
            for kw in [
                "DB_USER",
                "DATABASE_USER",
                "POSTGRES_USER",
                "PG_USER",
                "MYSQL_USER",
                "DB_USERNAME",
                "DATABASE_USERNAME",
            ]
        )

        if not is_db_user_var:
            continue

        expr_lower = expr.lower()

        for superuser in SUPERUSER_NAMES:
            if superuser in expr_lower:
                findings.append(
                    StandardFinding(
                        rule_name="multi-tenant-superuser-bypass",
                        message=f'Using superuser "{superuser}" bypasses RLS policies',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category=METADATA.category,
                        snippet=f'{var} = "{superuser}"',
                        cwe_id="CWE-863",
                    )
                )
                break

    return findings


def _check_raw_query_outside_transaction(db: RuleDB) -> list[StandardFinding]:
    """Find raw SQL queries executed outside transaction context."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("callee_function REGEXP ?", r"(?i)\.(query|raw|execute)")
        .where("file NOT LIKE ?", "%test%")
        .order_by("file, line")
        .limit(100)
    )

    raw_queries = list(rows)

    for file, line, func, args in raw_queries:
        nearby_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ?", file)
            .where("line BETWEEN ? AND ?", line - 30, line + 5)
            .where("callee_function IS NOT NULL")
        )

        in_transaction = any(
            "transaction" in row[0].lower() or "begin" in row[0].lower() for row in nearby_rows
        )

        if in_transaction:
            continue

        args_lower = (args or "").lower()
        has_sensitive = any(table in args_lower for table in SENSITIVE_TABLES)

        if has_sensitive:
            findings.append(
                StandardFinding(
                    rule_name="multi-tenant-raw-no-transaction",
                    message="Raw SQL on sensitive table outside transaction - RLS context may not apply",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category=METADATA.category,
                    snippet=f"{func}(...)",
                    cwe_id="CWE-863",
                )
            )

    return findings


def _check_orm_missing_tenant(db: RuleDB) -> list[StandardFinding]:
    """Find ORM queries without tenant filtering."""
    findings = []
    seen = set()

    sensitive_pattern = "|".join(re.escape(t) for t in SENSITIVE_TABLES)
    tenant_pattern = "(?i)(facility_id|tenant_id|account_id|org_id|organization_id)"

    sql, params = Q.raw(
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
          AND o.query_type REGEXP '(?i)\\.(findAll|findOne|findMany|find|where)'
          AND o.query_type REGEXP ?
          AND a.file IS NULL
        ORDER BY o.file, o.line
        """,
        [tenant_pattern, sensitive_pattern],
    )

    rows = db.execute(sql, params)

    for file, line, query_type in rows:
        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        model_name = query_type.split(".")[0] if "." in query_type else query_type

        findings.append(
            StandardFinding(
                rule_name="multi-tenant-orm-no-tenant",
                message=f"ORM query on {model_name} without tenant filtering",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category=METADATA.category,
                snippet=query_type,
                cwe_id="CWE-863",
            )
        )

    return findings
