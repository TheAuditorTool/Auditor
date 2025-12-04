# Design: Standardize Extractor Fidelity

## Architecture Overview

```
                    CURRENT (Shadow IT)
                    ===================

    Extractor ─────────────────────────────> Database
         │                                      │
         │  (bypasses everything)               │
         │                                      │
         └──> returns {} ──> Storage ──> (nothing to process)
                                │
                                v
                          Fidelity Check: 0 vs 0 = PASS (WRONG!)


                    CORRECT (After Fix)
                    ===================

    Extractor ─────> returns {data} + manifest ─────> Storage
                           │                            │
                           │                            v
                           │                     writes to DB
                           │                            │
                           v                            v
                    Manifest: {count: 50}         Receipt: {count: 50}
                                    │                 │
                                    └────> Fidelity ─┘
                                           Check: 50 vs 50 = PASS (CORRECT!)
```

## Decision Log

### Decision 1: Extractor Return Value Structure

**Question**: What should refactored extractors return?

**Answer**: A dictionary with keys matching storage handler names, plus FidelityToken manifest.

```python
# docker.py AFTER refactor
def extract(self, file_info, content, tree=None) -> dict[str, Any]:
    result = {
        "docker_images": [
            {"file_path": "...", "base_image": "...", "user": "...", "has_healthcheck": False},
        ],
        "dockerfile_ports": [
            {"file_path": "...", "port": 8080, "protocol": "tcp"},
        ],
        "dockerfile_env_vars": [
            {"file_path": "...", "var_name": "NODE_ENV", "var_value": "production", "is_build_arg": False},
        ],
    }
    return FidelityToken.attach_manifest(result)
```

**Rationale**: This matches the established pattern in compliant extractors (go.py, rust.py, etc.).

### Decision 2: Storage Handler Registration

**Question**: Where do new handlers go?

**Answer**: `InfrastructureStorage` for Docker/GHA/Prisma/Compose/Nginx. `NodeStorage` for package.json. `PythonStorage` for pyproject.toml/requirements.txt.

**File**: `theauditor/indexer/storage/infrastructure_storage.py`
**Insertion Point**: Lines 16-31 (inside `self.handlers = {` dict)

**VERIFIED Current State** (lines 16-31):
```python
# EXISTING handlers (Terraform + GraphQL only):
self.handlers = {
    "terraform_file": self._store_terraform_file,
    "terraform_resources": self._store_terraform_resources,
    "terraform_variables": self._store_terraform_variables,
    # ... more terraform ...
    "graphql_schemas": self._store_graphql_schemas,
    "graphql_types": self._store_graphql_types,
    # ... more graphql ...
}
# NO Docker, GitHub Actions, Prisma, Compose, or Nginx handlers exist!
```

**After Fix** - Add these handlers to the dict:
```python
self.handlers = {
    # ... existing terraform/graphql handlers ...
    # NEW - Docker (add after graphql_resolver_params)
    "docker_images": self._store_docker_images,
    "dockerfile_ports": self._store_dockerfile_ports,
    "dockerfile_env_vars": self._store_dockerfile_env_vars,
    # NEW - GitHub Actions
    "github_workflows": self._store_github_workflows,
    "github_jobs": self._store_github_jobs,
    "github_steps": self._store_github_steps,
    "github_step_outputs": self._store_github_step_outputs,
    "github_step_references": self._store_github_step_references,
    "github_job_dependencies": self._store_github_job_dependencies,
    # NEW - Prisma
    "prisma_models": self._store_prisma_models,
    # NEW - Compose/Nginx
    "compose_services": self._store_compose_services,
    "compose_service_ports": self._store_compose_service_ports,
    "compose_service_volumes": self._store_compose_service_volumes,
    "compose_service_envs": self._store_compose_service_envs,
    "nginx_configs": self._store_nginx_configs,
}
```

### Decision 3: DB Manager Method Reuse

**Question**: Do we reuse existing `db_manager.add_*` methods?

**Answer**: YES. The db_manager methods are correct. The problem is extractors calling them directly instead of going through storage.

```python
# infrastructure_storage.py
def store_docker_images(self, file_path: str, data: list[dict], jsx_pass: bool = False):
    for row in data:
        self.db_manager.add_docker_image(
            file_path=row["file_path"],
            base_image=row.get("base_image"),
            user=row.get("user"),
            has_healthcheck=row.get("has_healthcheck", False),
        )
    self.counts["docker_images"] = self.counts.get("docker_images", 0) + len(data)
```

### Decision 4: Manifest Extractor Split Strategy

**Question**: How to handle manifest_extractor.py which covers 3 ecosystems?

**Answer**: Keep it unified but return separate keys for each ecosystem. Storage handlers are already split by domain.

```python
# manifest_extractor.py returns:
{
    # Node.js keys -> NodeStorage handlers
    "package_configs": [...],
    "package_dependencies": [...],
    "package_scripts": [...],
    "package_engines": [...],
    "package_workspaces": [...],

    # Python keys -> PythonStorage handlers
    "python_package_configs": [...],
    "python_package_dependencies": [...],
    "python_build_requirements": [...],
}
```

### Decision 5: Generic Extractor Compose/Nginx Handling

**Question**: Does generic.py already have storage handlers?

**Answer**: **VERIFIED - NO HANDLERS EXIST.** I checked `infrastructure_storage.py:16-31` - only Terraform and GraphQL handlers are registered. Compose and Nginx handlers must be added.

**Required handlers to ADD:**
- `compose_services` -> `_store_compose_services()`
- `compose_service_ports` -> `_store_compose_service_ports()`
- `compose_service_volumes` -> `_store_compose_service_volumes()`
- `compose_service_envs` -> `_store_compose_service_envs()`
- `compose_service_capabilities` -> `_store_compose_service_capabilities()`
- `compose_service_deps` -> `_store_compose_service_deps()`
- `nginx_configs` -> `_store_nginx_configs()`

### Decision 6: GitHub Actions Data Structure

**Question**: What's the exact structure for GHA data?

**Answer**: Match existing db_manager method signatures:

```python
# github_workflows
{"workflow_path": "...", "workflow_name": "...", "on_triggers": "[json]", "permissions": "[json]", "concurrency": "[json]", "env": "[json]"}

# github_jobs
{"job_id": "...", "workflow_path": "...", "job_key": "...", "job_name": "...", "runs_on": "[json]", "strategy": "[json]", "permissions": "[json]", "env": "[json]", "if_condition": "...", "timeout_minutes": int, "uses_reusable_workflow": bool, "reusable_workflow_path": "..."}

# github_steps
{"step_id": "...", "job_id": "...", "sequence_order": int, "step_name": "...", "uses_action": "...", "uses_version": "...", "run_script": "...", "shell": "...", "env": "[json]", "with_args": "[json]", "if_condition": "...", "timeout_minutes": int, "continue_on_error": bool}

# github_step_outputs
{"step_id": "...", "output_name": "...", "output_expression": "..."}

# github_step_references
{"step_id": "...", "reference_location": "...", "reference_type": "...", "reference_path": "..."}

# github_job_dependencies
{"job_id": "...", "needs_job_id": "..."}
```

### Decision 7: Error Handling

**Question**: What happens if extraction fails?

**Answer**: Return empty lists for that category. ZERO FALLBACK - no silent catches that hide failures.

```python
# CORRECT
def extract(self, file_info, content, tree=None):
    result = {"docker_images": [], "dockerfile_ports": [], "dockerfile_env_vars": []}

    try:
        # Parse and populate result
    except SomeSpecificError as e:
        logger.error(f"Failed to parse {file_info['path']}: {e}")
        # Return empty result - manifest will show count: 0
        return FidelityToken.attach_manifest(result)

    return FidelityToken.attach_manifest(result)
```

### Decision 8: SQL Extractor Minimal Fix

**Question**: How much to change in sql.py?

**Answer**: Minimal - just add FidelityToken import and call.

```python
# sql.py - BEFORE (line 77)
return result

# sql.py - AFTER
from ..fidelity_utils import FidelityToken

# ... at end of extract():
return FidelityToken.attach_manifest(result)
```

### Decision 9: Remove db_manager Injection Site

**Question**: Where is db_manager injected into extractors?

**Answer**: `theauditor/indexer/orchestrator.py:54-56`

**Current code to REMOVE:**
```python
# orchestrator.py lines 54-56
self.docker_extractor.db_manager = self.db_manager
self.generic_extractor.db_manager = self.db_manager
self.github_workflow_extractor.db_manager = self.db_manager
```

And also line 65 in the extractor loop:
```python
# orchestrator.py line 65
ext.db_manager = self.db_manager
```

**Why this exists**: Legacy pattern where extractors were given direct database access.
**Why remove**: After refactor, extractors return data dicts. Storage layer handles DB writes. Extractors no longer need db_manager.

**Note**: `BaseExtractor` in `extractors/__init__.py` does NOT have a db_manager attribute - it's dynamically injected by the orchestrator. After removing these lines, any extractor that tries to access `self.db_manager` will raise `AttributeError` (good - exposes unfixed extractors).

### Decision 10: Logging Standards

**Question**: What logging pattern must extractors use?

**Answer**: All extractors MUST use the centralized logger from `theauditor.utils.logging`.

```python
# CORRECT - Use this pattern
from theauditor.utils.logging import logger

logger.error(f"Failed to parse {file_path}: {e}")
logger.debug(f"Extracted {len(items)} items from {file_path}")
logger.warning(f"Skipping malformed entry in {file_path}")
```

**BANNED patterns:**
```python
# WRONG - Do NOT use these
import logging  # Wrong module
logger = logging.getLogger(__name__)  # Wrong pattern

print(f"Error: {e}")  # Never use print for errors

logger.info("Status: OK")  # No emojis - Windows CP1252 crash
```

**Why centralized logging matters:**
- Unified format across all extractors
- Pino-compatible JSON mode for structured logging
- Rich Live integration (logs appear above progress table)
- No emoji crashes on Windows Command Prompt

### Decision 11: Storage Handler Pattern

**Question**: How do storage handlers inherit and register?

**Answer**: Storage handlers inherit from domain-specific classes that follow `BaseStorage` pattern.

**File**: `theauditor/indexer/storage/base.py`

```python
class BaseStorage:
    """Base class for domain-specific storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        self.db_manager = db_manager
        self.counts = counts
        self.handlers: dict[str, Callable] = {}  # Subclasses populate this
        self._current_extracted: dict = {}  # Set by DataStorer for each file

    def begin_file_processing(self):
        """Reset per-file state. Override if handler needs file-scoped caches."""
        pass
```

**Handler Registration Pattern** (in domain storage classes):

```python
# infrastructure_storage.py
class InfrastructureStorage(BaseStorage):
    def __init__(self, db_manager, counts):
        super().__init__(db_manager, counts)

        # Register handlers - key matches extractor output key
        self.handlers = {
            "docker_images": self.store_docker_images,
            "dockerfile_ports": self.store_dockerfile_ports,
            "dockerfile_env_vars": self.store_dockerfile_env_vars,
            # ... more handlers
        }

    def store_docker_images(self, file_path: str, data: list[dict], jsx_pass: bool):
        """Store docker image records."""
        for item in data:
            self.db_manager.add_docker_image(
                file_path=file_path,
                base_image=item.get("base_image"),
                user=item.get("user"),
                has_healthcheck=item.get("has_healthcheck", False),
            )
        self.counts["docker_images"] = self.counts.get("docker_images", 0) + len(data)
```

**DataStorer aggregates all domain handlers** (`storage/__init__.py:64-72`):
```python
self.handlers = {
    **self.core.handlers,
    **self.python.handlers,
    **self.node.handlers,
    **self.infrastructure.handlers,
    **self.rust.handlers,
    **self.go.handlers,
    **self.bash.handlers,
}
```

---

## Data Flow Diagrams

### Docker Extraction (After Fix)

```
Dockerfile ──> DockerExtractor.extract()
                     │
                     v
              Parse with dockerfile_parse
                     │
                     v
              Build data dicts:
              - docker_images: [{...}]
              - dockerfile_ports: [{...}]
              - dockerfile_env_vars: [{...}]
                     │
                     v
              FidelityToken.attach_manifest(result)
                     │
                     v
              Return result with _extraction_manifest
                     │
                     v
              DataStorer.store()
                     │
                     v
              InfrastructureStorage.store_docker_images()
              InfrastructureStorage.store_dockerfile_ports()
              InfrastructureStorage.store_dockerfile_env_vars()
                     │
                     v
              db_manager.add_docker_image() etc.
                     │
                     v
              FidelityToken.create_receipt() for each
                     │
                     v
              Fidelity Reconciliation: manifest vs receipt
```

### GitHub Actions Extraction (After Fix)

```
.github/workflows/*.yml ──> GitHubWorkflowExtractor.extract()
                                    │
                                    v
                             yaml.safe_load()
                                    │
                                    v
                             Build data dicts:
                             - github_workflows: [{...}]
                             - github_jobs: [{...}]
                             - github_steps: [{...}]
                             - github_step_outputs: [{...}]
                             - github_step_references: [{...}]
                             - github_job_dependencies: [{...}]
                                    │
                                    v
                             FidelityToken.attach_manifest(result)
                                    │
                                    v
                             Return to DataStorer
                                    │
                                    v
                             InfrastructureStorage handlers
                                    │
                                    v
                             db_manager.add_github_*()
                                    │
                                    v
                             Fidelity Reconciliation
```

## Implementation Order

1. **Phase 1: Storage Handlers** (safe, additive)
   - Add handlers to InfrastructureStorage for all missing data types
   - Wire them in `storage/__init__.py`
   - This creates parallel path - extractors can start using it

2. **Phase 2: Refactor Extractors** (one at a time)
   - sql.py (trivial - just add FidelityToken)
   - docker.py
   - github_actions.py
   - prisma.py
   - generic.py
   - manifest_extractor.py

3. **Phase 3: Verification**
   - Run `aud full --offline` after each refactor
   - Check fidelity audit log for non-zero counts
   - Verify database contains expected data

## File Changes Summary

| File | Change Type | LOC Estimate |
|------|-------------|--------------|
| `infrastructure_storage.py` | ADD handlers | +200 |
| `storage/__init__.py` | WIRE handlers | +5 |
| `docker.py` | REWRITE | ~135 (no change in size) |
| `github_actions.py` | REWRITE | ~238 (no change in size) |
| `prisma.py` | REWRITE | ~145 (no change in size) |
| `generic.py` | REWRITE | ~332 (no change in size) |
| `manifest_extractor.py` | REWRITE | ~311 (no change in size) |
| `sql.py` | ADD FidelityToken | +3 |
| `orchestrator.py` | REMOVE db_manager injection | -4 |

---

## Appendix: db_manager Method Signatures

These are the EXACT method signatures from the database mixins. Storage handlers must call these.

### Docker Methods (`infrastructure_database.py`)

```python
# Line 12-20
def add_docker_image(
    self,
    file_path: str,
    base_image: str | None,
    user: str | None,
    has_healthcheck: bool,
)

# Line 371-378
def add_dockerfile_port(
    self,
    file_path: str,
    port: str,
    protocol: str = "tcp",
)

# Line 380-388
def add_dockerfile_env_var(
    self,
    file_path: str,
    var_name: str,
    var_value: str | None,
    is_build_arg: bool = False,
)
```

### GitHub Actions Methods (`infrastructure_database.py`)

```python
# Line 271-279
def add_github_workflow(
    self,
    workflow_path: str,
    workflow_name: str | None,
    on_triggers: str,
    permissions: str | None = None,
    concurrency: str | None = None,
    env: str | None = None,
)

# Line 285-315 (truncated - see full in file)
def add_github_job(
    self,
    job_id: str,
    workflow_path: str,
    job_key: str,
    job_name: str | None,
    runs_on: str | None,
    strategy: str | None = None,
    permissions: str | None = None,
    env: str | None = None,
    if_condition: str | None = None,
    timeout_minutes: int | None = None,
    uses_reusable_workflow: bool = False,
    reusable_workflow_path: str | None = None,
)

# Line 318-320
def add_github_job_dependency(self, job_id: str, needs_job_id: str)

# Line 322-354 (truncated - see full in file)
def add_github_step(
    self,
    step_id: str,
    job_id: str,
    sequence_order: int,
    step_name: str | None,
    uses_action: str | None,
    uses_version: str | None,
    run_script: str | None,
    shell: str | None,
    env: str | None,
    with_args: str | None = None,
    if_condition: str | None = None,
    timeout_minutes: int | None = None,
    continue_on_error: bool = False,
)

# Line 357-361
def add_github_step_output(self, step_id: str, output_name: str, output_expression: str)

# Line 363-369
def add_github_step_reference(
    self, step_id: str, reference_location: str, reference_type: str, reference_path: str
)
```

### Compose/Nginx Methods (`infrastructure_database.py`)

```python
# Line 22-56
def add_compose_service(
    self,
    file_path: str,
    service_name: str,
    image: str | None,
    is_privileged: bool,
    network_mode: str,
    user: str | None = None,
    security_opt: list[str] | None = None,
    restart: str | None = None,
    command: list[str] | None = None,
    entrypoint: list[str] | None = None,
    healthcheck: dict | None = None,
)

# Line 58-68
def add_nginx_config(
    self, file_path: str, block_type: str, block_context: str, directives: dict, level: int
)
```

### Prisma Methods (`frameworks_database.py`)

```python
# Line 71-79
def add_prisma_model(
    self,
    model_name: str,
    field_name: str,
    field_type: str,
    is_indexed: bool,
    is_unique: bool,
    is_relation: bool,
)
```

### Node.js Package Methods (`node_database.py`)

```python
# Line 405-413
def add_package_config(
    self,
    file_path: str,
    package_name: str,
    version: str,
    is_private: bool = False,
)

# Line 686-694
def add_package_dependency(
    self,
    file_path: str,
    name: str,
    version_spec: str | None,
    is_dev: bool = False,
    is_peer: bool = False,
)

# Line 699-706
def add_package_script(
    self,
    file_path: str,
    script_name: str,
    script_command: str,
)

# Line 708-715
def add_package_engine(
    self,
    file_path: str,
    engine_name: str,
    version_spec: str | None,
)

# Line 717-723
def add_package_workspace(
    self,
    file_path: str,
    workspace_path: str,
)
```

### Python Package Methods (`python_database.py`)

```python
# Line 89-97
def add_python_package_config(
    self,
    file_path: str,
    file_type: str,
    project_name: str | None,
    project_version: str | None,
)

# Line 106-114
def add_python_package_dependency(
    self,
    file_path: str,
    name: str,
    version_spec: str | None,
    is_dev: bool = False,
    group_name: str | None = None,
    extras: str | None = None,
    git_url: str | None = None,
)
```
