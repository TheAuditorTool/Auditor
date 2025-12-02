"""
Schema Contract Verification (Wave 1)
=====================================
Validates that schema definitions are internally consistent and can create
valid SQLite tables. Runs entirely in memory - no disk I/O required.

Checks:
  1. All FLUSH_ORDER tables exist in TABLES registry
  2. All table schemas can create valid SQL
  3. Column definitions are syntactically correct
  4. Foreign key references point to valid tables
  5. No duplicate table definitions

Exit codes:
  0 = All checks passed
  1 = Warnings (non-fatal issues)
  2 = Critical errors (schema is broken)

Author: TheAuditor Team
"""
import sqlite3
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def verify_schema() -> int:
    """Run all schema verification checks. Returns exit code."""
    print("=" * 60)
    print("SCHEMA CONTRACT VERIFICATION (Wave 1)")
    print("=" * 60)

    errors = 0
    warnings = 0

    # 1. Import schema module
    print("\n[1] Loading schema module...")
    try:
        from theauditor.indexer.schema import TABLES, FLUSH_ORDER, validate_schema_contract
        print(f"    [OK] Loaded {len(TABLES)} table definitions")
        print(f"    [OK] Loaded {len(FLUSH_ORDER)} flush order entries")
    except Exception as e:
        print(f"    [CRITICAL] Failed to import schema: {e}")
        return 2

    # 2. Run built-in contract validation (already runs on import, but let's be explicit)
    print("\n[2] Validating FLUSH_ORDER <-> TABLES contract...")
    contract_errors = validate_schema_contract()
    if contract_errors:
        for err in contract_errors:
            print(f"    [CRITICAL] {err}")
            errors += 1
    else:
        print("    [OK] All FLUSH_ORDER tables exist in TABLES")

    # 3. In-memory SQL creation test
    print("\n[3] Testing SQL generation (in-memory database)...")
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    creation_failures = []
    for table_name, table_schema in TABLES.items():
        try:
            # Generate and execute CREATE TABLE
            sql = table_schema.create_table_sql()
            cursor.execute(sql)

            # Also create indexes
            for idx_sql in table_schema.create_indexes_sql():
                cursor.execute(idx_sql)

        except Exception as e:
            creation_failures.append((table_name, str(e)))

    if creation_failures:
        print(f"    [CRITICAL] {len(creation_failures)} tables failed to create:")
        for table_name, error in creation_failures[:5]:
            print(f"        - {table_name}: {error[:80]}")
        if len(creation_failures) > 5:
            print(f"        ... and {len(creation_failures) - 5} more")
        errors += len(creation_failures)
    else:
        print(f"    [OK] All {len(TABLES)} tables created successfully")

    # 4. Column type validation
    print("\n[4] Validating column definitions...")
    VALID_TYPES = {"TEXT", "INTEGER", "REAL", "BLOB", "BOOLEAN"}
    type_warnings = []

    for table_name, table_schema in TABLES.items():
        for col in table_schema.columns:
            col_type_upper = col.type.upper()
            if col_type_upper not in VALID_TYPES:
                type_warnings.append(f"{table_name}.{col.name}: {col.type}")

    if type_warnings:
        print(f"    [WARN] {len(type_warnings)} non-standard column types:")
        for w in type_warnings[:5]:
            print(f"        - {w}")
        if len(type_warnings) > 5:
            print(f"        ... and {len(type_warnings) - 5} more")
        warnings += 1
    else:
        print("    [OK] All column types are standard SQLite types")

    # 5. Foreign key reference validation
    print("\n[5] Validating foreign key references...")
    fk_errors = []

    for table_name, table_schema in TABLES.items():
        for fk in table_schema.foreign_keys:
            # Check if foreign table exists
            if hasattr(fk, 'foreign_table'):
                if fk.foreign_table not in TABLES:
                    fk_errors.append(f"{table_name} -> {fk.foreign_table} (table not found)")
            elif isinstance(fk, tuple) and len(fk) >= 2:
                # Legacy tuple format: (local_col, foreign_table, foreign_col, ...)
                if fk[1] not in TABLES:
                    fk_errors.append(f"{table_name} -> {fk[1]} (table not found)")

    if fk_errors:
        print(f"    [CRITICAL] {len(fk_errors)} foreign key reference errors:")
        for err in fk_errors[:5]:
            print(f"        - {err}")
        if len(fk_errors) > 5:
            print(f"        ... and {len(fk_errors) - 5} more")
        errors += len(fk_errors)
    else:
        total_fks = sum(len(ts.foreign_keys) for ts in TABLES.values())
        print(f"    [OK] All {total_fks} foreign key references are valid")

    # 6. Check for tables with no columns (broken schema)
    print("\n[6] Checking for empty table definitions...")
    empty_tables = [name for name, schema in TABLES.items() if not schema.columns]
    if empty_tables:
        print(f"    [CRITICAL] {len(empty_tables)} tables have no columns:")
        for t in empty_tables:
            print(f"        - {t}")
        errors += len(empty_tables)
    else:
        print("    [OK] All tables have at least one column")

    # 7. Schema domain breakdown
    print("\n[7] Schema domain summary:")
    try:
        from theauditor.indexer.schemas.core_schema import CORE_TABLES
        from theauditor.indexer.schemas.python_schema import PYTHON_TABLES
        from theauditor.indexer.schemas.node_schema import NODE_TABLES
        from theauditor.indexer.schemas.infrastructure_schema import INFRASTRUCTURE_TABLES
        from theauditor.indexer.schemas.planning_schema import PLANNING_TABLES
        from theauditor.indexer.schemas.security_schema import SECURITY_TABLES
        from theauditor.indexer.schemas.graphql_schema import GRAPHQL_TABLES
        from theauditor.indexer.schemas.frameworks_schema import FRAMEWORKS_TABLES

        domains = [
            ("Core", CORE_TABLES),
            ("Python", PYTHON_TABLES),
            ("Node/JS", NODE_TABLES),
            ("Infrastructure", INFRASTRUCTURE_TABLES),
            ("Planning", PLANNING_TABLES),
            ("Security", SECURITY_TABLES),
            ("GraphQL", GRAPHQL_TABLES),
            ("Frameworks", FRAMEWORKS_TABLES),
        ]

        for name, tables in domains:
            print(f"    {name.ljust(15)}: {len(tables)} tables")

    except ImportError as e:
        print(f"    [WARN] Could not load domain schemas: {e}")
        warnings += 1

    conn.close()

    # Final verdict
    print("\n" + "=" * 60)
    if errors > 0:
        print(f"[FAIL] Schema verification failed with {errors} error(s), {warnings} warning(s)")
        return 2
    elif warnings > 0:
        print(f"[PASS] Schema verification passed with {warnings} warning(s)")
        return 1
    else:
        print("[PASS] Schema verification passed - all checks clean")
        return 0


if __name__ == "__main__":
    exit_code = verify_schema()
    sys.exit(exit_code)
