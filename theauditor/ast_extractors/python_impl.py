"""Python AST extraction implementations.

DEPRECATION NOTICE (2025-10-30 - Phase 2.1)
============================================
This module is DEPRECATED and kept for rollback safety only.
All functionality has been refactored into modular structure:
  - theauditor/ast_extractors/python/core_extractors.py
  - theauditor/ast_extractors/python/framework_extractors.py
  - theauditor/ast_extractors/python/cfg_extractor.py

Use: `from theauditor.ast_extractors import python as python_impl`

This file will be removed in Phase 2.2 after verification period.

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
This is an IMPLEMENTATION layer module. All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer (indexer/__init__.py)
when storing to database. See indexer/__init__.py:952 for example.

This separation ensures single source of truth for file paths.
"""

import ast
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Set

from .base import (
    get_node_name,
    extract_vars_from_expr,
    find_containing_function_python,
    find_containing_class_python,
)

logger = logging.getLogger(__name__)


def _get_type_annotation(node: Optional[ast.AST]) -> Optional[str]:
    """Convert an annotation AST node into source text."""
    if node is None:
        return None
    try:
        if hasattr(ast, "unparse"):
            return ast.unparse(node)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Failed to unparse annotation at line %s: %s",
            getattr(node, "lineno", "?"),
            exc,
        )
    return None


def _analyze_annotation_flags(
    node: Optional[ast.AST], annotation_text: Optional[str]
) -> Tuple[bool, bool, Optional[str]]:
    """Derive generic flags from an annotation node."""
    if node is None or annotation_text is None:
        return False, False, None

    if isinstance(node, ast.Subscript):
        # Subscript indicates parametrised generic: List[int], Optional[str], etc.
        type_params_text = _get_type_annotation(getattr(node, "slice", None))
        if type_params_text:
            return True, True, type_params_text
        return True, False, None

    return False, False, None


def _parse_function_type_comment(comment: Optional[str]) -> Tuple[List[str], Optional[str]]:
    """Parse legacy PEP 484 type comments into parameter and return segments."""
    if not comment:
        return [], None

    text = comment.strip()
    if not text:
        return [], None

    # Strip optional leading markers ("# type:", "type:")
    if text.startswith("#"):
        text = text.lstrip("#").strip()
    if text.lower().startswith("type:"):
        text = text[5:].strip()

    if "->" not in text:
        return [], text or None

    params_part, return_part = text.split("->", 1)
    params_part = params_part.strip()
    return_part = return_part.strip() or None

    param_types: List[str] = []
    if params_part.startswith("(") and params_part.endswith(")"):
        inner = params_part[1:-1].strip()
        if inner:
            param_types = [segment.strip() for segment in inner.split(",")]
    elif params_part:
        param_types = [params_part]

    return param_types, return_part


SQLALCHEMY_BASE_IDENTIFIERS = {
    "Base",
    "DeclarativeBase",
    "db.Model",
    "sqlalchemy.orm.declarative_base",
}

DJANGO_MODEL_BASES = {
    "models.Model",
    "django.db.models.Model",
}

FASTAPI_HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
}


def _get_str_constant(node: Optional[ast.AST]) -> Optional[str]:
    """Return string value for constant nodes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):
        return node.s
    return None


def _keyword_arg(call: ast.Call, name: str) -> Optional[ast.AST]:
    """Fetch keyword argument by name from AST call."""
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _get_bool_constant(node: Optional[ast.AST]) -> Optional[bool]:
    """Return boolean value for constant/literal nodes."""
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
    return None


def _cascade_implies_delete(value: Optional[str]) -> bool:
    """Return True when cascade configuration includes delete semantics."""
    if not value:
        return False
    normalized = value.lower()
    return "delete" in normalized or "remove" in normalized


def _extract_backref_name(backref_value: ast.AST) -> Optional[str]:
    """Extract string name from backref keyword (string or sqlalchemy.orm.backref)."""
    name = _get_str_constant(backref_value)
    if name:
        return name

    if isinstance(backref_value, ast.Call):
        if backref_value.args:
            return _get_str_constant(backref_value.args[0]) or get_node_name(backref_value.args[0])
    return get_node_name(backref_value)


def _extract_backref_cascade(backref_value: ast.AST) -> bool:
    """Inspect backref(...) call for cascade style arguments."""
    if isinstance(backref_value, ast.Call):
        cascade_node = _keyword_arg(backref_value, "cascade")
        if cascade_node:
            cascade_value = _get_str_constant(cascade_node) or get_node_name(cascade_node)
            if _cascade_implies_delete(cascade_value):
                return True

        passive_deletes = _keyword_arg(backref_value, "passive_deletes")
        bool_val = _get_bool_constant(passive_deletes)
        if bool_val:
            return True
    return False


def _infer_relationship_type(
    attr_name: str,
    relationship_call: ast.Call
) -> str:
    """Infer relationship type using heuristics (uselist, secondary, naming)."""
    # Many-to-many when a secondary table is provided
    if _keyword_arg(relationship_call, "secondary"):
        return "manyToMany"

    uselist_arg = _keyword_arg(relationship_call, "uselist")
    uselist = _get_bool_constant(uselist_arg)

    if uselist is False:
        return "hasOne"

    # Default heuristic based on attribute naming
    if attr_name.endswith("s") or attr_name.endswith("_list"):
        return "hasMany"

    return "belongsTo"


def _inverse_relationship_type(rel_type: str) -> str:
    """Return the opposite relationship type for inferred inverse records."""
    if rel_type == "hasMany":
        return "belongsTo"
    if rel_type == "belongsTo":
        return "hasMany"
    if rel_type == "hasOne":
        return "belongsTo"
    # many-to-many (or unknown) mirrors itself
    return rel_type


def _is_truthy(node: Optional[ast.AST]) -> bool:
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.NameConstant):
        return bool(node.value)
    return False


def _dependency_name(call: ast.Call) -> Optional[str]:
    """Extract dependency target from Depends() call."""
    func_name = get_node_name(call.func)
    if not (func_name.endswith("Depends") or func_name == "Depends"):
        return None

    if call.args:
        return get_node_name(call.args[0])

    keyword = _keyword_arg(call, "dependency")
    if keyword:
        return get_node_name(keyword)
    return "Depends"


def _extract_fastapi_dependencies(func_node: ast.FunctionDef) -> List[str]:
    """Collect dependency call targets from FastAPI route parameters."""
    dependencies: List[str] = []

    positional = list(func_node.args.args)
    defaults = list(func_node.args.defaults)
    pos_defaults_start = len(positional) - len(defaults)

    for idx, arg in enumerate(positional):
        default = None
        if idx >= pos_defaults_start and defaults:
            default = defaults[idx - pos_defaults_start]
        if isinstance(default, ast.Call):
            dep = _dependency_name(default)
            if dep:
                dependencies.append(dep)

    for kw_arg, default in zip(func_node.args.kwonlyargs, func_node.args.kw_defaults):
        if isinstance(default, ast.Call):
            dep = _dependency_name(default)
            if dep:
                dependencies.append(dep)

    return dependencies


def extract_python_functions(tree: Dict, parser_self) -> List[Dict]:
    """Extract function definitions from Python AST.
    
    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance for accessing methods
        
    Returns:
        List of function info dictionaries
    """
    functions = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return functions
    
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # CRITICAL FIX: Add end_line for proper function boundaries
            end_line = getattr(node, "end_lineno", node.lineno)
            col = getattr(node, "col_offset", 0)

            function_entry: Dict[str, Any] = {
                "name": node.name,
                "line": node.lineno,
                "end_line": end_line,
                "column": col,
                "async": isinstance(node, ast.AsyncFunctionDef),
            }

            parameter_entries: List[Dict[str, Any]] = []

            def _register_param(arg: ast.arg, kind: str) -> None:
                if not isinstance(arg, ast.arg):
                    return

                annotation_text = _get_type_annotation(getattr(arg, "annotation", None))
                if not annotation_text and getattr(arg, "type_comment", None):
                    annotation_text = arg.type_comment.strip()

                is_generic, has_type_params, type_params = _analyze_annotation_flags(
                    getattr(arg, "annotation", None), annotation_text
                )

                parameter_entries.append({
                    "name": arg.arg,
                    "kind": kind,
                    "line": getattr(arg, "lineno", node.lineno),
                    "column": getattr(arg, "col_offset", 0),
                    "type_annotation": annotation_text,
                    "is_any": annotation_text in {"Any", "typing.Any"} if annotation_text else False,
                    "is_generic": is_generic,
                    "has_type_params": has_type_params,
                    "type_params": type_params,
                })

            # Positional-only args (Python 3.8+)
            for arg in getattr(node.args, "posonlyargs", []):
                _register_param(arg, "posonly")

            # Regular args
            for arg in node.args.args:
                _register_param(arg, "arg")

            # Vararg (*args)
            if node.args.vararg:
                _register_param(node.args.vararg, "vararg")

            # Keyword-only args
            for arg in node.args.kwonlyargs:
                _register_param(arg, "kwonly")

            # Kwarg (**kwargs)
            if node.args.kwarg:
                _register_param(node.args.kwarg, "kwarg")

            # Map type comments (legacy) onto parameters if present
            type_comment_params, type_comment_return = _parse_function_type_comment(
                getattr(node, "type_comment", None)
            )
            if type_comment_params:
                for idx, comment_value in enumerate(type_comment_params):
                    if idx < len(parameter_entries) and comment_value:
                        entry = parameter_entries[idx]
                        if not entry["type_annotation"]:
                            entry["type_annotation"] = comment_value

            # Capture decorator names for downstream analysis (e.g., typing.overload)
            decorators: List[str] = []
            for decorator in getattr(node, "decorator_list", []):
                decorators.append(get_node_name(decorator))

            # Collect parameter names for backward compatibility
            function_entry["args"] = [
                arg.arg for arg in node.args.args
            ]
            function_entry["parameters"] = [p["name"] for p in parameter_entries]

            # Determine return annotation (including legacy comments)
            return_annotation = _get_type_annotation(getattr(node, "returns", None))
            if not return_annotation and type_comment_return:
                return_annotation = type_comment_return

            is_generic, has_type_params, type_params = _analyze_annotation_flags(
                getattr(node, "returns", None), return_annotation
            )

            type_annotation_records: List[Dict[str, Any]] = []

            # Parameter records
            for param in parameter_entries:
                if not param["type_annotation"]:
                    continue
                type_annotation_records.append({
                    "line": param["line"],
                    "column": param["column"],
                    "symbol_name": f"{node.name}.{param['name']}",
                    "symbol_kind": "parameter",
                    "language": "python",
                    "type_annotation": param["type_annotation"],
                    "is_any": param["is_any"],
                    "is_unknown": False,
                    "is_generic": param["is_generic"],
                    "has_type_params": param["has_type_params"],
                    "type_params": param["type_params"],
                    "return_type": None,
                })

            # Function return record
            if return_annotation:
                is_any_return = return_annotation in {"Any", "typing.Any"}
                type_annotation_records.append({
                    "line": node.lineno,
                    "column": col,
                    "symbol_name": node.name,
                    "symbol_kind": "function",
                    "language": "python",
                    "type_annotation": None,
                    "return_type": return_annotation,
                    "is_any": is_any_return,
                    "is_unknown": False,
                    "is_generic": is_generic,
                    "has_type_params": has_type_params,
                    "type_params": type_params,
                })

            function_entry["type_annotations"] = type_annotation_records
            function_entry["return_type"] = return_annotation
            function_entry["is_typed"] = bool(type_annotation_records)
            function_entry["decorators"] = decorators

            functions.append(function_entry)
    
    return functions


def extract_python_classes(tree: Dict, parser_self) -> List[Dict]:
    """Extract class definitions from Python AST."""
    classes = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return classes
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "column": node.col_offset,
                "bases": [get_node_name(base) for base in node.bases],
                "type_annotations": [],
            })
    
    return classes


def extract_python_attribute_annotations(tree: Dict, parser_self) -> List[Dict]:
    """Extract type annotations declared on class or module attributes."""
    annotations: List[Dict[str, Any]] = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return annotations

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.AnnAssign):
            target_name = get_node_name(node.target)
            if not target_name:
                continue

            annotation_text = _get_type_annotation(node.annotation)
            if not annotation_text:
                continue

            class_name = find_containing_class_python(actual_tree, getattr(node, "lineno", 0))
            is_generic, has_type_params, type_params = _analyze_annotation_flags(node.annotation, annotation_text)

            annotations.append({
                "line": getattr(node, "lineno", 0),
                "column": getattr(node, "col_offset", 0),
                "symbol_name": f"{class_name}.{target_name}" if class_name else target_name,
                "symbol_kind": "class_attribute" if class_name else "module_attribute",
                "language": "python",
                "type_annotation": annotation_text,
                "return_type": None,
                "class_name": class_name,
                "is_any": annotation_text in {"Any", "typing.Any"},
                "is_unknown": False,
                "is_generic": is_generic,
                "has_type_params": has_type_params,
                "type_params": type_params,
            })

    return annotations


def extract_sqlalchemy_definitions(tree: Dict, parser_self) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Extract SQLAlchemy ORM models, fields, and relationships."""
    models: List[Dict[str, Any]] = []
    fields: List[Dict[str, Any]] = []
    relationships: List[Dict[str, Any]] = []
    seen_relationships: Set[Tuple[str, str, str]] = set()

    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return models, fields, relationships

    for node in actual_tree.body if isinstance(actual_tree, ast.Module) else []:
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = {get_node_name(base) for base in node.bases}
        if not any(
            name in SQLALCHEMY_BASE_IDENTIFIERS
            or name.endswith("Base")
            or name.endswith("Model")
            for name in base_names
        ):
            continue

        has_column = False
        for stmt in node.body:
            value = getattr(stmt, "value", None)
            if isinstance(value, ast.Call) and get_node_name(value.func).endswith("Column"):
                has_column = True
                break
        if not has_column:
            continue

        table_name = None
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        table_name = _get_str_constant(stmt.value) or get_node_name(stmt.value)

        models.append({
            "model_name": node.name,
            "line": node.lineno,
            "table_name": table_name,
            "orm_type": "sqlalchemy",
        })

        for stmt in node.body:
            value = getattr(stmt, "value", None)
            attr_name = None
            if isinstance(stmt, ast.Assign):
                targets = [t for t in stmt.targets if isinstance(t, ast.Name)]
                attr_name = targets[0].id if targets else None
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                attr_name = stmt.target.id

            if not attr_name or not isinstance(value, ast.Call):
                continue

            func_name = get_node_name(value.func)
            line_no = getattr(stmt, "lineno", node.lineno)

            if func_name.endswith("Column"):
                field_type = None
                if value.args:
                    field_type = _get_type_annotation(value.args[0]) or get_node_name(value.args[0])

                is_primary_key = _is_truthy(_keyword_arg(value, "primary_key"))
                is_foreign_key = False
                foreign_key_target = None

                for arg in value.args:
                    if isinstance(arg, ast.Call) and get_node_name(arg.func).endswith("ForeignKey"):
                        is_foreign_key = True
                        if arg.args:
                            foreign_key_target = _get_str_constant(arg.args[0]) or get_node_name(arg.args[0])

                fk_kw = _keyword_arg(value, "ForeignKey")
                if fk_kw:
                    is_foreign_key = True
                    foreign_key_target = _get_str_constant(fk_kw) or get_node_name(fk_kw)

                fields.append({
                    "model_name": node.name,
                    "field_name": attr_name,
                    "line": line_no,
                    "field_type": field_type,
                    "is_primary_key": is_primary_key,
                    "is_foreign_key": is_foreign_key,
                    "foreign_key_target": foreign_key_target,
                })
            elif func_name.endswith("relationship"):
                target_model = None
                if value.args:
                    target_model = _get_str_constant(value.args[0]) or get_node_name(value.args[0])

                relationship_type = _infer_relationship_type(attr_name, value)

                cascade_delete = False
                cascade_kw = _keyword_arg(value, "cascade")
                if cascade_kw:
                    cascade_val = _get_str_constant(cascade_kw) or get_node_name(cascade_kw)
                    cascade_delete = _cascade_implies_delete(cascade_val)

                passive_kw = _keyword_arg(value, "passive_deletes")
                passive_bool = _get_bool_constant(passive_kw)
                if passive_bool:
                    cascade_delete = True

                foreign_key = None
                foreign_keys_kw = _keyword_arg(value, "foreign_keys")
                if foreign_keys_kw:
                    fk_candidate = None
                    if isinstance(foreign_keys_kw, (ast.List, ast.Tuple)) and getattr(foreign_keys_kw, "elts", None):
                        fk_candidate = foreign_keys_kw.elts[0]
                    else:
                        fk_candidate = foreign_keys_kw

                    if fk_candidate is not None:
                        fk_text = _get_str_constant(fk_candidate) or get_node_name(fk_candidate)
                        if fk_text and "." in fk_text:
                            fk_text = fk_text.split(".")[-1]
                        foreign_key = fk_text

                def _add_relationship(
                    source_model: str,
                    target_model_name: Optional[str],
                    rel_type: str,
                    alias: Optional[str],
                    cascade_flag: bool,
                    fk_name: Optional[str],
                    rel_line: int,
                ) -> None:
                    target_name = target_model_name or "Unknown"
                    key = (source_model, target_name, alias or "")
                    if key in seen_relationships:
                        return
                    relationships.append({
                        "line": rel_line,
                        "source_model": source_model,
                        "target_model": target_name,
                        "relationship_type": rel_type,
                        "foreign_key": fk_name,
                        "cascade_delete": cascade_flag,
                        "as_name": alias,
                    })
                    seen_relationships.add(key)

                _add_relationship(
                    node.name,
                    target_model,
                    relationship_type,
                    attr_name,
                    cascade_delete,
                    foreign_key,
                    line_no,
                )

                back_populates_node = _keyword_arg(value, "back_populates")
                if back_populates_node and target_model:
                    inverse_alias = _get_str_constant(back_populates_node) or get_node_name(back_populates_node)
                    _add_relationship(
                        target_model,
                        node.name,
                        _inverse_relationship_type(relationship_type),
                        inverse_alias,
                        cascade_delete,
                        foreign_key,
                        line_no,
                    )

                backref_node = _keyword_arg(value, "backref")
                if backref_node and target_model:
                    backref_name = _extract_backref_name(backref_node)
                    inverse_cascade = cascade_delete or _extract_backref_cascade(backref_node)
                    inverse_type = _inverse_relationship_type(relationship_type)
                    _add_relationship(
                        target_model,
                        node.name,
                        inverse_type,
                        backref_name,
                        inverse_cascade,
                        foreign_key,
                        line_no,
                    )

    return models, fields, relationships


def extract_django_definitions(tree: Dict, parser_self) -> Tuple[List[Dict], List[Dict]]:
    """Extract Django ORM models and relationships."""
    relationships: List[Dict[str, Any]] = []
    models: List[Dict[str, Any]] = []

    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return models, relationships

    for node in actual_tree.body if isinstance(actual_tree, ast.Module) else []:
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = {get_node_name(base) for base in node.bases}
        if not any(name in DJANGO_MODEL_BASES for name in base_names):
            continue

        models.append({
            "model_name": node.name,
            "line": node.lineno,
            "table_name": None,
            "orm_type": "django",
        })

        for stmt in node.body:
            value = getattr(stmt, "value", None)
            attr_name = None
            if isinstance(stmt, ast.Assign):
                targets = [t for t in stmt.targets if isinstance(t, ast.Name)]
                attr_name = targets[0].id if targets else None
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                attr_name = stmt.target.id
            if not attr_name or not isinstance(value, ast.Call):
                continue

            func_name = get_node_name(value.func)
            line_no = getattr(stmt, "lineno", node.lineno)

            if func_name.endswith("ForeignKey"):
                target = None
                if value.args:
                    target = _get_str_constant(value.args[0]) or get_node_name(value.args[0])
                cascade = False
                on_delete = _keyword_arg(value, "on_delete")
                if on_delete and get_node_name(on_delete).endswith("CASCADE"):
                    cascade = True
                relationships.append({
                    "line": line_no,
                    "source_model": node.name,
                    "target_model": target or "Unknown",
                    "relationship_type": "belongsTo",
                    "foreign_key": attr_name,
                    "cascade_delete": cascade,
                    "as_name": attr_name,
                })
            elif func_name.endswith("ManyToManyField"):
                target = None
                if value.args:
                    target = _get_str_constant(value.args[0]) or get_node_name(value.args[0])
                relationships.append({
                    "line": line_no,
                    "source_model": node.name,
                    "target_model": target or "Unknown",
                    "relationship_type": "manyToMany",
                    "foreign_key": None,
                    "cascade_delete": False,
                    "as_name": attr_name,
                })
            elif func_name.endswith("OneToOneField"):
                target = None
                if value.args:
                    target = _get_str_constant(value.args[0]) or get_node_name(value.args[0])
                relationships.append({
                    "line": line_no,
                    "source_model": node.name,
                    "target_model": target or "Unknown",
                    "relationship_type": "hasOne",
                    "foreign_key": attr_name,
                    "cascade_delete": False,
                    "as_name": attr_name,
                })

    return models, relationships


def extract_pydantic_validators(tree: Dict, parser_self) -> List[Dict]:
    """Extract Pydantic validator metadata."""
    validators: List[Dict[str, Any]] = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return validators

    for node in actual_tree.body if isinstance(actual_tree, ast.Module) else []:
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = {get_node_name(base) for base in node.bases}
        if not any(name.endswith("BaseModel") or name == "BaseModel" for name in base_names):
            continue

        for stmt in node.body:
            if not isinstance(stmt, ast.FunctionDef):
                continue

            for decorator in stmt.decorator_list:
                dec_node = decorator.func if isinstance(decorator, ast.Call) else decorator
                dec_name = get_node_name(dec_node)
                if dec_name.endswith("root_validator"):
                    validators.append({
                        "line": stmt.lineno,
                        "model_name": node.name,
                        "field_name": None,
                        "validator_method": stmt.name,
                        "validator_type": "root",
                    })
                elif dec_name.endswith("validator"):
                    fields = []
                    if isinstance(decorator, ast.Call):
                        for arg in decorator.args:
                            candidate = _get_str_constant(arg) or get_node_name(arg)
                            if candidate:
                                fields.append(candidate)
                    if not fields:
                        fields = [None]
                    for field in fields:
                        validators.append({
                            "line": stmt.lineno,
                            "model_name": node.name,
                            "field_name": field,
                            "validator_method": stmt.name,
                            "validator_type": "field",
                        })

    return validators


def extract_marshmallow_schemas(tree: Dict, parser_self) -> List[Dict]:
    """[DEPRECATED - NOT USED] Extract Marshmallow schema definitions.

    WARNING: This function is part of the OLD monolithic python_impl.py file.
    The ACTIVE version is in python/framework_extractors.py:1108
    This file is kept for rollback only, NOT used in production.

    Detects classes extending Schema from marshmallow.

    Args:
        tree: AST tree dict
        parser_self: Parser instance for AST traversal

    Returns:
        List of dicts with keys:
            - line: int - Line number
            - schema_name: str - Class name
            - has_meta: bool - Whether Meta inner class exists
            - meta_fields: str - Comma-separated field list from Meta.fields (or None)
    """
    schemas = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return schemas

    # Find all class definitions
    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if class extends Schema
        extends_schema = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == 'Schema':
                extends_schema = True
                break
            elif isinstance(base, ast.Attribute) and base.attr == 'Schema':
                extends_schema = True
                break

        if not extends_schema:
            continue

        schema_name = node.name
        line = node.lineno

        # Check for Meta inner class
        has_meta = False
        meta_fields = None

        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == 'Meta':
                has_meta = True

                # Try to extract fields from Meta.fields attribute
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.name == 'fields':
                                # Extract field names from tuple/list
                                if isinstance(meta_item.value, (ast.Tuple, ast.List)):
                                    field_names = []
                                    for elt in meta_item.value.elts:
                                        if isinstance(elt, ast.Constant):
                                            field_names.append(elt.value)
                                    meta_fields = ', '.join(field_names)
                                break
                break

        # Count fields in the schema
        field_count = 0
        has_nested_schemas = False
        has_custom_validators = False

        for item in node.body:
            if isinstance(item, ast.Assign):
                # Check if it's a field assignment
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Check if value is a field call
                        if isinstance(item.value, ast.Call):
                            if hasattr(item.value.func, 'attr') and 'field' in item.value.func.attr.lower():
                                field_count += 1
                                # Check for nested schemas
                                if item.value.func.attr in ['Nested', 'List']:
                                    has_nested_schemas = True
                            elif hasattr(item.value.func, 'id') and 'field' in item.value.func.id.lower():
                                field_count += 1
            # Check for validator methods
            elif isinstance(item, ast.FunctionDef):
                if item.name.startswith('validate_') or item.name.startswith('validates_'):
                    has_custom_validators = True

        schemas.append({
            'line': line,
            'schema_class_name': schema_name,  # Changed from schema_name
            'field_count': field_count,
            'has_nested_schemas': has_nested_schemas,
            'has_custom_validators': has_custom_validators
        })

    return schemas


def extract_marshmallow_fields(tree: Dict, parser_self) -> List[Dict]:
    """Extract Marshmallow field definitions from schema classes.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int - Line number
            - schema_name: str - Parent schema class name
            - field_name: str - Field name
            - field_type: str - Field type (String, Integer, etc.)
            - is_required: bool - Whether field is required
            - validators: str - Validator names (comma-separated)
    """
    fields = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return fields

    # Find all class definitions that extend Schema
    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if class extends Schema
        extends_schema = any(
            (isinstance(base, ast.Name) and base.id == 'Schema') or
            (isinstance(base, ast.Attribute) and base.attr == 'Schema')
            for base in node.bases
        )

        if not extends_schema:
            continue

        schema_name = node.name

        # Find field assignments in class body
        for item in node.body:
            if isinstance(item, ast.Assign):
                # Get field name from assignment target
                field_name = None
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id
                        break

                if not field_name:
                    continue

                # Check if assignment is a fields.* call
                field_type = None
                required = False
                allow_none = False
                has_validate = False
                has_custom_validator = False

                if isinstance(item.value, ast.Call):
                    # Get field type (e.g., fields.String())
                    if isinstance(item.value.func, ast.Attribute):
                        if isinstance(item.value.func.value, ast.Name) and item.value.func.value.id == 'fields':
                            field_type = item.value.func.attr

                    # Check for keywords
                    for keyword in item.value.keywords:
                        if keyword.arg == 'required':
                            if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                                required = True

                        elif keyword.arg == 'allow_none':
                            if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                                allow_none = True

                        # Check for validate keyword
                        elif keyword.arg == 'validate':
                            has_validate = True
                            # Can be a single validator or list of validators
                            if isinstance(keyword.value, ast.Name):
                                has_custom_validator = True
                            elif isinstance(keyword.value, ast.List):
                                has_custom_validator = True

                if field_type:  # Only add if we detected a fields.* pattern
                    fields.append({
                        'line': item.lineno,
                        'schema_class_name': schema_name,  # Changed from schema_name
                        'field_name': field_name,
                        'field_type': field_type,
                        'required': required,  # Changed from is_required
                        'allow_none': allow_none,
                        'has_validate': has_validate,
                        'has_custom_validator': has_custom_validator
                    })

    return fields


def extract_wtforms_forms(tree: Dict, parser_self) -> List[Dict]:
    """Extract WTForms form definitions.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - form_name: str
            - has_csrf: bool - Whether CSRF protection is enabled
            - submit_method: str - Submit method name if defined
    """
    forms = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return forms

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if class extends Form or FlaskForm
        extends_form = any(
            (isinstance(base, ast.Name) and base.id in ['Form', 'FlaskForm']) or
            (isinstance(base, ast.Attribute) and base.attr in ['Form', 'FlaskForm'])
            for base in node.bases
        )

        if not extends_form:
            continue

        form_name = node.name
        line = node.lineno
        has_csrf = True  # Default for FlaskForm
        submit_method = None

        # Look for submit method
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name in ['submit', 'on_submit', 'validate_on_submit']:
                submit_method = item.name
                break

        forms.append({
            'line': line,
            'form_name': form_name,
            'has_csrf': has_csrf,
            'submit_method': submit_method
        })

    return forms


def extract_wtforms_fields(tree: Dict, parser_self) -> List[Dict]:
    """Extract WTForms field definitions.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - form_name: str
            - field_name: str
            - field_type: str - StringField, IntegerField, etc.
            - validators: str - Comma-separated validator names
            - default_value: str - Default value if present
    """
    fields = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return fields

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if class extends Form
        extends_form = any(
            (isinstance(base, ast.Name) and base.id in ['Form', 'FlaskForm']) or
            (isinstance(base, ast.Attribute) and base.attr in ['Form', 'FlaskForm'])
            for base in node.bases
        )

        if not extends_form:
            continue

        form_name = node.name

        # Find field assignments
        for item in node.body:
            if isinstance(item, ast.Assign):
                field_name = None
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id
                        break

                if not field_name:
                    continue

                field_type = None
                validators = []
                default_value = None

                if isinstance(item.value, ast.Call):
                    # Get field type (e.g., StringField())
                    if isinstance(item.value.func, ast.Name):
                        field_type = item.value.func.id

                    # Extract validators from second positional arg or 'validators' keyword
                    if len(item.value.args) >= 2:
                        if isinstance(item.value.args[1], ast.List):
                            for elt in item.value.args[1].elts:
                                if isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name):
                                    validators.append(elt.func.id)

                    # Check for default keyword
                    for keyword in item.value.keywords:
                        if keyword.arg == 'default':
                            if isinstance(keyword.value, ast.Constant):
                                default_value = str(keyword.value.value)

                if field_type and 'Field' in field_type:  # Only WTForms fields
                    fields.append({
                        'line': item.lineno,
                        'form_name': form_name,
                        'field_name': field_name,
                        'field_type': field_type,
                        'validators': ', '.join(validators) if validators else None,
                        'default_value': default_value
                    })

    return fields


def extract_celery_tasks(tree: Dict, parser_self) -> List[Dict]:
    """Extract Celery task definitions.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - task_name: str - Function name
            - bind: bool - Whether bind=True
            - max_retries: int - Max retries (or None)
            - rate_limit: str - Rate limit string (or None)
    """
    tasks = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return tasks

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check for @task or @app.task decorator
        has_task_decorator = False
        bind = False
        max_retries = None
        rate_limit = None

        for decorator in node.decorator_list:
            # Check for @task
            if isinstance(decorator, ast.Name) and decorator.id == 'task':
                has_task_decorator = True

            # Check for @app.task or @celery.task
            elif isinstance(decorator, ast.Attribute) and decorator.attr == 'task':
                has_task_decorator = True

            # Check for @task(...) with arguments
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name) and decorator.func.id == 'task':
                    has_task_decorator = True
                elif isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'task':
                    has_task_decorator = True

                # Extract decorator arguments
                for keyword in decorator.keywords:
                    if keyword.arg == 'bind':
                        if isinstance(keyword.value, ast.Constant):
                            bind = keyword.value.value
                    elif keyword.arg == 'max_retries':
                        if isinstance(keyword.value, ast.Constant):
                            max_retries = keyword.value.value
                    elif keyword.arg == 'rate_limit':
                        if isinstance(keyword.value, ast.Constant):
                            rate_limit = keyword.value.value

        if not has_task_decorator:
            continue

        tasks.append({
            'line': node.lineno,
            'task_name': node.name,
            'bind': bind,
            'max_retries': max_retries,
            'rate_limit': rate_limit
        })

    return tasks


def extract_celery_task_calls(tree: Dict, parser_self) -> List[Dict]:
    """Extract Celery task invocations (.delay(), .apply_async()).

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - task_name: str - Task being invoked
            - call_type: str - 'delay' or 'apply_async'
            - arguments: str - Stringified arguments
    """
    task_calls = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return task_calls

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.Call):
            continue

        # Check for task.delay() or task.apply_async()
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ['delay', 'apply_async']:
                # Get task name from the object being called
                task_name = None
                if isinstance(node.func.value, ast.Name):
                    task_name = node.func.value.id

                if task_name:
                    # Stringify arguments
                    arguments = []
                    for arg in node.args:
                        if isinstance(arg, ast.Constant):
                            arguments.append(repr(arg.value))
                        elif isinstance(arg, ast.Name):
                            arguments.append(arg.id)

                    for keyword in node.keywords:
                        if isinstance(keyword.value, ast.Constant):
                            arguments.append(f"{keyword.arg}={repr(keyword.value.value)}")

                    task_calls.append({
                        'line': node.lineno,
                        'task_name': task_name,
                        'call_type': node.func.attr,
                        'arguments': ', '.join(arguments)
                    })

    return task_calls


def extract_celery_beat_schedules(tree: Dict, parser_self) -> List[Dict]:
    """Extract Celery Beat periodic task schedules.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - schedule_name: str - Schedule entry name
            - task_name: str - Task to execute
            - crontab: str - Crontab schedule (if present)
            - interval: str - Interval schedule (if present)
    """
    schedules = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return schedules

    # Look for beat_schedule dict or CELERYBEAT_SCHEDULE dict
    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.Assign):
            continue

        schedule_dict_name = None

        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr == 'beat_schedule':
                schedule_dict_name = 'beat_schedule'
                break
            elif isinstance(target, ast.Name) and target.id == 'CELERYBEAT_SCHEDULE':
                schedule_dict_name = 'CELERYBEAT_SCHEDULE'
                break

        if not schedule_dict_name:
            continue

        # Parse the dict
        if isinstance(node.value, ast.Dict):
            for key, value in zip(node.value.keys, node.value.values):
                if isinstance(key, ast.Constant):
                    schedule_name = key.value

                    # Parse schedule entry dict
                    task_name = None
                    crontab = None
                    interval = None

                    if isinstance(value, ast.Dict):
                        for k, v in zip(value.keys, value.values):
                            if isinstance(k, ast.Constant):
                                if k.value == 'task':
                                    if isinstance(v, ast.Constant):
                                        task_name = v.value
                                elif k.value == 'schedule':
                                    # Could be crontab(...) or interval seconds
                                    if isinstance(v, ast.Call):
                                        if isinstance(v.func, ast.Name) and v.func.id == 'crontab':
                                            # Extract crontab args
                                            crontab_parts = []
                                            for keyword in v.keywords:
                                                if isinstance(keyword.value, ast.Constant):
                                                    crontab_parts.append(f"{keyword.arg}={keyword.value.value}")
                                            crontab = ', '.join(crontab_parts)
                                    elif isinstance(v, ast.Constant):
                                        interval = str(v.value)

                    if task_name:
                        schedules.append({
                            'line': node.lineno,
                            'schedule_name': schedule_name,
                            'task_name': task_name,
                            'crontab': crontab,
                            'interval': interval
                        })

    return schedules


def extract_pytest_fixtures(tree: Dict, parser_self) -> List[Dict]:
    """Extract pytest fixture definitions.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - fixture_name: str - Function name
            - scope: str - 'function', 'class', 'module', 'session'
            - autouse: bool - Whether autouse=True
    """
    fixtures = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return fixtures

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check for @pytest.fixture decorator
        has_fixture_decorator = False
        scope = 'function'  # Default
        autouse = False

        for decorator in node.decorator_list:
            # Check for @pytest.fixture
            if isinstance(decorator, ast.Attribute):
                if isinstance(decorator.value, ast.Name) and decorator.value.id == 'pytest':
                    if decorator.attr == 'fixture':
                        has_fixture_decorator = True

            # Check for @pytest.fixture(...) with arguments
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if isinstance(decorator.func.value, ast.Name) and decorator.func.value.id == 'pytest':
                        if decorator.func.attr == 'fixture':
                            has_fixture_decorator = True

                            # Extract decorator arguments
                            for keyword in decorator.keywords:
                                if keyword.arg == 'scope':
                                    if isinstance(keyword.value, ast.Constant):
                                        scope = keyword.value.value
                                elif keyword.arg == 'autouse':
                                    if isinstance(keyword.value, ast.Constant):
                                        autouse = keyword.value.value

        if not has_fixture_decorator:
            continue

        fixtures.append({
            'line': node.lineno,
            'fixture_name': node.name,
            'scope': scope,
            'autouse': autouse
        })

    return fixtures


def extract_pytest_parametrize(tree: Dict, parser_self) -> List[Dict]:
    """Extract pytest.mark.parametrize decorators.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - test_function: str - Test function name
            - parameter_names: str - Comma-separated parameter names
            - parameter_values: str - Stringified parameter values
    """
    parametrize_decorators = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return parametrize_decorators

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        for decorator in node.decorator_list:
            # Check for @pytest.mark.parametrize(...)
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    # Check for pytest.mark.parametrize
                    if (isinstance(decorator.func.value, ast.Attribute) and
                        isinstance(decorator.func.value.value, ast.Name) and
                        decorator.func.value.value.id == 'pytest' and
                        decorator.func.value.attr == 'mark' and
                        decorator.func.attr == 'parametrize'):

                        # Extract parameter names (first arg)
                        parameter_names = None
                        if len(decorator.args) >= 1:
                            if isinstance(decorator.args[0], ast.Constant):
                                parameter_names = decorator.args[0].value

                        # Extract parameter values (second arg)
                        parameter_values = None
                        if len(decorator.args) >= 2:
                            # This is typically a list of tuples
                            parameter_values = ast.unparse(decorator.args[1])

                        if parameter_names:
                            parametrize_decorators.append({
                                'line': node.lineno,
                                'test_function': node.name,
                                'parameter_names': parameter_names,
                                'parameter_values': parameter_values
                            })

    return parametrize_decorators


def extract_pytest_markers(tree: Dict, parser_self) -> List[Dict]:
    """Extract custom pytest markers.

    Args:
        tree: AST tree dict
        parser_self: Parser instance

    Returns:
        List of dicts with keys:
            - line: int
            - test_function: str - Test function name
            - marker_name: str - Marker name (e.g., 'slow', 'skipif')
            - marker_args: str - Stringified marker arguments (or None)
    """
    markers = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return markers

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        for decorator in node.decorator_list:
            # Check for @pytest.mark.* (excluding parametrize which is handled separately)
            if isinstance(decorator, ast.Attribute):
                if (isinstance(decorator.value, ast.Attribute) and
                    isinstance(decorator.value.value, ast.Name) and
                    decorator.value.value.id == 'pytest' and
                    decorator.value.attr == 'mark'):

                    marker_name = decorator.attr
                    if marker_name != 'parametrize':  # Skip parametrize
                        markers.append({
                            'line': node.lineno,
                            'test_function': node.name,
                            'marker_name': marker_name,
                            'marker_args': None
                        })

            # Check for @pytest.mark.*(...) with arguments
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if (isinstance(decorator.func.value, ast.Attribute) and
                        isinstance(decorator.func.value.value, ast.Name) and
                        decorator.func.value.value.id == 'pytest' and
                        decorator.func.value.attr == 'mark'):

                        marker_name = decorator.func.attr
                        if marker_name != 'parametrize':  # Skip parametrize
                            # Stringify arguments
                            marker_args = ast.unparse(decorator)
                            markers.append({
                                'line': node.lineno,
                                'test_function': node.name,
                                'marker_name': marker_name,
                                'marker_args': marker_args
                            })

    return markers



def extract_flask_blueprints(tree: Dict, parser_self) -> List[Dict]:
    """Detect Flask blueprint declarations."""
    blueprints: List[Dict[str, Any]] = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return blueprints

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Assign):
            if not isinstance(node.value, ast.Call):
                continue
            func_name = get_node_name(node.value.func)
            if not func_name.endswith("Blueprint"):
                continue
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            if not targets:
                continue
            var_name = targets[0].id
            name_arg = node.value.args[0] if node.value.args else None
            blueprint_name = _get_str_constant(name_arg) or var_name
            url_prefix = _get_str_constant(_keyword_arg(node.value, "url_prefix"))
            subdomain = _get_str_constant(_keyword_arg(node.value, "subdomain"))
            blueprints.append({
                "line": getattr(node, "lineno", 0),
                "blueprint_name": blueprint_name,
                "url_prefix": url_prefix,
                "subdomain": subdomain,
            })

    return blueprints


def extract_python_calls(tree: Dict, parser_self) -> List[Dict]:
    """Extract function calls from Python AST."""
    calls = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return calls
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Call):
            func_name = get_node_name(node.func)
            if func_name:
                calls.append({
                    "name": func_name,
                    "line": node.lineno,
                    "column": node.col_offset,
                    "args_count": len(node.args),
                })
    
    return calls


def extract_python_imports(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract import statements from Python AST."""
    imports = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return imports
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "source": "import",
                    "target": alias.name,
                    "type": "import",
                    "line": node.lineno,
                    "as": alias.asname,
                    "specifiers": []
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append({
                    "source": "from",
                    "target": module,
                    "type": "from",
                    "line": node.lineno,
                    "imported": alias.name,
                    "as": alias.asname,
                    "specifiers": [alias.name]
                })
    
    return imports


def extract_python_exports(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract export statements from Python AST.
    
    In Python, all top-level functions, classes, and assignments are "exported".
    """
    exports = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return exports
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.FunctionDef) and node.col_offset == 0:
            exports.append({
                "name": node.name,
                "type": "function",
                "line": node.lineno,
                "default": False
            })
        elif isinstance(node, ast.ClassDef) and node.col_offset == 0:
            exports.append({
                "name": node.name,
                "type": "class",
                "line": node.lineno,
                "default": False
            })
        elif isinstance(node, ast.Assign) and node.col_offset == 0:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    exports.append({
                        "name": target.id,
                        "type": "variable",
                        "line": node.lineno,
                        "default": False
                    })
    
    return exports


def extract_python_assignments(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract variable assignments from Python AST for data flow analysis."""
    import os
    assignments = []
    actual_tree = tree.get("tree")
    
    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        print(f"[AST_DEBUG] extract_python_assignments called", file=sys.stderr)
    
    if not actual_tree:
        return assignments
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Assign):
            # Extract target variable(s)
            for target in node.targets:
                target_var = get_node_name(target)
                source_expr = ast.unparse(node.value) if hasattr(ast, "unparse") else str(node.value)
                
                # Find containing function
                in_function = find_containing_function_python(actual_tree, node.lineno)
                
                # CRITICAL FIX: Check if this is a class instantiation
                # BeautifulSoup(html) is ast.Call with func.id = "BeautifulSoup"
                is_instantiation = isinstance(node.value, ast.Call)
                
                assignments.append({
                    "target_var": target_var,
                    "source_expr": source_expr,
                    "line": node.lineno,
                    "in_function": in_function or "global",
                    "source_vars": extract_vars_from_expr(node.value),
                    "is_instantiation": is_instantiation  # Track for taint analysis
                })
        
        elif isinstance(node, ast.AnnAssign) and node.value:
            # Handle annotated assignments (x: int = 5)
            target_var = get_node_name(node.target)
            source_expr = ast.unparse(node.value) if hasattr(ast, "unparse") else str(node.value)
            
            in_function = find_containing_function_python(actual_tree, node.lineno)
            
            assignments.append({
                "target_var": target_var,
                "source_expr": source_expr,
                "line": node.lineno,
                "in_function": in_function or "global",
                "source_vars": extract_vars_from_expr(node.value)
            })

    # CRITICAL FIX: Deduplicate assignments by (line, target_var, in_function)
    # WHY: ast.walk() can visit nodes multiple times if they appear in tree multiple times.
    # Same issue as TypeScript extractor, same solution.
    seen = set()
    deduped = []
    for a in assignments:
        key = (a['line'], a['target_var'], a['in_function'])
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(assignments) != len(deduped):
            print(f"[AST_DEBUG] Python deduplication: {len(assignments)} -> {len(deduped)} assignments ({len(assignments) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_python_function_params(tree: Dict, parser_self) -> Dict[str, List[str]]:
    """Extract function definitions and their parameter names from Python AST."""
    func_params = {}
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return func_params
    
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = [arg.arg for arg in node.args.args]
            func_params[node.name] = params
    
    return func_params


def extract_python_calls_with_args(tree: Dict, function_params: Dict[str, List[str]], parser_self) -> List[Dict[str, Any]]:
    """Extract Python function calls with argument mapping."""
    calls = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return calls
    
    # Find containing function for each call
    function_ranges = {}
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Call):
            func_name = get_node_name(node.func)
            
            # Find caller function
            caller_function = "global"
            for fname, (start, end) in function_ranges.items():
                if start <= node.lineno <= end:
                    caller_function = fname
                    break
            
            # Get callee parameters
            callee_params = function_params.get(func_name.split(".")[-1], [])
            
            # Map arguments to parameters
            for i, arg in enumerate(node.args):
                arg_expr = ast.unparse(arg) if hasattr(ast, "unparse") else str(arg)
                param_name = callee_params[i] if i < len(callee_params) else f"arg{i}"
                
                calls.append({
                    "line": node.lineno,
                    "caller_function": caller_function,
                    "callee_function": func_name,
                    "argument_index": i,
                    "argument_expr": arg_expr,
                    "param_name": param_name
                })
    
    return calls


def extract_python_returns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract return statements from Python AST."""
    returns = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return returns
    
    # First, map all functions
    function_ranges = {}
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)
    
    # Extract return statements
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Return):
            # Find containing function
            function_name = "global"
            for fname, (start, end) in function_ranges.items():
                if start <= node.lineno <= end:
                    function_name = fname
                    break
            
            # Extract return expression
            if node.value:
                return_expr = ast.unparse(node.value) if hasattr(ast, "unparse") else str(node.value)
                return_vars = extract_vars_from_expr(node.value)
            else:
                return_expr = "None"
                return_vars = []
            
            returns.append({
                "function_name": function_name,
                "line": node.lineno,
                "return_expr": return_expr,
                "return_vars": return_vars
            })

    # CRITICAL FIX: Deduplicate returns by (line, function_name)
    # WHY: ast.walk() can visit nodes multiple times
    # NOTE: PRIMARY KEY is (file, line, function_name) but file is added by orchestrator
    seen = set()
    deduped = []
    for r in returns:
        key = (r['line'], r['function_name'])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(returns) != len(deduped):
            print(f"[AST_DEBUG] Python returns deduplication: {len(returns)} -> {len(deduped)} ({len(returns) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


# Python doesn't have property accesses in the same way as JS
# This is a placeholder for consistency
def extract_python_properties(tree: Dict, parser_self) -> List[Dict]:
    """Extract property accesses from Python AST.

    In Python, these would be attribute accesses.
    Currently returns empty list for consistency.
    """
    return []


def extract_python_dicts(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract dict literal structures from Python AST.

    This is the centralized, correct implementation for dict literal extraction.
    Extracts patterns like:
    - {'key': value}
    - {'key': func_ref}
    - {**spread_dict}

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of dict property records matching object_literals schema
    """
    object_literals = []
    actual_tree = tree.get("tree")

    if not actual_tree or not isinstance(actual_tree, ast.Module):
        return object_literals

    # Build function ranges for scope detection
    function_ranges = {}
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, (start, end) in function_ranges.items():
            if start <= line_no <= end:
                return fname
        return "global"

    def extract_dict_properties(dict_node, variable_name, line_no):
        """Extract properties from a dict node."""
        records = []
        in_function = find_containing_function(line_no)

        # Handle dict with explicit keys
        if dict_node.keys:
            for i, (key, value) in enumerate(zip(dict_node.keys, dict_node.values)):
                # Skip None keys (these are **spread operations)
                if key is None:
                    # This is a dict unpacking: {**other_dict}
                    spread_name = get_node_name(value)
                    records.append({
                        "line": line_no,
                        "variable_name": variable_name,
                        "property_name": "**spread",
                        "property_value": spread_name,
                        "property_type": "spread",
                        "nested_level": 0,
                        "in_function": in_function
                    })
                    continue

                # Extract key name
                property_name = None
                if isinstance(key, ast.Constant):
                    property_name = str(key.value)
                elif isinstance(key, ast.Str):  # Python 3.7 compat
                    property_name = key.s
                elif isinstance(key, ast.Name):
                    property_name = key.id
                else:
                    property_name = get_node_name(key) or f"<key_{i}>"

                # Extract value
                property_value = ""
                property_type = "value"

                if isinstance(value, ast.Name):
                    # Variable reference (could be function)
                    property_value = value.id
                    property_type = "function_ref"
                elif isinstance(value, (ast.Lambda, ast.FunctionDef)):
                    # Function/lambda
                    property_value = "<lambda>" if isinstance(value, ast.Lambda) else value.name
                    property_type = "function"
                elif isinstance(value, ast.Constant):
                    property_value = str(value.value)[:250]
                    property_type = "literal"
                elif isinstance(value, ast.Str):  # Python 3.7
                    property_value = value.s[:250]
                    property_type = "literal"
                elif isinstance(value, ast.Dict):
                    property_value = "{...}"
                    property_type = "object"
                elif isinstance(value, ast.List):
                    property_value = "[...]"
                    property_type = "array"
                else:
                    # Complex expression
                    property_value = ast.unparse(value)[:250] if hasattr(ast, "unparse") else str(value)[:250]
                    property_type = "expression"

                records.append({
                    "line": line_no,
                    "variable_name": variable_name,
                    "property_name": property_name,
                    "property_value": property_value,
                    "property_type": property_type,
                    "nested_level": 0,
                    "in_function": in_function
                })

        return records

    # Traverse AST to find all dict literals
    for node in ast.walk(actual_tree):
        # Pattern 1: Variable assignment with dict
        # x = {'key': 'value'}
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(node.value, ast.Dict):
                    var_name = get_node_name(target)
                    records = extract_dict_properties(node.value, var_name, node.lineno)
                    object_literals.extend(records)

        # Pattern 2: Return statement with dict
        # return {'key': 'value'}
        elif isinstance(node, ast.Return):
            if node.value and isinstance(node.value, ast.Dict):
                var_name = f"<return_dict_line_{node.lineno}>"
                records = extract_dict_properties(node.value, var_name, node.lineno)
                object_literals.extend(records)

        # Pattern 3: Function call arguments with dict
        # func({'key': 'value'})
        elif isinstance(node, ast.Call):
            for i, arg in enumerate(node.args):
                if isinstance(arg, ast.Dict):
                    var_name = f"<arg_dict_line_{arg.lineno}>"
                    records = extract_dict_properties(arg, var_name, arg.lineno)
                    object_literals.extend(records)

        # Pattern 4: List elements with dict
        # [{'key': 'value'}]
        elif isinstance(node, ast.List):
            for elem in node.elts:
                if isinstance(elem, ast.Dict) and hasattr(elem, 'lineno'):
                    var_name = f"<list_dict_line_{elem.lineno}>"
                    records = extract_dict_properties(elem, var_name, elem.lineno)
                    object_literals.extend(records)

    return object_literals


def extract_python_cfg(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract control flow graphs for all Python functions.

    Returns CFG data matching the database schema expectations.
    """
    cfg_data = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return cfg_data

    # Find all functions and methods
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_cfg = build_python_function_cfg(node)
            if function_cfg:
                cfg_data.append(function_cfg)

    return cfg_data


def build_python_function_cfg(func_node: ast.FunctionDef) -> Dict[str, Any]:
    """Build control flow graph for a single Python function.

    Args:
        func_node: Function AST node

    Returns:
        CFG data dictionary
    """
    blocks = []
    edges = []
    block_id_counter = [0]  # Use list to allow mutation in nested function

    def get_next_block_id():
        block_id_counter[0] += 1
        return block_id_counter[0]

    # Entry block
    entry_block_id = get_next_block_id()
    blocks.append({
        'id': entry_block_id,
        'type': 'entry',
        'start_line': func_node.lineno,
        'end_line': func_node.lineno,
        'statements': []
    })

    # Process function body
    current_block_id = entry_block_id
    exit_block_id = None

    for stmt in func_node.body:
        block_info = process_python_statement(stmt, current_block_id, get_next_block_id)

        if block_info:
            new_blocks, new_edges, next_block_id = block_info
            blocks.extend(new_blocks)
            edges.extend(new_edges)
            current_block_id = next_block_id

    # Exit block
    if current_block_id:
        exit_block_id = get_next_block_id()
        blocks.append({
            'id': exit_block_id,
            'type': 'exit',
            'start_line': func_node.end_lineno or func_node.lineno,
            'end_line': func_node.end_lineno or func_node.lineno,
            'statements': []
        })
        edges.append({
            'source': current_block_id,
            'target': exit_block_id,
            'type': 'normal'
        })

    return {
        'function_name': func_node.name,
        'blocks': blocks,
        'edges': edges
    }


def process_python_statement(stmt: ast.stmt, current_block_id: int,
                            get_next_block_id) -> Optional[tuple]:
    """Process a statement and update CFG.

    Args:
        stmt: Statement AST node
        current_block_id: Current block ID
        get_next_block_id: Function to get next block ID

    Returns:
        Tuple of (new_blocks, new_edges, next_block_id) or None
    """
    blocks = []
    edges = []

    if isinstance(stmt, ast.If):
        # Create condition block
        condition_block_id = get_next_block_id()
        blocks.append({
            'id': condition_block_id,
            'type': 'condition',
            'start_line': stmt.lineno,
            'end_line': stmt.lineno,
            'condition': ast.unparse(stmt.test) if hasattr(ast, 'unparse') else 'condition',
            'statements': [{'type': 'if', 'line': stmt.lineno}]
        })

        # Connect current to condition
        edges.append({
            'source': current_block_id,
            'target': condition_block_id,
            'type': 'normal'
        })

        # Then branch
        then_block_id = get_next_block_id()
        blocks.append({
            'id': then_block_id,
            'type': 'basic',
            'start_line': stmt.body[0].lineno if stmt.body else stmt.lineno,
            'end_line': stmt.body[-1].end_lineno if stmt.body and hasattr(stmt.body[-1], 'end_lineno') else stmt.lineno,
            'statements': [{'type': 'statement', 'line': s.lineno} for s in stmt.body]
        })
        edges.append({
            'source': condition_block_id,
            'target': then_block_id,
            'type': 'true'
        })

        # Else branch (if exists)
        if stmt.orelse:
            else_block_id = get_next_block_id()
            blocks.append({
                'id': else_block_id,
                'type': 'basic',
                'start_line': stmt.orelse[0].lineno if stmt.orelse else stmt.lineno,
                'end_line': stmt.orelse[-1].end_lineno if stmt.orelse and hasattr(stmt.orelse[-1], 'end_lineno') else stmt.lineno,
                'statements': [{'type': 'statement', 'line': s.lineno} for s in stmt.orelse]
            })
            edges.append({
                'source': condition_block_id,
                'target': else_block_id,
                'type': 'false'
            })

            # Merge point
            merge_block_id = get_next_block_id()
            blocks.append({
                'id': merge_block_id,
                'type': 'merge',
                'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'statements': []
            })
            edges.append({'source': then_block_id, 'target': merge_block_id, 'type': 'normal'})
            edges.append({'source': else_block_id, 'target': merge_block_id, 'type': 'normal'})

            return blocks, edges, merge_block_id
        else:
            # No else branch - false goes to next block
            next_block_id = get_next_block_id()
            blocks.append({
                'id': next_block_id,
                'type': 'merge',
                'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'statements': []
            })
            edges.append({'source': condition_block_id, 'target': next_block_id, 'type': 'false'})
            edges.append({'source': then_block_id, 'target': next_block_id, 'type': 'normal'})

            return blocks, edges, next_block_id

    elif isinstance(stmt, (ast.While, ast.For)):
        # Loop condition block
        loop_block_id = get_next_block_id()
        blocks.append({
            'id': loop_block_id,
            'type': 'loop_condition',
            'start_line': stmt.lineno,
            'end_line': stmt.lineno,
            'condition': ast.unparse(stmt.test if isinstance(stmt, ast.While) else stmt.iter) if hasattr(ast, 'unparse') else 'loop',
            'statements': [{'type': 'while' if isinstance(stmt, ast.While) else 'for', 'line': stmt.lineno}]
        })
        edges.append({'source': current_block_id, 'target': loop_block_id, 'type': 'normal'})

        # Loop body
        body_block_id = get_next_block_id()
        blocks.append({
            'id': body_block_id,
            'type': 'loop_body',
            'start_line': stmt.body[0].lineno if stmt.body else stmt.lineno,
            'end_line': stmt.body[-1].end_lineno if stmt.body and hasattr(stmt.body[-1], 'end_lineno') else stmt.lineno,
            'statements': [{'type': 'statement', 'line': s.lineno} for s in stmt.body]
        })
        edges.append({'source': loop_block_id, 'target': body_block_id, 'type': 'true'})
        edges.append({'source': body_block_id, 'target': loop_block_id, 'type': 'back_edge'})

        # Exit from loop
        exit_block_id = get_next_block_id()
        blocks.append({
            'id': exit_block_id,
            'type': 'merge',
            'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
            'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
            'statements': []
        })
        edges.append({'source': loop_block_id, 'target': exit_block_id, 'type': 'false'})

        return blocks, edges, exit_block_id

    elif isinstance(stmt, ast.Return):
        # Return statement - no successors
        return_block_id = get_next_block_id()
        blocks.append({
            'id': return_block_id,
            'type': 'return',
            'start_line': stmt.lineno,
            'end_line': stmt.lineno,
            'statements': [{'type': 'return', 'line': stmt.lineno}]
        })
        edges.append({'source': current_block_id, 'target': return_block_id, 'type': 'normal'})

        return blocks, edges, None  # No successor after return

    elif isinstance(stmt, ast.Try):
        # Try-except block
        try_block_id = get_next_block_id()
        blocks.append({
            'id': try_block_id,
            'type': 'try',
            'start_line': stmt.lineno,
            'end_line': stmt.body[-1].end_lineno if stmt.body and hasattr(stmt.body[-1], 'end_lineno') else stmt.lineno,
            'statements': [{'type': 'try', 'line': stmt.lineno}]
        })
        edges.append({'source': current_block_id, 'target': try_block_id, 'type': 'normal'})

        # Exception handlers
        handler_ids = []
        for handler in stmt.handlers:
            handler_block_id = get_next_block_id()
            blocks.append({
                'id': handler_block_id,
                'type': 'except',
                'start_line': handler.lineno,
                'end_line': handler.body[-1].end_lineno if handler.body and hasattr(handler.body[-1], 'end_lineno') else handler.lineno,
                'statements': [{'type': 'except', 'line': handler.lineno}]
            })
            edges.append({'source': try_block_id, 'target': handler_block_id, 'type': 'exception'})
            handler_ids.append(handler_block_id)

        # Finally block (if exists)
        if stmt.finalbody:
            finally_block_id = get_next_block_id()
            blocks.append({
                'id': finally_block_id,
                'type': 'finally',
                'start_line': stmt.finalbody[0].lineno,
                'end_line': stmt.finalbody[-1].end_lineno if hasattr(stmt.finalbody[-1], 'end_lineno') else stmt.finalbody[0].lineno,
                'statements': [{'type': 'finally', 'line': stmt.finalbody[0].lineno}]
            })

            # All paths lead to finally
            edges.append({'source': try_block_id, 'target': finally_block_id, 'type': 'normal'})
            for handler_id in handler_ids:
                edges.append({'source': handler_id, 'target': finally_block_id, 'type': 'normal'})

            return blocks, edges, finally_block_id
        else:
            # Merge after exception handling
            merge_block_id = get_next_block_id()
            blocks.append({
                'id': merge_block_id,
                'type': 'merge',
                'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'statements': []
            })
            edges.append({'source': try_block_id, 'target': merge_block_id, 'type': 'normal'})
            for handler_id in handler_ids:
                edges.append({'source': handler_id, 'target': merge_block_id, 'type': 'normal'})

            return blocks, edges, merge_block_id

    # Default: basic statement, no branching
    return None
