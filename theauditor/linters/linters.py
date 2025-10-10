"""
theauditor/linters.py - Run external linters and store findings.

PHILOSOPHY:
- Database-first: Query files table, don't walk filesystem
- Config-driven: Use .auditor_venv/.theauditor_tools/ configs
- Tool-native: Use --format json, no regex parsing
- Single responsibility: One clear job per function
- Dual-write: Database + JSON (Truth Courier architecture)

FLOW:
1. Query database for files by extension
2. Run tool with --format json --output-file <path>
3. Parse JSON output (trivial json.load())
4. Write to findings_consolidated table
5. Write to .pf/raw/lint.json for AI consumption

ARCHITECT APPROVED: 2025-10-10
AUDIT FIXES APPLIED: 2025-10-10
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
import json
import subprocess
import platform
import sqlite3
from theauditor.indexer.database import DatabaseManager
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)

# Platform detection
IS_WINDOWS = platform.system() == "Windows"

# Constants (extracted from magic numbers per audit)
LINTER_TIMEOUT = 300  # 5 minutes per batch
BATCH_SIZE = 100  # Safe for Windows 8191 char limit and Linux arg limits


class LinterOrchestrator:
    """Coordinates running external linters on project files."""

    def __init__(self, root_path: str, db_path: str):
        """Initialize with project root and database path.

        Args:
            root_path: Project root directory
            db_path: Path to repo_index.db

        Raises:
            ValueError: If paths are invalid
            RuntimeError: If toolbox doesn't exist
        """
        self.root = Path(root_path).resolve()

        # Validate root is a directory
        if not self.root.exists():
            raise ValueError(f"Root path does not exist: {self.root}")
        if not self.root.is_dir():
            raise ValueError(f"Root path is not a directory: {self.root}")

        # Validate database exists
        db_path_obj = Path(db_path)
        if not db_path_obj.exists():
            raise ValueError(f"Database not found: {db_path}")

        self.db = DatabaseManager(db_path)
        self.toolbox = self.root / ".auditor_venv" / ".theauditor_tools"

        # Fail fast if toolbox doesn't exist
        if not self.toolbox.exists():
            raise RuntimeError(
                f"Toolbox not found at {self.toolbox}. "
                f"Run 'aud setup-ai --target {self.root}' first."
            )

        logger.info(f"LinterOrchestrator initialized: root={self.root}, toolbox={self.toolbox}")

    def run_all_linters(self, workset_files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Run all available linters on appropriate files.

        Args:
            workset_files: Optional list of file paths to lint (None = all files)

        Returns:
            List of finding dictionaries
        """
        findings = []

        # Query database for files by type
        js_files = self._get_source_files(['.js', '.jsx', '.ts', '.tsx', '.mjs'])
        py_files = self._get_source_files(['.py'])

        # Filter to workset if provided
        if workset_files:
            workset_set = set(workset_files)
            js_files = [f for f in js_files if f in workset_set]
            py_files = [f for f in py_files if f in workset_set]

        # Run JavaScript linters
        if js_files:
            logger.info(f"Running ESLint on {len(js_files)} JavaScript files")
            findings.extend(self._run_eslint(js_files))

        # Run Python linters
        if py_files:
            logger.info(f"Running Ruff on {len(py_files)} Python files")
            findings.extend(self._run_ruff(py_files))

            logger.info(f"Running Mypy on {len(py_files)} Python files")
            findings.extend(self._run_mypy(py_files))

        # Write to database (dual-write pattern)
        if findings:
            logger.info(f"Writing {len(findings)} findings to database")
            self.db.write_findings_batch(findings, "lint")

        # Write to JSON for AI consumption
        self._write_json_output(findings)

        return findings

    def _get_source_files(self, extensions: List[str]) -> List[str]:
        """Query database for source files with given extensions.

        Args:
            extensions: List of file extensions (e.g., ['.js', '.py'])

        Returns:
            List of file paths from database (empty list on error)
        """
        try:
            cursor = self.db.conn.cursor()
            placeholders = ','.join('?' * len(extensions))

            cursor.execute(f"""
                SELECT path FROM files
                WHERE ext IN ({placeholders})
                AND file_category = 'source'
                ORDER BY path
            """, extensions)

            files = [row[0] for row in cursor.fetchall()]
            logger.debug(f"Found {len(files)} files with extensions {extensions}")
            return files

        except sqlite3.OperationalError as e:
            logger.error(f"Database query failed (table missing or locked?): {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected database error: {e}")
            return []

    def _get_venv_binary(self, name: str) -> Optional[Path]:
        """Get path to binary in venv.

        Args:
            name: Binary name (e.g., 'ruff', 'mypy')

        Returns:
            Path to binary, or None if not found
        """
        venv_bin = self.root / ".auditor_venv" / ("Scripts" if IS_WINDOWS else "bin")
        binary = venv_bin / (f"{name}.exe" if IS_WINDOWS else name)

        if not binary.exists():
            logger.error(f"{name} not found at {binary}")
            return None

        return binary

    def _run_eslint(self, files: List[str]) -> List[Dict[str, Any]]:
        """Run ESLint with our config and parse output.

        Uses batching to avoid command-line length limits (Windows 8191 chars, Linux ~2MB).

        Args:
            files: List of file paths to lint

        Returns:
            List of finding dictionaries
        """
        # ESLint config from toolbox
        config_path = self.toolbox / "eslint.config.cjs"
        if not config_path.exists():
            logger.error(f"ESLint config not found: {config_path}")
            return []

        # Find ESLint binary in toolbox
        eslint_bin = self.toolbox / "node_modules" / ".bin" / ("eslint.cmd" if IS_WINDOWS else "eslint")

        if not eslint_bin.exists():
            logger.error(f"ESLint not found: {eslint_bin}")
            return []

        # Run in batches to avoid command-line length limits
        all_findings = []
        total_batches = (len(files) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_num, i in enumerate(range(0, len(files), BATCH_SIZE), 1):
            batch = files[i:i + BATCH_SIZE]
            logger.debug(f"Running ESLint batch {batch_num}/{total_batches} ({len(batch)} files)")

            findings = self._run_eslint_batch(batch, eslint_bin, config_path, batch_num)
            all_findings.extend(findings)

        logger.info(f"ESLint found {len(all_findings)} issues across {len(files)} files")
        return all_findings

    def _run_eslint_batch(self, files: List[str], eslint_bin: Path, config_path: Path, batch_num: int) -> List[Dict[str, Any]]:
        """Run ESLint on a single batch of files.

        Args:
            files: Batch of file paths to lint
            eslint_bin: Path to ESLint binary
            config_path: Path to ESLint config
            batch_num: Batch number for output file naming

        Returns:
            List of finding dictionaries from this batch
        """
        # Output file for JSON results (one per batch to avoid conflicts)
        output_file = self.root / ".pf" / "raw" / f"eslint_output_batch{batch_num}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Build command
        cmd = [
            str(eslint_bin),
            "--config", str(config_path),
            "--format", "json",
            "--output-file", str(output_file),
            *files
        ]

        # Run ESLint (exit code 1 = lint errors, that's OK)
        try:
            subprocess.run(cmd, cwd=str(self.root), timeout=LINTER_TIMEOUT, check=False)
        except subprocess.TimeoutExpired:
            logger.error(f"ESLint batch {batch_num} timed out after {LINTER_TIMEOUT} seconds")
            return []
        except Exception as e:
            logger.error(f"ESLint batch {batch_num} execution failed: {e}")
            return []

        # Parse JSON output
        if not output_file.exists():
            logger.warning(f"ESLint batch {batch_num} did not produce output file")
            return []

        try:
            with open(output_file, encoding='utf-8') as f:
                results = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"ESLint batch {batch_num} output is not valid JSON: {e}")
            return []

        # Convert to standardized findings
        findings = []
        for file_result in results:
            file_path = file_result.get("filePath", "")

            for msg in file_result.get("messages", []):
                findings.append({
                    "tool": "eslint",
                    "file": self._normalize_path(file_path),
                    "line": msg.get("line", 0),
                    "column": msg.get("column", 0),
                    "rule": msg.get("ruleId") or "eslint-error",
                    "message": msg.get("message", ""),
                    "severity": "error" if msg.get("severity") == 2 else "warning",
                    "category": "lint"
                })

        return findings

    def _run_ruff(self, files: List[str]) -> List[Dict[str, Any]]:
        """Run Ruff with our config and parse output.

        Uses batching to avoid command-line length limits.

        Args:
            files: List of file paths to lint

        Returns:
            List of finding dictionaries
        """
        # Ruff config from toolbox
        config_path = self.toolbox / "pyproject.toml"
        if not config_path.exists():
            logger.error(f"Ruff config not found: {config_path}")
            return []

        # Find Ruff binary in venv
        ruff_bin = self._get_venv_binary("ruff")
        if not ruff_bin:
            return []

        # Run in batches
        all_findings = []
        total_batches = (len(files) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_num, i in enumerate(range(0, len(files), BATCH_SIZE), 1):
            batch = files[i:i + BATCH_SIZE]
            logger.debug(f"Running Ruff batch {batch_num}/{total_batches} ({len(batch)} files)")

            findings = self._run_ruff_batch(batch, ruff_bin, config_path, batch_num)
            all_findings.extend(findings)

        logger.info(f"Ruff found {len(all_findings)} issues across {len(files)} files")
        return all_findings

    def _run_ruff_batch(self, files: List[str], ruff_bin: Path, config_path: Path, batch_num: int) -> List[Dict[str, Any]]:
        """Run Ruff on a single batch of files.

        Args:
            files: Batch of file paths to lint
            ruff_bin: Path to Ruff binary
            config_path: Path to Ruff config
            batch_num: Batch number for output file naming

        Returns:
            List of finding dictionaries from this batch
        """
        # Output file for JSON results
        output_file = self.root / ".pf" / "raw" / f"ruff_output_batch{batch_num}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Build command
        cmd = [
            str(ruff_bin),
            "check",
            "--config", str(config_path),
            "--output-format", "json",
            *files
        ]

        # Run Ruff and capture output
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.root),
                timeout=LINTER_TIMEOUT,
                check=False,
                capture_output=True,
                text=True
            )

            # Ruff outputs JSON to stdout
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result.stdout)

        except subprocess.TimeoutExpired:
            logger.error(f"Ruff batch {batch_num} timed out after {LINTER_TIMEOUT} seconds")
            return []
        except Exception as e:
            logger.error(f"Ruff batch {batch_num} execution failed: {e}")
            return []

        # Parse JSON output
        if not output_file.exists() or output_file.stat().st_size == 0:
            logger.debug(f"Ruff batch {batch_num} found no issues")
            return []

        try:
            with open(output_file, encoding='utf-8') as f:
                results = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Ruff batch {batch_num} output is not valid JSON: {e}")
            return []

        # Convert to standardized findings
        findings = []
        for item in results:
            findings.append({
                "tool": "ruff",
                "file": self._normalize_path(item.get("filename", "")),
                "line": item.get("location", {}).get("row", 0),
                "column": item.get("location", {}).get("column", 0),
                "rule": item.get("code", ""),
                "message": item.get("message", ""),
                "severity": "warning",  # Ruff doesn't distinguish error/warning
                "category": "lint"
            })

        return findings

    def _run_mypy(self, files: List[str]) -> List[Dict[str, Any]]:
        """Run Mypy with our config and parse output.

        Uses batching to avoid command-line length limits.

        Args:
            files: List of file paths to type-check

        Returns:
            List of finding dictionaries
        """
        # Mypy config from toolbox
        config_path = self.toolbox / "pyproject.toml"
        if not config_path.exists():
            logger.error(f"Mypy config not found: {config_path}")
            return []

        # Find Mypy binary in venv
        mypy_bin = self._get_venv_binary("mypy")
        if not mypy_bin:
            return []

        # Run in batches
        all_findings = []
        total_batches = (len(files) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_num, i in enumerate(range(0, len(files), BATCH_SIZE), 1):
            batch = files[i:i + BATCH_SIZE]
            logger.debug(f"Running Mypy batch {batch_num}/{total_batches} ({len(batch)} files)")

            findings = self._run_mypy_batch(batch, mypy_bin, config_path, batch_num)
            all_findings.extend(findings)

        logger.info(f"Mypy found {len(all_findings)} issues across {len(files)} files")
        return all_findings

    def _run_mypy_batch(self, files: List[str], mypy_bin: Path, config_path: Path, batch_num: int) -> List[Dict[str, Any]]:
        """Run Mypy on a single batch of files.

        Args:
            files: Batch of file paths to type-check
            mypy_bin: Path to Mypy binary
            config_path: Path to Mypy config
            batch_num: Batch number for output file naming

        Returns:
            List of finding dictionaries from this batch
        """
        # Output file for JSON results
        output_file = self.root / ".pf" / "raw" / f"mypy_output_batch{batch_num}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Build command
        cmd = [
            str(mypy_bin),
            "--config-file", str(config_path),
            "--output", "json",
            *files
        ]

        # Run Mypy and capture output
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.root),
                timeout=LINTER_TIMEOUT,
                check=False,
                capture_output=True,
                text=True
            )

            # Mypy outputs JSON to stdout
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result.stdout)

        except subprocess.TimeoutExpired:
            logger.error(f"Mypy batch {batch_num} timed out after {LINTER_TIMEOUT} seconds")
            return []
        except Exception as e:
            logger.error(f"Mypy batch {batch_num} execution failed: {e}")
            return []

        # Parse JSON output (mypy outputs one JSON object per line)
        if not output_file.exists() or output_file.stat().st_size == 0:
            logger.debug(f"Mypy batch {batch_num} found no issues")
            return []

        findings = []
        try:
            with open(output_file, encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                        findings.append({
                            "tool": "mypy",
                            "file": self._normalize_path(item.get("file", "")),
                            "line": item.get("line", 0),
                            "column": item.get("column", 0),
                            "rule": item.get("code", "type-error"),
                            "message": item.get("message", ""),
                            "severity": item.get("severity", "error"),
                            "category": "type"
                        })
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
        except Exception as e:
            logger.error(f"Failed to parse Mypy batch {batch_num} output: {e}")
            return []

        return findings

    def _normalize_path(self, path: str) -> str:
        """Normalize path to forward slashes and make relative to project root.

        Includes path traversal protection per security audit.

        Args:
            path: Absolute or relative path

        Returns:
            Normalized relative path with forward slashes
        """
        path = path.replace("\\", "/")

        # If path is absolute, make it relative to project root
        try:
            abs_path = Path(path)
            if abs_path.is_absolute():
                rel_path = abs_path.relative_to(self.root)

                # Security: Verify result doesn't escape root
                if ".." in str(rel_path):
                    logger.warning(f"Path escapes root directory: {path}")
                    return path

                return str(rel_path).replace("\\", "/")
        except ValueError:
            # Path is not under project root, keep as-is
            pass
        except OSError as e:
            logger.warning(f"Path normalization failed for {path}: {e}")

        return path

    def _write_json_output(self, findings: List[Dict[str, Any]]):
        """Write findings to JSON file for AI consumption.

        Args:
            findings: List of finding dictionaries

        Raises:
            IOError: If file write fails (disk full, permissions, etc.)
        """
        output_file = self.root / ".pf" / "raw" / "lint.json"

        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create output directory: {e}")
            raise IOError(f"Cannot create {output_file.parent}: {e}") from e

        # Sort for determinism
        sorted_findings = sorted(findings, key=lambda f: (f["file"], f["line"], f["rule"]))

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(sorted_findings, f, indent=2, sort_keys=True)
            logger.info(f"Wrote {len(findings)} findings to {output_file}")
        except IOError as e:
            logger.error(f"Failed to write lint.json (disk full? permissions?): {e}")
            raise  # Don't silently fail - this is critical for AI consumption
        except Exception as e:
            logger.error(f"Unexpected error writing lint.json: {e}")
            raise IOError(f"Failed to write {output_file}: {e}") from e
