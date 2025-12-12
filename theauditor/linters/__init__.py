"""Linters package - Async parallel linter orchestration.

This package provides:
- LinterOrchestrator: Main entry point for running linters
- Finding: Typed dataclass for lint results
- BaseLinter: ABC for implementing new linters
- ConfigGenerator: Intelligent linter config generation
- Individual linter classes for each supported tool
"""

from .base import BaseLinter, Finding
from .clippy import ClippyLinter
from .config_generator import ConfigGenerator, ConfigResult
from .eslint import EslintLinter
from .golangci import GolangciLinter
from .linters import LinterOrchestrator
from .mypy import MypyLinter
from .ruff import RuffLinter
from .shellcheck import ShellcheckLinter

__all__ = [
    "BaseLinter",
    "ClippyLinter",
    "ConfigGenerator",
    "ConfigResult",
    "EslintLinter",
    "Finding",
    "GolangciLinter",
    "LinterOrchestrator",
    "MypyLinter",
    "RuffLinter",
    "ShellcheckLinter",
]
