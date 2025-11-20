"""Advanced class feature extractors - Metaclasses, descriptors, dataclasses, enums.

This module contains extraction logic for advanced Python class features:
- Metaclasses (type subclasses, __metaclass__)
- Descriptors (__get__, __set__, __delete__)
- Dataclasses (@dataclass decorator and fields)
- Enums (Enum subclasses and members)
- Slots (__slots__ optimization)
- Abstract base classes (ABC, @abstractmethod)
- Class methods and static methods (@classmethod, @staticmethod)
- Multiple inheritance and MRO
- Dunder methods (__init__, __str__, __repr__, __eq__, etc.)
- Visibility conventions (_private, __name_mangling)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with pattern-specific keys
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

Week 4 Implementation (Python Coverage V2):
============================================
Implements advanced class features.

Expected extraction from TheAuditor codebase:
- ~5 metaclasses
- ~10 descriptors
- ~20 dataclasses
- ~10 enums
- ~15 __slots__ usage
- ~30 abstract classes
- ~100 class/static methods
- ~50 multiple inheritance cases
- ~200 dunder methods
- ~150 visibility patterns
Total: ~590 advanced class feature records
"""
from __future__ import annotations
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


# Dunder method categories
LIFECYCLE_DUNDERS = {'__init__', '__new__', '__del__'}
REPRESENTATION_DUNDERS = {'__str__', '__repr__', '__format__', '__bytes__'}
COMPARISON_DUNDERS = {'__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__', '__hash__'}
NUMERIC_DUNDERS = {'__add__', '__sub__', '__mul__', '__truediv__', '__floordiv__', '__mod__', '__pow__',
                   '__radd__', '__rsub__', '__rmul__', '__rtruediv__', '__rfloordiv__', '__rmod__', '__rpow__'}
CONTAINER_DUNDERS = {'__len__', '__getitem__', '__setitem__', '__delitem__', '__contains__', '__iter__', '__next__'}
ATTRIBUTE_DUNDERS = {'__getattr__', '__setattr__', '__delattr__', '__getattribute__'}
CALLABLE_DUNDERS = {'__call__'}
CONTEXT_DUNDERS = {'__enter__', '__exit__', '__aenter__', '__aexit__'}


# ============================================================================
# Metaclass Extractors
# ============================================================================

def extract_metaclasses(context: FileContext) -> list[dict[str, Any]]:
    """Extract metaclass definitions and usage.

    Detects:
    - Classes that inherit from type
    - Classes using metaclass= parameter
    - __metaclass__ attribute (Python 2 style)

    Returns:
        List of metaclass dicts:
        {
            'line': int,
            'class_name': str,
            'metaclass_name': str,
            'is_definition': bool,  # True if defining metaclass, False if using
        }
    """
    metaclasses = []
    context.tree = tree.get("tree")

    if not isinstance(context.tree, ast.AST):
        return metaclasses

    for node in context.find_nodes(ast.ClassDef):
        # Check if class inherits from type (metaclass definition)
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == 'type':
                metaclass_data = {
                    'line': node.lineno,
                    'class_name': node.name,
                    'metaclass_name': node.name,  # Self is the metaclass
                    'is_definition': True,
                }
                metaclasses.append(metaclass_data)

        # Check for metaclass= keyword
        for keyword in node.keywords:
            if keyword.arg == 'metaclass':
                metaclass_name = 'unknown'
                if isinstance(keyword.value, ast.Name):
                    metaclass_name = keyword.value.id

                metaclass_data = {
                    'line': node.lineno,
                    'class_name': node.name,
                    'metaclass_name': metaclass_name,
                    'is_definition': False,
                }
                metaclasses.append(metaclass_data)

    return metaclasses


# ============================================================================
# Descriptor Extractors
# ============================================================================

def extract_descriptors(context: FileContext) -> list[dict[str, Any]]:
    """Extract descriptor protocol implementations.

    Detects classes with __get__, __set__, __delete__ methods.

    Returns:
        List of descriptor dicts:
        {
            'line': int,
            'class_name': str,
            'has_get': bool,
            'has_set': bool,
            'has_delete': bool,
            'descriptor_type': str,  # 'data' | 'non-data' | 'read-only'
        }
    """
    descriptors = []
    context.tree = tree.get("tree")

    if not isinstance(context.tree, ast.AST):
        return descriptors

    for node in context.find_nodes(ast.ClassDef):
        has_get = False
        has_set = False
        has_delete = False

        # Check for descriptor protocol methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name == '__get__':
                    has_get = True
                elif item.name == '__set__':
                    has_set = True
                elif item.name == '__delete__':
                    has_delete = True

        # Only record if at least __get__ is present
        if has_get:
            # Determine descriptor type
            if has_set or has_delete:
                descriptor_type = 'data'  # Data descriptor
            else:
                descriptor_type = 'non-data'  # Non-data descriptor

            descriptor_data = {
                'line': node.lineno,
                'class_name': node.name,
                'has_get': has_get,
                'has_set': has_set,
                'has_delete': has_delete,
                'descriptor_type': descriptor_type,
            }
            descriptors.append(descriptor_data)

    return descriptors


# ============================================================================
# Dataclass Extractors
# ============================================================================

def extract_dataclasses(context: FileContext) -> list[dict[str, Any]]:
    """Extract dataclass definitions.

    Detects @dataclass decorator usage and field definitions.

    Returns:
        List of dataclass dicts:
        {
            'line': int,
            'class_name': str,
            'frozen': bool,  # If frozen=True
            'field_count': int,
        }
    """
    dataclasses = []
    context.tree = tree.get("tree")

    if not isinstance(context.tree, ast.AST):
        return dataclasses

    for node in context.find_nodes(ast.ClassDef):
        has_dataclass = False
        frozen = False

        # Check decorators for @dataclass
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == 'dataclass':
                has_dataclass = True
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name) and decorator.func.id == 'dataclass':
                    has_dataclass = True
                    # Check for frozen=True
                    for keyword in decorator.keywords:
                        if keyword.arg == 'frozen':
                            if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                                frozen = True

        if has_dataclass:
            # Count fields (annotated attributes)
            field_count = 0
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    field_count += 1

            dataclass_data = {
                'line': node.lineno,
                'class_name': node.name,
                'frozen': frozen,
                'field_count': field_count,
            }
            dataclasses.append(dataclass_data)

    return dataclasses


# ============================================================================
# Enum Extractors
# ============================================================================

def extract_enums(context: FileContext) -> list[dict[str, Any]]:
    """Extract Enum class definitions.

    Detects classes inheriting from Enum and their members.

    Returns:
        List of enum dicts:
        {
            'line': int,
            'enum_name': str,
            'enum_type': str,  # 'Enum' | 'IntEnum' | 'Flag' | 'IntFlag'
            'member_count': int,
        }
    """
    enums = []
    context.tree = tree.get("tree")

    if not isinstance(context.tree, ast.AST):
        return enums

    enum_types = {'Enum', 'IntEnum', 'Flag', 'IntFlag', 'StrEnum'}

    for node in context.find_nodes(ast.ClassDef):
        enum_type = None

        # Check if inherits from Enum
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in enum_types:
                enum_type = base.id
            elif isinstance(base, ast.Attribute) and base.attr in enum_types:
                enum_type = base.attr

        if enum_type:
            # Count enum members (assignments)
            member_count = 0
            for item in node.body:
                if isinstance(item, ast.Assign):
                    member_count += len(item.targets)

            enum_data = {
                'line': node.lineno,
                'enum_name': node.name,
                'enum_type': enum_type,
                'member_count': member_count,
            }
            enums.append(enum_data)

    return enums


# ============================================================================
# Slots Extractors
# ============================================================================

def extract_slots(context: FileContext) -> list[dict[str, Any]]:
    """Extract __slots__ usage.

    Detects classes using __slots__ for memory optimization.

    Returns:
        List of slots dicts:
        {
            'line': int,
            'class_name': str,
            'slot_count': int,
        }
    """
    slots = []
    context.tree = tree.get("tree")

    if not isinstance(context.tree, ast.AST):
        return slots

    for node in context.find_nodes(ast.ClassDef):
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == '__slots__':
                        # Count slots
                        slot_count = 0
                        if isinstance(item.value, (ast.List, ast.Tuple)):
                            slot_count = len(item.value.elts)

                        slots_data = {
                            'line': item.lineno,
                            'class_name': node.name,
                            'slot_count': slot_count,
                        }
                        slots.append(slots_data)

    return slots


# ============================================================================
# Abstract Base Class Extractors
# ============================================================================

def extract_abstract_classes(context: FileContext) -> list[dict[str, Any]]:
    """Extract abstract base classes (ABC) and abstract methods.

    Detects classes using ABC or @abstractmethod decorators.

    Returns:
        List of ABC dicts:
        {
            'line': int,
            'class_name': str,
            'abstract_method_count': int,
        }
    """
    abstract_classes = []
    context.tree = tree.get("tree")

    if not isinstance(context.tree, ast.AST):
        return abstract_classes

    for node in context.find_nodes(ast.ClassDef):
        # Check if inherits from ABC
        inherits_abc = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in ('ABC', 'ABCMeta'):
                inherits_abc = True

        # Count abstract methods
        abstract_method_count = 0
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == 'abstractmethod':
                        abstract_method_count += 1

        if inherits_abc or abstract_method_count > 0:
            abc_data = {
                'line': node.lineno,
                'class_name': node.name,
                'abstract_method_count': abstract_method_count,
            }
            abstract_classes.append(abc_data)

    return abstract_classes


# ============================================================================
# Method Type Extractors
# ============================================================================

def extract_method_types(context: FileContext) -> list[dict[str, Any]]:
    """Extract method types (@classmethod, @staticmethod, instance methods).

    Returns:
        List of method type dicts:
        {
            'line': int,
            'method_name': str,
            'method_type': str,  # 'instance' | 'class' | 'static'
            'in_class': str,
        }
    """
    method_types = []
    context.tree = tree.get("tree")

    if not isinstance(context.tree, ast.AST):
        return method_types

    for node in context.find_nodes(ast.ClassDef):
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_type = 'instance'  # Default

                # Check decorators
                for decorator in item.decorator_list:
                    if isinstance(decorator, ast.Name):
                        if decorator.id == 'classmethod':
                            method_type = 'class'
                        elif decorator.id == 'staticmethod':
                            method_type = 'static'

                method_data = {
                    'line': item.lineno,
                    'method_name': item.name,
                    'method_type': method_type,
                    'in_class': node.name,
                }
                method_types.append(method_data)

    return method_types


# ============================================================================
# Multiple Inheritance Extractors
# ============================================================================

def extract_multiple_inheritance(context: FileContext) -> list[dict[str, Any]]:
    """Extract multiple inheritance patterns.

    Detects classes with more than one base class.

    Returns:
        List of multiple inheritance dicts:
        {
            'line': int,
            'class_name': str,
            'base_count': int,
            'base_classes': str,  # Comma-separated
        }
    """
    multi_inheritance = []
    context.tree = tree.get("tree")

    if not isinstance(context.tree, ast.AST):
        return multi_inheritance

    for node in context.find_nodes(ast.ClassDef):
        if len(node.bases) > 1:
            # Get base class names
            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.append(base.attr)

            inheritance_data = {
                'line': node.lineno,
                'class_name': node.name,
                'base_count': len(node.bases),
                'base_classes': ', '.join(base_names),
            }
            multi_inheritance.append(inheritance_data)

    return multi_inheritance


# ============================================================================
# Dunder Method Extractors
# ============================================================================

def extract_dunder_methods(context: FileContext) -> list[dict[str, Any]]:
    """Extract dunder (magic) method definitions.

    Categorizes dunder methods by purpose.

    Returns:
        List of dunder method dicts:
        {
            'line': int,
            'method_name': str,
            'category': str,  # 'lifecycle' | 'representation' | 'comparison' | etc.
            'in_class': str,
        }
    """
    dunder_methods = []
    context.tree = tree.get("tree")

    if not isinstance(context.tree, ast.AST):
        return dunder_methods

    def categorize_dunder(name):
        """Categorize dunder method by name."""
        if name in LIFECYCLE_DUNDERS:
            return 'lifecycle'
        elif name in REPRESENTATION_DUNDERS:
            return 'representation'
        elif name in COMPARISON_DUNDERS:
            return 'comparison'
        elif name in NUMERIC_DUNDERS:
            return 'numeric'
        elif name in CONTAINER_DUNDERS:
            return 'container'
        elif name in ATTRIBUTE_DUNDERS:
            return 'attribute'
        elif name in CALLABLE_DUNDERS:
            return 'callable'
        elif name in CONTEXT_DUNDERS:
            return 'context_manager'
        else:
            return 'other'

    for node in context.find_nodes(ast.ClassDef):
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name.startswith('__') and item.name.endswith('__'):
                    dunder_data = {
                        'line': item.lineno,
                        'method_name': item.name,
                        'category': categorize_dunder(item.name),
                        'in_class': node.name,
                    }
                    dunder_methods.append(dunder_data)

    return dunder_methods


# ============================================================================
# Visibility Convention Extractors
# ============================================================================

def extract_visibility_conventions(context: FileContext) -> list[dict[str, Any]]:
    """Extract naming conventions for visibility (_private, __name_mangling).

    Returns:
        List of visibility dicts:
        {
            'line': int,
            'name': str,
            'visibility': str,  # 'public' | 'protected' | 'private'
            'is_name_mangled': bool,
            'in_class': str,
        }
    """
    visibility = []
    context.tree = tree.get("tree")

    if not isinstance(context.tree, ast.AST):
        return visibility

    for node in context.find_nodes(ast.ClassDef):
        # Check methods and attributes
        for item in node.body:
            name = None
            line = None

            if isinstance(item, ast.FunctionDef):
                name = item.name
                line = item.lineno
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        line = item.lineno

            if name and not (name.startswith('__') and name.endswith('__')):
                # Determine visibility
                if name.startswith('__'):
                    vis = 'private'
                    is_mangled = True
                elif name.startswith('_'):
                    vis = 'protected'
                    is_mangled = False
                else:
                    vis = 'public'
                    is_mangled = False

                visibility_data = {
                    'line': line,
                    'name': name,
                    'visibility': vis,
                    'is_name_mangled': is_mangled,
                    'in_class': node.name,
                }
                visibility.append(visibility_data)

    return visibility
