"""Protocol and module pattern extractors - Dunder protocols and module metadata.

This module contains extraction logic for Python protocols:
- Iterator protocol (__iter__, __next__, StopIteration)
- Container protocol (__len__, __getitem__, __setitem__, __delitem__, __contains__)
- Callable protocol (__call__)
- Comparison protocol (rich comparison methods)
- Arithmetic protocol (numeric dunder methods)
- Pickle protocol (__getstate__, __setstate__, __reduce__)
- Weak reference usage (weakref module)
- Context variables (contextvars module)
- Module attributes (__name__, __file__, __doc__, __all__)
- Class decorators (separate from method decorators)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with pattern-specific keys
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

Week 6 Implementation (Python Coverage V2):
============================================
Implements 10 protocol patterns.

Expected extraction from TheAuditor codebase:
- ~80 iterator protocol implementations
- ~120 container protocol implementations
- ~60 callable protocol implementations
- ~200 comparison protocol implementations
- ~150 arithmetic protocol implementations
- ~20 pickle protocol implementations
- ~30 weakref usage
- ~15 contextvar usage
- ~200 module attribute usage
- ~25 class decorators
Total: ~900 protocol records
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


def _get_class_methods(class_node: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    """Extract methods from a class definition."""
    methods = {}
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef):
            methods[item.name] = item
    return methods


# Protocol method sets
ITERATOR_METHODS = {'__iter__', '__next__'}
CONTAINER_METHODS = {'__len__', '__getitem__', '__setitem__', '__delitem__', '__contains__'}
COMPARISON_METHODS = {'__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__'}
ARITHMETIC_METHODS = {
    '__add__', '__sub__', '__mul__', '__truediv__', '__floordiv__', '__mod__', '__pow__',
    '__radd__', '__rsub__', '__rmul__', '__rtruediv__', '__rfloordiv__', '__rmod__', '__rpow__',
    '__iadd__', '__isub__', '__imul__', '__itruediv__', '__ifloordiv__', '__imod__', '__ipow__',
}
PICKLE_METHODS = {'__getstate__', '__setstate__', '__reduce__', '__reduce_ex__'}


# ============================================================================
# Iterator Protocol Extractors
# ============================================================================

def extract_iterator_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract iterator protocol implementations.

    Detects:
    - __iter__ method
    - __next__ method
    - StopIteration raises
    - Generator-based __iter__

    Returns:
        List of iterator protocol dicts:
        {
            'line': int,
            'class_name': str,
            'has_iter': bool,
            'has_next': bool,
            'raises_stopiteration': bool,
            'is_generator': bool,
        }
    """
    iterator_protocols = []

    if not isinstance(context.tree, ast.AST):
        return iterator_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        # Check for iterator protocol methods
        has_iter = '__iter__' in methods
        has_next = '__next__' in methods

        if has_iter or has_next:
            # Check for StopIteration
            raises_stopiteration = False
            if '__next__' in methods:
                for subnode in context.find_nodes(ast.Raise):
                    if isinstance(subnode.exc, ast.Call):
                        if isinstance(subnode.exc.func, ast.Name):
                            if subnode.exc.func.id == 'StopIteration':
                                raises_stopiteration = True
                    elif isinstance(subnode.exc, ast.Name):
                        if subnode.exc.id == 'StopIteration':
                            raises_stopiteration = True

            # Check if __iter__ is a generator
            is_generator = False
            if '__iter__' in methods:
                for subnode in context.find_nodes((ast.Yield, ast.YieldFrom)):
                    is_generator = True
                    break

            iterator_data = {
                'line': node.lineno,
                'class_name': node.name,
                'has_iter': has_iter,
                'has_next': has_next,
                'raises_stopiteration': raises_stopiteration,
                'is_generator': is_generator,
            }
            iterator_protocols.append(iterator_data)

    return iterator_protocols


# ============================================================================
# Container Protocol Extractors
# ============================================================================

def extract_container_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract container protocol implementations.

    Detects:
    - __len__, __getitem__, __setitem__, __delitem__, __contains__
    - Sequence vs mapping distinction

    Returns:
        List of container protocol dicts:
        {
            'line': int,
            'class_name': str,
            'has_len': bool,
            'has_getitem': bool,
            'has_setitem': bool,
            'has_delitem': bool,
            'has_contains': bool,
            'is_sequence': bool,
            'is_mapping': bool,
        }
    """
    container_protocols = []

    if not isinstance(context.tree, ast.AST):
        return container_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        # Check for container protocol methods
        has_len = '__len__' in methods
        has_getitem = '__getitem__' in methods
        has_setitem = '__setitem__' in methods
        has_delitem = '__delitem__' in methods
        has_contains = '__contains__' in methods

        if any([has_len, has_getitem, has_setitem, has_delitem, has_contains]):
            # Try to distinguish sequence vs mapping
            # Sequence: __getitem__ with int index
            # Mapping: __getitem__ with any key type
            is_sequence = False
            is_mapping = False

            if '__getitem__' in methods:
                getitem_method = methods['__getitem__']
                # Simple heuristic: check if method signature uses 'index' or 'key'
                if getitem_method.args.args:
                    param_name = getitem_method.args.args[-1].arg
                    if 'index' in param_name or 'idx' in param_name or 'i' == param_name:
                        is_sequence = True
                    elif 'key' in param_name or 'k' == param_name:
                        is_mapping = True
                    else:
                        # Default: if has __len__, assume sequence
                        is_sequence = has_len
                        is_mapping = not has_len

            container_data = {
                'line': node.lineno,
                'class_name': node.name,
                'has_len': has_len,
                'has_getitem': has_getitem,
                'has_setitem': has_setitem,
                'has_delitem': has_delitem,
                'has_contains': has_contains,
                'is_sequence': is_sequence,
                'is_mapping': is_mapping,
            }
            container_protocols.append(container_data)

    return container_protocols


# ============================================================================
# Callable Protocol Extractors
# ============================================================================

def extract_callable_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract callable protocol implementations (__call__).

    Detects:
    - __call__ method
    - Parameter count
    - *args/**kwargs

    Returns:
        List of callable protocol dicts:
        {
            'line': int,
            'class_name': str,
            'param_count': int,
            'has_args': bool,
            'has_kwargs': bool,
        }
    """
    callable_protocols = []

    if not isinstance(context.tree, ast.AST):
        return callable_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        if '__call__' in methods:
            call_method = methods['__call__']

            # Count parameters (excluding self)
            param_count = len(call_method.args.args) - 1  # Exclude 'self'

            # Check for *args and **kwargs
            has_args = call_method.args.vararg is not None
            has_kwargs = call_method.args.kwarg is not None

            callable_data = {
                'line': call_method.lineno,
                'class_name': node.name,
                'param_count': param_count,
                'has_args': has_args,
                'has_kwargs': has_kwargs,
            }
            callable_protocols.append(callable_data)

    return callable_protocols


# ============================================================================
# Comparison Protocol Extractors
# ============================================================================

def extract_comparison_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract comparison protocol implementations.

    Detects:
    - Rich comparison methods (__eq__, __lt__, __gt__, __le__, __ge__, __ne__)
    - @total_ordering decorator
    - All methods implemented

    Returns:
        List of comparison protocol dicts:
        {
            'line': int,
            'class_name': str,
            'methods': str,  # Comma-separated
            'is_total_ordering': bool,
            'has_all_rich': bool,
        }
    """
    comparison_protocols = []

    if not isinstance(context.tree, ast.AST):
        return comparison_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        # Find comparison methods
        comparison_methods_found = [m for m in COMPARISON_METHODS if m in methods]

        if comparison_methods_found:
            # Check for @total_ordering decorator
            is_total_ordering = False
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    if decorator.id == 'total_ordering':
                        is_total_ordering = True
                elif isinstance(decorator, ast.Attribute):
                    if decorator.attr == 'total_ordering':
                        is_total_ordering = True

            # Check if all rich comparison methods are present
            has_all_rich = len(comparison_methods_found) == len(COMPARISON_METHODS)

            comparison_data = {
                'line': node.lineno,
                'class_name': node.name,
                'methods': ', '.join(sorted(comparison_methods_found)),
                'is_total_ordering': is_total_ordering,
                'has_all_rich': has_all_rich,
            }
            comparison_protocols.append(comparison_data)

    return comparison_protocols


# ============================================================================
# Arithmetic Protocol Extractors
# ============================================================================

def extract_arithmetic_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract arithmetic protocol implementations.

    Detects:
    - Arithmetic dunder methods (__add__, __mul__, etc.)
    - Reflected methods (__radd__, __rmul__, etc.)
    - In-place methods (__iadd__, __imul__, etc.)

    Returns:
        List of arithmetic protocol dicts:
        {
            'line': int,
            'class_name': str,
            'methods': str,  # Comma-separated
            'has_reflected': bool,
            'has_inplace': bool,
        }
    """
    arithmetic_protocols = []

    if not isinstance(context.tree, ast.AST):
        return arithmetic_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        # Find arithmetic methods
        arithmetic_methods_found = [m for m in ARITHMETIC_METHODS if m in methods]

        if arithmetic_methods_found:
            # Check for reflected methods
            has_reflected = any(m.startswith('__r') for m in arithmetic_methods_found)

            # Check for in-place methods
            has_inplace = any(m.startswith('__i') for m in arithmetic_methods_found)

            arithmetic_data = {
                'line': node.lineno,
                'class_name': node.name,
                'methods': ', '.join(sorted(arithmetic_methods_found)),
                'has_reflected': has_reflected,
                'has_inplace': has_inplace,
            }
            arithmetic_protocols.append(arithmetic_data)

    return arithmetic_protocols


# ============================================================================
# Pickle Protocol Extractors
# ============================================================================

def extract_pickle_protocol(context: FileContext) -> list[dict[str, Any]]:
    """Extract pickle protocol implementations.

    Detects:
    - __getstate__, __setstate__, __reduce__, __reduce_ex__

    Returns:
        List of pickle protocol dicts:
        {
            'line': int,
            'class_name': str,
            'has_getstate': bool,
            'has_setstate': bool,
            'has_reduce': bool,
            'has_reduce_ex': bool,
        }
    """
    pickle_protocols = []

    if not isinstance(context.tree, ast.AST):
        return pickle_protocols

    for node in context.find_nodes(ast.ClassDef):
        methods = _get_class_methods(node)

        # Check for pickle protocol methods
        has_getstate = '__getstate__' in methods
        has_setstate = '__setstate__' in methods
        has_reduce = '__reduce__' in methods
        has_reduce_ex = '__reduce_ex__' in methods

        if any([has_getstate, has_setstate, has_reduce, has_reduce_ex]):
            pickle_data = {
                'line': node.lineno,
                'class_name': node.name,
                'has_getstate': has_getstate,
                'has_setstate': has_setstate,
                'has_reduce': has_reduce,
                'has_reduce_ex': has_reduce_ex,
            }
            pickle_protocols.append(pickle_data)

    return pickle_protocols


# ============================================================================
# Weakref Usage Extractors
# ============================================================================

def extract_weakref_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract weakref module usage.

    Detects:
    - weakref.ref()
    - weakref.proxy()
    - WeakValueDictionary, WeakKeyDictionary

    Returns:
        List of weakref usage dicts:
        {
            'line': int,
            'usage_type': str,  # 'ref' | 'proxy' | 'WeakValueDictionary' | 'WeakKeyDictionary'
            'in_function': str,
        }
    """
    weakref_usage = []

    if not isinstance(context.tree, ast.AST):
        return weakref_usage

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        usage_type = None

        # Check for weakref.function() calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'weakref':
                    attr_name = node.func.attr
                    if attr_name in ('ref', 'proxy', 'WeakValueDictionary', 'WeakKeyDictionary'):
                        usage_type = attr_name

        # Check for direct calls (after from weakref import ...)
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ('ref', 'proxy', 'WeakValueDictionary', 'WeakKeyDictionary'):
                usage_type = func_name

        if usage_type:
            weakref_data = {
                'line': node.lineno,
                'usage_type': usage_type,
                'in_function': _find_containing_function(node, function_ranges),
            }
            weakref_usage.append(weakref_data)

    return weakref_usage


# ============================================================================
# Context Variable Extractors
# ============================================================================

def extract_contextvar_usage(context: FileContext) -> list[dict[str, Any]]:
    """Extract contextvars module usage.

    Detects:
    - ContextVar creation
    - get()/set() operations
    - Token usage

    Returns:
        List of contextvar usage dicts:
        {
            'line': int,
            'operation': str,  # 'ContextVar' | 'get' | 'set' | 'Token'
            'in_function': str,
        }
    """
    contextvar_usage = []

    if not isinstance(context.tree, ast.AST):
        return contextvar_usage

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Call):
        operation = None

        # Check for contextvars.ContextVar() calls
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == 'contextvars':
                    attr_name = node.func.attr
                    if attr_name in ('ContextVar', 'Token'):
                        operation = attr_name

        # Check for direct calls (after from contextvars import ...)
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ('ContextVar', 'Token'):
                operation = func_name

        # Check for .get()/.set() calls on ContextVar instances
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in ('get', 'set'):
                # Heuristic: if method is get/set, might be ContextVar
                # (This is best-effort without type analysis)
                operation = attr_name

        if operation:
            contextvar_data = {
                'line': node.lineno,
                'operation': operation,
                'in_function': _find_containing_function(node, function_ranges),
            }
            contextvar_usage.append(contextvar_data)

    return contextvar_usage


# ============================================================================
# Module Attribute Extractors
# ============================================================================

def extract_module_attributes(context: FileContext) -> list[dict[str, Any]]:
    """Extract module-level attribute usage.

    Detects:
    - __name__, __file__, __doc__, __all__ usage
    - Read vs write operations

    Returns:
        List of module attribute dicts:
        {
            'line': int,
            'attribute': str,  # '__name__' | '__file__' | '__doc__' | '__all__'
            'usage_type': str,  # 'read' | 'write' | 'check'
            'in_function': str,
        }
    """
    module_attributes = []

    if not isinstance(context.tree, ast.AST):
        return module_attributes

    function_ranges = context.function_ranges

    # Track assignment targets
    assignment_targets = set()
    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                assignment_targets.add((target.lineno, target.id))

    # Find module attribute usage
    for node in context.find_nodes(ast.Name):
        if node.id in ('__name__', '__file__', '__doc__', '__all__'):
            # Determine usage type
            usage_type = 'read'
            if (node.lineno, node.id) in assignment_targets:
                usage_type = 'write'
            elif isinstance(node.ctx, ast.Store):
                usage_type = 'write'

            module_attr_data = {
                'line': node.lineno,
                'attribute': node.id,
                'usage_type': usage_type,
                'in_function': _find_containing_function(node, function_ranges),
            }
            module_attributes.append(module_attr_data)

    return module_attributes


# ============================================================================
# Class Decorator Extractors
# ============================================================================

def extract_class_decorators(context: FileContext) -> list[dict[str, Any]]:
    """Extract class decorators (separate from method decorators).

    Detects:
    - @dataclass, @total_ordering, custom decorators
    - Decorator arguments

    Returns:
        List of class decorator dicts:
        {
            'line': int,
            'class_name': str,
            'decorator': str,
            'decorator_type': str,  # 'dataclass' | 'total_ordering' | 'custom'
            'has_arguments': bool,
        }
    """
    class_decorators = []

    if not isinstance(context.tree, ast.AST):
        return class_decorators

    for node in context.find_nodes(ast.ClassDef):
        for decorator in node.decorator_list:
            decorator_name = None
            has_arguments = False

            # Simple decorator: @name
            if isinstance(decorator, ast.Name):
                decorator_name = decorator.id

            # Decorator with arguments: @name(...)
            elif isinstance(decorator, ast.Call):
                has_arguments = True
                if isinstance(decorator.func, ast.Name):
                    decorator_name = decorator.func.id
                elif isinstance(decorator.func, ast.Attribute):
                    decorator_name = decorator.func.attr

            # Attribute decorator: @module.name
            elif isinstance(decorator, ast.Attribute):
                decorator_name = decorator.attr

            if decorator_name:
                # Classify decorator type
                decorator_type = 'custom'
                if decorator_name == 'dataclass':
                    decorator_type = 'dataclass'
                elif decorator_name == 'total_ordering':
                    decorator_type = 'total_ordering'

                class_decorator_data = {
                    'line': decorator.lineno,
                    'class_name': node.name,
                    'decorator': decorator_name,
                    'decorator_type': decorator_type,
                    'has_arguments': has_arguments,
                }
                class_decorators.append(class_decorator_data)

    return class_decorators
