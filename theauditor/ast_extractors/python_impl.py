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
    task_graphql_extractors,
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
    import sys
    # print(f"[PYTHON_IMPL ENTRY] extract_all_python_data() called", file=sys.stderr)
    # print(f"[PYTHON_IMPL ENTRY] Context type: {type(context)}", file=sys.stderr)
    # print(f"[PYTHON_IMPL ENTRY] Context.tree: {type(context.tree) if hasattr(context, 'tree') else 'NO TREE'}", file=sys.stderr)
    # print(f"[PYTHON_IMPL ENTRY] Context.file_path: {context.file_path if hasattr(context, 'file_path') else 'NO PATH'}", file=sys.stderr)

    # ==========================================================================
    # CONSOLIDATED RESULT DICTIONARY
    # ==========================================================================
    # This dictionary uses 28 consolidated Python keys (8 kept + 20 new)
    # instead of ~150 granular keys. Extractor outputs are tagged with
    # discriminator fields before being appended to the appropriate list.
    #
    # HISTORY:
    # - 2025-11-25: Consolidated from ~150 keys to 28 (wire-extractors-to-consolidated-schema)
    # ==========================================================================

    result = {
        # Core language features (unchanged)
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

        # ORM and database (unchanged)
        'orm_relationships': [],

        # Infrastructure (unchanged)
        'cdk_constructs': [],
        'cdk_construct_properties': [],

        # SQL queries (unchanged - used by security analysis)
        'sql_queries': [],

        # Legacy routes field (unchanged for backward compatibility)
        'routes': [],

        # ===== KEPT PYTHON TABLES (8) =====
        'python_orm_models': [],
        'python_orm_fields': [],
        'python_routes': [],
        'python_validators': [],
        'python_decorators': [],
        'python_django_views': [],
        'python_django_middleware': [],
        'python_package_configs': [],

        # ===== NEW CONSOLIDATED TABLES (20) =====
        # Group 1: Control & Data Flow
        'python_loops': [],              # for_loop, while_loop, async_for_loop
        'python_branches': [],           # if, match, raise, except, finally
        'python_functions_advanced': [], # async, async_generator, generator, lambda, context_manager
        'python_io_operations': [],      # file, network, database, process, param_flow, closure, nonlocal, conditional
        'python_state_mutations': [],    # instance, class, global, argument, augmented

        # Group 2: Object-Oriented & Types
        'python_class_features': [],     # metaclass, slots, abstract, dataclass, enum, inheritance, dunder, visibility, method_type
        'python_protocols': [],          # iterator, container, callable, comparison, arithmetic, pickle, context_manager
        'python_descriptors': [],        # descriptor, property, dynamic_attr, cached_property, attr_access
        'python_type_definitions': [],   # typed_dict, generic, protocol
        'python_literals': [],           # literal, overload

        # Group 3: Security & Testing
        'python_security_findings': [],  # sql_injection, command_injection, path_traversal, dangerous_eval, crypto, auth, password, jwt
        'python_test_cases': [],         # unittest, pytest, assertion
        'python_test_fixtures': [],      # fixture, parametrize, marker, mock, plugin_hook, hypothesis
        'python_framework_config': [],   # flask/celery/django configs
        'python_validation_schemas': [], # marshmallow, drf, wtforms

        # Group 4: Low-Level & Misc
        'python_operators': [],          # binary, unary, membership, chained, ternary, walrus, matmul
        'python_collections': [],        # dict, list, set, string, builtin, itertools, functools, collections
        'python_stdlib_usage': [],       # re, json, datetime, pathlib, logging, threading, contextlib, typing, weakref, contextvars
        'python_imports_advanced': [],   # static, dynamic, namespace, module_attr
        'python_expressions': [],        # comprehension, slice, tuple, unpack, none, truthiness, format, ellipsis, bytes, exec, copy, recursion, yield, complexity, resource, memoize, await, break, continue, pass, assert, del, with, class_decorator
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

    # Context managers → python_functions_advanced (function_type='context_manager')
    context_managers = core_extractors.extract_python_context_managers(context)
    for cm in context_managers:
        cm['function_type'] = 'context_manager'
        result['python_functions_advanced'].append(cm)

    # Generators → python_functions_advanced (function_type='generator')
    generators = core_extractors.extract_generators(context)
    for gen in generators:
        gen['function_type'] = 'generator'
        result['python_functions_advanced'].append(gen)

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

    # Django forms → python_framework_config (framework='django', config_type='form')
    django_forms = django_web_extractors.extract_django_forms(context)
    for form in django_forms:
        form['framework'] = 'django'
        form['config_type'] = 'form'
        result['python_framework_config'].append(form)

    # Django form fields → python_framework_config (framework='django', config_type='form_field')
    django_form_fields = django_web_extractors.extract_django_form_fields(context)
    for field in django_form_fields:
        field['framework'] = 'django'
        field['config_type'] = 'form_field'
        result['python_framework_config'].append(field)

    # Django admin → python_framework_config (framework='django', config_type='admin')
    django_admin = django_web_extractors.extract_django_admin(context)
    for admin in django_admin:
        admin['framework'] = 'django'
        admin['config_type'] = 'admin'
        result['python_framework_config'].append(admin)

    django_middleware = django_web_extractors.extract_django_middleware(context)
    if django_middleware:
        result['python_django_middleware'].extend(django_middleware)

    # Validation frameworks
    # Pydantic validators → python_validators (kept table)
    pydantic_validators = validation_extractors.extract_pydantic_validators(context)
    if pydantic_validators:
        result['python_validators'].extend(pydantic_validators)

    # Marshmallow schemas → python_validation_schemas (framework='marshmallow', schema_type='schema')
    marshmallow_schemas = validation_extractors.extract_marshmallow_schemas(context)
    for schema in marshmallow_schemas:
        schema['framework'] = 'marshmallow'
        schema['schema_type'] = 'schema'
        result['python_validation_schemas'].append(schema)

    # Marshmallow fields → python_validation_schemas (framework='marshmallow', schema_type='field')
    marshmallow_fields = validation_extractors.extract_marshmallow_fields(context)
    for field in marshmallow_fields:
        field['framework'] = 'marshmallow'
        field['schema_type'] = 'field'
        result['python_validation_schemas'].append(field)

    # DRF serializers → python_validation_schemas (framework='drf', schema_type='serializer')
    drf_serializers = validation_extractors.extract_drf_serializers(context)
    for serializer in drf_serializers:
        serializer['framework'] = 'drf'
        serializer['schema_type'] = 'serializer'
        result['python_validation_schemas'].append(serializer)

    # DRF serializer fields → python_validation_schemas (framework='drf', schema_type='field')
    drf_serializer_fields = validation_extractors.extract_drf_serializer_fields(context)
    for field in drf_serializer_fields:
        field['framework'] = 'drf'
        field['schema_type'] = 'field'
        result['python_validation_schemas'].append(field)

    # WTForms forms → python_validation_schemas (framework='wtforms', schema_type='form')
    wtforms_forms = validation_extractors.extract_wtforms_forms(context)
    for form in wtforms_forms:
        form['framework'] = 'wtforms'
        form['schema_type'] = 'form'
        result['python_validation_schemas'].append(form)

    # WTForms fields → python_validation_schemas (framework='wtforms', schema_type='field')
    wtforms_fields = validation_extractors.extract_wtforms_fields(context)
    for field in wtforms_fields:
        field['framework'] = 'wtforms'
        field['schema_type'] = 'field'
        result['python_validation_schemas'].append(field)

    # Background tasks - Celery → python_framework_config
    celery_tasks = framework_extractors.extract_celery_tasks(context)
    for task in celery_tasks:
        task['framework'] = 'celery'
        task['config_type'] = 'task'
        result['python_framework_config'].append(task)

    celery_task_calls = framework_extractors.extract_celery_task_calls(context)
    for call in celery_task_calls:
        call['framework'] = 'celery'
        call['config_type'] = 'task_call'
        result['python_framework_config'].append(call)

    celery_beat_schedules = framework_extractors.extract_celery_beat_schedules(context)
    for schedule in celery_beat_schedules:
        schedule['framework'] = 'celery'
        schedule['config_type'] = 'schedule'
        result['python_framework_config'].append(schedule)

    # Flask framework → python_framework_config
    flask_apps = flask_extractors.extract_flask_app_factories(context)
    for app in flask_apps:
        app['framework'] = 'flask'
        app['config_type'] = 'app'
        result['python_framework_config'].append(app)

    flask_extensions = flask_extractors.extract_flask_extensions(context)
    for ext in flask_extensions:
        ext['framework'] = 'flask'
        ext['config_type'] = 'extension'
        result['python_framework_config'].append(ext)

    flask_hooks = flask_extractors.extract_flask_request_hooks(context)
    for hook in flask_hooks:
        hook['framework'] = 'flask'
        hook['config_type'] = 'hook'
        result['python_framework_config'].append(hook)

    flask_error_handlers = flask_extractors.extract_flask_error_handlers(context)
    for handler in flask_error_handlers:
        handler['framework'] = 'flask'
        handler['config_type'] = 'error_handler'
        result['python_framework_config'].append(handler)

    flask_websockets = flask_extractors.extract_flask_websocket_handlers(context)
    for ws in flask_websockets:
        ws['framework'] = 'flask'
        ws['config_type'] = 'websocket'
        result['python_framework_config'].append(ws)

    flask_cli_commands = flask_extractors.extract_flask_cli_commands(context)
    for cmd in flask_cli_commands:
        cmd['framework'] = 'flask'
        cmd['config_type'] = 'cli'
        result['python_framework_config'].append(cmd)

    flask_cors = flask_extractors.extract_flask_cors_configs(context)
    for cors in flask_cors:
        cors['framework'] = 'flask'
        cors['config_type'] = 'cors'
        result['python_framework_config'].append(cors)

    flask_rate_limits = flask_extractors.extract_flask_rate_limits(context)
    for limit in flask_rate_limits:
        limit['framework'] = 'flask'
        limit['config_type'] = 'rate_limit'
        result['python_framework_config'].append(limit)

    flask_cache = flask_extractors.extract_flask_cache_decorators(context)
    for cache in flask_cache:
        cache['framework'] = 'flask'
        cache['config_type'] = 'cache'
        result['python_framework_config'].append(cache)

    # Flask routes → python_routes (kept table)
    flask_routes = flask_extractors.extract_flask_routes(context)
    if flask_routes:
        result['python_routes'].extend(flask_routes)

    # Flask blueprints - skip (table doesn't exist in schema)
    # flask_blueprints = orm_extractors.extract_flask_blueprints(context)
    # Note: python_blueprints table was deleted - blueprints are now captured via routes

    # Testing patterns → python_test_cases and python_test_fixtures
    # unittest_test_cases → python_test_cases (test_type='unittest')
    unittest_test_cases = testing_extractors.extract_unittest_test_cases(context)
    for tc in unittest_test_cases:
        tc['test_type'] = 'unittest'
        result['python_test_cases'].append(tc)

    # assertion_patterns → python_test_cases (test_type='assertion')
    assertion_patterns = testing_extractors.extract_assertion_patterns(context)
    for ap in assertion_patterns:
        ap['test_type'] = 'assertion'
        result['python_test_cases'].append(ap)

    # pytest_plugin_hooks → python_test_fixtures (fixture_type='plugin_hook')
    pytest_plugin_hooks = testing_extractors.extract_pytest_plugin_hooks(context)
    for hook in pytest_plugin_hooks:
        hook['fixture_type'] = 'plugin_hook'
        result['python_test_fixtures'].append(hook)

    # hypothesis_strategies → python_test_fixtures (fixture_type='hypothesis')
    hypothesis_strategies = testing_extractors.extract_hypothesis_strategies(context)
    for strategy in hypothesis_strategies:
        strategy['fixture_type'] = 'hypothesis'
        result['python_test_fixtures'].append(strategy)

    # pytest_fixtures → python_test_fixtures (fixture_type='fixture')
    pytest_fixtures = testing_extractors.extract_pytest_fixtures(context)
    for fixture in pytest_fixtures:
        fixture['fixture_type'] = 'fixture'
        result['python_test_fixtures'].append(fixture)

    # pytest_parametrize → python_test_fixtures (fixture_type='parametrize')
    pytest_parametrize = testing_extractors.extract_pytest_parametrize(context)
    for param in pytest_parametrize:
        param['fixture_type'] = 'parametrize'
        result['python_test_fixtures'].append(param)

    # pytest_markers → python_test_fixtures (fixture_type='marker')
    pytest_markers = testing_extractors.extract_pytest_markers(context)
    for marker in pytest_markers:
        marker['fixture_type'] = 'marker'
        result['python_test_fixtures'].append(marker)

    # mock_patterns → python_test_fixtures (fixture_type='mock')
    mock_patterns = testing_extractors.extract_mock_patterns(context)
    for mock in mock_patterns:
        mock['fixture_type'] = 'mock'
        result['python_test_fixtures'].append(mock)

    # Security patterns → python_security_findings
    # auth_decorators → python_security_findings (finding_type='auth')
    auth_decorators = security_extractors.extract_auth_decorators(context)
    for auth in auth_decorators:
        auth['finding_type'] = 'auth'
        result['python_security_findings'].append(auth)

    # password_hashing → python_security_findings (finding_type='password')
    password_hashing = security_extractors.extract_password_hashing(context)
    for pw in password_hashing:
        pw['finding_type'] = 'password'
        result['python_security_findings'].append(pw)

    # jwt_operations → python_security_findings (finding_type='jwt')
    jwt_operations = security_extractors.extract_jwt_operations(context)
    for jwt in jwt_operations:
        jwt['finding_type'] = 'jwt'
        result['python_security_findings'].append(jwt)

    # sql_queries → sql_queries (unchanged - used by security analysis)
    sql_queries = security_extractors.extract_sql_queries(context)
    if sql_queries:
        result['sql_queries'].extend(sql_queries)

    # sql_injection → python_security_findings (finding_type='sql_injection')
    sql_injection = security_extractors.extract_sql_injection_patterns(context)
    for sqli in sql_injection:
        sqli['finding_type'] = 'sql_injection'
        result['python_security_findings'].append(sqli)

    # command_injection → python_security_findings (finding_type='command_injection')
    command_injection = security_extractors.extract_command_injection_patterns(context)
    for cmdi in command_injection:
        cmdi['finding_type'] = 'command_injection'
        result['python_security_findings'].append(cmdi)

    # path_traversal → python_security_findings (finding_type='path_traversal')
    path_traversal = security_extractors.extract_path_traversal_patterns(context)
    for pt in path_traversal:
        pt['finding_type'] = 'path_traversal'
        result['python_security_findings'].append(pt)

    # dangerous_eval → python_security_findings (finding_type='dangerous_eval')
    dangerous_eval = security_extractors.extract_dangerous_eval_exec(context)
    for de in dangerous_eval:
        de['finding_type'] = 'dangerous_eval'
        result['python_security_findings'].append(de)

    # crypto_operations → python_security_findings (finding_type='crypto')
    crypto_operations = security_extractors.extract_crypto_operations(context)
    for crypto in crypto_operations:
        crypto['finding_type'] = 'crypto'
        result['python_security_findings'].append(crypto)

    # Django advanced patterns → python_framework_config
    django_signals = django_advanced_extractors.extract_django_signals(context)
    for signal in django_signals:
        signal['framework'] = 'django'
        signal['config_type'] = 'signal'
        result['python_framework_config'].append(signal)

    django_receivers = django_advanced_extractors.extract_django_receivers(context)
    for receiver in django_receivers:
        receiver['framework'] = 'django'
        receiver['config_type'] = 'receiver'
        result['python_framework_config'].append(receiver)

    django_managers = django_advanced_extractors.extract_django_managers(context)
    for manager in django_managers:
        manager['framework'] = 'django'
        manager['config_type'] = 'manager'
        result['python_framework_config'].append(manager)

    django_querysets = django_advanced_extractors.extract_django_querysets(context)
    for queryset in django_querysets:
        queryset['framework'] = 'django'
        queryset['config_type'] = 'queryset'
        result['python_framework_config'].append(queryset)

    # State mutation patterns → python_state_mutations
    instance_mutations = state_mutation_extractors.extract_instance_mutations(context)
    for mut in instance_mutations:
        mut['mutation_type'] = 'instance'
        result['python_state_mutations'].append(mut)

    class_mutations = state_mutation_extractors.extract_class_mutations(context)
    for mut in class_mutations:
        mut['mutation_type'] = 'class'
        result['python_state_mutations'].append(mut)

    global_mutations = state_mutation_extractors.extract_global_mutations(context)
    for mut in global_mutations:
        mut['mutation_type'] = 'global'
        result['python_state_mutations'].append(mut)

    argument_mutations = state_mutation_extractors.extract_argument_mutations(context)
    for mut in argument_mutations:
        mut['mutation_type'] = 'argument'
        result['python_state_mutations'].append(mut)

    augmented_assignments = state_mutation_extractors.extract_augmented_assignments(context)
    for mut in augmented_assignments:
        mut['mutation_type'] = 'augmented'
        result['python_state_mutations'].append(mut)

    # Exception flow patterns → python_branches
    exception_raises = exception_flow_extractors.extract_exception_raises(context)
    for exc in exception_raises:
        exc['branch_type'] = 'raise'
        result['python_branches'].append(exc)

    exception_catches = exception_flow_extractors.extract_exception_catches(context)
    for exc in exception_catches:
        exc['branch_type'] = 'except'
        result['python_branches'].append(exc)

    finally_blocks = exception_flow_extractors.extract_finally_blocks(context)
    for block in finally_blocks:
        block['branch_type'] = 'finally'
        result['python_branches'].append(block)

    # context_managers_enhanced → python_protocols (protocol_type='context_manager')
    context_managers_enhanced = exception_flow_extractors.extract_context_managers(context)
    for cm in context_managers_enhanced:
        cm['protocol_type'] = 'context_manager'
        result['python_protocols'].append(cm)

    # Data flow patterns → python_io_operations
    # io_operations already has io_type from extractor, just extend
    io_operations = data_flow_extractors.extract_io_operations(context)
    if io_operations:
        result['python_io_operations'].extend(io_operations)

    parameter_return_flow = data_flow_extractors.extract_parameter_return_flow(context)
    for flow in parameter_return_flow:
        flow['io_type'] = 'param_flow'
        result['python_io_operations'].append(flow)

    closure_captures = data_flow_extractors.extract_closure_captures(context)
    for capture in closure_captures:
        capture['io_type'] = 'closure'
        result['python_io_operations'].append(capture)

    nonlocal_access = data_flow_extractors.extract_nonlocal_access(context)
    for access in nonlocal_access:
        access['io_type'] = 'nonlocal'
        result['python_io_operations'].append(access)

    conditional_calls = data_flow_extractors.extract_conditional_calls(context)
    for call in conditional_calls:
        call['io_type'] = 'conditional'
        result['python_io_operations'].append(call)

    # Behavioral patterns → python_expressions/python_descriptors
    recursion_patterns = behavioral_extractors.extract_recursion_patterns(context)
    for pattern in recursion_patterns:
        pattern['expression_type'] = 'recursion'
        result['python_expressions'].append(pattern)

    generator_yields = behavioral_extractors.extract_generator_yields(context)
    for yld in generator_yields:
        yld['expression_type'] = 'yield'
        result['python_expressions'].append(yld)

    # property_patterns → python_descriptors (descriptor_type='property')
    property_patterns = behavioral_extractors.extract_property_patterns(context)
    for prop in property_patterns:
        prop['descriptor_type'] = 'property'
        result['python_descriptors'].append(prop)

    # dynamic_attributes → python_descriptors (descriptor_type='dynamic_attr')
    dynamic_attributes = behavioral_extractors.extract_dynamic_attributes(context)
    for attr in dynamic_attributes:
        attr['descriptor_type'] = 'dynamic_attr'
        result['python_descriptors'].append(attr)

    # Performance patterns → python_expressions
    loop_complexity = performance_extractors.extract_loop_complexity(context)
    for lc in loop_complexity:
        lc['expression_type'] = 'complexity'
        result['python_expressions'].append(lc)

    resource_usage = performance_extractors.extract_resource_usage(context)
    for ru in resource_usage:
        ru['expression_type'] = 'resource'
        result['python_expressions'].append(ru)

    memoization_patterns = performance_extractors.extract_memoization_patterns(context)
    for memo in memoization_patterns:
        memo['expression_type'] = 'memoize'
        result['python_expressions'].append(memo)

    # Fundamental patterns → python_expressions/python_functions_advanced
    comprehensions = fundamental_extractors.extract_comprehensions(context)
    for comp in comprehensions:
        comp['expression_type'] = 'comprehension'
        result['python_expressions'].append(comp)

    # lambda_functions → python_functions_advanced (function_type='lambda')
    lambda_functions = fundamental_extractors.extract_lambda_functions(context)
    for lam in lambda_functions:
        lam['function_type'] = 'lambda'
        result['python_functions_advanced'].append(lam)

    slice_operations = fundamental_extractors.extract_slice_operations(context)
    for sl in slice_operations:
        sl['expression_type'] = 'slice'
        result['python_expressions'].append(sl)

    tuple_operations = fundamental_extractors.extract_tuple_operations(context)
    for tup in tuple_operations:
        tup['expression_type'] = 'tuple'
        result['python_expressions'].append(tup)

    unpacking_patterns = fundamental_extractors.extract_unpacking_patterns(context)
    for unpack in unpacking_patterns:
        unpack['expression_type'] = 'unpack'
        result['python_expressions'].append(unpack)

    none_patterns = fundamental_extractors.extract_none_patterns(context)
    for none_pat in none_patterns:
        none_pat['expression_type'] = 'none'
        result['python_expressions'].append(none_pat)

    truthiness_patterns = fundamental_extractors.extract_truthiness_patterns(context)
    for truth in truthiness_patterns:
        truth['expression_type'] = 'truthiness'
        result['python_expressions'].append(truth)

    string_formatting = fundamental_extractors.extract_string_formatting(context)
    for fmt in string_formatting:
        fmt['expression_type'] = 'format'
        result['python_expressions'].append(fmt)

    # Operator patterns → python_operators
    # operators already has operator_type from extractor, just extend
    operators = operator_extractors.extract_operators(context)
    if operators:
        result['python_operators'].extend(operators)

    membership_tests = operator_extractors.extract_membership_tests(context)
    for test in membership_tests:
        test['operator_type'] = 'membership'
        result['python_operators'].append(test)

    chained_comparisons = operator_extractors.extract_chained_comparisons(context)
    for comp in chained_comparisons:
        comp['operator_type'] = 'chained'
        result['python_operators'].append(comp)

    ternary_expressions = operator_extractors.extract_ternary_expressions(context)
    for tern in ternary_expressions:
        tern['operator_type'] = 'ternary'
        result['python_operators'].append(tern)

    walrus_operators = operator_extractors.extract_walrus_operators(context)
    for walrus in walrus_operators:
        walrus['operator_type'] = 'walrus'
        result['python_operators'].append(walrus)

    matrix_multiplication = operator_extractors.extract_matrix_multiplication(context)
    for matmul in matrix_multiplication:
        matmul['operator_type'] = 'matmul'
        result['python_operators'].append(matmul)

    # Collection patterns → python_collections
    dict_operations = collection_extractors.extract_dict_operations(context)
    for op in dict_operations:
        op['collection_type'] = 'dict'
        result['python_collections'].append(op)

    list_mutations = collection_extractors.extract_list_mutations(context)
    for mut in list_mutations:
        mut['collection_type'] = 'list'
        result['python_collections'].append(mut)

    set_operations = collection_extractors.extract_set_operations(context)
    for op in set_operations:
        op['collection_type'] = 'set'
        result['python_collections'].append(op)

    string_methods = collection_extractors.extract_string_methods(context)
    for meth in string_methods:
        meth['collection_type'] = 'string'
        result['python_collections'].append(meth)

    builtin_usage = collection_extractors.extract_builtin_usage(context)
    for usage in builtin_usage:
        usage['collection_type'] = 'builtin'
        result['python_collections'].append(usage)

    itertools_usage = collection_extractors.extract_itertools_usage(context)
    for usage in itertools_usage:
        usage['collection_type'] = 'itertools'
        result['python_collections'].append(usage)

    functools_usage = collection_extractors.extract_functools_usage(context)
    for usage in functools_usage:
        usage['collection_type'] = 'functools'
        result['python_collections'].append(usage)

    collections_usage = collection_extractors.extract_collections_usage(context)
    for usage in collections_usage:
        usage['collection_type'] = 'collections'
        result['python_collections'].append(usage)

    # Class feature patterns → python_class_features/python_descriptors
    metaclasses = class_feature_extractors.extract_metaclasses(context)
    for meta in metaclasses:
        meta['feature_type'] = 'metaclass'
        result['python_class_features'].append(meta)

    # descriptors from class_feature_extractors → python_descriptors (descriptor_type='descriptor')
    descriptors = class_feature_extractors.extract_descriptors(context)
    for desc in descriptors:
        desc['descriptor_type'] = 'descriptor'
        result['python_descriptors'].append(desc)

    dataclasses = class_feature_extractors.extract_dataclasses(context)
    for dc in dataclasses:
        dc['feature_type'] = 'dataclass'
        result['python_class_features'].append(dc)

    enums = class_feature_extractors.extract_enums(context)
    for enum in enums:
        enum['feature_type'] = 'enum'
        result['python_class_features'].append(enum)

    slots = class_feature_extractors.extract_slots(context)
    for slot in slots:
        slot['feature_type'] = 'slots'
        result['python_class_features'].append(slot)

    abstract_classes = class_feature_extractors.extract_abstract_classes(context)
    for abstract in abstract_classes:
        abstract['feature_type'] = 'abstract'
        result['python_class_features'].append(abstract)

    method_types = class_feature_extractors.extract_method_types(context)
    for mt in method_types:
        mt['feature_type'] = 'method_type'
        result['python_class_features'].append(mt)

    multiple_inheritance = class_feature_extractors.extract_multiple_inheritance(context)
    for mi in multiple_inheritance:
        mi['feature_type'] = 'inheritance'
        result['python_class_features'].append(mi)

    dunder_methods = class_feature_extractors.extract_dunder_methods(context)
    for dunder in dunder_methods:
        dunder['feature_type'] = 'dunder'
        result['python_class_features'].append(dunder)

    visibility_conventions = class_feature_extractors.extract_visibility_conventions(context)
    for vis in visibility_conventions:
        vis['feature_type'] = 'visibility'
        result['python_class_features'].append(vis)

    # Stdlib patterns → python_stdlib_usage
    regex_patterns = stdlib_pattern_extractors.extract_regex_patterns(context)
    for regex in regex_patterns:
        regex['module'] = 're'
        result['python_stdlib_usage'].append(regex)

    json_operations = stdlib_pattern_extractors.extract_json_operations(context)
    for json_op in json_operations:
        json_op['module'] = 'json'
        result['python_stdlib_usage'].append(json_op)

    datetime_operations = stdlib_pattern_extractors.extract_datetime_operations(context)
    for dt in datetime_operations:
        dt['module'] = 'datetime'
        result['python_stdlib_usage'].append(dt)

    path_operations = stdlib_pattern_extractors.extract_path_operations(context)
    for path_op in path_operations:
        path_op['module'] = 'pathlib'
        result['python_stdlib_usage'].append(path_op)

    logging_patterns = stdlib_pattern_extractors.extract_logging_patterns(context)
    for log in logging_patterns:
        log['module'] = 'logging'
        result['python_stdlib_usage'].append(log)

    threading_patterns = stdlib_pattern_extractors.extract_threading_patterns(context)
    for thread in threading_patterns:
        thread['module'] = 'threading'
        result['python_stdlib_usage'].append(thread)

    contextlib_patterns = stdlib_pattern_extractors.extract_contextlib_patterns(context)
    for ctx in contextlib_patterns:
        ctx['module'] = 'contextlib'
        result['python_stdlib_usage'].append(ctx)

    type_checking = stdlib_pattern_extractors.extract_type_checking(context)
    for tc in type_checking:
        tc['module'] = 'typing'
        result['python_stdlib_usage'].append(tc)

    # Control flow patterns → python_loops/python_branches/python_expressions/python_imports_advanced
    for_loops = control_flow_extractors.extract_for_loops(context)
    for loop in for_loops:
        loop['loop_type'] = 'for_loop'
        result['python_loops'].append(loop)

    while_loops = control_flow_extractors.extract_while_loops(context)
    for loop in while_loops:
        loop['loop_type'] = 'while_loop'
        result['python_loops'].append(loop)

    async_for_loops = control_flow_extractors.extract_async_for_loops(context)
    for loop in async_for_loops:
        loop['loop_type'] = 'async_for_loop'
        result['python_loops'].append(loop)

    if_statements = control_flow_extractors.extract_if_statements(context)
    for stmt in if_statements:
        stmt['branch_type'] = 'if'
        result['python_branches'].append(stmt)

    match_statements = control_flow_extractors.extract_match_statements(context)
    for stmt in match_statements:
        stmt['branch_type'] = 'match'
        result['python_branches'].append(stmt)

    break_continue_pass = control_flow_extractors.extract_break_continue_pass(context)
    for stmt in break_continue_pass:
        stmt['expression_type'] = 'break_continue'
        result['python_expressions'].append(stmt)

    assert_statements = control_flow_extractors.extract_assert_statements(context)
    for stmt in assert_statements:
        stmt['expression_type'] = 'assert'
        result['python_expressions'].append(stmt)

    del_statements = control_flow_extractors.extract_del_statements(context)
    for stmt in del_statements:
        stmt['expression_type'] = 'del'
        result['python_expressions'].append(stmt)

    # import_statements → python_imports_advanced (import_type='static')
    import_statements = control_flow_extractors.extract_import_statements(context)
    for stmt in import_statements:
        stmt['import_type'] = 'static'
        result['python_imports_advanced'].append(stmt)

    with_statements = control_flow_extractors.extract_with_statements(context)
    for stmt in with_statements:
        stmt['expression_type'] = 'with'
        result['python_expressions'].append(stmt)

    # Protocol patterns → python_protocols/python_stdlib_usage/python_imports_advanced/python_expressions
    iterator_protocol = protocol_extractors.extract_iterator_protocol(context)
    for proto in iterator_protocol:
        proto['protocol_type'] = 'iterator'
        result['python_protocols'].append(proto)

    container_protocol = protocol_extractors.extract_container_protocol(context)
    for proto in container_protocol:
        proto['protocol_type'] = 'container'
        result['python_protocols'].append(proto)

    callable_protocol = protocol_extractors.extract_callable_protocol(context)
    for proto in callable_protocol:
        proto['protocol_type'] = 'callable'
        result['python_protocols'].append(proto)

    comparison_protocol = protocol_extractors.extract_comparison_protocol(context)
    for proto in comparison_protocol:
        proto['protocol_type'] = 'comparison'
        result['python_protocols'].append(proto)

    arithmetic_protocol = protocol_extractors.extract_arithmetic_protocol(context)
    for proto in arithmetic_protocol:
        proto['protocol_type'] = 'arithmetic'
        result['python_protocols'].append(proto)

    pickle_protocol = protocol_extractors.extract_pickle_protocol(context)
    for proto in pickle_protocol:
        proto['protocol_type'] = 'pickle'
        result['python_protocols'].append(proto)

    # weakref_usage → python_stdlib_usage (module='weakref')
    weakref_usage = protocol_extractors.extract_weakref_usage(context)
    for wr in weakref_usage:
        wr['module'] = 'weakref'
        result['python_stdlib_usage'].append(wr)

    # contextvar_usage → python_stdlib_usage (module='contextvars')
    contextvar_usage = protocol_extractors.extract_contextvar_usage(context)
    for cv in contextvar_usage:
        cv['module'] = 'contextvars'
        result['python_stdlib_usage'].append(cv)

    # module_attributes → python_imports_advanced (import_type='module_attr')
    module_attributes = protocol_extractors.extract_module_attributes(context)
    for attr in module_attributes:
        attr['import_type'] = 'module_attr'
        result['python_imports_advanced'].append(attr)

    # class_decorators → python_expressions (expression_type='class_decorator')
    class_decorators = protocol_extractors.extract_class_decorators(context)
    for dec in class_decorators:
        dec['expression_type'] = 'class_decorator'
        result['python_expressions'].append(dec)

    # Advanced patterns → python_imports_advanced/python_descriptors/python_expressions
    # namespace_packages → python_imports_advanced (import_type='namespace')
    namespace_packages = advanced_extractors.extract_namespace_packages(context)
    for pkg in namespace_packages:
        pkg['import_type'] = 'namespace'
        result['python_imports_advanced'].append(pkg)

    # cached_property → python_descriptors (descriptor_type='cached_property')
    cached_property = advanced_extractors.extract_cached_property(context)
    for cp in cached_property:
        cp['descriptor_type'] = 'cached_property'
        result['python_descriptors'].append(cp)

    # descriptor_protocol → python_descriptors (descriptor_type='descriptor_protocol')
    descriptor_protocol = advanced_extractors.extract_descriptor_protocol(context)
    for dp in descriptor_protocol:
        dp['descriptor_type'] = 'descriptor_protocol'
        result['python_descriptors'].append(dp)

    # attribute_access_protocol → python_descriptors (descriptor_type='attr_access')
    attribute_access_protocol = advanced_extractors.extract_attribute_access_protocol(context)
    for aap in attribute_access_protocol:
        aap['descriptor_type'] = 'attr_access'
        result['python_descriptors'].append(aap)

    copy_protocol = advanced_extractors.extract_copy_protocol(context)
    for cp in copy_protocol:
        cp['expression_type'] = 'copy'
        result['python_expressions'].append(cp)

    ellipsis_usage = advanced_extractors.extract_ellipsis_usage(context)
    for ell in ellipsis_usage:
        ell['expression_type'] = 'ellipsis'
        result['python_expressions'].append(ell)

    bytes_operations = advanced_extractors.extract_bytes_operations(context)
    for bo in bytes_operations:
        bo['expression_type'] = 'bytes'
        result['python_expressions'].append(bo)

    exec_eval_compile = advanced_extractors.extract_exec_eval_compile(context)
    for eec in exec_eval_compile:
        eec['expression_type'] = 'exec'
        result['python_expressions'].append(eec)

    # Async patterns → python_functions_advanced/python_expressions
    async_functions = async_extractors.extract_async_functions(context)
    for af in async_functions:
        af['function_type'] = 'async'
        result['python_functions_advanced'].append(af)

    # await_expressions → python_expressions (expression_type='await')
    await_expressions = async_extractors.extract_await_expressions(context)
    for aw in await_expressions:
        aw['expression_type'] = 'await'
        result['python_expressions'].append(aw)

    async_generators = async_extractors.extract_async_generators(context)
    for ag in async_generators:
        ag['function_type'] = 'async_generator'
        result['python_functions_advanced'].append(ag)

    # Type patterns → python_type_definitions/python_literals
    # protocols from type_extractors → python_type_definitions (type_kind='protocol')
    protocols = type_extractors.extract_protocols(context)
    for proto in protocols:
        proto['type_kind'] = 'protocol'
        result['python_type_definitions'].append(proto)

    generics = type_extractors.extract_generics(context)
    for gen in generics:
        gen['type_kind'] = 'generic'
        result['python_type_definitions'].append(gen)

    typed_dicts = type_extractors.extract_typed_dicts(context)
    for td in typed_dicts:
        td['type_kind'] = 'typed_dict'
        result['python_type_definitions'].append(td)

    literals = type_extractors.extract_literals(context)
    for lit in literals:
        lit['literal_type'] = 'literal'
        result['python_literals'].append(lit)

    overloads = type_extractors.extract_overloads(context)
    for ovl in overloads:
        ovl['literal_type'] = 'overload'
        result['python_literals'].append(ovl)

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