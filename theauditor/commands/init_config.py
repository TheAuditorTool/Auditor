"""Ensure minimal mypy config exists (idempotent)."""

import click


@click.command("init-config", hidden=True)
@click.option("--pyproject", default="pyproject.toml", help="Path to pyproject.toml")
def init_config(pyproject):
    """Create or update minimal mypy type-checking configuration in pyproject.toml (idempotent).

    Scaffolds basic mypy configuration required for TheAuditor's lint command to perform
    Python type checking. Idempotent operation that preserves existing mypy settings while
    ensuring minimum required configuration exists. Prevents lint failures due to missing
    mypy config.

    AI ASSISTANT CONTEXT:
      Purpose: Bootstrap mypy type-checking configuration
      Input: Existing pyproject.toml (if present) or create new
      Output: pyproject.toml with [tool.mypy] section
      Prerequisites: None (creates from scratch if needed)
      Integration: Enables 'aud lint' for Python type checking
      Performance: ~1 second (file I/O only)

    WHY NEEDED:
      - TheAuditor's lint command runs mypy for type checking
      - mypy requires config file to function properly
      - Missing config causes lint failures or incorrect analysis
      - Ensures consistent type checking across environments

    WHAT IT CREATES:
      [tool.mypy] section in pyproject.toml:
        - python_version = "3.11"
        - warn_return_any = true
        - warn_unused_configs = true
        - Strict mode disabled (opt-in via manual edit)

    EXAMPLES:
      aud init-config
      aud init-config --pyproject /path/to/pyproject.toml
      aud init && aud init-config && aud init-js

    PERFORMANCE: ~1 second

    EXIT CODES:
      0 = Success
      1 = File write error

    RELATED COMMANDS:
      aud init     # Python project initialization
      aud init-js  # JavaScript/TypeScript configuration
      aud lint     # Uses mypy with created config

    NOTE: This command does NOT enable strict type checking by default. For
    strict mode, manually edit pyproject.toml and set strict = true.
    """
    click.echo("WARNING: 'aud init-config' is deprecated and will be removed in v2.0.")
    click.echo("         Mypy configuration is not part of security auditing.")
    click.echo("")

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
