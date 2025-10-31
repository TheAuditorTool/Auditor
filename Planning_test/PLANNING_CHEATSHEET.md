# Planning System Cheat Sheet

**For PowerShell Users:** All commands work in PowerShell. File creation uses PowerShell heredoc syntax (`@" "@`).

## Quick Reference Commands

```powershell
# Initialize planning system (creates .pf/planning.db)
aud planning init --name "Plan Name" --description "Optional description"

# Add task with verification spec
aud planning add-task PLAN_ID --title "Task title" --spec spec.yaml --assigned-to "Name"

# Add task without spec (manual tracking only)
aud planning add-task PLAN_ID --title "Task title"

# Show plan details
aud planning show PLAN_ID
aud planning show PLAN_ID --tasks
aud planning show PLAN_ID --tasks --verbose

# Run verification (MUST run 'aud index' first!)
aud index && aud planning verify-task PLAN_ID TASK_NUMBER --verbose

# Auto-mark completed if 0 violations
aud planning verify-task PLAN_ID TASK_NUMBER --auto-update

# Update task status manually
aud planning update-task PLAN_ID TASK_NUMBER --status completed
aud planning update-task PLAN_ID TASK_NUMBER --status in_progress
aud planning update-task PLAN_ID TASK_NUMBER --status blocked

# Reassign task
aud planning update-task PLAN_ID TASK_NUMBER --assigned-to "Alice"

# Archive completed plan
aud planning archive PLAN_ID --notes "Deployment notes"

# Show rollback instructions
aud planning rewind PLAN_ID
aud planning rewind PLAN_ID --checkpoint "checkpoint-name"
```

## Spec Template (Copy-Paste Ready)

```yaml
refactor_name: Your Refactoring Name
description: What you're doing
version: 1.0

rules:
  # Rule to REMOVE a pattern
  - id: remove-old-pattern
    description: Old pattern should not exist
    severity: critical
    match:
      identifiers: [oldFunction, OldClass]
    expect:
      identifiers: []  # Empty = should be completely gone

  # Rule to ADD a pattern
  - id: new-pattern-present
    description: New pattern should exist
    severity: critical
    match:
      identifiers: [newFunction, NewClass]
    expect:
      identifiers: [newFunction]  # At least one match required

  # Rule to REPLACE patterns
  - id: replace-pattern
    description: Old should be replaced with new
    severity: high
    match:
      identifiers: [oldAPI]
    expect:
      identifiers: [newAPI]  # If oldAPI found, newAPI must also exist
```

## Common Spec Patterns

### Remove console.log (JavaScript)

```yaml
refactor_name: Remove Console Logging
rules:
  - id: no-console
    match:
      identifiers: [console.log, console.debug, console.warn, console.info]
    expect:
      identifiers: []
```

### Remove print() (Python)

```yaml
refactor_name: Use Logging Instead of Print
rules:
  - id: no-print
    match:
      identifiers: [print]
    expect:
      identifiers: [logging.info, logging.debug, logger]
```

### Remove Hardcoded Secrets

```yaml
refactor_name: Remove Hardcoded Secrets
rules:
  - id: no-hardcoded-secrets
    match:
      identifiers: [password, api_key, secret, token]
    expect:
      identifiers: [os.getenv, process.env, config]
```

### Migrate var to const/let (JavaScript)

```yaml
refactor_name: Modernize Variable Declarations
rules:
  - id: no-var
    match:
      identifiers: [var]
    expect:
      identifiers: [const, let]
```

### API Route Migration

```yaml
refactor_name: API v1 to v2 Migration
rules:
  - id: remove-v1
    match:
      api_routes: ['/api/v1']
    expect:
      api_routes: []

  - id: v2-present
    match:
      api_routes: ['/api/v2']
    expect:
      api_routes: ['/api/v2/users', '/api/v2/products']
```

### Database Model Rename

```yaml
refactor_name: User to Account Model Rename
rules:
  - id: remove-user-model
    match:
      identifiers: [class User, UserModel, db.User]
    expect:
      identifiers: []

  - id: account-model-present
    match:
      identifiers: [class Account, AccountModel, db.Account]
    expect:
      identifiers: [class Account]

  - id: update-foreign-keys
    match:
      identifiers: [user_id, userId]
    expect:
      identifiers: [account_id, accountId]
```

## Typical Workflows

### Greenfield Development (No Spec Needed)

```bash
aud planning init --name "New Feature"
aud planning add-task 1 --title "Implement user registration"
aud planning add-task 1 --title "Add email validation"
aud planning update-task 1 1 --status completed
aud planning archive 1
```

### Refactoring with Verification

```bash
# 1. Create plan
aud planning init --name "Security Hardening"

# 2. Add task with spec
aud planning add-task 1 --title "Remove secrets" --spec secrets_spec.yaml

# 3. Baseline verification (expect violations)
aud index && aud planning verify-task 1 1 --verbose
# Output: 47 violations

# 4. Fix some violations
[make code changes]

# 5. Re-verify (iterative)
aud index && aud planning verify-task 1 1 --verbose
# Output: 32 violations (fixed 15)

# 6. Continue until 0
aud index && aud planning verify-task 1 1 --auto-update
# Output: 0 violations, status: completed

# 7. Archive with proof
aud planning archive 1 --notes "47 vulnerabilities fixed"
```

### Multi-Task Migration

```bash
aud planning init --name "Auth0 to Cognito Migration"

# Break into smaller tasks
aud planning add-task 1 --title "Remove Auth0 imports" --spec auth_part1.yaml
aud planning add-task 1 --title "Add Cognito config" --spec auth_part2.yaml
aud planning add-task 1 --title "Update routes" --spec auth_part3.yaml

# Verify each task independently
aud planning verify-task 1 1 --verbose
aud planning verify-task 1 2 --verbose
aud planning verify-task 1 3 --verbose

# Mark completed as you go
aud planning update-task 1 1 --status completed
# ... etc
```

## Troubleshooting

| Error | Solution |
|-------|----------|
| `Error: repo_index.db not found` | Run `aud index` first |
| `Error: planning.db not found` | Run `aud planning init` first |
| `Error: Task N not found` | Check task numbers with `aud planning show PLAN_ID --tasks` |
| `Total violations: 0` but should have violations | Check your spec patterns with `aud query --symbol "YourPattern"` |
| Verification is slow (>30s) | Simplify spec (fewer rules), use more specific patterns |
| Git snapshot fails | Initialize git: `git init && git add . && git commit -m "init"` |

## Performance Guidelines

| Operation | Typical Time | Notes |
|-----------|--------------|-------|
| `aud planning init` | <50ms | Creates database |
| `aud planning add-task` | <20ms | Inserts task |
| `aud planning verify-task` | 100ms-5s | Depends on spec complexity |
| `aud planning archive` | 200ms-2s | Git diff parsing |
| `aud index` (10k LOC) | 30-60s | Must run before verification |
| `aud index` (100k LOC) | 3-5 minutes | One-time cost |

## Best Practices

1. **Run verification frequently** - Fast feedback loop
2. **Start with simple specs** - Add complexity incrementally
3. **Use `--verbose` during development** - See exact violations
4. **Use `--auto-update` only at the end** - Prevents premature completion
5. **Create checkpoints** - Snapshot after major changes
6. **Write descriptive notes** - Archive with deployment context

## File Locations

```
.pf/
├── repo_index.db       # Code index (regenerated by aud full)
└── planning.db         # Planning data (persists across aud full)

docs/planning/
├── README.md           # Full documentation
└── examples/
    ├── jwt_migration.yaml
    ├── auth_migration.yaml
    ├── model_rename.yaml
    └── api_versioning.yaml
```

## Quick Copy-Paste Workflows

### 5-Minute Trial

```powershell
cd C:\path\to\project
aud init
aud index
@"
refactor_name: Find TODOs
rules:
  - id: todos
    match:
      identifiers: [TODO, FIXME]
    expect:
      identifiers: []
"@ | Out-File -FilePath trial.yaml -Encoding UTF8
aud planning init --name "Trial"
aud planning add-task 1 --spec trial.yaml
aud planning verify-task 1 1 --verbose
```

### Security Hardening

```powershell
@"
refactor_name: Security Hardening
rules:
  - id: no-hardcoded-secrets
    match:
      identifiers: [password, api_key, secret]
    expect:
      identifiers: [os.getenv, process.env]
"@ | Out-File -FilePath security.yaml -Encoding UTF8
aud planning init --name "Security Audit"
aud planning add-task 1 --spec security.yaml
aud index
aud planning verify-task 1 1 --verbose
```

### Clean Up Logging

```powershell
@"
refactor_name: Clean Up Logging
rules:
  - id: no-console
    match:
      identifiers: [console.log, print]
    expect:
      identifiers: [logger, logging]
"@ | Out-File -FilePath logging.yaml -Encoding UTF8
aud planning init --name "Logging Cleanup"
aud planning add-task 1 --spec logging.yaml
aud index
aud planning verify-task 1 1 --verbose
```

## Help Commands

```powershell
aud planning --help                    # Overview
aud planning init --help               # Init details
aud planning verify-task --help        # Verification options
aud --help                             # Main TheAuditor help
```

## PowerShell Tips

### Creating YAML Files

**Method 1: Heredoc (inline)**
```powershell
@"
refactor_name: My Spec
rules:
  - id: rule-1
    match:
      identifiers: [oldFunction]
    expect:
      identifiers: []
"@ | Out-File -FilePath spec.yaml -Encoding UTF8
```

**Method 2: Notepad (manual)**
```powershell
notepad spec.yaml
# Copy-paste YAML content, save
```

### Path Formatting

PowerShell accepts both formats:
```powershell
cd C:\Users\santa\project        # Backslashes
cd C:/Users/santa/project        # Forward slashes (works in PowerShell)
```

### Chaining Commands

Use semicolons in PowerShell:
```powershell
aud init; aud index              # Sequential execution
```

Or use `&&` in PowerShell 7+:
```powershell
aud init && aud index            # Stops on first error
```

## Full Documentation

- `docs/planning/README.md` - Complete guide (436 lines)
- `docs/planning/examples/` - Production-ready spec templates
- `TRIAL_GUIDE.md` - Step-by-step trial scenarios
