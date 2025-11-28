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

**ACTUAL COUNT: 19 blob columns across 8 tables** (not 50 - previous grep over-counted code paths)

Recent schema normalizations FIXED:
- Python symbols/functions/classes - junction tables exist
- Node.js imports/exports - 8 junction tables added (commit 811cd5c)
- Angular/Vue components - normalized
- CFG blocks/edges - normalized
- Findings consolidated - normalized (commit 75c74d0)

### Still Need Fixing: 19 Blob Columns

#### package_configs (6 blobs)
| Column | Fix |
|--------|-----|
| `dependencies` | `package_dependencies` junction |
| `dev_dependencies` | `package_dev_dependencies` junction |
| `peer_dependencies` | `package_peer_dependencies` junction |
| `scripts` | `package_scripts` junction |
| `engines` | `package_engines` junction |
| `workspaces` | `package_workspaces` junction |

#### docker_images (3 blobs)
| Column | Fix |
|--------|-----|
| `exposed_ports` | `dockerfile_ports` junction |
| `env_vars` | `dockerfile_env_vars` junction |
| `build_args` | `dockerfile_build_args` junction |

#### compose_services (10 blobs)
| Column | Fix |
|--------|-----|
| `ports` | `compose_service_ports` junction |
| `volumes` | `compose_service_volumes` junction |
| `environment` | `compose_service_env` junction |
| `cap_add` | `compose_service_capabilities` junction |
| `cap_drop` | (same junction, with add/drop flag) |
| `security_opt` | `compose_service_security_opts` junction |
| `command` | scalar or `compose_service_commands` |
| `entrypoint` | scalar or same table |
| `depends_on` | `compose_service_deps` junction |
| `healthcheck` | `compose_service_healthcheck` (scalar columns) |

#### terraform_* tables (5 blobs)
| Table.Column | Fix |
|--------------|-----|
| `terraform_files.providers_json` | `terraform_providers` junction |
| `terraform_resources.properties_json` | `terraform_resource_properties` junction |
| `terraform_resources.depends_on_json` | `terraform_resource_deps` junction |
| `terraform_resources.sensitive_flags_json` | `terraform_sensitive_props` junction |
| `terraform_variables.default_json` | scalar or junction |
| `terraform_variable_values.variable_value_json` | scalar |
| `terraform_outputs.value_json` | scalar |
| `terraform_findings.graph_context_json` | `terraform_finding_context` junction |

#### graphql_* tables (2 blobs)
| Table.Column | Fix |
|--------------|-----|
| `graphql_fields.directives_json` | `graphql_field_directives` junction |
| `graphql_field_args.directives_json` | `graphql_arg_directives` junction |

#### Acceptable Blobs (path serialization)
| Table.Column | Why OK |
|--------------|--------|
| `taint_flows.path_json` | Array of hops - junction would be overkill |
| `resolved_flow_audit.path_json` | Same - serialized path trace |
| `plans.metadata_json` | Freeform plan metadata |
| `refactor_history.details_json` | Freeform refactor details |
| `refactor_candidates.metadata_json` | Freeform metadata |
| `code_snapshots.files_json` | Snapshot blob - acceptable |
| `bullmq_queues.redis_config` | External config passthrough |

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

## SUMMARY: ACTUAL VIOLATIONS

| Category | Count |
|----------|-------|
| Engines writing to .pf/raw/ | 15 |
| Engines writing to .pf/readthis/ | 5 |
| JSON blob columns in DB | **19** (only ~12 need fixing) |
| Files reading JSON instead of DB | 9 |

---

## PRIORITY ORDER FOR FIXES

### Week 1: Stop JSON File I/O
1. Remove all JSON writes to `.pf/raw/`
2. Update all readers to query database
3. Delete `.pf/readthis/` and `commands/report.py`

### Week 2: Normalize package_configs (6 blobs)
- Create junction tables for deps, scripts, engines, workspaces
- Update `node_database.py` and extractors

### Week 3: Normalize Docker/Compose (13 blobs)
- Create junction tables for ports, volumes, env, caps, etc.
- Update `infrastructure_database.py`

### Week 4: Normalize Terraform (5 blobs) + GraphQL (2 blobs)
- Create junction tables for providers, properties, directives

---

## HANDOFF FOR TOMORROW

**TL;DR:**
- **15 engines** write JSON files that should just stay in DB
- **19 JSON blobs** in DB, but only **~12 need fixing** (7 are acceptable)
- **9 files** read JSON when they should query DB

**Already fixed (don't re-audit):**
- Python schema - normalized to junction tables
- Node.js imports/exports - 8 junction tables
- Findings consolidated - typed columns
- CFG blocks/edges - normalized

**The rule going forward:**
- NO `json.dump()` to `.pf/raw/` or `.pf/readthis/`
- NO `json.dumps()` into database TEXT columns (except path traces)
- ALL data in normalized tables with proper foreign keys

**Start here:**
1. Pick `vulnerability_scanner.py` - already writes to DB
2. Find who reads `vulnerabilities.json`
3. Update them to query `findings_consolidated`
4. Remove the JSON write
5. Repeat

Good night!
