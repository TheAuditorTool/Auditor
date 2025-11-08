"""Test boundary analysis functionality.

Demonstrates:
1. Distance calculation between entry and control points
2. Finding all validation paths from entry points
3. Boundary quality assessment
4. Input validation analysis
"""

import tempfile
import sqlite3
from pathlib import Path
from theauditor.boundaries.distance import (
    calculate_distance,
    find_all_paths_to_controls,
    measure_boundary_quality
)
from theauditor.boundaries.input_validation_analyzer import (
    analyze_input_validation_boundaries,
    generate_report
)


def create_test_database():
    """
    Create test database with sample code structure.

    Simulates this code:

        # Distance 0 (GOOD):
        @app.post('/good')
        def good_handler(data: UserSchema):  # Line 10
            db.insert(data)                  # Line 11

        # Distance 3 (BAD):
        @app.post('/bad')
        def bad_handler(request):            # Line 20
            process_user(request.json)       # Line 21
                def process_user(data):      # Line 30
                    save_user(data)          # Line 31
                        def save_user(data): # Line 40
                            validate(data)   # Line 41 (TOO LATE!)
                            db.insert(data)  # Line 42

        # Distance None (CRITICAL - no validation):
        @app.post('/missing')
        def missing_handler(request):        # Line 50
            db.insert(request.json)          # Line 51
    """
    import os
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)  # Close file descriptor to avoid Windows lock
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create minimal schema
    cursor.execute("""
        CREATE TABLE symbols (
            file TEXT,
            name TEXT,
            type TEXT,
            start_line INTEGER,
            end_line INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE call_graph (
            caller_file TEXT,
            caller_function TEXT,
            callee_file TEXT,
            callee_function TEXT,
            line INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE python_routes (
            file TEXT,
            line INTEGER,
            path TEXT,
            method TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE js_routes (
            file TEXT,
            line INTEGER,
            path TEXT,
            method TEXT
        )
    """)

    # Insert test data

    # Good handler (distance 0 - validation in signature)
    cursor.execute("""
        INSERT INTO symbols VALUES
        ('test.py', 'good_handler', 'function', 10, 11),
        ('test.py', 'UserSchema', 'class', 5, 7)
    """)

    cursor.execute("""
        INSERT INTO python_routes VALUES
        ('test.py', 10, '/good', 'POST')
    """)

    # Bad handler (distance 3 - validation too late)
    cursor.execute("""
        INSERT INTO symbols VALUES
        ('test.py', 'bad_handler', 'function', 20, 21),
        ('test.py', 'process_user', 'function', 30, 31),
        ('test.py', 'save_user', 'function', 40, 42),
        ('test.py', 'validate', 'function', 41, 41)
    """)

    cursor.execute("""
        INSERT INTO python_routes VALUES
        ('test.py', 20, '/bad', 'POST')
    """)

    # Call chain: bad_handler → process_user → save_user → validate
    cursor.execute("""
        INSERT INTO call_graph VALUES
        ('test.py', 'bad_handler', 'test.py', 'process_user', 21),
        ('test.py', 'process_user', 'test.py', 'save_user', 31),
        ('test.py', 'save_user', 'test.py', 'validate', 41)
    """)

    # Missing handler (no validation at all)
    cursor.execute("""
        INSERT INTO symbols VALUES
        ('test.py', 'missing_handler', 'function', 50, 51)
    """)

    cursor.execute("""
        INSERT INTO python_routes VALUES
        ('test.py', 50, '/missing', 'POST')
    """)

    conn.commit()
    conn.close()

    return db_path


def test_distance_calculation():
    """Test basic distance calculation."""
    db_path = create_test_database()

    try:
        # Test distance 0 (validation in same function)
        # Entry: bad_handler (line 20)
        # Control: bad_handler itself would be 0, but we don't have validation there

        # Test distance 3 (validation 3 calls deep)
        # Entry: bad_handler (line 20) → process_user → save_user → validate
        distance = calculate_distance(
            db_path=db_path,
            entry_file='test.py',
            entry_line=20,  # bad_handler
            control_file='test.py',
            control_line=41  # validate (3 calls deep)
        )

        print(f"[PASS] Distance calculation: {distance}")
        assert distance == 3, f"Expected distance 3, got {distance}"

    finally:
        Path(db_path).unlink()


def test_find_validation_paths():
    """Test finding all validation paths from entry point."""
    db_path = create_test_database()

    try:
        # Find all validation paths from bad_handler
        controls = find_all_paths_to_controls(
            db_path=db_path,
            entry_file='test.py',
            entry_line=20,  # bad_handler
            control_patterns=['validate', 'schema'],
            max_depth=5
        )

        print(f"[PASS] Found {len(controls)} validation points")
        for control in controls:
            print(f"  - {control['control_function']} at distance {control['distance']}")
            print(f"    Path: {' -> '.join(control['path'])}")

        assert len(controls) > 0, "Should find at least one validation point"
        assert any(c['distance'] == 3 for c in controls), "Should find validation at distance 3"

    finally:
        Path(db_path).unlink()


def test_boundary_quality():
    """Test boundary quality assessment."""

    # Test missing validation
    quality = measure_boundary_quality([])
    print(f"[PASS] Missing validation: {quality['quality']} - {quality['reason']}")
    assert quality['quality'] == 'missing'

    # Test clear boundary (distance 0)
    quality = measure_boundary_quality([
        {'distance': 0, 'control_function': 'validate', 'path': ['handler', 'validate']}
    ])
    print(f"[PASS] Clear boundary: {quality['quality']} - {quality['reason']}")
    assert quality['quality'] == 'clear'

    # Test fuzzy boundary (distance 3)
    quality = measure_boundary_quality([
        {'distance': 3, 'control_function': 'validate', 'path': ['handler', 'a', 'b', 'validate']}
    ])
    print(f"[PASS] Fuzzy boundary: {quality['quality']} - {quality['reason']}")
    assert quality['quality'] == 'fuzzy'

    # Test multiple validations (scattered)
    quality = measure_boundary_quality([
        {'distance': 1, 'control_function': 'validateA', 'path': ['handler', 'validateA']},
        {'distance': 2, 'control_function': 'validateB', 'path': ['handler', 'process', 'validateB']}
    ])
    print(f"[PASS] Scattered validation: {quality['quality']} - {quality['reason']}")
    assert quality['quality'] == 'fuzzy'


def test_input_validation_analysis():
    """Test full input validation analysis."""
    db_path = create_test_database()

    try:
        # Analyze all routes
        results = analyze_input_validation_boundaries(db_path, max_entries=10)

        print(f"\n[PASS] Analyzed {len(results)} entry points:")
        for result in results:
            print(f"\n  {result['entry_point']}")
            print(f"    Quality: {result['quality']['quality']}")
            print(f"    Controls: {len(result['controls'])}")
            print(f"    Violations: {len(result['violations'])}")

        # Generate report
        report = generate_report(results)
        print("\n" + "="*60)
        print("BOUNDARY ANALYSIS REPORT:")
        print("="*60)
        print(report)

        # Verify we found the issues
        assert any(r['entry_point'] == 'POST /missing' for r in results), "Should find /missing route"
        assert any(r['entry_point'] == 'POST /bad' for r in results), "Should find /bad route"

        # Verify violations detected
        missing_result = next(r for r in results if r['entry_point'] == 'POST /missing')
        assert len(missing_result['violations']) > 0, "/missing should have violations"
        assert any(v['type'] == 'NO_VALIDATION' for v in missing_result['violations']), \
            "/missing should have NO_VALIDATION violation"

    finally:
        Path(db_path).unlink()


if __name__ == '__main__':
    print("Testing Boundary Analysis\n")

    print("1. Testing distance calculation...")
    test_distance_calculation()

    print("\n2. Testing validation path discovery...")
    test_find_validation_paths()

    print("\n3. Testing boundary quality assessment...")
    test_boundary_quality()

    print("\n4. Testing full input validation analysis...")
    test_input_validation_analysis()

    print("\n" + "="*60)
    print("SUCCESS: All tests passed!")
    print("="*60)
