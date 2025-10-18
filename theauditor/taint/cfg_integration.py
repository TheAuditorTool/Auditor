"""Control Flow Graph integration for flow-sensitive taint analysis.

This module bridges the gap between CFG data and taint propagation,
enabling path-aware vulnerability detection.

Schema Contract:
    All queries use build_query() for schema compliance.
    Table existence is guaranteed by schema contract - no checks needed.
"""

import os
import sys
import sqlite3
from typing import Dict, List, Set, Any, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, field

from theauditor.indexer.schema import build_query
from .database import (
    get_block_for_line,
    get_paths_between_blocks,
    get_block_statements,
    get_cfg_for_function,
    check_cfg_available
)
from .propagation import has_sanitizer_between
from .registry import TaintRegistry
from .core import TaintPath  # ARCHITECTURAL FIX: Use proper data structure


@dataclass
class BlockTaintState:
    """Represents taint state for a specific CFG block.
    
    This tracks which variables are tainted when entering/exiting a block,
    allowing for path-sensitive analysis.
    """
    block_id: int
    tainted_vars: Set[str] = field(default_factory=set)
    sanitized_vars: Set[str] = field(default_factory=set)
    conditions: List[str] = field(default_factory=list)  # Path conditions to reach this block
    
    def is_tainted(self, var_name: str) -> bool:
        """Check if a variable is tainted in this block."""
        return var_name in self.tainted_vars and var_name not in self.sanitized_vars
    
    def add_taint(self, var_name: str) -> None:
        """Mark a variable as tainted."""
        self.tainted_vars.add(var_name)
        self.sanitized_vars.discard(var_name)

    def sanitize(self, var_name: str) -> None:
        """Mark a variable as sanitized."""
        self.sanitized_vars.add(var_name)
    
    def merge(self, other: 'BlockTaintState') -> 'BlockTaintState':
        """Merge taint state from another block (for join points)."""
        # Conservative: variable is tainted if tainted in ANY incoming path
        merged = BlockTaintState(self.block_id)
        merged.tainted_vars = self.tainted_vars | other.tainted_vars
        # Variable is sanitized only if sanitized in ALL paths
        merged.sanitized_vars = self.sanitized_vars & other.sanitized_vars
        merged.conditions = list(set(self.conditions + other.conditions))
        return merged
    
    def copy(self) -> 'BlockTaintState':
        """Create a deep copy of this state."""
        return BlockTaintState(
            block_id=self.block_id,
            tainted_vars=self.tainted_vars.copy(),
            sanitized_vars=self.sanitized_vars.copy(),
            conditions=self.conditions.copy()
        )


class PathAnalyzer:
    """Analyzes execution paths through CFG for taint propagation."""
    
    def __init__(self, cursor: sqlite3.Cursor, file_path: str, function_name: str) -> None:
        """
        Initialize path analyzer for a specific function.

        Args:
            cursor: Database cursor
            file_path: Path to source file
            function_name: Name of function to analyze (will be normalized)
        """
        self.cursor = cursor
        self.file_path = file_path.replace("\\", "/")

        # CRITICAL FIX: Store BOTH original and normalized names
        # assignments/function_call_args store: "accountService.createAccount"
        # cfg_blocks stores: "createAccount"
        self.original_function_name = function_name  # Keep original for assignments/calls

        # Normalize for CFG lookup only
        self.function_name = self._normalize_function_name(function_name)
        self.cfg = get_cfg_for_function(cursor, file_path, self.function_name)
        self.debug = os.environ.get("THEAUDITOR_TAINT_DEBUG") or os.environ.get("THEAUDITOR_CFG_DEBUG")

        # Initialize registry for sanitizer checking
        self.registry = TaintRegistry()

        # Build block lookup
        self.blocks = {b["id"]: b for b in self.cfg["blocks"]}

        # Build adjacency lists
        self.successors = defaultdict(list)
        self.predecessors = defaultdict(list)
        for edge in self.cfg["edges"]:
            self.successors[edge["source"]].append((edge["target"], edge["type"]))
            self.predecessors[edge["target"]].append((edge["source"], edge["type"]))

    def _normalize_function_name(self, func_name: str) -> str:
        """Normalize function name for CFG lookup.

        CRITICAL FIX: Strip object/class prefix to match cfg_blocks table naming.

        Examples:
            'accountService.createAccount' → 'createAccount'
            'BatchController.constructor' → 'constructor'
            'ApiService.setupInterceptors' → 'setupInterceptors'
            'createAccount' → 'createAccount' (unchanged)

        WHY: function_call_args stores fully qualified names but cfg_blocks
        stores method names only. This normalization bridges the gap.

        Returns:
            Normalized function name for CFG lookup
        """
        if '.' in func_name:
            # Split on last dot to handle nested objects: a.b.c → c
            return func_name.split('.')[-1]
        return func_name

    def find_vulnerable_paths(self, source_line: int, sink_line: int,
                            initial_tainted_var: str, max_paths: int = 100) -> List[Dict[str, Any]]:
        """
        Find all paths from source to sink where taint reaches sink.
        
        Stage 2 Enhancement: Improved path tracking with condition extraction
        and path merging at join points.
        
        Args:
            source_line: Line where taint originates
            sink_line: Line where sink is located
            initial_tainted_var: Variable that is initially tainted
            max_paths: Maximum number of paths to analyze (Stage 2 addition)
            
        Returns:
            List of vulnerable path dictionaries with conditions
        """
        if self.debug:
            print(f"\n[CFG] Finding vulnerable paths in {self.function_name}", file=sys.stderr)
            print(f"[CFG]   Source: line {source_line}, var: {initial_tainted_var}", file=sys.stderr)
            print(f"[CFG]   Sink: line {sink_line}", file=sys.stderr)
            print(f"[CFG]   Max paths limit: {max_paths}", file=sys.stderr)
        
        # Find blocks containing source and sink
        source_block = get_block_for_line(self.cursor, self.file_path, source_line, self.function_name)
        sink_block = get_block_for_line(self.cursor, self.file_path, sink_line, self.function_name)
        
        if not source_block or not sink_block:
            if self.debug:
                print(f"[CFG]   WARNING: Could not find blocks for source/sink", file=sys.stderr)
            return []
        
        if self.debug:
            print(f"[CFG]   Source block: {source_block['id']} ({source_block['type']})", file=sys.stderr)
            print(f"[CFG]   Sink block: {sink_block['id']} ({sink_block['type']})", file=sys.stderr)
        
        # Stage 2: Enhanced path enumeration with limit
        paths = get_paths_between_blocks(
            self.cursor, self.file_path, 
            source_block["id"], sink_block["id"],
            max_paths=max_paths  # Stage 2: Configurable limit
        )
        
        if self.debug:
            print(f"[CFG]   Found {len(paths)} paths from source to sink", file=sys.stderr)
            if len(paths) == max_paths:
                print(f"[CFG]   WARNING: Path limit reached, may have missed some paths", file=sys.stderr)
        
        # Stage 2: Track states at join points for merging
        join_point_states = {}  # block_id -> list of incoming states
        vulnerable_paths = []
        
        for path_idx, path_blocks in enumerate(paths):
            if self.debug and path_idx < 3:  # Show first 3 paths
                print(f"[CFG]   Analyzing path {path_idx + 1}: {' -> '.join(map(str, path_blocks))}", file=sys.stderr)
            
            # Analyze taint propagation along this path
            is_vulnerable, path_info = self._analyze_path_taint_enhanced(
                path_blocks, initial_tainted_var, source_line, sink_line,
                join_point_states
            )
            
            if is_vulnerable:
                vulnerable_paths.append(path_info)
                if self.debug:
                    print(f"[CFG]   VULNERABLE PATH {path_idx + 1}: {' -> '.join(map(str, path_blocks))}", file=sys.stderr)
                    if path_info.get("conditions"):
                        print(f"[CFG]     Conditions: {path_info['conditions']}", file=sys.stderr)
        
        if self.debug:
            print(f"[CFG]   Result: {len(vulnerable_paths)}/{len(paths)} paths are vulnerable", file=sys.stderr)
        
        return vulnerable_paths
    
    def _analyze_path_taint(self, path_blocks: List[int], tainted_var: str,
                           source_line: int, sink_line: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Analyze if taint propagates along a specific path.
        
        Args:
            path_blocks: List of block IDs forming the path
            tainted_var: Initially tainted variable
            source_line: Source line number
            sink_line: Sink line number
            
        Returns:
            Tuple of (is_vulnerable, path_info)
        """
        # Start with initial taint state
        current_state = BlockTaintState(path_blocks[0])
        current_state.add_taint(tainted_var)
        
        # Track conditions along path
        path_conditions = []
        
        # Propagate taint through each block
        for i, block_id in enumerate(path_blocks):
            block = self.blocks.get(block_id)
            if not block:
                continue
            
            # Add block condition if it's a conditional block
            if block["type"] == "condition" and block.get("condition"):
                # Determine which branch we took
                if i + 1 < len(path_blocks):
                    next_block = path_blocks[i + 1]
                    # Find edge type
                    for target, edge_type in self.successors[block_id]:
                        if target == next_block:
                            if edge_type == "true":
                                path_conditions.append(f"if ({block['condition']})")
                            elif edge_type == "false":
                                path_conditions.append(f"if not ({block['condition']})")
                            break
            
            # Check for sanitizers in this block
            current_state = self._process_block_for_sanitizers(current_state, block)
            
            # Check for new taints from assignments in this block
            current_state = self._process_block_for_assignments(current_state, block)
        
        # Check if taint reaches sink
        is_vulnerable = current_state.is_tainted(tainted_var)
        
        path_info = {
            "blocks": path_blocks,
            "conditions": path_conditions,
            "tainted_vars": list(current_state.tainted_vars),
            "sanitized_vars": list(current_state.sanitized_vars),
            "is_vulnerable": is_vulnerable
        }
        
        return is_vulnerable, path_info
    
    def _process_block_for_sanitizers(self, state: BlockTaintState,
                                     block: Dict[str, Any]) -> BlockTaintState:
        """
        Check if block contains sanitizers that clean tainted data.

        Args:
            state: Current taint state
            block: CFG block to process

        Returns:
            Updated taint state

        Schema Contract:
            Queries cfg_block_statements and function_call_args tables (guaranteed to exist)
        """
        new_state = state.copy()

        # Get statements in this block - query database instead of string matching
        block_id = block.get("id")
        if block_id:
            # Query cfg_block_statements for calls in this block
            query = build_query('cfg_block_statements',
                ['statement_type', 'line', 'statement_text'],
                where="block_id = ? AND statement_type = 'call'",
                order_by="line"
            )
            self.cursor.execute(query, (block_id,))

            for stmt_type, line, stmt_text in self.cursor.fetchall():
                # Query function_call_args to get exact function name
                args_query = build_query('function_call_args',
                    ['callee_function', 'argument_expr'],
                    where="file = ? AND line = ?"
                )
                self.cursor.execute(args_query, (self.file_path, line))

                for callee, arg_expr in self.cursor.fetchall():
                    # Check if callee is a sanitizer using registry
                    if self.registry.is_sanitizer(callee):
                        # Find which variable is being sanitized
                        for var in list(new_state.tainted_vars):
                            # Minimal string check on EXTRACTED argument expression
                            if var in arg_expr:
                                new_state.sanitize(var)
                                if self.debug:
                                    print(f"[CFG]     Sanitizer {callee} found for {var} at line {line}", file=sys.stderr)

        return new_state
    
    def _analyze_path_taint_enhanced(self, path_blocks: List[int], tainted_var: str,
                                    source_line: int, sink_line: int,
                                    join_point_states: Dict[int, List[BlockTaintState]]) -> Tuple[bool, Dict[str, Any]]:
        """
        Stage 2: Enhanced path analysis with better condition tracking and join point merging.
        
        Args:
            path_blocks: List of block IDs forming the path
            tainted_var: Initially tainted variable
            source_line: Source line number
            sink_line: Sink line number
            join_point_states: States at join points for merging
            
        Returns:
            Tuple of (is_vulnerable, path_info)
        """
        # Start with initial taint state
        current_state = BlockTaintState(path_blocks[0])
        current_state.add_taint(tainted_var)
        
        # Track detailed conditions along path
        path_conditions = []
        condition_stack = []  # For nested conditions
        
        # Process each block in the path
        for i, block_id in enumerate(path_blocks):
            block = self.blocks.get(block_id)
            if not block:
                continue
            
            # Stage 2: Check if this is a join point (multiple predecessors)
            predecessors = self.predecessors.get(block_id, [])
            if len(predecessors) > 1 and block_id in join_point_states:
                # Merge states from different incoming paths
                if self.debug:
                    print(f"[CFG]     Merging states at join point block {block_id}", file=sys.stderr)
                
                for incoming_state in join_point_states[block_id]:
                    current_state = current_state.merge(incoming_state)
            
            # Stage 2: Enhanced condition extraction
            if block["type"] == "condition":
                condition = block.get("condition", "")
                if condition:
                    # Determine branch taken
                    if i + 1 < len(path_blocks):
                        next_block = path_blocks[i + 1]
                        
                        # Find the edge type to determine branch
                        for target, edge_type in self.successors.get(block_id, []):
                            if target == next_block:
                                # Format condition based on branch
                                if edge_type == "true":
                                    formatted_cond = f"if ({condition})"
                                    condition_stack.append((condition, True))
                                elif edge_type == "false":
                                    formatted_cond = f"if not ({condition})"
                                    condition_stack.append((condition, False))
                                else:
                                    formatted_cond = f"when ({condition})"
                                
                                path_conditions.append({
                                    "block": block_id,
                                    "condition": formatted_cond,
                                    "type": edge_type,
                                    "line": block.get("start_line", 0)
                                })
                                break
            
            # Stage 2: Handle loop conditions specially
            elif block["type"] == "loop_condition":
                condition = block.get("condition", "")
                if condition:
                    # Check if we're entering or exiting the loop
                    if i + 1 < len(path_blocks):
                        next_block = path_blocks[i + 1]
                        for target, edge_type in self.successors.get(block_id, []):
                            if target == next_block:
                                if edge_type == "true":
                                    path_conditions.append({
                                        "block": block_id,
                                        "condition": f"while ({condition})",
                                        "type": "loop_enter",
                                        "line": block.get("start_line", 0)
                                    })
                                else:
                                    path_conditions.append({
                                        "block": block_id,
                                        "condition": f"exit loop ({condition})",
                                        "type": "loop_exit",
                                        "line": block.get("start_line", 0)
                                    })
                                break
            
            # Check for sanitizers in this block
            current_state = self._process_block_for_sanitizers(current_state, block)
            
            # Check for new taints from assignments
            current_state = self._process_block_for_assignments(current_state, block)
            
            # Stage 2: Store state at potential join points
            successors = self.successors.get(block_id, [])
            for succ_block, _ in successors:
                if len(self.predecessors.get(succ_block, [])) > 1:
                    # This successor is a join point
                    if succ_block not in join_point_states:
                        join_point_states[succ_block] = []
                    join_point_states[succ_block].append(current_state.copy())

        # SURGICAL FIX: Check if ANY tainted var reaches sink, not just initial var
        # Bug: Only checked if initial_tainted_var reached sink, missing propagated vars
        # Example: data → newUser → Account.create(newUser) would fail if we only check "data"
        is_vulnerable = False

        # Get sink's actual arguments from database
        sink_args_query = build_query('function_call_args', ['argument_expr'],
                                      where="file = ? AND line = ?")
        self.cursor.execute(sink_args_query, (self.file_path, sink_line))
        sink_args_result = self.cursor.fetchone()

        if sink_args_result:
            argument_expr = sink_args_result[0]
            # SURGICAL FIX: Check if ANY variable tainted at sink point is used in sink arguments
            # This handles propagated vars: data → newUser, both checked
            for var in current_state.tainted_vars:
                if var in argument_expr and current_state.is_tainted(var):
                    is_vulnerable = True
                    if self.debug:
                        print(f"[CFG]     VULNERABLE: Tainted var '{var}' reaches sink at line {sink_line} via args '{argument_expr[:80]}'", file=sys.stderr)
                    break

        # Stage 2: Enhanced path info with detailed conditions
        path_info = {
            "blocks": path_blocks,
            "conditions": path_conditions,
            "condition_summary": self._summarize_conditions(path_conditions),
            "tainted_vars": list(current_state.tainted_vars),
            "sanitized_vars": list(current_state.sanitized_vars),
            "is_vulnerable": is_vulnerable,
            "path_complexity": len(path_conditions)  # Metric for path complexity
        }

        return is_vulnerable, path_info
    
    def _summarize_conditions(self, conditions: List[Dict[str, Any]]) -> str:
        """
        Stage 2: Create a human-readable summary of path conditions.
        
        Args:
            conditions: List of condition dictionaries
            
        Returns:
            Human-readable condition summary
        """
        if not conditions:
            return "Direct path (no conditions)"
        
        summary_parts = []
        for cond in conditions:
            if cond["type"] == "true":
                summary_parts.append(f"{cond['condition']} is TRUE")
            elif cond["type"] == "false":
                summary_parts.append(f"{cond['condition']} is FALSE")
            elif cond["type"] == "loop_enter":
                summary_parts.append(f"Enter loop: {cond['condition']}")
            elif cond["type"] == "loop_exit":
                summary_parts.append(f"Exit loop: {cond['condition']}")
        
        return " AND ".join(summary_parts) if summary_parts else "Unknown conditions"
    
    def _process_block_for_assignments(self, state: BlockTaintState,
                                      block: Dict[str, Any]) -> BlockTaintState:
        """
        Track taint propagation through assignments in block.

        Args:
            state: Current taint state
            block: CFG block to process

        Returns:
            Updated taint state

        Schema Contract:
            Queries assignments table (guaranteed to exist)
        """
        new_state = state.copy()

        # Get assignments in this block from database
        if block["start_line"] and block["end_line"]:
            # CRITICAL FIX: Must filter by in_function to avoid pollution from nested functions
            # Example: createApp (lines 19-137) contains setHeaders (lines 92-104) and _callback (110-129)
            # Without in_function filter, we'd get assignments from ALL three functions in overlapping ranges
            query = build_query('assignments',
                ['target_var', 'source_expr'],
                where="file = ? AND in_function = ? AND line BETWEEN ? AND ?"
            )
            # CRITICAL FIX: Use original_function_name (FULL name like "AccountController.list")
            # NOT normalized name, because assignments table stores FULL names
            self.cursor.execute(query, (
                self.file_path,
                self.original_function_name,  # Use FULL name for assignments table
                block["start_line"],
                block["end_line"]
            ))

            for target_var, source_expr in self.cursor.fetchall():
                # Check if source expression contains tainted variables
                # CRITICAL FIX: Create a list copy to avoid "Set changed size during iteration" error
                # This bug only affects Python files because they have CFG data and assignments
                # JavaScript files in PlantFlow also have this, but Python's set iteration is stricter
                for tainted_var in list(new_state.tainted_vars):
                    if tainted_var in source_expr:
                        # Target becomes tainted
                        new_state.add_taint(target_var)
                        if self.debug:
                            print(f"[CFG]     Taint propagated: {tainted_var} -> {target_var}", file=sys.stderr)

        return new_state
    
    # DELETED: analyze_loop_with_fixed_point() - 52 lines of string parsing dead code
    # Calls _is_taint_propagating_operation() and _propagate_loop_taint() which parse statement text
    # Loop analysis rarely used and broken - delete to enforce database-query approach
    
    def _get_loop_body_blocks(self, loop_block_id: int) -> List[int]:
        """Get all blocks that are part of the loop body."""
        loop_blocks = []
        
        # Find blocks dominated by the loop header
        # Simplified: find blocks between loop header and back edge
        visited = set()
        queue = [loop_block_id]
        
        while queue:
            block_id = queue.pop(0)
            if block_id in visited:
                continue
            visited.add(block_id)
            
            # Add successors that are part of the loop
            for succ_id, edge_type in self.successors.get(block_id, []):
                if edge_type == "true":  # Loop body path
                    loop_blocks.append(succ_id)
                    queue.append(succ_id)
                elif succ_id == loop_block_id:  # Back edge
                    break
        
        return loop_blocks
    
    def _get_block_statements(self, block_id: int) -> List[Dict[str, Any]]:
        """Get statements in a block from the database.

        Schema Contract:
            Queries cfg_block_statements table (guaranteed to exist)
        """
        query = build_query('cfg_block_statements',
            ['statement_type', 'statement_text', 'line'],
            where="block_id = ?",
            order_by="statement_order"
        )
        self.cursor.execute(query, (block_id,))

        return [
            {"type": row[0], "text": row[1], "line": row[2]}
            for row in self.cursor.fetchall()
        ]
    
    # DELETED: _is_taint_propagating_operation() - 13 lines of string parsing cancer
    # Parsed statement text instead of querying database
    # Example: "if '+=' in text" - STRING PARSING, not database query
    
    # DELETED: _propagate_loop_taint() - 22 lines of string parsing cancer
    # Parsed statement text with string operations: text.split("+=")[0].strip()
    # Should query assignments table instead
    
    def _apply_widening(self, state: BlockTaintState, loop_blocks: List[int]) -> BlockTaintState:
        """
        Conservative widening when fixed-point doesn't converge.

        Marks all variables modified in loop as potentially tainted.

        Schema Contract:
            Queries assignments table (guaranteed to exist)
        """
        widened_state = state.copy()

        # Find all variables assigned in loop body
        for block_id in loop_blocks:
            block = self.blocks.get(block_id)
            if not block or not block.get("start_line"):
                continue

            query = build_query('assignments',
                ['DISTINCT target_var'],
                where="file = ? AND line BETWEEN ? AND ?"
            )
            self.cursor.execute(query, (self.file_path, block["start_line"], block["end_line"]))

            for target_var, in self.cursor.fetchall():
                # Conservative: if any tainted var exists, all loop vars become tainted
                if state.tainted_vars:
                    widened_state.add_taint(target_var)

        return widened_state


def trace_flow_sensitive(cursor: sqlite3.Cursor, source: Dict[str, Any],
                        sink: Dict[str, Any], source_function: Dict[str, Any],
                        max_paths: int = 100) -> List[Dict[str, Any]]:
    """
    Perform flow-sensitive taint analysis using CFG.
    
    Stage 2 Enhancement: Improved with configurable path limits and
    enhanced condition tracking.
    
    This is the main entry point for CFG-based taint analysis.
    
    Args:
        cursor: Database cursor
        source: Taint source information
        sink: Security sink information
        source_function: Function containing the source
        max_paths: Maximum paths to analyze (Stage 2: now used)
        
    Returns:
        List of vulnerable path dictionaries with conditions
    """
    debug = os.environ.get("THEAUDITOR_TAINT_DEBUG") or os.environ.get("THEAUDITOR_CFG_DEBUG")
    
    if debug:
        print(f"\n[CFG] Starting flow-sensitive analysis (Stage 2)", file=sys.stderr)
        print(f"[CFG] Source: {source['pattern']} at {source['file']}:{source['line']}", file=sys.stderr)
        print(f"[CFG] Sink: {sink['pattern']} at {sink['file']}:{sink['line']}", file=sys.stderr)
        print(f"[CFG] Max paths: {max_paths}", file=sys.stderr)
    
    # Check if CFG data is available
    if not check_cfg_available(cursor):
        if debug:
            print(f"[CFG] No CFG data available, falling back to flow-insensitive", file=sys.stderr)
        return []
    
    # Ensure source and sink are in same file
    if source["file"] != sink["file"]:
        return []

    # Get function containing sink
    query = build_query('symbols', ['name', 'line'],
        where="path = ? AND type = 'function' AND line <= ?",
        order_by="line DESC",
        limit=1
    )
    cursor.execute(query, (sink["file"], sink["line"]))

    sink_func = cursor.fetchone()
    if not sink_func or sink_func[0] != source_function["name"]:
        # Source and sink in different functions
        if debug:
            print(f"[CFG] Source and sink in different functions", file=sys.stderr)
        return []
    
    # Initialize path analyzer
    analyzer = PathAnalyzer(cursor, source["file"], source_function["name"])
    
    # Find the tainted variable from source
    # This is simplified - would need better parsing
    tainted_var = source.get("name", source["pattern"])
    if "." in tainted_var:
        # For patterns like req.body, use the full pattern
        pass
    else:
        # Try to find assigned variable
        query = build_query('assignments', ['target_var'],
            where="file = ? AND line = ? AND source_expr LIKE ?",
            limit=1
        )
        cursor.execute(query, (source["file"], source["line"], f"%{source['pattern']}%"))

        result = cursor.fetchone()
        if result:
            tainted_var = result[0]
    
    # Find vulnerable paths (Stage 2: with max_paths limit)
    vulnerable_paths = analyzer.find_vulnerable_paths(
        source["line"], sink["line"], tainted_var, max_paths=max_paths
    )
    
    # Convert to taint path format (Stage 2: enhanced with detailed conditions)
    taint_paths = []
    for path_info in vulnerable_paths:
        # Build descriptive path
        path_description = []
        
        # Add source
        path_description.append({
            "type": "source",
            "location": f"{source['file']}:{source['line']}",
            "var": tainted_var,
            "pattern": source["pattern"]
        })
        
        # Stage 2: Add detailed path conditions if any
        if path_info.get("conditions"):
            path_description.append({
                "type": "conditions",
                "conditions": path_info["conditions"],
                "summary": path_info.get("condition_summary", "")
            })
        
        # Add sink
        path_description.append({
            "type": "sink",
            "location": f"{sink['file']}:{sink['line']}",
            "pattern": sink["pattern"]
        })
        
        # ARCHITECTURAL FIX: Create proper TaintPath object instead of dict
        # TaintPath will automatically calculate vulnerability_type
        path_obj = TaintPath(
            source=source,
            sink=sink,
            path=path_description
        )
        
        # Add CFG-specific metadata as attributes
        path_obj.flow_sensitive = True
        path_obj.conditions = path_info.get("conditions", [])
        path_obj.condition_summary = path_info.get("condition_summary", "")
        path_obj.path_complexity = path_info.get("path_complexity", 0)
        path_obj.tainted_vars = path_info.get("tainted_vars", [])
        path_obj.sanitized_vars = path_info.get("sanitized_vars", [])
        
        taint_paths.append(path_obj)
    
    if debug:
        print(f"[CFG] Found {len(taint_paths)} vulnerable paths", file=sys.stderr)
    
    return taint_paths


def should_use_cfg(cursor: sqlite3.Cursor, source: Dict[str, Any],
                  sink: Dict[str, Any]) -> bool:
    """
    Determine if CFG analysis should be used for this source-sink pair.

    Args:
        cursor: Database cursor
        source: Taint source
        sink: Security sink

    Returns:
        True if CFG analysis is beneficial

    Schema Contract:
        Queries cfg_blocks table (guaranteed to exist)
    """
    # Check if CFG data exists
    if not check_cfg_available(cursor):
        return False

    # Check if source and sink are in same file
    if source["file"] != sink["file"]:
        return False

    # Check if there are conditional statements between source and sink
    # This is a heuristic - CFG is most useful when there are branches
    query = build_query('cfg_blocks', ['id'],
        where="file = ? AND block_type IN ('condition', 'loop_condition') AND start_line > ? AND end_line < ?",
        limit=1
    )
    cursor.execute(query, (source["file"], source["line"], sink["line"]))

    has_conditional_blocks = cursor.fetchone() is not None

    # Use CFG if there are conditional blocks
    return has_conditional_blocks


def verify_unsanitized_cfg_paths(
    cursor: sqlite3.Cursor,
    source: Dict[str, Any],
    sink: Dict[str, Any],
    source_function: Dict[str, Any],
    max_paths: int = 100
) -> Optional[List[TaintPath]]:
    """
    Verify that at least one unsanitized CFG path connects source to sink.

    Returns None when CFG data is unavailable for the function so callers can
    fall back to flow-insensitive analysis, returns an empty list when all
    candidate paths are sanitized, and returns a list of TaintPath objects when
    an unsanitized path exists.
    """
    if source.get("file") != sink.get("file"):
        return None

    if not source_function or "name" not in source_function:
        return None

    if not check_cfg_available(cursor):
        return None

    # Ensure both source and sink map to known CFG blocks; otherwise we cannot
    # reason about path sensitivity for this function.
    source_block = get_block_for_line(
        cursor,
        source["file"],
        source.get("line", -1),
        source_function["name"],
    )
    sink_block = get_block_for_line(
        cursor,
        sink["file"],
        sink.get("line", -1),
        source_function["name"],
    )

    if not source_block or not sink_block:
        return None

    return trace_flow_sensitive(
        cursor=cursor,
        source=source,
        sink=sink,
        source_function=source_function,
        max_paths=max_paths,
    )
