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

- [x] 1.1.1 Add `package_dependencies` table to `indexer/schemas/node_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `name`, `version_spec`, `is_dev`, `is_peer`
  - Indexes: `file_path`, `name`
  - Unique: `(file_path, name, is_dev, is_peer)`
- [x] 1.1.2 Add `package_scripts` table to `indexer/schemas/node_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `script_name`, `script_command`
  - Indexes: `file_path`
  - Unique: `(file_path, script_name)`
- [x] 1.1.3 Add `package_engines` table to `indexer/schemas/node_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `engine_name`, `version_spec`
  - Indexes: `file_path`
  - Unique: `(file_path, engine_name)`
- [x] 1.1.4 Add `package_workspaces` table to `indexer/schemas/node_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `workspace_path`
  - Indexes: `file_path`
  - Unique: `(file_path, workspace_path)`

### 1.2 Docker Junction Tables

**Parent table**: `docker_images` with PK `file_path` (TEXT) at `infrastructure_schema.py:18-21`

- [x] 1.2.1 Add `dockerfile_ports` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `port`, `protocol`
  - Indexes: `file_path`
  - Unique: `(file_path, port, protocol)`
- [x] 1.2.2 Add `dockerfile_env_vars` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `var_name`, `var_value`, `is_build_arg`
  - Indexes: `file_path`
  - Unique: `(file_path, var_name, is_build_arg)`

### 1.3 Docker Compose Junction Tables

**Parent table**: `compose_services` with COMPOSITE PK `(file_path, service_name)` at `infrastructure_schema.py:34-38`

- [x] 1.3.1 Add `compose_service_ports` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `service_name` (TEXT FK), `host_port`, `container_port`, `protocol`
  - Indexes: `(file_path, service_name)`
  - Unique: `(file_path, service_name, host_port, container_port, protocol)`
- [x] 1.3.2 Add `compose_service_volumes` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `service_name` (TEXT FK), `host_path`, `container_path`, `mode`
  - Indexes: `(file_path, service_name)`
  - Unique: `(file_path, service_name, host_path, container_path)`
- [x] 1.3.3 Add `compose_service_env` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `service_name` (TEXT FK), `var_name`, `var_value`
  - Indexes: `(file_path, service_name)`
  - Unique: `(file_path, service_name, var_name)`
- [x] 1.3.4 Add `compose_service_capabilities` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `service_name` (TEXT FK), `capability`, `is_add`
  - Indexes: `(file_path, service_name)`
  - Unique: `(file_path, service_name, capability)`
- [x] 1.3.5 Add `compose_service_deps` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `file_path` (TEXT FK), `service_name` (TEXT FK), `depends_on_service`, `condition`
  - Indexes: `(file_path, service_name)`
  - Unique: `(file_path, service_name, depends_on_service)`

### 1.4 Terraform Junction Tables

**Parent table**: `terraform_resources` with PK `resource_id` (TEXT) at `infrastructure_schema.py:96-99`

- [x] 1.4.1 Add `terraform_resource_properties` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `resource_id` (TEXT FK), `property_name`, `property_value`, `property_type`
  - Indexes: `resource_id`
  - Unique: `(resource_id, property_name)`
- [x] 1.4.2 Add `terraform_resource_deps` table to `indexer/schemas/infrastructure_schema.py`
  - Columns: `id`, `resource_id` (TEXT FK), `depends_on_resource`
  - Indexes: `resource_id`
  - Unique: `(resource_id, depends_on_resource)`

### 1.5 GraphQL Junction Tables

**Parent tables**:
- `graphql_fields.field_id` (INTEGER) at `graphql_schema.py:67-70`
- `graphql_field_args.(field_id, arg_name)` (COMPOSITE PK, NO arg_id!) at `graphql_schema.py:94-105`

- [x] 1.5.1 Add `graphql_field_directives` table to `indexer/schemas/graphql_schema.py`
  - Columns: `id`, `field_id` (INTEGER FK), `directive_name`, `directive_args`
  - Indexes: `field_id`
  - Unique: `(field_id, directive_name)`
- [x] 1.5.2 Add `graphql_arg_directives` table to `indexer/schemas/graphql_schema.py`
  - Columns: `id`, `field_id` (INTEGER FK), `arg_name` (TEXT FK), `directive_name`, `directive_args`
  - Indexes: `(field_id, arg_name)` composite
  - Unique: `(field_id, arg_name, directive_name)`

### 1.6 Database Manager Methods

**NOTE**: Database is a directory with mixin classes, not a single file:
- Package methods → `indexer/database/node_database.py`
- Docker/Compose/Terraform methods → `indexer/database/infrastructure_database.py`
- GraphQL methods → `indexer/database/graphql_database.py`

- [x] 1.6.1 Add `add_package_dependency()` method to `indexer/database/node_database.py`
  - Uses `generic_batches["package_dependencies"]` for batch insert
  - Handles is_dev and is_peer flags
- [x] 1.6.2 Add `add_package_script()` method to `indexer/database/node_database.py`
- [x] 1.6.3 Add `add_package_engine()` method to `indexer/database/node_database.py`
- [x] 1.6.4 Add `add_package_workspace()` method to `indexer/database/node_database.py`
- [x] 1.6.5 Add `add_dockerfile_port()` method to `indexer/database/infrastructure_database.py`
- [x] 1.6.6 Add `add_dockerfile_env_var()` method to `indexer/database/infrastructure_database.py`
- [x] 1.6.7 Add `add_compose_service_port()` method to `indexer/database/infrastructure_database.py`
- [x] 1.6.8 Add `add_compose_service_volume()` method to `indexer/database/infrastructure_database.py`
- [x] 1.6.9 Add `add_compose_service_env()` method to `indexer/database/infrastructure_database.py`
- [x] 1.6.10 Add `add_compose_service_capability()` method to `indexer/database/infrastructure_database.py`
- [x] 1.6.11 Add `add_compose_service_dep()` method to `indexer/database/infrastructure_database.py`
- [x] 1.6.12 Add `add_terraform_resource_property()` method to `indexer/database/infrastructure_database.py`
- [x] 1.6.13 Add `add_terraform_resource_dep()` method to `indexer/database/infrastructure_database.py`
- [x] 1.6.14 Add `add_graphql_field_directive()` method to `indexer/database/graphql_database.py`
- [x] 1.6.15 Add `add_graphql_arg_directive()` method to `indexer/database/graphql_database.py`
  - Note: Uses composite FK (field_id, arg_name), NOT arg_id

---

## Phase 2: Update Extractors (Python)

**NOTE**: All extractors in this scope are Python. No Node.js extractor changes required.

### 2.1 Package.json Extractor

**File**: `indexer/extractors/generic.py:335-360`
**Method**: `_extract_package_direct()`
**Current**: Calls `db_manager.add_package_config()` at line 345 with JSON in dependencies column

- [x] 2.1.1 Update `_extract_package_direct()` in `indexer/extractors/generic.py:335-360`
- [x] 2.1.2 After `add_package_config()` at line 345, call `add_package_dependency(file_path, deps_list)`
- [x] 2.1.3 After `add_package_config()`, call `add_package_script(file_path, scripts_list)`
- [x] 2.1.4 After `add_package_config()`, call `add_package_engine(file_path, engines_list)`
- [x] 2.1.5 After `add_package_config()`, call `add_package_workspace(file_path, workspaces_list)`
- [x] 2.1.6 Keep JSON column writes temporarily (dual-write for verification)

### 2.2 Dockerfile Extractor

**File**: `indexer/extractors/docker.py:56-134`
**Method**: `extract()`
**Current**: Calls `db_manager.add_docker_image()` at line 126 with JSON in exposed_ports column

- [x] 2.2.1 Update `extract()` in `indexer/extractors/docker.py:56-134`
- [x] 2.2.2 After `add_docker_image()` at line 126, call `add_dockerfile_port(file_path, ports_list)`
- [x] 2.2.3 After `add_docker_image()`, call `add_dockerfile_env_var(file_path, env_list)`
- [x] 2.2.4 Keep JSON column writes temporarily (dual-write for verification)

### 2.3 Docker Compose Extractor

**File**: `indexer/extractors/generic.py:128-198`
**Method**: `_extract_compose_direct()`
**Current**: Calls `db_manager.add_compose_service()` at line 177 with JSON in ports/volumes/environment columns

- [x] 2.3.1 Update `_extract_compose_direct()` in `indexer/extractors/generic.py:128-198`
- [x] 2.3.2 After `add_compose_service()` at line 177, call `add_compose_service_port(file_path, service_name, ports)`
- [x] 2.3.3 After `add_compose_service()`, call `add_compose_service_volume(file_path, service_name, volumes)`
- [x] 2.3.4 After `add_compose_service()`, call `add_compose_service_env(file_path, service_name, env)`
- [x] 2.3.5 After `add_compose_service()`, call `add_compose_service_capability(file_path, service_name, caps)`
- [x] 2.3.6 After `add_compose_service()`, call `add_compose_service_dep(file_path, service_name, deps)`
- [x] 2.3.7 Keep JSON column writes temporarily (dual-write for verification)

### 2.4 Terraform Extractor

**File**: `indexer/extractors/terraform.py`
**Current**: Uses `json.dumps(props)` for properties_json column

- [x] 2.4.1 Update terraform extraction in `indexer/extractors/terraform.py`
- [x] 2.4.2 After `add_terraform_resource()`, call `add_terraform_resource_property(resource_id, props)`
- [x] 2.4.3 After `add_terraform_resource()`, call `add_terraform_resource_dep(resource_id, deps)`
- [x] 2.4.4 Keep JSON column writes temporarily (dual-write for verification)

### 2.5 GraphQL Extractor (Python-Only)

**File**: `indexer/extractors/graphql.py:209-300`
**Methods**: `_extract_field()` at line 209, `_extract_field_arg()` at line 258
**Current**: `json.dumps(directives)` at lines 237 and 290

- [x] 2.5.1 Update `_extract_field()` in `indexer/extractors/graphql.py:209-256`
  - Keep JSON writes (dual-write), add junction table writes
- [x] 2.5.2 Update `_extract_field_arg()` in `indexer/extractors/graphql.py:258-304`
  - Keep JSON writes (dual-write), add junction table writes
- [x] 2.5.3 After field insertion, call `add_graphql_field_directive(field_id, directives)`
- [x] 2.5.4 After arg insertion, call `add_graphql_arg_directive(field_id, arg_name, directives)`
  - Note: Uses composite FK (field_id, arg_name), NOT arg_id
- [x] 2.5.5 Keep JSON column writes temporarily (dual-write for verification)

---

## Phase 3: Verification (No Node.js Changes Required)

**IMPORTANT**: GraphQL extraction is Python-only (`indexer/extractors/graphql.py`). There is NO `ast_extractors/javascript/graphql_extractors.js` file.

Package.json extraction is also Python-only (`indexer/extractors/generic.py:335-377`). The `ast_extractors/javascript/module_framework.js` file exists but does NOT handle package.json extraction.

### 3.1 Verify No Node.js Changes Needed

- [x] 3.1.1 Confirmed: `ast_extractors/javascript/graphql_extractors.js` does NOT exist
- [x] 3.1.2 Confirmed: Package.json handled by Python `generic.py`, not Node.js
- [x] 3.1.3 Verify all junction table inserts happen in Python layer only

---

## Phase 4: Remove JSON Column Writes

### 4.1 Verify Junction Table Data

- [x] 4.1.1 Run `aud full --index` on test project
- [x] 4.1.2 Query junction tables to verify data populated
- [x] 4.1.3 Compare junction table data to JSON column data for accuracy

### 4.2 Remove Dual Writes

- [x] 4.2.1 Remove `json.dumps(dependencies)` from package.json extractor (generic.py)
- [x] 4.2.2 Remove `json.dumps(exposed_ports)` from dockerfile extractor (docker.py)
- [x] 4.2.3 Remove `json.dumps(ports)` from docker-compose extractor (generic.py)
- [x] 4.2.4 Remove `json.dumps(properties)` from terraform extractor (infrastructure_storage.py)
- [x] 4.2.5 Remove `json.dumps(directives)` from graphql extractor (infrastructure_storage.py)

---

## Phase 5: Remove JSON File Writes - SKIPPED

**DECISION (2025-11-29)**: Phase 5 SKIPPED per architect decision. `.pf/raw/*.json` files are useful for debugging and external tool consumption. JSON file writes remain.

### 5.1 Remove Engine JSON Writes - SKIPPED

- [~] 5.1.1 SKIPPED - Keep `_write_to_json()` method in `vulnerability_scanner.py`
- [~] 5.1.2 SKIPPED - Keep `write_vulnerabilities_json()` function
- [~] 5.1.3 SKIPPED - Keep JSON write function calls
- [~] 5.1.4 SKIPPED - Keep `write_deps_latest_json()` function
- [~] 5.1.5 SKIPPED - Keep calls to `write_deps_latest_json()`
- [~] 5.1.6 SKIPPED - Keep JSON output from cfg.py
- [~] 5.1.7 SKIPPED - Keep JSON output from terraform.py
- [~] 5.1.8 SKIPPED - Keep JSON output from docker_analyze.py
- [~] 5.1.9 SKIPPED - Keep JSON output from workflows.py
- [~] 5.1.10 SKIPPED - Keep JSON output from detect_frameworks.py

### 5.2 Update Callers - SKIPPED

- [~] 5.2.1 SKIPPED - No changes to pipelines.py
- [~] 5.2.2 SKIPPED - No changes to JSON output path parameters

---

## Phase 6: Deprecate .pf/readthis/ - ALREADY DONE

**NOTE (2025-11-29)**: Phase 6 was ALREADY COMPLETED by previous tickets. The `commands/report.py` file no longer exists, and `.pf/readthis/` is not generated.

### 6.1 Delete Report Command - ALREADY DONE

- [x] 6.1.1 `commands/report.py` already deleted (previous ticket)
- [x] 6.1.2 `report` command already removed from `cli.py`
- [x] 6.1.3 Report already removed from `pipelines.py`

### 6.2 Remove Chunk Generation - ALREADY DONE

- [x] 6.2.1 Chunk generation already removed
- [x] 6.2.2 Chunk output already removed from taint.py
- [x] 6.2.3 Chunk output already removed from workflows.py
- [x] 6.2.4 Chunk output already removed from detect_patterns.py

### 6.3 Update Pipeline References - ALREADY DONE

- [x] 6.3.1 Readthis references already removed from full.py
- [x] 6.3.2 Readthis file counting already removed from pipelines.py

---

## Phase 7: Testing and Verification

### 7.1 Schema Tests

- [x] 7.1.1 Test for junction tables existence - schema contract tests pass
- [x] 7.1.2 All 15 junction tables verified in schema - 170 total tables
- [x] 7.1.3 Schema contract tests updated: `test_schema_contract.py`, `test_node_schema_contract.py`

### 7.2 Extraction Tests

- [x] 7.2.1 Package.json extraction populates junction tables (verified via pipeline)
- [x] 7.2.2 Dockerfile extraction populates junction tables (verified via pipeline)
- [x] 7.2.3 Docker-compose extraction populates junction tables (verified via pipeline)
- [x] 7.2.4 Terraform extraction populates junction tables (53 properties, 1 dep)
- [x] 7.2.5 GraphQL extraction populates junction tables (verified via pipeline)

### 7.3 Integration Tests

- [x] 7.3.1 Run `aud full --offline` on TheAuditor codebase - 24/24 phases pass
- [x] 7.3.2 Verify junction tables populated with correct data
- [x] 7.3.3 Verify no `.pf/readthis/` directory created (already done by previous ticket)
- [x] 7.3.4 Schema contract tests pass (40/40)

### 7.4 Query Tests

- [x] 7.4.1 Query `package_dependencies` and verify expected data
- [x] 7.4.2 Query `terraform_resource_properties` - 53 rows
- [x] 7.4.3 Query `terraform_resource_deps` - 1 row

### 7.5 Additional Fixes (2025-11-29)

- [x] 7.5.1 Fixed `terraform/graph.py` to read from junction tables instead of removed JSON columns
- [x] 7.5.2 Fixed `rules/terraform/terraform_analyze.py` to read from junction tables
- [x] 7.5.3 Updated `test_schema_contract.py` table count: 155 → 170
- [x] 7.5.4 Updated `test_node_schema_contract.py` table counts: 47 → 51, 155 → 170

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

| Phase | Tasks | Status |
|-------|-------|--------|
| 1. Schema (Junction Tables) | 21 | COMPLETE |
| 2. Python Extractors | 24 | COMPLETE |
| 3. Verification | 3 | COMPLETE |
| 4. Remove JSON Columns | 8 | COMPLETE |
| 5. Remove JSON Files | 12 | SKIPPED |
| 6. Deprecate Readthis | 7 | ALREADY DONE |
| 7. Testing | 16 | COMPLETE |
| 8. Documentation | 5 | PENDING |

**TICKET STATUS: IMPLEMENTATION COMPLETE (2025-11-29)**

**Completed Scope**: Phase 1-4, 6-7
- All 15 junction tables created in schema files
- All 15 database methods added to mixin classes
- All extractors write to junction tables ONLY (no JSON blobs)
- ZERO FALLBACK: No dual-write, junction tables are single source of truth
- All downstream readers updated (terraform/graph.py, terraform_analyze.py)
- Schema contract tests updated and passing (40/40)
- Pipeline passes all 24 phases

**Skipped Scope**: Phase 5
- `.pf/raw/*.json` file writes remain per architect decision
- JSON files useful for debugging and external tool consumption

**Remaining**: Phase 8 Documentation (optional)

**Key Changes**:
1. Phase 3 reduced from "Node Extractors" to "Verification" (GraphQL/package.json are Python-only)
2. Phase 5 skipped per architect decision
3. Phase 6 already done by previous tickets
4. Additional fixes for downstream readers that queried removed JSON columns
