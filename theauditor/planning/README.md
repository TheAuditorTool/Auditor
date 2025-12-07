# Planning System Documentation

The planning system provides database-centric task tracking with deterministic verification, integrated directly with TheAuditor's indexed codebase.

**NEW FEATURE**: Incremental edit tracking with sequence numbers!

Track every AI edit within a task - something git can't do for uncommitted changes!

## Quick Start

```bash
# Initialize a plan
aud planning init --name "My Migration Plan"

# Add tasks with verification specs
aud planning add-task 1 --title "Migrate auth" --spec examples/auth_migration.yaml

# Make code changes, then verify
aud full --index && aud planning verify-task 1 1 --verbose

# Archive when complete
aud planning archive 1 --notes "Migration deployed to production"
```

## Core Concepts

### Database-Centric State

All planning data is stored in `.pf/planning/planning.db`, separate from `repo_index.db`. This separation ensures:
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
aud full --index && aud planning verify-task 1 3 --verbose
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
aud full --index && aud planning verify-task 1 1 --verbose
# Output: 47 violations (all places needing migration)

# 5. Make incremental changes
# [Update some files]

# 6. Re-verify (track progress)
aud full --index && aud planning verify-task 1 1 --verbose
# Output: 31 violations (16 fixed, 31 remaining)

# 7. Repeat until 0 violations
# [Continue fixing]

# 8. Final verification
aud full --index && aud planning verify-task 1 1 --auto-update
# Output: 0 violations, task marked completed

# 9. Archive
aud planning archive 1 --notes "Auth migration complete, deployed v2.0"
```

### Checkpoint-Driven Development (Incremental Tracking)

**The Problem Git Can't Solve:** You make 3 incremental edits to `auth.ts` (add imports, add handler, add error handling). Git only sees 1 uncommitted change. If edit 3 breaks things, you can't easily revert to "after edit 2".

**The Solution:** Planning checkpoints with sequence tracking.

```bash
# 1. Initialize plan and task
aud planning init --name "Implement OAuth Flow"
aud planning add-task 1 --title "Add OAuth routes"

# 2. Make edit 1: Add imports
[modify auth.ts - add import statements]
aud planning checkpoint 1 1 --name "added-imports"
# Checkpoint created: sequence 1

# 3. Make edit 2: Add route handler
[modify auth.ts - add route handler function]
aud planning checkpoint 1 1  # Auto-generates "edit_2"
# Checkpoint created: sequence 2

# 4. Make edit 3: Add error handling
[modify auth.ts - add try/catch blocks]
aud planning checkpoint 1 1 --name "added-error-handling"
# Checkpoint created: sequence 3

# 5. View all checkpoints
aud planning show-diff 1 1
# Output:
#   [1] added-imports
#   [2] edit_2
#   [3] added-error-handling

# 6. If edit 3 broke things, rewind to after edit 2
aud planning rewind 1 1 --to 2
# Shows which checkpoints apply: [1] and [2], stops before [3]

# 7. View the exact diff at checkpoint 2
aud planning show-diff 1 1 --sequence 2
# Shows full unified diff as of edit 2

# 8. Rollback if needed (execute the git commands shown)
git checkout <commit-sha-from-rewind>
```

**Key Insight:** Each checkpoint stores the full git diff at that point. Sequence numbers let you say "I want the code state after edit 2" even though all 3 edits are uncommitted changes to the same file.

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
- `sequence`: Auto-incrementing sequence number per task (NEW)
- `checkpoint_name`: Descriptive name
- `timestamp`: When snapshot was created
- `git_ref`: Git commit SHA
- `files_json`: JSON array of affected files

**Key Feature:** `sequence` enables incremental tracking. Task 1 can have sequences 1,2,3 while Task 2 also has sequences 1,2,3. Sequences are per-task, not global.

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

Auto-creates `.pf/planning/planning.db` if it doesn't exist.

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

**Prerequisites**: Must run `aud full --index` after code changes.

### archive

Archive completed plan with final snapshot.

```bash
aud planning archive PLAN_ID [--notes "Archive notes"]
```

Creates final git snapshot and marks plan as archived.

### rewind

Show rollback instructions for a plan or task.

```bash
aud planning rewind PLAN_ID [--checkpoint "checkpoint-name"]
aud planning rewind PLAN_ID TASK_NUMBER [--to SEQUENCE]
```

**Plan-level rewind:**
- Without `--checkpoint`: Lists all plan snapshots
- With `--checkpoint`: Shows git commands to rollback

**Task-level rewind (NEW - Granular Control):**
- Without `--to`: Lists all task checkpoints with sequence numbers
- With `--to N`: Shows commands to rewind to sequence N (e.g., `--to 2` for edit_2)

**Safety**: Only displays commands, does not execute them.

### checkpoint (NEW)

Create incremental snapshot after editing code.

```bash
aud planning checkpoint PLAN_ID TASK_NUMBER [--name "checkpoint-name"]
```

Use this after each edit to track incremental changes within a task. Each checkpoint gets an auto-incrementing sequence number (1, 2, 3...).

**Auto-naming:** If `--name` omitted, generates names like `edit_2`, `edit_3`, etc.

**The Brilliant Insight:** Git can't distinguish 3 incremental edits to an uncommitted file. Planning checkpoints can.

Example:
```bash
# AI makes edit 1
[modify auth.ts]
aud planning checkpoint 1 1 --name "added-imports"  # Sequence 1

# AI makes edit 2
[modify auth.ts again]
aud planning checkpoint 1 1  # Auto-generates "edit_2", Sequence 2

# AI makes edit 3
[modify auth.ts again]
aud planning checkpoint 1 1 --name "added-error-handling"  # Sequence 3
```

### show-diff (NEW)

View stored diffs for a task.

```bash
aud planning show-diff PLAN_ID TASK_NUMBER [--sequence N] [--file FILENAME]
```

Lists all checkpoints for a task, or displays the diff for a specific checkpoint.

Options:
- No options: Lists all checkpoints with sequence numbers
- `--sequence N`: Shows full diff for checkpoint N
- `--file FILENAME`: Filter diffs to specific file (works with --sequence)

Example:
```bash
# List all checkpoints
aud planning show-diff 1 1
# Output:
#   [1] added-imports
#   [2] edit_2
#   [3] added-error-handling

# View specific checkpoint's diff
aud planning show-diff 1 1 --sequence 2

# View diffs for specific file only
aud planning show-diff 1 1 --sequence 2 --file auth.ts
```

## Integration with Other Commands

### With `aud full`

Verification requires indexed code:

```bash
# Pattern: modify → index → verify
[Make code changes]
aud full --index                       # Update repo_index.db
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
aud refactor --file my_spec.yaml

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
2. **Test specs independently**: Use `aud refactor --file spec.yaml` before attaching to tasks
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
**Solution**: Run `aud full --index` or `aud full` first.

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
