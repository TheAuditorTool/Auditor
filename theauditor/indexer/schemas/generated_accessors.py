# Auto-generated accessor classes from schema
import sqlite3
from typing import Any

from ..schema import build_query


class AngularComponentStylesTable:
    """Accessor class for angular_component_styles table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from angular_component_styles."""
        query = build_query('angular_component_styles', ['file', 'component_name', 'style_path'])
        cursor.execute(query)
        return [dict(zip(['file', 'component_name', 'style_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_component_styles', ['file', 'component_name', 'style_path'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'component_name', 'style_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_name(cursor: sqlite3.Cursor, component_name: str) -> list[dict[str, Any]]:
        """Get rows by component_name."""
        query = build_query('angular_component_styles', ['file', 'component_name', 'style_path'], where="component_name = ?")
        cursor.execute(query, (component_name,))
        return [dict(zip(['file', 'component_name', 'style_path'], row, strict=True)) for row in cursor.fetchall()]


class AngularComponentsTable:
    """Accessor class for angular_components table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from angular_components."""
        query = build_query('angular_components', ['file', 'line', 'component_name', 'selector', 'template_path', 'has_lifecycle_hooks'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'component_name', 'selector', 'template_path', 'has_lifecycle_hooks'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_components', ['file', 'line', 'component_name', 'selector', 'template_path', 'has_lifecycle_hooks'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'component_name', 'selector', 'template_path', 'has_lifecycle_hooks'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_name(cursor: sqlite3.Cursor, component_name: str) -> list[dict[str, Any]]:
        """Get rows by component_name."""
        query = build_query('angular_components', ['file', 'line', 'component_name', 'selector', 'template_path', 'has_lifecycle_hooks'], where="component_name = ?")
        cursor.execute(query, (component_name,))
        return [dict(zip(['file', 'line', 'component_name', 'selector', 'template_path', 'has_lifecycle_hooks'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_selector(cursor: sqlite3.Cursor, selector: str) -> list[dict[str, Any]]:
        """Get rows by selector."""
        query = build_query('angular_components', ['file', 'line', 'component_name', 'selector', 'template_path', 'has_lifecycle_hooks'], where="selector = ?")
        cursor.execute(query, (selector,))
        return [dict(zip(['file', 'line', 'component_name', 'selector', 'template_path', 'has_lifecycle_hooks'], row, strict=True)) for row in cursor.fetchall()]


class AngularGuardsTable:
    """Accessor class for angular_guards table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from angular_guards."""
        query = build_query('angular_guards', ['file', 'line', 'guard_name', 'guard_type', 'implements_interface'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_guards', ['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_guard_name(cursor: sqlite3.Cursor, guard_name: str) -> list[dict[str, Any]]:
        """Get rows by guard_name."""
        query = build_query('angular_guards', ['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], where="guard_name = ?")
        cursor.execute(query, (guard_name,))
        return [dict(zip(['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_guard_type(cursor: sqlite3.Cursor, guard_type: str) -> list[dict[str, Any]]:
        """Get rows by guard_type."""
        query = build_query('angular_guards', ['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], where="guard_type = ?")
        cursor.execute(query, (guard_type,))
        return [dict(zip(['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], row, strict=True)) for row in cursor.fetchall()]


class AngularModuleDeclarationsTable:
    """Accessor class for angular_module_declarations table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from angular_module_declarations."""
        query = build_query('angular_module_declarations', ['file', 'module_name', 'declaration_name', 'declaration_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'module_name', 'declaration_name', 'declaration_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_module_declarations', ['file', 'module_name', 'declaration_name', 'declaration_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'module_name', 'declaration_name', 'declaration_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_name(cursor: sqlite3.Cursor, module_name: str) -> list[dict[str, Any]]:
        """Get rows by module_name."""
        query = build_query('angular_module_declarations', ['file', 'module_name', 'declaration_name', 'declaration_type'], where="module_name = ?")
        cursor.execute(query, (module_name,))
        return [dict(zip(['file', 'module_name', 'declaration_name', 'declaration_type'], row, strict=True)) for row in cursor.fetchall()]


class AngularModuleExportsTable:
    """Accessor class for angular_module_exports table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from angular_module_exports."""
        query = build_query('angular_module_exports', ['file', 'module_name', 'exported_name'])
        cursor.execute(query)
        return [dict(zip(['file', 'module_name', 'exported_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_module_exports', ['file', 'module_name', 'exported_name'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'module_name', 'exported_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_name(cursor: sqlite3.Cursor, module_name: str) -> list[dict[str, Any]]:
        """Get rows by module_name."""
        query = build_query('angular_module_exports', ['file', 'module_name', 'exported_name'], where="module_name = ?")
        cursor.execute(query, (module_name,))
        return [dict(zip(['file', 'module_name', 'exported_name'], row, strict=True)) for row in cursor.fetchall()]


class AngularModuleImportsTable:
    """Accessor class for angular_module_imports table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from angular_module_imports."""
        query = build_query('angular_module_imports', ['file', 'module_name', 'imported_module'])
        cursor.execute(query)
        return [dict(zip(['file', 'module_name', 'imported_module'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_module_imports', ['file', 'module_name', 'imported_module'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'module_name', 'imported_module'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_name(cursor: sqlite3.Cursor, module_name: str) -> list[dict[str, Any]]:
        """Get rows by module_name."""
        query = build_query('angular_module_imports', ['file', 'module_name', 'imported_module'], where="module_name = ?")
        cursor.execute(query, (module_name,))
        return [dict(zip(['file', 'module_name', 'imported_module'], row, strict=True)) for row in cursor.fetchall()]


class AngularModuleProvidersTable:
    """Accessor class for angular_module_providers table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from angular_module_providers."""
        query = build_query('angular_module_providers', ['file', 'module_name', 'provider_name', 'provider_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'module_name', 'provider_name', 'provider_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_module_providers', ['file', 'module_name', 'provider_name', 'provider_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'module_name', 'provider_name', 'provider_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_name(cursor: sqlite3.Cursor, module_name: str) -> list[dict[str, Any]]:
        """Get rows by module_name."""
        query = build_query('angular_module_providers', ['file', 'module_name', 'provider_name', 'provider_type'], where="module_name = ?")
        cursor.execute(query, (module_name,))
        return [dict(zip(['file', 'module_name', 'provider_name', 'provider_type'], row, strict=True)) for row in cursor.fetchall()]


class AngularModulesTable:
    """Accessor class for angular_modules table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from angular_modules."""
        query = build_query('angular_modules', ['file', 'line', 'module_name'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'module_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_modules', ['file', 'line', 'module_name'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'module_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_name(cursor: sqlite3.Cursor, module_name: str) -> list[dict[str, Any]]:
        """Get rows by module_name."""
        query = build_query('angular_modules', ['file', 'line', 'module_name'], where="module_name = ?")
        cursor.execute(query, (module_name,))
        return [dict(zip(['file', 'line', 'module_name'], row, strict=True)) for row in cursor.fetchall()]


class AngularServicesTable:
    """Accessor class for angular_services table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from angular_services."""
        query = build_query('angular_services', ['file', 'line', 'service_name', 'is_injectable', 'provided_in'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'service_name', 'is_injectable', 'provided_in'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_services', ['file', 'line', 'service_name', 'is_injectable', 'provided_in'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'service_name', 'is_injectable', 'provided_in'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_service_name(cursor: sqlite3.Cursor, service_name: str) -> list[dict[str, Any]]:
        """Get rows by service_name."""
        query = build_query('angular_services', ['file', 'line', 'service_name', 'is_injectable', 'provided_in'], where="service_name = ?")
        cursor.execute(query, (service_name,))
        return [dict(zip(['file', 'line', 'service_name', 'is_injectable', 'provided_in'], row, strict=True)) for row in cursor.fetchall()]


class ApiEndpointControlsTable:
    """Accessor class for api_endpoint_controls table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from api_endpoint_controls."""
        query = build_query('api_endpoint_controls', ['id', 'endpoint_file', 'endpoint_line', 'control_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'endpoint_file', 'endpoint_line', 'control_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_control_name(cursor: sqlite3.Cursor, control_name: str) -> list[dict[str, Any]]:
        """Get rows by control_name."""
        query = build_query('api_endpoint_controls', ['id', 'endpoint_file', 'endpoint_line', 'control_name'], where="control_name = ?")
        cursor.execute(query, (control_name,))
        return [dict(zip(['id', 'endpoint_file', 'endpoint_line', 'control_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_endpoint_file(cursor: sqlite3.Cursor, endpoint_file: str) -> list[dict[str, Any]]:
        """Get rows by endpoint_file."""
        query = build_query('api_endpoint_controls', ['id', 'endpoint_file', 'endpoint_line', 'control_name'], where="endpoint_file = ?")
        cursor.execute(query, (endpoint_file,))
        return [dict(zip(['id', 'endpoint_file', 'endpoint_line', 'control_name'], row, strict=True)) for row in cursor.fetchall()]


class ApiEndpointsTable:
    """Accessor class for api_endpoints table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from api_endpoints."""
        query = build_query('api_endpoints', ['file', 'line', 'method', 'pattern', 'path', 'full_path', 'has_auth', 'handler_function'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'method', 'pattern', 'path', 'full_path', 'has_auth', 'handler_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('api_endpoints', ['file', 'line', 'method', 'pattern', 'path', 'full_path', 'has_auth', 'handler_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'method', 'pattern', 'path', 'full_path', 'has_auth', 'handler_function'], row, strict=True)) for row in cursor.fetchall()]


class AssignmentSourceVarsTable:
    """Accessor class for assignment_source_vars table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from assignment_source_vars."""
        query = build_query('assignment_source_vars', ['file', 'line', 'target_var', 'source_var', 'var_index'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'target_var', 'source_var', 'var_index'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_var(cursor: sqlite3.Cursor, source_var: str) -> list[dict[str, Any]]:
        """Get rows by source_var."""
        query = build_query('assignment_source_vars', ['file', 'line', 'target_var', 'source_var', 'var_index'], where="source_var = ?")
        cursor.execute(query, (source_var,))
        return [dict(zip(['file', 'line', 'target_var', 'source_var', 'var_index'], row, strict=True)) for row in cursor.fetchall()]


class AssignmentSourcesTable:
    """Accessor class for assignment_sources table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from assignment_sources."""
        query = build_query('assignment_sources', ['id', 'assignment_file', 'assignment_line', 'assignment_col', 'assignment_target', 'source_var_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_col', 'assignment_target', 'source_var_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_var_name(cursor: sqlite3.Cursor, source_var_name: str) -> list[dict[str, Any]]:
        """Get rows by source_var_name."""
        query = build_query('assignment_sources', ['id', 'assignment_file', 'assignment_line', 'assignment_col', 'assignment_target', 'source_var_name'], where="source_var_name = ?")
        cursor.execute(query, (source_var_name,))
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_col', 'assignment_target', 'source_var_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_assignment_file(cursor: sqlite3.Cursor, assignment_file: str) -> list[dict[str, Any]]:
        """Get rows by assignment_file."""
        query = build_query('assignment_sources', ['id', 'assignment_file', 'assignment_line', 'assignment_col', 'assignment_target', 'source_var_name'], where="assignment_file = ?")
        cursor.execute(query, (assignment_file,))
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_col', 'assignment_target', 'source_var_name'], row, strict=True)) for row in cursor.fetchall()]


class AssignmentSourcesJsxTable:
    """Accessor class for assignment_sources_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from assignment_sources_jsx."""
        query = build_query('assignment_sources_jsx', ['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_var_name(cursor: sqlite3.Cursor, source_var_name: str) -> list[dict[str, Any]]:
        """Get rows by source_var_name."""
        query = build_query('assignment_sources_jsx', ['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'], where="source_var_name = ?")
        cursor.execute(query, (source_var_name,))
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_assignment_file(cursor: sqlite3.Cursor, assignment_file: str) -> list[dict[str, Any]]:
        """Get rows by assignment_file."""
        query = build_query('assignment_sources_jsx', ['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'], where="assignment_file = ?")
        cursor.execute(query, (assignment_file,))
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'], row, strict=True)) for row in cursor.fetchall()]


class AssignmentsTable:
    """Accessor class for assignments table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from assignments."""
        query = build_query('assignments', ['file', 'line', 'col', 'target_var', 'source_expr', 'in_function', 'property_path'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'col', 'target_var', 'source_expr', 'in_function', 'property_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('assignments', ['file', 'line', 'col', 'target_var', 'source_expr', 'in_function', 'property_path'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'col', 'target_var', 'source_expr', 'in_function', 'property_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('assignments', ['file', 'line', 'col', 'target_var', 'source_expr', 'in_function', 'property_path'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['file', 'line', 'col', 'target_var', 'source_expr', 'in_function', 'property_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_var(cursor: sqlite3.Cursor, target_var: str) -> list[dict[str, Any]]:
        """Get rows by target_var."""
        query = build_query('assignments', ['file', 'line', 'col', 'target_var', 'source_expr', 'in_function', 'property_path'], where="target_var = ?")
        cursor.execute(query, (target_var,))
        return [dict(zip(['file', 'line', 'col', 'target_var', 'source_expr', 'in_function', 'property_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_path(cursor: sqlite3.Cursor, property_path: str) -> list[dict[str, Any]]:
        """Get rows by property_path."""
        query = build_query('assignments', ['file', 'line', 'col', 'target_var', 'source_expr', 'in_function', 'property_path'], where="property_path = ?")
        cursor.execute(query, (property_path,))
        return [dict(zip(['file', 'line', 'col', 'target_var', 'source_expr', 'in_function', 'property_path'], row, strict=True)) for row in cursor.fetchall()]


class AssignmentsJsxTable:
    """Accessor class for assignments_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from assignments_jsx."""
        query = build_query('assignments_jsx', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('assignments_jsx', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('assignments_jsx', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_path(cursor: sqlite3.Cursor, property_path: str) -> list[dict[str, Any]]:
        """Get rows by property_path."""
        query = build_query('assignments_jsx', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], where="property_path = ?")
        cursor.execute(query, (property_path,))
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]


class BashCommandArgsTable:
    """Accessor class for bash_command_args table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bash_command_args."""
        query = build_query('bash_command_args', ['file', 'command_line', 'command_pipeline_position', 'arg_index', 'arg_value', 'is_quoted', 'quote_type', 'has_expansion', 'expansion_vars', 'normalized_flags'])
        cursor.execute(query)
        return [dict(zip(['file', 'command_line', 'command_pipeline_position', 'arg_index', 'arg_value', 'is_quoted', 'quote_type', 'has_expansion', 'expansion_vars', 'normalized_flags'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_expansion(cursor: sqlite3.Cursor, has_expansion: int) -> list[dict[str, Any]]:
        """Get rows by has_expansion."""
        query = build_query('bash_command_args', ['file', 'command_line', 'command_pipeline_position', 'arg_index', 'arg_value', 'is_quoted', 'quote_type', 'has_expansion', 'expansion_vars', 'normalized_flags'], where="has_expansion = ?")
        cursor.execute(query, (has_expansion,))
        return [dict(zip(['file', 'command_line', 'command_pipeline_position', 'arg_index', 'arg_value', 'is_quoted', 'quote_type', 'has_expansion', 'expansion_vars', 'normalized_flags'], row, strict=True)) for row in cursor.fetchall()]


class BashCommandsTable:
    """Accessor class for bash_commands table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bash_commands."""
        query = build_query('bash_commands', ['file', 'line', 'command_name', 'pipeline_position', 'containing_function', 'wrapped_command'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'command_name', 'pipeline_position', 'containing_function', 'wrapped_command'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bash_commands', ['file', 'line', 'command_name', 'pipeline_position', 'containing_function', 'wrapped_command'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'command_name', 'pipeline_position', 'containing_function', 'wrapped_command'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_command_name(cursor: sqlite3.Cursor, command_name: str) -> list[dict[str, Any]]:
        """Get rows by command_name."""
        query = build_query('bash_commands', ['file', 'line', 'command_name', 'pipeline_position', 'containing_function', 'wrapped_command'], where="command_name = ?")
        cursor.execute(query, (command_name,))
        return [dict(zip(['file', 'line', 'command_name', 'pipeline_position', 'containing_function', 'wrapped_command'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_wrapped_command(cursor: sqlite3.Cursor, wrapped_command: str) -> list[dict[str, Any]]:
        """Get rows by wrapped_command."""
        query = build_query('bash_commands', ['file', 'line', 'command_name', 'pipeline_position', 'containing_function', 'wrapped_command'], where="wrapped_command = ?")
        cursor.execute(query, (wrapped_command,))
        return [dict(zip(['file', 'line', 'command_name', 'pipeline_position', 'containing_function', 'wrapped_command'], row, strict=True)) for row in cursor.fetchall()]


class BashControlFlowsTable:
    """Accessor class for bash_control_flows table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bash_control_flows."""
        query = build_query('bash_control_flows', ['file', 'line', 'end_line', 'type', 'condition', 'has_else', 'case_value', 'num_patterns', 'loop_variable', 'iterable', 'loop_expression', 'containing_function'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'end_line', 'type', 'condition', 'has_else', 'case_value', 'num_patterns', 'loop_variable', 'iterable', 'loop_expression', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bash_control_flows', ['file', 'line', 'end_line', 'type', 'condition', 'has_else', 'case_value', 'num_patterns', 'loop_variable', 'iterable', 'loop_expression', 'containing_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'end_line', 'type', 'condition', 'has_else', 'case_value', 'num_patterns', 'loop_variable', 'iterable', 'loop_expression', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type(cursor: sqlite3.Cursor, type: str) -> list[dict[str, Any]]:
        """Get rows by type."""
        query = build_query('bash_control_flows', ['file', 'line', 'end_line', 'type', 'condition', 'has_else', 'case_value', 'num_patterns', 'loop_variable', 'iterable', 'loop_expression', 'containing_function'], where="type = ?")
        cursor.execute(query, (type,))
        return [dict(zip(['file', 'line', 'end_line', 'type', 'condition', 'has_else', 'case_value', 'num_patterns', 'loop_variable', 'iterable', 'loop_expression', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]


class BashFunctionsTable:
    """Accessor class for bash_functions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bash_functions."""
        query = build_query('bash_functions', ['file', 'line', 'end_line', 'name', 'style', 'body_start_line', 'body_end_line'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'end_line', 'name', 'style', 'body_start_line', 'body_end_line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bash_functions', ['file', 'line', 'end_line', 'name', 'style', 'body_start_line', 'body_end_line'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'end_line', 'name', 'style', 'body_start_line', 'body_end_line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('bash_functions', ['file', 'line', 'end_line', 'name', 'style', 'body_start_line', 'body_end_line'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'line', 'end_line', 'name', 'style', 'body_start_line', 'body_end_line'], row, strict=True)) for row in cursor.fetchall()]


class BashPipesTable:
    """Accessor class for bash_pipes table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bash_pipes."""
        query = build_query('bash_pipes', ['file', 'line', 'pipeline_id', 'position', 'command_text', 'containing_function'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'pipeline_id', 'position', 'command_text', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bash_pipes', ['file', 'line', 'pipeline_id', 'position', 'command_text', 'containing_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'pipeline_id', 'position', 'command_text', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]


class BashRedirectionsTable:
    """Accessor class for bash_redirections table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bash_redirections."""
        query = build_query('bash_redirections', ['file', 'line', 'direction', 'target', 'fd_number', 'containing_function'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'direction', 'target', 'fd_number', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bash_redirections', ['file', 'line', 'direction', 'target', 'fd_number', 'containing_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'direction', 'target', 'fd_number', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_direction(cursor: sqlite3.Cursor, direction: str) -> list[dict[str, Any]]:
        """Get rows by direction."""
        query = build_query('bash_redirections', ['file', 'line', 'direction', 'target', 'fd_number', 'containing_function'], where="direction = ?")
        cursor.execute(query, (direction,))
        return [dict(zip(['file', 'line', 'direction', 'target', 'fd_number', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]


class BashSetOptionsTable:
    """Accessor class for bash_set_options table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bash_set_options."""
        query = build_query('bash_set_options', ['file', 'line', 'options', 'containing_function'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'options', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bash_set_options', ['file', 'line', 'options', 'containing_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'options', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]


class BashSourcesTable:
    """Accessor class for bash_sources table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bash_sources."""
        query = build_query('bash_sources', ['file', 'line', 'sourced_path', 'syntax', 'has_variable_expansion', 'containing_function'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'sourced_path', 'syntax', 'has_variable_expansion', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bash_sources', ['file', 'line', 'sourced_path', 'syntax', 'has_variable_expansion', 'containing_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'sourced_path', 'syntax', 'has_variable_expansion', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_sourced_path(cursor: sqlite3.Cursor, sourced_path: str) -> list[dict[str, Any]]:
        """Get rows by sourced_path."""
        query = build_query('bash_sources', ['file', 'line', 'sourced_path', 'syntax', 'has_variable_expansion', 'containing_function'], where="sourced_path = ?")
        cursor.execute(query, (sourced_path,))
        return [dict(zip(['file', 'line', 'sourced_path', 'syntax', 'has_variable_expansion', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]


class BashSubshellsTable:
    """Accessor class for bash_subshells table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bash_subshells."""
        query = build_query('bash_subshells', ['file', 'line', 'col', 'syntax', 'command_text', 'capture_target', 'containing_function'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'col', 'syntax', 'command_text', 'capture_target', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bash_subshells', ['file', 'line', 'col', 'syntax', 'command_text', 'capture_target', 'containing_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'col', 'syntax', 'command_text', 'capture_target', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_capture_target(cursor: sqlite3.Cursor, capture_target: str) -> list[dict[str, Any]]:
        """Get rows by capture_target."""
        query = build_query('bash_subshells', ['file', 'line', 'col', 'syntax', 'command_text', 'capture_target', 'containing_function'], where="capture_target = ?")
        cursor.execute(query, (capture_target,))
        return [dict(zip(['file', 'line', 'col', 'syntax', 'command_text', 'capture_target', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]


class BashVariablesTable:
    """Accessor class for bash_variables table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bash_variables."""
        query = build_query('bash_variables', ['file', 'line', 'name', 'scope', 'readonly', 'value_expr', 'containing_function'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'name', 'scope', 'readonly', 'value_expr', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bash_variables', ['file', 'line', 'name', 'scope', 'readonly', 'value_expr', 'containing_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'name', 'scope', 'readonly', 'value_expr', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('bash_variables', ['file', 'line', 'name', 'scope', 'readonly', 'value_expr', 'containing_function'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'line', 'name', 'scope', 'readonly', 'value_expr', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_scope(cursor: sqlite3.Cursor, scope: str) -> list[dict[str, Any]]:
        """Get rows by scope."""
        query = build_query('bash_variables', ['file', 'line', 'name', 'scope', 'readonly', 'value_expr', 'containing_function'], where="scope = ?")
        cursor.execute(query, (scope,))
        return [dict(zip(['file', 'line', 'name', 'scope', 'readonly', 'value_expr', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]


class BullmqQueuesTable:
    """Accessor class for bullmq_queues table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bullmq_queues."""
        query = build_query('bullmq_queues', ['file', 'line', 'queue_name', 'redis_config'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'queue_name', 'redis_config'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bullmq_queues', ['file', 'line', 'queue_name', 'redis_config'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'queue_name', 'redis_config'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_queue_name(cursor: sqlite3.Cursor, queue_name: str) -> list[dict[str, Any]]:
        """Get rows by queue_name."""
        query = build_query('bullmq_queues', ['file', 'line', 'queue_name', 'redis_config'], where="queue_name = ?")
        cursor.execute(query, (queue_name,))
        return [dict(zip(['file', 'line', 'queue_name', 'redis_config'], row, strict=True)) for row in cursor.fetchall()]


class BullmqWorkersTable:
    """Accessor class for bullmq_workers table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from bullmq_workers."""
        query = build_query('bullmq_workers', ['file', 'line', 'queue_name', 'worker_function', 'processor_path'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'queue_name', 'worker_function', 'processor_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bullmq_workers', ['file', 'line', 'queue_name', 'worker_function', 'processor_path'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'queue_name', 'worker_function', 'processor_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_queue_name(cursor: sqlite3.Cursor, queue_name: str) -> list[dict[str, Any]]:
        """Get rows by queue_name."""
        query = build_query('bullmq_workers', ['file', 'line', 'queue_name', 'worker_function', 'processor_path'], where="queue_name = ?")
        cursor.execute(query, (queue_name,))
        return [dict(zip(['file', 'line', 'queue_name', 'worker_function', 'processor_path'], row, strict=True)) for row in cursor.fetchall()]


class CargoDependenciesTable:
    """Accessor class for cargo_dependencies table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cargo_dependencies."""
        query = build_query('cargo_dependencies', ['file_path', 'name', 'version_spec', 'is_dev', 'features'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'name', 'version_spec', 'is_dev', 'features'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('cargo_dependencies', ['file_path', 'name', 'version_spec', 'is_dev', 'features'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'name', 'version_spec', 'is_dev', 'features'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('cargo_dependencies', ['file_path', 'name', 'version_spec', 'is_dev', 'features'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file_path', 'name', 'version_spec', 'is_dev', 'features'], row, strict=True)) for row in cursor.fetchall()]


class CargoPackageConfigsTable:
    """Accessor class for cargo_package_configs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cargo_package_configs."""
        query = build_query('cargo_package_configs', ['file_path', 'package_name', 'package_version', 'edition'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'package_name', 'package_version', 'edition'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_package_name(cursor: sqlite3.Cursor, package_name: str) -> list[dict[str, Any]]:
        """Get rows by package_name."""
        query = build_query('cargo_package_configs', ['file_path', 'package_name', 'package_version', 'edition'], where="package_name = ?")
        cursor.execute(query, (package_name,))
        return [dict(zip(['file_path', 'package_name', 'package_version', 'edition'], row, strict=True)) for row in cursor.fetchall()]


class CdkConstructPropertiesTable:
    """Accessor class for cdk_construct_properties table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cdk_construct_properties."""
        query = build_query('cdk_construct_properties', ['id', 'construct_id', 'property_name', 'property_value_expr', 'line'])
        cursor.execute(query)
        return [dict(zip(['id', 'construct_id', 'property_name', 'property_value_expr', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_construct_id(cursor: sqlite3.Cursor, construct_id: str) -> list[dict[str, Any]]:
        """Get rows by construct_id."""
        query = build_query('cdk_construct_properties', ['id', 'construct_id', 'property_name', 'property_value_expr', 'line'], where="construct_id = ?")
        cursor.execute(query, (construct_id,))
        return [dict(zip(['id', 'construct_id', 'property_name', 'property_value_expr', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_name(cursor: sqlite3.Cursor, property_name: str) -> list[dict[str, Any]]:
        """Get rows by property_name."""
        query = build_query('cdk_construct_properties', ['id', 'construct_id', 'property_name', 'property_value_expr', 'line'], where="property_name = ?")
        cursor.execute(query, (property_name,))
        return [dict(zip(['id', 'construct_id', 'property_name', 'property_value_expr', 'line'], row, strict=True)) for row in cursor.fetchall()]


class CdkConstructsTable:
    """Accessor class for cdk_constructs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cdk_constructs."""
        query = build_query('cdk_constructs', ['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'])
        cursor.execute(query)
        return [dict(zip(['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('cdk_constructs', ['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_cdk_class(cursor: sqlite3.Cursor, cdk_class: str) -> list[dict[str, Any]]:
        """Get rows by cdk_class."""
        query = build_query('cdk_constructs', ['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'], where="cdk_class = ?")
        cursor.execute(query, (cdk_class,))
        return [dict(zip(['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'], row, strict=True)) for row in cursor.fetchall()]


class CdkFindingsTable:
    """Accessor class for cdk_findings table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cdk_findings."""
        query = build_query('cdk_findings', ['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'])
        cursor.execute(query)
        return [dict(zip(['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('cdk_findings', ['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_construct_id(cursor: sqlite3.Cursor, construct_id: str) -> list[dict[str, Any]]:
        """Get rows by construct_id."""
        query = build_query('cdk_findings', ['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], where="construct_id = ?")
        cursor.execute(query, (construct_id,))
        return [dict(zip(['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_severity(cursor: sqlite3.Cursor, severity: str) -> list[dict[str, Any]]:
        """Get rows by severity."""
        query = build_query('cdk_findings', ['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], where="severity = ?")
        cursor.execute(query, (severity,))
        return [dict(zip(['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_category(cursor: sqlite3.Cursor, category: str) -> list[dict[str, Any]]:
        """Get rows by category."""
        query = build_query('cdk_findings', ['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], where="category = ?")
        cursor.execute(query, (category,))
        return [dict(zip(['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], row, strict=True)) for row in cursor.fetchall()]


class CfgBlockStatementsTable:
    """Accessor class for cfg_block_statements table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cfg_block_statements."""
        query = build_query('cfg_block_statements', ['block_id', 'statement_type', 'line', 'statement_text'])
        cursor.execute(query)
        return [dict(zip(['block_id', 'statement_type', 'line', 'statement_text'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_block_id(cursor: sqlite3.Cursor, block_id: int) -> list[dict[str, Any]]:
        """Get rows by block_id."""
        query = build_query('cfg_block_statements', ['block_id', 'statement_type', 'line', 'statement_text'], where="block_id = ?")
        cursor.execute(query, (block_id,))
        return [dict(zip(['block_id', 'statement_type', 'line', 'statement_text'], row, strict=True)) for row in cursor.fetchall()]


class CfgBlockStatementsJsxTable:
    """Accessor class for cfg_block_statements_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cfg_block_statements_jsx."""
        query = build_query('cfg_block_statements_jsx', ['block_id', 'statement_type', 'line', 'statement_text', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['block_id', 'statement_type', 'line', 'statement_text', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_block_id(cursor: sqlite3.Cursor, block_id: int) -> list[dict[str, Any]]:
        """Get rows by block_id."""
        query = build_query('cfg_block_statements_jsx', ['block_id', 'statement_type', 'line', 'statement_text', 'jsx_mode', 'extraction_pass'], where="block_id = ?")
        cursor.execute(query, (block_id,))
        return [dict(zip(['block_id', 'statement_type', 'line', 'statement_text', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]


class CfgBlocksTable:
    """Accessor class for cfg_blocks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cfg_blocks."""
        query = build_query('cfg_blocks', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('cfg_blocks', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> list[dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('cfg_blocks', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'], row, strict=True)) for row in cursor.fetchall()]


class CfgBlocksJsxTable:
    """Accessor class for cfg_blocks_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cfg_blocks_jsx."""
        query = build_query('cfg_blocks_jsx', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('cfg_blocks_jsx', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> list[dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('cfg_blocks_jsx', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]


class CfgEdgesTable:
    """Accessor class for cfg_edges table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cfg_edges."""
        query = build_query('cfg_edges', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('cfg_edges', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> list[dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('cfg_edges', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_block_id(cursor: sqlite3.Cursor, source_block_id: int) -> list[dict[str, Any]]:
        """Get rows by source_block_id."""
        query = build_query('cfg_edges', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], where="source_block_id = ?")
        cursor.execute(query, (source_block_id,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_block_id(cursor: sqlite3.Cursor, target_block_id: int) -> list[dict[str, Any]]:
        """Get rows by target_block_id."""
        query = build_query('cfg_edges', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], where="target_block_id = ?")
        cursor.execute(query, (target_block_id,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], row, strict=True)) for row in cursor.fetchall()]


class CfgEdgesJsxTable:
    """Accessor class for cfg_edges_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from cfg_edges_jsx."""
        query = build_query('cfg_edges_jsx', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('cfg_edges_jsx', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> list[dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('cfg_edges_jsx', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_block_id(cursor: sqlite3.Cursor, source_block_id: int) -> list[dict[str, Any]]:
        """Get rows by source_block_id."""
        query = build_query('cfg_edges_jsx', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], where="source_block_id = ?")
        cursor.execute(query, (source_block_id,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_block_id(cursor: sqlite3.Cursor, target_block_id: int) -> list[dict[str, Any]]:
        """Get rows by target_block_id."""
        query = build_query('cfg_edges_jsx', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], where="target_block_id = ?")
        cursor.execute(query, (target_block_id,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]


class ClassDecoratorArgsTable:
    """Accessor class for class_decorator_args table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from class_decorator_args."""
        query = build_query('class_decorator_args', ['file', 'class_line', 'class_name', 'decorator_index', 'arg_index', 'arg_value'])
        cursor.execute(query)
        return [dict(zip(['file', 'class_line', 'class_name', 'decorator_index', 'arg_index', 'arg_value'], row, strict=True)) for row in cursor.fetchall()]


class ClassDecoratorsTable:
    """Accessor class for class_decorators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from class_decorators."""
        query = build_query('class_decorators', ['file', 'class_line', 'class_name', 'decorator_index', 'decorator_name', 'decorator_line'])
        cursor.execute(query)
        return [dict(zip(['file', 'class_line', 'class_name', 'decorator_index', 'decorator_name', 'decorator_line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_decorator_name(cursor: sqlite3.Cursor, decorator_name: str) -> list[dict[str, Any]]:
        """Get rows by decorator_name."""
        query = build_query('class_decorators', ['file', 'class_line', 'class_name', 'decorator_index', 'decorator_name', 'decorator_line'], where="decorator_name = ?")
        cursor.execute(query, (decorator_name,))
        return [dict(zip(['file', 'class_line', 'class_name', 'decorator_index', 'decorator_name', 'decorator_line'], row, strict=True)) for row in cursor.fetchall()]


class ClassPropertiesTable:
    """Accessor class for class_properties table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from class_properties."""
        query = build_query('class_properties', ['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('class_properties', ['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_class_name(cursor: sqlite3.Cursor, class_name: str) -> list[dict[str, Any]]:
        """Get rows by class_name."""
        query = build_query('class_properties', ['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], where="class_name = ?")
        cursor.execute(query, (class_name,))
        return [dict(zip(['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_name(cursor: sqlite3.Cursor, property_name: str) -> list[dict[str, Any]]:
        """Get rows by property_name."""
        query = build_query('class_properties', ['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], where="property_name = ?")
        cursor.execute(query, (property_name,))
        return [dict(zip(['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], row, strict=True)) for row in cursor.fetchall()]


class CodeDiffsTable:
    """Accessor class for code_diffs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from code_diffs."""
        query = build_query('code_diffs', ['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'])
        cursor.execute(query)
        return [dict(zip(['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_snapshot_id(cursor: sqlite3.Cursor, snapshot_id: int) -> list[dict[str, Any]]:
        """Get rows by snapshot_id."""
        query = build_query('code_diffs', ['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'], where="snapshot_id = ?")
        cursor.execute(query, (snapshot_id,))
        return [dict(zip(['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('code_diffs', ['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'], row, strict=True)) for row in cursor.fetchall()]


class CodeSnapshotsTable:
    """Accessor class for code_snapshots table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from code_snapshots."""
        query = build_query('code_snapshots', ['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'shadow_sha', 'files_json'])
        cursor.execute(query)
        return [dict(zip(['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'shadow_sha', 'files_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_plan_id(cursor: sqlite3.Cursor, plan_id: int) -> list[dict[str, Any]]:
        """Get rows by plan_id."""
        query = build_query('code_snapshots', ['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'shadow_sha', 'files_json'], where="plan_id = ?")
        cursor.execute(query, (plan_id,))
        return [dict(zip(['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'shadow_sha', 'files_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_task_id(cursor: sqlite3.Cursor, task_id: int) -> list[dict[str, Any]]:
        """Get rows by task_id."""
        query = build_query('code_snapshots', ['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'shadow_sha', 'files_json'], where="task_id = ?")
        cursor.execute(query, (task_id,))
        return [dict(zip(['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'shadow_sha', 'files_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_timestamp(cursor: sqlite3.Cursor, timestamp: str) -> list[dict[str, Any]]:
        """Get rows by timestamp."""
        query = build_query('code_snapshots', ['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'shadow_sha', 'files_json'], where="timestamp = ?")
        cursor.execute(query, (timestamp,))
        return [dict(zip(['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'shadow_sha', 'files_json'], row, strict=True)) for row in cursor.fetchall()]


class ComposeServiceCapabilitiesTable:
    """Accessor class for compose_service_capabilities table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from compose_service_capabilities."""
        query = build_query('compose_service_capabilities', ['id', 'file_path', 'service_name', 'capability', 'is_add'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'service_name', 'capability', 'is_add'], row, strict=True)) for row in cursor.fetchall()]


class ComposeServiceDepsTable:
    """Accessor class for compose_service_deps table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from compose_service_deps."""
        query = build_query('compose_service_deps', ['id', 'file_path', 'service_name', 'depends_on_service', 'condition'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'service_name', 'depends_on_service', 'condition'], row, strict=True)) for row in cursor.fetchall()]


class ComposeServiceEnvTable:
    """Accessor class for compose_service_env table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from compose_service_env."""
        query = build_query('compose_service_env', ['id', 'file_path', 'service_name', 'var_name', 'var_value'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'service_name', 'var_name', 'var_value'], row, strict=True)) for row in cursor.fetchall()]


class ComposeServicePortsTable:
    """Accessor class for compose_service_ports table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from compose_service_ports."""
        query = build_query('compose_service_ports', ['id', 'file_path', 'service_name', 'host_port', 'container_port', 'protocol'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'service_name', 'host_port', 'container_port', 'protocol'], row, strict=True)) for row in cursor.fetchall()]


class ComposeServiceVolumesTable:
    """Accessor class for compose_service_volumes table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from compose_service_volumes."""
        query = build_query('compose_service_volumes', ['id', 'file_path', 'service_name', 'host_path', 'container_path', 'mode'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'service_name', 'host_path', 'container_path', 'mode'], row, strict=True)) for row in cursor.fetchall()]


class ComposeServicesTable:
    """Accessor class for compose_services table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from compose_services."""
        query = build_query('compose_services', ['file_path', 'service_name', 'image', 'is_privileged', 'network_mode', 'user', 'security_opt', 'restart', 'command', 'entrypoint', 'healthcheck', 'mem_limit', 'cpus', 'read_only'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'service_name', 'image', 'is_privileged', 'network_mode', 'user', 'security_opt', 'restart', 'command', 'entrypoint', 'healthcheck', 'mem_limit', 'cpus', 'read_only'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('compose_services', ['file_path', 'service_name', 'image', 'is_privileged', 'network_mode', 'user', 'security_opt', 'restart', 'command', 'entrypoint', 'healthcheck', 'mem_limit', 'cpus', 'read_only'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'service_name', 'image', 'is_privileged', 'network_mode', 'user', 'security_opt', 'restart', 'command', 'entrypoint', 'healthcheck', 'mem_limit', 'cpus', 'read_only'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_privileged(cursor: sqlite3.Cursor, is_privileged: bool) -> list[dict[str, Any]]:
        """Get rows by is_privileged."""
        query = build_query('compose_services', ['file_path', 'service_name', 'image', 'is_privileged', 'network_mode', 'user', 'security_opt', 'restart', 'command', 'entrypoint', 'healthcheck', 'mem_limit', 'cpus', 'read_only'], where="is_privileged = ?")
        cursor.execute(query, (is_privileged,))
        return [dict(zip(['file_path', 'service_name', 'image', 'is_privileged', 'network_mode', 'user', 'security_opt', 'restart', 'command', 'entrypoint', 'healthcheck', 'mem_limit', 'cpus', 'read_only'], row, strict=True)) for row in cursor.fetchall()]


class ConfigFilesTable:
    """Accessor class for config_files table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from config_files."""
        query = build_query('config_files', ['path', 'content', 'type', 'context_dir'])
        cursor.execute(query)
        return [dict(zip(['path', 'content', 'type', 'context_dir'], row, strict=True)) for row in cursor.fetchall()]


class DependencyVersionsTable:
    """Accessor class for dependency_versions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from dependency_versions."""
        query = build_query('dependency_versions', ['manager', 'package_name', 'locked_version', 'latest_version', 'delta', 'is_outdated', 'last_checked', 'error'])
        cursor.execute(query)
        return [dict(zip(['manager', 'package_name', 'locked_version', 'latest_version', 'delta', 'is_outdated', 'last_checked', 'error'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_outdated(cursor: sqlite3.Cursor, is_outdated: bool) -> list[dict[str, Any]]:
        """Get rows by is_outdated."""
        query = build_query('dependency_versions', ['manager', 'package_name', 'locked_version', 'latest_version', 'delta', 'is_outdated', 'last_checked', 'error'], where="is_outdated = ?")
        cursor.execute(query, (is_outdated,))
        return [dict(zip(['manager', 'package_name', 'locked_version', 'latest_version', 'delta', 'is_outdated', 'last_checked', 'error'], row, strict=True)) for row in cursor.fetchall()]


class DiInjectionsTable:
    """Accessor class for di_injections table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from di_injections."""
        query = build_query('di_injections', ['file', 'line', 'target_class', 'injected_service', 'injection_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'target_class', 'injected_service', 'injection_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('di_injections', ['file', 'line', 'target_class', 'injected_service', 'injection_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'target_class', 'injected_service', 'injection_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_class(cursor: sqlite3.Cursor, target_class: str) -> list[dict[str, Any]]:
        """Get rows by target_class."""
        query = build_query('di_injections', ['file', 'line', 'target_class', 'injected_service', 'injection_type'], where="target_class = ?")
        cursor.execute(query, (target_class,))
        return [dict(zip(['file', 'line', 'target_class', 'injected_service', 'injection_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_injected_service(cursor: sqlite3.Cursor, injected_service: str) -> list[dict[str, Any]]:
        """Get rows by injected_service."""
        query = build_query('di_injections', ['file', 'line', 'target_class', 'injected_service', 'injection_type'], where="injected_service = ?")
        cursor.execute(query, (injected_service,))
        return [dict(zip(['file', 'line', 'target_class', 'injected_service', 'injection_type'], row, strict=True)) for row in cursor.fetchall()]


class DockerImagesTable:
    """Accessor class for docker_images table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from docker_images."""
        query = build_query('docker_images', ['file_path', 'base_image', 'user', 'has_healthcheck'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'base_image', 'user', 'has_healthcheck'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_base_image(cursor: sqlite3.Cursor, base_image: str) -> list[dict[str, Any]]:
        """Get rows by base_image."""
        query = build_query('docker_images', ['file_path', 'base_image', 'user', 'has_healthcheck'], where="base_image = ?")
        cursor.execute(query, (base_image,))
        return [dict(zip(['file_path', 'base_image', 'user', 'has_healthcheck'], row, strict=True)) for row in cursor.fetchall()]


class DockerfileEnvVarsTable:
    """Accessor class for dockerfile_env_vars table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from dockerfile_env_vars."""
        query = build_query('dockerfile_env_vars', ['id', 'file_path', 'var_name', 'var_value', 'is_build_arg'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'var_name', 'var_value', 'is_build_arg'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('dockerfile_env_vars', ['id', 'file_path', 'var_name', 'var_value', 'is_build_arg'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'file_path', 'var_name', 'var_value', 'is_build_arg'], row, strict=True)) for row in cursor.fetchall()]


class DockerfileInstructionsTable:
    """Accessor class for dockerfile_instructions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from dockerfile_instructions."""
        query = build_query('dockerfile_instructions', ['id', 'file_path', 'line', 'instruction', 'arguments'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'line', 'instruction', 'arguments'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('dockerfile_instructions', ['id', 'file_path', 'line', 'instruction', 'arguments'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'file_path', 'line', 'instruction', 'arguments'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_instruction(cursor: sqlite3.Cursor, instruction: str) -> list[dict[str, Any]]:
        """Get rows by instruction."""
        query = build_query('dockerfile_instructions', ['id', 'file_path', 'line', 'instruction', 'arguments'], where="instruction = ?")
        cursor.execute(query, (instruction,))
        return [dict(zip(['id', 'file_path', 'line', 'instruction', 'arguments'], row, strict=True)) for row in cursor.fetchall()]


class DockerfilePortsTable:
    """Accessor class for dockerfile_ports table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from dockerfile_ports."""
        query = build_query('dockerfile_ports', ['id', 'file_path', 'port', 'protocol'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'port', 'protocol'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('dockerfile_ports', ['id', 'file_path', 'port', 'protocol'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'file_path', 'port', 'protocol'], row, strict=True)) for row in cursor.fetchall()]


class EnvVarUsageTable:
    """Accessor class for env_var_usage table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from env_var_usage."""
        query = build_query('env_var_usage', ['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('env_var_usage', ['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_var_name(cursor: sqlite3.Cursor, var_name: str) -> list[dict[str, Any]]:
        """Get rows by var_name."""
        query = build_query('env_var_usage', ['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], where="var_name = ?")
        cursor.execute(query, (var_name,))
        return [dict(zip(['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_access_type(cursor: sqlite3.Cursor, access_type: str) -> list[dict[str, Any]]:
        """Get rows by access_type."""
        query = build_query('env_var_usage', ['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], where="access_type = ?")
        cursor.execute(query, (access_type,))
        return [dict(zip(['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], row, strict=True)) for row in cursor.fetchall()]


class ExpressMiddlewareChainsTable:
    """Accessor class for express_middleware_chains table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from express_middleware_chains."""
        query = build_query('express_middleware_chains', ['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('express_middleware_chains', ['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_route_line(cursor: sqlite3.Cursor, route_line: int) -> list[dict[str, Any]]:
        """Get rows by route_line."""
        query = build_query('express_middleware_chains', ['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], where="route_line = ?")
        cursor.execute(query, (route_line,))
        return [dict(zip(['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_route_path(cursor: sqlite3.Cursor, route_path: str) -> list[dict[str, Any]]:
        """Get rows by route_path."""
        query = build_query('express_middleware_chains', ['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], where="route_path = ?")
        cursor.execute(query, (route_path,))
        return [dict(zip(['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_route_method(cursor: sqlite3.Cursor, route_method: str) -> list[dict[str, Any]]:
        """Get rows by route_method."""
        query = build_query('express_middleware_chains', ['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], where="route_method = ?")
        cursor.execute(query, (route_method,))
        return [dict(zip(['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_handler_type(cursor: sqlite3.Cursor, handler_type: str) -> list[dict[str, Any]]:
        """Get rows by handler_type."""
        query = build_query('express_middleware_chains', ['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], where="handler_type = ?")
        cursor.execute(query, (handler_type,))
        return [dict(zip(['id', 'file', 'route_line', 'route_path', 'route_method', 'execution_order', 'handler_expr', 'handler_type', 'handler_file', 'handler_function', 'handler_line'], row, strict=True)) for row in cursor.fetchall()]


class FilesTable:
    """Accessor class for files table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from files."""
        query = build_query('files', ['path', 'sha256', 'ext', 'bytes', 'loc', 'file_category'])
        cursor.execute(query)
        return [dict(zip(['path', 'sha256', 'ext', 'bytes', 'loc', 'file_category'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_ext(cursor: sqlite3.Cursor, ext: str) -> list[dict[str, Any]]:
        """Get rows by ext."""
        query = build_query('files', ['path', 'sha256', 'ext', 'bytes', 'loc', 'file_category'], where="ext = ?")
        cursor.execute(query, (ext,))
        return [dict(zip(['path', 'sha256', 'ext', 'bytes', 'loc', 'file_category'], row, strict=True)) for row in cursor.fetchall()]


class FindingsConsolidatedTable:
    """Accessor class for findings_consolidated table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from findings_consolidated."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_tool(cursor: sqlite3.Cursor, tool: str) -> list[dict[str, Any]]:
        """Get rows by tool."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], where="tool = ?")
        cursor.execute(query, (tool,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_severity(cursor: sqlite3.Cursor, severity: str) -> list[dict[str, Any]]:
        """Get rows by severity."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], where="severity = ?")
        cursor.execute(query, (severity,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_rule(cursor: sqlite3.Cursor, rule: str) -> list[dict[str, Any]]:
        """Get rows by rule."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], where="rule = ?")
        cursor.execute(query, (rule,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_category(cursor: sqlite3.Cursor, category: str) -> list[dict[str, Any]]:
        """Get rows by category."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], where="category = ?")
        cursor.execute(query, (category,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_cfg_complexity(cursor: sqlite3.Cursor, cfg_complexity: int) -> list[dict[str, Any]]:
        """Get rows by cfg_complexity."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], where="cfg_complexity = ?")
        cursor.execute(query, (cfg_complexity,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_graph_score(cursor: sqlite3.Cursor, graph_score: float) -> list[dict[str, Any]]:
        """Get rows by graph_score."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], where="graph_score = ?")
        cursor.execute(query, (graph_score,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_mypy_error_code(cursor: sqlite3.Cursor, mypy_error_code: str) -> list[dict[str, Any]]:
        """Get rows by mypy_error_code."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], where="mypy_error_code = ?")
        cursor.execute(query, (mypy_error_code,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'cfg_function', 'cfg_complexity', 'cfg_block_count', 'cfg_edge_count', 'cfg_has_loops', 'cfg_has_recursion', 'cfg_start_line', 'cfg_end_line', 'cfg_threshold', 'graph_id', 'graph_in_degree', 'graph_out_degree', 'graph_total_connections', 'graph_centrality', 'graph_score', 'graph_cycle_nodes', 'mypy_error_code', 'mypy_severity_int', 'mypy_column', 'tf_finding_id', 'tf_resource_id', 'tf_remediation', 'tf_graph_context', 'details_json'], row, strict=True)) for row in cursor.fetchall()]


class FrameworkSafeSinksTable:
    """Accessor class for framework_safe_sinks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from framework_safe_sinks."""
        query = build_query('framework_safe_sinks', ['framework_id', 'sink_pattern', 'sink_type', 'is_safe', 'reason'])
        cursor.execute(query)
        return [dict(zip(['framework_id', 'sink_pattern', 'sink_type', 'is_safe', 'reason'], row, strict=True)) for row in cursor.fetchall()]


class FrameworkTaintPatternsTable:
    """Accessor class for framework_taint_patterns table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from framework_taint_patterns."""
        query = build_query('framework_taint_patterns', ['id', 'framework_id', 'pattern', 'pattern_type', 'category'])
        cursor.execute(query)
        return [dict(zip(['id', 'framework_id', 'pattern', 'pattern_type', 'category'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_framework_id(cursor: sqlite3.Cursor, framework_id: int) -> list[dict[str, Any]]:
        """Get rows by framework_id."""
        query = build_query('framework_taint_patterns', ['id', 'framework_id', 'pattern', 'pattern_type', 'category'], where="framework_id = ?")
        cursor.execute(query, (framework_id,))
        return [dict(zip(['id', 'framework_id', 'pattern', 'pattern_type', 'category'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_pattern_type(cursor: sqlite3.Cursor, pattern_type: str) -> list[dict[str, Any]]:
        """Get rows by pattern_type."""
        query = build_query('framework_taint_patterns', ['id', 'framework_id', 'pattern', 'pattern_type', 'category'], where="pattern_type = ?")
        cursor.execute(query, (pattern_type,))
        return [dict(zip(['id', 'framework_id', 'pattern', 'pattern_type', 'category'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_pattern(cursor: sqlite3.Cursor, pattern: str) -> list[dict[str, Any]]:
        """Get rows by pattern."""
        query = build_query('framework_taint_patterns', ['id', 'framework_id', 'pattern', 'pattern_type', 'category'], where="pattern = ?")
        cursor.execute(query, (pattern,))
        return [dict(zip(['id', 'framework_id', 'pattern', 'pattern_type', 'category'], row, strict=True)) for row in cursor.fetchall()]


class FrameworksTable:
    """Accessor class for frameworks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from frameworks."""
        query = build_query('frameworks', ['id', 'name', 'version', 'language', 'path', 'source', 'package_manager', 'is_primary'])
        cursor.execute(query)
        return [dict(zip(['id', 'name', 'version', 'language', 'path', 'source', 'package_manager', 'is_primary'], row, strict=True)) for row in cursor.fetchall()]


class FrontendApiCallsTable:
    """Accessor class for frontend_api_calls table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from frontend_api_calls."""
        query = build_query('frontend_api_calls', ['file', 'line', 'method', 'url_literal', 'body_variable', 'function_name'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'method', 'url_literal', 'body_variable', 'function_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('frontend_api_calls', ['file', 'line', 'method', 'url_literal', 'body_variable', 'function_name'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'method', 'url_literal', 'body_variable', 'function_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_url_literal(cursor: sqlite3.Cursor, url_literal: str) -> list[dict[str, Any]]:
        """Get rows by url_literal."""
        query = build_query('frontend_api_calls', ['file', 'line', 'method', 'url_literal', 'body_variable', 'function_name'], where="url_literal = ?")
        cursor.execute(query, (url_literal,))
        return [dict(zip(['file', 'line', 'method', 'url_literal', 'body_variable', 'function_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_method(cursor: sqlite3.Cursor, method: str) -> list[dict[str, Any]]:
        """Get rows by method."""
        query = build_query('frontend_api_calls', ['file', 'line', 'method', 'url_literal', 'body_variable', 'function_name'], where="method = ?")
        cursor.execute(query, (method,))
        return [dict(zip(['file', 'line', 'method', 'url_literal', 'body_variable', 'function_name'], row, strict=True)) for row in cursor.fetchall()]


class FuncDecoratorArgsTable:
    """Accessor class for func_decorator_args table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from func_decorator_args."""
        query = build_query('func_decorator_args', ['file', 'function_line', 'function_name', 'decorator_index', 'arg_index', 'arg_value'])
        cursor.execute(query)
        return [dict(zip(['file', 'function_line', 'function_name', 'decorator_index', 'arg_index', 'arg_value'], row, strict=True)) for row in cursor.fetchall()]


class FuncDecoratorsTable:
    """Accessor class for func_decorators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from func_decorators."""
        query = build_query('func_decorators', ['file', 'function_line', 'function_name', 'decorator_index', 'decorator_name', 'decorator_line'])
        cursor.execute(query)
        return [dict(zip(['file', 'function_line', 'function_name', 'decorator_index', 'decorator_name', 'decorator_line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_decorator_name(cursor: sqlite3.Cursor, decorator_name: str) -> list[dict[str, Any]]:
        """Get rows by decorator_name."""
        query = build_query('func_decorators', ['file', 'function_line', 'function_name', 'decorator_index', 'decorator_name', 'decorator_line'], where="decorator_name = ?")
        cursor.execute(query, (decorator_name,))
        return [dict(zip(['file', 'function_line', 'function_name', 'decorator_index', 'decorator_name', 'decorator_line'], row, strict=True)) for row in cursor.fetchall()]


class FuncParamDecoratorsTable:
    """Accessor class for func_param_decorators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from func_param_decorators."""
        query = build_query('func_param_decorators', ['file', 'function_line', 'function_name', 'param_index', 'decorator_name', 'decorator_args'])
        cursor.execute(query)
        return [dict(zip(['file', 'function_line', 'function_name', 'param_index', 'decorator_name', 'decorator_args'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_decorator_name(cursor: sqlite3.Cursor, decorator_name: str) -> list[dict[str, Any]]:
        """Get rows by decorator_name."""
        query = build_query('func_param_decorators', ['file', 'function_line', 'function_name', 'param_index', 'decorator_name', 'decorator_args'], where="decorator_name = ?")
        cursor.execute(query, (decorator_name,))
        return [dict(zip(['file', 'function_line', 'function_name', 'param_index', 'decorator_name', 'decorator_args'], row, strict=True)) for row in cursor.fetchall()]


class FuncParamsTable:
    """Accessor class for func_params table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from func_params."""
        query = build_query('func_params', ['file', 'function_line', 'function_name', 'param_index', 'param_name', 'param_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'function_line', 'function_name', 'param_index', 'param_name', 'param_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_param_name(cursor: sqlite3.Cursor, param_name: str) -> list[dict[str, Any]]:
        """Get rows by param_name."""
        query = build_query('func_params', ['file', 'function_line', 'function_name', 'param_index', 'param_name', 'param_type'], where="param_name = ?")
        cursor.execute(query, (param_name,))
        return [dict(zip(['file', 'function_line', 'function_name', 'param_index', 'param_name', 'param_type'], row, strict=True)) for row in cursor.fetchall()]


class FunctionCallArgsTable:
    """Accessor class for function_call_args table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from function_call_args."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_caller_function(cursor: sqlite3.Cursor, caller_function: str) -> list[dict[str, Any]]:
        """Get rows by caller_function."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], where="caller_function = ?")
        cursor.execute(query, (caller_function,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_callee_function(cursor: sqlite3.Cursor, callee_function: str) -> list[dict[str, Any]]:
        """Get rows by callee_function."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], where="callee_function = ?")
        cursor.execute(query, (callee_function,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_callee_file_path(cursor: sqlite3.Cursor, callee_file_path: str) -> list[dict[str, Any]]:
        """Get rows by callee_file_path."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], where="callee_file_path = ?")
        cursor.execute(query, (callee_file_path,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_argument_index(cursor: sqlite3.Cursor, argument_index: int) -> list[dict[str, Any]]:
        """Get rows by argument_index."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], where="argument_index = ?")
        cursor.execute(query, (argument_index,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_param_name(cursor: sqlite3.Cursor, param_name: str) -> list[dict[str, Any]]:
        """Get rows by param_name."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], where="param_name = ?")
        cursor.execute(query, (param_name,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row, strict=True)) for row in cursor.fetchall()]


class FunctionCallArgsJsxTable:
    """Accessor class for function_call_args_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from function_call_args_jsx."""
        query = build_query('function_call_args_jsx', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('function_call_args_jsx', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_caller_function(cursor: sqlite3.Cursor, caller_function: str) -> list[dict[str, Any]]:
        """Get rows by caller_function."""
        query = build_query('function_call_args_jsx', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'], where="caller_function = ?")
        cursor.execute(query, (caller_function,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]


class FunctionReturnSourcesTable:
    """Accessor class for function_return_sources table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from function_return_sources."""
        query = build_query('function_return_sources', ['id', 'return_file', 'return_line', 'return_col', 'return_function', 'return_var_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'return_file', 'return_line', 'return_col', 'return_function', 'return_var_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_return_var_name(cursor: sqlite3.Cursor, return_var_name: str) -> list[dict[str, Any]]:
        """Get rows by return_var_name."""
        query = build_query('function_return_sources', ['id', 'return_file', 'return_line', 'return_col', 'return_function', 'return_var_name'], where="return_var_name = ?")
        cursor.execute(query, (return_var_name,))
        return [dict(zip(['id', 'return_file', 'return_line', 'return_col', 'return_function', 'return_var_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_return_file(cursor: sqlite3.Cursor, return_file: str) -> list[dict[str, Any]]:
        """Get rows by return_file."""
        query = build_query('function_return_sources', ['id', 'return_file', 'return_line', 'return_col', 'return_function', 'return_var_name'], where="return_file = ?")
        cursor.execute(query, (return_file,))
        return [dict(zip(['id', 'return_file', 'return_line', 'return_col', 'return_function', 'return_var_name'], row, strict=True)) for row in cursor.fetchall()]


class FunctionReturnSourcesJsxTable:
    """Accessor class for function_return_sources_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from function_return_sources_jsx."""
        query = build_query('function_return_sources_jsx', ['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_return_var_name(cursor: sqlite3.Cursor, return_var_name: str) -> list[dict[str, Any]]:
        """Get rows by return_var_name."""
        query = build_query('function_return_sources_jsx', ['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name', 'extraction_pass'], where="return_var_name = ?")
        cursor.execute(query, (return_var_name,))
        return [dict(zip(['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_return_file(cursor: sqlite3.Cursor, return_file: str) -> list[dict[str, Any]]:
        """Get rows by return_file."""
        query = build_query('function_return_sources_jsx', ['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name', 'extraction_pass'], where="return_file = ?")
        cursor.execute(query, (return_file,))
        return [dict(zip(['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]


class FunctionReturnsTable:
    """Accessor class for function_returns table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from function_returns."""
        query = build_query('function_returns', ['file', 'line', 'col', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'col', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('function_returns', ['file', 'line', 'col', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'col', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> list[dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('function_returns', ['file', 'line', 'col', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['file', 'line', 'col', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'], row, strict=True)) for row in cursor.fetchall()]


class FunctionReturnsJsxTable:
    """Accessor class for function_returns_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from function_returns_jsx."""
        query = build_query('function_returns_jsx', ['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('function_returns_jsx', ['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> list[dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('function_returns_jsx', ['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]


class GithubJobDependenciesTable:
    """Accessor class for github_job_dependencies table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from github_job_dependencies."""
        query = build_query('github_job_dependencies', ['job_id', 'needs_job_id'])
        cursor.execute(query)
        return [dict(zip(['job_id', 'needs_job_id'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_job_id(cursor: sqlite3.Cursor, job_id: str) -> list[dict[str, Any]]:
        """Get rows by job_id."""
        query = build_query('github_job_dependencies', ['job_id', 'needs_job_id'], where="job_id = ?")
        cursor.execute(query, (job_id,))
        return [dict(zip(['job_id', 'needs_job_id'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_needs_job_id(cursor: sqlite3.Cursor, needs_job_id: str) -> list[dict[str, Any]]:
        """Get rows by needs_job_id."""
        query = build_query('github_job_dependencies', ['job_id', 'needs_job_id'], where="needs_job_id = ?")
        cursor.execute(query, (needs_job_id,))
        return [dict(zip(['job_id', 'needs_job_id'], row, strict=True)) for row in cursor.fetchall()]


class GithubJobsTable:
    """Accessor class for github_jobs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from github_jobs."""
        query = build_query('github_jobs', ['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'])
        cursor.execute(query)
        return [dict(zip(['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_workflow_path(cursor: sqlite3.Cursor, workflow_path: str) -> list[dict[str, Any]]:
        """Get rows by workflow_path."""
        query = build_query('github_jobs', ['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], where="workflow_path = ?")
        cursor.execute(query, (workflow_path,))
        return [dict(zip(['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_job_key(cursor: sqlite3.Cursor, job_key: str) -> list[dict[str, Any]]:
        """Get rows by job_key."""
        query = build_query('github_jobs', ['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], where="job_key = ?")
        cursor.execute(query, (job_key,))
        return [dict(zip(['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_uses_reusable_workflow(cursor: sqlite3.Cursor, uses_reusable_workflow: bool) -> list[dict[str, Any]]:
        """Get rows by uses_reusable_workflow."""
        query = build_query('github_jobs', ['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], where="uses_reusable_workflow = ?")
        cursor.execute(query, (uses_reusable_workflow,))
        return [dict(zip(['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], row, strict=True)) for row in cursor.fetchall()]


class GithubStepOutputsTable:
    """Accessor class for github_step_outputs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from github_step_outputs."""
        query = build_query('github_step_outputs', ['id', 'step_id', 'output_name', 'output_expression'])
        cursor.execute(query)
        return [dict(zip(['id', 'step_id', 'output_name', 'output_expression'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_step_id(cursor: sqlite3.Cursor, step_id: str) -> list[dict[str, Any]]:
        """Get rows by step_id."""
        query = build_query('github_step_outputs', ['id', 'step_id', 'output_name', 'output_expression'], where="step_id = ?")
        cursor.execute(query, (step_id,))
        return [dict(zip(['id', 'step_id', 'output_name', 'output_expression'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_output_name(cursor: sqlite3.Cursor, output_name: str) -> list[dict[str, Any]]:
        """Get rows by output_name."""
        query = build_query('github_step_outputs', ['id', 'step_id', 'output_name', 'output_expression'], where="output_name = ?")
        cursor.execute(query, (output_name,))
        return [dict(zip(['id', 'step_id', 'output_name', 'output_expression'], row, strict=True)) for row in cursor.fetchall()]


class GithubStepReferencesTable:
    """Accessor class for github_step_references table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from github_step_references."""
        query = build_query('github_step_references', ['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'])
        cursor.execute(query)
        return [dict(zip(['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_step_id(cursor: sqlite3.Cursor, step_id: str) -> list[dict[str, Any]]:
        """Get rows by step_id."""
        query = build_query('github_step_references', ['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], where="step_id = ?")
        cursor.execute(query, (step_id,))
        return [dict(zip(['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_reference_type(cursor: sqlite3.Cursor, reference_type: str) -> list[dict[str, Any]]:
        """Get rows by reference_type."""
        query = build_query('github_step_references', ['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], where="reference_type = ?")
        cursor.execute(query, (reference_type,))
        return [dict(zip(['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_reference_path(cursor: sqlite3.Cursor, reference_path: str) -> list[dict[str, Any]]:
        """Get rows by reference_path."""
        query = build_query('github_step_references', ['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], where="reference_path = ?")
        cursor.execute(query, (reference_path,))
        return [dict(zip(['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_reference_location(cursor: sqlite3.Cursor, reference_location: str) -> list[dict[str, Any]]:
        """Get rows by reference_location."""
        query = build_query('github_step_references', ['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], where="reference_location = ?")
        cursor.execute(query, (reference_location,))
        return [dict(zip(['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], row, strict=True)) for row in cursor.fetchall()]


class GithubStepsTable:
    """Accessor class for github_steps table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from github_steps."""
        query = build_query('github_steps', ['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'])
        cursor.execute(query)
        return [dict(zip(['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_job_id(cursor: sqlite3.Cursor, job_id: str) -> list[dict[str, Any]]:
        """Get rows by job_id."""
        query = build_query('github_steps', ['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], where="job_id = ?")
        cursor.execute(query, (job_id,))
        return [dict(zip(['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_uses_action(cursor: sqlite3.Cursor, uses_action: str) -> list[dict[str, Any]]:
        """Get rows by uses_action."""
        query = build_query('github_steps', ['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], where="uses_action = ?")
        cursor.execute(query, (uses_action,))
        return [dict(zip(['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_uses_version(cursor: sqlite3.Cursor, uses_version: str) -> list[dict[str, Any]]:
        """Get rows by uses_version."""
        query = build_query('github_steps', ['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], where="uses_version = ?")
        cursor.execute(query, (uses_version,))
        return [dict(zip(['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], row, strict=True)) for row in cursor.fetchall()]


class GithubWorkflowsTable:
    """Accessor class for github_workflows table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from github_workflows."""
        query = build_query('github_workflows', ['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'])
        cursor.execute(query)
        return [dict(zip(['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_workflow_path(cursor: sqlite3.Cursor, workflow_path: str) -> list[dict[str, Any]]:
        """Get rows by workflow_path."""
        query = build_query('github_workflows', ['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'], where="workflow_path = ?")
        cursor.execute(query, (workflow_path,))
        return [dict(zip(['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_workflow_name(cursor: sqlite3.Cursor, workflow_name: str) -> list[dict[str, Any]]:
        """Get rows by workflow_name."""
        query = build_query('github_workflows', ['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'], where="workflow_name = ?")
        cursor.execute(query, (workflow_name,))
        return [dict(zip(['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'], row, strict=True)) for row in cursor.fetchall()]


class GoCapturedVarsTable:
    """Accessor class for go_captured_vars table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_captured_vars."""
        query = build_query('go_captured_vars', ['file', 'line', 'goroutine_id', 'var_name', 'var_type', 'is_loop_var'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'goroutine_id', 'var_name', 'var_type', 'is_loop_var'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_captured_vars', ['file', 'line', 'goroutine_id', 'var_name', 'var_type', 'is_loop_var'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'goroutine_id', 'var_name', 'var_type', 'is_loop_var'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_goroutine_id(cursor: sqlite3.Cursor, goroutine_id: int) -> list[dict[str, Any]]:
        """Get rows by goroutine_id."""
        query = build_query('go_captured_vars', ['file', 'line', 'goroutine_id', 'var_name', 'var_type', 'is_loop_var'], where="goroutine_id = ?")
        cursor.execute(query, (goroutine_id,))
        return [dict(zip(['file', 'line', 'goroutine_id', 'var_name', 'var_type', 'is_loop_var'], row, strict=True)) for row in cursor.fetchall()]


class GoChannelOpsTable:
    """Accessor class for go_channel_ops table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_channel_ops."""
        query = build_query('go_channel_ops', ['file', 'line', 'channel_name', 'operation', 'containing_func'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'channel_name', 'operation', 'containing_func'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_channel_ops', ['file', 'line', 'channel_name', 'operation', 'containing_func'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'channel_name', 'operation', 'containing_func'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_channel_name(cursor: sqlite3.Cursor, channel_name: str) -> list[dict[str, Any]]:
        """Get rows by channel_name."""
        query = build_query('go_channel_ops', ['file', 'line', 'channel_name', 'operation', 'containing_func'], where="channel_name = ?")
        cursor.execute(query, (channel_name,))
        return [dict(zip(['file', 'line', 'channel_name', 'operation', 'containing_func'], row, strict=True)) for row in cursor.fetchall()]


class GoChannelsTable:
    """Accessor class for go_channels table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_channels."""
        query = build_query('go_channels', ['file', 'line', 'name', 'element_type', 'direction', 'buffer_size'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'name', 'element_type', 'direction', 'buffer_size'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_channels', ['file', 'line', 'name', 'element_type', 'direction', 'buffer_size'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'name', 'element_type', 'direction', 'buffer_size'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('go_channels', ['file', 'line', 'name', 'element_type', 'direction', 'buffer_size'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'line', 'name', 'element_type', 'direction', 'buffer_size'], row, strict=True)) for row in cursor.fetchall()]


class GoConstantsTable:
    """Accessor class for go_constants table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_constants."""
        query = build_query('go_constants', ['file', 'line', 'name', 'value', 'type', 'is_exported'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'name', 'value', 'type', 'is_exported'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_constants', ['file', 'line', 'name', 'value', 'type', 'is_exported'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'name', 'value', 'type', 'is_exported'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('go_constants', ['file', 'line', 'name', 'value', 'type', 'is_exported'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'line', 'name', 'value', 'type', 'is_exported'], row, strict=True)) for row in cursor.fetchall()]


class GoDeferStatementsTable:
    """Accessor class for go_defer_statements table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_defer_statements."""
        query = build_query('go_defer_statements', ['file', 'line', 'containing_func', 'deferred_expr'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'containing_func', 'deferred_expr'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_defer_statements', ['file', 'line', 'containing_func', 'deferred_expr'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'containing_func', 'deferred_expr'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_containing_func(cursor: sqlite3.Cursor, containing_func: str) -> list[dict[str, Any]]:
        """Get rows by containing_func."""
        query = build_query('go_defer_statements', ['file', 'line', 'containing_func', 'deferred_expr'], where="containing_func = ?")
        cursor.execute(query, (containing_func,))
        return [dict(zip(['file', 'line', 'containing_func', 'deferred_expr'], row, strict=True)) for row in cursor.fetchall()]


class GoErrorReturnsTable:
    """Accessor class for go_error_returns table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_error_returns."""
        query = build_query('go_error_returns', ['file', 'line', 'func_name', 'returns_error'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'func_name', 'returns_error'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_error_returns', ['file', 'line', 'func_name', 'returns_error'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'func_name', 'returns_error'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_func_name(cursor: sqlite3.Cursor, func_name: str) -> list[dict[str, Any]]:
        """Get rows by func_name."""
        query = build_query('go_error_returns', ['file', 'line', 'func_name', 'returns_error'], where="func_name = ?")
        cursor.execute(query, (func_name,))
        return [dict(zip(['file', 'line', 'func_name', 'returns_error'], row, strict=True)) for row in cursor.fetchall()]


class GoFuncParamsTable:
    """Accessor class for go_func_params table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_func_params."""
        query = build_query('go_func_params', ['file', 'func_name', 'func_line', 'param_index', 'param_name', 'param_type', 'is_variadic'])
        cursor.execute(query)
        return [dict(zip(['file', 'func_name', 'func_line', 'param_index', 'param_name', 'param_type', 'is_variadic'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_func_name(cursor: sqlite3.Cursor, func_name: str) -> list[dict[str, Any]]:
        """Get rows by func_name."""
        query = build_query('go_func_params', ['file', 'func_name', 'func_line', 'param_index', 'param_name', 'param_type', 'is_variadic'], where="func_name = ?")
        cursor.execute(query, (func_name,))
        return [dict(zip(['file', 'func_name', 'func_line', 'param_index', 'param_name', 'param_type', 'is_variadic'], row, strict=True)) for row in cursor.fetchall()]


class GoFuncReturnsTable:
    """Accessor class for go_func_returns table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_func_returns."""
        query = build_query('go_func_returns', ['file', 'func_name', 'func_line', 'return_index', 'return_name', 'return_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'func_name', 'func_line', 'return_index', 'return_name', 'return_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_func_name(cursor: sqlite3.Cursor, func_name: str) -> list[dict[str, Any]]:
        """Get rows by func_name."""
        query = build_query('go_func_returns', ['file', 'func_name', 'func_line', 'return_index', 'return_name', 'return_type'], where="func_name = ?")
        cursor.execute(query, (func_name,))
        return [dict(zip(['file', 'func_name', 'func_line', 'return_index', 'return_name', 'return_type'], row, strict=True)) for row in cursor.fetchall()]


class GoFunctionsTable:
    """Accessor class for go_functions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_functions."""
        query = build_query('go_functions', ['file', 'line', 'name', 'signature', 'is_exported', 'is_async', 'doc_comment'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'name', 'signature', 'is_exported', 'is_async', 'doc_comment'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_functions', ['file', 'line', 'name', 'signature', 'is_exported', 'is_async', 'doc_comment'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'name', 'signature', 'is_exported', 'is_async', 'doc_comment'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('go_functions', ['file', 'line', 'name', 'signature', 'is_exported', 'is_async', 'doc_comment'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'line', 'name', 'signature', 'is_exported', 'is_async', 'doc_comment'], row, strict=True)) for row in cursor.fetchall()]


class GoGoroutinesTable:
    """Accessor class for go_goroutines table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_goroutines."""
        query = build_query('go_goroutines', ['file', 'line', 'containing_func', 'spawned_expr', 'is_anonymous'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'containing_func', 'spawned_expr', 'is_anonymous'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_goroutines', ['file', 'line', 'containing_func', 'spawned_expr', 'is_anonymous'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'containing_func', 'spawned_expr', 'is_anonymous'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_containing_func(cursor: sqlite3.Cursor, containing_func: str) -> list[dict[str, Any]]:
        """Get rows by containing_func."""
        query = build_query('go_goroutines', ['file', 'line', 'containing_func', 'spawned_expr', 'is_anonymous'], where="containing_func = ?")
        cursor.execute(query, (containing_func,))
        return [dict(zip(['file', 'line', 'containing_func', 'spawned_expr', 'is_anonymous'], row, strict=True)) for row in cursor.fetchall()]


class GoImportsTable:
    """Accessor class for go_imports table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_imports."""
        query = build_query('go_imports', ['file', 'line', 'path', 'alias', 'is_dot_import'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'path', 'alias', 'is_dot_import'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_imports', ['file', 'line', 'path', 'alias', 'is_dot_import'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'path', 'alias', 'is_dot_import'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_path(cursor: sqlite3.Cursor, path: str) -> list[dict[str, Any]]:
        """Get rows by path."""
        query = build_query('go_imports', ['file', 'line', 'path', 'alias', 'is_dot_import'], where="path = ?")
        cursor.execute(query, (path,))
        return [dict(zip(['file', 'line', 'path', 'alias', 'is_dot_import'], row, strict=True)) for row in cursor.fetchall()]


class GoInterfaceMethodsTable:
    """Accessor class for go_interface_methods table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_interface_methods."""
        query = build_query('go_interface_methods', ['file', 'interface_name', 'method_name', 'signature'])
        cursor.execute(query)
        return [dict(zip(['file', 'interface_name', 'method_name', 'signature'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_interface_name(cursor: sqlite3.Cursor, interface_name: str) -> list[dict[str, Any]]:
        """Get rows by interface_name."""
        query = build_query('go_interface_methods', ['file', 'interface_name', 'method_name', 'signature'], where="interface_name = ?")
        cursor.execute(query, (interface_name,))
        return [dict(zip(['file', 'interface_name', 'method_name', 'signature'], row, strict=True)) for row in cursor.fetchall()]


class GoInterfacesTable:
    """Accessor class for go_interfaces table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_interfaces."""
        query = build_query('go_interfaces', ['file', 'line', 'name', 'is_exported', 'doc_comment'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'name', 'is_exported', 'doc_comment'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_interfaces', ['file', 'line', 'name', 'is_exported', 'doc_comment'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'name', 'is_exported', 'doc_comment'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('go_interfaces', ['file', 'line', 'name', 'is_exported', 'doc_comment'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'line', 'name', 'is_exported', 'doc_comment'], row, strict=True)) for row in cursor.fetchall()]


class GoMethodsTable:
    """Accessor class for go_methods table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_methods."""
        query = build_query('go_methods', ['file', 'line', 'receiver_type', 'receiver_name', 'is_pointer_receiver', 'name', 'signature', 'is_exported'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'receiver_type', 'receiver_name', 'is_pointer_receiver', 'name', 'signature', 'is_exported'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_methods', ['file', 'line', 'receiver_type', 'receiver_name', 'is_pointer_receiver', 'name', 'signature', 'is_exported'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'receiver_type', 'receiver_name', 'is_pointer_receiver', 'name', 'signature', 'is_exported'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_receiver_type(cursor: sqlite3.Cursor, receiver_type: str) -> list[dict[str, Any]]:
        """Get rows by receiver_type."""
        query = build_query('go_methods', ['file', 'line', 'receiver_type', 'receiver_name', 'is_pointer_receiver', 'name', 'signature', 'is_exported'], where="receiver_type = ?")
        cursor.execute(query, (receiver_type,))
        return [dict(zip(['file', 'line', 'receiver_type', 'receiver_name', 'is_pointer_receiver', 'name', 'signature', 'is_exported'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('go_methods', ['file', 'line', 'receiver_type', 'receiver_name', 'is_pointer_receiver', 'name', 'signature', 'is_exported'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'line', 'receiver_type', 'receiver_name', 'is_pointer_receiver', 'name', 'signature', 'is_exported'], row, strict=True)) for row in cursor.fetchall()]


class GoMiddlewareTable:
    """Accessor class for go_middleware table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_middleware."""
        query = build_query('go_middleware', ['file', 'line', 'framework', 'router_var', 'middleware_func', 'is_global'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'framework', 'router_var', 'middleware_func', 'is_global'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_middleware', ['file', 'line', 'framework', 'router_var', 'middleware_func', 'is_global'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'framework', 'router_var', 'middleware_func', 'is_global'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_framework(cursor: sqlite3.Cursor, framework: str) -> list[dict[str, Any]]:
        """Get rows by framework."""
        query = build_query('go_middleware', ['file', 'line', 'framework', 'router_var', 'middleware_func', 'is_global'], where="framework = ?")
        cursor.execute(query, (framework,))
        return [dict(zip(['file', 'line', 'framework', 'router_var', 'middleware_func', 'is_global'], row, strict=True)) for row in cursor.fetchall()]


class GoModuleConfigsTable:
    """Accessor class for go_module_configs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_module_configs."""
        query = build_query('go_module_configs', ['file_path', 'module_path', 'go_version'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'module_path', 'go_version'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_path(cursor: sqlite3.Cursor, module_path: str) -> list[dict[str, Any]]:
        """Get rows by module_path."""
        query = build_query('go_module_configs', ['file_path', 'module_path', 'go_version'], where="module_path = ?")
        cursor.execute(query, (module_path,))
        return [dict(zip(['file_path', 'module_path', 'go_version'], row, strict=True)) for row in cursor.fetchall()]


class GoModuleDependenciesTable:
    """Accessor class for go_module_dependencies table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_module_dependencies."""
        query = build_query('go_module_dependencies', ['file_path', 'module_path', 'version', 'is_indirect'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'module_path', 'version', 'is_indirect'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('go_module_dependencies', ['file_path', 'module_path', 'version', 'is_indirect'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'module_path', 'version', 'is_indirect'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_path(cursor: sqlite3.Cursor, module_path: str) -> list[dict[str, Any]]:
        """Get rows by module_path."""
        query = build_query('go_module_dependencies', ['file_path', 'module_path', 'version', 'is_indirect'], where="module_path = ?")
        cursor.execute(query, (module_path,))
        return [dict(zip(['file_path', 'module_path', 'version', 'is_indirect'], row, strict=True)) for row in cursor.fetchall()]


class GoPackagesTable:
    """Accessor class for go_packages table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_packages."""
        query = build_query('go_packages', ['file', 'line', 'name', 'import_path'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'name', 'import_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('go_packages', ['file', 'line', 'name', 'import_path'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'line', 'name', 'import_path'], row, strict=True)) for row in cursor.fetchall()]


class GoRoutesTable:
    """Accessor class for go_routes table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_routes."""
        query = build_query('go_routes', ['file', 'line', 'framework', 'method', 'path', 'handler_func'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'framework', 'method', 'path', 'handler_func'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_routes', ['file', 'line', 'framework', 'method', 'path', 'handler_func'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'framework', 'method', 'path', 'handler_func'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_framework(cursor: sqlite3.Cursor, framework: str) -> list[dict[str, Any]]:
        """Get rows by framework."""
        query = build_query('go_routes', ['file', 'line', 'framework', 'method', 'path', 'handler_func'], where="framework = ?")
        cursor.execute(query, (framework,))
        return [dict(zip(['file', 'line', 'framework', 'method', 'path', 'handler_func'], row, strict=True)) for row in cursor.fetchall()]


class GoStructFieldsTable:
    """Accessor class for go_struct_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_struct_fields."""
        query = build_query('go_struct_fields', ['file', 'struct_name', 'field_name', 'field_type', 'tag', 'is_embedded', 'is_exported'])
        cursor.execute(query)
        return [dict(zip(['file', 'struct_name', 'field_name', 'field_type', 'tag', 'is_embedded', 'is_exported'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_struct_name(cursor: sqlite3.Cursor, struct_name: str) -> list[dict[str, Any]]:
        """Get rows by struct_name."""
        query = build_query('go_struct_fields', ['file', 'struct_name', 'field_name', 'field_type', 'tag', 'is_embedded', 'is_exported'], where="struct_name = ?")
        cursor.execute(query, (struct_name,))
        return [dict(zip(['file', 'struct_name', 'field_name', 'field_type', 'tag', 'is_embedded', 'is_exported'], row, strict=True)) for row in cursor.fetchall()]


class GoStructsTable:
    """Accessor class for go_structs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_structs."""
        query = build_query('go_structs', ['file', 'line', 'name', 'is_exported', 'doc_comment'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'name', 'is_exported', 'doc_comment'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_structs', ['file', 'line', 'name', 'is_exported', 'doc_comment'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'name', 'is_exported', 'doc_comment'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('go_structs', ['file', 'line', 'name', 'is_exported', 'doc_comment'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'line', 'name', 'is_exported', 'doc_comment'], row, strict=True)) for row in cursor.fetchall()]


class GoTypeAssertionsTable:
    """Accessor class for go_type_assertions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_type_assertions."""
        query = build_query('go_type_assertions', ['file', 'line', 'expr', 'asserted_type', 'is_type_switch', 'containing_func'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'expr', 'asserted_type', 'is_type_switch', 'containing_func'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_type_assertions', ['file', 'line', 'expr', 'asserted_type', 'is_type_switch', 'containing_func'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'expr', 'asserted_type', 'is_type_switch', 'containing_func'], row, strict=True)) for row in cursor.fetchall()]


class GoTypeParamsTable:
    """Accessor class for go_type_params table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_type_params."""
        query = build_query('go_type_params', ['file', 'line', 'parent_name', 'parent_kind', 'param_index', 'param_name', 'type_constraint'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'parent_name', 'parent_kind', 'param_index', 'param_name', 'type_constraint'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_parent_name(cursor: sqlite3.Cursor, parent_name: str) -> list[dict[str, Any]]:
        """Get rows by parent_name."""
        query = build_query('go_type_params', ['file', 'line', 'parent_name', 'parent_kind', 'param_index', 'param_name', 'type_constraint'], where="parent_name = ?")
        cursor.execute(query, (parent_name,))
        return [dict(zip(['file', 'line', 'parent_name', 'parent_kind', 'param_index', 'param_name', 'type_constraint'], row, strict=True)) for row in cursor.fetchall()]


class GoVariablesTable:
    """Accessor class for go_variables table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from go_variables."""
        query = build_query('go_variables', ['file', 'line', 'name', 'type', 'initial_value', 'is_exported', 'is_package_level', 'containing_func'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'name', 'type', 'initial_value', 'is_exported', 'is_package_level', 'containing_func'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('go_variables', ['file', 'line', 'name', 'type', 'initial_value', 'is_exported', 'is_package_level', 'containing_func'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'name', 'type', 'initial_value', 'is_exported', 'is_package_level', 'containing_func'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('go_variables', ['file', 'line', 'name', 'type', 'initial_value', 'is_exported', 'is_package_level', 'containing_func'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'line', 'name', 'type', 'initial_value', 'is_exported', 'is_package_level', 'containing_func'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_package_level(cursor: sqlite3.Cursor, is_package_level: bool) -> list[dict[str, Any]]:
        """Get rows by is_package_level."""
        query = build_query('go_variables', ['file', 'line', 'name', 'type', 'initial_value', 'is_exported', 'is_package_level', 'containing_func'], where="is_package_level = ?")
        cursor.execute(query, (is_package_level,))
        return [dict(zip(['file', 'line', 'name', 'type', 'initial_value', 'is_exported', 'is_package_level', 'containing_func'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_containing_func(cursor: sqlite3.Cursor, containing_func: str) -> list[dict[str, Any]]:
        """Get rows by containing_func."""
        query = build_query('go_variables', ['file', 'line', 'name', 'type', 'initial_value', 'is_exported', 'is_package_level', 'containing_func'], where="containing_func = ?")
        cursor.execute(query, (containing_func,))
        return [dict(zip(['file', 'line', 'name', 'type', 'initial_value', 'is_exported', 'is_package_level', 'containing_func'], row, strict=True)) for row in cursor.fetchall()]


class GraphqlArgDirectivesTable:
    """Accessor class for graphql_arg_directives table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from graphql_arg_directives."""
        query = build_query('graphql_arg_directives', ['id', 'field_id', 'arg_name', 'directive_name', 'arguments_json'])
        cursor.execute(query)
        return [dict(zip(['id', 'field_id', 'arg_name', 'directive_name', 'arguments_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_directive_name(cursor: sqlite3.Cursor, directive_name: str) -> list[dict[str, Any]]:
        """Get rows by directive_name."""
        query = build_query('graphql_arg_directives', ['id', 'field_id', 'arg_name', 'directive_name', 'arguments_json'], where="directive_name = ?")
        cursor.execute(query, (directive_name,))
        return [dict(zip(['id', 'field_id', 'arg_name', 'directive_name', 'arguments_json'], row, strict=True)) for row in cursor.fetchall()]


class GraphqlExecutionEdgesTable:
    """Accessor class for graphql_execution_edges table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from graphql_execution_edges."""
        query = build_query('graphql_execution_edges', ['from_field_id', 'to_symbol_id', 'edge_kind'])
        cursor.execute(query)
        return [dict(zip(['from_field_id', 'to_symbol_id', 'edge_kind'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_from_field_id(cursor: sqlite3.Cursor, from_field_id: int) -> list[dict[str, Any]]:
        """Get rows by from_field_id."""
        query = build_query('graphql_execution_edges', ['from_field_id', 'to_symbol_id', 'edge_kind'], where="from_field_id = ?")
        cursor.execute(query, (from_field_id,))
        return [dict(zip(['from_field_id', 'to_symbol_id', 'edge_kind'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_to_symbol_id(cursor: sqlite3.Cursor, to_symbol_id: int) -> list[dict[str, Any]]:
        """Get rows by to_symbol_id."""
        query = build_query('graphql_execution_edges', ['from_field_id', 'to_symbol_id', 'edge_kind'], where="to_symbol_id = ?")
        cursor.execute(query, (to_symbol_id,))
        return [dict(zip(['from_field_id', 'to_symbol_id', 'edge_kind'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_edge_kind(cursor: sqlite3.Cursor, edge_kind: str) -> list[dict[str, Any]]:
        """Get rows by edge_kind."""
        query = build_query('graphql_execution_edges', ['from_field_id', 'to_symbol_id', 'edge_kind'], where="edge_kind = ?")
        cursor.execute(query, (edge_kind,))
        return [dict(zip(['from_field_id', 'to_symbol_id', 'edge_kind'], row, strict=True)) for row in cursor.fetchall()]


class GraphqlFieldArgsTable:
    """Accessor class for graphql_field_args table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from graphql_field_args."""
        query = build_query('graphql_field_args', ['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable'])
        cursor.execute(query)
        return [dict(zip(['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_id(cursor: sqlite3.Cursor, field_id: int) -> list[dict[str, Any]]:
        """Get rows by field_id."""
        query = build_query('graphql_field_args', ['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable'], where="field_id = ?")
        cursor.execute(query, (field_id,))
        return [dict(zip(['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_arg_type(cursor: sqlite3.Cursor, arg_type: str) -> list[dict[str, Any]]:
        """Get rows by arg_type."""
        query = build_query('graphql_field_args', ['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable'], where="arg_type = ?")
        cursor.execute(query, (arg_type,))
        return [dict(zip(['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable'], row, strict=True)) for row in cursor.fetchall()]


class GraphqlFieldDirectivesTable:
    """Accessor class for graphql_field_directives table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from graphql_field_directives."""
        query = build_query('graphql_field_directives', ['id', 'field_id', 'directive_name', 'arguments_json'])
        cursor.execute(query)
        return [dict(zip(['id', 'field_id', 'directive_name', 'arguments_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_id(cursor: sqlite3.Cursor, field_id: int) -> list[dict[str, Any]]:
        """Get rows by field_id."""
        query = build_query('graphql_field_directives', ['id', 'field_id', 'directive_name', 'arguments_json'], where="field_id = ?")
        cursor.execute(query, (field_id,))
        return [dict(zip(['id', 'field_id', 'directive_name', 'arguments_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_directive_name(cursor: sqlite3.Cursor, directive_name: str) -> list[dict[str, Any]]:
        """Get rows by directive_name."""
        query = build_query('graphql_field_directives', ['id', 'field_id', 'directive_name', 'arguments_json'], where="directive_name = ?")
        cursor.execute(query, (directive_name,))
        return [dict(zip(['id', 'field_id', 'directive_name', 'arguments_json'], row, strict=True)) for row in cursor.fetchall()]


class GraphqlFieldsTable:
    """Accessor class for graphql_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from graphql_fields."""
        query = build_query('graphql_fields', ['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'line', 'column'])
        cursor.execute(query)
        return [dict(zip(['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'line', 'column'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type_id(cursor: sqlite3.Cursor, type_id: int) -> list[dict[str, Any]]:
        """Get rows by type_id."""
        query = build_query('graphql_fields', ['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'line', 'column'], where="type_id = ?")
        cursor.execute(query, (type_id,))
        return [dict(zip(['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'line', 'column'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_name(cursor: sqlite3.Cursor, field_name: str) -> list[dict[str, Any]]:
        """Get rows by field_name."""
        query = build_query('graphql_fields', ['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'line', 'column'], where="field_name = ?")
        cursor.execute(query, (field_name,))
        return [dict(zip(['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'line', 'column'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_return_type(cursor: sqlite3.Cursor, return_type: str) -> list[dict[str, Any]]:
        """Get rows by return_type."""
        query = build_query('graphql_fields', ['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'line', 'column'], where="return_type = ?")
        cursor.execute(query, (return_type,))
        return [dict(zip(['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'line', 'column'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_list(cursor: sqlite3.Cursor, is_list: bool) -> list[dict[str, Any]]:
        """Get rows by is_list."""
        query = build_query('graphql_fields', ['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'line', 'column'], where="is_list = ?")
        cursor.execute(query, (is_list,))
        return [dict(zip(['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'line', 'column'], row, strict=True)) for row in cursor.fetchall()]


class GraphqlFindingsCacheTable:
    """Accessor class for graphql_findings_cache table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from graphql_findings_cache."""
        query = build_query('graphql_findings_cache', ['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'description', 'message', 'confidence', 'provenance'])
        cursor.execute(query)
        return [dict(zip(['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'description', 'message', 'confidence', 'provenance'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_id(cursor: sqlite3.Cursor, field_id: int) -> list[dict[str, Any]]:
        """Get rows by field_id."""
        query = build_query('graphql_findings_cache', ['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'description', 'message', 'confidence', 'provenance'], where="field_id = ?")
        cursor.execute(query, (field_id,))
        return [dict(zip(['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'description', 'message', 'confidence', 'provenance'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resolver_symbol_id(cursor: sqlite3.Cursor, resolver_symbol_id: int) -> list[dict[str, Any]]:
        """Get rows by resolver_symbol_id."""
        query = build_query('graphql_findings_cache', ['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'description', 'message', 'confidence', 'provenance'], where="resolver_symbol_id = ?")
        cursor.execute(query, (resolver_symbol_id,))
        return [dict(zip(['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'description', 'message', 'confidence', 'provenance'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_rule(cursor: sqlite3.Cursor, rule: str) -> list[dict[str, Any]]:
        """Get rows by rule."""
        query = build_query('graphql_findings_cache', ['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'description', 'message', 'confidence', 'provenance'], where="rule = ?")
        cursor.execute(query, (rule,))
        return [dict(zip(['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'description', 'message', 'confidence', 'provenance'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_severity(cursor: sqlite3.Cursor, severity: str) -> list[dict[str, Any]]:
        """Get rows by severity."""
        query = build_query('graphql_findings_cache', ['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'description', 'message', 'confidence', 'provenance'], where="severity = ?")
        cursor.execute(query, (severity,))
        return [dict(zip(['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'description', 'message', 'confidence', 'provenance'], row, strict=True)) for row in cursor.fetchall()]


class GraphqlResolverMappingsTable:
    """Accessor class for graphql_resolver_mappings table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from graphql_resolver_mappings."""
        query = build_query('graphql_resolver_mappings', ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'])
        cursor.execute(query)
        return [dict(zip(['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_id(cursor: sqlite3.Cursor, field_id: int) -> list[dict[str, Any]]:
        """Get rows by field_id."""
        query = build_query('graphql_resolver_mappings', ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], where="field_id = ?")
        cursor.execute(query, (field_id,))
        return [dict(zip(['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resolver_symbol_id(cursor: sqlite3.Cursor, resolver_symbol_id: int) -> list[dict[str, Any]]:
        """Get rows by resolver_symbol_id."""
        query = build_query('graphql_resolver_mappings', ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], where="resolver_symbol_id = ?")
        cursor.execute(query, (resolver_symbol_id,))
        return [dict(zip(['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resolver_path(cursor: sqlite3.Cursor, resolver_path: str) -> list[dict[str, Any]]:
        """Get rows by resolver_path."""
        query = build_query('graphql_resolver_mappings', ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], where="resolver_path = ?")
        cursor.execute(query, (resolver_path,))
        return [dict(zip(['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_binding_style(cursor: sqlite3.Cursor, binding_style: str) -> list[dict[str, Any]]:
        """Get rows by binding_style."""
        query = build_query('graphql_resolver_mappings', ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], where="binding_style = ?")
        cursor.execute(query, (binding_style,))
        return [dict(zip(['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], row, strict=True)) for row in cursor.fetchall()]


class GraphqlResolverParamsTable:
    """Accessor class for graphql_resolver_params table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from graphql_resolver_params."""
        query = build_query('graphql_resolver_params', ['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'])
        cursor.execute(query)
        return [dict(zip(['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resolver_symbol_id(cursor: sqlite3.Cursor, resolver_symbol_id: int) -> list[dict[str, Any]]:
        """Get rows by resolver_symbol_id."""
        query = build_query('graphql_resolver_params', ['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], where="resolver_symbol_id = ?")
        cursor.execute(query, (resolver_symbol_id,))
        return [dict(zip(['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_arg_name(cursor: sqlite3.Cursor, arg_name: str) -> list[dict[str, Any]]:
        """Get rows by arg_name."""
        query = build_query('graphql_resolver_params', ['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], where="arg_name = ?")
        cursor.execute(query, (arg_name,))
        return [dict(zip(['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_param_name(cursor: sqlite3.Cursor, param_name: str) -> list[dict[str, Any]]:
        """Get rows by param_name."""
        query = build_query('graphql_resolver_params', ['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], where="param_name = ?")
        cursor.execute(query, (param_name,))
        return [dict(zip(['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], row, strict=True)) for row in cursor.fetchall()]


class GraphqlSchemasTable:
    """Accessor class for graphql_schemas table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from graphql_schemas."""
        query = build_query('graphql_schemas', ['file_path', 'schema_hash', 'language', 'last_modified'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'schema_hash', 'language', 'last_modified'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_schema_hash(cursor: sqlite3.Cursor, schema_hash: str) -> list[dict[str, Any]]:
        """Get rows by schema_hash."""
        query = build_query('graphql_schemas', ['file_path', 'schema_hash', 'language', 'last_modified'], where="schema_hash = ?")
        cursor.execute(query, (schema_hash,))
        return [dict(zip(['file_path', 'schema_hash', 'language', 'last_modified'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_language(cursor: sqlite3.Cursor, language: str) -> list[dict[str, Any]]:
        """Get rows by language."""
        query = build_query('graphql_schemas', ['file_path', 'schema_hash', 'language', 'last_modified'], where="language = ?")
        cursor.execute(query, (language,))
        return [dict(zip(['file_path', 'schema_hash', 'language', 'last_modified'], row, strict=True)) for row in cursor.fetchall()]


class GraphqlTypesTable:
    """Accessor class for graphql_types table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from graphql_types."""
        query = build_query('graphql_types', ['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'])
        cursor.execute(query)
        return [dict(zip(['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_schema_path(cursor: sqlite3.Cursor, schema_path: str) -> list[dict[str, Any]]:
        """Get rows by schema_path."""
        query = build_query('graphql_types', ['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], where="schema_path = ?")
        cursor.execute(query, (schema_path,))
        return [dict(zip(['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type_name(cursor: sqlite3.Cursor, type_name: str) -> list[dict[str, Any]]:
        """Get rows by type_name."""
        query = build_query('graphql_types', ['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], where="type_name = ?")
        cursor.execute(query, (type_name,))
        return [dict(zip(['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_kind(cursor: sqlite3.Cursor, kind: str) -> list[dict[str, Any]]:
        """Get rows by kind."""
        query = build_query('graphql_types', ['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], where="kind = ?")
        cursor.execute(query, (kind,))
        return [dict(zip(['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], row, strict=True)) for row in cursor.fetchall()]


class ImportSpecifiersTable:
    """Accessor class for import_specifiers table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from import_specifiers."""
        query = build_query('import_specifiers', ['file', 'import_line', 'specifier_name', 'original_name', 'is_default', 'is_namespace', 'is_named'])
        cursor.execute(query)
        return [dict(zip(['file', 'import_line', 'specifier_name', 'original_name', 'is_default', 'is_namespace', 'is_named'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_specifier_name(cursor: sqlite3.Cursor, specifier_name: str) -> list[dict[str, Any]]:
        """Get rows by specifier_name."""
        query = build_query('import_specifiers', ['file', 'import_line', 'specifier_name', 'original_name', 'is_default', 'is_namespace', 'is_named'], where="specifier_name = ?")
        cursor.execute(query, (specifier_name,))
        return [dict(zip(['file', 'import_line', 'specifier_name', 'original_name', 'is_default', 'is_namespace', 'is_named'], row, strict=True)) for row in cursor.fetchall()]


class ImportStyleNamesTable:
    """Accessor class for import_style_names table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from import_style_names."""
        query = build_query('import_style_names', ['id', 'import_file', 'import_line', 'imported_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'import_file', 'import_line', 'imported_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_imported_name(cursor: sqlite3.Cursor, imported_name: str) -> list[dict[str, Any]]:
        """Get rows by imported_name."""
        query = build_query('import_style_names', ['id', 'import_file', 'import_line', 'imported_name'], where="imported_name = ?")
        cursor.execute(query, (imported_name,))
        return [dict(zip(['id', 'import_file', 'import_line', 'imported_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_import_file(cursor: sqlite3.Cursor, import_file: str) -> list[dict[str, Any]]:
        """Get rows by import_file."""
        query = build_query('import_style_names', ['id', 'import_file', 'import_line', 'imported_name'], where="import_file = ?")
        cursor.execute(query, (import_file,))
        return [dict(zip(['id', 'import_file', 'import_line', 'imported_name'], row, strict=True)) for row in cursor.fetchall()]


class ImportStylesTable:
    """Accessor class for import_styles table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from import_styles."""
        query = build_query('import_styles', ['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement', 'resolved_path'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement', 'resolved_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('import_styles', ['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement', 'resolved_path'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement', 'resolved_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_package(cursor: sqlite3.Cursor, package: str) -> list[dict[str, Any]]:
        """Get rows by package."""
        query = build_query('import_styles', ['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement', 'resolved_path'], where="package = ?")
        cursor.execute(query, (package,))
        return [dict(zip(['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement', 'resolved_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_import_style(cursor: sqlite3.Cursor, import_style: str) -> list[dict[str, Any]]:
        """Get rows by import_style."""
        query = build_query('import_styles', ['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement', 'resolved_path'], where="import_style = ?")
        cursor.execute(query, (import_style,))
        return [dict(zip(['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement', 'resolved_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resolved_path(cursor: sqlite3.Cursor, resolved_path: str) -> list[dict[str, Any]]:
        """Get rows by resolved_path."""
        query = build_query('import_styles', ['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement', 'resolved_path'], where="resolved_path = ?")
        cursor.execute(query, (resolved_path,))
        return [dict(zip(['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement', 'resolved_path'], row, strict=True)) for row in cursor.fetchall()]


class JwtPatternsTable:
    """Accessor class for jwt_patterns table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from jwt_patterns."""
        query = build_query('jwt_patterns', ['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('jwt_patterns', ['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_pattern_type(cursor: sqlite3.Cursor, pattern_type: str) -> list[dict[str, Any]]:
        """Get rows by pattern_type."""
        query = build_query('jwt_patterns', ['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], where="pattern_type = ?")
        cursor.execute(query, (pattern_type,))
        return [dict(zip(['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_secret_source(cursor: sqlite3.Cursor, secret_source: str) -> list[dict[str, Any]]:
        """Get rows by secret_source."""
        query = build_query('jwt_patterns', ['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], where="secret_source = ?")
        cursor.execute(query, (secret_source,))
        return [dict(zip(['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], row, strict=True)) for row in cursor.fetchall()]


class LockAnalysisTable:
    """Accessor class for lock_analysis table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from lock_analysis."""
        query = build_query('lock_analysis', ['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('lock_analysis', ['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_lock_type(cursor: sqlite3.Cursor, lock_type: str) -> list[dict[str, Any]]:
        """Get rows by lock_type."""
        query = build_query('lock_analysis', ['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'], where="lock_type = ?")
        cursor.execute(query, (lock_type,))
        return [dict(zip(['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'], row, strict=True)) for row in cursor.fetchall()]


class NginxConfigsTable:
    """Accessor class for nginx_configs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from nginx_configs."""
        query = build_query('nginx_configs', ['file_path', 'block_type', 'block_context', 'directives', 'level'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'block_type', 'block_context', 'directives', 'level'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('nginx_configs', ['file_path', 'block_type', 'block_context', 'directives', 'level'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'block_type', 'block_context', 'directives', 'level'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_block_type(cursor: sqlite3.Cursor, block_type: str) -> list[dict[str, Any]]:
        """Get rows by block_type."""
        query = build_query('nginx_configs', ['file_path', 'block_type', 'block_context', 'directives', 'level'], where="block_type = ?")
        cursor.execute(query, (block_type,))
        return [dict(zip(['file_path', 'block_type', 'block_context', 'directives', 'level'], row, strict=True)) for row in cursor.fetchall()]


class ObjectLiteralsTable:
    """Accessor class for object_literals table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from object_literals."""
        query = build_query('object_literals', ['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('object_literals', ['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_variable_name(cursor: sqlite3.Cursor, variable_name: str) -> list[dict[str, Any]]:
        """Get rows by variable_name."""
        query = build_query('object_literals', ['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], where="variable_name = ?")
        cursor.execute(query, (variable_name,))
        return [dict(zip(['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_value(cursor: sqlite3.Cursor, property_value: str) -> list[dict[str, Any]]:
        """Get rows by property_value."""
        query = build_query('object_literals', ['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], where="property_value = ?")
        cursor.execute(query, (property_value,))
        return [dict(zip(['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_type(cursor: sqlite3.Cursor, property_type: str) -> list[dict[str, Any]]:
        """Get rows by property_type."""
        query = build_query('object_literals', ['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], where="property_type = ?")
        cursor.execute(query, (property_type,))
        return [dict(zip(['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], row, strict=True)) for row in cursor.fetchall()]


class OrmQueriesTable:
    """Accessor class for orm_queries table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from orm_queries."""
        query = build_query('orm_queries', ['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('orm_queries', ['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_query_type(cursor: sqlite3.Cursor, query_type: str) -> list[dict[str, Any]]:
        """Get rows by query_type."""
        query = build_query('orm_queries', ['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'], where="query_type = ?")
        cursor.execute(query, (query_type,))
        return [dict(zip(['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'], row, strict=True)) for row in cursor.fetchall()]


class OrmRelationshipsTable:
    """Accessor class for orm_relationships table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from orm_relationships."""
        query = build_query('orm_relationships', ['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('orm_relationships', ['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_model(cursor: sqlite3.Cursor, source_model: str) -> list[dict[str, Any]]:
        """Get rows by source_model."""
        query = build_query('orm_relationships', ['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], where="source_model = ?")
        cursor.execute(query, (source_model,))
        return [dict(zip(['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_model(cursor: sqlite3.Cursor, target_model: str) -> list[dict[str, Any]]:
        """Get rows by target_model."""
        query = build_query('orm_relationships', ['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], where="target_model = ?")
        cursor.execute(query, (target_model,))
        return [dict(zip(['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_relationship_type(cursor: sqlite3.Cursor, relationship_type: str) -> list[dict[str, Any]]:
        """Get rows by relationship_type."""
        query = build_query('orm_relationships', ['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], where="relationship_type = ?")
        cursor.execute(query, (relationship_type,))
        return [dict(zip(['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], row, strict=True)) for row in cursor.fetchall()]


class PackageConfigsTable:
    """Accessor class for package_configs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from package_configs."""
        query = build_query('package_configs', ['file_path', 'package_name', 'version', 'private'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'package_name', 'version', 'private'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('package_configs', ['file_path', 'package_name', 'version', 'private'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'package_name', 'version', 'private'], row, strict=True)) for row in cursor.fetchall()]


class PackageDependenciesTable:
    """Accessor class for package_dependencies table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from package_dependencies."""
        query = build_query('package_dependencies', ['id', 'file_path', 'name', 'version_spec', 'is_dev', 'is_peer'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'name', 'version_spec', 'is_dev', 'is_peer'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('package_dependencies', ['id', 'file_path', 'name', 'version_spec', 'is_dev', 'is_peer'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'file_path', 'name', 'version_spec', 'is_dev', 'is_peer'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('package_dependencies', ['id', 'file_path', 'name', 'version_spec', 'is_dev', 'is_peer'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['id', 'file_path', 'name', 'version_spec', 'is_dev', 'is_peer'], row, strict=True)) for row in cursor.fetchall()]


class PackageEnginesTable:
    """Accessor class for package_engines table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from package_engines."""
        query = build_query('package_engines', ['id', 'file_path', 'engine_name', 'version_spec'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'engine_name', 'version_spec'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('package_engines', ['id', 'file_path', 'engine_name', 'version_spec'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'file_path', 'engine_name', 'version_spec'], row, strict=True)) for row in cursor.fetchall()]


class PackageScriptsTable:
    """Accessor class for package_scripts table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from package_scripts."""
        query = build_query('package_scripts', ['id', 'file_path', 'script_name', 'script_command'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'script_name', 'script_command'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('package_scripts', ['id', 'file_path', 'script_name', 'script_command'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'file_path', 'script_name', 'script_command'], row, strict=True)) for row in cursor.fetchall()]


class PackageWorkspacesTable:
    """Accessor class for package_workspaces table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from package_workspaces."""
        query = build_query('package_workspaces', ['id', 'file_path', 'workspace_path'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'workspace_path'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('package_workspaces', ['id', 'file_path', 'workspace_path'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'file_path', 'workspace_path'], row, strict=True)) for row in cursor.fetchall()]


class PlanJobsTable:
    """Accessor class for plan_jobs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from plan_jobs."""
        query = build_query('plan_jobs', ['id', 'task_id', 'job_number', 'description', 'completed', 'is_audit_job', 'created_at'])
        cursor.execute(query)
        return [dict(zip(['id', 'task_id', 'job_number', 'description', 'completed', 'is_audit_job', 'created_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_task_id(cursor: sqlite3.Cursor, task_id: int) -> list[dict[str, Any]]:
        """Get rows by task_id."""
        query = build_query('plan_jobs', ['id', 'task_id', 'job_number', 'description', 'completed', 'is_audit_job', 'created_at'], where="task_id = ?")
        cursor.execute(query, (task_id,))
        return [dict(zip(['id', 'task_id', 'job_number', 'description', 'completed', 'is_audit_job', 'created_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_completed(cursor: sqlite3.Cursor, completed: int) -> list[dict[str, Any]]:
        """Get rows by completed."""
        query = build_query('plan_jobs', ['id', 'task_id', 'job_number', 'description', 'completed', 'is_audit_job', 'created_at'], where="completed = ?")
        cursor.execute(query, (completed,))
        return [dict(zip(['id', 'task_id', 'job_number', 'description', 'completed', 'is_audit_job', 'created_at'], row, strict=True)) for row in cursor.fetchall()]


class PlanPhasesTable:
    """Accessor class for plan_phases table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from plan_phases."""
        query = build_query('plan_phases', ['id', 'plan_id', 'phase_number', 'title', 'description', 'success_criteria', 'status', 'created_at'])
        cursor.execute(query)
        return [dict(zip(['id', 'plan_id', 'phase_number', 'title', 'description', 'success_criteria', 'status', 'created_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_plan_id(cursor: sqlite3.Cursor, plan_id: int) -> list[dict[str, Any]]:
        """Get rows by plan_id."""
        query = build_query('plan_phases', ['id', 'plan_id', 'phase_number', 'title', 'description', 'success_criteria', 'status', 'created_at'], where="plan_id = ?")
        cursor.execute(query, (plan_id,))
        return [dict(zip(['id', 'plan_id', 'phase_number', 'title', 'description', 'success_criteria', 'status', 'created_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_status(cursor: sqlite3.Cursor, status: str) -> list[dict[str, Any]]:
        """Get rows by status."""
        query = build_query('plan_phases', ['id', 'plan_id', 'phase_number', 'title', 'description', 'success_criteria', 'status', 'created_at'], where="status = ?")
        cursor.execute(query, (status,))
        return [dict(zip(['id', 'plan_id', 'phase_number', 'title', 'description', 'success_criteria', 'status', 'created_at'], row, strict=True)) for row in cursor.fetchall()]


class PlanSpecsTable:
    """Accessor class for plan_specs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from plan_specs."""
        query = build_query('plan_specs', ['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'])
        cursor.execute(query)
        return [dict(zip(['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_plan_id(cursor: sqlite3.Cursor, plan_id: int) -> list[dict[str, Any]]:
        """Get rows by plan_id."""
        query = build_query('plan_specs', ['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'], where="plan_id = ?")
        cursor.execute(query, (plan_id,))
        return [dict(zip(['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_spec_type(cursor: sqlite3.Cursor, spec_type: str) -> list[dict[str, Any]]:
        """Get rows by spec_type."""
        query = build_query('plan_specs', ['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'], where="spec_type = ?")
        cursor.execute(query, (spec_type,))
        return [dict(zip(['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'], row, strict=True)) for row in cursor.fetchall()]


class PlanTasksTable:
    """Accessor class for plan_tasks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from plan_tasks."""
        query = build_query('plan_tasks', ['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'])
        cursor.execute(query)
        return [dict(zip(['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_plan_id(cursor: sqlite3.Cursor, plan_id: int) -> list[dict[str, Any]]:
        """Get rows by plan_id."""
        query = build_query('plan_tasks', ['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], where="plan_id = ?")
        cursor.execute(query, (plan_id,))
        return [dict(zip(['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_phase_id(cursor: sqlite3.Cursor, phase_id: int) -> list[dict[str, Any]]:
        """Get rows by phase_id."""
        query = build_query('plan_tasks', ['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], where="phase_id = ?")
        cursor.execute(query, (phase_id,))
        return [dict(zip(['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_status(cursor: sqlite3.Cursor, status: str) -> list[dict[str, Any]]:
        """Get rows by status."""
        query = build_query('plan_tasks', ['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], where="status = ?")
        cursor.execute(query, (status,))
        return [dict(zip(['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_audit_status(cursor: sqlite3.Cursor, audit_status: str) -> list[dict[str, Any]]:
        """Get rows by audit_status."""
        query = build_query('plan_tasks', ['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], where="audit_status = ?")
        cursor.execute(query, (audit_status,))
        return [dict(zip(['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_spec_id(cursor: sqlite3.Cursor, spec_id: int) -> list[dict[str, Any]]:
        """Get rows by spec_id."""
        query = build_query('plan_tasks', ['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], where="spec_id = ?")
        cursor.execute(query, (spec_id,))
        return [dict(zip(['id', 'plan_id', 'phase_id', 'task_number', 'title', 'description', 'status', 'audit_status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], row, strict=True)) for row in cursor.fetchall()]


class PlansTable:
    """Accessor class for plans table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from plans."""
        query = build_query('plans', ['id', 'name', 'description', 'created_at', 'status', 'metadata_json'])
        cursor.execute(query)
        return [dict(zip(['id', 'name', 'description', 'created_at', 'status', 'metadata_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_status(cursor: sqlite3.Cursor, status: str) -> list[dict[str, Any]]:
        """Get rows by status."""
        query = build_query('plans', ['id', 'name', 'description', 'created_at', 'status', 'metadata_json'], where="status = ?")
        cursor.execute(query, (status,))
        return [dict(zip(['id', 'name', 'description', 'created_at', 'status', 'metadata_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_created_at(cursor: sqlite3.Cursor, created_at: str) -> list[dict[str, Any]]:
        """Get rows by created_at."""
        query = build_query('plans', ['id', 'name', 'description', 'created_at', 'status', 'metadata_json'], where="created_at = ?")
        cursor.execute(query, (created_at,))
        return [dict(zip(['id', 'name', 'description', 'created_at', 'status', 'metadata_json'], row, strict=True)) for row in cursor.fetchall()]


class PrismaModelsTable:
    """Accessor class for prisma_models table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from prisma_models."""
        query = build_query('prisma_models', ['model_name', 'field_name', 'field_type', 'is_indexed', 'is_unique', 'is_relation'])
        cursor.execute(query)
        return [dict(zip(['model_name', 'field_name', 'field_type', 'is_indexed', 'is_unique', 'is_relation'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_indexed(cursor: sqlite3.Cursor, is_indexed: bool) -> list[dict[str, Any]]:
        """Get rows by is_indexed."""
        query = build_query('prisma_models', ['model_name', 'field_name', 'field_type', 'is_indexed', 'is_unique', 'is_relation'], where="is_indexed = ?")
        cursor.execute(query, (is_indexed,))
        return [dict(zip(['model_name', 'field_name', 'field_type', 'is_indexed', 'is_unique', 'is_relation'], row, strict=True)) for row in cursor.fetchall()]


class PythonBranchesTable:
    """Accessor class for python_branches table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_branches."""
        query = build_query('python_branches', ['id', 'file', 'line', 'branch_kind', 'branch_type', 'has_else', 'has_elif', 'chain_length', 'has_complex_condition', 'nesting_level', 'case_count', 'has_guards', 'has_wildcard', 'pattern_types', 'exception_types', 'handling_strategy', 'variable_name', 'exception_type', 'is_re_raise', 'from_exception', 'message', 'condition', 'has_cleanup', 'cleanup_calls', 'in_function'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'branch_kind', 'branch_type', 'has_else', 'has_elif', 'chain_length', 'has_complex_condition', 'nesting_level', 'case_count', 'has_guards', 'has_wildcard', 'pattern_types', 'exception_types', 'handling_strategy', 'variable_name', 'exception_type', 'is_re_raise', 'from_exception', 'message', 'condition', 'has_cleanup', 'cleanup_calls', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_branches', ['id', 'file', 'line', 'branch_kind', 'branch_type', 'has_else', 'has_elif', 'chain_length', 'has_complex_condition', 'nesting_level', 'case_count', 'has_guards', 'has_wildcard', 'pattern_types', 'exception_types', 'handling_strategy', 'variable_name', 'exception_type', 'is_re_raise', 'from_exception', 'message', 'condition', 'has_cleanup', 'cleanup_calls', 'in_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'branch_kind', 'branch_type', 'has_else', 'has_elif', 'chain_length', 'has_complex_condition', 'nesting_level', 'case_count', 'has_guards', 'has_wildcard', 'pattern_types', 'exception_types', 'handling_strategy', 'variable_name', 'exception_type', 'is_re_raise', 'from_exception', 'message', 'condition', 'has_cleanup', 'cleanup_calls', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_branch_kind(cursor: sqlite3.Cursor, branch_kind: str) -> list[dict[str, Any]]:
        """Get rows by branch_kind."""
        query = build_query('python_branches', ['id', 'file', 'line', 'branch_kind', 'branch_type', 'has_else', 'has_elif', 'chain_length', 'has_complex_condition', 'nesting_level', 'case_count', 'has_guards', 'has_wildcard', 'pattern_types', 'exception_types', 'handling_strategy', 'variable_name', 'exception_type', 'is_re_raise', 'from_exception', 'message', 'condition', 'has_cleanup', 'cleanup_calls', 'in_function'], where="branch_kind = ?")
        cursor.execute(query, (branch_kind,))
        return [dict(zip(['id', 'file', 'line', 'branch_kind', 'branch_type', 'has_else', 'has_elif', 'chain_length', 'has_complex_condition', 'nesting_level', 'case_count', 'has_guards', 'has_wildcard', 'pattern_types', 'exception_types', 'handling_strategy', 'variable_name', 'exception_type', 'is_re_raise', 'from_exception', 'message', 'condition', 'has_cleanup', 'cleanup_calls', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_branches', ['id', 'file', 'line', 'branch_kind', 'branch_type', 'has_else', 'has_elif', 'chain_length', 'has_complex_condition', 'nesting_level', 'case_count', 'has_guards', 'has_wildcard', 'pattern_types', 'exception_types', 'handling_strategy', 'variable_name', 'exception_type', 'is_re_raise', 'from_exception', 'message', 'condition', 'has_cleanup', 'cleanup_calls', 'in_function'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'branch_kind', 'branch_type', 'has_else', 'has_elif', 'chain_length', 'has_complex_condition', 'nesting_level', 'case_count', 'has_guards', 'has_wildcard', 'pattern_types', 'exception_types', 'handling_strategy', 'variable_name', 'exception_type', 'is_re_raise', 'from_exception', 'message', 'condition', 'has_cleanup', 'cleanup_calls', 'in_function'], row, strict=True)) for row in cursor.fetchall()]


class PythonBuildRequiresTable:
    """Accessor class for python_build_requires table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_build_requires."""
        query = build_query('python_build_requires', ['file_path', 'name', 'version_spec'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'name', 'version_spec'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('python_build_requires', ['file_path', 'name', 'version_spec'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'name', 'version_spec'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('python_build_requires', ['file_path', 'name', 'version_spec'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file_path', 'name', 'version_spec'], row, strict=True)) for row in cursor.fetchall()]


class PythonClassFeaturesTable:
    """Accessor class for python_class_features table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_class_features."""
        query = build_query('python_class_features', ['id', 'file', 'line', 'feature_kind', 'feature_type', 'class_name', 'name', 'in_class', 'metaclass_name', 'is_definition', 'field_count', 'frozen', 'enum_name', 'enum_type', 'member_count', 'slot_count', 'abstract_method_count', 'method_name', 'method_type', 'category', 'visibility', 'is_name_mangled', 'decorator', 'decorator_type', 'has_arguments'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'feature_kind', 'feature_type', 'class_name', 'name', 'in_class', 'metaclass_name', 'is_definition', 'field_count', 'frozen', 'enum_name', 'enum_type', 'member_count', 'slot_count', 'abstract_method_count', 'method_name', 'method_type', 'category', 'visibility', 'is_name_mangled', 'decorator', 'decorator_type', 'has_arguments'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_class_features', ['id', 'file', 'line', 'feature_kind', 'feature_type', 'class_name', 'name', 'in_class', 'metaclass_name', 'is_definition', 'field_count', 'frozen', 'enum_name', 'enum_type', 'member_count', 'slot_count', 'abstract_method_count', 'method_name', 'method_type', 'category', 'visibility', 'is_name_mangled', 'decorator', 'decorator_type', 'has_arguments'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'feature_kind', 'feature_type', 'class_name', 'name', 'in_class', 'metaclass_name', 'is_definition', 'field_count', 'frozen', 'enum_name', 'enum_type', 'member_count', 'slot_count', 'abstract_method_count', 'method_name', 'method_type', 'category', 'visibility', 'is_name_mangled', 'decorator', 'decorator_type', 'has_arguments'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_feature_kind(cursor: sqlite3.Cursor, feature_kind: str) -> list[dict[str, Any]]:
        """Get rows by feature_kind."""
        query = build_query('python_class_features', ['id', 'file', 'line', 'feature_kind', 'feature_type', 'class_name', 'name', 'in_class', 'metaclass_name', 'is_definition', 'field_count', 'frozen', 'enum_name', 'enum_type', 'member_count', 'slot_count', 'abstract_method_count', 'method_name', 'method_type', 'category', 'visibility', 'is_name_mangled', 'decorator', 'decorator_type', 'has_arguments'], where="feature_kind = ?")
        cursor.execute(query, (feature_kind,))
        return [dict(zip(['id', 'file', 'line', 'feature_kind', 'feature_type', 'class_name', 'name', 'in_class', 'metaclass_name', 'is_definition', 'field_count', 'frozen', 'enum_name', 'enum_type', 'member_count', 'slot_count', 'abstract_method_count', 'method_name', 'method_type', 'category', 'visibility', 'is_name_mangled', 'decorator', 'decorator_type', 'has_arguments'], row, strict=True)) for row in cursor.fetchall()]


class PythonCollectionsTable:
    """Accessor class for python_collections table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_collections."""
        query = build_query('python_collections', ['id', 'file', 'line', 'collection_kind', 'collection_type', 'operation', 'method', 'in_function', 'has_default', 'mutates_in_place', 'builtin', 'has_key'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'collection_kind', 'collection_type', 'operation', 'method', 'in_function', 'has_default', 'mutates_in_place', 'builtin', 'has_key'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_collections', ['id', 'file', 'line', 'collection_kind', 'collection_type', 'operation', 'method', 'in_function', 'has_default', 'mutates_in_place', 'builtin', 'has_key'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'collection_kind', 'collection_type', 'operation', 'method', 'in_function', 'has_default', 'mutates_in_place', 'builtin', 'has_key'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_collection_kind(cursor: sqlite3.Cursor, collection_kind: str) -> list[dict[str, Any]]:
        """Get rows by collection_kind."""
        query = build_query('python_collections', ['id', 'file', 'line', 'collection_kind', 'collection_type', 'operation', 'method', 'in_function', 'has_default', 'mutates_in_place', 'builtin', 'has_key'], where="collection_kind = ?")
        cursor.execute(query, (collection_kind,))
        return [dict(zip(['id', 'file', 'line', 'collection_kind', 'collection_type', 'operation', 'method', 'in_function', 'has_default', 'mutates_in_place', 'builtin', 'has_key'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_collections', ['id', 'file', 'line', 'collection_kind', 'collection_type', 'operation', 'method', 'in_function', 'has_default', 'mutates_in_place', 'builtin', 'has_key'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'collection_kind', 'collection_type', 'operation', 'method', 'in_function', 'has_default', 'mutates_in_place', 'builtin', 'has_key'], row, strict=True)) for row in cursor.fetchall()]


class PythonComprehensionsTable:
    """Accessor class for python_comprehensions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_comprehensions."""
        query = build_query('python_comprehensions', ['id', 'file', 'line', 'comp_kind', 'comp_type', 'iteration_var', 'iteration_source', 'result_expr', 'filter_expr', 'has_filter', 'nesting_level', 'in_function'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'comp_kind', 'comp_type', 'iteration_var', 'iteration_source', 'result_expr', 'filter_expr', 'has_filter', 'nesting_level', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_comprehensions', ['id', 'file', 'line', 'comp_kind', 'comp_type', 'iteration_var', 'iteration_source', 'result_expr', 'filter_expr', 'has_filter', 'nesting_level', 'in_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'comp_kind', 'comp_type', 'iteration_var', 'iteration_source', 'result_expr', 'filter_expr', 'has_filter', 'nesting_level', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_comp_kind(cursor: sqlite3.Cursor, comp_kind: str) -> list[dict[str, Any]]:
        """Get rows by comp_kind."""
        query = build_query('python_comprehensions', ['id', 'file', 'line', 'comp_kind', 'comp_type', 'iteration_var', 'iteration_source', 'result_expr', 'filter_expr', 'has_filter', 'nesting_level', 'in_function'], where="comp_kind = ?")
        cursor.execute(query, (comp_kind,))
        return [dict(zip(['id', 'file', 'line', 'comp_kind', 'comp_type', 'iteration_var', 'iteration_source', 'result_expr', 'filter_expr', 'has_filter', 'nesting_level', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_comprehensions', ['id', 'file', 'line', 'comp_kind', 'comp_type', 'iteration_var', 'iteration_source', 'result_expr', 'filter_expr', 'has_filter', 'nesting_level', 'in_function'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'comp_kind', 'comp_type', 'iteration_var', 'iteration_source', 'result_expr', 'filter_expr', 'has_filter', 'nesting_level', 'in_function'], row, strict=True)) for row in cursor.fetchall()]


class PythonControlStatementsTable:
    """Accessor class for python_control_statements table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_control_statements."""
        query = build_query('python_control_statements', ['id', 'file', 'line', 'statement_kind', 'statement_type', 'loop_type', 'condition_type', 'has_message', 'target_count', 'target_type', 'context_count', 'has_alias', 'is_async', 'in_function'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'statement_kind', 'statement_type', 'loop_type', 'condition_type', 'has_message', 'target_count', 'target_type', 'context_count', 'has_alias', 'is_async', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_control_statements', ['id', 'file', 'line', 'statement_kind', 'statement_type', 'loop_type', 'condition_type', 'has_message', 'target_count', 'target_type', 'context_count', 'has_alias', 'is_async', 'in_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'statement_kind', 'statement_type', 'loop_type', 'condition_type', 'has_message', 'target_count', 'target_type', 'context_count', 'has_alias', 'is_async', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_statement_kind(cursor: sqlite3.Cursor, statement_kind: str) -> list[dict[str, Any]]:
        """Get rows by statement_kind."""
        query = build_query('python_control_statements', ['id', 'file', 'line', 'statement_kind', 'statement_type', 'loop_type', 'condition_type', 'has_message', 'target_count', 'target_type', 'context_count', 'has_alias', 'is_async', 'in_function'], where="statement_kind = ?")
        cursor.execute(query, (statement_kind,))
        return [dict(zip(['id', 'file', 'line', 'statement_kind', 'statement_type', 'loop_type', 'condition_type', 'has_message', 'target_count', 'target_type', 'context_count', 'has_alias', 'is_async', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_control_statements', ['id', 'file', 'line', 'statement_kind', 'statement_type', 'loop_type', 'condition_type', 'has_message', 'target_count', 'target_type', 'context_count', 'has_alias', 'is_async', 'in_function'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'statement_kind', 'statement_type', 'loop_type', 'condition_type', 'has_message', 'target_count', 'target_type', 'context_count', 'has_alias', 'is_async', 'in_function'], row, strict=True)) for row in cursor.fetchall()]


class PythonDecoratorsTable:
    """Accessor class for python_decorators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_decorators."""
        query = build_query('python_decorators', ['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_decorators', ['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_decorator_type(cursor: sqlite3.Cursor, decorator_type: str) -> list[dict[str, Any]]:
        """Get rows by decorator_type."""
        query = build_query('python_decorators', ['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], where="decorator_type = ?")
        cursor.execute(query, (decorator_type,))
        return [dict(zip(['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_name(cursor: sqlite3.Cursor, target_name: str) -> list[dict[str, Any]]:
        """Get rows by target_name."""
        query = build_query('python_decorators', ['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], where="target_name = ?")
        cursor.execute(query, (target_name,))
        return [dict(zip(['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], row, strict=True)) for row in cursor.fetchall()]


class PythonDescriptorsTable:
    """Accessor class for python_descriptors table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_descriptors."""
        query = build_query('python_descriptors', ['id', 'file', 'line', 'descriptor_kind', 'descriptor_type', 'name', 'class_name', 'in_class', 'has_get', 'has_set', 'has_delete', 'is_data_descriptor', 'property_name', 'access_type', 'has_computation', 'has_validation', 'method_name', 'is_functools'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'descriptor_kind', 'descriptor_type', 'name', 'class_name', 'in_class', 'has_get', 'has_set', 'has_delete', 'is_data_descriptor', 'property_name', 'access_type', 'has_computation', 'has_validation', 'method_name', 'is_functools'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_descriptors', ['id', 'file', 'line', 'descriptor_kind', 'descriptor_type', 'name', 'class_name', 'in_class', 'has_get', 'has_set', 'has_delete', 'is_data_descriptor', 'property_name', 'access_type', 'has_computation', 'has_validation', 'method_name', 'is_functools'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'descriptor_kind', 'descriptor_type', 'name', 'class_name', 'in_class', 'has_get', 'has_set', 'has_delete', 'is_data_descriptor', 'property_name', 'access_type', 'has_computation', 'has_validation', 'method_name', 'is_functools'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_descriptor_kind(cursor: sqlite3.Cursor, descriptor_kind: str) -> list[dict[str, Any]]:
        """Get rows by descriptor_kind."""
        query = build_query('python_descriptors', ['id', 'file', 'line', 'descriptor_kind', 'descriptor_type', 'name', 'class_name', 'in_class', 'has_get', 'has_set', 'has_delete', 'is_data_descriptor', 'property_name', 'access_type', 'has_computation', 'has_validation', 'method_name', 'is_functools'], where="descriptor_kind = ?")
        cursor.execute(query, (descriptor_kind,))
        return [dict(zip(['id', 'file', 'line', 'descriptor_kind', 'descriptor_type', 'name', 'class_name', 'in_class', 'has_get', 'has_set', 'has_delete', 'is_data_descriptor', 'property_name', 'access_type', 'has_computation', 'has_validation', 'method_name', 'is_functools'], row, strict=True)) for row in cursor.fetchall()]


class PythonDjangoMiddlewareTable:
    """Accessor class for python_django_middleware table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_django_middleware."""
        query = build_query('python_django_middleware', ['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_django_middleware', ['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_process_request(cursor: sqlite3.Cursor, has_process_request: bool) -> list[dict[str, Any]]:
        """Get rows by has_process_request."""
        query = build_query('python_django_middleware', ['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], where="has_process_request = ?")
        cursor.execute(query, (has_process_request,))
        return [dict(zip(['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row, strict=True)) for row in cursor.fetchall()]


class PythonDjangoViewsTable:
    """Accessor class for python_django_views table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_django_views."""
        query = build_query('python_django_views', ['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_django_views', ['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_view_type(cursor: sqlite3.Cursor, view_type: str) -> list[dict[str, Any]]:
        """Get rows by view_type."""
        query = build_query('python_django_views', ['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], where="view_type = ?")
        cursor.execute(query, (view_type,))
        return [dict(zip(['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> list[dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('python_django_views', ['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_permission_check(cursor: sqlite3.Cursor, has_permission_check: bool) -> list[dict[str, Any]]:
        """Get rows by has_permission_check."""
        query = build_query('python_django_views', ['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], where="has_permission_check = ?")
        cursor.execute(query, (has_permission_check,))
        return [dict(zip(['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], row, strict=True)) for row in cursor.fetchall()]


class PythonExpressionsTable:
    """Accessor class for python_expressions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_expressions."""
        query = build_query('python_expressions', ['id', 'file', 'line', 'expression_kind', 'expression_type', 'in_function', 'target', 'has_start', 'has_stop', 'has_step', 'is_assignment', 'element_count', 'operation', 'has_rest', 'target_count', 'unpack_type', 'pattern', 'uses_is', 'format_type', 'has_expressions', 'var_count', 'context', 'has_globals', 'has_locals', 'generator_function', 'yield_expr', 'yield_type', 'in_loop', 'condition', 'awaited_expr', 'containing_function'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'expression_kind', 'expression_type', 'in_function', 'target', 'has_start', 'has_stop', 'has_step', 'is_assignment', 'element_count', 'operation', 'has_rest', 'target_count', 'unpack_type', 'pattern', 'uses_is', 'format_type', 'has_expressions', 'var_count', 'context', 'has_globals', 'has_locals', 'generator_function', 'yield_expr', 'yield_type', 'in_loop', 'condition', 'awaited_expr', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_expressions', ['id', 'file', 'line', 'expression_kind', 'expression_type', 'in_function', 'target', 'has_start', 'has_stop', 'has_step', 'is_assignment', 'element_count', 'operation', 'has_rest', 'target_count', 'unpack_type', 'pattern', 'uses_is', 'format_type', 'has_expressions', 'var_count', 'context', 'has_globals', 'has_locals', 'generator_function', 'yield_expr', 'yield_type', 'in_loop', 'condition', 'awaited_expr', 'containing_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'expression_kind', 'expression_type', 'in_function', 'target', 'has_start', 'has_stop', 'has_step', 'is_assignment', 'element_count', 'operation', 'has_rest', 'target_count', 'unpack_type', 'pattern', 'uses_is', 'format_type', 'has_expressions', 'var_count', 'context', 'has_globals', 'has_locals', 'generator_function', 'yield_expr', 'yield_type', 'in_loop', 'condition', 'awaited_expr', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_expression_kind(cursor: sqlite3.Cursor, expression_kind: str) -> list[dict[str, Any]]:
        """Get rows by expression_kind."""
        query = build_query('python_expressions', ['id', 'file', 'line', 'expression_kind', 'expression_type', 'in_function', 'target', 'has_start', 'has_stop', 'has_step', 'is_assignment', 'element_count', 'operation', 'has_rest', 'target_count', 'unpack_type', 'pattern', 'uses_is', 'format_type', 'has_expressions', 'var_count', 'context', 'has_globals', 'has_locals', 'generator_function', 'yield_expr', 'yield_type', 'in_loop', 'condition', 'awaited_expr', 'containing_function'], where="expression_kind = ?")
        cursor.execute(query, (expression_kind,))
        return [dict(zip(['id', 'file', 'line', 'expression_kind', 'expression_type', 'in_function', 'target', 'has_start', 'has_stop', 'has_step', 'is_assignment', 'element_count', 'operation', 'has_rest', 'target_count', 'unpack_type', 'pattern', 'uses_is', 'format_type', 'has_expressions', 'var_count', 'context', 'has_globals', 'has_locals', 'generator_function', 'yield_expr', 'yield_type', 'in_loop', 'condition', 'awaited_expr', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_expressions', ['id', 'file', 'line', 'expression_kind', 'expression_type', 'in_function', 'target', 'has_start', 'has_stop', 'has_step', 'is_assignment', 'element_count', 'operation', 'has_rest', 'target_count', 'unpack_type', 'pattern', 'uses_is', 'format_type', 'has_expressions', 'var_count', 'context', 'has_globals', 'has_locals', 'generator_function', 'yield_expr', 'yield_type', 'in_loop', 'condition', 'awaited_expr', 'containing_function'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'expression_kind', 'expression_type', 'in_function', 'target', 'has_start', 'has_stop', 'has_step', 'is_assignment', 'element_count', 'operation', 'has_rest', 'target_count', 'unpack_type', 'pattern', 'uses_is', 'format_type', 'has_expressions', 'var_count', 'context', 'has_globals', 'has_locals', 'generator_function', 'yield_expr', 'yield_type', 'in_loop', 'condition', 'awaited_expr', 'containing_function'], row, strict=True)) for row in cursor.fetchall()]


class PythonFixtureParamsTable:
    """Accessor class for python_fixture_params table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_fixture_params."""
        query = build_query('python_fixture_params', ['id', 'file', 'fixture_id', 'param_name', 'param_value', 'param_order'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'fixture_id', 'param_name', 'param_value', 'param_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_fixture_params', ['id', 'file', 'fixture_id', 'param_name', 'param_value', 'param_order'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'fixture_id', 'param_name', 'param_value', 'param_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_fixture_id(cursor: sqlite3.Cursor, fixture_id: int) -> list[dict[str, Any]]:
        """Get rows by fixture_id."""
        query = build_query('python_fixture_params', ['id', 'file', 'fixture_id', 'param_name', 'param_value', 'param_order'], where="fixture_id = ?")
        cursor.execute(query, (fixture_id,))
        return [dict(zip(['id', 'file', 'fixture_id', 'param_name', 'param_value', 'param_order'], row, strict=True)) for row in cursor.fetchall()]


class PythonFrameworkConfigTable:
    """Accessor class for python_framework_config table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_framework_config."""
        query = build_query('python_framework_config', ['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_framework_config', ['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_framework(cursor: sqlite3.Cursor, framework: str) -> list[dict[str, Any]]:
        """Get rows by framework."""
        query = build_query('python_framework_config', ['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], where="framework = ?")
        cursor.execute(query, (framework,))
        return [dict(zip(['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_config_kind(cursor: sqlite3.Cursor, config_kind: str) -> list[dict[str, Any]]:
        """Get rows by config_kind."""
        query = build_query('python_framework_config', ['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], where="config_kind = ?")
        cursor.execute(query, (config_kind,))
        return [dict(zip(['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_class_name(cursor: sqlite3.Cursor, class_name: str) -> list[dict[str, Any]]:
        """Get rows by class_name."""
        query = build_query('python_framework_config', ['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], where="class_name = ?")
        cursor.execute(query, (class_name,))
        return [dict(zip(['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> list[dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('python_framework_config', ['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> list[dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('python_framework_config', ['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['id', 'file', 'line', 'config_kind', 'config_type', 'framework', 'name', 'endpoint', 'cache_type', 'timeout', 'class_name', 'model_name', 'function_name', 'target_name', 'base_class', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row, strict=True)) for row in cursor.fetchall()]


class PythonFrameworkMethodsTable:
    """Accessor class for python_framework_methods table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_framework_methods."""
        query = build_query('python_framework_methods', ['id', 'file', 'config_id', 'method_name', 'method_order'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'config_id', 'method_name', 'method_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_framework_methods', ['id', 'file', 'config_id', 'method_name', 'method_order'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'config_id', 'method_name', 'method_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_config_id(cursor: sqlite3.Cursor, config_id: int) -> list[dict[str, Any]]:
        """Get rows by config_id."""
        query = build_query('python_framework_methods', ['id', 'file', 'config_id', 'method_name', 'method_order'], where="config_id = ?")
        cursor.execute(query, (config_id,))
        return [dict(zip(['id', 'file', 'config_id', 'method_name', 'method_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_method_name(cursor: sqlite3.Cursor, method_name: str) -> list[dict[str, Any]]:
        """Get rows by method_name."""
        query = build_query('python_framework_methods', ['id', 'file', 'config_id', 'method_name', 'method_order'], where="method_name = ?")
        cursor.execute(query, (method_name,))
        return [dict(zip(['id', 'file', 'config_id', 'method_name', 'method_order'], row, strict=True)) for row in cursor.fetchall()]


class PythonFunctionsAdvancedTable:
    """Accessor class for python_functions_advanced table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_functions_advanced."""
        query = build_query('python_functions_advanced', ['id', 'file', 'line', 'function_kind', 'function_type', 'name', 'function_name', 'yield_count', 'has_send', 'has_yield_from', 'is_infinite', 'await_count', 'has_async_for', 'has_async_with', 'parameter_count', 'parameters', 'body', 'captures_closure', 'captured_vars', 'used_in', 'as_name', 'context_expr', 'is_async', 'iter_expr', 'target_var', 'base_case_line', 'calls_function', 'recursion_type', 'cache_size', 'memoization_type', 'is_recursive', 'has_memoization', 'in_function'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'function_kind', 'function_type', 'name', 'function_name', 'yield_count', 'has_send', 'has_yield_from', 'is_infinite', 'await_count', 'has_async_for', 'has_async_with', 'parameter_count', 'parameters', 'body', 'captures_closure', 'captured_vars', 'used_in', 'as_name', 'context_expr', 'is_async', 'iter_expr', 'target_var', 'base_case_line', 'calls_function', 'recursion_type', 'cache_size', 'memoization_type', 'is_recursive', 'has_memoization', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_functions_advanced', ['id', 'file', 'line', 'function_kind', 'function_type', 'name', 'function_name', 'yield_count', 'has_send', 'has_yield_from', 'is_infinite', 'await_count', 'has_async_for', 'has_async_with', 'parameter_count', 'parameters', 'body', 'captures_closure', 'captured_vars', 'used_in', 'as_name', 'context_expr', 'is_async', 'iter_expr', 'target_var', 'base_case_line', 'calls_function', 'recursion_type', 'cache_size', 'memoization_type', 'is_recursive', 'has_memoization', 'in_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'function_kind', 'function_type', 'name', 'function_name', 'yield_count', 'has_send', 'has_yield_from', 'is_infinite', 'await_count', 'has_async_for', 'has_async_with', 'parameter_count', 'parameters', 'body', 'captures_closure', 'captured_vars', 'used_in', 'as_name', 'context_expr', 'is_async', 'iter_expr', 'target_var', 'base_case_line', 'calls_function', 'recursion_type', 'cache_size', 'memoization_type', 'is_recursive', 'has_memoization', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_kind(cursor: sqlite3.Cursor, function_kind: str) -> list[dict[str, Any]]:
        """Get rows by function_kind."""
        query = build_query('python_functions_advanced', ['id', 'file', 'line', 'function_kind', 'function_type', 'name', 'function_name', 'yield_count', 'has_send', 'has_yield_from', 'is_infinite', 'await_count', 'has_async_for', 'has_async_with', 'parameter_count', 'parameters', 'body', 'captures_closure', 'captured_vars', 'used_in', 'as_name', 'context_expr', 'is_async', 'iter_expr', 'target_var', 'base_case_line', 'calls_function', 'recursion_type', 'cache_size', 'memoization_type', 'is_recursive', 'has_memoization', 'in_function'], where="function_kind = ?")
        cursor.execute(query, (function_kind,))
        return [dict(zip(['id', 'file', 'line', 'function_kind', 'function_type', 'name', 'function_name', 'yield_count', 'has_send', 'has_yield_from', 'is_infinite', 'await_count', 'has_async_for', 'has_async_with', 'parameter_count', 'parameters', 'body', 'captures_closure', 'captured_vars', 'used_in', 'as_name', 'context_expr', 'is_async', 'iter_expr', 'target_var', 'base_case_line', 'calls_function', 'recursion_type', 'cache_size', 'memoization_type', 'is_recursive', 'has_memoization', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_functions_advanced', ['id', 'file', 'line', 'function_kind', 'function_type', 'name', 'function_name', 'yield_count', 'has_send', 'has_yield_from', 'is_infinite', 'await_count', 'has_async_for', 'has_async_with', 'parameter_count', 'parameters', 'body', 'captures_closure', 'captured_vars', 'used_in', 'as_name', 'context_expr', 'is_async', 'iter_expr', 'target_var', 'base_case_line', 'calls_function', 'recursion_type', 'cache_size', 'memoization_type', 'is_recursive', 'has_memoization', 'in_function'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'function_kind', 'function_type', 'name', 'function_name', 'yield_count', 'has_send', 'has_yield_from', 'is_infinite', 'await_count', 'has_async_for', 'has_async_with', 'parameter_count', 'parameters', 'body', 'captures_closure', 'captured_vars', 'used_in', 'as_name', 'context_expr', 'is_async', 'iter_expr', 'target_var', 'base_case_line', 'calls_function', 'recursion_type', 'cache_size', 'memoization_type', 'is_recursive', 'has_memoization', 'in_function'], row, strict=True)) for row in cursor.fetchall()]


class PythonImportsAdvancedTable:
    """Accessor class for python_imports_advanced table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_imports_advanced."""
        query = build_query('python_imports_advanced', ['id', 'file', 'line', 'import_kind', 'import_type', 'module', 'name', 'alias', 'is_relative', 'in_function', 'has_alias', 'imported_names', 'is_wildcard', 'relative_level', 'attribute', 'is_default', 'export_type'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'import_kind', 'import_type', 'module', 'name', 'alias', 'is_relative', 'in_function', 'has_alias', 'imported_names', 'is_wildcard', 'relative_level', 'attribute', 'is_default', 'export_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_imports_advanced', ['id', 'file', 'line', 'import_kind', 'import_type', 'module', 'name', 'alias', 'is_relative', 'in_function', 'has_alias', 'imported_names', 'is_wildcard', 'relative_level', 'attribute', 'is_default', 'export_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'import_kind', 'import_type', 'module', 'name', 'alias', 'is_relative', 'in_function', 'has_alias', 'imported_names', 'is_wildcard', 'relative_level', 'attribute', 'is_default', 'export_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_import_kind(cursor: sqlite3.Cursor, import_kind: str) -> list[dict[str, Any]]:
        """Get rows by import_kind."""
        query = build_query('python_imports_advanced', ['id', 'file', 'line', 'import_kind', 'import_type', 'module', 'name', 'alias', 'is_relative', 'in_function', 'has_alias', 'imported_names', 'is_wildcard', 'relative_level', 'attribute', 'is_default', 'export_type'], where="import_kind = ?")
        cursor.execute(query, (import_kind,))
        return [dict(zip(['id', 'file', 'line', 'import_kind', 'import_type', 'module', 'name', 'alias', 'is_relative', 'in_function', 'has_alias', 'imported_names', 'is_wildcard', 'relative_level', 'attribute', 'is_default', 'export_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_imports_advanced', ['id', 'file', 'line', 'import_kind', 'import_type', 'module', 'name', 'alias', 'is_relative', 'in_function', 'has_alias', 'imported_names', 'is_wildcard', 'relative_level', 'attribute', 'is_default', 'export_type'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'import_kind', 'import_type', 'module', 'name', 'alias', 'is_relative', 'in_function', 'has_alias', 'imported_names', 'is_wildcard', 'relative_level', 'attribute', 'is_default', 'export_type'], row, strict=True)) for row in cursor.fetchall()]


class PythonIoOperationsTable:
    """Accessor class for python_io_operations table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_io_operations."""
        query = build_query('python_io_operations', ['id', 'file', 'line', 'io_kind', 'io_type', 'operation', 'target', 'is_static', 'flow_type', 'function_name', 'parameter_name', 'return_expr', 'is_async', 'in_function'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'io_kind', 'io_type', 'operation', 'target', 'is_static', 'flow_type', 'function_name', 'parameter_name', 'return_expr', 'is_async', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_io_operations', ['id', 'file', 'line', 'io_kind', 'io_type', 'operation', 'target', 'is_static', 'flow_type', 'function_name', 'parameter_name', 'return_expr', 'is_async', 'in_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'io_kind', 'io_type', 'operation', 'target', 'is_static', 'flow_type', 'function_name', 'parameter_name', 'return_expr', 'is_async', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_io_kind(cursor: sqlite3.Cursor, io_kind: str) -> list[dict[str, Any]]:
        """Get rows by io_kind."""
        query = build_query('python_io_operations', ['id', 'file', 'line', 'io_kind', 'io_type', 'operation', 'target', 'is_static', 'flow_type', 'function_name', 'parameter_name', 'return_expr', 'is_async', 'in_function'], where="io_kind = ?")
        cursor.execute(query, (io_kind,))
        return [dict(zip(['id', 'file', 'line', 'io_kind', 'io_type', 'operation', 'target', 'is_static', 'flow_type', 'function_name', 'parameter_name', 'return_expr', 'is_async', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_io_operations', ['id', 'file', 'line', 'io_kind', 'io_type', 'operation', 'target', 'is_static', 'flow_type', 'function_name', 'parameter_name', 'return_expr', 'is_async', 'in_function'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'io_kind', 'io_type', 'operation', 'target', 'is_static', 'flow_type', 'function_name', 'parameter_name', 'return_expr', 'is_async', 'in_function'], row, strict=True)) for row in cursor.fetchall()]


class PythonLiteralsTable:
    """Accessor class for python_literals table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_literals."""
        query = build_query('python_literals', ['id', 'file', 'line', 'literal_kind', 'literal_type', 'name', 'literal_value_1', 'literal_value_2', 'literal_value_3', 'literal_value_4', 'literal_value_5', 'function_name', 'overload_count', 'variants'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'literal_kind', 'literal_type', 'name', 'literal_value_1', 'literal_value_2', 'literal_value_3', 'literal_value_4', 'literal_value_5', 'function_name', 'overload_count', 'variants'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_literals', ['id', 'file', 'line', 'literal_kind', 'literal_type', 'name', 'literal_value_1', 'literal_value_2', 'literal_value_3', 'literal_value_4', 'literal_value_5', 'function_name', 'overload_count', 'variants'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'literal_kind', 'literal_type', 'name', 'literal_value_1', 'literal_value_2', 'literal_value_3', 'literal_value_4', 'literal_value_5', 'function_name', 'overload_count', 'variants'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_literal_kind(cursor: sqlite3.Cursor, literal_kind: str) -> list[dict[str, Any]]:
        """Get rows by literal_kind."""
        query = build_query('python_literals', ['id', 'file', 'line', 'literal_kind', 'literal_type', 'name', 'literal_value_1', 'literal_value_2', 'literal_value_3', 'literal_value_4', 'literal_value_5', 'function_name', 'overload_count', 'variants'], where="literal_kind = ?")
        cursor.execute(query, (literal_kind,))
        return [dict(zip(['id', 'file', 'line', 'literal_kind', 'literal_type', 'name', 'literal_value_1', 'literal_value_2', 'literal_value_3', 'literal_value_4', 'literal_value_5', 'function_name', 'overload_count', 'variants'], row, strict=True)) for row in cursor.fetchall()]


class PythonLoopsTable:
    """Accessor class for python_loops table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_loops."""
        query = build_query('python_loops', ['id', 'file', 'line', 'loop_kind', 'loop_type', 'has_else', 'nesting_level', 'target_count', 'in_function', 'is_infinite', 'estimated_complexity', 'has_growing_operation'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'loop_kind', 'loop_type', 'has_else', 'nesting_level', 'target_count', 'in_function', 'is_infinite', 'estimated_complexity', 'has_growing_operation'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_loops', ['id', 'file', 'line', 'loop_kind', 'loop_type', 'has_else', 'nesting_level', 'target_count', 'in_function', 'is_infinite', 'estimated_complexity', 'has_growing_operation'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'loop_kind', 'loop_type', 'has_else', 'nesting_level', 'target_count', 'in_function', 'is_infinite', 'estimated_complexity', 'has_growing_operation'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_loop_kind(cursor: sqlite3.Cursor, loop_kind: str) -> list[dict[str, Any]]:
        """Get rows by loop_kind."""
        query = build_query('python_loops', ['id', 'file', 'line', 'loop_kind', 'loop_type', 'has_else', 'nesting_level', 'target_count', 'in_function', 'is_infinite', 'estimated_complexity', 'has_growing_operation'], where="loop_kind = ?")
        cursor.execute(query, (loop_kind,))
        return [dict(zip(['id', 'file', 'line', 'loop_kind', 'loop_type', 'has_else', 'nesting_level', 'target_count', 'in_function', 'is_infinite', 'estimated_complexity', 'has_growing_operation'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_loops', ['id', 'file', 'line', 'loop_kind', 'loop_type', 'has_else', 'nesting_level', 'target_count', 'in_function', 'is_infinite', 'estimated_complexity', 'has_growing_operation'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'loop_kind', 'loop_type', 'has_else', 'nesting_level', 'target_count', 'in_function', 'is_infinite', 'estimated_complexity', 'has_growing_operation'], row, strict=True)) for row in cursor.fetchall()]


class PythonOperatorsTable:
    """Accessor class for python_operators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_operators."""
        query = build_query('python_operators', ['id', 'file', 'line', 'operator_kind', 'operator_type', 'operator', 'in_function', 'container_type', 'chain_length', 'operators', 'has_complex_condition', 'variable', 'used_in'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'operator_kind', 'operator_type', 'operator', 'in_function', 'container_type', 'chain_length', 'operators', 'has_complex_condition', 'variable', 'used_in'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_operators', ['id', 'file', 'line', 'operator_kind', 'operator_type', 'operator', 'in_function', 'container_type', 'chain_length', 'operators', 'has_complex_condition', 'variable', 'used_in'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'operator_kind', 'operator_type', 'operator', 'in_function', 'container_type', 'chain_length', 'operators', 'has_complex_condition', 'variable', 'used_in'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_operator_kind(cursor: sqlite3.Cursor, operator_kind: str) -> list[dict[str, Any]]:
        """Get rows by operator_kind."""
        query = build_query('python_operators', ['id', 'file', 'line', 'operator_kind', 'operator_type', 'operator', 'in_function', 'container_type', 'chain_length', 'operators', 'has_complex_condition', 'variable', 'used_in'], where="operator_kind = ?")
        cursor.execute(query, (operator_kind,))
        return [dict(zip(['id', 'file', 'line', 'operator_kind', 'operator_type', 'operator', 'in_function', 'container_type', 'chain_length', 'operators', 'has_complex_condition', 'variable', 'used_in'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_operators', ['id', 'file', 'line', 'operator_kind', 'operator_type', 'operator', 'in_function', 'container_type', 'chain_length', 'operators', 'has_complex_condition', 'variable', 'used_in'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'operator_kind', 'operator_type', 'operator', 'in_function', 'container_type', 'chain_length', 'operators', 'has_complex_condition', 'variable', 'used_in'], row, strict=True)) for row in cursor.fetchall()]


class PythonOrmFieldsTable:
    """Accessor class for python_orm_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_orm_fields."""
        query = build_query('python_orm_fields', ['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_orm_fields', ['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> list[dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('python_orm_fields', ['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_foreign_key(cursor: sqlite3.Cursor, is_foreign_key: bool) -> list[dict[str, Any]]:
        """Get rows by is_foreign_key."""
        query = build_query('python_orm_fields', ['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], where="is_foreign_key = ?")
        cursor.execute(query, (is_foreign_key,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], row, strict=True)) for row in cursor.fetchall()]


class PythonOrmModelsTable:
    """Accessor class for python_orm_models table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_orm_models."""
        query = build_query('python_orm_models', ['file', 'line', 'model_name', 'table_name', 'orm_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'orm_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_orm_models', ['file', 'line', 'model_name', 'table_name', 'orm_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'orm_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_orm_type(cursor: sqlite3.Cursor, orm_type: str) -> list[dict[str, Any]]:
        """Get rows by orm_type."""
        query = build_query('python_orm_models', ['file', 'line', 'model_name', 'table_name', 'orm_type'], where="orm_type = ?")
        cursor.execute(query, (orm_type,))
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'orm_type'], row, strict=True)) for row in cursor.fetchall()]


class PythonPackageConfigsTable:
    """Accessor class for python_package_configs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_package_configs."""
        query = build_query('python_package_configs', ['file_path', 'file_type', 'project_name', 'project_version', 'indexed_at'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'file_type', 'project_name', 'project_version', 'indexed_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('python_package_configs', ['file_path', 'file_type', 'project_name', 'project_version', 'indexed_at'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'file_type', 'project_name', 'project_version', 'indexed_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_type(cursor: sqlite3.Cursor, file_type: str) -> list[dict[str, Any]]:
        """Get rows by file_type."""
        query = build_query('python_package_configs', ['file_path', 'file_type', 'project_name', 'project_version', 'indexed_at'], where="file_type = ?")
        cursor.execute(query, (file_type,))
        return [dict(zip(['file_path', 'file_type', 'project_name', 'project_version', 'indexed_at'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_project_name(cursor: sqlite3.Cursor, project_name: str) -> list[dict[str, Any]]:
        """Get rows by project_name."""
        query = build_query('python_package_configs', ['file_path', 'file_type', 'project_name', 'project_version', 'indexed_at'], where="project_name = ?")
        cursor.execute(query, (project_name,))
        return [dict(zip(['file_path', 'file_type', 'project_name', 'project_version', 'indexed_at'], row, strict=True)) for row in cursor.fetchall()]


class PythonPackageDependenciesTable:
    """Accessor class for python_package_dependencies table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_package_dependencies."""
        query = build_query('python_package_dependencies', ['file_path', 'name', 'version_spec', 'is_dev', 'group_name', 'extras', 'git_url'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'name', 'version_spec', 'is_dev', 'group_name', 'extras', 'git_url'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('python_package_dependencies', ['file_path', 'name', 'version_spec', 'is_dev', 'group_name', 'extras', 'git_url'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'name', 'version_spec', 'is_dev', 'group_name', 'extras', 'git_url'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('python_package_dependencies', ['file_path', 'name', 'version_spec', 'is_dev', 'group_name', 'extras', 'git_url'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file_path', 'name', 'version_spec', 'is_dev', 'group_name', 'extras', 'git_url'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_dev(cursor: sqlite3.Cursor, is_dev: int) -> list[dict[str, Any]]:
        """Get rows by is_dev."""
        query = build_query('python_package_dependencies', ['file_path', 'name', 'version_spec', 'is_dev', 'group_name', 'extras', 'git_url'], where="is_dev = ?")
        cursor.execute(query, (is_dev,))
        return [dict(zip(['file_path', 'name', 'version_spec', 'is_dev', 'group_name', 'extras', 'git_url'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_group_name(cursor: sqlite3.Cursor, group_name: str) -> list[dict[str, Any]]:
        """Get rows by group_name."""
        query = build_query('python_package_dependencies', ['file_path', 'name', 'version_spec', 'is_dev', 'group_name', 'extras', 'git_url'], where="group_name = ?")
        cursor.execute(query, (group_name,))
        return [dict(zip(['file_path', 'name', 'version_spec', 'is_dev', 'group_name', 'extras', 'git_url'], row, strict=True)) for row in cursor.fetchall()]


class PythonProtocolMethodsTable:
    """Accessor class for python_protocol_methods table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_protocol_methods."""
        query = build_query('python_protocol_methods', ['id', 'file', 'protocol_id', 'method_name', 'method_order'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'protocol_id', 'method_name', 'method_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_protocol_methods', ['id', 'file', 'protocol_id', 'method_name', 'method_order'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'protocol_id', 'method_name', 'method_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_protocol_id(cursor: sqlite3.Cursor, protocol_id: int) -> list[dict[str, Any]]:
        """Get rows by protocol_id."""
        query = build_query('python_protocol_methods', ['id', 'file', 'protocol_id', 'method_name', 'method_order'], where="protocol_id = ?")
        cursor.execute(query, (protocol_id,))
        return [dict(zip(['id', 'file', 'protocol_id', 'method_name', 'method_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_method_name(cursor: sqlite3.Cursor, method_name: str) -> list[dict[str, Any]]:
        """Get rows by method_name."""
        query = build_query('python_protocol_methods', ['id', 'file', 'protocol_id', 'method_name', 'method_order'], where="method_name = ?")
        cursor.execute(query, (method_name,))
        return [dict(zip(['id', 'file', 'protocol_id', 'method_name', 'method_order'], row, strict=True)) for row in cursor.fetchall()]


class PythonProtocolsTable:
    """Accessor class for python_protocols table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_protocols."""
        query = build_query('python_protocols', ['id', 'file', 'line', 'protocol_kind', 'protocol_type', 'class_name', 'in_function', 'has_iter', 'has_next', 'is_generator', 'raises_stopiteration', 'has_contains', 'has_getitem', 'has_setitem', 'has_delitem', 'has_len', 'is_mapping', 'is_sequence', 'has_args', 'has_kwargs', 'param_count', 'has_getstate', 'has_setstate', 'has_reduce', 'has_reduce_ex', 'context_expr', 'resource_type', 'variable_name', 'is_async', 'has_copy', 'has_deepcopy'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'protocol_kind', 'protocol_type', 'class_name', 'in_function', 'has_iter', 'has_next', 'is_generator', 'raises_stopiteration', 'has_contains', 'has_getitem', 'has_setitem', 'has_delitem', 'has_len', 'is_mapping', 'is_sequence', 'has_args', 'has_kwargs', 'param_count', 'has_getstate', 'has_setstate', 'has_reduce', 'has_reduce_ex', 'context_expr', 'resource_type', 'variable_name', 'is_async', 'has_copy', 'has_deepcopy'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_protocols', ['id', 'file', 'line', 'protocol_kind', 'protocol_type', 'class_name', 'in_function', 'has_iter', 'has_next', 'is_generator', 'raises_stopiteration', 'has_contains', 'has_getitem', 'has_setitem', 'has_delitem', 'has_len', 'is_mapping', 'is_sequence', 'has_args', 'has_kwargs', 'param_count', 'has_getstate', 'has_setstate', 'has_reduce', 'has_reduce_ex', 'context_expr', 'resource_type', 'variable_name', 'is_async', 'has_copy', 'has_deepcopy'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'protocol_kind', 'protocol_type', 'class_name', 'in_function', 'has_iter', 'has_next', 'is_generator', 'raises_stopiteration', 'has_contains', 'has_getitem', 'has_setitem', 'has_delitem', 'has_len', 'is_mapping', 'is_sequence', 'has_args', 'has_kwargs', 'param_count', 'has_getstate', 'has_setstate', 'has_reduce', 'has_reduce_ex', 'context_expr', 'resource_type', 'variable_name', 'is_async', 'has_copy', 'has_deepcopy'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_protocol_kind(cursor: sqlite3.Cursor, protocol_kind: str) -> list[dict[str, Any]]:
        """Get rows by protocol_kind."""
        query = build_query('python_protocols', ['id', 'file', 'line', 'protocol_kind', 'protocol_type', 'class_name', 'in_function', 'has_iter', 'has_next', 'is_generator', 'raises_stopiteration', 'has_contains', 'has_getitem', 'has_setitem', 'has_delitem', 'has_len', 'is_mapping', 'is_sequence', 'has_args', 'has_kwargs', 'param_count', 'has_getstate', 'has_setstate', 'has_reduce', 'has_reduce_ex', 'context_expr', 'resource_type', 'variable_name', 'is_async', 'has_copy', 'has_deepcopy'], where="protocol_kind = ?")
        cursor.execute(query, (protocol_kind,))
        return [dict(zip(['id', 'file', 'line', 'protocol_kind', 'protocol_type', 'class_name', 'in_function', 'has_iter', 'has_next', 'is_generator', 'raises_stopiteration', 'has_contains', 'has_getitem', 'has_setitem', 'has_delitem', 'has_len', 'is_mapping', 'is_sequence', 'has_args', 'has_kwargs', 'param_count', 'has_getstate', 'has_setstate', 'has_reduce', 'has_reduce_ex', 'context_expr', 'resource_type', 'variable_name', 'is_async', 'has_copy', 'has_deepcopy'], row, strict=True)) for row in cursor.fetchall()]


class PythonRoutesTable:
    """Accessor class for python_routes table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_routes."""
        query = build_query('python_routes', ['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_routes', ['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_framework(cursor: sqlite3.Cursor, framework: str) -> list[dict[str, Any]]:
        """Get rows by framework."""
        query = build_query('python_routes', ['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'], where="framework = ?")
        cursor.execute(query, (framework,))
        return [dict(zip(['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'], row, strict=True)) for row in cursor.fetchall()]


class PythonSchemaValidatorsTable:
    """Accessor class for python_schema_validators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_schema_validators."""
        query = build_query('python_schema_validators', ['id', 'file', 'schema_id', 'validator_name', 'validator_type', 'validator_order'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'schema_id', 'validator_name', 'validator_type', 'validator_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_schema_validators', ['id', 'file', 'schema_id', 'validator_name', 'validator_type', 'validator_order'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'schema_id', 'validator_name', 'validator_type', 'validator_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_schema_id(cursor: sqlite3.Cursor, schema_id: int) -> list[dict[str, Any]]:
        """Get rows by schema_id."""
        query = build_query('python_schema_validators', ['id', 'file', 'schema_id', 'validator_name', 'validator_type', 'validator_order'], where="schema_id = ?")
        cursor.execute(query, (schema_id,))
        return [dict(zip(['id', 'file', 'schema_id', 'validator_name', 'validator_type', 'validator_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_validator_name(cursor: sqlite3.Cursor, validator_name: str) -> list[dict[str, Any]]:
        """Get rows by validator_name."""
        query = build_query('python_schema_validators', ['id', 'file', 'schema_id', 'validator_name', 'validator_type', 'validator_order'], where="validator_name = ?")
        cursor.execute(query, (validator_name,))
        return [dict(zip(['id', 'file', 'schema_id', 'validator_name', 'validator_type', 'validator_order'], row, strict=True)) for row in cursor.fetchall()]


class PythonSecurityFindingsTable:
    """Accessor class for python_security_findings table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_security_findings."""
        query = build_query('python_security_findings', ['id', 'file', 'line', 'finding_kind', 'finding_type', 'function_name', 'decorator_name', 'permissions', 'is_vulnerable', 'shell_true', 'is_constant_input', 'is_critical', 'has_concatenation'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'finding_kind', 'finding_type', 'function_name', 'decorator_name', 'permissions', 'is_vulnerable', 'shell_true', 'is_constant_input', 'is_critical', 'has_concatenation'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_security_findings', ['id', 'file', 'line', 'finding_kind', 'finding_type', 'function_name', 'decorator_name', 'permissions', 'is_vulnerable', 'shell_true', 'is_constant_input', 'is_critical', 'has_concatenation'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'finding_kind', 'finding_type', 'function_name', 'decorator_name', 'permissions', 'is_vulnerable', 'shell_true', 'is_constant_input', 'is_critical', 'has_concatenation'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_finding_kind(cursor: sqlite3.Cursor, finding_kind: str) -> list[dict[str, Any]]:
        """Get rows by finding_kind."""
        query = build_query('python_security_findings', ['id', 'file', 'line', 'finding_kind', 'finding_type', 'function_name', 'decorator_name', 'permissions', 'is_vulnerable', 'shell_true', 'is_constant_input', 'is_critical', 'has_concatenation'], where="finding_kind = ?")
        cursor.execute(query, (finding_kind,))
        return [dict(zip(['id', 'file', 'line', 'finding_kind', 'finding_type', 'function_name', 'decorator_name', 'permissions', 'is_vulnerable', 'shell_true', 'is_constant_input', 'is_critical', 'has_concatenation'], row, strict=True)) for row in cursor.fetchall()]


class PythonStateMutationsTable:
    """Accessor class for python_state_mutations table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_state_mutations."""
        query = build_query('python_state_mutations', ['id', 'file', 'line', 'mutation_kind', 'mutation_type', 'target', 'operator', 'target_type', 'operation', 'is_init', 'is_dunder_method', 'is_property_setter', 'in_function'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'mutation_kind', 'mutation_type', 'target', 'operator', 'target_type', 'operation', 'is_init', 'is_dunder_method', 'is_property_setter', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_state_mutations', ['id', 'file', 'line', 'mutation_kind', 'mutation_type', 'target', 'operator', 'target_type', 'operation', 'is_init', 'is_dunder_method', 'is_property_setter', 'in_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'mutation_kind', 'mutation_type', 'target', 'operator', 'target_type', 'operation', 'is_init', 'is_dunder_method', 'is_property_setter', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_mutation_kind(cursor: sqlite3.Cursor, mutation_kind: str) -> list[dict[str, Any]]:
        """Get rows by mutation_kind."""
        query = build_query('python_state_mutations', ['id', 'file', 'line', 'mutation_kind', 'mutation_type', 'target', 'operator', 'target_type', 'operation', 'is_init', 'is_dunder_method', 'is_property_setter', 'in_function'], where="mutation_kind = ?")
        cursor.execute(query, (mutation_kind,))
        return [dict(zip(['id', 'file', 'line', 'mutation_kind', 'mutation_type', 'target', 'operator', 'target_type', 'operation', 'is_init', 'is_dunder_method', 'is_property_setter', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_state_mutations', ['id', 'file', 'line', 'mutation_kind', 'mutation_type', 'target', 'operator', 'target_type', 'operation', 'is_init', 'is_dunder_method', 'is_property_setter', 'in_function'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'mutation_kind', 'mutation_type', 'target', 'operator', 'target_type', 'operation', 'is_init', 'is_dunder_method', 'is_property_setter', 'in_function'], row, strict=True)) for row in cursor.fetchall()]


class PythonStdlibUsageTable:
    """Accessor class for python_stdlib_usage table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_stdlib_usage."""
        query = build_query('python_stdlib_usage', ['id', 'file', 'line', 'stdlib_kind', 'module', 'usage_type', 'function_name', 'pattern', 'in_function', 'operation', 'has_flags', 'direction', 'path_type', 'log_level', 'threading_type', 'is_decorator'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'stdlib_kind', 'module', 'usage_type', 'function_name', 'pattern', 'in_function', 'operation', 'has_flags', 'direction', 'path_type', 'log_level', 'threading_type', 'is_decorator'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_stdlib_usage', ['id', 'file', 'line', 'stdlib_kind', 'module', 'usage_type', 'function_name', 'pattern', 'in_function', 'operation', 'has_flags', 'direction', 'path_type', 'log_level', 'threading_type', 'is_decorator'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'stdlib_kind', 'module', 'usage_type', 'function_name', 'pattern', 'in_function', 'operation', 'has_flags', 'direction', 'path_type', 'log_level', 'threading_type', 'is_decorator'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_stdlib_kind(cursor: sqlite3.Cursor, stdlib_kind: str) -> list[dict[str, Any]]:
        """Get rows by stdlib_kind."""
        query = build_query('python_stdlib_usage', ['id', 'file', 'line', 'stdlib_kind', 'module', 'usage_type', 'function_name', 'pattern', 'in_function', 'operation', 'has_flags', 'direction', 'path_type', 'log_level', 'threading_type', 'is_decorator'], where="stdlib_kind = ?")
        cursor.execute(query, (stdlib_kind,))
        return [dict(zip(['id', 'file', 'line', 'stdlib_kind', 'module', 'usage_type', 'function_name', 'pattern', 'in_function', 'operation', 'has_flags', 'direction', 'path_type', 'log_level', 'threading_type', 'is_decorator'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> list[dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('python_stdlib_usage', ['id', 'file', 'line', 'stdlib_kind', 'module', 'usage_type', 'function_name', 'pattern', 'in_function', 'operation', 'has_flags', 'direction', 'path_type', 'log_level', 'threading_type', 'is_decorator'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['id', 'file', 'line', 'stdlib_kind', 'module', 'usage_type', 'function_name', 'pattern', 'in_function', 'operation', 'has_flags', 'direction', 'path_type', 'log_level', 'threading_type', 'is_decorator'], row, strict=True)) for row in cursor.fetchall()]


class PythonTestCasesTable:
    """Accessor class for python_test_cases table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_test_cases."""
        query = build_query('python_test_cases', ['id', 'file', 'line', 'test_kind', 'test_type', 'name', 'function_name', 'class_name', 'assertion_type', 'test_expr'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'test_kind', 'test_type', 'name', 'function_name', 'class_name', 'assertion_type', 'test_expr'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_test_cases', ['id', 'file', 'line', 'test_kind', 'test_type', 'name', 'function_name', 'class_name', 'assertion_type', 'test_expr'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'test_kind', 'test_type', 'name', 'function_name', 'class_name', 'assertion_type', 'test_expr'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_test_kind(cursor: sqlite3.Cursor, test_kind: str) -> list[dict[str, Any]]:
        """Get rows by test_kind."""
        query = build_query('python_test_cases', ['id', 'file', 'line', 'test_kind', 'test_type', 'name', 'function_name', 'class_name', 'assertion_type', 'test_expr'], where="test_kind = ?")
        cursor.execute(query, (test_kind,))
        return [dict(zip(['id', 'file', 'line', 'test_kind', 'test_type', 'name', 'function_name', 'class_name', 'assertion_type', 'test_expr'], row, strict=True)) for row in cursor.fetchall()]


class PythonTestFixturesTable:
    """Accessor class for python_test_fixtures table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_test_fixtures."""
        query = build_query('python_test_fixtures', ['id', 'file', 'line', 'fixture_kind', 'fixture_type', 'name', 'scope', 'autouse', 'in_function'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'fixture_kind', 'fixture_type', 'name', 'scope', 'autouse', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_test_fixtures', ['id', 'file', 'line', 'fixture_kind', 'fixture_type', 'name', 'scope', 'autouse', 'in_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'fixture_kind', 'fixture_type', 'name', 'scope', 'autouse', 'in_function'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_fixture_kind(cursor: sqlite3.Cursor, fixture_kind: str) -> list[dict[str, Any]]:
        """Get rows by fixture_kind."""
        query = build_query('python_test_fixtures', ['id', 'file', 'line', 'fixture_kind', 'fixture_type', 'name', 'scope', 'autouse', 'in_function'], where="fixture_kind = ?")
        cursor.execute(query, (fixture_kind,))
        return [dict(zip(['id', 'file', 'line', 'fixture_kind', 'fixture_type', 'name', 'scope', 'autouse', 'in_function'], row, strict=True)) for row in cursor.fetchall()]


class PythonTypeDefinitionsTable:
    """Accessor class for python_type_definitions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_type_definitions."""
        query = build_query('python_type_definitions', ['id', 'file', 'line', 'type_kind', 'name', 'type_param_count', 'type_param_1', 'type_param_2', 'type_param_3', 'type_param_4', 'type_param_5', 'is_runtime_checkable', 'methods'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'type_kind', 'name', 'type_param_count', 'type_param_1', 'type_param_2', 'type_param_3', 'type_param_4', 'type_param_5', 'is_runtime_checkable', 'methods'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_type_definitions', ['id', 'file', 'line', 'type_kind', 'name', 'type_param_count', 'type_param_1', 'type_param_2', 'type_param_3', 'type_param_4', 'type_param_5', 'is_runtime_checkable', 'methods'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'type_kind', 'name', 'type_param_count', 'type_param_1', 'type_param_2', 'type_param_3', 'type_param_4', 'type_param_5', 'is_runtime_checkable', 'methods'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type_kind(cursor: sqlite3.Cursor, type_kind: str) -> list[dict[str, Any]]:
        """Get rows by type_kind."""
        query = build_query('python_type_definitions', ['id', 'file', 'line', 'type_kind', 'name', 'type_param_count', 'type_param_1', 'type_param_2', 'type_param_3', 'type_param_4', 'type_param_5', 'is_runtime_checkable', 'methods'], where="type_kind = ?")
        cursor.execute(query, (type_kind,))
        return [dict(zip(['id', 'file', 'line', 'type_kind', 'name', 'type_param_count', 'type_param_1', 'type_param_2', 'type_param_3', 'type_param_4', 'type_param_5', 'is_runtime_checkable', 'methods'], row, strict=True)) for row in cursor.fetchall()]


class PythonTypeddictFieldsTable:
    """Accessor class for python_typeddict_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_typeddict_fields."""
        query = build_query('python_typeddict_fields', ['id', 'file', 'typeddict_id', 'field_name', 'field_type', 'required', 'field_order'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'typeddict_id', 'field_name', 'field_type', 'required', 'field_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_typeddict_fields', ['id', 'file', 'typeddict_id', 'field_name', 'field_type', 'required', 'field_order'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'typeddict_id', 'field_name', 'field_type', 'required', 'field_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_typeddict_id(cursor: sqlite3.Cursor, typeddict_id: int) -> list[dict[str, Any]]:
        """Get rows by typeddict_id."""
        query = build_query('python_typeddict_fields', ['id', 'file', 'typeddict_id', 'field_name', 'field_type', 'required', 'field_order'], where="typeddict_id = ?")
        cursor.execute(query, (typeddict_id,))
        return [dict(zip(['id', 'file', 'typeddict_id', 'field_name', 'field_type', 'required', 'field_order'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_name(cursor: sqlite3.Cursor, field_name: str) -> list[dict[str, Any]]:
        """Get rows by field_name."""
        query = build_query('python_typeddict_fields', ['id', 'file', 'typeddict_id', 'field_name', 'field_type', 'required', 'field_order'], where="field_name = ?")
        cursor.execute(query, (field_name,))
        return [dict(zip(['id', 'file', 'typeddict_id', 'field_name', 'field_type', 'required', 'field_order'], row, strict=True)) for row in cursor.fetchall()]


class PythonValidationSchemasTable:
    """Accessor class for python_validation_schemas table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_validation_schemas."""
        query = build_query('python_validation_schemas', ['id', 'file', 'line', 'schema_kind', 'schema_type', 'framework', 'name', 'field_type', 'required'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'schema_kind', 'schema_type', 'framework', 'name', 'field_type', 'required'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_validation_schemas', ['id', 'file', 'line', 'schema_kind', 'schema_type', 'framework', 'name', 'field_type', 'required'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'schema_kind', 'schema_type', 'framework', 'name', 'field_type', 'required'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_framework(cursor: sqlite3.Cursor, framework: str) -> list[dict[str, Any]]:
        """Get rows by framework."""
        query = build_query('python_validation_schemas', ['id', 'file', 'line', 'schema_kind', 'schema_type', 'framework', 'name', 'field_type', 'required'], where="framework = ?")
        cursor.execute(query, (framework,))
        return [dict(zip(['id', 'file', 'line', 'schema_kind', 'schema_type', 'framework', 'name', 'field_type', 'required'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_schema_kind(cursor: sqlite3.Cursor, schema_kind: str) -> list[dict[str, Any]]:
        """Get rows by schema_kind."""
        query = build_query('python_validation_schemas', ['id', 'file', 'line', 'schema_kind', 'schema_type', 'framework', 'name', 'field_type', 'required'], where="schema_kind = ?")
        cursor.execute(query, (schema_kind,))
        return [dict(zip(['id', 'file', 'line', 'schema_kind', 'schema_type', 'framework', 'name', 'field_type', 'required'], row, strict=True)) for row in cursor.fetchall()]


class PythonValidatorsTable:
    """Accessor class for python_validators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from python_validators."""
        query = build_query('python_validators', ['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_validators', ['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> list[dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('python_validators', ['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_validator_type(cursor: sqlite3.Cursor, validator_type: str) -> list[dict[str, Any]]:
        """Get rows by validator_type."""
        query = build_query('python_validators', ['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], where="validator_type = ?")
        cursor.execute(query, (validator_type,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], row, strict=True)) for row in cursor.fetchall()]


class ReactComponentHooksTable:
    """Accessor class for react_component_hooks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from react_component_hooks."""
        query = build_query('react_component_hooks', ['id', 'component_file', 'component_name', 'hook_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'component_file', 'component_name', 'hook_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_hook_name(cursor: sqlite3.Cursor, hook_name: str) -> list[dict[str, Any]]:
        """Get rows by hook_name."""
        query = build_query('react_component_hooks', ['id', 'component_file', 'component_name', 'hook_name'], where="hook_name = ?")
        cursor.execute(query, (hook_name,))
        return [dict(zip(['id', 'component_file', 'component_name', 'hook_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_file(cursor: sqlite3.Cursor, component_file: str) -> list[dict[str, Any]]:
        """Get rows by component_file."""
        query = build_query('react_component_hooks', ['id', 'component_file', 'component_name', 'hook_name'], where="component_file = ?")
        cursor.execute(query, (component_file,))
        return [dict(zip(['id', 'component_file', 'component_name', 'hook_name'], row, strict=True)) for row in cursor.fetchall()]


class ReactComponentsTable:
    """Accessor class for react_components table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from react_components."""
        query = build_query('react_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('react_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('react_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'], row, strict=True)) for row in cursor.fetchall()]


class ReactHookDependenciesTable:
    """Accessor class for react_hook_dependencies table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from react_hook_dependencies."""
        query = build_query('react_hook_dependencies', ['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_dependency_name(cursor: sqlite3.Cursor, dependency_name: str) -> list[dict[str, Any]]:
        """Get rows by dependency_name."""
        query = build_query('react_hook_dependencies', ['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'], where="dependency_name = ?")
        cursor.execute(query, (dependency_name,))
        return [dict(zip(['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_hook_file(cursor: sqlite3.Cursor, hook_file: str) -> list[dict[str, Any]]:
        """Get rows by hook_file."""
        query = build_query('react_hook_dependencies', ['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'], where="hook_file = ?")
        cursor.execute(query, (hook_file,))
        return [dict(zip(['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'], row, strict=True)) for row in cursor.fetchall()]


class ReactHooksTable:
    """Accessor class for react_hooks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from react_hooks."""
        query = build_query('react_hooks', ['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('react_hooks', ['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_name(cursor: sqlite3.Cursor, component_name: str) -> list[dict[str, Any]]:
        """Get rows by component_name."""
        query = build_query('react_hooks', ['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], where="component_name = ?")
        cursor.execute(query, (component_name,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_hook_name(cursor: sqlite3.Cursor, hook_name: str) -> list[dict[str, Any]]:
        """Get rows by hook_name."""
        query = build_query('react_hooks', ['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], where="hook_name = ?")
        cursor.execute(query, (hook_name,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], row, strict=True)) for row in cursor.fetchall()]


class RefactorCandidatesTable:
    """Accessor class for refactor_candidates table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from refactor_candidates."""
        query = build_query('refactor_candidates', ['id', 'file_path', 'reason', 'severity', 'loc', 'cyclomatic_complexity', 'duplication_percent', 'num_dependencies', 'detected_at', 'metadata_json'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'reason', 'severity', 'loc', 'cyclomatic_complexity', 'duplication_percent', 'num_dependencies', 'detected_at', 'metadata_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('refactor_candidates', ['id', 'file_path', 'reason', 'severity', 'loc', 'cyclomatic_complexity', 'duplication_percent', 'num_dependencies', 'detected_at', 'metadata_json'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'file_path', 'reason', 'severity', 'loc', 'cyclomatic_complexity', 'duplication_percent', 'num_dependencies', 'detected_at', 'metadata_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_reason(cursor: sqlite3.Cursor, reason: str) -> list[dict[str, Any]]:
        """Get rows by reason."""
        query = build_query('refactor_candidates', ['id', 'file_path', 'reason', 'severity', 'loc', 'cyclomatic_complexity', 'duplication_percent', 'num_dependencies', 'detected_at', 'metadata_json'], where="reason = ?")
        cursor.execute(query, (reason,))
        return [dict(zip(['id', 'file_path', 'reason', 'severity', 'loc', 'cyclomatic_complexity', 'duplication_percent', 'num_dependencies', 'detected_at', 'metadata_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_severity(cursor: sqlite3.Cursor, severity: str) -> list[dict[str, Any]]:
        """Get rows by severity."""
        query = build_query('refactor_candidates', ['id', 'file_path', 'reason', 'severity', 'loc', 'cyclomatic_complexity', 'duplication_percent', 'num_dependencies', 'detected_at', 'metadata_json'], where="severity = ?")
        cursor.execute(query, (severity,))
        return [dict(zip(['id', 'file_path', 'reason', 'severity', 'loc', 'cyclomatic_complexity', 'duplication_percent', 'num_dependencies', 'detected_at', 'metadata_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_detected_at(cursor: sqlite3.Cursor, detected_at: str) -> list[dict[str, Any]]:
        """Get rows by detected_at."""
        query = build_query('refactor_candidates', ['id', 'file_path', 'reason', 'severity', 'loc', 'cyclomatic_complexity', 'duplication_percent', 'num_dependencies', 'detected_at', 'metadata_json'], where="detected_at = ?")
        cursor.execute(query, (detected_at,))
        return [dict(zip(['id', 'file_path', 'reason', 'severity', 'loc', 'cyclomatic_complexity', 'duplication_percent', 'num_dependencies', 'detected_at', 'metadata_json'], row, strict=True)) for row in cursor.fetchall()]


class RefactorHistoryTable:
    """Accessor class for refactor_history table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from refactor_history."""
        query = build_query('refactor_history', ['id', 'timestamp', 'target_file', 'refactor_type', 'migrations_found', 'migrations_complete', 'schema_consistent', 'validation_status', 'details_json'])
        cursor.execute(query)
        return [dict(zip(['id', 'timestamp', 'target_file', 'refactor_type', 'migrations_found', 'migrations_complete', 'schema_consistent', 'validation_status', 'details_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_file(cursor: sqlite3.Cursor, target_file: str) -> list[dict[str, Any]]:
        """Get rows by target_file."""
        query = build_query('refactor_history', ['id', 'timestamp', 'target_file', 'refactor_type', 'migrations_found', 'migrations_complete', 'schema_consistent', 'validation_status', 'details_json'], where="target_file = ?")
        cursor.execute(query, (target_file,))
        return [dict(zip(['id', 'timestamp', 'target_file', 'refactor_type', 'migrations_found', 'migrations_complete', 'schema_consistent', 'validation_status', 'details_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_refactor_type(cursor: sqlite3.Cursor, refactor_type: str) -> list[dict[str, Any]]:
        """Get rows by refactor_type."""
        query = build_query('refactor_history', ['id', 'timestamp', 'target_file', 'refactor_type', 'migrations_found', 'migrations_complete', 'schema_consistent', 'validation_status', 'details_json'], where="refactor_type = ?")
        cursor.execute(query, (refactor_type,))
        return [dict(zip(['id', 'timestamp', 'target_file', 'refactor_type', 'migrations_found', 'migrations_complete', 'schema_consistent', 'validation_status', 'details_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_timestamp(cursor: sqlite3.Cursor, timestamp: str) -> list[dict[str, Any]]:
        """Get rows by timestamp."""
        query = build_query('refactor_history', ['id', 'timestamp', 'target_file', 'refactor_type', 'migrations_found', 'migrations_complete', 'schema_consistent', 'validation_status', 'details_json'], where="timestamp = ?")
        cursor.execute(query, (timestamp,))
        return [dict(zip(['id', 'timestamp', 'target_file', 'refactor_type', 'migrations_found', 'migrations_complete', 'schema_consistent', 'validation_status', 'details_json'], row, strict=True)) for row in cursor.fetchall()]


class RefsTable:
    """Accessor class for refs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from refs."""
        query = build_query('refs', ['src', 'kind', 'value', 'line'])
        cursor.execute(query)
        return [dict(zip(['src', 'kind', 'value', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_src(cursor: sqlite3.Cursor, src: str) -> list[dict[str, Any]]:
        """Get rows by src."""
        query = build_query('refs', ['src', 'kind', 'value', 'line'], where="src = ?")
        cursor.execute(query, (src,))
        return [dict(zip(['src', 'kind', 'value', 'line'], row, strict=True)) for row in cursor.fetchall()]


class ResolvedFlowAuditTable:
    """Accessor class for resolved_flow_audit table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from resolved_flow_audit."""
        query = build_query('resolved_flow_audit', ['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'])
        cursor.execute(query)
        return [dict(zip(['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_vulnerability_type(cursor: sqlite3.Cursor, vulnerability_type: str) -> list[dict[str, Any]]:
        """Get rows by vulnerability_type."""
        query = build_query('resolved_flow_audit', ['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], where="vulnerability_type = ?")
        cursor.execute(query, (vulnerability_type,))
        return [dict(zip(['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_path_length(cursor: sqlite3.Cursor, path_length: int) -> list[dict[str, Any]]:
        """Get rows by path_length."""
        query = build_query('resolved_flow_audit', ['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], where="path_length = ?")
        cursor.execute(query, (path_length,))
        return [dict(zip(['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_status(cursor: sqlite3.Cursor, status: str) -> list[dict[str, Any]]:
        """Get rows by status."""
        query = build_query('resolved_flow_audit', ['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], where="status = ?")
        cursor.execute(query, (status,))
        return [dict(zip(['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_sanitizer_method(cursor: sqlite3.Cursor, sanitizer_method: str) -> list[dict[str, Any]]:
        """Get rows by sanitizer_method."""
        query = build_query('resolved_flow_audit', ['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], where="sanitizer_method = ?")
        cursor.execute(query, (sanitizer_method,))
        return [dict(zip(['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_engine(cursor: sqlite3.Cursor, engine: str) -> list[dict[str, Any]]:
        """Get rows by engine."""
        query = build_query('resolved_flow_audit', ['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], where="engine = ?")
        cursor.execute(query, (engine,))
        return [dict(zip(['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive', 'status', 'sanitizer_file', 'sanitizer_line', 'sanitizer_method', 'engine'], row, strict=True)) for row in cursor.fetchall()]


class ReturnSourceVarsTable:
    """Accessor class for return_source_vars table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from return_source_vars."""
        query = build_query('return_source_vars', ['file', 'line', 'function_name', 'source_var', 'var_index'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'function_name', 'source_var', 'var_index'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_var(cursor: sqlite3.Cursor, source_var: str) -> list[dict[str, Any]]:
        """Get rows by source_var."""
        query = build_query('return_source_vars', ['file', 'line', 'function_name', 'source_var', 'var_index'], where="source_var = ?")
        cursor.execute(query, (source_var,))
        return [dict(zip(['file', 'line', 'function_name', 'source_var', 'var_index'], row, strict=True)) for row in cursor.fetchall()]


class RouterMountsTable:
    """Accessor class for router_mounts table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from router_mounts."""
        query = build_query('router_mounts', ['file', 'line', 'mount_path_expr', 'router_variable', 'is_literal'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'mount_path_expr', 'router_variable', 'is_literal'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('router_mounts', ['file', 'line', 'mount_path_expr', 'router_variable', 'is_literal'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'mount_path_expr', 'router_variable', 'is_literal'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_router_variable(cursor: sqlite3.Cursor, router_variable: str) -> list[dict[str, Any]]:
        """Get rows by router_variable."""
        query = build_query('router_mounts', ['file', 'line', 'mount_path_expr', 'router_variable', 'is_literal'], where="router_variable = ?")
        cursor.execute(query, (router_variable,))
        return [dict(zip(['file', 'line', 'mount_path_expr', 'router_variable', 'is_literal'], row, strict=True)) for row in cursor.fetchall()]


class RustAsyncFunctionsTable:
    """Accessor class for rust_async_functions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_async_functions."""
        query = build_query('rust_async_functions', ['file_path', 'line', 'function_name', 'return_type', 'has_await', 'await_count'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'function_name', 'return_type', 'has_await', 'await_count'], row, strict=True)) for row in cursor.fetchall()]


class RustAttributesTable:
    """Accessor class for rust_attributes table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_attributes."""
        query = build_query('rust_attributes', ['file_path', 'line', 'attribute_name', 'args', 'target_type', 'target_name', 'target_line'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'attribute_name', 'args', 'target_type', 'target_name', 'target_line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_attribute_name(cursor: sqlite3.Cursor, attribute_name: str) -> list[dict[str, Any]]:
        """Get rows by attribute_name."""
        query = build_query('rust_attributes', ['file_path', 'line', 'attribute_name', 'args', 'target_type', 'target_name', 'target_line'], where="attribute_name = ?")
        cursor.execute(query, (attribute_name,))
        return [dict(zip(['file_path', 'line', 'attribute_name', 'args', 'target_type', 'target_name', 'target_line'], row, strict=True)) for row in cursor.fetchall()]


class RustAwaitPointsTable:
    """Accessor class for rust_await_points table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_await_points."""
        query = build_query('rust_await_points', ['file_path', 'line', 'containing_function', 'awaited_expression'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'containing_function', 'awaited_expression'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_containing_function(cursor: sqlite3.Cursor, containing_function: str) -> list[dict[str, Any]]:
        """Get rows by containing_function."""
        query = build_query('rust_await_points', ['file_path', 'line', 'containing_function', 'awaited_expression'], where="containing_function = ?")
        cursor.execute(query, (containing_function,))
        return [dict(zip(['file_path', 'line', 'containing_function', 'awaited_expression'], row, strict=True)) for row in cursor.fetchall()]


class RustEnumVariantsTable:
    """Accessor class for rust_enum_variants table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_enum_variants."""
        query = build_query('rust_enum_variants', ['file_path', 'enum_line', 'variant_index', 'variant_name', 'variant_kind', 'fields_json', 'discriminant'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'enum_line', 'variant_index', 'variant_name', 'variant_kind', 'fields_json', 'discriminant'], row, strict=True)) for row in cursor.fetchall()]


class RustEnumsTable:
    """Accessor class for rust_enums table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_enums."""
        query = build_query('rust_enums', ['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'derives_json'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'derives_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('rust_enums', ['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'derives_json'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'derives_json'], row, strict=True)) for row in cursor.fetchall()]


class RustExternBlocksTable:
    """Accessor class for rust_extern_blocks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_extern_blocks."""
        query = build_query('rust_extern_blocks', ['file_path', 'line', 'end_line', 'abi'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'end_line', 'abi'], row, strict=True)) for row in cursor.fetchall()]


class RustExternFunctionsTable:
    """Accessor class for rust_extern_functions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_extern_functions."""
        query = build_query('rust_extern_functions', ['file_path', 'line', 'name', 'abi', 'return_type', 'params_json', 'is_variadic'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'name', 'abi', 'return_type', 'params_json', 'is_variadic'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('rust_extern_functions', ['file_path', 'line', 'name', 'abi', 'return_type', 'params_json', 'is_variadic'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file_path', 'line', 'name', 'abi', 'return_type', 'params_json', 'is_variadic'], row, strict=True)) for row in cursor.fetchall()]


class RustFunctionsTable:
    """Accessor class for rust_functions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_functions."""
        query = build_query('rust_functions', ['file_path', 'line', 'end_line', 'name', 'visibility', 'is_async', 'is_unsafe', 'is_const', 'is_extern', 'abi', 'return_type', 'params_json', 'generics', 'where_clause'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'end_line', 'name', 'visibility', 'is_async', 'is_unsafe', 'is_const', 'is_extern', 'abi', 'return_type', 'params_json', 'generics', 'where_clause'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('rust_functions', ['file_path', 'line', 'end_line', 'name', 'visibility', 'is_async', 'is_unsafe', 'is_const', 'is_extern', 'abi', 'return_type', 'params_json', 'generics', 'where_clause'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file_path', 'line', 'end_line', 'name', 'visibility', 'is_async', 'is_unsafe', 'is_const', 'is_extern', 'abi', 'return_type', 'params_json', 'generics', 'where_clause'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_async(cursor: sqlite3.Cursor, is_async: bool) -> list[dict[str, Any]]:
        """Get rows by is_async."""
        query = build_query('rust_functions', ['file_path', 'line', 'end_line', 'name', 'visibility', 'is_async', 'is_unsafe', 'is_const', 'is_extern', 'abi', 'return_type', 'params_json', 'generics', 'where_clause'], where="is_async = ?")
        cursor.execute(query, (is_async,))
        return [dict(zip(['file_path', 'line', 'end_line', 'name', 'visibility', 'is_async', 'is_unsafe', 'is_const', 'is_extern', 'abi', 'return_type', 'params_json', 'generics', 'where_clause'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_unsafe(cursor: sqlite3.Cursor, is_unsafe: bool) -> list[dict[str, Any]]:
        """Get rows by is_unsafe."""
        query = build_query('rust_functions', ['file_path', 'line', 'end_line', 'name', 'visibility', 'is_async', 'is_unsafe', 'is_const', 'is_extern', 'abi', 'return_type', 'params_json', 'generics', 'where_clause'], where="is_unsafe = ?")
        cursor.execute(query, (is_unsafe,))
        return [dict(zip(['file_path', 'line', 'end_line', 'name', 'visibility', 'is_async', 'is_unsafe', 'is_const', 'is_extern', 'abi', 'return_type', 'params_json', 'generics', 'where_clause'], row, strict=True)) for row in cursor.fetchall()]


class RustGenericsTable:
    """Accessor class for rust_generics table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_generics."""
        query = build_query('rust_generics', ['file_path', 'parent_line', 'parent_type', 'param_name', 'param_kind', 'bounds', 'default_value'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'parent_line', 'parent_type', 'param_name', 'param_kind', 'bounds', 'default_value'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_parent_type(cursor: sqlite3.Cursor, parent_type: str) -> list[dict[str, Any]]:
        """Get rows by parent_type."""
        query = build_query('rust_generics', ['file_path', 'parent_line', 'parent_type', 'param_name', 'param_kind', 'bounds', 'default_value'], where="parent_type = ?")
        cursor.execute(query, (parent_type,))
        return [dict(zip(['file_path', 'parent_line', 'parent_type', 'param_name', 'param_kind', 'bounds', 'default_value'], row, strict=True)) for row in cursor.fetchall()]


class RustImplBlocksTable:
    """Accessor class for rust_impl_blocks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_impl_blocks."""
        query = build_query('rust_impl_blocks', ['file_path', 'line', 'end_line', 'target_type_raw', 'target_type_resolved', 'trait_name', 'trait_resolved', 'generics', 'where_clause', 'is_unsafe'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'end_line', 'target_type_raw', 'target_type_resolved', 'trait_name', 'trait_resolved', 'generics', 'where_clause', 'is_unsafe'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_type_raw(cursor: sqlite3.Cursor, target_type_raw: str) -> list[dict[str, Any]]:
        """Get rows by target_type_raw."""
        query = build_query('rust_impl_blocks', ['file_path', 'line', 'end_line', 'target_type_raw', 'target_type_resolved', 'trait_name', 'trait_resolved', 'generics', 'where_clause', 'is_unsafe'], where="target_type_raw = ?")
        cursor.execute(query, (target_type_raw,))
        return [dict(zip(['file_path', 'line', 'end_line', 'target_type_raw', 'target_type_resolved', 'trait_name', 'trait_resolved', 'generics', 'where_clause', 'is_unsafe'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_type_resolved(cursor: sqlite3.Cursor, target_type_resolved: str) -> list[dict[str, Any]]:
        """Get rows by target_type_resolved."""
        query = build_query('rust_impl_blocks', ['file_path', 'line', 'end_line', 'target_type_raw', 'target_type_resolved', 'trait_name', 'trait_resolved', 'generics', 'where_clause', 'is_unsafe'], where="target_type_resolved = ?")
        cursor.execute(query, (target_type_resolved,))
        return [dict(zip(['file_path', 'line', 'end_line', 'target_type_raw', 'target_type_resolved', 'trait_name', 'trait_resolved', 'generics', 'where_clause', 'is_unsafe'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_trait_name(cursor: sqlite3.Cursor, trait_name: str) -> list[dict[str, Any]]:
        """Get rows by trait_name."""
        query = build_query('rust_impl_blocks', ['file_path', 'line', 'end_line', 'target_type_raw', 'target_type_resolved', 'trait_name', 'trait_resolved', 'generics', 'where_clause', 'is_unsafe'], where="trait_name = ?")
        cursor.execute(query, (trait_name,))
        return [dict(zip(['file_path', 'line', 'end_line', 'target_type_raw', 'target_type_resolved', 'trait_name', 'trait_resolved', 'generics', 'where_clause', 'is_unsafe'], row, strict=True)) for row in cursor.fetchall()]


class RustLifetimesTable:
    """Accessor class for rust_lifetimes table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_lifetimes."""
        query = build_query('rust_lifetimes', ['file_path', 'parent_line', 'lifetime_name', 'is_static'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'parent_line', 'lifetime_name', 'is_static'], row, strict=True)) for row in cursor.fetchall()]


class RustMacroInvocationsTable:
    """Accessor class for rust_macro_invocations table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_macro_invocations."""
        query = build_query('rust_macro_invocations', ['file_path', 'line', 'macro_name', 'containing_function', 'args_sample'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'macro_name', 'containing_function', 'args_sample'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_macro_name(cursor: sqlite3.Cursor, macro_name: str) -> list[dict[str, Any]]:
        """Get rows by macro_name."""
        query = build_query('rust_macro_invocations', ['file_path', 'line', 'macro_name', 'containing_function', 'args_sample'], where="macro_name = ?")
        cursor.execute(query, (macro_name,))
        return [dict(zip(['file_path', 'line', 'macro_name', 'containing_function', 'args_sample'], row, strict=True)) for row in cursor.fetchall()]


class RustMacrosTable:
    """Accessor class for rust_macros table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_macros."""
        query = build_query('rust_macros', ['file_path', 'line', 'name', 'macro_type', 'visibility'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'name', 'macro_type', 'visibility'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('rust_macros', ['file_path', 'line', 'name', 'macro_type', 'visibility'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file_path', 'line', 'name', 'macro_type', 'visibility'], row, strict=True)) for row in cursor.fetchall()]


class RustModulesTable:
    """Accessor class for rust_modules table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_modules."""
        query = build_query('rust_modules', ['file_path', 'module_name', 'line', 'visibility', 'is_inline', 'parent_module'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'module_name', 'line', 'visibility', 'is_inline', 'parent_module'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_name(cursor: sqlite3.Cursor, module_name: str) -> list[dict[str, Any]]:
        """Get rows by module_name."""
        query = build_query('rust_modules', ['file_path', 'module_name', 'line', 'visibility', 'is_inline', 'parent_module'], where="module_name = ?")
        cursor.execute(query, (module_name,))
        return [dict(zip(['file_path', 'module_name', 'line', 'visibility', 'is_inline', 'parent_module'], row, strict=True)) for row in cursor.fetchall()]


class RustStructFieldsTable:
    """Accessor class for rust_struct_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_struct_fields."""
        query = build_query('rust_struct_fields', ['file_path', 'struct_line', 'field_index', 'field_name', 'field_type', 'visibility', 'is_pub'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'struct_line', 'field_index', 'field_name', 'field_type', 'visibility', 'is_pub'], row, strict=True)) for row in cursor.fetchall()]


class RustStructsTable:
    """Accessor class for rust_structs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_structs."""
        query = build_query('rust_structs', ['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'is_tuple_struct', 'is_unit_struct', 'derives_json'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'is_tuple_struct', 'is_unit_struct', 'derives_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('rust_structs', ['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'is_tuple_struct', 'is_unit_struct', 'derives_json'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'is_tuple_struct', 'is_unit_struct', 'derives_json'], row, strict=True)) for row in cursor.fetchall()]


class RustTraitMethodsTable:
    """Accessor class for rust_trait_methods table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_trait_methods."""
        query = build_query('rust_trait_methods', ['file_path', 'trait_line', 'method_line', 'method_name', 'return_type', 'params_json', 'has_default', 'is_async'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'trait_line', 'method_line', 'method_name', 'return_type', 'params_json', 'has_default', 'is_async'], row, strict=True)) for row in cursor.fetchall()]


class RustTraitsTable:
    """Accessor class for rust_traits table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_traits."""
        query = build_query('rust_traits', ['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'supertraits', 'is_unsafe', 'is_auto'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'supertraits', 'is_unsafe', 'is_auto'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('rust_traits', ['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'supertraits', 'is_unsafe', 'is_auto'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file_path', 'line', 'end_line', 'name', 'visibility', 'generics', 'supertraits', 'is_unsafe', 'is_auto'], row, strict=True)) for row in cursor.fetchall()]


class RustUnsafeBlocksTable:
    """Accessor class for rust_unsafe_blocks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_unsafe_blocks."""
        query = build_query('rust_unsafe_blocks', ['file_path', 'line_start', 'line_end', 'containing_function', 'reason', 'safety_comment', 'has_safety_comment', 'operations_json'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line_start', 'line_end', 'containing_function', 'reason', 'safety_comment', 'has_safety_comment', 'operations_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_containing_function(cursor: sqlite3.Cursor, containing_function: str) -> list[dict[str, Any]]:
        """Get rows by containing_function."""
        query = build_query('rust_unsafe_blocks', ['file_path', 'line_start', 'line_end', 'containing_function', 'reason', 'safety_comment', 'has_safety_comment', 'operations_json'], where="containing_function = ?")
        cursor.execute(query, (containing_function,))
        return [dict(zip(['file_path', 'line_start', 'line_end', 'containing_function', 'reason', 'safety_comment', 'has_safety_comment', 'operations_json'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_safety_comment(cursor: sqlite3.Cursor, has_safety_comment: bool) -> list[dict[str, Any]]:
        """Get rows by has_safety_comment."""
        query = build_query('rust_unsafe_blocks', ['file_path', 'line_start', 'line_end', 'containing_function', 'reason', 'safety_comment', 'has_safety_comment', 'operations_json'], where="has_safety_comment = ?")
        cursor.execute(query, (has_safety_comment,))
        return [dict(zip(['file_path', 'line_start', 'line_end', 'containing_function', 'reason', 'safety_comment', 'has_safety_comment', 'operations_json'], row, strict=True)) for row in cursor.fetchall()]


class RustUnsafeTraitsTable:
    """Accessor class for rust_unsafe_traits table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_unsafe_traits."""
        query = build_query('rust_unsafe_traits', ['file_path', 'line', 'trait_name', 'impl_type'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'trait_name', 'impl_type'], row, strict=True)) for row in cursor.fetchall()]


class RustUseStatementsTable:
    """Accessor class for rust_use_statements table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from rust_use_statements."""
        query = build_query('rust_use_statements', ['file_path', 'line', 'import_path', 'local_name', 'canonical_path', 'is_glob', 'visibility'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'import_path', 'local_name', 'canonical_path', 'is_glob', 'visibility'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_canonical_path(cursor: sqlite3.Cursor, canonical_path: str) -> list[dict[str, Any]]:
        """Get rows by canonical_path."""
        query = build_query('rust_use_statements', ['file_path', 'line', 'import_path', 'local_name', 'canonical_path', 'is_glob', 'visibility'], where="canonical_path = ?")
        cursor.execute(query, (canonical_path,))
        return [dict(zip(['file_path', 'line', 'import_path', 'local_name', 'canonical_path', 'is_glob', 'visibility'], row, strict=True)) for row in cursor.fetchall()]


class SequelizeAssociationsTable:
    """Accessor class for sequelize_associations table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from sequelize_associations."""
        query = build_query('sequelize_associations', ['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('sequelize_associations', ['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> list[dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('sequelize_associations', ['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_model(cursor: sqlite3.Cursor, target_model: str) -> list[dict[str, Any]]:
        """Get rows by target_model."""
        query = build_query('sequelize_associations', ['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], where="target_model = ?")
        cursor.execute(query, (target_model,))
        return [dict(zip(['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_association_type(cursor: sqlite3.Cursor, association_type: str) -> list[dict[str, Any]]:
        """Get rows by association_type."""
        query = build_query('sequelize_associations', ['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], where="association_type = ?")
        cursor.execute(query, (association_type,))
        return [dict(zip(['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], row, strict=True)) for row in cursor.fetchall()]


class SequelizeModelFieldsTable:
    """Accessor class for sequelize_model_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from sequelize_model_fields."""
        query = build_query('sequelize_model_fields', ['file', 'model_name', 'field_name', 'data_type', 'is_primary_key', 'is_nullable', 'is_unique', 'default_value'])
        cursor.execute(query)
        return [dict(zip(['file', 'model_name', 'field_name', 'data_type', 'is_primary_key', 'is_nullable', 'is_unique', 'default_value'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_data_type(cursor: sqlite3.Cursor, data_type: str) -> list[dict[str, Any]]:
        """Get rows by data_type."""
        query = build_query('sequelize_model_fields', ['file', 'model_name', 'field_name', 'data_type', 'is_primary_key', 'is_nullable', 'is_unique', 'default_value'], where="data_type = ?")
        cursor.execute(query, (data_type,))
        return [dict(zip(['file', 'model_name', 'field_name', 'data_type', 'is_primary_key', 'is_nullable', 'is_unique', 'default_value'], row, strict=True)) for row in cursor.fetchall()]


class SequelizeModelsTable:
    """Accessor class for sequelize_models table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from sequelize_models."""
        query = build_query('sequelize_models', ['file', 'line', 'model_name', 'table_name', 'extends_model'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'extends_model'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('sequelize_models', ['file', 'line', 'model_name', 'table_name', 'extends_model'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'extends_model'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> list[dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('sequelize_models', ['file', 'line', 'model_name', 'table_name', 'extends_model'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'extends_model'], row, strict=True)) for row in cursor.fetchall()]


class SqlObjectsTable:
    """Accessor class for sql_objects table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from sql_objects."""
        query = build_query('sql_objects', ['file', 'kind', 'name'])
        cursor.execute(query)
        return [dict(zip(['file', 'kind', 'name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('sql_objects', ['file', 'kind', 'name'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'kind', 'name'], row, strict=True)) for row in cursor.fetchall()]


class SqlQueriesTable:
    """Accessor class for sql_queries table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from sql_queries."""
        query = build_query('sql_queries', ['file_path', 'line_number', 'query_text', 'command', 'extraction_source'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line_number', 'query_text', 'command', 'extraction_source'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('sql_queries', ['file_path', 'line_number', 'query_text', 'command', 'extraction_source'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'line_number', 'query_text', 'command', 'extraction_source'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_command(cursor: sqlite3.Cursor, command: str) -> list[dict[str, Any]]:
        """Get rows by command."""
        query = build_query('sql_queries', ['file_path', 'line_number', 'query_text', 'command', 'extraction_source'], where="command = ?")
        cursor.execute(query, (command,))
        return [dict(zip(['file_path', 'line_number', 'query_text', 'command', 'extraction_source'], row, strict=True)) for row in cursor.fetchall()]


class SqlQueryTablesTable:
    """Accessor class for sql_query_tables table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from sql_query_tables."""
        query = build_query('sql_query_tables', ['id', 'query_file', 'query_line', 'table_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'query_file', 'query_line', 'table_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_table_name(cursor: sqlite3.Cursor, table_name: str) -> list[dict[str, Any]]:
        """Get rows by table_name."""
        query = build_query('sql_query_tables', ['id', 'query_file', 'query_line', 'table_name'], where="table_name = ?")
        cursor.execute(query, (table_name,))
        return [dict(zip(['id', 'query_file', 'query_line', 'table_name'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_query_file(cursor: sqlite3.Cursor, query_file: str) -> list[dict[str, Any]]:
        """Get rows by query_file."""
        query = build_query('sql_query_tables', ['id', 'query_file', 'query_line', 'table_name'], where="query_file = ?")
        cursor.execute(query, (query_file,))
        return [dict(zip(['id', 'query_file', 'query_line', 'table_name'], row, strict=True)) for row in cursor.fetchall()]


class SymbolsTable:
    """Accessor class for symbols table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from symbols."""
        query = build_query('symbols', ['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'])
        cursor.execute(query)
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_path(cursor: sqlite3.Cursor, path: str) -> list[dict[str, Any]]:
        """Get rows by path."""
        query = build_query('symbols', ['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], where="path = ?")
        cursor.execute(query, (path,))
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type(cursor: sqlite3.Cursor, type: str) -> list[dict[str, Any]]:
        """Get rows by type."""
        query = build_query('symbols', ['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], where="type = ?")
        cursor.execute(query, (type,))
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('symbols', ['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], row, strict=True)) for row in cursor.fetchall()]


class SymbolsJsxTable:
    """Accessor class for symbols_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from symbols_jsx."""
        query = build_query('symbols_jsx', ['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_path(cursor: sqlite3.Cursor, path: str) -> list[dict[str, Any]]:
        """Get rows by path."""
        query = build_query('symbols_jsx', ['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'], where="path = ?")
        cursor.execute(query, (path,))
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type(cursor: sqlite3.Cursor, type: str) -> list[dict[str, Any]]:
        """Get rows by type."""
        query = build_query('symbols_jsx', ['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'], where="type = ?")
        cursor.execute(query, (type,))
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'], row, strict=True)) for row in cursor.fetchall()]


class TaintFlowsTable:
    """Accessor class for taint_flows table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from taint_flows."""
        query = build_query('taint_flows', ['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive'])
        cursor.execute(query)
        return [dict(zip(['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_vulnerability_type(cursor: sqlite3.Cursor, vulnerability_type: str) -> list[dict[str, Any]]:
        """Get rows by vulnerability_type."""
        query = build_query('taint_flows', ['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive'], where="vulnerability_type = ?")
        cursor.execute(query, (vulnerability_type,))
        return [dict(zip(['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_path_length(cursor: sqlite3.Cursor, path_length: int) -> list[dict[str, Any]]:
        """Get rows by path_length."""
        query = build_query('taint_flows', ['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive'], where="path_length = ?")
        cursor.execute(query, (path_length,))
        return [dict(zip(['id', 'source_file', 'source_line', 'source_pattern', 'sink_file', 'sink_line', 'sink_pattern', 'vulnerability_type', 'path_length', 'hops', 'path_json', 'flow_sensitive'], row, strict=True)) for row in cursor.fetchall()]


class TerraformDataSourcesTable:
    """Accessor class for terraform_data_sources table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from terraform_data_sources."""
        query = build_query('terraform_data_sources', ['data_id', 'file_path', 'data_type', 'data_name', 'line'])
        cursor.execute(query)
        return [dict(zip(['data_id', 'file_path', 'data_type', 'data_name', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_data_sources', ['data_id', 'file_path', 'data_type', 'data_name', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['data_id', 'file_path', 'data_type', 'data_name', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_data_type(cursor: sqlite3.Cursor, data_type: str) -> list[dict[str, Any]]:
        """Get rows by data_type."""
        query = build_query('terraform_data_sources', ['data_id', 'file_path', 'data_type', 'data_name', 'line'], where="data_type = ?")
        cursor.execute(query, (data_type,))
        return [dict(zip(['data_id', 'file_path', 'data_type', 'data_name', 'line'], row, strict=True)) for row in cursor.fetchall()]


class TerraformFilesTable:
    """Accessor class for terraform_files table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from terraform_files."""
        query = build_query('terraform_files', ['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_name(cursor: sqlite3.Cursor, module_name: str) -> list[dict[str, Any]]:
        """Get rows by module_name."""
        query = build_query('terraform_files', ['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'], where="module_name = ?")
        cursor.execute(query, (module_name,))
        return [dict(zip(['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_stack_name(cursor: sqlite3.Cursor, stack_name: str) -> list[dict[str, Any]]:
        """Get rows by stack_name."""
        query = build_query('terraform_files', ['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'], where="stack_name = ?")
        cursor.execute(query, (stack_name,))
        return [dict(zip(['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'], row, strict=True)) for row in cursor.fetchall()]


class TerraformFindingsTable:
    """Accessor class for terraform_findings table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from terraform_findings."""
        query = build_query('terraform_findings', ['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'])
        cursor.execute(query)
        return [dict(zip(['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_findings', ['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resource_id(cursor: sqlite3.Cursor, resource_id: str) -> list[dict[str, Any]]:
        """Get rows by resource_id."""
        query = build_query('terraform_findings', ['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], where="resource_id = ?")
        cursor.execute(query, (resource_id,))
        return [dict(zip(['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_severity(cursor: sqlite3.Cursor, severity: str) -> list[dict[str, Any]]:
        """Get rows by severity."""
        query = build_query('terraform_findings', ['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], where="severity = ?")
        cursor.execute(query, (severity,))
        return [dict(zip(['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_category(cursor: sqlite3.Cursor, category: str) -> list[dict[str, Any]]:
        """Get rows by category."""
        query = build_query('terraform_findings', ['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], where="category = ?")
        cursor.execute(query, (category,))
        return [dict(zip(['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], row, strict=True)) for row in cursor.fetchall()]


class TerraformOutputsTable:
    """Accessor class for terraform_outputs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from terraform_outputs."""
        query = build_query('terraform_outputs', ['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'])
        cursor.execute(query)
        return [dict(zip(['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_outputs', ['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_output_name(cursor: sqlite3.Cursor, output_name: str) -> list[dict[str, Any]]:
        """Get rows by output_name."""
        query = build_query('terraform_outputs', ['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], where="output_name = ?")
        cursor.execute(query, (output_name,))
        return [dict(zip(['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_sensitive(cursor: sqlite3.Cursor, is_sensitive: bool) -> list[dict[str, Any]]:
        """Get rows by is_sensitive."""
        query = build_query('terraform_outputs', ['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], where="is_sensitive = ?")
        cursor.execute(query, (is_sensitive,))
        return [dict(zip(['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], row, strict=True)) for row in cursor.fetchall()]


class TerraformResourceDepsTable:
    """Accessor class for terraform_resource_deps table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from terraform_resource_deps."""
        query = build_query('terraform_resource_deps', ['id', 'resource_id', 'depends_on_ref'])
        cursor.execute(query)
        return [dict(zip(['id', 'resource_id', 'depends_on_ref'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resource_id(cursor: sqlite3.Cursor, resource_id: str) -> list[dict[str, Any]]:
        """Get rows by resource_id."""
        query = build_query('terraform_resource_deps', ['id', 'resource_id', 'depends_on_ref'], where="resource_id = ?")
        cursor.execute(query, (resource_id,))
        return [dict(zip(['id', 'resource_id', 'depends_on_ref'], row, strict=True)) for row in cursor.fetchall()]


class TerraformResourcePropertiesTable:
    """Accessor class for terraform_resource_properties table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from terraform_resource_properties."""
        query = build_query('terraform_resource_properties', ['id', 'resource_id', 'property_name', 'property_value', 'is_sensitive'])
        cursor.execute(query)
        return [dict(zip(['id', 'resource_id', 'property_name', 'property_value', 'is_sensitive'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resource_id(cursor: sqlite3.Cursor, resource_id: str) -> list[dict[str, Any]]:
        """Get rows by resource_id."""
        query = build_query('terraform_resource_properties', ['id', 'resource_id', 'property_name', 'property_value', 'is_sensitive'], where="resource_id = ?")
        cursor.execute(query, (resource_id,))
        return [dict(zip(['id', 'resource_id', 'property_name', 'property_value', 'is_sensitive'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_name(cursor: sqlite3.Cursor, property_name: str) -> list[dict[str, Any]]:
        """Get rows by property_name."""
        query = build_query('terraform_resource_properties', ['id', 'resource_id', 'property_name', 'property_value', 'is_sensitive'], where="property_name = ?")
        cursor.execute(query, (property_name,))
        return [dict(zip(['id', 'resource_id', 'property_name', 'property_value', 'is_sensitive'], row, strict=True)) for row in cursor.fetchall()]


class TerraformResourcesTable:
    """Accessor class for terraform_resources table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from terraform_resources."""
        query = build_query('terraform_resources', ['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'has_public_exposure', 'line'])
        cursor.execute(query)
        return [dict(zip(['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'has_public_exposure', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_resources', ['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'has_public_exposure', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'has_public_exposure', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resource_type(cursor: sqlite3.Cursor, resource_type: str) -> list[dict[str, Any]]:
        """Get rows by resource_type."""
        query = build_query('terraform_resources', ['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'has_public_exposure', 'line'], where="resource_type = ?")
        cursor.execute(query, (resource_type,))
        return [dict(zip(['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'has_public_exposure', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resource_name(cursor: sqlite3.Cursor, resource_name: str) -> list[dict[str, Any]]:
        """Get rows by resource_name."""
        query = build_query('terraform_resources', ['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'has_public_exposure', 'line'], where="resource_name = ?")
        cursor.execute(query, (resource_name,))
        return [dict(zip(['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'has_public_exposure', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_public_exposure(cursor: sqlite3.Cursor, has_public_exposure: bool) -> list[dict[str, Any]]:
        """Get rows by has_public_exposure."""
        query = build_query('terraform_resources', ['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'has_public_exposure', 'line'], where="has_public_exposure = ?")
        cursor.execute(query, (has_public_exposure,))
        return [dict(zip(['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'has_public_exposure', 'line'], row, strict=True)) for row in cursor.fetchall()]


class TerraformVariableValuesTable:
    """Accessor class for terraform_variable_values table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from terraform_variable_values."""
        query = build_query('terraform_variable_values', ['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_variable_values', ['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_variable_name(cursor: sqlite3.Cursor, variable_name: str) -> list[dict[str, Any]]:
        """Get rows by variable_name."""
        query = build_query('terraform_variable_values', ['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], where="variable_name = ?")
        cursor.execute(query, (variable_name,))
        return [dict(zip(['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_sensitive_context(cursor: sqlite3.Cursor, is_sensitive_context: bool) -> list[dict[str, Any]]:
        """Get rows by is_sensitive_context."""
        query = build_query('terraform_variable_values', ['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], where="is_sensitive_context = ?")
        cursor.execute(query, (is_sensitive_context,))
        return [dict(zip(['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], row, strict=True)) for row in cursor.fetchall()]


class TerraformVariablesTable:
    """Accessor class for terraform_variables table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from terraform_variables."""
        query = build_query('terraform_variables', ['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'])
        cursor.execute(query)
        return [dict(zip(['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> list[dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_variables', ['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_variable_name(cursor: sqlite3.Cursor, variable_name: str) -> list[dict[str, Any]]:
        """Get rows by variable_name."""
        query = build_query('terraform_variables', ['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], where="variable_name = ?")
        cursor.execute(query, (variable_name,))
        return [dict(zip(['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_sensitive(cursor: sqlite3.Cursor, is_sensitive: bool) -> list[dict[str, Any]]:
        """Get rows by is_sensitive."""
        query = build_query('terraform_variables', ['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], where="is_sensitive = ?")
        cursor.execute(query, (is_sensitive,))
        return [dict(zip(['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], row, strict=True)) for row in cursor.fetchall()]


class TypeAnnotationsTable:
    """Accessor class for type_annotations table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from type_annotations."""
        query = build_query('type_annotations', ['file', 'line', 'column', 'symbol_name', 'symbol_kind', 'type_annotation', 'is_any', 'is_unknown', 'is_generic', 'has_type_params', 'type_params', 'return_type', 'extends_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'column', 'symbol_name', 'symbol_kind', 'type_annotation', 'is_any', 'is_unknown', 'is_generic', 'has_type_params', 'type_params', 'return_type', 'extends_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('type_annotations', ['file', 'line', 'column', 'symbol_name', 'symbol_kind', 'type_annotation', 'is_any', 'is_unknown', 'is_generic', 'has_type_params', 'type_params', 'return_type', 'extends_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'column', 'symbol_name', 'symbol_kind', 'type_annotation', 'is_any', 'is_unknown', 'is_generic', 'has_type_params', 'type_params', 'return_type', 'extends_type'], row, strict=True)) for row in cursor.fetchall()]


class ValidationFrameworkUsageTable:
    """Accessor class for validation_framework_usage table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from validation_framework_usage."""
        query = build_query('validation_framework_usage', ['file_path', 'line', 'framework', 'method', 'variable_name', 'is_validator', 'argument_expr'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'framework', 'method', 'variable_name', 'is_validator', 'argument_expr'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_validator(cursor: sqlite3.Cursor, is_validator: bool) -> list[dict[str, Any]]:
        """Get rows by is_validator."""
        query = build_query('validation_framework_usage', ['file_path', 'line', 'framework', 'method', 'variable_name', 'is_validator', 'argument_expr'], where="is_validator = ?")
        cursor.execute(query, (is_validator,))
        return [dict(zip(['file_path', 'line', 'framework', 'method', 'variable_name', 'is_validator', 'argument_expr'], row, strict=True)) for row in cursor.fetchall()]


class VariableUsageTable:
    """Accessor class for variable_usage table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from variable_usage."""
        query = build_query('variable_usage', ['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('variable_usage', ['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_component(cursor: sqlite3.Cursor, in_component: str) -> list[dict[str, Any]]:
        """Get rows by in_component."""
        query = build_query('variable_usage', ['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], where="in_component = ?")
        cursor.execute(query, (in_component,))
        return [dict(zip(['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_variable_name(cursor: sqlite3.Cursor, variable_name: str) -> list[dict[str, Any]]:
        """Get rows by variable_name."""
        query = build_query('variable_usage', ['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], where="variable_name = ?")
        cursor.execute(query, (variable_name,))
        return [dict(zip(['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], row, strict=True)) for row in cursor.fetchall()]


class VueComponentEmitsTable:
    """Accessor class for vue_component_emits table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from vue_component_emits."""
        query = build_query('vue_component_emits', ['file', 'component_name', 'emit_name', 'payload_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'component_name', 'emit_name', 'payload_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_component_emits', ['file', 'component_name', 'emit_name', 'payload_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'component_name', 'emit_name', 'payload_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_name(cursor: sqlite3.Cursor, component_name: str) -> list[dict[str, Any]]:
        """Get rows by component_name."""
        query = build_query('vue_component_emits', ['file', 'component_name', 'emit_name', 'payload_type'], where="component_name = ?")
        cursor.execute(query, (component_name,))
        return [dict(zip(['file', 'component_name', 'emit_name', 'payload_type'], row, strict=True)) for row in cursor.fetchall()]


class VueComponentPropsTable:
    """Accessor class for vue_component_props table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from vue_component_props."""
        query = build_query('vue_component_props', ['file', 'component_name', 'prop_name', 'prop_type', 'is_required', 'default_value'])
        cursor.execute(query)
        return [dict(zip(['file', 'component_name', 'prop_name', 'prop_type', 'is_required', 'default_value'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_component_props', ['file', 'component_name', 'prop_name', 'prop_type', 'is_required', 'default_value'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'component_name', 'prop_name', 'prop_type', 'is_required', 'default_value'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_name(cursor: sqlite3.Cursor, component_name: str) -> list[dict[str, Any]]:
        """Get rows by component_name."""
        query = build_query('vue_component_props', ['file', 'component_name', 'prop_name', 'prop_type', 'is_required', 'default_value'], where="component_name = ?")
        cursor.execute(query, (component_name,))
        return [dict(zip(['file', 'component_name', 'prop_name', 'prop_type', 'is_required', 'default_value'], row, strict=True)) for row in cursor.fetchall()]


class VueComponentSetupReturnsTable:
    """Accessor class for vue_component_setup_returns table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from vue_component_setup_returns."""
        query = build_query('vue_component_setup_returns', ['file', 'component_name', 'return_name', 'return_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'component_name', 'return_name', 'return_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_component_setup_returns', ['file', 'component_name', 'return_name', 'return_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'component_name', 'return_name', 'return_type'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_name(cursor: sqlite3.Cursor, component_name: str) -> list[dict[str, Any]]:
        """Get rows by component_name."""
        query = build_query('vue_component_setup_returns', ['file', 'component_name', 'return_name', 'return_type'], where="component_name = ?")
        cursor.execute(query, (component_name,))
        return [dict(zip(['file', 'component_name', 'return_name', 'return_type'], row, strict=True)) for row in cursor.fetchall()]


class VueComponentsTable:
    """Accessor class for vue_components table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from vue_components."""
        query = build_query('vue_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used'])
        cursor.execute(query)
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> list[dict[str, Any]]:
        """Get rows by name."""
        query = build_query('vue_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type(cursor: sqlite3.Cursor, type: str) -> list[dict[str, Any]]:
        """Get rows by type."""
        query = build_query('vue_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used'], where="type = ?")
        cursor.execute(query, (type,))
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used'], row, strict=True)) for row in cursor.fetchall()]


class VueDirectivesTable:
    """Accessor class for vue_directives table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from vue_directives."""
        query = build_query('vue_directives', ['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_directives', ['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_directive_name(cursor: sqlite3.Cursor, directive_name: str) -> list[dict[str, Any]]:
        """Get rows by directive_name."""
        query = build_query('vue_directives', ['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'], where="directive_name = ?")
        cursor.execute(query, (directive_name,))
        return [dict(zip(['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'], row, strict=True)) for row in cursor.fetchall()]


class VueHooksTable:
    """Accessor class for vue_hooks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from vue_hooks."""
        query = build_query('vue_hooks', ['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_hooks', ['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_name(cursor: sqlite3.Cursor, component_name: str) -> list[dict[str, Any]]:
        """Get rows by component_name."""
        query = build_query('vue_hooks', ['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], where="component_name = ?")
        cursor.execute(query, (component_name,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_hook_type(cursor: sqlite3.Cursor, hook_type: str) -> list[dict[str, Any]]:
        """Get rows by hook_type."""
        query = build_query('vue_hooks', ['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], where="hook_type = ?")
        cursor.execute(query, (hook_type,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], row, strict=True)) for row in cursor.fetchall()]


class VueProvideInjectTable:
    """Accessor class for vue_provide_inject table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
        """Get all rows from vue_provide_inject."""
        query = build_query('vue_provide_inject', ['file', 'line', 'component_name', 'operation_type', 'key_name', 'value_expr', 'is_reactive'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'component_name', 'operation_type', 'key_name', 'value_expr', 'is_reactive'], row, strict=True)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> list[dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_provide_inject', ['file', 'line', 'component_name', 'operation_type', 'key_name', 'value_expr', 'is_reactive'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'component_name', 'operation_type', 'key_name', 'value_expr', 'is_reactive'], row, strict=True)) for row in cursor.fetchall()]

