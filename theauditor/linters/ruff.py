"""Ruff linter implementation.

Ruff is a fast Python linter written in Rust. It handles parallelization
internally, so we pass all files in a single invocation (no batching).
"""

import json
import time

from theauditor.linters.base import BaseLinter, Finding, LinterResult
from theauditor.utils.logging import logger


class RuffLinter(BaseLinter):
    """Ruff linter for Python files.

    Executes ruff check with JSON output and parses findings.
    No batching - Ruff is internally parallelized and handles large file lists.
    """

    @property
    def name(self) -> str:
        return "ruff"

    async def run(self, files: list[str]) -> LinterResult:
        """Run Ruff on Python files.

        Args:
            files: List of Python file paths relative to project root

        Returns:
            LinterResult with status and findings
        """
        if not files:
            return LinterResult.success(self.name, [], 0.0)

        ruff_bin = self.toolbox.get_venv_binary("ruff", required=False)
        if not ruff_bin:
            return LinterResult.skipped(self.name, "Ruff not found")

        config_path = self.toolbox.get_python_linter_config()
        if not config_path.exists():
            return LinterResult.skipped(self.name, f"Ruff config not found: {config_path}")

        start_time = time.perf_counter()

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
            _returncode, stdout, _stderr = await self._run_command(cmd)
        except TimeoutError:
            return LinterResult.failed(self.name, "Timed out", time.perf_counter() - start_time)

        if not stdout.strip():
            duration = time.perf_counter() - start_time
            logger.debug(f"[{self.name}] No issues found")
            return LinterResult.success(self.name, [], duration)

        try:
            results = json.loads(stdout)
        except json.JSONDecodeError as e:
            return LinterResult.failed(
                self.name, f"Invalid JSON output: {e}", time.perf_counter() - start_time
            )

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

        duration = time.perf_counter() - start_time
        logger.info(
            f"[{self.name}] Found {len(findings)} issues in {len(files)} files ({duration:.2f}s)"
        )
        return LinterResult.success(self.name, findings, duration)
