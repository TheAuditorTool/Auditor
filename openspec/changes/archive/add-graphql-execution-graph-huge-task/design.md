# Design: GraphQL Resolver Execution Graph

## Verification Summary (SOP v4.20 - UPDATED POST-REFACTOR)

**CRITICAL**: Architecture has been refactored since original design. All references updated to match current codebase structure.

### Verified Absence of GraphQL Support
- `theauditor/indexer/config.py:128-138` - SUPPORTED_AST_EXTENSIONS lacks `.graphql`/`.gql` extensions (VERIFIED)
- `theauditor/indexer/extractors/` - NO graphql.py exists (VERIFIED via directory listing)
- `theauditor/indexer/schemas/` - NO graphql_schema.py exists (VERIFIED)
- `theauditor/indexer/database/` - NO graphql_database.py mixin exists (VERIFIED)
- `.pf/repo_index.db` - NO tables with LIKE '%graphql%' (VERIFIED via sqlite3 query)

### Verified Current Architecture (Post-Refactor)
- **Schema System**: Modular pattern with 7 schema modules in `theauditor/indexer/schemas/` (108 tables total)
  - Verified: core_schema.py, security_schema.py, frameworks_schema.py, python_schema.py, node_schema.py, infrastructure_schema.py, planning_schema.py, utils.py
- **Database Manager**: Mixin-based architecture with 8 components in `theauditor/indexer/database/`
  - Verified: base_database.py, core_database.py, python_database.py, node_database.py, infrastructure_database.py, security_database.py, frameworks_database.py, planning_database.py
- **Storage Layer**: DataStorer class at `theauditor/indexer/storage.py` with 66 handler methods
  - Verified: Handler registry pattern at storage.py:42-110
- **Pipeline Staging**: 4-stage architecture at `theauditor/pipelines.py:594-629`
  - Verified: foundation_commands (Stage 1), data_prep_commands (Stage 2), 3 parallel tracks (Stage 3A/B/C), final_commands (Stage 4)

### Verified String-Based Heuristics (Current State)
- `theauditor/rules/security/api_auth_analyze.py:318-347` - _check_graphql_mutations() uses GRAPHQL_PATTERNS frozenset for string matching (VERIFIED)
- `theauditor/rules/security/api_auth_analyze.py:539-541` - Comment confirms "Can't parse GraphQL schema for auth directives" (VERIFIED)
- `theauditor/fce.py` and `theauditor/taint/sources.py` - NO GraphQL support (VERIFIED via grep)

## Goals
1. Parse GraphQL schemas and resolvers with deterministic AST tooling, persisting canonical metadata into `repo_index.db` and exporting courier artefacts without guessing.
2. Build a resolver execution graph that links GraphQL fields to concrete backend symbols, enabling taint traces, auth analysis, and performance checks across languages.
3. Integrate the new data with the existing pipeline, taint engine, rules orchestrator, and FCE so GraphQL risks surface alongside REST findings using the same database-first guarantees.

## Database Schema Additions

**ARCHITECTURE** (Post-Refactor - VERIFIED):
- Schema definitions: `theauditor/indexer/schemas/graphql_schema.py` (NEW FILE - following modular pattern)
- Database operations: `theauditor/indexer/database/graphql_database.py` (NEW FILE - GraphQLDatabaseMixin)
- Storage handlers: `theauditor/indexer/storage.py` (ADD handlers to existing DataStorer class)
- Registration: Update `schema.py:62-70` to merge GRAPHQL_TABLES, update `database/__init__.py:44-73` to inherit GraphQLDatabaseMixin

**PATTERN** (Verified from frameworks_database.py:10-81):
- Mixin class defines add_* methods (e.g., add_graphql_schema, add_graphql_type, etc.)
- Each method appends to self.generic_batches['table_name']
- BaseDatabaseManager.flush_all_batches() handles INSERT execution
- NO direct SQL in mixin - pure data queueing

| Table | Purpose | Key Columns | Notes |
|-------|---------|-------------|-------|
| `graphql_schemas` | Track each schema file and fingerprint | `file_path` (PK), `schema_hash`, `language` (`'sdl'`, `'code-first'`), `last_modified` | Enables change detection and multi-schema projects. |
| `graphql_types` | Normalised type definitions | `type_id` (PK AUTOINCREMENT), `schema_path` (FK to `graphql_schemas.file_path`), `type_name`, `kind`, `implements`, `description` | One row per type/interface/input/enum. |
| `graphql_fields` | Field metadata per type | `field_id` (PK AUTOINCREMENT), `type_id` FK, `field_name`, `return_type`, `is_list`, `is_nullable`, `directives_json`, `line`, `column` | Captures directives/nullable/list semantics. |
| `graphql_field_args` | Argument definitions | Composite PK `(field_id, arg_name)`, columns: `arg_type`, `has_default`, `default_value`, `is_nullable`, `directives_json` | Normalises arguments instead of JSON blobs. |
| `graphql_resolver_mappings` | Bridge fields to backend code | Composite PK `(field_id, resolver_symbol_id)`, columns: `resolver_path`, `resolver_line`, `resolver_language`, `resolver_export`, `binding_style` (`'apollo-object'`, `'apollo-class'`, `'graphene-decorator'`, etc.) | Links to `symbols` for precise taint + rule queries. |
| `graphql_resolver_params` | Map GraphQL args to function params | Composite PK `(resolver_symbol_id, arg_name)`, columns: `param_name`, `param_index`, `is_kwargs`, `is_list_input` | Enables correct taint parameter mapping. |
| `graphql_execution_edges` | Derived resolver execution graph | Composite PK `(from_field_id, to_symbol_id, edge_kind)`, where `edge_kind` in `('resolver', 'downstream_call')` | `resolver` edges connect field -> resolver symbol; `downstream_call` edges connect resolver symbol -> callee symbol ID sourced from the existing call graph. |
| `graphql_findings_cache` | Optional summary for FCE fast paths | `finding_id` (PK AUTOINCREMENT), `field_id`, `resolver_symbol_id`, `rule`, `severity`, `details_json`, `provenance` | Mirrors other domain caches to avoid recomputing heavy joins inside FCE. |

Batch writers will mirror existing patterns (`self.graphql_schema_batch`, etc.) with `flush_graphql_batches()` invoked during indexer finalisation. Schema validation via `TABLES['graphql_schemas']` et al. ensures migrations stay consistent.

## Extraction Workflow

**CRITICAL ARCHITECTURE RULE** (Verified from storage.py:112-139 and orchestrator.py:30-90):
- Extractors return dict of `{data_type: [records...]}`
- DataStorer receives extracted dict and dispatches to handler methods via registry
- Handlers call DatabaseManager.add_* methods which queue to self.generic_batches
- NO direct database writes in extractors - pure data extraction

### Schema Pass - SDL Extraction

**NEW FILE**: `theauditor/indexer/extractors/graphql.py`

**Pattern** (Verified from extractors/javascript.py, extractors/python.py):
1. Import from `theauditor.indexer.extractors import BaseExtractor, register_extractor`
2. Decorate class with `@register_extractor`
3. Implement `supported_extensions` property returning `['.graphql', '.gql', '.graphqls']`
4. Implement `extract(self, file_info, content, tree)` method returning dict

**Implementation**:
```python
@register_extractor
class GraphQLExtractor(BaseExtractor):
    @property
    def supported_extensions(self):
        return ['.graphql', '.gql', '.graphqls']

    def extract(self, file_info, content, tree):
        # Parse SDL using graphql-core (already vendored per verification)
        # Return dict with keys matching DataStorer handler names:
        return {
            'graphql_schemas': [schema_records...],
            'graphql_types': [type_records...],
            'graphql_fields': [field_records...],
            'graphql_field_args': [arg_records...],
        }
```

**Hash Computation**: Use `hashlib.sha256(ast.to_json().encode()).hexdigest()` for schema_hash to deduplicate

**Directives Storage**: JSON-serialize directive metadata for auth/rate-limit/deprecated analysis

**Code-First Schemas**: JavaScript/Python extractors handle at resolver mapping stage (below)

### Resolver Mapping Pass

**UPDATED FILES**: `theauditor/indexer/extractors/javascript.py`, `theauditor/indexer/extractors/python.py`

**Pattern** (NO FALLBACKS - Verified from CLAUDE.md:131-150):
- AST-based detection ONLY - NO regex fallbacks
- Match against existing `symbols` rows via file path + line/column
- Return new data_types in extracted dict: `'graphql_resolver_mappings'`, `'graphql_resolver_params'`

**JavaScript / TypeScript**:
- Extend AST walkers to detect:
  - Apollo: `const resolvers = { Query: { user: (parent, args) => ... } }`
  - Apollo: `export const resolvers = { ... }`
  - Apollo: `makeExecutableSchema({ resolvers })`
  - NestJS: `@Resolver('Type')` class decorators + `@Query()`, `@Mutation()`, `@ResolveField()` method decorators
  - TypeGraphQL: `@Resolver()` classes with `@Query()` methods
- Resolve function identifiers to symbols table by matching (file, line, column) - NO guessing
- Return dict with:
  ```python
  {
      'graphql_resolver_mappings': [(field_key, symbol_id, binding_style, ...)],
      'graphql_resolver_params': [(symbol_id, arg_name, param_name, param_index, ...)],
  }
  ```

**Python**:
- Extend AST walkers to detect:
  - Graphene: `class UserType(graphene.ObjectType):` with field resolvers
  - Ariadne: `@query.field("user")` decorators
  - Strawberry: `@strawberry.type` classes with field methods
- Match to symbols via AST node location (file, line) - NO string matching
- Capture decorator metadata for binding_style classification
- Return same dict structure as JavaScript

**CRITICAL**: Both extractors return data dicts - DataStorer handlers insert to DB via DatabaseManager add_* methods

## Resolver Execution Graph
- After indexer batches flush, invoke a lightweight builder inside the new `aud graphql build` command that:
  1. Reads `graphql_resolver_mappings` and `symbols` to create `resolver` edges (field -> resolver symbol).
  2. Joins the call graph from `.pf/graphs.db` (call edges) to materialise `downstream_call` edges for each resolver's callees, storing them in `graphql_execution_edges`. This reuses the existing call graph rather than recomputing static analysis.
  3. Generates adjacency lists for taint (field -> resolver params) and for rule queries (e.g., fetch all DB calls reachable from a resolver).
- The builder exports `.pf/raw/graphql_execution.json` containing a serialised view (types, fields, resolver symbol metadata, immediate downstream calls) with provenance for each edge, keeping JSON consumers in sync with the SQLite truth.

## Pipeline & CLI Integration

**NEW FILE**: `theauditor/commands/graphql.py`

**Pattern** (Verified from commands/ directory structure):
```python
import click
from theauditor.utils.decorators import handle_exceptions
from theauditor.utils.logger import setup_logger

@click.group()
def graphql():
    """GraphQL schema and resolver analysis commands."""
    pass

@graphql.command('build')
@handle_exceptions
def graphql_build():
    """Build GraphQL execution graph from indexed data."""
    # Implementation

@graphql.command('analyze')
@handle_exceptions
def graphql_analyze():
    """Analyze GraphQL schema coverage (manual inspection)."""
    # Implementation

@graphql.command('dump')
@handle_exceptions
def graphql_dump():
    """Dump GraphQL data to JSON for debugging."""
    # Implementation
```

**CLI Registration** (Update `theauditor/cli.py`):
```python
from theauditor.commands import graphql
cli.add_command(graphql.graphql)
```

**Pipeline Integration** (Update `theauditor/pipelines.py:605-629`):

**CRITICAL** (Verified from pipelines.py:594-629):
- Stage 1: foundation_commands (index, detect-frameworks)
- Stage 2: data_prep_commands (workset, graph build, graph build-dfg, terraform provision, cfg)
- Stage 3A: track_a_commands (taint)
- Stage 3B: track_b_commands (static, patterns, detect-patterns)
- Stage 3C: track_c_commands (deps, docs)
- Stage 4: final_commands (fce, lint, report)

**Categorization Logic** (Add after line 628):
```python
elif "graphql build" in cmd_str:
    data_prep_commands.append((phase_name, cmd))
```

**Reasoning**: GraphQL build must run AFTER index (Stage 1) to read symbols table, BEFORE taint analysis (Stage 3A) to provide resolver sources. Place in data_prep_commands (Stage 2) alongside graph build-dfg.

**Status Reporting**: Ensure `.pf/status/graphql_build.status` written using existing status_manager pattern (verified at pipelines.py)

## Storage Handler Registration

**UPDATE FILE**: `theauditor/indexer/storage.py`

**Pattern** (Verified from storage.py:42-110):
Add handler methods to DataStorer class and register in `self.handlers` dict at `__init__`:

```python
# In DataStorer.__init__ (storage.py:42-110)
self.handlers = {
    # ... existing 66 handlers ...
    'graphql_schemas': self._store_graphql_schemas,
    'graphql_types': self._store_graphql_types,
    'graphql_fields': self._store_graphql_fields,
    'graphql_field_args': self._store_graphql_field_args,
    'graphql_resolver_mappings': self._store_graphql_resolver_mappings,
    'graphql_resolver_params': self._store_graphql_resolver_params,
}

# Handler implementation pattern (after line ~1800)
def _store_graphql_schemas(self, file_path: str, schemas: List, jsx_pass: bool):
    """Store GraphQL schema records."""
    for schema_record in schemas:
        self.db_manager.add_graphql_schema(
            file_path=schema_record['file_path'],
            schema_hash=schema_record['schema_hash'],
            language=schema_record['language'],
            last_modified=schema_record.get('last_modified'),
        )
        self.counts['graphql_schemas'] = self.counts.get('graphql_schemas', 0) + 1

# Similar for _store_graphql_types, _store_graphql_fields, etc.
```

**CRITICAL** (NO FALLBACKS - Verified from CLAUDE.md:131-150):
- NO try/except around db_manager calls
- NO fallback to JSON if DB write fails
- Hard failure is correct behavior (database MUST work)

## Taint & Graph Integration
- Extend `theauditor/taint/sources.py` to include dynamic GraphQL sources registered at runtime: for each `graphql_fields` row, add a `GraphQLFieldSource` entry mapping GraphQL argument names to resolver parameter slots via `graphql_resolver_params`.
- Update `theauditor/taint/database.py` and `memory_cache.py` to preload the new tables into in-memory structures (`cache.graphql_fields`, `cache.graphql_resolver_edges`), enabling O(1) lookups when seeding taint flows.
- Modify `theauditor/taint/core.py` so the initial frontier includes GraphQL field arguments, automatically linking them to resolver parameters; the propagation step then leverages existing call graph edges (plus `graphql_execution_edges`) to reach sinks.
- Integrate GraphQL nodes into the existing graph database (`theauditor/graph/store.py`) by adding a `graph_type='graphql'` edge set, allowing impact analysis and context commands to traverse GraphQL relationships alongside imports/calls.

## Rules & FCE

**CRITICAL** (Verified from rules/progress.md - Post-Refactor Pattern):
- SQL queries use EXACT matches, Python does filtering AFTER fetch
- NO `LIKE '%pattern%'` in WHERE clauses
- File filtering via RuleMetadata exclude_patterns, NOT SQL
- Pattern definitions use frozen dataclasses
- All table/column references via build_query() anchored to schema.py

**NEW PACKAGE**: `theauditor/rules/graphql/` with 4 orchestrator-compliant modules:

### auth.py - GraphQL Mutation/Query Auth Detection

**Pattern Definitions** (Frozen Dataclass):
```python
@dataclass(frozen=True)
class GraphQLAuthPatterns:
    # Decorators
    AUTH_DECORATORS = frozenset([
        '@authenticated', '@requiresAuth', '@login_required',
        '@UseGuards', 'AuthGuard', 'JwtGuard', 'LocalGuard',
        '@Authorized', '@RequiresAuthentication', '@Protected'
    ])

    # Schema Directives
    AUTH_DIRECTIVES = frozenset([
        '@auth', '@authenticated', '@requiresAuth', '@requiresRole',
        '@hasPermission', '@private', '@protected', '@secured'
    ])

    # Function Calls
    AUTH_FUNCTIONS = frozenset([
        'authenticate', 'verifyToken', 'checkAuth', 'requireAuth',
        'ensureAuthenticated', 'validateToken', 'decodeToken'
    ])

    # Sensitive Operations (mutations that MUST have auth)
    SENSITIVE_MUTATIONS = frozenset([
        'create', 'update', 'delete', 'upsert', 'remove',
        'edit', 'modify', 'save', 'destroy', 'insert'
    ])
```

**Detection Logic**:
```python
def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    patterns = GraphQLAuthPatterns()

    # Step 1: Get all mutations from graphql_fields
    query = build_query('graphql_fields',
        ['field_id', 'type_id', 'field_name', 'directives_json'],
        where="type_id IN (SELECT type_id FROM graphql_types WHERE type_name = 'Mutation')")

    for field_id, type_id, field_name, directives_json in context.cursor.fetchall():
        # Step 2: Check schema directives first
        directives = json.loads(directives_json or '[]')
        if any(d['name'] in patterns.AUTH_DIRECTIVES for d in directives):
            continue  # Has auth directive

        # Step 3: Get resolver for this field
        resolver_query = build_query('graphql_resolver_mappings',
            ['resolver_symbol_id', 'resolver_path', 'resolver_line'],
            where=f"field_id = {field_id}")

        # Step 4: Check resolver for auth decorators/calls
        # JOIN with function_call_args to find auth function calls
        # Python-side: filter test files, check patterns

    return findings
```

**Metadata**:
- rule_id: `graphql-mutation-no-auth`
- severity: `HIGH` (unauthenticated mutation), `CRITICAL` (if PII/financial field involved)
- CWE: CWE-285, CWE-306
- OWASP: A01:2021 - Broken Access Control

### injection.py - GraphQL Argument Injection Detection

**Pattern Definitions**:
```python
@dataclass(frozen=True)
class GraphQLInjectionPatterns:
    # SQL sinks
    SQL_SINKS = frozenset([
        'execute', 'query', 'raw', 'rawQuery', 'executeRaw',
        'createQueryBuilder', 'QueryBuilder', 'knex.raw'
    ])

    # Sanitization functions
    SANITIZERS = frozenset([
        'escape', 'escapeString', 'sanitize', 'parameterize',
        'prepared', 'bind', 'placeholder', 'safeQuery'
    ])

    # Command sinks
    COMMAND_SINKS = frozenset([
        'exec', 'spawn', 'execSync', 'spawnSync', 'child_process',
        'eval', 'Function', 'require', 'import'
    ])
```

**Detection Logic**:
```python
def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    # Step 1: Get GraphQL field arguments as taint sources
    query = build_query('graphql_field_args',
        ['field_id', 'arg_name', 'arg_type'])

    # Step 2: Map to resolver parameters via graphql_resolver_params
    param_query = build_query('graphql_resolver_params',
        ['resolver_symbol_id', 'arg_name', 'param_name', 'param_index'])

    # Step 3: Check taint_flows for flows from resolver params to sinks
    taint_query = build_query('taint_flows',
        ['source_id', 'sink_id', 'flow_path'])

    # Step 4: Verify no sanitization in flow_path
    # Python-side: parse flow_path JSON, check for sanitizer function calls

    return findings
```

**Leverages**: Existing taint engine with new GraphQL sources

### nplus1.py - GraphQL N+1 Query Detection

**Pattern Definitions**:
```python
@dataclass(frozen=True)
class GraphQLNPlus1Patterns:
    # ORM query methods
    ORM_QUERIES = frozenset([
        'findOne', 'findById', 'findUnique', 'get', 'fetch',
        'load', 'query', 'select', 'where', 'filter'
    ])

    # DB client methods
    DB_QUERIES = frozenset([
        'execute', 'query', 'raw', 'sql', 'connection.query'
    ])
```

**Detection Logic**:
```python
def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    # Step 1: Find list-returning fields
    query = build_query('graphql_fields',
        ['field_id', 'type_id', 'field_name', 'return_type', 'is_list'],
        where="is_list = 1")

    for parent_field in context.cursor.fetchall():
        # Step 2: Get child fields of return type
        child_query = build_query('graphql_fields',
            ['field_id', 'field_name'],
            where=f"type_id = '{parent_field.return_type}'")

        # Step 3: For each child, get resolver
        # Step 4: Check if resolver calls DB inside loop
        # JOIN: graphql_resolver_mappings → symbols → cfg_blocks (kind='loop')
        # Check: orm_queries or sql_queries inside loop block

    return findings
```

**Severity**: `MEDIUM` (10-100 iterations), `HIGH` (>100 iterations)

### overfetch.py - GraphQL Sensitive Field Exposure

**Pattern Definitions**:
```python
@dataclass(frozen=True)
class GraphQLOverfetchPatterns:
    SENSITIVE_FIELDS = frozenset([
        # PII
        'ssn', 'social_security', 'creditCard', 'credit_card', 'cardNumber',
        'cvv', 'password', 'passwordHash', 'apiKey', 'api_key', 'secretKey',
        'privateKey', 'token', 'accessToken', 'refreshToken', 'sessionId',
        # Financial
        'bankAccount', 'routingNumber', 'accountNumber', 'balance', 'salary',
        # Health
        'medicalRecord', 'diagnosis', 'prescription', 'healthRecord'
    ])
```

**Detection Logic**:
```python
def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    # Step 1: Get ORM model fields
    orm_query = build_query('python_orm_fields',
        ['model_name', 'field_name', 'field_type'])

    # Step 2: Get GraphQL schema fields
    graphql_query = build_query('graphql_fields',
        ['type_id', 'field_name', 'return_type'])

    # Step 3: Find ORM fields NOT in GraphQL schema
    # Python-side: check if field_name.lower() in SENSITIVE_FIELDS
    # If sensitive field exists in ORM but not GraphQL schema, check resolver

    return findings
```

**All Rules Share**:
- RuleMetadata with exclude_patterns (test/, spec., __tests__, fixtures/)
- build_query() for all table access (schema-contract compliance)
- Frozen dataclass patterns
- Findings write to findings_consolidated with provenance
- Python-side filtering AFTER SQL fetch

**FCE Integration**:
- Enhance `theauditor/fce.py` to query graphql_findings_cache OR join findings_consolidated WHERE rule LIKE 'graphql-%'
- Merge into report_summary.json with new `graphql` section
- Provenance links back to graphql_fields/graphql_resolver_mappings rows

## Outputs & Courier Artefacts
- `.pf/raw/graphql_schema.json` containing schemas, types, fields, and argument metadata with table row IDs for provenance.
- `.pf/raw/graphql_execution.json` capturing resolver bindings, downstream calls, and derived checksums.
- `.pf/readthis/graphql_schema_*.json` / `.pf/readthis/graphql_execution_*.json` chunked via `theauditor.extraction._chunk_large_file` respecting courier limits, ensuring AI assistants can ingest slices offline.
- `graphql` section in `.pf/raw/report_summary.json` summarising counts of secured vs. unsecured resolvers, detected vulnerabilities, and directive coverage.

## Non-Goals & Follow-Ups
- Do not implement mutation performance profiling or caching heuristics in this change; focus on structural truth. Future work can extend `aud graphql analyze` with latency estimations once tracing data exists.
- Insights scoring remains out of scope; GraphQL findings stay in the Truth Courier lane with no interpretive severity adjustments beyond rule metadata.
