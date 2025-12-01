"""Clippy linter implementation.

Clippy is the Rust linter. It runs via cargo clippy on the entire crate -
you cannot selectively lint individual files. We run it on the whole project
and filter output to match requested files.
"""

import json
import shutil

from theauditor.linters.base import LINTER_TIMEOUT, BaseLinter, Finding
from theauditor.utils.logging import logger


class ClippyLinter(BaseLinter):
    """Clippy linter for Rust files.

    Runs cargo clippy on the entire crate with JSON output.
    Crate-level execution - cannot target individual files.
    """

    @property
    def name(self) -> str:
        return "clippy"

    async def run(self, files: list[str]) -> list[Finding]:
        """Run Clippy on Rust project.

        Clippy runs on the entire crate (cannot target individual files),
        but output is filtered to match the requested files list.

        Args:
            files: List of Rust file paths to filter output to

        Returns:
            List of Finding objects from Clippy analysis (filtered to requested files)
        """
        # Check for Cargo.toml
        cargo_toml = self.root / "Cargo.toml"
        if not cargo_toml.exists():
            logger.debug(f"[{self.name}] No Cargo.toml found - skipping")
            return []

        # Check cargo is available
        if not shutil.which("cargo"):
            logger.warning(f"[{self.name}] Cargo not found - skipping Rust linting")
            return []

        cmd = [
            "cargo",
            "clippy",
            "--message-format=json",
            "--",
            "-W",
            "clippy::all",
        ]

        try:
            returncode, stdout, stderr = await self._run_command(cmd, timeout=LINTER_TIMEOUT)
        except TimeoutError:
            logger.error(f"[{self.name}] Timed out")
            return []

        # Build set of requested files for O(1) filtering
        requested_files = set(files) if files else set()

        all_findings = []
        for line in stdout.splitlines():
            if not line.strip():
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Only process compiler messages
            if msg.get("reason") != "compiler-message":
                continue

            finding = self._parse_clippy_message(msg)
            if finding:
                all_findings.append(finding)

        # Filter to requested files only
        if requested_files:
            findings = [f for f in all_findings if f.file in requested_files]
            logger.info(
                f"[{self.name}] Found {len(findings)} issues in requested files "
                f"({len(all_findings)} total in crate)"
            )
        else:
            findings = all_findings
            logger.info(f"[{self.name}] Found {len(findings)} issues")

        return findings

    def _parse_clippy_message(self, msg: dict) -> Finding | None:
        """Parse a Clippy compiler message into a Finding.

        Args:
            msg: Parsed JSON object with reason == "compiler-message"

        Returns:
            Finding object or None if parsing fails
        """
        message = msg.get("message", {})

        spans = message.get("spans", [])
        if not spans:
            return None

        # Get primary span, or first span
        primary_span = next((s for s in spans if s.get("is_primary")), spans[0])

        file_name = primary_span.get("file_name", "")
        line = primary_span.get("line_start", 0)
        column = primary_span.get("column_start", 0)

        # Extract rule code
        code = message.get("code", {})
        rule = code.get("code", "") if code else "clippy"

        # Map severity
        level = message.get("level", "warning")
        severity_map = {
            "error": "error",
            "warning": "warning",
            "note": "info",
            "help": "info",
        }
        severity = severity_map.get(level, "warning")

        return Finding(
            tool=self.name,
            file=self._normalize_path(file_name),
            line=line,
            column=column,
            rule=rule,
            message=message.get("message", ""),
            severity=severity,
            category="lint",
        )
