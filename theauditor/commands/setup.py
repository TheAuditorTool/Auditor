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
    """Setup sandboxed JS/TS analysis tools for TheAuditor.

    This command creates a sandboxed environment for JavaScript/TypeScript analysis:
    1. Creates a Python venv at <target>/.auditor_venv
    2. Installs TheAuditor into that venv (editable)
    3. Sets up isolated JS/TS tools at <target>/.auditor_venv/.theauditor_tools
    4. Installs ESLint, TypeScript, and other analysis tools

    This sandbox ensures JS/TS analysis works correctly without interfering
    with the project's own dependencies.
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