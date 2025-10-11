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
from typing import List, Set, Dict, Optional, Tuple
from pathlib import Path
from enum import Enum

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

def find_rate_limit_issues(context: StandardRuleContext) -> List[StandardFinding]:
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

def _detect_middleware_ordering(cursor) -> List[StandardFinding]:
    """Detect incorrect middleware ordering (auth before rate limit)."""
    findings = []

    # Query middleware registrations
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function LIKE '%use%'
           OR callee_function LIKE '%middleware%'
        ORDER BY file, line
    """)

    # Group by file and analyze ordering
    file_middleware = {}
    for file, line, func, args in cursor.fetchall():
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

def _detect_unprotected_endpoints(cursor) -> List[StandardFinding]:
    """Detect critical endpoints without rate limiting."""
    findings = []

    # Find route definitions
    placeholders = ','.join(['?' for _ in CRITICAL_ENDPOINTS])
    cursor.execute(f"""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%post%'
               OR callee_function LIKE '%get%'
               OR callee_function LIKE '%route%')
          AND ({' OR '.join(['argument_expr LIKE ?' for _ in CRITICAL_ENDPOINTS])})
    """, [f'%{endpoint}%' for endpoint in CRITICAL_ENDPOINTS])

    for file, line, func, args in cursor.fetchall():
        # Identify which critical endpoint
        endpoint_found = None
        for endpoint in CRITICAL_ENDPOINTS:
            if endpoint in args.lower():
                endpoint_found = endpoint
                break

        if endpoint_found:
            # Check for rate limiting within ±30 lines
            query_rate_limit = build_query('function_call_args', ['callee_function', 'line'],
                where="""file = ?
                  AND (callee_function LIKE '%limit%'
                       OR callee_function LIKE '%throttle%'
                       OR argument_expr LIKE '%limit%'
                       OR argument_expr LIKE '%throttle%')"""
            )
            cursor.execute(query_rate_limit, (file,))

            # Filter in Python for ABS(line - ?) <= 30
            nearby_rate_limits = [row for row in cursor.fetchall() if abs(row[1] - line) <= 30]
            has_rate_limit = len(nearby_rate_limits) > 0

            # Also check for decorators
            if not has_rate_limit:
                query_decorators = build_query('symbols', ['name', 'line'],
                    where="""path = ?
                      AND type = 'decorator'
                      AND (name LIKE '%limit%' OR name LIKE '%throttle%')"""
                )
                cursor.execute(query_decorators, (file,))

                # Filter in Python for ABS(line - ?) <= 10
                nearby_decorators = [row for row in cursor.fetchall() if abs(row[1] - line) <= 10]
                has_rate_limit = len(nearby_decorators) > 0

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

def _detect_bypassable_keys(cursor) -> List[StandardFinding]:
    """Detect rate limiters using spoofable headers for keys."""
    findings = []

    # Find rate limiter configurations with key generation
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%RateLimit%'
               OR callee_function LIKE '%Limiter%')
          AND argument_expr IS NOT NULL
          AND (argument_expr LIKE '%keyGenerator%'
               OR argument_expr LIKE '%key_func%'
               OR argument_expr LIKE '%getKey%')
    """)

    for file, line, func, args in cursor.fetchall():
        if not args:
            continue

        args_lower = args.lower()

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
    placeholders = ','.join(['?' for _ in SPOOFABLE_HEADERS])
    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE source_expr LIKE '%headers%'
          AND ({' OR '.join(['source_expr LIKE ?' for _ in SPOOFABLE_HEADERS])})
          AND (target_var LIKE '%ip%' OR target_var LIKE '%key%' OR target_var LIKE '%client%')
    """, [f'%{h}%' for h in SPOOFABLE_HEADERS])

    for file, line, var, expr in cursor.fetchall():
        # Check if this var is used in rate limiting
        query_var_usage = build_query('function_call_args', ['callee_function'],
            where="""file = ?
              AND line > ?
              AND line <= ? + 50
              AND argument_expr LIKE ?
              AND (callee_function LIKE '%limit%' OR callee_function LIKE '%throttle%')""",
            limit=1
        )
        cursor.execute(query_var_usage, (file, line, line, f'%{var}%'))

        if cursor.fetchone() is not None:
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

def _detect_memory_storage(cursor) -> List[StandardFinding]:
    """Detect rate limiters using non-persistent storage."""
    findings = []

    # Check for memory storage patterns
    placeholders = ','.join(['?' for _ in MEMORY_STORAGE_PATTERNS])
    cursor.execute(f"""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%RateLimit%'
               OR callee_function LIKE '%Limiter%')
          AND argument_expr IS NOT NULL
          AND ({' OR '.join(['LOWER(argument_expr) LIKE ?' for _ in MEMORY_STORAGE_PATTERNS])})
    """, [f'%{pattern}%' for pattern in MEMORY_STORAGE_PATTERNS])

    for file, line, func, args in cursor.fetchall():
        # Check if persistent storage is also configured
        has_persistent = any(pattern in args.lower() for pattern in PERSISTENT_STORAGE_PATTERNS)

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
          AND (argument_expr IS NULL
               OR argument_expr NOT LIKE '%storage_uri%')
    """)

    for file, line, func, args in cursor.fetchall():
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

def _detect_expensive_operations(cursor) -> List[StandardFinding]:
    """Detect expensive operations that run before rate limiting."""
    findings = []

    # Find files with rate limiting
    cursor.execute("""
        SELECT DISTINCT file
        FROM function_call_args
        WHERE callee_function LIKE '%limit%'
           OR callee_function LIKE '%throttle%'
           OR callee_function LIKE '%RateLimit%'
    """)

    rate_limited_files = {row[0] for row in cursor.fetchall()}

    for file in rate_limited_files:
        # Get earliest rate limiter position
        cursor.execute("""
            SELECT MIN(line)
            FROM function_call_args
            WHERE file = ?
              AND (callee_function LIKE '%limit%'
                   OR callee_function LIKE '%throttle%'
                   OR callee_function LIKE '%RateLimit%')
        """, (file,))

        result = cursor.fetchone()
        if not result or not result[0]:
            continue

        rate_limit_line = result[0]

        # Find expensive operations before rate limiting
        placeholders = ','.join(['?' for _ in EXPENSIVE_OPERATIONS])
        cursor.execute(f"""
            SELECT line, callee_function, argument_expr
            FROM function_call_args
            WHERE file = ?
              AND line < ?
              AND ({' OR '.join(['callee_function LIKE ?' for _ in EXPENSIVE_OPERATIONS])})
        """, (file, rate_limit_line, *[f'%{op}%' for op in EXPENSIVE_OPERATIONS]))

        for exp_line, exp_func, exp_args in cursor.fetchall():
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

def _detect_api_rate_limits(cursor) -> List[StandardFinding]:
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
            query_limit = build_query('function_call_args', ['callee_function', 'line'],
                where="""file = ?
                  AND (callee_function LIKE '%limit%'
                       OR callee_function LIKE '%throttle%'
                       OR argument_expr LIKE '%rateLimit%')"""
            )
            cursor.execute(query_limit, (file,))

            # Filter in Python for ABS(line - ?) <= 50
            nearby_limits = [row for row in cursor.fetchall() if abs(row[1] - line) <= 50]
            has_rate_limit = len(nearby_limits) > 0

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

def _detect_decorator_ordering(cursor) -> List[StandardFinding]:
    """Detect incorrect decorator ordering in Python."""
    findings = []

    # Get all decorators
    cursor.execute("""
        SELECT path, line, name
        FROM symbols
        WHERE type = 'decorator'
          AND (name LIKE '%limit%'
               OR name LIKE '%throttle%'
               OR name LIKE '%auth%'
               OR name LIKE '%login_required%')
        ORDER BY path, line
    """)

    # Group decorators by proximity
    file_decorators = {}
    for file, line, name in cursor.fetchall():
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

def _detect_bypass_configs(cursor) -> List[StandardFinding]:
    """Detect configurations that allow rate limit bypass."""
    findings = []

    # Look for bypass-related assignments
    placeholders = ','.join(['?' for _ in BYPASS_TECHNIQUES])
    cursor.execute(f"""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE ({' OR '.join(['target_var LIKE ?' for _ in BYPASS_TECHNIQUES])})
           OR ({' OR '.join(['source_expr LIKE ?' for _ in BYPASS_TECHNIQUES])})
    """, [f'%{tech}%' for tech in BYPASS_TECHNIQUES] * 2)

    for file, line, var, expr in cursor.fetchall():
        # Check if this relates to rate limiting
        query_limit_nearby = build_query('function_call_args', ['callee_function', 'line'],
            where="""file = ?
              AND (callee_function LIKE '%limit%'
                   OR argument_expr LIKE '%rateLimit%')"""
        )
        cursor.execute(query_limit_nearby, (file,))

        # Filter in Python for ABS(line - ?) <= 30
        nearby = [row for row in cursor.fetchall() if abs(row[1] - line) <= 30]
        if len(nearby) > 0:
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

def _detect_missing_user_limits(cursor) -> List[StandardFinding]:
    """Detect rate limiters that don't consider authenticated users."""
    findings = []

    # Find rate limiter configurations
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%RateLimit%'
               OR callee_function LIKE '%Limiter%')
          AND argument_expr IS NOT NULL
    """)

    for file, line, func, args in cursor.fetchall():
        if not args:
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

def _detect_weak_rate_limits(cursor) -> List[StandardFinding]:
    """Detect rate limits with weak values (too high)."""
    findings = []

    # Find rate limit configurations with numeric values
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE (callee_function LIKE '%RateLimit%'
               OR callee_function LIKE '%limit%')
          AND argument_expr IS NOT NULL
          AND (argument_expr LIKE '%max:%'
               OR argument_expr LIKE '%limit:%'
               OR argument_expr LIKE '%requests:%')
    """)

    for file, line, func, args in cursor.fetchall():
        if not args:
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
                query_auth = build_query('function_call_args', ['argument_expr', 'line'],
                    where="""file = ?
                      AND (argument_expr LIKE '%login%'
                           OR argument_expr LIKE '%auth%'
                           OR argument_expr LIKE '%password%')"""
                )
                cursor.execute(query_auth, (file,))

                # Filter in Python for ABS(line - ?) <= 20
                nearby_auth = [row for row in cursor.fetchall() if abs(row[1] - line) <= 20]
                if len(nearby_auth) > 0:
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

def generate_rate_limit_summary(findings: List[StandardFinding]) -> Dict:
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