"""Graph store module - persistence and database operations for graphs."""

import json
import sqlite3
from pathlib import Path
from typing import Any


class XGraphStore:
    """Store and query cross-project graphs in SQLite."""
    
    def __init__(self, db_path: str = "./.pf/graphs.db"):
        """
        Initialize store with database path.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    def _init_schema(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Nodes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    file TEXT NOT NULL,
                    lang TEXT,
                    loc INTEGER DEFAULT 0,
                    churn INTEGER,
                    type TEXT DEFAULT 'module',
                    graph_type TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Edges table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    type TEXT DEFAULT 'import',
                    file TEXT,
                    line INTEGER,
                    graph_type TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, target, type, graph_type)
                )
            """)
            
            # Analysis results table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_type TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type)")

            conn.commit()
    
    def save_import_graph(self, graph: dict[str, Any]) -> None:
        """
        Save import graph to database.
        
        Args:
            graph: Import graph with nodes and edges
        """
        with sqlite3.connect(self.db_path) as conn:
            # Clear existing import graph
            conn.execute("DELETE FROM nodes WHERE graph_type = 'import'")
            conn.execute("DELETE FROM edges WHERE graph_type = 'import'")
            
            # Insert nodes
            for node in graph.get("nodes", []):
                metadata_json = json.dumps(node.get("metadata", {})) if node.get("metadata") else None
                conn.execute(
                    """
                    INSERT OR REPLACE INTO nodes 
                    (id, file, lang, loc, churn, type, graph_type, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, 'import', ?)
                    """,
                    (
                        node["id"],
                        node["file"],
                        node.get("lang"),
                        node.get("loc", 0),
                        node.get("churn"),
                        node.get("type", "module"),
                        metadata_json,
                    ),
                )

            # Insert edges
            for edge in graph.get("edges", []):
                metadata_json = json.dumps(edge.get("metadata", {})) if edge.get("metadata") else None
                conn.execute(
                    """
                    INSERT OR IGNORE INTO edges 
                    (source, target, type, file, line, graph_type, metadata)
                    VALUES (?, ?, ?, ?, ?, 'import', ?)
                    """,
                    (
                        edge["source"],
                        edge["target"],
                        edge.get("type", "import"),
                        edge.get("file"),
                        edge.get("line"),
                        metadata_json,
                    ),
                )
            
            conn.commit()
    
    def save_call_graph(self, graph: dict[str, Any]) -> None:
        """
        Save call graph to database.
        
        Args:
            graph: Call graph with nodes and edges
        """
        with sqlite3.connect(self.db_path) as conn:
            # Clear existing call graph
            conn.execute("DELETE FROM nodes WHERE graph_type = 'call'")
            conn.execute("DELETE FROM edges WHERE graph_type = 'call'")
            
            # Insert nodes
            for node in graph.get("nodes", []):
                metadata_json = json.dumps(node.get("metadata", {})) if node.get("metadata") else None
                conn.execute(
                    """
                    INSERT OR REPLACE INTO nodes 
                    (id, file, lang, loc, churn, type, graph_type, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, 'call', ?)
                    """,
                    (
                        node["id"],
                        node["file"],
                        node.get("lang"),
                        node.get("loc", 0),
                        node.get("churn"),
                        node.get("type", "function"),
                        metadata_json,
                    ),
                )

            # Insert edges
            for edge in graph.get("edges", []):
                metadata_json = json.dumps(edge.get("metadata", {})) if edge.get("metadata") else None
                conn.execute(
                    """
                    INSERT OR IGNORE INTO edges 
                    (source, target, type, file, line, graph_type, metadata)
                    VALUES (?, ?, ?, ?, ?, 'call', ?)
                    """,
                    (
                        edge["source"],
                        edge["target"],
                        edge.get("type", "call"),
                        edge.get("file"),
                        edge.get("line"),
                        metadata_json,
                    ),
                )
            
            conn.commit()
    
    def load_import_graph(self) -> dict[str, Any]:
        """
        Load import graph from database.
        
        Returns:
            Import graph dict
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Load nodes
            nodes = []
            for row in conn.execute(
                "SELECT * FROM nodes WHERE graph_type = 'import'"
            ):
                nodes.append({
                    "id": row["id"],
                    "file": row["file"],
                    "lang": row["lang"],
                    "loc": row["loc"],
                    "churn": row["churn"],
                    "type": row["type"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                })
            
            # Load edges
            edges = []
            for row in conn.execute(
                "SELECT * FROM edges WHERE graph_type = 'import'"
            ):
                edges.append({
                    "source": row["source"],
                    "target": row["target"],
                    "type": row["type"],
                    "file": row["file"],
                    "line": row["line"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                })
            
            return {"nodes": nodes, "edges": edges}
    
    def load_call_graph(self) -> dict[str, Any]:
        """
        Load call graph from database.
        
        Returns:
            Call graph dict
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Load nodes
            nodes = []
            for row in conn.execute(
                "SELECT * FROM nodes WHERE graph_type = 'call'"
            ):
                nodes.append({
                    "id": row["id"],
                    "file": row["file"],
                    "lang": row["lang"],
                    "loc": row["loc"],
                    "churn": row["churn"],
                    "type": row["type"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                })
            
            # Load edges
            edges = []
            for row in conn.execute(
                "SELECT * FROM edges WHERE graph_type = 'call'"
            ):
                edges.append({
                    "source": row["source"],
                    "target": row["target"],
                    "type": row["type"],
                    "file": row["file"],
                    "line": row["line"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                })
            
            return {"nodes": nodes, "edges": edges}
    
    def query_dependencies(
        self, 
        node_id: str, 
        direction: str = "both",
        graph_type: str = "import"
    ) -> dict[str, list[str]]:
        """
        Query dependencies of a node.
        
        Args:
            node_id: Node to query
            direction: 'upstream', 'downstream', or 'both'
            graph_type: 'import' or 'call'
            
        Returns:
            Dict with upstream and/or downstream dependencies
        """
        result = {}
        
        with sqlite3.connect(self.db_path) as conn:
            if direction in ["upstream", "both"]:
                # Find who depends on this node
                upstream = []
                for row in conn.execute(
                    "SELECT DISTINCT source FROM edges WHERE target = ? AND graph_type = ?",
                    (node_id, graph_type)
                ):
                    upstream.append(row[0])
                result["upstream"] = upstream
            
            if direction in ["downstream", "both"]:
                # Find what this node depends on
                downstream = []
                for row in conn.execute(
                    "SELECT DISTINCT target FROM edges WHERE source = ? AND graph_type = ?",
                    (node_id, graph_type)
                ):
                    downstream.append(row[0])
                result["downstream"] = downstream
        
        return result
    
    def query_calls(
        self,
        node_id: str,
        direction: str = "both"
    ) -> dict[str, list[str]]:
        """
        Query function calls related to a node.
        
        Args:
            node_id: Node to query
            direction: 'callers', 'callees', or 'both'
            
        Returns:
            Dict with callers and/or callees
        """
        result = {}
        
        with sqlite3.connect(self.db_path) as conn:
            if direction in ["callers", "both"]:
                # Find who calls this function
                callers = []
                for row in conn.execute(
                    "SELECT DISTINCT source FROM edges WHERE target = ? AND graph_type = 'call'",
                    (node_id,)
                ):
                    callers.append(row[0])
                result["callers"] = callers
            
            if direction in ["callees", "both"]:
                # Find what this function calls
                callees = []
                for row in conn.execute(
                    "SELECT DISTINCT target FROM edges WHERE source = ? AND graph_type = 'call'",
                    (node_id,)
                ):
                    callees.append(row[0])
                result["callees"] = callees
        
        return result
    
    def save_analysis_result(
        self, 
        analysis_type: str, 
        result: dict[str, Any]
    ) -> None:
        """
        Save analysis result to database.
        
        Args:
            analysis_type: Type of analysis (e.g., 'cycles', 'hotspots')
            result: Analysis result dict
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO analysis_results (analysis_type, result_json)
                VALUES (?, ?)
                """,
                (analysis_type, json.dumps(result))
            )
            conn.commit()
    
    def get_latest_analysis(self, analysis_type: str) -> dict[str, Any] | None:
        """
        Get most recent analysis result of given type.
        
        Args:
            analysis_type: Type of analysis
            
        Returns:
            Analysis result dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT result_json FROM analysis_results 
                WHERE analysis_type = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (analysis_type,)
            ).fetchone()
            
            if row:
                return json.loads(row[0])
            return None
    
    def get_graph_stats(self) -> dict[str, Any]:
        """
        Get summary statistics about stored graphs.
        
        Returns:
            Dict with node and edge counts
        """
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
        """
        Get nodes with high risk based on connectivity and churn.
        
        Args:
            threshold: Risk threshold (0-1)
            limit: Maximum number of nodes to return
            
        Returns:
            List of high-risk nodes
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Calculate risk based on in-degree and churn
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
                nodes.append({
                    "id": row["id"],
                    "file": row["file"],
                    "churn": row["churn"],
                    "in_degree": row["in_degree"],
                    "risk_score": row["risk_score"],
                })
            
            return nodes
