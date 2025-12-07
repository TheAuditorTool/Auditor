"""Python extraction delegation layer."""

from typing import Any

from theauditor.ast_extractors.python import (
    advanced_extractors,
    async_extractors,
    behavioral_extractors,
    cdk_extractor,
    cfg_extractor,
    class_feature_extractors,
    collection_extractors,
    control_flow_extractors,
    core_extractors,
    data_flow_extractors,
    django_advanced_extractors,
    django_web_extractors,
    exception_flow_extractors,
    flask_extractors,
    framework_extractors,
    fundamental_extractors,
    operator_extractors,
    orm_extractors,
    performance_extractors,
    protocol_extractors,
    security_extractors,
    state_mutation_extractors,
    stdlib_pattern_extractors,
    task_graphql_extractors,
    testing_extractors,
    type_extractors,
    validation_extractors,
)
from theauditor.ast_extractors.python.utils.context import FileContext


def extract_all_python_data(
    context: FileContext,
    resolved_imports: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Extract all Python data by delegating to specialized extractors."""

    # Ensure resolved_imports is not None for downstream use
    resolved_imports = resolved_imports or {}

    result = {
        "imports": [],
        "symbols": [],
        "assignments": [],
        "function_calls": [],
        "returns": [],
        "variable_usage": [],
        "func_params": [],  # For cross-file parameter binding
        "cfg": [],
        "object_literals": [],
        "type_annotations": [],
        "resolved_imports": {},
        "orm_relationships": [],
        "cdk_constructs": [],
        "cdk_construct_properties": [],
        "sql_queries": [],
        "jwt_patterns": [],
        "routes": [],
        "python_orm_models": [],
        "python_orm_fields": [],
        "python_routes": [],
        "python_validators": [],
        "python_decorators": [],
        "python_django_views": [],
        "python_django_middleware": [],
        "python_loops": [],
        "python_branches": [],
        "python_functions_advanced": [],
        "python_io_operations": [],
        "python_state_mutations": [],
        "python_class_features": [],
        "python_protocols": [],
        "python_descriptors": [],
        "python_type_definitions": [],
        "python_literals": [],
        "python_security_findings": [],
        "python_test_cases": [],
        "python_test_fixtures": [],
        "python_framework_config": [],
        "python_validation_schemas": [],
        "python_operators": [],
        "python_collections": [],
        "python_stdlib_usage": [],
        "python_imports_advanced": [],
        "python_expressions": [],
        "python_comprehensions": [],
        "python_control_statements": [],
    }

    functions = core_extractors.extract_python_functions(context)
    if functions:
        for func in functions:
            func["type"] = "function"
        result["symbols"].extend(functions)

    # Extract function parameters for cross-file parameter binding
    # Transform dict format to list format expected by storage layer
    raw_func_params = core_extractors.extract_python_function_params(context)
    for func in functions:
        func_name = func.get("name", "")
        func_line = func.get("line", 0)
        param_names = raw_func_params.get(func_name, [])
        for idx, param_name in enumerate(param_names):
            result["func_params"].append({
                "function_name": func_name,
                "function_line": func_line,
                "param_index": idx,
                "param_name": param_name,
                "param_type": None,  # Python AST doesn't always have type info
            })

    classes = core_extractors.extract_python_classes(context)
    if classes:
        for cls in classes:
            cls["type"] = "class"
        result["symbols"].extend(classes)

    attribute_annotations = core_extractors.extract_python_attribute_annotations(context)
    if attribute_annotations:
        result["type_annotations"].extend(attribute_annotations)

    imports = core_extractors.extract_python_imports(context)
    if imports:
        result["imports"].extend(imports)

    assignments = core_extractors.extract_python_assignments(context)
    if assignments:
        result["assignments"].extend(assignments)

    variable_usage = core_extractors.extract_variable_usage(context)
    if variable_usage:
        result["variable_usage"].extend(variable_usage)

    # Pass function_params (for intra-file param binding) and resolved_imports (for cross-file callee linking)
    calls_with_args = core_extractors.extract_python_calls_with_args(
        context,
        function_params=raw_func_params,
        resolved_imports=resolved_imports,
    )
    for call in calls_with_args:
        callee = call.get("callee_function", "")
        if callee:
            result["function_calls"].append(
                {
                    "line": call.get("line", 0),
                    "caller_function": call.get("caller_function", "global"),
                    "callee_function": callee,
                    "argument_index": call.get("argument_index", 0),
                    "argument_expr": call.get("argument_expr", ""),
                    "param_name": call.get("param_name", ""),
                    "callee_file_path": call.get("callee_file_path"),
                }
            )

    returns = core_extractors.extract_python_returns(context)
    if returns:
        result["returns"].extend(returns)

    properties = core_extractors.extract_python_properties(context)
    if properties:
        for prop in properties:
            prop["type"] = "property"
        result["symbols"].extend(properties)

    calls = core_extractors.extract_python_calls(context)
    if calls:
        for call in calls:
            call["type"] = "call"
        result["symbols"].extend(calls)

    dicts = core_extractors.extract_python_dicts(context)
    if dicts:
        result["object_literals"].extend(dicts)

    decorators = core_extractors.extract_python_decorators(context)
    if decorators:
        result["python_decorators"].extend(decorators)

    context_managers = core_extractors.extract_python_context_managers(context)
    for cm in context_managers:
        cm["function_kind"] = "context_manager"
        result["python_functions_advanced"].append(cm)

    generators = core_extractors.extract_generators(context)
    for gen in generators:
        gen["function_kind"] = "generator"
        result["python_functions_advanced"].append(gen)

    sql_models, sql_fields, sql_relationships = orm_extractors.extract_sqlalchemy_definitions(
        context
    )
    if sql_models:
        result["python_orm_models"].extend(sql_models)
    if sql_fields:
        result["python_orm_fields"].extend(sql_fields)
    if sql_relationships:
        result["orm_relationships"].extend(sql_relationships)

    django_models, django_relationships = orm_extractors.extract_django_definitions(context)
    if django_models:
        result["python_orm_models"].extend(django_models)
    if django_relationships:
        result["orm_relationships"].extend(django_relationships)

    django_cbvs = django_web_extractors.extract_django_cbvs(context)
    if django_cbvs:
        result["python_django_views"].extend(django_cbvs)

    # Django forms → python_framework_config (framework='django', config_type='form')
    django_forms = django_web_extractors.extract_django_forms(context)
    for form in django_forms:
        form["framework"] = "django"
        form["config_type"] = "form"
        result["python_framework_config"].append(form)

    # Django form fields → python_framework_config (framework='django', config_type='form_field')
    django_form_fields = django_web_extractors.extract_django_form_fields(context)
    for field in django_form_fields:
        field["framework"] = "django"
        field["config_type"] = "form_field"
        result["python_framework_config"].append(field)

    # Django admin → python_framework_config (framework='django', config_type='admin')
    django_admin = django_web_extractors.extract_django_admin(context)
    for admin in django_admin:
        admin["framework"] = "django"
        admin["config_type"] = "admin"
        result["python_framework_config"].append(admin)

    django_middleware = django_web_extractors.extract_django_middleware(context)
    if django_middleware:
        result["python_django_middleware"].extend(django_middleware)

    pydantic_validators = validation_extractors.extract_pydantic_validators(context)
    if pydantic_validators:
        result["python_validators"].extend(pydantic_validators)

    # Marshmallow schemas → python_validation_schemas (framework='marshmallow', schema_type='schema')
    marshmallow_schemas = validation_extractors.extract_marshmallow_schemas(context)
    for schema in marshmallow_schemas:
        schema["framework"] = "marshmallow"
        schema["schema_type"] = "schema"
        result["python_validation_schemas"].append(schema)

    # Marshmallow fields → python_validation_schemas (framework='marshmallow', schema_type='field')
    marshmallow_fields = validation_extractors.extract_marshmallow_fields(context)
    for field in marshmallow_fields:
        field["framework"] = "marshmallow"
        field["schema_type"] = "field"
        result["python_validation_schemas"].append(field)

    # DRF serializers → python_validation_schemas (framework='drf', schema_type='serializer')
    drf_serializers = validation_extractors.extract_drf_serializers(context)
    for serializer in drf_serializers:
        serializer["framework"] = "drf"
        serializer["schema_type"] = "serializer"
        result["python_validation_schemas"].append(serializer)

    # DRF serializer fields → python_validation_schemas (framework='drf', schema_type='field')
    drf_serializer_fields = validation_extractors.extract_drf_serializer_fields(context)
    for field in drf_serializer_fields:
        field["framework"] = "drf"
        field["schema_type"] = "field"
        result["python_validation_schemas"].append(field)

    # WTForms forms → python_validation_schemas (framework='wtforms', schema_type='form')
    wtforms_forms = validation_extractors.extract_wtforms_forms(context)
    for form in wtforms_forms:
        form["framework"] = "wtforms"
        form["schema_type"] = "form"
        result["python_validation_schemas"].append(form)

    # WTForms fields → python_validation_schemas (framework='wtforms', schema_type='field')
    wtforms_fields = validation_extractors.extract_wtforms_fields(context)
    for field in wtforms_fields:
        field["framework"] = "wtforms"
        field["schema_type"] = "field"
        result["python_validation_schemas"].append(field)

    celery_tasks = framework_extractors.extract_celery_tasks(context)
    for task in celery_tasks:
        task["framework"] = "celery"
        task["config_type"] = "task"
        result["python_framework_config"].append(task)

    celery_task_calls = framework_extractors.extract_celery_task_calls(context)
    for call in celery_task_calls:
        call["framework"] = "celery"
        call["config_type"] = "task_call"
        result["python_framework_config"].append(call)

    celery_beat_schedules = framework_extractors.extract_celery_beat_schedules(context)
    for schedule in celery_beat_schedules:
        schedule["framework"] = "celery"
        schedule["config_type"] = "schedule"
        result["python_framework_config"].append(schedule)

    flask_apps = flask_extractors.extract_flask_app_factories(context)
    for app in flask_apps:
        app["framework"] = "flask"
        app["config_type"] = "app"
        result["python_framework_config"].append(app)

    flask_extensions = flask_extractors.extract_flask_extensions(context)
    for ext in flask_extensions:
        ext["framework"] = "flask"
        ext["config_type"] = "extension"
        result["python_framework_config"].append(ext)

    flask_hooks = flask_extractors.extract_flask_request_hooks(context)
    for hook in flask_hooks:
        hook["framework"] = "flask"
        hook["config_type"] = "hook"
        result["python_framework_config"].append(hook)

    flask_error_handlers = flask_extractors.extract_flask_error_handlers(context)
    for handler in flask_error_handlers:
        handler["framework"] = "flask"
        handler["config_type"] = "error_handler"
        result["python_framework_config"].append(handler)

    flask_websockets = flask_extractors.extract_flask_websocket_handlers(context)
    for ws in flask_websockets:
        ws["framework"] = "flask"
        ws["config_type"] = "websocket"
        result["python_framework_config"].append(ws)

    flask_cli_commands = flask_extractors.extract_flask_cli_commands(context)
    for cmd in flask_cli_commands:
        cmd["framework"] = "flask"
        cmd["config_type"] = "cli"
        result["python_framework_config"].append(cmd)

    flask_cors = flask_extractors.extract_flask_cors_configs(context)
    for cors in flask_cors:
        cors["framework"] = "flask"
        cors["config_type"] = "cors"
        result["python_framework_config"].append(cors)

    flask_rate_limits = flask_extractors.extract_flask_rate_limits(context)
    for limit in flask_rate_limits:
        limit["framework"] = "flask"
        limit["config_type"] = "rate_limit"
        result["python_framework_config"].append(limit)

    flask_cache = flask_extractors.extract_flask_cache_decorators(context)
    for cache in flask_cache:
        cache["framework"] = "flask"
        cache["config_type"] = "cache"
        result["python_framework_config"].append(cache)

    flask_routes = flask_extractors.extract_flask_routes(context)
    if flask_routes:
        result["python_routes"].extend(flask_routes)

    flask_blueprints = orm_extractors.extract_flask_blueprints(context)
    for bp in flask_blueprints:
        bp["framework"] = "flask"
        bp["config_kind"] = "blueprint"
        bp["config_type"] = bp.get("blueprint_type")
        result["python_framework_config"].append(bp)

    graphene_resolvers = task_graphql_extractors.extract_graphene_resolvers(context)
    for resolver in graphene_resolvers:
        resolver["framework"] = "graphene"
        resolver["config_kind"] = "resolver"
        resolver["config_type"] = resolver.get("resolver_type")
        result["python_framework_config"].append(resolver)

    ariadne_resolvers = task_graphql_extractors.extract_ariadne_resolvers(context)
    for resolver in ariadne_resolvers:
        resolver["framework"] = "ariadne"
        resolver["config_kind"] = "resolver"
        resolver["config_type"] = resolver.get("resolver_type")
        result["python_framework_config"].append(resolver)

    strawberry_resolvers = task_graphql_extractors.extract_strawberry_resolvers(context)
    for resolver in strawberry_resolvers:
        resolver["framework"] = "strawberry"
        resolver["config_kind"] = "resolver"
        resolver["config_type"] = resolver.get("resolver_type")
        result["python_framework_config"].append(resolver)

    # unittest_test_cases → python_test_cases (test_type='unittest')
    unittest_test_cases = testing_extractors.extract_unittest_test_cases(context)
    for tc in unittest_test_cases:
        tc["test_type"] = "unittest"
        result["python_test_cases"].append(tc)

    # assertion_patterns → python_test_cases (test_type='assertion')
    assertion_patterns = testing_extractors.extract_assertion_patterns(context)
    for ap in assertion_patterns:
        ap["test_type"] = "assertion"
        result["python_test_cases"].append(ap)

    # pytest_plugin_hooks → python_test_fixtures (fixture_type='plugin_hook')
    pytest_plugin_hooks = testing_extractors.extract_pytest_plugin_hooks(context)
    for hook in pytest_plugin_hooks:
        hook["fixture_type"] = "plugin_hook"
        result["python_test_fixtures"].append(hook)

    # hypothesis_strategies → python_test_fixtures (fixture_type='hypothesis')
    hypothesis_strategies = testing_extractors.extract_hypothesis_strategies(context)
    for strategy in hypothesis_strategies:
        strategy["fixture_type"] = "hypothesis"
        result["python_test_fixtures"].append(strategy)

    # pytest_fixtures → python_test_fixtures (fixture_type='fixture')
    pytest_fixtures = testing_extractors.extract_pytest_fixtures(context)
    for fixture in pytest_fixtures:
        fixture["fixture_type"] = "fixture"
        result["python_test_fixtures"].append(fixture)

    # pytest_parametrize → python_test_fixtures (fixture_type='parametrize')
    pytest_parametrize = testing_extractors.extract_pytest_parametrize(context)
    for param in pytest_parametrize:
        param["fixture_type"] = "parametrize"
        result["python_test_fixtures"].append(param)

    # pytest_markers → python_test_fixtures (fixture_type='marker')
    pytest_markers = testing_extractors.extract_pytest_markers(context)
    for marker in pytest_markers:
        marker["fixture_type"] = "marker"
        result["python_test_fixtures"].append(marker)

    # mock_patterns → python_test_fixtures (fixture_type='mock')
    mock_patterns = testing_extractors.extract_mock_patterns(context)
    for mock in mock_patterns:
        mock["fixture_type"] = "mock"
        result["python_test_fixtures"].append(mock)

    # auth_decorators → python_security_findings (finding_type='auth')
    auth_decorators = security_extractors.extract_auth_decorators(context)
    for auth in auth_decorators:
        auth["finding_type"] = "auth"
        result["python_security_findings"].append(auth)

    # password_hashing → python_security_findings (finding_type='password')
    password_hashing = security_extractors.extract_password_hashing(context)
    for pw in password_hashing:
        pw["finding_type"] = "password"
        result["python_security_findings"].append(pw)

    # jwt_operations → python_security_findings (finding_type='jwt') AND jwt_patterns
    jwt_operations = security_extractors.extract_jwt_operations(context)
    for jwt in jwt_operations:
        jwt["finding_type"] = "jwt"
        result["python_security_findings"].append(jwt)
        # Also populate jwt_patterns for the dedicated table
        result["jwt_patterns"].append({
            "line": jwt.get("line"),
            "type": jwt.get("type"),
            "full_match": jwt.get("full_match", ""),
            "secret_type": jwt.get("secret_type", "unknown"),
            "algorithm": jwt.get("algorithm"),
        })

    sql_queries = security_extractors.extract_sql_queries(context)
    if sql_queries:
        result["sql_queries"].extend(sql_queries)

    # sql_injection → python_security_findings (finding_type='sql_injection')
    sql_injection = security_extractors.extract_sql_injection_patterns(context)
    for sqli in sql_injection:
        sqli["finding_type"] = "sql_injection"
        result["python_security_findings"].append(sqli)

    # command_injection → python_security_findings (finding_type='command_injection')
    command_injection = security_extractors.extract_command_injection_patterns(context)
    for cmdi in command_injection:
        cmdi["finding_type"] = "command_injection"
        result["python_security_findings"].append(cmdi)

    # path_traversal → python_security_findings (finding_type='path_traversal')
    path_traversal = security_extractors.extract_path_traversal_patterns(context)
    for pt in path_traversal:
        pt["finding_type"] = "path_traversal"
        result["python_security_findings"].append(pt)

    # dangerous_eval → python_security_findings (finding_type='dangerous_eval')
    dangerous_eval = security_extractors.extract_dangerous_eval_exec(context)
    for de in dangerous_eval:
        de["finding_type"] = "dangerous_eval"
        result["python_security_findings"].append(de)

    # crypto_operations → python_security_findings (finding_type='crypto')
    crypto_operations = security_extractors.extract_crypto_operations(context)
    for crypto in crypto_operations:
        crypto["finding_type"] = "crypto"
        result["python_security_findings"].append(crypto)

    django_signals = django_advanced_extractors.extract_django_signals(context)
    for signal in django_signals:
        signal["framework"] = "django"
        signal["config_type"] = "signal"
        result["python_framework_config"].append(signal)

    django_receivers = django_advanced_extractors.extract_django_receivers(context)
    for receiver in django_receivers:
        receiver["framework"] = "django"
        receiver["config_type"] = "receiver"
        result["python_framework_config"].append(receiver)

    django_managers = django_advanced_extractors.extract_django_managers(context)
    for manager in django_managers:
        manager["framework"] = "django"
        manager["config_type"] = "manager"
        result["python_framework_config"].append(manager)

    django_querysets = django_advanced_extractors.extract_django_querysets(context)
    for queryset in django_querysets:
        queryset["framework"] = "django"
        queryset["config_type"] = "queryset"
        result["python_framework_config"].append(queryset)

    instance_mutations = state_mutation_extractors.extract_instance_mutations(context)
    for mut in instance_mutations:
        mut["mutation_kind"] = "instance"
        result["python_state_mutations"].append(mut)

    class_mutations = state_mutation_extractors.extract_class_mutations(context)
    for mut in class_mutations:
        mut["mutation_kind"] = "class"
        result["python_state_mutations"].append(mut)

    global_mutations = state_mutation_extractors.extract_global_mutations(context)
    for mut in global_mutations:
        mut["mutation_kind"] = "global"
        result["python_state_mutations"].append(mut)

    argument_mutations = state_mutation_extractors.extract_argument_mutations(context)
    for mut in argument_mutations:
        mut["mutation_kind"] = "argument"
        result["python_state_mutations"].append(mut)

    augmented_assignments = state_mutation_extractors.extract_augmented_assignments(context)
    for mut in augmented_assignments:
        mut["mutation_kind"] = "augmented"
        result["python_state_mutations"].append(mut)

    exception_raises = exception_flow_extractors.extract_exception_raises(context)
    for exc in exception_raises:
        exc["branch_kind"] = "raise"
        result["python_branches"].append(exc)

    exception_catches = exception_flow_extractors.extract_exception_catches(context)
    for exc in exception_catches:
        exc["branch_kind"] = "except"
        result["python_branches"].append(exc)

    finally_blocks = exception_flow_extractors.extract_finally_blocks(context)
    for block in finally_blocks:
        block["branch_kind"] = "finally"
        result["python_branches"].append(block)

    context_managers_enhanced = exception_flow_extractors.extract_context_managers(context)
    for cm in context_managers_enhanced:
        cm["protocol_kind"] = "context_manager"
        result["python_protocols"].append(cm)

    io_operations = data_flow_extractors.extract_io_operations(context)
    for io_op in io_operations:
        io_op["io_kind"] = io_op.get("io_type", "file")
        result["python_io_operations"].append(io_op)

    parameter_return_flow = data_flow_extractors.extract_parameter_return_flow(context)
    for flow in parameter_return_flow:
        flow["io_kind"] = "param_flow"
        result["python_io_operations"].append(flow)

    closure_captures = data_flow_extractors.extract_closure_captures(context)
    for capture in closure_captures:
        capture["io_kind"] = "closure"
        result["python_io_operations"].append(capture)

    nonlocal_access = data_flow_extractors.extract_nonlocal_access(context)
    for access in nonlocal_access:
        access["io_kind"] = "nonlocal"
        result["python_io_operations"].append(access)

    conditional_calls = data_flow_extractors.extract_conditional_calls(context)
    for call in conditional_calls:
        call["io_kind"] = "conditional"
        result["python_io_operations"].append(call)

    recursion_patterns = behavioral_extractors.extract_recursion_patterns(context)
    for pattern in recursion_patterns:
        pattern["function_kind"] = "recursive"
        result["python_functions_advanced"].append(pattern)

    generator_yields = behavioral_extractors.extract_generator_yields(context)
    for yld in generator_yields:
        yld["expression_type"] = "yield"
        result["python_expressions"].append(yld)

    property_patterns = behavioral_extractors.extract_property_patterns(context)
    for prop in property_patterns:
        prop["descriptor_kind"] = "property"
        result["python_descriptors"].append(prop)

    dynamic_attributes = behavioral_extractors.extract_dynamic_attributes(context)
    for attr in dynamic_attributes:
        attr["descriptor_kind"] = "dynamic_attr"
        result["python_descriptors"].append(attr)

    loop_complexity = performance_extractors.extract_loop_complexity(context)
    for lc in loop_complexity:
        lc["loop_kind"] = "complexity_analysis"
        result["python_loops"].append(lc)

    resource_usage = performance_extractors.extract_resource_usage(context)
    for ru in resource_usage:
        ru["expression_type"] = "resource"
        result["python_expressions"].append(ru)

    memoization_patterns = performance_extractors.extract_memoization_patterns(context)
    for memo in memoization_patterns:
        memo["function_kind"] = "memoized"
        result["python_functions_advanced"].append(memo)

    comprehensions = fundamental_extractors.extract_comprehensions(context)
    for comp in comprehensions:
        comp["comp_kind"] = comp.get("comp_type", "list")
        result["python_comprehensions"].append(comp)

    lambda_functions = fundamental_extractors.extract_lambda_functions(context)
    for lam in lambda_functions:
        lam["function_kind"] = "lambda"
        result["python_functions_advanced"].append(lam)

    slice_operations = fundamental_extractors.extract_slice_operations(context)
    for sl in slice_operations:
        sl["expression_type"] = "slice"
        result["python_expressions"].append(sl)

    tuple_operations = fundamental_extractors.extract_tuple_operations(context)
    for tup in tuple_operations:
        tup["expression_type"] = "tuple"
        result["python_expressions"].append(tup)

    unpacking_patterns = fundamental_extractors.extract_unpacking_patterns(context)
    for unpack in unpacking_patterns:
        unpack["expression_type"] = "unpack"
        result["python_expressions"].append(unpack)

    none_patterns = fundamental_extractors.extract_none_patterns(context)
    for none_pat in none_patterns:
        none_pat["expression_type"] = "none"
        result["python_expressions"].append(none_pat)

    truthiness_patterns = fundamental_extractors.extract_truthiness_patterns(context)
    for truth in truthiness_patterns:
        truth["expression_type"] = "truthiness"
        result["python_expressions"].append(truth)

    string_formatting = fundamental_extractors.extract_string_formatting(context)
    for fmt in string_formatting:
        fmt["expression_type"] = "format"
        result["python_expressions"].append(fmt)

    operators = operator_extractors.extract_operators(context)
    if operators:
        result["python_operators"].extend(operators)

    membership_tests = operator_extractors.extract_membership_tests(context)
    for test in membership_tests:
        test["operator_type"] = "membership"
        result["python_operators"].append(test)

    chained_comparisons = operator_extractors.extract_chained_comparisons(context)
    for comp in chained_comparisons:
        comp["operator_type"] = "chained"
        result["python_operators"].append(comp)

    ternary_expressions = operator_extractors.extract_ternary_expressions(context)
    for tern in ternary_expressions:
        tern["operator_type"] = "ternary"
        result["python_operators"].append(tern)

    walrus_operators = operator_extractors.extract_walrus_operators(context)
    for walrus in walrus_operators:
        walrus["operator_type"] = "walrus"
        result["python_operators"].append(walrus)

    matrix_multiplication = operator_extractors.extract_matrix_multiplication(context)
    for matmul in matrix_multiplication:
        matmul["operator_type"] = "matmul"
        result["python_operators"].append(matmul)

    dict_operations = collection_extractors.extract_dict_operations(context)
    for op in dict_operations:
        op["collection_type"] = "dict"
        result["python_collections"].append(op)

    list_mutations = collection_extractors.extract_list_mutations(context)
    for mut in list_mutations:
        mut["collection_type"] = "list"
        result["python_collections"].append(mut)

    set_operations = collection_extractors.extract_set_operations(context)
    for op in set_operations:
        op["collection_type"] = "set"
        result["python_collections"].append(op)

    string_methods = collection_extractors.extract_string_methods(context)
    for meth in string_methods:
        meth["collection_type"] = "string"
        result["python_collections"].append(meth)

    builtin_usage = collection_extractors.extract_builtin_usage(context)
    for usage in builtin_usage:
        usage["collection_type"] = "builtin"
        result["python_collections"].append(usage)

    itertools_usage = collection_extractors.extract_itertools_usage(context)
    for usage in itertools_usage:
        usage["collection_type"] = "itertools"
        result["python_collections"].append(usage)

    functools_usage = collection_extractors.extract_functools_usage(context)
    for usage in functools_usage:
        usage["collection_type"] = "functools"
        result["python_collections"].append(usage)

    collections_usage = collection_extractors.extract_collections_usage(context)
    for usage in collections_usage:
        usage["collection_type"] = "collections"
        result["python_collections"].append(usage)

    metaclasses = class_feature_extractors.extract_metaclasses(context)
    for meta in metaclasses:
        meta["feature_kind"] = "metaclass"
        result["python_class_features"].append(meta)

    descriptors = class_feature_extractors.extract_descriptors(context)
    for desc in descriptors:
        desc["descriptor_kind"] = "descriptor"
        result["python_descriptors"].append(desc)

    dataclasses = class_feature_extractors.extract_dataclasses(context)
    for dc in dataclasses:
        dc["feature_kind"] = "dataclass"
        result["python_class_features"].append(dc)

    enums = class_feature_extractors.extract_enums(context)
    for enum in enums:
        enum["feature_kind"] = "enum"
        result["python_class_features"].append(enum)

    slots = class_feature_extractors.extract_slots(context)
    for slot in slots:
        slot["feature_kind"] = "slots"
        result["python_class_features"].append(slot)

    abstract_classes = class_feature_extractors.extract_abstract_classes(context)
    for abstract in abstract_classes:
        abstract["feature_kind"] = "abstract"
        result["python_class_features"].append(abstract)

    method_types = class_feature_extractors.extract_method_types(context)
    for mt in method_types:
        mt["feature_kind"] = "method_type"
        result["python_class_features"].append(mt)

    multiple_inheritance = class_feature_extractors.extract_multiple_inheritance(context)
    for mi in multiple_inheritance:
        mi["feature_kind"] = "inheritance"
        result["python_class_features"].append(mi)

    dunder_methods = class_feature_extractors.extract_dunder_methods(context)
    for dunder in dunder_methods:
        dunder["feature_kind"] = "dunder"
        result["python_class_features"].append(dunder)

    visibility_conventions = class_feature_extractors.extract_visibility_conventions(context)
    for vis in visibility_conventions:
        vis["feature_kind"] = "visibility"
        result["python_class_features"].append(vis)

    regex_patterns = stdlib_pattern_extractors.extract_regex_patterns(context)
    for regex in regex_patterns:
        regex["module"] = "re"
        result["python_stdlib_usage"].append(regex)

    json_operations = stdlib_pattern_extractors.extract_json_operations(context)
    for json_op in json_operations:
        json_op["module"] = "json"
        result["python_stdlib_usage"].append(json_op)

    datetime_operations = stdlib_pattern_extractors.extract_datetime_operations(context)
    for dt in datetime_operations:
        dt["module"] = "datetime"
        result["python_stdlib_usage"].append(dt)

    path_operations = stdlib_pattern_extractors.extract_path_operations(context)
    for path_op in path_operations:
        path_op["module"] = "pathlib"
        result["python_stdlib_usage"].append(path_op)

    logging_patterns = stdlib_pattern_extractors.extract_logging_patterns(context)
    for log in logging_patterns:
        log["module"] = "logging"
        result["python_stdlib_usage"].append(log)

    threading_patterns = stdlib_pattern_extractors.extract_threading_patterns(context)
    for thread in threading_patterns:
        thread["module"] = "threading"
        result["python_stdlib_usage"].append(thread)

    contextlib_patterns = stdlib_pattern_extractors.extract_contextlib_patterns(context)
    for ctx in contextlib_patterns:
        ctx["module"] = "contextlib"
        result["python_stdlib_usage"].append(ctx)

    type_checking = stdlib_pattern_extractors.extract_type_checking(context)
    for tc in type_checking:
        tc["module"] = "typing"
        result["python_stdlib_usage"].append(tc)

    for_loops = control_flow_extractors.extract_for_loops(context)
    for loop in for_loops:
        loop["loop_kind"] = "for"
        result["python_loops"].append(loop)

    while_loops = control_flow_extractors.extract_while_loops(context)
    for loop in while_loops:
        loop["loop_kind"] = "while"
        result["python_loops"].append(loop)

    async_for_loops = control_flow_extractors.extract_async_for_loops(context)
    for loop in async_for_loops:
        loop["loop_kind"] = "async_for"
        result["python_loops"].append(loop)

    if_statements = control_flow_extractors.extract_if_statements(context)
    for stmt in if_statements:
        stmt["branch_kind"] = "if"
        result["python_branches"].append(stmt)

    match_statements = control_flow_extractors.extract_match_statements(context)
    for stmt in match_statements:
        stmt["branch_kind"] = "match"
        result["python_branches"].append(stmt)

    break_continue_pass = control_flow_extractors.extract_break_continue_pass(context)
    for stmt in break_continue_pass:
        stmt["statement_kind"] = stmt.get("statement_type", "pass")
        result["python_control_statements"].append(stmt)

    assert_statements = control_flow_extractors.extract_assert_statements(context)
    for stmt in assert_statements:
        stmt["statement_kind"] = "assert"
        result["python_control_statements"].append(stmt)

    del_statements = control_flow_extractors.extract_del_statements(context)
    for stmt in del_statements:
        stmt["statement_kind"] = "del"
        result["python_control_statements"].append(stmt)

    # import_statements → python_imports_advanced (import_type='static')
    import_statements = control_flow_extractors.extract_import_statements(context)
    for stmt in import_statements:
        stmt["import_type"] = "static"
        result["python_imports_advanced"].append(stmt)

    with_statements = control_flow_extractors.extract_with_statements(context)
    for stmt in with_statements:
        stmt["statement_kind"] = "with"
        result["python_control_statements"].append(stmt)

    iterator_protocol = protocol_extractors.extract_iterator_protocol(context)
    for proto in iterator_protocol:
        proto["protocol_kind"] = "iterator"
        result["python_protocols"].append(proto)

    container_protocol = protocol_extractors.extract_container_protocol(context)
    for proto in container_protocol:
        proto["protocol_kind"] = "container"
        result["python_protocols"].append(proto)

    callable_protocol = protocol_extractors.extract_callable_protocol(context)
    for proto in callable_protocol:
        proto["protocol_kind"] = "callable"
        result["python_protocols"].append(proto)

    comparison_protocol = protocol_extractors.extract_comparison_protocol(context)
    for proto in comparison_protocol:
        proto["protocol_kind"] = "comparison"
        result["python_protocols"].append(proto)

    arithmetic_protocol = protocol_extractors.extract_arithmetic_protocol(context)
    for proto in arithmetic_protocol:
        proto["protocol_kind"] = "arithmetic"
        result["python_protocols"].append(proto)

    pickle_protocol = protocol_extractors.extract_pickle_protocol(context)
    for proto in pickle_protocol:
        proto["protocol_kind"] = "pickle"
        result["python_protocols"].append(proto)

    weakref_usage = protocol_extractors.extract_weakref_usage(context)
    for wr in weakref_usage:
        wr["module"] = "weakref"
        result["python_stdlib_usage"].append(wr)

    contextvar_usage = protocol_extractors.extract_contextvar_usage(context)
    for cv in contextvar_usage:
        cv["module"] = "contextvars"
        result["python_stdlib_usage"].append(cv)

    # module_attributes → python_imports_advanced (import_type='module_attr')
    module_attributes = protocol_extractors.extract_module_attributes(context)
    for attr in module_attributes:
        attr["import_type"] = "module_attr"
        result["python_imports_advanced"].append(attr)

    class_decorators = protocol_extractors.extract_class_decorators(context)
    for dec in class_decorators:
        dec["feature_kind"] = "class_decorator"
        result["python_class_features"].append(dec)

    # namespace_packages → python_imports_advanced (import_type='namespace')
    namespace_packages = advanced_extractors.extract_namespace_packages(context)
    for pkg in namespace_packages:
        pkg["import_type"] = "namespace"
        result["python_imports_advanced"].append(pkg)

    python_exports = core_extractors.extract_python_exports(context)
    for exp in python_exports:
        exp["import_kind"] = "export"
        exp["export_type"] = exp.get("type")
        result["python_imports_advanced"].append(exp)

    cached_property = advanced_extractors.extract_cached_property(context)
    for cp in cached_property:
        cp["descriptor_kind"] = "cached_property"
        result["python_descriptors"].append(cp)

    descriptor_protocol = advanced_extractors.extract_descriptor_protocol(context)
    for dp in descriptor_protocol:
        dp["descriptor_kind"] = "descriptor_protocol"
        result["python_descriptors"].append(dp)

    attribute_access_protocol = advanced_extractors.extract_attribute_access_protocol(context)
    for aap in attribute_access_protocol:
        aap["descriptor_kind"] = "attr_access"
        result["python_descriptors"].append(aap)

    copy_protocol = advanced_extractors.extract_copy_protocol(context)
    for cp in copy_protocol:
        cp["protocol_kind"] = "copy"
        result["python_protocols"].append(cp)

    ellipsis_usage = advanced_extractors.extract_ellipsis_usage(context)
    for ell in ellipsis_usage:
        ell["expression_type"] = "ellipsis"
        result["python_expressions"].append(ell)

    bytes_operations = advanced_extractors.extract_bytes_operations(context)
    for bo in bytes_operations:
        bo["expression_type"] = "bytes"
        result["python_expressions"].append(bo)

    exec_eval_compile = advanced_extractors.extract_exec_eval_compile(context)
    for eec in exec_eval_compile:
        eec["expression_type"] = "exec"
        result["python_expressions"].append(eec)

    async_functions = async_extractors.extract_async_functions(context)
    for af in async_functions:
        af["function_kind"] = "async"
        result["python_functions_advanced"].append(af)

    # await_expressions → python_expressions (expression_type='await')
    await_expressions = async_extractors.extract_await_expressions(context)
    for aw in await_expressions:
        aw["expression_type"] = "await"
        result["python_expressions"].append(aw)

    async_generators = async_extractors.extract_async_generators(context)
    for ag in async_generators:
        ag["function_kind"] = "async_generator"
        result["python_functions_advanced"].append(ag)

    protocols = type_extractors.extract_protocols(context)
    for proto in protocols:
        proto["type_kind"] = "protocol"
        result["python_type_definitions"].append(proto)

    generics = type_extractors.extract_generics(context)
    for gen in generics:
        gen["type_kind"] = "generic"
        result["python_type_definitions"].append(gen)

    typed_dicts = type_extractors.extract_typed_dicts(context)
    for td in typed_dicts:
        td["type_kind"] = "typed_dict"
        result["python_type_definitions"].append(td)

    literals = type_extractors.extract_literals(context)
    for lit in literals:
        lit["literal_kind"] = "literal"
        result["python_literals"].append(lit)

    overloads = type_extractors.extract_overloads(context)
    for ovl in overloads:
        ovl["literal_kind"] = "overload"
        result["python_literals"].append(ovl)

    cdk_constructs = cdk_extractor.extract_python_cdk_constructs(context)
    if cdk_constructs:
        result["cdk_constructs"].extend(cdk_constructs)

    cfg = cfg_extractor.extract_python_cfg(context)
    if cfg:
        result["cfg"].extend(cfg)

    symbols = result.get("symbols", [])
    if symbols:
        seen = set()
        unique_symbols = []
        duplicates = []
        for sym in symbols:
            key = (sym.get("name"), sym.get("line"), sym.get("type"), sym.get("col", 0))
            if key in seen:
                duplicates.append(sym)
            else:
                seen.add(key)
                unique_symbols.append(sym)

        if duplicates:
            result["symbols"] = unique_symbols

    return result
