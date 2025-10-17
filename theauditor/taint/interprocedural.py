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

import os
import sys
import sqlite3
from typing import Dict, List, Any, Optional, Set, TYPE_CHECKING

from theauditor.indexer.schema import build_query
from .database import get_containing_function, get_code_snippet

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
    cache: Optional['MemoryCache'] = None
) -> List['TaintPath']:
    """
    Implements a file-aware, multi-hop, flow-insensitive taint tracking algorithm.
    This version correctly follows taint across file boundaries via function calls
    and return values.
    """
    from .core import TaintPath

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
            # The worklist is file-aware, so we only check sinks in the current file context.
            if sink["file"] != current_file:
                continue

            sink_function = get_containing_function(cursor, sink)
            if sink_function and sink_function["name"] == current_func:
                # The sink is in the current function. Check if our tainted var reaches it.
                query = build_query('function_call_args', ['argument_expr'],
                                    where="file = ? AND line = ? AND argument_expr LIKE ?", limit=1)
                cursor.execute(query, (current_file, sink["line"], f"%{current_var}%"))
                if cursor.fetchone():
                    if debug:
                        print(f"[INTER-PROCEDURAL-S2] VULNERABILITY FOUND: '{current_var}' reaches sink '{sink['pattern']}'", file=sys.stderr)
                    vuln_path = path + [{"type": "sink_reached", "func": current_func, "var": current_var, "sink": sink["pattern"], "line": sink["line"]}]
                    paths.append(TaintPath(source={"file": source_file, "line": source_line, "pattern": source_var, "name": source_var}, sink=sink, path=vuln_path))

        # 2. Propagate taint to other functions (cross-file).
        # Find all function calls within the current function that use the tainted variable as an argument.
        query = build_query(
            'function_call_args',
            ['callee_function', 'param_name', 'line', 'callee_file_path'],  # CRITICAL: Query the resolved callee path
            where="file = ? AND caller_function = ? AND (argument_expr = ? OR argument_expr LIKE ?)"
        )
        cursor.execute(query, (current_file, current_func, current_var, f"%{current_var}%"))

        for callee_func, param_name, call_line, callee_file_path in cursor.fetchall():
            if not callee_file_path:
                if debug:
                    print(f"[INTER-PROCEDURAL-S2] WARNING: Could not resolve file for call to '{callee_func}' at {current_file}:{call_line}. Skipping.", file=sys.stderr)
                continue  # Skip calls we cannot resolve to a file.

            callee_file = callee_file_path.replace('\\', '/')
            if debug and callee_file != current_file:
                print(f"[INTER-PROCEDURAL-S2] Cross-file call: {current_file} -> {callee_file} ({current_func} -> {callee_func})", file=sys.stderr)

            new_path = path + [{"type": "argument_pass", "from_file": current_file, "from_func": current_func, "to_file": callee_file, "to_func": callee_func, "var": current_var, "param": param_name, "line": call_line}]
            worklist.append((param_name, callee_func, callee_file, depth + 1, new_path))

        # 3. Propagate taint through return values.
        # Find if the current tainted variable is returned by the current function.
        query = build_query(
            'function_returns',
            ['return_expr', 'line'],
            where="file = ? AND function_name = ? AND (return_expr = ? OR return_expr LIKE ? OR return_vars LIKE ?)"
        )
        cursor.execute(query, (current_file, current_func, current_var, f"%{current_var}%", f'%"{current_var}"%'))

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
    source_var: str,
    source_file: str,
    source_line: int,
    source_function: str,
    sinks: List[Dict[str, Any]],
    max_depth: int = 5,
    cache: Optional['MemoryCache'] = None
) -> List['TaintPath']:
    """
    Implements a file-aware, multi-hop, CFG-based (flow-sensitive) taint analysis.
    This is the most precise analysis stage, using a worklist to trace taint across
    file boundaries and a CFG analyzer to verify path feasibility.
    """
    from .core import TaintPath

    paths: List[TaintPath] = []
    debug = os.environ.get("THEAUDITOR_TAINT_DEBUG") or os.environ.get("THEAUDITOR_CFG_DEBUG")

    if debug:
        print(f"[INTER-CFG-S3] Starting Stage 3 analysis", file=sys.stderr)
        print(f"  Source '{source_var}' in {source_function} at {source_file}:{source_line}", file=sys.stderr)

    # Worklist stores the state:
    # (current_file, current_function, tainted_vars_set, depth, call_path)
    worklist: List[tuple[str, str, frozenset, int, list]] = [(source_file, source_function, frozenset([source_var]), 0, [])]

    # visited prevents cycles by tracking (file, function, tainted_vars).
    visited: Set[tuple[str, str, frozenset]] = set()

    while worklist:
        current_file, current_func, tainted_vars, depth, call_path = worklist.pop(0)

        if depth > max_depth:
            continue

        state_key = (current_file, current_func, tainted_vars)
        if state_key in visited:
            continue
        visited.add(state_key)

        if debug:
            print(f"[INTER-CFG-S3] Depth {depth}: Analyzing {current_func} ({current_file}) with tainted vars {list(tainted_vars)}", file=sys.stderr)

        # 1. Check for sinks in the current context.
        for sink in sinks:
            if sink["file"] != current_file:
                continue

            sink_function = get_containing_function(cursor, sink)
            if sink_function and sink_function["name"] == current_func:
                for tainted_var in tainted_vars:
                    query = build_query('function_call_args', ['argument_expr'],
                                        where="file = ? AND line = ? AND argument_expr LIKE ?", limit=1)
                    cursor.execute(query, (current_file, sink["line"], f"%{tainted_var}%"))
                    if cursor.fetchone():
                        if debug:
                            print(f"[INTER-CFG-S3] VULNERABILITY FOUND: '{tainted_var}' reaches sink '{sink['pattern']}'", file=sys.stderr)
                        vuln_path = call_path + [{"type": "sink_reached", "func": current_func, "var": tainted_var, "sink": sink["pattern"], "line": sink["line"]}]
                        paths.append(TaintPath(source={"file": source_file, "line": source_line, "pattern": source_var, "name": source_var}, sink=sink, path=vuln_path))

        # 2. Propagate taint to other functions using CFG-based analysis.
        # Use the InterProceduralCFGAnalyzer to understand how callees modify data.
        query = build_query(
            'function_call_args',
            ['callee_function', 'param_name', 'argument_expr', 'line', 'callee_file_path'],
            where="file = ? AND caller_function = ?"
        )
        cursor.execute(query, (current_file, current_func))

        for callee_func, param_name, arg_expr, call_line, callee_file_path in cursor.fetchall():
            if not callee_file_path:
                continue

            # Build args_mapping: caller_var -> callee_param
            args_mapping = {}
            for tainted_var in tainted_vars:
                if tainted_var in arg_expr:
                    args_mapping[tainted_var] = param_name

            if not args_mapping:
                continue

            callee_file = callee_file_path.replace('\\', '/')

            # Build taint_state: var -> is_tainted
            taint_state = {var: True for var in tainted_vars}

            # CALL THE ANALYZER to understand how the callee affects taint
            effect = analyzer.analyze_function_call(
                caller_file=current_file,
                caller_func=current_func,
                callee_file=callee_file,
                callee_func=callee_func,
                args_mapping=args_mapping,
                taint_state=taint_state
            )

            # Propagate taint based on the effect
            propagated_taint = set()

            # Add tainted parameters
            for param, effect_type in effect.param_effects.items():
                if effect_type == 'tainted':
                    propagated_taint.add(param)

            # Add parameters that passthrough to return (for later return tracking)
            for param, taints_return in effect.passthrough_taint.items():
                if taints_return:
                    propagated_taint.add(param)

            if propagated_taint:
                new_path = call_path + [{"type": "cfg_call", "from_file": current_file, "from_func": current_func, "to_file": callee_file, "to_func": callee_func, "line": call_line, "effect": effect}]
                worklist.append((callee_file, callee_func, frozenset(propagated_taint), depth + 1, new_path))
                if debug:
                    print(f"[INTER-CFG-S3] Adding to worklist: {callee_func} ({callee_file}) with tainted params {list(propagated_taint)}", file=sys.stderr)
                    print(f"  Effect: {effect.param_effects}", file=sys.stderr)

        # 3. Propagate taint through return values using CFG-based analysis.
        # Check if current function returns tainted data and track it back to callers.

        # Find if any of the current tainted variables are returned by the current function.
        for current_var in tainted_vars:
            query = build_query(
                'function_returns',
                ['return_expr', 'line'],
                where="file = ? AND function_name = ? AND (return_expr = ? OR return_expr LIKE ? OR return_vars LIKE ?)"
            )
            cursor.execute(query, (current_file, current_func, current_var, f"%{current_var}%", f'%"{current_var}"%'))

            if not cursor.fetchone():
                continue  # This var is not returned

            # This function returns tainted data. Find callers and track the return value.
            # Query backwards: who calls this function?
            caller_query = build_query(
                'function_call_args',
                ['file', 'caller_function', 'line'],
                where="callee_function = ? AND callee_file_path = ?"
            )
            cursor.execute(caller_query, (current_func, current_file))

            for caller_file_raw, caller_func, call_line in cursor.fetchall():
                caller_file = caller_file_raw.replace('\\', '/')

                # Find the assignment that captures this function's return value
                assignment_query = build_query(
                    'assignments',
                    ['target_var'],
                    where="file = ? AND line = ? AND source_expr LIKE ?"
                )
                cursor.execute(assignment_query, (caller_file, call_line, f"%{current_func}%"))

                result = cursor.fetchone()
                if result:
                    target_var = result[0]
                    if debug:
                        print(f"[INTER-CFG-S3] Return flow: '{current_var}' from {current_func} returned to '{target_var}' in {caller_func} at {caller_file}:{call_line}", file=sys.stderr)
                    new_path = call_path + [{"type": "cfg_return", "from_file": current_file, "from_func": current_func, "to_file": caller_file, "to_func": caller_func, "return_var": current_var, "target_var": target_var, "line": call_line}]
                    worklist.append((caller_file, caller_func, frozenset([target_var]), depth + 1, new_path))

    return paths
