"""Prisma ORM Security and Performance Analyzer.

Detects security vulnerabilities and performance anti-patterns in Prisma ORM usage:
- SQL injection via raw query methods ($queryRawUnsafe, $executeRawUnsafe)
- Unbounded queries missing pagination (take/skip)
- N+1 query patterns (findMany without includes)
- Missing transaction wrappers around multiple writes
- Unhandled OrThrow methods without error boundaries
- Missing database indexes on common lookup fields
- Connection pool misconfiguration
- Mass assignment via data: req.body passed to create/update (CWE-915)

Tables Used:
- orm_queries: Prisma query calls with pagination and transaction info
- function_call_args: Raw function arguments for injection detection
- prisma_models: Schema model definitions with index info
- assignments: Variable assignments for connection string analysis
- files: File paths for schema detection

CWE References:
- CWE-89: SQL Injection
- CWE-400: Uncontrolled Resource Consumption
- CWE-662: Improper Synchronization
- CWE-755: Improper Handling of Exceptional Conditions
- CWE-770: Allocation of Resources Without Limits
- CWE-915: Improperly Controlled Modification of Dynamically-Determined Object Attributes

Schema Contract Compliance: v2.0 (Fidelity Layer - Q class + RuleDB)
"""

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="prisma_orm_issues",
    category="orm",
    target_extensions=[".ts", ".js", ".tsx", ".jsx", ".mjs", ".cjs"],
    exclude_patterns=[
        "__tests__/",
        "test/",
        "tests/",
        "node_modules/",
        "dist/",
        "build/",
        ".next/",
        "migrations/",
        "prisma/migrations/",
        ".pf/",
        ".auditor_venv/",
    ],
    execution_scope="database",
    primary_table="orm_queries",
)


DB_VAR_PATTERNS = frozenset(
    [
        "DATABASE_URL",
        "DATABASE",
        "POSTGRES",
        "MYSQL",
        "MONGODB",
        "PRISMA",
        "DB_URL",
        "DB_CONNECTION",
    ]
)


UNBOUNDED_METHODS = frozenset(
    [
        "findMany",
        "findManyRaw",
        "aggregateRaw",
        "groupBy",
    ]
)


WRITE_METHODS = frozenset(
    [
        "create",
        "createMany",
        "createManyAndReturn",
        "update",
        "updateMany",
        "delete",
        "deleteMany",
        "upsert",
        "executeRaw",
        "executeRawUnsafe",
    ]
)


THROW_METHODS = frozenset(
    [
        "findUniqueOrThrow",
        "findFirstOrThrow",
    ]
)


RAW_QUERY_METHODS = frozenset(
    [
        "$queryRaw",
        "$queryRawUnsafe",
        "$queryRawTyped",
        "$executeRaw",
        "$executeRawUnsafe",
        "queryRaw",
        "queryRawUnsafe",
        "executeRaw",
        "executeRawUnsafe",
    ]
)


COMMON_INDEX_FIELDS = frozenset(
    [
        "id",
        "email",
        "username",
        "userId",
        "user_id",
        "createdAt",
        "created_at",
        "updatedAt",
        "updated_at",
        "status",
        "type",
        "slug",
        "uuid",
        "externalId",
        "external_id",
    ]
)


CONNECTION_DANGER_PATTERNS = frozenset(
    [
        "connection_limit=100",
        "connection_limit=50",
        "connectionLimit=100",
        "connectionLimit=50",
        "pool_size=100",
        "pool_size=50",
    ]
)


PRISMA_SOURCES = frozenset(
    [
        "findMany",
        "findFirst",
        "findUnique",
        "where",
        "select",
        "include",
        "orderBy",
    ]
)


UNSAFE_INPUT_SOURCES = frozenset(
    [
        "req.body",
        "request.body",
        "body",
        "params",
        "req.params",
        "request.params",
        "req.query",
        "request.query",
        "input",
    ]
)


MASS_ASSIGNMENT_METHODS = frozenset(
    [
        "create",
        "createMany",
        "update",
        "updateMany",
        "upsert",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Prisma ORM security vulnerabilities and performance anti-patterns.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []

        _check_unbounded_queries(db, findings)
        _check_n_plus_one_patterns(db, findings)
        _check_missing_transactions(db, findings)
        _check_unhandled_throw_methods(db, findings)
        _check_sql_injection(db, findings)
        _check_missing_indexes(db, findings)
        _check_connection_config(db, findings)
        _check_unindexed_common_fields(db, findings)
        _check_mass_assignment(db, findings)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_unbounded_queries(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect findMany/aggregateRaw without pagination limits."""
    rows = db.query(
        Q("orm_queries")
        .select("file", "line", "query_type", "has_limit")
        .where("has_limit = 0 OR has_limit IS NULL")
        .order_by("file, line")
    )

    for file, line, query_type, _has_limit in rows:
        if not query_type:
            continue

        method_match = None
        for method in UNBOUNDED_METHODS:
            if f".{method}" in query_type:
                method_match = method
                break

        if not method_match:
            continue

        model = query_type.split(".")[0] if "." in query_type else "unknown"

        findings.append(
            StandardFinding(
                rule_name="prisma-unbounded-query",
                message=f"Unbounded {method_match} on {model} - add take/skip pagination or cursor-based pagination",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="orm",
                confidence=Confidence.HIGH,
                cwe_id="CWE-400",
            )
        )


def _check_n_plus_one_patterns(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect findMany without includes that may cause N+1 queries."""
    rows = db.query(
        Q("orm_queries")
        .select("file", "line", "query_type", "includes")
        .where("includes IS NULL OR includes = '[]' OR includes = '{}' OR includes = ''")
        .order_by("file, line")
    )

    for file, line, query_type, _includes in rows:
        if not query_type or ".findMany" not in query_type:
            continue

        model = query_type.split(".")[0] if "." in query_type else "unknown"

        findings.append(
            StandardFinding(
                rule_name="prisma-n-plus-one",
                message=f"Potential N+1: findMany on {model} without includes - verify if relations are accessed in loop",
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="orm",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-400",
            )
        )


def _check_missing_transactions(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect multiple write operations without transaction wrapper."""
    rows = db.query(
        Q("orm_queries")
        .select("file", "line", "query_type", "has_transaction")
        .order_by("file, line")
    )

    file_operations: dict[str, list[dict]] = {}
    for file, line, query_type, has_transaction in rows:
        if not query_type:
            continue

        is_write = any(f".{method}" in query_type for method in WRITE_METHODS)
        if not is_write:
            continue

        if file not in file_operations:
            file_operations[file] = []

        file_operations[file].append(
            {
                "line": line,
                "query": query_type,
                "has_transaction": has_transaction,
            }
        )

    for file, operations in file_operations.items():
        for i in range(len(operations) - 1):
            op1 = operations[i]
            op2 = operations[i + 1]

            lines_apart = op2["line"] - op1["line"]
            both_unwrapped = not op1["has_transaction"] and not op2["has_transaction"]

            if lines_apart <= 30 and both_unwrapped:
                findings.append(
                    StandardFinding(
                        rule_name="prisma-missing-transaction",
                        message=f"Multiple writes without $transaction: {op1['query']} (line {op1['line']}) and {op2['query']} (line {op2['line']})",
                        file_path=file,
                        line=op1["line"],
                        severity=Severity.HIGH,
                        category="orm",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-662",
                    )
                )
                break


def _check_unhandled_throw_methods(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect OrThrow methods without visible error handling."""
    orm_rows = db.query(
        Q("orm_queries").select("file", "line", "query_type").order_by("file, line")
    )

    for file, line, query_type in orm_rows:
        if not query_type:
            continue

        is_throw_method = any(f".{method}" in query_type for method in THROW_METHODS)
        if not is_throw_method:
            continue

        cfg_rows = db.query(
            Q("cfg_blocks")
            .select("block_type")
            .where("file = ?", file)
            .where("block_type IN ('try', 'catch', 'except', 'finally')")
            .where("start_line <= ? AND end_line >= ?", line + 5, line - 5)
            .limit(1)
        )

        has_error_handling = len(cfg_rows) > 0

        if not has_error_handling:
            method = query_type.split(".")[-1] if "." in query_type else query_type
            findings.append(
                StandardFinding(
                    rule_name="prisma-unhandled-throw",
                    message=f"OrThrow method {method} without visible try/catch - may crash on not found",
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category="orm",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-755",
                )
            )


def _check_sql_injection(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect SQL injection via raw query methods with string interpolation."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func:
            continue

        func_lower = func.lower()
        is_raw_query = "queryraw" in func_lower or "executeraw" in func_lower

        if not is_raw_query:
            continue

        is_unsafe_method = "Unsafe" in func
        has_interpolation = False

        if args:
            interpolation_patterns = ("${", "+", "`", "concat(", ".format(", 'f"', "f'")
            has_interpolation = any(p in args for p in interpolation_patterns)

        if is_unsafe_method or has_interpolation:
            severity = Severity.CRITICAL if is_unsafe_method else Severity.HIGH
            confidence = Confidence.HIGH if is_unsafe_method else Confidence.MEDIUM
            reason = (
                "unsafe method allows arbitrary SQL"
                if is_unsafe_method
                else "string interpolation in query"
            )

            findings.append(
                StandardFinding(
                    rule_name="prisma-sql-injection",
                    message=f"SQL injection risk in {func}: {reason}",
                    file_path=file,
                    line=line,
                    severity=severity,
                    category="orm",
                    confidence=confidence,
                    cwe_id="CWE-89",
                )
            )


def _check_missing_indexes(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect queries on models with few indexed fields."""
    sql, params = Q.raw(
        """
        SELECT p.model_name, COUNT(DISTINCT p.field_name) as indexed_count
        FROM prisma_models p
        WHERE p.is_indexed = 1 OR p.is_unique = 1
        GROUP BY p.model_name
        HAVING indexed_count < 2
        """,
        [],
    )
    poorly_indexed = db.execute(sql, params)
    poorly_indexed_models = {row[0]: row[1] for row in poorly_indexed}

    if not poorly_indexed_models:
        return

    orm_rows = db.query(
        Q("orm_queries").select("file", "line", "query_type").order_by("file, line")
    )

    reported_models: set[str] = set()
    for file, line, query_type in orm_rows:
        if not query_type:
            continue

        is_find_query = any(m in query_type for m in [".findMany", ".findFirst", ".findUnique"])
        if not is_find_query:
            continue

        model = query_type.split(".")[0] if "." in query_type else None
        if not model or model in reported_models:
            continue

        if model in poorly_indexed_models:
            indexed_count = poorly_indexed_models[model]
            reported_models.add(model)
            findings.append(
                StandardFinding(
                    rule_name="prisma-missing-index",
                    message=f"Model {model} has only {indexed_count} indexed field(s) - queries may be slow",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="orm",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-400",
                )
            )


def _check_connection_config(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect database connection configuration issues."""
    file_rows = db.query(Q("files").select("path").limit(500))

    has_prisma_schema = any(
        "schema.prisma" in path or "prisma/schema" in path for (path,) in file_rows
    )

    if not has_prisma_schema:
        return

    assignment_rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, var, expr in assignment_rows:
        if not var:
            continue

        var_upper = var.upper()
        is_db_var = any(pattern in var_upper for pattern in DB_VAR_PATTERNS)

        if not is_db_var:
            continue

        expr_lower = (expr or "").lower()

        if expr and "connection_limit" not in expr_lower and "pool" not in expr_lower:
            findings.append(
                StandardFinding(
                    rule_name="prisma-no-connection-limit",
                    message=f"Database URL in {var} without connection_limit - may exhaust connections under load",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="orm",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-770",
                )
            )

        for danger_pattern in CONNECTION_DANGER_PATTERNS:
            if danger_pattern in expr_lower:
                findings.append(
                    StandardFinding(
                        rule_name="prisma-high-connection-limit",
                        message=f"Connection limit too high in {var} ({danger_pattern}) - may exhaust database connections",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="orm",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-770",
                    )
                )
                break


def _check_unindexed_common_fields(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect common lookup fields that are not indexed."""
    field_list = ", ".join(f"'{f}'" for f in COMMON_INDEX_FIELDS)

    sql, params = Q.raw(
        f"""
        SELECT DISTINCT p.model_name, p.field_name
        FROM prisma_models p
        WHERE p.field_name IN ({field_list})
          AND p.is_indexed = 0
          AND p.is_unique = 0
        """,
        [],
    )
    unindexed_rows = db.execute(sql, params)

    for model_name, field_name in unindexed_rows:
        findings.append(
            StandardFinding(
                rule_name="prisma-unindexed-common-field",
                message=f"Common lookup field '{field_name}' in {model_name} is not indexed - add @unique or @@index",
                file_path="schema.prisma",
                line=0,
                severity=Severity.MEDIUM,
                category="orm",
                confidence=Confidence.HIGH,
                cwe_id="CWE-400",
            )
        )


def _check_mass_assignment(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect mass assignment vulnerabilities - passing req.body directly to data field.

    Prisma's create/update methods accept a data object. If this is populated
    directly from user input (req.body), attackers can overwrite any field.
    Example: prisma.user.create({ data: req.body }) allows setting isAdmin: true
    """
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func or not args:
            continue

        is_prisma_write = any(f".{method}" in func for method in MASS_ASSIGNMENT_METHODS)
        if not is_prisma_write:
            continue

        args_str = str(args)
        args_lower = args_str.lower()

        has_unsafe_input = any(source.lower() in args_lower for source in UNSAFE_INPUT_SOURCES)

        if not has_unsafe_input:
            continue

        has_data_spread = (
            "...req.body" in args_str or "...body" in args_str or "...request.body" in args_str
        )
        has_data_direct = any(
            f"data: {source}" in args_str or f"data:{source}" in args_str.replace(" ", "")
            for source in UNSAFE_INPUT_SOURCES
        )
        has_spread_in_data = "data: {" in args_str and "..." in args_str

        if has_data_spread or has_data_direct or has_spread_in_data:
            model = func.split(".")[-2] if func.count(".") >= 2 else "model"
            method = func.split(".")[-1] if "." in func else func

            findings.append(
                StandardFinding(
                    rule_name="prisma-mass-assignment",
                    message=f"Mass assignment vulnerability: {model}.{method}() receives raw user input in data field",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="orm",
                    snippet=f"{func}({{ data: ... }})"
                    if len(args_str) > 60
                    else f"{func}({args_str})",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-915",
                    additional_info={
                        "remediation": "Whitelist allowed fields: prisma.user.create({ data: { email: body.email, name: body.name } })",
                    },
                )
            )


def register_taint_patterns(taint_registry) -> None:
    """Register Prisma-specific taint patterns for dataflow analysis."""
    for pattern in RAW_QUERY_METHODS:
        taint_registry.register_sink(pattern, "sql", "javascript")
        taint_registry.register_sink(f"prisma.{pattern}", "sql", "javascript")
        taint_registry.register_sink(f"db.{pattern}", "sql", "javascript")

    for pattern in PRISMA_SOURCES:
        taint_registry.register_source(f"prisma.{pattern}", "user_input", "javascript")

    taint_registry.register_sink("prisma.$transaction", "transaction", "javascript")
    taint_registry.register_sink("$transaction", "transaction", "javascript")
