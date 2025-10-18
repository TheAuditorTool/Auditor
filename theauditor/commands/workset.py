"""Compute target file set from git diff and dependencies."""

import click
from theauditor.utils.error_handler import handle_exceptions


@click.command()
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
@click.option("--db", default=None, help="Input SQLite database path")
@click.option("--manifest", default=None, help="Input manifest file path")
@click.option("--all", is_flag=True, help="Include all source files (ignores common directories)")
@click.option("--diff", help="Git diff range (e.g., main..HEAD)")
@click.option("--files", multiple=True, help="Explicit file list")
@click.option("--include", multiple=True, help="Include glob patterns")
@click.option("--exclude", multiple=True, help="Exclude glob patterns")
@click.option("--max-depth", default=None, type=int, help="Maximum dependency depth")
@click.option("--out", default=None, help="Output workset file path")
@click.option("--print-stats", is_flag=True, help="Print summary statistics")
def workset(root, db, manifest, all, diff, files, include, exclude, max_depth, out, print_stats):
    """Identify files to analyze based on changes or patterns.

    A workset is a focused subset of files for targeted analysis. Instead
    of analyzing your entire codebase every time, workset identifies only
    the files that matter for your current task. It automatically includes
    dependent files that could be affected by changes.

    Use Cases:
      - After making changes: Analyze only modified files and their deps
      - Pull request review: Focus on files changed in the PR
      - Targeted security scan: Check specific components
      - Performance optimization: Reduce analysis time by 10-100x

    Examples:
      aud workset --diff HEAD~1          # Files changed in last commit
      aud workset --diff main..feature   # Files changed in feature branch
      aud workset --all                  # All source files (skip git diff)
      aud workset --files auth.py db.py  # Specific files + dependencies
      aud workset --include "*/auth/*"   # Files matching pattern

    Then use with other commands:
      aud workset --diff HEAD~3 && aud lint --workset
      aud workset --diff main && aud taint-analyze --workset
      aud workset --files api.py && aud impact --workset

    Output:
      .pf/workset.json    # List of files to analyze

    Contains:
      - seed_files: Directly changed/selected files
      - expanded_files: Dependencies and affected files
      - total_files: Complete set for analysis

    Note: Most analysis commands support --workset flag to use this file."""
    from theauditor.workset import compute_workset
    from theauditor.config_runtime import load_runtime_config
    
    # Load configuration
    config = load_runtime_config(root)
    
    # Use config defaults if not provided
    if db is None:
        db = config["paths"]["db"]
    if manifest is None:
        manifest = config["paths"]["manifest"]
    if out is None:
        out = config["paths"]["workset"]
    if max_depth is None:
        max_depth = config["limits"]["max_graph_depth"]

    result = compute_workset(
        root_path=root,
        db_path=db,
        manifest_path=manifest,
        all_files=all,
        diff_spec=diff,
        file_list=list(files) if files else None,
        include_patterns=list(include) if include else None,
        exclude_patterns=list(exclude) if exclude else None,
        max_depth=max_depth,
        output_path=out,
        print_stats=print_stats,
    )

    if not print_stats:
        click.echo(f"Workset written to {out}")
        click.echo(f"  Seed files: {result['seed_count']}")
        click.echo(f"  Expanded files: {result['expanded_count']}")