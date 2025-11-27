"""Detect universal runtime, DB, and logic patterns in code."""

import click
from pathlib import Path
from theauditor.utils.helpers import get_self_exclusion_patterns


@click.command("detect-patterns")
@click.option("--project-path", default=".", help="Root directory to analyze")
@click.option(
    "--patterns", multiple=True, help="Pattern categories to use (e.g., runtime_issues, db_issues)"
)
@click.option("--output-json", help="Path to output JSON file")
@click.option("--file-filter", help="Glob pattern to filter files")
@click.option("--max-rows", default=50, type=int, help="Maximum rows to display in table")
@click.option("--print-stats", is_flag=True, help="Print summary statistics")
@click.option("--with-ast/--no-ast", default=True, help="Enable AST-based pattern matching")
@click.option(
    "--with-frameworks/--no-frameworks",
    default=True,
    help="Enable framework detection and framework-specific patterns",
)
@click.option(
    "--exclude-self", is_flag=True, help="Exclude TheAuditor's own files (for self-testing)"
)
def detect_patterns(
    project_path,
    patterns,
    output_json,
    file_filter,
    max_rows,
    print_stats,
    with_ast,
    with_frameworks,
    exclude_self,
):
    """Detect security vulnerabilities and code quality issues.

    Runs 100+ security pattern rules across your codebase using both
    regex and AST-based detection. Covers OWASP Top 10, CWE Top 25,
    and framework-specific vulnerabilities.

    Pattern Categories:
      Authentication:
        - Hardcoded credentials and API keys
        - Weak password validation
        - Missing authentication checks
        - Insecure session management

      Injection Attacks:
        - SQL injection vulnerabilities
        - Command injection risks
        - XSS (Cross-Site Scripting)
        - Template injection
        - LDAP/NoSQL injection

      Data Security:
        - Exposed sensitive data
        - Insecure cryptography
        - Weak random number generation
        - Missing encryption

      Infrastructure:
        - Debug mode in production
        - Insecure CORS configuration
        - Missing security headers
        - Exposed admin interfaces

      Code Quality:
        - Race conditions
        - Resource leaks
        - Infinite loops
        - Dead code blocks

    Detection Methods:
      1. Pattern Matching: Fast regex-based detection
      2. AST Analysis: Semantic understanding of code structure
      3. Framework Detection: Django, Flask, React-specific rules

    Examples:
      aud detect-patterns                           # Run all patterns
      aud detect-patterns --patterns auth_issues    # Specific category
      aud detect-patterns --file-filter "*.py"      # Python files only
      aud detect-patterns --no-ast                  # Regex only (faster)
      aud detect-patterns --exclude-self            # Skip TheAuditor files

    Output:
      .pf/raw/patterns.json       # All findings in JSON
      .pf/readthis/patterns_*.json # AI-optimized chunks

    Finding Format:
      {
        "file": "src/auth.py",
        "line": 42,
        "pattern": "hardcoded_secret",
        "severity": "critical",
        "message": "Hardcoded API key detected",
        "code_snippet": "api_key = 'sk_live_...'",
        "cwe": "CWE-798"
      }

    Severity Levels:
      critical - Immediate security risk
      high     - Serious vulnerability
      medium   - Potential issue
      low      - Code quality concern

    Performance:
      Small project:  < 30 seconds
      Large project:  2-5 minutes
      With AST:       2-3x slower but more accurate

    Note: Use --with-ast for comprehensive analysis (default).
    Disable with --no-ast for quick scans."""
    from theauditor.pattern_loader import PatternLoader
    from theauditor.universal_detector import UniversalPatternDetector

    try:
        project_path = Path(project_path).resolve()
        pattern_loader = PatternLoader()

        exclude_patterns = get_self_exclusion_patterns(exclude_self)

        detector = UniversalPatternDetector(
            project_path,
            pattern_loader,
            with_ast=with_ast,
            with_frameworks=with_frameworks,
            exclude_patterns=exclude_patterns,
        )

        categories = list(patterns) if patterns else None
        findings = detector.detect_patterns(categories=categories, file_filter=file_filter)

        db_path = project_path / ".pf" / "repo_index.db"
        if db_path.exists():
            try:
                from theauditor.indexer.database import DatabaseManager

                db_manager = DatabaseManager(str(db_path))

                findings_dicts = []
                for f in findings:
                    if hasattr(f, "to_dict"):
                        findings_dicts.append(f.to_dict())
                    elif isinstance(f, dict):
                        findings_dicts.append(f)
                    else:
                        findings_dicts.append(dict(f))

                db_manager.write_findings_batch(findings_dicts, tool_name="patterns")
                db_manager.close()

                click.echo(f"[DB] Wrote {len(findings)} findings to database for FCE correlation")
            except Exception as e:
                click.echo(f"[DB] Warning: Database write failed: {e}", err=True)
                click.echo("[DB] JSON output will still be generated for AI consumption")
        else:
            click.echo(
                f"[DB] Database not found - run 'aud full' first for optimal FCE performance"
            )

        output_path = (
            Path(output_json) if output_json else (project_path / ".pf" / "raw" / "patterns.json")
        )
        detector.to_json(output_path)
        click.echo(f"[OK] Patterns analysis saved to {output_path}")

        table = detector.format_table(max_rows=max_rows)
        click.echo(table)

        if print_stats:
            stats = detector.get_summary_stats()
            click.echo("\n--- Summary Statistics ---")
            click.echo(f"Total findings: {stats['total_findings']}")
            click.echo(f"Files affected: {stats['files_affected']}")

            if stats["by_severity"]:
                click.echo("\nBy severity:")
                for severity, count in sorted(stats["by_severity"].items()):
                    click.echo(f"  {severity}: {count}")

            if stats["by_category"]:
                click.echo("\nBy category:")
                for category, count in sorted(stats["by_category"].items()):
                    click.echo(f"  {category}: {count}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e
