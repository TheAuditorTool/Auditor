"""Rust FFI Boundary Analyzer - Database-First Approach.

Detects FFI-related security issues:
- Extern functions with raw pointer parameters
- Variadic C functions (format string risks)
- FFI boundaries without proper validation
"""

import json
import sqlite3

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="rust_ffi_boundary",
    category="memory_safety",
    target_extensions=[".rs"],
    exclude_patterns=[
        "test/",
        "tests/",
        "benches/",
    ],
    execution_scope="database",
    requires_jsx_pass=False,
)


class FFIBoundaryAnalyzer:
    """Analyzer for Rust FFI boundary security issues."""

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
            # Check if Rust FFI tables exist
            self.cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='rust_extern_functions'
            """)
            if not self.cursor.fetchone():
                return []

            self._check_variadic_functions()
            self._check_raw_pointer_params()
            self._check_extern_blocks()

        finally:
            conn.close()

        return self.findings

    def _check_variadic_functions(self):
        """Flag variadic C functions (format string vulnerability risk)."""
        self.cursor.execute("""
            SELECT file_path, line, name, abi, params_json
            FROM rust_extern_functions
            WHERE is_variadic = 1
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line"]
            fn_name = row["name"]
            abi = row["abi"] or "C"

            # Check for known format string functions
            format_functions = {"printf", "sprintf", "fprintf", "snprintf", "vprintf", "vsprintf"}
            is_format_fn = any(fmt in fn_name.lower() for fmt in format_functions)

            severity = Severity.CRITICAL if is_format_fn else Severity.HIGH

            self.findings.append(
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

    def _check_raw_pointer_params(self):
        """Flag FFI functions with raw pointer parameters."""
        self.cursor.execute("""
            SELECT file_path, line, name, abi, params_json, return_type
            FROM rust_extern_functions
            WHERE params_json IS NOT NULL
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line"]
            fn_name = row["name"]
            params_json = row["params_json"]
            return_type = row["return_type"] or ""

            # Check for raw pointers in params
            has_raw_ptr = False
            ptr_params = []

            if params_json:
                try:
                    params = json.loads(params_json)
                    for param in params:
                        param_type = param.get("type", "") if isinstance(param, dict) else str(param)
                        if "*const" in param_type or "*mut" in param_type:
                            has_raw_ptr = True
                            param_name = param.get("name", "?") if isinstance(param, dict) else "?"
                            ptr_params.append(f"{param_name}: {param_type}")
                except (json.JSONDecodeError, TypeError):
                    # Check raw string for pointer patterns
                    if "*const" in params_json or "*mut" in params_json:
                        has_raw_ptr = True

            # Also check return type for raw pointers
            has_ptr_return = "*const" in return_type or "*mut" in return_type

            if has_raw_ptr:
                self.findings.append(
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
                self.findings.append(
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

    def _check_extern_blocks(self):
        """Flag extern blocks for security review."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rust_extern_blocks'
        """)
        if not self.cursor.fetchone():
            return

        self.cursor.execute("""
            SELECT file_path, line, end_line, abi
            FROM rust_extern_blocks
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line"]
            abi = row["abi"] or "C"

            # Count functions in this block
            self.cursor.execute(
                """
                SELECT COUNT(*) as fn_count
                FROM rust_extern_functions
                WHERE file_path = ?
                  AND line > ?
                  AND (? IS NULL OR line < ?)
            """,
                (file_path, line, row["end_line"], row["end_line"]),
            )
            fn_count_row = self.cursor.fetchone()
            fn_count = fn_count_row["fn_count"] if fn_count_row else 0

            # Only report if there are functions
            if fn_count > 0:
                self.findings.append(
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


def find_ffi_boundary_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Rust FFI boundary security issues."""
    analyzer = FFIBoundaryAnalyzer(context)
    return analyzer.analyze()


# Alias for backwards compatibility
analyze = find_ffi_boundary_issues
