"""Direct database query interface for AI code navigation."""

import sqlite3
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

from theauditor.utils.helpers import normalize_path_for_db

VALID_TABLES = {
    "symbols",
    "function_call_args",
    "assignments",
    "api_endpoints",
    "findings_consolidated",
    "refs",
    "function_calls",
    "jwt_patterns",
    # NOTE: oauth_patterns, password_patterns, session_patterns were planned but never implemented
    "sql_queries",
    "orm_queries",
    "react_components",
    "python_routes",
    "js_routes",
}


def validate_table_name(table: str) -> str:
    """Validate table name against whitelist to prevent SQL injection."""
    if table not in VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    return table


@dataclass
class SymbolInfo:
    """Symbol definition with full context."""

    name: str
    type: str
    file: str
    line: int
    end_line: int
    signature: str | None = None
    is_exported: bool | None = False
    framework_type: str | None = None


@dataclass
class CallSite:
    """Function call location with context."""

    caller_file: str
    caller_line: int
    caller_function: str | None
    callee_function: str
    arguments: list[str]


@dataclass
class Dependency:
    """Import or call dependency between files."""

    source_file: str
    target_file: str
    import_type: str
    line: int
    symbols: list[str] | None = None


class CodeQueryEngine:
    """Query engine for code navigation."""

    def __init__(self, root: Path):
        """Initialize with project root."""

        self.root = Path(root).resolve()
        pf_dir = self.root / ".pf"

        repo_db_path = pf_dir / "repo_index.db"
        if not repo_db_path.exists():
            raise FileNotFoundError(
                f"Database not found: {repo_db_path}\nRun 'aud full' first to build the database."
            )

        self.repo_db = sqlite3.connect(str(repo_db_path))

        self.repo_db.execute("PRAGMA journal_mode=WAL;")
        self.repo_db.execute("PRAGMA synchronous=NORMAL;")
        self.repo_db.execute("PRAGMA cache_size=-64000;")
        self.repo_db.row_factory = sqlite3.Row

        graph_db_path = pf_dir / "graphs.db"
        if graph_db_path.exists():
            self.graph_db = sqlite3.connect(str(graph_db_path))
            self.graph_db.execute("PRAGMA journal_mode=WAL;")
            self.graph_db.execute("PRAGMA synchronous=NORMAL;")
            self.graph_db.execute("PRAGMA cache_size=-64000;")
            self.graph_db.row_factory = sqlite3.Row
        else:
            self.graph_db = None

    def _normalize_path(self, file_path: str) -> str:
        """Normalize file path for database queries."""
        return normalize_path_for_db(file_path, self.root)

    def _require_graph_db(self) -> None:
        """Enforce Architecture Law: No Graph DB = Hard Stop.

        Zero Fallback Policy: If graph_db is required but missing, CRASH.
        Do not return {"error": ...} - raise RuntimeError instead.
        """
        if not self.graph_db:
            raise RuntimeError(
                "Graph database required for this operation.\n"
                "Fix: Run 'aud full' (or 'aud graph build') to generate it."
            )

    def _find_similar_symbols(self, input_name: str, limit: int = 5) -> list[str]:
        """Find symbols similar to input for helpful 'Did you mean?' suggestions."""
        cursor = self.repo_db.cursor()
        suggestions = set()

        definition_tables = ["symbols", "symbols_jsx", "react_components"]

        for table in definition_tables:
            cursor.execute(
                f"""
                SELECT DISTINCT name FROM {table}
                WHERE name LIKE ?
                LIMIT ?
            """,
                (f"%{input_name}%", limit),
            )

            for row in cursor.fetchall():
                suggestions.add(row["name"])

        return list(suggestions)[:limit]

    def _resolve_symbol(self, input_name: str) -> tuple[list[str], str | None]:
        """Resolve user input to qualified symbol name(s).

        Uses unified UNION query to resolve symbols in O(1) queries instead of O(12-18).
        Priority: exact matches first, then suffix matches.
        """
        cursor = self.repo_db.cursor()

        suffix_pattern = f"%.{input_name}"

        last_segment_pattern = None
        if "." in input_name:
            last_segment = input_name.split(".")[-1]
            last_segment_pattern = f"%.{last_segment}"

        query_parts = []
        params = []

        for table in ["symbols", "symbols_jsx"]:
            query_parts.append(f"SELECT DISTINCT name, 1 AS priority FROM {table} WHERE name = ?")
            params.append(input_name)

            query_parts.append(
                f"SELECT DISTINCT name, 2 AS priority FROM {table} WHERE name LIKE ?"
            )
            params.append(suffix_pattern)

            if last_segment_pattern:
                query_parts.append(
                    f"SELECT DISTINCT name, 2 AS priority FROM {table} WHERE name LIKE ?"
                )
                params.append(last_segment_pattern)

        query_parts.append(
            "SELECT DISTINCT name, 1 AS priority FROM react_components WHERE name = ?"
        )
        params.append(input_name)

        for table in ["function_call_args", "function_call_args_jsx"]:
            query_parts.append(
                f"SELECT DISTINCT callee_function AS name, 1 AS priority FROM {table} WHERE callee_function = ?"
            )
            params.append(input_name)

            query_parts.append(
                f"SELECT DISTINCT callee_function AS name, 2 AS priority FROM {table} WHERE callee_function LIKE ?"
            )
            params.append(suffix_pattern)

            if last_segment_pattern:
                query_parts.append(
                    f"SELECT DISTINCT callee_function AS name, 2 AS priority FROM {table} WHERE callee_function LIKE ?"
                )
                params.append(last_segment_pattern)

        query = " UNION ".join(query_parts) + " ORDER BY priority, name"
        cursor.execute(query, params)

        found_symbols = set()
        for row in cursor.fetchall():
            found_symbols.add(row["name"])

        operator_chars = {"+", "-", "*", "/", "(", ")", " "}
        for table in ["function_call_args", "function_call_args_jsx"]:
            arg_query = f"""
                SELECT DISTINCT argument_expr FROM {table}
                WHERE argument_expr = ? OR argument_expr LIKE ?
            """
            arg_params = [input_name, suffix_pattern]

            if last_segment_pattern:
                arg_query += " OR argument_expr LIKE ?"
                arg_params.append(last_segment_pattern)

            cursor.execute(arg_query, arg_params)
            for row in cursor.fetchall():
                expr = row["argument_expr"]

                if expr and not any(c in expr for c in operator_chars):
                    found_symbols.add(expr)

        if not found_symbols:
            suggestions = self._find_similar_symbols(input_name)
            msg = f"Symbol '{input_name}' not found."
            if suggestions:
                msg += f" Did you mean: {', '.join(suggestions)}?"
            msg += "\nTip: Run `aud query --symbol <partial>` to discover exact names."
            return [], msg

        return list(found_symbols), None

    def find_symbol(self, name: str, type_filter: str | None = None) -> list[SymbolInfo] | dict:
        """Find symbol definitions by exact name match."""
        cursor = self.repo_db.cursor()
        results = []

        query = """
            SELECT path, name, type, line, end_line, type_annotation, is_typed
            FROM symbols
            WHERE name = ?
        """
        params = [name]
        if type_filter:
            query += " AND type = ?"
            params.append(type_filter)

        cursor.execute(query, params)
        for row in cursor.fetchall():
            results.append(
                SymbolInfo(
                    name=row["name"],
                    type=row["type"],
                    file=row["path"],
                    line=row["line"],
                    end_line=row["end_line"] or row["line"],
                    signature=row["type_annotation"],
                    is_exported=bool(row["is_typed"]) if row["is_typed"] is not None else False,
                    framework_type=None,
                )
            )

        query_jsx = """
            SELECT path, name, type, line
            FROM symbols_jsx
            WHERE name = ?
        """
        params_jsx = [name]
        if type_filter:
            query_jsx += " AND type = ?"
            params_jsx.append(type_filter)

        cursor.execute(query_jsx, params_jsx)
        for row in cursor.fetchall():
            results.append(
                SymbolInfo(
                    name=row["name"],
                    type=row["type"],
                    file=row["path"],
                    line=row["line"],
                    end_line=row["line"],
                    signature=None,
                    is_exported=False,
                    framework_type=None,
                )
            )

        unique_results = {}
        for sym in results:
            key = (sym.file, sym.line, sym.name)
            if key not in unique_results:
                unique_results[key] = sym
        results = list(unique_results.values())

        if not results:
            suggestions = self._find_similar_symbols(name)
            if suggestions:
                return {
                    "error": f"No symbol definitions found for '{name}'. Did you mean: {', '.join(suggestions)}?"
                }

        return results

    def get_callers(self, symbol_name: str, depth: int = 1) -> list[CallSite] | dict:
        """Find who calls a symbol (with optional transitive search).

        Uses Recursive CTE to push graph traversal to SQLite instead of Python BFS loop.
        Performance: O(1) queries instead of O(depth * symbols) queries.
        """
        if depth < 1 or depth > 5:
            raise ValueError("Depth must be between 1 and 5")

        resolved_names, error = self._resolve_symbol(symbol_name)

        if error:
            return {
                "error": error,
                "suggestion": "Use: aud query --symbol <partial> to search symbols",
            }

        cursor = self.repo_db.cursor()

        target_symbols = resolved_names
        placeholders = ",".join("?" * len(target_symbols))

        query = f"""
            WITH RECURSIVE
            -- Combine both call tables into unified view
            all_calls AS (
                SELECT file, line, caller_function, callee_function, argument_expr
                FROM function_call_args
                UNION ALL
                SELECT file, line, caller_function, callee_function, argument_expr
                FROM function_call_args_jsx
            ),
            -- Recursive traversal
            caller_graph(file, line, caller_function, callee_function, argument_expr, depth, visited_path) AS (
                -- BASE CASE: Direct callers of target symbol(s)
                SELECT
                    file, line, caller_function, callee_function, argument_expr,
                    1 AS depth,
                    caller_function AS visited_path
                FROM all_calls
                WHERE callee_function IN ({placeholders})
                   OR argument_expr IN ({placeholders})

                UNION ALL

                -- RECURSIVE STEP: Callers of callers
                SELECT
                    ac.file, ac.line, ac.caller_function, ac.callee_function, ac.argument_expr,
                    cg.depth + 1,
                    cg.visited_path || '>' || ac.caller_function
                FROM all_calls ac
                JOIN caller_graph cg ON ac.callee_function = cg.caller_function
                WHERE cg.depth < ?
                  AND cg.caller_function IS NOT NULL
                  -- Cycle detection: don't revisit same caller in this path
                  AND cg.visited_path NOT LIKE '%' || ac.caller_function || '%'
            )
            SELECT DISTINCT file, line, caller_function, callee_function, argument_expr, depth
            FROM caller_graph
            ORDER BY depth, file, line
        """

        params = tuple(target_symbols) + tuple(target_symbols) + (depth,)
        cursor.execute(query, params)

        visited = set()
        all_callers = []

        for row in cursor.fetchall():
            caller_key = (row["caller_function"], row["file"], row["line"])
            if caller_key not in visited:
                visited.add(caller_key)
                all_callers.append(
                    CallSite(
                        caller_file=row["file"],
                        caller_line=row["line"],
                        caller_function=row["caller_function"],
                        callee_function=row["callee_function"],
                        arguments=[row["argument_expr"]] if row["argument_expr"] else [],
                    )
                )

        return all_callers

    def get_callees(self, symbol_name: str) -> list[CallSite]:
        """Find what a symbol calls."""
        cursor = self.repo_db.cursor()
        callees = []

        for table in ["function_call_args", "function_call_args_jsx"]:
            query = f"""
                SELECT DISTINCT
                    file, line, caller_function, callee_function, argument_expr
                FROM {table}
                WHERE caller_function LIKE ?
                ORDER BY line
            """

            cursor.execute(query, (f"%{symbol_name}%",))

            for row in cursor.fetchall():
                callees.append(
                    CallSite(
                        caller_file=row["file"],
                        caller_line=row["line"],
                        caller_function=row["caller_function"],
                        callee_function=row["callee_function"],
                        arguments=[row["argument_expr"]] if row["argument_expr"] else [],
                    )
                )

        return callees

    def get_file_dependencies(
        self, file_path: str, direction: str = "both"
    ) -> dict[str, list[Dependency]]:
        """Get import dependencies for a file."""
        self._require_graph_db()

        cursor = self.graph_db.cursor()
        result = {}

        if direction in ["incoming", "both"]:
            cursor.execute(
                """
                SELECT source, target, type, line
                FROM edges
                WHERE target LIKE ? AND graph_type = 'import'
                ORDER BY source
            """,
                (f"%{file_path}%",),
            )

            result["incoming"] = [
                Dependency(
                    source_file=row["source"],
                    target_file=row["target"],
                    import_type=row["type"],
                    line=row["line"] or 0,
                    symbols=[],
                )
                for row in cursor.fetchall()
            ]

        if direction in ["outgoing", "both"]:
            cursor.execute(
                """
                SELECT source, target, type, line
                FROM edges
                WHERE source LIKE ? AND graph_type = 'import'
                ORDER BY target
            """,
                (f"%{file_path}%",),
            )

            result["outgoing"] = [
                Dependency(
                    source_file=row["source"],
                    target_file=row["target"],
                    import_type=row["type"],
                    line=row["line"] or 0,
                    symbols=[],
                )
                for row in cursor.fetchall()
            ]

        return result

    def get_api_handlers(self, route_pattern: str) -> list[dict]:
        """Find API endpoint handlers."""

        if route_pattern.startswith("C:/Program Files/Git"):
            route_pattern = route_pattern.replace("C:/Program Files/Git", "")

        cursor = self.repo_db.cursor()

        cursor.execute(
            """
            SELECT ae.file, ae.line, ae.method, ae.pattern, ae.path, ae.full_path,
                   ae.handler_function,
                   GROUP_CONCAT(aec.control_name, ', ') AS controls,
                   CASE WHEN COUNT(aec.control_name) > 0 THEN 1 ELSE 0 END AS has_auth,
                   COUNT(aec.control_name) AS control_count
            FROM api_endpoints ae
            LEFT JOIN api_endpoint_controls aec
              ON ae.file = aec.endpoint_file
              AND ae.line = aec.endpoint_line
            WHERE ae.full_path LIKE ? OR ae.pattern LIKE ? OR ae.path LIKE ?
            GROUP BY ae.file, ae.line, ae.method, ae.path
            ORDER BY ae.full_path, ae.method
        """,
            (f"%{route_pattern}%", f"%{route_pattern}%", f"%{route_pattern}%"),
        )

        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)

            controls_str = row_dict.get("controls")
            if controls_str:
                row_dict["controls"] = [c.strip() for c in controls_str.split(",")]
            else:
                row_dict["controls"] = []
            results.append(row_dict)
        return results

    def get_component_tree(self, component_name: str) -> dict:
        """Get React component hierarchy."""
        cursor = self.repo_db.cursor()

        cursor.execute(
            """
            SELECT
                rc.file, rc.name, rc.type, rc.start_line, rc.end_line,
                rc.has_jsx, rc.props_type,
                GROUP_CONCAT(rch.hook_name) as hooks_concat
            FROM react_components rc
            LEFT JOIN react_component_hooks rch
                ON rc.file = rch.component_file AND rc.name = rch.component_name
            WHERE rc.name = ?
            GROUP BY rc.file, rc.name, rc.type, rc.start_line, rc.end_line, rc.has_jsx, rc.props_type
        """,
            (component_name,),
        )

        row = cursor.fetchone()
        if not row:
            msg = f"Component not found: {component_name}"
            suggestions = self._find_similar_symbols(component_name)
            if suggestions:
                msg += f". Did you mean: {', '.join(suggestions)}?"
            return {"error": msg}

        result = dict(row)

        hooks_concat = result.pop("hooks_concat", None)
        if hooks_concat:
            result["hooks"] = hooks_concat.split(",")
        else:
            result["hooks"] = []

        cursor.execute(
            """
            SELECT DISTINCT callee_function as child_component, line
            FROM function_call_args_jsx
            WHERE file = ? AND callee_function IN (SELECT name FROM react_components)
            ORDER BY line
        """,
            (result["file"],),
        )
        result["children"] = [dict(r) for r in cursor.fetchall()]

        return result

    def get_data_dependencies(self, symbol_name: str) -> dict[str, list[dict]]:
        """Get data dependencies (reads/writes) for a function."""
        if not symbol_name:
            raise ValueError("symbol_name cannot be empty")

        cursor = self.repo_db.cursor()

        cursor.execute(
            """
            SELECT target_var, source_expr, line, file
            FROM assignments
            WHERE in_function = ?
            ORDER BY line
        """,
            (symbol_name,),
        )

        writes = []
        for row in cursor.fetchall():
            writes.append(
                {
                    "variable": row["target_var"],
                    "expression": row["source_expr"],
                    "line": row["line"],
                    "file": row["file"],
                }
            )

        cursor.execute(
            """
            SELECT DISTINCT asrc.source_var_name
            FROM assignments a
            JOIN assignment_sources asrc
                ON a.file = asrc.assignment_file
                AND a.line = asrc.assignment_line
                AND a.target_var = asrc.assignment_target
            WHERE a.in_function = ?
        """,
            (symbol_name,),
        )

        all_reads = {row["source_var_name"] for row in cursor.fetchall() if row["source_var_name"]}

        reads = [{"variable": var} for var in sorted(all_reads)]

        return {"reads": reads, "writes": writes}

    def trace_variable_flow(self, var_name: str, from_file: str, depth: int = 10) -> list[dict]:
        """Trace variable through def-use chains using assignment_sources."""
        if not var_name:
            raise ValueError("var_name cannot be empty")
        if depth < 1 or depth > 10:
            raise ValueError("Depth must be between 1 and 10")

        from_file = self._normalize_path(from_file)
        cursor = self.repo_db.cursor()
        flows = []
        queue = deque([(var_name, from_file, 0)])
        visited = set()

        while queue:
            current_var, current_file, current_depth = queue.popleft()

            if current_depth >= depth:
                continue

            visit_key = (current_var, current_file)
            if visit_key in visited:
                continue
            visited.add(visit_key)

            cursor.execute(
                """
                SELECT
                    a.target_var,
                    a.source_expr,
                    a.file,
                    a.line,
                    a.in_function,
                    asrc.source_var_name
                FROM assignments a
                JOIN assignment_sources asrc
                    ON a.file = asrc.assignment_file
                    AND a.line = asrc.assignment_line
                    AND a.target_var = asrc.assignment_target
                WHERE asrc.source_var_name = ?
                    AND a.file LIKE ?
            """,
                (current_var, f"%{current_file}%"),
            )

            for row in cursor.fetchall():
                flow_step = {
                    "from_var": current_var,
                    "to_var": row["target_var"],
                    "expression": row["source_expr"],
                    "file": row["file"],
                    "line": row["line"],
                    "function": row["in_function"] or "global",
                    "depth": current_depth + 1,
                }
                flows.append(flow_step)

                if current_depth + 1 < depth:
                    queue.append((row["target_var"], row["file"], current_depth + 1))

        return flows

    def get_cross_function_taint(self, function_name: str) -> list[dict]:
        """Track variables returned from function and assigned elsewhere."""
        if not function_name:
            raise ValueError("function_name cannot be empty")

        cursor = self.repo_db.cursor()

        cursor.execute(
            """
            SELECT
                frs.return_var_name,
                frs.return_file,
                frs.return_line,
                a.target_var AS assignment_var,
                a.file AS assignment_file,
                a.line AS assignment_line,
                a.in_function AS assigned_in_function
            FROM function_return_sources frs
            JOIN assignment_sources asrc
                ON frs.return_var_name = asrc.source_var_name
            JOIN assignments a
                ON asrc.assignment_file = a.file
                AND asrc.assignment_line = a.line
                AND asrc.assignment_target = a.target_var
            WHERE frs.return_function = ?
            ORDER BY frs.return_line, a.line
        """,
            (function_name,),
        )

        flows = []
        for row in cursor.fetchall():
            flows.append(
                {
                    "return_var": row["return_var_name"],
                    "return_file": row["return_file"],
                    "return_line": row["return_line"],
                    "assignment_var": row["assignment_var"],
                    "assignment_file": row["assignment_file"],
                    "assignment_line": row["assignment_line"],
                    "assigned_in_function": row["assigned_in_function"] or "global",
                    "flow_type": "cross_function_taint",
                }
            )

        return flows

    def get_api_security_coverage(self, route_pattern: str | None = None) -> list[dict]:
        """Find API endpoints and their authentication controls via junction table."""
        cursor = self.repo_db.cursor()

        if route_pattern:
            cursor.execute(
                """
                SELECT
                    ae.file,
                    ae.line,
                    ae.method,
                    ae.pattern,
                    ae.path,
                    ae.handler_function,
                    GROUP_CONCAT(aec.control_name, ', ') AS controls
                FROM api_endpoints ae
                LEFT JOIN api_endpoint_controls aec
                    ON ae.file = aec.endpoint_file
                    AND ae.line = aec.endpoint_line
                WHERE ae.pattern LIKE ? OR ae.path LIKE ?
                GROUP BY ae.file, ae.line, ae.method, ae.path
                ORDER BY ae.path, ae.method
            """,
                (f"%{route_pattern}%", f"%{route_pattern}%"),
            )
        else:
            cursor.execute("""
                SELECT
                    ae.file,
                    ae.line,
                    ae.method,
                    ae.pattern,
                    ae.path,
                    ae.handler_function,
                    GROUP_CONCAT(aec.control_name, ', ') AS controls
                FROM api_endpoints ae
                LEFT JOIN api_endpoint_controls aec
                    ON ae.file = aec.endpoint_file
                    AND ae.line = aec.endpoint_line
                GROUP BY ae.file, ae.line, ae.method, ae.path
                ORDER BY ae.path, ae.method
            """)

        endpoints = []
        for row in cursor.fetchall():
            controls_str = row["controls"] or ""
            controls_list = [c.strip() for c in controls_str.split(",") if c.strip()]

            endpoints.append(
                {
                    "file": row["file"],
                    "line": row["line"],
                    "method": row["method"],
                    "pattern": row["pattern"],
                    "path": row["path"],
                    "handler_function": row["handler_function"],
                    "controls": controls_list,
                    "control_count": len(controls_list),
                    "has_auth": len(controls_list) > 0,
                }
            )

        return endpoints

    def get_findings(
        self,
        file_path: str | None = None,
        tool: str | None = None,
        severity: str | None = None,
        rule: str | None = None,
        category: str | None = None,
        limit: int = 5000,
    ) -> list[dict]:
        """Query findings from findings_consolidated table."""
        cursor = self.repo_db.cursor()

        where_clauses = []
        params = []

        if file_path:
            where_clauses.append("file LIKE ?")
            params.append(f"%{file_path}%")

        if tool:
            where_clauses.append("tool = ?")
            params.append(tool)

        if severity:
            where_clauses.append("severity = ?")
            params.append(severity)

        if rule:
            where_clauses.append("rule LIKE ?")
            params.append(f"%{rule}%")

        if category:
            where_clauses.append("category = ?")
            params.append(category)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Build limit clause (0 = unlimited)
        limit_sql = f"LIMIT {limit}" if limit > 0 else ""

        cursor.execute(
            f"""
            SELECT file, line, column, rule, tool, message, severity,
                   category, confidence, cwe,
                   cfg_function, cfg_complexity, cfg_block_count,
                   graph_id, graph_score, graph_centrality,
                   mypy_error_code, mypy_severity_int,
                   tf_finding_id, tf_resource_id, tf_remediation
            FROM findings_consolidated
            WHERE {where_sql}
            ORDER BY severity DESC, file, line
            {limit_sql}
        """,
            params,
        )

        findings = []
        for row in cursor.fetchall():
            finding = {
                "file": row["file"],
                "line": row["line"],
                "column": row["column"],
                "rule": row["rule"],
                "tool": row["tool"],
                "message": row["message"],
                "severity": row["severity"],
                "category": row["category"],
                "confidence": row["confidence"],
                "cwe": row["cwe"],
            }

            details = {}
            tool = row["tool"]

            if tool == "cfg-analysis":
                if row["cfg_function"]:
                    details["function"] = row["cfg_function"]
                if row["cfg_complexity"] is not None:
                    details["complexity"] = row["cfg_complexity"]
                if row["cfg_block_count"] is not None:
                    details["block_count"] = row["cfg_block_count"]

            elif tool == "graph-analysis":
                if row["graph_id"]:
                    details["id"] = row["graph_id"]
                if row["graph_score"] is not None:
                    details["score"] = row["graph_score"]
                if row["graph_centrality"] is not None:
                    details["centrality"] = row["graph_centrality"]

            elif tool == "mypy":
                if row["mypy_error_code"]:
                    details["error_code"] = row["mypy_error_code"]
                if row["mypy_severity_int"] is not None:
                    details["severity"] = row["mypy_severity_int"]

            elif tool == "terraform":
                if row["tf_finding_id"]:
                    details["finding_id"] = row["tf_finding_id"]
                if row["tf_resource_id"]:
                    details["resource_id"] = row["tf_resource_id"]
                if row["tf_remediation"]:
                    details["remediation"] = row["tf_remediation"]

            if details:
                finding["details"] = details

            findings.append(finding)

        return findings

    def pattern_search(
        self,
        pattern: str,
        type_filter: str | None = None,
        path_filter: str | None = None,
        limit: int = 100,
    ) -> list[SymbolInfo]:
        """Search symbols by pattern (LIKE query)."""
        cursor = self.repo_db.cursor()
        results = []

        query = """
            SELECT path, name, type, line, end_line, type_annotation, is_typed
            FROM symbols
            WHERE name LIKE ?
        """
        params = [pattern]

        if type_filter:
            query += " AND type = ?"
            params.append(type_filter)

        if path_filter:
            query += " AND path LIKE ?"
            params.append(path_filter)

        query += " ORDER BY path, line"
        query += f" LIMIT {limit}"

        cursor.execute(query, params)

        for row in cursor.fetchall():
            results.append(
                SymbolInfo(
                    name=row["name"],
                    type=row["type"],
                    file=row["path"],
                    line=row["line"],
                    end_line=row["end_line"] or row["line"],
                    signature=row["type_annotation"],
                    is_exported=bool(row["is_typed"]) if row["is_typed"] is not None else False,
                    framework_type=None,
                )
            )

        query_jsx = """
            SELECT path, name, type, line
            FROM symbols_jsx
            WHERE name LIKE ?
        """
        params_jsx = [pattern]

        if type_filter:
            query_jsx += " AND type = ?"
            params_jsx.append(type_filter)

        if path_filter:
            query_jsx += " AND path LIKE ?"
            params_jsx.append(path_filter)

        query_jsx += " ORDER BY path, line"
        query_jsx += f" LIMIT {limit}"

        cursor.execute(query_jsx, params_jsx)

        for row in cursor.fetchall():
            results.append(
                SymbolInfo(
                    name=row["name"],
                    type=row["type"],
                    file=row["path"],
                    line=row["line"],
                    end_line=row["line"],
                    signature=None,
                    is_exported=False,
                    framework_type=None,
                )
            )

        return results[:limit]

    def content_search(
        self,
        pattern: str,
        path_filter: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Search code content in expressions and function arguments.

        Unlike pattern_search (which searches symbol names), this searches
        the actual code content stored in:
        - function_call_args.argument_expr (function call arguments)
        - assignments.source_expr (right-hand side of assignments)

        Args:
            pattern: SQL LIKE pattern (use % as wildcard)
            path_filter: Optional path filter (SQL LIKE pattern)
            limit: Maximum results to return

        Returns:
            List of matches with file, line, context, and matched content
        """
        cursor = self.repo_db.cursor()
        results = []

        # Search function_call_args.argument_expr
        query_args = """
            SELECT file, line, caller_function, callee_function, argument_expr
            FROM function_call_args
            WHERE argument_expr LIKE ?
        """
        params_args = [pattern]

        if path_filter:
            query_args += " AND file LIKE ?"
            params_args.append(path_filter)

        query_args += f" ORDER BY file, line LIMIT {limit}"

        cursor.execute(query_args, params_args)
        for row in cursor.fetchall():
            results.append({
                "type": "function_argument",
                "file": row["file"],
                "line": row["line"],
                "context": f"{row['caller_function'] or 'global'} -> {row['callee_function']}",
                "content": row["argument_expr"],
            })

        # Search assignments.source_expr
        remaining = limit - len(results)
        if remaining > 0:
            query_assign = """
                SELECT file, line, target_var, source_expr, in_function
                FROM assignments
                WHERE source_expr LIKE ?
            """
            params_assign = [pattern]

            if path_filter:
                query_assign += " AND file LIKE ?"
                params_assign.append(path_filter)

            query_assign += f" ORDER BY file, line LIMIT {remaining}"

            cursor.execute(query_assign, params_assign)
            for row in cursor.fetchall():
                results.append({
                    "type": "assignment",
                    "file": row["file"],
                    "line": row["line"],
                    "context": f"{row['target_var']} = ... (in {row['in_function'] or 'global'})",
                    "content": row["source_expr"],
                })

        # Also search function_call_args in JSX files
        remaining = limit - len(results)
        if remaining > 0:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='function_call_args_jsx'")
            if cursor.fetchone():
                query_jsx = """
                    SELECT file, line, caller_function, callee_function, argument_expr
                    FROM function_call_args_jsx
                    WHERE argument_expr LIKE ?
                """
                params_jsx = [pattern]

                if path_filter:
                    query_jsx += " AND file LIKE ?"
                    params_jsx.append(path_filter)

                query_jsx += f" ORDER BY file, line LIMIT {remaining}"

                cursor.execute(query_jsx, params_jsx)
                for row in cursor.fetchall():
                    results.append({
                        "type": "jsx_function_argument",
                        "file": row["file"],
                        "line": row["line"],
                        "context": f"{row['caller_function'] or 'global'} -> {row['callee_function']}",
                        "content": row["argument_expr"],
                    })

        return results

    def category_search(self, category: str, limit: int = 200) -> dict[str, list[dict]]:
        """Search across pattern tables by security category.

        Primary source is findings_consolidated. Additional tables are queried
        only if they exist in the database.
        """
        cursor = self.repo_db.cursor()
        results = {}

        # Get existing tables first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        # Tables that MAY exist for each category
        category_tables = {
            "jwt": ["jwt_patterns"],
            "oauth": ["oauth_patterns"],
            "password": ["password_patterns"],
            "session": ["session_patterns"],
            "sql": ["sql_queries", "orm_queries"],
            "xss": ["react_components"],
            "auth": ["jwt_patterns", "oauth_patterns", "password_patterns", "session_patterns"],
        }

        tables = category_tables.get(category.lower(), [])

        # Only query tables that actually exist
        for table in tables:
            if table not in existing_tables:
                continue
            validated_table = validate_table_name(table)
            cursor.execute(f"SELECT * FROM {validated_table} LIMIT {limit}")
            rows = cursor.fetchall()
            if rows:
                results[table] = [dict(row) for row in rows]

        # Primary source: findings_consolidated (always exists after aud full)
        cursor.execute(
            f"SELECT * FROM findings_consolidated WHERE category LIKE ? LIMIT {limit}",
            (f"%{category}%",),
        )
        findings = cursor.fetchall()
        if findings:
            results["findings"] = [dict(row) for row in findings]

        # Also search by rule name (e.g., "password" matches rules about passwords)
        cursor.execute(
            f"SELECT * FROM findings_consolidated WHERE rule LIKE ? LIMIT {limit}",
            (f"%{category}%",),
        )
        rule_findings = cursor.fetchall()
        if rule_findings:
            # Dedupe with existing findings
            existing_ids = {f.get("id") for f in results.get("findings", [])}
            new_findings = [dict(row) for row in rule_findings if dict(row).get("id") not in existing_ids]
            if new_findings:
                results.setdefault("findings", []).extend(new_findings)

        # Symbol search as fallback
        pattern_results = self.pattern_search(f"%{category}%", limit=limit)
        if pattern_results:
            results["symbols"] = [asdict(s) for s in pattern_results]

        return results

    def cross_table_search(
        self, search_term: str, include_tables: list[str] | None = None, limit: int = 50
    ) -> dict[str, list[dict]]:
        """Search across multiple tables (exploratory analysis)."""
        cursor = self.repo_db.cursor()
        results = {}

        if not include_tables:
            include_tables = [
                "symbols",
                "api_endpoints",
                "react_components",
                "findings_consolidated",
                "function_call_args",
                "assignments",
            ]

        for table in include_tables:
            validated_table = validate_table_name(table)

            cursor.execute(f"PRAGMA table_info({validated_table})")
            columns = [row[1] for row in cursor.fetchall()]

            text_columns = [
                c
                for c in columns
                if c
                in [
                    "name",
                    "file",
                    "route",
                    "handler_function",
                    "callee_function",
                    "target_var",
                    "variable_name",
                    "message",
                    "rule",
                ]
            ]

            if not text_columns:
                continue

            where_parts = [f"{col} LIKE ?" for col in text_columns]
            where_clause = " OR ".join(where_parts)
            params = [f"%{search_term}%"] * len(text_columns)

            query = f"SELECT * FROM {validated_table} WHERE {where_clause} LIMIT {limit}"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            if rows:
                results[table] = [dict(row) for row in rows]

        return results

    REACT_HOOK_NAMES = {
        "useState",
        "useEffect",
        "useCallback",
        "useMemo",
        "useRef",
        "useContext",
        "useReducer",
        "useLayoutEffect",
        "useImperativeHandle",
        "useDebugValue",
        "useTransition",
        "useDeferredValue",
        "useId",
        "useSyncExternalStore",
        "useInsertionEffect",
        "useAuth",
        "useForm",
        "useQuery",
        "useMutation",
        "useSelector",
        "useDispatch",
        "useNavigate",
        "useParams",
        "useLocation",
        "useHistory",
        "useRouter",
        "useStore",
        "useTheme",
        "useModal",
        "useToast",
    }

    def get_file_symbols(self, file_path: str, limit: int = 50) -> list[dict]:
        """Get all symbols defined in a file."""
        cursor = self.repo_db.cursor()
        results = []

        normalized_path = self._normalize_path(file_path)

        cursor.execute(
            """
            SELECT name, type, line, end_line, type_annotation, path
            FROM symbols
            WHERE path LIKE ?
              AND type NOT IN ('call')
            ORDER BY line
            LIMIT ?
        """,
            (f"%{normalized_path}", limit),
        )

        for row in cursor.fetchall():
            results.append(
                {
                    "name": row["name"],
                    "type": row["type"],
                    "line": row["line"],
                    "end_line": row["end_line"] or row["line"],
                    "signature": row["type_annotation"],
                    "path": row["path"],
                }
            )

        remaining = limit - len(results)
        if remaining > 0:
            cursor.execute(
                """
                SELECT name, type, line, path
                FROM symbols_jsx
                WHERE path LIKE ?
                  AND type NOT IN ('call')
                ORDER BY line
                LIMIT ?
            """,
                (f"%{normalized_path}", remaining),
            )

            for row in cursor.fetchall():
                results.append(
                    {
                        "name": row["name"],
                        "type": row["type"],
                        "line": row["line"],
                        "end_line": row["line"],
                        "signature": None,
                        "path": row["path"],
                    }
                )

        return results[:limit]

    def get_file_hooks(self, file_path: str) -> list[dict]:
        """Get React/Vue hooks used in a file."""
        cursor = self.repo_db.cursor()
        results = []

        normalized_path = self._normalize_path(file_path)

        cursor.execute(
            """
            SELECT DISTINCT hook_name, line
            FROM react_hooks
            WHERE file LIKE ?
            ORDER BY line
        """,
            (f"%{normalized_path}",),
        )

        for row in cursor.fetchall():
            hook = row["hook_name"]

            is_known_hook = hook in self.REACT_HOOK_NAMES
            is_custom_hook = hook.startswith("use") and len(hook) > 3 and hook[3].isupper()
            if is_known_hook or is_custom_hook:
                results.append(
                    {
                        "hook_name": hook,
                        "line": row["line"],
                    }
                )

        cursor.execute(
            """
            SELECT DISTINCT hook_name, line
            FROM vue_hooks
            WHERE file LIKE ?
            ORDER BY line
        """,
            (f"%{normalized_path}",),
        )

        for row in cursor.fetchall():
            results.append(
                {
                    "hook_name": row["hook_name"],
                    "line": row["line"],
                }
            )

        return results

    def get_file_imports(self, file_path: str, limit: int = 50) -> list[dict]:
        """Get imports declared in a file."""
        cursor = self.repo_db.cursor()

        normalized_path = self._normalize_path(file_path)

        cursor.execute(
            """
            SELECT value, kind, line
            FROM refs
            WHERE src LIKE ?
            ORDER BY line
            LIMIT ?
        """,
            (f"%{normalized_path}", limit),
        )

        return [
            {"module": row["value"], "kind": row["kind"], "line": row["line"]}
            for row in cursor.fetchall()
        ]

    def get_file_importers(self, file_path: str, limit: int = 50) -> list[dict]:
        """Get files that import this file."""
        self._require_graph_db()

        cursor = self.graph_db.cursor()

        normalized_path = self._normalize_path(file_path)

        cursor.execute(
            """
            SELECT source, type, line
            FROM edges
            WHERE target LIKE ? AND graph_type = 'import'
            ORDER BY source
            LIMIT ?
        """,
            (f"%{normalized_path}%", limit),
        )

        return [
            {"source_file": row["source"], "type": row["type"], "line": row["line"] or 0}
            for row in cursor.fetchall()
        ]

    NOISE_FUNCTIONS = {
        "print",
        "len",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "range",
        "enumerate",
        "zip",
        "isinstance",
        "issubclass",
        "super",
        "getattr",
        "setattr",
        "hasattr",
        "delattr",
        "min",
        "max",
        "sum",
        "any",
        "all",
        "open",
        "repr",
        "type",
        "help",
        "dir",
        "id",
        "input",
        "abs",
        "round",
        "sorted",
        "reversed",
        "filter",
        "map",
        "format",
        "ord",
        "chr",
        "hex",
        "bin",
        "oct",
        "hash",
        "callable",
        "vars",
        "locals",
        "globals",
        "iter",
        "next",
        "slice",
        "property",
        "staticmethod",
        "classmethod",
        "object",
        "bytes",
        "bytearray",
        "Exception",
        "ValueError",
        "TypeError",
        "RuntimeError",
        "KeyError",
        "IndexError",
        "AttributeError",
        "ImportError",
        "OSError",
        "IOError",
        "FileNotFoundError",
        "NotImplementedError",
        "StopIteration",
        "AssertionError",
        "ZeroDivisionError",
        "OverflowError",
        "console.log",
        "console.error",
        "console.warn",
        "console.info",
        "console.debug",
        "require",
        "import",
        "typeof",
        "parseInt",
        "parseFloat",
        "JSON.stringify",
        "JSON.parse",
        "Object.keys",
        "Object.values",
        "Object.entries",
        "Array.isArray",
        "String",
        "Number",
        "Boolean",
        "Array",
        "Object",
        "Promise",
        "setTimeout",
        "setInterval",
        "clearTimeout",
        "clearInterval",
        "describe",
        "it",
        "test",
        "expect",
        "beforeEach",
        "afterEach",
        "beforeAll",
        "afterAll",
        "jest",
        "assert",
        "pytest",
    }

    def get_file_outgoing_calls(self, file_path: str, limit: int = 50) -> list[dict]:
        """Get function calls made FROM this file."""
        cursor = self.repo_db.cursor()
        results = []

        normalized_path = self._normalize_path(file_path)

        noise_list = list(self.NOISE_FUNCTIONS)
        placeholders = ", ".join(["?"] * len(noise_list))

        for table in ["function_call_args", "function_call_args_jsx"]:
            cursor.execute(
                f"""
                SELECT DISTINCT callee_function, line, argument_expr, caller_function, file
                FROM {table}
                WHERE file LIKE ?
                  AND callee_function NOT IN ({placeholders})
                ORDER BY line
                LIMIT ?
            """,
                [f"%{normalized_path}"] + noise_list + [limit - len(results)],
            )

            for row in cursor.fetchall():
                results.append(
                    {
                        "callee_function": row["callee_function"],
                        "line": row["line"],
                        "arguments": row["argument_expr"] or "",
                        "caller_function": row["caller_function"],
                        "file": row["file"],
                    }
                )

        return results[:limit]

    def get_file_incoming_calls(self, file_path: str, limit: int = 50) -> list[dict]:
        """Get calls TO symbols defined in this file."""
        cursor = self.repo_db.cursor()

        normalized_path = self._normalize_path(file_path)

        cursor.execute(
            """
            SELECT DISTINCT name FROM symbols
            WHERE path LIKE ? AND type IN ('function', 'class', 'method')
        """,
            (f"%{normalized_path}",),
        )

        symbol_names = [row["name"] for row in cursor.fetchall()]

        if not symbol_names:
            return []

        placeholders = ",".join(["?" for _ in symbol_names])

        results = []
        for table in ["function_call_args", "function_call_args_jsx"]:
            cursor.execute(
                f"""
                SELECT DISTINCT file, line, caller_function, callee_function
                FROM {table}
                WHERE callee_function IN ({placeholders})
                  AND file NOT LIKE ?
                ORDER BY file, line
                LIMIT ?
            """,
                (*symbol_names, f"%{normalized_path}", limit - len(results)),
            )

            for row in cursor.fetchall():
                results.append(
                    {
                        "caller_file": row["file"],
                        "caller_line": row["line"],
                        "caller_function": row["caller_function"],
                        "callee_function": row["callee_function"],
                    }
                )

            if len(results) >= limit:
                break

        return results[:limit]

    def get_file_framework_info(self, file_path: str) -> dict:
        """Get framework-specific information for a file."""
        cursor = self.repo_db.cursor()
        result = {"framework": None}

        normalized_path = self._normalize_path(file_path)

        ext = file_path.split(".")[-1].lower() if "." in file_path else ""

        if ext in ("tsx", "jsx", "vue"):
            cursor.execute(
                """
                SELECT name, type, start_line, end_line, props_type
                FROM react_components
                WHERE file LIKE ?
            """,
                (f"%{normalized_path}",),
            )
            components = [dict(row) for row in cursor.fetchall()]
            if components:
                result["framework"] = "react"
                result["components"] = components

            cursor.execute(
                """
                SELECT name, type, start_line, end_line
                FROM vue_components
                WHERE file LIKE ?
            """,
                (f"%{normalized_path}",),
            )
            vue_comps = [dict(row) for row in cursor.fetchall()]
            if vue_comps:
                result["framework"] = "vue"
                result["components"] = vue_comps

        if ext in ("ts", "js", "mjs"):
            cursor.execute(
                """
                SELECT method, path, handler_function, line
                FROM api_endpoints
                WHERE file LIKE ?
            """,
                (f"%{normalized_path}",),
            )
            routes = [dict(row) for row in cursor.fetchall()]
            if routes:
                result["framework"] = result.get("framework") or "express"
                result["routes"] = routes

            cursor.execute(
                """
                SELECT route_path, route_method, handler_expr, execution_order
                FROM express_middleware_chains
                WHERE file LIKE ?
                ORDER BY route_path, execution_order
            """,
                (f"%{normalized_path}",),
            )
            middleware = [dict(row) for row in cursor.fetchall()]
            if middleware:
                result["framework"] = result.get("framework") or "express"
                result["middleware"] = middleware

        if ext == "py":
            cursor.execute(
                """
                SELECT method, pattern, handler_function, framework, line
                FROM python_routes
                WHERE file LIKE ?
            """,
                (f"%{normalized_path}",),
            )
            routes = [dict(row) for row in cursor.fetchall()]
            if routes:
                result["framework"] = routes[0].get("framework", "flask")
                result["routes"] = routes

            cursor.execute(
                """
                SELECT decorator_name, target_name, line
                FROM python_decorators
                WHERE file LIKE ?
            """,
                (f"%{normalized_path}",),
            )
            decorators = [dict(row) for row in cursor.fetchall()]
            if decorators:
                result["decorators"] = decorators

        cursor.execute(
            """
            SELECT model_name, table_name, line
            FROM sequelize_models
            WHERE file LIKE ?
        """,
            (f"%{normalized_path}",),
        )
        models = [dict(row) for row in cursor.fetchall()]
        if models:
            result["framework"] = result.get("framework") or "sequelize"
            result["models"] = models

        if ext == "go":
            cursor.execute(
                """
                SELECT method, path, handler_func, framework, line
                FROM go_routes
                WHERE file_path LIKE ?
            """,
                (f"%{normalized_path}",),
            )
            routes = [dict(row) for row in cursor.fetchall()]
            if routes:
                result["framework"] = routes[0].get("framework", "gin")
                result["routes"] = routes

        if ext == "rs":
            cursor.execute(
                """
                SELECT attribute_name, args, target_name, target_line, line
                FROM rust_attributes
                WHERE file_path LIKE ?
                AND attribute_name IN ('get', 'post', 'put', 'delete', 'patch', 'route', 'web')
            """,
                (f"%{normalized_path}",),
            )
            routes = []
            for row in cursor.fetchall():
                routes.append(
                    {
                        "method": row["attribute_name"].upper(),
                        "path": row["args"],
                        "handler_function": row["target_name"],
                        "line": row["target_line"] or row["line"],
                    }
                )
            if routes:
                result["framework"] = "actix-web"
                result["routes"] = routes

        return result

    def get_file_findings_exact(self, file_path: str, limit: int = 20) -> list[dict]:
        """Get findings for exact file path (not LIKE pattern).

        Returns findings sorted by severity (critical first) then line number.
        """
        normalized = normalize_path_for_db(file_path)
        cursor = self.repo_db.cursor()

        cursor.execute(
            """
            SELECT file, line, rule, tool, message, severity, category, cwe
            FROM findings_consolidated
            WHERE file = ?
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5
                END,
                line
            LIMIT ?
            """,
            (normalized, limit),
        )

        return [
            {
                "file": row["file"],
                "line": row["line"],
                "rule": row["rule"],
                "tool": row["tool"],
                "message": row["message"],
                "severity": row["severity"],
                "category": row["category"],
                "cwe": row["cwe"],
            }
            for row in cursor.fetchall()
        ]

    def get_file_taint_flows(self, file_path: str, limit: int = 10) -> list[dict]:
        """Get taint flows involving this file (as source or sink)."""
        normalized = normalize_path_for_db(file_path)
        cursor = self.repo_db.cursor()

        cursor.execute(
            """
            SELECT source_file, source_line, source_pattern,
                   sink_file, sink_line, sink_pattern,
                   vulnerability_type, path_length
            FROM taint_flows
            WHERE source_file = ? OR sink_file = ?
            ORDER BY
                CASE vulnerability_type
                    WHEN 'SQL Injection' THEN 1
                    WHEN 'Command Injection' THEN 2
                    WHEN 'Path Traversal' THEN 3
                    ELSE 4
                END,
                path_length
            LIMIT ?
            """,
            (normalized, normalized, limit),
        )

        return [
            {
                "source_file": row["source_file"],
                "source_line": row["source_line"],
                "source_pattern": row["source_pattern"],
                "sink_file": row["sink_file"],
                "sink_line": row["sink_line"],
                "sink_pattern": row["sink_pattern"],
                "vulnerability_type": row["vulnerability_type"],
                "path_length": row["path_length"],
            }
            for row in cursor.fetchall()
        ]

    def get_file_context_bundle(
        self, file_path: str, limit: int = 20, include_issues: bool = True
    ) -> dict:
        """Aggregate all context for a file in one call.

        Args:
            file_path: Path to the file
            limit: Max items per section
            include_issues: If True, include findings and taint flows
        """
        query_limit = limit + 1
        result = {
            "target": file_path,
            "target_type": "file",
            "symbols": self.get_file_symbols(file_path, query_limit),
            "hooks": self.get_file_hooks(file_path),
            "imports": self.get_file_imports(file_path, query_limit),
            "importers": self.get_file_importers(file_path, query_limit),
            "outgoing_calls": self.get_file_outgoing_calls(file_path, query_limit),
            "incoming_calls": self.get_file_incoming_calls(file_path, query_limit),
            "framework_info": self.get_file_framework_info(file_path),
        }

        if include_issues:
            result["findings"] = self.get_file_findings_exact(file_path, query_limit)
            result["taint_flows"] = self.get_file_taint_flows(file_path, query_limit)

        return result

    def get_symbol_context_bundle(self, symbol_name: str, limit: int = 20, depth: int = 1) -> dict:
        """Aggregate all context for a symbol in one call."""

        resolved_names, error = self._resolve_symbol(symbol_name)
        if error:
            return {"error": error}

        definitions = self.find_symbol(resolved_names[0])
        if isinstance(definitions, dict) and "error" in definitions:
            return definitions

        definition = definitions[0] if definitions else None

        callers = self.get_callers(resolved_names[0], depth=depth)
        if isinstance(callers, dict) and "error" in callers:
            callers = []

        callees = self.get_callees(resolved_names[0])

        query_limit = limit + 1
        return {
            "target": symbol_name,
            "resolved_as": resolved_names,
            "target_type": "symbol",
            "definition": {
                "file": definition.file if definition else None,
                "line": definition.line if definition else None,
                "end_line": definition.end_line if definition else None,
                "type": definition.type if definition else None,
                "signature": definition.signature if definition else None,
            }
            if definition
            else None,
            "callers": [
                {
                    "file": c.caller_file,
                    "line": c.caller_line,
                    "caller_function": c.caller_function,
                    "callee_function": c.callee_function,
                }
                for c in (callers[:query_limit] if isinstance(callers, list) else [])
            ],
            "callees": [
                {
                    "file": c.caller_file,
                    "line": c.caller_line,
                    "callee_function": c.callee_function,
                }
                for c in (callees[:query_limit] if isinstance(callees, list) else [])
            ],
        }

    def close(self):
        """Close database connections."""
        if self.repo_db:
            self.repo_db.close()
        if self.graph_db:
            self.graph_db.close()
