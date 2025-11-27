"""Backward compatibility shim for ML insights.

This file exists to maintain backward compatibility for code that imports
from theauditor.ml directly. All functionality has been moved to
theauditor.insights.ml for better organization.

This ensures that:
  - from theauditor.ml import learn  # STILL WORKS
  - from theauditor.ml import suggest  # STILL WORKS
  - import theauditor.ml  # STILL WORKS
"""

from theauditor.insights.ml import *
