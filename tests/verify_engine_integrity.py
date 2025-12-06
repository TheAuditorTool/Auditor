"""
Verification Script: Taint Engine Integrity Check (Post-Fix)

Tests that the fixes for H1, H2, H3 are working correctly:
- H1: Windows path normalization (split-brain fix)
- H2: Debug logging for malformed node IDs (silent failure fix)
- H3: Parser handles :: in function names (parser fragility fix)

Run: cd C:/Users/santa/Desktop/TheAuditor && .venv/Scripts/python.exe tests/verify_engine_integrity.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from theauditor.taint.access_path import AccessPath


def test_h1_windows_path_normalization():
    """
    H1 FIX: Test that Windows paths are normalized to Unix-style.

    After fix: AccessPath('a\\b') should equal AccessPath('a/b')
    """
    print("\n" + "="*70)
    print("[H1] TESTING: Windows Path Normalization (POST-FIX)")
    print("="*70)

    unix_path = "src/utils/helper.js"
    windows_path = "src\\utils\\helper.js"

    # Create AccessPath objects with mixed slash styles
    ap_unix = AccessPath(file=unix_path, function="main", base="x", fields=())
    ap_windows = AccessPath(file=windows_path, function="main", base="x", fields=())

    print(f"\n  Input Unix Path:    '{unix_path}'")
    print(f"  Input Windows Path: '{windows_path}'")
    print(f"\n  After normalization:")
    print(f"  Unix file:    '{ap_unix.file}'")
    print(f"  Windows file: '{ap_windows.file}'")

    # Test: Windows path should be normalized to Unix
    path_normalized = (ap_windows.file == "src/utils/helper.js")
    print(f"\n  Windows path normalized to forward slashes: {path_normalized}")

    # Test: Both objects should be equal now
    objects_equal = (ap_unix == ap_windows)
    print(f"  AccessPath objects equal: {objects_equal}")

    # Test: Hashes should match
    hashes_equal = (hash(ap_unix) == hash(ap_windows))
    print(f"  Hashes equal: {hashes_equal}")

    # Test: node_ids should match
    node_ids_equal = (ap_unix.node_id == ap_windows.node_id)
    print(f"  node_id strings equal: {node_ids_equal}")

    if path_normalized and objects_equal and hashes_equal and node_ids_equal:
        print("\n  RESULT: PASS - H1 FIX VERIFIED")
        print("  Split-brain vulnerability is ELIMINATED.")
        return True
    else:
        print("\n  RESULT: FAIL - H1 FIX NOT WORKING")
        return False


def test_h2_logging_check():
    """
    H2 FIX: Verify debug logging code exists for malformed node IDs.

    We can't easily test stderr output, so we verify the code change exists.
    """
    print("\n" + "="*70)
    print("[H2] TESTING: Silent Failure Fix (Code Inspection)")
    print("="*70)

    ifds_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "theauditor", "taint", "ifds_analyzer.py"
    )

    with open(ifds_path, "r") as f:
        content = f.read()

    # Check for the warning log pattern
    warning_pattern = "Dropped malformed node ID"
    warning_found = warning_pattern in content

    # Check that 'else: pass' is gone (replaced with logging)
    silent_pass_pattern = "else:\n                pass"
    silent_pass_found = silent_pass_pattern in content

    print(f"\n  Checking ifds_analyzer.py:")
    print(f"  Warning log pattern found: {warning_found}")
    print(f"  Silent 'else: pass' removed: {not silent_pass_found}")

    if warning_found and not silent_pass_found:
        print("\n  RESULT: PASS - H2 FIX VERIFIED")
        print("  Malformed node IDs will now be logged in debug mode.")
        return True
    else:
        print("\n  RESULT: FAIL - H2 FIX NOT COMPLETE")
        if not warning_found:
            print("  Missing: Warning log statement")
        if silent_pass_found:
            print("  Still present: Silent 'else: pass' pattern")
        return False


def test_h3_parser_robustness():
    """
    H3 FIX: Test that parser handles :: in function names correctly.

    After fix: file::A::B::C::var should parse as:
    - file = 'file'
    - function = 'A::B::C'
    - base = 'var'
    """
    print("\n" + "="*70)
    print("[H3] TESTING: Parser Robustness (POST-FIX)")
    print("="*70)

    test_cases = [
        # (input, expected_file, expected_func, expected_base, description)
        (
            "file.cpp::ClassName::MethodName::varName",
            "file.cpp",
            "ClassName::MethodName",
            "varName",
            "C++ method with class prefix"
        ),
        (
            "src/module.ts::MyClass::constructor::this",
            "src/module.ts",
            "MyClass::constructor",
            "this",
            "TypeScript class constructor"
        ),
        (
            "lib/rust/mod.rs::crate::module::function::data",
            "lib/rust/mod.rs",
            "crate::module::function",
            "data",
            "Rust fully qualified path"
        ),
        (
            "normal/path.js::normalFunc::normalVar",
            "normal/path.js",
            "normalFunc",
            "normalVar",
            "Normal case (no issue expected)"
        ),
        (
            "file::var",
            "file",
            "global",
            "var",
            "Two-part ID (global function)"
        ),
    ]

    all_passed = True

    for input_id, exp_file, exp_func, exp_base, description in test_cases:
        result = AccessPath.parse(input_id)

        print(f"\n  Test: {description}")
        print(f"    Input: '{input_id}'")

        if result:
            file_ok = (result.file == exp_file)
            func_ok = (result.function == exp_func)
            base_ok = (result.base == exp_base)

            print(f"    Expected: file='{exp_file}', func='{exp_func}', base='{exp_base}'")
            print(f"    Actual:   file='{result.file}', func='{result.function}', base='{result.base}'")

            if file_ok and func_ok and base_ok:
                print(f"    Status: PASS")
            else:
                print(f"    Status: FAIL")
                all_passed = False
        else:
            print(f"    ERROR: Parse returned None")
            all_passed = False

    if all_passed:
        print("\n  RESULT: PASS - H3 FIX VERIFIED")
        print("  Parser correctly handles :: in function names.")
        return True
    else:
        print("\n  RESULT: FAIL - H3 FIX NOT COMPLETE")
        return False


def test_flow_resolver_normalization():
    """
    Verify flow_resolver.py has path normalization code.
    """
    print("\n" + "="*70)
    print("[FlowResolver] TESTING: Path Normalization in Source")
    print("="*70)

    resolver_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "theauditor", "taint", "flow_resolver.py"
    )

    with open(resolver_path, "r") as f:
        content = f.read()

    # Check for normalization pattern
    norm_pattern = 'file.replace("\\\\", "/")'
    norm_count = content.count(norm_pattern)

    print(f"\n  Checking flow_resolver.py:")
    print(f"  Path normalization calls found: {norm_count}")

    # We expect at least 7 normalization calls (3 entry + 4 exit node locations)
    if norm_count >= 7:
        print("\n  RESULT: PASS - FlowResolver normalization verified")
        print(f"  Found {norm_count} path normalization calls.")
        return True
    else:
        print("\n  RESULT: FAIL - Insufficient normalization calls")
        print(f"  Expected at least 7, found {norm_count}")
        return False


def test_roundtrip_integrity():
    """
    Test that creating an AccessPath and parsing its node_id
    produces equivalent results (round-trip integrity).
    """
    print("\n" + "="*70)
    print("[BONUS] TESTING: Round-Trip Integrity")
    print("="*70)

    test_cases = [
        ("src/app.js", "handleRequest", "req", ("body", "data")),
        ("lib\\utils\\helper.ts", "process", "input", ()),  # Windows path
        ("backend/api/v1/users.py", "create_user", "user_data", ("email",)),
    ]

    all_passed = True

    for file, func, base, fields in test_cases:
        # Create original AccessPath
        original = AccessPath(file=file, function=func, base=base, fields=fields)
        node_id = original.node_id

        # Parse the node_id back
        parsed = AccessPath.parse(node_id)

        print(f"\n  Original: file='{file}', func='{func}', base='{base}'")
        print(f"  Stored file (normalized): '{original.file}'")
        print(f"  node_id: '{node_id}'")

        if parsed:
            match = (
                parsed.file == original.file and
                parsed.function == original.function and
                parsed.base == original.base
            )

            print(f"  Parsed:  file='{parsed.file}', func='{parsed.function}', base='{parsed.base}'")
            print(f"  Match: {match}")

            if not match:
                all_passed = False
        else:
            print(f"  ERROR: Parse returned None")
            all_passed = False

    if all_passed:
        print("\n  RESULT: PASS - Round-trip integrity maintained")
        return True
    else:
        print("\n  RESULT: FAIL - Round-trip integrity broken")
        return False


def main():
    print("\n")
    print("#" * 70)
    print("#  TAINT ENGINE INTEGRITY VERIFICATION (POST-FIX)")
    print("#  Confirming H1, H2, H3 fixes are working correctly")
    print("#" * 70)

    results = {}

    # Run all verification tests
    results['H1_Path_Normalization'] = test_h1_windows_path_normalization()
    results['H2_Logging_Fix'] = test_h2_logging_check()
    results['H3_Parser_Fix'] = test_h3_parser_robustness()
    results['FlowResolver_Normalization'] = test_flow_resolver_normalization()
    results['Bonus_Roundtrip'] = test_roundtrip_integrity()

    # Summary
    print("\n")
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {test_name}: {status}")

    print(f"\n  Total: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n  OVERALL VERDICT: ALL FIXES VERIFIED")
        print("  The taint engine integrity issues have been resolved.")
    else:
        print("\n  OVERALL VERDICT: SOME FIXES INCOMPLETE")
        print("  Review the failing tests above.")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
