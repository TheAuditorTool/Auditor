"""Debug logging for validation framework implementation."""

import json
import os
import sys

VALIDATION_DEBUG = os.getenv("THEAUDITOR_VALIDATION_DEBUG", "0") == "1"


def log_validation(layer: str, message: str, data: dict = None):
    """Log validation framework detection/extraction/analysis."""
    if not VALIDATION_DEBUG:
        return

    prefix = f"[VALIDATION-{layer}]"
    print(f"{prefix} {message}", file=sys.stderr)

    if data:
        data_str = json.dumps(data, indent=2)

        for line in data_str.split("\n"):
            print(f"{prefix}   {line}", file=sys.stderr)


def is_validation_debug_enabled() -> bool:
    """Check if validation debug logging is enabled."""
    return VALIDATION_DEBUG
