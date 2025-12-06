"""GraphQL-specific database operations."""

from theauditor.utils.logging import logger


class GraphQLDatabaseMixin:
    """Mixin providing add_* methods for GRAPHQL_TABLES."""

    def add_graphql_schema(
        self, file_path: str, schema_hash: str, language: str, last_modified: int | None = None
    ):
        """Add a GraphQL schema file record to the batch."""
        self.generic_batches["graphql_schemas"].append(
            (file_path, schema_hash, language, last_modified)
        )

    def add_graphql_type(
        self,
        schema_path: str,
        type_name: str,
        kind: str,
        implements: str | None = None,
        description: str | None = None,
        line: int | None = None,
    ):
        """Add a GraphQL type definition record to the batch."""
        import os

        tuple_data = (schema_path, type_name, kind, implements, description, line)

        if os.environ.get("THEAUDITOR_DEBUG") == "1" and (
            "graphql_types" not in self.generic_batches
            or len(self.generic_batches["graphql_types"]) == 0
        ):
            logger.debug("Database: add_graphql_type - First tuple")
            logger.error(f"  Tuple length: {len(tuple_data)}")
            logger.error(f"  Tuple data: {tuple_data}")

        self.generic_batches["graphql_types"].append(tuple_data)

    def add_graphql_field(
        self,
        type_id: int,
        field_name: str,
        return_type: str,
        is_list: bool = False,
        is_nullable: bool = True,
        line: int | None = None,
        column: int | None = None,
    ):
        """Add a GraphQL field definition record to the batch."""
        self.generic_batches["graphql_fields"].append(
            (
                type_id,
                field_name,
                return_type,
                1 if is_list else 0,
                1 if is_nullable else 0,
                line,
                column,
            )
        )

    def add_graphql_field_directive(
        self, field_id: int, directive_name: str, arguments_json: str | None = None
    ):
        """Add a GraphQL field directive to the batch (junction table)."""
        self.generic_batches["graphql_field_directives"].append(
            (field_id, directive_name, arguments_json)
        )

    def add_graphql_field_arg(
        self,
        field_id: int,
        arg_name: str,
        arg_type: str,
        has_default: bool = False,
        default_value: str | None = None,
        is_nullable: bool = True,
    ):
        """Add a GraphQL field argument definition record to the batch."""
        self.generic_batches["graphql_field_args"].append(
            (
                field_id,
                arg_name,
                arg_type,
                1 if has_default else 0,
                default_value,
                1 if is_nullable else 0,
            )
        )

    def add_graphql_arg_directive(
        self,
        field_id: int,
        arg_name: str,
        directive_name: str,
        arguments_json: str | None = None,
    ):
        """Add a GraphQL argument directive to the batch (junction table)."""
        self.generic_batches["graphql_arg_directives"].append(
            (field_id, arg_name, directive_name, arguments_json)
        )

    def add_graphql_resolver_mapping(
        self,
        field_id: int,
        resolver_symbol_id: int,
        resolver_path: str,
        resolver_line: int,
        resolver_language: str,
        binding_style: str,
        resolver_export: str | None = None,
    ):
        """Add a GraphQL resolver mapping record to the batch."""
        self.generic_batches["graphql_resolver_mappings"].append(
            (
                field_id,
                resolver_symbol_id,
                resolver_path,
                resolver_line,
                resolver_language,
                resolver_export,
                binding_style,
            )
        )

    def add_graphql_resolver_param(
        self,
        resolver_symbol_id: int,
        arg_name: str,
        param_name: str,
        param_index: int,
        is_kwargs: bool = False,
        is_list_input: bool = False,
    ):
        """Add a GraphQL resolver parameter mapping record to the batch."""

        param_key = (resolver_symbol_id, arg_name)
        for p in reversed(self.generic_batches["graphql_resolver_params"]):
            if (p[0], p[1]) == param_key:
                return

        self.generic_batches["graphql_resolver_params"].append(
            (
                resolver_symbol_id,
                arg_name,
                param_name,
                param_index,
                1 if is_kwargs else 0,
                1 if is_list_input else 0,
            )
        )

    def add_graphql_execution_edge(self, from_field_id: int, to_symbol_id: int, edge_kind: str):
        """Add a GraphQL execution graph edge record to the batch."""
        self.generic_batches["graphql_execution_edges"].append(
            (from_field_id, to_symbol_id, edge_kind)
        )
