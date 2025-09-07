"""Backward compatibility shim for taint analyzer.

This file exists to maintain backward compatibility for code that imports
from theauditor.taint_analyzer directly. All functionality has been
refactored into the theauditor.taint package for better maintainability.

This ensures that:
  - from theauditor.taint_analyzer import trace_taint  # STILL WORKS
  - from theauditor import taint_analyzer  # STILL WORKS
  - import theauditor.taint_analyzer  # STILL WORKS
"""

# Import everything from the refactored taint package
from theauditor.taint import *

# This shim ensures 100% backward compatibility while the actual
# implementation is now modularized in theauditor/taint/