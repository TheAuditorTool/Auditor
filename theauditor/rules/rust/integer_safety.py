"""Rust Integer Safety Analyzer - Database-First Approach.

Detects integer-related vulnerabilities:
- Unchecked arithmetic operations
- Truncating `as` casts
- Integer overflow risks
- Missing overflow checks in crypto/financial code
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
    name="rust_integer_safety",
    category="integer_safety",
    target_extensions=[".rs"],
    exclude_patterns=[
        "test/",
        "tests/",
        "benches/",
    ],
    execution_scope="database")


DANGEROUS_CAST_PATTERNS = [
    " as u8",
    " as i8",
    " as u16",
    " as i16",
    " as u32",
    " as i32",
    " as usize",
    " as isize",
]


HIGH_RISK_FUNCTIONS = [
    "transfer",
    "withdraw",
    "deposit",
    "balance",
    "amount",
    "price",
    "fee",
    "reward",
    "stake",
    "mint",
    "burn",
]


WRAPPING_IMPORTS = [
    "std::num::Wrapping",
    "num::Wrapping",
    "std::num::Saturating",
]


class IntegerSafetyAnalyzer:
    """Analyzer for Rust integer safety issues."""

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
            self.cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='rust_functions'
            """)
            if not self.cursor.fetchone():
                return []

            self._check_high_risk_functions()
            self._check_macro_casts()
            self._check_wrapping_usage()

        finally:
            conn.close()

        return self.findings

    def _check_high_risk_functions(self):
        """Flag functions with financial/crypto names that don't use checked math."""
        self.cursor.execute("""
            SELECT file_path, line, name, visibility
            FROM rust_functions
            WHERE visibility = 'pub'
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line"]
            fn_name = row["name"].lower()

            for risk_pattern in HIGH_RISK_FUNCTIONS:
                if risk_pattern in fn_name:
                    self.findings.append(
                        StandardFinding(
                            rule_name="rust-integer-high-risk-function",
                            message=f"Function {row['name']}() handles values - verify overflow protection",
                            file_path=file_path,
                            line=line,
                            severity=Severity.MEDIUM,
                            category="integer_safety",
                            confidence=Confidence.LOW,
                            cwe_id="CWE-190",
                            additional_info={
                                "function": row["name"],
                                "risk_pattern": risk_pattern,
                                "recommendation": "Use checked_add/checked_sub or saturating arithmetic",
                            },
                        )
                    )
                    break

    def _check_macro_casts(self):
        """Check for truncating casts in macro invocations."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rust_macro_invocations'
        """)
        if not self.cursor.fetchone():
            return

        self.cursor.execute("""
            SELECT file_path, line, macro_name, containing_function, args_sample
            FROM rust_macro_invocations
            WHERE args_sample IS NOT NULL
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line"]
            args = row["args_sample"] or ""
            containing_fn = row["containing_function"] or "unknown"

            for cast_pattern in DANGEROUS_CAST_PATTERNS:
                if cast_pattern in args:
                    self.findings.append(
                        StandardFinding(
                            rule_name="rust-truncating-cast",
                            message=f"Truncating cast '{cast_pattern.strip()}' in {row['macro_name']}!() may lose data",
                            file_path=file_path,
                            line=line,
                            severity=Severity.MEDIUM,
                            category="integer_safety",
                            confidence=Confidence.MEDIUM,
                            cwe_id="CWE-681",
                            additional_info={
                                "function": containing_fn,
                                "macro": row["macro_name"],
                                "cast_pattern": cast_pattern.strip(),
                                "recommendation": "Use TryFrom/TryInto for safe conversion",
                            },
                        )
                    )
                    break

    def _check_wrapping_usage(self):
        """Check for explicit wrapping arithmetic usage (informational)."""
        self.cursor.execute("""
            SELECT file_path, line, import_path
            FROM rust_use_statements
            WHERE import_path LIKE '%Wrapping%'
               OR import_path LIKE '%Saturating%'
        """)

        for row in self.cursor.fetchall():
            self.findings.append(
                StandardFinding(
                    rule_name="rust-wrapping-arithmetic-used",
                    message="Explicit wrapping/saturating arithmetic imported",
                    file_path=row["file_path"],
                    line=row["line"],
                    severity=Severity.INFO,
                    category="integer_safety",
                    confidence=Confidence.HIGH,
                    additional_info={
                        "import": row["import_path"],
                        "note": "Good practice - explicit overflow handling",
                    },
                )
            )


def find_integer_safety_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Rust integer safety issues."""
    analyzer = IntegerSafetyAnalyzer(context)
    return analyzer.analyze()


analyze = find_integer_safety_issues
