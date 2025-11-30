"""IFDS-based taint analyzer using pre-computed graphs."""

import sqlite3
import sys
from collections import deque
from typing import TYPE_CHECKING

from .access_path import AccessPath
from .sanitizer_util import SanitizerRegistry

if TYPE_CHECKING:
    from .taint_path import TaintPath


class IFDSTaintAnalyzer:
    """Demand-driven taint analyzer using IFDS backward reachability."""

    def __init__(
        self, repo_db_path: str, graph_db_path: str, cache=None, registry=None, type_resolver=None
    ):
        """Initialize IFDS analyzer with database connections."""
        self.repo_conn = sqlite3.connect(repo_db_path)
        self.repo_conn.row_factory = sqlite3.Row
        self.repo_cursor = self.repo_conn.cursor()

        self.graph_conn = sqlite3.connect(graph_db_path)
        self.graph_conn.row_factory = sqlite3.Row
        self.graph_cursor = self.graph_conn.cursor()

        self.cache = cache
        self.registry = registry
        self.type_resolver = type_resolver

        self.summaries: dict[tuple[str, str], dict[str, set[str]]] = {}

        self.visited: set[tuple[str, str]] = set()

        self.max_depth = 10
        self.max_paths_per_sink = 100

        import os

        self.debug = bool(os.environ.get("THEAUDITOR_DEBUG"))

        if self.debug:
            print("[IFDS] ========================================", file=sys.stderr)
            print("[IFDS] IFDS Analyzer Initialized (DEBUG MODE)", file=sys.stderr)
            print(f"[IFDS] Database: {repo_db_path}", file=sys.stderr)
            print("[IFDS] ========================================", file=sys.stderr)

        self.sanitizer_registry = SanitizerRegistry(
            self.repo_cursor, self.registry, debug=self.debug
        )

    def analyze_sink_to_sources(
        self, sink: dict, sources: list[dict], max_depth: int = 10
    ) -> tuple[list[TaintPath], list[TaintPath]]:
        """Find all taint paths from sink to sources using IFDS backward analysis."""
        self.max_depth = max_depth

        source_aps = []
        for source in sources:
            source_ap = self._dict_to_access_path(source)
            if source_ap:
                source_aps.append((source, source_ap))

        if not source_aps:
            return ([], [])

        if self.debug:
            print(f"\n[IFDS] Analyzing sink: {sink.get('pattern', '?')}", file=sys.stderr)
            print(f"[IFDS] Checking against {len(source_aps)} sources", file=sys.stderr)

        vulnerable, sanitized = self._trace_backward_to_any_source(sink, source_aps, max_depth)

        if self.debug:
            print(
                f"[IFDS] Found {len(vulnerable)} vulnerable paths, {len(sanitized)} sanitized paths",
                file=sys.stderr,
            )

        return (vulnerable, sanitized)

    def _trace_backward_to_any_source(
        self, sink: dict, source_aps: list[tuple[dict, AccessPath]], max_depth: int
    ) -> tuple[list[TaintPath], list[TaintPath]]:
        """Backward trace from sink, checking if ANY source is reachable."""
        vulnerable_paths = []
        sanitized_paths = []

        sink_ap = self._dict_to_access_path(sink)
        if not sink_ap:
            return ([], [])

        worklist = deque([(sink_ap, 0, [], None)])
        visited_states: set[str] = set()
        iteration = 0

        while worklist and (len(vulnerable_paths) + len(sanitized_paths)) < self.max_paths_per_sink:
            iteration += 1
            if iteration > 10000:
                if self.debug:
                    print("[IFDS] Hit iteration limit", file=sys.stderr)
                break

            current_ap, depth, hop_chain, matched_source = worklist.popleft()

            state = current_ap.node_id
            if state in visited_states:
                continue
            visited_states.add(state)

            path_nodes = {
                hop.get("to") for hop in hop_chain if isinstance(hop, dict) and hop.get("to")
            }
            if current_ap.node_id in path_nodes:
                continue

            current_matched_source = matched_source

            if self._is_true_entry_point(current_ap.node_id):
                current_matched_source = {
                    "type": "http_request",
                    "pattern": current_ap.base,
                    "file": current_ap.file,
                    "line": 0,
                    "name": current_ap.node_id,
                }

            else:
                for source_dict, source_ap in source_aps:
                    if self._access_paths_match(current_ap, source_ap):
                        current_matched_source = source_dict

                        break

            if depth >= max_depth:
                if current_matched_source:
                    sanitizer_meta = self.sanitizer_registry._path_goes_through_sanitizer(hop_chain)

                    if sanitizer_meta:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        path.sanitizer_file = sanitizer_meta["file"]
                        path.sanitizer_line = sanitizer_meta["line"]
                        path.sanitizer_method = sanitizer_meta["method"]
                        sanitized_paths.append(path)

                        if self.debug:
                            print(
                                f"[IFDS] ✓ Recorded SANITIZED path at max_depth={depth}, {len(hop_chain)} hops",
                                file=sys.stderr,
                            )
                    else:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        vulnerable_paths.append(path)

                        if self.debug:
                            print(
                                f"[IFDS] ✓ Recorded VULNERABLE path at max_depth={depth}, {len(hop_chain)} hops",
                                file=sys.stderr,
                            )

                continue

            predecessors = self._get_predecessors(current_ap)

            if not predecessors:
                if current_matched_source:
                    sanitizer_meta = self.sanitizer_registry._path_goes_through_sanitizer(hop_chain)

                    if sanitizer_meta:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        path.sanitizer_file = sanitizer_meta["file"]
                        path.sanitizer_line = sanitizer_meta["line"]
                        path.sanitizer_method = sanitizer_meta["method"]
                        sanitized_paths.append(path)

                        if self.debug:
                            print(
                                f"[IFDS] ✓ Recorded SANITIZED path at natural termination (no predecessors), {len(hop_chain)} hops",
                                file=sys.stderr,
                            )
                    else:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        vulnerable_paths.append(path)

                        if self.debug:
                            print(
                                f"[IFDS] ✓ Recorded VULNERABLE path at natural termination (no predecessors), {len(hop_chain)} hops",
                                file=sys.stderr,
                            )

                continue

            for pred_ap, edge_type, edge_meta in predecessors:
                hop = {
                    "type": edge_type,
                    "from": pred_ap.node_id,
                    "to": current_ap.node_id,
                    "from_file": pred_ap.file,
                    "to_file": current_ap.file,
                    "line": edge_meta.get("line", 0),
                    "depth": depth + 1,
                }
                new_chain = [hop] + hop_chain

                worklist.append((pred_ap, depth + 1, new_chain, current_matched_source))

        return (vulnerable_paths, sanitized_paths)

    def _get_predecessors(self, ap: AccessPath) -> list[tuple[AccessPath, str, dict]]:
        """Get all access paths that flow into this access path."""
        predecessors = []

        self.graph_cursor.execute(
            """
            SELECT target, type, metadata
            FROM edges
            WHERE source = ?
              AND graph_type = 'data_flow'
              AND type LIKE '%_reverse'
        """,
            (ap.node_id,),
        )

        for row in self.graph_cursor.fetchall():
            source_id = row["target"]
            edge_type = row["type"]
            metadata = {}

            if row["metadata"]:
                try:
                    import json

                    metadata = json.loads(row["metadata"])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            source_ap = AccessPath.parse(source_id)
            if source_ap:
                predecessors.append((source_ap, edge_type, metadata))

        self.graph_cursor.execute(
            """
            SELECT source, type, metadata
            FROM edges
            WHERE target = ? AND graph_type = 'call'
        """,
            (ap.node_id,),
        )

        for row in self.graph_cursor.fetchall():
            source_id = row["source"]
            edge_type = row["type"]
            metadata = {}

            if row["metadata"]:
                try:
                    import json

                    metadata = json.loads(row["metadata"])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            source_ap = AccessPath.parse(source_id)
            if source_ap:
                predecessors.append((source_ap, edge_type, metadata))

                if self.debug:
                    print(
                        f"[IFDS] Edge (Parse OK): {source_id} -> {ap.node_id} ({edge_type})",
                        file=sys.stderr,
                    )
            else:
                pass

        if not predecessors and self.debug:
            print(f"[IFDS] No predecessors for {ap.node_id} (termination point)", file=sys.stderr)

        return predecessors

    def _could_alias(self, ap1: AccessPath, ap2: AccessPath) -> bool:
        """Conservative alias check (no expensive alias analysis)."""

        if ap1.base == ap2.base:
            return True

        return bool(ap1.matches(ap2))

    def _access_paths_match(self, ap1: AccessPath, ap2: AccessPath) -> bool:
        """Check if two access paths represent the same data."""

        http_objects = {"req", "res", "request", "response"}

        if (
            ap1.base in http_objects
            and ap2.base in http_objects
            and self._is_controller_file(ap1.file)
            and self._is_controller_file(ap2.file)
        ):
            if ap1.file != ap2.file:
                return False

            if (
                ap1.function != ap2.function
                and "Controller." in ap1.function
                and "Controller." in ap2.function
            ):
                return False

        if self.type_resolver and ap1.base == ap2.base:
            ap1_node_id = f"{ap1.file}::{ap1.function}::{ap1.base}"
            ap2_node_id = f"{ap2.file}::{ap2.function}::{ap2.base}"
            if self.type_resolver.is_same_type(ap1_node_id, ap2_node_id):
                return True

        if ap1.base == ap2.base and ap1.fields == ap2.fields:
            return True

        return bool(ap1.matches(ap2))

    def _dict_to_access_path(self, node_dict: dict) -> AccessPath | None:
        """Convert source/sink dict to AccessPath."""
        file = node_dict.get("file", "")
        pattern = node_dict.get("pattern", node_dict.get("name", ""))

        if not file or not pattern:
            return None

        function = self._get_containing_function(file, node_dict.get("line", 0))

        parts = pattern.split(".")
        base = parts[0]
        fields = tuple(parts[1:]) if len(parts) > 1 else ()

        return AccessPath(file=file, function=function, base=base, fields=fields)

    def _get_containing_function(self, file: str, line: int) -> str:
        """Get function containing a line."""
        self.repo_cursor.execute(
            """
            SELECT name FROM symbols
            WHERE path = ? AND type = 'function' AND line <= ?
            ORDER BY line DESC
            LIMIT 1
        """,
            (file, line),
        )

        row = self.repo_cursor.fetchone()
        return row["name"] if row else "global"

    def _build_taint_path(self, source: dict, sink: dict, hop_chain: list[dict]):
        """Build TaintPath object from hop chain."""

        from .taint_path import TaintPath

        path_steps = []

        path_steps.append(
            {
                "type": "source",
                "file": source.get("file"),
                "line": source.get("line"),
                "name": source.get("name"),
                "pattern": source.get("pattern"),
            }
        )

        for hop in hop_chain:
            path_steps.append(hop)

        path_steps.append(
            {
                "type": "sink",
                "file": sink.get("file"),
                "line": sink.get("line"),
                "name": sink.get("name"),
                "pattern": sink.get("pattern"),
            }
        )

        path = TaintPath(source, sink, path_steps)
        path.flow_sensitive = True
        path.path_length = len(path_steps)

        return path

    def _get_language_for_file(self, file_path: str) -> str:
        """Detect language from file extension."""
        if not file_path:
            return "unknown"

        lower = file_path.lower()
        if lower.endswith(".py"):
            return "python"
        elif lower.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")):
            return "javascript"
        elif lower.endswith(".go"):
            return "go"
        elif lower.endswith(".rs"):
            return "rust"
        return "unknown"

    def _is_controller_file(self, file_path: str) -> bool:
        """Check if file is a controller/route handler."""

        if not self.type_resolver:
            raise ValueError(
                "TypeResolver is MANDATORY for IFDSTaintAnalyzer._is_controller_file(). "
                "NO FALLBACKS. Initialize IFDSTaintAnalyzer with type_resolver parameter."
            )

        return self.type_resolver.is_controller_file(file_path)

    def _is_true_entry_point(self, node_id: str) -> bool:
        """Check if a node represents a true entry point (HTTP request data)."""
        if not node_id:
            return False

        parts = node_id.split("::")
        if len(parts) < 3:
            return False

        file_path = parts[0]
        function_name = parts[1]
        variable = parts[2]

        if not self.registry:
            raise ValueError(
                "TaintRegistry is MANDATORY for IFDSTaintAnalyzer._is_true_entry_point(). "
                "NO FALLBACKS. Initialize IFDSTaintAnalyzer with registry parameter."
            )

        lang = self._get_language_for_file(file_path)
        request_patterns = self.registry.get_source_patterns(lang)

        if any(pattern in variable for pattern in request_patterns):
            if self._is_controller_file(file_path):
                self.repo_cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM express_middleware_chains
                    WHERE (handler_function = ? OR handler_expr LIKE ?)
                """,
                    (function_name, f"%{function_name}%"),
                )

                count = self.repo_cursor.fetchone()[0]
                if count > 0:
                    if self.debug:
                        print(
                            f"[IFDS] TRUE ENTRY POINT (middleware chain): {node_id}",
                            file=sys.stderr,
                        )
                    return True

        if "process.env" in variable or "env." in variable:
            if self.debug:
                print(f"[IFDS] TRUE ENTRY POINT (env var): {node_id}", file=sys.stderr)
            return True

        if "process.argv" in variable or "argv" in variable:
            if self.debug:
                print(f"[IFDS] TRUE ENTRY POINT (CLI arg): {node_id}", file=sys.stderr)
            return True

        return False

    def close(self):
        """Close database connections."""
        self.repo_conn.close()
        self.graph_conn.close()
