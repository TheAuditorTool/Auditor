"""Exception flow extractors - Raises, catches, finally blocks, context managers."""

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


def _detect_handling_strategy(handler_body: list[ast.stmt]) -> str:
    """Detect exception handling strategy from handler body."""
    if not handler_body:
        return "pass"

    if len(handler_body) == 1:
        stmt = handler_body[0]

        if isinstance(stmt, ast.Return):
            if stmt.value is None or (
                isinstance(stmt.value, ast.Constant) and stmt.value.value is None
            ):
                return "return_none"
            return "return_value"

        if isinstance(stmt, ast.Raise):
            if stmt.exc is None:
                return "re_raise"
            return "convert_to_other"

        if isinstance(stmt, ast.Pass):
            return "pass"

    has_log = False
    has_pass = False
    has_raise = False

    for stmt in handler_body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            if isinstance(stmt.value.func, ast.Attribute):
                if stmt.value.func.attr in ["error", "warning", "exception", "debug", "info"]:
                    has_log = True
            elif isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "print":
                has_log = True
        elif isinstance(stmt, ast.Pass):
            has_pass = True
        elif isinstance(stmt, ast.Raise):
            has_raise = True

    if has_log and has_pass:
        return "log_and_continue"
    if has_log and has_raise:
        return "log_and_re_raise"

    return "other"


def extract_exception_raises(context: FileContext) -> list[dict[str, Any]]:
    """Extract exception raise statements with exception type and context."""
    raises = []

    if not isinstance(context.tree, ast.AST):
        return raises

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

    for node in context.find_nodes(ast.Raise):
        in_function = find_containing_function(node.lineno)

        if node.exc is None:
            raises.append(
                {
                    "line": node.lineno,
                    "exception_type": None,
                    "message": None,
                    "from_exception": None,
                    "in_function": in_function,
                    "condition": None,
                    "is_re_raise": True,
                }
            )
        else:
            exception_type = get_node_name(node.exc)

            if isinstance(node.exc, ast.Call):
                exception_type = get_node_name(node.exc.func)

                message = None
                if node.exc.args:
                    message = _get_str_constant(node.exc.args[0])
            else:
                message = None

            from_exception = get_node_name(node.cause) if node.cause else None

            raises.append(
                {
                    "line": node.lineno,
                    "exception_type": exception_type,
                    "message": message,
                    "from_exception": from_exception,
                    "in_function": in_function,
                    "condition": None,
                    "is_re_raise": False,
                }
            )

    seen = set()
    deduped = []
    for r in raises:
        key = (r["line"], r["exception_type"], r["in_function"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    if len(raises) != len(deduped):
        logger.debug(
            f"Exception raises deduplication: {len(raises)} -> {len(deduped)} ({len(raises) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_exception_catches(context: FileContext) -> list[dict[str, Any]]:
    """Extract exception handlers (except clauses) and their handling strategies."""
    handlers = []

    if not isinstance(context.tree, ast.AST):
        return handlers

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

    for node in context.find_nodes(ast.Try):
        for handler in node.handlers:
            in_function = find_containing_function(handler.lineno)

            exception_types = []
            if handler.type is None:
                exception_types = ["Exception"]
            elif isinstance(handler.type, ast.Tuple):
                for exc in handler.type.elts:
                    exc_type = get_node_name(exc)
                    if exc_type:
                        exception_types.append(exc_type)
            else:
                exc_type = get_node_name(handler.type)
                if exc_type:
                    exception_types.append(exc_type)

            variable_name = handler.name if handler.name else None

            handling_strategy = _detect_handling_strategy(handler.body)

            handlers.append(
                {
                    "line": handler.lineno,
                    "exception_types": ",".join(exception_types)
                    if exception_types
                    else "Exception",
                    "variable_name": variable_name,
                    "handling_strategy": handling_strategy,
                    "in_function": in_function,
                }
            )

    seen = set()
    deduped = []
    for h in handlers:
        key = (h["line"], h["exception_types"], h["in_function"])
        if key not in seen:
            seen.add(key)
            deduped.append(h)

    if len(handlers) != len(deduped):
        logger.debug(
            f"Exception catches deduplication: {len(handlers)} -> {len(deduped)} ({len(handlers) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_finally_blocks(context: FileContext) -> list[dict[str, Any]]:
    """Extract finally blocks that always execute."""
    finally_blocks = []

    if not isinstance(context.tree, ast.AST):
        return finally_blocks

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

    for node in context.find_nodes(ast.Try):
        if node.finalbody:
            cleanup_calls = []

            for stmt in node.finalbody:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    func_name = get_node_name(stmt.value.func)
                    if func_name:
                        cleanup_calls.append(func_name)

                elif isinstance(stmt, ast.Assign):
                    if isinstance(stmt.value, ast.Call):
                        func_name = get_node_name(stmt.value.func)
                        if func_name:
                            cleanup_calls.append(func_name)

            finally_line = node.finalbody[0].lineno if node.finalbody else node.lineno
            in_function = find_containing_function(finally_line)

            finally_blocks.append(
                {
                    "line": finally_line,
                    "cleanup_calls": ",".join(cleanup_calls) if cleanup_calls else None,
                    "has_cleanup": bool(cleanup_calls),
                    "in_function": in_function,
                }
            )

    seen = set()
    deduped = []
    for fb in finally_blocks:
        key = (fb["line"], fb["in_function"])
        if key not in seen:
            seen.add(key)
            deduped.append(fb)

    if len(finally_blocks) != len(deduped):
        logger.debug(
            f"Finally blocks deduplication: {len(finally_blocks)} -> {len(deduped)} ({len(finally_blocks) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_context_managers(context: FileContext) -> list[dict[str, Any]]:
    """Extract context managers (with statements) that ensure cleanup."""
    context_managers = []

    if not isinstance(context.tree, ast.AST):
        return context_managers

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

    def classify_resource_type(context_expr: str) -> str | None:
        """Classify resource type from context expression."""
        if not context_expr:
            return None

        expr_lower = context_expr.lower()

        if "open(" in expr_lower or "path." in expr_lower or "file" in expr_lower:
            return "file"

        if "lock" in expr_lower or "rlock" in expr_lower or "semaphore" in expr_lower:
            return "lock"

        if (
            "session" in expr_lower
            or "connection" in expr_lower
            or "transaction" in expr_lower
            and "db" in expr_lower
            or "sql" in expr_lower
            or "engine" in expr_lower
        ):
            return "database"

        if "client" in expr_lower or "request" in expr_lower or "http" in expr_lower:
            return "network"

        return None

    for node in context.find_nodes(ast.With):
        for item in node.items:
            context_expr = get_node_name(item.context_expr)
            as_name = get_node_name(item.optional_vars) if item.optional_vars else None
            in_function = find_containing_function(node.lineno)
            resource_type = classify_resource_type(context_expr)

            context_managers.append(
                {
                    "line": node.lineno,
                    "context_expr": context_expr,
                    "variable_name": as_name,
                    "in_function": in_function,
                    "is_async": False,
                    "resource_type": resource_type,
                }
            )

    seen = set()
    deduped = []
    for cm in context_managers:
        key = (cm["line"], cm["context_expr"], cm["in_function"])
        if key not in seen:
            seen.add(key)
            deduped.append(cm)

    if len(context_managers) != len(deduped):
        logger.debug(
            f"Context managers deduplication: {len(context_managers)} -> {len(deduped)} ({len(context_managers) - len(deduped)} duplicates removed)"
        )

    return deduped
