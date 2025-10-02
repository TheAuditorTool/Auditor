"""Database operations for the indexer.

This module contains the DatabaseManager class which handles all database
operations including schema creation, batch inserts, and transaction management.
"""

import sqlite3
import json
from typing import Any, List, Dict, Optional
from pathlib import Path

from .config import DEFAULT_BATCH_SIZE, MAX_BATCH_SIZE


class DatabaseManager:
    """Manages database operations with batching and transactions."""

    def __init__(self, db_path: str, batch_size: int = DEFAULT_BATCH_SIZE):
        """Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file
            batch_size: Size of batches for insert operations
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        
        # Validate and set batch size
        if batch_size <= 0:
            self.batch_size = DEFAULT_BATCH_SIZE
        elif batch_size > MAX_BATCH_SIZE:
            self.batch_size = MAX_BATCH_SIZE
        else:
            self.batch_size = batch_size
            
        # Initialize batch lists
        self.files_batch = []
        self.refs_batch = []
        self.endpoints_batch = []
        self.sql_objects_batch = []
        self.sql_queries_batch = []
        self.symbols_batch = []
        self.orm_queries_batch = []
        self.docker_images_batch = []
        self.assignments_batch = []
        self.function_call_args_batch = []
        self.function_returns_batch = []
        self.prisma_batch = []
        self.compose_batch = []
        self.nginx_batch = []
        self.cfg_blocks_batch = []
        self.cfg_edges_batch = []
        self.cfg_statements_batch = []
        self.react_components_batch = []
        self.react_hooks_batch = []
        self.variable_usage_batch = []
        self.frameworks_batch = []
        self.framework_safe_sinks_batch = []

        # JSX-specific batch lists for dual-pass extraction
        self.function_returns_jsx_batch = []
        self.symbols_jsx_batch = []
        self.assignments_jsx_batch = []
        self.function_call_args_jsx_batch = []

        # Vue-specific batch lists for framework analysis
        self.vue_components_batch = []
        self.vue_hooks_batch = []
        self.vue_directives_batch = []
        self.vue_provide_inject_batch = []

        # TypeScript type annotation batch list
        self.type_annotations_batch = []

        # Build analysis batch lists
        self.package_configs_batch = []
        self.lock_analysis_batch = []
        self.import_styles_batch = []

    def begin_transaction(self):
        """Start a new transaction."""
        self.conn.execute("BEGIN IMMEDIATE")

    def commit(self):
        """Commit the current transaction."""
        try:
            self.conn.commit()
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to commit database changes: {e}")

    def rollback(self):
        """Rollback the current transaction."""
        self.conn.rollback()

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def validate_schema(self) -> bool:
        """
        Validate database schema matches expected definitions.

        Runs after indexing to ensure all tables were created correctly.
        Logs warnings for any mismatches.

        Returns:
            True if all schemas valid, False if mismatches found
        """
        from .schema import validate_all_tables
        import sys

        cursor = self.conn.cursor()
        mismatches = validate_all_tables(cursor)

        if not mismatches:
            print("[SCHEMA] All table schemas validated successfully", file=sys.stderr)
            return True

        print("[SCHEMA] Schema validation warnings detected:", file=sys.stderr)
        for table_name, errors in mismatches.items():
            print(f"[SCHEMA]   Table: {table_name}", file=sys.stderr)
            for error in errors:
                print(f"[SCHEMA]     - {error}", file=sys.stderr)

        print("[SCHEMA] Note: Some mismatches may be due to migration columns (expected)", file=sys.stderr)
        return False

    def create_schema(self):
        """Create all database tables and indexes."""
        cursor = self.conn.cursor()

        # Create tables
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS files(
                path TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL,
                ext TEXT NOT NULL,
                bytes INTEGER NOT NULL,
                loc INTEGER NOT NULL,
                file_category TEXT NOT NULL DEFAULT 'source'
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS config_files(
                path TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                type TEXT NOT NULL,
                context_dir TEXT,
                FOREIGN KEY(path) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS refs(
                src TEXT NOT NULL,
                kind TEXT NOT NULL,
                value TEXT NOT NULL,
                FOREIGN KEY(src) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS api_endpoints(
                file TEXT NOT NULL,
                line INTEGER,
                method TEXT NOT NULL,
                pattern TEXT NOT NULL,
                path TEXT,
                controls TEXT,
                has_auth BOOLEAN DEFAULT 0,
                handler_function TEXT,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        # Migration: Add new columns to api_endpoints table (Phase 4)
        # For existing databases with old 4-column schema, add the 4 new columns
        try:
            cursor.execute("ALTER TABLE api_endpoints ADD COLUMN line INTEGER")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE api_endpoints ADD COLUMN path TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE api_endpoints ADD COLUMN has_auth BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE api_endpoints ADD COLUMN handler_function TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sql_objects(
                file TEXT NOT NULL,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS symbols(
                path TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                line INTEGER NOT NULL,
                col INTEGER NOT NULL,
                FOREIGN KEY(path) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sql_queries(
                file_path TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                query_text TEXT NOT NULL,
                command TEXT NOT NULL CHECK(command != 'UNKNOWN'),
                tables TEXT,
                extraction_source TEXT NOT NULL DEFAULT 'code_execute',
                FOREIGN KEY(file_path) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS docker_images(
                file_path TEXT PRIMARY KEY,
                base_image TEXT,
                exposed_ports TEXT,
                env_vars TEXT,
                build_args TEXT,
                user TEXT,
                has_healthcheck BOOLEAN DEFAULT 0,
                FOREIGN KEY(file_path) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orm_queries(
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                query_type TEXT NOT NULL,
                includes TEXT,
                has_limit BOOLEAN DEFAULT 0,
                has_transaction BOOLEAN DEFAULT 0,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS prisma_models(
                model_name TEXT NOT NULL,
                field_name TEXT NOT NULL,
                field_type TEXT NOT NULL,
                is_indexed BOOLEAN DEFAULT 0,
                is_unique BOOLEAN DEFAULT 0,
                is_relation BOOLEAN DEFAULT 0,
                PRIMARY KEY (model_name, field_name)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS compose_services(
                file_path TEXT NOT NULL,
                service_name TEXT NOT NULL,
                image TEXT,
                ports TEXT,
                volumes TEXT,
                environment TEXT,
                is_privileged BOOLEAN DEFAULT 0,
                network_mode TEXT,
                PRIMARY KEY (file_path, service_name),
                FOREIGN KEY(file_path) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nginx_configs(
                file_path TEXT NOT NULL,
                block_type TEXT NOT NULL,
                block_context TEXT,
                directives TEXT,
                level INTEGER DEFAULT 0,
                PRIMARY KEY (file_path, block_type, block_context),
                FOREIGN KEY(file_path) REFERENCES files(path)
            )
        """
        )

        # Build analysis tables for bundle rules
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS package_configs(
                file_path TEXT PRIMARY KEY,
                package_name TEXT,
                version TEXT,
                dependencies TEXT,
                dev_dependencies TEXT,
                peer_dependencies TEXT,
                scripts TEXT,
                engines TEXT,
                workspaces TEXT,
                private BOOLEAN DEFAULT 0,
                FOREIGN KEY(file_path) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS lock_analysis(
                file_path TEXT PRIMARY KEY,
                lock_type TEXT NOT NULL,
                package_manager_version TEXT,
                total_packages INTEGER,
                duplicate_packages TEXT,
                lock_file_version TEXT,
                FOREIGN KEY(file_path) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS import_styles(
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                package TEXT NOT NULL,
                import_style TEXT NOT NULL,
                imported_names TEXT,
                alias_name TEXT,
                full_statement TEXT,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        # Data flow analysis tables for taint tracking
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS assignments (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                target_var TEXT NOT NULL,
                source_expr TEXT NOT NULL,
                source_vars TEXT,
                in_function TEXT NOT NULL,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS function_call_args (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                caller_function TEXT NOT NULL,
                callee_function TEXT NOT NULL CHECK(callee_function != ''),
                argument_index INTEGER NOT NULL,
                argument_expr TEXT NOT NULL,
                param_name TEXT NOT NULL,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS function_returns (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                function_name TEXT NOT NULL,
                return_expr TEXT NOT NULL,
                return_vars TEXT,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        # Control Flow Graph tables
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cfg_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file TEXT NOT NULL,
                function_name TEXT NOT NULL,
                block_type TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                condition_expr TEXT,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cfg_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file TEXT NOT NULL,
                function_name TEXT NOT NULL,
                source_block_id INTEGER NOT NULL,
                target_block_id INTEGER NOT NULL,
                edge_type TEXT NOT NULL,
                FOREIGN KEY(file) REFERENCES files(path),
                FOREIGN KEY(source_block_id) REFERENCES cfg_blocks(id),
                FOREIGN KEY(target_block_id) REFERENCES cfg_blocks(id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cfg_block_statements (
                block_id INTEGER NOT NULL,
                statement_type TEXT NOT NULL,
                line INTEGER NOT NULL,
                statement_text TEXT,
                FOREIGN KEY(block_id) REFERENCES cfg_blocks(id)
            )
        """
        )

        # React-specific tables for enhanced hooks analysis
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS react_components (
                file TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                has_jsx BOOLEAN DEFAULT 0,
                hooks_used TEXT,
                props_type TEXT,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS react_hooks (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                component_name TEXT NOT NULL,
                hook_name TEXT NOT NULL,
                dependency_array TEXT,
                dependency_vars TEXT,
                callback_body TEXT,
                has_cleanup BOOLEAN DEFAULT 0,
                cleanup_type TEXT,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS variable_usage (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                variable_name TEXT NOT NULL,
                usage_type TEXT NOT NULL,
                in_component TEXT,
                in_hook TEXT,
                scope_level INTEGER,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        # Framework detection tables for context-aware analysis
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS frameworks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version TEXT,
                language TEXT NOT NULL,
                path TEXT DEFAULT '.',
                source TEXT,
                package_manager TEXT,
                is_primary BOOLEAN DEFAULT 0,
                UNIQUE(name, language, path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS framework_safe_sinks(
                framework_id INTEGER,
                sink_pattern TEXT NOT NULL,
                sink_type TEXT NOT NULL,
                is_safe BOOLEAN DEFAULT 1,
                reason TEXT,
                FOREIGN KEY(framework_id) REFERENCES frameworks(id)
            )
        """
        )

        # Enhance function_returns table for React (handle existing columns gracefully)
        try:
            cursor.execute("ALTER TABLE function_returns ADD COLUMN has_jsx BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE function_returns ADD COLUMN returns_component BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE function_returns ADD COLUMN cleanup_operations TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # ========================================================
        # PARALLEL JSX TABLES FOR DUAL-PASS EXTRACTION
        # ========================================================
        # These tables store preserved JSX data (Pass 1)
        # While standard tables store transformed data (Pass 2)

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS function_returns_jsx (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                function_name TEXT,
                return_expr TEXT,
                return_vars TEXT,
                has_jsx BOOLEAN DEFAULT 0,
                returns_component BOOLEAN DEFAULT 0,
                cleanup_operations TEXT,
                jsx_mode TEXT NOT NULL DEFAULT 'preserved',
                extraction_pass INTEGER DEFAULT 1,
                PRIMARY KEY (file, line, extraction_pass),
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS symbols_jsx (
                path TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                line INTEGER NOT NULL,
                col INTEGER NOT NULL,
                jsx_mode TEXT NOT NULL DEFAULT 'preserved',
                extraction_pass INTEGER DEFAULT 1,
                PRIMARY KEY (path, name, line, jsx_mode),
                FOREIGN KEY(path) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS assignments_jsx (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                target_var TEXT NOT NULL,
                source_expr TEXT NOT NULL,
                source_vars TEXT,
                in_function TEXT NOT NULL,
                jsx_mode TEXT NOT NULL DEFAULT 'preserved',
                extraction_pass INTEGER DEFAULT 1,
                PRIMARY KEY (file, line, target_var, jsx_mode),
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS function_call_args_jsx (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                caller_function TEXT NOT NULL,
                callee_function TEXT NOT NULL,
                argument_index INTEGER NOT NULL,
                argument_expr TEXT NOT NULL,
                param_name TEXT NOT NULL,
                jsx_mode TEXT NOT NULL DEFAULT 'preserved',
                extraction_pass INTEGER DEFAULT 1,
                PRIMARY KEY (file, line, callee_function, argument_index, jsx_mode),
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        # Unified views for backward compatibility
        cursor.execute(
            """
            CREATE VIEW IF NOT EXISTS function_returns_unified AS
            SELECT *, 'transformed' as view_jsx_mode, 0 as view_extraction_pass
            FROM function_returns
            UNION ALL
            SELECT * FROM function_returns_jsx
        """
        )

        cursor.execute(
            """
            CREATE VIEW IF NOT EXISTS symbols_unified AS
            SELECT *, 'transformed' as view_jsx_mode FROM symbols
            UNION ALL
            SELECT * FROM symbols_jsx
        """
        )

        # ========================================================
        # VUE-SPECIFIC TABLES FOR FRAMEWORK ANALYSIS
        # ========================================================
        # These tables store Vue component data and patterns

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vue_components (
                file TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                has_template BOOLEAN DEFAULT 0,
                has_style BOOLEAN DEFAULT 0,
                composition_api_used BOOLEAN DEFAULT 0,
                props_definition TEXT,
                emits_definition TEXT,
                setup_return TEXT,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vue_hooks (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                component_name TEXT NOT NULL,
                hook_name TEXT NOT NULL,
                hook_type TEXT NOT NULL,
                dependencies TEXT,
                return_value TEXT,
                is_async BOOLEAN DEFAULT 0,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vue_directives (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                directive_name TEXT NOT NULL,
                expression TEXT,
                in_component TEXT,
                has_key BOOLEAN DEFAULT 0,
                modifiers TEXT,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        # ========================================================
        # TYPESCRIPT TYPE ANNOTATIONS TABLE
        # ========================================================
        # Store TypeScript type information extracted by compiler
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS type_annotations (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                column INTEGER,
                symbol_name TEXT NOT NULL,
                symbol_kind TEXT NOT NULL,
                type_annotation TEXT,
                is_any BOOLEAN DEFAULT 0,
                is_unknown BOOLEAN DEFAULT 0,
                is_generic BOOLEAN DEFAULT 0,
                has_type_params BOOLEAN DEFAULT 0,
                type_params TEXT,
                return_type TEXT,
                extends_type TEXT,
                PRIMARY KEY (file, line, column, symbol_name),
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vue_provide_inject (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                component_name TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                key_name TEXT NOT NULL,
                value_expr TEXT,
                is_reactive BOOLEAN DEFAULT 0,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        # ========================================================
        # FINDINGS CONSOLIDATED TABLE (DUAL-WRITE PATTERN)
        # ========================================================
        # This table stores ALL tool findings for fast FCE correlation
        # while preserving JSON outputs for AI consumption pipeline.
        # Tools write to BOTH database (performance) AND JSON (AI consumption).
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS findings_consolidated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                column INTEGER,
                rule TEXT NOT NULL,
                tool TEXT NOT NULL,
                message TEXT,
                severity TEXT NOT NULL,
                category TEXT,
                confidence REAL,
                code_snippet TEXT,
                cwe TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_refs_src ON refs(src)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_endpoints_file ON api_endpoints(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sql_file ON sql_objects(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_path ON symbols(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sql_queries_file ON sql_queries(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sql_queries_command ON sql_queries(command)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docker_images_base ON docker_images(base_image)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orm_queries_file ON orm_queries(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orm_queries_type ON orm_queries(query_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prisma_models_indexed ON prisma_models(is_indexed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compose_services_file ON compose_services(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_compose_services_privileged ON compose_services(is_privileged)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nginx_configs_file ON nginx_configs(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nginx_configs_type ON nginx_configs(block_type)")
        
        # Indexes for data flow tables
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_file ON assignments(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_function ON assignments(in_function)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_target ON assignments(target_var)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_call_args_file ON function_call_args(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_call_args_caller ON function_call_args(caller_function)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_call_args_callee ON function_call_args(callee_function)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_call_args_file_line ON function_call_args(file, line)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_returns_file ON function_returns(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_returns_function ON function_returns(function_name)")
        
        # Indexes for CFG tables
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cfg_blocks_file ON cfg_blocks(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cfg_blocks_function ON cfg_blocks(function_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cfg_edges_file ON cfg_edges(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cfg_edges_function ON cfg_edges(function_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cfg_edges_source ON cfg_edges(source_block_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cfg_edges_target ON cfg_edges(target_block_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cfg_statements_block ON cfg_block_statements(block_id)")

        # Indexes for React tables
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_react_components_file ON react_components(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_react_components_name ON react_components(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_react_hooks_file ON react_hooks(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_react_hooks_component ON react_hooks(component_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_react_hooks_name ON react_hooks(hook_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_variable_usage_file ON variable_usage(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_variable_usage_component ON variable_usage(in_component)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_variable_usage_var ON variable_usage(variable_name)")

        # Indexes for JSX tables
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jsx_returns_file ON function_returns_jsx(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jsx_returns_function ON function_returns_jsx(function_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jsx_symbols_path ON symbols_jsx(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jsx_symbols_type ON symbols_jsx(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jsx_assignments_file ON assignments_jsx(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jsx_assignments_function ON assignments_jsx(in_function)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jsx_calls_file ON function_call_args_jsx(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jsx_calls_caller ON function_call_args_jsx(caller_function)")

        # Indexes for Vue tables
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vue_components_file ON vue_components(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vue_components_name ON vue_components(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vue_components_type ON vue_components(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vue_hooks_file ON vue_hooks(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vue_hooks_component ON vue_hooks(component_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vue_hooks_type ON vue_hooks(hook_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vue_directives_file ON vue_directives(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vue_directives_name ON vue_directives(directive_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vue_provide_inject_file ON vue_provide_inject(file)")

        # Indexes for TypeScript type annotations
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_type_annotations_file ON type_annotations(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_type_annotations_any ON type_annotations(file, is_any)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_type_annotations_unknown ON type_annotations(file, is_unknown)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_type_annotations_generic ON type_annotations(file, is_generic)")

        # Indexes for build analysis tables
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_package_configs_file ON package_configs(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lock_analysis_file ON lock_analysis(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lock_analysis_type ON lock_analysis(lock_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_styles_file ON import_styles(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_styles_package ON import_styles(package)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_import_styles_style ON import_styles(import_style)")

        # Indexes for findings_consolidated table (dual-write pattern for FCE performance)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_findings_file_line ON findings_consolidated(file, line)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_findings_tool ON findings_consolidated(tool)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings_consolidated(severity)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_findings_rule ON findings_consolidated(rule)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_findings_category ON findings_consolidated(category)")

        # Migration: Add type_annotation column to symbols table if it doesn't exist
        try:
            cursor.execute("ALTER TABLE symbols ADD COLUMN type_annotation TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE symbols ADD COLUMN is_typed BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add extraction_source column to sql_queries table (Phase 3B)
        try:
            cursor.execute("ALTER TABLE sql_queries ADD COLUMN extraction_source TEXT DEFAULT 'code_execute'")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add file_category column to files table (Phase 3B)
        try:
            cursor.execute("ALTER TABLE files ADD COLUMN file_category TEXT DEFAULT 'source'")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add 9 security fields to compose_services table (Phase 3C)
        # Security-critical fields (P0 priority)
        try:
            cursor.execute("ALTER TABLE compose_services ADD COLUMN user TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE compose_services ADD COLUMN cap_add TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE compose_services ADD COLUMN cap_drop TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE compose_services ADD COLUMN security_opt TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Operational fields (P1/P2 priority)
        try:
            cursor.execute("ALTER TABLE compose_services ADD COLUMN restart TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE compose_services ADD COLUMN command TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE compose_services ADD COLUMN entrypoint TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE compose_services ADD COLUMN depends_on TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute("ALTER TABLE compose_services ADD COLUMN healthcheck TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        self.conn.commit()

    def clear_tables(self):
        """Clear all existing data from tables."""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("DELETE FROM files")
            cursor.execute("DELETE FROM refs")
            cursor.execute("DELETE FROM api_endpoints")
            cursor.execute("DELETE FROM sql_objects")
            cursor.execute("DELETE FROM symbols")
            cursor.execute("DELETE FROM sql_queries")
            cursor.execute("DELETE FROM docker_images")
            cursor.execute("DELETE FROM orm_queries")
            cursor.execute("DELETE FROM prisma_models")
            cursor.execute("DELETE FROM compose_services")
            cursor.execute("DELETE FROM nginx_configs")
            cursor.execute("DELETE FROM assignments")
            cursor.execute("DELETE FROM function_call_args")
            cursor.execute("DELETE FROM function_returns")
            cursor.execute("DELETE FROM cfg_blocks")
            cursor.execute("DELETE FROM cfg_edges")
            cursor.execute("DELETE FROM cfg_block_statements")
            cursor.execute("DELETE FROM react_components")
            cursor.execute("DELETE FROM react_hooks")
            cursor.execute("DELETE FROM variable_usage")
            # Also clear JSX tables
            cursor.execute("DELETE FROM function_returns_jsx")
            cursor.execute("DELETE FROM symbols_jsx")
            cursor.execute("DELETE FROM assignments_jsx")
            cursor.execute("DELETE FROM function_call_args_jsx")
            # Also clear Vue tables
            cursor.execute("DELETE FROM vue_components")
            cursor.execute("DELETE FROM vue_hooks")
            cursor.execute("DELETE FROM vue_directives")
            cursor.execute("DELETE FROM vue_provide_inject")
            # Also clear type annotations
            cursor.execute("DELETE FROM type_annotations")
            # Also clear build analysis tables
            cursor.execute("DELETE FROM package_configs")
            cursor.execute("DELETE FROM lock_analysis")
            cursor.execute("DELETE FROM import_styles")
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to clear existing data: {e}")

    def add_file(self, path: str, sha256: str, ext: str, bytes_size: int, loc: int):
        """Add a file record to the batch.

        Deduplicates paths to prevent UNIQUE constraint violations.
        This can happen with symlinks, junction points, or case sensitivity issues.
        """
        # Check if path already in current batch (O(n) but batches are small)
        if not any(item[0] == path for item in self.files_batch):
            self.files_batch.append((path, sha256, ext, bytes_size, loc))

    def add_ref(self, src: str, kind: str, value: str):
        """Add a reference record to the batch."""
        self.refs_batch.append((src, kind, value))

    def add_endpoint(self, file_path: str, method: str, pattern: str, controls: List[str],
                     line: Optional[int] = None, path: Optional[str] = None,
                     has_auth: bool = False, handler_function: Optional[str] = None):
        """Add an API endpoint record to the batch."""
        controls_json = json.dumps(controls) if controls else "[]"
        self.endpoints_batch.append((file_path, line, method, pattern, path,
                                    controls_json, has_auth, handler_function))

    def add_sql_object(self, file_path: str, kind: str, name: str):
        """Add a SQL object record to the batch."""
        self.sql_objects_batch.append((file_path, kind, name))

    def add_sql_query(self, file_path: str, line: int, query_text: str, command: str, tables: List[str],
                      extraction_source: str = 'code_execute'):
        """Add a SQL query record to the batch.

        Args:
            file_path: Path to the file containing the query
            line: Line number
            query_text: SQL query text
            command: SQL command type (SELECT, INSERT, etc.)
            tables: List of table names referenced
            extraction_source: Source of extraction - one of:
                - 'code_execute': Direct db.execute() calls (HIGH priority for SQL injection)
                - 'orm_query': ORM method calls (MEDIUM priority, usually parameterized)
                - 'migration_file': Database migration files (LOW priority, DDL only)
        """
        tables_json = json.dumps(tables) if tables else "[]"
        self.sql_queries_batch.append((file_path, line, query_text, command, tables_json, extraction_source))

    def add_symbol(self, path: str, name: str, symbol_type: str, line: int, col: int):
        """Add a symbol record to the batch."""
        self.symbols_batch.append((path, name, symbol_type, line, col))

    def add_orm_query(self, file_path: str, line: int, query_type: str, includes: Optional[str],
                      has_limit: bool, has_transaction: bool):
        """Add an ORM query record to the batch."""
        self.orm_queries_batch.append((file_path, line, query_type, includes, has_limit, has_transaction))

    def add_docker_image(self, file_path: str, base_image: Optional[str], exposed_ports: List[str],
                        env_vars: Dict, build_args: Dict, user: Optional[str], has_healthcheck: bool):
        """Add a Docker image record to the batch."""
        ports_json = json.dumps(exposed_ports)
        env_json = json.dumps(env_vars)
        args_json = json.dumps(build_args)
        self.docker_images_batch.append((file_path, base_image, ports_json, env_json, 
                                        args_json, user, has_healthcheck))

    def add_assignment(self, file_path: str, line: int, target_var: str, source_expr: str,
                      source_vars: List[str], in_function: str):
        """Add a variable assignment record to the batch."""
        source_vars_json = json.dumps(source_vars)
        self.assignments_batch.append((file_path, line, target_var, source_expr, 
                                      source_vars_json, in_function))

    def add_function_call_arg(self, file_path: str, line: int, caller_function: str,
                              callee_function: str, arg_index: int, arg_expr: str, param_name: str):
        """Add a function call argument record to the batch."""
        self.function_call_args_batch.append((file_path, line, caller_function, callee_function,
                                             arg_index, arg_expr, param_name))

    def add_function_return(self, file_path: str, line: int, function_name: str,
                           return_expr: str, return_vars: List[str]):
        """Add a function return statement record to the batch."""
        return_vars_json = json.dumps(return_vars)
        self.function_returns_batch.append((file_path, line, function_name, 
                                           return_expr, return_vars_json))

    def add_config_file(self, path: str, content: str, file_type: str, context: Optional[str] = None):
        """Add a configuration file content to the batch."""
        if not hasattr(self, 'config_files_batch'):
            self.config_files_batch = []
        self.config_files_batch.append((path, content, file_type, context))

    def add_prisma_model(self, model_name: str, field_name: str, field_type: str,
                        is_indexed: bool, is_unique: bool, is_relation: bool):
        """Add a Prisma model field record to the batch."""
        self.prisma_batch.append((model_name, field_name, field_type, 
                                 is_indexed, is_unique, is_relation))

    def add_compose_service(self, file_path: str, service_name: str, image: Optional[str],
                           ports: List[str], volumes: List[str], environment: Dict,
                           is_privileged: bool, network_mode: str,
                           # 9 new security fields (Phase 3C)
                           user: Optional[str] = None,
                           cap_add: Optional[List[str]] = None,
                           cap_drop: Optional[List[str]] = None,
                           security_opt: Optional[List[str]] = None,
                           restart: Optional[str] = None,
                           command: Optional[List[str]] = None,
                           entrypoint: Optional[List[str]] = None,
                           depends_on: Optional[List[str]] = None,
                           healthcheck: Optional[Dict] = None):
        """Add a Docker Compose service record to the batch.

        Args:
            file_path: Path to docker-compose.yml
            service_name: Name of the service
            image: Docker image name
            ports: List of port mappings
            volumes: List of volume mounts
            environment: Dictionary of environment variables
            is_privileged: Whether service runs in privileged mode
            network_mode: Network mode (bridge, host, etc.)
            user: User/UID to run as (security: detect root)
            cap_add: Linux capabilities to add (security: detect dangerous caps)
            cap_drop: Linux capabilities to drop (security: enforce hardening)
            security_opt: Security options (security: detect disabled AppArmor/SELinux)
            restart: Restart policy (operational: availability)
            command: Override CMD instruction (security: command injection risk)
            entrypoint: Override ENTRYPOINT instruction (security: tampering)
            depends_on: Service dependencies (operational: dependency graph)
            healthcheck: Health check configuration (operational: availability)
        """
        ports_json = json.dumps(ports)
        volumes_json = json.dumps(volumes)
        env_json = json.dumps(environment)

        # Encode new fields as JSON (or None if not provided)
        cap_add_json = json.dumps(cap_add) if cap_add else None
        cap_drop_json = json.dumps(cap_drop) if cap_drop else None
        security_opt_json = json.dumps(security_opt) if security_opt else None
        command_json = json.dumps(command) if command else None
        entrypoint_json = json.dumps(entrypoint) if entrypoint else None
        depends_on_json = json.dumps(depends_on) if depends_on else None
        healthcheck_json = json.dumps(healthcheck) if healthcheck else None

        self.compose_batch.append((
            file_path, service_name, image, ports_json, volumes_json, env_json,
            is_privileged, network_mode,
            # 9 new fields
            user, cap_add_json, cap_drop_json, security_opt_json,
            restart, command_json, entrypoint_json, depends_on_json, healthcheck_json
        ))

    def add_nginx_config(self, file_path: str, block_type: str, block_context: str,
                        directives: Dict, level: int):
        """Add an Nginx configuration block to the batch."""
        directives_json = json.dumps(directives)
        # Use a default context if empty to avoid primary key issues
        block_context = block_context or 'default'
        
        # Check for duplicates before adding
        batch_key = (file_path, block_type, block_context)
        if not any(b[:3] == batch_key for b in self.nginx_batch):
            self.nginx_batch.append((file_path, block_type, block_context,
                                   directives_json, level))

    def add_cfg_block(self, file_path: str, function_name: str, block_type: str,
                     start_line: int, end_line: int, condition_expr: Optional[str] = None) -> int:
        """Add a CFG block to the batch and return its temporary ID.
        
        Note: Since we use AUTOINCREMENT, we need to handle IDs carefully.
        This returns a temporary ID that will be replaced during flush.
        """
        # Generate temporary ID (negative to distinguish from real IDs)
        temp_id = -(len(self.cfg_blocks_batch) + 1)
        self.cfg_blocks_batch.append((file_path, function_name, block_type,
                                     start_line, end_line, condition_expr, temp_id))
        return temp_id

    def add_cfg_edge(self, file_path: str, function_name: str, source_block_id: int,
                    target_block_id: int, edge_type: str):
        """Add a CFG edge to the batch."""
        self.cfg_edges_batch.append((file_path, function_name, source_block_id,
                                    target_block_id, edge_type))

    def add_cfg_statement(self, block_id: int, statement_type: str, line: int,
                         statement_text: Optional[str] = None):
        """Add a CFG block statement to the batch."""
        self.cfg_statements_batch.append((block_id, statement_type, line, statement_text))

    def add_react_component(self, file_path: str, name: str, component_type: str,
                           start_line: int, end_line: int, has_jsx: bool,
                           hooks_used: Optional[List[str]] = None,
                           props_type: Optional[str] = None):
        """Add a React component to the batch."""
        hooks_json = json.dumps(hooks_used) if hooks_used else None
        self.react_components_batch.append((file_path, name, component_type,
                                           start_line, end_line, has_jsx,
                                           hooks_json, props_type))

    def add_react_hook(self, file_path: str, line: int, component_name: str,
                      hook_name: str, dependency_array: Optional[List[str]] = None,
                      dependency_vars: Optional[List[str]] = None,
                      callback_body: Optional[str] = None, has_cleanup: bool = False,
                      cleanup_type: Optional[str] = None):
        """Add a React hook usage to the batch."""
        deps_array_json = json.dumps(dependency_array) if dependency_array is not None else None
        deps_vars_json = json.dumps(dependency_vars) if dependency_vars else None
        # Limit callback body to 500 chars
        if callback_body and len(callback_body) > 500:
            callback_body = callback_body[:497] + '...'
        self.react_hooks_batch.append((file_path, line, component_name, hook_name,
                                      deps_array_json, deps_vars_json, callback_body,
                                      has_cleanup, cleanup_type))

    def add_variable_usage(self, file_path: str, line: int, variable_name: str,
                          usage_type: str, in_component: Optional[str] = None,
                          in_hook: Optional[str] = None, scope_level: int = 0):
        """Add a variable usage record to the batch."""
        self.variable_usage_batch.append((file_path, line, variable_name, usage_type,
                                         in_component or '', in_hook or '', scope_level))

    # ========================================================
    # JSX-SPECIFIC BATCH METHODS FOR DUAL-PASS EXTRACTION
    # ========================================================

    def add_function_return_jsx(self, file_path: str, line: int, function_name: str,
                                return_expr: str, return_vars: List[str], has_jsx: bool = False,
                                returns_component: bool = False, cleanup_operations: Optional[str] = None,
                                jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX function return record for preserved JSX extraction."""
        return_vars_json = json.dumps(return_vars)
        self.function_returns_jsx_batch.append((file_path, line, function_name, return_expr,
                                                return_vars_json, has_jsx, returns_component,
                                                cleanup_operations, jsx_mode, extraction_pass))

    def add_symbol_jsx(self, path: str, name: str, symbol_type: str, line: int, col: int,
                      jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX symbol record for preserved JSX extraction."""
        self.symbols_jsx_batch.append((path, name, symbol_type, line, col, jsx_mode, extraction_pass))

    def add_assignment_jsx(self, file_path: str, line: int, target_var: str, source_expr: str,
                          source_vars: List[str], in_function: str, jsx_mode: str = 'preserved',
                          extraction_pass: int = 1):
        """Add a JSX assignment record for preserved JSX extraction."""
        source_vars_json = json.dumps(source_vars)
        self.assignments_jsx_batch.append((file_path, line, target_var, source_expr,
                                          source_vars_json, in_function, jsx_mode, extraction_pass))

    def add_function_call_arg_jsx(self, file_path: str, line: int, caller_function: str,
                                  callee_function: str, arg_index: int, arg_expr: str, param_name: str,
                                  jsx_mode: str = 'preserved', extraction_pass: int = 1):
        """Add a JSX function call argument record for preserved JSX extraction."""
        self.function_call_args_jsx_batch.append((file_path, line, caller_function, callee_function,
                                                  arg_index, arg_expr, param_name, jsx_mode, extraction_pass))

    # ========================================================
    # VUE-SPECIFIC BATCH METHODS FOR FRAMEWORK ANALYSIS
    # ========================================================

    def add_vue_component(self, file_path: str, name: str, component_type: str,
                         start_line: int, end_line: int, has_template: bool = False,
                         has_style: bool = False, composition_api_used: bool = False,
                         props_definition: Optional[Dict] = None,
                         emits_definition: Optional[Dict] = None,
                         setup_return: Optional[str] = None):
        """Add a Vue component to the batch."""
        props_json = json.dumps(props_definition) if props_definition else None
        emits_json = json.dumps(emits_definition) if emits_definition else None
        self.vue_components_batch.append((file_path, name, component_type,
                                         start_line, end_line, has_template, has_style,
                                         composition_api_used, props_json, emits_json,
                                         setup_return))

    def add_vue_hook(self, file_path: str, line: int, component_name: str,
                    hook_name: str, hook_type: str, dependencies: Optional[List[str]] = None,
                    return_value: Optional[str] = None, is_async: bool = False):
        """Add a Vue hook/reactivity usage to the batch."""
        deps_json = json.dumps(dependencies) if dependencies else None
        self.vue_hooks_batch.append((file_path, line, component_name, hook_name,
                                    hook_type, deps_json, return_value, is_async))

    def add_vue_directive(self, file_path: str, line: int, directive_name: str,
                         expression: str, in_component: str, has_key: bool = False,
                         modifiers: Optional[List[str]] = None):
        """Add a Vue directive usage to the batch."""
        modifiers_json = json.dumps(modifiers) if modifiers else None
        self.vue_directives_batch.append((file_path, line, directive_name, expression,
                                         in_component, has_key, modifiers_json))

    def add_vue_provide_inject(self, file_path: str, line: int, component_name: str,
                              operation_type: str, key_name: str, value_expr: Optional[str] = None,
                              is_reactive: bool = False):
        """Add a Vue provide/inject operation to the batch."""
        self.vue_provide_inject_batch.append((file_path, line, component_name,
                                             operation_type, key_name, value_expr, is_reactive))

    def add_type_annotation(self, file_path: str, line: int, column: int, symbol_name: str,
                           symbol_kind: str, type_annotation: str = None, is_any: bool = False,
                           is_unknown: bool = False, is_generic: bool = False,
                           has_type_params: bool = False, type_params: str = None,
                           return_type: str = None, extends_type: str = None):
        """Add a TypeScript type annotation record to the batch."""
        self.type_annotations_batch.append((file_path, line, column, symbol_name, symbol_kind,
                                           type_annotation, is_any, is_unknown, is_generic,
                                           has_type_params, type_params, return_type, extends_type))

    def add_package_config(self, file_path: str, package_name: str, version: str,
                          dependencies: Optional[Dict], dev_dependencies: Optional[Dict],
                          peer_dependencies: Optional[Dict], scripts: Optional[Dict],
                          engines: Optional[Dict], workspaces: Optional[List],
                          is_private: bool = False):
        """Add a package.json configuration to the batch."""
        deps_json = json.dumps(dependencies) if dependencies else None
        dev_deps_json = json.dumps(dev_dependencies) if dev_dependencies else None
        peer_deps_json = json.dumps(peer_dependencies) if peer_dependencies else None
        scripts_json = json.dumps(scripts) if scripts else None
        engines_json = json.dumps(engines) if engines else None
        workspaces_json = json.dumps(workspaces) if workspaces else None

        self.package_configs_batch.append((file_path, package_name, version,
                                          deps_json, dev_deps_json, peer_deps_json,
                                          scripts_json, engines_json, workspaces_json,
                                          is_private))

    def add_lock_analysis(self, file_path: str, lock_type: str,
                         package_manager_version: Optional[str],
                         total_packages: int, duplicate_packages: Optional[Dict],
                         lock_file_version: Optional[str]):
        """Add a lock file analysis result to the batch."""
        duplicates_json = json.dumps(duplicate_packages) if duplicate_packages else None

        self.lock_analysis_batch.append((file_path, lock_type, package_manager_version,
                                        total_packages, duplicates_json, lock_file_version))

    def add_import_style(self, file_path: str, line: int, package: str,
                        import_style: str, imported_names: Optional[List[str]] = None,
                        alias_name: Optional[str] = None, full_statement: Optional[str] = None):
        """Add an import style record to the batch."""
        names_json = json.dumps(imported_names) if imported_names else None

        self.import_styles_batch.append((file_path, line, package, import_style,
                                        names_json, alias_name, full_statement))

    def add_framework(self, name, version, language, path, source, is_primary=False):
        """Add framework to batch."""
        # Skip if no name provided
        if not name:
            return
        self.frameworks_batch.append((name, version, language, path, source, is_primary))
        if len(self.frameworks_batch) >= self.batch_size:
            self.flush_batch()

    def add_framework_safe_sink(self, framework_id, pattern, sink_type, is_safe, reason):
        """Add framework safe sink to batch."""
        self.framework_safe_sinks_batch.append((framework_id, pattern, sink_type, is_safe, reason))
        if len(self.framework_safe_sinks_batch) >= self.batch_size:
            self.flush_batch()

    def write_findings_batch(self, findings: List[dict], tool_name: str):
        """Write findings to database using batch insert for dual-write pattern.

        This method implements the dual-write architecture where findings are written
        to BOTH the database (for FCE performance) AND JSON files (for AI consumption).

        Args:
            findings: List of finding dicts from any tool (patterns, taint, lint, etc.)
            tool_name: Name of the tool that generated findings (e.g., 'patterns', 'taint')

        Notes:
            - Normalizes findings to standard format (handles different field names)
            - Uses batch inserts for performance (batch_size from config)
            - Automatically commits after all batches complete
            - Optional fields (column, cwe, confidence) are gracefully handled
        """
        if not findings:
            return

        from datetime import datetime, UTC

        cursor = self.conn.cursor()

        # Normalize findings to standard format
        normalized = []
        for f in findings:
            # Handle different finding formats from various tools
            # Try multiple field names for compatibility
            normalized.append((
                f.get('file', ''),
                int(f.get('line', 0)),
                f.get('column'),  # Optional
                f.get('rule', f.get('pattern', f.get('pattern_name', f.get('code', 'unknown')))),  # Try multiple names
                f.get('tool', tool_name),
                f.get('message', ''),
                f.get('severity', 'medium'),  # Default to medium if not specified
                f.get('category'),  # Optional
                f.get('confidence'),  # Optional
                f.get('code_snippet'),  # Optional
                f.get('cwe'),  # Optional
                f.get('timestamp', datetime.now(UTC).isoformat())
            ))

        # Batch insert using configured batch size for performance
        for i in range(0, len(normalized), self.batch_size):
            batch = normalized[i:i+self.batch_size]
            cursor.executemany(
                """INSERT INTO findings_consolidated
                   (file, line, column, rule, tool, message, severity, category,
                    confidence, code_snippet, cwe, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                batch
            )

        # Commit immediately for findings (not part of normal batch cycle)
        self.conn.commit()

        # Debug logging if enabled
        if hasattr(self, '_debug') and self._debug:
            print(f"[DB] Wrote {len(findings)} findings from {tool_name} to findings_consolidated")

    def get_framework_id(self, name, language):
        """Get framework ID from database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM frameworks WHERE name = ? AND language = ?", (name, language))
        result = cursor.fetchone()
        return result[0] if result else None

    def flush_batch(self, batch_idx: Optional[int] = None):
        """Execute all pending batch inserts."""
        cursor = self.conn.cursor()
        
        try:
            if self.files_batch:
                # Use INSERT OR REPLACE to handle duplicates gracefully
                # This can occur with symlinks, junction points, or processing the same file twice
                cursor.executemany(
                    "INSERT OR REPLACE INTO files (path, sha256, ext, bytes, loc) VALUES (?, ?, ?, ?, ?)",
                    self.files_batch
                )
                self.files_batch = []
            
            if self.refs_batch:
                cursor.executemany(
                    "INSERT INTO refs (src, kind, value) VALUES (?, ?, ?)",
                    self.refs_batch
                )
                self.refs_batch = []
            
            if self.endpoints_batch:
                cursor.executemany(
                    "INSERT INTO api_endpoints (file, line, method, pattern, path, controls, has_auth, handler_function) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    self.endpoints_batch
                )
                self.endpoints_batch = []
            
            if self.sql_objects_batch:
                cursor.executemany(
                    "INSERT INTO sql_objects (file, kind, name) VALUES (?, ?, ?)",
                    self.sql_objects_batch
                )
                self.sql_objects_batch = []
            
            if self.sql_queries_batch:
                cursor.executemany(
                    "INSERT INTO sql_queries (file_path, line_number, query_text, command, tables, extraction_source) VALUES (?, ?, ?, ?, ?, ?)",
                    self.sql_queries_batch
                )
                self.sql_queries_batch = []
            
            if self.symbols_batch:
                cursor.executemany(
                    "INSERT INTO symbols (path, name, type, line, col) VALUES (?, ?, ?, ?, ?)",
                    self.symbols_batch
                )
                self.symbols_batch = []
            
            if self.orm_queries_batch:
                cursor.executemany(
                    "INSERT INTO orm_queries (file, line, query_type, includes, has_limit, has_transaction) VALUES (?, ?, ?, ?, ?, ?)",
                    self.orm_queries_batch
                )
                self.orm_queries_batch = []
            
            if self.docker_images_batch:
                cursor.executemany(
                    "INSERT INTO docker_images (file_path, base_image, exposed_ports, env_vars, build_args, user, has_healthcheck) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    self.docker_images_batch
                )
                self.docker_images_batch = []

            if self.assignments_batch:
                cursor.executemany(
                    "INSERT INTO assignments (file, line, target_var, source_expr, source_vars, in_function) VALUES (?, ?, ?, ?, ?, ?)",
                    self.assignments_batch
                )
                self.assignments_batch = []
            
            if self.function_call_args_batch:
                cursor.executemany(
                    "INSERT INTO function_call_args (file, line, caller_function, callee_function, argument_index, argument_expr, param_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    self.function_call_args_batch
                )
                self.function_call_args_batch = []
            
            if self.function_returns_batch:
                cursor.executemany(
                    "INSERT INTO function_returns (file, line, function_name, return_expr, return_vars) VALUES (?, ?, ?, ?, ?)",
                    self.function_returns_batch
                )
                self.function_returns_batch = []
            
            if self.prisma_batch:
                cursor.executemany(
                    """INSERT INTO prisma_models 
                       (model_name, field_name, field_type, is_indexed, is_unique, is_relation) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    self.prisma_batch
                )
                self.prisma_batch = []
            
            if self.compose_batch:
                cursor.executemany(
                    """INSERT INTO compose_services
                       (file_path, service_name, image, ports, volumes, environment,
                        is_privileged, network_mode, user, cap_add, cap_drop, security_opt,
                        restart, command, entrypoint, depends_on, healthcheck)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.compose_batch
                )
                self.compose_batch = []
            
            if self.nginx_batch:
                cursor.executemany(
                    """INSERT INTO nginx_configs 
                       (file_path, block_type, block_context, directives, level) 
                       VALUES (?, ?, ?, ?, ?)""",
                    self.nginx_batch
                )
                self.nginx_batch = []
            
            if hasattr(self, 'config_files_batch') and self.config_files_batch:
                cursor.executemany(
                    "INSERT OR REPLACE INTO config_files (path, content, type, context_dir) VALUES (?, ?, ?, ?)",
                    self.config_files_batch
                )
                self.config_files_batch = []
            
            # Handle CFG blocks with ID mapping (blocks must be inserted before edges/statements)
            if self.cfg_blocks_batch:
                # Map temporary IDs to real IDs
                id_mapping = {}
                
                for batch_item in self.cfg_blocks_batch:
                    # Extract temp_id from the batch item (last element)
                    file_path, function_name, block_type, start_line, end_line, condition_expr, temp_id = batch_item
                    
                    cursor.execute(
                        """INSERT INTO cfg_blocks (file, function_name, block_type, start_line, end_line, condition_expr) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (file_path, function_name, block_type, start_line, end_line, condition_expr)
                    )
                    # Map the temporary ID to the real ID
                    real_id = cursor.lastrowid
                    id_mapping[temp_id] = real_id
                
                self.cfg_blocks_batch = []
                
                # Update edges with real IDs
                if self.cfg_edges_batch:
                    updated_edges = []
                    for file_path, function_name, source_id, target_id, edge_type in self.cfg_edges_batch:
                        # Map temporary IDs to real IDs
                        real_source = id_mapping.get(source_id, source_id) if source_id < 0 else source_id
                        real_target = id_mapping.get(target_id, target_id) if target_id < 0 else target_id
                        updated_edges.append((file_path, function_name, real_source, real_target, edge_type))
                    
                    cursor.executemany(
                        """INSERT INTO cfg_edges (file, function_name, source_block_id, target_block_id, edge_type) 
                           VALUES (?, ?, ?, ?, ?)""",
                        updated_edges
                    )
                    self.cfg_edges_batch = []
                
                # Update statements with real IDs
                if self.cfg_statements_batch:
                    updated_statements = []
                    for block_id, statement_type, line, statement_text in self.cfg_statements_batch:
                        # Map temporary ID to real ID
                        real_block_id = id_mapping.get(block_id, block_id) if block_id < 0 else block_id
                        updated_statements.append((real_block_id, statement_type, line, statement_text))
                    
                    cursor.executemany(
                        """INSERT INTO cfg_block_statements (block_id, statement_type, line, statement_text) 
                           VALUES (?, ?, ?, ?)""",
                        updated_statements
                    )
                    self.cfg_statements_batch = []

            # Handle React data batches
            if self.react_components_batch:
                cursor.executemany(
                    """INSERT INTO react_components
                       (file, name, type, start_line, end_line, has_jsx, hooks_used, props_type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.react_components_batch
                )
                self.react_components_batch = []

            if self.react_hooks_batch:
                cursor.executemany(
                    """INSERT INTO react_hooks
                       (file, line, component_name, hook_name, dependency_array, dependency_vars,
                        callback_body, has_cleanup, cleanup_type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.react_hooks_batch
                )
                self.react_hooks_batch = []

            if self.variable_usage_batch:
                cursor.executemany(
                    """INSERT INTO variable_usage
                       (file, line, variable_name, usage_type, in_component, in_hook, scope_level)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    self.variable_usage_batch
                )
                self.variable_usage_batch = []

            # Handle JSX-specific batches for dual-pass extraction
            if self.function_returns_jsx_batch:
                cursor.executemany(
                    """INSERT OR REPLACE INTO function_returns_jsx
                       (file, line, function_name, return_expr, return_vars, has_jsx, returns_component,
                        cleanup_operations, jsx_mode, extraction_pass)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.function_returns_jsx_batch
                )
                self.function_returns_jsx_batch = []

            if self.symbols_jsx_batch:
                cursor.executemany(
                    """INSERT OR REPLACE INTO symbols_jsx
                       (path, name, type, line, col, jsx_mode, extraction_pass)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    self.symbols_jsx_batch
                )
                self.symbols_jsx_batch = []

            if self.assignments_jsx_batch:
                cursor.executemany(
                    """INSERT OR REPLACE INTO assignments_jsx
                       (file, line, target_var, source_expr, source_vars, in_function, jsx_mode, extraction_pass)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.assignments_jsx_batch
                )
                self.assignments_jsx_batch = []

            if self.function_call_args_jsx_batch:
                cursor.executemany(
                    """INSERT OR REPLACE INTO function_call_args_jsx
                       (file, line, caller_function, callee_function, argument_index, argument_expr,
                        param_name, jsx_mode, extraction_pass)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.function_call_args_jsx_batch
                )
                self.function_call_args_jsx_batch = []

            # Handle Vue-specific batches for framework analysis
            if self.vue_components_batch:
                cursor.executemany(
                    """INSERT INTO vue_components
                       (file, name, type, start_line, end_line, has_template, has_style,
                        composition_api_used, props_definition, emits_definition, setup_return)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.vue_components_batch
                )
                self.vue_components_batch = []

            if self.vue_hooks_batch:
                cursor.executemany(
                    """INSERT INTO vue_hooks
                       (file, line, component_name, hook_name, hook_type, dependencies,
                        return_value, is_async)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.vue_hooks_batch
                )
                self.vue_hooks_batch = []

            if self.vue_directives_batch:
                cursor.executemany(
                    """INSERT INTO vue_directives
                       (file, line, directive_name, expression, in_component, has_key, modifiers)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    self.vue_directives_batch
                )
                self.vue_directives_batch = []

            if self.vue_provide_inject_batch:
                cursor.executemany(
                    """INSERT INTO vue_provide_inject
                       (file, line, component_name, operation_type, key_name, value_expr, is_reactive)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    self.vue_provide_inject_batch
                )
                self.vue_provide_inject_batch = []

            # Handle TypeScript type annotations
            if self.type_annotations_batch:
                cursor.executemany(
                    """INSERT OR REPLACE INTO type_annotations
                       (file, line, column, symbol_name, symbol_kind, type_annotation,
                        is_any, is_unknown, is_generic, has_type_params, type_params,
                        return_type, extends_type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.type_annotations_batch
                )
                self.type_annotations_batch = []

            # Framework detection tables
            if self.frameworks_batch:
                cursor.executemany(
                    """INSERT OR IGNORE INTO frameworks (name, version, language, path, source, is_primary)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    self.frameworks_batch
                )
                self.frameworks_batch = []

            if self.framework_safe_sinks_batch:
                cursor.executemany(
                    """INSERT OR IGNORE INTO framework_safe_sinks (framework_id, sink_pattern, sink_type, is_safe, reason)
                       VALUES (?, ?, ?, ?, ?)""",
                    self.framework_safe_sinks_batch
                )
                self.framework_safe_sinks_batch = []

            # Handle build analysis batches
            if self.package_configs_batch:
                cursor.executemany(
                    """INSERT OR REPLACE INTO package_configs
                       (file_path, package_name, version, dependencies, dev_dependencies,
                        peer_dependencies, scripts, engines, workspaces, private)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.package_configs_batch
                )
                self.package_configs_batch = []

            if self.lock_analysis_batch:
                cursor.executemany(
                    """INSERT OR REPLACE INTO lock_analysis
                       (file_path, lock_type, package_manager_version, total_packages,
                        duplicate_packages, lock_file_version)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    self.lock_analysis_batch
                )
                self.lock_analysis_batch = []

            if self.import_styles_batch:
                cursor.executemany(
                    """INSERT INTO import_styles
                       (file, line, package, import_style, imported_names, alias_name, full_statement)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    self.import_styles_batch
                )
                self.import_styles_batch = []

            # Handle edges and statements without blocks (shouldn't happen, but be safe)
            elif self.cfg_edges_batch:
                cursor.executemany(
                    """INSERT INTO cfg_edges (file, function_name, source_block_id, target_block_id, edge_type) 
                       VALUES (?, ?, ?, ?, ?)""",
                    self.cfg_edges_batch
                )
                self.cfg_edges_batch = []
            
            elif self.cfg_statements_batch:
                cursor.executemany(
                    """INSERT INTO cfg_block_statements (block_id, statement_type, line, statement_text) 
                       VALUES (?, ?, ?, ?)""",
                    self.cfg_statements_batch
                )
                self.cfg_statements_batch = []
                
        except sqlite3.Error as e:
            if batch_idx is not None:
                raise RuntimeError(f"Batch insert failed at file index {batch_idx}: {e}")
            else:
                raise RuntimeError(f"Batch insert failed: {e}")


# Standalone function for backward compatibility
def create_database_schema(conn: sqlite3.Connection) -> None:
    """Create SQLite database schema - backward compatibility wrapper.
    
    Args:
        conn: SQLite connection (remains open after schema creation)
    """
    # Use the existing connection to create schema
    manager = DatabaseManager.__new__(DatabaseManager)
    manager.conn = conn
    manager.cursor = conn.cursor()
    manager.batch_size = 200
    
    # Initialize batch lists
    manager.files_batch = []
    manager.refs_batch = []
    manager.endpoints_batch = []
    manager.sql_objects_batch = []
    manager.sql_queries_batch = []
    manager.symbols_batch = []
    manager.orm_queries_batch = []
    manager.docker_images_batch = []
    manager.assignments_batch = []
    manager.function_call_args_batch = []
    manager.function_returns_batch = []
    manager.prisma_batch = []
    manager.compose_batch = []
    manager.nginx_batch = []
    manager.cfg_blocks_batch = []
    manager.cfg_edges_batch = []
    manager.cfg_statements_batch = []
    manager.react_components_batch = []
    manager.react_hooks_batch = []
    manager.variable_usage_batch = []
    manager.function_returns_jsx_batch = []
    manager.symbols_jsx_batch = []
    manager.assignments_jsx_batch = []
    manager.function_call_args_jsx_batch = []
    manager.vue_components_batch = []
    manager.vue_hooks_batch = []
    manager.vue_directives_batch = []
    manager.vue_provide_inject_batch = []
    manager.type_annotations_batch = []
    manager.package_configs_batch = []
    manager.lock_analysis_batch = []
    manager.import_styles_batch = []

    # Create the schema using the existing connection
    manager.create_schema()
    # Don't close - let caller handle connection lifecycle