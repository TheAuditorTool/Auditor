# ruff: noqa: N999 - UPPERCASE name is intentional for template visibility
"""RULE TEMPLATE: Standard Backend/Database Rule (No JSX Required)."""

import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="your_rule_name",
    category="security",
    target_extensions=[".py", ".js", ".ts", ".mjs", ".cjs"],
    exclude_patterns=["frontend/", "client/", "migrations/", "test/", "__tests__/"],
    requires_jsx_pass=False,
    execution_scope="database",
)


@dataclass(frozen=True)
class YourRulePatterns:
    """Pattern definitions for your security rule."""

    DANGEROUS_FUNCTIONS: frozenset = frozenset(
        [
            "eval",
            "exec",
            "execfile",
            "compile",
            "__import__",
            "Function",
            "setTimeout",
            "setInterval",
        ]
    )

    INPUT_SOURCES: frozenset = frozenset(
        ["request.", "req.", "params.", "query.", "body.", "cookies.", "argv", "stdin", "input()"]
    )

    SAFE_SANITIZERS: frozenset = frozenset(
        ["escape", "sanitize", "validate", "DOMPurify", "validator.escape"]
    )


def find_your_rule_name(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect [YOUR VULNERABILITY TYPE] using database-only approach."""
    findings = []

    if not context.db_path:
        return findings

    patterns = YourRulePatterns()
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        findings.extend(_check_dangerous_calls(cursor, patterns))
        findings.extend(_check_user_input_flow(cursor, patterns))

    finally:
        conn.close()

    return findings


def _check_dangerous_calls(cursor, patterns: YourRulePatterns) -> list[StandardFinding]:
    """Check for dangerous function calls with user input."""
    findings = []

    dangerous_funcs = ", ".join(f"'{func}'" for func in patterns.DANGEROUS_FUNCTIONS)

    cursor.execute(f"""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IN ({dangerous_funcs})
          AND argument_index = 0
        ORDER BY file, line
    """)

    seen = set()

    for file, line, func, args in cursor.fetchall():
        if not args:
            continue

        has_user_input = any(src in args for src in patterns.INPUT_SOURCES)

        if not has_user_input:
            continue

        has_sanitizer = any(san in args for san in patterns.SAFE_SANITIZERS)

        if has_sanitizer:
            continue

        key = f"{file}:{line}"
        if key in seen:
            continue
        seen.add(key)

        findings.append(
            StandardFinding(
                file_path=file,
                line=line,
                rule_name="your-rule-dangerous-call",
                message=f"Dangerous function {func}() called with user input",
                severity=Severity.HIGH,
                category="security",
                snippet=args[:80] + "..." if len(args) > 80 else args,
                cwe_id="CWE-XXX",
            )
        )

    return findings


def _check_user_input_flow(cursor, patterns: YourRulePatterns) -> list[StandardFinding]:
    """Check for direct user input flow to dangerous sinks."""
    findings = []

    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE source_expr IS NOT NULL
        ORDER BY file, line
        LIMIT 1000
    """)

    for file, line, target, source in cursor.fetchall():
        if "request." not in source and "req." not in source:
            continue

        has_input = any(src in source for src in patterns.INPUT_SOURCES)

        if has_input:
            findings.append(
                StandardFinding(
                    file_path=file,
                    line=line,
                    rule_name="your-rule-input-flow",
                    message=f"User input assigned to variable {target}",
                    severity=Severity.MEDIUM,
                    category="security",
                    snippet=f"{target} = {source[:60]}",
                )
            )

    return findings


def _is_express_app(conn) -> bool:
    """Check if this is an Express.js application."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM frameworks
        WHERE name = 'express' AND language = 'javascript'
    """)

    return cursor.fetchone()[0] > 0


def _get_framework_safe_sinks(conn, framework_name: str) -> frozenset:
    """Get safe sinks for a specific framework."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT fss.sink_pattern
        FROM framework_safe_sinks fss
        JOIN frameworks f ON f.id = fss.framework_id
        WHERE f.name = ?
          AND fss.is_safe = 1
    """,
        [framework_name],
    )

    return frozenset(row[0] for row in cursor.fetchall())
