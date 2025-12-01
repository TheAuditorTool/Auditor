"""
Database Integrity & Fidelity Verifier (v2)
============================================
Now checks configuration consistency, logical relationships, and schema drift.

Usage:
    python scripts/verify_db.py [path/to/repo_index.db]

If no path given, defaults to .pf/repo_index.db

Checks performed:
  [0] Configuration Audit - Ensures all tables in TABLES are in FLUSH_ORDER
  [1] Schema / ORM Model Verification
  [2] Logical Duplicate Check
  [3] Orphan Check (Foreign Key Logic)
  [4] Syntax Error Findings
  [5] Taint Analysis Readiness
  [6] Database Stats Summary
  [7] Resolved Flow Audit
  [8] Schema Drift Detection

Author: TheAuditor Team
"""
import importlib.util
import sqlite3
import sys
from pathlib import Path


def load_schema_module(project_root: Path):
    """Dynamically load the schema module to check configuration."""
    schema_path = project_root / "theauditor" / "indexer" / "schema.py"
    if not schema_path.exists():
        print(f"[WARN] Cannot find schema.py at {schema_path}. Skipping config check.")
        return None

    try:
        # Clear any cached module first
        module_names_to_clear = [k for k in sys.modules if k.startswith("theauditor")]
        for name in module_names_to_clear:
            del sys.modules[name]

        # Add project root to path so imports work
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Now import fresh
        from theauditor.indexer.schema import TABLES, FLUSH_ORDER

        # Create a simple namespace object to return
        class SchemaModule:
            pass

        mod = SchemaModule()
        mod.TABLES = TABLES
        mod.FLUSH_ORDER = FLUSH_ORDER
        return mod
    except Exception as e:
        print(f"[WARN] Failed to load schema.py: {e}")
        return None


def check_integrity(db_path: Path, project_root: Path) -> int:
    """
    Run all integrity checks on the database.
    Returns exit code: 0 = all good, 1 = warnings, 2 = critical errors
    """
    if not db_path.exists():
        print(f"[ERROR] Database not found at {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"[INFO] Auditing Database: {db_path}\n")

    exit_code = 0
    errors = 0
    warnings = 0

    # ==========================================================================
    # 0. CONFIGURATION AUDIT (The "FLUSH_ORDER" Catcher)
    # ==========================================================================
    print("--- [0] Configuration Audit (FLUSH_ORDER) ---")

    schema_mod = load_schema_module(project_root)
    if schema_mod:
        defined_tables = set(schema_mod.TABLES.keys())
        flushed_tables = set(t[0] for t in schema_mod.FLUSH_ORDER)

        # Tables that are intentionally NOT flushed (runtime-only or special)
        # These are tables that exist in schema but are populated by other means
        KNOWN_NON_FLUSHED = {
            # Core analysis tables populated during taint/graph phases
            "taint_flows",
            "resolved_flow_audit",
            "cfg_blocks",
            "cfg_edges",
            "cfg_block_statements",
            "cfg_blocks_jsx",
            "cfg_edges_jsx",
            "cfg_block_statements_jsx",
            # Dependency/version tables populated separately
            "dependency_versions",
            "validation_framework_usage",
            # Frontend-specific
            "frontend_api_calls",
            # Tables populated by specific analyzers
            "jwt_patterns",
            "bullmq_queues",
            "bullmq_workers",
            "di_injections",
            # Vue-specific (populated during framework analysis)
            "vue_component_props",
            "vue_component_emits",
            "vue_component_setup_returns",
            # Angular-specific
            "angular_component_styles",
            "angular_module_declarations",
            "angular_module_imports",
            "angular_module_providers",
            "angular_module_exports",
            # GraphQL resolvers (populated during graphql analysis)
            "graphql_resolvers",
            # Tables that exist but are optional
            "findings_consolidated",
        }

        # Check 1: Are there tables defined but NOT flushed (and not in known exceptions)?
        forgotten = defined_tables - flushed_tables - KNOWN_NON_FLUSHED
        if forgotten:
            print(f"[CRITICAL] Tables defined but NOT in FLUSH_ORDER (data will be lost!):")
            for t in sorted(forgotten):
                print(f"           - {t}")
            errors += 1
        else:
            print("[OK] All indexer tables are in FLUSH_ORDER.")

        # Check 2: Are we flushing tables that don't exist in TABLES?
        ghosts = flushed_tables - defined_tables
        if ghosts:
            print(f"[CRITICAL] FLUSH_ORDER contains undefined tables: {sorted(ghosts)}")
            errors += 1
        else:
            print("[OK] All FLUSH_ORDER entries exist in TABLES.")

        # Info: Show counts
        print(f"[INFO] TABLES defined: {len(defined_tables)}, FLUSH_ORDER entries: {len(flushed_tables)}")
    else:
        print("[SKIP] Schema module not loaded, skipping config audit.")
        warnings += 1

    # ==========================================================================
    # 1. SCHEMA / ORM MODEL VERIFICATION
    # ==========================================================================
    print("\n--- [1] Schema / ORM Model Verification ---")

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
        cursor.execute("SELECT count(*) FROM sql_queries")
        sql_count = cursor.fetchone()[0]
        print(f"       (Found {sql_count} raw SQL queries)")
        warnings += 1
    else:
        print(f"[OK] Found {total_models} ORM models total:")
        print(f"     - Sequelize: {sequelize_count} models, {sequelize_fields} fields")
        print(f"     - Prisma: {prisma_count} models")
        print(f"     - Python ORM: {python_orm_count} models")

        if sequelize_count > 0:
            cursor.execute("SELECT model_name, file FROM sequelize_models LIMIT 3")
            for row in cursor.fetchall():
                fname = row["file"].split("/")[-1] if row["file"] else "unknown"
                print(f"       * {row['model_name']} ({fname})")

    # CRITICAL: Check for orphaned Sequelize fields (fields without parent model)
    if sequelize_fields > 0 and sequelize_count == 0:
        print("[CRITICAL] Orphaned Sequelize fields detected!")
        print(f"           {sequelize_fields} fields exist but 0 models registered")
        print("           -> This implies 'sequelize_models' is missing from FLUSH_ORDER")
        cursor.execute("SELECT DISTINCT model_name, file FROM sequelize_model_fields LIMIT 3")
        for row in cursor.fetchall():
            fname = row["file"].split("/")[-1] if row["file"] else "unknown"
            print(f"           - Model '{row['model_name']}' fields in {fname}")
        errors += 1

    # ==========================================================================
    # 2. LOGICAL DUPLICATE CHECK
    # ==========================================================================
    print("\n--- [2] Logical Duplicate Check ---")

    cursor.execute("""
        SELECT path, line, col, name, type, count(*) as c
        FROM symbols
        GROUP BY path, line, col, name, type
        HAVING c > 1
        LIMIT 10
    """)
    dupes = cursor.fetchall()

    if dupes:
        print(f"[WARN] Found {len(dupes)} exact duplicates (same name/line/col/type):")
        for row in dupes[:3]:
            print(f"       - {row['name']} ({row['type']}) at {row['path']}:{row['line']}:{row['col']} (x{row['c']})")
        if len(dupes) > 3:
            print(f"       ... and {len(dupes) - 3} more")
        warnings += 1
    else:
        print("[OK] No exact symbol duplicates found.")

    # ==========================================================================
    # 3. ORPHAN CHECK (Foreign Key Logic)
    # ==========================================================================
    print("\n--- [3] Orphan Check (Data Integrity) ---")

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
        warnings += 1
    else:
        print("[OK] All assignment_sources link to valid assignments.")

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

    cursor.execute("SELECT count(*) FROM api_endpoints")
    endpoints = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM env_var_usage")
    env_vars = cursor.fetchone()[0]

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
        warnings += 1

    # ==========================================================================
    # 6. DATABASE STATS SUMMARY
    # ==========================================================================
    print("\n--- [6] Database Stats ---")

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
        warnings += 1

    # ==========================================================================
    # 8. SCHEMA DRIFT DETECTION
    # ==========================================================================
    print("\n--- [8] Schema Drift Detection ---")

    # Check for commonly confused column names
    schema_checks = [
        ("func_params", "function_line", "Expected 'function_line' in func_params (not 'line')"),
        ("symbols", "line", "Expected 'line' in symbols"),
        ("assignments", "line", "Expected 'line' in assignments"),
    ]

    drift_found = False
    for table, expected_col, message in schema_checks:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = {row["name"] for row in cursor.fetchall()}
        if columns and expected_col not in columns:
            print(f"[CRITICAL] Schema drift: {message}")
            print(f"           Actual columns: {sorted(columns)}")
            drift_found = True
            errors += 1

    if not drift_found:
        print("[OK] No schema drift detected in critical tables.")

    # Check for the specific func_params line vs function_line bug
    cursor.execute("PRAGMA table_info(func_params)")
    func_params_cols = {row["name"] for row in cursor.fetchall()}
    if "line" in func_params_cols and "function_line" not in func_params_cols:
        print("[CRITICAL] func_params has 'line' but code expects 'function_line'!")
        errors += 1
    elif "function_line" in func_params_cols and "line" not in func_params_cols:
        print("[OK] func_params uses 'function_line' (correct).")

    # ==========================================================================
    # FINAL VERDICT
    # ==========================================================================
    print("\n" + "=" * 60)

    if errors > 0:
        exit_code = 2
        print(f"[FAIL] Found {errors} critical error(s) and {warnings} warning(s)")
        print("       Run 'aud full --index' after fixing to rebuild the DB.")
    elif warnings > 0:
        exit_code = 1
        print(f"[WARN] Integrity checks passed with {warnings} warning(s)")
    else:
        exit_code = 0
        print("[PASS] All integrity checks passed!")

    print("=" * 60)

    conn.close()
    return exit_code


def main():
    """Main entry point."""
    print("=" * 60)
    print("DATABASE INTEGRITY VERIFIER v2")
    print("=" * 60)

    # Default path or CLI argument
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    else:
        db_path = Path(".pf/repo_index.db")

    # Determine project root (parent of scripts/)
    project_root = Path(__file__).parent.parent

    exit_code = check_integrity(db_path, project_root)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
