"""Performance pattern extractors - Loop complexity, resource usage, memoization."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext
from theauditor.utils.logging import logger

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


def extract_loop_complexity(context: FileContext) -> list[dict[str, Any]]:
    """Detect loop complexity patterns indicating algorithmic performance."""
    loop_patterns = []

    if not isinstance(context.tree, ast.AST):
        return loop_patterns

    function_ranges = []

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges.append((node.name, node.lineno, node.end_lineno or node.lineno))

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    def calculate_nesting_level(node, current_level=1):
        """Recursively calculate nesting level of loops."""
        max_level = current_level

        for child in ast.walk(node):
            if child == node:
                continue

            if isinstance(child, (ast.For, ast.While, ast.AsyncFor)):
                nested_level = calculate_nesting_level(child, current_level + 1)
                max_level = max(max_level, nested_level)

        return max_level

    def has_growing_operation(node):
        """Check if loop body contains growing operations."""
        for child in context.find_nodes(ast.Call):
            if isinstance(child.func, ast.Attribute) and child.func.attr in [
                "append",
                "extend",
                "add",
                "update",
                "insert",
            ]:
                return True

        return False

    for node in context.walk_tree():
        loop_type = None
        nesting_level = 1

        if isinstance(node, (ast.For, ast.AsyncFor)):
            loop_type = "for"
            nesting_level = calculate_nesting_level(node)

        elif isinstance(node, ast.While):
            loop_type = "while"
            nesting_level = calculate_nesting_level(node)

        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            loop_type = "comprehension"

            nesting_level = len(node.generators) if hasattr(node, "generators") else 1

        if loop_type:
            in_function = find_containing_function(node.lineno)
            has_growing = has_growing_operation(node)

            if nesting_level == 1:
                estimated_complexity = "O(n)"
            elif nesting_level == 2:
                estimated_complexity = "O(n^2)"
            elif nesting_level == 3:
                estimated_complexity = "O(n^3)"
            else:
                estimated_complexity = f"O(n^{nesting_level})"

            loop_patterns.append(
                {
                    "line": node.lineno,
                    "loop_type": loop_type,
                    "nesting_level": nesting_level,
                    "has_growing_operation": has_growing,
                    "in_function": in_function,
                    "estimated_complexity": estimated_complexity,
                }
            )

    seen = set()
    deduped = []
    for lp in loop_patterns:
        key = (lp["line"], lp["loop_type"], lp["in_function"])
        if key not in seen:
            seen.add(key)
            deduped.append(lp)

    if len(loop_patterns) != len(deduped):
        logger.debug(
            f"Loop complexity deduplication: {len(loop_patterns)} -> {len(deduped)} ({len(loop_patterns) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_resource_usage(context: FileContext) -> list[dict[str, Any]]:
    """Detect resource usage patterns that may impact performance."""
    resource_patterns = []

    if not isinstance(context.tree, ast.AST):
        return resource_patterns

    function_ranges = []

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges.append((node.name, node.lineno, node.end_lineno or node.lineno))

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    for node in context.find_nodes(ast.ListComp):
        for gen in node.generators:
            if (
                isinstance(gen.iter, ast.Call)
                and get_node_name(gen.iter.func) == "range"
                and gen.iter.args
            ):
                first_arg = gen.iter.args[0]
                if (
                    isinstance(first_arg, ast.Constant)
                    and isinstance(first_arg.value, int)
                    and first_arg.value > 1000
                ):
                    in_function = find_containing_function(node.lineno)
                    allocation_expr = get_node_name(node) or "[x for x in range(...)]"

                    resource_patterns.append(
                        {
                            "line": node.lineno,
                            "resource_type": "large_list",
                            "allocation_expr": allocation_expr,
                            "in_function": in_function,
                            "has_cleanup": False,
                        }
                    )

    seen = set()
    deduped = []
    for rp in resource_patterns:
        key = (rp["line"], rp["resource_type"], rp["in_function"])
        if key not in seen:
            seen.add(key)
            deduped.append(rp)

    if len(resource_patterns) != len(deduped):
        logger.debug(
            f"Resource usage deduplication: {len(resource_patterns)} -> {len(deduped)} ({len(resource_patterns) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_memoization_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Detect memoization patterns and missing opportunities."""
    memoization_patterns = []

    if not isinstance(context.tree, ast.AST):
        return memoization_patterns

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        func_name = node.name
        has_memoization = False
        memoization_type = "none"
        cache_size = None

        for decorator in node.decorator_list:
            dec_name = get_node_name(decorator)
            if dec_name:
                if "lru_cache" in dec_name:
                    has_memoization = True
                    memoization_type = "lru_cache"

                    if isinstance(decorator, ast.Call):
                        for keyword in decorator.keywords:
                            if keyword.arg == "maxsize" and isinstance(keyword.value, ast.Constant):
                                cache_size = keyword.value.value

                elif dec_name == "cache":
                    has_memoization = True
                    memoization_type = "cache"

        is_recursive = False
        for child in context.find_nodes(ast.Call):
            called_func = get_node_name(child.func)
            if called_func and func_name in called_func:
                is_recursive = True
                break

        if not has_memoization:
            for child in context.find_nodes(ast.If):
                test_str = get_node_name(child.test) or ""
                if "cache" in test_str.lower():
                    has_memoization = True
                    memoization_type = "manual"
                    break

        memoization_patterns.append(
            {
                "line": node.lineno,
                "function_name": func_name,
                "has_memoization": has_memoization,
                "memoization_type": memoization_type,
                "is_recursive": is_recursive,
                "cache_size": cache_size,
            }
        )

    seen = set()
    deduped = []
    for mp in memoization_patterns:
        key = (mp["line"], mp["function_name"])
        if key not in seen:
            seen.add(key)
            deduped.append(mp)

    if len(memoization_patterns) != len(deduped):
        logger.debug(
            f"Memoization patterns deduplication: {len(memoization_patterns)} -> {len(deduped)} ({len(memoization_patterns) - len(deduped)} duplicates removed)"
        )

    return deduped
