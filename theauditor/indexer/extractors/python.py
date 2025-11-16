"""Python file extractor.

Handles extraction of Python-specific elements including:
- Python imports (import/from statements)
- Flask/FastAPI route decorators with middleware
- AST-based symbol extraction

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
This is an EXTRACTOR layer module. It:
- RECEIVES: file_info dict (contains 'path' key from indexer)
- DELEGATES: To ast_parser.extract_X(tree) methods
- RETURNS: Extracted data WITHOUT file_path keys

The INDEXER layer (indexer/__init__.py) provides file_path and stores to database.
See indexer/__init__.py:619-564 for _store_extracted_data() implementation.

This separation ensures single source of truth for file paths.
"""

import ast
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import BaseExtractor
from .sql import parse_sql_query
from theauditor.ast_extractors import python as python_impl
from theauditor.ast_extractors.base import get_node_name
from theauditor.ast_extractors.python import (
    advanced_extractors,  # Python Coverage V2 - Advanced
    async_extractors,
    behavioral_extractors,
    cdk_extractor,
    class_feature_extractors,  # Python Coverage V2 - Week 4
    collection_extractors,  # Python Coverage V2 - Week 3
    control_flow_extractors,  # Python Coverage V2 - Week 5
    core_extractors,
    data_flow_extractors,
    django_advanced_extractors,
    exception_flow_extractors,
    flask_extractors,
    framework_extractors,
    fundamental_extractors,  # Python Coverage V2 - Week 1
    operator_extractors,  # Python Coverage V2 - Week 2
    performance_extractors,
    protocol_extractors,  # Python Coverage V2 - Week 6
    security_extractors,
    state_mutation_extractors,
    stdlib_pattern_extractors,  # Python Coverage V2 - Week 4
    testing_extractors,
    type_extractors
)


class PythonExtractor(BaseExtractor):
    """Extractor for Python files."""
    
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports."""
        return ['.py', '.pyx']
    
    def extract(self, file_info: Dict[str, Any], content: str, 
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all relevant information from a Python file.
        
        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree
            
        Returns:
            Dictionary containing all extracted data
        """
        result = {
            'imports': [],
            'routes': [],
            'symbols': [],
            'assignments': [],
            'function_calls': [],
            'returns': [],
            'variable_usage': [],  # CRITICAL: Track all variable usage for complete analysis
            'cfg': [],  # Control flow graph data
            'object_literals': [],  # Dict literal parsing for dynamic dispatch
            'type_annotations': [],
            'resolved_imports': {},
            'orm_relationships': [],
            'python_orm_models': [],
            'python_orm_fields': [],
            'python_routes': [],
            'python_blueprints': [],
            'python_validators': [],
            'cdk_constructs': [],  # AWS CDK constructs
            'cdk_construct_properties': [],  # CDK construct properties
            # Phase 2.2A: New Python pattern extractions
            'python_decorators': [],  # All decorator usage
            'python_context_managers': [],  # with statements and context manager classes
            'python_async_functions': [],  # async def functions
            'python_await_expressions': [],  # await calls
            'python_async_generators': [],  # async for and async generator functions
            'python_pytest_fixtures': [],  # @pytest.fixture decorators
            'python_pytest_parametrize': [],  # @pytest.mark.parametrize decorators
            'python_pytest_markers': [],  # Custom pytest markers
            'python_mock_patterns': [],  # unittest.mock usage
            'python_protocols': [],  # Protocol classes
            'python_generics': [],  # Generic[T] classes
            'python_typed_dicts': [],  # TypedDict definitions
            'python_literals': [],  # Literal type usage
            'python_overloads': [],  # @overload decorators
            # Django framework extractions
            'python_django_views': [],  # Django Class-Based Views
            'python_django_forms': [],  # Django Form definitions
            'python_django_form_fields': [],  # Django Form field definitions
            'python_django_admin': [],  # Django Admin customization
            'python_django_middleware': [],  # Django Middleware
            # Marshmallow validation framework
            'python_marshmallow_schemas': [],  # Marshmallow schema definitions
            'python_marshmallow_fields': [],  # Marshmallow field definitions
            # Django REST Framework validation
            'python_drf_serializers': [],  # DRF serializer definitions
            'python_drf_serializer_fields': [],  # DRF serializer field definitions
            # WTForms validation
            'python_wtforms_forms': [],  # WTForms form definitions
            'python_wtforms_fields': [],  # WTForms field definitions
            # Celery background tasks
            'python_celery_tasks': [],  # Celery task definitions
            'python_celery_task_calls': [],  # Celery task invocations
            'python_celery_beat_schedules': [],  # Celery Beat periodic schedules
            # Generators
            'python_generators': [],  # Generator functions and expressions
            # Flask Framework (Phase 3.1)
            'python_flask_apps': [],  # Flask application factories
            'python_flask_extensions': [],  # Flask extension registrations
            'python_flask_hooks': [],  # Flask request/response hooks
            'python_flask_error_handlers': [],  # Flask error handlers
            'python_flask_websockets': [],  # Flask-SocketIO WebSocket handlers
            'python_flask_cli_commands': [],  # Flask CLI commands
            'python_flask_cors': [],  # Flask CORS configurations
            'python_flask_rate_limits': [],  # Flask rate limiting
            'python_flask_cache': [],  # Flask caching decorators
            # Testing Ecosystem (Phase 3.2)
            'python_unittest_test_cases': [],  # Unittest TestCase classes
            'python_assertion_patterns': [],  # Assertion statements
            'python_pytest_plugin_hooks': [],  # Pytest conftest.py hooks
            'python_hypothesis_strategies': [],  # Hypothesis strategies
            # Security Patterns (Phase 3.3 - OWASP Top 10)
            'python_auth_decorators': [],  # Authentication decorators
            'python_password_hashing': [],  # Password hashing patterns
            'python_jwt_operations': [],  # JWT operations
            'python_sql_injection': [],  # SQL injection vulnerabilities
            'python_command_injection': [],  # Command injection patterns
            'python_path_traversal': [],  # Path traversal vulnerabilities
            'python_dangerous_eval': [],  # eval/exec dangerous calls
            'python_crypto_operations': [],  # Cryptography operations
            # Phase 3.4: Django Advanced Patterns
            'python_django_signals': [],  # Django signal definitions and connections
            'python_django_receivers': [],  # Django @receiver decorators
            'python_django_managers': [],  # Django custom managers
            'python_django_querysets': [],  # Django QuerySet definitions
            # Causal Learning Patterns (Week 1 - State Mutations)
            'python_instance_mutations': [],  # self.x = value patterns (side effect detection)
            'python_class_mutations': [],  # ClassName.x = value, cls.x = value patterns
            'python_global_mutations': [],  # global x; x = value patterns
            'python_argument_mutations': [],  # def foo(lst): lst.append(x) patterns
            'python_augmented_assignments': [],  # x += 1 patterns (all target types)
            # Causal Learning Patterns (Week 1 - Exception Flow)
            'python_exception_raises': [],  # raise ValueError("msg") patterns
            'python_exception_catches': [],  # except ValueError as e: ... patterns
            'python_finally_blocks': [],  # finally: cleanup() patterns
            'python_context_managers_enhanced': [],  # with open(...) as f: ... patterns (enhanced)
            # Causal Learning Patterns (Week 2 - Data Flow)
            'python_io_operations': [],  # File/DB/Network/Process/Env I/O operations
            'python_parameter_return_flow': [],  # Parameter → return value flow tracking
            'python_closure_captures': [],  # Closure variable captures from outer scope
            'python_nonlocal_access': [],  # nonlocal variable modifications
            'python_conditional_calls': [],  # Function calls under conditional execution
            # Causal Learning Patterns (Week 3 - Behavioral)
            'python_recursion_patterns': [],  # Recursion detection (direct, tail, mutual)
            'python_generator_yields': [],  # Generator yield patterns (enhanced)
            'python_property_patterns': [],  # Property getters/setters with computation/validation
            'python_dynamic_attributes': [],  # __getattr__, __setattr__, etc.
            # Causal Learning Patterns (Week 4 - Performance)
            'python_loop_complexity': [],  # Loop nesting levels and complexity estimation
            'python_resource_usage': [],  # Large allocations, file handles, etc.
            'python_memoization_patterns': [],  # Caching patterns and opportunities
            # Python Coverage V2 (Week 1 - Fundamentals)
            'python_comprehensions': [],  # List/dict/set/generator comprehensions
            'python_lambda_functions': [],  # Lambda expressions with closure detection
            'python_slice_operations': [],  # Slice notation patterns (start:stop:step)
            'python_tuple_operations': [],  # Tuple pack/unpack operations
            'python_unpacking_patterns': [],  # Extended unpacking (a, *rest, b = ...)
            'python_none_patterns': [],  # None handling (is None vs == None)
            'python_truthiness_patterns': [],  # Implicit bool conversion patterns
            'python_string_formatting': [],  # String formatting (f-strings, %, format())
            # Python Coverage V2 (Week 2 - Operators)
            'python_operators': [],  # All operators (arithmetic, comparison, logical, bitwise)
            'python_membership_tests': [],  # in/not in operators
            'python_chained_comparisons': [],  # 1 < x < 10
            'python_ternary_expressions': [],  # x if y else z
            'python_walrus_operators': [],  # := assignment expressions
            'python_matrix_multiplication': [],  # @ operator
            # Python Coverage V2 (Week 3 - Collections)
            'python_dict_operations': [],  # Dict methods (keys, values, items, get, etc.)
            'python_list_mutations': [],  # List methods (append, extend, sort, etc.)
            'python_set_operations': [],  # Set operations (union, intersection, etc.)
            'python_string_methods': [],  # String methods (split, join, strip, etc.)
            'python_builtin_usage': [],  # Builtin functions (len, sum, max, sorted, etc.)
            'python_itertools_usage': [],  # Itertools functions
            'python_functools_usage': [],  # Functools functions
            'python_collections_usage': [],  # Collections module (defaultdict, Counter, etc.)
            # Python Coverage V2 (Week 4 - Advanced Class Features)
            'python_metaclasses': [],  # Metaclass definitions and usage
            'python_descriptors': [],  # Descriptor protocol (__get__, __set__, __delete__)
            'python_dataclasses': [],  # @dataclass decorator usage
            'python_enums': [],  # Enum class definitions
            'python_slots': [],  # __slots__ usage
            'python_abstract_classes': [],  # ABC and @abstractmethod
            'python_method_types': [],  # @classmethod, @staticmethod, instance methods
            'python_multiple_inheritance': [],  # Classes with multiple base classes
            'python_dunder_methods': [],  # Magic methods (__init__, __str__, etc.)
            'python_visibility_conventions': [],  # _private, __name_mangling
            # Python Coverage V2 (Week 4 - Stdlib Patterns)
            'python_regex_patterns': [],  # re module usage
            'python_json_operations': [],  # json.dumps/loads
            'python_datetime_operations': [],  # datetime module usage
            'python_path_operations': [],  # pathlib and os.path usage
            'python_logging_patterns': [],  # logger.debug/info/error
            'python_threading_patterns': [],  # Thread, Lock, Queue, etc.
            'python_contextlib_patterns': [],  # @contextmanager, closing(), etc.
            'python_type_checking': [],  # isinstance(), issubclass(), type()
            # Python Coverage V2 (Week 5 - Control Flow)
            'python_for_loops': [],  # for loops with enumerate/zip detection
            'python_while_loops': [],  # while loops with infinite loop detection
            'python_async_for_loops': [],  # async for loops
            'python_if_statements': [],  # if/elif/else chains
            'python_match_statements': [],  # match/case (Python 3.10+)
            'python_break_continue_pass': [],  # Loop control flow
            'python_assert_statements': [],  # assert statements
            'python_del_statements': [],  # del statements
            'python_import_statements': [],  # import/from statements (enhanced)
            'python_with_statements': [],  # with/async with statements
            # Python Coverage V2 (Week 6 - Protocols)
            'python_iterator_protocol': [],  # __iter__, __next__ implementations
            'python_container_protocol': [],  # __len__, __getitem__, etc.
            'python_callable_protocol': [],  # __call__ implementations
            'python_comparison_protocol': [],  # Rich comparison methods
            'python_arithmetic_protocol': [],  # Arithmetic dunder methods
            'python_pickle_protocol': [],  # __getstate__, __setstate__, etc.
            'python_weakref_usage': [],  # weakref module usage
            'python_contextvar_usage': [],  # contextvars module usage
            'python_module_attributes': [],  # __name__, __file__, etc.
            'python_class_decorators': [],  # Class-level decorators

            # Python Coverage V2 - Advanced patterns (8)
            'python_namespace_packages': [],  # pkgutil.extend_path usage
            'python_cached_property': [],  # @cached_property decorator
            'python_descriptor_protocol': [],  # __get__, __set__, __delete__
            'python_attribute_access_protocol': [],  # __getattr__, __setattr__, etc.
            'python_copy_protocol': [],  # __copy__, __deepcopy__
            'python_ellipsis_usage': [],  # Ellipsis (...) usage
            'python_bytes_operations': [],  # bytes/bytearray operations
            'python_exec_eval_compile': [],  # exec/eval/compile usage
        }
        seen_symbols = set()
        
        # Extract imports using AST (proper Python import extraction)
        if tree and isinstance(tree, dict):
            result['imports'] = self._extract_imports_ast(tree)
            import os
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Python extractor found {len(result['imports'])} imports in {file_info['path']}")
            resolved = self._resolve_imports(file_info, tree)
            if resolved:
                result['resolved_imports'] = resolved
        else:
            # No AST available - skip import extraction
            result['imports'] = []
            result['resolved_imports'] = {}
            import os
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG] Python extractor: No AST for {file_info['path']}, skipping imports")
        
        # If we have an AST tree, extract Python-specific information
        if tree and isinstance(tree, dict):
            # Extract routes with decorators using AST
            result['routes'] = self._extract_routes_ast(tree, file_info['path'])
            
            # Extract symbols from AST parser results
            if self.ast_parser:
                # Functions
                functions = self.ast_parser.extract_functions(tree)
                for func in functions:
                    if func.get('type_annotations'):
                        result['type_annotations'].extend(func['type_annotations'])

                    symbol_entry = {
                        'name': func.get('name', ''),
                        'type': 'function',
                        'line': func.get('line', 0),
                        'end_line': func.get('end_line', func.get('line', 0)),  # Use end_line if available
                        'col': func.get('col', func.get('column', 0)),
                        'column': func.get('column', func.get('col', 0)),
                        'parameters': func.get('parameters', []),
                        'return_type': func.get('return_type'),
                    }
                    key = (file_info['path'], symbol_entry['name'], symbol_entry['type'], symbol_entry['line'], symbol_entry['col'])
                    if key not in seen_symbols:
                        seen_symbols.add(key)
                        result['symbols'].append(symbol_entry)
                
                # Classes
                classes = self.ast_parser.extract_classes(tree)
                for cls in classes:
                    symbol_entry = {
                        'name': cls.get('name', ''),
                        'type': 'class',
                        'line': cls.get('line', 0),
                        'col': cls.get('col', cls.get('column', 0)),
                        'column': cls.get('column', cls.get('col', 0))
                    }
                    key = (file_info['path'], symbol_entry['name'], symbol_entry['type'], symbol_entry['line'], symbol_entry['col'])
                    if key not in seen_symbols:
                        seen_symbols.add(key)
                        result['symbols'].append(symbol_entry)
                # Class/module attribute annotations
                attribute_annotations = core_extractors.extract_python_attribute_annotations(tree, self.ast_parser)
                if attribute_annotations:
                    result['type_annotations'].extend(attribute_annotations)
                
                # Calls and other symbols
                symbols = self.ast_parser.extract_calls(tree)
                for symbol in symbols:
                    symbol_entry = {
                        'name': symbol.get('name', ''),
                        'type': symbol.get('type', 'call'),
                        'line': symbol.get('line', 0),
                        'col': symbol.get('col', symbol.get('column', 0))
                    }
                    key = (file_info['path'], symbol_entry['name'], symbol_entry['type'], symbol_entry['line'], symbol_entry['col'])
                    if key not in seen_symbols:
                        seen_symbols.add(key)
                        result['symbols'].append(symbol_entry)

                # Property accesses for taint analysis (request.args, request.GET, etc.)
                properties = self.ast_parser.extract_properties(tree)
                for prop in properties:
                    symbol_entry = {
                        'name': prop.get('name', ''),
                        'type': 'property',
                        'line': prop.get('line', 0),
                        'col': prop.get('col', prop.get('column', 0))
                    }
                    key = (file_info['path'], symbol_entry['name'], symbol_entry['type'], symbol_entry['line'], symbol_entry['col'])
                    if key not in seen_symbols:
                        seen_symbols.add(key)
                        result['symbols'].append(symbol_entry)

                # ORM metadata (SQLAlchemy & Django)
                sql_models, sql_fields, sql_relationships = framework_extractors.extract_sqlalchemy_definitions(tree, self.ast_parser)
                if sql_models:
                    result['python_orm_models'].extend(sql_models)
                if sql_fields:
                    result['python_orm_fields'].extend(sql_fields)
                if sql_relationships:
                    result['orm_relationships'].extend(sql_relationships)

                django_models, django_relationships = framework_extractors.extract_django_definitions(tree, self.ast_parser)
                if django_models:
                    result['python_orm_models'].extend(django_models)
                if django_relationships:
                    result['orm_relationships'].extend(django_relationships)

                # Django Class-Based Views
                django_cbvs = framework_extractors.extract_django_cbvs(tree, self.ast_parser)
                if django_cbvs:
                    result['python_django_views'].extend(django_cbvs)

                # Django Forms
                django_forms = framework_extractors.extract_django_forms(tree, self.ast_parser)
                if django_forms:
                    result['python_django_forms'].extend(django_forms)

                # Django Form Fields
                django_form_fields = framework_extractors.extract_django_form_fields(tree, self.ast_parser)
                if django_form_fields:
                    result['python_django_form_fields'].extend(django_form_fields)

                # Django Admin
                django_admins = framework_extractors.extract_django_admin(tree, self.ast_parser)
                if django_admins:
                    result['python_django_admin'].extend(django_admins)

                # Django Middleware
                django_middlewares = framework_extractors.extract_django_middleware(tree, self.ast_parser)
                if django_middlewares:
                    result['python_django_middleware'].extend(django_middlewares)

                # Marshmallow Schemas
                marshmallow_schemas = framework_extractors.extract_marshmallow_schemas(tree, self.ast_parser)
                if marshmallow_schemas:
                    result['python_marshmallow_schemas'].extend(marshmallow_schemas)

                # Marshmallow Fields
                marshmallow_fields = framework_extractors.extract_marshmallow_fields(tree, self.ast_parser)
                if marshmallow_fields:
                    result['python_marshmallow_fields'].extend(marshmallow_fields)

                # DRF Serializers
                drf_serializers = framework_extractors.extract_drf_serializers(tree, self.ast_parser)
                if drf_serializers:
                    result['python_drf_serializers'].extend(drf_serializers)

                # DRF Serializer Fields
                drf_serializer_fields = framework_extractors.extract_drf_serializer_fields(tree, self.ast_parser)
                if drf_serializer_fields:
                    result['python_drf_serializer_fields'].extend(drf_serializer_fields)

                # WTForms
                wtforms_forms = framework_extractors.extract_wtforms_forms(tree, self.ast_parser)
                if wtforms_forms:
                    result['python_wtforms_forms'].extend(wtforms_forms)

                # WTForms Fields
                wtforms_fields = framework_extractors.extract_wtforms_fields(tree, self.ast_parser)
                if wtforms_fields:
                    result['python_wtforms_fields'].extend(wtforms_fields)

                # Celery Tasks
                celery_tasks = framework_extractors.extract_celery_tasks(tree, self.ast_parser)
                if celery_tasks:
                    result['python_celery_tasks'].extend(celery_tasks)

                # Celery Task Calls
                celery_task_calls = framework_extractors.extract_celery_task_calls(tree, self.ast_parser)
                if celery_task_calls:
                    result['python_celery_task_calls'].extend(celery_task_calls)

                # Celery Beat Schedules
                celery_beat_schedules = framework_extractors.extract_celery_beat_schedules(tree, self.ast_parser)
                if celery_beat_schedules:
                    result['python_celery_beat_schedules'].extend(celery_beat_schedules)

                # Generators
                generators = core_extractors.extract_generators(tree, self.ast_parser)
                if generators:
                    result['python_generators'].extend(generators)

                # Flask Framework (Phase 3.1)
                flask_apps = flask_extractors.extract_flask_app_factories(tree, self.ast_parser)
                if flask_apps:
                    result['python_flask_apps'].extend(flask_apps)

                flask_extensions = flask_extractors.extract_flask_extensions(tree, self.ast_parser)
                if flask_extensions:
                    result['python_flask_extensions'].extend(flask_extensions)

                flask_hooks = flask_extractors.extract_flask_request_hooks(tree, self.ast_parser)
                if flask_hooks:
                    result['python_flask_hooks'].extend(flask_hooks)

                flask_error_handlers = flask_extractors.extract_flask_error_handlers(tree, self.ast_parser)
                if flask_error_handlers:
                    result['python_flask_error_handlers'].extend(flask_error_handlers)

                flask_websockets = flask_extractors.extract_flask_websocket_handlers(tree, self.ast_parser)
                if flask_websockets:
                    result['python_flask_websockets'].extend(flask_websockets)

                flask_cli_commands = flask_extractors.extract_flask_cli_commands(tree, self.ast_parser)
                if flask_cli_commands:
                    result['python_flask_cli_commands'].extend(flask_cli_commands)

                flask_cors = flask_extractors.extract_flask_cors_configs(tree, self.ast_parser)
                if flask_cors:
                    result['python_flask_cors'].extend(flask_cors)

                flask_rate_limits = flask_extractors.extract_flask_rate_limits(tree, self.ast_parser)
                if flask_rate_limits:
                    result['python_flask_rate_limits'].extend(flask_rate_limits)

                flask_cache = flask_extractors.extract_flask_cache_decorators(tree, self.ast_parser)
                if flask_cache:
                    result['python_flask_cache'].extend(flask_cache)

                # Testing Ecosystem (Phase 3.2)
                unittest_test_cases = testing_extractors.extract_unittest_test_cases(tree, self.ast_parser)
                if unittest_test_cases:
                    result['python_unittest_test_cases'].extend(unittest_test_cases)

                assertion_patterns = testing_extractors.extract_assertion_patterns(tree, self.ast_parser)
                if assertion_patterns:
                    result['python_assertion_patterns'].extend(assertion_patterns)

                pytest_plugin_hooks = testing_extractors.extract_pytest_plugin_hooks(tree, self.ast_parser)
                if pytest_plugin_hooks:
                    result['python_pytest_plugin_hooks'].extend(pytest_plugin_hooks)

                hypothesis_strategies = testing_extractors.extract_hypothesis_strategies(tree, self.ast_parser)
                if hypothesis_strategies:
                    result['python_hypothesis_strategies'].extend(hypothesis_strategies)

                # Security Patterns (Phase 3.3 - OWASP Top 10)
                auth_decorators = security_extractors.extract_auth_decorators(tree, self.ast_parser)
                if auth_decorators:
                    result['python_auth_decorators'].extend(auth_decorators)

                password_hashing = security_extractors.extract_password_hashing(tree, self.ast_parser)
                if password_hashing:
                    result['python_password_hashing'].extend(password_hashing)

                jwt_operations = security_extractors.extract_jwt_operations(tree, self.ast_parser)
                if jwt_operations:
                    result['python_jwt_operations'].extend(jwt_operations)

                sql_injection = security_extractors.extract_sql_injection_patterns(tree, self.ast_parser)
                if sql_injection:
                    result['python_sql_injection'].extend(sql_injection)

                command_injection = security_extractors.extract_command_injection_patterns(tree, self.ast_parser)
                if command_injection:
                    result['python_command_injection'].extend(command_injection)

                path_traversal = security_extractors.extract_path_traversal_patterns(tree, self.ast_parser)
                if path_traversal:
                    result['python_path_traversal'].extend(path_traversal)

                dangerous_eval = security_extractors.extract_dangerous_eval_exec(tree, self.ast_parser)
                if dangerous_eval:
                    result['python_dangerous_eval'].extend(dangerous_eval)

                crypto_operations = security_extractors.extract_crypto_operations(tree, self.ast_parser)
                if crypto_operations:
                    result['python_crypto_operations'].extend(crypto_operations)

                # Phase 3.4: Django Advanced Patterns
                django_signals = django_advanced_extractors.extract_django_signals(tree, self.ast_parser)
                if django_signals:
                    result['python_django_signals'].extend(django_signals)

                django_receivers = django_advanced_extractors.extract_django_receivers(tree, self.ast_parser)
                if django_receivers:
                    result['python_django_receivers'].extend(django_receivers)

                django_managers = django_advanced_extractors.extract_django_managers(tree, self.ast_parser)
                if django_managers:
                    result['python_django_managers'].extend(django_managers)

                django_querysets = django_advanced_extractors.extract_django_querysets(tree, self.ast_parser)
                if django_querysets:
                    result['python_django_querysets'].extend(django_querysets)

                # Causal Learning Patterns (Week 1 - Side Effect Detection)
                instance_mutations = state_mutation_extractors.extract_instance_mutations(tree, self.ast_parser)
                if instance_mutations:
                    result['python_instance_mutations'].extend(instance_mutations)

                class_mutations = state_mutation_extractors.extract_class_mutations(tree, self.ast_parser)
                if class_mutations:
                    result['python_class_mutations'].extend(class_mutations)

                global_mutations = state_mutation_extractors.extract_global_mutations(tree, self.ast_parser)
                if global_mutations:
                    result['python_global_mutations'].extend(global_mutations)

                argument_mutations = state_mutation_extractors.extract_argument_mutations(tree, self.ast_parser)
                if argument_mutations:
                    result['python_argument_mutations'].extend(argument_mutations)

                augmented_assignments = state_mutation_extractors.extract_augmented_assignments(tree, self.ast_parser)
                if augmented_assignments:
                    result['python_augmented_assignments'].extend(augmented_assignments)

                # Exception flow patterns (Priority 1 - Causal Learning Week 1)
                exception_raises = exception_flow_extractors.extract_exception_raises(tree, self.ast_parser)
                if exception_raises:
                    result['python_exception_raises'].extend(exception_raises)

                exception_catches = exception_flow_extractors.extract_exception_catches(tree, self.ast_parser)
                if exception_catches:
                    result['python_exception_catches'].extend(exception_catches)

                finally_blocks = exception_flow_extractors.extract_finally_blocks(tree, self.ast_parser)
                if finally_blocks:
                    result['python_finally_blocks'].extend(finally_blocks)

                context_managers_enhanced = exception_flow_extractors.extract_context_managers(tree, self.ast_parser)
                if context_managers_enhanced:
                    result['python_context_managers_enhanced'].extend(context_managers_enhanced)

                # Data flow patterns (Priority 3 - Causal Learning Week 2)
                io_operations = data_flow_extractors.extract_io_operations(tree, self.ast_parser)
                if io_operations:
                    result['python_io_operations'].extend(io_operations)

                parameter_return_flow = data_flow_extractors.extract_parameter_return_flow(tree, self.ast_parser)
                if parameter_return_flow:
                    result['python_parameter_return_flow'].extend(parameter_return_flow)

                closure_captures = data_flow_extractors.extract_closure_captures(tree, self.ast_parser)
                if closure_captures:
                    result['python_closure_captures'].extend(closure_captures)

                nonlocal_access = data_flow_extractors.extract_nonlocal_access(tree, self.ast_parser)
                if nonlocal_access:
                    result['python_nonlocal_access'].extend(nonlocal_access)

                conditional_calls = data_flow_extractors.extract_conditional_calls(tree, self.ast_parser)
                if conditional_calls:
                    result['python_conditional_calls'].extend(conditional_calls)

                # Behavioral patterns (Priority 5 - Causal Learning Week 3)
                recursion_patterns = behavioral_extractors.extract_recursion_patterns(tree, self.ast_parser)
                if recursion_patterns:
                    result['python_recursion_patterns'].extend(recursion_patterns)

                generator_yields = behavioral_extractors.extract_generator_yields(tree, self.ast_parser)
                if generator_yields:
                    result['python_generator_yields'].extend(generator_yields)

                property_patterns = behavioral_extractors.extract_property_patterns(tree, self.ast_parser)
                if property_patterns:
                    result['python_property_patterns'].extend(property_patterns)

                dynamic_attributes = behavioral_extractors.extract_dynamic_attributes(tree, self.ast_parser)
                if dynamic_attributes:
                    result['python_dynamic_attributes'].extend(dynamic_attributes)

                # Performance patterns (Priority 7 - Causal Learning Week 4)
                loop_complexity = performance_extractors.extract_loop_complexity(tree, self.ast_parser)
                if loop_complexity:
                    result['python_loop_complexity'].extend(loop_complexity)

                resource_usage = performance_extractors.extract_resource_usage(tree, self.ast_parser)
                if resource_usage:
                    result['python_resource_usage'].extend(resource_usage)

                memoization_patterns = performance_extractors.extract_memoization_patterns(tree, self.ast_parser)
                if memoization_patterns:
                    result['python_memoization_patterns'].extend(memoization_patterns)

                # Python Coverage V2 - Week 1: Fundamental patterns
                comprehensions = fundamental_extractors.extract_comprehensions(tree, self.ast_parser)
                if comprehensions:
                    result['python_comprehensions'].extend(comprehensions)

                lambda_functions = fundamental_extractors.extract_lambda_functions(tree, self.ast_parser)
                if lambda_functions:
                    result['python_lambda_functions'].extend(lambda_functions)

                slice_operations = fundamental_extractors.extract_slice_operations(tree, self.ast_parser)
                if slice_operations:
                    result['python_slice_operations'].extend(slice_operations)

                tuple_operations = fundamental_extractors.extract_tuple_operations(tree, self.ast_parser)
                if tuple_operations:
                    result['python_tuple_operations'].extend(tuple_operations)

                unpacking_patterns = fundamental_extractors.extract_unpacking_patterns(tree, self.ast_parser)
                if unpacking_patterns:
                    result['python_unpacking_patterns'].extend(unpacking_patterns)

                none_patterns = fundamental_extractors.extract_none_patterns(tree, self.ast_parser)
                if none_patterns:
                    result['python_none_patterns'].extend(none_patterns)

                truthiness_patterns = fundamental_extractors.extract_truthiness_patterns(tree, self.ast_parser)
                if truthiness_patterns:
                    result['python_truthiness_patterns'].extend(truthiness_patterns)

                string_formatting = fundamental_extractors.extract_string_formatting(tree, self.ast_parser)
                if string_formatting:
                    result['python_string_formatting'].extend(string_formatting)

                # Python Coverage V2 - Week 2: Operators and expressions
                operators = operator_extractors.extract_operators(tree, self.ast_parser)
                if operators:
                    result['python_operators'].extend(operators)

                membership_tests = operator_extractors.extract_membership_tests(tree, self.ast_parser)
                if membership_tests:
                    result['python_membership_tests'].extend(membership_tests)

                chained_comparisons = operator_extractors.extract_chained_comparisons(tree, self.ast_parser)
                if chained_comparisons:
                    result['python_chained_comparisons'].extend(chained_comparisons)

                ternary_expressions = operator_extractors.extract_ternary_expressions(tree, self.ast_parser)
                if ternary_expressions:
                    result['python_ternary_expressions'].extend(ternary_expressions)

                walrus_operators = operator_extractors.extract_walrus_operators(tree, self.ast_parser)
                if walrus_operators:
                    result['python_walrus_operators'].extend(walrus_operators)

                matrix_multiplication = operator_extractors.extract_matrix_multiplication(tree, self.ast_parser)
                if matrix_multiplication:
                    result['python_matrix_multiplication'].extend(matrix_multiplication)

                # Python Coverage V2 - Week 3: Collections and methods
                dict_operations = collection_extractors.extract_dict_operations(tree, self.ast_parser)
                if dict_operations:
                    result['python_dict_operations'].extend(dict_operations)

                list_mutations = collection_extractors.extract_list_mutations(tree, self.ast_parser)
                if list_mutations:
                    result['python_list_mutations'].extend(list_mutations)

                set_operations = collection_extractors.extract_set_operations(tree, self.ast_parser)
                if set_operations:
                    result['python_set_operations'].extend(set_operations)

                string_methods = collection_extractors.extract_string_methods(tree, self.ast_parser)
                if string_methods:
                    result['python_string_methods'].extend(string_methods)

                builtin_usage = collection_extractors.extract_builtin_usage(tree, self.ast_parser)
                if builtin_usage:
                    result['python_builtin_usage'].extend(builtin_usage)

                itertools_usage = collection_extractors.extract_itertools_usage(tree, self.ast_parser)
                if itertools_usage:
                    result['python_itertools_usage'].extend(itertools_usage)

                functools_usage = collection_extractors.extract_functools_usage(tree, self.ast_parser)
                if functools_usage:
                    result['python_functools_usage'].extend(functools_usage)

                collections_usage = collection_extractors.extract_collections_usage(tree, self.ast_parser)
                if collections_usage:
                    result['python_collections_usage'].extend(collections_usage)

                # Python Coverage V2 - Week 4: Advanced class features
                metaclasses = class_feature_extractors.extract_metaclasses(tree, self.ast_parser)
                if metaclasses:
                    result['python_metaclasses'].extend(metaclasses)

                descriptors = class_feature_extractors.extract_descriptors(tree, self.ast_parser)
                if descriptors:
                    result['python_descriptors'].extend(descriptors)

                dataclasses = class_feature_extractors.extract_dataclasses(tree, self.ast_parser)
                if dataclasses:
                    result['python_dataclasses'].extend(dataclasses)

                enums = class_feature_extractors.extract_enums(tree, self.ast_parser)
                if enums:
                    result['python_enums'].extend(enums)

                slots = class_feature_extractors.extract_slots(tree, self.ast_parser)
                if slots:
                    result['python_slots'].extend(slots)

                abstract_classes = class_feature_extractors.extract_abstract_classes(tree, self.ast_parser)
                if abstract_classes:
                    result['python_abstract_classes'].extend(abstract_classes)

                method_types = class_feature_extractors.extract_method_types(tree, self.ast_parser)
                if method_types:
                    result['python_method_types'].extend(method_types)

                multiple_inheritance = class_feature_extractors.extract_multiple_inheritance(tree, self.ast_parser)
                if multiple_inheritance:
                    result['python_multiple_inheritance'].extend(multiple_inheritance)

                dunder_methods = class_feature_extractors.extract_dunder_methods(tree, self.ast_parser)
                if dunder_methods:
                    result['python_dunder_methods'].extend(dunder_methods)

                visibility_conventions = class_feature_extractors.extract_visibility_conventions(tree, self.ast_parser)
                if visibility_conventions:
                    result['python_visibility_conventions'].extend(visibility_conventions)

                # Python Coverage V2 - Week 4: Stdlib patterns
                regex_patterns = stdlib_pattern_extractors.extract_regex_patterns(tree, self.ast_parser)
                if regex_patterns:
                    result['python_regex_patterns'].extend(regex_patterns)

                json_operations = stdlib_pattern_extractors.extract_json_operations(tree, self.ast_parser)
                if json_operations:
                    result['python_json_operations'].extend(json_operations)

                datetime_operations = stdlib_pattern_extractors.extract_datetime_operations(tree, self.ast_parser)
                if datetime_operations:
                    result['python_datetime_operations'].extend(datetime_operations)

                path_operations = stdlib_pattern_extractors.extract_path_operations(tree, self.ast_parser)
                if path_operations:
                    result['python_path_operations'].extend(path_operations)

                logging_patterns = stdlib_pattern_extractors.extract_logging_patterns(tree, self.ast_parser)
                if logging_patterns:
                    result['python_logging_patterns'].extend(logging_patterns)

                threading_patterns = stdlib_pattern_extractors.extract_threading_patterns(tree, self.ast_parser)
                if threading_patterns:
                    result['python_threading_patterns'].extend(threading_patterns)

                contextlib_patterns = stdlib_pattern_extractors.extract_contextlib_patterns(tree, self.ast_parser)
                if contextlib_patterns:
                    result['python_contextlib_patterns'].extend(contextlib_patterns)

                type_checking = stdlib_pattern_extractors.extract_type_checking(tree, self.ast_parser)
                if type_checking:
                    result['python_type_checking'].extend(type_checking)

                # Python Coverage V2 - Week 5: Control flow patterns
                for_loops = control_flow_extractors.extract_for_loops(tree, self.ast_parser)
                if for_loops:
                    result['python_for_loops'].extend(for_loops)

                while_loops = control_flow_extractors.extract_while_loops(tree, self.ast_parser)
                if while_loops:
                    result['python_while_loops'].extend(while_loops)

                async_for_loops = control_flow_extractors.extract_async_for_loops(tree, self.ast_parser)
                if async_for_loops:
                    result['python_async_for_loops'].extend(async_for_loops)

                if_statements = control_flow_extractors.extract_if_statements(tree, self.ast_parser)
                if if_statements:
                    result['python_if_statements'].extend(if_statements)

                match_statements = control_flow_extractors.extract_match_statements(tree, self.ast_parser)
                if match_statements:
                    result['python_match_statements'].extend(match_statements)

                break_continue_pass = control_flow_extractors.extract_break_continue_pass(tree, self.ast_parser)
                if break_continue_pass:
                    result['python_break_continue_pass'].extend(break_continue_pass)

                assert_statements = control_flow_extractors.extract_assert_statements(tree, self.ast_parser)
                if assert_statements:
                    result['python_assert_statements'].extend(assert_statements)

                del_statements = control_flow_extractors.extract_del_statements(tree, self.ast_parser)
                if del_statements:
                    result['python_del_statements'].extend(del_statements)

                import_statements = control_flow_extractors.extract_import_statements(tree, self.ast_parser)
                if import_statements:
                    result['python_import_statements'].extend(import_statements)

                with_statements = control_flow_extractors.extract_with_statements(tree, self.ast_parser)
                if with_statements:
                    result['python_with_statements'].extend(with_statements)

                # Python Coverage V2 - Week 6: Protocol patterns
                iterator_protocol = protocol_extractors.extract_iterator_protocol(tree, self.ast_parser)
                if iterator_protocol:
                    result['python_iterator_protocol'].extend(iterator_protocol)

                container_protocol = protocol_extractors.extract_container_protocol(tree, self.ast_parser)
                if container_protocol:
                    result['python_container_protocol'].extend(container_protocol)

                callable_protocol = protocol_extractors.extract_callable_protocol(tree, self.ast_parser)
                if callable_protocol:
                    result['python_callable_protocol'].extend(callable_protocol)

                comparison_protocol = protocol_extractors.extract_comparison_protocol(tree, self.ast_parser)
                if comparison_protocol:
                    result['python_comparison_protocol'].extend(comparison_protocol)

                arithmetic_protocol = protocol_extractors.extract_arithmetic_protocol(tree, self.ast_parser)
                if arithmetic_protocol:
                    result['python_arithmetic_protocol'].extend(arithmetic_protocol)

                pickle_protocol = protocol_extractors.extract_pickle_protocol(tree, self.ast_parser)
                if pickle_protocol:
                    result['python_pickle_protocol'].extend(pickle_protocol)

                weakref_usage = protocol_extractors.extract_weakref_usage(tree, self.ast_parser)
                if weakref_usage:
                    result['python_weakref_usage'].extend(weakref_usage)

                contextvar_usage = protocol_extractors.extract_contextvar_usage(tree, self.ast_parser)
                if contextvar_usage:
                    result['python_contextvar_usage'].extend(contextvar_usage)

                module_attributes = protocol_extractors.extract_module_attributes(tree, self.ast_parser)
                if module_attributes:
                    result['python_module_attributes'].extend(module_attributes)

                class_decorators = protocol_extractors.extract_class_decorators(tree, self.ast_parser)
                if class_decorators:
                    result['python_class_decorators'].extend(class_decorators)

                # Python Coverage V2 - Advanced patterns (8)
                namespace_packages = advanced_extractors.extract_namespace_packages(tree, self.ast_parser)
                if namespace_packages:
                    result['python_namespace_packages'].extend(namespace_packages)

                cached_property = advanced_extractors.extract_cached_property(tree, self.ast_parser)
                if cached_property:
                    result['python_cached_property'].extend(cached_property)

                descriptor_protocol = advanced_extractors.extract_descriptor_protocol(tree, self.ast_parser)
                if descriptor_protocol:
                    result['python_descriptor_protocol'].extend(descriptor_protocol)

                attribute_access_protocol = advanced_extractors.extract_attribute_access_protocol(tree, self.ast_parser)
                if attribute_access_protocol:
                    result['python_attribute_access_protocol'].extend(attribute_access_protocol)

                copy_protocol = advanced_extractors.extract_copy_protocol(tree, self.ast_parser)
                if copy_protocol:
                    result['python_copy_protocol'].extend(copy_protocol)

                ellipsis_usage = advanced_extractors.extract_ellipsis_usage(tree, self.ast_parser)
                if ellipsis_usage:
                    result['python_ellipsis_usage'].extend(ellipsis_usage)

                bytes_operations = advanced_extractors.extract_bytes_operations(tree, self.ast_parser)
                if bytes_operations:
                    result['python_bytes_operations'].extend(bytes_operations)

                exec_eval_compile = advanced_extractors.extract_exec_eval_compile(tree, self.ast_parser)
                if exec_eval_compile:
                    result['python_exec_eval_compile'].extend(exec_eval_compile)

                # AWS CDK Infrastructure-as-Code constructs
                cdk_constructs = cdk_extractor.extract_python_cdk_constructs(tree, self.ast_parser)
                if cdk_constructs:
                    # Return raw CDK construct data - indexer generates composite keys
                    result['cdk_constructs'] = cdk_constructs

                # Extract data flow information for taint analysis
                assignments = self.ast_parser.extract_assignments(tree)
                for assignment in assignments:
                    result['assignments'].append({
                        'line': assignment.get('line', 0),
                        'target_var': assignment.get('target_var', ''),
                        'source_expr': assignment.get('source_expr', ''),
                        'source_vars': assignment.get('source_vars', []),
                        'in_function': assignment.get('in_function', 'global')
                    })
                
                # Extract function calls with arguments
                # CRITICAL: Call Python extractor directly to pass resolved_imports for cross-file taint analysis
                function_params = self.ast_parser._extract_function_parameters(tree, 'python')
                calls_with_args = core_extractors.extract_python_calls_with_args(
                    tree,
                    function_params,
                    self.ast_parser,
                    resolved_imports=result.get('resolved_imports', {})
                )
                for call in calls_with_args:
                    # Skip calls with empty callee_function (violates CHECK constraint)
                    callee = call.get('callee_function', '')
                    if not callee:
                        continue

                    result['function_calls'].append({
                        'line': call.get('line', 0),
                        'caller_function': call.get('caller_function', 'global'),
                        'callee_function': callee,
                        'argument_index': call.get('argument_index', 0),
                        'argument_expr': call.get('argument_expr', ''),
                        'param_name': call.get('param_name', ''),
                        'callee_file_path': call.get('callee_file_path')  # NEW: Cross-file taint analysis
                    })
                
                # Extract return statements
                return_statements = self.ast_parser.extract_returns(tree)
                for ret in return_statements:
                    result['returns'].append({
                        'line': ret.get('line', 0),
                        'function_name': ret.get('function_name', 'global'),
                        'return_expr': ret.get('return_expr', ''),
                        'return_vars': ret.get('return_vars', [])
                    })
            
            # Extract control flow graph using centralized AST infrastructure
            if tree and self.ast_parser:
                result['cfg'] = self.ast_parser.extract_cfg(tree)

            # Extract dict literals using centralized AST infrastructure
            if tree and self.ast_parser:
                result['object_literals'] = self.ast_parser.extract_object_literals(tree)
        else:
            # Fallback to regex extraction for routes if no AST
            # Convert regex results to dictionary format for consistency
            fallback_routes = []
            for method, path in self.extract_routes(content):
                fallback_routes.append({
                    'line': 0,  # No line info from regex
                    'method': method,
                    'pattern': path,
                    'path': file_info['path'],
                    'has_auth': False,  # Can't detect auth from regex
                    'handler_function': '',  # No function name from regex
                    'controls': []
                })
            result['routes'] = fallback_routes
        
        # Extract SQL queries from db.execute() calls using AST
        if tree and isinstance(tree, dict):
            result['sql_queries'] = self._extract_sql_queries_ast(tree, content, file_info.get('path', ''))
        else:
            result['sql_queries'] = []

        # =================================================================
        # JWT EXTRACTION - AST ONLY, NO REGEX
        # =================================================================
        # Edge cases that regex might catch but AST won't: ~0.0001%
        # We accept this loss. If you encounter one, document it and move on.
        # DO NOT ADD REGEX FALLBACKS. EVER.
        if tree:
            result['jwt_patterns'] = self._extract_jwt_from_ast(tree, file_info.get('path', ''))
        else:
            result['jwt_patterns'] = []

        # CRITICAL FIX: Extract variable usage for ALL Python files
        # This is essential for complete taint analysis and dead code detection
        if tree and self.ast_parser:
            result['variable_usage'] = self._extract_variable_usage(tree, content)

        # Pydantic validators & Flask blueprints are AST-driven; safe to extract outside parser guard
        if tree and isinstance(tree, dict):
            validators = framework_extractors.extract_pydantic_validators(tree, self.ast_parser)
            if validators:
                result['python_validators'].extend(validators)
            blueprints = framework_extractors.extract_flask_blueprints(tree, self.ast_parser)
            if blueprints:
                result['python_blueprints'].extend(blueprints)

        # Phase 2.2A: Extract new Python patterns (decorators, async, testing, advanced types)
        if tree and isinstance(tree, dict):
            # Core patterns: decorators and context managers
            decorators = core_extractors.extract_python_decorators(tree, self.ast_parser)
            if decorators:
                result['python_decorators'].extend(decorators)

            context_managers = core_extractors.extract_python_context_managers(tree, self.ast_parser)
            if context_managers:
                result['python_context_managers'].extend(context_managers)

            # Async patterns
            async_functions = async_extractors.extract_async_functions(tree, self.ast_parser)
            if async_functions:
                result['python_async_functions'].extend(async_functions)

            await_expressions = async_extractors.extract_await_expressions(tree, self.ast_parser)
            if await_expressions:
                result['python_await_expressions'].extend(await_expressions)

            async_generators = async_extractors.extract_async_generators(tree, self.ast_parser)
            if async_generators:
                result['python_async_generators'].extend(async_generators)

            # Testing patterns
            pytest_fixtures = testing_extractors.extract_pytest_fixtures(tree, self.ast_parser)
            if pytest_fixtures:
                result['python_pytest_fixtures'].extend(pytest_fixtures)

            pytest_parametrize = testing_extractors.extract_pytest_parametrize(tree, self.ast_parser)
            if pytest_parametrize:
                result['python_pytest_parametrize'].extend(pytest_parametrize)

            pytest_markers = testing_extractors.extract_pytest_markers(tree, self.ast_parser)
            if pytest_markers:
                result['python_pytest_markers'].extend(pytest_markers)

            mock_patterns = testing_extractors.extract_mock_patterns(tree, self.ast_parser)
            if mock_patterns:
                result['python_mock_patterns'].extend(mock_patterns)

            # Advanced type patterns
            protocols = type_extractors.extract_protocols(tree, self.ast_parser)
            if protocols:
                result['python_protocols'].extend(protocols)

            generics = type_extractors.extract_generics(tree, self.ast_parser)
            if generics:
                result['python_generics'].extend(generics)

            typed_dicts = type_extractors.extract_typed_dicts(tree, self.ast_parser)
            if typed_dicts:
                result['python_typed_dicts'].extend(typed_dicts)

            literals = type_extractors.extract_literals(tree, self.ast_parser)
            if literals:
                result['python_literals'].extend(literals)

            overloads = type_extractors.extract_overloads(tree, self.ast_parser)
            if overloads:
                result['python_overloads'].extend(overloads)

        # Mirror route data into python_routes for framework tracking
        if result['routes']:
            for route in result['routes']:
                result['python_routes'].append({
                    'line': route.get('line'),
                    'framework': route.get('framework', 'flask'),
                    'method': route.get('method'),
                    'pattern': route.get('pattern'),
                    'handler_function': route.get('handler_function'),
                    'has_auth': route.get('has_auth', False),
                    'dependencies': route.get('dependencies', []),
                    'blueprint': route.get('blueprint'),
                })

        return result
    
    def _resolve_imports(self, file_info: Dict[str, Any], tree: Dict[str, Any]) -> Dict[str, str]:
        """Resolve Python import targets to absolute module/file paths."""
        resolved: Dict[str, str] = {}
        actual_tree = tree.get("tree")

        if not isinstance(actual_tree, ast.AST):
            return resolved

        # Determine current module parts from file path
        file_path = Path(file_info['path'])
        module_parts = list(file_path.with_suffix('').parts)
        package_parts = module_parts[:-1]  # directory components

        def normalize_path(path: Path) -> str:
            return str(path).replace("\\", "/")

        def module_parts_to_path(parts: List[str]) -> Optional[str]:
            if not parts:
                return None
            candidate_file = Path(*parts).with_suffix('.py')
            candidate_init = Path(*parts) / '__init__.py'

            if (self.root_path / candidate_file).exists():
                return normalize_path(candidate_file)
            if (self.root_path / candidate_init).exists():
                return normalize_path(candidate_init)
            return None

        def resolve_dotted(module_name: str) -> Optional[str]:
            if not module_name:
                return None
            return module_parts_to_path(module_name.split('.'))

        for node in ast.walk(actual_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    resolved_target = resolve_dotted(module_name) or module_name

                    local_name = alias.asname or module_name.split('.')[-1]

                    resolved[module_name] = resolved_target
                    resolved[local_name] = resolved_target

            elif isinstance(node, ast.ImportFrom):
                level = getattr(node, 'level', 0) or 0
                base_parts = package_parts.copy()

                if level:
                    if level <= len(base_parts):
                        base_parts = base_parts[:-level]
                    else:
                        base_parts = []

                module_name = node.module or ""
                module_name_parts = module_name.split('.') if module_name else []
                target_base = base_parts + module_name_parts

                # Resolve module itself
                module_key = '.'.join(part for part in target_base if part)
                module_path = module_parts_to_path(target_base)
                if module_key:
                    resolved[module_key] = module_path or module_key
                elif module_path:
                    resolved[module_path] = module_path

                for alias in node.names:
                    imported_name = alias.name
                    local_name = alias.asname or imported_name

                    full_parts = target_base + [imported_name]
                    symbol_path = module_parts_to_path(full_parts)

                    if symbol_path:
                        resolved_value = symbol_path
                    elif module_path:
                        resolved_value = module_path
                    elif module_key:
                        resolved_value = f"{module_key}.{imported_name}"
                    else:
                        resolved_value = local_name

                    resolved[local_name] = resolved_value

        return resolved
    
    def _extract_routes_ast(self, tree: Dict[str, Any], file_path: str) -> List[Dict]:
        """Extract Flask/FastAPI routes using Python AST.

        Args:
            tree: Parsed AST tree
            file_path: Path to file being analyzed

        Returns:
            List of route dictionaries with all 8 api_endpoints fields:
            - line: Line number of the route handler function
            - method: HTTP method (GET, POST, etc.)
            - pattern: Route pattern (e.g., '/api/users/<id>')
            - path: Full file path (same as file_path)
            - has_auth: Boolean indicating presence of auth decorators
            - handler_function: Name of the handler function
            - controls: List of non-route decorator names (middleware)
        """
        routes = []

        # Check if we have a Python AST tree
        if not isinstance(tree.get("tree"), ast.Module):
            return routes

        # Auth decorator patterns to detect
        AUTH_DECORATORS = frozenset([
            'login_required', 'auth_required', 'permission_required',
            'require_auth', 'authenticated', 'authorize', 'requires_auth',
            'jwt_required', 'token_required', 'verify_jwt', 'check_auth'
        ])

        # Walk the AST to find decorated functions
        for node in ast.walk(tree["tree"]):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_auth = False
                controls: List[str] = []
                framework = None
                blueprint_name = None
                method = 'GET'
                pattern = ''
                route_found = False

                for decorator in node.decorator_list:
                    dec_identifier = get_node_name(decorator)

                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        method_name = decorator.func.attr
                        owner_name = get_node_name(decorator.func.value)

                        if method_name in ['route'] + list(python_impl.FASTAPI_HTTP_METHODS):
                            pattern = ''
                            if decorator.args:
                                path_node = decorator.args[0]
                                if isinstance(path_node, ast.Constant):
                                    pattern = str(path_node.value)
                                elif hasattr(ast, "Str") and isinstance(path_node, ast.Str):
                                    pattern = path_node.s

                            if method_name == 'route':
                                method = 'GET'
                                for keyword in decorator.keywords:
                                    if keyword.arg == 'methods' and isinstance(keyword.value, ast.List) and keyword.value.elts:
                                        element = keyword.value.elts[0]
                                        if isinstance(element, ast.Constant):
                                            method = str(element.value).upper()
                            else:
                                method = method_name.upper()

                            framework = 'flask' if method_name == 'route' else 'fastapi'
                            blueprint_name = owner_name
                            route_found = True
                            dec_identifier = method_name

                    if dec_identifier and dec_identifier in AUTH_DECORATORS:
                        has_auth = True
                    elif dec_identifier and dec_identifier not in ['route'] + list(python_impl.FASTAPI_HTTP_METHODS):
                        controls.append(dec_identifier)

                if route_found:
                    dependencies = []
                    if framework == 'fastapi':
                        dependencies = python_impl._extract_fastapi_dependencies(node)

                    routes.append({
                        'line': node.lineno,
                        'method': method,
                        'pattern': pattern,
                        'path': file_path,
                        'has_auth': has_auth,
                        'handler_function': node.name,
                        'controls': controls,
                        'framework': framework or 'flask',
                        'dependencies': dependencies,
                        'blueprint': blueprint_name if framework == 'flask' else None,
                    })

        return routes

    def _extract_imports_ast(self, tree: Dict[str, Any]) -> List[tuple]:
        """Extract imports from Python AST.

        Uses Python's ast module to accurately extract import statements,
        avoiding false matches in comments, strings, or docstrings.

        Args:
            tree: Parsed AST tree dictionary

        Returns:
            List of (kind, module, line_number) tuples:
            - ('import', 'os', 15)
            - ('from', 'pathlib', 23)
        """
        imports = []

        # Handle None or non-dict input gracefully
        if not tree or not isinstance(tree, dict):
            return imports

        actual_tree = tree.get("tree")

        import os
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG]   _extract_imports_ast: tree type={type(tree)}, has 'tree' key={('tree' in tree) if isinstance(tree, dict) else False}")
            if isinstance(tree, dict) and 'tree' in tree:
                print(f"[DEBUG]   actual_tree type={type(actual_tree)}, isinstance(ast.Module)={isinstance(actual_tree, ast.Module)}")

        if not actual_tree or not isinstance(actual_tree, ast.Module):
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG]   Returning empty - actual_tree check failed")
            return imports

        for node in ast.walk(actual_tree):
            if isinstance(node, ast.Import):
                # import os, sys, pathlib
                for alias in node.names:
                    imports.append(('import', alias.name, node.lineno))

            elif isinstance(node, ast.ImportFrom):
                # from pathlib import Path
                # Store the module name (pathlib), not the imported names
                module = node.module or ''  # Handle relative imports (module can be None)
                if module:  # Only store if module name exists
                    imports.append(('from', module, node.lineno))

        return imports

    def _resolve_imports(self, file_info: Dict[str, Any], tree: Dict[str, Any]) -> Dict[str, str]:
        """Resolve Python imports to module paths or local files."""
        resolved: Dict[str, str] = {}

        if not tree or not isinstance(tree, dict):
            return resolved

        actual_tree = tree.get("tree")
        if not isinstance(actual_tree, ast.AST):
            return resolved

        file_path = Path(file_info['path'])
        package_parts = list(file_path.with_suffix('').parts[:-1])

        def to_path(parts: List[str]) -> Optional[str]:
            if not parts:
                return None
            candidate = Path(*parts).with_suffix('.py')
            candidate_init = Path(*parts) / '__init__.py'
            for target in (candidate, candidate_init):
                absolute = (self.root_path / target).resolve()
                if absolute.exists():
                    return target.as_posix()
            return None

        def register(name: str, value: str) -> None:
            if not name or not value:
                return
            resolved[name] = value

        for node in ast.walk(actual_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    module_parts = module_name.split('.')
                    resolved_value = to_path(module_parts) or module_name
                    local_name = alias.asname or module_parts[-1]
                    register(module_name, resolved_value)
                    register(local_name, resolved_value)
            elif isinstance(node, ast.ImportFrom):
                level = getattr(node, "level", 0) or 0
                base_parts = package_parts.copy()
                if level:
                    base_parts = base_parts[:-level] if level <= len(base_parts) else []
                module_parts = node.module.split('.') if node.module else []
                if module_parts and level == 0:
                    target_base = module_parts
                else:
                    target_base = base_parts + module_parts
                base_resolved = to_path(target_base)
                module_key = '.'.join(part for part in target_base if part)
                if module_key:
                    register(module_key, base_resolved or module_key)
                for alias in node.names:
                    imported_name = alias.name
                    local_name = alias.asname or imported_name
                    full_parts = target_base + [imported_name]
                    resolved_value = to_path(full_parts)
                    if not resolved_value:
                        candidate_key = module_key + '.' + imported_name if module_key else imported_name
                        resolved_value = candidate_key
                    register(local_name, resolved_value)
                    if module_key:
                        register(f"{module_key}.{imported_name}", resolved_value)

        return resolved

    def _determine_sql_source(self, file_path: str, method_name: str) -> str:
        """Determine extraction source category for SQL query (Python).

        Args:
            file_path: Path to the file being analyzed
            method_name: Database method name

        Returns:
            extraction_source category string
        """
        file_path_lower = file_path.lower()

        # Migration files
        if 'migration' in file_path_lower or 'migrate' in file_path_lower:
            return 'migration_file'

        # Database schema files
        if file_path.endswith('.sql') or 'schema' in file_path_lower:
            return 'migration_file'

        # Django/SQLAlchemy ORM methods
        ORM_METHODS = frozenset([
            'filter', 'get', 'create', 'update', 'delete', 'all',  # Django QuerySet
            'select', 'insert', 'update', 'delete',  # SQLAlchemy
            'exec_driver_sql', 'query'  # SQLAlchemy raw
        ])

        if method_name in ORM_METHODS:
            return 'orm_query'

        # Default: direct database execution
        return 'code_execute'

    def _resolve_sql_literal(self, node: ast.AST) -> Optional[str]:
        """Resolve AST node to static SQL string.

        Handles:
        - ast.Constant / ast.Str: Plain strings
        - ast.JoinedStr: F-strings (if all parts are static)
        - ast.BinOp(Add): String concatenation
        - ast.Call(.format): Format strings

        Returns:
            Static SQL string if resolvable, None if dynamic
        """
        # Plain string literal
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        elif isinstance(node, ast.Str):  # Python 3.7
            return node.s

        # F-string: f"SELECT * FROM {table}"
        elif isinstance(node, ast.JoinedStr):
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(str(value.value))
                elif isinstance(value, ast.FormattedValue):
                    # Dynamic expression - can't resolve statically
                    # BUT: If it's a simple constant, we can resolve
                    if isinstance(value.value, ast.Constant):
                        parts.append(str(value.value.value))
                    else:
                        # Dynamic variable/expression - return None (can't analyze)
                        return None
                else:
                    return None
            return ''.join(parts)

        # String concatenation: "SELECT * " + "FROM users"
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._resolve_sql_literal(node.left)
            right = self._resolve_sql_literal(node.right)
            if left is not None and right is not None:
                return left + right
            return None

        # .format() call: "SELECT * FROM {}".format("users")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'format':
                # Get base string
                base = self._resolve_sql_literal(node.func.value)
                if base is None:
                    return None

                # Check if all format arguments are constants
                args = []
                for arg in node.args:
                    if isinstance(arg, ast.Constant):
                        args.append(str(arg.value))
                    else:
                        return None  # Dynamic argument

                try:
                    return base.format(*args)
                except (IndexError, KeyError):
                    return None  # Malformed format string

        return None

    def _extract_sql_queries_ast(self, tree: Dict[str, Any], content: str, file_path: str = '') -> List[Dict]:
        """Extract SQL queries from database execution calls using AST.

        Detects actual SQL execution calls like:
        - cursor.execute("SELECT ...")
        - db.query("INSERT ...")
        - connection.raw("UPDATE ...")

        This avoids the 97.6% false positive rate of regex matching
        by only detecting actual database method calls.

        Args:
            tree: Parsed AST tree dictionary
            content: File content (for extracting string literals)
            file_path: Path to the file being analyzed (for source categorization)

        Returns:
            List of SQL query dictionaries with extraction_source tags
        """
        queries = []
        actual_tree = tree.get("tree")

        if not actual_tree or not isinstance(actual_tree, ast.Module):
            return queries

        # SQL execution method names
        SQL_METHODS = frozenset([
            'execute', 'executemany', 'executescript',  # sqlite3, psycopg2, mysql
            'query', 'raw', 'exec_driver_sql',  # Django ORM, SQLAlchemy
            'select', 'insert', 'update', 'delete',  # Query builder methods
        ])

        # No sqlparse import check - parse_sql_query() will raise ImportError
        # if sqlparse is missing, ensuring hard failure instead of silent skip

        for node in ast.walk(actual_tree):
            if not isinstance(node, ast.Call):
                continue

            # Check if this is a database method call
            method_name = None
            if isinstance(node.func, ast.Attribute):
                method_name = node.func.attr

            if method_name not in SQL_METHODS:
                continue

            # Extract SQL query from first argument (if it's a string literal)
            if not node.args:
                continue

            first_arg = node.args[0]

            # Resolve SQL literal (handles plain strings, f-strings, concatenations, .format())
            query_text = self._resolve_sql_literal(first_arg)

            if not query_text:
                # DEBUG: Log skipped queries
                import os
                if os.environ.get("THEAUDITOR_DEBUG"):
                    node_type = type(first_arg).__name__
                    print(f"[SQL EXTRACT] Skipped dynamic query at {file_path}:{node.lineno} (type: {node_type})")
                continue  # Not a string literal (variable, complex f-string, etc.)

            # Parse SQL using shared helper
            parsed = parse_sql_query(query_text)
            if not parsed:
                continue  # Unparseable or UNKNOWN command

            command, tables = parsed

            # Determine extraction source for intelligent filtering
            extraction_source = self._determine_sql_source(file_path, method_name)

            queries.append({
                'line': node.lineno,
                'query_text': query_text[:1000],  # Limit length
                'command': command,
                'tables': tables,
                'extraction_source': extraction_source
            })

        return queries

    def _extract_jwt_from_ast(self, tree: Dict[str, Any], file_path: str) -> List[Dict]:
        """Extract JWT patterns from PyJWT library calls using AST.

        NO REGEX. This uses Python AST analysis to detect JWT library usage.

        Detects PyJWT library usage:
        - jwt.encode(payload, key, algorithm='HS256')
        - jwt.decode(token, key, algorithms=['HS256'])

        Edge cases: ~0.0001% of obfuscated/dynamic JWT calls might be missed.
        We accept this. AST-first is non-negotiable.

        Args:
            tree: Parsed AST tree dictionary
            file_path: Path to the file being analyzed

        Returns:
            List of JWT pattern dicts matching orchestrator expectations:
            - line: int
            - type: 'jwt_sign' | 'jwt_verify' | 'jwt_decode'
            - full_match: str (function call context)
            - secret_type: 'hardcoded' | 'environment' | 'config' | 'variable' | 'unknown'
            - algorithm: str ('HS256', 'RS256', etc.) or None
        """
        patterns = []
        actual_tree = tree.get("tree")

        if not actual_tree or not isinstance(actual_tree, ast.Module):
            return patterns

        # JWT method names for PyJWT library (frozenset for O(1) lookup)
        JWT_ENCODE_METHODS = frozenset(['encode'])  # jwt.encode()
        JWT_DECODE_METHODS = frozenset(['decode'])  # jwt.decode()

        for node in ast.walk(actual_tree):
            if not isinstance(node, ast.Call):
                continue

            # Check if this is a JWT method call
            method_name = None
            is_jwt_call = False

            if isinstance(node.func, ast.Attribute):
                method_name = node.func.attr
                # Check if the object is 'jwt' (e.g., jwt.encode)
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == 'jwt':
                        is_jwt_call = True

            if not is_jwt_call or not method_name:
                continue

            # Determine pattern type
            pattern_type = None
            if method_name in JWT_ENCODE_METHODS:
                pattern_type = 'jwt_sign'
            elif method_name in JWT_DECODE_METHODS:
                pattern_type = 'jwt_decode'

            if not pattern_type:
                continue

            line = node.lineno

            if pattern_type == 'jwt_sign':
                # jwt.encode(payload, key, algorithm='HS256')
                # args[0]=payload, args[1]=key
                # keywords may contain algorithm
                secret_node = None
                algorithm = 'HS256'  # Default per JWT spec

                # Extract key argument (second positional argument)
                if len(node.args) >= 2:
                    secret_node = node.args[1]

                # Extract algorithm from keyword arguments
                for keyword in node.keywords:
                    if keyword.arg == 'algorithm':
                        if isinstance(keyword.value, ast.Constant):
                            algorithm = keyword.value.value
                        elif isinstance(keyword.value, ast.Str):  # Python 3.7 compat
                            algorithm = keyword.value.s

                # Categorize secret source
                secret_type = 'unknown'
                if secret_node:
                    if isinstance(secret_node, (ast.Constant, ast.Str)):
                        # Hardcoded string literal
                        secret_type = 'hardcoded'
                    elif isinstance(secret_node, ast.Subscript):
                        # os.environ['KEY'] or config['key']
                        if isinstance(secret_node.value, ast.Attribute):
                            if hasattr(secret_node.value, 'attr'):
                                if secret_node.value.attr == 'environ':
                                    secret_type = 'environment'
                        elif isinstance(secret_node.value, ast.Name):
                            if secret_node.value.id in ['config', 'settings', 'secrets']:
                                secret_type = 'config'
                    elif isinstance(secret_node, ast.Call):
                        # os.getenv('KEY')
                        if isinstance(secret_node.func, ast.Attribute):
                            if secret_node.func.attr == 'getenv':
                                secret_type = 'environment'
                        elif isinstance(secret_node.func, ast.Name):
                            if secret_node.func.id == 'getenv':
                                secret_type = 'environment'
                    elif isinstance(secret_node, ast.Attribute):
                        # config.JWT_SECRET or settings.SECRET_KEY
                        if isinstance(secret_node.value, ast.Name):
                            if secret_node.value.id in ['config', 'settings', 'secrets']:
                                secret_type = 'config'
                    elif isinstance(secret_node, ast.Name):
                        # Variable reference
                        secret_type = 'variable'

                full_match = f"jwt.encode(...)"

                patterns.append({
                    'line': line,
                    'type': pattern_type,
                    'full_match': full_match,
                    'secret_type': secret_type,
                    'algorithm': algorithm
                })

            elif pattern_type == 'jwt_decode':
                # jwt.decode(token, key, algorithms=['HS256'])
                algorithm = None

                # Extract algorithms from keyword arguments
                for keyword in node.keywords:
                    if keyword.arg == 'algorithms':
                        # algorithms is a list
                        if isinstance(keyword.value, ast.List):
                            if keyword.value.elts:
                                first_algo = keyword.value.elts[0]
                                if isinstance(first_algo, ast.Constant):
                                    algorithm = first_algo.value
                                elif isinstance(first_algo, ast.Str):
                                    algorithm = first_algo.s

                full_match = f"jwt.decode(...)"

                patterns.append({
                    'line': line,
                    'type': pattern_type,
                    'full_match': full_match,
                    'secret_type': None,  # Not applicable for decode
                    'algorithm': algorithm
                })

        return patterns

    def _extract_variable_usage(self, tree: Dict[str, Any], content: str) -> List[Dict]:
        """Extract ALL variable usage for complete data flow analysis.

        This is critical for taint analysis, dead code detection, and
        understanding the complete data flow in Python code.

        Args:
            tree: Parsed AST tree dictionary
            content: File content

        Returns:
            List of all variable usage records with read/write/delete operations
        """
        usage = []
        actual_tree = tree.get("tree")

        if not actual_tree or not isinstance(actual_tree, ast.Module):
            return usage

        try:
            # Build function ranges for accurate scope mapping
            function_ranges = {}
            class_ranges = {}

            # First pass: Map all functions and classes
            for node in ast.walk(actual_tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                        function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)
                elif isinstance(node, ast.ClassDef):
                    if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                        class_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

            # Helper to determine scope for a line number
            def get_scope(line_no):
                # Check if in a function
                for fname, (start, end) in function_ranges.items():
                    if start <= line_no <= end:
                        # Check if this function is inside a class
                        for cname, (cstart, cend) in class_ranges.items():
                            if cstart <= start <= cend:
                                return f"{cname}.{fname}"
                        return fname

                # Check if in a class (but not in a method)
                for cname, (start, end) in class_ranges.items():
                    if start <= line_no <= end:
                        return cname

                return "global"

            # Second pass: Extract all variable usage
            for node in ast.walk(actual_tree):
                if isinstance(node, ast.Name) and hasattr(node, 'lineno'):
                    # Determine usage type based on context
                    usage_type = "read"
                    if isinstance(node.ctx, ast.Store):
                        usage_type = "write"
                    elif isinstance(node.ctx, ast.Del):
                        usage_type = "delete"
                    elif isinstance(node.ctx, ast.AugStore):
                        usage_type = "augmented_write"  # +=, -=, etc.
                    elif isinstance(node.ctx, ast.Param):
                        usage_type = "param"  # Function parameter

                    scope = get_scope(node.lineno)

                    usage.append({
                        'line': node.lineno,
                        'variable_name': node.id,
                        'usage_type': usage_type,
                        'in_component': scope,  # In Python, this is the function/class name
                        'in_hook': '',  # Python doesn't have hooks
                        'scope_level': 0 if scope == "global" else (2 if "." in scope else 1)
                    })

                # Also track attribute access (e.g., self.var, obj.attr)
                elif isinstance(node, ast.Attribute) and hasattr(node, 'lineno'):
                    # Build the full attribute chain
                    attr_chain = []
                    current = node
                    while isinstance(current, ast.Attribute):
                        attr_chain.append(current.attr)
                        current = current.value

                    # Add the base
                    if isinstance(current, ast.Name):
                        attr_chain.append(current.id)

                    # Reverse to get correct order
                    full_name = ".".join(reversed(attr_chain))

                    # Determine usage type
                    usage_type = "read"
                    if isinstance(node.ctx, ast.Store):
                        usage_type = "write"
                    elif isinstance(node.ctx, ast.Del):
                        usage_type = "delete"

                    scope = get_scope(node.lineno)

                    usage.append({
                        'line': node.lineno,
                        'variable_name': full_name,
                        'usage_type': usage_type,
                        'in_component': scope,
                        'in_hook': '',
                        'scope_level': 0 if scope == "global" else (2 if "." in scope else 1)
                    })

                # Track function/method calls as variable usage (the function name is "read")
                elif isinstance(node, ast.Call) and hasattr(node, 'lineno'):
                    func_name = None
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        # Build the call chain
                        attr_chain = []
                        current = node.func
                        while isinstance(current, ast.Attribute):
                            attr_chain.append(current.attr)
                            current = current.value
                        if isinstance(current, ast.Name):
                            attr_chain.append(current.id)
                        func_name = ".".join(reversed(attr_chain))

                    if func_name:
                        scope = get_scope(node.lineno)
                        usage.append({
                            'line': node.lineno,
                            'variable_name': func_name,
                            'usage_type': 'call',  # Special type for function calls
                            'in_component': scope,
                            'in_hook': '',
                            'scope_level': 0 if scope == "global" else (2 if "." in scope else 1)
                        })

            # Deduplicate while preserving order
            seen = set()
            deduped_usage = []
            for use in usage:
                key = (use['line'], use['variable_name'], use['usage_type'])
                if key not in seen:
                    seen.add(key)
                    deduped_usage.append(use)

            return deduped_usage

        except Exception as e:
            # Log error but don't fail the extraction
            import os
            if os.environ.get("THEAUDITOR_DEBUG"):
                import sys
                print(f"[DEBUG] Error in Python variable extraction: {e}", file=sys.stderr)
            return usage
