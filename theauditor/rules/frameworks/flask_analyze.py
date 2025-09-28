"""Golden Standard Flask Security Analyzer.

Detects Flask security misconfigurations via database analysis.
Demonstrates database-aware rule pattern using finite pattern matching.

MIGRATION STATUS: Golden Standard Implementation [2024-12-29]
Signature: context: StandardRuleContext -> List[StandardFinding]
"""

import json
import sqlite3
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass
from pathlib import Path

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


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

            # Check if this is a Flask project
            cursor.execute("""
                SELECT DISTINCT src FROM refs
                WHERE value IN ('flask', 'Flask')
            """)
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

            cursor.execute("""
                SELECT file, line, argument_expr
                FROM function_call_args
                WHERE callee_function = 'render_template_string'
                ORDER BY file, line
            """)

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
                    snippet=template_arg[:100] if len(template_arg) > 100 else template_arg,
                    fix_suggestion='Use render_template() with static template files instead'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_markup_xss(self) -> None:
        """Check for XSS via Markup()."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, line, argument_expr
                FROM function_call_args
                WHERE callee_function = 'Markup'
                ORDER BY file, line
            """)

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
                        snippet=markup_content[:100] if len(markup_content) > 100 else markup_content,
                        fix_suggestion='Sanitize user input before using Markup() or use escape()'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_debug_mode(self) -> None:
        """Check for debug mode enabled."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, line, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE '%.run'
                  AND argument_expr LIKE '%debug%True%'
                ORDER BY file, line
            """)

            for file, line, args in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='flask-debug-mode-enabled',
                    message='Flask debug mode enabled - exposes interactive debugger',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    snippet=args[:100] if len(args) > 100 else args,
                    fix_suggestion='Set debug=False in production environments'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_hardcoded_secrets(self) -> None:
        """Check for hardcoded secret keys."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build query for secret variables
            secret_conditions = " OR ".join([f"target_var LIKE '%{var}%'" for var in self.patterns.SECRET_VARS])

            cursor.execute(f"""
                SELECT file, line, target_var, source_expr
                FROM assignments
                WHERE ({secret_conditions})
                  AND source_expr LIKE '"%"'
                  AND source_expr NOT LIKE '%environ%'
                  AND source_expr NOT LIKE '%getenv%'
                ORDER BY file, line
            """)

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
                        snippet=f'{var_name} = {secret_value[:30]}...',
                        fix_suggestion='Use environment variables and generate strong random secrets'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_unsafe_file_uploads(self) -> None:
        """Check for unsafe file upload operations."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT DISTINCT f1.file, f1.line
                FROM function_call_args f1
                WHERE f1.callee_function LIKE '%.save'
                  AND EXISTS (
                      SELECT 1 FROM function_call_args f2
                      WHERE f2.file = f1.file
                        AND f2.line BETWEEN f1.line - 10 AND f1.line
                        AND f2.argument_expr LIKE '%request.files%'
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM function_call_args f3
                      WHERE f3.file = f1.file
                        AND f3.line BETWEEN f1.line - 10 AND f1.line + 10
                        AND (f3.callee_function IN ('secure_filename', 'validate', 'allowed'))
                  )
                ORDER BY f1.file, f1.line
            """)

            for file, line in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='flask-unsafe-file-upload',
                    message='File upload without validation - malicious file upload risk',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet='request.files[...].save() without secure_filename()',
                    fix_suggestion='Use secure_filename() and validate file extensions'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_sql_injection(self) -> None:
        """Check for SQL injection risks."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check sql_queries table if it exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='sql_queries'
            """)

            if cursor.fetchone():
                cursor.execute("""
                    SELECT file_path, line_number, query_text
                    FROM sql_queries
                    WHERE (query_text LIKE '%' || '%' || '%'
                           OR query_text LIKE '%.format(%'
                           OR query_text LIKE '%f"%'
                           OR query_text LIKE "%f'%")
                    ORDER BY file_path, line_number
                """)

                for file, line, query in cursor.fetchall():
                    self.findings.append(StandardFinding(
                        rule_name='flask-sql-injection-risk',
                        message='String formatting in SQL query - SQL injection vulnerability',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='injection',
                        snippet=query[:100] if len(query) > 100 else query,
                        fix_suggestion='Use parameterized queries with ? or :param placeholders'
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_open_redirects(self) -> None:
        """Check for open redirect vulnerabilities."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, line, argument_expr
                FROM function_call_args
                WHERE callee_function = 'redirect'
                  AND (argument_expr LIKE '%request.args.get%'
                       OR argument_expr LIKE '%request.values.get%'
                       OR argument_expr LIKE '%request.form.get%')
                ORDER BY file, line
            """)

            for file, line, redirect_arg in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='flask-unsafe-redirect',
                    message='Unvalidated redirect from user input - open redirect vulnerability',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=redirect_arg[:100] if len(redirect_arg) > 100 else redirect_arg,
                    fix_suggestion='Validate redirect URLs against a whitelist'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_eval_usage(self) -> None:
        """Check for eval usage with user input."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, line, argument_expr
                FROM function_call_args
                WHERE callee_function = 'eval'
                  AND argument_expr LIKE '%request.%'
                ORDER BY file, line
            """)

            for file, line, eval_arg in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='flask-eval-usage',
                    message='Use of eval with user input - code injection vulnerability',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    snippet=eval_arg[:100] if len(eval_arg) > 100 else eval_arg,
                    fix_suggestion='Never use eval() with user input - use ast.literal_eval() for safe evaluation'
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
            cursor.execute("""
                SELECT file, line, source_expr
                FROM assignments
                WHERE (target_var LIKE '%CORS%'
                       OR target_var LIKE '%Access-Control-Allow-Origin%')
                  AND source_expr LIKE '%*%'
                ORDER BY file, line
            """)

            for file, line, cors_config in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='flask-cors-wildcard',
                    message='CORS with wildcard origin - allows any domain access',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=cors_config[:100] if len(cors_config) > 100 else cors_config,
                    fix_suggestion='Specify explicit allowed origins instead of wildcard'
                ))

            # Check function calls
            cursor.execute("""
                SELECT file, line, argument_expr
                FROM function_call_args
                WHERE callee_function = 'CORS'
                  AND argument_expr LIKE '%*%'
                ORDER BY file, line
            """)

            for file, line, cors_arg in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='flask-cors-wildcard',
                    message='CORS with wildcard origin - allows any domain access',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='security',
                    snippet=cors_arg[:100] if len(cors_arg) > 100 else cors_arg,
                    fix_suggestion='Specify explicit allowed origins instead of wildcard'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_unsafe_deserialization(self) -> None:
        """Check for unsafe pickle deserialization."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, line, argument_expr
                FROM function_call_args
                WHERE callee_function IN ('pickle.loads', 'loads', 'pickle.load', 'load')
                  AND argument_expr LIKE '%request.%'
                ORDER BY file, line
            """)

            for file, line, pickle_arg in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='flask-unsafe-deserialization',
                    message='Pickle deserialization of user input - Remote Code Execution risk',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    snippet=pickle_arg[:100] if len(pickle_arg) > 100 else pickle_arg,
                    fix_suggestion='Never unpickle untrusted data - use JSON instead'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_werkzeug_debugger(self) -> None:
        """Check for Werkzeug debugger exposure."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT file, line, target_var, source_expr
                FROM assignments
                WHERE target_var = 'WERKZEUG_DEBUG_PIN'
                   OR source_expr LIKE '%use_debugger%True%'
                ORDER BY file, line
            """)

            for file, line, var, value in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='flask-werkzeug-debugger',
                    message='Werkzeug debugger exposed - allows arbitrary code execution',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='security',
                    snippet=f'{var} = {value[:50]}',
                    fix_suggestion='Disable Werkzeug debugger in production'
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
            cursor.execute("""
                SELECT COUNT(*) FROM refs
                WHERE value IN ('flask_wtf', 'CSRFProtect', 'csrf')
            """)
            has_csrf = cursor.fetchone()[0] > 0

            if not has_csrf:
                # Check if there are state-changing endpoints
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='api_endpoints'
                """)

                if cursor.fetchone():
                    cursor.execute("""
                        SELECT COUNT(*) FROM api_endpoints
                        WHERE method IN ('POST', 'PUT', 'DELETE', 'PATCH')
                    """)
                    has_state_changing = cursor.fetchone()[0] > 0

                    if has_state_changing and self.flask_files:
                        self.findings.append(StandardFinding(
                            rule_name='flask-missing-csrf',
                            message='State-changing endpoints without CSRF protection',
                            file_path=self.flask_files[0],
                            line=1,
                            severity=Severity.HIGH,
                            category='security',
                            snippet='Missing CSRF protection for POST/PUT/DELETE/PATCH endpoints',
                            fix_suggestion='Use Flask-WTF for CSRF protection: from flask_wtf.csrf import CSRFProtect'
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_session_security(self) -> None:
        """Check for insecure session cookie configuration."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build query for session configs
            config_conditions = " OR ".join([f"target_var LIKE '%{config}%'" for config in self.patterns.SESSION_CONFIGS])

            cursor.execute(f"""
                SELECT file, line, target_var, source_expr
                FROM assignments
                WHERE ({config_conditions})
                  AND source_expr = 'False'
                ORDER BY file, line
            """)

            for file, line, var, config in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='flask-insecure-session',
                    message=f'Insecure session cookie configuration: {var} = False',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='session',
                    snippet=f'{var} = {config}',
                    fix_suggestion='Set SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax"'
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass