"""Standard library pattern extractors - Regex, JSON, datetime, pathlib, logging, etc.

This module contains extraction logic for standard library usage patterns:
- Regular expressions (re module)
- JSON operations (json module)
- Datetime operations (datetime module)
- Path operations (pathlib, os.path)
- Logging patterns (logging module)
- Threading patterns (threading, multiprocessing)
- Context managers (contextlib)
- Type checking (typing, isinstance, issubclass)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with pattern-specific keys
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

Week 4 Implementation (Python Coverage V2):
============================================
Implements standard library patterns.

Expected extraction from TheAuditor codebase:
- ~80 regex patterns
- ~40 JSON operations
- ~30 datetime operations
- ~200 path operations
- ~150 logging patterns
- ~20 threading patterns
- ~30 context managers
- ~50 type checking patterns
Total: ~600 stdlib pattern records
"""
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
from typing import Any, Dict, List, Optional, Set

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def _build_function_ranges(tree: ast.AST) -> list:
    """Build list of function ranges for context tracking."""
    function_ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges.append((
                    node.name,
                    node.lineno,
                    node.end_lineno or node.lineno
                ))
    return function_ranges


def _find_containing_function(node: ast.AST, function_ranges: list) -> str:
    """Find the function containing this node."""
    if not hasattr(node, 'lineno'):
        return 'global'

    line_no = node.lineno
    for fname, start, end in function_ranges:
        if start <= line_no <= end:
            return fname
    return 'global'


# Regex functions
REGEX_FUNCTIONS = {'compile', 'match', 'search', 'findall', 'finditer', 'sub', 'subn', 'split'}

# JSON functions
JSON_FUNCTIONS = {'dumps', 'dump', 'loads', 'load'}

# Datetime functions
DATETIME_TYPES = {'datetime', 'date', 'time', 'timedelta', 'timezone'}

# Path operations
PATH_METHODS = {'exists', 'is_file', 'is_dir', 'mkdir', 'rmdir', 'unlink', 'rename', 'resolve', 'glob', 'iterdir'}

# Logging methods
LOGGING_METHODS = {'debug', 'info', 'warning', 'error', 'critical', 'exception'}

# Threading types
THREADING_TYPES = {'Thread', 'Lock', 'RLock', 'Semaphore', 'Event', 'Condition', 'Queue'}

# Context manager decorators
CONTEXTLIB_DECORATORS = {'contextmanager', 'asynccontextmanager', 'closing', 'suppress'}


# ============================================================================
# Regex Pattern Extractors
# ============================================================================

def extract_regex_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract regular expression usage (re module).

    Detects re.compile(), re.match(), re.search(), re.findall(), etc.

    Returns:
        List of regex pattern dicts:
        {
            'line': int,
            'operation': str,  # 'compile' | 'match' | 'search' | 'findall' | 'sub'
            'has_flags': bool,  # If regex flags used (re.IGNORECASE, etc.)
            'in_function': str,
        }
    """
    regex_patterns = []

    if not isinstance(context.tree, ast.AST):
        return regex_patterns

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        operation = None

        # Check for re.function() calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 're':
                    if node.func.attr in REGEX_FUNCTIONS:
                        operation = node.func.attr

        if operation:
            # Check for flags argument
            has_flags = False
            for keyword in node.keywords:
                if keyword.arg == 'flags':
                    has_flags = True

            regex_data = {
                'line': node.lineno,
                'operation': operation,
                'has_flags': has_flags,
                'in_function': _find_containing_function(node, function_ranges),
            }
            regex_patterns.append(regex_data)

    return regex_patterns


# ============================================================================
# JSON Operation Extractors
# ============================================================================

def extract_json_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract JSON serialization/deserialization operations.

    Detects json.dumps(), json.loads(), json.dump(), json.load().

    Returns:
        List of JSON operation dicts:
        {
            'line': int,
            'operation': str,  # 'dumps' | 'loads' | 'dump' | 'load'
            'direction': str,  # 'serialize' | 'deserialize'
            'in_function': str,
        }
    """
    json_operations = []

    if not isinstance(context.tree, ast.AST):
        return json_operations

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        operation = None

        # Check for json.function() calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'json':
                    if node.func.attr in JSON_FUNCTIONS:
                        operation = node.func.attr

        if operation:
            # Determine direction
            if operation in ('dumps', 'dump'):
                direction = 'serialize'
            else:
                direction = 'deserialize'

            json_data = {
                'line': node.lineno,
                'operation': operation,
                'direction': direction,
                'in_function': _find_containing_function(node, function_ranges),
            }
            json_operations.append(json_data)

    return json_operations


# ============================================================================
# Datetime Operation Extractors
# ============================================================================

def extract_datetime_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract datetime module usage.

    Detects datetime(), date(), time(), timedelta(), timezone() usage.

    Returns:
        List of datetime operation dicts:
        {
            'line': int,
            'datetime_type': str,  # 'datetime' | 'date' | 'time' | 'timedelta' | 'timezone'
            'in_function': str,
        }
    """
    datetime_operations = []

    if not isinstance(context.tree, ast.AST):
        return datetime_operations

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        datetime_type = None

        # Check for datetime.Type() calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'datetime':
                    if node.func.attr in DATETIME_TYPES:
                        datetime_type = node.func.attr

        # Check for direct Type() calls (after import)
        elif isinstance(node.func, ast.Name):
            if node.func.id in DATETIME_TYPES:
                datetime_type = node.func.id

        if datetime_type:
            datetime_data = {
                'line': node.lineno,
                'datetime_type': datetime_type,
                'in_function': _find_containing_function(node, function_ranges),
            }
            datetime_operations.append(datetime_data)

    return datetime_operations


# ============================================================================
# Path Operation Extractors
# ============================================================================

def extract_path_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract pathlib and os.path operations.

    Detects Path() usage, exists(), mkdir(), glob(), etc.

    Returns:
        List of path operation dicts:
        {
            'line': int,
            'operation': str,  # Method/function name
            'path_type': str,  # 'pathlib' | 'os.path'
            'in_function': str,
        }
    """
    path_operations = []

    if not isinstance(context.tree, ast.AST):
        return path_operations

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        operation = None
        path_type = None

        # Check for Path() constructor
        if isinstance(node.func, ast.Name) and node.func.id == 'Path':
            operation = 'Path'
            path_type = 'pathlib'

        # Check for path.method() calls
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in PATH_METHODS:
                operation = node.func.attr
                path_type = 'pathlib'  # Assume pathlib

            # Check for os.path.function() calls
            if isinstance(node.func.value, ast.Attribute):
                if isinstance(node.func.value.value, ast.Name):
                    if node.func.value.value.id == 'os' and node.func.value.attr == 'path':
                        operation = node.func.attr
                        path_type = 'os.path'

        if operation:
            path_data = {
                'line': node.lineno,
                'operation': operation,
                'path_type': path_type or 'unknown',
                'in_function': _find_containing_function(node, function_ranges),
            }
            path_operations.append(path_data)

    return path_operations


# ============================================================================
# Logging Pattern Extractors
# ============================================================================

def extract_logging_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract logging usage patterns.

    Detects logger.debug(), logger.info(), logger.warning(), etc.

    Returns:
        List of logging pattern dicts:
        {
            'line': int,
            'log_level': str,  # 'debug' | 'info' | 'warning' | 'error' | 'critical'
            'in_function': str,
        }
    """
    logging_patterns = []

    if not isinstance(context.tree, ast.AST):
        return logging_patterns

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        # Check for logger.method() or logging.method() calls
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in LOGGING_METHODS:
                logging_data = {
                    'line': node.lineno,
                    'log_level': method_name,
                    'in_function': _find_containing_function(node, function_ranges),
                }
                logging_patterns.append(logging_data)

    return logging_patterns


# ============================================================================
# Threading Pattern Extractors
# ============================================================================

def extract_threading_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract threading and multiprocessing usage.

    Detects Thread(), Lock(), Queue(), Process(), etc.

    Returns:
        List of threading pattern dicts:
        {
            'line': int,
            'threading_type': str,  # 'Thread' | 'Lock' | 'Queue' | 'Process'
            'in_function': str,
        }
    """
    threading_patterns = []

    if not isinstance(context.tree, ast.AST):
        return threading_patterns

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        threading_type = None

        # Check for threading.Type() calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id in ('threading', 'multiprocessing'):
                    if node.func.attr in THREADING_TYPES or node.func.attr == 'Process':
                        threading_type = node.func.attr

        # Check for direct Type() calls
        elif isinstance(node.func, ast.Name):
            if node.func.id in THREADING_TYPES or node.func.id == 'Process':
                threading_type = node.func.id

        if threading_type:
            threading_data = {
                'line': node.lineno,
                'threading_type': threading_type,
                'in_function': _find_containing_function(node, function_ranges),
            }
            threading_patterns.append(threading_data)

    return threading_patterns


# ============================================================================
# Context Manager Extractors
# ============================================================================

def extract_contextlib_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract contextlib usage (@contextmanager, closing(), suppress()).

    Returns:
        List of contextlib pattern dicts:
        {
            'line': int,
            'pattern': str,  # 'contextmanager' | 'closing' | 'suppress' | etc.
            'is_decorator': bool,
            'in_function': str,
        }
    """
    contextlib_patterns = []

    if not isinstance(context.tree, ast.AST):
        return contextlib_patterns

    function_ranges = context.function_ranges

    # Track decorators
    for node in context.find_nodes(ast.FunctionDef):
        for decorator in node.decorator_list:
            pattern = None
            if isinstance(decorator, ast.Name):
                if decorator.id in CONTEXTLIB_DECORATORS:
                    pattern = decorator.id
            elif isinstance(decorator, ast.Attribute):
                if isinstance(decorator.value, ast.Name):
                    if decorator.value.id == 'contextlib':
                        if decorator.attr in CONTEXTLIB_DECORATORS:
                            pattern = decorator.attr

            if pattern:
                contextlib_data = {
                    'line': decorator.lineno,
                    'pattern': pattern,
                    'is_decorator': True,
                    'in_function': _find_containing_function(node, function_ranges),
                }
                contextlib_patterns.append(contextlib_data)

    # Track function calls (closing(), suppress())
    for node in context.find_nodes(ast.Call):
        pattern = None

        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'contextlib':
                    if node.func.attr in CONTEXTLIB_DECORATORS:
                        pattern = node.func.attr

        elif isinstance(node.func, ast.Name):
            if node.func.id in CONTEXTLIB_DECORATORS:
                pattern = node.func.id

        if pattern:
            contextlib_data = {
                'line': node.lineno,
                'pattern': pattern,
                'is_decorator': False,
                'in_function': _find_containing_function(node, function_ranges),
            }
            contextlib_patterns.append(contextlib_data)

    return contextlib_patterns


# ============================================================================
# Type Checking Extractors
# ============================================================================

def extract_type_checking(context: FileContext) -> list[dict[str, Any]]:
    """Extract runtime type checking patterns.

    Detects isinstance(), issubclass(), type() checks.

    Returns:
        List of type checking dicts:
        {
            'line': int,
            'check_type': str,  # 'isinstance' | 'issubclass' | 'type'
            'in_function': str,
        }
    """
    type_checking = []

    if not isinstance(context.tree, ast.AST):
        return type_checking

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        check_type = None

        if isinstance(node.func, ast.Name):
            if node.func.id in ('isinstance', 'issubclass', 'type'):
                check_type = node.func.id

        if check_type:
            type_check_data = {
                'line': node.lineno,
                'check_type': check_type,
                'in_function': _find_containing_function(node, function_ranges),
            }
            type_checking.append(type_check_data)

    return type_checking
