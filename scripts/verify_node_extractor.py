"""
Node/JavaScript Extractor Verification (Wave 2b)
=================================================
Tests the JavaScript/TypeScript extractor environment and build integrity.

This catches:
  - Missing extractor bundle (extractor.cjs)
  - Node.js not installed or not in PATH
  - Build out of sync with source
  - Bundle loading failures

Exit codes:
  0 = All checks passed
  1 = Warnings (non-fatal issues)
  2 = Critical errors (extractor is broken)

Author: TheAuditor Team
"""
import sys
import os
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def run_command(cmd: list, cwd: str = None) -> tuple[int, str, str]:
    """Run a command and return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out after 30 seconds"
    except FileNotFoundError:
        return -2, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -3, "", str(e)


def verify_node_extractor() -> int:
    """Run Node extractor verification. Returns exit code."""
    print("=" * 60)
    print("NODE/JAVASCRIPT EXTRACTOR VERIFICATION (Wave 2b)")
    print("=" * 60)

    errors = 0
    warnings = 0

    # 1. Check Node.js installation
    print("\n[1] Checking Node.js installation...")

    node_cmd = "node"
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"

    code, stdout, stderr = run_command([node_cmd, "--version"])
    if code == 0:
        node_version = stdout.strip()
        print(f"    [OK] Node.js version: {node_version}")

        # Check version is >= 18.x
        try:
            major = int(node_version.lstrip("v").split(".")[0])
            if major < 18:
                print(f"    [WARN] Node.js {node_version} is old. Recommended: >= 18.x")
                warnings += 1
        except ValueError:
            pass
    else:
        print(f"    [CRITICAL] Node.js not found or not working")
        print(f"               Error: {stderr}")
        return 2

    # 2. Check npm availability
    print("\n[2] Checking npm availability...")
    code, stdout, stderr = run_command([npm_cmd, "--version"])
    if code == 0:
        npm_version = stdout.strip()
        print(f"    [OK] npm version: {npm_version}")
    else:
        print(f"    [WARN] npm not found - may need manual installation")
        print(f"           Error: {stderr}")
        warnings += 1

    # 3. Load build guard and check paths
    print("\n[3] Loading JavaScript build guard...")
    try:
        from theauditor.indexer.js_build_guard import JavaScriptBuildGuard, get_js_project_path

        js_project = get_js_project_path()
        print(f"    [OK] JS project path: {js_project}")

        guard = JavaScriptBuildGuard(js_project)
        print(f"    [OK] Build guard initialized")
    except Exception as e:
        print(f"    [CRITICAL] Failed to load build guard: {e}")
        return 2

    # 4. Check extractor bundle exists
    print("\n[4] Checking extractor bundle...")
    if guard.artifact_file.exists():
        size_kb = guard.artifact_file.stat().st_size / 1024
        print(f"    [OK] Bundle exists: {guard.artifact_file.name} ({size_kb:.1f} KB)")
    else:
        print(f"    [CRITICAL] Bundle NOT FOUND: {guard.artifact_file}")
        print(f"               Run: cd {js_project} && npm install && npm run build")
        return 2

    # 5. Check source files exist
    print("\n[5] Checking TypeScript source files...")
    source_files = [
        js_project / "package.json",
        js_project / "tsconfig.json",
        js_project / "src" / "main.ts",
        js_project / "src" / "schema.ts",
    ]

    missing_sources = []
    for f in source_files:
        if not f.exists():
            missing_sources.append(f.name)

    if missing_sources:
        print(f"    [CRITICAL] Missing source files: {missing_sources}")
        errors += 1
    else:
        print(f"    [OK] Core source files present")

    # 6. Check build signature
    print("\n[6] Checking build signature (source/build sync)...")
    try:
        current_hash = guard.get_source_hash()
        stored_hash = guard.get_stored_signature()

        if stored_hash is None:
            print(f"    [WARN] No build signature found - cannot verify sync")
            warnings += 1
        elif current_hash != stored_hash:
            print(f"    [WARN] Build may be out of sync with source")
            print(f"           Current hash: {current_hash[:16]}...")
            print(f"           Stored hash:  {stored_hash[:16]}...")
            print(f"           Run: npm run build in {js_project}")
            warnings += 1
        else:
            print(f"    [OK] Build signature matches source (in sync)")
    except Exception as e:
        print(f"    [WARN] Could not check build signature: {e}")
        warnings += 1

    # 7. Test bundle can be loaded by Node
    print("\n[7] Testing bundle integrity (Node.js load test)...")
    test_script = f'''
try {{
    const extractor = require("{str(guard.artifact_file).replace(chr(92), '/')}");
    // The bundle loads successfully if require() doesn't throw
    // It may print warnings about optional deps (Vue) which is fine
    console.log("BUNDLE_LOADED");

    // Check for expected exports
    const hasExports = typeof extractor === 'object' || typeof extractor === 'function';
    if (hasExports) {{
        console.log("BUNDLE_OK");
    }} else {{
        console.log("BUNDLE_EMPTY");
    }}
}} catch (e) {{
    console.log("BUNDLE_LOAD_ERROR: " + e.message);
}}
'''
    code, stdout, stderr = run_command([node_cmd, "-e", test_script])

    # Note: stderr may contain Vue warnings which are fine
    vue_warnings = "VUE" in stderr.upper() or "@vue" in stderr

    if "BUNDLE_LOADED" in stdout and "BUNDLE_OK" in stdout:
        if vue_warnings:
            print(f"    [OK] Bundle loads correctly (Vue support disabled - optional)")
        else:
            print(f"    [OK] Bundle loads and exports correctly")
    elif "BUNDLE_LOADED" in stdout:
        print(f"    [WARN] Bundle loads but exports may be incomplete")
        warnings += 1
    elif "BUNDLE_LOAD_ERROR" in stdout:
        print(f"    [CRITICAL] Bundle failed to load")
        print(f"               {stdout.strip()}")
        errors += 1
    else:
        # Even if we get an error JSON, the bundle loaded
        if vue_warnings and '"error"' in stderr:
            # Bundle loaded but returned usage error (expected without input)
            print(f"    [OK] Bundle loads correctly (Vue optional, requires input)")
        else:
            print(f"    [WARN] Unexpected bundle test output")
            print(f"               stdout: {stdout.strip()[:100]}")
            warnings += 1

    # 8. Check node_modules
    print("\n[8] Checking node_modules...")
    node_modules = js_project / "node_modules"
    if node_modules.exists():
        # Count top-level packages
        pkg_count = len([d for d in node_modules.iterdir() if d.is_dir() and not d.name.startswith(".")])
        print(f"    [OK] node_modules exists with ~{pkg_count} packages")
    else:
        print(f"    [WARN] node_modules missing - run: npm install")
        warnings += 1

    # 9. Check package.json for required scripts
    print("\n[9] Checking package.json scripts...")
    try:
        import json
        pkg_json = js_project / "package.json"
        with open(pkg_json) as f:
            pkg_data = json.load(f)

        scripts = pkg_data.get("scripts", {})
        required_scripts = ["build"]

        missing_scripts = [s for s in required_scripts if s not in scripts]
        if missing_scripts:
            print(f"    [WARN] Missing npm scripts: {missing_scripts}")
            warnings += 1
        else:
            print(f"    [OK] Required npm scripts present: {required_scripts}")

    except Exception as e:
        print(f"    [WARN] Could not check package.json: {e}")
        warnings += 1

    # Final verdict
    print("\n" + "=" * 60)
    if errors > 0:
        print(f"[FAIL] Node extractor verification failed with {errors} error(s)")
        print("       Fix errors and re-run. JS/TS extraction will not work.")
        return 2
    elif warnings > 0:
        print(f"[PASS] Node extractor verification passed with {warnings} warning(s)")
        print("       JS/TS extraction should work but may have issues.")
        return 1
    else:
        print("[PASS] Node extractor verification passed - all checks clean")
        return 0


if __name__ == "__main__":
    exit_code = verify_node_extractor()
    sys.exit(exit_code)
