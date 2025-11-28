"""Linters package - REFACTORED: Single-file orchestration."""

from .linters import LinterOrchestrator

__all__ = [
    "LinterOrchestrator",
]


def __getattr__(name):
    """Provide helpful error messages for deprecated imports."""
    deprecated_names = {
        "detect_linters": "Use LinterOrchestrator instead",
        "run_linter": "Use LinterOrchestrator.run_all_linters() instead",
        "parse_eslint_output": "Internal to LinterOrchestrator",
        "parse_ruff_output": "Internal to LinterOrchestrator",
        "parse_mypy_output": "Internal to LinterOrchestrator",
    }

    if name in deprecated_names:
        raise ImportError(
            f"'{name}' is deprecated. {deprecated_names[name]}.\n"
            f"The linters package has been refactored to use LinterOrchestrator."
        )

    raise AttributeError(f"module 'theauditor.linters' has no attribute '{name}'")
