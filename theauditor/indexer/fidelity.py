"""Data Fidelity Control System.

Enforces the ZERO FALLBACK POLICY by reconciling extraction manifests
against storage receipts. If data is extracted but not stored, this module
triggers a loud crash to prevent silent data loss.

ARCHITECTURE:
    Extractor -> Manifest (what was found)
    Storage   -> Receipt (what was saved)
    Fidelity  -> Compare and CRASH if mismatch

This system was added after discovering ~22MB of silent data loss when
schema columns were invented without verifying actual extractor outputs.
"""

import logging
from typing import Dict

from .exceptions import DataFidelityError

logger = logging.getLogger(__name__)


def reconcile_fidelity(
    manifest: Dict[str, int],
    receipt: Dict[str, int],
    file_path: str,
    strict: bool = True
) -> Dict[str, any]:
    """Compare extraction manifest (what was found) vs storage receipt (what was saved).

    This is the core enforcement mechanism for data fidelity. It detects:
    1. CRITICAL: Data extracted but NOTHING stored (100% loss)
    2. WARNING: Partial mismatch (some rows filtered/duplicated)

    Args:
        manifest: Dict {table_name: count} from the extractor.
        receipt: Dict {table_name: count} from the storage layer.
        file_path: The file being processed (for error reporting).
        strict: If True, raises DataFidelityError on data loss.

    Returns:
        Dict containing:
            - status: 'OK', 'WARNING', or 'FAILED'
            - errors: List of critical errors (100% data loss)
            - warnings: List of partial mismatches

    Raises:
        DataFidelityError: If strict=True and data loss is detected.
    """
    # Collect all table names from both sources, ignoring metadata keys
    tables = {k for k in manifest.keys() if not k.startswith('_')}
    tables.update({k for k in receipt.keys() if not k.startswith('_')})

    errors = []
    warnings = []

    for table in sorted(tables):
        extracted = manifest.get(table, 0)
        stored = receipt.get(table, 0)

        if extracted > 0 and stored == 0:
            # CRITICAL: Data was extracted but nothing was stored.
            # This usually means:
            # - Missing storage handler
            # - Silent crash in storage handler
            # - Wrong key name in handler dispatch
            errors.append(f"{table}: extracted {extracted} -> stored 0 (100% LOSS)")

        elif extracted != stored:
            # WARNING: Partial mismatch
            # This could be:
            # - Duplicate filtering (acceptable)
            # - Partial insertion failure (concerning)
            delta = extracted - stored
            warnings.append(f"{table}: extracted {extracted} -> stored {stored} (delta: {delta})")

    # Build result
    result = {
        'status': 'FAILED' if errors else ('WARNING' if warnings else 'OK'),
        'errors': errors,
        'warnings': warnings
    }

    # Handle failures
    if errors:
        error_msg = (
            f"Fidelity Check FAILED for {file_path}. ZERO FALLBACK VIOLATION.\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
        if warnings:
            error_msg += "\nAdditional warnings:\n" + "\n".join(f"  - {w}" for w in warnings)

        if strict:
            logger.error(error_msg)
            raise DataFidelityError(error_msg, details=result)
        else:
            # Log as error even when not crashing (non-strict mode)
            logger.error(f"[NON-STRICT] {error_msg}")

    elif warnings:
        # Log warnings but don't fail
        logger.warning(
            f"Fidelity Warnings for {file_path}:\n"
            + "\n".join(f"  - {w}" for w in warnings)
        )

    return result
