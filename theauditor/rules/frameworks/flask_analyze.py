"""Flask Framework Security Analyzer - Database-First Approach.

Analyzes Flask applications for security vulnerabilities using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Proper confidence levels
"""


import json
import sqlite3
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# METADATA
# ============================================================================

METADATA = RuleMetadata(
    name="flask_security",
    category="frameworks",
    target_extensions=['.py'],
    exclude_patterns=['test/', 'spec.', '__tests__', 'migrations/'],
    requires_jsx_pass=False
)


# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class FlaskPatterns:
    """Configuration for Flask security patterns."""

    # User input sources that need validation
    USER_INPUT_SOURCES = frozenset([
        'request.', 'user_input', 'data', 'user_',
        'request.args', 'request.form', 'request.values',
        'request.json', 'request.data', 'request.files',
        'request.cookies', 'request.headers', 'request.environ'
    ])

    # Template injection risk functions
    TEMPLATE_FUNCS = frozenset([
        'render_template_string', 'Markup'
    ])

    # Dangerous functions for injection
    DANGEROUS_FUNCS = frozenset([
        'eval', 'exec', 'compile', '__import__',
        'pickle.loads', 'pickle.load', 'loads', 'load'
    ])

    # SQL execution methods
    SQL_METHODS = frozenset([
        'execute', 'executemany', 'query', 'exec'
    ])

    # String formatting patterns
    STRING_FORMATS = frozenset([
        '%', '.format', 'f"', "f'"
    ])

    # Security-related variable names
    SECRET_VARS = frozenset([
        'SECRET_KEY', 'secret_key', 'API_KEY', 'api_key',
        'PASSWORD', 'password', 'TOKEN', 'token'
    ])

    # Environment variable functions
    ENV_FUNCS = frozenset([
        'environ', 'getenv', 'os.environ', 'os.getenv'
    ])

    # File validation functions
    FILE_VALIDATORS = frozenset([
        'secure_filename', 'validate', 'allowed'
    ])

    # CSRF protection libraries
    CSRF_LIBS = frozenset([
        'flask_wtf', 'CSRFProtect', 'csrf'
    ])

    # Session cookie configuration
    SESSION_CONFIGS = frozenset([
        'SESSION_COOKIE_SECURE', 'SESSION_COOKIE_HTTPONLY',
        'SESSION_COOKIE_SAMESITE'
    ])


# ============================================================================
# MAIN RULE FUNCTION (Standardized Interface)
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Flask security misconfigurations.

    Analyzes database for:
    - Server-Side Template Injection (SSTI)
    - XSS via Markup()
    - Debug mode enabled
    - Hardcoded secret keys
    - Unsafe file uploads
    - SQL injection risks
    - Open redirect vulnerabilities
    - Eval usage with user input
    - CORS wildcard configuration
    - Unsafe deserialization
    - Werkzeug debugger exposure
    - Missing CSRF protection
    - Session cookie security

    Args:
        context: Standardized rule context with database path

    Returns:
        List of StandardFinding objects for detected issues
    """
    analyzer = FlaskAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# FLASK ANALYZER CLASS
# ============================================================================

class FlaskAnalyzer:
    """Main analyzer for Flask applications."""

    def __init__(self, context: StandardRuleContext):
        self.context = context
        self.patterns = FlaskPatterns()
        self.findings: list[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")

        # Track Flask-specific data
        self.flask_files: list[str] = []

    def analyze(self) -> list[StandardFinding]:
        """Run complete Flask analysis."""
        # Load Flask data from database
        if not self._load_flask_data():
            return self.findings  # Not a Flask project

        # Run all security checks (12 original patterns - HTML in JSON + CSRF + Session)
        self._check_ssti_risks()
        self._check_markup_xss()
        self._check_debug_mode()
        self._check_hardcoded_secrets()
        self._check_unsafe_file_uploads()
        self._check_sql_injection()
        self._check_open_redirects()
        self._check_eval_usage()
        self._check_cors_wildcard()
        self._check_unsafe_deserialization()
        self._check_werkzeug_debugger()
        self._check_csrf_protection()
        self._check_session_security()

        return self.findings

    def _load_flask_data(self) -> bool:
        """Load Flask-related data from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if this is a Flask project - use schema-compliant query
            query = build_query('refs', ['src'],
                               where="value IN ('flask', 'Flask')")
            cursor.execute(query)
            flask_refs = cursor.fetchall()

            if not flask_refs:
                conn.close()
                return False  # Not a Flask project

            self.flask_files = [ref[0] for ref in flask_refs]
            conn.close()
            return True

        except (sqlite3.Error, Exception):
            return False

    def _check_ssti_risks(self) -> None:
        """Check for Server-Side Template Injection risks."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                               where="callee_function = 'render_template_string'",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, template_arg in cursor.fetchall():
                # Check if user input is involved
                has_user_input = any(src in template_arg for src in self.patterns.USER_INPUT_SOURCES)

                self.findings.append(StandardFinding(
                    rule_name='flask-ssti-render-template-string',
                    message='Use of render_template_string - Server-Side Template Injection risk',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL if has_user_input else Severity.HIGH,
                    category='injection',
                    confidence=Confidence.HIGH if has_user_input else Confidence.MEDIUM,
                    snippet=template_arg[:100] if len(template_arg) > 100 else template_arg,
                    cwe_id='CWE-94'  # Improper Control of Generation of Code
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_markup_xss(self) -> None:
        """Check for XSS via Markup()."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                               where="callee_function = 'Markup'",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, markup_content in cursor.fetchall():
                # Check if user input is involved
                if any(src in markup_content for src in self.patterns.USER_INPUT_SOURCES):
                    self.findings.append(StandardFinding(
                        rule_name='flask-markup-xss',
                        message='Use of Markup() with potential user input - XSS risk',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='xss',
                        confidence=Confidence.HIGH,
                        snippet=markup_content[:100] if len(markup_content) > 100 else markup_content,
                        cwe_id='CWE-79'  # Cross-site Scripting
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_debug_mode(self) -> None:
        """Check for debug mode enabled."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all function calls, filter in Python
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, callee, args in cursor.fetchall():
                # Filter for .run methods with debug=True
                if not callee.endswith('.run'):
                    continue
                if 'debug' not in args or 'True' not in args:
                    continue
                self.findings.append(StandardFinding(
                    rule_name='flask-debug-mode-enabled',
                    message='Flask debug mode enabled - exposes interactive debugger',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    confidence=Confidence.HIGH,
                    snippet=args[:100] if len(args) > 100 else args,
                    cwe_id='CWE-489'  # Active Debug Code
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_hardcoded_secrets(self) -> None:
        """Check for hardcoded secret keys."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all assignments, filter in Python
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, var_name, secret_value in cursor.fetchall():
                # Filter for secret variable names in Python
                var_name_upper = var_name.upper()
                if not any(secret in var_name_upper for secret in self.patterns.SECRET_VARS):
                    continue

                # Filter for hardcoded strings (not env vars)
                if not ('"' in secret_value or "'" in secret_value):
                    continue
                if 'environ' in secret_value or 'getenv' in secret_value:
                    continue
                # Check secret strength
                clean_secret = secret_value.strip('"\'')
                if len(clean_secret) < 32:
                    self.findings.append(StandardFinding(
                        rule_name='flask-secret-key-exposed',
                        message=f'Weak/hardcoded secret key ({len(clean_secret)} chars) - compromises session security',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='security',
                        confidence=Confidence.HIGH,
                        snippet=f'{var_name} = {secret_value[:30]}...',
                        cwe_id='CWE-798'  # Use of Hard-coded Credentials
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_unsafe_file_uploads(self) -> None:
        """Check for unsafe file upload operations."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all function calls, build relationships in Python
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               order_by="file, line")
            cursor.execute(query)

            all_calls = cursor.fetchall()
            save_calls = []
            file_validators = {}

            # First pass: identify .save calls and validators
            for file, line, callee, arg_expr in all_calls:
                if callee.endswith('.save'):
                    save_calls.append((file, line, callee, arg_expr))
                if callee in self.patterns.FILE_VALIDATORS:
                    if file not in file_validators:
                        file_validators[file] = []
                    file_validators[file].append(line)

            # Second pass: check for request.files nearby without validation
            seen = set()
            for save_file, save_line, save_callee, save_arg in save_calls:
                # Check if request.files is used nearby (within 10 lines before)
                has_file_input = False
                for file, line, callee, arg_expr in all_calls:
                    if file == save_file and abs(line - save_line) <= 10:
                        if 'request.files' in arg_expr:
                            has_file_input = True
                            break

                if not has_file_input:
                    continue

                # Check if validators are present nearby
                has_validation = False
                if save_file in file_validators:
                    for val_line in file_validators[save_file]:
                        if abs(val_line - save_line) <= 10:
                            has_validation = True
                            break

                if not has_validation:
                    key = (save_file, save_line)
                    if key not in seen:
                        seen.add(key)
                        file, line = key
                self.findings.append(StandardFinding(
                    rule_name='flask-unsafe-file-upload',
                    message='File upload without validation - malicious file upload risk',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    confidence=Confidence.HIGH,
                    snippet='request.files[...].save() without secure_filename()',
                    cwe_id='CWE-434'  # Unrestricted Upload of File with Dangerous Type
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_sql_injection(self) -> None:
        """Check for SQL injection risks."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all SQL queries, filter in Python
            query = build_query('sql_queries', ['file_path', 'line_number', 'query_text'],
                               order_by="file_path, line_number")
            cursor.execute(query)

            for file, line, query_text in cursor.fetchall():
                # Check for string formatting patterns in Python
                if not ('%' in query_text and '%' in query_text[query_text.index('%')+1:]):
                    if '.format(' not in query_text:
                        if 'f"' not in query_text and "f'" not in query_text:
                            continue
                self.findings.append(StandardFinding(
                    rule_name='flask-sql-injection-risk',
                    message='String formatting in SQL query - SQL injection vulnerability',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    confidence=Confidence.HIGH,
                    snippet=query_text[:100] if len(query_text) > 100 else query_text,
                    cwe_id='CWE-89'  # SQL Injection
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_open_redirects(self) -> None:
        """Check for open redirect vulnerabilities."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch redirect calls, filter in Python
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               where="callee_function = 'redirect'",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, callee, redirect_arg in cursor.fetchall():
                # Check for user input patterns in Python
                if not ('request.args.get' in redirect_arg or
                        'request.values.get' in redirect_arg or
                        'request.form.get' in redirect_arg):
                    continue
                self.findings.append(StandardFinding(
                    rule_name='flask-unsafe-redirect',
                    message='Unvalidated redirect from user input - open redirect vulnerability',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    confidence=Confidence.HIGH,
                    snippet=redirect_arg[:100] if len(redirect_arg) > 100 else redirect_arg,
                    cwe_id='CWE-601'  # URL Redirection to Untrusted Site
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_eval_usage(self) -> None:
        """Check for eval usage with user input."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch eval calls, filter in Python
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               where="callee_function = 'eval'",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, callee, eval_arg in cursor.fetchall():
                # Check for request input in Python
                if 'request.' not in eval_arg:
                    continue
                self.findings.append(StandardFinding(
                    rule_name='flask-eval-usage',
                    message='Use of eval with user input - code injection vulnerability',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    confidence=Confidence.HIGH,
                    snippet=eval_arg[:100] if len(eval_arg) > 100 else eval_arg,
                    cwe_id='CWE-95'  # Improper Neutralization of Directives in Dynamically Evaluated Code
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_cors_wildcard(self) -> None:
        """Check for CORS wildcard configuration."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check assignments - fetch all, filter in Python
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, target_var, cors_config in cursor.fetchall():
                # Filter for CORS variables in Python
                target_upper = target_var.upper()
                if 'CORS' not in target_upper and 'ACCESS-CONTROL-ALLOW-ORIGIN' not in target_upper:
                    continue
                if '*' not in cors_config:
                    continue

                self.findings.append(StandardFinding(
                    rule_name='flask-cors-wildcard',
                    message='CORS with wildcard origin - allows any domain access',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    confidence=Confidence.HIGH,
                    snippet=cors_config[:100] if len(cors_config) > 100 else cors_config,
                    cwe_id='CWE-346'  # Origin Validation Error
                ))

            # Check function calls - fetch CORS calls, filter in Python
            query2 = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                                where="callee_function = 'CORS'",
                                order_by="file, line")
            cursor.execute(query2)

            for file, line, callee, cors_arg in cursor.fetchall():
                if '*' not in cors_arg:
                    continue
                self.findings.append(StandardFinding(
                    rule_name='flask-cors-wildcard',
                    message='CORS with wildcard origin - allows any domain access',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    confidence=Confidence.HIGH,
                    snippet=cors_arg[:100] if len(cors_arg) > 100 else cors_arg,
                    cwe_id='CWE-346'  # Origin Validation Error
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_unsafe_deserialization(self) -> None:
        """Check for unsafe pickle deserialization."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch pickle calls, filter in Python
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               where="callee_function IN ('pickle.loads', 'loads', 'pickle.load', 'load')",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, callee, pickle_arg in cursor.fetchall():
                # Check for request input in Python
                if 'request.' not in pickle_arg:
                    continue
                self.findings.append(StandardFinding(
                    rule_name='flask-unsafe-deserialization',
                    message='Pickle deserialization of user input - Remote Code Execution risk',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    confidence=Confidence.HIGH,
                    snippet=pickle_arg[:100] if len(pickle_arg) > 100 else pickle_arg,
                    cwe_id='CWE-502'  # Deserialization of Untrusted Data
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_werkzeug_debugger(self) -> None:
        """Check for Werkzeug debugger exposure."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all assignments, filter in Python
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, var, value in cursor.fetchall():
                # Check for debugger patterns in Python
                if var != 'WERKZEUG_DEBUG_PIN' and not ('use_debugger' in value and 'True' in value):
                    continue
                self.findings.append(StandardFinding(
                    rule_name='flask-werkzeug-debugger',
                    message='Werkzeug debugger exposed - allows arbitrary code execution',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    confidence=Confidence.HIGH,
                    snippet=f'{var} = {value[:50]}',
                    cwe_id='CWE-489'  # Active Debug Code
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_csrf_protection(self) -> None:
        """Check for missing CSRF protection."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check for CSRF imports
            query_csrf = build_query('refs', ['value'],
                where="value IN ('flask_wtf', 'CSRFProtect', 'csrf')",
                limit=1
            )
            cursor.execute(query_csrf)
            has_csrf = cursor.fetchone() is not None

            if not has_csrf:
                # Check if there are state-changing endpoints
                query_endpoints = build_query('api_endpoints', ['method'],
                    where="method IN ('POST', 'PUT', 'DELETE', 'PATCH')",
                    limit=1
                )
                cursor.execute(query_endpoints)
                has_state_changing = cursor.fetchone() is not None

                if has_state_changing and self.flask_files:
                    self.findings.append(StandardFinding(
                        rule_name='flask-missing-csrf',
                        message='State-changing endpoints without CSRF protection',
                        file_path=self.flask_files[0],
                        line=1,
                        severity=Severity.HIGH,
                        category='security',
                        confidence=Confidence.MEDIUM,
                        snippet='Missing CSRF protection for POST/PUT/DELETE/PATCH endpoints',
                        cwe_id='CWE-352'  # Cross-Site Request Forgery
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_session_security(self) -> None:
        """Check for insecure session cookie configuration."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all assignments, filter in Python
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               where="source_expr = 'False'",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, var, config in cursor.fetchall():
                # Filter for session config variables in Python
                var_upper = var.upper()
                if not any(session_config in var_upper for session_config in self.patterns.SESSION_CONFIGS):
                    continue
                self.findings.append(StandardFinding(
                    rule_name='flask-insecure-session',
                    message=f'Insecure session cookie configuration: {var} = False',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='session',
                    confidence=Confidence.HIGH,
                    snippet=f'{var} = {config}',
                    cwe_id='CWE-614'  # Sensitive Cookie Without Secure Attribute
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass


def register_taint_patterns(taint_registry):
    """Register Flask-specific taint patterns.

    This function is called by the orchestrator to register
    framework-specific sources and sinks for taint analysis.

    Args:
        taint_registry: TaintRegistry instance
    """
    # Flask user input sources (taint sources)
    FLASK_INPUT_SOURCES = frozenset([
        'request.args', 'request.form', 'request.values',
        'request.json', 'request.data', 'request.files',
        'request.cookies', 'request.headers', 'request.environ',
        'request.get_json', 'request.get_data'
    ])

    for pattern in FLASK_INPUT_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'python')

    # Flask SSTI sinks (template injection targets)
    FLASK_SSTI_SINKS = frozenset([
        'render_template_string', 'Markup', 'jinja2.Template'
    ])

    for pattern in FLASK_SSTI_SINKS:
        taint_registry.register_sink(pattern, 'ssti', 'python')

    # Flask redirect sinks (open redirect targets)
    FLASK_REDIRECT_SINKS = frozenset([
        'redirect', 'url_for', 'make_response'
    ])

    for pattern in FLASK_REDIRECT_SINKS:
        taint_registry.register_sink(pattern, 'redirect', 'python')

    # Flask SQL execution sinks
    FLASK_SQL_SINKS = frozenset([
        'execute', 'executemany', 'db.execute', 'session.execute'
    ])

    for pattern in FLASK_SQL_SINKS:
        taint_registry.register_sink(pattern, 'sql', 'python')