"""Setup commands for TheAuditor - AI development environment integration."""

import platform
from pathlib import Path

import click


@click.command("setup-ai")
@click.option(
    "--target",
    required=True,
    help="Target project root (absolute or relative path)"
)
@click.option(
    "--sync",
    is_flag=True,
    help="Force update (reinstall packages)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print plan without executing"
)
def setup_ai(target, sync, dry_run):
    """Setup sandboxed analysis tools and vulnerability databases.

    This command creates a complete sandboxed environment for TheAuditor:

    1. Creates a Python venv at <target>/.auditor_venv
    2. Installs TheAuditor into that venv (editable)
    3. Sets up isolated JS/TS tools (ESLint, TypeScript)
    4. Downloads OSV-Scanner binary for vulnerability detection
    5. Downloads offline vulnerability databases (npm, PyPI)

    Initial Setup:
      - Downloads 100-500MB of vulnerability databases
      - Takes 5-10 minutes (one-time setup)
      - Enables offline vulnerability scanning with no rate limits

    Benefits:
      - JS/TS analysis isolated from project dependencies
      - Offline vulnerability scanning (no OSV.dev API calls)
      - Cross-referenced findings from 3 sources (npm audit, pip-audit, OSV-Scanner)

    After setup, run: aud deps --vuln-scan
    """
    from theauditor.venv_install import setup_project_venv

    # Resolve target path
    target_dir = Path(target).resolve()

    if not target_dir.exists():
        raise click.ClickException(f"Target directory does not exist: {target_dir}")

    # Print header
    click.echo(f"\n{'='*60}")
    click.echo(f"AI Development Setup - Zero-Optional Installation")
    click.echo(f"{'='*60}")
    click.echo(f"Target:  {target_dir}")
    click.echo(f"Mode:    {'DRY RUN' if dry_run else 'EXECUTE'}")
    click.echo(f"{'='*60}\n")

    # Handle dry run
    if dry_run:
        click.echo("DRY RUN - Plan of operations:")
        click.echo(f"1. Create/verify venv at {target_dir}/.auditor_venv")
        click.echo(f"2. Install TheAuditor (editable) into venv")
        click.echo(f"3. Install JS/TS analysis tools (ESLint, TypeScript, etc.)")
        click.echo("\nNo files will be modified.")
        return

    # Setup venv
    click.echo("Step 1: Setting up Python virtual environment...", nl=False)
    click.echo()  # Flush

    try:
        venv_path, success = setup_project_venv(target_dir, force=sync)

        if not success:
            raise click.ClickException(f"Failed to setup venv at {venv_path}")

        # Print summary
        is_windows = platform.system() == "Windows"
        check_mark = "[OK]" if is_windows else "✓"

        click.echo(f"\n{'='*60}")
        click.echo("Setup Complete - Summary:")
        click.echo(f"{'='*60}")
        click.echo(f"{check_mark} Sandboxed environment configured at: {target_dir}/.auditor_venv")
        click.echo(f"{check_mark} JS/TS tools installed at: {target_dir}/.auditor_venv/.theauditor_tools")
        click.echo(f"{check_mark} Professional linters installed (ruff, mypy, black, ESLint, TypeScript)")

    except Exception as e:
        raise click.ClickException(f"Setup failed: {e}") from e