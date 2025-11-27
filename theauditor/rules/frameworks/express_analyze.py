"""Express.js Framework Security Analyzer - Database-First Approach.

Analyzes Express.js applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Proper confidence levels
"""

import sqlite3
from dataclasses import dataclass
from typing import Any

from theauditor.indexer.schema import build_query
from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="express_security",
    category="frameworks",
    target_extensions=[".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=["frontend/", "client/", "test/", "spec.", "__tests__"],
    requires_jsx_pass=False,
)


@dataclass(frozen=True)
class ExpressPatterns:
    """Configuration for Express.js security patterns."""

    USER_INPUT_SOURCES = frozenset(
        [
            "req.body",
            "req.query",
            "req.params",
            "req.cookies",
            "req.headers",
            "req.ip",
            "req.hostname",
            "req.path",
            "request.body",
            "request.query",
            "request.params",
        ]
    )

    RESPONSE_SINKS = frozenset(
        [
            "res.send",
            "res.json",
            "res.jsonp",
            "res.render",
            "res.write",
            "res.end",
            "response.send",
            "response.json",
        ]
    )

    SYNC_OPERATIONS = frozenset(
        [
            "readFileSync",
            "writeFileSync",
            "appendFileSync",
            "unlinkSync",
            "mkdirSync",
            "rmdirSync",
            "readdirSync",
            "statSync",
            "lstatSync",
            "existsSync",
            "accessSync",
        ]
    )

    DB_OPERATIONS = frozenset(
        [
            "query",
            "find",
            "findOne",
            "findById",
            "create",
            "update",
            "updateOne",
            "updateMany",
            "delete",
            "deleteOne",
            "deleteMany",
            "save",
            "exec",
            "insert",
            "remove",
            "aggregate",
            "count",
        ]
    )

    RATE_LIMIT_LIBS = frozenset(
        [
            "express-rate-limit",
            "rate-limiter-flexible",
            "express-slow-down",
            "express-brute",
            "rate-limiter",
        ]
    )

    SANITIZATION_FUNCS = frozenset(
        ["sanitize", "escape", "encode", "DOMPurify", "xss", "validator", "clean", "strip"]
    )

    SECURITY_MIDDLEWARE = frozenset(
        ["helmet", "cors", "csurf", "csrf", "express-session", "cookie-parser"]
    )


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Express.js security misconfigurations.

    Analyzes database for:
    - Missing Helmet security middleware
    - Missing error handler (try/catch) in routes
    - XSS vulnerabilities (direct output of user input)
    - Synchronous operations blocking event loop
    - Missing rate limiting on API endpoints
    - Body parser without size limit
    - Database queries directly in route handlers

    Args:
        context: Standardized rule context with database path

    Returns:
        List of StandardFinding objects for detected issues
    """
    analyzer = ExpressAnalyzer(context)
    return analyzer.analyze()


class ExpressAnalyzer:
    """Main analyzer for Express.js applications."""

    def __init__(self, context: StandardRuleContext):
        self.context = context
        self.patterns = ExpressPatterns()
        self.findings: list[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")

        self.express_files: list[str] = []
        self.api_endpoints: list[dict[str, Any]] = []
        self.function_calls: list[dict[str, Any]] = []
        self.imports: dict[str, set[str]] = {}

    def analyze(self) -> list[StandardFinding]:
        """Run complete Express.js analysis."""

        if not self._load_express_data():
            return self.findings

        self._check_missing_helmet()
        self._check_missing_error_handler()
        self._check_sync_operations()
        self._check_xss_vulnerabilities()
        self._check_missing_rate_limiting()
        self._check_body_parser_limits()
        self._check_db_in_routes()

        self._check_cors_wildcard()
        self._check_missing_csrf()
        self._check_session_security()

        return self.findings

    def _load_express_data(self) -> bool:
        """Load Express.js related data from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = build_query("refs", ["src"], where="value = 'express'")
        cursor.execute(query)
        express_refs = cursor.fetchall()

        if not express_refs:
            conn.close()
            return False

        self.express_files = [ref[0] for ref in express_refs]

        query2 = build_query(
            "api_endpoints",
            ["file", "line", "method", "pattern", "handler_function"],
            order_by="file, line",
        )
        cursor.execute(query2)
        for row in cursor.fetchall():
            self.api_endpoints.append(
                {
                    "file": row[0],
                    "line": row[1],
                    "method": row[2],
                    "pattern": row[3],
                    "handler": row[4],
                }
            )

        query3 = build_query("refs", ["src", "value"], where="kind = 'import'")
        cursor.execute(query3)
        for file, import_val in cursor.fetchall():
            if file not in self.imports:
                self.imports[file] = set()
            self.imports[file].add(import_val)

        conn.close()
        return True

    def _check_missing_error_handler(self) -> None:
        """Check for routes without error handling using CFG data."""
        if not self.api_endpoints:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for endpoint in self.api_endpoints:
            handler = endpoint.get("handler", "")
            if not handler:
                continue

            query = build_query(
                "cfg_blocks",
                ["block_type"],
                where="file = ? AND function_name = ? AND block_type IN ('try', 'except', 'catch')",
                limit=1,
            )
            cursor.execute(query, (endpoint["file"], handler))

            has_error_handling = cursor.fetchone() is not None

            if not has_error_handling:
                self.findings.append(
                    StandardFinding(
                        rule_name="express-missing-error-handler",
                        message="Express route without error handling",
                        file_path=endpoint["file"],
                        line=endpoint["line"],
                        severity=Severity.HIGH,
                        category="error-handling",
                        confidence=Confidence.MEDIUM,
                        snippet="Route handler missing try/catch",
                        cwe_id="CWE-755",
                    )
                )

        conn.close()

    def _check_missing_helmet(self) -> None:
        """Check for missing Helmet security middleware."""

        has_helmet = False
        for file_imports in self.imports.values():
            if "helmet" in file_imports:
                has_helmet = True
                break

        if not has_helmet and self.express_files:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query("function_call_args", ["callee_function", "argument_expr"])
            cursor.execute(query)

            helmet_calls = 0
            for callee, arg_expr in cursor.fetchall():
                if "helmet" in callee or ("use" in callee and "helmet" in arg_expr):
                    helmet_calls += 1

            conn.close()

            if helmet_calls == 0:
                self.findings.append(
                    StandardFinding(
                        rule_name="express-missing-helmet",
                        message="Express app without Helmet security middleware - missing critical security headers",
                        file_path=self.express_files[0],
                        line=1,
                        severity=Severity.HIGH,
                        category="security",
                        confidence=Confidence.HIGH,
                        snippet="Missing: app.use(helmet())",
                        cwe_id="CWE-693",
                    )
                )

    def _check_sync_operations(self) -> None:
        """Check for synchronous file operations in routes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        sync_ops_list = ["fs.readFileSync", "fs.writeFileSync", "child_process.execSync"]
        placeholders = ",".join("?" * len(sync_ops_list))

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "caller_function"],
            where=f"""callee_function IN ({placeholders})
                             AND EXISTS (
                                 SELECT 1 FROM api_endpoints e
                                 WHERE e.file = function_call_args.file
                             )""",
            order_by="file, line",
        )
        cursor.execute(query, sync_ops_list)

        seen = set()
        results = []
        for row in cursor.fetchall():
            key = (row[0], row[1], row[2], row[3])
            if key not in seen:
                seen.add(key)
                results.append(row)

        for file, line, sync_op, caller in results:
            self.findings.append(
                StandardFinding(
                    rule_name="express-sync-in-async",
                    message=f"Synchronous operation {sync_op} blocking event loop in route",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="performance",
                    confidence=Confidence.HIGH,
                    snippet=f"{sync_op}(...) in {caller}",
                    cwe_id="CWE-407",
                )
            )

        conn.close()

    def _check_xss_vulnerabilities(self) -> None:
        """Check for direct output of user input (XSS)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            where="callee_function IN ('res.send', 'res.json', 'res.write', 'res.render')",
            order_by="file, line",
        )
        cursor.execute(query)

        response_outputs = cursor.fetchall()

        for file, line, method, arg_expr in response_outputs:
            has_user_input = False
            input_source = None

            for source in self.patterns.USER_INPUT_SOURCES:
                if source in arg_expr:
                    has_user_input = True
                    input_source = source
                    break

            if has_user_input:
                query2 = build_query(
                    "function_call_args",
                    ["callee_function"],
                    where="file = ? AND line BETWEEN ? AND ? AND callee_function IN ('sanitize', 'escape', 'encode', 'DOMPurify', 'xss')",
                    limit=1,
                )
                cursor.execute(query2, (file, line - 5, line + 5))

                has_sanitization = cursor.fetchone() is not None

                if not has_sanitization:
                    self.findings.append(
                        StandardFinding(
                            rule_name="express-xss-direct-send",
                            message=f"Potential XSS - {input_source} directly in response without sanitization",
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="xss",
                            confidence=Confidence.HIGH,
                            snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                            cwe_id="CWE-79",
                        )
                    )

        conn.close()

    def _check_missing_rate_limiting(self) -> None:
        """Check for missing rate limiting on API endpoints."""

        api_routes = [ep for ep in self.api_endpoints if "/api" in ep["pattern"]]

        if not api_routes:
            return

        has_rate_limit = False
        for file_imports in self.imports.values():
            if any(lib in file_imports for lib in self.patterns.RATE_LIMIT_LIBS):
                has_rate_limit = True
                break

        if not has_rate_limit:
            self.findings.append(
                StandardFinding(
                    rule_name="express-missing-rate-limit",
                    message="API endpoints without rate limiting - vulnerable to DoS/brute force",
                    file_path=api_routes[0]["file"],
                    line=api_routes[0]["line"],
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.MEDIUM,
                    snippet="Add express-rate-limit middleware",
                    cwe_id="CWE-307",
                )
            )

    def _check_body_parser_limits(self) -> None:
        """Check for body parser without size limit."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            order_by="file, line",
        )
        cursor.execute(query)

        for file, line, callee, config in cursor.fetchall():
            if "bodyParser" not in callee and callee not in ("json", "urlencoded"):
                continue

            if "limit" not in config:
                self.findings.append(
                    StandardFinding(
                        rule_name="express-body-parser-limit",
                        message="Body parser without size limit - vulnerable to DoS",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="security",
                        confidence=Confidence.MEDIUM,
                        snippet="Add limit option to bodyParser",
                        cwe_id="CWE-400",
                    )
                )

        conn.close()

    def _check_db_in_routes(self) -> None:
        """Check for database queries directly in route handlers."""
        if not self.api_endpoints:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        route_files = {ep["file"] for ep in self.api_endpoints}

        for route_file in route_files:
            query = build_query(
                "function_call_args",
                ["line", "callee_function", "caller_function"],
                where="""file = ?
                                        AND callee_function IN ('query', 'find', 'findOne', 'findById', 'create',
                                                                'update', 'updateOne', 'updateMany', 'delete',
                                                                'deleteOne', 'deleteMany', 'save', 'exec')""",
                order_by="line",
            )
            cursor.execute(query, (route_file,))

            for line, db_method, caller in cursor.fetchall():
                caller_lower = caller.lower() if caller else ""
                if (
                    "service" in caller_lower
                    or "repository" in caller_lower
                    or "model" in caller_lower
                ):
                    continue
                self.findings.append(
                    StandardFinding(
                        rule_name="express-direct-db-query",
                        message=f"Database {db_method} directly in route handler - consider using service layer",
                        file_path=route_file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="architecture",
                        confidence=Confidence.MEDIUM,
                        snippet=f"Move {db_method} to service/repository layer",
                        cwe_id="CWE-1061",
                    )
                )

        conn.close()

    def _check_cors_wildcard(self) -> None:
        """Check for CORS wildcard configuration."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            where="callee_function = 'cors'",
            order_by="file, line",
        )
        cursor.execute(query)

        for file, line, callee, config in cursor.fetchall():
            if (
                "origin:*" in config
                or "origin: *" in config
                or "origin:true" in config
                or "origin: true" in config
                or config == ""
            ):
                self.findings.append(
                    StandardFinding(
                        rule_name="express-cors-wildcard",
                        message="CORS configured with wildcard origin - allows any domain",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        confidence=Confidence.HIGH,
                        snippet="CORS with origin: * or origin: true",
                        cwe_id="CWE-346",
                    )
                )

        conn.close()

    def _check_missing_csrf(self) -> None:
        """Check for missing CSRF protection."""

        modifying_endpoints = [
            ep
            for ep in self.api_endpoints
            if ep.get("method", "").upper() in ["POST", "PUT", "DELETE", "PATCH"]
        ]

        if not modifying_endpoints:
            return

        has_csrf = False
        for file_imports in self.imports.values():
            if "csurf" in file_imports or "csrf" in file_imports:
                has_csrf = True
                break

        if not has_csrf:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query("function_call_args", ["callee_function", "argument_expr"])
            cursor.execute(query)

            csrf_calls = 0
            for callee, arg_expr in cursor.fetchall():
                if callee in ("csurf", "csrf") or ("use" in callee and "csrf" in arg_expr):
                    csrf_calls += 1

            conn.close()

            if csrf_calls == 0:
                self.findings.append(
                    StandardFinding(
                        rule_name="express-missing-csrf",
                        message="State-changing endpoints without CSRF protection",
                        file_path=modifying_endpoints[0]["file"],
                        line=modifying_endpoints[0]["line"],
                        severity=Severity.HIGH,
                        category="csrf",
                        confidence=Confidence.MEDIUM,
                        snippet="POST/PUT/DELETE endpoints need CSRF tokens",
                        cwe_id="CWE-352",
                    )
                )

    def _check_session_security(self) -> None:
        """Check for insecure session configuration."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = build_query(
            "function_call_args",
            ["file", "line", "callee_function", "argument_expr"],
            order_by="file, line",
        )
        cursor.execute(query)

        for file, line, callee, config in cursor.fetchall():
            if not ("session" in callee or ("use" in callee and "session" in config)):
                continue

            config_lower = config.lower()

            issues = []
            if "secret" in config_lower:
                if any(weak in config_lower for weak in ["secret", "keyboard cat", "default"]):
                    issues.append("weak secret")

            if "cookie" in config_lower:
                if "httponly" not in config_lower:
                    issues.append("missing httpOnly")
                if "secure" not in config_lower:
                    issues.append("missing secure flag")
                if "samesite" not in config_lower:
                    issues.append("missing sameSite")

            if issues:
                self.findings.append(
                    StandardFinding(
                        rule_name="express-session-insecure",
                        message=f"Insecure session configuration: {', '.join(issues)}",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="security",
                        confidence=Confidence.HIGH,
                        snippet="Session configuration issues",
                        cwe_id="CWE-614",
                    )
                )

        conn.close()


def register_taint_patterns(taint_registry):
    """Register Express.js-specific taint patterns.

    This function is called by the orchestrator to register
    framework-specific sources and sinks for taint analysis.

    Args:
        taint_registry: TaintRegistry instance
    """

    EXPRESS_INPUT_SOURCES = frozenset(
        [
            "req.body",
            "req.query",
            "req.params",
            "req.cookies",
            "req.headers",
            "req.ip",
            "req.hostname",
            "req.path",
            "request.body",
            "request.query",
            "request.params",
            "request.headers",
            "request.cookies",
        ]
    )

    for pattern in EXPRESS_INPUT_SOURCES:
        taint_registry.register_source(pattern, "http_request", "javascript")

    EXPRESS_RESPONSE_SINKS = frozenset(
        [
            "res.send",
            "res.json",
            "res.jsonp",
            "res.render",
            "res.write",
            "res.end",
            "response.send",
            "response.json",
            "response.render",
            "response.write",
        ]
    )

    for pattern in EXPRESS_RESPONSE_SINKS:
        taint_registry.register_sink(pattern, "response", "javascript")

    EXPRESS_REDIRECT_SINKS = frozenset(["res.redirect", "response.redirect", "res.location"])

    for pattern in EXPRESS_REDIRECT_SINKS:
        taint_registry.register_sink(pattern, "redirect", "javascript")
