"""Rust Memory Safety Analyzer - Database-First Approach.

Detects dangerous memory operations that may lead to undefined behavior:
- std::mem::transmute usage
- Box::leak and similar memory leaks
- ManuallyDrop misuse
- Raw pointer dereferencing patterns
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
    name="rust_memory_safety",
    category="memory_safety",
    target_extensions=[".rs"],
    exclude_patterns=[
        "test/",
        "tests/",
        "benches/",
    ],
    execution_scope="database")


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
}


class MemorySafetyAnalyzer:
    """Analyzer for Rust memory safety issues."""

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
                WHERE type='table' AND name='rust_use_statements'
            """)
            if not self.cursor.fetchone():
                return []

            self._check_dangerous_imports()
            self._check_unsafe_blocks_for_patterns()

        finally:
            conn.close()

        return self.findings

    def _check_dangerous_imports(self):
        """Flag imports of dangerous memory functions."""
        self.cursor.execute("""
            SELECT file_path, line, import_path, local_name
            FROM rust_use_statements
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line"]
            import_path = row["import_path"] or ""
            local_name = row["local_name"]

            for dangerous_path, info in DANGEROUS_IMPORTS.items():
                if dangerous_path in import_path or import_path.endswith(
                    dangerous_path.split("::")[-1]
                ):
                    severity_map = {
                        "critical": Severity.CRITICAL,
                        "high": Severity.HIGH,
                        "medium": Severity.MEDIUM,
                        "low": Severity.LOW,
                    }
                    severity = severity_map.get(info["severity"], Severity.MEDIUM)

                    self.findings.append(
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

    def _check_unsafe_blocks_for_patterns(self):
        """Check unsafe blocks for dangerous patterns."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='rust_unsafe_blocks'
        """)
        if not self.cursor.fetchone():
            return

        self.cursor.execute("""
            SELECT
                file_path, line_start, line_end,
                containing_function, operations_json
            FROM rust_unsafe_blocks
            WHERE operations_json IS NOT NULL
        """)

        for row in self.cursor.fetchall():
            file_path = row["file_path"]
            line = row["line_start"]
            containing_fn = row["containing_function"] or "unknown"
            operations = row["operations_json"] or ""

            for method, info in DANGEROUS_METHODS.items():
                if method in operations.lower():
                    severity_map = {
                        "critical": Severity.CRITICAL,
                        "high": Severity.HIGH,
                        "medium": Severity.MEDIUM,
                        "low": Severity.LOW,
                    }
                    severity = severity_map.get(info["severity"], Severity.MEDIUM)

                    self.findings.append(
                        StandardFinding(
                            rule_name=f"rust-unsafe-{method.replace('_', '-')}",
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


def find_memory_safety_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Rust memory safety issues."""
    analyzer = MemorySafetyAnalyzer(context)
    return analyzer.analyze()


analyze = find_memory_safety_issues
