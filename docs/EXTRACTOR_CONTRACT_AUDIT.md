# Extractor Return Structure vs Storage Contract Audit

**Date:** 2025-10-03
**Auditor:** System Architecture Analysis
**Scope:** All extractors in `theauditor/indexer/extractors/` vs `_store_extracted_data()` in `theauditor/indexer/__init__.py`

## Executive Summary

This audit documents the **contract mismatches** between what extractors return and what the storage layer expects. These mismatches can cause:
- Silent data loss (fields ignored)
- Runtime errors (missing required fields)
- Type errors (tuples vs dicts)
- Database inconsistencies

**Critical Finding:** `add_ref()` expects **3 parameters** (src, kind, value) but extractors return **3-tuple with line number**, creating a **MISMATCH** that's handled by a workaround in `_store_extracted_data()`.

---

## Contract Analysis by Data Type

### 1. IMPORTS/REFS (`imports` key)

#### Extractor Returns:
**PythonExtractor** (lines 267-308):
```python
# Returns list of 3-tuples:
[('import', 'module_name', line_number), ...]
# Example: ('import', 'os', 15)
# Example: ('from', 'pathlib', 23)
```

**JavaScriptExtractor** (lines 116-127):
```python
# Returns list of 3-tuples:
[(kind, module, line), ...]
# kind = 'import' or 'require'
# Example: ('import', 'express', 42)
```

**SQLExtractor**: No imports returned
**DockerExtractor**: No imports returned
**GenericExtractor**: No imports returned
**JsonConfigExtractor**: No imports returned
**PrismaExtractor**: No imports returned

#### Storage Expects:
`_store_extracted_data()` lines 595-612:
```python
for import_tuple in extracted['imports']:
    # Handle both 2-tuple (kind, value) and 3-tuple (kind, value, line) formats
    if len(import_tuple) == 3:
        kind, value, line = import_tuple
    else:
        kind, value = import_tuple
        line = None
```

**Database Method:** `add_ref(src, kind, value)` (line 1045-1047)
```python
def add_ref(self, src: str, kind: str, value: str):
    """Add a reference record to the batch."""
    self.refs_batch.append((src, kind, value))
```

#### ❌ CRITICAL MISMATCH:
- **Extractors return:** 3-tuple `(kind, module, line)`
- **Storage calls:** `add_ref(file_path, kind, resolved, line)` with **4 arguments**
- **Database method expects:** `add_ref(src, kind, value)` with **3 arguments**

**Root Cause:** Line 611 calls `add_ref()` with 4 parameters, but method signature only takes 3!

```python
# Line 611 in _store_extracted_data():
self.db_manager.add_ref(file_path, kind, resolved, line)  # ❌ 4 args

# But add_ref() signature (line 1045):
def add_ref(self, src: str, kind: str, value: str):  # ✅ 3 params only!
```

**Impact:** Line numbers for imports are being **silently dropped** or causing errors.

---

### 2. ROUTES/API_ENDPOINTS (`routes` key)

#### Extractor Returns:

**PythonExtractor** (lines 176-265):
```python
# Returns list of dictionaries with 7 fields:
[{
    'line': int,
    'method': str,           # HTTP method (GET, POST, etc.)
    'pattern': str,          # Route pattern
    'path': str,             # File path
    'has_auth': bool,        # Auth decorator detected
    'handler_function': str, # Handler name
    'controls': list         # Non-route decorators
}, ...]
```

**JavaScriptExtractor** (lines 766-871):
```python
# Returns list of dictionaries with 8 fields:
[{
    'file': str,            # File path
    'line': int,
    'method': str,
    'pattern': str,
    'path': str,
    'has_auth': bool,
    'handler_function': str,
    'controls': list
}, ...]
```

**Other extractors:** No routes returned

#### Storage Expects:
`_store_extracted_data()` lines 614-633:
```python
if isinstance(route, dict):
    self.db_manager.add_endpoint(
        file_path=file_path,
        method=route.get('method', 'GET'),
        pattern=route.get('pattern', ''),
        controls=route.get('controls', []),
        line=route.get('line'),
        path=route.get('path'),
        has_auth=route.get('has_auth', False),
        handler_function=route.get('handler_function')
    )
```

**Database Method:** `add_endpoint()` (lines 1049-1055)
```python
def add_endpoint(self, file_path: str, method: str, pattern: str, controls: List[str],
                 line: Optional[int] = None, path: Optional[str] = None,
                 has_auth: bool = False, handler_function: Optional[str] = None):
    controls_json = json.dumps(controls) if controls else "[]"
    self.endpoints_batch.append((file_path, line, method, pattern, path,
                                controls_json, has_auth, handler_function))
```

#### ✅ MATCH (with minor redundancy):
- PythonExtractor returns 7 fields, all expected by storage
- JavaScriptExtractor returns 8 fields (includes redundant 'file' key), all expected
- Storage properly handles dictionary format

**Minor Issue:** JavaScriptExtractor includes both `'file'` and `'path'` keys (redundant).

---

### 3. SQL_QUERIES (`sql_queries` key)

#### Extractor Returns:

**PythonExtractor** (lines 343-455):
```python
# Returns list of dictionaries with 5 fields:
[{
    'line': int,
    'query_text': str,         # SQL query (max 1000 chars)
    'command': str,            # SELECT, INSERT, UPDATE, DELETE, etc.
    'tables': list,            # List of table names
    'extraction_source': str   # 'code_execute', 'orm_query', 'migration_file'
}, ...]
```

**JavaScriptExtractor** (lines 654-764):
```python
# Returns list of dictionaries with 5 fields (same structure):
[{
    'line': int,
    'query_text': str,
    'command': str,
    'tables': list,
    'extraction_source': str
}, ...]
```

**SQLExtractor** (lines 21-46):
```python
# Returns EMPTY list (no sql_queries extraction):
result['sql_queries'] = []
# Only extracts 'sql_objects' for DDL statements
```

#### Storage Expects:
`_store_extracted_data()` lines 641-649:
```python
for query in extracted['sql_queries']:
    self.db_manager.add_sql_query(
        file_path, query['line'], query['query_text'],
        query['command'], query['tables'],
        query.get('extraction_source', 'code_execute')  # Phase 3B: source tagging
    )
```

**Database Method:** `add_sql_query()` (lines 1061-1076)
```python
def add_sql_query(self, file_path: str, line: int, query_text: str, command: str, tables: List[str],
                  extraction_source: str = 'code_execute'):
    tables_json = json.dumps(tables) if tables else "[]"
    # Expects tables as a LIST
```

#### ✅ MATCH:
- Both Python and JavaScript extractors return the exact structure expected
- All 5 fields present and correct types
- `extraction_source` has proper default handling

---

### 4. SYMBOLS (`symbols` key)

#### Extractor Returns:

**PythonExtractor** (lines 66-106):
```python
# Returns list of dictionaries with 4-5 fields:
[{
    'name': str,
    'type': str,      # 'function', 'class', 'call', 'property'
    'line': int,
    'end_line': int,  # ⚠️ Only for functions (optional)
    'col': int
}, ...]
```

**JavaScriptExtractor** (lines 133-197):
```python
# Returns list of dictionaries with 4 fields:
[{
    'name': str,
    'type': str,  # 'function', 'class', 'call', 'property'
    'line': int,
    'col': int
}, ...]
```

**Other extractors:** Return empty lists or no symbols key

#### Storage Expects:
`_store_extracted_data()` lines 651-658:
```python
for symbol in extracted['symbols']:
    self.db_manager.add_symbol(
        file_path, symbol['name'], symbol['type'],
        symbol['line'], symbol['col']
    )
```

**Database Method:** (not shown in excerpt, but expects 5 params based on call)

#### ⚠️ MINOR MISMATCH:
- **PythonExtractor** includes `end_line` field for functions (line 74)
- **Storage** does NOT extract or store `end_line`
- **Impact:** `end_line` data is silently ignored for Python functions

---

### 5. ASSIGNMENTS (`assignments` key)

#### Extractor Returns:

**PythonExtractor** (lines 109-117):
```python
# Returns list of dictionaries with 5 fields:
[{
    'line': int,
    'target_var': str,
    'source_expr': str,
    'source_vars': list,  # List of variable names
    'in_function': str
}, ...]
```

**JavaScriptExtractor** (lines 200-204):
```python
# Returns assignments from ast_parser (same structure)
# Assumed same 5 fields based on Python pattern
```

#### Storage Expects:
`_store_extracted_data()` lines 708-721:
```python
for assignment in extracted['assignments']:
    self.db_manager.add_assignment(
        file_path, assignment['line'], assignment['target_var'],
        assignment['source_expr'], assignment['source_vars'],
        assignment['in_function']
    )
```

**Database Method:** `add_assignment()` (lines 1097-1102)
```python
def add_assignment(self, file_path: str, line: int, target_var: str, source_expr: str,
                  source_vars: List[str], in_function: str):
    source_vars_json = json.dumps(source_vars)  # ✅ Expects LIST
```

#### ✅ MATCH:
- Extractor returns all 5 required fields
- `source_vars` is a list as expected
- Types match perfectly

---

### 6. FUNCTION_CALLS (`function_calls` key)

#### Extractor Returns:

**PythonExtractor** (lines 119-129):
```python
# Returns list of dictionaries with 6 fields:
[{
    'line': int,
    'caller_function': str,
    'callee_function': str,
    'argument_index': int,
    'argument_expr': str,
    'param_name': str
}, ...]
```

**JavaScriptExtractor** (lines 207-211):
```python
# Returns function_calls from ast_parser (same structure)
# Assumed same 6 fields
```

#### Storage Expects:
`_store_extracted_data()` lines 723-752:
```python
for call in extracted['function_calls']:
    callee = call['callee_function']

    # JWT Categorization Enhancement (lines 728-745)
    # Modifies callee_function based on JWT patterns

    self.db_manager.add_function_call_arg(
        file_path, call['line'], call['caller_function'],
        call['callee_function'], call['argument_index'],
        call['argument_expr'], call['param_name']
    )
```

**Database Method:** `add_function_call_arg()` (lines 1104-1108)
```python
def add_function_call_arg(self, file_path: str, line: int, caller_function: str,
                          callee_function: str, arg_index: int, arg_expr: str, param_name: str):
    self.function_call_args_batch.append((file_path, line, caller_function, callee_function,
                                         arg_index, arg_expr, param_name))
```

#### ✅ MATCH:
- Extractor returns all 6 required fields
- Field names match exactly
- Types match perfectly

---

### 7. RETURNS (`returns` key)

#### Extractor Returns:

**PythonExtractor** (lines 131-139):
```python
# Returns list of dictionaries with 4 fields:
[{
    'line': int,
    'function_name': str,
    'return_expr': str,
    'return_vars': list  # List of variable names
}, ...]
```

**JavaScriptExtractor** (lines 214-218):
```python
# Returns returns from ast_parser (same structure)
```

#### Storage Expects:
`_store_extracted_data()` lines 754-760:
```python
for ret in extracted['returns']:
    self.db_manager.add_function_return(
        file_path, ret['line'], ret['function_name'],
        ret['return_expr'], ret['return_vars']
    )
```

**Database Method:** `add_function_return()` (lines 1110-1115)
```python
def add_function_return(self, file_path: str, line: int, function_name: str,
                       return_expr: str, return_vars: List[str]):
    return_vars_json = json.dumps(return_vars)  # ✅ Expects LIST
```

#### ✅ MATCH:
- All 4 fields present and correct
- `return_vars` is a list as expected

---

### 8. VARIABLE_USAGE (`variable_usage` key)

#### Extractor Returns:

**PythonExtractor** (lines 457-611):
```python
# Returns list of dictionaries with 6 fields:
[{
    'line': int,
    'variable_name': str,
    'usage_type': str,     # 'read', 'write', 'delete', 'augmented_write', 'param', 'call'
    'in_component': str,   # Function/class name or 'global'
    'in_hook': str,        # Empty for Python (React concept)
    'scope_level': int     # 0=global, 1=function, 2=nested
}, ...]
```

**JavaScriptExtractor** (lines 508-538):
```python
# Returns list of dictionaries with 6 fields:
[{
    'line': int,
    'variable_name': str,
    'usage_type': str,    # 'write', 'read', 'call'
    'in_component': str,
    'in_hook': str,
    'scope_level': int
}, ...]
```

#### Storage Expects:
`_store_extracted_data()` lines 920-931:
```python
for var in extracted['variable_usage']:
    self.db_manager.add_variable_usage(
        file_path,
        var['line'],
        var['variable_name'],
        var['usage_type'],
        var.get('in_component'),
        var.get('in_hook'),
        var.get('scope_level', 0)
    )
```

#### ✅ MATCH:
- All 6 fields present
- Proper default handling for optional fields

---

### 9. CFG (Control Flow Graph) (`cfg` key)

#### Extractor Returns:

**PythonExtractor** (lines 142-143):
```python
# Returns CFG from ast_parser:
result['cfg'] = self.ast_parser.extract_cfg(tree)
# Structure: list of function CFGs
```

**JavaScriptExtractor** (lines 221-223):
```python
# Returns CFG from ast_parser (same)
```

#### Storage Expects:
`_store_extracted_data()` lines 762-811:
```python
for function_cfg in extracted['cfg']:
    # Expects each function_cfg to have:
    {
        'function_name': str,
        'blocks': [{
            'id': str,              # Temporary ID
            'type': str,
            'start_line': int,
            'end_line': int,
            'condition': str,       # Optional
            'statements': [{
                'type': str,
                'line': int,
                'text': str         # Optional
            }, ...]
        }, ...],
        'edges': [{
            'source': str,  # Block ID
            'target': str,  # Block ID
            'type': str
        }, ...]
    }
```

#### ✅ MATCH (assumed):
- Complex nested structure
- Proper ID mapping for blocks
- Statement storage implemented

---

### 10. DOCKER_INFO (`docker_info` key)

#### Extractor Returns:

**DockerExtractor** (lines 55-151):
```python
# Returns EMPTY DICT (direct database writes)
# NO docker_info key returned
# Uses: self.db_manager.add_docker_image(...) directly
```

#### Storage Expects:
`_store_extracted_data()` lines 690-698:
```python
if 'docker_info' in extracted and extracted['docker_info']:
    info = extracted['docker_info']
    self.db_manager.add_docker_image(
        file_path, info.get('base_image'), info.get('exposed_ports', []),
        info.get('env_vars', {}), info.get('build_args', {}),
        info.get('user'), info.get('has_healthcheck', False)
    )
```

#### ❌ CRITICAL MISMATCH:
- **DockerExtractor** does NOT return `docker_info` key (writes directly to DB)
- **Storage** expects `docker_info` dict with 6 fields
- **Impact:** Docker data is stored TWICE (once by extractor, once by storage) OR not at all depending on flow

**Recommendation:** DockerExtractor should return empty dict `{}` (which it does), and storage code is DEAD CODE.

---

### 11. CONFIG_DATA (Generic Configs)

#### Extractor Returns:

**GenericExtractor** (lines 96-135):
```python
# Returns minimal dict (direct database writes):
return {
    'imports': [],
    'routes': [],
    'sql_queries': [],
    'symbols': []
}
# NO 'config_data' key
# Uses self.db_manager.add_compose_service() directly
# Uses self.db_manager.add_nginx_config() directly
# Uses self.db_manager.add_package_config() directly
```

#### Storage Expects:
NO storage code for `config_data` key in `_store_extracted_data()`

#### ✅ MATCH:
- GenericExtractor uses database-first pattern (direct writes)
- Storage layer doesn't expect `config_data`
- Clean architecture

---

### 12. PACKAGE_CONFIGS & LOCK_ANALYSIS

#### Extractor Returns:

**JsonConfigExtractor** (lines 56-72):
```python
result = {
    'package_configs': [{
        'file_path': str,
        'package_name': str,
        'version': str,
        'dependencies': dict,
        'dev_dependencies': dict,
        'peer_dependencies': dict,
        'scripts': dict,
        'engines': dict,
        'workspaces': list,
        'is_private': bool
    }],
    'lock_analysis': [{
        'file_path': str,
        'lock_type': str,              # 'npm', 'yarn', 'pnpm'
        'package_manager_version': str,
        'total_packages': int,
        'duplicate_packages': dict,
        'lock_file_version': str
    }]
}
```

#### Storage Expects:
`_store_extracted_data()` lines 933-962:
```python
if 'package_configs' in extracted:
    for pkg_config in extracted['package_configs']:
        self.db_manager.add_package_config(
            pkg_config['file_path'],      # ✅
            pkg_config['package_name'],   # ✅
            pkg_config['version'],        # ✅
            pkg_config.get('dependencies'),      # ✅
            pkg_config.get('dev_dependencies'),  # ✅
            pkg_config.get('peer_dependencies'), # ✅
            pkg_config.get('scripts'),           # ✅
            pkg_config.get('engines'),           # ✅
            pkg_config.get('workspaces'),        # ✅
            pkg_config.get('is_private', False)  # ✅
        )

if 'lock_analysis' in extracted:
    for lock in extracted['lock_analysis']:
        self.db_manager.add_lock_analysis(
            lock['file_path'],                    # ✅
            lock['lock_type'],                    # ✅
            lock.get('package_manager_version'),  # ✅
            lock['total_packages'],               # ✅
            lock.get('duplicate_packages'),       # ✅
            lock.get('lock_file_version')         # ✅
        )
```

#### ✅ MATCH:
- All fields present and properly typed
- Good use of `.get()` for optional fields

---

### 13. REACT & VUE FRAMEWORK DATA

#### Extractor Returns:

**JavaScriptExtractor** (lines 228-411):
```python
result = {
    'react_components': [{
        'name': str,
        'type': str,           # 'function' or 'class'
        'start_line': int,
        'end_line': int,
        'has_jsx': bool,
        'hooks_used': list,    # List of hook names
        'props_type': str      # Optional
    }],
    'react_hooks': [{
        'line': int,
        'component_name': str,
        'hook_name': str,
        'hook_type': str,            # 'builtin' or 'custom'
        'dependency_array': str,     # Optional
        'dependency_vars': list,     # Optional
        'callback_body': str,        # Optional
        'has_cleanup': bool,
        'cleanup_type': str          # Optional
    }],
    'vue_components': [{
        'name': str,
        'type': str,
        'start_line': int,
        'end_line': int,
        'has_template': bool,
        'has_style': bool,
        'composition_api_used': bool,
        'props_definition': str,     # Optional
        'emits_definition': str,     # Optional
        'setup_return': str          # Optional
    }],
    # ... vue_hooks, vue_directives, vue_provide_inject
}
```

#### Storage Expects:
`_store_extracted_data()` lines 827-918:
```python
# React Components
for component in extracted['react_components']:
    self.db_manager.add_react_component(
        file_path,
        component['name'],              # ✅
        component['type'],              # ✅
        component['start_line'],        # ✅
        component['end_line'],          # ✅
        component['has_jsx'],           # ✅
        component.get('hooks_used'),    # ✅
        component.get('props_type')     # ✅
    )

# React Hooks
for hook in extracted['react_hooks']:
    self.db_manager.add_react_hook(
        file_path,
        hook['line'],                          # ✅
        hook['component_name'],                # ✅
        hook['hook_name'],                     # ✅
        hook.get('dependency_array'),          # ✅
        hook.get('dependency_vars'),           # ✅
        hook.get('callback_body'),             # ✅
        hook.get('has_cleanup', False),        # ✅
        hook.get('cleanup_type')               # ✅
    )

# Similar for Vue components, hooks, directives, provide/inject
```

#### ✅ MATCH:
- All React/Vue fields properly mapped
- Good use of `.get()` for optional fields

---

### 14. TYPE_ANNOTATIONS (TypeScript)

#### Extractor Returns:

**JavaScriptExtractor** (lines 493-504):
```python
result['type_annotations'] = [{
    'line': int,
    'symbol_name': str,
    'annotation_type': str,  # 'return'
    'type_text': str         # Return type
}]
```

#### Storage Expects:
`_store_extracted_data()` lines 660-678:
```python
for annotation in extracted['type_annotations']:
    self.db_manager.add_type_annotation(
        file_path,
        annotation.get('line', 0),                           # ✅
        annotation.get('column', 0),                         # ❌ NOT in extractor
        annotation.get('symbol_name', ''),                   # ✅
        annotation.get('annotation_type',
                      annotation.get('symbol_kind', 'unknown')), # ✅
        annotation.get('type_annotation',
                      annotation.get('type_text', '')),      # ✅ (aliased)
        annotation.get('is_any', False),                     # ❌ NOT in extractor
        annotation.get('is_unknown', False),                 # ❌ NOT in extractor
        annotation.get('is_generic', False),                 # ❌ NOT in extractor
        annotation.get('has_type_params', False),            # ❌ NOT in extractor
        annotation.get('type_params'),                       # ❌ NOT in extractor
        annotation.get('return_type'),                       # ❌ NOT in extractor
        annotation.get('extends_type')                       # ❌ NOT in extractor
    )
```

#### ⚠️ MAJOR MISMATCH:
- **Extractor returns:** 4 fields (line, symbol_name, annotation_type, type_text)
- **Storage expects:** 13 fields!
- **Missing fields:** column, is_any, is_unknown, is_generic, has_type_params, type_params, return_type, extends_type
- **Impact:** Type annotations stored with mostly NULL/FALSE values, incomplete semantic analysis

---

### 15. JWT_PATTERNS

#### Extractor Returns:

**PythonExtractor** (line 167):
```python
result['jwt_patterns'] = self.extract_jwt_patterns(content)
# From BaseExtractor - structure unknown but assumed:
[{
    'line': int,
    'type': str,
    'full_match': str,      # Optional
    'secret_type': str,     # Optional
    'algorithm': str        # Optional
}]
```

**JavaScriptExtractor** (lines 488-490):
```python
jwt_patterns = self.extract_jwt_patterns(content)  # BaseExtractor method
if jwt_patterns:
    result['jwt_patterns'] = jwt_patterns
```

#### Storage Expects:
`_store_extracted_data()` lines 813-825:
```python
for pattern in extracted['jwt_patterns']:
    self.db_manager.add_jwt_pattern(
        file_path=file_path,
        line_number=pattern['line'],                # ✅
        pattern_type=pattern['type'],               # ✅
        pattern_text=pattern.get('full_match', ''), # ✅
        secret_source=pattern.get('secret_type', 'unknown'), # ✅
        algorithm=pattern.get('algorithm')          # ✅
    )
```

#### ✅ MATCH (assumed):
- All fields appear to be present
- Need to verify BaseExtractor.extract_jwt_patterns() implementation

---

### 16. ORM_QUERIES

#### Extractor Returns:

**JavaScriptExtractor** (lines 413-473):
```python
result['orm_queries'] = [{
    'line': int,
    'query_type': str,      # Full callee_function or method name
    'includes': str,        # 'has_includes', 'has_relations', or None
    'has_limit': bool,
    'has_transaction': bool
}]
```

#### Storage Expects:
`_store_extracted_data()` lines 680-688:
```python
for query in extracted['orm_queries']:
    self.db_manager.add_orm_query(
        file_path, query['line'], query['query_type'],
        query.get('includes'), query.get('has_limit', False),
        query.get('has_transaction', False)
    )
```

#### ✅ MATCH:
- All 5 fields present and correct

---

### 17. IMPORT_STYLES

#### Extractor Returns:

**JavaScriptExtractor** (lines 551-614):
```python
result['import_styles'] = [{
    'line': int,
    'package': str,
    'import_style': str,      # 'namespace', 'named', 'default', 'side-effect'
    'imported_names': list,   # Optional
    'alias_name': str,        # Optional
    'full_statement': str     # Optional (max 200 chars)
}]
```

#### Storage Expects:
`_store_extracted_data()` lines 964-977:
```python
for import_style in extracted['import_styles']:
    self.db_manager.add_import_style(
        file_path,
        import_style['line'],                      # ✅
        import_style['package'],                   # ✅
        import_style['import_style'],              # ✅
        import_style.get('imported_names'),        # ✅
        import_style.get('alias_name'),            # ✅
        import_style.get('full_statement')         # ✅
    )
```

#### ✅ MATCH:
- All 6 fields properly mapped

---

## Critical Issues Summary

### P0 - CRITICAL (Must Fix)

1. **IMPORTS/REFS Line Number Handling** (`add_ref()` signature mismatch)
   - **File:** `theauditor/indexer/database.py`, line 1045
   - **Issue:** `add_ref()` expects 3 params, but called with 4 (file_path, kind, resolved, line)
   - **Impact:** Runtime error OR line numbers silently dropped
   - **Fix:** Update `add_ref()` signature to accept line parameter OR change storage call

2. **TYPE_ANNOTATIONS Incomplete Fields**
   - **File:** `theauditor/indexer/extractors/javascript.py`, lines 493-504
   - **Issue:** Extractor returns 4 fields, storage expects 13
   - **Impact:** Type analysis severely incomplete, 9 fields always NULL/FALSE
   - **Fix:** Enhance JavaScript extractor to extract all type annotation fields

### P1 - HIGH (Should Fix)

3. **DOCKER_INFO Dead Code**
   - **File:** `theauditor/indexer/__init__.py`, lines 690-698
   - **Issue:** Storage expects `docker_info` key, but DockerExtractor uses direct DB writes
   - **Impact:** Dead code, potential confusion
   - **Fix:** Remove docker_info handling from storage OR refactor DockerExtractor

4. **SYMBOLS end_line Ignored**
   - **File:** Python extractor includes `end_line` for functions, storage doesn't use it
   - **Impact:** Function span data lost
   - **Fix:** Update storage to extract and store `end_line` for symbols

### P2 - MEDIUM (Nice to Have)

5. **ROUTES Redundant Field**
   - **File:** `theauditor/indexer/extractors/javascript.py`, line 829
   - **Issue:** JavaScriptExtractor returns both 'file' and 'path' keys (redundant)
   - **Impact:** Minor inefficiency
   - **Fix:** Remove 'file' key from routes dictionaries

---

## Recommendations

### Immediate Actions:

1. **Fix `add_ref()` signature** to handle line numbers:
   ```python
   def add_ref(self, src: str, kind: str, value: str, line: Optional[int] = None):
       """Add a reference record to the batch."""
       self.refs_batch.append((src, kind, value, line))
   ```

2. **Enhance type annotation extraction** in JavaScriptExtractor to include all 13 fields expected by storage

3. **Remove dead docker_info code** from `_store_extracted_data()` or document that it's deprecated

### Long-term Improvements:

1. **Create contract tests** to validate extractor return structures match storage expectations
2. **Document extractor contracts** with TypedDict or dataclasses for type safety
3. **Implement schema validation** at extractor-storage boundary
4. **Add integration tests** that verify end-to-end data flow for each extractor

---

## Testing Checklist

For each extractor, verify:

- [ ] PythonExtractor: imports line numbers stored correctly
- [ ] JavaScriptExtractor: imports line numbers stored correctly
- [ ] JavaScriptExtractor: type annotations have all 13 fields
- [ ] DockerExtractor: no duplicate docker_info writes
- [ ] PythonExtractor: symbol end_line preserved
- [ ] All extractors: run with THEAUDITOR_DEBUG=1 and verify no errors
- [ ] All extractors: query database after indexing and verify data completeness

---

**End of Audit Report**
