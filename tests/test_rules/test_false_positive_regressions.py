"""Regression tests for previously noisy rule detections.

Credit: Test cases from external contributor @dev-corelift (PR #20)
These tests verify that token-based matching prevents substring collision false positives.
"""

import sqlite3

from theauditor.rules.secrets.hardcoded_secret_analyze import (
    _find_secret_assignments,
)
from theauditor.rules.security.crypto_analyze import (
    _find_weak_encryption_algorithms,
)
from theauditor.rules.security.pii_analyze import (
    _detect_pii_in_apis,
    _detect_pii_in_errors,
    _detect_unencrypted_pii,
    _organize_pii_patterns,
)


def _create_assignments_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS assignments (
            file TEXT,
            line INTEGER,
            target_var TEXT,
            source_expr TEXT,
            in_function TEXT,
            property_path TEXT
        )
        """
    )
    conn.commit()


def _create_function_call_args_table(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS function_call_args (
            file TEXT,
            line INTEGER,
            caller_function TEXT,
            callee_function TEXT,
            argument_index INTEGER,
            argument_expr TEXT,
            param_name TEXT,
            callee_file_path TEXT
        )
        """
    )
    conn.commit()


def test_secret_assignment_skips_dynamic_values(temp_db):
    """Header-derived values should not be treated as hardcoded secrets.

    Credit: @dev-corelift (PR #20)
    """
    conn = temp_db
    _create_assignments_table(conn)

    conn.execute(
        """
        INSERT INTO assignments (file, line, target_var, source_expr, in_function, property_path)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "packages/edge/src/api/cache.ts",
            35,
            "apiKey",
            "request.headers.get('X-API-Key')",
            "invalidateCache",
            None,
        ),
    )
    conn.commit()

    findings = _find_secret_assignments(conn.cursor())
    assert all(
        finding.rule_name != "secret-hardcoded-assignment" for finding in findings
    ), f"Unexpected secret finding: {findings}"


def test_crypto_alias_detection_ignores_includes(temp_db):
    """String helper methods such as includes() should not trigger DES findings.

    Credit: @dev-corelift (PR #20)
    Prevents substring collision: "includes" contains "des" but isn't crypto-related.
    """
    conn = temp_db
    _create_function_call_args_table(conn)

    conn.execute(
        """
        INSERT INTO function_call_args (
            file, line, caller_function, callee_function,
            argument_index, argument_expr, param_name, callee_file_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "packages/edge/src/api/github.ts",
            240,
            "changes.some",
            "c.path.includes",
            None,
            "robots.txt",
            None,
            None,
        ),
    )
    conn.commit()

    findings = _find_weak_encryption_algorithms(conn.cursor())
    assert all(
        finding.rule_name != "crypto-weak-encryption" for finding in findings
    ), f"Unexpected crypto finding: {findings}"


def test_pii_detectors_skip_generic_identifiers(temp_db):
    """PII detectors should ignore generic fields like message/className.

    Credit: @dev-corelift (PR #20)
    Prevents false positives:
    - "message" should not match "sms_history"
    - "className" should not match "class" (student context)
    """
    conn = temp_db
    cursor = conn.cursor()
    _create_function_call_args_table(conn)

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS api_endpoints (
            file TEXT,
            line INTEGER,
            method TEXT,
            pattern TEXT,
            path TEXT,
            has_auth BOOLEAN,
            handler_function TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS symbols (
            path TEXT,
            name TEXT,
            type TEXT,
            line INTEGER,
            col INTEGER,
            end_line INTEGER,
            type_annotation TEXT,
            parameters TEXT,
            is_typed BOOLEAN
        )
        """
    )
    conn.commit()

    # Simulate router definition returning { message: "..." }
    cursor.execute(
        """
        INSERT INTO api_endpoints (file, line, method, pattern, path, has_auth, handler_function)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "packages/edge/src/api/dashboard.ts",
            77,
            "GET",
            "/api/dashboard",
            "/api/dashboard",
            0,
            "getDashboard",
        ),
    )

    # Error response logging with a generic message field
    cursor.execute(
        """
        INSERT INTO function_call_args (
            file, line, caller_function, callee_function,
            argument_index, argument_expr, param_name, callee_file_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "packages/edge/src/api/sites.ts",
            990,
            "logger.error",
            "response.json",
            0,
            "{ message: 'Site updated successfully' }",
            None,
            None,
        ),
    )
    cursor.execute(
        """
        INSERT INTO symbols (path, name, type, line, col, end_line, type_annotation, parameters, is_typed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "packages/edge/src/api/sites.ts",
            "errorHandler",
            "catch",
            982,
            0,
            1000,
            None,
            None,
            0,
        ),
    )

    # Simulated write operation that references className values
    cursor.execute(
        """
        INSERT INTO function_call_args (
            file, line, caller_function, callee_function,
            argument_index, argument_expr, param_name, callee_file_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "packages/frontend/src/app/pages/sites/RemovalWizard.tsx",
            453,
            "fs.writeFile",
            "fs.writeFile",
            0,
            "className('flex items-start gap-3 p-3 bg-app-surface-2')",
            None,
            None,
        ),
    )
    conn.commit()

    pii_categories = _organize_pii_patterns()

    api_findings = _detect_pii_in_apis(conn.cursor(), pii_categories)
    assert not api_findings, f"Unexpected API findings: {api_findings}"

    error_findings = _detect_pii_in_errors(conn.cursor(), pii_categories)
    assert not error_findings, f"Unexpected error findings: {error_findings}"

    storage_findings = _detect_unencrypted_pii(conn.cursor(), pii_categories)
    assert not storage_findings, f"Unexpected storage findings: {storage_findings}"
