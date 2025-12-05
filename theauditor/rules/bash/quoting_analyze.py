"""Bash Quoting Analyzer - Detects unquoted variable expansion vulnerabilities."""

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
    name="bash_quoting",
    category="security",
    target_extensions=[".sh", ".bash"],
    exclude_patterns=["node_modules/", "vendor/", ".git/"],
    execution_scope="database",
    primary_table="bash_command_args",
)

# Commands where unquoted variables are particularly dangerous
DANGEROUS_COMMANDS = frozenset([
    "rm", "mv", "cp", "chmod", "chown", "chgrp", "mkdir", "rmdir",
    "touch", "cat", "grep", "find", "xargs", "exec", "eval", "source",
])


def find_bash_quoting_issues(context: StandardRuleContext) -> RuleResult:
    """Detect Bash quoting vulnerabilities.

    Named find_* for orchestrator discovery.

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []
    seen: set[str] = set()

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    def add_finding(
        file: str,
        line: int,
        rule_name: str,
        message: str,
        severity: Severity,
        confidence: Confidence = Confidence.HIGH,
    ) -> None:
        """Add a finding if not already seen."""
        key = f"{file}:{line}:{rule_name}"
        if key in seen:
            return
        seen.add(key)

        findings.append(
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

    with RuleDB(context.db_path, METADATA.name) as db:
        # Check unquoted expansion
        _check_unquoted_expansion(db, add_finding)

        # Check dangerous unquoted commands
        _check_dangerous_unquoted_commands(db, add_finding)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_unquoted_expansion(db: RuleDB, add_finding) -> None:
    """Detect unquoted variable expansion in command arguments."""
    rows = db.query(
        Q("bash_command_args")
        .select("file", "command_line", "arg_value", "is_quoted", "has_expansion")
        .where("is_quoted = ? AND has_expansion = ?", 0, 1)
    )

    for file, command_line, arg_value, is_quoted, has_expansion in rows:
        arg = arg_value or ""

        # Skip arithmetic contexts
        if "$((" in arg:
            continue

        # Get the command name for this argument
        cmd_rows = db.query(
            Q("bash_commands")
            .select("command_name")
            .where("file = ? AND line = ?", file, command_line)
        )

        command_name = ""
        for (cmd,) in cmd_rows:
            command_name = cmd or ""
            break

        # Skip quoting checks for double-bracket tests - they safely handle unquoted vars
        # Unlike POSIX [ or test, [[ does not perform word splitting or glob expansion
        if command_name == "[[":
            continue

        # Higher severity for dangerous commands
        if command_name in DANGEROUS_COMMANDS:
            add_finding(
                file=file,
                line=command_line,
                rule_name="bash-unquoted-dangerous",
                message=f"Unquoted variable in {command_name}: {arg[:50]}",
                severity=Severity.HIGH,
                confidence=Confidence.HIGH,
            )
        else:
            add_finding(
                file=file,
                line=command_line,
                rule_name="bash-unquoted-expansion",
                message=f"Unquoted variable expansion: {arg[:50]}",
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
            )


def _check_dangerous_unquoted_commands(db: RuleDB, add_finding) -> None:
    """Detect file operation commands with unquoted path arguments."""
    dangerous_list = ", ".join(f"'{cmd}'" for cmd in DANGEROUS_COMMANDS)

    sql, params = Q.raw(
        f"""
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
        """,
        [],
    )

    for row in db.execute(sql, params):
        file, line, command_name, all_args = row
        args = all_args or ""

        # Check for glob patterns in rm/mv/cp
        if command_name in ("rm", "mv", "cp") and "*" in args:
            # Unquoted glob with variable is especially dangerous
            if "$" in args:
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-glob-injection",
                    message=f"{command_name} with unquoted glob and variable",
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                )
