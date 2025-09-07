"""Run Factual Correlation Engine to aggregate and correlate findings."""

import click
from theauditor.utils.error_handler import handle_exceptions


@click.command(name="fce")
@handle_exceptions
@click.option("--root", default=".", help="Root directory")
@click.option("--capsules", default="./.pf/capsules", help="Capsules directory")
@click.option("--manifest", default="manifest.json", help="Manifest file path")
@click.option("--workset", default="./.pf/workset.json", help="Workset file path")
@click.option("--timeout", default=600, type=int, help="Timeout in seconds")
@click.option("--print-plan", is_flag=True, help="Print detected tools without running")
def fce(root, capsules, manifest, workset, timeout, print_plan):
    """Run Factual Correlation Engine to aggregate and correlate findings."""
    from theauditor.fce import run_fce

    result = run_fce(
        root_path=root,
        capsules_dir=capsules,
        manifest_path=manifest,
        workset_path=workset,
        timeout=timeout,
        print_plan=print_plan,
    )

    if result.get("printed_plan"):
        return

    if result["success"]:
        if result["failures_found"] == 0:
            click.echo("[OK] All tools passed - no failures detected")
        else:
            click.echo(f"Found {result['failures_found']} failures")
            # Check if output_files exists and has at least 2 elements
            if result.get('output_files') and len(result.get('output_files', [])) > 1:
                click.echo(f"FCE report written to: {result['output_files'][1]}")
            elif result.get('output_files') and len(result.get('output_files', [])) > 0:
                click.echo(f"FCE report written to: {result['output_files'][0]}")
    else:
        click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
        raise click.ClickException(result.get("error", "FCE failed"))