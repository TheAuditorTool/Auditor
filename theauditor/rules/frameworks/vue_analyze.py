"""Vue.js Framework Security Analyzer.

Detects security vulnerabilities in Vue.js applications including:
- v-html and innerHTML binding XSS (CWE-79)
- eval() in Vue components (CWE-95)
- Exposed API keys (CWE-200)
- Unescaped interpolation in Vue 1.x (CWE-79)
- Dynamic component injection (CWE-470)
- Unsafe target="_blank" links (CWE-1022)
- Direct DOM manipulation via $refs (CWE-79)
- Sensitive data in localStorage/sessionStorage (CWE-922)
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
    name="vue_security",
    category="frameworks",
    target_extensions=[".vue", ".js", ".ts"],
    exclude_patterns=["node_modules/", "test/", "spec.", "__tests__/"],
    execution_scope="database",
    primary_table="function_call_args",
)


VUE_XSS_DIRECTIVES = frozenset(
    [
        "v-html",
        ":innerHTML",
        "v-bind:innerHTML",
        "v-bind:outerHTML",
        ":outerHTML",
    ]
)


SENSITIVE_PATTERNS = frozenset(
    [
        "KEY",
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "PRIVATE",
        "API_KEY",
        "CREDENTIAL",
        "AUTH",
    ]
)


VUE_ENV_PREFIXES = frozenset(
    [
        "VUE_APP_",
        "VITE_",
        "NUXT_ENV_",
    ]
)


DANGEROUS_FUNCTIONS = frozenset(
    [
        "eval",
        "Function",
        "setTimeout",
        "setInterval",
        "document.write",
        "document.writeln",
    ]
)


DOM_MANIPULATION = frozenset(
    [
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.getElementById",
        "document.querySelector",
        "document.getElementsByClassName",
        "document.getElementsByTagName",
    ]
)


VUE_INPUT_SOURCES = frozenset(
    [
        "$route.params",
        "$route.query",
        "this.$route",
        "props.",
        "v-model",
        "$emit",
        "$attrs",
        "$listeners",
    ]
)


VUE_ADDITIONAL_SINKS = frozenset(
    [
        "$refs.innerHTML",
        "$refs.outerHTML",
        "this.$refs",
        "vm.$refs",
    ]
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Vue.js security vulnerabilities using indexed data.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        findings.extend(_check_v_html_xss(db))
        findings.extend(_check_eval_injection(db))
        findings.extend(_check_exposed_api_keys(db))
        findings.extend(_check_unescaped_interpolation(db))
        findings.extend(_check_dynamic_component_injection(db))
        findings.extend(_check_unsafe_target_blank(db))
        findings.extend(_check_refs_dom_manipulation(db))
        findings.extend(_check_direct_dom_access(db))
        findings.extend(_check_insecure_storage(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_v_html_xss(db: RuleDB) -> list[StandardFinding]:
    """Check for v-html and innerHTML binding - primary XSS vector in Vue.

    Detection strategy:
    1. Assignments containing v-html directives (template extraction)
    2. Vue render function calls (h, createVNode) with innerHTML in props
    3. Object literals with innerHTML/domProps properties
    """
    findings = []
    seen = set()

    assignment_rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where(
            "source_expr LIKE ? OR source_expr LIKE ? OR source_expr LIKE ?",
            "%v-html%",
            "%innerHTML%",
            "%outerHTML%",
        )
        .order_by("file, line")
    )

    for file, line, _target, html_content in assignment_rows:
        if not html_content:
            continue
        if any(pattern in html_content for pattern in VUE_XSS_DIRECTIVES):
            key = (file, line)
            if key not in seen:
                seen.add(key)
                findings.append(
                    StandardFinding(
                        rule_name="vue-v-html-xss",
                        message="Use of v-html or innerHTML binding - primary XSS vector in Vue",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="xss",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-79",
                        snippet=html_content[:80] if len(html_content) > 80 else html_content,
                    )
                )

    render_rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where(
            "callee_function IN (?, ?, ?, ?) AND argument_expr LIKE ?",
            "h",
            "createVNode",
            "_createElementVNode",
            "createElementVNode",
            "%innerHTML%",
        )
        .order_by("file, line")
    )

    for file, line, callee, args in render_rows:
        key = (file, line)
        if key not in seen:
            seen.add(key)
            findings.append(
                StandardFinding(
                    rule_name="vue-v-html-xss",
                    message=f"Vue render function {callee}() with innerHTML - XSS risk",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-79",
                    snippet=args[:80] if args and len(args) > 80 else args,
                )
            )

    literal_rows = db.query(
        Q("object_literals")
        .select("file", "line", "property_name", "property_value")
        .where("property_name IN (?, ?, ?)", "innerHTML", "outerHTML", "domProps")
        .order_by("file, line")
    )

    for file, line, prop_name, prop_value in literal_rows:
        key = (file, line)
        if key not in seen:
            seen.add(key)
            findings.append(
                StandardFinding(
                    rule_name="vue-v-html-xss",
                    message=f"Object literal with {prop_name} property - XSS risk in Vue",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-79",
                    snippet=f"{prop_name}: {prop_value[:50]}" if prop_value else prop_name,
                )
            )

    return findings


def _check_eval_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for eval() usage in Vue components."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where("callee_function = ?", "eval")
        .order_by("file, line")
    )

    for file, line, eval_content in rows:
        if file.endswith(".vue"):
            findings.append(
                StandardFinding(
                    rule_name="vue-eval-injection",
                    message="Using eval() in Vue component - code injection risk",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-95",
                    snippet=eval_content[:80]
                    if eval_content and len(eval_content) > 80
                    else eval_content,
                )
            )
            continue

        vue_refs = db.query(
            Q("refs")
            .select("src")
            .where("src = ? AND value IN (?, ?)", file, "vue", "Vue")
            .limit(1)
        )

        if vue_refs:
            findings.append(
                StandardFinding(
                    rule_name="vue-eval-injection",
                    message="Using eval() in Vue component - code injection risk",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-95",
                    snippet=eval_content[:80]
                    if eval_content and len(eval_content) > 80
                    else eval_content,
                )
            )

    return findings


def _check_exposed_api_keys(db: RuleDB) -> list[StandardFinding]:
    """Check for exposed API keys in Vue components."""
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var", "source_expr").order_by("file, line")
    )

    for file, line, var_name, value in rows:
        if not var_name:
            continue

        has_vue_prefix = any(var_name.startswith(prefix) for prefix in VUE_ENV_PREFIXES)
        if not has_vue_prefix:
            continue

        var_upper = var_name.upper()
        if not any(pattern in var_upper for pattern in SENSITIVE_PATTERNS):
            continue

        if value and ("process.env" in value or "import.meta.env" in value):
            continue

        findings.append(
            StandardFinding(
                rule_name="vue-exposed-api-key",
                message=f"API key/secret {var_name} hardcoded in Vue component",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="security",
                confidence=Confidence.HIGH,
                cwe_id="CWE-200",
                snippet=f"{var_name} = {value[:40]}..."
                if value and len(value) > 40
                else f"{var_name} = {value}",
            )
        )

    return findings


def _check_unescaped_interpolation(db: RuleDB) -> list[StandardFinding]:
    """Check for triple mustache unescaped interpolation (Vue 1.x legacy)."""
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr LIKE ?", "%{{{%")
        .order_by("file, line")
    )

    for file, line, _target, interpolation in rows:
        if not interpolation:
            continue

        if "{{{" in interpolation and "}}}" in interpolation:
            findings.append(
                StandardFinding(
                    rule_name="vue-unescaped-interpolation",
                    message="Triple mustache {{{ }}} unescaped interpolation - XSS risk (Vue 1.x legacy)",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-79",
                    snippet=interpolation[:60] if len(interpolation) > 60 else interpolation,
                )
            )

    return findings


def _check_dynamic_component_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for dynamic component with user-controlled input."""
    findings = []

    user_input_sources = ["$route", "params", "query", "user", "input", "data"]

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr LIKE ? AND source_expr LIKE ?", "%<component%", "%:is%")
        .order_by("file, line")
    )

    for file, line, _target, component_code in rows:
        if not component_code:
            continue

        if "<component" not in component_code or ":is" not in component_code:
            continue

        if any(src in component_code for src in user_input_sources):
            findings.append(
                StandardFinding(
                    rule_name="vue-dynamic-component-injection",
                    message="Dynamic component with user-controlled input - component injection risk",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-470",
                    snippet=component_code[:80] if len(component_code) > 80 else component_code,
                )
            )

    return findings


def _check_unsafe_target_blank(db: RuleDB) -> list[StandardFinding]:
    """Check for unsafe target='_blank' without rel='noopener'."""
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

        if 'target="_blank"' not in link_code and "target='_blank'" not in link_code:
            continue

        if "noopener" in link_code or "noreferrer" in link_code:
            continue

        findings.append(
            StandardFinding(
                rule_name="vue-unsafe-target-blank",
                message='External link without rel="noopener" - reverse tabnabbing vulnerability',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category="security",
                confidence=Confidence.HIGH,
                cwe_id="CWE-1022",
                snippet=link_code[:80] if len(link_code) > 80 else link_code,
            )
        )

    return findings


def _check_refs_dom_manipulation(db: RuleDB) -> list[StandardFinding]:
    """Check for direct DOM manipulation via $refs."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not func:
            continue

        if "$refs" not in func and "this.$refs" not in func:
            continue

        if args and any(danger in args for danger in ["innerHTML", "outerHTML"]):
            findings.append(
                StandardFinding(
                    rule_name="vue-direct-dom-manipulation",
                    message="Direct DOM manipulation via $refs bypassing Vue security",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="xss",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-79",
                    snippet=f"{func}({args[:50]})"
                    if args and len(args) > 50
                    else f"{func}({args})",
                )
            )

    return findings


def _check_direct_dom_access(db: RuleDB) -> list[StandardFinding]:
    """Check for direct DOM access anti-pattern in Vue components."""
    findings = []

    for dom_method in DOM_MANIPULATION:
        rows = db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function")
            .where("callee_function = ?", dom_method)
            .order_by("file, line")
        )

        for file, line, callee in rows:
            if file.endswith(".vue"):
                findings.append(
                    StandardFinding(
                        rule_name="vue-anti-pattern-dom",
                        message=f"Direct DOM access with {callee} - anti-pattern in Vue",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="best-practice",
                        confidence=Confidence.MEDIUM,
                    )
                )
                continue

            vue_refs = db.query(
                Q("refs")
                .select("src")
                .where("src = ? AND value IN (?, ?)", file, "vue", "Vue")
                .limit(1)
            )

            if vue_refs:
                findings.append(
                    StandardFinding(
                        rule_name="vue-anti-pattern-dom",
                        message=f"Direct DOM access with {callee} - anti-pattern in Vue",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="best-practice",
                        confidence=Confidence.MEDIUM,
                    )
                )

    return findings


def _check_insecure_storage(db: RuleDB) -> list[StandardFinding]:
    """Check for sensitive data stored in localStorage/sessionStorage."""
    findings = []

    for storage_method in ["localStorage.setItem", "sessionStorage.setItem"]:
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
            if not any(
                sens in data_lower for sens in ["token", "password", "secret", "jwt", "key"]
            ):
                continue

            if file.endswith(".vue"):
                storage_type = "localStorage" if "localStorage" in callee else "sessionStorage"
                findings.append(
                    StandardFinding(
                        rule_name="vue-insecure-storage",
                        message=f"Sensitive data in {storage_type} - accessible to XSS attacks",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-922",
                        snippet=data[:60] if len(data) > 60 else data,
                    )
                )
                continue

            vue_refs = db.query(
                Q("refs")
                .select("src")
                .where("src = ? AND value IN (?, ?)", file, "vue", "Vue")
                .limit(1)
            )

            if vue_refs:
                storage_type = "localStorage" if "localStorage" in callee else "sessionStorage"
                findings.append(
                    StandardFinding(
                        rule_name="vue-insecure-storage",
                        message=f"Sensitive data in {storage_type} - accessible to XSS attacks",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-922",
                        snippet=data[:60] if len(data) > 60 else data,
                    )
                )

    return findings


def register_taint_patterns(taint_registry) -> None:
    """Register Vue.js-specific taint patterns for dataflow analysis."""
    for pattern in VUE_XSS_DIRECTIVES:
        taint_registry.register_sink(pattern, "xss", "javascript")

    for pattern in VUE_ADDITIONAL_SINKS:
        taint_registry.register_sink(pattern, "xss", "javascript")

    for pattern in VUE_INPUT_SOURCES:
        taint_registry.register_source(pattern, "user_input", "javascript")

    for pattern in DANGEROUS_FUNCTIONS:
        taint_registry.register_sink(pattern, "code_execution", "javascript")
