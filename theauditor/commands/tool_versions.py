"""Detect and record tool versions."""

import click


@click.command("tool-versions")
@click.option("--out-dir", default="./.pf/raw", help="Output directory for version manifest")
def tool_versions(out_dir):
    """Detect and record versions of all analysis tools.

    This command creates a version manifest for reproducibility and debugging.
    It detects versions of:
    - Python linters (pylint, mypy, flake8, black, ruff)
    - JavaScript linters (ESLint, TypeScript compiler)
    - Security scanners (semgrep, bandit)
    - TheAuditor itself

    WHY THIS MATTERS:
    - Ensures analysis reproducibility across environments
    - Helps debug tool-specific issues
    - Validates tool installation after setup
    - Required for comparing results across runs

    EXAMPLES:
      # Record tool versions after setup
      aud setup-ai --target . && aud tool-versions

      # Verify tools before CI run
      aud tool-versions && aud full

      # Debug version mismatches
      aud tool-versions --out-dir ./debug

    OUTPUT:
      .pf/raw/tools.json           # Version manifest with timestamps (machine-readable)
      .pf/raw/TOOLS.md             # Human-readable version report

    OUTPUT FORMAT:
      {
        "python": "3.11.4",
        "pylint": "2.17.4",
        "eslint": "8.43.0",
        "theauditor": "1.3.0-RC1",
        "detected_at": "2025-10-26T15:30:00Z"
      }

    COMMON WORKFLOWS:
      Initial Setup:
        aud setup-ai --target . && aud tool-versions  # Install and verify tools

      CI/CD Pipeline:
        aud tool-versions                             # Record baseline
        aud full                                      # Run analysis
        aud report                                    # Compare with previous runs

      Debugging:
        aud tool-versions --out-dir ./debug           # Save versions for support ticket

    PREREQUISITES:
      aud setup-ai --target .      # Install sandboxed tools

    RELATED COMMANDS:
      aud setup-ai                 # Setup tools first
      aud full                     # Uses tool versions for analysis

    NOTE: This command is idempotent and safe to run multiple times.
    It will overwrite previous version files.
    """
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
