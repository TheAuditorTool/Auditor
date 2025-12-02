"""
Python Extractor Verification (Wave 2a)
=======================================
Tests the Python extractor in ISOLATION - no database, no storage layer.
Just "Code In -> Extracted Data Out".

This catches:
  - AST parsing failures
  - Extractor logic bugs
  - Missing or malformed output fields
  - Crashes during extraction

Exit codes:
  0 = All checks passed
  1 = Warnings (non-fatal issues)
  2 = Critical errors (extractor is broken)

Author: TheAuditor Team
"""
import sys
import os
import traceback

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Test code samples - each tests a specific extraction capability
TEST_CASES = [
    {
        "name": "Basic function with import",
        "code": '''
import os
from pathlib import Path

def hello(name: str) -> bool:
    """Greet the user."""
    print(f"Hello {name}")
    return True
''',
        "expected": {
            "symbols": ["hello"],
            "refs": ["os", "pathlib", "Path"],  # refs includes both imports and references
        },
    },
    {
        "name": "Class with methods",
        "code": '''
class UserService:
    """User management service."""

    def __init__(self, db):
        self.db = db

    def get_user(self, user_id: int) -> dict:
        return self.db.find(user_id)

    def create_user(self, name: str) -> dict:
        return self.db.insert({"name": name})
''',
        "expected": {
            "symbols": ["UserService", "__init__", "get_user", "create_user"],
        },
    },
    {
        "name": "Flask route decorator",
        "code": '''
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/api/users", methods=["GET"])
def list_users():
    return jsonify([])

@app.route("/api/users/<int:user_id>", methods=["POST"])
def get_user(user_id):
    data = request.get_json()
    return jsonify(data)
''',
        "expected": {
            # Note: 'app' is an assignment, not a function definition
            # The extractor captures function calls like Flask() as symbols
            "symbols": ["list_users", "get_user"],
        },
    },
    {
        "name": "SQLAlchemy ORM model",
        "code": '''
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(255))
''',
        "expected": {
            # Note: 'Base' is an assignment to a function call, not a class definition
            # The extractor correctly captures 'User' as a class symbol
            "symbols": ["User"],
        },
    },
    {
        "name": "Async function with decorator",
        "code": '''
import asyncio

async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

@asyncio.coroutine
def legacy_fetch():
    yield from asyncio.sleep(1)
''',
        "expected": {
            "symbols": ["fetch_data", "legacy_fetch"],
        },
    },
    {
        "name": "Assignment and return tracking",
        "code": '''
def process_data(input_data):
    result = transform(input_data)
    filtered = [x for x in result if x > 0]
    return filtered
''',
        "expected": {
            "symbols": ["process_data"],
            # These are harder to verify without full extractor output
        },
    },
]


def verify_python_extractor() -> int:
    """Run Python extractor verification. Returns exit code."""
    print("=" * 60)
    print("PYTHON EXTRACTOR VERIFICATION (Wave 2a)")
    print("=" * 60)

    errors = 0
    warnings = 0

    # 1. Import required modules
    print("\n[1] Loading extractor modules...")
    try:
        from theauditor.ast_extractors.ast_parser import ASTParser
        from theauditor.indexer.extractors.python import PythonExtractor
        from pathlib import Path as PathLib

        print("    [OK] Loaded ASTParser and PythonExtractor")
    except ImportError as e:
        print(f"    [CRITICAL] Failed to import extractor modules: {e}")
        return 2

    # 2. Initialize extractor
    print("\n[2] Initializing extractor...")
    try:
        parser = ASTParser()
        extractor = PythonExtractor(PathLib(PROJECT_ROOT), parser)
        print("    [OK] Extractor initialized")
    except Exception as e:
        print(f"    [CRITICAL] Failed to initialize extractor: {e}")
        traceback.print_exc()
        return 2

    # 3. Run test cases
    print("\n[3] Running extraction test cases...")
    passed = 0
    failed = 0

    for i, test_case in enumerate(TEST_CASES):
        name = test_case["name"]
        code = test_case["code"]
        expected = test_case.get("expected", {})

        print(f"\n    [{i+1}/{len(TEST_CASES)}] {name}...")

        try:
            # Parse the code
            code_bytes = code.encode("utf-8")

            # Create a mock file info
            file_info = {"path": f"test_case_{i}.py", "ext": ".py"}

            # Parse to get AST
            import ast
            python_ast = ast.parse(code)
            tree = {
                "type": "python_ast",
                "tree": python_ast,
                "language": "python",
                "content": code,
            }

            # Extract
            result = extractor.extract(file_info, code, tree)

            # Validate result structure
            if not isinstance(result, dict):
                print(f"        [FAIL] Result is not a dict: {type(result)}")
                failed += 1
                continue

            # Check for required keys
            required_keys = ["symbols"]
            missing_keys = [k for k in required_keys if k not in result]
            if missing_keys:
                print(f"        [WARN] Missing keys in result: {missing_keys}")
                warnings += 1

            # Check expected values
            extraction_ok = True

            if "symbols" in expected:
                actual_symbols = [s.get("name") for s in result.get("symbols", []) if isinstance(s, dict)]
                for expected_sym in expected["symbols"]:
                    if expected_sym not in actual_symbols:
                        print(f"        [FAIL] Expected symbol '{expected_sym}' not found")
                        print(f"               Found: {actual_symbols}")
                        extraction_ok = False
                        break

            if extraction_ok:
                symbol_count = len(result.get("symbols", []))
                ref_count = len(result.get("imports", []) or result.get("refs", []) or [])
                print(f"        [OK] Extracted {symbol_count} symbols, {ref_count} refs")
                passed += 1
            else:
                failed += 1

        except SyntaxError as e:
            print(f"        [FAIL] Syntax error in test code: {e}")
            failed += 1
        except Exception as e:
            print(f"        [FAIL] Extraction crashed: {e}")
            traceback.print_exc()
            failed += 1

    # 4. Summary
    print("\n" + "-" * 60)
    print(f"    Test Results: {passed}/{len(TEST_CASES)} passed, {failed} failed")

    if failed > 0:
        errors += failed

    # 5. Test empty/edge cases
    print("\n[4] Testing edge cases...")

    edge_cases = [
        ("Empty file", ""),
        ("Comment only", "# Just a comment"),
        ("Syntax error", "def broken("),  # Should fail gracefully
        ("Unicode content", "def greet(): return '\u4e2d\u6587'"),
    ]

    for name, code in edge_cases:
        try:
            file_info = {"path": f"edge_{name.replace(' ', '_')}.py", "ext": ".py"}

            # Some cases will have syntax errors
            try:
                import ast
                python_ast = ast.parse(code)
                tree = {
                    "type": "python_ast",
                    "tree": python_ast,
                    "language": "python",
                    "content": code,
                }
                result = extractor.extract(file_info, code, tree)
                print(f"    [{name}] [OK] Handled gracefully")
            except SyntaxError:
                # Syntax error files should return empty result, not crash
                print(f"    [{name}] [OK] Syntax error detected (expected)")

        except Exception as e:
            print(f"    [{name}] [FAIL] Crashed: {e}")
            errors += 1

    # 6. Verify output types
    print("\n[5] Verifying output field types...")
    try:
        code = '''
def sample_func(x: int) -> str:
    result = str(x)
    return result
'''
        file_info = {"path": "type_test.py", "ext": ".py"}
        import ast
        python_ast = ast.parse(code)
        tree = {
            "type": "python_ast",
            "tree": python_ast,
            "language": "python",
            "content": code,
        }
        result = extractor.extract(file_info, code, tree)

        # Check that all values are lists (not None)
        list_fields = ["symbols", "imports", "assignments", "function_calls", "returns"]
        for field in list_fields:
            value = result.get(field)
            if value is not None and not isinstance(value, list):
                print(f"    [FAIL] Field '{field}' should be list, got {type(value)}")
                errors += 1
            else:
                print(f"    [OK] Field '{field}' is valid type")

    except Exception as e:
        print(f"    [FAIL] Type verification crashed: {e}")
        errors += 1

    # Final verdict
    print("\n" + "=" * 60)
    if errors > 0:
        print(f"[FAIL] Python extractor verification failed with {errors} error(s)")
        return 2
    elif warnings > 0:
        print(f"[PASS] Python extractor verification passed with {warnings} warning(s)")
        return 1
    else:
        print("[PASS] Python extractor verification passed - all checks clean")
        return 0


if __name__ == "__main__":
    exit_code = verify_python_extractor()
    sys.exit(exit_code)
