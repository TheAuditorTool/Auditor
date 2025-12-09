"""Taint Analysis Fidelity Control System.

Provides manifest/receipt verification at 4 critical stages in the taint pipeline:
1. Discovery - source/sink identification
2. Analysis - IFDS path tracing
3. Deduplication - path consolidation
4. Output - DB and JSON persistence

Mirrors patterns from indexer/fidelity.py and graph/fidelity.py.
"""

import os
from typing import Any

from theauditor.indexer.fidelity_utils import FidelityToken
from theauditor.utils.logging import logger


class TaintFidelityError(Exception):
    """Raised when taint fidelity check fails in strict mode."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


def create_discovery_manifest(sources: list, sinks: list) -> dict[str, Any]:
    """Create manifest after source/sink discovery.

    Args:
        sources: List of discovered taint sources
        sinks: List of discovered taint sinks

    Returns:
        Manifest dict with source/sink tokens and stage identifier
    """
    return {
        "sources": FidelityToken.create_manifest(sources),
        "sinks": FidelityToken.create_manifest(sinks),
        "_stage": "discovery",
    }


def create_analysis_manifest(
    vulnerable_paths: list,
    sanitized_paths: list,
    sinks_analyzed: int,
    sources_checked: int,
) -> dict[str, Any]:
    """Create manifest after IFDS analysis.

    Args:
        vulnerable_paths: List of paths reaching sinks without sanitization
        sanitized_paths: List of paths blocked by sanitizers
        sinks_analyzed: Number of sinks processed
        sources_checked: Number of sources checked

    Returns:
        Manifest dict with path counts and analysis stats
    """
    return {
        "vulnerable_paths": FidelityToken.create_manifest(vulnerable_paths),
        "sanitized_paths": FidelityToken.create_manifest(sanitized_paths),
        "sinks_analyzed": sinks_analyzed,
        "sources_checked": sources_checked,
        "_stage": "analysis",
    }


def create_dedup_manifest(
    pre_dedup_count: int,
    post_dedup_count: int,
) -> dict[str, Any]:
    """Create manifest after deduplication.

    Args:
        pre_dedup_count: Total paths before deduplication
        post_dedup_count: Total paths after deduplication

    Returns:
        Manifest dict with dedup stats and removal ratio
    """
    return {
        "pre_dedup_count": pre_dedup_count,
        "post_dedup_count": post_dedup_count,
        "removed_count": pre_dedup_count - post_dedup_count,
        "removal_ratio": (pre_dedup_count - post_dedup_count) / max(pre_dedup_count, 1),
        "_stage": "dedup",
    }


def create_db_output_receipt(
    db_rows_inserted: int,
    vulnerable_count: int,
    sanitized_count: int,
) -> dict[str, Any]:
    """Create receipt after DB write in trace_taint().

    Args:
        db_rows_inserted: Actual rows inserted to database
        vulnerable_count: Expected vulnerable path count
        sanitized_count: Expected sanitized path count

    Returns:
        Receipt dict with DB write stats
    """
    return {
        "db_rows": db_rows_inserted,
        "vulnerable_count": vulnerable_count,
        "sanitized_count": sanitized_count,
        "_stage": "db_output",
    }


def create_json_output_receipt(
    json_vulnerabilities: int,
    json_bytes_written: int,
) -> dict[str, Any]:
    """Create receipt after JSON write in save_taint_analysis().

    Args:
        json_vulnerabilities: Number of vulnerabilities in JSON
        json_bytes_written: Byte size of JSON output

    Returns:
        Receipt dict with JSON write stats
    """
    return {
        "json_count": json_vulnerabilities,
        "json_bytes": json_bytes_written,
        "_stage": "json_output",
    }


def reconcile_taint_fidelity(
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    stage: str,
    strict: bool = True,
) -> dict[str, Any]:
    """Compare taint manifest vs receipt at each pipeline stage.

    Args:
        manifest: What was produced/expected at this stage
        receipt: What was actually stored/written
        stage: One of "discovery", "analysis", "dedup", "db_output", "json_output"
        strict: If True, raise TaintFidelityError on failure

    Returns:
        Dict with status ("OK", "WARNING", "FAILED"), errors, and warnings

    Raises:
        TaintFidelityError: In strict mode when errors are detected
    """
    # Environment variable override
    strict_env = os.environ.get("TAINT_FIDELITY_STRICT", "1")
    if strict_env == "0":
        strict = False

    errors = []
    warnings = []

    # Stage-specific reconciliation logic
    if stage == "discovery":
        # Verify sources and sinks were found
        src_count = manifest.get("sources", {}).get("count", 0)
        sink_count = manifest.get("sinks", {}).get("count", 0)
        if src_count == 0:
            warnings.append("Discovery found 0 sources - is this expected?")
        if sink_count == 0:
            warnings.append("Discovery found 0 sinks - is this expected?")

    elif stage == "analysis":
        # Verify analysis didn't silently fail
        sinks_analyzed = manifest.get("sinks_analyzed", 0)
        sinks_expected = receipt.get("sinks_to_analyze", 0)

        if sinks_analyzed == 0 and sinks_expected > 0:
            errors.append(
                f"Analysis processed 0/{sinks_expected} sinks - pipeline stalled"
            )

    elif stage == "dedup":
        # Warn if dedup removed too many paths
        removal_ratio = manifest.get("removal_ratio", 0)
        if removal_ratio > 0.5:
            warnings.append(
                f"Dedup removed {manifest.get('removed_count')}/{manifest.get('pre_dedup_count')} "
                f"paths ({removal_ratio:.0%}) - check for hash collisions"
            )

    elif stage == "db_output":
        # Verify DB write succeeded
        manifest_count = manifest.get("paths_to_write", 0)
        db_count = receipt.get("db_rows", 0)

        if manifest_count > 0 and db_count == 0:
            errors.append(
                f"DB Output: {manifest_count} paths to write, 0 written (100% LOSS)"
            )
        elif manifest_count != db_count:
            warnings.append(
                f"DB Output: manifest={manifest_count}, db_rows={db_count} "
                f"(delta={manifest_count - db_count})"
            )

    elif stage == "json_output":
        # Verify JSON write succeeded
        manifest_count = manifest.get("paths_to_write", 0)
        json_count = receipt.get("json_count", 0)

        if manifest_count > 0 and json_count == 0:
            errors.append(
                f"JSON Output: {manifest_count} paths to write, 0 in JSON (100% LOSS)"
            )
        elif manifest_count != json_count:
            warnings.append(
                f"JSON Output: manifest={manifest_count}, json={json_count} "
                f"(delta={manifest_count - json_count})"
            )

    result = {
        "status": "FAILED" if errors else ("WARNING" if warnings else "OK"),
        "stage": stage,
        "errors": errors,
        "warnings": warnings,
    }

    if errors and strict:
        error_msg = f"Taint Fidelity FAILED at {stage}: " + "; ".join(errors)
        logger.error(error_msg)
        raise TaintFidelityError(error_msg, details=result)

    if warnings:
        logger.warning(f"Taint Fidelity Warnings at {stage}: {warnings}")

    return result
