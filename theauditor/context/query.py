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
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict
from collections import deque


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
    file: str  # CRITICAL: maps from symbols.path column!
    line: int
    end_line: int
    signature: Optional[str] = None
    is_exported: Optional[bool] = False
    framework_type: Optional[str] = None


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
    caller_function: Optional[str]
    callee_function: str
    arguments: List[str]


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
    symbols: Optional[List[str]] = None


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
        pf_dir = root / ".pf"

        # Validate repo_index.db exists (required)
        repo_db_path = pf_dir / "repo_index.db"
        if not repo_db_path.exists():
            raise FileNotFoundError(
                f"Database not found: {repo_db_path}\n"
                "Run 'aud index' first to build the database."
            )

        # Connect to repo_index.db (required)
        self.repo_db = sqlite3.connect(str(repo_db_path))
        self.repo_db.row_factory = sqlite3.Row  # Enable dict-like access

        # Connect to graphs.db (optional)
        graph_db_path = pf_dir / "graphs.db"
        if graph_db_path.exists():
            self.graph_db = sqlite3.connect(str(graph_db_path))
            self.graph_db.row_factory = sqlite3.Row
        else:
            self.graph_db = None  # Graph commands not run yet

    def find_symbol(self, name: str, type_filter: Optional[str] = None) -> List[SymbolInfo]:
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

        # Query both main and JSX tables
        for table in ['symbols', 'symbols_jsx']:
            # CRITICAL: symbols table uses 'path' column, not 'file'!
            query = f"""
                SELECT path, name, type, line, end_line, type_annotation, is_typed
                FROM {table}
                WHERE name = ?
            """
            params = [name]

            if type_filter:
                query += " AND type = ?"
                params.append(type_filter)

            try:
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    results.append(SymbolInfo(
                        name=row['name'],
                        type=row['type'],
                        file=row['path'],  # Map path -> file
                        line=row['line'],
                        end_line=row['end_line'] or row['line'],
                        signature=row['type_annotation'],
                        is_exported=bool(row['is_typed']) if row['is_typed'] is not None else False,
                        framework_type=None  # Not in current schema
                    ))
            except sqlite3.OperationalError:
                # Table might not exist (e.g., no JSX in Python projects)
                continue

        return results

    def get_callers(self, symbol_name: str, depth: int = 1) -> List[CallSite]:
        """Find who calls a symbol (with optional transitive search).

        Direct query on function_call_args table.
        For depth > 1, recursively finds callers of callers using BFS.

        Args:
            symbol_name: Symbol to find callers for
            depth: Traversal depth (1-5, default=1)

        Returns:
            List of call sites with full context

        Raises:
            ValueError: If depth < 1 or depth > 5

        Example:
            # Direct callers
            callers = engine.get_callers("validateInput", depth=1)

            # Transitive callers (3 levels deep)
            callers = engine.get_callers("validateInput", depth=3)
        """
        if depth < 1 or depth > 5:
            raise ValueError("Depth must be between 1 and 5")

        cursor = self.repo_db.cursor()
        all_callers = []
        visited = set()

        # BFS for transitive callers
        queue = deque([(symbol_name, 0)])

        while queue:
            current_symbol, current_depth = queue.popleft()

            if current_depth >= depth:
                continue

            # Query both regular and JSX call tables
            for table in ['function_call_args', 'function_call_args_jsx']:
                query = f"""
                    SELECT DISTINCT
                        file, line, caller_function, callee_function, argument_expr
                    FROM {table}
                    WHERE callee_function = ?
                    ORDER BY file, line
                """

                try:
                    cursor.execute(query, (current_symbol,))

                    for row in cursor.fetchall():
                        call_site = CallSite(
                            caller_file=row['file'],
                            caller_line=row['line'],
                            caller_function=row['caller_function'],
                            callee_function=row['callee_function'],
                            arguments=[row['argument_expr']] if row['argument_expr'] else []
                        )

                        # Track unique callers (avoid duplicates)
                        caller_key = (
                            call_site.caller_function,
                            call_site.caller_file,
                            call_site.caller_line
                        )

                        if caller_key not in visited:
                            visited.add(caller_key)
                            all_callers.append(call_site)

                            # Add to queue for next depth level
                            if current_depth + 1 < depth and call_site.caller_function:
                                queue.append((call_site.caller_function, current_depth + 1))

                except sqlite3.OperationalError:
                    # Table might not exist (e.g., no JSX in Python projects)
                    continue

        return all_callers

    def get_callees(self, symbol_name: str) -> List[CallSite]:
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

        # Query both regular and JSX call tables
        for table in ['function_call_args', 'function_call_args_jsx']:
            query = f"""
                SELECT DISTINCT
                    file, line, caller_function, callee_function, argument_expr
                FROM {table}
                WHERE caller_function LIKE ?
                ORDER BY line
            """

            try:
                cursor.execute(query, (f'%{symbol_name}%',))

                for row in cursor.fetchall():
                    callees.append(CallSite(
                        caller_file=row['file'],
                        caller_line=row['line'],
                        caller_function=row['caller_function'],
                        callee_function=row['callee_function'],
                        arguments=[row['argument_expr']] if row['argument_expr'] else []
                    ))

            except sqlite3.OperationalError:
                # Table might not exist
                continue

        return callees

    def get_file_dependencies(
        self,
        file_path: str,
        direction: str = 'both'
    ) -> Dict[str, List[Dependency]]:
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
            return {
                'error': 'Graph database not found. Run: aud graph build'
            }

        cursor = self.graph_db.cursor()
        result = {}

        if direction in ['incoming', 'both']:
            # Who imports this file?
            cursor.execute("""
                SELECT source, target, type, line
                FROM edges
                WHERE target LIKE ? AND graph_type = 'import'
                ORDER BY source
            """, (f'%{file_path}%',))

            result['incoming'] = [
                Dependency(
                    source_file=row['source'],
                    target_file=row['target'],
                    import_type=row['type'],
                    line=row['line'] or 0,
                    symbols=[]
                )
                for row in cursor.fetchall()
            ]

        if direction in ['outgoing', 'both']:
            # What does this file import?
            cursor.execute("""
                SELECT source, target, type, line
                FROM edges
                WHERE source LIKE ? AND graph_type = 'import'
                ORDER BY target
            """, (f'%{file_path}%',))

            result['outgoing'] = [
                Dependency(
                    source_file=row['source'],
                    target_file=row['target'],
                    import_type=row['type'],
                    line=row['line'] or 0,
                    symbols=[]
                )
                for row in cursor.fetchall()
            ]

        return result

    def get_api_handlers(self, route_pattern: str) -> List[Dict]:
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
        cursor = self.repo_db.cursor()

        cursor.execute("""
            SELECT file, line, method, pattern, path, controls, has_auth, handler_function
            FROM api_endpoints
            WHERE path LIKE ? OR pattern LIKE ?
            ORDER BY path, method
        """, (f'%{route_pattern}%', f'%{route_pattern}%'))

        return [dict(row) for row in cursor.fetchall()]

    def get_component_tree(self, component_name: str) -> Dict:
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

        # Component definition
        try:
            cursor.execute("""
                SELECT file, name, type, start_line, end_line, has_jsx, hooks_used, props_type
                FROM react_components
                WHERE name = ?
            """, (component_name,))

            row = cursor.fetchone()
            if not row:
                return {'error': f'Component not found: {component_name}'}

            result = dict(row)

            # Hooks used (parse JSON if stored as JSON string)
            import json
            if result.get('hooks_used'):
                try:
                    result['hooks'] = json.loads(result['hooks_used'])
                except (json.JSONDecodeError, TypeError):
                    result['hooks'] = []
            else:
                result['hooks'] = []

            # Child components (components this one renders)
            try:
                cursor.execute("""
                    SELECT DISTINCT callee_function as child_component, line
                    FROM function_call_args_jsx
                    WHERE file = ? AND callee_function IN (SELECT name FROM react_components)
                    ORDER BY line
                """, (result['file'],))
                result['children'] = [dict(r) for r in cursor.fetchall()]
            except sqlite3.OperationalError:
                result['children'] = []

            return result

        except sqlite3.OperationalError:
            return {'error': 'react_components table not found. Project may not use React.'}

    def get_data_dependencies(self, symbol_name: str) -> Dict[str, List[Dict]]:
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

        try:
            # Variables WRITTEN by this function
            cursor.execute("""
                SELECT target_var, source_expr, line, file
                FROM assignments
                WHERE in_function = ?
                ORDER BY line
            """, (symbol_name,))

            writes = []
            for row in cursor.fetchall():
                writes.append({
                    'variable': row['target_var'],
                    'expression': row['source_expr'],
                    'line': row['line'],
                    'file': row['file']
                })

            # Variables READ by this function (normalized query, NO JSON PARSING)
            cursor.execute("""
                SELECT DISTINCT asrc.source_var_name
                FROM assignments a
                JOIN assignment_sources asrc
                    ON a.file = asrc.assignment_file
                    AND a.line = asrc.assignment_line
                    AND a.target_var = asrc.assignment_target
                WHERE a.in_function = ?
            """, (symbol_name,))

            all_reads = {row['source_var_name'] for row in cursor.fetchall() if row['source_var_name']}

            # Deduplicate and sort reads
            reads = [{'variable': var} for var in sorted(all_reads)]

            return {
                'reads': reads,
                'writes': writes
            }

        except sqlite3.OperationalError as e:
            if 'no such table' in str(e):
                return {
                    'error': 'assignments table not found. Run: aud index'
                }
            raise  # Re-raise unexpected errors

    def get_findings(
        self,
        file_path: Optional[str] = None,
        tool: Optional[str] = None,
        severity: Optional[str] = None,
        rule: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict]:
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

        try:
            where_clauses = []
            params = []

            if file_path:
                where_clauses.append("file LIKE ?")
                params.append(f'%{file_path}%')

            if tool:
                where_clauses.append("tool = ?")
                params.append(tool)

            if severity:
                where_clauses.append("severity = ?")
                params.append(severity)

            if rule:
                where_clauses.append("rule LIKE ?")
                params.append(f'%{rule}%')

            if category:
                where_clauses.append("category = ?")
                params.append(category)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            cursor.execute(f"""
                SELECT file, line, column, rule, tool, message, severity,
                       category, confidence, cwe, details_json
                FROM findings_consolidated
                WHERE {where_sql}
                ORDER BY severity DESC, file, line
                LIMIT 1000
            """, params)

            findings = []
            for row in cursor.fetchall():
                finding = {
                    'file': row['file'],
                    'line': row['line'],
                    'column': row['column'],
                    'rule': row['rule'],
                    'tool': row['tool'],
                    'message': row['message'],
                    'severity': row['severity'],
                    'category': row['category'],
                    'confidence': row['confidence'],
                    'cwe': row['cwe']
                }

                # Parse details_json if present
                if row['details_json']:
                    import json
                    try:
                        finding['details'] = json.loads(row['details_json'])
                    except (json.JSONDecodeError, TypeError):
                        # Malformed JSON - skip details field
                        pass

                findings.append(finding)

            return findings

        except sqlite3.OperationalError as e:
            if 'no such table' in str(e):
                # Graceful degradation with helpful message
                return [{
                    'error': 'findings_consolidated table not found',
                    'message': 'Run "aud full" first to generate findings',
                    'hint': 'The findings table is created during pattern detection and taint analysis'
                }]
            raise  # Re-raise unexpected errors

    def close(self):
        """Close database connections.

        Call this when done to release resources.
        """
        if self.repo_db:
            self.repo_db.close()
        if self.graph_db:
            self.graph_db.close()
