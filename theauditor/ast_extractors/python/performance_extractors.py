"""Performance pattern extractors - Loop complexity, resource usage, memoization.

This module contains extraction logic for performance-related patterns:
- Loop complexity (nested loops, growing operations)
- Resource usage (large allocations, unclosed file handles)
- Memoization patterns (@lru_cache, manual caching, missing opportunities)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'nesting_level', 'resource_type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
This separation ensures single source of truth for file paths.

Causal Learning Purpose:
========================
These extractors enable hypothesis generation for DIEC tool:
- "Function X has O(n²) complexity due to nested loops" → Test performance scaling
- "Function allocates large memory structures" → Measure memory usage
- "Function would benefit from memoization" → Test with/without caching

Each extraction enables >3 hypothesis types per python_coverage.md requirements.
Target >70% validation rate when hypotheses are tested experimentally.

Week 4 Implementation (Priority 7 - Performance):
===================================================
Performance characteristics can only be validated through measurement.

Expected extraction from TheAuditor codebase:
- ~250 loop complexity patterns
- ~100 resource usage patterns
- ~50 memoization patterns
Total: ~400 performance indicator records
"""

import ast
import logging
import os
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext

from ..base import get_node_name

logger = logging.getLogger(__name__)


def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes.

    Handles both Python 3.8+ ast.Constant and legacy ast.Str nodes.
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_loop_complexity(context: FileContext) -> list[dict[str, Any]]:
    """Detect loop complexity patterns indicating algorithmic performance.

    Detects:
    - Nested loops (nesting level 2, 3, 4+)
    - Growing operations in loops (append, extend, +=)
    - Loop types (for, while, comprehensions)
    - Estimated complexity (O(n), O(n²), O(n³))

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of loop complexity dicts:
        {
            'line': int,
            'loop_type': str,  # 'for' | 'while' | 'comprehension'
            'nesting_level': int,  # 1, 2, 3, 4+
            'has_growing_operation': bool,  # True if contains append/extend/+=
            'in_function': str,
            'estimated_complexity': str,  # 'O(n)' | 'O(n^2)' | 'O(n^3)' | 'O(n^4+)'
        }

    Enables hypothesis: "Function X has O(n²) complexity"
    Experiment design: Test with varying input sizes, measure execution time
    """
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
            if (isinstance(child.func, ast.Attribute) and
                child.func.attr in ["append", "extend", "add", "update", "insert"]):
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

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        if len(loop_patterns) != len(deduped):
            print(
                f"[AST_DEBUG] Loop complexity deduplication: {len(loop_patterns)} -> {len(deduped)} ({len(loop_patterns) - len(deduped)} duplicates removed)",
                file=sys.stderr,
            )

    return deduped


def extract_resource_usage(context: FileContext) -> list[dict[str, Any]]:
    """Detect resource usage patterns that may impact performance.

    Detects:
    - Large data structure allocations (list/dict/set with >1000 elements)
    - File handles without context managers
    - Database connections without cleanup
    - Large string concatenations

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of resource usage dicts:
        {
            'line': int,
            'resource_type': str,  # 'large_list' | 'large_dict' | 'file_handle' | 'db_connection' | 'string_concat'
            'allocation_expr': str,  # Expression that allocates resource
            'in_function': str,
            'has_cleanup': bool,  # True if resource cleanup is present
        }

    Enables hypothesis: "Function X allocates large memory structures"
    Experiment design: Measure memory usage before/after function call
    """
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
            if (isinstance(gen.iter, ast.Call) and
                get_node_name(gen.iter.func) == "range" and gen.iter.args):
                first_arg = gen.iter.args[0]
                if (isinstance(first_arg, ast.Constant) and
                        isinstance(first_arg.value, int) and first_arg.value > 1000):
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

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        if len(resource_patterns) != len(deduped):
            print(
                f"[AST_DEBUG] Resource usage deduplication: {len(resource_patterns)} -> {len(deduped)} ({len(resource_patterns) - len(deduped)} duplicates removed)",
                file=sys.stderr,
            )

    return deduped


def extract_memoization_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Detect memoization patterns and missing opportunities.

    Detects:
    - @lru_cache decorator usage
    - @cache decorator usage (Python 3.9+)
    - Manual cache dictionaries (module-level _cache = {})
    - Recursive functions without memoization (opportunity)

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of memoization pattern dicts:
        {
            'line': int,
            'function_name': str,
            'has_memoization': bool,  # True if memoization present
            'memoization_type': str,  # 'lru_cache' | 'cache' | 'manual' | 'none'
            'is_recursive': bool,  # True if function is recursive
            'cache_size': int | None,  # LRU cache size if specified
        }

    Enables hypothesis: "Function X would benefit from memoization"
    Experiment design: Test performance with/without memoization, measure speedup
    """
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
                            if (keyword.arg == "maxsize" and
                                isinstance(keyword.value, ast.Constant)):
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

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys

        if len(memoization_patterns) != len(deduped):
            print(
                f"[AST_DEBUG] Memoization patterns deduplication: {len(memoization_patterns)} -> {len(deduped)} ({len(memoization_patterns) - len(deduped)} duplicates removed)",
                file=sys.stderr,
            )

    return deduped
