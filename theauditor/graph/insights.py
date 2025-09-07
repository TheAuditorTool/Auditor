"""Backward compatibility shim for graph insights.

This file exists to maintain backward compatibility for code that imports
from theauditor.graph.insights directly. All functionality has been moved to
theauditor.insights.graph for better organization.

This ensures that:
  - from theauditor.graph.insights import GraphInsights  # STILL WORKS
  - from theauditor.graph import insights  # STILL WORKS
  - import theauditor.graph.insights  # STILL WORKS
"""

# Import everything from the new location
from theauditor.insights.graph import *

# This shim ensures 100% backward compatibility while the actual
# implementation is now in theauditor/insights/graph.py