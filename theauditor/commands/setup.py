"""Setup commands for TheAuditor - Claude Code integration."""

import click


@click.command("setup-claude")
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
def setup_claude(target, sync, dry_run):
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
    from theauditor.claude_setup import setup_claude_complete

    try:
        result = setup_claude_complete(
            target=target,
            sync=sync,
            dry_run=dry_run
        )

        # The setup_claude_complete function already prints detailed output
        # Just handle any failures here
        if result.get("failed"):
            click.echo("\n[WARN]  Some operations failed:", err=True)
            for item in result["failed"]:
                click.echo(f"  - {item}", err=True)
            raise click.ClickException("Setup incomplete due to failures")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e