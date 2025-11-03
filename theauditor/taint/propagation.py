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
from .sources import TAINT_SOURCES
from .database import (
    get_containing_function,
    get_function_boundaries,
    get_code_snippet,
    check_cfg_available,
    resolve_function_identity,
)
from .interprocedural import trace_inter_procedural_flow_insensitive
from .registry import TaintRegistry
from .orm_utils import enhance_python_fk_taint


# DELETED: is_sanitizer() function (14 lines)
# Use registry.is_sanitizer() instead (provides same functionality)
# This eliminates duplicate code - registry.py has the canonical implementation


def has_sanitizer_between(cursor: sqlite3.Cursor, source: Dict[str, Any], sink: Dict[str, Any]) -> bool:
    """Check if there's a sanitizer call between source and sink in the same function.

    Schema Contract:
        Queries symbols table (guaranteed to exist)
    """
    if source["file"] != sink["file"]:
        return False

    # Initialize registry for sanitizer checking
    registry = TaintRegistry()

    # Find all calls between source and sink lines
    query = build_query('symbols', ['name', 'line'],
        where="path = ? AND type = 'call' AND line > ? AND line < ?",
        order_by="line"
    )
    cursor.execute(query, (source["file"], source["line"], sink["line"]))

    intermediate_calls = cursor.fetchall()

    # Check if any intermediate call is a sanitizer using registry
    for call_name, _ in intermediate_calls:
        if registry.is_sanitizer(call_name):
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

    Stage Selection:
    - use_cfg=True: Stage 3 (CFG-based multi-hop with worklist)
    - use_cfg=False: Stage 2 (call-graph flow-insensitive)

    Note: The stage3 parameter was removed in v1.2.1 - use_cfg now controls everything.
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

    # Import CFG integration functions (needed for direct-use checks and intra-procedural verification)
    # NOT used for old conflicting engine - that was deleted (Bug #12)
    from .cfg_integration import verify_unsanitized_cfg_paths

    cfg_verifier_enabled = check_cfg_available(cursor) if use_cfg else False
    
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

    # PHASE 1.5: Track arguments that receive tainted data (NEW - CRITICAL FIX)
    # This enables cross-file taint tracking by following function call arguments
    #
    # Bug context: Phase 1 captures LEFT side of assignments (return values)
    # but taint flows through RIGHT side (arguments). This phase fixes that.
    #
    # Example:
    #   const entity = await accountService.createAccount(req.body, 'system');
    #   Phase 1 captures: "entity" (return value) ❌
    #   Phase 1.5 captures: "accountService.createAccount:data" (parameter) ✅
    #
    query = build_query('function_call_args',
        ['callee_function', 'param_name', 'argument_expr', 'callee_file_path'],
        where="file = ? AND line BETWEEN ? AND ? AND argument_expr LIKE ?",
        order_by="line"
    )
    cursor.execute(query, (
        source["file"],
        source["line"] - 2,
        source["line"] + 2,
        f"%{source['pattern']}%"
    ))

    call_args_found = cursor.fetchall()

    for callee_func, param_name, arg_expr, callee_file in call_args_found:
        # Verify source pattern actually appears in argument (not just substring match)
        if source['pattern'] in arg_expr:
            # Track the parameter in the callee function
            tainted_elements.add(f"{callee_func}:{param_name}")

            if debug_mode:
                print(f"[TAINT] Phase 1.5: Found argument {param_name} in call to {callee_func} at {source['file']}:{source['line']}", file=sys.stderr)
                if callee_file:
                    print(f"[TAINT]   Target file: {callee_file}", file=sys.stderr)

    # PHASE 2: ALWAYS add source pattern itself to tainted elements
    # CRITICAL FIX: Phase 1 may find return value assignments (e.g., "entity"),
    # but cross-file detection needs the SOURCE PATTERN (e.g., "req.body") to match arguments
    #
    # Example bug:
    #   const entity = await service.create(req.body);
    #   Phase 1 finds: "entity" ✓
    #   Phase 1.5 finds: "service.create:data" ✓
    #   Stage 3 traverses into service with tainted_vars={"entity"}
    #   Checks if "entity" in "req.body" → FALSE → No traversal! ✗
    #
    # Fix: Also add "req.body" to tainted_vars so Stage 3 can match arguments
    #
    # Note: get_containing_function() now returns CANONICAL function names from symbols table
    # (e.g., "AccountController.create" not "asyncHandler_arg0"), so this works correctly
    func_name = source_function.get("name", "global")
    source_pattern = source['pattern']
    tainted_elements.add(f"{func_name}:{source_pattern}")
    if "." in source_pattern:
        segments = source_pattern.split(".")
        # Add hierarchical prefixes (e.g., req, req.params) to preserve alias mapping
        for i in range(1, len(segments)):
            prefix = ".".join(segments[:i])
            if prefix:
                tainted_elements.add(f"{func_name}:{prefix}")
    if debug_mode:
        print(f"[TAINT] Phase 2: Added source pattern to tainted elements: {func_name}:{source['pattern']}", file=sys.stderr)

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

    # ============================================================================
    # DELETED: Old worklist algorithm (lines 293-401) - THE MULTI-HOP BUG
    # ============================================================================
    # This loop tried to propagate taint inter-procedurally but FAILED because:
    # 1. All queries were locked to source["file"] (lines 331-334, 362-365)
    # 2. It polluted tainted_elements with cross-file variables like "service.save:user_data"
    # 3. When processing those cross-file variables, queries returned ZERO ROWS
    # 4. Taint propagation STOPPED at file boundaries
    #
    # Example of the bug:
    #   Controller: req.body → "AccountController.create:data" ✅
    #   Call found: accountService.createAccount(data) ✅
    #   Worklist adds: "accountService.createAccount:accountData" ✅
    #   Worklist tries: WHERE file='controller.ts' AND in_function='accountService.createAccount' ❌
    #   Result: ZERO ROWS (service is in different file) ❌
    #
    # SOLUTION: The pro-active inter-procedural search (lines 418-516) handles
    # ALL propagation correctly, including cross-file flows. This old worklist
    # was fighting against it.
    # ============================================================================

    # ============================================================================
    # CRITICAL FIX (v1.2.1): PRO-ACTIVE INTER-PROCEDURAL SEARCH
    # ============================================================================
    # Run inter-procedural analysis FIRST for ALL sinks, not just same-file sinks.
    # This catches the common case: Controller → Service → Model flows.
    #
    # Previous bug: Only checked same-file sinks (line 420), missing cross-file flows.
    # Fix: Pro-actively search for inter-procedural paths before intra-procedural loop.

    if use_cfg:
        # Stage 3: CFG-based multi-hop analysis for ALL sinks (including cross-file)
        if debug_mode:
            print(f"[TAINT] Running pro-active inter-procedural analysis for all {len(sinks)} sinks", file=sys.stderr)

        from .interprocedural import trace_inter_procedural_flow_cfg
        from .interprocedural_cfg import InterProceduralCFGAnalyzer

        analyzer = InterProceduralCFGAnalyzer(cursor, cache)

        # CRITICAL FIX: Group tainted_elements by function to enable multi-hop cross-file
        # Previous bug: Only traced vars from source function, discarded cross-file tainted elements
        # like "accountService.createAccount:data" because func_name != start_func_name
        start_func_name = source_function.get("name", "global")
        tainted_by_function = {}  # func_name -> {var1, var2, ...}

        start_display_name = source_function.get("name", "global")
        start_canonical_name, start_file_hint = resolve_function_identity(
            cursor,
            start_display_name,
            source["file"]
        )

        tainted_by_function: Dict[str, Dict[str, Any]] = {}

        def record_tainted_function(func_display: str, var_name: str) -> None:
            canonical_name, resolved_file = resolve_function_identity(
                cursor,
                func_display,
                None
            )
            entry = tainted_by_function.setdefault(
                canonical_name,
                {"vars": set(), "displays": set(), "file": resolved_file}
            )
            entry["vars"].add(var_name)
            entry["displays"].add(func_display)
            if resolved_file:
                entry["file"] = resolved_file

        for element in tainted_elements:
            if ":" in element:
                func_display, var_name = element.split(":", 1)
                record_tainted_function(func_display, var_name)
            else:
                record_tainted_function(start_display_name, element)

        enhance_python_fk_taint(cursor, cache, tainted_by_function)

        if debug_mode:
            debug_repr = {
                name: {
                    "vars": list(info["vars"]),
                    "aliases": list(info["displays"])
                }
                for name, info in tainted_by_function.items()
            }
            print(f"[TAINT] Grouped tainted elements by function: {debug_repr}", file=sys.stderr)

        # Process EACH tainted function (not just source function!)
        inter_paths = []
        ordered_keys: List[str] = []
        primary_candidates = [
            start_canonical_name if 'start_canonical_name' in locals() else None,
            start_display_name
        ]
        for candidate in primary_candidates:
            if candidate and candidate in tainted_by_function and candidate not in ordered_keys:
                ordered_keys.append(candidate)
        for func_name in tainted_by_function.keys():
            if func_name not in ordered_keys:
                ordered_keys.append(func_name)

        for func_name in ordered_keys:
            func_info = tainted_by_function.get(func_name)
            if not func_info:
                continue
            vars_to_trace = func_info["vars"]
            if not vars_to_trace:
                continue

            display_aliases = func_info["displays"]
            display_name = next(iter(display_aliases), func_name)

            if func_name == start_canonical_name:
                func_file_path = start_file_hint or source_function.get("file_path", source["file"])
                func_line = source["line"]
            else:
                func_file_path = func_info.get("file")
                func_line = None

                func_file_query = build_query(
                    "symbols", ["path", "line"], where="name = ? AND type = 'function'", limit=1
                )
                cursor.execute(func_file_query, (func_name,))
                result = cursor.fetchone()
                if result:
                    func_file_path, func_line = result[0], result[1]
                else:
                    callee_query = build_query(
                        "function_call_args", ["callee_file_path"],
                        where="callee_function = ?", limit=1
                    )
                    cursor.execute(callee_query, (func_name,))
                    result = cursor.fetchone()
                    if result and result[0]:
                        func_file_path = result[0]
                    if func_line is None:
                        func_line = 1

            if func_file_path:
                func_file_path = func_file_path.replace("\\", "/")

            if not func_file_path:
                if debug_mode:
                    print(f"[TAINT] WARNING: Could not resolve file path for {func_name}, skipping", file=sys.stderr)
                continue

            if func_line is None:
                func_line = 1

            if debug_mode:
                print(f"[TAINT] Tracing from {func_name} in {func_file_path} with vars: {vars_to_trace}", file=sys.stderr)

            paths_from_func = trace_inter_procedural_flow_cfg(
                analyzer=analyzer,
                cursor=cursor,
                source_vars=vars_to_trace,  # Pass entire set for this function
                source_file=func_file_path,
                source_line=func_line,
                source_function=display_name,
                sinks=sinks,  # ALL sinks, including cross-file
                max_depth=max_depth,
                cache=cache,
                origin_source=source
            )

            if paths_from_func:
                if debug_mode:
                    print(f"[TAINT] Found {len(paths_from_func)} paths from {func_name}", file=sys.stderr)
                inter_paths.extend(paths_from_func)

        if inter_paths:
            if debug_mode:
                print(f"[TAINT] Pro-active inter-procedural found {len(inter_paths)} paths total", file=sys.stderr)
            paths.extend(inter_paths)
    else:
        # Stage 2: Flow-insensitive inter-procedural analysis for ALL sinks (including cross-file)
        # BUG FIX: Previously skipped all cross-file sinks. Now calling the inter-procedural function.
        if debug_mode:
            print(f"[TAINT] Running flow-insensitive inter-procedural analysis for all {len(sinks)} sinks", file=sys.stderr)

        start_display_name = source_function.get("name", "global")
        start_canonical_name, start_file_hint = resolve_function_identity(
            cursor,
            start_display_name,
            source["file"]
        )

        tainted_by_function: Dict[str, Dict[str, Any]] = {}

        def record_tainted_function(func_display: str, var_name: str) -> None:
            canonical_name, resolved_file = resolve_function_identity(
                cursor,
                func_display,
                None
            )
            entry = tainted_by_function.setdefault(
                canonical_name,
                {"vars": set(), "displays": set(), "file": resolved_file}
            )
            entry["vars"].add(var_name)
            entry["displays"].add(func_display)
            if resolved_file:
                entry["file"] = resolved_file

        for element in tainted_elements:
            if ":" in element:
                func_display, var_name = element.split(":", 1)
                record_tainted_function(func_display, var_name)
            else:
                record_tainted_function(start_display_name, element)

        enhance_python_fk_taint(cursor, cache, tainted_by_function)

        if debug_mode:
            debug_repr = {
                name: {
                    "vars": list(info["vars"]),
                    "aliases": list(info["displays"])
                }
                for name, info in tainted_by_function.items()
            }
            print(f"[TAINT] Grouped tainted elements by function: {debug_repr}", file=sys.stderr)

        # Process EACH tainted function (not just source function!)
        inter_paths = []
        for func_name, func_info in tainted_by_function.items():
            vars_to_trace = func_info["vars"]
            if not vars_to_trace:
                continue

            display_aliases = func_info["displays"]
            display_name = next(iter(display_aliases), func_name)

            if func_name == start_canonical_name:
                func_file_path = start_file_hint or source_function.get("file_path", source["file"])
                func_line = source["line"]
            else:
                func_file_path = func_info.get("file")
                func_line = None

                func_file_query = build_query(
                    "symbols", ["path", "line"], where="name = ? AND type = 'function'", limit=1
                )
                cursor.execute(func_file_query, (func_name,))
                result = cursor.fetchone()
                if result:
                    func_file_path, func_line = result[0], result[1]
                else:
                    callee_query = build_query(
                        "function_call_args", ["callee_file_path"],
                        where="callee_function = ?", limit=1
                    )
                    cursor.execute(callee_query, (func_name,))
                    result = cursor.fetchone()
                    if result and result[0]:
                        func_file_path = result[0]
                    if func_line is None:
                        func_line = 1

            if func_file_path:
                func_file_path = func_file_path.replace("\\", "/")

            if not func_file_path:
                if debug_mode:
                    print(f"[TAINT] WARNING: Could not resolve file path for {func_name}, skipping", file=sys.stderr)
                continue

            if func_line is None:
                func_line = 1

            if debug_mode:
                print(f"[TAINT] Tracing from {func_name} in {func_file_path} with vars: {vars_to_trace}", file=sys.stderr)

            # Trace EACH variable from this function
            for source_var in vars_to_trace:
                if not source_var:
                    continue

                if debug_mode:
                    print(f"[TAINT] Tracing variable: '{source_var}' from {func_name}", file=sys.stderr)

                paths_for_var = trace_inter_procedural_flow_insensitive(
                    cursor=cursor,
                    source_var=source_var,
                    source_file=func_file_path,
                    source_line=func_line,
                    source_function=display_name,
                    sinks=sinks,  # ALL sinks, including cross-file
                    max_depth=max_depth,
                    cache=cache,
                    origin_source=source
                )
                inter_paths.extend(paths_for_var)

        if inter_paths:
            if debug_mode:
                print(f"[TAINT] Flow-insensitive inter-procedural found {len(inter_paths)} paths total", file=sys.stderr)
            paths.extend(inter_paths)

    return paths


def deduplicate_paths(paths: List[Any]) -> List[Any]:  # Returns List[TaintPath]
    """Deduplicate taint paths while preserving the most informative flow for each source-sink pair.

    Key rule: Prefer cross-file / multi-hop and flow-sensitive paths over shorter, same-file variants.
    This prevents the Stage 2 direct path (2 steps) from overwriting Stage 3 multi-hop results.
    """

    def _path_score(path: Any) -> tuple[int, int, int]:
        """Score paths so we keep the most informative version per source/sink pair.

        Score dimensions (higher is better):
        1. Number of cross-file hops (`cfg_call`, `argument_pass`, `return_flow`)
        2. Whether the path used flow-sensitive analysis (Stage 3)
        3. Path length (prefer longer when cross-file, shorter otherwise)
        """
        steps = path.path or []

        cross_hops = 0
        uses_cfg = bool(getattr(path, "flow_sensitive", False))

        for step in steps:
            step_type = step.get("type")
            if step_type == "cfg_call":
                uses_cfg = True  # Ensure cfg-aware paths win ties
            if step_type in {"cfg_call", "argument_pass", "return_flow"}:
                from_file = step.get("from_file")
                to_file = step.get("to_file")
                # Always print for cfg_call to debug
                if step_type == "cfg_call":
                    print(f"[DEDUP] cfg_call step: from={from_file} to={to_file}", file=sys.stderr)
                if from_file and to_file and from_file != to_file:
                    cross_hops += 1
                    print(f"[DEDUP] Cross-file hop detected! cross_hops={cross_hops}", file=sys.stderr)

        length = len(steps)

        # Prefer longer paths when they traverse files, shorter otherwise (cleaner intra-file output)
        length_component = length if cross_hops else -length

        if cross_hops > 0:
            print(f"[DEDUP] Path score: cross_hops={cross_hops}, uses_cfg={1 if uses_cfg else 0}, length={length_component}", file=sys.stderr)

        return (cross_hops, 1 if uses_cfg else 0, length_component)

    # Phase 1: retain the best path for each unique source/sink pairing.
    unique_source_sink: Dict[tuple[str, str], tuple[Any, tuple[int, int, int]]] = {}

    for path in paths:
        key = (
            f"{path.source['file']}:{path.source['line']}",
            f"{path.sink['file']}:{path.sink['line']}",
        )
        score = _path_score(path)

        if key not in unique_source_sink or score > unique_source_sink[key][1]:
            unique_source_sink[key] = (path, score)

    if not unique_source_sink:
        return []

    # Phase 2: group by sink location so we only emit one finding per sink line.
    sink_groups: Dict[tuple[str, int], List[Any]] = {}
    for path, _score in unique_source_sink.values():
        sink = path.sink
        sink_key = (sink.get("file", "unknown_file"), sink.get("line", 0))
        sink_groups.setdefault(sink_key, []).append(path)

    deduped_paths: List[Any] = []
    for sink_key, sink_paths in sink_groups.items():
        if not sink_paths:
            continue

        scored_paths = [(p, _path_score(p)) for p in sink_paths]
        scored_paths.sort(key=lambda item: item[1], reverse=True)
        best_path, _ = scored_paths[0]

        # Reset aggregation before attaching related sources
        best_path.related_sources = []

        for other_path, _ in scored_paths[1:]:
            best_path.add_related_path(other_path)

        deduped_paths.append(best_path)

    # Debug: Check what we're returning
    multi_file_count = sum(1 for p in deduped_paths if p.source.get('file') != p.sink.get('file'))
    print(f"[DEDUP] Returning {len(deduped_paths)} paths ({multi_file_count} multi-file)", file=sys.stderr)

    return deduped_paths


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
        use_cfg=True,  # Enable CFG-based flow-sensitive analysis (Stage 3)
        cache=cache  # Pass cache through
    )
