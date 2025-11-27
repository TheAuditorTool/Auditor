"""Setup commands for TheAuditor - AI development environment integration."""

import platform
from pathlib import Path

import click


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

    click.echo(f"\n{'=' * 60}")
    click.echo(f"AI Development Setup - Zero-Optional Installation")
    click.echo(f"{'=' * 60}")
    click.echo(f"Target:  {target_dir}")
    click.echo(f"Mode:    {'DRY RUN' if dry_run else 'EXECUTE'}")
    click.echo(f"{'=' * 60}\n")

    if dry_run:
        click.echo("DRY RUN - Plan of operations:")
        click.echo(f"1. Create/verify venv at {target_dir}/.auditor_venv")
        click.echo(f"2. Install TheAuditor (editable) into venv")
        click.echo(f"3. Install JS/TS analysis tools (ESLint, TypeScript, etc.)")
        click.echo("\nNo files will be modified.")
        return

    if show_versions:
        from theauditor.tools import write_tools_report

        out_dir = target_dir / ".pf" / "raw"
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            res = write_tools_report(str(out_dir))
            click.echo(f"Tool versions (from {out_dir}):")
            python_found = sum(1 for v in res["python"].values() if v != "missing")
            node_found = sum(1 for v in res["node"].values() if v != "missing")
            click.echo(f"  Python tools: {python_found}/4 found")
            click.echo(f"  Node tools: {node_found}/3 found")
            for tool, version in res["python"].items():
                click.echo(f"    {tool}: {version}")
            for tool, version in res["node"].items():
                click.echo(f"    {tool}: {version}")
        except Exception as e:
            click.echo(f"Error detecting tool versions: {e}", err=True)
        return

    click.echo("Step 1: Setting up Python virtual environment...", nl=False)
    click.echo()

    try:
        venv_path, success = setup_project_venv(target_dir, force=sync)

        if not success:
            raise click.ClickException(f"Failed to setup venv at {venv_path}")

        is_windows = platform.system() == "Windows"
        check_mark = "[OK]" if is_windows else "✓"

        click.echo(f"\n{'=' * 60}")
        click.echo("Setup Complete - Summary:")
        click.echo(f"{'=' * 60}")
        click.echo(f"{check_mark} Sandboxed environment configured at: {target_dir}/.auditor_venv")
        click.echo(
            f"{check_mark} JS/TS tools installed at: {target_dir}/.auditor_venv/.theauditor_tools"
        )
        click.echo(
            f"{check_mark} Professional linters installed (ruff, mypy, black, ESLint, TypeScript)"
        )

    except Exception as e:
        raise click.ClickException(f"Setup failed: {e}") from e
