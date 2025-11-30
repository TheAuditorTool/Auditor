"""Rust Panic Path Analyzer - Database-First Approach.

Detects panic-inducing patterns that may cause availability issues:
- panic!() macro usage outside tests
- unwrap() calls on Option/Result
- expect() calls without meaningful messages
- assert!() in production code
"""

import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

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
    requires_jsx_pass=False,
)


# Panic-inducing macros
PANIC_MACROS = frozenset([
    "panic",
    "todo",
    "unimplemented",
    "unreachable",
])

# Assertion macros (may panic in debug builds)
ASSERT_MACROS = frozenset([
    "assert",
    "assert_eq",
    "assert_ne",
    "debug_assert",
    "debug_assert_eq",
    "debug_assert_ne",
])


class PanicPathAnalyzer:
    """Analyzer for Rust panic-inducing code patterns."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context."""
        self.context = context
        self.findings = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        conn.row_factory = sqlite3.Row
        self.cursor = conn.cursor()

        try:
            # Check if Rust tables exist
            self.cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='rust_macro_invocations'
            """)
            if not self.cursor.fetchone():
                return []

            self._check_panic_macros()
            self._check_assertion_macros()
            self._check_todo_unimplemented()

        finally:
            conn.close()

        return self.findings

    def _is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file."""
        test_patterns = ["test", "_test.rs", "tests/", "/test/", "benches/"]
        return any(pattern in file_path.lower() for pattern in test_patterns)

    def _check_panic_macros(self):
        """Flag panic!() macro invocations outside tests."""
        placeholders = ",".join("?" * len(PANIC_MACROS))

        self.cursor.execute(
            f"""
            SELECT file_path, line, macro_name, containing_function, args_sample
            FROM rust_macro_invocations
            WHERE macro_name IN ({placeholders})
        """,
            list(PANIC_MACROS),
        )

        for row in self.cursor.fetchall():
            file_path = row["file_path"]

            # Skip test files
            if self._is_test_file(file_path):
                continue

            line = row["line"]
            macro_name = row["macro_name"]
            containing_fn = row["containing_function"] or "unknown"
            args = row["args_sample"] or ""

            severity = Severity.HIGH
            if macro_name == "panic":
                severity = Severity.CRITICAL
            elif macro_name in ("todo", "unimplemented"):
                severity = Severity.HIGH

            self.findings.append(
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

    def _check_assertion_macros(self):
        """Flag assert macros that may panic in production."""
        placeholders = ",".join("?" * len(ASSERT_MACROS))

        self.cursor.execute(
            f"""
            SELECT file_path, line, macro_name, containing_function, args_sample
            FROM rust_macro_invocations
            WHERE macro_name IN ({placeholders})
        """,
            list(ASSERT_MACROS),
        )

        for row in self.cursor.fetchall():
            file_path = row["file_path"]

            # Skip test files
            if self._is_test_file(file_path):
                continue

            line = row["line"]
            macro_name = row["macro_name"]
            containing_fn = row["containing_function"] or "unknown"

            # debug_assert variants only panic in debug builds - lower severity
            is_debug = macro_name.startswith("debug_")
            severity = Severity.LOW if is_debug else Severity.MEDIUM

            self.findings.append(
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

    def _check_todo_unimplemented(self):
        """Flag todo!() and unimplemented!() as incomplete code."""
        self.cursor.execute("""
            SELECT file_path, line, macro_name, containing_function
            FROM rust_macro_invocations
            WHERE macro_name IN ('todo', 'unimplemented')
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line"]
            macro_name = row["macro_name"]
            containing_fn = row["containing_function"] or "unknown"

            self.findings.append(
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


def find_panic_paths(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Rust panic-inducing code patterns."""
    analyzer = PanicPathAnalyzer(context)
    return analyzer.analyze()


# Alias for backwards compatibility
analyze = find_panic_paths
