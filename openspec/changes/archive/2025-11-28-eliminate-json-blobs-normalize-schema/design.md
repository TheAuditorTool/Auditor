# Design: Eliminate JSON Blobs and Normalize Schema

## Context

TheAuditor stores extracted data in SQLite databases (`.pf/repo_index.db` and `.pf/graphs.db`). The schema has evolved organically, resulting in:

1. **19 TEXT columns** storing `json.dumps()` data instead of normalized tables
2. **15 engines** writing both to database AND `.pf/raw/*.json` files
3. **Deprecated `.pf/readthis/`** directory still being generated

This design document covers the technical approach to eliminate JSON blobs and normalize the schema.

### Stakeholders

- **Architect (Human)**: Approves schema changes, migration strategy
- **Lead Auditor (Gemini)**: Reviews for security implications, edge cases
- **Lead Coder (Opus)**: Implements schema changes, extraction updates

### Constraints

1. **ZERO FALLBACK**: No try/except for missing tables - schema contract guarantees existence
2. **3-Layer Architecture**: INDEXER provides file_path, EXTRACTOR delegates, IMPLEMENTATION returns data
3. **Windows Environment**: No emojis in output, use `.venv/Scripts/python.exe`
4. **Python-Only Extractors**: All extractors in this scope are Python (no Node.js changes needed)

### Parent Table Primary Keys (VERIFIED)

Critical schema fact: Most parent tables use TEXT primary keys, not INTEGER:

| Parent Table | Primary Key | Type | Schema File |
|--------------|-------------|------|-------------|
| `package_configs` | `file_path` | TEXT | `node_schema.py:376-379` |
| `docker_images` | `file_path` | TEXT | `infrastructure_schema.py:18-21` |
| `compose_services` | `(file_path, service_name)` | COMPOSITE | `infrastructure_schema.py:34-38` |
| `terraform_resources` | `resource_id` | TEXT | `infrastructure_schema.py:96-99` |
| `graphql_fields` | `field_id` | INTEGER | `graphql_schema.py:67-70` |
| `graphql_field_args` | `(field_id, arg_name)` | COMPOSITE | `graphql_schema.py:94-105` |

**Implication**: Junction tables must use TEXT foreign keys for package/docker/compose/terraform. GraphQL fields use INTEGER FK, but graphql_field_args uses COMPOSITE FK (field_id, arg_name).

---

## Goals / Non-Goals

### Goals

1. Eliminate JSON blob columns with proper junction tables
2. Remove redundant JSON file writes from engines
3. Delete deprecated `.pf/readthis/` generation
4. Maintain full query capability for all previously-stored data

### Non-Goals

1. **NOT changing acceptable JSON columns** (path traces, freeform metadata)
2. **NOT modifying findings_consolidated schema** (handled by `consolidate-findings-queries`)
3. **NOT adding new extraction capabilities** (just normalizing existing data)
4. **NOT removing `.pf/raw/` directory entirely** (keep for future debugging)

---

## Decisions

### Decision 1: Junction Table Naming Convention

**What**: All junction tables follow pattern `{parent_table}_{relationship}` (singular)

**Why**: Consistent with existing schema (`function_call_args`, `class_base_classes`)

**Examples**:
- `package_configs` + dependencies = `package_dependencies`
- `docker_images` + ports = `dockerfile_ports`
- `compose_services` + environment = `compose_service_env`

**Alternatives Considered**:
- Plural names (`package_dependencies` vs `package_dependency`) - Rejected: existing pattern uses plural
- Prefixed names (`junction_package_deps`) - Rejected: verbose, inconsistent

### Decision 2: Foreign Key Strategy

**What**: Define FKs in database mixin files after table creation, not in `schema.py`

**Why**: Avoids circular dependency issues. Matches existing pattern per `project.md`:
> "FOREIGN KEY Pattern: Intentionally omitted from schema.py (defined in database.py to avoid circular dependencies)"

**Database Directory Structure** (NOT a single file):
```
theauditor/indexer/database/
├── __init__.py
├── base_database.py              # Base class
├── infrastructure_database.py    # add_docker_image, add_compose_service
├── node_database.py              # add_package_config
├── graphql_database.py           # GraphQL methods
├── python_database.py
├── security_database.py
├── frameworks_database.py
├── core_database.py
└── planning_database.py
```

**Implementation**:
```python
# In infrastructure_database.py after CREATE TABLE
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_package_dependencies_file_path
    ON package_dependencies(file_path)
""")
# FK enforcement is implicit via application-level ID passing
```

### Decision 3: Batch Insert Pattern for Junction Tables

**What**: Use `executemany()` for junction table inserts, not individual `execute()` calls

**Why**: Performance. A single `package.json` may have 50+ dependencies.

**Implementation** (using correct TEXT FK):
```python
def add_package_dependencies(self, file_path: str, dependencies: list[dict]) -> None:
    """Insert multiple dependencies in one batch.

    Args:
        file_path: FK to package_configs.file_path (TEXT, not INTEGER!)
        dependencies: List of {name: str, version_spec: str, is_dev: bool, is_peer: bool}
    """
    rows = [
        (file_path, d['name'], d['version_spec'], d.get('is_dev', False), d.get('is_peer', False))
        for d in dependencies
    ]
    self.cursor.executemany("""
        INSERT INTO package_dependencies (file_path, name, version_spec, is_dev, is_peer)
        VALUES (?, ?, ?, ?, ?)
    """, rows)
```

### Decision 4: GraphQL Extractor Changes (Python-Only)

**What**: GraphQL extraction is entirely in Python. Remove `json.dumps()` and insert to junction tables directly.

**Why**: There is NO Node.js GraphQL extractor. `ast_extractors/javascript/graphql_extractors.js` does not exist.

**VERIFIED FILE**: `indexer/extractors/graphql.py`

**Current Implementation** (lines 209-237 for _extract_field, 258-290 for _extract_field_arg):
```python
# In _extract_field() at line 237:
directives_json = None
if hasattr(node, "directives") and node.directives:
    directives = self._extract_directives(node.directives)
    if directives:
        directives_json = json.dumps(directives)  # <-- REMOVE THIS

# In _extract_field_arg() at line 290:
directives_json = json.dumps(directives)  # <-- REMOVE THIS
```

**New Implementation**:
```python
# After extracting all fields, call:
db_manager.add_graphql_field_directives(field_id, directives)
# Where directives is list[dict], not JSON string
```

### Decision 5: JSON Column Removal Strategy

**What**: Remove JSON columns AFTER junction tables are populated, not simultaneously

**Why**: Safer migration. Can verify data integrity before removing columns.

**Migration Steps**:
1. Add junction tables (schema change)
2. Update extractors to write to junction tables AND old JSON columns
3. Deploy, run `aud full --index`
4. Verify junction table data matches JSON column data
5. Remove JSON column writes from extractors
6. (Future) Drop JSON columns from schema (optional, they're just unused)

### Decision 6: Readthis Removal Approach - ALREADY COMPLETE

**Status**: DONE (verified 2025-11-28)

**What was planned**: Delete `commands/report.py` entirely, remove chunk generation from other commands

**What happened**: Previous tickets already completed this work:
- `commands/report.py` - DELETED (file does not exist)
- `context.py` - Rewritten to 328 lines, no chunk generation
- `taint.py`, `workflows.py`, `detect_patterns.py` - No readthis/chunk references
- `full.py`, `pipelines.py` - No readthis references
- `cli.py` - No report command registration

**No action required for Decision 6.**

---

## Schema Design

### New Junction Tables

**CRITICAL**: Parent tables use TEXT primary keys (file_path), not INTEGER. Only GraphQL uses INTEGER PKs.

#### Package Dependencies (replaces `package_configs.dependencies`, `dev_dependencies`, `peer_dependencies`)

```sql
-- FK: package_configs.file_path (TEXT)
CREATE TABLE package_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,  -- FK to package_configs.file_path
    name TEXT NOT NULL,
    version_spec TEXT,
    is_dev BOOLEAN DEFAULT 0,
    is_peer BOOLEAN DEFAULT 0,
    UNIQUE(file_path, name, is_dev, is_peer)
);
CREATE INDEX idx_package_dependencies_file_path ON package_dependencies(file_path);
CREATE INDEX idx_package_dependencies_name ON package_dependencies(name);
```

#### Package Scripts (replaces `package_configs.scripts`)

```sql
-- FK: package_configs.file_path (TEXT)
CREATE TABLE package_scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,  -- FK to package_configs.file_path
    script_name TEXT NOT NULL,
    script_command TEXT NOT NULL,
    UNIQUE(file_path, script_name)
);
CREATE INDEX idx_package_scripts_file_path ON package_scripts(file_path);
```

#### Package Engines (replaces `package_configs.engines`)

```sql
-- FK: package_configs.file_path (TEXT)
CREATE TABLE package_engines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,  -- FK to package_configs.file_path
    engine_name TEXT NOT NULL,
    version_spec TEXT,
    UNIQUE(file_path, engine_name)
);
CREATE INDEX idx_package_engines_file_path ON package_engines(file_path);
```

#### Package Workspaces (replaces `package_configs.workspaces`)

```sql
-- FK: package_configs.file_path (TEXT)
CREATE TABLE package_workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,  -- FK to package_configs.file_path
    workspace_path TEXT NOT NULL,
    UNIQUE(file_path, workspace_path)
);
CREATE INDEX idx_package_workspaces_file_path ON package_workspaces(file_path);
```

#### Dockerfile Ports (replaces `docker_images.exposed_ports`)

```sql
-- FK: docker_images.file_path (TEXT)
CREATE TABLE dockerfile_ports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,  -- FK to docker_images.file_path
    port INTEGER NOT NULL,
    protocol TEXT DEFAULT 'tcp',
    UNIQUE(file_path, port, protocol)
);
CREATE INDEX idx_dockerfile_ports_file_path ON dockerfile_ports(file_path);
```

#### Dockerfile Env Vars (replaces `docker_images.env_vars`, `build_args`)

```sql
-- FK: docker_images.file_path (TEXT)
CREATE TABLE dockerfile_env_vars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,  -- FK to docker_images.file_path
    var_name TEXT NOT NULL,
    var_value TEXT,
    is_build_arg BOOLEAN DEFAULT 0,
    UNIQUE(file_path, var_name, is_build_arg)
);
CREATE INDEX idx_dockerfile_env_vars_file_path ON dockerfile_env_vars(file_path);
```

#### Compose Service Ports (replaces `compose_services.ports`)

```sql
-- FK: compose_services.(file_path, service_name) COMPOSITE
CREATE TABLE compose_service_ports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,      -- FK part 1
    service_name TEXT NOT NULL,   -- FK part 2
    host_port INTEGER,
    container_port INTEGER NOT NULL,
    protocol TEXT DEFAULT 'tcp',
    UNIQUE(file_path, service_name, host_port, container_port, protocol)
);
CREATE INDEX idx_compose_service_ports_fk ON compose_service_ports(file_path, service_name);
```

#### Compose Service Volumes (replaces `compose_services.volumes`)

```sql
-- FK: compose_services.(file_path, service_name) COMPOSITE
CREATE TABLE compose_service_volumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,      -- FK part 1
    service_name TEXT NOT NULL,   -- FK part 2
    host_path TEXT,
    container_path TEXT NOT NULL,
    mode TEXT DEFAULT 'rw',
    UNIQUE(file_path, service_name, host_path, container_path)
);
CREATE INDEX idx_compose_service_volumes_fk ON compose_service_volumes(file_path, service_name);
```

#### Compose Service Env (replaces `compose_services.environment`)

```sql
-- FK: compose_services.(file_path, service_name) COMPOSITE
CREATE TABLE compose_service_env (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,      -- FK part 1
    service_name TEXT NOT NULL,   -- FK part 2
    var_name TEXT NOT NULL,
    var_value TEXT,
    UNIQUE(file_path, service_name, var_name)
);
CREATE INDEX idx_compose_service_env_fk ON compose_service_env(file_path, service_name);
```

#### Compose Service Capabilities (replaces `compose_services.cap_add`, `cap_drop`)

```sql
-- FK: compose_services.(file_path, service_name) COMPOSITE
CREATE TABLE compose_service_capabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,      -- FK part 1
    service_name TEXT NOT NULL,   -- FK part 2
    capability TEXT NOT NULL,
    is_add BOOLEAN NOT NULL,
    UNIQUE(file_path, service_name, capability)
);
CREATE INDEX idx_compose_service_capabilities_fk ON compose_service_capabilities(file_path, service_name);
```

#### Compose Service Dependencies (replaces `compose_services.depends_on`)

```sql
-- FK: compose_services.(file_path, service_name) COMPOSITE
CREATE TABLE compose_service_deps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,      -- FK part 1
    service_name TEXT NOT NULL,   -- FK part 2
    depends_on_service TEXT NOT NULL,
    condition TEXT DEFAULT 'service_started',
    UNIQUE(file_path, service_name, depends_on_service)
);
CREATE INDEX idx_compose_service_deps_fk ON compose_service_deps(file_path, service_name);
```

#### Terraform Resource Properties (replaces `terraform_resources.properties_json`)

```sql
-- FK: terraform_resources.resource_id (TEXT)
CREATE TABLE terraform_resource_properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id TEXT NOT NULL,  -- FK to terraform_resources.resource_id
    property_name TEXT NOT NULL,
    property_value TEXT,
    property_type TEXT DEFAULT 'string',
    UNIQUE(resource_id, property_name)
);
CREATE INDEX idx_terraform_resource_properties_resource_id ON terraform_resource_properties(resource_id);
```

#### Terraform Resource Dependencies (replaces `terraform_resources.depends_on_json`)

```sql
-- FK: terraform_resources.resource_id (TEXT)
CREATE TABLE terraform_resource_deps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id TEXT NOT NULL,  -- FK to terraform_resources.resource_id
    depends_on_resource TEXT NOT NULL,
    UNIQUE(resource_id, depends_on_resource)
);
CREATE INDEX idx_terraform_resource_deps_resource_id ON terraform_resource_deps(resource_id);
```

#### GraphQL Field Directives (replaces `graphql_fields.directives_json`)

```sql
CREATE TABLE graphql_field_directives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL,
    directive_name TEXT NOT NULL,
    directive_args TEXT,
    UNIQUE(field_id, directive_name)
);
CREATE INDEX idx_graphql_field_directives_field_id ON graphql_field_directives(field_id);
```

#### GraphQL Arg Directives (replaces `graphql_field_args.directives_json`)

```sql
-- FK: graphql_field_args.(field_id, arg_name) COMPOSITE
-- NOTE: graphql_field_args has NO arg_id column - it uses composite PK (field_id, arg_name)
CREATE TABLE graphql_arg_directives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id INTEGER NOT NULL,    -- FK part 1
    arg_name TEXT NOT NULL,       -- FK part 2
    directive_name TEXT NOT NULL,
    directive_args TEXT,
    UNIQUE(field_id, arg_name, directive_name)
);
CREATE INDEX idx_graphql_arg_directives_fk ON graphql_arg_directives(field_id, arg_name);
```

---

## Risks / Trade-offs

### Risk 1: Schema Migration Complexity

**Risk**: 15 new tables may have edge cases not covered by design
**Likelihood**: MEDIUM
**Impact**: LOW (can add columns/fix in follow-up)
**Mitigation**: Implement tables in batches (package_configs first, then docker, then terraform)

### Risk 2: Node Extractor Integration

**Risk**: Node extractors may return data in unexpected format
**Likelihood**: LOW (existing patterns are stable)
**Impact**: MEDIUM (breaks extraction)
**Mitigation**: Add validation in Python extractor layer, log and skip malformed data

### Risk 3: Performance Regression

**Risk**: Junction table inserts may be slower than single JSON column write
**Likelihood**: LOW (batch inserts mitigate)
**Impact**: MEDIUM (slower `aud full`)
**Mitigation**: Use `executemany()`, maintain batch size of 200

### Risk 4: Downstream Consumer Breakage

**Risk**: Code reading JSON columns will break
**Likelihood**: HIGH (by design)
**Impact**: LOW (we're updating all consumers)
**Mitigation**: Search codebase for JSON column reads, update before removing

---

## Migration Plan

### Phase 1: Add Junction Tables (Non-Breaking)

1. Add 15 table definitions to `indexer/schemas/node_schema.py`, `infrastructure_schema.py`
2. Add `add_*` methods to `indexer/database.py`
3. Update extractors to write to BOTH junction tables AND old JSON columns
4. Deploy, run `aud full --index`
5. Verify data in junction tables matches JSON columns

### Phase 2: Remove JSON Column Writes (Breaking for Readers)

1. Remove `json.dumps()` writes from extractors
2. Update any code reading JSON columns to query junction tables
3. Deploy, run `aud full --index`
4. Verify no regressions

### Phase 3: Remove JSON File Writes (Breaking for External Tools)

1. Remove `_write_to_json()` and similar methods from engines
2. ~~Delete `commands/report.py`~~ - ALREADY DONE
3. ~~Remove readthis chunk generation~~ - ALREADY DONE
4. Deploy, run `aud full`
5. ~~Verify no `.pf/readthis/` created~~ - ALREADY VERIFIED

### Rollback

Each phase can be rolled back independently:
- Phase 1: Junction tables are additive, no rollback needed
- Phase 2: Re-add JSON column writes
- Phase 3: Re-add JSON file writes (readthis/report.py already removed, no rollback needed)

---

## Open Questions

1. **Should we keep JSON columns as read-only archive?**
   - Current decision: YES, don't DROP columns (just stop writing)
   - Rationale: Zero risk, columns are just unused space

2. **Should `.pf/raw/` JSON files be auto-deleted on next run?**
   - Current decision: NO, leave old files
   - Rationale: May be useful for debugging migration issues

3. **Timeline for Phase 2 and 3?**
   - Awaiting Architect decision
   - Recommendation: Phase 1 in this PR, Phase 2+3 in follow-up

---

## References

| Document | Purpose |
|----------|---------|
| `readers_writers.md` | Original audit identifying violations |
| `consolidate-findings-queries` | Related change handling JSON readers |
| `CLAUDE.md` Section 5 | Database architecture documentation |
| `project.md` | Schema contract and FK patterns |
