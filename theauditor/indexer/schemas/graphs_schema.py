"""Graph database schema definitions - Used by graphs.db ONLY."""

from .utils import Column, TableSchema

GRAPH_NODES = TableSchema(
    name="nodes",
    columns=[
        Column("id", "TEXT", nullable=False),  # Node identifier (file path, function name, etc.)
        Column("file", "TEXT", nullable=False),
        Column("lang", "TEXT"),
        Column("loc", "INTEGER", default="0"),
        Column("churn", "INTEGER"),
        Column("variable_name", "TEXT"),
        Column("scope", "TEXT"),
        Column(
            "type", "TEXT", default="'module'"
        ),  # Node type: 'module', 'function', 'variable', 'resource'
        Column(
            "graph_type", "TEXT", nullable=False
        ),  # Graph type: 'import', 'call', 'data_flow', 'terraform_provisioning'
        Column("metadata", "TEXT"),
        Column("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["id", "graph_type"],  # Composite PK: same ID can exist in different graph types
    indexes=[
        ("idx_nodes_file", ["file"]),
        ("idx_nodes_type", ["type"]),
        ("idx_nodes_graph_type", ["graph_type"]),
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
        Column("expression", "TEXT"),
        Column("function", "TEXT"),
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
    unique_constraints=[],
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
