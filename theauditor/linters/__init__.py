"""Linters package - REFACTORED: Single-file orchestration.

DEPRECATED modules (renamed to .bak, kept for reference):
- detector.py.bak (272 lines) - Replaced by LinterOrchestrator database queries
- runner.py.bak (387 lines) - Replaced by LinterOrchestrator._run_* methods
- parsers.py.bak (504 lines) - Replaced by LinterOrchestrator JSON parsing

NEW architecture (single file):
- linters.py (400 lines) - Complete linter orchestration

Config files (kept for setup):
- package.json - Copied to .auditor_venv/.theauditor_tools/ during setup
- eslint.config.cjs - Copied to .auditor_venv/.theauditor_tools/ during setup
- pyproject.toml - Copied to .auditor_venv/.theauditor_tools/ during setup
"""
from __future__ import annotations


# Import from the new single-file module in this directory
from .linters import LinterOrchestrator

__all__ = [
    "LinterOrchestrator",
]

# Backward compatibility warning for old imports
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