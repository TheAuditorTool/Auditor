"""Rust FFI Boundary Analyzer - Fidelity-Compliant.

Detects FFI-related security issues:
- Extern functions with raw pointer parameters
- Variadic C functions (format string risks)
- FFI boundaries without proper validation
- Rust functions exposed to C without panic handling (catch_unwind)
"""

import json

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
    name="rust_ffi_boundary",
    category="memory_safety",
    target_extensions=[".rs"],
    exclude_patterns=["test/", "tests/", "benches/"],
    execution_scope="database",
    primary_table="rust_extern_functions",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect Rust FFI boundary security issues.

    Returns RuleResult with findings and fidelity manifest.
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings.extend(_check_variadic_functions(db))
        findings.extend(_check_raw_pointer_params(db))
        findings.extend(_check_extern_blocks(db))
        findings.extend(_check_panic_across_ffi(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _check_variadic_functions(db: RuleDB) -> list[StandardFinding]:
    """Flag variadic C functions (format string vulnerability risk)."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("rust_extern_functions")
        .select("file_path", "line", "name", "abi", "params_json")
        .where("is_variadic = ?", 1)
    )

    format_functions = {"printf", "sprintf", "fprintf", "snprintf", "vprintf", "vsprintf"}

    for row in rows:
        file_path, line, fn_name, abi, _ = row
        abi = abi or "C"

        is_format_fn = any(fmt in fn_name.lower() for fmt in format_functions)
        severity = Severity.CRITICAL if is_format_fn else Severity.HIGH

        findings.append(
            StandardFinding(
                rule_name="rust-ffi-variadic",
                message=f"Variadic FFI function {fn_name}() - potential format string vulnerability",
                file_path=file_path,
                line=line,
                severity=severity,
                category="memory_safety",
                confidence=Confidence.HIGH,
                cwe_id="CWE-134",
                additional_info={
                    "function": fn_name,
                    "abi": abi,
                    "is_format_function": is_format_fn,
                    "recommendation": "Ensure format strings are not user-controlled",
                },
            )
        )

    return findings


def _check_raw_pointer_params(db: RuleDB) -> list[StandardFinding]:
    """Flag FFI functions with raw pointer parameters."""
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("rust_extern_functions")
        .select("file_path", "line", "name", "abi", "params_json", "return_type")
        .where("params_json IS NOT NULL")
    )

    for row in rows:
        file_path, line, fn_name, _, params_json, return_type = row
        return_type = return_type or ""

        has_raw_ptr = False
        ptr_params: list[str] = []

        if params_json:
            try:
                params_data = json.loads(params_json)
                for param in params_data:
                    param_type = param.get("type", "") if isinstance(param, dict) else str(param)
                    if "*const" in param_type or "*mut" in param_type:
                        has_raw_ptr = True
                        param_name = param.get("name", "?") if isinstance(param, dict) else "?"
                        ptr_params.append(f"{param_name}: {param_type}")
            except (json.JSONDecodeError, TypeError):
                if "*const" in params_json or "*mut" in params_json:
                    has_raw_ptr = True

        has_ptr_return = "*const" in return_type or "*mut" in return_type

        if has_raw_ptr:
            findings.append(
                StandardFinding(
                    rule_name="rust-ffi-raw-pointer-param",
                    message=f"FFI function {fn_name}() has raw pointer parameters",
                    file_path=file_path,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="memory_safety",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-119",
                    additional_info={
                        "function": fn_name,
                        "pointer_params": ptr_params,
                        "recommendation": "Ensure pointer validity before dereferencing",
                    },
                )
            )

        if has_ptr_return:
            findings.append(
                StandardFinding(
                    rule_name="rust-ffi-raw-pointer-return",
                    message=f"FFI function {fn_name}() returns raw pointer",
                    file_path=file_path,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="memory_safety",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-119",
                    additional_info={
                        "function": fn_name,
                        "return_type": return_type,
                        "recommendation": "Check for null and validate lifetime before use",
                    },
                )
            )

    return findings


def _check_extern_blocks(db: RuleDB) -> list[StandardFinding]:
    """Flag extern blocks for security review."""
    findings: list[StandardFinding] = []

    rows = db.query(Q("rust_extern_blocks").select("file_path", "line", "end_line", "abi"))

    for row in rows:
        file_path, line, end_line, abi = row
        abi = abi or "C"

        fn_query = (
            Q("rust_extern_functions")
            .select("COUNT(*) as fn_count")
            .where("file_path = ?", file_path)
            .where("line > ?", line)
        )
        if end_line is not None:
            fn_query = fn_query.where("line < ?", end_line)
        fn_count_rows = db.query(fn_query)
        fn_count = fn_count_rows[0][0] if fn_count_rows else 0

        if fn_count > 0:
            findings.append(
                StandardFinding(
                    rule_name="rust-ffi-extern-block",
                    message=f'extern "{abi}" block with {fn_count} FFI declarations',
                    file_path=file_path,
                    line=line,
                    severity=Severity.INFO,
                    category="memory_safety",
                    confidence=Confidence.HIGH,
                    additional_info={
                        "abi": abi,
                        "function_count": fn_count,
                        "recommendation": "Review FFI boundary for memory safety",
                    },
                )
            )

    return findings


def _check_panic_across_ffi(db: RuleDB) -> list[StandardFinding]:
    """Flag Rust functions exposed to C that may panic across FFI boundary.

    When a Rust panic unwinds across an FFI boundary into C, the behavior
    is undefined (typically aborts). Exposed functions should use catch_unwind.

    Checks for: #[no_mangle] pub extern "C" fn without catch_unwind
    """
    findings: list[StandardFinding] = []

    rows = db.query(
        Q("rust_functions")
        .select("file_path", "line", "name", "visibility", "is_unsafe", "return_type")
        .where("visibility = ?", "pub")
        .where("abi IN (?, ?, ?)", "C", "system", "cdecl")
    )

    for row in rows:
        file_path, line, fn_name, _, _, _ = row

        catch_unwind_rows = db.query(
            Q("function_call_args")
            .select("COUNT(*) as count")
            .where("file = ?", file_path)
            .where("line >= ?", line)
            .where("line <= ?", line + 100)
            .where(
                "callee_function = ? OR callee_function LIKE ? OR callee_function = ?",
                "catch_unwind",
                "%::catch_unwind",
                "panic::catch_unwind",
            )
        )
        has_catch_unwind = catch_unwind_rows[0][0] > 0 if catch_unwind_rows else False

        if not has_catch_unwind:
            findings.append(
                StandardFinding(
                    rule_name="rust-ffi-panic-across-boundary",
                    message=f'extern "C" fn {fn_name}() may panic across FFI boundary',
                    file_path=file_path,
                    line=line,
                    severity=Severity.HIGH,
                    category="memory_safety",
                    confidence=Confidence.MEDIUM,
                    cwe_id="CWE-248",
                    additional_info={
                        "function": fn_name,
                        "recommendation": (
                            "Wrap function body with std::panic::catch_unwind() "
                            "to prevent undefined behavior when panic crosses FFI"
                        ),
                    },
                )
            )

    return findings
