# Spec: Extractor Fidelity

## Overview

All extractors in `theauditor/indexer/extractors/` MUST follow the Fidelity Protocol:

1. **Extract data** from files into structured dictionaries
2. **Return data dictionaries** - NEVER write to database directly
3. **Attach fidelity manifest** using `FidelityToken.attach_manifest()`
4. **Let Storage layer** handle database writes and receipt generation

---

## ADDED Requirements

### Requirement: No Direct Database Writes from Extractors

Extractors MUST NOT call any `self.db_manager.*` methods.

**Rationale**: Direct writes bypass the fidelity system. The storage layer must mediate all database access to generate receipts.

#### Scenario: Docker Extractor Compliance Check

**Given** the Docker extractor at `theauditor/indexer/extractors/docker.py`
**When** I search for `self.db_manager` calls
**Then** zero matches are found
**And** all data is returned via result dictionary

#### Scenario: GitHub Actions Extractor Compliance Check

**Given** the GitHub Actions extractor at `theauditor/indexer/extractors/github_actions.py`
**When** I search for `self.db_manager` calls
**Then** zero matches are found
**And** all data is returned via result dictionary

#### Scenario: Full Codebase Compliance Check

**Given** all extractors in `theauditor/indexer/extractors/`
**When** I run `grep -r "self.db_manager" theauditor/indexer/extractors/`
**Then** zero matches are returned

---

### Requirement: All Extractors Use FidelityToken

Every extractor's `extract()` method MUST call `FidelityToken.attach_manifest(result)` before returning.

**Rationale**: Manifests enable fidelity reconciliation. Without manifests, data integrity cannot be verified.

#### Scenario: Docker Extractor Manifest Generation

**Given** a Dockerfile at `test/Dockerfile`
**When** DockerExtractor.extract() processes the file
**Then** the result contains key `_extraction_manifest`
**And** the manifest contains entry for `docker_images` with count > 0

#### Scenario: GitHub Actions Manifest Generation

**Given** a workflow file at `.github/workflows/ci.yml`
**When** GitHubWorkflowExtractor.extract() processes the file
**Then** the result contains key `_extraction_manifest`
**And** the manifest contains entries for `github_workflows`, `github_jobs`, `github_steps`

#### Scenario: SQL Extractor Manifest Fix

**Given** the SQL extractor at `theauditor/indexer/extractors/sql.py`
**When** I check its extract() method
**Then** it calls `FidelityToken.attach_manifest(result)` before returning

---

### Requirement: Return Data Dictionaries

Extractors MUST return dictionaries with:
- Keys that match registered storage handler names
- Values that are lists of row dictionaries (for table data) or dicts (for K/V data)

**Rationale**: The DataStorer dispatches to handlers by key name. Mismatched keys result in data not being stored.

#### Scenario: Docker Data Structure

**Given** DockerExtractor processes a Dockerfile
**When** extract() returns
**Then** result contains keys: `docker_images`, `dockerfile_ports`, `dockerfile_env_vars`
**And** each value is a list of dictionaries

#### Scenario: GitHub Actions Data Structure

**Given** GitHubWorkflowExtractor processes a workflow file
**When** extract() returns
**Then** result contains keys: `github_workflows`, `github_jobs`, `github_steps`, `github_step_outputs`, `github_step_references`, `github_job_dependencies`
**And** each value is a list of dictionaries

---

### Requirement: Meaningful Empty Results

Extractors MUST return structure with empty lists when extraction finds nothing, not `{}`.

**Rationale**: Empty `{}` provides no schema information. Empty lists with manifest show "we checked and found 0 items" vs "we didn't check".

#### Scenario: Empty Dockerfile

**Given** an empty Dockerfile
**When** DockerExtractor.extract() processes it
**Then** result contains `docker_images: []`, `dockerfile_ports: []`, `dockerfile_env_vars: []`
**And** result contains `_extraction_manifest` with counts of 0

#### Scenario: Malformed YAML Workflow

**Given** a malformed workflow file that fails to parse
**When** GitHubWorkflowExtractor.extract() processes it
**Then** result contains empty lists for all data types
**And** result contains `_extraction_manifest` with counts of 0
**And** error is logged (not silently swallowed)

---

### Requirement: Storage Handlers for All Data Types

Every data type returned by extractors MUST have a registered storage handler in `DataStorer.handlers`.

**Rationale**: Unhandled keys are silently ignored, causing data loss.

#### Scenario: Docker Storage Handlers Registered

**Given** InfrastructureStorage is initialized
**When** I check self.handlers dict
**Then** it contains keys: `docker_images`, `dockerfile_ports`, `dockerfile_env_vars`
**And** each maps to a handler function

#### Scenario: GitHub Actions Storage Handlers Registered

**Given** InfrastructureStorage is initialized
**When** I check self.handlers dict
**Then** it contains keys: `github_workflows`, `github_jobs`, `github_steps`, `github_step_outputs`, `github_step_references`, `github_job_dependencies`
**And** each maps to a handler function

#### Scenario: Package Manifest Storage Handlers Registered

**Given** NodeStorage and PythonStorage are initialized
**When** I check their handlers dicts
**Then** NodeStorage contains: `package_configs`, `package_dependencies`, `package_scripts`, `package_engines`, `package_workspaces`
**And** PythonStorage contains: `python_package_configs`, `python_package_dependencies`, `python_build_requirements`

---

## Contract

### Extractor Interface

```python
from theauditor.indexer.fidelity_utils import FidelityToken

class SomeExtractor(BaseExtractor):
    def extract(self, file_info: dict, content: str, tree: Any | None = None) -> dict[str, Any]:
        """
        MUST return dict with:
        - Keys matching storage handler names
        - Values being lists of row dictionaries
        - _extraction_manifest key added by FidelityToken

        MUST NOT:
        - Call self.db_manager.* methods directly
        - Return empty dict {} when data exists
        - Catch exceptions silently
        """
        result = {
            "some_data_type": [
                {"col1": "value1", "col2": "value2"},
            ],
        }
        return FidelityToken.attach_manifest(result)
```

### FidelityToken API

```python
class FidelityToken:
    @staticmethod
    def attach_manifest(extracted_data: dict[str, Any]) -> dict[str, Any]:
        """Attaches _extraction_manifest to result dict."""
```

### Storage Handler Interface

```python
class SomeStorage(BaseStorage):
    def __init__(self, db_manager, counts):
        self.handlers = {
            "some_data_type": self.store_some_data_type,
        }

    def store_some_data_type(self, file_path: str, data: list[dict], jsx_pass: bool = False):
        for row in data:
            self.db_manager.add_some_data(**row)
        self.counts["some_data_type"] += len(data)
```

---

## Compliance Matrix

**Updated**: 2025-12-04 (All extractors now compliant)

| Extractor | REQ-001 | REQ-002 | REQ-003 | REQ-004 | REQ-005 |
|-----------|---------|---------|---------|---------|---------|
| go.py | PASS | PASS | PASS | PASS | PASS |
| rust.py | PASS | PASS | PASS | PASS | PASS |
| bash.py | PASS | PASS | PASS | PASS | PASS |
| terraform.py | PASS | PASS | PASS | PASS | PASS |
| graphql.py | PASS | PASS | PASS | PASS | PASS |
| python.py | PASS | PASS | PASS | PASS | PASS |
| javascript.py | PASS | PASS | PASS | PASS | PASS |
| sql.py | PASS | PASS | PASS | PASS | PASS |
| docker.py | PASS | PASS | PASS | PASS | PASS |
| github_actions.py | PASS | PASS | PASS | PASS | PASS |
| prisma.py | PASS | PASS | PASS | PASS | PASS |
| generic.py | PASS | PASS | PASS | PASS | PASS |
| manifest_extractor.py | PASS | PASS | PASS | PASS | PASS |

**Verification Evidence** (2025-12-04):
- `grep "self.db_manager" theauditor/indexer/extractors/` = 0 matches
- `grep "FidelityToken.attach_manifest"` = 18 matches (all extractors)
- `aud full --offline` = 22/22 phases PASS, 315.7s
- Database counts: GHA=115, package=137, nginx=1, python_pkg=42
