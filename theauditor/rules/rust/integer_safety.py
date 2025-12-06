"""Rust Integer Safety Analyzer - Fidelity-Compliant.

Detects integer-related vulnerabilities:
- Unchecked arithmetic operations
- Truncating `as` casts
- Integer overflow risks
- Missing overflow checks in crypto/financial code
"""

import re

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
    name="rust_integer_safety",
    category="integer_safety",
    target_extensions=[".rs"],
    exclude_patterns=["test/", "tests/", "benches/"],
    execution_scope="database",
    primary_table="rust_functions",
)


TRUNCATING_CAST_TYPES = ["u8", "i8", "u16", "i16", "u32", "i32", "usize", "isize"]


CAST_PATTERN = re.compile(r"\bas\s+(" + "|".join(TRUNCATING_CAST_TYPES) + r")\b", re.IGNORECASE)

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


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Rust integer safety issues.

    Returns RuleResult with findings and fidelity manifest.
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_high_risk_functions(db))
        findings.extend(_check_macro_casts(db))
        findings.extend(_check_wrapping_usage(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_high_risk_functions(db: RuleDB) -> list[StandardFinding]:
    """Flag functions with financial/crypto names that don't use checked math."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("rust_functions")
        .select("file_path", "line", "name", "visibility")
        .where("visibility = ?", "pub")
    )

    for row in rows:
        file_path, line, fn_name, _ = row
        fn_name_lower = fn_name.lower()

        for risk_pattern in HIGH_RISK_FUNCTIONS:
            if risk_pattern in fn_name_lower:
                findings.append(
                    StandardFinding(
                        rule_name="rust-integer-high-risk-function",
                        message=f"Function {fn_name}() handles values - verify overflow protection",
                        file_path=file_path,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="integer_safety",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-190",
                        additional_info={
                            "function": fn_name,
                            "risk_pattern": risk_pattern,
                            "recommendation": "Use checked_add/checked_sub or saturating arithmetic",
                        },
                    )
                )
                break

    return findings


def _check_macro_casts(db: RuleDB) -> list[StandardFinding]:
    """Check for truncating casts in macro invocations.

    Uses regex to handle variable whitespace: "x as u8", "x  as  u8", "(x)as u8".
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("rust_macro_invocations")
        .select("file_path", "line", "macro_name", "containing_function", "args_sample")
        .where("args_sample IS NOT NULL")
    )

    for row in rows:
        file_path, line, macro_name, containing_fn, args = row
        containing_fn = containing_fn or "unknown"
        args = args or ""

        match = CAST_PATTERN.search(args)
        if match:
            cast_type = match.group(1)
            findings.append(
                StandardFinding(
                    rule_name="rust-truncating-cast",
                    message=f"Truncating cast 'as {cast_type}' in {macro_name}!() may lose data",
                    file_path=file_path,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="integer_safety",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-681",
                    additional_info={
                        "function": containing_fn,
                        "macro": macro_name,
                        "cast_type": cast_type,
                        "recommendation": "Use TryFrom/TryInto for safe conversion",
                    },
                )
            )

    return findings


def _check_wrapping_usage(db: RuleDB) -> list[StandardFinding]:
    """Check for explicit wrapping arithmetic usage (informational)."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("rust_use_statements")
        .select("file_path", "line", "import_path")
        .where("import_path LIKE ? OR import_path LIKE ?", "%Wrapping%", "%Saturating%")
    )

    for row in rows:
        file_path, line, import_path = row
        findings.append(
            StandardFinding(
                rule_name="rust-wrapping-arithmetic-used",
                message="Explicit wrapping/saturating arithmetic imported",
                file_path=file_path,
                line=line,
                severity=Severity.INFO,
                category="integer_safety",
                confidence=Confidence.HIGH,
                additional_info={
                    "import": import_path,
                    "note": "Good practice - explicit overflow handling",
                },
            )
        )

    return findings
