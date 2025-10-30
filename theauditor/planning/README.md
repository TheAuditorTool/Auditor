# Planning System Documentation

The planning system provides database-centric task tracking with deterministic verification, integrated directly with TheAuditor's indexed codebase.

## Quick Start

```bash
# Initialize a plan
aud planning init --name "My Migration Plan"

# Add tasks with verification specs
aud planning add-task 1 --title "Migrate auth" --spec examples/auth_migration.yaml

# Make code changes, then verify
aud index && aud planning verify-task 1 1 --verbose

# Archive when complete
aud planning archive 1 --notes "Migration deployed to production"
```

## Core Concepts

### Database-Centric State

All planning data is stored in `.pf/planning.db`, separate from `repo_index.db`. This separation ensures:
- Planning state persists across `aud full` runs (which regenerate repo_index.db)
- Different query patterns optimized for each database
- Clear separation between code metadata and planning metadata

### Verification Specs

Specs use the RefactorProfile YAML format, compatible with `aud refactor`. Each spec defines:
- **match**: Patterns to find in the codebase (old code)
- **expect**: Patterns that should exist (new code)
- **expect_not**: Patterns that should be removed

Example:
```yaml
refactor_name: Remove Deprecated API
description: Remove usage of deprecated authentication methods
rules:
  - id: remove-old-auth
    match:
      identifiers: [oldAuthMethod]
    expect:
      identifiers: []  # Should be completely removed
```

### Git Snapshots

When verification fails, the system automatically creates a snapshot:
- Captures full git diff of current working directory
- Stores in `code_snapshots` and `code_diffs` tables
- Enables deterministic rollback via `aud planning rewind`

### Task Workflow

1. **pending** - Task created, not started
2. **in_progress** - Work underway
3. **completed** - Verification passed (0 violations)
4. **blocked** - Cannot proceed due to dependencies

## Example Specs

The `examples/` directory contains real-world verification specs:

### JWT Security Migration (`jwt_migration.yaml`)
Ensures all JWT signing operations use environment variables instead of hardcoded secrets.

**Use case**: Security hardening, credential rotation preparation
**Verification**: Checks that `jwt.sign()` calls reference `process.env.JWT_SECRET`

### Auth Provider Migration (`auth_migration.yaml`)
Migrates from Auth0 to AWS Cognito across the entire codebase.

**Use case**: Provider switching, vendor consolidation
**Verification**: Removes Auth0 imports, verifies Cognito implementation

### Database Model Rename (`model_rename.yaml`)
Renames a database model (e.g., User → Account) across all references.

**Use case**: Model refactoring, schema evolution
**Verification**: Checks model class, queries, relationships, API routes

### API Versioning (`api_versioning.yaml`)
Migrates from v1 to v2 API endpoints while maintaining backward compatibility.

**Use case**: API evolution, breaking changes with deprecation period
**Verification**: Ensures v2 routes exist, v1 deprecated but functional

## Common Workflows

### Greenfield Feature Development

When implementing a new feature with no existing code:

```bash
# 1. Initialize plan
aud planning init --name "Add Product Catalog"

# 2. Find analogous patterns
aud query --api "/users" --format json  # See how existing endpoints work

# 3. Add tasks (no spec yet - greenfield)
aud planning add-task 1 --title "Create Product model"
aud planning add-task 2 --title "Add CRUD endpoints"

# 4. Implement features
# [Write code]

# 5. Add verification spec after implementation
# Create spec that verifies your new patterns exist
aud planning add-task 3 --title "Verify implementation" --spec product_verification.yaml

# 6. Verify
aud index && aud planning verify-task 1 3 --verbose
```

### Refactoring Migration

When changing existing code to new patterns:

```bash
# 1. Initialize plan
aud planning init --name "Modernize Authentication"

# 2. Create verification spec defining old → new patterns
# See examples/auth_migration.yaml

# 3. Add task with spec
aud planning add-task 1 --title "Migrate to OAuth2" --spec auth_spec.yaml

# 4. Baseline verification (expect violations)
aud index && aud planning verify-task 1 1 --verbose
# Output: 47 violations (all places needing migration)

# 5. Make incremental changes
# [Update some files]

# 6. Re-verify (track progress)
aud index && aud planning verify-task 1 1 --verbose
# Output: 31 violations (16 fixed, 31 remaining)

# 7. Repeat until 0 violations
# [Continue fixing]

# 8. Final verification
aud index && aud planning verify-task 1 1 --auto-update
# Output: 0 violations, task marked completed

# 9. Archive
aud planning archive 1 --notes "Auth migration complete, deployed v2.0"
```

### Checkpoint-Driven Development

For complex changes with rollback points:

```bash
# 1. Add task
aud planning add-task 1 --title "Refactor database layer"

# 2. Make partial changes
# [Modify 10 files]

# 3. Verify (creates snapshot if violations exist)
aud planning verify-task 1 1
# Snapshot created: abc123de

# 4. Continue work
# [Modify 10 more files]

# 5. If things break, check available snapshots
aud planning rewind 1

# 6. Rollback to snapshot if needed
aud planning rewind 1 --checkpoint "verify-task-1-failed"
# Shows git commands to revert

# 7. Execute rollback
git checkout abc123de
```

## Database Schema

### Tables

**plans** - Top-level plan metadata
- `id`: Primary key
- `name`: Plan name
- `description`: Plan description
- `status`: active | completed | archived
- `created_at`: Timestamp
- `metadata_json`: Flexible JSON metadata

**plan_tasks** - Individual tasks within plans
- `id`: Primary key
- `plan_id`: Foreign key to plans
- `task_number`: User-facing task number (1, 2, 3...)
- `title`: Task title
- `description`: Task description
- `status`: pending | in_progress | completed | blocked
- `assigned_to`: Optional assignee
- `spec_id`: Foreign key to plan_specs (nullable)
- `created_at`: Timestamp
- `completed_at`: Completion timestamp

**plan_specs** - YAML verification specs
- `id`: Primary key
- `plan_id`: Foreign key to plans
- `spec_yaml`: Full YAML text (RefactorProfile format)
- `spec_type`: Optional type classification
- `created_at`: Timestamp

**code_snapshots** - Git checkpoint metadata
- `id`: Primary key
- `plan_id`: Foreign key to plans
- `task_id`: Foreign key to plan_tasks (nullable)
- `checkpoint_name`: Descriptive name
- `timestamp`: When snapshot was created
- `git_ref`: Git commit SHA
- `files_json`: JSON array of affected files

**code_diffs** - Full git diffs for snapshots
- `id`: Primary key
- `snapshot_id`: Foreign key to code_snapshots
- `file_path`: Path to file
- `diff_text`: Full unified diff text
- `added_lines`: Count of + lines
- `removed_lines`: Count of - lines

## Command Reference

### init

Create a new implementation plan.

```bash
aud planning init --name "Plan Name" [--description "Description"]
```

Auto-creates `.pf/planning.db` if it doesn't exist.

### show

Display plan details and task status.

```bash
aud planning show PLAN_ID [--tasks] [--verbose]
```

Options:
- `--tasks`: Show task list with status
- `--verbose`: Show full metadata and descriptions

### add-task

Add a task to a plan with optional verification spec.

```bash
aud planning add-task PLAN_ID --title "Task Title" [--description "Desc"] [--spec spec.yaml] [--assigned-to "Name"]
```

Task numbers auto-increment (1, 2, 3...).

### update-task

Update task status or assignment.

```bash
aud planning update-task PLAN_ID TASK_NUMBER [--status STATUS] [--assigned-to "Name"]
```

Status values: `pending`, `in_progress`, `completed`, `blocked`

### verify-task

Verify task completion against its spec.

```bash
aud planning verify-task PLAN_ID TASK_NUMBER [--verbose] [--auto-update]
```

Options:
- `--verbose`: Show detailed violation list
- `--auto-update`: Auto-mark completed if 0 violations

**Prerequisites**: Must run `aud index` after code changes.

### archive

Archive completed plan with final snapshot.

```bash
aud planning archive PLAN_ID [--notes "Archive notes"]
```

Creates final git snapshot and marks plan as archived.

### rewind

Show rollback instructions for a plan.

```bash
aud planning rewind PLAN_ID [--checkpoint "checkpoint-name"]
```

Without `--checkpoint`: Lists all snapshots
With `--checkpoint`: Shows git commands to rollback

**Safety**: Only displays commands, does not execute them.

## Integration with Other Commands

### With `aud index`

Verification requires indexed code:

```bash
# Pattern: modify → index → verify
[Make code changes]
aud index                              # Update repo_index.db
aud planning verify-task 1 1 --verbose # Query indexed code
```

### With `aud query`

Find analogous patterns for greenfield development:

```bash
# Find existing API routes
aud query --api "/users" --format json

# Find similar functions
aud query --symbol "createUser" --format json

# Use findings to guide new implementation
```

### With `aud refactor`

Planning specs use the same RefactorProfile format:

```bash
# Test spec outside of planning
aud refactor --profile my_spec.yaml --print-violations

# If spec works, attach to task
aud planning add-task 1 --title "Task" --spec my_spec.yaml
```

### With `aud blueprint`

Get architectural overview before planning:

```bash
# Understand codebase structure
aud blueprint --format text

# Plan based on actual architecture
aud planning init --name "Refactor based on blueprint findings"
```

## Tips and Best Practices

### Writing Good Specs

1. **Start broad, refine narrow**: Begin with high-level patterns, add specific rules iteratively
2. **Test specs independently**: Use `aud refactor --profile spec.yaml` before attaching to tasks
3. **Use severity correctly**: `critical` for breaking changes, `high` for important patterns, `medium` for style
4. **Expect empty for removal**: Use `expect: {identifiers: []}` to verify complete removal
5. **Combine multiple rules**: One spec can check multiple aspects (imports, API routes, configs)

### Task Granularity

- **Too large**: "Migrate entire auth system" (hard to verify incrementally)
- **Too small**: "Change variable name in file.js" (not worth tracking)
- **Just right**: "Migrate /auth routes to OAuth2" (specific, verifiable component)

### When to Checkpoint

Create snapshots at logical boundaries:
- Before major refactoring
- After each component migration
- Before potentially breaking changes
- When verification shows many violations (track progress)

### Verification Timing

- Run verification frequently during development (fast feedback)
- Use `--auto-update` for final verification only (prevents premature completion)
- Re-index before each verification (code changes must be indexed first)

## Troubleshooting

### "Error: repo_index.db not found"

**Cause**: Verification requires indexed code.
**Solution**: Run `aud index` or `aud full` first.

### "Error: No verification spec for task"

**Cause**: Task has no `spec_id` (was created without `--spec`).
**Solution**: Cannot verify tasks without specs. Create new task with spec or mark as completed manually.

### "Verification finds unexpected violations"

**Cause**: Spec might be too strict or matches unintended patterns.
**Solution**: Use `--verbose` to see exact violations, refine spec rules.

### "Planning.db doesn't exist"

**Cause**: First time running planning commands.
**Solution**: Run `aud planning init` to auto-create database.

## Performance Notes

Typical operation latency:
- `init`: <50ms (creates database file)
- `show`: <10ms (single SELECT query)
- `add-task`: <20ms (auto-increment + INSERT)
- `verify-task`: 100ms-5s (depends on spec complexity)
- `archive`: 200ms-2s (git diff parsing + writes)

Scalability:
- Plans: Unlimited (int primary key)
- Tasks per plan: ~1000 practical limit (UI becomes unwieldy)
- Snapshots per plan: ~50 tested (archive time <5s)
- Verification complexity: O(n*r) where n=files, r=rules

## Further Reading

- **RefactorProfile format**: See `aud refactor --help`
- **Code querying**: See `aud query --help`
- **Blueprint visualization**: See `aud blueprint --help`
- **Main documentation**: See project README.md
