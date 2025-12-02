"""theauditor/linters.py - Run external linters and store findings."""

import json
import platform
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from theauditor.indexer.database import DatabaseManager
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


IS_WINDOWS = platform.system() == "Windows"


LINTER_TIMEOUT = 300
BATCH_SIZE = 100


ESLINT_SEVERITY_ERROR = 2
ESLINT_SEVERITY_WARNING = 1


class LinterOrchestrator:
    """Coordinates running external linters on project files."""

    def __init__(self, root_path: str, db_path: str):
        """Initialize with project root and database path."""
        self.root = Path(root_path).resolve()

        if not self.root.exists():
            raise ValueError(f"Root path does not exist: {self.root}")
        if not self.root.is_dir():
            raise ValueError(f"Root path is not a directory: {self.root}")

        db_path_obj = Path(db_path)
        if not db_path_obj.exists():
            raise ValueError(f"Database not found: {db_path}")

        self.db = DatabaseManager(db_path)
        self.toolbox = self.root / ".auditor_venv" / ".theauditor_tools"

        if not self.toolbox.exists():
            raise RuntimeError(
                f"Toolbox not found at {self.toolbox}. "
                f"Run 'aud setup-ai --target {self.root}' first."
            )

        logger.info(f"LinterOrchestrator initialized: root={self.root}, toolbox={self.toolbox}")

    def run_all_linters(self, workset_files: list[str] | None = None) -> list[dict[str, Any]]:
        """Run all available linters on appropriate files."""
        findings = []

        js_files = self._get_source_files([".js", ".jsx", ".ts", ".tsx", ".mjs"])
        py_files = self._get_source_files([".py"])
        rs_files = self._get_source_files([".rs"])

        if workset_files:
            workset_set = set(workset_files)
            js_files = [f for f in js_files if f in workset_set]
            py_files = [f for f in py_files if f in workset_set]
            rs_files = [f for f in rs_files if f in workset_set]

        if js_files:
            logger.info(f"Running ESLint on {len(js_files)} JavaScript files")
            findings.extend(self._run_eslint(js_files))

        if py_files:
            logger.info(f"Running Ruff on {len(py_files)} Python files")
            findings.extend(self._run_ruff(py_files))

            logger.info(f"Running Mypy on {len(py_files)} Python files")
            findings.extend(self._run_mypy(py_files))

        if rs_files:
            logger.info(f"Running Clippy on {len(rs_files)} Rust files")
            findings.extend(self._run_clippy())

        if findings:
            # Filter out findings for files not in the database (e.g., venv, node_modules, typeshed stubs)
            # These cause FK violations since they weren't indexed
            excluded_prefixes = (".auditor_venv", ".venv", "node_modules", "__pycache__")
            original_count = len(findings)
            findings = [
                f for f in findings
                if not f.get("file", "").startswith(excluded_prefixes)
            ]
            if len(findings) < original_count:
                logger.info(f"Filtered {original_count - len(findings)} findings from excluded paths")

            if findings:
                logger.info(f"Writing {len(findings)} findings to database")
                self.db.write_findings_batch(findings, "lint")

        self._write_json_output(findings)

        return findings

    def _get_source_files(self, extensions: list[str]) -> list[str]:
        """Query database for source files with given extensions."""
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

    def _get_venv_binary(self, name: str) -> Path:
        """Get path to binary in venv."""
        venv_bin = self.root / ".auditor_venv" / ("Scripts" if IS_WINDOWS else "bin")
        binary = venv_bin / (f"{name}.exe" if IS_WINDOWS else name)

        if not binary.exists():
            raise FileNotFoundError(
                f"{name} not found at {binary}. "
                f"Run 'aud setup-ai --target {self.root}' to install linting tools."
            )

        return binary

    def _run_eslint(self, files: list[str]) -> list[dict[str, Any]]:
        """Run ESLint with our config and parse output."""

        config_path = self.toolbox / "eslint.config.cjs"
        if not config_path.exists():
            logger.error(f"ESLint config not found: {config_path}")
            return []

        eslint_bin = (
            self.toolbox / "node_modules" / ".bin" / ("eslint.cmd" if IS_WINDOWS else "eslint")
        )

        if not eslint_bin.exists():
            logger.error(f"ESLint not found: {eslint_bin}")
            return []

        all_findings = []
        total_batches = (len(files) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_num, i in enumerate(range(0, len(files), BATCH_SIZE), 1):
            batch = files[i : i + BATCH_SIZE]
            logger.debug(f"Running ESLint batch {batch_num}/{total_batches} ({len(batch)} files)")

            findings = self._run_eslint_batch(batch, eslint_bin, config_path, batch_num)
            all_findings.extend(findings)

        logger.info(f"ESLint found {len(all_findings)} issues across {len(files)} files")
        return all_findings

    def _run_eslint_batch(
        self, files: list[str], eslint_bin: Path, config_path: Path, batch_num: int
    ) -> list[dict[str, Any]]:
        """Run ESLint on a single batch of files."""

        temp_dir = self.root / ".pf" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_file = temp_dir / f"eslint_output_batch{batch_num}.json"

        cmd = [
            str(eslint_bin),
            "--config",
            str(config_path),
            "--format",
            "json",
            "--output-file",
            str(output_file),
            *files,
        ]

        try:
            subprocess.run(cmd, cwd=str(self.root), timeout=LINTER_TIMEOUT, check=False)
        except subprocess.TimeoutExpired:
            logger.error(f"ESLint batch {batch_num} timed out after {LINTER_TIMEOUT} seconds")
            return []
        except Exception as e:
            logger.error(f"ESLint batch {batch_num} execution failed: {e}")
            return []

        if not output_file.exists():
            logger.warning(f"ESLint batch {batch_num} did not produce output file")
            return []

        try:
            with open(output_file, encoding="utf-8") as f:
                results = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"ESLint batch {batch_num} output is not valid JSON: {e}")
            return []

        findings = []
        for file_result in results:
            file_path = file_result.get("filePath", "")

            for msg in file_result.get("messages", []):
                findings.append(
                    {
                        "tool": "eslint",
                        "file": self._normalize_path(file_path),
                        "line": msg.get("line", 0),
                        "column": msg.get("column", 0),
                        "rule": msg.get("ruleId") or "eslint-error",
                        "message": msg.get("message", ""),
                        "severity": "error"
                        if msg.get("severity") == ESLINT_SEVERITY_ERROR
                        else "warning",
                        "category": "lint",
                    }
                )

        try:
            output_file.unlink()
        except OSError:
            logger.debug(f"Could not remove temp file: {output_file}")

        return findings

    def _run_ruff(self, files: list[str]) -> list[dict[str, Any]]:
        """Run Ruff with our config and parse output."""

        config_path = self.toolbox / "pyproject.toml"
        if not config_path.exists():
            logger.error(f"Ruff config not found: {config_path}")
            return []

        ruff_bin = self._get_venv_binary("ruff")

        all_findings = []
        total_batches = (len(files) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_num, i in enumerate(range(0, len(files), BATCH_SIZE), 1):
            batch = files[i : i + BATCH_SIZE]
            logger.debug(f"Running Ruff batch {batch_num}/{total_batches} ({len(batch)} files)")

            findings = self._run_ruff_batch(batch, ruff_bin, config_path, batch_num)
            all_findings.extend(findings)

        logger.info(f"Ruff found {len(all_findings)} issues across {len(files)} files")
        return all_findings

    def _run_ruff_batch(
        self, files: list[str], ruff_bin: Path, config_path: Path, batch_num: int
    ) -> list[dict[str, Any]]:
        """Run Ruff on a single batch of files."""

        temp_dir = self.root / ".pf" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_file = temp_dir / f"ruff_output_batch{batch_num}.json"

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
            result = subprocess.run(
                cmd,
                cwd=str(self.root),
                timeout=LINTER_TIMEOUT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            stdout = result.stdout or ""
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(stdout)

        except subprocess.TimeoutExpired:
            logger.error(f"Ruff batch {batch_num} timed out after {LINTER_TIMEOUT} seconds")
            return []
        except Exception as e:
            logger.error(f"Ruff batch {batch_num} execution failed: {e}")
            return []

        if not output_file.exists() or output_file.stat().st_size == 0:
            logger.debug(f"Ruff batch {batch_num} found no issues")
            return []

        try:
            with open(output_file, encoding="utf-8") as f:
                results = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Ruff batch {batch_num} output is not valid JSON: {e}")
            return []

        findings = []
        for item in results:
            location = item.get("location", {}) or {}
            rule_code = (item.get("code") or "").strip()
            if not rule_code:
                rule_code = "ruff-unknown"

            findings.append(
                {
                    "tool": "ruff",
                    "file": self._normalize_path(item.get("filename", "")),
                    "line": location.get("row", 0),
                    "column": location.get("column", 0),
                    "rule": rule_code,
                    "message": item.get("message", ""),
                    "severity": "warning",
                    "category": "lint",
                }
            )

        try:
            output_file.unlink()
        except OSError:
            logger.debug(f"Could not remove temp file: {output_file}")

        return findings

    def _run_mypy(self, files: list[str]) -> list[dict[str, Any]]:
        """Run Mypy with our config and parse output."""

        config_path = self.toolbox / "pyproject.toml"
        if not config_path.exists():
            logger.error(f"Mypy config not found: {config_path}")
            return []

        mypy_bin = self._get_venv_binary("mypy")

        all_findings = []
        total_batches = (len(files) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_num, i in enumerate(range(0, len(files), BATCH_SIZE), 1):
            batch = files[i : i + BATCH_SIZE]
            logger.debug(f"Running Mypy batch {batch_num}/{total_batches} ({len(batch)} files)")

            findings = self._run_mypy_batch(batch, mypy_bin, config_path, batch_num)
            all_findings.extend(findings)

        logger.info(f"Mypy found {len(all_findings)} issues across {len(files)} files")
        return all_findings

    def _run_mypy_batch(
        self, files: list[str], mypy_bin: Path, config_path: Path, batch_num: int
    ) -> list[dict[str, Any]]:
        """Run Mypy on a single batch of files."""

        temp_dir = self.root / ".pf" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_file = temp_dir / f"mypy_output_batch{batch_num}.json"

        cmd = [str(mypy_bin), "--config-file", str(config_path), "--output", "json", *files]

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.root),
                timeout=LINTER_TIMEOUT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            stdout = result.stdout or ""
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(stdout)

        except subprocess.TimeoutExpired:
            logger.error(f"Mypy batch {batch_num} timed out after {LINTER_TIMEOUT} seconds")
            return []
        except Exception as e:
            logger.error(f"Mypy batch {batch_num} execution failed: {e}")
            return []

        if not output_file.exists() or output_file.stat().st_size == 0:
            logger.debug(f"Mypy batch {batch_num} found no issues")
            return []

        findings = []
        try:
            with open(output_file, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                        source_file = self._normalize_path(item.get("file", ""))
                        raw_severity = (item.get("severity") or "error").lower()
                        original_code = item.get("code")
                        rule_code = (original_code or "").strip()

                        if not rule_code:
                            rule_code = "mypy-note" if raw_severity == "note" else "mypy-unknown"

                        line_no = item.get("line", 0)
                        if isinstance(line_no, int) and line_no < 0:
                            line_no = 0

                        column_no = item.get("column", 0)
                        if isinstance(column_no, int) and column_no < 0:
                            column_no = 0

                        if raw_severity == "note":
                            mapped_severity = "info"
                            category = "lint-meta"
                        else:
                            mapped_severity = (
                                raw_severity if raw_severity in {"error", "warning"} else "error"
                            )
                            category = "type"

                        additional = {}
                        if item.get("hint"):
                            additional["hint"] = item["hint"]
                        additional["mypy_severity"] = raw_severity
                        if original_code:
                            additional["mypy_code"] = original_code

                        findings.append(
                            {
                                "tool": "mypy",
                                "file": source_file,
                                "line": line_no,
                                "column": column_no,
                                "rule": rule_code,
                                "message": item.get("message", ""),
                                "severity": mapped_severity,
                                "category": category,
                                "additional_info": additional,
                            }
                        )
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to parse Mypy batch {batch_num} output: {e}")
            return []

        try:
            output_file.unlink()
        except OSError:
            logger.debug(f"Could not remove temp file: {output_file}")

        return findings

    def _normalize_path(self, path: str) -> str:
        """Normalize path to forward slashes and make relative to project root."""
        path = path.replace("\\", "/")

        try:
            abs_path = Path(path)
            if abs_path.is_absolute():
                rel_path = abs_path.relative_to(self.root)

                if ".." in str(rel_path):
                    logger.warning(f"Path escapes root directory: {path}")
                    return path

                return str(rel_path).replace("\\", "/")
        except ValueError:
            pass
        except OSError as e:
            logger.warning(f"Path normalization failed for {path}: {e}")

        return path

    def _write_json_output(self, findings: list[dict[str, Any]]):
        """Write findings to JSON file for AI consumption."""
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

    def _run_clippy(self) -> list[dict[str, Any]]:
        """Run Cargo Clippy on Rust project and parse output."""

        cargo_toml = self.root / "Cargo.toml"
        if not cargo_toml.exists():
            logger.debug("No Cargo.toml found - skipping Clippy")
            return []

        try:
            subprocess.run(
                ["cargo", "--version"],
                check=True,
                capture_output=True,
                timeout=5,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("Cargo not found - skipping Clippy. Install Rust toolchain to enable.")
            return []

        logger.info("Running Clippy on Rust project...")

        cmd = ["cargo", "clippy", "--message-format=json", "--", "-W", "clippy::all"]

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.root),
                timeout=LINTER_TIMEOUT,
                check=False,
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired:
            logger.error(f"Clippy timed out after {LINTER_TIMEOUT} seconds")
            return []
        except Exception as e:
            logger.error(f"Clippy execution failed: {e}")
            return []

        findings = []
        for json_line in result.stdout.splitlines():
            if not json_line.strip():
                continue

            try:
                msg = json.loads(json_line)

                if msg.get("reason") != "compiler-message":
                    continue

                message = msg.get("message", {})

                spans = message.get("spans", [])
                if not spans:
                    continue

                primary_span = next((s for s in spans if s.get("is_primary")), spans[0])

                file_name = primary_span.get("file_name", "")
                line = primary_span.get("line_start", 0)
                column = primary_span.get("column_start", 0)

                code = message.get("code", {})
                rule = code.get("code", "") if code else "clippy"

                level = message.get("level", "warning")
                severity_map = {
                    "error": "error",
                    "warning": "warning",
                    "note": "info",
                    "help": "info",
                }
                severity = severity_map.get(level, "warning")

                findings.append(
                    {
                        "tool": "clippy",
                        "file": self._normalize_path(file_name),
                        "line": line,
                        "column": column,
                        "rule": rule,
                        "message": message.get("message", ""),
                        "severity": severity,
                        "category": "lint",
                    }
                )

            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.debug(f"Skipping malformed Clippy output line: {e}")
                continue

        logger.info(f"Clippy found {len(findings)} issues")
        return findings
