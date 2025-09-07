"""Linters package - detection, execution, and parsing of linter outputs."""

# Re-export main functions for convenience
from .detector import detect_linters, check_package_json_has_eslint
from .runner import run_linter
from .parsers import (
    parse_eslint_output,
    parse_ruff_output,
    parse_mypy_output,
    parse_tsc_output,
    parse_prettier_output,
    parse_black_output,
    parse_golangci_output,
    parse_go_vet_output,
    parse_maven_output,
    parse_bandit_output,
)

__all__ = [
    # Detection
    "detect_linters",
    "check_package_json_has_eslint",
    # Execution
    "run_linter",
    # Parsing
    "parse_eslint_output",
    "parse_ruff_output",
    "parse_mypy_output",
    "parse_tsc_output",
    "parse_prettier_output",
    "parse_black_output",
    "parse_golangci_output",
    "parse_go_vet_output",
    "parse_maven_output",
    "parse_bandit_output",
]