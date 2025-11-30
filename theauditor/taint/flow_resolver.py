"""Complete flow resolution engine for codebase truth generation."""

import json
import sqlite3
from collections import defaultdict
from functools import lru_cache

from theauditor.utils.logger import setup_logger

from .sanitizer_util import SanitizerRegistry

logger = setup_logger(__name__)


INFRASTRUCTURE_MAX_EFFORT = 5_000
INFRASTRUCTURE_MAX_VISITS = 2
USERCODE_MAX_EFFORT = 25_000
USERCODE_MAX_VISITS = 10


class FlowResolver:
    """Resolves ALL control flows in codebase to populate resolved_flow_audit table."""

    # Phase 0.3: LRU cache sizes for lazy graph loading
    SUCCESSORS_CACHE_SIZE = 10_000  # Most traversals touch <10k unique nodes
    EDGE_TYPE_CACHE_SIZE = 20_000   # Edge types queried frequently during path recording

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
        self.max_depth = 20
        self.max_flows = 100_000
        self.max_flows_per_entry = 1_000

        self.sanitizer_registry = SanitizerRegistry(self.repo_cursor, registry=registry)

        # Phase 0.3: Removed eager loading of adjacency_list and edge_types
        # Now using lazy @lru_cache decorated methods for on-demand queries
        # Memory: O(cache_size) instead of O(all_edges)

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

        for _i, entry_id in enumerate(entry_nodes):
            if self.flows_resolved >= self.max_flows:
                logger.warning(f"Reached maximum flow limit ({self.max_flows})")
                break

            self._trace_from_entry(entry_id, exit_nodes)

        self.repo_conn.commit()

        logger.info(f"Flow resolution complete: {self.flows_resolved} flows resolved")
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
        """Get all entry points from the unified graph."""
        cursor = self.graph_conn.cursor()
        entry_nodes = []

        request_patterns = []
        if self.registry:
            for lang in ["javascript", "python", "rust"]:
                patterns = self.registry.get_source_patterns(lang)
                for p in patterns:
                    if p not in request_patterns:
                        request_patterns.append(p)

        for pattern in request_patterns:
            cursor.execute(
                """
                SELECT id FROM nodes
                WHERE graph_type = 'data_flow'
                  AND (id LIKE ? OR id LIKE ?)
            """,
                (f"%::{pattern}", f"%::{pattern}.%"),
            )

            for (node_id,) in cursor.fetchall():
                if node_id not in entry_nodes:
                    entry_nodes.append(node_id)

        cursor.execute("""
            SELECT DISTINCT target
            FROM edges
            WHERE graph_type = 'data_flow'
              AND type = 'cross_boundary'
        """)

        for (target,) in cursor.fetchall():
            entry_nodes.append(target)

        repo_cursor = self.repo_conn.cursor()
        repo_cursor.execute("""
            SELECT DISTINCT file, line, var_name, in_function
            FROM env_var_usage
        """)

        for row in repo_cursor.fetchall():
            file = row[0]
            var_name = row[2]
            func = row[3] if row[3] else "global"

            node_id = f"{file}::{func}::{var_name}"

            cursor.execute(
                """
                SELECT 1 FROM nodes
                WHERE graph_type = 'data_flow'
                  AND id = ?
                LIMIT 1
            """,
                (node_id,),
            )

            if cursor.fetchone():
                entry_nodes.append(node_id)

        cursor.execute("""
            SELECT DISTINCT target
            FROM edges
            WHERE graph_type = 'call'
              AND source LIKE '%index%'
              AND target NOT LIKE '%node_modules%'
            LIMIT 100
        """)

        for (target,) in cursor.fetchall():
            cursor.execute(
                """
                SELECT DISTINCT id FROM nodes
                WHERE graph_type = 'data_flow'
                  AND id LIKE ?
                LIMIT 1
            """,
                (f"{target.split('::')[0]}::%",),
            )

            result = cursor.fetchone()
            if result:
                entry_nodes.append(result[0])

        return entry_nodes

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
        """Trace all flows from a single entry point using DFS with Adaptive Throttling."""

        parts = entry_id.split("::")
        file_path = parts[0].lower()
        var_name = parts[-1] if len(parts) > 0 else ""

        is_infrastructure = (
            "config" in file_path
            or "env" in file_path
            or (var_name.isupper() and len(var_name) > 1)
            or "process.env" in var_name
        )

        if is_infrastructure:
            current_max_effort = INFRASTRUCTURE_MAX_EFFORT
            current_max_visits = INFRASTRUCTURE_MAX_VISITS
        else:
            current_max_effort = USERCODE_MAX_EFFORT
            current_max_visits = USERCODE_MAX_VISITS

        worklist = [(entry_id, [entry_id])]
        visited_edges: set[tuple[str, str]] = set()
        node_visit_counts: dict[str, int] = defaultdict(int)

        flows_from_this_entry = 0
        effort_counter = 0

        while (
            worklist
            and self.flows_resolved < self.max_flows
            and flows_from_this_entry < self.max_flows_per_entry
        ):
            effort_counter += 1
            if effort_counter > current_max_effort:
                break

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
        """
        cursor = self.graph_conn.cursor()
        cursor.execute("""
            SELECT target FROM edges
            WHERE source = ? AND graph_type = 'data_flow'
        """, (node_id,))

        return tuple(row[0] for row in cursor.fetchall())

    def _classify_flow(self, path: list[str]) -> tuple[str, dict | None]:
        """Classify a flow path based on sanitization."""

        sanitizer_meta = self.sanitizer_registry._path_goes_through_sanitizer(path)

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

        # Query assignment_source_vars (RHS of assignments) not assignments.target_var (LHS)
        # Source patterns like req.body, useAuth are SOURCE expressions, not target variables
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

        sink_line = 0
        sink_function = sink_parts[1] if len(sink_parts) > 1 else "global"

        # Query function_call_args and function_call_args_jsx for sink line
        # Sink patterns can be in:
        # - argument_expr (the pattern is passed as an argument)
        # - callee_function (the pattern IS the function being called, e.g. useState, setX)
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
                sink_file, f"%{sink_pattern}%", f"%{sink_pattern}%", sink_function, sink_function,
                sink_file, f"%{sink_pattern}%", f"%{sink_pattern}%", sink_function, sink_function,
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

        # TAINT FIX T4: Dynamic vulnerability classification instead of hardcoded "unknown"
        vuln_type = self._determine_vuln_type(sink_pattern, source_pattern)

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

    def _determine_vuln_type(self, sink_pattern: str, source_pattern: str | None = None) -> str:
        """Determine vulnerability type from sink and source patterns.

        TAINT FIX T4: Replace hardcoded "unknown" with dynamic classification.
        Classification based on common sink patterns across Node.js/Python/React.
        """
        if not sink_pattern:
            return "Data Exposure"

        lower_sink = sink_pattern.lower()
        lower_source = (source_pattern or "").lower()

        # XSS patterns - DOM manipulation and HTML output
        xss_patterns = [
            "innerhtml", "outerhtml", "dangerouslysetinnerhtml", "insertadjacenthtml",
            "document.write", "document.writeln", "res.send", "res.render", "res.write",
            "response.write", "response.send", "sethtml", "v-html", "ng-bind-html",
            "__html", "createelement", "appendchild", "insertbefore",
        ]
        if any(p in lower_sink for p in xss_patterns):
            return "Cross-Site Scripting (XSS)"

        # SQL Injection patterns
        sql_patterns = [
            "query", "execute", "exec", "raw", "sequelize.query", "knex.raw",
            "prisma.$queryraw", "prisma.$executeraw", "cursor.execute", "conn.execute",
            "db.query", "pool.query", "client.query", "sql", "rawquery",
        ]
        if any(p in lower_sink for p in sql_patterns):
            return "SQL Injection"

        # Command Injection patterns
        cmd_patterns = [
            "exec", "execsync", "spawn", "spawnsync", "child_process",
            "shellexecute", "popen", "system", "subprocess", "os.system",
            "os.popen", "subprocess.run", "subprocess.call", "subprocess.popen",
            "eval", "function(", "new function",
        ]
        if any(p in lower_sink for p in cmd_patterns):
            # Distinguish eval from exec
            if "eval" in lower_sink or "function(" in lower_sink:
                return "Code Injection"
            return "Command Injection"

        # Path Traversal patterns
        path_patterns = [
            "readfile", "writefile", "readfilesync", "writefilesync",
            "createreadstream", "createwritestream", "fs.read", "fs.write",
            "open(", "path.join", "path.resolve", "sendfile", "download",
            "unlink", "rmdir", "mkdir", "rename", "copy", "move",
        ]
        if any(p in lower_sink for p in path_patterns):
            return "Path Traversal"

        # SSRF patterns
        ssrf_patterns = [
            "fetch", "axios", "request", "http.get", "http.request",
            "https.get", "https.request", "urllib", "requests.get",
            "requests.post", "curl", "httpx",
        ]
        if any(p in lower_sink for p in ssrf_patterns):
            return "Server-Side Request Forgery (SSRF)"

        # Prototype Pollution (JS-specific)
        proto_patterns = [
            "__proto__", "constructor.prototype", "object.assign", "merge(",
            "extend(", "deepmerge", "lodash.merge", "$.extend",
        ]
        if any(p in lower_sink for p in proto_patterns):
            return "Prototype Pollution"

        # Log Injection
        log_patterns = [
            "console.log", "console.error", "console.warn", "logger.",
            "logging.", "log.info", "log.error", "log.debug",
        ]
        if any(p in lower_sink for p in log_patterns):
            return "Log Injection"

        # Redirect / Open Redirect
        redirect_patterns = [
            "redirect", "location.href", "location.assign", "location.replace",
            "res.redirect", "window.location",
        ]
        if any(p in lower_sink for p in redirect_patterns):
            return "Open Redirect"

        # Default - check source pattern for hints
        if "req.body" in lower_source or "req.params" in lower_source or "req.query" in lower_source:
            return "Unvalidated Input"
        if "user" in lower_source or "input" in lower_source:
            return "Unvalidated Input"

        return "Data Exposure"

    def _get_edge_type(self, from_node: str, to_node: str) -> str:
        """Get edge type via lazy DB query with LRU cache.

        Phase 0.3: Replaced in-memory edge_types with on-demand query.
        """
        return self._get_edge_type_cached(from_node, to_node)

    @lru_cache(maxsize=20_000)
    def _get_edge_type_cached(self, from_node: str, to_node: str) -> str:
        """Internal cached query for edge type."""
        cursor = self.graph_conn.cursor()
        cursor.execute("""
            SELECT type FROM edges
            WHERE source = ? AND target = ? AND graph_type = 'data_flow'
            LIMIT 1
        """, (from_node, to_node))

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

    def close(self):
        """Clean up database connections."""
        self.repo_conn.close()
        self.graph_conn.close()
