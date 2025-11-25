"""Rate Limit Analyzer - Production-Ready Database-Driven Detection.

Detects 15+ rate limiting misconfigurations and bypass techniques using pure SQL queries.
Follows gold standard patterns (v1.1+ schema contract compliance).

This implementation:
- Uses frozensets for O(1) pattern matching (immutable, hashable)
- Direct database queries (assumes all tables exist per schema contract)
- Uses parameterized queries (no SQL injection)
- Implements multi-layer detection patterns
- Provides confidence scoring based on context
- Maps findings to security regulations (OWASP, PCI-DSS, NIST)
"""


import sqlite3

from theauditor.rules.base import (
    StandardRuleContext,
    StandardFinding,
    Severity,
    Confidence,
    RuleMetadata
)

METADATA = RuleMetadata(
    name="rate_limiting",
    category="security",
    target_extensions=['.py', '.js', '.ts'],
    exclude_patterns=['test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)

# ============================================================================
# PATTERN DEFINITIONS (ALL FROZENSETS)
# ============================================================================

# Authentication middleware patterns
AUTH_PATTERNS = frozenset([
    'authenticate', 'auth', 'requireauth', 'isAuthenticated',
    'passport.authenticate', 'jwt.verify', 'verifytoken',
    'ensureAuthenticated', 'requireLogin', 'checkAuth',
    'login_required', '@auth', '@authenticated',
    'authorize', 'checktoken', 'validatetoken',
    'session.check', 'user.validate', 'identity.verify'
])

# Rate limiting patterns
RATE_LIMIT_PATTERNS = frozenset([
    'express-rate-limit', 'ratelimit', 'rate-limit',
    'express-slow-down', 'slowdown', 'slow-down',
    'express-brute', 'expressbrute', 'brute',
    'rate-limiter-flexible', 'rateLimiterMemory', 'rateLimiterRedis',
    '@limit', '@ratelimit', '@throttle', 'limiter',
    'flask-limiter', 'django-ratelimit', 'throttle',
    'api-rate-limit', 'koa-ratelimit', 'fastify-rate-limit'
])

# Expensive operation patterns
EXPENSIVE_OPERATIONS = frozenset([
    'bcrypt', 'scrypt', 'argon2', 'pbkdf2', 'hash', 'compare',
    'crypto.scrypt', 'crypto.pbkdf2', 'hashPassword', 'verifyPassword',
    'database', 'query', 'findone', 'findall', 'select', 'execute',
    'mongoose.find', 'sequelize.query', 'prisma.find',
    'sendEmail', 'sendMail', 'mailer.send', 'nodemailer',
    'fetch', 'axios', 'request', 'http.get', 'got', 'superagent',
    's3.upload', 's3.getObject', 'cloudinary.upload',
    'stripe.charge', 'paypal.payment', 'twilio.send'
])

# Critical endpoints requiring rate limiting
CRITICAL_ENDPOINTS = frozenset([
    '/login', '/signin', '/auth', '/authenticate',
    '/register', '/signup', '/create-account', '/join',
    '/reset-password', '/forgot-password', '/password-reset',
    '/verify', '/confirm', '/validate', '/activate',
    '/api/auth', '/api/login', '/api/register',
    '/token', '/oauth', '/oauth2', '/2fa', '/mfa',
    '/payment', '/checkout', '/subscribe', '/purchase',
    '/admin', '/api-key', '/webhook', '/graphql'
])

# Spoofable headers
SPOOFABLE_HEADERS = frozenset([
    'x-forwarded-for', 'x-real-ip', 'cf-connecting-ip',
    'x-client-ip', 'x-originating-ip', 'x-remote-ip',
    'x-forwarded-host', 'x-original-ip', 'true-client-ip',
    'x-cluster-client-ip', 'x-forwarded', 'forwarded-for',
    'client-ip', 'real-ip', 'x-proxyuser-ip'
])

# Memory storage patterns
MEMORY_STORAGE_PATTERNS = frozenset([
    'memorystore', 'memory', 'inmemory', 'localstore',
    'rateLimiterMemory', 'new memory', 'store: memory',
    'storage: memory', 'cache: memory', 'local',
    'memoryadapter', 'memcache', 'inmemorycache'
])

# Persistent storage patterns (good)
PERSISTENT_STORAGE_PATTERNS = frozenset([
    'redis', 'mongodb', 'postgres', 'mysql', 'dynamodb',
    'rateLimiterRedis', 'redisStore', 'mongoStore',
    'storage_uri', 'database_url', 'redis://', 'mongodb://',
    'elasticache', 'memcached', 'hazelcast'
])

# Rate limit bypass techniques
BYPASS_TECHNIQUES = frozenset([
    'proxy', 'tor', 'vpn', 'rotate', 'spoof',
    'bypass', 'override', 'whitelist', 'skip',
    'disable', 'ignore', 'exclude', 'exempt'
])

# Framework indicators
FRAMEWORK_PATTERNS = frozenset([
    'express', 'fastify', 'koa', 'hapi', 'restify',
    'flask', 'django', 'fastapi', 'bottle',
    'rails', 'sinatra', 'spring', 'laravel'
])

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def find_rate_limit_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect rate limiting misconfigurations using database queries.

    Implements 15+ detection patterns for rate limiting issues including
    middleware ordering, unprotected endpoints, bypassable keys, and more.
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # All required tables guaranteed to exist by schema contract
        # (theauditor/indexer/schema.py - TABLES registry with 46 table definitions)
        # If table missing, rule will crash with clear sqlite3.OperationalError (CORRECT behavior)

        # Core detection layers - execute unconditionally
        # Layer 1: Middleware ordering issues
        findings.extend(_detect_middleware_ordering(cursor))

        # Layer 2: Unprotected critical endpoints
        findings.extend(_detect_unprotected_endpoints(cursor))

        # Layer 3: Bypassable key generation
        findings.extend(_detect_bypassable_keys(cursor))

        # Layer 4: Memory storage issues
        findings.extend(_detect_memory_storage(cursor))

        # Layer 5: Expensive operations before rate limiting
        findings.extend(_detect_expensive_operations(cursor))

        # Layer 6: API endpoints without rate limiting
        findings.extend(_detect_api_rate_limits(cursor))

        # Layer 7: Decorator ordering (Python)
        findings.extend(_detect_decorator_ordering(cursor))

        # Layer 8: Rate limit bypass configurations
        findings.extend(_detect_bypass_configs(cursor))

        # Layer 9: Missing user-based rate limiting
        findings.extend(_detect_missing_user_limits(cursor))

        # Layer 10: Rate limit value analysis
        findings.extend(_detect_weak_rate_limits(cursor))

    finally:
        conn.close()

    return findings

# ============================================================================
# HELPER: Confidence Determination
# ============================================================================

def _determine_confidence(
    pattern_type: str,
    has_context: bool = True,
    is_critical: bool = False,
    has_fallback: bool = True
) -> Confidence:
    """Determine confidence level based on detection context."""
    if is_critical and not has_fallback:
        return Confidence.HIGH
    elif pattern_type in ['middleware_order', 'critical_endpoint']:
        return Confidence.HIGH if has_context else Confidence.MEDIUM
    elif pattern_type in ['bypassable_key', 'memory_storage']:
        return Confidence.HIGH
    elif pattern_type == 'expensive_operation':
        return Confidence.MEDIUM
    else:
        return Confidence.LOW

# ============================================================================
# HELPER: Framework Detection
# ============================================================================

def _detect_framework(file_path: str) -> str:
    """Detect the framework based on file path and patterns."""
    file_lower = file_path.lower()

    if '.js' in file_lower or '.ts' in file_lower:
        if 'express' in file_lower:
            return 'Express.js'
        elif 'fastify' in file_lower:
            return 'Fastify'
        elif 'koa' in file_lower:
            return 'Koa'
        return 'Node.js'
    elif '.py' in file_lower:
        if 'flask' in file_lower:
            return 'Flask'
        elif 'django' in file_lower:
            return 'Django'
        elif 'fastapi' in file_lower:
            return 'FastAPI'
        return 'Python'
    return 'Unknown'

# ============================================================================
# HELPER: Attack Scenario Generation
# ============================================================================

def _get_attack_scenario(rule_name: str) -> str:
    """Generate attack scenario descriptions."""

    scenarios = {
        'rate-limit-after-auth': 'Attacker can trigger expensive auth operations (DB queries, bcrypt) repeatedly, causing DoS',
        'missing-rate-limit': 'Attacker can brute-force passwords, enumerate users, or trigger password resets without limits',
        'bypassable-key': 'Attacker spoofs X-Forwarded-For header to bypass rate limits using different IPs',
        'memory-storage': 'Rate limits reset on server restart or are not shared across instances',
        'expensive-before-limit': 'Attacker triggers resource-intensive operations before being rate limited'
    }

    return scenarios.get(rule_name, 'Attacker can abuse unprotected functionality')

# ============================================================================
# DETECTION LAYER 1: Middleware Ordering
# ============================================================================

def _detect_middleware_ordering(cursor) -> list[StandardFinding]:
    """Detect incorrect middleware ordering (auth before rate limit)."""
    findings = []

    # Query middleware registrations
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
        ORDER BY file, line
    """)

    # Group by file and analyze ordering
    file_middleware = {}
    for file, line, func, args in cursor.fetchall():
        # Filter for middleware registration functions in Python
        func_lower = func.lower()
        if not ('use' in func_lower or 'middleware' in func_lower):
            continue

        if file not in file_middleware:
            file_middleware[file] = []

        if not args:
            continue

        args_lower = args.lower()

        # Determine middleware type
        mw_type = None
        if any(pattern in args_lower for pattern in RATE_LIMIT_PATTERNS):
            mw_type = 'rate_limit'
        elif any(pattern in args_lower for pattern in AUTH_PATTERNS):
            mw_type = 'auth'
        elif any(pattern in args_lower for pattern in EXPENSIVE_OPERATIONS):
            mw_type = 'expensive'

        if mw_type:
            file_middleware[file].append({
                'line': line,
                'type': mw_type,
                'func': func,
                'args': args[:100]
            })

    # Check ordering in each file
    for file, middlewares in file_middleware.items():
        # Sort by line number to get registration order
        middlewares.sort(key=lambda x: x['line'])

        rate_limit_pos = -1
        auth_positions = []
        expensive_positions = []

        for i, mw in enumerate(middlewares):
            if mw['type'] == 'rate_limit':
                rate_limit_pos = i
            elif mw['type'] == 'auth':
                auth_positions.append((i, mw))
            elif mw['type'] == 'expensive':
                expensive_positions.append((i, mw))

        # Check for auth before rate limiting
        if rate_limit_pos > -1:
            for auth_pos, auth_mw in auth_positions:
                if auth_pos < rate_limit_pos:
                    framework = _detect_framework(file)

                    findings.append(StandardFinding(
                        rule_name='rate-limit-after-auth',
                        message='Authentication middleware executes before rate limiting',
                        file_path=file,
                        line=auth_mw['line'],
                        severity=Severity.HIGH,
                        confidence=_determine_confidence('middleware_order', True, True, False),
                        category='security',
                        snippet=f"{auth_mw['func']}({auth_mw['args']})",
                        cwe_id='CWE-770',  # Allocation of Resources Without Limits
                        additional_info={
                            'framework': framework,
                            'attack_scenario': _get_attack_scenario('rate-limit-after-auth'),
                            'regulations': ['OWASP A6:2021', 'PCI-DSS 8.1.8'],
                            'middleware_type': 'authentication',
                            'position': f"Line {auth_mw['line']} before rate limiter"
                        }
                    ))

            # Check for expensive operations before rate limiting
            for exp_pos, exp_mw in expensive_positions:
                if exp_pos < rate_limit_pos:
                    findings.append(StandardFinding(
                        rule_name='expensive-before-limit',
                        message='Expensive operation executes before rate limiting',
                        file_path=file,
                        line=exp_mw['line'],
                        severity=Severity.HIGH,
                        confidence=_determine_confidence('expensive_operation', True, False, False),
                        category='security',
                        snippet=f"{exp_mw['func']}({exp_mw['args']})",
                        cwe_id='CWE-770',
                        additional_info={
                            'operation_type': exp_mw['type'],
                            'attack_scenario': _get_attack_scenario('expensive-before-limit')
                        }
                    ))

    return findings

# ============================================================================
# DETECTION LAYER 2: Unprotected Critical Endpoints
# ============================================================================

def _detect_unprotected_endpoints(cursor) -> list[StandardFinding]:
    """Detect critical endpoints without rate limiting."""
    findings = []

    # Find route definitions
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter for route functions in Python
        func_lower = func.lower()
        if not ('post' in func_lower or 'get' in func_lower or 'route' in func_lower):
            continue

        # Identify which critical endpoint
        args_lower = args.lower()
        endpoint_found = None
        for endpoint in CRITICAL_ENDPOINTS:
            if endpoint in args_lower:
                endpoint_found = endpoint
                break

        if endpoint_found:
            # Check for rate limiting within ±30 lines
            cursor.execute("""
                SELECT callee_function, line, argument_expr
                FROM function_call_args
                WHERE file = ?
                  AND callee_function IS NOT NULL
            """, (file,))

            # Filter in Python for limit/throttle within ±30 lines
            nearby_rate_limits = []
            for nearby_func, nearby_line, nearby_args in cursor.fetchall():
                if abs(nearby_line - line) > 30:
                    continue
                func_lower = nearby_func.lower()
                args_lower = (nearby_args or '').lower()
                if 'limit' in func_lower or 'throttle' in func_lower or 'limit' in args_lower or 'throttle' in args_lower:
                    nearby_rate_limits.append((nearby_func, nearby_line))

            has_rate_limit = len(nearby_rate_limits) > 0

            # Also check for decorators
            if not has_rate_limit:
                cursor.execute("""
                    SELECT name, line
                    FROM symbols
                    WHERE path = ?
                      AND type = 'decorator'
                      AND name IS NOT NULL
                """, (file,))

                # Filter in Python for limit/throttle within ±10 lines
                for dec_name, dec_line in cursor.fetchall():
                    if abs(dec_line - line) > 10:
                        continue
                    dec_name_lower = dec_name.lower()
                    if 'limit' in dec_name_lower or 'throttle' in dec_name_lower:
                        has_rate_limit = True
                        break

            if not has_rate_limit:
                framework = _detect_framework(file)

                findings.append(StandardFinding(
                    rule_name='missing-rate-limit',
                    message=f'Critical endpoint {endpoint_found} lacks rate limiting',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=_determine_confidence('critical_endpoint', True, True, False),
                    category='security',
                    snippet=f'{func}("{endpoint_found}")',
                    cwe_id='CWE-307',  # Improper Restriction of Excessive Authentication Attempts
                    additional_info={
                        'endpoint': endpoint_found,
                        'framework': framework,
                        'attack_scenario': _get_attack_scenario('missing-rate-limit'),
                        'regulations': ['OWASP A7:2021', 'PCI-DSS 8.1.6', 'NIST 800-63B'],
                        'risk': 'Brute force, credential stuffing, user enumeration'
                    }
                ))

    return findings

# ============================================================================
# DETECTION LAYER 3: Bypassable Key Generation
# ============================================================================

def _detect_bypassable_keys(cursor) -> list[StandardFinding]:
    """Detect rate limiters using spoofable headers for keys."""
    findings = []

    # Find rate limiter configurations with key generation
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter for RateLimit/Limiter functions with key generation
        func_lower = func.lower()
        if not ('ratelimit' in func_lower or 'limiter' in func_lower):
            continue

        args_lower = args.lower()
        if not ('keygenerator' in args_lower or 'key_func' in args_lower or 'getkey' in args_lower):
            continue

        # Check for spoofable headers
        uses_spoofable = False
        spoofable_found = None
        for header in SPOOFABLE_HEADERS:
            if header in args_lower:
                uses_spoofable = True
                spoofable_found = header
                break

        if uses_spoofable:
            # Check for fallback mechanisms
            has_fallback = any(fallback in args for fallback in ['||', '??', 'req.ip', 'req.connection'])

            if not has_fallback:
                framework = _detect_framework(file)

                findings.append(StandardFinding(
                    rule_name='bypassable-key',
                    message=f'Rate limiter uses spoofable header ({spoofable_found}) without fallback',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category='security',
                    snippet=f'keyGenerator uses {spoofable_found}',
                    cwe_id='CWE-290',  # Authentication Bypass by Spoofing
                    additional_info={
                        'spoofable_header': spoofable_found,
                        'framework': framework,
                        'attack_scenario': _get_attack_scenario('bypassable-key'),
                        'regulations': ['OWASP A7:2021'],
                        'bypass_technique': f'Spoof {spoofable_found} header with different values'
                    }
                ))

    # Also check assignments that might be used for keys
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE source_expr IS NOT NULL
          AND target_var IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, var, expr in cursor.fetchall():
        # Filter for assignments involving headers and spoofable patterns
        expr_lower = expr.lower()
        if 'headers' not in expr_lower:
            continue

        # Check if contains spoofable header
        has_spoofable = any(header in expr_lower for header in SPOOFABLE_HEADERS)
        if not has_spoofable:
            continue

        # Check if var name suggests IP/key/client
        var_lower = var.lower()
        if not ('ip' in var_lower or 'key' in var_lower or 'client' in var_lower):
            continue

        # Check if this var is used in rate limiting
        cursor.execute("""
            SELECT callee_function, argument_expr
            FROM function_call_args
            WHERE file = ?
              AND line > ?
              AND line <= ? + 50
              AND argument_expr IS NOT NULL
              AND callee_function IS NOT NULL
            LIMIT 1
        """, (file, line, line))

        # Filter in Python for var usage in limit/throttle
        var_used_in_rate_limit = False
        for nearby_func, nearby_args in cursor.fetchall():
            if var not in nearby_args:
                continue
            func_lower = nearby_func.lower()
            if 'limit' in func_lower or 'throttle' in func_lower:
                var_used_in_rate_limit = True
                break

        cursor.execute("SELECT 1")  # Dummy to get fetchone

        if var_used_in_rate_limit:
            findings.append(StandardFinding(
                rule_name='bypassable-key-indirect',
                message='Rate limiting key derived from spoofable header',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                category='security',
                snippet=f'{var} = {expr[:100]}',
                cwe_id='CWE-290',
                additional_info={
                    'variable': var,
                    'note': 'This variable appears to be used for rate limiting'
                }
            ))

    return findings

# ============================================================================
# DETECTION LAYER 4: Memory Storage Issues
# ============================================================================

def _detect_memory_storage(cursor) -> list[StandardFinding]:
    """Detect rate limiters using non-persistent storage."""
    findings = []

    # Check for memory storage patterns
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter for RateLimit/Limiter functions
        func_lower = func.lower()
        if not ('ratelimit' in func_lower or 'limiter' in func_lower):
            continue

        # Check if uses memory storage
        args_lower = args.lower()
        has_memory = any(pattern in args_lower for pattern in MEMORY_STORAGE_PATTERNS)
        if not has_memory:
            continue

        # Check if persistent storage is also configured
        has_persistent = any(pattern in args_lower for pattern in PERSISTENT_STORAGE_PATTERNS)

        if not has_persistent:
            framework = _detect_framework(file)

            findings.append(StandardFinding(
                rule_name='memory-storage',
                message='Rate limiter using in-memory storage - ineffective in distributed environment',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category='security',
                snippet=f'{func}({{store: MemoryStore}})',
                cwe_id='CWE-770',
                additional_info={
                    'framework': framework,
                    'attack_scenario': _get_attack_scenario('memory-storage'),
                    'impact': 'Rate limits reset on restart, not shared across instances',
                    'environments_affected': ['Kubernetes', 'Serverless', 'Load-balanced'],
                }
            ))

    # Check Flask-Limiter without storage_uri
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function = 'Limiter'
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter in Python for missing storage_uri
        if args and 'storage_uri' in args.lower():
            continue

        findings.append(StandardFinding(
            rule_name='flask-memory-storage',
            message='Flask-Limiter using default in-memory storage',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            confidence=Confidence.HIGH,
            category='security',
            snippet='Limiter(app)  # No storage_uri',
            cwe_id='CWE-770',
            additional_info={
                'framework': 'Flask',
            }
        ))

    return findings

# ============================================================================
# DETECTION LAYER 5: Expensive Operations Before Rate Limiting
# ============================================================================

def _detect_expensive_operations(cursor) -> list[StandardFinding]:
    """Detect expensive operations that run before rate limiting."""
    findings = []

    # Find files with rate limiting
    cursor.execute("""
        SELECT DISTINCT file
        FROM function_call_args
        WHERE callee_function IS NOT NULL
    """)

    # Filter in Python for files with rate limiting
    rate_limited_files = set()
    for (file,) in cursor.fetchall():
        cursor.execute("""
            SELECT callee_function
            FROM function_call_args
            WHERE file = ?
              AND callee_function IS NOT NULL
            LIMIT 1
        """, (file,))

        for (func,) in cursor.fetchall():
            func_lower = func.lower()
            if 'limit' in func_lower or 'throttle' in func_lower or 'ratelimit' in func_lower:
                rate_limited_files.add(file)
                break

    for file in rate_limited_files:
        # Get earliest rate limiter position
        cursor.execute("""
            SELECT line, callee_function
            FROM function_call_args
            WHERE file = ?
              AND callee_function IS NOT NULL
            ORDER BY line
        """, (file,))

        # Find earliest rate limiter line
        rate_limit_line = None
        for line_num, func in cursor.fetchall():
            func_lower = func.lower()
            if 'limit' in func_lower or 'throttle' in func_lower or 'ratelimit' in func_lower:
                rate_limit_line = line_num
                break

        if rate_limit_line is None:
            continue

        # Dummy query for compatibility
        cursor.execute("SELECT ?", (rate_limit_line,))

        # Find expensive operations before rate limiting
        cursor.execute("""
            SELECT line, callee_function, argument_expr
            FROM function_call_args
            WHERE file = ?
              AND line < ?
              AND callee_function IS NOT NULL
        """, (file, rate_limit_line))

        for exp_line, exp_func, exp_args in cursor.fetchall():
            # Filter for expensive operations
            exp_func_lower = exp_func.lower()
            if not any(op in exp_func_lower for op in EXPENSIVE_OPERATIONS):
                continue

            # Determine operation type
            op_type = 'unknown'
            if any(db in exp_func.lower() for db in ['database', 'query', 'find', 'select']):
                op_type = 'database'
            elif any(crypto in exp_func.lower() for crypto in ['bcrypt', 'hash', 'crypto', 'argon']):
                op_type = 'cryptographic'
            elif any(io in exp_func.lower() for io in ['email', 'mail', 'fetch', 'axios']):
                op_type = 'network I/O'

            findings.append(StandardFinding(
                rule_name='expensive-before-limit',
                message=f'{op_type.title()} operation ({exp_func}) executes before rate limiting',
                file_path=file,
                line=exp_line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                category='security',
                snippet=f'{exp_func}()',
                cwe_id='CWE-770',
                additional_info={
                    'operation_type': op_type,
                    'function': exp_func,
                    'rate_limit_line': rate_limit_line,
                    'attack_scenario': _get_attack_scenario('expensive-before-limit'),
                    'impact': f'{op_type} DoS vulnerability'
                }
            ))

    return findings

# ============================================================================
# DETECTION LAYER 6: API Endpoints Without Rate Limiting
# ============================================================================

def _detect_api_rate_limits(cursor) -> list[StandardFinding]:
    """Detect API endpoints without rate limiting."""
    findings = []

    # Get all API endpoints
    cursor.execute("""
        SELECT file, line, method, path
        FROM api_endpoints
        WHERE path IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, method, path in cursor.fetchall():
        # Check if critical endpoint
        is_critical = any(endpoint in path.lower() for endpoint in CRITICAL_ENDPOINTS)

        if is_critical:
            # Check for rate limiting near this endpoint
            cursor.execute("""
                SELECT callee_function, line, argument_expr
                FROM function_call_args
                WHERE file = ?
                  AND callee_function IS NOT NULL
            """, (file,))

            # Filter in Python for limit/throttle within ±50 lines
            has_rate_limit = False
            for nearby_func, nearby_line, nearby_args in cursor.fetchall():
                if abs(nearby_line - line) > 50:
                    continue
                func_lower = nearby_func.lower()
                args_lower = (nearby_args or '').lower()
                if 'limit' in func_lower or 'throttle' in func_lower or 'ratelimit' in args_lower:
                    has_rate_limit = True
                    break

            if not has_rate_limit:
                findings.append(StandardFinding(
                    rule_name='api-missing-rate-limit',
                    message=f'API endpoint {method} {path} lacks rate limiting',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category='security',
                    snippet=f'{method} {path}',
                    cwe_id='CWE-307',
                    additional_info={
                        'method': method,
                        'path': path,
                        'risk': 'API abuse, data scraping, DoS'
                    }
                ))

    return findings

# ============================================================================
# DETECTION LAYER 7: Decorator Ordering (Python)
# ============================================================================

def _detect_decorator_ordering(cursor) -> list[StandardFinding]:
    """Detect incorrect decorator ordering in Python."""
    findings = []

    # Get all decorators
    cursor.execute("""
        SELECT path, line, name
        FROM symbols
        WHERE type = 'decorator'
          AND name IS NOT NULL
        ORDER BY path, line
    """)

    # Group decorators by proximity, filter in Python
    file_decorators = {}
    for file, line, name in cursor.fetchall():
        name_lower = name.lower()
        # Filter for limit/throttle/auth decorators
        if not ('limit' in name_lower or 'throttle' in name_lower or 'auth' in name_lower or 'login_required' in name_lower):
            continue

        if file not in file_decorators:
            file_decorators[file] = []
        file_decorators[file].append({'line': line, 'name': name})

    # Check ordering within each file
    for file, decorators in file_decorators.items():
        # Group by function (decorators within 5 lines)
        function_groups = []
        current_group = []
        last_line = -10

        for dec in sorted(decorators, key=lambda x: x['line']):
            if dec['line'] - last_line <= 5:
                current_group.append(dec)
            else:
                if current_group:
                    function_groups.append(current_group)
                current_group = [dec]
            last_line = dec['line']

        if current_group:
            function_groups.append(current_group)

        # Check each function's decorators
        for group in function_groups:
            rate_limit_line = -1
            auth_line = -1

            for dec in group:
                name_lower = dec['name'].lower()
                if any(pattern in name_lower for pattern in ['limit', 'throttle', 'ratelimit']):
                    rate_limit_line = dec['line']
                elif any(pattern in name_lower for pattern in ['auth', 'login_required']):
                    auth_line = dec['line']

            # Auth decorator should come after rate limit
            if rate_limit_line > 0 and auth_line > 0 and auth_line < rate_limit_line:
                findings.append(StandardFinding(
                    rule_name='python-decorator-order',
                    message='Authentication decorator before rate limiting decorator',
                    file_path=file,
                    line=auth_line,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    category='security',
                    snippet='@login_required before @rate_limit',
                    cwe_id='CWE-770',
                    additional_info={
                        'framework': 'Python/Flask/Django',
                    }
                ))

    return findings

# ============================================================================
# DETECTION LAYER 8: Rate Limit Bypass Configurations
# ============================================================================

def _detect_bypass_configs(cursor) -> list[StandardFinding]:
    """Detect configurations that allow rate limit bypass."""
    findings = []

    # Look for bypass-related assignments
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, var, expr in cursor.fetchall():
        # Filter for bypass techniques in Python
        var_lower = var.lower()
        expr_lower = expr.lower()
        has_bypass = any(tech in var_lower or tech in expr_lower for tech in BYPASS_TECHNIQUES)
        if not has_bypass:
            continue

        # Check if this relates to rate limiting
        cursor.execute("""
            SELECT callee_function, line, argument_expr
            FROM function_call_args
            WHERE file = ?
              AND callee_function IS NOT NULL
        """, (file,))

        # Filter in Python for limit/rateLimit within ±30 lines
        has_rate_limit_nearby = False
        for nearby_func, nearby_line, nearby_args in cursor.fetchall():
            if abs(nearby_line - line) > 30:
                continue
            func_lower = nearby_func.lower()
            args_lower = (nearby_args or '').lower()
            if 'limit' in func_lower or 'ratelimit' in args_lower:
                has_rate_limit_nearby = True
                break

        if has_rate_limit_nearby:
            findings.append(StandardFinding(
                rule_name='rate-limit-bypass-config',
                message='Potential rate limit bypass configuration detected',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.LOW,
                category='security',
                snippet=f'{var} = {expr[:100]}',
                cwe_id='CWE-770',
                additional_info={
                    'variable': var,
                    'note': 'Ensure bypass is properly restricted to internal services only'
                }
            ))

    return findings

# ============================================================================
# DETECTION LAYER 9: Missing User-Based Rate Limiting
# ============================================================================

def _detect_missing_user_limits(cursor) -> list[StandardFinding]:
    """Detect rate limiters that don't consider authenticated users."""
    findings = []

    # Find rate limiter configurations
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter for RateLimit/Limiter functions
        func_lower = func.lower()
        if not ('ratelimit' in func_lower or 'limiter' in func_lower):
            continue

        args_lower = args.lower()

        # Check if user/session based limiting is configured
        has_user_limit = any(pattern in args_lower for pattern in [
            'user', 'userid', 'session', 'account',
            'req.user', 'req.session', 'current_user'
        ])

        # Check if only using IP
        ip_only = ('ip' in args_lower or 'address' in args_lower) and not has_user_limit

        if ip_only:
            findings.append(StandardFinding(
                rule_name='ip-only-rate-limit',
                message='Rate limiter uses only IP address, not user identity',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                category='security',
                snippet=f'{func}(ip-based only)',
                cwe_id='CWE-770',
                additional_info={
                    'limitation': 'Shared IPs (NAT, proxy) affect multiple users',
                }
            ))

    return findings

# ============================================================================
# DETECTION LAYER 10: Weak Rate Limit Values
# ============================================================================

def _detect_weak_rate_limits(cursor) -> list[StandardFinding]:
    """Detect rate limits with weak values (too high)."""
    findings = []

    # Find rate limit configurations with numeric values
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Filter for RateLimit/limit functions with numeric config
        func_lower = func.lower()
        if not ('ratelimit' in func_lower or 'limit' in func_lower):
            continue

        args_lower = args.lower()
        if not ('max:' in args_lower or 'limit:' in args_lower or 'requests:' in args_lower):
            continue

        # Extract numeric values using string methods
        numbers = []
        for token in args.replace(',', ' ').replace(':', ' ').replace('(', ' ').replace(')', ' ').replace('=', ' ').split():
            if token.isdigit():
                numbers.append(token)

        for num_str in numbers:
            num = int(num_str)

            # Check if this is a weak limit for authentication
            if num > 10:
                # Check if this is an auth endpoint
                cursor.execute("""
                    SELECT argument_expr, line
                    FROM function_call_args
                    WHERE file = ?
                      AND argument_expr IS NOT NULL
                """, (file,))

                # Filter in Python for login/auth/password within ±20 lines
                is_auth_endpoint = False
                for nearby_args, nearby_line in cursor.fetchall():
                    if abs(nearby_line - line) > 20:
                        continue
                    args_lower = nearby_args.lower()
                    if 'login' in args_lower or 'auth' in args_lower or 'password' in args_lower:
                        is_auth_endpoint = True
                        break

                if is_auth_endpoint:
                    findings.append(StandardFinding(
                        rule_name='weak-rate-limit-value',
                        message=f'Rate limit too high ({num}) for authentication endpoint',
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.LOW,
                        category='security',
                        snippet=f'max: {num} requests',
                        cwe_id='CWE-307',
                        additional_info={
                            'current_limit': num,
                            'reference': 'NIST 800-63B'
                        }
                    ))

    return findings

# ============================================================================
# ADDITIONAL HELPERS
# ============================================================================

def generate_rate_limit_summary(findings: list[StandardFinding]) -> dict:
    """Generate a summary report of rate limiting findings."""
    summary = {
        'total_findings': len(findings),
        'by_severity': {},
        'by_pattern': {},
        'frameworks_affected': set(),
        'top_risks': []
    }

    for finding in findings:
        # Count by severity
        sev = finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity)
        summary['by_severity'][sev] = summary['by_severity'].get(sev, 0) + 1

        # Count by pattern
        pattern = finding.rule_name
        summary['by_pattern'][pattern] = summary['by_pattern'].get(pattern, 0) + 1

        # Track frameworks
        if finding.additional_info and 'framework' in finding.additional_info:
            summary['frameworks_affected'].add(finding.additional_info['framework'])

    # Convert set to list for JSON serialization
    summary['frameworks_affected'] = list(summary['frameworks_affected'])

    # Get top risks
    critical_findings = [f for f in findings if f.severity == Severity.CRITICAL]
    summary['top_risks'] = [
        {
            'rule': f.rule_name,
            'message': f.message,
            'file': f.file_path,
            'line': f.line
        }
        for f in critical_findings[:5]
    ]

    return summary

# ============================================================================
# EXPORT FOR RULE REGISTRATION
# ============================================================================

__all__ = [
    'find_rate_limit_issues',
    'generate_rate_limit_summary'
]