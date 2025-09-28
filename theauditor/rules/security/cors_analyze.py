"""CORS Security Analyzer - Golden Standard Implementation.

Detects comprehensive CORS vulnerabilities using database-driven approach.
Follows golden standard patterns with frozensets, proper confidence levels,
and table existence checks.

Detects 15+ real-world CORS vulnerabilities:
- Classic wildcard with credentials
- Subdomain wildcard takeover risks
- Null origin bypass
- Origin reflection without validation
- Regex escape failures
- Protocol downgrade attacks
- Port confusion vulnerabilities
- Case sensitivity bypasses
- Cache poisoning via missing Vary header
- Excessive preflight cache
- WebSocket CORS bypass
- Dynamic validation flaws
- Framework-specific misconfigurations
"""

import sqlite3
import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence


# ============================================================================
# GOLDEN STANDARD: FROZEN DATACLASS FOR PATTERNS
# ============================================================================

@dataclass(frozen=True)
class CORSPatterns:
    """Immutable CORS detection patterns following golden standard."""

    # Framework CORS functions
    CORS_FUNCTIONS = frozenset([
        'cors', 'CORS', 'Cors',
        'enableCors', 'setCors', 'configureCors',
        'express-cors', '@koa/cors', 'fastify-cors',
        'cors.init', 'cors.create', 'corsMiddleware'
    ])

    # Header setting functions
    HEADER_FUNCTIONS = frozenset([
        'setHeader', 'set', 'header', 'writeHead',
        'res.setHeader', 'res.set', 'res.header',
        'response.setHeader', 'response.set',
        'reply.header', 'ctx.set', 'headers.set'
    ])

    # CORS headers to track
    CORS_HEADERS = frozenset([
        'Access-Control-Allow-Origin',
        'Access-Control-Allow-Credentials',
        'Access-Control-Allow-Methods',
        'Access-Control-Allow-Headers',
        'Access-Control-Expose-Headers',
        'Access-Control-Max-Age',
        'Access-Control-Request-Method',
        'Access-Control-Request-Headers',
        'Vary'
    ])

    # Dangerous origin patterns
    DANGEROUS_ORIGINS = frozenset([
        '*',
        'null',
        'file://',
        'http://localhost',
        'http://127.0.0.1',
        'http://0.0.0.0',
        'true'  # Some frameworks use boolean true as wildcard
    ])

    # Regex vulnerability indicators
    REGEX_INDICATORS = frozenset([
        'RegExp', 'regexp', 'regex',
        '/^', '^http', '.test(', '.match(',
        'new RegExp', 'pattern:', '/$/'
    ])

    # Dynamic origin indicators
    DYNAMIC_INDICATORS = frozenset([
        'function', 'callback', '=>',
        'req.headers.origin', 'req.header',
        'request.headers', 'origin ||',
        'getOrigin', 'checkOrigin', 'validateOrigin'
    ])

    # WebSocket event handlers
    WEBSOCKET_HANDLERS = frozenset([
        'io.on', 'socket.on', 'ws.on',
        'connection', 'connect', 'upgrade',
        'WebSocket', 'SocketIO', 'ws://', 'wss://'
    ])

    # Framework identifiers
    FRAMEWORKS = frozenset([
        'express', 'fastify', 'koa', 'hapi',
        'restify', 'nestjs', 'next', 'nuxt',
        'django', 'flask', 'fastapi'
    ])

    # Common CORS variable names
    CORS_VAR_NAMES = frozenset([
        'corsOptions', 'corsConfig', 'cors_options',
        'corsSettings', 'corsPolicy', 'corsRules',
        'allowedOrigins', 'whitelist', 'origins'
    ])


# ============================================================================
# MAIN CORS ANALYZER CLASS
# ============================================================================

class CORSAnalyzer:
    """Comprehensive CORS vulnerability detection following golden standard."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with context and patterns.

        Args:
            context: Standard rule context with database path
        """
        self.context = context
        self.patterns = CORSPatterns()
        self.findings = []
        self.existing_tables = set()

    def analyze(self) -> List[StandardFinding]:
        """Main entry point - runs all CORS vulnerability checks.

        Returns:
            List of CORS vulnerability findings
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Check table availability (golden standard requirement)
            self._check_table_availability()

            # Must have minimum tables for analysis
            if not self._has_minimum_tables():
                return []

            # Run all vulnerability checks
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

        finally:
            conn.close()

        return self.findings

    def _check_table_availability(self):
        """Check which tables exist for graceful degradation."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'function_call_args', 'assignments', 'symbols',
                'api_endpoints', 'config_files', 'files'
            )
        """)
        self.existing_tables = {row[0] for row in self.cursor.fetchall()}

    def _has_minimum_tables(self) -> bool:
        """Check if we have minimum required tables."""
        required = {'function_call_args', 'assignments'}
        return required.issubset(self.existing_tables)

    # ========================================================================
    # CHECK 1: Classic Wildcard with Credentials
    # ========================================================================

    def _check_wildcard_with_credentials(self):
        """Detect wildcard origin with credentials enabled."""
        if 'function_call_args' not in self.existing_tables:
            return

        # Check CORS function calls
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """.format(','.join(['?'] * len(self.patterns.CORS_FUNCTIONS))),
        list(self.patterns.CORS_FUNCTIONS))

        for file, line, func, args in self.cursor.fetchall():
            if not args:
                continue

            # Check for wildcard and credentials
            has_wildcard = any(origin in args for origin in ['*', '"*"', "'*'", 'true'])
            has_credentials = 'credentials' in args.lower() and 'true' in args.lower()

            if has_wildcard and has_credentials:
                self.findings.append(StandardFinding(
                    rule_name='cors-wildcard-credentials',
                    message='CORS wildcard origin with credentials enabled - any site can read authenticated data',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category='security',
                    snippet=f'{func}(origin: "*", credentials: true)',
                    fix_suggestion='Never use wildcard origin with credentials. Use explicit origin whitelist.',
                    cwe_id='CWE-942'  # Permissive Cross-domain Policy
                ))

    # ========================================================================
    # CHECK 2: Subdomain Wildcards
    # ========================================================================

    def _check_subdomain_wildcards(self):
        """Detect subdomain wildcard patterns that enable takeover attacks."""
        if 'assignments' not in self.existing_tables:
            return

        # Look for origin patterns with subdomain wildcards
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (target_var LIKE '%origin%' OR target_var LIKE '%cors%')
              AND (source_expr LIKE '%*.%' OR source_expr LIKE '%/.*\.%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check for subdomain wildcard patterns
            subdomain_patterns = [
                r'\*\.',  # *.example.com
                r'/\.\*\\?\.',  # Regex: /.*\.example\.com/
                r'/\^https?:\/\/\.\*\\?\.',  # Full regex pattern
            ]

            for pattern in subdomain_patterns:
                if re.search(pattern, expr):
                    self.findings.append(StandardFinding(
                        rule_name='cors-subdomain-wildcard',
                        message='Subdomain wildcard in CORS origin - vulnerable to subdomain takeover',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.HIGH,
                        category='security',
                        snippet=f'{var} = {expr[:100]}',
                        fix_suggestion='List specific subdomains instead of using wildcards. Monitor for subdomain takeovers.',
                        cwe_id='CWE-942'
                    ))
                    break

    # ========================================================================
    # CHECK 3: Null Origin Handling
    # ========================================================================

    def _check_null_origin_handling(self):
        """Detect allowing 'null' origin which enables sandbox attacks."""
        queries = [
            # Check in function arguments
            ("function_call_args", """
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE argument_expr LIKE '%null%'
                  AND (argument_expr LIKE '%origin%' OR callee_function IN ({}))
            """.format(','.join(['?'] * len(self.patterns.CORS_FUNCTIONS)))),

            # Check in assignments
            ("assignments", """
                SELECT file, line, target_var, source_expr
                FROM assignments
                WHERE (target_var LIKE '%origin%' OR target_var LIKE '%whitelist%')
                  AND source_expr LIKE '%null%'
            """)
        ]

        for table, query in queries:
            if table not in self.existing_tables:
                continue

            if table == "function_call_args":
                self.cursor.execute(query, list(self.patterns.CORS_FUNCTIONS))
            else:
                self.cursor.execute(query)

            for row in self.cursor.fetchall():
                file, line = row[0], row[1]
                context = row[2] if len(row) > 2 else ""

                # Check if null is being explicitly allowed
                if 'null' in str(row).lower():
                    self.findings.append(StandardFinding(
                        rule_name='cors-null-origin',
                        message='CORS allows "null" origin - enables attacks from sandboxed contexts',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.HIGH,
                        category='security',
                        snippet='origin: [..., "null", ...]',
                        fix_suggestion='Never allow "null" origin. It can be exploited via data: URIs and sandboxed iframes.',
                        cwe_id='CWE-346'  # Origin Validation Error
                    ))

    # ========================================================================
    # CHECK 4: Origin Reflection Without Validation
    # ========================================================================

    def _check_origin_reflection(self):
        """Detect reflecting origin header without validation."""
        if 'assignments' not in self.existing_tables:
            return

        # Find origin reflections
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (source_expr LIKE '%req.headers.origin%'
                   OR source_expr LIKE '%req.header%origin%'
                   OR source_expr LIKE '%request.headers.origin%'
                   OR source_expr LIKE '%request.headers[%origin%]%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if there's validation nearby
            self.cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND ABS(line - ?) <= 10
                  AND (callee_function LIKE '%includes%'
                       OR callee_function LIKE '%indexOf%'
                       OR callee_function LIKE '%test%'
                       OR callee_function LIKE '%match%'
                       OR argument_expr LIKE '%whitelist%'
                       OR argument_expr LIKE '%allowed%')
            """, (file, line))

            validation_count = self.cursor.fetchone()[0]

            if validation_count == 0:
                self.findings.append(StandardFinding(
                    rule_name='cors-origin-reflection',
                    message='Origin header reflected without validation - attacker can bypass CORS',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category='security',
                    snippet=f'{var} = {expr}',
                    fix_suggestion='Always validate origin against whitelist before reflecting. Never trust user input.',
                    cwe_id='CWE-346'
                ))

    # ========================================================================
    # CHECK 5: Regex Vulnerabilities
    # ========================================================================

    def _check_regex_vulnerabilities(self):
        """Detect vulnerable regex patterns in CORS origin validation."""
        if 'assignments' not in self.existing_tables:
            return

        # Find regex patterns used for origin validation
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (target_var LIKE '%origin%' OR target_var LIKE '%cors%')
              AND (source_expr LIKE '%RegExp%' OR source_expr LIKE '%/^%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            vulnerabilities = []

            # Check for unescaped dots
            if re.search(r'/[^\\]\.[^*+]/', expr):
                vulnerabilities.append('unescaped dots')

            # Check for missing anchors
            if 'RegExp' in expr and not ('^' in expr or '$' in expr):
                vulnerabilities.append('missing anchors')

            # Check for case sensitivity
            if 'RegExp' in expr and '/i' not in expr and 'ignoreCase' not in expr:
                vulnerabilities.append('case sensitive')

            if vulnerabilities:
                self.findings.append(StandardFinding(
                    rule_name='cors-regex-vulnerability',
                    message=f'Vulnerable regex pattern: {", ".join(vulnerabilities)}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    snippet=f'{var} = {expr[:100]}',
                    fix_suggestion='Escape dots, use anchors (^ and $), consider case-insensitive matching.',
                    cwe_id='CWE-185'  # Incorrect Regular Expression
                ))

    # ========================================================================
    # CHECK 6: Protocol Downgrade
    # ========================================================================

    def _check_protocol_downgrade(self):
        """Detect allowing HTTP origins when HTTPS should be required."""
        tables_queries = [
            ("assignments", """
                SELECT file, line, target_var, source_expr
                FROM assignments
                WHERE (target_var LIKE '%origin%' OR target_var LIKE '%cors%')
                  AND source_expr LIKE '%http://%'
                  AND source_expr NOT LIKE '%https://%'
            """),
            ("function_call_args", """
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function IN ({})
                  AND argument_expr LIKE '%http://%'
                  AND argument_expr NOT LIKE '%localhost%'
                  AND argument_expr NOT LIKE '%127.0.0.1%'
            """.format(','.join(['?'] * len(self.patterns.CORS_FUNCTIONS))))
        ]

        for table, query in tables_queries:
            if table not in self.existing_tables:
                continue

            if table == "function_call_args":
                self.cursor.execute(query, list(self.patterns.CORS_FUNCTIONS))
            else:
                self.cursor.execute(query)

            for row in self.cursor.fetchall():
                file, line = row[0], row[1]
                self.findings.append(StandardFinding(
                    rule_name='cors-protocol-downgrade',
                    message='HTTP origin allowed - vulnerable to protocol downgrade attacks',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    category='security',
                    snippet='origin: "http://..."',
                    fix_suggestion='Use HTTPS origins only. HTTP is vulnerable to MITM attacks.',
                    cwe_id='CWE-757'  # Selection of Less-Secure Algorithm
                ))

    # ========================================================================
    # CHECK 7: Port Confusion
    # ========================================================================

    def _check_port_confusion(self):
        """Detect port handling issues in CORS origin validation."""
        if 'assignments' not in self.existing_tables:
            return

        # Look for port-specific origin configurations
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (target_var LIKE '%origin%' OR target_var LIKE '%cors%')
              AND source_expr LIKE '%:%'
              AND source_expr NOT LIKE '%:80%'
              AND source_expr NOT LIKE '%:443%'
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if multiple ports or non-standard ports
            port_matches = re.findall(r':(\d+)', expr)
            if port_matches and len(set(port_matches)) > 1:
                self.findings.append(StandardFinding(
                    rule_name='cors-port-confusion',
                    message='Multiple or non-standard ports in CORS config - potential security risk',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    snippet=f'{var} = {expr[:100]}',
                    fix_suggestion='Be explicit about allowed ports. Different ports are different origins.',
                    cwe_id='CWE-942'
                ))

    # ========================================================================
    # CHECK 8: Case Sensitivity Issues
    # ========================================================================

    def _check_case_sensitivity(self):
        """Detect case-sensitive origin comparisons that can be bypassed."""
        if 'function_call_args' not in self.existing_tables:
            return

        # Look for string comparisons without case normalization
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE (callee_function IN ('===', '==', 'equals', 'strcmp')
                   OR callee_function LIKE '%indexOf%'
                   OR callee_function LIKE '%includes%')
              AND (argument_expr LIKE '%origin%' OR argument_expr LIKE '%Origin%')
            ORDER BY file, line
        """)

        for file, line, func, args in self.cursor.fetchall():
            # Check if toLowerCase/toUpperCase is nearby
            self.cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND ABS(line - ?) <= 3
                  AND (callee_function LIKE '%toLowerCase%'
                       OR callee_function LIKE '%toUpperCase%')
            """, (file, line))

            if self.cursor.fetchone()[0] == 0:
                self.findings.append(StandardFinding(
                    rule_name='cors-case-sensitivity',
                    message='Case-sensitive origin comparison - can be bypassed with different casing',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.LOW,
                    category='security',
                    snippet=f'{func}(...origin...)',
                    fix_suggestion='Normalize case before comparing origins. Use toLowerCase() on both values.',
                    cwe_id='CWE-178'  # Improper Handling of Case Sensitivity
                ))

    # ========================================================================
    # CHECK 9: Missing Vary Header
    # ========================================================================

    def _check_missing_vary_header(self):
        """Detect missing Vary: Origin header causing cache poisoning."""
        if 'function_call_args' not in self.existing_tables:
            return

        # Find files setting Access-Control-Allow-Origin
        self.cursor.execute("""
            SELECT DISTINCT file FROM function_call_args
            WHERE argument_expr LIKE '%Access-Control-Allow-Origin%'
        """)

        cors_files = [row[0] for row in self.cursor.fetchall()]

        for file in cors_files:
            # Check if Vary header is set in same file
            self.cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND argument_expr LIKE '%Vary%'
                  AND argument_expr LIKE '%Origin%'
            """, (file,))

            if self.cursor.fetchone()[0] == 0:
                # Find a line number for reporting
                self.cursor.execute("""
                    SELECT MIN(line) FROM function_call_args
                    WHERE file = ?
                      AND argument_expr LIKE '%Access-Control-Allow-Origin%'
                """, (file,))

                line = self.cursor.fetchone()[0] or 1

                self.findings.append(StandardFinding(
                    rule_name='cors-missing-vary',
                    message='Missing Vary: Origin header - vulnerable to cache poisoning',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    snippet='Access-Control-Allow-Origin without Vary: Origin',
                    fix_suggestion='Always set "Vary: Origin" when origin is dynamic to prevent cache poisoning.',
                    cwe_id='CWE-524'  # Use of Cache Containing Sensitive Information
                ))

    # ========================================================================
    # CHECK 10: Excessive Preflight Cache
    # ========================================================================

    def _check_excessive_preflight_cache(self):
        """Detect excessive Access-Control-Max-Age values."""
        if 'function_call_args' not in self.existing_tables:
            return

        self.cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE argument_expr LIKE '%Access-Control-Max-Age%'
            ORDER BY file, line
        """)

        for file, line, args in self.cursor.fetchall():
            # Extract max age value
            max_age_match = re.search(r'Max-Age["\s:]+(\d+)', args, re.IGNORECASE)
            if max_age_match:
                max_age = int(max_age_match.group(1))

                # Check if excessive (>1 day = 86400 seconds)
                if max_age > 86400:
                    days = max_age / 86400
                    self.findings.append(StandardFinding(
                        rule_name='cors-excessive-cache',
                        message=f'Excessive CORS preflight cache: {days:.1f} days - changes won\'t apply',
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        confidence=Confidence.HIGH,
                        category='security',
                        snippet=f'Access-Control-Max-Age: {max_age}',
                        fix_suggestion='Use reasonable Max-Age (3600-7200 seconds). Long cache prevents security updates.',
                        cwe_id='CWE-942'
                    ))

    # ========================================================================
    # CHECK 11: WebSocket CORS Bypass
    # ========================================================================

    def _check_websocket_bypass(self):
        """Detect WebSocket handlers without origin validation."""
        if 'function_call_args' not in self.existing_tables:
            return

        # Find WebSocket connection handlers
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({})
              OR argument_expr LIKE '%connection%'
              OR argument_expr LIKE '%upgrade%'
            ORDER BY file, line
        """.format(','.join(['?'] * len(self.patterns.WEBSOCKET_HANDLERS))),
        list(self.patterns.WEBSOCKET_HANDLERS))

        for file, line, func, args in self.cursor.fetchall():
            # Check if origin validation exists nearby
            self.cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND ABS(line - ?) <= 20
                  AND (argument_expr LIKE '%origin%'
                       OR argument_expr LIKE '%handshake%'
                       OR callee_function LIKE '%authenticate%')
            """, (file, line))

            if self.cursor.fetchone()[0] == 0:
                self.findings.append(StandardFinding(
                    rule_name='cors-websocket-bypass',
                    message='WebSocket connection without origin validation - bypasses CORS',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.LOW,
                    category='security',
                    snippet=f'{func}("connection", ...)',
                    fix_suggestion='Validate origin in WebSocket handshake. WebSockets don\'t follow CORS.',
                    cwe_id='CWE-346'
                ))

    # ========================================================================
    # CHECK 12: Dynamic Origin Validation Flaws
    # ========================================================================

    def _check_dynamic_origin_flaws(self):
        """Detect flawed dynamic origin validation logic."""
        if 'assignments' not in self.existing_tables:
            return

        # Find dynamic origin validators
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (target_var LIKE '%origin%' OR target_var LIKE '%cors%')
              AND (source_expr LIKE '%function%' OR source_expr LIKE '%=>%'
                   OR source_expr LIKE '%callback%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            issues = []

            # Check for dangerous patterns in dynamic validators
            if '|| "*"' in expr or '|| true' in expr:
                issues.append('falls back to wildcard')

            if 'return true' in expr and 'return false' not in expr:
                issues.append('always returns true')

            if 'callback(null, true)' in expr and 'callback(null, false)' not in expr:
                issues.append('always allows origin')

            if issues:
                self.findings.append(StandardFinding(
                    rule_name='cors-dynamic-flaw',
                    message=f'Flawed dynamic origin validation: {", ".join(issues)}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    snippet=f'{var} = function(...)',
                    fix_suggestion='Ensure dynamic validators properly reject invalid origins. No wildcard fallbacks.',
                    cwe_id='CWE-942'
                ))

    # ========================================================================
    # CHECK 13: Fallback to Wildcard
    # ========================================================================

    def _check_fallback_wildcards(self):
        """Detect configurations that fall back to wildcard on error."""
        if 'assignments' not in self.existing_tables:
            return

        # Look for conditional/ternary operators with wildcards
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (target_var LIKE '%origin%' OR target_var LIKE '%cors%')
              AND source_expr LIKE '%?%'
              AND (source_expr LIKE '%*%' OR source_expr LIKE '%true%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check for ternary with wildcard fallback
            if re.search(r'\?\s*["\']?\*["\']?\s*:', expr) or re.search(r':\s*["\']?\*["\']?', expr):
                self.findings.append(StandardFinding(
                    rule_name='cors-wildcard-fallback',
                    message='CORS configuration falls back to wildcard - security risk',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    category='security',
                    snippet=f'{var} = ... ? ... : "*"',
                    fix_suggestion='Never fall back to wildcard. Use safe default or reject invalid origins.',
                    cwe_id='CWE-942'
                ))

    # ========================================================================
    # CHECK 14: Development Configuration Leaks
    # ========================================================================

    def _check_development_configs(self):
        """Detect development CORS configs that might leak to production."""
        if 'assignments' not in self.existing_tables:
            return

        # Look for environment-based CORS configs
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (target_var LIKE '%origin%' OR target_var LIKE '%cors%')
              AND (source_expr LIKE '%NODE_ENV%' OR source_expr LIKE '%development%'
                   OR source_expr LIKE '%localhost%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check for unsafe development configs
            if 'development' in expr.lower() and ('*' in expr or 'true' in expr or 'localhost' in expr):
                self.findings.append(StandardFinding(
                    rule_name='cors-dev-leak',
                    message='Unsafe development CORS config - might leak to production',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    snippet=f'{var} = NODE_ENV === "development" ? "*" : ...',
                    fix_suggestion='Use environment-specific config files. Never use wildcards even in development.',
                    cwe_id='CWE-489'  # Active Debug Code
                ))

    # ========================================================================
    # CHECK 15: Framework-Specific Issues
    # ========================================================================

    def _check_framework_specific(self):
        """Detect framework-specific CORS misconfigurations."""
        if 'function_call_args' not in self.existing_tables:
            return

        # Check Express specific issues
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ('app.use', 'router.use')
              AND argument_expr LIKE '%cors%'
            ORDER BY file, line
        """)

        for file, line, func, args in self.cursor.fetchall():
            # Check if CORS middleware is applied after routes
            self.cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND line < ?
                  AND (callee_function LIKE '%.get'
                       OR callee_function LIKE '%.post'
                       OR callee_function LIKE '%.route')
            """, (file, line))

            routes_before = self.cursor.fetchone()[0]

            if routes_before > 0:
                self.findings.append(StandardFinding(
                    rule_name='cors-middleware-order',
                    message='CORS middleware applied after routes - some endpoints unprotected',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    snippet=f'{func}(cors()) // After route definitions',
                    fix_suggestion='Apply CORS middleware before defining routes. Order matters in Express.',
                    cwe_id='CWE-696'  # Incorrect Behavior Order
                ))

        # Check Flask-CORS specific issues
        if 'CORS' in str(self.patterns.CORS_FUNCTIONS):
            self.cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function = 'CORS'
                  AND argument_expr LIKE '%resources%/*%'
                  AND argument_expr LIKE '%supports_credentials%True%'
                ORDER BY file, line
            """)

            for file, line, func, args in self.cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='cors-flask-wildcard',
                    message='Flask-CORS with wildcard resources and credentials',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category='security',
                    snippet='CORS(app, resources="/*", supports_credentials=True)',
                    fix_suggestion='Specify exact resource paths when using credentials in Flask-CORS.',
                    cwe_id='CWE-942'
                ))


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def find_cors_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Main entry point for CORS vulnerability detection.

    Args:
        context: Standard rule context with database path

    Returns:
        List of CORS vulnerability findings
    """
    analyzer = CORSAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# TAINT PATTERN REGISTRATION
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register CORS-related taint patterns for flow analysis.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = CORSPatterns()

    # Register origin as taint source
    origin_sources = [
        'req.headers.origin',
        'request.headers.origin',
        'req.header.origin',
        'req.get("origin")'
    ]

    for source in origin_sources:
        taint_registry.register_source(source, 'user_input', 'javascript')
        taint_registry.register_source(source, 'user_input', 'python')

    # Register CORS headers as sinks
    for header in patterns.CORS_HEADERS:
        taint_registry.register_sink(header, 'cors_header', 'all')

    # Register response methods as sinks
    response_methods = [
        'res.setHeader', 'res.set', 'res.header',
        'response.headers', 'response.set_header'
    ]

    for method in response_methods:
        taint_registry.register_sink(method, 'response', 'all')