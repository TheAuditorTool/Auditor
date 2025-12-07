"""Go Injection Vulnerability Analyzer.

Detects common Go injection vulnerabilities:
1. SQL injection via string formatting (fmt.Sprintf) - CWE-89
2. Command injection via exec.Command with variables - CWE-78
3. Template injection via unsafe template type conversions - CWE-79
4. Path traversal via filepath.Join with user input - CWE-22
"""

from dataclasses import dataclass

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
    name="go_injection",
    category="injection",
    target_extensions=[".go"],
    exclude_patterns=[
        "vendor/",
        "node_modules/",
        "testdata/",
        "_test.go",
    ],
    execution_scope="database",
    primary_table="go_variables",
)


@dataclass(frozen=True)
class GoInjectionPatterns:
    """Immutable pattern definitions for Go injection detection.

    Used by register_taint_patterns() for taint analysis integration.
    """

    SQL_METHODS = frozenset(
        [
            "Query",
            "QueryRow",
            "QueryContext",
            "QueryRowContext",
            "Exec",
            "ExecContext",
            "Prepare",
            "PrepareContext",
            "Raw",
            "Where",
            "Select",
            "Get",
            "NamedQuery",
            "NamedExec",
        ]
    )

    COMMAND_METHODS = frozenset(
        [
            "exec.Command",
            "exec.CommandContext",
            "os.StartProcess",
            "syscall.Exec",
            "syscall.ForkExec",
        ]
    )

    TEMPLATE_METHODS = frozenset(
        [
            "template.HTML",
            "template.HTMLAttr",
            "template.JS",
            "template.JSStr",
            "template.URL",
            "template.CSS",
        ]
    )

    PATH_METHODS = frozenset(
        [
            "filepath.Join",
            "path.Join",
            "os.Open",
            "os.OpenFile",
            "os.Create",
            "ioutil.ReadFile",
            "os.ReadFile",
            "os.WriteFile",
        ]
    )

    USER_INPUTS = frozenset(
        [
            "r.URL.Query",
            "r.FormValue",
            "r.PostFormValue",
            "r.Form",
            "r.PostForm",
            "r.Body",
            "c.Query",
            "c.Param",
            "c.PostForm",
            "c.BindJSON",
            "c.ShouldBind",
            "ctx.Query",
            "ctx.Param",
            "ctx.FormValue",
            "ctx.Body",
        ]
    )

    SAFE_PATTERNS = frozenset(
        [
            "?",
            "$1",
            "$2",
            ":name",
            "@name",
        ]
    )


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Go injection vulnerabilities.

    Args:
        context: Provides db_path and project context

    Returns:
        RuleResult with findings and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_sql_injection(db))
        findings.extend(_check_command_injection(db))
        findings.extend(_check_template_injection(db))
        findings.extend(_check_path_traversal(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_sql_injection(db: RuleDB) -> list[StandardFinding]:
    """Detect SQL injection via string formatting and concatenation.

    Detects:
    1. fmt.Sprintf building SQL queries with format specifiers
    2. String concatenation building SQL queries
    """
    findings = []

    sprintf_rows = db.query(
        Q("go_variables")
        .select("file", "line", "name", "initial_value")
        .where("initial_value LIKE ?", "%fmt.Sprintf%")
        .where(
            "UPPER(initial_value) LIKE ? OR UPPER(initial_value) LIKE ? "
            "OR UPPER(initial_value) LIKE ? OR UPPER(initial_value) LIKE ? "
            "OR UPPER(initial_value) LIKE ?",
            "%SELECT %",
            "%INSERT %",
            "%UPDATE %",
            "%DELETE %",
            "%WHERE %",
        )
    )

    for file_path, line, name, initial_value in sprintf_rows:
        value = initial_value or ""

        has_safe_patterns = any(safe in value for safe in GoInjectionPatterns.SAFE_PATTERNS)
        has_format_specifiers = "%s" in value or "%v" in value or "%d" in value

        if has_safe_patterns and has_format_specifiers:
            findings.append(
                StandardFinding(
                    rule_name="go-sql-injection-partial",
                    message=f"SQL in '{name}' has parameterization but also format specifiers - possible table/column name injection",
                    file_path=file_path,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    confidence=Confidence.LOW,
                    cwe_id="CWE-89",
                )
            )
        elif not has_safe_patterns:
            findings.append(
                StandardFinding(
                    rule_name="go-sql-injection",
                    message=f"SQL built with fmt.Sprintf without parameterization in '{name}'",
                    file_path=file_path,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-89",
                )
            )

    concat_rows = db.query(
        Q("go_variables")
        .select("file", "line", "name", "initial_value")
        .where("initial_value LIKE ?", "%+%")
        .where(
            "UPPER(initial_value) LIKE ? OR UPPER(initial_value) LIKE ? "
            "OR UPPER(initial_value) LIKE ? OR UPPER(initial_value) LIKE ? "
            "OR UPPER(initial_value) LIKE ?",
            "%SELECT %",
            "%INSERT %",
            "%UPDATE %",
            "%DELETE %",
            "%WHERE %",
        )
    )

    for file_path, line, name, initial_value in concat_rows:
        value = initial_value or ""

        if "fmt.Sprintf" in value:
            continue

        has_sql_string = (
            '"SELECT' in value
            or '"INSERT' in value
            or '"UPDATE' in value
            or '"DELETE' in value
            or '"WHERE' in value
            or "'SELECT" in value
        )

        if has_sql_string:
            findings.append(
                StandardFinding(
                    rule_name="go-sql-injection-concat",
                    message=f"SQL built with string concatenation in '{name}' - use parameterized queries",
                    file_path=file_path,
                    line=line,
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-89",
                )
            )

    return findings


def _check_command_injection(db: RuleDB) -> list[StandardFinding]:
    """Detect command injection via exec.Command and related methods.

    Command execution with non-literal first argument is dangerous as it
    allows attackers to inject arbitrary commands.
    """
    findings = []

    command_methods = list(GoInjectionPatterns.COMMAND_METHODS)
    like_clauses = " OR ".join(["initial_value LIKE ?" for _ in command_methods])
    like_params = [f"%{method}%" for method in command_methods]

    rows = db.query(
        Q("go_variables")
        .select("file", "line", "initial_value")
        .where(like_clauses, *like_params)
    )

    for file_path, line, initial_value in rows:
        value = initial_value or ""

        matched_method = None
        for method in command_methods:
            if method in value:
                matched_method = method
                break

        if not matched_method:
            continue

        if f'{matched_method}("' in value or f"{matched_method}('" in value:
            continue

        findings.append(
            StandardFinding(
                rule_name="go-command-injection",
                message=f"{matched_method} with non-literal command - potential command injection",
                file_path=file_path,
                line=line,
                severity=Severity.CRITICAL,
                category="injection",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-78",
            )
        )

    return findings


def _check_template_injection(db: RuleDB) -> list[StandardFinding]:
    """Detect unsafe template usage.

    template.HTML, template.JS, template.URL with variable input
    bypasses Go's template auto-escaping, enabling XSS.
    """
    findings = []

    rows = db.query(
        Q("go_variables")
        .select("file", "line", "initial_value")
        .where(
            "initial_value LIKE ? OR initial_value LIKE ? OR initial_value LIKE ?",
            "%template.HTML(%",
            "%template.JS(%",
            "%template.URL(%",
        )
    )

    for file_path, line, initial_value in rows:
        value = initial_value or ""

        if (
            'template.HTML("' in value
            or "template.HTML('" in value
            or 'template.JS("' in value
            or "template.JS('" in value
            or 'template.URL("' in value
            or "template.URL('" in value
        ):
            continue

        findings.append(
            StandardFinding(
                rule_name="go-template-injection",
                message="Unsafe template type conversion with variable input",
                file_path=file_path,
                line=line,
                severity=Severity.HIGH,
                category="injection",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-79",
            )
        )

    return findings


def _check_path_traversal(db: RuleDB) -> list[StandardFinding]:
    """Detect path traversal via filepath.Join with user input.

    User-controlled paths passed to file operations can allow
    attackers to access files outside the intended directory.
    """
    findings = []

    rows = db.query(
        Q("go_variables")
        .select("file", "line", "initial_value")
        .where(
            "initial_value LIKE ? OR initial_value LIKE ? OR initial_value LIKE ?",
            "%filepath.Join%",
            "%path.Join%",
            "%os.Open(%",
        )
    )

    for file_path, line, initial_value in rows:
        value = initial_value or ""

        user_input_present = any(
            pattern in value
            for pattern in [
                "r.URL",
                "c.Param",
                "c.Query",
                "ctx.Param",
                "r.FormValue",
                "r.PostFormValue",
            ]
        )

        if user_input_present:
            findings.append(
                StandardFinding(
                    rule_name="go-path-traversal",
                    message="Path operation with user-controlled input - potential path traversal",
                    file_path=file_path,
                    line=line,
                    severity=Severity.HIGH,
                    category="injection",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-22",
                )
            )

    return findings


def register_taint_patterns(taint_registry):
    """Register Go injection-specific taint patterns.

    Called by taint analysis engine to configure Go-specific
    sources, sinks, and sanitizers for dataflow analysis.
    """
    patterns = GoInjectionPatterns()

    for pattern in patterns.USER_INPUTS:
        taint_registry.register_source(pattern, "user_input", "go")

    for pattern in patterns.SQL_METHODS:
        taint_registry.register_sink(pattern, "sql", "go")

    for pattern in patterns.COMMAND_METHODS:
        taint_registry.register_sink(pattern, "command", "go")

    for pattern in patterns.TEMPLATE_METHODS:
        taint_registry.register_sink(pattern, "template", "go")

    for pattern in patterns.PATH_METHODS:
        taint_registry.register_sink(pattern, "path", "go")
