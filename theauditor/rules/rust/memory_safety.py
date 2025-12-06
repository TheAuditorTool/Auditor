"""Rust Memory Safety Analyzer - Fidelity-Compliant.

Detects dangerous memory operations that may lead to undefined behavior:
- std::mem::transmute usage
- Box::leak and similar memory leaks
- ManuallyDrop misuse
- Raw pointer dereferencing patterns
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
    name="rust_memory_safety",
    category="memory_safety",
    target_extensions=[".rs"],
    exclude_patterns=["test/", "tests/", "benches/"],
    execution_scope="database",
    primary_table="rust_unsafe_blocks",
)

DANGEROUS_IMPORTS = {
    "std::mem::transmute": {
        "severity": "critical",
        "message": "transmute can easily cause undefined behavior",
        "cwe": "CWE-843",
    },
    "std::mem::transmute_copy": {
        "severity": "critical",
        "message": "transmute_copy can cause undefined behavior",
        "cwe": "CWE-843",
    },
    "std::mem::forget": {
        "severity": "medium",
        "message": "mem::forget may leak resources",
        "cwe": "CWE-401",
    },
    "std::mem::ManuallyDrop": {
        "severity": "medium",
        "message": "ManuallyDrop requires manual drop() call - memory leak risk",
        "cwe": "CWE-401",
    },
    "std::mem::zeroed": {
        "severity": "high",
        "message": "mem::zeroed can create invalid values for many types",
        "cwe": "CWE-908",
    },
    "std::mem::uninitialized": {
        "severity": "critical",
        "message": "mem::uninitialized is deprecated and causes UB",
        "cwe": "CWE-908",
    },
    "std::mem::MaybeUninit": {
        "severity": "medium",
        "message": "MaybeUninit requires careful handling",
        "cwe": "CWE-908",
    },
    "std::ptr::read": {
        "severity": "high",
        "message": "ptr::read requires valid pointer and may cause UB",
        "cwe": "CWE-119",
    },
    "std::ptr::write": {
        "severity": "high",
        "message": "ptr::write requires valid pointer and may cause UB",
        "cwe": "CWE-119",
    },
    "std::ptr::read_volatile": {
        "severity": "high",
        "message": "volatile read requires valid aligned pointer",
        "cwe": "CWE-119",
    },
    "std::ptr::write_volatile": {
        "severity": "high",
        "message": "volatile write requires valid aligned pointer",
        "cwe": "CWE-119",
    },
    "std::ptr::copy": {
        "severity": "high",
        "message": "ptr::copy can cause UB with overlapping regions",
        "cwe": "CWE-119",
    },
    "std::ptr::copy_nonoverlapping": {
        "severity": "high",
        "message": "ptr::copy_nonoverlapping requires non-overlapping regions",
        "cwe": "CWE-119",
    },
}

DANGEROUS_METHODS = {
    "leak": {
        "severity": "medium",
        "message": "Box::leak intentionally leaks memory",
        "cwe": "CWE-401",
    },
    "into_raw": {
        "severity": "medium",
        "message": "into_raw requires manual memory management",
        "cwe": "CWE-401",
    },
    "from_raw": {
        "severity": "high",
        "message": "from_raw requires pointer from matching into_raw",
        "cwe": "CWE-416",
    },
    "as_ptr": {
        "severity": "low",
        "message": "as_ptr creates raw pointer - ensure lifetime validity",
        "cwe": "CWE-119",
    },
    "as_mut_ptr": {
        "severity": "medium",
        "message": "as_mut_ptr creates mutable raw pointer",
        "cwe": "CWE-119",
    },
    "ManuallyDrop::new": {
        "severity": "medium",
        "message": "ManuallyDrop::new disables automatic drop - ensure manual cleanup",
        "cwe": "CWE-401",
    },
    "ManuallyDrop::into_inner": {
        "severity": "high",
        "message": "ManuallyDrop::into_inner - safety critical, may cause double-free",
        "cwe": "CWE-415",
    },
    "ManuallyDrop::drop": {
        "severity": "high",
        "message": "ManuallyDrop::drop - ensure value not used after drop",
        "cwe": "CWE-416",
    },
    "ManuallyDrop::take": {
        "severity": "high",
        "message": "ManuallyDrop::take - unsafe, leaves ManuallyDrop in invalid state",
        "cwe": "CWE-416",
    },
}

SEVERITY_MAP = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
}


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Rust memory safety issues.

    Returns RuleResult with findings and fidelity manifest.
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_dangerous_imports(db))
        findings.extend(_check_unsafe_blocks_for_patterns(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_dangerous_imports(db: RuleDB) -> list[StandardFinding]:
    """Flag imports of dangerous memory functions."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("rust_use_statements").select("file_path", "line", "import_path", "local_name")
    )

    for row in rows:
        file_path, line, import_path, local_name = row
        import_path = import_path or ""

        for dangerous_path, info in DANGEROUS_IMPORTS.items():
            if dangerous_path in import_path or import_path.endswith(
                dangerous_path.split("::")[-1]
            ):
                severity = SEVERITY_MAP.get(info["severity"], Severity.MEDIUM)

                findings.append(
                    StandardFinding(
                        rule_name="rust-dangerous-import",
                        message=f"Import of {import_path}: {info['message']}",
                        file_path=file_path,
                        line=line,
                        severity=severity,
                        category="memory_safety",
                        confidence=Confidence.HIGH,
                        cwe_id=info["cwe"],
                        additional_info={
                            "import": import_path,
                            "local_name": local_name,
                            "recommendation": "Ensure proper safety documentation and review",
                        },
                    )
                )

    return findings


def _check_unsafe_blocks_for_patterns(db: RuleDB) -> list[StandardFinding]:
    """Check unsafe blocks for dangerous patterns."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("rust_unsafe_blocks")
        .select("file_path", "line_start", "line_end", "containing_function", "operations_json")
        .where("operations_json IS NOT NULL")
    )

    for row in rows:
        file_path, line, _, containing_fn, operations = row
        containing_fn = containing_fn or "unknown"
        operations = operations or ""

        for method, info in DANGEROUS_METHODS.items():
            if method in operations.lower():
                severity = SEVERITY_MAP.get(info["severity"], Severity.MEDIUM)

                findings.append(
                    StandardFinding(
                        rule_name=f"rust-unsafe-{method.replace('_', '-').replace('::', '-')}",
                        message=f"{method}() in unsafe block: {info['message']}",
                        file_path=file_path,
                        line=line,
                        severity=severity,
                        category="memory_safety",
                        confidence=Confidence.MEDIUM,
                        cwe_id=info["cwe"],
                        additional_info={
                            "function": containing_fn,
                            "operation": method,
                            "recommendation": "Review memory management carefully",
                        },
                    )
                )

    return findings
