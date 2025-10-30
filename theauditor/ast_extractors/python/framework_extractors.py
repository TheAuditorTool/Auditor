"""Python framework extractors - Web frameworks & ORMs.

This module contains extraction logic for Python web frameworks and ORMs:
- SQLAlchemy ORM (models, fields, relationships)
- Django ORM (models, relationships)
- Flask (blueprints, routes)
- FastAPI (routes, dependencies)
- Pydantic (validators)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
"""

import ast
import logging
from typing import Any, Dict, List, Optional, Tuple, Set

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Framework Detection Constants
# ============================================================================

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


# ============================================================================
# Framework Helper Functions
# ============================================================================

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


# ============================================================================
# Framework Extractors
# ============================================================================

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


# Helper function needed for SQLAlchemy
def _get_type_annotation(node: Optional[ast.AST]) -> Optional[str]:
    """Convert an annotation AST node into source text."""
    if node is None:
        return None
    try:
        if hasattr(ast, "unparse"):
            return ast.unparse(node)
    except Exception:
        pass
    return None


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
