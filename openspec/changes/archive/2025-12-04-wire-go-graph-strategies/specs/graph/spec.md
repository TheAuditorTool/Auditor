## ADDED Requirements

### Requirement: Go HTTP Strategy Registration
The DFG builder SHALL include GoHttpStrategy in the strategies list.

#### Scenario: GoHttpStrategy import
- **WHEN** dfg_builder.py is loaded
- **THEN** GoHttpStrategy SHALL be imported from `theauditor/graph/strategies/go_http.py`
- **AND** import location SHALL be `theauditor/graph/dfg_builder.py:14` (alphabetical order after bash_pipes)

#### Scenario: GoHttpStrategy registration
- **WHEN** the DFGBuilder is initialized
- **THEN** GoHttpStrategy() SHALL be included in the `self.strategies` list
- **AND** wiring location SHALL be `theauditor/graph/dfg_builder.py:36` (after BashPipeStrategy)

#### Scenario: Go HTTP middleware edges
- **WHEN** DFGBuilder.build_unified_flow_graph() executes
- **THEN** GoHttpStrategy.build() SHALL be called
- **AND** it SHALL query `go_middleware` table for middleware chain data
- **AND** it SHALL query `go_routes` table for route-to-handler mappings
- **AND** it SHALL create edges with edge_type='go_middleware_chain' and 'go_route_handler'

### Requirement: Go ORM Strategy Registration
The DFG builder SHALL include GoOrmStrategy in the strategies list.

#### Scenario: GoOrmStrategy import
- **WHEN** dfg_builder.py is loaded
- **THEN** GoOrmStrategy SHALL be imported from `theauditor/graph/strategies/go_orm.py`
- **AND** import location SHALL be `theauditor/graph/dfg_builder.py:15` (alphabetical order after go_http)

#### Scenario: GoOrmStrategy registration
- **WHEN** the DFGBuilder is initialized
- **THEN** GoOrmStrategy() SHALL be included in the `self.strategies` list
- **AND** wiring location SHALL be `theauditor/graph/dfg_builder.py:37` (after GoHttpStrategy)

#### Scenario: Go ORM relationship edges
- **WHEN** DFGBuilder.build_unified_flow_graph() executes
- **THEN** GoOrmStrategy.build() SHALL be called
- **AND** it SHALL query `go_struct_fields` table for GORM/SQLx/Ent models
- **AND** it SHALL create edges with edge_type='go_orm_has_many', 'go_orm_belongs_to', etc.

### Requirement: ZERO FALLBACK Compliance
Strategy execution SHALL follow ZERO FALLBACK policy.

#### Scenario: Empty table handling
- **WHEN** `go_middleware`, `go_routes`, or `go_struct_fields` tables are empty
- **THEN** strategies SHALL return `{"nodes": [], "edges": [], "metadata": {...}}`
- **AND** strategies SHALL NOT crash or throw exceptions
- **AND** strategies SHALL NOT use try-except fallback logic

#### Scenario: Strategy failure
- **WHEN** a Go strategy fails for any reason other than empty tables
- **THEN** the failure SHALL propagate up (crash the build)
- **AND** the failure SHALL NOT be silently swallowed
- **AND** per dfg_builder.py:614-615 comment: "ZERO FALLBACK: Strategy failures must CRASH"
