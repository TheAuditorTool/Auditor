"""Linters package - Async parallel linter orchestration.

This package provides:
- LinterOrchestrator: Main entry point for running linters
- Finding: Typed dataclass for lint results
- BaseLinter: ABC for implementing new linters
- Individual linter classes for each supported tool
"""

from .base import BaseLinter, Finding
from .clippy import ClippyLinter
from .eslint import EslintLinter
from .golangci import GolangciLinter
from .linters import LinterOrchestrator
from .mypy import MypyLinter
from .ruff import RuffLinter
from .shellcheck import ShellcheckLinter

__all__ = [
    "BaseLinter",
    "ClippyLinter",
    "EslintLinter",
    "Finding",
    "GolangciLinter",
    "LinterOrchestrator",
    "MypyLinter",
    "RuffLinter",
    "ShellcheckLinter",
]
