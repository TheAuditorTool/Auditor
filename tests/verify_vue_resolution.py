"""Verification script for vue-inmemory-module-resolution ticket.

Tests:
1. Module resolution logic (resolve_import_paths)
2. Schema changes (resolved_path column)

Run: python tests/verify_vue_resolution.py
"""

import os
import sys
import sqlite3
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from theauditor.indexer.extractors.javascript_resolvers import JavaScriptResolversMixin


def create_test_database():
    """Create a test database with sample data."""
    db_path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create files table
    cursor.execute("""
        CREATE TABLE files (
            path TEXT PRIMARY KEY,
            ext TEXT,
            size INTEGER,
            mtime REAL
        )
    """)

    # Create import_styles table with resolved_path column
    cursor.execute("""
        CREATE TABLE import_styles (
            file TEXT NOT NULL,
            line INTEGER NOT NULL,
            package TEXT NOT NULL,
            import_style TEXT NOT NULL,
            alias_name TEXT,
            full_statement TEXT,
            resolved_path TEXT
        )
    """)

    # Insert sample files (simulating indexed JS/TS/Vue files)
    sample_files = [
        ("src/utils.ts", ".ts", 1000, 1700000000.0),
        ("src/helpers/format.ts", ".ts", 500, 1700000000.0),
        ("src/components/Button.vue", ".vue", 2000, 1700000000.0),
        ("src/components/Card.vue", ".vue", 1500, 1700000000.0),
        ("src/index.ts", ".ts", 300, 1700000000.0),
        ("src/api/client.ts", ".ts", 800, 1700000000.0),
        ("src/api/index.ts", ".ts", 200, 1700000000.0),
        ("lib/shared.js", ".js", 400, 1700000000.0),
    ]
    cursor.executemany(
        "INSERT INTO files (path, ext, size, mtime) VALUES (?, ?, ?, ?)",
        sample_files
    )

    # Insert sample imports to resolve
    sample_imports = [
        # Relative imports
        ("src/components/Button.vue", 1, "./Card", "named", None, "import { Card } from './Card'"),
        ("src/components/Button.vue", 2, "../utils", "named", None, "import { formatDate } from '../utils'"),
        ("src/components/Button.vue", 3, "../api", "named", None, "import { api } from '../api'"),  # Should resolve to index.ts
        ("src/api/client.ts", 1, "./index", "named", None, "import { config } from './index'"),
        ("src/index.ts", 1, "./utils", "default", None, "import utils from './utils'"),

        # Parent traversal
        ("src/components/Button.vue", 4, "../../lib/shared", "named", None, "import { shared } from '../../lib/shared'"),

        # Should NOT resolve (bare specifier)
        ("src/index.ts", 2, "lodash", "named", None, "import { debounce } from 'lodash'"),

        # Should NOT resolve (file doesn't exist)
        ("src/index.ts", 3, "./nonexistent", "named", None, "import { x } from './nonexistent'"),
    ]
    cursor.executemany(
        "INSERT INTO import_styles (file, line, package, import_style, alias_name, full_statement) VALUES (?, ?, ?, ?, ?, ?)",
        sample_imports
    )

    conn.commit()
    conn.close()
    return db_path


def verify_resolution(db_path):
    """Run resolver and verify results."""
    print("\n=== Running resolve_import_paths() ===\n")

    # Enable debug output
    os.environ["THEAUDITOR_DEBUG"] = "1"

    # Run the resolver
    JavaScriptResolversMixin.resolve_import_paths(db_path)

    # Check results
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT file, line, package, resolved_path
        FROM import_styles
        ORDER BY file, line
    """)

    results = cursor.fetchall()
    conn.close()

    print("\n=== Resolution Results ===\n")
    print(f"{'File':<35} {'Line':<5} {'Import':<25} {'Resolved':<30}")
    print("-" * 100)

    passed = 0
    failed = 0
    expected_results = {
        ("src/components/Button.vue", 1, "./Card"): "src/components/Card.vue",
        ("src/components/Button.vue", 2, "../utils"): "src/utils.ts",
        ("src/components/Button.vue", 3, "../api"): "src/api/index.ts",
        ("src/components/Button.vue", 4, "../../lib/shared"): "lib/shared.js",
        ("src/api/client.ts", 1, "./index"): "src/api/index.ts",
        ("src/index.ts", 1, "./utils"): "src/utils.ts",
        ("src/index.ts", 2, "lodash"): None,  # Bare specifier - should not resolve
        ("src/index.ts", 3, "./nonexistent"): None,  # File doesn't exist
    }

    for file, line, package, resolved in results:
        key = (file, line, package)
        expected = expected_results.get(key)
        status = "PASS" if resolved == expected else "FAIL"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        resolved_display = resolved or "(NULL)"
        expected_display = expected or "(NULL)"

        print(f"{file:<35} {line:<5} {package:<25} {resolved_display:<30} [{status}]")
        if status == "FAIL":
            print(f"  Expected: {expected_display}")

    print("-" * 100)
    print(f"\nResults: {passed} passed, {failed} failed")

    return failed == 0


def verify_schema():
    """Verify schema has resolved_path column."""
    print("\n=== Schema Verification ===\n")

    from theauditor.indexer.schemas.node_schema import IMPORT_STYLES

    columns = [c.name for c in IMPORT_STYLES.columns]
    has_resolved_path = "resolved_path" in columns

    print(f"IMPORT_STYLES columns: {columns}")
    print(f"Has resolved_path: {has_resolved_path}")

    if has_resolved_path:
        print("Schema verification: PASS")
        return True
    else:
        print("Schema verification: FAIL - resolved_path column missing!")
        return False


def verify_database_method():
    """Verify add_import_style accepts resolved_path parameter."""
    print("\n=== Database Method Verification ===\n")

    import inspect
    from theauditor.indexer.database.node_database import NodeDatabaseMixin

    sig = inspect.signature(NodeDatabaseMixin.add_import_style)
    params = list(sig.parameters.keys())

    has_resolved_path = "resolved_path" in params

    print(f"add_import_style parameters: {params}")
    print(f"Has resolved_path param: {has_resolved_path}")

    if has_resolved_path:
        print("Database method verification: PASS")
        return True
    else:
        print("Database method verification: FAIL - resolved_path parameter missing!")
        return False


def main():
    print("=" * 60)
    print("vue-inmemory-module-resolution Verification")
    print("=" * 60)

    # Verify schema
    schema_ok = verify_schema()

    # Verify database method
    method_ok = verify_database_method()

    # Create test database and run resolution
    db_path = create_test_database()
    try:
        resolution_ok = verify_resolution(db_path)
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)

    all_passed = schema_ok and method_ok and resolution_ok

    print(f"Schema:     {'PASS' if schema_ok else 'FAIL'}")
    print(f"DB Method:  {'PASS' if method_ok else 'FAIL'}")
    print(f"Resolution: {'PASS' if resolution_ok else 'FAIL'}")
    print(f"\nOverall:    {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
