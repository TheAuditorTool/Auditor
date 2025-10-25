"""Ensure minimal mypy config exists (idempotent)."""

import click


@click.command("init-config")
@click.option("--pyproject", default="pyproject.toml", help="Path to pyproject.toml")
def init_config(pyproject):
    """Ensure minimal mypy configuration exists in pyproject.toml.

    This command creates or updates pyproject.toml with a minimal mypy configuration
    required for type checking. It is idempotent (safe to run multiple times) and
    will not overwrite existing mypy settings.

    WHY THIS IS NEEDED:
    - TheAuditor's lint command runs mypy for type checking
    - mypy requires a config file to function properly
    - Missing config causes lint failures or incorrect type checking
    - Ensures consistent type checking across all environments

    WHAT IT CREATES:
    - Adds [tool.mypy] section to pyproject.toml if missing
    - Sets basic type checking options (strict mode disabled by default)
    - Preserves any existing mypy configuration

    EXAMPLES:
      # Initialize mypy config in current directory
      aud init-config

      # Specify custom pyproject.toml location
      aud init-config --pyproject /path/to/pyproject.toml

      # Run as part of project setup
      aud init && aud init-config && aud init-js

    OUTPUT:
      - Creates or updates pyproject.toml with [tool.mypy] section
      - Prints confirmation message

    CREATED CONFIG:
      [tool.mypy]
      python_version = "3.11"
      warn_return_any = true
      warn_unused_configs = true

    PREREQUISITES:
      None - this command can be run anytime

    RELATED COMMANDS:
      aud init              # Initialize .pf/ directory
      aud init-js           # Initialize package.json for JS projects
      aud lint              # Runs mypy using this config

    NOTE: This command is idempotent. Running it multiple times will not
    create duplicate config sections or overwrite existing settings.
    """
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
