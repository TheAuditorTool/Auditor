"""Graph store module - persistence and database operations for graphs."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from theauditor.indexer.fidelity_utils import FidelityToken
from theauditor.indexer.schemas.graphs_schema import GRAPH_TABLES
from theauditor.utils.logging import logger

from .exceptions import GraphFidelityError
from .fidelity import reconcile_graph_fidelity


class XGraphStore:
    """Store and query cross-project graphs in SQLite."""

    def __init__(self, db_path: str = "./.pf/graphs.db"):
        """Initialize store with database path."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema using TableSchema definitions."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            for _table_name, schema in GRAPH_TABLES.items():
                cursor.execute(schema.create_table_sql())

                for index_sql in schema.create_indexes_sql():
                    cursor.execute(index_sql)

            conn.commit()

    def _save_graph_bulk(
        self,
        graph: dict[str, Any],
        graph_type: str,
        default_node_type: str = "node",
        default_edge_type: str = "edge",
        file_path: str | None = None,
    ) -> None:
        """Generic bulk saver using executemany for 10x performance.

        Phase 0.4: Added file_path parameter for incremental updates.
        Phase 0.5: Added explicit transaction with rollback on failure.
        Phase 0.6: Added fidelity enforcement with manifest-receipt-reconcile.

        Args:
            graph: Dict with 'nodes' and 'edges' lists
            graph_type: Type of graph ('import', 'call', 'data_flow', etc.)
            default_node_type: Default type for nodes without explicit type
            default_edge_type: Default type for edges without explicit type
            file_path: If provided, only delete/update nodes/edges for this file.
                      If None, full rebuild (deletes all nodes/edges of graph_type).
        """

        manifest = graph.get("_extraction_manifest", {})

        graph_metadata = graph.get("metadata")
        if graph_metadata:
            self._store_graph_metadata(graph_type, graph_metadata, file_path)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            if file_path:
                cursor.execute(
                    "SELECT id FROM nodes WHERE graph_type = ? AND file = ?",
                    (graph_type, file_path),
                )
                node_ids_to_delete = [row[0] for row in cursor.fetchall()]

                if node_ids_to_delete:
                    placeholders = ",".join("?" * len(node_ids_to_delete))
                    cursor.execute(
                        f"DELETE FROM edges WHERE graph_type = ? AND target IN ({placeholders})",
                        [graph_type] + node_ids_to_delete,
                    )

                cursor.execute(
                    "DELETE FROM nodes WHERE graph_type = ? AND file = ?", (graph_type, file_path)
                )

                cursor.execute(
                    "DELETE FROM edges WHERE graph_type = ? AND file = ?", (graph_type, file_path)
                )
            else:
                cursor.execute("DELETE FROM nodes WHERE graph_type = ?", (graph_type,))
                cursor.execute("DELETE FROM edges WHERE graph_type = ?", (graph_type,))

            nodes_data = []
            for node in graph.get("nodes", []):
                metadata_json = (
                    json.dumps(node.get("metadata", {})) if node.get("metadata") else None
                )
                nodes_data.append(
                    (
                        node["id"],
                        node["file"],
                        node.get("lang"),
                        node.get("loc", 0),
                        node.get("churn"),
                        node.get("variable_name"),
                        node.get("scope"),
                        node.get("type", default_node_type),
                        graph_type,
                        metadata_json,
                    )
                )

            edges_data = []
            for edge in graph.get("edges", []):
                metadata_json = (
                    json.dumps(edge.get("metadata", {})) if edge.get("metadata") else None
                )
                edges_data.append(
                    (
                        edge["source"],
                        edge["target"],
                        edge.get("type", default_edge_type),
                        edge.get("file"),
                        edge.get("line"),
                        edge.get("expression"),
                        edge.get("function"),
                        graph_type,
                        metadata_json,
                    )
                )

            valid_node_ids = {n[0] for n in nodes_data}
            orphaned = [
                (e[0], e[1])
                for e in edges_data
                if e[0] not in valid_node_ids or e[1] not in valid_node_ids
            ]

            if orphaned:
                logger.warning(f"GATEKEEPER: {len(orphaned)} orphaned edges in {graph_type}")
                for src, tgt in orphaned[:10]:
                    logger.warning(f"  Edge {src} -> {tgt} references missing node")
                raise GraphFidelityError(
                    f"Orphaned edges in {graph_type}",
                    details={"count": len(orphaned), "sample": orphaned[:5]},
                )

            node_columns = [
                "id",
                "file",
                "lang",
                "loc",
                "churn",
                "variable_name",
                "scope",
                "type",
                "graph_type",
                "metadata",
            ]
            edge_columns = [
                "source",
                "target",
                "type",
                "file",
                "line",
                "expression",
                "function",
                "graph_type",
                "metadata",
            ]

            receipt = {
                "nodes": FidelityToken.create_receipt(
                    count=len(nodes_data),
                    columns=node_columns,
                    tx_id=manifest.get("nodes", {}).get("tx_id"),
                    data_bytes=sum(len(str(n)) for n in nodes_data),
                ),
                "edges": FidelityToken.create_receipt(
                    count=len(edges_data),
                    columns=edge_columns,
                    tx_id=manifest.get("edges", {}).get("tx_id"),
                    data_bytes=sum(len(str(e)) for e in edges_data),
                ),
            }

            if graph_metadata and "metadata" in manifest:
                receipt["metadata"] = FidelityToken.create_receipt(
                    count=len(graph_metadata),
                    columns=[],
                    tx_id=manifest.get("metadata", {}).get("tx_id"),
                    data_bytes=sum(len(str(k)) + len(str(v)) for k, v in graph_metadata.items()),
                )

            if not manifest:
                raise GraphFidelityError(
                    f"NO MANIFEST: Builder for {graph_type} sent data without fidelity manifest. "
                    "All producers MUST call FidelityToken.attach_manifest().",
                    details={
                        "graph_type": graph_type,
                        "nodes": len(nodes_data),
                        "edges": len(edges_data),
                    },
                )

            reconcile_graph_fidelity(manifest, receipt, f"GraphStore:{graph_type}", strict=True)

            if nodes_data:
                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO nodes
                    (id, file, lang, loc, churn, variable_name, scope, type, graph_type, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    nodes_data,
                )

            if edges_data:
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO edges
                    (source, target, type, file, line, expression, function, graph_type, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    edges_data,
                )

            conn.commit()

            # POST-COMMIT VERIFICATION: Ensure nodes actually persisted
            cursor.execute(
                "SELECT COUNT(*) FROM nodes WHERE graph_type = ?", (graph_type,)
            )
            actual_node_count = cursor.fetchone()[0]
            if actual_node_count != len(nodes_data):
                raise GraphFidelityError(
                    f"POST-COMMIT DATA LOSS in {graph_type}: "
                    f"Prepared {len(nodes_data)} nodes, DB has {actual_node_count}. "
                    f"Lost {len(nodes_data) - actual_node_count} nodes. "
                    "Check for ID collisions across graph types.",
                    details={
                        "expected": len(nodes_data),
                        "actual": actual_node_count,
                        "graph_type": graph_type,
                    },
                )

            logger.info(
                f"[GraphStore] Saved {graph_type}: {len(nodes_data)} nodes, {len(edges_data)} edges"
            )

        except GraphFidelityError:
            conn.rollback()
            raise

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Graph save failed for {graph_type}: {e}") from e

        finally:
            conn.close()

    def _store_graph_metadata(
        self, graph_type: str, metadata: dict[str, Any], file_path: str | None
    ) -> None:
        """Store graph metadata in analysis_results table.

        Nothing gets dropped silently. Every piece of data is stored.
        """
        analysis_type = f"graph_metadata:{graph_type}"
        if file_path:
            analysis_type = f"graph_metadata:{graph_type}:{file_path}"

        self.save_analysis_result(analysis_type, metadata)
        logger.debug(f"[GraphStore] Stored metadata for {graph_type}: {len(metadata)} keys")

    def save_import_graph(self, graph: dict[str, Any]) -> None:
        """Save import graph to database."""
        self._save_graph_bulk(
            graph, "import", default_node_type="module", default_edge_type="import"
        )

    def save_call_graph(self, graph: dict[str, Any]) -> None:
        """Save call graph to database."""
        self._save_graph_bulk(graph, "call", default_node_type="function", default_edge_type="call")

    def save_data_flow_graph(self, graph: dict[str, Any]) -> None:
        """Save data flow graph to database."""
        self._save_graph_bulk(
            graph, "data_flow", default_node_type="variable", default_edge_type="assignment"
        )

    def save_custom_graph(self, graph: dict[str, Any], graph_type: str) -> None:
        """Save custom graph type to database."""
        self._save_graph_bulk(
            graph, graph_type, default_node_type="resource", default_edge_type="edge"
        )

    def _load_graph(self, graph_type: str) -> dict[str, Any]:
        """Generic graph loader for any graph type."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            nodes = []
            for row in conn.execute("SELECT * FROM nodes WHERE graph_type = ?", (graph_type,)):
                nodes.append(
                    {
                        "id": row["id"],
                        "file": row["file"],
                        "lang": row["lang"],
                        "loc": row["loc"],
                        "churn": row["churn"],
                        "variable_name": row["variable_name"],
                        "scope": row["scope"],
                        "type": row["type"],
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    }
                )

            edges = []
            for row in conn.execute("SELECT * FROM edges WHERE graph_type = ?", (graph_type,)):
                edges.append(
                    {
                        "source": row["source"],
                        "target": row["target"],
                        "type": row["type"],
                        "file": row["file"],
                        "line": row["line"],
                        "expression": row["expression"],
                        "function": row["function"],
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    }
                )

            return {"nodes": nodes, "edges": edges}

    def load_import_graph(self) -> dict[str, Any]:
        """Load import graph from database."""
        return self._load_graph("import")

    def load_call_graph(self) -> dict[str, Any]:
        """Load call graph from database."""
        return self._load_graph("call")

    def query_dependencies(
        self, node_id: str, direction: str = "both", graph_type: str = "import"
    ) -> dict[str, list[str]]:
        """Query dependencies of a node."""
        result = {}

        with sqlite3.connect(self.db_path) as conn:
            if direction in ["upstream", "both"]:
                upstream = []
                for row in conn.execute(
                    "SELECT DISTINCT source FROM edges WHERE target = ? AND graph_type = ?",
                    (node_id, graph_type),
                ):
                    upstream.append(row[0])
                result["upstream"] = upstream

            if direction in ["downstream", "both"]:
                downstream = []
                for row in conn.execute(
                    "SELECT DISTINCT target FROM edges WHERE source = ? AND graph_type = ?",
                    (node_id, graph_type),
                ):
                    downstream.append(row[0])
                result["downstream"] = downstream

        return result

    def query_calls(self, node_id: str, direction: str = "both") -> dict[str, list[str]]:
        """Query function calls related to a node."""
        result = {}

        with sqlite3.connect(self.db_path) as conn:
            if direction in ["callers", "both"]:
                callers = []
                for row in conn.execute(
                    "SELECT DISTINCT source FROM edges WHERE target = ? AND graph_type = 'call'",
                    (node_id,),
                ):
                    callers.append(row[0])
                result["callers"] = callers

            if direction in ["callees", "both"]:
                callees = []
                for row in conn.execute(
                    "SELECT DISTINCT target FROM edges WHERE source = ? AND graph_type = 'call'",
                    (node_id,),
                ):
                    callees.append(row[0])
                result["callees"] = callees

        return result

    def save_analysis_result(self, analysis_type: str, result: dict[str, Any]) -> None:
        """Save analysis result to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO analysis_results (analysis_type, result_json)
                VALUES (?, ?)
                """,
                (analysis_type, json.dumps(result)),
            )
            conn.commit()

    def get_latest_analysis(self, analysis_type: str) -> dict[str, Any] | None:
        """Get most recent analysis result of given type."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT result_json FROM analysis_results
                WHERE analysis_type = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (analysis_type,),
            ).fetchone()

            if row:
                return json.loads(row[0])
            return None

    def get_graph_stats(self) -> dict[str, Any]:
        """Get summary statistics about stored graphs."""
        with sqlite3.connect(self.db_path) as conn:
            stats = {
                "import_nodes": conn.execute(
                    "SELECT COUNT(*) FROM nodes WHERE graph_type = 'import'"
                ).fetchone()[0],
                "import_edges": conn.execute(
                    "SELECT COUNT(*) FROM edges WHERE graph_type = 'import'"
                ).fetchone()[0],
                "call_nodes": conn.execute(
                    "SELECT COUNT(*) FROM nodes WHERE graph_type = 'call'"
                ).fetchone()[0],
                "call_edges": conn.execute(
                    "SELECT COUNT(*) FROM edges WHERE graph_type = 'call'"
                ).fetchone()[0],
            }

            return stats

    def get_high_risk_nodes(self, threshold: float = 0.5, limit: int = 10) -> list[dict[str, Any]]:
        """Get nodes with high risk based on connectivity and churn."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT
                    n.id,
                    n.file,
                    n.churn,
                    COUNT(DISTINCT e.source) as in_degree,
                    (COUNT(DISTINCT e.source) * COALESCE(n.churn, 1)) / 100.0 as risk_score
                FROM nodes n
                LEFT JOIN edges e ON n.id = e.target
                WHERE n.graph_type = 'import'
                GROUP BY n.id
                HAVING risk_score > ?
                ORDER BY risk_score DESC
                LIMIT ?
            """

            nodes = []
            for row in conn.execute(query, (threshold, limit)):
                nodes.append(
                    {
                        "id": row["id"],
                        "file": row["file"],
                        "churn": row["churn"],
                        "in_degree": row["in_degree"],
                        "risk_score": row["risk_score"],
                    }
                )

            return nodes
