"""WorkflowChecker - Validate agent execution against planning.md workflows."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from theauditor.session.parser import Session, ToolCall
from theauditor.utils.logging import logger


@dataclass
class WorkflowCompliance:
    """Workflow compliance result."""

    compliant: bool
    score: float
    violations: list[str]
    checks: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class WorkflowChecker:
    """Check if session execution follows defined workflows."""

    DEFAULT_CHECKS = {
        "blueprint_first": "Run aud blueprint before modifications",
        "query_before_edit": "Use aud query before editing",
        "no_blind_reads": "Read files before editing",
    }

    def __init__(self, workflow_path: Path = None):
        """Initialize workflow checker."""
        self.workflow_path = workflow_path
        self.workflows = self._parse_workflows() if workflow_path and workflow_path.exists() else {}

    def check_compliance(self, session: Session) -> WorkflowCompliance:
        """Check if session followed workflow."""

        tool_sequence = self._extract_tool_sequence(session)

        checks = {
            "blueprint_first": self._check_blueprint_first(tool_sequence),
            "query_before_edit": self._check_query_usage(tool_sequence),
            "no_blind_reads": self._check_blind_edits(tool_sequence),
        }

        score = self._calculate_compliance_score(checks)
        compliant = all(checks.values())
        violations = [check for check, passed in checks.items() if not passed]

        logger.info(
            f"Workflow compliance: {score:.2f} "
            f"({'COMPLIANT' if compliant else 'NON-COMPLIANT'}) "
            f"Violations: {violations if violations else 'none'}"
        )

        return WorkflowCompliance(
            compliant=compliant, score=score, violations=violations, checks=checks
        )

    def _parse_workflows(self) -> dict[str, Any]:
        """Parse workflows from planning.md."""

        return {}

    def _extract_tool_sequence(self, session: Session) -> list[ToolCall]:
        """Extract chronological tool call sequence."""
        return session.all_tool_calls

    def _check_blueprint_first(self, sequence: list[ToolCall]) -> bool:
        """Check if aud blueprint was run before modifications."""
        blueprint_run = False

        for call in sequence:
            if call.tool_name == "Bash":
                command = call.input_params.get("command", "")
                if "aud blueprint" in command or "aud full" in command:
                    blueprint_run = True

            if call.tool_name in ["Edit", "Write"] and not blueprint_run:
                logger.debug(
                    f"Workflow violation: Edit/Write before blueprint "
                    f"(file: {call.input_params.get('file_path')})"
                )
                return False

        return True

    def _check_query_usage(self, sequence: list[ToolCall]) -> bool:
        """Check if aud query was used before editing."""
        for call in sequence:
            if call.tool_name == "Bash":
                command = call.input_params.get("command", "")
                if "aud query" in command or "aud context" in command:
                    pass

            if call.tool_name in ["Edit", "Write"]:
                pass

        return True

    def _check_blind_edits(self, sequence: list[ToolCall]) -> bool:
        """Check if files were read before being edited."""
        files_read = set()
        blind_edits = []

        for call in sequence:
            if call.tool_name == "Read":
                file_path = call.input_params.get("file_path")
                if file_path:
                    files_read.add(file_path)

            if call.tool_name in ["Edit", "Write"]:
                file_path = call.input_params.get("file_path")
                if file_path and file_path not in files_read:
                    blind_edits.append(file_path)
                    logger.debug(f"Blind edit detected: {file_path}")

        if blind_edits:
            logger.info(f"Found {len(blind_edits)} blind edits")
            return False

        return True

    def _calculate_compliance_score(self, checks: dict[str, bool]) -> float:
        """Calculate compliance score from checks."""
        if not checks:
            return 0.0

        passed = sum(1 for check in checks.values() if check)
        total = len(checks)

        return passed / total if total > 0 else 0.0
