"""Inter-procedural taint tracking - the 'Toss the Salad' algorithm.

This module implements cross-function taint tracking by following
data flow through function arguments and return values.

Schema Contract:
    All queries use build_query() for schema compliance.
    Table existence is guaranteed by schema contract - no checks needed.
"""

import os
import sys
import sqlite3
from typing import Dict, List, Any, Optional, Set

from theauditor.indexer.schema import build_query
from .database import get_containing_function, get_code_snippet


def normalize_function_name(func_name: str) -> str:
    """
    Normalize function names by stripping module/object prefixes.

    Examples:
        "accountService.createAccount" -> "createAccount"
        "this.handleClick" -> "handleClick"
        "controller.update" -> "update"
        "MyClass.method" -> "method"

    This is necessary because function_call_args stores qualified names
    (e.g., "service.method") but symbols table stores base names (e.g., "method").
    """
    if not func_name:
        return func_name

    # Split on last dot to get base function name
    if '.' in func_name:
        return func_name.split('.')[-1]

    return func_name


def trace_inter_procedural_flow_insensitive(
    cursor: sqlite3.Cursor,
    source_var: str,
    source_file: str,
    source_line: int,
    source_function: str,
    sinks: List[Dict[str, Any]],
    max_depth: int = 5,
    cache: Optional[Any] = None
) -> List[Any]:  # Returns List[TaintPath]
    """
    The 'Toss the Salad' algorithm for flow-INSENSITIVE inter-procedural taint tracking.

    This function traces taint flow across function boundaries by:
    1. Following variables passed as function arguments
    2. Mapping arguments to function parameters inside callees
    3. Tracking taint through return values
    4. Mapping return values back to variables in the caller
    
    Args:
        cursor: Database cursor
        source_var: The tainted variable to track
        source_file: File containing the source
        source_line: Line where taint originates
        source_function: Function containing the source
        sinks: List of potential sinks to check
        max_depth: Maximum call depth to trace
        
    Returns:
        List of TaintPath objects showing inter-procedural vulnerabilities
    """
    # Import TaintPath here to avoid circular dependency
    from .core import TaintPath

    paths = []
    debug = os.environ.get("THEAUDITOR_TAINT_DEBUG") or os.environ.get("THEAUDITOR_DEBUG")
    
    if debug:
        print(f"\n[INTER-PROCEDURAL] Starting toss-the-salad tracking:", file=sys.stderr)
        print(f"  Source var: {source_var} in {source_function} at {source_file}:{source_line}", file=sys.stderr)
        print(f"  Max depth: {max_depth}", file=sys.stderr)
        print(f"  Checking {len(sinks)} sinks", file=sys.stderr)
    
    # Track visited functions to avoid cycles
    visited = set()
    
    # Worklist: (current_var, current_function, current_file, depth, path_so_far)
    worklist = [(source_var, source_function, source_file, 0, [])]
    
    while worklist:
        current_var, current_func, current_file, depth, path = worklist.pop(0)
        
        if depth > max_depth:
            if debug:
                print(f"[INTER-PROCEDURAL] Max depth {max_depth} reached", file=sys.stderr)
            continue
        
        # Create unique key for this state
        # CORRECTION 2: Remove depth from cycle detection key
        # Cycle detection prevents revisiting same state regardless of depth
        state_key = f"{current_file}:{current_func}:{current_var}"
        if state_key in visited:
            continue
        visited.add(state_key)
        
        if debug:
            print(f"\n[INTER-PROCEDURAL] Depth {depth}: Tracking {current_var} in {current_func}", file=sys.stderr)

        # Step 1: Check if current variable is passed as argument to other functions
        # Schema Contract: function_call_args table guaranteed to exist
        query = build_query('function_call_args',
            ['callee_function', 'param_name', 'line'],
            where="file = ? AND caller_function = ? AND (argument_expr = ? OR argument_expr LIKE ?)"
        )
        cursor.execute(query, (current_file, current_func, current_var, f"%{current_var}%"))

        calls = cursor.fetchall()
        if debug and calls:
            print(f"[INTER-PROCEDURAL] Found {len(calls)} function calls passing {current_var}", file=sys.stderr)
        
        for callee_func, param_name, call_line in calls:
            if debug:
                print(f"  -> {current_var} passed to {callee_func}({param_name}) at line {call_line}", file=sys.stderr)

            # ENHANCEMENT 1: Normalize function name before querying symbols
            normalized_callee = normalize_function_name(callee_func)

            # Query symbols table for callee's file location
            query = build_query('symbols', ['path'], where="name = ?", limit=1)
            cursor.execute(query, (normalized_callee,))
            callee_location = cursor.fetchone()

            # Fallback to current file if not found (defensive)
            callee_file = callee_location[0].replace("\\", "/") if callee_location else current_file

            # Debug output for cross-file transitions
            if debug and callee_file != current_file:
                print(f"[INTER-PROCEDURAL] Following call across files:", file=sys.stderr)
                print(f"  {current_file} → {callee_file}", file=sys.stderr)
                print(f"  Function: {current_func} → {callee_func}", file=sys.stderr)

            # Track the parameter in the callee function
            new_path = path + [{
                "type": "argument_pass",
                "from_func": current_func,
                "from_file": current_file,      # Added for better reporting
                "to_func": callee_func,
                "to_file": callee_file,          # Added for better reporting
                "var": current_var,
                "param": param_name,
                "line": call_line
            }]

            # Add to worklist with CORRECT file context
            worklist.append((param_name, callee_func, callee_file, depth + 1, new_path))
            
            # Step 2: Check if callee function contains any sinks using this parameter
            for sink in sinks:
                # CHANGE 1.1: Cross-file guard removed - check sinks in callee's file
                if sink["file"] != callee_file:
                    continue

                # Get function containing the sink
                sink_function = get_containing_function(cursor, sink)
                if not sink_function or sink_function["name"] != callee_func:
                    continue

                # Check if parameter flows to sink
                query = build_query('function_call_args', ['argument_expr'],
                    where="file = ? AND line = ? AND argument_expr LIKE ?",
                    limit=1
                )
                cursor.execute(query, (sink["file"], sink["line"], f"%{param_name}%"))

                if cursor.fetchone() is not None:
                    # Found inter-procedural vulnerability!
                    if debug:
                        print(f"[INTER-PROCEDURAL] VULNERABILITY FOUND!", file=sys.stderr)
                        print(f"  {source_var} -> {param_name} -> {sink['pattern']}", file=sys.stderr)
                    
                    vuln_path = new_path + [{
                        "type": "sink_reached",
                        "func": callee_func,
                        "var": param_name,
                        "sink": sink["pattern"],
                        "line": sink["line"]
                    }]
                    
                    path_obj = TaintPath(
                        source={"file": source_file, "line": source_line, "pattern": source_var, "name": source_var},
                        sink=sink,
                        path=vuln_path
                    )
                    paths.append(path_obj)

        # Step 3: Check if current variable is returned by current function
        query = build_query('function_returns',
            ['return_expr', 'line'],
            where="file = ? AND function_name = ? AND (return_expr = ? OR return_expr LIKE ? OR return_vars LIKE ?)"
        )
        cursor.execute(query, (current_file, current_func, current_var, f"%{current_var}%", f'%"{current_var}"%'))

        returns = cursor.fetchall()
        if debug and returns:
            print(f"[INTER-PROCEDURAL] {current_func} returns {current_var} in {len(returns)} places", file=sys.stderr)
        
        for return_expr, return_line in returns:
            # Find where this function is called and its return value is used
            query = build_query('function_call_args',
                ['caller_function', 'target_var', 'line'],
                where="file = ? AND callee_function = ? AND target_var IS NOT NULL"
            )
            cursor.execute(query, (current_file, current_func))

            call_sites = cursor.fetchall()
            if debug and call_sites:
                print(f"[INTER-PROCEDURAL] {current_func} called from {len(call_sites)} locations", file=sys.stderr)
            
            for caller_func, target_var, call_line in call_sites:
                if not target_var:
                    continue
                
                if debug:
                    print(f"  <- Return value assigned to {target_var} in {caller_func}", file=sys.stderr)
                
                # The return value is now tainted in the caller
                new_path = path + [{
                    "type": "return_flow",
                    "from_func": current_func,
                    "to_func": caller_func,
                    "return_var": current_var,
                    "target_var": target_var,
                    "line": call_line
                }]
                
                # Add to worklist to continue tracking in caller
                worklist.append((target_var, caller_func, current_file, depth + 1, new_path))
        
        # Step 4: Check if current variable directly reaches a sink in current function
        for sink in sinks:
            if sink["file"] != current_file:
                continue
            
            # Get function containing the sink
            sink_function = get_containing_function(cursor, sink)
            if not sink_function or sink_function["name"] != current_func:
                continue

            # Check if current variable is used in sink
            query = build_query('function_call_args', ['argument_expr'],
                where="file = ? AND line = ? AND argument_expr LIKE ?",
                limit=1
            )
            cursor.execute(query, (sink["file"], sink["line"], f"%{current_var}%"))

            if cursor.fetchone() is not None:
                # Direct vulnerability in current function
                if debug:
                    print(f"[INTER-PROCEDURAL] Direct sink reached in {current_func}", file=sys.stderr)
                
                vuln_path = path + [{
                    "type": "direct_sink",
                    "func": current_func,
                    "var": current_var,
                    "sink": sink["pattern"],
                    "line": sink["line"]
                }]
                
                path_obj = TaintPath(
                    source={"file": source_file, "line": source_line, "pattern": source_var, "name": source_var},
                    sink=sink,
                    path=vuln_path
                )
                paths.append(path_obj)
    
    if debug:
        print(f"\n[INTER-PROCEDURAL] Completed. Found {len(paths)} vulnerabilities", file=sys.stderr)
    
    return paths


def trace_inter_procedural_flow_cfg(
    analyzer: 'InterProceduralCFGAnalyzer',
    cursor: sqlite3.Cursor,
    source_var: str,
    source_file: str,
    source_line: int,
    source_function: str,
    sinks: List[Dict[str, Any]],
    max_depth: int = 5,
    cache: Optional[Any] = None
) -> List[Any]:  # Returns List[TaintPath]
    """
    Stage 3: CFG-based inter-procedural taint tracking with MULTI-HOP WORKLIST.

    This enhanced version uses Control Flow Graphs to understand:
    - Pass-by-reference modifications
    - Path-sensitive analysis within called functions
    - Dynamic dispatch resolution
    - MULTI-HOP call chains (NEW: v1.2.1)

    Algorithm:
    1. Initialize worklist with (function, taint_state, depth, call_path)
    2. For each function, query ALL callees (not just sink function)
    3. Build args_mapping for each callee
    4. Use CFG analyzer for path-sensitive analysis within each function
    5. Recursively add callees to worklist if taint propagates
    6. Continue until sink reached or max_depth exceeded

    Returns:
        List of TaintPath objects showing inter-procedural vulnerabilities
    """
    from .core import TaintPath

    paths = []
    debug = os.environ.get("THEAUDITOR_TAINT_DEBUG") or os.environ.get("THEAUDITOR_CFG_DEBUG")

    if debug:
        print(f"\n[INTER-CFG] Starting Stage 3 MULTI-HOP inter-procedural analysis", file=sys.stderr)
        print(f"  Source: {source_var} in {source_function} at {source_file}:{source_line}", file=sys.stderr)
        print(f"  Max depth: {max_depth}", file=sys.stderr)
        print(f"  Checking {len(sinks)} sinks", file=sys.stderr)

    # Track visited states to avoid cycles: (function, frozenset(tainted_vars))
    visited = set()

    # Worklist: (current_function, taint_state_dict, depth, call_path)
    # taint_state_dict: Dict[str, bool] mapping variable names to taint status
    worklist = [(source_function, {source_var: True}, 0, [])]

    while worklist:
        current_func, taint_state, depth, call_path = worklist.pop(0)

        # Max depth check
        if depth > max_depth:
            if debug:
                print(f"[INTER-CFG] Max depth {max_depth} reached", file=sys.stderr)
            continue

        # Cycle detection: Create state key from function + tainted variables
        tainted_vars_frozen = frozenset(taint_state.keys())
        state_key = (source_file, current_func, tainted_vars_frozen)
        if state_key in visited:
            if debug:
                print(f"[INTER-CFG] Already visited {current_func} with vars {tainted_vars_frozen}", file=sys.stderr)
            continue
        visited.add(state_key)

        if debug:
            print(f"\n[INTER-CFG] Depth {depth}: Analyzing {current_func}", file=sys.stderr)
            print(f"  Tainted vars: {list(taint_state.keys())}", file=sys.stderr)

        # STEP 1: Check if current function contains any sinks
        for sink in sinks:
            if sink["file"] != source_file:
                continue

            # Get function containing sink
            sink_function = get_containing_function(cursor, sink)
            if not sink_function or sink_function["name"] != current_func:
                continue

            # Sink is in current function - check if tainted vars reach it
            # Use CFG analyzer for path-sensitive analysis within this function
            for tainted_var in taint_state:
                # Check if this tainted variable flows to the sink
                # Query function_call_args to see if tainted_var is used in sink's arguments
                query = build_query('function_call_args', ['argument_expr'],
                    where="file = ? AND line = ? AND argument_expr LIKE ?",
                    limit=1
                )
                cursor.execute(query, (sink["file"], sink["line"], f"%{tainted_var}%"))

                if cursor.fetchone() is not None:
                    # VULNERABILITY FOUND!
                    if debug:
                        print(f"[INTER-CFG] VULNERABILITY: {tainted_var} reaches sink {sink['pattern']} at line {sink['line']}", file=sys.stderr)

                    vuln_path = call_path + [{
                        "type": "inter_procedural_cfg",
                        "func": current_func,
                        "var": tainted_var,
                        "sink": sink["pattern"],
                        "line": sink["line"],
                        "depth": depth
                    }]

                    path_obj = TaintPath(
                        source={"file": source_file, "line": source_line, "pattern": source_var, "name": source_var},
                        sink=sink,
                        path=vuln_path
                    )
                    paths.append(path_obj)

        # STEP 2: Query ALL callees from current function (not just sink function)
        # This is the MULTI-HOP key: explore all possible call paths
        if cache and hasattr(cache, 'calls_by_caller'):
            # Cache path: O(1) lookup
            cache_key = (source_file, current_func)
            cached_calls = cache.calls_by_caller.get(cache_key, [])
            all_calls = cached_calls
        else:
            # Disk fallback: Query all function calls from current function
            query = build_query('function_call_args',
                ['callee_function', 'param_name', 'argument_expr', 'line'],
                where="file = ? AND caller_function = ?"
            )
            cursor.execute(query, (source_file, current_func))
            all_calls = [
                {
                    'callee_function': row[0],
                    'param_name': row[1],
                    'argument_expr': row[2],
                    'line': row[3],
                    'file': source_file
                }
                for row in cursor.fetchall()
            ]

        if debug and all_calls:
            print(f"[INTER-CFG] Found {len(all_calls)} function calls from {current_func}", file=sys.stderr)

        # STEP 3: For each callee, check if taint propagates
        for call in all_calls:
            callee_func_raw = call['callee_function']
            # CRITICAL FIX: Normalize function name to match symbols table
            # function_call_args has "service.method", symbols has "method"
            callee_func = normalize_function_name(callee_func_raw)

            param_name = call.get('param_name', '')
            arg_expr = call.get('argument_expr', '')
            call_line = call.get('line', 0)

            # Build args_mapping: which tainted vars are passed to which parameters?
            propagated_taint = {}  # New taint state in callee
            args_mapping = {}

            for tainted_var in taint_state:
                if arg_expr and tainted_var in arg_expr:
                    # Tainted var is passed to this parameter
                    if param_name:
                        propagated_taint[param_name] = True
                        args_mapping[tainted_var] = param_name

                        if debug:
                            print(f"  -> {tainted_var} passed to {callee_func_raw} [{callee_func}]({param_name}) at line {call_line}", file=sys.stderr)

            # If no taint propagates, skip this call
            if not propagated_taint:
                continue

            # STEP 4: Use CFG analyzer for path-sensitive analysis (if available)
            # This gives us more precise taint propagation through the callee
            if analyzer:
                try:
                    effect = analyzer.analyze_function_call(
                        source_file, current_func,
                        source_file, callee_func,  # Use normalized name
                        args_mapping, taint_state
                    )

                    # Update propagated_taint based on CFG analysis
                    # If CFG shows taint doesn't actually propagate, don't add to worklist
                    if not (effect.return_tainted or any(effect.param_effects.values())):
                        if debug:
                            print(f"  [CFG] No taint propagation through {callee_func}", file=sys.stderr)
                        continue
                except Exception as e:
                    # CFG analysis failed - fall back to conservative assumption (taint propagates)
                    if debug:
                        print(f"  [CFG] Analysis failed for {callee_func}: {e}", file=sys.stderr)

            # STEP 5: Add callee to worklist for recursive analysis (use normalized name)
            new_call_path = call_path + [{
                "type": "call",
                "from_func": current_func,
                "to_func": callee_func,  # Use normalized name
                "var": list(taint_state.keys())[0] if taint_state else "unknown",
                "param": param_name,
                "line": call_line,
                "depth": depth
            }]

            worklist.append((callee_func, propagated_taint, depth + 1, new_call_path))

            if debug:
                print(f"  [WORKLIST] Added {callee_func} (from {callee_func_raw}) to worklist (depth {depth + 1})", file=sys.stderr)

    if debug:
        print(f"\n[INTER-CFG] Completed multi-hop analysis. Found {len(paths)} vulnerabilities", file=sys.stderr)

    return paths