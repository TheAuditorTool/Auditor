"""Node.js/TypeScript/React/Vue database operations.

This module contains add_* methods for NODE_TABLES defined in schemas/node_schema.py.
Handles 17 Node.js tables including TypeScript, React, Vue, and package management.
"""
from __future__ import annotations


import json
from typing import Optional, Dict, List


class NodeDatabaseMixin:
    """Mixin providing add_* methods for NODE_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.
    """

    # ========================================================
    # TYPESCRIPT BATCH METHODS
    # ========================================================

    def add_class_property(self, file: str, line: int, class_name: str, property_name: str,
                          property_type: str | None = None, is_optional: bool = False,
                          is_readonly: bool = False, access_modifier: str | None = None,
                          has_declare: bool = False, initializer: str | None = None):
        """Add a class property declaration record to the batch.

        Args:
            file: File containing the class
            line: Line number of property declaration
            class_name: Name of the containing class
            property_name: Name of the property
            property_type: TypeScript type annotation (e.g., "string", "number | null")
            is_optional: Whether property has ? modifier
            is_readonly: Whether property has readonly keyword
            access_modifier: "private", "protected", or "public" (None = public by default)
            has_declare: Whether property has declare keyword (TypeScript ambient declaration)
            initializer: Default value expression if present
        """
        self.generic_batches['class_properties'].append((
            file, line, class_name, property_name, property_type,
            1 if is_optional else 0,
            1 if is_readonly else 0,
            access_modifier,
            1 if has_declare else 0,
            initializer
        ))

    def add_type_annotation(self, file_path: str, line: int, column: int, symbol_name: str,
                           symbol_kind: str, type_annotation: str = None, is_any: bool = False,
                           is_unknown: bool = False, is_generic: bool = False,
                           has_type_params: bool = False, type_params: str = None,
                           return_type: str = None, extends_type: str = None):
        """Add a TypeScript type annotation record to the batch."""
        self.generic_batches['type_annotations'].append((file_path, line, column, symbol_name, symbol_kind,
                                                         type_annotation, is_any, is_unknown, is_generic,
                                                         has_type_params, type_params, return_type, extends_type))

    # ========================================================
    # REACT BATCH METHODS
    # ========================================================

    def add_react_component(self, file_path: str, name: str, component_type: str,
                           start_line: int, end_line: int, has_jsx: bool,
                           hooks_used: list[str] | None = None,
                           props_type: str | None = None):
        """Add a React component to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch component record (without hooks_used column)
        - Phase 2: Batch junction records for each hook used

        NO FALLBACKS. If hooks_used is malformed, hard fail.
        """
        # Phase 1: Add component record (6 params, no hooks_used column)
        self.generic_batches['react_components'].append((file_path, name, component_type,
                                                         start_line, end_line, has_jsx, props_type))

        # Phase 2: Add junction records for each hook used
        if hooks_used:
            for hook_name in hooks_used:
                if not hook_name:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['react_component_hooks'].append((file_path, name, hook_name))

    def add_react_hook(self, file_path: str, line: int, component_name: str,
                      hook_name: str, dependency_array: list[str] | None = None,
                      dependency_vars: list[str] | None = None,
                      callback_body: str | None = None, has_cleanup: bool = False,
                      cleanup_type: str | None = None):
        """Add a React hook usage to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch hook record (without dependency_vars column)
        - Phase 2: Batch junction records for each dependency variable

        NO FALLBACKS. If dependency_vars is malformed, hard fail.
        """
        # Phase 1: Add hook record (7 params, no dependency_vars column)
        deps_array_json = json.dumps(dependency_array) if dependency_array is not None else None
        # Limit callback body to 500 chars
        if callback_body and len(callback_body) > 500:
            callback_body = callback_body[:497] + '...'
        self.generic_batches['react_hooks'].append((file_path, line, component_name, hook_name,
                                                    deps_array_json, callback_body,
                                                    has_cleanup, cleanup_type))

        # Phase 2: Add junction records for each dependency variable
        if dependency_vars:
            for dep_var in dependency_vars:
                if not dep_var:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['react_hook_dependencies'].append((file_path, line, component_name, dep_var))

    # ========================================================
    # VUE BATCH METHODS
    # ========================================================

    def add_vue_component(self, file_path: str, name: str, component_type: str,
                         start_line: int, end_line: int, has_template: bool = False,
                         has_style: bool = False, composition_api_used: bool = False,
                         props_definition: dict | None = None,
                         emits_definition: dict | None = None,
                         setup_return: str | None = None):
        """Add a Vue component to the batch."""
        props_json = json.dumps(props_definition) if props_definition else None
        emits_json = json.dumps(emits_definition) if emits_definition else None
        self.generic_batches['vue_components'].append((file_path, name, component_type,
                                                       start_line, end_line, has_template, has_style,
                                                       composition_api_used, props_json, emits_json,
                                                       setup_return))

    def add_vue_hook(self, file_path: str, line: int, component_name: str,
                    hook_name: str, hook_type: str, dependencies: list[str] | None = None,
                    return_value: str | None = None, is_async: bool = False):
        """Add a Vue hook/reactivity usage to the batch."""
        deps_json = json.dumps(dependencies) if dependencies else None
        self.generic_batches['vue_hooks'].append((file_path, line, component_name, hook_name,
                                                  hook_type, deps_json, return_value, is_async))

    def add_vue_directive(self, file_path: str, line: int, directive_name: str,
                         expression: str, in_component: str, has_key: bool = False,
                         modifiers: list[str] | None = None):
        """Add a Vue directive usage to the batch."""
        modifiers_json = json.dumps(modifiers) if modifiers else None
        self.generic_batches['vue_directives'].append((file_path, line, directive_name, expression,
                                                       in_component, has_key, modifiers_json))

    def add_vue_provide_inject(self, file_path: str, line: int, component_name: str,
                              operation_type: str, key_name: str, value_expr: str | None = None,
                              is_reactive: bool = False):
        """Add a Vue provide/inject operation to the batch."""
        self.generic_batches['vue_provide_inject'].append((file_path, line, component_name,
                                                           operation_type, key_name, value_expr, is_reactive))

    # ========================================================
    # PACKAGE MANAGEMENT BATCH METHODS
    # ========================================================

    def add_package_config(self, file_path: str, package_name: str, version: str,
                          dependencies: dict | None, dev_dependencies: dict | None,
                          peer_dependencies: dict | None, scripts: dict | None,
                          engines: dict | None, workspaces: list | None,
                          is_private: bool = False):
        """Add a package.json configuration to the batch."""
        deps_json = json.dumps(dependencies) if dependencies else None
        dev_deps_json = json.dumps(dev_dependencies) if dev_dependencies else None
        peer_deps_json = json.dumps(peer_dependencies) if peer_dependencies else None
        scripts_json = json.dumps(scripts) if scripts else None
        engines_json = json.dumps(engines) if engines else None
        workspaces_json = json.dumps(workspaces) if workspaces else None

        self.generic_batches['package_configs'].append((file_path, package_name, version,
                                                        deps_json, dev_deps_json, peer_deps_json,
                                                        scripts_json, engines_json, workspaces_json,
                                                        is_private))

    def add_lock_analysis(self, file_path: str, lock_type: str,
                         package_manager_version: str | None,
                         total_packages: int, duplicate_packages: dict | None,
                         lock_file_version: str | None):
        """Add a lock file analysis result to the batch."""
        duplicates_json = json.dumps(duplicate_packages) if duplicate_packages else None

        self.generic_batches['lock_analysis'].append((file_path, lock_type, package_manager_version,
                                                      total_packages, duplicates_json, lock_file_version))

    def add_import_style(self, file_path: str, line: int, package: str,
                        import_style: str, imported_names: list[str] | None = None,
                        alias_name: str | None = None, full_statement: str | None = None):
        """Add an import style record to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch import style record (without imported_names column)
        - Phase 2: Batch junction records for each imported name

        NO FALLBACKS. If imported_names is malformed, hard fail.
        """
        # Phase 1: Add import style record (5 params, no imported_names column)
        self.generic_batches['import_styles'].append((file_path, line, package, import_style,
                                                      alias_name, full_statement))

        # Phase 2: Add junction records for each imported name
        if imported_names:
            for imported_name in imported_names:
                if not imported_name:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['import_style_names'].append((file_path, line, imported_name))

    # ========================================================
    # FRONTEND API CALLS BATCH METHODS
    # ========================================================

    def add_frontend_api_call(self, file: str, line: int, method: str, url_literal: str,
                              body_variable: str | None = None, function_name: str | None = None):
        """Add a frontend API call record to the batch.

        Tracks fetch() and axios calls from frontend code to backend APIs.
        Used for cross-boundary taint flow analysis (frontend -> backend).

        Args:
            file: Frontend file making the API call
            line: Line number of the call
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            url_literal: Static API path (e.g., '/api/users')
            body_variable: Variable name sent as body (e.g., 'userData')
            function_name: Function containing the API call
        """
        self.generic_batches['frontend_api_calls'].append((
            file, line, method, url_literal, body_variable, function_name
        ))

    # ========================================================
    # FRAMEWORK DETECTION BATCH METHODS
    # ========================================================

    def add_framework(self, name, version, language, path, source, is_primary=False):
        """Add framework to batch."""
        # Skip if no name provided
        if not name:
            return
        self.generic_batches['frameworks'].append((name, version, language, path, source, is_primary))
        if len(self.generic_batches['frameworks']) >= self.batch_size:
            self.flush_batch()

    def add_framework_safe_sink(self, framework_id, pattern, sink_type, is_safe, reason):
        """Add framework safe sink to batch."""
        self.generic_batches['framework_safe_sinks'].append((framework_id, pattern, sink_type, is_safe, reason))
        if len(self.generic_batches['framework_safe_sinks']) >= self.batch_size:
            self.flush_batch()

    def get_framework_id(self, name, language):
        """Get framework ID from database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM frameworks WHERE name = ? AND language = ?", (name, language))
        result = cursor.fetchone()
        return result[0] if result else None
