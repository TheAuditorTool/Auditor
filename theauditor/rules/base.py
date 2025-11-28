"""Base contracts for rule standardization."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


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
    """Universal immutable context for all standardized rules."""

    file_path: Path
    content: str
    language: str
    project_path: Path

    ast_wrapper: dict[str, Any] | None = None

    db_path: str | None = None
    taint_checker: Callable | None = None
    module_resolver: Any | None = None

    file_hash: str | None = None
    file_size: int | None = None
    line_count: int | None = None

    extra: dict[str, Any] = field(default_factory=dict)

    def get_ast(self, expected_type: str = None) -> Any | None:
        """Safely extract AST with optional type checking."""
        if not self.ast_wrapper:
            return None

        ast_type = self.ast_wrapper.get("type")

        if expected_type and ast_type != expected_type:
            logger.debug(f"AST type mismatch: wanted {expected_type}, got {ast_type}")
            return None

        return self.ast_wrapper.get("tree")

    def get_lines(self) -> list[str]:
        """Get file content as list of lines."""
        return self.content.splitlines() if self.content else []

    def get_snippet(self, line_num: int, context_lines: int = 2) -> str:
        """Extract code snippet around a line number."""
        lines = self.get_lines()
        if not lines or line_num < 1 or line_num > len(lines):
            return ""

        start = max(1, line_num - context_lines)
        end = min(len(lines), line_num + context_lines)

        snippet_lines = []
        for i in range(start, end + 1):
            prefix = ">> " if i == line_num else "   "
            snippet_lines.append(f"{i:4d}{prefix}{lines[i - 1]}")

        return "\n".join(snippet_lines)


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


RuleFunction = Callable[[StandardRuleContext], list[StandardFinding]]


def validate_rule_signature(func: Callable) -> bool:
    """Check if a function follows the standard rule signature."""
    import inspect

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    return len(params) == 1 and params[0] == "context"


@dataclass
class RuleMetadata:
    """Metadata describing rule requirements for smart orchestrator filtering."""

    name: str
    category: str

    target_extensions: list[str] | None = None
    exclude_patterns: list[str] | None = None
    target_file_patterns: list[str] | None = None

    execution_scope: Literal["database", "file"] | None = None

    requires_jsx_pass: bool = False
    jsx_pass_mode: str = "preserved"


def convert_old_context(old_context, project_path: Path = None) -> StandardRuleContext:
    """Convert old RuleContext to StandardRuleContext."""
    from pathlib import Path

    return StandardRuleContext(
        file_path=Path(old_context.file_path) if old_context.file_path else Path("unknown"),
        content=old_context.content or "",
        language=old_context.language or "unknown",
        project_path=Path(old_context.project_path) if old_context.project_path else Path("."),
        ast_wrapper=old_context.ast_tree if hasattr(old_context, "ast_tree") else None,
        db_path=old_context.db_path if hasattr(old_context, "db_path") else None,
    )
