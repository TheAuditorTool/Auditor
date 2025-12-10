"""Run linters and normalize output to evidence format."""

import json
from pathlib import Path
from typing import Any

import click

from theauditor.cli import RichCommand
from theauditor.linters import LinterOrchestrator
from theauditor.pipeline.ui import console, err_console
from theauditor.utils import load_json_file
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.logging import logger


def lint_command(
    root_path: str = ".",
    workset_path: str = "./.pf/workset.json",
    timeout: int = 300,
    print_plan: bool = False,
    auto_fix: bool = False,
) -> dict[str, Any]:
    """
    Run linters and normalize output.

    Returns:
        Dictionary with success status and statistics
    """

    workset_files = None
    if workset_path is not None:
        try:
            workset = load_json_file(workset_path)
            workset_files = [p["path"] for p in workset.get("paths", [])]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load workset: {e}, running on all files")
            workset_files = None

    if print_plan:
        console.print("Lint Plan:")
        console.print("  Mode: CHECK-ONLY")
        if workset_files:
            console.print(f"  Workset: {len(workset_files)} files", highlight=False)
        else:
            console.print("  Scope: All source files")
        console.print("  Linters: ESLint, Ruff, Mypy")
        console.print("  Output: findings_consolidated table")
        return {"success": True, "printed_plan": True}

    db_path = Path(root_path) / ".pf" / "repo_index.db"
    if not db_path.exists():
        return {"success": False, "error": f"Database not found: {db_path}. Run 'aud full' first."}

    try:
        orchestrator = LinterOrchestrator(root_path, str(db_path))
    except RuntimeError as e:
        return {"success": False, "error": str(e)}

    try:
        findings = orchestrator.run_all_linters(workset_files)
    except Exception as e:
        logger.error(f"Linter execution failed: {e}")
        return {"success": False, "error": f"Linter execution failed: {e}"}

    stats = {
        "total_findings": len(findings),
        "tools_run": 3,
        "workset_size": len(workset_files) if workset_files else 0,
        "errors": sum(1 for f in findings if f.get("severity") == "error"),
        "warnings": sum(1 for f in findings if f.get("severity") == "warning"),
    }

    console.print("\nLint complete:")
    console.print(f"  Total findings: {stats['total_findings']}", highlight=False)
    console.print(f"  Errors: {stats['errors']}", highlight=False)
    console.print(f"  Warnings: {stats['warnings']}", highlight=False)
    console.print("  Database: findings written to findings_consolidated table")

    return {
        "success": True,
        "stats": stats,
        "output_files": [],
        "auto_fix_applied": False,
    }


@click.command(cls=RichCommand)
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
@click.option(
    "--workset", is_flag=True, help="Use workset mode (lint only files in .pf/workset.json)"
)
@click.option("--workset-path", default=None, help="Custom workset path (rarely needed)")
@click.option("--timeout", default=None, type=int, help="Timeout in seconds for each linter")
@click.option("--print-plan", is_flag=True, help="Print lint plan without executing")
def lint(root, workset, workset_path, timeout, print_plan):
    """Run code quality checks with industry-standard linters and normalize output.

    Automatically detects and runs available linters in your project, normalizing
    all output into a unified format for analysis. Supports both full codebase
    and targeted workset analysis for efficient CI/CD integration.

    AI ASSISTANT CONTEXT:
      Purpose: Run static analysis linters and normalize findings to unified format
      Input: Source files (Python, JS/TS, Go, Docker), .pf/workset.json (optional)
      Output: findings_consolidated table (query with aud query --findings)
      Prerequisites: aud full (for workset mode), linters installed in project
      Integration: Part of full pipeline, works with workset for targeted analysis
      Performance: ~10-60 seconds depending on codebase size and linters installed

    SUPPORTED LINTERS (Auto-Detected):
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

    EXAMPLES:
      # Lint entire codebase
      aud lint

      # Lint only changed files (requires workset)
      aud workset --diff HEAD~1 && aud lint --workset

      # Preview what would run
      aud lint --print-plan

      # Increase timeout for large projects
      aud lint --timeout 600

    COMMON WORKFLOWS:
      After Changes:
        aud workset --diff HEAD~1 && aud lint --workset

      PR Review:
        aud workset --diff main && aud lint --workset

      CI Pipeline:
        aud lint || exit 1

    OUTPUT:
      findings_consolidated table     # Query with aud query --findings

    PERFORMANCE:
      Small (<1K files):     ~10-20 seconds
      Medium (5K files):     ~30-60 seconds
      Large (20K+ files):    ~2-5 minutes
      With --workset:        ~5-15 seconds (only changed files)

    EXIT CODES:
      0 = Success (findings don't fail the command)
      1 = Linter execution error or database missing

    RELATED COMMANDS:
      aud workset        # Create file list for targeted linting
      aud full           # Complete pipeline including lint
      aud detect-patterns # Pattern-based security analysis

    SEE ALSO:
      aud manual lint    # Deep dive into linting workflow
      aud manual workset # Understand workset targeting

    TROUBLESHOOTING:
      Error: "Database not found":
        -> Run 'aud full' first to create .pf/repo_index.db

      No linters found:
        -> Install linters: npm install eslint, pip install ruff

      Timeout during linting:
        -> Increase timeout: aud lint --timeout 600
        -> Use workset mode: aud lint --workset

      ESLint not running:
        -> Check node_modules exists
        -> Verify eslint is in PATH or node_modules/.bin

    NOTE: Install linters in your project for best results:
      npm install --save-dev eslint prettier
      pip install ruff mypy black pylint bandit

    Auto-fix is deprecated - use native linter fix commands instead:
      eslint --fix, ruff --fix, prettier --write, black ."""
    from theauditor.commands.config import LINT_TIMEOUT, WORKSET_PATH

    if timeout is None:
        timeout = LINT_TIMEOUT
    if workset_path is None and workset:
        workset_path = WORKSET_PATH

    actual_workset_path = workset_path if workset else None

    result = lint_command(
        root_path=root,
        workset_path=actual_workset_path,
        timeout=timeout,
        print_plan=print_plan,
        auto_fix=False,
    )

    if result.get("printed_plan"):
        return

    if not result["success"]:
        err_console.print(
            f"[error]Error: {result.get('error', 'Lint failed')}[/error]",
            highlight=False,
        )
        raise click.ClickException(result.get("error", "Lint failed"))
