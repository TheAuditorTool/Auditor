"""Debug logging for validation framework implementation."""

import json
import os

from theauditor.utils.logging import logger

VALIDATION_DEBUG = os.getenv("THEAUDITOR_VALIDATION_DEBUG", "0") == "1"


def log_validation(layer: str, message: str, data: dict = None):
    """Log validation framework detection/extraction/analysis."""
    if not VALIDATION_DEBUG:
        return

    prefix = f"[VALIDATION-{layer}]"
    logger.error(f"{prefix} {message}")

    if data:
        data_str = json.dumps(data, indent=2)

        for line in data_str.split("\n"):
            logger.error(f"{prefix}   {line}")


def is_validation_debug_enabled() -> bool:
    """Check if validation debug logging is enabled."""
    return VALIDATION_DEBUG
