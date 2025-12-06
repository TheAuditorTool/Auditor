"""Setup commands for TheAuditor - AI development environment integration."""

from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console


@click.command("setup-ai", cls=RichCommand)
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
        aud full

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
      aud full               # Uses sandboxed environment after setup
      aud deps --vuln-scan   # Uses offline vulnerability databases
      aud lint               # Uses sandboxed ESLint/TypeScript

    SEE ALSO:
      aud manual setup       # Deep dive into sandboxed environment concepts
      aud manual tools       # Understand tool detection and management

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

    mode_style = "yellow" if dry_run else "green"
    mode_text = "DRY RUN" if dry_run else "EXECUTE"

    header_content = Text()
    header_content.append("Target:  ", style="dim")
    header_content.append(str(target_dir), style="cyan")
    header_content.append("\nMode:    ", style="dim")
    header_content.append(mode_text, style=f"bold {mode_style}")

    console.print()
    console.print(
        Panel(
            header_content,
            title="[bold blue]TheAuditor[/bold blue] [dim]AI Development Setup[/dim]",
            subtitle="[dim]Zero-Optional Installation[/dim]",
            border_style="blue",
            padding=(1, 2),
        )
    )

    if dry_run:
        plan_table = Table(show_header=False, box=None, padding=(0, 2))
        plan_table.add_column("Step", style="cyan", width=4)
        plan_table.add_column("Action", style="white")

        plan_table.add_row("1.", f"Create/verify venv at [cyan]{target_dir}/.auditor_venv[/cyan]")
        plan_table.add_row("2.", "Install TheAuditor [dim](editable)[/dim] into venv")
        plan_table.add_row(
            "3.", "Install JS/TS analysis tools [dim](ESLint, TypeScript, etc.)[/dim]"
        )

        console.print()
        console.print(
            Panel(
                plan_table,
                title="[bold yellow]DRY RUN[/bold yellow] [dim]Plan of Operations[/dim]",
                subtitle="[dim]No files will be modified[/dim]",
                border_style="yellow",
                padding=(1, 1),
            )
        )
        return

    if show_versions:
        from theauditor.commands.tools import detect_all_tools

        results = detect_all_tools()

        python_found = sum(1 for t in results["python"] if t.available)
        node_found = sum(1 for t in results["node"] if t.available)
        rust_found = sum(1 for t in results["rust"] if t.available)

        summary = Text()
        summary.append("Python: ", style="dim")
        summary.append(
            f"{python_found}/{len(results['python'])}", style="green" if python_found else "red"
        )
        summary.append("  Node: ", style="dim")
        summary.append(
            f"{node_found}/{len(results['node'])}", style="green" if node_found else "red"
        )
        summary.append("  Rust: ", style="dim")
        summary.append(
            f"{rust_found}/{len(results['rust'])}", style="green" if rust_found else "red"
        )

        console.print()
        console.print(Panel(summary, title="[bold]Tool Versions[/bold]", border_style="blue"))

        for category, tools_list in results.items():
            tools_table = Table(show_header=False, box=None, padding=(0, 2))
            tools_table.add_column("Tool", style="white", width=20)
            tools_table.add_column("Version", style="cyan")
            tools_table.add_column("Source", style="dim")

            for tool in tools_list:
                status_style = "green" if tool.available else "red"
                status = tool.display_version
                source_tag = tool.source if tool.available and tool.source != "system" else ""
                tools_table.add_row(
                    tool.name, f"[{status_style}]{status}[/{status_style}]", source_tag
                )

            console.print(
                Panel(tools_table, title=f"[bold]{category.upper()}[/bold]", border_style="dim")
            )
        return

    console.print()
    console.print("[bold cyan]Step 1:[/bold cyan] Setting up Python virtual environment...")
    console.print()

    try:
        venv_path, success = setup_project_venv(target_dir, force=sync)

        if not success:
            raise click.ClickException(f"Failed to setup venv at {venv_path}")

        summary_table = Table(show_header=False, box=None, padding=(0, 2))
        summary_table.add_column("Status", style="green")
        summary_table.add_column("Item", style="white")

        summary_table.add_row(
            "[bold green]OK[/bold green]",
            f"Sandboxed environment: [cyan]{target_dir}/.auditor_venv[/cyan]",
        )
        summary_table.add_row(
            "[bold green]OK[/bold green]",
            f"JS/TS tools: [cyan]{target_dir}/.auditor_venv/.theauditor_tools[/cyan]",
        )
        summary_table.add_row(
            "[bold green]OK[/bold green]",
            "Professional linters: [dim]ruff, mypy, black, ESLint, TypeScript[/dim]",
        )

        console.print()
        console.print(
            Panel(
                summary_table,
                title="[bold green]Setup Complete[/bold green]",
                border_style="green",
                padding=(1, 1),
            )
        )

    except Exception as e:
        raise click.ClickException(f"Setup failed: {e}") from e
