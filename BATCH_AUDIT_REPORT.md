# Batch Tuple Size vs INSERT Statement Audit

**Date:** 2025-10-03
**File:** `theauditor/indexer/database.py`
**Purpose:** Verify all batch list tuple sizes match their corresponding INSERT statement placeholder counts

---

## Summary

**Total batches audited:** 30
**Mismatches found:** 0
**Status:** ✅ ALL BATCHES VALIDATED

---

## Detailed Analysis

### 1. files_batch
- **add_file()** appends: `(path, sha256, ext, bytes_size, loc)` = **5 elements**
- **INSERT columns:** `(path, sha256, ext, bytes, loc)` = **5 columns**
- **INSERT values:** `(?, ?, ?, ?, ?)` = **5 placeholders**
- **Line:** 1497
- **Status:** ✅ MATCH

### 2. refs_batch
- **add_ref()** appends: `(src, kind, value)` = **3 elements**
- **INSERT columns:** `(src, kind, value)` = **3 columns**
- **INSERT values:** `(?, ?, ?)` = **3 placeholders**
- **Line:** 1504
- **Status:** ✅ MATCH

### 3. endpoints_batch (api_endpoints table)
- **add_endpoint()** appends: `(file_path, line, method, pattern, path, controls_json, has_auth, handler_function)` = **8 elements**
- **INSERT columns:** `(file, line, method, pattern, path, controls, has_auth, handler_function)` = **8 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?)` = **8 placeholders**
- **Line:** 1511
- **Status:** ✅ MATCH

### 4. sql_objects_batch
- **add_sql_object()** appends: `(file_path, kind, name)` = **3 elements**
- **INSERT columns:** `(file, kind, name)` = **3 columns**
- **INSERT values:** `(?, ?, ?)` = **3 placeholders**
- **Line:** 1518
- **Status:** ✅ MATCH

### 5. sql_queries_batch
- **add_sql_query()** appends: `(file_path, line, query_text, command, tables_json, extraction_source)` = **6 elements**
- **INSERT columns:** `(file_path, line_number, query_text, command, tables, extraction_source)` = **6 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?)` = **6 placeholders**
- **Line:** 1525
- **Status:** ✅ MATCH

### 6. jwt_patterns_batch
- **add_jwt_pattern()** appends dict with keys: `file_path, line_number, pattern_type, pattern_text, secret_source, algorithm` = **6 fields**
- **INSERT columns:** `(file_path, line_number, pattern_type, pattern_text, secret_source, algorithm)` = **6 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?)` = **6 placeholders**
- **Line:** 1217 (_flush_jwt_patterns method)
- **Status:** ✅ MATCH (uses dict-based batch, converted to tuple in executemany)

### 7. symbols_batch
- **add_symbol()** appends: `(path, name, symbol_type, line, col)` = **5 elements**
- **INSERT columns:** `(path, name, type, line, col)` = **5 columns**
- **INSERT values:** `(?, ?, ?, ?, ?)` = **5 placeholders**
- **Line:** 1535
- **Status:** ✅ MATCH

### 8. orm_queries_batch
- **add_orm_query()** appends: `(file_path, line, query_type, includes, has_limit, has_transaction)` = **6 elements**
- **INSERT columns:** `(file, line, query_type, includes, has_limit, has_transaction)` = **6 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?)` = **6 placeholders**
- **Line:** 1542
- **Status:** ✅ MATCH

### 9. docker_images_batch
- **add_docker_image()** appends: `(file_path, base_image, ports_json, env_json, args_json, user, has_healthcheck)` = **7 elements**
- **INSERT columns:** `(file_path, base_image, exposed_ports, env_vars, build_args, user, has_healthcheck)` = **7 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?)` = **7 placeholders**
- **Line:** 1549
- **Status:** ✅ MATCH

### 10. assignments_batch
- **add_assignment()** appends: `(file_path, line, target_var, source_expr, source_vars_json, in_function)` = **6 elements**
- **INSERT columns:** `(file, line, target_var, source_expr, source_vars, in_function)` = **6 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?)` = **6 placeholders**
- **Line:** 1556
- **Status:** ✅ MATCH

### 11. function_call_args_batch
- **add_function_call_arg()** appends: `(file_path, line, caller_function, callee_function, arg_index, arg_expr, param_name)` = **7 elements**
- **INSERT columns:** `(file, line, caller_function, callee_function, argument_index, argument_expr, param_name)` = **7 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?)` = **7 placeholders**
- **Line:** 1563
- **Status:** ✅ MATCH

### 12. function_returns_batch
- **add_function_return()** appends: `(file_path, line, function_name, return_expr, return_vars_json)` = **5 elements**
- **INSERT columns:** `(file, line, function_name, return_expr, return_vars)` = **5 columns**
- **INSERT values:** `(?, ?, ?, ?, ?)` = **5 placeholders**
- **Line:** 1570
- **Status:** ✅ MATCH

### 13. prisma_batch
- **add_prisma_model()** appends: `(model_name, field_name, field_type, is_indexed, is_unique, is_relation)` = **6 elements**
- **INSERT columns:** `(model_name, field_name, field_type, is_indexed, is_unique, is_relation)` = **6 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?)` = **6 placeholders**
- **Line:** 1577
- **Status:** ✅ MATCH

### 14. compose_batch
- **add_compose_service()** appends: `(file_path, service_name, image, ports_json, volumes_json, env_json, is_privileged, network_mode, user, cap_add_json, cap_drop_json, security_opt_json, restart, command_json, entrypoint_json, depends_on_json, healthcheck_json)` = **17 elements**
- **INSERT columns:** `(file_path, service_name, image, ports, volumes, environment, is_privileged, network_mode, user, cap_add, cap_drop, security_opt, restart, command, entrypoint, depends_on, healthcheck)` = **17 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)` = **17 placeholders**
- **Line:** 1586
- **Status:** ✅ MATCH

### 15. nginx_batch
- **add_nginx_config()** appends: `(file_path, block_type, block_context, directives_json, level)` = **5 elements**
- **INSERT columns:** `(file_path, block_type, block_context, directives, level)` = **5 columns**
- **INSERT values:** `(?, ?, ?, ?, ?)` = **5 placeholders**
- **Line:** 1598
- **Status:** ✅ MATCH

### 16. config_files_batch
- **add_config_file()** appends: `(path, content, file_type, context)` = **4 elements**
- **INSERT columns:** `(path, content, type, context_dir)` = **4 columns**
- **INSERT values:** `(?, ?, ?, ?)` = **4 placeholders**
- **Line:** 1606
- **Status:** ✅ MATCH

### 17. cfg_blocks_batch
- **add_cfg_block()** appends: `(file_path, function_name, block_type, start_line, end_line, condition_expr, temp_id)` = **7 elements**
- **INSERT columns:** `(file, function_name, block_type, start_line, end_line, condition_expr)` = **6 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?)` = **6 placeholders**
- **Line:** 1621
- **Status:** ✅ MATCH (temp_id is stripped before INSERT - used only for ID mapping)

### 18. cfg_edges_batch
- **add_cfg_edge()** appends: `(file_path, function_name, source_block_id, target_block_id, edge_type)` = **5 elements**
- **INSERT columns:** `(file, function_name, source_block_id, target_block_id, edge_type)` = **5 columns**
- **INSERT values:** `(?, ?, ?, ?, ?)` = **5 placeholders**
- **Line:** 1641
- **Status:** ✅ MATCH

### 19. cfg_statements_batch
- **add_cfg_statement()** appends: `(block_id, statement_type, line, statement_text)` = **4 elements**
- **INSERT columns:** `(block_id, statement_type, line, statement_text)` = **4 columns**
- **INSERT values:** `(?, ?, ?, ?)` = **4 placeholders**
- **Line:** 1656
- **Status:** ✅ MATCH

### 20. react_components_batch
- **add_react_component()** appends: `(file_path, name, component_type, start_line, end_line, has_jsx, hooks_json, props_type)` = **8 elements**
- **INSERT columns:** `(file, name, type, start_line, end_line, has_jsx, hooks_used, props_type)` = **8 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?)` = **8 placeholders**
- **Line:** 1667
- **Status:** ✅ MATCH

### 21. react_hooks_batch
- **add_react_hook()** appends: `(file_path, line, component_name, hook_name, deps_array_json, deps_vars_json, callback_body, has_cleanup, cleanup_type)` = **9 elements**
- **INSERT columns:** `(file, line, component_name, hook_name, dependency_array, dependency_vars, callback_body, has_cleanup, cleanup_type)` = **9 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?, ?)` = **9 placeholders**
- **Line:** 1677
- **Status:** ✅ MATCH

### 22. variable_usage_batch
- **add_variable_usage()** appends: `(file_path, line, variable_name, usage_type, in_component or '', in_hook or '', scope_level)` = **7 elements**
- **INSERT columns:** `(file, line, variable_name, usage_type, in_component, in_hook, scope_level)` = **7 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?)` = **7 placeholders**
- **Line:** 1686
- **Status:** ✅ MATCH

### 23. function_returns_jsx_batch
- **add_function_return_jsx()** appends: `(file_path, line, function_name, return_expr, return_vars_json, has_jsx, returns_component, cleanup_operations, jsx_mode, extraction_pass)` = **10 elements**
- **INSERT columns:** `(file, line, function_name, return_expr, return_vars, has_jsx, returns_component, cleanup_operations, jsx_mode, extraction_pass)` = **10 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)` = **10 placeholders**
- **Line:** 1697
- **Status:** ✅ MATCH

### 24. symbols_jsx_batch
- **add_symbol_jsx()** appends: `(path, name, symbol_type, line, col, jsx_mode, extraction_pass)` = **7 elements**
- **INSERT columns:** `(path, name, type, line, col, jsx_mode, extraction_pass)` = **7 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?)` = **7 placeholders**
- **Line:** 1706
- **Status:** ✅ MATCH

### 25. assignments_jsx_batch
- **add_assignment_jsx()** appends: `(file_path, line, target_var, source_expr, source_vars_json, in_function, jsx_mode, extraction_pass)` = **8 elements**
- **INSERT columns:** `(file, line, target_var, source_expr, source_vars, in_function, jsx_mode, extraction_pass)` = **8 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?)` = **8 placeholders**
- **Line:** 1715
- **Status:** ✅ MATCH

### 26. function_call_args_jsx_batch
- **add_function_call_arg_jsx()** appends: `(file_path, line, caller_function, callee_function, arg_index, arg_expr, param_name, jsx_mode, extraction_pass)` = **9 elements**
- **INSERT columns:** `(file, line, caller_function, callee_function, argument_index, argument_expr, param_name, jsx_mode, extraction_pass)` = **9 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?, ?)` = **9 placeholders**
- **Line:** 1725
- **Status:** ✅ MATCH

### 27. vue_components_batch
- **add_vue_component()** appends: `(file_path, name, component_type, start_line, end_line, has_template, has_style, composition_api_used, props_json, emits_json, setup_return)` = **11 elements**
- **INSERT columns:** `(file, name, type, start_line, end_line, has_template, has_style, composition_api_used, props_definition, emits_definition, setup_return)` = **11 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)` = **11 placeholders**
- **Line:** 1736
- **Status:** ✅ MATCH

### 28. vue_hooks_batch
- **add_vue_hook()** appends: `(file_path, line, component_name, hook_name, hook_type, deps_json, return_value, is_async)` = **8 elements**
- **INSERT columns:** `(file, line, component_name, hook_name, hook_type, dependencies, return_value, is_async)` = **8 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?)` = **8 placeholders**
- **Line:** 1746
- **Status:** ✅ MATCH

### 29. vue_directives_batch
- **add_vue_directive()** appends: `(file_path, line, directive_name, expression, in_component, has_key, modifiers_json)` = **7 elements**
- **INSERT columns:** `(file, line, directive_name, expression, in_component, has_key, modifiers)` = **7 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?)` = **7 placeholders**
- **Line:** 1755
- **Status:** ✅ MATCH

### 30. vue_provide_inject_batch
- **add_vue_provide_inject()** appends: `(file_path, line, component_name, operation_type, key_name, value_expr, is_reactive)` = **7 elements**
- **INSERT columns:** `(file, line, component_name, operation_type, key_name, value_expr, is_reactive)` = **7 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?)` = **7 placeholders**
- **Line:** 1764
- **Status:** ✅ MATCH

### 31. type_annotations_batch
- **add_type_annotation()** appends: `(file_path, line, column, symbol_name, symbol_kind, type_annotation, is_any, is_unknown, is_generic, has_type_params, type_params, return_type, extends_type)` = **13 elements**
- **INSERT columns:** `(file, line, column, symbol_name, symbol_kind, type_annotation, is_any, is_unknown, is_generic, has_type_params, type_params, return_type, extends_type)` = **13 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)` = **13 placeholders**
- **Line:** 1776
- **Status:** ✅ MATCH

### 32. frameworks_batch
- **add_framework()** appends: `(name, version, language, path, source, is_primary)` = **6 elements**
- **INSERT columns:** `(name, version, language, path, source, is_primary)` = **6 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?)` = **6 placeholders**
- **Line:** 1785
- **Status:** ✅ MATCH

### 33. framework_safe_sinks_batch
- **add_framework_safe_sink()** appends: `(framework_id, pattern, sink_type, is_safe, reason)` = **5 elements**
- **INSERT columns:** `(framework_id, sink_pattern, sink_type, is_safe, reason)` = **5 columns**
- **INSERT values:** `(?, ?, ?, ?, ?)` = **5 placeholders**
- **Line:** 1793
- **Status:** ✅ MATCH

### 34. package_configs_batch
- **add_package_config()** appends: `(file_path, package_name, version, deps_json, dev_deps_json, peer_deps_json, scripts_json, engines_json, workspaces_json, is_private)` = **10 elements**
- **INSERT columns:** `(file_path, package_name, version, dependencies, dev_dependencies, peer_dependencies, scripts, engines, workspaces, private)` = **10 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)` = **10 placeholders**
- **Line:** 1804
- **Status:** ✅ MATCH

### 35. lock_analysis_batch
- **add_lock_analysis()** appends: `(file_path, lock_type, package_manager_version, total_packages, duplicates_json, lock_file_version)` = **6 elements**
- **INSERT columns:** `(file_path, lock_type, package_manager_version, total_packages, duplicate_packages, lock_file_version)` = **6 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?)` = **6 placeholders**
- **Line:** 1814
- **Status:** ✅ MATCH

### 36. import_styles_batch
- **add_import_style()** appends: `(file_path, line, package, import_style, names_json, alias_name, full_statement)` = **7 elements**
- **INSERT columns:** `(file, line, package, import_style, imported_names, alias_name, full_statement)` = **7 columns**
- **INSERT values:** `(?, ?, ?, ?, ?, ?, ?)` = **7 placeholders**
- **Line:** 1823
- **Status:** ✅ MATCH

---

## Special Cases Handled Correctly

### 1. CFG Blocks ID Mapping (cfg_blocks_batch)
- **Tuple includes temp_id:** 7 elements in append
- **INSERT excludes temp_id:** 6 placeholders (temp_id stripped in flush_batch)
- **ID mapping logic:** Lines 1614-1627 correctly extract temp_id and map to real AUTOINCREMENT ID
- **Status:** ✅ Correct implementation

### 2. JWT Patterns Dict-Based Batch
- **Append format:** Dict with 6 keys
- **Flush conversion:** Dict values converted to tuple in _flush_jwt_patterns() at line 1221
- **Status:** ✅ Correct implementation

### 3. Optional Field Handling
- **add_config_file():** Uses `context` parameter, maps to `context_dir` column
- **add_endpoint():** Uses `controls` parameter, JSON-encoded in add method
- **Status:** ✅ Consistent naming and encoding

---

## Conclusion

**All 36 batch operations have been validated:**
- ✅ Every tuple size matches its corresponding INSERT statement placeholder count
- ✅ All JSON encoding happens in add_* methods before append
- ✅ All special cases (ID mapping, dict batches) are handled correctly
- ✅ No schema mismatches detected

**Database integrity: CONFIRMED**
