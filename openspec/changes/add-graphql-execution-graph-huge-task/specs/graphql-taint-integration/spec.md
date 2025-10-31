## ADDED Requirements

### Requirement: GraphQL Field Arguments as Taint Sources
The taint engine MUST register GraphQL field arguments as untrusted input sources with parameter mappings.

#### Scenario: Taint Source Registration Code
- **GIVEN** `theauditor/taint/sources.py` defines taint sources
- **WHEN** adding GraphQL support
- **THEN** it includes GraphQLFieldSource class:
```python
from typing import Dict, List, Optional
from dataclasses import dataclass
import sqlite3
from theauditor.indexer.schema import build_query


@dataclass
class GraphQLFieldSource:
    """Represents a GraphQL field argument as a taint source."""
    field_id: int
    field_name: str
    type_name: str  # Parent type (Query, Mutation, etc.)
    arg_name: str
    arg_type: str
    resolver_symbol_id: int
    param_name: str
    param_index: int
    file_path: str
    line: int


def load_graphql_sources(cursor: sqlite3.Cursor) -> List[GraphQLFieldSource]:
    """Load GraphQL field arguments as taint sources.

    This function queries graphql_field_args, graphql_fields, graphql_types,
    graphql_resolver_mappings, and graphql_resolver_params to build complete
    taint source entries.

    Returns:
        List of GraphQLFieldSource objects representing untrusted inputs
    """
    sources = []

    # Step 1: Get all GraphQL field arguments
    query = build_query('graphql_field_args',
        ['field_id', 'arg_name', 'arg_type'])
    cursor.execute(query)
    field_args = cursor.fetchall()

    for field_id, arg_name, arg_type in field_args:
        # Step 2: Get field info (name, parent type)
        field_query = build_query('graphql_fields',
            ['type_id', 'field_name', 'line'],
            where=f"field_id = {field_id}")
        cursor.execute(field_query)
        field_row = cursor.fetchone()
        if not field_row:
            continue
        type_id, field_name, field_line = field_row

        # Step 3: Get type name (Query, Mutation, etc.)
        type_query = build_query('graphql_types',
            ['type_name'],
            where=f"type_id = {type_id}")
        cursor.execute(type_query)
        type_row = cursor.fetchone()
        if not type_row:
            continue
        type_name = type_row[0]

        # Step 4: Get resolver mapping
        resolver_query = build_query('graphql_resolver_mappings',
            ['resolver_symbol_id', 'resolver_path'],
            where=f"field_id = {field_id}")
        cursor.execute(resolver_query)
        resolver_row = cursor.fetchone()
        if not resolver_row:
            continue  # Field has no resolver yet
        resolver_symbol_id, resolver_path = resolver_row

        # Step 5: Get parameter mapping
        param_query = build_query('graphql_resolver_params',
            ['param_name', 'param_index'],
            where=f"resolver_symbol_id = {resolver_symbol_id} AND arg_name = '{arg_name}'")
        cursor.execute(param_query)
        param_row = cursor.fetchone()
        if not param_row:
            continue  # Argument not mapped to parameter
        param_name, param_index = param_row

        # Create taint source
        sources.append(GraphQLFieldSource(
            field_id=field_id,
            field_name=field_name,
            type_name=type_name,
            arg_name=arg_name,
            arg_type=arg_type,
            resolver_symbol_id=resolver_symbol_id,
            param_name=param_name,
            param_index=param_index,
            file_path=resolver_path,
            line=field_line
        ))

    return sources


# Add to existing source loading function
def load_all_sources(cursor: sqlite3.Cursor) -> Dict[str, List]:
    """Load all taint sources from database.

    Returns:
        Dictionary mapping source type to list of source objects
    """
    return {
        'http': load_http_sources(cursor),
        'websocket': load_websocket_sources(cursor),
        'env_vars': load_env_var_sources(cursor),
        'graphql': load_graphql_sources(cursor),  # NEW
        # ... other source types
    }
```
- **AND** GraphQL sources are loaded alongside existing HTTP/WebSocket sources
- **AND** each source has complete resolver parameter mapping
- **AND** NO fallbacks if resolver mapping missing (hard fail with debug log)

### Requirement: Taint Engine Frontier Seeding
The taint core module MUST seed initial frontier with GraphQL argument locations.

#### Scenario: Frontier Initialization Includes GraphQL
- **GIVEN** `theauditor/taint/core.py` initializes taint propagation frontier
- **WHEN** beginning taint analysis
- **THEN** it seeds GraphQL sources:
```python
def initialize_frontier(cursor: sqlite3.Cursor) -> List[TaintNode]:
    """Initialize taint propagation frontier with all source types.

    Returns:
        List of TaintNode objects representing untrusted inputs
    """
    frontier = []

    # Load all source types
    sources = load_all_sources(cursor)

    # Add HTTP sources
    for http_source in sources['http']:
        frontier.append(TaintNode(
            symbol_id=http_source.handler_symbol_id,
            param_index=http_source.param_index,
            param_name=http_source.param_name,
            source_type='http',
            file_path=http_source.file_path,
            line=http_source.line
        ))

    # Add GraphQL sources (NEW)
    for graphql_source in sources['graphql']:
        frontier.append(TaintNode(
            symbol_id=graphql_source.resolver_symbol_id,
            param_index=graphql_source.param_index,
            param_name=graphql_source.param_name,
            source_type='graphql',
            source_metadata={
                'field_id': graphql_source.field_id,
                'field_name': graphql_source.field_name,
                'type_name': graphql_source.type_name,
                'arg_name': graphql_source.arg_name,
                'arg_type': graphql_source.arg_type
            },
            file_path=graphql_source.file_path,
            line=graphql_source.line
        ))

    # Add WebSocket, env_vars, etc.
    # ...

    return frontier
```
- **AND** GraphQL nodes include metadata for provenance tracking
- **AND** frontier initialization happens before propagation loop
- **AND** GraphQL sources treated identically to HTTP sources in propagation

### Requirement: Taint Propagation Through Execution Edges
The taint propagation step MUST follow graphql_execution_edges for downstream calls.

#### Scenario: Propagation Leverages Execution Graph
- **GIVEN** taint engine propagates through call graph
- **WHEN** processing GraphQL taint nodes
- **THEN** it queries execution edges:
```python
def propagate_taint(cursor: sqlite3.Cursor, frontier: List[TaintNode]) -> List[TaintFlow]:
    """Propagate taint from sources to sinks through call graph and execution edges.

    Returns:
        List of TaintFlow objects representing source→sink paths
    """
    flows = []
    visited = set()

    while frontier:
        node = frontier.pop(0)
        node_key = (node.symbol_id, node.param_index)

        if node_key in visited:
            continue
        visited.add(node_key)

        # Check if this node is a sink
        if is_sink(cursor, node.symbol_id):
            flows.append(TaintFlow(
                source=node.source_metadata,
                sink_symbol_id=node.symbol_id,
                path=node.path
            ))
            continue

        # Propagate through regular call graph
        call_edges = get_call_edges(cursor, node.symbol_id)
        for callee_symbol_id in call_edges:
            frontier.append(propagate_to_callee(node, callee_symbol_id))

        # Propagate through GraphQL execution edges (NEW)
        if node.source_type == 'graphql':
            exec_query = build_query('graphql_execution_edges',
                ['to_symbol_id', 'edge_kind'],
                where=f"from_field_id = {node.source_metadata['field_id']}")
            cursor.execute(exec_query)

            for to_symbol_id, edge_kind in cursor.fetchall():
                if edge_kind == 'downstream_call':
                    frontier.append(TaintNode(
                        symbol_id=to_symbol_id,
                        param_index=0,  # Flow enters via first param
                        param_name='_taint',
                        source_type='graphql',
                        source_metadata=node.source_metadata,
                        file_path=node.file_path,
                        line=node.line,
                        path=node.path + [to_symbol_id]
                    ))

    return flows
```
- **AND** execution edges provide additional propagation paths beyond call graph
- **AND** taint flows preserve GraphQL metadata for finding generation
- **AND** both 'resolver' and 'downstream_call' edges are traversed

### Requirement: Memory Cache Preloading
The memory cache MUST preload GraphQL tables for O(1) lookup performance.

#### Scenario: Cache Initialization Includes GraphQL
- **GIVEN** `theauditor/taint/memory_cache.py` preloads tables for performance
- **WHEN** initializing cache
- **THEN** it loads GraphQL data:
```python
class TaintCache:
    """In-memory cache of database tables for fast taint analysis."""

    def __init__(self, cursor: sqlite3.Cursor):
        """Load all tables into memory for O(1) lookups."""
        # Existing caches
        self.symbols = self._load_symbols(cursor)
        self.call_edges = self._load_call_edges(cursor)
        self.function_calls = self._load_function_calls(cursor)

        # GraphQL caches (NEW)
        self.graphql_fields = self._load_graphql_fields(cursor)
        self.graphql_resolver_mappings = self._load_graphql_resolver_mappings(cursor)
        self.graphql_execution_edges = self._load_graphql_execution_edges(cursor)

    def _load_graphql_fields(self, cursor: sqlite3.Cursor) -> Dict[int, dict]:
        """Load graphql_fields into memory indexed by field_id."""
        query = build_query('graphql_fields',
            ['field_id', 'type_id', 'field_name', 'return_type', 'is_list'])
        cursor.execute(query)

        return {
            field_id: {
                'type_id': type_id,
                'field_name': field_name,
                'return_type': return_type,
                'is_list': bool(is_list)
            }
            for field_id, type_id, field_name, return_type, is_list in cursor.fetchall()
        }

    def _load_graphql_resolver_mappings(self, cursor: sqlite3.Cursor) -> Dict[int, int]:
        """Load resolver mappings indexed by field_id → resolver_symbol_id."""
        query = build_query('graphql_resolver_mappings',
            ['field_id', 'resolver_symbol_id'])
        cursor.execute(query)

        return {field_id: symbol_id for field_id, symbol_id in cursor.fetchall()}

    def _load_graphql_execution_edges(self, cursor: sqlite3.Cursor) -> Dict[int, List[int]]:
        """Load execution edges indexed by from_field_id → [to_symbol_ids]."""
        query = build_query('graphql_execution_edges',
            ['from_field_id', 'to_symbol_id', 'edge_kind'])
        cursor.execute(query)

        edges = {}
        for from_field_id, to_symbol_id, edge_kind in cursor.fetchall():
            if from_field_id not in edges:
                edges[from_field_id] = []
            edges[from_field_id].append(to_symbol_id)

        return edges

    def get_resolver_for_field(self, field_id: int) -> Optional[int]:
        """O(1) lookup of resolver symbol ID for a GraphQL field."""
        return self.graphql_resolver_mappings.get(field_id)

    def get_downstream_calls(self, field_id: int) -> List[int]:
        """O(1) lookup of downstream call targets from a GraphQL field."""
        return self.graphql_execution_edges.get(field_id, [])
```
- **AND** cache is initialized once at taint analysis start
- **AND** all table loading uses build_query for schema compliance
- **AND** cache provides O(1) lookups via dict indexing

### Requirement: Graph Database Integration
GraphQL execution edges MUST be queryable via graph store for impact analysis.

#### Scenario: Graph Store Includes GraphQL Edge Type
- **GIVEN** `theauditor/graph/store.py` stores typed edges
- **WHEN** adding GraphQL support
- **THEN** it supports 'graphql' edge type:
```python
def load_graphql_edges(cursor: sqlite3.Cursor) -> List[Edge]:
    """Load GraphQL execution edges into graph database.

    Returns:
        List of Edge objects with graph_type='graphql'
    """
    edges = []

    query = build_query('graphql_execution_edges',
        ['from_field_id', 'to_symbol_id', 'edge_kind'])
    cursor.execute(query)

    for from_field_id, to_symbol_id, edge_kind in cursor.fetchall():
        # Get source symbol ID from resolver mapping
        resolver_query = build_query('graphql_resolver_mappings',
            ['resolver_symbol_id'],
            where=f"field_id = {from_field_id}")
        cursor.execute(resolver_query)
        resolver_row = cursor.fetchone()
        if not resolver_row:
            continue
        from_symbol_id = resolver_row[0]

        edges.append(Edge(
            from_id=from_symbol_id,
            to_id=to_symbol_id,
            edge_type=edge_kind,  # 'resolver' or 'downstream_call'
            graph_type='graphql',
            metadata={'field_id': from_field_id}
        ))

    return edges


# Update main graph loading
def build_graph(cursor: sqlite3.Cursor) -> Graph:
    """Build complete code graph including all edge types."""
    graph = Graph()

    # Load existing edge types
    graph.add_edges(load_import_edges(cursor), graph_type='import')
    graph.add_edges(load_call_edges(cursor), graph_type='call')

    # Load GraphQL edges (NEW)
    graph.add_edges(load_graphql_edges(cursor), graph_type='graphql')

    return graph
```
- **AND** GraphQL edges coexist with import/call edges
- **AND** impact analysis can traverse GraphQL relationships
- **AND** context commands (aud context query) can show GraphQL connections
