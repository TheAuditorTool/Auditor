"""SQL-based rate limiting misconfiguration detector.

This module provides detection of dangerous rate limiting configurations
by querying the indexed database instead of traversing AST structures.
"""

import sqlite3
from typing import List, Set
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_rate_limit_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """
    Detect rate limiting misconfigurations using SQL queries.
    
    This function queries the indexed database to find:
    - Inefficient middleware order (expensive operations before rate limiting)
    - Missing rate limiting on critical endpoints
    - Bypassable key generation (single header like X-Forwarded-For)
    - Non-persistent storage (in-memory store)
    
    Args:
        context: StandardRuleContext with database path
        
    Returns:
        List of StandardFinding objects
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    try:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()
        
        # Pattern 1: Rate limiting after authentication middleware
        findings.extend(_find_middleware_ordering_issues(cursor))
        
        # Pattern 2: Missing rate limiting on critical endpoints
        findings.extend(_find_unprotected_critical_endpoints(cursor))
        
        # Pattern 3: Bypassable key generation
        findings.extend(_find_bypassable_key_generation(cursor))
        
        # Pattern 4: In-memory storage in production
        findings.extend(_find_memory_storage_issues(cursor))
        
        # Pattern 5: Rate limiting after expensive operations
        findings.extend(_find_expensive_operations_before_rate_limit(cursor))
        
        conn.close()
        
    except Exception:
        pass  # Return empty findings on error
    
    return findings


def _find_middleware_ordering_issues(cursor) -> List[StandardFinding]:
    """Find cases where auth middleware runs before rate limiting."""
    findings = []
    
    # Common authentication middleware patterns
    auth_patterns = [
        'authenticate', 'auth', 'requireAuth', 'isAuthenticated',
        'passport.authenticate', 'jwt.verify', 'verifyToken',
        'ensureAuthenticated', 'requireLogin', 'checkAuth',
        'login_required', '@auth', '@authenticated'
    ]
    
    # Rate limiting patterns
    rate_limit_patterns = [
        'express-rate-limit', 'rateLimit', 'RateLimit', 'rate-limit',
        'express-slow-down', 'slowDown', 'SlowDown',
        'express-brute', 'ExpressBrute', 'limiter',
        'rate-limiter-flexible', 'RateLimiterMemory', 'RateLimiterRedis',
        '@limit', '@ratelimit', '@throttle', 'Limiter'
    ]
    
    # Find middleware registration calls (app.use, router.use)
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%app.use%' 
               OR f.callee_function LIKE '%router.use%'
               OR f.callee_function LIKE '%app.middleware%')
        ORDER BY f.file, f.line
    """)
    
    middleware_registrations = cursor.fetchall()
    
    # Group by file and check ordering
    file_middleware = {}
    for file, line, func, args in middleware_registrations:
        if file not in file_middleware:
            file_middleware[file] = []
        
        # Determine middleware type
        middleware_type = None
        if args:
            args_lower = args.lower() if args else ""
            
            # Check if it's rate limiting
            if any(pattern.lower() in args_lower for pattern in rate_limit_patterns):
                middleware_type = 'rate_limit'
            # Check if it's authentication
            elif any(pattern.lower() in args_lower for pattern in auth_patterns):
                middleware_type = 'auth'
            # Check if it's expensive operation
            elif any(pattern in args_lower for pattern in ['database', 'query', 'bcrypt', 'hash', 'crypto']):
                middleware_type = 'expensive'
        
        if middleware_type:
            file_middleware[file].append({
                'line': line,
                'type': middleware_type,
                'func': func,
                'args': args[:200] if args else ''
            })
    
    # Check ordering in each file
    for file, middlewares in file_middleware.items():
        rate_limit_line = -1
        auth_lines = []
        expensive_lines = []
        
        for mw in middlewares:
            if mw['type'] == 'rate_limit':
                rate_limit_line = mw['line']
            elif mw['type'] == 'auth':
                auth_lines.append(mw['line'])
            elif mw['type'] == 'expensive':
                expensive_lines.append(mw['line'])
        
        # Check if auth comes before rate limiting
        if rate_limit_line > 0:
            for auth_line in auth_lines:
                if auth_line < rate_limit_line:
                    findings.append(StandardFinding(
                        rule_name='rate-limit-after-auth',
                        message='Authentication middleware runs before rate limiting - expensive operation not protected',
                        file_path=file,
                        line=auth_line,
                        severity=Severity.HIGH,
                        category='security',
                        snippet='app.use(authenticate) // before rate limiting',
                        fix_suggestion='Move rate limiting middleware before authentication',
                        cwe_id='CWE-770'
                    ))
    
    # Also check for decorators in Python
    cursor.execute("""
        SELECT s.file, s.line, s.name, s.symbol_type
        FROM symbols s
        WHERE s.symbol_type = 'decorator'
          AND (s.name LIKE '%limit%' 
               OR s.name LIKE '%throttle%' 
               OR s.name LIKE '%ratelimit%'
               OR s.name LIKE '%auth%'
               OR s.name LIKE '%login_required%')
        ORDER BY s.file, s.line
    """)
    
    python_decorators = cursor.fetchall()
    
    # Group Python decorators by function
    file_decorators = {}
    for file, line, name, _ in python_decorators:
        if file not in file_decorators:
            file_decorators[file] = []
        
        decorator_type = None
        name_lower = name.lower()
        if any(pattern in name_lower for pattern in ['limit', 'throttle', 'ratelimit']):
            decorator_type = 'rate_limit'
        elif any(pattern in name_lower for pattern in ['auth', 'login_required']):
            decorator_type = 'auth'
        
        if decorator_type:
            file_decorators[file].append({
                'line': line,
                'type': decorator_type,
                'name': name
            })
    
    # Check decorator ordering
    for file, decorators in file_decorators.items():
        # Group decorators by proximity (within 5 lines = same function)
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
        
        # Check ordering within each function
        for group in function_groups:
            rate_limit_line = -1
            auth_line = -1
            
            for dec in group:
                if dec['type'] == 'rate_limit':
                    rate_limit_line = dec['line']
                elif dec['type'] == 'auth':
                    auth_line = dec['line']
            
            if rate_limit_line > 0 and auth_line > 0 and auth_line < rate_limit_line:
                findings.append(StandardFinding(
                    rule_name='rate-limit-after-auth',
                    message='Authentication decorator runs before rate limiting decorator',
                    file_path=file,
                    line=auth_line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet='@login_required // before @rate_limit',
                    fix_suggestion='Place rate limiting decorator before authentication decorator',
                    cwe_id='CWE-770'
                ))
    
    return findings


def _find_unprotected_critical_endpoints(cursor) -> List[StandardFinding]:
    """Find critical endpoints without rate limiting protection."""
    findings = []
    
    # Critical endpoint patterns
    critical_endpoints = [
        '/login', '/signin', '/auth',
        '/register', '/signup', '/create-account',
        '/reset-password', '/forgot-password', '/password-reset',
        '/verify', '/confirm', '/validate',
        '/api/auth', '/api/login', '/api/register',
        '/token', '/oauth', '/2fa'
    ]
    
    # Rate limiting indicators
    rate_limit_indicators = [
        'rateLimit', 'rate-limit', 'limiter', 'throttle',
        'express-rate-limit', 'express-slow-down', 'express-brute',
        '@limit', '@ratelimit', '@throttle'
    ]
    
    # Find route definitions
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%app.post%' 
               OR f.callee_function LIKE '%app.get%'
               OR f.callee_function LIKE '%router.post%'
               OR f.callee_function LIKE '%router.get%'
               OR f.callee_function LIKE '%app.route%'
               OR f.callee_function LIKE '%@route%')
    """)
    
    routes = cursor.fetchall()
    
    for file, line, func, args in routes:
        if not args:
            continue
            
        # Check if this is a critical endpoint
        route_path = None
        args_lower = args.lower()
        
        for endpoint in critical_endpoints:
            if endpoint in args_lower:
                route_path = endpoint
                break
        
        if route_path:
            # Check if rate limiting is applied (look for rate limit within ±20 lines)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM function_call_args f2
                WHERE f2.file = ?
                  AND f2.line BETWEEN ? AND ?
                  AND ({})
            """.format(' OR '.join([f"f2.argument_expr LIKE '%{pattern}%'" for pattern in rate_limit_indicators])),
            (file, line - 20, line + 20))
            
            has_rate_limit = cursor.fetchone()[0] > 0
            
            # Also check for rate limiting decorators nearby
            if not has_rate_limit:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM symbols s
                    WHERE s.file = ?
                      AND s.line BETWEEN ? AND ?
                      AND s.symbol_type = 'decorator'
                      AND (s.name LIKE '%limit%' OR s.name LIKE '%throttle%' OR s.name LIKE '%ratelimit%')
                """, (file, line - 10, line + 10))
                
                has_rate_limit = cursor.fetchone()[0] > 0
            
            if not has_rate_limit:
                findings.append(StandardFinding(
                    rule_name='missing-rate-limit-critical',
                    message=f'Critical endpoint {route_path} lacks rate limiting protection',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    snippet=f'{func}("{route_path}", ...)',
                    fix_suggestion='Apply rate limiting middleware or decorator',
                    cwe_id='CWE-307'
                ))
    
    return findings


def _find_bypassable_key_generation(cursor) -> List[StandardFinding]:
    """Find rate limiters using single spoofable headers for key generation."""
    findings = []
    
    # Spoofable headers
    spoofable_headers = [
        'x-forwarded-for', 'x-real-ip', 'cf-connecting-ip',
        'x-client-ip', 'x-originating-ip', 'x-remote-ip'
    ]
    
    # Find rate limiter configurations
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%RateLimit%' 
               OR f.callee_function LIKE '%Limiter%'
               OR f.callee_function LIKE '%rateLimit%'
               OR f.callee_function LIKE '%express-rate-limit%')
          AND (f.argument_expr LIKE '%keyGenerator%' 
               OR f.argument_expr LIKE '%key_func%'
               OR f.argument_expr LIKE '%getKey%')
    """)
    
    configs = cursor.fetchall()
    
    for file, line, func, args in configs:
        if not args:
            continue
            
        args_lower = args.lower()
        
        # Check if using single spoofable header
        uses_spoofable = any(header in args_lower for header in spoofable_headers)
        
        if uses_spoofable:
            # Check if there's a fallback (|| or ??)
            has_fallback = '||' in args or '??' in args or 'req.ip' in args_lower
            
            if not has_fallback:
                findings.append(StandardFinding(
                    rule_name='rate-limit-bypassable-key',
                    message='Rate limiter relies on spoofable header for key generation',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    snippet='keyGenerator: req.headers["x-forwarded-for"]',
                    fix_suggestion='Use multiple sources with fallback: req.headers["x-forwarded-for"] || req.ip',
                    cwe_id='CWE-290'
                ))
    
    # Also check for simple header access patterns
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.source_expr LIKE '%headers[%'
          AND ({})
          AND (a.target_var LIKE '%key%' OR a.target_var LIKE '%ip%' OR a.target_var LIKE '%client%')
    """.format(' OR '.join([f"a.source_expr LIKE '%{h}%'" for h in spoofable_headers])))
    
    header_assignments = cursor.fetchall()
    
    for file, line, var, expr in header_assignments:
        # Check if this variable is used in rate limiting context
        cursor.execute("""
            SELECT COUNT(*)
            FROM function_call_args f
            WHERE f.file = ?
              AND f.line BETWEEN ? AND ?
              AND f.argument_expr LIKE ?
              AND (f.callee_function LIKE '%limit%' OR f.callee_function LIKE '%throttle%')
        """, (file, line, line + 20, f'%{var}%'))
        
        if cursor.fetchone()[0] > 0:
            findings.append(StandardFinding(
                rule_name='rate-limit-bypassable-key',
                message='Rate limiting key derived from spoofable header',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=f'{var} = {expr}',
                fix_suggestion='Combine with req.ip for robust key generation',
                cwe_id='CWE-290'
            ))
    
    return findings


def _find_memory_storage_issues(cursor) -> List[StandardFinding]:
    """Find rate limiters using in-memory storage in production."""
    findings = []
    
    # Memory storage patterns
    memory_patterns = [
        'MemoryStore', 'memory', 'InMemory', 'LocalStore',
        'RateLimiterMemory', 'new Memory', 'store: memory'
    ]
    
    # Find rate limiter storage configurations
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE (f.callee_function LIKE '%RateLimit%' 
               OR f.callee_function LIKE '%Limiter%'
               OR f.callee_function LIKE '%rateLimit%'
               OR f.callee_function LIKE '%express-rate-limit%')
          AND (f.argument_expr LIKE '%store%' OR f.argument_expr LIKE '%storage%')
    """)
    
    configs = cursor.fetchall()
    
    for file, line, func, args in configs:
        if not args:
            continue
            
        # Check for memory storage patterns
        if any(pattern.lower() in args.lower() for pattern in memory_patterns):
            findings.append(StandardFinding(
                rule_name='rate-limit-memory-store',
                message='Rate limiter using in-memory storage - ineffective in distributed/serverless environment',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet='store: new MemoryStore()',
                fix_suggestion='Use Redis, MongoDB, or other persistent storage',
                cwe_id='CWE-770'
            ))
    
    # Check Flask-Limiter configurations
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function = 'Limiter'
          AND (f.argument_expr IS NULL 
               OR f.argument_expr NOT LIKE '%storage_uri%'
               OR f.argument_expr LIKE '%memory%')
    """)
    
    flask_configs = cursor.fetchall()
    
    for file, line, func, args in flask_configs:
        # No storage_uri or explicit memory means default memory storage
        findings.append(StandardFinding(
            rule_name='rate-limit-memory-store',
            message='Flask-Limiter using default in-memory storage - ineffective in production',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet='Limiter(app)',
            fix_suggestion='Use Redis backend: storage_uri="redis://localhost:6379"',
            cwe_id='CWE-770'
        ))
    
    return findings


def _find_expensive_operations_before_rate_limit(cursor) -> List[StandardFinding]:
    """Find expensive operations that run before rate limiting."""
    findings = []
    
    # Expensive operation patterns
    expensive_operations = [
        'bcrypt', 'scrypt', 'argon2', 'pbkdf2', 'hash', 'compare',
        'crypto.scrypt', 'crypto.pbkdf2',
        'database', 'query', 'findOne', 'findAll', 'select', 'execute',
        'sendEmail', 'sendMail', 'mailer.send',
        'fetch', 'axios', 'request', 'http.get'
    ]
    
    # Find files with rate limiting
    cursor.execute("""
        SELECT DISTINCT f.file
        FROM function_call_args f
        WHERE f.callee_function LIKE '%limit%' 
           OR f.callee_function LIKE '%throttle%'
           OR f.callee_function LIKE '%RateLimit%'
    """)
    
    rate_limited_files = {row[0] for row in cursor.fetchall()}
    
    for file in rate_limited_files:
        # Get rate limiter positions
        cursor.execute("""
            SELECT MIN(f.line)
            FROM function_call_args f
            WHERE f.file = ?
              AND (f.callee_function LIKE '%limit%' 
                   OR f.callee_function LIKE '%throttle%'
                   OR f.callee_function LIKE '%RateLimit%')
        """, (file,))
        
        rate_limit_line = cursor.fetchone()[0]
        
        if rate_limit_line:
            # Find expensive operations before rate limiting
            cursor.execute("""
                SELECT f.line, f.callee_function, f.argument_expr
                FROM function_call_args f
                WHERE f.file = ?
                  AND f.line < ?
                  AND ({})
            """.format(' OR '.join([f"f.callee_function LIKE '%{op}%'" for op in expensive_operations])),
            (file, rate_limit_line))
            
            expensive_before = cursor.fetchall()
            
            for exp_line, exp_func, exp_args in expensive_before:
                # Check if this is in middleware context (app.use nearby)
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM function_call_args f2
                    WHERE f2.file = ?
                      AND f2.line BETWEEN ? AND ?
                      AND (f2.callee_function LIKE '%app.use%' OR f2.callee_function LIKE '%router.use%')
                """, (file, exp_line - 10, exp_line + 10))
                
                if cursor.fetchone()[0] > 0:
                    findings.append(StandardFinding(
                        rule_name='rate-limit-after-expensive',
                        message=f'Expensive operation ({exp_func}) runs before rate limiting',
                        file_path=file,
                        line=exp_line,
                        severity=Severity.HIGH,
                        category='security',
                        snippet=f'{exp_func}(...)',
                        fix_suggestion='Move rate limiting middleware earlier in the stack',
                        cwe_id='CWE-770'
                    ))
    
    return findings


