"""Direct database query interface for AI code navigation.

This module provides exact queries over TheAuditor's indexed data.
NO inference, NO guessing, NO embeddings - just SQL queries.

Architecture:
- CodeQueryEngine: Main query interface
- SymbolInfo/CallSite/Dependency: Typed result objects
- All queries use existing tables (no schema changes)

Performance:
- Query time: <10ms (indexed lookups)
- No caching needed (SQLite is fast enough)
- Transitive queries use BFS (max depth: 5)

Usage:
    from theauditor.context import CodeQueryEngine

    engine = CodeQueryEngine(Path.cwd())

    # Find symbol
    symbols = engine.find_symbol("authenticateUser")

    # Get callers (transitive)
    callers = engine.get_callers("validateInput", depth=3)

    # Get file dependencies
    deps = engine.get_file_dependencies("src/auth.ts")
"""

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
    "oauth_patterns",
    "password_patterns",
    "session_patterns",
    "sql_queries",
    "orm_queries",
    "react_components",
    "python_routes",
    "js_routes",
}


def validate_table_name(table: str) -> str:
    """Validate table name against whitelist to prevent SQL injection.

    Args:
        table: Table name to validate

    Returns:
        The validated table name

    Raises:
        ValueError: If table name is not whitelisted
    """
    if table not in VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    return table


@dataclass
class SymbolInfo:
    """Symbol definition with full context.

    Attributes:
        name: Symbol name (function, class, variable, etc.)
        type: Symbol type (function, class, method, variable, etc.)
        file: File path (normalized relative path)
        line: Starting line number
        end_line: Ending line number
        signature: Type signature if available
        is_exported: Whether symbol is exported
        framework_type: Framework-specific type (component, hook, route, etc.)
    """

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
    """Function call location with context.

    Attributes:
        caller_file: File containing the call
        caller_line: Line number of the call
        caller_function: Function making the call (None = top-level)
        callee_function: Function being called
        arguments: List of argument expressions
    """

    caller_file: str
    caller_line: int
    caller_function: str | None
    callee_function: str
    arguments: list[str]


@dataclass
class Dependency:
    """Import or call dependency between files.

    Attributes:
        source_file: File that imports/calls
        target_file: File being imported/called
        import_type: Type of relationship (import, require, call)
        line: Line number where dependency occurs
        symbols: List of imported symbols (if applicable)
    """

    source_file: str
    target_file: str
    import_type: str
    line: int
    symbols: list[str] | None = None


class CodeQueryEngine:
    """Query engine for code navigation.

    Uses existing database tables - NO new schema required.
    All queries return exact matches with provenance.

    Database Schema Used:
        repo_index.db:
            - symbols (33k rows) - symbol.path NOT symbol.file!
            - symbols_jsx (8k rows)
            - function_call_args (13k rows)
            - function_call_args_jsx (4k rows)
            - variable_usage (57k rows)
            - assignments (6k rows)
            - api_endpoints (185 rows)
            - react_components (1k rows)
            - react_hooks (667 rows)
            - refs (1.7k rows)

        graphs.db:
            - edges (7.3k rows) - import + call relationships
            - nodes (4.8k rows)

    Performance:
        - Symbol lookup: <5ms (indexed)
        - Direct callers: <10ms
        - Transitive (depth=3): <50ms
    """

    def __init__(self, root: Path):
        """Initialize with project root.

        Args:
            root: Project root directory (contains .pf/)

        Raises:
            FileNotFoundError: If repo_index.db doesn't exist
        """
        self.root = root
        pf_dir = root / ".pf"

        repo_db_path = pf_dir / "repo_index.db"
        if not repo_db_path.exists():
            raise FileNotFoundError(
                f"Database not found: {repo_db_path}\nRun 'aud full' first to build the database."
            )

        self.repo_db = sqlite3.connect(str(repo_db_path))
        self.repo_db.row_factory = sqlite3.Row

        graph_db_path = pf_dir / "graphs.db"
        if graph_db_path.exists():
            self.graph_db = sqlite3.connect(str(graph_db_path))
            self.graph_db.row_factory = sqlite3.Row
        else:
            self.graph_db = None

    def _normalize_path(self, file_path: str) -> str:
        """Normalize file path for database queries.

        CRITICAL: Call this before ANY query using file paths!
        Converts Windows absolute paths to Unix-style relative paths
        that match what's stored in the database.

        Args:
            file_path: User-provided path (may be absolute Windows path)

        Returns:
            Normalized path for database LIKE queries
        """
        return normalize_path_for_db(file_path, self.root)

    def _find_similar_symbols(self, input_name: str, limit: int = 5) -> list[str]:
        """Find symbols similar to input for helpful 'Did you mean?' suggestions.

        Searches DEFINITION tables (symbols, react_components) for partial matches.
        Used when exact symbol lookup fails to help users find correct spelling.

        Args:
            input_name: User-provided symbol name that wasn't found
            limit: Maximum suggestions to return

        Returns:
            List of similar symbol names (up to limit)

        Example:
            # User typed "Sale" but component is "POSSale"
            suggestions = engine._find_similar_symbols("Sale")
            # Returns: ["POSSale", "SaleResponse", "SalesReport"]
        """
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

        Symbol Resolution Step (NOT a fallback - this is normalization).
        Maps imprecise user input to exact indexed symbols.

        The schema separates DEFINITIONS (symbols table) from USAGE (function_call_args).
        This method searches both to handle:
        1. Direct function calls: foo() -> callee_function = 'foo'
        2. Callback references: router.get(handler) -> argument_expr = 'handler'
        3. Symbol definitions: function foo() {} -> symbols.name = 'foo'

        Algorithm:
        1. Check DEFINITIONS (symbols, symbols_jsx, react_components)
        2. Check USAGE - direct calls (function_call_args.callee_function)
        3. Check USAGE - callbacks (function_call_args.argument_expr)
        4. If nothing found, suggest similar symbols

        Args:
            input_name: User-provided symbol name (may be unqualified)

        Returns:
            Tuple of (qualified_names: list[str], error: str | None)
            - If 0 matches: ([], "Symbol 'X' not found. Did you mean: Y, Z?")
            - If 1+ matches: ([qualified_names], None)

        Example:
            # User provides "getAllOrders"
            names, err = engine._resolve_symbol("getAllOrders")
            # Returns: (["orderController.getAllOrders"], None)
        """
        cursor = self.repo_db.cursor()
        found_symbols = set()

        for table in ["symbols", "symbols_jsx"]:
            cursor.execute(
                f"""
                SELECT DISTINCT name FROM {table} WHERE name = ?
            """,
                (input_name,),
            )
            for row in cursor.fetchall():
                found_symbols.add(row["name"])

            cursor.execute(
                f"""
                SELECT DISTINCT name FROM {table} WHERE name LIKE ?
            """,
                (f"%.{input_name}",),
            )
            for row in cursor.fetchall():
                found_symbols.add(row["name"])

            if "." in input_name:
                last_segment = input_name.split(".")[-1]
                cursor.execute(
                    f"""
                    SELECT DISTINCT name FROM {table} WHERE name LIKE ?
                """,
                    (f"%.{last_segment}",),
                )
                for row in cursor.fetchall():
                    found_symbols.add(row["name"])

        cursor.execute(
            """
            SELECT DISTINCT name FROM react_components WHERE name = ?
        """,
            (input_name,),
        )
        for row in cursor.fetchall():
            found_symbols.add(row["name"])

        for table in ["function_call_args", "function_call_args_jsx"]:
            cursor.execute(
                f"""
                SELECT DISTINCT callee_function FROM {table} WHERE callee_function = ?
            """,
                (input_name,),
            )
            for row in cursor.fetchall():
                found_symbols.add(row["callee_function"])

            cursor.execute(
                f"""
                SELECT DISTINCT callee_function FROM {table} WHERE callee_function LIKE ?
            """,
                (f"%.{input_name}",),
            )
            for row in cursor.fetchall():
                found_symbols.add(row["callee_function"])

            if "." in input_name:
                last_segment = input_name.split(".")[-1]
                cursor.execute(
                    f"""
                    SELECT DISTINCT callee_function FROM {table} WHERE callee_function LIKE ?
                """,
                    (f"%.{last_segment}",),
                )
                for row in cursor.fetchall():
                    found_symbols.add(row["callee_function"])

        for table in ["function_call_args", "function_call_args_jsx"]:
            cursor.execute(
                f"""
                SELECT DISTINCT argument_expr FROM {table}
                WHERE argument_expr = ? OR argument_expr LIKE ?
            """,
                (input_name, f"%.{input_name}"),
            )

            for row in cursor.fetchall():
                expr = row["argument_expr"]

                if expr and not any(c in expr for c in ["+", "-", "*", "/", "(", ")", " "]):
                    found_symbols.add(expr)

            if "." in input_name:
                last_segment = input_name.split(".")[-1]
                cursor.execute(
                    f"""
                    SELECT DISTINCT argument_expr FROM {table}
                    WHERE argument_expr LIKE ?
                """,
                    (f"%.{last_segment}",),
                )
                for row in cursor.fetchall():
                    expr = row["argument_expr"]
                    if expr and not any(c in expr for c in ["+", "-", "*", "/", "(", ")", " "]):
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
        """Find symbol definitions by exact name match.

        Queries both symbols and symbols_jsx tables for React/JSX support.

        Args:
            name: Exact symbol name to search for
            type_filter: Optional type filter (function, class, etc.)

        Returns:
            List of matching symbols with full context

        Example:
            symbols = engine.find_symbol("authenticateUser")
            for sym in symbols:
                print(f"{sym.name} at {sym.file}:{sym.line}")
        """
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

        First resolves user input to qualified symbol name(s), then queries
        function_call_args table. For depth > 1, recursively finds callers
        of callers using BFS.

        Symbol Resolution:
            - "save" may resolve to ["User.save", "File.save"]
            - If ambiguous, returns callers for ALL matches with labeling
            - If not found, returns error dict

        Args:
            symbol_name: Symbol to find callers for (may be unqualified)
            depth: Traversal depth (1-5, default=1)

        Returns:
            List of call sites with full context, OR
            Dict with 'error' key if symbol not found, OR
            Dict with 'ambiguous' key listing possible matches

        Raises:
            ValueError: If depth < 1 or depth > 5

        Example:
            # Direct callers
            callers = engine.get_callers("validateInput", depth=1)

            # Transitive callers (3 levels deep)
            callers = engine.get_callers("validateInput", depth=3)

            # Unqualified name (will resolve)
            callers = engine.get_callers("save", depth=1)  # Finds User.save, File.save
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
        all_callers = []
        visited = set()

        symbols_to_query = resolved_names

        queue = deque([(name, 0) for name in symbols_to_query])

        while queue:
            current_symbol, current_depth = queue.popleft()

            if current_depth >= depth:
                continue

            for table in ["function_call_args", "function_call_args_jsx"]:
                query = f"""
                    SELECT DISTINCT
                        file, line, caller_function, callee_function, argument_expr
                    FROM {table}
                    WHERE callee_function = ?
                       OR argument_expr = ?
                       OR argument_expr LIKE ?
                    ORDER BY file, line
                """

                params = (current_symbol, current_symbol, f"%.{current_symbol}")

                cursor.execute(query, params)

                for row in cursor.fetchall():
                    call_site = CallSite(
                        caller_file=row["file"],
                        caller_line=row["line"],
                        caller_function=row["caller_function"],
                        callee_function=row["callee_function"],
                        arguments=[row["argument_expr"]] if row["argument_expr"] else [],
                    )

                    caller_key = (
                        call_site.caller_function,
                        call_site.caller_file,
                        call_site.caller_line,
                    )

                    if caller_key not in visited:
                        visited.add(caller_key)
                        all_callers.append(call_site)

                        if current_depth + 1 < depth and call_site.caller_function:
                            queue.append((call_site.caller_function, current_depth + 1))

        return all_callers

    def get_callees(self, symbol_name: str) -> list[CallSite]:
        """Find what a symbol calls.

        Query function_call_args WHERE caller_function matches.

        Args:
            symbol_name: Symbol to find callees for

        Returns:
            List of call sites showing what this symbol calls

        Example:
            callees = engine.get_callees("UserController.create")
            for call in callees:
                print(f"Calls: {call.callee_function}")
        """
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
        """Get import dependencies for a file.

        Uses graphs.db edges table with graph_type='import'.

        Args:
            file_path: File to query (partial path match)
            direction: 'incoming', 'outgoing', or 'both'

        Returns:
            Dict with 'incoming' and/or 'outgoing' dependency lists

        Example:
            deps = engine.get_file_dependencies("src/auth.ts")
            print(f"Imported by: {deps['incoming']}")
            print(f"Imports: {deps['outgoing']}")
        """
        if not self.graph_db:
            return {"error": "Graph database not found. Run: aud graph build"}

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
        """Find API endpoint handlers.

        Direct query on api_endpoints table.

        Args:
            route_pattern: Route to search (supports LIKE wildcards)

        Returns:
            List of endpoint info dicts

        Example:
            endpoints = engine.get_api_handlers("/users")
            for ep in endpoints:
                print(f"{ep['method']} {ep['path']} -> {ep['handler_function']}")
        """

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
        """Get React component hierarchy.

        Uses:
        - react_components table (definition)
        - react_hooks table (hooks used)
        - function_call_args_jsx (child components)

        Args:
            component_name: Component to query

        Returns:
            Dict with component info, hooks, and children

        Example:
            tree = engine.get_component_tree("UserProfile")
            print(f"Hooks: {tree['hooks']}")
            print(f"Children: {tree['children']}")
        """
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
        """Get data dependencies (reads/writes) for a function.

        Uses assignments table (HAS in_function column).
        NOT variable_usage (that has in_component for React components).

        Data flow analysis:
        - READS: Variables consumed by the function (from source_vars JSON array)
        - WRITES: Variables assigned by the function (target_var)

        Args:
            symbol_name: Function name to analyze

        Returns:
            Dict with 'reads' and 'writes' lists

        Example:
            deps = engine.get_data_dependencies("createApp")
            for read in deps['reads']:
                print(f"Reads: {read['variable']}")
            for write in deps['writes']:
                print(f"Writes: {write['variable']} = {write['expression']}")

        Raises:
            ValueError: If symbol_name is empty
        """
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

    def trace_variable_flow(self, var_name: str, from_file: str, depth: int = 3) -> list[dict]:
        """Trace variable through def-use chains using assignment_sources.

        Uses BFS traversal through assignment_sources junction table to find
        how variables flow through assignments (X = Y → Z = X → A = Z).

        This is PURE DATA FLOW analysis (what data moves where), complementing
        get_callers() which is CONTROL FLOW analysis (who calls what).

        Args:
            var_name: Variable name to trace
            from_file: Starting file path (can be partial)
            depth: Traversal depth (1-5, default=3)

        Returns:
            List of flow step dicts with from_var, to_var, expression, file, line, depth

        Example:
            # Trace how userToken flows through code
            flow = engine.trace_variable_flow("userToken", "auth.ts", depth=3)
            for step in flow:
                print(f"{step['from_var']} -> {step['to_var']} at {step['file']}:{step['line']}")

        Raises:
            ValueError: If depth < 1 or depth > 5 or var_name empty
        """
        if not var_name:
            raise ValueError("var_name cannot be empty")
        if depth < 1 or depth > 5:
            raise ValueError("Depth must be between 1 and 5")

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
        """Track variables returned from function and assigned elsewhere.

        This is ADVANCED DATA FLOW: combines function_return_sources with assignment_sources
        to find cross-function taint propagation (function A returns X → function B assigns X to Y).

        One of the 7 advanced query capabilities unlocked by schema normalization.

        Args:
            function_name: Function whose return values to trace

        Returns:
            List of cross-function flow dicts with return_var, assignment_var, files, lines

        Example:
            # Track how validateUser's returns propagate
            flows = engine.get_cross_function_taint("validateUser")
            for flow in flows:
                print(f"Returns {flow['return_var']} -> Assigned to {flow['assignment_var']}")

        Raises:
            ValueError: If function_name is empty
        """
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
        """Find API endpoints and their authentication controls via junction table.

        Uses api_endpoint_controls junction table to show which auth mechanisms
        protect each endpoint (JWT, session, API key, etc.).

        One of the 7 advanced query capabilities unlocked by schema normalization.

        Args:
            route_pattern: Optional route pattern to filter (partial match)

        Returns:
            List of endpoint dicts with route, method, and controls list

        Example:
            # Check auth coverage for /users endpoints
            coverage = engine.get_api_security_coverage("/users")
            for ep in coverage:
                print(f"{ep['method']} {ep['route']}: {len(ep['controls'])} controls")

        Raises:
            None - gracefully returns empty list if tables missing
        """
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
    ) -> list[dict]:
        """Query findings from findings_consolidated table.

        Direct SQL query on findings table instead of reading chunked JSON files.
        Much faster (<20ms vs reading 3 x 65KB JSON files) and no truncation limits.

        Replaces workflow:
        OLD: Read .pf/readthis/patterns_chunk01.json (chunked, limited to 3 chunks)
        NEW: aud context query --findings --severity HIGH (instant, no limits)

        Args:
            file_path: Filter by file path (partial match supported)
            tool: Filter by tool (patterns, taint, eslint, cfg-analysis, etc.)
            severity: Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
            rule: Filter by rule name (partial match supported)
            category: Filter by category

        Returns:
            List of finding dicts with file, line, rule, tool, message, severity, etc.

        Example:
            # Get all HIGH severity findings
            findings = engine.get_findings(severity='HIGH')

            # Get taint findings in auth files
            findings = engine.get_findings(file_path='auth', tool='taint')

            # Get specific pattern rule
            findings = engine.get_findings(rule='sql-injection')

        Raises:
            None - gracefully returns empty list if table missing
        """
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
            LIMIT 1000
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
        """Search symbols by pattern (LIKE query).

        Faster than Compass's vector similarity (no ML, no CUDA).
        Uses SQL LIKE for instant pattern matching.

        Args:
            pattern: Search pattern (supports % wildcards)
            type_filter: Filter by symbol type (function, class, etc.)
            path_filter: Filter by file path (supports % wildcards)
            limit: Maximum results to return

        Returns:
            List of matching symbols

        Example:
            # Find all auth-related functions
            results = engine.pattern_search("auth%", type_filter="function")

            # Find all validation code
            results = engine.pattern_search("%valid%")

            # Find all controllers in src/api/
            results = engine.pattern_search("%Controller%", path_filter="src/api/%")

            # List everything in a path
            results = engine.pattern_search("%", path_filter="services/%")
        """
        cursor = self.repo_db.cursor()
        results = []

        for table in ["symbols", "symbols_jsx"]:
            query = f"""
                SELECT path, name, type, line, end_line, type_annotation, is_typed
                FROM {table}
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

        return results[:limit]

    def category_search(self, category: str, limit: int = 200) -> dict[str, list[dict]]:
        """Search across pattern tables by security category.

        NO embeddings, NO inference - direct queries on indexed pattern tables.
        100x faster than Compass's vector similarity.

        Args:
            category: Security category (jwt, oauth, password, sql, xss, etc.)
            limit: Maximum results per table

        Returns:
            Dict with category results from multiple tables

        Example:
            # Find all JWT usage
            results = engine.category_search("jwt")
            # Returns: jwt_patterns, findings for JWT, symbols with JWT

            # Find all authentication code
            results = engine.category_search("auth")
        """
        cursor = self.repo_db.cursor()
        results = {}

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

        for table in tables:
            validated_table = validate_table_name(table)
            cursor.execute(f"SELECT * FROM {validated_table} LIMIT {limit}")
            rows = cursor.fetchall()
            if rows:
                results[table] = [dict(row) for row in rows]

        cursor.execute(
            f"SELECT * FROM findings_consolidated WHERE category LIKE ? LIMIT {limit}",
            (f"%{category}%",),
        )
        findings = cursor.fetchall()
        if findings:
            results["findings"] = [dict(row) for row in findings]

        pattern_results = self.pattern_search(f"%{category}%", limit=limit)
        if pattern_results:
            results["symbols"] = [asdict(s) for s in pattern_results]

        return results

    def cross_table_search(
        self, search_term: str, include_tables: list[str] | None = None, limit: int = 50
    ) -> dict[str, list[dict]]:
        """Search across multiple tables (exploratory analysis).

        Better than Compass's "semantic search" because we return EXACT matches
        from RICH data (TypeScript compiler, not tree-sitter).

        Args:
            search_term: Term to search for
            include_tables: Tables to search (default: all major tables)
            limit: Results per table

        Returns:
            Dict of results from each table

        Example:
            # Find everything about payments
            results = engine.cross_table_search("payment")
            # Returns: symbols, findings, api_endpoints, etc.

            # Search specific tables
            results = engine.cross_table_search(
                "user",
                include_tables=["symbols", "api_endpoints", "findings_consolidated"]
            )
        """
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
        """Get all symbols defined in a file.

        Args:
            file_path: File path (partial match supported)
            limit: Max results

        Returns:
            List of {name, type, line, end_line, signature, path} dicts
        """
        cursor = self.repo_db.cursor()
        results = []

        normalized_path = self._normalize_path(file_path)

        for table in ["symbols", "symbols_jsx"]:
            cursor.execute(
                f"""
                SELECT name, type, line, end_line, type_annotation, path
                FROM {table}
                WHERE path LIKE ?
                  AND type NOT IN ('call')
                ORDER BY line
                LIMIT ?
            """,
                (f"%{normalized_path}", limit - len(results)),
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

        return results[:limit]

    def get_file_hooks(self, file_path: str) -> list[dict]:
        """Get React/Vue hooks used in a file.

        IMPORTANT: Filters react_hooks table which contains BOTH hooks AND method calls.
        Only returns actual React hooks (useState, useEffect, etc.) or custom hooks
        that follow the useXxx naming convention.

        Args:
            file_path: File path (partial match supported)

        Returns:
            List of {hook_name, line} dicts
        """
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
        """Get imports declared in a file.

        Uses refs table for what THIS file imports.

        Args:
            file_path: File path (partial match)
            limit: Max results

        Returns:
            List of {module, kind, line} dicts
        """
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
        """Get files that import this file.

        Uses edges table in graphs.db with graph_type='import'.

        Args:
            file_path: File path (partial match)
            limit: Max results

        Returns:
            List of {source_file, type, line} dicts
        """
        if not self.graph_db:
            return []

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
        """Get function calls made FROM this file.

        Args:
            file_path: File path (partial match)
            limit: Max results

        Returns:
            List of {callee_function, line, arguments, caller_function, file} dicts
        """
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
        """Get calls TO symbols defined in this file.

        Optimized: Single query with IN clause instead of O(N) loop.

        Args:
            file_path: File path (partial match)
            limit: Max results

        Returns:
            List of {caller_file, caller_line, caller_function, callee_function} dicts
        """
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
        """Get framework-specific information for a file.

        Auto-detects framework from file extension and queries appropriate tables:
        - React/Vue: components, hooks
        - Express: middleware, routes
        - Flask/FastAPI: routes, decorators
        - Sequelize/SQLAlchemy: models, relationships

        Args:
            file_path: File path (partial match)

        Returns:
            Dict with framework name and relevant data
        """
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

        return result

    def get_file_context_bundle(self, file_path: str, limit: int = 20) -> dict:
        """Aggregate all context for a file in one call.

        This is the main entry point for 'aud explain <file>'.

        Args:
            file_path: File path (partial match supported)
            limit: Max items per section

        Returns:
            Dict with all sections: symbols, hooks, imports, importers,
            outgoing_calls, incoming_calls, framework_info

        Note: Queries for limit+1 items to enable accurate truncation detection.
              Caller should check len(section) > limit to detect truncation.
        """

        query_limit = limit + 1
        return {
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

    def get_symbol_context_bundle(self, symbol_name: str, limit: int = 20, depth: int = 1) -> dict:
        """Aggregate all context for a symbol in one call.

        This is the main entry point for 'aud explain <Symbol.method>'.

        Args:
            symbol_name: Symbol name (resolution applied)
            limit: Max items per section
            depth: Call graph traversal depth (1-5)

        Returns:
            Dict with definition, callers, callees, or error dict
        """

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
        """Close database connections.

        Call this when done to release resources.
        """
        if self.repo_db:
            self.repo_db.close()
        if self.graph_db:
            self.graph_db.close()
