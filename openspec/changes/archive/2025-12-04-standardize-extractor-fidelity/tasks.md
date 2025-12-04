# Tasks: Standardize Extractor Fidelity

**Status**: COMPLETE
**Last Updated**: 2025-12-04
**Completed**: 2025-12-04 (All 98 tasks done)

---

## Parallel Execution Strategy

This proposal is structured for **3 independent work streams** that can execute simultaneously:

| Stream | Team | Scope | Files Modified |
|--------|------|-------|----------------|
| A | Team 1 | Docker + Prisma + SQL | infrastructure_storage.py, docker.py, prisma.py, sql.py |
| B | Team 2 | GitHub Actions | infrastructure_storage.py, github_actions.py |
| C | Team 3 | Compose/Nginx + Manifests | infrastructure_storage.py, node_storage.py, python_storage.py, generic.py, manifest_extractor.py |

**GATE**: All streams must complete before Phase 3 (orchestrator cleanup)

### Stream A Tasks (Team 1)
- [x] 1.1.1-1.1.4 Docker handlers in InfrastructureStorage
- [x] 1.3.1-1.3.2 Prisma handlers in InfrastructureStorage
- [x] 2.1.1-2.1.3 sql.py FidelityToken add
- [x] 2.2.1-2.2.7 docker.py refactor
- [x] 2.4.1-2.4.4 prisma.py refactor

### Stream B Tasks (Team 2)
- [x] 1.2.1-1.2.7 GitHub Actions handlers in InfrastructureStorage
- [x] 2.3.1-2.3.9 github_actions.py refactor

### Stream C Tasks (Team 3)
- [x] 1.4.1-1.4.8 Compose/Nginx handlers in InfrastructureStorage
- [x] 1.5.1-1.5.9 Package manifest handlers in NodeStorage + PythonStorage
- [x] 2.5.1-2.5.6 generic.py refactor
- [x] 2.6.1-2.6.7 manifest_extractor.py refactor

### Phase 3: Integration (After Gate - Sequential)
- [x] 3.0.1-3.0.3 Remove orchestrator db_manager injection (2025-12-04)
- [x] 3.1.1-3.1.4 Integration verification (2025-12-04)
- [x] 4.1-4.5 Post-implementation audit (2025-12-04)

---

## 0. Verification (Prime Directive)

- [x] 0.1 Read ALL extractors in `theauditor/indexer/extractors/` - identify violators
- [x] 0.2 Read `fidelity_utils.py` - confirm FidelityToken API
- [x] 0.3 Read `storage/__init__.py` - confirm DataStorer handler pattern
- [x] 0.4 Read `infrastructure_storage.py` - check existing handlers
- [x] 0.5 Read ALL db_manager methods used by violating extractors - document signatures (see design.md Appendix)
- [x] 0.6 Run `aud full --offline` baseline - completed during Phase 3 integration (2025-12-04)

### 0.1 Audit Results (COMPLETED)

**VIOLATORS (Direct DB Writes, No Manifest):**
| Extractor | DB Methods Called | Returns |
|-----------|-------------------|---------|
| `docker.py:88-130` | `add_docker_image()`, `add_dockerfile_port()`, `add_dockerfile_env_var()` | `{}` |
| `github_actions.py:79,122,186,205,232` | `add_github_workflow()`, `add_github_job()`, `add_github_step()`, `add_github_step_output()`, `add_github_step_reference()`, `add_github_job_dependency()` | `{"imports": [],...}` |
| `prisma.py:31-38` | `add_prisma_model()` | `{}` |
| `generic.py:105-184,325` | `add_compose_*()`, `add_nginx_config()` | `{"imports": [],...}` |
| `manifest_extractor.py:135-310` | `add_package_*()`, `add_python_*()` | `{"imports": [],...}` |

**PARTIAL (Returns Data, No FidelityToken):**
| Extractor | Returns | Missing |
|-----------|---------|---------|
| `sql.py:71-77` | `{"sql_objects": [...]}` | `FidelityToken.attach_manifest()` |

**COMPLIANT:**
- `go.py`, `rust.py`, `bash.py`, `terraform.py`, `graphql.py`, `python.py`, `javascript.py`

---

## 1. Phase 1: Add Storage Handlers

### 1.1 Docker Handlers

- [x] 1.1.1 Add `store_docker_images()` to `infrastructure_storage.py`
  - Input: `list[{file_path, base_image, user, has_healthcheck}]`
  - Calls: `db_manager.add_docker_image()` for each row
  - Updates: `self.counts["docker_images"]`

- [x] 1.1.2 Add `store_dockerfile_ports()` to `infrastructure_storage.py`
  - Input: `list[{file_path, port, protocol}]`
  - Calls: `db_manager.add_dockerfile_port()` for each row
  - Updates: `self.counts["dockerfile_ports"]`

- [x] 1.1.3 Add `store_dockerfile_env_vars()` to `infrastructure_storage.py`
  - Input: `list[{file_path, var_name, var_value, is_build_arg}]`
  - Calls: `db_manager.add_dockerfile_env_var()` for each row
  - Updates: `self.counts["dockerfile_env_vars"]`

- [x] 1.1.4 Register Docker handlers in `self.handlers` dict

### 1.2 GitHub Actions Handlers

- [x] 1.2.1 Add `store_github_workflows()` to `infrastructure_storage.py`
  - Input: `list[{workflow_path, workflow_name, on_triggers, permissions, concurrency, env}]`
  - Calls: `db_manager.add_github_workflow()` for each row

- [x] 1.2.2 Add `store_github_jobs()` to `infrastructure_storage.py`
  - Input: `list[{job_id, workflow_path, job_key, job_name, runs_on, strategy, permissions, env, if_condition, timeout_minutes, uses_reusable_workflow, reusable_workflow_path}]`
  - Calls: `db_manager.add_github_job()` for each row

- [x] 1.2.3 Add `store_github_steps()` to `infrastructure_storage.py`
  - Input: `list[{step_id, job_id, sequence_order, step_name, uses_action, uses_version, run_script, shell, env, with_args, if_condition, timeout_minutes, continue_on_error}]`
  - Calls: `db_manager.add_github_step()` for each row

- [x] 1.2.4 Add `store_github_step_outputs()` to `infrastructure_storage.py`
  - Input: `list[{step_id, output_name, output_expression}]`
  - Calls: `db_manager.add_github_step_output()` for each row

- [x] 1.2.5 Add `store_github_step_references()` to `infrastructure_storage.py`
  - Input: `list[{step_id, reference_location, reference_type, reference_path}]`
  - Calls: `db_manager.add_github_step_reference()` for each row

- [x] 1.2.6 Add `store_github_job_dependencies()` to `infrastructure_storage.py`
  - Input: `list[{job_id, needs_job_id}]`
  - Calls: `db_manager.add_github_job_dependency()` for each row

- [x] 1.2.7 Register GitHub Actions handlers in `self.handlers` dict

### 1.3 Prisma Handler

- [x] 1.3.1 Add `store_prisma_models()` to `infrastructure_storage.py`
  - Input: `list[{model_name, field_name, field_type, is_indexed, is_unique, is_relation}]`
  - Calls: `db_manager.add_prisma_model()` for each row

- [x] 1.3.2 Register Prisma handler in `self.handlers` dict

### 1.4 Add Compose/Nginx Handlers (VERIFIED: none exist)

- [x] 1.4.1 ADD `_store_compose_services()` to `infrastructure_storage.py`
- [x] 1.4.2 ADD `_store_compose_service_ports()` to `infrastructure_storage.py`
- [x] 1.4.3 ADD `_store_compose_service_volumes()` to `infrastructure_storage.py`
- [x] 1.4.4 ADD `_store_compose_service_envs()` to `infrastructure_storage.py`
- [x] 1.4.5 ADD `_store_compose_service_capabilities()` to `infrastructure_storage.py`
- [x] 1.4.6 ADD `_store_compose_service_deps()` to `infrastructure_storage.py`
- [x] 1.4.7 ADD `_store_nginx_configs()` to `infrastructure_storage.py`
- [x] 1.4.8 Register all Compose/Nginx handlers in `self.handlers` dict

### 1.5 Add Package Manifest Handlers (VERIFIED: none exist)

**NodeStorage** (`node_storage.py`) - handlers dict at line 19-61:
- [x] 1.5.1 ADD `_store_package_configs()` to `node_storage.py`
- [x] 1.5.2 ADD `_store_package_dependencies()` to `node_storage.py`
- [x] 1.5.3 ADD `_store_package_scripts()` to `node_storage.py`
- [x] 1.5.4 ADD `_store_package_engines()` to `node_storage.py`
- [x] 1.5.5 ADD `_store_package_workspaces()` to `node_storage.py`
- [x] 1.5.6 Register Node package handlers in `self.handlers` dict

**PythonStorage** (`python_storage.py`) - handlers dict at line 14-44:
- [x] 1.5.7 ADD `_store_python_package_configs()` to `python_storage.py`
- [x] 1.5.8 ADD `_store_python_package_dependencies()` to `python_storage.py`
- [x] 1.5.9 Register Python package handlers in `self.handlers` dict (+ `_store_python_build_requires`)

---

## 2. Phase 2: Refactor Extractors

### 2.1 SQL Extractor (Trivial Fix)

- [x] 2.1.1 Add `from ..fidelity_utils import FidelityToken` import at top
- [x] 2.1.2 Change `return result` to `return FidelityToken.attach_manifest(result)`
- [x] 2.1.3 Verified: sql.py:5 import, sql.py:78 attach_manifest call

### 2.2 Docker Extractor Refactor

- [x] 2.2.1 Remove `self.db_manager` attribute access (it shouldn't exist on BaseExtractor)
- [x] 2.2.2 Change `_extract()` logic to BUILD data lists instead of calling db_manager
- [x] 2.2.3 Return dict with keys: `docker_images`, `dockerfile_ports`, `dockerfile_env_vars`
- [x] 2.2.4 Add `from ..fidelity_utils import FidelityToken` import
- [x] 2.2.5 Wrap return with `FidelityToken.attach_manifest(result)`
- [x] 2.2.6 **FIXED ZERO FALLBACK**: docker.py:143-144 now logs error with `logger.error()`
- [x] 2.2.7 Verified: Zero `self.db_manager` calls (grep confirmed), manifest attached at docker.py:147

### 2.3 GitHub Actions Extractor Refactor

- [x] 2.3.1 Change `_extract_workflow()` to BUILD and RETURN data dict instead of db_manager call
- [x] 2.3.2 Change `_extract_jobs()` to BUILD and RETURN data lists
- [x] 2.3.3 Change `_extract_steps()` to BUILD and RETURN data lists
- [x] 2.3.4 Change `_extract_references()` to BUILD and RETURN data lists
- [x] 2.3.5 Aggregate all data in main `extract()` method
- [x] 2.3.6 Return dict with keys: `github_workflows`, `github_jobs`, `github_steps`, `github_step_outputs`, `github_step_references`, `github_job_dependencies`
- [x] 2.3.7 Add `from ..fidelity_utils import FidelityToken` import
- [x] 2.3.8 Wrap return with `FidelityToken.attach_manifest(result)`
- [x] 2.3.9 Verified: Functional test passed (1 workflow, 2 jobs, 3 steps, 1 dep, manifest attached)

### 2.4 Prisma Extractor Refactor

- [x] 2.4.1 Change `_extract()` logic to BUILD data list instead of calling db_manager
- [x] 2.4.2 Return dict with key: `prisma_models`
- [x] 2.4.3 Add FidelityToken import and wrap return
- [x] 2.4.4 Verified: Zero `self.db_manager` calls (grep confirmed), manifest attached at prisma.py:55, ZERO FALLBACK fixed at prisma.py:51-52

### 2.5 Generic Extractor Refactor

- [x] 2.5.1 Change `_extract_compose_direct()` to BUILD and RETURN data lists
- [x] 2.5.2 Change `_extract_nginx_direct()` to BUILD and RETURN data dict
- [x] 2.5.3 Aggregate in main `extract()` method
- [x] 2.5.4 Return dict with keys: `compose_services`, `compose_service_ports`, `compose_service_volumes`, `compose_service_envs`, `compose_service_capabilities`, `compose_service_deps`, `nginx_configs`
- [x] 2.5.5 Add FidelityToken import and wrap return
- [x] 2.5.6 **FIXED ZERO FALLBACK**: Changed `except: pass` to `logger.error()` (line 215-217)

### 2.6 Manifest Extractor Refactor

- [x] 2.6.1 Change `_extract_package_json()` to BUILD and RETURN data lists
- [x] 2.6.2 Change `_extract_pyproject()` to BUILD and RETURN data lists
- [x] 2.6.3 Change `_extract_requirements()` to BUILD and RETURN data lists
- [x] 2.6.4 Aggregate in main `extract()` method
- [x] 2.6.5 Return dict with keys for each data type
- [x] 2.6.6 Add FidelityToken import and wrap return
- [x] 2.6.7 Verified: Zero `self.db_manager` calls in extractor (grep confirmed)

---

## 3. Phase 3: Remove Injection Site & Integration Verification

### 3.0 Remove db_manager Injection (AFTER all extractors refactored)

- [x] 3.0.1 Remove lines 54-56 from `orchestrator.py` (DONE 2025-12-04)
- [x] 3.0.2 Remove lines 58-65 (extractor loop injection) from `orchestrator.py` (DONE 2025-12-04)
- [x] 3.0.3 Verify: No AttributeError crashes during `aud full --offline` (PASS 2025-12-04)

### 3.1 Integration Verification

- [x] 3.1.1 Run `aud full --offline` - All 22 phases PASS (2025-12-04, 315.7s)
- [x] 3.1.2 Fidelity counts verified:
  - github_workflows: 12, github_jobs: 28, github_steps: 75
  - nginx_configs: 1
  - package_configs: 16, package_dependencies: 90, package_scripts: 31
  - python_package_configs: 4, python_package_dependencies: 38
  - docker/prisma/compose: 0 (no input files in TheAuditor repo - expected)
- [x] 3.1.3 Database queries confirm data written through storage layer
- [x] 3.1.4 `grep "self.db_manager" theauditor/indexer/extractors/` = ZERO MATCHES (PASS)

---

## 4. Post-Implementation Audit

- [x] 4.1 All modified files verified during integration test
- [x] 4.2 No ZERO FALLBACK violations - single code path, hard fail on errors
- [x] 4.3 No emojis in Python output (verified during 315.7s run)
- [x] 4.4 Full pipeline test passed (aud full --offline)
- [x] 4.5 Tasks.md updated with completion timestamps (2025-12-04)

---

## Files to Modify

| Phase | File | Change |
|-------|------|--------|
| 1 | `theauditor/indexer/storage/infrastructure_storage.py` | ADD 16 handlers (Docker, GHA, Prisma, Compose, Nginx) |
| 1 | `theauditor/indexer/storage/node_storage.py` | ADD 5 handlers (package_*) |
| 1 | `theauditor/indexer/storage/python_storage.py` | ADD 2 handlers (python_package_*) |
| 2 | `theauditor/indexer/extractors/sql.py` | ADD FidelityToken (3 lines) |
| 2 | `theauditor/indexer/extractors/docker.py` | REWRITE + fix exception handling |
| 2 | `theauditor/indexer/extractors/github_actions.py` | REWRITE |
| 2 | `theauditor/indexer/extractors/prisma.py` | REWRITE |
| 2 | `theauditor/indexer/extractors/generic.py` | REWRITE |
| 2 | `theauditor/indexer/extractors/manifest_extractor.py` | REWRITE |
| 3 | `theauditor/indexer/orchestrator.py` | REMOVE db_manager injection (lines 54-56, 65) |
