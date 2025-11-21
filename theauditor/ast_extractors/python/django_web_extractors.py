"""Django web framework extractors (non-ORM patterns).

This module extracts Django-specific web patterns:
- Class-Based Views (CBVs): ListView, DetailView, CreateView, UpdateView, DeleteView, etc.
- Forms: Django Form and ModelForm definitions with field validation
- Admin: ModelAdmin customizations (list_display, list_filter, search_fields, etc.)
- Middleware: Middleware class definitions and hooks

ARCHITECTURAL CONTRACT:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'view_class_name', 'form_class_name', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
"""
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
from typing import Any, Dict, List, Optional, Tuple, Set

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Django CBV Type Mapping
# ============================================================================

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


# ============================================================================
# Helper Functions (Internal - Duplicated for Self-Containment)
# ============================================================================

def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes.

    Internal helper - duplicated across framework extractor files for self-containment.
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return node.value
    return None


def _keyword_arg(call: ast.Call, name: str) -> ast.AST | None:
    """Fetch keyword argument by name from AST call.

    Internal helper - duplicated across framework extractor files for self-containment.
    """
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _extract_list_of_strings(node) -> str | None:
    """Helper: Extract list/tuple of string constants as comma-separated string.

    Internal helper - duplicated across framework extractor files for self-containment.
    """
    items = []

    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                items.append(elt.value)
            elif isinstance(elt, ast.Name):
                items.append(elt.id)

    return ','.join(items) if items else None


# ============================================================================
# Django Web Extractors
# ============================================================================

def extract_django_cbvs(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return cbvs

    for node in context.walk_tree():
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


def extract_django_forms(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return forms

    for node in context.walk_tree():
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


def extract_django_form_fields(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return fields

    for node in context.walk_tree():
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


def extract_django_admin(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return admins

    # Track admin registrations to link ModelAdmin to models
    register_calls = {}  # {admin_class_name: model_name}

    # First pass: Find admin.site.register(Model, ModelAdmin) calls
    for node in context.find_nodes(ast.Call):
        func_name = get_node_name(node.func)
        if 'register' in func_name and len(node.args) >= 2:
            # admin.site.register(Article, ArticleAdmin)
            model_arg = get_node_name(node.args[0])
            admin_class_arg = get_node_name(node.args[1])
            if admin_class_arg:
                register_calls[admin_class_arg] = model_arg

    # Second pass: Extract ModelAdmin classes and check for @admin.register() decorators
    for node in context.walk_tree():
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


def extract_django_middleware(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return middlewares

    for node in context.walk_tree():
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
