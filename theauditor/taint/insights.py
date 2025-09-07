"""Backward compatibility shim for taint insights.

This file exists to maintain backward compatibility for code that imports
from theauditor.taint.insights directly. All functionality has been moved to
theauditor.insights.taint for better organization.

This ensures that:
  - from theauditor.taint.insights import calculate_severity  # STILL WORKS
  - from theauditor.taint.insights import format_taint_report  # STILL WORKS
  - import theauditor.taint.insights  # STILL WORKS
"""

# Import everything from the new location
from theauditor.insights.taint import *

# This shim ensures 100% backward compatibility while the actual
# implementation is now in theauditor/insights/taint.py