"""Behavioral pattern extractors - Recursion, generators, properties, dynamic attributes."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext
from theauditor.utils.logging import logger

from ..base import get_node_name

DYNAMIC_METHODS = frozenset({"__getattr__", "__setattr__", "__getattribute__", "__delattr__"})


def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_recursion_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Detect recursion patterns including direct, mutual, and tail recursion."""
    recursion_patterns = []

    if not isinstance(context.tree, ast.AST):
        return recursion_patterns

    function_definitions = {}
    function_calls = {}

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        func_name = node.name
        is_async = isinstance(node, ast.AsyncFunctionDef)
        function_definitions[func_name] = (node, is_async)

    for func_name, (_func_node, _is_async) in function_definitions.items():
        calls_in_function = []

        for child in context.find_nodes(ast.Call):
            called_func = get_node_name(child.func)
            if called_func:
                if "." in called_func:
                    called_func = called_func.split(".")[-1]
                calls_in_function.append((child.lineno, called_func))

        function_calls[func_name] = calls_in_function

    for func_name, (_func_node, _is_async) in function_definitions.items():
        calls_in_func = function_calls.get(func_name, [])

        direct_recursive_calls = [
            (line, called) for line, called in calls_in_func if called == func_name
        ]

        for call_line, _called_func in direct_recursive_calls:
            is_tail = False

            for return_node in context.find_nodes(ast.Return):
                if return_node.value and isinstance(return_node.value, ast.Call):
                    returned_func = get_node_name(return_node.value.func)
                    if returned_func and func_name in returned_func:
                        is_tail = True
                        break

            recursion_type = "tail" if is_tail else "direct"

            base_case_line = None
            for child in context.find_nodes(ast.If):
                for stmt in child.body:
                    if isinstance(stmt, ast.Return):
                        base_case_line = child.lineno
                        break
                if base_case_line:
                    break

            recursion_patterns.append(
                {
                    "line": call_line,
                    "function_name": func_name,
                    "recursion_type": recursion_type,
                    "calls_function": func_name,
                    "base_case_line": base_case_line,
                    "is_async": is_async,
                }
            )

    analyzed_pairs = set()

    for func_a in function_definitions:
        calls_from_a = function_calls.get(func_a, [])

        for line_a, func_b in calls_from_a:
            if func_b not in function_definitions:
                continue

            if func_a == func_b:
                continue

            calls_from_b = function_calls.get(func_b, [])
            calls_back_to_a = [(line, called) for line, called in calls_from_b if called == func_a]

            if calls_back_to_a:
                pair = tuple(sorted([func_a, func_b]))
                if pair not in analyzed_pairs:
                    analyzed_pairs.add(pair)

                    is_async_a = function_definitions[func_a][1]

                    recursion_patterns.append(
                        {
                            "line": line_a,
                            "function_name": func_a,
                            "recursion_type": "mutual",
                            "calls_function": func_b,
                            "base_case_line": None,
                            "is_async": is_async_a,
                        }
                    )

    seen = set()
    deduped = []
    for rp in recursion_patterns:
        key = (rp["line"], rp["function_name"], rp["calls_function"])
        if key not in seen:
            seen.add(key)
            deduped.append(rp)

    if len(recursion_patterns) != len(deduped):
        logger.debug(
            f"Recursion patterns deduplication: {len(recursion_patterns)} -> {len(deduped)} ({len(recursion_patterns) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_generator_yields(context: FileContext) -> list[dict[str, Any]]:
    """Extract generator yield patterns (ENHANCED from core_extractors.py)."""
    yields = []

    if not isinstance(context.tree, ast.AST):
        return yields

    function_ranges = []
    loop_ranges = []

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges.append((node.name, node.lineno, node.end_lineno or node.lineno))

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    def is_in_loop(line_no):
        """Check if line is inside a loop."""
        return any(start <= line_no <= end for start, end in loop_ranges)

    for node in context.find_nodes(ast.Yield):
        generator_function = find_containing_function(node.lineno)
        if generator_function == "global":
            continue

        yield_expr = get_node_name(node.value) if node.value else None
        in_loop = is_in_loop(node.lineno)

        yields.append(
            {
                "line": node.lineno,
                "generator_function": generator_function,
                "yield_type": "yield",
                "yield_expr": yield_expr,
                "condition": None,
                "in_loop": in_loop,
            }
        )

    seen = set()
    deduped = []
    for y in yields:
        key = (y["line"], y["generator_function"], y["yield_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(y)

    if len(yields) != len(deduped):
        logger.debug(
            f"Generator yields deduplication: {len(yields)} -> {len(deduped)} ({len(yields) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_property_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract property patterns including computed properties and validated setters."""
    properties = []

    if not isinstance(context.tree, ast.AST):
        return properties

    class_ranges = {}

    for node in context.find_nodes(ast.ClassDef):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            class_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    def find_containing_class(line_no):
        """Find the class containing this line."""
        for cname, (start, end) in class_ranges.items():
            if start <= line_no <= end:
                return cname
        return None

    for node in context.find_nodes(ast.FunctionDef):
        is_property_getter = False
        is_property_setter = False
        is_property_deleter = False

        for decorator in node.decorator_list:
            dec_name = get_node_name(decorator)
            if dec_name:
                if dec_name == "property":
                    is_property_getter = True
                elif ".setter" in dec_name:
                    is_property_setter = True
                elif ".deleter" in dec_name:
                    is_property_deleter = True

        if not (is_property_getter or is_property_setter or is_property_deleter):
            continue

        property_name = node.name
        in_class = find_containing_class(node.lineno)

        if not in_class:
            continue

        has_computation = False
        if is_property_getter:
            for child in context.find_nodes(ast.Return):
                if child.value:
                    if isinstance(child.value, ast.Attribute):
                        if (
                            isinstance(child.value.value, ast.Name)
                            and child.value.value.id == "self"
                        ):
                            if child.value.attr == f"_{property_name}":
                                has_computation = False
                            else:
                                has_computation = True

                    elif isinstance(child.value, (ast.BinOp, ast.Call, ast.Compare, ast.IfExp)):
                        has_computation = True

        has_validation = False
        if is_property_setter:
            for child in context.find_nodes(ast.If):
                for stmt in child.body:
                    if isinstance(stmt, ast.Raise):
                        has_validation = True
                        break
                if has_validation:
                    break

        if is_property_getter:
            access_type = "getter"
        elif is_property_setter:
            access_type = "setter"
        else:
            access_type = "deleter"

        properties.append(
            {
                "line": node.lineno,
                "property_name": property_name,
                "access_type": access_type,
                "in_class": in_class,
                "has_computation": has_computation,
                "has_validation": has_validation,
            }
        )

    seen = set()
    deduped = []
    for prop in properties:
        key = (prop["line"], prop["property_name"], prop["access_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(prop)

    if len(properties) != len(deduped):
        logger.debug(
            f"Property patterns deduplication: {len(properties)} -> {len(deduped)} ({len(properties) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_dynamic_attributes(context: FileContext) -> list[dict[str, Any]]:
    """Extract dynamic attribute access patterns (__getattr__, __setattr__, __getattribute__)."""
    dynamic_attrs = []

    if not isinstance(context.tree, ast.AST):
        return dynamic_attrs

    class_ranges = {}

    for node in context.find_nodes(ast.ClassDef):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            class_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    def find_containing_class(line_no):
        """Find the class containing this line."""
        for cname, (start, end) in class_ranges.items():
            if start <= line_no <= end:
                return cname
        return None

    for node in context.find_nodes(ast.FunctionDef):
        if node.name not in DYNAMIC_METHODS:
            continue

        in_class = find_containing_class(node.lineno)
        if not in_class:
            continue

        has_delegation = False
        for child in context.find_nodes(ast.Attribute):
            if (
                isinstance(child.value, ast.Name)
                and child.value.id == "self"
                and child.attr.startswith("_")
            ):
                has_delegation = True
                break

        has_validation = False
        if node.name == "__setattr__":
            for child in context.find_nodes(ast.If):
                for stmt in child.body:
                    if isinstance(stmt, ast.Raise):
                        has_validation = True
                        break
                if has_validation:
                    break

        dynamic_attrs.append(
            {
                "line": node.lineno,
                "method_name": node.name,
                "in_class": in_class,
                "has_delegation": has_delegation,
                "has_validation": has_validation,
            }
        )

    seen = set()
    deduped = []
    for da in dynamic_attrs:
        key = (da["line"], da["method_name"], da["in_class"])
        if key not in seen:
            seen.add(key)
            deduped.append(da)

    if len(dynamic_attrs) != len(deduped):
        logger.debug(
            f"Dynamic attributes deduplication: {len(dynamic_attrs)} -> {len(deduped)} ({len(dynamic_attrs) - len(deduped)} duplicates removed)"
        )

    return deduped
