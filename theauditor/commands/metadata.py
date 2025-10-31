"""Metadata collection commands for churn and coverage analysis."""

import click
from pathlib import Path
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


@click.group()
@click.help_option("-h", "--help")
def metadata():
    """Collect temporal and quality metadata for FCE correlation and risk analysis.

    Group of commands that extract pure facts about code quality over time. Provides
    the temporal dimension (git churn, modification frequency) and quality dimension
    (test coverage, complexity) for Feed-forward Correlation Engine (FCE) analysis.

    AI ASSISTANT CONTEXT:
      Purpose: Extract temporal and quality facts for risk correlation
      Input: Git history, coverage reports, repo_index.db
      Output: .pf/raw/churn_analysis.json, .pf/raw/coverage_analysis.json
      Prerequisites: Git repository (for churn), coverage tool output (for coverage)
      Integration: Data feeds into 'aud fce' for compound risk detection
      Performance: ~5-20 seconds (git log parsing + database queries)

    SUBCOMMANDS:
      churn:
        - Analyzes git commit history for file volatility
        - Metrics: commits per file, unique authors, days since last change
        - Time range: Configurable (default 90 days)
        - Use case: Correlate high churn with vulnerabilities

      coverage:
        - Parses test coverage reports (coverage.py, Jest, etc.)
        - Metrics: Line coverage %, uncovered lines, branch coverage
        - Input: .coverage, coverage.xml, lcov.info
        - Use case: Correlate low coverage with defects

      analyze:
        - Combined analysis of churn + coverage + findings
        - Identifies hot spots (high churn + low coverage + vulnerabilities)
        - Outputs prioritized risk report
        - Use case: Focus refactoring on highest-risk files

    COMMON WORKFLOWS:
      Pre-Release Risk Assessment:
        aud metadata churn --days 30
        aud metadata coverage
        aud metadata analyze

      Continuous Monitoring:
        aud full && aud metadata churn && aud fce

      Technical Debt Tracking:
        aud metadata analyze --output ./debt_report.json

    EXAMPLES:
      # Analyze git churn for last 90 days
      aud metadata churn

      # Parse test coverage report
      aud metadata coverage

      # Combined hot spot analysis
      aud metadata analyze

    SEE ALSO:
      aud fce --help             # Understand FCE correlation engine
      aud metadata churn --help  # Detailed churn analysis options
      aud metadata coverage --help  # Coverage parsing options

    NOTE: Metadata commands extract raw facts only - no pattern detection or
    heuristics. Analysis and correlation happen in 'aud fce' and 'aud full'.
    """
    pass


@metadata.command("churn")
@click.option("--root", default=".", help="Root directory to analyze")
@click.option("--days", default=90, type=int, help="Number of days to analyze")
@click.option("--output", default="./.pf/raw/churn_analysis.json", help="Output JSON path")
def analyze_churn(root, days, output):
    """Analyze git commit history for code churn metrics.
    
    Collects pure facts about file volatility:
    - Number of commits per file in the specified time range
    - Number of unique authors per file
    - Days since last modification
    
    This data provides the temporal dimension for FCE correlation.
    
    Examples:
        # Analyze last 90 days (default)
        aud metadata churn
        
        # Analyze last 30 days
        aud metadata churn --days 30
        
        # Custom output location
        aud metadata churn --output analysis/churn.json
    """
    from theauditor.indexer.metadata_collector import MetadataCollector
    
    try:
        click.echo(f"Analyzing git history for last {days} days...")
        
        collector = MetadataCollector(root_path=root)
        result = collector.collect_churn(days=days, output_path=output)
        
        if 'error' in result:
            click.echo(f"[WARNING] {result['error']}", err=True)
            if not result.get('files'):
                return
        
        total_files = result.get('total_files_analyzed', 0)
        click.echo(f"[OK] Analyzed {total_files} files")
        
        if result.get('files'):
            # Show top 5 most active files
            click.echo("\nTop 5 most active files:")
            for i, file_data in enumerate(result['files'][:5], 1):
                click.echo(f"  {i}. {file_data['path']}")
                click.echo(f"     Commits: {file_data['commits_90d']}, "
                          f"Authors: {file_data['unique_authors']}, "
                          f"Last modified: {file_data['days_since_modified']} days ago")
        
        click.echo(f"\n[SAVED] Churn analysis saved to {output}")
        
    except Exception as e:
        logger.error(f"Churn analysis failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e))


@metadata.command("coverage")
@click.option("--root", default=".", help="Root directory")
@click.option("--coverage-file", help="Path to coverage file (auto-detects if not specified)")
@click.option("--output", default="./.pf/raw/coverage_analysis.json", help="Output JSON path")
def analyze_coverage(root, coverage_file, output):
    """Parse test coverage reports for quality metrics.
    
    Supports:
    - Python: coverage.json from coverage.py
    - Node.js: coverage-final.json from Istanbul/nyc
    
    Collects pure facts about test coverage:
    - Line coverage percentage per file
    - Number of executed vs missing lines
    - List of uncovered line numbers
    
    This data provides the quality dimension for FCE correlation.
    
    Examples:
        # Auto-detect coverage file
        aud metadata coverage
        
        # Specify Python coverage file
        aud metadata coverage --coverage-file htmlcov/coverage.json
        
        # Specify Node.js coverage file
        aud metadata coverage --coverage-file coverage/coverage-final.json
    """
    from theauditor.indexer.metadata_collector import MetadataCollector
    
    try:
        if coverage_file:
            click.echo(f"Loading coverage from: {coverage_file}")
        else:
            click.echo("Auto-detecting coverage file...")
        
        collector = MetadataCollector(root_path=root)
        result = collector.collect_coverage(
            coverage_file=coverage_file,
            output_path=output
        )
        
        if 'error' in result:
            click.echo(f"[ERROR] {result['error']}", err=True)
            if not result.get('files'):
                raise click.ClickException(result['error'])
        
        format_detected = result.get('format_detected', 'unknown')
        total_files = result.get('total_files_analyzed', 0)
        avg_coverage = result.get('average_coverage', 0)
        
        click.echo(f"[OK] Parsed {format_detected} coverage for {total_files} files")
        click.echo(f"     Average coverage: {avg_coverage}%")
        
        if result.get('files'):
            # Show 5 least covered files
            click.echo("\nLeast covered files:")
            for i, file_data in enumerate(result['files'][:5], 1):
                click.echo(f"  {i}. {file_data['path']}: {file_data['line_coverage_percent']}%")
                if file_data.get('lines_missing') is not None:
                    click.echo(f"     Missing: {file_data['lines_missing']} lines")
                elif file_data.get('statements_total') is not None:
                    covered = file_data.get('statements_executed', 0)
                    total = file_data.get('statements_total', 0)
                    click.echo(f"     Statements: {covered}/{total} covered")
        
        click.echo(f"\n[SAVED] Coverage analysis saved to {output}")
        
    except Exception as e:
        logger.error(f"Coverage analysis failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e))


@metadata.command("analyze")
@click.option("--root", default=".", help="Root directory")
@click.option("--days", default=90, type=int, help="Number of days for churn analysis")
@click.option("--coverage-file", help="Path to coverage file (optional)")
@click.option("--skip-churn", is_flag=True, help="Skip churn analysis")
@click.option("--skip-coverage", is_flag=True, help="Skip coverage analysis")
def analyze_all(root, days, coverage_file, skip_churn, skip_coverage):
    """Run both churn and coverage analysis (convenience command).
    
    This combines both metadata collection steps into a single command,
    useful for pipeline integration.
    
    Examples:
        # Run both analyses
        aud metadata analyze
        
        # Run with custom coverage file
        aud metadata analyze --coverage-file coverage.json
        
        # Run churn only
        aud metadata analyze --skip-coverage
    """
    from theauditor.indexer.metadata_collector import MetadataCollector
    
    try:
        collector = MetadataCollector(root_path=root)
        
        # Run churn analysis
        if not skip_churn:
            click.echo(f"[1/2] Analyzing git history for last {days} days...")
            churn_result = collector.collect_churn(
                days=days,
                output_path="./.pf/raw/churn_analysis.json"
            )
            
            if 'error' in churn_result:
                click.echo(f"  [WARNING] Churn: {churn_result['error']}", err=True)
            else:
                total = churn_result.get('total_files_analyzed', 0)
                click.echo(f"  [OK] Churn: Analyzed {total} files")
        else:
            click.echo("[1/2] Skipping churn analysis")
        
        # Run coverage analysis
        if not skip_coverage:
            click.echo("[2/2] Analyzing test coverage...")
            coverage_result = collector.collect_coverage(
                coverage_file=coverage_file,
                output_path="./.pf/raw/coverage_analysis.json"
            )
            
            if 'error' in coverage_result:
                click.echo(f"  [WARNING] Coverage: {coverage_result['error']}", err=True)
            else:
                format_type = coverage_result.get('format_detected', 'unknown')
                total = coverage_result.get('total_files_analyzed', 0)
                avg = coverage_result.get('average_coverage', 0)
                click.echo(f"  [OK] Coverage: {format_type} format, {total} files, {avg}% average")
        else:
            click.echo("[2/2] Skipping coverage analysis")
        
        click.echo("\n[COMPLETE] Metadata analysis finished")
        click.echo("  Output: .pf/raw/churn_analysis.json")
        click.echo("  Output: .pf/raw/coverage_analysis.json")
        
    except Exception as e:
        logger.error(f"Metadata analysis failed: {e}")
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e))