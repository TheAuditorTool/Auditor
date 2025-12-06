"""Validation and serialization framework extractors."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext

from ..base import get_node_name


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


def extract_pydantic_validators(context: FileContext) -> list[dict]:
    """Extract Pydantic validator metadata."""
    validators: list[dict[str, Any]] = []
    if not isinstance(context.tree, ast.AST):
        return validators

    for node in context.tree.body if isinstance(context.tree, ast.Module) else []:
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
                    validators.append(
                        {
                            "line": stmt.lineno,
                            "model_name": node.name,
                            "field_name": None,
                            "validator_method": stmt.name,
                            "validator_type": "root",
                        }
                    )
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
                        validators.append(
                            {
                                "line": stmt.lineno,
                                "model_name": node.name,
                                "field_name": field,
                                "validator_method": stmt.name,
                                "validator_type": "field",
                            }
                        )

    return validators


def extract_marshmallow_schemas(context: FileContext) -> list[dict[str, Any]]:
    """Extract Marshmallow schema definitions."""
    schemas = []
    if not isinstance(context.tree, ast.AST):
        return schemas

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [get_node_name(base) for base in node.bases]
        is_marshmallow_schema = any(
            base.endswith("Schema") and base not in ["BaseModel", "Model", "APIView"]
            for base in base_names
        )

        if not is_marshmallow_schema:
            continue

        schema_class_name = node.name
        field_count = 0
        has_nested_schemas = False
        has_custom_validators = False
        validators = []

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                        field_type_name = get_node_name(item.value.func)

                        if (
                            "marshmallow" in field_type_name
                            or "ma." in field_type_name
                            or "fields." in field_type_name
                        ):
                            field_count += 1

                            if "Nested" in field_type_name:
                                has_nested_schemas = True

            elif isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    dec_name = get_node_name(decorator)
                    if "validates" in dec_name:
                        has_custom_validators = True

                        validator_type = "field"
                        if "validates_schema" in dec_name:
                            validator_type = "schema"
                        elif (
                            "pre_load" in dec_name
                            or "post_load" in dec_name
                            or "pre_dump" in dec_name
                            or "post_dump" in dec_name
                        ):
                            validator_type = "hook"
                        validators.append({"name": item.name, "type": validator_type})
                        break

        schemas.append(
            {
                "line": node.lineno,
                "schema_class_name": schema_class_name,
                "field_count": field_count,
                "has_nested_schemas": has_nested_schemas,
                "has_custom_validators": has_custom_validators,
                "validators": validators,
            }
        )

    return schemas


def extract_marshmallow_fields(context: FileContext) -> list[dict[str, Any]]:
    """Extract Marshmallow field definitions from schemas."""
    fields = []
    if not isinstance(context.tree, ast.AST):
        return fields

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [get_node_name(base) for base in node.bases]
        is_marshmallow_schema = any(
            base.endswith("Schema") and base not in ["BaseModel", "Model", "APIView"]
            for base in base_names
        )

        if not is_marshmallow_schema:
            continue

        schema_class_name = node.name

        field_validators = set()
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                for decorator in item.decorator_list:
                    if isinstance(decorator, ast.Call):
                        dec_name = get_node_name(decorator.func)
                        if dec_name == "validates" and decorator.args:
                            field_name_arg = _get_str_constant(decorator.args[0])
                            if field_name_arg:
                                field_validators.add(field_name_arg)

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)

                            if not (
                                "marshmallow" in field_type_name
                                or "ma." in field_type_name
                                or "fields." in field_type_name
                            ):
                                continue

                            field_type = field_type_name.split(".")[-1]

                            required = False
                            allow_none = False
                            has_validate = False

                            for keyword in item.value.keywords:
                                if keyword.arg == "required":
                                    if isinstance(keyword.value, ast.Constant):
                                        required = bool(keyword.value.value)
                                elif keyword.arg == "allow_none":
                                    if isinstance(keyword.value, ast.Constant):
                                        allow_none = bool(keyword.value.value)
                                elif keyword.arg == "validate":
                                    has_validate = True

                            has_custom_validator = field_name in field_validators

                            fields.append(
                                {
                                    "line": item.lineno,
                                    "schema_class_name": schema_class_name,
                                    "field_name": field_name,
                                    "field_type": field_type,
                                    "required": required,
                                    "allow_none": allow_none,
                                    "has_validate": has_validate,
                                    "has_custom_validator": has_custom_validator,
                                }
                            )

    return fields


def extract_drf_serializers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django REST Framework serializer definitions."""
    serializers_list = []
    if not isinstance(context.tree, ast.AST):
        return serializers_list

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [get_node_name(base) for base in node.bases]
        is_drf_serializer = any(
            base.endswith("Serializer")
            and ("serializers" in base or base in ["Serializer", "ModelSerializer"])
            for base in base_names
        )

        if not is_drf_serializer:
            continue

        serializer_class_name = node.name
        field_count = 0
        is_model_serializer = any("ModelSerializer" in base for base in base_names)
        has_meta_model = False
        has_read_only_fields = False
        has_custom_validators = False
        validators = []

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                        field_type_name = get_node_name(item.value.func)

                        if "serializers." in field_type_name or "Field" in field_type_name:
                            field_count += 1

            elif isinstance(item, ast.ClassDef) and item.name == "Meta":
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name):
                                if target.id == "model":
                                    has_meta_model = True
                                elif target.id == "read_only_fields":
                                    has_read_only_fields = True

            elif isinstance(item, ast.FunctionDef) and item.name.startswith("validate_"):
                has_custom_validators = True

                validator_type = "object" if item.name == "validate" else "field"
                validators.append({"name": item.name, "type": validator_type})

        serializers_list.append(
            {
                "line": node.lineno,
                "serializer_class_name": serializer_class_name,
                "field_count": field_count,
                "is_model_serializer": is_model_serializer,
                "has_meta_model": has_meta_model,
                "has_read_only_fields": has_read_only_fields,
                "has_custom_validators": has_custom_validators,
                "validators": validators,
            }
        )

    return serializers_list


def extract_drf_serializer_fields(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django REST Framework field definitions from serializers."""
    fields = []
    if not isinstance(context.tree, ast.AST):
        return fields

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [get_node_name(base) for base in node.bases]
        is_drf_serializer = any(
            base.endswith("Serializer")
            and ("serializers" in base or base in ["Serializer", "ModelSerializer"])
            for base in base_names
        )

        if not is_drf_serializer:
            continue

        serializer_class_name = node.name

        field_validators = set()
        for item in node.body:
            if (
                isinstance(item, ast.FunctionDef)
                and item.name.startswith("validate_")
                and item.name != "validate"
            ):
                field_name = item.name[9:]
                field_validators.add(field_name)

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)

                            if not (
                                "serializers." in field_type_name
                                or "Field" in field_type_name
                                or field_type_name
                                in [
                                    "CharField",
                                    "IntegerField",
                                    "EmailField",
                                    "BooleanField",
                                    "DateField",
                                    "DateTimeField",
                                    "SerializerMethodField",
                                    "PrimaryKeyRelatedField",
                                ]
                            ):
                                continue

                            field_type = field_type_name.split(".")[-1]

                            read_only = False
                            write_only = False
                            required = False
                            allow_null = False
                            has_source = False

                            for keyword in item.value.keywords:
                                if keyword.arg == "read_only":
                                    if isinstance(keyword.value, ast.Constant):
                                        read_only = bool(keyword.value.value)
                                elif keyword.arg == "write_only":
                                    if isinstance(keyword.value, ast.Constant):
                                        write_only = bool(keyword.value.value)
                                elif keyword.arg == "required":
                                    if isinstance(keyword.value, ast.Constant):
                                        required = bool(keyword.value.value)
                                elif keyword.arg == "allow_null":
                                    if isinstance(keyword.value, ast.Constant):
                                        allow_null = bool(keyword.value.value)
                                elif keyword.arg == "source":
                                    has_source = True

                            has_custom_validator = field_name in field_validators

                            fields.append(
                                {
                                    "line": item.lineno,
                                    "serializer_class_name": serializer_class_name,
                                    "field_name": field_name,
                                    "field_type": field_type,
                                    "read_only": read_only,
                                    "write_only": write_only,
                                    "required": required,
                                    "allow_null": allow_null,
                                    "has_source": has_source,
                                    "has_custom_validator": has_custom_validator,
                                }
                            )

    return fields


def extract_wtforms_forms(context: FileContext) -> list[dict[str, Any]]:
    """Extract WTForms form definitions."""
    forms_list = []
    if not isinstance(context.tree, ast.AST):
        return forms_list

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [get_node_name(base) for base in node.bases]
        is_wtforms_form = any(
            base.endswith("Form")
            and ("wtforms" in base or "flask_wtf" in base or base in ["Form", "FlaskForm"])
            for base in base_names
        )

        if not is_wtforms_form:
            continue

        form_class_name = node.name
        field_count = 0
        has_custom_validators = False
        validators = []

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                        field_type_name = get_node_name(item.value.func)

                        if "Field" in field_type_name and (
                            "wtforms" in field_type_name
                            or field_type_name
                            in [
                                "StringField",
                                "IntegerField",
                                "PasswordField",
                                "BooleanField",
                                "TextAreaField",
                                "SelectField",
                                "DateField",
                                "DateTimeField",
                                "FileField",
                                "DecimalField",
                                "FloatField",
                                "SubmitField",
                            ]
                        ):
                            field_count += 1

            elif isinstance(item, ast.FunctionDef) and item.name.startswith("validate_"):
                has_custom_validators = True
                validators.append({"name": item.name, "type": "field"})

        forms_list.append(
            {
                "line": node.lineno,
                "form_class_name": form_class_name,
                "field_count": field_count,
                "has_custom_validators": has_custom_validators,
                "validators": validators,
            }
        )

    return forms_list


def extract_wtforms_fields(context: FileContext) -> list[dict[str, Any]]:
    """Extract WTForms field definitions from forms."""
    fields = []
    if not isinstance(context.tree, ast.AST):
        return fields

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = [get_node_name(base) for base in node.bases]
        is_wtforms_form = any(
            base.endswith("Form")
            and ("wtforms" in base or "flask_wtf" in base or base in ["Form", "FlaskForm"])
            for base in base_names
        )

        if not is_wtforms_form:
            continue

        form_class_name = node.name

        field_validators = set()
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("validate_"):
                field_name = item.name[9:]
                field_validators.add(field_name)

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)

                            if not (
                                "Field" in field_type_name
                                and (
                                    "wtforms" in field_type_name
                                    or field_type_name
                                    in [
                                        "StringField",
                                        "IntegerField",
                                        "PasswordField",
                                        "BooleanField",
                                        "TextAreaField",
                                        "SelectField",
                                        "DateField",
                                        "DateTimeField",
                                        "FileField",
                                        "DecimalField",
                                        "FloatField",
                                        "SubmitField",
                                        "EmailField",
                                        "URLField",
                                        "TelField",
                                    ]
                                )
                            ):
                                continue

                            field_type = field_type_name.split(".")[-1]

                            has_validators = False
                            for keyword in item.value.keywords:
                                if keyword.arg == "validators":
                                    has_validators = True
                                    break

                            has_custom_validator = field_name in field_validators

                            fields.append(
                                {
                                    "line": item.lineno,
                                    "form_class_name": form_class_name,
                                    "field_name": field_name,
                                    "field_type": field_type,
                                    "has_validators": has_validators,
                                    "has_custom_validator": has_custom_validator,
                                }
                            )

    return fields
