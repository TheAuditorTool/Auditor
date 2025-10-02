"""Base contracts for rule standardization.

This module defines the universal interface that ALL rules must follow.
Created as part of the Great Refactor to eliminate signature chaos.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union
from pathlib import Path
from enum import Enum
import logging

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
    """Universal immutable context for all standardized rules.
    
    Design Principles:
    1. Contains everything a rule might need
    2. Immutable during execution
    3. Extensible via 'extra' without breaking changes
    4. Helpers for common operations
    
    Migration Note:
    Old rules received various parameters (tree, file_path, **kwargs).
    This unified context replaces ALL of those parameters.
    """
    
    # Required fields (must be provided)
    file_path: Path
    content: str
    language: str  # 'python', 'javascript', 'typescript', etc.
    project_path: Path
    
    # Optional AST data
    ast_wrapper: Optional[Dict[str, Any]] = None
    # Expected structure:
    # {
    #   "type": "python_ast" | "tree_sitter" | "semantic_ast",
    #   "tree": <actual AST object>,
    #   "parser_version": "1.0.0"
    # }
    
    # Analysis tools (lazy-loaded)
    db_path: Optional[str] = None
    taint_checker: Optional[Callable] = None
    module_resolver: Optional[Any] = None
    
    # File metadata
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    line_count: Optional[int] = None
    
    # Extensibility
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def get_ast(self, expected_type: str = None) -> Optional[Any]:
        """Safely extract AST with optional type checking.
        
        Args:
            expected_type: If provided, only return AST if type matches
            
        Returns:
            The AST tree object or None if not available/wrong type
            
        Example:
            tree = context.get_ast("python_ast")
            if tree:
                # Work with Python AST
        """
        if not self.ast_wrapper:
            return None
        
        ast_type = self.ast_wrapper.get("type")
        
        # Type checking if requested
        if expected_type and ast_type != expected_type:
            logger.debug(f"AST type mismatch: wanted {expected_type}, got {ast_type}")
            return None
        
        return self.ast_wrapper.get("tree")
    
    def get_lines(self) -> List[str]:
        """Get file content as list of lines."""
        return self.content.splitlines() if self.content else []
    
    def get_snippet(self, line_num: int, context_lines: int = 2) -> str:
        """Extract code snippet around a line number.
        
        Args:
            line_num: 1-based line number
            context_lines: Lines before/after to include
            
        Returns:
            Code snippet with line numbers
        """
        lines = self.get_lines()
        if not lines or line_num < 1 or line_num > len(lines):
            return ""
        
        start = max(1, line_num - context_lines)
        end = min(len(lines), line_num + context_lines)
        
        snippet_lines = []
        for i in range(start, end + 1):
            prefix = ">> " if i == line_num else "   "
            snippet_lines.append(f"{i:4d}{prefix}{lines[i-1]}")
        
        return "\n".join(snippet_lines)


@dataclass
class StandardFinding:
    """Standardized output from all rules.
    
    This replaces the various dict formats that rules previously returned.
    """
    
    # Required fields
    rule_name: str
    message: str
    file_path: str
    line: int
    
    # Optional with defaults
    column: int = 0
    severity: Union[Severity, str] = Severity.MEDIUM
    category: str = "security"
    confidence: Union[Confidence, str] = Confidence.HIGH
    snippet: str = ""
    
    # Additional context
    references: Optional[List[str]] = None
    cwe_id: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Field mappings aligned with findings_consolidated schema:
        - rule_name → rule
        - file_path → file
        - snippet → code_snippet
        - cwe_id → cwe
        """
        result = {
            "rule": self.rule_name,  # Schema expects 'rule'
            "message": self.message,
            "file": self.file_path,  # Schema expects 'file'
            "line": self.line,
            "column": self.column,
            "severity": self.severity.value if isinstance(self.severity, Severity) else self.severity,
            "category": self.category,
            "confidence": self.confidence.value if isinstance(self.confidence, Confidence) else self.confidence,
            "code_snippet": self.snippet,  # Schema expects 'code_snippet'
        }

        # Only include optional fields if set
        if self.references:
            result["references"] = self.references
        if self.cwe_id:
            result["cwe"] = self.cwe_id  # Schema expects 'cwe'
        if self.additional_info:
            result["additional_info"] = self.additional_info

        return result


# Type alias for rule functions
RuleFunction = Callable[[StandardRuleContext], List[StandardFinding]]


def validate_rule_signature(func: Callable) -> bool:
    """Check if a function follows the standard rule signature.
    
    Args:
        func: Function to validate
        
    Returns:
        True if signature matches standard, False otherwise
    """
    import inspect
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    # Must have exactly one parameter named 'context'
    return len(params) == 1 and params[0] == 'context'


@dataclass
class RuleMetadata:
    """Metadata describing rule requirements for smart orchestrator filtering.

    Added in Phase 3B to enable intelligent file targeting and skip irrelevant files.

    Usage in rules:
        METADATA = RuleMetadata(
            name="sql_injection",
            category="sql",
            target_extensions=['.py', '.js'],
            exclude_patterns=['migrations/'],
            requires_jsx_pass=False
        )
    """
    # Required fields
    name: str  # Rule identifier (snake_case)
    category: str  # sql, xss, auth, secrets, etc.

    # File targeting (orchestrator uses these for filtering)
    target_extensions: Optional[List[str]] = None  # ['.py', '.js'] - ONLY these files
    exclude_patterns: Optional[List[str]] = None  # ['migrations/', 'test/'] - SKIP these
    target_file_patterns: Optional[List[str]] = None  # ['backend/', 'server/'] - INCLUDE these

    # JSX-specific settings
    requires_jsx_pass: bool = False  # True = query *_jsx tables instead of standard tables
    jsx_pass_mode: str = 'preserved'  # 'preserved' or 'transformed' (only if requires_jsx_pass=True)


def convert_old_context(old_context, project_path: Path = None) -> StandardRuleContext:
    """Convert old RuleContext to StandardRuleContext.

    Helper for dual-mode orchestrator during migration.
    """
    from pathlib import Path
    
    return StandardRuleContext(
        file_path=Path(old_context.file_path) if old_context.file_path else Path("unknown"),
        content=old_context.content or "",
        language=old_context.language or "unknown",
        project_path=Path(old_context.project_path) if old_context.project_path else Path("."),
        ast_wrapper=old_context.ast_tree if hasattr(old_context, 'ast_tree') else None,
        db_path=old_context.db_path if hasattr(old_context, 'db_path') else None,
    )