"""
Inter-procedural taint tracking engine with full cross-file, multi-hop support.

This module implements the complete, file-aware worklist algorithms for both
flow-insensitive (Stage 2) and flow-sensitive (Stage 3/CFG) taint analysis,
fulfilling the architectural vision outlined in the project documentation.

Key Architectural Principles:
- File-Aware Worklist: The core of cross-file analysis. The state tuple in the
  worklist includes the current file context, allowing taint to be followed
  naturally across module boundaries.
- Unambiguous Call Resolution: Leverages the `callee_file_path` from the
  database (a required schema enhancement) to deterministically find the exact
  file for any given function call, eliminating the primary bug in the previous
  implementation.
- No Cross-File Guards: All artificial barriers that prevented the analyzer
  from looking for sinks in different files have been removed.
- Return Value Tracking: Correctly tracks how tainted data flows out of
  functions and back into calling contexts.
- Cycle Detection: Robust cycle detection prevents infinite loops in cases
  of mutual recursion, ensuring the analysis always terminates.

Schema Contract:
- All queries use build_query() for schema compliance.
- Assumes the `function_call_args` table has a `callee_file_path` column. If this
  column is missing, the indexer must be updated. This contract is critical for
  unambiguous call resolution.
"""

import json
import os
import re
import sys
import sqlite3
from collections import defaultdict
from typing import Dict, List, Any, Optional, Set, TYPE_CHECKING

from theauditor.indexer.schema import build_query
from .database import get_containing_function, get_code_snippet, resolve_function_identity, get_function_boundaries

if TYPE_CHECKING:
    from .core import TaintPath
    from .memory_cache import MemoryCache
    from .interprocedural_cfg import InterProceduralCFGAnalyzer


def normalize_function_name(func_name: str) -> str:
    """
    Normalizes function names by stripping module/object prefixes for matching.
    e.g., service.create -> create. This is used as a fallback only when
    direct resolution fails.
    """
    if not func_name:
        return ""
    return func_name.split('.')[-1]


def trace_inter_procedural_flow_insensitive(
    cursor: sqlite3.Cursor,
    source_var: str,
    source_file: str,
    source_line: int,
    source_function: str,
    sinks: List[Dict[str, Any]],
    max_depth: int = 5,
    cache: Optional['MemoryCache'] = None,
    origin_source: Optional[Dict[str, Any]] = None
) -> List['TaintPath']:
    """
    Implements a file-aware, multi-hop, flow-insensitive taint tracking algorithm.
    This version correctly follows taint across file boundaries via function calls
    and return values.
    """
    from .core import TaintPath

    if origin_source is None:
        origin_source = {
            "file": source_file,
            "line": source_line,
            "pattern": source_var,
            "name": source_var
        }
    else:
        origin_source = {
            "file": origin_source.get("file", source_file),
            "line": origin_source.get("line", source_line),
            "pattern": origin_source.get("pattern", source_var),
            "name": origin_source.get("name", origin_source.get("pattern", source_var))
        }

    paths: List[TaintPath] = []
    debug = os.environ.get("THEAUDITOR_TAINT_DEBUG") or os.environ.get("THEAUDITOR_DEBUG")

    if debug:
        print(f"[INTER-PROCEDURAL-S2] Starting Stage 2 analysis", file=sys.stderr)
        print(f"  Source '{source_var}' in {source_function} at {source_file}:{source_line}", file=sys.stderr)

    # Worklist stores the state to be processed:
    # (current_var, current_function, current_file, depth, path_so_far)
    worklist: List[tuple[str, str, str, int, list]] = [(source_var, source_function, source_file, 0, [])]

    # visited prevents re-processing the same state (file, function, var) to avoid cycles.
    visited: Set[tuple[str, str, str]] = set()

    while worklist:
        current_var, current_func, current_file, depth, path = worklist.pop(0)

        if depth > max_depth:
            continue

        state_key = (current_file, current_func, current_var)
        if state_key in visited:
            continue
        visited.add(state_key)

        if debug:
            print(f"[INTER-PROCEDURAL-S2] Depth {depth}: Tracking '{current_var}' in {current_func} ({current_file})", file=sys.stderr)

        # 1. Check for sinks in the current context.
        for sink in sinks:
            if sink["file"] != current_file:
                continue

            sink_function = get_containing_function(cursor, sink)
            if sink_function:
                # Normalize both sides for comparison (both may have prefixes like "service.method")
                sink_func_normalized = sink_function["name"].split('.')[-1].lower()
                current_func_normalized = current_func.split('.')[-1].lower()

                if sink_func_normalized == current_func_normalized:
                    # The sink is in the current function. Check if our tainted var reaches it.
                    sink_query = build_query(
                        'function_call_args',
                        ['callee_function', 'argument_expr'],
                        where="file = ? AND line = ?"
                    )
                    cursor.execute(sink_query, (current_file, sink["line"]))
                    matches = cursor.fetchall()

                    sink_hit = False
                    for callee_func, argument_expr in matches:
                        arg_text = argument_expr or ""
                        if current_var and current_var in arg_text:
                            sink_hit = True
                            break
                        if current_var and callee_func:
                            callee_text = callee_func.strip()
                            if callee_text.startswith(f"{current_var}.") or callee_text.endswith(f".{current_var}"):
                                sink_hit = True
                                break

                    if sink_hit:
                        if debug:
                            print(f"[INTER-PROCEDURAL-S2] VULNERABILITY FOUND: '{current_var}' reaches sink '{sink['pattern']}'", file=sys.stderr)
                        vuln_path = path + [{"type": "sink_reached", "func": current_func, "var": current_var, "sink": sink["pattern"], "line": sink["line"]}]
                        paths.append(TaintPath(source=origin_source.copy(), sink=sink, path=vuln_path))

        # 2. Propagate taint to other functions (cross-file).
        # Find all function calls within the current function that use the tainted variable as an argument.
        # Use line boundaries instead of relying on caller_function string (handles comment-prefixed names)
        canonical_current, resolved_file = resolve_function_identity(cursor, current_func, current_file)
        lookup_names = [name for name in {current_func, canonical_current} if name]
        search_file = (resolved_file or current_file).replace("\\", "/")

        func_start = None
        func_end = None
        for name in lookup_names:
            bounds_query = build_query(
                'symbols',
                ['line', 'end_line'],
                where="path = ? AND type = 'function' AND name = ?",
                limit=1
            )
            cursor.execute(bounds_query, (search_file, name))
            row = cursor.fetchone()
            if row:
                func_start = row[0]
                func_end = row[1] or (row[0] + 200)
                break

        if func_start is None or func_end is None:
            # Fallback: cover entire file to avoid missing calls (should be rare)
            func_start = 0
            func_end = 10**9

        query = build_query(
            'function_call_args',
            ['callee_function', 'param_name', 'line', 'callee_file_path', 'argument_expr'],
            where="file = ? AND line >= ? AND line <= ? AND (argument_expr = ? OR argument_expr LIKE ?)"
        )
        cursor.execute(
            query,
            (search_file, func_start, func_end, current_var, f"%{current_var}%")
        )

        for callee_func, param_name, call_line, callee_file_path, argument_expr in cursor.fetchall():
            if not callee_file_path:
                if debug:
                    print(f"[INTER-PROCEDURAL-S2] WARNING: Could not resolve file for call to '{callee_func}' at {current_file}:{call_line}. Skipping.", file=sys.stderr)
                continue  # Skip calls we cannot resolve to a file.

            callee_file = callee_file_path.replace('\\', '/')
            if debug and callee_file != current_file:
                print(f"[INTER-PROCEDURAL-S2] Cross-file call: {current_file} -> {callee_file} ({current_func} -> {callee_func})", file=sys.stderr)

            new_path = path + [{"type": "argument_pass", "from_file": current_file, "from_func": current_func, "to_file": callee_file, "to_func": callee_func, "var": current_var, "param": param_name, "line": call_line}]

            propagated_names: Set[str] = set()
            if param_name:
                propagated_names.add(param_name)

            if argument_expr:
                candidate = argument_expr.strip()
                # Handle TypeScript non-null assertions like userId!
                if candidate.endswith("!"):
                    candidate = candidate[:-1]

                # Only use simple identifiers (avoid complex expressions)
                if candidate and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", candidate):
                    propagated_names.add(candidate)

            if not propagated_names:
                propagated_names.add(param_name or current_var)

            for propagated_var in propagated_names:
                worklist.append((propagated_var, callee_func, callee_file, depth + 1, new_path))

        # 3. Propagate taint through return values.
        # Find if the current tainted variable is returned by the current function.
        # Handle both normalized and fully-qualified function names
        # NORMALIZATION FIX: return_vars column removed, use UNION to check both return_expr and junction table
        combined_query = """
            SELECT return_expr, line FROM function_returns
            WHERE file = ? AND (function_name = ? OR function_name LIKE ?)
              AND (return_expr = ? OR return_expr LIKE ?)
            UNION
            SELECT fr.return_expr, fr.line
            FROM function_returns fr
            INNER JOIN function_return_sources frs
                ON fr.file = frs.return_file
                AND fr.line = frs.return_line
                AND fr.function_name = frs.return_function
            WHERE fr.file = ?
              AND (fr.function_name = ? OR fr.function_name LIKE ?)
              AND frs.return_var_name = ?
        """
        cursor.execute(combined_query, (
            current_file, current_func, f"%.{current_func}", current_var, f"%{current_var}%",
            current_file, current_func, f"%.{current_func}", current_var
        ))

        for return_expr, return_line in cursor.fetchall():
            # Now, find where the current function was called and its return value assigned to a new variable.
            # This query looks backwards from the callee (current_func) to its callers.
            # NOTE: This assumes the `assignments` table correctly captures `target_var` for function calls.
            # A more robust solution might require enhancing the `function_call_args` table further.
            assignment_query = build_query(
                'assignments',
                ['target_var', 'in_function', 'file', 'line'],
                where="source_expr LIKE ?"
            )
            cursor.execute(assignment_query, (f"%{current_func}%",))

            for target_var, caller_func, caller_file, call_line in cursor.fetchall():
                caller_file = caller_file.replace('\\', '/')
                if debug:
                    print(f"[INTER-PROCEDURAL-S2] Return flow: '{current_var}' from {current_func} is assigned to '{target_var}' in {caller_func} at {caller_file}:{call_line}", file=sys.stderr)
                new_path = path + [{"type": "return_flow", "from_file": current_file, "from_func": current_func, "to_file": caller_file, "to_func": caller_func, "return_var": current_var, "target_var": target_var, "line": call_line}]
                worklist.append((target_var, caller_func, caller_file, depth + 1, new_path))

    return paths


def trace_inter_procedural_flow_cfg(
    analyzer: 'InterProceduralCFGAnalyzer',
    cursor: sqlite3.Cursor,
    source_vars: Set[str],  # CRITICAL FIX: Now accepts SET of variables for unified analysis
    source_file: str,
    source_line: int,
    source_function: str,
    sinks: List[Dict[str, Any]],
    max_depth: int = 5,
    cache: Optional['MemoryCache'] = None,
    origin_source: Optional[Dict[str, Any]] = None
) -> List['TaintPath']:
    """
    Implements a file-aware, multi-hop, CFG-based (flow-sensitive) taint analysis.
    This is the most precise analysis stage, using a worklist to trace taint across
    file boundaries and a CFG analyzer to verify path feasibility.

    CRITICAL FIX: Now accepts source_vars as a SET to enable unified multi-hop analysis.
    Previous bug: Called separately for each var, resetting worklist each time.
    """
    from .core import TaintPath

    if origin_source:
        source_info = {
            "file": origin_source.get("file", source_file),
            "line": origin_source.get("line", source_line),
            "pattern": origin_source.get("pattern", next(iter(source_vars), "unknown_source")),
            "name": origin_source.get("name", origin_source.get("pattern", next(iter(source_vars), "unknown_source")))
        }
    else:
        default_pattern = next(iter(source_vars), "unknown_source")
        source_info = {
            "file": source_file,
            "line": source_line,
            "pattern": default_pattern,
            "name": default_pattern
        }

    paths: List[TaintPath] = []
    debug = os.environ.get("THEAUDITOR_TAINT_DEBUG") or os.environ.get("THEAUDITOR_CFG_DEBUG")

    if debug:
        print(f"[INTER-CFG-S3] Starting Stage 3 unified analysis", file=sys.stderr)
        print(f"  Source vars {list(source_vars)} in {source_function} at {source_file}:{source_line}", file=sys.stderr)

    generic_param_regex = re.compile(r"^arg\d*$", re.IGNORECASE)

    def _is_generic_param(name: Optional[str]) -> bool:
        if not name:
            return True
        lowered = name.lower()
        return (
            lowered in {"req", "res", "next", "callback", "cb", "_"}
            or generic_param_regex.match(lowered) is not None
        )

    def _extract_simple_identifier(expr: Optional[str]) -> Optional[str]:
        if not expr:
            return None
        candidate = expr.strip()
        if candidate.endswith("!"):
            candidate = candidate[:-1]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", candidate):
            return candidate
        return None

    # Worklist stores the state:
    # (current_file, current_function, tainted_vars_set, depth, call_path)
    # CRITICAL FIX: Initialize with ENTIRE SET of source variables for unified analysis
    worklist: List[tuple[str, str, frozenset, int, list]] = [(source_file, source_function, frozenset(source_vars), 0, [])]

    # visited prevents cycles by tracking (file, function, tainted_vars).
    visited: Set[tuple[str, str, frozenset]] = set()

    while worklist:
        current_file, current_func, tainted_vars, depth, call_path = worklist.pop(0)

        if depth > max_depth:
            continue

        raw_file = current_file
        raw_func_name = current_func

        callback_override = None
        for entry in reversed(call_path):
            if entry.get("type") == "cfg_callback" and entry.get("callback_func") == raw_func_name:
                callback_override = entry
                break

        if callback_override:
            current_file = callback_override.get("from_file", current_file)
            current_func = callback_override.get("from_func", current_func)

        original_func_name = current_func
        normalized_file = current_file.replace("\\", "/")
        canonical_current_func, resolved_file_hint = resolve_function_identity(cursor, original_func_name, normalized_file)
        current_func = canonical_current_func or original_func_name
        current_file = (resolved_file_hint or normalized_file).replace("\\", "/")

        state_key = (current_file, current_func, tainted_vars)
        if state_key in visited:
            continue
        visited.add(state_key)

        if debug:
            print(f"[INTER-CFG-S3] Depth {depth}: Analyzing {current_func} ({current_file}) with tainted vars {list(tainted_vars)}", file=sys.stderr)

        lookup_names = [name for name in {current_func, original_func_name} if name]
        func_start_line = None
        func_end_line = None
        for name in lookup_names:
            bounds_query = build_query(
                'symbols',
                ['line', 'end_line'],
                where="path = ? AND type = 'function' AND name = ?",
                limit=1
            )
            cursor.execute(bounds_query, (current_file, name))
            row = cursor.fetchone()
            if row:
                func_start_line = row[0]
                func_end_line = row[1] or (row[0] + 200)
                break
        if func_start_line is None or func_end_line is None:
            func_start_line = 0
            func_end_line = 10**9

        # 1. Check for sinks in the current context using PathAnalyzer for intra-procedural flow.
        from .cfg_integration import PathAnalyzer

        for sink in sinks:
            # Ensure sink is in current file first
            if sink["file"] != current_file:
                continue

            sink_function = get_containing_function(cursor, sink)
            if sink_function:
                # CRITICAL FIX: Normalize both sides for comparison
                # Both sink_function["name"] and current_func may have prefixes (e.g., "service.method")
                # Must normalize BOTH the same way: split on '.', take last part, lowercase
                sink_func_normalized = sink_function["name"].split('.')[-1].lower()
                current_func_normalized = current_func.split('.')[-1].lower()

                if sink_func_normalized == current_func_normalized:
                    # SURGICAL FIX: Use PathAnalyzer to trace propagation within function
                    # This handles cases where tainted vars are renamed (e.g., data → newUser)
                    try:
                        path_analyzer = PathAnalyzer(cursor, current_file, current_func)

                        # Check each tainted var for paths to sink
                        for tainted_var in tainted_vars:
                            vulnerable_paths_info = path_analyzer.find_vulnerable_paths(
                                source_line=func_start_line,
                                sink_line=sink["line"],
                                initial_tainted_var=tainted_var
                            )

                            if vulnerable_paths_info:
                                if debug:
                                    print(f"[INTER-CFG-S3] VULNERABILITY FOUND: '{tainted_var}' reaches sink '{sink['pattern']}' via intra-procedural flow", file=sys.stderr)

                                vuln_path = call_path + [
                                    {"type": "intra_procedural_flow", "func": current_func, "var": tainted_var},
                                    {"type": "sink_reached", "func": current_func, "var": tainted_var, "sink": sink["pattern"], "line": sink["line"]}
                                ]

                                path_obj = TaintPath(source=source_info.copy(), sink=sink, path=vuln_path)
                                path_obj.flow_sensitive = True
                                paths.append(path_obj)
                                break  # Found path for this sink, stop checking other vars
                    except Exception as e:
                        if debug:
                            print(f"[INTER-CFG-S3] PathAnalyzer failed: {e}", file=sys.stderr)
                        raise

        # 2. Propagate taint to other functions using CFG-based analysis.
        # Use the InterProceduralCFGAnalyzer to understand how callees modify data.

        # CRITICAL FIX: get_containing_function now returns NORMALIZED names (from cfg_blocks).
        # But function_call_args.caller_function has BOTH normalized and fully-qualified names.
        # Single query with OR handles both cases (NOT a forbidden fallback - one query, two conditions)
        query = build_query(
            'function_call_args',
            ['callee_function', 'param_name', 'argument_expr', 'line', 'callee_file_path'],
            where="file = ? AND line >= ? AND line <= ?"
        )
        cursor.execute(query, (current_file, func_start_line, func_end_line))
        call_args_data = cursor.fetchall()

        # CRITICAL FIX (BUG #11): Group function_call_args by call site BEFORE building args_mapping
        # Original bug: Loop processed each parameter row individually, resetting args_mapping each time
        # This prevented accumulating the full mapping for multi-parameter calls
        # Example: accountService.createAccount(req.body, 'system') returns 2 rows (one per param)
        #   - Row 1: param_name="data", arg_expr="req.body" -> args_mapping = {'req.body': 'data'} (good!)
        #   - Row 2: param_name="_createdBy", arg_expr="'system'" -> args_mapping = {} (RECREATED!) -> skip
        # Fix: Group by (call_line, callee_func, callee_file_path) so all params processed together
        calls_by_site = defaultdict(lambda: {"params": [], "callee_file_path": None, "callee_func": None})
        for callee_func, param_name, arg_expr, call_line, callee_file_path in call_args_data:
            if not callee_file_path:  # Skip unresolved calls early
                continue
            site_key = (call_line, callee_func)
            calls_by_site[site_key]["params"].append({"name": param_name, "expr": arg_expr})
            calls_by_site[site_key]["callee_file_path"] = callee_file_path
            calls_by_site[site_key]["callee_func"] = callee_func

        if debug and calls_by_site:
            print(f"[INTER-CFG-S3] Found {len(calls_by_site)} distinct call sites in {current_func}", file=sys.stderr)

        # Track new tainted vars from return values in current scope
        new_tainted_in_current_scope = set()

        # NOW loop through the grouped calls (one iteration per CALL, not per parameter)
        for (call_line, callee_func_key), call_info in calls_by_site.items():
            callee_func = call_info["callee_func"]
            params = call_info["params"]
            callee_file_path = call_info["callee_file_path"]

            # Build args_mapping for the ENTIRE call (all parameters processed together)
            args_mapping: Dict[str, str] = {}
            alias_params: Set[str] = set()
            for param_info in params:
                param_name = (param_info["name"] or "").strip()
                arg_expr = param_info["expr"] or ""

                # Identify tainted vars that flow into this argument
                relevant_tainted = [tv for tv in tainted_vars if tv and tv in arg_expr]
                if not relevant_tainted:
                    simple_identifier = _extract_simple_identifier(arg_expr)
                    if simple_identifier:
                        # Attempt to resolve alias via assignments within current function scope
                        for lookup_name in lookup_names:
                            alias_query = build_query(
                                'assignments',
                                ['source_expr'],
                                where="file = ? AND in_function = ? AND target_var = ?",
                                limit=5
                            )
                            cursor.execute(alias_query, (current_file, lookup_name, simple_identifier))
                            alias_rows = cursor.fetchall()
                            alias_sources = [row[0] for row in alias_rows if row and row[0]]
                            if any(tv and any(tv in source for source in alias_sources) for tv in tainted_vars):
                                relevant_tainted = [
                                    tv for tv in tainted_vars
                                    if any(tv in source for source in alias_sources)
                                ]
                                break
                    if not relevant_tainted:
                        continue

                simple_identifier = _extract_simple_identifier(arg_expr)
                if simple_identifier:
                    alias_params.add(simple_identifier)

                for tainted_var in relevant_tainted:
                    mapped_name = param_name or simple_identifier or tainted_var

                    if simple_identifier and _is_generic_param(param_name):
                        mapped_name = simple_identifier

                    args_mapping[tainted_var] = mapped_name
                    alias_params.add(mapped_name)
                    if debug:
                        print(f"[INTER-CFG-S3]   Mapping: {tainted_var} -> {mapped_name} via '{arg_expr[:50]}'", file=sys.stderr)

            # If NO tainted variables map to any parameters for this specific call, skip it
            if not args_mapping:
                # Attempt to traverse into inline callbacks (e.g., runWithTenant_arg1) that capture tainted vars
                callback_query = build_query(
                    'cfg_blocks',
                    ['function_name'],
                    where="file = ? AND start_line = ?"
                )
                cursor.execute(callback_query, (current_file, call_line))
                callback_functions = [
                    row[0] for row in cursor.fetchall()
                    if row and row[0] and row[0] != canonical_current_func and row[0] != current_func and row[0] != raw_func_name
                ]

                if callback_functions and debug:
                    print(f"[INTER-CFG-S3]   No direct taint mapping; traversing captured callbacks at line {call_line}: {callback_functions}", file=sys.stderr)

                for cb_name in callback_functions:
                    callback_taints = set(tainted_vars)
                    cb_start = call_line
                    cb_end = call_line
                    vars_used_in_callback: Set[str] = set()
                    seeded_aliases: Set[str] = set()

                    bounds = None
                    scoped_bounds_query = build_query(
                        'cfg_blocks',
                        ['start_line', 'end_line'],
                        where="file = ? AND function_name = ? AND start_line = ?",
                        limit=1
                    )
                    cursor.execute(scoped_bounds_query, (current_file, cb_name, call_line))
                    bounds = cursor.fetchone()
                    if not bounds:
                        fallback_bounds_query = build_query(
                            'cfg_blocks',
                            ['start_line', 'end_line'],
                            where="file = ? AND function_name = ?",
                            order_by="(end_line - start_line) ASC",
                            limit=1
                        )
                        cursor.execute(fallback_bounds_query, (current_file, cb_name))
                        bounds = cursor.fetchone()
                    if bounds:
                        cb_start = bounds[0] or cb_start
                        cb_end = bounds[1] or cb_start
                        if cb_end < cb_start:
                            cb_end = cb_start

                        usage_query = build_query(
                            'variable_usage',
                            ['variable_name'],
                            where="file = ? AND line >= ? AND line <= ?"
                        )
                        cursor.execute(usage_query, (current_file, cb_start, cb_end))
                        vars_used_in_callback = {
                            row[0] for row in cursor.fetchall() if row and row[0]
                        }

                        # Query assignments with normalized junction table (NO JSON PARSING)
                        cursor.execute("""
                            SELECT DISTINCT a.target_var, asrc.source_var_name
                            FROM assignments a
                            LEFT JOIN assignment_sources asrc
                                ON a.file = asrc.assignment_file
                                AND a.line = asrc.assignment_line
                                AND a.target_var = asrc.assignment_target
                            WHERE a.file = ? AND a.line >= ? AND a.line <= ?
                        """, (current_file, cb_start, cb_end))

                        known_taints = set(tainted_vars)
                        for target_var, source_var in cursor.fetchall():
                            if not target_var:
                                continue
                            if not source_var:  # Assignment with no source vars (LEFT JOIN null)
                                continue
                            base_name = source_var.split('.', 1)[0]
                            if source_var in known_taints or base_name in known_taints:
                                seeded_aliases.add(target_var)
                                known_taints.add(target_var)

                    captured_taint: Set[str] = set()
                    if vars_used_in_callback:
                        for outer_var in tainted_vars:
                            base_outer = outer_var.split('.', 1)[0]
                            if outer_var in vars_used_in_callback or base_outer in vars_used_in_callback:
                                captured_taint.add(outer_var)
                        if debug and captured_taint:
                            print(f"[INTER-CFG-S3]   Callback {cb_name} captured tainted vars: {sorted(captured_taint)}", file=sys.stderr)

                    final_callback_taint = set(callback_taints)
                    if captured_taint:
                        final_callback_taint.update(captured_taint)
                    if bounds:
                        final_callback_taint.update(seeded_aliases)

                    callback_path = call_path + [
                        {
                            "type": "cfg_callback",
                            "from_file": current_file,
                            "from_func": current_func,
                            "callback_func": cb_name,
                            "line": call_line,
                            "captured_vars": sorted(captured_taint),
                            "seeded_aliases": sorted(seeded_aliases),
                            "taint_state": sorted(final_callback_taint)
                        }
                    ]
                    callback_state = frozenset(final_callback_taint)
                    if debug and final_callback_taint != set(tainted_vars):
                        delta = sorted(final_callback_taint - set(tainted_vars))
                        if delta:
                            print(f"[INTER-CFG-S3]   Seeding callback '{cb_name}' with {delta}", file=sys.stderr)

                    worklist.append((current_file, cb_name, callback_state, depth + 1, callback_path))

                if debug:
                    print(f"[INTER-CFG-S3]   No relevant taint mapping for call to {callee_func} at line {call_line}, skipping traversal", file=sys.stderr)
                continue

            callee_file = callee_file_path.replace('\\', '/')

            canonical_callee, resolved_callee_file = resolve_function_identity(
                cursor,
                callee_func,
                callee_file
            )
            effective_callee = canonical_callee or callee_func
            if resolved_callee_file:
                callee_file = resolved_callee_file.replace("\\", "/")

            # Build taint_state: var -> is_tainted
            taint_state = {var: True for var in tainted_vars}

            # CALL THE ANALYZER to understand how the callee affects taint
            effect = analyzer.analyze_function_call(
                caller_file=current_file,
                caller_func=current_func,
                callee_file=callee_file,
                callee_func=effective_callee,
                args_mapping=args_mapping,
                taint_state=taint_state
            )

            # CRITICAL FIX: Traverse INTO callee with ENTRY taint state, not EXIT state
            # args_mapping.values() = callee parameters that receive tainted caller values
            # This is what we need to START analysis in the callee, not effect.param_effects (exit state)
            propagated_params = set(args_mapping.values())
            propagated_params.update(alias_params)

            if propagated_params:
                new_path = call_path + [{"type": "cfg_call", "from_file": current_file, "from_func": current_func, "to_file": callee_file, "to_func": effective_callee, "line": call_line, "params": list(propagated_params)}]

                # THIS IS THE LINE THAT ENABLES MULTI-HOP TRAVERSAL
                worklist.append((callee_file, effective_callee, frozenset(propagated_params), depth + 1, new_path))

                if debug:
                    print(f"[INTER-CFG-S3] TRAVERSING INTO CALLEE: {effective_callee} ({callee_file}) with tainted params {list(propagated_params)}", file=sys.stderr)
            elif debug:
                print(f"[INTER-CFG-S3] No tainted params to propagate to {callee_func}", file=sys.stderr)

            # CRITICAL FIX: Use effect.return_tainted (don't discard CFG results!)
            if effect.return_tainted:
                # Find the assignment that captures this call's return value
                # Handle both normalized and fully-qualified function names in assignments.in_function
                in_conditions: List[str] = []
                in_params: List[str] = []
                for name in {current_func, original_func_name}:
                    if not name:
                        continue
                    in_conditions.append("in_function = ?")
                    in_params.append(name)
                    in_conditions.append("in_function LIKE ?")
                    in_params.append(f"%.{name}")
                if not in_conditions:
                    in_conditions.append("1=0")

                where_clause = "file = ? AND line = ? AND source_expr LIKE ? AND (" + " OR ".join(in_conditions) + ")"
                assignment_query = build_query(
                    'assignments',
                    ['target_var'],
                    where=where_clause
                )
                params: List[Any] = [current_file, call_line, f"%{callee_func}%"] + in_params
                cursor.execute(assignment_query, params)

                result = cursor.fetchone()
                if result:
                    target_var = result[0]
                    new_tainted_in_current_scope.add(target_var)
                    if debug:
                        print(f"[INTER-CFG-S3] Return tainted: {callee_func} taints '{target_var}' at {current_file}:{call_line}", file=sys.stderr)

        # If we found new tainted vars from return values, re-add current context with expanded tainted set
        # This ensures we check for sinks with the new tainted vars
        if new_tainted_in_current_scope:
            expanded_tainted = tainted_vars | new_tainted_in_current_scope
            # Check if this expanded state was already visited to prevent infinite loops
            new_state_key = (current_file, current_func, frozenset(expanded_tainted))
            if new_state_key not in visited:
                worklist.append((current_file, current_func, frozenset(expanded_tainted), depth, call_path))
                if debug:
                    print(f"[INTER-CFG-S3] Re-adding current context with expanded tainted set: {list(expanded_tainted)}", file=sys.stderr)
            elif debug:
                print(f"[INTER-CFG-S3] Expanded state already visited, skipping re-add", file=sys.stderr)

    return paths
