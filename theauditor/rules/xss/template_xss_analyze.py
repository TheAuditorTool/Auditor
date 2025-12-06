"""Template Injection and XSS Detection.

Detects server-side template injection (SSTI) and template XSS:
- Template string injection with user input
- Unsafe template syntax (|safe, |raw, {{{, etc.)
- Dynamic template compilation
- Disabled auto-escaping
- Unsafe custom helpers/filters
- SSTI exploitation patterns (__class__, __mro__, etc.)
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
    TEMPLATE_COMPILE_FUNCTIONS,
    TEMPLATE_ENGINES,
    TEMPLATE_TARGET_EXTENSIONS,
)

METADATA = RuleMetadata(
    name="template_injection",
    category="xss",
    target_extensions=TEMPLATE_TARGET_EXTENSIONS,
    exclude_patterns=["test/", "__tests__/", "node_modules/", "*.test.js"],
    execution_scope="database",
    primary_table="function_call_args",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect template injection and XSS vulnerabilities.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings: list[StandardFinding] = []

        findings.extend(_check_template_string_injection(db))
        findings.extend(_check_unsafe_template_syntax(db))
        findings.extend(_check_dynamic_template_compilation(db))
        findings.extend(_check_template_autoescape_disabled(db))
        findings.extend(_check_custom_template_helpers(db))
        findings.extend(_check_server_side_template_injection(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_template_string_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for template string injection with user input."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("""callee_function IN (
            'render_template_string', 'from_string',
            'Template', 'jinja2.Template',
            'django.template.Template'
        )""")
        .where("argument_index = 0")
        .order_by("file, line")
    )

    for file, line, func, template_arg in rows:
        has_user_input = any(src in (template_arg or "") for src in COMMON_INPUT_SOURCES)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="template-string-injection",
                    message=f"Template Injection: {func} with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    snippet=f"{func}(request.form.template)",
                    cwe_id="CWE-94",
                )
            )

        if (
            "+" in (template_arg or "")
            or 'f"' in (template_arg or "")
            or "`" in (template_arg or "")
        ):
            findings.append(
                StandardFinding(
                    rule_name="template-dynamic-construction",
                    message="Template Injection: Dynamic template construction",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    snippet=f"{func}(base_template + user_content)",
                    cwe_id="CWE-94",
                )
            )

    return findings


def _check_unsafe_template_syntax(db: RuleDB) -> list[StandardFinding]:
    """Check for unsafe template syntax usage."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "source_expr")
        .where("source_expr IS NOT NULL")
        .where(
            "source_expr LIKE ? OR source_expr LIKE ? OR source_expr LIKE ? OR "
            "source_expr LIKE ? OR source_expr LIKE ? OR source_expr LIKE ? OR "
            "source_expr LIKE ? OR source_expr LIKE ?",
            "%|safe%",
            "%|raw%",
            "%{{{%",
            "%Markup(%",
            "%mark_safe%",
            "%SafeString%",
            "%autoescape%",
            "%{!!%",
        )
        .order_by("file, line")
    )

    for file, line, source in rows:
        for engine, patterns in TEMPLATE_ENGINES.items():
            for unsafe_pattern in patterns.get("unsafe", []):
                if unsafe_pattern in (source or ""):
                    has_user_input = any(src in source for src in COMMON_INPUT_SOURCES)

                    if has_user_input:
                        normalized = (source or "").replace(" ", "")
                        if (
                            engine == "mako"
                            and unsafe_pattern.lower() == "|n"
                            and "|n" not in normalized
                        ):
                            continue
                        if (
                            engine == "mako"
                            and unsafe_pattern.lower() == "|h"
                            and "|h" not in normalized
                        ):
                            continue

                        findings.append(
                            StandardFinding(
                                rule_name=f"{engine}-unsafe-syntax",
                                message=f'XSS: {engine} unsafe pattern "{unsafe_pattern}" with user input',
                                file_path=file,
                                line=line,
                                severity=Severity.HIGH,
                                category="xss",
                                snippet=f"{unsafe_pattern} with user data",
                                cwe_id="CWE-79",
                            )
                        )

        has_unescaped = (
            ("{{{" in source and "}}}" in source)
            or ("<%-%" in source and "%>" in source)
            or ("!{" in source and "}" in source)
        )

        if has_unescaped:
            has_user_input = any(src in (source or "") for src in COMMON_INPUT_SOURCES)

            if has_user_input:
                snippet = source[:80] if len(source or "") > 80 else source
                findings.append(
                    StandardFinding(
                        rule_name="template-unescaped-output",
                        message="XSS: Unescaped template output with user input",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="xss",
                        snippet=snippet,
                        cwe_id="CWE-79",
                    )
                )

    return findings


def _check_dynamic_template_compilation(db: RuleDB) -> list[StandardFinding]:
    """Check for dynamic template compilation."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("argument_index = 0")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, callee, template_source in rows:
        is_compile_func = any(compile_func in callee for compile_func in TEMPLATE_COMPILE_FUNCTIONS)
        if not is_compile_func:
            continue

        has_user_input = any(src in (template_source or "") for src in COMMON_INPUT_SOURCES)

        has_external = any(
            ext in (template_source or "")
            for ext in ["database", "fetch", "ajax", "xhr", "readFile", "localStorage"]
        )

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="template-compile-user-input",
                    message=f"Template Injection: {callee} with user input",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    snippet=f"{callee}(userTemplate)",
                    cwe_id="CWE-94",
                )
            )
        elif has_external:
            findings.append(
                StandardFinding(
                    rule_name="template-compile-external",
                    message=f"Template Injection: {callee} with external source",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="injection",
                    snippet=f"{callee}(fetchedTemplate)",
                    cwe_id="CWE-94",
                )
            )

    return findings


def _check_template_autoescape_disabled(db: RuleDB) -> list[StandardFinding]:
    """Check for disabled auto-escaping in templates."""
    findings: list[StandardFinding] = []

    autoescape_patterns = [
        "autoescape off",
        "autoescape false",
        "autoescape=False",
        "autoescape: false",
        '"autoescape": false',
        "AUTOESCAPE = False",
        "config.autoescape = false",
    ]

    rows = db.query(
        Q("assignments")
        .select("file", "line", "source_expr")
        .where("source_expr IS NOT NULL")
        .where("source_expr LIKE ?", "%autoescape%")
        .order_by("file, line")
    )

    for file, line, source in rows:
        matched_pattern = next((p for p in autoescape_patterns if p in source), None)

        if matched_pattern:
            findings.append(
                StandardFinding(
                    rule_name="template-autoescape-disabled",
                    message="XSS: Template auto-escaping disabled",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="configuration",
                    snippet=matched_pattern,
                    cwe_id="CWE-79",
                )
            )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        is_environment = "Environment" in func
        has_autoescape = "autoescape" in (args or "")

        if not (is_environment and has_autoescape):
            continue

        if "False" in (args or "") or "false" in (args or ""):
            findings.append(
                StandardFinding(
                    rule_name="jinja2-autoescape-disabled",
                    message="XSS: Jinja2 Environment with autoescape disabled",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="configuration",
                    snippet="Environment(autoescape=False)",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_custom_template_helpers(db: RuleDB) -> list[StandardFinding]:
    """Check for unsafe custom template helpers/filters."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, filter_def in rows:
        is_filter = (
            ".filters[" in func or "app.jinja_env.filters" in func or func == "register.filter"
        )
        if not is_filter:
            continue

        if "Markup" in (filter_def or "") or "mark_safe" in (filter_def or ""):
            findings.append(
                StandardFinding(
                    rule_name="template-unsafe-filter",
                    message="XSS: Custom template filter returns unescaped HTML",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet="Custom filter with Markup/mark_safe",
                    cwe_id="CWE-79",
                )
            )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where("callee_function IN (?, ?)", "Handlebars.registerHelper", "registerHelper")
        .order_by("file, line")
    )

    for file, line, helper_def in rows:
        if "SafeString" in (helper_def or "") or "new Handlebars.SafeString" in (helper_def or ""):
            findings.append(
                StandardFinding(
                    rule_name="handlebars-unsafe-helper",
                    message="XSS: Handlebars helper returns SafeString (unescaped)",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="xss",
                    snippet="Handlebars.SafeString(userContent)",
                    cwe_id="CWE-79",
                )
            )

    return findings


def _check_server_side_template_injection(db: RuleDB) -> list[StandardFinding]:
    """Check for server-side template injection (SSTI)."""
    findings: list[StandardFinding] = []

    dangerous_template_patterns = [
        ".__class__",
        ".__mro__",
        ".__subclasses__",
        ".__globals__",
        ".__builtins__",
        ".__import__",
        "config.",
        "self.",
        "lipsum.",
        "cycler.",
        "|attr(",
        "|format(",
        "getattr(",
        "{{config",
        "{{self",
        "{{request",
        "${__",
        "#{__",
    ]

    assignment_rows = list(
        db.query(
            Q("assignments")
            .select("file", "line", "source_expr")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )
    )

    render_funcs = list(
        db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function")
            .where("callee_function IS NOT NULL")
        )
    )

    for pattern in dangerous_template_patterns:
        needs_proximity_check = pattern in ["config.", "self."]

        if needs_proximity_check:
            for file, line, source in assignment_rows:
                if pattern not in source:
                    continue

                has_nearby_render = False
                for rf_file, rf_line, rf_func in render_funcs:
                    if rf_file != file:
                        continue

                    is_render_func = (
                        rf_func
                        in (
                            "render_template_string",
                            "render",
                            "compile",
                            "ejs.render",
                            "ejs.compile",
                            "Handlebars.compile",
                        )
                        or "render" in rf_func
                        or "compile" in rf_func
                    )

                    if is_render_func and abs(rf_line - line) <= 20:
                        has_nearby_render = True
                        break

                if not has_nearby_render:
                    continue

                snippet = source[:80] if len(source or "") > 80 else source
                findings.append(
                    StandardFinding(
                        rule_name="ssti-dangerous-pattern",
                        message=f'SSTI: Dangerous template pattern "{pattern}"',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="injection",
                        snippet=snippet,
                        cwe_id="CWE-94",
                    )
                )
        else:
            for file, line, source in assignment_rows:
                if pattern not in source:
                    continue

                snippet = source[:80] if len(source or "") > 80 else source
                findings.append(
                    StandardFinding(
                        rule_name="ssti-dangerous-pattern",
                        message=f'SSTI: Dangerous template pattern "{pattern}"',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category="injection",
                        snippet=snippet,
                        cwe_id="CWE-94",
                    )
                )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IN (?, ?, ?)", "render_template", "render", "include")
        .where("argument_index = 0")
        .order_by("file, line")
    )

    for file, line, func, template_name in rows:
        has_user_input = any(src in (template_name or "") for src in COMMON_INPUT_SOURCES)

        if has_user_input:
            findings.append(
                StandardFinding(
                    rule_name="ssti-user-template-name",
                    message="SSTI: User controls template name/path",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    snippet=f"{func}(request.args.template)",
                    cwe_id="CWE-94",
                )
            )

    template_directives = ["{% include", "{% extends", "{% import"]
    user_input_indicators = ["request.", "params.", "user."]

    for file, line, source in assignment_rows:
        has_directive = any(directive in source for directive in template_directives)
        if not has_directive:
            continue

        has_user_input = any(indicator in source for indicator in user_input_indicators)
        if not has_user_input:
            continue

        findings.append(
            StandardFinding(
                rule_name="ssti-dynamic-include",
                message="SSTI: Dynamic template include/extend with user input",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="injection",
                snippet="{% include request.args.partial %}",
                cwe_id="CWE-94",
            )
        )

    return findings
