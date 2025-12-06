"""ORM framework extractors - SQLAlchemy and Django ORM."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext

from ..base import get_node_name

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


def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _keyword_arg(call: ast.Call, name: str) -> ast.AST | None:
    """Fetch keyword argument by name from AST call."""
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _get_bool_constant(node: ast.AST | None) -> bool | None:
    """Return boolean value for constant/literal nodes."""
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
    return None


def _cascade_implies_delete(value: str | None) -> bool:
    """Return True when cascade configuration includes delete semantics."""
    if not value:
        return False
    normalized = value.lower()
    return "delete" in normalized or "remove" in normalized


def _extract_backref_name(backref_value: ast.AST) -> str | None:
    """Extract string name from backref keyword (string or sqlalchemy.orm.backref)."""
    name = _get_str_constant(backref_value)
    if name:
        return name

    if isinstance(backref_value, ast.Call) and backref_value.args:
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


def _infer_relationship_type(attr_name: str, relationship_call: ast.Call) -> str:
    """Infer relationship type using heuristics (uselist, secondary, naming)."""

    if _keyword_arg(relationship_call, "secondary"):
        return "manyToMany"

    uselist_arg = _keyword_arg(relationship_call, "uselist")
    uselist = _get_bool_constant(uselist_arg)

    if uselist is False:
        return "hasOne"

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

    return rel_type


def _is_truthy(node: ast.AST | None) -> bool:
    """Check if AST node represents a truthy value."""
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.Constant):
        return bool(node.value)
    return False


def _get_type_annotation(node: ast.AST | None) -> str | None:
    """Convert an annotation AST node into source text."""
    if node is None:
        return None
    try:
        if hasattr(ast, "unparse"):
            return ast.unparse(node)
    except Exception:
        pass
    return None


def extract_sqlalchemy_definitions(
    context: FileContext,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Extract SQLAlchemy ORM models, fields, and relationships."""
    models: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    seen_relationships: set[tuple[int, str, str, str]] = set()

    if not isinstance(context.tree, ast.AST):
        return models, fields, relationships

    for node in context.tree.body if isinstance(context.tree, ast.Module) else []:
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = {get_node_name(base) for base in node.bases}
        if not any(
            name in SQLALCHEMY_BASE_IDENTIFIERS or name.endswith("Base") or name.endswith("Model")
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

        models.append(
            {
                "model_name": node.name,
                "line": node.lineno,
                "table_name": table_name,
                "orm_type": "sqlalchemy",
            }
        )

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
                            foreign_key_target = _get_str_constant(arg.args[0]) or get_node_name(
                                arg.args[0]
                            )

                fk_kw = _keyword_arg(value, "ForeignKey")
                if fk_kw:
                    is_foreign_key = True
                    foreign_key_target = _get_str_constant(fk_kw) or get_node_name(fk_kw)

                fields.append(
                    {
                        "model_name": node.name,
                        "field_name": attr_name,
                        "line": line_no,
                        "field_type": field_type,
                        "is_primary_key": is_primary_key,
                        "is_foreign_key": is_foreign_key,
                        "foreign_key_target": foreign_key_target,
                    }
                )
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
                    if isinstance(foreign_keys_kw, (ast.List, ast.Tuple)) and getattr(
                        foreign_keys_kw, "elts", None
                    ):
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
                    target_model_name: str | None,
                    rel_type: str,
                    alias: str | None,
                    cascade_flag: bool,
                    fk_name: str | None,
                    rel_line: int,
                ) -> None:
                    target_name = target_model_name or "Unknown"

                    key = (rel_line, source_model, target_name, rel_type)
                    if key in seen_relationships:
                        return
                    relationships.append(
                        {
                            "line": rel_line,
                            "source_model": source_model,
                            "target_model": target_name,
                            "relationship_type": rel_type,
                            "foreign_key": fk_name,
                            "cascade_delete": cascade_flag,
                            "as_name": alias,
                        }
                    )
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

                backref_node = _keyword_arg(value, "backref")
                if backref_node and target_model and target_model != node.name:
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


def extract_django_definitions(context: FileContext) -> tuple[list[dict], list[dict]]:
    """Extract Django ORM models and relationships."""
    relationships: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    seen_relationships: set[tuple[int, str, str, str]] = set()

    if not isinstance(context.tree, ast.AST):
        return models, relationships

    for node in context.tree.body if isinstance(context.tree, ast.Module) else []:
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = {get_node_name(base) for base in node.bases}
        if not any(name in DJANGO_MODEL_BASES for name in base_names):
            continue

        models.append(
            {
                "model_name": node.name,
                "line": node.lineno,
                "table_name": None,
                "orm_type": "django",
            }
        )

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

                rel_key = (line_no, node.name, target or "Unknown", "belongsTo")
                if rel_key not in seen_relationships:
                    relationships.append(
                        {
                            "line": line_no,
                            "source_model": node.name,
                            "target_model": target or "Unknown",
                            "relationship_type": "belongsTo",
                            "foreign_key": attr_name,
                            "cascade_delete": cascade,
                            "as_name": attr_name,
                        }
                    )
                    seen_relationships.add(rel_key)
            elif func_name.endswith("ManyToManyField"):
                target = None
                if value.args:
                    target = _get_str_constant(value.args[0]) or get_node_name(value.args[0])

                rel_key = (line_no, node.name, target or "Unknown", "manyToMany")
                if rel_key not in seen_relationships:
                    relationships.append(
                        {
                            "line": line_no,
                            "source_model": node.name,
                            "target_model": target or "Unknown",
                            "relationship_type": "manyToMany",
                            "foreign_key": None,
                            "cascade_delete": False,
                            "as_name": attr_name,
                        }
                    )
                    seen_relationships.add(rel_key)
            elif func_name.endswith("OneToOneField"):
                target = None
                if value.args:
                    target = _get_str_constant(value.args[0]) or get_node_name(value.args[0])

                rel_key = (line_no, node.name, target or "Unknown", "hasOne")
                if rel_key not in seen_relationships:
                    relationships.append(
                        {
                            "line": line_no,
                            "source_model": node.name,
                            "target_model": target or "Unknown",
                            "relationship_type": "hasOne",
                            "foreign_key": attr_name,
                            "cascade_delete": False,
                            "as_name": attr_name,
                        }
                    )
                    seen_relationships.add(rel_key)

    return models, relationships


def extract_flask_blueprints(context: FileContext) -> list[dict]:
    """Detect Flask blueprint declarations."""
    blueprints: list[dict[str, Any]] = []
    if not isinstance(context.tree, ast.AST):
        return blueprints

    for node in context.find_nodes(ast.Assign):
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
        blueprints.append(
            {
                "line": getattr(node, "lineno", 0),
                "blueprint_name": blueprint_name,
                "url_prefix": url_prefix,
                "subdomain": subdomain,
            }
        )

    return blueprints
