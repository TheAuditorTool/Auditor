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

        # PHASE 5: Check for object_literals table (v1.2+ feature)
        # Cache this check to avoid repeated queries
        self._has_object_literals_table = self._check_object_literals_table()
    
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
        
        # Check persistent cache if available
        if self.cache:
            cached_result = self.cache.get_cached_analysis(
                callee_file, callee_func, {"args": args_mapping, "taint": taint_state}
            )
            if cached_result:
                if self.debug:
                    print(f"  Persistent cache hit for {callee_func}", file=sys.stderr)
                effect = self._deserialize_effect(cached_result)
                self.analysis_cache[cache_key] = effect
                return effect
        
        # Prevent infinite recursion
        if self.recursion_depth > self.max_recursion:
            if self.debug:
                print(f"  Max recursion depth reached", file=sys.stderr)
            return InterProceduralEffect()  # Conservative: assume no effect
        
        self.recursion_depth += 1
        
        try:
            # Get CFG for callee function
            from theauditor.taint.cfg_integration import PathAnalyzer, BlockTaintState
            
            # Check if CFG data exists for the callee
            analyzer = None
            try:
                analyzer = PathAnalyzer(self.cursor, callee_file, callee_func)
            except Exception as e:
                if self.debug:
                    print(f"  No CFG data for {callee_func}: {e}", file=sys.stderr)
                # Fall back to conservative analysis
                return self._analyze_without_cfg(callee_func, args_mapping, taint_state)
            
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
            if self.cache:
                self.cache.cache_analysis(
                    callee_file, callee_func,
                    {"args": args_mapping, "taint": taint_state},
                    self._serialize_effect(effect)
                )
            
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

    def _check_object_literals_table(self) -> bool:
        """Check if object_literals table exists in database (v1.2+ feature).

        Returns:
            True if table exists, False otherwise
        """
        try:
            self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='object_literals'"
            )
            exists = self.cursor.fetchone() is not None

            if not exists and self.debug:
                print("[TAINT DEBUG] object_literals table not found - using regex fallback", file=sys.stderr)

            return exists
        except Exception as e:
            if self.debug:
                print(f"[TAINT DEBUG] Error checking object_literals table: {e}", file=sys.stderr)
            return False

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
        # Fast path: Skip database query if table doesn't exist
        if not self._has_object_literals_table:
            return []

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

        except sqlite3.OperationalError as e:
            # Table might have been deleted mid-analysis
            if "no such table" in str(e):
                self._has_object_literals_table = False  # Update cache
                if self.debug:
                    print(f"[TAINT DEBUG] object_literals table disappeared - disabling", file=sys.stderr)
            return []

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
        """Analyze all execution paths through the function."""
        exit_states = []
        
        # Find all exit blocks (return statements)
        exit_blocks = []
        for block_id, block in analyzer.blocks.items():
            if block["type"] == "exit" or block.get("has_return", False):
                exit_blocks.append(block_id)
        
        if not exit_blocks:
            # No explicit returns - use last block
            if analyzer.blocks:
                exit_blocks = [max(analyzer.blocks.keys())]
        
        # For each exit block, analyze paths from entry
        for exit_block in exit_blocks:
            # This is simplified - real implementation would use PathAnalyzer's methods
            # to properly trace through all paths
            exit_state = self._trace_to_exit(analyzer, entry_state, exit_block)
            if exit_state:
                exit_states.append(exit_state)
        
        return exit_states
    
    def _trace_to_exit(
        self, 
        analyzer: 'PathAnalyzer', 
        entry_state: 'BlockTaintState',
        exit_block_id: int
    ) -> Optional['BlockTaintState']:
        """Trace taint from entry to a specific exit block."""
        # Simplified - would use proper dataflow analysis
        current_state = entry_state.copy()
        
        # Process assignments and sanitizers along the path
        # This is a simplified version - real implementation would
        # follow actual CFG paths
        for block_id, block in analyzer.blocks.items():
            if block_id <= exit_block_id:  # Simplified path check
                current_state = analyzer._process_block_for_assignments(current_state, block)
                current_state = analyzer._process_block_for_sanitizers(current_state, block)
        
        return current_state
    
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
            param_tainted = False
            param_sanitized = False
            
            for state in exit_states:
                if callee_param in state.tainted_vars:
                    param_tainted = True
                if callee_param in state.sanitized_vars:
                    param_sanitized = True
            
            if param_sanitized and not param_tainted:
                effect.param_effects[callee_param] = 'sanitized'
            elif param_tainted:
                effect.param_effects[callee_param] = 'tainted'
            else:
                effect.param_effects[callee_param] = 'unmodified'
        
        return effect
    
    def _analyze_passthrough(
        self,
        analyzer: 'PathAnalyzer',
        entry_state: 'BlockTaintState'
    ) -> Dict[str, bool]:
        """Analyze which parameters directly taint the return value."""
        passthrough = {}
        
        # For each tainted parameter, check if it flows to return
        for param in entry_state.tainted_vars:
            # Trace if this parameter reaches a return statement
            # Simplified - real implementation would trace through CFG
            passthrough[param] = self._param_reaches_return(analyzer, param)
        
        return passthrough
    
    def _param_reaches_return(self, analyzer: 'PathAnalyzer', param: str) -> bool:
        """Check if a parameter flows to a return statement.

        Schema Contract:
            Queries function_returns table (guaranteed to exist)
        """
        # Query return statements in the function
        query = build_query('function_returns', ['return_expr'],
            where="file = ? AND function_name = ?"
        )
        self.cursor.execute(query, (analyzer.file_path, analyzer.function_name))

        for return_expr, in self.cursor.fetchall():
            if param in return_expr:
                return True

        return False
    
    def _analyze_without_cfg(
        self,
        callee_func: str,
        args_mapping: Dict[str, str],
        taint_state: Dict[str, bool]
    ) -> InterProceduralEffect:
        """Conservative analysis when CFG is not available."""
        # Be conservative: assume all tainted inputs taint outputs
        effect = InterProceduralEffect()
        
        # If any input is tainted, assume return is tainted
        for caller_var, is_tainted in taint_state.items():
            if is_tainted:
                effect.return_tainted = True
                break
        
        # Assume parameters are unmodified (conservative for pass-by-ref)
        for param in args_mapping.values():
            effect.param_effects[param] = 'unmodified'
        
        return effect
    
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