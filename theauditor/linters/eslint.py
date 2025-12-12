"""ESLint linter implementation.

ESLint is a JavaScript/TypeScript linter. Unlike Ruff, it runs on Node.js
and is subject to Windows command line length limits (8191 chars), so we
use dynamic batching based on actual path lengths.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from theauditor.linters.base import LINTER_TIMEOUT, BaseLinter, Finding, LinterResult
from theauditor.utils.logging import logger

if TYPE_CHECKING:
    from theauditor.linters.config_generator import ConfigResult

ESLINT_SEVERITY_ERROR = 2
ESLINT_SEVERITY_WARNING = 1


MAX_CMD_LENGTH = 8000


MAX_CONCURRENT_BATCHES = 4


class EslintLinter(BaseLinter):
    """ESLint linter for JavaScript/TypeScript files.

    Uses dynamic batching to avoid Windows command line length limits.
    Batches run in parallel with limited concurrency (MAX_CONCURRENT_BATCHES).
    """

    def __init__(self, toolbox, root: Path, *, config_result: ConfigResult | None = None):
        """Initialize ESLint linter.

        Args:
            toolbox: Toolbox instance for tool paths
            root: Project root directory
            config_result: Optional config generation result for intelligent config selection
        """
        super().__init__(toolbox, root)
        self.config_result = config_result

    @property
    def name(self) -> str:
        return "eslint"

    async def run(self, files: list[str]) -> LinterResult:
        """Run ESLint on JavaScript/TypeScript files.

        Args:
            files: List of JS/TS file paths relative to project root

        Returns:
            LinterResult with status and findings
        """
        if not files:
            return LinterResult.success(self.name, [], 0.0)

        eslint_bin = self.toolbox.get_eslint(required=False)
        if not eslint_bin:
            return LinterResult.skipped(self.name, "ESLint not found")

        # Config selection - NO FALLBACK
        if self.config_result is None:
            # No ConfigGenerator was run - use static sandbox config (backward compat)
            config_path = self.toolbox.get_eslint_config()
            if not config_path.exists():
                return LinterResult.skipped(self.name, f"ESLint config not found: {config_path}")
        elif self.config_result.use_project_eslint:
            # Project has its own config - omit --config flag, let ESLint auto-discover
            config_path = None
            logger.info(f"[{self.name}] Using project ESLint config (auto-discovery)")
        else:
            # Use generated config
            config_path = self.config_result.eslint_config_path
            if config_path is None or not config_path.exists():
                return LinterResult.skipped(self.name, "Generated ESLint config not found")

        start_time = time.perf_counter()

        batches = self._create_batches(files, eslint_bin, config_path)
        logger.debug(f"[{self.name}] Split {len(files)} files into {len(batches)} batches")

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)

        async def run_with_limit(batch: list[str], batch_num: int) -> list[Finding]:
            async with semaphore:
                return await self._run_batch(batch, eslint_bin, config_path, batch_num)

        tasks = [run_with_limit(batch, batch_num) for batch_num, batch in enumerate(batches, 1)]
        results = await asyncio.gather(*tasks)

        all_findings = [finding for batch_findings in results for finding in batch_findings]

        duration = time.perf_counter() - start_time
        logger.info(
            f"[{self.name}] Found {len(all_findings)} issues in {len(files)} files ({duration:.2f}s)"
        )
        return LinterResult.success(self.name, all_findings, duration)

    def _create_batches(
        self, files: list[str], eslint_bin: Path, config_path: Path | None
    ) -> list[list[str]]:
        """Create batches based on command line length limits.

        Dynamically calculates batch sizes to stay under Windows 8191 char limit.

        Args:
            files: All files to lint
            eslint_bin: Path to ESLint binary
            config_path: Path to ESLint config (None for project auto-discovery)

        Returns:
            List of file batches
        """
        if config_path is not None:
            base_cmd = f"{eslint_bin} --config {config_path} --format json --output-file temp.json "
        else:
            base_cmd = f"{eslint_bin} --format json --output-file temp.json "
        base_len = len(base_cmd)

        batches = []
        current_batch = []
        current_len = base_len

        for file in files:
            file_len = len(file) + 1

            if current_len + file_len > MAX_CMD_LENGTH and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_len = base_len

            current_batch.append(file)
            current_len += file_len

        if current_batch:
            batches.append(current_batch)

        return batches

    async def _run_batch(
        self,
        files: list[str],
        eslint_bin: Path,
        config_path: Path | None,
        batch_num: int,
    ) -> list[Finding]:
        """Run ESLint on a single batch of files.

        ESLint writes to an output file rather than stdout for reliable JSON.

        Args:
            files: Files in this batch
            eslint_bin: Path to ESLint binary
            config_path: Path to ESLint config (None for project auto-discovery)
            batch_num: Batch number for logging

        Returns:
            List of Finding objects from this batch
        """
        temp_dir = self.root / ".pf" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_file = temp_dir / f"eslint_output_batch{batch_num}.json"

        cmd = [str(eslint_bin)]
        if config_path is not None:
            cmd.extend(["--config", str(config_path)])
        cmd.extend(["--format", "json", "--output-file", str(output_file), *files])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.root),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, _stderr = await asyncio.wait_for(proc.communicate(), timeout=LINTER_TIMEOUT)
        except TimeoutError:
            logger.error(f"[{self.name}] Batch {batch_num} timed out")
            return []
        except Exception as e:
            logger.error(f"[{self.name}] Batch {batch_num} failed: {e}")
            return []

        if not output_file.exists():
            logger.warning(f"[{self.name}] Batch {batch_num} produced no output file")
            return []

        try:
            with open(output_file, encoding="utf-8") as f:
                results = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] Batch {batch_num} invalid JSON: {e}")
            return []
        finally:
            try:
                output_file.unlink()
            except OSError:
                pass

        findings = []
        for file_result in results:
            file_path = file_result.get("filePath", "")

            for msg in file_result.get("messages", []):
                severity = "error" if msg.get("severity") == ESLINT_SEVERITY_ERROR else "warning"

                findings.append(
                    Finding(
                        tool=self.name,
                        file=self._normalize_path(file_path),
                        line=msg.get("line", 0),
                        column=msg.get("column", 0),
                        rule=msg.get("ruleId") or "eslint-error",
                        message=msg.get("message", ""),
                        severity=severity,
                        category="lint",
                    )
                )

        return findings
