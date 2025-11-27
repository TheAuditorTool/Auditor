"""Backward compatibility shim for graph insights.

This file exists to maintain backward compatibility for code that imports
from theauditor.graph.insights directly. All functionality has been moved to
theauditor.insights.graph for better organization.

This ensures that:
  - from theauditor.graph.insights import GraphInsights  # STILL WORKS
  - from theauditor.graph import insights  # STILL WORKS
  - import theauditor.graph.insights  # STILL WORKS
"""

from theauditor.insights.graph import *  # noqa: F403 - intentional re-export for backward compat
