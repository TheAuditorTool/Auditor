"""
FORENSIC AUDIT SCRIPT v1.0
Target: Data Integrity & 'Zero Fallback' Violations
Author: Lead Auditor (Gemini)
"""

import sqlite3
import os
import sys
import glob
import re
from pathlib import Path

# --- CONFIGURATION (WINDOWS PATH HARDCODED) ---
ROOT_PATH = "C:/Users/santa/Desktop/TheAuditor"
DB_PATH = os.path.join(ROOT_PATH, ".pf/repo_index.db")

# Tables that MUST have data in a healthy repo
CRITICAL_TABLES = [
    "files",
    "symbols",
    "assignments",
    "python_routes",
    "graphql_fields",
    "react_components",
    "terraform_resources"
]

def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title.upper()}")
    print("=" * 60)

def audit_database():
    print_header("1. DATABASE CENSUS (The Truth)")

    if not os.path.exists(DB_PATH):
        print(f"[CRITICAL] Database NOT found at: {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        print(f"Total Tables Found: {len(tables)}")
        print("-" * 60)
        print(f"{'TABLE NAME':<40} | {'ROWS':<10} | {'STATUS'}")
        print("-" * 60)

        empty_critical = []
        empty_tables = []
        populated_tables = []

        for table in sorted(tables):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            status = "OK"
            if count == 0:
                status = "EMPTY"
                empty_tables.append(table)
                if table in CRITICAL_TABLES:
                    status = "!! CRITICAL EMPTY !!"
                    empty_critical.append(table)
            else:
                populated_tables.append((table, count))

            # Show all tables with status
            if count == 0 or table in CRITICAL_TABLES or count > 1000:
                print(f"{table:<40} | {count:<10} | {status}")

        print("-" * 60)
        print(f"\nSUMMARY: {len(populated_tables)} populated, {len(empty_tables)} empty")

        if empty_critical:
            print(f"\n[FAIL] CRITICAL tables are EMPTY: {', '.join(empty_critical)}")
        else:
            print("[PASS] All critical tables contain data.")

        # Check for path format consistency
        print_header("1b. PATH FORMAT AUDIT")

        # Check files table for backslashes
        cursor.execute("SELECT COUNT(*) FROM files WHERE path LIKE '%\\\\%'")
        backslash_files = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM files")
        total_files = cursor.fetchone()[0]

        print(f"Files with backslashes: {backslash_files} / {total_files}")
        if backslash_files > 0:
            print("[FAIL] Backslash paths detected in files table!")
            cursor.execute("SELECT path FROM files WHERE path LIKE '%\\\\%' LIMIT 5")
            for row in cursor.fetchall():
                print(f"  Example: {row[0]}")
        else:
            print("[PASS] All file paths use forward slashes.")

        # Check refs table
        cursor.execute("SELECT COUNT(*) FROM refs WHERE value LIKE '%\\\\%'")
        backslash_refs = cursor.fetchone()[0]
        print(f"Refs with backslashes: {backslash_refs}")
        if backslash_refs > 0:
            print("[WARN] Backslash paths in refs.value column")

        # Check symbols table
        cursor.execute("SELECT COUNT(*) FROM symbols WHERE path LIKE '%\\\\%'")
        backslash_symbols = cursor.fetchone()[0]
        print(f"Symbols with backslashes: {backslash_symbols}")
        if backslash_symbols > 0:
            print("[FAIL] Backslash paths in symbols.path column!")

        conn.close()

    except Exception as e:
        print(f"[CRITICAL] Database Audit Failed: {e}")
        import traceback
        traceback.print_exc()

def audit_codebase():
    print_header("2. STATIC ANALYSIS (Zero Fallback Violations)")

    # Python files only for now
    search_path = os.path.join(ROOT_PATH, "theauditor/**/*.py")
    files = glob.glob(search_path, recursive=True)

    findings = []

    for file_path in files:
        # Skip this script and tests
        if "forensic_audit.py" in file_path or "test" in file_path.lower():
            continue

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.split('\n')

            rel_path = os.path.relpath(file_path, ROOT_PATH)

            for i, line in enumerate(lines):
                line_num = i + 1
                stripped = line.strip()

                # Check 1: except ... pass (inline)
                if re.search(r"except\s*.*:\s*pass\s*$", stripped):
                    findings.append(f"[VIOLATION] Silent 'except: pass' at {rel_path}:{line_num}")
                    findings.append(f"    {stripped}")

                # Check 2: except Exception followed by pass on next line
                if re.match(r"except\s+(Exception|BaseException)\s*(as\s+\w+)?:", stripped):
                    if i + 1 < len(lines) and lines[i+1].strip() == "pass":
                        findings.append(f"[VIOLATION] 'except Exception: pass' at {rel_path}:{line_num}")
                        findings.append(f"    {stripped} -> pass")

                # Check 3: verify=False, strict=False, check=False
                if re.search(r"\b(verify|strict|check)\s*=\s*False\b", stripped):
                    # Skip if it's a function definition or comment
                    if not stripped.startswith("#") and "def " not in stripped:
                        findings.append(f"[WARN] Safety disabled at {rel_path}:{line_num}")
                        findings.append(f"    {stripped}")

        except Exception as e:
            print(f"[ERROR] Could not read {file_path}: {e}")

    if not findings:
        print("[PASS] No obvious 'Silent Swallow' or 'Safety Off' patterns found.")
    else:
        for f in findings:
            print(f)
        print(f"\n[RESULT] Found {len([f for f in findings if f.startswith('[')])} potential violations.")

def audit_orchestrator():
    print_header("3. ORCHESTRATOR LOGIC CHECK")

    orch_path = os.path.join(ROOT_PATH, "theauditor/indexer/orchestrator.py")
    if not os.path.exists(orch_path):
        print(f"[ERROR] Orchestrator not found at {orch_path}")
        return

    try:
        with open(orch_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for proper error handling
        has_findings_batch = "write_findings_batch" in content
        has_extraction_error = "extraction_error" in content or "Extraction FAILED" in content

        if has_findings_batch and has_extraction_error:
            print("[PASS] Orchestrator has 'Fail Loud' logic (findings batch + error logging).")
        elif has_extraction_error:
            print("[PASS] Orchestrator logs extraction failures visibly.")
        else:
            print("[WARN] Orchestrator may have silent failure paths. Manual review needed.")

        # Count try-except blocks
        try_count = len(re.findall(r'\btry\s*:', content))
        except_count = len(re.findall(r'\bexcept\s+', content))
        print(f"Try blocks: {try_count}, Except blocks: {except_count}")

    except Exception as e:
        print(f"[ERROR] Analyzing orchestrator: {e}")

def audit_graph_strategies():
    print_header("4. GRAPH STRATEGY INTEGRITY")

    strategies_path = os.path.join(ROOT_PATH, "theauditor/graph/strategies/*.py")
    files = glob.glob(strategies_path)

    for file_path in files:
        rel_path = os.path.relpath(file_path, ROOT_PATH)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for try-except that returns empty
            empty_return_pattern = r'except.*:\s*\n.*return\s*\{["\']nodes["\']\s*:\s*\[\]'
            if re.search(empty_return_pattern, content, re.MULTILINE):
                print(f"[VIOLATION] {rel_path}: Returns empty graph on exception (Silent Failure)")

            # Check for proper crash behavior (no try-except around strategy.build)
            if "except Exception" in content and "return {" in content:
                # More detailed check
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "except Exception" in line or "except Exception as" in line:
                        # Check next few lines for empty return
                        for j in range(i+1, min(i+5, len(lines))):
                            if '"nodes": []' in lines[j] or "'nodes': []" in lines[j]:
                                print(f"[WARN] {rel_path}:{i+1}: May return empty on failure")
                                break

        except Exception as e:
            print(f"[ERROR] {rel_path}: {e}")

    print("[INFO] Strategy audit complete.")

if __name__ == "__main__":
    print("=" * 60)
    print(" THEAUDITOR FORENSIC DATA AUTOPSY v1.0")
    print(" Target: Data Integrity & Zero Fallback Violations")
    print("=" * 60)
    print(f"Root: {ROOT_PATH}")
    print(f"DB:   {DB_PATH}")

    audit_database()
    audit_codebase()
    audit_orchestrator()
    audit_graph_strategies()

    print("\n" + "="*60)
    print(" AUDIT COMPLETE")
    print("="*60)
