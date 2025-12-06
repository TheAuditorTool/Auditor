"""Rust Unsafe Block Analyzer.

Detects unsafe code patterns that may indicate security or safety issues:
- Unsafe blocks without // SAFETY: comments documenting invariants
- Unsafe code hidden inside safe public APIs (unsoundness risk)
- Unsafe trait implementations requiring manual verification
- Public unsafe functions that expose unsafe API

CWE-676: Use of Potentially Dangerous Function - unsafe Rust requires
manual verification that safety invariants are upheld.
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
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="rust_unsafe",
    category="memory_safety",
    target_extensions=[".rs"],
    exclude_patterns=["test/", "tests/", "benches/", "examples/"],
    execution_scope="database",
    primary_table="function_call_args",
)


def _check_unsafe_without_safety_comment(db: RuleDB) -> list[StandardFinding]:
    """Flag unsafe blocks without SAFETY comments."""
    findings = []

    rows = db.query(
        Q("rust_unsafe_blocks")
        .select(
            "file_path",
            "line_start",
            "line_end",
            "containing_function",
            "has_safety_comment",
            "reason",
        )
        .where("has_safety_comment = ?", 0)
    )

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

    rows = db.query(
        Q("rust_unsafe_blocks")
        .alias("ub")
        .select("DISTINCT ub.file_path", "ub.line_start")
        .join("rust_functions", on=[("file_path", "file_path"), ("containing_function", "name")])
        .select("rust_functions.name", "rust_functions.visibility", "rust_functions.line")
        .where("rust_functions.visibility = ?", "pub")
        .where("rust_functions.is_unsafe = ?", 0)
    )

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

    rows = db.query(Q("rust_unsafe_traits").select("file_path", "line", "trait_name", "impl_type"))

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

    rows = db.query(
        Q("rust_functions")
        .select("file_path", "line", "name", "visibility", "return_type")
        .where("is_unsafe = ?", 1)
        .where("visibility = ?", "pub")
    )

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

    Checks for:
    1. Unsafe blocks without // SAFETY: comments
    2. Unsafe code hidden inside safe public APIs (unsoundness)
    3. Unsafe trait implementations requiring verification
    4. Public unsafe functions exposing unsafe API

    Returns RuleResult with findings and fidelity manifest.
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        findings.extend(_check_unsafe_without_safety_comment(db))
        findings.extend(_check_unsafe_in_public_api(db))
        findings.extend(_check_unsafe_trait_impls(db))
        findings.extend(_check_unsafe_functions(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())
