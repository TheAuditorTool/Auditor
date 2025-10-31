# Taint Analysis Specification Delta

**Capability**: `taint-analysis`
**Change ID**: `refactor-taint-schema-driven-architecture`

---

## MODIFIED Requirements

### Requirement: Taint Analysis Architecture

The taint analysis system SHALL use schema-driven architecture where schema definitions automatically generate data access infrastructure.

**Architecture Contract**:
- Schema SHALL auto-generate TypedDicts for type safety
- Schema SHALL auto-generate accessor classes for query methods
- Schema SHALL auto-generate memory cache loader for all tables
- Memory cache SHALL always be loaded (no optional fallback)
- Source and sink discovery SHALL be database-driven (no hardcoded patterns)
- CFG-based analysis SHALL use single unified implementation (no duplicates)

#### Scenario: Adding new table to schema

- **WHEN** developer adds new table definition to schema.py
- **THEN** TypedDict SHALL be auto-generated for the table
- **AND** accessor class SHALL be auto-generated with get_all() and get_by_{indexed_column}() methods
- **AND** memory cache loader SHALL automatically load the table on initialization
- **AND** taint analysis SHALL have immediate access to table data without manual loader code

#### Scenario: Taint analysis initialization

- **WHEN** TaintAnalyzer is instantiated with database path
- **THEN** SchemaMemoryCache SHALL load all 70 tables into memory automatically
- **AND** indexes SHALL be built for all columns marked as indexed in schema
- **AND** memory usage SHALL stay within 500MB for projects up to 200K LOC
- **AND** subsequent taint queries SHALL use in-memory data exclusively (no disk queries)

#### Scenario: Source discovery

- **WHEN** taint analyzer discovers sources
- **THEN** sources SHALL be discovered by querying actual database tables (api_endpoints, symbols, function_call_args)
- **AND** sources SHALL NOT be discovered by searching for hardcoded patterns
- **AND** discovery SHALL classify sources based on metadata (has_auth flag, endpoint type, property access patterns)
- **AND** risk assessment SHALL be data-driven (public endpoints = high risk, authenticated = medium risk)

#### Scenario: Sink discovery

- **WHEN** taint analyzer discovers sinks
- **THEN** sinks SHALL be discovered from specialized tables (sql_queries, orm_queries, react_hooks, function_call_args)
- **AND** SQL sinks SHALL be assessed for risk based on query structure (concatenation = high, parameterized = low)
- **AND** XSS sinks SHALL be discovered from react_hooks table with DOM manipulation patterns
- **AND** command sinks SHALL be discovered from function_call_args with exec/spawn patterns
- **AND** sinks SHALL NOT be discovered by searching for hardcoded pattern lists

#### Scenario: CFG-based interprocedural analysis

- **WHEN** taint analyzer performs interprocedural analysis
- **THEN** analysis SHALL use single unified CFG-based implementation
- **AND** analysis SHALL query cfg_blocks, cfg_edges, cfg_block_statements from memory cache
- **AND** analysis SHALL NOT fall back to flow-insensitive implementation
- **AND** path feasibility SHALL be verified using CFG block traversal

#### Scenario: Adding new taint feature (e.g., Vue v-model XSS)

- **WHEN** developer adds Vue v-model XSS detection feature
- **THEN** developer SHALL modify 3 layers maximum:
  1. AST parser (extract v-model from Vue templates)
  2. Schema definition (define vue_directives table)
  3. Taint analyzer (add v-model classification in discover_sinks)
- **AND** developer SHALL NOT write manual cache loader (auto-generated)
- **AND** developer SHALL NOT write manual query functions (accessor auto-generated)
- **AND** developer SHALL NOT add hardcoded patterns to registry (database-driven)
- **AND** feature SHALL be immediately usable after schema + analyzer changes

#### Scenario: Memory cache always available

- **WHEN** any taint module requires database access
- **THEN** module SHALL use memory cache attributes directly (cache.symbols, cache.assignments)
- **AND** module SHALL NOT query database with SQL (no cursor.execute calls)
- **AND** module SHALL NOT check if cache is available (cache always exists)
- **AND** module SHALL NOT have fallback logic to disk queries

---

## Technical Implementation Notes

**Auto-Generated Infrastructure** (from schema.py):
```python
# TypedDict (auto-generated)
class SymbolRow(TypedDict):
    id: int
    path: str
    name: str
    type: str
    line: int
    # ... all columns

# Accessor class (auto-generated)
class SymbolsTable:
    @staticmethod
    def get_all(cursor) -> List[SymbolRow]: ...

    @staticmethod
    def get_by_path(cursor, path: str) -> List[SymbolRow]: ...

# Memory cache (auto-generated)
class SchemaMemoryCache:
    def __init__(self, db_path):
        # Loads ALL 70 tables automatically
        self.symbols = ...
        self.symbols_by_path = ...  # Indexed access
        # ... all tables + indexes
```

**Database-Driven Discovery**:
```python
class TaintAnalyzer:
    def discover_sources(self):
        # Query actual tables, classify results
        for endpoint in self.cache.api_endpoints:
            if not endpoint['has_auth']:
                yield source(type='http', risk='high')

    def discover_sinks(self):
        # Query specialized tables
        for query_row in self.cache.sql_queries:
            risk = assess_sql_risk(query_row['query_text'])
            yield sink(type='sql', risk=risk)
```

**Eliminated Anti-Patterns**:
- ❌ Manual cache loaders (40+ functions) → Auto-generated
- ❌ Hardcoded pattern registries (sources.py, config.py) → Database-driven
- ❌ Optional cache with fallback (database.py, 1,447 lines) → Mandatory cache
- ❌ Duplicate CFG implementations (3 files) → Single implementation
- ❌ 8-layer cascading changes → 3-layer changes

**Performance Characteristics**:
- Memory: 50-500MB depending on project size
- Speed: 100-300x faster than disk queries
- Startup: One-time load (~1-5 seconds for large projects)
- Queries: O(1) for indexed columns, O(n) for full scans (in-memory)
