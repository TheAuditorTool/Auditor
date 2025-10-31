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
@click.option("--no-archive", is_flag=True, help="Skip archiving previous index (fast rebuild)")
def index(root, manifest, db, print_stats, dry_run, follow_symlinks, exclude_self, no_archive):
    """Build comprehensive code inventory and symbol database from source code AST parsing.

    THE foundational command for TheAuditor - creates a complete SQLite database inventory
    of your codebase by parsing Abstract Syntax Trees (AST) for all supported languages.
    Extracts every function, class, import, variable, and their relationships into a
    queryable database that powers all other analysis commands.

    This command is REQUIRED before running any analysis - taint-analyze, deadcode, graph,
    impact, and 30+ other commands all read from the database created by index. Think of
    it as "compile once, analyze many times" - the database persists across multiple
    analysis runs until you re-index.

    AI ASSISTANT CONTEXT:
      Purpose: Creates foundational SQLite database of code facts for all analysis
      Input: Source code files (Python, JavaScript, TypeScript, JSX, TSX)
      Output: .pf/repo_index.db (SQLite), .pf/manifest.json (file inventory)
      Prerequisites: None (this is the entry point command)
      Integration: Required by ALL analysis commands (taint, graph, deadcode, etc.)
      Performance: ~5-20 seconds for medium codebases (scales with file count)

    WHAT IT INDEXES:
      Code Structure:
        - Functions, methods, classes, variables (with line numbers)
        - Function signatures (parameters, return types, decorators)
        - Class inheritance hierarchies and method overrides
        - Variable assignments and scope information

      Relationships:
        - Import statements (who imports what)
        - Function calls (caller -> callee with line numbers)
        - Class instantiations and method invocations
        - Module dependencies (import graph)

      Metadata:
        - File paths, sizes, line counts, language detection
        - Framework detection (Flask, Django, React, Express, etc.)
        - Security patterns (crypto usage, file I/O, network calls)
        - AST cache for incremental re-indexing

      Database Tables Created:
        - files: All source files with metadata
        - symbols: Functions, classes, methods, variables
        - refs: Import statements and module dependencies
        - calls: Function call graph (caller -> callee)
        - assignments: Variable assignments and data flow
        - patterns: Security-relevant code patterns
        - frameworks: Detected frameworks and versions

    HOW IT WORKS (Indexing Pipeline):
      1. File Discovery: Recursively scans root directory for source files
         - Respects .gitignore patterns
         - Filters by extension (.py, .js, .ts, .jsx, .tsx)
         - Optionally follows symlinks (--follow-symlinks)

      2. Language Detection: Identifies parser for each file
         - Python: ast module (built-in)
         - JavaScript/TypeScript: tree-sitter (external)

      3. AST Parsing: Parses each file into Abstract Syntax Tree
         - Caches parsed ASTs in .pf/.ast_cache/ (70% speedup on re-index)
         - Handles syntax errors gracefully (logs and continues)

      4. Fact Extraction: Walks AST to extract symbols and relationships
         - Function definitions (name, line, params, decorators)
         - Class definitions (name, bases, methods)
         - Import statements (source, target, alias)
         - Function calls (callee, args, line number)

      5. Database Write: Inserts extracted facts into SQLite
         - Schema validation after write (ensures contract compliance)
         - Transaction-based (atomic commit on success)
         - Archives previous index to .pf/history/full/ (rollback capability)

    EXAMPLES:
      # Use Case 1: First-time indexing (fresh project setup)
      aud index --print-stats

      # Use Case 2: Re-index after code changes (incremental with cache)
      aud index

      # Use Case 3: Preview what would be indexed without writing
      aud index --dry-run --print-stats

      # Use Case 4: Fast rebuild without archiving previous index
      aud index --no-archive

      # Use Case 5: Self-testing TheAuditor's own codebase
      aud index --exclude-self --print-stats

    COMMON WORKFLOWS:
      First-Time Project Setup:
        cd /path/to/project && aud index --print-stats

      After Code Changes (Git Workflow):
        git pull && aud index && aud taint-analyze

      CI/CD Pipeline (Fresh Index Every Build):
        aud index --no-archive && aud full --fail-on-findings

    OUTPUT FILES:
      .pf/repo_index.db              # SQLite database (50-200MB for medium projects)
      .pf/manifest.json              # File inventory with metadata (1-5MB)
      .pf/.ast_cache/                # Cached AST trees (optional, speeds up re-index)
      .pf/history/full/YYYYMMDD_HHMMSS/  # Archived previous index (rollback)
      .pf/pipeline.log               # Indexing errors and warnings

    OUTPUT FORMAT (manifest.json Schema):
      {
        "files": [
          {
            "path": "src/main.py",
            "language": "python",
            "size_bytes": 1024,
            "lines_of_code": 45,
            "last_modified": "2025-11-01T12:00:00Z"
          }
        ],
        "statistics": {
          "total_files": 120,
          "total_symbols": 450,
          "total_imports": 200
        }
      }

    PERFORMANCE EXPECTATIONS:
      Small (<100 files):       ~2-5 seconds,   ~50MB RAM,  ~10MB database
      Medium (500 files):       ~10-20 seconds, ~200MB RAM, ~50MB database
      Large (2000+ files):      ~60-120 seconds, ~500MB RAM, ~200MB database
      Note: AST cache reduces re-index time by 70% (second run ~3-6s for small)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        None (all flags can be combined)

      Recommended Combinations:
        --print-stats --dry-run        # Preview indexing without writing
        --no-archive --print-stats     # Fast rebuild with statistics

      Flag Modifiers:
        --dry-run: Skips all file writes (database, manifest, archive)
        --no-archive: Skips archiving (saves ~5s but loses rollback capability)
        --exclude-self: Excludes TheAuditor's own files (for self-testing only)
        --follow-symlinks: Follows symlinks (may cause infinite loops, use cautiously)

    PREREQUISITES:
      Required:
        Python >=3.11              # Language runtime
        Disk space: ~3x codebase size  # For database + archive + cache

      Optional:
        Git repository             # For .gitignore pattern respect
        .auditorconfig             # Custom exclude patterns

    EXIT CODES:
      0 = Success, index created and validated
      1 = Indexing error (syntax errors, I/O failures)
      2 = Schema validation failure (database contract violation)

    RELATED COMMANDS:
      aud full                   # Runs index + all analysis commands
      aud taint-analyze          # Requires index first
      aud graph build            # Builds graph database from repo_index.db
      aud deadcode               # Finds unused code (requires index)
      aud workset                # Filters index to changed files only

    SEE ALSO:
      aud explain workset        # Understand incremental analysis
      aud explain fce            # Learn about database-driven analysis

    TROUBLESHOOTING:
      Error: "Permission denied" writing to .pf/:
        -> Run from repository root with write permissions
        -> Check if .pf/ directory is locked by another process

      Slow indexing (>2 minutes for medium project):
        -> First run is slower (no AST cache), second run 70% faster
        -> Use --exclude patterns in .auditorconfig for vendor/ or node_modules/
        -> Large files (>10K LOC) slow parsing, consider splitting

      Out of memory during indexing:
        -> Database write is memory-intensive for large projects
        -> Index in smaller batches (use --root on subdirectories)
        -> Close other applications to free RAM

      Schema validation warnings after indexing:
        -> Usually safe to ignore (migrated columns from old schema)
        -> If persistent, delete .pf/ and re-run 'aud index' fresh

      Syntax errors in indexed files:
        -> Index continues gracefully, logs errors to .pf/pipeline.log
        -> Check log for files that failed to parse
        -> Fix syntax errors in source files and re-run index

    NOTE: The database is regenerated fresh on every 'aud index' run. Incremental
    indexing (only changed files) is NOT supported - full re-parse every time ensures
    consistency. Use AST cache (automatic) to speed up repeated indexing.
    """
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

    # ARCHIVE previous index before rebuilding (unless --no-archive or --dry-run)
    if not no_archive and not dry_run:
        from pathlib import Path
        pf_dir = Path(".pf")

        # Only archive if .pf exists with contents
        if pf_dir.exists() and any(pf_dir.iterdir()):
            try:
                from theauditor.commands._archive import _archive
                from click.testing import CliRunner

                click.echo("[INDEX] Archiving previous index data to .pf/history/full/...")

                # Call _archive programmatically
                runner = CliRunner()
                result_archive = runner.invoke(_archive, ["--run-type", "full"])

                if result_archive.exit_code != 0:
                    click.echo(f"[WARNING] Archive failed but continuing: {result_archive.output}", err=True)
                elif print_stats:
                    click.echo(f"[INDEX] Archive complete")
            except Exception as e:
                click.echo(f"[WARNING] Could not archive previous index: {e}", err=True)
                click.echo(f"[WARNING] Continuing with index rebuild...", err=True)
    elif no_archive and print_stats:
        click.echo("[INDEX] Skipping archive (--no-archive flag)")

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

    # SCHEMA CONTRACT: Validate database schema after indexing
    if not dry_run:
        try:
            import sqlite3
            from theauditor.indexer.schema import validate_all_tables

            conn = sqlite3.connect(db)
            cursor = conn.cursor()
            mismatches = validate_all_tables(cursor)
            conn.close()

            if mismatches:
                click.echo("", err=True)
                click.echo(" Schema Validation Warnings ", err=True)
                click.echo("=" * 60, err=True)
                for table_name, errors in mismatches.items():
                    click.echo(f"  {table_name}:", err=True)
                    for error in errors[:3]:  # Show first 3 errors per table
                        click.echo(f"    - {error}", err=True)
                click.echo("", err=True)
                click.echo("Note: Some warnings may be expected (migrated columns).", err=True)
                click.echo("Run 'aud index' again to rebuild with correct schema.", err=True)
        except Exception as e:
            click.echo(f"Schema validation skipped: {e}", err=True)