"""Validate agent templates for SOP compliance."""

import click


@click.command("validate-templates")
@click.option("--source", default="./agent_templates", help="Directory containing agent templates")
@click.option("--format", type=click.Choice(["json", "text"]), default="text", help="Output format")
@click.option("--output", help="Write report to file instead of stdout")
def validate_templates(source, format, output):
    """Validate agent templates for SOP compliance."""
    from theauditor.agent_template_validator import TemplateValidator
    
    validator = TemplateValidator()
    results = validator.validate_all(source)
    
    report = validator.generate_report(results, format=format)
    
    if output:
        with open(output, 'w') as f:
            f.write(report)
        click.echo(f"Report written to {output}")
    else:
        click.echo(report)
    
    # Exit with non-zero if violations found
    if not results["valid"]:
        raise click.ClickException(
            f"Template validation failed: {results['total_violations']} violations found"
        )