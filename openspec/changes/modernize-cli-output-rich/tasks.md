# Tasks: CLI 2.0 Modernization

## Parallel Execution Plan

```
Phase 0: Infrastructure (SEQUENTIAL - must complete first)
    │
    ├── Creates RichCommand class
    └── All other phases depend on this

    ↓ GATE: Phase 0 complete

┌─────────┬─────────┬─────────┬─────────┬─────────┐
│ Term 1  │ Term 2  │ Term 3  │ Term 4  │ Term 5  │
│ Phase 1 │ Phase 2 │ Phase 3 │ Phase 4 │ Phase 5 │
│ 5 files │ 2 files │ 8 files │ 8 files │ 10 files│
│ 5 cmds  │ 10 cmds │ 8 cmds  │ 38 cmds │ 13 cmds │
└─────────┴─────────┴─────────┴─────────┴─────────┘
    │
    ↓ GATE: All 5 phases complete

Phase 6: Final Polish (SEQUENTIAL)
```

**Max parallel terminals: 5** (during Phases 1-5)

---

## Per-Command Deliverables Checklist

For EVERY command touched, deliver ALL of these:

- [ ] **Rich formatting** - `cls=RichCommand` on decorator
- [ ] **Content rewrite** - Accurate, AI-friendly docstring (not dev-dump)
- [ ] **Manual entry** - Create/update `aud manual <topic>` entry
- [ ] **Cross-references** - Help says "See: aud manual X", manual links back
- [ ] **Verification** - Examples actually work, descriptions match reality
- [ ] **AI-first language** - Written for AI to understand and execute

---

## Phase 0: Infrastructure (SEQUENTIAL)

**Terminal**: 1
**Duration**: Must complete before Phases 1-5 can start
**Files**: 1 (cli.py)

### Tasks
- [ ] **0.1** Create `RichCommand(click.Command)` class at `cli.py:140`
- [ ] **0.2** Implement `_parse_docstring()` for section extraction
- [ ] **0.3** Implement `_render_sections()` for all 11 section types
- [ ] **0.4** Implement `_render_options()` for clean option display
- [ ] **0.5** Test with `manual.py` - add `cls=RichCommand`
- [ ] **0.6** Verify: `aud manual --help` shows Rich output
- [ ] **0.7** Verify: `aud manual --help | cat` degrades gracefully (no ANSI)

### Exit Gate
```bash
aud manual --help  # Must show Rich panels
aud manual --help | cat  # Must show plain text, no [bold] visible
```

**DO NOT proceed to Phases 1-5 until Phase 0 passes.**

---

## Phase 1: Core Commands (PARALLEL)

**Terminal**: 1 of 5
**Files**: 5
**Commands**: 5 + manual entries

| File | Command | Manual Topic | Priority |
|------|---------|--------------|----------|
| manual.py | `aud manual` | (IS the manual) | HIGH |
| full.py | `aud full` | pipeline, full | HIGH |
| taint.py | `aud taint-analyze` | taint, security | HIGH |
| index.py | `aud index` | (deprecated notice) | HIGH |
| detect_patterns.py | `aud detect-patterns` | patterns, sast | HIGH |

### Per-File Tasks

**manual.py:1015**
- [ ] Add `cls=RichCommand` to decorator
- [ ] Rewrite docstring: what manual does, how to use, list topics
- [ ] Remove `markup=False` at line 1200 to enable Rich
- [ ] Migrate all 16 EXPLANATIONS entries to Rich markup
- [ ] Verify: `aud manual --list` shows topics
- [ ] Verify: `aud manual taint` renders with Rich panels

**full.py:67**
- [ ] Add `cls=RichCommand` to decorator
- [ ] Rewrite docstring: 4-stage pipeline, what each stage does
- [ ] Create/update manual entry: `pipeline`, `full`
- [ ] Add cross-ref: "See: aud manual pipeline"
- [ ] Verify: Examples work (`aud full --offline`)
- [ ] Verify: Describes current architecture (not old 10-phase)

**taint.py:14**
- [ ] Add `cls=RichCommand` to decorator
- [ ] Trim docstring from ~200 to ~80 lines (remove dev-dump)
- [ ] Create/update manual entry: `taint`
- [ ] Add cross-ref: "See: aud manual taint"
- [ ] Verify: Examples work
- [ ] Verify: Describes actual taint analysis behavior

**index.py:11**
- [ ] Add `cls=RichCommand` to decorator
- [ ] Rewrite as DEPRECATION WARNING (Rich warning panel)
- [ ] Point to `aud full` as replacement
- [ ] No manual entry needed (deprecated)

**detect_patterns.py:11**
- [ ] Add `cls=RichCommand` to decorator
- [ ] Rewrite docstring: what patterns detected, rule categories
- [ ] Create/update manual entry: `patterns`, `sast`
- [ ] Add cross-ref: "See: aud manual patterns"
- [ ] Verify: Examples work

### Verification Checkpoint
```bash
# All must show Rich formatting
aud manual --help
aud full --help
aud taint-analyze --help
aud detect-patterns --help

# Manual entries must exist and render
aud manual taint
aud manual pipeline
aud manual patterns

# Examples must actually work
aud full --help  # Should describe 4-stage pipeline
aud manual --list  # Should list all topics
```

---

## Phase 2: Graph & Session Groups (PARALLEL)

**Terminal**: 2 of 5
**Files**: 2
**Commands**: 10 (2 groups + 8 subcommands) + manual entries

| File | Group | Subcommands | Manual Topics |
|------|-------|-------------|---------------|
| graph.py | `aud graph` | build, build-dfg, analyze, query, viz | graph, callgraph, dependencies |
| session.py | `aud session` | analyze, report, inspect, activity, list | session, ml |

### Per-File Tasks

**graph.py:12**
- [ ] Group already uses RichGroup (verify)
- [ ] Add `cls=RichCommand` to all 5 subcommands
- [ ] Rewrite group docstring: what graph analysis does
- [ ] Rewrite each subcommand docstring
- [ ] Create/update manual entries: `graph`, `callgraph`, `dependencies`
- [ ] Add cross-refs in help and manual
- [ ] Verify: `aud graph build --help` shows Rich
- [ ] Verify: `aud graph query --symbol X` works

**session.py:22**
- [ ] Add `cls=RichGroup` to group (if not already)
- [ ] Add `cls=RichCommand` to all 5 subcommands
- [ ] Rewrite group docstring: session analysis purpose
- [ ] Rewrite each subcommand docstring
- [ ] Create/update manual entries: `session`, `ml`
- [ ] Add cross-refs
- [ ] Verify: All 5 subcommands show Rich

### Verification Checkpoint
```bash
# Group help
aud graph --help
aud session --help

# All subcommands
aud graph build --help
aud graph analyze --help
aud graph query --help
aud graph viz --help
aud session analyze --help
aud session report --help
aud session inspect --help
aud session activity --help
aud session list --help

# Manual entries
aud manual graph
aud manual session
```

---

## Phase 3: Medium Priority Standalone (PARALLEL)

**Terminal**: 3 of 5
**Files**: 8
**Commands**: 8 + manual entries

| File | Command | Manual Topic |
|------|---------|--------------|
| blueprint.py | `aud blueprint` | blueprint, architecture |
| refactor.py | `aud refactor` | refactor |
| query.py | `aud query` | query, sql |
| deps.py | `aud deps` | deps, dependencies |
| impact.py | `aud impact` | impact, blast-radius |
| explain.py | `aud explain` | explain |
| workset.py | `aud workset` | workset |
| deadcode.py | `aud deadcode` | deadcode |

### Per-File Tasks

For each of the 8 files:
- [ ] Add `cls=RichCommand` to decorator
- [ ] Rewrite docstring: AI-friendly, accurate, examples that work
- [ ] Create/update corresponding manual entry
- [ ] Add bidirectional cross-references
- [ ] Verify examples actually work
- [ ] Verify descriptions match current behavior

### Verification Checkpoint
```bash
for cmd in blueprint refactor query deps impact explain workset deadcode; do
  aud $cmd --help
done

# Manual entries
aud manual blueprint
aud manual workset
aud manual impact
```

---

## Phase 4: Remaining Groups (PARALLEL)

**Terminal**: 4 of 5
**Files**: 8
**Commands**: 38 (8 groups + 30 subcommands) + manual entries

| File | Group | Subcommands | Manual Topics |
|------|-------|-------------|---------------|
| planning.py | `aud planning` | 14 subcommands | planning |
| terraform.py | `aud terraform` | provision, analyze, report | terraform, iac |
| cfg.py | `aud cfg` | analyze, viz | cfg, control-flow |
| tools.py | `aud tools` | list, check, report | tools |
| workflows.py | `aud workflows` | analyze | workflows, cicd |
| metadata.py | `aud metadata` | churn, coverage, analyze | metadata, git |
| cdk.py | `aud cdk` | analyze | cdk, aws |
| graphql.py | `aud graphql` | build, query, viz | graphql |

### Per-File Tasks

**planning.py:46** (LARGEST - 14 subcommands)
- [ ] Add `cls=RichGroup` to group
- [ ] Add `cls=RichCommand` to all 14 subcommands:
  - init, show, list, add-phase, add-task, add-job
  - update-task, verify-task, archive, rewind
  - checkpoint, show-diff, validate, setup-agents
- [ ] Rewrite all docstrings
- [ ] Create manual entry: `planning`
- [ ] Verify all 14 subcommands

**terraform.py, cfg.py, tools.py, workflows.py, metadata.py, cdk.py, graphql.py**
- [ ] Same pattern: RichGroup + RichCommand for each subcommand
- [ ] Rewrite docstrings
- [ ] Create manual entries
- [ ] Verify

### Verification Checkpoint
```bash
for cmd in planning terraform cfg tools workflows metadata cdk graphql; do
  aud $cmd --help
  # Check first subcommand too
done

# Spot check subcommands
aud planning show --help
aud terraform analyze --help
aud cfg viz --help
```

---

## Phase 5: Remaining Standalone (PARALLEL)

**Terminal**: 5 of 5
**Files**: 10
**Commands**: 13 (ml.py has 3) + manual entries

| File | Command(s) | Manual Topic |
|------|------------|--------------|
| context.py | `aud context` | context |
| boundaries.py | `aud boundaries` | boundaries, trust |
| docker_analyze.py | `aud docker-analyze` | docker |
| lint.py | `aud lint` | lint |
| fce.py | `aud fce` | fce |
| detect_frameworks.py | `aud detect-frameworks` | frameworks |
| docs.py | `aud docs` | docs |
| rules.py | `aud rules` | rules |
| setup.py | `aud setup-ai` | setup |
| ml.py | `aud learn`, `aud suggest`, `aud learn-feedback` | ml, learning |

### Per-File Tasks

Same pattern for all:
- [ ] Add `cls=RichCommand` to decorator(s)
- [ ] Rewrite docstring(s)
- [ ] Create/update manual entry
- [ ] Add cross-references
- [ ] Verify examples work

### Verification Checkpoint
```bash
for cmd in context boundaries docker-analyze lint fce detect-frameworks docs rules setup-ai learn suggest learn-feedback; do
  aud $cmd --help
done

# Manual entries
aud manual fce
aud manual boundaries
aud manual setup
```

---

## Phase 6: Final Polish (SEQUENTIAL)

**Terminal**: 1
**Duration**: After all Phase 1-5 complete

### Tasks
- [ ] **6.1** `_archive.py` - Add `cls=RichCommand` (hidden command)
- [ ] **6.2** Cross-reference audit: every help mentions manual, every manual links commands
- [ ] **6.3** Consistency review: same section order across all commands
- [ ] **6.4** Example verification: run every example in every help
- [ ] **6.5** Manual coverage: verify every command has manual entry
- [ ] **6.6** Grammar/spelling sweep
- [ ] **6.7** Windows terminal test: Windows Terminal, CMD, PowerShell

### Final Verification
```bash
# Every command must show Rich
for file in theauditor/commands/*.py; do
  name=$(basename $file .py)
  if [[ $name != "__init__" && $name != "_archive" && $name != "config" ]]; then
    echo "=== $name ==="
    aud $name --help 2>&1 | head -3
  fi
done

# Every manual topic must render
aud manual --list
for topic in $(aud manual --list | grep -E '^\s+-' | tr -d ' -'); do
  aud manual $topic 2>&1 | head -3
done

# Sample examples must work
aud full --help  # Check pipeline description
aud taint-analyze --help  # Check examples
aud query --help  # Check query syntax
```

### Exit Criteria
- [ ] ALL 34 command files have Rich formatting
- [ ] ALL manual entries render with Rich
- [ ] ALL commands have corresponding manual entries
- [ ] ALL cross-references are bidirectional and valid
- [ ] ALL examples actually work
- [ ] NO outdated content (aud index refs, wrong paths, old architecture)
- [ ] NO encoding errors on Windows

---

## Summary

| Phase | Terminal | Files | Commands | Manual Entries | Notes |
|-------|----------|-------|----------|----------------|-------|
| 0 | Sequential | 1 | 1 | 0 | Infrastructure - GATE |
| 1 | Parallel 1 | 5 | 5 | ~5 | Core commands |
| 2 | Parallel 2 | 2 | 10 | ~4 | Graph + Session groups |
| 3 | Parallel 3 | 8 | 8 | ~8 | Medium standalone |
| 4 | Parallel 4 | 8 | 38 | ~8 | Remaining groups |
| 5 | Parallel 5 | 10 | 13 | ~10 | Remaining standalone |
| 6 | Sequential | 1 | 1 | 0 | Final polish - GATE |
| **Total** | **5 parallel** | **35** | **76+** | **~35** | |

**Execution time**:
- Phase 0: ~1 hour (infrastructure)
- Phases 1-5: Parallel (~2-4 hours each, running simultaneously)
- Phase 6: ~1-2 hours (final polish)
- **Total wall-clock: ~5-7 hours** (vs ~20+ hours sequential)
