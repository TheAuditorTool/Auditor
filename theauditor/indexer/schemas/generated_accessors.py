# Auto-generated accessor classes from schema
from typing import List, Optional, Dict, Any
import sqlite3
from ..schema import build_query

class AngularComponentsTable:
    """Accessor class for angular_components table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from angular_components."""
        query = build_query('angular_components', ['file', 'line', 'component_name', 'selector', 'template_path', 'style_paths', 'has_lifecycle_hooks'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'component_name', 'selector', 'template_path', 'style_paths', 'has_lifecycle_hooks'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_components', ['file', 'line', 'component_name', 'selector', 'template_path', 'style_paths', 'has_lifecycle_hooks'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'component_name', 'selector', 'template_path', 'style_paths', 'has_lifecycle_hooks'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_name(cursor: sqlite3.Cursor, component_name: str) -> List[Dict[str, Any]]:
        """Get rows by component_name."""
        query = build_query('angular_components', ['file', 'line', 'component_name', 'selector', 'template_path', 'style_paths', 'has_lifecycle_hooks'], where="component_name = ?")
        cursor.execute(query, (component_name,))
        return [dict(zip(['file', 'line', 'component_name', 'selector', 'template_path', 'style_paths', 'has_lifecycle_hooks'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_selector(cursor: sqlite3.Cursor, selector: str) -> List[Dict[str, Any]]:
        """Get rows by selector."""
        query = build_query('angular_components', ['file', 'line', 'component_name', 'selector', 'template_path', 'style_paths', 'has_lifecycle_hooks'], where="selector = ?")
        cursor.execute(query, (selector,))
        return [dict(zip(['file', 'line', 'component_name', 'selector', 'template_path', 'style_paths', 'has_lifecycle_hooks'], row)) for row in cursor.fetchall()]


class AngularGuardsTable:
    """Accessor class for angular_guards table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from angular_guards."""
        query = build_query('angular_guards', ['file', 'line', 'guard_name', 'guard_type', 'implements_interface'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_guards', ['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_guard_name(cursor: sqlite3.Cursor, guard_name: str) -> List[Dict[str, Any]]:
        """Get rows by guard_name."""
        query = build_query('angular_guards', ['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], where="guard_name = ?")
        cursor.execute(query, (guard_name,))
        return [dict(zip(['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_guard_type(cursor: sqlite3.Cursor, guard_type: str) -> List[Dict[str, Any]]:
        """Get rows by guard_type."""
        query = build_query('angular_guards', ['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], where="guard_type = ?")
        cursor.execute(query, (guard_type,))
        return [dict(zip(['file', 'line', 'guard_name', 'guard_type', 'implements_interface'], row)) for row in cursor.fetchall()]


class AngularModulesTable:
    """Accessor class for angular_modules table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from angular_modules."""
        query = build_query('angular_modules', ['file', 'line', 'module_name', 'declarations', 'imports', 'providers', 'exports'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'module_name', 'declarations', 'imports', 'providers', 'exports'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_modules', ['file', 'line', 'module_name', 'declarations', 'imports', 'providers', 'exports'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'module_name', 'declarations', 'imports', 'providers', 'exports'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_name(cursor: sqlite3.Cursor, module_name: str) -> List[Dict[str, Any]]:
        """Get rows by module_name."""
        query = build_query('angular_modules', ['file', 'line', 'module_name', 'declarations', 'imports', 'providers', 'exports'], where="module_name = ?")
        cursor.execute(query, (module_name,))
        return [dict(zip(['file', 'line', 'module_name', 'declarations', 'imports', 'providers', 'exports'], row)) for row in cursor.fetchall()]


class AngularServicesTable:
    """Accessor class for angular_services table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from angular_services."""
        query = build_query('angular_services', ['file', 'line', 'service_name', 'is_injectable', 'provided_in'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'service_name', 'is_injectable', 'provided_in'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('angular_services', ['file', 'line', 'service_name', 'is_injectable', 'provided_in'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'service_name', 'is_injectable', 'provided_in'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_service_name(cursor: sqlite3.Cursor, service_name: str) -> List[Dict[str, Any]]:
        """Get rows by service_name."""
        query = build_query('angular_services', ['file', 'line', 'service_name', 'is_injectable', 'provided_in'], where="service_name = ?")
        cursor.execute(query, (service_name,))
        return [dict(zip(['file', 'line', 'service_name', 'is_injectable', 'provided_in'], row)) for row in cursor.fetchall()]


class ApiEndpointControlsTable:
    """Accessor class for api_endpoint_controls table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from api_endpoint_controls."""
        query = build_query('api_endpoint_controls', ['id', 'endpoint_file', 'endpoint_line', 'control_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'endpoint_file', 'endpoint_line', 'control_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_control_name(cursor: sqlite3.Cursor, control_name: str) -> List[Dict[str, Any]]:
        """Get rows by control_name."""
        query = build_query('api_endpoint_controls', ['id', 'endpoint_file', 'endpoint_line', 'control_name'], where="control_name = ?")
        cursor.execute(query, (control_name,))
        return [dict(zip(['id', 'endpoint_file', 'endpoint_line', 'control_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_endpoint_file(cursor: sqlite3.Cursor, endpoint_file: str) -> List[Dict[str, Any]]:
        """Get rows by endpoint_file."""
        query = build_query('api_endpoint_controls', ['id', 'endpoint_file', 'endpoint_line', 'control_name'], where="endpoint_file = ?")
        cursor.execute(query, (endpoint_file,))
        return [dict(zip(['id', 'endpoint_file', 'endpoint_line', 'control_name'], row)) for row in cursor.fetchall()]


class ApiEndpointsTable:
    """Accessor class for api_endpoints table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from api_endpoints."""
        query = build_query('api_endpoints', ['file', 'line', 'method', 'pattern', 'path', 'has_auth', 'handler_function'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'method', 'pattern', 'path', 'has_auth', 'handler_function'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('api_endpoints', ['file', 'line', 'method', 'pattern', 'path', 'has_auth', 'handler_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'method', 'pattern', 'path', 'has_auth', 'handler_function'], row)) for row in cursor.fetchall()]


class AssignmentSourcesTable:
    """Accessor class for assignment_sources table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from assignment_sources."""
        query = build_query('assignment_sources', ['id', 'assignment_file', 'assignment_line', 'assignment_target', 'source_var_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_target', 'source_var_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_var_name(cursor: sqlite3.Cursor, source_var_name: str) -> List[Dict[str, Any]]:
        """Get rows by source_var_name."""
        query = build_query('assignment_sources', ['id', 'assignment_file', 'assignment_line', 'assignment_target', 'source_var_name'], where="source_var_name = ?")
        cursor.execute(query, (source_var_name,))
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_target', 'source_var_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_assignment_file(cursor: sqlite3.Cursor, assignment_file: str) -> List[Dict[str, Any]]:
        """Get rows by assignment_file."""
        query = build_query('assignment_sources', ['id', 'assignment_file', 'assignment_line', 'assignment_target', 'source_var_name'], where="assignment_file = ?")
        cursor.execute(query, (assignment_file,))
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_target', 'source_var_name'], row)) for row in cursor.fetchall()]


class AssignmentSourcesJsxTable:
    """Accessor class for assignment_sources_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from assignment_sources_jsx."""
        query = build_query('assignment_sources_jsx', ['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_var_name(cursor: sqlite3.Cursor, source_var_name: str) -> List[Dict[str, Any]]:
        """Get rows by source_var_name."""
        query = build_query('assignment_sources_jsx', ['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'], where="source_var_name = ?")
        cursor.execute(query, (source_var_name,))
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_assignment_file(cursor: sqlite3.Cursor, assignment_file: str) -> List[Dict[str, Any]]:
        """Get rows by assignment_file."""
        query = build_query('assignment_sources_jsx', ['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'], where="assignment_file = ?")
        cursor.execute(query, (assignment_file,))
        return [dict(zip(['id', 'assignment_file', 'assignment_line', 'assignment_target', 'jsx_mode', 'source_var_name'], row)) for row in cursor.fetchall()]


class AssignmentsTable:
    """Accessor class for assignments table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from assignments."""
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> List[Dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_var(cursor: sqlite3.Cursor, target_var: str) -> List[Dict[str, Any]]:
        """Get rows by target_var."""
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path'], where="target_var = ?")
        cursor.execute(query, (target_var,))
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_path(cursor: sqlite3.Cursor, property_path: str) -> List[Dict[str, Any]]:
        """Get rows by property_path."""
        query = build_query('assignments', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path'], where="property_path = ?")
        cursor.execute(query, (property_path,))
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path'], row)) for row in cursor.fetchall()]


class AssignmentsJsxTable:
    """Accessor class for assignments_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from assignments_jsx."""
        query = build_query('assignments_jsx', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('assignments_jsx', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_function(cursor: sqlite3.Cursor, in_function: str) -> List[Dict[str, Any]]:
        """Get rows by in_function."""
        query = build_query('assignments_jsx', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], where="in_function = ?")
        cursor.execute(query, (in_function,))
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_path(cursor: sqlite3.Cursor, property_path: str) -> List[Dict[str, Any]]:
        """Get rows by property_path."""
        query = build_query('assignments_jsx', ['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], where="property_path = ?")
        cursor.execute(query, (property_path,))
        return [dict(zip(['file', 'line', 'target_var', 'source_expr', 'in_function', 'property_path', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]


class BullmqQueuesTable:
    """Accessor class for bullmq_queues table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from bullmq_queues."""
        query = build_query('bullmq_queues', ['file', 'line', 'queue_name', 'redis_config'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'queue_name', 'redis_config'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bullmq_queues', ['file', 'line', 'queue_name', 'redis_config'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'queue_name', 'redis_config'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_queue_name(cursor: sqlite3.Cursor, queue_name: str) -> List[Dict[str, Any]]:
        """Get rows by queue_name."""
        query = build_query('bullmq_queues', ['file', 'line', 'queue_name', 'redis_config'], where="queue_name = ?")
        cursor.execute(query, (queue_name,))
        return [dict(zip(['file', 'line', 'queue_name', 'redis_config'], row)) for row in cursor.fetchall()]


class BullmqWorkersTable:
    """Accessor class for bullmq_workers table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from bullmq_workers."""
        query = build_query('bullmq_workers', ['file', 'line', 'queue_name', 'worker_function', 'processor_path'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'queue_name', 'worker_function', 'processor_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('bullmq_workers', ['file', 'line', 'queue_name', 'worker_function', 'processor_path'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'queue_name', 'worker_function', 'processor_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_queue_name(cursor: sqlite3.Cursor, queue_name: str) -> List[Dict[str, Any]]:
        """Get rows by queue_name."""
        query = build_query('bullmq_workers', ['file', 'line', 'queue_name', 'worker_function', 'processor_path'], where="queue_name = ?")
        cursor.execute(query, (queue_name,))
        return [dict(zip(['file', 'line', 'queue_name', 'worker_function', 'processor_path'], row)) for row in cursor.fetchall()]


class CdkConstructPropertiesTable:
    """Accessor class for cdk_construct_properties table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from cdk_construct_properties."""
        query = build_query('cdk_construct_properties', ['id', 'construct_id', 'property_name', 'property_value_expr', 'line'])
        cursor.execute(query)
        return [dict(zip(['id', 'construct_id', 'property_name', 'property_value_expr', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_construct_id(cursor: sqlite3.Cursor, construct_id: str) -> List[Dict[str, Any]]:
        """Get rows by construct_id."""
        query = build_query('cdk_construct_properties', ['id', 'construct_id', 'property_name', 'property_value_expr', 'line'], where="construct_id = ?")
        cursor.execute(query, (construct_id,))
        return [dict(zip(['id', 'construct_id', 'property_name', 'property_value_expr', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_name(cursor: sqlite3.Cursor, property_name: str) -> List[Dict[str, Any]]:
        """Get rows by property_name."""
        query = build_query('cdk_construct_properties', ['id', 'construct_id', 'property_name', 'property_value_expr', 'line'], where="property_name = ?")
        cursor.execute(query, (property_name,))
        return [dict(zip(['id', 'construct_id', 'property_name', 'property_value_expr', 'line'], row)) for row in cursor.fetchall()]


class CdkConstructsTable:
    """Accessor class for cdk_constructs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from cdk_constructs."""
        query = build_query('cdk_constructs', ['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'])
        cursor.execute(query)
        return [dict(zip(['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('cdk_constructs', ['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_cdk_class(cursor: sqlite3.Cursor, cdk_class: str) -> List[Dict[str, Any]]:
        """Get rows by cdk_class."""
        query = build_query('cdk_constructs', ['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'], where="cdk_class = ?")
        cursor.execute(query, (cdk_class,))
        return [dict(zip(['construct_id', 'file_path', 'line', 'cdk_class', 'construct_name'], row)) for row in cursor.fetchall()]


class CdkFindingsTable:
    """Accessor class for cdk_findings table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from cdk_findings."""
        query = build_query('cdk_findings', ['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'])
        cursor.execute(query)
        return [dict(zip(['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('cdk_findings', ['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_construct_id(cursor: sqlite3.Cursor, construct_id: str) -> List[Dict[str, Any]]:
        """Get rows by construct_id."""
        query = build_query('cdk_findings', ['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], where="construct_id = ?")
        cursor.execute(query, (construct_id,))
        return [dict(zip(['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_severity(cursor: sqlite3.Cursor, severity: str) -> List[Dict[str, Any]]:
        """Get rows by severity."""
        query = build_query('cdk_findings', ['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], where="severity = ?")
        cursor.execute(query, (severity,))
        return [dict(zip(['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_category(cursor: sqlite3.Cursor, category: str) -> List[Dict[str, Any]]:
        """Get rows by category."""
        query = build_query('cdk_findings', ['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], where="category = ?")
        cursor.execute(query, (category,))
        return [dict(zip(['finding_id', 'file_path', 'construct_id', 'category', 'severity', 'title', 'description', 'remediation', 'line'], row)) for row in cursor.fetchall()]


class CfgBlockStatementsTable:
    """Accessor class for cfg_block_statements table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from cfg_block_statements."""
        query = build_query('cfg_block_statements', ['block_id', 'statement_type', 'line', 'statement_text'])
        cursor.execute(query)
        return [dict(zip(['block_id', 'statement_type', 'line', 'statement_text'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_block_id(cursor: sqlite3.Cursor, block_id: int) -> List[Dict[str, Any]]:
        """Get rows by block_id."""
        query = build_query('cfg_block_statements', ['block_id', 'statement_type', 'line', 'statement_text'], where="block_id = ?")
        cursor.execute(query, (block_id,))
        return [dict(zip(['block_id', 'statement_type', 'line', 'statement_text'], row)) for row in cursor.fetchall()]


class CfgBlockStatementsJsxTable:
    """Accessor class for cfg_block_statements_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from cfg_block_statements_jsx."""
        query = build_query('cfg_block_statements_jsx', ['block_id', 'statement_type', 'line', 'statement_text', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['block_id', 'statement_type', 'line', 'statement_text', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_block_id(cursor: sqlite3.Cursor, block_id: int) -> List[Dict[str, Any]]:
        """Get rows by block_id."""
        query = build_query('cfg_block_statements_jsx', ['block_id', 'statement_type', 'line', 'statement_text', 'jsx_mode', 'extraction_pass'], where="block_id = ?")
        cursor.execute(query, (block_id,))
        return [dict(zip(['block_id', 'statement_type', 'line', 'statement_text', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]


class CfgBlocksTable:
    """Accessor class for cfg_blocks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from cfg_blocks."""
        query = build_query('cfg_blocks', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('cfg_blocks', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> List[Dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('cfg_blocks', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr'], row)) for row in cursor.fetchall()]


class CfgBlocksJsxTable:
    """Accessor class for cfg_blocks_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from cfg_blocks_jsx."""
        query = build_query('cfg_blocks_jsx', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('cfg_blocks_jsx', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> List[Dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('cfg_blocks_jsx', ['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['id', 'file', 'function_name', 'block_type', 'start_line', 'end_line', 'condition_expr', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]


class CfgEdgesTable:
    """Accessor class for cfg_edges table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from cfg_edges."""
        query = build_query('cfg_edges', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('cfg_edges', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> List[Dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('cfg_edges', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_block_id(cursor: sqlite3.Cursor, source_block_id: int) -> List[Dict[str, Any]]:
        """Get rows by source_block_id."""
        query = build_query('cfg_edges', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], where="source_block_id = ?")
        cursor.execute(query, (source_block_id,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_block_id(cursor: sqlite3.Cursor, target_block_id: int) -> List[Dict[str, Any]]:
        """Get rows by target_block_id."""
        query = build_query('cfg_edges', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], where="target_block_id = ?")
        cursor.execute(query, (target_block_id,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type'], row)) for row in cursor.fetchall()]


class CfgEdgesJsxTable:
    """Accessor class for cfg_edges_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from cfg_edges_jsx."""
        query = build_query('cfg_edges_jsx', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('cfg_edges_jsx', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> List[Dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('cfg_edges_jsx', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_block_id(cursor: sqlite3.Cursor, source_block_id: int) -> List[Dict[str, Any]]:
        """Get rows by source_block_id."""
        query = build_query('cfg_edges_jsx', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], where="source_block_id = ?")
        cursor.execute(query, (source_block_id,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_block_id(cursor: sqlite3.Cursor, target_block_id: int) -> List[Dict[str, Any]]:
        """Get rows by target_block_id."""
        query = build_query('cfg_edges_jsx', ['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], where="target_block_id = ?")
        cursor.execute(query, (target_block_id,))
        return [dict(zip(['id', 'file', 'function_name', 'source_block_id', 'target_block_id', 'edge_type', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]


class ClassPropertiesTable:
    """Accessor class for class_properties table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from class_properties."""
        query = build_query('class_properties', ['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('class_properties', ['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_class_name(cursor: sqlite3.Cursor, class_name: str) -> List[Dict[str, Any]]:
        """Get rows by class_name."""
        query = build_query('class_properties', ['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], where="class_name = ?")
        cursor.execute(query, (class_name,))
        return [dict(zip(['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_name(cursor: sqlite3.Cursor, property_name: str) -> List[Dict[str, Any]]:
        """Get rows by property_name."""
        query = build_query('class_properties', ['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], where="property_name = ?")
        cursor.execute(query, (property_name,))
        return [dict(zip(['file', 'line', 'class_name', 'property_name', 'property_type', 'is_optional', 'is_readonly', 'access_modifier', 'has_declare', 'initializer'], row)) for row in cursor.fetchall()]


class CodeDiffsTable:
    """Accessor class for code_diffs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from code_diffs."""
        query = build_query('code_diffs', ['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'])
        cursor.execute(query)
        return [dict(zip(['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_snapshot_id(cursor: sqlite3.Cursor, snapshot_id: int) -> List[Dict[str, Any]]:
        """Get rows by snapshot_id."""
        query = build_query('code_diffs', ['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'], where="snapshot_id = ?")
        cursor.execute(query, (snapshot_id,))
        return [dict(zip(['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('code_diffs', ['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'snapshot_id', 'file_path', 'diff_text', 'added_lines', 'removed_lines'], row)) for row in cursor.fetchall()]


class CodeSnapshotsTable:
    """Accessor class for code_snapshots table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from code_snapshots."""
        query = build_query('code_snapshots', ['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'files_json'])
        cursor.execute(query)
        return [dict(zip(['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'files_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_plan_id(cursor: sqlite3.Cursor, plan_id: int) -> List[Dict[str, Any]]:
        """Get rows by plan_id."""
        query = build_query('code_snapshots', ['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'files_json'], where="plan_id = ?")
        cursor.execute(query, (plan_id,))
        return [dict(zip(['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'files_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_task_id(cursor: sqlite3.Cursor, task_id: int) -> List[Dict[str, Any]]:
        """Get rows by task_id."""
        query = build_query('code_snapshots', ['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'files_json'], where="task_id = ?")
        cursor.execute(query, (task_id,))
        return [dict(zip(['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'files_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_timestamp(cursor: sqlite3.Cursor, timestamp: str) -> List[Dict[str, Any]]:
        """Get rows by timestamp."""
        query = build_query('code_snapshots', ['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'files_json'], where="timestamp = ?")
        cursor.execute(query, (timestamp,))
        return [dict(zip(['id', 'plan_id', 'task_id', 'sequence', 'checkpoint_name', 'timestamp', 'git_ref', 'files_json'], row)) for row in cursor.fetchall()]


class ComposeServicesTable:
    """Accessor class for compose_services table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from compose_services."""
        query = build_query('compose_services', ['file_path', 'service_name', 'image', 'ports', 'volumes', 'environment', 'is_privileged', 'network_mode', 'user', 'cap_add', 'cap_drop', 'security_opt', 'restart', 'command', 'entrypoint', 'depends_on', 'healthcheck'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'service_name', 'image', 'ports', 'volumes', 'environment', 'is_privileged', 'network_mode', 'user', 'cap_add', 'cap_drop', 'security_opt', 'restart', 'command', 'entrypoint', 'depends_on', 'healthcheck'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('compose_services', ['file_path', 'service_name', 'image', 'ports', 'volumes', 'environment', 'is_privileged', 'network_mode', 'user', 'cap_add', 'cap_drop', 'security_opt', 'restart', 'command', 'entrypoint', 'depends_on', 'healthcheck'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'service_name', 'image', 'ports', 'volumes', 'environment', 'is_privileged', 'network_mode', 'user', 'cap_add', 'cap_drop', 'security_opt', 'restart', 'command', 'entrypoint', 'depends_on', 'healthcheck'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_privileged(cursor: sqlite3.Cursor, is_privileged: bool) -> List[Dict[str, Any]]:
        """Get rows by is_privileged."""
        query = build_query('compose_services', ['file_path', 'service_name', 'image', 'ports', 'volumes', 'environment', 'is_privileged', 'network_mode', 'user', 'cap_add', 'cap_drop', 'security_opt', 'restart', 'command', 'entrypoint', 'depends_on', 'healthcheck'], where="is_privileged = ?")
        cursor.execute(query, (is_privileged,))
        return [dict(zip(['file_path', 'service_name', 'image', 'ports', 'volumes', 'environment', 'is_privileged', 'network_mode', 'user', 'cap_add', 'cap_drop', 'security_opt', 'restart', 'command', 'entrypoint', 'depends_on', 'healthcheck'], row)) for row in cursor.fetchall()]


class ConfigFilesTable:
    """Accessor class for config_files table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from config_files."""
        query = build_query('config_files', ['path', 'content', 'type', 'context_dir'])
        cursor.execute(query)
        return [dict(zip(['path', 'content', 'type', 'context_dir'], row)) for row in cursor.fetchall()]


class DiInjectionsTable:
    """Accessor class for di_injections table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from di_injections."""
        query = build_query('di_injections', ['file', 'line', 'target_class', 'injected_service', 'injection_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'target_class', 'injected_service', 'injection_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('di_injections', ['file', 'line', 'target_class', 'injected_service', 'injection_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'target_class', 'injected_service', 'injection_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_class(cursor: sqlite3.Cursor, target_class: str) -> List[Dict[str, Any]]:
        """Get rows by target_class."""
        query = build_query('di_injections', ['file', 'line', 'target_class', 'injected_service', 'injection_type'], where="target_class = ?")
        cursor.execute(query, (target_class,))
        return [dict(zip(['file', 'line', 'target_class', 'injected_service', 'injection_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_injected_service(cursor: sqlite3.Cursor, injected_service: str) -> List[Dict[str, Any]]:
        """Get rows by injected_service."""
        query = build_query('di_injections', ['file', 'line', 'target_class', 'injected_service', 'injection_type'], where="injected_service = ?")
        cursor.execute(query, (injected_service,))
        return [dict(zip(['file', 'line', 'target_class', 'injected_service', 'injection_type'], row)) for row in cursor.fetchall()]


class DockerImagesTable:
    """Accessor class for docker_images table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from docker_images."""
        query = build_query('docker_images', ['file_path', 'base_image', 'exposed_ports', 'env_vars', 'build_args', 'user', 'has_healthcheck'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'base_image', 'exposed_ports', 'env_vars', 'build_args', 'user', 'has_healthcheck'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_base_image(cursor: sqlite3.Cursor, base_image: str) -> List[Dict[str, Any]]:
        """Get rows by base_image."""
        query = build_query('docker_images', ['file_path', 'base_image', 'exposed_ports', 'env_vars', 'build_args', 'user', 'has_healthcheck'], where="base_image = ?")
        cursor.execute(query, (base_image,))
        return [dict(zip(['file_path', 'base_image', 'exposed_ports', 'env_vars', 'build_args', 'user', 'has_healthcheck'], row)) for row in cursor.fetchall()]


class EnvVarUsageTable:
    """Accessor class for env_var_usage table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from env_var_usage."""
        query = build_query('env_var_usage', ['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('env_var_usage', ['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_var_name(cursor: sqlite3.Cursor, var_name: str) -> List[Dict[str, Any]]:
        """Get rows by var_name."""
        query = build_query('env_var_usage', ['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], where="var_name = ?")
        cursor.execute(query, (var_name,))
        return [dict(zip(['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_access_type(cursor: sqlite3.Cursor, access_type: str) -> List[Dict[str, Any]]:
        """Get rows by access_type."""
        query = build_query('env_var_usage', ['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], where="access_type = ?")
        cursor.execute(query, (access_type,))
        return [dict(zip(['file', 'line', 'var_name', 'access_type', 'in_function', 'property_access'], row)) for row in cursor.fetchall()]


class FilesTable:
    """Accessor class for files table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from files."""
        query = build_query('files', ['path', 'sha256', 'ext', 'bytes', 'loc', 'file_category'])
        cursor.execute(query)
        return [dict(zip(['path', 'sha256', 'ext', 'bytes', 'loc', 'file_category'], row)) for row in cursor.fetchall()]


class FindingsConsolidatedTable:
    """Accessor class for findings_consolidated table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from findings_consolidated."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'details_json'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'details_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_tool(cursor: sqlite3.Cursor, tool: str) -> List[Dict[str, Any]]:
        """Get rows by tool."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'details_json'], where="tool = ?")
        cursor.execute(query, (tool,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'details_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_severity(cursor: sqlite3.Cursor, severity: str) -> List[Dict[str, Any]]:
        """Get rows by severity."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'details_json'], where="severity = ?")
        cursor.execute(query, (severity,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'details_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_rule(cursor: sqlite3.Cursor, rule: str) -> List[Dict[str, Any]]:
        """Get rows by rule."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'details_json'], where="rule = ?")
        cursor.execute(query, (rule,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'details_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_category(cursor: sqlite3.Cursor, category: str) -> List[Dict[str, Any]]:
        """Get rows by category."""
        query = build_query('findings_consolidated', ['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'details_json'], where="category = ?")
        cursor.execute(query, (category,))
        return [dict(zip(['id', 'file', 'line', 'column', 'rule', 'tool', 'message', 'severity', 'category', 'confidence', 'code_snippet', 'cwe', 'timestamp', 'details_json'], row)) for row in cursor.fetchall()]


class FrameworkSafeSinksTable:
    """Accessor class for framework_safe_sinks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from framework_safe_sinks."""
        query = build_query('framework_safe_sinks', ['framework_id', 'sink_pattern', 'sink_type', 'is_safe', 'reason'])
        cursor.execute(query)
        return [dict(zip(['framework_id', 'sink_pattern', 'sink_type', 'is_safe', 'reason'], row)) for row in cursor.fetchall()]


class FrameworksTable:
    """Accessor class for frameworks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from frameworks."""
        query = build_query('frameworks', ['id', 'name', 'version', 'language', 'path', 'source', 'package_manager', 'is_primary'])
        cursor.execute(query)
        return [dict(zip(['id', 'name', 'version', 'language', 'path', 'source', 'package_manager', 'is_primary'], row)) for row in cursor.fetchall()]


class FunctionCallArgsTable:
    """Accessor class for function_call_args table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from function_call_args."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_caller_function(cursor: sqlite3.Cursor, caller_function: str) -> List[Dict[str, Any]]:
        """Get rows by caller_function."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], where="caller_function = ?")
        cursor.execute(query, (caller_function,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_callee_function(cursor: sqlite3.Cursor, callee_function: str) -> List[Dict[str, Any]]:
        """Get rows by callee_function."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], where="callee_function = ?")
        cursor.execute(query, (callee_function,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_callee_file_path(cursor: sqlite3.Cursor, callee_file_path: str) -> List[Dict[str, Any]]:
        """Get rows by callee_file_path."""
        query = build_query('function_call_args', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], where="callee_file_path = ?")
        cursor.execute(query, (callee_file_path,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'callee_file_path'], row)) for row in cursor.fetchall()]


class FunctionCallArgsJsxTable:
    """Accessor class for function_call_args_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from function_call_args_jsx."""
        query = build_query('function_call_args_jsx', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('function_call_args_jsx', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_caller_function(cursor: sqlite3.Cursor, caller_function: str) -> List[Dict[str, Any]]:
        """Get rows by caller_function."""
        query = build_query('function_call_args_jsx', ['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'], where="caller_function = ?")
        cursor.execute(query, (caller_function,))
        return [dict(zip(['file', 'line', 'caller_function', 'callee_function', 'argument_index', 'argument_expr', 'param_name', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]


class FunctionReturnSourcesTable:
    """Accessor class for function_return_sources table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from function_return_sources."""
        query = build_query('function_return_sources', ['id', 'return_file', 'return_line', 'return_function', 'return_var_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'return_file', 'return_line', 'return_function', 'return_var_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_return_var_name(cursor: sqlite3.Cursor, return_var_name: str) -> List[Dict[str, Any]]:
        """Get rows by return_var_name."""
        query = build_query('function_return_sources', ['id', 'return_file', 'return_line', 'return_function', 'return_var_name'], where="return_var_name = ?")
        cursor.execute(query, (return_var_name,))
        return [dict(zip(['id', 'return_file', 'return_line', 'return_function', 'return_var_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_return_file(cursor: sqlite3.Cursor, return_file: str) -> List[Dict[str, Any]]:
        """Get rows by return_file."""
        query = build_query('function_return_sources', ['id', 'return_file', 'return_line', 'return_function', 'return_var_name'], where="return_file = ?")
        cursor.execute(query, (return_file,))
        return [dict(zip(['id', 'return_file', 'return_line', 'return_function', 'return_var_name'], row)) for row in cursor.fetchall()]


class FunctionReturnSourcesJsxTable:
    """Accessor class for function_return_sources_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from function_return_sources_jsx."""
        query = build_query('function_return_sources_jsx', ['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_return_var_name(cursor: sqlite3.Cursor, return_var_name: str) -> List[Dict[str, Any]]:
        """Get rows by return_var_name."""
        query = build_query('function_return_sources_jsx', ['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name'], where="return_var_name = ?")
        cursor.execute(query, (return_var_name,))
        return [dict(zip(['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_return_file(cursor: sqlite3.Cursor, return_file: str) -> List[Dict[str, Any]]:
        """Get rows by return_file."""
        query = build_query('function_return_sources_jsx', ['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name'], where="return_file = ?")
        cursor.execute(query, (return_file,))
        return [dict(zip(['id', 'return_file', 'return_line', 'return_function', 'jsx_mode', 'return_var_name'], row)) for row in cursor.fetchall()]


class FunctionReturnsTable:
    """Accessor class for function_returns table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from function_returns."""
        query = build_query('function_returns', ['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('function_returns', ['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> List[Dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('function_returns', ['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations'], row)) for row in cursor.fetchall()]


class FunctionReturnsJsxTable:
    """Accessor class for function_returns_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from function_returns_jsx."""
        query = build_query('function_returns_jsx', ['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('function_returns_jsx', ['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> List[Dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('function_returns_jsx', ['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['file', 'line', 'function_name', 'return_expr', 'has_jsx', 'returns_component', 'cleanup_operations', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]


class GithubJobDependenciesTable:
    """Accessor class for github_job_dependencies table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from github_job_dependencies."""
        query = build_query('github_job_dependencies', ['job_id', 'needs_job_id'])
        cursor.execute(query)
        return [dict(zip(['job_id', 'needs_job_id'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_job_id(cursor: sqlite3.Cursor, job_id: str) -> List[Dict[str, Any]]:
        """Get rows by job_id."""
        query = build_query('github_job_dependencies', ['job_id', 'needs_job_id'], where="job_id = ?")
        cursor.execute(query, (job_id,))
        return [dict(zip(['job_id', 'needs_job_id'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_needs_job_id(cursor: sqlite3.Cursor, needs_job_id: str) -> List[Dict[str, Any]]:
        """Get rows by needs_job_id."""
        query = build_query('github_job_dependencies', ['job_id', 'needs_job_id'], where="needs_job_id = ?")
        cursor.execute(query, (needs_job_id,))
        return [dict(zip(['job_id', 'needs_job_id'], row)) for row in cursor.fetchall()]


class GithubJobsTable:
    """Accessor class for github_jobs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from github_jobs."""
        query = build_query('github_jobs', ['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'])
        cursor.execute(query)
        return [dict(zip(['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_workflow_path(cursor: sqlite3.Cursor, workflow_path: str) -> List[Dict[str, Any]]:
        """Get rows by workflow_path."""
        query = build_query('github_jobs', ['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], where="workflow_path = ?")
        cursor.execute(query, (workflow_path,))
        return [dict(zip(['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_job_key(cursor: sqlite3.Cursor, job_key: str) -> List[Dict[str, Any]]:
        """Get rows by job_key."""
        query = build_query('github_jobs', ['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], where="job_key = ?")
        cursor.execute(query, (job_key,))
        return [dict(zip(['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_uses_reusable_workflow(cursor: sqlite3.Cursor, uses_reusable_workflow: bool) -> List[Dict[str, Any]]:
        """Get rows by uses_reusable_workflow."""
        query = build_query('github_jobs', ['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], where="uses_reusable_workflow = ?")
        cursor.execute(query, (uses_reusable_workflow,))
        return [dict(zip(['job_id', 'workflow_path', 'job_key', 'job_name', 'runs_on', 'strategy', 'permissions', 'env', 'if_condition', 'timeout_minutes', 'uses_reusable_workflow', 'reusable_workflow_path'], row)) for row in cursor.fetchall()]


class GithubStepOutputsTable:
    """Accessor class for github_step_outputs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from github_step_outputs."""
        query = build_query('github_step_outputs', ['id', 'step_id', 'output_name', 'output_expression'])
        cursor.execute(query)
        return [dict(zip(['id', 'step_id', 'output_name', 'output_expression'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_step_id(cursor: sqlite3.Cursor, step_id: str) -> List[Dict[str, Any]]:
        """Get rows by step_id."""
        query = build_query('github_step_outputs', ['id', 'step_id', 'output_name', 'output_expression'], where="step_id = ?")
        cursor.execute(query, (step_id,))
        return [dict(zip(['id', 'step_id', 'output_name', 'output_expression'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_output_name(cursor: sqlite3.Cursor, output_name: str) -> List[Dict[str, Any]]:
        """Get rows by output_name."""
        query = build_query('github_step_outputs', ['id', 'step_id', 'output_name', 'output_expression'], where="output_name = ?")
        cursor.execute(query, (output_name,))
        return [dict(zip(['id', 'step_id', 'output_name', 'output_expression'], row)) for row in cursor.fetchall()]


class GithubStepReferencesTable:
    """Accessor class for github_step_references table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from github_step_references."""
        query = build_query('github_step_references', ['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'])
        cursor.execute(query)
        return [dict(zip(['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_step_id(cursor: sqlite3.Cursor, step_id: str) -> List[Dict[str, Any]]:
        """Get rows by step_id."""
        query = build_query('github_step_references', ['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], where="step_id = ?")
        cursor.execute(query, (step_id,))
        return [dict(zip(['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_reference_type(cursor: sqlite3.Cursor, reference_type: str) -> List[Dict[str, Any]]:
        """Get rows by reference_type."""
        query = build_query('github_step_references', ['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], where="reference_type = ?")
        cursor.execute(query, (reference_type,))
        return [dict(zip(['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_reference_path(cursor: sqlite3.Cursor, reference_path: str) -> List[Dict[str, Any]]:
        """Get rows by reference_path."""
        query = build_query('github_step_references', ['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], where="reference_path = ?")
        cursor.execute(query, (reference_path,))
        return [dict(zip(['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_reference_location(cursor: sqlite3.Cursor, reference_location: str) -> List[Dict[str, Any]]:
        """Get rows by reference_location."""
        query = build_query('github_step_references', ['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], where="reference_location = ?")
        cursor.execute(query, (reference_location,))
        return [dict(zip(['id', 'step_id', 'reference_location', 'reference_type', 'reference_path'], row)) for row in cursor.fetchall()]


class GithubStepsTable:
    """Accessor class for github_steps table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from github_steps."""
        query = build_query('github_steps', ['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'])
        cursor.execute(query)
        return [dict(zip(['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_job_id(cursor: sqlite3.Cursor, job_id: str) -> List[Dict[str, Any]]:
        """Get rows by job_id."""
        query = build_query('github_steps', ['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], where="job_id = ?")
        cursor.execute(query, (job_id,))
        return [dict(zip(['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_uses_action(cursor: sqlite3.Cursor, uses_action: str) -> List[Dict[str, Any]]:
        """Get rows by uses_action."""
        query = build_query('github_steps', ['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], where="uses_action = ?")
        cursor.execute(query, (uses_action,))
        return [dict(zip(['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_uses_version(cursor: sqlite3.Cursor, uses_version: str) -> List[Dict[str, Any]]:
        """Get rows by uses_version."""
        query = build_query('github_steps', ['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], where="uses_version = ?")
        cursor.execute(query, (uses_version,))
        return [dict(zip(['step_id', 'job_id', 'sequence_order', 'step_name', 'uses_action', 'uses_version', 'run_script', 'shell', 'env', 'with_args', 'if_condition', 'timeout_minutes', 'continue_on_error'], row)) for row in cursor.fetchall()]


class GithubWorkflowsTable:
    """Accessor class for github_workflows table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from github_workflows."""
        query = build_query('github_workflows', ['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'])
        cursor.execute(query)
        return [dict(zip(['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_workflow_path(cursor: sqlite3.Cursor, workflow_path: str) -> List[Dict[str, Any]]:
        """Get rows by workflow_path."""
        query = build_query('github_workflows', ['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'], where="workflow_path = ?")
        cursor.execute(query, (workflow_path,))
        return [dict(zip(['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_workflow_name(cursor: sqlite3.Cursor, workflow_name: str) -> List[Dict[str, Any]]:
        """Get rows by workflow_name."""
        query = build_query('github_workflows', ['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'], where="workflow_name = ?")
        cursor.execute(query, (workflow_name,))
        return [dict(zip(['workflow_path', 'workflow_name', 'on_triggers', 'permissions', 'concurrency', 'env'], row)) for row in cursor.fetchall()]


class GraphqlExecutionEdgesTable:
    """Accessor class for graphql_execution_edges table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from graphql_execution_edges."""
        query = build_query('graphql_execution_edges', ['from_field_id', 'to_symbol_id', 'edge_kind'])
        cursor.execute(query)
        return [dict(zip(['from_field_id', 'to_symbol_id', 'edge_kind'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_from_field_id(cursor: sqlite3.Cursor, from_field_id: int) -> List[Dict[str, Any]]:
        """Get rows by from_field_id."""
        query = build_query('graphql_execution_edges', ['from_field_id', 'to_symbol_id', 'edge_kind'], where="from_field_id = ?")
        cursor.execute(query, (from_field_id,))
        return [dict(zip(['from_field_id', 'to_symbol_id', 'edge_kind'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_to_symbol_id(cursor: sqlite3.Cursor, to_symbol_id: int) -> List[Dict[str, Any]]:
        """Get rows by to_symbol_id."""
        query = build_query('graphql_execution_edges', ['from_field_id', 'to_symbol_id', 'edge_kind'], where="to_symbol_id = ?")
        cursor.execute(query, (to_symbol_id,))
        return [dict(zip(['from_field_id', 'to_symbol_id', 'edge_kind'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_edge_kind(cursor: sqlite3.Cursor, edge_kind: str) -> List[Dict[str, Any]]:
        """Get rows by edge_kind."""
        query = build_query('graphql_execution_edges', ['from_field_id', 'to_symbol_id', 'edge_kind'], where="edge_kind = ?")
        cursor.execute(query, (edge_kind,))
        return [dict(zip(['from_field_id', 'to_symbol_id', 'edge_kind'], row)) for row in cursor.fetchall()]


class GraphqlFieldArgsTable:
    """Accessor class for graphql_field_args table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from graphql_field_args."""
        query = build_query('graphql_field_args', ['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable', 'directives_json'])
        cursor.execute(query)
        return [dict(zip(['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable', 'directives_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_id(cursor: sqlite3.Cursor, field_id: int) -> List[Dict[str, Any]]:
        """Get rows by field_id."""
        query = build_query('graphql_field_args', ['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable', 'directives_json'], where="field_id = ?")
        cursor.execute(query, (field_id,))
        return [dict(zip(['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable', 'directives_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_arg_type(cursor: sqlite3.Cursor, arg_type: str) -> List[Dict[str, Any]]:
        """Get rows by arg_type."""
        query = build_query('graphql_field_args', ['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable', 'directives_json'], where="arg_type = ?")
        cursor.execute(query, (arg_type,))
        return [dict(zip(['field_id', 'arg_name', 'arg_type', 'has_default', 'default_value', 'is_nullable', 'directives_json'], row)) for row in cursor.fetchall()]


class GraphqlFieldsTable:
    """Accessor class for graphql_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from graphql_fields."""
        query = build_query('graphql_fields', ['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'directives_json', 'line', 'column'])
        cursor.execute(query)
        return [dict(zip(['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'directives_json', 'line', 'column'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type_id(cursor: sqlite3.Cursor, type_id: int) -> List[Dict[str, Any]]:
        """Get rows by type_id."""
        query = build_query('graphql_fields', ['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'directives_json', 'line', 'column'], where="type_id = ?")
        cursor.execute(query, (type_id,))
        return [dict(zip(['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'directives_json', 'line', 'column'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_name(cursor: sqlite3.Cursor, field_name: str) -> List[Dict[str, Any]]:
        """Get rows by field_name."""
        query = build_query('graphql_fields', ['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'directives_json', 'line', 'column'], where="field_name = ?")
        cursor.execute(query, (field_name,))
        return [dict(zip(['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'directives_json', 'line', 'column'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_return_type(cursor: sqlite3.Cursor, return_type: str) -> List[Dict[str, Any]]:
        """Get rows by return_type."""
        query = build_query('graphql_fields', ['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'directives_json', 'line', 'column'], where="return_type = ?")
        cursor.execute(query, (return_type,))
        return [dict(zip(['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'directives_json', 'line', 'column'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_list(cursor: sqlite3.Cursor, is_list: bool) -> List[Dict[str, Any]]:
        """Get rows by is_list."""
        query = build_query('graphql_fields', ['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'directives_json', 'line', 'column'], where="is_list = ?")
        cursor.execute(query, (is_list,))
        return [dict(zip(['field_id', 'type_id', 'field_name', 'return_type', 'is_list', 'is_nullable', 'directives_json', 'line', 'column'], row)) for row in cursor.fetchall()]


class GraphqlFindingsCacheTable:
    """Accessor class for graphql_findings_cache table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from graphql_findings_cache."""
        query = build_query('graphql_findings_cache', ['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'details_json', 'provenance'])
        cursor.execute(query)
        return [dict(zip(['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'details_json', 'provenance'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_id(cursor: sqlite3.Cursor, field_id: int) -> List[Dict[str, Any]]:
        """Get rows by field_id."""
        query = build_query('graphql_findings_cache', ['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'details_json', 'provenance'], where="field_id = ?")
        cursor.execute(query, (field_id,))
        return [dict(zip(['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'details_json', 'provenance'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resolver_symbol_id(cursor: sqlite3.Cursor, resolver_symbol_id: int) -> List[Dict[str, Any]]:
        """Get rows by resolver_symbol_id."""
        query = build_query('graphql_findings_cache', ['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'details_json', 'provenance'], where="resolver_symbol_id = ?")
        cursor.execute(query, (resolver_symbol_id,))
        return [dict(zip(['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'details_json', 'provenance'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_rule(cursor: sqlite3.Cursor, rule: str) -> List[Dict[str, Any]]:
        """Get rows by rule."""
        query = build_query('graphql_findings_cache', ['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'details_json', 'provenance'], where="rule = ?")
        cursor.execute(query, (rule,))
        return [dict(zip(['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'details_json', 'provenance'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_severity(cursor: sqlite3.Cursor, severity: str) -> List[Dict[str, Any]]:
        """Get rows by severity."""
        query = build_query('graphql_findings_cache', ['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'details_json', 'provenance'], where="severity = ?")
        cursor.execute(query, (severity,))
        return [dict(zip(['finding_id', 'field_id', 'resolver_symbol_id', 'rule', 'severity', 'details_json', 'provenance'], row)) for row in cursor.fetchall()]


class GraphqlResolverMappingsTable:
    """Accessor class for graphql_resolver_mappings table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from graphql_resolver_mappings."""
        query = build_query('graphql_resolver_mappings', ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'])
        cursor.execute(query)
        return [dict(zip(['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_id(cursor: sqlite3.Cursor, field_id: int) -> List[Dict[str, Any]]:
        """Get rows by field_id."""
        query = build_query('graphql_resolver_mappings', ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], where="field_id = ?")
        cursor.execute(query, (field_id,))
        return [dict(zip(['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resolver_symbol_id(cursor: sqlite3.Cursor, resolver_symbol_id: int) -> List[Dict[str, Any]]:
        """Get rows by resolver_symbol_id."""
        query = build_query('graphql_resolver_mappings', ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], where="resolver_symbol_id = ?")
        cursor.execute(query, (resolver_symbol_id,))
        return [dict(zip(['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resolver_path(cursor: sqlite3.Cursor, resolver_path: str) -> List[Dict[str, Any]]:
        """Get rows by resolver_path."""
        query = build_query('graphql_resolver_mappings', ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], where="resolver_path = ?")
        cursor.execute(query, (resolver_path,))
        return [dict(zip(['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_binding_style(cursor: sqlite3.Cursor, binding_style: str) -> List[Dict[str, Any]]:
        """Get rows by binding_style."""
        query = build_query('graphql_resolver_mappings', ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], where="binding_style = ?")
        cursor.execute(query, (binding_style,))
        return [dict(zip(['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line', 'resolver_language', 'resolver_export', 'binding_style'], row)) for row in cursor.fetchall()]


class GraphqlResolverParamsTable:
    """Accessor class for graphql_resolver_params table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from graphql_resolver_params."""
        query = build_query('graphql_resolver_params', ['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'])
        cursor.execute(query)
        return [dict(zip(['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resolver_symbol_id(cursor: sqlite3.Cursor, resolver_symbol_id: int) -> List[Dict[str, Any]]:
        """Get rows by resolver_symbol_id."""
        query = build_query('graphql_resolver_params', ['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], where="resolver_symbol_id = ?")
        cursor.execute(query, (resolver_symbol_id,))
        return [dict(zip(['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_arg_name(cursor: sqlite3.Cursor, arg_name: str) -> List[Dict[str, Any]]:
        """Get rows by arg_name."""
        query = build_query('graphql_resolver_params', ['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], where="arg_name = ?")
        cursor.execute(query, (arg_name,))
        return [dict(zip(['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_param_name(cursor: sqlite3.Cursor, param_name: str) -> List[Dict[str, Any]]:
        """Get rows by param_name."""
        query = build_query('graphql_resolver_params', ['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], where="param_name = ?")
        cursor.execute(query, (param_name,))
        return [dict(zip(['resolver_symbol_id', 'arg_name', 'param_name', 'param_index', 'is_kwargs', 'is_list_input'], row)) for row in cursor.fetchall()]


class GraphqlSchemasTable:
    """Accessor class for graphql_schemas table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from graphql_schemas."""
        query = build_query('graphql_schemas', ['file_path', 'schema_hash', 'language', 'last_modified'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'schema_hash', 'language', 'last_modified'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_schema_hash(cursor: sqlite3.Cursor, schema_hash: str) -> List[Dict[str, Any]]:
        """Get rows by schema_hash."""
        query = build_query('graphql_schemas', ['file_path', 'schema_hash', 'language', 'last_modified'], where="schema_hash = ?")
        cursor.execute(query, (schema_hash,))
        return [dict(zip(['file_path', 'schema_hash', 'language', 'last_modified'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_language(cursor: sqlite3.Cursor, language: str) -> List[Dict[str, Any]]:
        """Get rows by language."""
        query = build_query('graphql_schemas', ['file_path', 'schema_hash', 'language', 'last_modified'], where="language = ?")
        cursor.execute(query, (language,))
        return [dict(zip(['file_path', 'schema_hash', 'language', 'last_modified'], row)) for row in cursor.fetchall()]


class GraphqlTypesTable:
    """Accessor class for graphql_types table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from graphql_types."""
        query = build_query('graphql_types', ['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'])
        cursor.execute(query)
        return [dict(zip(['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_schema_path(cursor: sqlite3.Cursor, schema_path: str) -> List[Dict[str, Any]]:
        """Get rows by schema_path."""
        query = build_query('graphql_types', ['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], where="schema_path = ?")
        cursor.execute(query, (schema_path,))
        return [dict(zip(['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type_name(cursor: sqlite3.Cursor, type_name: str) -> List[Dict[str, Any]]:
        """Get rows by type_name."""
        query = build_query('graphql_types', ['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], where="type_name = ?")
        cursor.execute(query, (type_name,))
        return [dict(zip(['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_kind(cursor: sqlite3.Cursor, kind: str) -> List[Dict[str, Any]]:
        """Get rows by kind."""
        query = build_query('graphql_types', ['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], where="kind = ?")
        cursor.execute(query, (kind,))
        return [dict(zip(['type_id', 'schema_path', 'type_name', 'kind', 'implements', 'description', 'line'], row)) for row in cursor.fetchall()]


class ImportStyleNamesTable:
    """Accessor class for import_style_names table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from import_style_names."""
        query = build_query('import_style_names', ['id', 'import_file', 'import_line', 'imported_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'import_file', 'import_line', 'imported_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_imported_name(cursor: sqlite3.Cursor, imported_name: str) -> List[Dict[str, Any]]:
        """Get rows by imported_name."""
        query = build_query('import_style_names', ['id', 'import_file', 'import_line', 'imported_name'], where="imported_name = ?")
        cursor.execute(query, (imported_name,))
        return [dict(zip(['id', 'import_file', 'import_line', 'imported_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_import_file(cursor: sqlite3.Cursor, import_file: str) -> List[Dict[str, Any]]:
        """Get rows by import_file."""
        query = build_query('import_style_names', ['id', 'import_file', 'import_line', 'imported_name'], where="import_file = ?")
        cursor.execute(query, (import_file,))
        return [dict(zip(['id', 'import_file', 'import_line', 'imported_name'], row)) for row in cursor.fetchall()]


class ImportStylesTable:
    """Accessor class for import_styles table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from import_styles."""
        query = build_query('import_styles', ['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('import_styles', ['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_package(cursor: sqlite3.Cursor, package: str) -> List[Dict[str, Any]]:
        """Get rows by package."""
        query = build_query('import_styles', ['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement'], where="package = ?")
        cursor.execute(query, (package,))
        return [dict(zip(['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_import_style(cursor: sqlite3.Cursor, import_style: str) -> List[Dict[str, Any]]:
        """Get rows by import_style."""
        query = build_query('import_styles', ['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement'], where="import_style = ?")
        cursor.execute(query, (import_style,))
        return [dict(zip(['file', 'line', 'package', 'import_style', 'alias_name', 'full_statement'], row)) for row in cursor.fetchall()]


class JwtPatternsTable:
    """Accessor class for jwt_patterns table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from jwt_patterns."""
        query = build_query('jwt_patterns', ['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('jwt_patterns', ['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_pattern_type(cursor: sqlite3.Cursor, pattern_type: str) -> List[Dict[str, Any]]:
        """Get rows by pattern_type."""
        query = build_query('jwt_patterns', ['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], where="pattern_type = ?")
        cursor.execute(query, (pattern_type,))
        return [dict(zip(['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_secret_source(cursor: sqlite3.Cursor, secret_source: str) -> List[Dict[str, Any]]:
        """Get rows by secret_source."""
        query = build_query('jwt_patterns', ['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], where="secret_source = ?")
        cursor.execute(query, (secret_source,))
        return [dict(zip(['file_path', 'line_number', 'pattern_type', 'pattern_text', 'secret_source', 'algorithm'], row)) for row in cursor.fetchall()]


class LockAnalysisTable:
    """Accessor class for lock_analysis table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from lock_analysis."""
        query = build_query('lock_analysis', ['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('lock_analysis', ['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_lock_type(cursor: sqlite3.Cursor, lock_type: str) -> List[Dict[str, Any]]:
        """Get rows by lock_type."""
        query = build_query('lock_analysis', ['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'], where="lock_type = ?")
        cursor.execute(query, (lock_type,))
        return [dict(zip(['file_path', 'lock_type', 'package_manager_version', 'total_packages', 'duplicate_packages', 'lock_file_version'], row)) for row in cursor.fetchall()]


class NginxConfigsTable:
    """Accessor class for nginx_configs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from nginx_configs."""
        query = build_query('nginx_configs', ['file_path', 'block_type', 'block_context', 'directives', 'level'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'block_type', 'block_context', 'directives', 'level'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('nginx_configs', ['file_path', 'block_type', 'block_context', 'directives', 'level'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'block_type', 'block_context', 'directives', 'level'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_block_type(cursor: sqlite3.Cursor, block_type: str) -> List[Dict[str, Any]]:
        """Get rows by block_type."""
        query = build_query('nginx_configs', ['file_path', 'block_type', 'block_context', 'directives', 'level'], where="block_type = ?")
        cursor.execute(query, (block_type,))
        return [dict(zip(['file_path', 'block_type', 'block_context', 'directives', 'level'], row)) for row in cursor.fetchall()]


class ObjectLiteralsTable:
    """Accessor class for object_literals table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from object_literals."""
        query = build_query('object_literals', ['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'])
        cursor.execute(query)
        return [dict(zip(['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('object_literals', ['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_variable_name(cursor: sqlite3.Cursor, variable_name: str) -> List[Dict[str, Any]]:
        """Get rows by variable_name."""
        query = build_query('object_literals', ['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], where="variable_name = ?")
        cursor.execute(query, (variable_name,))
        return [dict(zip(['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_value(cursor: sqlite3.Cursor, property_value: str) -> List[Dict[str, Any]]:
        """Get rows by property_value."""
        query = build_query('object_literals', ['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], where="property_value = ?")
        cursor.execute(query, (property_value,))
        return [dict(zip(['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_property_type(cursor: sqlite3.Cursor, property_type: str) -> List[Dict[str, Any]]:
        """Get rows by property_type."""
        query = build_query('object_literals', ['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], where="property_type = ?")
        cursor.execute(query, (property_type,))
        return [dict(zip(['id', 'file', 'line', 'variable_name', 'property_name', 'property_value', 'property_type', 'nested_level', 'in_function'], row)) for row in cursor.fetchall()]


class OrmQueriesTable:
    """Accessor class for orm_queries table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from orm_queries."""
        query = build_query('orm_queries', ['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('orm_queries', ['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_query_type(cursor: sqlite3.Cursor, query_type: str) -> List[Dict[str, Any]]:
        """Get rows by query_type."""
        query = build_query('orm_queries', ['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'], where="query_type = ?")
        cursor.execute(query, (query_type,))
        return [dict(zip(['file', 'line', 'query_type', 'includes', 'has_limit', 'has_transaction'], row)) for row in cursor.fetchall()]


class OrmRelationshipsTable:
    """Accessor class for orm_relationships table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from orm_relationships."""
        query = build_query('orm_relationships', ['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('orm_relationships', ['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_source_model(cursor: sqlite3.Cursor, source_model: str) -> List[Dict[str, Any]]:
        """Get rows by source_model."""
        query = build_query('orm_relationships', ['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], where="source_model = ?")
        cursor.execute(query, (source_model,))
        return [dict(zip(['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_model(cursor: sqlite3.Cursor, target_model: str) -> List[Dict[str, Any]]:
        """Get rows by target_model."""
        query = build_query('orm_relationships', ['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], where="target_model = ?")
        cursor.execute(query, (target_model,))
        return [dict(zip(['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_relationship_type(cursor: sqlite3.Cursor, relationship_type: str) -> List[Dict[str, Any]]:
        """Get rows by relationship_type."""
        query = build_query('orm_relationships', ['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], where="relationship_type = ?")
        cursor.execute(query, (relationship_type,))
        return [dict(zip(['file', 'line', 'source_model', 'target_model', 'relationship_type', 'foreign_key', 'cascade_delete', 'as_name'], row)) for row in cursor.fetchall()]


class PackageConfigsTable:
    """Accessor class for package_configs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from package_configs."""
        query = build_query('package_configs', ['file_path', 'package_name', 'version', 'dependencies', 'dev_dependencies', 'peer_dependencies', 'scripts', 'engines', 'workspaces', 'private'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'package_name', 'version', 'dependencies', 'dev_dependencies', 'peer_dependencies', 'scripts', 'engines', 'workspaces', 'private'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('package_configs', ['file_path', 'package_name', 'version', 'dependencies', 'dev_dependencies', 'peer_dependencies', 'scripts', 'engines', 'workspaces', 'private'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'package_name', 'version', 'dependencies', 'dev_dependencies', 'peer_dependencies', 'scripts', 'engines', 'workspaces', 'private'], row)) for row in cursor.fetchall()]


class PlanSpecsTable:
    """Accessor class for plan_specs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from plan_specs."""
        query = build_query('plan_specs', ['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'])
        cursor.execute(query)
        return [dict(zip(['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_plan_id(cursor: sqlite3.Cursor, plan_id: int) -> List[Dict[str, Any]]:
        """Get rows by plan_id."""
        query = build_query('plan_specs', ['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'], where="plan_id = ?")
        cursor.execute(query, (plan_id,))
        return [dict(zip(['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_spec_type(cursor: sqlite3.Cursor, spec_type: str) -> List[Dict[str, Any]]:
        """Get rows by spec_type."""
        query = build_query('plan_specs', ['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'], where="spec_type = ?")
        cursor.execute(query, (spec_type,))
        return [dict(zip(['id', 'plan_id', 'spec_yaml', 'spec_type', 'created_at'], row)) for row in cursor.fetchall()]


class PlanTasksTable:
    """Accessor class for plan_tasks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from plan_tasks."""
        query = build_query('plan_tasks', ['id', 'plan_id', 'task_number', 'title', 'description', 'status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'])
        cursor.execute(query)
        return [dict(zip(['id', 'plan_id', 'task_number', 'title', 'description', 'status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_plan_id(cursor: sqlite3.Cursor, plan_id: int) -> List[Dict[str, Any]]:
        """Get rows by plan_id."""
        query = build_query('plan_tasks', ['id', 'plan_id', 'task_number', 'title', 'description', 'status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], where="plan_id = ?")
        cursor.execute(query, (plan_id,))
        return [dict(zip(['id', 'plan_id', 'task_number', 'title', 'description', 'status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_status(cursor: sqlite3.Cursor, status: str) -> List[Dict[str, Any]]:
        """Get rows by status."""
        query = build_query('plan_tasks', ['id', 'plan_id', 'task_number', 'title', 'description', 'status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], where="status = ?")
        cursor.execute(query, (status,))
        return [dict(zip(['id', 'plan_id', 'task_number', 'title', 'description', 'status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_spec_id(cursor: sqlite3.Cursor, spec_id: int) -> List[Dict[str, Any]]:
        """Get rows by spec_id."""
        query = build_query('plan_tasks', ['id', 'plan_id', 'task_number', 'title', 'description', 'status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], where="spec_id = ?")
        cursor.execute(query, (spec_id,))
        return [dict(zip(['id', 'plan_id', 'task_number', 'title', 'description', 'status', 'assigned_to', 'spec_id', 'created_at', 'completed_at'], row)) for row in cursor.fetchall()]


class PlansTable:
    """Accessor class for plans table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from plans."""
        query = build_query('plans', ['id', 'name', 'description', 'created_at', 'status', 'metadata_json'])
        cursor.execute(query)
        return [dict(zip(['id', 'name', 'description', 'created_at', 'status', 'metadata_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_status(cursor: sqlite3.Cursor, status: str) -> List[Dict[str, Any]]:
        """Get rows by status."""
        query = build_query('plans', ['id', 'name', 'description', 'created_at', 'status', 'metadata_json'], where="status = ?")
        cursor.execute(query, (status,))
        return [dict(zip(['id', 'name', 'description', 'created_at', 'status', 'metadata_json'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_created_at(cursor: sqlite3.Cursor, created_at: str) -> List[Dict[str, Any]]:
        """Get rows by created_at."""
        query = build_query('plans', ['id', 'name', 'description', 'created_at', 'status', 'metadata_json'], where="created_at = ?")
        cursor.execute(query, (created_at,))
        return [dict(zip(['id', 'name', 'description', 'created_at', 'status', 'metadata_json'], row)) for row in cursor.fetchall()]


class PrismaModelsTable:
    """Accessor class for prisma_models table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from prisma_models."""
        query = build_query('prisma_models', ['model_name', 'field_name', 'field_type', 'is_indexed', 'is_unique', 'is_relation'])
        cursor.execute(query)
        return [dict(zip(['model_name', 'field_name', 'field_type', 'is_indexed', 'is_unique', 'is_relation'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_indexed(cursor: sqlite3.Cursor, is_indexed: bool) -> List[Dict[str, Any]]:
        """Get rows by is_indexed."""
        query = build_query('prisma_models', ['model_name', 'field_name', 'field_type', 'is_indexed', 'is_unique', 'is_relation'], where="is_indexed = ?")
        cursor.execute(query, (is_indexed,))
        return [dict(zip(['model_name', 'field_name', 'field_type', 'is_indexed', 'is_unique', 'is_relation'], row)) for row in cursor.fetchall()]


class PythonAsyncFunctionsTable:
    """Accessor class for python_async_functions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_async_functions."""
        query = build_query('python_async_functions', ['file', 'line', 'function_name', 'has_await', 'await_count', 'has_async_with', 'has_async_for'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'function_name', 'has_await', 'await_count', 'has_async_with', 'has_async_for'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_async_functions', ['file', 'line', 'function_name', 'has_await', 'await_count', 'has_async_with', 'has_async_for'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'function_name', 'has_await', 'await_count', 'has_async_with', 'has_async_for'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> List[Dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('python_async_functions', ['file', 'line', 'function_name', 'has_await', 'await_count', 'has_async_with', 'has_async_for'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['file', 'line', 'function_name', 'has_await', 'await_count', 'has_async_with', 'has_async_for'], row)) for row in cursor.fetchall()]


class PythonAsyncGeneratorsTable:
    """Accessor class for python_async_generators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_async_generators."""
        query = build_query('python_async_generators', ['file', 'line', 'generator_type', 'target_vars', 'iterable_expr', 'function_name'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'generator_type', 'target_vars', 'iterable_expr', 'function_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_async_generators', ['file', 'line', 'generator_type', 'target_vars', 'iterable_expr', 'function_name'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'generator_type', 'target_vars', 'iterable_expr', 'function_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_generator_type(cursor: sqlite3.Cursor, generator_type: str) -> List[Dict[str, Any]]:
        """Get rows by generator_type."""
        query = build_query('python_async_generators', ['file', 'line', 'generator_type', 'target_vars', 'iterable_expr', 'function_name'], where="generator_type = ?")
        cursor.execute(query, (generator_type,))
        return [dict(zip(['file', 'line', 'generator_type', 'target_vars', 'iterable_expr', 'function_name'], row)) for row in cursor.fetchall()]


class PythonAwaitExpressionsTable:
    """Accessor class for python_await_expressions table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_await_expressions."""
        query = build_query('python_await_expressions', ['file', 'line', 'await_expr', 'containing_function'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'await_expr', 'containing_function'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_await_expressions', ['file', 'line', 'await_expr', 'containing_function'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'await_expr', 'containing_function'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_containing_function(cursor: sqlite3.Cursor, containing_function: str) -> List[Dict[str, Any]]:
        """Get rows by containing_function."""
        query = build_query('python_await_expressions', ['file', 'line', 'await_expr', 'containing_function'], where="containing_function = ?")
        cursor.execute(query, (containing_function,))
        return [dict(zip(['file', 'line', 'await_expr', 'containing_function'], row)) for row in cursor.fetchall()]


class PythonBlueprintsTable:
    """Accessor class for python_blueprints table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_blueprints."""
        query = build_query('python_blueprints', ['file', 'line', 'blueprint_name', 'url_prefix', 'subdomain'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'blueprint_name', 'url_prefix', 'subdomain'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_blueprints', ['file', 'line', 'blueprint_name', 'url_prefix', 'subdomain'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'blueprint_name', 'url_prefix', 'subdomain'], row)) for row in cursor.fetchall()]


class PythonCeleryBeatSchedulesTable:
    """Accessor class for python_celery_beat_schedules table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_celery_beat_schedules."""
        query = build_query('python_celery_beat_schedules', ['file', 'line', 'schedule_name', 'task_name', 'schedule_type', 'schedule_expression', 'args', 'kwargs'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'schedule_name', 'task_name', 'schedule_type', 'schedule_expression', 'args', 'kwargs'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_celery_beat_schedules', ['file', 'line', 'schedule_name', 'task_name', 'schedule_type', 'schedule_expression', 'args', 'kwargs'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'schedule_name', 'task_name', 'schedule_type', 'schedule_expression', 'args', 'kwargs'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_task_name(cursor: sqlite3.Cursor, task_name: str) -> List[Dict[str, Any]]:
        """Get rows by task_name."""
        query = build_query('python_celery_beat_schedules', ['file', 'line', 'schedule_name', 'task_name', 'schedule_type', 'schedule_expression', 'args', 'kwargs'], where="task_name = ?")
        cursor.execute(query, (task_name,))
        return [dict(zip(['file', 'line', 'schedule_name', 'task_name', 'schedule_type', 'schedule_expression', 'args', 'kwargs'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_schedule_type(cursor: sqlite3.Cursor, schedule_type: str) -> List[Dict[str, Any]]:
        """Get rows by schedule_type."""
        query = build_query('python_celery_beat_schedules', ['file', 'line', 'schedule_name', 'task_name', 'schedule_type', 'schedule_expression', 'args', 'kwargs'], where="schedule_type = ?")
        cursor.execute(query, (schedule_type,))
        return [dict(zip(['file', 'line', 'schedule_name', 'task_name', 'schedule_type', 'schedule_expression', 'args', 'kwargs'], row)) for row in cursor.fetchall()]


class PythonCeleryTaskCallsTable:
    """Accessor class for python_celery_task_calls table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_celery_task_calls."""
        query = build_query('python_celery_task_calls', ['file', 'line', 'caller_function', 'task_name', 'invocation_type', 'arg_count', 'has_countdown', 'has_eta', 'queue_override'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'caller_function', 'task_name', 'invocation_type', 'arg_count', 'has_countdown', 'has_eta', 'queue_override'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_celery_task_calls', ['file', 'line', 'caller_function', 'task_name', 'invocation_type', 'arg_count', 'has_countdown', 'has_eta', 'queue_override'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'caller_function', 'task_name', 'invocation_type', 'arg_count', 'has_countdown', 'has_eta', 'queue_override'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_task_name(cursor: sqlite3.Cursor, task_name: str) -> List[Dict[str, Any]]:
        """Get rows by task_name."""
        query = build_query('python_celery_task_calls', ['file', 'line', 'caller_function', 'task_name', 'invocation_type', 'arg_count', 'has_countdown', 'has_eta', 'queue_override'], where="task_name = ?")
        cursor.execute(query, (task_name,))
        return [dict(zip(['file', 'line', 'caller_function', 'task_name', 'invocation_type', 'arg_count', 'has_countdown', 'has_eta', 'queue_override'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_invocation_type(cursor: sqlite3.Cursor, invocation_type: str) -> List[Dict[str, Any]]:
        """Get rows by invocation_type."""
        query = build_query('python_celery_task_calls', ['file', 'line', 'caller_function', 'task_name', 'invocation_type', 'arg_count', 'has_countdown', 'has_eta', 'queue_override'], where="invocation_type = ?")
        cursor.execute(query, (invocation_type,))
        return [dict(zip(['file', 'line', 'caller_function', 'task_name', 'invocation_type', 'arg_count', 'has_countdown', 'has_eta', 'queue_override'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_caller_function(cursor: sqlite3.Cursor, caller_function: str) -> List[Dict[str, Any]]:
        """Get rows by caller_function."""
        query = build_query('python_celery_task_calls', ['file', 'line', 'caller_function', 'task_name', 'invocation_type', 'arg_count', 'has_countdown', 'has_eta', 'queue_override'], where="caller_function = ?")
        cursor.execute(query, (caller_function,))
        return [dict(zip(['file', 'line', 'caller_function', 'task_name', 'invocation_type', 'arg_count', 'has_countdown', 'has_eta', 'queue_override'], row)) for row in cursor.fetchall()]


class PythonCeleryTasksTable:
    """Accessor class for python_celery_tasks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_celery_tasks."""
        query = build_query('python_celery_tasks', ['file', 'line', 'task_name', 'decorator_name', 'arg_count', 'bind', 'serializer', 'max_retries', 'rate_limit', 'time_limit', 'queue'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'task_name', 'decorator_name', 'arg_count', 'bind', 'serializer', 'max_retries', 'rate_limit', 'time_limit', 'queue'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_celery_tasks', ['file', 'line', 'task_name', 'decorator_name', 'arg_count', 'bind', 'serializer', 'max_retries', 'rate_limit', 'time_limit', 'queue'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'task_name', 'decorator_name', 'arg_count', 'bind', 'serializer', 'max_retries', 'rate_limit', 'time_limit', 'queue'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_task_name(cursor: sqlite3.Cursor, task_name: str) -> List[Dict[str, Any]]:
        """Get rows by task_name."""
        query = build_query('python_celery_tasks', ['file', 'line', 'task_name', 'decorator_name', 'arg_count', 'bind', 'serializer', 'max_retries', 'rate_limit', 'time_limit', 'queue'], where="task_name = ?")
        cursor.execute(query, (task_name,))
        return [dict(zip(['file', 'line', 'task_name', 'decorator_name', 'arg_count', 'bind', 'serializer', 'max_retries', 'rate_limit', 'time_limit', 'queue'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_serializer(cursor: sqlite3.Cursor, serializer: str) -> List[Dict[str, Any]]:
        """Get rows by serializer."""
        query = build_query('python_celery_tasks', ['file', 'line', 'task_name', 'decorator_name', 'arg_count', 'bind', 'serializer', 'max_retries', 'rate_limit', 'time_limit', 'queue'], where="serializer = ?")
        cursor.execute(query, (serializer,))
        return [dict(zip(['file', 'line', 'task_name', 'decorator_name', 'arg_count', 'bind', 'serializer', 'max_retries', 'rate_limit', 'time_limit', 'queue'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_queue(cursor: sqlite3.Cursor, queue: str) -> List[Dict[str, Any]]:
        """Get rows by queue."""
        query = build_query('python_celery_tasks', ['file', 'line', 'task_name', 'decorator_name', 'arg_count', 'bind', 'serializer', 'max_retries', 'rate_limit', 'time_limit', 'queue'], where="queue = ?")
        cursor.execute(query, (queue,))
        return [dict(zip(['file', 'line', 'task_name', 'decorator_name', 'arg_count', 'bind', 'serializer', 'max_retries', 'rate_limit', 'time_limit', 'queue'], row)) for row in cursor.fetchall()]


class PythonContextManagersTable:
    """Accessor class for python_context_managers table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_context_managers."""
        query = build_query('python_context_managers', ['file', 'line', 'context_type', 'context_expr', 'as_name', 'is_async', 'is_custom'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'context_type', 'context_expr', 'as_name', 'is_async', 'is_custom'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_context_managers', ['file', 'line', 'context_type', 'context_expr', 'as_name', 'is_async', 'is_custom'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'context_type', 'context_expr', 'as_name', 'is_async', 'is_custom'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_context_type(cursor: sqlite3.Cursor, context_type: str) -> List[Dict[str, Any]]:
        """Get rows by context_type."""
        query = build_query('python_context_managers', ['file', 'line', 'context_type', 'context_expr', 'as_name', 'is_async', 'is_custom'], where="context_type = ?")
        cursor.execute(query, (context_type,))
        return [dict(zip(['file', 'line', 'context_type', 'context_expr', 'as_name', 'is_async', 'is_custom'], row)) for row in cursor.fetchall()]


class PythonDecoratorsTable:
    """Accessor class for python_decorators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_decorators."""
        query = build_query('python_decorators', ['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_decorators', ['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_decorator_type(cursor: sqlite3.Cursor, decorator_type: str) -> List[Dict[str, Any]]:
        """Get rows by decorator_type."""
        query = build_query('python_decorators', ['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], where="decorator_type = ?")
        cursor.execute(query, (decorator_type,))
        return [dict(zip(['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_name(cursor: sqlite3.Cursor, target_name: str) -> List[Dict[str, Any]]:
        """Get rows by target_name."""
        query = build_query('python_decorators', ['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], where="target_name = ?")
        cursor.execute(query, (target_name,))
        return [dict(zip(['file', 'line', 'decorator_name', 'decorator_type', 'target_type', 'target_name', 'is_async'], row)) for row in cursor.fetchall()]


class PythonDjangoAdminTable:
    """Accessor class for python_django_admin table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_django_admin."""
        query = build_query('python_django_admin', ['file', 'line', 'admin_class_name', 'model_name', 'list_display', 'list_filter', 'search_fields', 'readonly_fields', 'has_custom_actions'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'admin_class_name', 'model_name', 'list_display', 'list_filter', 'search_fields', 'readonly_fields', 'has_custom_actions'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_django_admin', ['file', 'line', 'admin_class_name', 'model_name', 'list_display', 'list_filter', 'search_fields', 'readonly_fields', 'has_custom_actions'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'admin_class_name', 'model_name', 'list_display', 'list_filter', 'search_fields', 'readonly_fields', 'has_custom_actions'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> List[Dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('python_django_admin', ['file', 'line', 'admin_class_name', 'model_name', 'list_display', 'list_filter', 'search_fields', 'readonly_fields', 'has_custom_actions'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'admin_class_name', 'model_name', 'list_display', 'list_filter', 'search_fields', 'readonly_fields', 'has_custom_actions'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_custom_actions(cursor: sqlite3.Cursor, has_custom_actions: bool) -> List[Dict[str, Any]]:
        """Get rows by has_custom_actions."""
        query = build_query('python_django_admin', ['file', 'line', 'admin_class_name', 'model_name', 'list_display', 'list_filter', 'search_fields', 'readonly_fields', 'has_custom_actions'], where="has_custom_actions = ?")
        cursor.execute(query, (has_custom_actions,))
        return [dict(zip(['file', 'line', 'admin_class_name', 'model_name', 'list_display', 'list_filter', 'search_fields', 'readonly_fields', 'has_custom_actions'], row)) for row in cursor.fetchall()]


class PythonDjangoFormFieldsTable:
    """Accessor class for python_django_form_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_django_form_fields."""
        query = build_query('python_django_form_fields', ['file', 'line', 'form_class_name', 'field_name', 'field_type', 'required', 'max_length', 'has_custom_validator'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'form_class_name', 'field_name', 'field_type', 'required', 'max_length', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_django_form_fields', ['file', 'line', 'form_class_name', 'field_name', 'field_type', 'required', 'max_length', 'has_custom_validator'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'form_class_name', 'field_name', 'field_type', 'required', 'max_length', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_form_class_name(cursor: sqlite3.Cursor, form_class_name: str) -> List[Dict[str, Any]]:
        """Get rows by form_class_name."""
        query = build_query('python_django_form_fields', ['file', 'line', 'form_class_name', 'field_name', 'field_type', 'required', 'max_length', 'has_custom_validator'], where="form_class_name = ?")
        cursor.execute(query, (form_class_name,))
        return [dict(zip(['file', 'line', 'form_class_name', 'field_name', 'field_type', 'required', 'max_length', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_field_type(cursor: sqlite3.Cursor, field_type: str) -> List[Dict[str, Any]]:
        """Get rows by field_type."""
        query = build_query('python_django_form_fields', ['file', 'line', 'form_class_name', 'field_name', 'field_type', 'required', 'max_length', 'has_custom_validator'], where="field_type = ?")
        cursor.execute(query, (field_type,))
        return [dict(zip(['file', 'line', 'form_class_name', 'field_name', 'field_type', 'required', 'max_length', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_max_length(cursor: sqlite3.Cursor, max_length: int) -> List[Dict[str, Any]]:
        """Get rows by max_length."""
        query = build_query('python_django_form_fields', ['file', 'line', 'form_class_name', 'field_name', 'field_type', 'required', 'max_length', 'has_custom_validator'], where="max_length = ?")
        cursor.execute(query, (max_length,))
        return [dict(zip(['file', 'line', 'form_class_name', 'field_name', 'field_type', 'required', 'max_length', 'has_custom_validator'], row)) for row in cursor.fetchall()]


class PythonDjangoFormsTable:
    """Accessor class for python_django_forms table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_django_forms."""
        query = build_query('python_django_forms', ['file', 'line', 'form_class_name', 'is_model_form', 'model_name', 'field_count', 'has_custom_clean'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'form_class_name', 'is_model_form', 'model_name', 'field_count', 'has_custom_clean'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_django_forms', ['file', 'line', 'form_class_name', 'is_model_form', 'model_name', 'field_count', 'has_custom_clean'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'form_class_name', 'is_model_form', 'model_name', 'field_count', 'has_custom_clean'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_model_form(cursor: sqlite3.Cursor, is_model_form: bool) -> List[Dict[str, Any]]:
        """Get rows by is_model_form."""
        query = build_query('python_django_forms', ['file', 'line', 'form_class_name', 'is_model_form', 'model_name', 'field_count', 'has_custom_clean'], where="is_model_form = ?")
        cursor.execute(query, (is_model_form,))
        return [dict(zip(['file', 'line', 'form_class_name', 'is_model_form', 'model_name', 'field_count', 'has_custom_clean'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_custom_clean(cursor: sqlite3.Cursor, has_custom_clean: bool) -> List[Dict[str, Any]]:
        """Get rows by has_custom_clean."""
        query = build_query('python_django_forms', ['file', 'line', 'form_class_name', 'is_model_form', 'model_name', 'field_count', 'has_custom_clean'], where="has_custom_clean = ?")
        cursor.execute(query, (has_custom_clean,))
        return [dict(zip(['file', 'line', 'form_class_name', 'is_model_form', 'model_name', 'field_count', 'has_custom_clean'], row)) for row in cursor.fetchall()]


class PythonDjangoMiddlewareTable:
    """Accessor class for python_django_middleware table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_django_middleware."""
        query = build_query('python_django_middleware', ['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_django_middleware', ['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_process_request(cursor: sqlite3.Cursor, has_process_request: bool) -> List[Dict[str, Any]]:
        """Get rows by has_process_request."""
        query = build_query('python_django_middleware', ['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], where="has_process_request = ?")
        cursor.execute(query, (has_process_request,))
        return [dict(zip(['file', 'line', 'middleware_class_name', 'has_process_request', 'has_process_response', 'has_process_exception', 'has_process_view', 'has_process_template_response'], row)) for row in cursor.fetchall()]


class PythonDjangoViewsTable:
    """Accessor class for python_django_views table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_django_views."""
        query = build_query('python_django_views', ['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_django_views', ['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_view_type(cursor: sqlite3.Cursor, view_type: str) -> List[Dict[str, Any]]:
        """Get rows by view_type."""
        query = build_query('python_django_views', ['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], where="view_type = ?")
        cursor.execute(query, (view_type,))
        return [dict(zip(['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> List[Dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('python_django_views', ['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_permission_check(cursor: sqlite3.Cursor, has_permission_check: bool) -> List[Dict[str, Any]]:
        """Get rows by has_permission_check."""
        query = build_query('python_django_views', ['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], where="has_permission_check = ?")
        cursor.execute(query, (has_permission_check,))
        return [dict(zip(['file', 'line', 'view_class_name', 'view_type', 'base_view_class', 'model_name', 'template_name', 'has_permission_check', 'http_method_names', 'has_get_queryset_override'], row)) for row in cursor.fetchall()]


class PythonDrfSerializerFieldsTable:
    """Accessor class for python_drf_serializer_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_drf_serializer_fields."""
        query = build_query('python_drf_serializer_fields', ['file', 'line', 'serializer_class_name', 'field_name', 'field_type', 'read_only', 'write_only', 'required', 'allow_null', 'has_source', 'has_custom_validator'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'serializer_class_name', 'field_name', 'field_type', 'read_only', 'write_only', 'required', 'allow_null', 'has_source', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_drf_serializer_fields', ['file', 'line', 'serializer_class_name', 'field_name', 'field_type', 'read_only', 'write_only', 'required', 'allow_null', 'has_source', 'has_custom_validator'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'serializer_class_name', 'field_name', 'field_type', 'read_only', 'write_only', 'required', 'allow_null', 'has_source', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_serializer_class_name(cursor: sqlite3.Cursor, serializer_class_name: str) -> List[Dict[str, Any]]:
        """Get rows by serializer_class_name."""
        query = build_query('python_drf_serializer_fields', ['file', 'line', 'serializer_class_name', 'field_name', 'field_type', 'read_only', 'write_only', 'required', 'allow_null', 'has_source', 'has_custom_validator'], where="serializer_class_name = ?")
        cursor.execute(query, (serializer_class_name,))
        return [dict(zip(['file', 'line', 'serializer_class_name', 'field_name', 'field_type', 'read_only', 'write_only', 'required', 'allow_null', 'has_source', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_read_only(cursor: sqlite3.Cursor, read_only: bool) -> List[Dict[str, Any]]:
        """Get rows by read_only."""
        query = build_query('python_drf_serializer_fields', ['file', 'line', 'serializer_class_name', 'field_name', 'field_type', 'read_only', 'write_only', 'required', 'allow_null', 'has_source', 'has_custom_validator'], where="read_only = ?")
        cursor.execute(query, (read_only,))
        return [dict(zip(['file', 'line', 'serializer_class_name', 'field_name', 'field_type', 'read_only', 'write_only', 'required', 'allow_null', 'has_source', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_write_only(cursor: sqlite3.Cursor, write_only: bool) -> List[Dict[str, Any]]:
        """Get rows by write_only."""
        query = build_query('python_drf_serializer_fields', ['file', 'line', 'serializer_class_name', 'field_name', 'field_type', 'read_only', 'write_only', 'required', 'allow_null', 'has_source', 'has_custom_validator'], where="write_only = ?")
        cursor.execute(query, (write_only,))
        return [dict(zip(['file', 'line', 'serializer_class_name', 'field_name', 'field_type', 'read_only', 'write_only', 'required', 'allow_null', 'has_source', 'has_custom_validator'], row)) for row in cursor.fetchall()]


class PythonDrfSerializersTable:
    """Accessor class for python_drf_serializers table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_drf_serializers."""
        query = build_query('python_drf_serializers', ['file', 'line', 'serializer_class_name', 'field_count', 'is_model_serializer', 'has_meta_model', 'has_read_only_fields', 'has_custom_validators'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'serializer_class_name', 'field_count', 'is_model_serializer', 'has_meta_model', 'has_read_only_fields', 'has_custom_validators'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_drf_serializers', ['file', 'line', 'serializer_class_name', 'field_count', 'is_model_serializer', 'has_meta_model', 'has_read_only_fields', 'has_custom_validators'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'serializer_class_name', 'field_count', 'is_model_serializer', 'has_meta_model', 'has_read_only_fields', 'has_custom_validators'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_serializer_class_name(cursor: sqlite3.Cursor, serializer_class_name: str) -> List[Dict[str, Any]]:
        """Get rows by serializer_class_name."""
        query = build_query('python_drf_serializers', ['file', 'line', 'serializer_class_name', 'field_count', 'is_model_serializer', 'has_meta_model', 'has_read_only_fields', 'has_custom_validators'], where="serializer_class_name = ?")
        cursor.execute(query, (serializer_class_name,))
        return [dict(zip(['file', 'line', 'serializer_class_name', 'field_count', 'is_model_serializer', 'has_meta_model', 'has_read_only_fields', 'has_custom_validators'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_model_serializer(cursor: sqlite3.Cursor, is_model_serializer: bool) -> List[Dict[str, Any]]:
        """Get rows by is_model_serializer."""
        query = build_query('python_drf_serializers', ['file', 'line', 'serializer_class_name', 'field_count', 'is_model_serializer', 'has_meta_model', 'has_read_only_fields', 'has_custom_validators'], where="is_model_serializer = ?")
        cursor.execute(query, (is_model_serializer,))
        return [dict(zip(['file', 'line', 'serializer_class_name', 'field_count', 'is_model_serializer', 'has_meta_model', 'has_read_only_fields', 'has_custom_validators'], row)) for row in cursor.fetchall()]


class PythonGeneratorsTable:
    """Accessor class for python_generators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_generators."""
        query = build_query('python_generators', ['file', 'line', 'generator_type', 'name', 'yield_count', 'has_yield_from', 'has_send', 'is_infinite'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'generator_type', 'name', 'yield_count', 'has_yield_from', 'has_send', 'is_infinite'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_generators', ['file', 'line', 'generator_type', 'name', 'yield_count', 'has_yield_from', 'has_send', 'is_infinite'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'generator_type', 'name', 'yield_count', 'has_yield_from', 'has_send', 'is_infinite'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_generator_type(cursor: sqlite3.Cursor, generator_type: str) -> List[Dict[str, Any]]:
        """Get rows by generator_type."""
        query = build_query('python_generators', ['file', 'line', 'generator_type', 'name', 'yield_count', 'has_yield_from', 'has_send', 'is_infinite'], where="generator_type = ?")
        cursor.execute(query, (generator_type,))
        return [dict(zip(['file', 'line', 'generator_type', 'name', 'yield_count', 'has_yield_from', 'has_send', 'is_infinite'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_infinite(cursor: sqlite3.Cursor, is_infinite: bool) -> List[Dict[str, Any]]:
        """Get rows by is_infinite."""
        query = build_query('python_generators', ['file', 'line', 'generator_type', 'name', 'yield_count', 'has_yield_from', 'has_send', 'is_infinite'], where="is_infinite = ?")
        cursor.execute(query, (is_infinite,))
        return [dict(zip(['file', 'line', 'generator_type', 'name', 'yield_count', 'has_yield_from', 'has_send', 'is_infinite'], row)) for row in cursor.fetchall()]


class PythonGenericsTable:
    """Accessor class for python_generics table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_generics."""
        query = build_query('python_generics', ['file', 'line', 'class_name', 'type_params'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'class_name', 'type_params'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_generics', ['file', 'line', 'class_name', 'type_params'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'class_name', 'type_params'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_class_name(cursor: sqlite3.Cursor, class_name: str) -> List[Dict[str, Any]]:
        """Get rows by class_name."""
        query = build_query('python_generics', ['file', 'line', 'class_name', 'type_params'], where="class_name = ?")
        cursor.execute(query, (class_name,))
        return [dict(zip(['file', 'line', 'class_name', 'type_params'], row)) for row in cursor.fetchall()]


class PythonLiteralsTable:
    """Accessor class for python_literals table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_literals."""
        query = build_query('python_literals', ['file', 'line', 'usage_context', 'name', 'literal_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'usage_context', 'name', 'literal_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_literals', ['file', 'line', 'usage_context', 'name', 'literal_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'usage_context', 'name', 'literal_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_usage_context(cursor: sqlite3.Cursor, usage_context: str) -> List[Dict[str, Any]]:
        """Get rows by usage_context."""
        query = build_query('python_literals', ['file', 'line', 'usage_context', 'name', 'literal_type'], where="usage_context = ?")
        cursor.execute(query, (usage_context,))
        return [dict(zip(['file', 'line', 'usage_context', 'name', 'literal_type'], row)) for row in cursor.fetchall()]


class PythonMarshmallowFieldsTable:
    """Accessor class for python_marshmallow_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_marshmallow_fields."""
        query = build_query('python_marshmallow_fields', ['file', 'line', 'schema_class_name', 'field_name', 'field_type', 'required', 'allow_none', 'has_validate', 'has_custom_validator'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'schema_class_name', 'field_name', 'field_type', 'required', 'allow_none', 'has_validate', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_marshmallow_fields', ['file', 'line', 'schema_class_name', 'field_name', 'field_type', 'required', 'allow_none', 'has_validate', 'has_custom_validator'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'schema_class_name', 'field_name', 'field_type', 'required', 'allow_none', 'has_validate', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_schema_class_name(cursor: sqlite3.Cursor, schema_class_name: str) -> List[Dict[str, Any]]:
        """Get rows by schema_class_name."""
        query = build_query('python_marshmallow_fields', ['file', 'line', 'schema_class_name', 'field_name', 'field_type', 'required', 'allow_none', 'has_validate', 'has_custom_validator'], where="schema_class_name = ?")
        cursor.execute(query, (schema_class_name,))
        return [dict(zip(['file', 'line', 'schema_class_name', 'field_name', 'field_type', 'required', 'allow_none', 'has_validate', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_required(cursor: sqlite3.Cursor, required: bool) -> List[Dict[str, Any]]:
        """Get rows by required."""
        query = build_query('python_marshmallow_fields', ['file', 'line', 'schema_class_name', 'field_name', 'field_type', 'required', 'allow_none', 'has_validate', 'has_custom_validator'], where="required = ?")
        cursor.execute(query, (required,))
        return [dict(zip(['file', 'line', 'schema_class_name', 'field_name', 'field_type', 'required', 'allow_none', 'has_validate', 'has_custom_validator'], row)) for row in cursor.fetchall()]


class PythonMarshmallowSchemasTable:
    """Accessor class for python_marshmallow_schemas table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_marshmallow_schemas."""
        query = build_query('python_marshmallow_schemas', ['file', 'line', 'schema_class_name', 'field_count', 'has_nested_schemas', 'has_custom_validators'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'schema_class_name', 'field_count', 'has_nested_schemas', 'has_custom_validators'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_marshmallow_schemas', ['file', 'line', 'schema_class_name', 'field_count', 'has_nested_schemas', 'has_custom_validators'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'schema_class_name', 'field_count', 'has_nested_schemas', 'has_custom_validators'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_schema_class_name(cursor: sqlite3.Cursor, schema_class_name: str) -> List[Dict[str, Any]]:
        """Get rows by schema_class_name."""
        query = build_query('python_marshmallow_schemas', ['file', 'line', 'schema_class_name', 'field_count', 'has_nested_schemas', 'has_custom_validators'], where="schema_class_name = ?")
        cursor.execute(query, (schema_class_name,))
        return [dict(zip(['file', 'line', 'schema_class_name', 'field_count', 'has_nested_schemas', 'has_custom_validators'], row)) for row in cursor.fetchall()]


class PythonMockPatternsTable:
    """Accessor class for python_mock_patterns table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_mock_patterns."""
        query = build_query('python_mock_patterns', ['file', 'line', 'mock_type', 'target', 'in_function', 'is_decorator'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'mock_type', 'target', 'in_function', 'is_decorator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_mock_patterns', ['file', 'line', 'mock_type', 'target', 'in_function', 'is_decorator'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'mock_type', 'target', 'in_function', 'is_decorator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_mock_type(cursor: sqlite3.Cursor, mock_type: str) -> List[Dict[str, Any]]:
        """Get rows by mock_type."""
        query = build_query('python_mock_patterns', ['file', 'line', 'mock_type', 'target', 'in_function', 'is_decorator'], where="mock_type = ?")
        cursor.execute(query, (mock_type,))
        return [dict(zip(['file', 'line', 'mock_type', 'target', 'in_function', 'is_decorator'], row)) for row in cursor.fetchall()]


class PythonOrmFieldsTable:
    """Accessor class for python_orm_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_orm_fields."""
        query = build_query('python_orm_fields', ['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_orm_fields', ['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> List[Dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('python_orm_fields', ['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_foreign_key(cursor: sqlite3.Cursor, is_foreign_key: bool) -> List[Dict[str, Any]]:
        """Get rows by is_foreign_key."""
        query = build_query('python_orm_fields', ['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], where="is_foreign_key = ?")
        cursor.execute(query, (is_foreign_key,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'field_type', 'is_primary_key', 'is_foreign_key', 'foreign_key_target'], row)) for row in cursor.fetchall()]


class PythonOrmModelsTable:
    """Accessor class for python_orm_models table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_orm_models."""
        query = build_query('python_orm_models', ['file', 'line', 'model_name', 'table_name', 'orm_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'orm_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_orm_models', ['file', 'line', 'model_name', 'table_name', 'orm_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'orm_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_orm_type(cursor: sqlite3.Cursor, orm_type: str) -> List[Dict[str, Any]]:
        """Get rows by orm_type."""
        query = build_query('python_orm_models', ['file', 'line', 'model_name', 'table_name', 'orm_type'], where="orm_type = ?")
        cursor.execute(query, (orm_type,))
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'orm_type'], row)) for row in cursor.fetchall()]


class PythonOverloadsTable:
    """Accessor class for python_overloads table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_overloads."""
        query = build_query('python_overloads', ['file', 'function_name', 'overload_count', 'variants'])
        cursor.execute(query)
        return [dict(zip(['file', 'function_name', 'overload_count', 'variants'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_overloads', ['file', 'function_name', 'overload_count', 'variants'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'function_name', 'overload_count', 'variants'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_function_name(cursor: sqlite3.Cursor, function_name: str) -> List[Dict[str, Any]]:
        """Get rows by function_name."""
        query = build_query('python_overloads', ['file', 'function_name', 'overload_count', 'variants'], where="function_name = ?")
        cursor.execute(query, (function_name,))
        return [dict(zip(['file', 'function_name', 'overload_count', 'variants'], row)) for row in cursor.fetchall()]


class PythonProtocolsTable:
    """Accessor class for python_protocols table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_protocols."""
        query = build_query('python_protocols', ['file', 'line', 'protocol_name', 'methods', 'is_runtime_checkable'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'protocol_name', 'methods', 'is_runtime_checkable'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_protocols', ['file', 'line', 'protocol_name', 'methods', 'is_runtime_checkable'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'protocol_name', 'methods', 'is_runtime_checkable'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_protocol_name(cursor: sqlite3.Cursor, protocol_name: str) -> List[Dict[str, Any]]:
        """Get rows by protocol_name."""
        query = build_query('python_protocols', ['file', 'line', 'protocol_name', 'methods', 'is_runtime_checkable'], where="protocol_name = ?")
        cursor.execute(query, (protocol_name,))
        return [dict(zip(['file', 'line', 'protocol_name', 'methods', 'is_runtime_checkable'], row)) for row in cursor.fetchall()]


class PythonPytestFixturesTable:
    """Accessor class for python_pytest_fixtures table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_pytest_fixtures."""
        query = build_query('python_pytest_fixtures', ['file', 'line', 'fixture_name', 'scope', 'has_autouse', 'has_params'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'fixture_name', 'scope', 'has_autouse', 'has_params'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_pytest_fixtures', ['file', 'line', 'fixture_name', 'scope', 'has_autouse', 'has_params'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'fixture_name', 'scope', 'has_autouse', 'has_params'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_fixture_name(cursor: sqlite3.Cursor, fixture_name: str) -> List[Dict[str, Any]]:
        """Get rows by fixture_name."""
        query = build_query('python_pytest_fixtures', ['file', 'line', 'fixture_name', 'scope', 'has_autouse', 'has_params'], where="fixture_name = ?")
        cursor.execute(query, (fixture_name,))
        return [dict(zip(['file', 'line', 'fixture_name', 'scope', 'has_autouse', 'has_params'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_scope(cursor: sqlite3.Cursor, scope: str) -> List[Dict[str, Any]]:
        """Get rows by scope."""
        query = build_query('python_pytest_fixtures', ['file', 'line', 'fixture_name', 'scope', 'has_autouse', 'has_params'], where="scope = ?")
        cursor.execute(query, (scope,))
        return [dict(zip(['file', 'line', 'fixture_name', 'scope', 'has_autouse', 'has_params'], row)) for row in cursor.fetchall()]


class PythonPytestMarkersTable:
    """Accessor class for python_pytest_markers table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_pytest_markers."""
        query = build_query('python_pytest_markers', ['file', 'line', 'test_function', 'marker_name', 'marker_args'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'test_function', 'marker_name', 'marker_args'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_pytest_markers', ['file', 'line', 'test_function', 'marker_name', 'marker_args'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'test_function', 'marker_name', 'marker_args'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_marker_name(cursor: sqlite3.Cursor, marker_name: str) -> List[Dict[str, Any]]:
        """Get rows by marker_name."""
        query = build_query('python_pytest_markers', ['file', 'line', 'test_function', 'marker_name', 'marker_args'], where="marker_name = ?")
        cursor.execute(query, (marker_name,))
        return [dict(zip(['file', 'line', 'test_function', 'marker_name', 'marker_args'], row)) for row in cursor.fetchall()]


class PythonPytestParametrizeTable:
    """Accessor class for python_pytest_parametrize table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_pytest_parametrize."""
        query = build_query('python_pytest_parametrize', ['file', 'line', 'test_function', 'parameter_names', 'argvalues_count'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'test_function', 'parameter_names', 'argvalues_count'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_pytest_parametrize', ['file', 'line', 'test_function', 'parameter_names', 'argvalues_count'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'test_function', 'parameter_names', 'argvalues_count'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_test_function(cursor: sqlite3.Cursor, test_function: str) -> List[Dict[str, Any]]:
        """Get rows by test_function."""
        query = build_query('python_pytest_parametrize', ['file', 'line', 'test_function', 'parameter_names', 'argvalues_count'], where="test_function = ?")
        cursor.execute(query, (test_function,))
        return [dict(zip(['file', 'line', 'test_function', 'parameter_names', 'argvalues_count'], row)) for row in cursor.fetchall()]


class PythonRoutesTable:
    """Accessor class for python_routes table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_routes."""
        query = build_query('python_routes', ['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_routes', ['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_framework(cursor: sqlite3.Cursor, framework: str) -> List[Dict[str, Any]]:
        """Get rows by framework."""
        query = build_query('python_routes', ['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'], where="framework = ?")
        cursor.execute(query, (framework,))
        return [dict(zip(['file', 'line', 'framework', 'method', 'pattern', 'handler_function', 'has_auth', 'dependencies', 'blueprint'], row)) for row in cursor.fetchall()]


class PythonTypedDictsTable:
    """Accessor class for python_typed_dicts table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_typed_dicts."""
        query = build_query('python_typed_dicts', ['file', 'line', 'typeddict_name', 'fields'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'typeddict_name', 'fields'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_typed_dicts', ['file', 'line', 'typeddict_name', 'fields'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'typeddict_name', 'fields'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_typeddict_name(cursor: sqlite3.Cursor, typeddict_name: str) -> List[Dict[str, Any]]:
        """Get rows by typeddict_name."""
        query = build_query('python_typed_dicts', ['file', 'line', 'typeddict_name', 'fields'], where="typeddict_name = ?")
        cursor.execute(query, (typeddict_name,))
        return [dict(zip(['file', 'line', 'typeddict_name', 'fields'], row)) for row in cursor.fetchall()]


class PythonValidatorsTable:
    """Accessor class for python_validators table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_validators."""
        query = build_query('python_validators', ['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_validators', ['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> List[Dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('python_validators', ['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_validator_type(cursor: sqlite3.Cursor, validator_type: str) -> List[Dict[str, Any]]:
        """Get rows by validator_type."""
        query = build_query('python_validators', ['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], where="validator_type = ?")
        cursor.execute(query, (validator_type,))
        return [dict(zip(['file', 'line', 'model_name', 'field_name', 'validator_method', 'validator_type'], row)) for row in cursor.fetchall()]


class PythonWtformsFieldsTable:
    """Accessor class for python_wtforms_fields table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_wtforms_fields."""
        query = build_query('python_wtforms_fields', ['file', 'line', 'form_class_name', 'field_name', 'field_type', 'has_validators', 'has_custom_validator'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'form_class_name', 'field_name', 'field_type', 'has_validators', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_wtforms_fields', ['file', 'line', 'form_class_name', 'field_name', 'field_type', 'has_validators', 'has_custom_validator'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'form_class_name', 'field_name', 'field_type', 'has_validators', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_form_class_name(cursor: sqlite3.Cursor, form_class_name: str) -> List[Dict[str, Any]]:
        """Get rows by form_class_name."""
        query = build_query('python_wtforms_fields', ['file', 'line', 'form_class_name', 'field_name', 'field_type', 'has_validators', 'has_custom_validator'], where="form_class_name = ?")
        cursor.execute(query, (form_class_name,))
        return [dict(zip(['file', 'line', 'form_class_name', 'field_name', 'field_type', 'has_validators', 'has_custom_validator'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_validators(cursor: sqlite3.Cursor, has_validators: bool) -> List[Dict[str, Any]]:
        """Get rows by has_validators."""
        query = build_query('python_wtforms_fields', ['file', 'line', 'form_class_name', 'field_name', 'field_type', 'has_validators', 'has_custom_validator'], where="has_validators = ?")
        cursor.execute(query, (has_validators,))
        return [dict(zip(['file', 'line', 'form_class_name', 'field_name', 'field_type', 'has_validators', 'has_custom_validator'], row)) for row in cursor.fetchall()]


class PythonWtformsFormsTable:
    """Accessor class for python_wtforms_forms table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from python_wtforms_forms."""
        query = build_query('python_wtforms_forms', ['file', 'line', 'form_class_name', 'field_count', 'has_custom_validators'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'form_class_name', 'field_count', 'has_custom_validators'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('python_wtforms_forms', ['file', 'line', 'form_class_name', 'field_count', 'has_custom_validators'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'form_class_name', 'field_count', 'has_custom_validators'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_form_class_name(cursor: sqlite3.Cursor, form_class_name: str) -> List[Dict[str, Any]]:
        """Get rows by form_class_name."""
        query = build_query('python_wtforms_forms', ['file', 'line', 'form_class_name', 'field_count', 'has_custom_validators'], where="form_class_name = ?")
        cursor.execute(query, (form_class_name,))
        return [dict(zip(['file', 'line', 'form_class_name', 'field_count', 'has_custom_validators'], row)) for row in cursor.fetchall()]


class ReactComponentHooksTable:
    """Accessor class for react_component_hooks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from react_component_hooks."""
        query = build_query('react_component_hooks', ['id', 'component_file', 'component_name', 'hook_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'component_file', 'component_name', 'hook_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_hook_name(cursor: sqlite3.Cursor, hook_name: str) -> List[Dict[str, Any]]:
        """Get rows by hook_name."""
        query = build_query('react_component_hooks', ['id', 'component_file', 'component_name', 'hook_name'], where="hook_name = ?")
        cursor.execute(query, (hook_name,))
        return [dict(zip(['id', 'component_file', 'component_name', 'hook_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_file(cursor: sqlite3.Cursor, component_file: str) -> List[Dict[str, Any]]:
        """Get rows by component_file."""
        query = build_query('react_component_hooks', ['id', 'component_file', 'component_name', 'hook_name'], where="component_file = ?")
        cursor.execute(query, (component_file,))
        return [dict(zip(['id', 'component_file', 'component_name', 'hook_name'], row)) for row in cursor.fetchall()]


class ReactComponentsTable:
    """Accessor class for react_components table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from react_components."""
        query = build_query('react_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('react_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> List[Dict[str, Any]]:
        """Get rows by name."""
        query = build_query('react_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_jsx', 'props_type'], row)) for row in cursor.fetchall()]


class ReactHookDependenciesTable:
    """Accessor class for react_hook_dependencies table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from react_hook_dependencies."""
        query = build_query('react_hook_dependencies', ['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_dependency_name(cursor: sqlite3.Cursor, dependency_name: str) -> List[Dict[str, Any]]:
        """Get rows by dependency_name."""
        query = build_query('react_hook_dependencies', ['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'], where="dependency_name = ?")
        cursor.execute(query, (dependency_name,))
        return [dict(zip(['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_hook_file(cursor: sqlite3.Cursor, hook_file: str) -> List[Dict[str, Any]]:
        """Get rows by hook_file."""
        query = build_query('react_hook_dependencies', ['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'], where="hook_file = ?")
        cursor.execute(query, (hook_file,))
        return [dict(zip(['id', 'hook_file', 'hook_line', 'hook_component', 'dependency_name'], row)) for row in cursor.fetchall()]


class ReactHooksTable:
    """Accessor class for react_hooks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from react_hooks."""
        query = build_query('react_hooks', ['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('react_hooks', ['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_name(cursor: sqlite3.Cursor, component_name: str) -> List[Dict[str, Any]]:
        """Get rows by component_name."""
        query = build_query('react_hooks', ['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], where="component_name = ?")
        cursor.execute(query, (component_name,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_hook_name(cursor: sqlite3.Cursor, hook_name: str) -> List[Dict[str, Any]]:
        """Get rows by hook_name."""
        query = build_query('react_hooks', ['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], where="hook_name = ?")
        cursor.execute(query, (hook_name,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'dependency_array', 'callback_body', 'has_cleanup', 'cleanup_type'], row)) for row in cursor.fetchall()]


class RefsTable:
    """Accessor class for refs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from refs."""
        query = build_query('refs', ['src', 'kind', 'value', 'line'])
        cursor.execute(query)
        return [dict(zip(['src', 'kind', 'value', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_src(cursor: sqlite3.Cursor, src: str) -> List[Dict[str, Any]]:
        """Get rows by src."""
        query = build_query('refs', ['src', 'kind', 'value', 'line'], where="src = ?")
        cursor.execute(query, (src,))
        return [dict(zip(['src', 'kind', 'value', 'line'], row)) for row in cursor.fetchall()]


class SequelizeAssociationsTable:
    """Accessor class for sequelize_associations table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from sequelize_associations."""
        query = build_query('sequelize_associations', ['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('sequelize_associations', ['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> List[Dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('sequelize_associations', ['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_target_model(cursor: sqlite3.Cursor, target_model: str) -> List[Dict[str, Any]]:
        """Get rows by target_model."""
        query = build_query('sequelize_associations', ['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], where="target_model = ?")
        cursor.execute(query, (target_model,))
        return [dict(zip(['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_association_type(cursor: sqlite3.Cursor, association_type: str) -> List[Dict[str, Any]]:
        """Get rows by association_type."""
        query = build_query('sequelize_associations', ['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], where="association_type = ?")
        cursor.execute(query, (association_type,))
        return [dict(zip(['file', 'line', 'model_name', 'association_type', 'target_model', 'foreign_key', 'through_table'], row)) for row in cursor.fetchall()]


class SequelizeModelsTable:
    """Accessor class for sequelize_models table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from sequelize_models."""
        query = build_query('sequelize_models', ['file', 'line', 'model_name', 'table_name', 'extends_model'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'extends_model'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('sequelize_models', ['file', 'line', 'model_name', 'table_name', 'extends_model'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'extends_model'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_model_name(cursor: sqlite3.Cursor, model_name: str) -> List[Dict[str, Any]]:
        """Get rows by model_name."""
        query = build_query('sequelize_models', ['file', 'line', 'model_name', 'table_name', 'extends_model'], where="model_name = ?")
        cursor.execute(query, (model_name,))
        return [dict(zip(['file', 'line', 'model_name', 'table_name', 'extends_model'], row)) for row in cursor.fetchall()]


class SqlObjectsTable:
    """Accessor class for sql_objects table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from sql_objects."""
        query = build_query('sql_objects', ['file', 'kind', 'name'])
        cursor.execute(query)
        return [dict(zip(['file', 'kind', 'name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('sql_objects', ['file', 'kind', 'name'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'kind', 'name'], row)) for row in cursor.fetchall()]


class SqlQueriesTable:
    """Accessor class for sql_queries table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from sql_queries."""
        query = build_query('sql_queries', ['file_path', 'line_number', 'query_text', 'command', 'extraction_source'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line_number', 'query_text', 'command', 'extraction_source'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('sql_queries', ['file_path', 'line_number', 'query_text', 'command', 'extraction_source'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['file_path', 'line_number', 'query_text', 'command', 'extraction_source'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_command(cursor: sqlite3.Cursor, command: str) -> List[Dict[str, Any]]:
        """Get rows by command."""
        query = build_query('sql_queries', ['file_path', 'line_number', 'query_text', 'command', 'extraction_source'], where="command = ?")
        cursor.execute(query, (command,))
        return [dict(zip(['file_path', 'line_number', 'query_text', 'command', 'extraction_source'], row)) for row in cursor.fetchall()]


class SqlQueryTablesTable:
    """Accessor class for sql_query_tables table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from sql_query_tables."""
        query = build_query('sql_query_tables', ['id', 'query_file', 'query_line', 'table_name'])
        cursor.execute(query)
        return [dict(zip(['id', 'query_file', 'query_line', 'table_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_table_name(cursor: sqlite3.Cursor, table_name: str) -> List[Dict[str, Any]]:
        """Get rows by table_name."""
        query = build_query('sql_query_tables', ['id', 'query_file', 'query_line', 'table_name'], where="table_name = ?")
        cursor.execute(query, (table_name,))
        return [dict(zip(['id', 'query_file', 'query_line', 'table_name'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_query_file(cursor: sqlite3.Cursor, query_file: str) -> List[Dict[str, Any]]:
        """Get rows by query_file."""
        query = build_query('sql_query_tables', ['id', 'query_file', 'query_line', 'table_name'], where="query_file = ?")
        cursor.execute(query, (query_file,))
        return [dict(zip(['id', 'query_file', 'query_line', 'table_name'], row)) for row in cursor.fetchall()]


class SymbolsTable:
    """Accessor class for symbols table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from symbols."""
        query = build_query('symbols', ['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'])
        cursor.execute(query)
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_path(cursor: sqlite3.Cursor, path: str) -> List[Dict[str, Any]]:
        """Get rows by path."""
        query = build_query('symbols', ['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], where="path = ?")
        cursor.execute(query, (path,))
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type(cursor: sqlite3.Cursor, type: str) -> List[Dict[str, Any]]:
        """Get rows by type."""
        query = build_query('symbols', ['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], where="type = ?")
        cursor.execute(query, (type,))
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> List[Dict[str, Any]]:
        """Get rows by name."""
        query = build_query('symbols', ['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'end_line', 'type_annotation', 'parameters', 'is_typed'], row)) for row in cursor.fetchall()]


class SymbolsJsxTable:
    """Accessor class for symbols_jsx table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from symbols_jsx."""
        query = build_query('symbols_jsx', ['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'])
        cursor.execute(query)
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_path(cursor: sqlite3.Cursor, path: str) -> List[Dict[str, Any]]:
        """Get rows by path."""
        query = build_query('symbols_jsx', ['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'], where="path = ?")
        cursor.execute(query, (path,))
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type(cursor: sqlite3.Cursor, type: str) -> List[Dict[str, Any]]:
        """Get rows by type."""
        query = build_query('symbols_jsx', ['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'], where="type = ?")
        cursor.execute(query, (type,))
        return [dict(zip(['path', 'name', 'type', 'line', 'col', 'jsx_mode', 'extraction_pass'], row)) for row in cursor.fetchall()]


class TerraformFilesTable:
    """Accessor class for terraform_files table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from terraform_files."""
        query = build_query('terraform_files', ['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_module_name(cursor: sqlite3.Cursor, module_name: str) -> List[Dict[str, Any]]:
        """Get rows by module_name."""
        query = build_query('terraform_files', ['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'], where="module_name = ?")
        cursor.execute(query, (module_name,))
        return [dict(zip(['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_stack_name(cursor: sqlite3.Cursor, stack_name: str) -> List[Dict[str, Any]]:
        """Get rows by stack_name."""
        query = build_query('terraform_files', ['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'], where="stack_name = ?")
        cursor.execute(query, (stack_name,))
        return [dict(zip(['file_path', 'module_name', 'stack_name', 'backend_type', 'providers_json', 'is_module', 'module_source'], row)) for row in cursor.fetchall()]


class TerraformFindingsTable:
    """Accessor class for terraform_findings table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from terraform_findings."""
        query = build_query('terraform_findings', ['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'])
        cursor.execute(query)
        return [dict(zip(['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_findings', ['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resource_id(cursor: sqlite3.Cursor, resource_id: str) -> List[Dict[str, Any]]:
        """Get rows by resource_id."""
        query = build_query('terraform_findings', ['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], where="resource_id = ?")
        cursor.execute(query, (resource_id,))
        return [dict(zip(['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_severity(cursor: sqlite3.Cursor, severity: str) -> List[Dict[str, Any]]:
        """Get rows by severity."""
        query = build_query('terraform_findings', ['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], where="severity = ?")
        cursor.execute(query, (severity,))
        return [dict(zip(['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_category(cursor: sqlite3.Cursor, category: str) -> List[Dict[str, Any]]:
        """Get rows by category."""
        query = build_query('terraform_findings', ['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], where="category = ?")
        cursor.execute(query, (category,))
        return [dict(zip(['finding_id', 'file_path', 'resource_id', 'category', 'severity', 'title', 'description', 'graph_context_json', 'remediation', 'line'], row)) for row in cursor.fetchall()]


class TerraformOutputsTable:
    """Accessor class for terraform_outputs table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from terraform_outputs."""
        query = build_query('terraform_outputs', ['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'])
        cursor.execute(query)
        return [dict(zip(['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_outputs', ['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_output_name(cursor: sqlite3.Cursor, output_name: str) -> List[Dict[str, Any]]:
        """Get rows by output_name."""
        query = build_query('terraform_outputs', ['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], where="output_name = ?")
        cursor.execute(query, (output_name,))
        return [dict(zip(['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_sensitive(cursor: sqlite3.Cursor, is_sensitive: bool) -> List[Dict[str, Any]]:
        """Get rows by is_sensitive."""
        query = build_query('terraform_outputs', ['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], where="is_sensitive = ?")
        cursor.execute(query, (is_sensitive,))
        return [dict(zip(['output_id', 'file_path', 'output_name', 'value_json', 'is_sensitive', 'description', 'line'], row)) for row in cursor.fetchall()]


class TerraformResourcesTable:
    """Accessor class for terraform_resources table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from terraform_resources."""
        query = build_query('terraform_resources', ['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'properties_json', 'depends_on_json', 'sensitive_flags_json', 'has_public_exposure', 'line'])
        cursor.execute(query)
        return [dict(zip(['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'properties_json', 'depends_on_json', 'sensitive_flags_json', 'has_public_exposure', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_resources', ['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'properties_json', 'depends_on_json', 'sensitive_flags_json', 'has_public_exposure', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'properties_json', 'depends_on_json', 'sensitive_flags_json', 'has_public_exposure', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resource_type(cursor: sqlite3.Cursor, resource_type: str) -> List[Dict[str, Any]]:
        """Get rows by resource_type."""
        query = build_query('terraform_resources', ['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'properties_json', 'depends_on_json', 'sensitive_flags_json', 'has_public_exposure', 'line'], where="resource_type = ?")
        cursor.execute(query, (resource_type,))
        return [dict(zip(['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'properties_json', 'depends_on_json', 'sensitive_flags_json', 'has_public_exposure', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_resource_name(cursor: sqlite3.Cursor, resource_name: str) -> List[Dict[str, Any]]:
        """Get rows by resource_name."""
        query = build_query('terraform_resources', ['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'properties_json', 'depends_on_json', 'sensitive_flags_json', 'has_public_exposure', 'line'], where="resource_name = ?")
        cursor.execute(query, (resource_name,))
        return [dict(zip(['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'properties_json', 'depends_on_json', 'sensitive_flags_json', 'has_public_exposure', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_has_public_exposure(cursor: sqlite3.Cursor, has_public_exposure: bool) -> List[Dict[str, Any]]:
        """Get rows by has_public_exposure."""
        query = build_query('terraform_resources', ['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'properties_json', 'depends_on_json', 'sensitive_flags_json', 'has_public_exposure', 'line'], where="has_public_exposure = ?")
        cursor.execute(query, (has_public_exposure,))
        return [dict(zip(['resource_id', 'file_path', 'resource_type', 'resource_name', 'module_path', 'properties_json', 'depends_on_json', 'sensitive_flags_json', 'has_public_exposure', 'line'], row)) for row in cursor.fetchall()]


class TerraformVariableValuesTable:
    """Accessor class for terraform_variable_values table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from terraform_variable_values."""
        query = build_query('terraform_variable_values', ['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'])
        cursor.execute(query)
        return [dict(zip(['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_variable_values', ['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_variable_name(cursor: sqlite3.Cursor, variable_name: str) -> List[Dict[str, Any]]:
        """Get rows by variable_name."""
        query = build_query('terraform_variable_values', ['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], where="variable_name = ?")
        cursor.execute(query, (variable_name,))
        return [dict(zip(['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_sensitive_context(cursor: sqlite3.Cursor, is_sensitive_context: bool) -> List[Dict[str, Any]]:
        """Get rows by is_sensitive_context."""
        query = build_query('terraform_variable_values', ['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], where="is_sensitive_context = ?")
        cursor.execute(query, (is_sensitive_context,))
        return [dict(zip(['id', 'file_path', 'variable_name', 'variable_value_json', 'line', 'is_sensitive_context'], row)) for row in cursor.fetchall()]


class TerraformVariablesTable:
    """Accessor class for terraform_variables table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from terraform_variables."""
        query = build_query('terraform_variables', ['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'])
        cursor.execute(query)
        return [dict(zip(['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file_path(cursor: sqlite3.Cursor, file_path: str) -> List[Dict[str, Any]]:
        """Get rows by file_path."""
        query = build_query('terraform_variables', ['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], where="file_path = ?")
        cursor.execute(query, (file_path,))
        return [dict(zip(['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_variable_name(cursor: sqlite3.Cursor, variable_name: str) -> List[Dict[str, Any]]:
        """Get rows by variable_name."""
        query = build_query('terraform_variables', ['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], where="variable_name = ?")
        cursor.execute(query, (variable_name,))
        return [dict(zip(['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_sensitive(cursor: sqlite3.Cursor, is_sensitive: bool) -> List[Dict[str, Any]]:
        """Get rows by is_sensitive."""
        query = build_query('terraform_variables', ['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], where="is_sensitive = ?")
        cursor.execute(query, (is_sensitive,))
        return [dict(zip(['variable_id', 'file_path', 'variable_name', 'variable_type', 'default_json', 'is_sensitive', 'description', 'source_file', 'line'], row)) for row in cursor.fetchall()]


class TypeAnnotationsTable:
    """Accessor class for type_annotations table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from type_annotations."""
        query = build_query('type_annotations', ['file', 'line', 'column', 'symbol_name', 'symbol_kind', 'type_annotation', 'is_any', 'is_unknown', 'is_generic', 'has_type_params', 'type_params', 'return_type', 'extends_type'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'column', 'symbol_name', 'symbol_kind', 'type_annotation', 'is_any', 'is_unknown', 'is_generic', 'has_type_params', 'type_params', 'return_type', 'extends_type'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('type_annotations', ['file', 'line', 'column', 'symbol_name', 'symbol_kind', 'type_annotation', 'is_any', 'is_unknown', 'is_generic', 'has_type_params', 'type_params', 'return_type', 'extends_type'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'column', 'symbol_name', 'symbol_kind', 'type_annotation', 'is_any', 'is_unknown', 'is_generic', 'has_type_params', 'type_params', 'return_type', 'extends_type'], row)) for row in cursor.fetchall()]


class ValidationFrameworkUsageTable:
    """Accessor class for validation_framework_usage table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from validation_framework_usage."""
        query = build_query('validation_framework_usage', ['file_path', 'line', 'framework', 'method', 'variable_name', 'is_validator', 'argument_expr'])
        cursor.execute(query)
        return [dict(zip(['file_path', 'line', 'framework', 'method', 'variable_name', 'is_validator', 'argument_expr'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_is_validator(cursor: sqlite3.Cursor, is_validator: bool) -> List[Dict[str, Any]]:
        """Get rows by is_validator."""
        query = build_query('validation_framework_usage', ['file_path', 'line', 'framework', 'method', 'variable_name', 'is_validator', 'argument_expr'], where="is_validator = ?")
        cursor.execute(query, (is_validator,))
        return [dict(zip(['file_path', 'line', 'framework', 'method', 'variable_name', 'is_validator', 'argument_expr'], row)) for row in cursor.fetchall()]


class VariableUsageTable:
    """Accessor class for variable_usage table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from variable_usage."""
        query = build_query('variable_usage', ['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('variable_usage', ['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_in_component(cursor: sqlite3.Cursor, in_component: str) -> List[Dict[str, Any]]:
        """Get rows by in_component."""
        query = build_query('variable_usage', ['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], where="in_component = ?")
        cursor.execute(query, (in_component,))
        return [dict(zip(['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_variable_name(cursor: sqlite3.Cursor, variable_name: str) -> List[Dict[str, Any]]:
        """Get rows by variable_name."""
        query = build_query('variable_usage', ['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], where="variable_name = ?")
        cursor.execute(query, (variable_name,))
        return [dict(zip(['file', 'line', 'variable_name', 'usage_type', 'in_component', 'in_hook', 'scope_level'], row)) for row in cursor.fetchall()]


class VueComponentsTable:
    """Accessor class for vue_components table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from vue_components."""
        query = build_query('vue_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used', 'props_definition', 'emits_definition', 'setup_return'])
        cursor.execute(query)
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used', 'props_definition', 'emits_definition', 'setup_return'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used', 'props_definition', 'emits_definition', 'setup_return'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used', 'props_definition', 'emits_definition', 'setup_return'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_name(cursor: sqlite3.Cursor, name: str) -> List[Dict[str, Any]]:
        """Get rows by name."""
        query = build_query('vue_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used', 'props_definition', 'emits_definition', 'setup_return'], where="name = ?")
        cursor.execute(query, (name,))
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used', 'props_definition', 'emits_definition', 'setup_return'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_type(cursor: sqlite3.Cursor, type: str) -> List[Dict[str, Any]]:
        """Get rows by type."""
        query = build_query('vue_components', ['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used', 'props_definition', 'emits_definition', 'setup_return'], where="type = ?")
        cursor.execute(query, (type,))
        return [dict(zip(['file', 'name', 'type', 'start_line', 'end_line', 'has_template', 'has_style', 'composition_api_used', 'props_definition', 'emits_definition', 'setup_return'], row)) for row in cursor.fetchall()]


class VueDirectivesTable:
    """Accessor class for vue_directives table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from vue_directives."""
        query = build_query('vue_directives', ['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_directives', ['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_directive_name(cursor: sqlite3.Cursor, directive_name: str) -> List[Dict[str, Any]]:
        """Get rows by directive_name."""
        query = build_query('vue_directives', ['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'], where="directive_name = ?")
        cursor.execute(query, (directive_name,))
        return [dict(zip(['file', 'line', 'directive_name', 'expression', 'in_component', 'has_key', 'modifiers'], row)) for row in cursor.fetchall()]


class VueHooksTable:
    """Accessor class for vue_hooks table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from vue_hooks."""
        query = build_query('vue_hooks', ['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_hooks', ['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_component_name(cursor: sqlite3.Cursor, component_name: str) -> List[Dict[str, Any]]:
        """Get rows by component_name."""
        query = build_query('vue_hooks', ['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], where="component_name = ?")
        cursor.execute(query, (component_name,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_hook_type(cursor: sqlite3.Cursor, hook_type: str) -> List[Dict[str, Any]]:
        """Get rows by hook_type."""
        query = build_query('vue_hooks', ['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], where="hook_type = ?")
        cursor.execute(query, (hook_type,))
        return [dict(zip(['file', 'line', 'component_name', 'hook_name', 'hook_type', 'dependencies', 'return_value', 'is_async'], row)) for row in cursor.fetchall()]


class VueProvideInjectTable:
    """Accessor class for vue_provide_inject table."""

    @staticmethod
    def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
        """Get all rows from vue_provide_inject."""
        query = build_query('vue_provide_inject', ['file', 'line', 'component_name', 'operation_type', 'key_name', 'value_expr', 'is_reactive'])
        cursor.execute(query)
        return [dict(zip(['file', 'line', 'component_name', 'operation_type', 'key_name', 'value_expr', 'is_reactive'], row)) for row in cursor.fetchall()]

    @staticmethod
    def get_by_file(cursor: sqlite3.Cursor, file: str) -> List[Dict[str, Any]]:
        """Get rows by file."""
        query = build_query('vue_provide_inject', ['file', 'line', 'component_name', 'operation_type', 'key_name', 'value_expr', 'is_reactive'], where="file = ?")
        cursor.execute(query, (file,))
        return [dict(zip(['file', 'line', 'component_name', 'operation_type', 'key_name', 'value_expr', 'is_reactive'], row)) for row in cursor.fetchall()]

