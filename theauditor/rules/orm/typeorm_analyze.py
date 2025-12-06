"""TypeORM Security and Performance Analyzer.

Detects security vulnerabilities and performance anti-patterns in TypeORM usage:
- Unbounded queries missing pagination (take/skip/limit)
- N+1 query patterns (multiple findOne calls without relations)
- Missing transaction wrappers around multiple writes
- SQL injection via raw query with string interpolation
- QueryBuilder without pagination (getMany/getRawMany)
- cascade:true which can cause unintended deletions
- synchronize:true which should NEVER be used in production
- Missing indexes on common lookup fields
- Complex multi-join queries without pagination
- EntityManager overuse vs Repository pattern
- Mass assignment via req.body passed to save/insert (CWE-915)
- Exposed sensitive columns without select:false (CWE-200)

Tables Used:
- function_call_args: TypeORM method calls and arguments
- assignments: Configuration detection (cascade, synchronize)
- files: Entity file discovery
- symbols: Field/property detection for index analysis

CWE References:
- CWE-89: SQL Injection
- CWE-200: Exposure of Sensitive Information to an Unauthorized Actor
- CWE-400: Uncontrolled Resource Consumption
- CWE-662: Improper Synchronization
- CWE-665: Improper Initialization
- CWE-672: Operation on Resource After Expiration
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
    name="typeorm_orm_issues",
    category="orm",
    target_extensions=[".ts", ".tsx", ".js", ".mjs"],
    exclude_patterns=[
        "__tests__/",
        "test/",
        "tests/",
        "node_modules/",
        "dist/",
        "build/",
        ".next/",
        "migrations/",
        "migration/",
        ".pf/",
        ".auditor_venv/",
    ],
    execution_scope="database",
    primary_table="function_call_args",
)


UNBOUNDED_METHODS = frozenset(
    [
        "find",
        "findAndCount",
        "getMany",
        "getManyAndCount",
        "getRawMany",
        "getRawAndEntities",
    ]
)


WRITE_METHODS = frozenset(
    [
        "save",
        "insert",
        "update",
        "delete",
        "remove",
        "softDelete",
        "restore",
        "upsert",
        "increment",
        "decrement",
        "create",
    ]
)


QUERYBUILDER_MANY = frozenset(
    [
        "getMany",
        "getManyAndCount",
        "getRawMany",
        "getRawAndEntities",
    ]
)


RAW_QUERY_METHODS = frozenset(
    [
        "query",
        "createQueryBuilder",
        "getQuery",
        "getSql",
        "manager.query",
        "connection.query",
        "entityManager.query",
        "dataSource.query",
        "queryRunner.query",
    ]
)


TRANSACTION_METHODS = frozenset(
    [
        "transaction",
        "startTransaction",
        "commitTransaction",
        "rollbackTransaction",
        "queryRunner.startTransaction",
    ]
)


COMMON_INDEXED_FIELDS = frozenset(
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
        "deletedAt",
        "deleted_at",
        "status",
        "type",
        "slug",
        "code",
        "uuid",
        "tenantId",
        "tenant_id",
    ]
)


TYPEORM_SOURCES = frozenset(
    [
        "find",
        "findOne",
        "findOneBy",
        "findBy",
        "where",
        "andWhere",
        "orWhere",
        "having",
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
        "data",
    ]
)


MASS_ASSIGNMENT_METHODS = frozenset(
    [
        "save",
        "insert",
        "update",
        "create",
        "upsert",
    ]
)


SENSITIVE_FIELD_NAMES = frozenset(
    [
        "password",
        "passwordHash",
        "password_hash",
        "hashedPassword",
        "hashed_password",
        "secret",
        "secretKey",
        "secret_key",
        "apiKey",
        "api_key",
        "apiSecret",
        "api_secret",
        "token",
        "accessToken",
        "access_token",
        "refreshToken",
        "refresh_token",
        "privateKey",
        "private_key",
        "encryptionKey",
        "encryption_key",
        "salt",
        "pin",
        "ssn",
        "creditCard",
        "credit_card",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect TypeORM security vulnerabilities and performance anti-patterns.

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
        _check_sql_injection(db, findings)
        _check_querybuilder_no_limit(db, findings)
        _check_cascade_true(db, findings)
        _check_synchronize_true(db, findings)
        _check_missing_indexes(db, findings)
        _check_complex_joins(db, findings)
        _check_entity_manager_overuse(db, findings)
        _check_mass_assignment(db, findings)
        _check_exposed_secrets(db, findings)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_unbounded_queries(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect repository find methods without pagination."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, method, args in rows:
        if not method:
            continue

        is_unbounded = any(method.endswith(f".{m}") for m in UNBOUNDED_METHODS)
        if not is_unbounded:
            continue

        has_limit = False
        if args:
            args_str = str(args).lower()
            has_limit = any(term in args_str for term in ["limit", "take", "skip", "offset"])

        if not has_limit:
            method_name = method.split(".")[-1] if "." in method else method
            severity = Severity.HIGH if method_name in QUERYBUILDER_MANY else Severity.MEDIUM

            findings.append(
                StandardFinding(
                    rule_name="typeorm-unbounded-query",
                    message=f"Unbounded query: {method} without pagination - add take/skip",
                    file_path=file,
                    line=line,
                    severity=severity,
                    category="orm",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-400",
                )
            )


def _check_n_plus_one_patterns(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect multiple findOne calls that may indicate N+1 problem."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    file_queries: dict[str, list[dict]] = {}
    for file, line, method, args in rows:
        if not method:
            continue

        is_find_one = any(
            method.endswith(f".{m}") for m in ["findOne", "findOneBy", "findOneOrFail"]
        )
        if not is_find_one:
            continue

        if file not in file_queries:
            file_queries[file] = []
        file_queries[file].append({"line": line, "method": method, "args": args})

    for file, queries in file_queries.items():
        for i in range(len(queries) - 1):
            q1 = queries[i]
            q2 = queries[i + 1]

            if q2["line"] - q1["line"] <= 10:
                has_relations1 = q1["args"] and "relations" in str(q1["args"])
                has_relations2 = q2["args"] and "relations" in str(q2["args"])

                if not has_relations1 and not has_relations2:
                    findings.append(
                        StandardFinding(
                            rule_name="typeorm-n-plus-one",
                            message=f"Potential N+1: Multiple {q1['method']} calls without relations - use eager loading",
                            file_path=file,
                            line=q1["line"],
                            severity=Severity.HIGH,
                            category="orm",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-400",
                        )
                    )
                    break


def _check_missing_transactions(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect multiple write operations without transaction wrapper."""
    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    file_operations: dict[str, list[dict]] = {}
    for file, line, method in rows:
        if not method:
            continue

        is_write = any(f".{m}" in method for m in WRITE_METHODS)
        if not is_write:
            continue

        if file not in file_operations:
            file_operations[file] = []
        file_operations[file].append({"line": line, "method": method})

    for file, operations in file_operations.items():
        for i in range(len(operations) - 1):
            op1 = operations[i]
            op2 = operations[i + 1]

            if op2["line"] - op1["line"] <= 20:
                has_transaction = _check_transaction_between(db, file, op1["line"], op2["line"])

                if not has_transaction:
                    findings.append(
                        StandardFinding(
                            rule_name="typeorm-missing-transaction",
                            message=f"Multiple writes without transaction: {op1['method']} (line {op1['line']}) and {op2['method']} (line {op2['line']})",
                            file_path=file,
                            line=op1["line"],
                            severity=Severity.HIGH,
                            category="orm",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-662",
                        )
                    )
                    break


def _check_transaction_between(db: RuleDB, file: str, start_line: int, end_line: int) -> bool:
    """Check if there's a transaction between two lines."""
    rows = db.query(
        Q("function_call_args")
        .select("callee_function")
        .where("file = ?", file)
        .where("line BETWEEN ? AND ?", start_line - 10, end_line + 10)
    )

    for (callee,) in rows:
        if not callee:
            continue
        callee_lower = callee.lower()
        if "transaction" in callee_lower or "queryrunner" in callee_lower:
            return True

    return False


def _check_sql_injection(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect SQL injection via raw query with string interpolation."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func or not args:
            continue

        func_lower = func.lower()
        is_raw_query = (
            func == "query"
            or ".query" in func_lower
            or "querybuilder" in func_lower
            or ".createquerybuilder" in func_lower
        )

        if not is_raw_query:
            continue

        args_str = str(args)

        interpolation_patterns = ["${", '"+', '" +', "` +", "concat(", ".format("]
        has_interpolation = any(pattern in args_str for pattern in interpolation_patterns)

        has_params = ":" in args_str or "$" in args_str

        if has_interpolation and not has_params:
            findings.append(
                StandardFinding(
                    rule_name="typeorm-sql-injection",
                    message=f"SQL injection risk in {func}: string interpolation without parameters",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="orm",
                    confidence=Confidence.HIGH if "query" in func else Confidence.MEDIUM,
                    cwe_id="CWE-89",
                )
            )


def _check_querybuilder_no_limit(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect QueryBuilder getMany/getRawMany without pagination."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, method, _args in rows:
        if not method:
            continue

        method_lower = method.lower()
        is_get_many = any(m in method_lower for m in ["getmany", "getrawmany", "getmanyandcount"])

        if not is_get_many:
            continue

        limit_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ?", file)
            .where("ABS(line - ?) <= 5", line)
        )

        has_limit_nearby = False
        for (callee,) in limit_rows:
            if callee and (callee.endswith(".limit") or callee.endswith(".take")):
                has_limit_nearby = True
                break

        if not has_limit_nearby:
            findings.append(
                StandardFinding(
                    rule_name="typeorm-querybuilder-no-limit",
                    message=f"QueryBuilder {method} without limit/take - add pagination",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="orm",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-400",
                )
            )


def _check_cascade_true(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect cascade:true which can cause unintended data deletion."""
    rows = db.query(Q("assignments").select("file", "line", "source_expr"))

    for file, line, expr in rows:
        if not expr:
            continue

        expr_lower = expr.lower().replace(" ", "")
        if "cascade" not in expr_lower or "true" not in expr_lower:
            continue

        cascade_patterns = ["cascade:true", 'cascade"true', "cascade'true"]
        if not any(pattern in expr_lower for pattern in cascade_patterns):
            continue

        findings.append(
            StandardFinding(
                rule_name="typeorm-cascade-true",
                message="cascade:true can cause unintended cascading deletions - use explicit save operations",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="orm",
                confidence=Confidence.HIGH,
                cwe_id="CWE-672",
            )
        )


def _check_synchronize_true(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect synchronize:true which should NEVER be used in production."""
    rows = db.query(Q("assignments").select("file", "line", "source_expr"))

    for file, line, expr in rows:
        if not expr:
            continue

        expr_lower = expr.lower().replace(" ", "")
        if "synchronize" not in expr_lower or "true" not in expr_lower:
            continue

        sync_patterns = ["synchronize:true", 'synchronize"true', "synchronize'true"]
        if not any(pattern in expr_lower for pattern in sync_patterns):
            continue

        file_lower = file.lower()
        if any(pattern in file_lower for pattern in ["test", "spec", "mock"]):
            continue

        findings.append(
            StandardFinding(
                rule_name="typeorm-synchronize-true",
                message="synchronize:true detected - NEVER use in production, use migrations instead",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="orm",
                confidence=Confidence.HIGH,
                cwe_id="CWE-665",
            )
        )


def _check_missing_indexes(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect common lookup fields without indexes in entity files."""
    file_rows = db.query(Q("files").select("path"))

    entity_files: list[str] = []
    for (path,) in file_rows:
        if not path:
            continue
        if not (path.endswith(".entity.ts") or path.endswith(".entity.js")):
            continue
        path_lower = path.lower()
        if "test" in path_lower or "spec" in path_lower:
            continue
        entity_files.append(path)

    reported_fields: set[str] = set()

    for entity_file in entity_files:
        symbol_rows = db.query(
            Q("symbols")
            .select("line", "name")
            .where("path = ?", entity_file)
            .where("type IN ('property', 'field', 'member')")
        )

        for field_line, field_name in symbol_rows:
            if not field_name:
                continue

            field_name_lower = field_name.lower()
            matching_field = None
            for common_field in COMMON_INDEXED_FIELDS:
                if common_field.lower() in field_name_lower:
                    matching_field = common_field
                    break

            if not matching_field:
                continue

            report_key = f"{entity_file}:{matching_field}"
            if report_key in reported_fields:
                continue

            nearby_rows = db.query(
                Q("symbols")
                .select("name")
                .where("path = ?", entity_file)
                .where("ABS(line - ?) <= 3", field_line)
            )

            has_index = False
            for (symbol_name,) in nearby_rows:
                if symbol_name and "index" in symbol_name.lower():
                    has_index = True
                    break

            if not has_index:
                reported_fields.add(report_key)
                findings.append(
                    StandardFinding(
                        rule_name="typeorm-missing-index",
                        message=f"Common field '{field_name}' is not indexed - add @Index() decorator",
                        file_path=entity_file,
                        line=field_line,
                        severity=Severity.MEDIUM,
                        category="orm",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-400",
                    )
                )


def _check_complex_joins(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect complex multi-join queries without pagination."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    join_counts: dict[str, dict] = {}
    for file, line, method, _args in rows:
        if not method:
            continue

        method_lower = method.lower()
        is_join = any(j in method_lower for j in ["leftjoin", "innerjoin", "leftjoinandselect"])

        if not is_join:
            continue

        key = f"{file}:{line // 10}"
        if key not in join_counts:
            join_counts[key] = {"file": file, "line": line, "count": 0}
        join_counts[key]["count"] += 1

    for _key, data in join_counts.items():
        if data["count"] < 3:
            continue

        limit_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ?", data["file"])
            .where("ABS(line - ?) <= 10", data["line"])
        )

        has_limit = False
        for (callee,) in limit_rows:
            if callee and (callee.endswith(".limit") or callee.endswith(".take")):
                has_limit = True
                break

        if not has_limit:
            findings.append(
                StandardFinding(
                    rule_name="typeorm-complex-joins",
                    message=f"Complex query with {data['count']} joins but no pagination - may cause performance issues",
                    file_path=data["file"],
                    line=data["line"],
                    severity=Severity.HIGH,
                    category="orm",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-400",
                )
            )


def _check_entity_manager_overuse(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect heavy EntityManager usage instead of Repository pattern."""
    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    manager_usage: list[tuple[str, int, str]] = []
    for file, line, func in rows:
        if not func:
            continue
        func_lower = func.lower()
        if "entitymanager." in func_lower or "getmanager" in func_lower:
            manager_usage.append((file, line, func))

    if len(manager_usage) <= 20:
        return

    all_rows = db.query(Q("function_call_args").select("callee_function"))

    repo_count = 0
    for (callee,) in all_rows:
        if not callee:
            continue
        callee_lower = callee.lower()
        if "getrepository" in callee_lower or "getcustomrepository" in callee_lower:
            repo_count += 1

    if repo_count < 5:
        findings.append(
            StandardFinding(
                rule_name="typeorm-entity-manager-overuse",
                message=f"Heavy EntityManager usage ({len(manager_usage)} calls) - consider Repository pattern for better maintainability",
                file_path=manager_usage[0][0],
                line=1,
                severity=Severity.LOW,
                category="orm",
                confidence=Confidence.LOW,
                cwe_id="CWE-1061",
            )
        )


def _check_mass_assignment(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect mass assignment vulnerabilities - passing req.body directly to save/insert.

    Attackers can overwrite internal fields (e.g., isAdmin, role, balance) if raw input
    is passed directly to TypeORM write methods without whitelisting.
    """
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func or not args:
            continue

        is_write_method = any(f".{method}" in func for method in MASS_ASSIGNMENT_METHODS)
        if not is_write_method:
            continue

        args_str = str(args)
        args_lower = args_str.lower()

        has_unsafe_input = any(source.lower() in args_lower for source in UNSAFE_INPUT_SOURCES)

        if not has_unsafe_input:
            continue

        has_spread = "..." in args_str
        has_direct_pass = any(
            f"({source}" in args_str or f", {source}" in args_str or f"[{source}" in args_str
            for source in UNSAFE_INPUT_SOURCES
        )

        if has_direct_pass or has_spread:
            findings.append(
                StandardFinding(
                    rule_name="typeorm-mass-assignment",
                    message=f"Mass assignment vulnerability: {func} receives raw user input directly",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="orm",
                    snippet=f"{func}({args_str[:50]}...)"
                    if len(args_str) > 50
                    else f"{func}({args_str})",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-915",
                    additional_info={
                        "remediation": "Whitelist allowed fields explicitly: repository.save({ field1: body.field1, field2: body.field2 })",
                    },
                )
            )


def _check_exposed_secrets(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect sensitive columns without select:false in TypeORM entities.

    By default, TypeORM returns all columns in queries. Sensitive fields like
    password, secret, token should use @Column({ select: false }) to prevent
    accidental exposure in API responses.
    """
    file_rows = db.query(Q("files").select("path"))

    entity_files: list[str] = []
    for (path,) in file_rows:
        if not path:
            continue
        if not (path.endswith(".entity.ts") or path.endswith(".entity.js")):
            continue
        path_lower = path.lower()
        if "test" in path_lower or "spec" in path_lower or "mock" in path_lower:
            continue
        entity_files.append(path)

    reported_fields: set[str] = set()

    for entity_file in entity_files:
        symbol_rows = db.query(
            Q("symbols")
            .select("line", "name")
            .where("path = ?", entity_file)
            .where("type IN ('property', 'field', 'member')")
        )

        for field_line, field_name in symbol_rows:
            if not field_name:
                continue

            field_name_lower = field_name.lower()
            matching_sensitive = None
            for sensitive_field in SENSITIVE_FIELD_NAMES:
                if (
                    sensitive_field.lower() == field_name_lower
                    or sensitive_field.lower() in field_name_lower
                ):
                    matching_sensitive = sensitive_field
                    break

            if not matching_sensitive:
                continue

            report_key = f"{entity_file}:{field_name}"
            if report_key in reported_fields:
                continue

            nearby_call_rows = db.query(
                Q("function_call_args")
                .select("argument_expr")
                .where("file = ?", entity_file)
                .where("ABS(line - ?) <= 3", field_line)
            )

            has_select_false = False
            for (args,) in nearby_call_rows:
                if not args:
                    continue
                args_lower = str(args).lower().replace(" ", "")
                if "select:false" in args_lower or "select :false" in str(args).lower():
                    has_select_false = True
                    break

            assign_rows = db.query(
                Q("assignments")
                .select("source_expr")
                .where("file = ?", entity_file)
                .where("ABS(line - ?) <= 3", field_line)
            )

            for (expr,) in assign_rows:
                if not expr:
                    continue
                expr_lower = str(expr).lower().replace(" ", "")
                if "select:false" in expr_lower:
                    has_select_false = True
                    break

            if not has_select_false:
                reported_fields.add(report_key)
                findings.append(
                    StandardFinding(
                        rule_name="typeorm-exposed-secret",
                        message=f"Sensitive field '{field_name}' missing select:false - will be returned in queries by default",
                        file_path=entity_file,
                        line=field_line,
                        severity=Severity.HIGH,
                        category="orm",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-200",
                        additional_info={
                            "remediation": f"Add @Column({{ select: false }}) to '{field_name}' to prevent accidental exposure in API responses.",
                        },
                    )
                )


def register_taint_patterns(taint_registry) -> None:
    """Register TypeORM-specific taint patterns for dataflow analysis."""
    for pattern in RAW_QUERY_METHODS:
        taint_registry.register_sink(pattern, "sql", "javascript")
        taint_registry.register_sink(pattern, "sql", "typescript")

    for pattern in TYPEORM_SOURCES:
        taint_registry.register_source(pattern, "user_input", "javascript")
        taint_registry.register_source(pattern, "user_input", "typescript")

    for pattern in TRANSACTION_METHODS:
        taint_registry.register_sink(pattern, "transaction", "javascript")
        taint_registry.register_sink(pattern, "transaction", "typescript")
