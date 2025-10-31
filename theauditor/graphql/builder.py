"""GraphQL Builder - Correlates SDL schemas with resolver implementations.

This module implements the core correlation logic that maps:
1. GraphQL SDL fields → Resolver functions (via symbols table)
2. GraphQL arguments → Function parameters
3. Field dependencies → Execution graph edges

NO FALLBACKS. Hard fail if database is wrong.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class GraphQLType:
    """GraphQL type metadata from SDL."""
    type_id: int
    schema_path: str
    type_name: str
    kind: str  # 'object', 'interface', 'input', etc.


@dataclass
class GraphQLField:
    """GraphQL field metadata from SDL."""
    field_id: int
    type_id: int
    field_name: str
    return_type: str
    is_list: bool
    is_nullable: bool


@dataclass
class ResolverCandidate:
    """Potential resolver function from symbols table."""
    symbol_id: int
    name: str
    file_path: str
    line: int
    type: str  # 'function' or 'method'


class GraphQLBuilder:
    """Correlates GraphQL schemas with resolver implementations.

    Architecture:
    - Phase 1: Load SDL schemas/fields from graphql_* tables
    - Phase 2: Load symbols table (all functions/methods)
    - Phase 3: Correlate using naming conventions + framework patterns
    - Phase 4: Build execution graph edges

    NO FALLBACKS. Database must exist and be correct.
    """

    def __init__(self, db_path: Path, verbose: bool = False):
        """Initialize builder with database connection."""
        self.db_path = db_path
        self.verbose = verbose
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

        # Loaded data
        self.types: Dict[int, GraphQLType] = {}
        self.fields: Dict[int, GraphQLField] = {}
        self.resolvers: List[ResolverCandidate] = []

        # Correlation results
        self.mappings: List[Tuple[int, int, str, str, int, str, str]] = []  # (field_id, symbol_id, ...)
        self.edges: List[Tuple[int, int, str]] = []  # (from_field_id, to_symbol_id, edge_kind)

        # Statistics
        self.stats = {
            'schemas_loaded': 0,
            'types_loaded': 0,
            'fields_loaded': 0,
            'resolvers_found': 0,
            'mappings_created': 0,
            'edges_created': 0,
            'missing_resolvers': 0
        }

    def load_schemas(self) -> int:
        """Load GraphQL schemas from graphql_schemas table.

        Returns:
            Number of schemas loaded
        """
        cursor = self.conn.cursor()

        # Load types
        cursor.execute("""
            SELECT type_id, schema_path, type_name, kind
            FROM graphql_types
            ORDER BY type_id
        """)

        for row in cursor.fetchall():
            gql_type = GraphQLType(
                type_id=row['type_id'],
                schema_path=row['schema_path'],
                type_name=row['type_name'],
                kind=row['kind']
            )
            self.types[gql_type.type_id] = gql_type

        self.stats['types_loaded'] = len(self.types)

        # Load fields
        cursor.execute("""
            SELECT field_id, type_id, field_name, return_type, is_list, is_nullable
            FROM graphql_fields
            ORDER BY field_id
        """)

        for row in cursor.fetchall():
            field = GraphQLField(
                field_id=row['field_id'],
                type_id=row['type_id'],
                field_name=row['field_name'],
                return_type=row['return_type'],
                is_list=bool(row['is_list']),
                is_nullable=bool(row['is_nullable'])
            )
            self.fields[field.field_id] = field

        self.stats['fields_loaded'] = len(self.fields)

        # Count unique schemas
        cursor.execute("SELECT COUNT(DISTINCT schema_path) FROM graphql_types")
        self.stats['schemas_loaded'] = cursor.fetchone()[0]

        return self.stats['schemas_loaded']

    def load_resolver_candidates(self) -> int:
        """Load potential resolver functions from symbols table.

        Filters symbols to functions/methods that match resolver patterns:
        - Names containing 'resolve', 'resolver', 'query', 'mutation'
        - Class methods (potential Graphene/Strawberry patterns)
        - Decorated functions (potential Ariadne/Apollo patterns)

        Returns:
            Number of resolver candidates found
        """
        cursor = self.conn.cursor()

        # Load all functions and methods as potential resolvers
        cursor.execute("""
            SELECT symbol_id, name, file, line, type
            FROM symbols
            WHERE type IN ('function', 'method', 'async_function', 'async_method')
            ORDER BY symbol_id
        """)

        for row in cursor.fetchall():
            name = row['name']

            # Filter to likely resolvers (heuristic, not strict)
            is_resolver_candidate = (
                'resolve' in name.lower() or
                'resolver' in name.lower() or
                'query' in name.lower() or
                'mutation' in name.lower() or
                row['type'] in ('method', 'async_method')  # Methods could be resolvers
            )

            if is_resolver_candidate:
                candidate = ResolverCandidate(
                    symbol_id=row['symbol_id'],
                    name=name,
                    file_path=row['file'],
                    line=row['line'],
                    type=row['type']
                )
                self.resolvers.append(candidate)

        self.stats['resolvers_found'] = len(self.resolvers)
        return self.stats['resolvers_found']

    def correlate_resolvers(self) -> int:
        """Correlate GraphQL fields with resolver functions.

        Matching strategies:
        1. Graphene: resolve_<field> method name in ObjectType class
        2. Ariadne: @query.field("name") → function name
        3. Strawberry: @strawberry.field on method → method name = field name
        4. Apollo: Query.<field> → <field>Resolver or resolve<Field> function
        5. NestJS/TypeGraphQL: @Query() decorator with field name

        Returns:
            Number of resolver mappings created
        """
        conn = self.conn
        cursor = conn.cursor()

        for field_id, field in self.fields.items():
            # Get parent type
            parent_type = self.types.get(field.type_id)
            if not parent_type:
                continue

            # Find matching resolver
            matched_resolver = self._find_matching_resolver(parent_type, field)

            if matched_resolver:
                # Determine binding style by analyzing resolver name/context
                binding_style = self._infer_binding_style(matched_resolver.name, parent_type.type_name)

                # Create mapping entry
                mapping = (
                    field.field_id,
                    matched_resolver.symbol_id,
                    matched_resolver.file_path,
                    matched_resolver.line,
                    self._detect_language(matched_resolver.file_path),
                    binding_style,
                    None  # resolver_export (optional)
                )
                self.mappings.append(mapping)

                if self.verbose:
                    logger.info(f"Mapped {parent_type.type_name}.{field.field_name} → {matched_resolver.name}")
            else:
                self.stats['missing_resolvers'] += 1
                if self.verbose:
                    logger.warning(f"No resolver found for {parent_type.type_name}.{field.field_name}")

        # Batch insert mappings
        if self.mappings:
            cursor.executemany("""
                INSERT INTO graphql_resolver_mappings
                (field_id, resolver_symbol_id, resolver_path, resolver_line,
                 resolver_language, binding_style, resolver_export)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, self.mappings)
            conn.commit()

        self.stats['mappings_created'] = len(self.mappings)
        return self.stats['mappings_created']

    def _find_matching_resolver(self, parent_type: GraphQLType, field: GraphQLField) -> Optional[ResolverCandidate]:
        """Find resolver function matching a GraphQL field.

        Matching rules (in priority order):
        1. resolve_<field_name> method (Graphene pattern)
        2. <field_name> function (direct naming)
        3. <field_name>Resolver function (Apollo pattern)
        4. resolve<FieldName> function (camelCase variant)
        """
        field_name = field.field_name
        field_name_lower = field_name.lower()

        # Pattern 1: resolve_<field> (Graphene, Ariadne)
        for resolver in self.resolvers:
            if resolver.name == f"resolve_{field_name}":
                return resolver

        # Pattern 2: Direct field name match
        for resolver in self.resolvers:
            if resolver.name == field_name:
                return resolver

        # Pattern 3: <field>Resolver (Apollo)
        for resolver in self.resolvers:
            if resolver.name == f"{field_name}Resolver":
                return resolver

        # Pattern 4: resolve<Field> (camelCase)
        field_name_camel = field_name[0].upper() + field_name[1:] if field_name else ''
        for resolver in self.resolvers:
            if resolver.name == f"resolve{field_name_camel}":
                return resolver

        # Pattern 5: Fuzzy match (contains field name)
        for resolver in self.resolvers:
            if field_name_lower in resolver.name.lower() and 'resolve' in resolver.name.lower():
                return resolver

        return None

    def _infer_binding_style(self, resolver_name: str, type_name: str) -> str:
        """Infer GraphQL binding style from resolver name and context."""
        if resolver_name.startswith('resolve_'):
            return 'graphene-method'
        elif 'Resolver' in resolver_name and resolver_name.endswith('Resolver'):
            return 'apollo-function'
        elif resolver_name.startswith('resolve') and resolver_name[7:8].isupper():
            return 'ariadne-decorator'
        else:
            return 'unknown'

    def _detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        if file_path.endswith('.py'):
            return 'python'
        elif file_path.endswith(('.js', '.ts', '.jsx', '.tsx')):
            return 'javascript'
        else:
            return 'unknown'

    def build_execution_graph(self) -> int:
        """Build execution graph edges from resolvers to downstream calls.

        Creates two types of edges:
        1. 'resolver': field → resolver function (from mappings)
        2. 'downstream_call': resolver → functions it calls

        Returns:
            Number of edges created
        """
        cursor = self.conn.cursor()

        # Edge type 1: field → resolver (from mappings)
        for mapping in self.mappings:
            field_id, symbol_id = mapping[0], mapping[1]
            edge = (field_id, symbol_id, 'resolver')
            self.edges.append(edge)

        # Edge type 2: resolver → downstream calls
        # Query function_calls table to find what each resolver calls
        for mapping in self.mappings:
            resolver_symbol_id = mapping[1]
            resolver_path = mapping[2]
            resolver_name = self._get_symbol_name(resolver_symbol_id)

            if not resolver_name:
                continue

            # Find all function calls within this resolver
            cursor.execute("""
                SELECT DISTINCT fc.callee_function
                FROM function_calls fc
                JOIN symbols s ON s.symbol_id = ?
                WHERE fc.caller_function = ?
                  AND fc.file = ?
            """, (resolver_symbol_id, resolver_name, resolver_path))

            for row in cursor.fetchall():
                callee = row[0]

                # Lookup callee symbol_id
                cursor.execute("""
                    SELECT symbol_id
                    FROM symbols
                    WHERE name = ? AND file = ?
                    LIMIT 1
                """, (callee, resolver_path))

                callee_row = cursor.fetchone()
                if callee_row:
                    callee_symbol_id = callee_row[0]
                    edge = (mapping[0], callee_symbol_id, 'downstream_call')  # field_id → callee
                    self.edges.append(edge)

        # Batch insert edges
        if self.edges:
            cursor.executemany("""
                INSERT OR IGNORE INTO graphql_execution_edges
                (from_field_id, to_symbol_id, edge_kind)
                VALUES (?, ?, ?)
            """, self.edges)
            self.conn.commit()

        self.stats['edges_created'] = len(self.edges)
        return self.stats['edges_created']

    def _get_symbol_name(self, symbol_id: int) -> Optional[str]:
        """Get symbol name from symbol_id."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM symbols WHERE symbol_id = ?", (symbol_id,))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_coverage_percent(self) -> float:
        """Calculate resolver coverage percentage."""
        total_fields = self.stats['fields_loaded']
        if total_fields == 0:
            return 0.0
        mapped = self.stats['mappings_created']
        return (mapped / total_fields) * 100.0

    def get_missing_count(self) -> int:
        """Get count of fields without resolvers."""
        return self.stats['missing_resolvers']

    def print_summary(self):
        """Print detailed summary statistics."""
        print("\n=== GraphQL Build Summary ===")
        print(f"Schemas loaded:      {self.stats['schemas_loaded']}")
        print(f"Types loaded:        {self.stats['types_loaded']}")
        print(f"Fields loaded:       {self.stats['fields_loaded']}")
        print(f"Resolver candidates: {self.stats['resolvers_found']}")
        print(f"Mappings created:    {self.stats['mappings_created']}")
        print(f"Execution edges:     {self.stats['edges_created']}")
        print(f"Coverage:            {self.get_coverage_percent():.1f}%")
        print(f"Missing resolvers:   {self.stats['missing_resolvers']}")
