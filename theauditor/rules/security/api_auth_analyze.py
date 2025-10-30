"""API Authentication Security Analyzer - Database-First Approach.

Detects missing authentication on state-changing API endpoints using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows golden standard patterns from compose_analyze.py:
- Frozensets for all patterns
- Table existence checks
- Graceful degradation
- Proper confidence levels

Detects:
- Missing authentication on POST/PUT/PATCH/DELETE endpoints
- Weak authentication patterns
- Public endpoints that shouldn't be public
- GraphQL mutations without auth
- API key authentication issues
"""

import sqlite3
import json
from typing import List, Set
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata

# ============================================================================
# RULE METADATA (Golden Standard)
# ============================================================================

METADATA = RuleMetadata(
    name="api_authentication",
    category="security",
    target_extensions=['.py', '.js', '.ts'],
    exclude_patterns=['test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)

# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class ApiAuthPatterns:
    """Immutable pattern definitions for API authentication detection."""

    # State-changing HTTP methods that require authentication
    STATE_CHANGING_METHODS = frozenset([
        'POST', 'PUT', 'PATCH', 'DELETE', 'post', 'put', 'patch', 'delete'
    ])

    # GraphQL mutations that require authentication
    GRAPHQL_MUTATIONS = frozenset([
        'mutation', 'Mutation', 'createMutation', 'updateMutation',
        'deleteMutation', 'upsertMutation'
    ])

    # Authentication middleware/decorator patterns
    AUTH_MIDDLEWARE = frozenset([
        # Generic authentication
        'auth', 'authenticate', 'authenticated', 'authorization', 'authorize',
        'authorized', 'requireAuth', 'requiresAuth', 'isAuthenticated',
        'ensureAuthenticated', 'protect', 'protected', 'secure', 'secured',
        'checkAuth', 'validateAuth', 'verifyAuth', 'authRequired',

        # JWT specific
        'jwt', 'verifyToken', 'validateToken', 'checkToken', 'jwtAuth',
        'verifyJWT', 'validateJWT', 'checkJWT', 'decodeToken', 'verifyJwt',
        'jwtMiddleware', 'jwtRequired', 'requireJWT', 'jwtVerify',

        # Session/Cookie
        'session', 'checkSession', 'validateSession', 'requireSession',
        'cookie', 'checkCookie', 'validateCookie', 'sessionAuth',
        'sessionRequired', 'cookieAuth', 'cookieRequired', 'hasSession',

        # Framework specific - Express/Node.js
        'passport', 'passport.authenticate', 'ensureLoggedIn', 'requireUser',
        'currentUser', 'isLoggedIn', 'loggedIn', 'ensureUser',

        # Framework specific - Python
        'login_required', 'permission_required', 'requires_auth',
        'auth_required', 'token_required', 'api_key_required',
        '@login_required', '@auth_required', '@authenticated',

        # Framework specific - .NET
        '[Authorize]', '[Authentication]', '[RequireAuth]',
        'AuthorizeAttribute', 'AuthenticationAttribute',

        # Role-based access control
        'role', 'checkRole', 'hasRole', 'requireRole', 'roleRequired',
        'permission', 'checkPermission', 'hasPermission', 'permissionRequired',
        'admin', 'requireAdmin', 'isAdmin', 'checkAdmin', 'adminOnly',
        'rbac', 'acl', 'checkAcl', 'hasAccess', 'accessControl',

        # API Key authentication
        'apiKey', 'api_key', 'checkApiKey', 'validateApiKey',
        'requireApiKey', 'verifyApiKey', 'x-api-key', 'apiKeyRequired',
        'apiKeyAuth', 'apiKeyMiddleware', 'hasApiKey',

        # OAuth/OAuth2
        'oauth', 'checkOAuth', 'validateOAuth', 'oauthAuth',
        'oauth2', 'bearerToken', 'bearerAuth', 'checkBearer',

        # Guards (Angular/NestJS pattern)
        'guard', 'Guard', 'authGuard', 'AuthGuard', 'canActivate',
        'UseGuards', '@UseGuards', 'JwtGuard', 'LocalGuard',

        # Other security middleware
        'middleware', 'authMiddleware', 'securityMiddleware',
        'authenticationMiddleware', 'authorizationMiddleware',
        'tokenMiddleware', 'userMiddleware'
    ])

    # Patterns indicating public/open endpoints (no auth needed)
    PUBLIC_ENDPOINT_PATTERNS = frozenset([
        'public', 'open', 'anonymous', 'noauth', 'no-auth',
        'skipAuth', 'skipAuthentication', 'allowAnonymous',
        'isPublic', 'publicRoute', 'publicEndpoint', 'health',
        'healthcheck', 'health-check', 'ping', 'status', 'version',
        'metrics', 'swagger', 'docs', 'documentation', 'spec'
    ])

    # Sensitive operations that ALWAYS need auth
    SENSITIVE_OPERATIONS = frozenset([
        # User management
        'user', 'users', 'profile', 'account', 'settings',
        'password', 'reset', 'change-password', 'update-password',

        # Admin operations
        'admin', 'administrator', 'superuser', 'root',
        'config', 'configuration', 'system', 'backup',

        # Financial/payment
        'payment', 'billing', 'invoice', 'subscription',
        'checkout', 'purchase', 'order', 'transaction',

        # Data operations
        'delete', 'remove', 'destroy', 'purge', 'truncate',
        'export', 'download', 'backup', 'restore',

        # Security operations
        'token', 'key', 'secret', 'credential', 'certificate',
        'audit', 'log', 'security', 'permission', 'role'
    ])

    # Rate limiting patterns (sometimes used instead of auth)
    RATE_LIMIT_PATTERNS = frozenset([
        'rateLimit', 'rate-limit', 'throttle', 'rateLimiter',
        'speedLimiter', 'bruteForce', 'ddos', 'flood',
        'requestLimit', 'apiLimit', 'quotaLimit'
    ])

    # CSRF protection patterns
    CSRF_PATTERNS = frozenset([
        'csrf', 'xsrf', 'csrfToken', 'xsrfToken', 'csrfProtection',
        'validateCsrf', 'checkCsrf', 'verifyCsrf', 'csrfMiddleware',
        'doubleCookie', 'sameSite', 'origin-check'
    ])

    # GraphQL specific patterns
    GRAPHQL_PATTERNS = frozenset([
        'graphql', 'GraphQL', 'apollo', 'relay',
        'query', 'Query', 'mutation', 'Mutation',
        'subscription', 'Subscription', 'resolver', 'Resolver'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class ApiAuthAnalyzer:
    """Analyzer for API authentication security issues."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = ApiAuthPatterns()
        self.findings = []

    def analyze(self) -> List[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of API authentication issues found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Run authentication checks
            self._check_missing_auth_on_mutations()
            self._check_sensitive_endpoints()
            self._check_graphql_mutations()
            self._check_weak_auth_patterns()
            self._check_csrf_protection()

        finally:
            conn.close()

        return self.findings

    def _check_missing_auth_on_mutations(self):
        """Check for state-changing endpoints without authentication."""
        # Convert patterns to lowercase for case-insensitive matching
        auth_patterns_lower = [p.lower() for p in self.patterns.AUTH_MIDDLEWARE]
        public_patterns_lower = [p.lower() for p in self.patterns.PUBLIC_ENDPOINT_PATTERNS]

        # JOIN with api_endpoint_controls to get controls for each endpoint
        self.cursor.execute("""
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
        """)

        for file, line, method, pattern, controls_str in self.cursor.fetchall():
            # Parse controls from concatenated string
            controls = controls_str.split('|') if controls_str else []

            # Convert to lowercase for matching
            controls_lower = [str(c).lower() for c in controls if c]
            pattern_lower = pattern.lower() if pattern else ''

            # Check if this is explicitly a public endpoint
            is_public = any(pub in pattern_lower for pub in public_patterns_lower)
            if is_public:
                continue  # Skip public endpoints

            # Check for authentication middleware
            has_auth = any(
                any(auth in control for auth in auth_patterns_lower)
                for control in controls_lower
            )

            if not has_auth:
                # Determine severity based on endpoint pattern
                severity = self._determine_severity(pattern, method)
                confidence = self._determine_confidence(pattern, controls)

                self.findings.append(StandardFinding(
                    rule_name='api-missing-auth',
                    message=f'State-changing endpoint lacks authentication: {method} {pattern}',
                    file_path=file,
                    line=line or 1,
                    severity=severity,
                    category='authentication',
                    confidence=confidence,
                    cwe_id='CWE-306'  # Missing Authentication for Critical Function
                ))

    def _check_sensitive_endpoints(self):
        """Check if sensitive operations have proper authentication."""
        sensitive_patterns_lower = [p.lower() for p in self.patterns.SENSITIVE_OPERATIONS]
        auth_patterns_lower = [p.lower() for p in self.patterns.AUTH_MIDDLEWARE]

        # JOIN with api_endpoint_controls to get controls for each endpoint
        self.cursor.execute("""
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
        """)

        for file, line, method, pattern, controls_str in self.cursor.fetchall():
            # Check if pattern contains any sensitive operation
            pattern_lower = pattern.lower() if pattern else ''
            if not any(sensitive in pattern_lower for sensitive in sensitive_patterns_lower):
                continue

            # Parse controls from concatenated string
            controls = controls_str.split('|') if controls_str else []
            controls_lower = [str(c).lower() for c in controls if c]

            # Check for authentication
            has_auth = any(
                any(auth in control for auth in auth_patterns_lower)
                for control in controls_lower
            )

            if not has_auth:
                self.findings.append(StandardFinding(
                    rule_name='api-sensitive-no-auth',
                    message=f'Sensitive endpoint "{pattern}" lacks authentication',
                    file_path=file,
                    line=line or 1,
                    severity=Severity.CRITICAL,
                    category='authentication',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-306'
                ))

    def _check_graphql_mutations(self):
        """Check GraphQL mutations for authentication."""
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
            ORDER BY file, line
            LIMIT 2000
        """)

        for file, line, func, args in self.cursor.fetchall():
            # Check if function matches GraphQL patterns
            func_lower = func.lower()
            if not (func in self.patterns.GRAPHQL_PATTERNS or
                   'resolver' in func_lower or
                   'Mutation' in func):
                continue

            if 'mutation' in func.lower() or 'Mutation' in func:
                # Check if there's auth nearby
                has_auth = self._check_auth_nearby(file, line)

                if not has_auth:
                    self.findings.append(StandardFinding(
                        rule_name='graphql-mutation-no-auth',
                        message=f'GraphQL mutation "{func}" lacks authentication',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='authentication',
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-306'
                    ))

    def _check_weak_auth_patterns(self):
        """Check for weak authentication patterns."""
        # JOIN with api_endpoint_controls to get controls for each endpoint
        self.cursor.execute("""
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
        """)

        for file, line, method, pattern, controls_concat in self.cursor.fetchall():
            # Parse controls from concatenated string
            controls = controls_concat.split('|') if controls_concat else []
            controls_str = ' '.join(str(c).lower() for c in controls if c)

            # Check for basic auth (weak)
            if 'basic' in controls_str and 'auth' in controls_str:
                self.findings.append(StandardFinding(
                    rule_name='api-basic-auth',
                    message=f'Basic authentication used for {pattern}',
                    file_path=file,
                    line=line or 1,
                    severity=Severity.MEDIUM,
                    category='authentication',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-344'  # Use of Weak Authentication
                ))

            # Check for API key in URL (bad practice)
            if pattern and ('api_key=' in pattern or 'apikey=' in pattern):
                self.findings.append(StandardFinding(
                    rule_name='api-key-in-url',
                    message=f'API key passed in URL: {pattern}',
                    file_path=file,
                    line=line or 1,
                    severity=Severity.HIGH,
                    category='authentication',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-598'  # Information Exposure Through Query Strings
                ))

    def _check_csrf_protection(self):
        """Check if state-changing endpoints have CSRF protection."""
        csrf_patterns_lower = [p.lower() for p in self.patterns.CSRF_PATTERNS]

        # JOIN with api_endpoint_controls to get controls for each endpoint
        self.cursor.execute("""
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
        """)

        for file, line, method, pattern, controls_str in self.cursor.fetchall():
            # Skip if this looks like a pure API endpoint
            if pattern and ('/api/' in pattern or '/v1/' in pattern or '/v2/' in pattern):
                continue

            # Parse controls from concatenated string
            controls = controls_str.split('|') if controls_str else []
            controls_lower = [str(c).lower() for c in controls if c]

            # Check for CSRF protection
            has_csrf = any(
                any(csrf in control for csrf in csrf_patterns_lower)
                for control in controls_lower
            )

            if not has_csrf:
                self.findings.append(StandardFinding(
                    rule_name='api-missing-csrf',
                    message=f'State-changing endpoint lacks CSRF protection: {method} {pattern}',
                    file_path=file,
                    line=line or 1,
                    severity=Severity.MEDIUM,
                    category='authentication',
                    confidence=Confidence.LOW,  # Low confidence as it might be an API
                    cwe_id='CWE-352'  # Cross-Site Request Forgery
                ))

    def _check_auth_nearby(self, file: str, line: int) -> bool:
        """Check if there's authentication middleware nearby."""
        auth_patterns = list(self.patterns.AUTH_MIDDLEWARE)
        placeholders = ','.join('?' * len(auth_patterns))

        self.cursor.execute(f"""
            SELECT COUNT(*) FROM function_call_args
            WHERE file = ?
              AND ABS(line - ?) <= 20
              AND callee_function IN ({placeholders})
            LIMIT 1
        """, [file, line] + auth_patterns)

        return self.cursor.fetchone()[0] > 0

    def _determine_severity(self, pattern: str, method: str) -> Severity:
        """Determine severity based on endpoint pattern and method."""
        if not pattern:
            return Severity.HIGH

        pattern_lower = pattern.lower()

        # Critical severity for sensitive operations
        for sensitive in self.patterns.SENSITIVE_OPERATIONS:
            if sensitive.lower() in pattern_lower:
                return Severity.CRITICAL

        # DELETE operations are always high severity
        if method.upper() == 'DELETE':
            return Severity.HIGH

        # User/admin operations are critical
        if any(word in pattern_lower for word in ['admin', 'user', 'account', 'password']):
            return Severity.CRITICAL

        # Financial operations are critical
        if any(word in pattern_lower for word in ['payment', 'billing', 'checkout']):
            return Severity.CRITICAL

        return Severity.HIGH

    def _determine_confidence(self, pattern: str, controls: list) -> Confidence:
        """Determine confidence level based on available information."""
        # High confidence if we have clear pattern and no controls
        if pattern and not controls:
            return Confidence.HIGH

        # Medium confidence if we have controls but no auth detected
        if controls:
            # Check if there might be custom auth we didn't detect
            controls_str = ' '.join(str(c) for c in controls)
            if 'custom' in controls_str.lower() or 'internal' in controls_str.lower():
                return Confidence.LOW

            return Confidence.MEDIUM

        # Low confidence if pattern suggests it might be public
        if pattern:
            pattern_lower = pattern.lower()
            if any(word in pattern_lower for word in ['public', 'open', 'health']):
                return Confidence.LOW

        return Confidence.MEDIUM


# ============================================================================
# MISSING DATABASE FEATURES FLAGGED
# ============================================================================

"""
FLAGGED: Missing database features for better API auth detection:

1. HTTP header extraction:
   - Can't detect Authorization headers directly
   - Need to extract x-api-key, Bearer token patterns

2. Decorator extraction:
   - Can't detect @login_required or similar decorators
   - Need decorator parsing in indexer

3. Middleware chain:
   - Can't see full middleware stack for an endpoint
   - Need middleware ordering/chaining information

4. Route inheritance:
   - Can't detect auth at router level that applies to all routes
   - Need route hierarchy information

5. GraphQL schema:
   - Can't parse GraphQL schema for auth directives
   - Need GraphQL-specific parsing
"""


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_apiauth_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect API authentication security issues.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of API authentication issues found
    """
    analyzer = ApiAuthAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# TAINT REGISTRATION (For Orchestrator)
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register API auth-specific taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = ApiAuthPatterns()

    # Register sensitive operations as sinks
    for pattern in patterns.SENSITIVE_OPERATIONS:
        taint_registry.register_sink(pattern, "sensitive_operation", "api")

    # Register auth middleware as sanitizers (they clean/validate)
    for pattern in patterns.AUTH_MIDDLEWARE:
        taint_registry.register_sanitizer(pattern, "auth_validation", "api")

    # Register public patterns as sources (untrusted)
    for pattern in patterns.PUBLIC_ENDPOINT_PATTERNS:
        taint_registry.register_source(pattern, "public_endpoint", "api")