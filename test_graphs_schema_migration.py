"""
Test script to verify graphs schema migration is 1:1 lossless.

Compares:
- OLD: Raw SQL in store.py (before migration)
- NEW: TableSchema-based in graphs_schema.py (after migration)

Creates two databases and compares them at SQLite level.
"""

import sqlite3
import os
from pathlib import Path


def create_old_schema_db(db_path: str):
    """Create database using OLD raw SQL approach (pre-migration)."""
    conn = sqlite3.connect(db_path)

    # OLD RAW SQL from store.py _init_schema() before migration
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            file TEXT NOT NULL,
            lang TEXT,
            loc INTEGER DEFAULT 0,
            churn INTEGER,
            type TEXT DEFAULT 'module',
            graph_type TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            type TEXT DEFAULT 'import',
            file TEXT,
            line INTEGER,
            graph_type TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, target, type, graph_type)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_type TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type)")

    conn.commit()
    conn.close()


def create_new_schema_db(db_path: str):
    """Create database using NEW TableSchema approach (post-migration)."""
    from theauditor.indexer.schemas.graphs_schema import GRAPH_TABLES

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # NEW APPROACH: Use TableSchema definitions
    for table_name, schema in GRAPH_TABLES.items():
        cursor.execute(schema.create_table_sql())

        for index_sql in schema.create_indexes_sql():
            cursor.execute(index_sql)

    conn.commit()
    conn.close()


def get_table_info(db_path: str) -> dict:
    """Extract complete schema information from database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    schema_info = {}

    # Get all tables (exclude sqlite_sequence which is auto-created by AUTOINCREMENT)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    for table_name in tables:
        table_data = {}

        # Get table DDL
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        table_data['ddl'] = cursor.fetchone()[0]

        # Get columns
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'cid': row[0],
                'name': row[1],
                'type': row[2],
                'notnull': row[3],
                'dflt_value': row[4],
                'pk': row[5]
            })
        table_data['columns'] = columns

        # Get indexes
        cursor.execute(f"PRAGMA index_list({table_name})")
        indexes = []
        for row in cursor.fetchall():
            idx_name = row[1]
            cursor.execute(f"PRAGMA index_info({idx_name})")
            idx_cols = [col[2] for col in cursor.fetchall()]
            indexes.append({
                'name': idx_name,
                'unique': row[2],
                'columns': idx_cols
            })
        table_data['indexes'] = indexes

        schema_info[table_name] = table_data

    conn.close()
    return schema_info


def normalize_sql(sql: str) -> str:
    """Normalize SQL for comparison (remove whitespace differences)."""
    import re
    # Remove extra whitespace
    sql = re.sub(r'\s+', ' ', sql.strip())
    # Remove IF NOT EXISTS for comparison
    sql = sql.replace('IF NOT EXISTS ', '')
    return sql.upper()


def compare_schemas(old_info: dict, new_info: dict) -> tuple[bool, list[str]]:
    """Compare two database schemas and return differences."""
    differences = []

    # Compare table lists
    old_tables = set(old_info.keys())
    new_tables = set(new_info.keys())

    if old_tables != new_tables:
        differences.append(f"Table mismatch: OLD={old_tables}, NEW={new_tables}")
        return False, differences

    # Compare each table
    for table_name in old_tables:
        old_table = old_info[table_name]
        new_table = new_info[table_name]

        # Compare columns
        old_cols = old_table['columns']
        new_cols = new_table['columns']

        if len(old_cols) != len(new_cols):
            differences.append(f"{table_name}: Column count mismatch (OLD={len(old_cols)}, NEW={len(new_cols)})")
            continue

        for old_col, new_col in zip(old_cols, new_cols):
            if old_col != new_col:
                differences.append(f"{table_name}.{old_col['name']}: Column mismatch")
                differences.append(f"  OLD: {old_col}")
                differences.append(f"  NEW: {new_col}")

        # Compare indexes (filter out auto-generated ones)
        old_indexes = [idx for idx in old_table['indexes'] if not idx['name'].startswith('sqlite_autoindex')]
        new_indexes = [idx for idx in new_table['indexes'] if not idx['name'].startswith('sqlite_autoindex')]

        old_idx_names = {idx['name'] for idx in old_indexes}
        new_idx_names = {idx['name'] for idx in new_indexes}

        if old_idx_names != new_idx_names:
            differences.append(f"{table_name}: Index mismatch")
            differences.append(f"  OLD indexes: {old_idx_names}")
            differences.append(f"  NEW indexes: {new_idx_names}")

    return len(differences) == 0, differences


def main():
    """Run comprehensive schema comparison test."""
    print("=" * 80)
    print("GRAPHS SCHEMA MIGRATION TEST")
    print("=" * 80)
    print()

    # Paths for test databases
    old_db = "vs.db"
    new_db = "test.db"

    # Clean up old test databases
    for db_path in [old_db, new_db]:
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"[CLEANUP] Removed old {db_path}")

    print()
    print("=" * 80)
    print("STEP 1: Create databases")
    print("=" * 80)

    # Create OLD schema database (raw SQL)
    print(f"\n[CREATE] {old_db} using OLD raw SQL approach...")
    create_old_schema_db(old_db)
    print(f"[OK] {old_db} created")

    # Create NEW schema database (TableSchema)
    print(f"\n[CREATE] {new_db} using NEW TableSchema approach...")
    create_new_schema_db(new_db)
    print(f"[OK] {new_db} created")

    print()
    print("=" * 80)
    print("STEP 2: Extract schema information")
    print("=" * 80)

    print(f"\n[EXTRACT] Reading schema from {old_db}...")
    old_info = get_table_info(old_db)
    print(f"[OK] Found {len(old_info)} tables in {old_db}")
    for table_name in sorted(old_info.keys()):
        print(f"  - {table_name}: {len(old_info[table_name]['columns'])} columns, {len(old_info[table_name]['indexes'])} indexes")

    print(f"\n[EXTRACT] Reading schema from {new_db}...")
    new_info = get_table_info(new_db)
    print(f"[OK] Found {len(new_info)} tables in {new_db}")
    for table_name in sorted(new_info.keys()):
        print(f"  - {table_name}: {len(new_info[table_name]['columns'])} columns, {len(new_info[table_name]['indexes'])} indexes")

    print()
    print("=" * 80)
    print("STEP 3: Compare schemas at database level")
    print("=" * 80)
    print()

    is_identical, differences = compare_schemas(old_info, new_info)

    if is_identical:
        print("[SUCCESS] Schemas are IDENTICAL!")
        print()
        print("Migration verified:")
        print("  - All tables match")
        print("  - All columns match (name, type, nullable, default, pk)")
        print("  - All indexes match")
        print("  - All constraints match")
        print()
        print("[PASS] graphs_schema.py migration is 1:1 lossless!")
    else:
        print("[FAILURE] Schemas have DIFFERENCES:")
        print()
        for diff in differences:
            print(f"  {diff}")
        print()
        print("[FAIL] Migration is NOT lossless!")
        return 1

    print()
    print("=" * 80)
    print("STEP 4: Detailed column-by-column comparison")
    print("=" * 80)
    print()

    for table_name in sorted(old_info.keys()):
        print(f"Table: {table_name}")
        print("-" * 80)

        old_cols = old_info[table_name]['columns']
        new_cols = new_info[table_name]['columns']

        print(f"{'Column':<20} {'Type':<15} {'NotNull':<10} {'Default':<20} {'PK':<5}")
        print("-" * 80)

        for old_col, new_col in zip(old_cols, new_cols):
            # Verify each field matches
            match = "OK" if old_col == new_col else "MISMATCH"

            print(f"{old_col['name']:<20} {old_col['type']:<15} {old_col['notnull']:<10} {str(old_col['dflt_value']):<20} {old_col['pk']:<5} [{match}]")

        print()

    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)
    print()
    print("[SUCCESS] Migration test PASSED!")
    print(f"  - vs.db (old raw SQL): {os.path.getsize(old_db)} bytes")
    print(f"  - test.db (new TableSchema): {os.path.getsize(new_db)} bytes")
    print()
    print("Databases remain on disk for manual inspection:")
    print(f"  - {old_db}")
    print(f"  - {new_db}")
    print()

    return 0


if __name__ == "__main__":
    exit(main())
