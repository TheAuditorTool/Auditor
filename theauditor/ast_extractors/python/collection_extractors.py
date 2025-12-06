"""Collection and method extractors - Dict/list/set/string methods + builtins."""

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


DICT_METHODS = {
    "keys",
    "values",
    "items",
    "get",
    "setdefault",
    "update",
    "pop",
    "popitem",
    "clear",
    "copy",
    "fromkeys",
}


LIST_METHODS = {
    "append",
    "extend",
    "insert",
    "remove",
    "pop",
    "clear",
    "index",
    "count",
    "sort",
    "reverse",
    "copy",
}


SET_METHODS = {
    "add",
    "remove",
    "discard",
    "pop",
    "clear",
    "union",
    "intersection",
    "difference",
    "symmetric_difference",
    "update",
    "intersection_update",
    "difference_update",
    "symmetric_difference_update",
    "issubset",
    "issuperset",
    "isdisjoint",
}


STRING_METHODS = {
    "split",
    "join",
    "strip",
    "lstrip",
    "rstrip",
    "replace",
    "find",
    "rfind",
    "index",
    "rindex",
    "startswith",
    "endswith",
    "upper",
    "lower",
    "capitalize",
    "title",
    "swapcase",
    "format",
    "format_map",
    "encode",
    "decode",
}


BUILTIN_FUNCTIONS = {
    "len",
    "sum",
    "max",
    "min",
    "abs",
    "round",
    "sorted",
    "reversed",
    "enumerate",
    "zip",
    "map",
    "filter",
    "reduce",
    "any",
    "all",
    "range",
    "list",
    "dict",
    "set",
    "tuple",
}


ITERTOOLS_FUNCTIONS = {
    "chain",
    "cycle",
    "repeat",
    "combinations",
    "combinations_with_replacement",
    "permutations",
    "product",
    "islice",
    "groupby",
    "accumulate",
    "compress",
    "dropwhile",
    "filterfalse",
    "starmap",
    "takewhile",
    "tee",
    "zip_longest",
}


FUNCTOOLS_FUNCTIONS = {
    "partial",
    "reduce",
    "wraps",
    "lru_cache",
    "cache",
    "cached_property",
    "singledispatch",
    "total_ordering",
}


COLLECTIONS_TYPES = {
    "defaultdict",
    "Counter",
    "OrderedDict",
    "deque",
    "ChainMap",
    "namedtuple",
    "UserDict",
    "UserList",
    "UserString",
}


def extract_dict_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract dictionary method calls."""
    dict_ops = []

    if not isinstance(context.tree, ast.AST):
        return dict_ops

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in DICT_METHODS:
                has_default = False
                if method_name == "get" and len(node.args) > 1:
                    has_default = True

                dict_data = {
                    "line": node.lineno,
                    "operation": method_name,
                    "has_default": has_default,
                    "in_function": _find_containing_function(node, function_ranges),
                }
                dict_ops.append(dict_data)

    return dict_ops


def extract_list_mutations(context: FileContext) -> list[dict[str, Any]]:
    """Extract list method calls (focusing on mutations)."""
    list_mutations = []

    if not isinstance(context.tree, ast.AST):
        return list_mutations

    function_ranges = context.function_ranges

    mutating_methods = {"append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse"}

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in LIST_METHODS:
                list_data = {
                    "line": node.lineno,
                    "method": method_name,
                    "mutates_in_place": method_name in mutating_methods,
                    "in_function": _find_containing_function(node, function_ranges),
                }
                list_mutations.append(list_data)

    return list_mutations


def extract_set_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract set operations (union, intersection, difference, etc.)."""
    set_ops = []

    if not isinstance(context.tree, ast.AST):
        return set_ops

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in SET_METHODS:
                set_data = {
                    "line": node.lineno,
                    "operation": method_name,
                    "in_function": _find_containing_function(node, function_ranges),
                }
                set_ops.append(set_data)

    return set_ops


def extract_string_methods(context: FileContext) -> list[dict[str, Any]]:
    """Extract string method calls."""
    string_methods = []

    if not isinstance(context.tree, ast.AST):
        return string_methods

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in STRING_METHODS:
                string_data = {
                    "line": node.lineno,
                    "method": method_name,
                    "in_function": _find_containing_function(node, function_ranges),
                }
                string_methods.append(string_data)

    return string_methods


def extract_builtin_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract builtin function usage."""
    builtins = []

    if not isinstance(context.tree, ast.AST):
        return builtins

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in BUILTIN_FUNCTIONS:
                has_key = False
                if func_name in {"sorted", "max", "min"}:
                    for keyword in node.keywords:
                        if keyword.arg == "key":
                            has_key = True
                            break

                builtin_data = {
                    "line": node.lineno,
                    "builtin": func_name,
                    "has_key": has_key,
                    "in_function": _find_containing_function(node, function_ranges),
                }
                builtins.append(builtin_data)

    return builtins


def extract_itertools_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract itertools function usage."""
    itertools_usage = []

    if not isinstance(context.tree, ast.AST):
        return itertools_usage

    function_ranges = context.function_ranges

    infinite_functions = {"cycle", "count"}

    for node in context.find_nodes(ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "itertools"
        ):
            func_name = node.func.attr
            if func_name in ITERTOOLS_FUNCTIONS:
                is_infinite = func_name in infinite_functions

                if func_name == "repeat" and len(node.args) > 1:
                    is_infinite = False

                itertools_data = {
                    "line": node.lineno,
                    "function": func_name,
                    "is_infinite": is_infinite,
                    "in_function": _find_containing_function(node, function_ranges),
                }
                itertools_usage.append(itertools_data)

    return itertools_usage


def extract_functools_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract functools function usage."""
    functools_usage = []

    if not isinstance(context.tree, ast.AST):
        return functools_usage

    function_ranges = context.function_ranges

    decorator_usage = set()
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorator_usage.add((decorator.lineno, decorator.id))
            elif (
                isinstance(decorator, ast.Attribute)
                and isinstance(decorator.value, ast.Name)
                and decorator.value.id == "functools"
            ):
                decorator_usage.add((decorator.lineno, decorator.attr))

    for node in context.find_nodes(ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "functools"
        ):
            func_name = node.func.attr
            if func_name in FUNCTOOLS_FUNCTIONS:
                is_decorator = (node.lineno, func_name) in decorator_usage

                functools_data = {
                    "line": node.lineno,
                    "function": func_name,
                    "is_decorator": is_decorator,
                    "in_function": _find_containing_function(node, function_ranges),
                }
                functools_usage.append(functools_data)

    return functools_usage


def extract_collections_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract collections module usage."""
    collections_usage = []

    if not isinstance(context.tree, ast.AST):
        return collections_usage

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        collection_type = None

        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "collections"
            and node.func.attr in COLLECTIONS_TYPES
        ):
            collection_type = node.func.attr

        elif isinstance(node.func, ast.Name) and node.func.id in COLLECTIONS_TYPES:
            collection_type = node.func.id

        if collection_type:
            default_factory = None
            if collection_type == "defaultdict" and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Name):
                    default_factory = first_arg.id

            collections_data = {
                "line": node.lineno,
                "collection_type": collection_type,
                "default_factory": default_factory or "unknown",
                "in_function": _find_containing_function(node, function_ranges),
            }
            collections_usage.append(collections_data)

    return collections_usage
