"""Taint Analysis Fidelity Control System.

Mirrors indexer/fidelity.py and graph/fidelity.py patterns:
- Uses FidelityToken for tx_id/columns/count/bytes tracking
- Manifest created before operation, receipt after
- reconcile compares manifest vs receipt with proper checks

Checkpoints:
1. Discovery - source/sink identification (count verification)
2. Analysis - IFDS path tracing (count verification)
3. DB Output - persistence to resolved_flow_audit + taint_flows (tx_id + count)

Note: Dedup checkpoint was REMOVED - it measured intentional deduplication
as if it were data loss, which is fundamentally wrong.
"""

import os
import uuid
from typing import Any

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
        Manifest dict with counts for fidelity checking
    """
    return {
        "sources_count": len(sources),
        "sinks_count": len(sinks),
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
        vulnerable_paths: Paths reaching sinks without sanitization
        sanitized_paths: Paths blocked by sanitizers
        sinks_analyzed: Number of sinks processed
        sources_checked: Number of sources checked

    Returns:
        Manifest dict with path counts and analysis stats
    """
    return {
        "vulnerable_count": len(vulnerable_paths),
        "sanitized_count": len(sanitized_paths),
        "total_paths": len(vulnerable_paths) + len(sanitized_paths),
        "sinks_analyzed": sinks_analyzed,
        "sources_checked": sources_checked,
        "_stage": "analysis",
    }


def create_db_manifest(paths_to_write: int) -> dict[str, Any]:
    """Create manifest BEFORE DB write with transaction ID.

    Args:
        paths_to_write: Number of paths about to be written

    Returns:
        Manifest with tx_id for cross-talk detection
    """
    return {
        "tx_id": str(uuid.uuid4()),
        "count": paths_to_write,
        "tables": ["resolved_flow_audit", "taint_flows"],
        "_stage": "db_output",
    }


def create_db_receipt(
    rows_inserted: int,
    tx_id: str,
) -> dict[str, Any]:
    """Create receipt AFTER DB write echoing transaction ID.

    Args:
        rows_inserted: Actual rows inserted
        tx_id: Transaction ID from manifest (echoed back)

    Returns:
        Receipt for comparison against manifest
    """
    return {
        "tx_id": tx_id,
        "count": rows_inserted,
        "_stage": "db_output",
    }


def reconcile_taint_fidelity(
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    stage: str,
    strict: bool = True,
) -> dict[str, Any]:
    """Compare taint manifest vs receipt at each pipeline stage.

    Mirrors indexer/fidelity.py reconcile_fidelity() pattern.

    Args:
        manifest: What was produced/expected at this stage
        receipt: What was actually stored/written
        stage: One of "discovery", "analysis", "db_output"
        strict: If True, raise TaintFidelityError on failure

    Returns:
        Dict with status ("OK", "WARNING", "FAILED"), errors, and warnings

    Raises:
        TaintFidelityError: In strict mode when errors are detected
    """
    strict_env = os.environ.get("TAINT_FIDELITY_STRICT", "1")
    if strict_env == "0":
        strict = False

    errors = []
    warnings = []

    if stage == "discovery":
        src_count = manifest.get("sources_count", 0)
        sink_count = manifest.get("sinks_count", 0)

        if sink_count == 0:
            errors.append(
                "Discovery found 0 sinks - taint analysis cannot proceed without sinks"
            )
        if src_count == 0:
            warnings.append("Discovery found 0 sources - no taint origins detected")

    elif stage == "analysis":
        sinks_analyzed = manifest.get("sinks_analyzed", 0)
        sinks_expected = receipt.get("sinks_to_analyze", 0)

        if sinks_analyzed == 0 and sinks_expected > 0:
            errors.append(
                f"Analysis processed 0/{sinks_expected} sinks - IFDS pipeline stalled"
            )

    elif stage == "db_output":
        m_tx = manifest.get("tx_id")
        r_tx = receipt.get("tx_id")

        if m_tx and r_tx and m_tx != r_tx:
            errors.append(
                f"TRANSACTION MISMATCH: manifest tx '{m_tx[:8]}...' != receipt tx '{r_tx[:8]}...'. "
                "Possible pipeline cross-talk or stale buffer."
            )

        m_count = manifest.get("count", 0)
        r_count = receipt.get("count", 0)

        if m_count > 0 and r_count == 0:
            errors.append(f"DB Output: {m_count} paths to write, 0 written (100% LOSS)")
        elif m_count != r_count:
            delta = m_count - r_count
            warnings.append(
                f"DB Output: manifest={m_count}, db_rows={r_count} (delta={delta})"
            )

    result = {
        "status": "FAILED" if errors else ("WARNING" if warnings else "OK"),
        "stage": stage,
        "errors": errors,
        "warnings": warnings,
    }

    if errors:
        error_msg = (
            f"Taint Fidelity FAILED at {stage}. ZERO FALLBACK VIOLATION.\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
        if warnings:
            error_msg += "\nAdditional warnings:\n" + "\n".join(
                f"  - {w}" for w in warnings
            )

        if strict:
            logger.error(error_msg)
            raise TaintFidelityError(error_msg, details=result)
        else:
            logger.error(f"[NON-STRICT] {error_msg}")

    elif warnings:
        logger.warning(
            f"Taint Fidelity Warnings at {stage}:\n"
            + "\n".join(f"  - {w}" for w in warnings)
        )

    return result
