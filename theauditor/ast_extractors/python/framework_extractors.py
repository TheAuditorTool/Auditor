"""Framework extractors - Backward-compatible facade."""

from .django_web_extractors import (
    extract_django_admin,
    extract_django_cbvs,
    extract_django_form_fields,
    extract_django_forms,
    extract_django_middleware,
)
from .orm_extractors import (
    extract_django_definitions,
    extract_flask_blueprints,
    extract_sqlalchemy_definitions,
)
from .task_graphql_extractors import (
    extract_ariadne_resolvers,
    extract_celery_beat_schedules,
    extract_celery_task_calls,
    extract_celery_tasks,
    extract_graphene_resolvers,
    extract_strawberry_resolvers,
)
from .validation_extractors import (
    extract_drf_serializer_fields,
    extract_drf_serializers,
    extract_marshmallow_fields,
    extract_marshmallow_schemas,
    extract_pydantic_validators,
    extract_wtforms_fields,
    extract_wtforms_forms,
)

FASTAPI_HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
}


def _extract_fastapi_dependencies(func_node):
    """Collect dependency call targets from FastAPI route parameters."""
    import ast

    from ..base import get_node_name

    dependencies = []

    def _dependency_name(call):
        """Extract dependency target from Depends() call."""
        func_name = get_node_name(call.func)
        if not (func_name.endswith("Depends") or func_name == "Depends"):
            return None

        if call.args:
            return get_node_name(call.args[0])

        for keyword in call.keywords:
            if keyword.arg == "dependency":
                return get_node_name(keyword.value)
        return "Depends"

    positional = list(func_node.args.args)
    defaults = list(func_node.args.defaults)
    pos_defaults_start = len(positional) - len(defaults)

    for idx, _arg in enumerate(positional):
        default = None
        if idx >= pos_defaults_start and defaults:
            default = defaults[idx - pos_defaults_start]
        if isinstance(default, ast.Call):
            dep = _dependency_name(default)
            if dep:
                dependencies.append(dep)

    for _kw_arg, default in zip(func_node.args.kwonlyargs, func_node.args.kw_defaults, strict=True):
        if isinstance(default, ast.Call):
            dep = _dependency_name(default)
            if dep:
                dependencies.append(dep)

    return dependencies


__all__ = [
    "extract_sqlalchemy_definitions",
    "extract_django_definitions",
    "extract_flask_blueprints",
    "extract_pydantic_validators",
    "extract_marshmallow_schemas",
    "extract_marshmallow_fields",
    "extract_drf_serializers",
    "extract_drf_serializer_fields",
    "extract_wtforms_forms",
    "extract_wtforms_fields",
    "extract_django_cbvs",
    "extract_django_forms",
    "extract_django_form_fields",
    "extract_django_admin",
    "extract_django_middleware",
    "extract_celery_tasks",
    "extract_celery_task_calls",
    "extract_celery_beat_schedules",
    "extract_graphene_resolvers",
    "extract_ariadne_resolvers",
    "extract_strawberry_resolvers",
    "FASTAPI_HTTP_METHODS",
    "_extract_fastapi_dependencies",
]
