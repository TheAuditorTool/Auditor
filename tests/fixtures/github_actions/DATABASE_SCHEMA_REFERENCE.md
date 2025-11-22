# GitHub Actions Database Schema Quick Reference

For rule writers - this is what you have to query.

## Tables Overview

```
github_workflows           # 1 row per workflow file
github_jobs                # 1 row per job
github_job_dependencies    # M:N junction table for needs: relationships
github_steps               # 1 row per step
github_step_outputs        # 1 row per output declaration
github_step_references     # 1 row per ${{ }} expression
```

## github_workflows

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| workflow_path | TEXT PK | Path to workflow file | `.github/workflows/ci.yml` |
| workflow_name | TEXT | Name from YAML or filename | `"Test CI"` |
| on_triggers | TEXT JSON | Array of trigger events | `["push", "pull_request_target"]` |
| permissions | TEXT JSON | Workflow-level permissions | `{"contents": "write"}` |
| concurrency | TEXT JSON | Concurrency settings | `{"group": "deploy"}` |
| env | TEXT JSON | Workflow-level env vars | `{"NODE_VERSION": "20"}` |

**Query Example:**
```python
cursor.execute("""
    SELECT workflow_path, on_triggers
    FROM github_workflows
    WHERE on_triggers LIKE '%pull_request_target%'
""")
```

## github_jobs

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| job_id | TEXT PK | Composite: workflow_path::job_key | `.github/workflows/ci.yml::build` |
| workflow_path | TEXT FK | Parent workflow | `.github/workflows/ci.yml` |
| job_key | TEXT | Job key from YAML | `"build"` |
| job_name | TEXT | Optional display name | `"Build Application"` |
| runs_on | TEXT JSON | Runner labels | `["ubuntu-latest"]` |
| strategy | TEXT JSON | Matrix strategy | `{"matrix": {"node": [18, 20]}}` |
| permissions | TEXT JSON | Job-level permissions | `{"contents": "read"}` |
| env | TEXT JSON | Job-level env vars | `{"CI": "true"}` |
| if_condition | TEXT | Conditional expression | `"github.event_name == 'push'"` |
| timeout_minutes | INTEGER | Job timeout | `30` |
| uses_reusable_workflow | BOOLEAN | Is reusable workflow call | `1` |
| reusable_workflow_path | TEXT | Path to reusable workflow | `"org/repo/.github/workflows/deploy.yml@main"` |

**Query Example:**
```python
cursor.execute("""
    SELECT job_id, permissions
    FROM github_jobs
    WHERE workflow_path IN (
        SELECT workflow_path FROM github_workflows
        WHERE on_triggers LIKE '%pull_request_target%'
    )
    AND permissions LIKE '%write%'
""")
```

## github_job_dependencies

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| job_id | TEXT PK | Dependent job | `.github/workflows/ci.yml::deploy` |
| needs_job_id | TEXT PK | Dependency job | `.github/workflows/ci.yml::build` |

**Query Example (find jobs that depend on untrusted jobs):**
```python
cursor.execute("""
    SELECT DISTINCT d.job_id
    FROM github_job_dependencies d
    JOIN github_steps s ON d.needs_job_id = s.job_id
    WHERE s.run_script LIKE '%github.event.pull_request%'
""")
```

## github_steps

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| step_id | TEXT PK | Composite: job_id::sequence_order | `.github/workflows/ci.yml::build::0` |
| job_id | TEXT FK | Parent job | `.github/workflows/ci.yml::build` |
| sequence_order | INTEGER | 0-indexed step order | `0` |
| step_name | TEXT | Optional display name | `"Checkout code"` |
| uses_action | TEXT | Action reference (no version) | `"actions/checkout"` |
| uses_version | TEXT | Version/ref/SHA | `"v4"` or `"main"` or `"8ade135..."` |
| run_script | TEXT | Shell script content | `"npm install && npm test"` |
| shell | TEXT | Shell type | `"bash"` |
| env | TEXT JSON | Step-level env vars | `{"NODE_ENV": "test"}` |
| with_args | TEXT JSON | Action inputs | `{"ref": "main"}` |
| if_condition | TEXT | Conditional expression | `"success()"` |
| timeout_minutes | INTEGER | Step timeout | `10` |
| continue_on_error | BOOLEAN | Continue on failure | `0` |

**Query Example (find unpinned actions):**
```python
cursor.execute("""
    SELECT step_id, uses_action, uses_version, env
    FROM github_steps
    WHERE uses_action IS NOT NULL
    AND uses_version IN ('main', 'master', 'develop', 'v1', 'v2')
    AND (env LIKE '%secrets%' OR env IS NOT NULL)
""")
```

## github_step_outputs

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| id | INTEGER PK AUTOINCREMENT | Auto ID | `1` |
| step_id | TEXT FK | Parent step | `.github/workflows/ci.yml::build::2` |
| output_name | TEXT | Output key | `"version"` |
| output_expression | TEXT | Output value expression | `"${{ steps.version.outputs.value }}"` |

**Query Example:**
```python
cursor.execute("""
    SELECT output_name, output_expression
    FROM github_step_outputs
    WHERE step_id IN (
        SELECT step_id FROM github_steps
        WHERE uses_action = 'actions/checkout'
    )
""")
```

## github_step_references

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| id | INTEGER PK AUTOINCREMENT | Auto ID | `1` |
| step_id | TEXT FK | Parent step | `.github/workflows/ci.yml::build::0` |
| reference_location | TEXT | Where it appears | `"run"` or `"env"` or `"with"` or `"if"` |
| reference_type | TEXT | First segment of path | `"github"` or `"secrets"` or `"needs"` |
| reference_path | TEXT | Full expression path | `"github.event.pull_request.head.sha"` |

**Query Example (find PR data in run scripts):**
```python
cursor.execute("""
    SELECT DISTINCT s.job_id, r.reference_path
    FROM github_step_references r
    JOIN github_steps s ON r.step_id = s.step_id
    WHERE r.reference_location = 'run'
    AND r.reference_path LIKE 'github.event.pull_request%'
""")
```

## Common Query Patterns for Rules

### Pattern 1: Find pull_request_target workflows with early checkout
```python
# Step 1: Get workflows triggered by pull_request_target
cursor.execute("""
    SELECT workflow_path FROM github_workflows
    WHERE on_triggers LIKE '%pull_request_target%'
""")
workflows = [row[0] for row in cursor.fetchall()]

# Step 2: Find early checkout steps in these workflows
for workflow_path in workflows:
    cursor.execute("""
        SELECT s.step_id, s.sequence_order, r.reference_path
        FROM github_steps s
        JOIN github_step_references r ON s.step_id = r.step_id
        WHERE s.job_id LIKE ?
        AND s.uses_action = 'actions/checkout'
        AND r.reference_path LIKE 'github.event.pull_request.head%'
        ORDER BY s.sequence_order
    """, (f"{workflow_path}::%",))
```

### Pattern 2: Find mutable action versions with secrets
```python
cursor.execute("""
    SELECT s.step_id, s.uses_action, s.uses_version, s.env
    FROM github_steps s
    WHERE s.uses_action IS NOT NULL
    AND s.uses_version IN ('main', 'master', 'develop', 'v1', 'v2', 'v3')
    AND (
        s.env LIKE '%secrets.%'
        OR EXISTS (
            SELECT 1 FROM github_step_references r
            WHERE r.step_id = s.step_id
            AND r.reference_type = 'secrets'
        )
    )
""")
```

### Pattern 3: Find jobs with excessive permissions
```python
cursor.execute("""
    SELECT j.job_id, j.permissions, w.on_triggers
    FROM github_jobs j
    JOIN github_workflows w ON j.workflow_path = w.workflow_path
    WHERE w.on_triggers LIKE '%pull_request_target%'
    AND (
        j.permissions LIKE '%write-all%'
        OR j.permissions LIKE '%contents": "write%'
        OR j.permissions LIKE '%packages": "write%'
        OR j.permissions LIKE '%id-token": "write%'
    )
""")
```

## JSON Column Parsing in Python

```python
import json

# Parse JSON columns
cursor.execute("SELECT on_triggers, permissions FROM github_workflows")
for row in cursor.fetchall():
    triggers = json.loads(row[0]) if row[0] else []
    perms = json.loads(row[1]) if row[1] else {}

    if 'pull_request_target' in triggers:
        if perms.get('contents') == 'write':
            # FINDING!
```

## Rule Output Format

```python
from theauditor.rules.base import StandardFinding

findings.append(StandardFinding(
    file=workflow_path,
    line=0,  # Workflow-level finding
    rule="untrusted_checkout_sequence",
    tool="github-actions-rules",
    message=f"pull_request_target workflow checks out untrusted PR code at step {step_name}",
    severity="critical",
    category="supply-chain",
    confidence=0.95,
    code_snippet=f"uses: {uses_action}@{uses_version}\nwith:\n  ref: {ref_value}",
    cwe="CWE-284",
    details_json=json.dumps({
        "workflow": workflow_path,
        "job_id": job_id,
        "step_id": step_id,
        "step_order": sequence_order,
        "checkout_ref": ref_value
    })
))
```
