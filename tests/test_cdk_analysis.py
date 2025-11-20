"""Tests for AWS CDK analysis (Python and TypeScript/JavaScript).

Schema-first testing approach - uses build_query() and build_join_query()
from theauditor.indexer.schema for all database queries.
"""

import pytest
import sqlite3
import subprocess
from pathlib import Path

from theauditor.indexer.schema import build_query, build_join_query


DB_PATH = Path(r"C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db")


def test_database_exists():
    """Verify database exists before running tests."""
    if not DB_PATH.exists():
        pytest.skip("Database not found - run 'aud index' first")


def test_python_cdk_constructs_extracted():
    """Test Python CDK construct extraction from vulnerable_stack.py."""
    if not DB_PATH.exists():
        pytest.skip("Database not found")

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # Query using build_query() - schema-first approach
        query = build_query(
            'cdk_constructs',
            columns=['construct_id', 'file_path', 'cdk_class', 'construct_name'],
            where="file_path LIKE '%vulnerable_stack.py'"
        )
        cursor.execute(query)
        python_constructs = cursor.fetchall()

        # Verify at least 3 constructs extracted
        assert len(python_constructs) >= 3, \
            f"Expected at least 3 Python CDK constructs, found {len(python_constructs)}"

        # Verify specific construct types
        cdk_classes = [row[2] for row in python_constructs]
        assert any('Bucket' in c for c in cdk_classes), "Missing s3.Bucket construct"
        assert any('DatabaseInstance' in c for c in cdk_classes), "Missing rds.DatabaseInstance construct"
        assert any('SecurityGroup' in c for c in cdk_classes), "Missing ec2.SecurityGroup construct"

    finally:
        conn.close()


def test_typescript_cdk_constructs_extracted():
    """Test TypeScript CDK construct extraction from vulnerable_stack.ts."""
    if not DB_PATH.exists():
        pytest.skip("Database not found")

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # Query using build_query() - schema-first approach
        query = build_query(
            'cdk_constructs',
            columns=['construct_id', 'file_path', 'cdk_class', 'construct_name'],
            where="file_path LIKE '%vulnerable_stack.ts'"
        )
        cursor.execute(query)
        ts_constructs = cursor.fetchall()

        # Verify at least 3 constructs extracted
        assert len(ts_constructs) >= 3, \
            f"Expected at least 3 TypeScript CDK constructs, found {len(ts_constructs)}"

        # Verify specific construct types
        cdk_classes = [row[2] for row in ts_constructs]
        assert any('Bucket' in c for c in cdk_classes), "Missing s3.Bucket construct"
        assert any('DatabaseInstance' in c for c in cdk_classes), "Missing rds.DatabaseInstance construct"
        assert any('SecurityGroup' in c for c in cdk_classes), "Missing ec2.SecurityGroup construct"

    finally:
        conn.close()


def test_python_cdk_properties_extracted():
    """Test Python CDK property extraction using JOIN."""
    if not DB_PATH.exists():
        pytest.skip("Database not found")

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # JOIN cdk_construct_properties with cdk_constructs
        # Foreign key: cdk_construct_properties.construct_id -> cdk_constructs.construct_id
        cursor.execute("""
            SELECT c.file_path, c.construct_id, p.property_name, p.property_value_expr, p.line
            FROM cdk_constructs c
            JOIN cdk_construct_properties p ON c.construct_id = p.construct_id
            WHERE c.file_path LIKE '%vulnerable_stack.py'
        """)
        python_props = cursor.fetchall()

        # Verify properties extracted
        assert len(python_props) >= 5, \
            f"Expected at least 5 Python CDK properties, found {len(python_props)}"

        # Verify property names use snake_case (Python convention)
        property_names = [row[2] for row in python_props]  # property_name column
        assert any('public_read_access' in p or 'storage_encrypted' in p for p in property_names), \
            "Expected Python snake_case property names"

    finally:
        conn.close()


def test_typescript_cdk_properties_extracted():
    """Test TypeScript CDK property extraction using JOIN."""
    if not DB_PATH.exists():
        pytest.skip("Database not found")

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # JOIN cdk_construct_properties with cdk_constructs
        # Foreign key: cdk_construct_properties.construct_id -> cdk_constructs.construct_id
        cursor.execute("""
            SELECT c.file_path, c.construct_id, p.property_name, p.property_value_expr, p.line
            FROM cdk_constructs c
            JOIN cdk_construct_properties p ON c.construct_id = p.construct_id
            WHERE c.file_path LIKE '%vulnerable_stack.ts'
        """)
        ts_props = cursor.fetchall()

        # Verify properties extracted
        assert len(ts_props) >= 5, \
            f"Expected at least 5 TypeScript CDK properties, found {len(ts_props)}"

        # Verify property names use camelCase (TypeScript/JavaScript convention)
        property_names = [row[2] for row in ts_props]  # property_name column
        assert any('publicReadAccess' in p or 'storageEncrypted' in p for p in property_names), \
            "Expected TypeScript camelCase property names"

    finally:
        conn.close()


def test_python_typescript_parity():
    """Test that Python and TypeScript extraction produce matching construct counts."""
    if not DB_PATH.exists():
        pytest.skip("Database not found")

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # Query Python constructs
        query_py = build_query(
            'cdk_constructs',
            columns=['construct_id', 'cdk_class'],
            where="file_path LIKE '%vulnerable_stack.py'"
        )
        cursor.execute(query_py)
        python_constructs = cursor.fetchall()

        # Query TypeScript constructs
        query_ts = build_query(
            'cdk_constructs',
            columns=['construct_id', 'cdk_class'],
            where="file_path LIKE '%vulnerable_stack.ts'"
        )
        cursor.execute(query_ts)
        ts_constructs = cursor.fetchall()

        # Verify parity
        assert len(python_constructs) == len(ts_constructs), \
            f"Python has {len(python_constructs)} constructs, TypeScript has {len(ts_constructs)} - expected parity"

        # Verify both have same construct types (normalized)
        python_types = {c[1].split('.')[-1] for c in python_constructs}  # e.g., 'Bucket' from 's3.Bucket'
        ts_types = {c[1].split('.')[-1] for c in ts_constructs}
        assert python_types == ts_types, \
            f"Construct types don't match: Python={python_types}, TypeScript={ts_types}"

    finally:
        conn.close()


def test_cdk_analyzer_detects_vulnerabilities():
    """Test that CDK analyzer detects vulnerabilities from both Python and TypeScript."""
    if not DB_PATH.exists():
        pytest.skip("Database not found")

    # Run CDK analyzer
    result = subprocess.run(
        ["aud", "cdk", "analyze", "--db", str(DB_PATH)],
        cwd=r"C:\Users\santa\Desktop\TheAuditor",
        capture_output=True,
        text=True
    )

    # Should detect findings (exit code 1 or 2)
    assert result.returncode in [1, 2], \
        f"Expected findings (exit code 1 or 2), got {result.returncode}: {result.stderr}"

    # Verify both files mentioned in output
    assert 'vulnerable_stack.py' in result.stdout, "Expected vulnerable_stack.py in findings"
    assert 'vulnerable_stack.ts' in result.stdout, "Expected vulnerable_stack.ts in findings"


def test_cdk_findings_written_to_database():
    """Test that CDK findings are written to database."""
    if not DB_PATH.exists():
        pytest.skip("Database not found")

    # Run analyzer to populate findings
    subprocess.run(
        ["aud", "cdk", "analyze", "--db", str(DB_PATH)],
        cwd=r"C:\Users\santa\Desktop\TheAuditor",
        capture_output=True
    )

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # Check cdk_findings table using build_query()
        query = build_query('cdk_findings', columns=['finding_id', 'file_path', 'severity', 'category'])
        cursor.execute(query)
        findings = cursor.fetchall()

        assert len(findings) > 0, "Expected CDK findings in database"

        # Check Python findings
        query_py = build_query(
            'cdk_findings',
            columns=['finding_id', 'severity'],
            where="file_path LIKE '%vulnerable_stack.py'"
        )
        cursor.execute(query_py)
        python_findings = cursor.fetchall()
        assert len(python_findings) > 0, "Expected Python CDK findings"

        # Check TypeScript findings
        query_ts = build_query(
            'cdk_findings',
            columns=['finding_id', 'severity'],
            where="file_path LIKE '%vulnerable_stack.ts'"
        )
        cursor.execute(query_ts)
        ts_findings = cursor.fetchall()
        assert len(ts_findings) > 0, "Expected TypeScript CDK findings"

        # Check findings_consolidated table
        query_consolidated = build_query(
            'findings_consolidated',
            columns=['id', 'file', 'rule', 'severity'],
            where="tool = 'cdk'"
        )
        cursor.execute(query_consolidated)
        consolidated = cursor.fetchall()
        assert len(consolidated) > 0, "Expected CDK findings in findings_consolidated"

    finally:
        conn.close()


def test_cdk_severity_levels():
    """Test that CDK findings have correct severity levels."""
    if not DB_PATH.exists():
        pytest.skip("Database not found")

    # Run analyzer
    subprocess.run(
        ["aud", "cdk", "analyze", "--db", str(DB_PATH)],
        cwd=r"C:\Users\santa\Desktop\TheAuditor",
        capture_output=True
    )

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # Check for CRITICAL findings (public S3 buckets)
        query_critical = build_query(
            'cdk_findings',
            columns=['finding_id', 'category', 'title'],
            where="severity = 'critical'"
        )
        cursor.execute(query_critical)
        critical_findings = cursor.fetchall()
        assert len(critical_findings) > 0, "Expected at least one CRITICAL finding (public S3 bucket)"

        # Check for HIGH findings (unencrypted storage)
        query_high = build_query(
            'cdk_findings',
            columns=['finding_id', 'category', 'title'],
            where="severity = 'high'"
        )
        cursor.execute(query_high)
        high_findings = cursor.fetchall()
        assert len(high_findings) > 0, "Expected at least one HIGH finding (unencrypted storage)"

    finally:
        conn.close()


def test_cdk_analyzer_json_output():
    """Test that JSON output format works."""
    if not DB_PATH.exists():
        pytest.skip("Database not found")

    # Test JSON output
    result = subprocess.run(
        ["aud", "cdk", "analyze", "--db", str(DB_PATH), "--format", "json"],
        cwd=r"C:\Users\santa\Desktop\TheAuditor",
        capture_output=True,
        text=True
    )

    # Should produce valid JSON
    import json
    try:
        data = json.loads(result.stdout)
        assert 'findings' in data, "Expected 'findings' key in JSON output"
        assert 'summary' in data, "Expected 'summary' key in JSON output"
        assert isinstance(data['findings'], list), "Expected 'findings' to be a list"
    except json.JSONDecodeError as e:
        pytest.fail(f"Invalid JSON output: {e}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
