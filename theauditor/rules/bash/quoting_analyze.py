"""Bash Quoting Analyzer - Detects unquoted variable expansion vulnerabilities."""

import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="bash_quoting",
    category="security",
    target_extensions=[".sh", ".bash"],
    exclude_patterns=["node_modules/", "vendor/", ".git/"],
    execution_scope="database",
    requires_jsx_pass=False,
)

# Commands where unquoted variables are particularly dangerous
DANGEROUS_COMMANDS = frozenset([
    "rm", "mv", "cp", "chmod", "chown", "chgrp",
    "mkdir", "rmdir", "touch", "cat", "grep",
    "find", "xargs", "exec", "eval", "source",
])

# Safe contexts where unquoted is acceptable
SAFE_CONTEXTS = frozenset([
    "$((",  # Arithmetic expansion
    "$((",
    "[[",   # Modern test (handles some cases)
])


class BashQuotingAnalyzer:
    """Analyzer for Bash quoting vulnerabilities."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context."""
        self.context = context
        self.findings: list[StandardFinding] = []
        self.seen: set[str] = set()

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        conn.row_factory = sqlite3.Row
        self.cursor = conn.cursor()

        self._check_unquoted_expansion()
        self._check_dangerous_unquoted_commands()

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
                category="security",
                confidence=confidence,
                cwe_id="CWE-78",
            )
        )

    def _check_unquoted_expansion(self) -> None:
        """Detect unquoted variable expansion in command arguments."""
        self.cursor.execute("""
            SELECT
                a.file,
                a.command_line,
                a.arg_value,
                a.is_quoted,
                a.quote_type,
                a.has_expansion,
                a.expansion_vars,
                c.command_name
            FROM bash_command_args a
            JOIN bash_commands c
                ON a.file = c.file
                AND a.command_line = c.line
                AND a.command_pipeline_position IS c.pipeline_position
            WHERE a.is_quoted = 0
              AND a.has_expansion = 1
        """)

        for row in self.cursor.fetchall():
            file = row["file"]
            line = row["command_line"]
            arg_value = row["arg_value"] or ""
            command_name = row["command_name"] or ""
            expansion_vars = row["expansion_vars"] or ""

            # Skip arithmetic contexts
            if "$((" in arg_value:
                continue

            # Higher severity for dangerous commands
            if command_name in DANGEROUS_COMMANDS:
                self._add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-unquoted-dangerous",
                    message=f"Unquoted variable in {command_name}: {arg_value[:50]}",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                )
            else:
                self._add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-unquoted-expansion",
                    message=f"Unquoted variable expansion: {arg_value[:50]}",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                )

    def _check_dangerous_unquoted_commands(self) -> None:
        """Detect file operation commands with unquoted path arguments."""
        dangerous_list = ", ".join(f"'{cmd}'" for cmd in DANGEROUS_COMMANDS)

        self.cursor.execute(f"""
            SELECT
                c.file,
                c.line,
                c.command_name,
                GROUP_CONCAT(a.arg_value, ' ') as all_args
            FROM bash_commands c
            LEFT JOIN bash_command_args a
                ON c.file = a.file
                AND c.line = a.command_line
                AND c.pipeline_position IS a.command_pipeline_position
            WHERE c.command_name IN ({dangerous_list})
            GROUP BY c.file, c.line, c.command_name
        """)

        for row in self.cursor.fetchall():
            file = row["file"]
            line = row["line"]
            command_name = row["command_name"]
            all_args = row["all_args"] or ""

            # Check for glob patterns in rm/mv/cp
            if command_name in ("rm", "mv", "cp") and "*" in all_args:
                # Unquoted glob with variable is especially dangerous
                if "$" in all_args:
                    self._add_finding(
                        file=file,
                        line=line,
                        rule_name="bash-glob-injection",
                        message=f"{command_name} with unquoted glob and variable",
                        severity=Severity.HIGH,
                        confidence=Confidence.HIGH,
                    )


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Bash quoting vulnerabilities."""
    analyzer = BashQuotingAnalyzer(context)
    return analyzer.analyze()
