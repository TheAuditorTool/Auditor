"""
Python-specific schema definitions.

This module contains table schemas specific to Python frameworks and patterns:
- ORM models (SQLAlchemy, Django)
- HTTP routes (Flask, FastAPI, Django)
- Validation patterns (Pydantic)
- Decorators
- Control flow (loops, branches, exceptions)
- Security findings (injections, crypto, auth)
- Testing (fixtures, test cases)
- Framework configs (Flask, Django, Celery)

Design Philosophy:
- Python-only tables
- Framework-specific extractions
- Complements core schema with language-specific patterns
- Domain-grouped consolidated tables with discriminator columns

TABLE HISTORY:
- 2025-11-25: Reduced from 149 to 8 tables (consolidate-python-orphan-tables)
- 2025-11-25: Added 20 consolidated tables (wire-extractors-to-consolidated-schema)
- Current: 28 tables (8 original + 20 consolidated)
"""

from typing import Dict

from .utils import Column, TableSchema


# ============================================================================
# PYTHON-SPECIFIC TABLES (8 tables with verified consumers)
# ============================================================================

PYTHON_ORM_MODELS = TableSchema(
    name="python_orm_models",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("table_name", "TEXT"),
        Column("orm_type", "TEXT", nullable=False, default="'sqlalchemy'"),
    ],
    primary_key=["file", "model_name"],
    indexes=[
        ("idx_python_orm_models_file", ["file"]),
        ("idx_python_orm_models_type", ["orm_type"]),
    ]
)

PYTHON_ORM_FIELDS = TableSchema(
    name="python_orm_fields",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT"),
        Column("is_primary_key", "BOOLEAN", default="0"),
        Column("is_foreign_key", "BOOLEAN", default="0"),
        Column("foreign_key_target", "TEXT"),
    ],
    primary_key=["file", "model_name", "field_name"],
    indexes=[
        ("idx_python_orm_fields_file", ["file"]),
        ("idx_python_orm_fields_model", ["model_name"]),
        ("idx_python_orm_fields_foreign", ["is_foreign_key"]),
    ]
)

PYTHON_ROUTES = TableSchema(
    name="python_routes",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER"),
        Column("framework", "TEXT", nullable=False),
        Column("method", "TEXT"),
        Column("pattern", "TEXT"),
        Column("handler_function", "TEXT"),
        Column("has_auth", "BOOLEAN", default="0"),
        Column("dependencies", "TEXT"),
        Column("blueprint", "TEXT"),
    ],
    indexes=[
        ("idx_python_routes_file", ["file"]),
        ("idx_python_routes_framework", ["framework"]),
    ]
)

PYTHON_VALIDATORS = TableSchema(
    name="python_validators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("model_name", "TEXT", nullable=False),
        Column("field_name", "TEXT"),
        Column("validator_method", "TEXT", nullable=False),
        Column("validator_type", "TEXT", nullable=False),
    ],
    indexes=[
        ("idx_python_validators_file", ["file"]),
        ("idx_python_validators_model", ["model_name"]),
        ("idx_python_validators_type", ["validator_type"]),
    ]
)

PYTHON_PACKAGE_CONFIGS = TableSchema(
    name="python_package_configs",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("file_type", "TEXT", nullable=False),  # 'pyproject' | 'requirements'
        Column("project_name", "TEXT"),
        Column("project_version", "TEXT"),
        Column("dependencies", "TEXT"),  # JSON array of dependency dicts
        Column("optional_dependencies", "TEXT"),  # JSON object {group: [deps]}
        Column("build_system", "TEXT"),  # JSON object with build-backend info
        Column("indexed_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
    ],
    primary_key=["file_path"],
    indexes=[
        ("idx_python_package_configs_file", ["file_path"]),
        ("idx_python_package_configs_type", ["file_type"]),
        ("idx_python_package_configs_project", ["project_name"]),
    ]
)

PYTHON_DECORATORS = TableSchema(
    name="python_decorators",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("decorator_name", "TEXT", nullable=False),
        Column("decorator_type", "TEXT", nullable=False),
        Column("target_type", "TEXT", nullable=False),
        Column("target_name", "TEXT", nullable=False),
        Column("is_async", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "decorator_name", "target_name"],
    indexes=[
        ("idx_python_decorators_file", ["file"]),
        ("idx_python_decorators_type", ["decorator_type"]),
        ("idx_python_decorators_target", ["target_name"]),
    ]
)

PYTHON_DJANGO_VIEWS = TableSchema(
    name="python_django_views",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("view_class_name", "TEXT", nullable=False),
        Column("view_type", "TEXT", nullable=False),
        Column("base_view_class", "TEXT"),
        Column("model_name", "TEXT"),
        Column("template_name", "TEXT"),
        Column("has_permission_check", "BOOLEAN", default="0"),
        Column("http_method_names", "TEXT"),
        Column("has_get_queryset_override", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "view_class_name"],
    indexes=[
        ("idx_python_django_views_file", ["file"]),
        ("idx_python_django_views_type", ["view_type"]),
        ("idx_python_django_views_model", ["model_name"]),
        ("idx_python_django_views_no_perm", ["has_permission_check"]),
    ]
)

PYTHON_DJANGO_MIDDLEWARE = TableSchema(
    name="python_django_middleware",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("middleware_class_name", "TEXT", nullable=False),
        Column("has_process_request", "BOOLEAN", default="0"),
        Column("has_process_response", "BOOLEAN", default="0"),
        Column("has_process_exception", "BOOLEAN", default="0"),
        Column("has_process_view", "BOOLEAN", default="0"),
        Column("has_process_template_response", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "line", "middleware_class_name"],
    indexes=[
        ("idx_python_django_middleware_file", ["file"]),
        ("idx_python_django_middleware_request", ["has_process_request"]),
    ]
)


# ============================================================================
# CONSOLIDATED PYTHON TABLES (20 new tables - Phase 2 Wire Extractors)
# ============================================================================

# -----------------------------------------------------------------------------
# GROUP 1: Control & Data Flow (5 tables)
# -----------------------------------------------------------------------------

PYTHON_LOOPS = TableSchema(
    name="python_loops",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern: loop_kind (table discriminator) + loop_type (preserved subtype)
        Column("loop_kind", "TEXT", nullable=False),  # 'for', 'while', 'async_for', 'complexity_analysis'
        Column("loop_type", "TEXT"),                  # Extractor's subtype (e.g., 'enumerate', 'zip') - NOT overwritten
        # From extract_for_loops, extract_while_loops, extract_async_for_loops
        Column("has_else", "INTEGER", default="0"),
        Column("nesting_level", "INTEGER", default="0"),
        Column("target_count", "INTEGER"),            # extract_for_loops, extract_async_for_loops
        Column("in_function", "TEXT"),                # All extractors
        Column("is_infinite", "INTEGER", default="0"),  # extract_while_loops
        # From extract_loop_complexity (re-routed from python_expressions)
        Column("estimated_complexity", "TEXT"),       # 'O(n)', 'O(n^2)', etc.
        Column("has_growing_operation", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_loops_file", ["file"]),
        ("idx_python_loops_kind", ["loop_kind"]),
        ("idx_python_loops_function", ["in_function"]),
    ]
)

PYTHON_BRANCHES = TableSchema(
    name="python_branches",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern: branch_kind (table discriminator) + branch_type (preserved subtype)
        Column("branch_kind", "TEXT", nullable=False),  # 'if', 'match', 'raise', 'except', 'finally'
        Column("branch_type", "TEXT"),                  # Extractor's subtype - NOT overwritten
        # From extract_if_statements
        Column("has_else", "INTEGER", default="0"),
        Column("has_elif", "INTEGER", default="0"),     # Renamed from elif_count (it's boolean)
        Column("chain_length", "INTEGER"),
        Column("has_complex_condition", "INTEGER", default="0"),
        Column("nesting_level", "INTEGER", default="0"),
        # From extract_match_statements
        Column("case_count", "INTEGER", default="0"),
        Column("has_guards", "INTEGER", default="0"),
        Column("has_wildcard", "INTEGER", default="0"),
        Column("pattern_types", "TEXT"),               # JSON array or comma-separated
        # From extract_exception_catches
        Column("exception_types", "TEXT"),             # Renamed from exception_type (plural for catches)
        Column("handling_strategy", "TEXT"),
        Column("variable_name", "TEXT"),
        # From extract_exception_raises
        Column("exception_type", "TEXT"),              # Singular for raises
        Column("is_re_raise", "INTEGER", default="0"),
        Column("from_exception", "TEXT"),
        Column("message", "TEXT"),
        Column("condition", "TEXT"),                   # For raises (e.g., "if error")
        # From extract_finally_blocks
        Column("has_cleanup", "INTEGER", default="0"),
        Column("cleanup_calls", "TEXT"),
        # Common
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_branches_file", ["file"]),
        ("idx_python_branches_kind", ["branch_kind"]),
        ("idx_python_branches_function", ["in_function"]),
    ]
)

PYTHON_FUNCTIONS_ADVANCED = TableSchema(
    name="python_functions_advanced",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern: function_kind (table discriminator) + function_type (preserved subtype)
        Column("function_kind", "TEXT", nullable=False),  # 'generator', 'async', 'lambda', 'context_manager', 'async_generator', 'recursive', 'memoized'
        Column("function_type", "TEXT"),                  # Preserved (generator_type, context_type, recursion_type, memoization_type)
        Column("name", "TEXT"),                           # extract_generators
        Column("function_name", "TEXT"),                  # extract_async_functions, extract_recursion/memoization
        # From extract_generators
        Column("yield_count", "INTEGER", default="0"),
        Column("has_send", "INTEGER", default="0"),
        Column("has_yield_from", "INTEGER", default="0"),
        Column("is_infinite", "INTEGER", default="0"),
        # From extract_async_functions
        Column("await_count", "INTEGER", default="0"),
        Column("has_async_for", "INTEGER", default="0"),
        Column("has_async_with", "INTEGER", default="0"),
        # From extract_lambda_functions
        Column("parameter_count", "INTEGER"),
        Column("parameters", "TEXT"),
        Column("body", "TEXT"),
        Column("captures_closure", "INTEGER", default="0"),
        Column("captured_vars", "TEXT"),
        Column("used_in", "TEXT"),
        # From extract_python_context_managers
        Column("as_name", "TEXT"),
        Column("context_expr", "TEXT"),
        Column("is_async", "INTEGER", default="0"),
        # From extract_async_generators
        Column("iter_expr", "TEXT"),
        Column("target_var", "TEXT"),
        # From extract_recursion_patterns (re-routed from python_expressions)
        Column("base_case_line", "INTEGER"),
        Column("calls_function", "TEXT"),
        Column("recursion_type", "TEXT"),
        # From extract_memoization_patterns (re-routed from python_expressions)
        Column("cache_size", "INTEGER"),
        Column("memoization_type", "TEXT"),
        Column("is_recursive", "INTEGER", default="0"),
        Column("has_memoization", "INTEGER", default="0"),
        # Common
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_functions_advanced_file", ["file"]),
        ("idx_python_functions_advanced_kind", ["function_kind"]),
        ("idx_python_functions_advanced_function", ["in_function"]),
    ]
)

PYTHON_IO_OPERATIONS = TableSchema(
    name="python_io_operations",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern: io_kind (table discriminator) + io_type (preserved subtype)
        Column("io_kind", "TEXT", nullable=False),  # 'file', 'network', 'database', 'process', 'param_flow', 'closure', 'nonlocal', 'conditional'
        Column("io_type", "TEXT"),                  # Extractor's subtype - NOT overwritten
        # From extract_io_operations
        Column("operation", "TEXT"),                # 'read', 'write', 'open', 'close', etc.
        Column("target", "TEXT"),
        Column("is_static", "INTEGER", default="0"),
        # From extract_parameter_return_flow
        Column("flow_type", "TEXT"),
        Column("function_name", "TEXT"),
        Column("parameter_name", "TEXT"),
        Column("return_expr", "TEXT"),
        Column("is_async", "INTEGER", default="0"),
        # Common
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_io_operations_file", ["file"]),
        ("idx_python_io_operations_kind", ["io_kind"]),
        ("idx_python_io_operations_function", ["in_function"]),
    ]
)

PYTHON_STATE_MUTATIONS = TableSchema(
    name="python_state_mutations",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern: mutation_kind (table discriminator) + mutation_type (preserved subtype)
        Column("mutation_kind", "TEXT", nullable=False),  # 'instance', 'class', 'global', 'argument', 'augmented'
        Column("mutation_type", "TEXT"),                  # Extractor's subtype - NOT overwritten
        Column("target", "TEXT"),
        # From extract_augmented_assignments
        Column("operator", "TEXT"),
        Column("target_type", "TEXT"),
        # From extract_instance_mutations
        Column("operation", "TEXT"),
        Column("is_init", "INTEGER", default="0"),
        Column("is_dunder_method", "INTEGER", default="0"),
        Column("is_property_setter", "INTEGER", default="0"),
        # Common
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_state_mutations_file", ["file"]),
        ("idx_python_state_mutations_kind", ["mutation_kind"]),
        ("idx_python_state_mutations_function", ["in_function"]),
    ]
)

# -----------------------------------------------------------------------------
# GROUP 2: Object-Oriented & Types (5 tables)
# -----------------------------------------------------------------------------

PYTHON_CLASS_FEATURES = TableSchema(
    name="python_class_features",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern
        Column("feature_kind", "TEXT", nullable=False),  # 'metaclass', 'dataclass', 'enum', 'slots', 'abstract', 'method_type', 'dunder', 'visibility', 'class_decorator', 'inheritance'
        Column("feature_type", "TEXT"),                  # Preserved subtype from extractor
        # Common columns
        Column("class_name", "TEXT"),
        Column("name", "TEXT"),
        Column("in_class", "TEXT"),
        # From extract_metaclasses
        Column("metaclass_name", "TEXT"),
        Column("is_definition", "INTEGER", default="0"),
        # From extract_dataclasses
        Column("field_count", "INTEGER"),
        Column("frozen", "INTEGER", default="0"),
        # From extract_enums
        Column("enum_name", "TEXT"),
        Column("enum_type", "TEXT"),
        Column("member_count", "INTEGER"),
        # From extract_slots
        Column("slot_count", "INTEGER"),
        # From extract_abstract_classes
        Column("abstract_method_count", "INTEGER"),
        # From extract_method_types, extract_dunder_methods
        Column("method_name", "TEXT"),
        Column("method_type", "TEXT"),
        Column("category", "TEXT"),
        # From extract_visibility_conventions
        Column("visibility", "TEXT"),
        Column("is_name_mangled", "INTEGER", default="0"),
        # From extract_class_decorators (re-routed)
        Column("decorator", "TEXT"),
        Column("decorator_type", "TEXT"),
        Column("has_arguments", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_class_features_file", ["file"]),
        ("idx_python_class_features_kind", ["feature_kind"]),
    ]
)

PYTHON_PROTOCOLS = TableSchema(
    name="python_protocols",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern
        Column("protocol_kind", "TEXT", nullable=False),  # 'iterator', 'container', 'callable', 'comparison', 'arithmetic', 'pickle', 'context_manager', 'copy'
        Column("protocol_type", "TEXT"),                  # Preserved subtype from extractor
        # Common
        Column("class_name", "TEXT"),
        Column("in_function", "TEXT"),
        # From extract_iterator_protocol
        Column("has_iter", "INTEGER", default="0"),
        Column("has_next", "INTEGER", default="0"),
        Column("is_generator", "INTEGER", default="0"),
        Column("raises_stopiteration", "INTEGER", default="0"),
        # From extract_container_protocol
        Column("has_contains", "INTEGER", default="0"),
        Column("has_getitem", "INTEGER", default="0"),
        Column("has_setitem", "INTEGER", default="0"),
        Column("has_delitem", "INTEGER", default="0"),
        Column("has_len", "INTEGER", default="0"),
        Column("is_mapping", "INTEGER", default="0"),
        Column("is_sequence", "INTEGER", default="0"),
        # From extract_callable_protocol
        Column("has_args", "INTEGER", default="0"),
        Column("has_kwargs", "INTEGER", default="0"),
        Column("param_count", "INTEGER"),
        # From extract_pickle_protocol
        Column("has_getstate", "INTEGER", default="0"),
        Column("has_setstate", "INTEGER", default="0"),
        Column("has_reduce", "INTEGER", default="0"),
        Column("has_reduce_ex", "INTEGER", default="0"),
        # From extract_context_managers (exception_flow)
        Column("context_expr", "TEXT"),
        Column("resource_type", "TEXT"),
        Column("variable_name", "TEXT"),
        Column("is_async", "INTEGER", default="0"),
        # From extract_copy_protocol (re-routed)
        Column("has_copy", "INTEGER", default="0"),
        Column("has_deepcopy", "INTEGER", default="0"),
        # NOTE: implemented_methods JSON REMOVED -> python_protocol_methods junction table
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_protocols_file", ["file"]),
        ("idx_python_protocols_kind", ["protocol_kind"]),
    ]
)

PYTHON_DESCRIPTORS = TableSchema(
    name="python_descriptors",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern
        Column("descriptor_kind", "TEXT", nullable=False),  # 'property', 'descriptor', 'dynamic_attr', 'cached_property', 'descriptor_protocol', 'attr_access'
        Column("descriptor_type", "TEXT"),                  # Preserved subtype from extractor
        # Common
        Column("name", "TEXT"),
        Column("class_name", "TEXT"),
        Column("in_class", "TEXT"),
        # From extract_descriptors, extract_descriptor_protocol (renamed from has_getter/setter/deleter)
        Column("has_get", "INTEGER", default="0"),
        Column("has_set", "INTEGER", default="0"),
        Column("has_delete", "INTEGER", default="0"),
        Column("is_data_descriptor", "INTEGER", default="0"),
        # From extract_property_patterns
        Column("property_name", "TEXT"),
        Column("access_type", "TEXT"),
        Column("has_computation", "INTEGER", default="0"),
        Column("has_validation", "INTEGER", default="0"),
        # From extract_cached_property
        Column("method_name", "TEXT"),
        Column("is_functools", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_descriptors_file", ["file"]),
        ("idx_python_descriptors_kind", ["descriptor_kind"]),
    ]
)

PYTHON_TYPE_DEFINITIONS = TableSchema(
    name="python_type_definitions",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # type_kind already serves as discriminator
        Column("type_kind", "TEXT", nullable=False),  # 'typed_dict', 'generic', 'protocol'
        Column("name", "TEXT"),
        # From extract_generics - expanded from type_params JSON
        Column("type_param_count", "INTEGER"),
        Column("type_param_1", "TEXT"),
        Column("type_param_2", "TEXT"),
        Column("type_param_3", "TEXT"),
        Column("type_param_4", "TEXT"),
        Column("type_param_5", "TEXT"),
        # From extract_protocols (type_extractors)
        Column("is_runtime_checkable", "INTEGER", default="0"),
        Column("methods", "TEXT"),  # Simple comma-separated (not a big JSON)
        # From extract_typed_dicts - typeddict_name stored in 'name'
        # NOTE: fields JSON REMOVED -> python_typeddict_fields junction table
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_type_definitions_file", ["file"]),
        ("idx_python_type_definitions_kind", ["type_kind"]),
    ]
)

PYTHON_LITERALS = TableSchema(
    name="python_literals",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern
        Column("literal_kind", "TEXT", nullable=False),  # 'literal', 'overload'
        Column("literal_type", "TEXT"),                  # Preserved subtype from extractor
        Column("name", "TEXT"),
        # From extract_literals - expanded from literal_values JSON (bounded array)
        Column("literal_value_1", "TEXT"),
        Column("literal_value_2", "TEXT"),
        Column("literal_value_3", "TEXT"),
        Column("literal_value_4", "TEXT"),
        Column("literal_value_5", "TEXT"),
        # From extract_overloads
        Column("function_name", "TEXT"),
        Column("overload_count", "INTEGER"),
        Column("variants", "TEXT"),  # Comma-separated variant signatures
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_literals_file", ["file"]),
        ("idx_python_literals_kind", ["literal_kind"]),
    ]
)

# -----------------------------------------------------------------------------
# GROUP 3: Security & Testing (5 tables)
# -----------------------------------------------------------------------------

PYTHON_SECURITY_FINDINGS = TableSchema(
    name="python_security_findings",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Discriminators (two-column pattern)
        Column("finding_kind", "TEXT", nullable=False),   # Discriminator: 'auth', 'command_injection', 'crypto', 'dangerous_eval', 'jwt', 'password', 'path_traversal', 'sql_injection'
        Column("finding_type", "TEXT"),                   # Extractor's subtype (preserved)
        # From extract_auth_decorators
        Column("function_name", "TEXT"),
        Column("decorator_name", "TEXT"),
        Column("permissions", "TEXT"),
        # From extract_command_injection_patterns
        Column("is_vulnerable", "INTEGER", default="0"),
        Column("shell_true", "INTEGER", default="0"),
        # From extract_dangerous_eval_exec
        Column("is_constant_input", "INTEGER", default="0"),
        Column("is_critical", "INTEGER", default="0"),
        # From extract_path_traversal_patterns
        Column("has_concatenation", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_security_findings_file", ["file"]),
        ("idx_python_security_findings_kind", ["finding_kind"]),
    ]
)

PYTHON_TEST_CASES = TableSchema(
    name="python_test_cases",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Discriminators (two-column pattern)
        Column("test_kind", "TEXT", nullable=False),    # Discriminator: 'unittest', 'assertion'
        Column("test_type", "TEXT"),                    # Extractor's subtype (preserved)
        # From extract_assertion_patterns
        Column("name", "TEXT"),
        Column("function_name", "TEXT"),
        Column("class_name", "TEXT"),
        Column("assertion_type", "TEXT"),
        Column("test_expr", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_test_cases_file", ["file"]),
        ("idx_python_test_cases_kind", ["test_kind"]),
    ]
)

PYTHON_TEST_FIXTURES = TableSchema(
    name="python_test_fixtures",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Discriminators (two-column pattern)
        Column("fixture_kind", "TEXT", nullable=False),   # Discriminator: 'fixture', 'parametrize', 'marker', 'mock', 'plugin_hook', 'hypothesis'
        Column("fixture_type", "TEXT"),                   # Extractor's subtype (preserved)
        # From pytest extractors
        Column("name", "TEXT"),
        Column("scope", "TEXT"),              # 'function', 'class', 'module', 'session'
        Column("autouse", "INTEGER", default="0"),
        Column("in_function", "TEXT"),
        # NOTE: params removed - moved to python_fixture_params junction table
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_test_fixtures_file", ["file"]),
        ("idx_python_test_fixtures_kind", ["fixture_kind"]),
    ]
)

PYTHON_FRAMEWORK_CONFIG = TableSchema(
    name="python_framework_config",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Discriminators (two-column pattern)
        Column("config_kind", "TEXT", nullable=False),    # Discriminator: 'app', 'extension', 'hook', 'error_handler', 'task', 'signal', 'admin', 'form', 'middleware', 'blueprint', 'resolver', etc.
        Column("config_type", "TEXT"),                    # Extractor's subtype (preserved)
        # Common columns
        Column("framework", "TEXT", nullable=False),      # 'flask', 'celery', 'django', 'graphene', 'ariadne', 'strawberry'
        Column("name", "TEXT"),
        Column("endpoint", "TEXT"),
        # From extract_flask_cache_decorators
        Column("cache_type", "TEXT"),
        Column("timeout", "INTEGER"),
        # From extract_django_middleware (boolean flags instead of JSON)
        Column("has_process_request", "INTEGER", default="0"),
        Column("has_process_response", "INTEGER", default="0"),
        Column("has_process_exception", "INTEGER", default="0"),
        Column("has_process_view", "INTEGER", default="0"),
        Column("has_process_template_response", "INTEGER", default="0"),
        # NOTE: methods removed - moved to python_framework_methods junction table
        # NOTE: schedule, details JSON removed - expanded to specific columns above
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_framework_config_file", ["file"]),
        ("idx_python_framework_config_framework", ["framework"]),
        ("idx_python_framework_config_kind", ["config_kind"]),
    ]
)

PYTHON_VALIDATION_SCHEMAS = TableSchema(
    name="python_validation_schemas",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Discriminators (two-column pattern)
        Column("schema_kind", "TEXT", nullable=False),    # Discriminator: 'schema', 'field', 'serializer', 'form'
        Column("schema_type", "TEXT"),                    # Extractor's subtype (preserved)
        # Common columns
        Column("framework", "TEXT", nullable=False),      # 'marshmallow', 'drf', 'wtforms'
        Column("name", "TEXT"),
        Column("field_type", "TEXT"),
        Column("required", "INTEGER", default="0"),
        # NOTE: validators removed - moved to python_schema_validators junction table
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_validation_schemas_file", ["file"]),
        ("idx_python_validation_schemas_framework", ["framework"]),
        ("idx_python_validation_schemas_kind", ["schema_kind"]),
    ]
)

# -----------------------------------------------------------------------------
# GROUP 4: Low-Level & Misc (5 tables)
# -----------------------------------------------------------------------------

PYTHON_OPERATORS = TableSchema(
    name="python_operators",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern: operator_kind (table discriminator) + operator_type (preserved subtype)
        Column("operator_kind", "TEXT", nullable=False),  # 'binary', 'unary', 'membership', 'chained', 'ternary', 'walrus', 'matmul'
        Column("operator_type", "TEXT"),                  # Extractor's subtype - NOT overwritten
        Column("operator", "TEXT"),
        Column("in_function", "TEXT"),
        # From extract_membership_tests
        Column("container_type", "TEXT"),
        # From extract_chained_comparisons
        Column("chain_length", "INTEGER"),
        Column("operators", "TEXT"),                       # Comma-separated list
        # From extract_ternary_expressions
        Column("has_complex_condition", "INTEGER", default="0"),
        # From extract_walrus_operators
        Column("variable", "TEXT"),
        Column("used_in", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_operators_file", ["file"]),
        ("idx_python_operators_kind", ["operator_kind"]),
        ("idx_python_operators_function", ["in_function"]),
    ]
)

PYTHON_COLLECTIONS = TableSchema(
    name="python_collections",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern: collection_kind (table discriminator) + collection_type (preserved subtype)
        Column("collection_kind", "TEXT", nullable=False),  # 'dict', 'list', 'set', 'string', 'builtin'
        Column("collection_type", "TEXT"),                  # Extractor's subtype - NOT overwritten
        Column("operation", "TEXT"),
        Column("method", "TEXT"),
        Column("in_function", "TEXT"),
        # From extract_dict_operations
        Column("has_default", "INTEGER", default="0"),
        # From extract_list_mutations
        Column("mutates_in_place", "INTEGER", default="0"),
        # From extract_builtin_usage
        Column("builtin", "TEXT"),
        Column("has_key", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_collections_file", ["file"]),
        ("idx_python_collections_kind", ["collection_kind"]),
        ("idx_python_collections_function", ["in_function"]),
    ]
)

PYTHON_STDLIB_USAGE = TableSchema(
    name="python_stdlib_usage",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern: stdlib_kind (table discriminator) + usage_type (preserved subtype)
        Column("stdlib_kind", "TEXT", nullable=False),    # 're', 'json', 'datetime', 'pathlib', 'logging', 'threading', 'contextlib', 'typing', 'weakref', 'contextvars'
        Column("module", "TEXT"),                         # Module name (may differ from stdlib_kind)
        Column("usage_type", "TEXT"),                     # Extractor's subtype - NOT overwritten
        Column("function_name", "TEXT"),
        Column("pattern", "TEXT"),                        # extract_contextlib_patterns
        Column("in_function", "TEXT"),
        # From extract_regex_patterns, extract_json_operations, etc.
        Column("operation", "TEXT"),
        Column("has_flags", "INTEGER", default="0"),      # extract_regex_patterns
        Column("direction", "TEXT"),                      # extract_json_operations
        Column("path_type", "TEXT"),                      # extract_path_operations
        Column("log_level", "TEXT"),                      # extract_logging_patterns
        Column("threading_type", "TEXT"),                 # extract_threading_patterns
        Column("is_decorator", "INTEGER", default="0"),   # extract_contextlib_patterns
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_stdlib_usage_file", ["file"]),
        ("idx_python_stdlib_usage_kind", ["stdlib_kind"]),
        ("idx_python_stdlib_usage_function", ["in_function"]),
    ]
)

PYTHON_IMPORTS_ADVANCED = TableSchema(
    name="python_imports_advanced",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern: import_kind (table discriminator) + import_type (preserved subtype)
        Column("import_kind", "TEXT", nullable=False),    # 'static', 'dynamic', 'namespace', 'module_attr', 'export'
        Column("import_type", "TEXT"),                    # Extractor's subtype - NOT overwritten
        Column("module", "TEXT"),
        Column("name", "TEXT"),
        Column("alias", "TEXT"),
        Column("is_relative", "INTEGER", default="0"),
        Column("in_function", "TEXT"),
        # From extract_import_statements
        Column("has_alias", "INTEGER", default="0"),
        Column("imported_names", "TEXT"),                 # Comma-separated list
        Column("is_wildcard", "INTEGER", default="0"),
        Column("relative_level", "INTEGER"),
        # From extract_module_attributes
        Column("attribute", "TEXT"),
        # CRITICAL: From extract_python_exports (previously UNWIRED)
        Column("is_default", "INTEGER", default="0"),     # Is default export
        Column("export_type", "TEXT"),                    # 'function', 'class', 'variable', etc.
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_imports_advanced_file", ["file"]),
        ("idx_python_imports_advanced_kind", ["import_kind"]),
        ("idx_python_imports_advanced_function", ["in_function"]),
    ]
)

PYTHON_EXPRESSIONS = TableSchema(
    name="python_expressions",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Two-discriminator pattern: expression_kind (table discriminator) + expression_type (preserved subtype)
        # REDUCED: comprehensions/control_statements moved to separate tables in Phase 2
        Column("expression_kind", "TEXT", nullable=False),  # 'slice', 'tuple', 'unpack', 'none', 'truthiness', 'format', 'ellipsis', 'bytes', 'exec', 'yield', 'await', 'resource'
        Column("expression_type", "TEXT"),                  # Extractor's subtype - NOT overwritten
        Column("in_function", "TEXT"),
        # From extract_slice_operations
        Column("target", "TEXT"),
        Column("has_start", "INTEGER", default="0"),
        Column("has_stop", "INTEGER", default="0"),
        Column("has_step", "INTEGER", default="0"),
        Column("is_assignment", "INTEGER", default="0"),
        # From extract_tuple_operations
        Column("element_count", "INTEGER"),
        Column("operation", "TEXT"),                        # Also used by bytes, exec
        # From extract_unpacking_patterns
        Column("has_rest", "INTEGER", default="0"),
        Column("target_count", "INTEGER"),
        Column("unpack_type", "TEXT"),
        # From extract_none_patterns, extract_truthiness_patterns
        Column("pattern", "TEXT"),
        Column("uses_is", "INTEGER", default="0"),
        # From extract_string_formatting
        Column("format_type", "TEXT"),
        Column("has_expressions", "INTEGER", default="0"),
        Column("var_count", "INTEGER"),
        # From extract_ellipsis_usage
        Column("context", "TEXT"),
        # From extract_exec_eval_compile
        Column("has_globals", "INTEGER", default="0"),
        Column("has_locals", "INTEGER", default="0"),
        # From extract_generator_yields
        Column("generator_function", "TEXT"),
        Column("yield_expr", "TEXT"),
        Column("yield_type", "TEXT"),
        Column("in_loop", "INTEGER", default="0"),
        Column("condition", "TEXT"),
        # From extract_await_expressions
        Column("awaited_expr", "TEXT"),
        Column("containing_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_python_expressions_file", ["file"]),
        ("idx_python_expressions_kind", ["expression_kind"]),
        ("idx_python_expressions_function", ["in_function"]),
    ]
)

# -----------------------------------------------------------------------------
# GROUP 5: Expression Decomposition (2 new tables - Phase 2 Fidelity Control)
# Split from python_expressions to reduce 90% NULL sparsity
# -----------------------------------------------------------------------------

PYTHON_COMPREHENSIONS = TableSchema(
    name="python_comprehensions",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Discriminators (two-column pattern)
        Column("comp_kind", "TEXT", nullable=False),   # 'list', 'dict', 'set', 'generator'
        Column("comp_type", "TEXT"),                   # Extractor's subtype (preserved)
        # From extract_comprehensions (extractor_truth.txt)
        Column("iteration_var", "TEXT"),
        Column("iteration_source", "TEXT"),
        Column("result_expr", "TEXT"),
        Column("filter_expr", "TEXT"),
        Column("has_filter", "INTEGER", default="0"),
        Column("nesting_level", "INTEGER", default="0"),
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_pcomp_file", ["file"]),
        ("idx_pcomp_kind", ["comp_kind"]),
        ("idx_pcomp_function", ["in_function"]),
    ]
)

PYTHON_CONTROL_STATEMENTS = TableSchema(
    name="python_control_statements",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        # Discriminators (two-column pattern)
        Column("statement_kind", "TEXT", nullable=False),  # 'break', 'continue', 'pass', 'assert', 'del', 'with'
        Column("statement_type", "TEXT"),                  # Extractor's subtype (preserved)
        # From extract_break_continue_pass
        Column("loop_type", "TEXT"),
        # From extract_assert_statements
        Column("condition_type", "TEXT"),
        Column("has_message", "INTEGER", default="0"),
        # From extract_del_statements
        Column("target_count", "INTEGER"),
        Column("target_type", "TEXT"),
        # From extract_with_statements
        Column("context_count", "INTEGER"),
        Column("has_alias", "INTEGER", default="0"),
        Column("is_async", "INTEGER", default="0"),
        # Common
        Column("in_function", "TEXT"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_pcs_file", ["file"]),
        ("idx_pcs_kind", ["statement_kind"]),
        ("idx_pcs_function", ["in_function"]),
    ]
)


# -----------------------------------------------------------------------------
# GROUP 6: Junction Tables (Phase 4 Fidelity Control - eliminate JSON blobs)
# -----------------------------------------------------------------------------

# Junction table for python_protocols.implemented_methods (JSON blob removed)
PYTHON_PROTOCOL_METHODS = TableSchema(
    name="python_protocol_methods",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("protocol_id", "INTEGER", nullable=False),  # FK to python_protocols.id
        Column("method_name", "TEXT", nullable=False),
        Column("method_order", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_ppm_file", ["file"]),
        ("idx_ppm_protocol", ["protocol_id"]),
        ("idx_ppm_method", ["method_name"]),
    ],
    foreign_keys=[
        ("protocol_id", "python_protocols", "id", "CASCADE"),
    ]
)

# Junction table for python_type_definitions.fields (JSON blob removed - TypedDict fields)
PYTHON_TYPEDDICT_FIELDS = TableSchema(
    name="python_typeddict_fields",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("typeddict_id", "INTEGER", nullable=False),  # FK to python_type_definitions.id
        Column("field_name", "TEXT", nullable=False),
        Column("field_type", "TEXT"),
        Column("required", "INTEGER", default="1"),
        Column("field_order", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_ptf_file", ["file"]),
        ("idx_ptf_typeddict", ["typeddict_id"]),
        ("idx_ptf_field", ["field_name"]),
    ],
    foreign_keys=[
        ("typeddict_id", "python_type_definitions", "id", "CASCADE"),
    ]
)

# Junction table for python_test_fixtures.params (JSON blob removed - Phase 5)
PYTHON_FIXTURE_PARAMS = TableSchema(
    name="python_fixture_params",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("fixture_id", "INTEGER", nullable=False),  # FK to python_test_fixtures.id
        Column("param_name", "TEXT"),
        Column("param_value", "TEXT"),
        Column("param_order", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_pfp_file", ["file"]),
        ("idx_pfp_fixture", ["fixture_id"]),
    ],
    foreign_keys=[
        ("fixture_id", "python_test_fixtures", "id", "CASCADE"),
    ]
)

# Junction table for python_framework_config.methods (JSON blob removed - Phase 5)
PYTHON_FRAMEWORK_METHODS = TableSchema(
    name="python_framework_methods",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("config_id", "INTEGER", nullable=False),  # FK to python_framework_config.id
        Column("method_name", "TEXT", nullable=False),
        Column("method_order", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_pfm_file", ["file"]),
        ("idx_pfm_config", ["config_id"]),
        ("idx_pfm_method", ["method_name"]),
    ],
    foreign_keys=[
        ("config_id", "python_framework_config", "id", "CASCADE"),
    ]
)

# Junction table for python_validation_schemas.validators (JSON blob removed - Phase 5)
PYTHON_SCHEMA_VALIDATORS = TableSchema(
    name="python_schema_validators",
    columns=[
        Column("id", "INTEGER", autoincrement=True),
        Column("file", "TEXT", nullable=False),
        Column("schema_id", "INTEGER", nullable=False),  # FK to python_validation_schemas.id
        Column("validator_name", "TEXT", nullable=False),
        Column("validator_type", "TEXT"),
        Column("validator_order", "INTEGER", default="0"),
    ],
    primary_key=["id"],
    indexes=[
        ("idx_psv_file", ["file"]),
        ("idx_psv_schema", ["schema_id"]),
        ("idx_psv_validator", ["validator_name"]),
    ],
    foreign_keys=[
        ("schema_id", "python_validation_schemas", "id", "CASCADE"),
    ]
)


# ============================================================================
# PYTHON TABLES REGISTRY (35 tables: 8 original + 20 consolidated + 2 decomposed + 5 junction)
# ============================================================================

PYTHON_TABLES: Dict[str, TableSchema] = {
    # =========================================================================
    # ORIGINAL TABLES (8 with verified consumers)
    # =========================================================================

    # ORM tables - consumers: overfetch.py, discovery.py, schema_cache_adapter.py
    "python_orm_models": PYTHON_ORM_MODELS,
    "python_orm_fields": PYTHON_ORM_FIELDS,

    # Routes - consumers: boundary_analyzer.py, deadcode_graph.py, query.py
    "python_routes": PYTHON_ROUTES,

    # Validators - consumers: discovery.py (via SchemaMemoryCache)
    "python_validators": PYTHON_VALIDATORS,

    # Package configs - consumers: deps.py, blueprint.py
    "python_package_configs": PYTHON_PACKAGE_CONFIGS,

    # Decorators - consumers: interceptors.py, deadcode_graph.py, query.py
    "python_decorators": PYTHON_DECORATORS,

    # Django - consumers: interceptors.py
    "python_django_views": PYTHON_DJANGO_VIEWS,
    "python_django_middleware": PYTHON_DJANGO_MIDDLEWARE,

    # =========================================================================
    # CONSOLIDATED TABLES (20 new - Phase 2 Wire Extractors)
    # =========================================================================

    # Group 1: Control & Data Flow
    "python_loops": PYTHON_LOOPS,
    "python_branches": PYTHON_BRANCHES,
    "python_functions_advanced": PYTHON_FUNCTIONS_ADVANCED,
    "python_io_operations": PYTHON_IO_OPERATIONS,
    "python_state_mutations": PYTHON_STATE_MUTATIONS,

    # Group 2: Object-Oriented & Types
    "python_class_features": PYTHON_CLASS_FEATURES,
    "python_protocols": PYTHON_PROTOCOLS,
    "python_descriptors": PYTHON_DESCRIPTORS,
    "python_type_definitions": PYTHON_TYPE_DEFINITIONS,
    "python_literals": PYTHON_LITERALS,

    # Group 3: Security & Testing
    "python_security_findings": PYTHON_SECURITY_FINDINGS,
    "python_test_cases": PYTHON_TEST_CASES,
    "python_test_fixtures": PYTHON_TEST_FIXTURES,
    "python_framework_config": PYTHON_FRAMEWORK_CONFIG,
    "python_validation_schemas": PYTHON_VALIDATION_SCHEMAS,

    # Group 4: Low-Level & Misc
    "python_operators": PYTHON_OPERATORS,
    "python_collections": PYTHON_COLLECTIONS,
    "python_stdlib_usage": PYTHON_STDLIB_USAGE,
    "python_imports_advanced": PYTHON_IMPORTS_ADVANCED,
    "python_expressions": PYTHON_EXPRESSIONS,

    # Group 5: Expression Decomposition (Phase 2 Fidelity Control)
    "python_comprehensions": PYTHON_COMPREHENSIONS,
    "python_control_statements": PYTHON_CONTROL_STATEMENTS,

    # Group 6: Junction Tables (Phase 4 + Phase 5 Fidelity Control)
    "python_protocol_methods": PYTHON_PROTOCOL_METHODS,
    "python_typeddict_fields": PYTHON_TYPEDDICT_FIELDS,
    "python_fixture_params": PYTHON_FIXTURE_PARAMS,
    "python_framework_methods": PYTHON_FRAMEWORK_METHODS,
    "python_schema_validators": PYTHON_SCHEMA_VALIDATORS,
}
