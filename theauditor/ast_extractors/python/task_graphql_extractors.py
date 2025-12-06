"""Task queue and GraphQL resolver extractors."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext

from ..base import get_node_name


def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _keyword_arg(call: ast.Call, name: str) -> ast.AST | None:
    """Fetch keyword argument by name from AST call."""
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _get_bool_constant(node: ast.AST | None) -> bool | None:
    """Return boolean value for constant/literal nodes."""
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
    return None


def _dependency_name(call: ast.Call) -> str | None:
    """Extract dependency target from Depends() call."""
    func_name = get_node_name(call.func)
    if not (func_name.endswith("Depends") or func_name == "Depends"):
        return None

    if call.args:
        return get_node_name(call.args[0])

    keyword = _keyword_arg(call, "dependency")
    if keyword:
        return get_node_name(keyword)
    return "Depends"


def extract_celery_tasks(context: FileContext) -> list[dict[str, Any]]:
    """Extract Celery task definitions."""
    tasks = []
    if not isinstance(context.tree, ast.AST):
        return tasks

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        is_celery_task = False
        decorator_name = None
        bind = False
        serializer = None
        max_retries = None
        rate_limit = None
        time_limit = None
        queue = None

        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                dec_name = decorator.id
                if dec_name in ["task", "shared_task"]:
                    is_celery_task = True
                    decorator_name = dec_name
            elif isinstance(decorator, ast.Attribute):
                dec_name = get_node_name(decorator)
                if "task" in dec_name and (
                    "app." in dec_name or "celery." in dec_name or dec_name.endswith(".task")
                ):
                    is_celery_task = True
                    decorator_name = dec_name
            elif isinstance(decorator, ast.Call):
                func_name = get_node_name(decorator.func)
                if "task" in func_name or "shared_task" in func_name:
                    is_celery_task = True
                    decorator_name = func_name

                    for keyword in decorator.keywords:
                        if keyword.arg == "bind":
                            if isinstance(keyword.value, ast.Constant):
                                bind = bool(keyword.value.value)
                        elif keyword.arg == "serializer":
                            if isinstance(keyword.value, ast.Constant):
                                serializer = keyword.value.value
                        elif keyword.arg == "max_retries":
                            if isinstance(keyword.value, ast.Constant):
                                max_retries = keyword.value.value
                        elif keyword.arg == "rate_limit":
                            if isinstance(keyword.value, ast.Constant):
                                rate_limit = keyword.value.value
                        elif keyword.arg == "time_limit":
                            if isinstance(keyword.value, ast.Constant):
                                time_limit = keyword.value.value
                        elif keyword.arg == "queue" and isinstance(keyword.value, ast.Constant):
                            queue = keyword.value.value

        if not is_celery_task:
            continue

        task_name = node.name

        arg_count = 0
        arg_names = []
        for arg in node.args.args:
            if arg.arg != "self":
                arg_count += 1
                arg_names.append(arg.arg)

        tasks.append(
            {
                "line": node.lineno,
                "task_name": task_name,
                "decorator_name": decorator_name or "task",
                "arg_count": arg_count,
                "bind": bind,
                "serializer": serializer,
                "max_retries": max_retries,
                "rate_limit": rate_limit,
                "time_limit": time_limit,
                "queue": queue,
            }
        )

    return tasks


def extract_celery_task_calls(context: FileContext) -> list[dict[str, Any]]:
    """Extract Celery task invocation patterns."""
    calls = []
    if not isinstance(context.tree, ast.AST):
        return calls

    current_function = None

    for node in context.find_nodes(ast.FunctionDef):
        current_function = node.name

        if not isinstance(node, ast.Call):
            continue

        invocation_type = None
        task_name = None
        arg_count = 0
        has_countdown = False
        has_eta = False
        queue_override = None

        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr

            if attr_name in ["delay", "apply_async", "s", "si", "apply"]:
                invocation_type = attr_name

                if isinstance(node.func.value, ast.Name):
                    task_name = node.func.value.id
                elif isinstance(node.func.value, ast.Attribute):
                    task_name = get_node_name(node.func.value)

                arg_count = len(node.args)

                if attr_name == "apply_async":
                    for keyword in node.keywords:
                        if keyword.arg == "countdown":
                            has_countdown = True
                        elif keyword.arg == "eta":
                            has_eta = True
                        elif keyword.arg == "queue" and isinstance(keyword.value, ast.Constant):
                            queue_override = keyword.value.value

        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

            if func_name in ["chain", "group", "chord"]:
                invocation_type = func_name
                task_name = func_name
                arg_count = len(node.args)

        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            obj_name = get_node_name(node.func.value)

            if attr_name in ["chain", "group", "chord"] and "celery" in obj_name.lower():
                invocation_type = attr_name
                task_name = f"{obj_name}.{attr_name}"
                arg_count = len(node.args)

        if invocation_type and task_name:
            calls.append(
                {
                    "line": node.lineno,
                    "caller_function": current_function or "<module>",
                    "task_name": task_name,
                    "invocation_type": invocation_type,
                    "arg_count": arg_count,
                    "has_countdown": has_countdown,
                    "has_eta": has_eta,
                    "queue_override": queue_override,
                }
            )

    return calls


def extract_celery_beat_schedules(context: FileContext) -> list[dict[str, Any]]:
    """Extract Celery Beat periodic task schedules."""
    schedules = []
    if not isinstance(context.tree, ast.AST):
        return schedules

    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "beat_schedule"
                and isinstance(node.value, ast.Dict)
            ):
                for _i, (key_node, value_node) in enumerate(
                    zip(node.value.keys, node.value.values, strict=True)
                ):
                    if not isinstance(key_node, ast.Constant):
                        continue

                    schedule_name = key_node.value

                    if isinstance(value_node, ast.Dict):
                        task_name = None
                        schedule_type = None
                        schedule_expression = None
                        args_expr = None
                        kwargs_expr = None

                        for sched_key, sched_value in zip(
                            value_node.keys, value_node.values, strict=True
                        ):
                            if not isinstance(sched_key, ast.Constant):
                                continue

                            key_name = sched_key.value

                            if key_name == "task":
                                if isinstance(sched_value, ast.Constant):
                                    task_name = sched_value.value
                            elif key_name == "schedule":
                                if isinstance(sched_value, ast.Call):
                                    if isinstance(sched_value.func, ast.Name):
                                        schedule_type = sched_value.func.id

                                        if schedule_type == "crontab":
                                            parts = []
                                            for keyword in sched_value.keywords:
                                                if isinstance(keyword.value, ast.Constant):
                                                    parts.append(
                                                        f"{keyword.arg}={keyword.value.value}"
                                                    )
                                            schedule_expression = (
                                                ", ".join(parts) if parts else "crontab()"
                                            )
                                        elif schedule_type == "schedule":
                                            for keyword in sched_value.keywords:
                                                if keyword.arg == "run_every" and isinstance(
                                                    keyword.value, ast.Constant
                                                ):
                                                    schedule_expression = (
                                                        f"every {keyword.value.value}s"
                                                    )
                                elif isinstance(sched_value, ast.Constant):
                                    schedule_type = "interval"
                                    schedule_expression = f"{sched_value.value} seconds"
                            elif key_name == "args":
                                args_expr = (
                                    ast.unparse(sched_value)
                                    if hasattr(ast, "unparse")
                                    else str(sched_value)
                                )
                            elif key_name == "kwargs":
                                kwargs_expr = (
                                    ast.unparse(sched_value)
                                    if hasattr(ast, "unparse")
                                    else str(sched_value)
                                )

                        if schedule_name and task_name:
                            schedules.append(
                                {
                                    "line": node.lineno,
                                    "schedule_name": schedule_name,
                                    "task_name": task_name,
                                    "schedule_type": schedule_type or "unknown",
                                    "schedule_expression": schedule_expression,
                                    "args": args_expr,
                                    "kwargs": kwargs_expr,
                                }
                            )

        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    func_name = get_node_name(decorator.func)
                    if "periodic_task" in func_name:
                        schedule_expression = None
                        for keyword in decorator.keywords:
                            if keyword.arg == "run_every" and isinstance(
                                keyword.value, ast.Constant
                            ):
                                schedule_expression = f"every {keyword.value.value}s"

                        schedules.append(
                            {
                                "line": node.lineno,
                                "schedule_name": node.name,
                                "task_name": node.name,
                                "schedule_type": "periodic_task",
                                "schedule_expression": schedule_expression or "unknown",
                                "args": None,
                                "kwargs": None,
                            }
                        )

    return schedules


def extract_graphene_resolvers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Graphene GraphQL resolver methods."""
    resolvers = []

    if not context or not context.tree:
        return resolvers

    for node in context.find_nodes(ast.ClassDef):
        is_graphene_type = False
        for base in node.bases:
            base_name = get_node_name(base)
            if "graphene" in base_name.lower() or "ObjectType" in base_name:
                is_graphene_type = True
                break

        if not is_graphene_type:
            continue

        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("resolve_"):
                field_name = item.name[len("resolve_") :]

                params = []
                for idx, arg in enumerate(item.args.args):
                    if arg.arg not in ("self", "info"):
                        params.append(
                            {"param_name": arg.arg, "param_index": idx, "is_kwargs": False}
                        )

                if item.args.kwarg:
                    params.append(
                        {
                            "param_name": item.args.kwarg.arg,
                            "param_index": len(item.args.args),
                            "is_kwargs": True,
                        }
                    )

                resolvers.append(
                    {
                        "line": item.lineno,
                        "resolver_name": item.name,
                        "field_name": field_name,
                        "type_name": node.name,
                        "binding_style": "graphene-method",
                        "params": params,
                    }
                )

    return resolvers


def extract_ariadne_resolvers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Ariadne GraphQL resolver decorators."""
    resolvers = []

    if not context or not context.tree:
        return resolvers

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            decorator_name = get_node_name(decorator.func)

            if ".field" not in decorator_name:
                continue

            if "query" in decorator_name.lower():
                type_name = "Query"
            elif "mutation" in decorator_name.lower():
                type_name = "Mutation"
            elif "subscription" in decorator_name.lower():
                type_name = "Subscription"
            else:
                type_name = "Unknown"

            field_name = None
            if decorator.args and len(decorator.args) > 0:
                field_name = _get_str_constant(decorator.args[0])

            if not field_name:
                continue

            params = []
            for idx, arg in enumerate(node.args.args):
                if arg.arg not in ("obj", "info", "self"):
                    params.append({"param_name": arg.arg, "param_index": idx, "is_kwargs": False})

            if node.args.kwarg:
                params.append(
                    {
                        "param_name": node.args.kwarg.arg,
                        "param_index": len(node.args.args),
                        "is_kwargs": True,
                    }
                )

            resolvers.append(
                {
                    "line": node.lineno,
                    "resolver_name": node.name,
                    "field_name": field_name,
                    "type_name": type_name,
                    "binding_style": "ariadne-decorator",
                    "params": params,
                }
            )

    return resolvers


def extract_strawberry_resolvers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Strawberry GraphQL resolver decorators."""
    resolvers = []

    if not context or not context.tree:
        return resolvers

    for node in context.find_nodes(ast.ClassDef):
        is_strawberry_type = False
        for decorator in node.decorator_list:
            decorator_name = get_node_name(decorator)
            if "strawberry" in decorator_name.lower() and "type" in decorator_name.lower():
                is_strawberry_type = True
                break

        if not is_strawberry_type:
            continue

        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue

            is_strawberry_field = False
            for decorator in item.decorator_list:
                decorator_name = get_node_name(decorator)
                if "strawberry" in decorator_name.lower() and "field" in decorator_name.lower():
                    is_strawberry_field = True
                    break

            if not is_strawberry_field:
                continue

            params = []
            for idx, arg in enumerate(item.args.args):
                if arg.arg != "self":
                    params.append({"param_name": arg.arg, "param_index": idx, "is_kwargs": False})

            if item.args.kwarg:
                params.append(
                    {
                        "param_name": item.args.kwarg.arg,
                        "param_index": len(item.args.args),
                        "is_kwargs": True,
                    }
                )

            resolvers.append(
                {
                    "line": item.lineno,
                    "resolver_name": item.name,
                    "field_name": item.name,
                    "type_name": node.name,
                    "binding_style": "strawberry-field",
                    "params": params,
                }
            )

    return resolvers
