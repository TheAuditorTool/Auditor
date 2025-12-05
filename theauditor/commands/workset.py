"""Compute target file set from git diff and dependencies."""

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console
from theauditor.utils.error_handler import handle_exceptions


@click.command(cls=RichCommand)
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
@click.option("--db", default=None, help="Input SQLite database path")
@click.option("--all", is_flag=True, help="Include all source files (ignores common directories)")
@click.option("--diff", help="Git diff range (e.g., main..HEAD)")
@click.option("--files", multiple=True, help="Explicit file list")
@click.option("--include", multiple=True, help="Include glob patterns")
@click.option("--exclude", multiple=True, help="Exclude glob patterns")
@click.option("--max-depth", default=10, type=int, help="Maximum dependency depth")
@click.option("--out", default=None, help="Output workset file path")
@click.option("--print-stats", is_flag=True, help="Print summary statistics")
def workset(root, db, all, diff, files, include, exclude, max_depth, out, print_stats):
    """Compute targeted file subset for incremental analysis based on git changes or patterns.

    Performance optimization tool that creates a focused subset of files for analysis instead
    of re-analyzing your entire codebase. Integrates with git diff to automatically identify
    changed files, then expands to include dependent files that could be affected by those
    changes using the import graph from repo_index.db.

    This enables 10-100x faster analysis for PR reviews, commit validations, and iterative
    development workflows. The workset is saved to .pf/workset.json and consumed by other
    commands via the --workset flag.

    AI ASSISTANT CONTEXT:
      Purpose: Creates focused file subset for targeted analysis (incremental workflows)
      Input: Git diff / file patterns + .pf/repo_index.db (import graph)
      Output: .pf/workset.json (seed files + expanded dependencies)
      Prerequisites: aud full (for dependency expansion), git repository (for --diff)
      Integration: Output consumed by aud lint --workset for targeted analysis
      Performance: ~1-3 seconds (git diff + graph query), analysis 10-100x faster

    WHAT IT COMPUTES:
      Seed Files (Direct Selection):
        - Git diff results (--diff main..HEAD)
        - Explicit file lists (--files auth.py db.py)
        - Glob pattern matches (--include "src/*/api.py")
        - All source files if --all specified

      Dependency Expansion (Transitive):
        - Direct importers (files that import seed files)
        - Transitive importers (files that import importers, up to --max-depth)
        - Callers of functions defined in seed files
        - Classes that inherit from seed file classes

      Filtering (Post-Expansion):
        - Exclude patterns (--exclude "test/*" to skip tests)
        - Respect .gitignore (automatically applied)
        - Language filters (only Python/JS/TS source files)

    HOW IT WORKS (Workset Algorithm):
      1. Seed File Discovery:
         - Git diff: Run `git diff --name-only <range>` for changed files
         - Explicit: Use --files list directly
         - Glob: Expand --include patterns to matching files
         - All: Query database for all indexed files

      2. Dependency Expansion (Graph Traversal):
         - Query refs table for files importing seed files
         - Recursively expand importers up to --max-depth hops
         - Query calls table for functions invoked by seed files
         - Include class inheritance dependencies

      3. Filtering and Deduplication:
         - Apply --exclude patterns (regex matching)
         - Remove duplicates (seed + expanded may overlap)
         - Filter out non-source files (configs, docs, etc.)

      4. Output Generation:
         - Write JSON with seed_files, expanded_files, total_files
         - Print statistics if --print-stats enabled
         - Save to .pf/workset.json (default) or --out path

    EXAMPLES:
      # Use Case 1: Analyze files changed in last commit
      aud workset --diff HEAD~1 && aud lint --workset

      # Use Case 2: PR review workflow (feature branch vs main)
      aud workset --diff main..feature && aud lint --workset

      # Use Case 3: Analyze specific files and their dependencies
      aud workset --files auth.py api.py --max-depth 2

      # Use Case 4: Pattern-based analysis (all API endpoints)
      aud workset --include "*/api/*" && aud lint --workset

      # Use Case 5: Targeted lint on all source files
      aud workset --all && aud lint --workset

    COMMON WORKFLOWS:
      Pre-Commit Hook (Fast Validation):
        aud workset --diff HEAD && aud lint --workset

      CI/CD PR Checks (Changed Files Only):
        aud full --index && aud workset --diff origin/main..HEAD && aud lint --workset

      Iterative Development (After Code Changes):
        aud workset --diff HEAD~3 && aud lint --workset

    OUTPUT FILES:
      .pf/workset.json               # Workset file consumed by --workset flag
      .pf/repo_index.db (tables read):
        - refs: Import graph for dependency expansion
        - calls: Function call graph
        - symbols: Function/class definitions

    OUTPUT FORMAT (workset.json Schema):
      {
        "seed_files": [
          "src/auth.py",
          "src/api.py"
        ],
        "expanded_files": [
          "src/main.py",
          "tests/test_auth.py"
        ],
        "total_files": 4,
        "expansion_depth": 2,
        "generated_at": "2025-11-01T12:00:00Z"
      }

    PERFORMANCE EXPECTATIONS:
      Workset Generation:
        Small (<10 changed files):    ~0.5-1 seconds
        Medium (50 changed files):    ~1-2 seconds
        Large (200+ changed files):   ~3-5 seconds

      Analysis Speedup (with --workset vs full):
        PR with 5 files:    100x faster (0.5s vs 50s)
        PR with 50 files:   10x faster (5s vs 50s)
        All files (--all):  No speedup (equivalent to full)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        --diff / --files / --all      # Choose ONE seed source
        (Can combine --include/--exclude with any seed source)

      Recommended Combinations:
        --diff main..HEAD --exclude "test/*"        # PR without tests
        --files api.py --max-depth 1 --print-stats  # Single file + direct deps

      Flag Modifiers:
        --diff: Uses git diff for seed files (requires git repository)
        --all: Ignores git, uses all indexed files (no dependency expansion)
        --max-depth: Limits dependency expansion (default: 3 hops)
        --exclude: Filters out files from final workset (post-expansion)

    PREREQUISITES:
      Required:
        aud full               # Populates refs table for dependency expansion

      Optional:
        Git repository         # For --diff flag (not needed for --files/--all)
        .pf/repo_index.db      # For --all flag (queries files table)

    EXIT CODES:
      0 = Success, workset created
      1 = Git diff failed (invalid range or not a git repository)
      2 = No files matched criteria (empty workset)

    RELATED COMMANDS:
      aud full               # Must run first to populate import graph
      aud lint --workset     # Use workset for targeted lint analysis

    SEE ALSO:
      aud explain workset    # Deep dive into workset algorithm
      aud explain fce        # Understand dependency graph analysis

    TROUBLESHOOTING:
      Error: "Git diff failed" or "Not a git repository":
        -> Use --files or --all instead of --diff for non-git projects
        -> Verify git is installed: git --version
        -> Run from repository root (where .git/ exists)

      Workset too large (includes too many files):
        -> Reduce --max-depth (default 3, try 1 or 2)
        -> Add --exclude patterns to filter out test/vendor files
        -> Use --diff with smaller commit range

      Workset empty (no files matched):
        -> Check git diff output: git diff --name-only <range>
        -> Verify files exist in database (run 'aud full --index')
        -> Check --include/--exclude patterns are correct

      Missing dependencies (analysis incomplete):
        -> Increase --max-depth to capture transitive dependencies
        -> Verify 'aud full' ran successfully (check .pf/repo_index.db)
        -> Use --print-stats to see seed vs expanded file counts

    NOTE: Workset is purely a performance optimization - it does NOT change analysis
    behavior, only which files are analyzed. For maximum confidence, run full analysis
    periodically even if using workset for daily development.
    """
    from theauditor.commands.config import DB_PATH, WORKSET_PATH
    from theauditor.workset import compute_workset

    if db is None:
        db = DB_PATH
    if out is None:
        out = WORKSET_PATH

    result = compute_workset(
        root_path=root,
        db_path=db,
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
        console.print(f"Workset written to {out}", highlight=False)
        console.print(f"  Seed files: {result['seed_count']}", highlight=False)
        console.print(f"  Expanded files: {result['expanded_count']}", highlight=False)
