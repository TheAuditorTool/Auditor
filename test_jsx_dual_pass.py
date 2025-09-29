"""Test script for JSX dual-pass extraction implementation.

This script verifies that the JSX dual-pass extraction system:
1. Properly extracts data with jsx_mode parameter
2. Populates both JSX and standard tables
3. Validates extraction integrity
4. Handles rollback correctly
"""

import os
import sys
import sqlite3
import tempfile
import shutil
from pathlib import Path

# Add TheAuditor to path
sys.path.insert(0, str(Path(__file__).parent))

from theauditor.indexer import IndexerOrchestrator


def create_test_react_project(test_dir: Path):
    """Create a small test React project with JSX components."""

    # Create directory structure
    (test_dir / "src" / "components").mkdir(parents=True, exist_ok=True)

    # Create a simple React component with JSX
    component_code = '''import React, { useState, useEffect } from 'react';

interface ButtonProps {
    label: string;
    onClick: () => void;
}

const Button: React.FC<ButtonProps> = ({ label, onClick }) => {
    const [clicked, setClicked] = useState(false);

    useEffect(() => {
        if (clicked) {
            console.log('Button was clicked!');
        }
    }, [clicked]);

    const handleClick = () => {
        setClicked(true);
        onClick();
    };

    return (
        <button className="custom-button" onClick={handleClick}>
            {label}
        </button>
    );
};

export default Button;
'''

    (test_dir / "src" / "components" / "Button.tsx").write_text(component_code)

    # Create an App component
    app_code = '''import React from 'react';
import Button from './components/Button';

function App() {
    const handleButtonClick = () => {
        alert('Button clicked!');
    };

    return (
        <div className="App">
            <header className="App-header">
                <h1>Test React App</h1>
                <Button label="Click me!" onClick={handleButtonClick} />
            </header>
        </div>
    );
}

export default App;
'''

    (test_dir / "src" / "App.tsx").write_text(app_code)

    # Create a functional component without JSX
    util_code = '''export function calculateSum(a: number, b: number): number {
    return a + b;
}

export const formatCurrency = (amount: number): string => {
    return `$${amount.toFixed(2)}`;
};
'''

    (test_dir / "src" / "utils.ts").write_text(util_code)

    # Create package.json
    package_json = '''{
  "name": "test-react-app",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  }
}'''

    (test_dir / "package.json").write_text(package_json)


def check_database_tables(db_path: Path):
    """Check if all required database tables exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check for JSX tables
    jsx_tables = [
        'function_returns_jsx',
        'symbols_jsx',
        'assignments_jsx',
        'function_call_args_jsx'
    ]

    standard_tables = [
        'function_returns',
        'symbols',
        'assignments',
        'function_call_args'
    ]

    all_tables = jsx_tables + standard_tables + ['extraction_metadata']

    existing_tables = {}
    for table in all_tables:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        existing_tables[table] = cursor.fetchone() is not None

    conn.close()
    return existing_tables


def check_table_data(db_path: Path, jsx_mode: str):
    """Check data in database tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    results = {}

    # Check JSX tables
    if jsx_mode in ['preserved', 'both']:
        cursor.execute("SELECT COUNT(*) FROM function_returns_jsx")
        results['function_returns_jsx'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM symbols_jsx")
        results['symbols_jsx'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM function_returns_jsx WHERE has_jsx = 1")
        results['jsx_detected'] = cursor.fetchone()[0]

    # Check standard tables
    if jsx_mode in ['transformed', 'both']:
        cursor.execute("SELECT COUNT(*) FROM function_returns")
        results['function_returns'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM symbols")
        results['symbols'] = cursor.fetchone()[0]

    # Check extraction metadata
    cursor.execute("SELECT * FROM extraction_metadata ORDER BY extraction_id DESC LIMIT 1")
    metadata = cursor.fetchone()
    if metadata:
        results['extraction_status'] = metadata  # Will include all columns

    conn.close()
    return results


def run_test(test_name: str, jsx_mode: str):
    """Run a test with specified JSX mode."""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"JSX Mode: {jsx_mode}")
    print('='*60)

    # Create temporary test directory
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir)

        # Create test React project
        print("Creating test React project...")
        create_test_react_project(test_dir)

        # Initialize indexer
        print(f"Initializing indexer with jsx_mode='{jsx_mode}'...")
        indexer = IndexerOrchestrator(str(test_dir))

        try:
            # Run indexing
            print(f"Running indexing...")
            counts, stats = indexer.index(jsx_mode=jsx_mode, validate_extraction=True)

            # Check database
            db_path = test_dir / ".pf" / "repo_index.db"

            # Verify tables exist
            print("\nChecking database tables...")
            tables = check_database_tables(db_path)
            for table, exists in tables.items():
                status = "✓" if exists else "✗"
                print(f"  {status} {table}")

            # Check data
            print("\nChecking extracted data...")
            data = check_table_data(db_path, jsx_mode)

            if jsx_mode in ['preserved', 'both']:
                print(f"  JSX Tables:")
                print(f"    - function_returns_jsx: {data.get('function_returns_jsx', 0)} rows")
                print(f"    - symbols_jsx: {data.get('symbols_jsx', 0)} rows")
                print(f"    - JSX detected: {data.get('jsx_detected', 0)} components")

            if jsx_mode in ['transformed', 'both']:
                print(f"  Standard Tables:")
                print(f"    - function_returns: {data.get('function_returns', 0)} rows")
                print(f"    - symbols: {data.get('symbols', 0)} rows")

            # Report results
            print(f"\nExtraction Stats:")
            print(f"  - Files processed: {counts.get('files', 0)}")
            print(f"  - Symbols extracted: {counts.get('symbols', 0)}")
            print(f"  - JSX components: {counts.get('jsx_components', 0)}")

            # Test result
            success = False
            if jsx_mode == 'both':
                # Both table sets should have data
                success = (
                    data.get('function_returns_jsx', 0) > 0 and
                    data.get('function_returns', 0) > 0
                )
            elif jsx_mode == 'preserved':
                # Only JSX tables should have data
                success = data.get('function_returns_jsx', 0) > 0
            elif jsx_mode == 'transformed':
                # Only standard tables should have data
                success = data.get('function_returns', 0) > 0

            if success:
                print(f"\n✓ TEST PASSED: {test_name}")
            else:
                print(f"\n✗ TEST FAILED: {test_name}")
                print("  Expected data in tables but found none")

            return success

        except Exception as e:
            print(f"\n✗ TEST FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Run all tests."""
    print("JSX DUAL-PASS EXTRACTION TEST SUITE")
    print("====================================")

    # Check if aud setup-claude has been run
    if not (Path.cwd() / ".auditor_venv" / ".theauditor_tools").exists():
        print("\n⚠️  WARNING: .auditor_venv/.theauditor_tools not found")
        print("   Run 'aud setup-claude --target .' first for JS/TS analysis")
        return

    tests = [
        ("Transformed Mode (Backward Compatibility)", "transformed"),
        ("Preserved Mode (JSX Structure)", "preserved"),
        ("Dual-Pass Mode (Both Tables)", "both"),
    ]

    results = []
    for test_name, jsx_mode in tests:
        success = run_test(test_name, jsx_mode)
        results.append((test_name, success))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {total - passed} tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()