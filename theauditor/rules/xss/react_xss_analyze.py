"""React-specific XSS Detection.

Detects XSS vulnerabilities specific to React applications:
- dangerouslySetInnerHTML with user input
- javascript: URLs in href/src props
- Direct DOM manipulation via refs
- Dynamic component injection
- Server-side rendering vulnerabilities
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
    REACT_INPUT_SOURCES,
    SANITIZER_CALL_PATTERNS,
)

METADATA = RuleMetadata(
    name="react_xss",
    category="xss",
    target_extensions=[".jsx", ".tsx", ".js", ".ts"],
    exclude_patterns=["test/", "__tests__/", "node_modules/", "*.test.jsx", "*.spec.tsx"],
    execution_scope="database",
    primary_table="react_components",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect React-specific XSS vulnerabilities."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        if not _is_react_app(db):
            return RuleResult(findings=findings, manifest=db.get_manifest())

        findings.extend(_check_dangerous_html_prop(db))
        findings.extend(_check_javascript_urls(db))
        findings.extend(_check_ref_innerhtml(db))
        findings.extend(_check_component_injection(db))
        findings.extend(_check_server_side_rendering(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _is_react_app(db: RuleDB) -> bool:
    """Check if this is a React application."""
    framework_rows = db.query(
        Q("frameworks")
        .select("name")
        .where("name IN (?, ?, ?)", "react", "React", "react.js")
        .where("language = ?", "javascript")
    )

    if len(list(framework_rows)) > 0:
        return True

    component_rows = db.query(Q("react_components").select("name").limit(1))

    return len(list(component_rows)) > 0


def _has_user_input(expr: str) -> bool:
    """Check if expression contains React user input sources."""
    return any(src in expr for src in REACT_INPUT_SOURCES)


def _is_sanitized(expr: str) -> bool:
    """Check if expression is properly sanitized."""
    return any(pattern in expr for pattern in SANITIZER_CALL_PATTERNS)


def _check_dangerous_html_prop(db: RuleDB) -> list[StandardFinding]:
    """Check for dangerouslySetInnerHTML with user input."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "source_expr")
        .where("source_expr IS NOT NULL")
        .where("source_expr LIKE ?", "%dangerouslySetInnerHTML%")
        .where("source_expr LIKE ?", "%__html%")
    )

    for file, line, source in rows:
        if _is_sanitized(source):
            continue

        has_user_input = _has_user_input(source)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="react-xss-dangerous-html",
                    message="XSS: dangerouslySetInnerHTML with unsanitized user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=source[:100] + "..." if len(source) > 100 else source,
                    cwe_id="CWE-79",
                )
            )

    markup_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .where(
            "callee_function LIKE ? OR callee_function LIKE ? OR callee_function LIKE ?",
            "%createMarkup%",
            "%getRawMarkup%",
            "%getHTML%",
        )
    )

    for file, line, func, args in markup_rows:
        if _is_sanitized(args):
            continue

        has_user_input = _has_user_input(args)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="react-xss-markup-function",
                    message=f"XSS: {func} creates HTML from unsanitized user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=f"{func}({args[:50]}...)" if len(args) > 50 else f"{func}({args})",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_javascript_urls(db: RuleDB) -> list[StandardFinding]:
    """Check for javascript: URLs in href/src props."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "param_name", "argument_expr")
        .where("param_name IN (?, ?, ?, ?)", "href", "src", "action", "formAction")
        .where("argument_expr IS NOT NULL")
    )

    for file, line, prop, value in rows:
        has_dangerous_protocol = any(
            proto in value.lower() for proto in ["javascript:", "vbscript:", "data:text/html"]
        )
        has_user_input = _has_user_input(value)

        if has_dangerous_protocol and has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="react-xss-javascript-url",
                    message=f"XSS: {prop} prop with dangerous URL protocol and user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=f"{prop}={{{value[:40]}...}}"
                    if len(value) > 40
                    else f"{prop}={{{value}}}",
                    cwe_id="CWE-79",
                )
            )
        elif has_user_input and prop == "href":
            findings.append(
                StandardFinding(
                    rule_name="react-xss-unsafe-href",
                    message="XSS: href prop with user input - validate URL protocol",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet=f"href={{{value[:40]}...}}" if len(value) > 40 else f"href={{{value}}}",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_ref_innerhtml(db: RuleDB) -> list[StandardFinding]:
    """Check for direct DOM manipulation via refs."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
        .where(
            "target_var LIKE ? OR target_var LIKE ? OR target_var LIKE ?",
            "%ref.current.innerHTML%",
            "%.current.innerHTML%",
            "%Ref.current.innerHTML%",
        )
    )

    for file, line, target, source in rows:
        if _is_sanitized(source):
            continue

        has_user_input = _has_user_input(source)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="react-xss-ref-innerhtml",
                    message="XSS: Direct innerHTML manipulation via React ref with unsanitized input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="xss",
                    snippet=f"{target} = {source[:50]}..."
                    if len(source) > 50
                    else f"{target} = {source}",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_component_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for dynamic component injection vulnerabilities."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?)", "React.createElement", "createElement")
        .where("argument_index = ?", 0)
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, component_arg in rows:
        has_user_input = _has_user_input(component_arg)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="react-component-injection",
                    message="Component Injection: Dynamic component type from user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    snippet=f"{func}({component_arg[:30]}..., ...)",
                    cwe_id="CWE-74",
                )
            )

    new_func_rows = db.query(
        Q("assignments")
        .select("file", "line", "source_expr")
        .where("source_expr IS NOT NULL")
        .where("source_expr LIKE ?", "%new Function%")
    )

    for file, line, source in new_func_rows:
        has_user_input = _has_user_input(source)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="react-code-injection",
                    message="Code Injection: new Function() with user input in React component",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    snippet="new Function(userInput)",
                    cwe_id="CWE-94",
                )
            )

    return findings


def _check_server_side_rendering(db: RuleDB) -> list[StandardFinding]:
    """Check for SSR-specific XSS vulnerabilities."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(
            "callee_function IN (?, ?, ?, ?)",
            "renderToString",
            "renderToStaticMarkup",
            "ReactDOMServer.renderToString",
            "ReactDOMServer.renderToStaticMarkup",
        )
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not args:
            continue

        has_user_input = _has_user_input(args)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="react-ssr-xss",
                    message="SSR XSS: Server-side rendering with unsanitized user input",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    snippet=f"{func}(<Component userInput=... />)",
                    cwe_id="CWE-79",
                )
            )

    hydrate_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where(
            "callee_function IN (?, ?, ?, ?)",
            "hydrate",
            "ReactDOM.hydrate",
            "hydrateRoot",
            "ReactDOM.hydrateRoot",
        )
        .order_by("file, line")
    )

    for file, line, func in hydrate_rows:
        nearby_rows = db.query(
            Q("assignments")
            .select("target_var", "source_expr")
            .where("file = ?", file)
            .where("line BETWEEN ? AND ?", max(1, line - 20), line + 20)
        )

        has_unsafe_html = False
        for target_var, source_expr in nearby_rows:
            target = target_var or ""
            source = source_expr or ""
            if ".innerHTML" in target or "__html" in source:
                has_unsafe_html = True
                break

        if has_unsafe_html:
            findings.append(
                StandardFinding(
                    rule_name="react-hydration-xss",
                    message="XSS: React hydration with potentially unsafe initial HTML",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet=f"{func}(...) with unsafe initial HTML",
                    cwe_id="CWE-79",
                )
            )

    return findings
