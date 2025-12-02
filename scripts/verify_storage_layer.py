"""
Storage Layer Verification (Wave 3)
====================================
Tests the database manager and storage layer in ISOLATION.
Uses an in-memory database - no disk I/O, no production data touched.

This catches:
  - Schema creation failures
  - CRUD operation bugs
  - Foreign key constraint violations
  - Batch flush ordering issues
  - Parent-child relationship problems

Exit codes:
  0 = All checks passed
  1 = Warnings (non-fatal issues)
  2 = Critical errors (storage is broken)

Author: TheAuditor Team
"""
import sys
import os
import traceback
import sqlite3

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def verify_storage_layer() -> int:
    """Run storage layer verification. Returns exit code."""
    print("=" * 60)
    print("STORAGE LAYER VERIFICATION (Wave 3)")
    print("=" * 60)

    errors = 0
    warnings = 0

    # 1. Import modules
    print("\n[1] Loading storage modules...")
    try:
        from theauditor.indexer.database import DatabaseManager
        from theauditor.indexer.storage import DataStorer
        from theauditor.indexer.schema import TABLES, FLUSH_ORDER

        print(f"    [OK] Loaded DatabaseManager and DataStorer")
        print(f"    [OK] Schema has {len(TABLES)} tables, {len(FLUSH_ORDER)} flush entries")
    except ImportError as e:
        print(f"    [CRITICAL] Failed to import modules: {e}")
        traceback.print_exc()
        return 2

    # 2. Initialize in-memory database
    print("\n[2] Creating in-memory database...")
    try:
        db = DatabaseManager(":memory:")

        # Enable strict foreign key enforcement
        db.conn.execute("PRAGMA foreign_keys = ON")

        # Create schema
        db.create_schema()

        print(f"    [OK] Database initialized with strict FK enforcement")
    except Exception as e:
        print(f"    [CRITICAL] Database initialization failed: {e}")
        traceback.print_exc()
        return 2

    # 3. Initialize data storer
    print("\n[3] Initializing DataStorer...")
    try:
        counts = {
            "files": 0, "refs": 0, "symbols": 0, "routes": 0,
            "assignments": 0, "function_calls": 0, "returns": 0,
            "variable_usage": 0, "object_literals": 0, "cfg_blocks": 0,
            "cfg_edges": 0, "cfg_statements": 0,
        }
        storer = DataStorer(db, counts)
        print(f"    [OK] DataStorer initialized")
    except Exception as e:
        print(f"    [CRITICAL] DataStorer initialization failed: {e}")
        traceback.print_exc()
        return 2

    # 4. Test basic file insertion (parent table)
    print("\n[4] Testing file insertion (parent table)...")
    try:
        file_path = "src/test_file.py"
        db.add_file(file_path, "abc123hash", ".py", 1024, 50)
        db.flush_batch()
        db.commit()

        # Verify
        cursor = db.conn.cursor()
        cursor.execute("SELECT path, ext, loc FROM files WHERE path = ?", (file_path,))
        row = cursor.fetchone()

        if row and row[0] == file_path:
            print(f"    [OK] File inserted and retrieved correctly")
        else:
            print(f"    [FAIL] File not found after insert")
            errors += 1

    except Exception as e:
        print(f"    [FAIL] File insertion crashed: {e}")
        traceback.print_exc()
        errors += 1

    # 5. Test symbol insertion (child table with FK to files)
    print("\n[5] Testing symbol insertion (child table FK)...")
    try:
        db.add_symbol(file_path, "test_function", "function", 10, 0)
        db.flush_batch()
        db.commit()

        cursor = db.conn.cursor()
        cursor.execute("SELECT name, type FROM symbols WHERE path = ?", (file_path,))
        row = cursor.fetchone()

        if row and row[0] == "test_function":
            print(f"    [OK] Symbol inserted with valid FK reference")
        else:
            print(f"    [FAIL] Symbol not found after insert")
            errors += 1

    except sqlite3.IntegrityError as e:
        print(f"    [FAIL] FK violation on symbol insert: {e}")
        errors += 1
    except Exception as e:
        print(f"    [FAIL] Symbol insertion crashed: {e}")
        traceback.print_exc()
        errors += 1

    # 6. Test ref insertion
    print("\n[6] Testing ref insertion...")
    try:
        db.add_ref(file_path, "import", "os", 1)
        db.flush_batch()
        db.commit()

        cursor = db.conn.cursor()
        cursor.execute("SELECT kind, value FROM refs WHERE src = ?", (file_path,))
        row = cursor.fetchone()

        if row and row[1] == "os":
            print(f"    [OK] Ref inserted correctly")
        else:
            print(f"    [FAIL] Ref not found after insert")
            errors += 1

    except Exception as e:
        print(f"    [FAIL] Ref insertion crashed: {e}")
        traceback.print_exc()
        errors += 1

    # 7. Test DataStorer with mock extracted data
    print("\n[7] Testing DataStorer with mock extracted data...")
    try:
        # Register a new file first
        mock_file = "src/mock_module.py"
        db.add_file(mock_file, "hash456", ".py", 512, 25)
        db.flush_batch()

        # Mock extracted data that storer would receive
        mock_data = {
            "symbols": [
                {"name": "MyClass", "type": "class", "line": 1, "col": 0},
                {"name": "my_method", "type": "method", "line": 5, "col": 4},
            ],
            "imports": [
                {"type": "import", "target": "json", "line": 1},
                {"type": "from", "target": "typing", "line": 2},
            ],
            "assignments": [
                {
                    "line": 10,
                    "target_var": "result",
                    "source_expr": "compute()",
                    "source_vars": ["compute"],
                    "in_function": "my_method",
                    "col": 4,
                },
            ],
        }

        storer.store(mock_file, mock_data)
        db.flush_batch()
        db.commit()

        # Verify counts
        cursor = db.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM symbols WHERE path = ?", (mock_file,))
        symbol_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM refs WHERE src = ?", (mock_file,))
        ref_count = cursor.fetchone()[0]

        if symbol_count >= 2 and ref_count >= 2:
            print(f"    [OK] DataStorer processed mock data correctly")
            print(f"        Symbols: {symbol_count}, Refs: {ref_count}")
        else:
            print(f"    [WARN] DataStorer may have missed some data")
            print(f"        Symbols: {symbol_count} (expected 2+), Refs: {ref_count} (expected 2+)")
            warnings += 1

    except Exception as e:
        print(f"    [FAIL] DataStorer processing crashed: {e}")
        traceback.print_exc()
        errors += 1

    # 8. Test FK violation detection (should fail on orphan insert)
    print("\n[8] Testing FK violation detection...")
    try:
        # Try to insert symbol for non-existent file (should fail with FK enforcement)
        orphan_file = "nonexistent/orphan.py"

        db.add_symbol(orphan_file, "orphan_func", "function", 1, 0)
        db.flush_batch()

        # If we get here without error, FK enforcement may be off
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM symbols WHERE path = ?", (orphan_file,))
        orphan_count = cursor.fetchone()[0]

        if orphan_count > 0:
            print(f"    [WARN] Orphan symbol was inserted - FK enforcement may be weak")
            warnings += 1
        else:
            print(f"    [OK] No orphan symbols found")

    except sqlite3.IntegrityError as e:
        # This is EXPECTED - FK should catch the orphan
        # Clear the failed batch so it doesn't contaminate later tests
        db.generic_batches.clear()
        db.rollback()  # Rollback any partial transaction
        print(f"    [OK] FK violation correctly caught: {str(e)[:50]}...")
    except (ValueError, RuntimeError) as e:
        # base_database.py wraps IntegrityError in ValueError/RuntimeError
        # This is also expected behavior
        db.generic_batches.clear()
        db.rollback()
        if "FOREIGN KEY" in str(e) or "ORPHAN" in str(e):
            print(f"    [OK] FK violation correctly caught and wrapped")
        else:
            print(f"    [WARN] Unexpected error during FK test: {str(e)[:60]}...")
            warnings += 1
    except Exception as e:
        # Clear batch on any error
        db.generic_batches.clear()
        print(f"    [WARN] Unexpected error during FK test: {e}")
        warnings += 1

    # 9. Test batch flush ordering
    print("\n[9] Testing batch flush ordering...")
    try:
        # Add a file and its children in the same batch
        batch_file = "src/batch_test.py"

        # Queue file (parent)
        db.add_file(batch_file, "batchhash", ".py", 100, 10)

        # Queue symbol (child) - should be flushed AFTER files
        db.add_symbol(batch_file, "batch_func", "function", 5, 0)

        # Single flush should handle ordering correctly
        db.flush_batch()
        db.commit()

        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM symbols WHERE path = ?", (batch_file,))
        batch_count = cursor.fetchone()[0]

        if batch_count == 1:
            print(f"    [OK] Batch flush ordering works correctly")
        else:
            print(f"    [FAIL] Batch ordering issue - symbol count: {batch_count}")
            errors += 1

    except sqlite3.IntegrityError as e:
        print(f"    [FAIL] FK violation in batch - ordering broken: {e}")
        errors += 1
    except Exception as e:
        print(f"    [FAIL] Batch flush crashed: {e}")
        traceback.print_exc()
        errors += 1

    # 10. Test transaction rollback
    print("\n[10] Testing transaction rollback...")
    try:
        rollback_file = "src/rollback_test.py"
        db.add_file(rollback_file, "rollbackhash", ".py", 100, 10)
        db.flush_batch()
        # Don't commit - simulate rollback

        # Rollback
        db.rollback()

        # Check if file was rolled back
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM files WHERE path = ?", (rollback_file,))
        rollback_count = cursor.fetchone()[0]

        if rollback_count == 0:
            print(f"    [OK] Transaction rollback works correctly")
        else:
            print(f"    [WARN] Rollback may not have worked - file count: {rollback_count}")
            warnings += 1

    except Exception as e:
        print(f"    [WARN] Rollback test error: {e}")
        warnings += 1

    # 11. Check table row counts
    print("\n[11] Final database state check...")
    try:
        cursor = db.conn.cursor()

        tables_to_check = ["files", "symbols", "refs", "assignments"]
        for table in tables_to_check:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"    {table.ljust(15)}: {count} rows")

    except Exception as e:
        print(f"    [WARN] Could not check table counts: {e}")
        warnings += 1

    # Cleanup
    db.close()

    # Final verdict
    print("\n" + "=" * 60)
    if errors > 0:
        print(f"[FAIL] Storage layer verification failed with {errors} error(s)")
        print("       Database operations may not work correctly.")
        return 2
    elif warnings > 0:
        print(f"[PASS] Storage layer verification passed with {warnings} warning(s)")
        return 1
    else:
        print("[PASS] Storage layer verification passed - all checks clean")
        return 0


if __name__ == "__main__":
    exit_code = verify_storage_layer()
    sys.exit(exit_code)
