"""Mypy linter implementation.

Mypy is a static type checker for Python. It needs full project context
for cross-file type inference, so we pass all files in a single invocation
(no batching).
"""

import json
import time
from pathlib import Path

from theauditor.linters.base import BaseLinter, Finding, LinterResult
from theauditor.linters.config_generator import ConfigGenerator
from theauditor.utils.logging import logger


class MypyLinter(BaseLinter):
    """Mypy type checker for Python files.

    Executes mypy with JSON output (JSONL - one JSON object per line).
    No batching - Mypy needs full project context for cross-file type inference.
    """

    @property
    def name(self) -> str:
        return "mypy"

    async def _run_pass(
        self,
        files: list[str],
        mypy_bin: Path,
        config_path: Path,
    ) -> list[Finding]:
        """Run a single mypy pass with the provided config."""
        cmd = [
            str(mypy_bin),
            "--config-file",
            str(config_path),
            "--output",
            "json",
            *files,
        ]

        _returncode, stdout, _stderr = await self._run_command(cmd)

        if not stdout.strip():
            return []

        findings: list[Finding] = []
        for line in stdout.splitlines():
            if not line.strip():
                continue

            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            finding = self._parse_mypy_item(item)
            if finding:
                findings.append(finding)

        return findings

    async def run(self, files: list[str]) -> LinterResult:
        """Run Mypy on Python files.

        Args:
            files: List of Python file paths relative to project root

        Returns:
            LinterResult with status and findings
        """
        if not files:
            return LinterResult.success(self.name, [], 0.0)

        mypy_bin = self.toolbox.get_venv_binary("mypy", required=False)
        if not mypy_bin:
            return LinterResult.skipped(self.name, "Mypy not found")

        # Generate mypy config dynamically based on project analysis
        db_path = self.root / ".pf" / "repo_index.db"
        if not db_path.exists():
            return LinterResult.skipped(
                self.name, "Database not found - run indexing first (aud full --index)"
            )

        try:
            with ConfigGenerator(self.root, db_path) as config_gen:
                config_path = config_gen.generate_python_config(force_strict=False)
        except Exception as e:
            logger.warning(f"Failed to generate mypy config: {e}")
            return LinterResult.skipped(self.name, f"Config generation failed: {e}")

        generated_config = self.root / ".pf" / "temp" / "mypy.ini"
        use_project_config = config_path.resolve() != generated_config.resolve()

        start_time = time.perf_counter()

        try:
            findings = await self._run_pass(files, mypy_bin, config_path)
        except TimeoutError:
            return LinterResult.failed(self.name, "Timed out", time.perf_counter() - start_time)
        except Exception as e:
            return LinterResult.failed(self.name, f"Run failed: {e}", time.perf_counter() - start_time)

        suppressed_count = 0
        if use_project_config:
            logger.info(f"[{self.name}] Project config detected. Running audit pass...")
            strict_config: Path | None = None
            try:
                with ConfigGenerator(self.root, db_path) as config_gen:
                    strict_config = config_gen.generate_python_config(force_strict=True)
            except Exception as e:
                logger.warning(f"[{self.name}] Audit config generation failed: {e}")

            if strict_config:
                try:
                    strict_findings = await self._run_pass(files, mypy_bin, strict_config)
                except TimeoutError:
                    logger.warning(f"[{self.name}] Audit pass timed out")
                    strict_findings = []
                except Exception as e:
                    logger.warning(f"[{self.name}] Audit pass failed: {e}")
                    strict_findings = []

                if strict_findings:
                    seen = {(f.file, f.line, f.column, f.rule) for f in findings}
                    for finding in strict_findings:
                        key = (finding.file, finding.line, finding.column, finding.rule)
                        if key in seen:
                            continue

                        finding.category = "suppressed-risk"
                        finding.severity = "warning"
                        finding.message = (
                            f"[SUPPRESSED RISK] {finding.message}"
                            if finding.message
                            else "[SUPPRESSED RISK]"
                        )
                        additional = finding.additional_info or {}
                        additional["audit_finding"] = True
                        finding.additional_info = additional
                        findings.append(finding)
                        suppressed_count += 1

        duration = time.perf_counter() - start_time

        if not findings:
            logger.debug(f"[{self.name}] No issues found")
        else:
            logger.info(
                f"[{self.name}] Found {len(findings)} issues in {len(files)} files "
                f"({duration:.2f}s)"
            )

        if suppressed_count:
            logger.info(f"[{self.name}] Audit revealed {suppressed_count} suppressed issues")

        return LinterResult.success(self.name, findings, duration)

    def _parse_mypy_item(self, item: dict) -> Finding | None:
        """Parse a single Mypy JSON output item into a Finding.

        Args:
            item: Parsed JSON object from Mypy output

        Returns:
            Finding object or None if parsing fails
        """
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
            mapped_severity = raw_severity if raw_severity in {"error", "warning"} else "error"
            category = "type"

        additional = {}
        if item.get("hint"):
            additional["hint"] = item["hint"]
        additional["mypy_severity"] = raw_severity
        if original_code:
            additional["mypy_code"] = original_code

        return Finding(
            tool=self.name,
            file=source_file,
            line=line_no,
            column=column_no,
            rule=rule_code,
            message=item.get("message", ""),
            severity=mapped_severity,
            category=category,
            additional_info=additional if additional else None,
        )
