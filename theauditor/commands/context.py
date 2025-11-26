"""Context command - semantic business logic for findings classification.

Apply user-defined YAML rules to classify analysis findings based on your
business logic, refactoring contexts, and semantic patterns.

Example: During OAuth migration, mark all JWT findings as "obsolete".
"""

import json
import sqlite3
from pathlib import Path

import click

from theauditor.utils.error_handler import handle_exceptions


@click.command()
@click.option("--file", "-f", "context_file", required=True, type=click.Path(exists=True),
              help="Semantic context YAML file")
@click.option("--output", "-o", type=click.Path(),
              help="Custom output JSON file (optional)")
@click.option("--verbose", "-v", is_flag=True,
              help="Show detailed findings in report")
@handle_exceptions
def context(context_file: str, output: str | None, verbose: bool):
    """Apply user-defined semantic rules to classify findings based on business logic and refactoring context.

    Enables project-specific interpretation of analysis findings through YAML rules that classify
    issues as obsolete (needs immediate fix), current (correct pattern), or transitional (acceptable
    during migration). Essential for refactoring workflows where temporary inconsistencies are expected
    (e.g., OAuth migration makes JWT findings obsolete, but old endpoints still exist during transition).

    AI ASSISTANT CONTEXT:
      Purpose: Semantic classification of findings based on business context
      Input: context.yaml (rules), .pf/raw/*.json (analysis findings)
      Output: .pf/raw/context_report.json (classified findings)
      Prerequisites: aud full or aud detect-patterns (populates findings)
      Integration: Refactoring workflows, technical debt tracking, migration planning
      Performance: ~1-3 seconds (YAML parsing + finding classification)

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
         - Reads findings from .pf/raw/*.json
         - Includes detect-patterns, taint-analyze, deadcode, etc.

      3. Apply Classification Rules:
         - Matches findings against YAML patterns
         - Assigns state (obsolete/current/transitional)
         - Unmatched findings default to "current"

      4. Generate Report:
         - Groups findings by state
         - Calculates counts per classification
         - Outputs to .pf/raw/context_report.json

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
      --output: Custom output path (default: .pf/raw/context_report.json)
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
      aud full --help        # Understand full analysis pipeline
      aud explain workset    # Learn about targeted analysis

    TROUBLESHOOTING:
      Error: "YAML parse error":
        -> Validate YAML syntax: cat context.yaml | yaml lint
        -> Check indentation (YAML is whitespace-sensitive)
        -> Verify required fields (refactor_context, rules)

      No findings classified:
        -> Run 'aud full' or 'aud detect-patterns' first
        -> Check .pf/raw/*.json files exist and have content
        -> Verify YAML patterns match actual finding types

      All findings marked "current" (no obsolete):
        -> YAML patterns may not match finding format
        -> Check pattern field names match finding structure
        -> Use --verbose to see classification logic

    NOTE: Context classification is for human workflow management, not security
    enforcement. "Transitional" findings are still real issues that must be fixed
    eventually - classification just provides temporary exception tracking.
    """
    from theauditor.insights import SemanticContext

    # Find .pf directory
    pf_dir = Path.cwd() / ".pf"
    db_path = pf_dir / "repo_index.db"

    # Simple check: Does database file exist?
    if not db_path.exists():
        click.echo("\n" + "="*60, err=True)
        click.echo("❌ ERROR: Database not found", err=True)
        click.echo("="*60, err=True)
        click.echo("\nSemantic context requires analysis data.", err=True)
        click.echo("\nPlease run ONE of these first:", err=True)
        click.echo("\n  Option A (Recommended):", err=True)
        click.echo("    aud full", err=True)
        click.echo("\nThen try again:", err=True)
        click.echo(f"    aud context --file {context_file}\n", err=True)
        raise click.Abort()

    # Load semantic context
    click.echo("\n" + "="*80)
    click.echo("SEMANTIC CONTEXT ANALYSIS")
    click.echo("="*80)
    click.echo(f"\n📋 Loading semantic context: {context_file}")

    try:
        context = SemanticContext.load(Path(context_file))
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"\n❌ ERROR loading context file: {e}", err=True)
        raise click.Abort()

    click.echo(f"✓ Loaded context: {context.context_name}")
    click.echo(f"  Version: {context.version}")
    click.echo(f"  Description: {context.description}")

    # Load findings from database
    click.echo(f"\n📊 Loading findings from database...")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if findings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='findings_consolidated'
        """)

        if not cursor.fetchone():
            click.echo("\n⚠️  WARNING: findings_consolidated table not found", err=True)
            click.echo("\nThis means analysis hasn't been run yet.", err=True)
            click.echo("\nPlease run:", err=True)
            click.echo("    aud full", err=True)
            conn.close()
            raise click.Abort()

        # Load all findings
        cursor.execute("""
            SELECT file, line, column, rule, tool, message, severity, category, code_snippet, cwe
            FROM findings_consolidated
            ORDER BY file, line
        """)

        findings = []
        for row in cursor.fetchall():
            findings.append({
                'file': row['file'],
                'line': row['line'],
                'column': row['column'],
                'rule': row['rule'],
                'tool': row['tool'],
                'message': row['message'],
                'severity': row['severity'],
                'category': row['category'],
                'code_snippet': row['code_snippet'],
                'cwe': row['cwe']
            })

        conn.close()

    except sqlite3.Error as e:
        click.echo(f"\n❌ ERROR reading database: {e}", err=True)
        raise click.Abort()

    # Handle empty findings
    if not findings:
        click.echo("\n⚠️  No findings in database")
        click.echo("\nThis could mean:")
        click.echo("  1. Analysis hasn't been run yet (run: aud full)")
        click.echo("  2. No issues detected (clean code!)")
        click.echo("  3. Database is outdated (re-run: aud full)")
        click.echo("\nCannot classify findings without data.")
        raise click.Abort()

    click.echo(f"✓ Loaded {len(findings)} findings from database")

    # Show pattern summary
    click.echo(f"\n🔍 Applying semantic patterns:")
    click.echo(f"  Obsolete patterns:     {len(context.obsolete_patterns)}")
    click.echo(f"  Current patterns:      {len(context.current_patterns)}")
    click.echo(f"  Transitional patterns: {len(context.transitional_patterns)}")

    # Classify findings
    click.echo(f"\n⚙️  Classifying findings...")
    result = context.classify_findings(findings)

    click.echo(f"✓ Classification complete")
    click.echo(f"  Classified: {result.summary['classified']}")
    click.echo(f"  Unclassified: {result.summary['unclassified']}")

    # Generate and display report
    click.echo("\n" + "="*80)
    report = context.generate_report(result, verbose=verbose)
    click.echo(report)

    # Write to .pf/raw/ for extraction
    click.echo("\n" + "="*80)
    click.echo("💾 Writing results...")
    click.echo("="*80)

    raw_dir = pf_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    output_file = raw_dir / f"semantic_context_{context.context_name}.json"
    context.export_to_json(result, output_file)
    click.echo(f"\n✓ Raw results: {output_file}")

    # AUTO-EXTRACT for AI consumption
    click.echo(f"\n🔧 Auto-extracting chunks for AI consumption...")

    readthis_dir = pf_dir / "readthis"
    readthis_dir.mkdir(parents=True, exist_ok=True)

    # Simple chunking logic
    chunks_created = _extract_semantic_chunks(output_file, readthis_dir, context.context_name)

    if chunks_created > 0:
        click.echo(f"✓ Created {chunks_created} chunk file(s) in .pf/readthis/")
    else:
        click.echo(f"✓ Results fit in single file (no chunking needed)")

    # User-specified output file (optional)
    if output:
        context.export_to_json(result, Path(output))
        click.echo(f"\n✓ Custom output: {output}")

    # Summary of outputs
    click.echo("\n" + "="*80)
    click.echo("📂 OUTPUT LOCATIONS")
    click.echo("="*80)
    click.echo(f"\n  Raw JSON:     {output_file}")
    click.echo(f"  AI Chunks:    .pf/readthis/semantic_context_{context.context_name}_chunk*.json")
    if output:
        click.echo(f"  Custom:       {output}")

    # Next steps
    click.echo("\n" + "="*80)
    click.echo("✅ SEMANTIC CONTEXT ANALYSIS COMPLETE")
    click.echo("="*80)

    migration_progress = result.get_migration_progress()
    if migration_progress['files_need_migration'] > 0:
        click.echo(f"\n📋 Next steps:")
        click.echo(f"  1. Address {len(result.get_high_priority_files())} high-priority files")
        click.echo(f"  2. Update {len(result.mixed_files)} mixed files")
        click.echo(f"  3. Migrate {migration_progress['files_need_migration']} files total")
        click.echo(f"\n  Run with --verbose for detailed file list")
    else:
        click.echo(f"\n🎉 All files migrated! No obsolete patterns found.")


def _extract_semantic_chunks(json_file: Path, readthis_dir: Path, context_name: str) -> int:
    """Extract and chunk semantic context results for AI consumption.

    Args:
        json_file: Path to raw JSON file
        readthis_dir: Output directory for chunks
        context_name: Name of semantic context

    Returns:
        Number of chunks created (0 if no chunking needed)
    """
    # Load the JSON file
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Calculate size
    json_str = json.dumps(data, indent=2)
    size_bytes = len(json_str.encode('utf-8'))

    # Chunking threshold (65KB)
    MAX_CHUNK_SIZE = 65_000

    # If small enough, write single file and return 0
    if size_bytes <= MAX_CHUNK_SIZE:
        output_file = readthis_dir / f"semantic_context_{context_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return 0

    # Need to chunk - split by sections
    chunks = []

    # Chunk 1: Summary + metadata
    chunk1 = {
        'context_name': data.get('context_name'),
        'description': data.get('description'),
        'version': data.get('version'),
        'generated_at': data.get('generated_at'),
        'migration_progress': data.get('migration_progress'),
        'high_priority_files': data.get('high_priority_files'),
        'summary': data.get('classification', {}).get('summary', {})
    }
    chunks.append(chunk1)

    # Chunk 2: Obsolete findings (if any)
    classification = data.get('classification', {})
    if classification.get('obsolete'):
        chunk2 = {
            'context_name': data.get('context_name'),
            'type': 'obsolete_findings',
            'obsolete': classification['obsolete'],
            'mixed_files': classification.get('mixed_files', {})
        }
        chunks.append(chunk2)

    # Chunk 3: Current findings (if any)
    if classification.get('current'):
        chunk3 = {
            'context_name': data.get('context_name'),
            'type': 'current_findings',
            'current': classification['current']
        }
        chunks.append(chunk3)

    # Chunk 4: Transitional + migration suggestions
    chunk4 = {
        'context_name': data.get('context_name'),
        'type': 'transitional_and_suggestions',
        'transitional': classification.get('transitional', []),
        'migration_suggestions': data.get('migration_suggestions', [])
    }
    chunks.append(chunk4)

    # Write chunks
    for i, chunk in enumerate(chunks, 1):
        chunk_file = readthis_dir / f"semantic_context_{context_name}_chunk{i:02d}.json"
        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, indent=2)

    return len(chunks)



# Export for CLI registration
context_command = context
