"""
Memory-optimized cache for taint analysis database operations.

This module provides in-memory caching of database tables with multiple
indexes optimized for different access patterns used during taint analysis.

Design Philosophy:
- Trade memory for speed (2024 reality: RAM is cheap, time is not)
- Multiple indexes for different access patterns
- Pre-compute expensive operations
- Graceful fallback on memory constraints
"""

import sys
import json
from collections import defaultdict
from typing import Dict, List, Set, Any, Optional, Tuple
import sqlite3

class MemoryCache:
    """
    Pre-loaded database cache with multiple indexes for O(1) lookups.

    Design Philosophy:
    - Trade memory for speed (2024 reality: RAM is cheap, time is not)
    - Multiple indexes for different access patterns
    - Pre-compute expensive operations
    """

    def __init__(self, cursor: sqlite3.Cursor = None, max_memory_mb: int = 4000):
        """
        Initialize cache with modern defaults.

        Args:
            cursor: SQLite database cursor (optional, for immediate loading)
            max_memory_mb: Memory limit (default 4GB - works on cheapest VPS)
        """
        self.max_memory = max_memory_mb * 1024 * 1024
        self.current_memory = 0

        # Primary storage
        self.symbols = []
        self.assignments = []
        self.function_call_args = []
        self.cfg_blocks = []
        self.cfg_edges = []
        self.function_returns = []

        # NEW: Specialized table storage for multi-table taint analysis (Phase 3.3)
        self.sql_queries = []
        self.orm_queries = []
        self.react_hooks = []
        self.variable_usage = []

        # Multi-index architecture for different query patterns
        # Index 1: By line for proximity queries
        self.symbols_by_line = defaultdict(list)  # (file, line) -> [symbols]

        # Index 2: By name for pattern matching
        self.symbols_by_name = defaultdict(list)  # name -> [symbols]

        # Index 3: By file for file-scoped queries
        self.symbols_by_file = defaultdict(list)  # file -> [symbols]

        # Index 4: By type for type filtering
        self.symbols_by_type = defaultdict(list)  # type -> [symbols]

        # Assignment indexes
        self.assignments_by_func = defaultdict(list)  # (file, func) -> [assigns]
        self.assignments_by_target = defaultdict(list)  # target_var -> [assigns]
        self.assignments_by_file = defaultdict(list)  # file -> [assigns]

        # Function call indexes
        self.calls_by_caller = defaultdict(list)  # (file, caller) -> [calls]
        self.calls_by_callee = defaultdict(list)  # callee -> [calls]
        self.calls_by_file = defaultdict(list)  # file -> [calls]

        # Function returns index
        self.returns_by_function = defaultdict(list)  # (file, func) -> [returns]

        # NEW: Specialized table indexes for multi-table taint analysis (Phase 3.3)
        self.sql_queries_by_type = defaultdict(list)  # query_type -> [queries]
        self.sql_queries_by_file = defaultdict(list)  # file -> [queries]
        self.orm_queries_by_model = defaultdict(list)  # model_name -> [queries]
        self.orm_queries_by_file = defaultdict(list)  # file -> [queries]
        self.react_hooks_by_name = defaultdict(list)  # hook_name -> [hooks]
        self.react_hooks_by_file = defaultdict(list)  # file -> [hooks]
        self.variable_usage_by_name = defaultdict(list)  # var_name -> [usages]
        self.variable_usage_by_file = defaultdict(list)  # file -> [usages]

        # Pre-computed patterns (will be populated during precompute)
        self.precomputed_sources = {}  # pattern -> [matching symbols]
        self.precomputed_sinks = {}    # pattern -> [matching symbols]
        self.call_graph = {}            # func -> [called_funcs]

        # Cache status
        self.is_loaded = False
        self.load_error = None

    def preload(self, cursor: sqlite3.Cursor) -> bool:
        """
        Load entire database into memory with multiple indexes.

        Returns:
            True if successful, False if memory exceeded or error
        """
        try:
            print(f"[MEMORY] Starting database preload...", file=sys.stderr)

            # Check database size before loading
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Estimate memory usage
            estimated_memory = 0
            for table in ['symbols', 'assignments', 'function_call_args', 'cfg_blocks', 'cfg_edges']:
                if table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    # Rough estimate: 200 bytes per row + indexes
                    estimated_memory += count * 300
            
            if estimated_memory > self.max_memory:
                print(f"[MEMORY] Estimated memory {estimated_memory/1024/1024:.1f}MB exceeds limit {self.max_memory/1024/1024:.1f}MB", file=sys.stderr)
                self.load_error = "Memory limit exceeded"
                return False

            # Step 1: Load symbols with multi-indexing
            if 'symbols' in tables:
                cursor.execute("SELECT path, name, type, line, col FROM symbols")
                symbols_data = cursor.fetchall()

                for path, name, sym_type, line, col in symbols_data:
                    # Normalize path separators
                    path = path.replace("\\", "/") if path else ""
                    
                    symbol = {
                        "file": path,
                        "name": name or "",
                        "type": sym_type or "",
                        "line": line or 0,
                        "col": col or 0
                    }

                    # Store in primary list
                    self.symbols.append(symbol)

                    # Build multiple indexes for O(1) access
                    self.symbols_by_line[(path, line)].append(symbol)
                    self.symbols_by_name[name].append(symbol)
                    self.symbols_by_file[path].append(symbol)
                    self.symbols_by_type[sym_type].append(symbol)

                    self.current_memory += sys.getsizeof(symbol) + 200  # Include index overhead

                print(f"[MEMORY] Loaded {len(self.symbols)} symbols", file=sys.stderr)

            # Step 2: Load assignments with function indexing
            if 'assignments' in tables:
                cursor.execute("""
                    SELECT file, line, target_var, source_expr, source_vars, in_function
                    FROM assignments
                """)
                assignments_data = cursor.fetchall()

                for file, line, target, source_expr, source_vars, func in assignments_data:
                    # Normalize path
                    file = file.replace("\\", "/") if file else ""
                    
                    assignment = {
                        "file": file,
                        "line": line or 0,
                        "target_var": target or "",
                        "source_expr": source_expr or "",
                        "source_vars": source_vars or "",
                        "in_function": func or "global"
                    }

                    self.assignments.append(assignment)
                    self.assignments_by_func[(file, func)].append(assignment)
                    self.assignments_by_target[target].append(assignment)
                    self.assignments_by_file[file].append(assignment)

                    self.current_memory += sys.getsizeof(assignment) + 100

                print(f"[MEMORY] Loaded {len(self.assignments)} assignments", file=sys.stderr)

            # Step 3: Load function call arguments
            if 'function_call_args' in tables:
                cursor.execute("""
                    SELECT file, line, caller_function, callee_function,
                           param_name, argument_expr
                    FROM function_call_args
                """)
                call_args_data = cursor.fetchall()

                for file, line, caller, callee, param, arg_expr in call_args_data:
                    # Normalize path
                    file = file.replace("\\", "/") if file else ""
                    
                    call_arg = {
                        "file": file,
                        "line": line or 0,
                        "caller_function": caller or "global",
                        "callee_function": callee or "",
                        "param_name": param or "",
                        "argument_expr": arg_expr or ""
                    }

                    self.function_call_args.append(call_arg)
                    self.calls_by_caller[(file, caller)].append(call_arg)
                    self.calls_by_callee[callee].append(call_arg)
                    self.calls_by_file[file].append(call_arg)

                    self.current_memory += sys.getsizeof(call_arg) + 100

                print(f"[MEMORY] Loaded {len(self.function_call_args)} function call args", file=sys.stderr)

            # Step 4: Load function returns if table exists
            if 'function_returns' in tables:
                cursor.execute("""
                    SELECT file, function_name, return_expr, return_vars, line
                    FROM function_returns
                """)
                returns_data = cursor.fetchall()

                for file, func_name, return_expr, return_vars, line in returns_data:
                    # Normalize path
                    file = file.replace("\\", "/") if file else ""
                    
                    ret = {
                        "file": file,
                        "function_name": func_name or "",
                        "return_expr": return_expr or "",
                        "return_vars": return_vars or "",
                        "line": line or 0
                    }

                    self.function_returns.append(ret)
                    self.returns_by_function[(file, func_name)].append(ret)

                    self.current_memory += sys.getsizeof(ret) + 50

                print(f"[MEMORY] Loaded {len(self.function_returns)} function returns", file=sys.stderr)

            # Step 5: Load specialized tables for multi-table taint analysis (Phase 3.3)
            if 'sql_queries' in tables:
                cursor.execute("""
                    SELECT file, line, query_text, query_type
                    FROM sql_queries
                    WHERE query_text IS NOT NULL
                    AND query_text != ''
                    AND query_type != 'UNKNOWN'
                """)
                sql_queries_data = cursor.fetchall()

                for file, line, query_text, query_type in sql_queries_data:
                    file = file.replace("\\", "/") if file else ""

                    query = {
                        "file": file,
                        "line": line or 0,
                        "query_text": query_text or "",
                        "query_type": query_type or ""
                    }

                    self.sql_queries.append(query)
                    self.sql_queries_by_type[query_type].append(query)
                    self.sql_queries_by_file[file].append(query)
                    self.current_memory += sys.getsizeof(query) + 50

                print(f"[MEMORY] Loaded {len(self.sql_queries)} SQL queries", file=sys.stderr)

            if 'orm_queries' in tables:
                cursor.execute("""
                    SELECT file, line, model_name, operation, framework_specific
                    FROM orm_queries
                    WHERE model_name IS NOT NULL
                """)
                orm_queries_data = cursor.fetchall()

                for file, line, model_name, operation, framework_data in orm_queries_data:
                    file = file.replace("\\", "/") if file else ""

                    query = {
                        "file": file,
                        "line": line or 0,
                        "model_name": model_name or "",
                        "operation": operation or "",
                        "framework_specific": framework_data or ""
                    }

                    self.orm_queries.append(query)
                    self.orm_queries_by_model[model_name].append(query)
                    self.orm_queries_by_file[file].append(query)
                    self.current_memory += sys.getsizeof(query) + 50

                print(f"[MEMORY] Loaded {len(self.orm_queries)} ORM queries", file=sys.stderr)

            if 'react_hooks' in tables:
                cursor.execute("""
                    SELECT file, line, hook_name, dependencies
                    FROM react_hooks
                """)
                react_hooks_data = cursor.fetchall()

                for file, line, hook_name, deps in react_hooks_data:
                    file = file.replace("\\", "/") if file else ""

                    hook = {
                        "file": file,
                        "line": line or 0,
                        "hook_name": hook_name or "",
                        "dependencies": deps or ""
                    }

                    self.react_hooks.append(hook)
                    self.react_hooks_by_name[hook_name].append(hook)
                    self.react_hooks_by_file[file].append(hook)
                    self.current_memory += sys.getsizeof(hook) + 50

                print(f"[MEMORY] Loaded {len(self.react_hooks)} React hooks", file=sys.stderr)

            if 'variable_usage' in tables:
                # Only load if count is reasonable (avoid massive tables)
                cursor.execute("SELECT COUNT(*) FROM variable_usage")
                usage_count = cursor.fetchone()[0]

                if usage_count < 500000:  # 500K limit for variable_usage
                    cursor.execute("""
                        SELECT file, line, var_name, usage_type, context
                        FROM variable_usage
                    """)
                    variable_usage_data = cursor.fetchall()

                    for file, line, var_name, usage_type, context in variable_usage_data:
                        file = file.replace("\\", "/") if file else ""

                        usage = {
                            "file": file,
                            "line": line or 0,
                            "var_name": var_name or "",
                            "usage_type": usage_type or "",
                            "context": context or ""
                        }

                        self.variable_usage.append(usage)
                        self.variable_usage_by_name[var_name].append(usage)
                        self.variable_usage_by_file[file].append(usage)
                        self.current_memory += sys.getsizeof(usage) + 50

                    print(f"[MEMORY] Loaded {len(self.variable_usage)} variable usages", file=sys.stderr)
                else:
                    print(f"[MEMORY] Skipping variable_usage table (too large: {usage_count} rows)", file=sys.stderr)

            # Step 6: Pre-compute call graph (NEW OPTIMIZATION!)
            self._precompute_call_graph()

            # Step 7: Pre-compute common patterns (NEW OPTIMIZATION!)
            self._precompute_patterns()

            print(f"[MEMORY] Total memory used: {self.current_memory / 1024 / 1024:.1f}MB", file=sys.stderr)
            print(f"[MEMORY] Indexes built: 19 primary (11 base + 8 specialized), 3 pre-computed (sources, sinks, call_graph)", file=sys.stderr)

            self.is_loaded = True
            return True

        except MemoryError as e:
            print(f"[MEMORY] MemoryError during preload: {e}", file=sys.stderr)
            self.load_error = "MemoryError"
            return False
        except Exception as e:
            print(f"[MEMORY] Unexpected error during preload: {e}", file=sys.stderr)
            self.load_error = str(e)
            return False

    def _precompute_call_graph(self):
        """Pre-build the entire call graph for instant access."""
        # Group functions by file
        functions_by_file = defaultdict(list)
        for sym in self.symbols_by_type.get("function", []):
            functions_by_file[sym["file"]].append(sym)

        # Build call graph
        for file, functions in functions_by_file.items():
            for func in functions:
                func_key = f"{file}:{func['name']}"

                # Find all calls within this function's scope
                calls_in_func = []
                func_line = func["line"]
                
                # CRITICAL FIX: Use actual function boundaries if available
                func_end_line = func.get("end_line")
                if func_end_line and func_end_line > func_line:
                    # We have accurate boundaries - use them
                    for call in self.symbols_by_type.get("call", []):
                        if call["file"] == file:
                            if func_line <= call["line"] <= func_end_line:
                                calls_in_func.append(call["name"])
                else:
                    # Fallback: Use heuristic for functions without end_line
                    # This happens for older indexed data or languages without boundary support
                    for call in self.symbols_by_type.get("call", []):
                        if call["file"] == file:
                            # Use 200-line heuristic as fallback
                            if func_line <= call["line"] < func_line + 200:
                                calls_in_func.append(call["name"])

                self.call_graph[func_key] = calls_in_func

        print(f"[MEMORY] Pre-computed call graph for {len(self.call_graph)} functions", file=sys.stderr)

    def _precompute_patterns(self):
        """Pre-compute common taint source and sink patterns for TRUE O(1) lookup."""
        from .sources import TAINT_SOURCES, SECURITY_SINKS
        
        # Pre-compute ALL taint source patterns
        for category, patterns in TAINT_SOURCES.items():
            for pattern in patterns:
                matching_symbols = []
                
                # CRITICAL FIX: Pre-compute all possible matches
                if "." in pattern:
                    # Property access pattern - exact match first
                    if pattern in self.symbols_by_name:
                        for sym in self.symbols_by_name[pattern]:
                            if sym["type"] in ['call', 'property', 'symbol']:
                                matching_symbols.append(sym)
                    
                    # Also check substring matches for property patterns
                    for name, symbols in self.symbols_by_name.items():
                        if pattern in name and name != pattern:  # Avoid duplicates
                            for sym in symbols:
                                if sym["type"] in ['call', 'property', 'symbol']:
                                    matching_symbols.append(sym)
                else:
                    # Direct name match - simple O(1) lookup
                    if pattern in self.symbols_by_name:
                        for sym in self.symbols_by_name[pattern]:
                            if sym["type"] in ['call', 'symbol']:
                                matching_symbols.append(sym)
                
                # Store pre-computed results even if empty (to avoid re-searching)
                self.precomputed_sources[pattern] = matching_symbols

        # Pre-compute ALL security sink patterns (Phase 3.3: Multi-table strategy)
        for category, patterns in SECURITY_SINKS.items():
            for pattern in patterns:
                matching_results = []

                # STRATEGY 1: Check specialized tables first (more precise)
                if category == 'sql':
                    # Check SQL queries table
                    for query in self.sql_queries:
                        # Match pattern in query context
                        for call_arg in self.function_call_args:
                            if (call_arg["file"] == query["file"] and
                                call_arg["line"] == query["line"]):
                                callee = call_arg["callee_function"]
                                if pattern in callee or callee in pattern:
                                    matching_results.append({
                                        "file": query["file"],
                                        "name": callee,
                                        "line": query["line"],
                                        "column": 0,
                                        "pattern": pattern,
                                        "category": category,
                                        "type": "sink",
                                        "metadata": {
                                            "query_text": query["query_text"][:200],
                                            "query_type": query["query_type"],
                                            "table": "sql_queries"
                                        }
                                    })

                    # Check ORM queries table
                    for query in self.orm_queries:
                        if pattern in query["operation"]:
                            matching_results.append({
                                "file": query["file"],
                                "name": f"{query['model_name']}.{query['operation']}",
                                "line": query["line"],
                                "column": 0,
                                "pattern": pattern,
                                "category": category,
                                "type": "sink",
                                "metadata": {
                                    "model": query["model_name"],
                                    "operation": query["operation"],
                                    "table": "orm_queries"
                                }
                            })

                elif category == 'xss':
                    # Check React hooks for dangerouslySetInnerHTML
                    if pattern == 'dangerouslySetInnerHTML':
                        for hook in self.react_hooks:
                            if 'dangerouslySetInnerHTML' in hook.get("hook_name", "") or \
                               'dangerouslySetInnerHTML' in hook.get("dependencies", ""):
                                matching_results.append({
                                    "file": hook["file"],
                                    "name": "dangerouslySetInnerHTML",
                                    "line": hook["line"],
                                    "column": 0,
                                    "pattern": pattern,
                                    "category": category,
                                    "type": "sink",
                                    "metadata": {
                                        "hook": hook["hook_name"],
                                        "dependencies": hook["dependencies"],
                                        "table": "react_hooks"
                                    }
                                })

                    # Check function_call_args for XSS sinks (res.send, res.render, etc.)
                    for call_arg in self.function_call_args:
                        callee = call_arg["callee_function"]
                        if pattern in callee or callee.endswith(f".{pattern}"):
                            matching_results.append({
                                "file": call_arg["file"],
                                "name": callee,
                                "line": call_arg["line"],
                                "column": 0,
                                "pattern": pattern,
                                "category": category,
                                "type": "sink",
                                "metadata": {
                                    "arguments": call_arg["argument_expr"][:200],
                                    "table": "function_call_args"
                                }
                            })

                elif category in ['command', 'path']:
                    # Check function_call_args for command/path sinks
                    for call_arg in self.function_call_args:
                        callee = call_arg["callee_function"]
                        if pattern in callee or callee.endswith(f".{pattern}"):
                            matching_results.append({
                                "file": call_arg["file"],
                                "name": callee,
                                "line": call_arg["line"],
                                "column": 0,
                                "pattern": pattern,
                                "category": category,
                                "type": "sink",
                                "metadata": {
                                    "arguments": call_arg["argument_expr"][:200],
                                    "table": "function_call_args"
                                }
                            })

                # STRATEGY 2: Fallback to symbols table (catches remaining sinks)
                # Handle chained method patterns specially
                if '().' in pattern:
                    # Complex chained pattern - decompose and find matches
                    parts = pattern.replace('().', '.').split('.')
                    final_method = parts[-1]

                    # Find all calls to the final method
                    if final_method in self.symbols_by_name:
                        for sym in self.symbols_by_name[final_method]:
                            if sym["type"] == 'call':
                                # Avoid duplicates
                                if not any(r["file"] == sym["file"] and r["line"] == sym["line"]
                                          for r in matching_results):
                                    matching_results.append({
                                        "file": sym["file"],
                                        "name": sym["name"],
                                        "line": sym["line"],
                                        "column": sym["col"],
                                        "pattern": pattern,
                                        "category": category,
                                        "type": "sink",
                                        "metadata": {"table": "symbols"}
                                    })

                    # Also check for qualified names
                    for name, symbols in self.symbols_by_name.items():
                        if name.endswith(f".{final_method}"):
                            for sym in symbols:
                                if sym["type"] == 'call':
                                    if not any(r["file"] == sym["file"] and r["line"] == sym["line"]
                                              for r in matching_results):
                                        matching_results.append({
                                            "file": sym["file"],
                                            "name": sym["name"],
                                            "line": sym["line"],
                                            "column": sym["col"],
                                            "pattern": pattern,
                                            "category": category,
                                            "type": "sink",
                                            "metadata": {"table": "symbols"}
                                        })
                else:
                    # Simple pattern - direct O(1) lookup first
                    if pattern in self.symbols_by_name:
                        for sym in self.symbols_by_name[pattern]:
                            if sym["type"] == 'call':
                                if not any(r["file"] == sym["file"] and r["line"] == sym["line"]
                                          for r in matching_results):
                                    matching_results.append({
                                        "file": sym["file"],
                                        "name": sym["name"],
                                        "line": sym["line"],
                                        "column": sym["col"],
                                        "pattern": pattern,
                                        "category": category,
                                        "type": "sink",
                                        "metadata": {"table": "symbols"}
                                    })

                    # Also check for method calls like obj.method
                    for name, symbols in self.symbols_by_name.items():
                        if name.endswith(f".{pattern}") and name != pattern:
                            for sym in symbols:
                                if sym["type"] == 'call':
                                    if not any(r["file"] == sym["file"] and r["line"] == sym["line"]
                                              for r in matching_results):
                                        matching_results.append({
                                            "file": sym["file"],
                                            "name": sym["name"],
                                            "line": sym["line"],
                                            "column": sym["col"],
                                            "pattern": pattern,
                                            "category": category,
                                            "type": "sink",
                                            "metadata": {"table": "symbols"}
                                        })

                # Store pre-computed results even if empty
                self.precomputed_sinks[pattern] = matching_results

        print(f"[MEMORY] Pre-computed {len(self.precomputed_sources)} source patterns", file=sys.stderr)
        print(f"[MEMORY] Pre-computed {len(self.precomputed_sinks)} sink patterns (multi-table)", file=sys.stderr)

    def find_taint_sources_cached(self, sources_dict: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """
        Find all occurrences of taint sources using cache.
        
        Returns same format as database.find_taint_sources for compatibility.
        """
        from .sources import TAINT_SOURCES
        
        sources = []
        sources_to_use = sources_dict if sources_dict is not None else TAINT_SOURCES
        
        # Combine all source patterns
        all_sources = []
        for source_list in sources_to_use.values():
            all_sources.extend(source_list)
        
        for source_pattern in all_sources:
            # Check pre-computed patterns first
            if source_pattern in self.precomputed_sources:
                # O(1) lookup!
                for sym in self.precomputed_sources[source_pattern]:
                    sources.append({
                        "file": sym["file"],
                        "name": sym["name"],
                        "line": sym["line"],
                        "column": sym["col"],
                        "pattern": source_pattern,
                        "type": "source"
                    })
            else:
                # Pattern not pre-computed - use optimized lookups
                if "." in source_pattern:
                    # Property access pattern - check exact match first for O(1)
                    if source_pattern in self.symbols_by_name:
                        # FAST: O(1) exact match
                        for sym in self.symbols_by_name[source_pattern]:
                            if sym["type"] in ['call', 'property', 'symbol']:
                                sources.append({
                                    "file": sym["file"],
                                    "name": sym["name"],
                                    "line": sym["line"],
                                    "column": sym["col"],
                                    "pattern": source_pattern,
                                    "type": "source"
                                })
                    else:
                        # Substring match required - optimize by filtering candidates
                        # This is inherently O(N) but we minimize N
                        base_obj = source_pattern.split('.')[0]
                        for name, symbols in self.symbols_by_name.items():
                            # Only check names starting with base object
                            if name.startswith(base_obj) and source_pattern in name:
                                for sym in symbols:
                                    if sym["type"] in ['call', 'property', 'symbol']:
                                        sources.append({
                                            "file": sym["file"],
                                            "name": sym["name"],
                                            "line": sym["line"],
                                            "column": sym["col"],
                                            "pattern": source_pattern,
                                            "type": "source"
                                        })
                else:
                    # Direct name match - TRUE O(1) lookup
                    if source_pattern in self.symbols_by_name:
                        for sym in self.symbols_by_name[source_pattern]:
                            if sym["type"] in ['call', 'symbol']:
                                sources.append({
                                    "file": sym["file"],
                                    "name": sym["name"],
                                    "line": sym["line"],
                                    "column": sym["col"],
                                    "pattern": source_pattern,
                                    "type": "source"
                                })
        
        return sources

    def find_security_sinks_cached(self, sinks_dict: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """
        Find all occurrences of security sinks using cache.

        Phase 3.3: Returns pre-computed multi-table results with rich metadata.
        All sinks are pre-computed during cache load for TRUE O(1) lookup.

        Returns same format as database.find_security_sinks for compatibility.
        """
        from .sources import SECURITY_SINKS

        sinks = []
        sinks_to_use = sinks_dict if sinks_dict is not None else SECURITY_SINKS

        # Combine all sink patterns
        all_sinks = []
        for sink_list in sinks_to_use.values():
            all_sinks.extend(sink_list)

        for sink_pattern in all_sinks:
            # All patterns should be pre-computed during cache load
            if sink_pattern in self.precomputed_sinks:
                # TRUE O(1) lookup - just return pre-computed results
                sinks.extend(self.precomputed_sinks[sink_pattern])
            else:
                # This should never happen if _precompute_patterns() worked correctly
                print(f"[MEMORY] WARNING: Pattern not pre-computed: {sink_pattern}", file=sys.stderr)

        return sinks

    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        return self.current_memory / 1024 / 1024

    def clear(self):
        """Clear all cached data to free memory."""
        self.symbols.clear()
        self.assignments.clear()
        self.function_call_args.clear()
        self.cfg_blocks.clear()
        self.cfg_edges.clear()
        self.function_returns.clear()

        # Clear specialized tables (Phase 3.3)
        self.sql_queries.clear()
        self.orm_queries.clear()
        self.react_hooks.clear()
        self.variable_usage.clear()

        self.symbols_by_line.clear()
        self.symbols_by_name.clear()
        self.symbols_by_file.clear()
        self.symbols_by_type.clear()

        self.assignments_by_func.clear()
        self.assignments_by_target.clear()
        self.assignments_by_file.clear()

        self.calls_by_caller.clear()
        self.calls_by_callee.clear()
        self.calls_by_file.clear()

        self.returns_by_function.clear()

        # Clear specialized table indexes (Phase 3.3)
        self.sql_queries_by_type.clear()
        self.sql_queries_by_file.clear()
        self.orm_queries_by_model.clear()
        self.orm_queries_by_file.clear()
        self.react_hooks_by_name.clear()
        self.react_hooks_by_file.clear()
        self.variable_usage_by_name.clear()
        self.variable_usage_by_file.clear()

        self.precomputed_sources.clear()
        self.precomputed_sinks.clear()
        self.call_graph.clear()

        self.current_memory = 0
        self.is_loaded = False

        print("[MEMORY] Cache cleared", file=sys.stderr)


def attempt_cache_preload(cursor: sqlite3.Cursor, memory_limit_mb: int = 4000) -> Optional[MemoryCache]:
    """
    Attempt to preload database into memory cache with graceful fallback.
    
    Args:
        cursor: Database cursor
        memory_limit_mb: Memory limit in MB (default 4GB)
        
    Returns:
        MemoryCache if successful, None if failed or exceeded memory
    """
    try:
        # Check database size first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Estimate size
        estimated_size = 0
        for table in ['symbols', 'assignments', 'function_call_args']:
            if table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                # Rough estimate: 300 bytes per row including indexes
                estimated_size += count * 300
        
        estimated_mb = estimated_size / 1024 / 1024
        
        if estimated_mb > memory_limit_mb * 0.8:  # 80% safety margin
            print(f"[MEMORY] Database estimated at {estimated_mb:.1f}MB exceeds 80% of {memory_limit_mb}MB limit", file=sys.stderr)
            print("[MEMORY] Falling back to disk-based queries", file=sys.stderr)
            return None
        
        print(f"[MEMORY] Database estimated at {estimated_mb:.1f}MB, attempting to load...", file=sys.stderr)
        
        # Create and load cache
        cache = MemoryCache(max_memory_mb=memory_limit_mb)
        if cache.preload(cursor):
            print(f"[MEMORY] Successfully loaded cache using {cache.get_memory_usage_mb():.1f}MB", file=sys.stderr)
            return cache
        else:
            print(f"[MEMORY] Cache preload failed: {cache.load_error}", file=sys.stderr)
            return None
            
    except MemoryError:
        print("[MEMORY] MemoryError caught, falling back to disk", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[MEMORY] Unexpected error during cache attempt: {e}", file=sys.stderr)
        return None