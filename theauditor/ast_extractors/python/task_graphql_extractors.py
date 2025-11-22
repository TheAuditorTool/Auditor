"""Task queue and GraphQL resolver extractors.

This module extracts async task queue and GraphQL resolver patterns:
- Celery: Task definitions (@task, @shared_task), task invocations (.delay, .apply_async), Beat schedules
- GraphQL (Graphene): resolve_* methods in ObjectType classes
- GraphQL (Ariadne): @query.field, @mutation.field decorators
- GraphQL (Strawberry): @strawberry.field decorators

ARCHITECTURAL CONTRACT:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'task_name', 'resolver_name', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
"""
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
from typing import Any, Dict, List, Optional, Tuple, Set

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions (Internal - Duplicated for Self-Containment)
# ============================================================================

def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes.

    Internal helper - duplicated across framework extractor files for self-containment.
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return node.value
    return None


def _keyword_arg(call: ast.Call, name: str) -> ast.AST | None:
    """Fetch keyword argument by name from AST call.

    Internal helper - duplicated across framework extractor files for self-containment.
    """
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _get_bool_constant(node: ast.AST | None) -> bool | None:
    """Return boolean value for constant/literal nodes.

    Internal helper - duplicated across framework extractor files for self-containment.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
    return None


def _dependency_name(call: ast.Call) -> str | None:
    """Extract dependency target from Depends() call.

    Internal helper - duplicated across framework extractor files for self-containment.
    """
    func_name = get_node_name(call.func)
    if not (func_name.endswith("Depends") or func_name == "Depends"):
        return None

    if call.args:
        return get_node_name(call.args[0])

    keyword = _keyword_arg(call, "dependency")
    if keyword:
        return get_node_name(keyword)
    return "Depends"


# ============================================================================
# Celery Task Queue Extractors
# ============================================================================

def extract_celery_tasks(context: FileContext) -> list[dict[str, Any]]:
    """Extract Celery task definitions.

    Detects:
    - @app.task, @shared_task, @celery.task decorators
    - Task arguments (function parameters - injection surface)
    - bind=True (task instance access)
    - serializer parameter (pickle = RCE risk, json = safe)
    - max_retries, retry_backoff (error handling)
    - rate_limit, time_limit (DoS protection)
    - queue name (privilege separation)

    Security relevance:
    - Pickle serializer = insecure deserialization (RCE)
    - Unvalidated task arguments = injection vulnerabilities
    - Missing rate_limit = resource exhaustion
    - Shared queue = privilege escalation risk
    - Missing time_limit = infinite execution (DoS)
    """
    tasks = []
    if not isinstance(context.tree, ast.AST):
        return tasks

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check if function has Celery task decorator
        is_celery_task = False
        decorator_name = None
        bind = False
        serializer = None
        max_retries = None
        rate_limit = None
        time_limit = None
        queue = None

        for decorator in node.decorator_list:
            # Handle @app.task, @shared_task, @celery.task
            if isinstance(decorator, ast.Name):
                dec_name = decorator.id
                if dec_name in ['task', 'shared_task']:
                    is_celery_task = True
                    decorator_name = dec_name
            elif isinstance(decorator, ast.Attribute):
                dec_name = get_node_name(decorator)
                if 'task' in dec_name and ('app.' in dec_name or 'celery.' in dec_name or dec_name.endswith('.task')):
                    is_celery_task = True
                    decorator_name = dec_name
            elif isinstance(decorator, ast.Call):
                # Handle @task(...), @app.task(...), @shared_task(...)
                func_name = get_node_name(decorator.func)
                if 'task' in func_name or 'shared_task' in func_name:
                    is_celery_task = True
                    decorator_name = func_name

                    # Extract decorator keyword arguments
                    for keyword in decorator.keywords:
                        if keyword.arg == 'bind':
                            if isinstance(keyword.value, ast.Constant):
                                bind = bool(keyword.value.value)
                        elif keyword.arg == 'serializer':
                            if isinstance(keyword.value, ast.Constant):
                                serializer = keyword.value.value
                        elif keyword.arg == 'max_retries':
                            if isinstance(keyword.value, ast.Constant):
                                max_retries = keyword.value.value
                        elif keyword.arg == 'rate_limit':
                            if isinstance(keyword.value, ast.Constant):
                                rate_limit = keyword.value.value
                        elif keyword.arg == 'time_limit':
                            if isinstance(keyword.value, ast.Constant):
                                time_limit = keyword.value.value
                        elif keyword.arg == 'queue':
                            if isinstance(keyword.value, ast.Constant):
                                queue = keyword.value.value

        if not is_celery_task:
            continue

        task_name = node.name

        # Extract task arguments (excluding 'self' if bind=True)
        arg_count = 0
        arg_names = []
        for arg in node.args.args:
            if arg.arg != 'self':  # Skip 'self' parameter
                arg_count += 1
                arg_names.append(arg.arg)

        tasks.append({
            "line": node.lineno,
            "task_name": task_name,
            "decorator_name": decorator_name or 'task',
            "arg_count": arg_count,
            "bind": bind,
            "serializer": serializer,
            "max_retries": max_retries,
            "rate_limit": rate_limit,
            "time_limit": time_limit,
            "queue": queue,
        })

    return tasks


def extract_celery_task_calls(context: FileContext) -> list[dict[str, Any]]:
    """Extract Celery task invocation patterns.

    Detects:
    - task.delay(args) - simple invocation
    - task.apply_async(args=(...), countdown=60, queue='high') - advanced invocation
    - chain(task1.s(), task2.s()) - sequential execution
    - group(task1.s(), task2.s()) - parallel execution
    - chord(group(...), callback.s()) - parallel with callback
    - task.s() / task.si() - task signatures

    Security relevance:
    - Taint tracking: user_input -> task.delay(data) -> unsafe task execution
    - Privilege escalation: non-admin calling admin tasks
    - Queue bypass: apply_async with queue override
    """
    calls = []
    if not isinstance(context.tree, ast.AST):
        return calls

    # Track which function we're currently in for caller context
    current_function = None

    for node in context.find_nodes(ast.FunctionDef):
        current_function = node.name

        # Look for Call nodes
        if not isinstance(node, ast.Call):
            continue

        invocation_type = None
        task_name = None
        arg_count = 0
        has_countdown = False
        has_eta = False
        queue_override = None

        # Pattern 1: task.delay() or task.apply_async()
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr

            if attr_name in ['delay', 'apply_async', 's', 'si', 'apply']:
                invocation_type = attr_name

                # Get task name from the object being called
                if isinstance(node.func.value, ast.Name):
                    task_name = node.func.value.id
                elif isinstance(node.func.value, ast.Attribute):
                    # Handle module.task.delay() pattern
                    task_name = get_node_name(node.func.value)

                # Count arguments
                arg_count = len(node.args)

                # For apply_async, check for special kwargs
                if attr_name == 'apply_async':
                    for keyword in node.keywords:
                        if keyword.arg == 'countdown':
                            has_countdown = True
                        elif keyword.arg == 'eta':
                            has_eta = True
                        elif keyword.arg == 'queue' and isinstance(keyword.value, ast.Constant):
                            queue_override = keyword.value.value

        # Pattern 2: chain(), group(), chord() Canvas primitives
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

            if func_name in ['chain', 'group', 'chord']:
                invocation_type = func_name
                task_name = func_name  # Canvas primitives don't have specific task names
                arg_count = len(node.args)  # Number of tasks in the canvas

        # Pattern 3: Fully qualified canvas calls (celery.chain, celery.group)
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            obj_name = get_node_name(node.func.value)

            if attr_name in ['chain', 'group', 'chord'] and 'celery' in obj_name.lower():
                invocation_type = attr_name
                task_name = f"{obj_name}.{attr_name}"
                arg_count = len(node.args)

        # Only record if we detected a Celery invocation pattern
        if invocation_type and task_name:
            calls.append({
                "line": node.lineno,
                "caller_function": current_function or '<module>',
                "task_name": task_name,
                "invocation_type": invocation_type,
                "arg_count": arg_count,
                "has_countdown": has_countdown,
                "has_eta": has_eta,
                "queue_override": queue_override,
            })

    return calls


def extract_celery_beat_schedules(context: FileContext) -> list[dict[str, Any]]:
    """Extract Celery Beat periodic task schedules.

    Detects:
    - app.conf.beat_schedule = {...} dictionary assignments
    - crontab() expressions (minute, hour, day_of_week, day_of_month, month_of_year)
    - schedule() interval expressions (run_every seconds)
    - @periodic_task decorator (deprecated)
    - Task references and arguments in schedules

    Security relevance:
    - Scheduled admin tasks running automatically
    - Overfrequent schedules (DoS risk)
    - Sensitive data operations (backups, cleanups)
    """
    schedules = []
    if not isinstance(context.tree, ast.AST):
        return schedules

    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            # Check if assigning to beat_schedule attribute
            if isinstance(target, ast.Attribute) and target.attr == 'beat_schedule':
                # Parse the dictionary value
                if isinstance(node.value, ast.Dict):
                    for i, (key_node, value_node) in enumerate(zip(node.value.keys, node.value.values)):
                        if not isinstance(key_node, ast.Constant):
                            continue

                        schedule_name = key_node.value

                        # Extract task info from the dict value
                        if isinstance(value_node, ast.Dict):
                            task_name = None
                            schedule_type = None
                            schedule_expression = None
                            args_expr = None
                            kwargs_expr = None

                            # Parse the schedule config dict
                            for sched_key, sched_value in zip(value_node.keys, value_node.values):
                                if not isinstance(sched_key, ast.Constant):
                                    continue

                                key_name = sched_key.value

                                if key_name == 'task':
                                    if isinstance(sched_value, ast.Constant):
                                        task_name = sched_value.value
                                elif key_name == 'schedule':
                                    # Detect schedule type by call name
                                    if isinstance(sched_value, ast.Call):
                                        if isinstance(sched_value.func, ast.Name):
                                            schedule_type = sched_value.func.id  # 'crontab' or 'schedule'

                                            # Build expression string
                                            if schedule_type == 'crontab':
                                                # Extract crontab parameters
                                                parts = []
                                                for keyword in sched_value.keywords:
                                                    if isinstance(keyword.value, ast.Constant):
                                                        parts.append(f"{keyword.arg}={keyword.value.value}")
                                                schedule_expression = ', '.join(parts) if parts else 'crontab()'
                                            elif schedule_type == 'schedule':
                                                # Extract run_every
                                                for keyword in sched_value.keywords:
                                                    if keyword.arg == 'run_every' and isinstance(keyword.value, ast.Constant):
                                                        schedule_expression = f"every {keyword.value.value}s"
                                    elif isinstance(sched_value, ast.Constant):
                                        # Direct number (seconds)
                                        schedule_type = 'interval'
                                        schedule_expression = f"{sched_value.value} seconds"
                                elif key_name == 'args':
                                    # JSON-encode args
                                    args_expr = ast.unparse(sched_value) if hasattr(ast, 'unparse') else str(sched_value)
                                elif key_name == 'kwargs':
                                    # JSON-encode kwargs
                                    kwargs_expr = ast.unparse(sched_value) if hasattr(ast, 'unparse') else str(sched_value)

                            if schedule_name and task_name:
                                schedules.append({
                                    "line": node.lineno,
                                    "schedule_name": schedule_name,
                                    "task_name": task_name,
                                    "schedule_type": schedule_type or 'unknown',
                                    "schedule_expression": schedule_expression,
                                    "args": args_expr,
                                    "kwargs": kwargs_expr,
                                })

        # Pattern 2: @periodic_task decorator (deprecated but still used)
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    func_name = get_node_name(decorator.func)
                    if 'periodic_task' in func_name:
                        # Extract run_every parameter
                        schedule_expression = None
                        for keyword in decorator.keywords:
                            if keyword.arg == 'run_every' and isinstance(keyword.value, ast.Constant):
                                schedule_expression = f"every {keyword.value.value}s"

                        schedules.append({
                            "line": node.lineno,
                            "schedule_name": node.name,
                            "task_name": node.name,
                            "schedule_type": 'periodic_task',
                            "schedule_expression": schedule_expression or 'unknown',
                            "args": None,
                            "kwargs": None,
                        })

    return schedules


# ============================================================================
# GraphQL Resolver Extractors
# ============================================================================

def extract_graphene_resolvers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Graphene GraphQL resolver methods.

    Graphene pattern:
        class UserType(graphene.ObjectType):
            name = graphene.String()

            def resolve_name(self, info):
                return self.name

    Returns resolver metadata WITHOUT field_id (correlation happens in graphql build command).
    """
    resolvers = []

    if not context or not context.tree:
        return resolvers

    for node in context.find_nodes(ast.ClassDef):
        # Check if class inherits from graphene patterns
        is_graphene_type = False
        for base in node.bases:
            base_name = get_node_name(base)
            if 'graphene' in base_name.lower() or 'ObjectType' in base_name:
                is_graphene_type = True
                break

        if not is_graphene_type:
            continue

        # Extract resolve_* methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith('resolve_'):
                # Field name is the part after 'resolve_'
                field_name = item.name[len('resolve_'):]

                # Extract parameters (skip 'self' and 'info')
                params = []
                for idx, arg in enumerate(item.args.args):
                    if arg.arg not in ('self', 'info'):
                        params.append({
                            'param_name': arg.arg,
                            'param_index': idx,
                            'is_kwargs': False
                        })

                # Handle **kwargs
                if item.args.kwarg:
                    params.append({
                        'param_name': item.args.kwarg.arg,
                        'param_index': len(item.args.args),
                        'is_kwargs': True
                    })

                resolvers.append({
                    'line': item.lineno,
                    'resolver_name': item.name,
                    'field_name': field_name,
                    'type_name': node.name,
                    'binding_style': 'graphene-method',
                    'params': params
                })

    return resolvers


def extract_ariadne_resolvers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Ariadne GraphQL resolver decorators.

    Ariadne patterns:
        @query.field("user")
        def resolve_user(obj, info, id):
            return get_user(id)

        @mutation.field("createUser")
        def create_user_resolver(obj, info, name):
            return create_user(name)

    Returns resolver metadata WITHOUT field_id (correlation happens in graphql build command).
    """
    resolvers = []

    if not context or not context.tree:
        return resolvers

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check decorators for Ariadne patterns
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            # Pattern: @query.field("fieldName") or @mutation.field("fieldName")
            decorator_name = get_node_name(decorator.func)

            if '.field' not in decorator_name:
                continue

            # Determine type (Query, Mutation, Subscription)
            if 'query' in decorator_name.lower():
                type_name = 'Query'
            elif 'mutation' in decorator_name.lower():
                type_name = 'Mutation'
            elif 'subscription' in decorator_name.lower():
                type_name = 'Subscription'
            else:
                type_name = 'Unknown'

            # Extract field name from decorator argument
            field_name = None
            if decorator.args and len(decorator.args) > 0:
                field_name = _get_str_constant(decorator.args[0])

            if not field_name:
                continue

            # Extract parameters (skip 'obj' and 'info')
            params = []
            for idx, arg in enumerate(node.args.args):
                if arg.arg not in ('obj', 'info', 'self'):
                    params.append({
                        'param_name': arg.arg,
                        'param_index': idx,
                        'is_kwargs': False
                    })

            # Handle **kwargs
            if node.args.kwarg:
                params.append({
                    'param_name': node.args.kwarg.arg,
                    'param_index': len(node.args.args),
                    'is_kwargs': True
                })

            resolvers.append({
                'line': node.lineno,
                'resolver_name': node.name,
                'field_name': field_name,
                'type_name': type_name,
                'binding_style': 'ariadne-decorator',
                'params': params
            })

    return resolvers


def extract_strawberry_resolvers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Strawberry GraphQL resolver decorators.

    Strawberry patterns:
        @strawberry.type
        class User:
            name: str

            @strawberry.field
            def full_name(self) -> str:
                return f"{self.first_name} {self.last_name}"

    Returns resolver metadata WITHOUT field_id (correlation happens in graphql build command).
    """
    resolvers = []

    if not context or not context.tree:
        return resolvers

    for node in context.find_nodes(ast.ClassDef):
        is_strawberry_type = False
        for decorator in node.decorator_list:
            decorator_name = get_node_name(decorator)
            if 'strawberry' in decorator_name.lower() and 'type' in decorator_name.lower():
                is_strawberry_type = True
                break

        if not is_strawberry_type:
            continue

        # Extract methods with @strawberry.field decorator
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue

            is_strawberry_field = False
            for decorator in item.decorator_list:
                decorator_name = get_node_name(decorator)
                if 'strawberry' in decorator_name.lower() and 'field' in decorator_name.lower():
                    is_strawberry_field = True
                    break

            if not is_strawberry_field:
                continue

            # Extract parameters (skip 'self')
            params = []
            for idx, arg in enumerate(item.args.args):
                if arg.arg != 'self':
                    params.append({
                        'param_name': arg.arg,
                        'param_index': idx,
                        'is_kwargs': False
                    })

            # Handle **kwargs
            if item.args.kwarg:
                params.append({
                    'param_name': item.args.kwarg.arg,
                    'param_index': len(item.args.args),
                    'is_kwargs': True
                })

            resolvers.append({
                'line': item.lineno,
                'resolver_name': item.name,
                'field_name': item.name,  # Strawberry uses method name as field name
                'type_name': node.name,
                'binding_style': 'strawberry-field',
                'params': params
            })

    return resolvers
