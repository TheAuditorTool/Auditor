# Appendix: Implementation Details

**Purpose**: Copy-paste ready artifacts for implementation. Zero detective work.

---

## 1. Complete DDL for New Tables

### 1.1 python_comprehensions (NEW)

```sql
CREATE TABLE python_comprehensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,

    -- Discriminators (two-column pattern)
    comp_kind TEXT NOT NULL,              -- 'list', 'dict', 'set', 'generator'
    comp_type TEXT,                       -- Extractor's subtype (preserved)

    -- From extract_comprehensions (extractor_truth.txt line 746)
    -- KEYS: ['comp_type', 'filter_expr', 'has_filter', 'in_function', 'iteration_source', 'iteration_var', 'line', 'nesting_level', 'result_expr']
    iteration_var TEXT,
    iteration_source TEXT,
    result_expr TEXT,
    filter_expr TEXT,
    has_filter INTEGER DEFAULT 0,
    nesting_level INTEGER DEFAULT 0,
    in_function TEXT
);

CREATE INDEX idx_pcomp_file ON python_comprehensions(file);
CREATE INDEX idx_pcomp_kind ON python_comprehensions(comp_kind);
CREATE INDEX idx_pcomp_function ON python_comprehensions(in_function);
```

### 1.2 python_control_statements (NEW)

```sql
CREATE TABLE python_control_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,

    -- Discriminators (two-column pattern)
    statement_kind TEXT NOT NULL,         -- 'break', 'continue', 'pass', 'assert', 'del', 'with'
    statement_type TEXT,                  -- Extractor's subtype (preserved)

    -- From extract_break_continue_pass (extractor_truth.txt line 715)
    -- KEYS: ['in_function', 'line', 'loop_type', 'statement_type']
    loop_type TEXT,

    -- From extract_assert_statements (extractor_truth.txt line 713)
    -- KEYS: ['condition_type', 'has_message', 'in_function', 'line']
    condition_type TEXT,
    has_message INTEGER DEFAULT 0,

    -- From extract_del_statements (extractor_truth.txt line 716)
    -- KEYS: ['in_function', 'line', 'target_count', 'target_type']
    target_count INTEGER,
    target_type TEXT,

    -- From extract_with_statements (extractor_truth.txt line 722)
    -- KEYS: ['context_count', 'has_alias', 'in_function', 'is_async', 'line']
    context_count INTEGER,
    has_alias INTEGER DEFAULT 0,
    is_async INTEGER DEFAULT 0,

    -- Common
    in_function TEXT
);

CREATE INDEX idx_pcs_file ON python_control_statements(file);
CREATE INDEX idx_pcs_kind ON python_control_statements(statement_kind);
CREATE INDEX idx_pcs_function ON python_control_statements(in_function);
```

### 1.3 Junction Table DDL

```sql
-- 1. python_protocol_methods (for python_protocols.implemented_methods JSON)
CREATE TABLE python_protocol_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,
    protocol_id INTEGER NOT NULL,
    method_name TEXT NOT NULL,
    method_order INTEGER DEFAULT 0,
    FOREIGN KEY (protocol_id) REFERENCES python_protocols(id) ON DELETE CASCADE
);

CREATE INDEX idx_ppm_file ON python_protocol_methods(file);
CREATE INDEX idx_ppm_protocol ON python_protocol_methods(protocol_id);
CREATE INDEX idx_ppm_method ON python_protocol_methods(method_name);

-- 2. python_typeddict_fields (for python_type_definitions.fields JSON)
CREATE TABLE python_typeddict_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,
    typeddict_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    field_type TEXT,
    required INTEGER DEFAULT 1,
    field_order INTEGER DEFAULT 0,
    FOREIGN KEY (typeddict_id) REFERENCES python_type_definitions(id) ON DELETE CASCADE
);

CREATE INDEX idx_ptf_file ON python_typeddict_fields(file);
CREATE INDEX idx_ptf_typeddict ON python_typeddict_fields(typeddict_id);
CREATE INDEX idx_ptf_field ON python_typeddict_fields(field_name);

-- 3. python_fixture_params (for python_test_fixtures.params JSON)
CREATE TABLE python_fixture_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,
    fixture_id INTEGER NOT NULL,
    param_name TEXT,
    param_value TEXT,
    param_order INTEGER DEFAULT 0,
    FOREIGN KEY (fixture_id) REFERENCES python_test_fixtures(id) ON DELETE CASCADE
);

CREATE INDEX idx_pfp_file ON python_fixture_params(file);
CREATE INDEX idx_pfp_fixture ON python_fixture_params(fixture_id);

-- 4. python_schema_validators (for python_validation_schemas.validators JSON)
CREATE TABLE python_schema_validators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,
    schema_id INTEGER NOT NULL,
    validator_name TEXT NOT NULL,
    validator_type TEXT,
    validator_order INTEGER DEFAULT 0,
    FOREIGN KEY (schema_id) REFERENCES python_validation_schemas(id) ON DELETE CASCADE
);

CREATE INDEX idx_psv_file ON python_schema_validators(file);
CREATE INDEX idx_psv_schema ON python_schema_validators(schema_id);
CREATE INDEX idx_psv_validator ON python_schema_validators(validator_name);

-- 5. python_framework_methods (for python_framework_config.methods JSON)
CREATE TABLE python_framework_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,
    config_id INTEGER NOT NULL,
    method_name TEXT NOT NULL,
    method_order INTEGER DEFAULT 0,
    FOREIGN KEY (config_id) REFERENCES python_framework_config(id) ON DELETE CASCADE
);

CREATE INDEX idx_pfm_file ON python_framework_methods(file);
CREATE INDEX idx_pfm_config ON python_framework_methods(config_id);
CREATE INDEX idx_pfm_method ON python_framework_methods(method_name);
```

---

## 2. Complete Extractor-to-Table Mapping

This is the authoritative mapping of all extractors to their target tables with discriminator values.

**Source**: `theauditor/ast_extractors/python_impl.py` (lines 65-1107)

```python
# File: theauditor/indexer/extractor_mapping.py (NEW)
# This mapping defines where each extractor output goes

EXTRACTOR_TO_TABLE = {
    # =========================================================================
    # python_loops (3 extractors)
    # Current line in python_impl.py: 872-885
    # =========================================================================
    'extract_for_loops': ('python_loops', {'loop_kind': 'for'}),
    'extract_while_loops': ('python_loops', {'loop_kind': 'while'}),
    'extract_async_for_loops': ('python_loops', {'loop_kind': 'async_for'}),
    # RE-ROUTE from python_expressions:
    'extract_loop_complexity': ('python_loops', {'loop_kind': 'complexity_analysis'}),

    # =========================================================================
    # python_branches (5 extractors)
    # Current lines in python_impl.py: 578-591, 887-895
    # =========================================================================
    'extract_if_statements': ('python_branches', {'branch_kind': 'if'}),
    'extract_match_statements': ('python_branches', {'branch_kind': 'match'}),
    'extract_exception_raises': ('python_branches', {'branch_kind': 'raise'}),
    'extract_exception_catches': ('python_branches', {'branch_kind': 'except'}),
    'extract_finally_blocks': ('python_branches', {'branch_kind': 'finally'}),

    # =========================================================================
    # python_functions_advanced (5 extractors + 2 re-routes)
    # Current lines in python_impl.py: 237-246, 671-674, 1024-1038
    # =========================================================================
    'extract_python_context_managers': ('python_functions_advanced', {'function_kind': 'context_manager'}),
    'extract_generators': ('python_functions_advanced', {'function_kind': 'generator'}),
    'extract_lambda_functions': ('python_functions_advanced', {'function_kind': 'lambda'}),
    'extract_async_functions': ('python_functions_advanced', {'function_kind': 'async'}),
    'extract_async_generators': ('python_functions_advanced', {'function_kind': 'async_generator'}),
    # RE-ROUTE from python_expressions:
    'extract_recursion_patterns': ('python_functions_advanced', {'function_kind': 'recursive'}),
    'extract_memoization_patterns': ('python_functions_advanced', {'function_kind': 'memoized'}),

    # =========================================================================
    # python_io_operations (5 extractors)
    # Current lines in python_impl.py: 601-623
    # =========================================================================
    'extract_io_operations': ('python_io_operations', {}),  # io_type from extractor
    'extract_parameter_return_flow': ('python_io_operations', {'io_kind': 'param_flow'}),
    'extract_closure_captures': ('python_io_operations', {'io_kind': 'closure'}),
    'extract_nonlocal_access': ('python_io_operations', {'io_kind': 'nonlocal'}),
    'extract_conditional_calls': ('python_io_operations', {'io_kind': 'conditional'}),

    # =========================================================================
    # python_state_mutations (5 extractors)
    # Current lines in python_impl.py: 552-575
    # =========================================================================
    'extract_instance_mutations': ('python_state_mutations', {'mutation_kind': 'instance'}),
    'extract_class_mutations': ('python_state_mutations', {'mutation_kind': 'class'}),
    'extract_global_mutations': ('python_state_mutations', {'mutation_kind': 'global'}),
    'extract_argument_mutations': ('python_state_mutations', {'mutation_kind': 'argument'}),
    'extract_augmented_assignments': ('python_state_mutations', {'mutation_kind': 'augmented'}),

    # =========================================================================
    # python_class_features (9 extractors + 1 re-route)
    # Current lines in python_impl.py: 779-828
    # =========================================================================
    'extract_metaclasses': ('python_class_features', {'feature_kind': 'metaclass'}),
    'extract_dataclasses': ('python_class_features', {'feature_kind': 'dataclass'}),
    'extract_enums': ('python_class_features', {'feature_kind': 'enum'}),
    'extract_slots': ('python_class_features', {'feature_kind': 'slots'}),
    'extract_abstract_classes': ('python_class_features', {'feature_kind': 'abstract'}),
    'extract_method_types': ('python_class_features', {'feature_kind': 'method_type'}),
    'extract_multiple_inheritance': ('python_class_features', {'feature_kind': 'inheritance'}),
    'extract_dunder_methods': ('python_class_features', {'feature_kind': 'dunder'}),
    'extract_visibility_conventions': ('python_class_features', {'feature_kind': 'visibility'}),
    # RE-ROUTE from python_expressions:
    'extract_class_decorators': ('python_class_features', {'feature_kind': 'class_decorator'}),

    # =========================================================================
    # python_protocols (7 extractors + 1 re-route)
    # Current lines in python_impl.py: 594-597, 924-952
    # =========================================================================
    'extract_context_managers': ('python_protocols', {'protocol_kind': 'context_manager'}),  # exception_flow version
    'extract_iterator_protocol': ('python_protocols', {'protocol_kind': 'iterator'}),
    'extract_container_protocol': ('python_protocols', {'protocol_kind': 'container'}),
    'extract_callable_protocol': ('python_protocols', {'protocol_kind': 'callable'}),
    'extract_comparison_protocol': ('python_protocols', {'protocol_kind': 'comparison'}),
    'extract_arithmetic_protocol': ('python_protocols', {'protocol_kind': 'arithmetic'}),
    'extract_pickle_protocol': ('python_protocols', {'protocol_kind': 'pickle'}),
    # RE-ROUTE from python_expressions:
    'extract_copy_protocol': ('python_protocols', {'protocol_kind': 'copy'}),

    # =========================================================================
    # python_descriptors (6 extractors)
    # Current lines in python_impl.py: 637-646, 785-788, 986-1001
    # =========================================================================
    'extract_property_patterns': ('python_descriptors', {'descriptor_kind': 'property'}),
    'extract_dynamic_attributes': ('python_descriptors', {'descriptor_kind': 'dynamic_attr'}),
    'extract_descriptors': ('python_descriptors', {'descriptor_kind': 'descriptor'}),
    'extract_cached_property': ('python_descriptors', {'descriptor_kind': 'cached_property'}),
    'extract_descriptor_protocol': ('python_descriptors', {'descriptor_kind': 'descriptor_protocol'}),
    'extract_attribute_access_protocol': ('python_descriptors', {'descriptor_kind': 'attr_access'}),

    # =========================================================================
    # python_type_definitions (3 extractors)
    # Current lines in python_impl.py: 1042-1055
    # =========================================================================
    'extract_protocols': ('python_type_definitions', {'type_kind': 'protocol'}),  # type_extractors version
    'extract_generics': ('python_type_definitions', {'type_kind': 'generic'}),
    'extract_typed_dicts': ('python_type_definitions', {'type_kind': 'typed_dict'}),

    # =========================================================================
    # python_literals (2 extractors)
    # Current lines in python_impl.py: 1057-1065
    # =========================================================================
    'extract_literals': ('python_literals', {'literal_kind': 'literal'}),
    'extract_overloads': ('python_literals', {'literal_kind': 'overload'}),

    # =========================================================================
    # python_security_findings (9 extractors)
    # Current lines in python_impl.py: 474-524
    # =========================================================================
    'extract_auth_decorators': ('python_security_findings', {'finding_kind': 'auth'}),
    'extract_password_hashing': ('python_security_findings', {'finding_kind': 'password'}),
    'extract_jwt_operations': ('python_security_findings', {'finding_kind': 'jwt'}),
    'extract_sql_injection_patterns': ('python_security_findings', {'finding_kind': 'sql_injection'}),
    'extract_command_injection_patterns': ('python_security_findings', {'finding_kind': 'command_injection'}),
    'extract_path_traversal_patterns': ('python_security_findings', {'finding_kind': 'path_traversal'}),
    'extract_dangerous_eval_exec': ('python_security_findings', {'finding_kind': 'dangerous_eval'}),
    'extract_crypto_operations': ('python_security_findings', {'finding_kind': 'crypto'}),
    'extract_sql_queries': (None, {}),  # Goes to sql_queries, not Python table

    # =========================================================================
    # python_test_cases (2 extractors)
    # Current lines in python_impl.py: 425-434
    # =========================================================================
    'extract_unittest_test_cases': ('python_test_cases', {'test_kind': 'unittest'}),
    'extract_assertion_patterns': ('python_test_cases', {'test_kind': 'assertion'}),

    # =========================================================================
    # python_test_fixtures (6 extractors)
    # Current lines in python_impl.py: 437-470
    # =========================================================================
    'extract_pytest_plugin_hooks': ('python_test_fixtures', {'fixture_kind': 'plugin_hook'}),
    'extract_hypothesis_strategies': ('python_test_fixtures', {'fixture_kind': 'hypothesis'}),
    'extract_pytest_fixtures': ('python_test_fixtures', {'fixture_kind': 'fixture'}),
    'extract_pytest_parametrize': ('python_test_fixtures', {'fixture_kind': 'parametrize'}),
    'extract_pytest_markers': ('python_test_fixtures', {'fixture_kind': 'marker'}),
    'extract_mock_patterns': ('python_test_fixtures', {'fixture_kind': 'mock'}),

    # =========================================================================
    # python_framework_config (19 extractors + 4 unwired)
    # Current lines in python_impl.py: 268-412, 527-549
    # =========================================================================
    'extract_django_forms': ('python_framework_config', {'framework': 'django', 'config_kind': 'form'}),
    'extract_django_form_fields': ('python_framework_config', {'framework': 'django', 'config_kind': 'form_field'}),
    'extract_django_admin': ('python_framework_config', {'framework': 'django', 'config_kind': 'admin'}),
    'extract_django_signals': ('python_framework_config', {'framework': 'django', 'config_kind': 'signal'}),
    'extract_django_receivers': ('python_framework_config', {'framework': 'django', 'config_kind': 'receiver'}),
    'extract_django_managers': ('python_framework_config', {'framework': 'django', 'config_kind': 'manager'}),
    'extract_django_querysets': ('python_framework_config', {'framework': 'django', 'config_kind': 'queryset'}),
    'extract_celery_tasks': ('python_framework_config', {'framework': 'celery', 'config_kind': 'task'}),
    'extract_celery_task_calls': ('python_framework_config', {'framework': 'celery', 'config_kind': 'task_call'}),
    'extract_celery_beat_schedules': ('python_framework_config', {'framework': 'celery', 'config_kind': 'schedule'}),
    'extract_flask_app_factories': ('python_framework_config', {'framework': 'flask', 'config_kind': 'app'}),
    'extract_flask_extensions': ('python_framework_config', {'framework': 'flask', 'config_kind': 'extension'}),
    'extract_flask_request_hooks': ('python_framework_config', {'framework': 'flask', 'config_kind': 'hook'}),
    'extract_flask_error_handlers': ('python_framework_config', {'framework': 'flask', 'config_kind': 'error_handler'}),
    'extract_flask_websocket_handlers': ('python_framework_config', {'framework': 'flask', 'config_kind': 'websocket'}),
    'extract_flask_cli_commands': ('python_framework_config', {'framework': 'flask', 'config_kind': 'cli'}),
    'extract_flask_cors_configs': ('python_framework_config', {'framework': 'flask', 'config_kind': 'cors'}),
    'extract_flask_rate_limits': ('python_framework_config', {'framework': 'flask', 'config_kind': 'rate_limit'}),
    'extract_flask_cache_decorators': ('python_framework_config', {'framework': 'flask', 'config_kind': 'cache'}),
    # UNWIRED - NEED TO ADD (currently skipped in python_impl.py:419-421):
    'extract_flask_blueprints': ('python_framework_config', {'framework': 'flask', 'config_kind': 'blueprint'}),
    'extract_graphene_resolvers': ('python_framework_config', {'framework': 'graphene', 'config_kind': 'resolver'}),
    'extract_ariadne_resolvers': ('python_framework_config', {'framework': 'ariadne', 'config_kind': 'resolver'}),
    'extract_strawberry_resolvers': ('python_framework_config', {'framework': 'strawberry', 'config_kind': 'resolver'}),

    # =========================================================================
    # python_validation_schemas (6 extractors)
    # Current lines in python_impl.py: 299-338
    # =========================================================================
    'extract_marshmallow_schemas': ('python_validation_schemas', {'framework': 'marshmallow', 'schema_kind': 'schema'}),
    'extract_marshmallow_fields': ('python_validation_schemas', {'framework': 'marshmallow', 'schema_kind': 'field'}),
    'extract_drf_serializers': ('python_validation_schemas', {'framework': 'drf', 'schema_kind': 'serializer'}),
    'extract_drf_serializer_fields': ('python_validation_schemas', {'framework': 'drf', 'schema_kind': 'field'}),
    'extract_wtforms_forms': ('python_validation_schemas', {'framework': 'wtforms', 'schema_kind': 'form'}),
    'extract_wtforms_fields': ('python_validation_schemas', {'framework': 'wtforms', 'schema_kind': 'field'}),

    # =========================================================================
    # python_operators (6 extractors)
    # Current lines in python_impl.py: 708-735
    # =========================================================================
    'extract_operators': ('python_operators', {}),  # operator_type from extractor
    'extract_membership_tests': ('python_operators', {'operator_kind': 'membership'}),
    'extract_chained_comparisons': ('python_operators', {'operator_kind': 'chained'}),
    'extract_ternary_expressions': ('python_operators', {'operator_kind': 'ternary'}),
    'extract_walrus_operators': ('python_operators', {'operator_kind': 'walrus'}),
    'extract_matrix_multiplication': ('python_operators', {'operator_kind': 'matmul'}),

    # =========================================================================
    # python_collections (8 extractors)
    # Current lines in python_impl.py: 738-776
    # =========================================================================
    'extract_dict_operations': ('python_collections', {'collection_kind': 'dict'}),
    'extract_list_mutations': ('python_collections', {'collection_kind': 'list'}),
    'extract_set_operations': ('python_collections', {'collection_kind': 'set'}),
    'extract_string_methods': ('python_collections', {'collection_kind': 'string'}),
    'extract_builtin_usage': ('python_collections', {'collection_kind': 'builtin'}),
    'extract_itertools_usage': ('python_collections', {'collection_kind': 'itertools'}),
    'extract_functools_usage': ('python_collections', {'collection_kind': 'functools'}),
    'extract_collections_usage': ('python_collections', {'collection_kind': 'collections'}),

    # =========================================================================
    # python_stdlib_usage (10 extractors)
    # Current lines in python_impl.py: 831-869, 955-964
    # =========================================================================
    'extract_regex_patterns': ('python_stdlib_usage', {'stdlib_kind': 're'}),
    'extract_json_operations': ('python_stdlib_usage', {'stdlib_kind': 'json'}),
    'extract_datetime_operations': ('python_stdlib_usage', {'stdlib_kind': 'datetime'}),
    'extract_path_operations': ('python_stdlib_usage', {'stdlib_kind': 'pathlib'}),
    'extract_logging_patterns': ('python_stdlib_usage', {'stdlib_kind': 'logging'}),
    'extract_threading_patterns': ('python_stdlib_usage', {'stdlib_kind': 'threading'}),
    'extract_contextlib_patterns': ('python_stdlib_usage', {'stdlib_kind': 'contextlib'}),
    'extract_type_checking': ('python_stdlib_usage', {'stdlib_kind': 'typing'}),
    'extract_weakref_usage': ('python_stdlib_usage', {'stdlib_kind': 'weakref'}),
    'extract_contextvar_usage': ('python_stdlib_usage', {'stdlib_kind': 'contextvars'}),

    # =========================================================================
    # python_imports_advanced (3 extractors + 1 unwired)
    # Current lines in python_impl.py: 913-916, 967-983
    # =========================================================================
    'extract_import_statements': ('python_imports_advanced', {'import_kind': 'static'}),
    'extract_module_attributes': ('python_imports_advanced', {'import_kind': 'module_attr'}),
    'extract_namespace_packages': ('python_imports_advanced', {'import_kind': 'namespace'}),
    # UNWIRED - NEED TO ADD:
    'extract_python_exports': ('python_imports_advanced', {'import_kind': 'export'}),

    # =========================================================================
    # python_comprehensions (NEW - 1 extractor, split from expressions)
    # =========================================================================
    'extract_comprehensions': ('python_comprehensions', {}),  # comp_kind from extractor's comp_type

    # =========================================================================
    # python_control_statements (NEW - 4 extractors, split from expressions)
    # =========================================================================
    'extract_break_continue_pass': ('python_control_statements', {'statement_kind': 'control'}),
    'extract_assert_statements': ('python_control_statements', {'statement_kind': 'assert'}),
    'extract_del_statements': ('python_control_statements', {'statement_kind': 'del'}),
    'extract_with_statements': ('python_control_statements', {'statement_kind': 'with'}),

    # =========================================================================
    # python_expressions (REDUCED - remaining extractors after splits/re-routes)
    # Current lines in python_impl.py: various
    # =========================================================================
    'extract_slice_operations': ('python_expressions', {'expression_kind': 'slice'}),
    'extract_tuple_operations': ('python_expressions', {'expression_kind': 'tuple'}),
    'extract_unpacking_patterns': ('python_expressions', {'expression_kind': 'unpack'}),
    'extract_none_patterns': ('python_expressions', {'expression_kind': 'none'}),
    'extract_truthiness_patterns': ('python_expressions', {'expression_kind': 'truthiness'}),
    'extract_string_formatting': ('python_expressions', {'expression_kind': 'format'}),
    'extract_ellipsis_usage': ('python_expressions', {'expression_kind': 'ellipsis'}),
    'extract_bytes_operations': ('python_expressions', {'expression_kind': 'bytes'}),
    'extract_exec_eval_compile': ('python_expressions', {'expression_kind': 'exec'}),
    'extract_generator_yields': ('python_expressions', {'expression_kind': 'yield'}),
    'extract_await_expressions': ('python_expressions', {'expression_kind': 'await'}),
    'extract_resource_usage': ('python_expressions', {'expression_kind': 'resource'}),

    # =========================================================================
    # CORE TABLES (not consolidated - unchanged)
    # =========================================================================
    'extract_python_functions': ('symbols', {'type': 'function'}),
    'extract_python_classes': ('symbols', {'type': 'class'}),
    'extract_python_calls': ('symbols', {'type': 'call'}),
    'extract_python_properties': ('symbols', {'type': 'property'}),
    'extract_python_imports': ('imports', {}),
    'extract_python_assignments': ('assignments', {}),
    'extract_variable_usage': ('variable_usage', {}),
    'extract_python_returns': ('returns', {}),
    'extract_python_dicts': ('object_literals', {}),
    'extract_python_attribute_annotations': ('type_annotations', {}),
    'extract_python_calls_with_args': ('function_calls', {}),
    'extract_python_decorators': ('python_decorators', {}),
    'extract_sqlalchemy_definitions': ('python_orm_models', {}),  # Returns tuple
    'extract_django_definitions': ('python_orm_models', {}),  # Returns tuple
    'extract_django_cbvs': ('python_django_views', {}),
    'extract_django_middleware': ('python_django_middleware', {}),
    'extract_flask_routes': ('python_routes', {}),
    'extract_pydantic_validators': ('python_validators', {}),
}

# Total: ~110 extractors mapped to 30 Python tables + core tables
```

---

## 3. Schema Diff for All 20 Consolidated Tables

### 3.1 python_loops

**Current Schema** (`python_schema.py:196-214`):
```python
PYTHON_LOOPS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("loop_type", "TEXT", nullable=False),  # OVERWRITTEN
        Column("target", "TEXT"),                      # INVENTED
        Column("iterator", "TEXT"),                    # INVENTED
        Column("has_else", "INTEGER", default="0"),
        Column("nesting_level", "INTEGER", default="0"),
        Column("body_line_count", "INTEGER"),          # INVENTED
    ]
)
```

**Extractor Truth**:
- `extract_for_loops`: `['has_else', 'in_function', 'line', 'loop_type', 'nesting_level', 'target_count']`
- `extract_while_loops`: `['has_else', 'in_function', 'is_infinite', 'line', 'nesting_level']`
- `extract_async_for_loops`: `['has_else', 'in_function', 'line', 'target_count']`
- `extract_loop_complexity` (re-routed): `['estimated_complexity', 'has_growing_operation', 'in_function', 'line', 'loop_type', 'nesting_level']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | loop_kind | TEXT NOT NULL | Discriminator |
| KEEP | loop_type | TEXT | Extractor (NOT overwritten) |
| REMOVE | target | TEXT | INVENTED |
| REMOVE | iterator | TEXT | INVENTED |
| REMOVE | body_line_count | INTEGER | INVENTED |
| KEEP | has_else | INTEGER | Extractor |
| KEEP | nesting_level | INTEGER | Extractor |
| ADD | target_count | INTEGER | extract_for_loops, extract_async_for_loops |
| ADD | in_function | TEXT | All extractors |
| ADD | is_infinite | INTEGER | extract_while_loops |
| ADD | estimated_complexity | TEXT | extract_loop_complexity |
| ADD | has_growing_operation | INTEGER | extract_loop_complexity |

---

### 3.2 python_branches

**Current Schema** (`python_schema.py:216-234`):
```python
PYTHON_BRANCHES = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("branch_type", "TEXT", nullable=False),
        Column("condition", "TEXT"),                   # INVENTED
        Column("has_else", "INTEGER", default="0"),
        Column("elif_count", "INTEGER", default="0"),  # WRONG TYPE
        Column("case_count", "INTEGER", default="0"),
        Column("exception_type", "TEXT"),              # WRONG NAME
    ]
)
```

**Extractor Truth**:
- `extract_if_statements`: `['chain_length', 'has_complex_condition', 'has_elif', 'has_else', 'in_function', 'line', 'nesting_level']`
- `extract_match_statements`: `['case_count', 'has_guards', 'has_wildcard', 'in_function', 'line', 'pattern_types']`
- `extract_exception_catches`: `['exception_types', 'handling_strategy', 'in_function', 'line', 'variable_name']`
- `extract_exception_raises`: `['condition', 'exception_type', 'from_exception', 'in_function', 'is_re_raise', 'line', 'message']`
- `extract_finally_blocks`: `['cleanup_calls', 'has_cleanup', 'in_function', 'line']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | branch_kind | TEXT NOT NULL | Discriminator |
| KEEP | branch_type | TEXT | Preserved |
| REMOVE | condition | TEXT | INVENTED (raises has different 'condition') |
| KEEP | has_else | INTEGER | extract_if_statements |
| RENAME | elif_count -> has_elif | INTEGER | extract_if_statements (bool) |
| KEEP | case_count | INTEGER | extract_match_statements |
| RENAME | exception_type -> exception_types | TEXT | extract_exception_catches |
| ADD | chain_length | INTEGER | extract_if_statements |
| ADD | has_complex_condition | INTEGER | extract_if_statements |
| ADD | nesting_level | INTEGER | extract_if_statements |
| ADD | has_guards | INTEGER | extract_match_statements |
| ADD | has_wildcard | INTEGER | extract_match_statements |
| ADD | pattern_types | TEXT | extract_match_statements |
| ADD | handling_strategy | TEXT | extract_exception_catches |
| ADD | variable_name | TEXT | extract_exception_catches |
| ADD | is_re_raise | INTEGER | extract_exception_raises |
| ADD | from_exception | TEXT | extract_exception_raises |
| ADD | message | TEXT | extract_exception_raises |
| ADD | has_cleanup | INTEGER | extract_finally_blocks |
| ADD | cleanup_calls | TEXT | extract_finally_blocks |
| ADD | in_function | TEXT | All extractors |

---

### 3.3 python_functions_advanced

**Current Schema** (`python_schema.py:236-253`):
```python
PYTHON_FUNCTIONS_ADVANCED = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("function_type", "TEXT", nullable=False),  # OVERWRITTEN
        Column("name", "TEXT"),
        Column("is_method", "INTEGER", default="0"),       # INVENTED
        Column("yield_count", "INTEGER", default="0"),
        Column("await_count", "INTEGER", default="0"),
    ]
)
```

**Extractor Truth**:
- `extract_generators`: `['generator_type', 'has_send', 'has_yield_from', 'is_infinite', 'line', 'name', 'yield_count']`
- `extract_async_functions`: `['await_count', 'function_name', 'has_async_for', 'has_async_with', 'line']`
- `extract_lambda_functions`: `['body', 'captured_vars', 'captures_closure', 'in_function', 'line', 'parameter_count', 'parameters', 'used_in']`
- `extract_python_context_managers`: `['as_name', 'context_expr', 'context_type', 'is_async', 'line']`
- `extract_async_generators`: `['generator_type', 'iter_expr', 'line', 'target_var']`
- `extract_recursion_patterns` (re-routed): `['base_case_line', 'calls_function', 'function_name', 'is_async', 'line', 'recursion_type']`
- `extract_memoization_patterns` (re-routed): `['cache_size', 'function_name', 'has_memoization', 'is_recursive', 'line', 'memoization_type']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | function_kind | TEXT NOT NULL | Discriminator |
| KEEP | function_type | TEXT | Preserved (generator_type, context_type, etc.) |
| KEEP | name | TEXT | extract_generators |
| ADD | function_name | TEXT | extract_async_functions, extract_recursion_patterns, extract_memoization_patterns |
| REMOVE | is_method | INTEGER | INVENTED |
| KEEP | yield_count | INTEGER | extract_generators |
| KEEP | await_count | INTEGER | extract_async_functions |
| ADD | has_send | INTEGER | extract_generators |
| ADD | has_yield_from | INTEGER | extract_generators |
| ADD | is_infinite | INTEGER | extract_generators |
| ADD | has_async_for | INTEGER | extract_async_functions |
| ADD | has_async_with | INTEGER | extract_async_functions |
| ADD | parameter_count | INTEGER | extract_lambda_functions |
| ADD | parameters | TEXT | extract_lambda_functions |
| ADD | body | TEXT | extract_lambda_functions |
| ADD | captures_closure | INTEGER | extract_lambda_functions |
| ADD | captured_vars | TEXT | extract_lambda_functions |
| ADD | used_in | TEXT | extract_lambda_functions |
| ADD | as_name | TEXT | extract_python_context_managers |
| ADD | context_expr | TEXT | extract_python_context_managers |
| ADD | is_async | INTEGER | extract_python_context_managers |
| ADD | iter_expr | TEXT | extract_async_generators |
| ADD | target_var | TEXT | extract_async_generators |
| ADD | base_case_line | INTEGER | extract_recursion_patterns |
| ADD | calls_function | TEXT | extract_recursion_patterns |
| ADD | recursion_type | TEXT | extract_recursion_patterns |
| ADD | cache_size | INTEGER | extract_memoization_patterns |
| ADD | memoization_type | TEXT | extract_memoization_patterns |
| ADD | is_recursive | INTEGER | extract_memoization_patterns |
| ADD | has_memoization | INTEGER | extract_memoization_patterns |
| ADD | in_function | TEXT | extract_lambda_functions |

---

### 3.4 python_io_operations

**Current Schema** (`python_schema.py:255-272`):
```python
PYTHON_IO_OPERATIONS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("io_type", "TEXT", nullable=False),
        Column("operation", "TEXT"),
        Column("target", "TEXT"),
        Column("is_taint_source", "INTEGER", default="0"),  # INVENTED
        Column("is_taint_sink", "INTEGER", default="0"),    # INVENTED
    ]
)
```

**Extractor Truth**:
- `extract_io_operations`: `['in_function', 'io_type', 'is_static', 'line', 'operation', 'target']`
- `extract_parameter_return_flow`: `['flow_type', 'function_name', 'is_async', 'line', 'parameter_name', 'return_expr']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | io_kind | TEXT NOT NULL | Discriminator |
| KEEP | io_type | TEXT | Extractor (or flow_type) |
| KEEP | operation | TEXT | extract_io_operations |
| KEEP | target | TEXT | extract_io_operations |
| REMOVE | is_taint_source | INTEGER | INVENTED |
| REMOVE | is_taint_sink | INTEGER | INVENTED |
| ADD | is_static | INTEGER | extract_io_operations |
| ADD | flow_type | TEXT | extract_parameter_return_flow |
| ADD | function_name | TEXT | extract_parameter_return_flow |
| ADD | parameter_name | TEXT | extract_parameter_return_flow |
| ADD | return_expr | TEXT | extract_parameter_return_flow |
| ADD | is_async | INTEGER | extract_parameter_return_flow |
| ADD | in_function | TEXT | All extractors |

---

### 3.5 python_state_mutations

**Current Schema** (`python_schema.py:274-291`):
```python
PYTHON_STATE_MUTATIONS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("mutation_type", "TEXT", nullable=False),
        Column("target", "TEXT"),
        Column("operator", "TEXT"),
        Column("value_expr", "TEXT"),                    # NOT IN TRUTH
        Column("in_function", "TEXT"),
    ]
)
```

**Extractor Truth**:
- `extract_instance_mutations`: `['in_function', 'is_dunder_method', 'is_init', 'is_property_setter', 'line', 'operation', 'target']`
- `extract_augmented_assignments`: `['in_function', 'line', 'operator', 'target', 'target_type']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | mutation_kind | TEXT NOT NULL | Discriminator |
| KEEP | mutation_type | TEXT | Preserved |
| KEEP | target | TEXT | All extractors |
| KEEP | operator | TEXT | extract_augmented_assignments |
| REMOVE | value_expr | TEXT | NOT IN TRUTH |
| KEEP | in_function | TEXT | All extractors |
| ADD | operation | TEXT | extract_instance_mutations |
| ADD | is_init | INTEGER | extract_instance_mutations |
| ADD | is_dunder_method | INTEGER | extract_instance_mutations |
| ADD | is_property_setter | INTEGER | extract_instance_mutations |
| ADD | target_type | TEXT | extract_augmented_assignments |

---

### 3.6 python_class_features

**Current Schema** (`python_schema.py:297-313`):
```python
PYTHON_CLASS_FEATURES = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("feature_type", "TEXT", nullable=False),
        Column("class_name", "TEXT"),
        Column("name", "TEXT"),
        Column("details", "TEXT"),  # JSON BLOB - MUST EXPAND
    ]
)
```

**Extractor Truth** (showing all keys):
- `extract_metaclasses`: `['class_name', 'is_definition', 'line', 'metaclass_name']`
- `extract_dataclasses`: `['class_name', 'field_count', 'frozen', 'line']`
- `extract_enums`: `['enum_name', 'enum_type', 'line', 'member_count']`
- `extract_slots`: `['class_name', 'line', 'slot_count']`
- `extract_abstract_classes`: `['abstract_method_count', 'class_name', 'line']`
- `extract_method_types`: `['in_class', 'line', 'method_name', 'method_type']`
- `extract_dunder_methods`: `['category', 'in_class', 'line', 'method_name']`
- `extract_visibility_conventions`: `['in_class', 'is_name_mangled', 'line', 'name', 'visibility']`
- `extract_class_decorators` (re-routed): `['class_name', 'decorator', 'decorator_type', 'has_arguments', 'line']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | feature_kind | TEXT NOT NULL | Discriminator |
| KEEP | feature_type | TEXT | Preserved |
| KEEP | class_name | TEXT | Multiple extractors |
| KEEP | name | TEXT | extract_visibility_conventions |
| REMOVE | details | TEXT | JSON BLOB - EXPAND |
| ADD | in_class | TEXT | extract_method_types, extract_dunder_methods, etc. |
| ADD | metaclass_name | TEXT | extract_metaclasses |
| ADD | is_definition | INTEGER | extract_metaclasses |
| ADD | field_count | INTEGER | extract_dataclasses |
| ADD | frozen | INTEGER | extract_dataclasses |
| ADD | enum_name | TEXT | extract_enums |
| ADD | enum_type | TEXT | extract_enums |
| ADD | member_count | INTEGER | extract_enums |
| ADD | slot_count | INTEGER | extract_slots |
| ADD | abstract_method_count | INTEGER | extract_abstract_classes |
| ADD | method_name | TEXT | extract_method_types, extract_dunder_methods |
| ADD | method_type | TEXT | extract_method_types |
| ADD | category | TEXT | extract_dunder_methods |
| ADD | visibility | TEXT | extract_visibility_conventions |
| ADD | is_name_mangled | INTEGER | extract_visibility_conventions |
| ADD | decorator | TEXT | extract_class_decorators |
| ADD | decorator_type | TEXT | extract_class_decorators |
| ADD | has_arguments | INTEGER | extract_class_decorators |

---

### 3.7 python_protocols

**Current Schema** (`python_schema.py:315-330`):
```python
PYTHON_PROTOCOLS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("protocol_type", "TEXT", nullable=False),  # OVERWRITTEN by orchestrator
        Column("class_name", "TEXT"),
        Column("implemented_methods", "TEXT"),  # JSON BLOB - NEEDS JUNCTION TABLE
    ]
)
```

**Extractor Truth**:
- `extract_iterator_protocol`: `['class_name', 'has_iter', 'has_next', 'is_generator', 'line', 'raises_stopiteration']`
- `extract_container_protocol`: `['class_name', 'has_contains', 'has_delitem', 'has_getitem', 'has_len', 'has_setitem', 'is_mapping', 'is_sequence', 'line']`
- `extract_callable_protocol`: `['class_name', 'has_args', 'has_kwargs', 'line', 'param_count']`
- `extract_pickle_protocol`: `['class_name', 'has_getstate', 'has_reduce', 'has_reduce_ex', 'has_setstate', 'line']`
- `extract_context_managers` (exception_flow): `['context_expr', 'in_function', 'is_async', 'line', 'resource_type', 'variable_name']`
- `extract_copy_protocol` (re-routed): `['class_name', 'has_copy', 'has_deepcopy', 'line']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | protocol_kind | TEXT NOT NULL | Discriminator |
| KEEP | protocol_type | TEXT | Preserved (NOT overwritten) |
| KEEP | class_name | TEXT | All extractors |
| REMOVE | implemented_methods | TEXT | JSON BLOB → junction table |
| ADD | has_iter | INTEGER | extract_iterator_protocol |
| ADD | has_next | INTEGER | extract_iterator_protocol |
| ADD | is_generator | INTEGER | extract_iterator_protocol |
| ADD | raises_stopiteration | INTEGER | extract_iterator_protocol |
| ADD | has_contains | INTEGER | extract_container_protocol |
| ADD | has_getitem | INTEGER | extract_container_protocol |
| ADD | has_setitem | INTEGER | extract_container_protocol |
| ADD | has_delitem | INTEGER | extract_container_protocol |
| ADD | has_len | INTEGER | extract_container_protocol |
| ADD | is_mapping | INTEGER | extract_container_protocol |
| ADD | is_sequence | INTEGER | extract_container_protocol |
| ADD | has_args | INTEGER | extract_callable_protocol |
| ADD | has_kwargs | INTEGER | extract_callable_protocol |
| ADD | param_count | INTEGER | extract_callable_protocol |
| ADD | has_getstate | INTEGER | extract_pickle_protocol |
| ADD | has_setstate | INTEGER | extract_pickle_protocol |
| ADD | has_reduce | INTEGER | extract_pickle_protocol |
| ADD | has_reduce_ex | INTEGER | extract_pickle_protocol |
| ADD | context_expr | TEXT | extract_context_managers |
| ADD | resource_type | TEXT | extract_context_managers |
| ADD | variable_name | TEXT | extract_context_managers |
| ADD | is_async | INTEGER | extract_context_managers |
| ADD | has_copy | INTEGER | extract_copy_protocol |
| ADD | has_deepcopy | INTEGER | extract_copy_protocol |
| ADD | in_function | TEXT | extract_context_managers |

---

### 3.8 python_descriptors

**Current Schema** (`python_schema.py:332-350`):
```python
PYTHON_DESCRIPTORS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("descriptor_type", "TEXT", nullable=False),
        Column("name", "TEXT"),
        Column("class_name", "TEXT"),
        Column("has_getter", "INTEGER", default="0"),  # WRONG NAME
        Column("has_setter", "INTEGER", default="0"),  # WRONG NAME
        Column("has_deleter", "INTEGER", default="0"), # WRONG NAME
    ]
)
```

**Extractor Truth**:
- `extract_property_patterns`: `['access_type', 'has_computation', 'has_validation', 'in_class', 'line', 'property_name']`
- `extract_descriptors`: `['class_name', 'descriptor_type', 'has_delete', 'has_get', 'has_set', 'line']`
- `extract_cached_property`: `['in_class', 'is_functools', 'line', 'method_name']`
- `extract_descriptor_protocol`: `['class_name', 'has_delete', 'has_get', 'has_set', 'is_data_descriptor', 'line']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | descriptor_kind | TEXT NOT NULL | Discriminator |
| KEEP | descriptor_type | TEXT | Preserved |
| KEEP | name | TEXT | extract_property_patterns (property_name) |
| KEEP | class_name | TEXT | extract_descriptors |
| RENAME | has_getter -> has_get | INTEGER | extract_descriptors |
| RENAME | has_setter -> has_set | INTEGER | extract_descriptors |
| RENAME | has_deleter -> has_delete | INTEGER | extract_descriptors |
| ADD | access_type | TEXT | extract_property_patterns |
| ADD | has_computation | INTEGER | extract_property_patterns |
| ADD | has_validation | INTEGER | extract_property_patterns |
| ADD | in_class | TEXT | extract_property_patterns, extract_cached_property |
| ADD | method_name | TEXT | extract_cached_property |
| ADD | is_functools | INTEGER | extract_cached_property |
| ADD | is_data_descriptor | INTEGER | extract_descriptor_protocol |

---

### 3.9 python_type_definitions

**Current Schema** (`python_schema.py:352-368`):
```python
PYTHON_TYPE_DEFINITIONS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("type_kind", "TEXT", nullable=False),  # Good - already has discriminator
        Column("name", "TEXT"),
        Column("type_params", "TEXT"),  # JSON BLOB - expand to columns
        Column("fields", "TEXT"),       # JSON BLOB - NEEDS JUNCTION TABLE
    ]
)
```

**Extractor Truth**:
- `extract_protocols` (type_extractors): `['is_runtime_checkable', 'line', 'methods', 'protocol_name']`
- `extract_generics`: `['class_name', 'line', 'type_params']`
- `extract_typed_dicts`: `['fields', 'line', 'typeddict_name']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| KEEP | type_kind | TEXT NOT NULL | Already discriminator |
| KEEP | name | TEXT | typeddict_name, protocol_name, class_name |
| REMOVE | type_params | TEXT | JSON BLOB → expand to columns |
| REMOVE | fields | TEXT | JSON BLOB → junction table |
| ADD | type_param_1 | TEXT | extract_generics (bounded array) |
| ADD | type_param_2 | TEXT | extract_generics |
| ADD | type_param_3 | TEXT | extract_generics |
| ADD | type_param_4 | TEXT | extract_generics |
| ADD | type_param_5 | TEXT | extract_generics |
| ADD | type_param_count | INTEGER | extract_generics |
| ADD | is_runtime_checkable | INTEGER | extract_protocols |
| ADD | methods | TEXT | extract_protocols (simple comma-separated) |

---

### 3.10 python_literals

**Current Schema** (`python_schema.py:370-385`):
```python
PYTHON_LITERALS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("literal_type", "TEXT", nullable=False),
        Column("name", "TEXT"),
        Column("literal_values", "TEXT"),  # JSON BLOB - expand to columns
    ]
)
```

**Extractor Truth**:
- `extract_overloads`: `['function_name', 'overload_count', 'variants']`
- `extract_literals`: No data in sample (keys unknown, but typically simple values)

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | literal_kind | TEXT NOT NULL | Discriminator |
| KEEP | literal_type | TEXT | Preserved |
| KEEP | name | TEXT | function_name |
| REMOVE | literal_values | TEXT | JSON BLOB → expand |
| ADD | literal_value_1 | TEXT | extract_literals (bounded) |
| ADD | literal_value_2 | TEXT | extract_literals |
| ADD | literal_value_3 | TEXT | extract_literals |
| ADD | literal_value_4 | TEXT | extract_literals |
| ADD | literal_value_5 | TEXT | extract_literals |
| ADD | overload_count | INTEGER | extract_overloads |
| ADD | variants | TEXT | extract_overloads (comma-separated) |

---

### 3.11 python_security_findings

**Current Schema** (`python_schema.py:391-410`):
```python
PYTHON_SECURITY_FINDINGS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("finding_type", "TEXT", nullable=False),
        Column("severity", "TEXT", default="'medium'"),
        Column("source_expr", "TEXT"),   # INVENTED - not in extractor
        Column("sink_expr", "TEXT"),     # INVENTED - not in extractor
        Column("vulnerable_code", "TEXT"),  # INVENTED
        Column("cwe_id", "TEXT"),        # INVENTED
    ]
)
```

**Extractor Truth**:
- `extract_auth_decorators`: `['decorator_name', 'function_name', 'line', 'permissions']`
- `extract_command_injection_patterns`: `['function', 'is_vulnerable', 'line', 'shell_true']`
- `extract_dangerous_eval_exec`: `['function', 'is_constant_input', 'is_critical', 'line']`
- `extract_path_traversal_patterns`: `['function', 'has_concatenation', 'is_vulnerable', 'line']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | finding_kind | TEXT NOT NULL | Discriminator |
| KEEP | finding_type | TEXT | Preserved |
| REMOVE | severity | TEXT | INVENTED |
| REMOVE | source_expr | TEXT | INVENTED |
| REMOVE | sink_expr | TEXT | INVENTED |
| REMOVE | vulnerable_code | TEXT | INVENTED |
| REMOVE | cwe_id | TEXT | INVENTED |
| ADD | function_name | TEXT | All extractors |
| ADD | decorator_name | TEXT | extract_auth_decorators |
| ADD | permissions | TEXT | extract_auth_decorators |
| ADD | is_vulnerable | INTEGER | extract_command_injection, extract_path_traversal |
| ADD | shell_true | INTEGER | extract_command_injection_patterns |
| ADD | is_constant_input | INTEGER | extract_dangerous_eval_exec |
| ADD | is_critical | INTEGER | extract_dangerous_eval_exec |
| ADD | has_concatenation | INTEGER | extract_path_traversal_patterns |

---

### 3.12 python_test_cases

**Current Schema** (`python_schema.py:412-429`):
```python
PYTHON_TEST_CASES = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("test_type", "TEXT", nullable=False),
        Column("name", "TEXT"),
        Column("class_name", "TEXT"),
        Column("assertion_type", "TEXT"),
        Column("expected_exception", "TEXT"),  # INVENTED
    ]
)
```

**Extractor Truth**:
- `extract_assertion_patterns`: `['assertion_type', 'function_name', 'line', 'test_expr']`
- `extract_unittest_test_cases`: No data in sample

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | test_kind | TEXT NOT NULL | Discriminator |
| KEEP | test_type | TEXT | Preserved |
| KEEP | name | TEXT | function_name |
| KEEP | class_name | TEXT | Preserved |
| KEEP | assertion_type | TEXT | extract_assertion_patterns |
| REMOVE | expected_exception | TEXT | INVENTED |
| ADD | test_expr | TEXT | extract_assertion_patterns |

---

### 3.13 python_test_fixtures

**Current Schema** (`python_schema.py:431-448`):
```python
PYTHON_TEST_FIXTURES = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("fixture_type", "TEXT", nullable=False),
        Column("name", "TEXT"),
        Column("scope", "TEXT"),
        Column("params", "TEXT"),  # JSON BLOB - NEEDS JUNCTION TABLE
        Column("autouse", "INTEGER", default="0"),
    ]
)
```

**Extractor Truth** (no data in sample, keys from extractor signatures):
- `extract_pytest_fixtures`: params, scope, etc.
- `extract_pytest_parametrize`: parameters
- `extract_pytest_markers`: marker data
- `extract_hypothesis_strategies`: strategy configs

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | fixture_kind | TEXT NOT NULL | Discriminator |
| KEEP | fixture_type | TEXT | Preserved |
| KEEP | name | TEXT | Preserved |
| KEEP | scope | TEXT | Preserved |
| REMOVE | params | TEXT | JSON BLOB → junction table |
| KEEP | autouse | INTEGER | Preserved |
| ADD | in_function | TEXT | Common pattern |

---

### 3.14 python_framework_config

**Current Schema** (`python_schema.py:450-470`):
```python
PYTHON_FRAMEWORK_CONFIG = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),
        Column("config_type", "TEXT", nullable=False),
        Column("name", "TEXT"),
        Column("endpoint", "TEXT"),
        Column("methods", "TEXT"),   # JSON BLOB - NEEDS JUNCTION TABLE
        Column("schedule", "TEXT"),  # JSON BLOB - expand
        Column("details", "TEXT"),   # JSON BLOB - expand
    ]
)
```

**Extractor Truth**:
- `extract_flask_cache_decorators`: `['cache_type', 'function_name', 'line', 'timeout']`
- `extract_django_middleware`: `['has_process_exception', 'has_process_request', 'has_process_response', 'has_process_template_response', 'has_process_view', 'line', 'middleware_class_name']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | config_kind | TEXT NOT NULL | Discriminator |
| KEEP | framework | TEXT | Preserved |
| RENAME | config_type -> config_subtype | TEXT | Preserved |
| KEEP | name | TEXT | function_name, middleware_class_name |
| KEEP | endpoint | TEXT | Preserved |
| REMOVE | methods | TEXT | JSON BLOB → junction table |
| REMOVE | schedule | TEXT | JSON BLOB → expand |
| REMOVE | details | TEXT | JSON BLOB → expand |
| ADD | cache_type | TEXT | extract_flask_cache_decorators |
| ADD | timeout | INTEGER | extract_flask_cache_decorators |
| ADD | has_process_request | INTEGER | extract_django_middleware |
| ADD | has_process_response | INTEGER | extract_django_middleware |
| ADD | has_process_exception | INTEGER | extract_django_middleware |
| ADD | has_process_view | INTEGER | extract_django_middleware |
| ADD | has_process_template_response | INTEGER | extract_django_middleware |

---

### 3.15 python_validation_schemas

**Current Schema** (`python_schema.py:472-490`):
```python
PYTHON_VALIDATION_SCHEMAS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("framework", "TEXT", nullable=False),
        Column("schema_type", "TEXT", nullable=False),
        Column("name", "TEXT"),
        Column("field_type", "TEXT"),
        Column("validators", "TEXT"),  # JSON BLOB - NEEDS JUNCTION TABLE
        Column("required", "INTEGER", default="0"),
    ]
)
```

**Extractor Truth**: No data in sample code

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | schema_kind | TEXT NOT NULL | Discriminator |
| KEEP | framework | TEXT | Preserved |
| KEEP | schema_type | TEXT | Preserved |
| KEEP | name | TEXT | Preserved |
| KEEP | field_type | TEXT | Preserved |
| REMOVE | validators | TEXT | JSON BLOB → junction table |
| KEEP | required | INTEGER | Preserved |

---

### 3.16 python_operators

**Current Schema** (`python_schema.py:496-512`):
```python
PYTHON_OPERATORS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("operator_type", "TEXT", nullable=False),
        Column("operator", "TEXT"),
        Column("left_operand", "TEXT"),   # INVENTED
        Column("right_operand", "TEXT"),  # INVENTED
    ]
)
```

**Extractor Truth**:
- `extract_operators`: `['in_function', 'line', 'operator', 'operator_type']`
- `extract_membership_tests`: `['container_type', 'in_function', 'line', 'operator']`
- `extract_chained_comparisons`: `['chain_length', 'in_function', 'line', 'operators']`
- `extract_ternary_expressions`: `['has_complex_condition', 'in_function', 'line']`
- `extract_walrus_operators`: `['in_function', 'line', 'used_in', 'variable']`
- `extract_matrix_multiplication`: `['in_function', 'line']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | operator_kind | TEXT NOT NULL | Discriminator |
| KEEP | operator_type | TEXT | Preserved |
| KEEP | operator | TEXT | Multiple extractors |
| REMOVE | left_operand | TEXT | INVENTED |
| REMOVE | right_operand | TEXT | INVENTED |
| ADD | in_function | TEXT | All extractors |
| ADD | container_type | TEXT | extract_membership_tests |
| ADD | chain_length | INTEGER | extract_chained_comparisons |
| ADD | operators | TEXT | extract_chained_comparisons |
| ADD | has_complex_condition | INTEGER | extract_ternary_expressions |
| ADD | variable | TEXT | extract_walrus_operators |
| ADD | used_in | TEXT | extract_walrus_operators |

---

### 3.17 python_collections

**Current Schema** (`python_schema.py:514-529`):
```python
PYTHON_COLLECTIONS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("collection_type", "TEXT", nullable=False),
        Column("operation", "TEXT"),
        Column("method", "TEXT"),
    ]
)
```

**Extractor Truth**:
- `extract_dict_operations`: `['has_default', 'in_function', 'line', 'operation']`
- `extract_list_mutations`: `['in_function', 'line', 'method', 'mutates_in_place']`
- `extract_set_operations`: `['in_function', 'line', 'operation']`
- `extract_string_methods`: `['in_function', 'line', 'method']`
- `extract_builtin_usage`: `['builtin', 'has_key', 'in_function', 'line']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | collection_kind | TEXT NOT NULL | Discriminator |
| KEEP | collection_type | TEXT | Preserved |
| KEEP | operation | TEXT | Multiple extractors |
| KEEP | method | TEXT | Multiple extractors |
| ADD | in_function | TEXT | All extractors |
| ADD | has_default | INTEGER | extract_dict_operations |
| ADD | mutates_in_place | INTEGER | extract_list_mutations |
| ADD | builtin | TEXT | extract_builtin_usage |
| ADD | has_key | INTEGER | extract_builtin_usage |

---

### 3.18 python_stdlib_usage

**Current Schema** (`python_schema.py:531-547`):
```python
PYTHON_STDLIB_USAGE = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("module", "TEXT", nullable=False),
        Column("usage_type", "TEXT", nullable=False),
        Column("function_name", "TEXT"),
        Column("pattern", "TEXT"),
    ]
)
```

**Extractor Truth**:
- `extract_regex_patterns`: `['has_flags', 'in_function', 'line', 'operation']`
- `extract_json_operations`: `['direction', 'in_function', 'line', 'operation']`
- `extract_path_operations`: `['in_function', 'line', 'operation', 'path_type']`
- `extract_logging_patterns`: `['in_function', 'line', 'log_level']`
- `extract_threading_patterns`: `['in_function', 'line', 'threading_type']`
- `extract_contextlib_patterns`: `['in_function', 'is_decorator', 'line', 'pattern']`
- `extract_weakref_usage`: `['in_function', 'line', 'usage_type']`
- `extract_contextvar_usage`: `['in_function', 'line', 'operation']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | stdlib_kind | TEXT NOT NULL | Discriminator |
| KEEP | module | TEXT | Preserved |
| KEEP | usage_type | TEXT | Preserved |
| KEEP | function_name | TEXT | Preserved |
| KEEP | pattern | TEXT | extract_contextlib_patterns |
| ADD | in_function | TEXT | All extractors |
| ADD | operation | TEXT | Multiple extractors |
| ADD | has_flags | INTEGER | extract_regex_patterns |
| ADD | direction | TEXT | extract_json_operations |
| ADD | path_type | TEXT | extract_path_operations |
| ADD | log_level | TEXT | extract_logging_patterns |
| ADD | threading_type | TEXT | extract_threading_patterns |
| ADD | is_decorator | INTEGER | extract_contextlib_patterns |

---

### 3.19 python_imports_advanced

**Current Schema** (`python_schema.py:549-566`):
```python
PYTHON_IMPORTS_ADVANCED = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("import_type", "TEXT", nullable=False),
        Column("module", "TEXT"),
        Column("name", "TEXT"),
        Column("alias", "TEXT"),
        Column("is_relative", "INTEGER", default="0"),
    ]
)
```

**Extractor Truth**:
- `extract_import_statements`: `['has_alias', 'import_type', 'imported_names', 'in_function', 'is_wildcard', 'line', 'module', 'relative_level']`
- `extract_module_attributes`: `['attribute', 'in_function', 'line', 'usage_type']`
- `extract_python_exports` (UNWIRED): `['default', 'line', 'name', 'type']`

**Target Schema**:
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | import_kind | TEXT NOT NULL | Discriminator |
| KEEP | import_type | TEXT | Preserved |
| KEEP | module | TEXT | extract_import_statements |
| KEEP | name | TEXT | All extractors |
| KEEP | alias | TEXT | Preserved |
| KEEP | is_relative | INTEGER | Preserved |
| ADD | in_function | TEXT | All extractors |
| ADD | has_alias | INTEGER | extract_import_statements |
| ADD | imported_names | TEXT | extract_import_statements |
| ADD | is_wildcard | INTEGER | extract_import_statements |
| ADD | relative_level | INTEGER | extract_import_statements |
| ADD | attribute | TEXT | extract_module_attributes |
| ADD | default | INTEGER | extract_python_exports |
| ADD | export_type | TEXT | extract_python_exports |

---

### 3.20 python_expressions (REDUCED)

**Current Schema** (`python_schema.py:568-584`):
```python
PYTHON_EXPRESSIONS = TableSchema(
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("expression_type", "TEXT", nullable=False),  # Junk drawer of 22 types
        Column("subtype", "TEXT"),
        Column("expression", "TEXT"),
        Column("variables", "TEXT"),
    ]
)
```

**After Decomposition** - extractors REMOVED (moved to other tables):
- `extract_comprehensions` → python_comprehensions (NEW)
- `extract_break_continue_pass` → python_control_statements (NEW)
- `extract_assert_statements` → python_control_statements (NEW)
- `extract_del_statements` → python_control_statements (NEW)
- `extract_with_statements` → python_control_statements (NEW)
- `extract_copy_protocol` → python_protocols
- `extract_recursion_patterns` → python_functions_advanced
- `extract_memoization_patterns` → python_functions_advanced
- `extract_loop_complexity` → python_loops
- `extract_class_decorators` → python_class_features

**Remaining extractors** (12):
- `extract_slice_operations`: `['has_start', 'has_step', 'has_stop', 'in_function', 'is_assignment', 'line', 'target']`
- `extract_tuple_operations`: `['element_count', 'in_function', 'line', 'operation']`
- `extract_unpacking_patterns`: `['has_rest', 'in_function', 'line', 'target_count', 'unpack_type']`
- `extract_none_patterns`: `['in_function', 'line', 'pattern', 'uses_is']`
- `extract_truthiness_patterns`: `['expression', 'in_function', 'line', 'pattern']`
- `extract_string_formatting`: `['format_type', 'has_expressions', 'in_function', 'line', 'var_count']`
- `extract_ellipsis_usage`: `['context', 'in_function', 'line']`
- `extract_bytes_operations`: `['in_function', 'line', 'operation']`
- `extract_exec_eval_compile`: `['has_globals', 'has_locals', 'in_function', 'line', 'operation']`
- `extract_generator_yields`: `['condition', 'generator_function', 'in_loop', 'line', 'yield_expr', 'yield_type']`
- `extract_await_expressions`: `['awaited_expr', 'containing_function', 'line']`
- `extract_resource_usage`: No data in sample

**Target Schema** (REDUCED from 55 columns to ~25):
| Action | Column | Type | Source |
|--------|--------|------|--------|
| ADD | expression_kind | TEXT NOT NULL | Discriminator |
| KEEP | expression_type | TEXT | Preserved (subtype) |
| REMOVE | subtype | TEXT | Replaced by expression_type |
| REMOVE | expression | TEXT | Too generic |
| REMOVE | variables | TEXT | Too generic |
| ADD | in_function | TEXT | All extractors |
| ADD | target | TEXT | extract_slice_operations |
| ADD | has_start | INTEGER | extract_slice_operations |
| ADD | has_stop | INTEGER | extract_slice_operations |
| ADD | has_step | INTEGER | extract_slice_operations |
| ADD | is_assignment | INTEGER | extract_slice_operations |
| ADD | element_count | INTEGER | extract_tuple_operations |
| ADD | operation | TEXT | Multiple extractors |
| ADD | has_rest | INTEGER | extract_unpacking_patterns |
| ADD | target_count | INTEGER | extract_unpacking_patterns |
| ADD | unpack_type | TEXT | extract_unpacking_patterns |
| ADD | pattern | TEXT | extract_none_patterns, extract_truthiness_patterns |
| ADD | uses_is | INTEGER | extract_none_patterns |
| ADD | format_type | TEXT | extract_string_formatting |
| ADD | has_expressions | INTEGER | extract_string_formatting |
| ADD | var_count | INTEGER | extract_string_formatting |
| ADD | context | TEXT | extract_ellipsis_usage |
| ADD | has_globals | INTEGER | extract_exec_eval_compile |
| ADD | has_locals | INTEGER | extract_exec_eval_compile |
| ADD | generator_function | TEXT | extract_generator_yields |
| ADD | yield_expr | TEXT | extract_generator_yields |
| ADD | yield_type | TEXT | extract_generator_yields |
| ADD | in_loop | INTEGER | extract_generator_yields |
| ADD | condition | TEXT | extract_generator_yields |
| ADD | awaited_expr | TEXT | extract_await_expressions |
| ADD | containing_function | TEXT | extract_await_expressions |

**Result**: ~50% sparsity (acceptable) vs 90% before decomposition

---

## 4. Exact Line Numbers for Code Changes

### 4.1 python_impl.py Changes

**File**: `theauditor/ast_extractors/python_impl.py`

| Lines | Current Code | Change Required |
|-------|--------------|-----------------|
| 872-875 | `loop['loop_type'] = 'for_loop'` | Change to `loop['loop_kind'] = 'for'` (preserve loop_type) |
| 877-880 | `loop['loop_type'] = 'while_loop'` | Change to `loop['loop_kind'] = 'while'` |
| 882-885 | `loop['loop_type'] = 'async_for_loop'` | Change to `loop['loop_kind'] = 'async_for'` |
| 887-890 | `stmt['branch_type'] = 'if'` | Change to `stmt['branch_kind'] = 'if'` |
| 892-895 | `stmt['branch_type'] = 'match'` | Change to `stmt['branch_kind'] = 'match'` |
| 897-900 | `stmt['expression_type'] = 'break_continue'` | Route to `python_control_statements` instead |
| 902-905 | `stmt['expression_type'] = 'assert'` | Route to `python_control_statements` instead |
| 907-910 | `stmt['expression_type'] = 'del'` | Route to `python_control_statements` instead |
| 918-921 | `stmt['expression_type'] = 'with'` | Route to `python_control_statements` instead |
| 665-668 | Routes to `python_expressions` | Route to `python_comprehensions` instead |
| 626-629 | `pattern['expression_type'] = 'recursion'` | Route to `python_functions_advanced` instead |
| 659-662 | `memo['expression_type'] = 'memoize'` | Route to `python_functions_advanced` instead |
| 649-652 | `lc['expression_type'] = 'complexity'` | Route to `python_loops` instead |
| 1003-1006 | `cp['expression_type'] = 'copy'` | Route to `python_protocols` instead |
| 972-976 | `dec['expression_type'] = 'class_decorator'` | Route to `python_class_features` instead |
| 419-421 | Flask blueprints SKIPPED | ADD wiring to `python_framework_config` |
| N/A | extract_python_exports not called | ADD call and route to `python_imports_advanced` |
| N/A | GraphQL resolvers not called | ADD calls and route to `python_framework_config` |

### 4.2 python_schema.py Changes

**File**: `theauditor/indexer/schemas/python_schema.py`

| Lines | Table | Changes |
|-------|-------|---------|
| 196-214 | PYTHON_LOOPS | Remove target, iterator, body_line_count; Add loop_kind, target_count, etc. |
| 216-234 | PYTHON_BRANCHES | Remove condition; Rename elif_count; Add branch_kind, many columns |
| 236-253 | PYTHON_FUNCTIONS_ADVANCED | Remove is_method; Add function_kind, many columns |
| 255-272 | PYTHON_IO_OPERATIONS | Remove is_taint_source/sink; Add io_kind, is_static, etc. |
| 274-291 | PYTHON_STATE_MUTATIONS | Remove value_expr; Add mutation_kind, operation, etc. |
| 297-313 | PYTHON_CLASS_FEATURES | Remove details JSON; Add feature_kind, all expanded columns |
| 315-330 | PYTHON_PROTOCOLS | Remove implemented_methods JSON; Add protocol_kind, all columns |
| 332-350 | PYTHON_DESCRIPTORS | Add descriptor_kind, many columns |
| 352-368 | PYTHON_TYPE_DEFINITIONS | Remove type_params/fields JSON; Add type_kind |
| 370-385 | PYTHON_LITERALS | Remove literal_values JSON; Add literal_kind, literal_value_1..5 |
| 391-410 | PYTHON_SECURITY_FINDINGS | Add finding_kind |
| 412-429 | PYTHON_TEST_CASES | Add test_kind |
| 431-448 | PYTHON_TEST_FIXTURES | Remove params JSON; Add fixture_kind |
| 450-470 | PYTHON_FRAMEWORK_CONFIG | Remove details/methods/schedule JSON; Add config_kind |
| 472-490 | PYTHON_VALIDATION_SCHEMAS | Remove validators JSON; Add schema_kind |
| 496-512 | PYTHON_OPERATORS | Add operator_kind |
| 514-529 | PYTHON_COLLECTIONS | Add collection_kind |
| 531-547 | PYTHON_STDLIB_USAGE | Add stdlib_kind |
| 549-566 | PYTHON_IMPORTS_ADVANCED | Add import_kind |
| 568-584 | PYTHON_EXPRESSIONS | Add expression_kind, reduce columns |
| N/A | NEW | Add PYTHON_COMPREHENSIONS |
| N/A | NEW | Add PYTHON_CONTROL_STATEMENTS |
| N/A | NEW | Add 5 junction tables |

### 4.3 python_storage.py Changes

**File**: `theauditor/indexer/storage/python_storage.py`

All storage handlers need updates to:
1. Use `*_kind` discriminator column names
2. Add new columns to .get() calls
3. Remove invented columns from .get() calls
4. Handle junction table population

### 4.4 python_database.py Changes

**File**: `theauditor/indexer/database/python_database.py`

All `add_python_*` method signatures need updates to match new schema columns.

New methods needed:
- `add_python_comprehension()`
- `add_python_control_statement()`
- `add_python_protocol_method()`
- `add_python_typeddict_field()`
- `add_python_fixture_param()`
- `add_python_schema_validator()`
- `add_python_framework_method()`

### 4.5 base_database.py Changes

**File**: `theauditor/indexer/database/base_database.py`

Update `FLUSH_ORDER` to include new tables in correct order:
```python
FLUSH_ORDER = [
    # ... existing tables ...

    # NEW: After existing tables, before junction tables
    'python_comprehensions',
    'python_control_statements',

    # NEW: Junction tables LAST (after parent tables)
    'python_protocol_methods',
    'python_typeddict_fields',
    'python_fixture_params',
    'python_schema_validators',
    'python_framework_methods',
]
```

---

## 5. Junction Table FK Population Pattern

### 5.1 Storage Handler Pattern

```python
# File: theauditor/indexer/storage/python_storage.py

import json

def _store_python_protocols(self, data: list, file_path: str) -> int:
    """Store protocols and populate junction table for implemented_methods."""
    rows_inserted = 0

    for record in data:
        # 1. Insert parent record and get ID
        protocol_id = self.db.add_python_protocol(
            file=file_path,
            line=record.get('line'),
            protocol_kind=record.get('protocol_kind'),
            protocol_type=record.get('protocol_type'),
            class_name=record.get('class_name'),
            has_iter=record.get('has_iter', 0),
            has_next=record.get('has_next', 0),
            # ... other columns ...
        )
        rows_inserted += 1

        # 2. Extract implemented_methods (may be JSON string or list)
        methods = record.get('implemented_methods', [])
        if isinstance(methods, str):
            try:
                methods = json.loads(methods)
            except json.JSONDecodeError:
                methods = []

        # 3. Insert junction table rows using parent ID
        for order, method_name in enumerate(methods):
            self.db.add_python_protocol_method(
                file=file_path,
                protocol_id=protocol_id,  # FK from step 1
                method_name=method_name,
                method_order=order
            )

    return rows_inserted
```

### 5.2 Database Mixin Pattern

```python
# File: theauditor/indexer/database/python_database.py

def add_python_protocol(
    self,
    file: str,
    line: int,
    protocol_kind: str,
    protocol_type: str = None,
    class_name: str = None,
    # ... all other columns ...
) -> int:
    """Insert protocol and return the inserted row ID."""
    cursor = self.conn.cursor()
    cursor.execute('''
        INSERT INTO python_protocols (
            file, line, protocol_kind, protocol_type, class_name, ...
        ) VALUES (?, ?, ?, ?, ?, ...)
    ''', (file, line, protocol_kind, protocol_type, class_name, ...))

    # CRITICAL: Return lastrowid for FK reference
    return cursor.lastrowid


def add_python_protocol_method(
    self,
    file: str,
    protocol_id: int,
    method_name: str,
    method_order: int = 0
) -> int:
    """Insert protocol method junction record."""
    cursor = self.conn.cursor()
    cursor.execute('''
        INSERT INTO python_protocol_methods (
            file, protocol_id, method_name, method_order
        ) VALUES (?, ?, ?, ?)
    ''', (file, protocol_id, method_name, method_order))

    return cursor.lastrowid
```

### 5.3 Batch Insert Modification

**Current Issue**: The current batch methods don't return IDs.

**Solution Options**:

1. **Single-row inserts for junction parents** (RECOMMENDED for this ticket):
   - Tables with junction children use single-row inserts
   - Return `cursor.lastrowid` for FK reference
   - Acceptable performance for expected data volumes

2. **Deferred junction population**:
   - Insert parent rows in batch
   - Query back IDs using (file, line) composite key
   - Insert junction rows
   - More complex, saves round trips

**Recommendation**: Use Option 1 for simplicity. Profile after implementation.

---

## 6. Flush Order Position

**Current flush_order** (from `base_database.py`):
```python
# End of current flush_order
'python_expressions',
```

**New flush_order additions**:
```python
# Parent tables (append after python_expressions)
'python_comprehensions',        # Position: after python_expressions
'python_control_statements',    # Position: after python_comprehensions

# Junction tables (MUST be LAST - after ALL parent tables)
'python_protocol_methods',      # After python_protocols
'python_typeddict_fields',      # After python_type_definitions
'python_fixture_params',        # After python_test_fixtures
'python_schema_validators',     # After python_validation_schemas
'python_framework_methods',     # After python_framework_config
```

**Why junction tables last**: ON DELETE CASCADE requires parent rows to exist first. If flushed before parents, FK constraint fails.

---

## 7. Verification Queries

After implementation, run these queries to verify correctness:

```sql
-- Verify no NULL in required columns
SELECT COUNT(*) as null_loop_kind FROM python_loops WHERE loop_kind IS NULL;
-- Expected: 0

-- Verify two-discriminator pattern preserved subtypes
SELECT loop_kind, loop_type, COUNT(*) as count
FROM python_loops
WHERE loop_type IS NOT NULL
GROUP BY loop_kind, loop_type;
-- Expected: rows with loop_kind='for' and loop_type='enumerate', 'zip', etc.

-- Verify junction tables populated
SELECT
    (SELECT COUNT(*) FROM python_protocol_methods) as protocol_methods,
    (SELECT COUNT(*) FROM python_typeddict_fields) as typeddict_fields,
    (SELECT COUNT(*) FROM python_fixture_params) as fixture_params;
-- Expected: > 0 for each (depends on sample code)

-- Verify JOIN works
SELECT p.class_name, pm.method_name
FROM python_protocols p
JOIN python_protocol_methods pm ON p.id = pm.protocol_id
LIMIT 10;
-- Expected: protocol class names with their implemented methods

-- Verify no JSON blobs remain
SELECT name FROM pragma_table_info('python_protocols')
WHERE name = 'implemented_methods';
-- Expected: 0 rows (column removed)

-- Verify data recovery (exports wired)
SELECT COUNT(*) FROM python_imports_advanced WHERE import_kind = 'export';
-- Expected: > 0 if sample code has __all__

-- Verify fidelity check would pass
-- (This is pseudo-code - actual check is in Python)
SELECT
    'python_loops' as table_name,
    COUNT(*) as row_count
FROM python_loops
UNION ALL
SELECT
    'python_branches' as table_name,
    COUNT(*) as row_count
FROM python_branches;
-- Expected: matches extraction manifest
```
