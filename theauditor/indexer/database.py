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
        self.docker_issues_batch = []
        self.assignments_batch = []
        self.function_call_args_batch = []
        self.function_returns_batch = []
        self.prisma_batch = []
        self.compose_batch = []
        self.nginx_batch = []
        # JSX-preserved batches
        self.symbols_jsx_batch = []
        self.assignments_jsx_batch = []
        self.function_call_args_jsx_batch = []
        self.function_returns_jsx_batch = []
        # Framework persistence batches
        self.frameworks_batch = []
        self.framework_safe_sinks_batch = []
        # React metadata batches
        self.react_components_batch = []
        self.react_hooks_batch = []

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
                loc INTEGER NOT NULL
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
                method TEXT NOT NULL,
                pattern TEXT NOT NULL,
                controls TEXT,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

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
                command TEXT NOT NULL,
                tables TEXT,
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
            CREATE TABLE IF NOT EXISTS docker_issues(
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                issue_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                FOREIGN KEY(file) REFERENCES files(path)
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
                callee_function TEXT NOT NULL,
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

        # JSX-preserved dual-pass tables
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS symbols_jsx(
                path TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                line INTEGER NOT NULL,
                col INTEGER NOT NULL,
                jsx_mode TEXT NOT NULL,
                extraction_pass INTEGER NOT NULL DEFAULT 2,
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
                jsx_mode TEXT NOT NULL,
                extraction_pass INTEGER NOT NULL DEFAULT 2,
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
                jsx_mode TEXT NOT NULL,
                extraction_pass INTEGER NOT NULL DEFAULT 2,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS function_returns_jsx (
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                function_name TEXT NOT NULL,
                return_expr TEXT NOT NULL,
                return_vars TEXT,
                has_jsx BOOLEAN NOT NULL DEFAULT 0,
                jsx_mode TEXT NOT NULL,
                extraction_pass INTEGER NOT NULL DEFAULT 2,
                FOREIGN KEY(file) REFERENCES files(path)
            )
        """
        )

        # Framework detection persistence
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS frameworks (
                framework TEXT NOT NULL,
                language TEXT NOT NULL,
                version TEXT,
                source TEXT,
                path TEXT,
                is_primary BOOLEAN NOT NULL DEFAULT 0
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS framework_safe_sinks (
                framework TEXT NOT NULL,
                sink_type TEXT NOT NULL,
                value TEXT NOT NULL
            )
        """
        )

        # React metadata tables
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS react_components (
                file TEXT NOT NULL,
                component TEXT NOT NULL,
                line INTEGER,
                col INTEGER,
                export_type TEXT,
                hook_calls INTEGER NOT NULL DEFAULT 0
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS react_hooks (
                file TEXT NOT NULL,
                hook TEXT NOT NULL,
                component TEXT,
                line INTEGER,
                col INTEGER
            )
        """
        )

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_refs_src ON refs(src)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_endpoints_file ON api_endpoints(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sql_file ON sql_objects(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_path ON symbols(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sql_queries_file ON sql_queries(file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sql_queries_command ON sql_queries(command)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docker_images_base ON docker_images(base_image)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docker_issues_file ON docker_issues(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docker_issues_severity ON docker_issues(severity)")
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_call_args_file ON function_call_args(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_call_args_caller ON function_call_args(caller_function)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_call_args_callee ON function_call_args(callee_function)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_returns_file ON function_returns(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_returns_function ON function_returns(function_name)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbols_jsx_path ON symbols_jsx(path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_jsx_file ON assignments_jsx(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_call_args_jsx_file ON function_call_args_jsx(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_function_returns_jsx_file ON function_returns_jsx(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_frameworks_name ON frameworks(framework)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_frameworks_primary ON frameworks(is_primary)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_framework_sinks ON framework_safe_sinks(framework)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_react_components_file ON react_components(file)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_react_hooks_file ON react_hooks(file)")

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
            cursor.execute("DELETE FROM docker_issues")
            cursor.execute("DELETE FROM orm_queries")
            cursor.execute("DELETE FROM prisma_models")
            cursor.execute("DELETE FROM compose_services")
            cursor.execute("DELETE FROM nginx_configs")
            cursor.execute("DELETE FROM assignments")
            cursor.execute("DELETE FROM function_call_args")
            cursor.execute("DELETE FROM function_returns")
            cursor.execute("DELETE FROM symbols_jsx")
            cursor.execute("DELETE FROM assignments_jsx")
            cursor.execute("DELETE FROM function_call_args_jsx")
            cursor.execute("DELETE FROM function_returns_jsx")
            cursor.execute("DELETE FROM frameworks")
            cursor.execute("DELETE FROM framework_safe_sinks")
            cursor.execute("DELETE FROM react_components")
            cursor.execute("DELETE FROM react_hooks")
        except sqlite3.Error as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to clear existing data: {e}")

    def add_file(self, path: str, sha256: str, ext: str, bytes_size: int, loc: int):
        """Add a file record to the batch."""
        self.files_batch.append((path, sha256, ext, bytes_size, loc))

    def add_ref(self, src: str, kind: str, value: str):
        """Add a reference record to the batch."""
        self.refs_batch.append((src, kind, value))

    def add_endpoint(self, file_path: str, method: str, pattern: str, controls: List[str]):
        """Add an API endpoint record to the batch."""
        controls_json = json.dumps(controls) if controls else "[]"
        self.endpoints_batch.append((file_path, method, pattern, controls_json))

    def add_sql_object(self, file_path: str, kind: str, name: str):
        """Add a SQL object record to the batch."""
        self.sql_objects_batch.append((file_path, kind, name))

    def add_sql_query(self, file_path: str, line: int, query_text: str, command: str, tables: List[str]):
        """Add a SQL query record to the batch."""
        tables_json = json.dumps(tables) if tables else "[]"
        self.sql_queries_batch.append((file_path, line, query_text, command, tables_json))

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

    def add_docker_issue(self, file_path: str, line: int, issue_type: str, severity: str):
        """Add a Docker security issue to the batch."""
        self.docker_issues_batch.append((file_path, line, issue_type, severity))

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

    # JSX-preserved helpers -------------------------------------------------

    def add_symbol_jsx(
        self,
        path: str,
        name: str,
        symbol_type: str,
        line: int,
        col: int,
        jsx_mode: str,
        extraction_pass: int,
    ) -> None:
        """Add a preserved-mode symbol for JSX-aware analysis."""
        self.symbols_jsx_batch.append(
            (path, name, symbol_type, line, col, jsx_mode, extraction_pass)
        )

    def add_assignment_jsx(
        self,
        file_path: str,
        line: int,
        target_var: str,
        source_expr: str,
        source_vars: List[str],
        in_function: str,
        jsx_mode: str,
        extraction_pass: int,
    ) -> None:
        """Add a preserved-mode assignment record."""
        self.assignments_jsx_batch.append(
            (
                file_path,
                line,
                target_var,
                source_expr,
                json.dumps(source_vars),
                in_function,
                jsx_mode,
                extraction_pass,
            )
        )

    def add_function_call_arg_jsx(
        self,
        file_path: str,
        line: int,
        caller_function: str,
        callee_function: str,
        argument_index: int,
        argument_expr: str,
        param_name: str,
        jsx_mode: str,
        extraction_pass: int,
    ) -> None:
        """Add a preserved-mode function call argument."""
        self.function_call_args_jsx_batch.append(
            (
                file_path,
                line,
                caller_function,
                callee_function,
                argument_index,
                argument_expr,
                param_name,
                jsx_mode,
                extraction_pass,
            )
        )

    def add_function_return_jsx(
        self,
        file_path: str,
        line: int,
        function_name: str,
        return_expr: str,
        return_vars: List[str],
        has_jsx: bool,
        jsx_mode: str,
        extraction_pass: int,
    ) -> None:
        """Add a preserved-mode function return entry."""
        self.function_returns_jsx_batch.append(
            (
                file_path,
                line,
                function_name,
                return_expr,
                json.dumps(return_vars),
                int(has_jsx),
                jsx_mode,
                extraction_pass,
            )
        )

    # Framework persistence helpers ---------------------------------------

    def add_framework(
        self,
        framework: str,
        language: str,
        version: Optional[str],
        source: Optional[str],
        path: Optional[str],
        is_primary: bool,
    ) -> None:
        """Queue a detected framework for insertion."""
        self.frameworks_batch.append(
            (framework, language, version or "unknown", source or "", path or ".", int(is_primary))
        )

    def add_framework_safe_sink(
        self,
        framework: str,
        sink_type: str,
        value: str,
    ) -> None:
        """Queue a framework-specific safe sink."""
        self.framework_safe_sinks_batch.append((framework, sink_type, value))

    # React metadata helpers ----------------------------------------------

    def add_react_component(
        self,
        file_path: str,
        component: str,
        line: Optional[int],
        col: Optional[int],
        export_type: Optional[str],
        hook_calls: int,
    ) -> None:
        """Persist a detected React component."""
        self.react_components_batch.append(
            (file_path, component, line, col, export_type or "", hook_calls)
        )

    def add_react_hook(
        self,
        file_path: str,
        hook: str,
        component: Optional[str],
        line: Optional[int],
        col: Optional[int],
    ) -> None:
        """Persist a detected React hook usage."""
        self.react_hooks_batch.append((file_path, hook, component or "", line, col))

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
                           is_privileged: bool, network_mode: str):
        """Add a Docker Compose service record to the batch."""
        ports_json = json.dumps(ports)
        volumes_json = json.dumps(volumes)
        env_json = json.dumps(environment)
        self.compose_batch.append((file_path, service_name, image, ports_json,
                                  volumes_json, env_json, is_privileged, network_mode))

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

    def flush_batch(self, batch_idx: Optional[int] = None):
        """Execute all pending batch inserts."""
        cursor = self.conn.cursor()
        
        try:
            if self.files_batch:
                cursor.executemany(
                    "INSERT INTO files (path, sha256, ext, bytes, loc) VALUES (?, ?, ?, ?, ?)",
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
                    "INSERT INTO api_endpoints (file, method, pattern, controls) VALUES (?, ?, ?, ?)",
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
                    "INSERT INTO sql_queries (file_path, line_number, query_text, command, tables) VALUES (?, ?, ?, ?, ?)",
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
            
            if self.docker_issues_batch:
                cursor.executemany(
                    "INSERT INTO docker_issues (file, line, issue_type, severity) VALUES (?, ?, ?, ?)",
                    self.docker_issues_batch
                )
                self.docker_issues_batch = []
            
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

            if self.symbols_jsx_batch:
                cursor.executemany(
                    """INSERT INTO symbols_jsx
                        (path, name, type, line, col, jsx_mode, extraction_pass)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    self.symbols_jsx_batch,
                )
                self.symbols_jsx_batch = []

            if self.assignments_jsx_batch:
                cursor.executemany(
                    """INSERT INTO assignments_jsx
                        (file, line, target_var, source_expr, source_vars, in_function, jsx_mode, extraction_pass)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.assignments_jsx_batch,
                )
                self.assignments_jsx_batch = []

            if self.function_call_args_jsx_batch:
                cursor.executemany(
                    """INSERT INTO function_call_args_jsx
                        (file, line, caller_function, callee_function, argument_index, argument_expr, param_name, jsx_mode, extraction_pass)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.function_call_args_jsx_batch,
                )
                self.function_call_args_jsx_batch = []

            if self.function_returns_jsx_batch:
                cursor.executemany(
                    """INSERT INTO function_returns_jsx
                        (file, line, function_name, return_expr, return_vars, has_jsx, jsx_mode, extraction_pass)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    self.function_returns_jsx_batch,
                )
                self.function_returns_jsx_batch = []

            if self.frameworks_batch:
                cursor.executemany(
                    "INSERT INTO frameworks (framework, language, version, source, path, is_primary) VALUES (?, ?, ?, ?, ?, ?)",
                    self.frameworks_batch,
                )
                self.frameworks_batch = []

            if self.framework_safe_sinks_batch:
                cursor.executemany(
                    "INSERT INTO framework_safe_sinks (framework, sink_type, value) VALUES (?, ?, ?)",
                    self.framework_safe_sinks_batch,
                )
                self.framework_safe_sinks_batch = []

            if self.react_components_batch:
                cursor.executemany(
                    "INSERT INTO react_components (file, component, line, col, export_type, hook_calls) VALUES (?, ?, ?, ?, ?, ?)",
                    self.react_components_batch,
                )
                self.react_components_batch = []

            if self.react_hooks_batch:
                cursor.executemany(
                    "INSERT INTO react_hooks (file, hook, component, line, col) VALUES (?, ?, ?, ?, ?)",
                    self.react_hooks_batch,
                )
                self.react_hooks_batch = []
            
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
                        is_privileged, network_mode) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
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
    manager.docker_issues_batch = []
    manager.assignments_batch = []
    manager.function_calls_batch = []
    manager.returns_batch = []
    manager.prisma_batch = []
    manager.compose_batch = []
    manager.nginx_batch = []
    
    # Create the schema using the existing connection
    manager.create_schema()
    # Don't close - let caller handle connection lifecycle
