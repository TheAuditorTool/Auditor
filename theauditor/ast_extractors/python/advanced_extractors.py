"""Python Coverage V2 - Advanced Patterns (8 extractors)."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext


def _get_enclosing_function(node: ast.AST, parent_map: dict) -> str:
    """Get the name of the enclosing function or 'global'."""
    current = node
    while current in parent_map:
        current = parent_map[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
    return "global"


def extract_namespace_packages(context: FileContext) -> list[dict[str, Any]]:
    """Extract namespace package patterns (pkgutil.extend_path usage)."""
    results = []
    if not context.tree:
        return results

    parent_map = context.parent_map

    for node in context.find_nodes(ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pkgutil"
            and node.func.attr == "extend_path"
        ):
            results.append(
                {
                    "line": node.lineno,
                    "pattern": "extend_path",
                    "in_function": _get_enclosing_function(node, parent_map),
                }
            )

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__path__":
                    results.append(
                        {
                            "line": node.lineno,
                            "pattern": "path_manipulation",
                            "in_function": _get_enclosing_function(node, parent_map),
                        }
                    )

    return results


def extract_cached_property(context: FileContext) -> list[dict[str, Any]]:
    """Extract @cached_property decorator usage."""
    results = []
    if not context.tree:
        return results

    for node in context.find_nodes(ast.ClassDef):
        class_name = node.name
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in item.decorator_list:
                    decorator_name = None
                    is_functools = False

                    if isinstance(dec, ast.Name):
                        decorator_name = dec.id
                    elif (
                        isinstance(dec, ast.Attribute)
                        and isinstance(dec.value, ast.Name)
                        and dec.value.id == "functools"
                        and dec.attr == "cached_property"
                    ):
                        decorator_name = "cached_property"
                        is_functools = True

                    if decorator_name and "cached_property" in decorator_name.lower():
                        results.append(
                            {
                                "line": item.lineno,
                                "method_name": item.name,
                                "in_class": class_name,
                                "is_functools": is_functools,
                            }
                        )

    return results


def extract_descriptor_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract descriptor protocol implementations (__get__, __set__, __delete__)."""
    results = []
    if not context.tree:
        return results

    for node in context.find_nodes(ast.ClassDef):
        has_get = False
        has_set = False
        has_delete = False

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name == "__get__":
                    has_get = True
                elif item.name == "__set__":
                    has_set = True
                elif item.name == "__delete__":
                    has_delete = True

        if has_get or has_set or has_delete:
            results.append(
                {
                    "line": node.lineno,
                    "class_name": node.name,
                    "has_get": has_get,
                    "has_set": has_set,
                    "has_delete": has_delete,
                    "is_data_descriptor": has_set or has_delete,
                }
            )

    return results


def extract_attribute_access_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract attribute access protocol (__getattr__, __setattr__, __delattr__, __getattribute__)."""
    results = []
    if not context.tree:
        return results

    for node in context.find_nodes(ast.ClassDef):
        has_getattr = False
        has_setattr = False
        has_delattr = False
        has_getattribute = False

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name == "__getattr__":
                    has_getattr = True
                elif item.name == "__setattr__":
                    has_setattr = True
                elif item.name == "__delattr__":
                    has_delattr = True
                elif item.name == "__getattribute__":
                    has_getattribute = True

        if has_getattr or has_setattr or has_delattr or has_getattribute:
            results.append(
                {
                    "line": node.lineno,
                    "class_name": node.name,
                    "has_getattr": has_getattr,
                    "has_setattr": has_setattr,
                    "has_delattr": has_delattr,
                    "has_getattribute": has_getattribute,
                }
            )

    return results


def extract_copy_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract copy protocol (__copy__, __deepcopy__)."""
    results = []
    if not context.tree:
        return results

    for node in context.find_nodes(ast.ClassDef):
        has_copy = False
        has_deepcopy = False

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if item.name == "__copy__":
                    has_copy = True
                elif item.name == "__deepcopy__":
                    has_deepcopy = True

        if has_copy or has_deepcopy:
            results.append(
                {
                    "line": node.lineno,
                    "class_name": node.name,
                    "has_copy": has_copy,
                    "has_deepcopy": has_deepcopy,
                }
            )

    return results


def extract_ellipsis_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract Ellipsis (...) usage patterns."""
    results = []
    if not context.tree:
        return results

    parent_map = context.parent_map

    for node in context.walk_tree():
        if isinstance(node, ast.Constant) and node.value is ...:
            ellipsis_context = "expression"

            parent = parent_map.get(node)
            if parent and isinstance(parent, (ast.AnnAssign, ast.arg)):
                ellipsis_context = "type_hint"

            elif parent and isinstance(parent, ast.Slice):
                ellipsis_context = "slice"

            elif isinstance(parent, ast.Expr):
                ellipsis_context = "pass_placeholder"

            results.append(
                {
                    "line": node.lineno,
                    "context": ellipsis_context,
                    "in_function": _get_enclosing_function(node, parent_map),
                }
            )

    return results


def extract_bytes_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract bytes/bytearray operations."""
    results = []
    if not context.tree:
        return results

    parent_map = context.parent_map

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id == "bytes":
                results.append(
                    {
                        "line": node.lineno,
                        "operation": "bytes",
                        "in_function": _get_enclosing_function(node, parent_map),
                    }
                )
            elif node.func.id == "bytearray":
                results.append(
                    {
                        "line": node.lineno,
                        "operation": "bytearray",
                        "in_function": _get_enclosing_function(node, parent_map),
                    }
                )

        elif isinstance(node.func, ast.Attribute):
            if node.func.attr == "encode":
                results.append(
                    {
                        "line": node.lineno,
                        "operation": "encode",
                        "in_function": _get_enclosing_function(node, parent_map),
                    }
                )
            elif node.func.attr == "decode":
                results.append(
                    {
                        "line": node.lineno,
                        "operation": "decode",
                        "in_function": _get_enclosing_function(node, parent_map),
                    }
                )

        if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
            results.append(
                {
                    "line": node.lineno,
                    "operation": "literal",
                    "in_function": _get_enclosing_function(node, parent_map),
                }
            )

    return results


def extract_exec_eval_compile(context: FileContext) -> list[dict[str, Any]]:
    """Extract exec/eval/compile dynamic execution patterns."""
    results = []
    if not context.tree:
        return results

    parent_map = context.parent_map

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Name):
            operation = None
            if node.func.id == "exec":
                operation = "exec"
            elif node.func.id == "eval":
                operation = "eval"
            elif node.func.id == "compile":
                operation = "compile"

            if operation:
                has_globals = len(node.args) >= 2
                has_locals = len(node.args) >= 3

                for kw in node.keywords:
                    if kw.arg == "globals":
                        has_globals = True
                    elif kw.arg == "locals":
                        has_locals = True

                results.append(
                    {
                        "line": node.lineno,
                        "operation": operation,
                        "has_globals": has_globals,
                        "has_locals": has_locals,
                        "in_function": _get_enclosing_function(node, parent_map),
                    }
                )

    return results
