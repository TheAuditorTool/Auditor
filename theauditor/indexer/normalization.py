"""
Normalization Layer.

Promotes language-specific raw data into canonical tables for the Graph Builder.
This bridges the gap between extraction (which writes to language-specific tables)
and graph building (which reads from canonical tables).

NO FALLBACKS. Single pass. Hard fail on errors.
"""

import os
import sqlite3

from theauditor.utils.logging import logger


def normalize_python_routes(db_path: str) -> int:
    """
    Lift Python routes from 'python_routes' to 'api_endpoints'.

    Why: The Graph Builder (dfg_builder.py:390) ONLY reads from 'api_endpoints'
    to link Frontend -> Backend. Without this normalization, Python backends
    (Flask, Django, FastAPI) are invisible to cross-boundary analysis.

    Returns: Number of routes promoted.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM python_routes")
    result = cursor.fetchone()
    count = result[0] if result else 0

    if count == 0:
        logger.debug("[Normalization] No Python routes found to normalize.")
        conn.close()
        return 0

    logger.debug(f"[Normalization] Promoting {count} Python routes to API Endpoints...")

    cursor.execute("""
        INSERT INTO api_endpoints (
            file,
            line,
            method,
            pattern,
            path,
            full_path,
            has_auth,
            handler_function
        )
        SELECT
            REPLACE(file, '\\', '/'),
            line,
            UPPER(COALESCE(method, 'GET')),
            pattern,
            pattern,
            pattern,
            has_auth,
            handler_function
        FROM python_routes
        WHERE handler_function IS NOT NULL
          AND pattern IS NOT NULL
          AND line IS NOT NULL
          AND (REPLACE(file, '\\', '/'), line) NOT IN (
              SELECT file, line FROM api_endpoints
          )
    """)

    promoted = cursor.rowcount
    conn.commit()
    conn.close()

    if os.environ.get("THEAUDITOR_DEBUG") or promoted > 0:
        logger.info(f"[Normalization] Successfully promoted {promoted} Python routes.")

    return promoted


def run_normalization_pass(db_path: str) -> dict[str, int]:
    """
    Run all registered normalizers.

    Returns dict with counts per normalizer for reporting.
    """
    results = {}

    results["python_routes"] = normalize_python_routes(db_path)

    return results
