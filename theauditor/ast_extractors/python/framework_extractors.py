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


# Django CBV type mapping
DJANGO_CBV_TYPES = {
    "ListView": "list",
    "DetailView": "detail",
    "CreateView": "create",
    "UpdateView": "update",
    "DeleteView": "delete",
    "FormView": "form",
    "TemplateView": "template",
    "RedirectView": "redirect",
    "View": "base",
    "ArchiveIndexView": "archive_index",
    "YearArchiveView": "year_archive",
    "MonthArchiveView": "month_archive",
    "WeekArchiveView": "week_archive",
    "DayArchiveView": "day_archive",
    "TodayArchiveView": "today_archive",
    "DateDetailView": "date_detail",
}


def extract_django_cbvs(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract Django Class-Based View definitions.

    Detects:
    - Generic views (ListView, DetailView, CreateView, UpdateView, DeleteView, etc.)
    - Model associations (model = User or queryset = User.objects.all())
    - Permission decorators on dispatch() method
    - get_queryset() overrides (SQL injection surface)
    - http_method_names restrictions
    - template_name attributes

    Security relevance:
    - Missing permission checks = access control bypass
    - get_queryset() overrides = SQL injection surface
    - http_method_names = attack surface enumeration
    """
    cbvs = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return cbvs

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check inheritance from Django CBV classes
        base_names = [get_node_name(base) for base in node.bases]
        view_type = None
        base_view_class = None

        for base_name in base_names:
            for cbv_class, cbv_type in DJANGO_CBV_TYPES.items():
                if base_name == cbv_class or base_name.endswith(f".{cbv_class}"):
                    view_type = cbv_type
                    base_view_class = cbv_class
                    break
            if view_type:
                break

        if not view_type:
            continue

        # Check class-level @method_decorator(..., name='dispatch') for permission checks
        has_permission_check = False
        for decorator in node.decorator_list:
            # Check for @method_decorator(login_required, name='dispatch')
            # Also handles @method_decorator([login_required, permission_required], name='dispatch')
            if isinstance(decorator, ast.Call):
                dec_func_name = get_node_name(decorator.func)
                if 'method_decorator' in dec_func_name:
                    # Check if name='dispatch' keyword argument exists
                    is_dispatch = False
                    for keyword in decorator.keywords:
                        if keyword.arg == 'name':
                            name_value = _get_str_constant(keyword.value)
                            if name_value == 'dispatch':
                                is_dispatch = True
                                break

                    if is_dispatch and decorator.args:
                        first_arg = decorator.args[0]
                        # Handle single decorator: @method_decorator(login_required, name='dispatch')
                        if isinstance(first_arg, ast.Name):
                            first_arg_name = get_node_name(first_arg)
                            if any(perm in first_arg_name for perm in ["permission", "login_required", "staff_member"]):
                                has_permission_check = True
                                break
                        # Handle list of decorators: @method_decorator([login_required, permission_required], name='dispatch')
                        elif isinstance(first_arg, ast.List):
                            for elt in first_arg.elts:
                                elt_name = get_node_name(elt)
                                if any(perm in elt_name for perm in ["permission", "login_required", "staff_member"]):
                                    has_permission_check = True
                                    break
                        # Handle function call: @method_decorator(permission_required('foo'), name='dispatch')
                        elif isinstance(first_arg, ast.Call):
                            func_name = get_node_name(first_arg.func)
                            if any(perm in func_name for perm in ["permission", "login_required", "staff_member"]):
                                has_permission_check = True
                                break
            if has_permission_check:
                break

        # Extract class-level attributes
        model_name = None
        template_name = None
        http_method_names = None
        has_get_queryset_override = False

        for item in node.body:
            # Model assignment: model = User
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "model":
                            model_name = get_node_name(item.value)
                        elif target.id == "template_name":
                            template_name = _get_str_constant(item.value)
                        elif target.id == "http_method_names":
                            # Extract list of allowed methods
                            if isinstance(item.value, ast.List):
                                methods = []
                                for elt in item.value.elts:
                                    method = _get_str_constant(elt)
                                    if method:
                                        methods.append(method)
                                http_method_names = ",".join(methods)

            # Check for dispatch() method with permission decorators
            elif isinstance(item, ast.FunctionDef):
                if item.name == "dispatch":
                    # Check for @permission_required, @login_required, @method_decorator, etc.
                    for decorator in item.decorator_list:
                        dec_name = get_node_name(decorator)
                        if any(perm in dec_name for perm in ["permission", "login_required", "staff_member", "method_decorator"]):
                            has_permission_check = True
                            break

                # Check for get_queryset() override
                elif item.name == "get_queryset":
                    has_get_queryset_override = True

        cbvs.append({
            "line": node.lineno,
            "view_class_name": node.name,
            "view_type": view_type,
            "base_view_class": base_view_class,
            "model_name": model_name,
            "template_name": template_name,
            "has_permission_check": has_permission_check,
            "http_method_names": http_method_names,
            "has_get_queryset_override": has_get_queryset_override,
        })

    return cbvs


def extract_django_forms(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract Django Form and ModelForm definitions.

    Detects:
    - Form and ModelForm class inheritance
    - ModelForm Meta.model associations
    - Field count (for validation surface area)
    - Custom clean() or clean_<field> methods (validators)

    Security relevance:
    - Form fields = input validation surface
    - Missing clean() methods = unvalidated input
    - ModelForm without validators = direct DB write risk
    """
    forms = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return forms

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check inheritance from django.forms.Form or ModelForm
        base_names = [get_node_name(base) for base in node.bases]
        is_form = any('Form' in base for base in base_names)
        if not is_form:
            continue

        is_model_form = any('ModelForm' in base for base in base_names)
        model_name = None
        field_count = 0
        has_custom_clean = False

        # Scan class body
        for item in node.body:
            # Count field assignments (CharField, EmailField, etc.)
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Check if value is a field instantiation
                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)
                            if 'Field' in field_type_name:
                                field_count += 1

            # Check for Meta class (ModelForm)
            elif isinstance(item, ast.ClassDef) and item.name == 'Meta':
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == 'model':
                                model_name = get_node_name(meta_item.value)

            # Check for custom clean methods
            elif isinstance(item, ast.FunctionDef):
                if item.name == 'clean' or item.name.startswith('clean_'):
                    has_custom_clean = True

        forms.append({
            "line": node.lineno,
            "form_class_name": node.name,
            "is_model_form": is_model_form,
            "model_name": model_name,
            "field_count": field_count,
            "has_custom_clean": has_custom_clean,
        })

    return forms


def extract_django_form_fields(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract Django form field definitions.

    Detects:
    - Field types (CharField, EmailField, IntegerField, etc.)
    - required/optional (required=False keyword)
    - max_length constraint
    - Custom validators (clean_<fieldname> methods)

    Security relevance:
    - Fields without max_length = DoS risk (unbounded input)
    - Optional fields without validation = incomplete sanitization
    - Fields without custom validators = missing business logic checks
    """
    fields = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return fields

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if this is a Form class
        base_names = [get_node_name(base) for base in node.bases]
        is_form = any('Form' in base for base in base_names)
        if not is_form:
            continue

        form_class_name = node.name

        # Collect custom validator methods (clean_<field>)
        custom_validators = set()
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith('clean_'):
                field_name = item.name[6:]  # Remove 'clean_' prefix
                custom_validators.add(field_name)

        # Extract field definitions
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        # Check if value is a field instantiation
                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)
                            if not 'Field' in field_type_name:
                                continue

                            # Extract field type (CharField, EmailField, etc.)
                            field_type = field_type_name.split('.')[-1]

                            # Extract keyword arguments
                            required = True  # Default is required
                            max_length = None

                            for keyword in item.value.keywords:
                                if keyword.arg == 'required':
                                    if isinstance(keyword.value, ast.Constant):
                                        required = bool(keyword.value.value)
                                elif keyword.arg == 'max_length':
                                    if isinstance(keyword.value, ast.Constant):
                                        max_length = keyword.value.value

                            has_custom_validator = field_name in custom_validators

                            fields.append({
                                "line": item.lineno,
                                "form_class_name": form_class_name,
                                "field_name": field_name,
                                "field_type": field_type,
                                "required": required,
                                "max_length": max_length,
                                "has_custom_validator": has_custom_validator,
                            })

    return fields


def extract_django_admin(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract Django ModelAdmin customizations.

    Detects:
    - ModelAdmin class registrations
    - Associated model (from admin.site.register or inline Meta)
    - list_display fields (columns shown in admin list view)
    - list_filter fields (filtering sidebar)
    - search_fields (search functionality)
    - readonly_fields (non-editable fields)
    - Custom admin actions (bulk operations)

    Security relevance:
    - Exposed fields in list_display = information disclosure
    - Missing readonly_fields = mass assignment risk
    - Custom actions without permission checks = privilege escalation
    - search_fields without validation = SQL injection
    """
    admins = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return admins

    # Track admin registrations to link ModelAdmin to models
    register_calls = {}  # {admin_class_name: model_name}

    # First pass: Find admin.site.register(Model, ModelAdmin) calls
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Call):
            func_name = get_node_name(node.func)
            if 'register' in func_name and len(node.args) >= 2:
                # admin.site.register(Article, ArticleAdmin)
                model_arg = get_node_name(node.args[0])
                admin_class_arg = get_node_name(node.args[1])
                if admin_class_arg:
                    register_calls[admin_class_arg] = model_arg

    # Second pass: Extract ModelAdmin classes and check for @admin.register() decorators
    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check inheritance from ModelAdmin
        base_names = [get_node_name(base) for base in node.bases]
        is_model_admin = any('ModelAdmin' in base or 'admin.ModelAdmin' in base for base in base_names)
        if not is_model_admin:
            continue

        admin_class_name = node.name
        model_name = register_calls.get(admin_class_name)  # From admin.site.register()

        # Check for @admin.register(Model) decorator pattern
        if not model_name:
            for decorator in node.decorator_list:
                # @admin.register(Article) or @admin.register(Article, site=custom_site)
                if isinstance(decorator, ast.Call):
                    dec_func_name = get_node_name(decorator.func)
                    if 'register' in dec_func_name and decorator.args:
                        # First argument is the model
                        model_name = get_node_name(decorator.args[0])
                        break

        # Extract admin configuration attributes
        list_display = None
        list_filter = None
        search_fields = None
        readonly_fields = None
        has_custom_actions = False

        for item in node.body:
            # Class-level attribute assignments
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id

                        # Extract list/tuple values as comma-separated strings
                        if attr_name == 'list_display':
                            list_display = _extract_list_of_strings(item.value)
                        elif attr_name == 'list_filter':
                            list_filter = _extract_list_of_strings(item.value)
                        elif attr_name == 'search_fields':
                            search_fields = _extract_list_of_strings(item.value)
                        elif attr_name == 'readonly_fields':
                            readonly_fields = _extract_list_of_strings(item.value)
                        elif attr_name == 'actions':
                            # If actions is not None/empty, custom actions exist
                            if not (isinstance(item.value, ast.Constant) and item.value.value is None):
                                has_custom_actions = True

            # Check for custom action methods (decorated with @admin.action or convention name)
            elif isinstance(item, ast.FunctionDef):
                # Custom actions typically have @admin.action decorator or are in actions list
                for decorator in item.decorator_list:
                    dec_name = get_node_name(decorator)
                    if 'action' in dec_name:
                        has_custom_actions = True

        admins.append({
            "line": node.lineno,
            "admin_class_name": admin_class_name,
            "model_name": model_name,
            "list_display": list_display,
            "list_filter": list_filter,
            "search_fields": search_fields,
            "readonly_fields": readonly_fields,
            "has_custom_actions": has_custom_actions,
        })

    return admins


def _extract_list_of_strings(node) -> Optional[str]:
    """Helper: Extract list/tuple of string constants as comma-separated string."""
    items = []

    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                items.append(elt.value)
            elif isinstance(elt, ast.Name):
                items.append(elt.id)

    return ','.join(items) if items else None


def extract_django_middleware(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract Django middleware class definitions.

    Detects:
    - Middleware class definitions (MiddlewareMixin, callable classes)
    - process_request() method (pre-view processing)
    - process_response() method (post-view processing)
    - process_exception() method (exception handling)
    - process_view() method (view-level processing)
    - process_template_response() method (template processing)

    Security relevance:
    - process_request without auth checks = bypass opportunity
    - process_response modifying sensitive data = data leakage
    - process_exception logging = information disclosure
    - Missing middleware hooks = incomplete security layer
    """
    middlewares = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return middlewares

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if this looks like middleware:
        # 1. Inherits from MiddlewareMixin
        # 2. Has __init__ + __call__ (callable middleware)
        # 3. Has process_* methods
        base_names = [get_node_name(base) for base in node.bases]
        is_middleware = any('Middleware' in base for base in base_names)

        # Check for middleware hooks
        has_init = False
        has_call = False
        has_process_request = False
        has_process_response = False
        has_process_exception = False
        has_process_view = False
        has_process_template_response = False

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name == '__init__':
                    has_init = True
                elif item.name == '__call__':
                    has_call = True
                elif item.name == 'process_request':
                    has_process_request = True
                elif item.name == 'process_response':
                    has_process_response = True
                elif item.name == 'process_exception':
                    has_process_exception = True
                elif item.name == 'process_view':
                    has_process_view = True
                elif item.name == 'process_template_response':
                    has_process_template_response = True

        # Consider it middleware if:
        # - Inherits from Middleware* OR
        # - Has __init__ + __call__ (callable middleware pattern) OR
        # - Has any process_* methods
        has_any_process_method = (
            has_process_request or has_process_response or
            has_process_exception or has_process_view or
            has_process_template_response
        )

        is_callable_middleware = has_init and has_call
        is_likely_middleware = is_middleware or is_callable_middleware or has_any_process_method

        if not is_likely_middleware:
            continue

        middlewares.append({
            "line": node.lineno,
            "middleware_class_name": node.name,
            "has_process_request": has_process_request,
            "has_process_response": has_process_response,
            "has_process_exception": has_process_exception,
            "has_process_view": has_process_view,
            "has_process_template_response": has_process_template_response,
        })

    return middlewares


def extract_marshmallow_schemas(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract Marshmallow schema definitions.

    Detects:
    - Schema class definitions (inherit from marshmallow.Schema or ma.Schema)
    - Field count (validation surface area)
    - Has nested schemas (ma.Nested references)
    - Custom validators (@validates, @validates_schema decorators)

    Security relevance:
    - Schemas without validators = incomplete input validation
    - Missing required fields = data integrity issues
    - Nested schemas = complex validation chains (parity with Zod/Joi)
    """
    schemas = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return schemas

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if inherits from marshmallow.Schema
        # Handles: Schema (from marshmallow import Schema), ma.Schema, marshmallow.Schema
        base_names = [get_node_name(base) for base in node.bases]
        is_marshmallow_schema = any(
            base.endswith('Schema') and base not in ['BaseModel', 'Model', 'APIView']
            for base in base_names
        )

        if not is_marshmallow_schema:
            continue

        schema_class_name = node.name
        field_count = 0
        has_nested_schemas = False
        has_custom_validators = False

        # Scan class body for fields and validators
        for item in node.body:
            # Count field assignments (ma.String(), ma.Integer(), etc.)
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Check if value is a Marshmallow field
                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)
                            # Check for marshmallow field types or ma.Field patterns
                            if ('marshmallow' in field_type_name or 'ma.' in field_type_name or
                                'fields.' in field_type_name):
                                field_count += 1

                                # Check for nested schemas
                                if 'Nested' in field_type_name:
                                    has_nested_schemas = True

            # Check for validator decorators
            elif isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    dec_name = get_node_name(decorator)
                    if 'validates' in dec_name:
                        has_custom_validators = True
                        break

        schemas.append({
            "line": node.lineno,
            "schema_class_name": schema_class_name,
            "field_count": field_count,
            "has_nested_schemas": has_nested_schemas,
            "has_custom_validators": has_custom_validators,
        })

    return schemas


def extract_marshmallow_fields(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract Marshmallow field definitions from schemas.

    Detects:
    - Field types (ma.String, ma.Integer, ma.Email, ma.Boolean, ma.Nested, etc.)
    - required flag (required=True)
    - allow_none flag (allow_none=True)
    - Custom validators (validate= keyword)

    Security relevance:
    - Fields without required= validation = optional input bypass
    - allow_none without validation = null pointer issues
    - Missing validate= = incomplete validation (parity with Zod refinements)
    """
    fields = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return fields

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if this is a Marshmallow schema
        # Handles: Schema (from marshmallow import Schema), ma.Schema, marshmallow.Schema
        base_names = [get_node_name(base) for base in node.bases]
        is_marshmallow_schema = any(
            base.endswith('Schema') and base not in ['BaseModel', 'Model', 'APIView']
            for base in base_names
        )

        if not is_marshmallow_schema:
            continue

        schema_class_name = node.name

        # Collect validator methods (validates decorators)
        field_validators = set()
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    # @validates('field_name') or @validates_schema
                    if isinstance(decorator, ast.Call):
                        dec_name = get_node_name(decorator.func)
                        if dec_name == 'validates' and decorator.args:
                            # Extract field name from @validates('field_name')
                            field_name_arg = _get_str_constant(decorator.args[0])
                            if field_name_arg:
                                field_validators.add(field_name_arg)

        # Extract field definitions
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        # Check if value is a Marshmallow field
                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)

                            # Skip if not a marshmallow field
                            if not ('marshmallow' in field_type_name or 'ma.' in field_type_name or
                                   'fields.' in field_type_name):
                                continue

                            # Extract field type (String, Integer, Email, etc.)
                            field_type = field_type_name.split('.')[-1]

                            # Extract keyword arguments
                            required = False
                            allow_none = False
                            has_validate = False

                            for keyword in item.value.keywords:
                                if keyword.arg == 'required':
                                    if isinstance(keyword.value, ast.Constant):
                                        required = bool(keyword.value.value)
                                elif keyword.arg == 'allow_none':
                                    if isinstance(keyword.value, ast.Constant):
                                        allow_none = bool(keyword.value.value)
                                elif keyword.arg == 'validate':
                                    has_validate = True

                            # Check if field has custom validator method
                            has_custom_validator = field_name in field_validators

                            fields.append({
                                "line": item.lineno,
                                "schema_class_name": schema_class_name,
                                "field_name": field_name,
                                "field_type": field_type,
                                "required": required,
                                "allow_none": allow_none,
                                "has_validate": has_validate,
                                "has_custom_validator": has_custom_validator,
                            })

    return fields
