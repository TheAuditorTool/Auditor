"""Graph-based dead code detection using NetworkX and graphs.db."""

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from theauditor.utils.logging import logger

DEFAULT_EXCLUSIONS = [
    # Package/test markers
    "__init__.py",
    "test",
    "__tests__",
    ".test.",
    ".spec.",
    # Database migrations/seeders (run by CLI, not imported)
    "migration",
    "migrations",
    "seeders",
    "seeds",
    # Scripts (run directly via node/python, not imported)
    "scripts/",
    # Build artifacts
    "__pycache__",
    "node_modules",
    ".venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
    # Tool configuration files (loaded by tools, not imported)
    "eslint.config",
    "vite.config",
    "vitest.config",
    "jest.config",
    "webpack.config",
    "rollup.config",
    "tsconfig",
    "prettier.config",
    ".prettierrc",
    "tailwind.config",
    "postcss.config",
    # Database CLI configs (Sequelize, Knex, etc.)
    "database-cli",
    ".sequelizerc",
    "knexfile",
]


def load_exclusions_from_config(root: Path) -> list[str] | None:
    """Load dead code exclusion patterns from .auditor/config.json.

    Config file format:
    {
        "deadcode": {
            "exclusions": ["pattern1", "pattern2", ...]
        }
    }

    Returns None if no config file exists (caller should use DEFAULT_EXCLUSIONS).
    Raises ValueError if config file exists but is malformed.
    """
    config_path = root / ".auditor" / "config.json"

    if not config_path.exists():
        return None

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {config_path}: {e}") from e

    deadcode_config = config.get("deadcode", {})
    exclusions = deadcode_config.get("exclusions")

    if exclusions is None:
        return None

    if not isinstance(exclusions, list):
        raise ValueError(
            f"deadcode.exclusions must be a list in {config_path}, got {type(exclusions).__name__}"
        )

    return exclusions


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
    """Detect dead code using graph-based analysis.

    Zero Fallback Policy: Raises FileNotFoundError if graphs.db missing.
    """
    repo_db = Path(db_path)
    graphs_db = repo_db.parent / "graphs.db"

    if not graphs_db.exists():
        raise FileNotFoundError(
            f"graphs.db not found: {graphs_db}\nRun 'aud graph build' to create it."
        )

    detector = GraphDeadCodeDetector(str(graphs_db), str(repo_db), debug=False)

    return detector.analyze(
        path_filter=path_filter,
        exclude_patterns=exclude_patterns,
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

        self.project_root = self.graphs_db.parent.parent
        self.config_exclusions = load_exclusions_from_config(self.project_root)

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
        analyze_ghost_imports: bool = False,
    ) -> list[DeadCode]:
        """Run full dead code analysis.

        Args:
            path_filter: Only analyze files matching this path prefix
            exclude_patterns: Patterns to exclude from analysis
            analyze_symbols: Also find dead functions/classes within live modules
            analyze_ghost_imports: Detect imports that are never actually used
        """

        if exclude_patterns is None:
            exclude_patterns = self.config_exclusions or DEFAULT_EXCLUSIONS

        findings = []

        if self.debug:
            logger.info("Building import graph...")

        self.import_graph = self._build_import_graph(path_filter)
        entry_points = self._find_entry_points(self.import_graph)

        if self.debug:
            logger.info(f"  Nodes: {self.import_graph.number_of_nodes()}")
            logger.info(f"  Edges: {self.import_graph.number_of_edges()}")
            logger.info(f"  Entry points: {len(entry_points)}")

        dead_modules = self._find_dead_nodes(self.import_graph, entry_points, exclude_patterns)
        findings.extend(dead_modules)

        if analyze_symbols:
            if self.debug:
                logger.info("Building call graph for symbol analysis...")

            live_modules = {
                n for n in self.import_graph.nodes() if n not in {f.path for f in dead_modules}
            }
            self.call_graph = self._build_call_graph(path_filter, live_modules)

            dead_symbols = self._find_dead_symbols(self.call_graph, live_modules, exclude_patterns)
            findings.extend(dead_symbols)

        if analyze_ghost_imports:
            if self.debug:
                logger.info("Detecting ghost imports...")

            ghost_imports = self._detect_ghost_imports(exclude_patterns, path_filter)
            findings.extend(ghost_imports)

            if self.debug:
                logger.info(f"  Ghost imports found: {len(ghost_imports)}")

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
            query += f" AND source LIKE '{path_filter}'"

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

        cursor.execute("SELECT DISTINCT file FROM go_routes")
        entry_points.update(row[0] for row in cursor.fetchall())

        cursor.execute("""
            SELECT DISTINCT path FROM files
            WHERE ext = '.go'
            AND (path LIKE '%/main.go' OR path LIKE '%_test.go')
        """)
        entry_points.update(row[0] for row in cursor.fetchall())

        cursor.execute("""
            SELECT DISTINCT file_path FROM rust_attributes
            WHERE attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route', 'web', 'actix_web::main', 'tokio::main')
        """)
        entry_points.update(row[0] for row in cursor.fetchall())

        cursor.execute("""
            SELECT DISTINCT path FROM files
            WHERE ext = '.rs'
            AND (path LIKE '%/main.rs' OR path LIKE '%/lib.rs')
        """)
        entry_points.update(row[0] for row in cursor.fetchall())

        cursor.execute("SELECT DISTINCT path FROM files WHERE ext IN ('.sh', '.bash')")
        entry_points.update(row[0] for row in cursor.fetchall())

        return entry_points

    def _find_reachable_files_sql(
        self, entry_points: set[str], path_filter: str | None = None
    ) -> set[str]:
        """Find all reachable files from entry points using Recursive CTE.

        Replaces NetworkX in-memory graph traversal with pure SQL.
        Performance: O(1) queries, zero RAM for graph storage.
        """
        if not entry_points:
            return set()

        cursor = self.graphs_conn.cursor()

        placeholders = ",".join("?" * len(entry_points))
        entry_list = list(entry_points)

        query = f"""
            WITH RECURSIVE reachable(file_path) AS (
                -- BASE CASE: Entry points are reachable
                SELECT DISTINCT source AS file_path
                FROM edges
                WHERE source IN ({placeholders})
                  AND graph_type = 'import'

                UNION

                -- Also include entry points that may not have outgoing edges
                SELECT DISTINCT target AS file_path
                FROM edges
                WHERE source IN ({placeholders})
                  AND graph_type = 'import'

                UNION

                -- RECURSIVE STEP: Files imported by reachable files
                SELECT DISTINCT e.target
                FROM edges e
                JOIN reachable r ON e.source = r.file_path
                WHERE e.graph_type = 'import'
                  AND e.type IN ('import', 'from')
            )
            SELECT DISTINCT file_path FROM reachable
        """

        if path_filter:
            query = query.replace(
                "SELECT DISTINCT file_path FROM reachable",
                f"SELECT DISTINCT file_path FROM reachable WHERE file_path LIKE '{path_filter}'",
            )

        params = tuple(entry_list) + tuple(entry_list)
        cursor.execute(query, params)

        reachable = {row[0] for row in cursor.fetchall()}

        reachable.update(entry_points)

        return reachable

    def _get_all_files_sql(self, path_filter: str | None = None) -> set[str]:
        """Get all files from the import graph edges."""
        cursor = self.graphs_conn.cursor()

        query = """
            SELECT DISTINCT source FROM edges WHERE graph_type = 'import'
            UNION
            SELECT DISTINCT target FROM edges WHERE graph_type = 'import'
        """

        if path_filter:
            query = f"""
                SELECT DISTINCT source FROM edges
                WHERE graph_type = 'import' AND source LIKE '{path_filter}'
                UNION
                SELECT DISTINCT target FROM edges
                WHERE graph_type = 'import' AND target LIKE '{path_filter}'
            """

        cursor.execute(query)
        return {row[0] for row in cursor.fetchall()}

    def _find_dead_nodes(
        self, graph: nx.DiGraph, entry_points: set[str], exclude_patterns: list[str]
    ) -> list[DeadCode]:
        """Find dead nodes using SQL-based reachability.

        Uses Recursive CTE for reachability (O(1) query) instead of
        Python loop with nx.descendants (O(entries × edges)).
        NetworkX still used for clustering (operates on small dead node set).
        """

        reachable = self._find_reachable_files_sql(entry_points)

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

    def _detect_ghost_imports(
        self, exclude_patterns: list[str], path_filter: str | None = None
    ) -> list[DeadCode]:
        """Detect ghost imports: files imported but never actually used.

        Cross-references graphs.db (import edges) with repo_index.db (function calls).
        If File A imports File B but never calls any function from File B,
        the import is flagged as a "ghost import" - potentially dead code.

        Returns findings with type="ghost_import".
        """
        graphs_cursor = self.graphs_conn.cursor()
        repo_cursor = self.repo_conn.cursor()

        import_query = """
            SELECT DISTINCT source, target
            FROM edges
            WHERE graph_type = 'import'
              AND type IN ('import', 'from')
              AND NOT target LIKE 'external::%'
        """
        if path_filter:
            import_query += f" AND source LIKE '{path_filter}'"

        graphs_cursor.execute(import_query)
        all_imports = graphs_cursor.fetchall()

        if not all_imports:
            return []

        call_index: dict[str, set[str]] = defaultdict(set)

        repo_cursor.execute("""
            SELECT DISTINCT file, callee_file_path
            FROM function_call_args
            WHERE callee_file_path IS NOT NULL
              AND callee_file_path != ''
        """)
        for row in repo_cursor.fetchall():
            call_index[row[0]].add(row[1])

        repo_cursor.execute("""
            SELECT DISTINCT file, callee_file_path
            FROM function_call_args_jsx
            WHERE callee_file_path IS NOT NULL
              AND callee_file_path != ''
        """)
        for row in repo_cursor.fetchall():
            call_index[row[0]].add(row[1])

        all_callees = set()
        for callees in call_index.values():
            all_callees.update(callees)

        findings = []
        for importer, imported in all_imports:
            if any(pattern in importer for pattern in exclude_patterns):
                continue
            if any(pattern in imported for pattern in exclude_patterns):
                continue

            if importer in call_index and imported in call_index[importer]:
                continue

            has_call = False
            caller_callees = call_index.get(importer, set())

            for callee_file in caller_callees:
                if callee_file.endswith(imported) or imported.endswith(callee_file):
                    has_call = True
                    break
                if imported in callee_file or callee_file in imported:
                    has_call = True
                    break

            if not has_call:
                for caller_file, callees in call_index.items():
                    if caller_file.endswith(importer) or importer.endswith(caller_file):
                        if imported in callees:
                            has_call = True
                            break
                        for callee_file in callees:
                            if callee_file.endswith(imported) or imported in callee_file:
                                has_call = True
                                break
                        if has_call:
                            break

            if not has_call:
                confidence, reason = self._classify_ghost_import(importer, imported)
                findings.append(
                    DeadCode(
                        type="ghost_import",
                        path=importer,
                        name=imported,
                        line=0,
                        symbol_count=0,
                        reason=reason,
                        confidence=confidence,
                        lines_estimated=0,
                        cluster_id=None,
                    )
                )

        return findings

    def _classify_ghost_import(self, importer: str, imported: str) -> tuple[str, str]:
        """Classify confidence and reason for ghost import."""
        confidence = "medium"
        reason = f"Imports '{Path(imported).name}' but no function calls detected"

        if imported.endswith("__init__.py"):
            confidence = "low"
            reason = "Package import (may import for side effects or re-exports)"
        elif "types" in imported.lower() or "typing" in imported.lower():
            confidence = "low"
            reason = "Type definition import (used for type hints, not runtime calls)"
        elif any(pattern in imported for pattern in ["constants", "config", "settings"]):
            confidence = "low"
            reason = "Config/constants import (may use variables, not functions)"
        elif importer.endswith("__init__.py"):
            confidence = "low"
            reason = "Re-export pattern (package __init__ importing for re-export)"

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
            logger.info(f"Cluster #{cluster_id} exported to {output_path}")
            logger.info(f"    Visualize with: dot -Tpng {output_path} -o cluster_{cluster_id}.png")

    def __del__(self):
        """Close database connections."""
        if hasattr(self, "graphs_conn"):
            self.graphs_conn.close()
        if hasattr(self, "repo_conn"):
            self.repo_conn.close()
