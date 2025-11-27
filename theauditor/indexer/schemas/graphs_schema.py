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

GRAPH_NODES = TableSchema(
    name="nodes",
    columns=[
        Column("id", "TEXT", primary_key=True),
        Column("file", "TEXT", nullable=False),
        Column("lang", "TEXT"),
        Column("loc", "INTEGER", default="0"),
        Column("churn", "INTEGER"),
        Column(
            "type", "TEXT", default="'module'"
        ),  # Node type: 'module', 'function', 'variable', 'resource'
        Column(
            "graph_type", "TEXT", nullable=False
        ),  # Graph type: 'import', 'call', 'data_flow', 'terraform_provisioning'
        Column("metadata", "TEXT"),
        Column("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
    ],
    indexes=[
        ("idx_nodes_file", ["file"]),
        ("idx_nodes_type", ["type"]),
    ],
)


GRAPH_EDGES = TableSchema(
    name="edges",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("source", "TEXT", nullable=False),
        Column("target", "TEXT", nullable=False),
        Column(
            "type", "TEXT", default="'import'"
        ),  # Edge type: 'import', 'call', 'assignment', 'return', 'provision'
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False, default="0"),
        Column(
            "graph_type", "TEXT", nullable=False
        ),  # Graph type: 'import', 'call', 'data_flow', 'terraform_provisioning'
        Column("metadata", "TEXT"),
        Column("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
    ],
    indexes=[
        ("idx_edges_source", ["source"]),
        ("idx_edges_target", ["target"]),
    ],
    unique_constraints=[["source", "target", "type", "graph_type"]],
)


ANALYSIS_RESULTS = TableSchema(
    name="analysis_results",
    columns=[
        Column("id", "INTEGER", primary_key=True, autoincrement=True),
        Column("analysis_type", "TEXT", nullable=False),
        Column("result_json", "TEXT", nullable=False),
        Column("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
    ],
    indexes=[],
)


GRAPH_TABLES: dict[str, TableSchema] = {
    "nodes": GRAPH_NODES,
    "edges": GRAPH_EDGES,
    "analysis_results": ANALYSIS_RESULTS,
}
