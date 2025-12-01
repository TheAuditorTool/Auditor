"""
Database Integrity & Fidelity Verifier
======================================
Run this to prove your database is clean before building on top of it.

Usage:
    python scripts/verify_db.py [path/to/repo_index.db]

If no path given, defaults to .pf/repo_index.db

Author: TheAuditor Team
"""
import sqlite3
import sys
from pathlib import Path


def check_integrity(db_path: Path) -> int:
    """
    Run all integrity checks on the database.
    Returns exit code: 0 = all good, 1 = warnings, 2 = errors
    """
    if not db_path.exists():
        print(f"[ERROR] Database not found at {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"[INFO] Auditing Database: {db_path}\n")

    exit_code = 0

    # ==========================================================================
    # 1. SCHEMA / ORM MODEL VERIFICATION
    # ==========================================================================
    print("--- [1] Schema / ORM Model Verification ---")

    # Check Sequelize models
    cursor.execute("SELECT count(*) FROM sequelize_models")
    sequelize_count = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM sequelize_model_fields")
    sequelize_fields = cursor.fetchone()[0]

    # Check Prisma models
    cursor.execute("SELECT count(*) FROM prisma_models")
    prisma_count = cursor.fetchone()[0]

    # Check Python ORM models
    cursor.execute("SELECT count(*) FROM python_orm_models")
    python_orm_count = cursor.fetchone()[0]

    total_models = sequelize_count + prisma_count + python_orm_count

    if total_models == 0:
        print("[WARN] No ORM models found (Sequelize/Prisma/Python)")
        print("       This may be expected if the codebase uses raw SQL only.")
        # Check raw SQL queries
        cursor.execute("SELECT count(*) FROM sql_queries")
        sql_count = cursor.fetchone()[0]
        print(f"       (Found {sql_count} raw SQL queries)")
        exit_code = max(exit_code, 1)
    else:
        print(f"[OK] Found {total_models} ORM models total:")
        print(f"     - Sequelize: {sequelize_count} models, {sequelize_fields} fields")
        print(f"     - Prisma: {prisma_count} models")
        print(f"     - Python ORM: {python_orm_count} models")

        # Show sample models
        if sequelize_count > 0:
            cursor.execute("SELECT model_name, file FROM sequelize_models LIMIT 3")
            for row in cursor.fetchall():
                fname = row["file"].split("/")[-1] if row["file"] else "unknown"
                print(f"       * {row['model_name']} ({fname})")

    # Check for orphaned Sequelize fields (fields without parent model)
    if sequelize_fields > 0 and sequelize_count == 0:
        print("[WARN] Orphaned Sequelize fields detected!")
        print(f"       {sequelize_fields} fields exist but 0 models registered")
        cursor.execute("""
            SELECT DISTINCT model_name, file FROM sequelize_model_fields LIMIT 3
        """)
        for row in cursor.fetchall():
            fname = row["file"].split("/")[-1] if row["file"] else "unknown"
            print(f"       - Model '{row['model_name']}' fields in {fname} (not in sequelize_models)")
        exit_code = max(exit_code, 1)

    # ==========================================================================
    # 2. LOGICAL DUPLICATE CHECK
    # ==========================================================================
    print("\n--- [2] Logical Duplicate Check ---")

    # Check for symbols defined on the exact same line (should be rare)
    cursor.execute("""
        SELECT path, line, name, type, count(*) as c
        FROM symbols
        GROUP BY path, line, name, type
        HAVING c > 1
        LIMIT 10
    """)
    dupes = cursor.fetchall()

    if dupes:
        print(f"[WARN] Found {len(dupes)} logical duplicates (same name/line/type):")
        for row in dupes[:3]:
            print(f"       - {row['name']} ({row['type']}) at {row['path']}:{row['line']} (x{row['c']})")
        if len(dupes) > 3:
            print(f"       ... and {len(dupes) - 3} more")
        exit_code = max(exit_code, 1)
    else:
        print("[OK] No logical symbol duplicates found.")

    # ==========================================================================
    # 3. ORPHAN CHECK (Foreign Key Logic)
    # ==========================================================================
    print("\n--- [3] Orphan Check (Data Integrity) ---")

    # Check assignment_sources -> assignments linkage
    cursor.execute("""
        SELECT count(*) FROM assignment_sources src
        LEFT JOIN assignments a ON
            src.assignment_file = a.file AND
            src.assignment_line = a.line AND
            src.assignment_target = a.target_var
        WHERE a.file IS NULL
    """)
    orphan_sources = cursor.fetchone()[0]

    if orphan_sources > 0:
        print(f"[WARN] Found {orphan_sources} orphaned assignment_sources")
        print("       (Sources that don't link to valid assignments)")
        exit_code = max(exit_code, 1)
    else:
        print("[OK] All assignment_sources link to valid assignments.")

    # Check function_call_args without matching symbols
    cursor.execute("""
        SELECT count(*) FROM function_call_args fca
        WHERE fca.callee_function IS NOT NULL
          AND fca.callee_function != ''
          AND NOT EXISTS (
            SELECT 1 FROM symbols s
            WHERE s.name = fca.callee_function
              AND s.type IN ('function', 'method', 'call')
          )
        LIMIT 1
    """)
    # This is expected to have some - external library calls won't have symbols
    # So we just report it as informational

    # ==========================================================================
    # 4. SYNTAX ERROR FINDINGS CHECK
    # ==========================================================================
    print("\n--- [4] Syntax Error Findings ---")

    cursor.execute("""
        SELECT count(*) FROM findings_consolidated
        WHERE rule = 'syntax_error'
    """)
    syntax_errors = cursor.fetchone()[0]

    if syntax_errors > 0:
        print(f"[INFO] Found {syntax_errors} files with syntax errors (recorded as findings)")
        cursor.execute("""
            SELECT file, message FROM findings_consolidated
            WHERE rule = 'syntax_error'
            LIMIT 3
        """)
        for row in cursor.fetchall():
            fname = row["file"].split("/")[-1] if row["file"] else "unknown"
            msg = row["message"][:60] + "..." if len(row["message"]) > 60 else row["message"]
            print(f"       - {fname}: {msg}")
    else:
        print("[OK] No syntax errors recorded in findings.")

    # ==========================================================================
    # 5. TAINT ANALYSIS READINESS
    # ==========================================================================
    print("\n--- [5] Taint Analysis Readiness ---")

    # Check if we have sources (API endpoints, env vars, etc.)
    cursor.execute("SELECT count(*) FROM api_endpoints")
    endpoints = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM env_var_usage")
    env_vars = cursor.fetchone()[0]

    # Check if we have sinks (function calls with dangerous patterns)
    cursor.execute("""
        SELECT count(*) FROM function_call_args
        WHERE callee_function LIKE '%.query%'
           OR callee_function LIKE '%.execute%'
           OR callee_function LIKE 'res.send%'
           OR callee_function LIKE 'res.json%'
    """)
    potential_sinks = cursor.fetchone()[0]

    print(f"[INFO] Taint analysis inputs:")
    print(f"       - API Endpoints (sources): {endpoints}")
    print(f"       - Env Var Usage (sources): {env_vars}")
    print(f"       - Potential Sinks: {potential_sinks}")

    if endpoints == 0 and env_vars == 0:
        print("[WARN] No taint sources found - taint analysis may find nothing")
        exit_code = max(exit_code, 1)

    # ==========================================================================
    # 6. DATABASE STATS SUMMARY
    # ==========================================================================
    print("\n--- [6] Database Stats ---")

    # Core tables with actual names
    stats_tables = [
        ("files", "Files indexed"),
        ("symbols", "Symbols extracted"),
        ("import_specifiers", "Import specifiers"),
        ("api_endpoints", "API endpoints"),
        ("function_call_args", "Function call args"),
        ("assignments", "Assignments"),
        ("variable_usage", "Variable usages"),
        ("func_params", "Function parameters"),
        ("findings_consolidated", "Security findings"),
    ]

    for table, description in stats_tables:
        cursor.execute(f"SELECT count(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   {description.ljust(25)}: {count:,}")

    # ==========================================================================
    # 7. RESOLVED FLOW AUDIT CHECK
    # ==========================================================================
    print("\n--- [7] Resolved Flow Audit ---")

    cursor.execute("SELECT count(*) FROM resolved_flow_audit")
    total_flows = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM resolved_flow_audit WHERE status = 'VULNERABLE'")
    vuln_flows = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM resolved_flow_audit WHERE status = 'SANITIZED'")
    safe_flows = cursor.fetchone()[0]

    print(f"[INFO] Flow resolution results:")
    print(f"       - Total flows: {total_flows:,}")
    print(f"       - Vulnerable: {vuln_flows:,}")
    print(f"       - Sanitized: {safe_flows:,}")

    if total_flows == 0:
        print("[WARN] No flows resolved - run 'aud full' to populate")
        exit_code = max(exit_code, 1)

    # ==========================================================================
    # FINAL VERDICT
    # ==========================================================================
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("[PASS] All integrity checks passed!")
    elif exit_code == 1:
        print("[WARN] Integrity checks passed with warnings")
    else:
        print("[FAIL] Integrity checks failed!")
    print("=" * 60)

    conn.close()
    return exit_code


def main():
    """Main entry point."""
    print("=" * 60)
    print("DATABASE INTEGRITY VERIFIER")
    print("=" * 60)

    # Default path or CLI argument
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    else:
        db_path = Path(".pf/repo_index.db")

    exit_code = check_integrity(db_path)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
