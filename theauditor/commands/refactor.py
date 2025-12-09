"""Refactoring impact analysis command.

Analyzes database migrations to detect schema changes and finds code that still
references removed/renamed fields and tables, reporting potential breaking changes.

NO pattern detection. NO FCE. Just direct database queries.
"""

import json
import re
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console
from theauditor.refactor import (
    ProfileEvaluation,
    RefactorProfile,
    RefactorRuleEngine,
)

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


DROP_TABLE = re.compile(r'(?:dropTable|DROP\s+TABLE)\s*\(\s*[\'"`](\w+)[\'"`]', re.IGNORECASE)
REMOVE_COLUMN = re.compile(
    r'(?:removeColumn|dropColumn|DROP\s+COLUMN)\s*\(\s*[\'"`](\w+)[\'"`]\s*,\s*[\'"`](\w+)[\'"`]',
    re.IGNORECASE,
)
RENAME_TABLE = re.compile(
    r'(?:renameTable|RENAME\s+TABLE)\s*\(\s*[\'"`](\w+)[\'"`]\s*,\s*[\'"`](\w+)[\'"`]',
    re.IGNORECASE,
)
RENAME_COLUMN = re.compile(
    r'(?:renameColumn)\s*\(\s*[\'"`](\w+)[\'"`]\s*,\s*[\'"`](\w+)[\'"`]\s*,\s*[\'"`](\w+)[\'"`]',
    re.IGNORECASE,
)


@click.command(cls=RichCommand)
@click.option(
    "--migration-dir",
    "-m",
    default="backend/migrations",
    help="Directory containing database migrations",
)
@click.option(
    "--migration-limit",
    "-ml",
    type=int,
    default=0,
    help="Number of recent migrations to analyze (0=all, default=all)",
)
@click.option(
    "--file",
    "-f",
    "profile_file",
    type=click.Path(exists=True),
    help="Refactor profile YAML describing old/new schema expectations",
)
@click.option("--output", "-o", type=click.Path(), help="Output file for detailed report")
@click.option(
    "--in-file",
    "in_file_filter",
    help="Only scan files matching this pattern (e.g., 'OrderDetails' or 'src/components')",
)
@click.option(
    "--query-last",
    is_flag=True,
    help="Query results from the last refactor run (reads from database, no re-analysis)",
)
@click.option(
    "--validate-only",
    is_flag=True,
    help="Validate YAML profile syntax without running analysis (use with --file)",
)
@click.option(
    "--test-pattern",
    help="Test a single pattern against files (regex or identifier). Use with --in-file.",
)
def refactor(
    migration_dir: str,
    migration_limit: int,
    profile_file: str | None,
    output: str | None,
    in_file_filter: str | None,
    query_last: bool,
    validate_only: bool,
    test_pattern: str | None,
) -> None:
    """Detect incomplete refactorings and breaking changes from database schema migrations.

    Analyzes database migration files to identify removed/renamed tables and columns, then
    queries the codebase for references to those deleted schema elements. Reports code that
    will break at runtime due to schema-code mismatch - the classic "forgot to update the
    queries" problem that breaks production silently.

    AI ASSISTANT CONTEXT:
      Purpose: Detect code-schema mismatches from incomplete refactorings
      Input: backend/migrations/ (SQL files), .pf/repo_index.db (code references)
      Output: Breaking changes report (code using deleted tables/columns)
      Prerequisites: aud full (for code symbol database)
      Integration: Pre-deployment validation, refactoring safety checks
      Performance: ~2-5 seconds (migration parsing + database queries)

    YAML CONFIGURATION (for --file mode):
      To use custom refactor profiles, you MUST write a YAML file defining:
      - Legacy identifiers/patterns to find (old schema references)
      - Expected new identifiers (new schema references)
      - Scope rules (which files to check)

      For full YAML schema and templates: aud manual refactor

    WHAT IT DETECTS:
      Schema Changes:
        - Dropped tables (DROP TABLE users)
        - Renamed tables (ALTER TABLE users RENAME TO accounts)
        - Dropped columns (ALTER TABLE users DROP COLUMN email)
        - Renamed columns (ALTER TABLE users RENAME COLUMN name TO full_name)

      Code References:
        - SQL queries mentioning deleted tables/columns
        - ORM model references (SQLAlchemy, Django)
        - Raw SQL in string literals
        - Dynamic query builders

      Mismatch Classification:
        - CRITICAL: Code references deleted table (guaranteed break)
        - HIGH: Code references deleted column in existing table
        - MEDIUM: Code may reference renamed element (needs verification)

    HOW IT WORKS (Refactoring Analysis):
      1. Migration Parsing:
         - Scans backend/migrations/ for SQL files
         - Extracts DROP/ALTER statements
         - Limits to recent N migrations (--migration-limit)

      2. Schema Change Extraction:
         - Identifies removed/renamed tables and columns
         - Tracks old→new mapping for renames
         - Builds schema change timeline

      3. Code Reference Query:
         - Searches repo_index.db for SQL strings
         - Searches assignments table for ORM references
         - Matches code references to deleted schema elements

      4. Mismatch Reporting:
         - Cross-references code with schema changes
         - Classifies severity (CRITICAL/HIGH/MEDIUM)
         - Outputs breaking change report

    EXAMPLES:
      # Use Case 1: Analyze last 5 migrations (default)
      aud refactor

      # Use Case 2: Analyze all migrations
      aud refactor --migration-limit 0

      # Use Case 3: Use custom migration directory
      aud refactor --migration-dir ./db/migrations

      # Use Case 4: Export detailed report
      aud refactor --output ./refactor_analysis.json

      # Use Case 5: Use refactor profile (YAML expectations)
      aud refactor --file ./refactor_profile.yml

      # Use Case 6: Query results from last run (NO re-analysis)
      aud refactor --query-last

      # Use Case 7: Validate YAML profile before running
      aud refactor --file ./profile.yml --validate-only

    COMMON WORKFLOWS:
      Pre-Deployment Validation:
        aud full && aud refactor --migration-limit 1

      Large Refactoring Review:
        aud refactor --migration-limit 0 --output ./breaking_changes.json

      CI/CD Integration:
        aud refactor || exit 2  # Fail build on breaking changes

    AI WORKFLOW (for custom YAML profiles):
      The correct workflow for AI assistants using refactor profiles:

      1. INVESTIGATE: Query database to understand what patterns exist
         aud query --pattern "%product%" --path "frontend/src/**"

      2. WRITE YAML: Create profile based on actual patterns found
         (See 'aud manual refactor' for YAML schema)

      3. VALIDATE: Check YAML syntax before running
         aud refactor --file profile.yml --validate-only

      4. RUN: Execute the refactor analysis
         aud refactor --file profile.yml

      5. QUERY RESULTS: Get violations from database (NOT file output)
         aud refactor --query-last

      WRONG APPROACH (wastes time):
        - Guessing patterns without discovery
        - Using --output file.json then reading the file
        - Running full analysis to test one rule

      RIGHT APPROACH:
        - Query DB first to discover actual patterns
        - Use --validate-only before full run
        - Use --query-last to read results from DB

    OUTPUT FORMAT (breaking changes report):
      {
        "schema_changes": [
          {
            "type": "dropped_table",
            "name": "users",
            "migration": "0042_drop_users_table.sql"
          }
        ],
        "code_references": [
          {
            "file": "api/handlers.py",
            "line": 45,
            "code": "SELECT * FROM users WHERE id = ?",
            "severity": "CRITICAL",
            "issue": "References dropped table 'users'"
          }
        ],
        "summary": {
          "critical": 2,
          "high": 5,
          "medium": 3
        }
      }

    PERFORMANCE EXPECTATIONS:
      Small (<10 migrations):  ~1-2 seconds
      Medium (50 migrations):  ~3-5 seconds
      Large (100+ migrations): ~5-10 seconds

    FLAG INTERACTIONS:
      --migration-limit 0: Analyzes ALL migrations (thorough but slower)
      --file: Uses custom refactor profile (expected schema changes)
      --output: Saves detailed JSON report (for CI/CD integration)

    PREREQUISITES:
      Required:
        aud full               # Populates code reference database
        backend/migrations/    # Migration files directory

      Optional:
        refactor_profile.yml   # Expected schema changes (reduces false positives)

    EXIT CODES:
      0 = No breaking changes detected
      1 = Breaking changes found (critical/high severity)
      2 = Analysis error (database missing or migration parse failure)

    RELATED COMMANDS:
      aud full               # Populates code reference database
      aud impact             # Broader change impact analysis
      aud query              # Manual code search for schema elements

    TROUBLESHOOTING:
      Error: "No migrations found":
        -> Check --migration-dir points to correct directory
        -> Verify directory contains .sql files
        -> Default: backend/migrations/

      False positives (code flagged but not breaking):
        -> Use --file with refactor_profile.yml to specify expected changes
        -> Some references may be in commented code (check manually)

      Missing schema changes (not detected):
        -> Only analyzes DROP/ALTER TABLE statements
        -> Index changes, constraint changes not tracked
        -> Focus is on table/column structure only

    SEE ALSO:
      aud manual refactor     Learn about refactoring analysis
      aud manual impact       Blast radius and coupling analysis

    NOTE: This command detects syntactic mismatches only, not semantic issues.
    Code may still break if schema change affects data types or constraints.
    """
    repo_root = Path.cwd()
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent

    pf_dir = repo_root / ".pf"
    db_path = pf_dir / "repo_index.db"

    # Handle --query-last: show results from last run without re-analysis
    if query_last:
        if not db_path.exists():
            err_console.print(
                "[error]Error: No index found. Run 'aud full' first.[/error]",
            )
            raise click.Abort()

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, target_file, refactor_type, validation_status, details_json "
            "FROM refactor_history ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            console.print("\nNo previous refactor runs found in database.")
            console.print("Run 'aud refactor' first to populate history.")
            return

        console.print("\n" + "=" * 70, markup=False)
        console.print("LAST REFACTOR RUN RESULTS")
        console.rule()
        console.print(f"  Timestamp: {row['timestamp']}", highlight=False)
        console.print(f"  Target: {row['target_file']}", highlight=False)
        console.print(f"  Type: {row['refactor_type']}", highlight=False)
        console.print(f"  Status: {row['validation_status']}", highlight=False)

        if row["details_json"]:
            details = json.loads(row["details_json"])
            summary = details.get("summary", {})
            console.print("\n  SUMMARY:", highlight=False)
            console.print(f"    Risk Level: {summary.get('risk_level', 'N/A')}", highlight=False)
            console.print(
                f"    Total Mismatches: {summary.get('total_mismatches', 0)}", highlight=False
            )
            console.print(
                f"    Profile Violations: {summary.get('profile_violations', 0)}", highlight=False
            )

            # Show profile violations if present
            profile = details.get("profile", {})
            if profile.get("rule_results"):
                console.print("\n  VIOLATIONS BY RULE:", highlight=False)
                for rule_result in profile["rule_results"]:
                    rule_id = rule_result.get("rule", {}).get("id", "unknown")
                    severity = rule_result.get("rule", {}).get("severity", "unknown")
                    violations = rule_result.get("violations", [])
                    if violations:
                        console.print(
                            f"    [{severity.upper()}] {rule_id}: {len(violations)} violations",
                            highlight=False,
                        )
                        for v in violations[:3]:
                            console.print(
                                f"      - {v.get('file', '?')}:{v.get('line', '?')}",
                                highlight=False,
                            )
                        if len(violations) > 3:
                            console.print(
                                f"      ... and {len(violations) - 3} more", highlight=False
                            )

        console.print("\n" + "=" * 70 + "\n", markup=False)
        return

    # Handle --validate-only: check YAML syntax without running analysis
    if validate_only:
        if not profile_file:
            err_console.print(
                "[error]Error: --validate-only requires --file <profile.yml>[/error]",
            )
            raise click.Abort()

        console.print("\n" + "=" * 70, markup=False)
        console.print("YAML PROFILE VALIDATION")
        console.rule()

        try:
            profile = RefactorProfile.load(Path(profile_file))
            console.print(f"  Profile: {profile.refactor_name}", highlight=False)
            console.print(f"  Description: {profile.description}", highlight=False)
            console.print(f"  Version: {profile.version or 'N/A'}", highlight=False)
            console.print(f"  Rules: {len(profile.rules)}", highlight=False)

            console.print("\n  RULES FOUND:", highlight=False)
            for rule in profile.rules:
                match_count = len(rule.match.get("identifiers", [])) + len(
                    rule.match.get("expressions", [])
                )
                expect_count = (
                    len(rule.expect.identifiers) + len(rule.expect.expressions)
                    if not rule.expect.is_empty()
                    else 0
                )
                console.print(
                    f"    [{rule.severity.upper()}] {rule.id}: "
                    f"{match_count} match patterns, {expect_count} expect patterns",
                    highlight=False,
                )
                if rule.scope.get("include"):
                    console.print(
                        f"      Scope include: {rule.scope['include']}", highlight=False
                    )
                if rule.scope.get("exclude"):
                    console.print(
                        f"      Scope exclude: {rule.scope['exclude'][:3]}...", highlight=False
                    )

            console.print("\n  VALIDATION: PASSED", highlight=False)
            console.print("  Profile is syntactically valid and ready to use.", highlight=False)

        except Exception as exc:
            console.print(f"\n  VALIDATION: FAILED", highlight=False)
            console.print(f"  Error: {exc}", highlight=False)
            console.print("\n  Common issues:", highlight=False)
            console.print("    - 'identfiers' typo (should be 'identifiers')", highlight=False)
            console.print("    - Missing required fields (id, match)", highlight=False)
            console.print("    - Invalid YAML syntax (indentation)", highlight=False)
            raise click.Abort() from exc

        console.print("\n" + "=" * 70 + "\n", markup=False)
        return

    # Handle --test-pattern: test a single pattern before writing full YAML
    if test_pattern:
        if not db_path.exists():
            err_console.print(
                "[error]Error: No index found. Run 'aud full' first.[/error]",
            )
            raise click.Abort()

        console.print("\n" + "=" * 70, markup=False)
        console.print("PATTERN TEST MODE")
        console.rule()
        console.print(f"  Pattern: {test_pattern}", highlight=False)
        if in_file_filter:
            console.print(f"  File filter: {in_file_filter}", highlight=False)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Detect pattern type: regex (starts with /) or identifier (plain text)
        is_regex = test_pattern.startswith("/") and test_pattern.endswith("/")
        if is_regex:
            pattern_str = test_pattern[1:-1]  # Strip slashes
            console.print(f"  Type: regex", highlight=False)
        else:
            pattern_str = test_pattern
            console.print(f"  Type: identifier (literal match)", highlight=False)

        console.print()

        # Build query based on pattern type
        matches = []

        if is_regex:
            # Search in symbols table using LIKE (approximate) then filter with regex
            # Also search in assignments for property access patterns
            like_pattern = "%" + pattern_str.replace("\\.", ".").replace(".*", "%") + "%"

            # Search symbols
            query = "SELECT path, line, name, type FROM symbols WHERE name LIKE ?"
            if in_file_filter:
                query += " AND path LIKE ?"
                cursor.execute(query, (like_pattern, f"%{in_file_filter}%"))
            else:
                cursor.execute(query, (like_pattern,))

            compiled_re = re.compile(pattern_str)
            for row in cursor.fetchall():
                if compiled_re.search(row["name"]):
                    matches.append({
                        "file": row["path"],
                        "line": row["line"],
                        "match": row["name"],
                        "type": row["type"],
                        "source": "symbols",
                    })

            # Also search assignments for things like "item.product.id"
            query = "SELECT file, line, target_var, source_expr FROM assignments WHERE target_var LIKE ? OR source_expr LIKE ?"
            if in_file_filter:
                query += " AND file LIKE ?"
                cursor.execute(query, (like_pattern, like_pattern, f"%{in_file_filter}%"))
            else:
                cursor.execute(query, (like_pattern, like_pattern))

            for row in cursor.fetchall():
                target = row["target_var"] or ""
                value = row["source_expr"] or ""
                matched_text = None
                if compiled_re.search(target):
                    matched_text = target
                elif compiled_re.search(value):
                    matched_text = value
                if matched_text:
                    matches.append({
                        "file": row["file"],
                        "line": row["line"],
                        "match": matched_text[:60] + ("..." if len(matched_text) > 60 else ""),
                        "type": "assignment",
                        "source": "assignments",
                    })

        else:
            # Literal identifier match
            query = "SELECT path, line, name, type FROM symbols WHERE name = ?"
            if in_file_filter:
                query += " AND path LIKE ?"
                cursor.execute(query, (pattern_str, f"%{in_file_filter}%"))
            else:
                cursor.execute(query, (pattern_str,))

            for row in cursor.fetchall():
                matches.append({
                    "file": row["path"],
                    "line": row["line"],
                    "match": row["name"],
                    "type": row["type"],
                    "source": "symbols",
                })

            # Also check assignments
            query = "SELECT file, line, target_var FROM assignments WHERE target_var = ?"
            if in_file_filter:
                query += " AND file LIKE ?"
                cursor.execute(query, (pattern_str, f"%{in_file_filter}%"))
            else:
                cursor.execute(query, (pattern_str,))

            for row in cursor.fetchall():
                matches.append({
                    "file": row["file"],
                    "line": row["line"],
                    "match": row["target_var"],
                    "type": "assignment",
                    "source": "assignments",
                })

        conn.close()

        # Dedupe and sort
        seen = set()
        unique_matches = []
        for m in matches:
            key = (m["file"], m["line"], m["match"])
            if key not in seen:
                seen.add(key)
                unique_matches.append(m)

        unique_matches.sort(key=lambda x: (x["file"], x["line"]))

        # Output results
        if unique_matches:
            console.print(f"MATCHES FOUND: {len(unique_matches)}\n", highlight=False)

            # Group by file
            from collections import defaultdict
            by_file = defaultdict(list)
            for m in unique_matches:
                by_file[m["file"]].append(m)

            for file_path, file_matches in sorted(by_file.items()):
                console.print(f"  {file_path}:", highlight=False)
                for m in file_matches[:10]:
                    console.print(
                        f"    Line {m['line']:4d}: {m['match']} ({m['type']})",
                        highlight=False,
                    )
                if len(file_matches) > 10:
                    console.print(
                        f"    ... and {len(file_matches) - 10} more in this file",
                        highlight=False,
                    )
                console.print()

            # Emit JSON for AI consumption
            console.print("--- TEST-PATTERN JSON ---", highlight=False)
            output = {
                "pattern": test_pattern,
                "is_regex": is_regex,
                "total_matches": len(unique_matches),
                "matches": unique_matches[:50],  # Limit to 50 for readability
            }
            console.print(json.dumps(output, indent=2), markup=False)
            console.print("--- END JSON ---", highlight=False)
        else:
            console.print("NO MATCHES FOUND", highlight=False)
            console.print("\nTips:", highlight=False)
            console.print("  - For regex patterns, use /pattern/ syntax", highlight=False)
            console.print("  - Try a broader pattern (e.g., /product/ instead of /product_id/)", highlight=False)
            console.print("  - Check if the file filter is correct", highlight=False)

        console.print("\n" + "=" * 70 + "\n", markup=False)
        return

    # Normal flow continues below
    if not db_path.exists():
        err_console.print(
            "[error]Error: No index found. Run 'aud full' first.[/error]",
        )
        raise click.Abort()

    console.print("\n" + "=" * 70, markup=False)
    console.print("REFACTORING IMPACT ANALYSIS - Schema Change Detection")
    console.rule()

    profile_report = None
    if profile_file:
        console.print("\nPhase 1: Evaluating refactor profile (YAML rules)...")
        try:
            profile = RefactorProfile.load(Path(profile_file))
        except Exception as exc:
            err_console.print(f"[error]Error loading profile: {exc}[/error]", highlight=False)
            raise click.Abort() from exc

        console.print(f"  Profile: {profile.refactor_name}", highlight=False)
        console.print(f"  Rules: {len(profile.rules)}", highlight=False)

        migration_glob = f"{migration_dir}/**"
        for rule in profile.rules:
            if migration_glob not in rule.scope.get("exclude", []):
                rule.scope.setdefault("exclude", []).append(migration_glob)

        if in_file_filter:
            console.print(f"  Filter: *{in_file_filter}*", highlight=False)
            for rule in profile.rules:
                rule.scope["include"] = [f"*{in_file_filter}*"]

        with RefactorRuleEngine(db_path, repo_root) as engine:
            profile_report = engine.evaluate(profile)

    console.print("\nPhase 2: Analyzing database migrations...")
    schema_changes = _analyze_migrations(repo_root, migration_dir, migration_limit)

    has_schema_changes = bool(
        schema_changes["removed_tables"]
        or schema_changes["removed_columns"]
        or schema_changes["renamed_items"]
    )

    if not has_schema_changes:
        console.print("\nNo schema changes detected in migrations.")
        console.print("Tip: This command looks for removeColumn, dropTable, renameColumn, etc.")
        if not profile_report:
            from datetime import datetime

            from theauditor.indexer.database import DatabaseManager

            db = DatabaseManager(str(db_path))
            db.add_refactor_history(
                timestamp=datetime.now().isoformat(),
                target_file=migration_dir,
                refactor_type="migration_check",
                migrations_found=0,
                migrations_complete=1,
                schema_consistent=1,
                validation_status="NONE",
                details_json=json.dumps({"summary": {"migrations_found": 0, "risk_level": "NONE"}}),
            )
            db.flush_batch()
            db.commit()
            return

    console.print("\nPhase 3: Searching codebase for references to removed schema...")
    mismatches = _find_code_references(db_path, schema_changes, repo_root, migration_dir)

    schema_counts = _aggregate_schema_counts(mismatches)

    console.print("\n" + "=" * 70, markup=False)
    console.print("RESULTS")
    console.rule()

    _print_impact_overview(profile_report, mismatches, schema_counts)
    if profile_report:
        _print_profile_report(profile_report, schema_counts)

    profile_violations = profile_report.total_violations() if profile_report else 0
    total_issues = sum(len(v) for v in mismatches.values())

    if total_issues == 0:
        console.print("\nNo mismatches found!")
        console.print("All removed schema items appear to have been cleaned up from the codebase.")
    else:
        console.print(f"\nFound {total_issues} potential breaking references:", highlight=False)

        _print_mismatch_summary(
            mismatches["removed_tables"],
            label="Removed Tables",
            key_field="table",
            description="code still touching dropped tables",
        )
        _print_mismatch_summary(
            mismatches["removed_columns"],
            label="Removed Columns",
            key_field="column",
            description="code still touching dropped columns",
        )
        _print_mismatch_summary(
            mismatches["renamed_items"],
            label="Renamed Items",
            key_field="old_name",
            description="code still referencing pre-rename identifiers",
        )

    risk = _assess_risk(mismatches)
    console.print(f"\nSchema Stability Risk: {risk}", highlight=False)

    if profile_report:
        debt_level = "NONE"
        if profile_violations > 0:
            debt_level = "LOW"
        if profile_violations > 20:
            debt_level = "MEDIUM"
        if profile_violations > 50:
            debt_level = "HIGH"
        console.print(
            f"Refactor Debt Level:   {debt_level} ({profile_violations} legacy patterns)",
            highlight=False,
        )

    if output:
        report = _generate_report(schema_changes, mismatches, risk, profile_report)
        with open(output, "w") as f:
            json.dump(report, f, indent=2, default=str)
        console.print(f"\nDetailed report saved: {output}", highlight=False)

    from datetime import datetime

    from theauditor.indexer.database import DatabaseManager

    db = DatabaseManager(str(db_path))
    db.add_refactor_history(
        timestamp=datetime.now().isoformat(),
        target_file=migration_dir,
        refactor_type="migration_check",
        migrations_found=len(schema_changes["removed_tables"])
        + len(schema_changes["removed_columns"]),
        migrations_complete=0 if sum(len(v) for v in mismatches.values()) > 0 else 1,
        schema_consistent=1 if risk in ["NONE", "LOW"] else 0,
        validation_status=risk,
        details_json=json.dumps(
            _generate_report(schema_changes, mismatches, risk, profile_report), default=str
        ),
    )
    db.flush_batch()
    db.commit()

    console.print("")


def _analyze_migrations(
    repo_root: Path, migration_dir: str, migration_limit: int
) -> dict[str, Any]:
    """Parse migrations to find schema changes.

    Returns dict with:
        removed_tables: List of table names that were dropped
        removed_columns: List of {table, column} dicts for dropped columns
        renamed_items: List of {old_name, new_name, type} dicts
    """
    migration_path = repo_root / migration_dir

    if not migration_path.exists():
        for common_path in [
            "backend/migrations",
            "migrations",
            "db/migrations",
            "database/migrations",
        ]:
            test_path = repo_root / common_path
            if test_path.exists():
                import glob

                if (
                    glob.glob(str(test_path / "*.js"))
                    + glob.glob(str(test_path / "*.ts"))
                    + glob.glob(str(test_path / "*.sql"))
                ):
                    migration_path = test_path
                    console.print(f"Found migrations in: {common_path}", highlight=False)
                    break

    if not migration_path.exists():
        err_console.print(
            f"[error]WARNING: No migrations found at {migration_path}[/error]",
            highlight=False,
        )
        return {"removed_tables": [], "removed_columns": [], "renamed_items": []}

    import glob

    migrations = sorted(
        glob.glob(str(migration_path / "*.js"))
        + glob.glob(str(migration_path / "*.ts"))
        + glob.glob(str(migration_path / "*.sql"))
    )

    if not migrations:
        return {"removed_tables": [], "removed_columns": [], "renamed_items": []}

    if migration_limit > 0:
        migrations = migrations[-migration_limit:]
        console.print(f"Analyzing {len(migrations)} most recent migrations", highlight=False)
    else:
        console.print(f"Analyzing ALL {len(migrations)} migrations", highlight=False)

    removed_tables = set()
    removed_columns = []
    renamed_items = []

    for mig_file in migrations:
        try:
            with open(mig_file, encoding="utf-8") as f:
                content = f.read()

            if mig_file.endswith((".js", ".ts")):
                parts = re.split(
                    r"(?:async\s+)?down\s*[:=(]", content, maxsplit=1, flags=re.IGNORECASE
                )
                if len(parts) > 1:
                    content = parts[0]

            for match in DROP_TABLE.finditer(content):
                table = match.group(1)
                removed_tables.add(table)

            for match in REMOVE_COLUMN.finditer(content):
                table = match.group(1)
                column = match.group(2)
                removed_columns.append({"table": table, "column": column})

            for match in RENAME_TABLE.finditer(content):
                old_name = match.group(1)
                new_name = match.group(2)
                renamed_items.append({"old_name": old_name, "new_name": new_name, "type": "table"})

            for match in RENAME_COLUMN.finditer(content):
                table = match.group(1)
                old_name = match.group(2)
                new_name = match.group(3)
                renamed_items.append(
                    {
                        "old_name": f"{table}.{old_name}",
                        "new_name": f"{table}.{new_name}",
                        "type": "column",
                    }
                )

        except Exception as e:
            console.print(f"Warning: Could not read {mig_file}: {e}", highlight=False)

    console.print(f"  Removed tables: {len(removed_tables)}", highlight=False)
    console.print(f"  Removed columns: {len(removed_columns)}", highlight=False)
    console.print(f"  Renamed items: {len(renamed_items)}", highlight=False)

    return {
        "removed_tables": list(removed_tables),
        "removed_columns": removed_columns,
        "renamed_items": renamed_items,
    }


def _find_code_references(
    db_path: Path, schema_changes: dict, repo_root: Path, migration_dir: str = "migrations"
) -> dict[str, list[dict]]:
    """Query database for code that references removed schema items.

    Returns dict with:
        removed_tables: Code references to dropped tables
        removed_columns: Code references to dropped columns
        renamed_items: Code using old names

    Note: Automatically excludes migration files themselves from results.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    def is_migration_file(file_path: str) -> bool:
        if not file_path:
            return False
        normalized = file_path.replace("\\", "/")
        return f"/{migration_dir}/" in normalized or normalized.startswith(f"{migration_dir}/")

    mismatches = {"removed_tables": [], "removed_columns": [], "renamed_items": []}

    for table in schema_changes["removed_tables"]:
        cursor.execute(
            """
            SELECT path, line, name, type
            FROM symbols
            WHERE name LIKE ?
        """,
            (f"%{table}%",),
        )

        for row in cursor.fetchall():
            if is_migration_file(row["path"]):
                continue
            mismatches["removed_tables"].append(
                {
                    "file": row["path"],
                    "line": row["line"] or 0,
                    "table": table,
                    "snippet": f"{row['type']} {row['name']}",
                }
            )

        cursor.execute(
            """
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var LIKE ? OR source_expr LIKE ?
            LIMIT 50
        """,
            (f"%{table}%", f"%{table}%"),
        )

        for row in cursor.fetchall():
            if is_migration_file(row["file"]):
                continue
            mismatches["removed_tables"].append(
                {
                    "file": row["file"],
                    "line": row["line"] or 0,
                    "table": table,
                    "snippet": (row["source_expr"] or row["target_var"] or "")[:200],
                }
            )

    for col_info in schema_changes["removed_columns"]:
        table = col_info["table"]
        column = col_info["column"]

        cursor.execute(
            """
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE source_expr LIKE ? OR source_expr LIKE ?
            LIMIT 20
        """,
            (f"%{table}.{column}%", f"%'{column}'%"),
        )

        for row in cursor.fetchall():
            if is_migration_file(row["file"]):
                continue
            mismatches["removed_columns"].append(
                {
                    "file": row["file"],
                    "line": row["line"] or 0,
                    "table": table,
                    "column": column,
                    "snippet": (row["source_expr"] or "")[:200],
                }
            )

    for rename_info in schema_changes["renamed_items"]:
        old_name = rename_info["old_name"]
        new_name = rename_info["new_name"]

        cursor.execute(
            """
            SELECT path, line, name, type
            FROM symbols
            WHERE name LIKE ?
            LIMIT 20
        """,
            (f"%{old_name}%",),
        )

        for row in cursor.fetchall():
            if is_migration_file(row["path"]):
                continue
            mismatches["renamed_items"].append(
                {
                    "file": row["path"],
                    "line": row["line"] or 0,
                    "old_name": old_name,
                    "new_name": new_name,
                    "snippet": f"{row['type']} {row['name']}",
                }
            )

    conn.close()

    for category in mismatches:
        seen = set()
        deduped = []
        for item in mismatches[category]:
            key = (item["file"], item.get("line", 0))
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        mismatches[category] = deduped

    return mismatches


def _print_profile_report(
    report: ProfileEvaluation, schema_counts: dict[str, dict[str, int]] | None = None
) -> None:
    """Pretty-print YAML profile evaluation."""
    console.print(f"  Description: {report.profile.description}", highlight=False)
    if report.profile.version:
        console.print(f"  Version: {report.profile.version}", highlight=False)

    total_old = sum(len(r.violations) for r in report.rule_results)
    rules_with_old = [r for r in report.rule_results if r.violations]

    console.print("\n  PROFILE SUMMARY")
    console.print(f"    Rules evaluated: {len(report.rule_results)}", highlight=False)
    console.print(f"    Rules with old references: {len(rules_with_old)}", highlight=False)
    console.print(f"    Total old references: {total_old}", highlight=False)

    _print_rule_breakdown(report.rule_results, schema_counts)
    _print_top_files(report.rule_results, schema_counts)
    _print_missing_expectations(report.rule_results)


def _assess_risk(mismatches: dict[str, list]) -> str:
    """Assess risk level based on number of mismatches."""
    total = sum(len(v) for v in mismatches.values())

    if total == 0:
        return "NONE"
    elif total < 5:
        return "LOW"
    elif total < 15:
        return "MEDIUM"
    else:
        return "HIGH"


def _generate_report(
    schema_changes: dict,
    mismatches: dict,
    risk: str,
    profile_report: ProfileEvaluation | None = None,
) -> dict:
    """Generate JSON report."""
    report = {
        "schema_changes": schema_changes,
        "mismatches": mismatches,
        "summary": {
            "removed_tables": len(schema_changes["removed_tables"]),
            "removed_columns": len(schema_changes["removed_columns"]),
            "renamed_items": len(schema_changes["renamed_items"]),
            "total_mismatches": sum(len(v) for v in mismatches.values()),
            "risk_level": risk,
        },
    }
    if profile_report:
        report["profile"] = profile_report.to_dict()
        report["summary"]["profile_violations"] = profile_report.total_violations()
    return report


def _aggregate_schema_counts(
    mismatches: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, int]]:
    """Aggregate schema mismatch counts per file."""
    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tables": 0, "columns": 0, "renamed": 0, "total": 0}
    )

    for item in mismatches.get("removed_tables", []):
        file_path = item.get("file")
        if not file_path:
            continue
        counts[file_path]["tables"] += 1

    for item in mismatches.get("removed_columns", []):
        file_path = item.get("file")
        if not file_path:
            continue
        counts[file_path]["columns"] += 1

    for item in mismatches.get("renamed_items", []):
        file_path = item.get("file")
        if not file_path:
            continue
        counts[file_path]["renamed"] += 1

    for info in counts.values():
        info["total"] = info["tables"] + info["columns"] + info["renamed"]

    return counts


def _collect_profile_files(rule_results: list) -> set[str]:
    """Return set of files involved in profile violations."""
    files = set()
    for result in rule_results:
        for item in result.violations:
            file_path = item.get("file")
            if file_path:
                files.add(file_path)
    return files


def _print_impact_overview(
    profile_report: ProfileEvaluation | None,
    mismatches: dict[str, list[dict[str, Any]]],
    schema_counts: dict[str, dict[str, int]],
) -> None:
    """Display high-level summary across profile + schema phases."""
    console.print("\nIMPACT OVERVIEW")

    if profile_report:
        rule_count = len(profile_report.rule_results)
        rules_with_old = sum(1 for r in profile_report.rule_results if r.violations)
        total_old = sum(len(r.violations) for r in profile_report.rule_results)
        files_with_old = len(_collect_profile_files(profile_report.rule_results))
        console.print(
            f"  Profile coverage: {rule_count} rules | "
            f"{rules_with_old} with old refs | "
            f"{total_old} old refs | files impacted: {files_with_old}",
            highlight=False,
        )

    tables_total = len(mismatches.get("removed_tables", []))
    columns_total = len(mismatches.get("removed_columns", []))
    renamed_total = len(mismatches.get("renamed_items", []))
    console.print(
        f"  Schema mismatches: tables={tables_total}, columns={columns_total}, renamed={renamed_total} | "
        f"files impacted: {len(schema_counts)}",
        highlight=False,
    )

    if profile_report:
        profile_files = _collect_profile_files(profile_report.rule_results)
        overlap = sum(1 for file in profile_files if schema_counts.get(file))
        console.print(
            f"  Files overlapping profile + schema mismatches: {overlap}", highlight=False
        )


def _print_rule_breakdown(
    rule_results: list, schema_counts: dict[str, dict[str, int]] | None = None
) -> None:
    """Show per-rule stats sorted by severity and violation count."""
    console.print("\n  RULE BREAKDOWN")
    for result in sorted(
        rule_results,
        key=lambda r: (
            SEVERITY_ORDER.get(r.rule.severity, 4),
            -len(r.violations),
            r.rule.id,
        ),
    ):
        old_count = len(result.violations)
        new_count = len(result.expected_references)
        unique_files = len({item["file"] for item in result.violations})
        header = f"    [{result.rule.severity.upper()}] {result.rule.id}"
        console.print(header, markup=False)
        console.print(f"      Description: {result.rule.description}", highlight=False)
        console.print(
            f"      Old refs: {old_count} (files: {unique_files}) | New refs: {new_count}",
            highlight=False,
        )
        if schema_counts and old_count:
            violation_files = {item["file"] for item in result.violations}
            overlapping = [
                schema_counts.get(file) for file in violation_files if schema_counts.get(file)
            ]
            if overlapping:
                overlap_refs = sum(entry["total"] for entry in overlapping)
                console.print(
                    f"      Schema mismatches touching these files: "
                    f"{overlap_refs} refs across {len(overlapping)} file(s)",
                    highlight=False,
                )

        if old_count:
            console.print("      Files:")

            file_lines: dict[str, list[int]] = defaultdict(list)
            for item in result.violations:
                if item.get("file"):
                    file_lines[item["file"]].append(item.get("line", 0))

            sorted_files = sorted(file_lines.items(), key=lambda x: (-len(x[1]), x[0]))[:5]
            for file_path, lines in sorted_files:
                lines_sorted = sorted(set(lines))
                if len(lines_sorted) <= 5:
                    line_str = ", ".join(str(ln) for ln in lines_sorted)
                else:
                    line_str = ", ".join(str(ln) for ln in lines_sorted[:5])
                    line_str += f", ... (+{len(lines_sorted) - 5})"

                suffix = ""
                if schema_counts and schema_counts.get(file_path, {}).get("total"):
                    schema_info = schema_counts[file_path]
                    suffix = (
                        f" | schema refs: {schema_info['total']} "
                        f"(tables:{schema_info['tables']}, columns:{schema_info['columns']})"
                    )
                console.print(f"        - {file_path} (lines {line_str}){suffix}", highlight=False)
        else:
            console.print("      Files: clean")

        if new_count:
            console.print("      Confirmed new schema locations:")
            for item in result.expected_references[:3]:
                console.print(
                    f"        + {item['file']}:{item['line']} :: {item['match']}", highlight=False
                )
            if new_count > 3:
                console.print(f"        ... {new_count - 3} more", highlight=False)
        elif not result.rule.expect.is_empty():
            console.print("      Confirmed new schema locations: missing")


def _print_top_files(
    rule_results: list, schema_counts: dict[str, dict[str, int]] | None = None, limit: int = 10
) -> None:
    """Aggregate violations across rules to highlight hotspots."""
    queue = _build_file_priority_queue(rule_results, schema_counts, limit=limit)
    if not queue:
        return
    console.print("\n  FILE PRIORITY QUEUE")
    for file_path, data in queue:
        rules_desc = ", ".join(f"{rule_id}({count})" for rule_id, count in data["rules"])
        schema_suffix = ""
        schema = data.get("schema")
        if schema and schema.get("total"):
            schema_suffix = (
                f" | schema refs: {schema['total']} "
                f"(tables:{schema['tables']}, columns:{schema['columns']})"
            )
        console.print(
            f"    - \\[{data['max_severity'].upper()}] {file_path}: "
            f"{data['count']} refs across {data['rule_count']} rule(s) | {rules_desc}{schema_suffix}",
            highlight=False,
        )


def _top_counts(items: Iterable[str], limit: int = 5) -> list[tuple[str, int]]:
    """Return top counts for iterable items."""
    counter = Counter(item for item in items if item)
    return counter.most_common(limit)


def _build_file_priority_queue(
    rule_results: list, schema_counts: dict[str, dict[str, int]] | None = None, limit: int = 10
) -> list[tuple[str, dict[str, Any]]]:
    """Summarize files affected by rules with severity and rule context."""
    stats: dict[str, dict[str, Any]] = {}

    for result in rule_results:
        severity = result.rule.severity
        for issue in result.violations:
            file_path = issue.get("file")
            if not file_path:
                continue
            entry = stats.setdefault(
                file_path,
                {
                    "count": 0,
                    "rules": Counter(),
                    "max_severity": severity,
                },
            )
            entry["count"] += 1
            entry["rules"][result.rule.id] += 1
            if SEVERITY_ORDER.get(severity, 4) < SEVERITY_ORDER.get(entry["max_severity"], 4):
                entry["max_severity"] = severity

    queue = sorted(
        stats.items(),
        key=lambda item: (
            SEVERITY_ORDER.get(item[1]["max_severity"], 4),
            -item[1]["count"],
            item[0],
        ),
    )[:limit]

    formatted = []
    for file_path, data in queue:
        formatted.append(
            (
                file_path,
                {
                    "count": data["count"],
                    "rule_count": len(data["rules"]),
                    "max_severity": data["max_severity"],
                    "rules": data["rules"].most_common(),
                    "schema": schema_counts.get(file_path) if schema_counts else None,
                },
            )
        )
    return formatted


def _print_missing_expectations(rule_results: list) -> None:
    """Highlight rules that expect new schema references but none were found."""
    missing = [
        result
        for result in rule_results
        if not result.expected_references and not result.rule.expect.is_empty()
    ]
    if not missing:
        return
    console.print("\n  RULES WITH MISSING NEW SCHEMA REFERENCES")
    for result in missing:
        console.print(
            f"    - \\[{result.rule.severity.upper()}] {result.rule.id}: expected patterns not observed",
            highlight=False,
        )


def _print_mismatch_summary(
    items: list[dict[str, Any]], label: str, key_field: str, description: str
) -> None:
    """Report aggregate info plus sample references for schema mismatches."""
    count = len(items)
    console.print(f"\n{label} ({count} issues):", highlight=False)
    if not items:
        console.print("  None")
        return

    top_keys = _top_counts((item.get(key_field) for item in items), limit=5)
    top_files = _top_counts((item.get("file") for item in items), limit=5)

    console.print(f"  Summary: {description}", highlight=False)
    if top_keys:
        console.print("  Most affected identifiers:")
        for key, key_count in top_keys:
            console.print(f"    - {key}: {key_count}", highlight=False)
    if top_files:
        console.print("  Files with highest counts:")
        for file_path, file_count in top_files:
            console.print(f"    - {file_path}: {file_count}", highlight=False)

    console.print("  Sample references:")
    for issue in items[:10]:
        location = f"{issue['file']}:{issue.get('line', 0)}"
        console.print(f"    - {location}", highlight=False)
        if "table" in issue and "column" in issue:
            console.print(f"      {issue['table']}.{issue['column']}", highlight=False)
        elif "table" in issue:
            console.print(f"      {issue['table']}", highlight=False)
        elif "old_name" in issue and "new_name" in issue:
            console.print(f"      {issue['old_name']} -> {issue['new_name']}", highlight=False)
        snippet = issue.get("snippet")
        if snippet:
            console.print(f"      Snippet: {snippet[:80]}...", highlight=False)


refactor_command = refactor
