# Tasks: Rich CLI Help Modernization

## Status Legend
- [ ] Not started
- [x] Complete
- [~] In progress
- [!] Blocked

---

## Complete File Inventory

### Group Commands (10 files - need RichGroup)

| File | Line | Subcommands | Docstring Size |
|------|------|-------------|----------------|
| graph.py | 12 | build, build-dfg, analyze, query, viz | ~150 lines |
| session.py | 22 | analyze, list, inspect, report, activity | ~100 lines |
| planning.py | 46 | (invoke_without_command) | ~200 lines |
| terraform.py | 16 | analyze, scan | ~80 lines |
| cfg.py | 12 | analyze, viz | ~100 lines |
| tools.py | 185 | (subcommands TBD) | ~50 lines |
| workflows.py | 20 | (subcommands TBD) | ~100 lines |
| metadata.py | 9 | (subcommands TBD) | ~50 lines |
| cdk.py | 16 | analyze | ~60 lines |
| graphql.py | 12 | (subcommands TBD) | ~80 lines |

### Standalone Commands (26 files - need RichCommand)

| File | Line | Docstring Size | Priority |
|------|------|----------------|----------|
| taint.py | 14 | ~200 lines | HIGH |
| manual.py | 1015 | ~150 lines + 16 entries | HIGH |
| full.py | 67 | ~100 lines | HIGH |
| index.py | 11 | ~150 lines (deprecation) | HIGH |
| detect_patterns.py | 11 | ~80 lines | HIGH |
| blueprint.py | 20 | ~50 lines | MEDIUM |
| refactor.py | 44 | ~100 lines | MEDIUM |
| query.py | 16 | ~80 lines | MEDIUM |
| deps.py | 15 | ~60 lines | MEDIUM |
| impact.py | 13 | ~60 lines | MEDIUM |
| explain.py | 78 | ~50 lines | MEDIUM |
| workset.py | 9 | ~40 lines | MEDIUM |
| deadcode.py | 16 | ~50 lines | LOW |
| context.py | 18 | ~40 lines | LOW |
| boundaries.py | 17 | ~60 lines | LOW |
| docker_analyze.py | 13 | ~40 lines | LOW |
| lint.py | 88 | ~30 lines | LOW |
| fce.py | 9 | ~40 lines | LOW |
| detect_frameworks.py | 16 | ~50 lines | LOW |
| docs.py | 11 | ~40 lines | LOW |
| rules.py | 16 | ~40 lines | LOW |
| setup.py | 14 | ~60 lines | LOW |
| ml.py | 10,398,617 | 3 commands, ~100 lines each | LOW |
| _archive.py | 15 | ~20 lines (hidden) | LOW |

---

## Phase 0: Infrastructure & Verification
> Build RichCommand, test with 1 file, verify pattern works

### Tasks
- [ ] **0.1** Create `RichCommand` class in `cli.py:140` (after RichGroup)
- [ ] **0.2** Create docstring section parser (in RichCommand class)
- [ ] **0.3** Test with `manual.py` only - add `cls=RichCommand`
- [ ] **0.4** Verify output: `aud manual --help` shows Rich formatting

### Verification Checkpoint 0
```bash
# Run these commands - all must show Rich formatting (colored output)
aud manual --help 2>&1 | head -10
# Expected: Rule line with "aud manual", colored sections

# If piped, should degrade gracefully (no ANSI codes)
aud manual --help | cat | head -10
# Expected: Plain text, no [bold] markup visible
```

### Exit Criteria
- [ ] RichCommand class exists in cli.py
- [ ] `aud manual --help` displays with Rich panels
- [ ] Non-TTY output degrades gracefully
- [ ] No errors or exceptions

---

## Phase 1: Batch 1 - Core Commands (5 files)
> Most visible commands users interact with daily

### Files in Batch
1. `manual.py:1015` - Update docstring + 16 EXPLANATIONS entries
2. `full.py:67` - Main pipeline command
3. `taint.py:14` - Security analysis (trim verbose docstring)
4. `index.py:11` - Deprecation notice (Rich warning panel)
5. `detect_patterns.py:11` - Security patterns

### Tasks
- [ ] **1.1** manual.py - Add `cls=RichCommand`, update docstring format
- [ ] **1.2** manual.py - Migrate 16 EXPLANATIONS to Rich markup (remove `markup=False` at line 1200)
- [ ] **1.3** full.py - Add `cls=RichCommand`, update to current 4-stage pipeline
- [ ] **1.4** taint.py - Add `cls=RichCommand`, trim from 200 to ~80 lines
- [ ] **1.5** index.py - Format deprecation as Rich warning panel
- [ ] **1.6** detect_patterns.py - Add `cls=RichCommand`, update docstring

### Verification Checkpoint 1
```bash
# All 5 commands should show Rich formatting
for cmd in "manual --help" "full --help" "taint-analyze --help" "index --help" "detect-patterns --help"; do
  echo "=== aud $cmd ==="
  aud $cmd 2>&1 | head -5
done

# Verify no crashes
aud manual taint  # Should show Rich-formatted explanation
aud full --help   # Should show 4-stage pipeline description
```

### Exit Criteria
- [ ] All 5 commands show Rich formatting
- [ ] `aud manual <topic>` renders with Rich panels
- [ ] No "aud index" references in docstrings (use "aud full")
- [ ] No crashes or encoding errors

---

## Phase 2: Batch 2 - Graph & Session Groups (2 files, 10 subcommands)
> Group commands need RichGroup + RichCommand for subcommands

### Files in Batch
1. `graph.py:12` - Group (5 subcommands: build, build-dfg, analyze, query, viz)
2. `session.py:22` - Group (5 subcommands: analyze, list, inspect, report, activity)

### Tasks
- [ ] **2.1** graph.py - Update group to use existing RichGroup pattern
- [ ] **2.2** graph.py - Update all 5 subcommand docstrings
- [ ] **2.3** session.py - Update group docstring
- [ ] **2.4** session.py - Update all 5 subcommand docstrings

### Verification Checkpoint 2
```bash
# Group help should show Rich formatting
aud graph --help
aud session --help

# Subcommand help should also be Rich
aud graph build --help
aud graph analyze --help
aud session analyze --help
aud session list --help
```

### Exit Criteria
- [ ] `aud graph --help` shows Rich panel
- [ ] All 5 graph subcommands have Rich help
- [ ] `aud session --help` shows Rich panel
- [ ] All 5 session subcommands have Rich help

---

## Phase 3: Batch 3 - Medium Priority Commands (8 files)
> Important analysis commands

### Files in Batch
1. `blueprint.py:20`
2. `refactor.py:44`
3. `query.py:16`
4. `deps.py:15`
5. `impact.py:13`
6. `explain.py:78`
7. `workset.py:9`
8. `deadcode.py:16`

### Tasks
- [ ] **3.1** blueprint.py - Add `cls=RichCommand`, update docstring
- [ ] **3.2** refactor.py - Add `cls=RichCommand`, trim verbose content
- [ ] **3.3** query.py - Add `cls=RichCommand`, document query syntax
- [ ] **3.4** deps.py - Add `cls=RichCommand`, document vuln-scan
- [ ] **3.5** impact.py - Add `cls=RichCommand`, add blast radius examples
- [ ] **3.6** explain.py - Add `cls=RichCommand`
- [ ] **3.7** workset.py - Add `cls=RichCommand`, add diff examples
- [ ] **3.8** deadcode.py - Add `cls=RichCommand`

### Verification Checkpoint 3
```bash
for cmd in blueprint refactor query deps impact explain workset deadcode; do
  echo "=== aud $cmd --help ==="
  aud $cmd --help 2>&1 | head -3
done
```

### Exit Criteria
- [ ] All 8 commands show Rich formatting
- [ ] No outdated content (aud index references, wrong paths)
- [ ] Examples are accurate and work

---

## Phase 4: Batch 4 - Remaining Groups (8 files)
> Less frequently used group commands

### Files in Batch
1. `planning.py:46` - Group
2. `terraform.py:16` - Group (2 subcommands)
3. `cfg.py:12` - Group (2 subcommands)
4. `tools.py:185` - Group
5. `workflows.py:20` - Group
6. `metadata.py:9` - Group
7. `cdk.py:16` - Group (1 subcommand)
8. `graphql.py:12` - Group

### Tasks
- [ ] **4.1** planning.py - Update group + any subcommands
- [ ] **4.2** terraform.py - Update group + analyze, scan subcommands
- [ ] **4.3** cfg.py - Update group + analyze, viz subcommands
- [ ] **4.4** tools.py - Update group
- [ ] **4.5** workflows.py - Update group
- [ ] **4.6** metadata.py - Update group
- [ ] **4.7** cdk.py - Update group + analyze subcommand
- [ ] **4.8** graphql.py - Update group

### Verification Checkpoint 4
```bash
for cmd in planning terraform cfg tools workflows metadata cdk graphql; do
  echo "=== aud $cmd --help ==="
  aud $cmd --help 2>&1 | head -3
done
```

### Exit Criteria
- [ ] All 8 group commands show Rich formatting
- [ ] Subcommands also have Rich help
- [ ] No crashes

---

## Phase 5: Batch 5 - Remaining Standalone (10 files)
> Low priority standalone commands

### Files in Batch
1. `context.py:18`
2. `boundaries.py:17`
3. `docker_analyze.py:13`
4. `lint.py:88`
5. `fce.py:9`
6. `detect_frameworks.py:16`
7. `docs.py:11`
8. `rules.py:16`
9. `setup.py:14`
10. `ml.py:10,398,617` (3 commands: learn, suggest, learn-feedback)

### Tasks
- [ ] **5.1** context.py - Add `cls=RichCommand`
- [ ] **5.2** boundaries.py - Add `cls=RichCommand`
- [ ] **5.3** docker_analyze.py - Add `cls=RichCommand`
- [ ] **5.4** lint.py - Add `cls=RichCommand`
- [ ] **5.5** fce.py - Add `cls=RichCommand`
- [ ] **5.6** detect_frameworks.py - Add `cls=RichCommand`
- [ ] **5.7** docs.py - Add `cls=RichCommand`
- [ ] **5.8** rules.py - Add `cls=RichCommand`
- [ ] **5.9** setup.py - Add `cls=RichCommand`
- [ ] **5.10** ml.py - Update all 3 commands (learn, suggest, learn-feedback)

### Verification Checkpoint 5
```bash
for cmd in context boundaries docker-analyze lint fce detect-frameworks docs rules setup-ai learn suggest learn-feedback; do
  echo "=== aud $cmd --help ==="
  aud $cmd --help 2>&1 | head -3
done
```

### Exit Criteria
- [ ] All 10 files (13 commands) show Rich formatting
- [ ] No crashes or encoding errors

---

## Phase 6: Batch 6 - Hidden/Internal + Final Polish (2 files + review)

### Files in Batch
1. `_archive.py:15` - Hidden command

### Tasks
- [ ] **6.1** _archive.py - Add `cls=RichCommand` (hidden but still should work)
- [ ] **6.2** Final consistency review - same section order across all commands
- [ ] **6.3** Verify all RELATED COMMANDS references are valid
- [ ] **6.4** Verify all examples work
- [ ] **6.5** Grammar/spelling check across all files
- [ ] **6.6** Test on Windows Terminal, CMD, PowerShell

### Final Verification
```bash
# Full test suite
echo "Testing all commands..."
aud --help  # Should show main dashboard

# Count Rich-formatted commands (should be 36+)
for file in theauditor/commands/*.py; do
  name=$(basename $file .py)
  if [[ $name != "__init__" && $name != "_archive" ]]; then
    aud $name --help 2>&1 | head -1
  fi
done

# Test manual entries
for topic in taint workset fce cfg impact pipeline severity patterns; do
  echo "=== aud manual $topic ==="
  aud manual $topic 2>&1 | head -3
done
```

### Exit Criteria
- [ ] ALL 36 command files have Rich formatting
- [ ] ALL 16 manual entries render with Rich
- [ ] No encoding errors on Windows
- [ ] No outdated content anywhere
- [ ] Consistent style across all commands

---

## Summary

| Phase | Files | Commands | Description |
|-------|-------|----------|-------------|
| 0 | 1 | 1 | Infrastructure + verify pattern |
| 1 | 5 | 5 | Core commands (manual, full, taint, index, detect-patterns) |
| 2 | 2 | 12 | Graph + Session groups with subcommands |
| 3 | 8 | 8 | Medium priority standalone |
| 4 | 8 | 8+ | Remaining groups with subcommands |
| 5 | 10 | 13 | Remaining standalone (incl. ml.py with 3 cmds) |
| 6 | 1 | 1 | Hidden + final polish |
| **Total** | **35** | **48+** | All commands covered |

Note: 35 files because `__init__.py` has no commands.
