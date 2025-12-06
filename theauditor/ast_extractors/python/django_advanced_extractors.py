"""Django Advanced Pattern Extractors (Phase 3.4)"""

import ast
import json
from typing import Any

from theauditor.ast_extractors.base import get_node_name
from theauditor.ast_extractors.python.utils.context import FileContext


def extract_django_signals(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django signal definitions and connections."""
    results = []

    if not context.tree:
        return results

    for node in context.find_nodes(ast.Assign):
        if isinstance(node.value, ast.Call):
            func_name = get_node_name(node.value.func)
            if func_name and "Signal" in func_name:
                signal_name = "unknown"
                if node.targets and isinstance(node.targets[0], ast.Name):
                    signal_name = node.targets[0].id

                providing_args = []
                for keyword in node.value.keywords:
                    if keyword.arg == "providing_args" and isinstance(keyword.value, ast.List):
                        for elt in keyword.value.elts:
                            if isinstance(elt, ast.Constant):
                                providing_args.append(elt.value)

                results.append(
                    {
                        "line": node.lineno,
                        "signal_name": signal_name,
                        "signal_type": "definition",
                        "providing_args": json.dumps(providing_args),
                        "sender": None,
                        "receiver_function": None,
                    }
                )

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "connect":
            signal_name = get_node_name(node.func.value) or "unknown"

            receiver_function = None
            if node.args:
                receiver_function = get_node_name(node.args[0])

            sender = None
            for keyword in node.keywords:
                if keyword.arg == "sender":
                    sender = get_node_name(keyword.value)

            results.append(
                {
                    "line": node.lineno,
                    "signal_name": signal_name,
                    "signal_type": "connection",
                    "providing_args": "[]",
                    "sender": sender,
                    "receiver_function": receiver_function,
                }
            )

    for node in context.find_nodes(ast.ClassDef):
        for base in node.bases:
            base_name = get_node_name(base)
            if base_name and "Signal" in base_name:
                results.append(
                    {
                        "line": node.lineno,
                        "signal_name": node.name,
                        "signal_type": "custom",
                        "providing_args": "[]",
                        "sender": None,
                        "receiver_function": None,
                    }
                )
                break

    return results


def extract_django_receivers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django @receiver decorators."""
    results = []

    if not context.tree:
        return results

    for node in context.find_nodes(ast.FunctionDef):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                func_name = get_node_name(decorator.func)
                if func_name and "receiver" in func_name:
                    signals = []
                    sender = None
                    is_weak = False

                    for arg in decorator.args:
                        signal_name = get_node_name(arg)
                        if signal_name:
                            signals.append(signal_name)

                    for keyword in decorator.keywords:
                        if keyword.arg == "sender":
                            sender = get_node_name(keyword.value)
                        elif keyword.arg == "weak" and isinstance(keyword.value, ast.Constant):
                            is_weak = keyword.value.value is True

                    results.append(
                        {
                            "line": node.lineno,
                            "function_name": node.name,
                            "signals": json.dumps(signals),
                            "sender": sender,
                            "is_weak": is_weak,
                        }
                    )

    return results


def extract_django_managers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django custom manager definitions."""
    results = []

    if not context.tree:
        return results

    for node in context.find_nodes(ast.ClassDef):
        manager_base = None
        for base in node.bases:
            base_name = get_node_name(base)
            if base_name and "Manager" in base_name:
                manager_base = base_name
                break

        if manager_base:
            custom_methods = []
            for item in node.body:
                if (
                    isinstance(item, ast.FunctionDef)
                    and not item.name.startswith("_")
                    and item.name not in ["get_queryset"]
                ):
                    custom_methods.append(item.name)

            results.append(
                {
                    "line": node.lineno,
                    "manager_name": node.name,
                    "base_class": manager_base,
                    "custom_methods": json.dumps(custom_methods),
                    "model_assignment": None,
                }
            )

    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id == "objects"
                and isinstance(node.value, ast.Call)
            ):
                manager_name = get_node_name(node.value.func)
                if manager_name and "Manager" in manager_name:
                    results.append(
                        {
                            "line": node.lineno,
                            "manager_name": manager_name,
                            "base_class": "Manager",
                            "custom_methods": "[]",
                            "model_assignment": "objects",
                        }
                    )

    return results


def extract_django_querysets(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django QuerySet method definitions and chains."""
    results = []

    if not context.tree:
        return results

    for node in context.find_nodes(ast.ClassDef):
        queryset_base = None
        for base in node.bases:
            base_name = get_node_name(base)
            if base_name and "QuerySet" in base_name:
                queryset_base = base_name
                break

        if queryset_base:
            custom_methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                    custom_methods.append(item.name)

            has_as_manager = False
            for call_node in context.find_nodes(ast.Call):
                if (
                    isinstance(call_node.func, ast.Attribute)
                    and call_node.func.attr == "as_manager"
                ):
                    obj_name = get_node_name(call_node.func.value)
                    if obj_name == node.name:
                        has_as_manager = True
                        break

            results.append(
                {
                    "line": node.lineno,
                    "queryset_name": node.name,
                    "base_class": queryset_base,
                    "custom_methods": json.dumps(custom_methods),
                    "has_as_manager": has_as_manager,
                    "method_chain": None,
                }
            )

    queryset_methods = [
        "filter",
        "exclude",
        "order_by",
        "select_related",
        "prefetch_related",
        "annotate",
        "aggregate",
        "values",
        "values_list",
        "distinct",
    ]

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr in queryset_methods:
            chain_parts = []
            current = node
            while isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute):
                if current.func.attr in queryset_methods:
                    chain_parts.append(current.func.attr)
                current = current.func.value
                if isinstance(current, ast.Call):
                    continue
                else:
                    break

            if len(chain_parts) > 1:
                method_chain = ".".join(reversed(chain_parts))
                results.append(
                    {
                        "line": node.lineno,
                        "queryset_name": "chain",
                        "base_class": "QuerySet",
                        "custom_methods": "[]",
                        "has_as_manager": False,
                        "method_chain": method_chain,
                    }
                )

    seen = set()
    deduped = []
    for item in results:
        key = (item["line"], item["queryset_name"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped
