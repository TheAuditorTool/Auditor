"""Standard library pattern extractors - Regex, JSON, datetime, pathlib, logging, etc."""

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


REGEX_FUNCTIONS = {"compile", "match", "search", "findall", "finditer", "sub", "subn", "split"}


JSON_FUNCTIONS = {"dumps", "dump", "loads", "load"}


DATETIME_TYPES = {"datetime", "date", "time", "timedelta", "timezone"}


PATH_METHODS = {
    "exists",
    "is_file",
    "is_dir",
    "mkdir",
    "rmdir",
    "unlink",
    "rename",
    "resolve",
    "glob",
    "iterdir",
}


LOGGING_METHODS = {"debug", "info", "warning", "error", "critical", "exception"}


THREADING_TYPES = {"Thread", "Lock", "RLock", "Semaphore", "Event", "Condition", "Queue"}


CONTEXTLIB_DECORATORS = {"contextmanager", "asynccontextmanager", "closing", "suppress"}


def extract_regex_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract regular expression usage (re module)."""
    regex_patterns = []

    if not isinstance(context.tree, ast.AST):
        return regex_patterns

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        operation = None

        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "re"
            and node.func.attr in REGEX_FUNCTIONS
        ):
            operation = node.func.attr

        if operation:
            has_flags = False
            for keyword in node.keywords:
                if keyword.arg == "flags":
                    has_flags = True

            regex_data = {
                "line": node.lineno,
                "operation": operation,
                "has_flags": has_flags,
                "in_function": _find_containing_function(node, function_ranges),
            }
            regex_patterns.append(regex_data)

    return regex_patterns


def extract_json_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract JSON serialization/deserialization operations."""
    json_operations = []

    if not isinstance(context.tree, ast.AST):
        return json_operations

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        operation = None

        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "json"
            and node.func.attr in JSON_FUNCTIONS
        ):
            operation = node.func.attr

        if operation:
            direction = "serialize" if operation in ("dumps", "dump") else "deserialize"

            json_data = {
                "line": node.lineno,
                "operation": operation,
                "direction": direction,
                "in_function": _find_containing_function(node, function_ranges),
            }
            json_operations.append(json_data)

    return json_operations


def extract_datetime_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract datetime module usage."""
    datetime_operations = []

    if not isinstance(context.tree, ast.AST):
        return datetime_operations

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        datetime_type = None

        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "datetime"
            and node.func.attr in DATETIME_TYPES
        ):
            datetime_type = node.func.attr

        elif isinstance(node.func, ast.Name) and node.func.id in DATETIME_TYPES:
            datetime_type = node.func.id

        if datetime_type:
            datetime_data = {
                "line": node.lineno,
                "datetime_type": datetime_type,
                "in_function": _find_containing_function(node, function_ranges),
            }
            datetime_operations.append(datetime_data)

    return datetime_operations


def extract_path_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract pathlib and os.path operations."""
    path_operations = []

    if not isinstance(context.tree, ast.AST):
        return path_operations

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        operation = None
        path_type = None

        if isinstance(node.func, ast.Name) and node.func.id == "Path":
            operation = "Path"
            path_type = "pathlib"

        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in PATH_METHODS:
                operation = node.func.attr
                path_type = "pathlib"

            if (
                isinstance(node.func.value, ast.Attribute)
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "os"
                and node.func.value.attr == "path"
            ):
                operation = node.func.attr
                path_type = "os.path"

        if operation:
            path_data = {
                "line": node.lineno,
                "operation": operation,
                "path_type": path_type or "unknown",
                "in_function": _find_containing_function(node, function_ranges),
            }
            path_operations.append(path_data)

    return path_operations


def extract_logging_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract logging usage patterns."""
    logging_patterns = []

    if not isinstance(context.tree, ast.AST):
        return logging_patterns

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in LOGGING_METHODS:
                logging_data = {
                    "line": node.lineno,
                    "log_level": method_name,
                    "in_function": _find_containing_function(node, function_ranges),
                }
                logging_patterns.append(logging_data)

    return logging_patterns


def extract_threading_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract threading and multiprocessing usage."""
    threading_patterns = []

    if not isinstance(context.tree, ast.AST):
        return threading_patterns

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        threading_type = None

        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ("threading", "multiprocessing")
            and (node.func.attr in THREADING_TYPES or node.func.attr == "Process")
        ):
            threading_type = node.func.attr

        elif isinstance(node.func, ast.Name) and (
            node.func.id in THREADING_TYPES or node.func.id == "Process"
        ):
            threading_type = node.func.id

        if threading_type:
            threading_data = {
                "line": node.lineno,
                "threading_type": threading_type,
                "in_function": _find_containing_function(node, function_ranges),
            }
            threading_patterns.append(threading_data)

    return threading_patterns


def extract_contextlib_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract contextlib usage (@contextmanager, closing(), suppress())."""
    contextlib_patterns = []

    if not isinstance(context.tree, ast.AST):
        return contextlib_patterns

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.FunctionDef):
        for decorator in node.decorator_list:
            pattern = None
            if isinstance(decorator, ast.Name):
                if decorator.id in CONTEXTLIB_DECORATORS:
                    pattern = decorator.id
            elif (
                isinstance(decorator, ast.Attribute)
                and isinstance(decorator.value, ast.Name)
                and decorator.value.id == "contextlib"
                and decorator.attr in CONTEXTLIB_DECORATORS
            ):
                pattern = decorator.attr

            if pattern:
                contextlib_data = {
                    "line": decorator.lineno,
                    "pattern": pattern,
                    "is_decorator": True,
                    "in_function": _find_containing_function(node, function_ranges),
                }
                contextlib_patterns.append(contextlib_data)

    for node in context.find_nodes(ast.Call):
        pattern = None

        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "contextlib"
            and node.func.attr in CONTEXTLIB_DECORATORS
        ):
            pattern = node.func.attr

        elif isinstance(node.func, ast.Name) and node.func.id in CONTEXTLIB_DECORATORS:
            pattern = node.func.id

        if pattern:
            contextlib_data = {
                "line": node.lineno,
                "pattern": pattern,
                "is_decorator": False,
                "in_function": _find_containing_function(node, function_ranges),
            }
            contextlib_patterns.append(contextlib_data)

    return contextlib_patterns


def extract_type_checking(context: FileContext) -> list[dict[str, Any]]:
    """Extract runtime type checking patterns."""
    type_checking = []

    if not isinstance(context.tree, ast.AST):
        return type_checking

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        check_type = None

        if isinstance(node.func, ast.Name) and node.func.id in ("isinstance", "issubclass", "type"):
            check_type = node.func.id

        if check_type:
            type_check_data = {
                "line": node.lineno,
                "check_type": check_type,
                "in_function": _find_containing_function(node, function_ranges),
            }
            type_checking.append(type_check_data)

    return type_checking
