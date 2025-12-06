"""Sequelize ORM Security and Performance Analyzer.

Detects security vulnerabilities and performance anti-patterns in Sequelize ORM usage:
- Death queries with all:true nested:true (recursive load entire database)
- N+1 query patterns (findAll without include when associations exist)
- Unbounded queries missing pagination (limit/offset)
- Race conditions in findOrCreate without transactions
- Missing transaction wrappers around multiple writes
- SQL injection via Sequelize.literal() with string concatenation
- Excessive eager loading (too many includes)
- Hard deletes bypassing soft delete (paranoid:false, force:true)
- Raw SQL queries bypassing ORM protections
- Mass assignment via req.body passed to create/update (CWE-915)
- raw:true bypassing model hooks (CWE-213)
- Insecure logging configuration exposing sensitive data (CWE-532)

Tables Used:
- function_call_args: Sequelize method calls and arguments
- assignments: Variable assignments for transaction detection
- sql_queries: Raw SQL detection

CWE References:
- CWE-89: SQL Injection
- CWE-213: Exposure of Sensitive Information Through Debug Information
- CWE-362: Race Condition
- CWE-400: Uncontrolled Resource Consumption
- CWE-471: Modification of Assumed-Immutable Data
- CWE-532: Insertion of Sensitive Information into Log File
- CWE-662: Improper Synchronization
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
    name="sequelize_orm_issues",
    category="orm",
    target_extensions=[".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=[
        "__tests__/",
        "test/",
        "tests/",
        "node_modules/",
        "dist/",
        "build/",
        ".next/",
        "migrations/",
        "seeders/",
        ".pf/",
        ".auditor_venv/",
    ],
    execution_scope="database",
    primary_table="function_call_args",
)


UNBOUNDED_METHODS = frozenset(
    [
        "findAll",
        "findAndCountAll",
        "scope",
        "findAllWithScopes",
    ]
)


WRITE_METHODS = frozenset(
    [
        "create",
        "bulkCreate",
        "update",
        "bulkUpdate",
        "destroy",
        "bulkDestroy",
        "upsert",
        "save",
        "increment",
        "decrement",
        "restore",
        "bulkRestore",
        "set",
        "add",
        "remove",
        "setAttributes",
    ]
)


RACE_CONDITION_METHODS = frozenset(
    [
        "findOrCreate",
        "findOrBuild",
        "findCreateFind",
    ]
)


RAW_QUERY_METHODS = frozenset(
    [
        "sequelize.query",
        "query",
        "Sequelize.literal",
        "literal",
        "sequelize.fn",
        "Sequelize.fn",
        "sequelize.col",
        "Sequelize.col",
        "sequelize.where",
        "Sequelize.where",
        "sequelize.cast",
        "Sequelize.cast",
    ]
)


SQL_INJECTION_PATTERNS = frozenset(
    [
        "${",
        '"+',
        '" +',
        "` +",
        "concat(",
        "+ req.",
        "+ params.",
        "+ body.",
        "${req.",
        "${params.",
        ".replace(",
        ".replaceAll(",
        "eval(",
    ]
)


COMMON_MODELS = frozenset(
    [
        "User",
        "Account",
        "Product",
        "Order",
        "Customer",
        "Post",
        "Comment",
        "Category",
        "Tag",
        "Role",
        "Permission",
        "Session",
        "Token",
        "File",
        "Image",
    ]
)


SEQUELIZE_SOURCES = frozenset(
    [
        "findAll",
        "findOne",
        "findByPk",
        "findOrCreate",
        "where",
        "attributes",
        "order",
        "group",
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
        "create",
        "bulkCreate",
        "update",
        "bulkUpdate",
        "upsert",
    ]
)


RAW_BYPASS_METHODS = frozenset(
    [
        "findAll",
        "findOne",
        "findByPk",
        "findAndCountAll",
        "findOrCreate",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Sequelize ORM security vulnerabilities and performance anti-patterns.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []

        _check_death_queries(db, findings)
        _check_n_plus_one_patterns(db, findings)
        _check_unbounded_queries(db, findings)
        _check_race_conditions(db, findings)
        _check_missing_transactions(db, findings)
        _check_sql_injection(db, findings)
        _check_excessive_eager_loading(db, findings)
        _check_hard_deletes(db, findings)
        _check_raw_sql_bypass(db, findings)
        _check_mass_assignment(db, findings)
        _check_raw_true_bypass(db, findings)
        _check_insecure_logging(db, findings)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_death_queries(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect death queries with all:true and nested:true that load entire database."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, method, args in rows:
        if not method:
            continue

        is_find_method = any(
            method.endswith(f".{m}") for m in ["findAll", "findOne", "findAndCountAll"]
        )
        if not is_find_method:
            continue

        args_str = str(args).lower()
        has_all = "all: true" in args_str or "all:true" in args_str
        has_nested = "nested: true" in args_str or "nested:true" in args_str

        if has_all and has_nested:
            findings.append(
                StandardFinding(
                    rule_name="sequelize-death-query",
                    message=f"Death query: {method} with all:true and nested:true will recursively load entire database",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="orm",
                    snippet=f"{method}({{ include: {{ all: true, nested: true }} }})",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-400",
                )
            )


def _check_n_plus_one_patterns(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect potential N+1 query patterns - findAll without include."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, method, args in rows:
        if not method:
            continue

        is_find_all = method.endswith(".findAll") or method.endswith(".findAndCountAll")
        if not is_find_all:
            continue

        model = method.split(".")[0] if "." in method else "Model"

        if model not in COMMON_MODELS and not (model and model[0].isupper()):
            continue

        has_include = args and "include" in str(args)
        if has_include:
            continue

        has_associations = _check_associations_nearby(db, file, model)

        if has_associations:
            findings.append(
                StandardFinding(
                    rule_name="sequelize-n-plus-one",
                    message=f"Potential N+1: {method} without include - model has associations defined",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="orm",
                    snippet=f"{method}() without eager loading",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-400",
                )
            )


def _check_associations_nearby(db: RuleDB, file: str, model: str) -> bool:
    """Check if model has associations defined in the file."""
    rows = db.query(Q("function_call_args").select("callee_function").where("file = ?", file))

    association_methods = [".belongsTo", ".hasOne", ".hasMany", ".belongsToMany"]
    for (callee,) in rows:
        if not callee:
            continue
        if callee.startswith(f"{model}.") and any(callee.endswith(m) for m in association_methods):
            return True

    return False


def _check_unbounded_queries(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Check for queries without limits that could cause memory exhaustion."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func:
            continue

        is_unbounded_method = any(f".{method}" in func for method in UNBOUNDED_METHODS)
        if not is_unbounded_method:
            continue

        has_limit = False
        if args:
            args_str = str(args).lower()
            has_limit = any(
                p in args_str for p in ["limit:", "limit :", "take:", "offset:", "page:"]
            )

        if not has_limit:
            findings.append(
                StandardFinding(
                    rule_name="sequelize-unbounded-query",
                    message=f"Unbounded query: {func} without limit - add pagination",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="orm",
                    snippet=f"{func}() without pagination",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-400",
                )
            )


def _check_race_conditions(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Check for race condition vulnerabilities in findOrCreate patterns."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, _args in rows:
        if not func:
            continue

        is_race_method = any(f".{method}" in func for method in RACE_CONDITION_METHODS)
        if not is_race_method:
            continue

        has_transaction = _check_transaction_nearby(db, file, line)

        if not has_transaction:
            findings.append(
                StandardFinding(
                    rule_name="sequelize-race-condition",
                    message=f"Race condition risk: {func} without transaction wrapper",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="orm",
                    snippet=f"{func}() outside transaction",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-362",
                )
            )


def _check_transaction_nearby(db: RuleDB, file: str, line: int) -> bool:
    """Check if there's a transaction wrapper nearby."""
    call_rows = db.query(
        Q("function_call_args").select("callee_function", "line").where("file = ?", file)
    )

    for callee, func_line in call_rows:
        if not callee:
            continue
        if abs(func_line - line) > 30:
            continue
        if "transaction" in callee.lower() or callee in ["t.commit", "t.rollback"]:
            return True

    assign_rows = db.query(
        Q("assignments").select("target_var", "source_expr", "line").where("file = ?", file)
    )

    for target, source, assign_line in assign_rows:
        if abs(assign_line - line) > 30:
            continue
        target_str = target or ""
        source_str = source or ""
        if "transaction" in target_str.lower() or "transaction" in source_str.lower():
            return True

    return False


def _check_missing_transactions(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Check for multiple write operations without transaction wrapper."""
    rows = db.query(
        Q("function_call_args").select("file", "line", "callee_function").order_by("file, line")
    )

    write_ops: list[tuple[str, int, str]] = []
    for file, line, func in rows:
        if not func:
            continue
        if any(f".{method}" in func for method in WRITE_METHODS):
            write_ops.append((file, line, func))

    file_ops: dict[str, list[dict]] = {}
    for file, line, func in write_ops:
        if file not in file_ops:
            file_ops[file] = []
        file_ops[file].append({"line": line, "func": func})

    for file, ops in file_ops.items():
        if len(ops) < 2:
            continue

        ops.sort(key=lambda x: x["line"])

        for i in range(len(ops) - 1):
            op1 = ops[i]
            op2 = ops[i + 1]

            if op2["line"] - op1["line"] <= 20:
                has_transaction = _check_transaction_between(db, file, op1["line"], op2["line"])

                if not has_transaction:
                    findings.append(
                        StandardFinding(
                            rule_name="sequelize-missing-transaction",
                            message=f"Multiple writes without transaction: {op1['func']} (line {op1['line']}) and {op2['func']} (line {op2['line']})",
                            file_path=file,
                            line=op1["line"],
                            severity=Severity.HIGH,
                            category="orm",
                            snippet=f"Multiple operations at lines {op1['line']} and {op2['line']}",
                            confidence=Confidence.HIGH,
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
        .where("line BETWEEN ? AND ?", start_line - 5, end_line + 5)
    )

    for (callee,) in rows:
        if not callee:
            continue
        if "transaction" in callee.lower() or callee in ["t.commit", "t.rollback"]:
            return True

    return False


def _check_sql_injection(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Check for SQL injection via Sequelize.literal() with string concatenation."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func or not args:
            continue

        func_lower = func.lower()
        is_raw_method = any(method.lower() in func_lower for method in RAW_QUERY_METHODS)
        if not is_raw_method:
            continue

        args_str = str(args)
        has_injection = any(pattern in args_str for pattern in SQL_INJECTION_PATTERNS)

        if has_injection:
            is_literal = "literal" in func_lower
            findings.append(
                StandardFinding(
                    rule_name="sequelize-sql-injection",
                    message=f"SQL injection risk in {func}: string concatenation detected",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL if is_literal else Severity.HIGH,
                    category="orm",
                    snippet=f"{func} with string concatenation",
                    confidence=Confidence.HIGH if is_literal else Confidence.MEDIUM,
                    cwe_id="CWE-89",
                )
            )


def _check_excessive_eager_loading(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Check for excessive eager loading that could cause performance issues."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, method, args in rows:
        if not method or not args:
            continue

        is_find_method = any(
            method.endswith(f".{m}") for m in ["findAll", "findOne", "findAndCountAll"]
        )
        if not is_find_method:
            continue

        args_str = str(args)
        if "include" not in args_str:
            continue

        include_count = args_str.count("include:")
        bracket_depth = args_str.count("[{")

        if include_count > 3:
            findings.append(
                StandardFinding(
                    rule_name="sequelize-excessive-eager-loading",
                    message=f"Excessive eager loading: {include_count} includes in {method} - consider lazy loading",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="orm",
                    snippet=f"{method} with {include_count} associations",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-400",
                )
            )

        if bracket_depth > 3:
            findings.append(
                StandardFinding(
                    rule_name="sequelize-deep-nesting",
                    message=f"Deeply nested includes ({bracket_depth} levels) in {method} - may cause slow queries",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="orm",
                    snippet=f"{method} with {bracket_depth} levels of nesting",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-400",
                )
            )


def _check_hard_deletes(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Check for hard deletes that bypass soft delete (paranoid mode)."""
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, method, args in rows:
        if not method:
            continue

        is_destroy = method.endswith(".destroy") or method.endswith(".bulkDestroy")
        if not is_destroy:
            continue

        args_str = str(args) if args else ""

        if "paranoid: false" in args_str or "paranoid:false" in args_str:
            findings.append(
                StandardFinding(
                    rule_name="sequelize-hard-delete",
                    message=f"Hard delete with paranoid:false in {method} - bypasses soft delete",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="orm",
                    snippet=f"{method}({{ paranoid: false }})",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-471",
                )
            )

        if "force: true" in args_str or "force:true" in args_str:
            findings.append(
                StandardFinding(
                    rule_name="sequelize-force-delete",
                    message=f"Force delete with force:true in {method} - permanently removes data",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="orm",
                    snippet=f"{method}({{ force: true }})",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-471",
                )
            )


def _check_raw_sql_bypass(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Check for raw SQL queries that bypass ORM protections."""
    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text", "command")
        .where("command IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')")
        .order_by("file_path, line_number")
    )

    for file, line, query_text, command in rows:
        if not file:
            continue

        file_lower = file.lower()
        if "migration" in file_lower or "seed" in file_lower:
            continue

        if not file.endswith((".js", ".mjs", ".cjs", ".ts")):
            continue

        query_lower = (query_text or "").lower()
        if "sequelize" in query_lower or "replacements" in query_lower:
            continue

        findings.append(
            StandardFinding(
                rule_name="sequelize-bypass",
                message=f"Raw {command} query bypassing ORM - use Sequelize methods for consistency",
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category="orm",
                snippet=f"{command} query outside ORM",
                confidence=Confidence.LOW,
                cwe_id="CWE-213",
            )
        )


def _check_mass_assignment(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect mass assignment vulnerabilities - passing req.body directly to create/update.

    Attackers can overwrite internal fields (e.g., isAdmin, balance) if raw input
    is passed directly to ORM write methods without whitelisting.
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
                    rule_name="sequelize-mass-assignment",
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
                        "remediation": "Whitelist allowed fields explicitly: Model.create({ field1: req.body.field1, field2: req.body.field2 })",
                    },
                )
            )


def _check_raw_true_bypass(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect raw:true which bypasses model hooks (encryption, hashing, soft deletes).

    Using { raw: true } improves performance but skips afterFind hooks and
    returns plain objects instead of model instances, bypassing security logic.
    """
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func or not args:
            continue

        is_find_method = any(f".{method}" in func for method in RAW_BYPASS_METHODS)
        if not is_find_method:
            continue

        args_str = str(args)
        args_lower = args_str.lower().replace(" ", "")

        if "raw:true" in args_lower or "raw :true" in args_str.lower():
            findings.append(
                StandardFinding(
                    rule_name="sequelize-raw-bypass",
                    message=f"Hook bypass: {func} with raw:true skips model hooks (encryption, soft delete logic)",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="orm",
                    snippet=f"{func}({{ raw: true, ... }})",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-213",
                    additional_info={
                        "remediation": "Remove raw:true unless you explicitly need plain objects and understand hooks are bypassed.",
                    },
                )
            )


def _check_insecure_logging(db: RuleDB, findings: list[StandardFinding]) -> None:
    """Detect insecure Sequelize logging configuration exposing SQL/credentials.

    Sequelize's logging: console.log or logging: true dumps SQL queries
    to stdout, potentially exposing PII, passwords, and session tokens in logs.
    """
    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, var, expr in rows:
        if not expr:
            continue

        expr_lower = expr.lower().replace(" ", "")
        var_lower = (var or "").lower()

        is_sequelize_config = (
            "sequelize" in var_lower
            or "db" in var_lower
            or "database" in var_lower
            or "connection" in var_lower
            or "sequelize" in expr_lower
        )

        if not is_sequelize_config:
            continue

        if "logging" not in expr_lower:
            continue

        has_console_log = "console.log" in expr or "console.warn" in expr or "console.info" in expr
        has_logging_true = "logging:true" in expr_lower or "logging: true" in expr.lower()

        has_env_check = any(
            pattern in expr_lower
            for pattern in ["process.env", "node_env", "production", "development"]
        )

        if (has_console_log or has_logging_true) and not has_env_check:
            severity = Severity.HIGH if has_console_log else Severity.MEDIUM
            findings.append(
                StandardFinding(
                    rule_name="sequelize-insecure-logging",
                    message="Insecure logging: Sequelize config logs SQL to console without environment check",
                    file_path=file,
                    line=line,
                    severity=severity,
                    category="orm",
                    snippet=f"logging: {'console.log' if has_console_log else 'true'}",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-532",
                    additional_info={
                        "remediation": "Use logging: process.env.NODE_ENV !== 'production' ? console.log : false",
                    },
                )
            )

    func_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function LIKE ?", "%Sequelize%")
        .order_by("file, line")
    )

    for file, line, _func, args in func_rows:
        if not args:
            continue

        args_lower = str(args).lower().replace(" ", "")

        if "logging" not in args_lower:
            continue

        has_console_log = "console.log" in str(args) or "console.warn" in str(args)
        has_logging_true = "logging:true" in args_lower

        has_env_check = any(
            pattern in args_lower for pattern in ["process.env", "node_env", "production"]
        )

        if (has_console_log or has_logging_true) and not has_env_check:
            findings.append(
                StandardFinding(
                    rule_name="sequelize-insecure-logging",
                    message="Insecure logging in Sequelize constructor: SQL queries logged without environment check",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="orm",
                    snippet="new Sequelize({ logging: ... })",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-532",
                    additional_info={
                        "remediation": "Use logging: process.env.NODE_ENV !== 'production' ? console.log : false",
                    },
                )
            )


def register_taint_patterns(taint_registry) -> None:
    """Register Sequelize-specific taint patterns for dataflow analysis."""
    for pattern in RAW_QUERY_METHODS:
        taint_registry.register_sink(pattern, "sql", "javascript")

    for pattern in SEQUELIZE_SOURCES:
        taint_registry.register_source(pattern, "user_input", "javascript")

    transaction_methods = [
        "transaction",
        "commit",
        "rollback",
        "t.commit",
        "t.rollback",
        "sequelize.transaction",
    ]
    for pattern in transaction_methods:
        taint_registry.register_sink(pattern, "transaction", "javascript")
