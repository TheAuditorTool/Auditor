# Tasks: Eliminate JSON Blobs and Normalize Schema

## 0. Verification

- [x] 0.1 Verify JSON blob columns exist in `node_schema.py:382-385` (package_configs)
- [x] 0.2 Verify JSON blob columns exist in infrastructure tables (docker, compose, terraform)
- [x] 0.3 Verify engines writing to `.pf/raw/*.json` (`vulnerability_scanner.py:630`, `deps.py:1212`)
- [x] 0.4 Verify `.pf/readthis/` generation active (`context.py:312`, `report.py:104`)
- [x] 0.5 Verify no conflict with `consolidate-findings-queries` (separate scope confirmed)

---

## Phase 1: Add Junction Tables (Schema)

### 1.1 Package Config Junction Tables

**Parent table**: `package_configs` with PK `file_path` (TEXT) at `node_schema.py:376-379`

- [ ] 1.1.1 Add `package_dependencies` table to `indexer/schemas/node_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `name`, `version_spec`, `is_dev`, `is_peer`
  - Indexes: `file_path`, `name`
  - Unique: `(file_path, name, is_dev, is_peer)`
- [ ] 1.1.2 Add `package_scripts` table to `indexer/schemas/node_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `script_name`, `script_command`
  - Indexes: `file_path`
  - Unique: `(file_path, script_name)`
- [ ] 1.1.3 Add `package_engines` table to `indexer/schemas/node_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `engine_name`, `version_spec`
  - Indexes: `file_path`
  - Unique: `(file_path, engine_name)`
- [ ] 1.1.4 Add `package_workspaces` table to `indexer/schemas/node_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `workspace_path`
  - Indexes: `file_path`
  - Unique: `(file_path, workspace_path)`

### 1.2 Docker Junction Tables

**Parent table**: `docker_images` with PK `file_path` (TEXT) at `infrastructure_schema.py:18-21`

- [ ] 1.2.1 Add `dockerfile_ports` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `port`, `protocol`
  - Indexes: `file_path`
  - Unique: `(file_path, port, protocol)`
- [ ] 1.2.2 Add `dockerfile_env_vars` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `var_name`, `var_value`, `is_build_arg`
  - Indexes: `file_path`
  - Unique: `(file_path, var_name, is_build_arg)`

### 1.3 Docker Compose Junction Tables

**Parent table**: `compose_services` with COMPOSITE PK `(file_path, service_name)` at `infrastructure_schema.py:34-38`

- [ ] 1.3.1 Add `compose_service_ports` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `service_name` (TEXT FK), `host_port`, `container_port`, `protocol`
  - Indexes: `(file_path, service_name)`
  - Unique: `(file_path, service_name, host_port, container_port, protocol)`
- [ ] 1.3.2 Add `compose_service_volumes` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `service_name` (TEXT FK), `host_path`, `container_path`, `mode`
  - Indexes: `(file_path, service_name)`
  - Unique: `(file_path, service_name, host_path, container_path)`
- [ ] 1.3.3 Add `compose_service_env` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `service_name` (TEXT FK), `var_name`, `var_value`
  - Indexes: `(file_path, service_name)`
  - Unique: `(file_path, service_name, var_name)`
- [ ] 1.3.4 Add `compose_service_capabilities` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `service_name` (TEXT FK), `capability`, `is_add`
  - Indexes: `(file_path, service_name)`
  - Unique: `(file_path, service_name, capability)`
- [ ] 1.3.5 Add `compose_service_deps` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `service_name` (TEXT FK), `depends_on_service`, `condition`
  - Indexes: `(file_path, service_name)`
  - Unique: `(file_path, service_name, depends_on_service)`

### 1.4 Terraform Junction Tables

**Parent table**: `terraform_resources` with PK `resource_id` (TEXT) at `infrastructure_schema.py:96-99`

- [ ] 1.4.1 Add `terraform_resource_properties` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `resource_id` (TEXT FK), `property_name`, `property_value`, `property_type`
  - Indexes: `resource_id`
  - Unique: `(resource_id, property_name)`
- [ ] 1.4.2 Add `terraform_resource_deps` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `resource_id` (TEXT FK), `depends_on_resource`
  - Indexes: `resource_id`
  - Unique: `(resource_id, depends_on_resource)`

### 1.5 GraphQL Junction Tables

**Parent tables**:
- `graphql_fields.field_id` (INTEGER) at `graphql_schema.py:67-70`
- `graphql_field_args.(field_id, arg_name)` (COMPOSITE PK, NO arg_id!) at `graphql_schema.py:94-105`

- [ ] 1.5.1 Add `graphql_field_directives` table to `indexer/schemas/graphql_schema.py`
  - Columns: `id`, `field_id` (INTEGER FK), `directive_name`, `directive_args`
  - Indexes: `field_id`
  - Unique: `(field_id, directive_name)`
- [ ] 1.5.2 Add `graphql_arg_directives` table to `indexer/schemas/graphql_schema.py`
  - Columns: `id`, `field_id` (INTEGER FK), `arg_name` (TEXT FK), `directive_name`, `directive_args`
  - Indexes: `(field_id, arg_name)` composite
  - Unique: `(field_id, arg_name, directive_name)`

### 1.6 Database Manager Methods

**NOTE**: Database is a directory with mixin classes, not a single file:
- Package methods → `indexer/database/node_database.py`
- Docker/Compose/Terraform methods → `indexer/database/infrastructure_database.py`
- GraphQL methods → `indexer/database/graphql_database.py`

- [ ] 1.6.1 Add `add_package_dependencies()` method to `indexer/database/node_database.py`
  - Uses `executemany()` for batch insert
  - Handles is_dev and is_peer flags
- [ ] 1.6.2 Add `add_package_scripts()` method to `indexer/database/node_database.py`
- [ ] 1.6.3 Add `add_package_engines()` method to `indexer/database/node_database.py`
- [ ] 1.6.4 Add `add_package_workspaces()` method to `indexer/database/node_database.py`
- [ ] 1.6.5 Add `add_dockerfile_ports()` method to `indexer/database/infrastructure_database.py`
- [ ] 1.6.6 Add `add_dockerfile_env_vars()` method to `indexer/database/infrastructure_database.py`
- [ ] 1.6.7 Add `add_compose_service_ports()` method to `indexer/database/infrastructure_database.py`
- [ ] 1.6.8 Add `add_compose_service_volumes()` method to `indexer/database/infrastructure_database.py`
- [ ] 1.6.9 Add `add_compose_service_env()` method to `indexer/database/infrastructure_database.py`
- [ ] 1.6.10 Add `add_compose_service_capabilities()` method to `indexer/database/infrastructure_database.py`
- [ ] 1.6.11 Add `add_compose_service_deps()` method to `indexer/database/infrastructure_database.py`
- [ ] 1.6.12 Add `add_terraform_resource_properties()` method to `indexer/database/infrastructure_database.py`
- [ ] 1.6.13 Add `add_terraform_resource_deps()` method to `indexer/database/infrastructure_database.py`
- [ ] 1.6.14 Add `add_graphql_field_directives()` method to `indexer/database/graphql_database.py`
- [ ] 1.6.15 Add `add_graphql_arg_directives()` method to `indexer/database/graphql_database.py`
  - Note: Uses composite FK (field_id, arg_name), NOT arg_id

---

## Phase 2: Update Extractors (Python)

**NOTE**: All extractors in this scope are Python. No Node.js extractor changes required.

### 2.1 Package.json Extractor

**File**: `indexer/extractors/generic.py:335-360`
**Method**: `_extract_package_direct()`
**Current**: Calls `db_manager.add_package_config()` at line 345 with JSON in dependencies column

- [ ] 2.1.1 Update `_extract_package_direct()` in `indexer/extractors/generic.py:335-360`
- [ ] 2.1.2 After `add_package_config()` at line 345, call `add_package_dependencies(file_path, deps_list)`
- [ ] 2.1.3 After `add_package_config()`, call `add_package_scripts(file_path, scripts_list)`
- [ ] 2.1.4 After `add_package_config()`, call `add_package_engines(file_path, engines_list)`
- [ ] 2.1.5 After `add_package_config()`, call `add_package_workspaces(file_path, workspaces_list)`
- [ ] 2.1.6 Keep JSON column writes temporarily (dual-write for verification)

### 2.2 Dockerfile Extractor

**File**: `indexer/extractors/docker.py:56-134`
**Method**: `extract()`
**Current**: Calls `db_manager.add_docker_image()` at line 126 with JSON in exposed_ports column

- [ ] 2.2.1 Update `extract()` in `indexer/extractors/docker.py:56-134`
- [ ] 2.2.2 After `add_docker_image()` at line 126, call `add_dockerfile_ports(file_path, ports_list)`
- [ ] 2.2.3 After `add_docker_image()`, call `add_dockerfile_env_vars(file_path, env_list)`
- [ ] 2.2.4 Keep JSON column writes temporarily (dual-write for verification)

### 2.3 Docker Compose Extractor

**File**: `indexer/extractors/generic.py:128-198`
**Method**: `_extract_compose_direct()`
**Current**: Calls `db_manager.add_compose_service()` at line 177 with JSON in ports/volumes/environment columns

- [ ] 2.3.1 Update `_extract_compose_direct()` in `indexer/extractors/generic.py:128-198`
- [ ] 2.3.2 After `add_compose_service()` at line 177, call `add_compose_service_ports(file_path, service_name, ports)`
- [ ] 2.3.3 After `add_compose_service()`, call `add_compose_service_volumes(file_path, service_name, volumes)`
- [ ] 2.3.4 After `add_compose_service()`, call `add_compose_service_env(file_path, service_name, env)`
- [ ] 2.3.5 After `add_compose_service()`, call `add_compose_service_capabilities(file_path, service_name, caps)`
- [ ] 2.3.6 After `add_compose_service()`, call `add_compose_service_deps(file_path, service_name, deps)`
- [ ] 2.3.7 Keep JSON column writes temporarily (dual-write for verification)

### 2.4 Terraform Extractor

**File**: `indexer/extractors/terraform.py`
**Current**: Uses `json.dumps(props)` for properties_json column

- [ ] 2.4.1 Update terraform extraction in `indexer/extractors/terraform.py`
- [ ] 2.4.2 After `add_terraform_resource()`, call `add_terraform_resource_properties(resource_id, props)`
- [ ] 2.4.3 After `add_terraform_resource()`, call `add_terraform_resource_deps(resource_id, deps)`
- [ ] 2.4.4 Keep JSON column writes temporarily (dual-write for verification)

### 2.5 GraphQL Extractor (Python-Only)

**File**: `indexer/extractors/graphql.py:209-300`
**Methods**: `_extract_field()` at line 209, `_extract_field_arg()` at line 258
**Current**: `json.dumps(directives)` at lines 237 and 290

- [ ] 2.5.1 Update `_extract_field()` in `indexer/extractors/graphql.py:209-256`
  - Remove `directives_json = json.dumps(directives)` at line 237
  - Return directives as list, not JSON string
- [ ] 2.5.2 Update `_extract_field_arg()` in `indexer/extractors/graphql.py:258-304`
  - Remove `directives_json = json.dumps(directives)` at line 290
  - Return directives as list, not JSON string
- [ ] 2.5.3 After field insertion, call `add_graphql_field_directives(field_id, directives)`
- [ ] 2.5.4 After arg insertion, call `add_graphql_arg_directives(field_id, arg_name, directives)`
  - Note: Uses composite FK (field_id, arg_name), NOT arg_id
- [ ] 2.5.5 Keep JSON column writes temporarily (dual-write for verification)

---

## Phase 3: Verification (No Node.js Changes Required)

**IMPORTANT**: GraphQL extraction is Python-only (`indexer/extractors/graphql.py`). There is NO `ast_extractors/javascript/graphql_extractors.js` file.

Package.json extraction is also Python-only (`indexer/extractors/generic.py:335-377`). The `ast_extractors/javascript/module_framework.js` file exists but does NOT handle package.json extraction.

### 3.1 Verify No Node.js Changes Needed

- [x] 3.1.1 Confirmed: `ast_extractors/javascript/graphql_extractors.js` does NOT exist
- [x] 3.1.2 Confirmed: Package.json handled by Python `generic.py`, not Node.js
- [ ] 3.1.3 Verify all junction table inserts happen in Python layer only

---

## Phase 4: Remove JSON Column Writes

### 4.1 Verify Junction Table Data

- [ ] 4.1.1 Run `aud full --index` on test project
- [ ] 4.1.2 Query junction tables to verify data populated
- [ ] 4.1.3 Compare junction table data to JSON column data for accuracy

### 4.2 Remove Dual Writes

- [ ] 4.2.1 Remove `json.dumps(dependencies)` from package.json extractor
- [ ] 4.2.2 Remove `json.dumps(exposed_ports)` from dockerfile extractor
- [ ] 4.2.3 Remove `json.dumps(ports)` from docker-compose extractor
- [ ] 4.2.4 Remove `json.dumps(properties)` from terraform extractor
- [ ] 4.2.5 Remove `json.dumps(directives)` from graphql extractor

---

## Phase 5: Remove JSON File Writes

### 5.1 Remove Engine JSON Writes

- [ ] 5.1.1 Remove `_write_to_json()` method from `vulnerability_scanner.py:629-657`
- [ ] 5.1.2 Remove `write_vulnerabilities_json()` function from `vulnerability_scanner.py:708-730`
- [ ] 5.1.3 Remove calls to JSON write functions in `vulnerability_scanner.py`
- [ ] 5.1.4 Remove `write_deps_latest_json()` function from `deps.py:1211-1220`
- [ ] 5.1.5 Remove calls to `write_deps_latest_json()` in `deps.py` and `commands/deps.py`
- [ ] 5.1.6 Remove JSON output from `commands/cfg.py:235`
- [ ] 5.1.7 Remove JSON output from `commands/terraform.py:153,263`
- [ ] 5.1.8 Remove JSON output from `commands/docker_analyze.py:248`
- [ ] 5.1.9 Remove JSON output from `commands/workflows.py:162`
- [ ] 5.1.10 Remove JSON output from `commands/detect_frameworks.py:221`

### 5.2 Update Callers

- [ ] 5.2.1 Update `pipelines.py` if it references removed JSON functions
- [ ] 5.2.2 Update any command that expects JSON output path parameter

---

## Phase 6: Deprecate .pf/readthis/

### 6.1 Delete Report Command

- [ ] 6.1.1 Delete `commands/report.py` entirely
- [ ] 6.1.2 Remove `report` command registration from `cli.py`
- [ ] 6.1.3 Remove report from `pipelines.py` if present in stage list

### 6.2 Remove Chunk Generation

- [ ] 6.2.1 Remove chunk generation from `commands/context.py:343-407` (`_extract_semantic_chunks` function)
- [ ] 6.2.2 Remove chunk output from `commands/taint.py:165`
- [ ] 6.2.3 Remove chunk output from `commands/workflows.py:108`
- [ ] 6.2.4 Remove chunk output from `commands/detect_patterns.py:91`

### 6.3 Update Pipeline References

- [ ] 6.3.1 Remove readthis references from `commands/full.py:77-78, 203`
- [ ] 6.3.2 Remove readthis file counting from `pipelines.py:1553, 1560, 1573`

---

## Phase 7: Testing and Verification

### 7.1 Schema Tests

- [ ] 7.1.1 Add test for `package_dependencies` table existence
- [ ] 7.1.2 Add test for all 15 junction tables existence
- [ ] 7.1.3 Verify schema contract includes new tables

### 7.2 Extraction Tests

- [ ] 7.2.1 Test package.json extraction populates junction tables
- [ ] 7.2.2 Test dockerfile extraction populates junction tables
- [ ] 7.2.3 Test docker-compose extraction populates junction tables
- [ ] 7.2.4 Test terraform extraction populates junction tables
- [ ] 7.2.5 Test graphql extraction populates junction tables

### 7.3 Integration Tests

- [ ] 7.3.1 Run `aud full --offline` on TheAuditor codebase
- [ ] 7.3.2 Verify no JSON files created in `.pf/raw/` (for removed engines)
- [ ] 7.3.3 Verify no `.pf/readthis/` directory created
- [ ] 7.3.4 Verify all existing tests pass

### 7.4 Query Tests

- [ ] 7.4.1 Query `package_dependencies` and verify expected data
- [ ] 7.4.2 Query `dockerfile_ports` and verify expected data
- [ ] 7.4.3 Query `compose_service_env` and verify expected data

---

## Phase 8: Documentation

### 8.1 Update Documentation

- [ ] 8.1.1 Update `CLAUDE.md` Section 5 with new junction tables
- [ ] 8.1.2 Update `project.md` with new schema tables
- [ ] 8.1.3 Update any README referencing `.pf/readthis/`

### 8.2 Migration Notes

- [ ] 8.2.1 Document that `aud full --index` is required after deployment
- [ ] 8.2.2 Document that old JSON files are not auto-deleted
- [ ] 8.2.3 Document manual cleanup of `.pf/readthis/` if desired

---

## Summary

| Phase | Tasks | Estimated Effort |
|-------|-------|------------------|
| 1. Schema | 21 | MEDIUM |
| 2. Python Extractors | 24 | MEDIUM |
| 3. Verification | 3 | LOW (mostly pre-verified) |
| 4. Remove JSON Columns | 6 | LOW |
| 5. Remove JSON Files | 12 | MEDIUM |
| 6. Deprecate Readthis | 7 | LOW |
| 7. Testing | 12 | MEDIUM |
| 8. Documentation | 5 | LOW |
| **TOTAL** | **90** | HIGH |

**Key Change from Original**: Phase 3 reduced from "Node Extractors" to "Verification" because:
- GraphQL extraction is Python-only (no `graphql_extractors.js` exists)
- Package.json extraction is Python-only (in `generic.py`, not `module_framework.js`)
