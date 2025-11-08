"""IFDS-based taint analyzer using pre-computed graphs.

This module implements demand-driven backward taint analysis using the IFDS
framework adapted from "IFDS Taint Analysis with Access Paths" (Allen et al., 2021).

Key differences from paper:
- Uses pre-computed graphs.db instead of on-the-fly graph construction
- Database-first (no SSA/φ-nodes, works with normalized AST data)
- Multi-language (Python, JS, TS via extractors)

Architecture:
    Sources → [Backward IFDS] → Sinks
              ↓
    graphs.db (DFG + Call Graph)
              ↓
    5-10 hop cross-file flows

Performance: O(CallD³ + 2ED²) - h-sparse IFDS (page 10, Table 3)
"""

from __future__ import annotations  # Defer evaluation of type annotations
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any, TYPE_CHECKING
from collections import deque, defaultdict

from .access_path import AccessPath

# Avoid circular import: core.py imports ifds_analyzer, ifds_analyzer imports core
# TaintPath is only used for type hints, so we can defer the import
if TYPE_CHECKING:
    from .core import TaintPath


class IFDSTaintAnalyzer:
    """Demand-driven taint analyzer using IFDS backward reachability.

    Uses pre-computed graphs from DFGBuilder and PathCorrelator instead of
    rebuilding data flow on every run.
    """

    def __init__(self, repo_db_path: str, graph_db_path: str, cache=None, registry=None):
        """Initialize IFDS analyzer with database connections.

        Args:
            repo_db_path: Path to repo_index.db (CFG, symbols, assignments)
            graph_db_path: Path to graphs.db (DFG, call graph)
            cache: Optional memory cache for performance
            registry: Optional TaintRegistry for sanitizer checking
        """
        self.repo_conn = sqlite3.connect(repo_db_path)
        self.repo_conn.row_factory = sqlite3.Row
        self.repo_cursor = self.repo_conn.cursor()

        self.graph_conn = sqlite3.connect(graph_db_path)
        self.graph_conn.row_factory = sqlite3.Row
        self.graph_cursor = self.graph_conn.cursor()

        self.cache = cache
        self.registry = registry

        # Function summaries: (func_name, file) -> {param_path: [return_paths]}
        self.summaries: Dict[Tuple[str, str], Dict[str, Set[str]]] = {}

        # Visited nodes for cycle detection
        self.visited: Set[Tuple[str, str]] = set()

        self.max_depth = 10  # 10-hop max
        self.max_paths_per_sink = 100

        self.debug = False  # Set via env var

        # Load safe sinks (sanitizers) from database
        self._load_safe_sinks()

    def analyze_sink_to_sources(self, sink: Dict, sources: List[Dict],
                                max_depth: int = 10) -> List[TaintPath]:
        """Find all taint paths from sink to sources using IFDS backward analysis.

        Algorithm (IFDS paper - demand-driven):
        1. Start at sink (backward analysis is demand-driven from sinks)
        2. Query graphs.db for data dependencies (backward edges)
        3. Follow edges backward through assignments, calls, returns
        4. Check if path reaches ANY source (early termination)
        5. Build TaintPath with full hop chain

        Args:
            sink: Security sink dict (file, line, pattern, name)
            sources: List of taint source dicts
            max_depth: Maximum hops (default 10)

        Returns:
            List of TaintPath objects with 5-10 hop cross-file flows
        """
        self.max_depth = max_depth
        all_paths = []

        # Parse all sources as AccessPaths for matching
        source_aps = []
        for source in sources:
            source_ap = self._dict_to_access_path(source)
            if source_ap:
                source_aps.append((source, source_ap))

        if not source_aps:
            return []

        if self.debug:
            print(f"\n[IFDS] Analyzing sink: {sink.get('pattern', '?')}", file=sys.stderr)
            print(f"[IFDS] Checking against {len(source_aps)} sources", file=sys.stderr)

        # Trace backward from sink, checking if ANY source is reachable
        paths = self._trace_backward_to_any_source(sink, source_aps, max_depth)
        all_paths.extend(paths)

        if self.debug and all_paths:
            print(f"[IFDS] Found {len(all_paths)} paths", file=sys.stderr)

        return all_paths

    def _trace_backward_to_any_source(self, sink: Dict, source_aps: List[Tuple[Dict, AccessPath]],
                                      max_depth: int) -> List[TaintPath]:
        """Backward trace from sink, checking if ANY source is reachable.

        This is more efficient than looping through sources because we check
        all sources at each step rather than doing separate traces.

        Args:
            sink: Sink dict
            source_aps: List of (source_dict, AccessPath) tuples
            max_depth: Maximum hops

        Returns:
            List of TaintPath objects
        """
        # Runtime import to avoid circular dependency
        from .core import TaintPath

        paths = []

        # Parse sink as AccessPath
        sink_ap = self._dict_to_access_path(sink)
        if not sink_ap:
            return []

        # Worklist: (current_ap, depth, hop_chain)
        worklist = deque([(sink_ap, 0, [])])
        visited_states: Set[Tuple[str, int]] = set()
        iteration = 0

        while worklist and len(paths) < self.max_paths_per_sink:
            iteration += 1
            if iteration > 10000:  # Safety valve
                if self.debug:
                    print(f"[IFDS] Hit iteration limit", file=sys.stderr)
                break

            current_ap, depth, hop_chain = worklist.popleft()

            # Cycle detection
            state = (current_ap.node_id, depth)
            if state in visited_states:
                continue
            visited_states.add(state)

            # Check if current node matches ANY source
            for source_dict, source_ap in source_aps:
                if self._access_paths_match(current_ap, source_ap):
                    # Found a path! Check if it's sanitized
                    if self._path_goes_through_sanitizer(hop_chain):
                        if self.debug:
                            print(f"[IFDS] Skipping sanitized path from {source_ap} to sink", file=sys.stderr)
                        continue

                    path = self._build_taint_path(source_dict, sink, hop_chain)
                    paths.append(path)
                    if len(paths) >= self.max_paths_per_sink:
                        break

            if depth >= max_depth:
                continue

            # Get predecessors from graphs.db
            predecessors = self._get_predecessors(current_ap)
            for pred_ap, edge_type, edge_meta in predecessors:
                hop = {
                    'type': edge_type,
                    'from': pred_ap.node_id,
                    'to': current_ap.node_id,
                    'from_file': pred_ap.file,
                    'to_file': current_ap.file,
                    'line': edge_meta.get('line', 0),
                    'depth': depth + 1
                }
                new_chain = [hop] + hop_chain  # Prepend (backward)
                worklist.append((pred_ap, depth + 1, new_chain))

        return paths

    def _trace_backward_from_sink(self, sink: Dict, source_ap: AccessPath,
                                  max_depth: int) -> List[TaintPath]:
        """Backward trace from sink to source using graphs.db.

        This is the core IFDS backward reachability algorithm.

        Algorithm:
            worklist = [(sink_access_path, depth=0, path_hops=[])]
            while worklist:
                current_ap, depth, hops = worklist.pop()
                if current_ap matches source_ap:
                    return TaintPath(source, sink, hops)
                if depth < max_depth:
                    for predecessor in get_data_dependencies(current_ap):
                        worklist.append((predecessor, depth+1, hops + [hop]))

        Returns:
            List of TaintPath objects if sink is reachable from source
        """
        # Runtime import to avoid circular dependency
        from .core import TaintPath

        paths = []

        # Parse sink as AccessPath
        sink_ap = self._dict_to_access_path(sink)
        if not sink_ap:
            return []

        # Worklist: (access_path, depth, hop_chain)
        worklist = deque([(sink_ap, 0, [])])
        visited_states: Set[Tuple[str, int]] = set()

        iteration = 0
        while worklist and len(paths) < 10:  # Max 10 paths per sink
            iteration += 1
            if iteration > 10000:
                if self.debug:
                    print(f"[IFDS] Hit iteration limit", file=sys.stderr)
                break

            current_ap, depth, hop_chain = worklist.popleft()

            # Cycle detection
            state = (current_ap.node_id, depth)
            if state in visited_states:
                continue
            visited_states.add(state)

            # Check if we reached the source
            if self._access_paths_match(current_ap, source_ap):
                # Found a path! Build TaintPath
                path = self._build_taint_path(source, sink, hop_chain)
                paths.append(path)
                if self.debug:
                    print(f"[IFDS] Found path with {len(hop_chain)} hops: {source_ap} -> {sink_ap}", file=sys.stderr)
                continue

            # Max depth check
            if depth >= max_depth:
                continue

            # Get predecessors from graphs.db
            predecessors = self._get_predecessors(current_ap)

            for pred_ap, edge_type, edge_meta in predecessors:
                # Build hop metadata
                hop = {
                    'type': edge_type,
                    'from': pred_ap.node_id,
                    'to': current_ap.node_id,
                    'from_file': pred_ap.file,
                    'to_file': current_ap.file,
                    'line': edge_meta.get('line', 0),
                    'depth': depth + 1
                }

                new_chain = [hop] + hop_chain  # Prepend (backward analysis)
                worklist.append((pred_ap, depth + 1, new_chain))

        return paths

    def _get_predecessors(self, ap: AccessPath) -> List[Tuple[AccessPath, str, Dict]]:
        """Get all access paths that flow into this access path.

        CRITICAL CHANGE (Phase 3): Now uses dynamic flow functions per Algorithm 1.

        Instead of just querying static graphs.db edges, this method:
        1. Queries repo_index.db to find what defines this variable
        2. Dynamically computes predecessors based on statement type
        3. Falls back to graphs.db for backward compatibility

        This solves the directional mismatch from Phase 2.

        Returns:
            List of (predecessor_access_path, edge_type, metadata) tuples
        """
        predecessors = []

        # PHASE 3: Dynamic flow functions (PRIMARY PATH)
        # Query repo_index.db to find defining statement
        defining_stmt = self._get_defining_statement(ap)

        if defining_stmt:
            stmt_type = defining_stmt.get('type')

            if self.debug:
                print(f"[IFDS] {ap.node_id} defined by {stmt_type}", file=sys.stderr)

            # Dispatch to appropriate flow function
            if stmt_type == 'PARAMETER':
                # THE CRITICAL FIX: Query function_call_args backward
                dynamic_preds = self._flow_function_parameter(ap)
                predecessors.extend(dynamic_preds)

            elif stmt_type == 'ASSIGNMENT':
                # Simple variable flow
                dynamic_preds = self._flow_function_assignment(ap, defining_stmt)
                predecessors.extend(dynamic_preds)

            elif stmt_type == 'FIELD_LOAD':
                # Field-sensitive flow
                dynamic_preds = self._flow_function_field_load(ap, defining_stmt)
                predecessors.extend(dynamic_preds)

        # FALLBACK: Static graph edges (for types not yet implemented)
        # Keep existing graph traversal for backward compatibility
        # This ensures assignment/return edges from graphs.db still work
        if not predecessors:
            self.graph_cursor.execute("""
                SELECT source, target, type, file, line, metadata
                FROM edges
                WHERE target = ?
                ORDER BY type
            """, (ap.node_id,))

            for row in self.graph_cursor.fetchall():
                source_node = row['source']
                edge_type = row['type']

                # Parse source as AccessPath
                source_ap = AccessPath.parse(source_node, ap.max_length)
                if not source_ap:
                    continue

                # Check if source is relevant (conservative alias check)
                # SKIP alias check for parameter_binding edges
                if edge_type != 'parameter_binding' and not self._could_alias(source_ap, ap):
                    continue

                meta = {
                    'file': row['file'] if row['file'] else source_ap.file,
                    'line': row['line'] if row['line'] else 0,
                }

                predecessors.append((source_ap, edge_type, meta))

        return predecessors

    def _could_alias(self, ap1: AccessPath, ap2: AccessPath) -> bool:
        """Conservative alias check (no expensive alias analysis).

        From paper (page 10): "Our taint analysis deliberately omits computing
        complete aliasing information... This deliberate trade-off of soundness
        for scalability drastically reduces theoretical complexity."

        Args:
            ap1, ap2: Access paths to compare

        Returns:
            True if paths could potentially alias (conservative)
        """
        # Same base variable = could alias
        if ap1.base == ap2.base:
            return True

        # Field prefix match
        if ap1.matches(ap2):
            return True

        # TODO: Add more sophisticated aliasing if needed
        # For now, be conservative

        return False

    def _access_paths_match(self, ap1: AccessPath, ap2: AccessPath) -> bool:
        """Check if two access paths represent the same data.

        Args:
            ap1, ap2: Access paths to compare

        Returns:
            True if paths definitely match
        """
        # Exact match on base + fields
        if ap1.base == ap2.base and ap1.fields == ap2.fields:
            return True

        # Prefix match (conservative)
        if ap1.matches(ap2):
            # Only match if files/functions are compatible
            # Allow cross-file matches (data flows across files)
            return True

        return False

    def _dict_to_access_path(self, node_dict: Dict) -> Optional[AccessPath]:
        """Convert source/sink dict to AccessPath.

        Args:
            node_dict: Dict with 'file', 'line', 'name', 'pattern'

        Returns:
            AccessPath or None if cannot parse
        """
        file = node_dict.get('file', '')
        pattern = node_dict.get('pattern', node_dict.get('name', ''))

        if not file or not pattern:
            return None

        # Get containing function
        function = self._get_containing_function(file, node_dict.get('line', 0))

        # Parse pattern as base.field.field
        parts = pattern.split('.')
        base = parts[0]
        fields = tuple(parts[1:]) if len(parts) > 1 else ()

        return AccessPath(
            file=file,
            function=function,
            base=base,
            fields=fields
        )

    def _get_containing_function(self, file: str, line: int) -> str:
        """Get function containing a line.

        Args:
            file: File path
            line: Line number

        Returns:
            Function name or "global"
        """
        self.repo_cursor.execute("""
            SELECT name FROM symbols
            WHERE path = ? AND type = 'function' AND line <= ?
            ORDER BY line DESC
            LIMIT 1
        """, (file, line))

        row = self.repo_cursor.fetchone()
        return row['name'] if row else "global"

    def _build_taint_path(self, source: Dict, sink: Dict,
                         hop_chain: List[Dict]):  # Return type removed to avoid circular import
        """Build TaintPath object from hop chain.

        Args:
            source: Source dict
            sink: Sink dict
            hop_chain: List of hop metadata dicts

        Returns:
            TaintPath with full hop chain
        """
        # Runtime import to avoid circular dependency
        from .core import TaintPath

        # Convert hops to path format
        path_steps = []

        # Add source
        path_steps.append({
            'type': 'source',
            'file': source.get('file'),
            'line': source.get('line'),
            'name': source.get('name'),
            'pattern': source.get('pattern')
        })

        # Add each hop
        for hop in hop_chain:
            path_steps.append(hop)

        # Add sink
        path_steps.append({
            'type': 'sink',
            'file': sink.get('file'),
            'line': sink.get('line'),
            'name': sink.get('name'),
            'pattern': sink.get('pattern')
        })

        # Create TaintPath
        path = TaintPath(source, sink, path_steps)
        path.flow_sensitive = True  # IFDS is flow-sensitive
        path.path_length = len(path_steps)

        return path

    def _load_safe_sinks(self):
        """Load sanitizers from framework_safe_sinks table."""
        self.safe_sinks: Set[str] = set()
        try:
            self.repo_cursor.execute("SELECT pattern FROM framework_safe_sinks")
            for row in self.repo_cursor.fetchall():
                self.safe_sinks.add(row['pattern'])
            if self.debug and self.safe_sinks:
                print(f"[IFDS] Loaded {len(self.safe_sinks)} safe sinks (sanitizers)", file=sys.stderr)
        except sqlite3.OperationalError:
            # Table doesn't exist - no sanitizers loaded
            pass

    def _is_sanitizer(self, function_name: str) -> bool:
        """Check if a function is a sanitizer.

        Checks both registry patterns and database safe_sinks.
        """
        # Check database safe sinks
        if function_name in self.safe_sinks:
            return True

        # Check any pattern that partially matches
        for safe_sink in self.safe_sinks:
            if safe_sink in function_name or function_name in safe_sink:
                return True

        # Check registry if available
        if self.registry and self.registry.is_sanitizer(function_name):
            return True

        return False

    def _path_goes_through_sanitizer(self, hop_chain: List[Dict]) -> bool:
        """Check if a taint path goes through a sanitizer.

        Queries repo_index.db to check if any hop involves a sanitizer call.
        """
        for hop in hop_chain:
            hop_file = hop.get('from_file') or hop.get('to_file')
            hop_line = hop.get('line', 0)

            if not hop_file or not hop_line:
                continue

            # Query function calls at this line
            self.repo_cursor.execute("""
                SELECT callee_function FROM function_call_args
                WHERE file = ? AND line = ?
                LIMIT 10
            """, (hop_file, hop_line))

            for row in self.repo_cursor.fetchall():
                callee = row['callee_function']
                if self._is_sanitizer(callee):
                    if self.debug:
                        print(f"[IFDS] Path sanitized by {callee} at {hop_file}:{hop_line}", file=sys.stderr)
                    return True

        return False

    def _get_defining_statement(self, ap: AccessPath) -> Optional[Dict[str, Any]]:
        """Determine what defines this AccessPath (Algorithm 1 dispatcher).

        Queries repo_index.db to find if this variable is:
        - A function parameter (PARAMETER)
        - Defined by assignment (ASSIGNMENT or FIELD_LOAD)
        - A source/allocation (not implemented yet)

        This is Step 1 of Algorithm 1 from the Oracle Labs paper.

        Returns:
            Dict with 'type' and statement data, or None if undefined
        """
        # Check if it's a function parameter
        # Query symbols table for parameters
        self.repo_cursor.execute("""
            SELECT path, name, type, line, parameters
            FROM symbols
            WHERE path = ? AND name = ? AND type = 'parameter'
            LIMIT 1
        """, (ap.file, ap.base))

        param_row = self.repo_cursor.fetchone()
        if param_row:
            return {
                'type': 'PARAMETER',
                'file': param_row['path'],
                'name': param_row['name'],
                'line': param_row['line']
            }

        # Check if it's defined by assignment
        # Query assignments table
        if ap.fields:
            # Field access like req.body
            # Check assignments with property_path
            full_path = f"{ap.base}.{'.'.join(ap.fields)}"
            self.repo_cursor.execute("""
                SELECT file, line, target_var, source_expr, in_function, property_path
                FROM assignments
                WHERE file = ? AND target_var = ? AND in_function = ?
                   AND (property_path = ? OR property_path IS NULL)
                ORDER BY line DESC
                LIMIT 1
            """, (ap.file, ap.base, ap.function, full_path))
        else:
            # Simple variable
            self.repo_cursor.execute("""
                SELECT file, line, target_var, source_expr, in_function, property_path
                FROM assignments
                WHERE file = ? AND target_var = ? AND in_function = ?
                ORDER BY line DESC
                LIMIT 1
            """, (ap.file, ap.base, ap.function))

        assign_row = self.repo_cursor.fetchone()
        if assign_row:
            # Check if it's a field load (source_expr contains '.')
            source_expr = assign_row['source_expr']
            if '.' in source_expr and not source_expr.startswith('"') and not source_expr.startswith("'"):
                return {
                    'type': 'FIELD_LOAD',
                    'file': assign_row['file'],
                    'line': assign_row['line'],
                    'target_var': assign_row['target_var'],
                    'source_expr': source_expr,
                    'property_path': assign_row['property_path']
                }
            else:
                return {
                    'type': 'ASSIGNMENT',
                    'file': assign_row['file'],
                    'line': assign_row['line'],
                    'target_var': assign_row['target_var'],
                    'source_expr': source_expr
                }

        # Not defined in this scope - could be from outer scope or undefined
        return None

    def _flow_function_parameter(self, ap: AccessPath) -> List[Tuple[AccessPath, str, Dict]]:
        """Flow function for parameters - THE CRITICAL FIX for directional mismatch.

        When tracing backward hits a parameter (e.g., db.js::execute::sql),
        this finds all call sites that pass arguments to this parameter.

        Algorithm:
        1. Query function_call_args WHERE callee matches ap.function AND param_name = ap.base
        2. For each call site, extract caller file, caller function, argument expression
        3. Parse argument to get variable name
        4. Return AccessPath for caller's argument

        This dynamically creates the backward edge that Phase 2 couldn't pre-build.
        """
        predecessors = []

        # Extract function name from ap.function (may be qualified like "MyClass.method")
        func_name = ap.function.split('.')[-1] if '.' in ap.function else ap.function

        # Query function_call_args for calls to this function with this parameter
        self.repo_cursor.execute("""
            SELECT file, line, caller_function, callee_function,
                   argument_expr, param_name
            FROM function_call_args
            WHERE callee_file_path = ?
              AND (callee_function LIKE ? OR callee_function = ?)
              AND param_name = ?
        """, (ap.file, f'%{func_name}%', func_name, ap.base))

        for row in self.repo_cursor.fetchall():
            caller_file = row['file']
            caller_function = row['caller_function'] if row['caller_function'] else "global"
            argument_expr = row['argument_expr']

            # Parse argument expression to get variable name
            arg_var = self._parse_arg_variable(argument_expr)
            if not arg_var:
                continue

            # Create AccessPath for caller's argument
            caller_ap = AccessPath(
                file=caller_file,
                function=caller_function,
                base=arg_var.split('.')[0],
                fields=tuple(arg_var.split('.')[1:]) if '.' in arg_var else ()
            )

            meta = {
                'file': caller_file,
                'line': row['line'],
                'call': row['callee_function']
            }

            predecessors.append((caller_ap, 'parameter_call', meta))

            if self.debug:
                print(f"[IFDS] Parameter flow: {caller_ap.node_id} -> {ap.node_id}", file=sys.stderr)

        return predecessors

    def _flow_function_assignment(self, ap: AccessPath, stmt: Dict) -> List[Tuple[AccessPath, str, Dict]]:
        """Flow function for assignments (Algorithm 1, Case 2).

        For assignment x = y, when tracing x backward, return y.

        Queries assignment_sources junction table for source variables.
        """
        predecessors = []

        file = stmt['file']
        line = stmt['line']
        target_var = stmt['target_var']

        # Query assignment_sources for source variables
        self.repo_cursor.execute("""
            SELECT source_var_name
            FROM assignment_sources
            WHERE assignment_file = ? AND assignment_line = ? AND assignment_target = ?
        """, (file, line, target_var))

        for row in self.repo_cursor.fetchall():
            source_var = row['source_var_name']

            # Create AccessPath for source variable
            source_ap = AccessPath(
                file=file,
                function=ap.function,  # Same function scope
                base=source_var.split('.')[0],
                fields=tuple(source_var.split('.')[1:]) if '.' in source_var else ()
            )

            meta = {'file': file, 'line': line, 'assignment': True}
            predecessors.append((source_ap, 'assignment', meta))

        return predecessors

    def _flow_function_field_load(self, ap: AccessPath, stmt: Dict) -> List[Tuple[AccessPath, str, Dict]]:
        """Flow function for field loads (Algorithm 1, Case 3).

        For x = y.f, when tracing:
        - x backward → y.f
        - x.g backward → y.f.g (field composition)
        """
        predecessors = []

        source_expr = stmt['source_expr']
        file = stmt['file']
        line = stmt['line']

        # Parse source_expr as base.field1.field2...
        parts = source_expr.split('.')
        if not parts:
            return []

        base = parts[0]
        source_fields = tuple(parts[1:]) if len(parts) > 1 else ()

        # If tracing x.g, need to compose with source fields
        # Tracing x.g where x = y.f means predecessor is y.f.g
        if ap.fields:
            # Compose: source_fields + ap.fields
            combined_fields = source_fields + ap.fields
        else:
            # Tracing x directly means predecessor is y.f
            combined_fields = source_fields

        source_ap = AccessPath(
            file=file,
            function=ap.function,
            base=base,
            fields=combined_fields
        )

        meta = {'file': file, 'line': line, 'field_load': True}
        predecessors.append((source_ap, 'field_load', meta))

        return predecessors

    def _parse_arg_variable(self, arg_expr: str) -> Optional[str]:
        """Parse argument expression to extract variable name.

        Similar to dfg_builder._parse_argument_variable but simpler.
        Returns variable name with optional field access (e.g., "req.body").
        """
        if not arg_expr or not isinstance(arg_expr, str):
            return None

        arg_expr = arg_expr.strip()

        # Skip literals
        if arg_expr.startswith('"') or arg_expr.startswith("'") or arg_expr.isdigit():
            return None

        # Skip function calls
        if '(' in arg_expr:
            return None

        # Skip operators
        if any(op in arg_expr for op in ['+', '-', '*', '/', '=', '<', '>', '!']):
            return None

        # Must start with valid identifier
        if not (arg_expr[0].isalpha() or arg_expr[0] == '_'):
            return None

        return arg_expr  # May include dots for field access

    def close(self):
        """Close database connections."""
        self.repo_conn.close()
        self.graph_conn.close()
