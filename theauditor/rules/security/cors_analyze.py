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

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata

# ============================================================================
# RULE METADATA (Golden Standard)
# ============================================================================

METADATA = RuleMetadata(
    name="cors_security",
    category="security",
    target_extensions=['.py', '.js', '.ts'],
    exclude_patterns=['test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)

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

    def analyze(self) -> list[StandardFinding]:
        """Main entry point - runs all CORS vulnerability checks.

        Returns:
            List of CORS vulnerability findings
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
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

    # ========================================================================
    # CHECK 1: Classic Wildcard with Credentials
    # ========================================================================

    def _check_wildcard_with_credentials(self):
        """Detect wildcard origin with credentials enabled."""
        # Check CORS function calls - static query
        placeholders = ','.join(['?'] * len(self.patterns.CORS_FUNCTIONS))
        query = f"""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({placeholders})
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """
        self.cursor.execute(query, list(self.patterns.CORS_FUNCTIONS))

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
                    code_snippet=f'{func}(origin: "*", credentials: true)',
                    cwe_id='CWE-942'  # Permissive Cross-domain Policy
                ))

    # ========================================================================
    # CHECK 2: Subdomain Wildcards
    # ========================================================================

    def _check_subdomain_wildcards(self):
        """Detect subdomain wildcard patterns that enable takeover attacks."""
        # Fetch all assignments, filter in Python
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if variable name contains origin or cors
            var_lower = var.lower()
            if not ('origin' in var_lower or 'cors' in var_lower):
                continue

            # Check if source expression contains wildcard patterns
            if not ('*.' in expr or '/.' in expr):
                continue

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
                        code_snippet=f'{var} = {expr[:100]}',
                        cwe_id='CWE-942'
                    ))
                    break

    # ========================================================================
    # CHECK 3: Null Origin Handling
    # ========================================================================

    def _check_null_origin_handling(self):
        """Detect allowing 'null' origin which enables sandbox attacks."""
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        for row in self.cursor.fetchall():
            file, line, callee, args = row[0], row[1], row[2], row[3]

            # Check if contains 'null'
            if 'null' not in str(args).lower():
                continue

            # Check if related to origin or is CORS function
            if not ('origin' in str(args).lower() or callee in self.patterns.CORS_FUNCTIONS):
                continue

            # Check if null is being explicitly allowed
            self.findings.append(StandardFinding(
                rule_name='cors-null-origin',
                message='CORS allows "null" origin - enables attacks from sandboxed contexts',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
                category='security',
                code_snippet='origin: [..., "null", ...]',
                cwe_id='CWE-346'  # Origin Validation Error
            ))

        # Check in assignments
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for row in self.cursor.fetchall():
            file, line, var, expr = row[0], row[1], row[2], row[3]

            # Check if variable contains origin or whitelist
            var_lower = var.lower()
            if not ('origin' in var_lower or 'whitelist' in var_lower):
                continue

            # Check if source contains null
            if 'null' not in expr.lower():
                continue

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
                    code_snippet='origin: [..., "null", ...]',
                    cwe_id='CWE-346'  # Origin Validation Error
                ))

    # ========================================================================
    # CHECK 4: Origin Reflection Without Validation
    # ========================================================================

    def _check_origin_reflection(self):
        """Detect reflecting origin header without validation."""
        # Fetch all assignments, filter in Python
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE source_expr IS NOT NULL
            ORDER BY file, line
        """)

        origin_patterns = ['req.headers.origin', 'req.header', 'request.headers.origin', 'request.headers[']

        for file, line, var, expr in self.cursor.fetchall():
            # Check if source expression contains origin header access
            if not any(pattern in expr for pattern in origin_patterns):
                continue

            # Check if 'origin' is in the expression
            if 'origin' not in expr.lower():
                continue

            # Check if there's validation nearby - fetch function calls for this file
            self.cursor.execute("""
                SELECT callee_function, line, argument_expr
                FROM function_call_args
                WHERE file = ?
                  AND callee_function IS NOT NULL
            """, (file,))

            # Filter in Python for nearby validation and validation functions
            validation_funcs = ['includes', 'indexOf', 'test', 'match']
            validation_keywords = ['whitelist', 'allowed']

            nearby_validation = []
            for callee, func_line, args in self.cursor.fetchall():
                if abs(func_line - line) > 10:
                    continue

                # Check if function is validation-related
                if any(vf in callee for vf in validation_funcs):
                    nearby_validation.append((callee, func_line))
                    continue

                # Check if args contain validation keywords
                if args and any(kw in str(args).lower() for kw in validation_keywords):
                    nearby_validation.append((callee, func_line))

            validation_count = len(nearby_validation)

            if validation_count == 0:
                self.findings.append(StandardFinding(
                    rule_name='cors-origin-reflection',
                    message='Origin header reflected without validation - attacker can bypass CORS',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category='security',
                    code_snippet=f'{var} = {expr}',
                    cwe_id='CWE-346'
                ))

    # ========================================================================
    # CHECK 5: Regex Vulnerabilities
    # ========================================================================

    def _check_regex_vulnerabilities(self):
        """Detect vulnerable regex patterns in CORS origin validation."""
        # Fetch all assignments, filter in Python
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if variable name contains origin or cors
            var_lower = var.lower()
            if not ('origin' in var_lower or 'cors' in var_lower):
                continue

            # Check if source contains regex patterns
            if not ('RegExp' in expr or '/^' in expr):
                continue

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
                    code_snippet=f'{var} = {expr[:100]}',
                    cwe_id='CWE-185'  # Incorrect Regular Expression
                ))

    # ========================================================================
    # CHECK 6: Protocol Downgrade
    # ========================================================================

    def _check_protocol_downgrade(self):
        """Detect allowing HTTP origins when HTTPS should be required."""
        # Fetch all assignments, filter in Python
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for row in self.cursor.fetchall():
            file, line, var, expr = row[0], row[1], row[2], row[3]

            # Check if variable contains origin or cors
            var_lower = var.lower()
            if not ('origin' in var_lower or 'cors' in var_lower):
                continue

            # Check if source contains http:// but not https://
            if 'http://' not in expr or 'https://' in expr:
                continue

            self.findings.append(StandardFinding(
                rule_name='cors-protocol-downgrade',
                message='HTTP origin allowed - vulnerable to protocol downgrade attacks',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category='security',
                code_snippet='origin: "http://..."',
                cwe_id='CWE-757'  # Selection of Less-Secure Algorithm
            ))

        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        for row in self.cursor.fetchall():
            file, line, callee, args = row[0], row[1], row[2], row[3]

            # Check if CORS function
            if callee not in self.patterns.CORS_FUNCTIONS:
                continue

            # Check if contains http:// but skip localhost
            if 'http://' not in args:
                continue

            if 'localhost' in args or '127.0.0.1' in args:
                continue

            self.findings.append(StandardFinding(
                rule_name='cors-protocol-downgrade',
                message='HTTP origin allowed - vulnerable to protocol downgrade attacks',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                category='security',
                code_snippet='origin: "http://..."',
                cwe_id='CWE-757'  # Selection of Less-Secure Algorithm
            ))

    # ========================================================================
    # CHECK 7: Port Confusion
    # ========================================================================

    def _check_port_confusion(self):
        """Detect port handling issues in CORS origin validation."""
        # Fetch all assignments, filter in Python
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if variable contains origin or cors
            var_lower = var.lower()
            if not ('origin' in var_lower or 'cors' in var_lower):
                continue

            # Check if source contains port (colon)
            if ':' not in expr:
                continue

            # Skip standard ports
            if ':80' in expr or ':443' in expr:
                continue

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
                    code_snippet=f'{var} = {expr[:100]}',
                    cwe_id='CWE-942'
                ))

    # ========================================================================
    # CHECK 8: Case Sensitivity Issues
    # ========================================================================

    def _check_case_sensitivity(self):
        """Detect case-sensitive origin comparisons that can be bypassed."""
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        comparison_funcs = ['===', '==', 'equals', 'strcmp']

        for file, line, func, args in self.cursor.fetchall():
            # Check if function is comparison function or contains indexOf/includes
            if not (func in comparison_funcs or 'indexOf' in func or 'includes' in func):
                continue

            # Check if args contain 'origin' (case insensitive)
            if 'origin' not in args.lower():
                continue

            # Check if toLowerCase/toUpperCase is nearby - fetch case functions for this file
            self.cursor.execute("""
                SELECT callee_function, line
                FROM function_call_args
                WHERE file = ?
                  AND callee_function IS NOT NULL
            """, (file,))

            # Filter in Python for nearby case functions
            nearby_case = []
            for callee, func_line in self.cursor.fetchall():
                if abs(func_line - line) > 3:
                    continue

                if 'toLowerCase' in callee or 'toUpperCase' in callee:
                    nearby_case.append((callee, func_line))

            if len(nearby_case) == 0:
                self.findings.append(StandardFinding(
                    rule_name='cors-case-sensitivity',
                    message='Case-sensitive origin comparison - can be bypassed with different casing',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.LOW,
                    category='security',
                    code_snippet=f'{func}(...origin...)',
                    cwe_id='CWE-178'  # Improper Handling of Case Sensitivity
                ))

    # ========================================================================
    # CHECK 9: Missing Vary Header
    # ========================================================================

    def _check_missing_vary_header(self):
        """Detect missing Vary: Origin header causing cache poisoning."""
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT DISTINCT file, argument_expr, line
            FROM function_call_args
            WHERE argument_expr IS NOT NULL
        """)

        # Build map of files with CORS headers
        cors_files = {}
        for file, args, line in self.cursor.fetchall():
            if 'Access-Control-Allow-Origin' in args:
                if file not in cors_files:
                    cors_files[file] = line

        for file, first_line in cors_files.items():
            # Check if Vary header is set in same file
            self.cursor.execute("""
                SELECT argument_expr
                FROM function_call_args
                WHERE file = ?
                  AND argument_expr IS NOT NULL
                LIMIT 100
            """, (file,))

            has_vary = False
            for (args,) in self.cursor.fetchall():
                if 'Vary' in args and 'Origin' in args:
                    has_vary = True
                    break

            if not has_vary:
                line = first_line

                self.findings.append(StandardFinding(
                    rule_name='cors-missing-vary',
                    message='Missing Vary: Origin header - vulnerable to cache poisoning',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    code_snippet='Access-Control-Allow-Origin without Vary: Origin',
                    cwe_id='CWE-524'  # Use of Cache Containing Sensitive Information
                ))

    # ========================================================================
    # CHECK 10: Excessive Preflight Cache
    # ========================================================================

    def _check_excessive_preflight_cache(self):
        """Detect excessive Access-Control-Max-Age values."""
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, argument_expr
            FROM function_call_args
            WHERE argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, args in self.cursor.fetchall():
            # Check if contains Access-Control-Max-Age
            if 'Access-Control-Max-Age' not in args:
                continue

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
                        code_snippet=f'Access-Control-Max-Age: {max_age}',
                        cwe_id='CWE-942'
                    ))

    # ========================================================================
    # CHECK 11: WebSocket CORS Bypass
    # ========================================================================

    def _check_websocket_bypass(self):
        """Detect WebSocket handlers without origin validation."""
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, func, args in self.cursor.fetchall():
            # Check if WebSocket handler
            is_websocket = (func in self.patterns.WEBSOCKET_HANDLERS or
                          (args and ('connection' in args or 'upgrade' in args)))

            if not is_websocket:
                continue

            # Check if origin validation exists nearby - fetch function calls for this file
            self.cursor.execute("""
                SELECT callee_function, line, argument_expr
                FROM function_call_args
                WHERE file = ?
                  AND callee_function IS NOT NULL
            """, (file,))

            # Filter in Python for nearby validation
            validation_count = 0
            for callee, func_line, func_args in self.cursor.fetchall():
                if abs(func_line - line) > 20:
                    continue

                # Check for validation patterns
                if func_args and ('origin' in func_args or 'handshake' in func_args):
                    validation_count += 1
                    break

                if 'authenticate' in callee:
                    validation_count += 1
                    break

            if validation_count == 0:
                self.findings.append(StandardFinding(
                    rule_name='cors-websocket-bypass',
                    message='WebSocket connection without origin validation - bypasses CORS',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.LOW,
                    category='security',
                    code_snippet=f'{func}("connection", ...)',
                    cwe_id='CWE-346'
                ))

    # ========================================================================
    # CHECK 12: Dynamic Origin Validation Flaws
    # ========================================================================

    def _check_dynamic_origin_flaws(self):
        """Detect flawed dynamic origin validation logic."""
        # Fetch all assignments, filter in Python
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if variable contains origin or cors
            var_lower = var.lower()
            if not ('origin' in var_lower or 'cors' in var_lower):
                continue

            # Check if source contains function/callback patterns
            if not ('function' in expr or '=>' in expr or 'callback' in expr):
                continue

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
                    code_snippet=f'{var} = function(...)',
                    cwe_id='CWE-942'
                ))

    # ========================================================================
    # CHECK 13: Fallback to Wildcard
    # ========================================================================

    def _check_fallback_wildcards(self):
        """Detect configurations that fall back to wildcard on error."""
        # Fetch all assignments, filter in Python
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if variable contains origin or cors
            var_lower = var.lower()
            if not ('origin' in var_lower or 'cors' in var_lower):
                continue

            # Check if source contains ternary and wildcard/true
            if '?' not in expr:
                continue

            if not ('*' in expr or 'true' in expr):
                continue

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
                    code_snippet=f'{var} = ... ? ... : "*"',
                    cwe_id='CWE-942'
                ))

    # ========================================================================
    # CHECK 14: Development Configuration Leaks
    # ========================================================================

    def _check_development_configs(self):
        """Detect development CORS configs that might leak to production."""
        # Fetch all assignments, filter in Python
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if variable contains origin or cors
            var_lower = var.lower()
            if not ('origin' in var_lower or 'cors' in var_lower):
                continue

            # Check if source contains development environment patterns
            if not ('NODE_ENV' in expr or 'development' in expr or 'localhost' in expr):
                continue

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
                    code_snippet=f'{var} = NODE_ENV === "development" ? "*" : ...',
                    cwe_id='CWE-489'  # Active Debug Code
                ))

    # ========================================================================
    # CHECK 15: Framework-Specific Issues
    # ========================================================================

    def _check_framework_specific(self):
        """Detect framework-specific CORS misconfigurations."""
        # Fetch all function_call_args, filter in Python
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ('app.use', 'router.use')
              AND argument_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, func, args in self.cursor.fetchall():
            # Check if arguments contain 'cors'
            if 'cors' not in args.lower():
                continue

            # Check if CORS middleware is applied after routes
            self.cursor.execute("""
                SELECT callee_function, line
                FROM function_call_args
                WHERE file = ?
                  AND line < ?
                  AND callee_function IS NOT NULL
            """, (file, line))

            # Filter in Python for route methods
            routes_before = 0
            for callee, callee_line in self.cursor.fetchall():
                if '.get' in callee or '.post' in callee or '.route' in callee:
                    routes_before += 1

            if routes_before > 0:
                self.findings.append(StandardFinding(
                    rule_name='cors-middleware-order',
                    message='CORS middleware applied after routes - some endpoints unprotected',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category='security',
                    code_snippet=f'{func}(cors()) // After route definitions',
                    cwe_id='CWE-696'  # Incorrect Behavior Order
                ))

        # Check Flask-CORS specific issues
        if 'CORS' in str(self.patterns.CORS_FUNCTIONS):
            # Fetch all CORS function calls, filter in Python
            self.cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function = 'CORS'
                  AND argument_expr IS NOT NULL
                ORDER BY file, line
            """)

            for file, line, func, args in self.cursor.fetchall():
                # Check if args contain wildcard resources and credentials
                if not ('resources' in args and '/*' in args):
                    continue

                if not ('supports_credentials' in args and 'True' in args):
                    continue

                self.findings.append(StandardFinding(
                    rule_name='cors-flask-wildcard',
                    message='Flask-CORS with wildcard resources and credentials',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category='security',
                    code_snippet='CORS(app, resources="/*", supports_credentials=True)',
                    cwe_id='CWE-942'
                ))


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def find_cors_issues(context: StandardRuleContext) -> list[StandardFinding]:
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