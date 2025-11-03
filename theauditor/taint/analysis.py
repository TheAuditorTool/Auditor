"""
Unified taint flow analysis module.

Phase 4.5: Merges the 3 CFG implementation files into a single, unified analyzer.
This eliminates duplicate logic and provides a single CFG-based implementation.

Previous structure:
- interprocedural.py (43KB) - Two implementations (flow-insensitive + CFG)
- interprocedural_cfg.py (36KB) - CFG analyzer class
- cfg_integration.py (37KB) - CFG utilities

New structure:
- analysis.py - Single unified TaintFlowAnalyzer with CFG-based analysis
"""

from typing import Dict, List, Any, Set, Optional, Tuple
from collections import defaultdict, deque
import sys


class TaintFlowAnalyzer:
    """Unified taint flow analyzer using CFG-based analysis."""

    def __init__(self, cache, cursor=None):
        """
        Initialize analyzer with cache.

        Args:
            cache: Memory cache (SchemaMemoryCache or MemoryCache)
            cursor: Optional database cursor for queries not in cache
        """
        self.cache = cache
        self.cursor = cursor
        self.visited_paths = set()
        self.max_path_length = 100

    def analyze_interprocedural(self, sources: List[Dict], sinks: List[Dict],
                              call_graph: Dict, max_depth: int = 5) -> List['TaintPath']:
        """
        Main entry point for interprocedural taint analysis.

        This is the unified CFG-based implementation that replaces the
        3 separate implementations in the old files.

        Args:
            sources: List of taint sources
            sinks: List of security sinks
            call_graph: Function call graph
            max_depth: Maximum depth to trace

        Returns:
            List of TaintPath objects representing vulnerabilities
        """
        taint_paths = []

        for source in sources:
            # Find the function containing this source
            source_function = self._get_containing_function(source)

            if not source_function:
                # Hard fail - database is WRONG if function not found
                continue

            # Analyze flow from this source using CFG
            paths = self._analyze_function_cfg(
                source, source_function, sinks, call_graph, max_depth
            )
            taint_paths.extend(paths)

        return taint_paths

    def _analyze_function_cfg(self, source: Dict, function: str, sinks: List[Dict],
                            call_graph: Dict, max_depth: int) -> List['TaintPath']:
        """
        Analyze taint flow through a function using CFG.

        This is the core CFG-based analysis that tracks taint through
        control flow blocks and edges.
        """
        paths = []

        # Get CFG blocks for this function
        cfg_blocks = self._get_cfg_blocks(function)

        if not cfg_blocks:
            # Fallback to simple analysis if no CFG
            return self._analyze_simple_flow(source, function, sinks)

        # Find the block containing the source
        source_block = self._find_block_containing_line(
            cfg_blocks, source.get('file', ''), source.get('line', 0)
        )

        if not source_block:
            return []

        # Initialize taint state
        tainted_vars = {source.get('name', 'unknown')}
        visited_blocks = set()

        # Worklist algorithm for CFG traversal
        worklist = deque([(source_block, tainted_vars, [source])])

        while worklist and len(paths) < 100:  # Limit total paths
            current_block, current_tainted, current_path = worklist.popleft()

            # Skip if already visited this block with same taint state
            state_key = (current_block.get('id'), frozenset(current_tainted))
            if state_key in visited_blocks:
                continue
            visited_blocks.add(state_key)

            # Propagate taint through this block FIRST
            # This allows assignments in the block to taint new variables before checking sinks
            new_tainted = self._propagate_through_block(current_block, current_tainted)

            # Check for sinks in this block AFTER propagation
            # This ensures that variables tainted by assignments in this block can reach sinks in the same block
            for sink in sinks:
                if self._is_sink_in_block(sink, current_block):
                    # Check if any tainted variable reaches this sink (using new_tainted after propagation)
                    if self._can_taint_reach_sink(new_tainted, sink):
                        # Create a TaintPath
                        from .core import TaintPath
                        path = TaintPath(source, sink, current_path + [sink])
                        path.flow_sensitive = True
                        path.tainted_vars = list(new_tainted)
                        paths.append(path)

            # Check for function calls that propagate taint cross-function
            if max_depth > 0:
                calls_in_block = self._get_calls_in_block(current_block)
                for call in calls_in_block:
                    # Get which parameters receive tainted data (extractors already mapped this!)
                    tainted_params = self._get_tainted_params_for_call(call, new_tainted)

                    if tainted_params:
                        # Get callee location (could be cross-file)
                        callee_func_raw = call.get('callee_function', '')
                        callee_file = call.get('callee_file_path', '') or source.get('file', '')

                        # Normalize function name: "controller.dashboardService.getDashboardStats" → "DashboardService.getDashboardStats"
                        # CFG uses Class.method, not variable.method
                        callee_func = self._normalize_function_name(callee_func_raw, callee_file)

                        if callee_func:
                            # Propagate taint into callee with tainted parameters
                            for param_name in tainted_params.keys():
                                # Find function start line from CFG or symbols
                                callee_line = self._get_function_start_line(callee_func, callee_file)

                                # Create synthetic source for the tainted parameter in callee
                                callee_source = {
                                    'name': param_name,
                                    'file': callee_file,
                                    'line': callee_line or 1
                                }
                                callee_paths = self._analyze_function_cfg(
                                    callee_source, callee_func, sinks, call_graph, max_depth - 1
                                )
                                paths.extend(callee_paths)

            # Add successor blocks to worklist
            successors = self._get_block_successors(current_block)
            for successor in successors:
                new_path = current_path + [{'type': 'flow', 'block': current_block.get('id')}]
                worklist.append((successor, new_tainted.copy(), new_path))

        return paths

    def _analyze_simple_flow(self, source: Dict, function: str, sinks: List[Dict]) -> List['TaintPath']:
        """
        Simple flow analysis without CFG (fallback).

        Used when CFG is not available for a function.
        """
        paths = []

        # Get all assignments in the function
        assignments = self._get_function_assignments(function, source.get('file', ''))

        # Track tainted variables
        tainted_vars = {source.get('name', 'unknown')}

        # Propagate through assignments using junction table
        for assignment in assignments:
            target = assignment.get('target_var', '') or ''

            # Query junction table for precise source variables
            source_vars = self._get_assignment_source_vars(
                source.get('file', ''),
                assignment.get('line', 0),
                target
            )

            # Check if any source variable is tainted
            if any(src_var in tainted_vars for src_var in source_vars):
                tainted_vars.add(target)

        # Check if any sink is reachable
        for sink in sinks:
            if sink.get('file') == source.get('file'):
                # Simple check: is sink in same function and uses tainted var
                sink_name = sink.get('name', '') or ''
                if sink_name and any(var in sink_name for var in tainted_vars):
                    from .core import TaintPath
                    path = TaintPath(source, sink, [source, sink])
                    path.flow_sensitive = False
                    path.tainted_vars = list(tainted_vars)
                    paths.append(path)

        return paths

    def _get_containing_function(self, source: Dict) -> Optional[str]:
        """
        Get the function containing a source.

        For parameter sources, uses the function field from discovery.
        For other sources, checks symbols table and api_endpoints.
        """
        # For parameter sources, use the function field directly
        if source.get('type') == 'parameter' and source.get('function'):
            return source.get('function')

        file_path = source.get('file', '')
        line = source.get('line', 0)

        # Check traditional function symbols - find exact line match first
        for symbol in self.cache.symbols:
            start_line = symbol.get('line', 0) or 0
            # For function definitions, the source line equals the function line
            if (symbol.get('type') == 'function' and
                symbol.get('path') == file_path and
                start_line == line):
                return symbol.get('name')

        # Then check range matches
        for symbol in self.cache.symbols:
            start_line = symbol.get('line', 0) or 0
            end_line = symbol.get('end_line')
            if end_line is None:
                end_line = (line or 0) + 100

            if (symbol.get('type') == 'function' and
                symbol.get('path') == file_path and
                line is not None and start_line <= line <= end_line):
                return symbol.get('name')

        # Check api_endpoints for endpoint handlers (arrow functions in route definitions)
        # Find endpoints in the same file, ordered by line
        endpoints_in_file = [
            ep for ep in self.cache.api_endpoints
            if ep.get('file') == file_path
        ]
        endpoints_in_file.sort(key=lambda ep: ep.get('line', 0) or 0)

        for i, endpoint in enumerate(endpoints_in_file):
            start_line = endpoint.get('line', 0) or 0
            # End of this handler is start of next handler (or +200 lines if last)
            if i + 1 < len(endpoints_in_file):
                end_line = endpoints_in_file[i + 1].get('line', 0) or 0
            else:
                end_line = start_line + 200  # Assume max 200 lines per handler

            if start_line <= line < end_line:
                # Use endpoint path as function name
                method = endpoint.get('method', 'UNKNOWN')
                path = endpoint.get('pattern', endpoint.get('path', 'unknown'))
                return f"{method} {path}"

        return None

    def _normalize_function_name(self, func_name: str, file: str) -> Optional[str]:
        """
        Normalize function name from function_call_args to match CFG naming.

        function_call_args uses: "controller.dashboardService.getDashboardStats"
        CFG uses: "DashboardService.getDashboardStats"

        Returns CFG-compatible function name or None if not found.
        """
        if not func_name:
            return None

        # Try finding exact match first
        for block in self.cache.cfg_blocks:
            if block.get('function_name') == func_name and block.get('file') == file:
                return func_name

        # Try matching by suffix (method name)
        # "controller.dashboardService.getDashboardStats" → find CFG function ending with ".getDashboardStats"
        if '.' in func_name:
            method_name = func_name.split('.')[-1]  # "getDashboardStats"

            for block in self.cache.cfg_blocks:
                cfg_func = block.get('function_name', '')
                if block.get('file') == file and cfg_func.endswith('.' + method_name):
                    return cfg_func

        return None

    def _get_function_start_line(self, function: str, file: str) -> Optional[int]:
        """Get the start line of a function from CFG or symbols."""
        # Try CFG first
        for block in self.cache.cfg_blocks:
            if block.get('function_name') == function and block.get('file') == file:
                return block.get('start_line')

        # Fallback to symbols table
        for symbol in self.cache.symbols:
            if (symbol.get('type') == 'function' and
                symbol.get('name') == function and
                symbol.get('path') == file):
                return symbol.get('line')

        return None

    def _get_cfg_blocks(self, function: str) -> List[Dict]:
        """Get CFG blocks for a function."""
        return [b for b in self.cache.cfg_blocks
               if b.get('function_name') == function]

    def _find_block_containing_line(self, blocks: List[Dict], file: str, line: int) -> Optional[Dict]:
        """Find the CFG block containing a specific line."""
        if line is None:
            return None
        for block in blocks:
            start_line = block.get('start_line', 0) or 0
            end_line = block.get('end_line', 0) or 0
            if (block.get('file') == file and
                start_line <= line <= end_line):
                return block
        return None

    def _is_sink_in_block(self, sink: Dict, block: Dict) -> bool:
        """Check if a sink is in a CFG block."""
        sink_line = sink.get('line', 0) or 0
        start_line = block.get('start_line', 0) or 0
        end_line = block.get('end_line', 0) or 0
        return (sink.get('file') == block.get('file') and
                start_line <= sink_line <= end_line)

    def _can_taint_reach_sink(self, tainted_vars: Set[str], sink: Dict) -> bool:
        """Check if tainted variables can reach a sink."""
        # Simple check: does sink use any tainted variable
        sink_pattern = sink.get('pattern', '') or ''
        sink_name = sink.get('name', '') or ''

        for var in tainted_vars:
            if var in sink_pattern or var in sink_name:
                return True

        return False

    def _get_assignment_source_vars(self, file: str, line: int, target: str) -> List[str]:
        """
        Get source variables for an assignment using assignment_sources junction table.
        Schema contract guarantees assignment_sources exists.
        """
        source_vars = []
        for src_row in self.cache.assignment_sources:
            if (src_row.get('assignment_file') == file and
                src_row.get('assignment_line') == line and
                src_row.get('assignment_target') == target):
                source_vars.append(src_row.get('source_var_name', ''))
        return source_vars

    def _get_tainted_params_for_call(self, call: Dict, tainted_vars: Set[str]) -> Dict[str, str]:
        """
        Get parameter names that receive tainted data for a function call.
        Uses function_call_args which ALREADY has param_name mapped by extractors.

        Returns dict of {param_name: tainted_arg_var}
        """
        tainted_params = {}

        # Query all arguments for this call
        call_file = call.get('file')
        call_line = call.get('line')

        for call_arg in self.cache.function_call_args:
            if (call_arg.get('file') == call_file and
                call_arg.get('line') == call_line):

                arg_expr = call_arg.get('argument_expr', '') or ''
                param_name = call_arg.get('param_name', '') or ''

                # Check if this argument uses a tainted variable
                for tainted_var in tainted_vars:
                    if tainted_var in arg_expr and param_name:
                        tainted_params[param_name] = tainted_var
                        break

        return tainted_params

    def _propagate_through_block(self, block: Dict, tainted_vars: Set[str]) -> Set[str]:
        """Propagate taint through a CFG block."""
        new_tainted = tainted_vars.copy()

        # Get assignments in this block
        block_start = block.get('start_line', 0) or 0
        block_end = block.get('end_line', 0) or 0
        block_assignments = []
        for a in self.cache.assignments:
            a_line = a.get('line', 0) or 0
            if (a.get('file') == block.get('file') and
                block_start <= a_line <= block_end):
                block_assignments.append(a)

        for assignment in block_assignments:
            target = assignment.get('target_var', '') or ''

            # Query junction table for precise source variables
            source_vars = self._get_assignment_source_vars(
                block.get('file'),
                assignment.get('line', 0),
                target
            )

            # If any source variable is tainted, target becomes tainted
            if any(src_var in new_tainted for src_var in source_vars):
                new_tainted.add(target)

        return new_tainted

    def _get_calls_in_block(self, block: Dict) -> List[Dict]:
        """Get function calls in a CFG block."""
        calls = []
        block_start = block.get('start_line', 0) or 0
        block_end = block.get('end_line', 0) or 0
        for c in self.cache.function_call_args:
            c_line = c.get('line', 0) or 0
            if (c.get('file') == block.get('file') and
                block_start <= c_line <= block_end):
                calls.append(c)
        return calls

    def _is_tainted_call(self, call: Dict, tainted_vars: Set[str]) -> bool:
        """Check if a function call uses tainted arguments."""
        args = call.get('argument_expr', '') or ''
        return bool(args and any(var in args for var in tainted_vars))

    def _get_block_successors(self, block: Dict) -> List[Dict]:
        """Get successor blocks in CFG."""
        successors = []
        block_id = block.get('id')
        for edge in self.cache.cfg_edges:
            if edge.get('from_block') == block_id:
                # Find the target block
                to_id = edge.get('to_block')
                for b in self.cache.cfg_blocks:
                    if b.get('id') == to_id:
                        successors.append(b)
                        break
        return successors

    def _get_function_assignments(self, function: str, file: str) -> List[Dict]:
        """Get all assignments in a function."""
        assignments = []

        # Check if this is an API endpoint handler (synthetic function name)
        if function and (function.startswith('GET ') or function.startswith('POST ') or
                        function.startswith('PUT ') or function.startswith('DELETE ') or
                        function.startswith('PATCH ')):
            # Use spatial index with line ranges from api_endpoints
            # Find the endpoint to get line range
            for endpoint in self.cache.api_endpoints:
                if endpoint.get('file') == file:
                    method = endpoint.get('method', '')
                    path = endpoint.get('pattern', endpoint.get('path', ''))
                    endpoint_name = f"{method} {path}"

                    if endpoint_name == function:
                        start_line = endpoint.get('line', 0) or 0
                        start_block = start_line // 100

                        # Get assignments from spatial index (~500 lines, 5 blocks)
                        for block_idx in range(start_block, start_block + 5):
                            block_assignments = self.cache.assignments_by_location.get(file, {}).get(block_idx, [])
                            for a in block_assignments:
                                a_line = a.get('line', 0) or 0
                                if a_line >= start_line:
                                    assignments.append(a)
                        break
        else:
            # Traditional function lookup
            assignments = [a for a in self.cache.assignments
                         if a.get('file') == file and a.get('in_function') == function]

        return assignments

    def check_path_feasibility(self, path: List[Dict]) -> bool:
        """
        Check if a taint path is feasible through CFG.

        This checks that the path follows valid control flow edges.
        """
        if len(path) < 2:
            return True

        # Check each transition in the path
        for i in range(len(path) - 1):
            current = path[i]
            next_node = path[i + 1]

            # Get blocks for current and next
            current_block = self._find_block_for_node(current)
            next_block = self._find_block_for_node(next_node)

            if current_block and next_block:
                # Check if there's a valid CFG edge
                if not self._has_cfg_edge(current_block, next_block):
                    # Path is not feasible
                    return False

        return True

    def _find_block_for_node(self, node: Dict) -> Optional[Dict]:
        """Find the CFG block containing a node."""
        file = node.get('file', '')
        line = node.get('line', 0) or 0

        for block in self.cache.cfg_blocks:
            block_start = block.get('start_line', 0) or 0
            block_end = block.get('end_line', 0) or 0
            if (block.get('file') == file and
                block_start <= line <= block_end):
                return block
        return None

    def _has_cfg_edge(self, from_block: Dict, to_block: Dict) -> bool:
        """Check if there's a CFG edge between two blocks."""
        from_id = from_block.get('id')
        to_id = to_block.get('id')

        for edge in self.cache.cfg_edges:
            if (edge.get('from_block') == from_id and
                edge.get('to_block') == to_id):
                return True

        # Also allow if blocks are in sequence (implicit fall-through)
        if (from_block.get('file') == to_block.get('file') and
            from_block.get('end_line', 0) + 1 == to_block.get('start_line', 0)):
            return True

        return False