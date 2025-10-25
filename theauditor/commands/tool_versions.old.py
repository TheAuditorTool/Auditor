"""Detect and record tool versions."""

import click


@click.command("tool-versions")
@click.option("--out-dir", default="./.pf/audit", help="Output directory")
def tool_versions(out_dir):
    """Detect and record tool versions."""
    from theauditor.tools import write_tools_report

    try:
        res = write_tools_report(out_dir)
        click.echo(f"[OK] Tool versions written to {out_dir}/")
        click.echo("  - TOOLS.md (human-readable)")
        click.echo("  - tools.json (machine-readable)")

        # Show summary
        python_found = sum(1 for v in res["python"].values() if v != "missing")
        node_found = sum(1 for v in res["node"].values() if v != "missing")
        click.echo(f"  - Python tools: {python_found}/4 found")
        click.echo(f"  - Node tools: {node_found}/3 found")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e