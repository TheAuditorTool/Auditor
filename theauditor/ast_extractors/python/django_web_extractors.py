"""Django web framework extractors (non-ORM patterns)."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext

from ..base import get_node_name

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


def _extract_list_of_strings(node) -> str | None:
    """Helper: Extract list/tuple of string constants as comma-separated string."""
    items = []

    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                items.append(elt.value)
            elif isinstance(elt, ast.Name):
                items.append(elt.id)

    return ",".join(items) if items else None


def extract_django_cbvs(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django Class-Based View definitions."""
    cbvs = []
    if not isinstance(context.tree, ast.AST):
        return cbvs

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

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

        has_permission_check = False
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                dec_func_name = get_node_name(decorator.func)
                if "method_decorator" in dec_func_name:
                    is_dispatch = False
                    for keyword in decorator.keywords:
                        if keyword.arg == "name":
                            name_value = _get_str_constant(keyword.value)
                            if name_value == "dispatch":
                                is_dispatch = True
                                break

                    if is_dispatch and decorator.args:
                        first_arg = decorator.args[0]

                        if isinstance(first_arg, ast.Name):
                            first_arg_name = get_node_name(first_arg)
                            if any(
                                perm in first_arg_name
                                for perm in ["permission", "login_required", "staff_member"]
                            ):
                                has_permission_check = True
                                break

                        elif isinstance(first_arg, ast.List):
                            for elt in first_arg.elts:
                                elt_name = get_node_name(elt)
                                if any(
                                    perm in elt_name
                                    for perm in ["permission", "login_required", "staff_member"]
                                ):
                                    has_permission_check = True
                                    break

                        elif isinstance(first_arg, ast.Call):
                            func_name = get_node_name(first_arg.func)
                            if any(
                                perm in func_name
                                for perm in ["permission", "login_required", "staff_member"]
                            ):
                                has_permission_check = True
                                break
            if has_permission_check:
                break

        model_name = None
        template_name = None
        http_method_names = None
        has_get_queryset_override = False

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "model":
                            model_name = get_node_name(item.value)
                        elif target.id == "template_name":
                            template_name = _get_str_constant(item.value)
                        elif target.id == "http_method_names" and isinstance(item.value, ast.List):
                            methods = []
                            for elt in item.value.elts:
                                method = _get_str_constant(elt)
                                if method:
                                    methods.append(method)
                            http_method_names = ",".join(methods)

            elif isinstance(item, ast.FunctionDef):
                if item.name == "dispatch":
                    for decorator in item.decorator_list:
                        dec_name = get_node_name(decorator)
                        if any(
                            perm in dec_name
                            for perm in [
                                "permission",
                                "login_required",
                                "staff_member",
                                "method_decorator",
                            ]
                        ):
                            has_permission_check = True
                            break

                elif item.name == "get_queryset":
                    has_get_queryset_override = True

        cbvs.append(
            {
                "line": node.lineno,
                "view_class_name": node.name,
                "view_type": view_type,
                "base_view_class": base_view_class,
                "model_name": model_name,
                "template_name": template_name,
                "has_permission_check": has_permission_check,
                "http_method_names": http_method_names,
                "has_get_queryset_override": has_get_queryset_override,
            }
        )

    return cbvs


def extract_django_forms(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django Form and ModelForm definitions."""
    forms = []
    if not isinstance(context.tree, ast.AST):
        return forms

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [get_node_name(base) for base in node.bases]
        is_form = any("Form" in base for base in base_names)
        if not is_form:
            continue

        is_model_form = any("ModelForm" in base for base in base_names)
        model_name = None
        field_count = 0
        has_custom_clean = False

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                        field_type_name = get_node_name(item.value.func)
                        if "Field" in field_type_name:
                            field_count += 1

            elif isinstance(item, ast.ClassDef) and item.name == "Meta":
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == "model":
                                model_name = get_node_name(meta_item.value)

            elif isinstance(item, ast.FunctionDef) and (
                item.name == "clean" or item.name.startswith("clean_")
            ):
                has_custom_clean = True

        forms.append(
            {
                "line": node.lineno,
                "form_class_name": node.name,
                "is_model_form": is_model_form,
                "model_name": model_name,
                "field_count": field_count,
                "has_custom_clean": has_custom_clean,
            }
        )

    return forms


def extract_django_form_fields(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django form field definitions."""
    fields = []
    if not isinstance(context.tree, ast.AST):
        return fields

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [get_node_name(base) for base in node.bases]
        is_form = any("Form" in base for base in base_names)
        if not is_form:
            continue

        form_class_name = node.name

        custom_validators = set()
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("clean_"):
                field_name = item.name[6:]
                custom_validators.add(field_name)

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)
                            if "Field" not in field_type_name:
                                continue

                            field_type = field_type_name.split(".")[-1]

                            required = True
                            max_length = None

                            for keyword in item.value.keywords:
                                if keyword.arg == "required":
                                    if isinstance(keyword.value, ast.Constant):
                                        required = bool(keyword.value.value)
                                elif keyword.arg == "max_length" and isinstance(
                                    keyword.value, ast.Constant
                                ):
                                    max_length = keyword.value.value

                            has_custom_validator = field_name in custom_validators

                            fields.append(
                                {
                                    "line": item.lineno,
                                    "form_class_name": form_class_name,
                                    "field_name": field_name,
                                    "field_type": field_type,
                                    "required": required,
                                    "max_length": max_length,
                                    "has_custom_validator": has_custom_validator,
                                }
                            )

    return fields


def extract_django_admin(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django ModelAdmin customizations."""
    admins = []
    if not isinstance(context.tree, ast.AST):
        return admins

    register_calls = {}

    for node in context.find_nodes(ast.Call):
        func_name = get_node_name(node.func)
        if "register" in func_name and len(node.args) >= 2:
            model_arg = get_node_name(node.args[0])
            admin_class_arg = get_node_name(node.args[1])
            if admin_class_arg:
                register_calls[admin_class_arg] = model_arg

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [get_node_name(base) for base in node.bases]
        is_model_admin = any(
            "ModelAdmin" in base or "admin.ModelAdmin" in base for base in base_names
        )
        if not is_model_admin:
            continue

        admin_class_name = node.name
        model_name = register_calls.get(admin_class_name)

        if not model_name:
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    dec_func_name = get_node_name(decorator.func)
                    if "register" in dec_func_name and decorator.args:
                        model_name = get_node_name(decorator.args[0])
                        break

        list_display = None
        list_filter = None
        search_fields = None
        readonly_fields = None
        has_custom_actions = False

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id

                        if attr_name == "list_display":
                            list_display = _extract_list_of_strings(item.value)
                        elif attr_name == "list_filter":
                            list_filter = _extract_list_of_strings(item.value)
                        elif attr_name == "search_fields":
                            search_fields = _extract_list_of_strings(item.value)
                        elif attr_name == "readonly_fields":
                            readonly_fields = _extract_list_of_strings(item.value)
                        elif attr_name == "actions" and not (
                            isinstance(item.value, ast.Constant) and item.value.value is None
                        ):
                            has_custom_actions = True

            elif isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    dec_name = get_node_name(decorator)
                    if "action" in dec_name:
                        has_custom_actions = True

        admins.append(
            {
                "line": node.lineno,
                "admin_class_name": admin_class_name,
                "model_name": model_name,
                "list_display": list_display,
                "list_filter": list_filter,
                "search_fields": search_fields,
                "readonly_fields": readonly_fields,
                "has_custom_actions": has_custom_actions,
            }
        )

    return admins


def extract_django_middleware(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django middleware class definitions."""
    middlewares = []
    if not isinstance(context.tree, ast.AST):
        return middlewares

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [get_node_name(base) for base in node.bases]
        is_middleware = any("Middleware" in base for base in base_names)

        has_init = False
        has_call = False
        has_process_request = False
        has_process_response = False
        has_process_exception = False
        has_process_view = False
        has_process_template_response = False

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name == "__init__":
                    has_init = True
                elif item.name == "__call__":
                    has_call = True
                elif item.name == "process_request":
                    has_process_request = True
                elif item.name == "process_response":
                    has_process_response = True
                elif item.name == "process_exception":
                    has_process_exception = True
                elif item.name == "process_view":
                    has_process_view = True
                elif item.name == "process_template_response":
                    has_process_template_response = True

        has_any_process_method = (
            has_process_request
            or has_process_response
            or has_process_exception
            or has_process_view
            or has_process_template_response
        )

        is_callable_middleware = has_init and has_call
        is_likely_middleware = is_middleware or is_callable_middleware or has_any_process_method

        if not is_likely_middleware:
            continue

        middlewares.append(
            {
                "line": node.lineno,
                "middleware_class_name": node.name,
                "has_process_request": has_process_request,
                "has_process_response": has_process_response,
                "has_process_exception": has_process_exception,
                "has_process_view": has_process_view,
                "has_process_template_response": has_process_template_response,
            }
        )

    return middlewares
