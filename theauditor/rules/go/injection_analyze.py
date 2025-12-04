"""Go Injection Vulnerability Analyzer - Database-First Approach."""

import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

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
    execution_scope="database")


@dataclass(frozen=True)
class GoInjectionPatterns:
    """Immutable pattern definitions for Go injection detection."""

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

    STRING_FORMAT_PATTERNS = frozenset(
        [
            "fmt.Sprintf",
            "fmt.Fprintf",
            "+",
            "strings.Join",
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
            "Prepare",
        ]
    )


class GoInjectionAnalyzer:
    """Analyzer for Go injection vulnerabilities."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context."""
        self.context = context
        self.patterns = GoInjectionPatterns()
        self.findings = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        conn.row_factory = sqlite3.Row
        self.cursor = conn.cursor()

        try:
            self._check_sql_injection()
            self._check_command_injection()
            self._check_template_injection()
            self._check_path_traversal()
            self._check_sprintf_in_sql()

        finally:
            conn.close()

        return self.findings

    def _check_sql_injection(self):
        """Detect SQL injection via string formatting in queries."""

        self.cursor.execute("""
            SELECT file_path, line, name, signature
            FROM go_functions
            WHERE name IN ('Query', 'QueryRow', 'Exec', 'Raw', 'Where')
        """)

        self.cursor.execute("""
            SELECT file_path, line, name, initial_value
            FROM go_variables
            WHERE initial_value LIKE '%fmt.Sprintf%'
              AND (initial_value LIKE '%SELECT%'
                   OR initial_value LIKE '%INSERT%'
                   OR initial_value LIKE '%UPDATE%'
                   OR initial_value LIKE '%DELETE%')
        """)

        for row in self.cursor.fetchall():
            self.findings.append(
                StandardFinding(
                    rule_name="go-sql-injection",
                    message=f"SQL query built with fmt.Sprintf in variable '{row['name']}'",
                    file_path=row["file_path"],
                    line=row["line"],
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-89",
                )
            )

    def _check_command_injection(self):
        """Detect command injection via exec.Command with variables."""

        self.cursor.execute("""
            SELECT file_path, line, initial_value
            FROM go_variables
            WHERE initial_value LIKE '%exec.Command%'
              AND initial_value NOT LIKE '%exec.Command("%'
              AND initial_value NOT LIKE "%exec.Command('%"
        """)

        for row in self.cursor.fetchall():
            self.findings.append(
                StandardFinding(
                    rule_name="go-command-injection",
                    message="exec.Command with non-literal command - potential command injection",
                    file_path=row["file_path"],
                    line=row["line"],
                    severity=Severity.CRITICAL,
                    category="injection",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-78",
                )
            )

    def _check_template_injection(self):
        """Detect unsafe template usage (template.HTML with variable)."""

        self.cursor.execute("""
            SELECT file_path, line, initial_value
            FROM go_variables
            WHERE (initial_value LIKE '%template.HTML(%'
                   OR initial_value LIKE '%template.JS(%'
                   OR initial_value LIKE '%template.URL(%')
              AND initial_value NOT LIKE '%template.HTML("%'
              AND initial_value NOT LIKE "%template.HTML('%"
        """)

        for row in self.cursor.fetchall():
            self.findings.append(
                StandardFinding(
                    rule_name="go-template-injection",
                    message="Unsafe template type conversion with variable input",
                    file_path=row["file_path"],
                    line=row["line"],
                    severity=Severity.HIGH,
                    category="injection",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-79",
                )
            )

    def _check_path_traversal(self):
        """Detect path traversal via filepath.Join with user input."""

        self.cursor.execute("""
            SELECT file_path, line, initial_value
            FROM go_variables
            WHERE (initial_value LIKE '%filepath.Join%'
                   OR initial_value LIKE '%path.Join%'
                   OR initial_value LIKE '%os.Open(%')
              AND (initial_value LIKE '%r.URL%'
                   OR initial_value LIKE '%c.Param%'
                   OR initial_value LIKE '%c.Query%'
                   OR initial_value LIKE '%ctx.Param%')
        """)

        for row in self.cursor.fetchall():
            self.findings.append(
                StandardFinding(
                    rule_name="go-path-traversal",
                    message="Path operation with user-controlled input - potential path traversal",
                    file_path=row["file_path"],
                    line=row["line"],
                    severity=Severity.HIGH,
                    category="injection",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-22",
                )
            )

    def _check_sprintf_in_sql(self):
        """Detect fmt.Sprintf used to build SQL queries."""

        self.cursor.execute("""
            SELECT file_path, line, name, initial_value
            FROM go_variables
            WHERE initial_value LIKE '%fmt.Sprintf%'
              AND (UPPER(initial_value) LIKE '%SELECT %'
                   OR UPPER(initial_value) LIKE '%INSERT %'
                   OR UPPER(initial_value) LIKE '%UPDATE %'
                   OR UPPER(initial_value) LIKE '%DELETE %'
                   OR UPPER(initial_value) LIKE '%WHERE %')
        """)

        for row in self.cursor.fetchall():
            value = row["initial_value"] or ""
            if not any(safe in value for safe in ["?", "$1", ":name"]):
                self.findings.append(
                    StandardFinding(
                        rule_name="go-sql-sprintf",
                        message=f"SQL built with fmt.Sprintf without parameterization in '{row['name']}'",
                        file_path=row["file_path"],
                        line=row["line"],
                        severity=Severity.CRITICAL,
                        category="injection",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-89",
                    )
                )


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Go injection vulnerabilities."""
    analyzer = GoInjectionAnalyzer(context)
    return analyzer.analyze()


def register_taint_patterns(taint_registry):
    """Register Go injection-specific taint patterns."""
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
