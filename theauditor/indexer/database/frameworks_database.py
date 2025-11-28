"""Framework-specific database operations."""


class FrameworksDatabaseMixin:
    """Mixin providing add_* methods for FRAMEWORKS_TABLES."""

    def add_endpoint(
        self,
        file_path: str,
        method: str,
        pattern: str,
        controls: list[str],
        line: int | None = None,
        path: str | None = None,
        has_auth: bool = False,
        handler_function: str | None = None,
    ):
        """Add an API endpoint record to the batch."""

        self.generic_batches["api_endpoints"].append(
            (file_path, line, method, pattern, path, None, has_auth, handler_function)
        )

        if controls:
            for control_name in controls:
                if not control_name:
                    continue
                self.generic_batches["api_endpoint_controls"].append(
                    (file_path, line, control_name)
                )

    def add_orm_relationship(
        self,
        file: str,
        line: int,
        source_model: str,
        target_model: str,
        relationship_type: str,
        foreign_key: str | None = None,
        cascade_delete: bool = False,
        as_name: str | None = None,
    ):
        """Add an ORM relationship record to the batch."""
        self.generic_batches["orm_relationships"].append(
            (
                file,
                line,
                source_model,
                target_model,
                relationship_type,
                foreign_key,
                1 if cascade_delete else 0,
                as_name,
            )
        )

    def add_orm_query(
        self,
        file_path: str,
        line: int,
        query_type: str,
        includes: str | None,
        has_limit: bool,
        has_transaction: bool,
    ):
        """Add an ORM query record to the batch."""
        self.generic_batches["orm_queries"].append(
            (file_path, line, query_type, includes, has_limit, has_transaction)
        )

    def add_prisma_model(
        self,
        model_name: str,
        field_name: str,
        field_type: str,
        is_indexed: bool,
        is_unique: bool,
        is_relation: bool,
    ):
        """Add a Prisma model field record to the batch."""
        self.generic_batches["prisma_models"].append(
            (model_name, field_name, field_type, is_indexed, is_unique, is_relation)
        )

    def add_router_mount(
        self, file: str, line: int, mount_path_expr: str, router_variable: str, is_literal: bool
    ):
        """Add a router mount record to the batch."""
        self.generic_batches["router_mounts"].append(
            (file, line, mount_path_expr, router_variable, 1 if is_literal else 0)
        )
