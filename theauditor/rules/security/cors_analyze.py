"""CORS Security Analyzer - Golden Standard Implementation."""

import re
from dataclasses import dataclass

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
    name="cors_security",
    category="security",
    target_extensions=[".py", ".js", ".ts"],
    exclude_patterns=["test/", "spec.", "__tests__"],
    execution_scope="database",
    primary_table="function_call_args",
)


@dataclass(frozen=True)
class CORSPatterns:
    """Immutable CORS detection patterns following golden standard."""

    CORS_FUNCTIONS = frozenset(
        [
            "cors",
            "CORS",
            "Cors",
            "enableCors",
            "setCors",
            "configureCors",
            "express-cors",
            "@koa/cors",
            "fastify-cors",
            "cors.init",
            "cors.create",
            "corsMiddleware",
        ]
    )

    HEADER_FUNCTIONS = frozenset(
        [
            "setHeader",
            "set",
            "header",
            "writeHead",
            "res.setHeader",
            "res.set",
            "res.header",
            "response.setHeader",
            "response.set",
            "reply.header",
            "ctx.set",
            "headers.set",
        ]
    )

    CORS_HEADERS = frozenset(
        [
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Credentials",
            "Access-Control-Allow-Methods",
            "Access-Control-Allow-Headers",
            "Access-Control-Expose-Headers",
            "Access-Control-Max-Age",
            "Access-Control-Request-Method",
            "Access-Control-Request-Headers",
            "Vary",
        ]
    )

    DANGEROUS_ORIGINS = frozenset(
        ["*", "null", "file://", "http://localhost", "http://127.0.0.1", "http://0.0.0.0", "true"]
    )

    REGEX_INDICATORS = frozenset(
        [
            "RegExp",
            "regexp",
            "regex",
            "/^",
            "^http",
            ".test(",
            ".match(",
            "new RegExp",
            "pattern:",
            "/$/",
        ]
    )

    DYNAMIC_INDICATORS = frozenset(
        [
            "function",
            "callback",
            "=>",
            "req.headers.origin",
            "req.header",
            "request.headers",
            "origin ||",
            "getOrigin",
            "checkOrigin",
            "validateOrigin",
        ]
    )

    WEBSOCKET_HANDLERS = frozenset(
        [
            "io.on",
            "socket.on",
            "ws.on",
            "connection",
            "connect",
            "upgrade",
            "WebSocket",
            "SocketIO",
            "ws://",
            "wss://",
        ]
    )

    FRAMEWORKS = frozenset(
        [
            "express",
            "fastify",
            "koa",
            "hapi",
            "restify",
            "nestjs",
            "next",
            "nuxt",
            "django",
            "flask",
            "fastapi",
        ]
    )

    CORS_VAR_NAMES = frozenset(
        [
            "corsOptions",
            "corsConfig",
            "cors_options",
            "corsSettings",
            "corsPolicy",
            "corsRules",
            "allowedOrigins",
            "whitelist",
            "origins",
        ]
    )


class CORSAnalyzer:
    """Comprehensive CORS vulnerability detection following golden standard."""

    def __init__(self, db: RuleDB):
        """Initialize analyzer with database context."""
        self.db = db
        self.patterns = CORSPatterns()
        self.findings: list[StandardFinding] = []

    def analyze(self) -> list[StandardFinding]:
        """Main entry point - runs all CORS vulnerability checks."""
        self._check_wildcard_with_credentials()
        self._check_subdomain_wildcards()
        self._check_null_origin_handling()
        self._check_origin_reflection()
        self._check_regex_vulnerabilities()
        self._check_protocol_downgrade()
        self._check_port_confusion()
        self._check_case_sensitivity()
        self._check_missing_vary_header()
        self._check_excessive_preflight_cache()
        self._check_websocket_bypass()
        self._check_dynamic_origin_flaws()
        self._check_fallback_wildcards()
        self._check_development_configs()
        self._check_framework_specific()

        return self.findings

    def _check_wildcard_with_credentials(self):
        """Detect wildcard origin with credentials enabled."""
        funcs_list = list(self.patterns.CORS_FUNCTIONS)
        placeholders = ",".join(["?"] * len(funcs_list))

        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where(f"callee_function IN ({placeholders})", *funcs_list)
            .where("argument_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, func, args in rows:
            if not args:
                continue

            has_wildcard = any(origin in args for origin in ["*", '"*"', "'*'", "true"])
            has_credentials = "credentials" in args.lower() and "true" in args.lower()

            if has_wildcard and has_credentials:
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-wildcard-credentials",
                        message="CORS wildcard origin with credentials enabled - any site can read authenticated data",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        confidence=Confidence.HIGH,
                        category="security",
                        snippet=f'{func}(origin: "*", credentials: true)',
                        cwe_id="CWE-942",
                    )
                )

    def _check_subdomain_wildcards(self):
        """Detect subdomain wildcard patterns that enable takeover attacks."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, var, expr in rows:
            var_lower = var.lower()
            if not ("origin" in var_lower or "cors" in var_lower):
                continue

            if not ("*." in expr or "/." in expr):
                continue

            subdomain_patterns = [
                r"\*\.",
                r"/\.\*\\?\.",
                r"/\^https?:\/\/\.\*\\?\.",
            ]

            for pattern in subdomain_patterns:
                if re.search(pattern, expr):
                    self.findings.append(
                        StandardFinding(
                            rule_name="cors-subdomain-wildcard",
                            message="Subdomain wildcard in CORS origin - vulnerable to subdomain takeover",
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            confidence=Confidence.HIGH,
                            category="security",
                            snippet=f"{var} = {expr[:100]}",
                            cwe_id="CWE-942",
                        )
                    )
                    break

    def _check_null_origin_handling(self):
        """Detect allowing 'null' origin which enables sandbox attacks."""

        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("argument_expr IS NOT NULL")
            .order_by("file, line")
        )

        for row in rows:
            file, line, callee, args = row[0], row[1], row[2], row[3]

            if "null" not in str(args).lower():
                continue

            if not ("origin" in str(args).lower() or callee in self.patterns.CORS_FUNCTIONS):
                continue

            self.findings.append(
                StandardFinding(
                    rule_name="cors-null-origin",
                    message='CORS allows "null" origin - enables attacks from sandboxed contexts',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    category="security",
                    snippet='origin: [..., "null", ...]',
                    cwe_id="CWE-346",
                )
            )

        assign_rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for row in assign_rows:
            file, line, var, expr = row[0], row[1], row[2], row[3]

            var_lower = var.lower()
            if not ("origin" in var_lower or "whitelist" in var_lower):
                continue

            if "null" not in expr.lower():
                continue

            if "null" in str(row).lower():
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-null-origin",
                        message='CORS allows "null" origin - enables attacks from sandboxed contexts',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.HIGH,
                        category="security",
                        snippet='origin: [..., "null", ...]',
                        cwe_id="CWE-346",
                    )
                )

    def _check_origin_reflection(self):
        """Detect reflecting origin header without validation."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        origin_patterns = [
            "req.headers.origin",
            "req.header",
            "request.headers.origin",
            "request.headers[",
        ]

        for file, line, var, expr in rows:
            if not any(pattern in expr for pattern in origin_patterns):
                continue

            if "origin" not in expr.lower():
                continue

            nearby_rows = self.db.query(
                Q("function_call_args")
                .select("callee_function", "line", "argument_expr")
                .where("file = ?", file)
                .where("callee_function IS NOT NULL")
            )

            validation_funcs = ["includes", "indexOf", "test", "match"]
            validation_keywords = ["whitelist", "allowed"]

            nearby_validation = []
            for callee, func_line, args in nearby_rows:
                if abs(func_line - line) > 10:
                    continue

                if any(vf in callee for vf in validation_funcs):
                    nearby_validation.append((callee, func_line))
                    continue

                if args and any(kw in str(args).lower() for kw in validation_keywords):
                    nearby_validation.append((callee, func_line))

            validation_count = len(nearby_validation)

            if validation_count == 0:
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-origin-reflection",
                        message="Origin header reflected without validation - attacker can bypass CORS",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        confidence=Confidence.HIGH,
                        category="security",
                        snippet=f"{var} = {expr}",
                        cwe_id="CWE-346",
                    )
                )

    def _check_regex_vulnerabilities(self):
        """Detect vulnerable regex patterns in CORS origin validation."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, var, expr in rows:
            var_lower = var.lower()
            if not ("origin" in var_lower or "cors" in var_lower):
                continue

            if not ("RegExp" in expr or "/^" in expr):
                continue

            vulnerabilities = []

            if re.search(r"/[^\\]\.[^*+]/", expr):
                vulnerabilities.append("unescaped dots")

            if "RegExp" in expr and not ("^" in expr or "$" in expr):
                vulnerabilities.append("missing anchors")

            if "RegExp" in expr and "/i" not in expr and "ignoreCase" not in expr:
                vulnerabilities.append("case sensitive")

            if vulnerabilities:
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-regex-vulnerability",
                        message=f"Vulnerable regex pattern: {', '.join(vulnerabilities)}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        category="security",
                        snippet=f"{var} = {expr[:100]}",
                        cwe_id="CWE-185",
                    )
                )

    def _check_protocol_downgrade(self):
        """Detect allowing HTTP origins when HTTPS should be required."""

        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for row in rows:
            file, line, var, expr = row[0], row[1], row[2], row[3]

            var_lower = var.lower()
            if not ("origin" in var_lower or "cors" in var_lower):
                continue

            if "http://" not in expr or "https://" in expr:
                continue

            self.findings.append(
                StandardFinding(
                    rule_name="cors-protocol-downgrade",
                    message="HTTP origin allowed - vulnerable to protocol downgrade attacks",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    category="security",
                    snippet='origin: "http://..."',
                    cwe_id="CWE-757",
                )
            )

        funcs_list = list(self.patterns.CORS_FUNCTIONS)
        placeholders = ",".join(["?"] * len(funcs_list))

        func_rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where(f"callee_function IN ({placeholders})", *funcs_list)
            .where("argument_expr IS NOT NULL")
            .order_by("file, line")
        )

        for row in func_rows:
            file, line, _callee, args = row[0], row[1], row[2], row[3]

            if "http://" not in args:
                continue

            if "localhost" in args or "127.0.0.1" in args:
                continue

            self.findings.append(
                StandardFinding(
                    rule_name="cors-protocol-downgrade",
                    message="HTTP origin allowed - vulnerable to protocol downgrade attacks",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    category="security",
                    snippet='origin: "http://..."',
                    cwe_id="CWE-757",
                )
            )

    def _check_port_confusion(self):
        """Detect port handling issues in CORS origin validation."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, var, expr in rows:
            var_lower = var.lower()
            if not ("origin" in var_lower or "cors" in var_lower):
                continue

            if ":" not in expr:
                continue

            if ":80" in expr or ":443" in expr:
                continue

            port_matches = re.findall(r":(\d+)", expr)
            if port_matches and len(set(port_matches)) > 1:
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-port-confusion",
                        message="Multiple or non-standard ports in CORS config - potential security risk",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.MEDIUM,
                        category="security",
                        snippet=f"{var} = {expr[:100]}",
                        cwe_id="CWE-942",
                    )
                )

    def _check_case_sensitivity(self):
        """Detect case-sensitive origin comparisons that can be bypassed."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function IS NOT NULL")
            .where("argument_expr IS NOT NULL")
            .order_by("file, line")
        )

        comparison_funcs = ["===", "==", "equals", "strcmp"]

        for file, line, func, args in rows:
            if not (func in comparison_funcs or "indexOf" in func or "includes" in func):
                continue

            if "origin" not in args.lower():
                continue

            nearby_rows = self.db.query(
                Q("function_call_args")
                .select("callee_function", "line")
                .where("file = ?", file)
                .where("callee_function IS NOT NULL")
            )

            nearby_case = []
            for callee, func_line in nearby_rows:
                if abs(func_line - line) > 3:
                    continue

                if "toLowerCase" in callee or "toUpperCase" in callee:
                    nearby_case.append((callee, func_line))

            if len(nearby_case) == 0:
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-case-sensitivity",
                        message="Case-sensitive origin comparison - can be bypassed with different casing",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.LOW,
                        category="security",
                        snippet=f"{func}(...origin...)",
                        cwe_id="CWE-178",
                    )
                )

    def _check_missing_vary_header(self):
        """Detect missing Vary: Origin header causing cache poisoning."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "argument_expr", "line")
            .where("argument_expr IS NOT NULL")
        )

        cors_files = {}
        for file, args, line in rows:
            if "Access-Control-Allow-Origin" in args and file not in cors_files:
                cors_files[file] = line

        for file, first_line in cors_files.items():
            file_rows = self.db.query(
                Q("function_call_args")
                .select("argument_expr")
                .where("file = ?", file)
                .where("argument_expr IS NOT NULL")
            )

            has_vary = False
            for (args,) in file_rows:
                if "Vary" in args and "Origin" in args:
                    has_vary = True
                    break

            if not has_vary:
                line = first_line

                self.findings.append(
                    StandardFinding(
                        rule_name="cors-missing-vary",
                        message="Missing Vary: Origin header - vulnerable to cache poisoning",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        category="security",
                        snippet="Access-Control-Allow-Origin without Vary: Origin",
                        cwe_id="CWE-524",
                    )
                )

    def _check_excessive_preflight_cache(self):
        """Detect excessive Access-Control-Max-Age values."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "argument_expr")
            .where("argument_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, args in rows:
            if "Access-Control-Max-Age" not in args:
                continue

            max_age_match = re.search(r'Max-Age["\s:]+(\d+)', args, re.IGNORECASE)
            if max_age_match:
                max_age = int(max_age_match.group(1))

                if max_age > 86400:
                    days = max_age / 86400
                    self.findings.append(
                        StandardFinding(
                            rule_name="cors-excessive-cache",
                            message=f"Excessive CORS preflight cache: {days:.1f} days - changes won't apply",
                            file_path=file,
                            line=line,
                            severity=Severity.LOW,
                            confidence=Confidence.HIGH,
                            category="security",
                            snippet=f"Access-Control-Max-Age: {max_age}",
                            cwe_id="CWE-942",
                        )
                    )

    def _check_websocket_bypass(self):
        """Detect WebSocket handlers without origin validation."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, func, args in rows:
            is_websocket = func in self.patterns.WEBSOCKET_HANDLERS or (
                args and ("connection" in args or "upgrade" in args)
            )

            if not is_websocket:
                continue

            nearby_rows = self.db.query(
                Q("function_call_args")
                .select("callee_function", "line", "argument_expr")
                .where("file = ?", file)
                .where("callee_function IS NOT NULL")
            )

            validation_count = 0
            for callee, func_line, func_args in nearby_rows:
                if abs(func_line - line) > 20:
                    continue

                if func_args and ("origin" in func_args or "handshake" in func_args):
                    validation_count += 1
                    break

                if "authenticate" in callee:
                    validation_count += 1
                    break

            if validation_count == 0:
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-websocket-bypass",
                        message="WebSocket connection without origin validation - bypasses CORS",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.LOW,
                        category="security",
                        snippet=f'{func}("connection", ...)',
                        cwe_id="CWE-346",
                    )
                )

    def _check_dynamic_origin_flaws(self):
        """Detect flawed dynamic origin validation logic."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, var, expr in rows:
            var_lower = var.lower()
            if not ("origin" in var_lower or "cors" in var_lower):
                continue

            if not ("function" in expr or "=>" in expr or "callback" in expr):
                continue

            issues = []

            if '|| "*"' in expr or "|| true" in expr:
                issues.append("falls back to wildcard")

            if "return true" in expr and "return false" not in expr:
                issues.append("always returns true")

            if "callback(null, true)" in expr and "callback(null, false)" not in expr:
                issues.append("always allows origin")

            if issues:
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-dynamic-flaw",
                        message=f"Flawed dynamic origin validation: {', '.join(issues)}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        category="security",
                        snippet=f"{var} = function(...)",
                        cwe_id="CWE-942",
                    )
                )

    def _check_fallback_wildcards(self):
        """Detect configurations that fall back to wildcard on error."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, var, expr in rows:
            var_lower = var.lower()
            if not ("origin" in var_lower or "cors" in var_lower):
                continue

            if "?" not in expr:
                continue

            if not ("*" in expr or "true" in expr):
                continue

            if re.search(r'\?\s*["\']?\*["\']?\s*:', expr) or re.search(
                r':\s*["\']?\*["\']?', expr
            ):
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-wildcard-fallback",
                        message="CORS configuration falls back to wildcard - security risk",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.HIGH,
                        category="security",
                        snippet=f'{var} = ... ? ... : "*"',
                        cwe_id="CWE-942",
                    )
                )

    def _check_development_configs(self):
        """Detect development CORS configs that might leak to production."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, var, expr in rows:
            var_lower = var.lower()
            if not ("origin" in var_lower or "cors" in var_lower):
                continue

            if not ("NODE_ENV" in expr or "development" in expr or "localhost" in expr):
                continue

            if "development" in expr.lower() and (
                "*" in expr or "true" in expr or "localhost" in expr
            ):
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-dev-leak",
                        message="Unsafe development CORS config - might leak to production",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.MEDIUM,
                        category="security",
                        snippet=f'{var} = NODE_ENV === "development" ? "*" : ...',
                        cwe_id="CWE-489",
                    )
                )

    def _check_framework_specific(self):
        """Detect framework-specific CORS misconfigurations."""

        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function IN ('app.use', 'router.use')")
            .where("argument_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, func, args in rows:
            if "cors" not in args.lower():
                continue

            before_rows = self.db.query(
                Q("function_call_args")
                .select("callee_function", "line")
                .where("file = ?", file)
                .where("line < ?", line)
                .where("callee_function IS NOT NULL")
            )

            routes_before = 0
            for callee, _callee_line in before_rows:
                if ".get" in callee or ".post" in callee or ".route" in callee:
                    routes_before += 1

            if routes_before > 0:
                self.findings.append(
                    StandardFinding(
                        rule_name="cors-middleware-order",
                        message="CORS middleware applied after routes - some endpoints unprotected",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        category="security",
                        snippet=f"{func}(cors()) // After route definitions",
                        cwe_id="CWE-696",
                    )
                )

        if "CORS" in str(self.patterns.CORS_FUNCTIONS):
            flask_rows = self.db.query(
                Q("function_call_args")
                .select("file", "line", "callee_function", "argument_expr")
                .where("callee_function = ?", "CORS")
                .where("argument_expr IS NOT NULL")
                .order_by("file, line")
            )

            for file, line, _func, args in flask_rows:
                if not ("resources" in args and "/*" in args):
                    continue

                if not ("supports_credentials" in args and "True" in args):
                    continue

                self.findings.append(
                    StandardFinding(
                        rule_name="cors-flask-wildcard",
                        message="Flask-CORS with wildcard resources and credentials",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        confidence=Confidence.HIGH,
                        category="security",
                        snippet='CORS(app, resources="/*", supports_credentials=True)',
                        cwe_id="CWE-942",
                    )
                )


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect CORS security vulnerabilities.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        analyzer = CORSAnalyzer(db)
        findings = analyzer.analyze()
        return RuleResult(findings=findings, manifest=db.get_manifest())


def register_taint_patterns(taint_registry):
    """Register CORS-related taint patterns for flow analysis."""
    patterns = CORSPatterns()

    origin_sources = [
        "req.headers.origin",
        "request.headers.origin",
        "req.header.origin",
        'req.get("origin")',
    ]

    for source in origin_sources:
        taint_registry.register_source(source, "user_input", "javascript")
        taint_registry.register_source(source, "user_input", "python")

    for header in patterns.CORS_HEADERS:
        taint_registry.register_sink(header, "cors_header", "all")

    response_methods = [
        "res.setHeader",
        "res.set",
        "res.header",
        "response.headers",
        "response.set_header",
    ]

    for method in response_methods:
        taint_registry.register_sink(method, "response", "all")


__all__ = [
    "analyze",
    "METADATA",
    "register_taint_patterns",
    "CORSPatterns",
]
