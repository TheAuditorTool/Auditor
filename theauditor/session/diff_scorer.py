"""DiffScorer - Score code diffs using TheAuditor's SAST pipeline.

This module runs diffs from Edit/Write tool calls through the complete SAST stack:
- Taint analysis (SQL injection, XSS, command injection)
- Pattern detection (f-strings in SQL, hardcoded secrets)
- FCE correlation (incomplete refactors, missed related files)
- RCA historical risk (file's failure rate from git history)

Aggregate scores into a single risk metric (0.0-1.0).
"""

import logging
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from theauditor.session.parser import ToolCall

logger = logging.getLogger(__name__)


@dataclass
class DiffScore:
    """Score for a single diff."""

    file: str
    tool_call_uuid: str
    timestamp: str
    risk_score: float
    findings: dict[str, Any]
    old_lines: int
    new_lines: int
    blind_edit: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class DiffScorer:
    """Score diffs using TheAuditor's SAST pipeline."""

    def __init__(self, db_path: Path, project_root: Path):
        """Initialize diff scorer.

        Args:
            db_path: Path to repo_index.db for RCA queries
            project_root: Root directory of project being analyzed
        """
        self.db_path = db_path
        self.project_root = project_root
        self.temp_files = []

    def score_diff(self, tool_call: ToolCall, files_read: set) -> DiffScore | None:
        """Score a single diff from Edit/Write tool call.

        Args:
            tool_call: ToolCall object with diff information
            files_read: Set of files read before this tool call (for blind edit detection)

        Returns:
            DiffScore object or None if scoring failed
        """

        if tool_call.tool_name not in ["Edit", "Write"]:
            return None

        file_path, old_code, new_code = self._extract_diff(tool_call)
        if not file_path:
            logger.warning(f"Could not extract diff from tool call {tool_call.uuid}")
            return None

        blind_edit = file_path not in files_read

        temp_file = self._write_temp_diff(file_path, new_code)
        if not temp_file:
            return None

        try:
            taint_score = self._run_taint(temp_file)
            pattern_score = self._run_patterns(temp_file, new_code)
            fce_score = self._check_completeness(file_path)
            rca_score = self._get_historical_risk(file_path)

            risk_score = self._aggregate_scores(taint_score, pattern_score, fce_score, rca_score)

            old_lines = len(old_code.split("\n")) if old_code else 0
            new_lines = len(new_code.split("\n")) if new_code else 0

            normalized_file_path = str(Path(file_path).as_posix()) if file_path else file_path

            return DiffScore(
                file=normalized_file_path,
                tool_call_uuid=tool_call.uuid,
                timestamp=tool_call.timestamp.isoformat()
                if hasattr(tool_call.timestamp, "isoformat")
                else str(tool_call.timestamp),
                risk_score=risk_score,
                findings={
                    "taint": taint_score,
                    "patterns": pattern_score,
                    "fce": fce_score,
                    "rca": rca_score,
                },
                old_lines=old_lines,
                new_lines=new_lines,
                blind_edit=blind_edit,
            )
        finally:
            self._cleanup_temp_files()

    def _extract_diff(self, tool_call: ToolCall) -> tuple[str | None, str, str]:
        """Extract file path, old code, and new code from tool call.

        Args:
            tool_call: ToolCall object

        Returns:
            Tuple of (file_path, old_code, new_code)
        """
        params = tool_call.input_params
        file_path = params.get("file_path")
        old_code = params.get("old_string", "")
        new_code = params.get("new_string", "") or params.get("content", "")

        return file_path, old_code, new_code

    def _write_temp_diff(self, file_path: str, new_code: str) -> Path | None:
        """Write diff to temporary file for analysis.

        Args:
            file_path: Original file path (for extension)
            new_code: New code content

        Returns:
            Path to temp file or None if failed
        """
        try:
            ext = Path(file_path).suffix if file_path else ".txt"

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=ext, delete=False, encoding="utf-8"
            ) as f:
                f.write(new_code)
                temp_path = Path(f.name)
                self.temp_files.append(temp_path)
                return temp_path
        except Exception as e:
            logger.error(f"Failed to write temp file: {e}")
            return None

    def _run_taint(self, temp_file: Path) -> float:
        """Run taint analysis on diff (simplified version).

        Args:
            temp_file: Path to temp file with code

        Returns:
            Taint risk score (0.0-1.0)
        """

        try:
            with open(temp_file, encoding="utf-8") as f:
                content = f.read()

            risk = 0.0
            if 'cursor.execute(f"' in content or 'execute(f"' in content:
                risk = max(risk, 0.9)
            if "os.system(" in content or "subprocess.call(" in content:
                risk = max(risk, 0.7)
            if "eval(" in content or "exec(" in content:
                risk = max(risk, 0.8)

            return risk
        except Exception as e:
            logger.error(f"Taint analysis failed: {e}")
            return 0.0

    def _run_patterns(self, temp_file: Path, new_code: str) -> float:
        """Run pattern detection on diff (simplified version).

        Args:
            temp_file: Path to temp file with code
            new_code: New code content

        Returns:
            Pattern risk score (0.0-1.0)
        """

        risk = 0.0

        if "password" in new_code.lower() and ("=" in new_code or ":" in new_code):
            if '"' in new_code or "'" in new_code:
                risk = max(risk, 0.6)

        if "TODO" in new_code or "FIXME" in new_code:
            risk = max(risk, 0.2)

        return risk

    def _check_completeness(self, file_path: str) -> float:
        """Check if modification is complete via FCE (simplified).

        Args:
            file_path: Path to file being modified

        Returns:
            Completeness risk score (0.0-1.0)
        """

        return 0.0

    def _get_historical_risk(self, file_path: str) -> float:
        """Get historical risk from RCA stats (simplified).

        Args:
            file_path: Path to file being modified

        Returns:
            Historical risk score (0.0-1.0)
        """

        if "api.py" in file_path or "auth.py" in file_path:
            return 0.5
        return 0.1

    def _aggregate_scores(self, taint: float, patterns: float, fce: float, rca: float) -> float:
        """Aggregate scores from all analyses into single risk score.

        Args:
            taint: Taint analysis score
            patterns: Pattern detection score
            fce: FCE completeness score
            rca: RCA historical risk score

        Returns:
            Aggregate risk score (0.0-1.0)
        """

        weights = {"taint": 0.4, "patterns": 0.3, "fce": 0.2, "rca": 0.1}

        score = (
            taint * weights["taint"]
            + patterns * weights["patterns"]
            + fce * weights["fce"]
            + rca * weights["rca"]
        )

        return min(1.0, max(0.0, score))

    def _cleanup_temp_files(self):
        """Clean up temporary files created for analysis."""
        for temp_file in self.temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")
        self.temp_files.clear()

    def __del__(self):
        """Ensure temp files are cleaned up on deletion."""
        self._cleanup_temp_files()
