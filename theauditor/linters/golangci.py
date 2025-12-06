"""golangci-lint linter implementation.

golangci-lint is a meta-linter for Go that runs multiple linters in parallel.
It handles file discovery internally, so we pass all files in a single invocation.
This is a NEW linter - Go support was previously missing from TheAuditor.
"""

import json
import time

from theauditor.linters.base import BaseLinter, Finding, LinterResult
from theauditor.utils.logging import logger


class GolangciLinter(BaseLinter):
    """golangci-lint meta-linter for Go files.

    Executes golangci-lint with JSON output. This is an optional linter -
    silently skipped if golangci-lint is not installed.
    No batching - golangci-lint handles parallelization internally.
    """

    @property
    def name(self) -> str:
        return "golangci-lint"

    async def run(self, files: list[str]) -> LinterResult:
        """Run golangci-lint on Go files.

        Args:
            files: List of Go file paths relative to project root

        Returns:
            LinterResult with status and findings
        """
        if not files:
            return LinterResult.success(self.name, [], 0.0)

        golangci_bin = self.toolbox.get_golangci_lint(required=False)
        if not golangci_bin:
            return LinterResult.skipped(self.name, "golangci-lint not found")

        start_time = time.perf_counter()

        cmd = [
            str(golangci_bin),
            "run",
            "--out-format",
            "json",
            "--issues-exit-code",
            "0",
            "./...",
        ]

        try:
            _returncode, stdout, _stderr = await self._run_command(cmd)
        except TimeoutError:
            return LinterResult.failed(self.name, "Timed out", time.perf_counter() - start_time)

        if not stdout.strip():
            duration = time.perf_counter() - start_time
            logger.debug(f"[{self.name}] No issues found")
            return LinterResult.success(self.name, [], duration)

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as e:
            return LinterResult.failed(
                self.name, f"Invalid JSON output: {e}", time.perf_counter() - start_time
            )

        issues = result.get("Issues") or []
        findings = []

        for issue in issues:
            finding = self._parse_issue(issue)
            if finding:
                findings.append(finding)

        duration = time.perf_counter() - start_time
        logger.info(f"[{self.name}] Found {len(findings)} issues in Go files ({duration:.2f}s)")
        return LinterResult.success(self.name, findings, duration)

    def _parse_issue(self, issue: dict) -> Finding | None:
        """Parse a golangci-lint issue into a Finding.

        Args:
            issue: Issue object from golangci-lint JSON output

        Returns:
            Finding object or None if parsing fails
        """
        pos = issue.get("Pos", {})

        file_path = pos.get("Filename", "")
        if not file_path:
            return None

        line = pos.get("Line", 0)
        column = pos.get("Column", 0)

        from_linter = issue.get("FromLinter", "")
        rule = from_linter if from_linter else "golangci"

        message = issue.get("Text", "")

        severity_str = issue.get("Severity", "warning").lower()
        if severity_str == "error":
            severity = "error"
        elif severity_str in ("warning", ""):
            severity = "warning"
        else:
            severity = "info"

        return Finding(
            tool=self.name,
            file=self._normalize_path(file_path),
            line=line,
            column=column,
            rule=rule,
            message=message,
            severity=severity,
            category="lint",
        )
