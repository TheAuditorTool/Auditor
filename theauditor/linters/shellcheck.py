"""shellcheck linter implementation.

shellcheck is a static analysis tool for shell scripts. It identifies common
bugs and pitfalls in Bash/sh scripts. This is a NEW linter - Bash support
was previously missing from TheAuditor.
"""

import json

from theauditor.linters.base import BaseLinter, Finding
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


class ShellcheckLinter(BaseLinter):
    """shellcheck linter for Bash/shell files.

    Executes shellcheck with JSON output. This is an optional linter -
    silently skipped if shellcheck is not installed.
    No batching - shellcheck handles multiple files efficiently.
    """

    @property
    def name(self) -> str:
        return "shellcheck"

    async def run(self, files: list[str]) -> list[Finding]:
        """Run shellcheck on Bash/shell files.

        Args:
            files: List of shell script paths relative to project root

        Returns:
            List of Finding objects from shellcheck analysis
        """
        if not files:
            return []

        # Optional tool - silently skip if not found
        shellcheck_bin = self.toolbox.get_shellcheck(required=False)
        if not shellcheck_bin:
            logger.debug(f"[{self.name}] Not found - skipping Bash linting")
            return []

        # shellcheck accepts multiple files
        cmd = [
            str(shellcheck_bin),
            "--format=json",
            "--external-sources",  # Allow sourcing external files
            *files,
        ]

        try:
            returncode, stdout, stderr = await self._run_command(cmd)
        except TimeoutError:
            logger.error(f"[{self.name}] Timed out")
            return []

        if not stdout.strip():
            logger.debug(f"[{self.name}] No issues found")
            return []

        # shellcheck may return empty array "[]" for no issues
        if stdout.strip() == "[]":
            logger.debug(f"[{self.name}] No issues found")
            return []

        try:
            issues = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Invalid JSON output: {e}")
            return []

        findings = []
        for issue in issues:
            finding = self._parse_issue(issue)
            if finding:
                findings.append(finding)

        logger.info(f"[{self.name}] Found {len(findings)} issues in {len(files)} files")
        return findings

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

        # Rule is SC#### code
        code = issue.get("code", 0)
        rule = f"SC{code}" if code else "shellcheck"

        message = issue.get("message", "")

        # Map shellcheck levels: error, warning, info, style
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
