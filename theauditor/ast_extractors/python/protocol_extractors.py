"""Protocol and module pattern extractors - Dunder protocols and module metadata."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext


def _find_containing_function(node: ast.AST, function_ranges: list) -> str:
    """Find the function containing this node."""
    if not hasattr(node, "lineno"):
        return "global"

    line_no = node.lineno
    for fname, start, end in function_ranges:
        if start <= line_no <= end:
            return fname
    return "global"


def _get_class_methods(class_node: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    """Extract methods from a class definition."""
    methods = {}
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef):
            methods[item.name] = item
    return methods


ITERATOR_METHODS = {"__iter__", "__next__"}
CONTAINER_METHODS = {"__len__", "__getitem__", "__setitem__", "__delitem__", "__contains__"}
COMPARISON_METHODS = {"__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__"}
ARITHMETIC_METHODS = {
    "__add__",
    "__sub__",
    "__mul__",
    "__truediv__",
    "__floordiv__",
    "__mod__",
    "__pow__",
    "__radd__",
    "__rsub__",
    "__rmul__",
    "__rtruediv__",
    "__rfloordiv__",
    "__rmod__",
    "__rpow__",
    "__iadd__",
    "__isub__",
    "__imul__",
    "__itruediv__",
    "__ifloordiv__",
    "__imod__",
    "__ipow__",
}
PICKLE_METHODS = {"__getstate__", "__setstate__", "__reduce__", "__reduce_ex__"}


def extract_iterator_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract iterator protocol implementations."""
    iterator_protocols = []

    if not isinstance(context.tree, ast.AST):
        return iterator_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        has_iter = "__iter__" in methods
        has_next = "__next__" in methods

        if has_iter or has_next:
            raises_stopiteration = False
            if "__next__" in methods:
                for subnode in context.find_nodes(ast.Raise):
                    if isinstance(subnode.exc, ast.Call):
                        if (
                            isinstance(subnode.exc.func, ast.Name)
                            and subnode.exc.func.id == "StopIteration"
                        ):
                            raises_stopiteration = True
                    elif isinstance(subnode.exc, ast.Name) and subnode.exc.id == "StopIteration":
                        raises_stopiteration = True

            is_generator = False
            if "__iter__" in methods:
                for _subnode in context.find_nodes((ast.Yield, ast.YieldFrom)):
                    is_generator = True
                    break

            implemented_methods = [m for m in ITERATOR_METHODS if m in methods]

            iterator_data = {
                "line": node.lineno,
                "class_name": node.name,
                "has_iter": has_iter,
                "has_next": has_next,
                "raises_stopiteration": raises_stopiteration,
                "is_generator": is_generator,
                "implemented_methods": implemented_methods,
            }
            iterator_protocols.append(iterator_data)

    return iterator_protocols


def extract_container_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract container protocol implementations."""
    container_protocols = []

    if not isinstance(context.tree, ast.AST):
        return container_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        has_len = "__len__" in methods
        has_getitem = "__getitem__" in methods
        has_setitem = "__setitem__" in methods
        has_delitem = "__delitem__" in methods
        has_contains = "__contains__" in methods

        if any([has_len, has_getitem, has_setitem, has_delitem, has_contains]):
            is_sequence = False
            is_mapping = False

            if "__getitem__" in methods:
                getitem_method = methods["__getitem__"]

                if getitem_method.args.args:
                    param_name = getitem_method.args.args[-1].arg
                    if "index" in param_name or "idx" in param_name or param_name == "i":
                        is_sequence = True
                    elif "key" in param_name or param_name == "k":
                        is_mapping = True
                    else:
                        is_sequence = has_len
                        is_mapping = not has_len

            implemented_methods = [m for m in CONTAINER_METHODS if m in methods]

            container_data = {
                "line": node.lineno,
                "class_name": node.name,
                "has_len": has_len,
                "has_getitem": has_getitem,
                "has_setitem": has_setitem,
                "has_delitem": has_delitem,
                "has_contains": has_contains,
                "is_sequence": is_sequence,
                "is_mapping": is_mapping,
                "implemented_methods": implemented_methods,
            }
            container_protocols.append(container_data)

    return container_protocols


def extract_callable_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract callable protocol implementations (__call__)."""
    callable_protocols = []

    if not isinstance(context.tree, ast.AST):
        return callable_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        if "__call__" in methods:
            call_method = methods["__call__"]

            param_count = len(call_method.args.args) - 1

            has_args = call_method.args.vararg is not None
            has_kwargs = call_method.args.kwarg is not None

            callable_data = {
                "line": call_method.lineno,
                "class_name": node.name,
                "param_count": param_count,
                "has_args": has_args,
                "has_kwargs": has_kwargs,
                "implemented_methods": ["__call__"],
            }
            callable_protocols.append(callable_data)

    return callable_protocols


def extract_comparison_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract comparison protocol implementations."""
    comparison_protocols = []

    if not isinstance(context.tree, ast.AST):
        return comparison_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        comparison_methods_found = [m for m in COMPARISON_METHODS if m in methods]

        if comparison_methods_found:
            is_total_ordering = False
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    if decorator.id == "total_ordering":
                        is_total_ordering = True
                elif isinstance(decorator, ast.Attribute) and decorator.attr == "total_ordering":
                    is_total_ordering = True

            has_all_rich = len(comparison_methods_found) == len(COMPARISON_METHODS)

            comparison_data = {
                "line": node.lineno,
                "class_name": node.name,
                "methods": ", ".join(sorted(comparison_methods_found)),
                "is_total_ordering": is_total_ordering,
                "has_all_rich": has_all_rich,
                "implemented_methods": comparison_methods_found,
            }
            comparison_protocols.append(comparison_data)

    return comparison_protocols


def extract_arithmetic_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract arithmetic protocol implementations."""
    arithmetic_protocols = []

    if not isinstance(context.tree, ast.AST):
        return arithmetic_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        arithmetic_methods_found = [m for m in ARITHMETIC_METHODS if m in methods]

        if arithmetic_methods_found:
            has_reflected = any(m.startswith("__r") for m in arithmetic_methods_found)

            has_inplace = any(m.startswith("__i") for m in arithmetic_methods_found)

            arithmetic_data = {
                "line": node.lineno,
                "class_name": node.name,
                "methods": ", ".join(sorted(arithmetic_methods_found)),
                "has_reflected": has_reflected,
                "has_inplace": has_inplace,
                "implemented_methods": arithmetic_methods_found,
            }
            arithmetic_protocols.append(arithmetic_data)

    return arithmetic_protocols


def extract_pickle_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract pickle protocol implementations."""
    pickle_protocols = []

    if not isinstance(context.tree, ast.AST):
        return pickle_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        has_getstate = "__getstate__" in methods
        has_setstate = "__setstate__" in methods
        has_reduce = "__reduce__" in methods
        has_reduce_ex = "__reduce_ex__" in methods

        if any([has_getstate, has_setstate, has_reduce, has_reduce_ex]):
            implemented_methods = [m for m in PICKLE_METHODS if m in methods]

            pickle_data = {
                "line": node.lineno,
                "class_name": node.name,
                "has_getstate": has_getstate,
                "has_setstate": has_setstate,
                "has_reduce": has_reduce,
                "has_reduce_ex": has_reduce_ex,
                "implemented_methods": implemented_methods,
            }
            pickle_protocols.append(pickle_data)

    return pickle_protocols


def extract_weakref_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract weakref module usage."""
    weakref_usage = []

    if not isinstance(context.tree, ast.AST):
        return weakref_usage

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        usage_type = None

        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "weakref":
                attr_name = node.func.attr
                if attr_name in ("ref", "proxy", "WeakValueDictionary", "WeakKeyDictionary"):
                    usage_type = attr_name

        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ("ref", "proxy", "WeakValueDictionary", "WeakKeyDictionary"):
                usage_type = func_name

        if usage_type:
            weakref_data = {
                "line": node.lineno,
                "usage_type": usage_type,
                "in_function": _find_containing_function(node, function_ranges),
            }
            weakref_usage.append(weakref_data)

    return weakref_usage


def extract_contextvar_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract contextvars module usage."""
    contextvar_usage = []

    if not isinstance(context.tree, ast.AST):
        return contextvar_usage

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        operation = None

        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "contextvars":
                attr_name = node.func.attr
                if attr_name in ("ContextVar", "Token"):
                    operation = attr_name

        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ("ContextVar", "Token"):
                operation = func_name

        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in ("get", "set"):
                operation = attr_name

        if operation:
            contextvar_data = {
                "line": node.lineno,
                "operation": operation,
                "in_function": _find_containing_function(node, function_ranges),
            }
            contextvar_usage.append(contextvar_data)

    return contextvar_usage


def extract_module_attributes(context: FileContext) -> list[dict[str, Any]]:
    """Extract module-level attribute usage."""
    module_attributes = []

    if not isinstance(context.tree, ast.AST):
        return module_attributes

    function_ranges = context.function_ranges

    assignment_targets = set()
    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                assignment_targets.add((target.lineno, target.id))

    for node in context.find_nodes(ast.Name):
        if node.id in ("__name__", "__file__", "__doc__", "__all__"):
            usage_type = "read"
            if (node.lineno, node.id) in assignment_targets or isinstance(node.ctx, ast.Store):
                usage_type = "write"

            module_attr_data = {
                "line": node.lineno,
                "attribute": node.id,
                "usage_type": usage_type,
                "in_function": _find_containing_function(node, function_ranges),
            }
            module_attributes.append(module_attr_data)

    return module_attributes


def extract_class_decorators(context: FileContext) -> list[dict[str, Any]]:
    """Extract class decorators (separate from method decorators)."""
    class_decorators = []

    if not isinstance(context.tree, ast.AST):
        return class_decorators

    for node in context.find_nodes(ast.ClassDef):
        for decorator in node.decorator_list:
            decorator_name = None
            has_arguments = False

            if isinstance(decorator, ast.Name):
                decorator_name = decorator.id

            elif isinstance(decorator, ast.Call):
                has_arguments = True
                if isinstance(decorator.func, ast.Name):
                    decorator_name = decorator.func.id
                elif isinstance(decorator.func, ast.Attribute):
                    decorator_name = decorator.func.attr

            elif isinstance(decorator, ast.Attribute):
                decorator_name = decorator.attr

            if decorator_name:
                decorator_type = "custom"
                if decorator_name == "dataclass":
                    decorator_type = "dataclass"
                elif decorator_name == "total_ordering":
                    decorator_type = "total_ordering"

                class_decorator_data = {
                    "line": decorator.lineno,
                    "class_name": node.name,
                    "decorator": decorator_name,
                    "decorator_type": decorator_type,
                    "has_arguments": has_arguments,
                }
                class_decorators.append(class_decorator_data)

    return class_decorators
