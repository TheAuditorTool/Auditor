"""shellcheck linter implementation.

shellcheck is a static analysis tool for shell scripts. It identifies common
bugs and pitfalls in Bash/sh scripts. This is a NEW linter - Bash support
was previously missing from TheAuditor.
"""

import json
import time

from theauditor.linters.base import BaseLinter, Finding, LinterResult
from theauditor.utils.logging import logger


class ShellcheckLinter(BaseLinter):
    """shellcheck linter for Bash/shell files.

    Executes shellcheck with JSON output. This is an optional linter -
    silently skipped if shellcheck is not installed.
    No batching - shellcheck handles multiple files efficiently.
    """

    @property
    def name(self) -> str:
        return "shellcheck"

    async def run(self, files: list[str]) -> LinterResult:
        """Run shellcheck on Bash/shell files.

        Args:
            files: List of shell script paths relative to project root

        Returns:
            LinterResult with status and findings
        """
        if not files:
            return LinterResult.success(self.name, [], 0.0)

        shellcheck_bin = self.toolbox.get_shellcheck(required=False)
        if not shellcheck_bin:
            return LinterResult.skipped(self.name, "shellcheck not found")

        start_time = time.perf_counter()

        cmd = [
            str(shellcheck_bin),
            "--format=json",
            "--external-sources",
            *files,
        ]

        try:
            _returncode, stdout, _stderr = await self._run_command(cmd)
        except TimeoutError:
            return LinterResult.failed(self.name, "Timed out", time.perf_counter() - start_time)

        if not stdout.strip():
            duration = time.perf_counter() - start_time
            logger.debug(f"[{self.name}] No issues found")
            return LinterResult.success(self.name, [], duration)

        if stdout.strip() == "[]":
            duration = time.perf_counter() - start_time
            logger.debug(f"[{self.name}] No issues found")
            return LinterResult.success(self.name, [], duration)

        try:
            issues = json.loads(stdout)
        except json.JSONDecodeError as e:
            return LinterResult.failed(
                self.name, f"Invalid JSON output: {e}", time.perf_counter() - start_time
            )

        findings = []
        for issue in issues:
            finding = self._parse_issue(issue)
            if finding:
                findings.append(finding)

        duration = time.perf_counter() - start_time
        logger.info(
            f"[{self.name}] Found {len(findings)} issues in {len(files)} files ({duration:.2f}s)"
        )
        return LinterResult.success(self.name, findings, duration)

    def _parse_issue(self, issue: dict) -> Finding | None:
        """Parse a shellcheck issue into a Finding.

        Args:
            issue: Issue object from shellcheck JSON output

        Returns:
            Finding object or None if parsing fails
        """
        file_path = issue.get("file", "")
        if not file_path:
            return None

        line = issue.get("line", 0)
        column = issue.get("column", 0)

        code = issue.get("code", 0)
        rule = f"SC{code}" if code else "shellcheck"

        message = issue.get("message", "")

        level = issue.get("level", "warning").lower()
        severity_map = {
            "error": "error",
            "warning": "warning",
            "info": "info",
            "style": "info",
        }
        severity = severity_map.get(level, "warning")

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
