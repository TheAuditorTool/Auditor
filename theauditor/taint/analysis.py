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

            # Check for sinks in this block
            for sink in sinks:
                if self._is_sink_in_block(sink, current_block):
                    # Check if any tainted variable reaches this sink
                    if self._can_taint_reach_sink(current_tainted, sink):
                        # Create a TaintPath
                        from .core import TaintPath
                        path = TaintPath(source, sink, current_path + [sink])
                        path.flow_sensitive = True
                        path.tainted_vars = list(current_tainted)
                        paths.append(path)

            # Propagate taint through this block
            new_tainted = self._propagate_through_block(current_block, current_tainted)

            # Check for function calls that might propagate taint
            if max_depth > 0:
                calls_in_block = self._get_calls_in_block(current_block)
                for call in calls_in_block:
                    if self._is_tainted_call(call, new_tainted):
                        # Recursively analyze called function
                        callee_paths = self._analyze_function_cfg(
                            source, call.get('callee_function', ''),
                            sinks, call_graph, max_depth - 1
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

        # Propagate through assignments
        for assignment in assignments:
            target = assignment.get('target_var', '') or ''
            source_expr = assignment.get('source_expr', '') or ''

            # Check if assignment uses tainted data
            if source_expr and any(var in source_expr for var in tainted_vars):
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

        Checks both:
        1. symbols table (traditional function symbols)
        2. api_endpoints table (endpoint handlers that may not have function symbols)
        """
        file_path = source.get('file', '')
        line = source.get('line', 0)

        # Check traditional function symbols first
        if hasattr(self.cache, 'symbols'):
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
        if hasattr(self.cache, 'api_endpoints'):
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

    def _get_cfg_blocks(self, function: str) -> List[Dict]:
        """Get CFG blocks for a function."""
        if hasattr(self.cache, 'cfg_blocks'):
            return [b for b in self.cache.cfg_blocks
                   if b.get('function_name') == function]
        return []

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

    def _propagate_through_block(self, block: Dict, tainted_vars: Set[str]) -> Set[str]:
        """Propagate taint through a CFG block."""
        new_tainted = tainted_vars.copy()

        # Get assignments in this block
        if hasattr(self.cache, 'assignments'):
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
                source_expr = assignment.get('source_expr', '') or ''

                # If source uses tainted data, target becomes tainted
                if source_expr and any(var in source_expr for var in new_tainted):
                    new_tainted.add(target)

        return new_tainted

    def _get_calls_in_block(self, block: Dict) -> List[Dict]:
        """Get function calls in a CFG block."""
        calls = []
        if hasattr(self.cache, 'function_call_args'):
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
        if hasattr(self.cache, 'cfg_edges'):
            block_id = block.get('id')
            for edge in self.cache.cfg_edges:
                if edge.get('from_block') == block_id:
                    # Find the target block
                    to_id = edge.get('to_block')
                    if hasattr(self.cache, 'cfg_blocks'):
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
            if hasattr(self.cache, 'api_endpoints') and hasattr(self.cache, 'assignments_by_location'):
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
            if hasattr(self.cache, 'assignments'):
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

        if hasattr(self.cache, 'cfg_blocks'):
            for block in self.cache.cfg_blocks:
                block_start = block.get('start_line', 0) or 0
                block_end = block.get('end_line', 0) or 0
                if (block.get('file') == file and
                    block_start <= line <= block_end):
                    return block
        return None

    def _has_cfg_edge(self, from_block: Dict, to_block: Dict) -> bool:
        """Check if there's a CFG edge between two blocks."""
        if hasattr(self.cache, 'cfg_edges'):
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