"""
Schema module: Language-split database schema definitions.

This module merges all language-specific schema modules into a unified TABLES registry.
Each submodule defines tables for a specific domain (core, Python, Node.js, infrastructure, planning).

Design Philosophy:
- Language-split organization (no monolith)
- Single source of truth per domain
- Explicit imports and merging
- Backward-compatible TABLES export
"""

from typing import Dict
from .utils import TableSchema
from .core_schema import CORE_TABLES
from .security_schema import SECURITY_TABLES
from .frameworks_schema import FRAMEWORKS_TABLES
from .python_schema import PYTHON_TABLES
from .node_schema import NODE_TABLES
from .infrastructure_schema import INFRASTRUCTURE_TABLES
from .planning_schema import PLANNING_TABLES
from .graphs_schema import GRAPH_TABLES

# ============================================================================
# UNIFIED TABLES REGISTRY - repo_index.db tables ONLY
# Merge all domain-specific registries into single export
# ============================================================================

TABLES: Dict[str, TableSchema] = {
    **CORE_TABLES,
    **SECURITY_TABLES,
    **FRAMEWORKS_TABLES,
    **PYTHON_TABLES,
    **NODE_TABLES,
    **INFRASTRUCTURE_TABLES,
    **PLANNING_TABLES,
}

# ============================================================================
# GRAPH TABLES REGISTRY - graphs.db tables (separate database)
# NOT merged into TABLES - different lifecycle and query patterns
# ============================================================================

# GRAPH_TABLES imported separately for graph/store.py
# See: CLAUDE.md "WHY TWO DATABASES" for architectural rationale

# Export for backward compatibility
__all__ = [
    "TABLES",
    "GRAPH_TABLES",
    "TableSchema",
    "CORE_TABLES",
    "SECURITY_TABLES",
    "FRAMEWORKS_TABLES",
    "PYTHON_TABLES",
    "NODE_TABLES",
    "INFRASTRUCTURE_TABLES",
    "PLANNING_TABLES",
]
