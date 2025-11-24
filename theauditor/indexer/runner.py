"""Indexer workflow runner.

This module provides the high-level workflow for running the indexing process.
Replaces the legacy build_index() shim from indexer_compat.py.

2025 Modern: Clean entry point for pipelines.py, no backward compat baggage.
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from theauditor.config_runtime import load_runtime_config
from theauditor.indexer.core import FileWalker
from theauditor.indexer.orchestrator import IndexerOrchestrator
from theauditor.indexer.database import create_database_schema
from theauditor.indexer.config import DEFAULT_BATCH_SIZE


def run_repository_index(
    root_path: str = ".",
    manifest_path: str = ".pf/manifest.json",
    db_path: str = ".pf/repo_index.db",
    dry_run: bool = False,
    follow_symlinks: bool = False,
    exclude_patterns: list[str] | None = None,
    print_stats: bool = False,
) -> dict[str, Any]:
    """
    Run the complete repository indexing workflow.

    1. Walk files
    2. Write manifest
    3. Create/Migrate DB
    4. Index content (AST + Extraction)

    Args:
        root_path: Root directory to index
        manifest_path: Path to write manifest JSON (relative to root)
        db_path: Path to SQLite database (relative to root)
        dry_run: If True, only scan files without creating database
        follow_symlinks: Whether to follow symbolic links
        exclude_patterns: Patterns to exclude from indexing
        print_stats: Whether to print statistics to stdout

    Returns:
        Dictionary with success status and statistics

    Raises:
        FileNotFoundError: If root_path does not exist
    """
    start_time = time.time()
    root = Path(root_path).resolve()

    # ZERO FALLBACK: Hard fail if root doesn't exist
    if not root.exists():
        raise FileNotFoundError(f"Root path does not exist: {root_path}")

    # 1. Walk directory and collect files
    config = load_runtime_config(str(root))
    walker = FileWalker(root, config, follow_symlinks, exclude_patterns)
    files, walk_stats = walker.walk()

    if dry_run:
        if print_stats:
            elapsed_ms = int((time.time() - start_time) * 1000)
            print(f"Files scanned: {walk_stats['total_files']}")
            print(f"Text files indexed: {walk_stats['text_files']}")
            print(f"Binary files skipped: {walk_stats['binary_files']}")
            print(f"Large files skipped: {walk_stats['large_files']}")
            print(f"Elapsed: {elapsed_ms}ms")
        return {
            "success": True,
            "dry_run": True,
            "stats": walk_stats,
            "elapsed": time.time() - start_time
        }

    # 2. Write manifest
    manifest_file = root / manifest_path
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(files, f, indent=2, sort_keys=True)

    # 3. Create/Reset Database
    db_file = root / db_path
    db_file.parent.mkdir(parents=True, exist_ok=True)

    # Check if new database
    db_exists = db_file.exists()

    # Initialize Schema
    conn = sqlite3.connect(str(db_file))
    conn.execute("BEGIN IMMEDIATE")
    create_database_schema(conn)
    conn.commit()
    conn.close()

    if not db_exists:
        print(f"[Indexer] Created database: {db_path}")

    # 4. Run Indexer Orchestrator
    orchestrator = IndexerOrchestrator(
        root_path=root,
        db_path=str(db_file),
        batch_size=DEFAULT_BATCH_SIZE,
        follow_symlinks=follow_symlinks,
        exclude_patterns=exclude_patterns
    )

    # Clear old data before indexing to avoid unique constraint collisions
    orchestrator.db_manager.clear_tables()

    # Run the heavy lifting
    extract_counts, _ = orchestrator.index()

    elapsed = time.time() - start_time

    if print_stats:
        elapsed_ms = int(elapsed * 1000)
        print(f"Files scanned: {walk_stats['total_files']}")
        print(f"Text files indexed: {walk_stats['text_files']}")
        print(f"Binary files skipped: {walk_stats['binary_files']}")
        print(f"Large files skipped: {walk_stats['large_files']}")
        print(f"Refs extracted: {extract_counts['refs']}")
        print(f"Routes extracted: {extract_counts['routes']}")
        print(f"SQL objects extracted: {extract_counts['sql']}")
        print(f"SQL queries extracted: {extract_counts['sql_queries']}")
        print(f"Docker images analyzed: {extract_counts['docker']}")
        print(f"Symbols extracted: {extract_counts['symbols']}")
        print(f"Elapsed: {elapsed_ms}ms")

    return {
        "success": True,
        "stats": walk_stats,
        "extract_counts": extract_counts,
        "elapsed": elapsed,
    }
