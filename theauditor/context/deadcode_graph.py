"""Graph-based dead code detection using NetworkX and graphs.db."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

DEFAULT_EXCLUSIONS = [
    "__init__.py",
    "test",
    "__tests__",
    ".test.",
    ".spec.",
    "migration",
    "migrations",
    "__pycache__",
    "node_modules",
    ".venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
]


@dataclass
class DeadCode:
    """Base class for dead code findings."""

    type: str
    path: str
    name: str
    line: int
    symbol_count: int
    reason: str
    confidence: str
    lines_estimated: int = 0
    cluster_id: int | None = None


def detect_isolated_modules(
    db_path: str, path_filter: str = None, exclude_patterns: list[str] = None
) -> list[DeadCode]:
    """Detect dead code using graph-based analysis."""
    repo_db = Path(db_path)
    graphs_db = repo_db.parent / "graphs.db"

    if not graphs_db.exists():
        return []

    detector = GraphDeadCodeDetector(str(graphs_db), str(repo_db), debug=False)

    return detector.analyze(
        path_filter=path_filter,
        exclude_patterns=exclude_patterns or DEFAULT_EXCLUSIONS,
        analyze_symbols=False,
    )


detect_all = detect_isolated_modules


class GraphDeadCodeDetector:
    """Graph-based dead code analyzer."""

    def __init__(self, graphs_db_path: str, repo_db_path: str, debug: bool = False):
        self.graphs_db = Path(graphs_db_path)
        self.repo_db = Path(repo_db_path)
        self.debug = debug

        if not self.graphs_db.exists():
            raise FileNotFoundError(
                f"graphs.db not found: {self.graphs_db}\nRun 'aud graph build' to create it."
            )
        if not self.repo_db.exists():
            raise FileNotFoundError(
                f"repo_index.db not found: {self.repo_db}\nRun 'aud full' to create it."
            )

        self.graphs_conn = sqlite3.connect(self.graphs_db)
        self.repo_conn = sqlite3.connect(self.repo_db)

        self._validate_schema()

        self.import_graph: nx.DiGraph | None = None
        self.call_graph: nx.DiGraph | None = None

    def _validate_schema(self):
        """Validate database schema. CRASH if wrong (NO FALLBACK)."""
        cursor = self.graphs_conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='edges'")
        if not cursor.fetchone():
            raise ValueError(
                f"edges table not found in {self.graphs_db}\n"
                f"Database schema is wrong. Run 'aud graph build'."
            )

        cursor.execute("PRAGMA table_info(edges)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {"source", "target", "type", "graph_type"}
        missing = required - columns
        if missing:
            raise ValueError(
                f"edges table missing columns: {missing}\n"
                f"Database schema is wrong. Run 'aud graph build'."
            )

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'")
        if not cursor.fetchone():
            raise ValueError(
                f"nodes table not found in {self.graphs_db}\n"
                f"Database schema is wrong. Run 'aud graph build'."
            )

    def analyze(
        self,
        path_filter: str | None = None,
        exclude_patterns: list[str] | None = None,
        analyze_symbols: bool = False,
    ) -> list[DeadCode]:
        """Run full dead code analysis."""
        exclude_patterns = exclude_patterns or DEFAULT_EXCLUSIONS

        findings = []

        if self.debug:
            print("[Phase 1/2] Building import graph...")

        self.import_graph = self._build_import_graph(path_filter)
        entry_points = self._find_entry_points(self.import_graph)

        if self.debug:
            print(f"  Nodes: {self.import_graph.number_of_nodes()}")
            print(f"  Edges: {self.import_graph.number_of_edges()}")
            print(f"  Entry points: {len(entry_points)}")

        dead_modules = self._find_dead_nodes(self.import_graph, entry_points, exclude_patterns)
        findings.extend(dead_modules)

        if analyze_symbols:
            if self.debug:
                print("[Phase 2/2] Building call graph for symbol analysis...")

            live_modules = {
                n for n in self.import_graph.nodes() if n not in {f.path for f in dead_modules}
            }
            self.call_graph = self._build_call_graph(path_filter, live_modules)

            dead_symbols = self._find_dead_symbols(self.call_graph, live_modules, exclude_patterns)
            findings.extend(dead_symbols)

        return findings

    def _build_import_graph(self, path_filter: str | None = None) -> nx.DiGraph:
        """Build import graph from graphs.db."""
        graph = nx.DiGraph()
        cursor = self.graphs_conn.cursor()

        query = """
            SELECT source, target, type
            FROM edges
            WHERE graph_type = 'import'
              AND type IN ('import', 'from')
        """

        if path_filter:
            query += f" AND source LIKE '{path_filter}'"

        cursor.execute(query)

        edges_data = cursor.fetchall()
        graph.add_edges_from((row[0], row[1], {"type": row[2]}) for row in edges_data)

        return graph

    def _build_call_graph(self, path_filter: str | None, live_modules: set[str]) -> nx.DiGraph:
        """Build call graph for symbol-level analysis."""
        graph = nx.DiGraph()
        cursor = self.graphs_conn.cursor()

        query = """
            SELECT source, target, type
            FROM edges
            WHERE graph_type = 'call'
              AND type = 'call'
        """

        if path_filter:
            query += f" AND source LIKE '{path_filter}%'"

        cursor.execute(query)

        edges_data = []
        for source, target, edge_type in cursor.fetchall():
            source_file = source.split(":")[0] if ":" in source else source
            target_file = target.split(":")[0] if ":" in target else target

            if source_file in live_modules and target_file in live_modules:
                edges_data.append((source, target, {"type": edge_type}))

        graph.add_edges_from(edges_data)
        return graph

    def _find_entry_points(self, graph: nx.DiGraph) -> set[str]:
        """Multi-strategy entry point detection."""
        entry_points = set()

        for node in graph.nodes():
            if any(
                pattern in node
                for pattern in [
                    "cli.py",
                    "__main__.py",
                    "main.py",
                    "index.ts",
                    "index.js",
                    "index.tsx",
                    "App.tsx",
                ]
            ):
                entry_points.add(node)

        entry_points.update(self._find_decorated_entry_points())

        entry_points.update(self._find_framework_entry_points())

        for node in graph.nodes():
            if any(pattern in node for pattern in ["test_", ".test.", ".spec.", "_test.py"]):
                entry_points.add(node)

        return entry_points

    def _find_decorated_entry_points(self) -> set[str]:
        """Query repo_index.db for decorator-based entry points."""
        cursor = self.repo_conn.cursor()
        entry_points = set()

        cursor.execute("""
            SELECT DISTINCT file
            FROM python_decorators
            WHERE decorator_name IN (
                'route', 'get', 'post', 'put', 'delete', 'patch',  -- FastAPI/Flask
                'task', 'shared_task', 'periodic_task',            -- Celery
                'command', 'group', 'option'                       -- Click
            )
        """)
        entry_points.update(row[0] for row in cursor.fetchall())

        return entry_points

    def _find_framework_entry_points(self) -> set[str]:
        """Query repo_index.db for framework-specific entry points."""
        cursor = self.repo_conn.cursor()
        entry_points = set()

        cursor.execute("SELECT DISTINCT file FROM react_components")
        entry_points.update(row[0] for row in cursor.fetchall())

        cursor.execute("SELECT DISTINCT file FROM vue_components")
        entry_points.update(row[0] for row in cursor.fetchall())

        cursor.execute("SELECT DISTINCT file FROM python_routes")
        entry_points.update(row[0] for row in cursor.fetchall())

        return entry_points

    def _find_dead_nodes(
        self, graph: nx.DiGraph, entry_points: set[str], exclude_patterns: list[str]
    ) -> list[DeadCode]:
        """Find dead nodes using graph reachability."""

        reachable = set()
        for entry in entry_points:
            if entry in graph:
                reachable.update(nx.descendants(graph, entry))
                reachable.add(entry)

        all_nodes = set(graph.nodes())
        dead_nodes = all_nodes - reachable

        dead_nodes = {
            node
            for node in dead_nodes
            if not any(pattern in node for pattern in exclude_patterns)
            and not node.startswith("external::")
        }

        if not dead_nodes:
            return []

        dead_subgraph = graph.subgraph(dead_nodes).to_undirected()
        clusters = list(nx.connected_components(dead_subgraph))

        findings = []
        for cluster_id, cluster_nodes in enumerate(clusters):
            for node in cluster_nodes:
                symbol_count = self._get_symbol_count(node)
                confidence, reason = self._classify_dead_node(node, len(cluster_nodes))

                findings.append(
                    DeadCode(
                        type="module",
                        path=node,
                        name="",
                        line=0,
                        symbol_count=symbol_count,
                        reason=reason,
                        confidence=confidence,
                        lines_estimated=0,
                        cluster_id=cluster_id if len(cluster_nodes) > 1 else None,
                    )
                )

        return findings

    def _find_dead_symbols(
        self, call_graph: nx.DiGraph, live_modules: set[str], exclude_patterns: list[str]
    ) -> list[DeadCode]:
        """Find dead functions/classes within live modules."""
        cursor = self.repo_conn.cursor()

        placeholders = ",".join("?" * len(live_modules))
        cursor.execute(
            f"""
            SELECT path, name, line, type
            FROM symbols
            WHERE path IN ({placeholders})
              AND type IN ('function', 'method', 'class')
        """,
            tuple(live_modules),
        )
        all_symbols = {(row[0], row[1]): (row[2], row[3]) for row in cursor.fetchall()}

        called_symbols = set()
        for target in call_graph.nodes():
            if ":" in target:
                path, name = target.rsplit(":", 1)
                called_symbols.add((path, name))

        dead_symbols = set(all_symbols.keys()) - called_symbols

        findings = []
        for path, name in dead_symbols:
            if any(pattern in path for pattern in exclude_patterns):
                continue

            line, symbol_type = all_symbols[(path, name)]
            confidence, reason = self._classify_dead_symbol(name, symbol_type)

            findings.append(
                DeadCode(
                    type=symbol_type,
                    path=path,
                    name=name,
                    line=line,
                    symbol_count=1,
                    reason=reason,
                    confidence=confidence,
                    lines_estimated=0,
                    cluster_id=None,
                )
            )

        return findings

    def _get_symbol_count(self, file_path: str) -> int:
        """Query symbols table for file's symbol count."""
        cursor = self.repo_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM symbols WHERE path = ?", (file_path,))
        return cursor.fetchone()[0]

    def _classify_dead_node(self, path: str, cluster_size: int) -> tuple[str, str]:
        """Classify confidence and reason for dead module."""
        confidence = "high"
        reason = "Module never imported"

        if cluster_size > 1:
            reason = f"Part of zombie cluster ({cluster_size} files)"

        if path.endswith("__init__.py"):
            confidence = "low"
            reason = "Package marker (may be false positive)"
        elif any(pattern in path for pattern in ["migration", "alembic"]):
            confidence = "medium"
            reason = "Migration script (may be external entry)"

        return confidence, reason

    def _classify_dead_symbol(self, name: str, symbol_type: str) -> tuple[str, str]:
        """Classify confidence and reason for dead function/class."""
        confidence = "high"
        reason = f"{symbol_type.capitalize()} defined but never called"

        if name.startswith("_") and not name.startswith("__"):
            confidence = "medium"
            reason = f"Private {symbol_type} (may be internal API)"
        elif name.startswith("test_"):
            confidence = "low"
            reason = "Test function (invoked by test runner)"
        elif name in ["__init__", "__repr__", "__str__", "__eq__", "__hash__"]:
            confidence = "low"
            reason = "Magic method (invoked implicitly)"

        return confidence, reason

    def export_cluster_dot(self, cluster_id: int, findings: list[DeadCode], output_path: str):
        """Export zombie cluster as DOT file for visualization."""
        cluster_nodes = {f.path for f in findings if f.cluster_id == cluster_id}

        if not cluster_nodes:
            raise ValueError(f"Cluster #{cluster_id} not found in findings")

        subgraph = self.import_graph.subgraph(cluster_nodes)

        for node in subgraph.nodes():
            subgraph.nodes[node]["label"] = Path(node).name
            subgraph.nodes[node]["shape"] = "box"

        from networkx.drawing.nx_pydot import write_dot

        write_dot(subgraph, output_path)

        if self.debug:
            print(f"[OK] Cluster #{cluster_id} exported to {output_path}")
            print(f"    Visualize with: dot -Tpng {output_path} -o cluster_{cluster_id}.png")

    def __del__(self):
        """Close database connections."""
        if hasattr(self, "graphs_conn"):
            self.graphs_conn.close()
        if hasattr(self, "repo_conn"):
            self.repo_conn.close()
