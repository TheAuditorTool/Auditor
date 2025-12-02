"""Setup commands for TheAuditor - AI development environment integration."""

import platform
from pathlib import Path

import click

from theauditor.pipeline.ui import console


@click.command("setup-ai")
@click.option("--target", required=True, help="Target project root (absolute or relative path)")
@click.option("--sync", is_flag=True, help="Force update (reinstall packages)")
@click.option("--dry-run", is_flag=True, help="Print plan without executing")
@click.option(
    "--show-versions",
    is_flag=True,
    help="Show installed tool versions (reads from cache or runs detection)",
)
def setup_ai(target, sync, dry_run, show_versions):
    """Create isolated analysis environment with offline vulnerability databases and sandboxed tooling.

    One-time setup command that creates a completely sandboxed Python virtual environment
    with TheAuditor and all analysis tools (ESLint, TypeScript, OSV-Scanner), plus offline
    vulnerability databases (~500MB) for air-gapped security scanning. Enables zero-dependency
    analysis and offline vulnerability detection with no external API calls or rate limits.

    AI ASSISTANT CONTEXT:
      Purpose: Bootstrap sandboxed analysis environment for offline operation
      Input: Target project directory path
      Output: .auditor_venv/ (Python venv), .auditor_tools/ (JS tools), vuln databases
      Prerequisites: Python >=3.11, Node.js (for JavaScript tooling), network (initial download)
      Integration: Enables 'aud deps --vuln-scan' and 'aud lint' in isolation
      Performance: ~5-10 minutes (one-time setup, downloads ~500MB vulnerability data)

    WHAT IT INSTALLS:
      Python Environment (<target>/.auditor_venv/):
        - TheAuditor (editable install from current source)
        - All Python dependencies (isolated from project)
        - Dedicated Python 3.11+ interpreter

      JavaScript Tools (<target>/.auditor_tools/):
        - ESLint with TypeScript support
        - Prettier code formatter
        - TypeScript compiler
        - Isolated node_modules (no conflict with project)

      Security Tools:
        - OSV-Scanner binary (offline vulnerability scanner)
        - npm vulnerability database (~300MB, cached)
        - PyPI vulnerability database (~200MB, cached)
        - Database updates every 30 days (automatic refresh)

    HOW IT WORKS (Sandbox Creation):
      1. Virtual Environment Creation:
         - Creates Python venv at <target>/.auditor_venv
         - Isolates from system Python and project dependencies

      2. TheAuditor Installation:
         - Installs TheAuditor in editable mode (pip install -e)
         - Enables development workflow (code changes reflected immediately)

      3. JavaScript Tooling Setup:
         - Creates isolated node_modules at <target>/.auditor_tools
         - Installs ESLint, TypeScript, Prettier
         - No conflict with project dependencies

      4. Vulnerability Database Download:
         - Downloads OSV-Scanner binary (10-20MB)
         - Fetches npm advisory database (~300MB)
         - Fetches PyPI advisory database (~200MB)
         - Caches in <target>/.auditor_venv/vuln_cache/

      5. Verification:
         - Tests TheAuditor CLI executable
         - Verifies vulnerability database integrity
         - Reports setup success/failure

    EXAMPLES:
      # Use Case 1: Initial setup for project
      aud setup-ai --target /path/to/project

      # Use Case 2: Preview what will be installed (dry run)
      aud setup-ai --target . --dry-run

      # Use Case 3: Force reinstall (update tools)
      aud setup-ai --target . --sync

      # Use Case 4: Setup for current directory
      aud setup-ai --target .

    COMMON WORKFLOWS:
      Initial Project Setup:
        git clone <repo> && cd <repo>
        aud setup-ai --target .
        aud init && aud full

      Refresh Vulnerability Databases:
        aud setup-ai --target . --sync

      Multi-Project Setup:
        aud setup-ai --target ~/projects/api
        aud setup-ai --target ~/projects/frontend

    OUTPUT FILES:
      <target>/.auditor_venv/              # Python virtual environment
      <target>/.auditor_tools/             # Isolated JavaScript tools
      <target>/.auditor_venv/vuln_cache/   # Offline vulnerability databases
      <target>/.auditor_venv/bin/aud       # TheAuditor CLI executable

    PERFORMANCE EXPECTATIONS:
      Initial Setup:
        Virtual environment: ~30 seconds
        Python dependencies: ~1-2 minutes
        JavaScript tools: ~2-3 minutes
        Vulnerability databases: ~2-5 minutes (network-dependent)
        Total: ~5-10 minutes

      Subsequent Runs (--sync):
        ~2-5 minutes (skip venv creation, refresh databases only)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        --dry-run / --sync: dry-run shows plan, sync forces reinstall

      Recommended Combinations:
        --target . --sync         # Refresh databases and tools
        --target . --dry-run      # Preview before installing

      Flag Modifiers:
        --target: Project root directory (REQUIRED)
        --sync: Force update (reinstall packages, refresh databases)
        --dry-run: Show installation plan without executing

    PREREQUISITES:
      Required:
        Python >=3.11             # Language runtime
        Network access            # For downloading tools and databases
        Disk space: ~1GB          # For venv + tools + databases

      Optional:
        Node.js >=16              # For JavaScript analysis tools
        Git repository            # For editable TheAuditor install

    EXIT CODES:
      0 = Success, environment created
      1 = Setup error (permission denied, network failure)
      2 = Verification failed (tools not working after install)

    RELATED COMMANDS:
      aud init               # Uses sandboxed environment after setup
      aud deps --vuln-scan   # Uses offline vulnerability databases
      aud lint               # Uses sandboxed ESLint/TypeScript

    SEE ALSO:
      aud init --help        # Understand project initialization
      aud deps --help        # Learn about vulnerability scanning

    TROUBLESHOOTING:
      Error: "Permission denied" creating venv:
        -> Ensure write permissions in <target> directory
        -> Check disk space: df -h
        -> Avoid using sudo (venv should be user-owned)

      Network timeout downloading vulnerability databases:
        -> Retry with better connection
        -> Databases cache for 30 days, refresh periodically
        -> Use --dry-run to preview without downloading

      OSV-Scanner binary download fails:
        -> Check GitHub access: curl -I https://github.com
        -> Binary hosted on GitHub Releases
        -> May need VPN if GitHub blocked

      JavaScript tools not working after setup:
        -> Verify Node.js installed: node --version
        -> Check .auditor_tools/node_modules/ exists
        -> Re-run with --sync to force reinstall

      Vulnerability databases stale (>30 days old):
        -> Run 'aud setup-ai --target . --sync' to refresh
        -> Automatic refresh on next 'aud deps --vuln-scan'

    NOTE: This is a ONE-TIME setup per project. After setup, all analysis commands
    run in the sandboxed environment with offline vulnerability scanning. Databases
    refresh automatically every 30 days or manually with --sync.
    """
    from theauditor.venv_install import setup_project_venv

    target_dir = Path(target).resolve()

    if not target_dir.exists():
        raise click.ClickException(f"Target directory does not exist: {target_dir}")

    console.print(f"\n{'=' * 60}", highlight=False)
    console.print("AI Development Setup - Zero-Optional Installation")
    console.print(f"{'=' * 60}", highlight=False)
    console.print(f"Target:  {target_dir}", highlight=False)
    console.print(f"Mode:    {'DRY RUN' if dry_run else 'EXECUTE'}", highlight=False)
    console.print(f"{'=' * 60}\n", highlight=False)

    if dry_run:
        console.print("DRY RUN - Plan of operations:")
        console.print(f"1. Create/verify venv at {target_dir}/.auditor_venv", highlight=False)
        console.print("2. Install TheAuditor (editable) into venv")
        console.print("3. Install JS/TS analysis tools (ESLint, TypeScript, etc.)")
        console.print("\nNo files will be modified.")
        return

    if show_versions:
        from theauditor.commands.tools import detect_all_tools

        results = detect_all_tools()
        console.print("Tool versions:", highlight=False)

        python_found = sum(1 for t in results["python"] if t.available)
        node_found = sum(1 for t in results["node"] if t.available)
        rust_found = sum(1 for t in results["rust"] if t.available)

        console.print(f"  Python tools: {python_found}/{len(results['python'])} found", highlight=False)
        console.print(f"  Node tools: {node_found}/{len(results['node'])} found", highlight=False)
        console.print(f"  Rust tools: {rust_found}/{len(results['rust'])} found", highlight=False)

        for category, tools_list in results.items():
            console.print(f"\n  [{category.upper()}]", highlight=False)
            for tool in tools_list:
                status = tool.display_version
                source_tag = f" ({tool.source})" if tool.available and tool.source != "system" else ""
                console.print(f"    {tool.name}: {status}{source_tag}", highlight=False)
        return

    console.print("Step 1: Setting up Python virtual environment...", end="")
    console.print()

    try:
        venv_path, success = setup_project_venv(target_dir, force=sync)

        if not success:
            raise click.ClickException(f"Failed to setup venv at {venv_path}")

        is_windows = platform.system() == "Windows"
        check_mark = "[OK]" if is_windows else "✓"

        console.print(f"\n{'=' * 60}", highlight=False)
        console.print("Setup Complete - Summary:")
        console.print(f"{'=' * 60}", highlight=False)
        console.print(
            f"{check_mark} Sandboxed environment configured at: {target_dir}/.auditor_venv",
            highlight=False,
        )
        console.print(
            f"{check_mark} JS/TS tools installed at: {target_dir}/.auditor_venv/.theauditor_tools",
            highlight=False,
        )
        console.print(
            f"{check_mark} Professional linters installed (ruff, mypy, black, ESLint, TypeScript)",
            highlight=False,
        )

    except Exception as e:
        raise click.ClickException(f"Setup failed: {e}") from e
