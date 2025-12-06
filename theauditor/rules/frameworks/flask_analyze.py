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


USER_INPUT_SOURCES = frozenset(
    [
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
    ]
)


SECRET_VARS = frozenset(
    [
        "SECRET_KEY",
        "secret_key",
        "API_KEY",
        "api_key",
        "PASSWORD",
        "password",
        "TOKEN",
        "token",
    ]
)


FILE_VALIDATORS = frozenset(
    [
        "secure_filename",
        "validate",
        "allowed",
        "allowed_file",
    ]
)


SESSION_CONFIGS = frozenset(
    [
        "SESSION_COOKIE_SECURE",
        "SESSION_COOKIE_HTTPONLY",
        "SESSION_COOKIE_SAMESITE",
    ]
)


SESSION_LIFETIME_CONFIGS = frozenset(
    [
        "PERMANENT_SESSION_LIFETIME",
        "SESSION_PERMANENT",
    ]
)


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

        flask_files = _get_flask_files(db)
        if not flask_files:
            return RuleResult(findings=findings, manifest=db.get_manifest())

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
        findings.extend(_check_unsafe_yaml(db))
        findings.extend(_check_command_injection(db))
        findings.extend(_check_jwt_vulnerabilities(db))
        findings.extend(_check_path_traversal_sendfile(db))
        findings.extend(_check_missing_security_headers(db, flask_files))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_flask_files(db: RuleDB) -> list[str]:
    """Get files that import Flask."""
    rows = db.query(Q("refs").select("src").where("value IN (?, ?)", "flask", "Flask"))
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
    """Check for debug mode enabled.

    Detects both app.run(debug=True) and app.config['DEBUG'] = True patterns.
    """
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function LIKE ?", "%.run")
        .order_by("file, line")
    )

    for file, line, _callee, args in rows:
        args = args or ""
        if "debug" in args and "True" in args:
            findings.append(
                StandardFinding(
                    rule_name="flask-debug-mode-enabled",
                    message="Flask debug mode enabled via app.run(debug=True)",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=args[:100] if len(args) > 100 else args,
                    cwe_id="CWE-489",
                )
            )

    config_rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, target_var, source_expr in config_rows:
        target_var = target_var or ""
        source_expr = source_expr or ""

        if "DEBUG" in target_var and source_expr.strip() == "True":
            findings.append(
                StandardFinding(
                    rule_name="flask-debug-config-enabled",
                    message="Flask debug mode enabled via config assignment",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=f"{target_var} = {source_expr}",
                    cwe_id="CWE-489",
                )
            )

    update_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function LIKE ? AND argument_expr LIKE ?", "%config%", "%DEBUG%")
        .order_by("file, line")
    )

    for file, line, callee, args in update_rows:
        args = args or ""
        if "True" in args and "DEBUG" in args:
            findings.append(
                StandardFinding(
                    rule_name="flask-debug-config-update",
                    message="Flask debug mode enabled via config.update()",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=f"{callee}({args[:60]}...)" if len(args) > 60 else f"{callee}({args})",
                    cwe_id="CWE-489",
                )
            )

    return findings


def _check_hardcoded_secrets(db: RuleDB) -> list[StandardFinding]:
    """Check for hardcoded secret keys."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, var_name, secret_value in rows:
        var_name = var_name or ""
        secret_value = secret_value or ""
        var_name_upper = var_name.upper()

        if not any(secret in var_name_upper for secret in SECRET_VARS):
            continue

        if not ('"' in secret_value or "'" in secret_value):
            continue
        if "environ" in secret_value or "getenv" in secret_value:
            continue

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

    all_calls_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )
    all_calls = list(all_calls_rows)

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

        has_format = (
            (".format(" in query_text)
            or ('f"' in query_text)
            or ("f'" in query_text)
            or ("%" in query_text and "%" in query_text[query_text.index("%") + 1 :])
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
            "request.args.get" in redirect_arg
            or "request.values.get" in redirect_arg
            or "request.form.get" in redirect_arg
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

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
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
        .where(
            "callee_function IN (?, ?, ?, ?, ?)",
            "pickle.loads",
            "loads",
            "pickle.load",
            "load",
            "yaml.load",
        )
        .order_by("file, line")
    )

    for file, line, callee, pickle_arg in rows:
        pickle_arg = pickle_arg or ""
        callee = callee or ""

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
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, var, value in rows:
        var = var or ""
        value = value or ""

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

    rows = db.query(
        Q("refs")
        .select("value")
        .where("value IN (?, ?, ?)", "flask_wtf", "CSRFProtect", "csrf")
        .limit(1)
    )
    if list(rows):
        return findings

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
    """Check for insecure session cookie configuration.

    Checks for:
    1. Session cookie flags set to False (Secure, HttpOnly, SameSite)
    2. Missing PERMANENT_SESSION_LIFETIME (infinite sessions)
    """
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

    session_usage_rows = db.query(
        Q("function_call_args")
        .select("file")
        .where("argument_expr LIKE ? OR callee_function LIKE ?", "%session%", "%session%")
        .limit(1)
    )

    if list(session_usage_rows):
        lifetime_rows = db.query(
            Q("assignments")
            .select("target_var")
            .where("target_var LIKE ?", "%PERMANENT_SESSION_LIFETIME%")
            .limit(1)
        )

        if not list(lifetime_rows):
            config_rows = db.query(
                Q("function_call_args")
                .select("argument_expr")
                .where("argument_expr LIKE ?", "%PERMANENT_SESSION_LIFETIME%")
                .limit(1)
            )

            if not list(config_rows):
                flask_rows = db.query(
                    Q("refs").select("src").where("value IN (?, ?)", "flask", "Flask").limit(1)
                )
                flask_files = list(flask_rows)

                if flask_files:
                    findings.append(
                        StandardFinding(
                            rule_name="flask-missing-session-lifetime",
                            message="Sessions used without PERMANENT_SESSION_LIFETIME - sessions may never expire",
                            file_path=flask_files[0][0],
                            line=1,
                            severity=Severity.MEDIUM,
                            category="session",
                            confidence=Confidence.MEDIUM,
                            snippet="Set PERMANENT_SESSION_LIFETIME to limit session duration",
                            cwe_id="CWE-613",
                        )
                    )

    return findings


def _check_unsafe_yaml(db: RuleDB) -> list[StandardFinding]:
    """Check for unsafe YAML loading."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?)", "yaml.load", "yaml.unsafe_load")
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""

        if callee == "yaml.unsafe_load":
            findings.append(
                StandardFinding(
                    rule_name="flask-unsafe-yaml-load",
                    message="yaml.unsafe_load allows arbitrary code execution",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet="Use yaml.safe_load() instead",
                    cwe_id="CWE-502",
                )
            )
        elif "Loader" not in arg_expr:
            findings.append(
                StandardFinding(
                    rule_name="flask-yaml-load-no-loader",
                    message="yaml.load without Loader parameter - code execution risk",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    confidence=Confidence.HIGH,
                    snippet="Use yaml.safe_load() or Loader=yaml.SafeLoader",
                    cwe_id="CWE-502",
                )
            )

    return findings


def _check_command_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for command injection via subprocess with shell=True."""
    findings = []

    subprocess_funcs = (
        "subprocess.run",
        "subprocess.call",
        "subprocess.Popen",
        "subprocess.check_output",
        "subprocess.check_call",
        "os.system",
        "os.popen",
        "os.popen2",
        "os.popen3",
        "os.popen4",
        "commands.getoutput",
        "commands.getstatusoutput",
    )
    placeholders = ",".join("?" * len(subprocess_funcs))

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(f"callee_function IN ({placeholders})", *subprocess_funcs)
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""

        if "shell=True" in arg_expr or "shell = True" in arg_expr:
            for source in USER_INPUT_SOURCES:
                if source in arg_expr:
                    findings.append(
                        StandardFinding(
                            rule_name="flask-command-injection",
                            message=f"Command injection - {source} in {callee} with shell=True",
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="injection",
                            confidence=Confidence.HIGH,
                            snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                            cwe_id="CWE-78",
                        )
                    )
                    break
            else:
                findings.append(
                    StandardFinding(
                        rule_name="flask-shell-true",
                        message=f"{callee} with shell=True - potential command injection",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="injection",
                        confidence=Confidence.MEDIUM,
                        snippet="Avoid shell=True, use list of arguments instead",
                        cwe_id="CWE-78",
                    )
                )

        if callee == "os.system":
            for source in USER_INPUT_SOURCES:
                if source in arg_expr:
                    findings.append(
                        StandardFinding(
                            rule_name="flask-os-system-injection",
                            message=f"Command injection - {source} in os.system",
                            file_path=file,
                            line=line,
                            severity=Severity.CRITICAL,
                            category="injection",
                            confidence=Confidence.HIGH,
                            snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                            cwe_id="CWE-78",
                        )
                    )
                    break

    return findings


def _check_jwt_vulnerabilities(db: RuleDB) -> list[StandardFinding]:
    """Check for JWT implementation vulnerabilities."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function LIKE ? OR callee_function LIKE ?", "%jwt%decode%", "%decode%")
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""
        arg_lower = arg_expr.lower()

        if "jwt" not in callee.lower() and "jwt" not in arg_lower:
            continue

        issues = []

        if "algorithms" not in arg_lower and "algorithm" not in arg_lower:
            issues.append("no algorithm specified")

        if "verify=false" in arg_lower or "verify_signature=false" in arg_lower:
            issues.append("signature verification disabled")

        if "verify_exp" in arg_lower and "false" in arg_lower:
            issues.append("expiry verification disabled")

        if issues:
            findings.append(
                StandardFinding(
                    rule_name="flask-jwt-vulnerability",
                    message=f"JWT vulnerability: {', '.join(issues)}",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="authentication",
                    confidence=Confidence.HIGH,
                    snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                    cwe_id="CWE-347",
                )
            )

    return findings


def _check_path_traversal_sendfile(db: RuleDB) -> list[StandardFinding]:
    """Check for path traversal in send_file/send_from_directory."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?, ?)", "send_file", "send_from_directory", "safe_join")
        .order_by("file, line")
    )

    for file, line, callee, arg_expr in rows:
        arg_expr = arg_expr or ""

        for source in USER_INPUT_SOURCES:
            if source in arg_expr:
                if callee == "safe_join":
                    continue

                findings.append(
                    StandardFinding(
                        rule_name="flask-path-traversal-sendfile",
                        message=f"Path traversal risk - {source} in {callee}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="injection",
                        confidence=Confidence.HIGH,
                        snippet=arg_expr[:100] if len(arg_expr) > 100 else arg_expr,
                        cwe_id="CWE-22",
                    )
                )
                break

    return findings


def _check_missing_security_headers(db: RuleDB, flask_files: list[str]) -> list[StandardFinding]:
    """Check for missing security headers."""
    findings = []

    rows = db.query(
        Q("refs")
        .select("value")
        .where("value IN (?, ?, ?)", "flask_talisman", "Talisman", "flask-talisman")
        .limit(1)
    )
    if list(rows):
        return findings

    rows = db.query(
        Q("function_call_args")
        .select("argument_expr")
        .where(
            "argument_expr LIKE ? OR argument_expr LIKE ? OR argument_expr LIKE ?",
            "%X-Frame-Options%",
            "%Content-Security-Policy%",
            "%X-Content-Type-Options%",
        )
        .limit(1)
    )
    if list(rows):
        return findings

    if flask_files:
        findings.append(
            StandardFinding(
                rule_name="flask-missing-security-headers",
                message="Flask application without security headers (CSP, X-Frame-Options, etc.)",
                file_path=flask_files[0],
                line=1,
                severity=Severity.MEDIUM,
                category="security",
                confidence=Confidence.MEDIUM,
                snippet="Install flask-talisman for security headers",
                cwe_id="CWE-693",
            )
        )

    return findings


FLASK_INPUT_SOURCES = frozenset(
    [
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
    ]
)

FLASK_SSTI_SINKS = frozenset(
    [
        "render_template_string",
        "Markup",
        "jinja2.Template",
    ]
)

FLASK_REDIRECT_SINKS = frozenset(
    [
        "redirect",
        "url_for",
        "make_response",
    ]
)

FLASK_SQL_SINKS = frozenset(
    [
        "execute",
        "executemany",
        "db.execute",
        "session.execute",
    ]
)


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
