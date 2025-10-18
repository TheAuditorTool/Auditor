"""Internal archive command for segregating history by run type."""

import shutil
import sys
from datetime import datetime
from pathlib import Path

import click


@click.command(name="_archive")
@click.option("--run-type", required=True, type=click.Choice(["full", "diff"]), help="Type of run being archived")
@click.option("--diff-spec", help="Git diff specification for diff runs (e.g., main..HEAD)")
@click.option("--wipe-cache", is_flag=True, help="Delete caches during archive (default: preserve)")
def _archive(run_type: str, diff_spec: str = None, wipe_cache: bool = False):
    """
    Internal command to archive previous run artifacts with segregation by type.

    This command is not intended for direct user execution. It's called by
    the full and orchestrate workflows to maintain clean, segregated history.

    Cache Preservation:
    By default, caches (.cache/, context/) are PRESERVED to speed up subsequent
    runs. Use --wipe-cache to force deletion (useful for cache corruption recovery).

    Preserved by default:
    - .pf/.cache/ (AST parsing cache)
    - .pf/context/ (documentation cache and summaries)

    Always archived:
    - .pf/raw/ (raw tool outputs)
    - .pf/readthis/ (AI-consumable chunks)
    - All other .pf/ contents
    """
    # Define base paths
    pf_dir = Path(".pf")
    history_dir = pf_dir / "history"

    # Define cache directories that should be preserved by default
    CACHE_DIRS = {".cache", "context"}

    # Check if there's a previous run to archive (by checking if .pf exists and has files)
    if not pf_dir.exists() or not any(pf_dir.iterdir()):
        # No previous run to archive
        print("[ARCHIVE] No previous run artifacts found to archive", file=sys.stderr)
        return
    
    # Determine destination base path based on run type
    if run_type == "full":
        dest_base = history_dir / "full"
    else:  # run_type == "diff"
        dest_base = history_dir / "diff"
    
    # Create destination base directory if it doesn't exist
    dest_base.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp for archive directory
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create unique directory name
    if run_type == "diff" and diff_spec:
        # Sanitize diff spec for directory name
        # Replace problematic characters with underscores
        safe_spec = diff_spec.replace("..", "_")
        safe_spec = safe_spec.replace("/", "_")
        safe_spec = safe_spec.replace("\\", "_")
        safe_spec = safe_spec.replace(":", "_")
        safe_spec = safe_spec.replace(" ", "_")
        safe_spec = safe_spec.replace("~", "_")
        safe_spec = safe_spec.replace("^", "_")
        
        # Create descriptive name like "main_HEAD_20250819_090015"
        dir_name = f"{safe_spec}_{timestamp_str}"
    else:
        # Simple timestamp for full runs
        dir_name = timestamp_str
    
    # Create the archive destination directory
    archive_dest = dest_base / dir_name
    archive_dest.mkdir(exist_ok=True)
    
    # Move all top-level items from pf_dir to archive_dest
    archived_count = 0
    skipped_count = 0
    preserved_count = 0

    for item in pf_dir.iterdir():
        # CRITICAL: Skip the history directory itself to prevent recursive archiving
        if item.name == "history":
            continue

        # NEW: Preserve cache directories unless --wipe-cache was used
        if item.name in CACHE_DIRS and not wipe_cache:
            print(f"[ARCHIVE] Preserving cache: {item.name}/", file=sys.stderr)
            preserved_count += 1
            continue

        # Safely move the item to archive destination
        try:
            shutil.move(str(item), str(archive_dest))
            archived_count += 1
        except Exception as e:
            # Log error but don't stop the archiving process
            print(f"[WARNING] Could not archive {item.name}: {e}", file=sys.stderr)
            skipped_count += 1
    
    # Log summary
    if archived_count > 0:
        click.echo(f"[ARCHIVE] Archived {archived_count} items to {archive_dest}")
        if preserved_count > 0:
            click.echo(f"[ARCHIVE] Preserved {preserved_count} cache directories for reuse")
        if skipped_count > 0:
            click.echo(f"[ARCHIVE] Skipped {skipped_count} items due to errors")
    else:
        if preserved_count > 0:
            click.echo(f"[ARCHIVE] No artifacts to archive (only caches remain)")
        else:
            click.echo("[ARCHIVE] No artifacts archived (directory was empty)")
    
    # Create a metadata file in the archive to track run type and context
    metadata = {
        "run_type": run_type,
        "diff_spec": diff_spec,
        "timestamp": timestamp_str,
        "archived_at": datetime.now().isoformat(),
        "files_archived": archived_count,
        "files_skipped": skipped_count,
        "caches_preserved": preserved_count,
        "wipe_cache_requested": wipe_cache,
    }
    
    try:
        import json
        metadata_path = archive_dest / "_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        print(f"[WARNING] Could not write metadata file: {e}", file=sys.stderr)