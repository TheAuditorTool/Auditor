"""Input Validation Analyzer - Fidelity-Compliant Implementation.

Detects input validation vulnerabilities:
- Prototype pollution
- NoSQL injection
- Missing validation
- Template injection
- Type confusion
- Schema bypass
- GraphQL injection
- Path traversal
- Type juggling
- ORM injection
"""

from collections import defaultdict

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
    name="input_validation",
    category="security",
    execution_scope="database",
    target_extensions=[".py", ".js", ".ts"],
    exclude_patterns=["test/", "spec.", "__tests__"],
    primary_table="function_call_args",
)


VALIDATION_FUNCTIONS: frozenset[str] = frozenset(
    [
        "validate",
        "verify",
        "sanitize",
        "clean",
        "check",
        "isValid",
        "isEmail",
        "isURL",
        "isAlphanumeric",
        "joi.validate",
        "schema.validate",
        "joi.assert",
        "joi.attempt",
        "yup.validate",
        "schema.validateSync",
        "yup.reach",
        "yup.cast",
        "z.parse",
        "schema.parse",
        "schema.safeParse",
        "z.string",
        "validationResult",
        "checkSchema",
        "check",
        "body",
        "validateOrReject",
        "validateSync",
        "validator.validate",
        "ajv.compile",
        "ajv.validate",
        "schema.validate",
    ]
)

MERGE_FUNCTIONS: frozenset[str] = frozenset(
    [
        "Object.assign",
        "merge",
        "extend",
        "deepMerge",
        "deepExtend",
        "_.merge",
        "_.extend",
        "_.assign",
        "_.defaults",
        "jQuery.extend",
        "$.extend",
        "angular.merge",
        "angular.extend",
        "Object.setPrototypeOf",
        "Reflect.setPrototypeOf",
        "lodash.merge",
        "lodash.assign",
        "deep-extend",
        "node-extend",
    ]
)

NOSQL_OPERATORS: frozenset[str] = frozenset(
    [
        "$ne",
        "$gt",
        "$lt",
        "$gte",
        "$lte",
        "$in",
        "$nin",
        "$exists",
        "$regex",
        "$not",
        "$where",
        "$expr",
        "$jsonSchema",
        "$text",
        "$or",
        "$and",
        "$nor",
        "$elemMatch",
    ]
)

TEMPLATE_ENGINES: frozenset[str] = frozenset(
    [
        "render",
        "compile",
        "renderFile",
        "renderString",
        "ejs.render",
        "ejs.renderFile",
        "ejs.compile",
        "pug.render",
        "pug.renderFile",
        "pug.compile",
        "handlebars.compile",
        "hbs.compile",
        "hbs.renderView",
        "mustache.render",
        "mustache.compile",
        "nunjucks.render",
        "nunjucks.renderString",
        "jade.render",
        "jade.compile",
        "jade.renderFile",
        "doT.template",
        "dust.render",
        "swig.render",
    ]
)

TYPE_CHECKS: frozenset[str] = frozenset(
    [
        "typeof",
        "instanceof",
        "constructor",
        "Array.isArray",
        "Number.isInteger",
        "Number.isNaN",
        "isNaN",
        "isFinite",
        "Object.prototype.toString",
    ]
)

GRAPHQL_OPS: frozenset[str] = frozenset(
    [
        "graphql",
        "execute",
        "graphqlHTTP",
        "GraphQLSchema",
        "apollo-server",
        "graphql-yoga",
        "makeExecutableSchema",
        "buildSchema",
        "parse",
        "parseValue",
        "graphql-tag",
    ]
)

DB_WRITE_OPS: frozenset[str] = frozenset(
    [
        "create",
        "insert",
        "update",
        "save",
        "upsert",
        "findOneAndUpdate",
        "findByIdAndUpdate",
        "updateOne",
        "updateMany",
        "bulkWrite",
        "bulkCreate",
        "insertMany",
    ]
)

INPUT_SOURCES: frozenset[str] = frozenset(
    [
        "req.body",
        "req.query",
        "req.params",
        "request.body",
        "request.query",
        "request.params",
        "ctx.request.body",
        "ctx.query",
        "ctx.params",
        "event.body",
        "event.queryStringParameters",
    ]
)

DANGEROUS_SINKS: frozenset[str] = frozenset(
    [
        "eval",
        "Function",
        "exec",
        "spawn",
        "execFile",
        "vm.runInContext",
        "vm.runInNewContext",
        "require",
        "setTimeout",
        "setInterval",
        "setImmediate",
    ]
)

ORM_METHODS: frozenset[str] = frozenset(
    [
        "findOne",
        "find",
        "findAll",
        "findById",
        "findByPk",
        "where",
        "query",
        "raw",
        "sequelize.query",
        "knex.raw",
        "mongoose.find",
        "typeorm.query",
    ]
)

WEAK_PATTERNS: frozenset[str] = frozenset(
    [
        "return true",
        "return 1",
        "() => true",
        "validate: true",
        "required: false",
        "optional: true",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect input validation vulnerabilities.

    Returns RuleResult with findings and fidelity manifest.
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        seen_issues: set[str] = set()

        func_call_rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function IS NOT NULL")
            .where("argument_expr IS NOT NULL")
            .order_by("file, line")
        )

        assignment_rows = db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        validation_by_file = _prefetch_validation_calls(db)

        findings.extend(_detect_prototype_pollution(func_call_rows, seen_issues))
        findings.extend(_detect_nosql_injection(assignment_rows, func_call_rows, seen_issues))
        findings.extend(_detect_missing_validation(func_call_rows, validation_by_file, seen_issues))
        findings.extend(_detect_template_injection(func_call_rows, seen_issues))
        findings.extend(_detect_type_confusion(assignment_rows, seen_issues))
        findings.extend(_detect_incomplete_validation(db, seen_issues))
        findings.extend(_detect_schema_bypass(func_call_rows, seen_issues))
        findings.extend(_detect_validation_library_misuse(func_call_rows, seen_issues))
        findings.extend(_detect_framework_bypasses(db, seen_issues))
        findings.extend(_detect_graphql_injection(func_call_rows, seen_issues))
        findings.extend(_detect_second_order_injection(db, seen_issues))
        findings.extend(_detect_business_logic_bypass(assignment_rows, seen_issues))
        findings.extend(_detect_path_traversal(assignment_rows, seen_issues))
        findings.extend(_detect_type_juggling(assignment_rows, seen_issues))
        findings.extend(_detect_orm_injection(func_call_rows, seen_issues))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _add_finding(
    findings: list[StandardFinding],
    seen_issues: set[str],
    rule_name: str,
    message: str,
    file: str,
    line: int,
    severity: Severity,
    confidence: Confidence,
    cwe_id: str,
    snippet: str = "",
) -> None:
    """Add finding with deduplication."""
    issue_key = f"{file}:{line}:{rule_name}"
    if issue_key not in seen_issues:
        seen_issues.add(issue_key)
        findings.append(
            StandardFinding(
                rule_name=rule_name,
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="input-validation",
                snippet=snippet,
                confidence=confidence,
                cwe_id=cwe_id,
            )
        )


def _prefetch_validation_calls(db: RuleDB) -> dict[str, list[int]]:
    """Pre-fetch all validation function calls, indexed by file.

    Returns dict mapping file -> list of line numbers with validation calls.
    """
    validation_by_file: dict[str, list[int]] = defaultdict(list)

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func in rows:
        if any(val_func in func for val_func in VALIDATION_FUNCTIONS):
            validation_by_file[file].append(line)

    return validation_by_file


def _has_validation_nearby(
    validation_by_file: dict[str, list[int]],
    file: str,
    line: int,
    window: int = 20,
) -> bool:
    """Check if validation exists near a line using pre-fetched data."""
    if file not in validation_by_file:
        return False

    return any(line - window <= val_line <= line for val_line in validation_by_file[file])


def _detect_prototype_pollution(
    func_call_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect prototype pollution vulnerabilities."""
    findings: list[StandardFinding] = []

    user_input_keywords = frozenset(
        ["req.body", "request.body", "ctx.request.body", "userInput", "data"]
    )

    for file, line, func, args in func_call_rows:
        if not any(merge in func for merge in MERGE_FUNCTIONS):
            continue

        args_str = str(args).lower() if args else ""
        if not any(ui in args_str for ui in user_input_keywords):
            continue

        if any(x in args_str for x in ["config", "settings", "options", "{}"]):
            _add_finding(
                findings,
                seen_issues,
                rule_name="prototype-pollution",
                message=f"Prototype pollution risk via {func} with user input",
                file=file,
                line=line,
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                cwe_id="CWE-1321",
                snippet=f"{func}({args[:50]}...)",
            )

    return findings


def _detect_nosql_injection(
    assignment_rows: list,
    func_call_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect NoSQL injection vulnerabilities."""
    findings: list[StandardFinding] = []

    input_keywords = frozenset(["req.", "request.", "body", "query", "params"])

    for file, line, var, expr in assignment_rows:
        if not expr:
            continue
        if not any(keyword in expr for keyword in input_keywords):
            continue

        detected_operator = None
        for operator in NOSQL_OPERATORS:
            if operator in expr:
                detected_operator = operator
                break

        if detected_operator:
            _add_finding(
                findings,
                seen_issues,
                rule_name="nosql-injection",
                message=f'NoSQL operator "{detected_operator}" detected with user input',
                file=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-943",
                snippet=f"{var} = {expr[:50]}",
            )

    db_methods = frozenset([".find", ".update", ".delete"])

    for file, line, func, args in func_call_rows:
        if not any(method in func for method in db_methods):
            continue
        if "$" not in args:
            continue
        if any(op in str(args) for op in NOSQL_OPERATORS):
            _add_finding(
                findings,
                seen_issues,
                rule_name="nosql-injection-query",
                message=f"NoSQL injection in {func} with operators in query",
                file=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-943",
                snippet=f"{func}({args[:50]})",
            )

    return findings


def _detect_missing_validation(
    func_call_rows: list,
    validation_by_file: dict[str, list[int]],
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect database operations without validation using pre-fetched data."""
    findings: list[StandardFinding] = []

    user_input_patterns = frozenset(
        ["req.body", "req.query", "req.params", "request.body", "request.query"]
    )

    for file, line, func, args in func_call_rows:
        if not any(f".{db_op}" in func for db_op in DB_WRITE_OPS):
            continue
        if not any(pattern in args for pattern in user_input_patterns):
            continue

        if not _has_validation_nearby(validation_by_file, file, line):
            _add_finding(
                findings,
                seen_issues,
                rule_name="missing-validation",
                message=f"Database operation {func} with unvalidated user input",
                file=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-20",
                snippet=f"{func}({args[:50]})",
            )

    return findings


def _detect_template_injection(
    func_call_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect server-side template injection vulnerabilities."""
    findings: list[StandardFinding] = []

    user_input_keywords = frozenset(["req.", "request.", "userInput", "body", "query"])

    for file, line, func, args in func_call_rows:
        if not any(template in func for template in TEMPLATE_ENGINES):
            continue
        if not any(keyword in args for keyword in user_input_keywords):
            continue

        is_compile = "compile" in func.lower()
        _add_finding(
            findings,
            seen_issues,
            rule_name="template-injection",
            message=f"Template injection risk in {func} with user input",
            file=file,
            line=line,
            severity=Severity.CRITICAL if is_compile else Severity.HIGH,
            confidence=Confidence.HIGH,
            cwe_id="CWE-1336",
            snippet=f"{func}({args[:50]})",
        )

    return findings


def _detect_type_confusion(
    assignment_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect type confusion vulnerabilities."""
    findings: list[StandardFinding] = []

    type_check_patterns = frozenset(["typeof ", "instanceof "])
    primitive_checks = frozenset(['=== "string"', '=== "number"', '=== "boolean"'])

    for file, line, var, expr in assignment_rows:
        if not expr:
            continue

        has_type_check = any(pattern in expr for pattern in type_check_patterns)
        if not has_type_check:
            continue

        if "typeof " in expr:
            has_primitive_check = any(check in expr for check in primitive_checks)
            if not has_primitive_check:
                continue

        if any(src in expr for src in INPUT_SOURCES):
            _add_finding(
                findings,
                seen_issues,
                rule_name="type-confusion",
                message="Type check can be bypassed with arrays or objects",
                file=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                cwe_id="CWE-843",
                snippet=f"{var} = {expr[:50]}",
            )

    return findings


def _detect_incomplete_validation(
    db: RuleDB,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect validation that doesn't cover all fields.

    Uses Q.raw for complex JOIN with IN clause and dynamic placeholders.
    """
    findings: list[StandardFinding] = []

    validation_funcs = tuple(VALIDATION_FUNCTIONS)
    db_write_ops = tuple(DB_WRITE_OPS)

    placeholders_val = ",".join("?" * len(validation_funcs))
    placeholders_db = ",".join("?" * len(db_write_ops))

    sql, params = Q.raw(
        f"""
        SELECT f1.file, f1.line, f1.callee_function, f2.callee_function, f2.line
        FROM function_call_args f1
        JOIN function_call_args f2 ON f1.file = f2.file
        WHERE f1.callee_function IN ({placeholders_val})
          AND f2.callee_function IN ({placeholders_db})
          AND f2.line > f1.line
          AND f2.line - f1.line <= 20
        ORDER BY f1.file, f1.line
        """,
        list(validation_funcs) + list(db_write_ops),
    )
    rows = db.execute(sql, params)

    for file, val_line, val_func, db_func, _db_line in rows:
        _add_finding(
            findings,
            seen_issues,
            rule_name="incomplete-validation",
            message=f"Validation at line {val_line} may not cover all fields used in {db_func}",
            file=file,
            line=val_line,
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-20",
            snippet=f"{val_func} -> {db_func}",
        )

    return findings


def _detect_schema_bypass(
    func_call_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect validation that allows additional properties."""
    findings: list[StandardFinding] = []

    db_methods = frozenset([".create", ".update"])
    spread_indicators = frozenset(["...", "Object.assign", "spread"])

    for file, line, func, args in func_call_rows:
        if not any(method in func for method in db_methods):
            continue
        if not any(indicator in args for indicator in spread_indicators):
            continue
        if "..." in str(args):
            _add_finding(
                findings,
                seen_issues,
                rule_name="schema-bypass",
                message="Spread operator may allow additional properties to bypass validation",
                file=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-915",
                snippet=f"{func}({args[:50]})",
            )

    return findings


def _detect_validation_library_misuse(
    func_call_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect common validation library misconfigurations."""
    findings: list[StandardFinding] = []

    weak_configs = frozenset(
        ["required: false", "optional: true", "allowUnknown: true", "stripUnknown: false"]
    )

    for file, line, func, args in func_call_rows:
        if not any(val_func in func for val_func in VALIDATION_FUNCTIONS):
            continue
        if not any(weak in args for weak in weak_configs):
            continue

        config_issue = (
            "Unknown properties allowed"
            if "allowUnknown" in str(args)
            else "Weak validation config"
        )
        _add_finding(
            findings,
            seen_issues,
            rule_name="validation-misconfiguration",
            message=f"{config_issue} in {func}",
            file=file,
            line=line,
            severity=Severity.MEDIUM,
            confidence=Confidence.HIGH,
            cwe_id="CWE-20",
            snippet=f"{func}({args[:50]})",
        )

    return findings


def _detect_framework_bypasses(
    db: RuleDB,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect framework-specific validation bypasses.

    Uses Q.raw for LEFT JOIN with GROUP_CONCAT aggregate.
    """
    findings: list[StandardFinding] = []

    sql, params = Q.raw(
        """
        SELECT
            ae.file,
            ae.method,
            ae.pattern,
            ae.line,
            GROUP_CONCAT(aec.control_name, '|') as controls_str
        FROM api_endpoints ae
        LEFT JOIN api_endpoint_controls aec
            ON ae.file = aec.endpoint_file
            AND ae.line = aec.endpoint_line
        WHERE ae.method IN ('POST', 'PUT', 'PATCH', 'DELETE')
        GROUP BY ae.file, ae.line, ae.method, ae.pattern
        ORDER BY ae.file, ae.pattern
        """,
        [],
    )
    rows = db.execute(sql, params)

    for file, method, route, endpoint_line, controls_str in rows:
        if controls_str:
            continue

        line = endpoint_line if endpoint_line else 1
        _add_finding(
            findings,
            seen_issues,
            rule_name="missing-middleware",
            message=f"{method} endpoint {route} has no validation middleware",
            file=file,
            line=line,
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-20",
            snippet=f"{method} {route}",
        )

    return findings


def _detect_graphql_injection(
    func_call_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect GraphQL injection vulnerabilities."""
    findings: list[StandardFinding] = []

    user_query_patterns = frozenset(["req.body.query", "request.body.query", "userQuery"])

    for file, line, func, args in func_call_rows:
        if not any(graphql in func for graphql in GRAPHQL_OPS):
            continue
        if not any(pattern in args for pattern in user_query_patterns):
            continue

        _add_finding(
            findings,
            seen_issues,
            rule_name="graphql-injection",
            message=f"GraphQL injection risk in {func} with user-provided query",
            file=file,
            line=line,
            severity=Severity.HIGH,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-20",
            snippet=f"{func}({args[:50]})",
        )

    return findings


def _detect_second_order_injection(
    db: RuleDB,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect second-order injection vulnerabilities.

    Uses Q.raw for complex JOIN with IN clause.
    """
    findings: list[StandardFinding] = []

    template_funcs = tuple(TEMPLATE_ENGINES)
    placeholders = ",".join("?" * len(template_funcs))

    sql, params = Q.raw(
        f"""
        SELECT a.file, a.line, a.target_var, a.source_expr,
               f.callee_function, f.line, f.argument_expr
        FROM assignments a
        JOIN function_call_args f ON a.file = f.file
        WHERE a.source_expr IS NOT NULL
          AND a.target_var IS NOT NULL
          AND f.callee_function IN ({placeholders})
          AND f.line > a.line
          AND f.line - a.line <= 50
        ORDER BY a.file, a.line
        """,
        list(template_funcs),
    )
    rows = db.execute(sql, params)

    for file, _retrieve_line, var, source_expr, use_func, use_line, use_args in rows:
        if ".find" not in source_expr:
            continue
        if not use_args or var not in use_args:
            continue

        _add_finding(
            findings,
            seen_issues,
            rule_name="second-order-injection",
            message=f"Data from database used in {use_func} without revalidation",
            file=file,
            line=use_line,
            severity=Severity.MEDIUM,
            confidence=Confidence.LOW,
            cwe_id="CWE-20",
            snippet=f"{var} used in {use_func}",
        )

    return findings


def _detect_business_logic_bypass(
    assignment_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect business logic validation issues using pre-fetched data."""
    findings: list[StandardFinding] = []

    numeric_var_keywords = frozenset(["amount", "quantity", "price", "balance"])
    user_input_keywords = frozenset(["req.", "request."])
    negative_patterns = frozenset(["< 0", "<= 0", "Math.abs", "Math.max"])

    expr_by_file: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for file, line, _var, expr in assignment_rows:
        if expr:
            expr_by_file[file].append((line, expr))

    candidates = []
    for file, line, var, expr in assignment_rows:
        if not expr:
            continue
        var_lower = var.lower() if var else ""
        if not any(keyword in var_lower for keyword in numeric_var_keywords):
            continue
        if not any(keyword in expr for keyword in user_input_keywords):
            continue
        candidates.append((file, line, var, expr))

    for file, line, var, expr in candidates:
        has_negative_check = False

        for expr_line, nearby_expr in expr_by_file[file]:
            if abs(expr_line - line) <= 10:
                if any(pattern in nearby_expr for pattern in negative_patterns):
                    has_negative_check = True
                    break

        if not has_negative_check:
            _add_finding(
                findings,
                seen_issues,
                rule_name="business-logic-bypass",
                message=f"Numeric value {var} not validated for negative amounts",
                file=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.LOW,
                cwe_id="CWE-20",
                snippet=f"{var} = {expr[:50]}",
            )

    return findings


def _detect_path_traversal(
    assignment_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect path traversal vulnerabilities."""
    findings: list[StandardFinding] = []

    req_file_patterns = frozenset(["req.", "filename", "path", "file"])
    var_file_keywords = frozenset(["path", "file", "dir"])

    for file, line, var, expr in assignment_rows:
        if not expr:
            continue
        if not any(pattern in expr for pattern in req_file_patterns):
            continue
        if not ("filename" in expr or ".path" in expr or ".file" in expr):
            continue

        var_lower = var.lower() if var else ""
        if not any(keyword in var_lower for keyword in var_file_keywords):
            continue

        if "../" not in expr and ".." not in expr:
            _add_finding(
                findings,
                seen_issues,
                rule_name="path-traversal",
                message=f"Path variable {var} from user input without traversal check",
                file=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.LOW,
                cwe_id="CWE-22",
                snippet=f"{var} = {expr[:50]}",
            )

    return findings


def _detect_type_juggling(
    assignment_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect type juggling vulnerabilities."""
    findings: list[StandardFinding] = []

    security_keywords = frozenset(["true", "false", "admin", "role"])

    for file, line, var, expr in assignment_rows:
        if not expr:
            continue
        if "==" not in expr or "===" in expr:
            continue

        expr_lower = expr.lower()
        if not any(keyword in expr_lower for keyword in security_keywords):
            continue

        _add_finding(
            findings,
            seen_issues,
            rule_name="type-juggling",
            message="Loose equality (==) can cause type juggling vulnerabilities",
            file=file,
            line=line,
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            cwe_id="CWE-697",
            snippet=f"{var} = {expr[:50]}",
        )

    return findings


def _detect_orm_injection(
    func_call_rows: list,
    seen_issues: set[str],
) -> list[StandardFinding]:
    """Detect ORM-specific injection vulnerabilities."""
    findings: list[StandardFinding] = []

    user_input_patterns = frozenset(["req.", "request."])
    concat_indicators = frozenset(["+", "`"])

    for file, line, func, args in func_call_rows:
        if not any(orm in func for orm in ORM_METHODS):
            continue

        has_user_input = any(pattern in args for pattern in user_input_patterns)
        has_concatenation = any(indicator in str(args) for indicator in concat_indicators)

        if not (has_user_input or has_concatenation):
            continue

        if "+" in str(args) or "`" in str(args):
            _add_finding(
                findings,
                seen_issues,
                rule_name="orm-injection",
                message=f"ORM injection risk in {func} with string concatenation",
                file=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-89",
                snippet=f"{func}({args[:50]})",
            )

    return findings


def register_taint_patterns(taint_registry) -> None:
    """Register input validation taint patterns."""
    for source in INPUT_SOURCES:
        taint_registry.register_source(source, "user_input", "javascript")

    for sink in DANGEROUS_SINKS:
        taint_registry.register_sink(sink, "code_execution", "javascript")

    for template in TEMPLATE_ENGINES:
        taint_registry.register_sink(template, "template_injection", "javascript")

    for merge in MERGE_FUNCTIONS:
        taint_registry.register_sink(merge, "prototype_pollution", "javascript")
