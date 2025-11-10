"""IFDS-based taint analyzer using pre-computed graphs.

This module implements demand-driven backward taint analysis using the IFDS
framework adapted from "IFDS Taint Analysis with Access Paths" (Allen et al., 2021).

Key differences from paper:
- Uses pre-computed graphs.db instead of on-the-fly graph construction
- Database-first (no SSA/φ-nodes, works with normalized AST data)
- Multi-language (Python, JS, TS via extractors)

Architecture (Phase 6.1 - Goal B: Full Provenance):
    Sources → [Backward IFDS] → Sinks
              ↓
    graphs.db (DFG + Call Graph)
              ↓
    8-10 hop cross-file flows (COMPLETE call chain)

CRITICAL: Source matches are WAYPOINTS, not termination points.
Paths are recorded ONLY at max_depth or natural termination.
This captures the full call chain: route → middleware → controller → service → ORM

Performance: O(CallD³ + 2ED²) - h-sparse IFDS (page 10, Table 3)
"""

from __future__ import annotations  # Defer evaluation of type annotations
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any, TYPE_CHECKING
from collections import deque, defaultdict

from .access_path import AccessPath

# Avoid circular import: core.py imports ifds_analyzer, ifds_analyzer imports TaintPath
# TaintPath is only used for type hints, so we can defer the import
if TYPE_CHECKING:
    from .taint_path import TaintPath


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

        # Enable debug logging via environment variable
        import os
        self.debug = bool(os.environ.get("THEAUDITOR_DEBUG"))

        if self.debug:
            print("[IFDS] ========================================", file=sys.stderr)
            print("[IFDS] IFDS Analyzer Initialized (DEBUG MODE)", file=sys.stderr)
            print(f"[IFDS] Database: {repo_db_path}", file=sys.stderr)
            print("[IFDS] ========================================", file=sys.stderr)

        # Load safe sinks (sanitizers) from database
        self._load_safe_sinks()
        self._load_validation_sanitizers()

    def analyze_sink_to_sources(self, sink: Dict, sources: List[Dict],
                                max_depth: int = 10) -> Tuple[List['TaintPath'], List['TaintPath']]:
        """Find all taint paths from sink to sources using IFDS backward analysis.

        PHASE 6.1 CHANGE (Goal B - Full Provenance):
        Now returns (vulnerable_paths, sanitized_paths) tuple.

        Algorithm (IFDS paper - demand-driven with full provenance):
        1. Start at sink (backward analysis is demand-driven from sinks)
        2. Query graphs.db for data dependencies (backward edges)
        3. Follow edges backward through assignments, calls, returns, middleware
        4. Annotate when path reaches ANY source (DO NOT terminate early)
        5. Continue to max_depth to capture COMPLETE call chain
        6. Build TaintPath with full hop chain (8-10 hops)
        7. Classify path as vulnerable or sanitized based on sanitizer presence

        Args:
            sink: Security sink dict (file, line, pattern, name)
            sources: List of taint source dicts
            max_depth: Maximum hops (default 10)

        Returns:
            Tuple of (vulnerable_paths, sanitized_paths)
        """
        self.max_depth = max_depth

        # Parse all sources as AccessPaths for matching
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

        # Trace backward from sink, checking if ANY source is reachable
        vulnerable, sanitized = self._trace_backward_to_any_source(sink, source_aps, max_depth)

        if self.debug:
            print(f"[IFDS] Found {len(vulnerable)} vulnerable paths, {len(sanitized)} sanitized paths", file=sys.stderr)

        return (vulnerable, sanitized)

    def _trace_backward_to_any_source(self, sink: Dict, source_aps: List[Tuple[Dict, AccessPath]],
                                      max_depth: int) -> Tuple[List['TaintPath'], List['TaintPath']]:
        """Backward trace from sink, checking if ANY source is reachable.

        PHASE 6.1 CHANGE (Goal B - Full Provenance):
        Now returns (vulnerable_paths, sanitized_paths) tuple.

        CRITICAL ARCHITECTURAL CHANGE: Source matches are now WAYPOINTS, not termination points.
        Paths are recorded ONLY at max_depth or natural termination (no predecessors).
        This captures the COMPLETE call chain (8-10 hops) instead of stopping at first source (2-3 hops).

        Algorithm:
        1. Start at sink (backward analysis)
        2. Query graphs.db for data dependencies (backward edges)
        3. Follow edges backward through assignments, calls, returns, middleware
        4. When source is matched, ANNOTATE it (store matched_source in worklist state)
        5. CONTINUE exploring to max_depth (DO NOT terminate early)
        6. Record path ONLY when exploration terminates (max_depth OR no predecessors)
        7. Classify path as vulnerable or sanitized based on sanitizer presence

        Args:
            sink: Sink dict
            source_aps: List of (source_dict, AccessPath) tuples
            max_depth: Maximum hops

        Returns:
            Tuple of (vulnerable_paths, sanitized_paths)
        """
        # Runtime import to avoid circular dependency
        from .taint_path import TaintPath

        vulnerable_paths = []
        sanitized_paths = []

        # Parse sink as AccessPath
        sink_ap = self._dict_to_access_path(sink)
        if not sink_ap:
            return ([], [])

        # Worklist: (current_ap, depth, hop_chain, matched_source)
        # PHASE 6.1: Added matched_source to track which source (if any) this path reached
        worklist = deque([(sink_ap, 0, [], None)])
        visited_states: Set[Tuple[str, int]] = set()
        iteration = 0

        while worklist and (len(vulnerable_paths) + len(sanitized_paths)) < self.max_paths_per_sink:
            iteration += 1
            if iteration > 10000:  # Safety valve
                if self.debug:
                    print(f"[IFDS] Hit iteration limit", file=sys.stderr)
                break

            current_ap, depth, hop_chain, matched_source = worklist.popleft()

            # Cycle detection
            state = (current_ap.node_id, depth)
            if state in visited_states:
                continue
            visited_states.add(state)

            # PHASE 6.1: Check if current node matches ANY source (ANNOTATE, don't terminate)
            current_matched_source = matched_source  # Carry forward previous match
            for source_dict, source_ap in source_aps:
                if self._access_paths_match(current_ap, source_ap):
                    current_matched_source = source_dict
                    # ALWAYS print source match (not just debug mode)
                    print(f"[IFDS] *** SOURCE MATCHED at depth={depth}: {current_ap.node_id}", file=sys.stderr)
                    print(f"[IFDS]     Pattern: {source_dict.get('pattern')}", file=sys.stderr)
                    print(f"[IFDS]     Current hop_chain length: {len(hop_chain)}", file=sys.stderr)
                    print(f"[IFDS]     -> Continuing to explore predecessors (Goal B)", file=sys.stderr)
                    break

            # PHASE 6.1: Check termination conditions (ONLY place where paths are recorded)
            if depth >= max_depth:
                # Reached max depth - if we matched a source, record the path
                if current_matched_source:
                    sanitizer_meta = self._path_goes_through_sanitizer(hop_chain)

                    if sanitizer_meta:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        path.sanitizer_file = sanitizer_meta['file']
                        path.sanitizer_line = sanitizer_meta['line']
                        path.sanitizer_method = sanitizer_meta['method']
                        sanitized_paths.append(path)

                        if self.debug:
                            print(f"[IFDS] ✓ Recorded SANITIZED path at max_depth={depth}, {len(hop_chain)} hops", file=sys.stderr)
                    else:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        vulnerable_paths.append(path)

                        if self.debug:
                            print(f"[IFDS] ✓ Recorded VULNERABLE path at max_depth={depth}, {len(hop_chain)} hops", file=sys.stderr)

                continue

            # Get predecessors from graphs.db
            predecessors = self._get_predecessors(current_ap)

            # ALWAYS log predecessor count at depth 0-3 (critical early exploration)
            if depth <= 3:
                print(f"[IFDS] *** Depth={depth}, node={current_ap.node_id[:80]}, found {len(predecessors)} predecessors", file=sys.stderr)

            # PHASE 6.1: Natural termination - no more predecessors
            if not predecessors:
                # If we matched a source, record the path (complete call chain)
                if current_matched_source:
                    sanitizer_meta = self._path_goes_through_sanitizer(hop_chain)

                    if sanitizer_meta:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        path.sanitizer_file = sanitizer_meta['file']
                        path.sanitizer_line = sanitizer_meta['line']
                        path.sanitizer_method = sanitizer_meta['method']
                        sanitized_paths.append(path)

                        if self.debug:
                            print(f"[IFDS] ✓ Recorded SANITIZED path at natural termination (no predecessors), {len(hop_chain)} hops", file=sys.stderr)
                    else:
                        path = self._build_taint_path(current_matched_source, sink, hop_chain)
                        vulnerable_paths.append(path)

                        if self.debug:
                            print(f"[IFDS] ✓ Recorded VULNERABLE path at natural termination (no predecessors), {len(hop_chain)} hops", file=sys.stderr)

                continue

            # PHASE 6.1: Continue exploration (this runs EVEN IF we matched a source)
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
                # PHASE 6.1: Pass matched_source forward so we know this path reached a source
                worklist.append((pred_ap, depth + 1, new_chain, current_matched_source))

        return (vulnerable_paths, sanitized_paths)

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
        from .taint_path import TaintPath

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

        SIMPLIFIED ARCHITECTURE (Phase 4): Now reads pre-computed graph from graphs.db.

        All complex flow logic has been moved to dfg_builder.py which pre-computes:
        - Assignment edges (x = y)
        - Return edges (return x)
        - Parameter binding edges (func(x) -> param)
        - Cross-boundary edges (frontend -> backend API)
        - Express middleware edges (chain execution order)

        This method now just performs a single database lookup.

        Returns:
            List of (predecessor_access_path, edge_type, metadata) tuples
        """
        predecessors = []

        # Single query to graphs.db for all predecessors
        self.graph_cursor.execute("""
            SELECT source, type, metadata
            FROM edges
            WHERE target = ? AND graph_type = 'data_flow'
        """, (ap.node_id,))

        for row in self.graph_cursor.fetchall():
            source_id = row['source']
            edge_type = row['type']
            metadata = {}

            # Parse metadata if present
            if row['metadata']:
                try:
                    import json
                    metadata = json.loads(row['metadata'])
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            # Parse source node ID back to AccessPath
            source_ap = AccessPath.parse(source_id)
            if source_ap:
                predecessors.append((source_ap, edge_type, metadata))

                if self.debug:
                    print(f"[IFDS] Edge: {source_id} -> {ap.node_id} ({edge_type})", file=sys.stderr)

        # Log if no predecessors found (natural termination point)
        if not predecessors and self.debug:
            print(f"[IFDS] No predecessors for {ap.node_id} (termination point)", file=sys.stderr)

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
        from .taint_path import TaintPath

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
        if self.debug:
            print("[IFDS] → ENTRY: _load_safe_sinks()", file=sys.stderr)

        self.safe_sinks: Set[str] = set()
        try:
            # FIX: Column is 'sink_pattern', not 'pattern'
            self.repo_cursor.execute("SELECT sink_pattern FROM framework_safe_sinks")
            rows = self.repo_cursor.fetchall()

            if self.debug:
                print(f"[IFDS]   Query returned {len(rows)} rows from framework_safe_sinks", file=sys.stderr)

            for row in rows:
                pattern = row['sink_pattern']
                self.safe_sinks.add(pattern)
                if self.debug:
                    print(f"[IFDS]   + Safe sink pattern: {pattern}", file=sys.stderr)

            if self.debug:
                print(f"[IFDS] ← EXIT: Loaded {len(self.safe_sinks)} safe sink patterns", file=sys.stderr)
        except sqlite3.OperationalError as e:
            if self.debug:
                print(f"[IFDS] ← EXIT: Table framework_safe_sinks not found ({e})", file=sys.stderr)
            # Table doesn't exist - no sanitizers loaded
            pass

    def _load_validation_sanitizers(self):
        """Load validation framework sanitizers from validation_framework_usage table.

        This captures location-based sanitizers like Zod middleware that must be
        matched by file:line, not just function name pattern.
        """
        if self.debug:
            print("[IFDS] → ENTRY: _load_validation_sanitizers()", file=sys.stderr)

        self.validation_sanitizers: List[Dict] = []
        try:
            self.repo_cursor.execute("""
                SELECT file_path, line, framework, method, argument_expr, is_validator
                FROM validation_framework_usage
                WHERE is_validator = 1
            """)
            rows = self.repo_cursor.fetchall()

            if self.debug:
                print(f"[IFDS]   Query returned {len(rows)} rows from validation_framework_usage", file=sys.stderr)

            for row in rows:
                sanitizer = {
                    'file': row['file_path'],
                    'line': row['line'],
                    'framework': row['framework'],
                    'method': row['method'],
                    'argument': row['argument_expr']
                }
                self.validation_sanitizers.append(sanitizer)

                if self.debug:
                    print(f"[IFDS]   + Validation sanitizer: {sanitizer['framework']}.{sanitizer['method']}({sanitizer['argument']}) at {sanitizer['file']}:{sanitizer['line']}", file=sys.stderr)

            if self.debug:
                print(f"[IFDS] ← EXIT: Loaded {len(self.validation_sanitizers)} validation sanitizers", file=sys.stderr)
        except sqlite3.OperationalError as e:
            if self.debug:
                print(f"[IFDS] ← EXIT: Table validation_framework_usage not found ({e})", file=sys.stderr)
            # Table doesn't exist - no validation sanitizers loaded
            pass

    def _is_sanitizer(self, function_name: str) -> bool:
        """Check if a function is a sanitizer.

        Checks both registry patterns and database safe_sinks.
        """
        if self.debug:
            print(f"[IFDS]     → _is_sanitizer('{function_name}')?", file=sys.stderr)

        # Check database safe sinks (exact match)
        if function_name in self.safe_sinks:
            if self.debug:
                print(f"[IFDS]     ✓ EXACT MATCH in safe_sinks: {function_name}", file=sys.stderr)
            return True

        # Check any pattern that partially matches
        for safe_sink in self.safe_sinks:
            if safe_sink in function_name or function_name in safe_sink:
                if self.debug:
                    print(f"[IFDS]     ✓ PARTIAL MATCH: '{safe_sink}' ~ '{function_name}'", file=sys.stderr)
                return True

        # Check registry if available
        if self.registry and self.registry.is_sanitizer(function_name):
            if self.debug:
                print(f"[IFDS]     ✓ REGISTRY MATCH: {function_name}", file=sys.stderr)
            return True

        if self.debug:
            print(f"[IFDS]     ✗ NOT a sanitizer: {function_name}", file=sys.stderr)
        return False

    def _path_goes_through_sanitizer(self, hop_chain: List[Dict]) -> Optional[Dict]:
        """Check if a taint path goes through a sanitizer.

        PHASE 6 CHANGE: Now returns sanitizer metadata instead of bool.

        Checks TWO types of sanitizers:
        1. Validation framework sanitizers (location-based: file:line match from validation_framework_usage)
        2. Safe sink patterns (name-based: function name pattern match from framework_safe_sinks)

        This is the critical taint-kill logic that prevents false positives.

        Returns:
            Dict with sanitizer metadata if path is sanitized, None if vulnerable
            Format: {'file': str, 'line': int, 'method': str}
        """
        if self.debug:
            print(f"[IFDS] → ENTRY: _path_goes_through_sanitizer() - checking {len(hop_chain)} hops", file=sys.stderr)

        for i, hop in enumerate(hop_chain):
            hop_file = hop.get('from_file') or hop.get('to_file')
            hop_line = hop.get('line', 0)

            if self.debug:
                print(f"[IFDS]   Hop {i+1}/{len(hop_chain)}: {hop_file}:{hop_line}", file=sys.stderr)

            if not hop_file or not hop_line:
                if self.debug:
                    print(f"[IFDS]     ✗ Skipping (missing file or line)", file=sys.stderr)
                continue

            # ============================================================
            # CHECK 1: Validation Framework Sanitizers (Location-Based)
            # ============================================================
            # These are middleware sanitizers like Zod that must be matched by
            # exact file:line location, not just function name pattern
            if self.debug:
                print(f"[IFDS]     CHECK 1: Validation framework sanitizers ({len(self.validation_sanitizers)} loaded)", file=sys.stderr)

            for san in self.validation_sanitizers:
                # Match by file path (handle both absolute and relative paths)
                file_match = (
                    hop_file == san['file'] or
                    hop_file.endswith(san['file']) or
                    san['file'].endswith(hop_file)
                )

                if file_match and hop_line == san['line']:
                    if self.debug:
                        print(f"[IFDS]     ✓✓✓ VALIDATION SANITIZER MATCH ✓✓✓", file=sys.stderr)
                        print(f"[IFDS]         Framework: {san['framework']}", file=sys.stderr)
                        print(f"[IFDS]         Method: {san['method']}", file=sys.stderr)
                        print(f"[IFDS]         Argument: {san['argument']}", file=sys.stderr)
                        print(f"[IFDS]         Location: {san['file']}:{san['line']}", file=sys.stderr)
                        print(f"[IFDS]     ✓✓✓ TAINT KILLED ✓✓✓", file=sys.stderr)

                    # PHASE 6: Return sanitizer metadata instead of bool
                    return {
                        'file': san['file'],
                        'line': san['line'],
                        'method': f"{san['framework']}.{san['method']}"
                    }

            if self.debug:
                print(f"[IFDS]     ✗ No validation sanitizer match at this hop", file=sys.stderr)

            # ============================================================
            # CHECK 2: Safe Sink Patterns (Function Name-Based)
            # ============================================================
            # These are inherently safe functions like res.json() that auto-escape
            if self.debug:
                print(f"[IFDS]     CHECK 2: Safe sink patterns ({len(self.safe_sinks)} loaded)", file=sys.stderr)

            # Query function calls at this line
            self.repo_cursor.execute("""
                SELECT callee_function FROM function_call_args
                WHERE file = ? AND line = ?
                LIMIT 10
            """, (hop_file, hop_line))

            callees = [row['callee_function'] for row in self.repo_cursor.fetchall()]

            if self.debug:
                if callees:
                    print(f"[IFDS]     Found {len(callees)} function calls at this line: {callees}", file=sys.stderr)
                else:
                    print(f"[IFDS]     No function calls found at this line", file=sys.stderr)

            for callee in callees:
                if self._is_sanitizer(callee):
                    if self.debug:
                        print(f"[IFDS]     ✓✓✓ SAFE SINK MATCH ✓✓✓", file=sys.stderr)
                        print(f"[IFDS]         Function: {callee}", file=sys.stderr)
                        print(f"[IFDS]         Location: {hop_file}:{hop_line}", file=sys.stderr)
                        print(f"[IFDS]     ✓✓✓ TAINT KILLED ✓✓✓", file=sys.stderr)

                    # PHASE 6: Return sanitizer metadata instead of bool
                    return {
                        'file': hop_file,
                        'line': hop_line,
                        'method': callee
                    }

            if self.debug:
                print(f"[IFDS]     ✗ No safe sink match at this hop", file=sys.stderr)

        if self.debug:
            print(f"[IFDS] ← EXIT: _path_goes_through_sanitizer() - NO SANITIZER FOUND (path is tainted)", file=sys.stderr)
        return None  # PHASE 6: Return None instead of False

    def _get_defining_statement(self, ap: AccessPath) -> Optional[Dict[str, Any]]:
        """Determine what defines this AccessPath (Algorithm 1 dispatcher).

        Queries repo_index.db to find if this variable is:
        - A function parameter (PARAMETER)
        - Defined by assignment (ASSIGNMENT or FIELD_LOAD)
        - Defined by function call assignment (CALL_ASSIGNMENT) - Phase 4.1
        - Defined by field store (FIELD_STORE) - Phase 4.2
        - A source/allocation (not implemented yet)

        This is Step 1 of Algorithm 1 from the Oracle Labs paper.

        Returns:
            Dict with 'type' and statement data, or None if undefined
        """
        # PHASE 6.1: Debug logging for function=None cases
        if ap.function is None and ap.file and 'validate' in ap.file:
            print(f"[IFDS] _get_defining_statement: ap={ap.node_id}, function=None", file=sys.stderr)
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

        # PHASE 4.2: Check if tracing a field that was stored (field write)
        # This must come BEFORE general assignment check
        if ap.fields:
            # Check if this field path was written to (x.f = y)
            full_path = f"{ap.base}.{'.'.join(ap.fields)}"

            # PHASE 6.1: Handle function=None (middleware/file-level context)
            if ap.function is None:
                self.repo_cursor.execute("""
                    SELECT file, line, target_var, source_expr, in_function, property_path
                    FROM assignments
                    WHERE file = ? AND property_path = ?
                    ORDER BY line DESC
                    LIMIT 1
                """, (ap.file, full_path))
            else:
                self.repo_cursor.execute("""
                    SELECT file, line, target_var, source_expr, in_function, property_path
                    FROM assignments
                    WHERE file = ? AND property_path = ? AND in_function = ?
                    ORDER BY line DESC
                    LIMIT 1
                """, (ap.file, full_path, ap.function))

            field_store_row = self.repo_cursor.fetchone()
            if field_store_row:
                return {
                    'type': 'FIELD_STORE',
                    'file': field_store_row['file'],
                    'line': field_store_row['line'],
                    'target_path': full_path,
                    'source_expr': field_store_row['source_expr'],
                    'in_function': field_store_row['in_function']  # PHASE 6.1: Include for function scope tracking
                }

        # Check if it's defined by assignment
        # Query assignments table
        if ap.fields:
            # Field access like req.body
            # PHASE 6.1: Extractors may store "req.body" as single target_var OR as base="req" + property_path="req.body"
            # Try BOTH patterns
            full_path = f"{ap.base}.{'.'.join(ap.fields)}"

            # PHASE 6.1: Handle function=None (middleware/file-level context)
            # Try 1: target_var = full path (e.g., "req.body" as single string)
            # Try 2: target_var = base + property_path = full path
            if ap.function is None:
                self.repo_cursor.execute("""
                    SELECT file, line, target_var, source_expr, in_function, property_path
                    FROM assignments
                    WHERE file = ?
                      AND (
                        target_var = ?
                        OR (target_var = ? AND (property_path = ? OR property_path IS NULL))
                      )
                    ORDER BY line DESC
                    LIMIT 1
                """, (ap.file, full_path, ap.base, full_path))
            else:
                self.repo_cursor.execute("""
                    SELECT file, line, target_var, source_expr, in_function, property_path
                    FROM assignments
                    WHERE file = ? AND in_function = ?
                      AND (
                        target_var = ?
                        OR (target_var = ? AND (property_path = ? OR property_path IS NULL))
                      )
                    ORDER BY line DESC
                    LIMIT 1
                """, (ap.file, ap.function, full_path, ap.base, full_path))
        else:
            # Simple variable
            # PHASE 6.1: Handle function=None (middleware/file-level context)
            if ap.function is None:
                self.repo_cursor.execute("""
                    SELECT file, line, target_var, source_expr, in_function, property_path
                    FROM assignments
                    WHERE file = ? AND target_var = ?
                    ORDER BY line DESC
                    LIMIT 1
                """, (ap.file, ap.base))
            else:
                self.repo_cursor.execute("""
                    SELECT file, line, target_var, source_expr, in_function, property_path
                    FROM assignments
                    WHERE file = ? AND target_var = ? AND in_function = ?
                    ORDER BY line DESC
                    LIMIT 1
                """, (ap.file, ap.base, ap.function))

        assign_row = self.repo_cursor.fetchone()
        if assign_row:
            source_expr = assign_row['source_expr']

            # PHASE 4.1: Check if assignment is from function call (x = func())
            # Detect function calls by presence of '(' but exclude string literals
            if '(' in source_expr and ')' in source_expr:
                # Exclude string literals and property access
                if not source_expr.startswith('"') and not source_expr.startswith("'"):
                    return {
                        'type': 'CALL_ASSIGNMENT',
                        'file': assign_row['file'],
                        'line': assign_row['line'],
                        'target_var': assign_row['target_var'],
                        'callee_expr': source_expr,  # e.g., "getTainted()" or "s3.Bucket(...)"
                        'in_function': assign_row['in_function']  # PHASE 6.1: Include for function scope tracking
                    }

            # Check if it's a field load (source_expr contains '.')
            if '.' in source_expr and not source_expr.startswith('"') and not source_expr.startswith("'"):
                return {
                    'type': 'FIELD_LOAD',
                    'file': assign_row['file'],
                    'line': assign_row['line'],
                    'target_var': assign_row['target_var'],
                    'source_expr': source_expr,
                    'property_path': assign_row['property_path'],
                    'in_function': assign_row['in_function']  # PHASE 6.1: Include for function scope tracking
                }
            else:
                return {
                    'type': 'ASSIGNMENT',
                    'file': assign_row['file'],
                    'line': assign_row['line'],
                    'target_var': assign_row['target_var'],
                    'source_expr': source_expr,
                    'in_function': assign_row['in_function']  # PHASE 6.1: Include for function scope tracking
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

        # Query function_call_args for calls to this function with this parameter
        # Use exact matching - database has exact callee_file_path and callee_function from AST
        self.repo_cursor.execute("""
            SELECT file, line, caller_function, callee_function,
                   argument_expr, param_name
            FROM function_call_args
            WHERE callee_file_path = ?
              AND callee_function = ?
              AND param_name = ?
        """, (ap.file, ap.function, ap.base))

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
        # PHASE 6.1: Use in_function from stmt if available (fixes function=None inheritance bug)
        stmt_function = stmt.get('in_function')

        # Query assignment_sources for source variables
        self.repo_cursor.execute("""
            SELECT source_var_name
            FROM assignment_sources
            WHERE assignment_file = ? AND assignment_line = ? AND assignment_target = ?
        """, (file, line, target_var))

        for row in self.repo_cursor.fetchall():
            source_var = row['source_var_name']

            # Create AccessPath for source variable
            # PHASE 6.1: Use stmt_function instead of ap.function to avoid inheriting None
            source_ap = AccessPath(
                file=file,
                function=stmt_function if stmt_function else ap.function,  # Use actual function scope from assignment
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

    def _flow_function_return_to_caller(self, ap: AccessPath, stmt: Dict) -> List[Tuple[AccessPath, str, Dict]]:
        """Flow function for return-to-caller (PHASE 4.1).

        PHASE 6.1: Enhanced to handle library functions without returns.

        When tracing variable x defined by x = func(arg1, arg2), taint can flow from:
        1. Return values (for project functions with function_returns)
        2. Arguments (for library functions OR when taint propagates through args)

        Algorithm:
        1. Try return-to-caller flow (project functions)
        2. ALWAYS add argument flow (library functions + taint-propagating calls)

        This is NOT a fallback - both flows are valid sources of taint.
        Example: x = parseAsync(req.body) → taint from req.body (argument)
        Example: x = getTainted() → taint from return value
        """
        predecessors = []

        callee_expr = stmt['callee_expr']  # e.g., "getTainted()" or "s3.Bucket(...)"
        file = stmt['file']
        line = stmt['line']
        # PHASE 6.1: Use in_function from stmt
        stmt_function = stmt.get('in_function')

        # Parse function name from call expression
        # Handle cases: func(), obj.method(), require('mod').func()
        func_name = self._parse_function_name_from_call(callee_expr)
        if not func_name:
            if self.debug:
                print(f"[IFDS] Could not parse function name from {callee_expr}", file=sys.stderr)
            return []

        # Query function_call_args to find callee file and full function name
        # This gives us the actual callee location
        self.repo_cursor.execute("""
            SELECT DISTINCT callee_file_path, callee_function
            FROM function_call_args
            WHERE file = ? AND line = ?
              AND (callee_function LIKE ? OR callee_function = ?)
            LIMIT 5
        """, (file, line, f'%{func_name}%', func_name))

        call_sites = self.repo_cursor.fetchall()
        if not call_sites:
            # Try without line number (may be off by 1)
            self.repo_cursor.execute("""
                SELECT DISTINCT callee_file_path, callee_function
                FROM function_call_args
                WHERE file = ?
                  AND (callee_function LIKE ? OR callee_function = ?)
                LIMIT 5
            """, (file, f'%{func_name}%', func_name))
            call_sites = self.repo_cursor.fetchall()

        for call_site in call_sites:
            callee_file = call_site['callee_file_path']
            callee_function = call_site['callee_function']

            if not callee_file or not callee_function:
                continue

            # Query function_returns for this function
            self.repo_cursor.execute("""
                SELECT file, line, function_name, return_expr
                FROM function_returns
                WHERE file = ? AND function_name = ?
                LIMIT 10
            """, (callee_file, callee_function))

            returns = self.repo_cursor.fetchall()
            if not returns:
                # Try with partial match
                self.repo_cursor.execute("""
                    SELECT file, line, function_name, return_expr
                    FROM function_returns
                    WHERE file = ? AND function_name LIKE ?
                    LIMIT 10
                """, (callee_file, f'%{callee_function}%'))
                returns = self.repo_cursor.fetchall()

            for ret in returns:
                # Query function_return_sources to get returned variable(s)
                self.repo_cursor.execute("""
                    SELECT return_var_name
                    FROM function_return_sources
                    WHERE return_file = ? AND return_line = ? AND return_function = ?
                """, (ret['file'], ret['line'], ret['function_name']))

                return_sources = self.repo_cursor.fetchall()

                for src in return_sources:
                    return_var = src['return_var_name']

                    # Skip if return_var is empty or not a valid identifier
                    if not return_var or not isinstance(return_var, str):
                        continue

                    # Create AccessPath for returned variable in callee
                    # Parse as base.field1.field2...
                    parts = return_var.split('.')
                    base = parts[0]
                    fields = tuple(parts[1:]) if len(parts) > 1 else ()

                    # If tracing caller variable with fields (x.f where x = func()),
                    # need to compose: func returns y, so trace y.f
                    if ap.fields:
                        # Compose returned variable with traced fields
                        combined_fields = fields + ap.fields
                    else:
                        combined_fields = fields

                    return_ap = AccessPath(
                        file=callee_file,
                        function=callee_function,
                        base=base,
                        fields=combined_fields
                    )

                    meta = {
                        'file': callee_file,
                        'line': ret['line'],
                        'return': True,
                        'callee': callee_function
                    }

                    predecessors.append((return_ap, 'return_to_caller', meta))

                    if self.debug:
                        print(f"[IFDS] Return-to-caller: {return_ap.node_id} -> {ap.node_id}", file=sys.stderr)

        # PHASE 6.1: ALWAYS add argument flow (library functions + taint-propagating calls)
        # Query assignment_sources for arguments passed to this call
        # This handles library functions (parseAsync, validate, etc.) that have no returns in DB
        self.repo_cursor.execute("""
            SELECT source_var_name
            FROM assignment_sources
            WHERE assignment_file = ? AND assignment_line = ? AND assignment_target = ?
        """, (file, line, ap.base))

        for row in self.repo_cursor.fetchall():
            source_var = row['source_var_name']

            # Skip function names and method names (we want arguments, not callees)
            if '(' in source_var or source_var == func_name:
                continue

            # Create AccessPath for argument variable
            arg_ap = AccessPath(
                file=file,
                function=stmt_function if stmt_function else ap.function,
                base=source_var.split('.')[0],
                fields=tuple(source_var.split('.')[1:]) if '.' in source_var else ()
            )

            meta = {'file': file, 'line': line, 'call_argument': True}
            predecessors.append((arg_ap, 'call_argument', meta))

            if self.debug:
                print(f"[IFDS] Call argument flow: {arg_ap.node_id} -> {ap.node_id}", file=sys.stderr)

        return predecessors

    def _flow_function_field_store(self, ap: AccessPath, stmt: Dict) -> List[Tuple[AccessPath, str, Dict]]:
        """Flow function for field stores (PHASE 4.2) - Algorithm 1 Case 5.

        Implements taint-kill logic for field assignments (x.f = y).

        Algorithm per Oracle Labs paper (page 5, Case 5):
        When tracing b.f1...fn backward through z.g1...gm = y:

        Case 1: EXACT MATCH (z == b AND g1...gm == f1...fm)
            → Trace y (the source of the assignment)

        Case 2: CHILD OVERWRITE (traced path is child of stored path)
            Example: Tracing b.f1.f2 through b.f1 = y
            → KILL TAINT (parent overwritten, child no longer exists)

        Case 3: DIFFERENT FIELDS (no overlap)
            → PASS (identity function, unaffected)

        This is critical for reducing false positives.
        """
        predecessors = []

        target_path = stmt['target_path']  # e.g., "req.body"
        source_expr = stmt['source_expr']  # e.g., "safe_value" or variable
        file = stmt['file']
        line = stmt['line']

        # Parse AccessPath being traced
        traced_path = f"{ap.base}.{'.'.join(ap.fields)}" if ap.fields else ap.base

        # Case 1: Exact match - trace the source
        if traced_path == target_path:
            # Parse source expression to get variable
            source_var = self._parse_arg_variable(source_expr)
            if source_var:
                # Create AccessPath for source
                parts = source_var.split('.')
                base = parts[0]
                fields = tuple(parts[1:]) if len(parts) > 1 else ()

                source_ap = AccessPath(
                    file=file,
                    function=ap.function,
                    base=base,
                    fields=fields
                )

                meta = {'file': file, 'line': line, 'field_store': True}
                predecessors.append((source_ap, 'field_store', meta))

                if self.debug:
                    print(f"[IFDS] Field store exact: {source_ap.node_id} -> {ap.node_id}", file=sys.stderr)
            else:
                # Source is literal (e.g., "safe_string") → KILL TAINT
                if self.debug:
                    print(f"[IFDS] TAINT KILL: {traced_path} = literal at {file}:{line}", file=sys.stderr)
                # Return empty list = path terminates

            return predecessors

        # Case 2: Child overwrite - KILL TAINT
        # Example: Tracing req.body.username through req.body = {...}
        # The parent (req.body) was overwritten, so req.body.username no longer exists
        if traced_path.startswith(target_path + '.'):
            # Traced path is a CHILD of stored path
            # TAINT KILL: Parent overwritten, child no longer valid
            if self.debug:
                print(f"[IFDS] TAINT KILL: {traced_path} (child) overwritten by {target_path} (parent) at {file}:{line}", file=sys.stderr)
            return []  # Empty list = path terminates

        # Case 3: Different fields - PASS (identity function)
        # Example: Tracing req.headers through req.body = y (unrelated fields)
        # The traced path is unaffected by this field store
        if not target_path.startswith(traced_path):
            # Different fields, no aliasing
            # Identity function - trace continues unchanged
            meta = {'file': file, 'line': line, 'field_store_pass': True}
            predecessors.append((ap, 'field_store_pass', meta))

            if self.debug:
                print(f"[IFDS] Field store pass: {traced_path} unaffected by {target_path}", file=sys.stderr)

        return predecessors

    def _flow_function_express_controller_entry(self, ap: AccessPath) -> List[Tuple[AccessPath, str, Dict]]:
        """Flow function for Express controller entry points (PHASE 5).

        When tracing backward hits a controller function entry, check if it's called
        from an Express middleware chain. If so, create predecessor AccessPath at the
        PREVIOUS handler in the chain (typically validation middleware).

        This enables traces to traverse Express's next() callback boundary.

        Example:
            Tracing: area.controller.ts:create function entry
            Query: express_middleware_chains for route calling controller.create
            Find: validateBody at execution_order=1, controller.create at execution_order=2
            Return: AccessPath for validateBody (exit point, same variable)

        This is the missing link that connects controllers to their sanitizing middleware.
        """
        predecessors = []

        if self.debug:
            print(f"[IFDS] → ENTRY: _flow_function_express_controller_entry() for {ap.node_id}", file=sys.stderr)
            print(f"[IFDS]   file={ap.file}, function={ap.function}, base={ap.base}", file=sys.stderr)

        # PHASE 5 handles TWO cases:
        # Case 1: Controller → Middleware (at controller entry point with function context)
        # Case 2: Middleware → Previous Middleware (at middleware file with no function context)

        # Case 1: At controller entry point
        if ap.function:
            # Query: Is this function a controller in a middleware chain?
            # CRITICAL FIX: Don't filter by file - middleware chains store ROUTE file, not CONTROLLER file
            # Instead, match by handler_expr containing function name
            self.repo_cursor.execute("""
                SELECT
                    route_line,
                    route_path,
                    route_method,
                    execution_order,
                    file,
                    handler_expr
                FROM express_middleware_chains
                WHERE handler_type = 'controller'
                ORDER BY route_line, execution_order
            """)

            controller_entries = self.repo_cursor.fetchall()

            if self.debug:
                print(f"[IFDS]   Case 1: Checking {len(controller_entries)} controller entries", file=sys.stderr)

            for entry in controller_entries:
                # Check if handler_expr contains the function name
                # Example: "controller.create" should match function name "create"
                handler_expr = entry['handler_expr']
                if ap.function not in handler_expr:
                    continue

                # Find the PREVIOUS handler in execution chain (middleware that ran before controller)
                prev_order = entry['execution_order'] - 1

                if prev_order < 1:
                    # No middleware before this controller (direct route handler)
                    if self.debug:
                        print(f"[IFDS]   No middleware before controller (execution_order={entry['execution_order']})", file=sys.stderr)
                    continue

                # Query for middleware at prev_order
                self.repo_cursor.execute("""
                    SELECT file, handler_expr, handler_type, route_path, route_method
                    FROM express_middleware_chains
                    WHERE route_line = ?
                      AND route_path = ?
                      AND execution_order = ?
                    LIMIT 1
                """, (entry['route_line'], entry['route_path'], prev_order))

                middleware = self.repo_cursor.fetchone()

                if not middleware:
                    if self.debug:
                        print(f"[IFDS]   No middleware found at execution_order={prev_order}", file=sys.stderr)
                    continue

                # Create AccessPath at middleware exit point
                # CRITICAL FIX: middleware['file'] is the ROUTE file, not where middleware actually is!
                # We need to find where the middleware function (e.g., validateBody) is actually defined
                # For validation middleware, check validation_framework_usage table
                middleware_file = middleware['file']  # Default to route file
                middleware_line = 0  # Default to 0 if not found

                # Check if this is a validation middleware (validateBody, validateParams, validateQuery)
                if 'validate' in middleware['handler_expr'].lower():
                    # Query validation_framework_usage to find actual middleware file AND line
                    # CRITICAL: Need line number for sanitizer matching in _path_goes_through_sanitizer()
                    self.repo_cursor.execute("""
                        SELECT file_path, line
                        FROM validation_framework_usage
                        WHERE is_validator = 1
                        LIMIT 1
                    """)
                    validation_record = self.repo_cursor.fetchone()
                    if validation_record:
                        middleware_file = validation_record['file_path']
                        middleware_line = validation_record['line']
                        if self.debug:
                            print(f"[IFDS]   Resolved validation middleware to: {middleware_file}:{middleware_line}", file=sys.stderr)

                # PHASE 6.1: Map controller variable to request object
                # Controller variables (results, data, etc.) come from req.body/params/query
                # Validation middleware operates on req.body (most common), so trace req.body
                # TODO: Infer req.params/req.query based on middleware type
                middleware_ap = AccessPath(
                    file=middleware_file,  # Actual middleware file (validate.ts)
                    function=None,  # Middleware file context (not scoped to function)
                    base="req",  # Request object (not controller's local variable)
                    fields=("body",)  # Validation middleware validates req.body
                )

                meta = {
                    'route': entry['route_path'],
                    'method': entry['route_method'],
                    'from_order': entry['execution_order'],
                    'to_order': prev_order,
                    'middleware_expr': middleware['handler_expr'],
                    'line': middleware_line  # CRITICAL: Include line for sanitizer matching
                }

                predecessors.append((middleware_ap, 'express_middleware_chain', meta))

                if self.debug:
                    print(f"[IFDS] ✓✓✓ EXPRESS MIDDLEWARE CHAIN TRAVERSAL ✓✓✓", file=sys.stderr)
                    print(f"[IFDS]   From: {ap.file}:{ap.function} (controller, order={entry['execution_order']})", file=sys.stderr)
                    print(f"[IFDS]   To:   {middleware['file']} (middleware '{middleware['handler_expr']}', order={prev_order})", file=sys.stderr)
                    print(f"[IFDS]   Route: {meta['method']} {meta['route']}", file=sys.stderr)

        # Case 2: At middleware file (function=None)
        # Check if we're at a middleware location and can traverse to previous middleware
        elif ap.file:
            if self.debug:
                print(f"[IFDS]   Case 2: Checking if {ap.file} is middleware in any chain", file=sys.stderr)

            # Query: Is this file a middleware in any chain?
            # We need to find chains where this file appears as middleware
            # Note: ap.file might be validate.ts (actual middleware file) but express_middleware_chains stores route file
            # So we need to reverse-lookup: which routes call middleware that resolves to this file?

            # For validation middleware, we can check validation_framework_usage
            self.repo_cursor.execute("""
                SELECT file_path, line
                FROM validation_framework_usage
                WHERE is_validator = 1
                  AND file_path = ?
                LIMIT 1
            """, (ap.file,))

            validation_match = self.repo_cursor.fetchone()

            if validation_match:
                if self.debug:
                    print(f"[IFDS]   Matched validation middleware at {ap.file}", file=sys.stderr)

                # This is a validation middleware file - find which routes use it
                # Query middleware chains for validation middleware
                # Get handler expressions from validation_framework_usage table (database-driven)
                self.repo_cursor.execute("""
                    SELECT DISTINCT method
                    FROM validation_framework_usage
                    WHERE is_validator = 1
                """)

                validation_methods = [row['method'] for row in self.repo_cursor.fetchall()]

                if not validation_methods:
                    if self.debug:
                        print(f"[IFDS]   No validation methods found in database", file=sys.stderr)
                    # Continue without validation middleware
                else:
                    # Query middleware chains matching known validation methods
                    placeholders = ','.join('?' * len(validation_methods))
                    self.repo_cursor.execute(f"""
                        SELECT route_line, route_path, route_method, execution_order, file, handler_expr
                        FROM express_middleware_chains
                        WHERE handler_type = 'middleware'
                          AND (
                            {' OR '.join(f"handler_expr LIKE ?" for _ in validation_methods)}
                          )
                        ORDER BY route_line, execution_order
                    """, [f'%{method}%' for method in validation_methods])

                middleware_entries = self.repo_cursor.fetchall()

                for entry in middleware_entries:
                    # Find previous middleware in this chain
                    prev_order = entry['execution_order'] - 1
                    if prev_order < 1:
                        continue  # No previous middleware

                    # Query for previous middleware
                    self.repo_cursor.execute("""
                        SELECT file, handler_expr, handler_type, route_path, route_method
                        FROM express_middleware_chains
                        WHERE route_line = ? AND route_path = ? AND execution_order = ?
                        LIMIT 1
                    """, (entry['route_line'], entry['route_path'], prev_order))

                    prev_middleware = self.repo_cursor.fetchone()
                    if not prev_middleware:
                        continue

                    # Create AccessPath at previous middleware
                    # For now, just use the route file (prev_middleware['file'])
                    # TODO: Resolve actual middleware file location (Phase 5.2)
                    prev_middleware_ap = AccessPath(
                        file=prev_middleware['file'],  # Route file for now
                        function=None,  # Middleware context
                        base=ap.base,  # Same variable
                        fields=ap.fields  # Same field path
                    )

                    meta = {
                        'route': entry['route_path'],
                        'method': entry['route_method'],
                        'from_order': entry['execution_order'],
                        'to_order': prev_order,
                        'middleware_expr': prev_middleware['handler_expr'],
                        'line': 0  # TODO: Resolve line for non-validation middleware
                    }

                    predecessors.append((prev_middleware_ap, 'express_middleware_chain', meta))

                    if self.debug:
                        print(f"[IFDS] ✓✓✓ MIDDLEWARE CHAIN CONTINUATION ✓✓✓", file=sys.stderr)
                        print(f"[IFDS]   From: {ap.file} (middleware, order={entry['execution_order']})", file=sys.stderr)
                        print(f"[IFDS]   To:   {prev_middleware['file']} (middleware '{prev_middleware['handler_expr']}', order={prev_order})", file=sys.stderr)

        if self.debug:
            print(f"[IFDS] ← EXIT: Returning {len(predecessors)} middleware predecessors", file=sys.stderr)

        return predecessors

    def _flow_function_cross_boundary_bridge(self, ap: AccessPath) -> List[Tuple[AccessPath, str, Dict]]:
        """Flow function for cross-boundary flows (Frontend → Backend) - PART 3.

        When tracing backward hits a backend API source (req.body/params/query),
        this bridges the gap to frontend API calls that send data to this endpoint.

        This connects:
        - Frontend: fetch('/api/users', {body: userData})
        - Backend: router.post('/users', (req) => { req.body })

        Algorithm:
        1. Check if we're at req.body/params/query (backend API source)
        2. Find the backend API endpoint for this controller/function
        3. Query frontend_api_calls for matching URL and method
        4. Create AccessPaths for frontend body variables
        5. Handle field propagation (req.body.username → userData.username)

        Returns:
            List of (frontend_access_path, edge_type, metadata) tuples
        """
        predecessors = []

        if self.debug:
            print(f"[IFDS] → ENTRY: _flow_function_cross_boundary_bridge() for {ap.node_id}", file=sys.stderr)
            print(f"[IFDS]   base={ap.base}, fields={ap.fields}", file=sys.stderr)

        # Step 1: Check if we're at a backend API source (req.body/params/query)
        if ap.base != "req":
            return []  # Not a request object

        if not ap.fields or ap.fields[0] not in ("body", "params", "query"):
            return []  # Not an API source field

        # We're at req.body/params/query - this is a backend API source!
        source_type = ap.fields[0]  # "body", "params", or "query"
        remaining_fields = ap.fields[1:] if len(ap.fields) > 1 else ()  # e.g., ("username",) from req.body.username

        if self.debug:
            print(f"[IFDS]   ✓ At backend API source: req.{source_type}", file=sys.stderr)
            if remaining_fields:
                print(f"[IFDS]     With fields: {remaining_fields}", file=sys.stderr)

        # Step 2: Find the backend API endpoint for this function
        # Query api_endpoints to find which route this controller handles
        if not ap.function:
            if self.debug:
                print(f"[IFDS]   ✗ No function context, cannot determine API endpoint", file=sys.stderr)
            return []

        # The handler_function field contains patterns like:
        # - "controller.create"
        # - "handler(controller.create)"
        # - "FacilityController.update"
        # We need to match if ap.function appears in these patterns

        # Try matching where handler_function contains our function name
        self.repo_cursor.execute("""
            SELECT method, pattern, path, file, handler_function
            FROM api_endpoints
            WHERE (file = ? OR file LIKE ?)
              AND (handler_function LIKE ? OR handler_function LIKE ? OR handler_function LIKE ?)
            LIMIT 10
        """, (ap.file, f'%{ap.file.split("/")[-1]}%',  # Match file or just filename
              f'%{ap.function}%',  # Direct match
              f'%.{ap.function}%',  # controller.create pattern
              f'%({ap.function})%'  # handler(controller.create) pattern
        ))

        backend_endpoints = self.repo_cursor.fetchall()

        if not backend_endpoints:
            if self.debug:
                print(f"[IFDS]   ✗ No API endpoint found for {ap.file}:{ap.function}", file=sys.stderr)
            return []

        if self.debug:
            print(f"[IFDS]   Found {len(backend_endpoints)} backend endpoints", file=sys.stderr)

        # Step 3: For each backend endpoint, find matching frontend API calls
        for endpoint in backend_endpoints:
            method = endpoint['method']
            # Use pattern (e.g., "/users/:id") or path (e.g., "/users")
            route = endpoint['pattern'] if endpoint['pattern'] else endpoint['path']
            handler_func = endpoint['handler_function']

            if not route:
                continue

            if self.debug:
                print(f"[IFDS]   Checking backend: {method} {route} (handler: {handler_func})", file=sys.stderr)

            # Step 4: Query frontend_api_calls for matching calls
            # Handle route patterns - convert Express :param to template literal pattern
            # Backend: /users/:id → Frontend: /users/${id} or /users/123

            # For exact matches
            self.repo_cursor.execute("""
                SELECT file, line, method, url_literal, body_variable, function_name
                FROM frontend_api_calls
                WHERE method = ? AND url_literal = ?
                LIMIT 10
            """, (method, route))

            frontend_calls = list(self.repo_cursor.fetchall())

            # Also check with /api/v1 prefix (common pattern)
            if not frontend_calls and not route.startswith('/api'):
                api_route = f'/api/v1{route}'
                self.repo_cursor.execute("""
                    SELECT file, line, method, url_literal, body_variable, function_name
                    FROM frontend_api_calls
                    WHERE method = ? AND url_literal = ?
                    LIMIT 10
                """, (method, api_route))
                frontend_calls.extend(self.repo_cursor.fetchall())

            # For pattern matching (e.g., /users/:id matches /users/${userId})
            if ':' in route:
                # Convert :param to % for LIKE query
                # /users/:id → /users/%
                pattern = route.replace(':', '%')
                self.repo_cursor.execute("""
                    SELECT file, line, method, url_literal, body_variable, function_name
                    FROM frontend_api_calls
                    WHERE method = ? AND url_literal LIKE ?
                    LIMIT 10
                """, (method, pattern))
                frontend_calls.extend(self.repo_cursor.fetchall())

            if self.debug:
                print(f"[IFDS]   Found {len(frontend_calls)} matching frontend calls", file=sys.stderr)

            # Step 5: Create AccessPaths for each frontend call's body variable
            for fe_call in frontend_calls:
                # Skip if no body variable (GET requests, etc.)
                if not fe_call['body_variable']:
                    continue

                # Only trace body variables for req.body, not req.params/query
                # (params and query come from URL, not request body)
                if source_type == "body":
                    # Parse body variable (e.g., "userData" or "formData.user")
                    body_var = fe_call['body_variable']
                    parts = body_var.split('.')
                    base = parts[0]
                    base_fields = tuple(parts[1:]) if len(parts) > 1 else ()

                    # Compose fields: if tracing req.body.username,
                    # and frontend sends userData, trace userData.username
                    combined_fields = base_fields + remaining_fields

                    frontend_ap = AccessPath(
                        file=fe_call['file'],
                        function=fe_call['function_name'] if fe_call['function_name'] else 'global',
                        base=base,
                        fields=combined_fields
                    )

                    meta = {
                        'file': fe_call['file'],
                        'line': fe_call['line'],
                        'method': fe_call['method'],
                        'url': fe_call['url_literal'],
                        'backend_route': route,
                        'backend_function': ap.function,
                        'cross_boundary': True
                    }

                    predecessors.append((frontend_ap, 'cross_boundary_api', meta))

                    if self.debug:
                        print(f"[IFDS] ✓✓✓ CROSS-BOUNDARY BRIDGE ✓✓✓", file=sys.stderr)
                        print(f"[IFDS]   Frontend: {frontend_ap.node_id}", file=sys.stderr)
                        print(f"[IFDS]   API call: {meta['method']} {meta['url']} (line {meta['line']})", file=sys.stderr)
                        print(f"[IFDS]   Backend:  {ap.node_id}", file=sys.stderr)
                        print(f"[IFDS]   Route:    {meta['backend_route']} → {meta['backend_function']}", file=sys.stderr)

        if self.debug:
            print(f"[IFDS] ← EXIT: Returning {len(predecessors)} cross-boundary predecessors", file=sys.stderr)

        return predecessors

    def _parse_function_name_from_call(self, call_expr: str) -> Optional[str]:
        """Parse function name from call expression.

        Examples:
            "getTainted()" → "getTainted"
            "s3.Bucket(...)" → "Bucket"
            "User.findAll({ limit, offset })" → "findAll"
            "require('child_process').execSync" → "execSync"

        Returns:
            Function name or None if cannot parse
        """
        if not call_expr or '(' not in call_expr:
            return None

        # Remove arguments (everything from first '(' onwards)
        before_args = call_expr.split('(')[0].strip()

        # Handle method calls: obj.method → method
        if '.' in before_args:
            parts = before_args.split('.')
            # Get last part (method name)
            return parts[-1].strip()

        # Simple function call
        return before_args.strip()

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
