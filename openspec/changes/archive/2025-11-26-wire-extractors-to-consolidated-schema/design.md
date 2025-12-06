# Design: Wire Extractors to Consolidated Schema

## Context

### Current State (After consolidate-python-orphan-tables)

```
python_schema.py:     8 tables defined
python_storage.py:    7 handlers defined
python_impl.py:       ~150 output keys (RESTORED - not modified)
Extractors:           28 files (RESTORED - not modified)
```

### The Gap

`python_impl.py` produces ~150 output keys with no storage destination. Data is extracted then discarded.

### Polyglot Consideration

**This is Python-only.** Node/JS schema is unaffected. No orchestrator changes needed.

---

## Goals / Non-Goals

### Goals

1. Add 20 consolidated tables to `python_schema.py`
2. Add 20 storage handlers to `python_storage.py`
3. Rewire `python_impl.py` to map ~150 outputs to 28 keys
4. Preserve extractor intelligence - NO extractor code changes

### Non-Goals

1. NOT modifying extractor logic
2. NOT changing the 8 tables with verified consumers
3. NOT touching Node/JS schema
4. NOT changing orchestrator/pipeline

---

## Decisions

### Decision 1: Consolidation Strategy

**Decision: Domain-grouped tables (20 new) with discriminator columns**

**Rationale:**
- Balances granularity vs manageability
- Domain queries efficient (e.g., "all security patterns")
- Discriminator allows granular filtering
- Matches how developers think about code

### Decision 2: Discriminator Column Naming

**Decision: Domain-specific names using original extractor names as values**

**Example:** `python_loops.loop_type = 'for_loop'` (maps from `extract_for_loops`)

### Decision 3: Index Strategy

**Decision: Add composite index on (file, {discriminator}) for each table**

**Rationale:** Most queries filter by file + type

### Decision 4: Column Merging

**Decision: Normalize to common columns + JSON `details` for extras**

**Rationale:** Keeps schema clean, preserves all data

---

## Schema Definitions (20 Tables)

### Group 1: Control & Data Flow (5 Tables)

#### 1. python_loops

**File:** `theauditor/indexer/schemas/python_schema.py`

**Consolidates:**
- `extract_for_loops` (control_flow_extractors.py:93)
- `extract_while_loops` (control_flow_extractors.py:167)
- `extract_async_for_loops` (control_flow_extractors.py:219)

```sql
CREATE TABLE python_loops (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    loop_type TEXT NOT NULL,  -- 'for_loop', 'while_loop', 'async_for_loop'
    target TEXT,              -- loop variable
    iterator TEXT,            -- iterable expression
    has_else INTEGER DEFAULT 0,
    nesting_level INTEGER DEFAULT 0,
    body_line_count INTEGER
);
CREATE INDEX idx_python_loops_file ON python_loops(file);
CREATE INDEX idx_python_loops_type ON python_loops(loop_type);
```

#### 2. python_branches

**Consolidates:**
- `extract_if_statements` (control_flow_extractors.py:263)
- `extract_match_statements` (control_flow_extractors.py:343)
- `extract_exception_raises` (exception_flow_extractors.py)
- `extract_exception_catches` (exception_flow_extractors.py)
- `extract_finally_blocks` (exception_flow_extractors.py)

```sql
CREATE TABLE python_branches (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    branch_type TEXT NOT NULL,  -- 'if', 'match', 'try', 'except', 'finally', 'raise'
    condition TEXT,
    has_else INTEGER DEFAULT 0,
    elif_count INTEGER DEFAULT 0,
    case_count INTEGER DEFAULT 0,
    exception_type TEXT
);
CREATE INDEX idx_python_branches_file ON python_branches(file);
CREATE INDEX idx_python_branches_type ON python_branches(branch_type);
```

#### 3. python_functions_advanced

**Consolidates:**
- `extract_async_functions` (async_extractors.py)
- `extract_async_generators` (async_extractors.py)
- `extract_generators` (core_extractors.py)
- `extract_lambda_functions` (fundamental_extractors.py)
- `extract_context_managers` (core_extractors.py)

```sql
CREATE TABLE python_functions_advanced (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    function_type TEXT NOT NULL,  -- 'async', 'async_generator', 'generator', 'lambda', 'context_manager'
    name TEXT,
    is_method INTEGER DEFAULT 0,
    yield_count INTEGER DEFAULT 0,
    await_count INTEGER DEFAULT 0
);
CREATE INDEX idx_python_functions_advanced_file ON python_functions_advanced(file);
CREATE INDEX idx_python_functions_advanced_type ON python_functions_advanced(function_type);
```

#### 4. python_io_operations

**Consolidates:**
- `extract_io_operations` (data_flow_extractors.py)
- `extract_parameter_return_flow` (data_flow_extractors.py)
- `extract_closure_captures` (data_flow_extractors.py)
- `extract_nonlocal_access` (data_flow_extractors.py)
- `extract_conditional_calls` (data_flow_extractors.py)

```sql
CREATE TABLE python_io_operations (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    io_type TEXT NOT NULL,  -- 'file', 'network', 'database', 'process', 'param_flow', 'closure', 'nonlocal', 'conditional'
    operation TEXT,         -- 'read', 'write', 'open', 'close', etc.
    target TEXT,
    is_taint_source INTEGER DEFAULT 0,
    is_taint_sink INTEGER DEFAULT 0
);
CREATE INDEX idx_python_io_operations_file ON python_io_operations(file);
CREATE INDEX idx_python_io_operations_type ON python_io_operations(io_type);
```

#### 5. python_state_mutations

**Consolidates:**
- `extract_instance_mutations` (state_mutation_extractors.py)
- `extract_class_mutations` (state_mutation_extractors.py)
- `extract_global_mutations` (state_mutation_extractors.py)
- `extract_argument_mutations` (state_mutation_extractors.py)
- `extract_augmented_assignments` (state_mutation_extractors.py)

```sql
CREATE TABLE python_state_mutations (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    mutation_type TEXT NOT NULL,  -- 'instance', 'class', 'global', 'argument', 'augmented'
    target TEXT,
    operator TEXT,
    value_expr TEXT,
    in_function TEXT
);
CREATE INDEX idx_python_state_mutations_file ON python_state_mutations(file);
CREATE INDEX idx_python_state_mutations_type ON python_state_mutations(mutation_type);
```

---

### Group 2: Object-Oriented & Types (5 Tables)

#### 6. python_class_features

**Consolidates:**
- `extract_metaclasses` (class_feature_extractors.py)
- `extract_slots` (class_feature_extractors.py)
- `extract_abstract_classes` (class_feature_extractors.py)
- `extract_dataclasses` (class_feature_extractors.py)
- `extract_enums` (class_feature_extractors.py)
- `extract_multiple_inheritance` (class_feature_extractors.py)
- `extract_dunder_methods` (class_feature_extractors.py)
- `extract_visibility_conventions` (class_feature_extractors.py)
- `extract_method_types` (class_feature_extractors.py)

```sql
CREATE TABLE python_class_features (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    feature_type TEXT NOT NULL,  -- 'metaclass', 'slots', 'abstract', 'dataclass', 'enum', 'inheritance', 'dunder', 'visibility', 'method_type'
    class_name TEXT,
    name TEXT,
    details TEXT  -- JSON for feature-specific data
);
CREATE INDEX idx_python_class_features_file ON python_class_features(file);
CREATE INDEX idx_python_class_features_type ON python_class_features(feature_type);
```

#### 7. python_protocols

**Consolidates:**
- `extract_iterator_protocol` (protocol_extractors.py)
- `extract_container_protocol` (protocol_extractors.py)
- `extract_callable_protocol` (protocol_extractors.py)
- `extract_comparison_protocol` (protocol_extractors.py)
- `extract_arithmetic_protocol` (protocol_extractors.py)
- `extract_pickle_protocol` (protocol_extractors.py)
- `extract_context_managers_enhanced` (exception_flow_extractors.py)

```sql
CREATE TABLE python_protocols (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    protocol_type TEXT NOT NULL,  -- 'iterator', 'container', 'callable', 'comparison', 'arithmetic', 'pickle', 'context_manager'
    class_name TEXT,
    implemented_methods TEXT  -- JSON array
);
CREATE INDEX idx_python_protocols_file ON python_protocols(file);
CREATE INDEX idx_python_protocols_type ON python_protocols(protocol_type);
```

#### 8. python_descriptors

**Consolidates:**
- `extract_descriptors` (class_feature_extractors.py)
- `extract_property_patterns` (behavioral_extractors.py)
- `extract_dynamic_attributes` (behavioral_extractors.py)
- `extract_cached_property` (advanced_extractors.py)
- `extract_descriptor_protocol` (advanced_extractors.py)
- `extract_attribute_access_protocol` (advanced_extractors.py)

```sql
CREATE TABLE python_descriptors (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    descriptor_type TEXT NOT NULL,  -- 'descriptor', 'property', 'dynamic_attr', 'cached_property', 'attr_access'
    name TEXT,
    class_name TEXT,
    has_getter INTEGER DEFAULT 0,
    has_setter INTEGER DEFAULT 0,
    has_deleter INTEGER DEFAULT 0
);
CREATE INDEX idx_python_descriptors_file ON python_descriptors(file);
CREATE INDEX idx_python_descriptors_type ON python_descriptors(descriptor_type);
```

#### 9. python_type_definitions

**Consolidates:**
- `extract_typed_dicts` (type_extractors.py)
- `extract_generics` (type_extractors.py)
- `extract_protocols` (type_extractors.py)

```sql
CREATE TABLE python_type_definitions (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    type_kind TEXT NOT NULL,  -- 'typed_dict', 'generic', 'protocol'
    name TEXT,
    type_params TEXT,  -- JSON array of type parameters
    fields TEXT        -- JSON for TypedDict fields
);
CREATE INDEX idx_python_type_definitions_file ON python_type_definitions(file);
CREATE INDEX idx_python_type_definitions_kind ON python_type_definitions(type_kind);
```

#### 10. python_literals

**Consolidates:**
- `extract_literals` (type_extractors.py)
- `extract_overloads` (type_extractors.py)

```sql
CREATE TABLE python_literals (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    literal_type TEXT NOT NULL,  -- 'literal', 'overload'
    name TEXT,
    values TEXT  -- JSON array of literal values
);
CREATE INDEX idx_python_literals_file ON python_literals(file);
CREATE INDEX idx_python_literals_type ON python_literals(literal_type);
```

---

### Group 3: Security & Testing (5 Tables)

#### 11. python_security_findings

**Consolidates:**
- `extract_sql_injection_patterns` (security_extractors.py:191)
- `extract_command_injection_patterns` (security_extractors.py:255)
- `extract_path_traversal_patterns` (security_extractors.py:309)
- `extract_dangerous_eval_exec` (security_extractors.py:361)
- `extract_crypto_operations` (security_extractors.py:410)
- `extract_auth_decorators` (security_extractors.py:75)
- `extract_password_hashing` (security_extractors.py:128)
- `extract_jwt_operations` (security_extractors.py:561)

```sql
CREATE TABLE python_security_findings (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    finding_type TEXT NOT NULL,  -- 'sql_injection', 'command_injection', 'path_traversal', 'dangerous_eval', 'crypto', 'auth', 'password', 'jwt'
    severity TEXT DEFAULT 'medium',  -- 'low', 'medium', 'high', 'critical'
    source_expr TEXT,
    sink_expr TEXT,
    vulnerable_code TEXT,
    cwe_id TEXT
);
CREATE INDEX idx_python_security_findings_file ON python_security_findings(file);
CREATE INDEX idx_python_security_findings_type ON python_security_findings(finding_type);
CREATE INDEX idx_python_security_findings_severity ON python_security_findings(severity);
```

#### 12. python_test_cases

**Consolidates:**
- `extract_unittest_test_cases` (testing_extractors.py:196)
- `extract_assertion_patterns` (testing_extractors.py:256)

```sql
CREATE TABLE python_test_cases (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    test_type TEXT NOT NULL,  -- 'unittest', 'pytest', 'assertion'
    name TEXT,
    class_name TEXT,
    assertion_type TEXT,
    expected_exception TEXT
);
CREATE INDEX idx_python_test_cases_file ON python_test_cases(file);
CREATE INDEX idx_python_test_cases_type ON python_test_cases(test_type);
```

#### 13. python_test_fixtures

**Consolidates:**
- `extract_pytest_fixtures` (testing_extractors.py:30)
- `extract_pytest_parametrize` (testing_extractors.py:75)
- `extract_pytest_markers` (testing_extractors.py:113)
- `extract_mock_patterns` (testing_extractors.py:145)
- `extract_pytest_plugin_hooks` (testing_extractors.py:310)
- `extract_hypothesis_strategies` (testing_extractors.py:357)

```sql
CREATE TABLE python_test_fixtures (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    fixture_type TEXT NOT NULL,  -- 'fixture', 'parametrize', 'marker', 'mock', 'plugin_hook', 'hypothesis'
    name TEXT,
    scope TEXT,           -- 'function', 'class', 'module', 'session'
    params TEXT,          -- JSON array
    autouse INTEGER DEFAULT 0
);
CREATE INDEX idx_python_test_fixtures_file ON python_test_fixtures(file);
CREATE INDEX idx_python_test_fixtures_type ON python_test_fixtures(fixture_type);
```

#### 14. python_framework_config

**Consolidates:**
- `extract_flask_app_factories` (flask_extractors.py)
- `extract_flask_extensions` (flask_extractors.py)
- `extract_flask_request_hooks` (flask_extractors.py)
- `extract_flask_error_handlers` (flask_extractors.py)
- `extract_flask_websocket_handlers` (flask_extractors.py)
- `extract_flask_cli_commands` (flask_extractors.py)
- `extract_flask_cors_configs` (flask_extractors.py)
- `extract_flask_rate_limits` (flask_extractors.py)
- `extract_flask_cache_decorators` (flask_extractors.py)
- `extract_celery_tasks` (framework_extractors.py)
- `extract_celery_task_calls` (framework_extractors.py)
- `extract_celery_beat_schedules` (framework_extractors.py)
- `extract_django_admin` (django_web_extractors.py)
- `extract_django_signals` (django_advanced_extractors.py)
- `extract_django_receivers` (django_advanced_extractors.py)
- `extract_django_managers` (django_advanced_extractors.py)
- `extract_django_querysets` (django_advanced_extractors.py)
- `extract_django_forms` (django_web_extractors.py)
- `extract_django_form_fields` (django_web_extractors.py)

```sql
CREATE TABLE python_framework_config (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    framework TEXT NOT NULL,      -- 'flask', 'celery', 'django'
    config_type TEXT NOT NULL,    -- 'app', 'extension', 'hook', 'error_handler', 'task', 'signal', 'admin', 'form', etc.
    name TEXT,
    endpoint TEXT,
    methods TEXT,
    schedule TEXT,
    details TEXT  -- JSON for framework-specific data
);
CREATE INDEX idx_python_framework_config_file ON python_framework_config(file);
CREATE INDEX idx_python_framework_config_framework ON python_framework_config(framework);
CREATE INDEX idx_python_framework_config_type ON python_framework_config(config_type);
```

#### 15. python_validation_schemas

**Consolidates:**
- `extract_marshmallow_schemas` (validation_extractors.py)
- `extract_marshmallow_fields` (validation_extractors.py)
- `extract_drf_serializers` (validation_extractors.py)
- `extract_drf_serializer_fields` (validation_extractors.py)
- `extract_wtforms_forms` (validation_extractors.py)
- `extract_wtforms_fields` (validation_extractors.py)

```sql
CREATE TABLE python_validation_schemas (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    framework TEXT NOT NULL,     -- 'marshmallow', 'drf', 'wtforms'
    schema_type TEXT NOT NULL,   -- 'schema', 'field', 'serializer', 'form'
    name TEXT,
    field_type TEXT,
    validators TEXT,  -- JSON array
    required INTEGER DEFAULT 0
);
CREATE INDEX idx_python_validation_schemas_file ON python_validation_schemas(file);
CREATE INDEX idx_python_validation_schemas_framework ON python_validation_schemas(framework);
```

---

### Group 4: Low-Level & Misc (5 Tables)

#### 16. python_operators

**Consolidates:**
- `extract_operators` (operator_extractors.py)
- `extract_membership_tests` (operator_extractors.py)
- `extract_chained_comparisons` (operator_extractors.py)
- `extract_ternary_expressions` (operator_extractors.py)
- `extract_walrus_operators` (operator_extractors.py)
- `extract_matrix_multiplication` (operator_extractors.py)

```sql
CREATE TABLE python_operators (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    operator_type TEXT NOT NULL,  -- 'binary', 'unary', 'membership', 'chained', 'ternary', 'walrus', 'matmul'
    operator TEXT,
    left_operand TEXT,
    right_operand TEXT
);
CREATE INDEX idx_python_operators_file ON python_operators(file);
CREATE INDEX idx_python_operators_type ON python_operators(operator_type);
```

#### 17. python_collections

**Consolidates:**
- `extract_dict_operations` (collection_extractors.py)
- `extract_list_mutations` (collection_extractors.py)
- `extract_set_operations` (collection_extractors.py)
- `extract_string_methods` (collection_extractors.py)
- `extract_builtin_usage` (collection_extractors.py)
- `extract_itertools_usage` (collection_extractors.py)
- `extract_functools_usage` (collection_extractors.py)
- `extract_collections_usage` (collection_extractors.py)

```sql
CREATE TABLE python_collections (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    collection_type TEXT NOT NULL,  -- 'dict', 'list', 'set', 'string', 'builtin', 'itertools', 'functools', 'collections'
    operation TEXT,
    method TEXT
);
CREATE INDEX idx_python_collections_file ON python_collections(file);
CREATE INDEX idx_python_collections_type ON python_collections(collection_type);
```

#### 18. python_stdlib_usage

**Consolidates:**
- `extract_regex_patterns` (stdlib_pattern_extractors.py)
- `extract_json_operations` (stdlib_pattern_extractors.py)
- `extract_datetime_operations` (stdlib_pattern_extractors.py)
- `extract_path_operations` (stdlib_pattern_extractors.py)
- `extract_logging_patterns` (stdlib_pattern_extractors.py)
- `extract_threading_patterns` (stdlib_pattern_extractors.py)
- `extract_contextlib_patterns` (stdlib_pattern_extractors.py)
- `extract_type_checking` (stdlib_pattern_extractors.py)
- `extract_weakref_usage` (protocol_extractors.py)
- `extract_contextvar_usage` (protocol_extractors.py)

```sql
CREATE TABLE python_stdlib_usage (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    module TEXT NOT NULL,         -- 're', 'json', 'datetime', 'pathlib', 'logging', 'threading', 'contextlib', 'typing', 'weakref', 'contextvars'
    usage_type TEXT NOT NULL,     -- 'pattern', 'operation', 'call'
    function_name TEXT,
    pattern TEXT
);
CREATE INDEX idx_python_stdlib_usage_file ON python_stdlib_usage(file);
CREATE INDEX idx_python_stdlib_usage_module ON python_stdlib_usage(module);
```

#### 19. python_imports_advanced

**Consolidates:**
- `extract_import_statements` (control_flow_extractors.py:580)
- `extract_namespace_packages` (advanced_extractors.py)
- `extract_module_attributes` (protocol_extractors.py)

```sql
CREATE TABLE python_imports_advanced (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    import_type TEXT NOT NULL,  -- 'static', 'dynamic', 'namespace', 'module_attr'
    module TEXT,
    name TEXT,
    alias TEXT,
    is_relative INTEGER DEFAULT 0
);
CREATE INDEX idx_python_imports_advanced_file ON python_imports_advanced(file);
CREATE INDEX idx_python_imports_advanced_type ON python_imports_advanced(import_type);
```

#### 20. python_expressions

**Consolidates:**
- `extract_comprehensions` (fundamental_extractors.py)
- `extract_slice_operations` (fundamental_extractors.py)
- `extract_tuple_operations` (fundamental_extractors.py)
- `extract_unpacking_patterns` (fundamental_extractors.py)
- `extract_none_patterns` (fundamental_extractors.py)
- `extract_truthiness_patterns` (fundamental_extractors.py)
- `extract_string_formatting` (fundamental_extractors.py)
- `extract_ellipsis_usage` (advanced_extractors.py)
- `extract_bytes_operations` (advanced_extractors.py)
- `extract_exec_eval_compile` (advanced_extractors.py)
- `extract_copy_protocol` (advanced_extractors.py)
- `extract_recursion_patterns` (behavioral_extractors.py)
- `extract_generator_yields` (behavioral_extractors.py)
- `extract_loop_complexity` (performance_extractors.py)
- `extract_resource_usage` (performance_extractors.py)
- `extract_memoization_patterns` (performance_extractors.py)
- `extract_await_expressions` (async_extractors.py)
- `extract_break_continue_pass` (control_flow_extractors.py:416)
- `extract_assert_statements` (control_flow_extractors.py:477)
- `extract_del_statements` (control_flow_extractors.py:530)
- `extract_with_statements` (control_flow_extractors.py:631)
- `extract_class_decorators` (protocol_extractors.py)

```sql
CREATE TABLE python_expressions (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    expression_type TEXT NOT NULL,  -- 'comprehension', 'slice', 'tuple', 'unpack', 'none', 'truthiness', 'format', 'ellipsis', 'bytes', 'exec', 'copy', 'recursion', 'yield', 'complexity', 'resource', 'memoize', 'await', 'break', 'continue', 'pass', 'assert', 'del', 'with', 'class_decorator'
    subtype TEXT,                   -- For comprehensions: 'list', 'dict', 'set', 'generator'
    expression TEXT,
    variables TEXT
);
CREATE INDEX idx_python_expressions_file ON python_expressions(file);
CREATE INDEX idx_python_expressions_type ON python_expressions(expression_type);
```

---

## Complete Extractor → Table Mapping

### Mapping Reference

| Extractor File | Function | Line | → Table | Discriminator Value |
|---------------|----------|------|---------|---------------------|
| control_flow_extractors.py | extract_for_loops | 93 | python_loops | 'for_loop' |
| control_flow_extractors.py | extract_while_loops | 167 | python_loops | 'while_loop' |
| control_flow_extractors.py | extract_async_for_loops | 219 | python_loops | 'async_for_loop' |
| control_flow_extractors.py | extract_if_statements | 263 | python_branches | 'if' |
| control_flow_extractors.py | extract_match_statements | 343 | python_branches | 'match' |
| control_flow_extractors.py | extract_break_continue_pass | 416 | python_expressions | 'break'/'continue'/'pass' |
| control_flow_extractors.py | extract_assert_statements | 477 | python_expressions | 'assert' |
| control_flow_extractors.py | extract_del_statements | 530 | python_expressions | 'del' |
| control_flow_extractors.py | extract_import_statements | 580 | python_imports_advanced | 'static' |
| control_flow_extractors.py | extract_with_statements | 631 | python_expressions | 'with' |
| security_extractors.py | extract_auth_decorators | 75 | python_security_findings | 'auth' |
| security_extractors.py | extract_password_hashing | 128 | python_security_findings | 'password' |
| security_extractors.py | extract_sql_injection_patterns | 191 | python_security_findings | 'sql_injection' |
| security_extractors.py | extract_command_injection_patterns | 255 | python_security_findings | 'command_injection' |
| security_extractors.py | extract_path_traversal_patterns | 309 | python_security_findings | 'path_traversal' |
| security_extractors.py | extract_dangerous_eval_exec | 361 | python_security_findings | 'dangerous_eval' |
| security_extractors.py | extract_crypto_operations | 410 | python_security_findings | 'crypto' |
| security_extractors.py | extract_jwt_operations | 561 | python_security_findings | 'jwt' |
| testing_extractors.py | extract_pytest_fixtures | 30 | python_test_fixtures | 'fixture' |
| testing_extractors.py | extract_pytest_parametrize | 75 | python_test_fixtures | 'parametrize' |
| testing_extractors.py | extract_pytest_markers | 113 | python_test_fixtures | 'marker' |
| testing_extractors.py | extract_mock_patterns | 145 | python_test_fixtures | 'mock' |
| testing_extractors.py | extract_unittest_test_cases | 196 | python_test_cases | 'unittest' |
| testing_extractors.py | extract_assertion_patterns | 256 | python_test_cases | 'assertion' |
| testing_extractors.py | extract_pytest_plugin_hooks | 310 | python_test_fixtures | 'plugin_hook' |
| testing_extractors.py | extract_hypothesis_strategies | 357 | python_test_fixtures | 'hypothesis' |

*(Full mapping continues in tasks.md)*

---

## Risks / Trade-offs

### Risk 1: Query Migration

**Risk:** Old table names won't work
**Likelihood:** LOW (no verified consumers for orphan tables)
**Mitigation:** Discriminator allows equivalent queries

### Risk 2: Storage Handler Complexity

**Risk:** Single handler handles multiple types
**Likelihood:** MEDIUM
**Mitigation:** Clear mapping dict in each handler

### Risk 3: Performance

**Risk:** Larger tables slower to query
**Likelihood:** LOW (indexed on discriminator)
**Mitigation:** Composite indexes on (file, {type})
