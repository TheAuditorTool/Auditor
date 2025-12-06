## ADDED Requirements

### Requirement: Node.js ORM Graph Strategy

The graph builder SHALL include a `NodeOrmStrategy` that creates edges for Node.js ORM relationships.

The strategy SHALL query the following tables:
- `sequelize_models` - Sequelize model definitions
- `sequelize_associations` - Sequelize relationships (hasMany, belongsTo, hasOne)
- `sequelize_model_fields` - Sequelize field definitions

The strategy SHALL create bidirectional edges for ORM relationship expansion (e.g., `User.posts` -> `Post`).

#### Scenario: Sequelize hasMany relationship
- **WHEN** `sequelize_associations` contains a hasMany relationship from User to Post
- **AND** the graph builder runs NodeOrmStrategy
- **THEN** an edge is created from `User::posts` to `Post` entity

#### Scenario: Sequelize belongsTo relationship
- **WHEN** `sequelize_associations` contains a belongsTo relationship from Post to User
- **AND** the graph builder runs NodeOrmStrategy
- **THEN** an edge is created from `Post::author` to `User` entity

#### Scenario: TypeORM relationship handling
- **WHEN** `typeorm_entities` table exists with relationship data
- **AND** the graph builder runs NodeOrmStrategy
- **THEN** edges are created for TypeORM relationships

#### Scenario: Prisma relationship handling
- **WHEN** `prisma_models` table exists with relation fields
- **AND** the graph builder runs NodeOrmStrategy
- **THEN** edges are created for Prisma relations

---

### Requirement: ORM Model Metadata on Graph Nodes

Graph strategies SHALL populate node metadata with ORM model information.

When creating nodes for ORM-related variables, the strategy SHALL set `metadata.model` to the model name.

This metadata SHALL be queryable by the TypeResolver for aliasing detection.

#### Scenario: Python ORM node metadata
- **WHEN** PythonOrmStrategy creates a node for a SQLAlchemy model instance
- **THEN** the node has `metadata.model = 'ModelName'`

#### Scenario: Node ORM node metadata
- **WHEN** NodeOrmStrategy creates a node for a Sequelize model instance
- **THEN** the node has `metadata.model = 'ModelName'`

#### Scenario: Metadata queryable
- **WHEN** TypeResolver queries graph nodes for model metadata
- **THEN** the model name is retrievable from `nodes.metadata` JSON field

---

## MODIFIED Requirements

### Requirement: Graph Strategy Execution Order

The DFGBuilder SHALL execute strategies in the following order:
1. PythonOrmStrategy
2. NodeOrmStrategy (NEW)
3. NodeExpressStrategy
4. InterceptorStrategy

This order ensures ORM relationship edges exist before middleware chain processing.

#### Scenario: Strategy ordering
- **WHEN** `aud graph build` is executed
- **THEN** strategies run in the specified order
- **AND** NodeOrmStrategy edges are available to subsequent strategies

---

### Requirement: Python ORM Strategy Self-Contained

The PythonOrmStrategy SHALL contain all ORM context logic internally.

The strategy SHALL NOT import from `taint/orm_utils.py`.

All `PythonOrmContext` functionality SHALL be inlined into the strategy file.

#### Scenario: No external taint imports
- **WHEN** PythonOrmStrategy module is loaded
- **THEN** no imports exist from `theauditor.taint.*` modules

#### Scenario: Self-contained ORM context
- **WHEN** PythonOrmStrategy builds edges
- **THEN** it uses internal methods to query `python_orm_models` and `python_orm_relationships`

---

## REMOVED Requirements

### Requirement: taint/orm_utils.py Module

**Reason**: Module relocated to graph strategy layer. Logic consolidated into `graph/strategies/python_orm.py`.

**Migration**:
1. All `PythonOrmContext` methods moved to `python_orm.py`
2. Import statement at `python_orm.py:19` removed
3. File deleted from `taint/` directory

The graph layer now owns all ORM relationship logic. The taint layer is a pure consumer of pre-built graph edges.
