"""Ensure minimal mypy config exists (idempotent)."""

import click


@click.command("init-config")
@click.option("--pyproject", default="pyproject.toml", help="Path to pyproject.toml")
def init_config(pyproject):
    """Ensure minimal mypy config exists (idempotent)."""
    from theauditor.config import ensure_mypy_config

    try:
        res = ensure_mypy_config(pyproject)
        msg = (
            "mypy config created"
            if res.get("status") == "created"
            else "mypy config already present"
        )
        click.echo(msg)
    except Exception as e:
        raise click.ClickException(f"Failed to init config: {e}") from e