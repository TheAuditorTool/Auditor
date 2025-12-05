"""Rust Unsafe Block Analyzer - Fidelity-Compliant.

Detects unsafe code patterns that may indicate security or safety issues:
- Unsafe blocks without SAFETY comments
- Unsafe code in public APIs
- Unsafe trait implementations

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
    name="rust_unsafe",
    category="memory_safety",
    target_extensions=[".rs"],
    exclude_patterns=["test/", "tests/", "benches/", "examples/"],
    execution_scope="database",
)


def _table_exists(db: RuleDB, table_name: str) -> bool:
    """Check if a table exists in the database."""
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        [table_name],
    )
    return len(rows) > 0


def _check_unsafe_without_safety_comment(db: RuleDB) -> list[StandardFinding]:
    """Flag unsafe blocks without SAFETY comments."""
    findings = []

    rows = db.execute("""
        SELECT
            file_path, line_start, line_end,
            containing_function, has_safety_comment, reason
        FROM rust_unsafe_blocks
        WHERE has_safety_comment = 0
    """)

    for row in rows:
        file_path, line, _, containing_fn, _, _ = row
        containing_fn = containing_fn or "unknown"

        findings.append(
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

    return findings


def _check_unsafe_in_public_api(db: RuleDB) -> list[StandardFinding]:
    """Flag public functions containing unsafe blocks.

    This is the key check for "Unsoundness" - CVE-level issues in libraries.
    A safe public API that contains unsafe internally must uphold all invariants.
    """
    findings = []

    if not _table_exists(db, "rust_functions"):
        return findings

    rows = db.execute("""
        SELECT DISTINCT
            ub.file_path, ub.line_start,
            rf.name as fn_name, rf.visibility, rf.line as fn_line
        FROM rust_unsafe_blocks ub
        JOIN rust_functions rf ON ub.file_path = rf.file_path
            AND ub.containing_function = rf.name
        WHERE rf.visibility = 'pub'
          AND rf.is_unsafe = 0
    """)

    for row in rows:
        file_path, _, fn_name, _, fn_line = row

        findings.append(
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

    return findings


def _check_unsafe_trait_impls(db: RuleDB) -> list[StandardFinding]:
    """Flag unsafe trait implementations for review."""
    findings = []

    if not _table_exists(db, "rust_unsafe_traits"):
        return findings

    rows = db.execute("""
        SELECT file_path, line, trait_name, impl_type
        FROM rust_unsafe_traits
    """)

    for row in rows:
        file_path, line, trait_name, impl_type = row
        impl_type = impl_type or "unknown"

        findings.append(
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

    return findings


def _check_unsafe_functions(db: RuleDB) -> list[StandardFinding]:
    """Flag unsafe functions in public API."""
    findings = []

    if not _table_exists(db, "rust_functions"):
        return findings

    rows = db.execute("""
        SELECT file_path, line, name, visibility, return_type
        FROM rust_functions
        WHERE is_unsafe = 1 AND visibility = 'pub'
    """)

    for row in rows:
        file_path, line, fn_name, _, _ = row

        findings.append(
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

    return findings


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Rust unsafe code issues.

    Returns RuleResult with findings and fidelity manifest.
    """
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        if _table_exists(db, "rust_unsafe_blocks"):
            findings.extend(_check_unsafe_without_safety_comment(db))
            findings.extend(_check_unsafe_in_public_api(db))
            findings.extend(_check_unsafe_trait_impls(db))
            findings.extend(_check_unsafe_functions(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


# Legacy alias for orchestrator discovery
def find_unsafe_issues(context: StandardRuleContext) -> RuleResult:
    """Detect Rust unsafe code issues."""
    return analyze(context)
