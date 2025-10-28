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
import re
from collections import defaultdict
from typing import Dict, List, Set, Any, Optional, Tuple
import sqlite3

from theauditor.indexer.schema import build_query, build_join_query, TABLES
from theauditor.utils.memory import get_recommended_memory_limit, get_available_memory

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
        self.cfg_block_statements = []
        self.function_returns = []

        # Specialized taint analysis tables (8 indexes: sql_queries, orm_queries, react_hooks, variable_usage)
        self.sql_queries = []
        self.orm_queries = []
        self.react_hooks = []
        self.variable_usage = []

        # Specialized security tables (4 indexes: api_endpoints, jwt_patterns)
        # INDEX BREAKDOWN: 31 primary indexes = 11 base + 8 CFG + 8 taint-specialized + 4 security-specialized
        self.api_endpoints = []
        self.jwt_patterns = []

        # Python-specific framework tables (Phase 3 Python parity)
        self.python_orm_models: List[Dict[str, Any]] = []
        self.python_orm_fields: List[Dict[str, Any]] = []
        self.orm_relationships: List[Dict[str, Any]] = []
        self.python_routes: List[Dict[str, Any]] = []
        self.python_blueprints: List[Dict[str, Any]] = []
        self.python_validators: List[Dict[str, Any]] = []

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

        # CFG table indexes (for flow-sensitive taint analysis)
        self.cfg_blocks_by_file = defaultdict(list)  # file -> [blocks]
        self.cfg_blocks_by_function = defaultdict(list)  # (file, func) -> [blocks]
        self.cfg_blocks_by_id = {}  # block_id -> block
        self.cfg_edges_by_file = defaultdict(list)  # file -> [edges]
        self.cfg_edges_by_function = defaultdict(list)  # (file, func) -> [edges]
        self.cfg_edges_by_source = defaultdict(list)  # source_block_id -> [edges]
        self.cfg_edges_by_target = defaultdict(list)  # target_block_id -> [edges]
        self.cfg_statements_by_block = defaultdict(list)  # block_id -> [statements]

        # NEW: Specialized table indexes for multi-table taint analysis (Phase 3.3)
        self.sql_queries_by_type = defaultdict(list)  # query_type -> [queries]
        self.sql_queries_by_file = defaultdict(list)  # file -> [queries]
        self.orm_queries_by_model = defaultdict(list)  # model_name -> [queries]
        self.orm_queries_by_file = defaultdict(list)  # file -> [queries]
        self.react_hooks_by_name = defaultdict(list)  # hook_name -> [hooks]
        self.react_hooks_by_file = defaultdict(list)  # file -> [hooks]
        self.variable_usage_by_name = defaultdict(list)  # var_name -> [usages]
        self.variable_usage_by_file = defaultdict(list)  # file -> [usages]

        # Phase 3.4 indexes
        self.api_endpoints_by_file = defaultdict(list)  # file -> [endpoints]
        self.api_endpoints_by_method = defaultdict(list)  # method -> [endpoints]
        self.jwt_patterns_by_file = defaultdict(list)  # file -> [patterns]
        self.jwt_patterns_by_type = defaultdict(list)  # pattern_type -> [patterns]

        # Python-specific indexes for fast ORM / route lookups
        self.python_orm_models_by_file = defaultdict(list)
        self.python_orm_models_by_name = defaultdict(list)
        self.python_orm_fields_by_model = defaultdict(list)
        self.orm_relationships_by_source = defaultdict(list)
        self.orm_relationships_by_target = defaultdict(list)
        self.python_routes_by_file = defaultdict(list)
        self.python_routes_by_framework = defaultdict(list)
        self.python_validators_by_model = defaultdict(list)
        self.python_validators_by_file = defaultdict(list)
        self.python_blueprints_by_name = defaultdict(list)

        # Python type annotation + ORM metadata
        self.type_annotations: List[Dict[str, Any]] = []
        self.type_annotations_by_file = defaultdict(list)
        self.python_param_types: Dict[Tuple[str, str, str], str] = {}
        self.python_model_names: Set[str] = set()
        self.python_table_to_model: Dict[str, str] = {}
        self.python_relationship_aliases = defaultdict(list)  # model -> [relationship dict]
        self.python_fk_fields = defaultdict(list)  # model -> [field dict]

        # Pre-computed patterns (will be populated during precompute)
        self.precomputed_sources = {}  # pattern -> [matching symbols]
        self.precomputed_sinks = {}    # pattern -> [matching symbols]
        self.precomputed_orm_sinks = []  # ORM query sinks (pattern-agnostic)
        self.call_graph = {}            # func -> [called_funcs]

        # Track active pattern maps for dynamic framework/registry support
        self.sources_dict: Dict[str, List[str]] = {}
        self.sinks_dict: Dict[str, List[str]] = {}
        self._sources_signature: Optional[str] = None
        self._sinks_signature: Optional[str] = None

        # Cache status
        self.is_loaded = False
        self.load_error = None

    def preload(
        self,
        cursor: sqlite3.Cursor,
        sources_dict: Optional[Dict[str, List[str]]] = None,
        sinks_dict: Optional[Dict[str, List[str]]] = None,
    ) -> bool:
        """
        Load entire database into memory with multiple indexes.

        Returns:
            True if successful, False if memory exceeded or error
        """
        try:
            # Guard against re-loading if already loaded
            if self.is_loaded:
                print(f"[MEMORY] Cache already loaded ({self.get_memory_usage_mb():.1f}MB), checking patterns...", file=sys.stderr)
                # Only update patterns if they changed
                if sources_dict is not None or sinks_dict is not None:
                    self._update_pattern_sets(sources_dict, sinks_dict)
                    print(f"[MEMORY] Pattern sets updated without reload", file=sys.stderr)
                return True

            print(f"[MEMORY] Starting database preload...", file=sys.stderr)

            # Schema contract guarantees all tables exist
            # Check current memory usage against limit throughout loading

            # Step 1: Load symbols with multi-indexing
            # SCHEMA CONTRACT: Use build_query for correct columns
            query = build_query('symbols', ['path', 'name', 'type', 'line', 'col'])
            cursor.execute(query)
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
            # NORMALIZED QUERY: Reconstruct source_vars list from junction table using GROUP_CONCAT
            # NO JSON PARSING - database provides the list directly
            cursor.execute("""
                SELECT
                    a.file, a.line, a.target_var, a.source_expr, a.in_function,
                    GROUP_CONCAT(asrc.source_var_name, '|') as source_vars_concat
                FROM assignments a
                LEFT JOIN assignment_sources asrc
                    ON a.file = asrc.assignment_file
                    AND a.line = asrc.assignment_line
                    AND a.target_var = asrc.assignment_target
                GROUP BY a.file, a.line, a.target_var
            """)
            assignments_data = cursor.fetchall()

            for file, line, target, source_expr, func, source_vars_concat in assignments_data:
                # Normalize path
                file = file.replace("\\", "/") if file else ""

                # Reconstruct source_vars list from concatenated string
                source_vars_list = source_vars_concat.split('|') if source_vars_concat else []

                assignment = {
                    "file": file,
                    "line": line or 0,
                    "target_var": target or "",
                    "source_expr": source_expr or "",
                    "source_vars": source_vars_list,  # Now a real Python list, not JSON string
                    "in_function": func or "global"
                }

                self.assignments.append(assignment)
                self.assignments_by_func[(file, func)].append(assignment)
                self.assignments_by_target[target].append(assignment)
                self.assignments_by_file[file].append(assignment)

                self.current_memory += sys.getsizeof(assignment) + 100

            print(f"[MEMORY] Loaded {len(self.assignments)} assignments", file=sys.stderr)

            # Step 3: Load function call arguments
            # SCHEMA CONTRACT: Use build_query for correct columns
            query = build_query('function_call_args', [
                'file', 'line', 'caller_function', 'callee_function',
                'param_name', 'argument_expr'
            ])
            cursor.execute(query)
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

            # Step 4: Load function returns
            # NORMALIZED QUERY: Reconstruct return_vars list from junction table using GROUP_CONCAT
            # NO JSON PARSING - database provides the list directly
            cursor.execute("""
                SELECT
                    fr.file, fr.line, fr.function_name, fr.return_expr,
                    GROUP_CONCAT(frsrc.return_var_name, '|') as return_vars_concat
                FROM function_returns fr
                LEFT JOIN function_return_sources frsrc
                    ON fr.file = frsrc.return_file
                    AND fr.line = frsrc.return_line
                    AND fr.function_name = frsrc.return_function
                GROUP BY fr.file, fr.line, fr.function_name
            """)
            returns_data = cursor.fetchall()

            for file, line, func_name, return_expr, return_vars_concat in returns_data:
                # Normalize path
                file = file.replace("\\", "/") if file else ""

                # Reconstruct return_vars list from concatenated string
                return_vars_list = return_vars_concat.split('|') if return_vars_concat else []

                ret = {
                    "file": file,
                    "function_name": func_name or "",
                    "return_expr": return_expr or "",
                    "return_vars": return_vars_list,  # Now a real Python list, not JSON string
                    "line": line or 0
                }

                self.function_returns.append(ret)
                self.returns_by_function[(file, func_name)].append(ret)

                self.current_memory += sys.getsizeof(ret) + 50

            print(f"[MEMORY] Loaded {len(self.function_returns)} function returns", file=sys.stderr)

            # Step 5: Load specialized tables for multi-table taint analysis (Phase 3.3)
            # SCHEMA CONTRACT: Use build_query for correct columns
            query = build_query('sql_queries', [
                'file_path', 'line_number', 'query_text', 'command'
            ], where="query_text IS NOT NULL AND query_text != '' AND command != 'UNKNOWN'")
            cursor.execute(query)
            sql_queries_data = cursor.fetchall()

            for file_path, line_number, query_text, command in sql_queries_data:
                file_path = file_path.replace("\\", "/") if file_path else ""

                query = {
                    "file": file_path,
                    "line": line_number or 0,
                    "query_text": query_text or "",
                    "command": command or ""
                }

                self.sql_queries.append(query)
                self.sql_queries_by_type[command].append(query)
                self.sql_queries_by_file[file_path].append(query)
                self.current_memory += sys.getsizeof(query) + 50

            print(f"[MEMORY] Loaded {len(self.sql_queries)} SQL queries", file=sys.stderr)

            # SCHEMA CONTRACT: Use build_query for correct columns
            query = build_query('orm_queries', [
                'file', 'line', 'query_type', 'includes'
            ], where="query_type IS NOT NULL")
            cursor.execute(query)
            orm_queries_data = cursor.fetchall()

            for file, line, query_type, includes in orm_queries_data:
                file = file.replace("\\", "/") if file else ""

                query = {
                    "file": file,
                    "line": line or 0,
                    "query_type": query_type or "",
                    "includes": includes or ""
                }

                self.orm_queries.append(query)
                self.orm_queries_by_model[query_type].append(query)
                self.orm_queries_by_file[file].append(query)
                self.current_memory += sys.getsizeof(query) + 50

            print(f"[MEMORY] Loaded {len(self.orm_queries)} ORM queries", file=sys.stderr)

            # SCHEMA-DRIVEN JOIN: Auto-discovers foreign key, validates columns, generates SQL
            query = build_join_query(
                base_table='react_hooks',
                base_columns=['file', 'line', 'hook_name'],
                join_table='react_hook_dependencies',
                join_columns=['dependency_name'],
                aggregate={'dependency_name': 'GROUP_CONCAT'},
                group_by=['file', 'line', 'hook_name']
            )
            cursor.execute(query)
            react_hooks_data = cursor.fetchall()

            for file, line, hook_name, deps_concat in react_hooks_data:
                file = file.replace("\\", "/") if file else ""
                # Reconstruct dependencies list from concatenated string
                deps_list = deps_concat.split('|') if deps_concat else []

                hook = {
                    "file": file,
                    "line": line or 0,
                    "hook_name": hook_name or "",
                    "dependencies": deps_list  # Now a real Python list
                }

                self.react_hooks.append(hook)
                self.react_hooks_by_name[hook_name].append(hook)
                self.react_hooks_by_file[file].append(hook)
                self.current_memory += sys.getsizeof(hook) + 50

            print(f"[MEMORY] Loaded {len(self.react_hooks)} React hooks", file=sys.stderr)

            # CRITICAL: variable_usage is REQUIRED for taint analysis - ALWAYS load it
            # SCHEMA CONTRACT: Use build_query to guarantee correct columns
            query = build_query('variable_usage', [
                'file', 'line', 'variable_name', 'usage_type', 'in_component'
            ])
            cursor.execute(query)
            variable_usage_data = cursor.fetchall()

            for file, line, variable_name, usage_type, in_component in variable_usage_data:
                file = file.replace("\\", "/") if file else ""

                usage = {
                    "file": file,
                    "line": line or 0,
                    "variable_name": variable_name or "",  # Schema contract: use actual column name
                    "usage_type": usage_type or "",
                    "in_component": in_component or ""  # Renamed from 'context'
                }

                self.variable_usage.append(usage)
                self.variable_usage_by_name[variable_name].append(usage)
                self.variable_usage_by_file[file].append(usage)
                self.current_memory += sys.getsizeof(usage) + 50

            print(f"[MEMORY] Loaded {len(self.variable_usage)} variable usages", file=sys.stderr)

            # Python-specific ORM metadata (Phase 3 parity)
            query = build_query('python_orm_models', [
                'file', 'line', 'model_name', 'table_name', 'orm_type'
            ])
            cursor.execute(query)
            python_orm_models_data = cursor.fetchall()

            for file, line, model_name, table_name, orm_type in python_orm_models_data:
                file = file.replace("\\", "/") if file else ""
                model_name = model_name or ""
                table_name = table_name or ""
                model = {
                    "file": file,
                    "line": line or 0,
                    "model_name": model_name,
                    "table_name": table_name,
                    "orm_type": orm_type or "sqlalchemy",
                }
                self.python_orm_models.append(model)
                self.python_orm_models_by_file[file].append(model)
                self.python_orm_models_by_name[model_name].append(model)
                self.current_memory += sys.getsizeof(model) + 50
                if model_name:
                    self.python_model_names.add(model_name)
                if table_name:
                    self.python_table_to_model[table_name.lower()] = model_name

            print(f"[MEMORY] Loaded {len(self.python_orm_models)} Python ORM models", file=sys.stderr)

            query = build_query('python_orm_fields', [
                'file', 'line', 'model_name', 'field_name', 'field_type',
                'is_primary_key', 'is_foreign_key', 'foreign_key_target'
            ])
            cursor.execute(query)
            python_orm_fields_data = cursor.fetchall()

            for file, line, model_name, field_name, field_type, is_pk, is_fk, fk_target in python_orm_fields_data:
                file = file.replace("\\", "/") if file else ""
                model_name = model_name or ""
                field = {
                    "file": file,
                    "line": line or 0,
                    "model_name": model_name or "",
                    "field_name": field_name or "",
                    "field_type": field_type or "",
                    "is_primary_key": bool(is_pk),
                    "is_foreign_key": bool(is_fk),
                    "foreign_key_target": fk_target or "",
                }
                target_model = self._resolve_model_from_fk_target(fk_target)
                field["target_model"] = target_model or ""
                self.python_orm_fields.append(field)
                self.python_orm_fields_by_model[model_name].append(field)
                if target_model:
                    self.python_fk_fields[model_name].append({
                        "field_name": field_name or "",
                        "target_model": target_model,
                        "foreign_key_target": fk_target or "",
                    })
                self.current_memory += sys.getsizeof(field) + 50

            print(f"[MEMORY] Loaded {len(self.python_orm_fields)} Python ORM fields", file=sys.stderr)

            query = build_query('orm_relationships', [
                'file', 'line', 'source_model', 'target_model', 'relationship_type',
                'foreign_key', 'cascade_delete', 'as_name'
            ])
            cursor.execute(query)
            orm_relationship_data = cursor.fetchall()

            for (
                file,
                line,
                source_model,
                target_model,
                rel_type,
                foreign_key,
                cascade_delete,
                alias,
            ) in orm_relationship_data:
                file = file.replace("\\", "/") if file else ""
                rel = {
                    "file": file,
                    "line": line or 0,
                    "source_model": source_model or "",
                    "target_model": target_model or "",
                    "relationship_type": rel_type or "",
                    "foreign_key": foreign_key or "",
                    "cascade_delete": bool(cascade_delete),
                    "as_name": alias or "",
                }
                self.orm_relationships.append(rel)
                self.orm_relationships_by_source[source_model].append(rel)
                self.orm_relationships_by_target[target_model].append(rel)
                self.current_memory += sys.getsizeof(rel) + 50
                alias_name = alias or target_model or ""
                if source_model and alias_name:
                    self.python_relationship_aliases[source_model].append({
                        "alias": alias_name,
                        "target_model": target_model or "",
                        "relationship_type": rel_type or "",
                        "cascade_delete": bool(cascade_delete),
                        "foreign_key": foreign_key or "",
                    })

            print(f"[MEMORY] Loaded {len(self.orm_relationships)} ORM relationships", file=sys.stderr)

            query = build_query('python_routes', [
                'file', 'line', 'framework', 'method', 'pattern',
                'handler_function', 'has_auth', 'dependencies', 'blueprint'
            ])
            cursor.execute(query)
            python_routes_data = cursor.fetchall()

            for (
                file,
                line,
                framework,
                method,
                pattern,
                handler_function,
                has_auth,
                dependencies,
                blueprint,
            ) in python_routes_data:
                file = file.replace("\\", "/") if file else ""
                deps_list: List[str] = []
                if dependencies:
                    try:
                        deps_list = json.loads(dependencies)
                    except Exception:
                        deps_list = []
                route = {
                    "file": file,
                    "line": line or 0,
                    "framework": framework or "",
                    "method": method or "",
                    "pattern": pattern or "",
                    "handler_function": handler_function or "",
                    "has_auth": bool(has_auth),
                    "dependencies": deps_list,
                    "blueprint": blueprint or "",
                }
                self.python_routes.append(route)
                self.python_routes_by_file[file].append(route)
                self.python_routes_by_framework[framework].append(route)
                self.current_memory += sys.getsizeof(route) + 50

            print(f"[MEMORY] Loaded {len(self.python_routes)} Python routes", file=sys.stderr)

            query = build_query('python_blueprints', [
                'file', 'line', 'blueprint_name', 'url_prefix', 'subdomain'
            ])
            cursor.execute(query)
            python_blueprints_data = cursor.fetchall()

            for file, line, blueprint_name, url_prefix, subdomain in python_blueprints_data:
                file = file.replace("\\", "/") if file else ""
                blueprint_entry = {
                    "file": file,
                    "line": line or 0,
                    "blueprint_name": blueprint_name or "",
                    "url_prefix": url_prefix or "",
                    "subdomain": subdomain or "",
                }
                self.python_blueprints.append(blueprint_entry)
                self.python_blueprints_by_name[blueprint_name].append(blueprint_entry)
                self.current_memory += sys.getsizeof(blueprint_entry) + 50

            print(f"[MEMORY] Loaded {len(self.python_blueprints)} Python blueprints", file=sys.stderr)

            query = build_query('python_validators', [
                'file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'
            ])
            cursor.execute(query)
            python_validators_data = cursor.fetchall()

            for file, line, model_name, field_name, validator_method, validator_type in python_validators_data:
                file = file.replace("\\", "/") if file else ""
                validator = {
                    "file": file,
                    "line": line or 0,
                    "model_name": model_name or "",
                    "field_name": field_name or "",
                    "validator_method": validator_method or "",
                    "validator_type": validator_type or "",
                }
                self.python_validators.append(validator)
                self.python_validators_by_model[model_name].append(validator)
                self.python_validators_by_file[file].append(validator)
                self.current_memory += sys.getsizeof(validator) + 50

            print(f"[MEMORY] Loaded {len(self.python_validators)} Python validators", file=sys.stderr)

            # Type annotations (used for Python model resolution)
            query = build_query('type_annotations', [
                'file', 'line', 'symbol_name', 'symbol_kind', 'type_annotation', 'return_type'
            ])
            cursor.execute(query)
            type_annotations_data = cursor.fetchall()

            for file, line, symbol_name, symbol_kind, type_annotation, return_type in type_annotations_data:
                file = file.replace("\\", "/") if file else ""
                entry = {
                    "file": file,
                    "line": line or 0,
                    "symbol_name": symbol_name or "",
                    "symbol_kind": symbol_kind or "",
                    "type_annotation": type_annotation or "",
                    "return_type": return_type or "",
                }
                self.type_annotations.append(entry)
                self.type_annotations_by_file[file].append(entry)
                self.current_memory += sys.getsizeof(entry) + 50

                if entry["symbol_kind"] == "parameter" and entry["symbol_name"]:
                    split_result = self._split_symbol_name(entry["symbol_name"])
                    if split_result:
                        func_candidate, param_name = split_result
                        for key in self._generate_param_type_keys(file, func_candidate, param_name):
                            if key not in self.python_param_types:
                                self.python_param_types[key] = entry["type_annotation"]

            # Step 6: Load CFG tables for flow-sensitive taint analysis
            # These tables enable path-sensitive analysis through control flow graphs

            # Load cfg_blocks
            query = build_query('cfg_blocks', [
                'id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'
            ])
            cursor.execute(query)
            cfg_blocks_data = cursor.fetchall()

            for block_id, file, func_name, block_type, start_line, end_line, condition_expr in cfg_blocks_data:
                file = file.replace("\\", "/") if file else ""

                block = {
                    "id": block_id,
                    "file": file,
                    "function_name": func_name or "",
                    "block_type": block_type or "",
                    "start_line": start_line or 0,
                    "end_line": end_line or 0,
                    "condition_expr": condition_expr or ""
                }

                self.cfg_blocks.append(block)
                self.cfg_blocks_by_file[file].append(block)
                self.cfg_blocks_by_function[(file, func_name)].append(block)
                self.cfg_blocks_by_id[block_id] = block
                self.current_memory += sys.getsizeof(block) + 100

            print(f"[MEMORY] Loaded {len(self.cfg_blocks)} CFG blocks", file=sys.stderr)

            # Load cfg_edges
            query = build_query('cfg_edges', [
                'id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'
            ])
            cursor.execute(query)
            cfg_edges_data = cursor.fetchall()

            for edge_id, file, func_name, source_id, target_id, edge_type in cfg_edges_data:
                file = file.replace("\\", "/") if file else ""

                edge = {
                    "id": edge_id,
                    "file": file,
                    "function_name": func_name or "",
                    "source_block_id": source_id,
                    "target_block_id": target_id,
                    "edge_type": edge_type or ""
                }

                self.cfg_edges.append(edge)
                self.cfg_edges_by_file[file].append(edge)
                self.cfg_edges_by_function[(file, func_name)].append(edge)
                self.cfg_edges_by_source[source_id].append(edge)
                self.cfg_edges_by_target[target_id].append(edge)
                self.current_memory += sys.getsizeof(edge) + 100

            print(f"[MEMORY] Loaded {len(self.cfg_edges)} CFG edges", file=sys.stderr)

            # Load cfg_block_statements
            query = build_query('cfg_block_statements', [
                'block_id', 'statement_type', 'line', 'statement_text'
            ])
            cursor.execute(query)
            cfg_statements_data = cursor.fetchall()

            for block_id, stmt_type, line, stmt_text in cfg_statements_data:
                statement = {
                    "block_id": block_id,
                    "statement_type": stmt_type or "",
                    "line": line or 0,
                    "statement_text": stmt_text or ""
                }

                self.cfg_block_statements.append(statement)
                self.cfg_statements_by_block[block_id].append(statement)
                self.current_memory += sys.getsizeof(statement) + 50

            print(f"[MEMORY] Loaded {len(self.cfg_block_statements)} CFG statements", file=sys.stderr)

            # Step 7: Load Phase 3.4 security tables (jwt_patterns, api_endpoints)

            # Load api_endpoints
            # SCHEMA-DRIVEN JOIN: Auto-discovers foreign key, validates columns, generates SQL
            query = build_join_query(
                base_table='api_endpoints',
                base_columns=['file', 'line', 'method', 'pattern', 'path', 'has_auth', 'handler_function'],
                join_table='api_endpoint_controls',
                join_columns=['control_name'],
                aggregate={'control_name': 'GROUP_CONCAT'},
                group_by=['file', 'line', 'method', 'pattern', 'path', 'has_auth', 'handler_function']
            )
            cursor.execute(query)
            api_endpoints_data = cursor.fetchall()

            for file, line, method, pattern, path, has_auth, handler_func, controls_concat in api_endpoints_data:
                file = file.replace("\\", "/") if file else ""
                # Reconstruct controls list from concatenated string
                controls_list = controls_concat.split('|') if controls_concat else []

                endpoint = {
                    "file": file,
                    "line": line or 0,
                    "method": method or "",
                    "pattern": pattern or "",
                    "path": path or "",
                    "controls": controls_list,  # Now a real Python list
                    "has_auth": bool(has_auth),
                    "handler_function": handler_func or ""
                }

                self.api_endpoints.append(endpoint)
                self.api_endpoints_by_file[file].append(endpoint)
                self.api_endpoints_by_method[method].append(endpoint)
                self.current_memory += sys.getsizeof(endpoint) + 50

            print(f"[MEMORY] Loaded {len(self.api_endpoints)} API endpoints", file=sys.stderr)

            # Load jwt_patterns
            query = build_query('jwt_patterns', [
                'file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'
            ])
            cursor.execute(query)
            jwt_patterns_data = cursor.fetchall()

            for file_path, line_number, pattern_type, pattern_text, secret_source, algorithm in jwt_patterns_data:
                file_path = file_path.replace("\\", "/") if file_path else ""

                pattern = {
                    "file": file_path,  # Normalize to 'file' key
                    "line": line_number or 0,
                    "pattern_type": pattern_type or "",
                    "pattern_text": pattern_text or "",
                    "secret_source": secret_source or "",
                    "algorithm": algorithm or ""
                }

                self.jwt_patterns.append(pattern)
                self.jwt_patterns_by_file[file_path].append(pattern)
                self.jwt_patterns_by_type[pattern_type].append(pattern)
                self.current_memory += sys.getsizeof(pattern) + 50

            print(f"[MEMORY] Loaded {len(self.jwt_patterns)} JWT patterns", file=sys.stderr)

            # Step 8: Pre-compute call graph (NEW OPTIMIZATION!)
            self._precompute_call_graph()

            # Step 7: Pre-compute common patterns (NEW OPTIMIZATION!)
            self._update_pattern_sets(sources_dict, sinks_dict)

            print(f"[MEMORY] Total memory used: {self.current_memory / 1024 / 1024:.1f}MB", file=sys.stderr)
            print(f"[MEMORY] Indexes built: 31 primary (11 base + 8 CFG + 8 taint-specialized + 4 security-specialized), 3 pre-computed (sources, sinks, call_graph)", file=sys.stderr)

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

    def _clone_pattern_map(self, pattern_map: Optional[Dict[str, List[str]]]) -> Dict[str, List[str]]:
        """Create a defensive copy of a pattern map."""
        if not pattern_map:
            return {}
        return {category: list(patterns) for category, patterns in pattern_map.items()}

    def _compute_signature(self, pattern_map: Dict[str, List[str]]) -> str:
        """Create a stable signature for a pattern map (used for change detection)."""
        normalized = {category: sorted(patterns) for category, patterns in pattern_map.items()}
        return json.dumps(normalized, sort_keys=True)

    def _update_pattern_sets(
        self,
        sources_dict: Optional[Dict[str, List[str]]],
        sinks_dict: Optional[Dict[str, List[str]]]
    ) -> None:
        """Ensure in-memory pattern maps reflect the latest configuration."""
        from .sources import TAINT_SOURCES, SECURITY_SINKS

        updated = False

        if sources_dict is None:
            base_sources = self.sources_dict if self.sources_dict else TAINT_SOURCES
        else:
            base_sources = sources_dict

        cloned_sources = self._clone_pattern_map(base_sources)
        new_sources_sig = self._compute_signature(cloned_sources)
        if self._sources_signature != new_sources_sig:
            self.sources_dict = cloned_sources
            self._sources_signature = new_sources_sig
            updated = True

        if sinks_dict is None:
            base_sinks = self.sinks_dict if self.sinks_dict else SECURITY_SINKS
        else:
            base_sinks = sinks_dict

        cloned_sinks = self._clone_pattern_map(base_sinks)
        new_sinks_sig = self._compute_signature(cloned_sinks)
        if self._sinks_signature != new_sinks_sig:
            self.sinks_dict = cloned_sinks
            self._sinks_signature = new_sinks_sig
            updated = True

        if updated:
            self._precompute_patterns(self.sources_dict, self.sinks_dict)

    def _precompute_patterns(
        self,
        sources_dict: Dict[str, List[str]],
        sinks_dict: Dict[str, List[str]]
    ) -> None:
        """Pre-compute common taint source and sink patterns for TRUE O(1) lookup."""
        self.precomputed_sources.clear()
        self.precomputed_sinks.clear()
        self.precomputed_orm_sinks = []

        # Pre-compute ALL taint source patterns
        for category, patterns in sources_dict.items():
            for pattern in patterns:
                matching_symbols = []

                # Pre-compute all possible matches
                # CRITICAL: Must filter by type to exclude variable declarations
                if "." in pattern:
                    # Property access pattern - exact match first
                    if pattern in self.symbols_by_name:
                        for sym in self.symbols_by_name[pattern]:
                            if sym['type'] in ('call', 'property'):
                                matching_symbols.append(sym)

                    # Also check substring matches for property patterns
                    for name, symbols in self.symbols_by_name.items():
                        if pattern in name and name != pattern:  # Avoid duplicates
                            for sym in symbols:
                                if sym['type'] in ('call', 'property'):
                                    matching_symbols.append(sym)
                else:
                    # Direct name match - simple O(1) lookup
                    if pattern in self.symbols_by_name:
                        for sym in self.symbols_by_name[pattern]:
                            if sym['type'] in ('call', 'property'):
                                matching_symbols.append(sym)

                # Store pre-computed results even if empty (to avoid re-searching)
                self.precomputed_sources[pattern] = matching_symbols

        # Pre-compute ALL security sink patterns (Phase 3.3: Multi-table strategy)
        for category, patterns in sinks_dict.items():
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
                                            "command": query["command"],
                                            "table": "sql_queries"
                                        }
                                    })

                    # Check ORM queries table
                    for query in self.orm_queries:
                        if pattern in query["query_type"]:
                            matching_results.append({
                                "file": query["file"],
                                "name": f"{query['query_type']}",
                                "line": query["line"],
                                "column": 0,
                                "pattern": pattern,
                                "category": category,
                                "type": "sink",
                                "metadata": {
                                    "query_type": query["query_type"],
                                    "includes": query["includes"],
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

        # ORM queries behave as implicit SQL sinks regardless of configured patterns.
        # Mimic disk-based implementation by caching every ORM query as its own sink.
        for query in self.orm_queries:
            self.precomputed_orm_sinks.append({
                "file": query["file"],
                "name": query["query_type"],
                "line": query["line"],
                "column": 0,
                "pattern": query["query_type"],
                "category": "sql",
                "type": "sink",
                "metadata": {
                    "query_type": query["query_type"],
                    "includes": query["includes"],
                    "table": "orm_queries"
                }
            })

        print(f"[MEMORY] Pre-computed {len(self.precomputed_sources)} source patterns", file=sys.stderr)
        print(f"[MEMORY] Pre-computed {len(self.precomputed_sinks)} sink patterns (multi-table)", file=sys.stderr)

    def find_taint_sources_cached(self, sources_dict: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """
        Find all occurrences of taint sources using cache.
        
        Returns same format as database.find_taint_sources for compatibility.
        """
        sources = []
        # Ensure pattern maps are up-to-date with provided overrides
        self._update_pattern_sets(sources_dict, None)

        sources_to_use = sources_dict if sources_dict is not None else self.sources_dict
        
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
                        # CRITICAL: Must filter by type to exclude variable declarations
                        for sym in self.symbols_by_name[source_pattern]:
                            if sym['type'] in ('call', 'property'):
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
                                    if sym['type'] in ('call', 'property'):
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
                            if sym['type'] in ('call', 'property'):
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
        sinks = []
        # Ensure pattern maps are up-to-date with provided overrides
        self._update_pattern_sets(None, sinks_dict)

        sinks_to_use = sinks_dict if sinks_dict is not None else self.sinks_dict

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

        # Always include ORM sinks (implicit SQL operations)
        sinks.extend(self.precomputed_orm_sinks)

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
        self.cfg_block_statements.clear()
        self.function_returns.clear()

        # Clear specialized tables (Phase 3.3)
        self.sql_queries.clear()
        self.orm_queries.clear()
        self.react_hooks.clear()
        self.variable_usage.clear()
        self.python_orm_models.clear()
        self.python_orm_fields.clear()
        self.orm_relationships.clear()
        self.python_routes.clear()
        self.python_blueprints.clear()
        self.python_validators.clear()

        # Clear Phase 3.4 security tables
        self.api_endpoints.clear()
        self.jwt_patterns.clear()

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

        # Clear CFG table indexes
        self.cfg_blocks_by_file.clear()
        self.cfg_blocks_by_function.clear()
        self.cfg_blocks_by_id.clear()
        self.cfg_edges_by_file.clear()
        self.cfg_edges_by_function.clear()
        self.cfg_edges_by_source.clear()
        self.cfg_edges_by_target.clear()
        self.cfg_statements_by_block.clear()

        # Clear specialized table indexes (Phase 3.3)
        self.sql_queries_by_type.clear()
        self.sql_queries_by_file.clear()
        self.orm_queries_by_model.clear()
        self.orm_queries_by_file.clear()
        self.react_hooks_by_name.clear()
        self.react_hooks_by_file.clear()
        self.variable_usage_by_name.clear()
        self.variable_usage_by_file.clear()
        self.python_orm_models_by_file.clear()
        self.python_orm_models_by_name.clear()
        self.python_orm_fields_by_model.clear()
        self.orm_relationships_by_source.clear()
        self.orm_relationships_by_target.clear()
        self.python_routes_by_file.clear()
        self.python_routes_by_framework.clear()
        self.python_validators_by_model.clear()
        self.python_validators_by_file.clear()
        self.python_blueprints_by_name.clear()
        self.type_annotations.clear()
        self.type_annotations_by_file.clear()
        self.python_param_types.clear()
        self.python_model_names.clear()
        self.python_table_to_model.clear()
        self.python_relationship_aliases.clear()
        self.python_fk_fields.clear()

        # Clear Phase 3.4 indexes
        self.api_endpoints_by_file.clear()
        self.api_endpoints_by_method.clear()
        self.jwt_patterns_by_file.clear()
        self.jwt_patterns_by_type.clear()

        self.precomputed_sources.clear()
        self.precomputed_sinks.clear()
        self.call_graph.clear()

        self.sources_dict.clear()
        self.sinks_dict.clear()
        self._sources_signature = None
        self._sinks_signature = None

        self.current_memory = 0
        self.is_loaded = False

        print("[MEMORY] Cache cleared", file=sys.stderr)

    def _resolve_model_from_fk_target(self, fk_target: Optional[str]) -> Optional[str]:
        """Resolve model name from ForeignKey target string."""
        if not fk_target:
            return None
        target = fk_target.strip().strip('"').strip("'")
        if not target:
            return None
        table_part = target.split(".", 1)[0]
        table_lookup = table_part.lower()
        if table_lookup in self.python_table_to_model:
            return self.python_table_to_model[table_lookup]
        if table_part in self.python_model_names:
            return table_part
        capitalized = table_part[:1].upper() + table_part[1:]
        if capitalized in self.python_model_names:
            return capitalized
        return None

    def _split_symbol_name(self, symbol_name: str) -> Optional[Tuple[str, str]]:
        """Split symbol_name into function/method and parameter components."""
        if not symbol_name or "." not in symbol_name:
            return None
        func_name, param_name = symbol_name.rsplit(".", 1)
        func_name = func_name.strip()
        param_name = param_name.strip()
        if not func_name or not param_name:
            return None
        return func_name, param_name

    def _generate_param_type_keys(self, file_path: str, func_name: str, param_name: str) -> List[Tuple[str, str, str]]:
        """Generate lookup keys for parameter type annotations with fallbacks."""
        candidates = []
        if func_name:
            candidates.extend(self._generate_function_name_candidates(func_name))
        else:
            candidates.append("global")
        unique = []
        seen = set()
        for candidate in candidates:
            key = (file_path, candidate, param_name)
            if key not in seen:
                seen.add(key)
                unique.append(key)
        return unique

    def _generate_function_name_candidates(self, func_name: str) -> List[str]:
        """Generate function name variants for lookups (full, suffixes, lowercase)."""
        if not func_name:
            return ["global"]
        parts = [segment for segment in func_name.split(".") if segment]
        if not parts:
            return [func_name]
        candidates: List[str] = []
        for i in range(len(parts)):
            candidate = ".".join(parts[i:])
            if candidate:
                candidates.append(candidate)
        lower = func_name.lower()
        if lower not in candidates:
            candidates.append(lower)
        if parts[-1] not in candidates:
            candidates.append(parts[-1])
        return candidates

    def _infer_model_from_assignment(self, assignment: Dict[str, Any]) -> Optional[str]:
        """Infer model type from assignment source expression (e.g., Model())."""
        source_expr = assignment.get("source_expr") or ""
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(", source_expr)
        if match:
            candidate = match.group(1)
            if candidate in self.python_model_names:
                return candidate
        return None

    def resolve_python_model_from_annotation(self, annotation: Optional[str]) -> Optional[str]:
        """Resolve a model name from a type annotation string."""
        if not annotation:
            return None
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", annotation)
        for token in tokens:
            if token in self.python_model_names:
                return token
            lower = token.lower()
            if lower in self.python_table_to_model:
                return self.python_table_to_model[lower]
            capitalized = token[:1].upper() + token[1:]
            if capitalized in self.python_model_names:
                return capitalized
        return None

    def get_python_model_for_var(
        self,
        file_path: str,
        function_names: List[str],
        var_name: str,
        existing_bindings: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Resolve Python ORM model for a variable using annotations or assignments."""
        if not var_name:
            return None
        if existing_bindings and var_name in existing_bindings:
            return existing_bindings[var_name]

        candidates = []
        for func in function_names or []:
            candidates.extend(self._generate_function_name_candidates(func))
        if not candidates:
            candidates.append("global")

        for func_candidate in candidates:
            key = (file_path, func_candidate, var_name)
            if key in self.python_param_types:
                model = self.resolve_python_model_from_annotation(self.python_param_types[key])
                if model:
                    return model

        # Fallback: inspect assignments within candidate functions
        for func_candidate in candidates:
            assignments = self.assignments_by_func.get((file_path, func_candidate))
            if not assignments and func_candidate.endswith(".py"):
                assignments = self.assignments_by_func.get((file_path, "global"))
            if not assignments:
                continue
            for assignment in assignments:
                if assignment.get("target_var") == var_name:
                    model = self._infer_model_from_assignment(assignment)
                    if model:
                        return model

        return None

    def get_python_relationships(self, model_name: str) -> List[Dict[str, Any]]:
        """Return relationship definitions for a Python ORM model."""
        return self.python_relationship_aliases.get(model_name, [])

    def get_python_fk_fields(self, model_name: str) -> List[Dict[str, Any]]:
        """Return foreign key field definitions for a model."""
        return self.python_fk_fields.get(model_name, [])

    def get_assignments_for_function(self, file_path: str, function_name: str) -> List[Dict[str, Any]]:
        """Return assignments for given function name (with fallbacks)."""
        assignments = self.assignments_by_func.get((file_path, function_name))
        if assignments:
            return assignments
        for candidate in self._generate_function_name_candidates(function_name):
            assignments = self.assignments_by_func.get((file_path, candidate))
            if assignments:
                return assignments
        return self.assignments_by_func.get((file_path, "global"), [])


def attempt_cache_preload(
    cursor: sqlite3.Cursor,
    memory_limit_mb: Optional[int] = None,
    sources_dict: Optional[Dict[str, List[str]]] = None,
    sinks_dict: Optional[Dict[str, List[str]]] = None,
) -> Optional[MemoryCache]:
    """
    Attempt to preload database into memory cache with intelligent memory management.

    Uses system RAM detection to determine safe memory limits. Will not break
    CI/CD or automation by trying to load more than available RAM.

    Args:
        cursor: Database cursor
        memory_limit_mb: Optional explicit memory limit (uses smart detection if None)
        sources_dict: Optional taint sources
        sinks_dict: Optional security sinks

    Returns:
        MemoryCache if successful, None if failed or insufficient memory
    """
    try:
        # Use intelligent memory detection if no explicit limit provided
        if memory_limit_mb is None:
            memory_limit_mb = get_recommended_memory_limit()
            print(f"[MEMORY] Using system-detected limit: {memory_limit_mb}MB", file=sys.stderr)

        # Check if we have enough available memory before attempting load
        available_mb = get_available_memory()
        if available_mb > 0:
            # Need at least some headroom - don't consume ALL available memory
            if available_mb < memory_limit_mb * 0.5:  # Need at least 50% of our limit available
                print(f"[MEMORY] Insufficient available RAM ({available_mb}MB), falling back to disk", file=sys.stderr)
                return None

        # Attempt to load with detected limit
        cache = MemoryCache(max_memory_mb=memory_limit_mb)
        if cache.preload(cursor, sources_dict=sources_dict, sinks_dict=sinks_dict):
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
