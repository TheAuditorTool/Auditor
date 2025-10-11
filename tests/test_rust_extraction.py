#!/usr/bin/env python3
"""Test Rust extraction on hegel-cli project.

Usage:
    python3 .ddd/test_rust_extraction.py /path/to/hegel-cli
"""

import sys
import sqlite3
from pathlib import Path

# Add TheAuditor to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from theauditor.indexer import IndexerOrchestrator


def test_rust_extraction(project_dir: Path):
    """Test Rust extraction on a project."""
    project_dir = project_dir.resolve()

    if not project_dir.exists():
        print(f"❌ Project directory not found: {project_dir}")
        sys.exit(1)

    cargo_toml = project_dir / 'Cargo.toml'
    if not cargo_toml.exists():
        print(f"❌ Not a Rust project (no Cargo.toml): {project_dir}")
        sys.exit(1)

    print(f"📁 Project: {project_dir}")
    print(f"✅ Rust project detected")
    print()

    # Setup database
    pf_dir = project_dir / '.pf'
    pf_dir.mkdir(exist_ok=True)
    db_path = pf_dir / 'repo_index.db'

    # Remove old database
    if db_path.exists():
        db_path.unlink()
        print(f"🗑️  Removed old database")

    print(f"🗄️  Database: {db_path}")
    print()

    # Create orchestrator and index
    print("🔍 Starting indexing...")
    orchestrator = IndexerOrchestrator(
        root_path=project_dir,
        db_path=str(db_path)
    )

    # Create database schema
    orchestrator.db_manager.create_schema()

    # Run indexing
    orchestrator.index()

    print("\n✅ Indexing complete!")
    print("\n" + "="*60)
    print("📊 EXTRACTION STATISTICS")
    print("="*60)

    # Query results
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Total files
    cursor.execute("SELECT COUNT(*) FROM files WHERE ext = '.rs'")
    rust_files = cursor.fetchone()[0]
    print(f"\n  Rust files indexed: {rust_files}")

    # Total symbols
    cursor.execute("SELECT COUNT(*) FROM symbols WHERE path LIKE '%.rs'")
    rust_symbols = cursor.fetchone()[0]
    print(f"  Rust symbols extracted: {rust_symbols}")

    # Symbols by type
    cursor.execute("""
        SELECT type, COUNT(*)
        FROM symbols
        WHERE path LIKE '%.rs'
        GROUP BY type
        ORDER BY COUNT(*) DESC
    """)
    symbol_types = cursor.fetchall()

    if symbol_types:
        print(f"\n  Symbols by type:")
        for typ, count in symbol_types:
            print(f"    {typ:15s}: {count:4d}")

    # Imports
    cursor.execute("SELECT COUNT(*) FROM refs WHERE src LIKE '%.rs' AND kind = 'use'")
    rust_imports = cursor.fetchone()[0]
    print(f"\n  Use statements: {rust_imports}")

    # Sample symbols from main.rs or lib.rs
    for entry_file in ['main.rs', 'lib.rs']:
        cursor.execute(
            "SELECT name, type, line FROM symbols WHERE path LIKE ? ORDER BY line LIMIT 10",
            (f'%{entry_file}',)
        )
        sample_symbols = cursor.fetchall()

        if sample_symbols:
            print(f"\n  Sample from {entry_file}:")
            for name, typ, line in sample_symbols:
                print(f"    {name:20s} ({typ:10s}) at line {line}")
            break

    # List all indexed files
    cursor.execute("SELECT path FROM files WHERE ext = '.rs' ORDER BY path")
    rust_file_paths = [row[0] for row in cursor.fetchall()]

    if rust_file_paths:
        print(f"\n  Indexed Rust files ({len(rust_file_paths)}):")
        for path in rust_file_paths[:20]:  # Show first 20
            print(f"    {path}")
        if len(rust_file_paths) > 20:
            print(f"    ... and {len(rust_file_paths) - 20} more")

    conn.close()

    print("\n" + "="*60)
    print("✅ TEST COMPLETE")
    print("="*60)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        # Default to hegel-cli
        project_path = Path.home() / 'Code' / 'hegel-cli'
    else:
        project_path = Path(sys.argv[1])

    test_rust_extraction(project_path)
