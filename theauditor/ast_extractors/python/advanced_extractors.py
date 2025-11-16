"""Python Coverage V2 - Advanced Patterns (8 extractors).

Extracts advanced/rarely-used Python patterns for complete coverage beyond
basic curriculum needs. These patterns are typically seen in advanced libraries
and frameworks rather than introductory Python code.

Architectural Contract (CRITICAL):
===================================
All extraction functions:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with pattern-specific keys
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
"""

import ast
from typing import Dict, List, Any


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_parent_map(tree: ast.AST) -> Dict[ast.AST, ast.AST]:
    """Build a map from each node to its parent node."""
    parent_map = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent
    return parent_map


def _get_enclosing_function(node: ast.AST, parent_map: Dict) -> str:
    """Get the name of the enclosing function or 'global'."""
    current = node
    while current in parent_map:
        current = parent_map[current]
        if isinstance(current, ast.FunctionDef):
            return current.name
        elif isinstance(current, ast.AsyncFunctionDef):
            return current.name
    return 'global'


# ============================================================================
# 1. NAMESPACE PACKAGES DETECTION
# ============================================================================

def extract_namespace_packages(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract namespace package patterns (pkgutil.extend_path usage).

    Detects:
    - pkgutil.extend_path() calls
    - __path__ manipulation for namespace packages

    Returns:
        List of namespace package dicts:
        {
            'line': int,
            'pattern': str,  # 'extend_path' | 'path_manipulation'
            'in_function': str,
        }
    """
    results = []
    tree_obj = tree.get('tree')
    if not tree_obj:
        return results

    parent_map = _get_parent_map(tree_obj)

    for node in ast.walk(tree_obj):
        # pkgutil.extend_path() calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if (isinstance(node.func.value, ast.Name) and
                    node.func.value.id == 'pkgutil' and
                    node.func.attr == 'extend_path'):
                    results.append({
                        'line': node.lineno,
                        'pattern': 'extend_path',
                        'in_function': _get_enclosing_function(node, parent_map),
                    })

        # __path__ manipulation
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '__path__':
                    results.append({
                        'line': node.lineno,
                        'pattern': 'path_manipulation',
                        'in_function': _get_enclosing_function(node, parent_map),
                    })

    return results


# ============================================================================
# 2. CACHED_PROPERTY DETECTION
# ============================================================================

def extract_cached_property(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract @cached_property decorator usage.

    Detects:
    - functools.cached_property
    - Custom cached_property implementations

    Returns:
        List of cached property dicts:
        {
            'line': int,
            'method_name': str,
            'in_class': str,
            'is_functools': bool,
        }
    """
    results = []
    tree_obj = tree.get('tree')
    if not tree_obj:
        return results

    for node in ast.walk(tree_obj):
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dec in item.decorator_list:
                        decorator_name = None
                        is_functools = False

                        if isinstance(dec, ast.Name):
                            decorator_name = dec.id
                        elif isinstance(dec, ast.Attribute):
                            if isinstance(dec.value, ast.Name):
                                if dec.value.id == 'functools' and dec.attr == 'cached_property':
                                    decorator_name = 'cached_property'
                                    is_functools = True

                        if decorator_name and 'cached_property' in decorator_name.lower():
                            results.append({
                                'line': item.lineno,
                                'method_name': item.name,
                                'in_class': class_name,
                                'is_functools': is_functools,
                            })

    return results


# ============================================================================
# 3. DESCRIPTOR PROTOCOL
# ============================================================================

def extract_descriptor_protocol(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract descriptor protocol implementations (__get__, __set__, __delete__).

    Returns:
        List of descriptor protocol dicts:
        {
            'line': int,
            'class_name': str,
            'has_get': bool,
            'has_set': bool,
            'has_delete': bool,
            'is_data_descriptor': bool,  # Has __set__ or __delete__
        }
    """
    results = []
    tree_obj = tree.get('tree')
    if not tree_obj:
        return results

    for node in ast.walk(tree_obj):
        if isinstance(node, ast.ClassDef):
            has_get = False
            has_set = False
            has_delete = False

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == '__get__':
                        has_get = True
                    elif item.name == '__set__':
                        has_set = True
                    elif item.name == '__delete__':
                        has_delete = True

            # Only record if it's actually a descriptor
            if has_get or has_set or has_delete:
                results.append({
                    'line': node.lineno,
                    'class_name': node.name,
                    'has_get': has_get,
                    'has_set': has_set,
                    'has_delete': has_delete,
                    'is_data_descriptor': has_set or has_delete,
                })

    return results


# ============================================================================
# 4. ATTRIBUTE ACCESS PROTOCOL
# ============================================================================

def extract_attribute_access_protocol(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract attribute access protocol (__getattr__, __setattr__, __delattr__, __getattribute__).

    Returns:
        List of attribute access protocol dicts:
        {
            'line': int,
            'class_name': str,
            'has_getattr': bool,
            'has_setattr': bool,
            'has_delattr': bool,
            'has_getattribute': bool,
        }
    """
    results = []
    tree_obj = tree.get('tree')
    if not tree_obj:
        return results

    for node in ast.walk(tree_obj):
        if isinstance(node, ast.ClassDef):
            has_getattr = False
            has_setattr = False
            has_delattr = False
            has_getattribute = False

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == '__getattr__':
                        has_getattr = True
                    elif item.name == '__setattr__':
                        has_setattr = True
                    elif item.name == '__delattr__':
                        has_delattr = True
                    elif item.name == '__getattribute__':
                        has_getattribute = True

            # Only record if it implements at least one method
            if has_getattr or has_setattr or has_delattr or has_getattribute:
                results.append({
                    'line': node.lineno,
                    'class_name': node.name,
                    'has_getattr': has_getattr,
                    'has_setattr': has_setattr,
                    'has_delattr': has_delattr,
                    'has_getattribute': has_getattribute,
                })

    return results


# ============================================================================
# 5. COPY PROTOCOL
# ============================================================================

def extract_copy_protocol(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract copy protocol (__copy__, __deepcopy__).

    Returns:
        List of copy protocol dicts:
        {
            'line': int,
            'class_name': str,
            'has_copy': bool,
            'has_deepcopy': bool,
        }
    """
    results = []
    tree_obj = tree.get('tree')
    if not tree_obj:
        return results

    for node in ast.walk(tree_obj):
        if isinstance(node, ast.ClassDef):
            has_copy = False
            has_deepcopy = False

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == '__copy__':
                        has_copy = True
                    elif item.name == '__deepcopy__':
                        has_deepcopy = True

            # Only record if it implements at least one method
            if has_copy or has_deepcopy:
                results.append({
                    'line': node.lineno,
                    'class_name': node.name,
                    'has_copy': has_copy,
                    'has_deepcopy': has_deepcopy,
                })

    return results


# ============================================================================
# 6. ELLIPSIS USAGE
# ============================================================================

def extract_ellipsis_usage(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract Ellipsis (...) usage patterns.

    Detects:
    - Ellipsis in type hints
    - Ellipsis in slicing
    - Ellipsis as placeholder

    Returns:
        List of ellipsis usage dicts:
        {
            'line': int,
            'context': str,  # 'type_hint' | 'slice' | 'expression' | 'pass_placeholder'
            'in_function': str,
        }
    """
    results = []
    tree_obj = tree.get('tree')
    if not tree_obj:
        return results

    parent_map = _get_parent_map(tree_obj)

    for node in ast.walk(tree_obj):
        if isinstance(node, ast.Constant) and node.value is ...:
            context = 'expression'

            # Check if in type annotation
            parent = parent_map.get(node)
            if parent and isinstance(parent, (ast.AnnAssign, ast.arg)):
                context = 'type_hint'
            # Check if in slice
            elif parent and isinstance(parent, ast.Slice):
                context = 'slice'
            # Check if used as pass placeholder
            elif isinstance(parent, ast.Expr):
                context = 'pass_placeholder'

            results.append({
                'line': node.lineno,
                'context': context,
                'in_function': _get_enclosing_function(node, parent_map),
            })

    return results


# ============================================================================
# 7. BYTES/BYTEARRAY OPERATIONS
# ============================================================================

def extract_bytes_operations(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract bytes/bytearray operations.

    Detects:
    - bytes() constructor calls
    - bytearray() constructor calls
    - .encode()/.decode() calls
    - bytes literals (b'...')

    Returns:
        List of bytes operation dicts:
        {
            'line': int,
            'operation': str,  # 'bytes' | 'bytearray' | 'encode' | 'decode' | 'literal'
            'in_function': str,
        }
    """
    results = []
    tree_obj = tree.get('tree')
    if not tree_obj:
        return results

    parent_map = _get_parent_map(tree_obj)

    for node in ast.walk(tree_obj):
        # bytes() and bytearray() calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id == 'bytes':
                    results.append({
                        'line': node.lineno,
                        'operation': 'bytes',
                        'in_function': _get_enclosing_function(node, parent_map),
                    })
                elif node.func.id == 'bytearray':
                    results.append({
                        'line': node.lineno,
                        'operation': 'bytearray',
                        'in_function': _get_enclosing_function(node, parent_map),
                    })
            # .encode()/.decode() method calls
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr == 'encode':
                    results.append({
                        'line': node.lineno,
                        'operation': 'encode',
                        'in_function': _get_enclosing_function(node, parent_map),
                    })
                elif node.func.attr == 'decode':
                    results.append({
                        'line': node.lineno,
                        'operation': 'decode',
                        'in_function': _get_enclosing_function(node, parent_map),
                    })

        # Bytes literals
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bytes):
                results.append({
                    'line': node.lineno,
                    'operation': 'literal',
                    'in_function': _get_enclosing_function(node, parent_map),
                })

    return results


# ============================================================================
# 8. EXEC/EVAL/COMPILE USAGE
# ============================================================================

def extract_exec_eval_compile(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract exec/eval/compile dynamic execution patterns.

    SECURITY NOTE: These patterns are security-sensitive and should be
    carefully reviewed for potential code injection vulnerabilities.

    Returns:
        List of dynamic execution dicts:
        {
            'line': int,
            'operation': str,  # 'exec' | 'eval' | 'compile'
            'has_globals': bool,
            'has_locals': bool,
            'in_function': str,
        }
    """
    results = []
    tree_obj = tree.get('tree')
    if not tree_obj:
        return results

    parent_map = _get_parent_map(tree_obj)

    for node in ast.walk(tree_obj):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                operation = None
                if node.func.id == 'exec':
                    operation = 'exec'
                elif node.func.id == 'eval':
                    operation = 'eval'
                elif node.func.id == 'compile':
                    operation = 'compile'

                if operation:
                    # Check if globals/locals are provided
                    has_globals = len(node.args) >= 2
                    has_locals = len(node.args) >= 3

                    # Also check keyword arguments
                    for kw in node.keywords:
                        if kw.arg == 'globals':
                            has_globals = True
                        elif kw.arg == 'locals':
                            has_locals = True

                    results.append({
                        'line': node.lineno,
                        'operation': operation,
                        'has_globals': has_globals,
                        'has_locals': has_locals,
                        'in_function': _get_enclosing_function(node, parent_map),
                    })

    return results
