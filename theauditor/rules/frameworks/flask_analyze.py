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

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
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
        self.findings: List[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")

        # Track Flask-specific data
        self.flask_files: List[str] = []

    def analyze(self) -> List[StandardFinding]:
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

            query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                               where="callee_function LIKE '%.run' AND argument_expr LIKE '%debug%True%'",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, args in cursor.fetchall():
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

            # Build WHERE clause for secret variables using schema-compliant approach
            secret_conditions = " OR ".join([f"target_var LIKE '%{var}%'" for var in self.patterns.SECRET_VARS])
            where_clause = f"""({secret_conditions})
                  AND source_expr LIKE '"%"'
                  AND source_expr NOT LIKE '%environ%'
                  AND source_expr NOT LIKE '%getenv%'"""

            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               where=where_clause,
                               order_by="file, line")
            cursor.execute(query)

            for file, line, var_name, secret_value in cursor.fetchall():
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

            # Complex EXISTS/NOT EXISTS correlated subquery - build_query() supports this
            query = build_query('function_call_args', ['DISTINCT file', 'line'],
                               where="""callee_function LIKE '%.save'
                                 AND EXISTS (
                                     SELECT 1 FROM function_call_args f2
                                     WHERE f2.file = function_call_args.file
                                       AND f2.line BETWEEN function_call_args.line - 10 AND function_call_args.line
                                       AND f2.argument_expr LIKE '%request.files%'
                                 )
                                 AND NOT EXISTS (
                                     SELECT 1 FROM function_call_args f3
                                     WHERE f3.file = function_call_args.file
                                       AND f3.line BETWEEN function_call_args.line - 10 AND function_call_args.line + 10
                                       AND f3.callee_function IN ('secure_filename', 'validate', 'allowed')
                                 )""",
                               order_by="file, line")
            cursor.execute(query)

            for file, line in cursor.fetchall():
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

            # Query sql_queries table with schema-compliant query
            query = build_query('sql_queries', ['file_path', 'line_number', 'query_text'],
                               where="""(query_text LIKE '%' || '%' || '%'
                                        OR query_text LIKE '%.format(%'
                                        OR query_text LIKE '%f"%'
                                        OR query_text LIKE "%f'%")""",
                               order_by="file_path, line_number")
            cursor.execute(query)

            for file, line, query_text in cursor.fetchall():
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

            query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                               where="""callee_function = 'redirect'
                                        AND (argument_expr LIKE '%request.args.get%'
                                             OR argument_expr LIKE '%request.values.get%'
                                             OR argument_expr LIKE '%request.form.get%')""",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, redirect_arg in cursor.fetchall():
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

            query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                               where="callee_function = 'eval' AND argument_expr LIKE '%request.%'",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, eval_arg in cursor.fetchall():
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

            # Check assignments
            query = build_query('assignments', ['file', 'line', 'source_expr'],
                               where="""(target_var LIKE '%CORS%'
                                        OR target_var LIKE '%Access-Control-Allow-Origin%')
                                      AND source_expr LIKE '%*%'""",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, cors_config in cursor.fetchall():
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

            # Check function calls
            query2 = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                                where="callee_function = 'CORS' AND argument_expr LIKE '%*%'",
                                order_by="file, line")
            cursor.execute(query2)

            for file, line, cors_arg in cursor.fetchall():
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

            query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                               where="""callee_function IN ('pickle.loads', 'loads', 'pickle.load', 'load')
                                        AND argument_expr LIKE '%request.%'""",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, pickle_arg in cursor.fetchall():
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

            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               where="target_var = 'WERKZEUG_DEBUG_PIN' OR source_expr LIKE '%use_debugger%True%'",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, var, value in cursor.fetchall():
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
            query = build_query('refs', ['COUNT(*)'],
                               where="value IN ('flask_wtf', 'CSRFProtect', 'csrf')")
            cursor.execute(query)
            has_csrf = cursor.fetchone()[0] > 0

            if not has_csrf:
                # Check if there are state-changing endpoints
                query2 = build_query('api_endpoints', ['COUNT(*)'],
                                    where="method IN ('POST', 'PUT', 'DELETE', 'PATCH')")
                cursor.execute(query2)
                has_state_changing = cursor.fetchone()[0] > 0

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

            # Build WHERE clause for session configs using schema-compliant approach
            config_conditions = " OR ".join([f"target_var LIKE '%{config}%'" for config in self.patterns.SESSION_CONFIGS])
            where_clause = f"({config_conditions}) AND source_expr = 'False'"

            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               where=where_clause,
                               order_by="file, line")
            cursor.execute(query)

            for file, line, var, config in cursor.fetchall():
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