"""Python async pattern extractors - AsyncIO and concurrent patterns."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext

from ..base import get_node_name


def extract_async_functions(context: FileContext) -> list[dict[str, Any]]:
    """Extract async function definitions from Python AST."""
    async_functions = []

    if not context.tree:
        return async_functions

    for node in context.find_nodes(ast.AsyncFunctionDef):
        await_count = sum(1 for child in ast.walk(node) if isinstance(child, ast.Await))

        async_functions.append(
            {
                "line": node.lineno,
                "function_name": node.name,
                "await_count": await_count,
                "has_async_with": any(isinstance(child, ast.AsyncWith) for child in ast.walk(node)),
                "has_async_for": any(isinstance(child, ast.AsyncFor) for child in ast.walk(node)),
            }
        )

    return async_functions


def extract_await_expressions(context: FileContext) -> list[dict[str, Any]]:
    """Extract await expressions from Python AST."""
    awaits = []

    if not context.tree:
        return awaits

    function_ranges = {}
    for node in context.find_nodes(ast.AsyncFunctionDef):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    for node in context.find_nodes(ast.Await):
        containing_function = "global"
        for fname, (start, end) in function_ranges.items():
            if hasattr(node, "lineno") and start <= node.lineno <= end:
                containing_function = fname
                break

        awaited_expr = get_node_name(node.value)

        awaits.append(
            {
                "line": node.lineno,
                "containing_function": containing_function,
                "awaited_expr": awaited_expr,
            }
        )

    return awaits


def extract_async_generators(context: FileContext) -> list[dict[str, Any]]:
    """Extract async generators from Python AST."""
    async_generators = []

    if not context.tree:
        return async_generators

    for node in context.find_nodes(ast.AsyncFor):
        iter_expr = get_node_name(node.iter)
        target_var = get_node_name(node.target)

        async_generators.append(
            {
                "line": node.lineno,
                "generator_type": "async_for",
                "iter_expr": iter_expr,
                "target_var": target_var,
            }
        )

    for node in context.find_nodes(ast.AsyncFunctionDef):
        has_yield = any(isinstance(child, (ast.Yield, ast.YieldFrom)) for child in ast.walk(node))

        if has_yield:
            async_generators.append(
                {
                    "line": node.lineno,
                    "generator_type": "async_generator_function",
                    "function_name": node.name,
                }
            )

    return async_generators
