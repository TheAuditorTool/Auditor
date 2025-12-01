"""golangci-lint linter implementation.

golangci-lint is a meta-linter for Go that runs multiple linters in parallel.
It handles file discovery internally, so we pass all files in a single invocation.
This is a NEW linter - Go support was previously missing from TheAuditor.
"""

import json

from theauditor.linters.base import BaseLinter, Finding
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


class GolangciLinter(BaseLinter):
    """golangci-lint meta-linter for Go files.

    Executes golangci-lint with JSON output. This is an optional linter -
    silently skipped if golangci-lint is not installed.
    No batching - golangci-lint handles parallelization internally.
    """

    @property
    def name(self) -> str:
        return "golangci-lint"

    async def run(self, files: list[str]) -> list[Finding]:
        """Run golangci-lint on Go files.

        Args:
            files: List of Go file paths relative to project root

        Returns:
            List of Finding objects from golangci-lint analysis
        """
        if not files:
            return []

        # Optional tool - silently skip if not found
        golangci_bin = self.toolbox.get_golangci_lint(required=False)
        if not golangci_bin:
            logger.debug(f"[{self.name}] Not found - skipping Go linting")
            return []

        # golangci-lint runs on directories, not individual files
        # Run on project root and let it discover Go files
        cmd = [
            str(golangci_bin),
            "run",
            "--out-format",
            "json",
            "--issues-exit-code",
            "0",  # Don't fail on lint issues
            "./...",
        ]

        try:
            returncode, stdout, stderr = await self._run_command(cmd)
        except TimeoutError:
            logger.error(f"[{self.name}] Timed out")
            return []

        if not stdout.strip():
            logger.debug(f"[{self.name}] No issues found")
            return []

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Invalid JSON output: {e}")
            return []

        issues = result.get("Issues") or []
        findings = []

        for issue in issues:
            finding = self._parse_issue(issue)
            if finding:
                findings.append(finding)

        logger.info(f"[{self.name}] Found {len(findings)} issues in Go files")
        return findings

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

        # Rule comes from the "FromLinter" field
        from_linter = issue.get("FromLinter", "")
        rule = from_linter if from_linter else "golangci"

        message = issue.get("Text", "")

        # golangci-lint severity mapping
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
