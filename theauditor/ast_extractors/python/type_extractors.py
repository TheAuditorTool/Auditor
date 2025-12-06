"""Python advanced type extractors - Protocol, Generic, TypedDict, Literal."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext

from ..base import get_node_name


def extract_protocols(context: FileContext) -> list[dict[str, Any]]:
    """Extract Protocol class definitions from Python AST."""
    protocols = []

    if not context.tree:
        return protocols

    for node in context.find_nodes(ast.ClassDef):
        base_names = [get_node_name(base) for base in node.bases]
        if any("Protocol" in base for base in base_names):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(item.name)

            is_runtime_checkable = any(
                "runtime_checkable" in get_node_name(dec) for dec in node.decorator_list
            )

            protocols.append(
                {
                    "line": node.lineno,
                    "protocol_name": node.name,
                    "methods": methods,
                    "is_runtime_checkable": is_runtime_checkable,
                }
            )

    return protocols


def extract_generics(context: FileContext) -> list[dict[str, Any]]:
    """Extract Generic class definitions from Python AST."""
    generics = []

    if not context.tree:
        return generics

    for node in context.find_nodes(ast.ClassDef):
        has_generic = False
        type_params = []

        for base in node.bases:
            if (
                isinstance(base, ast.Subscript)
                and isinstance(base.value, ast.Name)
                and base.value.id == "Generic"
            ):
                has_generic = True

                if isinstance(base.slice, ast.Tuple):
                    for elt in base.slice.elts:
                        if isinstance(elt, ast.Name):
                            type_params.append(elt.id)
                elif isinstance(base.slice, ast.Name):
                    type_params.append(base.slice.id)

        if has_generic:
            generics.append(
                {
                    "line": node.lineno,
                    "class_name": node.name,
                    "type_params": type_params,
                }
            )

    return generics


def extract_typed_dicts(context: FileContext) -> list[dict[str, Any]]:
    """Extract TypedDict definitions from Python AST."""
    typed_dicts = []

    if not context.tree:
        return typed_dicts

    for node in context.find_nodes(ast.ClassDef):
        base_names = [get_node_name(base) for base in node.bases]
        if any("TypedDict" in base for base in base_names):
            fields = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    field_name = item.target.id
                    field_type = get_node_name(item.annotation) if item.annotation else None

                    is_required = True
                    if field_type and "NotRequired" in field_type:
                        is_required = False

                    fields.append(
                        {
                            "field_name": field_name,
                            "field_type": field_type,
                            "is_required": is_required,
                        }
                    )

            typed_dicts.append(
                {
                    "line": node.lineno,
                    "typeddict_name": node.name,
                    "fields": fields,
                }
            )

    return typed_dicts


def _is_literal_annotation(annotation_node) -> bool:
    """Check if AST node represents a Literal type annotation."""
    return (
        isinstance(annotation_node, ast.Subscript)
        and isinstance(annotation_node.value, ast.Name)
        and annotation_node.value.id == "Literal"
    )


def _get_literal_type_string(annotation_node) -> str:
    """Extract Literal type string from AST node."""
    if not isinstance(annotation_node, ast.Subscript):
        return ""

    parts = []
    if isinstance(annotation_node.slice, ast.Tuple):
        for elt in annotation_node.slice.elts:
            if isinstance(elt, ast.Constant):
                parts.append(repr(elt.value))
            elif isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                parts.append(repr(elt.s))
            elif isinstance(elt, ast.Constant) and isinstance(elt.value, (int, float)):
                parts.append(str(elt.n))
    elif isinstance(annotation_node.slice, ast.Constant):
        parts.append(repr(annotation_node.slice.value))
    elif isinstance(annotation_node.slice, ast.Constant) and isinstance(
        annotation_node.slice.value, str
    ):
        parts.append(repr(annotation_node.slice.s))
    elif isinstance(annotation_node.slice, ast.Constant) and isinstance(
        annotation_node.slice.value, (int, float)
    ):
        parts.append(str(annotation_node.slice.n))

    return f"Literal[{', '.join(parts)}]"


def extract_literals(context: FileContext) -> list[dict[str, Any]]:
    """Extract Literal type usage from Python AST."""
    literals = []

    if not context.tree:
        return literals

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        for arg in node.args.args:
            if arg.annotation and _is_literal_annotation(arg.annotation):
                literal_type = _get_literal_type_string(arg.annotation)
                literals.append(
                    {
                        "line": node.lineno,
                        "usage_context": "parameter",
                        "parameter_name": arg.arg,
                        "literal_type": literal_type,
                    }
                )

        if node.returns and _is_literal_annotation(node.returns):
            literal_type = _get_literal_type_string(node.returns)
            literals.append(
                {
                    "line": node.lineno,
                    "usage_context": "return",
                    "function_name": node.name,
                    "literal_type": literal_type,
                }
            )

    return literals


def extract_overloads(context: FileContext) -> list[dict[str, Any]]:
    """Extract @overload decorator usage from Python AST."""
    overloads = []

    if not context.tree:
        return overloads

    overload_groups = {}

    for node in context.find_nodes(ast.FunctionDef):
        has_overload = any("overload" in get_node_name(dec) for dec in node.decorator_list)

        if has_overload:
            if node.name not in overload_groups:
                overload_groups[node.name] = []

            param_types = []
            for arg in node.args.args:
                if arg.annotation:
                    param_types.append(get_node_name(arg.annotation))
                else:
                    param_types.append("Any")

            return_type = get_node_name(node.returns) if node.returns else None

            overload_groups[node.name].append(
                {
                    "line": node.lineno,
                    "param_types": param_types,
                    "return_type": return_type,
                }
            )

    for func_name, variants in overload_groups.items():
        overloads.append(
            {
                "function_name": func_name,
                "overload_count": len(variants),
                "variants": variants,
            }
        )

    return overloads
