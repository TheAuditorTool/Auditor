## ADDED Requirements

### Requirement: GraphQL Schema Table Definitions
The GraphQL schema module MUST define 8 tables using TableSchema pattern following modular architecture.

#### Scenario: Schema Module Follows Established Pattern
- **GIVEN** the codebase uses modular schema definitions in `theauditor/indexer/schemas/`
- **WHEN** creating `graphql_schema.py`
- **THEN** it imports from `.utils` and defines tables like:
```python
"""
GraphQL-specific schema definitions.

This module contains table schemas for GraphQL SDL parsing and resolver execution graphs.
"""

from typing import Dict
from .utils import Column, ForeignKey, TableSchema


# ============================================================================
# GRAPHQL SCHEMA TABLES
# ============================================================================

GRAPHQL_SCHEMAS = TableSchema(
    name="graphql_schemas",
    columns=[
        Column("file_path", "TEXT", nullable=False),
        Column("schema_hash", "TEXT", nullable=False),
        Column("language", "TEXT", nullable=False),  # 'sdl' or 'code-first'
        Column("last_modified", "REAL"),  # Unix timestamp
    ],
    primary_key=["file_path"],
    indexes=[
        ("idx_graphql_schemas_hash", ["schema_hash"]),
        ("idx_graphql_schemas_language", ["language"]),
    ]
)

GRAPHQL_TYPES = TableSchema(
    name="graphql_types",
    columns=[
        Column("type_id", "INTEGER", nullable=False, auto_increment=True),
        Column("schema_path", "TEXT", nullable=False),
        Column("type_name", "TEXT", nullable=False),
        Column("kind", "TEXT", nullable=False),  # OBJECT, INTERFACE, UNION, ENUM, INPUT_OBJECT, SCALAR
        Column("implements", "TEXT"),  # JSON array of interface names
        Column("description", "TEXT"),
        Column("line", "INTEGER"),
        Column("column", "INTEGER"),
    ],
    primary_key=["type_id"],
    foreign_keys=[
        ForeignKey("schema_path", "graphql_schemas", "file_path")
    ],
    indexes=[
        ("idx_graphql_types_schema", ["schema_path"]),
        ("idx_graphql_types_name", ["type_name"]),
        ("idx_graphql_types_kind", ["kind"]),
    ]
)

GRAPHQL_FIELDS = TableSchema(
    name="graphql_fields",
    columns=[
        Column("field_id", "INTEGER", nullable=False, auto_increment=True),
        Column("type_id", "INTEGER", nullable=False),
        Column("field_name", "TEXT", nullable=False),
        Column("return_type", "TEXT", nullable=False),
        Column("is_list", "BOOLEAN", default="0"),
        Column("is_nullable", "BOOLEAN", default="1"),
        Column("directives_json", "TEXT"),  # JSON array of directive objects
        Column("description", "TEXT"),
        Column("line", "INTEGER"),
        Column("column", "INTEGER"),
    ],
    primary_key=["field_id"],
    foreign_keys=[
        ForeignKey("type_id", "graphql_types", "type_id")
    ],
    indexes=[
        ("idx_graphql_fields_type", ["type_id"]),
        ("idx_graphql_fields_name", ["field_name"]),
        ("idx_graphql_fields_list", ["is_list"]),
    ]
)

GRAPHQL_FIELD_ARGS = TableSchema(
    name="graphql_field_args",
    columns=[
        Column("field_id", "INTEGER", nullable=False),
        Column("arg_name", "TEXT", nullable=False),
        Column("arg_type", "TEXT", nullable=False),
        Column("has_default", "BOOLEAN", default="0"),
        Column("default_value", "TEXT"),
        Column("is_nullable", "BOOLEAN", default="1"),
        Column("directives_json", "TEXT"),
    ],
    primary_key=["field_id", "arg_name"],
    foreign_keys=[
        ForeignKey("field_id", "graphql_fields", "field_id")
    ],
    indexes=[
        ("idx_graphql_field_args_field", ["field_id"]),
    ]
)

GRAPHQL_RESOLVER_MAPPINGS = TableSchema(
    name="graphql_resolver_mappings",
    columns=[
        Column("field_id", "INTEGER", nullable=False),
        Column("resolver_symbol_id", "INTEGER", nullable=False),
        Column("resolver_path", "TEXT", nullable=False),
        Column("resolver_line", "INTEGER"),
        Column("resolver_language", "TEXT", nullable=False),  # 'javascript', 'typescript', 'python'
        Column("resolver_export", "TEXT"),  # Export name if applicable
        Column("binding_style", "TEXT"),  # 'apollo-object', 'nestjs-decorator', 'graphene-class', etc.
    ],
    primary_key=["field_id", "resolver_symbol_id"],
    foreign_keys=[
        ForeignKey("field_id", "graphql_fields", "field_id"),
        ForeignKey("resolver_symbol_id", "symbols", "symbol_id")
    ],
    indexes=[
        ("idx_graphql_resolver_mappings_field", ["field_id"]),
        ("idx_graphql_resolver_mappings_symbol", ["resolver_symbol_id"]),
        ("idx_graphql_resolver_mappings_path", ["resolver_path"]),
    ]
)

GRAPHQL_RESOLVER_PARAMS = TableSchema(
    name="graphql_resolver_params",
    columns=[
        Column("resolver_symbol_id", "INTEGER", nullable=False),
        Column("arg_name", "TEXT", nullable=False),
        Column("param_name", "TEXT", nullable=False),
        Column("param_index", "INTEGER", nullable=False),
        Column("is_kwargs", "BOOLEAN", default="0"),
        Column("is_list_input", "BOOLEAN", default="0"),
    ],
    primary_key=["resolver_symbol_id", "arg_name"],
    foreign_keys=[
        ForeignKey("resolver_symbol_id", "symbols", "symbol_id")
    ],
    indexes=[
        ("idx_graphql_resolver_params_symbol", ["resolver_symbol_id"]),
    ]
)

GRAPHQL_EXECUTION_EDGES = TableSchema(
    name="graphql_execution_edges",
    columns=[
        Column("from_field_id", "INTEGER", nullable=False),
        Column("to_symbol_id", "INTEGER", nullable=False),
        Column("edge_kind", "TEXT", nullable=False),  # 'resolver' or 'downstream_call'
    ],
    primary_key=["from_field_id", "to_symbol_id", "edge_kind"],
    foreign_keys=[
        ForeignKey("from_field_id", "graphql_fields", "field_id"),
        ForeignKey("to_symbol_id", "symbols", "symbol_id")
    ],
    indexes=[
        ("idx_graphql_execution_edges_from", ["from_field_id"]),
        ("idx_graphql_execution_edges_to", ["to_symbol_id"]),
        ("idx_graphql_execution_edges_kind", ["edge_kind"]),
    ]
)

GRAPHQL_FINDINGS_CACHE = TableSchema(
    name="graphql_findings_cache",
    columns=[
        Column("finding_id", "INTEGER", nullable=False, auto_increment=True),
        Column("field_id", "INTEGER"),
        Column("resolver_symbol_id", "INTEGER"),
        Column("rule", "TEXT", nullable=False),
        Column("severity", "TEXT", nullable=False),
        Column("details_json", "TEXT"),
        Column("provenance", "TEXT"),  # JSON with table+row references
    ],
    primary_key=["finding_id"],
    foreign_keys=[
        ForeignKey("field_id", "graphql_fields", "field_id"),
        ForeignKey("resolver_symbol_id", "symbols", "symbol_id")
    ],
    indexes=[
        ("idx_graphql_findings_cache_rule", ["rule"]),
        ("idx_graphql_findings_cache_severity", ["severity"]),
    ]
)


# ============================================================================
# SCHEMA REGISTRY
# ============================================================================

GRAPHQL_TABLES: Dict[str, TableSchema] = {
    "graphql_schemas": GRAPHQL_SCHEMAS,
    "graphql_types": GRAPHQL_TYPES,
    "graphql_fields": GRAPHQL_FIELDS,
    "graphql_field_args": GRAPHQL_FIELD_ARGS,
    "graphql_resolver_mappings": GRAPHQL_RESOLVER_MAPPINGS,
    "graphql_resolver_params": GRAPHQL_RESOLVER_PARAMS,
    "graphql_execution_edges": GRAPHQL_EXECUTION_EDGES,
    "graphql_findings_cache": GRAPHQL_FINDINGS_CACHE,
}
```
- **AND** the schema module exports `GRAPHQL_TABLES` dict at module level
- **AND** all table definitions use Column/ForeignKey/TableSchema from `.utils`
- **AND** primary keys, foreign keys, and indexes are explicitly defined
- **AND** column types follow SQLite conventions (TEXT, INTEGER, REAL, BOOLEAN)

### Requirement: Schema Registration in Main Module
The main schema.py MUST merge GRAPHQL_TABLES into master TABLES registry.

#### Scenario: Schema Module Imported and Merged
- **GIVEN** `theauditor/indexer/schema.py` currently merges 7 module registries
- **WHEN** adding GraphQL support
- **THEN** it imports and merges GRAPHQL_TABLES:
```python
# Import all table registries
from .schemas.core_schema import CORE_TABLES
from .schemas.security_schema import SECURITY_TABLES
from .schemas.frameworks_schema import FRAMEWORKS_TABLES
from .schemas.python_schema import PYTHON_TABLES
from .schemas.node_schema import NODE_TABLES
from .schemas.infrastructure_schema import INFRASTRUCTURE_TABLES
from .schemas.planning_schema import PLANNING_TABLES
from .schemas.graphql_schema import GRAPHQL_TABLES  # NEW

TABLES: Dict[str, TableSchema] = {
    **CORE_TABLES,           # 21 tables
    **SECURITY_TABLES,       # 5 tables
    **FRAMEWORKS_TABLES,     # 5 tables
    **PYTHON_TABLES,         # 34 tables
    **NODE_TABLES,           # 17 tables
    **INFRASTRUCTURE_TABLES, # 18 tables
    **PLANNING_TABLES,       # 5 tables
    **GRAPHQL_TABLES,        # 8 tables (NEW)
}

# Update assertion from 108 → 116
assert len(TABLES) == 116, f"Schema contract violation: Expected 116 tables, got {len(TABLES)}"
```
- **AND** assertion validates total table count increased by 8
- **AND** schema loads without errors when imported

### Requirement: Database Mixin Implementation Pattern
The GraphQL database mixin MUST follow frameworks_database.py pattern with add_* methods.

#### Scenario: Database Mixin Follows Established Pattern
- **GIVEN** existing mixins use self.generic_batches for queuing
- **WHEN** implementing GraphQLDatabaseMixin
- **THEN** it follows this structure:
```python
"""GraphQL-specific database operations.

This module contains add_* methods for GRAPHQL_TABLES defined in schemas/graphql_schema.py.
"""

from typing import List, Optional


class GraphQLDatabaseMixin:
    """Mixin providing add_* methods for GRAPHQL_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.
    """

    def add_graphql_schema(self, file_path: str, schema_hash: str,
                          language: str, last_modified: Optional[float] = None):
        """Add GraphQL schema record to batch."""
        self.generic_batches['graphql_schemas'].append((
            file_path, schema_hash, language, last_modified
        ))

    def add_graphql_type(self, type_id: int, schema_path: str, type_name: str,
                        kind: str, implements: Optional[str] = None,
                        description: Optional[str] = None,
                        line: Optional[int] = None, column: Optional[int] = None):
        """Add GraphQL type definition to batch."""
        self.generic_batches['graphql_types'].append((
            type_id, schema_path, type_name, kind, implements,
            description, line, column
        ))

    def add_graphql_field(self, field_id: int, type_id: int, field_name: str,
                         return_type: str, is_list: bool = False,
                         is_nullable: bool = True, directives_json: Optional[str] = None,
                         description: Optional[str] = None,
                         line: Optional[int] = None, column: Optional[int] = None):
        """Add GraphQL field definition to batch."""
        self.generic_batches['graphql_fields'].append((
            field_id, type_id, field_name, return_type,
            1 if is_list else 0, 1 if is_nullable else 0,
            directives_json, description, line, column
        ))

    def add_graphql_field_arg(self, field_id: int, arg_name: str, arg_type: str,
                             has_default: bool = False, default_value: Optional[str] = None,
                             is_nullable: bool = True, directives_json: Optional[str] = None):
        """Add GraphQL field argument to batch."""
        self.generic_batches['graphql_field_args'].append((
            field_id, arg_name, arg_type,
            1 if has_default else 0, default_value,
            1 if is_nullable else 0, directives_json
        ))

    def add_graphql_resolver_mapping(self, field_id: int, resolver_symbol_id: int,
                                    resolver_path: str, resolver_line: Optional[int],
                                    resolver_language: str, resolver_export: Optional[str] = None,
                                    binding_style: Optional[str] = None):
        """Add GraphQL resolver mapping to batch."""
        self.generic_batches['graphql_resolver_mappings'].append((
            field_id, resolver_symbol_id, resolver_path, resolver_line,
            resolver_language, resolver_export, binding_style
        ))

    def add_graphql_resolver_param(self, resolver_symbol_id: int, arg_name: str,
                                   param_name: str, param_index: int,
                                   is_kwargs: bool = False, is_list_input: bool = False):
        """Add GraphQL resolver parameter mapping to batch."""
        self.generic_batches['graphql_resolver_params'].append((
            resolver_symbol_id, arg_name, param_name, param_index,
            1 if is_kwargs else 0, 1 if is_list_input else 0
        ))

    def add_graphql_execution_edge(self, from_field_id: int, to_symbol_id: int,
                                   edge_kind: str):
        """Add GraphQL execution edge to batch.

        Args:
            from_field_id: Source field ID
            to_symbol_id: Target symbol ID
            edge_kind: 'resolver' or 'downstream_call'
        """
        if edge_kind not in ('resolver', 'downstream_call'):
            raise ValueError(f"Invalid edge_kind: {edge_kind}")
        self.generic_batches['graphql_execution_edges'].append((
            from_field_id, to_symbol_id, edge_kind
        ))
```
- **AND** NO try/except around batch appends (hard fail on error)
- **AND** NO table existence checks (Zero Fallback Policy)
- **AND** all methods append tuples to self.generic_batches dict
- **AND** BaseDatabaseManager.flush_all_batches() handles actual INSERT

### Requirement: Database Manager Inheritance Chain Update
DatabaseManager MUST inherit from GraphQLDatabaseMixin in correct MRO order.

#### Scenario: Mixin Added to Inheritance Chain
- **GIVEN** `theauditor/indexer/database/__init__.py` defines DatabaseManager with 7 mixins
- **WHEN** adding GraphQL support
- **THEN** it imports and inherits from GraphQLDatabaseMixin:
```python
from .base_database import BaseDatabaseManager
from .core_database import CoreDatabaseMixin
from .python_database import PythonDatabaseMixin
from .node_database import NodeDatabaseMixin
from .infrastructure_database import InfrastructureDatabaseMixin
from .security_database import SecurityDatabaseMixin
from .frameworks_database import FrameworksDatabaseMixin
from .planning_database import PlanningDatabaseMixin
from .graphql_database import GraphQLDatabaseMixin  # NEW


class DatabaseManager(
    BaseDatabaseManager,
    CoreDatabaseMixin,
    PythonDatabaseMixin,
    NodeDatabaseMixin,
    InfrastructureDatabaseMixin,
    SecurityDatabaseMixin,
    FrameworksDatabaseMixin,
    PlanningDatabaseMixin,
    GraphQLDatabaseMixin  # NEW
):
    """Complete database manager combining all language-specific capabilities.

    Method Resolution Order (MRO):
    1. DatabaseManager
    2. BaseDatabaseManager
    3. CoreDatabaseMixin (21 tables, 16 methods)
    4. PythonDatabaseMixin (34 tables, 34 methods)
    5. NodeDatabaseMixin (17 tables, 14 methods)
    6. InfrastructureDatabaseMixin (18 tables, 18 methods)
    7. SecurityDatabaseMixin (5 tables, 4 methods)
    8. FrameworksDatabaseMixin (5 tables, 4 methods)
    9. PlanningDatabaseMixin (5 tables, 0 methods)
    10. GraphQLDatabaseMixin (8 tables, 7 methods)  # NEW

    Total: 113 tables, 97 methods
    """
    pass
```
- **AND** docstring updated with new table/method counts
- **AND** DatabaseManager instantiates without errors
- **AND** all add_graphql_* methods accessible via manager instance
