"""Go Concurrency Issue Analyzer - Database-First Approach.

This is a Go-specific analyzer that detects common concurrency bugs:
1. Captured loop variables in goroutines (data race)
2. Package-level variable access from goroutines without sync
3. Shared map access from multiple goroutines
"""

import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="go_concurrency",
    category="concurrency",
    target_extensions=[".go"],
    exclude_patterns=[
        "vendor/",
        "node_modules/",
        "testdata/",
        "_test.go",
    ],
    execution_scope="database",
    requires_jsx_pass=False,
)


@dataclass(frozen=True)
class GoConcurrencyPatterns:
    """Pattern definitions for Go concurrency issue detection."""

    # Synchronization primitives
    SYNC_PRIMITIVES = frozenset([
        "sync.Mutex",
        "sync.RWMutex",
        "sync.WaitGroup",
        "sync.Once",
        "sync.Cond",
        "sync.Map",
        "atomic.",
    ])

    # Channel operations (generally safe)
    CHANNEL_OPS = frozenset([
        "<-",
        "make(chan",
    ])


class GoConcurrencyAnalyzer:
    """Analyzer for Go concurrency issues.

    Key detection: Captured loop variables in goroutines.
    This is the #1 source of data races in Go code:

        for i, v := range items {
            go func() {
                process(v)  // v is captured - RACE CONDITION!
            }()
        }
    """

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context."""
        self.context = context
        self.patterns = GoConcurrencyPatterns()
        self.findings = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point."""
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        conn.row_factory = sqlite3.Row
        self.cursor = conn.cursor()

        try:
            # Run concurrency checks (tables guaranteed to exist by schema)
            self._check_captured_loop_variables()
            self._check_package_var_goroutine_access()
            self._check_goroutine_without_sync()

        finally:
            conn.close()

        return self.findings

    def _check_captured_loop_variables(self):
        """CRITICAL: Detect captured loop variables in goroutines.

        This is a HIGH CONFIDENCE finding because:
        1. go_captured_vars already filters to anonymous goroutines
        2. is_loop_var is set by walking up to enclosing for/range
        3. This pattern is almost always a bug
        """
        self.cursor.execute("""
            SELECT file_path, line, goroutine_id, var_name, is_loop_var
            FROM go_captured_vars
            WHERE is_loop_var = 1
            ORDER BY file_path, line
        """)

        for row in self.cursor.fetchall():
            self.findings.append(
                StandardFinding(
                    rule_name="go-race-captured-loop-var",
                    message=f"Loop variable '{row['var_name']}' captured in goroutine - data race!",
                    file_path=row["file_path"],
                    line=row["line"],
                    severity=Severity.CRITICAL,
                    category="concurrency",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-362",
                    additional_info={
                        "goroutine_id": row["goroutine_id"],
                        "var_name": row["var_name"],
                        "fix": f"Pass '{row['var_name']}' as parameter: go func({row['var_name']} T) {{ ... }}({row['var_name']})",
                    },
                )
            )

    def _check_package_var_goroutine_access(self):
        """Detect goroutines that might access package-level variables."""
        # Find package-level variables
        self.cursor.execute("""
            SELECT file_path, name
            FROM go_variables
            WHERE is_package_level = 1
        """)

        pkg_vars = {}
        for row in self.cursor.fetchall():
            key = row["file_path"]
            if key not in pkg_vars:
                pkg_vars[key] = set()
            pkg_vars[key].add(row["name"])

        if not pkg_vars:
            return

        # Find goroutines in files with package-level variables
        self.cursor.execute("""
            SELECT g.file_path, g.line, g.containing_func, g.is_anonymous
            FROM go_goroutines g
            WHERE g.is_anonymous = 1
        """)

        goroutines = self.cursor.fetchall()

        for goroutine in goroutines:
            file_path = goroutine["file_path"]

            if file_path not in pkg_vars:
                continue

            # Check if there's sync.Mutex in the file
            self.cursor.execute("""
                SELECT COUNT(*) as cnt FROM go_struct_fields
                WHERE file_path = ?
                  AND (field_type LIKE '%sync.Mutex%'
                       OR field_type LIKE '%sync.RWMutex%')
            """, (file_path,))

            has_mutex = self.cursor.fetchone()["cnt"] > 0

            if not has_mutex:
                # Check captured vars for this goroutine
                self.cursor.execute("""
                    SELECT var_name FROM go_captured_vars
                    WHERE file_path = ? AND line = ?
                """, (file_path, goroutine["line"]))

                captured = {row["var_name"] for row in self.cursor.fetchall()}
                pkg_var_access = captured.intersection(pkg_vars[file_path])

                if pkg_var_access:
                    for var_name in pkg_var_access:
                        self.findings.append(
                            StandardFinding(
                                rule_name="go-race-pkg-var",
                                message=f"Package variable '{var_name}' accessed in goroutine without visible sync",
                                file_path=file_path,
                                line=goroutine["line"],
                                severity=Severity.HIGH,
                                category="concurrency",
                                confidence=Confidence.MEDIUM,
                                cwe_id="CWE-362",
                            )
                        )

    def _check_goroutine_without_sync(self):
        """Detect files with multiple goroutines but no sync primitives."""
        # Count goroutines per file
        self.cursor.execute("""
            SELECT file_path, COUNT(*) as goroutine_count
            FROM go_goroutines
            GROUP BY file_path
            HAVING goroutine_count >= 2
        """)

        multi_goroutine_files = {
            row["file_path"]: row["goroutine_count"]
            for row in self.cursor.fetchall()
        }

        for file_path, count in multi_goroutine_files.items():
            # Check for sync imports
            self.cursor.execute("""
                SELECT COUNT(*) as cnt FROM go_imports
                WHERE file_path = ?
                  AND (path = 'sync' OR path = 'sync/atomic')
            """, (file_path,))

            has_sync_import = self.cursor.fetchone()["cnt"] > 0

            # Check for channel usage
            self.cursor.execute("""
                SELECT COUNT(*) as cnt FROM go_channels
                WHERE file_path = ?
            """, (file_path,))

            has_channels = self.cursor.fetchone()["cnt"] > 0

            if not has_sync_import and not has_channels:
                self.findings.append(
                    StandardFinding(
                        rule_name="go-goroutines-no-sync",
                        message=f"File has {count} goroutines but no sync primitives or channels",
                        file_path=file_path,
                        line=1,  # File-level finding
                        severity=Severity.MEDIUM,
                        category="concurrency",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-362",
                        additional_info={
                            "goroutine_count": count,
                            "suggestion": "Consider using sync.Mutex, sync.WaitGroup, or channels for coordination",
                        },
                    )
                )


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Go concurrency issues."""
    analyzer = GoConcurrencyAnalyzer(context)
    return analyzer.analyze()
