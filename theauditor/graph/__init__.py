"""Graph package - dependency and call graph functionality.

Core modules (always available):
- analyzer: Pure graph algorithms (cycles, paths, layers)
- builder: Graph construction from source code
- store: SQLite persistence

Optional modules:
- insights: Interpretive metrics (health scores, recommendations, hotspots)
"""

from .analyzer import XGraphAnalyzer
from .builder import Cycle, GraphEdge, GraphNode, Hotspot, ImpactAnalysis, XGraphBuilder
from .store import XGraphStore
from .visualizer import GraphVisualizer

try:
    from .insights import GraphInsights, check_insights_available, create_insights

    INSIGHTS_AVAILABLE = True
except ImportError:
    INSIGHTS_AVAILABLE = False
    GraphInsights = None

    def check_insights_available():
        return False

    def create_insights(weights=None):
        return None


__all__ = [
    "XGraphBuilder",
    "XGraphAnalyzer",
    "XGraphStore",
    "GraphVisualizer",
    "GraphNode",
    "GraphEdge",
    "Cycle",
    "Hotspot",
    "ImpactAnalysis",
    "GraphInsights",
    "INSIGHTS_AVAILABLE",
    "check_insights_available",
    "create_insights",
]
