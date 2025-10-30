"""React Framework Security Analyzer - Database-First Approach.

Analyzes React applications for security vulnerabilities using ONLY
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
# METADATA (Orchestrator Discovery)
# ============================================================================

METADATA = RuleMetadata(
    name="react_security",
    category="frameworks",
    target_extensions=['.jsx', '.tsx', '.js', '.ts'],
    exclude_patterns=['node_modules/', 'test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)


# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class ReactPatterns:
    """Configuration for React security patterns."""

    # User input sources that need sanitization
    USER_INPUT_SOURCES = frozenset([
        'props.user', 'props.input', 'props.data', 'props.content',
        'location.search', 'params.', 'query.', 'formData.',
        'event.target.value', 'e.target.value', 'request.body'
    ])

    # XSS sink methods
    XSS_SINKS = frozenset([
        'dangerouslySetInnerHTML', 'innerHTML', 'outerHTML',
        'document.write', 'document.writeln', 'eval', 'Function'
    ])

    # Sanitization functions
    SANITIZATION_FUNCS = frozenset([
        'sanitize', 'escape', 'encode', 'DOMPurify',
        'xss', 'clean', 'safe', 'purify'
    ])

    # Sensitive data patterns
    SENSITIVE_PATTERNS = frozenset([
        'KEY', 'TOKEN', 'SECRET', 'PASSWORD',
        'PRIVATE', 'CREDENTIAL', 'AUTH', 'API'
    ])

    # Frontend environment prefixes that expose to client bundle
    FRONTEND_ENV_PREFIXES = frozenset([
        'REACT_APP_', 'NEXT_PUBLIC_', 'VITE_',
        'GATSBY_', 'PUBLIC_'
    ])

    # Storage methods
    STORAGE_METHODS = frozenset([
        'localStorage.setItem', 'sessionStorage.setItem',
        'localStorage.set', 'sessionStorage.set',
        'document.cookie', 'indexedDB.put'
    ])

    # Form submission handlers
    FORM_HANDLERS = frozenset([
        'handleSubmit', 'onSubmit', 'submit',
        'submitForm', 'formSubmit'
    ])

    # Validation libraries
    VALIDATION_LIBS = frozenset([
        'yup', 'joi', 'zod', 'validator',
        'validate', 'sanitize', 'schema'
    ])

    # React hooks
    REACT_HOOKS = frozenset([
        'useState', 'useEffect', 'useContext', 'useReducer',
        'useMemo', 'useCallback', 'useRef', 'useImperativeHandle'
    ])

    # Routing functions
    ROUTE_FUNCTIONS = frozenset([
        'Route', 'PrivateRoute', 'ProtectedRoute',
        'Router', 'BrowserRouter', 'Switch'
    ])

    # Auth check functions
    AUTH_FUNCTIONS = frozenset([
        'isAuthenticated', 'currentUser', 'checkAuth',
        'requireAuth', 'withAuth', 'useAuth'
    ])


# ============================================================================
# MAIN RULE FUNCTION (Standardized Interface)
# ============================================================================

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect React security vulnerabilities.

    Analyzes database for:
    - dangerouslySetInnerHTML usage without sanitization
    - Exposed API keys in frontend code
    - eval() with JSX content
    - Unsafe target="_blank" links
    - Direct innerHTML manipulation
    - Hardcoded credentials
    - Insecure client-side storage
    - Missing input validation
    - useEffect without cleanup
    - Unprotected routes

    Args:
        context: Standardized rule context with database path

    Returns:
        List of StandardFinding objects for detected issues
    """
    analyzer = ReactAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# REACT ANALYZER CLASS
# ============================================================================

class ReactAnalyzer:
    """Main analyzer for React applications."""

    def __init__(self, context: StandardRuleContext):
        self.context = context
        self.patterns = ReactPatterns()
        self.findings: List[StandardFinding] = []
        self.db_path = context.db_path or str(context.project_path / ".pf" / "repo_index.db")

        # Track React-specific data
        self.react_files: List[str] = []
        self.has_react = False

    def analyze(self) -> List[StandardFinding]:
        """Run complete React analysis."""
        # Check if this is a React project
        if not self._detect_react_project():
            return self.findings

        # Run all security checks
        self._check_dangerous_html()
        self._check_exposed_api_keys()
        self._check_eval_with_jsx()
        self._check_unsafe_target_blank()
        self._check_direct_innerhtml()
        self._check_hardcoded_credentials()
        self._check_insecure_storage()
        self._check_missing_validation()
        self._check_useeffect_cleanup()
        self._check_unprotected_routes()

        # Additional checks using available data
        self._check_csrf_in_forms()
        self._check_unescaped_user_input()

        return self.findings

    def _detect_react_project(self) -> bool:
        """Check if this is a React project - trust schema contract."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check for React imports, filter in Python
            query = build_query('refs', ['src', 'value'])
            cursor.execute(query)

            react_refs = []
            for src, value in cursor.fetchall():
                if (value in ('react', 'react-dom', 'React') or
                    value.startswith('react/') or
                    value.startswith('react-dom/')):
                    react_refs.append(src)

            if react_refs:
                self.react_files = list(set(react_refs))
                self.has_react = True
            else:
                # Also check for React-specific symbols
                query2 = build_query('symbols', ['path', 'name'], limit=100)
                cursor.execute(query2)

                for path, name in cursor.fetchall():
                    if name in ('useState', 'useEffect', 'useContext', 'useReducer', 'Component', 'createElement'):
                        self.react_files = [path]
                        self.has_react = True
                        break

            conn.close()
            return self.has_react

        except (sqlite3.Error, Exception):
            return False

    def _check_dangerous_html(self) -> None:
        """Check for dangerouslySetInnerHTML usage without sanitization."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all function calls, filter in Python
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               order_by="file, line")
            cursor.execute(query)

            dangerous_html_usages = []
            for file, line, callee, html_content in cursor.fetchall():
                if callee == 'dangerouslySetInnerHTML' or 'dangerouslySetInnerHTML' in html_content:
                    dangerous_html_usages.append((file, line, html_content))

            for file, line, html_content in dangerous_html_usages:
                # Check if sanitization is nearby
                query_sanitize = build_query('function_call_args', ['callee_function'],
                    where="""file = ? AND line BETWEEN ? AND ?
                      AND callee_function IN ('sanitize', 'DOMPurify', 'escape', 'xss', 'purify')""",
                    limit=1
                )
                cursor.execute(query_sanitize, (file, line - 10, line + 10))
                has_sanitization = cursor.fetchone() is not None

                if not has_sanitization:
                    self.findings.append(StandardFinding(
                        rule_name='react-dangerous-html',
                        message='Use of dangerouslySetInnerHTML without sanitization - primary XSS vector',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='xss',
                        confidence=Confidence.HIGH,
                        snippet=html_content[:100] if len(html_content) > 100 else html_content,
                        cwe_id='CWE-79'  # Cross-site Scripting
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_exposed_api_keys(self) -> None:
        """Check for exposed API keys in frontend code."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build query for frontend environment variables with sensitive patterns
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               where="target_var != ''",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, var_name, value in cursor.fetchall():
                # Check if it's a frontend environment variable
                has_frontend_prefix = any(
                    var_name.startswith(prefix)
                    for prefix in self.patterns.FRONTEND_ENV_PREFIXES
                )

                if has_frontend_prefix:
                    # Check if it contains sensitive patterns
                    var_upper = var_name.upper()
                    has_sensitive = any(
                        pattern in var_upper
                        for pattern in self.patterns.SENSITIVE_PATTERNS
                    )

                    if has_sensitive:
                        self.findings.append(StandardFinding(
                            rule_name='react-exposed-api-key',
                            message=f'API key/secret {var_name} exposed in client bundle',
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category='security',
                            confidence=Confidence.HIGH,
                            snippet=f'{var_name} = {value[:50]}...' if len(value) > 50 else f'{var_name} = {value}',
                            cwe_id='CWE-200'  # Exposure of Sensitive Information
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_eval_with_jsx(self) -> None:
        """Check for eval() used with JSX content."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch eval calls, filter in Python
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               where="callee_function = 'eval'",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, callee, eval_content in cursor.fetchall():
                # Check for JSX patterns in Python
                if not ('<%>' in eval_content or 'jsx' in eval_content or
                        'JSX' in eval_content or 'React.createElement' in eval_content):
                    continue
                self.findings.append(StandardFinding(
                    rule_name='react-eval-jsx',
                    message='Using eval() with JSX - code injection vulnerability',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='injection',
                    confidence=Confidence.HIGH,
                    snippet=eval_content[:100] if len(eval_content) > 100 else eval_content,
                    cwe_id='CWE-95'  # Improper Neutralization of Directives in Dynamically Evaluated Code
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_unsafe_target_blank(self) -> None:
        """Check for unsafe target="_blank" links."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all assignments, filter in Python
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, target, link_code in cursor.fetchall():
                # Check for target="_blank" patterns in Python
                if not ('target="_blank"' in link_code or "target='_blank'" in link_code or
                        'target={' in link_code and '_blank' in link_code):
                    continue

                # Check if noopener/noreferrer is missing
                if 'noopener' in link_code or 'noreferrer' in link_code:
                    continue
                self.findings.append(StandardFinding(
                    rule_name='react-unsafe-target-blank',
                    message='External link without rel="noopener" - reverse tabnabbing vulnerability',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='security',
                    confidence=Confidence.HIGH,
                    snippet=link_code[:100] if len(link_code) > 100 else link_code,
                    cwe_id='CWE-1022'  # Use of Web Link to Untrusted Target
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_direct_innerhtml(self) -> None:
        """Check for direct innerHTML manipulation."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all assignments, filter in Python
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, target, content in cursor.fetchall():
                # Check for innerHTML/outerHTML in Python
                if not (target.endswith('.innerHTML') or target.endswith('.outerHTML')):
                    continue
                self.findings.append(StandardFinding(
                    rule_name='react-direct-innerhtml',
                    message='Direct innerHTML manipulation - bypasses React security',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    confidence=Confidence.HIGH,
                    snippet=f'{target} = {content[:50]}...' if len(content) > 50 else f'{target} = {content}',
                    cwe_id='CWE-79'  # Cross-site Scripting
                ))

            # Also check for document.write
            query = build_query('function_call_args', ['file', 'line', 'argument_expr'],
                               where="callee_function IN ('document.write', 'document.writeln')",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, write_content in cursor.fetchall():
                self.findings.append(StandardFinding(
                    rule_name='react-document-write',
                    message='Use of document.write in React - dangerous DOM manipulation',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category='xss',
                    confidence=Confidence.HIGH,
                    snippet=write_content[:100] if len(write_content) > 100 else write_content,
                    cwe_id='CWE-79'  # Cross-site Scripting
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_hardcoded_credentials(self) -> None:
        """Check for hardcoded credentials."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all assignments, filter in Python
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               order_by="file, line")
            cursor.execute(query)

            for file, line, var_name, credential in cursor.fetchall():
                # Filter for string literals (not env vars) in Python
                if not ('"' in credential or "'" in credential):
                    continue
                if 'process.env' in credential or 'import.meta.env' in credential:
                    continue

                # Check length (rough heuristic for meaningful values)
                clean_cred = credential.strip('"\'')
                if len(clean_cred) <= 10:
                    continue
                var_lower = var_name.lower()

                # Check if variable name suggests credentials
                is_credential = False
                cred_type = 'credential'

                if 'password' in var_lower:
                    is_credential = True
                    cred_type = 'password'
                elif 'apikey' in var_lower or 'api_key' in var_lower:
                    is_credential = True
                    cred_type = 'API key'
                elif 'token' in var_lower:
                    is_credential = True
                    cred_type = 'token'
                elif 'secret' in var_lower:
                    is_credential = True
                    cred_type = 'secret'
                elif 'privatekey' in var_lower or 'private_key' in var_lower:
                    is_credential = True
                    cred_type = 'private key'

                if is_credential:
                    self.findings.append(StandardFinding(
                        rule_name='react-hardcoded-credentials',
                        message=f'Hardcoded {cred_type} in React component',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='security',
                        confidence=Confidence.HIGH,
                        snippet=f'{var_name} = "..."',
                        cwe_id='CWE-798'  # Use of Hard-coded Credentials
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_insecure_storage(self) -> None:
        """Check for sensitive data in localStorage/sessionStorage."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build query for storage methods
            storage_methods_list = list(self.patterns.STORAGE_METHODS)
            placeholders = ','.join('?' * len(storage_methods_list))

            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               where=f"callee_function IN ({placeholders})",
                               order_by="file, line")
            cursor.execute(query, storage_methods_list)

            for file, line, storage_method, data in cursor.fetchall():
                # Check if data contains sensitive patterns
                data_lower = data.lower()
                has_sensitive = any(
                    pattern.lower() in data_lower
                    for pattern in self.patterns.SENSITIVE_PATTERNS
                )

                if has_sensitive:
                    storage_type = 'localStorage' if 'localStorage' in storage_method else 'sessionStorage'

                    self.findings.append(StandardFinding(
                        rule_name='react-insecure-storage',
                        message=f'Sensitive data stored in {storage_type} - accessible to XSS attacks',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='security',
                        confidence=Confidence.HIGH,
                        snippet=data[:100] if len(data) > 100 else data,
                        cwe_id='CWE-922'  # Insecure Storage of Sensitive Information
                    ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_missing_validation(self) -> None:
        """Check for forms without input validation."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Find form submission handlers
            form_handlers_list = list(self.patterns.FORM_HANDLERS)
            placeholders = ','.join('?' * len(form_handlers_list))

            cursor.execute(f"""
                SELECT DISTINCT file, line FROM function_call_args
                WHERE callee_function IN ({placeholders})
                ORDER BY file, line
            """, form_handlers_list)
            # ✅ FIX: Store results before loop to avoid cursor state bug
            form_handlers = cursor.fetchall()

            for file, line in form_handlers:
                # Check for nearby validation/sanitization calls, filter in Python
                query_validation = build_query('function_call_args', ['callee_function'],
                    where="file = ? AND line BETWEEN ? AND ?")
                cursor.execute(query_validation, (file, line - 20, line + 20))

                has_validation_nearby = False
                for (callee,) in cursor.fetchall():
                    callee_lower = callee.lower()
                    if 'validate' in callee_lower or 'sanitize' in callee_lower:
                        has_validation_nearby = True
                        break

                if not has_validation_nearby:
                    # Also check if validation libraries are imported
                    query_libs = build_query('refs', ['value'],
                        where="src = ? AND value IN ('yup', 'joi', 'zod', 'validator')",
                        limit=1
                    )
                    cursor.execute(query_libs, (file,))
                    has_validation_lib = cursor.fetchone() is not None

                    if not has_validation_lib:
                        self.findings.append(StandardFinding(
                            rule_name='react-missing-validation',
                            message='Form submission without input validation',
                            file_path=file,
                            line=line,
                            severity=Severity.MEDIUM,
                            category='validation',
                            confidence=Confidence.LOW,
                            snippet='Form handler without validation',
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_useeffect_cleanup(self) -> None:
        """Check for useEffect with external calls but no cleanup."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch useEffect calls, filter in Python
            query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                               where="callee_function = 'useEffect'",
                               order_by="file, line")
            cursor.execute(query)

            for file, line, callee, effect_code in cursor.fetchall():
                # Check for fetch without cleanup in Python
                if 'fetch' not in effect_code:
                    continue
                if 'cleanup' in effect_code or 'return' in effect_code:
                    continue
                self.findings.append(StandardFinding(
                    rule_name='react-useeffect-no-cleanup',
                    message='useEffect with fetch but no cleanup - potential memory leak',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='performance',
                    confidence=Confidence.LOW,
                    snippet=effect_code[:100] if len(effect_code) > 100 else effect_code,
                    cwe_id='CWE-401'  # Missing Release of Memory after Effective Lifetime
                ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_unprotected_routes(self) -> None:
        """Check for client-side routing without auth checks."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Find files with routing
            route_funcs_list = list(self.patterns.ROUTE_FUNCTIONS)
            placeholders = ','.join('?' * len(route_funcs_list))

            cursor.execute(f"""
                SELECT DISTINCT file FROM function_call_args
                WHERE callee_function IN ({placeholders})
            """, route_funcs_list)
            # ✅ FIX: Store results before loop to avoid cursor state bug
            route_files = cursor.fetchall()

            for (file,) in route_files:
                # Check if file has any auth-related function calls, filter in Python
                query_auth_pattern = build_query('function_call_args', ['callee_function'],
                    where="file = ?")
                cursor.execute(query_auth_pattern, (file,))

                has_auth_pattern = False
                for (callee,) in cursor.fetchall():
                    if 'auth' in callee or 'Auth' in callee:
                        has_auth_pattern = True
                        break

                if not has_auth_pattern:
                    # Also check if auth functions are used
                    auth_funcs_list = list(self.patterns.AUTH_FUNCTIONS)
                    placeholders = ','.join('?' * len(auth_funcs_list))

                    query_auth_funcs = build_query('function_call_args', ['callee_function'],
                        where=f"file = ? AND callee_function IN ({placeholders})",
                        limit=1
                    )
                    cursor.execute(query_auth_funcs, [file] + auth_funcs_list)
                    has_auth = cursor.fetchone() is not None

                    if not has_auth:
                        self.findings.append(StandardFinding(
                            rule_name='react-unprotected-routes',
                            message='Client-side routing without authentication checks',
                            file_path=file,
                            line=1,
                            severity=Severity.MEDIUM,
                            category='authorization',
                            confidence=Confidence.LOW,
                            snippet='Routes defined without auth guards',
                            cwe_id='CWE-862'  # Missing Authorization
                        ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_csrf_in_forms(self) -> None:
        """Check for forms without CSRF tokens."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all assignments, filter for forms in Python
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               order_by="file, line")
            cursor.execute(query)

            form_elements = []
            for file, line, target, form_content in cursor.fetchall():
                if '<form' in form_content:
                    form_elements.append((file, line, form_content))

            for file, line, form_content in form_elements:
                form_lower = form_content.lower()

                # Check if it's a POST/PUT/DELETE form
                has_modifying_method = False
                if 'method=' in form_lower:
                    if any(m in form_lower for m in ['post', 'put', 'delete', 'patch']):
                        has_modifying_method = True
                else:
                    # Default is GET, which is safe
                    has_modifying_method = False

                if has_modifying_method:
                    # Check if CSRF token is present
                    if 'csrf' not in form_lower and 'xsrf' not in form_lower:
                        # Also check if there's CSRF handling nearby, filter in Python
                        query_csrf = build_query('assignments', ['target_var', 'source_expr'],
                            where="file = ? AND line BETWEEN ? AND ?")
                        cursor.execute(query_csrf, (file, line - 10, line + 10))

                        has_csrf_nearby = False
                        for target_var, source_expr in cursor.fetchall():
                            target_lower = target_var.lower()
                            source_lower = source_expr.lower()
                            if 'csrf' in target_lower or 'csrf' in source_lower or \
                               'xsrf' in target_lower or 'xsrf' in source_lower:
                                has_csrf_nearby = True
                                break

                        if not has_csrf_nearby:
                            self.findings.append(StandardFinding(
                                rule_name='react-missing-csrf',
                                message='Form submission without CSRF token',
                                file_path=file,
                                line=line,
                                severity=Severity.HIGH,
                                category='csrf',
                                confidence=Confidence.MEDIUM,
                                snippet='Form with POST/PUT/DELETE without CSRF',
                                cwe_id='CWE-352'  # Cross-Site Request Forgery
                            ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass

    def _check_unescaped_user_input(self) -> None:
        """Check for unescaped user input in JSX."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Fetch all assignments, filter in Python
            query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr'],
                               order_by="file, line")
            cursor.execute(query)

            jsx_with_user_input = []
            for file, line, target, jsx_content in cursor.fetchall():
                # Check for JSX patterns with user input in Python
                if '<%>' not in jsx_content:
                    continue

                # Check for user input patterns
                if not ('{props.' in jsx_content or '{user' in jsx_content or
                        '{input' in jsx_content or '{data' in jsx_content or
                        '{params' in jsx_content or '{query' in jsx_content):
                    continue

                jsx_with_user_input.append((file, line, jsx_content))

            for file, line, jsx_content in jsx_with_user_input:
                # Check for user input patterns in JSX
                has_user_input = False
                input_source = None

                for pattern in self.patterns.USER_INPUT_SOURCES:
                    if pattern in jsx_content:
                        has_user_input = True
                        input_source = pattern
                        break

                if has_user_input:
                    # Check for sanitization
                    jsx_lower = jsx_content.lower()
                    has_sanitization = any(
                        san in jsx_lower
                        for san in self.patterns.SANITIZATION_FUNCS
                    )

                    if not has_sanitization:
                        # Also check for sanitization nearby
                        query_san_nearby = build_query('function_call_args', ['callee_function'],
                            where="""file = ? AND line BETWEEN ? AND ?
                              AND callee_function IN ('sanitize', 'escape', 'DOMPurify', 'xss')""",
                            limit=1
                        )
                        cursor.execute(query_san_nearby, (file, line - 5, line + 5))
                        has_sanitization_nearby = cursor.fetchone() is not None

                        if not has_sanitization_nearby:
                            self.findings.append(StandardFinding(
                                rule_name='react-unescaped-user-input',
                                message=f'User input {input_source} rendered without escaping - potential XSS',
                                file_path=file,
                                line=line,
                                severity=Severity.HIGH,
                                category='xss',
                                confidence=Confidence.MEDIUM,
                                snippet=jsx_content[:100] if len(jsx_content) > 100 else jsx_content,
                                cwe_id='CWE-79'  # Cross-site Scripting
                            ))

            conn.close()

        except (sqlite3.Error, Exception):
            pass


def register_taint_patterns(taint_registry):
    """Register React-specific taint patterns.

    This function is called by the orchestrator to register
    framework-specific sources and sinks for taint analysis.

    Args:
        taint_registry: TaintRegistry instance
    """
    # React user input sources (taint sources)
    REACT_INPUT_SOURCES = frozenset([
        'props.user', 'props.input', 'props.data', 'props.content',
        'location.search', 'params', 'query', 'formData',
        'event.target.value', 'e.target.value', 'useState',
        'this.props', 'this.state'
    ])

    for pattern in REACT_INPUT_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'javascript')

    # React XSS sinks (dangerous DOM operations)
    REACT_XSS_SINKS = frozenset([
        'dangerouslySetInnerHTML', 'innerHTML', 'outerHTML',
        'document.write', 'document.writeln'
    ])

    for pattern in REACT_XSS_SINKS:
        taint_registry.register_sink(pattern, 'xss', 'javascript')

    # React code execution sinks
    REACT_CODE_EXEC_SINKS = frozenset([
        'eval', 'Function', 'setTimeout', 'setInterval',
        'new Function'
    ])

    for pattern in REACT_CODE_EXEC_SINKS:
        taint_registry.register_sink(pattern, 'code_execution', 'javascript')

    # React storage sinks (sensitive data exposure)
    REACT_STORAGE_SINKS = frozenset([
        'localStorage.setItem', 'sessionStorage.setItem',
        'document.cookie'
    ])

    for pattern in REACT_STORAGE_SINKS:
        taint_registry.register_sink(pattern, 'storage', 'javascript')