"""Flask Framework Security Analyzer.

Detects security misconfigurations and vulnerabilities in Flask applications:
- Server-Side Template Injection (SSTI) via render_template_string
- XSS via Markup() with user input
- Debug mode enabled in production
- Hardcoded secret keys
- Unsafe file upload handling
- SQL injection via string formatting
- Open redirect vulnerabilities
- Eval/exec with user input
- CORS wildcard configuration
- Pickle deserialization of untrusted data
- Missing CSRF protection
- Insecure session configuration
"""

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="flask_security",
    category="frameworks",
    target_extensions=[".py"],
    exclude_patterns=["test/", "tests/", "spec.", "__tests__/", "migrations/", ".venv/"],
    execution_scope="database",
    primary_table="refs",
)

# User input sources in Flask
USER_INPUT_SOURCES = frozenset([
    "request.",
    "request.args",
    "request.form",
    "request.values",
    "request.json",
    "request.data",
    "request.files",
    "request.cookies",
    "request.headers",
    "request.environ",
    "request.get_json",
    "request.get_data",
])

# Secret variable names
SECRET_VARS = frozenset([
    "SECRET_KEY",
    "secret_key",
    "API_KEY",
    "api_key",
    "PASSWORD",
    "password",
    "TOKEN",
    "token",
])

# File validation functions
FILE_VALIDATORS = frozenset([
    "secure_filename",
    "validate",
    "allowed",
    "allowed_file",
])

# Session security configuration keys
SESSION_CONFIGS = frozenset([
    "SESSION_COOKIE_SECURE",
    "SESSION_COOKIE_HTTPONLY",
    "SESSION_COOKIE_SAMESITE",
])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Flask security misconfigurations.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []

        # Check if this is a Flask project
        flask_files = _get_flask_files(db)
        if not flask_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

        # Run all security checks
        findings.extend(_check_ssti_risks(db))
        findings.extend(_check_markup_xss(db))
        findings.extend(_check_debug_mode(db))
        findings.extend(_check_hardcoded_secrets(db))
        findings.extend(_check_unsafe_file_uploads(db))
        findings.extend(_check_sql_injection(db))
        findings.extend(_check_open_redirects(db))
        findings.extend(_check_eval_usage(db))
        findings.extend(_check_cors_wildcard(db))
        findings.extend(_check_unsafe_deserialization(db))
        findings.extend(_check_werkzeug_debugger(db))
        findings.extend(_check_csrf_protection(db, flask_files))
        findings.extend(_check_session_security(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_flask_files(db: RuleDB) -> list[str]:
    """Get files that import Flask."""
    rows = db.query(
        Q("refs")
        .select("src")
        .where("value IN (?, ?)", "flask", "Flask")
    )
    return [row[0] for row in rows]


def _check_ssti_risks(db: RuleDB) -> list[StandardFinding]:
    """Check for Server-Side Template Injection risks."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where("callee_function = ?", "render_template_string")
        .order_by("file, line")
    )

    for file, line, template_arg in rows:
        template_arg = template_arg or ""
        has_user_input = any(src in template_arg for src in USER_INPUT_SOURCES)

        findings.append(
            StandardFinding(
                rule_name="flask-ssti-render-template-string",
                message="Use of render_template_string - Server-Side Template Injection risk",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL if has_user_input else Severity.HIGH,
                category="injection",
                confidence=Confidence.HIGH if has_user_input else Confidence.MEDIUM,
                snippet=template_arg[:100] if len(template_arg) > 100 else template_arg,
                cwe_id="CWE-94",
            )
        )

    return findings


def _check_markup_xss(db: RuleDB) -> list[StandardFinding]:
    """Check for XSS via Markup()."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where("callee_function = ?", "Markup")
        .order_by("file, line")
    )

    for file, line, markup_content in rows:
        markup_content = markup_content or ""
        if any(src in markup_content for src in USER_INPUT_SOURCES):
            findings.append(
                StandardFinding(
                    rule_name="flask-markup-xss",
                    message="Use of Markup() with potential user input - XSS risk",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    confidence=Confidence.HIGH,
                    snippet=markup_content[:100] if len(markup_content) > 100 else markup_content,
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_debug_mode(db: RuleDB) -> list[StandardFinding]:
    """Check for debug mode enabled."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function LIKE ?", "%.run")
        .order_by("file, line")
    )

    for file, line, callee, args in rows:
        args = args or ""
        if "debug" in args and "True" in args:
            findings.append(
                StandardFinding(
                    rule_name="flask-debug-mode-enabled",
                    message="Flask debug mode enabled - exposes interactive debugger",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=args[:100] if len(args) > 100 else args,
                    cwe_id="CWE-489",
                )
            )

    return findings


def _check_hardcoded_secrets(db: RuleDB) -> list[StandardFinding]:
    """Check for hardcoded secret keys."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .order_by("file, line")
    )

    for file, line, var_name, secret_value in rows:
        var_name = var_name or ""
        secret_value = secret_value or ""
        var_name_upper = var_name.upper()

        # Check if this is a secret variable
        if not any(secret in var_name_upper for secret in SECRET_VARS):
            continue

        # Check if it's a string literal (not from env)
        if not ('"' in secret_value or "'" in secret_value):
            continue
        if "environ" in secret_value or "getenv" in secret_value:
            continue

        # Check if secret is weak (short)
        clean_secret = secret_value.strip("\"'")
        if len(clean_secret) < 32:
            findings.append(
                StandardFinding(
                    rule_name="flask-secret-key-exposed",
                    message=f"Weak/hardcoded secret key ({len(clean_secret)} chars) - compromises session security",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=f"{var_name} = {secret_value[:30]}...",
                    cwe_id="CWE-798",
                )
            )

    return findings


def _check_unsafe_file_uploads(db: RuleDB) -> list[StandardFinding]:
    """Check for unsafe file upload operations."""
    findings = []

    # Get all function calls for correlation
    all_calls_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )
    all_calls = list(all_calls_rows)

    # Find .save() calls and file validators
    save_calls = []
    file_validators: dict[str, list[int]] = {}

    for file, line, callee, arg_expr in all_calls:
        callee = callee or ""
        if callee.endswith(".save"):
            save_calls.append((file, line, callee, arg_expr or ""))
        if callee in FILE_VALIDATORS:
            if file not in file_validators:
                file_validators[file] = []
            file_validators[file].append(line)

    seen = set()
    for save_file, save_line, _save_callee, _save_arg in save_calls:
        # Check if this save is related to file upload
        has_file_input = False
        for file, line, _callee, arg_expr in all_calls:
            if (
                file == save_file
                and abs(line - save_line) <= 10
                and "request.files" in (arg_expr or "")
            ):
                has_file_input = True
                break

        if not has_file_input:
            continue

        # Check if file was validated
        has_validation = False
        if save_file in file_validators:
            for val_line in file_validators[save_file]:
                if abs(val_line - save_line) <= 10:
                    has_validation = True
                    break

        # Only flag if no validation found
        if not has_validation:
            key = (save_file, save_line)
            if key not in seen:
                seen.add(key)
                findings.append(
                    StandardFinding(
                        rule_name="flask-unsafe-file-upload",
                        message="File upload without validation - malicious file upload risk",
                        file_path=save_file,
                        line=save_line,
                        severity=Severity.HIGH,
                        category="security",
                        confidence=Confidence.HIGH,
                        snippet="request.files[...].save() without secure_filename()",
                        cwe_id="CWE-434",
                    )
                )

    return findings


def _check_sql_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for SQL injection risks."""
    findings = []

    rows = db.query(
        Q("sql_queries")
        .select("file_path", "line_number", "query_text")
        .order_by("file_path, line_number")
    )

    for file, line, query_text in rows:
        query_text = query_text or ""

        # Check for string formatting patterns in SQL
        has_format = (
            (".format(" in query_text) or
            ('f"' in query_text) or
            ("f'" in query_text) or
            # Check for % formatting with multiple %
            ("%" in query_text and "%" in query_text[query_text.index("%") + 1:])
        )

        if has_format:
            findings.append(
                StandardFinding(
                    rule_name="flask-sql-injection-risk",
                    message="String formatting in SQL query - SQL injection vulnerability",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet=query_text[:100] if len(query_text) > 100 else query_text,
                    cwe_id="CWE-89",
                )
            )

    return findings


def _check_open_redirects(db: RuleDB) -> list[StandardFinding]:
    """Check for open redirect vulnerabilities."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function = ?", "redirect")
        .order_by("file, line")
    )

    for file, line, _callee, redirect_arg in rows:
        redirect_arg = redirect_arg or ""
        if (
            "request.args.get" in redirect_arg or
            "request.values.get" in redirect_arg or
            "request.form.get" in redirect_arg
        ):
            findings.append(
                StandardFinding(
                    rule_name="flask-open-redirect",
                    message="Unvalidated redirect from user input - open redirect vulnerability",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=redirect_arg[:100] if len(redirect_arg) > 100 else redirect_arg,
                    cwe_id="CWE-601",
                )
            )

    return findings


def _check_eval_usage(db: RuleDB) -> list[StandardFinding]:
    """Check for eval usage with user input."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?, ?)", "eval", "exec", "compile")
        .order_by("file, line")
    )

    for file, line, callee, eval_arg in rows:
        eval_arg = eval_arg or ""
        if "request." in eval_arg:
            findings.append(
                StandardFinding(
                    rule_name="flask-eval-usage",
                    message=f"Use of {callee} with user input - code injection vulnerability",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet=eval_arg[:100] if len(eval_arg) > 100 else eval_arg,
                    cwe_id="CWE-95",
                )
            )

    return findings


def _check_cors_wildcard(db: RuleDB) -> list[StandardFinding]:
    """Check for CORS wildcard configuration."""
    findings = []

    # Check assignments
    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .order_by("file, line")
    )

    for file, line, target_var, cors_config in rows:
        target_var = target_var or ""
        cors_config = cors_config or ""
        target_upper = target_var.upper()

        if "CORS" not in target_upper and "ACCESS-CONTROL-ALLOW-ORIGIN" not in target_upper:
            continue
        if "*" not in cors_config:
            continue

        findings.append(
            StandardFinding(
                rule_name="flask-cors-wildcard",
                message="CORS with wildcard origin - allows any domain access",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="security",
                confidence=Confidence.HIGH,
                snippet=cors_config[:100] if len(cors_config) > 100 else cors_config,
                cwe_id="CWE-346",
            )
        )

    # Check CORS() function calls
    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function = ?", "CORS")
        .order_by("file, line")
    )

    for file, line, _callee, cors_arg in rows:
        cors_arg = cors_arg or ""
        if "*" in cors_arg:
            findings.append(
                StandardFinding(
                    rule_name="flask-cors-wildcard",
                    message="CORS with wildcard origin - allows any domain access",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=cors_arg[:100] if len(cors_arg) > 100 else cors_arg,
                    cwe_id="CWE-346",
                )
            )

    return findings


def _check_unsafe_deserialization(db: RuleDB) -> list[StandardFinding]:
    """Check for unsafe pickle deserialization."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?, ?, ?, ?)",
               "pickle.loads", "loads", "pickle.load", "load", "yaml.load")
        .order_by("file, line")
    )

    for file, line, callee, pickle_arg in rows:
        pickle_arg = pickle_arg or ""
        callee = callee or ""

        # Check for user input in deserialization
        if "request." in pickle_arg:
            findings.append(
                StandardFinding(
                    rule_name="flask-unsafe-deserialization",
                    message=f"Deserialization ({callee}) of user input - Remote Code Execution risk",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet=pickle_arg[:100] if len(pickle_arg) > 100 else pickle_arg,
                    cwe_id="CWE-502",
                )
            )

    return findings


def _check_werkzeug_debugger(db: RuleDB) -> list[StandardFinding]:
    """Check for Werkzeug debugger exposure."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .order_by("file, line")
    )

    for file, line, var, value in rows:
        var = var or ""
        value = value or ""

        # Check for WERKZEUG_DEBUG_PIN or use_debugger = True
        if var == "WERKZEUG_DEBUG_PIN" or ("use_debugger" in value and "True" in value):
            findings.append(
                StandardFinding(
                    rule_name="flask-werkzeug-debugger",
                    message="Werkzeug debugger exposed - allows arbitrary code execution",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=f"{var} = {value[:50]}",
                    cwe_id="CWE-489",
                )
            )

    return findings


def _check_csrf_protection(db: RuleDB, flask_files: list[str]) -> list[StandardFinding]:
    """Check for missing CSRF protection."""
    findings = []

    # Check if CSRF protection is imported
    rows = db.query(
        Q("refs")
        .select("value")
        .where("value IN (?, ?, ?)", "flask_wtf", "CSRFProtect", "csrf")
        .limit(1)
    )
    if list(rows):
        return findings

    # Check if there are state-changing endpoints
    rows = db.query(
        Q("api_endpoints")
        .select("method")
        .where("method IN (?, ?, ?, ?)", "POST", "PUT", "DELETE", "PATCH")
        .limit(1)
    )
    has_state_changing = bool(list(rows))

    if has_state_changing and flask_files:
        findings.append(
            StandardFinding(
                rule_name="flask-missing-csrf",
                message="State-changing endpoints without CSRF protection",
                file_path=flask_files[0],
                line=1,
                severity=Severity.HIGH,
                category="security",
                confidence=Confidence.MEDIUM,
                snippet="Missing CSRF protection for POST/PUT/DELETE/PATCH endpoints",
                cwe_id="CWE-352",
            )
        )

    return findings


def _check_session_security(db: RuleDB) -> list[StandardFinding]:
    """Check for insecure session cookie configuration."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr = ?", "False")
        .order_by("file, line")
    )

    for file, line, var, config in rows:
        var = var or ""
        config = config or ""
        var_upper = var.upper()

        if any(session_config in var_upper for session_config in SESSION_CONFIGS):
            findings.append(
                StandardFinding(
                    rule_name="flask-insecure-session",
                    message=f"Insecure session cookie configuration: {var} = False",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="session",
                    confidence=Confidence.HIGH,
                    snippet=f"{var} = {config}",
                    cwe_id="CWE-614",
                )
            )

    return findings


# TODO(quality): Missing detection patterns to add in future:
# - yaml.unsafe_load / yaml.load without Loader parameter
# - Command injection via subprocess with shell=True
# - JWT vulnerabilities (weak algorithm, no expiry)
# - Path traversal in send_file/send_from_directory
# - Race conditions in file operations
# - Missing security headers (X-Frame-Options, CSP, etc.)


# Taint patterns for taint tracking engine
FLASK_INPUT_SOURCES = frozenset([
    "request.args",
    "request.form",
    "request.values",
    "request.json",
    "request.data",
    "request.files",
    "request.cookies",
    "request.headers",
    "request.environ",
    "request.get_json",
    "request.get_data",
])

FLASK_SSTI_SINKS = frozenset([
    "render_template_string",
    "Markup",
    "jinja2.Template",
])

FLASK_REDIRECT_SINKS = frozenset([
    "redirect",
    "url_for",
    "make_response",
])

FLASK_SQL_SINKS = frozenset([
    "execute",
    "executemany",
    "db.execute",
    "session.execute",
])


def register_taint_patterns(taint_registry) -> None:
    """Register Flask-specific taint patterns for taint tracking engine.

    Args:
        taint_registry: The taint pattern registry to register patterns with
    """
    for pattern in FLASK_INPUT_SOURCES:
        taint_registry.register_source(pattern, "user_input", "python")

    for pattern in FLASK_SSTI_SINKS:
        taint_registry.register_sink(pattern, "ssti", "python")

    for pattern in FLASK_REDIRECT_SINKS:
        taint_registry.register_sink(pattern, "redirect", "python")

    for pattern in FLASK_SQL_SINKS:
        taint_registry.register_sink(pattern, "sql", "python")
