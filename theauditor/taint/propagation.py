"""Taint propagation through assignments and data flow.

This module implements the worklist algorithm for tracking taint through
variable assignments and function calls within a single function scope.
"""

import os
import sys
import sqlite3
import json
from typing import Dict, List, Set, Any, Optional
from collections import deque

from .sources import SANITIZERS, TAINT_SOURCES
from .database import get_containing_function, get_function_boundaries, get_code_snippet
from .interprocedural import trace_inter_procedural_flow


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
    """Check if there's a sanitizer call between source and sink in the same function."""
    if source["file"] != sink["file"]:
        return False
    
    # Find all calls between source and sink lines
    cursor.execute("""
        SELECT name, line
        FROM symbols
        WHERE path = ?
        AND type = 'call'
        AND line > ?
        AND line < ?
        ORDER BY line
    """, (source["file"], source["line"], sink["line"]))
    
    intermediate_calls = cursor.fetchall()
    
    # Check if any intermediate call is a sanitizer
    for call_name, _ in intermediate_calls:
        if is_sanitizer(call_name):
            return True
    
    return False


def is_external_source(cursor: sqlite3.Cursor, source: Dict[str, Any]) -> bool:
    """
    Validate if source actually handles external data.
    
    Returns True only for sources that truly bring in untrusted external data,
    not internal application data.
    """
    pattern = source.get("pattern", "")
    
    # Web scraping sources are always external
    web_scraping_patterns = [
        "requests.get", "requests.post", "requests.put", "requests.patch", "requests.delete",
        "response.text", "response.content", "response.json",
        "BeautifulSoup", "soup.find", "soup.find_all", "soup.select",
        "page.content", "page.inner_text", "page.inner_html",
        "driver.page_source", "element.text", "element.get_attribute",
        "urlopen", "urllib.request.urlopen"
    ]
    if pattern in web_scraping_patterns:
        return True
    
    # Web framework inputs are external
    web_input_patterns = [
        "req.body", "req.query", "req.params", "req.headers",
        "request.args", "request.form", "request.json", "request.data",
        "request.GET", "request.POST", "request.FILES"
    ]
    if pattern in web_input_patterns:
        return True
    
    # File I/O - check if reading external files
    if pattern in ["open", "json.load", "json.loads", "pd.read_csv", "pd.read_json", "pd.read_excel"]:
        # Check for nearby network/scraping calls suggesting external data
        cursor.execute("""
            SELECT COUNT(*) FROM symbols 
            WHERE path = ? AND line BETWEEN ? AND ?
            AND (name LIKE '%request%' OR name LIKE '%download%' 
                 OR name LIKE '%fetch%' OR name LIKE '%scrape%'
                 OR name LIKE '%BeautifulSoup%' OR name LIKE '%urlopen%')
        """, (source["file"], source["line"] - 50, source["line"] + 50))
        
        nearby_external_calls = cursor.fetchone()[0]
        return nearby_external_calls > 0
    
    # Environment variables and CLI args are external
    if pattern in ["os.getenv", "os.environ.get", "sys.argv", "input", "click.argument"]:
        return True
    
    # Conservative: if we're not sure, don't flag it
    return False


def trace_from_source(
    cursor: sqlite3.Cursor,
    source: Dict[str, Any],
    source_function: Dict[str, Any],
    sinks: List[Dict[str, Any]],
    call_graph: Dict[str, List[str]],
    max_depth: int,
    use_cfg: bool = False,
    stage3: bool = False
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
    
    # Validate source is truly external
    if not is_external_source(cursor, source):
        return []  # Skip internal sources
    
    # If CFG analysis is requested and available, use flow-sensitive analysis
    if use_cfg:
        from .cfg_integration import trace_flow_sensitive, should_use_cfg
        
        # Check if we should use CFG for these specific sources/sinks
        cfg_paths = []
        for sink in sinks:
            if should_use_cfg(cursor, source, sink):
                # Perform flow-sensitive analysis for this source-sink pair
                flow_paths = trace_flow_sensitive(
                    cursor=cursor,
                    source=source,
                    sink=sink,
                    source_function=source_function,
                    max_paths=100  # Reasonable limit for path explosion
                )
                cfg_paths.extend(flow_paths)
        
        # If we found any flow-sensitive paths, prefer those
        if cfg_paths:
            # Also run flow-insensitive for comparison (can be removed in production)
            debug_mode = os.environ.get("THEAUDITOR_TAINT_DEBUG") or os.environ.get("THEAUDITOR_CFG_DEBUG")
            if debug_mode:
                print(f"[CFG] Found {len(cfg_paths)} flow-sensitive paths", file=sys.stderr)
                print(f"[CFG] Running flow-insensitive analysis for comparison...", file=sys.stderr)
            # Convert flow-sensitive paths to TaintPath objects
            return cfg_paths
    
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
    
    # Check if the new data flow tables exist for assignment-based tracing
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='assignments'
    """)
    has_data_flow_tables = cursor.fetchone() is not None
    
    if not has_data_flow_tables:
        # Fall back to old proximity-based approach if tables don't exist
        # This maintains backward compatibility
        if paths:  # Return direct-use paths if found
            return paths
        return trace_from_source_legacy(cursor, source, source_function, sinks, call_graph, max_depth)
    
    # Initialize the set of tainted elements for assignment-based tracing
    # Format: "function:variable" or "function:__return__" for return values
    tainted_elements = set()
    
    # CRITICAL AMENDMENT: Check assignments table for taint source instantiation
    # Find initial tainted variables from assignments that match ANY taint source
    cursor.execute("""
        SELECT target_var, in_function, source_expr 
        FROM assignments 
        WHERE file = ? AND line BETWEEN ? AND ?
    """, (source["file"], source["line"] - 1, source["line"] + 1))
    
    initial_assignments = cursor.fetchall()
    
    # Get all taint source patterns for comparison
    all_taint_sources = []
    for source_list in TAINT_SOURCES.values():
        all_taint_sources.extend(source_list)
    
    # Check each assignment to see if it contains a taint source
    for target_var, in_function, source_expr in initial_assignments:
        # Check if the source expression contains any known taint source
        for source_pattern in all_taint_sources:
            if source_pattern in source_expr:
                # Add this variable as initially tainted
                tainted_elements.add(f"{in_function}:{target_var}")
                break  # Move to the next assignment
    
    # DEBUG: Log what we're looking for
    debug_mode = os.environ.get("THEAUDITOR_DEBUG") or os.environ.get("THEAUDITOR_TAINT_DEBUG")
    if debug_mode:
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"[TAINT] Processing source: {source['pattern']} at {source['file']}:{source['line']}", file=sys.stderr)
        print(f"[TAINT] Source function: {source_function.get('name', 'unknown')} ({source_function['file']}:{source_function['line']})", file=sys.stderr)
        print(f"[TAINT] Initial tainted variables: {tainted_elements}", file=sys.stderr)
        print(f"[TAINT] Found {len(sinks)} potential sinks to check", file=sys.stderr)
    
    # Step 1: Also check for direct assignment matching the specific source pattern
    # Check if the source directly taints a variable through assignment
    cursor.execute("""
        SELECT target_var, in_function FROM assignments 
        WHERE file = ? AND line = ? AND source_expr LIKE ?
    """, (source["file"], source["line"], f"%{source['pattern']}%"))
    
    initial_taints = cursor.fetchall()
    
    # DEBUG: Log what we found
    if debug_mode:
        print(f"[TAINT] Found {len(initial_taints)} initial taints from direct assignment", file=sys.stderr)
        for taint in initial_taints[:3]:  # Show first 3
            print(f"[TAINT]   - {taint[0]} in {taint[1]}", file=sys.stderr)
    if not initial_taints:
        # Try to find assignments near the source (within 3 lines)
        cursor.execute("""
            SELECT target_var, in_function, line, source_expr FROM assignments 
            WHERE file = ? AND line BETWEEN ? AND ? AND source_expr LIKE ?
        """, (source["file"], source["line"] - 1, source["line"] + 3, f"%{source['pattern']}%"))
        initial_taints = cursor.fetchall()
    
    # Add initially tainted variables to the worklist
    for row in initial_taints:
        target_var = row[0]
        in_function = row[1]
        tainted_elements.add(f"{in_function}:{target_var}")
    
    # If no direct assignment found, check if source is in a property access
    if not tainted_elements:
        # For sources like req.body, req.query, treat the entire expression as tainted
        if "." in source["pattern"]:
            # Find where this property is used
            cursor.execute("""
                SELECT target_var, in_function FROM assignments 
                WHERE file = ? AND source_expr LIKE ?
            """, (source["file"], f"%{source['pattern']}%"))
            for target_var, in_function in cursor.fetchall():
                tainted_elements.add(f"{in_function}:{target_var}")
        
        # ENHANCEMENT: If still no tainted elements, check for source usage in expressions
        # This helps catch cases where source is used in expressions without assignment
        if not tainted_elements:
            # Look for any usage of the source pattern in expressions
            cursor.execute("""
                SELECT DISTINCT in_function FROM assignments 
                WHERE file = ? AND (source_expr LIKE ? OR source_vars LIKE ?)
                LIMIT 1
            """, (source["file"], f"%{source['pattern']}%", f'%"{source["pattern"]}"%'))
            result = cursor.fetchone()
            if result:
                # Mark the source pattern itself as tainted in this function
                tainted_elements.add(f"{result[0]}:{source['pattern']}")
    
    # DEBUG: Log tainted elements before propagation
    if debug_mode:
        print(f"[TAINT] Tainted elements before propagation: {tainted_elements}", file=sys.stderr)
        if not tainted_elements:
            print(f"[TAINT] WARNING: No tainted elements found for source {source['pattern']}", file=sys.stderr)
            print(f"[TAINT]   This means taint will be LOST here!", file=sys.stderr)
    
    # CRITICAL FIX: For JavaScript, ensure source patterns create initial taint
    if source["file"].endswith(('.js', '.jsx', '.ts', '.tsx')):
        # If no tainted elements found yet for common JS sources, create one
        if not tainted_elements and source["pattern"] in ["req.body", "req.query", "req.params", "req.headers", "req.cookies"]:
            # Treat the source itself as tainted within its function scope
            func_name = source_function.get("name", "unknown")
            tainted_elements.add(f"{func_name}:{source['pattern']}")
            if debug_mode:
                print(f"[TAINT] Created initial taint for JS source: {func_name}:{source['pattern']}", file=sys.stderr)
    
    # ENHANCEMENT: Apply JavaScript-specific taint tracking
    if source["file"].endswith(('.js', '.jsx', '.ts', '.tsx')):
        from .javascript import enhance_javascript_tracking
        tainted_elements = enhance_javascript_tracking(
            cursor, source, tainted_elements, source["file"]
        )
        if debug_mode and tainted_elements:
            print(f"[TAINT] JavaScript enhancement added: {tainted_elements}", file=sys.stderr)
    
    # Step 2: Propagate taint through assignments (worklist algorithm)
    processed = set()
    iterations = 0
    max_iterations = 100  # Prevent infinite loops
    
    while tainted_elements - processed and iterations < max_iterations:
        iterations += 1
        new_taints = set()
        
        for element in tainted_elements - processed:
            processed.add(element)
            
            # Parse the element (format: "function:variable")
            if ":" in element:
                func_name, var_name = element.split(":", 1)
            else:
                func_name = "global"
                var_name = element
            
            # Find assignments where this tainted variable is used as source
            cursor.execute("""
                SELECT target_var, in_function, line FROM assignments 
                WHERE file = ? AND in_function = ? AND 
                (source_expr LIKE ? OR source_vars LIKE ?)
            """, (source["file"], func_name, f"%{var_name}%", f'%"{var_name}"%'))
            
            for target_var, in_function, line in cursor.fetchall():
                new_element = f"{in_function}:{target_var}"
                if new_element not in processed:
                    # CRITICAL DEBUG: Log taint propagation through assignments
                    if os.environ.get("THEAUDITOR_TAINT_DEBUG"):
                        print(f"[TAINT] Propagating through assignment: {var_name} -> {target_var} in {in_function} at line {line}")
                    new_taints.add(new_element)
            
            # Track taint through function calls
            # Check if tainted variable is passed as argument
            cursor.execute("""
                SELECT callee_function, param_name, line FROM function_call_args 
                WHERE file = ? AND caller_function = ? AND argument_expr LIKE ?
            """, (source["file"], func_name, f"%{var_name}%"))
            
            for callee_function, param_name, line in cursor.fetchall():
                # The parameter in the callee function is now tainted
                new_element = f"{callee_function}:{param_name}"
                if new_element not in processed:
                    # CRITICAL DEBUG: Log taint propagation through function calls
                    if os.environ.get("THEAUDITOR_TAINT_DEBUG"):
                        print(f"[TAINT] Propagating through function call: {var_name} in {func_name} -> {param_name} in {callee_function} at line {line}")
                    new_taints.add(new_element)
                
                # Check if the callee function returns the tainted parameter
                cursor.execute("""
                    SELECT return_expr FROM function_returns 
                    WHERE file = ? AND function_name = ? AND 
                    (return_expr LIKE ? OR return_vars LIKE ?)
                """, (source["file"], callee_function, f"%{param_name}%", f'%"{param_name}"%'))
                
                if cursor.fetchone():
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
            cursor.execute("""
                SELECT COUNT(*) FROM function_call_args 
                WHERE file = ? AND line = ? AND argument_expr LIKE ?
            """, (sink["file"], sink["line"], f"%{source['pattern']}%"))
            
            if cursor.fetchone()[0] > 0:
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
                
                # Try to trace inter-procedural flow from this tainted variable to the sink
                inter_paths = trace_inter_procedural_flow(
                    cursor=cursor,
                    source_var=var_name,
                    source_file=source["file"],
                    source_line=source["line"],
                    source_function=func_name,
                    sinks=[sink],  # Check just this specific sink
                    max_depth=3,  # Limited depth for performance
                    use_cfg=use_cfg,
                    stage3=stage3
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
            cursor.execute("""
                SELECT argument_expr FROM function_call_args 
                WHERE file = ? AND line = ? AND argument_expr LIKE ?
            """, (sink["file"], sink["line"], f"%{var_name}%"))
            
            if cursor.fetchone():
                sink_context_found = True
                if os.environ.get("THEAUDITOR_TAINT_DEBUG"):
                    print(f"[TAINT] FOUND: Tainted var {var_name} reaches sink at line {sink['line']}!")
            
            # Also check if sink pattern matches and variable is in scope
            if not sink_context_found and var_name != "__return__":
                # Check if there's an assignment or usage near the sink
                cursor.execute("""
                    SELECT COUNT(*) FROM assignments 
                    WHERE file = ? AND in_function = ? AND 
                    line BETWEEN ? AND ? AND 
                    (target_var = ? OR source_expr LIKE ?)
                """, (sink["file"], func_name, sink["line"] - 5, sink["line"] + 5,
                     var_name, f"%{var_name}%"))
                
                if cursor.fetchone()[0] > 0:
                    sink_context_found = True
            
            if sink_context_found:
                # Check for sanitizers between source and sink
                if not has_sanitizer_between(cursor, source, sink):
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
    
    return paths


def trace_from_source_legacy(
    cursor: sqlite3.Cursor,
    source: Dict[str, Any],
    source_function: Dict[str, Any],
    sinks: List[Dict[str, Any]],
    call_graph: Dict[str, List[str]],
    max_depth: int
) -> List[Any]:  # Returns List[TaintPath]
    """Legacy proximity-based taint tracing for backward compatibility."""
    # Import TaintPath here to avoid circular dependency
    from .core import TaintPath
    
    paths = []
    
    # Check if source function directly contains any sinks
    for sink in sinks:
        if sink["file"] == source_function["file"]:
            # Use unified boundary detection instead of arbitrary 100-line limit
            source_start, source_end = get_function_boundaries(
                cursor, source["file"], source_function["line"]
            )
            if source_start <= sink["line"] <= source_end:
                # Check if sink is in same function
                sink_function = get_containing_function(cursor, sink)
                if sink_function and sink_function["name"] == source_function["name"]:
                    # Check if there's a sanitizer between source and sink
                    if not has_sanitizer_between(cursor, source, sink):
                        # Only add path if no sanitizer found
                        path = TaintPath(
                            source=source,
                            sink=sink,
                            path=[source_function]
                        )
                        paths.append(path)
    
    # Trace interprocedural taint flow using BFS
    visited = set()
    sanitized_paths = set()  # Track paths that have been sanitized
    queue = deque([(source_function, [source_function], 0, False)])
    
    while queue:
        current_func, path, depth, is_sanitized = queue.popleft()
        
        if depth >= max_depth:
            continue
        
        func_key = f"{current_func['file']}:{current_func['name']}"
        if func_key in visited:
            continue
        visited.add(func_key)
        
        # Get functions called by current function
        called_functions = call_graph.get(func_key, [])
        
        for called_name in called_functions:
            # Check if this call is a sanitizer
            if is_sanitizer(called_name):
                # Mark this path as sanitized and continue tracing (but don't report vulnerabilities)
                is_sanitized = True
                sanitized_paths.add(func_key)
            
            # Check if this call is to a sink
            for sink in sinks:
                if called_name in sink["name"] or sink["pattern"] in called_name:
                    # Only report if path is not sanitized
                    if not is_sanitized:
                        taint_path = TaintPath(
                            source=source,
                            sink=sink,
                            path=path + [{"name": called_name, "type": "call", "file": sink["file"], "line": sink["line"]}]
                        )
                        paths.append(taint_path)
            
            # Find definition of called function
            cursor.execute("""
                SELECT path, line
                FROM symbols
                WHERE name = ?
                AND type = 'function'
                LIMIT 1
            """, (called_name.split(".")[-1],))  # Handle method calls
            
            func_def = cursor.fetchone()
            if func_def:
                next_func = {
                    "file": func_def[0],
                    "name": called_name,
                    "line": func_def[1]
                }
                queue.append((next_func, path + [next_func], depth + 1, is_sanitized))
    
    return paths


def deduplicate_paths(paths: List[Any]) -> List[Any]:  # Accepts/returns List[TaintPath]
    """Deduplicate taint paths, keeping the shortest path for each source-sink pair."""
    unique = {}
    
    for path in paths:
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
    max_depth: int
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
        stage3=False  # This wrapper is for Stage 2 only
    )