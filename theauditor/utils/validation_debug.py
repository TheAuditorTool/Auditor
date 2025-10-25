"""Debug logging for validation framework implementation.

This module provides debug logging specifically for tracking validation framework
detection, extraction, and taint analysis integration.

Usage:
    Set environment variable: THEAUDITOR_VALIDATION_DEBUG=1

    from theauditor.utils.validation_debug import log_validation

    log_validation("L1-DETECT", "Found zod in package.json", {"version": "4.1.11"})
    log_validation("L2-EXTRACT", "Extracted parseAsync call", {"line": 19})
    log_validation("L3-TAINT", "Checking sanitizer", {"source_line": 10, "sink_line": 60})
"""

import os
import sys
import json


VALIDATION_DEBUG = os.getenv('THEAUDITOR_VALIDATION_DEBUG', '0') == '1'


def log_validation(layer: str, message: str, data: dict = None):
    """Log validation framework detection/extraction/analysis.

    Args:
        layer: Layer identifier (L1-DETECT, L2-EXTRACT, L3-TAINT)
        message: Human-readable log message
        data: Optional dictionary of structured data to log

    Example:
        log_validation("L1-DETECT", "Found validation framework", {
            "framework": "zod",
            "version": "4.1.11",
            "source": "backend/package.json"
        })
    """
    if not VALIDATION_DEBUG:
        return

    prefix = f"[VALIDATION-{layer}]"
    print(f"{prefix} {message}", file=sys.stderr)

    if data:
        # Pretty print JSON data with indentation
        data_str = json.dumps(data, indent=2)
        # Indent each line for visual hierarchy
        for line in data_str.split('\n'):
            print(f"{prefix}   {line}", file=sys.stderr)


def is_validation_debug_enabled() -> bool:
    """Check if validation debug logging is enabled.

    Returns:
        True if THEAUDITOR_VALIDATION_DEBUG=1 is set
    """
    return VALIDATION_DEBUG
