"""Python AST extraction - Modular architecture (Phase 2.1 - Oct 2025).

⚠️  IMPORTANT: THIS IS THE SINGLE SOURCE OF TRUTH FOR PYTHON EXTRACTION ⚠️

This package is imported as `python_impl` throughout the codebase:
  - Base AST parser: `from . import python as python_impl` (ast_extractors/__init__.py:51)
  - Python extractor: `from theauditor.ast_extractors import python as python_impl` (indexer/extractors/python.py:28)

OLD architecture (DEPRECATED):
  - python_impl.py (1594-line monolithic file) - kept for rollback only, NOT used in production

NEW architecture (ACTIVE):
  - This package (__init__.py) orchestrates modular extraction
  - All functions re-exported here for backward compatibility
  - Acts like JavaScript's js_helper_templates.py pattern (but with Python imports, not file reads)

Module Boundaries:
==================

core_extractors.py (812 lines):
    - Language fundamentals: imports, functions, classes, assignments
    - Core patterns: properties, calls, returns, exports
    - Type annotations and helper functions

framework_extractors.py (568 lines):
    - Web frameworks: Django, Flask, FastAPI
    - ORM frameworks: SQLAlchemy, Django ORM
    - Validators: Pydantic
    - Background tasks: Celery (Phase 2.2)

cdk_extractor.py (NEW - AWS CDK support):
    - AWS CDK Infrastructure-as-Code: CDK v2 construct extraction
    - Security property extraction for cloud infrastructure

cfg_extractor.py (290 lines):
    - Control Flow Graph extraction
    - Matches JavaScript cfg_extractor.js pattern

async_extractors.py: (Phase 2.2 - NOT YET IMPLEMENTED)
    - Async functions, await expressions
    - Async context managers, async generators
    - AsyncIO patterns

testing_extractors.py: (Phase 2.2 - NOT YET IMPLEMENTED)
    - pytest fixtures, parametrize, markers
    - unittest patterns, mocking

type_extractors.py: (Phase 2.2 - NOT YET IMPLEMENTED)
    - Advanced type system: Protocol, Generic, TypedDict
    - Literal types, overload decorators

Backward Compatibility (HOUSE OF CARDS - but it works!):
=========================================================
All functions are re-exported at package level for backward compatibility.
Existing code using `from python_impl import extract_*` will continue working
via re-exports in this __init__.py.

The import alias `python as python_impl` ensures ALL code paths use THIS package,
not the old python_impl.py monolith. This is the glue holding the refactor together.

Architecture Contract (CRITICAL - DO NOT VIOLATE):
==================================================
All extraction functions:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
This separation ensures single source of truth for file paths.

For Future Developers (AI and Human):
======================================
If you're reading this wondering "why are there two python_impl things?":
  1. python_impl.py = OLD monolith (DEPRECATED, kept for rollback)
  2. python/ package = NEW modular structure (THIS FILE - production)
  3. Import alias makes them interchangeable: `from . import python as python_impl`
  4. This is intentional technical debt - don't "fix" it without understanding the import chain

Verification Commands:
======================
# Test import resolution works correctly:
python -c "from theauditor.ast_extractors import python_impl; print(python_impl.__file__)"
# Should print: .../theauditor/ast_extractors/python/__init__.py (NOT python_impl.py)

# Test function availability:
python -c "from theauditor.ast_extractors import python_impl; print(hasattr(python_impl, 'extract_python_cdk_constructs'))"
# Should print: True (this function only exists in NEW package)
"""

from .advanced_extractors import (
    extract_attribute_access_protocol,
    extract_bytes_operations,
    extract_cached_property,
    extract_copy_protocol,
    extract_descriptor_protocol,
    extract_ellipsis_usage,
    extract_exec_eval_compile,
    extract_namespace_packages,
)
from .async_extractors import (
    extract_async_functions,
    extract_async_generators,
    extract_await_expressions,
)
from .cdk_extractor import (
    extract_python_cdk_constructs,
)
from .cfg_extractor import (
    extract_python_cfg,
)
from .class_feature_extractors import (
    extract_abstract_classes,
    extract_dataclasses,
    extract_descriptors,
    extract_dunder_methods,
    extract_enums,
    extract_metaclasses,
    extract_method_types,
    extract_multiple_inheritance,
    extract_slots,
    extract_visibility_conventions,
)
from .collection_extractors import (
    extract_builtin_usage,
    extract_collections_usage,
    extract_dict_operations,
    extract_functools_usage,
    extract_itertools_usage,
    extract_list_mutations,
    extract_set_operations,
    extract_string_methods,
)
from .control_flow_extractors import (
    extract_assert_statements,
    extract_async_for_loops,
    extract_break_continue_pass,
    extract_del_statements,
    extract_for_loops,
    extract_if_statements,
    extract_import_statements,
    extract_match_statements,
    extract_while_loops,
    extract_with_statements,
)
from .core_extractors import (
    extract_generators,
    extract_python_assignments,
    extract_python_attribute_annotations,
    extract_python_calls,
    extract_python_calls_with_args,
    extract_python_classes,
    extract_python_context_managers,
    extract_python_decorators,
    extract_python_dicts,
    extract_python_exports,
    extract_python_function_params,
    extract_python_functions,
    extract_python_imports,
    extract_python_properties,
    extract_python_returns,
)
from .django_advanced_extractors import (
    extract_django_managers,
    extract_django_querysets,
    extract_django_receivers,
    extract_django_signals,
)
from .flask_extractors import (
    extract_flask_app_factories,
    extract_flask_cache_decorators,
    extract_flask_cli_commands,
    extract_flask_cors_configs,
    extract_flask_error_handlers,
    extract_flask_extensions,
    extract_flask_rate_limits,
    extract_flask_request_hooks,
    extract_flask_websocket_handlers,
)
from .framework_extractors import (
    extract_celery_beat_schedules,
    extract_celery_task_calls,
    extract_celery_tasks,
    extract_django_admin,
    extract_django_cbvs,
    extract_django_definitions,
    extract_django_form_fields,
    extract_django_forms,
    extract_django_middleware,
    extract_drf_serializer_fields,
    extract_drf_serializers,
    extract_flask_blueprints,
    extract_marshmallow_fields,
    extract_marshmallow_schemas,
    extract_pydantic_validators,
    extract_sqlalchemy_definitions,
    extract_wtforms_fields,
    extract_wtforms_forms,
)
from .fundamental_extractors import (
    extract_comprehensions,
    extract_lambda_functions,
    extract_none_patterns,
    extract_slice_operations,
    extract_string_formatting,
    extract_truthiness_patterns,
    extract_tuple_operations,
    extract_unpacking_patterns,
)
from .operator_extractors import (
    extract_chained_comparisons,
    extract_matrix_multiplication,
    extract_membership_tests,
    extract_operators,
    extract_ternary_expressions,
    extract_walrus_operators,
)
from .protocol_extractors import (
    extract_arithmetic_protocol,
    extract_callable_protocol,
    extract_class_decorators,
    extract_comparison_protocol,
    extract_container_protocol,
    extract_contextvar_usage,
    extract_iterator_protocol,
    extract_module_attributes,
    extract_pickle_protocol,
    extract_weakref_usage,
)
from .security_extractors import (
    extract_auth_decorators,
    extract_command_injection_patterns,
    extract_crypto_operations,
    extract_dangerous_eval_exec,
    extract_jwt_operations,
    extract_password_hashing,
    extract_path_traversal_patterns,
    extract_sql_injection_patterns,
)
from .stdlib_pattern_extractors import (
    extract_contextlib_patterns,
    extract_datetime_operations,
    extract_json_operations,
    extract_logging_patterns,
    extract_path_operations,
    extract_regex_patterns,
    extract_threading_patterns,
    extract_type_checking,
)
from .testing_extractors import (
    extract_assertion_patterns,
    extract_hypothesis_strategies,
    extract_mock_patterns,
    extract_pytest_fixtures,
    extract_pytest_markers,
    extract_pytest_parametrize,
    extract_pytest_plugin_hooks,
    extract_unittest_test_cases,
)
from .type_extractors import (
    extract_generics,
    extract_literals,
    extract_overloads,
    extract_protocols,
    extract_typed_dicts,
)

__all__ = [
    "extract_python_functions",
    "extract_python_classes",
    "extract_python_attribute_annotations",
    "extract_python_imports",
    "extract_python_exports",
    "extract_python_assignments",
    "extract_python_function_params",
    "extract_python_calls_with_args",
    "extract_python_returns",
    "extract_python_properties",
    "extract_python_calls",
    "extract_python_dicts",
    "extract_python_decorators",
    "extract_python_context_managers",
    "extract_generators",
    "extract_sqlalchemy_definitions",
    "extract_django_definitions",
    "extract_pydantic_validators",
    "extract_flask_blueprints",
    "extract_django_cbvs",
    "extract_django_forms",
    "extract_django_form_fields",
    "extract_django_admin",
    "extract_django_middleware",
    "extract_marshmallow_schemas",
    "extract_marshmallow_fields",
    "extract_drf_serializers",
    "extract_drf_serializer_fields",
    "extract_wtforms_forms",
    "extract_wtforms_fields",
    "extract_celery_tasks",
    "extract_celery_task_calls",
    "extract_celery_beat_schedules",
    "extract_flask_app_factories",
    "extract_flask_extensions",
    "extract_flask_request_hooks",
    "extract_flask_error_handlers",
    "extract_flask_websocket_handlers",
    "extract_flask_cli_commands",
    "extract_flask_cors_configs",
    "extract_flask_rate_limits",
    "extract_flask_cache_decorators",
    "extract_python_cfg",
    "extract_python_cdk_constructs",
    "extract_async_functions",
    "extract_await_expressions",
    "extract_async_generators",
    "extract_pytest_fixtures",
    "extract_pytest_parametrize",
    "extract_pytest_markers",
    "extract_mock_patterns",
    "extract_unittest_test_cases",
    "extract_assertion_patterns",
    "extract_pytest_plugin_hooks",
    "extract_hypothesis_strategies",
    "extract_auth_decorators",
    "extract_password_hashing",
    "extract_jwt_operations",
    "extract_sql_injection_patterns",
    "extract_command_injection_patterns",
    "extract_path_traversal_patterns",
    "extract_dangerous_eval_exec",
    "extract_crypto_operations",
    "extract_django_signals",
    "extract_django_receivers",
    "extract_django_managers",
    "extract_django_querysets",
    "extract_protocols",
    "extract_generics",
    "extract_typed_dicts",
    "extract_literals",
    "extract_overloads",
    "extract_comprehensions",
    "extract_lambda_functions",
    "extract_slice_operations",
    "extract_tuple_operations",
    "extract_unpacking_patterns",
    "extract_none_patterns",
    "extract_truthiness_patterns",
    "extract_string_formatting",
    "extract_operators",
    "extract_membership_tests",
    "extract_chained_comparisons",
    "extract_ternary_expressions",
    "extract_walrus_operators",
    "extract_matrix_multiplication",
    "extract_dict_operations",
    "extract_list_mutations",
    "extract_set_operations",
    "extract_string_methods",
    "extract_builtin_usage",
    "extract_itertools_usage",
    "extract_functools_usage",
    "extract_collections_usage",
    "extract_metaclasses",
    "extract_descriptors",
    "extract_dataclasses",
    "extract_enums",
    "extract_slots",
    "extract_abstract_classes",
    "extract_method_types",
    "extract_multiple_inheritance",
    "extract_dunder_methods",
    "extract_visibility_conventions",
    "extract_regex_patterns",
    "extract_json_operations",
    "extract_datetime_operations",
    "extract_path_operations",
    "extract_logging_patterns",
    "extract_threading_patterns",
    "extract_contextlib_patterns",
    "extract_type_checking",
    "extract_for_loops",
    "extract_while_loops",
    "extract_async_for_loops",
    "extract_if_statements",
    "extract_match_statements",
    "extract_break_continue_pass",
    "extract_assert_statements",
    "extract_del_statements",
    "extract_import_statements",
    "extract_with_statements",
    "extract_iterator_protocol",
    "extract_container_protocol",
    "extract_callable_protocol",
    "extract_comparison_protocol",
    "extract_arithmetic_protocol",
    "extract_pickle_protocol",
    "extract_weakref_usage",
    "extract_contextvar_usage",
    "extract_module_attributes",
    "extract_class_decorators",
    "extract_namespace_packages",
    "extract_cached_property",
    "extract_descriptor_protocol",
    "extract_attribute_access_protocol",
    "extract_copy_protocol",
    "extract_ellipsis_usage",
    "extract_bytes_operations",
    "extract_exec_eval_compile",
]
