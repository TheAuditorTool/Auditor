"""Collection and method extractors - Dict/list/set/string methods + builtins.

This module contains extraction logic for collection operations:
- Dictionary methods (keys, values, items, get, update, pop, etc.)
- List methods (append, extend, insert, remove, pop, sort, reverse, etc.)
- Set operations (union, intersection, difference, symmetric_difference)
- String methods (split, join, strip, replace, find, startswith, etc.)
- Builtin functions (len, sum, max, min, sorted, enumerate, zip, map, filter)
- Itertools patterns (chain, cycle, combinations, permutations)
- Functools patterns (partial, reduce, lru_cache)
- Collections module (defaultdict, Counter, deque, etc.)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with pattern-specific keys
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

Week 3 Implementation (Python Coverage V2):
============================================
Implements 8 collection and method patterns.

Expected extraction from TheAuditor codebase:
- ~300 dict operations
- ~200 list mutations
- ~50 set operations
- ~250 string methods
- ~400 builtin function calls
- ~30 itertools usage
- ~40 functools usage
- ~50 collections module usage
Total: ~1,320 collection pattern records
"""
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def _find_containing_function(node: ast.AST, function_ranges: list) -> str:
    """Find the function containing this node."""
    if not hasattr(node, 'lineno'):
        return 'global'

    line_no = node.lineno
    for fname, start, end in function_ranges:
        if start <= line_no <= end:
            return fname
    return 'global'


# Dictionary methods we track
DICT_METHODS = {
    'keys', 'values', 'items', 'get', 'setdefault', 'update',
    'pop', 'popitem', 'clear', 'copy', 'fromkeys'
}

# List methods we track
LIST_METHODS = {
    'append', 'extend', 'insert', 'remove', 'pop', 'clear',
    'index', 'count', 'sort', 'reverse', 'copy'
}

# Set methods we track
SET_METHODS = {
    'add', 'remove', 'discard', 'pop', 'clear',
    'union', 'intersection', 'difference', 'symmetric_difference',
    'update', 'intersection_update', 'difference_update', 'symmetric_difference_update',
    'issubset', 'issuperset', 'isdisjoint'
}

# String methods we track
STRING_METHODS = {
    'split', 'join', 'strip', 'lstrip', 'rstrip', 'replace',
    'find', 'rfind', 'index', 'rindex', 'startswith', 'endswith',
    'upper', 'lower', 'capitalize', 'title', 'swapcase',
    'format', 'format_map', 'encode', 'decode'
}

# Builtin functions we track
BUILTIN_FUNCTIONS = {
    'len', 'sum', 'max', 'min', 'abs', 'round',
    'sorted', 'reversed', 'enumerate', 'zip',
    'map', 'filter', 'reduce',
    'any', 'all', 'range', 'list', 'dict', 'set', 'tuple'
}

# Itertools functions
ITERTOOLS_FUNCTIONS = {
    'chain', 'cycle', 'repeat', 'combinations', 'combinations_with_replacement',
    'permutations', 'product', 'islice', 'groupby', 'accumulate',
    'compress', 'dropwhile', 'filterfalse', 'starmap', 'takewhile', 'tee', 'zip_longest'
}

# Functools functions
FUNCTOOLS_FUNCTIONS = {
    'partial', 'reduce', 'wraps', 'lru_cache', 'cache',
    'cached_property', 'singledispatch', 'total_ordering'
}

# Collections module types
COLLECTIONS_TYPES = {
    'defaultdict', 'Counter', 'OrderedDict', 'deque',
    'ChainMap', 'namedtuple', 'UserDict', 'UserList', 'UserString'
}


# ============================================================================
# Dictionary Operation Extractors
# ============================================================================

def extract_dict_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract dictionary method calls.

    Detects all dict method usage: keys(), values(), items(), get(), update(), etc.

    Returns:
        List of dict operation dicts:
        {
            'line': int,
            'operation': str,  # Method name
            'has_default': bool,  # For get() with default
            'in_function': str,
        }
    """
    dict_ops = []

    if not isinstance(context.tree, ast.AST):
        return dict_ops

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in DICT_METHODS:
                has_default = False
                if method_name == 'get' and len(node.args) > 1:
                    has_default = True

                dict_data = {
                    'line': node.lineno,
                    'operation': method_name,
                    'has_default': has_default,
                    'in_function': _find_containing_function(node, function_ranges),
                }
                dict_ops.append(dict_data)

    return dict_ops


# ============================================================================
# List Mutation Extractors
# ============================================================================

def extract_list_mutations(context: FileContext) -> list[dict[str, Any]]:
    """Extract list method calls (focusing on mutations).

    Detects: append(), extend(), insert(), remove(), pop(), sort(), reverse(), etc.

    Returns:
        List of list mutation dicts:
        {
            'line': int,
            'method': str,  # Method name
            'mutates_in_place': bool,  # True if modifies list
            'in_function': str,
        }
    """
    list_mutations = []

    if not isinstance(context.tree, ast.AST):
        return list_mutations

    function_ranges = context.function_ranges

    # Methods that mutate vs return new
    mutating_methods = {'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'sort', 'reverse'}

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in LIST_METHODS:
                list_data = {
                    'line': node.lineno,
                    'method': method_name,
                    'mutates_in_place': method_name in mutating_methods,
                    'in_function': _find_containing_function(node, function_ranges),
                }
                list_mutations.append(list_data)

    return list_mutations


# ============================================================================
# Set Operation Extractors
# ============================================================================

def extract_set_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract set operations (union, intersection, difference, etc.).

    Detects both method calls and operators: union() vs |, intersection() vs &

    Returns:
        List of set operation dicts:
        {
            'line': int,
            'operation': str,  # Method name
            'in_function': str,
        }
    """
    set_ops = []

    if not isinstance(context.tree, ast.AST):
        return set_ops

    function_ranges = context.function_ranges

    # Set method calls
    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in SET_METHODS:
                set_data = {
                    'line': node.lineno,
                    'operation': method_name,
                    'in_function': _find_containing_function(node, function_ranges),
                }
                set_ops.append(set_data)

    return set_ops


# ============================================================================
# String Method Extractors
# ============================================================================

def extract_string_methods(context: FileContext) -> list[dict[str, Any]]:
    """Extract string method calls.

    Detects: split(), join(), strip(), replace(), find(), startswith(), etc.

    Returns:
        List of string method dicts:
        {
            'line': int,
            'method': str,  # Method name
            'in_function': str,
        }
    """
    string_methods = []

    if not isinstance(context.tree, ast.AST):
        return string_methods

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name in STRING_METHODS:
                string_data = {
                    'line': node.lineno,
                    'method': method_name,
                    'in_function': _find_containing_function(node, function_ranges),
                }
                string_methods.append(string_data)

    return string_methods


# ============================================================================
# Builtin Function Extractors
# ============================================================================

def extract_builtin_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract builtin function usage.

    Detects: len(), sum(), max(), min(), sorted(), enumerate(), zip(), map(), filter()

    Returns:
        List of builtin usage dicts:
        {
            'line': int,
            'builtin': str,  # Function name
            'has_key': bool,  # For sorted(items, key=...)
            'in_function': str,
        }
    """
    builtins = []

    if not isinstance(context.tree, ast.AST):
        return builtins

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in BUILTIN_FUNCTIONS:
                # Check for key argument in sorted/max/min
                has_key = False
                if func_name in {'sorted', 'max', 'min'}:
                    for keyword in node.keywords:
                        if keyword.arg == 'key':
                            has_key = True
                            break

                builtin_data = {
                    'line': node.lineno,
                    'builtin': func_name,
                    'has_key': has_key,
                    'in_function': _find_containing_function(node, function_ranges),
                }
                builtins.append(builtin_data)

    return builtins


# ============================================================================
# Itertools Usage Extractors
# ============================================================================

def extract_itertools_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract itertools function usage.

    Detects: chain(), cycle(), combinations(), permutations(), etc.

    Returns:
        List of itertools usage dicts:
        {
            'line': int,
            'function': str,  # Function name
            'is_infinite': bool,  # True for cycle, repeat (no count)
            'in_function': str,
        }
    """
    itertools_usage = []

    if not isinstance(context.tree, ast.AST):
        return itertools_usage

    function_ranges = context.function_ranges

    infinite_functions = {'cycle', 'count'}

    for node in context.find_nodes(ast.Call):
        # Check for itertools.function() calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'itertools':
                    func_name = node.func.attr
                    if func_name in ITERTOOLS_FUNCTIONS:
                        is_infinite = func_name in infinite_functions

                        # Check if repeat has count argument
                        if func_name == 'repeat' and len(node.args) > 1:
                            is_infinite = False

                        itertools_data = {
                            'line': node.lineno,
                            'function': func_name,
                            'is_infinite': is_infinite,
                            'in_function': _find_containing_function(node, function_ranges),
                        }
                        itertools_usage.append(itertools_data)

    return itertools_usage


# ============================================================================
# Functools Usage Extractors
# ============================================================================

def extract_functools_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract functools function usage.

    Detects: partial(), reduce(), lru_cache(), cached_property(), etc.

    Returns:
        List of functools usage dicts:
        {
            'line': int,
            'function': str,  # Function name
            'is_decorator': bool,  # True if used as @decorator
            'in_function': str,
        }
    """
    functools_usage = []

    if not isinstance(context.tree, ast.AST):
        return functools_usage

    function_ranges = context.function_ranges

    # Track decorators
    decorator_usage = set()
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorator_usage.add((decorator.lineno, decorator.id))
            elif isinstance(decorator, ast.Attribute):
                if isinstance(decorator.value, ast.Name) and decorator.value.id == 'functools':
                    decorator_usage.add((decorator.lineno, decorator.attr))

    # Track function calls
    for node in context.find_nodes(ast.Call):
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'functools':
                    func_name = node.func.attr
                    if func_name in FUNCTOOLS_FUNCTIONS:
                        is_decorator = (node.lineno, func_name) in decorator_usage

                        functools_data = {
                            'line': node.lineno,
                            'function': func_name,
                            'is_decorator': is_decorator,
                            'in_function': _find_containing_function(node, function_ranges),
                        }
                        functools_usage.append(functools_data)

    return functools_usage


# ============================================================================
# Collections Module Usage Extractors
# ============================================================================

def extract_collections_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract collections module usage.

    Detects: defaultdict, Counter, deque, OrderedDict, ChainMap, namedtuple

    Returns:
        List of collections usage dicts:
        {
            'line': int,
            'collection_type': str,  # Type name
            'default_factory': str,  # For defaultdict (if detectable)
            'in_function': str,
        }
    """
    collections_usage = []

    if not isinstance(context.tree, ast.AST):
        return collections_usage

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        collection_type = None

        # Check for collections.Type() calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'collections':
                    if node.func.attr in COLLECTIONS_TYPES:
                        collection_type = node.func.attr

        # Check for direct Type() calls (after import)
        elif isinstance(node.func, ast.Name):
            if node.func.id in COLLECTIONS_TYPES:
                collection_type = node.func.id

        if collection_type:
            # Try to detect default_factory for defaultdict
            default_factory = None
            if collection_type == 'defaultdict' and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Name):
                    default_factory = first_arg.id

            collections_data = {
                'line': node.lineno,
                'collection_type': collection_type,
                'default_factory': default_factory or 'unknown',
                'in_function': _find_containing_function(node, function_ranges),
            }
            collections_usage.append(collections_data)

    return collections_usage
