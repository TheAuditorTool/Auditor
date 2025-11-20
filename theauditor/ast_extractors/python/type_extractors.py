"""Python advanced type extractors - Protocol, Generic, TypedDict, Literal.

This module contains extraction logic for advanced Python type system features:
- Protocol (structural subtyping)
- Generic[T] (generic classes and functions)
- TypedDict (structured dict types)
- Literal (literal types)
- @overload (function overloading)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
"""
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
from typing import Any, Dict, List

from ..base import get_node_name

logger = logging.getLogger(__name__)


def extract_protocols(context: FileContext) -> list[dict[str, Any]]:
    """Extract Protocol class definitions from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of Protocol records
    """
    protocols = []
    context.tree = tree.get("tree")

    if not context.tree:
        return protocols

    for node in context.find_nodes(ast.ClassDef):
        # Check if class inherits from Protocol
        base_names = [get_node_name(base) for base in node.bases]
        if any("Protocol" in base for base in base_names):
            # Extract method signatures (protocol members)
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(item.name)

            # Check for @runtime_checkable decorator
            is_runtime_checkable = any(
                "runtime_checkable" in get_node_name(dec)
                for dec in node.decorator_list
            )

            protocols.append({
                "line": node.lineno,
                "protocol_name": node.name,
                "methods": methods,
                "is_runtime_checkable": is_runtime_checkable,
            })

    return protocols


def extract_generics(context: FileContext) -> list[dict[str, Any]]:
    """Extract Generic class definitions from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of Generic records
    """
    generics = []
    context.tree = tree.get("tree")

    if not context.tree:
        return generics

    for node in context.find_nodes(ast.ClassDef):
        # Check if class inherits from Generic
        # Generic[T] is represented as ast.Subscript(value=Name('Generic'), slice=...)
        has_generic = False
        type_params = []

        for base in node.bases:
            # Check for Generic[...] (Subscript node)
            if isinstance(base, ast.Subscript):
                if isinstance(base.value, ast.Name) and base.value.id == "Generic":
                    has_generic = True
                    # Extract type parameters from subscript
                    if isinstance(base.slice, ast.Tuple):
                        # Multiple type params: Generic[T, K, V]
                        for elt in base.slice.elts:
                            if isinstance(elt, ast.Name):
                                type_params.append(elt.id)
                    elif isinstance(base.slice, ast.Name):
                        # Single type param: Generic[T]
                        type_params.append(base.slice.id)

        if has_generic:
            generics.append({
                "line": node.lineno,
                "class_name": node.name,
                "type_params": type_params,
            })

    return generics


def extract_typed_dicts(context: FileContext) -> list[dict[str, Any]]:
    """Extract TypedDict definitions from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of TypedDict records
    """
    typed_dicts = []
    context.tree = tree.get("tree")

    if not context.tree:
        return typed_dicts

    for node in context.find_nodes(ast.ClassDef):
        # Check if class inherits from TypedDict
        base_names = [get_node_name(base) for base in node.bases]
        if any("TypedDict" in base for base in base_names):
            # Extract field definitions
            fields = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    field_name = item.target.id
                    field_type = get_node_name(item.annotation) if item.annotation else None

                    # Check for Required/NotRequired
                    is_required = True
                    if field_type and "NotRequired" in field_type:
                        is_required = False

                    fields.append({
                        "field_name": field_name,
                        "field_type": field_type,
                        "is_required": is_required,
                    })

            typed_dicts.append({
                "line": node.lineno,
                "typeddict_name": node.name,
                "fields": fields,
            })

    return typed_dicts


def _is_literal_annotation(annotation_node) -> bool:
    """Check if AST node represents a Literal type annotation."""
    if isinstance(annotation_node, ast.Subscript):
        if isinstance(annotation_node.value, ast.Name) and annotation_node.value.id == "Literal":
            return True
    return False


def _get_literal_type_string(annotation_node) -> str:
    """Extract Literal type string from AST node.

    Converts Literal["a", "b"] to string representation.
    """
    if not isinstance(annotation_node, ast.Subscript):
        return ""

    # Build string representation
    parts = []
    if isinstance(annotation_node.slice, ast.Tuple):
        # Multiple values: Literal["a", "b", "c"]
        for elt in annotation_node.slice.elts:
            if isinstance(elt, ast.Constant):
                parts.append(repr(elt.value))
            elif (isinstance(elt, ast.Constant) and isinstance(elt.value, str)):  # Python 3.7 compat
                parts.append(repr(elt.s))
            elif (isinstance(elt, ast.Constant) and isinstance(elt.value, (int, float))):  # Python 3.7 compat
                parts.append(str(elt.n))
    elif isinstance(annotation_node.slice, ast.Constant):
        # Single value: Literal["a"]
        parts.append(repr(annotation_node.slice.value))
    elif (isinstance(annotation_node.slice, ast.Constant) and isinstance(annotation_node.slice.value, str)):  # Python 3.7 compat
        parts.append(repr(annotation_node.slice.s))
    elif (isinstance(annotation_node.slice, ast.Constant) and isinstance(annotation_node.slice.value, (int, float))):  # Python 3.7 compat
        parts.append(str(annotation_node.slice.n))

    return f"Literal[{', '.join(parts)}]"


def extract_literals(context: FileContext) -> list[dict[str, Any]]:
    """Extract Literal type usage from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of Literal usage records
    """
    literals = []
    context.tree = tree.get("tree")

    if not context.tree:
        return literals

    # Look for Literal in annotations
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        for arg in node.args.args:
            if arg.annotation and _is_literal_annotation(arg.annotation):
                literal_type = _get_literal_type_string(arg.annotation)
                literals.append({
                    "line": node.lineno,
                    "usage_context": "parameter",
                    "parameter_name": arg.arg,
                    "literal_type": literal_type,
                })

        # Return type annotation
        if node.returns and _is_literal_annotation(node.returns):
            literal_type = _get_literal_type_string(node.returns)
            literals.append({
                "line": node.lineno,
                "usage_context": "return",
                "function_name": node.name,
                "literal_type": literal_type,
            })

    return literals


def extract_overloads(context: FileContext) -> list[dict[str, Any]]:
    """Extract @overload decorator usage from Python AST.

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of overload records
    """
    overloads = []
    context.tree = tree.get("tree")

    if not context.tree:
        return overloads

    # Group overloaded functions by name
    overload_groups = {}

    for node in context.find_nodes(ast.FunctionDef):
        has_overload = any(
            "overload" in get_node_name(dec)
            for dec in node.decorator_list
        )

        if has_overload:
            if node.name not in overload_groups:
                overload_groups[node.name] = []

            # Extract parameter types
            param_types = []
            for arg in node.args.args:
                if arg.annotation:
                    param_types.append(get_node_name(arg.annotation))
                else:
                    param_types.append("Any")

            # Extract return type
            return_type = get_node_name(node.returns) if node.returns else None

            overload_groups[node.name].append({
                "line": node.lineno,
                "param_types": param_types,
                "return_type": return_type,
            })

    # Convert groups to records
    for func_name, variants in overload_groups.items():
        overloads.append({
            "function_name": func_name,
            "overload_count": len(variants),
            "variants": variants,
        })

    return overloads
