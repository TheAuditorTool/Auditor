"""Initialize TheAuditor for first-time use."""

from pathlib import Path
import click


@click.command()
@click.option("--offline", is_flag=True, help="Skip network operations (deps check, docs fetch)")
@click.option("--skip-docs", is_flag=True, help="Skip documentation fetching")
@click.option("--skip-deps", is_flag=True, help="Skip dependency checking")
def init(offline, skip_docs, skip_deps):
    """Initialize TheAuditor project structure and perform first-time setup.

    THE entry point command for new projects - creates the complete .pf/ directory
    infrastructure, runs initial indexing, and prepares your codebase for analysis.
    This is the first command you should run when setting up TheAuditor in any project.

    Orchestrates a 4-step initialization pipeline: (1) index repository to build symbol
    database, (2) create workset of all source files, (3) check dependencies for outdated
    packages, (4) fetch API documentation for external libraries. The entire process is
    idempotent - safe to run multiple times without data loss.

    AI ASSISTANT CONTEXT:
      Purpose: First-time project setup and .pf/ infrastructure creation
      Input: Source code files in current directory
      Output: .pf/ directory with repo_index.db, manifest.json, workset.json
      Prerequisites: None (this is the first command to run)
      Integration: Prerequisite for ALL analysis commands (creates database)
      Performance: ~10-30 seconds (scales with codebase size + network speed)

    WHAT IT CREATES:
      Directory Structure (.pf/):
        raw/                    # Immutable tool outputs (JSON/NDJSON)
        readthis/               # AI-optimized analysis chunks (<65KB each)
        .ast_cache/             # Cached AST trees (70% speedup on re-index)
        repo_index.db           # SQLite database with symbols/imports
        graphs.db               # Pre-computed graph structures (optional)
        manifest.json           # File inventory with metadata
        workset.json            # Target file list for analysis
        pipeline.log            # Execution trace and errors

      Database Tables (repo_index.db):
        files, symbols, refs, calls, assignments, patterns, frameworks
        (Full schema contract enforced - see schema.py)

    OPERATIONS PERFORMED:
      Step 1: Index Repository (aud index)
        - Parses all Python/JavaScript/TypeScript files
        - Extracts functions, classes, imports, calls
        - Creates repo_index.db SQLite database
        - Caches AST trees in .ast_cache/
        - Duration: ~5-20 seconds (scales with file count)

      Step 2: Create Workset (aud workset --all)
        - Identifies all source files from manifest.json
        - Creates workset.json with complete file list
        - Used by --workset flag on other commands
        - Duration: ~0.5-1 seconds

      Step 3: Check Dependencies (aud deps) [Optional]
        - Inventories Python (requirements.txt, pyproject.toml)
        - Inventories JavaScript (package.json, yarn.lock)
        - Checks for outdated packages (online check)
        - Skipped with --skip-deps or --offline
        - Duration: ~2-5 seconds (with network)

      Step 4: Fetch Documentation (aud docs) [Optional]
        - Downloads API documentation for external libraries
        - Caches in .pf/raw/docs/ for offline use
        - Creates AI-consumable documentation capsules
        - Skipped with --skip-docs or --offline
        - Duration: ~5-15 seconds (with network)

    EXAMPLES:
      # Use Case 1: First-time setup (full initialization with network)
      cd /path/to/project && aud init

      # Use Case 2: Offline initialization (no network operations)
      aud init --offline

      # Use Case 3: Fast setup (skip slow network operations)
      aud init --skip-docs --skip-deps

      # Use Case 4: Re-initialization after manual .pf/ deletion
      rm -rf .pf && aud init

      # Use Case 5: CI/CD initialization (offline, fast)
      aud init --offline && aud full --fail-on-findings

    COMMON WORKFLOWS:
      New Project Setup (Developer Workstation):
        git clone <repo> && cd <repo> && aud init && aud full

      CI/CD Pipeline (Fresh Build):
        aud init --offline && aud taint-analyze --fail-fast

      After Git Pull (Incremental Update):
        git pull && aud index && aud workset --diff origin/main..HEAD

    OUTPUT FILES:
      .pf/repo_index.db              # SQLite database (50-200MB)
      .pf/manifest.json              # File inventory (1-5MB)
      .pf/workset.json               # All source files list (~100KB)
      .pf/.ast_cache/                # Cached AST trees (10-50MB)
      .pf/pipeline.log               # Initialization log (debug info)
      .pf/raw/deps.json              # Dependency inventory (if not skipped)
      .pf/raw/docs/                  # API documentation (if not skipped)

    OUTPUT FORMAT (Directory Verification):
      After successful init, .pf/ contains:
      - repo_index.db (SQLite, must exist)
      - manifest.json (JSON, must have "files" array)
      - workset.json (JSON, must have "total_files" > 0)
      - pipeline.log (text, contains timestamp and step results)

    PERFORMANCE EXPECTATIONS:
      Small (<100 files):       ~5-10 seconds
      Medium (500 files):       ~15-30 seconds
      Large (2000+ files):      ~60-120 seconds
      Note: Add +5-15s if network operations enabled (deps + docs)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        None (all flags can be combined)

      Recommended Combinations:
        --offline               # Fastest (no network, skip deps + docs)
        --skip-docs             # Skip docs but check deps (faster)

      Flag Modifiers:
        --offline: Implies --skip-docs AND --skip-deps (no network at all)
        --skip-docs: Skips documentation fetch only (deps still checked)
        --skip-deps: Skips dependency check only (docs still fetched)

    PREREQUISITES:
      Required:
        Python >=3.11              # Language runtime
        Disk space: ~3x codebase size  # For database + cache + archives

      Optional:
        Git repository             # For .gitignore pattern respect
        Network access             # For --deps and --docs (unless skipped)
        package.json / requirements.txt  # For dependency checking

    EXIT CODES:
      0 = Success, all steps completed
      1 = Partial failure (some steps failed but .pf/ created)
      2 = Complete failure (indexing failed, no database created)

    RELATED COMMANDS:
      aud index              # Re-index after code changes
      aud full               # Run all analysis commands
      aud workset            # Update workset for targeted analysis
      aud deps               # Re-check dependencies for updates

    SEE ALSO:
      aud explain workset    # Understand workset concept
      aud explain fce        # Learn about database-driven analysis

    TROUBLESHOOTING:
      Error: "Permission denied" creating .pf/:
        -> Run from repository root with write permissions
        -> Check if .pf/ is owned by different user (chown to fix)

      Initialization hangs during deps/docs step:
        -> Network timeout (use --offline to skip network operations)
        -> Check network connectivity: curl -I https://pypi.org
        -> Use --skip-docs and --skip-deps to bypass

      Out of disk space error:
        -> TheAuditor needs ~3x codebase size for database + cache
        -> Free up disk space or use external drive
        -> Check df -h to see available space

      Indexing fails with syntax errors:
        -> Some files may have syntax errors (check .pf/pipeline.log)
        -> Init continues gracefully, fix syntax and re-run 'aud index'

      .pf/ already exists, safe to re-run?:
        -> YES - Init is idempotent, archives previous data automatically
        -> Previous index archived to .pf/history/full/TIMESTAMP/
        -> Safe to run multiple times for fresh start

    NOTE: Init is idempotent and safe to run multiple times. It will archive previous
    data before creating new infrastructure. For incremental updates after code changes,
    use 'aud index' instead of full 'aud init' for better performance.
    """
    from theauditor.init import initialize_project
    
    click.echo("[INIT] Initializing TheAuditor...\n")
    click.echo("This will run all setup steps:")
    click.echo("  1. Index repository")
    click.echo("  2. Create workset")
    click.echo("  3. Check dependencies")
    click.echo("  4. Fetch documentation")
    click.echo("\n" + "="*60 + "\n")
    
    # Call the refactored initialization logic with progress callback
    result = initialize_project(
        offline=offline,
        skip_docs=skip_docs,
        skip_deps=skip_deps,
        progress_callback=click.echo
    )
    
    stats = result["stats"]
    has_failures = result["has_failures"]
    next_steps = result["next_steps"]
    
    # Results have already been displayed via progress callback
    
    # Summary
    click.echo("\n" + "="*60)
    
    if has_failures:
        click.echo("\n[WARN]  Initialization Partially Complete\n")
    else:
        click.echo("\n[SUCCESS] Initialization Complete!\n")
    
    # Show summary
    click.echo("[STATS] Summary:")
    if stats.get("index", {}).get("success"):
        click.echo(f"  * Indexed: {stats['index']['text_files']} files")
    else:
        click.echo("  * Indexing: [FAILED] Failed")
    
    if stats.get("workset", {}).get("success"):
        click.echo(f"  * Workset: {stats['workset']['files']} files")
    elif stats.get("workset", {}).get("files") == 0:
        click.echo("  * Workset: [WARN]  No files found")
    else:
        click.echo("  * Workset: [FAILED] Failed")
    
    if stats.get("deps", {}).get("success"):
        click.echo(f"  * Dependencies: {stats['deps'].get('total', 0)} total, {stats['deps'].get('outdated', 0)} outdated")
    elif stats.get("deps", {}).get("skipped"):
        click.echo("  * Dependencies: [SKIPPED]  Skipped")
    
    if stats.get("docs", {}).get("success"):
        fetched = stats['docs'].get('fetched', 0)
        cached = stats['docs'].get('cached', 0)
        capsules = stats['docs'].get('capsules', 0)
        if cached > 0:
            click.echo(f"  * Documentation: {fetched} fetched, {cached} cached, {capsules} capsules")
        else:
            click.echo(f"  * Documentation: {fetched} fetched, {capsules} capsules")
    elif stats.get("docs", {}).get("skipped"):
        click.echo("  * Documentation: [SKIPPED]  Skipped")
    
    # Next steps - only show if we have files to work with
    if next_steps:
        click.echo("\n[TARGET] Next steps:")
        for i, step in enumerate(next_steps, 1):
            click.echo(f"  {i}. Run: {step}")
        click.echo("\nOr run all at once:")
        click.echo(f"  {' && '.join(next_steps)}")
    else:
        click.echo("\n[WARN]  No files found to audit. Check that you're in the right directory.")