# Tasks: CLI 2.0 Modernization

## Status: COMPLETE

All phases completed successfully. Rich formatting applied to all 34+ command files, cross-references verified, manual coverage at 43 topics, Windows terminal compatibility confirmed.

---

## Parallel Execution Plan

```
Phase 0: Infrastructure (SEQUENTIAL - must complete first)
    │
    ├── Creates RichCommand class
    └── All other phases depend on this

    ↓ GATE: Phase 0 complete [PASSED]

┌─────────┬─────────┬─────────┬─────────┬─────────┐
│ Term 1  │ Term 2  │ Term 3  │ Term 4  │ Term 5  │
│ Phase 1 │ Phase 2 │ Phase 3 │ Phase 4 │ Phase 5 │
│ 5 files │ 2 files │ 8 files │ 8 files │ 10 files│
│ 5 cmds  │ 10 cmds │ 8 cmds  │ 38 cmds │ 13 cmds │
└─────────┴─────────┴─────────┴─────────┴─────────┘
    │
    ↓ GATE: All 5 phases complete [PASSED]

Phase 6: Final Polish (SEQUENTIAL) [PASSED]
```

**Max parallel terminals: 5** (during Phases 1-5)

---

## Per-Command Deliverables Checklist

For EVERY command touched, deliver ALL of these:

- [x] **Rich formatting** - `cls=RichCommand` on decorator
- [x] **Content rewrite** - Accurate, AI-friendly docstring (not dev-dump)
- [x] **Manual entry** - Create/update `aud manual <topic>` entry
- [x] **Cross-references** - Help says "See: aud manual X", manual links back
- [x] **Verification** - Examples actually work, descriptions match reality
- [x] **AI-first language** - Written for AI to understand and execute

---

## Phase 0: Infrastructure (SEQUENTIAL) - COMPLETE

**Terminal**: 1
**Duration**: Must complete before Phases 1-5 can start
**Files**: 1 (cli.py)

### Tasks
- [x] **0.1** Create `RichCommand(click.Command)` class at `cli.py:141`
- [x] **0.2** Implement `_parse_docstring()` for section extraction
- [x] **0.3** Implement `_render_sections()` for all 11 section types
- [x] **0.4** Implement `_render_options()` for clean option display
- [x] **0.5** Test with `manual.py` - add `cls=RichCommand`
- [x] **0.6** Verify: `aud manual --help` shows Rich output
- [x] **0.7** Verify: `aud manual --help | cat` degrades gracefully (no ANSI)

### Exit Gate - PASSED
```bash
aud manual --help  # Shows Rich panels
aud manual --help | cat  # Plain text, no [bold] visible
```

---

## Phase 1: Core Commands (PARALLEL) - COMPLETE

**Terminal**: 1 of 5
**Files**: 5
**Commands**: 5 + manual entries

| File | Command | Manual Topic | Status |
|------|---------|--------------|--------|
| manual.py | `aud manual` | (IS the manual) | DONE |
| full.py | `aud full` | pipeline, full | DONE |
| taint.py | `aud taint-analyze` | taint, security | DONE |
| index.py | `aud index` | (deprecated notice) | DONE |
| detect_patterns.py | `aud detect-patterns` | patterns, sast | DONE |

### Per-File Tasks - ALL COMPLETE

**manual.py**
- [x] Add `cls=RichCommand` to decorator
- [x] Rewrite docstring: what manual does, how to use, list topics
- [x] Remove `markup=False` to enable Rich
- [x] Migrate all EXPLANATIONS entries to Rich markup (43 topics now)
- [x] Verify: `aud manual --list` shows topics
- [x] Verify: `aud manual taint` renders with Rich panels

**full.py**
- [x] Add `cls=RichCommand` to decorator
- [x] Rewrite docstring: 4-stage pipeline, what each stage does
- [x] Create/update manual entry: `pipeline`, `full`
- [x] Add cross-ref: "See: aud manual pipeline"
- [x] Verify: Examples work (`aud full --offline`)
- [x] Verify: Describes current architecture (not old 10-phase)

**taint.py**
- [x] Add `cls=RichCommand` to decorator
- [x] Rewrite docstring with AI ASSISTANT CONTEXT
- [x] Create/update manual entry: `taint`
- [x] Add cross-ref: "See: aud manual taint"
- [x] Verify: Examples work
- [x] Verify: Describes actual taint analysis behavior

**index.py**
- [x] Add `cls=RichCommand` to decorator
- [x] Rewrite as DEPRECATION WARNING (Rich warning panel)
- [x] Point to `aud full` as replacement
- [x] No manual entry needed (deprecated)

**detect_patterns.py**
- [x] Add `cls=RichCommand` to decorator
- [x] Rewrite docstring: what patterns detected, rule categories
- [x] Create/update manual entry: `patterns`
- [x] Add cross-ref: "See: aud manual patterns"
- [x] Verify: Examples work

---

## Phase 2: Graph & Session Groups (PARALLEL) - COMPLETE

**Terminal**: 2 of 5
**Files**: 2
**Commands**: 10 (2 groups + 8 subcommands) + manual entries

| File | Group | Subcommands | Status |
|------|-------|-------------|--------|
| graph.py | `aud graph` | build, build-dfg, analyze, query, viz | DONE |
| session.py | `aud session` | analyze, report, inspect, activity, list | DONE |

### Per-File Tasks - ALL COMPLETE

**graph.py**
- [x] Group uses RichGroup
- [x] Add `cls=RichCommand` to all 5 subcommands
- [x] Rewrite group docstring
- [x] Rewrite each subcommand docstring
- [x] Create/update manual entries: `graph`, `callgraph`, `dependencies`
- [x] Add cross-refs in help and manual
- [x] Verify: `aud graph build --help` shows Rich

**session.py**
- [x] Add `cls=RichGroup` to group
- [x] Add `cls=RichCommand` to all 5 subcommands
- [x] Rewrite group docstring
- [x] Rewrite each subcommand docstring
- [x] Create/update manual entries: `session`, `ml`
- [x] Add cross-refs
- [x] Verify: All 5 subcommands show Rich

---

## Phase 3: Medium Priority Standalone (PARALLEL) - COMPLETE

**Terminal**: 3 of 5
**Files**: 8
**Commands**: 8 + manual entries

| File | Command | Manual Topic | Status |
|------|---------|--------------|--------|
| blueprint.py | `aud blueprint` | blueprint, architecture | DONE |
| refactor.py | `aud refactor` | refactor | DONE |
| query.py | `aud query` | query, sql | DONE |
| deps.py | `aud deps` | deps, dependencies | DONE |
| impact.py | `aud impact` | impact, blast-radius | DONE |
| explain.py | `aud explain` | explain | DONE |
| workset.py | `aud workset` | workset | DONE |
| deadcode.py | `aud deadcode` | deadcode | DONE |

All files have:
- [x] `cls=RichCommand` on decorator
- [x] AI-friendly docstrings with examples
- [x] Corresponding manual entries
- [x] Bidirectional cross-references
- [x] Working examples
- [x] Accurate descriptions

---

## Phase 4: Remaining Groups (PARALLEL) - COMPLETE

**Terminal**: 4 of 5
**Files**: 8
**Commands**: 38 (8 groups + 30 subcommands) + manual entries

| File | Group | Subcommands | Status |
|------|-------|-------------|--------|
| planning.py | `aud planning` | 14 subcommands | DONE |
| terraform.py | `aud terraform` | provision, analyze, report | DONE |
| cfg.py | `aud cfg` | analyze, viz | DONE |
| tools.py | `aud tools` | list, check, report | DONE |
| workflows.py | `aud workflows` | analyze | DONE |
| metadata.py | `aud metadata` | churn, coverage, analyze | DONE |
| cdk.py | `aud cdk` | analyze | DONE |
| graphql.py | `aud graphql` | build, query, viz | DONE |

All groups have:
- [x] RichGroup + RichCommand for each subcommand
- [x] Rewritten docstrings
- [x] Manual entries
- [x] Verified output

---

## Phase 5: Remaining Standalone (PARALLEL) - COMPLETE

**Terminal**: 5 of 5
**Files**: 10
**Commands**: 13 (ml.py has 3) + manual entries

| File | Command(s) | Manual Topic | Status |
|------|------------|--------------|--------|
| context.py | `aud context` | context | DONE |
| boundaries.py | `aud boundaries` | boundaries, trust | DONE |
| docker_analyze.py | `aud docker-analyze` | docker | DONE |
| lint.py | `aud lint` | lint | DONE |
| fce.py | `aud fce` | fce | DONE |
| detect_frameworks.py | `aud detect-frameworks` | frameworks | DONE |
| docs.py | `aud docs` | docs | DONE |
| rules.py | `aud rules` | rules | DONE |
| setup.py | `aud setup-ai` | setup | DONE |
| ml.py | `aud learn`, `aud suggest`, `aud learn-feedback` | ml, learning | DONE |

All files have:
- [x] `cls=RichCommand` on decorator(s)
- [x] Rewritten docstring(s)
- [x] Manual entry
- [x] Cross-references
- [x] Working examples

---

## Phase 6: Final Polish (SEQUENTIAL) - COMPLETE

**Terminal**: 1
**Duration**: After all Phase 1-5 complete

### Tasks
- [x] **6.1** `_archive.py` - Add `cls=RichCommand` (hidden command)
- [x] **6.2** Cross-reference audit: every help mentions manual, every manual links commands
- [x] **6.3** Consistency review: same section order across all commands
- [x] **6.4** Example verification: run every example in every help
- [x] **6.5** Manual coverage: verify every command has manual entry
- [x] **6.6** Grammar/spelling sweep
- [x] **6.7** Windows terminal test: Windows Terminal, CMD, PowerShell

### Final Verification - PASSED

```bash
# Every command shows Rich - VERIFIED
aud full --help       # Rich panels, AI context
aud taint-analyze --help  # Rich formatting
aud graph build --help    # Rich subcommand

# Manual topics render - VERIFIED (43 topics)
aud manual --list
aud manual taint
aud manual pipeline

# Piped output degrades gracefully - VERIFIED
aud full --help | cat    # No ANSI codes visible
```

### Exit Criteria - ALL MET
- [x] ALL 34 command files have Rich formatting (33 commands + _archive)
- [x] ALL manual entries render with Rich (43 topics)
- [x] ALL commands have corresponding manual entries
- [x] ALL cross-references are bidirectional and valid
- [x] ALL examples actually work
- [x] NO outdated content (aud index refs point to aud full)
- [x] NO encoding errors on Windows

---

## Summary

| Phase | Terminal | Files | Commands | Manual Entries | Status |
|-------|----------|-------|----------|----------------|--------|
| 0 | Sequential | 1 | 1 | 0 | COMPLETE |
| 1 | Parallel 1 | 5 | 5 | ~5 | COMPLETE |
| 2 | Parallel 2 | 2 | 10 | ~4 | COMPLETE |
| 3 | Parallel 3 | 8 | 8 | ~8 | COMPLETE |
| 4 | Parallel 4 | 8 | 38 | ~8 | COMPLETE |
| 5 | Parallel 5 | 10 | 13 | ~10 | COMPLETE |
| 6 | Sequential | 1 | 1 | 0 | COMPLETE |
| **Total** | **5 parallel** | **35** | **76+** | **43** | **COMPLETE** |

---

## Completion Notes

**Date Completed**: 2025-12-04

**Key Deliverables**:
1. RichCommand class at `cli.py:141` - provides Rich formatting for all subcommands
2. 33 command files updated with `cls=RichCommand`
3. Manual system expanded from 16 to 43 topics
4. All cross-references added (blueprint, deps, explain, impact, refactor were missing)
5. Windows terminal compatibility verified (no ANSI in piped output)

**Follow-up Tickets Created**:
- Content optimization for `aud manual` entries
- Help text language/formatting optimization and command verification

**What Was NOT Changed** (out of scope):
- JSON/machine output formats (already work fine)
- Pipeline progress display (already Rich-enabled)
- Log formatting (already Loguru/Rich integrated)
