"""
TheAuditor System Health Check (The "Lay of the Land")
======================================================
Master script that orchestrates all verification waves.
Run this BEFORE running `aud full` to identify issues quickly.

Verification Waves:
  1. Schema Contract     - In-memory schema validation
  2a. Python Extractor   - Python extraction isolation test
  2b. Node Extractor     - JavaScript/TypeScript environment check
  3. Storage Layer       - Database CRUD and FK constraint tests
  4. Database Integrity  - (Optional) Full DB audit if repo_index.db exists
  5. Architecture        - (Optional) End-to-end integration tests

Usage:
    python scripts/health_check.py           # Run all waves
    python scripts/health_check.py --quick   # Skip optional waves
    python scripts/health_check.py --wave 3  # Run specific wave only

Exit codes:
  0 = All systems go
  1 = Warnings detected (proceed with caution)
  2 = Critical errors (fix before running aud full)

Author: TheAuditor Team
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent

# Wave definitions
WAVES = [
    {
        "id": 1,
        "name": "Schema Contract",
        "script": "verify_schema.py",
        "required": True,
        "description": "Validates schema definitions and SQL generation",
    },
    {
        "id": "2a",
        "name": "Python Extractor",
        "script": "verify_python_extractor.py",
        "required": True,
        "description": "Tests Python extraction in isolation",
    },
    {
        "id": "2b",
        "name": "Node Extractor",
        "script": "verify_node_extractor.py",
        "required": True,
        "description": "Checks JavaScript/TypeScript build environment",
    },
    {
        "id": "3a",
        "name": "Storage Layer",
        "script": "verify_storage_layer.py",
        "required": True,
        "description": "Tests database CRUD and FK constraints",
    },
    {
        "id": "3b",
        "name": "Graph Layer",
        "script": "verify_graph_layer.py",
        "required": True,
        "description": "Tests graph schema, store, strategies, and builders",
    },
    {
        "id": 4,
        "name": "Database Integrity",
        "script": "verify_db.py",
        "required": False,
        "description": "Full database audit (requires existing repo_index.db)",
        "condition": lambda: (PROJECT_ROOT / ".pf" / "repo_index.db").exists(),
    },
    {
        "id": 5,
        "name": "Architecture",
        "script": "verify_architecture.py",
        "required": False,
        "description": "End-to-end integration tests",
    },
]


def run_wave(wave: dict) -> tuple[int, str]:
    """
    Run a single verification wave.

    Returns:
        (exit_code, status_message)
        exit_code: 0=pass, 1=warnings, 2=errors
    """
    script_path = SCRIPTS_DIR / wave["script"]

    if not script_path.exists():
        return 2, f"Script not found: {wave['script']}"

    # Check condition if present
    if "condition" in wave and not wave["condition"]():
        return 0, "Skipped (condition not met)"

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,  # 2 minute timeout per wave
            cwd=str(PROJECT_ROOT),
        )

        # Parse exit code
        if result.returncode == 0:
            return 0, "PASS"
        elif result.returncode == 1:
            return 1, "PASS (with warnings)"
        else:
            # Print stderr for debugging
            if result.stderr:
                print(f"\n    --- Wave Output ---")
                for line in result.stderr.strip().split("\n")[-10:]:
                    print(f"    {line}")
            return 2, "FAIL"

    except subprocess.TimeoutExpired:
        return 2, "TIMEOUT (>120s)"
    except Exception as e:
        return 2, f"ERROR: {e}"


def main():
    parser = argparse.ArgumentParser(
        description="TheAuditor System Health Check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Skip optional waves (faster, required waves only)"
    )
    parser.add_argument(
        "--wave", type=str,
        help="Run specific wave only (e.g., --wave 3 or --wave 2a)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show full output from each wave"
    )

    args = parser.parse_args()

    # Header
    print("=" * 70)
    print("   THEAUDITOR SYSTEM HEALTH CHECK")
    print("   The 'Lay of the Land' Before Running aud full")
    print("=" * 70)
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Root: {PROJECT_ROOT}")
    print("=" * 70)

    # Determine which waves to run
    waves_to_run = []

    if args.wave:
        # Run specific wave
        target_id = args.wave
        for wave in WAVES:
            if str(wave["id"]) == target_id:
                waves_to_run = [wave]
                break

        if not waves_to_run:
            print(f"\nERROR: Wave '{args.wave}' not found.")
            print("Available waves:", ", ".join(str(w["id"]) for w in WAVES))
            return 2
    else:
        # Run all (or required only if --quick)
        for wave in WAVES:
            if wave["required"] or not args.quick:
                waves_to_run.append(wave)

    # Run waves
    results = []
    overall_status = 0

    for wave in waves_to_run:
        wave_id = str(wave["id"])
        wave_name = wave["name"]

        print(f"\n{'=' * 70}")
        print(f"  WAVE {wave_id}: {wave_name}")
        print(f"  {wave['description']}")
        print("-" * 70)

        exit_code, status = run_wave(wave)
        results.append((wave_id, wave_name, exit_code, status))

        # Update overall status
        if exit_code > overall_status:
            overall_status = exit_code

        # Print result
        status_icon = {0: "[OK]", 1: "[WARN]", 2: "[FAIL]"}.get(exit_code, "[?]")
        print(f"\n  Result: {status_icon} {status}")

        # Stop on critical failure for required waves
        if exit_code == 2 and wave["required"]:
            print(f"\n  BLOCKER DETECTED - Fix this before proceeding.")
            break

    # Summary
    print("\n" + "=" * 70)
    print("   SUMMARY")
    print("=" * 70)

    for wave_id, wave_name, exit_code, status in results:
        icon = {0: "[OK]  ", 1: "[WARN]", 2: "[FAIL]"}.get(exit_code, "[?]")
        print(f"   Wave {wave_id.ljust(3)} {wave_name.ljust(20)} {icon} {status}")

    print("-" * 70)

    # Final verdict
    if overall_status == 0:
        print("   VERDICT: ALL SYSTEMS GO")
        print("   You may now run 'aud full --offline' with confidence.")
    elif overall_status == 1:
        print("   VERDICT: PROCEED WITH CAUTION")
        print("   Some warnings detected. Review them before 'aud full'.")
    else:
        print("   VERDICT: FIX ERRORS BEFORE CONTINUING")
        print("   Critical errors detected. DO NOT run 'aud full' yet.")

    print("=" * 70)

    return overall_status


if __name__ == "__main__":
    sys.exit(main())
