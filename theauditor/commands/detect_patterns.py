"""Detect universal runtime, DB, and logic patterns in code."""

from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.helpers import get_self_exclusion_patterns


@click.command("detect-patterns", cls=RichCommand)
@click.option("--project-path", default=".", help="Root directory to analyze")
@click.option(
    "--patterns", multiple=True, help="Pattern categories to use (e.g., runtime_issues, db_issues)"
)
@click.option("--json", "as_json", is_flag=True, help="Output findings as JSON to stdout")
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
    as_json,
    file_filter,
    max_rows,
    print_stats,
    with_ast,
    with_frameworks,
    exclude_self,
):
    """Detect security vulnerabilities and code quality issues.

    DESCRIPTION:
      Runs 100+ security pattern rules across your codebase using both
      regex and AST-based detection. Covers OWASP Top 10, CWE Top 25,
      and framework-specific vulnerabilities.

      Detection Methods:
        1. Pattern Matching: Fast regex-based detection
        2. AST Analysis: Semantic understanding of code structure
        3. Framework Detection: Django, Flask, React-specific rules

    AI ASSISTANT CONTEXT:
      Purpose: Detect security vulnerabilities via pattern matching
      Input: Source code files (Python, JavaScript, TypeScript, etc.)
      Output: Console (summary) or JSON (--json), findings stored in database
      Prerequisites: None (can run standalone or after aud full)
      Integration: Runs in 'aud full' pipeline Stage 3 Track B
      Performance: 30 seconds to 5 minutes depending on codebase size

    WHAT IT DETECTS:
      Authentication Issues:
        Hardcoded credentials, API keys, weak passwords, missing auth checks

      Injection Attacks:
        SQL injection, command injection, XSS, template injection, LDAP/NoSQL

      Data Security:
        Exposed secrets, insecure crypto, weak RNG, missing encryption

      Infrastructure:
        Debug mode, insecure CORS, missing headers, exposed admin

      Code Quality:
        Race conditions, resource leaks, infinite loops, dead code

    EXAMPLES:
      aud detect-patterns                           # Run all patterns
      aud detect-patterns --patterns auth_issues    # Specific category
      aud detect-patterns --file-filter "*.py"      # Python files only
      aud detect-patterns --no-ast                  # Regex only (faster)
      aud detect-patterns --exclude-self            # Skip TheAuditor files

    OUTPUT:
      Console: Summary counts by severity
      --json:  All findings to stdout (pipe to file if needed)

      Finding Format:
        {
          "file": "src/auth.py",
          "line": 42,
          "pattern": "hardcoded_secret",
          "severity": "critical",
          "message": "Hardcoded API key detected",
          "cwe": "CWE-798"
        }

    PERFORMANCE:
      Small project (<5K LOC):    ~30 seconds
      Large project (50K+ LOC):   2-5 minutes
      With --no-ast:              2-3x faster but less accurate

    EXIT CODES:
      0 = Success (findings may still exist - check output)
      1 = Error during analysis

    RELATED COMMANDS:
      aud full               # Runs this as part of complete pipeline
      aud taint      # Complementary data flow analysis
      aud fce                # Cross-references pattern findings

    SEE ALSO:
      aud manual patterns    # Learn about pattern detection concepts
      aud manual severity    # Understand severity classifications

    NOTE:
      Use --with-ast for comprehensive analysis (default).
      Disable with --no-ast for quick scans.
      Findings are written to database for FCE correlation if repo_index.db exists."""
    from theauditor.universal_detector import UniversalPatternDetector

    try:
        project_path = Path(project_path).resolve()

        exclude_patterns = get_self_exclusion_patterns(exclude_self)

        detector = UniversalPatternDetector(
            project_path,
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

                console.print(
                    f"\\[DB] Wrote {len(findings)} findings to database for FCE correlation",
                    highlight=False,
                )
            except Exception as e:
                err_console.print(
                    f"[error]\\[DB] Warning: Database write failed: {e}[/error]",
                    highlight=False,
                )
        else:
            console.print(
                "\\[DB] Database not found - run 'aud full' first for optimal FCE performance"
            )

        if as_json:
            # Output JSON to stdout for piping
            import json
            findings_output = []
            for f in findings:
                if hasattr(f, "to_dict"):
                    findings_output.append(f.to_dict())
                elif isinstance(f, dict):
                    findings_output.append(f)
                else:
                    findings_output.append(dict(f))
            print(json.dumps(findings_output, indent=2))
        else:
            # Console table output
            table = detector.format_table(max_rows=max_rows)
            console.print(table, markup=False)

        if print_stats:
            stats = detector.get_summary_stats()
            console.print("\n--- Summary Statistics ---")
            console.print(f"Total findings: {stats['total_findings']}", highlight=False)
            console.print(f"Files affected: {stats['files_affected']}", highlight=False)

            if stats["by_severity"]:
                console.print("\nBy severity:")
                for severity, count in sorted(stats["by_severity"].items()):
                    console.print(f"  {severity}: {count}", highlight=False)

            if stats["by_category"]:
                console.print("\nBy category:")
                for category, count in sorted(stats["by_category"].items()):
                    console.print(f"  {category}: {count}", highlight=False)

    except Exception as e:
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.ClickException(str(e)) from e
