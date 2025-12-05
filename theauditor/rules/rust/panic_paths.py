"""Rust Panic Path Analyzer - Fidelity-Compliant.

Detects panic-inducing patterns that may cause availability issues:
- panic!() macro usage outside tests
- unwrap() calls on Option/Result
- expect() calls without meaningful messages
- assert!() in production code

Uses RuleDB for fidelity tracking. Rust-specific tables use db.execute()
since they may not be in Q class schema.
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

METADATA = RuleMetadata(
    name="rust_panic_paths",
    category="availability",
    target_extensions=[".rs"],
    exclude_patterns=[
        "test/",
        "tests/",
        "benches/",
        "*_test.rs",
        "test_*.rs",
    ],
    execution_scope="database",
)


PANIC_MACROS = frozenset(["panic", "todo", "unimplemented", "unreachable"])

ASSERT_MACROS = frozenset([
    "assert", "assert_eq", "assert_ne",
    "debug_assert", "debug_assert_eq", "debug_assert_ne",
])


def _is_test_file(file_path: str) -> bool:
    """Check if file is a test file."""
    test_patterns = ["test", "_test.rs", "tests/", "/test/", "benches/"]
    return any(pattern in file_path.lower() for pattern in test_patterns)


def _check_panic_macros(db: RuleDB) -> list[StandardFinding]:
    """Flag panic!() macro invocations outside tests."""
    findings = []
    placeholders = ",".join("?" * len(PANIC_MACROS))

    rows = db.execute(
        f"""
        SELECT file_path, line, macro_name, containing_function, args_sample
        FROM rust_macro_invocations
        WHERE macro_name IN ({placeholders})
        """,
        list(PANIC_MACROS),
    )

    for row in rows:
        file_path, line, macro_name, containing_fn, args = row
        containing_fn = containing_fn or "unknown"
        args = args or ""

        if _is_test_file(file_path):
            continue

        severity = Severity.HIGH
        if macro_name == "panic":
            severity = Severity.CRITICAL
        elif macro_name in ("todo", "unimplemented"):
            severity = Severity.HIGH

        findings.append(
            StandardFinding(
                rule_name=f"rust-{macro_name}-in-production",
                message=f"{macro_name}!() in {containing_fn}() may cause runtime panic",
                file_path=file_path,
                line=line,
                severity=severity,
                category="availability",
                confidence=Confidence.HIGH,
                cwe_id="CWE-248",
                additional_info={
                    "macro": macro_name,
                    "function": containing_fn,
                    "args_preview": args[:100] if args else None,
                    "recommendation": "Use Result/Option types instead of panicking",
                },
            )
        )

    return findings


def _check_assertion_macros(db: RuleDB) -> list[StandardFinding]:
    """Flag assert macros that may panic in production."""
    findings = []
    placeholders = ",".join("?" * len(ASSERT_MACROS))

    rows = db.execute(
        f"""
        SELECT file_path, line, macro_name, containing_function, args_sample
        FROM rust_macro_invocations
        WHERE macro_name IN ({placeholders})
        """,
        list(ASSERT_MACROS),
    )

    for row in rows:
        file_path, line, macro_name, containing_fn, _ = row
        containing_fn = containing_fn or "unknown"

        if _is_test_file(file_path):
            continue

        is_debug = macro_name.startswith("debug_")
        severity = Severity.LOW if is_debug else Severity.MEDIUM

        findings.append(
            StandardFinding(
                rule_name=f"rust-{macro_name.replace('_', '-')}-production",
                message=f"{macro_name}!() in {containing_fn}() may panic on assertion failure",
                file_path=file_path,
                line=line,
                severity=severity,
                category="availability",
                confidence=Confidence.MEDIUM,
                cwe_id="CWE-248",
                additional_info={
                    "macro": macro_name,
                    "function": containing_fn,
                    "is_debug_only": is_debug,
                    "recommendation": "Consider using ensure! or returning Result instead",
                },
            )
        )

    return findings


def _check_todo_unimplemented(db: RuleDB) -> list[StandardFinding]:
    """Flag todo!() and unimplemented!() as incomplete code."""
    findings = []

    rows = db.execute("""
        SELECT file_path, line, macro_name, containing_function
        FROM rust_macro_invocations
        WHERE macro_name IN ('todo', 'unimplemented')
    """)

    for row in rows:
        file_path, line, macro_name, containing_fn = row
        containing_fn = containing_fn or "unknown"

        findings.append(
            StandardFinding(
                rule_name="rust-incomplete-implementation",
                message=f"{macro_name}!() in {containing_fn}() indicates incomplete implementation",
                file_path=file_path,
                line=line,
                severity=Severity.HIGH,
                category="quality",
                confidence=Confidence.HIGH,
                additional_info={
                    "macro": macro_name,
                    "function": containing_fn,
                    "recommendation": "Implement the missing functionality before deployment",
                },
            )
        )

    return findings


def _check_unwraps(db: RuleDB) -> list[StandardFinding]:
    """Flag .unwrap() and .expect() calls that may panic.

    These are method calls, NOT macros, so we query function_call_args table.
    Patterns in database: 'unwrap', 'expect', or qualified like 'Option::unwrap'.
    """
    findings = []

    rows = db.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE file LIKE '%.rs'
          AND (
              callee_function = 'unwrap'
              OR callee_function = 'expect'
              OR callee_function LIKE '%::unwrap'
              OR callee_function LIKE '%::expect'
              OR callee_function = 'unwrap_or_default'
          )
        ORDER BY file, line
    """)

    for row in rows:
        file_path, line, callee, args = row
        args = args or ""

        if _is_test_file(file_path):
            continue

        # Determine severity based on method
        if callee in ("unwrap", "Option::unwrap", "Result::unwrap") or callee.endswith("::unwrap"):
            severity = Severity.HIGH
            message = ".unwrap() call may panic without meaningful error message"
            rule_suffix = "unwrap"
        elif callee in ("expect",) or callee.endswith("::expect"):
            severity = Severity.MEDIUM
            message = ".expect() call may panic"
            rule_suffix = "expect"
            if args and (args == '""' or args == "''"):
                severity = Severity.HIGH
                message = ".expect() with empty message - no better than unwrap()"
        elif callee == "unwrap_or_default":
            continue  # Safe - doesn't panic
        else:
            severity = Severity.MEDIUM
            message = f".{callee}() call may panic"
            rule_suffix = "unwrap"

        findings.append(
            StandardFinding(
                rule_name=f"rust-panic-{rule_suffix}",
                message=message,
                file_path=file_path,
                line=line,
                severity=severity,
                category="availability",
                confidence=Confidence.HIGH,
                cwe_id="CWE-248",
                additional_info={
                    "method": callee,
                    "args_preview": args[:100] if args else None,
                    "recommendation": "Use match, if let, or ? operator instead",
                },
            )
        )

    return findings


def _table_exists(db: RuleDB, table_name: str) -> bool:
    """Check if a table exists in the database."""
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        [table_name],
    )
    return len(rows) > 0


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Rust panic-inducing code patterns.

    Returns RuleResult with findings and fidelity manifest.
    """
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        # Check Rust macro table
        if _table_exists(db, "rust_macro_invocations"):
            findings.extend(_check_panic_macros(db))
            findings.extend(_check_assertion_macros(db))
            findings.extend(_check_todo_unimplemented(db))

        # Check function_call_args for unwrap/expect
        if _table_exists(db, "function_call_args"):
            findings.extend(_check_unwraps(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


# Legacy alias for orchestrator discovery
def find_panic_paths(context: StandardRuleContext) -> RuleResult:
    """Detect Rust panic-inducing code patterns."""
    return analyze(context)
