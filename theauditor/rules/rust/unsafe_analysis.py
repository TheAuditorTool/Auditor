"""Rust Unsafe Block Analyzer - Database-First Approach.

Detects unsafe code patterns that may indicate security or safety issues:
- Unsafe blocks without SAFETY comments
- Unsafe code in public APIs
- Unsafe trait implementations
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
    name="rust_unsafe",
    category="memory_safety",
    target_extensions=[".rs"],
    exclude_patterns=[
        "test/",
        "tests/",
        "benches/",
        "examples/",
    ],
    execution_scope="database",
    requires_jsx_pass=False,
)


class UnsafeAnalyzer:
    """Analyzer for Rust unsafe code patterns."""

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
                WHERE type='table' AND name='rust_unsafe_blocks'
            """)
            if not self.cursor.fetchone():
                return []

            self._check_unsafe_without_safety_comment()
            self._check_unsafe_in_public_api()
            self._check_unsafe_trait_impls()
            self._check_unsafe_functions()

        finally:
            conn.close()

        return self.findings

    def _check_unsafe_without_safety_comment(self):
        """Flag unsafe blocks without SAFETY comments."""
        self.cursor.execute("""
            SELECT
                file_path, line_start, line_end,
                containing_function, has_safety_comment, reason
            FROM rust_unsafe_blocks
            WHERE has_safety_comment = 0
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line_start"]
            containing_fn = row["containing_function"] or "unknown"

            self.findings.append(
                StandardFinding(
                    rule_name="rust-unsafe-no-safety-comment",
                    message=f"Unsafe block in {containing_fn}() lacks // SAFETY: comment",
                    file_path=file_path,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="memory_safety",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-676",
                    additional_info={
                        "containing_function": containing_fn,
                        "recommendation": "Add a // SAFETY: comment explaining why this unsafe block is sound",
                    },
                )
            )

    def _check_unsafe_in_public_api(self):
        """Flag public functions containing unsafe blocks."""
        self.cursor.execute("""
            SELECT DISTINCT
                ub.file_path, ub.line_start,
                rf.name as fn_name, rf.visibility, rf.line as fn_line
            FROM rust_unsafe_blocks ub
            JOIN rust_functions rf ON ub.file_path = rf.file_path
                AND ub.containing_function = rf.name
            WHERE rf.visibility = 'pub'
              AND rf.is_unsafe = 0
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            fn_name = row["fn_name"]
            fn_line = row["fn_line"]

            self.findings.append(
                StandardFinding(
                    rule_name="rust-unsafe-in-public-api",
                    message=f"Public function {fn_name}() contains unsafe block but is not marked unsafe",
                    file_path=file_path,
                    line=fn_line,
                    severity=Severity.HIGH,
                    category="memory_safety",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-676",
                    additional_info={
                        "function": fn_name,
                        "recommendation": "Consider marking the function unsafe or ensuring all invariants are upheld internally",
                    },
                )
            )

    def _check_unsafe_trait_impls(self):
        """Flag unsafe trait implementations for review."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rust_unsafe_traits'
        """)
        if not self.cursor.fetchone():
            return

        self.cursor.execute("""
            SELECT file_path, line, trait_name, impl_type
            FROM rust_unsafe_traits
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line"]
            trait_name = row["trait_name"]
            impl_type = row["impl_type"] or "unknown"

            self.findings.append(
                StandardFinding(
                    rule_name="rust-unsafe-trait-impl",
                    message=f"Unsafe impl {trait_name} for {impl_type} requires manual verification",
                    file_path=file_path,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="memory_safety",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-676",
                    additional_info={
                        "trait": trait_name,
                        "impl_type": impl_type,
                        "recommendation": "Verify that this type truly upholds the unsafe trait's invariants",
                    },
                )
            )

    def _check_unsafe_functions(self):
        """Flag unsafe functions in public API."""
        self.cursor.execute("""
            SELECT file_path, line, name, visibility, return_type
            FROM rust_functions
            WHERE is_unsafe = 1 AND visibility = 'pub'
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line"]
            fn_name = row["name"]

            self.findings.append(
                StandardFinding(
                    rule_name="rust-unsafe-public-fn",
                    message=f"Public unsafe function {fn_name}() exposes unsafe API",
                    file_path=file_path,
                    line=line,
                    severity=Severity.LOW,
                    category="memory_safety",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-676",
                    additional_info={
                        "function": fn_name,
                        "recommendation": "Document safety requirements in function docs",
                    },
                )
            )


def find_unsafe_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Rust unsafe code issues."""
    analyzer = UnsafeAnalyzer(context)
    return analyzer.analyze()


# Alias for backwards compatibility
analyze = find_unsafe_issues
