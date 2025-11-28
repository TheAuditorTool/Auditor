# JSON Readers & Writers Audit

**Date:** 2025-11-28
**Purpose:**
1. Identify files writing JSON to `.pf/raw/` and `.pf/readthis/` - DEPRECATED, readers must query DB
2. Identify JSON BLOBS stored in database columns - BANNED, need real junction tables

---

## PART 1: ENGINE OUTPUT MAPPING

Every analyzer/tool that produces output is an "engine". Current state:

### Engines That Write to .pf/raw/ (MUST READ FROM DB INSTEAD)

| Engine | File | JSON Output | DB Table | Status |
|--------|------|-------------|----------|--------|
| **FCE** | `fce.py:1587-1600` | `fce.json`, `fce_failures.json` | `findings_consolidated` | Has DB, remove JSON read |
| **Vulnerability Scanner** | `vulnerability_scanner.py:630,709` | `vulnerabilities.json` | `findings_consolidated` | Has DB, remove JSON read |
| **Taint Analyzer** | `taint/core.py:1034` | `taint_analysis.json` | `taint_flows`, `resolved_flow_audit` | Has DB, remove JSON read |
| **Linters** | `linters/linters.py:614` | `lint.json` | `findings_consolidated` | Has DB, remove JSON read |
| **Graph Analyzer** | `commands/graph.py:488,499,505` | `graph_analysis.json`, `graph_metrics.json`, `graph_summary.json` | `graphs.db` tables | Has DB, remove JSON read |
| **Deps Scanner** | `deps.py:544,1220` | `deps.json`, `deps_latest.json` | `deps_version_cache` | Partial, needs full DB |
| **CFG Analyzer** | `commands/cfg.py:235` | `cfg_analysis.json` | `cfg_blocks`, `cfg_edges` | Has DB, remove JSON read |
| **Metadata Collector** | `metadata_collector.py:152,315` | `churn_analysis.json`, `coverage_analysis.json` | `findings_consolidated` | Has DB, remove JSON read |
| **Terraform Analyzer** | `commands/terraform.py:153,263` | `terraform_graph.json`, `terraform_findings.json` | `terraform_*` tables | Has DB, remove JSON read |
| **Docker Analyzer** | `commands/docker_analyze.py:248` | `docker_findings.json` | `docker_*` tables | Has DB, remove JSON read |
| **Workflow Analyzer** | `commands/workflows.py:162` | `github_workflows.json` | `github_*` tables | Has DB, remove JSON read |
| **Framework Detector** | `commands/detect_frameworks.py:221` | `frameworks.json` | `framework_detection` | Has DB, remove JSON read |
| **Deadcode Analyzer** | `commands/deadcode.py:202` | `deadcode.json` | ? | NEEDS DB TABLE |
| **Summary Generator** | `commands/summary.py:325` | `audit_summary.json` | ? | NEEDS DB TABLE |
| **ML Insights** | `insights/ml.py:1021` | `graph_metrics.json` | ? | NEEDS DB TABLE |

### Engines Writing to .pf/readthis/ (DEPRECATED - REMOVE ENTIRELY)

| Engine | File | Output | Action |
|--------|------|--------|--------|
| Context Chunker | `commands/context.py:312,409` | `semantic_context_*.json` | DELETE |
| Taint Chunker | `commands/taint.py:165` | `taint_chunk*.json` | DELETE |
| Pattern Chunker | `commands/detect_patterns.py:91` | `patterns_*.json` | DELETE |
| Workflow Chunker | `commands/workflows.py:108` | `github_workflows_*.json` | DELETE |
| Report Generator | `commands/report.py` | ALL chunks | DELETE ENTIRE COMMAND |

---

## PART 2: JSON BLOB VIOLATIONS IN DATABASE

These store `json.dumps()` in TEXT columns instead of proper junction tables:

### indexer/database/node_database.py (8 violations)

| Line | Column | Data Type | Fix: Create Junction Table |
|------|--------|-----------|---------------------------|
| 146 | `dependency_array` | array of deps | `node_import_dependencies` |
| 217 | `dependencies` | object | `node_function_dependencies` |
| 242 | `modifiers` | array | `node_symbol_modifiers` |
| 476 | `dependencies` | object | `package_dependencies` |
| 477 | `dev_dependencies` | object | `package_dev_dependencies` |
| 478 | `peer_dependencies` | object | `package_peer_dependencies` |
| 479 | `scripts` | object | `package_scripts` |
| 480-481 | `engines`, `workspaces` | object/array | `package_engines`, `package_workspaces` |
| 508 | `duplicate_packages` | array | `lockfile_duplicates` |

### indexer/database/python_database.py (1 violation)

| Line | Column | Fix |
|------|--------|-----|
| 78 | `dependencies` | `python_config_dependencies` junction |

### indexer/database/infrastructure_database.py (12 violations)

| Line | Column | Fix |
|------|--------|-----|
| 29 | `exposed_ports` | `dockerfile_ports` junction |
| 30 | `env_vars` | `dockerfile_env_vars` junction |
| 31 | `build_args` | `dockerfile_build_args` junction |
| 77 | `ports` | `compose_service_ports` junction |
| 78 | `volumes` | `compose_service_volumes` junction |
| 79 | `environment` | `compose_service_env` junction |
| 81-87 | `cap_add`, `cap_drop`, `security_opt`, `command`, `entrypoint`, `depends_on`, `healthcheck` | Individual junction tables |
| 115 | `directives` | `nginx_directives` junction |

### indexer/extractors/github_actions.py (10 violations)

| Line | Column | Fix |
|------|--------|-----|
| 109-115 | `on_triggers` | `workflow_triggers` junction |
| 118 | `permissions` | `workflow_permissions` junction |
| 121 | `concurrency` | `workflow_concurrency` (or scalar columns) |
| 124 | `env` | `workflow_env_vars` junction |
| 152-154 | `runs_on` | `job_runners` junction |
| 159 | `strategy` | `job_matrix_strategies` junction |
| 162 | `permissions` | `job_permissions` junction |
| 165 | `env` | `job_env_vars` junction |
| 233 | `env` | `step_env_vars` junction |
| 236 | `with_args` | `step_with_args` junction |

### indexer/extractors/graphql.py (3 violations)

| Line | Column | Fix |
|------|--------|-----|
| 190 | `implements` | `graphql_type_implements` junction |
| 237 | `directives` | `graphql_field_directives` junction |
| 290 | `directives` | `graphql_arg_directives` junction |

### indexer/extractors/python_deps.py (3 violations)

| Line | Column | Fix |
|------|--------|-----|
| 248 | `dependencies` | `pyproject_dependencies` junction |
| 249 | `optional_dependencies` | `pyproject_optional_deps` junction |
| 250 | `build_system` | scalar columns or `pyproject_build_system` |

### indexer/extractors/terraform.py (1 violation)

| Line | Column | Fix |
|------|--------|-----|
| 146 | `providers` | `terraform_module_providers` junction |

### indexer/storage/python_storage.py (5 violations)

| Line | Column | Fix |
|------|--------|-----|
| 215 | `pattern_types` | `context_manager_patterns` junction |
| 218 | `exception_types` | `context_manager_exceptions` junction |
| 221 | `cleanup_calls` | `context_manager_cleanup` junction |
| 263 | `parameters` | `lambda_parameters` junction |
| 266 | `captured_vars` | `lambda_captured_vars` junction |

### indexer/storage/infrastructure_storage.py (5 violations)

| Line | Column | Fix |
|------|--------|-----|
| 61 | `properties` | `terraform_resource_properties` junction |
| 62 | `depends_on` | `terraform_resource_deps` junction |
| 63 | `sensitive_flags` | `terraform_sensitive_properties` junction |
| 79 | `default` | scalar or `terraform_variable_defaults` |
| 100-122 | `value` | scalar or junction based on type |

### indexer/storage/core_storage.py (1 violation)

| Line | Column | Fix |
|------|--------|-----|
| 244 | `parameters` | Already has `function_parameters` table - verify usage |

### graph/store.py (3 violations)

| Line | Column | Fix |
|------|--------|-----|
| 64 | `metadata` (nodes) | `graph_node_metadata` junction |
| 82 | `metadata` (edges) | `graph_edge_metadata` junction |
| 316 | `result` | `analysis_result_details` junction |

### Other Files (5 violations)

| File | Line | Column | Fix |
|------|------|--------|-----|
| `planning/manager.py` | 147, 331 | `metadata`, `files_affected` | `plan_metadata`, `plan_files` junctions |
| `commands/refactor.py` | 297 | `details_json` | `refactor_details` junction |
| `vulnerability_scanner.py` | 622 | `details` | `vulnerability_details` junction |
| `session/store.py` | 138 | `diffs_scored` | `session_diffs` junction |

---

## PART 3: FILES THAT READ JSON (MUST QUERY DB)

| File | What It Reads | Query Instead |
|------|---------------|---------------|
| `rules/dependency/update_lag.py:52` | `deps_latest.json` | `deps_version_cache` table |
| `insights/ml/intelligence.py:597-607` | ALL raw artifacts | Individual DB tables |
| `insights/ml.py:1021` | `graph_metrics.json` | `graphs.db` tables |
| `commands/insights.py:276,333` | `graph_analysis.json`, `taint_analysis.json` | DB tables |
| `commands/graph.py:713` | `graph_analysis.json` | `graphs.db` tables |
| `commands/summary.py` | All `.pf/raw/*.json` | `findings_consolidated` + other tables |
| `config_runtime.py:25` | `fce_json` path | Remove config, query DB |
| `pipelines.py:383` | `deps.json` | Pass DB path |
| `fce.py:716,731,828,864` | Various JSON | Already DB-first, verify no fallbacks |

---

## SUMMARY: TOTAL VIOLATIONS

| Category | Count |
|----------|-------|
| Engines writing to .pf/raw/ | 15 |
| Engines writing to .pf/readthis/ | 5 |
| JSON blob columns in DB | **~50** |
| Files reading JSON instead of DB | 9 |

---

## PRIORITY ORDER FOR FIXES

### Week 1: Stop JSON File I/O
1. Remove all JSON writes to `.pf/raw/`
2. Update all readers to query database
3. Delete `.pf/readthis/` and `commands/report.py`

### Week 2-3: Normalize Node Schema (8 blobs)
- `node_database.py` junction tables for deps, scripts, engines, etc.

### Week 3-4: Normalize Infrastructure Schema (17 blobs)
- `infrastructure_database.py` + `infrastructure_storage.py` junctions
- `github_actions.py` workflow/job/step junctions

### Week 4+: Normalize Everything Else (~25 blobs)
- GraphQL, Terraform, Python storage
- Graph metadata, planning, vulnerability details

---

## HANDOFF FOR TOMORROW

**TL;DR:**
- **~15 engines** write JSON files that should just stay in DB
- **~50 JSON blobs** stored in DB columns need real junction tables
- **~9 files** read JSON when they should query DB

**The rule going forward:**
- NO `json.dump()` to `.pf/raw/` or `.pf/readthis/`
- NO `json.dumps()` into database TEXT columns
- ALL data in normalized tables with proper foreign keys

**Start here:**
1. Pick `vulnerability_scanner.py` - already writes to DB
2. Find who reads `vulnerabilities.json`
3. Update them to query `findings_consolidated`
4. Remove the JSON write
5. Repeat

Good night!
