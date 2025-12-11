"""Internal archive command for segregating history by run type."""

import shutil
from datetime import datetime
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.utils.logging import logger

CACHE_DIRS = frozenset({".cache", "context", "ml", "planning"})


@click.command(name="_archive", cls=RichCommand)
@click.option(
    "--run-type",
    required=True,
    type=click.Choice(["full", "diff"]),
    help="Type of run being archived",
)
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
    - All other .pf/ contents

    AI ASSISTANT CONTEXT:
      Purpose: Internal command to archive previous run artifacts by run type
      Input: .pf/ directory contents (raw outputs, databases, caches)
      Output: .pf/history/{full|diff}/<timestamp>/ archived artifacts with _metadata.json
      Prerequisites: None (called internally by pipeline)
      Integration: NOT for direct use - called automatically by aud full before each run
    """

    pf_dir = Path(".pf")
    history_dir = pf_dir / "history"

    if not pf_dir.exists() or not any(pf_dir.iterdir()):
        logger.info("No previous run artifacts found to archive")
        return

    dest_base = history_dir / "full" if run_type == "full" else history_dir / "diff"

    dest_base.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    if run_type == "diff" and diff_spec:
        safe_spec = diff_spec.replace("..", "_")
        safe_spec = safe_spec.replace("/", "_")
        safe_spec = safe_spec.replace("\\", "_")
        safe_spec = safe_spec.replace(":", "_")
        safe_spec = safe_spec.replace(" ", "_")
        safe_spec = safe_spec.replace("~", "_")
        safe_spec = safe_spec.replace("^", "_")

        dir_name = f"{safe_spec}_{timestamp_str}"
    else:
        dir_name = timestamp_str

    archive_dest = dest_base / dir_name
    archive_dest.mkdir(exist_ok=True)

    archived_count = 0
    skipped_count = 0
    preserved_count = 0

    for item in pf_dir.iterdir():
        if item.name == "history":
            continue

        if item.name in CACHE_DIRS and not wipe_cache:
            logger.info(f"Preserving cache: {item.name}/")
            preserved_count += 1
            continue

        try:
            shutil.move(str(item), str(archive_dest))
            archived_count += 1
        except Exception as e:
            logger.warning(f"Could not archive {item.name}: {e}")
            skipped_count += 1

    # Copy journal.ndjson to archive (ml/ is preserved but journal needs archiving for ML training)
    journal_src = pf_dir / "ml" / "journal.ndjson"
    if journal_src.exists():
        try:
            shutil.copy2(str(journal_src), str(archive_dest / "journal.ndjson"))
            logger.info("[ARCHIVE] Copied journal.ndjson to history for ML training")
        except Exception as e:
            logger.warning(f"Could not copy journal.ndjson: {e}")

    if archived_count > 0:
        logger.info(f"[ARCHIVE] Archived {archived_count} items to {archive_dest}")
        if preserved_count > 0:
            logger.info(f"[ARCHIVE] Preserved {preserved_count} cache directories for reuse")
        if skipped_count > 0:
            logger.warning(f"[ARCHIVE] Skipped {skipped_count} items due to errors")
    else:
        if preserved_count > 0:
            logger.info("[ARCHIVE] No artifacts to archive (only caches remain)")
        else:
            logger.info("[ARCHIVE] No artifacts archived (directory was empty)")

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
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not write metadata file: {e}")
