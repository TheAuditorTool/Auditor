"""Run linters and normalize output to evidence format."""

import json
from pathlib import Path
from typing import Any

import click

from theauditor.linters import LinterOrchestrator
from theauditor.utils import load_json_file
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


def lint_command(
    root_path: str = ".",
    workset_path: str = "./.pf/workset.json",
    manifest_path: str = "manifest.json",
    timeout: int = 300,
    print_plan: bool = False,
    auto_fix: bool = False,
) -> dict[str, Any]:
    """
    Run linters and normalize output.

    Returns:
        Dictionary with success status and statistics
    """
    # AUTO-FIX DEPRECATED: Force disabled to prevent version mismatch issues
    auto_fix = False

    # Load workset files if in workset mode
    workset_files = None
    if workset_path is not None:
        try:
            workset = load_json_file(workset_path)
            workset_files = [p["path"] for p in workset.get("paths", [])]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load workset: {e}, running on all files")
            workset_files = None

    if print_plan:
        print("Lint Plan:")
        print(f"  Mode: CHECK-ONLY")
        if workset_files:
            print(f"  Workset: {len(workset_files)} files")
        else:
            print(f"  Scope: All source files")
        print("  Linters: ESLint, Ruff, Mypy")
        print("  Output: .pf/raw/lint.json + findings_consolidated table")
        return {"success": True, "printed_plan": True}

    # Initialize orchestrator
    db_path = Path(root_path) / ".pf" / "repo_index.db"
    if not db_path.exists():
        return {
            "success": False,
            "error": f"Database not found: {db_path}. Run 'aud index' first."
        }

    try:
        orchestrator = LinterOrchestrator(root_path, str(db_path))
    except RuntimeError as e:
        return {"success": False, "error": str(e)}

    # Run all linters
    try:
        findings = orchestrator.run_all_linters(workset_files)
    except Exception as e:
        logger.error(f"Linter execution failed: {e}")
        return {"success": False, "error": f"Linter execution failed: {e}"}

    # Statistics
    stats = {
        "total_findings": len(findings),
        "tools_run": 3,  # ESLint, Ruff, Mypy
        "workset_size": len(workset_files) if workset_files else 0,
        "errors": sum(1 for f in findings if f.get("severity") == "error"),
        "warnings": sum(1 for f in findings if f.get("severity") == "warning"),
    }

    print("\nLint complete:")
    print(f"  Total findings: {stats['total_findings']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Warnings: {stats['warnings']}")
    print(f"  Output: .pf/raw/lint.json")
    print(f"  Database: findings written to findings_consolidated table")

    return {
        "success": True,
        "stats": stats,
        "output_files": [str(Path(root_path) / ".pf" / "raw" / "lint.json")],
        "auto_fix_applied": False,
    }


@click.command()
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
@click.option("--workset", is_flag=True, help="Use workset mode (lint only files in .pf/workset.json)")
@click.option("--workset-path", default=None, help="Custom workset path (rarely needed)")
@click.option("--manifest", default=None, help="Manifest file path")
@click.option("--timeout", default=None, type=int, help="Timeout in seconds for each linter")
@click.option("--print-plan", is_flag=True, help="Print lint plan without executing")
def lint(root, workset, workset_path, manifest, timeout, print_plan):
    """Run code quality checks with industry-standard linters.

    Automatically detects and runs available linters in your project,
    normalizing all output into a unified format for analysis. Supports
    both full codebase and targeted workset analysis.

    Supported Linters (Auto-Detected):
      Python:
        - ruff       # Fast, comprehensive Python linter
        - mypy       # Static type checker
        - black      # Code formatter (check mode)
        - pylint     # Classic Python linter
        - bandit     # Security-focused linter

      JavaScript/TypeScript:
        - eslint     # Pluggable JS/TS linter
        - prettier   # Code formatter (check mode)
        - tsc        # TypeScript compiler (type checking)

      Go:
        - golangci-lint  # Meta-linter for Go
        - go vet         # Go static analyzer

      Docker:
        - hadolint   # Dockerfile linter

    Examples:
      aud lint                        # Lint entire codebase
      aud lint --workset              # Lint only changed files
      aud lint --print-plan           # Preview what would run
      aud lint --timeout 600          # Increase timeout for large projects

    Common Workflows:
      After changes:  aud workset --diff HEAD~1 && aud lint --workset
      PR review:      aud workset --diff main && aud lint --workset
      CI pipeline:    aud lint || exit 1

    Output:
      .pf/raw/lint.json               # Normalized findings
      .pf/raw/ast_cache/eslint/*.json # Cached ASTs from ESLint

    Finding Format:
      {
        "file": "src/auth.py",
        "line": 42,
        "column": 10,
        "severity": "error",      # error | warning | info
        "rule": "undefined-var",
        "message": "Variable 'user' is not defined",
        "tool": "eslint"
      }

    Exit Behavior:
      - Always exits with code 0 (findings don't fail the command)
      - Check stats['errors'] in output to determine CI/CD failure

    Note: Install linters in your project for best results:
      npm install --save-dev eslint prettier
      pip install ruff mypy black pylint bandit

    Auto-fix is deprecated - use native linter fix commands instead:
      eslint --fix, ruff --fix, prettier --write, black ."""
    from theauditor.config_runtime import load_runtime_config
    
    # Load configuration
    config = load_runtime_config(root)
    
    # Use config defaults if not provided
    if manifest is None:
        manifest = config["paths"]["manifest"]
    if timeout is None:
        timeout = config["timeouts"]["lint_timeout"]
    if workset_path is None and workset:
        workset_path = config["paths"]["workset"]

    # Use workset path only if --workset flag is set
    actual_workset_path = workset_path if workset else None
    
    result = lint_command(
        root_path=root,
        workset_path=actual_workset_path,
        manifest_path=manifest,
        timeout=timeout,
        print_plan=print_plan,
        auto_fix=False,  # Auto-fix permanently disabled
    )

    if result.get("printed_plan"):
        return

    if not result["success"]:
        click.echo(f"Error: {result.get('error', 'Lint failed')}", err=True)
        raise click.ClickException(result.get("error", "Lint failed"))