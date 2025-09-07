"""Detect frameworks and libraries used in the project."""

import json
import click
from pathlib import Path


@click.command("detect-frameworks")
@click.option("--project-path", default=".", help="Root directory to analyze")
@click.option("--output-json", help="Path to output JSON file (default: .pf/raw/frameworks.json)")
def detect_frameworks(project_path, output_json):
    """Detect frameworks and libraries used in the project."""
    from theauditor.framework_detector import FrameworkDetector
    
    try:
        # Initialize detector
        project_path = Path(project_path).resolve()
        
        detector = FrameworkDetector(project_path, exclude_patterns=[])
        
        # Detect frameworks
        frameworks = detector.detect_all()
        
        # Determine output path - always save to .pf/frameworks.json by default
        if output_json:
            # User specified custom path
            save_path = Path(output_json)
        else:
            # Default path
            save_path = Path(project_path) / ".pf" / "raw" / "frameworks.json"
        
        # Always save the JSON output
        detector.save_to_file(save_path)
        click.echo(f"Frameworks written to {save_path}")
        
        # Display table
        table = detector.format_table()
        click.echo(table)
        
        # Return success
        if frameworks:
            click.echo(f"\nDetected {len(frameworks)} framework(s)")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e