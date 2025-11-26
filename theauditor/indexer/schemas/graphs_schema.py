"""
Graph database schema definitions - Used by graphs.db ONLY.

This module contains table schemas for the separate graphs.db database:
- Graph nodes (modules, functions, variables)
- Graph edges (imports, calls, data flow)
- Analysis results (cycles, hotspots, layers)

Design Philosophy:
- Physically separate database from repo_index.db (different query patterns)
- Optimized for bidirectional graph traversal (dual indexes on source/target)
- Denormalized metadata (JSON blobs for flexible graph properties)
- Polymorphic graph_type column (single tables for import/call/data_flow graphs)
- NOT included in main TABLES registry (separate lifecycle)

Performance Features:
- Bidirectional edge indexes (idx_edges_source + idx_edges_target)
- Composite UNIQUE constraint creates automatic covering index
- Denormalized metadata avoids excessive JOINs
- Timestamp tracking for incremental analysis

Database Locations:
- graphs.db: .pf/graphs.db (opt-in, built via `aud graph build`)
- repo_index.db: .pf/repo_index.db (automatic, built via `aud index`)

See: CLAUDE.md "WHY TWO DATABASES" section for architectural rationale
"""

from .utils import Column, TableSchema


# ============================================================================
# GRAPH NODES - Modules, functions, variables, resources
# ============================================================================

GRAPH_NODES = TableSchema(
    name="nodes",
    columns=[
        Column("id", "TEXT", primary_key=True),  # PRIMARY KEY implies NOT NULL
        Column("file", "TEXT", nullable=False),
        Column("lang", "TEXT"),  # Language: 'python', 'typescript', 'javascript'
        Column("loc", "INTEGER", default="0"),  # Lines of code
        Column("churn", "INTEGER"),  # Git churn metric (commits touching this file)
        Column("type", "TEXT", default="'module'"),  # Node type: 'module', 'function', 'variable', 'resource'
        Column("graph_type", "TEXT", nullable=False),  # Graph type: 'import', 'call', 'data_flow', 'terraform_provisioning'
        Column("metadata", "TEXT"),  # JSON blob for flexible graph-specific properties
        Column("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
    ],
    indexes=[
        ("idx_nodes_file", ["file"]),
        ("idx_nodes_type", ["type"]),
    ]
)

# ============================================================================
# GRAPH EDGES - Imports, calls, data flow, provisioning dependencies
# ============================================================================

GRAPH_EDGES = TableSchema(
    name="edges",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),  # PRIMARY KEY implies NOT NULL
        Column("source", "TEXT", nullable=False),  # Source node ID
        Column("target", "TEXT", nullable=False),  # Target node ID
        Column("type", "TEXT", default="'import'"),  # Edge type: 'import', 'call', 'assignment', 'return', 'provision'
        Column("file", "TEXT", nullable=False),  # File where edge originates
        Column("line", "INTEGER", nullable=False, default="0"),  # Line number where edge originates
        Column("graph_type", "TEXT", nullable=False),  # Graph type: 'import', 'call', 'data_flow', 'terraform_provisioning'
        Column("metadata", "TEXT"),  # JSON blob for flexible edge properties
        Column("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
    ],
    indexes=[
        # CRITICAL: Bidirectional indexes for efficient graph traversal
        ("idx_edges_source", ["source"]),  # Find "what does X depend on?" (downstream)
        ("idx_edges_target", ["target"]),  # Find "what depends on X?" (upstream)
    ],
    unique_constraints=[
        # Composite UNIQUE constraint creates automatic covering index for duplicate detection
        # Prevents duplicate edges: (A -> B, 'import', 'import_graph')
        ["source", "target", "type", "graph_type"]
    ]
)

# ============================================================================
# ANALYSIS RESULTS - Cached analysis outputs (cycles, hotspots, layers)
# ============================================================================

ANALYSIS_RESULTS = TableSchema(
    name="analysis_results",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),  # PRIMARY KEY implies NOT NULL
        Column("analysis_type", "TEXT", nullable=False),  # 'cycles', 'hotspots', 'layers', 'blast_radius'
        Column("result_json", "TEXT", nullable=False),  # Full analysis result as JSON
        Column("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
    ],
    indexes=[]  # No indexes in original store.py schema
)

# ============================================================================
# GRAPH TABLES REGISTRY - Separate from main TABLES
# ============================================================================

GRAPH_TABLES: dict[str, TableSchema] = {
    "nodes": GRAPH_NODES,
    "edges": GRAPH_EDGES,
    "analysis_results": ANALYSIS_RESULTS,
}

# NOTE: GRAPH_TABLES is intentionally separate from main TABLES registry.
# graphs.db has different lifecycle (opt-in build) and query patterns (graph traversal).
# See theauditor/graph/store.py for usage.
