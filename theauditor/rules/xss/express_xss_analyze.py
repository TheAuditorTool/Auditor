"""Express.js-specific XSS Detection.

Detects XSS vulnerabilities specific to Express.js applications:
- res.send() with HTML containing user input
- Unsafe template rendering
- Cookie injection without httpOnly
- Header injection
- JSONP callback injection
"""

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q
from theauditor.rules.xss.constants import (
    COMMON_INPUT_SOURCES,
    is_sanitized,
)

METADATA = RuleMetadata(
    name="express_xss",
    category="xss",
    target_extensions=[".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=[
        "test/",
        "__tests__/",
        "node_modules/",
        "*.test.js",
        "*.spec.js",
        "frontend/",
        "client/",
    ],
    execution_scope="database",
    primary_table="function_call_args",
)

EXPRESS_DANGEROUS_SINKS = frozenset(
    [
        "res.send",
        "res.write",
        "res.end",
        "response.send",
        "response.write",
        "response.end",
    ]
)


EXPRESS_INPUT_SOURCES = COMMON_INPUT_SOURCES | frozenset(
    [
        "req.get(",
        "req.header(",
        "req.signedCookies",
        "req.originalUrl",
        "req.path",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Express.js-specific XSS vulnerabilities."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        if not _is_express_app(db):
            return RuleResult(findings=findings, manifest=db.get_manifest())

        findings.extend(_check_unsafe_res_send(db))
        findings.extend(_check_template_user_input(db))
        findings.extend(_check_middleware_injection(db))
        findings.extend(_check_cookie_injection(db))
        findings.extend(_check_header_injection(db))
        findings.extend(_check_jsonp_callback(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _is_express_app(db: RuleDB) -> bool:
    """Check if this is an Express.js application."""
    rows = db.query(
        Q("frameworks")
        .select("name")
        .where("name IN (?, ?)", "express", "express.js")
        .where("language = ?", "javascript")
    )
    return len(list(rows)) > 0


def _has_express_input(expr: str) -> bool:
    """Check if expression contains Express-specific user input sources."""
    return any(src in expr for src in EXPRESS_INPUT_SOURCES)


def _check_unsafe_res_send(db: RuleDB) -> list[StandardFinding]:
    """Check for res.send() with HTML content containing user input."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?)", "res.send", "response.send")
        .where("argument_index = ?", 0)
        .where("argument_expr IS NOT NULL")
    )

    for file, line, func, args in rows:
        if not args:
            continue

        has_html = any(
            pattern in args
            for pattern in [
                "`",
                "<html",
                "<div",
                "<script",
                "<img",
                "<iframe",
                "<span",
                "<p>",
            ]
        )
        has_user_input = _has_express_input(args)
        sanitized = is_sanitized(args)

        if sanitized:
            continue

        if has_html and has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="express-xss-res-send-html",
                    message="XSS: res.send() with HTML containing unsanitized user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=f"{func}({args[:60]}...)" if len(args) > 60 else f"{func}({args})",
                    cwe_id="CWE-79",
                )
            )
        elif has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="express-xss-res-send-tainted",
                    message="XSS Risk: res.send() with unsanitized user input (verify content-type)",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet=f"{func}({args[:60]}...)" if len(args) > 60 else f"{func}({args})",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_template_user_input(db: RuleDB) -> list[StandardFinding]:
    """Check for user input passed directly to template rendering."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?)", "res.render", "response.render")
        .where("argument_index = ?", 1)
        .where("argument_expr IS NOT NULL")
    )

    for file, line, func, locals_arg in rows:
        if not locals_arg:
            continue

        has_user_input = _has_express_input(locals_arg)
        sanitized = is_sanitized(locals_arg)
        spreads_input = "...req." in locals_arg or "...request." in locals_arg

        if has_user_input and not sanitized:
            severity = Severity.HIGH if spreads_input else Severity.MEDIUM
            message = (
                "XSS: Spreading user input object directly to template (dangerous)"
                if spreads_input
                else "XSS: User input passed to template - ensure template escapes properly"
            )

            findings.append(
                StandardFinding(
                    rule_name="express-xss-template-input",
                    message=message,
                    file_path=file,
                    line=line,
                    severity=severity,
                    category="xss",
                    snippet=f"{func}(template, {locals_arg[:40]}...)",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_middleware_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for XSS in custom Express middleware."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function = ?", "app.use")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, _func, middleware in rows:
        if not middleware:
            continue

        has_dangerous_sink = any(sink in middleware for sink in EXPRESS_DANGEROUS_SINKS)
        has_user_input = _has_express_input(middleware)
        sanitized = is_sanitized(middleware)

        if has_dangerous_sink and has_user_input and not sanitized:
            findings.append(
                StandardFinding(
                    rule_name="express-xss-middleware",
                    message="XSS: Express middleware writing unsanitized user input to response",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet="app.use((req, res, next) => { res.write(req.body...) })",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_cookie_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for cookies set with user input without httpOnly."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where("callee_function IN (?, ?)", "res.cookie", "response.cookie")
        .where("argument_index = ?", 1)
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, cookie_value in rows:
        if not _has_express_input(cookie_value):
            continue

        options_rows = db.query(
            Q("function_call_args")
            .select("argument_expr")
            .where("file = ?", file)
            .where("line = ?", line)
            .where("argument_index = ?", 2)
        )

        options_list = list(options_rows)
        has_httponly = options_list and options_list[0][0] and "httpOnly" in options_list[0][0]

        if not has_httponly:
            findings.append(
                StandardFinding(
                    rule_name="express-xss-cookie",
                    message="Cookie set with user input without httpOnly flag - enables XSS cookie theft",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet='res.cookie("name", req.body.value)',
                    cwe_id="CWE-1004",
                )
            )

    return findings


def _check_header_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for header injection that could lead to XSS."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(
            "callee_function IN (?, ?, ?, ?)",
            "res.set",
            "res.setHeader",
            "response.set",
            "response.setHeader",
        )
        .where("argument_index = ?", 1)
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, header_value in rows:
        if not _has_express_input(header_value):
            continue

        header_rows = db.query(
            Q("function_call_args")
            .select("argument_expr")
            .where("file = ?", file)
            .where("line = ?", line)
            .where("argument_index = ?", 0)
        )

        header_list = list(header_rows)
        if not header_list:
            continue

        header_name = header_list[0][0] or ""
        dangerous_headers = ["content-type", "x-xss-protection", "link", "refresh", "location"]

        if any(h in header_name.lower() for h in dangerous_headers):
            findings.append(
                StandardFinding(
                    rule_name="express-header-injection",
                    message=f"Header Injection: {header_name} set with unsanitized user input",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="injection",
                    snippet=f"{func}({header_name}, req.body...)",
                    cwe_id="CWE-113",
                )
            )

    return findings


def _check_jsonp_callback(db: RuleDB) -> list[StandardFinding]:
    """Check for JSONP callback injection."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line")
        .where("callee_function IN (?, ?)", "res.jsonp", "response.jsonp")
        .order_by("file, line")
    )

    for file, line in rows:
        assignment_rows = db.query(
            Q("assignments")
            .select("target_var", "source_expr")
            .where("file = ?", file)
            .where("line BETWEEN ? AND ?", max(1, line - 10), line + 5)
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
        )

        for target_var, source_expr in assignment_rows:
            is_callback_var = "callback" in target_var.lower()
            has_user_input = "req.query" in source_expr or "req.params" in source_expr

            if is_callback_var and has_user_input:
                findings.append(
                    StandardFinding(
                        rule_name="express-jsonp-injection",
                        message="JSONP Callback Injection: User controls callback function name",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="xss",
                        snippet="res.jsonp(data) with user-controlled callback",
                        cwe_id="CWE-79",
                    )
                )
                break

    return findings
