"""Python async pattern extractors - AsyncIO and concurrent patterns.

This module contains extraction logic for Python async/await patterns:
- async def functions
- await expressions
- async with statements
- async for loops
- async generators

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
"""
from __future__ import annotations
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
from typing import Any, Dict, List

from ..base import get_node_name

logger = logging.getLogger(__name__)


def extract_async_functions(context: FileContext) -> list[dict[str, Any]]:
    """Extract async function definitions from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of async function records
    """
    async_functions = []
    context.tree = tree.get("tree")

    if not context.tree:
        return async_functions

    for node in context.find_nodes(ast.AsyncFunctionDef):
        # Count await expressions in function body
        await_count = sum(
            1 for child in ast.walk(node)
            if isinstance(child, ast.Await)
        )

        async_functions.append({
            "line": node.lineno,
            "function_name": node.name,
            "await_count": await_count,
            "has_async_with": any(
                isinstance(child, ast.AsyncWith)
                for child in ast.walk(node)
            ),
            "has_async_for": any(
                isinstance(child, ast.AsyncFor)
                for child in ast.walk(node)
            ),
        })

    return async_functions


def extract_await_expressions(context: FileContext) -> list[dict[str, Any]]:
    """Extract await expressions from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of await expression records
    """
    awaits = []
    context.tree = tree.get("tree")

    if not context.tree:
        return awaits

    # Build function ranges to find containing function
    function_ranges = {}
    for node in context.find_nodes(ast.AsyncFunctionDef):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    for node in context.find_nodes(ast.Await):
        # Find containing function
        containing_function = "global"
        for fname, (start, end) in function_ranges.items():
            if hasattr(node, "lineno") and start <= node.lineno <= end:
                containing_function = fname
                break

        awaited_expr = get_node_name(node.value)

        awaits.append({
            "line": node.lineno,
            "containing_function": containing_function,
            "awaited_expr": awaited_expr,
        })

    return awaits


def extract_async_generators(context: FileContext) -> list[dict[str, Any]]:
    """Extract async generators from Python AST.

    Detects:
    - async for loops
    - Functions with yield inside async def

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of async generator records
    """
    async_generators = []
    context.tree = tree.get("tree")

    if not context.tree:
        return async_generators

    # Extract async for loops
    for node in context.find_nodes(ast.AsyncFor):
        iter_expr = get_node_name(node.iter)
        target_var = get_node_name(node.target)

        async_generators.append({
            "line": node.lineno,
            "generator_type": "async_for",
            "iter_expr": iter_expr,
            "target_var": target_var,
        })

    # Extract async generator functions (async def with yield)
    for node in context.find_nodes(ast.AsyncFunctionDef):
        has_yield = any(
            isinstance(child, (ast.Yield, ast.YieldFrom))
            for child in ast.walk(node)
        )

        if has_yield:
            async_generators.append({
                "line": node.lineno,
                "generator_type": "async_generator_function",
                "function_name": node.name,
            })

    return async_generators
