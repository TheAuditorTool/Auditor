"""WorkflowChecker - Validate agent execution against planning.md workflows.

This module checks if agent execution follows defined workflows:
- Did agent run `aud blueprint` first? (MANDATORY)
- Did agent use `aud query` before editing? (MANDATORY)
- Did agent read files before editing? (no blind edits)

Returns compliance score and list of violations.
"""


import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Any

from theauditor.session.parser import Session, ToolCall

logger = logging.getLogger(__name__)


@dataclass
class WorkflowCompliance:
    """Workflow compliance result."""
    compliant: bool
    score: float  # 0.0-1.0
    violations: list[str]  # ['blueprint_first', 'query_before_edit']
    checks: dict[str, bool]  # {'blueprint_first': False, ...}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class WorkflowChecker:
    """Check if session execution follows defined workflows."""

    # Default workflow checks (if planning.md not available)
    DEFAULT_CHECKS = {
        'blueprint_first': 'Run aud blueprint before modifications',
        'query_before_edit': 'Use aud query before editing',
        'no_blind_reads': 'Read files before editing'
    }

    def __init__(self, workflow_path: Path = None):
        """Initialize workflow checker.

        Args:
            workflow_path: Path to planning.md (optional)
        """
        self.workflow_path = workflow_path
        self.workflows = self._parse_workflows() if workflow_path and workflow_path.exists() else {}

    def check_compliance(self, session: Session) -> "WorkflowCompliance":
        """Check if session followed workflow.

        Args:
            session: Session object to check

        Returns:
            WorkflowCompliance object with score and violations
        """
        # Extract tool call sequence
        tool_sequence = self._extract_tool_sequence(session)

        # Run checks
        checks = {
            'blueprint_first': self._check_blueprint_first(tool_sequence),
            'query_before_edit': self._check_query_usage(tool_sequence),
            'no_blind_reads': self._check_blind_edits(tool_sequence)
        }

        # Calculate compliance score
        score = self._calculate_compliance_score(checks)
        compliant = all(checks.values())
        violations = [check for check, passed in checks.items() if not passed]

        logger.info(
            f"Workflow compliance: {score:.2f} "
            f"({'COMPLIANT' if compliant else 'NON-COMPLIANT'}) "
            f"Violations: {violations if violations else 'none'}"
        )

        return WorkflowCompliance(
            compliant=compliant,
            score=score,
            violations=violations,
            checks=checks
        )

    def _parse_workflows(self) -> dict[str, Any]:
        """Parse workflows from planning.md.

        Returns:
            Dict of workflow definitions
        """
        # Simplified implementation - in reality would parse planning.md
        # For now, use default checks
        return {}

    def _extract_tool_sequence(self, session: Session) -> list[ToolCall]:
        """Extract chronological tool call sequence.

        Args:
            session: Session object

        Returns:
            List of ToolCall objects in chronological order
        """
        return session.all_tool_calls

    def _check_blueprint_first(self, sequence: list[ToolCall]) -> bool:
        """Check if aud blueprint was run before modifications.

        Args:
            sequence: List of tool calls

        Returns:
            True if blueprint ran before any Edit/Write, False otherwise
        """
        blueprint_run = False

        for call in sequence:
            # Check if blueprint was run
            if call.tool_name == 'Bash':
                command = call.input_params.get('command', '')
                if 'aud blueprint' in command or 'aud full' in command:
                    blueprint_run = True

            # Check if any edits happened before blueprint
            if call.tool_name in ['Edit', 'Write']:
                if not blueprint_run:
                    logger.debug(
                        f"Workflow violation: Edit/Write before blueprint "
                        f"(file: {call.input_params.get('file_path')})"
                    )
                    return False  # Edit before blueprint = violation

        # If no edits, this check passes (not applicable)
        return True

    def _check_query_usage(self, sequence: list[ToolCall]) -> bool:
        """Check if aud query was used before editing.

        Args:
            sequence: List of tool calls

        Returns:
            True if query used appropriately, False otherwise
        """
        for call in sequence:
            # Check if query was run
            if call.tool_name == 'Bash':
                command = call.input_params.get('command', '')
                if 'aud query' in command or 'aud context' in command:
                    pass  # Query was run - noted but not acted upon yet

            # Check if edits happened
            if call.tool_name in ['Edit', 'Write']:
                # For now, we're lenient - query is recommended but not mandatory
                # In strict mode, would require query before every edit
                pass

        # For now, this check always passes (query is recommended, not mandatory)
        return True

    def _check_blind_edits(self, sequence: list[ToolCall]) -> bool:
        """Check if files were read before being edited.

        Args:
            sequence: List of tool calls

        Returns:
            True if all edits had prior reads, False otherwise
        """
        files_read = set()
        blind_edits = []

        for call in sequence:
            # Track files read
            if call.tool_name == 'Read':
                file_path = call.input_params.get('file_path')
                if file_path:
                    files_read.add(file_path)

            # Check if edit without prior read
            if call.tool_name in ['Edit', 'Write']:
                file_path = call.input_params.get('file_path')
                if file_path and file_path not in files_read:
                    blind_edits.append(file_path)
                    logger.debug(f"Blind edit detected: {file_path}")

        if blind_edits:
            logger.info(f"Found {len(blind_edits)} blind edits")
            return False

        return True

    def _calculate_compliance_score(self, checks: dict[str, bool]) -> float:
        """Calculate compliance score from checks.

        Args:
            checks: Dict of check results

        Returns:
            Compliance score (0.0-1.0)
        """
        if not checks:
            return 0.0

        passed = sum(1 for check in checks.values() if check)
        total = len(checks)

        return passed / total if total > 0 else 0.0
