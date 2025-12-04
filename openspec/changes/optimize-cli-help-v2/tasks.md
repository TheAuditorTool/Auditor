# Tasks: CLI Help Content Optimization

## Execution Model

```
+----------+----------+----------+----------+----------+----------+
| Track 1  | Track 2  | Track 3  | Track 4  | Track 5  | Track 6  |
|   Core   |  Graph   | Security | Analysis |  Infra   | Plan/ML  |
| 5 files  | 4 files  | 5 files  | 6 files  | 7 files  | 6 files  |
+----------+----------+----------+----------+----------+----------+
     |         |         |         |         |         |
     +---------+---------+---------+---------+---------+
                              |
                    All 6 run in parallel
                              |
                    +-------------------+
                    |   Final Review    |
                    |   (Sequential)    |
                    +-------------------+
```

**Each track is 100% independent. No dependencies between tracks.**

---

## Pre-Work: Reference Materials (ALL TRACKS MUST READ)

Before touching ANY file, each AI team MUST read:

1. **Reference Implementation:**
   - `theauditor/commands/full.py:68-192` - Gold standard for CLI help content
   - Study the AI ASSISTANT CONTEXT format, section structure, examples

2. **RichCommand Parser:**
   - `theauditor/cli.py:141-350` - Understands which sections are recognized
   - Section headers: AI ASSISTANT CONTEXT, DESCRIPTION, EXAMPLES, COMMON WORKFLOWS, etc.

3. **AI ASSISTANT CONTEXT Template (design.md):**
   ```python
   AI ASSISTANT CONTEXT:
     Purpose: Single sentence describing what this accomplishes
     Input: Required files/databases with paths (e.g., .pf/repo_index.db)
     Output: What gets produced with paths (e.g., .pf/raw/analysis.json)
     Prerequisites: What must run first (use "aud full" not "aud index")
     Integration: How this fits in typical workflow
   ```

---

## Pre-Work: Verification Protocol (ALL TRACKS)

For EACH command file:

1. Run `aud <command> --help` to see current state
2. Run the command with test args to verify it works
3. Cross-reference docstring claims against implementation
4. Verify examples by running them

**Per-Command Deliverables Checklist:**
- [ ] AI ASSISTANT CONTEXT section present (with all 5 fields)
- [ ] No "aud index" references (use "aud full")
- [ ] All examples verified working
- [ ] Description matches actual behavior
- [ ] Prerequisites are accurate
- [ ] RELATED COMMANDS section present
- [ ] SEE ALSO references valid manual topics

---

## Track 1: Core Pipeline Commands

**AI Team 1 Assignment**
**Files:** 5
**Commands:** 5
**"aud index" refs to fix:** 19 (1 in taint.py, 18 in index.py for deprecation)

### Files to Process

| File | Command | Priority | "aud index" Refs | AI CONTEXT |
|------|---------|----------|------------------|------------|
| full.py | `aud full` | CRITICAL | 0 | EXISTS |
| taint.py | `aud taint-analyze` | HIGH | 1 (line 335) | EXISTS |
| detect_patterns.py | `aud detect-patterns` | HIGH | 0 | EXISTS |
| index.py | `aud index` | MEDIUM | 18 (deprecation OK) | MISSING |
| manual.py | `aud manual` | HIGH | 0 | EXISTS |

### Per-File Tasks

**full.py:68** - REFERENCE IMPLEMENTATION
- [ ] Verify this is the gold standard (no changes needed unless issues found)
- [ ] Study this file before modifying others

**taint.py:15**
- [ ] Fix line 335: "Run 'aud index' to rebuild" -> "Run 'aud full' to rebuild"
- [ ] Verify AI ASSISTANT CONTEXT is present and accurate

**detect_patterns.py:12**
- [ ] Verify AI ASSISTANT CONTEXT is present
- [ ] Verify examples work

**index.py:12** - NEEDS AI CONTEXT (deprecation-focused)
- [ ] ADD AI ASSISTANT CONTEXT with deprecation message:
  ```python
  AI ASSISTANT CONTEXT:
    Purpose: DEPRECATED - redirects to aud full for backwards compatibility
    Input: N/A (runs aud full instead)
    Output: N/A (runs aud full instead)
    Prerequisites: N/A
    Integration: DO NOT USE - always use 'aud full' or 'aud full --index' instead
  ```
- [ ] Keep all 18 "aud index" refs (they're part of deprecation documentation)

**manual.py:128**
- [ ] Verify AI ASSISTANT CONTEXT is present
- [ ] Verify --list shows all topics

### Track 1 Verification Checkpoint
```bash
# Should return only taint.py:335 and index.py lines
grep -rn "aud index" theauditor/commands/{full,taint,detect_patterns,index,manual}.py

# AI ASSISTANT CONTEXT check (index.py should be added)
for f in theauditor/commands/{full,taint,detect_patterns,index,manual}.py; do
  grep -q "AI ASSISTANT CONTEXT" "$f" || echo "MISSING: $f"
done
```

---

## Track 2: Graph/Flow Commands

**AI Team 2 Assignment**
**Files:** 4
**Commands:** 11 (1 standalone + 10 subcommands)
**"aud index" refs to fix:** 7

### Files to Process

| File | Group | Subcommands | "aud index" Refs | AI CONTEXT |
|------|-------|-------------|------------------|------------|
| graph.py | `aud graph` | build, build-dfg, analyze, query, viz | 4 (lines 26,48,67,356) | EXISTS |
| graphql.py | `aud graphql` | build, query, viz | 3 (lines 26,49,65) | EXISTS |
| cfg.py | `aud cfg` | analyze, viz | 0 | MISSING |
| fce.py | `aud fce` | (standalone) | 0 | EXISTS |

### Per-File Tasks

**graph.py** (5 subcommands)
- [ ] Fix line 26: "Prerequisites: aud index" -> "Prerequisites: aud full"
- [ ] Fix line 48: "aud index" -> "aud full"
- [ ] Fix line 67: "aud index" -> "aud full"
- [ ] Fix line 356: "Prerequisites: aud index" -> "Prerequisites: aud full"
- [ ] Verify graph build actually creates graphs.db

**graphql.py** (3 subcommands)
- [ ] Fix line 26: "Prerequisites: aud index" -> "Prerequisites: aud full"
- [ ] Fix line 49: "aud index" -> "aud full"
- [ ] Fix line 65: "aud index" -> "aud full"

**cfg.py** (2 subcommands) - NEEDS AI CONTEXT
- [ ] ADD AI ASSISTANT CONTEXT to group docstring (line 16):
  ```python
  AI ASSISTANT CONTEXT:
    Purpose: Analyze control flow graph complexity and detect unreachable code
    Input: .pf/repo_index.db (after aud full)
    Output: .pf/raw/cfg.json (complexity metrics), DOT/SVG diagrams
    Prerequisites: aud full (populates CFG data in database)
    Integration: Use after aud full to identify complex functions needing refactoring
  ```
- [ ] Verify complexity threshold works
- [ ] Verify dead code detection works

**fce.py**
- [ ] Verify AI ASSISTANT CONTEXT present
- [ ] Verify FCE explanation is accurate

### Track 2 Verification Checkpoint
```bash
grep -rn "aud index" theauditor/commands/{graph,graphql,cfg,fce}.py
# Should return nothing after fixes

grep "AI ASSISTANT CONTEXT" theauditor/commands/{graph,graphql,cfg,fce}.py
# Should find in all 4 files after adding to cfg.py
```

---

## Track 3: Security/IaC Commands

**AI Team 3 Assignment**
**Files:** 5
**Commands:** 7 (4 standalone + 3 subcommands)
**"aud index" refs to fix:** 21

### Files to Process

| File | Command | Subcommands | "aud index" Refs | AI CONTEXT |
|------|---------|-------------|------------------|------------|
| boundaries.py | `aud boundaries` | - | 1 (line 69) | EXISTS |
| docker_analyze.py | `aud docker-analyze` | - | 9 (lines 38,40,76,85,101,157,169,180,183) | EXISTS |
| workflows.py | `aud workflows` | analyze | 4 (lines 32,34,50,107) | EXISTS |
| terraform.py | `aud terraform` | provision, analyze, report | 5 (lines 28,30,52,97,236) | EXISTS |
| cdk.py | `aud cdk` | analyze | 3 (lines 31,55,116) | EXISTS |

### Per-File Tasks

**boundaries.py:18**
- [ ] Fix line 69: "Prerequisites: aud index" -> "Prerequisites: aud full"

**docker_analyze.py:14** (9 refs)
- [ ] Fix lines 38,40,76,85,101,157,169,180,183: all "aud index" -> "aud full"

**workflows.py:71** (4 refs)
- [ ] Fix lines 32,34,50,107: all "aud index" -> "aud full"

**terraform.py** (5 refs)
- [ ] Fix lines 28,30,52,97,236: all "aud index" -> "aud full"

**cdk.py** (3 refs)
- [ ] Fix lines 31,55,116: all "aud index" -> "aud full"

### Track 3 Verification Checkpoint
```bash
grep -rn "aud index" theauditor/commands/{boundaries,docker_analyze,workflows,terraform,cdk}.py
# Should return nothing after fixes
```

---

## Track 4: Code Analysis Commands

**AI Team 4 Assignment**
**Files:** 6
**Commands:** 6 (all standalone)
**"aud index" refs to fix:** 12

### Files to Process

| File | Command | "aud index" Refs | AI CONTEXT |
|------|---------|------------------|------------|
| query.py | `aud query` | 0 | MISSING |
| explain.py | `aud explain` | 0 | EXISTS |
| impact.py | `aud impact` | 4 (lines 114,139,210,282) | EXISTS |
| deadcode.py | `aud deadcode` | 8 (lines 43,78,94,149,160,170,183) | EXISTS |
| refactor.py | `aud refactor` | 4 (lines 90,151,196,208) | EXISTS |
| context.py | `aud context` | 0 | EXISTS |

### Per-File Tasks

**query.py:17** - NEEDS AI CONTEXT
- [ ] ADD AI ASSISTANT CONTEXT:
  ```python
  AI ASSISTANT CONTEXT:
    Purpose: Query code relationships from indexed database (symbols, callers, dependencies)
    Input: .pf/repo_index.db (after aud full)
    Output: Structured results (text, JSON, or tree format)
    Prerequisites: aud full (populates symbols, calls, refs tables)
    Integration: Use for precise lookups; use aud explain for comprehensive context
  ```
- [ ] Verify all --show-* flags work

**explain.py:79**
- [ ] Verify AI ASSISTANT CONTEXT present
- [ ] Verify symbol resolution works

**impact.py:14** (4 refs)
- [ ] Fix lines 114,139,210,282: all "aud index" -> "aud full"

**deadcode.py:17** (8 refs)
- [ ] Fix lines 43,78,94,149,160,170,183: all "aud index" -> "aud full"
- [ ] Note: line 78 has "aud index && aud deadcode" -> "aud full && aud deadcode" (or just "aud full" if deadcode runs in pipeline)

**refactor.py:45** (4 refs)
- [ ] Fix lines 90,151,196,208: all "aud index" -> "aud full"

**context.py:19**
- [ ] Verify AI ASSISTANT CONTEXT present

### Track 4 Verification Checkpoint
```bash
grep -rn "aud index" theauditor/commands/{query,explain,impact,deadcode,refactor,context}.py
# Should return nothing after fixes

grep "AI ASSISTANT CONTEXT" theauditor/commands/query.py
# Should find after adding
```

---

## Track 5: Infrastructure Commands

**AI Team 5 Assignment**
**Files:** 7
**Commands:** 10 (4 standalone + 6 subcommands)
**"aud index" refs to fix:** 5

### Files to Process

| File | Command | Subcommands | "aud index" Refs | AI CONTEXT |
|------|---------|-------------|------------------|------------|
| deps.py | `aud deps` | - | 0 | MISSING |
| tools.py | `aud tools` | list, check, report | 0 | MISSING |
| setup.py | `aud setup-ai` | - | 0 | EXISTS |
| workset.py | `aud workset` | - | 5 (lines 38,104,159,171,198) | EXISTS |
| rules.py | `aud rules` | - | 0 | EXISTS |
| lint.py | `aud lint` | - | 0 | EXISTS |
| docs.py | `aud docs` | - | 0 | EXISTS |

### Per-File Tasks

**deps.py:16** - NEEDS AI CONTEXT
- [ ] ADD AI ASSISTANT CONTEXT:
  ```python
  AI ASSISTANT CONTEXT:
    Purpose: Analyze dependencies for vulnerabilities, outdated packages, and upgrades
    Input: package.json, pyproject.toml, requirements.txt, Cargo.toml, Dockerfiles
    Output: .pf/raw/deps.json, .pf/raw/deps_latest.json, .pf/raw/vulnerabilities.json
    Prerequisites: None (reads manifest files directly, no database required)
    Integration: Run standalone or as part of aud full --offline pipeline
  ```

**tools.py** (3 subcommands) - NEEDS AI CONTEXT
- [ ] ADD AI ASSISTANT CONTEXT to group docstring (tools.py:186):
  ```python
  AI ASSISTANT CONTEXT:
    Purpose: Detect and verify installed analysis tools (linters, runtimes, scanners)
    Input: System PATH, .auditor_venv sandbox
    Output: Tool version information (stdout or .pf/raw/tools.json)
    Prerequisites: None (reads system state directly)
    Integration: Run before aud full to verify toolchain, or after setup-ai
  ```

**setup.py:15**
- [ ] Verify AI ASSISTANT CONTEXT present

**workset.py:10** (5 refs)
- [ ] Fix lines 38,104,159,171,198: all "aud index" -> "aud full"

**rules.py:17**
- [ ] Verify AI ASSISTANT CONTEXT present

**lint.py:89**
- [ ] Verify AI ASSISTANT CONTEXT present

**docs.py:12**
- [ ] Verify AI ASSISTANT CONTEXT present

### Track 5 Verification Checkpoint
```bash
grep -rn "aud index" theauditor/commands/{deps,tools,setup,workset,rules,lint,docs}.py
# Should return nothing after fixes

grep "AI ASSISTANT CONTEXT" theauditor/commands/{deps,tools}.py
# Should find in both after adding
```

---

## Track 6: Planning/ML Commands

**AI Team 6 Assignment**
**Files:** 6
**Commands:** 28 (3 standalone + 25 subcommands)
**"aud index" refs to fix:** 21 (5 in planning.py, 2 in blueprint.py, 14 in detect_frameworks.py)

### Files to Process

| File | Command | Subcommands | "aud index" Refs | AI CONTEXT |
|------|---------|-------------|------------------|------------|
| planning.py | `aud planning` | 14 subcommands | 5 (lines 61,71,80,86,122) | MISSING |
| session.py | `aud session` | 5 subcommands | 0 | EXISTS |
| ml.py | 3 commands | learn, suggest, learn-feedback | 0 | EXISTS |
| metadata.py | `aud metadata` | churn, coverage, analyze | 0 | EXISTS |
| blueprint.py | `aud blueprint` | - | 2 (lines 60,117) | EXISTS |
| detect_frameworks.py | `aud detect-frameworks` | - | 14 (see proposal Appendix A) | EXISTS |

### Per-File Tasks

**planning.py** (14 subcommands) - NEEDS AI CONTEXT
- [ ] ADD AI ASSISTANT CONTEXT to group docstring (planning.py:49):
  ```python
  AI ASSISTANT CONTEXT:
    Purpose: Database-centric task management with spec-based verification
    Input: .pf/planning.db (auto-created), YAML verification specs
    Output: .pf/planning.db updates, git snapshots, verification reports
    Prerequisites: aud full (for verify-task to query indexed code)
    Integration: Create plans, add tasks with specs, verify against indexed code
  ```
- [ ] Fix lines 61,71,80,86,122: all "aud index" -> "aud full"

**session.py** (5 subcommands)
- [ ] Verify AI ASSISTANT CONTEXT present
- [ ] Verify session analysis description

**ml.py** (3 separate commands)
- [ ] Verify AI ASSISTANT CONTEXT present for each

**metadata.py** (3 subcommands)
- [ ] Verify AI ASSISTANT CONTEXT present

**blueprint.py:21** (2 refs)
- [ ] Fix lines 60,117: "aud index" -> "aud full"

**detect_frameworks.py:12** (14 refs - MOST REFS)
- [ ] Fix ALL 14 occurrences (lines 3,23,31,51,58,67,71,112,119,123,133,136,141,145)
- [ ] All "aud index" -> "aud full"

### Track 6 Verification Checkpoint
```bash
grep -rn "aud index" theauditor/commands/{planning,session,ml,metadata,blueprint,detect_frameworks}.py
# Should return nothing after fixes

grep "AI ASSISTANT CONTEXT" theauditor/commands/planning.py
# Should find after adding
```

---

## Final Review Phase (Sequential - After All Tracks Complete)

### Cross-Track Consistency Check
- [ ] All commands use same section ordering (AI ASSISTANT CONTEXT after DESCRIPTION)
- [ ] All commands use same terminology (Prerequisites, not "Requires")
- [ ] All cross-references are valid (aud manual topics exist)
- [ ] No remaining "aud index" anywhere (except index.py deprecation notices)

### Full Verification
```bash
# Run on entire commands directory - MUST BE EMPTY (except index.py)
grep -rn "aud index" theauditor/commands/*.py | grep -v "index.py"
# Should return nothing

# Verify all AI ASSISTANT CONTEXT present (excluding non-command files)
for f in theauditor/commands/*.py; do
  case "$f" in
    *__init__*|*config*|*manual_lib*) continue ;;
  esac
  grep -q "AI ASSISTANT CONTEXT" "$f" || echo "MISSING: $f"
done
# Should return nothing (all files have AI ASSISTANT CONTEXT)
```

---

## Summary

| Track | Files | Commands | AI Context Gaps | "aud index" Fixes |
|-------|-------|----------|-----------------|-------------------|
| 1 | 5 | 5 | 1 (index.py) | 1 (taint.py) |
| 2 | 4 | 11 | 1 (cfg.py) | 7 |
| 3 | 5 | 7 | 0 | 21 |
| 4 | 6 | 6 | 1 (query.py) | 12 |
| 5 | 7 | 10 | 2 (deps, tools) | 5 |
| 6 | 6 | 28 | 1 (planning) | 21 |
| **Total** | **33** | **67** | **6** | **67** |

**Note:** 91 total "aud index" refs - 18 in index.py (deprecation OK) - 6 in manual_lib02.py (separate ticket) = 67 to fix
