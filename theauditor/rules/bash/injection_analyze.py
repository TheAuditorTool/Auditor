"""Bash Command Injection Analyzer - Detects shell injection vulnerabilities."""

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
    name="bash_injection",
    category="injection",
    target_extensions=[".sh", ".bash"],
    exclude_patterns=["node_modules/", "vendor/", ".git/"],
    execution_scope="database",
    primary_table="bash_commands",
)


@dataclass(frozen=True)
class BashInjectionPatterns:
    """Pattern definitions for Bash injection detection."""

    EVAL_COMMANDS: frozenset = frozenset(["eval", "bash", "sh", "zsh", "ksh"])

    COMMAND_EXECUTION: frozenset = frozenset(["xargs", "find", "parallel", "watch", "exec"])

    XARGS_DANGEROUS_FLAGS: frozenset = frozenset(["-I", "-i", "-0"])


def find_bash_injection_issues(context: StandardRuleContext) -> RuleResult:
    """Detect Bash injection vulnerabilities.

    Named find_* for orchestrator discovery - enables register_taint_patterns loading.

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
        cwe_id: str = "CWE-78",
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
                category="injection",
                confidence=confidence,
                cwe_id=cwe_id,
            )
        )

    patterns = BashInjectionPatterns()

    with RuleDB(context.db_path, METADATA.name) as db:
        rows = db.query(
            Q("bash_commands")
            .select("file", "line", "command_name")
            .where("command_name = ?", "eval")
        )

        for file, line, _command_name in rows:
            arg_rows = db.query(
                Q("bash_command_args")
                .select("arg_value", "has_expansion")
                .where("file = ? AND command_line = ?", file, line)
            )

            has_expansion = False
            for arg_value, arg_has_expansion in arg_rows:
                if arg_has_expansion or (arg_value and "$" in arg_value):
                    has_expansion = True
                    break

            if has_expansion:
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-eval-injection",
                    message="eval with variable expansion - command injection risk",
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                )
            else:
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-eval-usage",
                    message="eval usage - review for command injection",
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                )

        rows = db.query(
            Q("bash_commands")
            .select("file", "line", "command_name")
            .where("command_name LIKE ? OR command_name LIKE ?", "$%", "${%")
        )

        for file, line, command_name in rows:
            add_finding(
                file=file,
                line=line,
                rule_name="bash-variable-as-command",
                message=f"Variable used as command name: {command_name}",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
            )

        rows = db.query(
            Q("bash_commands").select("file", "line").where("command_name = ?", "xargs")
        )

        for file, line in rows:
            arg_rows = db.query(
                Q("bash_command_args")
                .select("arg_value")
                .where("file = ? AND command_line = ?", file, line)
            )

            has_dangerous_flag = any(
                arg_value in patterns.XARGS_DANGEROUS_FLAGS
                for (arg_value,) in arg_rows
                if arg_value
            )

            if has_dangerous_flag:
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-xargs-injection",
                    message="xargs with -I flag can enable command injection",
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                )

        rows = db.query(
            Q("bash_subshells")
            .select("file", "line", "command_text")
            .where("syntax = ?", "backtick")
        )

        for file, line, command_text in rows:
            if command_text and "$" in command_text:
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-backtick-injection",
                    message="Backtick substitution with variables - prefer $() syntax",
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-78",
                )

        rows = db.query(
            Q("bash_sources")
            .select("file", "line", "sourced_path")
            .where("has_variable_expansion = ?", 1)
        )

        for file, line, sourced_path in rows:
            add_finding(
                file=file,
                line=line,
                rule_name="bash-source-injection",
                message=f"source with variable path: {sourced_path}",
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
            )

        rows = db.query(
            Q("bash_command_args")
            .select("file", "command_line", "arg_value")
            .where("arg_value LIKE ?", "%${!%")
        )

        for file, line, arg_value in rows:
            add_finding(
                file=file,
                line=line,
                rule_name="bash-indirect-expansion",
                message=f"Indirect variable expansion: {arg_value[:50]}",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
            )

        rows = db.query(
            Q("bash_variables")
            .select("file", "line", "value_expr")
            .where("value_expr LIKE ?", "%${!%")
        )

        for file, line, value_expr in rows:
            add_finding(
                file=file,
                line=line,
                rule_name="bash-indirect-expansion",
                message=f"Indirect variable expansion in assignment: {value_expr[:50]}",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
            )

        rows = db.query(
            Q("bash_subshells")
            .select("file", "line", "syntax", "command_text")
            .where("syntax LIKE ? AND command_text LIKE ?", "%process%", "%$%")
        )

        for file, line, _syntax, command_text in rows:
            add_finding(
                file=file,
                line=line,
                rule_name="bash-process-substitution-injection",
                message=f"Process substitution with variable: {command_text[:50]}",
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
            )

        rows = db.query(
            Q("bash_command_args")
            .select("file", "command_line", "arg_value")
            .where("arg_value LIKE ?", "%$((%")
        )

        for file, line, arg_value in rows:
            if arg_value and "$" in arg_value:
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-arithmetic-injection",
                    message=f"Arithmetic expansion with variable - potential code injection: {arg_value[:60]}",
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                )

        rows = db.query(
            Q("bash_variables")
            .select("file", "line", "value_expr")
            .where("value_expr LIKE ?", "%$((%")
        )

        for file, line, value_expr in rows:
            if value_expr and "$" in value_expr:
                add_finding(
                    file=file,
                    line=line,
                    rule_name="bash-arithmetic-injection",
                    message=f"Arithmetic expansion in assignment with variable: {value_expr[:60]}",
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                )

        rows = db.query(
            Q("bash_commands").select("file", "line").where("command_name = ?", "printf")
        )

        for file, line in rows:
            arg_rows = db.query(
                Q("bash_command_args")
                .select("arg_value", "has_expansion", "is_quoted")
                .where("file = ? AND command_line = ? AND arg_index = 0", file, line)
            )

            for arg_value, has_expansion, _is_quoted in arg_rows:
                if has_expansion or (arg_value and "$" in str(arg_value)):
                    add_finding(
                        file=file,
                        line=line,
                        rule_name="bash-printf-format-injection",
                        message=f"printf with variable format string: {arg_value[:40]}",
                        severity=Severity.MEDIUM,
                        confidence=Confidence.MEDIUM,
                    )
                    break

        return RuleResult(findings=findings, manifest=db.get_manifest())


BASH_SOURCES: frozenset[str] = frozenset(
    [
        "$1",
        "$2",
        "$3",
        "$4",
        "$5",
        "$6",
        "$7",
        "$8",
        "$9",
        "$@",
        "$*",
        "read",
        "$QUERY_STRING",
        "$REQUEST_URI",
        "$HTTP_USER_AGENT",
        "$HTTP_COOKIE",
        "$HTTP_REFERER",
        "$INPUT",
        "$DATA",
        "$PAYLOAD",
        "$USER_INPUT",
    ]
)


BASH_COMMAND_SINKS: frozenset[str] = frozenset(
    [
        "eval",
        "exec",
        "sh",
        "bash",
        "zsh",
        "ksh",
        "source",
        ".",
        "rm",
        "rmdir",
        "unlink",
        "mv",
        "cp",
        "curl",
        "wget",
        "xargs",
        "mysql",
        "psql",
        "sqlite3",
    ]
)


BASH_SANITIZERS: frozenset[str] = frozenset(
    [
        "printf",
    ]
)


def register_taint_patterns(taint_registry) -> None:
    """Register Bash injection-specific taint patterns.

    Called by orchestrator.collect_rule_patterns() during taint analysis setup.
    Pattern follows: rules/go/injection_analyze.py:306-323
    """
    for pattern in BASH_SOURCES:
        taint_registry.register_source(pattern, "user_input", "bash")

    for pattern in BASH_COMMAND_SINKS:
        taint_registry.register_sink(pattern, "command", "bash")

    for pattern in BASH_SANITIZERS:
        taint_registry.register_sanitizer(pattern, "bash")
