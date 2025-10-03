#!/usr/bin/env python3
"""
Create golden snapshot database from 5 production runs.

This script merges 5 repo_index.db files from diverse projects into a single
golden snapshot used for testing. This avoids dogfooding (testing TheAuditor
by running TheAuditor).

Usage:
    1. Run `aud full --offline` on 5 diverse projects
    2. Copy each .pf/repo_index.db to inputs/ directory:
       - inputs/project1_repo_index.db
       - inputs/project2_repo_index.db
       - inputs/project3_repo_index.db
       - inputs/project4_repo_index.db
       - inputs/project5_repo_index.db

    3. Run this script:
       python scripts/create_golden_snapshot.py

    4. Golden snapshot created at: repo_index.db (root directory)

The golden snapshot will contain:
- All tables from all 5 projects
- Diverse data (Python, JavaScript, SQL, JWT, API endpoints, etc.)
- Known-good state for deterministic testing
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def get_table_names(cursor):
    """Get all user tables from database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return [row[0] for row in cursor.fetchall()]


def copy_table_data(source_cursor, dest_cursor, table_name, project_name):
    """Copy all rows from source table to destination table."""
    # Get column names
    source_cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in source_cursor.fetchall()]

    if not columns:
        print(f"  ⚠ Skipping {table_name} - no columns found")
        return 0

    # Read all data from source
    source_cursor.execute(f"SELECT * FROM {table_name}")
    rows = source_cursor.fetchall()

    if not rows:
        print(f"  ⚠ Skipping {table_name} - no data")
        return 0

    # Insert into destination
    placeholders = ','.join(['?' for _ in columns])
    dest_cursor.execute(f"INSERT OR IGNORE INTO {table_name} VALUES ({placeholders})", rows[0])

    # Use executemany for remaining rows
    if len(rows) > 1:
        dest_cursor.executemany(f"INSERT OR IGNORE INTO {table_name} VALUES ({placeholders})", rows[1:])

    print(f"  ✓ {table_name}: {len(rows)} rows copied from {project_name}")
    return len(rows)


def create_golden_snapshot(input_dbs, output_db):
    """
    Merge multiple repo_index.db files into golden snapshot.

    Args:
        input_dbs: List of paths to source repo_index.db files
        output_db: Path to output golden snapshot database
    """
    print(f"Creating golden snapshot: {output_db}")
    print(f"Merging {len(input_dbs)} databases...")
    print()

    # Remove existing golden snapshot if present
    if output_db.exists():
        print(f"⚠ Removing existing snapshot: {output_db}")
        output_db.unlink()

    # Create destination database by copying first source
    if not input_dbs:
        print("❌ ERROR: No input databases found")
        return False

    print(f"1. Using {input_dbs[0].name} as base structure...")
    dest_conn = sqlite3.connect(output_db)
    dest_cursor = dest_conn.cursor()

    # Copy schema from first database
    source_conn = sqlite3.connect(input_dbs[0])
    source_cursor = source_conn.cursor()

    # Get schema SQL for all tables
    source_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    schemas = [row[0] for row in source_cursor.fetchall() if row[0]]

    for schema in schemas:
        try:
            dest_cursor.execute(schema)
        except sqlite3.OperationalError as e:
            print(f"  ⚠ Schema creation warning: {e}")

    # Get schema for indexes
    source_cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
    indexes = [row[0] for row in source_cursor.fetchall()]

    for index_sql in indexes:
        try:
            dest_cursor.execute(index_sql)
        except sqlite3.OperationalError as e:
            print(f"  ⚠ Index creation warning: {e}")

    dest_conn.commit()
    source_conn.close()

    print("  ✓ Schema created")
    print()

    # Merge data from all databases
    total_rows = 0
    tables = get_table_names(dest_cursor)

    for i, db_path in enumerate(input_dbs, 1):
        print(f"{i}. Merging {db_path.name}...")

        source_conn = sqlite3.connect(db_path)
        source_cursor = source_conn.cursor()

        project_rows = 0
        for table in tables:
            try:
                rows = copy_table_data(source_cursor, dest_cursor, table, db_path.stem)
                project_rows += rows
            except sqlite3.Error as e:
                print(f"  ⚠ Error copying {table}: {e}")

        source_conn.close()
        dest_conn.commit()

        print(f"  ✓ Total rows from {db_path.name}: {project_rows}")
        print()
        total_rows += project_rows

    # Add metadata table
    dest_cursor.execute("""
        CREATE TABLE IF NOT EXISTS _golden_snapshot_metadata (
            created_at TEXT,
            source_count INTEGER,
            total_rows INTEGER,
            notes TEXT
        )
    """)

    dest_cursor.execute("""
        INSERT INTO _golden_snapshot_metadata (created_at, source_count, total_rows, notes)
        VALUES (?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        len(input_dbs),
        total_rows,
        f"Merged from: {', '.join(db.stem for db in input_dbs)}"
    ))

    dest_conn.commit()

    # Print summary
    print("=" * 60)
    print("GOLDEN SNAPSHOT CREATED")
    print("=" * 60)
    print(f"Output: {output_db}")
    print(f"Source databases: {len(input_dbs)}")
    print(f"Total rows merged: {total_rows:,}")
    print()
    print("Table counts:")

    for table in sorted(tables):
        dest_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = dest_cursor.fetchone()[0]
        if count > 0:
            print(f"  {table:30s}: {count:,}")

    dest_conn.close()

    print()
    print("✓ Golden snapshot ready for testing!")
    print(f"  Move to project root: mv {output_db} ./repo_index.db")
    return True


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    inputs_dir = script_dir / "inputs"

    print("=" * 60)
    print("GOLDEN SNAPSHOT CREATOR")
    print("=" * 60)
    print()

    # Check for input directory
    if not inputs_dir.exists():
        print(f"❌ ERROR: inputs/ directory not found")
        print()
        print("Please create it and add 5 repo_index.db files:")
        print(f"  mkdir {inputs_dir}")
        print(f"  cp /path/to/project1/.pf/repo_index.db {inputs_dir}/project1_repo_index.db")
        print(f"  cp /path/to/project2/.pf/repo_index.db {inputs_dir}/project2_repo_index.db")
        print("  (... 3 more projects)")
        sys.exit(1)

    # Find input databases
    input_dbs = sorted(inputs_dir.glob("*repo_index.db"))

    if not input_dbs:
        print(f"❌ ERROR: No *repo_index.db files found in {inputs_dir}")
        print()
        print("Add database files from 5 diverse projects:")
        print("  - Python web app")
        print("  - React/Vue frontend")
        print("  - Express/Flask API")
        print("  - Full-stack app")
        print("  - TheAuditor itself")
        sys.exit(1)

    if len(input_dbs) < 3:
        print(f"⚠ WARNING: Only {len(input_dbs)} databases found")
        print("  Recommended: 5 diverse projects for comprehensive coverage")
        print()

    for db in input_dbs:
        print(f"  Found: {db.name} ({db.stat().st_size / 1024:.1f} KB)")

    print()

    # Create golden snapshot
    output_db = script_dir / "golden_repo_index.db"

    success = create_golden_snapshot(input_dbs, output_db)

    if success:
        # Move to project root
        final_path = project_root / "repo_index.db"
        if final_path.exists():
            print(f"\n⚠ WARNING: {final_path} already exists")
            response = input("  Overwrite? (y/N): ")
            if response.lower() != 'y':
                print("  Keeping new snapshot at: {output_db}")
                return

        output_db.rename(final_path)
        print(f"\n✓ Golden snapshot installed: {final_path}")
        print("\nRun tests: pytest tests/ -v")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
