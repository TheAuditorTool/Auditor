"""theauditor/linters/linters.py - Async linter orchestration.

Coordinates running external linters in parallel using asyncio.
Individual linter implementations are in separate modules.
"""

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from theauditor.indexer.database import DatabaseManager
from theauditor.linters.base import Finding
from theauditor.linters.clippy import ClippyLinter
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

        # Verify toolbox is set up
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
        # Get files by language
        js_files = self._get_source_files([".js", ".jsx", ".ts", ".tsx", ".mjs"])
        py_files = self._get_source_files([".py"])
        rs_files = self._get_source_files([".rs"])
        go_files = self._get_source_files([".go"])
        sh_files = self._get_source_files([".sh", ".bash"])

        # Filter to workset if provided
        if workset_files:
            workset_set = set(workset_files)
            js_files = [f for f in js_files if f in workset_set]
            py_files = [f for f in py_files if f in workset_set]
            rs_files = [f for f in rs_files if f in workset_set]
            go_files = [f for f in go_files if f in workset_set]
            sh_files = [f for f in sh_files if f in workset_set]

        # Create linter instances
        linters = []

        if js_files:
            logger.info(f"Queuing ESLint for {len(js_files)} JavaScript/TypeScript files")
            linters.append(("eslint", EslintLinter(self.toolbox, self.root), js_files))

        if py_files:
            logger.info(f"Queuing Ruff for {len(py_files)} Python files")
            linters.append(("ruff", RuffLinter(self.toolbox, self.root), py_files))

            logger.info(f"Queuing Mypy for {len(py_files)} Python files")
            linters.append(("mypy", MypyLinter(self.toolbox, self.root), py_files))

        if rs_files:
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

        # Run all linters in parallel
        logger.info(f"Running {len(linters)} linters in parallel...")

        tasks = [linter.run(files) for name, linter, files in linters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect findings, handling exceptions
        all_findings: list[Finding] = []
        for (name, linter, files), result in zip(linters, results):
            if isinstance(result, Exception):
                logger.error(f"[{name}] Failed with exception: {result}")
                continue
            all_findings.extend(result)

        # Convert Finding objects to dicts for backward compatibility
        findings_dicts = [f.to_dict() for f in all_findings]

        # Write to database and JSON
        if findings_dicts:
            logger.info(f"Writing {len(findings_dicts)} findings to database")
            self.db.write_findings_batch(findings_dicts, "lint")

        self._write_json_output(findings_dicts)

        return findings_dicts

    def _get_source_files(self, extensions: list[str]) -> list[str]:
        """Query database for source files with given extensions.

        Args:
            extensions: List of file extensions (e.g., [".py", ".pyi"])

        Returns:
            List of file paths relative to project root
        """
        try:
            cursor = self.db.conn.cursor()
            placeholders = ",".join("?" * len(extensions))

            query = (
                "SELECT path FROM files WHERE ext IN ("
                + placeholders
                + ") AND file_category = 'source' ORDER BY path"
            )
            cursor.execute(query, extensions)

            files = [row[0] for row in cursor.fetchall()]
            logger.debug(f"Found {len(files)} files with extensions {extensions}")
            return files

        except sqlite3.OperationalError as e:
            logger.error(f"Database query failed (table missing or locked?): {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected database error: {e}")
            return []

    def _write_json_output(self, findings: list[dict[str, Any]]):
        """Write findings to JSON file for AI consumption.

        Args:
            findings: List of finding dictionaries
        """
        output_file = self.root / ".pf" / "raw" / "lint.json"

        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create output directory: {e}")
            raise OSError(f"Cannot create {output_file.parent}: {e}") from e

        sorted_findings = sorted(findings, key=lambda f: (f["file"], f["line"], f["rule"]))

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(sorted_findings, f, indent=2, sort_keys=True)
            logger.info(f"Wrote {len(findings)} findings to {output_file}")
        except OSError as e:
            logger.error(f"Failed to write lint.json (disk full? permissions?): {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error writing lint.json: {e}")
            raise OSError(f"Failed to write {output_file}: {e}") from e
