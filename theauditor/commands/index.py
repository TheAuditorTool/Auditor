"""Build language-agnostic manifest and SQLite index of repository."""

import click
from theauditor.utils.error_handler import handle_exceptions
from theauditor.utils.helpers import get_self_exclusion_patterns


@click.command()
@handle_exceptions
@click.option("--root", default=".", help="Root directory to index")
@click.option("--manifest", default=None, help="Output manifest file path")
@click.option("--db", default=None, help="Output SQLite database path")
@click.option("--print-stats", is_flag=True, help="Print summary statistics")
@click.option("--dry-run", is_flag=True, help="Scan but don't write files")
@click.option("--follow-symlinks", is_flag=True, help="Follow symbolic links (default: skip)")
@click.option("--exclude-self", is_flag=True, help="Exclude TheAuditor's own files (for self-testing)")
def index(root, manifest, db, print_stats, dry_run, follow_symlinks, exclude_self):
    """Build comprehensive code inventory and symbol database.

    Creates a complete inventory of your codebase including all functions,
    classes, imports, and their relationships. This is the foundation for
    all other analysis commands - you MUST run index first.

    The index contains:
      - Every function, class, method, and variable
      - Import relationships and dependencies
      - File metadata (size, language, lines of code)
      - AST cache for performance optimization

    Examples:
      aud index                           # Index current directory
      aud index --exclude-self            # Exclude TheAuditor's own files
      aud index --print-stats             # Show detailed statistics
      aud index --dry-run --print-stats  # Preview what would be indexed

    Output Files:
      .pf/repo_index.db    # SQLite database with all symbols
      .pf/manifest.json    # File inventory with metadata
      .pf/.ast_cache/      # Cached AST trees for performance

    Database Tables:
      files       - All source files with metadata
      symbols     - Functions, classes, variables
      imports     - Import statements and dependencies
      patterns    - Detected security patterns

    Note: Most commands require index to be run first. The database
    is used by taint-analyze, graph, impact, and many other commands."""
    from theauditor.indexer import build_index
    from theauditor.config_runtime import load_runtime_config
    
    # Load configuration
    config = load_runtime_config(root)
    
    # Use config defaults if not provided
    if manifest is None:
        manifest = config["paths"]["manifest"]
    if db is None:
        db = config["paths"]["db"]

    # Build exclude patterns using centralized function
    exclude_patterns = get_self_exclusion_patterns(exclude_self)
    
    if exclude_self and print_stats:
        click.echo(f"[EXCLUDE-SELF] Excluding TheAuditor's own files from indexing")
        click.echo(f"[EXCLUDE-SELF] {len(exclude_patterns)} patterns will be excluded")

    result = build_index(
        root_path=root,
        manifest_path=manifest,
        db_path=db,
        print_stats=print_stats,
        dry_run=dry_run,
        follow_symlinks=follow_symlinks,
        exclude_patterns=exclude_patterns,
    )

    if result.get("error"):
        click.echo(f"Error: {result['error']}", err=True)
        raise click.ClickException(result["error"])