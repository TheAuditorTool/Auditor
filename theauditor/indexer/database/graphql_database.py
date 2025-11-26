"""GraphQL-specific database operations.

This module contains add_* methods for GRAPHQL_TABLES defined in schemas/graphql_schema.py.
Handles 8 GraphQL tables including schemas, types, fields, resolvers, and execution graph.
"""


class GraphQLDatabaseMixin:
    """Mixin providing add_* methods for GRAPHQL_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.

    NO FALLBACKS. NO TRY/EXCEPT. Hard fail if data is wrong.
    """

    # ========================================================
    # GRAPHQL SCHEMA BATCH METHODS
    # ========================================================

    def add_graphql_schema(self, file_path: str, schema_hash: str, language: str,
                          last_modified: int | None = None):
        """Add a GraphQL schema file record to the batch.

        Args:
            file_path: Absolute path to .graphql/.gql file
            schema_hash: SHA256 hash of schema content for change detection
            language: 'sdl' for schema definition language, 'code-first' for programmatic schemas
            last_modified: Unix timestamp of file modification (optional)

        NO FALLBACKS. If schema_hash is wrong, hard fail.
        """
        self.generic_batches['graphql_schemas'].append((file_path, schema_hash, language, last_modified))

    def add_graphql_type(self, schema_path: str, type_name: str, kind: str,
                        implements: str | None = None, description: str | None = None,
                        line: int | None = None):
        """Add a GraphQL type definition record to the batch.

        Args:
            schema_path: FK to graphql_schemas.file_path
            type_name: Name of the type (e.g., 'User', 'Query', 'Mutation')
            kind: Type kind - 'object', 'interface', 'input', 'enum', 'union', 'scalar'
            implements: JSON array of interface names (optional)
            description: Type description from schema (optional)
            line: Line number in schema file (optional)

        NO FALLBACKS. Type resolution happens at extraction time.
        """
        import os, sys
        tuple_data = (schema_path, type_name, kind, implements, description, line)

        if os.environ.get('THEAUDITOR_DEBUG') == '1':
            if 'graphql_types' not in self.generic_batches or len(self.generic_batches['graphql_types']) == 0:
                print(f"[DEBUG] Database: add_graphql_type - First tuple", file=sys.stderr)
                print(f"  Tuple length: {len(tuple_data)}", file=sys.stderr)
                print(f"  Tuple data: {tuple_data}", file=sys.stderr)

        self.generic_batches['graphql_types'].append(tuple_data)

    def add_graphql_field(self, type_id: int, field_name: str, return_type: str,
                         is_list: bool = False, is_nullable: bool = True,
                         directives_json: str | None = None,
                         line: int | None = None, column: int | None = None):
        """Add a GraphQL field definition record to the batch.

        Args:
            type_id: FK to graphql_types.type_id (from INSERT return)
            field_name: Name of the field (e.g., 'user', 'createPost')
            return_type: GraphQL return type (e.g., 'User', 'String!', '[Post]')
            is_list: Whether field returns a list (e.g., [User])
            is_nullable: Whether field return is nullable
            directives_json: JSON array of directive objects (e.g., @auth, @deprecated)
            line: Line number in schema file (optional)
            column: Column number in schema file (optional)

        NO FALLBACKS. type_id MUST exist from prior add_graphql_type call.
        """
        self.generic_batches['graphql_fields'].append((
            type_id, field_name, return_type,
            1 if is_list else 0,
            1 if is_nullable else 0,
            directives_json, line, column
        ))

    def add_graphql_field_arg(self, field_id: int, arg_name: str, arg_type: str,
                             has_default: bool = False, default_value: str | None = None,
                             is_nullable: bool = True, directives_json: str | None = None):
        """Add a GraphQL field argument definition record to the batch.

        Args:
            field_id: FK to graphql_fields.field_id (from INSERT return)
            arg_name: Argument name (e.g., 'id', 'limit', 'filter')
            arg_type: GraphQL argument type (e.g., 'ID!', 'Int', 'UserInput')
            has_default: Whether argument has a default value
            default_value: Default value as string (optional)
            is_nullable: Whether argument is nullable
            directives_json: JSON array of directive objects (optional)

        NO FALLBACKS. field_id MUST exist from prior add_graphql_field call.
        """
        self.generic_batches['graphql_field_args'].append((
            field_id, arg_name, arg_type,
            1 if has_default else 0,
            default_value,
            1 if is_nullable else 0,
            directives_json
        ))

    # ========================================================
    # GRAPHQL RESOLVER MAPPING BATCH METHODS
    # ========================================================

    def add_graphql_resolver_mapping(self, field_id: int, resolver_symbol_id: int,
                                    resolver_path: str, resolver_line: int,
                                    resolver_language: str, binding_style: str,
                                    resolver_export: str | None = None):
        """Add a GraphQL resolver mapping record to the batch.

        Maps a GraphQL field to its backend implementation symbol.

        Args:
            field_id: FK to graphql_fields.field_id
            resolver_symbol_id: FK to symbols.symbol_id (backend function/method)
            resolver_path: File path containing resolver implementation
            resolver_line: Line number of resolver function/method
            resolver_language: 'javascript', 'typescript', or 'python'
            binding_style: Resolver pattern - 'apollo-object', 'apollo-class', 'nestjs-decorator',
                          'graphene-decorator', 'ariadne-decorator', 'strawberry-type', etc.
            resolver_export: Export name for tracing (optional)

        NO FALLBACKS. Both field_id and resolver_symbol_id MUST exist.
        """
        self.generic_batches['graphql_resolver_mappings'].append((
            field_id, resolver_symbol_id, resolver_path, resolver_line,
            resolver_language, resolver_export, binding_style
        ))

    def add_graphql_resolver_param(self, resolver_symbol_id: int, arg_name: str, param_name: str,
                                  param_index: int, is_kwargs: bool = False, is_list_input: bool = False):
        """Add a GraphQL resolver parameter mapping record to the batch.

        Maps GraphQL argument names to function parameter positions for taint analysis.

        Args:
            resolver_symbol_id: FK to symbols.symbol_id (resolver function)
            arg_name: GraphQL argument name from schema (e.g., 'userId')
            param_name: Function parameter name in code (e.g., 'user_id', 'args')
            param_index: Parameter position in function signature (0-indexed)
            is_kwargs: True if parameter is part of kwargs dict (Python) or destructured object (JS)
            is_list_input: True if parameter expects list/array input

        NO FALLBACKS. resolver_symbol_id MUST exist from prior add_graphql_resolver_mapping call.
        """
        self.generic_batches['graphql_resolver_params'].append((
            resolver_symbol_id, arg_name, param_name, param_index,
            1 if is_kwargs else 0,
            1 if is_list_input else 0
        ))

    def add_graphql_execution_edge(self, from_field_id: int, to_symbol_id: int, edge_kind: str):
        """Add a GraphQL execution graph edge record to the batch.

        Represents execution flow from GraphQL fields to backend symbols.

        Args:
            from_field_id: FK to graphql_fields.field_id (source field)
            to_symbol_id: FK to symbols.symbol_id (target function/method)
            edge_kind: Edge type - 'resolver' (field->resolver) or 'downstream_call' (resolver->callee)

        NO FALLBACKS. Both from_field_id and to_symbol_id MUST exist.
        Edge kind MUST be 'resolver' or 'downstream_call' - validated at insert time.
        """
        self.generic_batches['graphql_execution_edges'].append((from_field_id, to_symbol_id, edge_kind))
