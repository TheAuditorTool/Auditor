# Planning System Trial Guide - Get Results in 10 Minutes

This guide walks you through trialing the planning system on YOUR test projects.

---

## Prerequisites

Before starting, verify you have:

1. **TheAuditor installed with planning system**
   ```powershell
   aud --version
   # Should show: TheAuditor version 1.3.0-RC1 or higher
   ```

   If command not found, ensure TheAuditor is installed and in your PATH.

2. **Python 3.11+**
   ```powershell
   python --version
   ```

3. **Git configured**
   ```powershell
   git config user.name
   git config user.email
   ```

   If not set:
   ```powershell
   git config --global user.name "Your Name"
   git config --global user.email "your@email.com"
   ```

4. **Windows PowerShell Note:**
   - This guide uses PowerShell syntax throughout
   - Heredoc examples use PowerShell `@" "@` syntax
   - All commands tested on Windows 10/11 PowerShell

---

## Quick Trial Checklist

**You need:**
- [ ] A git repository (any language - Python, JS, TS, Go, etc.)
- [ ] 10-30 minutes
- [ ] TheAuditor installed with planning system

**You'll learn:**
- [ ] How to create a verification spec
- [ ] How to run verification against real code
- [ ] How to iterate until 0 violations
- [ ] How to create audit trail snapshots

---

## Trial Scenario 1: "Remove Hardcoded Secrets" (10 minutes)

**Best for:** Any codebase with API keys, passwords, or secrets

### Step 1: Pick Your Test Project

```bash
# Use any project with some hardcoded strings
cd /path/to/your/test/project

# Initialize TheAuditor
aud init

# Index the codebase (this takes 30-60 seconds for small projects)
aud index
```

**What to look for:**
- `.pf/` directory created
- `repo_index.db` generated
- No errors during indexing

### Step 2: Find Something to Migrate

```powershell
# Search for common hardcoded patterns (PowerShell)
Select-String -Path "*.py","*.js" -Pattern "password" -Recurse | Select-Object -First 10
Select-String -Path "*.py","*.js" -Pattern "api_key" -Recurse | Select-Object -First 10
Select-String -Path "*.py","*.js" -Pattern "secret" -Recurse | Select-Object -First 10
```

**Or use TheAuditor's query (faster):**
```powershell
aud query --symbol "password" --format json
```

**Pick ONE pattern** you found (e.g., hardcoded passwords)

### Step 3: Create Your First Verification Spec

```powershell
# PowerShell: Create a simple spec using heredoc syntax
@"
refactor_name: Remove Hardcoded Secrets
description: Find all hardcoded password/secret strings
version: 1.0

rules:
  - id: no-hardcoded-passwords
    description: Password strings should not exist in code
    severity: critical
    match:
      identifiers: [password, Password, PASSWORD]
    expect:
      identifiers: []
    # Empty expect = pattern should be completely removed
"@ | Out-File -FilePath my_first_spec.yaml -Encoding UTF8
```

**Alternative (using text editor):**
```powershell
# Open in notepad
notepad my_first_spec.yaml

# Then copy-paste the YAML content above and save
```

### Step 4: Create Plan and Add Task

```bash
# Initialize planning system
aud planning init --name "Security Hardening Trial"

# Add task with your spec
aud planning add-task 1 --title "Remove hardcoded secrets" --spec my_first_spec.yaml

# Check it was created
aud planning show 1 --tasks
```

**Expected output:**
```
Plan 1: Security Hardening Trial
Status: active
Tasks (1):
  [ ] Task 1: Remove hardcoded secrets
    Status: pending
```

### Step 5: Run Verification (This is the Magic Part)

```bash
# Run verification - this queries the indexed database
aud planning verify-task 1 1 --verbose
```

**What you'll see:**
```
Verifying task 1...

Verification complete:
  Total violations: 23

Violations by rule:
  no-hardcoded-passwords: 23 violations
    - src/config.py:15
    - src/auth.py:42
    - tests/test_auth.py:18
    ... and 20 more
```

**KEY INSIGHT:** These are the EXACT file:line locations where your pattern exists.

### Step 6: Fix Some Violations (Not All)

```bash
# Pick 2-3 files from the violation list
# Edit them to remove/change the pattern
# For example, change:
#   password = "hardcoded123"
# To:
#   password = os.getenv("PASSWORD")

# After making changes, re-index
aud index

# Run verification again
aud planning verify-task 1 1 --verbose
```

**What you'll see:**
```
Verification complete:
  Total violations: 20

# Violations decreased from 23 -> 20 (you fixed 3)
```

**THIS IS THE KEY FEATURE:** You can track progress numerically.

### Step 7: Complete the Task

```bash
# Keep fixing violations until you see:
aud index && aud planning verify-task 1 1 --auto-update

# When 0 violations:
Verification complete:
  Total violations: 0

Task status updated: completed
```

### Step 8: Archive with Proof

```bash
# Create final snapshot
aud planning archive 1 --notes "Trial complete - 23 violations fixed"

# This creates git snapshot in planning.db
```

**Congratulations!** You just completed a verified refactoring with audit trail.

---

## Trial Scenario 2: "API Version Migration" (20 minutes)

**Best for:** Projects with multiple API endpoints

### Find Your API Routes

```bash
cd /path/to/your/api/project
aud init && aud index

# Search for API route patterns
aud query --api "/api" --format json
```

### Create Migration Spec

```powershell
# PowerShell heredoc syntax
@"
refactor_name: API v1 to v2 Migration
description: Ensure all routes use /api/v2
version: 1.0

rules:
  - id: remove-v1-routes
    description: Old /api/v1 routes should be removed
    severity: high
    match:
      api_routes: ['/api/v1']
    expect:
      api_routes: []

  - id: v2-routes-present
    description: New /api/v2 routes should exist
    severity: critical
    match:
      api_routes: ['/api/v2']
    expect:
      api_routes: ['/api/v2/users', '/api/v2/products']
"@ | Out-File -FilePath api_migration_spec.yaml -Encoding UTF8
```

### Run the Workflow

```bash
aud planning init --name "API Version Migration"
aud planning add-task 1 --title "Migrate to v2" --spec api_migration_spec.yaml

# Baseline verification (expect violations)
aud planning verify-task 1 1 --verbose

# Make changes to your routes
# Re-verify iteratively
aud index && aud planning verify-task 1 1 --verbose

# Archive when done
aud planning archive 1 --notes "API v2 migration complete"
```

---

## Trial Scenario 3: "Database Model Rename" (30 minutes)

**Best for:** Projects with ORM models (Django, SQLAlchemy, Prisma, TypeORM)

### Example: Rename "User" to "Account"

```bash
cd /path/to/your/orm/project
aud init && aud index
```

### Create Comprehensive Spec

```powershell
# PowerShell heredoc syntax
@"
refactor_name: User to Account Rename
description: Rename User model to Account everywhere
version: 1.0

rules:
  - id: remove-user-model
    description: Old User model should not exist
    severity: critical
    match:
      identifiers: [class User, model.User, UserModel]
    expect:
      identifiers: []

  - id: account-model-present
    description: New Account model should exist
    severity: critical
    match:
      identifiers: [class Account, model.Account, AccountModel]
    expect:
      identifiers: [class Account]

  - id: update-foreign-keys
    description: Foreign keys should reference account_id
    severity: high
    match:
      identifiers: [user_id, userId]
    expect:
      identifiers: [account_id, accountId]
"@ | Out-File -FilePath model_rename_spec.yaml -Encoding UTF8
```

### Run Iterative Refactoring

```bash
aud planning init --name "Model Rename Refactor"
aud planning add-task 1 --title "Rename User->Account" --spec model_rename_spec.yaml

# Baseline
aud planning verify-task 1 1 --verbose
# Output: 147 violations

# Do search-replace on SOME files
# Re-verify
aud index && aud planning verify-task 1 1 --verbose
# Output: 89 violations (you fixed 58)

# Continue until 0
```

---

## What Makes a Good Trial Project?

**✅ GOOD Projects:**
- Has patterns you want to change (console.log, hardcoded values, old APIs)
- 1,000 - 50,000 lines of code (small enough to iterate quickly)
- You have 30+ minutes to spend
- Git repository (for snapshots)

**❌ BAD Projects:**
- Tiny projects (<100 lines) - not enough to see value
- Huge projects (>500k lines) - first `aud index` takes 5-10 minutes
- No repeated patterns - nothing to verify

---

## Expected Timings

| Task | Time |
|------|------|
| `aud init` | 1 second |
| `aud index` (10k LOC) | 30-60 seconds |
| `aud index` (100k LOC) | 3-5 minutes |
| Create verification spec | 2-5 minutes (first time) |
| `aud planning verify-task` | 1-5 seconds |
| Fix violations | Depends on how many |

**Pro tip:** Start with a small project (1,000-10,000 lines) for fastest feedback.

---

## Common Patterns to Try

### For Python Projects

```yaml
# Find all print() statements (should use logging)
refactor_name: Replace print with logging
rules:
  - id: no-print
    match:
      identifiers: [print]
    expect:
      identifiers: [logging.info, logging.debug, logger]

# Find hardcoded file paths
refactor_name: Remove hardcoded paths
rules:
  - id: no-hardcoded-paths
    match:
      identifiers: ['/tmp/', '/var/', 'C:\\']
    expect:
      identifiers: [Path, pathlib, os.path]
```

### For JavaScript/TypeScript Projects

```yaml
# Remove console.log
refactor_name: Remove console logging
rules:
  - id: no-console
    match:
      identifiers: [console.log, console.debug]
    expect:
      identifiers: []

# Migrate var to const/let
refactor_name: Modernize variable declarations
rules:
  - id: no-var
    match:
      identifiers: [var]
    expect:
      identifiers: [const, let]
```

### For Any Project

```yaml
# Remove TODO comments (find incomplete work)
refactor_name: Clean up TODOs
rules:
  - id: no-todos
    match:
      identifiers: [TODO, FIXME, HACK]
    expect:
      identifiers: []
```

---

## Troubleshooting

### "Error: repo_index.db not found"

**Fix:** Run `aud index` first before `verify-task`

### "Total violations: 0" but you know there are matches

**Cause:** Your spec pattern doesn't match what's in the indexed database

**Fix:**
1. Check what's actually indexed: `aud query --symbol "YourPattern" --format json`
2. Adjust your spec's `match.identifiers` to match indexed symbols

### "Verification takes 30+ seconds"

**Cause:** Complex spec with many rules on large codebase

**Fix:**
- Simplify spec (fewer rules)
- Use more specific patterns (fewer matches)
- Normal for first run, subsequent runs are faster

### "Snapshot creation fails with git errors"

**Cause:** Not in a git repository or git not configured

**Fix:**
```bash
git init
git config user.email "test@example.com"
git config user.name "Test User"
git add .
git commit -m "Initial commit"
```

---

## Quick Win: 5-Minute Trial

**Fastest way to see it work:**

```powershell
# 1. Pick any project
cd C:\path\to\project
aud init
aud index

# 2. Create dead-simple spec (PowerShell)
@"
refactor_name: Find TODOs
rules:
  - id: find-todos
    match:
      identifiers: [TODO, FIXME]
    expect:
      identifiers: []
"@ | Out-File -FilePath quick_spec.yaml -Encoding UTF8

# 3. Run it
aud planning init --name "Quick Test"
aud planning add-task 1 --spec quick_spec.yaml
aud planning verify-task 1 1 --verbose

# You'll see all TODOs/FIXMEs with file:line precision
```

**Total time:** 5 minutes
**Value:** You just saw deterministic code querying in action

---

## What Success Looks Like

After your trial, you should be able to say:

✅ "I wrote a spec and ran verification"
✅ "I saw exact file:line violations"
✅ "I fixed some violations and re-verified"
✅ "I watched the violation count decrease"
✅ "I got to 0 violations and archived the task"
✅ "I understand why this prevents production incidents"

---

## Next Steps After Trial

### If you liked it:

1. **Use on real work:** Next refactoring task, use planning system
2. **Write better specs:** Check `docs/planning/examples/` for production examples
3. **Integrate with CI:** Run `aud planning verify-task` in CI pipeline
4. **Train team:** Share violation counts as objective progress metrics

### If you didn't like it:

**Tell me why!** This is RC1, feedback is critical:
- Was it too slow?
- Confusing to use?
- Spec format unclear?
- Didn't catch what you expected?

---

## Pro Tips

1. **Start with simple specs** (1 rule) then add complexity
2. **Re-run verification frequently** (fast feedback loop)
3. **Use `--verbose` to see exact violations** (shows file:line)
4. **Use `--auto-update` only at the end** (prevents premature completion)
5. **Check violation count trends** (should decrease over time)

---

## Trial Success Metrics

| Metric | What It Means |
|--------|---------------|
| Verification runs in <5s | System is fast enough for iterative use |
| Violations decrease with each fix | Your spec is correct |
| Reaches 0 violations | You achieved complete coverage |
| Archive creates snapshot | Audit trail is working |

---

**Ready to trial? Pick Scenario 1 (10 minutes) and start now!**

Questions? Run `aud planning --help` for full documentation.
