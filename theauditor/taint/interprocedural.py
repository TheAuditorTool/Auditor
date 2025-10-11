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
        state_key = f"{current_file}:{current_func}:{current_var}:{depth}"
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
            
            # Track the parameter in the callee function
            new_path = path + [{
                "type": "argument_pass",
                "from_func": current_func,
                "to_func": callee_func,
                "var": current_var,
                "param": param_name,
                "line": call_line
            }]
            
            # Add to worklist to continue tracking in callee
            worklist.append((param_name, callee_func, current_file, depth + 1, new_path))
            
            # Step 2: Check if callee function contains any sinks using this parameter
            for sink in sinks:
                if sink["file"] != current_file:
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
    Stage 3: CFG-based inter-procedural taint tracking.
    
    This enhanced version uses Control Flow Graphs to understand:
    - Pass-by-reference modifications
    - Path-sensitive analysis within called functions
    - Dynamic dispatch resolution
    """
    from .core import TaintPath
    
    paths = []
    debug = os.environ.get("THEAUDITOR_TAINT_DEBUG") or os.environ.get("THEAUDITOR_CFG_DEBUG")
    
    if debug:
        print(f"\n[INTER-CFG] Starting Stage 3 inter-procedural analysis", file=sys.stderr)
        print(f"  Source: {source_var} in {source_function}", file=sys.stderr)
    
    # Track taint state across function calls
    taint_state = {source_var: True}
    
    # Analyze each sink
    for sink in sinks:
        if sink["file"] != source_file:
            continue
        
        # Get function containing sink
        sink_function = get_containing_function(cursor, sink)
        if not sink_function:
            continue
        
        # Check if we need inter-procedural analysis
        if sink_function["name"] == source_function:
            # Same function - use regular CFG analysis
            continue
        
        # Analyze call path from source to sink function
        args_mapping = {}  # Will be populated from call graph
        
        # Use CFG analyzer to check if taint reaches sink
        effect = analyzer.analyze_function_call(
            source_file, source_function,
            sink["file"], sink_function["name"],
            args_mapping, taint_state
        )
        
        # Check if sink is reached with tainted data
        if effect.return_tainted or any(effect.param_effects.values()):
            if debug:
                print(f"[INTER-CFG] Vulnerability found via {sink_function['name']}", file=sys.stderr)
            
            path_obj = TaintPath(
                source={"file": source_file, "line": source_line, "pattern": source_var, "name": source_var},
                sink=sink,
                path=[{
                    "type": "inter_procedural_cfg",
                    "effect": effect.param_effects,
                    "passthrough": effect.passthrough_taint
                }]
            )
            paths.append(path_obj)
    
    return paths