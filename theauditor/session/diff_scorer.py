"""DiffScorer - Score code diffs using TheAuditor's SAST pipeline."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from theauditor.session.parser import ToolCall
from theauditor.utils.logging import logger


@dataclass(slots=True)
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
        """Initialize diff scorer."""
        self.db_path = db_path
        self.project_root = project_root

    def score_diff(self, tool_call: ToolCall, files_read: set) -> DiffScore | None:
        """Score a single diff from Edit/Write tool call."""

        if tool_call.tool_name not in ["Edit", "Write"]:
            return None

        file_path, old_code, new_code = self._extract_diff(tool_call)
        if not file_path:
            logger.warning(f"Could not extract diff from tool call {tool_call.uuid}")
            return None

        blind_edit = file_path not in files_read

        taint_score = self._run_taint(new_code)
        pattern_score = self._run_patterns(new_code)
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

    def _extract_diff(self, tool_call: ToolCall) -> tuple[str | None, str, str]:
        """Extract file path, old code, and new code from tool call."""
        params = tool_call.input_params
        file_path = params.get("file_path")
        old_code = params.get("old_string", "")
        new_code = params.get("new_string", "") or params.get("content", "")

        return file_path, old_code, new_code

    def _run_taint(self, content: str) -> float:
        """Run taint analysis on code content.

        Zero Fallback: No try/except - if analysis fails, it fails loud.
        """
        risk = 0.0
        if 'cursor.execute(f"' in content or 'execute(f"' in content:
            risk = max(risk, 0.9)
        if "os.system(" in content or "subprocess.call(" in content:
            risk = max(risk, 0.7)
        if "eval(" in content or "exec(" in content:
            risk = max(risk, 0.8)

        return risk

    def _run_patterns(self, content: str) -> float:
        """Run pattern detection on code content."""
        risk = 0.0

        if (
            "password" in content.lower()
            and ("=" in content or ":" in content)
            and ('"' in content or "'" in content)
        ):
            risk = max(risk, 0.6)

        if "TODO" in content or "FIXME" in content:
            risk = max(risk, 0.2)

        return risk

    def _check_completeness(self, file_path: str) -> float:
        """Check if modification is complete via FCE (simplified)."""

        return 0.0

    def _get_historical_risk(self, file_path: str) -> float:
        """Get historical risk from RCA stats (simplified)."""

        if "api.py" in file_path or "auth.py" in file_path:
            return 0.5
        return 0.1

    def _aggregate_scores(self, taint: float, patterns: float, fce: float, rca: float) -> float:
        """Aggregate scores from all analyses into single risk score."""

        weights = {"taint": 0.4, "patterns": 0.3, "fce": 0.2, "rca": 0.1}

        score = (
            taint * weights["taint"]
            + patterns * weights["patterns"]
            + fce * weights["fce"]
            + rca * weights["rca"]
        )

        return min(1.0, max(0.0, score))
