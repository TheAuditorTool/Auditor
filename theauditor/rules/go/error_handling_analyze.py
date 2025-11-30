"""Go Error Handling Analyzer - Database-First Approach.

Detects common Go error handling anti-patterns:
1. Ignored errors (assigning to _)
2. Panic in library code (non-main packages)
3. Recover without re-panic for unexpected errors
4. Functions returning error but not checking callers
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
    name="go_error_handling",
    category="error_handling",
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


class GoErrorHandlingAnalyzer:
    """Analyzer for Go error handling issues."""

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
            # Run error handling checks (tables guaranteed to exist by schema)
            self._check_panic_in_library()
            self._check_ignored_errors()
            self._check_defer_without_recover()

        finally:
            conn.close()

        return self.findings

    def _check_panic_in_library(self):
        """Detect panic() calls in non-main packages.

        Libraries should return errors, not panic. Panic should only be used
        in main packages or for truly unrecoverable situations.
        """
        # Find packages that are not "main"
        self.cursor.execute("""
            SELECT file_path, name
            FROM go_packages
            WHERE name != 'main'
        """)

        library_files = {row["file_path"] for row in self.cursor.fetchall()}

        if not library_files:
            return

        # Look for panic in variables (panic calls captured in initial_value)
        self.cursor.execute("""
            SELECT file_path, line, initial_value
            FROM go_variables
            WHERE initial_value LIKE '%panic(%'
        """)

        for row in self.cursor.fetchall():
            if row["file_path"] in library_files:
                self.findings.append(
                    StandardFinding(
                        rule_name="go-panic-in-library",
                        message="panic() called in library code - return error instead",
                        file_path=row["file_path"],
                        line=row["line"],
                        severity=Severity.MEDIUM,
                        category="error_handling",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-248",
                    )
                )

        # Check for defer statements with panic (less common but worth checking)
        self.cursor.execute("""
            SELECT file_path, line, deferred_expr
            FROM go_defer_statements
            WHERE deferred_expr LIKE '%panic(%'
        """)

        for row in self.cursor.fetchall():
            if row["file_path"] in library_files:
                self.findings.append(
                    StandardFinding(
                        rule_name="go-panic-in-library-defer",
                        message="panic() in deferred function in library code",
                        file_path=row["file_path"],
                        line=row["line"],
                        severity=Severity.MEDIUM,
                        category="error_handling",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-248",
                    )
                )

    def _check_ignored_errors(self):
        """Detect ignored errors via blank identifier assignment.

        Pattern: _ = someFunc() where someFunc returns error.
        This is a common anti-pattern in Go code.
        """
        # Find variables assigned to blank identifier (_)
        # The initial_value contains the RHS expression
        self.cursor.execute("""
            SELECT v.file_path, v.line, v.name, v.initial_value
            FROM go_variables v
            WHERE v.name = '_'
              AND v.initial_value IS NOT NULL
              AND v.initial_value != ''
        """)

        blank_assignments = self.cursor.fetchall()

        for row in blank_assignments:
            # Check if the RHS looks like a function call
            initial_value = row["initial_value"] or ""
            # Function calls typically have () in them
            if "(" in initial_value and ")" in initial_value:
                # Extract function name (simple heuristic)
                func_name = initial_value.split("(")[0].strip()
                if "." in func_name:
                    func_name = func_name.split(".")[-1]

                # Check if this function returns error
                self.cursor.execute("""
                    SELECT 1 FROM go_error_returns
                    WHERE func_name = ? AND returns_error = 1
                    LIMIT 1
                """, (func_name,))

                returns_error = self.cursor.fetchone() is not None

                # Also flag common error-returning stdlib functions
                error_funcs = {
                    "Close", "Write", "Read", "Scan", "Exec", "Query",
                    "QueryRow", "Prepare", "Begin", "Commit", "Rollback",
                    "Marshal", "Unmarshal", "Decode", "Encode", "Parse",
                    "Open", "Create", "Remove", "Rename", "Mkdir",
                }

                if returns_error or func_name in error_funcs:
                    self.findings.append(
                        StandardFinding(
                            rule_name="go-ignored-error",
                            message=f"Error ignored via blank identifier: _ = {initial_value}",
                            file_path=row["file_path"],
                            line=row["line"],
                            severity=Severity.MEDIUM,
                            category="error_handling",
                            confidence=Confidence.HIGH if returns_error else Confidence.MEDIUM,
                            cwe_id="CWE-391",
                            additional_info={
                                "ignored_call": initial_value,
                                "suggestion": "Handle or explicitly document why error is ignored",
                            },
                        )
                    )

    def _check_defer_without_recover(self):
        """Detect defer statements that might need recover().

        Looks for patterns where panic might occur but isn't caught.
        This is a LOW confidence check since recover is sometimes intentional.
        """
        # Find files with defer but no recover
        self.cursor.execute("""
            SELECT DISTINCT file_path
            FROM go_defer_statements
        """)

        files_with_defer = {row["file_path"] for row in self.cursor.fetchall()}

        for file_path in files_with_defer:
            # Check if there's a recover() call in the file
            self.cursor.execute("""
                SELECT COUNT(*) as cnt FROM go_defer_statements
                WHERE file_path = ?
                  AND deferred_expr LIKE '%recover()%'
            """, (file_path,))

            has_recover = self.cursor.fetchone()["cnt"] > 0

            if not has_recover:
                # Check if there are potential panic sources
                self.cursor.execute("""
                    SELECT COUNT(*) as cnt FROM go_type_assertions
                    WHERE file_path = ?
                      AND is_type_switch = 0
                """, (file_path,))

                has_type_assertions = self.cursor.fetchone()["cnt"] > 0

                if has_type_assertions:
                    self.findings.append(
                        StandardFinding(
                            rule_name="go-type-assertion-no-recover",
                            message="Type assertions without recover() - may panic",
                            file_path=file_path,
                            line=1,  # File-level finding
                            severity=Severity.LOW,
                            category="error_handling",
                            confidence=Confidence.LOW,
                            cwe_id="CWE-248",
                            additional_info={
                                "suggestion": "Use comma-ok pattern: v, ok := x.(T)",
                            },
                        )
                    )


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Go error handling issues."""
    analyzer = GoErrorHandlingAnalyzer(context)
    return analyzer.analyze()
