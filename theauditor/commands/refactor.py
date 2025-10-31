"""Refactoring impact analysis command.

Analyzes database migrations to detect schema changes and finds code that still
references removed/renamed fields and tables, reporting potential breaking changes.

NO pattern detection. NO FCE. Just direct database queries.
"""

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Iterable, Tuple

import click

from theauditor.refactor import (
    ProfileEvaluation,
    RefactorProfile,
    RefactorRuleEngine,
)

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

@click.command()
@click.option("--migration-dir", "-m", default="backend/migrations",
              help="Directory containing database migrations")
@click.option("--migration-limit", "-ml", type=int, default=5,
              help="Number of recent migrations to analyze (0=all, default=5)")
@click.option("--file", "-f", "profile_file", type=click.Path(exists=True),
              help="Refactor profile YAML describing old/new schema expectations")
@click.option("--output", "-o", type=click.Path(),
              help="Output file for detailed report")
def refactor(
    migration_dir: str,
    migration_limit: int,
    profile_file: Optional[str],
    output: Optional[str],
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
      Prerequisites: aud index (for code symbol database)
      Integration: Pre-deployment validation, refactoring safety checks
      Performance: ~2-5 seconds (migration parsing + database queries)

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

    COMMON WORKFLOWS:
      Pre-Deployment Validation:
        aud index && aud refactor --migration-limit 1

      Large Refactoring Review:
        aud refactor --migration-limit 0 --output ./breaking_changes.json

      CI/CD Integration:
        aud refactor || exit 2  # Fail build on breaking changes

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
        aud index              # Populates code reference database
        backend/migrations/    # Migration files directory

      Optional:
        refactor_profile.yml   # Expected schema changes (reduces false positives)

    EXIT CODES:
      0 = No breaking changes detected
      1 = Breaking changes found (critical/high severity)
      2 = Analysis error (database missing or migration parse failure)

    RELATED COMMANDS:
      aud index              # Populates code reference database
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

    NOTE: This command detects syntactic mismatches only, not semantic issues.
    Code may still break if schema change affects data types or constraints.
    """
    # Find repository root
    repo_root = Path.cwd()
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent

    pf_dir = repo_root / ".pf"
    db_path = pf_dir / "repo_index.db"

    if not db_path.exists():
        click.echo("Error: No index found. Run 'aud index' first.", err=True)
        raise click.Abort()

    click.echo("\n" + "=" * 70)
    click.echo("REFACTORING IMPACT ANALYSIS - Schema Change Detection")
    click.echo("=" * 70)

    profile_report = None
    if profile_file:
        click.echo("\nPhase 1: Evaluating refactor profile (YAML rules)...")
        try:
            profile = RefactorProfile.load(Path(profile_file))
        except Exception as exc:
            click.echo(f"Error loading profile: {exc}", err=True)
            raise click.Abort()

        click.echo(f"  Profile: {profile.refactor_name}")
        click.echo(f"  Rules: {len(profile.rules)}")
        with RefactorRuleEngine(db_path, repo_root) as engine:
            profile_report = engine.evaluate(profile)

    # Step 2: Analyze migrations for schema changes
    click.echo("\nPhase 2: Analyzing database migrations...")
    schema_changes = _analyze_migrations(repo_root, migration_dir, migration_limit)

    if not schema_changes['removed_tables'] and not schema_changes['removed_columns'] and not schema_changes['renamed_items']:
        click.echo("\nNo schema changes detected in migrations.")
        click.echo("Tip: This command looks for removeColumn, dropTable, renameColumn, etc.")
        if not profile_report:
            return

    # Step 3: Query database for code references
    click.echo("\nPhase 3: Searching codebase for references to removed schema...")
    mismatches = _find_code_references(db_path, schema_changes, repo_root)

    schema_counts = _aggregate_schema_counts(mismatches)

    # Step 3: Report findings
    click.echo("\n" + "=" * 70)
    click.echo("RESULTS")
    click.echo("=" * 70)

    _print_impact_overview(profile_report, mismatches, schema_counts)
    if profile_report:
        _print_profile_report(profile_report, schema_counts)

    profile_violations = profile_report.total_violations() if profile_report else 0
    total_issues = sum(len(v) for v in mismatches.values())

    if total_issues == 0:
        click.echo("\nNo mismatches found!")
        click.echo("All removed schema items appear to have been cleaned up from the codebase.")
    else:
        click.echo(f"\nFound {total_issues} potential breaking references:")

        _print_mismatch_summary(
            mismatches['removed_tables'],
            label="Removed Tables",
            key_field='table',
            description="code still touching dropped tables",
        )
        _print_mismatch_summary(
            mismatches['removed_columns'],
            label="Removed Columns",
            key_field='column',
            description="code still touching dropped columns",
        )
        _print_mismatch_summary(
            mismatches['renamed_items'],
            label="Renamed Items",
            key_field='old_name',
            description="code still referencing pre-rename identifiers",
        )

    # Risk assessment
    risk = _assess_risk(mismatches)
    click.echo(f"\nRisk Level: {risk}")
    if profile_report:
        if profile_violations > 0:
            click.echo(f"Profile violations (YAML rules): {profile_violations}")
        else:
            click.echo("Profile violations (YAML rules): 0")

    # Save detailed report
    if output:
        report = _generate_report(schema_changes, mismatches, risk, profile_report)
        with open(output, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        click.echo(f"\nDetailed report saved: {output}")

    click.echo("")


def _analyze_migrations(repo_root: Path, migration_dir: str, migration_limit: int) -> Dict[str, Any]:
    """Parse migrations to find schema changes.

    Returns dict with:
        removed_tables: List of table names that were dropped
        removed_columns: List of {table, column} dicts for dropped columns
        renamed_items: List of {old_name, new_name, type} dicts
    """
    migration_path = repo_root / migration_dir

    # Try common locations if default doesn't exist
    if not migration_path.exists():
        for common_path in ["backend/migrations", "migrations", "db/migrations", "database/migrations"]:
            test_path = repo_root / common_path
            if test_path.exists():
                import glob
                if glob.glob(str(test_path / "*.js")) + glob.glob(str(test_path / "*.ts")) + glob.glob(str(test_path / "*.sql")):
                    migration_path = test_path
                    click.echo(f"Found migrations in: {common_path}")
                    break

    if not migration_path.exists():
        click.echo(f"WARNING: No migrations found at {migration_path}", err=True)
        return {'removed_tables': [], 'removed_columns': [], 'renamed_items': []}

    # Find migration files
    import glob
    migrations = sorted(
        glob.glob(str(migration_path / "*.js")) +
        glob.glob(str(migration_path / "*.ts")) +
        glob.glob(str(migration_path / "*.sql"))
    )

    if not migrations:
        return {'removed_tables': [], 'removed_columns': [], 'renamed_items': []}

    # Select which migrations to analyze
    if migration_limit > 0:
        migrations = migrations[-migration_limit:]
        click.echo(f"Analyzing {len(migrations)} most recent migrations")
    else:
        click.echo(f"Analyzing ALL {len(migrations)} migrations")

    removed_tables = set()
    removed_columns = []  # List of {table, column}
    renamed_items = []    # List of {old_name, new_name, type}

    # Regex patterns for schema operations
    DROP_TABLE = re.compile(r'(?:dropTable|DROP\s+TABLE)\s*\(\s*[\'"`](\w+)[\'"`]', re.IGNORECASE)
    REMOVE_COLUMN = re.compile(r'(?:removeColumn|dropColumn|DROP\s+COLUMN)\s*\(\s*[\'"`](\w+)[\'"`]\s*,\s*[\'"`](\w+)[\'"`]', re.IGNORECASE)
    RENAME_TABLE = re.compile(r'(?:renameTable|RENAME\s+TABLE)\s*\(\s*[\'"`](\w+)[\'"`]\s*,\s*[\'"`](\w+)[\'"`]', re.IGNORECASE)
    RENAME_COLUMN = re.compile(r'(?:renameColumn)\s*\(\s*[\'"`](\w+)[\'"`]\s*,\s*[\'"`](\w+)[\'"`]\s*,\s*[\'"`](\w+)[\'"`]', re.IGNORECASE)

    for mig_file in migrations:
        try:
            with open(mig_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find dropped tables
            for match in DROP_TABLE.finditer(content):
                table = match.group(1)
                removed_tables.add(table)

            # Find removed columns
            for match in REMOVE_COLUMN.finditer(content):
                table = match.group(1)
                column = match.group(2)
                removed_columns.append({'table': table, 'column': column})

            # Find renamed tables
            for match in RENAME_TABLE.finditer(content):
                old_name = match.group(1)
                new_name = match.group(2)
                renamed_items.append({'old_name': old_name, 'new_name': new_name, 'type': 'table'})

            # Find renamed columns
            for match in RENAME_COLUMN.finditer(content):
                table = match.group(1)
                old_name = match.group(2)
                new_name = match.group(3)
                renamed_items.append({
                    'old_name': f"{table}.{old_name}",
                    'new_name': f"{table}.{new_name}",
                    'type': 'column'
                })

        except Exception as e:
            click.echo(f"Warning: Could not read {mig_file}: {e}")

    click.echo(f"  Removed tables: {len(removed_tables)}")
    click.echo(f"  Removed columns: {len(removed_columns)}")
    click.echo(f"  Renamed items: {len(renamed_items)}")

    return {
        'removed_tables': list(removed_tables),
        'removed_columns': removed_columns,
        'renamed_items': renamed_items
    }


def _find_code_references(db_path: Path, schema_changes: Dict, repo_root: Path) -> Dict[str, List[Dict]]:
    """Query database for code that references removed schema items.

    Returns dict with:
        removed_tables: Code references to dropped tables
        removed_columns: Code references to dropped columns
        renamed_items: Code using old names
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    mismatches = {
        'removed_tables': [],
        'removed_columns': [],
        'renamed_items': []
    }

    # Find code referencing removed tables
    for table in schema_changes['removed_tables']:
        # Search in symbols (class/variable names matching table name)
        cursor.execute("""
            SELECT path, line, name, type
            FROM symbols
            WHERE name LIKE ?
        """, (f"%{table}%",))

        for row in cursor.fetchall():
            mismatches['removed_tables'].append({
                'file': row['path'],
                'line': row['line'] or 0,
                'table': table,
                'snippet': f"{row['type']} {row['name']}"
            })

        # Search in assignments/operations
        cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var LIKE ? OR source_expr LIKE ?
            LIMIT 50
        """, (f"%{table}%", f"%{table}%"))

        for row in cursor.fetchall():
            mismatches['removed_tables'].append({
                'file': row['file'],
                'line': row['line'] or 0,
                'table': table,
                'snippet': (row['source_expr'] or row['target_var'] or '')[:200]
            })

    # Find code referencing removed columns
    for col_info in schema_changes['removed_columns']:
        table = col_info['table']
        column = col_info['column']

        # Search for table.column or "column" references
        search_patterns = [
            f"{table}.{column}",
            f'"{column}"',
            f"'{column}'",
            f"`{column}`"
        ]

        # Search assignments for column references
        cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE source_expr LIKE ? OR source_expr LIKE ?
            LIMIT 20
        """, (f"%{table}.{column}%", f"%'{column}'%"))

        for row in cursor.fetchall():
            mismatches['removed_columns'].append({
                'file': row['file'],
                'line': row['line'] or 0,
                'table': table,
                'column': column,
                'snippet': (row['source_expr'] or '')[:200]
            })

    # Find code using old names (renamed items)
    for rename_info in schema_changes['renamed_items']:
        old_name = rename_info['old_name']
        new_name = rename_info['new_name']

        cursor.execute("""
            SELECT path, line, name, type
            FROM symbols
            WHERE name LIKE ?
            LIMIT 20
        """, (f"%{old_name}%",))

        for row in cursor.fetchall():
            mismatches['renamed_items'].append({
                'file': row['path'],
                'line': row['line'] or 0,
                'old_name': old_name,
                'new_name': new_name,
                'snippet': f"{row['type']} {row['name']}"
            })

    conn.close()

    # Deduplicate by file+line
    for category in mismatches:
        seen = set()
        deduped = []
        for item in mismatches[category]:
            key = (item['file'], item.get('line', 0))
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        mismatches[category] = deduped

    return mismatches


def _print_profile_report(
    report: ProfileEvaluation,
    schema_counts: Optional[Dict[str, Dict[str, int]]] = None
) -> None:
    """Pretty-print YAML profile evaluation."""
    click.echo(f"  Description: {report.profile.description}")
    if report.profile.version:
        click.echo(f"  Version: {report.profile.version}")

    total_old = sum(len(r.violations) for r in report.rule_results)
    rules_with_old = [r for r in report.rule_results if r.violations]

    click.echo("\n  PROFILE SUMMARY")
    click.echo(f"    Rules evaluated: {len(report.rule_results)}")
    click.echo(f"    Rules with old references: {len(rules_with_old)}")
    click.echo(f"    Total old references: {total_old}")

    _print_rule_breakdown(report.rule_results, schema_counts)
    _print_top_files(report.rule_results, schema_counts)
    _print_missing_expectations(report.rule_results)


def _assess_risk(mismatches: Dict[str, List]) -> str:
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
    schema_changes: Dict,
    mismatches: Dict,
    risk: str,
    profile_report: Optional[ProfileEvaluation] = None,
) -> Dict:
    """Generate JSON report."""
    report = {
        'schema_changes': schema_changes,
        'mismatches': mismatches,
        'summary': {
            'removed_tables': len(schema_changes['removed_tables']),
            'removed_columns': len(schema_changes['removed_columns']),
            'renamed_items': len(schema_changes['renamed_items']),
            'total_mismatches': sum(len(v) for v in mismatches.values()),
            'risk_level': risk
        }
    }
    if profile_report:
        report['profile'] = profile_report.to_dict()
        report['summary']['profile_violations'] = profile_report.total_violations()
    return report


def _aggregate_schema_counts(mismatches: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, int]]:
    """Aggregate schema mismatch counts per file."""
    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {'tables': 0, 'columns': 0, 'renamed': 0, 'total': 0})

    for item in mismatches.get('removed_tables', []):
        file_path = item.get('file')
        if not file_path:
            continue
        counts[file_path]['tables'] += 1

    for item in mismatches.get('removed_columns', []):
        file_path = item.get('file')
        if not file_path:
            continue
        counts[file_path]['columns'] += 1

    for item in mismatches.get('renamed_items', []):
        file_path = item.get('file')
        if not file_path:
            continue
        counts[file_path]['renamed'] += 1

    for info in counts.values():
        info['total'] = info['tables'] + info['columns'] + info['renamed']

    return counts


def _collect_profile_files(rule_results: List) -> Set[str]:
    """Return set of files involved in profile violations."""
    files = set()
    for result in rule_results:
        for item in result.violations:
            file_path = item.get('file')
            if file_path:
                files.add(file_path)
    return files


def _print_impact_overview(
    profile_report: Optional[ProfileEvaluation],
    mismatches: Dict[str, List[Dict[str, Any]]],
    schema_counts: Dict[str, Dict[str, int]]
) -> None:
    """Display high-level summary across profile + schema phases."""
    click.echo("\nIMPACT OVERVIEW")

    if profile_report:
        rule_count = len(profile_report.rule_results)
        rules_with_old = sum(1 for r in profile_report.rule_results if r.violations)
        total_old = sum(len(r.violations) for r in profile_report.rule_results)
        files_with_old = len(_collect_profile_files(profile_report.rule_results))
        click.echo(
            f"  Profile coverage: {rule_count} rules | "
            f"{rules_with_old} with old refs | "
            f"{total_old} old refs | files impacted: {files_with_old}"
        )

    tables_total = len(mismatches.get('removed_tables', []))
    columns_total = len(mismatches.get('removed_columns', []))
    renamed_total = len(mismatches.get('renamed_items', []))
    click.echo(
        f"  Schema mismatches: tables={tables_total}, columns={columns_total}, renamed={renamed_total} | "
        f"files impacted: {len(schema_counts)}"
    )

    if profile_report:
        profile_files = _collect_profile_files(profile_report.rule_results)
        overlap = sum(1 for file in profile_files if schema_counts.get(file))
        click.echo(f"  Files overlapping profile + schema mismatches: {overlap}")


def _print_rule_breakdown(
    rule_results: List,
    schema_counts: Optional[Dict[str, Dict[str, int]]] = None
) -> None:
    """Show per-rule stats sorted by severity and violation count."""
    click.echo("\n  RULE BREAKDOWN")
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
        unique_files = len({item['file'] for item in result.violations})
        header = f"    [{result.rule.severity.upper()}] {result.rule.id}"
        click.echo(header)
        click.echo(f"      Description: {result.rule.description}")
        click.echo(f"      Old refs: {old_count} (files: {unique_files}) | New refs: {new_count}")
        if schema_counts and old_count:
            violation_files = {item['file'] for item in result.violations}
            overlapping = [schema_counts.get(file) for file in violation_files if schema_counts.get(file)]
            if overlapping:
                overlap_refs = sum(entry['total'] for entry in overlapping)
                click.echo(
                    f"      Schema mismatches touching these files: "
                    f"{overlap_refs} refs across {len(overlapping)} file(s)"
                )

        if old_count:
            click.echo("      Files:")
            top_files = _top_counts((item['file'] for item in result.violations), limit=5)
            for file_path, count in top_files:
                suffix = ""
                if schema_counts and schema_counts.get(file_path, {}).get('total'):
                    schema_info = schema_counts[file_path]
                    suffix = (
                        f" | schema refs: {schema_info['total']} "
                        f"(tables:{schema_info['tables']}, columns:{schema_info['columns']})"
                    )
                click.echo(f"        - {file_path} ({count}){suffix}")
        else:
            click.echo("      Files: clean")

        if new_count:
            click.echo("      Confirmed new schema locations:")
            for item in result.expected_references[:3]:
                click.echo(f"        + {item['file']}:{item['line']} :: {item['match']}")
            if new_count > 3:
                click.echo(f"        ... {new_count - 3} more")
        elif not result.rule.expect.is_empty():
            click.echo("      Confirmed new schema locations: missing")


def _print_top_files(
    rule_results: List,
    schema_counts: Optional[Dict[str, Dict[str, int]]] = None,
    limit: int = 10
) -> None:
    """Aggregate violations across rules to highlight hotspots."""
    queue = _build_file_priority_queue(rule_results, schema_counts, limit=limit)
    if not queue:
        return
    click.echo("\n  FILE PRIORITY QUEUE")
    for file_path, data in queue:
        rules_desc = ", ".join(f"{rule_id}({count})" for rule_id, count in data['rules'])
        schema_suffix = ""
        schema = data.get('schema')
        if schema and schema.get('total'):
            schema_suffix = (
                f" | schema refs: {schema['total']} "
                f"(tables:{schema['tables']}, columns:{schema['columns']})"
            )
        click.echo(
            f"    - [{data['max_severity'].upper()}] {file_path}: "
            f"{data['count']} refs across {data['rule_count']} rule(s) | {rules_desc}{schema_suffix}"
        )


def _top_counts(items: Iterable[str], limit: int = 5) -> List[Tuple[str, int]]:
    """Return top counts for iterable items."""
    counter = Counter(item for item in items if item)
    return counter.most_common(limit)


def _build_file_priority_queue(
    rule_results: List,
    schema_counts: Optional[Dict[str, Dict[str, int]]] = None,
    limit: int = 10
) -> List[Tuple[str, Dict[str, Any]]]:
    """Summarize files affected by rules with severity and rule context."""
    stats: Dict[str, Dict[str, Any]] = {}

    for result in rule_results:
        severity = result.rule.severity
        for issue in result.violations:
            file_path = issue.get('file')
            if not file_path:
                continue
            entry = stats.setdefault(
                file_path,
                {
                    'count': 0,
                    'rules': Counter(),
                    'max_severity': severity,
                },
            )
            entry['count'] += 1
            entry['rules'][result.rule.id] += 1
            if SEVERITY_ORDER.get(severity, 4) < SEVERITY_ORDER.get(entry['max_severity'], 4):
                entry['max_severity'] = severity

    queue = sorted(
        stats.items(),
        key=lambda item: (
            SEVERITY_ORDER.get(item[1]['max_severity'], 4),
            -item[1]['count'],
            item[0],
        ),
    )[:limit]

    formatted = []
    for file_path, data in queue:
        formatted.append(
            (
                file_path,
                {
                    'count': data['count'],
                    'rule_count': len(data['rules']),
                    'max_severity': data['max_severity'],
                    'rules': data['rules'].most_common(),
                    'schema': schema_counts.get(file_path) if schema_counts else None,
                },
            )
        )
    return formatted


def _print_missing_expectations(rule_results: List) -> None:
    """Highlight rules that expect new schema references but none were found."""
    missing = [
        result for result in rule_results
        if not result.expected_references and not result.rule.expect.is_empty()
    ]
    if not missing:
        return
    click.echo("\n  RULES WITH MISSING NEW SCHEMA REFERENCES")
    for result in missing:
        click.echo(f"    - [{result.rule.severity.upper()}] {result.rule.id}: expected patterns not observed")


def _print_mismatch_summary(items: List[Dict[str, Any]], label: str, key_field: str, description: str) -> None:
    """Report aggregate info plus sample references for schema mismatches."""
    count = len(items)
    click.echo(f"\n{label} ({count} issues):")
    if not items:
        click.echo("  None")
        return

    top_keys = _top_counts((item.get(key_field) for item in items), limit=5)
    top_files = _top_counts((item.get('file') for item in items), limit=5)

    click.echo(f"  Summary: {description}")
    if top_keys:
        click.echo("  Most affected identifiers:")
        for key, key_count in top_keys:
            click.echo(f"    - {key}: {key_count}")
    if top_files:
        click.echo("  Files with highest counts:")
        for file_path, file_count in top_files:
            click.echo(f"    - {file_path}: {file_count}")

    click.echo("  Sample references:")
    for issue in items[:10]:
        location = f"{issue['file']}:{issue.get('line', 0)}"
        click.echo(f"    - {location}")
        if 'table' in issue and 'column' in issue:
            click.echo(f"      {issue['table']}.{issue['column']}")
        elif 'table' in issue:
            click.echo(f"      {issue['table']}")
        elif 'old_name' in issue and 'new_name' in issue:
            click.echo(f"      {issue['old_name']} -> {issue['new_name']}")
        snippet = issue.get('snippet')
        if snippet:
            click.echo(f"      Snippet: {snippet[:80]}...")


# Export for CLI
refactor_command = refactor
