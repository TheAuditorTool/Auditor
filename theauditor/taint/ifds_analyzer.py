"""IFDS-based taint analyzer using pre-computed graphs."""

import sqlite3
import time
from collections import deque
from typing import TYPE_CHECKING

from theauditor.utils.logging import logger

from .access_path import AccessPath

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

        import os

        self.max_depth = int(os.environ.get("AUD_IFDS_DEPTH", 100))
        self.max_paths_per_sink = int(os.environ.get("AUD_IFDS_MAX_PATHS", 1000))
        self.time_budget_seconds = int(os.environ.get("AUD_IFDS_BUDGET", 120))

        self.debug = bool(os.environ.get("THEAUDITOR_DEBUG"))

        if self.debug:
            logger.debug("========================================")
            logger.debug("IFDS Analyzer Initialized (DEBUG MODE)")
            logger.debug(f"Database: {repo_db_path}")
            logger.debug("========================================")

        self._safe_sinks: set[str] = set()
        self._validation_sanitizers: list[dict] = []
        self._call_args_cache: dict[tuple, list[str]] = {}
        self._load_sanitizer_data()

    def analyze_sink_to_sources(
        self, sink: dict, sources: list[dict], max_depth: int = 15
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
            logger.debug(f"\n Analyzing sink: {sink.get('pattern', '?')}")
            logger.debug(f"Checking against {len(source_aps)} sources")

        vulnerable, sanitized = self._trace_backward_to_any_source(sink, source_aps, max_depth)

        if self.debug:
            logger.debug(
                f"Found {len(vulnerable)} vulnerable paths, {len(sanitized)} sanitized paths"
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

        start_time = time.time()

        while worklist and (len(vulnerable_paths) + len(sanitized_paths)) < self.max_paths_per_sink:
            if time.time() - start_time > self.time_budget_seconds:
                if self.debug:
                    logger.debug(f"Time budget ({self.time_budget_seconds}s) exceeded for sink")
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
                    sanitizer_meta = self._path_goes_through_sanitizer(hop_chain)

                    if sanitizer_meta:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        path.sanitizer_file = sanitizer_meta["file"]
                        path.sanitizer_line = sanitizer_meta["line"]
                        path.sanitizer_method = sanitizer_meta["method"]
                        sanitized_paths.append(path)

                        if self.debug:
                            logger.debug(
                                f"✓ Recorded SANITIZED path at max_depth={depth}, {len(hop_chain)} hops"
                            )
                    else:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        vulnerable_paths.append(path)

                        if self.debug:
                            logger.debug(
                                f"✓ Recorded VULNERABLE path at max_depth={depth}, {len(hop_chain)} hops"
                            )

                continue

            predecessors = self._get_predecessors(current_ap)

            if not predecessors:
                if current_matched_source:
                    sanitizer_meta = self._path_goes_through_sanitizer(hop_chain)

                    if sanitizer_meta:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        path.sanitizer_file = sanitizer_meta["file"]
                        path.sanitizer_line = sanitizer_meta["line"]
                        path.sanitizer_method = sanitizer_meta["method"]
                        sanitized_paths.append(path)

                        if self.debug:
                            logger.debug(
                                f"✓ Recorded SANITIZED path at natural termination (no predecessors), {len(hop_chain)} hops"
                            )
                    else:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        vulnerable_paths.append(path)

                        if self.debug:
                            logger.debug(
                                f"✓ Recorded VULNERABLE path at natural termination (no predecessors), {len(hop_chain)} hops"
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
        """Get all access paths that flow into this access path.

        Queries BOTH edge directions to ensure complete backward traversal:
        1. Reverse edges: WHERE source = current (edges explicitly marked as reverse)
        2. Forward edges: WHERE target = current (forward edges traversed backwards)

        This is NOT a fallback - it's complete graph coverage. If graph builder
        created A -> B but not B -> A_reverse, we still find the predecessor.
        """
        predecessors = []

        self.graph_cursor.execute(
            """
            SELECT target, type, metadata, line
            FROM edges
            WHERE source = ?
              AND graph_type = 'data_flow'
              AND type LIKE '%_reverse'
              AND target NOT LIKE '%node_modules%'
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

            metadata["line"] = row["line"] if row["line"] is not None else 0

            source_ap = AccessPath.parse(source_id)
            if source_ap:
                predecessors.append((source_ap, edge_type, metadata))
            elif self.debug:
                logger.debug(f"WARNING: Dropped malformed node ID: '{source_id}' (parse failed)")

        self.graph_cursor.execute(
            """
            SELECT source, type, metadata, line
            FROM edges
            WHERE target = ?
              AND graph_type = 'data_flow'
              AND type NOT LIKE '%_reverse'
              AND source NOT LIKE '%node_modules%'
        """,
            (ap.node_id,),
        )

        for row in self.graph_cursor.fetchall():
            pred_id = row["source"]
            edge_type = row["type"] + "_traversed_reverse"
            metadata = {}

            if row["metadata"]:
                try:
                    import json

                    metadata = json.loads(row["metadata"])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            metadata["line"] = row["line"] if row["line"] is not None else 0

            pred_ap = AccessPath.parse(pred_id)
            if pred_ap:
                if not any(p[0].node_id == pred_ap.node_id for p in predecessors):
                    predecessors.append((pred_ap, edge_type, metadata))
            elif self.debug:
                logger.debug(f"WARNING: Dropped malformed node ID: '{pred_id}' (parse failed)")

        self.graph_cursor.execute(
            """
            SELECT source, type, metadata, line
            FROM edges
            WHERE target = ?
              AND graph_type = 'call'
              AND source NOT LIKE '%node_modules%'
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

            metadata["line"] = row["line"] if row["line"] is not None else 0

            source_ap = AccessPath.parse(source_id)
            if source_ap:
                predecessors.append((source_ap, edge_type, metadata))

                if self.debug:
                    logger.debug(f"Edge (Parse OK): {source_id} -> {ap.node_id} ({edge_type})")
            elif self.debug:
                logger.debug(f"WARNING: Dropped malformed node ID: '{source_id}' (parse failed)")

        if not predecessors and self.debug:
            logger.debug(f"No predecessors for {ap.node_id} (termination point)")

        return predecessors

    def _could_alias(self, ap1: AccessPath, ap2: AccessPath) -> bool:
        """Conservative alias check (no expensive alias analysis)."""

        if ap1.base == ap2.base:
            return True

        return bool(ap1.matches(ap2))

    def _access_paths_match(self, ap1: AccessPath, ap2: AccessPath) -> bool:
        """Check if two access paths represent the same data.

        Matching strategy (in order):
        1. HTTP objects guard - prevent cross-controller false positives
        2. Exact match - same base AND same fields (fast path)
        3. Type-aware match - different bases but same ORM model type
        4. Prefix match - same base with field prefix overlap

        The type-aware match is CRITICAL for catching aliased variables:
        - input = req; sink(input.body) should match source(req.body)
        - This works when both variables have ORM model metadata attached
        """

        http_objects = {"req", "res", "request", "response"}

        # 1. HTTP OBJECTS GUARD: Prevent cross-controller false positives
        # req.body in UserController should NOT match req.body in AdminController
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

        # 2. EXACT MATCH (fast path): Same base AND same fields
        if ap1.base == ap2.base and ap1.fields == ap2.fields:
            return True

        # 3. TYPE-AWARE MATCH: Different bases but same underlying type
        # This catches: req.body vs input.body when input = req (aliased)
        # Key insight: check when FIELDS match, even if BASES differ
        if self.type_resolver and ap1.fields == ap2.fields:
            ap1_node_id = f"{ap1.file}::{ap1.function}::{ap1.base}"
            ap2_node_id = f"{ap2.file}::{ap2.function}::{ap2.base}"
            if self.type_resolver.is_same_type(ap1_node_id, ap2_node_id):
                return True

        # 4. PREFIX MATCH: Same base with field prefix overlap
        # Handles partial aliasing like x.y matching x
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
                        logger.debug(f"TRUE ENTRY POINT (middleware chain): {node_id}")
                    return True

        if "process.env" in variable or "env." in variable:
            if self.debug:
                logger.debug(f"TRUE ENTRY POINT (env var): {node_id}")
            return True

        if "process.argv" in variable or "argv" in variable:
            if self.debug:
                logger.debug(f"TRUE ENTRY POINT (CLI arg): {node_id}")
            return True

        return False

    def _load_sanitizer_data(self):
        """Load sanitizer data from database for path checking."""

        self.repo_cursor.execute("""
            SELECT DISTINCT sink_pattern
            FROM framework_safe_sinks
            WHERE is_safe = 1
        """)
        for row in self.repo_cursor.fetchall():
            pattern = row["sink_pattern"]
            if pattern:
                self._safe_sinks.add(pattern)

        self.repo_cursor.execute("""
            SELECT DISTINCT
                file_path as file, line, framework, is_validator, variable_name as schema_name
            FROM validation_framework_usage
            WHERE framework IN ('zod', 'joi', 'yup', 'express-validator')
        """)
        for row in self.repo_cursor.fetchall():
            self._validation_sanitizers.append(
                {
                    "file": row["file"],
                    "line": row["line"],
                    "framework": row["framework"],
                    "schema": row["schema_name"],
                }
            )

        self.repo_cursor.execute("""
            SELECT file, line, callee_function
            FROM function_call_args
            WHERE callee_function IS NOT NULL
        """)
        for row in self.repo_cursor.fetchall():
            key = (row["file"], row["line"])
            if key not in self._call_args_cache:
                self._call_args_cache[key] = []
            self._call_args_cache[key].append(row["callee_function"])

        self.repo_cursor.execute("""
            SELECT path as file, line, name as callee_function
            FROM symbols
            WHERE type = 'call' AND name IS NOT NULL
        """)
        for row in self.repo_cursor.fetchall():
            key = (row["file"], row["line"])
            callee = row["callee_function"]
            if key not in self._call_args_cache:
                self._call_args_cache[key] = []
            if callee not in self._call_args_cache[key]:
                self._call_args_cache[key].append(callee)

        if self.debug:
            logger.debug(
                f"Loaded {len(self._safe_sinks)} safe sinks, "
                f"{len(self._validation_sanitizers)} validators, "
                f"{len(self._call_args_cache)} call locations"
            )

    def _is_sanitizer(self, function_name: str, file_path: str = None) -> bool:
        """Check if function is a sanitizer. Uses registry if available.

        FIX #19: Pass language to registry.is_sanitizer() so it checks
        language-specific sanitizers (e.g., 'javascript'), not just 'global'.
        Without this, validators loaded from validation_framework_usage
        (registered under 'javascript') are NEVER matched.
        """
        lang = self._get_language_for_file(file_path) if file_path else None
        if self.registry and self.registry.is_sanitizer(function_name, lang):
            return True
        if function_name in self._safe_sinks:
            return True
        for safe_sink in self._safe_sinks:
            if safe_sink in function_name or function_name in safe_sink:
                return True
        return False

    def _path_goes_through_sanitizer(self, hop_chain: list[dict]) -> dict | None:
        """Check if a taint path goes through any sanitizer."""
        if not self.registry:
            raise ValueError("Registry is MANDATORY. NO FALLBACKS.")

        for _i, hop in enumerate(hop_chain):
            if isinstance(hop, dict):
                hop_file = hop.get("from_file") or hop.get("to_file")
                hop_line = hop.get("line", 0)
                node_str = (
                    hop.get("from")
                    or hop.get("to")
                    or hop.get("from_node")
                    or hop.get("to_node")
                    or ""
                )
            else:
                node_str = hop
                parts = node_str.split("::")
                hop_file = parts[0] if parts else None
                hop_line = 0
                if len(parts) > 1:
                    func = parts[1]
                    lang = self._get_language_for_file(hop_file)
                    validation_patterns = self.registry.get_sanitizer_patterns(lang)
                    for pattern in validation_patterns:
                        if pattern in func:
                            return {"file": hop_file, "line": 0, "method": func}

            if not hop_file:
                continue

            if hop_line > 0:
                callees = self._call_args_cache.get((hop_file, hop_line), [])
                for callee in callees:
                    if self._is_sanitizer(callee, hop_file):
                        return {"file": hop_file, "line": hop_line, "method": callee}

            if node_str and "::" in node_str:
                self.graph_cursor.execute(
                    """
                    SELECT target, metadata
                    FROM edges
                    WHERE source = ? AND graph_type = 'call'
                    LIMIT 10
                """,
                    (node_str,),
                )
                for row in self.graph_cursor.fetchall():
                    target = row["target"]

                    target_parts = target.split("::")
                    if len(target_parts) >= 2:
                        called_func = target_parts[-1]

                        if self._is_sanitizer(called_func, hop_file):
                            return {"file": hop_file, "line": hop_line, "method": called_func}

            if hop_line > 0:
                for san in self._validation_sanitizers:
                    if (san["file"].endswith(hop_file) or hop_file.endswith(san["file"])) and abs(
                        san["line"] - hop_line
                    ) <= 10:
                        return {
                            "file": hop_file,
                            "line": hop_line,
                            "method": f"{san['framework']}:{san.get('schema', 'validation')}",
                        }

        return None

    def close(self):
        """Close database connections."""
        self.repo_conn.close()
        self.graph_conn.close()
