"""API Authentication Security Analyzer - Database-First Approach."""

import json
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
    name="api_authentication",
    category="security",
    target_extensions=[".py", ".js", ".ts"],
    exclude_patterns=["test/", "spec.", "__tests__"],
    execution_scope="database",
    primary_table="api_endpoints",
)


@dataclass(frozen=True)
class ApiAuthPatterns:
    """Immutable pattern definitions for API authentication detection."""

    STATE_CHANGING_METHODS = frozenset(
        ["POST", "PUT", "PATCH", "DELETE", "post", "put", "patch", "delete"]
    )

    GRAPHQL_MUTATIONS = frozenset(
        [
            "mutation",
            "Mutation",
            "createMutation",
            "updateMutation",
            "deleteMutation",
            "upsertMutation",
        ]
    )

    AUTH_MIDDLEWARE = frozenset(
        [
            "auth",
            "authenticate",
            "authenticated",
            "authorization",
            "authorize",
            "authorized",
            "requireAuth",
            "requiresAuth",
            "isAuthenticated",
            "ensureAuthenticated",
            "protect",
            "protected",
            "secure",
            "secured",
            "checkAuth",
            "validateAuth",
            "verifyAuth",
            "authRequired",
            "jwt",
            "verifyToken",
            "validateToken",
            "checkToken",
            "jwtAuth",
            "verifyJWT",
            "validateJWT",
            "checkJWT",
            "decodeToken",
            "verifyJwt",
            "jwtMiddleware",
            "jwtRequired",
            "requireJWT",
            "jwtVerify",
            "session",
            "checkSession",
            "validateSession",
            "requireSession",
            "cookie",
            "checkCookie",
            "validateCookie",
            "sessionAuth",
            "sessionRequired",
            "cookieAuth",
            "cookieRequired",
            "hasSession",
            "passport",
            "passport.authenticate",
            "ensureLoggedIn",
            "requireUser",
            "currentUser",
            "isLoggedIn",
            "loggedIn",
            "ensureUser",
            "login_required",
            "permission_required",
            "requires_auth",
            "auth_required",
            "token_required",
            "api_key_required",
            "@login_required",
            "@auth_required",
            "@authenticated",
            "[Authorize]",
            "[Authentication]",
            "[RequireAuth]",
            "AuthorizeAttribute",
            "AuthenticationAttribute",
            "role",
            "checkRole",
            "hasRole",
            "requireRole",
            "roleRequired",
            "permission",
            "checkPermission",
            "hasPermission",
            "permissionRequired",
            "admin",
            "requireAdmin",
            "isAdmin",
            "checkAdmin",
            "adminOnly",
            "rbac",
            "acl",
            "checkAcl",
            "hasAccess",
            "accessControl",
            "apiKey",
            "api_key",
            "checkApiKey",
            "validateApiKey",
            "requireApiKey",
            "verifyApiKey",
            "x-api-key",
            "apiKeyRequired",
            "apiKeyAuth",
            "apiKeyMiddleware",
            "hasApiKey",
            "oauth",
            "checkOAuth",
            "validateOAuth",
            "oauthAuth",
            "oauth2",
            "bearerToken",
            "bearerAuth",
            "checkBearer",
            "guard",
            "Guard",
            "authGuard",
            "AuthGuard",
            "canActivate",
            "UseGuards",
            "@UseGuards",
            "JwtGuard",
            "LocalGuard",
            "middleware",
            "authMiddleware",
            "securityMiddleware",
            "authenticationMiddleware",
            "authorizationMiddleware",
            "tokenMiddleware",
            "userMiddleware",
        ]
    )

    PUBLIC_ENDPOINT_PATTERNS = frozenset(
        [
            "public",
            "open",
            "anonymous",
            "noauth",
            "no-auth",
            "skipAuth",
            "skipAuthentication",
            "allowAnonymous",
            "isPublic",
            "publicRoute",
            "publicEndpoint",
            "health",
            "healthcheck",
            "health-check",
            "ping",
            "status",
            "version",
            "metrics",
            "swagger",
            "docs",
            "documentation",
            "spec",
        ]
    )

    SENSITIVE_OPERATIONS = frozenset(
        [
            "user",
            "users",
            "profile",
            "account",
            "settings",
            "password",
            "reset",
            "change-password",
            "update-password",
            "admin",
            "administrator",
            "superuser",
            "root",
            "config",
            "configuration",
            "system",
            "backup",
            "payment",
            "billing",
            "invoice",
            "subscription",
            "checkout",
            "purchase",
            "order",
            "transaction",
            "delete",
            "remove",
            "destroy",
            "purge",
            "truncate",
            "export",
            "download",
            "backup",
            "restore",
            "token",
            "key",
            "secret",
            "credential",
            "certificate",
            "audit",
            "log",
            "security",
            "permission",
            "role",
        ]
    )

    RATE_LIMIT_PATTERNS = frozenset(
        [
            "rateLimit",
            "rate-limit",
            "throttle",
            "rateLimiter",
            "speedLimiter",
            "bruteForce",
            "ddos",
            "flood",
            "requestLimit",
            "apiLimit",
            "quotaLimit",
        ]
    )

    CSRF_PATTERNS = frozenset(
        [
            "csrf",
            "xsrf",
            "csrfToken",
            "xsrfToken",
            "csrfProtection",
            "validateCsrf",
            "checkCsrf",
            "verifyCsrf",
            "csrfMiddleware",
            "doubleCookie",
            "sameSite",
            "origin-check",
        ]
    )

    GRAPHQL_PATTERNS = frozenset(
        [
            "graphql",
            "GraphQL",
            "apollo",
            "relay",
            "query",
            "Query",
            "mutation",
            "Mutation",
            "subscription",
            "Subscription",
            "resolver",
            "Resolver",
        ]
    )


class ApiAuthAnalyzer:
    """Analyzer for API authentication security issues."""

    def __init__(self, db: RuleDB):
        """Initialize analyzer with database context."""
        self.db = db
        self.patterns = ApiAuthPatterns()
        self.findings: list[StandardFinding] = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        self._check_missing_auth_on_mutations()
        self._check_sensitive_endpoints()
        self._check_graphql_mutations()
        self._check_weak_auth_patterns()
        self._check_csrf_protection()

        return self.findings

    def _check_missing_auth_on_mutations(self):
        """Check for state-changing endpoints without authentication."""
        auth_patterns_lower = [p.lower() for p in self.patterns.AUTH_MIDDLEWARE]
        public_patterns_lower = [p.lower() for p in self.patterns.PUBLIC_ENDPOINT_PATTERNS]

        sql, params = Q.raw(
            """
            SELECT
                ae.file,
                ae.line,
                ae.method,
                ae.pattern,
                GROUP_CONCAT(aec.control_name, '|') as controls_str
            FROM api_endpoints ae
            LEFT JOIN api_endpoint_controls aec
                ON ae.file = aec.endpoint_file
                AND ae.line = aec.endpoint_line
            WHERE UPPER(ae.method) IN ('POST', 'PUT', 'PATCH', 'DELETE')
            GROUP BY ae.file, ae.line, ae.method, ae.pattern
            ORDER BY ae.file, ae.pattern
            """
        )
        rows = self.db.execute(sql, params)

        for file, line, method, pattern, controls_str in rows:
            controls = controls_str.split("|") if controls_str else []

            controls_lower = [str(c).lower() for c in controls if c]
            pattern_lower = pattern.lower() if pattern else ""

            is_public = any(pub in pattern_lower for pub in public_patterns_lower)
            if is_public:
                continue

            has_auth = any(
                any(auth in control for auth in auth_patterns_lower) for control in controls_lower
            )

            if not has_auth:
                severity = self._determine_severity(pattern, method)
                confidence = self._determine_confidence(pattern, controls)

                self.findings.append(
                    StandardFinding(
                        rule_name="api-missing-auth",
                        message=f"State-changing endpoint lacks authentication: {method} {pattern}",
                        file_path=file,
                        line=line or 1,
                        severity=severity,
                        category="authentication",
                        confidence=confidence,
                        cwe_id="CWE-306",
                    )
                )

    def _check_sensitive_endpoints(self):
        """Check if sensitive operations have proper authentication."""
        sensitive_patterns_lower = [p.lower() for p in self.patterns.SENSITIVE_OPERATIONS]
        auth_patterns_lower = [p.lower() for p in self.patterns.AUTH_MIDDLEWARE]

        sql, params = Q.raw(
            """
            SELECT
                ae.file,
                ae.line,
                ae.method,
                ae.pattern,
                GROUP_CONCAT(aec.control_name, '|') as controls_str
            FROM api_endpoints ae
            LEFT JOIN api_endpoint_controls aec
                ON ae.file = aec.endpoint_file
                AND ae.line = aec.endpoint_line
            WHERE ae.pattern IS NOT NULL
            GROUP BY ae.file, ae.line, ae.method, ae.pattern
            ORDER BY ae.file, ae.pattern
            """
        )
        rows = self.db.execute(sql, params)

        for file, line, _method, pattern, controls_str in rows:
            pattern_lower = pattern.lower() if pattern else ""
            if not any(sensitive in pattern_lower for sensitive in sensitive_patterns_lower):
                continue

            controls = controls_str.split("|") if controls_str else []
            controls_lower = [str(c).lower() for c in controls if c]

            has_auth = any(
                any(auth in control for auth in auth_patterns_lower) for control in controls_lower
            )

            if not has_auth:
                self.findings.append(
                    StandardFinding(
                        rule_name="api-sensitive-no-auth",
                        message=f'Sensitive endpoint "{pattern}" lacks authentication',
                        file_path=file,
                        line=line or 1,
                        severity=Severity.CRITICAL,
                        category="authentication",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-306",
                    )
                )

    def _check_graphql_mutations(self):
        """Check GraphQL mutations for authentication using database queries."""

        sql, params = Q.raw(
            """
            SELECT
                f.field_name,
                f.line AS field_line,
                t.schema_path,
                rm.resolver_path,
                rm.resolver_line,
                f.directives_json
            FROM graphql_types t
            JOIN graphql_fields f ON f.type_id = t.type_id
            LEFT JOIN graphql_resolver_mappings rm ON rm.field_id = f.field_id
            WHERE t.type_name = 'Mutation'
            ORDER BY f.field_name
            """
        )

        try:
            rows = self.db.execute(sql, params)
        except Exception:
            return

        for (
            field_name,
            field_line,
            schema_path,
            resolver_path,
            resolver_line,
            directives_json,
        ) in rows:
            has_auth_directive = False
            if directives_json:
                directives = json.loads(directives_json)
                for directive in directives:
                    if any(
                        auth in directive.get("name", "")
                        for auth in ["@auth", "@authenticated", "@requireAuth", "@authorize"]
                    ):
                        has_auth_directive = True
                        break

            if has_auth_directive:
                continue

            if resolver_path and resolver_line:
                has_auth = self._check_auth_nearby(resolver_path, resolver_line)
                if has_auth:
                    continue

            self.findings.append(
                StandardFinding(
                    rule_name="graphql-mutation-no-auth",
                    message=f'GraphQL mutation "{field_name}" lacks authentication directive or resolver protection',
                    file_path=schema_path
                    if schema_path
                    else resolver_path
                    if resolver_path
                    else "unknown",
                    line=field_line if field_line else resolver_line if resolver_line else 0,
                    severity=Severity.HIGH,
                    category="authentication",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-306",
                )
            )

    def _check_weak_auth_patterns(self):
        """Check for weak authentication patterns."""

        sql, params = Q.raw(
            """
            SELECT
                ae.file,
                ae.line,
                ae.method,
                ae.pattern,
                GROUP_CONCAT(aec.control_name, '|') as controls_str
            FROM api_endpoints ae
            LEFT JOIN api_endpoint_controls aec
                ON ae.file = aec.endpoint_file
                AND ae.line = aec.endpoint_line
            GROUP BY ae.file, ae.line, ae.method, ae.pattern
            HAVING controls_str IS NOT NULL
            ORDER BY ae.file, ae.pattern
            """
        )
        rows = self.db.execute(sql, params)

        for file, line, _method, pattern, controls_concat in rows:
            controls = controls_concat.split("|") if controls_concat else []
            controls_str = " ".join(str(c).lower() for c in controls if c)

            if "basic" in controls_str and "auth" in controls_str:
                self.findings.append(
                    StandardFinding(
                        rule_name="api-basic-auth",
                        message=f"Basic authentication used for {pattern}",
                        file_path=file,
                        line=line or 1,
                        severity=Severity.MEDIUM,
                        category="authentication",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-344",
                    )
                )

            if pattern and ("api_key=" in pattern or "apikey=" in pattern):
                self.findings.append(
                    StandardFinding(
                        rule_name="api-key-in-url",
                        message=f"API key passed in URL: {pattern}",
                        file_path=file,
                        line=line or 1,
                        severity=Severity.HIGH,
                        category="authentication",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-598",
                    )
                )

    def _check_csrf_protection(self):
        """Check if state-changing endpoints have CSRF protection."""
        csrf_patterns_lower = [p.lower() for p in self.patterns.CSRF_PATTERNS]

        sql, params = Q.raw(
            """
            SELECT
                ae.file,
                ae.line,
                ae.method,
                ae.pattern,
                GROUP_CONCAT(aec.control_name, '|') as controls_str
            FROM api_endpoints ae
            LEFT JOIN api_endpoint_controls aec
                ON ae.file = aec.endpoint_file
                AND ae.line = aec.endpoint_line
            WHERE UPPER(ae.method) IN ('POST', 'PUT', 'PATCH', 'DELETE')
            GROUP BY ae.file, ae.line, ae.method, ae.pattern
            ORDER BY ae.file, ae.pattern
            """
        )
        rows = self.db.execute(sql, params)

        for file, line, method, pattern, controls_str in rows:
            if pattern and ("/api/" in pattern or "/v1/" in pattern or "/v2/" in pattern):
                continue

            controls = controls_str.split("|") if controls_str else []
            controls_lower = [str(c).lower() for c in controls if c]

            has_csrf = any(
                any(csrf in control for csrf in csrf_patterns_lower) for control in controls_lower
            )

            if not has_csrf:
                self.findings.append(
                    StandardFinding(
                        rule_name="api-missing-csrf",
                        message=f"State-changing endpoint lacks CSRF protection: {method} {pattern}",
                        file_path=file,
                        line=line or 1,
                        severity=Severity.MEDIUM,
                        category="authentication",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-352",
                    )
                )

    def _check_auth_nearby(self, file: str, line: int) -> bool:
        """Check if there's authentication middleware nearby."""
        auth_patterns = list(self.patterns.AUTH_MIDDLEWARE)
        placeholders = ",".join(["?"] * len(auth_patterns))

        rows = self.db.query(
            Q("function_call_args")
            .select("COUNT(*)")
            .where("file = ?", file)
            .where(f"ABS(line - {line}) <= 20")
            .where(f"callee_function IN ({placeholders})", *auth_patterns)
        )

        return rows[0][0] > 0 if rows else False

    def _determine_severity(self, pattern: str, method: str) -> Severity:
        """Determine severity based on endpoint pattern and method."""
        if not pattern:
            return Severity.HIGH

        pattern_lower = pattern.lower()

        for sensitive in self.patterns.SENSITIVE_OPERATIONS:
            if sensitive.lower() in pattern_lower:
                return Severity.CRITICAL

        if method.upper() == "DELETE":
            return Severity.HIGH

        if any(word in pattern_lower for word in ["admin", "user", "account", "password"]):
            return Severity.CRITICAL

        if any(word in pattern_lower for word in ["payment", "billing", "checkout"]):
            return Severity.CRITICAL

        return Severity.HIGH

    def _determine_confidence(self, pattern: str, controls: list) -> Confidence:
        """Determine confidence level based on available information."""

        if pattern and not controls:
            return Confidence.HIGH

        if controls:
            controls_str = " ".join(str(c) for c in controls)
            if "custom" in controls_str.lower() or "internal" in controls_str.lower():
                return Confidence.LOW

            return Confidence.MEDIUM

        if pattern:
            pattern_lower = pattern.lower()
            if any(word in pattern_lower for word in ["public", "open", "health"]):
                return Confidence.LOW

        return Confidence.MEDIUM


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect API authentication security issues.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        analyzer = ApiAuthAnalyzer(db)
        findings = analyzer.analyze()
        return RuleResult(findings=findings, manifest=db.get_manifest())


def register_taint_patterns(taint_registry):
    """Register API auth-specific taint patterns."""
    patterns = ApiAuthPatterns()

    for pattern in patterns.SENSITIVE_OPERATIONS:
        taint_registry.register_sink(pattern, "sensitive_operation", "api")

    for pattern in patterns.AUTH_MIDDLEWARE:
        taint_registry.register_sanitizer(pattern, "api")

    for pattern in patterns.PUBLIC_ENDPOINT_PATTERNS:
        taint_registry.register_source(pattern, "public_endpoint", "api")


__all__ = [
    "analyze",
    "METADATA",
    "register_taint_patterns",
    "ApiAuthPatterns",
]
