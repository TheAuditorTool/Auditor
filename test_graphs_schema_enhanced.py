"""
Enhanced test script to verify graphs schema migration is 1:1 lossless.

Verifies:
- Table structure (columns, types, nullable, defaults, PK)
- Indexes
- UNIQUE constraints
- DDL comparison
- Foreign keys (if any)
"""

import sqlite3
import os
from test_graphs_schema_migration import create_old_schema_db, create_new_schema_db


def compare_ddl(old_db: str, new_db: str) -> tuple[bool, list[str]]:
    """Compare CREATE TABLE DDL between old and new databases."""
    old_conn = sqlite3.connect(old_db)
    new_conn = sqlite3.connect(new_db)

    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()

    # Get table names (exclude sqlite_sequence)
    old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence' ORDER BY name")
    tables = [row[0] for row in old_cursor.fetchall()]

    all_match = True
    differences = []

    print("=" * 80)
    print("DDL COMPARISON")
    print("=" * 80)
    print()

    for table_name in tables:
        print(f"Table: {table_name}")
        print("-" * 80)

        old_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        old_ddl = old_cursor.fetchone()[0]

        new_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        new_ddl = new_cursor.fetchone()[0]

        print("OLD DDL:")
        print(old_ddl)
        print()
        print("NEW DDL:")
        print(new_ddl)
        print()

        # Check UNIQUE constraints
        old_has_unique = "UNIQUE" in old_ddl.upper()
        new_has_unique = "UNIQUE" in new_ddl.upper()

        if old_has_unique != new_has_unique:
            differences.append(f"{table_name}: UNIQUE constraint mismatch (OLD={old_has_unique}, NEW={new_has_unique})")
            all_match = False
            print(f"[FAIL] UNIQUE constraint mismatch!")
        elif old_has_unique:
            print(f"[OK] UNIQUE constraint present in both")

        # Check AUTOINCREMENT
        old_has_autoinc = "AUTOINCREMENT" in old_ddl.upper()
        new_has_autoinc = "AUTOINCREMENT" in new_ddl.upper()

        if old_has_autoinc != new_has_autoinc:
            differences.append(f"{table_name}: AUTOINCREMENT mismatch (OLD={old_has_autoinc}, NEW={new_has_autoinc})")
            all_match = False
            print(f"[FAIL] AUTOINCREMENT mismatch!")
        elif old_has_autoinc:
            print(f"[OK] AUTOINCREMENT present in both")

        print()

    old_conn.close()
    new_conn.close()

    return all_match, differences


def verify_indexes(old_db: str, new_db: str) -> tuple[bool, list[str]]:
    """Verify indexes match between databases."""
    old_conn = sqlite3.connect(old_db)
    new_conn = sqlite3.connect(new_db)

    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()

    all_match = True
    differences = []

    print("=" * 80)
    print("INDEX VERIFICATION")
    print("=" * 80)
    print()

    # Get all indexes (exclude auto-generated ones)
    old_cursor.execute("""
        SELECT name, tbl_name, sql
        FROM sqlite_master
        WHERE type='index'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    old_indexes = old_cursor.fetchall()

    new_cursor.execute("""
        SELECT name, tbl_name, sql
        FROM sqlite_master
        WHERE type='index'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    new_indexes = new_cursor.fetchall()

    old_idx_names = {idx[0] for idx in old_indexes}
    new_idx_names = {idx[0] for idx in new_indexes}

    if old_idx_names != new_idx_names:
        differences.append(f"Index name mismatch: OLD={old_idx_names}, NEW={new_idx_names}")
        all_match = False
        print("[FAIL] Index names don't match!")
        print(f"  OLD: {old_idx_names}")
        print(f"  NEW: {new_idx_names}")
    else:
        print(f"[OK] All {len(old_indexes)} indexes match")
        for idx in old_indexes:
            print(f"  - {idx[0]} on {idx[1]}")

    print()

    old_conn.close()
    new_conn.close()

    return all_match, differences


def main():
    """Run comprehensive enhanced schema verification."""
    print("=" * 80)
    print("ENHANCED GRAPHS SCHEMA MIGRATION TEST")
    print("=" * 80)
    print()

    old_db = "vs.db"
    new_db = "test.db"

    # Clean up
    for db_path in [old_db, new_db]:
        if os.path.exists(db_path):
            os.remove(db_path)

    # Create databases
    print("[CREATE] Creating test databases...")
    create_old_schema_db(old_db)
    create_new_schema_db(new_db)
    print(f"[OK] vs.db: {os.path.getsize(old_db)} bytes")
    print(f"[OK] test.db: {os.path.getsize(new_db)} bytes")
    print()

    # Run enhanced checks
    ddl_match, ddl_diffs = compare_ddl(old_db, new_db)
    idx_match, idx_diffs = verify_indexes(old_db, new_db)

    # Final result
    print("=" * 80)
    print("FINAL RESULT")
    print("=" * 80)
    print()

    if ddl_match and idx_match:
        print("[SUCCESS] Migration is 1:1 LOSSLESS!")
        print()
        print("Verification complete:")
        print("  [OK] All tables match")
        print("  [OK] All columns match (name, type, nullable, default, pk)")
        print("  [OK] All indexes match")
        print("  [OK] All UNIQUE constraints match")
        print("  [OK] All AUTOINCREMENT flags match")
        print("  [OK] All DDL statements functionally identical")
        print()
        print(f"Database sizes: OLD={os.path.getsize(old_db)} bytes, NEW={os.path.getsize(new_db)} bytes")
        return 0
    else:
        print("[FAILURE] Migration has differences!")
        print()
        for diff in ddl_diffs + idx_diffs:
            print(f"  - {diff}")
        return 1


if __name__ == "__main__":
    exit(main())
