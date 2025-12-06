# TheAuditor Planning System

## Overview

The Planning System is a **database-centric task management and verification framework** that integrates directly with TheAuditor's indexed codebase. Unlike external tools (Jira, Linear), it provides **deterministic, automated verification** of task completion by querying the actual code.

**Core Philosophy**: Replace human self-assessment with code-driven validation. Task completion is verified through RefactorProfile YAML specs that query the indexed database.

## The Problem It Solves

1. **External Tools Lack Context**: Jira/Linear never see your actual code
2. **Manual Verification is Error-Prone**: Developers assess completion; hard to prove
3. **Large Migrations Need Tracking**: Migration from Auth0→Cognito (47 violations→31→0) requires progress snapshots
4. **Git Can't Track Incremental Edits**: Three uncommitted edits to same file = 1 git change. Planning tracks all 3 separately
5. **Rollback Without Commits**: Create checkpoints before each major change for deterministic rewinding

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CLI: aud planning <command>                                │
│  Commands: init, add-task, verify-task, checkpoint, rewind  │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┬─────────────────────┐
        ▼                     ▼                     ▼
   PlanningManager     RefactorRuleEngine    ShadowRepoManager
   (task mgmt)         (spec verification)   (git snapshots)
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────┐
        │  .pf/planning.db (SQLite)                │
        │  - plans, plan_phases, plan_tasks        │
        │  - plan_specs, plan_jobs                 │
        │  - code_snapshots, code_diffs            │
        └──────────────────────────────────────────┘
```

---

## Key Components

### 1. PlanningManager (`theauditor/planning/manager.py`)
- Database operations and snapshot creation
- Methods: `create_plan()`, `add_task()`, `create_snapshot()`, `load_task_spec()`

### 2. ShadowRepoManager (`theauditor/planning/shadow_git.py`)
- Immutable git repository for snapshots at `.pf/snapshots.git`
- Methods: `create_snapshot()`, `get_diff()`, `get_file_at_snapshot()`

### 3. RefactorRuleEngine Integration
- Evaluates YAML specs against indexed code
- Returns violation counts for progress measurement

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `plans` | Top-level plan with status (active/completed/archived) |
| `plan_phases` | Hierarchical grouping with success criteria |
| `plan_tasks` | Individual tasks with specs and status |
| `plan_specs` | YAML RefactorProfile storage |
| `plan_jobs` | Checkbox items (including audit jobs) |
| `code_snapshots` | Per-task snapshots with sequence numbers |
| `code_diffs` | File-level unified diffs |

---

## CLI Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `init` | Create new plan | `aud planning init --name "JWT Migration"` |
| `add-task` | Add task with spec | `aud planning add-task 1 --title "Migrate auth" --spec auth.yaml` |
| `checkpoint` | Create snapshot | `aud planning checkpoint 1 1 --name "added-imports"` |
| `verify-task` | Run spec verification | `aud planning verify-task 1 1 --verbose` |
| `show-diff` | View checkpoints | `aud planning show-diff 1 1 --sequence 2` |
| `rewind` | Show rollback steps | `aud planning rewind 1 1 --to 2` |
| `archive` | Mark plan complete | `aud planning archive 1 --notes "Deployed"` |

---

## Unique Features

### 1. Code-Driven Verification
Tasks complete when code matches YAML specs - verified against indexed database, not human opinion.

### 2. Sequence-Based Checkpoint Tracking
Each incremental edit within a task gets sequence number (1, 2, 3...). Git only shows uncommitted changes as 1 blob; Planning lets you ask "Show me the diff of edit 2 only."

### 3. Immutable Audit Trail
Every checkpoint committed to `.pf/snapshots.git` (bare repo) with "TheAuditor" as author.

### 4. Progress Measurement
- Verify task before implementation → shows baseline violations
- Re-verify after each checkpoint → shows violations decreasing
- Final verify with `--auto-update` → marks task completed when violations=0

---

## Usage Pattern: Refactoring Migration

```bash
# 1. Plan the migration
aud planning init --name "Upgrade Express v4→v5"
aud planning add-task 1 --title "Update middleware" --spec express_migration.yaml

# 2. Baseline verification (shows all violations = work items)
aud full --index
aud planning verify-task 1 1 --verbose
# Output: 47 violations (all places needing migration)

# 3. Iterative progress tracking
# [Fix 10 violations]
aud planning checkpoint 1 1 --name "updated-auth-middleware"
aud full --index && aud planning verify-task 1 1
# Output: 37 violations remaining (10 fixed!)

# 4. Complete and archive
aud planning archive 1 --notes "Express v5 migration complete"
```

---

## Integration Points

- **aud full**: Verification requires indexed code (`aud full --index`)
- **aud refactor**: Plan specs use same RefactorProfile YAML format
- **aud query**: For greenfield development, find analogous patterns
- **Session History**: `aud planning validate` checks execution against AI session logs
