"""theauditor/linters/linters.py - Async linter orchestration.

Coordinates running external linters in parallel using asyncio.
Individual linter implementations are in separate modules.
"""

import asyncio
from pathlib import Path
from typing import Any

from theauditor.indexer.database import DatabaseManager
from theauditor.linters.base import Finding, LinterResult
from theauditor.linters.clippy import ClippyLinter
from theauditor.linters.config_generator import ConfigGenerator, ConfigResult
from theauditor.linters.eslint import EslintLinter
from theauditor.linters.golangci import GolangciLinter
from theauditor.linters.mypy import MypyLinter
from theauditor.linters.ruff import RuffLinter
from theauditor.linters.shellcheck import ShellcheckLinter
from theauditor.utils.logging import logger
from theauditor.utils.toolbox import Toolbox


class LinterOrchestrator:
    """Coordinates running external linters on project files.

    Runs all applicable linters in parallel using asyncio.gather().
    Each linter is isolated - failures in one don't affect others.
    """

    def __init__(self, root_path: str, db_path: str):
        """Initialize with project root and database path.

        Args:
            root_path: Project root directory
            db_path: Path to repo_index.db database
        """
        self.root = Path(root_path).resolve()

        if not self.root.exists():
            raise ValueError(f"Root path does not exist: {self.root}")
        if not self.root.is_dir():
            raise ValueError(f"Root path is not a directory: {self.root}")

        db_path_obj = Path(db_path)
        if not db_path_obj.exists():
            raise ValueError(f"Database not found: {db_path}")

        self.db = DatabaseManager(db_path)
        self.toolbox = Toolbox(self.root)

        if not self.toolbox.sandbox.exists():
            raise RuntimeError(
                f"Toolbox not found at {self.toolbox.sandbox}. "
                f"Run 'aud setup-ai --target {self.root}' first."
            )

        logger.info(f"LinterOrchestrator initialized: root={self.root}")

    def run_all_linters(self, workset_files: list[str] | None = None) -> list[dict[str, Any]]:
        """Run all available linters on appropriate files.

        Synchronous wrapper around async implementation for backward compatibility.

        Args:
            workset_files: Optional list of files to limit linting to

        Returns:
            List of finding dictionaries (backward compatible format)
        """
        return asyncio.run(self._run_async(workset_files))

    async def _run_async(self, workset_files: list[str] | None = None) -> list[dict[str, Any]]:
        """Run all linters in parallel using asyncio.

        Args:
            workset_files: Optional list of files to limit linting to

        Returns:
            List of finding dictionaries
        """

        all_files = self._get_all_source_files()

        js_extensions = {".js", ".jsx", ".ts", ".tsx", ".mjs"}
        js_files = [p for p, ext in all_files if ext in js_extensions]
        py_files = [p for p, ext in all_files if ext == ".py"]
        rs_files = [p for p, ext in all_files if ext == ".rs"]
        go_files = [p for p, ext in all_files if ext == ".go"]
        sh_files = [p for p, ext in all_files if ext in {".sh", ".bash"}]

        if workset_files:
            workset_set = set(workset_files)
            js_files = [f for f in js_files if f in workset_set]
            py_files = [f for f in py_files if f in workset_set]
            rs_files = list(filter(workset_set.__contains__, rs_files))
            go_files = [f for f in go_files if f in workset_set]
            sh_files = [f for f in sh_files if f in workset_set]

        # Generate intelligent ESLint/TypeScript configs before linting
        config_result: ConfigResult | None = None
        if js_files:
            with ConfigGenerator(self.root, Path(self.db.db_path)) as generator:
                config_result = generator.prepare_configs()

        linters = []

        if js_files:
            logger.info(f"Queuing ESLint for {len(js_files)} JavaScript/TypeScript files")
            linters.append(("eslint", EslintLinter(self.toolbox, self.root, config_result=config_result), js_files))

        if py_files:
            logger.info(f"Queuing Ruff for {len(py_files)} Python files")
            linters.append(("ruff", RuffLinter(self.toolbox, self.root), py_files))

            logger.info(f"Queuing Mypy for {len(py_files)} Python files")
            linters.append(("mypy", MypyLinter(self.toolbox, self.root), py_files))

        if len(rs_files) > 0:
            logger.info(f"Queuing Clippy for {len(rs_files)} Rust files")
            linters.append(("clippy", ClippyLinter(self.toolbox, self.root), rs_files))

        if go_files:
            logger.info(f"Queuing golangci-lint for {len(go_files)} Go files")
            linters.append(("golangci-lint", GolangciLinter(self.toolbox, self.root), go_files))

        if sh_files:
            logger.info(f"Queuing shellcheck for {len(sh_files)} Bash files")
            linters.append(("shellcheck", ShellcheckLinter(self.toolbox, self.root), sh_files))

        if not linters:
            logger.info("No files to lint")
            return []

        logger.info(f"Running {len(linters)} linters in parallel...")

        tasks = [linter.run(files) for name, linter, files in linters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_findings: list[Finding] = []
        for (name, _linter, _files), result in zip(linters, results, strict=True):
            if isinstance(result, Exception):
                logger.error(f"[{name}] Failed with exception: {result}")
                continue

            linter_result: LinterResult = result

            if linter_result.status == "SKIPPED":
                logger.warning(f"[{name}] SKIPPED: {linter_result.error_message}")
            elif linter_result.status == "FAILED":
                logger.error(f"[{name}] FAILED: {linter_result.error_message}")
            else:
                all_findings.extend(linter_result.findings)

        findings_dicts = [f.to_dict() for f in all_findings]

        if findings_dicts:
            logger.info(f"Writing {len(findings_dicts)} findings to database")
            self.db.write_findings_batch(findings_dicts, "lint")

        return findings_dicts

    def _get_all_source_files(self) -> list[tuple[str, str]]:
        """Query database for ALL source files in one query.

        Returns:
            List of (path, extension) tuples for all source files.

        Raises:
            sqlite3.OperationalError: If database is locked or table missing.
                This is intentional - infrastructure failures must crash loud.
        """

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT path, ext FROM files WHERE file_category = 'source' ORDER BY path")
        files = cursor.fetchall()
        logger.debug(f"Fetched {len(files)} source files from database")
        return files
