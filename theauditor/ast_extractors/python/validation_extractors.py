"""Validation and serialization framework extractors.

This module extracts input validation and data serialization patterns:
- Pydantic: BaseModel validators (@validator, @root_validator)
- Marshmallow: Schema definitions and field validations
- Django REST Framework: Serializers and field definitions
- WTForms: Form definitions and field validators

ARCHITECTURAL CONTRACT:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'model_name', 'field_name', etc.
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
# Validation Framework Extractors
# ============================================================================

def extract_pydantic_validators(context: FileContext) -> list[dict]:
    """Extract Pydantic validator metadata."""
    validators: list[dict[str, Any]] = []
    context.tree = tree.get("tree")
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


def extract_marshmallow_schemas(context: FileContext) -> list[dict[str, Any]]:
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
    context.tree = tree.get("tree")
    if not isinstance(context.tree, ast.AST):
        return schemas

    for node in context.walk_tree():
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


def extract_marshmallow_fields(context: FileContext) -> list[dict[str, Any]]:
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
    context.tree = tree.get("tree")
    if not isinstance(context.tree, ast.AST):
        return fields

    for node in context.walk_tree():
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


def extract_drf_serializers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django REST Framework serializer definitions.

    Detects:
    - Serializer class definitions (inherit from serializers.Serializer or serializers.ModelSerializer)
    - Field count (validation surface area)
    - ModelSerializer detection (has Meta.model)
    - read_only_fields in Meta
    - Custom validators (validate_<field> methods)

    Security relevance:
    - Serializers without validators = incomplete input validation
    - Missing read_only_fields = mass assignment vulnerabilities
    - ModelSerializer without field restrictions = over-exposure (parity with Express/Prisma)
    """
    serializers_list = []
    context.tree = tree.get("tree")
    if not isinstance(context.tree, ast.AST):
        return serializers_list

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if inherits from DRF Serializer
        # Handles: Serializer, ModelSerializer, serializers.Serializer, rest_framework.serializers.Serializer
        base_names = [get_node_name(base) for base in node.bases]
        is_drf_serializer = any(
            base.endswith('Serializer') and ('serializers' in base or base in ['Serializer', 'ModelSerializer'])
            for base in base_names
        )

        if not is_drf_serializer:
            continue

        serializer_class_name = node.name
        field_count = 0
        is_model_serializer = any('ModelSerializer' in base for base in base_names)
        has_meta_model = False
        has_read_only_fields = False
        has_custom_validators = False

        # Scan class body for fields, Meta, and validators
        for item in node.body:
            # Count field assignments (serializers.CharField(), serializers.IntegerField(), etc.)
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Check if value is a DRF field
                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)
                            # Check for serializers.Field patterns
                            if ('serializers.' in field_type_name or 'Field' in field_type_name):
                                field_count += 1

            # Check for Meta class
            elif isinstance(item, ast.ClassDef) and item.name == 'Meta':
                for meta_item in item.body:
                    # Check for model = ... in Meta
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name):
                                if target.id == 'model':
                                    has_meta_model = True
                                elif target.id == 'read_only_fields':
                                    has_read_only_fields = True

            # Check for validator methods (validate_<field>)
            elif isinstance(item, ast.FunctionDef):
                if item.name.startswith('validate_'):
                    has_custom_validators = True

        serializers_list.append({
            "line": node.lineno,
            "serializer_class_name": serializer_class_name,
            "field_count": field_count,
            "is_model_serializer": is_model_serializer,
            "has_meta_model": has_meta_model,
            "has_read_only_fields": has_read_only_fields,
            "has_custom_validators": has_custom_validators,
        })

    return serializers_list


def extract_drf_serializer_fields(context: FileContext) -> list[dict[str, Any]]:
    """Extract Django REST Framework field definitions from serializers.

    Detects:
    - Field types (CharField, IntegerField, EmailField, SerializerMethodField, etc.)
    - read_only flag (read_only=True)
    - write_only flag (write_only=True)
    - required flag (required=True/False)
    - allow_null flag (allow_null=True)
    - source parameter (source='other_field')
    - Custom validators (validate_<field> methods)

    Security relevance:
    - Fields without read_only = mass assignment risk
    - write_only without validation = incomplete input sanitization
    - allow_null without validation = null pointer issues
    - Missing required= = optional input bypass (parity with Joi.required())
    """
    fields = []
    context.tree = tree.get("tree")
    if not isinstance(context.tree, ast.AST):
        return fields

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if this is a DRF serializer
        base_names = [get_node_name(base) for base in node.bases]
        is_drf_serializer = any(
            base.endswith('Serializer') and ('serializers' in base or base in ['Serializer', 'ModelSerializer'])
            for base in base_names
        )

        if not is_drf_serializer:
            continue

        serializer_class_name = node.name

        # Collect validator methods (validate_<field>)
        field_validators = set()
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name.startswith('validate_') and item.name != 'validate':
                    # Extract field name from validate_<field_name>
                    field_name = item.name[9:]  # Remove 'validate_' prefix
                    field_validators.add(field_name)

        # Extract field definitions
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        # Check if value is a DRF field
                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)

                            # Skip if not a DRF field
                            if not ('serializers.' in field_type_name or
                                   'Field' in field_type_name or
                                   field_type_name in ['CharField', 'IntegerField', 'EmailField',
                                                      'BooleanField', 'DateField', 'DateTimeField',
                                                      'SerializerMethodField', 'PrimaryKeyRelatedField']):
                                continue

                            # Extract field type (CharField, IntegerField, etc.)
                            field_type = field_type_name.split('.')[-1]

                            # Extract keyword arguments
                            read_only = False
                            write_only = False
                            required = False
                            allow_null = False
                            has_source = False

                            for keyword in item.value.keywords:
                                if keyword.arg == 'read_only':
                                    if isinstance(keyword.value, ast.Constant):
                                        read_only = bool(keyword.value.value)
                                elif keyword.arg == 'write_only':
                                    if isinstance(keyword.value, ast.Constant):
                                        write_only = bool(keyword.value.value)
                                elif keyword.arg == 'required':
                                    if isinstance(keyword.value, ast.Constant):
                                        required = bool(keyword.value.value)
                                elif keyword.arg == 'allow_null':
                                    if isinstance(keyword.value, ast.Constant):
                                        allow_null = bool(keyword.value.value)
                                elif keyword.arg == 'source':
                                    has_source = True

                            # Check if field has custom validator method
                            has_custom_validator = field_name in field_validators

                            fields.append({
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
                            })

    return fields


def extract_wtforms_forms(context: FileContext) -> list[dict[str, Any]]:
    """Extract WTForms form definitions.

    Detects:
    - Form class definitions (inherit from Form or FlaskForm)
    - Field count (validation surface area)
    - Custom validators (validate_<field> methods)

    Security relevance:
    - Forms without validators = incomplete input validation
    - Missing validators on sensitive fields = injection vulnerabilities
    - Flask-WTF CSRF protection when using FlaskForm (parity with DRF)
    """
    forms_list = []
    context.tree = tree.get("tree")
    if not isinstance(context.tree, ast.AST):
        return forms_list

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if inherits from WTForms Form
        # Handles: Form, FlaskForm, wtforms.Form, flask_wtf.FlaskForm
        base_names = [get_node_name(base) for base in node.bases]
        is_wtforms_form = any(
            base.endswith('Form') and ('wtforms' in base or 'flask_wtf' in base or base in ['Form', 'FlaskForm'])
            for base in base_names
        )

        if not is_wtforms_form:
            continue

        form_class_name = node.name
        field_count = 0
        has_custom_validators = False

        # Scan class body for fields and validators
        for item in node.body:
            # Count field assignments (StringField(), IntegerField(), etc.)
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Check if value is a WTForms field
                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)
                            # Check for wtforms.Field patterns
                            if ('Field' in field_type_name and
                                ('wtforms' in field_type_name or
                                 field_type_name in ['StringField', 'IntegerField', 'PasswordField',
                                                    'BooleanField', 'TextAreaField', 'SelectField',
                                                    'DateField', 'DateTimeField', 'FileField',
                                                    'DecimalField', 'FloatField', 'SubmitField'])):
                                field_count += 1

            # Check for validator methods (validate_<field>)
            elif isinstance(item, ast.FunctionDef):
                if item.name.startswith('validate_'):
                    has_custom_validators = True

        forms_list.append({
            "line": node.lineno,
            "form_class_name": form_class_name,
            "field_count": field_count,
            "has_custom_validators": has_custom_validators,
        })

    return forms_list


def extract_wtforms_fields(context: FileContext) -> list[dict[str, Any]]:
    """Extract WTForms field definitions from forms.

    Detects:
    - Field types (StringField, IntegerField, PasswordField, etc.)
    - Has validators (validators=[...] keyword argument)
    - Custom validators (validate_<field> methods)

    Security relevance:
    - Fields without validators = missing input validation
    - PasswordField without validators = weak password policy
    - Missing DataRequired = optional input bypass (parity with DRF required=True)
    """
    fields = []
    context.tree = tree.get("tree")
    if not isinstance(context.tree, ast.AST):
        return fields

    for node in context.walk_tree():
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if this is a WTForms form
        base_names = [get_node_name(base) for base in node.bases]
        is_wtforms_form = any(
            base.endswith('Form') and ('wtforms' in base or 'flask_wtf' in base or base in ['Form', 'FlaskForm'])
            for base in base_names
        )

        if not is_wtforms_form:
            continue

        form_class_name = node.name

        # Collect validator methods (validate_<field>)
        field_validators = set()
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name.startswith('validate_'):
                    # Extract field name from validate_<field_name>
                    field_name = item.name[9:]  # Remove 'validate_' prefix
                    field_validators.add(field_name)

        # Extract field definitions
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        # Check if value is a WTForms field
                        if isinstance(item.value, ast.Call):
                            field_type_name = get_node_name(item.value.func)

                            # Skip if not a WTForms field
                            if not ('Field' in field_type_name and
                                   ('wtforms' in field_type_name or
                                    field_type_name in ['StringField', 'IntegerField', 'PasswordField',
                                                       'BooleanField', 'TextAreaField', 'SelectField',
                                                       'DateField', 'DateTimeField', 'FileField',
                                                       'DecimalField', 'FloatField', 'SubmitField',
                                                       'EmailField', 'URLField', 'TelField'])):
                                continue

                            # Extract field type (StringField, IntegerField, etc.)
                            field_type = field_type_name.split('.')[-1]

                            # Check for validators keyword argument
                            has_validators = False
                            for keyword in item.value.keywords:
                                if keyword.arg == 'validators':
                                    has_validators = True
                                    break

                            # Check if field has custom validator method
                            has_custom_validator = field_name in field_validators

                            fields.append({
                                "line": item.lineno,
                                "form_class_name": form_class_name,
                                "field_name": field_name,
                                "field_type": field_type,
                                "has_validators": has_validators,
                                "has_custom_validator": has_custom_validator,
                            })

    return fields
