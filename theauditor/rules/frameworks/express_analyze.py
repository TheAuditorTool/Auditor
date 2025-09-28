"""Golden Standard Express.js Security Analyzer.

Detects Express.js security misconfigurations via database analysis.
Demonstrates database-aware rule pattern using finite pattern matching.

MIGRATION STATUS: Golden Standard Implementation [2024-12-29]
Signature: context: StandardRuleContext -> List[StandardFinding]
"""

import json
import sqlite3
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class ExpressPatterns:
    """Configuration for Express.js security patterns."""

    # User input sources that need sanitization
    USER_INPUT_SOURCES = frozenset([
        'req.body', 'req.query', 'req.params', 'req.cookies',
        'req.headers', 'req.ip', 'req.hostname', 'req.path',
        'request.body', 'request.query', 'request.params'
    ])

    # Response methods that could lead to XSS
    RESPONSE_SINKS = frozenset([
        'res.send', 'res.json', 'res.jsonp', 'res.render',
        'res.write', 'res.end', 'response.send', 'response.json'
    ])

    # Synchronous operations that block event loop
    SYNC_OPERATIONS = frozenset([
        'readFileSync', 'writeFileSync', 'appendFileSync',
        'unlinkSync', 'mkdirSync', 'rmdirSync', 'readdirSync',
        'statSync', 'lstatSync', 'existsSync', 'accessSync'
    ])

    # Database operation methods
    DB_OPERATIONS = frozenset([
        'query', 'find', 'findOne', 'findById', 'create',
        'update', 'updateOne', 'updateMany', 'delete',
        'deleteOne', 'deleteMany', 'save', 'exec',
        'insert', 'remove', 'aggregate', 'count'
    ])

    # Rate limiting libraries
    RATE_LIMIT_LIBS = frozenset([
        'express-rate-limit', 'rate-limiter-flexible', 'express-slow-down',
        'express-brute', 'rate-limiter'
    ])

    # Sanitization functions
    SANITIZATION_FUNCS = frozenset([
        'sanitize', 'escape', 'encode', 'DOMPurify',
        'xss', 'validator', 'clean', 'strip'
    ])

    # Security middleware
    SECURITY_MIDDLEWARE = frozenset([
        'helmet', 'cors', 'csurf', 'csrf',
        'express-session', 'cookie-parser'
    ])


# ============================================================================
# MAIN RULE FUNCTION (Standardized Interface)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
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


# ============================================================================
# EXPRESS ANALYZER CLASS
# ============================================================================

class ExpressAnalyzer:
    """Main analyzer for Express.js applications."""

    def __init__(self, context: StandardRuleContext):
        self.context = context
        self.patterns = ExpressPatterns()
        self.findings: List[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")

        # Track Express.js specific data
        self.express_files: List[str] = []
        self.api_endpoints: List[Dict[str, Any]] = []
        self.function_calls: List[Dict[str, Any]] = []
        self.imports: Dict[str, Set[str]] = {}

    def analyze(self) -> List[StandardFinding]:
        """Run complete Express.js analysis."""
        # Load data from database
        if not self._load_express_data():
            return self.findings  # Not an Express project

        # Run security checks (all original 7 patterns + 3 new)
        self._check_missing_helmet()
        self._check_missing_error_handler()  # Now possible with CFG data!
        self._check_sync_operations()
        self._check_xss_vulnerabilities()
        self._check_missing_rate_limiting()
        self._check_body_parser_limits()
        self._check_db_in_routes()

        # Additional security checks using available data
        self._check_cors_wildcard()
        self._check_missing_csrf()
        self._check_session_security()

        return self.findings

    def _load_express_data(self) -> bool:
        """Load Express.js related data from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if this is an Express project
            cursor.execute("""
                SELECT DISTINCT src FROM refs
                WHERE value = 'express'
            """)
            express_refs = cursor.fetchall()

            if not express_refs:
                conn.close()
                return False  # Not an Express project

            self.express_files = [ref[0] for ref in express_refs]

            # Load API endpoints
            cursor.execute("""
                SELECT file, line, method, pattern, handler_function
                FROM api_endpoints
                ORDER BY file, line
            """)
            for row in cursor.fetchall():
                self.api_endpoints.append({
                    'file': row[0],
                    'line': row[1],
                    'method': row[2],
                    'pattern': row[3],
                    'handler': row[4]
                })

            # Load imports/refs
            cursor.execute("""
                SELECT src, value FROM refs
                WHERE kind = 'import'
            """)
            for file, import_val in cursor.fetchall():
                if file not in self.imports:
                    self.imports[file] = set()
                self.imports[file].add(import_val)

            conn.close()
            return True

        except (sqlite3.Error, Exception):
            return False

    def _check_missing_error_handler(self) -> None:
        """Check for routes without error handling using CFG data."""
        if not self.api_endpoints:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check each route handler for try/catch blocks
            for endpoint in self.api_endpoints:
                # Get the handler function name (might be in handler field)
                handler = endpoint.get('handler', '')
                if not handler:
                    continue

                # Check if this function has try/catch blocks
                cursor.execute("""
                    SELECT COUNT(*) FROM cfg_blocks
                    WHERE file = ?
                      AND function_name = ?
                      AND block_type IN ('try', 'except', 'catch')
                """, (endpoint['file'], handler))

                has_error_handling = cursor.fetchone()[0] > 0

                if not has_error_handling:
                    self.findings.append(StandardFinding(
                        rule_name='express-missing-error-handler',
                        message='Express route without error handling',
                        file_path=endpoint['file'],
                        line=endpoint['line'],
                        severity=Severity.HIGH,
                        category='error-handling',
                        confidence=Confidence.MEDIUM,
                        snippet='Route handler missing try/catch',
                        fix_suggestion='Wrap route logic in try/catch or use async error middleware'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_missing_helmet(self) -> None:
        """Check for missing Helmet security middleware."""
        # Check if helmet is imported
        has_helmet = False
        for file_imports in self.imports.values():
            if 'helmet' in file_imports:
                has_helmet = True
                break

        if not has_helmet and self.express_files:
            # Check function calls for helmet usage
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT COUNT(*) FROM function_call_args
                    WHERE callee_function LIKE '%helmet%'
                       OR (callee_function = 'use' AND argument_expr LIKE '%helmet%')
                """)
                helmet_calls = cursor.fetchone()[0]
                conn.close()

                if helmet_calls == 0:
                    self.findings.append(StandardFinding(
                        rule_name='express-missing-helmet',
                        message='Express app without Helmet security middleware - missing critical security headers',
                        file_path=self.express_files[0],
                        line=1,
                        severity=Severity.HIGH,
                        category='security',
                        snippet='Missing: app.use(helmet())',
                        fix_suggestion='Install and use helmet: npm install helmet && app.use(helmet())'
                    ))

            except (sqlite3.Error, Exception):
                pass

    def _check_sync_operations(self) -> None:
        """Check for synchronous file operations in routes."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build query for sync operations
            sync_ops_list = "', '".join(self.patterns.SYNC_OPERATIONS)

            cursor.execute(f"""
                SELECT f.file, f.line, f.callee_function, f.caller_function
                FROM function_call_args f
                WHERE f.callee_function IN ('{sync_ops_list}')
                  AND EXISTS (
                      SELECT 1 FROM api_endpoints e
                      WHERE e.file = f.file
                  )
                ORDER BY f.file, f.line
            """)

            for file, line, sync_op, caller in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='express-sync-in-async',
                    message=f'Synchronous operation {sync_op} blocking event loop in route',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='performance',
                    snippet=f'{sync_op}(...) in {caller}',
                    fix_suggestion=f'Replace {sync_op} with async version: {sync_op.replace("Sync", "")}'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_xss_vulnerabilities(self) -> None:
        """Check for direct output of user input (XSS)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all response outputs
            cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function IN ('res.send', 'res.json', 'res.write', 'res.render')
                ORDER BY file, line
            """)

            for file, line, method, arg_expr in cursor.fetchall():
                # Check if argument contains user input
                has_user_input = False
                input_source = None

                for source in self.patterns.USER_INPUT_SOURCES:
                    if source in arg_expr:
                        has_user_input = True
                        input_source = source
                        break

                if has_user_input:
                    # Check for sanitization nearby
                    cursor.execute("""
                        SELECT COUNT(*) FROM function_call_args
                        WHERE file = ? AND line BETWEEN ? AND ?
                          AND callee_function IN ('sanitize', 'escape', 'encode', 'DOMPurify', 'xss')
                    """, (file, line - 5, line + 5))

                    has_sanitization = cursor.fetchone()[0] > 0

                    if not has_sanitization:
                        self.findings.append(StandardFinding(
                            rule_name='express-xss-direct-send',
                            message=f'Potential XSS - {input_source} directly in response without sanitization',
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category='xss',
                            snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                            fix_suggestion=f'Sanitize {input_source} before sending'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_missing_rate_limiting(self) -> None:
        """Check for missing rate limiting on API endpoints."""
        # Check if we have API endpoints
        api_routes = [ep for ep in self.api_endpoints if '/api' in ep['pattern']]

        if not api_routes:
            return

        # Check for rate limiting libraries
        has_rate_limit = False
        for file_imports in self.imports.values():
            if any(lib in file_imports for lib in self.patterns.RATE_LIMIT_LIBS):
                has_rate_limit = True
                break

        if not has_rate_limit:
            self.findings.append(StandardFinding(
                rule_name='express-missing-rate-limit',
                message='API endpoints without rate limiting - vulnerable to DoS/brute force',
                file_path=api_routes[0]['file'],
                line=api_routes[0]['line'],
                severity=Severity.HIGH,
                category='security',
                snippet='Add express-rate-limit middleware',
                fix_suggestion='Install express-rate-limit: npm install express-rate-limit'
            ))

    def _check_body_parser_limits(self) -> None:
        """Check for body parser without size limit."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, line, argument_expr
                FROM function_call_args
                WHERE (callee_function LIKE '%bodyParser%'
                       OR callee_function = 'json'
                       OR callee_function = 'urlencoded')
                ORDER BY file, line
            """)

            for file, line, config in cursor.fetchall():
                # Check if limit is specified
                if 'limit' not in config:
                    self.findings.append(StandardFinding(
                        rule_name='express-body-parser-limit',
                        message='Body parser without size limit - vulnerable to DoS',
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category='security',
                        snippet='Add limit option to bodyParser',
                        fix_suggestion="Add size limit: bodyParser.json({ limit: '10mb' })"
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_db_in_routes(self) -> None:
        """Check for database queries directly in route handlers."""
        if not self.api_endpoints:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all DB operations in files with routes
            route_files = set(ep['file'] for ep in self.api_endpoints)

            for route_file in route_files:
                cursor.execute("""
                    SELECT line, callee_function
                    FROM function_call_args
                    WHERE file = ?
                      AND callee_function IN ('query', 'find', 'findOne', 'findById', 'create',
                                              'update', 'updateOne', 'updateMany', 'delete',
                                              'deleteOne', 'deleteMany', 'save', 'exec')
                      AND caller_function NOT LIKE '%service%'
                      AND caller_function NOT LIKE '%repository%'
                      AND caller_function NOT LIKE '%model%'
                    ORDER BY line
                """, (route_file,))

                for line, db_method in cursor.fetchall():
                    self.findings.append(StandardFinding(
                        rule_name='express-direct-db-query',
                        message=f'Database {db_method} directly in route handler - consider using service layer',
                        file_path=route_file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category='architecture',
                        snippet=f'Move {db_method} to service/repository layer',
                        fix_suggestion='Separate concerns: use service/repository pattern'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_cors_wildcard(self) -> None:
        """Check for CORS wildcard configuration."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check for CORS wildcard in function calls
            cursor.execute("""
                SELECT file, line, argument_expr
                FROM function_call_args
                WHERE callee_function = 'cors'
                  AND (argument_expr LIKE '%origin:%*%'
                       OR argument_expr LIKE '%origin:%true%'
                       OR argument_expr = '')
                ORDER BY file, line
            """)

            for file, line, config in cursor.fetchall():
                if '*' in config or 'true' in config or config == '':
                    self.findings.append(StandardFinding(
                        rule_name='express-cors-wildcard',
                        message='CORS configured with wildcard origin - allows any domain',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='security',
                        snippet='CORS with origin: * or origin: true',
                        fix_suggestion='Specify allowed origins explicitly instead of wildcard'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_missing_csrf(self) -> None:
        """Check for missing CSRF protection."""
        # Check if we have POST/PUT/DELETE endpoints
        modifying_endpoints = [
            ep for ep in self.api_endpoints
            if ep.get('method', '').upper() in ['POST', 'PUT', 'DELETE', 'PATCH']
        ]

        if not modifying_endpoints:
            return

        # Check for CSRF middleware
        has_csrf = False
        for file_imports in self.imports.values():
            if 'csurf' in file_imports or 'csrf' in file_imports:
                has_csrf = True
                break

        if not has_csrf:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                # Check for CSRF in function calls
                cursor.execute("""
                    SELECT COUNT(*) FROM function_call_args
                    WHERE callee_function IN ('csurf', 'csrf')
                       OR (callee_function = 'use' AND argument_expr LIKE '%csrf%')
                """)
                csrf_calls = cursor.fetchone()[0]
                conn.close()

                if csrf_calls == 0:
                    self.findings.append(StandardFinding(
                        rule_name='express-missing-csrf',
                        message='State-changing endpoints without CSRF protection',
                        file_path=modifying_endpoints[0]['file'],
                        line=modifying_endpoints[0]['line'],
                        severity=Severity.HIGH,
                        category='csrf',
                        snippet='POST/PUT/DELETE endpoints need CSRF tokens',
                        fix_suggestion='Add csurf middleware: npm install csurf && app.use(csrf())'
                    ))

            except (sqlite3.Error, Exception):
                pass

    def _check_session_security(self) -> None:
        """Check for insecure session configuration."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check for express-session configuration
            cursor.execute("""
                SELECT file, line, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE '%session%'
                   OR (callee_function = 'use' AND argument_expr LIKE '%session%')
                ORDER BY file, line
            """)

            for file, line, config in cursor.fetchall():
                config_lower = config.lower()

                # Check for weak session configuration
                issues = []
                if 'secret' in config_lower:
                    if any(weak in config_lower for weak in ['secret', 'keyboard cat', 'default']):
                        issues.append('weak secret')

                if 'cookie' in config_lower:
                    if 'httponly' not in config_lower:
                        issues.append('missing httpOnly')
                    if 'secure' not in config_lower:
                        issues.append('missing secure flag')
                    if 'samesite' not in config_lower:
                        issues.append('missing sameSite')

                if issues:
                    self.findings.append(StandardFinding(
                        rule_name='express-session-insecure',
                        message=f'Insecure session configuration: {", ".join(issues)}',
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category='security',
                        snippet='Session configuration issues',
                        fix_suggestion='Use secure session config: httpOnly, secure, sameSite, strong secret'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass