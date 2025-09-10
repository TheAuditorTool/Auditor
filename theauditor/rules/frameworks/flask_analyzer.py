"""Flask framework-specific security analyzer using AST."""

import ast
from typing import Any, Dict, List


def find_flask_issues(tree: Any, file_path: str = None, content: str = None, **kwargs) -> List[Dict[str, Any]]:
    """Find Flask security issues using AST analysis.
    
    Args:
        tree: AST tree from parser
        file_path: Path to the file being analyzed
        content: File content
        **kwargs: Additional context
        
    Returns:
        List of security findings
    """
    findings = []
    
    if not content:
        return findings
    
    # Check if this is a Flask file
    is_flask = (
        'from flask' in content or
        'import flask' in content or
        'Flask(__name__)' in content or
        '@app.route' in content or
        'render_template' in content
    )
    
    if not is_flask:
        return findings
    
    # For Python files, use native AST if available
    if isinstance(tree, ast.AST):
        python_tree = tree
    else:
        try:
            python_tree = ast.parse(content)
        except SyntaxError:
            python_tree = None
    
    # Pattern 1: SSTI via render_template_string
    ssti_risks = _find_ssti_risks(content)
    for line_num in ssti_risks:
        findings.append({
            "pattern_name": "flask-ssti-render-template-string",
            "type": "FLASK_SSTI",
            "message": "Use of render_template_string - Server-Side Template Injection risk",
            "file": file_path,
            "line": line_num,
            "severity": "critical",
            "category": "injection"
        })
    
    # Pattern 2: Markup XSS
    markup_xss = _find_markup_xss(content)
    for line_num in markup_xss:
        findings.append({
            "pattern_name": "flask-markup-xss",
            "type": "FLASK_MARKUP_XSS",
            "message": "Use of Markup() - XSS risk if content is from user input",
            "file": file_path,
            "line": line_num,
            "severity": "high",
            "category": "xss"
        })
    
    # Pattern 3: Debug mode enabled
    if _has_debug_mode(content):
        findings.append({
            "pattern_name": "flask-debug-mode-enabled",
            "type": "FLASK_DEBUG_MODE",
            "message": "Flask debug mode enabled - exposes interactive debugger",
            "file": file_path,
            "line": 1,
            "severity": "critical",
            "category": "security"
        })
    
    # Pattern 4: Hardcoded secret key
    secret_keys = _find_hardcoded_secrets(content)
    for line_num in secret_keys:
        findings.append({
            "pattern_name": "flask-secret-key-exposed",
            "type": "FLASK_SECRET_KEY",
            "message": "Hardcoded SECRET_KEY - compromises session security",
            "file": file_path,
            "line": line_num,
            "severity": "critical",
            "category": "security"
        })
    
    # Pattern 5: Unsafe file upload
    unsafe_uploads = _find_unsafe_file_uploads(content)
    for line_num in unsafe_uploads:
        findings.append({
            "pattern_name": "flask-unsafe-file-upload",
            "type": "FLASK_UNSAFE_UPLOAD",
            "message": "File upload without validation - malicious file upload risk",
            "file": file_path,
            "line": line_num,
            "severity": "high",
            "category": "security"
        })
    
    # Pattern 6: SQL injection risk
    sql_injections = _find_sql_injection_risks(content)
    for line_num in sql_injections:
        findings.append({
            "pattern_name": "flask-sql-injection-risk",
            "type": "FLASK_SQL_INJECTION",
            "message": "String formatting in SQL query - SQL injection vulnerability",
            "file": file_path,
            "line": line_num,
            "severity": "critical",
            "category": "injection"
        })
    
    # Pattern 7: Open redirect
    open_redirects = _find_open_redirects(content)
    for line_num in open_redirects:
        findings.append({
            "pattern_name": "flask-unsafe-redirect",
            "type": "FLASK_OPEN_REDIRECT",
            "message": "Unvalidated redirect - open redirect vulnerability",
            "file": file_path,
            "line": line_num,
            "severity": "high",
            "category": "security"
        })
    
    # Pattern 8: Eval usage
    eval_usage = _find_eval_usage(content)
    for line_num in eval_usage:
        findings.append({
            "pattern_name": "flask-eval-usage",
            "type": "FLASK_EVAL",
            "message": "Use of eval with user input - code injection vulnerability",
            "file": file_path,
            "line": line_num,
            "severity": "critical",
            "category": "injection"
        })
    
    # Pattern 9: CORS wildcard
    if _has_cors_wildcard(content):
        findings.append({
            "pattern_name": "flask-cors-wildcard",
            "type": "FLASK_CORS_WILDCARD",
            "message": "CORS with wildcard origin - allows any domain access",
            "file": file_path,
            "line": 1,
            "severity": "high",
            "category": "security"
        })
    
    # Pattern 10: Unsafe deserialization
    unsafe_pickle = _find_unsafe_deserialization(content)
    for line_num in unsafe_pickle:
        findings.append({
            "pattern_name": "flask-unsafe-deserialization",
            "type": "FLASK_UNSAFE_PICKLE",
            "message": "Pickle deserialization of user input - RCE risk",
            "file": file_path,
            "line": line_num,
            "severity": "critical",
            "category": "injection"
        })
    
    # Pattern 11: HTML in JSON
    html_in_json = _find_html_in_json(content)
    for line_num in html_in_json:
        findings.append({
            "pattern_name": "flask-jsonify-html",
            "type": "FLASK_JSONIFY_HTML",
            "message": "HTML in JSON response - potential XSS if rendered",
            "file": file_path,
            "line": line_num,
            "severity": "medium",
            "category": "xss"
        })
    
    # Pattern 12: Werkzeug debugger
    if _has_werkzeug_debugger(content):
        findings.append({
            "pattern_name": "flask-werkzeug-debugger",
            "type": "FLASK_WERKZEUG_DEBUG",
            "message": "Werkzeug debugger exposed - allows arbitrary code execution",
            "file": file_path,
            "line": 1,
            "severity": "critical",
            "category": "security"
        })
    
    return findings


def register_taint_patterns(taint_registry):
    """Register Flask-specific taint patterns."""
    
    # Flask response sinks
    FLASK_SINKS = [
        "render_template",
        "render_template_string",
        "jsonify",
        "make_response",
        "redirect",
        "send_file",
        "send_from_directory",
        "Markup",
        "flash"
    ]
    
    for pattern in FLASK_SINKS:
        taint_registry.register_sink(pattern, "response", "python")
    
    # Flask input sources
    FLASK_SOURCES = [
        "request.args",
        "request.form",
        "request.values",
        "request.json",
        "request.data",
        "request.files",
        "request.cookies",
        "request.headers",
        "request.environ",
        "request.view_args",
        "get_json()",
        "get_data()"
    ]
    
    for pattern in FLASK_SOURCES:
        taint_registry.register_source(pattern, "user_input", "python")


# Helper functions
def _find_ssti_risks(content: str) -> List[int]:
    """Find Server-Side Template Injection risks."""
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'render_template_string' in line:
            findings.append(i)
    
    return findings


def _find_markup_xss(content: str) -> List[int]:
    """Find Markup() usage that could lead to XSS."""
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'Markup(' in line:
            findings.append(i)
    
    return findings


def _has_debug_mode(content: str) -> bool:
    """Check if debug mode is enabled."""
    import re
    return bool(re.search(r'app\.run\s*\([^)]*debug\s*=\s*True', content))


def _find_hardcoded_secrets(content: str) -> List[int]:
    """Find hardcoded secret keys."""
    import re
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if re.search(r"(?:app\.secret_key|SECRET_KEY)\s*=\s*['\"][^'\"]+['\"]", line):
            # Skip if it's from environment
            if 'os.environ' not in line and 'getenv' not in line:
                findings.append(i)
    
    return findings


def _find_unsafe_file_uploads(content: str) -> List[int]:
    """Find unsafe file upload operations."""
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'request.files' in line and '.save(' in line:
            # Check if there's validation nearby
            context_start = max(0, i - 5)
            context_end = min(len(lines), i + 5)
            context = '\n'.join(lines[context_start:context_end])
            
            if not any(check in context for check in ['allowed_file', 'secure_filename', 'validate']):
                findings.append(i)
    
    return findings


def _find_sql_injection_risks(content: str) -> List[int]:
    """Find SQL injection vulnerabilities."""
    import re
    findings = []
    lines = content.split('\n')
    
    sql_exec_pattern = r'(?:execute|executemany)\s*\('
    
    for i, line in enumerate(lines, 1):
        if re.search(sql_exec_pattern, line):
            # Check for string formatting
            if any(fmt in line for fmt in ['%', '.format', 'f"', "f'"]):
                findings.append(i)
    
    return findings


def _find_open_redirects(content: str) -> List[int]:
    """Find open redirect vulnerabilities."""
    import re
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if re.search(r'redirect\s*\(\s*request\.(?:args|values|form)\.get', line):
            findings.append(i)
    
    return findings


def _find_eval_usage(content: str) -> List[int]:
    """Find eval usage with user input."""
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'eval(' in line and 'request.' in line:
            findings.append(i)
    
    return findings


def _has_cors_wildcard(content: str) -> bool:
    """Check for CORS wildcard configuration."""
    return ('CORS' in content or 'Access-Control-Allow-Origin' in content) and '"*"' in content


def _find_unsafe_deserialization(content: str) -> List[int]:
    """Find unsafe pickle deserialization."""
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'pickle.loads' in line and 'request.' in line:
            findings.append(i)
    
    return findings


def _find_html_in_json(content: str) -> List[int]:
    """Find HTML in JSON responses."""
    import re
    findings = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'jsonify' in line and re.search(r'<[^>]+>', line):
            findings.append(i)
    
    return findings


def _has_werkzeug_debugger(content: str) -> bool:
    """Check for Werkzeug debugger exposure."""
    return 'WERKZEUG_DEBUG_PIN' in content or 'use_debugger=True' in content