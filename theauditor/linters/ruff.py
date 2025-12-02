"""Ruff linter implementation.

Ruff is a fast Python linter written in Rust. It handles parallelization
internally, so we pass all files in a single invocation (no batching).
"""

import json

from theauditor.linters.base import BaseLinter, Finding
from theauditor.utils.logging import logger


class RuffLinter(BaseLinter):
    """Ruff linter for Python files.

    Executes ruff check with JSON output and parses findings.
    No batching - Ruff is internally parallelized and handles large file lists.
    """

    @property
    def name(self) -> str:
        return "ruff"

    async def run(self, files: list[str]) -> list[Finding]:
        """Run Ruff on Python files.

        Args:
            files: List of Python file paths relative to project root

        Returns:
            List of Finding objects from Ruff analysis
        """
        if not files:
            return []

        ruff_bin = self.toolbox.get_venv_binary("ruff", required=False)
        if not ruff_bin:
            logger.warning("Ruff not found - skipping Python linting")
            return []

        config_path = self.toolbox.get_python_linter_config()
        if not config_path.exists():
            logger.error(f"Ruff config not found: {config_path}")
            return []

        # No batching - Ruff handles parallelization internally
        cmd = [
            str(ruff_bin),
            "check",
            "--config",
            str(config_path),
            "--output-format",
            "json",
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

        try:
            results = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Invalid JSON output: {e}")
            return []

        findings = []
        for item in results:
            location = item.get("location", {}) or {}
            rule_code = (item.get("code") or "").strip()
            if not rule_code:
                rule_code = "ruff-unknown"

            findings.append(
                Finding(
                    tool=self.name,
                    file=self._normalize_path(item.get("filename", "")),
                    line=location.get("row", 0),
                    column=location.get("column", 0),
                    rule=rule_code,
                    message=item.get("message", ""),
                    severity="warning",
                    category="lint",
                )
            )

        logger.info(f"[{self.name}] Found {len(findings)} issues in {len(files)} files")
        return findings
