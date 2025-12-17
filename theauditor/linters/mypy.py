"""Mypy linter implementation.

Mypy is a static type checker for Python. It needs full project context
for cross-file type inference, so we pass all files in a single invocation
(no batching).
"""

import json
import time

from theauditor.linters.base import BaseLinter, Finding, LinterResult
from theauditor.utils.logging import logger


class MypyLinter(BaseLinter):
    """Mypy type checker for Python files.

    Executes mypy with JSON output (JSONL - one JSON object per line).
    No batching - Mypy needs full project context for cross-file type inference.

    Prefers project's mypy configuration (pyproject.toml, mypy.ini, .mypy.ini,
    setup.cfg) over TheAuditor's bundled defaults.
    """

    @property
    def name(self) -> str:
        return "mypy"

    def _find_project_mypy_config(self) -> str | None:
        """Check if project has its own mypy configuration.

        Searches for mypy config in standard locations, in priority order:
        1. mypy.ini - dedicated mypy config file
        2. .mypy.ini - hidden dedicated mypy config file
        3. pyproject.toml - if contains [tool.mypy] section
        4. setup.cfg - if contains [mypy] section

        Returns:
            Path to config file if found, None otherwise.
        """
        # Check for dedicated mypy config files first (highest priority)
        for config_name in ["mypy.ini", ".mypy.ini"]:
            config_path = self.root / config_name
            if config_path.exists():
                return str(config_path)

        # Check pyproject.toml for [tool.mypy] section
        pyproject = self.root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if "[tool.mypy]" in content:
                    return str(pyproject)
            except Exception:
                pass

        # Check setup.cfg for [mypy] section
        setup_cfg = self.root / "setup.cfg"
        if setup_cfg.exists():
            try:
                content = setup_cfg.read_text()
                if "[mypy]" in content:
                    return str(setup_cfg)
            except Exception:
                pass

        return None

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

        # Prefer project's mypy config over TheAuditor's bundled default
        project_config = self._find_project_mypy_config()
        if project_config:
            config_path = project_config
            logger.debug(f"[{self.name}] Using project config: {config_path}")
        else:
            default_config = self.toolbox.get_python_linter_config()
            if not default_config.exists():
                return LinterResult.skipped(
                    self.name, f"Mypy config not found: {default_config}"
                )
            config_path = str(default_config)
            logger.debug(f"[{self.name}] Using TheAuditor default config: {config_path}")

        start_time = time.perf_counter()

        cmd = [
            str(mypy_bin),
            "--config-file",
            config_path,
            "--output",
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

        findings = []
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

        duration = time.perf_counter() - start_time
        logger.info(
            f"[{self.name}] Found {len(findings)} issues in {len(files)} files ({duration:.2f}s)"
        )
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
