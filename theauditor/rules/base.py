"""Base contracts for rule standardization."""

__all__ = [
    "Severity",
    "Confidence",
    "StandardRuleContext",
    "StandardFinding",
    "RuleFunction",
    "RuleMetadata",
    "validate_rule_signature",
    "convert_old_context",
    "RuleResult",
]

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from theauditor.rules.fidelity import RuleResult


class Severity(Enum):
    """Standardized severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(Enum):
    """Confidence in finding accuracy."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class StandardRuleContext:
    """Universal context for all standardized rules."""

    file_path: Path
    content: str
    language: str
    project_path: Path

    ast_wrapper: dict[str, Any] | None = None
    db_path: str | None = None
    taint_checker: Callable | None = None

    extra: dict[str, Any] = field(default_factory=dict)

    def get_ast(self, expected_type: str = None) -> Any | None:
        """Extract AST with optional type checking."""
        if not self.ast_wrapper:
            return None

        ast_type = self.ast_wrapper.get("type")
        if expected_type and ast_type != expected_type:
            return None

        return self.ast_wrapper.get("tree")

    def get_lines(self) -> list[str]:
        """Get file content as list of lines."""
        return self.content.splitlines() if self.content else []


@dataclass
class StandardFinding:
    """Standardized output from all rules."""

    rule_name: str
    message: str
    file_path: str
    line: int

    column: int = 0
    severity: Severity | str = Severity.MEDIUM
    category: str = "security"
    confidence: Confidence | str = Confidence.HIGH
    snippet: str = ""

    references: list[str] | None = None
    cwe_id: str | None = None
    additional_info: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "rule": self.rule_name,
            "message": self.message,
            "file": self.file_path,
            "line": self.line,
            "column": self.column,
            "severity": self.severity.value
            if isinstance(self.severity, Severity)
            else self.severity,
            "category": self.category,
            "confidence": self.confidence.value
            if isinstance(self.confidence, Confidence)
            else self.confidence,
            "code_snippet": self.snippet,
        }

        if self.references:
            result["references"] = self.references
        if self.cwe_id:
            result["cwe"] = self.cwe_id
        if self.additional_info:
            import json

            result["details_json"] = json.dumps(self.additional_info)

        return result


RuleFunction = Callable[[StandardRuleContext], list[StandardFinding] | RuleResult]


def validate_rule_signature(func: Callable) -> bool:
    """Check if a function follows the standard rule signature."""
    import inspect

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    return len(params) == 1 and params[0] == "context"


@dataclass
class RuleMetadata:
    """Metadata for orchestrator filtering."""

    name: str
    category: str

    target_extensions: list[str] | None = None
    exclude_patterns: list[str] | None = None
    target_file_patterns: list[str] | None = None

    execution_scope: Literal["database", "file"] | None = None

    primary_table: str | None = None


def convert_old_context(old_context, project_path: Path = None) -> StandardRuleContext:
    """Convert old RuleContext to StandardRuleContext."""
    return StandardRuleContext(
        file_path=Path(old_context.file_path) if old_context.file_path else Path("unknown"),
        content=old_context.content or "",
        language=old_context.language or "unknown",
        project_path=Path(old_context.project_path) if old_context.project_path else Path("."),
        ast_wrapper=old_context.ast_tree if hasattr(old_context, "ast_tree") else None,
        db_path=old_context.db_path if hasattr(old_context, "db_path") else None,
    )
