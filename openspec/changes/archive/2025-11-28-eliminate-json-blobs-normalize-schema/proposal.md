# Eliminate JSON Blobs and Normalize Schema

**Status**: PROPOSAL - Awaiting Architect Approval
**Change ID**: `eliminate-json-blobs-normalize-schema`
**Complexity**: MEDIUM (~20 files, ~800 lines changed)
**Breaking**: YES - Schema changes require migration + re-index
**Risk Level**: MEDIUM - Touches core extraction and database schema (pipeline cleanup already done)
**Prerequisite**: SATISFIED - `consolidate-findings-queries` completed, `findings_consolidated` in active use

---

## Why

### Problem Statement

TheAuditor violates its own "Database First" principle in two ways:

1. **JSON Blob Columns**: 19 TEXT columns store `json.dumps()` data instead of normalized junction tables. This breaks:
   - Query capability (can't JOIN on JSON content)
   - Data integrity (no FK constraints on blob contents)
   - Schema contract (consumers must parse JSON, not query columns)

2. **Redundant JSON File I/O**: 15 engines write to `.pf/raw/*.json` AND insert to database. This causes:
   - Split-brain reads (some code reads JSON, some reads DB)
   - Wasted I/O (writing same data twice)
   - Maintenance burden (two code paths to maintain)

3. **Deprecated `.pf/readthis/`**: This directory exists for "AI-optimized chunks" but:
   - AI tools (Claude, Cursor) can query database directly via `aud context query`
   - Chunking logic is fragile and unmaintained
   - `commands/report.py` is marked DEPRECATED but still runs

### Root Cause Evidence (VERIFIED 2025-11-28)

**JSON Blob Columns in Database** (19 columns across 6 tables):

| Table | Column | Current Type | Needs Junction |
|-------|--------|--------------|----------------|
| `package_configs` | `dependencies` | TEXT (JSON) | `package_dependencies` |
| `package_configs` | `dev_dependencies` | TEXT (JSON) | `package_dev_dependencies` |
| `package_configs` | `peer_dependencies` | TEXT (JSON) | `package_peer_dependencies` |
| `package_configs` | `scripts` | TEXT (JSON) | `package_scripts` |
| `package_configs` | `engines` | TEXT (JSON) | `package_engines` |
| `package_configs` | `workspaces` | TEXT (JSON) | `package_workspaces` |
| `docker_images` | `exposed_ports` | TEXT (JSON) | `dockerfile_ports` |
| `docker_images` | `env_vars` | TEXT (JSON) | `dockerfile_env_vars` |
| `docker_images` | `build_args` | TEXT (JSON) | `dockerfile_build_args` |
| `compose_services` | `ports` | TEXT (JSON) | `compose_service_ports` |
| `compose_services` | `volumes` | TEXT (JSON) | `compose_service_volumes` |
| `compose_services` | `environment` | TEXT (JSON) | `compose_service_env` |
| `compose_services` | `cap_add` | TEXT (JSON) | `compose_service_capabilities` |
| `compose_services` | `cap_drop` | TEXT (JSON) | (same table, add/drop flag) |
| `compose_services` | `depends_on` | TEXT (JSON) | `compose_service_deps` |
| `terraform_resources` | `properties_json` | TEXT (JSON) | `terraform_resource_properties` |
| `terraform_resources` | `depends_on_json` | TEXT (JSON) | `terraform_resource_deps` |
| `graphql_fields` | `directives_json` | TEXT (JSON) | `graphql_field_directives` |
| `graphql_field_args` | `directives_json` | TEXT (JSON) | `graphql_arg_directives` |

**Engines Writing Redundant JSON** (VERIFIED via grep):

| Engine | File | JSON Output | DB Table | Action |
|--------|------|-------------|----------|--------|
| Vulnerability Scanner | `vulnerability_scanner.py:630,709` | `vulnerabilities.json` | `findings_consolidated` | Remove JSON write |
| Deps Scanner | `deps.py:1212` | `deps_latest.json` | `deps_version_cache` | Remove JSON write |
| CFG Analyzer | `commands/cfg.py:235` | `cfg_analysis.json` | `cfg_blocks`, `cfg_edges` | Remove JSON write |
| Terraform Analyzer | `commands/terraform.py:153,263` | `terraform_*.json` | `terraform_*` tables | Remove JSON write |
| Docker Analyzer | `commands/docker_analyze.py:248` | `docker_findings.json` | `docker_*` tables | Remove JSON write |
| Workflow Analyzer | `commands/workflows.py:162` | `github_workflows.json` | `github_*` tables | Remove JSON write |
| Framework Detector | `commands/detect_frameworks.py:221` | `frameworks.json` | `framework_detection` | Remove JSON write |

**.pf/readthis/ Still Active** (VERIFIED):
- `context.py:312` - Creates semantic context chunks
- `detect_patterns.py:91` - Creates pattern chunks
- `taint.py:165` - Creates taint chunks
- `workflows.py:108` - Creates workflow chunks
- `report.py:104` - Main generator (DEPRECATED)

---

## What Changes

### Part A: Normalize JSON Blob Columns (Schema)

Create 15 new junction tables to replace JSON TEXT columns.

**Parent Table Primary Keys (VERIFIED)**:
| Parent Table | Primary Key | Type |
|--------------|-------------|------|
| `package_configs` | `file_path` | TEXT |
| `docker_images` | `file_path` | TEXT |
| `compose_services` | `(file_path, service_name)` | COMPOSITE |
| `terraform_resources` | `resource_id` | TEXT |
| `graphql_fields` | `field_id` | INTEGER AUTOINCREMENT |
| `graphql_field_args` | `(field_id, arg_name)` | COMPOSITE (NO arg_id column!) |

**Junction Tables**:
```
package_dependencies         (file_path TEXT FK, name, version_spec, is_dev, is_peer)
package_scripts              (file_path TEXT FK, script_name, script_command)
package_engines              (file_path TEXT FK, engine_name, version_spec)
package_workspaces           (file_path TEXT FK, workspace_path)
dockerfile_ports             (file_path TEXT FK, port, protocol)
dockerfile_env_vars          (file_path TEXT FK, var_name, var_value, is_build_arg)
compose_service_ports        (file_path TEXT FK, service_name TEXT FK, host_port, container_port, protocol)
compose_service_volumes      (file_path TEXT FK, service_name TEXT FK, host_path, container_path, mode)
compose_service_env          (file_path TEXT FK, service_name TEXT FK, var_name, var_value)
compose_service_capabilities (file_path TEXT FK, service_name TEXT FK, capability, is_add)
compose_service_deps         (file_path TEXT FK, service_name TEXT FK, depends_on_service, condition)
terraform_resource_properties(resource_id TEXT FK, property_name, property_value, property_type)
terraform_resource_deps      (resource_id TEXT FK, depends_on_resource)
graphql_field_directives     (field_id INTEGER FK, directive_name, directive_args)
graphql_arg_directives       (field_id INTEGER FK, arg_name TEXT FK, directive_name, directive_args)
```

### Part B: Update Extractors (Write to Junction Tables)

**VERIFIED FILE LOCATIONS**:

| Extractor | File:Lines | Current | After |
|-----------|------------|---------|-------|
| Package.json | `indexer/extractors/generic.py:335-360` | `json.dumps(deps)` in `_extract_package_direct()` | INSERT to `package_dependencies` |
| Dockerfile | `indexer/extractors/docker.py:56-134` | `json.dumps(ports)` in `extract()` | INSERT to `dockerfile_ports` |
| Docker Compose | `indexer/extractors/generic.py:128-198` | `json.dumps(env)` in `_extract_compose_direct()` | INSERT to `compose_service_env` |
| Terraform | `indexer/extractors/terraform.py` | `json.dumps(props)` | INSERT to `terraform_resource_properties` |
| GraphQL | `indexer/extractors/graphql.py:209-300` | `json.dumps(directives)` at lines 237, 290 | INSERT to `graphql_*_directives` |

**NOTE**: GraphQL extraction is **Python-only**. There is NO Node.js GraphQL extractor.

### Part C: Remove Redundant JSON Writes

| File | Lines | Current | After |
|------|-------|---------|-------|
| `vulnerability_scanner.py` | 630, 709 | `_write_to_json()` | DELETE method |
| `deps.py` | 1211-1220 | `write_deps_latest_json()` | DELETE function |
| `commands/cfg.py` | 235 | JSON output | Remove, data already in DB |
| `commands/terraform.py` | 153, 263 | JSON output | Remove, data already in DB |
| `commands/docker_analyze.py` | 248 | JSON output | Remove, data already in DB |
| `commands/workflows.py` | 162 | JSON output | Remove, data already in DB |
| `commands/detect_frameworks.py` | 221 | JSON output | Remove, data already in DB |

### Part D: Deprecate .pf/readthis/ - ALREADY COMPLETE

**Status**: DONE (verified 2025-11-28)

Previous tickets already completed this work:
- `commands/report.py` - DELETED (file does not exist)
- `context.py` - Rewritten, only 328 lines, no chunk generation
- `taint.py`, `workflows.py` - No readthis/chunk references
- `full.py`, `pipelines.py` - No readthis references

**No action required for Part D.**

---

## Impact

### Affected Specs

| Spec | Type | Why |
|------|------|-----|
| `indexer` | MODIFIED | New junction tables in schema, extractor changes |
| `pipeline` | MODIFIED | Remove JSON writes, deprecate readthis |

### Affected Code

| Component | Files | Change Type |
|-----------|-------|-------------|
| Schema definitions | `indexer/schemas/*.py` | ADD 15 tables |
| Database manager | `indexer/database/node_database.py`, `indexer/database/infrastructure_database.py`, `indexer/database/graphql_database.py` | ADD junction table methods |
| Extractors | `indexer/extractors/*.py` | MODIFY to use junction tables |
| Engines | `vulnerability_scanner.py`, `deps.py`, commands/* | REMOVE JSON writes |
| ~~Report command~~ | ~~`commands/report.py`~~ | ~~DELETE~~ ALREADY DONE |
| ~~Pipeline~~ | ~~`pipelines.py`, `full.py`~~ | ~~REMOVE readthis handling~~ ALREADY DONE |

### Breaking Changes

1. **Schema change** - Requires `aud full --index` after deployment
2. **JSON files removed** - External tools reading `.pf/raw/*.json` will break
3. ~~**readthis removed**~~ - ALREADY DONE (nothing reads `.pf/readthis/` anymore)

### Migration Path

1. Deploy code changes
2. Run `aud full --index` to rebuild database with new schema
3. Old `.pf/raw/*.json` files remain (read-only archive) but new runs won't create them
4. ~~Delete `.pf/readthis/` directory manually~~ - N/A (directory no longer generated)

---

## Polyglot Assessment

**Q: Does this need Python + Node + Rust implementations?**

**A: Python only. No Node.js changes required.**

| Component | Language | Change Required |
|-----------|----------|-----------------|
| Schema definitions | Python | YES - new tables in `node_schema.py`, `infrastructure_schema.py` |
| Database manager | Python | YES - junction table methods in `database.py` |
| Python extractors | Python | YES - `generic.py`, `docker.py`, `terraform.py`, `graphql.py` |
| Node AST extractors | JavaScript | NO - package.json handled by Python `generic.py`, no GraphQL JS extractor exists |
| Rust tree-sitter | Rust | NO - parsing only, doesn't touch DB |
| Pipeline/CLI | Python | YES - remove JSON writes |

**Orchestrator**: `indexer/__init__.py` (Python) - passes file_path context to extractors.

**VERIFIED**: No Node.js extractor changes needed:
- `ast_extractors/javascript/graphql_extractors.js` - **FILE DOES NOT EXIST**
- `ast_extractors/javascript/module_framework.js` - Exists but does NOT handle package.json extraction
- Package.json extraction is in Python: `indexer/extractors/generic.py:335-377`

---

## Relationship to Other Changes

| Change | Relationship |
|--------|--------------|
| `consolidate-findings-queries` | PREREQUISITE - Fixes JSON readers; this fixes writers |
| `refactor-extraction-zero-fallback-dedup` | PARALLEL - Can proceed independently |
| `add-fidelity-transaction-handshake` | NO CONFLICT - Different subsystem |

---

## Success Criteria

- [ ] No `json.dumps()` calls storing to TEXT columns (except acceptable exceptions)
- [ ] No `json.dump()` calls to `.pf/raw/` in modified engines
- [x] No `.pf/readthis/` directory created by `aud full` - VERIFIED DONE
- [x] `commands/report.py` deleted - VERIFIED DONE
- [ ] All 15 junction tables exist in schema.py
- [ ] `aud full --offline` completes without JSON I/O errors
- [ ] Existing tests pass after schema migration

---

## Acceptable Exceptions (DO NOT NORMALIZE)

These JSON columns are acceptable because they store serialized paths/traces, not queryable data:

| Table.Column | Why OK |
|--------------|--------|
| `taint_flows.path_json` | Serialized hop trace - junction would be overkill |
| `resolved_flow_audit.path_json` | Same - path serialization |
| `plans.metadata_json` | Freeform AI plan metadata |
| `refactor_history.details_json` | Freeform refactor context |
| `code_snapshots.files_json` | Snapshot blob - not queryable |
| `bullmq_queues.redis_config` | External config passthrough |

---

## Next Step

Architect reviews and approves/denies this proposal.
