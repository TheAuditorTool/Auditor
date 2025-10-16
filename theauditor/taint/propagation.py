"""Taint propagation through assignments and data flow.

This module implements the worklist algorithm for tracking taint through
variable assignments and function calls within a single function scope.

Schema Contract:
    All queries use build_query() for schema compliance.
    Table existence is guaranteed by schema contract - no checks needed.
"""

import os
import sys
import sqlite3
import json
from typing import Dict, List, Set, Any, Optional, Tuple
from collections import deque

from theauditor.indexer.schema import build_query
from .sources import SANITIZERS, TAINT_SOURCES
from .database import (
    get_containing_function,
    get_function_boundaries,
    get_code_snippet,
    check_cfg_available,
)
from .interprocedural import trace_inter_procedural_flow_insensitive


def is_sanitizer(function_name: str) -> bool:
    """Check if a function is a known sanitizer."""
    if not function_name:
        return False
    
    # Normalize function name
    func_lower = function_name.lower()
    
    # Check all sanitizer categories
    for sanitizer_list in SANITIZERS.values():
        for sanitizer in sanitizer_list:
            if sanitizer.lower() in func_lower or func_lower in sanitizer.lower():
                return True
    
    return False


def has_sanitizer_between(cursor: sqlite3.Cursor, source: Dict[str, Any], sink: Dict[str, Any]) -> bool:
    """Check if there's a sanitizer call between source and sink in the same function.

    Schema Contract:
        Queries symbols table (guaranteed to exist)
    """
    if source["file"] != sink["file"]:
        return False

    # Find all calls between source and sink lines
    query = build_query('symbols', ['name', 'line'],
        where="path = ? AND type = 'call' AND line > ? AND line < ?",
        order_by="line"
    )
    cursor.execute(query, (source["file"], source["line"], sink["line"]))
    
    intermediate_calls = cursor.fetchall()
    
    # Check if any intermediate call is a sanitizer
    for call_name, _ in intermediate_calls:
        if is_sanitizer(call_name):
            return True
    
    return False


# ============================================================================
# DELETED: is_external_source() - 50 lines of string matching fallback
# ============================================================================
# This function existed because database queries returned empty results
# (symbols table had zero call/property records due to indexer bug).
#
# HARD FAILURE PROTOCOL:
# All sources from database are VALID by definition.
# If database returns invalid sources, fix the SOURCE PATTERNS or INDEXER.
#
# DO NOT re-add validation logic here. Validation belongs in:
#   1. Indexer extraction (what gets into symbols table)
#   2. Source pattern definitions (taint/sources.py)
#
# String matching validation = hiding bugs. Let it fail loud.
# ============================================================================


def trace_from_source(
    cursor: sqlite3.Cursor,
    source: Dict[str, Any],
    source_function: Dict[str, Any],
    sinks: List[Dict[str, Any]],
    call_graph: Dict[str, List[str]],
    max_depth: int,
    use_cfg: bool = False,
    stage3: bool = False,
    cache: Optional[Any] = None
) -> List[Any]:  # Returns List[TaintPath]
    """
    Trace taint propagation from a source to potential sinks using true data flow analysis.
    
    This implements a worklist algorithm that:
    1. Identifies variables tainted by the source
    2. Propagates taint through assignments
    3. Tracks taint through function calls and returns
    4. Only reports vulnerabilities when tainted data reaches a sink
    
    When use_cfg=True and CFG data is available, performs flow-sensitive analysis
    that distinguishes between different execution paths.
    """
    # Import TaintPath here to avoid circular dependency
    from .core import TaintPath

    # Define debug_mode once at function scope to avoid UnboundLocalError
    # Checks all debug environment variables used throughout this function
    debug_mode = (
        os.environ.get("THEAUDITOR_DEBUG") or
        os.environ.get("THEAUDITOR_TAINT_DEBUG") or
        os.environ.get("THEAUDITOR_CFG_DEBUG")
    )

    # HARD FAILURE PROTOCOL: No validation needed.
    # All sources from database are valid by definition.
    # If we get invalid sources, fix the indexer or source patterns.

    # Cache of per-sink CFG results so we reuse analysis when verifying flows
    flow_sensitive_cache: Dict[Tuple[str, int], Optional[List[TaintPath]]] = {}
    cfg_verifier_enabled = False

    # If CFG analysis is requested and available, use flow-sensitive analysis
    if use_cfg:
        from .cfg_integration import (
            trace_flow_sensitive,
            should_use_cfg,
            verify_unsanitized_cfg_paths,
        )

        cfg_verifier_enabled = check_cfg_available(cursor)

        # Check if we should use CFG for these specific sources/sinks
        cfg_paths: List[TaintPath] = []
        for sink in sinks:
            if should_use_cfg(cursor, source, sink):
                # Perform flow-sensitive analysis for this source-sink pair
                flow_paths = trace_flow_sensitive(
                    cursor=cursor,
                    source=source,
                    sink=sink,
                    source_function=source_function,
                    max_paths=100,  # Reasonable limit for path explosion
                )
                flow_sensitive_cache[(sink["file"], sink["line"])] = flow_paths
                cfg_paths.extend(flow_paths)

        # If we found any flow-sensitive paths, prefer those
        if cfg_paths:
            # Also run flow-insensitive for comparison (can be removed in production)
            if debug_mode:
                print(f"[CFG] Found {len(cfg_paths)} flow-sensitive paths", file=sys.stderr)
                print(f"[CFG] Running flow-insensitive analysis for comparison...", file=sys.stderr)
            # Convert flow-sensitive paths to TaintPath objects
            return cfg_paths
    else:
        cfg_verifier_enabled = False
    
    paths = []
    
    # CRITICAL FIX: Check for direct-use vulnerabilities FIRST
    # This handles cases like res.send(req.body) where tainted data flows directly to sink
    # without intermediate variable assignment
    for sink in sinks:
        # Check if source and sink are in the same function
        if sink["file"] == source_function["file"]:
            # Use actual function boundaries
            source_start, source_end = get_function_boundaries(
                cursor, source["file"], source_function["line"]
            )
            
            # Verify BOTH source and sink are within same function scope
            if (source_start <= source["line"] <= source_end and
                source_start <= sink["line"] <= source_end):
                # Guaranteed same function - no false positives
                # Check if there's a sanitizer between source and sink
                if not has_sanitizer_between(cursor, source, sink):
                    cfg_paths_for_sink: Optional[List[TaintPath]] = None
                    if cfg_verifier_enabled:
                        cfg_key = (sink["file"], sink["line"])
                        cfg_paths_for_sink = flow_sensitive_cache.get(cfg_key)

                        if cfg_paths_for_sink is None:
                            cfg_paths_for_sink = verify_unsanitized_cfg_paths(
                                cursor=cursor,
                                source=source,
                                sink=sink,
                                source_function=source_function,
                                max_paths=100,
                            )
                            flow_sensitive_cache[cfg_key] = cfg_paths_for_sink

                    if cfg_paths_for_sink is not None:
                        if not cfg_paths_for_sink:
                            if debug_mode:
                                print(
                                    f"[TAINT][CFG] Skipping sanitized path to sink {sink['pattern']} at "
                                    f"{sink['file']}:{sink['line']}",
                                    file=sys.stderr,
                                )
                            continue

                        paths.extend(cfg_paths_for_sink)
                        continue

                    # Direct vulnerability found - source flows directly to sink
                    path = TaintPath(
                        source=source,
                        sink=sink,
                        path=[
                            {
                                "type": "direct_use",
                                "location": f"{source['file']}:{source['line']}",
                                "code": get_code_snippet(source['file'], source['line'])
                            },
                            {
                                "type": "sink",
                                "location": f"{sink['file']}:{sink['line']}",
                                "code": get_code_snippet(sink['file'], sink['line'])
                            }
                        ]
                    )
                    paths.append(path)

    # ============================================================================
    # INITIAL TAINT IDENTIFICATION - Clean 2-Phase Strategy
    # ============================================================================
    # Phase 1: Look for variable assignments that capture this source
    # Phase 2: If no assignments, treat source pattern itself as tainted
    #
    # Rationale: Not all sources create assignments. For example:
    #   - Assignment-based: const userData = req.body;  [captured in assignments table]
    #   - Direct-use: res.send(req.body);               [no assignment, handled separately]
    #
    # Schema Contract: assignments table guaranteed to exist

    tainted_elements = set()

    if debug_mode:
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"[TAINT] Processing source: {source['pattern']} at {source['file']}:{source['line']}", file=sys.stderr)
        print(f"[TAINT] Source function: {source_function.get('name', 'unknown')} ({source_function['file']}:{source_function['line']})", file=sys.stderr)

    # PHASE 1: Find assignments that capture this specific source
    # Use ±2 line tolerance to handle multi-line statements
    query = build_query('assignments', ['target_var', 'in_function', 'line'],
        where="file = ? AND line BETWEEN ? AND ? AND source_expr LIKE ?",
        order_by="line"
    )
    cursor.execute(query, (
        source["file"],
        source["line"] - 2,
        source["line"] + 2,
        f"%{source['pattern']}%"
    ))

    assignments_found = cursor.fetchall()

    for target_var, in_function, line in assignments_found:
        tainted_elements.add(f"{in_function}:{target_var}")
        if debug_mode:
            print(f"[TAINT] Phase 1: Found assignment {target_var} in {in_function} at line {line}", file=sys.stderr)

    # PHASE 2: If no assignments found, treat source pattern itself as tainted
    # This ensures the worklist algorithm always has a starting point
    if not tainted_elements:
        func_name = source_function.get("name", "global")
        tainted_elements.add(f"{func_name}:{source['pattern']}")
        if debug_mode:
            print(f"[TAINT] Phase 2: No assignments found, treating source pattern as tainted: {func_name}:{source['pattern']}", file=sys.stderr)

    # Final diagnostic
    if debug_mode:
        print(f"[TAINT] Initial tainted elements: {tainted_elements}", file=sys.stderr)
        print(f"[TAINT] Will check {len(sinks)} potential sinks", file=sys.stderr)

    # DELETED: JavaScript-specific taint tracking (lines 298-305)
    # This called enhance_javascript_tracking() from taint/javascript.py
    # which did string parsing fallback because symbols table was empty.
    # Now that indexer populates call/property symbols, this is unnecessary.

    # DELETED: Python-specific taint tracking (lines 303-314)
    # This called enhance_python_tracking() from taint/python.py
    # which did string parsing fallback because symbols table was empty.
    # Now that indexer populates call/property symbols, this is unnecessary.

    # Step 2: Propagate taint through assignments (worklist algorithm)
    processed = set()
    iterations = 0
    max_iterations = 100  # Prevent infinite loops
    
    while tainted_elements - processed and iterations < max_iterations:
        iterations += 1
        new_taints = set()
        
        # Create stable copy to iterate over
        to_process = list(tainted_elements - processed)
        for element in to_process:
            processed.add(element)
            
            # Parse the element (format: "function:variable")
            if ":" in element:
                func_name, var_name = element.split(":", 1)
            else:
                func_name = "global"
                var_name = element
            
            # Find assignments where this tainted variable is used as source
            if cache and hasattr(cache, 'assignments_by_func'):
                # FAST: O(1) lookup in pre-indexed data
                assignments = cache.assignments_by_func.get((source["file"], func_name), [])
                
                # Python-side filtering (still faster than SQL)
                results = []
                for assignment in assignments:
                    if (var_name in assignment.get("source_expr", "") or
                        f'"{var_name}"' in assignment.get("source_vars", "")):
                        results.append((
                            assignment["target_var"],
                            assignment["in_function"],
                            assignment["line"]
                        ))
            else:
                # FALLBACK: Original query implementation
                query = build_query('assignments', ['target_var', 'in_function', 'line'],
                    where="file = ? AND in_function = ? AND (source_expr LIKE ? OR source_vars LIKE ?)"
                )
                cursor.execute(query, (source["file"], func_name, f"%{var_name}%", f'%"{var_name}"%'))
                results = cursor.fetchall()
            
            for target_var, in_function, line in results:
                new_element = f"{in_function}:{target_var}"
                if new_element not in processed:
                    # CRITICAL DEBUG: Log taint propagation through assignments
                    if os.environ.get("THEAUDITOR_TAINT_DEBUG"):
                        print(f"[TAINT] Propagating through assignment: {var_name} -> {target_var} in {in_function} at line {line}")
                    new_taints.add(new_element)
            
            # Track taint through function calls
            # Check if tainted variable is passed as argument
            if cache and hasattr(cache, 'calls_by_caller'):
                # FAST: O(1) lookup in pre-indexed data
                calls = cache.calls_by_caller.get((source["file"], func_name), [])
                
                # Python-side filtering
                call_results = []
                for call in calls:
                    if var_name in call.get("argument_expr", ""):
                        call_results.append((
                            call["callee_function"],
                            call["param_name"],
                            call["line"]
                        ))
            else:
                # FALLBACK: Original query implementation
                query = build_query('function_call_args', ['callee_function', 'param_name', 'line'],
                    where="file = ? AND caller_function = ? AND argument_expr LIKE ?"
                )
                cursor.execute(query, (source["file"], func_name, f"%{var_name}%"))
                call_results = cursor.fetchall()
            
            for callee_function, param_name, line in call_results:
                # The parameter in the callee function is now tainted
                new_element = f"{callee_function}:{param_name}"
                if new_element not in processed:
                    # CRITICAL DEBUG: Log taint propagation through function calls
                    if os.environ.get("THEAUDITOR_TAINT_DEBUG"):
                        print(f"[TAINT] Propagating through function call: {var_name} in {func_name} -> {param_name} in {callee_function} at line {line}")
                    new_taints.add(new_element)
                
                # Check if the callee function returns the tainted parameter
                if cache and hasattr(cache, 'returns_by_function'):
                    # FAST: O(1) lookup
                    returns = cache.returns_by_function.get((source["file"], callee_function), [])
                    found_return = False
                    for ret in returns:
                        if (param_name in ret.get("return_expr", "") or
                            f'"{param_name}"' in ret.get("return_vars", "")):
                            found_return = True
                            break
                else:
                    # FALLBACK: Original query
                    query = build_query('function_returns', ['return_expr'],
                        where="file = ? AND function_name = ? AND (return_expr LIKE ? OR return_vars LIKE ?)"
                    )
                    cursor.execute(query, (source["file"], callee_function, f"%{param_name}%", f'%"{param_name}"%'))
                    found_return = cursor.fetchone() is not None
                
                if found_return:
                    # Function returns tainted data
                    new_element = f"{callee_function}:__return__"
                    if new_element not in processed:
                        new_taints.add(new_element)
        
        tainted_elements.update(new_taints)
    
    # DEBUG: Log final tainted elements
    if debug_mode:
        print(f"[TAINT] Propagation completed after {iterations} iterations", file=sys.stderr)
        print(f"[TAINT] Final tainted elements: {tainted_elements}", file=sys.stderr)
        print(f"[TAINT] Checking {len(sinks)} sinks for vulnerabilities", file=sys.stderr)
    
    # Step 3: Check if any tainted element reaches a sink
    for sink in sinks:
        # Only check sinks in the same file for now (can be extended)
        if sink["file"] != source["file"]:
            continue
        
        # Get the function containing the sink
        sink_function = get_containing_function(cursor, sink)
        if not sink_function:
            continue
        
        # ENHANCEMENT: Also check for direct use of source pattern in sink arguments
        # This catches cases where source is used directly without variable assignment
        if sink_function["name"] == source_function["name"]:
            # Check if source pattern appears directly in sink's arguments
            query = build_query('function_call_args', ['argument_expr'],
                where="file = ? AND line = ? AND argument_expr LIKE ?",
                limit=1
            )
            cursor.execute(query, (sink["file"], sink["line"], f"%{source['pattern']}%"))

            if cursor.fetchone() is not None:
                # Direct use of source in sink arguments
                if not has_sanitizer_between(cursor, source, sink):
                    path = TaintPath(
                        source=source,
                        sink=sink,
                        path=[
                            {
                                "type": "direct_argument",
                                "location": f"{source['file']}:{source['line']}",
                                "pattern": source['pattern']
                            },
                            {
                                "type": "sink",
                                "location": f"{sink['file']}:{sink['line']}",
                                "pattern": sink['pattern']
                            }
                        ]
                    )
                    paths.append(path)
                    continue  # Move to next sink
        
        # Check if any tainted variable is used in the sink
        skip_sink_due_to_cfg = False
        for element in tainted_elements:
            if ":" in element:
                func_name, var_name = element.split(":", 1)
            else:
                func_name = "global"
                var_name = element
            
            # Skip if not in the same function as the sink - BUT try inter-procedural tracking
            if func_name != sink_function["name"]:
                # CRITICAL: Attempt inter-procedural tracking
                if debug_mode:
                    print(f"[TAINT] Attempting inter-procedural tracking: {var_name} in {func_name} to sink in {sink_function['name']}", file=sys.stderr)

                # CENTRALIZED DECISION LOGIC: Choose between CFG-sensitive and insensitive analysis
                if use_cfg and stage3:
                    # Use CFG-based flow-sensitive inter-procedural analysis
                    from .interprocedural import trace_inter_procedural_flow_cfg
                    from .interprocedural_cfg import InterProceduralCFGAnalyzer

                    analyzer = InterProceduralCFGAnalyzer(cursor, cache)
                    inter_paths = trace_inter_procedural_flow_cfg(
                        analyzer=analyzer,
                        cursor=cursor,
                        source_var=var_name,
                        source_file=source["file"],
                        source_line=source["line"],
                        source_function=func_name,
                        sinks=[sink],
                        max_depth=3,
                        cache=cache
                    )
                else:
                    # Use call-graph-based flow-insensitive analysis (faster, less precise)
                    inter_paths = trace_inter_procedural_flow_insensitive(
                        cursor=cursor,
                        source_var=var_name,
                        source_file=source["file"],
                        source_line=source["line"],
                        source_function=func_name,
                        sinks=[sink],  # Check just this specific sink
                        max_depth=3,  # Limited depth for performance
                        cache=cache  # Pass cache through
                    )
                
                if inter_paths:
                    # Found inter-procedural vulnerability!
                    if debug_mode:
                        print(f"[TAINT] INTER-PROCEDURAL VULNERABILITY FOUND via toss-the-salad!", file=sys.stderr)
                    paths.extend(inter_paths)
                elif debug_mode:
                    print(f"[TAINT] No inter-procedural path found from {var_name} to sink", file=sys.stderr)
                
                continue
            
            # Check if the tainted variable appears in the sink's context
            # This is a simplified check - ideally we'd parse the sink expression
            sink_context_found = False
            
            # CRITICAL DEBUG: Log sink checking
            if os.environ.get("THEAUDITOR_TAINT_DEBUG"):
                print(f"[TAINT] Checking if tainted var {var_name} in {func_name} reaches sink at {sink['file']}:{sink['line']}")
            
            # Check in function call arguments at the sink line
            query = build_query('function_call_args', ['argument_expr'],
                where="file = ? AND line = ? AND argument_expr LIKE ?"
            )
            cursor.execute(query, (sink["file"], sink["line"], f"%{var_name}%"))

            if cursor.fetchone():
                sink_context_found = True
                if os.environ.get("THEAUDITOR_TAINT_DEBUG"):
                    print(f"[TAINT] FOUND: Tainted var {var_name} reaches sink at line {sink['line']}!")
            
            # Also check if sink pattern matches and variable is in scope
            if not sink_context_found and var_name != "__return__":
                # Check if there's an assignment or usage near the sink
                query = build_query('assignments', ['line'],
                    where="file = ? AND in_function = ? AND line BETWEEN ? AND ? AND (target_var = ? OR source_expr LIKE ?)",
                    limit=1
                )
                cursor.execute(query, (sink["file"], func_name, sink["line"] - 5, sink["line"] + 5,
                     var_name, f"%{var_name}%"))

                if cursor.fetchone() is not None:
                    sink_context_found = True

            if sink_context_found:
                # Check for sanitizers between source and sink
                if not has_sanitizer_between(cursor, source, sink):
                    cfg_paths_for_sink = None
                    if (
                        cfg_verifier_enabled
                        and sink["file"] == source["file"]
                        and sink_function["name"] == source_function["name"]
                    ):
                        cfg_key = (sink["file"], sink["line"])
                        cfg_paths_for_sink = flow_sensitive_cache.get(cfg_key)

                        if cfg_paths_for_sink is None:
                            cfg_paths_for_sink = verify_unsanitized_cfg_paths(
                                cursor=cursor,
                                source=source,
                                sink=sink,
                                source_function=source_function,
                                max_paths=100,
                            )
                            flow_sensitive_cache[cfg_key] = cfg_paths_for_sink

                    if cfg_paths_for_sink is not None:
                        if not cfg_paths_for_sink:
                            if debug_mode:
                                print(
                                    f"[TAINT][CFG] Skipping sanitized branch to sink {sink['pattern']} at "
                                    f"{sink['file']}:{sink['line']}",
                                    file=sys.stderr,
                                )
                            skip_sink_due_to_cfg = True
                            break

                        paths.extend(cfg_paths_for_sink)
                        skip_sink_due_to_cfg = True
                        break

                    # We found a real taint path!
                    if debug_mode:
                        print(f"[TAINT] VULNERABILITY FOUND!", file=sys.stderr)
                        print(f"[TAINT]   Source: {source['pattern']} at line {source['line']}", file=sys.stderr)
                        print(f"[TAINT]   Sink: {sink['pattern']} at line {sink['line']}", file=sys.stderr)
                        print(f"[TAINT]   Via variable: {var_name}", file=sys.stderr)
                    path = TaintPath(
                        source=source,
                        sink=sink,
                        path=[
                            {
                                "type": "source", 
                                "location": f"{source['file']}:{source['line']}", 
                                "var": var_name,
                                "code": get_code_snippet(source['file'], source['line'])
                            },
                            {
                                "type": "propagation", 
                                "tainted_vars": list(tainted_elements)[:5],  # Limit for readability
                                "transformations": len(tainted_elements)
                            },
                            {
                                "type": "sink", 
                                "location": f"{sink['file']}:{sink['line']}", 
                                "var": var_name,
                                "code": get_code_snippet(sink['file'], sink['line'])
                            }
                        ]
                    )
                    paths.append(path)
                    break  # One path per sink is enough

        if skip_sink_due_to_cfg:
            continue
    
    return paths


def deduplicate_paths(paths: List[Any]) -> List[Any]:  # Returns List[TaintPath]
    """Deduplicate taint paths, keeping the shortest path for each source-sink pair.
    
    Clean implementation - only handles TaintPath objects now that cfg_integration
    has been fixed to create proper TaintPath objects instead of dicts.
    """
    unique = {}
    
    for path in paths:
        # Direct attribute access - no defensive checks needed
        key = (
            f"{path.source['file']}:{path.source['line']}",
            f"{path.sink['file']}:{path.sink['line']}"
        )
        
        if key not in unique or len(path.path) < len(unique[key].path):
            unique[key] = path
    
    return list(unique.values())


def trace_from_source_flow_sensitive(
    cursor: sqlite3.Cursor,
    source: Dict[str, Any],
    source_function: Dict[str, Any],
    sinks: List[Dict[str, Any]],
    call_graph: Dict[str, List[str]],
    max_depth: int,
    cache: Optional[Any] = None
) -> List[Any]:  # Returns List[TaintPath]
    """
    Flow-sensitive wrapper for trace_from_source.
    
    This function explicitly enables CFG-based flow-sensitive analysis,
    which distinguishes between different execution paths to reduce false positives.
    
    Example:
        # This would be a false positive in flow-insensitive analysis:
        user_input = req.body.data
        if (validate(user_input)) {
            db.query(user_input)  # Safe - only executed after validation
        } else {
            log_error("Invalid input")
        }
    
    Args:
        cursor: Database cursor
        source: Taint source information
        source_function: Function containing the source
        sinks: List of potential sinks
        call_graph: Function call graph
        max_depth: Maximum depth for interprocedural analysis
        
    Returns:
        List of TaintPath objects representing flow-sensitive vulnerabilities
    """
    return trace_from_source(
        cursor=cursor,
        source=source,
        source_function=source_function,
        sinks=sinks,
        call_graph=call_graph,
        max_depth=max_depth,
        use_cfg=True,  # Enable flow-sensitive analysis
        stage3=False,  # This wrapper is for Stage 2 only
        cache=cache  # Pass cache through
    )
