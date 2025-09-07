"""Detect universal runtime, DB, and logic patterns in code."""

import click
from pathlib import Path
from theauditor.utils.helpers import get_self_exclusion_patterns


@click.command("detect-patterns")
@click.option("--project-path", default=".", help="Root directory to analyze")
@click.option("--patterns", multiple=True, help="Pattern categories to use (e.g., runtime_issues, db_issues)")
@click.option("--output-json", help="Path to output JSON file")
@click.option("--file-filter", help="Glob pattern to filter files")
@click.option("--max-rows", default=50, type=int, help="Maximum rows to display in table")
@click.option("--print-stats", is_flag=True, help="Print summary statistics")
@click.option("--with-ast/--no-ast", default=True, help="Enable AST-based pattern matching")
@click.option("--with-frameworks/--no-frameworks", default=True, help="Enable framework detection and framework-specific patterns")
@click.option("--exclude-self", is_flag=True, help="Exclude TheAuditor's own files (for self-testing)")
def detect_patterns(project_path, patterns, output_json, file_filter, max_rows, print_stats, with_ast, with_frameworks, exclude_self):
    """Detect universal runtime, DB, and logic patterns in code."""
    from theauditor.pattern_loader import PatternLoader
    from theauditor.universal_detector import UniversalPatternDetector
    
    try:
        # Initialize detector
        project_path = Path(project_path).resolve()
        pattern_loader = PatternLoader()
        
        # Get exclusion patterns using centralized function
        exclude_patterns = get_self_exclusion_patterns(exclude_self)
        
        detector = UniversalPatternDetector(
            project_path, 
            pattern_loader,
            with_ast=with_ast,
            with_frameworks=with_frameworks,
            exclude_patterns=exclude_patterns
        )
        
        # Run detection
        categories = list(patterns) if patterns else None
        findings = detector.detect_patterns(categories=categories, file_filter=file_filter)
        
        # Always save results to default location
        patterns_output = project_path / ".pf" / "raw" / "patterns.json"
        patterns_output.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to user-specified location if provided
        if output_json:
            detector.to_json(Path(output_json))
            click.echo(f"\n[OK] Full results saved to: {output_json}")
        
        # Save to default location
        detector.to_json(patterns_output)
        click.echo(f"[OK] Full results saved to: {patterns_output}")
        
        # Display table
        table = detector.format_table(max_rows=max_rows)
        click.echo(table)
        
        # Print statistics if requested
        if print_stats:
            stats = detector.get_summary_stats()
            click.echo("\n--- Summary Statistics ---")
            click.echo(f"Total findings: {stats['total_findings']}")
            click.echo(f"Files affected: {stats['files_affected']}")
            
            if stats['by_severity']:
                click.echo("\nBy severity:")
                for severity, count in sorted(stats['by_severity'].items()):
                    click.echo(f"  {severity}: {count}")
            
            if stats['by_category']:
                click.echo("\nBy category:")
                for category, count in sorted(stats['by_category'].items()):
                    click.echo(f"  {category}: {count}")
        
        # Successfully completed - found and reported all issues
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e