"""Indexer workflow runner."""

import sqlite3
import time
from pathlib import Path
from typing import Any

from theauditor.indexer.config import DEFAULT_BATCH_SIZE
from theauditor.indexer.core import FileWalker
from theauditor.indexer.database import create_database_schema
from theauditor.indexer.orchestrator import IndexerOrchestrator
from theauditor.utils.logging import logger

try:
    from theauditor.ast_extractors.js_semantic_parser import _module_resolver_cache
except ImportError:
    _module_resolver_cache = None


def run_repository_index(
    root_path: str = ".",
    db_path: str = ".pf/repo_index.db",
    dry_run: bool = False,
    follow_symlinks: bool = False,
    exclude_patterns: list[str] | None = None,
    print_stats: bool = False,
) -> dict[str, Any]:
    """Run the complete repository indexing workflow."""
    start_time = time.time()
    root = Path(root_path).resolve()

    if not root.exists():
        raise FileNotFoundError(f"Root path does not exist: {root_path}")

    walker = FileWalker(root, follow_symlinks, exclude_patterns)
    _files, walk_stats = walker.walk()

    if dry_run:
        if print_stats:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Files scanned: {walk_stats['total_files']}")
            logger.info(f"Text files indexed: {walk_stats['text_files']}")
            logger.info(f"Binary files skipped: {walk_stats['binary_files']}")
            logger.info(f"Large files skipped: {walk_stats['large_files']}")
            logger.info(f"Elapsed: {elapsed_ms}ms")
        return {
            "success": True,
            "dry_run": True,
            "stats": walk_stats,
            "elapsed": time.time() - start_time,
        }

    db_file = root / db_path
    db_file.parent.mkdir(parents=True, exist_ok=True)

    db_exists = db_file.exists()

    conn = sqlite3.connect(str(db_file), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("BEGIN IMMEDIATE")
    create_database_schema(conn)
    conn.commit()
    conn.close()

    if not db_exists:
        logger.info(f"Created database: {db_path}")

    if _module_resolver_cache is not None:
        try:
            _module_resolver_cache._load_all_configs_from_db()
        except Exception as e:
            logger.info(f"WARNING: Module resolver config load failed: {e}")

    orchestrator = IndexerOrchestrator(
        root_path=root,
        db_path=str(db_file),
        batch_size=DEFAULT_BATCH_SIZE,
        follow_symlinks=follow_symlinks,
        exclude_patterns=exclude_patterns,
    )

    orchestrator.db_manager.clear_tables()

    extract_counts, _ = orchestrator.index()

    elapsed = time.time() - start_time

    if print_stats:
        elapsed_ms = int(elapsed * 1000)
        logger.info(f"Files scanned: {walk_stats['total_files']}")
        logger.info(f"Text files indexed: {walk_stats['text_files']}")
        logger.info(f"Binary files skipped: {walk_stats['binary_files']}")
        logger.info(f"Large files skipped: {walk_stats['large_files']}")
        logger.info(f"Refs extracted: {extract_counts['refs']}")
        logger.info(f"Routes extracted: {extract_counts['routes']}")
        logger.info(f"SQL objects extracted: {extract_counts['sql']}")
        logger.info(f"SQL queries extracted: {extract_counts['sql_queries']}")
        logger.info(f"Docker images analyzed: {extract_counts['docker']}")
        logger.info(f"Symbols extracted: {extract_counts['symbols']}")
        logger.info(f"Elapsed: {elapsed_ms}ms")

    return {
        "success": True,
        "stats": walk_stats,
        "extract_counts": extract_counts,
        "elapsed": elapsed,
    }
