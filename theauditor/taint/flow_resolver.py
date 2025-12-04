"""Complete flow resolution engine for codebase truth generation."""

import json
import os
import sqlite3
import time
from collections import defaultdict
from functools import lru_cache

from theauditor.utils.logging import logger

# UNCAGED PROTOCOL: Replaced arbitrary effort limits with time budgets.
# Old limits (25k nodes, 20 depth) were training wheels for dirty data.
# With sanitized graph (Phase 3), we can traverse deep chains efficiently.
INFRASTRUCTURE_MAX_VISITS = 5    # Was 2 - allow more revisits for infra
USERCODE_MAX_VISITS = 50         # Was 10 - handle recursion/loops better


class FlowResolver:
    """Resolves ALL control flows in codebase to populate resolved_flow_audit table."""

    SUCCESSORS_CACHE_SIZE = 10_000
    EDGE_TYPE_CACHE_SIZE = 20_000

    def __init__(self, repo_db: str, graph_db: str, registry=None):
        """Initialize the flow resolver with database connections."""
        self.repo_db = repo_db
        self.graph_db = graph_db
        self.registry = registry
        self.repo_conn = sqlite3.connect(repo_db)
        self.repo_conn.row_factory = sqlite3.Row
        self.repo_cursor = self.repo_conn.cursor()
        self.graph_conn = sqlite3.connect(graph_db)
        self.flows_resolved = 0
        # UNCAGED: Increased limits now that graph data is clean
        self.max_depth = 100              # Was 20 - capture full framework lifecycles
        self.max_flows = 10_000_000       # Was 100,000 - no arbitrary cap
        self.max_flows_per_entry = 50_000 # Was 1,000 - allow deep exploration
        self.time_budget_seconds = 45     # NEW: Wall clock limit replaces effort counting
        self.debug = bool(os.environ.get("THEAUDITOR_DEBUG"))

        # Sanitizer data for path checking
        self._safe_sinks: set[str] = set()
        self._validation_sanitizers: list[dict] = []
        self._call_args_cache: dict[tuple, list[str]] = {}
        self._load_sanitizer_data()

        self.best_paths_cache: dict[tuple, int] = {}

        logger.info("FlowResolver initialized with lazy graph loading (Phase 0.3)")

    def _preload_graph(self):
        """DEPRECATED: Phase 0.3 removed eager loading.

        This method is kept as a no-op for backward compatibility.
        Graph data is now loaded on-demand via _get_successors() and _get_edge_type().
        """
        logger.debug("_preload_graph() is deprecated - using lazy loading instead")

    def resolve_all_flows(self) -> int:
        """Complete forward flow resolution to generate atomic truth."""
        logger.info("Starting complete flow resolution...")

        self.repo_conn.execute("DELETE FROM resolved_flow_audit")
        self.repo_conn.commit()

        entry_nodes = self._get_entry_nodes()
        exit_nodes = self._get_exit_nodes()

        logger.info(f"Found {len(entry_nodes)} entry points and {len(exit_nodes)} exit points")

        # UNCAGED: Time-based exit instead of arbitrary flow count
        start_time = time.time()

        for _i, entry_id in enumerate(entry_nodes):
            # Time budget check - stop if we've been running too long
            elapsed = time.time() - start_time
            if elapsed > self.time_budget_seconds:
                logger.warning(f"Time budget ({self.time_budget_seconds}s) exceeded after {elapsed:.1f}s")
                break

            self._trace_from_entry(entry_id, exit_nodes)

        self.repo_conn.commit()

        elapsed = time.time() - start_time
        logger.info(f"Flow resolution complete: {self.flows_resolved} flows resolved in {elapsed:.1f}s")
        return self.flows_resolved

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

    def _get_request_fields(self, file_path: str) -> list[str]:
        """Get request field patterns for a file's language."""

        if not self.registry:
            raise ValueError(
                "TaintRegistry is MANDATORY for FlowResolver._get_request_fields(). "
                "NO FALLBACKS. Initialize FlowResolver with registry parameter."
            )

        lang = self._get_language_for_file(file_path)
        patterns = self.registry.get_source_patterns(lang)

        request_patterns = [
            p
            for p in patterns
            if any(
                kw in p.lower()
                for kw in ["req", "request", "body", "params", "query", "form", "args", "json"]
            )
        ]

        return request_patterns

    def _get_entry_nodes(self) -> list[str]:
        """
        Get entry points using a Hybrid Strategy:
        1. Authoritative: Database tables (api_endpoints, middleware, env_vars).
        2. Heuristic: Graph nodes that LOOK like entry points (Smart Search).

        This walks ALL roads, but filters out noise (node_modules, tests, mocks).
        """
        graph_cursor = self.graph_conn.cursor()
        repo_cursor = self.repo_conn.cursor()
        entry_nodes = set()

        # --- 1. AUTHORITATIVE SOURCES (The "Highway Map") ---

        # Common web framework argument names to try for each handler
        web_args = ["req", "request", "args", "kwargs", "event", "context"]

        # API Endpoints (Python Flask/Django/FastAPI + normalized routes)
        repo_cursor.execute("""
            SELECT file, handler_function
            FROM api_endpoints
            WHERE handler_function IS NOT NULL
        """)
        for row in repo_cursor.fetchall():
            file, handler = row[0], row[1]
            file = file.replace("\\", "/") if file else file  # Normalize path
            base_id = f"{file}::{handler}"
            for arg in web_args:
                entry_nodes.add(f"{base_id}::{arg}")

        # Express Middleware Chains (First handlers only)
        repo_cursor.execute("""
            SELECT file, handler_function, handler_expr
            FROM express_middleware_chains
            WHERE execution_order = 0
        """)
        for row in repo_cursor.fetchall():
            file = row[0]
            file = file.replace("\\", "/") if file else file  # Normalize path
            func = row[1] or row[2]
            if func:
                base_id = f"{file}::{func}"
                for arg in ["req", "req.body", "req.query", "req.params"]:
                    entry_nodes.add(f"{base_id}::{arg}")

        # Environment Variables (Configuration Injection Sources)
        repo_cursor.execute("""
            SELECT DISTINCT file, var_name, in_function
            FROM env_var_usage
        """)
        for row in repo_cursor.fetchall():
            file, var_name = row[0], row[1]
            file = file.replace("\\", "/") if file else file  # Normalize path
            func = row[2] if row[2] else "global"
            entry_nodes.add(f"{file}::{func}::{var_name}")

        # Cross-Boundary Edges (Frontend -> Backend)
        graph_cursor.execute("""
            SELECT DISTINCT target
            FROM edges
            WHERE graph_type = 'data_flow'
              AND type = 'cross_boundary'
        """)
        for (target,) in graph_cursor.fetchall():
            entry_nodes.add(target)

        authoritative_count = len(entry_nodes)

        # --- 2. SMART HEURISTICS (The "Dirt Roads") ---
        # Catches what extractors missed, but filters out noise.

        # Patterns that indicate entry points (request objects, event handlers)
        heuristic_patterns = ["req", "request", "event", "context", "body", "payload"]

        # Exclusions - the circuit breaker against noise
        exclusions = [
            "node_modules", ".test.", ".spec.", "__tests__", "test/",
            "mock", "fixtures", ".d.ts", "__mocks__"
        ]

        # Query graph for nodes matching entry patterns
        # Node ID format: file::function::variable
        like_clauses = " OR ".join([f"id LIKE '%::{p}'" for p in heuristic_patterns])

        graph_cursor.execute(f"""
            SELECT id FROM nodes
            WHERE graph_type = 'data_flow'
              AND ({like_clauses})
        """)

        for (node_id,) in graph_cursor.fetchall():
            # Filter 1: Noise Exclusion (Tests/Libs)
            node_lower = node_id.lower()
            if any(exc in node_lower for exc in exclusions):
                continue

            # Filter 2: Must be actual parameter, not just variable containing the word
            # Node format: file::func::var - we want var to BE the pattern, not contain it
            parts = node_id.split("::")
            if len(parts) >= 3:
                var_name = parts[-1]
                # Only accept if variable name IS the pattern (not "my_request_helper")
                if var_name in heuristic_patterns or var_name.split(".")[0] in heuristic_patterns:
                    entry_nodes.add(node_id)

        heuristic_count = len(entry_nodes) - authoritative_count

        # --- 3. FINAL VALIDATION ---

        # Validate all nodes exist in graph (filter ghosts)
        validated = []
        for node in entry_nodes:
            graph_cursor.execute(
                """
                SELECT 1 FROM nodes
                WHERE id = ? AND graph_type = 'data_flow'
                LIMIT 1
            """,
                (node,),
            )
            if graph_cursor.fetchone():
                validated.append(node)

        # Final test/fixture filter on validated set
        filtered_entries = [
            n for n in validated
            if not any(
                x in n.lower()
                for x in [".test.", ".spec.", "__tests__", "/test/", "/mock/", "/fixtures/"]
            )
        ]

        if self.debug:
            logger.info(f"Hybrid Entry Analysis: {len(filtered_entries)} roots "
                f"(Authoritative: {authoritative_count}, Heuristic: {heuristic_count})")

        return filtered_entries

    def _get_exit_nodes(self) -> set[str]:
        """Get all exit points from the unified graph."""
        exit_nodes = set()
        repo_cursor = self.repo_conn.cursor()
        graph_cursor = self.graph_conn.cursor()

        repo_cursor.execute("""
            SELECT DISTINCT file, line, caller_function, argument_expr
            FROM function_call_args
            WHERE (
                callee_function LIKE '%.create%'
                OR callee_function LIKE '%.update%'
                OR callee_function LIKE '%.delete%'
                OR callee_function LIKE '%.findOne%'
                OR callee_function LIKE '%.findMany%'
                OR callee_function LIKE '%.save%'
                OR callee_function LIKE '%.destroy%'
                OR callee_function LIKE '%.upsert%'
                OR callee_function LIKE 'prisma.%'
                OR callee_function LIKE 'sequelize.query%'
            )
            AND argument_expr IS NOT NULL
            AND file NOT LIKE '%test%'
            AND file NOT LIKE '%node_modules%'
        """)

        for file, _line, func, arg_expr in repo_cursor.fetchall():
            file = file.replace("\\", "/") if file else file  # Normalize path
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                graph_cursor.execute(
                    """
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """,
                    (node_id,),
                )

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        repo_cursor.execute("""
            SELECT DISTINCT file, line, caller_function, argument_expr
            FROM function_call_args
            WHERE (
                callee_function LIKE '%.query'
                OR callee_function LIKE '%.execute'
                OR callee_function LIKE '%.exec'
                OR callee_function LIKE '%.run'
            )
            AND argument_expr IS NOT NULL
            AND file NOT LIKE '%test%'
            AND file NOT LIKE '%migration%'
            AND file NOT LIKE '%node_modules%'
        """)

        for file, _line, func, arg_expr in repo_cursor.fetchall():
            file = file.replace("\\", "/") if file else file  # Normalize path
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                graph_cursor.execute(
                    """
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """,
                    (node_id,),
                )

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        repo_cursor.execute("""
            SELECT DISTINCT file, line, caller_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN (
                'res.send', 'res.json', 'res.render', 'res.write',
                'res.status', 'res.end'
            )
            AND argument_expr IS NOT NULL
            AND file NOT LIKE '%test%'
            AND file NOT LIKE '%node_modules%'
        """)

        for file, _line, func, arg_expr in repo_cursor.fetchall():
            file = file.replace("\\", "/") if file else file  # Normalize path
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                for req_field in ["req", "req.body", "req.params", "req.query"]:
                    if req_field in arg_expr:
                        alt_node_id = f"{file}::{func}::{req_field}"
                        graph_cursor.execute(
                            """
                            SELECT 1 FROM nodes
                            WHERE graph_type = 'data_flow'
                              AND id = ?
                            LIMIT 1
                        """,
                            (alt_node_id,),
                        )
                        if graph_cursor.fetchone():
                            exit_nodes.add(alt_node_id)

                graph_cursor.execute(
                    """
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """,
                    (node_id,),
                )

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        repo_cursor.execute("""
            SELECT DISTINCT file, line, caller_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN (
                'axios.post', 'axios.get', 'fetch', 'request',
                'fs.writeFile', 'fs.writeFileSync', 'fs.appendFile',
                'console.log', 'console.error', 'logger.info'
            )
            AND argument_expr IS NOT NULL
            AND file NOT LIKE '%test%'
            AND file NOT LIKE '%node_modules%'
        """)

        for file, _line, func, arg_expr in repo_cursor.fetchall():
            file = file.replace("\\", "/") if file else file  # Normalize path
            if not func:
                func = "global"

            var_name = self._parse_argument_variable(arg_expr)
            if var_name:
                node_id = f"{file}::{func}::{var_name}"

                graph_cursor.execute(
                    """
                    SELECT 1 FROM nodes
                    WHERE graph_type = 'data_flow'
                      AND id = ?
                    LIMIT 1
                """,
                    (node_id,),
                )

                if graph_cursor.fetchone():
                    exit_nodes.add(node_id)

        return exit_nodes

    def _trace_from_entry(self, entry_id: str, exit_nodes: set[str]) -> None:
        """Trace all flows from a single entry point using DFS.

        UNCAGED: Removed effort_counter limit. Time budget at resolve_all_flows level
        handles runaway analysis. Visit counts still prevent infinite loops.
        """
        parts = entry_id.split("::")
        file_path = parts[0].lower()
        var_name = parts[-1] if len(parts) > 0 else ""

        # Adaptive visit limits: infrastructure nodes need fewer revisits
        is_infrastructure = (
            "config" in file_path
            or "env" in file_path
            or (var_name.isupper() and len(var_name) > 1)
            or "process.env" in var_name
        )
        current_max_visits = INFRASTRUCTURE_MAX_VISITS if is_infrastructure else USERCODE_MAX_VISITS

        worklist = [(entry_id, [entry_id])]
        visited_edges: set[tuple[str, str]] = set()
        node_visit_counts: dict[str, int] = defaultdict(int)

        flows_from_this_entry = 0
        # UNCAGED: Removed effort_counter - time budget handles this at higher level

        while (
            worklist
            and self.flows_resolved < self.max_flows
            and flows_from_this_entry < self.max_flows_per_entry
        ):
            current_id, path = worklist.pop()

            if len(path) > self.max_depth:
                self._record_flow(entry_id, current_id, path, "VULNERABLE", None)
                continue

            if current_id in exit_nodes:
                status, sanitizer_meta = self._classify_flow(path)
                self._record_flow(entry_id, current_id, path, status, sanitizer_meta)
                flows_from_this_entry += 1

            successors = self._get_successors(current_id)

            for successor_id in successors:
                edge = (current_id, successor_id)
                if edge in visited_edges:
                    continue

                if node_visit_counts[successor_id] >= current_max_visits:
                    continue

                node_visit_counts[successor_id] += 1
                visited_edges.add(edge)

                new_path = path + [successor_id]
                worklist.append((successor_id, new_path))

    def _get_successors(self, node_id: str) -> list[str]:
        """Get successor nodes via lazy DB query with LRU cache.

        Phase 0.3: Replaced in-memory adjacency_list with on-demand query.
        """
        return list(self._get_successors_cached(node_id))

    @lru_cache(maxsize=10_000)
    def _get_successors_cached(self, node_id: str) -> tuple[str, ...]:
        """Internal cached query for successors.

        Returns tuple for lru_cache hashability.

        FIX #9: Excludes node_modules targets to prevent traversal into
        third-party libraries. This treats libraries as "black boxes" -
        we know data enters axios.post(), we don't trace axios internals.
        """
        cursor = self.graph_conn.cursor()
        cursor.execute(
            """
            SELECT target FROM edges
            WHERE source = ?
              AND graph_type = 'data_flow'
              AND target NOT LIKE '%node_modules%'
        """,
            (node_id,),
        )

        return tuple(row[0] for row in cursor.fetchall())

    def _classify_flow(self, path: list[str]) -> tuple[str, dict | None]:
        """Classify a flow path based on sanitization."""

        sanitizer_meta = self._path_goes_through_sanitizer(path)

        if sanitizer_meta:
            return ("SANITIZED", sanitizer_meta)
        else:
            return ("VULNERABLE", None)

    def _record_flow(
        self, source: str, sink: str, path: list[str], status: str, sanitizer_meta: dict | None
    ) -> None:
        """Write resolved flow to resolved_flow_audit table with SEMANTIC DEDUPLICATION."""

        if source == sink or len(path) < 2:
            return

        source_parts = source.split("::")
        source_file = source_parts[0] if len(source_parts) > 0 else ""
        source_pattern = source_parts[2] if len(source_parts) > 2 else source

        sink_parts = sink.split("::")
        sink_file = sink_parts[0] if len(sink_parts) > 0 else ""
        sink_pattern = sink_parts[2] if len(sink_parts) > 2 else sink

        sanitizer_method = sanitizer_meta["method"] if sanitizer_meta else None

        current_length = len(path)

        cache_key = (source_file, source_pattern, sink_file, sink_pattern, status, sanitizer_method)

        cached_length = self.best_paths_cache.get(cache_key)
        if cached_length is not None and cached_length <= current_length:
            return

        self.best_paths_cache[cache_key] = current_length

        cursor = self.repo_conn.cursor()

        query_sig = """
            SELECT id, path_length FROM resolved_flow_audit
            WHERE source_file = ? AND source_pattern = ?
              AND sink_file = ? AND sink_pattern = ?
              AND status = ?
              -- SQL trick: checks if sanitizer matches OR both are NULL
              AND (sanitizer_method = ? OR (sanitizer_method IS NULL AND ? IS NULL))
              AND engine = 'FlowResolver'
            LIMIT 1
        """

        cursor.execute(
            query_sig,
            (
                source_file,
                source_pattern,
                sink_file,
                sink_pattern,
                status,
                sanitizer_method,
                sanitizer_method,
            ),
        )

        existing = cursor.fetchone()

        if existing:
            existing_id, existing_length = existing

            if existing_length <= current_length:
                return

            cursor.execute("DELETE FROM resolved_flow_audit WHERE id = ?", (existing_id,))

        repo_cursor = self.repo_conn.cursor()

        source_line = 0

        # Try assignment_source_vars first (most specific)
        repo_cursor.execute(
            """
            SELECT MIN(line) FROM assignment_source_vars
            WHERE file = ? AND source_var = ?
        """,
            (source_file, source_pattern),
        )
        result = repo_cursor.fetchone()
        if result and result[0]:
            source_line = result[0]

        # Fallback to func_params (for req, res, ctx parameters)
        if source_line == 0:
            repo_cursor.execute(
                """
                SELECT MIN(function_line) FROM func_params
                WHERE file = ? AND param_name = ?
            """,
                (source_file, source_pattern.split(".")[0]),
            )
            result = repo_cursor.fetchone()
            if result and result[0]:
                source_line = result[0]

        # Fallback to variable_usage (general usage)
        if source_line == 0:
            repo_cursor.execute(
                """
                SELECT MIN(line) FROM variable_usage
                WHERE file = ? AND variable_name = ?
            """,
                (source_file, source_pattern),
            )
            result = repo_cursor.fetchone()
            if result and result[0]:
                source_line = result[0]

        sink_line = 0
        sink_function = sink_parts[1] if len(sink_parts) > 1 else "global"

        repo_cursor.execute(
            """
            SELECT MIN(line) FROM (
                SELECT line FROM function_call_args
                WHERE file = ? AND (argument_expr LIKE ? OR callee_function LIKE ?)
                  AND (caller_function = ? OR (caller_function IS NULL AND ? = 'global'))
                UNION ALL
                SELECT line FROM function_call_args_jsx
                WHERE file = ? AND (argument_expr LIKE ? OR callee_function LIKE ?)
                  AND (caller_function = ? OR (caller_function IS NULL AND ? = 'global'))
            )
        """,
            (
                sink_file,
                f"%{sink_pattern}%",
                f"%{sink_pattern}%",
                sink_function,
                sink_function,
                sink_file,
                f"%{sink_pattern}%",
                f"%{sink_pattern}%",
                sink_function,
                sink_function,
            ),
        )
        result = repo_cursor.fetchone()
        if result and result[0]:
            sink_line = result[0]

        hop_chain = []
        for i in range(len(path) - 1):
            hop = {
                "from": path[i],
                "to": path[i + 1],
                "hop_number": i,
                "type": self._get_edge_type(path[i], path[i + 1]),
            }
            hop_chain.append(hop)

        # Get vulnerability type from registry. NO FALLBACKS.
        if not self.registry:
            raise ValueError("Registry is MANDATORY. NO FALLBACKS.")
        vuln_type = self.registry.get_sink_info(sink_pattern)["vulnerability_type"]

        cursor.execute(
            """
            INSERT INTO resolved_flow_audit (
                source_file, source_line, source_pattern,
                sink_file, sink_line, sink_pattern,
                vulnerability_type, path_length, hops, path_json, flow_sensitive,
                status, sanitizer_file, sanitizer_line, sanitizer_method,
                engine
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                source_file,
                source_line,
                source_pattern,
                sink_file,
                sink_line,
                sink_pattern,
                vuln_type,
                len(hop_chain),
                len(hop_chain),
                json.dumps(hop_chain),
                1,
                status,
                sanitizer_meta["file"] if sanitizer_meta else None,
                sanitizer_meta["line"] if sanitizer_meta else None,
                sanitizer_method,
                "FlowResolver",
            ),
        )

        self.flows_resolved += 1

        if self.flows_resolved % 1000 == 0:
            self.repo_conn.commit()
            logger.debug(f"Recorded {self.flows_resolved} semantic flows...")

    def _get_edge_type(self, from_node: str, to_node: str) -> str:
        """Get edge type via lazy DB query with LRU cache.

        Phase 0.3: Replaced in-memory edge_types with on-demand query.
        """
        return self._get_edge_type_cached(from_node, to_node)

    @lru_cache(maxsize=20_000)
    def _get_edge_type_cached(self, from_node: str, to_node: str) -> str:
        """Internal cached query for edge type."""
        cursor = self.graph_conn.cursor()
        cursor.execute(
            """
            SELECT type FROM edges
            WHERE source = ? AND target = ? AND graph_type = 'data_flow'
            LIMIT 1
        """,
            (from_node, to_node),
        )

        row = cursor.fetchone()
        return row[0] if row and row[0] else "unknown"

    def _parse_argument_variable(self, arg_expr: str) -> str | None:
        """Extract variable name from argument expression."""
        if not arg_expr or not isinstance(arg_expr, str):
            return None

        arg_expr = arg_expr.strip()

        if not arg_expr:
            return None

        if arg_expr.startswith('"') or arg_expr.startswith("'"):
            return None

        if "(" in arg_expr:
            return None

        if any(op in arg_expr for op in ["+", "-", "*", "/", "%", "=", "<", ">", "!"]):
            return None

        if arg_expr.isdigit():
            return None

        if not (arg_expr[0].isalpha() or arg_expr[0] == "_"):
            return None

        return arg_expr

    def _load_sanitizer_data(self):
        """Load sanitizer data from database for path checking."""
        # Load safe sinks
        self.repo_cursor.execute("""
            SELECT DISTINCT sink_pattern
            FROM framework_safe_sinks
            WHERE is_safe = 1
        """)
        for row in self.repo_cursor.fetchall():
            pattern = row["sink_pattern"]
            if pattern:
                self._safe_sinks.add(pattern)

        # Load validation sanitizers
        self.repo_cursor.execute("""
            SELECT DISTINCT
                file_path as file, line, framework, is_validator, variable_name as schema_name
            FROM validation_framework_usage
            WHERE framework IN ('zod', 'joi', 'yup', 'express-validator')
        """)
        for row in self.repo_cursor.fetchall():
            self._validation_sanitizers.append({
                "file": row["file"],
                "line": row["line"],
                "framework": row["framework"],
                "schema": row["schema_name"],
            })

        # Pre-load function calls for O(1) lookup
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

        logger.info(
            f"Loaded {len(self._safe_sinks)} safe sinks, "
            f"{len(self._validation_sanitizers)} validators, "
            f"{len(self._call_args_cache)} call locations"
        )

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

    def _is_sanitizer(self, function_name: str, file_path: str = None) -> bool:
        """Check if function is a sanitizer. Uses registry if available."""
        lang = self._get_language_for_file(file_path) if file_path else None
        if self.registry and self.registry.is_sanitizer(function_name, lang):
            return True
        if function_name in self._safe_sinks:
            return True
        for safe_sink in self._safe_sinks:
            if safe_sink in function_name or function_name in safe_sink:
                return True
        return False

    def _path_goes_through_sanitizer(self, path: list) -> dict | None:
        """Check if a taint path goes through any sanitizer.

        Uses call edge checks instead of string matching to detect sanitizers.
        """
        if not self.registry:
            raise ValueError("Registry is MANDATORY. NO FALLBACKS.")

        graph_cursor = self.graph_conn.cursor()

        def check_node_for_sanitizer(node_str: str) -> dict | None:
            """Check a single node for sanitizer calls via graph edges and call cache."""
            parts = node_str.split("::")
            hop_file = parts[0] if parts else None
            func = parts[1] if len(parts) > 1 else ""

            if not hop_file:
                return None

            # PRIMARY CHECK: Query graph for call edges from this node
            graph_cursor.execute(
                """
                SELECT target, metadata
                FROM edges
                WHERE source = ? AND graph_type = 'call'
                LIMIT 10
            """,
                (node_str,),
            )
            for row in graph_cursor.fetchall():
                target = row[0]
                # Extract function name from target node ID
                target_parts = target.split("::")
                if len(target_parts) >= 2:
                    called_func = target_parts[-1]
                    if self._is_sanitizer(called_func, hop_file):
                        return {"file": hop_file, "line": 0, "method": called_func}

            # SECONDARY CHECK: Check if function itself is a sanitizer
            if func and self._is_sanitizer(func, hop_file):
                return {"file": hop_file, "line": 0, "method": func}

            # TERTIARY CHECK: Validation frameworks (Zod, Joi, Yup, express-validator)
            # Match by file containing validators + common validation patterns in func/var
            var_name = parts[2] if len(parts) > 2 else ""
            validation_keywords = ["schema", "validate", "parse", "safeParse", "validator", "check"]

            for san in self._validation_sanitizers:
                # Check file match (loose match for path differences)
                if san["file"] in hop_file or hop_file in san["file"]:
                    schema_name = san.get("schema", "")
                    # Match if: schema name in func/var OR validation keyword in func/var
                    func_lower = func.lower() if func else ""
                    var_lower = var_name.lower() if var_name else ""

                    if schema_name and (schema_name in func or schema_name in var_name):
                        return {
                            "file": hop_file,
                            "line": san["line"],
                            "method": f"{san['framework']}:{schema_name}",
                        }
                    # Fallback: validation keyword match in same file as validator
                    if any(kw in func_lower or kw in var_lower for kw in validation_keywords):
                        return {
                            "file": hop_file,
                            "line": san["line"],
                            "method": f"{san['framework']}:inferred",
                        }

            return None

        for node in path:
            if isinstance(node, str):
                # Legacy string format: "file::func::pattern"
                result = check_node_for_sanitizer(node)
                if result:
                    return result
            elif isinstance(node, dict):
                # Dict format: {"from": "file::func::pattern", "to": "file::func::pattern", ...}
                for key in ("from", "to"):
                    node_str = node.get(key)
                    if node_str and isinstance(node_str, str):
                        result = check_node_for_sanitizer(node_str)
                        if result:
                            return result

        return None

    def close(self):
        """Clean up database connections."""
        self.repo_conn.close()
        self.graph_conn.close()
