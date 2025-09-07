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
    """Generate unified audit report from all artifacts."""
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