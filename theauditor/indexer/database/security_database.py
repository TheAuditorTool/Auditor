"""Security-focused database operations."""


class SecurityDatabaseMixin:
    """Mixin providing add_* methods for SECURITY_TABLES."""

    def add_sql_object(self, file_path: str, kind: str, name: str):
        """Add a SQL object record to the batch."""
        self.generic_batches["sql_objects"].append((file_path, kind, name))

    def add_sql_query(
        self,
        file_path: str,
        line: int,
        query_text: str,
        command: str,
        tables: list[str],
        extraction_source: str = "code_execute",
    ):
        """Add a SQL query record to the batch."""

        self.generic_batches["sql_queries"].append(
            (file_path, line, query_text, command, extraction_source)
        )

        if tables:
            for table_name in tables:
                if not table_name:
                    continue
                self.generic_batches["sql_query_tables"].append((file_path, line, table_name))

    def add_env_var_usage(
        self,
        file: str,
        line: int,
        var_name: str,
        access_type: str,
        in_function: str | None = None,
        property_access: str | None = None,
    ):
        """Add an environment variable usage record to the batch."""
        self.generic_batches["env_var_usage"].append(
            (file, line, var_name, access_type, in_function, property_access)
        )

    def add_jwt_pattern(
        self, file_path, line_number, pattern_type, pattern_text, secret_source, algorithm=None
    ):
        """Add JWT pattern detection."""
        self.jwt_patterns_batch.append(
            {
                "file_path": file_path,
                "line_number": line_number,
                "pattern_type": pattern_type,
                "pattern_text": pattern_text,
                "secret_source": secret_source,
                "algorithm": algorithm,
            }
        )
        if len(self.jwt_patterns_batch) >= self.batch_size:
            self._flush_jwt_patterns()
