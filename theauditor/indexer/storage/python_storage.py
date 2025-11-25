"""Python storage handlers for framework-specific patterns.

This module contains handlers for Python frameworks and patterns:
- ORM: sqlalchemy, django models, fields
- HTTP: flask routes, django views
- Validation: pydantic validators
- Decorators: general Python decorators
- Django: views, middleware

CONSOLIDATION NOTE (2025-11-25):
This file was reduced from 148 handlers to 7 handlers. 141 orphan handlers
(handlers for tables with zero consumers) were deleted. See openspec change
'consolidate-python-orphan-tables' for full rationale and verification.

Note: python_package_configs is stored via generic_batches in python_database.py,
not here - that's why we have 7 handlers for 8 Python tables.

Handler Count: 7
"""


import json
import os
import sys
from typing import List, Dict, Any
from .base import BaseStorage


class PythonStorage(BaseStorage):
    """Python-specific storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        self.handlers = {
            # ORM - consumers: overfetch.py, discovery.py, schema_cache_adapter.py
            'python_orm_models': self._store_python_orm_models,
            'python_orm_fields': self._store_python_orm_fields,

            # Routes - consumers: boundary_analyzer.py, deadcode_graph.py, query.py
            'python_routes': self._store_python_routes,

            # Validators - consumers: discovery.py (via SchemaMemoryCache)
            'python_validators': self._store_python_validators,

            # Decorators - consumers: interceptors.py, deadcode_graph.py, query.py
            'python_decorators': self._store_python_decorators,

            # Django - consumers: interceptors.py
            'python_django_views': self._store_python_django_views,
            'python_django_middleware': self._store_python_django_middleware,
        }

    def _store_python_orm_models(self, file_path: str, python_orm_models: list, jsx_pass: bool):
        """Store Python ORM models."""
        for model in python_orm_models:
            self.db_manager.add_python_orm_model(
                file_path,
                model.get('line', 0),
                model.get('model_name', ''),
                model.get('table_name'),
                model.get('orm_type', 'sqlalchemy')
            )
            if 'python_orm_models' not in self.counts:
                self.counts['python_orm_models'] = 0
            self.counts['python_orm_models'] += 1

    def _store_python_orm_fields(self, file_path: str, python_orm_fields: list, jsx_pass: bool):
        """Store Python ORM fields."""
        for field in python_orm_fields:
            self.db_manager.add_python_orm_field(
                file_path,
                field.get('line', 0),
                field.get('model_name', ''),
                field.get('field_name', ''),
                field.get('field_type'),
                field.get('is_primary_key', False),
                field.get('is_foreign_key', False),
                field.get('foreign_key_target')
            )
            if 'python_orm_fields' not in self.counts:
                self.counts['python_orm_fields'] = 0
            self.counts['python_orm_fields'] += 1

    def _store_python_routes(self, file_path: str, python_routes: list, jsx_pass: bool):
        """Store Python routes."""
        for route in python_routes:
            self.db_manager.add_python_route(
                file_path,
                route.get('line'),
                route.get('framework', ''),
                route.get('method', ''),
                route.get('pattern', ''),
                route.get('handler_function', ''),
                route.get('has_auth', False),
                route.get('dependencies'),
                route.get('blueprint')
            )
            if 'python_routes' not in self.counts:
                self.counts['python_routes'] = 0
            self.counts['python_routes'] += 1

    def _store_python_validators(self, file_path: str, python_validators: list, jsx_pass: bool):
        """Store Python validators."""
        for validator in python_validators:
            self.db_manager.add_python_validator(
                file_path,
                validator.get('line', 0),
                validator.get('model_name', ''),
                validator.get('field_name'),
                validator.get('validator_method', ''),
                validator.get('validator_type', '')
            )
            if 'python_validators' not in self.counts:
                self.counts['python_validators'] = 0
            self.counts['python_validators'] += 1

    def _store_python_decorators(self, file_path: str, python_decorators: list, jsx_pass: bool):
        """Store Python decorators."""
        for decorator in python_decorators:
            self.db_manager.add_python_decorator(
                file_path,
                decorator.get('line', 0),
                decorator.get('decorator_name', ''),
                decorator.get('decorator_type', ''),
                decorator.get('target_type', ''),
                decorator.get('target_name', ''),
                decorator.get('is_async', False)
            )
            if 'python_decorators' not in self.counts:
                self.counts['python_decorators'] = 0
            self.counts['python_decorators'] += 1

    def _store_python_django_views(self, file_path: str, python_django_views: list, jsx_pass: bool):
        """Store Python Django views."""
        for django_view in python_django_views:
            self.db_manager.add_python_django_view(
                file_path,
                django_view.get('line', 0),
                django_view.get('view_class_name', ''),
                django_view.get('view_type', ''),
                django_view.get('base_view_class'),
                django_view.get('model_name'),
                django_view.get('template_name'),
                django_view.get('has_permission_check', False),
                django_view.get('http_method_names'),
                django_view.get('has_get_queryset_override', False)
            )
            if 'python_django_views' not in self.counts:
                self.counts['python_django_views'] = 0
            self.counts['python_django_views'] += 1

    def _store_python_django_middleware(self, file_path: str, python_django_middleware: list, jsx_pass: bool):
        """Store Python Django middleware."""
        for django_middleware in python_django_middleware:
            self.db_manager.add_python_django_middleware(
                file_path,
                django_middleware.get('line', 0),
                django_middleware.get('middleware_class_name', ''),
                django_middleware.get('has_process_request', False),
                django_middleware.get('has_process_response', False),
                django_middleware.get('has_process_exception', False),
                django_middleware.get('has_process_view', False),
                django_middleware.get('has_process_template_response', False)
            )
            if 'python_django_middleware' not in self.counts:
                self.counts['python_django_middleware'] = 0
            self.counts['python_django_middleware'] += 1
