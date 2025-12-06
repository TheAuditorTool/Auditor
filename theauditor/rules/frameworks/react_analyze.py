"""React Framework Security Analyzer.

Detects security vulnerabilities in React applications including:
- dangerouslySetInnerHTML without sanitization (CWE-79)
- Exposed API keys in client bundle (CWE-200)
- eval() with JSX content (CWE-95)
- Unsafe target="_blank" links (CWE-1022)
- Direct innerHTML manipulation (CWE-79)
- Hardcoded credentials (CWE-798)
- Sensitive data in localStorage/sessionStorage (CWE-922)
- Forms without input validation (CWE-20)
- useEffect without cleanup (CWE-401)
- Unprotected routes (CWE-862)
- Missing CSRF protection (CWE-352)
- Unescaped user input in JSX (CWE-79)
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
    name="react_security",
    category="frameworks",
    target_extensions=[".jsx", ".tsx", ".js", ".ts"],
    exclude_patterns=["node_modules/", "test/", "spec.", "__tests__/"],
    execution_scope="database",
    primary_table="function_call_args",
)


USER_INPUT_SOURCES = frozenset(
    [
        "props.user",
        "props.input",
        "props.data",
        "props.content",
        "location.search",
        "params.",
        "query.",
        "formData.",
        "event.target.value",
        "e.target.value",
        "request.body",
        "useState",
        "this.props",
        "this.state",
    ]
)


XSS_SINKS = frozenset(
    [
        "dangerouslySetInnerHTML",
        "innerHTML",
        "outerHTML",
        "document.write",
        "document.writeln",
        "eval",
        "Function",
    ]
)


SANITIZATION_FUNCS = frozenset(
    [
        "sanitize",
        "escape",
        "encode",
        "DOMPurify",
        "xss",
        "clean",
        "safe",
        "purify",
    ]
)


SENSITIVE_PATTERNS = frozenset(
    [
        "KEY",
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "PRIVATE",
        "CREDENTIAL",
        "AUTH",
        "API",
    ]
)


FRONTEND_ENV_PREFIXES = frozenset(
    [
        "REACT_APP_",
        "NEXT_PUBLIC_",
        "VITE_",
        "GATSBY_",
        "PUBLIC_",
    ]
)


STORAGE_METHODS = frozenset(
    [
        "localStorage.setItem",
        "sessionStorage.setItem",
        "localStorage.set",
        "sessionStorage.set",
        "document.cookie",
        "indexedDB.put",
    ]
)


FORM_HANDLERS = frozenset(
    [
        "handleSubmit",
        "onSubmit",
        "submit",
        "submitForm",
        "formSubmit",
    ]
)


VALIDATION_LIBS = frozenset(
    [
        "yup",
        "joi",
        "zod",
        "validator",
        "validate",
        "sanitize",
        "schema",
    ]
)


ROUTE_FUNCTIONS = frozenset(
    [
        "Route",
        "PrivateRoute",
        "ProtectedRoute",
        "Router",
        "BrowserRouter",
        "Switch",
    ]
)


AUTH_FUNCTIONS = frozenset(
    [
        "isAuthenticated",
        "currentUser",
        "checkAuth",
        "requireAuth",
        "withAuth",
        "useAuth",
    ]
)


CODE_EXEC_SINKS = frozenset(
    [
        "eval",
        "Function",
        "setTimeout",
        "setInterval",
        "new Function",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect React security vulnerabilities using indexed data.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        findings.extend(_check_dangerous_html(db))
        findings.extend(_check_exposed_api_keys(db))
        findings.extend(_check_eval_with_jsx(db))
        findings.extend(_check_unsafe_target_blank(db))
        findings.extend(_check_direct_innerhtml(db))
        findings.extend(_check_hardcoded_credentials(db))
        findings.extend(_check_insecure_storage(db))
        findings.extend(_check_missing_validation(db))
        findings.extend(_check_useeffect_cleanup(db))
        findings.extend(_check_unprotected_routes(db))
        findings.extend(_check_csrf_in_forms(db))
        findings.extend(_check_unescaped_user_input(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_dangerous_html(db: RuleDB) -> list[StandardFinding]:
    """Check for dangerouslySetInnerHTML usage without sanitization."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(
            "callee_function = ? OR argument_expr LIKE ?",
            "dangerouslySetInnerHTML",
            "%dangerouslySetInnerHTML%",
        )
        .order_by("file, line")
    )

    dangerous_usages = []
    for file, line, _callee, html_content in rows:
        dangerous_usages.append((file, line, html_content))

    for file, line, html_content in dangerous_usages:
        has_sanitization = False
        for san_func in ["sanitize", "DOMPurify", "escape", "xss", "purify"]:
            san_rows = db.query(
                Q("function_call_args")
                .select("callee_function")
                .where(
                    "file = ? AND line BETWEEN ? AND ? AND callee_function = ?",
                    file,
                    line - 10,
                    line + 10,
                    san_func,
                )
                .limit(1)
            )
            if san_rows:
                has_sanitization = True
                break

        if not has_sanitization:
            findings.append(
                StandardFinding(
                    rule_name="react-dangerous-html",
                    message="Use of dangerouslySetInnerHTML without sanitization - primary XSS vector",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    confidence=Confidence.HIGH,
                    snippet=html_content[:100]
                    if html_content and len(html_content) > 100
                    else html_content,
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_exposed_api_keys(db: RuleDB) -> list[StandardFinding]:
    """Check for exposed API keys in frontend code."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var != ''")
        .order_by("file, line")
    )

    for file, line, var_name, value in rows:
        if not var_name:
            continue

        has_frontend_prefix = any(var_name.startswith(prefix) for prefix in FRONTEND_ENV_PREFIXES)
        if not has_frontend_prefix:
            continue

        var_upper = var_name.upper()
        has_sensitive = any(pattern in var_upper for pattern in SENSITIVE_PATTERNS)

        if has_sensitive:
            findings.append(
                StandardFinding(
                    rule_name="react-exposed-api-key",
                    message=f"API key/secret {var_name} exposed in client bundle",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=f"{var_name} = {value[:50]}..."
                    if value and len(value) > 50
                    else f"{var_name} = {value}",
                    cwe_id="CWE-200",
                )
            )

    return findings


def _check_eval_with_jsx(db: RuleDB) -> list[StandardFinding]:
    """Check for eval() used with JSX content."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function = ?", "eval")
        .order_by("file, line")
    )

    for file, line, _callee, eval_content in rows:
        if not eval_content:
            continue

        if not any(
            pattern in eval_content
            for pattern in ["<", "jsx", "JSX", "React.createElement", "createElement"]
        ):
            continue

        findings.append(
            StandardFinding(
                rule_name="react-eval-jsx",
                message="Using eval() with JSX - code injection vulnerability",
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category="injection",
                confidence=Confidence.HIGH,
                snippet=eval_content[:100] if len(eval_content) > 100 else eval_content,
                cwe_id="CWE-95",
            )
        )

    return findings


def _check_unsafe_target_blank(db: RuleDB) -> list[StandardFinding]:
    """Check for unsafe target='_blank' links without rel='noopener'."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr LIKE ?", "%_blank%")
        .order_by("file, line")
    )

    for file, line, _target, link_code in rows:
        if not link_code:
            continue

        has_target_blank = (
            'target="_blank"' in link_code
            or "target='_blank'" in link_code
            or ("target={" in link_code and "_blank" in link_code)
        )

        if not has_target_blank:
            continue

        if "noopener" in link_code or "noreferrer" in link_code:
            continue

        findings.append(
            StandardFinding(
                rule_name="react-unsafe-target-blank",
                message='External link without rel="noopener" - reverse tabnabbing vulnerability',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="security",
                confidence=Confidence.HIGH,
                snippet=link_code[:100] if len(link_code) > 100 else link_code,
                cwe_id="CWE-1022",
            )
        )

    return findings


def _check_direct_innerhtml(db: RuleDB) -> list[StandardFinding]:
    """Check for direct innerHTML manipulation bypassing React."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var LIKE ? OR target_var LIKE ?", "%.innerHTML", "%.outerHTML")
        .order_by("file, line")
    )

    for file, line, target, content in rows:
        if not target:
            continue

        if target.endswith(".innerHTML") or target.endswith(".outerHTML"):
            findings.append(
                StandardFinding(
                    rule_name="react-direct-innerhtml",
                    message="Direct innerHTML manipulation - bypasses React security",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    confidence=Confidence.HIGH,
                    snippet=f"{target} = {content[:50]}..."
                    if content and len(content) > 50
                    else f"{target} = {content}",
                    cwe_id="CWE-79",
                )
            )

    for func in ["document.write", "document.writeln"]:
        func_rows = db.query(
            Q("function_call_args")
            .select("file", "line", "argument_expr")
            .where("callee_function = ?", func)
            .order_by("file, line")
        )

        for file, line, write_content in func_rows:
            findings.append(
                StandardFinding(
                    rule_name="react-document-write",
                    message="Use of document.write in React - dangerous DOM manipulation",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    confidence=Confidence.HIGH,
                    snippet=write_content[:100]
                    if write_content and len(write_content) > 100
                    else write_content,
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_hardcoded_credentials(db: RuleDB) -> list[StandardFinding]:
    """Check for hardcoded credentials in React components."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, var_name, credential in rows:
        if not var_name or not credential:
            continue

        if '"' not in credential and "'" not in credential:
            continue

        if "process.env" in credential or "import.meta.env" in credential:
            continue

        clean_cred = credential.strip("\"'")
        if len(clean_cred) <= 10:
            continue

        var_lower = var_name.lower()
        is_credential = False
        cred_type = "credential"

        if "password" in var_lower:
            is_credential = True
            cred_type = "password"
        elif "apikey" in var_lower or "api_key" in var_lower:
            is_credential = True
            cred_type = "API key"
        elif "token" in var_lower:
            is_credential = True
            cred_type = "token"
        elif "secret" in var_lower:
            is_credential = True
            cred_type = "secret"
        elif "privatekey" in var_lower or "private_key" in var_lower:
            is_credential = True
            cred_type = "private key"

        if is_credential:
            findings.append(
                StandardFinding(
                    rule_name="react-hardcoded-credentials",
                    message=f"Hardcoded {cred_type} in React component",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="security",
                    confidence=Confidence.HIGH,
                    snippet=f'{var_name} = "..."',
                    cwe_id="CWE-798",
                )
            )

    return findings


def _check_insecure_storage(db: RuleDB) -> list[StandardFinding]:
    """Check for sensitive data stored in localStorage/sessionStorage."""
    findings = []

    for storage_method in STORAGE_METHODS:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function = ?", storage_method)
            .order_by("file, line")
        )

        for file, line, callee, data in rows:
            if not data:
                continue

            data_lower = data.lower()
            has_sensitive = any(pattern.lower() in data_lower for pattern in SENSITIVE_PATTERNS)

            if has_sensitive:
                storage_type = "localStorage" if "localStorage" in callee else "sessionStorage"
                findings.append(
                    StandardFinding(
                        rule_name="react-insecure-storage",
                        message=f"Sensitive data stored in {storage_type} - accessible to XSS attacks",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        confidence=Confidence.HIGH,
                        snippet=data[:100] if len(data) > 100 else data,
                        cwe_id="CWE-922",
                    )
                )

    return findings


def _check_missing_validation(db: RuleDB) -> list[StandardFinding]:
    """Check for forms without input validation."""
    findings = []

    form_files = set()
    for handler in FORM_HANDLERS:
        rows = db.query(
            Q("function_call_args").select("file", "line").where("callee_function = ?", handler)
        )
        for file, line in rows:
            form_files.add((file, line))

    for file, line in form_files:
        has_validation = False

        call_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where("file = ? AND line BETWEEN ? AND ?", file, line - 20, line + 20)
        )

        for (callee,) in call_rows:
            if not callee:
                continue
            callee_lower = callee.lower()
            if "validate" in callee_lower or "sanitize" in callee_lower:
                has_validation = True
                break

        if has_validation:
            continue

        for lib in ["yup", "joi", "zod", "validator"]:
            lib_rows = db.query(
                Q("refs").select("value").where("src = ? AND value = ?", file, lib).limit(1)
            )
            if lib_rows:
                has_validation = True
                break

        if not has_validation:
            findings.append(
                StandardFinding(
                    rule_name="react-missing-validation",
                    message="Form submission without input validation",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="validation",
                    confidence=Confidence.LOW,
                    snippet="Form handler without validation",
                    cwe_id="CWE-20",
                )
            )

    return findings


def _check_useeffect_cleanup(db: RuleDB) -> list[StandardFinding]:
    """Check for useEffect with external calls but no cleanup."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function = ?", "useEffect")
        .order_by("file, line")
    )

    for file, line, _callee, effect_code in rows:
        if not effect_code:
            continue

        if "fetch" not in effect_code:
            continue

        if "cleanup" in effect_code or "return" in effect_code or "AbortController" in effect_code:
            continue

        findings.append(
            StandardFinding(
                rule_name="react-useeffect-no-cleanup",
                message="useEffect with fetch but no cleanup - potential memory leak",
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category="performance",
                confidence=Confidence.LOW,
                snippet=effect_code[:100] if len(effect_code) > 100 else effect_code,
                cwe_id="CWE-401",
            )
        )

    return findings


def _check_unprotected_routes(db: RuleDB) -> list[StandardFinding]:
    """Check for client-side routing without authentication checks."""
    findings = []

    route_files = set()
    for route_func in ROUTE_FUNCTIONS:
        rows = db.query(
            Q("function_call_args").select("file").where("callee_function = ?", route_func)
        )
        for (file,) in rows:
            route_files.add(file)

    for file in route_files:
        call_rows = db.query(
            Q("function_call_args").select("callee_function").where("file = ?", file)
        )

        has_auth = False
        for (callee,) in call_rows:
            if not callee:
                continue
            if "auth" in callee.lower() or "Auth" in callee:
                has_auth = True
                break

        if has_auth:
            continue

        for auth_func in AUTH_FUNCTIONS:
            auth_rows = db.query(
                Q("function_call_args")
                .select("callee_function")
                .where("file = ? AND callee_function = ?", file, auth_func)
                .limit(1)
            )
            if auth_rows:
                has_auth = True
                break

        if not has_auth:
            findings.append(
                StandardFinding(
                    rule_name="react-unprotected-routes",
                    message="Client-side routing without authentication checks",
                    file_path=file,
                    line=1,
                    severity=Severity.MEDIUM,
                    category="authorization",
                    confidence=Confidence.LOW,
                    snippet="Routes defined without auth guards",
                    cwe_id="CWE-862",
                )
            )

    return findings


def _check_csrf_in_forms(db: RuleDB) -> list[StandardFinding]:
    """Check for forms without CSRF tokens."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    form_elements = []
    for file, line, _target, form_content in rows:
        if form_content and "<form" in form_content:
            form_elements.append((file, line, form_content))

    for file, line, form_content in form_elements:
        form_lower = form_content.lower()

        has_modifying_method = False
        if "method=" in form_lower:
            if any(m in form_lower for m in ["post", "put", "delete", "patch"]):
                has_modifying_method = True

        if not has_modifying_method:
            continue

        if "csrf" in form_lower or "xsrf" in form_lower:
            continue

        nearby_rows = db.query(
            Q("assignments")
            .select("target_var", "source_expr")
            .where("file = ? AND line BETWEEN ? AND ?", file, line - 10, line + 10)
        )

        has_csrf_nearby = False
        for target_var, source_expr in nearby_rows:
            target_lower = (target_var or "").lower()
            source_lower = (source_expr or "").lower()
            if (
                "csrf" in target_lower
                or "csrf" in source_lower
                or "xsrf" in target_lower
                or "xsrf" in source_lower
            ):
                has_csrf_nearby = True
                break

        if not has_csrf_nearby:
            findings.append(
                StandardFinding(
                    rule_name="react-missing-csrf",
                    message="Form submission without CSRF token",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="csrf",
                    confidence=Confidence.MEDIUM,
                    snippet="Form with POST/PUT/DELETE without CSRF",
                    cwe_id="CWE-352",
                )
            )

    return findings


def _check_unescaped_user_input(db: RuleDB) -> list[StandardFinding]:
    """Check for unescaped user input in JSX."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where(
            "source_expr LIKE ? OR source_expr LIKE ? OR source_expr LIKE ? OR source_expr LIKE ?",
            "%{props.%",
            "%{user%",
            "%{input%",
            "%{data%",
        )
        .order_by("file, line")
    )

    for file, line, _target, jsx_content in rows:
        if not jsx_content:
            continue

        if not any(
            pattern in jsx_content
            for pattern in ["{props.", "{user", "{input", "{data", "{params", "{query"]
        ):
            continue

        input_source = None
        for pattern in USER_INPUT_SOURCES:
            if pattern in jsx_content:
                input_source = pattern
                break

        if not input_source:
            continue

        jsx_lower = jsx_content.lower()
        has_sanitization = any(san in jsx_lower for san in SANITIZATION_FUNCS)

        if has_sanitization:
            continue

        san_rows = db.query(
            Q("function_call_args")
            .select("callee_function")
            .where(
                "file = ? AND line BETWEEN ? AND ? AND callee_function IN (?, ?, ?, ?)",
                file,
                line - 5,
                line + 5,
                "sanitize",
                "escape",
                "DOMPurify",
                "xss",
            )
            .limit(1)
        )

        if san_rows:
            continue

        findings.append(
            StandardFinding(
                rule_name="react-unescaped-user-input",
                message=f"User input {input_source} rendered without escaping - potential XSS",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="xss",
                confidence=Confidence.MEDIUM,
                snippet=jsx_content[:100] if len(jsx_content) > 100 else jsx_content,
                cwe_id="CWE-79",
            )
        )

    return findings


def register_taint_patterns(taint_registry) -> None:
    """Register React-specific taint patterns for dataflow analysis."""
    for pattern in USER_INPUT_SOURCES:
        taint_registry.register_source(pattern, "user_input", "javascript")

    for pattern in XSS_SINKS:
        taint_registry.register_sink(pattern, "xss", "javascript")

    for pattern in CODE_EXEC_SINKS:
        taint_registry.register_sink(pattern, "code_execution", "javascript")

    for pattern in STORAGE_METHODS:
        taint_registry.register_sink(pattern, "storage", "javascript")
