"""Input Validation Analyzer - Schema Contract Compliant Implementation.

Detects input validation vulnerabilities including validation bypasses,
type confusion, prototype pollution, and framework-specific issues using
ONLY indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows v1.1+ schema contract compliance:
- Frozensets for all patterns (O(1) lookups)
- Direct database queries (assumes all tables exist per schema contract)
- Uses parameterized queries (no SQL injection)
- Proper confidence levels
"""

import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="input_validation",
    category="security",
    execution_scope="database",
    target_extensions=[".py", ".js", ".ts"],
    exclude_patterns=["test/", "spec.", "__tests__"],
    requires_jsx_pass=False,
)


@dataclass(frozen=True)
class ValidationPatterns:
    """Immutable pattern definitions for input validation detection."""

    VALIDATION_FUNCTIONS = frozenset(
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

    MERGE_FUNCTIONS = frozenset(
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

    NOSQL_OPERATORS = frozenset(
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

    TEMPLATE_ENGINES = frozenset(
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

    TYPE_CHECKS = frozenset(
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

    GRAPHQL_OPS = frozenset(
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

    DB_WRITE_OPS = frozenset(
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

    INPUT_SOURCES = frozenset(
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

    DANGEROUS_SINKS = frozenset(
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

    ORM_METHODS = frozenset(
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

    WEAK_PATTERNS = frozenset(
        [
            "return true",
            "return 1",
            "() => true",
            "validate: true",
            "required: false",
            "optional: true",
        ]
    )


class InputValidationAnalyzer:
    """Analyzer for input validation vulnerabilities."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = ValidationPatterns()
        self.findings = []
        self.seen_issues = set()

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of input validation vulnerabilities found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            self._detect_prototype_pollution()
            self._detect_nosql_injection()
            self._detect_missing_validation()
            self._detect_template_injection()
            self._detect_type_confusion()

            self._detect_incomplete_validation()
            self._detect_schema_bypass()
            self._detect_validation_library_misuse()
            self._detect_framework_bypasses()
            self._detect_graphql_injection()

            self._detect_second_order_injection()
            self._detect_business_logic_bypass()
            self._detect_path_traversal()
            self._detect_type_juggling()
            self._detect_orm_injection()

        finally:
            conn.close()

        return self.findings

    def _add_finding(
        self,
        rule_name: str,
        message: str,
        file: str,
        line: int,
        severity: Severity,
        confidence: Confidence,
        cwe_id: str,
        snippet: str = "",
    ):
        """Add finding with deduplication."""
        issue_key = f"{file}:{line}:{rule_name}"
        if issue_key not in self.seen_issues:
            self.seen_issues.add(issue_key)
            self.findings.append(
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

    def _detect_prototype_pollution(self):
        """Detect prototype pollution vulnerabilities."""

        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        user_input_keywords = frozenset(
            ["req.body", "request.body", "ctx.request.body", "userInput", "data"]
        )

        for file, line, func, args in self.cursor.fetchall():
            if not any(merge in func for merge in self.patterns.MERGE_FUNCTIONS):
                continue

            args_str = str(args).lower() if args else ""
            if not any(ui in args_str for ui in user_input_keywords):
                continue

            if any(x in args_str for x in ["config", "settings", "options", "{}"]):
                self._add_finding(
                    rule_name="prototype-pollution",
                    message=f"Prototype pollution risk via {func} with user input",
                    file=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-1321",
                    snippet=f"{func}({args[:50]}...)",
                )

    def _detect_nosql_injection(self):
        """Detect NoSQL injection vulnerabilities."""

        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE source_expr IS NOT NULL
            ORDER BY file, line
        """)

        input_keywords = frozenset(["req.", "request.", "body", "query", "params"])

        for file, line, var, expr in self.cursor.fetchall():
            if not expr:
                continue

            if not any(keyword in expr for keyword in input_keywords):
                continue

            detected_operator = None
            for operator in self.patterns.NOSQL_OPERATORS:
                if operator in expr:
                    detected_operator = operator
                    break

            if detected_operator:
                self._add_finding(
                    rule_name="nosql-injection",
                    message=f'NoSQL operator "{detected_operator}" detected with user input',
                    file=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-943",
                    snippet=f"{var} = {expr[:50]}",
                )

        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        db_methods = frozenset([".find", ".update", ".delete"])

        for file, line, func, args in self.cursor.fetchall():
            if not any(method in func for method in db_methods):
                continue

            if "$" not in args:
                continue

            if any(op in str(args) for op in self.patterns.NOSQL_OPERATORS):
                self._add_finding(
                    rule_name="nosql-injection-query",
                    message=f"NoSQL injection in {func} with operators in query",
                    file=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-943",
                    snippet=f"{func}({args[:50]})",
                )

    def _detect_missing_validation(self):
        """Detect database operations without validation."""

        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        user_input_patterns = frozenset(
            ["req.body", "req.query", "req.params", "request.body", "request.query"]
        )

        for file, line, func, args in self.cursor.fetchall():
            if not any(f".{db_op}" in func for db_op in self.patterns.DB_WRITE_OPS):
                continue

            if not any(pattern in args for pattern in user_input_patterns):
                continue

            has_validation = self._check_validation_nearby(file, line)

            if not has_validation:
                self._add_finding(
                    rule_name="missing-validation",
                    message=f"Database operation {func} with unvalidated user input",
                    file=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-20",
                    snippet=f"{func}({args[:50]})",
                )

    def _detect_template_injection(self):
        """Detect server-side template injection vulnerabilities."""

        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        user_input_keywords = frozenset(["req.", "request.", "userInput", "body", "query"])

        for file, line, func, args in self.cursor.fetchall():
            if not any(template in func for template in self.patterns.TEMPLATE_ENGINES):
                continue

            if not any(keyword in args for keyword in user_input_keywords):
                continue

            is_compile = "compile" in func.lower()

            self._add_finding(
                rule_name="template-injection",
                message=f"Template injection risk in {func} with user input",
                file=file,
                line=line,
                severity=Severity.CRITICAL if is_compile else Severity.HIGH,
                confidence=Confidence.HIGH,
                cwe_id="CWE-1336",
                snippet=f"{func}({args[:50]})",
            )

    def _detect_type_confusion(self):
        """Detect type confusion vulnerabilities."""

        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE source_expr IS NOT NULL
            ORDER BY file, line
        """)

        type_check_patterns = frozenset(["typeof ", "instanceof "])
        primitive_checks = frozenset(['=== "string"', '=== "number"', '=== "boolean"'])

        for file, line, var, expr in self.cursor.fetchall():
            if not expr:
                continue

            has_type_check = any(pattern in expr for pattern in type_check_patterns)
            if not has_type_check:
                continue

            if "typeof " in expr:
                has_primitive_check = any(check in expr for check in primitive_checks)
                if not has_primitive_check:
                    continue

            if any(src in expr for src in self.patterns.INPUT_SOURCES):
                self._add_finding(
                    rule_name="type-confusion",
                    message="Type check can be bypassed with arrays or objects",
                    file=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-843",
                    snippet=f"{var} = {expr[:50]}",
                )

    def _detect_incomplete_validation(self):
        """Detect validation that doesn't cover all fields."""

        self.cursor.execute(
            """
            SELECT f1.file, f1.line, f1.callee_function, f2.callee_function, f2.line
            FROM function_call_args f1
            JOIN function_call_args f2 ON f1.file = f2.file
            WHERE f1.callee_function IN ({})
              AND f2.callee_function IN ({})
              AND f2.line > f1.line
              AND f2.line - f1.line <= 20
            ORDER BY f1.file, f1.line
        """.format(
                ",".join("?" * len(self.patterns.VALIDATION_FUNCTIONS)),
                ",".join("?" * len(self.patterns.DB_WRITE_OPS)),
            ),
            tuple(self.patterns.VALIDATION_FUNCTIONS) + tuple(self.patterns.DB_WRITE_OPS),
        )

        for file, val_line, val_func, db_func, _db_line in self.cursor.fetchall():
            self._add_finding(
                rule_name="incomplete-validation",
                message=f"Validation at line {val_line} may not cover all fields used in {db_func}",
                file=file,
                line=val_line,
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-20",
                snippet=f"{val_func} -> {db_func}",
            )

    def _detect_schema_bypass(self):
        """Detect validation that allows additional properties."""

        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        db_methods = frozenset([".create", ".update"])
        spread_indicators = frozenset(["...", "Object.assign", "spread"])

        for file, line, func, args in self.cursor.fetchall():
            if not any(method in func for method in db_methods):
                continue

            if not any(indicator in args for indicator in spread_indicators):
                continue

            if "..." in str(args):
                self._add_finding(
                    rule_name="schema-bypass",
                    message="Spread operator may allow additional properties to bypass validation",
                    file=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-915",
                    snippet=f"{func}({args[:50]})",
                )

    def _detect_validation_library_misuse(self):
        """Detect common validation library misconfigurations."""

        validation_funcs = tuple(self.patterns.VALIDATION_FUNCTIONS)
        placeholders = ",".join("?" * len(validation_funcs))

        self.cursor.execute(
            f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """,
            validation_funcs,
        )

        weak_configs = frozenset(
            ["required: false", "optional: true", "allowUnknown: true", "stripUnknown: false"]
        )

        for file, line, func, args in self.cursor.fetchall():
            if not any(weak in args for weak in weak_configs):
                continue

            config_issue = (
                "Unknown properties allowed"
                if "allowUnknown" in str(args)
                else "Weak validation config"
            )

            self._add_finding(
                rule_name="validation-misconfiguration",
                message=f"{config_issue} in {func}",
                file=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                cwe_id="CWE-20",
                snippet=f"{func}({args[:50]})",
            )

    def _detect_framework_bypasses(self):
        """Detect framework-specific validation bypasses."""

        self.cursor.execute("""
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
        """)

        for file, method, route, endpoint_line, controls_str in self.cursor.fetchall():
            if controls_str:
                continue

            line = endpoint_line if endpoint_line else 1

            self._add_finding(
                rule_name="missing-middleware",
                message=f"{method} endpoint {route} has no validation middleware",
                file=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-20",
                snippet=f"{method} {route}",
            )

    def _detect_graphql_injection(self):
        """Detect GraphQL injection vulnerabilities."""

        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        user_query_patterns = frozenset(["req.body.query", "request.body.query", "userQuery"])

        for file, line, func, args in self.cursor.fetchall():
            if not any(graphql in func for graphql in self.patterns.GRAPHQL_OPS):
                continue

            if not any(pattern in args for pattern in user_query_patterns):
                continue

            self._add_finding(
                rule_name="graphql-injection",
                message=f"GraphQL injection risk in {func} with user-provided query",
                file=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-20",
                snippet=f"{func}({args[:50]})",
            )

    def _detect_second_order_injection(self):
        """Detect second-order injection vulnerabilities."""

        template_funcs = tuple(self.patterns.TEMPLATE_ENGINES)
        placeholders = ",".join("?" * len(template_funcs))

        self.cursor.execute(
            f"""
            SELECT a.file, a.line, a.target_var, a.source_expr, f.callee_function, f.line, f.argument_expr
            FROM assignments a
            JOIN function_call_args f ON a.file = f.file
            WHERE a.source_expr IS NOT NULL
              AND a.target_var IS NOT NULL
              AND f.callee_function IN ({placeholders})
              AND f.line > a.line
              AND f.line - a.line <= 50
            ORDER BY a.file, a.line
        """,
            template_funcs,
        )

        for (
            file,
            _retrieve_line,
            var,
            source_expr,
            use_func,
            use_line,
            use_args,
        ) in self.cursor.fetchall():
            if ".find" not in source_expr:
                continue

            if not use_args or var not in use_args:
                continue

            self._add_finding(
                rule_name="second-order-injection",
                message=f"Data from database used in {use_func} without revalidation",
                file=file,
                line=use_line,
                severity=Severity.MEDIUM,
                confidence=Confidence.LOW,
                cwe_id="CWE-20",
                snippet=f"{var} used in {use_func}",
            )

    def _detect_business_logic_bypass(self):
        """Detect business logic validation issues."""

        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        numeric_var_keywords = frozenset(["amount", "quantity", "price", "balance"])
        user_input_keywords = frozenset(["req.", "request."])

        candidates = []
        for file, line, var, expr in self.cursor.fetchall():
            var_lower = var.lower()
            if not any(keyword in var_lower for keyword in numeric_var_keywords):
                continue

            if not any(keyword in expr for keyword in user_input_keywords):
                continue

            candidates.append((file, line, var, expr))

        for file, line, var, expr in candidates:
            self.cursor.execute(
                """
                SELECT source_expr FROM assignments
                WHERE file = ?
                  AND ABS(line - ?) <= 10
                  AND source_expr IS NOT NULL
            """,
                (file, line),
            )

            has_negative_check = False
            negative_patterns = frozenset(["< 0", "<= 0", "Math.abs", "Math.max"])
            for (nearby_expr,) in self.cursor.fetchall():
                if any(pattern in nearby_expr for pattern in negative_patterns):
                    has_negative_check = True
                    break

            if not has_negative_check:
                self._add_finding(
                    rule_name="business-logic-bypass",
                    message=f"Numeric value {var} not validated for negative amounts",
                    file=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.LOW,
                    cwe_id="CWE-20",
                    snippet=f"{var} = {expr[:50]}",
                )

    def _detect_path_traversal(self):
        """Detect path traversal vulnerabilities."""

        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        req_file_patterns = frozenset(["req.", "filename", "path", "file"])
        var_file_keywords = frozenset(["path", "file", "dir"])

        for file, line, var, expr in self.cursor.fetchall():
            if not any(pattern in expr for pattern in req_file_patterns):
                continue

            if not ("filename" in expr or ".path" in expr or ".file" in expr):
                continue

            var_lower = var.lower()
            if not any(keyword in var_lower for keyword in var_file_keywords):
                continue

            if "../" not in expr and ".." not in expr:
                self._add_finding(
                    rule_name="path-traversal",
                    message=f"Path variable {var} from user input without traversal check",
                    file=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.LOW,
                    cwe_id="CWE-22",
                    snippet=f"{var} = {expr[:50]}",
                )

    def _detect_type_juggling(self):
        """Detect type juggling vulnerabilities."""

        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE source_expr IS NOT NULL
            ORDER BY file, line
        """)

        security_keywords = frozenset(["true", "false", "admin", "role"])

        for file, line, var, expr in self.cursor.fetchall():
            if "==" not in expr or "===" in expr:
                continue

            expr_lower = expr.lower()
            if not any(keyword in expr_lower for keyword in security_keywords):
                continue

            self._add_finding(
                rule_name="type-juggling",
                message="Loose equality (==) can cause type juggling vulnerabilities",
                file=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-697",
                snippet=f"{var} = {expr[:50]}",
            )

    def _detect_orm_injection(self):
        """Detect ORM-specific injection vulnerabilities."""

        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        user_input_patterns = frozenset(["req.", "request."])
        concat_indicators = frozenset(["+", "`"])

        for file, line, func, args in self.cursor.fetchall():
            if not any(orm in func for orm in self.patterns.ORM_METHODS):
                continue

            has_user_input = any(pattern in args for pattern in user_input_patterns)
            has_concatenation = any(indicator in str(args) for indicator in concat_indicators)

            if not (has_user_input or has_concatenation):
                continue

            if "+" in str(args) or "`" in str(args):
                self._add_finding(
                    rule_name="orm-injection",
                    message=f"ORM injection risk in {func} with string concatenation",
                    file=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-89",
                    snippet=f"{func}({args[:50]})",
                )

    def _check_validation_nearby(self, file: str, line: int) -> bool:
        """Check if validation exists near a line."""

        validation_funcs = tuple(self.patterns.VALIDATION_FUNCTIONS)
        placeholders = ",".join("?" * len(validation_funcs))

        self.cursor.execute(
            f"""
            SELECT COUNT(*) FROM function_call_args
            WHERE file = ?
              AND line BETWEEN ? AND ?
              AND callee_function IN ({placeholders})
        """,
            (file, line - 20, line) + validation_funcs,
        )

        return self.cursor.fetchone()[0] > 0


def find_input_validation_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect input validation vulnerabilities.

    Detects:
    - Prototype pollution
    - NoSQL injection
    - Template injection
    - Type confusion
    - Validation bypasses
    - Framework-specific issues
    - ORM injection patterns

    Args:
        context: Standardized rule context with database path

    Returns:
        List of input validation vulnerabilities found
    """
    analyzer = InputValidationAnalyzer(context)
    return analyzer.analyze()


def register_taint_patterns(taint_registry):
    """Register input validation taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = ValidationPatterns()

    for source in patterns.INPUT_SOURCES:
        taint_registry.register_source(source, "user_input", "javascript")

    for sink in patterns.DANGEROUS_SINKS:
        taint_registry.register_sink(sink, "code_execution", "javascript")

    for template in patterns.TEMPLATE_ENGINES:
        taint_registry.register_sink(template, "template_injection", "javascript")

    for merge in patterns.MERGE_FUNCTIONS:
        taint_registry.register_sink(merge, "prototype_pollution", "javascript")
