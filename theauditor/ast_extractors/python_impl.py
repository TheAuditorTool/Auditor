"""Python extraction delegation layer.

This module acts as the central coordinator for all Python extraction,
delegating to specialized extractors and merging their results.

ARCHITECTURAL ROLE
==================
This is the SINGLE delegation point between:
- python.py (the thin wrapper that builds FileContext)
- ast_extractors/python/* (the specialized extractors)

All extraction logic flows through this file, which:
1. Receives a FileContext from python.py
2. Delegates to all appropriate extractors
3. Merges and returns the unified result

This separation ensures:
- python.py remains a thin wrapper (~150 lines)
- Extraction logic is properly modularized
- No duplicate extraction code
"""

from typing import Any, Dict
from theauditor.ast_extractors.python.utils.context import FileContext
from theauditor.ast_extractors.python import (
    # Core extractors
    core_extractors,
    fundamental_extractors,

    # Framework extractors
    framework_extractors,
    flask_extractors,
    django_advanced_extractors,
    validation_extractors,
    orm_extractors,
    django_web_extractors,

    # Pattern extractors
    async_extractors,
    behavioral_extractors,
    collection_extractors,
    control_flow_extractors,
    data_flow_extractors,
    exception_flow_extractors,
    operator_extractors,
    performance_extractors,
    protocol_extractors,
    state_mutation_extractors,

    # Advanced extractors
    advanced_extractors,
    class_feature_extractors,
    security_extractors,
    stdlib_pattern_extractors,
    testing_extractors,
    type_extractors,

    # Specialized extractors
    cfg_extractor,
    cdk_extractor,
)


def extract_all_python_data(context: FileContext) -> Dict[str, Any]:
    """Extract all Python data by delegating to specialized extractors.

    This is the main entry point for Python extraction. It coordinates
    all specialized extractors and merges their results into a unified
    dictionary that matches the database schema.

    Args:
        context: FileContext containing AST tree and optimized node index

    Returns:
        Dictionary containing all extracted data, organized by table name
    """
    result = {
        # Core language features
        'imports': [],
        'symbols': [],
        'assignments': [],
        'function_calls': [],
        'returns': [],
        'variable_usage': [],
        'cfg': [],
        'object_literals': [],
        'type_annotations': [],
        'resolved_imports': {},

        # ORM and database
        'orm_relationships': [],
        'python_orm_models': [],
        'python_orm_fields': [],

        # Web frameworks
        'routes': [],  # Legacy field for backward compatibility
        'python_routes': [],
        'python_blueprints': [],
        'python_validators': [],

        # Infrastructure
        'cdk_constructs': [],
        'cdk_construct_properties': [],

        # Python-specific patterns (Phase 2.2A)
        'python_decorators': [],
        'python_context_managers': [],
        'python_async_functions': [],
        'python_await_expressions': [],
        'python_async_generators': [],
        'python_pytest_fixtures': [],
        'python_pytest_parametrize': [],
        'python_pytest_markers': [],
        'python_mock_patterns': [],
        'python_protocols': [],
        'python_generics': [],
        'python_typed_dicts': [],
        'python_literals': [],
        'python_overloads': [],

        # Django framework
        'python_django_views': [],
        'python_django_forms': [],
        'python_django_form_fields': [],
        'python_django_admin': [],
        'python_django_middleware': [],
        'python_django_signals': [],
        'python_django_receivers': [],
        'python_django_managers': [],
        'python_django_querysets': [],

        # Validation frameworks
        'python_marshmallow_schemas': [],
        'python_marshmallow_fields': [],
        'python_drf_serializers': [],
        'python_drf_serializer_fields': [],
        'python_wtforms_forms': [],
        'python_wtforms_fields': [],

        # Background tasks
        'python_celery_tasks': [],
        'python_celery_task_calls': [],
        'python_celery_beat_schedules': [],

        # Generators
        'python_generators': [],

        # Flask framework (Phase 3.1)
        'python_flask_apps': [],
        'python_flask_extensions': [],
        'python_flask_hooks': [],
        'python_flask_error_handlers': [],
        'python_flask_websockets': [],
        'python_flask_cli_commands': [],
        'python_flask_cors': [],
        'python_flask_rate_limits': [],
        'python_flask_cache': [],

        # Testing (Phase 3.2)
        'python_unittest_test_cases': [],
        'python_assertion_patterns': [],
        'python_pytest_plugin_hooks': [],
        'python_hypothesis_strategies': [],

        # Security (Phase 3.3)
        'python_auth_decorators': [],
        'python_password_hashing': [],
        'python_jwt_operations': [],
        'sql_queries': [],  # SQL query extraction from execute() calls
        'python_sql_injection': [],
        'python_command_injection': [],
        'python_path_traversal': [],
        'python_dangerous_eval': [],
        'python_crypto_operations': [],

        # State mutations (Causal Learning Week 1)
        'python_instance_mutations': [],
        'python_class_mutations': [],
        'python_global_mutations': [],
        'python_argument_mutations': [],
        'python_augmented_assignments': [],

        # Exception flow (Causal Learning Week 1)
        'python_exception_raises': [],
        'python_exception_catches': [],
        'python_finally_blocks': [],
        'python_context_managers_enhanced': [],

        # Data flow (Causal Learning Week 2)
        'python_io_operations': [],
        'python_parameter_return_flow': [],
        'python_closure_captures': [],
        'python_nonlocal_access': [],
        'python_conditional_calls': [],

        # Behavioral patterns (Causal Learning Week 3)
        'python_recursion_patterns': [],
        'python_generator_yields': [],
        'python_property_patterns': [],
        'python_dynamic_attributes': [],

        # Performance patterns (Causal Learning Week 4)
        'python_loop_complexity': [],
        'python_resource_usage': [],
        'python_memoization_patterns': [],

        # Python Coverage V2 - Week 1: Fundamentals
        'python_comprehensions': [],
        'python_lambda_functions': [],
        'python_slice_operations': [],
        'python_tuple_operations': [],
        'python_unpacking_patterns': [],
        'python_none_patterns': [],
        'python_truthiness_patterns': [],
        'python_string_formatting': [],

        # Python Coverage V2 - Week 2: Operators
        'python_operators': [],
        'python_membership_tests': [],
        'python_chained_comparisons': [],
        'python_ternary_expressions': [],
        'python_walrus_operators': [],
        'python_matrix_multiplication': [],

        # Python Coverage V2 - Week 3: Collections
        'python_dict_operations': [],
        'python_list_mutations': [],
        'python_set_operations': [],
        'python_string_methods': [],
        'python_builtin_usage': [],
        'python_itertools_usage': [],
        'python_functools_usage': [],
        'python_collections_usage': [],

        # Python Coverage V2 - Week 4: Advanced classes
        'python_metaclasses': [],
        'python_descriptors': [],
        'python_dataclasses': [],
        'python_enums': [],
        'python_slots': [],
        'python_abstract_classes': [],
        'python_method_types': [],
        'python_multiple_inheritance': [],
        'python_dunder_methods': [],
        'python_visibility_conventions': [],

        # Python Coverage V2 - Week 4: Stdlib
        'python_regex_patterns': [],
        'python_json_operations': [],
        'python_datetime_operations': [],
        'python_path_operations': [],
        'python_logging_patterns': [],
        'python_threading_patterns': [],
        'python_contextlib_patterns': [],
        'python_type_checking': [],

        # Python Coverage V2 - Week 5: Control flow
        'python_for_loops': [],
        'python_while_loops': [],
        'python_async_for_loops': [],
        'python_if_statements': [],
        'python_match_statements': [],
        'python_break_continue_pass': [],
        'python_assert_statements': [],
        'python_del_statements': [],
        'python_import_statements': [],
        'python_with_statements': [],

        # Python Coverage V2 - Week 6: Protocols
        'python_iterator_protocol': [],
        'python_container_protocol': [],
        'python_callable_protocol': [],
        'python_comparison_protocol': [],
        'python_arithmetic_protocol': [],
        'python_pickle_protocol': [],
        'python_weakref_usage': [],
        'python_contextvar_usage': [],
        'python_module_attributes': [],
        'python_class_decorators': [],

        # Python Coverage V2 - Advanced
        'python_namespace_packages': [],
        'python_cached_property': [],
        'python_descriptor_protocol': [],
        'python_attribute_access_protocol': [],
        'python_copy_protocol': [],
        'python_ellipsis_usage': [],
        'python_bytes_operations': [],
        'python_exec_eval_compile': [],
    }

    # Core extractors - These run for every Python file
    functions = core_extractors.extract_python_functions(context)
    if functions:
        # Add 'type' field for storage layer
        for func in functions:
            func['type'] = 'function'
        result['symbols'].extend(functions)

    classes = core_extractors.extract_python_classes(context)
    if classes:
        # Add 'type' field for storage layer
        for cls in classes:
            cls['type'] = 'class'
        result['symbols'].extend(classes)

    attribute_annotations = core_extractors.extract_python_attribute_annotations(context)
    if attribute_annotations:
        result['type_annotations'].extend(attribute_annotations)

    # Extract imports (resolved_imports still handled in python.py as it needs file_info)
    imports = core_extractors.extract_python_imports(context)
    if imports:
        result['imports'].extend(imports)

    assignments = core_extractors.extract_python_assignments(context)
    if assignments:
        result['assignments'].extend(assignments)

    variable_usage = core_extractors.extract_variable_usage(context)
    if variable_usage:
        result['variable_usage'].extend(variable_usage)

    # Extract function calls with arguments
    # Note: function_params and resolved_imports are optional and can be None
    calls_with_args = core_extractors.extract_python_calls_with_args(context)
    for call in calls_with_args:
        # Skip calls with empty callee_function (violates CHECK constraint)
        callee = call.get('callee_function', '')
        if callee:
            result['function_calls'].append({
                'line': call.get('line', 0),
                'caller_function': call.get('caller_function', 'global'),
                'callee_function': callee,
                'argument_index': call.get('argument_index', 0),
                'argument_expr': call.get('argument_expr', ''),
                'param_name': call.get('param_name', ''),
                'callee_file_path': call.get('callee_file_path'),
            })

    returns = core_extractors.extract_python_returns(context)
    if returns:
        result['returns'].extend(returns)

    properties = core_extractors.extract_python_properties(context)
    if properties:
        # Add 'type' field for storage layer compatibility
        for prop in properties:
            prop['type'] = 'property'
        result['symbols'].extend(properties)

    calls = core_extractors.extract_python_calls(context)
    if calls:
        # Add 'type' field for storage layer compatibility
        for call in calls:
            call['type'] = 'call'
        result['symbols'].extend(calls)

    dicts = core_extractors.extract_python_dicts(context)
    if dicts:
        result['object_literals'].extend(dicts)

    decorators = core_extractors.extract_python_decorators(context)
    if decorators:
        result['python_decorators'].extend(decorators)

    context_managers = core_extractors.extract_python_context_managers(context)
    if context_managers:
        result['python_context_managers'].extend(context_managers)

    generators = core_extractors.extract_generators(context)
    if generators:
        result['python_generators'].extend(generators)

    # ORM and framework extractors
    sql_models, sql_fields, sql_relationships = orm_extractors.extract_sqlalchemy_definitions(context)
    if sql_models:
        result['python_orm_models'].extend(sql_models)
    if sql_fields:
        result['python_orm_fields'].extend(sql_fields)
    if sql_relationships:
        result['orm_relationships'].extend(sql_relationships)

    django_models, django_relationships = orm_extractors.extract_django_definitions(context)
    if django_models:
        result['python_orm_models'].extend(django_models)
    if django_relationships:
        result['orm_relationships'].extend(django_relationships)

    django_cbvs = django_web_extractors.extract_django_cbvs(context)
    if django_cbvs:
        result['python_django_views'].extend(django_cbvs)

    django_forms = django_web_extractors.extract_django_forms(context)
    if django_forms:
        result['python_django_forms'].extend(django_forms)

    django_form_fields = django_web_extractors.extract_django_form_fields(context)
    if django_form_fields:
        result['python_django_form_fields'].extend(django_form_fields)

    django_admin = django_web_extractors.extract_django_admin(context)
    if django_admin:
        result['python_django_admin'].extend(django_admin)

    django_middleware = django_web_extractors.extract_django_middleware(context)
    if django_middleware:
        result['python_django_middleware'].extend(django_middleware)

    # Validation frameworks
    pydantic_validators = validation_extractors.extract_pydantic_validators(context)
    if pydantic_validators:
        result['python_validators'].extend(pydantic_validators)

    marshmallow_schemas = validation_extractors.extract_marshmallow_schemas(context)
    if marshmallow_schemas:
        result['python_marshmallow_schemas'].extend(marshmallow_schemas)

    marshmallow_fields = validation_extractors.extract_marshmallow_fields(context)
    if marshmallow_fields:
        result['python_marshmallow_fields'].extend(marshmallow_fields)

    drf_serializers = validation_extractors.extract_drf_serializers(context)
    if drf_serializers:
        result['python_drf_serializers'].extend(drf_serializers)

    drf_serializer_fields = validation_extractors.extract_drf_serializer_fields(context)
    if drf_serializer_fields:
        result['python_drf_serializer_fields'].extend(drf_serializer_fields)

    wtforms_forms = validation_extractors.extract_wtforms_forms(context)
    if wtforms_forms:
        result['python_wtforms_forms'].extend(wtforms_forms)

    wtforms_fields = validation_extractors.extract_wtforms_fields(context)
    if wtforms_fields:
        result['python_wtforms_fields'].extend(wtforms_fields)

    # Background tasks
    celery_tasks = framework_extractors.extract_celery_tasks(context)
    if celery_tasks:
        result['python_celery_tasks'].extend(celery_tasks)

    celery_task_calls = framework_extractors.extract_celery_task_calls(context)
    if celery_task_calls:
        result['python_celery_task_calls'].extend(celery_task_calls)

    celery_beat_schedules = framework_extractors.extract_celery_beat_schedules(context)
    if celery_beat_schedules:
        result['python_celery_beat_schedules'].extend(celery_beat_schedules)

    # Flask framework
    flask_apps = flask_extractors.extract_flask_app_factories(context)
    if flask_apps:
        result['python_flask_apps'].extend(flask_apps)

    flask_extensions = flask_extractors.extract_flask_extensions(context)
    if flask_extensions:
        result['python_flask_extensions'].extend(flask_extensions)

    flask_hooks = flask_extractors.extract_flask_request_hooks(context)
    if flask_hooks:
        result['python_flask_hooks'].extend(flask_hooks)

    flask_error_handlers = flask_extractors.extract_flask_error_handlers(context)
    if flask_error_handlers:
        result['python_flask_error_handlers'].extend(flask_error_handlers)

    flask_websockets = flask_extractors.extract_flask_websocket_handlers(context)
    if flask_websockets:
        result['python_flask_websockets'].extend(flask_websockets)

    flask_cli_commands = flask_extractors.extract_flask_cli_commands(context)
    if flask_cli_commands:
        result['python_flask_cli_commands'].extend(flask_cli_commands)

    flask_cors = flask_extractors.extract_flask_cors_configs(context)
    if flask_cors:
        result['python_flask_cors'].extend(flask_cors)

    flask_rate_limits = flask_extractors.extract_flask_rate_limits(context)
    if flask_rate_limits:
        result['python_flask_rate_limits'].extend(flask_rate_limits)

    flask_cache = flask_extractors.extract_flask_cache_decorators(context)
    if flask_cache:
        result['python_flask_cache'].extend(flask_cache)

    flask_routes = flask_extractors.extract_flask_routes(context)
    if flask_routes:
        result['python_routes'].extend(flask_routes)

    flask_blueprints = orm_extractors.extract_flask_blueprints(context)
    if flask_blueprints:
        result['python_blueprints'].extend(flask_blueprints)

    # Testing patterns
    unittest_test_cases = testing_extractors.extract_unittest_test_cases(context)
    if unittest_test_cases:
        result['python_unittest_test_cases'].extend(unittest_test_cases)

    assertion_patterns = testing_extractors.extract_assertion_patterns(context)
    if assertion_patterns:
        result['python_assertion_patterns'].extend(assertion_patterns)

    pytest_plugin_hooks = testing_extractors.extract_pytest_plugin_hooks(context)
    if pytest_plugin_hooks:
        result['python_pytest_plugin_hooks'].extend(pytest_plugin_hooks)

    hypothesis_strategies = testing_extractors.extract_hypothesis_strategies(context)
    if hypothesis_strategies:
        result['python_hypothesis_strategies'].extend(hypothesis_strategies)

    pytest_fixtures = testing_extractors.extract_pytest_fixtures(context)
    if pytest_fixtures:
        result['python_pytest_fixtures'].extend(pytest_fixtures)

    pytest_parametrize = testing_extractors.extract_pytest_parametrize(context)
    if pytest_parametrize:
        result['python_pytest_parametrize'].extend(pytest_parametrize)

    pytest_markers = testing_extractors.extract_pytest_markers(context)
    if pytest_markers:
        result['python_pytest_markers'].extend(pytest_markers)

    mock_patterns = testing_extractors.extract_mock_patterns(context)
    if mock_patterns:
        result['python_mock_patterns'].extend(mock_patterns)

    # Security patterns
    auth_decorators = security_extractors.extract_auth_decorators(context)
    if auth_decorators:
        result['python_auth_decorators'].extend(auth_decorators)

    password_hashing = security_extractors.extract_password_hashing(context)
    if password_hashing:
        result['python_password_hashing'].extend(password_hashing)

    jwt_operations = security_extractors.extract_jwt_operations(context)
    if jwt_operations:
        result['python_jwt_operations'].extend(jwt_operations)

    sql_queries = security_extractors.extract_sql_queries(context)
    if sql_queries:
        result['sql_queries'].extend(sql_queries)

    sql_injection = security_extractors.extract_sql_injection_patterns(context)
    if sql_injection:
        result['python_sql_injection'].extend(sql_injection)

    command_injection = security_extractors.extract_command_injection_patterns(context)
    if command_injection:
        result['python_command_injection'].extend(command_injection)

    path_traversal = security_extractors.extract_path_traversal_patterns(context)
    if path_traversal:
        result['python_path_traversal'].extend(path_traversal)

    dangerous_eval = security_extractors.extract_dangerous_eval_exec(context)
    if dangerous_eval:
        result['python_dangerous_eval'].extend(dangerous_eval)

    crypto_operations = security_extractors.extract_crypto_operations(context)
    if crypto_operations:
        result['python_crypto_operations'].extend(crypto_operations)

    # Django advanced patterns
    django_signals = django_advanced_extractors.extract_django_signals(context)
    if django_signals:
        result['python_django_signals'].extend(django_signals)

    django_receivers = django_advanced_extractors.extract_django_receivers(context)
    if django_receivers:
        result['python_django_receivers'].extend(django_receivers)

    django_managers = django_advanced_extractors.extract_django_managers(context)
    if django_managers:
        result['python_django_managers'].extend(django_managers)

    django_querysets = django_advanced_extractors.extract_django_querysets(context)
    if django_querysets:
        result['python_django_querysets'].extend(django_querysets)

    # State mutation patterns
    instance_mutations = state_mutation_extractors.extract_instance_mutations(context)
    if instance_mutations:
        result['python_instance_mutations'].extend(instance_mutations)

    class_mutations = state_mutation_extractors.extract_class_mutations(context)
    if class_mutations:
        result['python_class_mutations'].extend(class_mutations)

    global_mutations = state_mutation_extractors.extract_global_mutations(context)
    if global_mutations:
        result['python_global_mutations'].extend(global_mutations)

    argument_mutations = state_mutation_extractors.extract_argument_mutations(context)
    if argument_mutations:
        result['python_argument_mutations'].extend(argument_mutations)

    augmented_assignments = state_mutation_extractors.extract_augmented_assignments(context)
    if augmented_assignments:
        result['python_augmented_assignments'].extend(augmented_assignments)

    # Exception flow patterns
    exception_raises = exception_flow_extractors.extract_exception_raises(context)
    if exception_raises:
        result['python_exception_raises'].extend(exception_raises)

    exception_catches = exception_flow_extractors.extract_exception_catches(context)
    if exception_catches:
        result['python_exception_catches'].extend(exception_catches)

    finally_blocks = exception_flow_extractors.extract_finally_blocks(context)
    if finally_blocks:
        result['python_finally_blocks'].extend(finally_blocks)

    context_managers_enhanced = exception_flow_extractors.extract_context_managers(context)
    if context_managers_enhanced:
        result['python_context_managers_enhanced'].extend(context_managers_enhanced)

    # Data flow patterns
    io_operations = data_flow_extractors.extract_io_operations(context)
    if io_operations:
        result['python_io_operations'].extend(io_operations)

    parameter_return_flow = data_flow_extractors.extract_parameter_return_flow(context)
    if parameter_return_flow:
        result['python_parameter_return_flow'].extend(parameter_return_flow)

    closure_captures = data_flow_extractors.extract_closure_captures(context)
    if closure_captures:
        result['python_closure_captures'].extend(closure_captures)

    nonlocal_access = data_flow_extractors.extract_nonlocal_access(context)
    if nonlocal_access:
        result['python_nonlocal_access'].extend(nonlocal_access)

    conditional_calls = data_flow_extractors.extract_conditional_calls(context)
    if conditional_calls:
        result['python_conditional_calls'].extend(conditional_calls)

    # Behavioral patterns
    recursion_patterns = behavioral_extractors.extract_recursion_patterns(context)
    if recursion_patterns:
        result['python_recursion_patterns'].extend(recursion_patterns)

    generator_yields = behavioral_extractors.extract_generator_yields(context)
    if generator_yields:
        result['python_generator_yields'].extend(generator_yields)

    property_patterns = behavioral_extractors.extract_property_patterns(context)
    if property_patterns:
        result['python_property_patterns'].extend(property_patterns)

    dynamic_attributes = behavioral_extractors.extract_dynamic_attributes(context)
    if dynamic_attributes:
        result['python_dynamic_attributes'].extend(dynamic_attributes)

    # Performance patterns
    loop_complexity = performance_extractors.extract_loop_complexity(context)
    if loop_complexity:
        result['python_loop_complexity'].extend(loop_complexity)

    resource_usage = performance_extractors.extract_resource_usage(context)
    if resource_usage:
        result['python_resource_usage'].extend(resource_usage)

    memoization_patterns = performance_extractors.extract_memoization_patterns(context)
    if memoization_patterns:
        result['python_memoization_patterns'].extend(memoization_patterns)

    # Fundamental patterns (Week 1)
    comprehensions = fundamental_extractors.extract_comprehensions(context)
    if comprehensions:
        result['python_comprehensions'].extend(comprehensions)

    lambda_functions = fundamental_extractors.extract_lambda_functions(context)
    if lambda_functions:
        result['python_lambda_functions'].extend(lambda_functions)

    slice_operations = fundamental_extractors.extract_slice_operations(context)
    if slice_operations:
        result['python_slice_operations'].extend(slice_operations)

    tuple_operations = fundamental_extractors.extract_tuple_operations(context)
    if tuple_operations:
        result['python_tuple_operations'].extend(tuple_operations)

    unpacking_patterns = fundamental_extractors.extract_unpacking_patterns(context)
    if unpacking_patterns:
        result['python_unpacking_patterns'].extend(unpacking_patterns)

    none_patterns = fundamental_extractors.extract_none_patterns(context)
    if none_patterns:
        result['python_none_patterns'].extend(none_patterns)

    truthiness_patterns = fundamental_extractors.extract_truthiness_patterns(context)
    if truthiness_patterns:
        result['python_truthiness_patterns'].extend(truthiness_patterns)

    string_formatting = fundamental_extractors.extract_string_formatting(context)
    if string_formatting:
        result['python_string_formatting'].extend(string_formatting)

    # Operator patterns (Week 2)
    operators = operator_extractors.extract_operators(context)
    if operators:
        result['python_operators'].extend(operators)

    membership_tests = operator_extractors.extract_membership_tests(context)
    if membership_tests:
        result['python_membership_tests'].extend(membership_tests)

    chained_comparisons = operator_extractors.extract_chained_comparisons(context)
    if chained_comparisons:
        result['python_chained_comparisons'].extend(chained_comparisons)

    ternary_expressions = operator_extractors.extract_ternary_expressions(context)
    if ternary_expressions:
        result['python_ternary_expressions'].extend(ternary_expressions)

    walrus_operators = operator_extractors.extract_walrus_operators(context)
    if walrus_operators:
        result['python_walrus_operators'].extend(walrus_operators)

    matrix_multiplication = operator_extractors.extract_matrix_multiplication(context)
    if matrix_multiplication:
        result['python_matrix_multiplication'].extend(matrix_multiplication)

    # Collection patterns (Week 3)
    dict_operations = collection_extractors.extract_dict_operations(context)
    if dict_operations:
        result['python_dict_operations'].extend(dict_operations)

    list_mutations = collection_extractors.extract_list_mutations(context)
    if list_mutations:
        result['python_list_mutations'].extend(list_mutations)

    set_operations = collection_extractors.extract_set_operations(context)
    if set_operations:
        result['python_set_operations'].extend(set_operations)

    string_methods = collection_extractors.extract_string_methods(context)
    if string_methods:
        result['python_string_methods'].extend(string_methods)

    builtin_usage = collection_extractors.extract_builtin_usage(context)
    if builtin_usage:
        result['python_builtin_usage'].extend(builtin_usage)

    itertools_usage = collection_extractors.extract_itertools_usage(context)
    if itertools_usage:
        result['python_itertools_usage'].extend(itertools_usage)

    functools_usage = collection_extractors.extract_functools_usage(context)
    if functools_usage:
        result['python_functools_usage'].extend(functools_usage)

    collections_usage = collection_extractors.extract_collections_usage(context)
    if collections_usage:
        result['python_collections_usage'].extend(collections_usage)

    # Class feature patterns (Week 4)
    metaclasses = class_feature_extractors.extract_metaclasses(context)
    if metaclasses:
        result['python_metaclasses'].extend(metaclasses)

    descriptors = class_feature_extractors.extract_descriptors(context)
    if descriptors:
        result['python_descriptors'].extend(descriptors)

    dataclasses = class_feature_extractors.extract_dataclasses(context)
    if dataclasses:
        result['python_dataclasses'].extend(dataclasses)

    enums = class_feature_extractors.extract_enums(context)
    if enums:
        result['python_enums'].extend(enums)

    slots = class_feature_extractors.extract_slots(context)
    if slots:
        result['python_slots'].extend(slots)

    abstract_classes = class_feature_extractors.extract_abstract_classes(context)
    if abstract_classes:
        result['python_abstract_classes'].extend(abstract_classes)

    method_types = class_feature_extractors.extract_method_types(context)
    if method_types:
        result['python_method_types'].extend(method_types)

    multiple_inheritance = class_feature_extractors.extract_multiple_inheritance(context)
    if multiple_inheritance:
        result['python_multiple_inheritance'].extend(multiple_inheritance)

    dunder_methods = class_feature_extractors.extract_dunder_methods(context)
    if dunder_methods:
        result['python_dunder_methods'].extend(dunder_methods)

    visibility_conventions = class_feature_extractors.extract_visibility_conventions(context)
    if visibility_conventions:
        result['python_visibility_conventions'].extend(visibility_conventions)

    # Stdlib patterns (Week 4)
    regex_patterns = stdlib_pattern_extractors.extract_regex_patterns(context)
    if regex_patterns:
        result['python_regex_patterns'].extend(regex_patterns)

    json_operations = stdlib_pattern_extractors.extract_json_operations(context)
    if json_operations:
        result['python_json_operations'].extend(json_operations)

    datetime_operations = stdlib_pattern_extractors.extract_datetime_operations(context)
    if datetime_operations:
        result['python_datetime_operations'].extend(datetime_operations)

    path_operations = stdlib_pattern_extractors.extract_path_operations(context)
    if path_operations:
        result['python_path_operations'].extend(path_operations)

    logging_patterns = stdlib_pattern_extractors.extract_logging_patterns(context)
    if logging_patterns:
        result['python_logging_patterns'].extend(logging_patterns)

    threading_patterns = stdlib_pattern_extractors.extract_threading_patterns(context)
    if threading_patterns:
        result['python_threading_patterns'].extend(threading_patterns)

    contextlib_patterns = stdlib_pattern_extractors.extract_contextlib_patterns(context)
    if contextlib_patterns:
        result['python_contextlib_patterns'].extend(contextlib_patterns)

    type_checking = stdlib_pattern_extractors.extract_type_checking(context)
    if type_checking:
        result['python_type_checking'].extend(type_checking)

    # Control flow patterns (Week 5)
    for_loops = control_flow_extractors.extract_for_loops(context)
    if for_loops:
        result['python_for_loops'].extend(for_loops)

    while_loops = control_flow_extractors.extract_while_loops(context)
    if while_loops:
        result['python_while_loops'].extend(while_loops)

    async_for_loops = control_flow_extractors.extract_async_for_loops(context)
    if async_for_loops:
        result['python_async_for_loops'].extend(async_for_loops)

    if_statements = control_flow_extractors.extract_if_statements(context)
    if if_statements:
        result['python_if_statements'].extend(if_statements)

    match_statements = control_flow_extractors.extract_match_statements(context)
    if match_statements:
        result['python_match_statements'].extend(match_statements)

    break_continue_pass = control_flow_extractors.extract_break_continue_pass(context)
    if break_continue_pass:
        result['python_break_continue_pass'].extend(break_continue_pass)

    assert_statements = control_flow_extractors.extract_assert_statements(context)
    if assert_statements:
        result['python_assert_statements'].extend(assert_statements)

    del_statements = control_flow_extractors.extract_del_statements(context)
    if del_statements:
        result['python_del_statements'].extend(del_statements)

    import_statements = control_flow_extractors.extract_import_statements(context)
    if import_statements:
        result['python_import_statements'].extend(import_statements)

    with_statements = control_flow_extractors.extract_with_statements(context)
    if with_statements:
        result['python_with_statements'].extend(with_statements)

    # Protocol patterns (Week 6)
    iterator_protocol = protocol_extractors.extract_iterator_protocol(context)
    if iterator_protocol:
        result['python_iterator_protocol'].extend(iterator_protocol)

    container_protocol = protocol_extractors.extract_container_protocol(context)
    if container_protocol:
        result['python_container_protocol'].extend(container_protocol)

    callable_protocol = protocol_extractors.extract_callable_protocol(context)
    if callable_protocol:
        result['python_callable_protocol'].extend(callable_protocol)

    comparison_protocol = protocol_extractors.extract_comparison_protocol(context)
    if comparison_protocol:
        result['python_comparison_protocol'].extend(comparison_protocol)

    arithmetic_protocol = protocol_extractors.extract_arithmetic_protocol(context)
    if arithmetic_protocol:
        result['python_arithmetic_protocol'].extend(arithmetic_protocol)

    pickle_protocol = protocol_extractors.extract_pickle_protocol(context)
    if pickle_protocol:
        result['python_pickle_protocol'].extend(pickle_protocol)

    weakref_usage = protocol_extractors.extract_weakref_usage(context)
    if weakref_usage:
        result['python_weakref_usage'].extend(weakref_usage)

    contextvar_usage = protocol_extractors.extract_contextvar_usage(context)
    if contextvar_usage:
        result['python_contextvar_usage'].extend(contextvar_usage)

    module_attributes = protocol_extractors.extract_module_attributes(context)
    if module_attributes:
        result['python_module_attributes'].extend(module_attributes)

    class_decorators = protocol_extractors.extract_class_decorators(context)
    if class_decorators:
        result['python_class_decorators'].extend(class_decorators)

    # Advanced patterns
    namespace_packages = advanced_extractors.extract_namespace_packages(context)
    if namespace_packages:
        result['python_namespace_packages'].extend(namespace_packages)

    cached_property = advanced_extractors.extract_cached_property(context)
    if cached_property:
        result['python_cached_property'].extend(cached_property)

    descriptor_protocol = advanced_extractors.extract_descriptor_protocol(context)
    if descriptor_protocol:
        result['python_descriptor_protocol'].extend(descriptor_protocol)

    attribute_access_protocol = advanced_extractors.extract_attribute_access_protocol(context)
    if attribute_access_protocol:
        result['python_attribute_access_protocol'].extend(attribute_access_protocol)

    copy_protocol = advanced_extractors.extract_copy_protocol(context)
    if copy_protocol:
        result['python_copy_protocol'].extend(copy_protocol)

    ellipsis_usage = advanced_extractors.extract_ellipsis_usage(context)
    if ellipsis_usage:
        result['python_ellipsis_usage'].extend(ellipsis_usage)

    bytes_operations = advanced_extractors.extract_bytes_operations(context)
    if bytes_operations:
        result['python_bytes_operations'].extend(bytes_operations)

    exec_eval_compile = advanced_extractors.extract_exec_eval_compile(context)
    if exec_eval_compile:
        result['python_exec_eval_compile'].extend(exec_eval_compile)

    # Async patterns
    async_functions = async_extractors.extract_async_functions(context)
    if async_functions:
        result['python_async_functions'].extend(async_functions)

    await_expressions = async_extractors.extract_await_expressions(context)
    if await_expressions:
        result['python_await_expressions'].extend(await_expressions)

    async_generators = async_extractors.extract_async_generators(context)
    if async_generators:
        result['python_async_generators'].extend(async_generators)

    # Type patterns
    protocols = type_extractors.extract_protocols(context)
    if protocols:
        result['python_protocols'].extend(protocols)

    generics = type_extractors.extract_generics(context)
    if generics:
        result['python_generics'].extend(generics)

    typed_dicts = type_extractors.extract_typed_dicts(context)
    if typed_dicts:
        result['python_typed_dicts'].extend(typed_dicts)

    literals = type_extractors.extract_literals(context)
    if literals:
        result['python_literals'].extend(literals)

    overloads = type_extractors.extract_overloads(context)
    if overloads:
        result['python_overloads'].extend(overloads)

    # Infrastructure
    cdk_constructs = cdk_extractor.extract_python_cdk_constructs(context)
    if cdk_constructs:
        result['cdk_constructs'].extend(cdk_constructs)

    # Control flow graph
    cfg = cfg_extractor.extract_python_cfg(context)
    if cfg:
        result['cfg'].extend(cfg)

    # DEDUPLICATE SYMBOLS - Check for duplicates before returning
    symbols = result.get('symbols', [])
    if symbols:
        seen = set()
        unique_symbols = []
        duplicates = []
        for sym in symbols:
            key = (sym.get('name'), sym.get('line'), sym.get('type'), sym.get('col', 0))
            if key in seen:
                duplicates.append(sym)
            else:
                seen.add(key)
                unique_symbols.append(sym)

        if duplicates:
            # print(f"\n[PYTHON_IMPL DEDUP] Found {len(duplicates)} duplicate symbols:", file=sys.stderr)
            # for dup in duplicates[:5]:  # Show first 5
            #     print(f"  DUPLICATE: {dup.get('name')} ({dup.get('type')}) line {dup.get('line')} col {dup.get('col')}", file=sys.stderr)
            result['symbols'] = unique_symbols
            # print(f"[PYTHON_IMPL DEDUP] Deduplicated: {len(symbols)} -> {len(unique_symbols)}", file=sys.stderr)

    # DEBUG: Log result summary (commented out for clean merge)
    # print(f"\n[PYTHON_IMPL EXIT] Extraction complete:", file=sys.stderr)
    # print(f"  Symbols: {len(result.get('symbols', []))}", file=sys.stderr)
    # print(f"  Imports: {len(result.get('imports', []))}", file=sys.stderr)
    # print(f"  Assignments: {len(result.get('assignments', []))}", file=sys.stderr)
    # print(f"  Function calls: {len(result.get('function_calls', []))}", file=sys.stderr)
    # print(f"  Python routes: {len(result.get('python_routes', []))}", file=sys.stderr)
    # print(f"  Python ORM models: {len(result.get('python_orm_models', []))}", file=sys.stderr)

    return result