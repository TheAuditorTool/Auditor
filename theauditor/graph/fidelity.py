"""Graph Fidelity Control System - mirrors indexer/fidelity.py."""

from typing import Any

from theauditor.utils.logging import logger

from .exceptions import GraphFidelityError


def reconcile_graph_fidelity(
    manifest: dict[str, Any], receipt: dict[str, Any], context: str, strict: bool = True
) -> dict[str, Any]:
    """Compare graph manifest (what was built) vs receipt (what was stored).

    Args:
        manifest: From FidelityToken.attach_manifest() on builder output
        receipt: From store operation
        context: Identifier like "GraphStore:import" or "DFGBuilder:unified"
        strict: If True, raise GraphFidelityError on mismatch

    Returns:
        Dict with status, errors, warnings
    """

    tables = {k for k in manifest if not k.startswith("_")}
    tables.update({k for k in receipt if not k.startswith("_")})

    errors = []
    warnings = []

    for table in sorted(tables):
        m_data = manifest.get(table, {})
        r_data = receipt.get(table, {})

        if isinstance(m_data, int):
            raise GraphFidelityError(
                f"LEGACY FORMAT VIOLATION: manifest['{table}'] is int ({m_data}). "
                "Builder must send dict with tx_id/columns/count/bytes.",
                details={"table": table, "value": m_data, "source": "manifest"},
            )
        if isinstance(r_data, int):
            raise GraphFidelityError(
                f"LEGACY FORMAT VIOLATION: receipt['{table}'] is int ({r_data}). "
                "Store must send dict with tx_id/columns/count/bytes.",
                details={"table": table, "value": r_data, "source": "receipt"},
            )

        m_count = m_data.get("count", 0)
        r_count = r_data.get("count", 0)

        m_tx = m_data.get("tx_id")
        r_tx = r_data.get("tx_id")

        if m_tx and r_tx and m_tx != r_tx:
            errors.append(
                f"{table}: TRANSACTION MISMATCH. "
                f"Builder sent batch '{m_tx[:8]}...', Store confirmed '{r_tx[:8]}...'. "
                "Possible pipeline cross-talk or stale buffer."
            )

        m_cols = set(m_data.get("columns", []))
        r_cols = set(r_data.get("columns", []))

        dropped_cols = m_cols - r_cols
        if dropped_cols:
            errors.append(
                f"{table}: SCHEMA VIOLATION. "
                f"Builder found {sorted(m_cols)}, Store only saved {sorted(r_cols)}. "
                f"Dropped columns: {dropped_cols}"
            )

        if m_count > 0 and r_count == 0:
            errors.append(f"{table}: built {m_count} -> stored 0 (100% LOSS)")
        elif m_count != r_count:
            delta = m_count - r_count
            warnings.append(f"{table}: built {m_count} -> stored {r_count} (delta: {delta})")

        m_bytes = m_data.get("bytes", 0)
        r_bytes = r_data.get("bytes", 0)

        if m_count == r_count and m_bytes > 1000 and r_bytes > 0 and r_bytes < m_bytes * 0.1:
            warnings.append(
                f"{table}: Data volume collapsed. "
                f"Builder: {m_bytes} bytes, Store: {r_bytes} bytes. "
                "Possible NULL data issue."
            )

    result = {
        "status": "FAILED" if errors else ("WARNING" if warnings else "OK"),
        "errors": errors,
        "warnings": warnings,
    }

    if errors:
        error_msg = (
            f"Graph Fidelity Check FAILED for {context}. ZERO FALLBACK VIOLATION.\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
        if warnings:
            error_msg += "\nAdditional warnings:\n" + "\n".join(f"  - {w}" for w in warnings)

        if strict:
            logger.error(error_msg)
            raise GraphFidelityError(error_msg, details=result)
        else:
            logger.error(f"[NON-STRICT] {error_msg}")

    elif warnings:
        logger.warning(
            f"Graph Fidelity Warnings for {context}:\n" + "\n".join(f"  - {w}" for w in warnings)
        )

    return result
