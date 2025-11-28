"""Data Fidelity Control System."""

import logging

from .exceptions import DataFidelityError

logger = logging.getLogger(__name__)


def reconcile_fidelity(
    manifest: dict[str, int], receipt: dict[str, int], file_path: str, strict: bool = True
) -> dict[str, any]:
    """Compare extraction manifest (what was found) vs storage receipt (what was saved)."""

    tables = {k for k in manifest if not k.startswith("_")}
    tables.update({k for k in receipt if not k.startswith("_")})

    errors = []
    warnings = []

    for table in sorted(tables):
        extracted = manifest.get(table, 0)
        stored = receipt.get(table, 0)

        if extracted > 0 and stored == 0:
            errors.append(f"{table}: extracted {extracted} -> stored 0 (100% LOSS)")

        elif extracted != stored:
            delta = extracted - stored
            warnings.append(f"{table}: extracted {extracted} -> stored {stored} (delta: {delta})")

    result = {
        "status": "FAILED" if errors else ("WARNING" if warnings else "OK"),
        "errors": errors,
        "warnings": warnings,
    }

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
            logger.error(f"[NON-STRICT] {error_msg}")

    elif warnings:
        logger.warning(
            f"Fidelity Warnings for {file_path}:\n" + "\n".join(f"  - {w}" for w in warnings)
        )

    return result
