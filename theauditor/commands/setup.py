"""Setup commands for TheAuditor - Claude Code integration."""

import click


@click.command("setup-claude")
@click.option(
    "--target", 
    required=True,
    help="Target project root (absolute or relative path)"
)
@click.option(
    "--source", 
    default="agent_templates",
    help="Path to TheAuditor agent templates directory (default: agent_templates)"
)
@click.option(
    "--sync",
    is_flag=True,
    help="Force update (still creates .bak on first change only)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print plan without executing"
)
def setup_claude(target, source, sync, dry_run):
    """Install Claude Code agents, hooks, and per-project venv for TheAuditor.
    
    This command performs a complete zero-optional installation:
    1. Creates a Python venv at <target>/.venv
    2. Installs TheAuditor into that venv (editable/offline)
    3. Creates cross-platform launcher wrappers at <target>/.claude/bin/
    4. Generates Claude agents from agent_templates/*.md
    5. Writes hooks to <target>/.claude/hooks.json
    
    All commands in agents/hooks use ./.claude/bin/aud to ensure
    they run with the project's own venv.
    """
    from theauditor.claude_setup import setup_claude_complete

    try:
        result = setup_claude_complete(
            target=target,
            source=source,
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