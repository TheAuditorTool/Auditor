"""Context command - semantic business logic for findings classification.

Apply user-defined YAML rules to classify analysis findings based on your
business logic, refactoring contexts, and semantic patterns.

Example: During OAuth migration, mark all JWT findings as "obsolete".
"""

import sqlite3
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.error_handler import handle_exceptions


@click.command(cls=RichCommand)
@click.option(
    "--file",
    "-f",
    "context_file",
    required=True,
    type=click.Path(exists=True),
    help="Semantic context YAML file",
)
@click.option("--output", "-o", type=click.Path(), help="Custom output JSON file (optional)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed findings in report")
@handle_exceptions
def context(context_file: str, output: str | None, verbose: bool):
    """Apply user-defined semantic rules to classify findings based on business logic and refactoring context.

    Enables project-specific interpretation of analysis findings through YAML rules that classify
    issues as obsolete (needs immediate fix), current (correct pattern), or transitional (acceptable
    during migration). Essential for refactoring workflows where temporary inconsistencies are expected
    (e.g., OAuth migration makes JWT findings obsolete, but old endpoints still exist during transition).

    AI ASSISTANT CONTEXT:
      Purpose: Semantic classification of findings based on business context
      Input: context.yaml (rules), findings_consolidated table (from aud full)
      Output: Console or JSON (--json), classified findings to stdout
      Prerequisites: aud full or aud detect-patterns (populates findings)
      Integration: Refactoring workflows, technical debt tracking, migration planning
      Performance: ~1-3 seconds (YAML parsing + finding classification)

    YAML CONFIGURATION REQUIRED:
      You MUST write a semantic context YAML file defining:
      - Obsolete patterns (deprecated code to flag for removal)
      - Current patterns (correct patterns to keep high-priority)
      - Transitional patterns (temporary dual-stack code with expiry date)

      For full YAML schema and templates: aud manual context

    WHAT IT CLASSIFIES:
      Finding States:
        - obsolete: Code using deprecated patterns (must fix)
        - current: Code following current standards (correct)
        - transitional: Temporary inconsistency during migration (acceptable)

      Use Cases:
        - OAuth Migration: Mark JWT findings as obsolete, OAuth2 as current
        - API Refactoring: Flag old endpoints as transitional during cutover
        - Framework Upgrade: Classify deprecated API usage as obsolete
        - Database Migration: Mark old table references as obsolete

    HOW IT WORKS (Semantic Classification):
      1. Load Context YAML:
         - Parses user-defined classification rules
         - Rules specify patterns (file paths, finding types) and their states

      2. Load Analysis Findings:
         - Reads findings from database (findings_consolidated table)
         - Includes detect-patterns, taint, deadcode, etc.

      3. Apply Classification Rules:
         - Matches findings against YAML patterns
         - Assigns state (obsolete/current/transitional)
         - Unmatched findings default to "current"

      4. Generate Report:
         - Groups findings by state
         - Calculates counts per classification
         - Outputs to console (or JSON with --json flag)

    YAML RULE FORMAT:
      refactor_context:
        name: "OAuth2 Migration"
        rules:
          - pattern: "jwt.sign"
            state: "obsolete"
            reason: "JWT auth deprecated, use OAuth2"
            files: ["api/auth/*.py"]

          - pattern: "oauth2.authorize"
            state: "current"
            reason: "New OAuth2 standard"

          - pattern: "legacy_api_key"
            state: "transitional"
            reason: "Allowed during 30-day migration period"

    EXAMPLES:
      # Use Case 1: Classify findings during OAuth migration
      aud full && aud context --file ./oauth_migration.yaml

      # Use Case 2: Verbose output (show all classified findings)
      aud context -f refactor_rules.yaml --verbose

      # Use Case 3: Export classification report
      aud context -f rules.yaml --output ./classification_report.json

    COMMON WORKFLOWS:
      Pre-Merge Refactoring Check:
        aud full && aud context -f refactor_context.yaml

      Migration Progress Tracking:
        aud context -f migration.yaml --verbose | grep obsolete

      Technical Debt Prioritization:
        aud context -f debt_rules.yaml -o debt_report.json

    OUTPUT FORMAT (context_report.json Schema):
      {
        "context_name": "OAuth2 Migration",
        "classified_findings": {
          "obsolete": [
            {
              "file": "api/auth.py",
              "line": 45,
              "finding": "jwt.sign() usage",
              "reason": "JWT deprecated, use OAuth2"
            }
          ],
          "current": [...],
          "transitional": [...]
        },
        "summary": {
          "obsolete_count": 15,
          "current_count": 120,
          "transitional_count": 8
        }
      }

    PERFORMANCE EXPECTATIONS:
      All cases: ~1-3 seconds (YAML parsing + classification logic)

    FLAG INTERACTIONS:
      --file: YAML rules file (REQUIRED)
      --output: Custom output path (writes JSON to file)
      --verbose: Shows detailed findings in console output

    PREREQUISITES:
      Required:
        aud full                   # Or aud detect-patterns (populates findings)
        context.yaml               # User-defined classification rules

    EXIT CODES:
      0 = Success, findings classified
      1 = YAML parse error or file not found
      2 = No findings to classify (run analysis first)

    RELATED COMMANDS:
      aud full               # Populates findings for classification
      aud detect-patterns    # Minimal analysis for findings
      aud refactor           # Detects schema-code mismatches

    SEE ALSO:
      aud manual context     # Deep dive into semantic context concepts
      aud full --help        # Understand full analysis pipeline

    TROUBLESHOOTING:
      Error: "YAML parse error":
        -> Validate YAML syntax: cat context.yaml | yaml lint
        -> Check indentation (YAML is whitespace-sensitive)
        -> Verify required fields (refactor_context, rules)

      No findings classified:
        -> Run 'aud full' or 'aud detect-patterns' first
        -> Check database has findings: aud query --findings
        -> Verify YAML patterns match actual finding types

      All findings marked "current" (no obsolete):
        -> YAML patterns may not match finding format
        -> Check pattern field names match finding structure
        -> Use --verbose to see classification logic

    NOTE: Context classification is for human workflow management, not security
    enforcement. "Transitional" findings are still real issues that must be fixed
    eventually - classification just provides temporary exception tracking.
    """
    from theauditor.context import SemanticContext

    pf_dir = Path.cwd() / ".pf"
    db_path = pf_dir / "repo_index.db"

    if not db_path.exists():
        err_console.print(
            "\n" + "=" * 60,
        )
        err_console.print(
            "[error]\\[X] ERROR: Database not found[/error]",
        )
        console.rule()
        err_console.print(
            "[error]\nSemantic context requires analysis data.[/error]",
        )
        err_console.print(
            "[error]\nPlease run ONE of these first:[/error]",
        )
        err_console.print(
            "[error]\n  Option A (Recommended):[/error]",
        )
        err_console.print(
            "[error]    aud full[/error]",
        )
        err_console.print(
            "[error]\nThen try again:[/error]",
        )
        err_console.print(
            f"[error]    aud context --file {context_file}\n[/error]", highlight=False
        )
        raise click.Abort()

    console.print("\n" + "=" * 80, markup=False)
    console.print("SEMANTIC CONTEXT ANALYSIS")
    console.rule()
    console.print(f"\n Loading semantic context: {context_file}", highlight=False)

    try:
        context = SemanticContext.load(Path(context_file))
    except (FileNotFoundError, ValueError) as e:
        err_console.print(
            f"[error]\n\\[X] ERROR loading context file: {e}[/error]", highlight=False
        )
        raise click.Abort() from e

    console.print(f"[success]Loaded context: {context.context_name}[/success]", highlight=False)
    console.print(f"  Version: {context.version}", highlight=False)
    console.print(f"  Description: {context.description}", highlight=False)

    console.print("\n Loading findings from database...")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='findings_consolidated'
        """)

        if not cursor.fetchone():
            err_console.print(
                "\n[warning]️  WARNING: findings_consolidated table not found[/warning]",
            )
            err_console.print(
                "[error]\nThis means analysis hasn't been run yet.[/error]",
            )
            err_console.print(
                "[error]\nPlease run:[/error]",
            )
            err_console.print(
                "[error]    aud full[/error]",
            )
            conn.close()
            raise click.Abort()

        cursor.execute("""
            SELECT file, line, column, rule, tool, message, severity, category, code_snippet, cwe
            FROM findings_consolidated
            ORDER BY file, line
        """)

        findings = []
        for row in cursor.fetchall():
            findings.append(
                {
                    "file": row["file"],
                    "line": row["line"],
                    "column": row["column"],
                    "rule": row["rule"],
                    "tool": row["tool"],
                    "message": row["message"],
                    "severity": row["severity"],
                    "category": row["category"],
                    "code_snippet": row["code_snippet"],
                    "cwe": row["cwe"],
                }
            )

        conn.close()

    except sqlite3.Error as e:
        err_console.print(f"[error]\n\\[X] ERROR reading database: {e}[/error]", highlight=False)
        raise click.Abort() from e

    if not findings:
        console.print("\n[warning]️  No findings in database[/warning]")
        console.print("\nThis could mean:")
        console.print("  1. Analysis hasn't been run yet (run: aud full)")
        console.print("  2. No issues detected (clean code!)")
        console.print("  3. Database is outdated (re-run: aud full)")
        console.print("\nCannot classify findings without data.")
        raise click.Abort()

    console.print(
        f"[success]Loaded {len(findings)} findings from database[/success]", highlight=False
    )

    console.print("\n Applying semantic patterns:")
    console.print(f"  Obsolete patterns:     {len(context.obsolete_patterns)}", highlight=False)
    console.print(f"  Current patterns:      {len(context.current_patterns)}", highlight=False)
    console.print(f"  Transitional patterns: {len(context.transitional_patterns)}", highlight=False)

    console.print("\n️  Classifying findings...")
    result = context.classify_findings(findings)

    console.print("[success]Classification complete[/success]")
    console.print(f"  Classified: {result.summary['classified']}", highlight=False)
    console.print(f"  Unclassified: {result.summary['unclassified']}", highlight=False)

    console.print("\n" + "=" * 80, markup=False)
    report = context.generate_report(result, verbose=verbose)
    console.print(report, markup=False)

    if output:
        console.print("\n" + "=" * 80, markup=False)
        console.print(" Writing results...")
        console.rule()
        context.export_to_json(result, Path(output))
        console.print(f"\n\\[OK] Custom output: {output}", highlight=False)

    console.print("\n" + "=" * 80, markup=False)
    console.print("[success]SEMANTIC CONTEXT ANALYSIS COMPLETE[/success]")
    console.rule()

    migration_progress = result.get_migration_progress()
    if migration_progress["files_need_migration"] > 0:
        console.print("\n Next steps:")
        console.print(
            f"  1. Address {len(result.get_high_priority_files())} high-priority files",
            highlight=False,
        )
        console.print(f"  2. Update {len(result.mixed_files)} mixed files", highlight=False)
        console.print(
            f"  3. Migrate {migration_progress['files_need_migration']} files total",
            highlight=False,
        )
        console.print("\n  Run with --verbose for detailed file list")
    else:
        console.print("\n All files migrated! No obsolete patterns found.")


context_command = context
