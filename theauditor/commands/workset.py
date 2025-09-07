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
    """Compute target file set from git diff and dependencies."""
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