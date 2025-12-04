"""Bash Command Injection Analyzer - Detects shell injection vulnerabilities."""

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
    name="bash_injection",
    category="injection",
    target_extensions=[".sh", ".bash"],
    exclude_patterns=["node_modules/", "vendor/", ".git/"],
    execution_scope="database")


@dataclass(frozen=True)
class BashInjectionPatterns:
    """Pattern definitions for Bash injection detection."""

    # Commands that evaluate code dynamically
    EVAL_COMMANDS: frozenset = frozenset(["eval", "bash", "sh", "zsh", "ksh"])

    # Commands where variable-as-command is dangerous
    COMMAND_EXECUTION: frozenset = frozenset(["xargs", "find", "parallel", "watch", "exec"])

    # Dangerous flags for xargs
    XARGS_DANGEROUS_FLAGS: frozenset = frozenset(["-I", "-i", "-0"])


class BashInjectionAnalyzer:
    """Analyzer for Bash injection vulnerabilities."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context."""
        self.context = context
        self.patterns = BashInjectionPatterns()
        self.findings: list[StandardFinding] = []
        self.seen: set[str] = set()

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        conn.row_factory = sqlite3.Row
        self.cursor = conn.cursor()

        self._check_eval_injection()
        self._check_variable_as_command()
        self._check_xargs_injection()
        self._check_backtick_injection()
        self._check_source_injection()

        conn.close()

        return self.findings

    def _add_finding(
        self,
        file: str,
        line: int,
        rule_name: str,
        message: str,
        severity: Severity,
        confidence: Confidence = Confidence.HIGH,
        cwe_id: str = "CWE-78",
    ) -> None:
        """Add a finding if not already seen."""
        key = f"{file}:{line}:{rule_name}"
        if key in self.seen:
            return
        self.seen.add(key)

        self.findings.append(
            StandardFinding(
                rule_name=rule_name,
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category="injection",
                confidence=confidence,
                cwe_id=cwe_id,
            )
        )

    def _check_eval_injection(self) -> None:
        """Detect eval with variable arguments."""
        self.cursor.execute("""
            SELECT c.file, c.line, c.command_name, a.arg_value, a.has_expansion
            FROM bash_commands c
            LEFT JOIN bash_command_args a
                ON c.file = a.file
                AND c.line = a.command_line
                AND c.pipeline_position IS a.command_pipeline_position
            WHERE c.command_name = 'eval'
        """)

        for row in self.cursor.fetchall():
            file = row["file"]
            line = row["line"]
            arg_value = row["arg_value"] or ""
            has_expansion = row["has_expansion"]

            # eval with any variable expansion is dangerous
            if has_expansion or "$" in arg_value:
                self._add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-eval-injection",
                    message="eval with variable expansion - command injection risk",
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                )
            else:
                # eval with literal is still suspicious
                self._add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-eval-usage",
                    message="eval usage - review for command injection",
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                )

    def _check_variable_as_command(self) -> None:
        """Detect variable used as command name."""
        self.cursor.execute("""
            SELECT file, line, command_name
            FROM bash_commands
            WHERE command_name LIKE '$%'
               OR command_name LIKE '${%'
        """)

        for row in self.cursor.fetchall():
            self._add_finding(
                file=row["file"],
                line=row["line"],
                rule_name="bash-variable-as-command",
                message=f"Variable used as command name: {row['command_name']}",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
            )

    def _check_xargs_injection(self) -> None:
        """Detect xargs with dangerous flags and untrusted input."""
        self.cursor.execute("""
            SELECT c.file, c.line, c.pipeline_position, a.arg_value
            FROM bash_commands c
            LEFT JOIN bash_command_args a
                ON c.file = a.file
                AND c.line = a.command_line
                AND c.pipeline_position IS a.command_pipeline_position
            WHERE c.command_name = 'xargs'
        """)

        xargs_calls: dict[tuple[str, int], list[str]] = {}
        for row in self.cursor.fetchall():
            key = (row["file"], row["line"])
            if key not in xargs_calls:
                xargs_calls[key] = []
            if row["arg_value"]:
                xargs_calls[key].append(row["arg_value"])

        for (file, line), args in xargs_calls.items():
            has_dangerous_flag = any(arg in self.patterns.XARGS_DANGEROUS_FLAGS for arg in args)
            if has_dangerous_flag:
                self._add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-xargs-injection",
                    message="xargs with -I flag can enable command injection",
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                )

    def _check_backtick_injection(self) -> None:
        """Detect backtick substitution which is harder to nest safely."""
        self.cursor.execute("""
            SELECT file, line, command_text, capture_target
            FROM bash_subshells
            WHERE syntax = 'backtick'
        """)

        for row in self.cursor.fetchall():
            command_text = row["command_text"] or ""
            # Backticks with variable expansion are risky
            if "$" in command_text:
                self._add_finding(
                    file=row["file"],
                    line=row["line"],
                    rule_name="bash-backtick-injection",
                    message="Backtick substitution with variables - prefer $() syntax",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-78",
                )

    def _check_source_injection(self) -> None:
        """Detect source/dot with variable path."""
        self.cursor.execute("""
            SELECT file, line, sourced_path, has_variable_expansion
            FROM bash_sources
            WHERE has_variable_expansion = 1
        """)

        for row in self.cursor.fetchall():
            self._add_finding(
                file=row["file"],
                line=row["line"],
                rule_name="bash-source-injection",
                message=f"source with variable path: {row['sourced_path']}",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
            )


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Bash injection vulnerabilities."""
    analyzer = BashInjectionAnalyzer(context)
    return analyzer.analyze()
