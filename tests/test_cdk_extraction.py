"""Tests for AWS CDK construct extraction (Python and TypeScript).

Tests both Python and TypeScript/JavaScript CDK extraction to ensure parity.
"""

import pytest
import sqlite3
from pathlib import Path


def test_python_cdk_extraction():
    """Test Python CDK construct extraction from vulnerable_stack.py."""
    # Use the existing database from aud index run
    db_path = Path(r"C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db")

    if not db_path.exists():
        pytest.skip("Database not found - run 'aud index' first")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Verify Python CDK constructs extracted
        cursor.execute("""
            SELECT COUNT(*)
            FROM cdk_constructs
            WHERE file LIKE '%vulnerable_stack.py'
        """)
        python_count = cursor.fetchone()[0]

        assert python_count >= 3, f"Expected at least 3 Python CDK constructs, found {python_count}"

        # Verify specific construct types
        cursor.execute("""
            SELECT cdk_class, construct_name
            FROM cdk_constructs
            WHERE file LIKE '%vulnerable_stack.py'
            ORDER BY cdk_class
        """)
        constructs = cursor.fetchall()

        classes = [c[0] for c in constructs]
        assert 's3.Bucket' in classes, "Missing s3.Bucket construct"
        assert 'rds.DatabaseInstance' in classes, "Missing rds.DatabaseInstance construct"
        assert 'ec2.SecurityGroup' in classes, "Missing ec2.SecurityGroup construct"

        # Verify properties extracted
        cursor.execute("""
            SELECT COUNT(*)
            FROM cdk_construct_properties
            WHERE file LIKE '%vulnerable_stack.py'
        """)
        python_props = cursor.fetchone()[0]

        assert python_props >= 5, f"Expected at least 5 Python properties, found {python_props}"

    finally:
        conn.close()


def test_typescript_cdk_extraction():
    """Test TypeScript CDK construct extraction from vulnerable_stack.ts."""
    db_path = Path(r"C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db")

    if not db_path.exists():
        pytest.skip("Database not found - run 'aud index' first")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Verify TypeScript CDK constructs extracted
        cursor.execute("""
            SELECT COUNT(*)
            FROM cdk_constructs
            WHERE file LIKE '%vulnerable_stack.ts'
        """)
        ts_count = cursor.fetchone()[0]

        assert ts_count >= 3, f"Expected at least 3 TypeScript CDK constructs, found {ts_count}"

        # Verify specific construct types
        cursor.execute("""
            SELECT cdk_class, construct_name
            FROM cdk_constructs
            WHERE file LIKE '%vulnerable_stack.ts'
            ORDER BY cdk_class
        """)
        constructs = cursor.fetchall()

        classes = [c[0] for c in constructs]
        assert 's3.Bucket' in classes, "Missing s3.Bucket construct"
        assert 'rds.DatabaseInstance' in classes, "Missing rds.DatabaseInstance construct"
        assert 'ec2.SecurityGroup' in classes, "Missing ec2.SecurityGroup construct"

        # Verify properties extracted (TypeScript uses camelCase)
        cursor.execute("""
            SELECT COUNT(*)
            FROM cdk_construct_properties
            WHERE file LIKE '%vulnerable_stack.ts'
        """)
        ts_props = cursor.fetchone()[0]

        assert ts_props >= 5, f"Expected at least 5 TypeScript properties, found {ts_props}"

        # Verify camelCase property names
        cursor.execute("""
            SELECT property_name
            FROM cdk_construct_properties
            WHERE file LIKE '%vulnerable_stack.ts'
              AND property_name IN ('publicReadAccess', 'storageEncrypted', 'allowAllOutbound')
        """)
        camel_props = cursor.fetchall()

        assert len(camel_props) > 0, "Expected camelCase properties (publicReadAccess, storageEncrypted, etc.)"

    finally:
        conn.close()


def test_python_typescript_parity():
    """Test that Python and TypeScript extraction produce similar results."""
    db_path = Path(r"C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db")

    if not db_path.exists():
        pytest.skip("Database not found - run 'aud index' first")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Count constructs per language
        cursor.execute("""
            SELECT COUNT(*)
            FROM cdk_constructs
            WHERE file LIKE '%vulnerable_stack.py'
        """)
        python_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM cdk_constructs
            WHERE file LIKE '%vulnerable_stack.ts'
        """)
        ts_count = cursor.fetchone()[0]

        # Both should have same number of constructs
        assert python_count == ts_count, \
            f"Python has {python_count} constructs, TypeScript has {ts_count} - expected parity"

        # Both should have similar construct types
        cursor.execute("""
            SELECT DISTINCT cdk_class
            FROM cdk_constructs
            WHERE file LIKE '%vulnerable_stack.py'
            ORDER BY cdk_class
        """)
        python_classes = set(row[0] for row in cursor.fetchall())

        cursor.execute("""
            SELECT DISTINCT cdk_class
            FROM cdk_constructs
            WHERE file LIKE '%vulnerable_stack.ts'
            ORDER BY cdk_class
        """)
        ts_classes = set(row[0] for row in cursor.fetchall())

        assert python_classes == ts_classes, \
            f"Construct classes don't match: Python={python_classes}, TypeScript={ts_classes}"

    finally:
        conn.close()


def test_property_value_extraction():
    """Test that property values are correctly extracted."""
    db_path = Path(r"C:\Users\santa\Desktop\TheAuditor\.pf\repo_index.db")

    if not db_path.exists():
        pytest.skip("Database not found - run 'aud index' first")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Check Python public_read_access=True
        cursor.execute("""
            SELECT property_value_expr
            FROM cdk_construct_properties
            WHERE file LIKE '%vulnerable_stack.py'
              AND property_name = 'public_read_access'
        """)
        python_public = cursor.fetchone()

        if python_public:
            assert 'True' in python_public[0], "Expected public_read_access=True in Python"

        # Check TypeScript publicReadAccess=true
        cursor.execute("""
            SELECT property_value_expr
            FROM cdk_construct_properties
            WHERE file LIKE '%vulnerable_stack.ts'
              AND property_name = 'publicReadAccess'
        """)
        ts_public = cursor.fetchone()

        if ts_public:
            assert 'true' in ts_public[0], "Expected publicReadAccess=true in TypeScript"

        # Check Python storage_encrypted=False
        cursor.execute("""
            SELECT property_value_expr
            FROM cdk_construct_properties
            WHERE file LIKE '%vulnerable_stack.py'
              AND property_name = 'storage_encrypted'
        """)
        python_encrypted = cursor.fetchone()

        if python_encrypted:
            assert 'False' in python_encrypted[0], "Expected storage_encrypted=False in Python"

        # Check TypeScript storageEncrypted=false
        cursor.execute("""
            SELECT property_value_expr
            FROM cdk_construct_properties
            WHERE file LIKE '%vulnerable_stack.ts'
              AND property_name = 'storageEncrypted'
        """)
        ts_encrypted = cursor.fetchone()

        if ts_encrypted:
            assert 'false' in ts_encrypted[0], "Expected storageEncrypted=false in TypeScript"

    finally:
        conn.close()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
