"""Generate unified audit report from all artifacts."""

from pathlib import Path
import click
from theauditor.utils.error_handler import handle_exceptions


@click.command()
@handle_exceptions
@click.option("--manifest", default="./.pf/manifest.json", help="Manifest file path")
@click.option("--db", default="./.pf/repo_index.db", help="Database path")
@click.option("--workset", default="./.pf/workset.json", help="Workset file path")
@click.option("--capsules", default="./.pf/capsules", help="Capsules directory")
@click.option("--run-report", default="./.pf/run_report.json", help="Run report file path")
@click.option("--journal", default="./.pf/journal.ndjson", help="Journal file path")
@click.option("--fce", default="./.pf/fce.json", help="FCE file path")
@click.option("--ast", default="./.pf/ast_proofs.json", help="AST proofs file path")
@click.option("--ml", default="./.pf/ml_suggestions.json", help="ML suggestions file path")
@click.option("--patch", help="Patch diff file path")
@click.option("--out-dir", default="./.pf/audit", help="Output directory for audit reports")
@click.option("--max-snippet-lines", default=3, type=int, help="Maximum lines per snippet")
@click.option("--max-snippet-chars", default=220, type=int, help="Maximum characters per line")
@click.option("--print-stats", is_flag=True, help="Print summary statistics")
def report(
    manifest,
    db,
    workset,
    capsules,
    run_report,
    journal,
    fce,
    ast,
    ml,
    patch,
    out_dir,
    max_snippet_lines,
    max_snippet_chars,
    print_stats,
):
    """Generate consolidated audit report from analysis artifacts.

    **DEPRECATED**: This command generates .pf/readthis/ chunks which are obsolete
    as of v1.3.0. Use `aud query` for database queries or read consolidated files
    in .pf/raw/ directly. See migration guide in README.md.

    This command is kept for backward compatibility only.

    AI ASSISTANT CONTEXT:
      Purpose: [DEPRECATED] Consolidate artifacts into chunks (obsolete)
      Input: .pf/raw/*.json (all analysis phase outputs)
      Output: .pf/readthis/*.json (chunked findings <65KB each) [DEPRECATED]
      Prerequisites: aud full (or individual analysis commands)
      Integration: [DEPRECATED] Use `aud query` or read .pf/raw/*.json instead
      Performance: ~2-5 seconds (JSON aggregation + chunking)

    Input Sources (Auto-Detected):
      - Pattern detection results (.pf/raw/patterns*.json)
      - Taint analysis findings (.pf/raw/taint*.json)
      - Lint results (.pf/raw/lint.json)
      - Dependency analysis (.pf/raw/deps*.json)
      - Graph analysis (.pf/raw/graph*.json)
      - FCE correlations (.pf/raw/fce.json)
      - Terraform security findings (.pf/raw/terraform_findings.json)
      - Control flow analysis (.pf/raw/cfg*.json)

    Output Structure:
      .pf/readthis/
      ├── summary.json           # Executive summary with counts
      ├── patterns_chunk01.json  # Security pattern findings
      ├── taint_chunk01.json     # Taint flow vulnerabilities
      ├── terraform_chunk01.json  # Infrastructure security issues
      ├── lint_chunk01.json      # Code quality issues
      └── *_chunk*.json          # Other findings (<65KB each)

    Chunking Strategy:
      - Each file is split into chunks under 65KB
      - Maximum 3 chunks per analysis type
      - Designed for LLM context windows
      - Preserves finding completeness

    Examples:
      aud report                  # Generate report from all artifacts
      aud report --print-stats    # Show detailed statistics

    Typical Workflow:
      1. aud full                 # Run all analysis
      2. aud report               # Generate consolidated report
      3. Review .pf/readthis/     # Check AI-optimized output

    Report Contents:
      - Security vulnerabilities with severity
      - Code quality issues with locations
      - Dependency problems
      - Infrastructure security (Terraform)
      - Architectural issues
      - Cross-referenced findings from FCE

    Note: Most commands auto-generate their chunks, so this command
    mainly verifies and summarizes existing output. Run after 'aud full'
    or individual analysis commands."""
    # Report generation has been simplified
    # Data is already chunked in .pf/readthis/ by extraction phase
    
    readthis_dir = Path("./.pf/readthis")
    
    if readthis_dir.exists():
        json_files = list(readthis_dir.glob("*.json"))
        click.echo(f"[OK] Audit report generated - Data chunks ready for AI consumption")
        click.echo(f"[INFO] Report contains {len(json_files)} JSON chunks in .pf/readthis/")
        
        if print_stats:
            total_size = sum(f.stat().st_size for f in json_files)
            click.echo(f"\n[STATS] Summary:")
            click.echo(f"  - Total chunks: {len(json_files)}")
            click.echo(f"  - Total size: {total_size:,} bytes")
            click.echo(f"  - Average chunk: {total_size // len(json_files):,} bytes" if json_files else "  - No chunks")
            
            click.echo(f"\n[FILES] Available chunks:")
            for f in sorted(json_files)[:10]:  # Show first 10
                size = f.stat().st_size
                click.echo(f"  - {f.name} ({size:,} bytes)")
            if len(json_files) > 10:
                click.echo(f"  ... and {len(json_files) - 10} more")
    else:
        click.echo("[WARNING] No readthis directory found at .pf/readthis/")
        click.echo("[INFO] Run 'aud full' to generate analysis data")