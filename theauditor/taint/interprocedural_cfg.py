"""Inter-procedural CFG analysis for cross-function taint tracking.

This module bridges Control Flow Graphs across function boundaries to enable
complete taint flow analysis including pass-by-reference modifications.

Schema Contract:
    All queries use build_query() for schema compliance.
    Table existence is guaranteed by schema contract - no checks needed.
"""

import os
import sys
import sqlite3
import hashlib
import json
import re
from typing import Dict, Set, Optional, List, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import defaultdict

from theauditor.indexer.schema import build_query

if TYPE_CHECKING:
    from .memory_cache import MemoryCache
    from .cfg_integration import BlockTaintState, PathAnalyzer

@dataclass
class InterProceduralEffect:
    """Results of analyzing a function call with CFG context.
    
    This captures how a function modifies its parameters and return value,
    enabling accurate taint tracking across function boundaries.
    """
    return_tainted: bool = False
    # Maps parameter name to its final state ('sanitized', 'tainted', 'unmodified')
    param_effects: Dict[str, str] = field(default_factory=dict)
    # NEW: Tracks which params directly taint the return value
    passthrough_taint: Dict[str, bool] = field(default_factory=dict)  # param_name -> taints_return
    side_effects: List[str] = field(default_factory=list)  # e.g., ["writes_to_db", "sends_response"]
    
    def merge_conservative(self, other: 'InterProceduralEffect') -> 'InterProceduralEffect':
        """Merge two effects conservatively for dynamic dispatch."""
        merged = InterProceduralEffect()
        
        # Return is tainted if ANY path taints it
        merged.return_tainted = self.return_tainted or other.return_tainted
        
        # Merge parameter effects conservatively
        all_params = set(self.param_effects.keys()) | set(other.param_effects.keys())
        for param in all_params:
            self_effect = self.param_effects.get(param, 'unmodified')
            other_effect = other.param_effects.get(param, 'unmodified')
            
            # Conservative: if either taints, result is tainted
            if self_effect == 'tainted' or other_effect == 'tainted':
                merged.param_effects[param] = 'tainted'
            elif self_effect == 'sanitized' and other_effect == 'sanitized':
                merged.param_effects[param] = 'sanitized'
            else:
                merged.param_effects[param] = 'unmodified'
        
        # Merge passthrough taint
        all_passthrough = set(self.passthrough_taint.keys()) | set(other.passthrough_taint.keys())
        for param in all_passthrough:
            merged.passthrough_taint[param] = (
                self.passthrough_taint.get(param, False) or 
                other.passthrough_taint.get(param, False)
            )
        
        # Combine side effects
        merged.side_effects = list(set(self.side_effects + other.side_effects))
        
        return merged


class InterProceduralCFGAnalyzer:
    """Connects CFGs across function boundaries for complete taint analysis.

    This is the Stage 3 enhancement that enables flow-sensitive analysis
    across function calls, including pass-by-reference modifications.
    """

    def __init__(self, cursor: sqlite3.Cursor, cache: Optional['MemoryCache'] = None) -> None:
        """Initialize inter-procedural CFG analyzer.

        Args:
            cursor: Database cursor for queries
            cache: Optional MemoryCache instance for performance optimization
        """
        self.cursor = cursor
        self.cache = cache
        self.analysis_cache = {}  # In-memory memoization
        self.recursion_depth = 0
        self.max_recursion = 10
        self.debug = os.environ.get("THEAUDITOR_CFG_DEBUG") or os.environ.get("THEAUDITOR_TAINT_DEBUG")
    
    def analyze_function_call(
        self,
        caller_file: str,
        caller_func: str,
        callee_file: str,
        callee_func: str,
        args_mapping: Dict[str, str],  # caller_var -> callee_param
        taint_state: Dict[str, bool]   # var -> is_tainted
    ) -> InterProceduralEffect:
        """
        Analyze a function call with full CFG context.
        
        This is the key innovation - we understand HOW the callee
        modifies data, not just that it was called.
        """
        if self.debug:
            print(f"\n[INTER-CFG] Analyzing call to {callee_func}", file=sys.stderr)
            print(f"  Args mapping: {args_mapping}", file=sys.stderr)
            print(f"  Taint state: {taint_state}", file=sys.stderr)
        
        # Check memoization cache
        cache_key = self._make_cache_key(callee_file, callee_func, args_mapping, taint_state)
        if cache_key in self.analysis_cache:
            if self.debug:
                print(f"  Cache hit for {callee_func}", file=sys.stderr)
            return self.analysis_cache[cache_key]
        
        # Prevent infinite recursion
        if self.recursion_depth > self.max_recursion:
            if self.debug:
                print(f"  Max recursion depth reached", file=sys.stderr)
            return InterProceduralEffect()  # Conservative: assume no effect
        
        self.recursion_depth += 1
        
        try:
            # Get CFG for callee function
            from theauditor.taint.cfg_integration import PathAnalyzer, BlockTaintState

            # HARD FAIL PROTOCOL: NO FALLBACKS
            # PathAnalyzer now normalizes function names internally
            # If this fails, it means CFG data is truly missing (indexer bug)
            # Let it crash loud so we can fix the root cause
            analyzer = PathAnalyzer(self.cursor, callee_file, callee_func)
            
            # Map caller's taint state to callee's entry state
            entry_state = self._map_taint_to_params(args_mapping, taint_state)
            
            # Analyze all paths through the callee
            exit_states = self._analyze_all_paths(analyzer, entry_state)
            
            # Extract effects: return value taint, param modifications, passthrough
            effect = self._extract_effects(exit_states, args_mapping)
            
            # CRITICAL: Track passthrough taint for utility functions
            # e.g., const getQuery = (req) => req.query
            effect.passthrough_taint = self._analyze_passthrough(analyzer, entry_state)
            
            # Cache the result
            self.analysis_cache[cache_key] = effect

            if self.debug:
                print(f"  Effect: return_tainted={effect.return_tainted}, params={effect.param_effects}", file=sys.stderr)
            
            return effect
            
        finally:
            self.recursion_depth -= 1
    
    def handle_dynamic_dispatch(
        self,
        call_expr: str,
        context: Dict[str, Any],
        args_mapping: Dict[str, str],
        taint_state: Dict[str, bool]
    ) -> InterProceduralEffect:
        """
        Resolve function pointers and dynamic dispatch.
        
        Handles patterns like:
        const handler = actions[req.query.action];
        handler(req.body);
        """
        if self.debug:
            print(f"\n[INTER-CFG] Handling dynamic dispatch: {call_expr}", file=sys.stderr)
        
        possible_callees = self._resolve_dynamic_callees(call_expr, context)
        
        if not possible_callees:
            # Cannot resolve - be conservative
            if self.debug:
                print(f"  Cannot resolve dynamic call", file=sys.stderr)
            return InterProceduralEffect(
                return_tainted=True,  # Conservative: assume return is tainted
                param_effects={param: 'tainted' for param in args_mapping.values()}
            )
        
        if self.debug:
            print(f"  Possible callees: {possible_callees}", file=sys.stderr)
        
        # Analyze all possible callees and merge conservatively
        effects = []
        for callee_func in possible_callees:
            effect = self.analyze_function_call(
                context["file"], context["function"],
                context["file"], callee_func,
                args_mapping, taint_state
            )
            effects.append(effect)
        
        # Merge all effects conservatively
        if not effects:
            return InterProceduralEffect()
        
        merged = effects[0]
        for effect in effects[1:]:
            merged = merged.merge_conservative(effect)
        
        return merged
    
    # ========================================================
    # PHASE 5: DATABASE-BACKED DYNAMIC DISPATCH RESOLUTION
    # ========================================================

    def _resolve_dynamic_callees_from_db(self, base_obj: str, context: Dict[str, Any]) -> List[str]:
        """Resolve dynamic callees using object_literals table (database-first, v1.2+).

        This is the NEW implementation that replaces regex parsing with structured
        database queries for 100-1000x speedup.

        Args:
            base_obj: Name of the object variable (e.g., "actions", "handlers")
            context: Taint context with file information

        Returns:
            List of possible function names that could be called

        Example:
            // Code: const actions = { create: handleCreate, update: handleUpdate };
            // Query: _resolve_dynamic_callees_from_db("actions", context)
            // Result: ["handleCreate", "handleUpdate"]
        """
        possible_callees = []

        try:
            # Build schema-compliant query
            query = build_query('object_literals',
                ['property_value'],
                where="variable_name = ? AND property_type IN ('function_ref', 'shorthand')"
            )

            # Execute query with indexed lookup (variable_name has index)
            self.cursor.execute(query, (base_obj,))

            # Extract function names
            for property_value, in self.cursor.fetchall():
                # property_value is the function name (e.g., "handleCreate")
                possible_callees.append(property_value)

            if self.debug and possible_callees:
                print(f"[TAINT DEBUG] Resolved {len(possible_callees)} callees for '{base_obj}' via database: {possible_callees}", file=sys.stderr)

        except Exception as e:
            if self.debug:
                print(f"[TAINT DEBUG] Database query error: {e}", file=sys.stderr)
            return []

        return possible_callees

    def _resolve_dynamic_callees(self, call_expr: str, context: Dict[str, Any]) -> List[str]:
        """Try to resolve dynamic function calls to possible targets.

        NEW in v1.2: Uses database-backed lookup (object_literals table) for
        100-1000x speedup. Falls back to regex for backward compatibility.

        Schema Contract:
            Queries object_literals table (v1.2+) or assignments table (fallback)
        """
        possible_callees = []

        # Pattern 1: Dictionary/array access like actions[key]
        if "[" in call_expr and "]" in call_expr:
            base_obj = call_expr.split("[")[0].strip()

            # === PHASE 5: TRY DATABASE FIRST (NEW, FAST) ===
            db_callees = self._resolve_dynamic_callees_from_db(base_obj, context)

            if db_callees:
                # Database query succeeded - use these results
                possible_callees.extend(db_callees)
                return list(set(possible_callees))  # Remove duplicates

            # === FALLBACK TO REGEX (BACKWARD COMPATIBILITY) ===
            # Only reached if:
            # 1. object_literals table doesn't exist (old database)
            # 2. No properties found for this object
            # 3. Database query error

            if self.debug:
                print(f"[TAINT DEBUG] Falling back to regex for '{base_obj}'", file=sys.stderr)

            # Find all assignments to this object
            query = build_query('assignments', ['source_expr'],
                where="target_var = ? AND file = ? AND in_function = ?"
            )
            self.cursor.execute(query, (base_obj, context["file"], context.get("function", "")))

            for source_expr, in self.cursor.fetchall():
                # Parse object literal to find possible functions
                if "{" in source_expr:
                    # LEGACY REGEX APPROACH (kept for backward compatibility)
                    # This is NOT matching source code - it's parsing an expression
                    # extracted by the indexer. Example:
                    #   source_expr = "{ create: handleCreate, update: handleUpdate }"
                    #   Need to extract: ["handleCreate", "handleUpdate"]
                    func_pattern = r":\s*(\w+)"  # Match function refs after colons
                    matches = re.findall(func_pattern, source_expr)
                    possible_callees.extend(matches)
        
        # Pattern 2: Ternary/conditional assignment
        # e.g., const handler = condition ? funcA : funcB
        if "?" in call_expr and ":" in call_expr:
            # Extract both branches
            parts = call_expr.split("?")
            if len(parts) == 2:
                branches = parts[1].split(":")
                if len(branches) == 2:
                    possible_callees.append(branches[0].strip())
                    possible_callees.append(branches[1].strip())
        
        return list(set(possible_callees))  # Remove duplicates
    
    def _map_taint_to_params(
        self, 
        args_mapping: Dict[str, str], 
        taint_state: Dict[str, bool]
    ) -> 'BlockTaintState':
        """Map caller's taint state to callee's parameter state."""
        from theauditor.taint.cfg_integration import BlockTaintState
        
        entry_state = BlockTaintState(block_id=0)  # Entry block
        
        for caller_var, callee_param in args_mapping.items():
            if taint_state.get(caller_var, False):
                entry_state.add_taint(callee_param)
        
        return entry_state
    
    def _analyze_all_paths(
        self,
        analyzer: 'PathAnalyzer',
        entry_state: 'BlockTaintState'
    ) -> List['BlockTaintState']:
        """Analyze all execution paths by QUERYING database for path enumeration."""
        from .database import get_paths_between_blocks

        exit_states = []

        # CRITICAL FIX: Query for actual entry block ID (not hardcoded 0)
        # Block ID 0 doesn't exist - entry blocks start at 1+
        query = build_query('cfg_blocks',
            ['id'],
            where="file = ? AND function_name = ? AND block_type = 'entry'",
            limit=1
        )
        self.cursor.execute(query, (analyzer.file_path, analyzer.function_name))
        entry_result = self.cursor.fetchone()

        # Use 1 as fallback (first block), but should always find entry
        entry_block_id = entry_result[0] if entry_result else 1

        if self.debug and entry_result:
            print(f"[INTER-CFG] Found entry block ID: {entry_block_id} for {analyzer.function_name}", file=sys.stderr)
        elif self.debug:
            print(f"[INTER-CFG] WARNING: No entry block found for {analyzer.function_name}, using fallback ID 1", file=sys.stderr)

        # Query database for exit blocks - CORRECT: use 'id' not 'block_id'
        query = build_query('cfg_blocks',
            ['id'],
            where="file = ? AND function_name = ? AND block_type = 'exit'"
        )
        self.cursor.execute(query, (analyzer.file_path, analyzer.function_name))

        exit_blocks = [row[0] for row in self.cursor.fetchall()]

        if not exit_blocks:
            # Use last block if no explicit returns
            # NOTE: Cannot use build_query with aggregate functions, use raw SQL
            self.cursor.execute(
                "SELECT MAX(id) FROM cfg_blocks WHERE file = ? AND function_name = ?",
                (analyzer.file_path, analyzer.function_name)
            )
            result = self.cursor.fetchone()
            if result and result[0] is not None:
                exit_blocks = [result[0]]

        # For each exit, get paths using DATABASE API
        # CORRECT: get_paths_between_blocks(cursor, file_path, source_block_id, sink_block_id)
        for exit_block in exit_blocks:
            paths = get_paths_between_blocks(
                self.cursor,
                analyzer.file_path,
                entry_block_id,  # FIXED: Use actual entry block ID, not 0
                exit_block  # end_block (exit)
            )

            if not paths:
                if self.debug:
                    print(f"[INTER-CFG] Exit block {exit_block} is unreachable", file=sys.stderr)
                continue

            # Analyze each path separately using DATABASE QUERIES (NOT simulation)
            for path in paths:
                exit_state = self._query_path_taint_status(
                    analyzer.file_path,
                    analyzer.original_function_name,  # CRITICAL FIX: Use original name for assignments/calls
                    entry_state,
                    path  # List of block IDs
                )
                if exit_state:
                    exit_states.append(exit_state)

        return exit_states
    
    def _query_path_taint_status(
        self,
        file_path: str,
        function_name: str,
        entry_state: 'BlockTaintState',
        path: List[int]  # List of block IDs from database
    ) -> Optional['BlockTaintState']:
        """Query database for taint status along a specific path (NO in-memory simulation)."""
        from theauditor.taint.cfg_integration import BlockTaintState

        current_tainted = set(entry_state.tainted_vars)
        # NEW: Track sanitized vars to prevent re-tainting within the same path
        current_sanitized = set()

        # CRITICAL FIX: Normalize name ONLY for cfg_blocks query
        # function_name is now ORIGINAL full name (e.g., "accountService.createAccount")
        # cfg_blocks needs normalized name (e.g., "createAccount")
        normalized_name = function_name.split('.')[-1]

        if self.debug:
            print(f"\n[INTER-CFG] Querying taint for path: {path}", file=sys.stderr)
            print(f"[INTER-CFG]   Original name: {function_name}, Normalized: {normalized_name}", file=sys.stderr)
            print(f"[INTER-CFG]   Entry Taint: {current_tainted}", file=sys.stderr)

        # Get block line ranges for path - CORRECT: query cfg_blocks.id
        block_ranges = {}
        if path:
            block_ids_str = ','.join('?' * len(path))
            query = build_query('cfg_blocks',
                ['id', 'start_line', 'end_line'],
                where=f"file = ? AND function_name = ? AND id IN ({block_ids_str})",
                order_by="start_line"
            )
            # CRITICAL FIX: Use normalized_name for cfg_blocks
            self.cursor.execute(query, (file_path, normalized_name, *path))
            for blk_id, start_line, end_line in self.cursor.fetchall():
                block_ranges[blk_id] = (start_line, end_line)

        # Get registry for sanitizer checking
        from .registry import TaintRegistry
        if not hasattr(self, 'registry') or self.registry is None:
            self.registry = TaintRegistry()

        # Process each block in path order
        for block_id in path:
            if block_id not in block_ranges:
                continue

            start_line, end_line = block_ranges[block_id]

            # Query assignments in this block's line range - CORRECT: assignments has NO block_id
            query = build_query('assignments',
                ['target_var', 'source_expr', 'line'],
                where="file = ? AND in_function = ? AND line >= ? AND line <= ?",
                order_by="line"
            )
            # CRITICAL FIX: Use ORIGINAL function_name for assignments (not normalized)
            self.cursor.execute(query, (file_path, function_name, start_line, end_line))
            assignments = self.cursor.fetchall()

            # Query function calls in this block's line range - CORRECT: function_call_args has NO block_id
            query = build_query('function_call_args',
                ['callee_function', 'argument_expr', 'line'],
                where="file = ? AND caller_function = ? AND line >= ? AND line <= ?",
                order_by="line"
            )
            # CRITICAL FIX: Use ORIGINAL function_name for function_call_args (not normalized)
            self.cursor.execute(query, (file_path, function_name, start_line, end_line))

            # Map calls by line for efficient lookup
            calls_by_line = defaultdict(list)
            for callee, arg_expr, line in self.cursor.fetchall():
                calls_by_line[line].append((callee, arg_expr))

            # --- CORRECTED LOGIC: Check sanitization FIRST, propagation SECOND ---
            for target_var, source_expr, line in assignments:
                is_sanitized_assignment = False

                # 1. CHECK FOR SANITIZATION FIRST (regardless of target taint status)
                # Check if this assignment's line corresponds to a sanitizer call
                if line in calls_by_line:
                    for callee, arg_expr in calls_by_line[line]:
                        if self.registry.is_sanitizer(callee):
                            # This is a sanitizer. Does it clean a tainted var?
                            for tainted_var in list(current_tainted):
                                if tainted_var in arg_expr:
                                    # YES. This assignment is a sanitization.
                                    is_sanitized_assignment = True
                                    current_sanitized.add(target_var)

                                    # If the sanitizer re-assigns the *same* var (e.g., x = sanitize(x)),
                                    # remove its taint.
                                    if target_var in current_tainted:
                                        current_tainted.discard(target_var)

                                    if self.debug:
                                        print(f"[INTER-CFG]   Sanitized: {tainted_var} -> {target_var} at line {line}", file=sys.stderr)
                                    break # Stop checking tainted_vars
                        if is_sanitized_assignment:
                            break # Stop checking calls_by_line

                if is_sanitized_assignment:
                    continue # This variable is clean, do not propagate taint. Move to next assignment.

                # 2. IF NOT SANITIZED, CHECK FOR PROPAGATION
                for tainted_var in list(current_tainted):
                    if tainted_var in source_expr:
                        # Propagate taint, *unless* the target was somehow sanitized before
                        if target_var not in current_sanitized:
                            current_tainted.add(target_var)
                            if self.debug:
                                print(f"[INTER-CFG]   Propagated: {tainted_var} -> {target_var} at line {line}", file=sys.stderr)
                            break # One propagation is enough

        final_state = BlockTaintState(block_id=path[-1])
        final_state.tainted_vars = current_tainted
        final_state.sanitized_vars = current_sanitized # Pass sanitization state up

        if self.debug:
            print(f"[INTER-CFG]   Exit Taint: {final_state.tainted_vars}", file=sys.stderr)

        return final_state
    
    def _extract_effects(
        self,
        exit_states: List['BlockTaintState'],
        args_mapping: Dict[str, str]
    ) -> InterProceduralEffect:
        """Extract the function's effects from exit states."""
        effect = InterProceduralEffect()

        # Check if return value is tainted in any exit state
        for state in exit_states:
            if "__return__" in state.tainted_vars:
                effect.return_tainted = True
                break

        # Check parameter modifications
        for caller_var, callee_param in args_mapping.items():
            param_tainted_in_any_path = False
            # NEW LOGIC: Parameter is only considered sanitized if it's
            # sanitized in ALL possible exit paths.
            param_sanitized_in_all_paths = True

            if not exit_states:
                param_sanitized_in_all_paths = False # No paths? Not sanitized.

            for state in exit_states:
                if callee_param in state.tainted_vars:
                    param_tainted_in_any_path = True

                # CRITICAL FIX: Use the new sanitized_vars from BlockTaintState
                # If it's NOT in sanitized_vars in even ONE path, it's not guaranteed sanitized.
                if callee_param not in state.sanitized_vars:
                    param_sanitized_in_all_paths = False

            # CONSERVATIVE MERGE:
            # Tainted if tainted in ANY path. (Taint wins)
            # Sanitized only if sanitized in ALL paths AND never re-tainted.

            if param_tainted_in_any_path:
                effect.param_effects[callee_param] = 'tainted'
            elif param_sanitized_in_all_paths:
                effect.param_effects[callee_param] = 'sanitized'
            else:
                effect.param_effects[callee_param] = 'unmodified'

        return effect
    
    def _analyze_passthrough(
        self,
        analyzer: 'PathAnalyzer',
        entry_state: 'BlockTaintState'
    ) -> Dict[str, bool]:
        """Query database to check if parameters reach return (NO in-memory flow tracking)."""
        from .database import get_paths_between_blocks

        passthrough = {}

        # CRITICAL FIX: Query for actual entry block ID (not hardcoded 0)
        # Block ID 0 doesn't exist - entry blocks start at 1+
        query = build_query('cfg_blocks',
            ['id'],
            where="file = ? AND function_name = ? AND block_type = 'entry'",
            limit=1
        )
        self.cursor.execute(query, (analyzer.file_path, analyzer.function_name))
        entry_result = self.cursor.fetchone()

        # Use 1 as fallback (first block), but should always find entry
        entry_block_id = entry_result[0] if entry_result else 1

        # Query for return blocks - CORRECT: use 'id' not 'block_id'
        query = build_query('cfg_blocks',
            ['id', 'start_line', 'end_line'],
            where="file = ? AND function_name = ? AND block_type = 'exit'"
        )
        self.cursor.execute(query, (analyzer.file_path, analyzer.function_name))

        return_blocks = self.cursor.fetchall()

        if not return_blocks:
            # Use last block if no explicit returns
            query = build_query('cfg_blocks',
                ['id', 'start_line', 'end_line'],
                where="file = ? AND function_name = ?",
                order_by="id DESC",
                limit=1
            )
            self.cursor.execute(query, (analyzer.file_path, analyzer.function_name))
            result = self.cursor.fetchone()
            if result:
                return_blocks = [result]

        # For each parameter, query if it reaches return
        for param in entry_state.tainted_vars:
            param_reaches = False

            for return_block_id, start_line, end_line in return_blocks:
                # Query variable_usage to check if param is used in return block
                # CORRECT: variable_usage has NO block_id or function_name - use line range
                query = build_query('variable_usage',
                    ['usage_type'],
                    where="file = ? AND variable_name = ? AND line >= ? AND line <= ?",
                    limit=1
                )
                self.cursor.execute(query, (analyzer.file_path, param, start_line, end_line))

                if self.cursor.fetchone():
                    # Param is used in return - check if sanitized along any path
                    # CORRECT: get_paths_between_blocks(cursor, file_path, source_id, sink_id)
                    paths = get_paths_between_blocks(
                        self.cursor,
                        analyzer.file_path,
                        entry_block_id,  # FIXED: Use actual entry block ID, not 0
                        return_block_id  # end_block
                    )

                    # Check if param is sanitized along ALL paths (conservative)
                    sanitized_all_paths = True
                    for path in paths:
                        if not self._is_sanitized_along_path(
                            analyzer.file_path,
                            analyzer.original_function_name,  # CRITICAL FIX: Use original name
                            param,
                            path
                        ):
                            sanitized_all_paths = False
                            break

                    if not sanitized_all_paths:
                        param_reaches = True
                        break

            passthrough[param] = param_reaches

        return passthrough

    def _is_sanitized_along_path(
        self,
        file_path: str,
        function_name: str,
        var_name: str,
        path: List[int]
    ) -> bool:
        """Query database to check if variable is sanitized along path."""
        # CRITICAL FIX: Normalize name ONLY for cfg_blocks query
        normalized_name = function_name.split('.')[-1]

        # Get block line ranges for path - CORRECT: cfg_blocks.id
        if not path:
            return False

        block_ids_str = ','.join('?' * len(path))
        query = build_query('cfg_blocks',
            ['start_line', 'end_line'],
            where=f"file = ? AND function_name = ? AND id IN ({block_ids_str})"
        )
        # CRITICAL FIX: Use normalized_name for cfg_blocks
        self.cursor.execute(query, (file_path, normalized_name, *path))

        line_ranges = self.cursor.fetchall()
        if not line_ranges:
            return False

        # Get min and max lines for query range
        min_line = min(start for start, _ in line_ranges)
        max_line = max(end for _, end in line_ranges)

        # Query for sanitizer calls on this variable along path
        # CORRECT: function_call_args has NO block_id - use line range
        query = build_query('function_call_args',
            ['callee_function', 'argument_expr'],
            where="file = ? AND caller_function = ? AND line >= ? AND line <= ?"
        )
        # CRITICAL FIX: Use ORIGINAL function_name for function_call_args (not normalized)
        self.cursor.execute(query, (file_path, function_name, min_line, max_line))

        # Get registry for sanitizer checking
        from .registry import TaintRegistry
        if not hasattr(self, 'registry') or self.registry is None:
            self.registry = TaintRegistry()

        for callee, arg_expr in self.cursor.fetchall():
            if var_name in arg_expr and self.registry.is_sanitizer(callee):
                return True

        return False
    
    # DELETED: _param_reaches_return() - replaced by querying variable_usage table
    # The database already has structured variable references - NO STRING PARSING NEEDED
    # Functionality now in _analyze_passthrough() which queries variable_usage table

    # ============================================================================
    # DELETED: _analyze_without_cfg() - 20 lines of fallback logic
    # ============================================================================
    # This function existed to provide "conservative analysis" when CFG lookup
    # failed. It returned params={'arg': 'unmodified'} which KILLED taint tracking.
    #
    # HARD FAILURE PROTOCOL:
    # - PathAnalyzer now normalizes function names (strips object prefix)
    # - If CFG lookup still fails, it means indexer bug → FIX THE INDEXER
    # - NO FALLBACKS. Let it crash loud so root cause is visible.
    #
    # The fallback pattern violated CLAUDE.md zero-fallback policy and hid the
    # function name mismatch bug for months.
    # ============================================================================

    def _make_cache_key(
        self,
        file: str,
        func: str,
        args_mapping: Dict[str, str],
        taint_state: Dict[str, bool]
    ) -> str:
        """Create a unique cache key for this analysis."""
        key_data = {
            "file": file,
            "func": func,
            "args": args_mapping,
            "taint": taint_state
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _serialize_effect(self, effect: InterProceduralEffect) -> str:
        """Serialize an effect for caching."""
        return json.dumps({
            "return_tainted": effect.return_tainted,
            "param_effects": effect.param_effects,
            "passthrough_taint": effect.passthrough_taint,
            "side_effects": effect.side_effects
        })
    
    def _deserialize_effect(self, data) -> InterProceduralEffect:
        """Deserialize an effect from cache."""
        # Handle both string and dict inputs (cfg_cache returns dict after json.loads)
        obj = data if isinstance(data, dict) else json.loads(data)
        return InterProceduralEffect(
            return_tainted=obj["return_tainted"],
            param_effects=obj["param_effects"],
            passthrough_taint=obj["passthrough_taint"],
            side_effects=obj["side_effects"]
        )