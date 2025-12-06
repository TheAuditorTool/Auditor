# Proposal: Standardize Extractor Fidelity - Eliminate Shadow IT

## Status

**COMPLETE** (Completed: 2025-12-04)

## Why

Five extractors bypass the fidelity system entirely. They write directly to the database via `db_manager.add_*()` calls and return empty or near-empty dictionaries. This means:

1. **No manifests generated** - extraction counts are invisible
2. **No receipts generated** - storage layer never sees the data
3. **Fidelity reconciliation always passes** - 0 vs 0 = SUCCESS masks failures
4. **Data loss is undetectable** - if extraction fails partially, nobody knows

### The Shadow IT Pattern (VIOLATORS)

| Extractor | Direct DB Calls | Returns |
|-----------|-----------------|---------|
| `docker.py` | `add_docker_image()`, `add_dockerfile_port()`, `add_dockerfile_env_var()` | `{}` |
| `github_actions.py` | `add_github_workflow()`, `add_github_job()`, `add_github_step()`, etc. | `{"imports": [], ...}` |
| `prisma.py` | `add_prisma_model()` | `{}` |
| `generic.py` | `add_compose_*()`, `add_nginx_config()` | `{"imports": [], ...}` |
| `manifest_extractor.py` | `add_package_*()`, `add_python_*()` | `{"imports": [], ...}` |

### The Gold Standard (COMPLIANT)

| Extractor | Pattern | FidelityToken |
|-----------|---------|---------------|
| `go.py` | Returns data dict | `FidelityToken.attach_manifest(result)` |
| `rust.py` | Returns data dict | `FidelityToken.attach_manifest(result)` |
| `bash.py` | Returns data dict | `FidelityToken.attach_manifest(result)` |
| `terraform.py` | Returns data dict | `FidelityToken.attach_manifest(result)` |
| `graphql.py` | Returns data dict | `FidelityToken.attach_manifest(result)` |
| `python.py` | Returns data dict | `FidelityToken.attach_manifest(result)` |
| `javascript.py` | Returns data dict | `FidelityToken.attach_manifest(result)` |

### Additional Issue

`sql.py` returns a proper data dict but doesn't use FidelityToken (partial compliance).

## What Changes

### Core Principle

**Extractors MUST NOT write to the database.** They produce data dictionaries. The Storage layer consumes those dictionaries and writes to the database. This separation enables:

1. Manifest generation (extractor reports what it found)
2. Receipt generation (storage reports what it wrote)
3. Fidelity reconciliation (compare manifest vs receipt)

### Refactored Extractors

Each violating extractor will be refactored to:

1. **Remove all `self.db_manager.*` calls**
2. **Build and return data dictionaries** with keys matching storage handler names
3. **Call `FidelityToken.attach_manifest(result)`** before returning

### New Storage Handlers

Add handlers to `InfrastructureStorage` for:

- Docker: `docker_images`, `dockerfile_ports`, `dockerfile_env_vars`
- GitHub Actions: `github_workflows`, `github_jobs`, `github_steps`, `github_step_outputs`, `github_step_references`, `github_job_dependencies`
- Prisma: `prisma_models`
- Compose: Already exists via `generic.py` but needs verification
- Nginx: Already exists via `generic.py` but needs verification
- Manifests (package.json/pyproject.toml/requirements.txt): `package_configs`, `package_dependencies`, `package_scripts`, etc.

### SQL Extractor Fix

Add `FidelityToken.attach_manifest()` call to `sql.py`.

## Impact

- **Affected specs**: NEW `extractor-fidelity` capability
- **Affected code**:
  - `theauditor/indexer/extractors/docker.py` (REWRITE)
  - `theauditor/indexer/extractors/github_actions.py` (REWRITE)
  - `theauditor/indexer/extractors/prisma.py` (REWRITE)
  - `theauditor/indexer/extractors/generic.py` (REWRITE)
  - `theauditor/indexer/extractors/manifest_extractor.py` (REWRITE)
  - `theauditor/indexer/extractors/sql.py` (ADD FidelityToken)
  - `theauditor/indexer/storage/infrastructure_storage.py` (ADD handlers)
  - `theauditor/indexer/storage/__init__.py` (WIRE handlers)

## Non-Goals

- NOT changing the FidelityToken API (it's working correctly)
- NOT refactoring compliant extractors (they're already correct)
- NOT adding new database tables (existing tables are sufficient)
- NOT changing the fidelity reconciliation logic
- NOT changing CLI interface

## Success Criteria

1. All 16 extractors use `FidelityToken.attach_manifest()` before returning
2. Zero extractors have `self.db_manager.*` calls (except inherited from BaseExtractor which has none)
3. `aud full --offline` completes with fidelity checks passing for ALL data types
4. Fidelity audit log shows non-zero counts for Docker/GHA/Prisma/etc. data

## Risk Assessment

**HIGH RISK** - This changes the data flow for infrastructure extraction.

### Mitigation

1. **Phase 1**: Add storage handlers FIRST (parallel path)
2. **Phase 2**: Refactor extractors one at a time
3. **Phase 3**: Verify fidelity counts after each refactor
4. **Rollback**: Git revert if fidelity starts failing unexpectedly
