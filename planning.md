# Planning System Foundation - Implementation Log
**Document Version:** 2.0
**Protocol:** TeamSOP v4.20
**Date Started:** 2025-11-01
**Last Updated:** 2025-11-01
**Status:** PREREQUISITE #1 COMPLETE | PERFORMANCE BREAKTHROUGH DISCOVERED

---

## Session Log: 2025-11-01 - Naming Convention Detection + Performance Fix

### What We Accomplished

**✅ Prerequisite #1 Complete: Naming Convention Detection**
- Implemented naming convention analysis in `blueprint.py`
- Query detects snake_case, camelCase, PascalCase across Python/JS/TS
- Output shows consistency percentages for functions and classes
- Working in production: `aud blueprint --structure` now shows naming conventions

**🚀 Critical Performance Breakthrough Discovered**
- Initial implementation: 180-264 seconds (3-4.4 minutes)
- Root cause identified: `WHERE path LIKE '%.py'` forces full table scan
- Solution: JOIN with files table + add `idx_files_ext` index
- **Final performance: 0.033 seconds (7,900x speedup)**

**Files Modified:**
1. `theauditor/indexer/schemas/core_schema.py` - Added `idx_files_ext` index to FILES table
2. `theauditor/commands/blueprint.py` - Rewrote naming convention query to use JOIN pattern
3. `regex_perf.md` (NEW) - Comprehensive documentation of the performance issue

### Critical Lessons Learned

**Query Optimization Pattern Discovered:**
```
❌ BAD:  WHERE path LIKE '%.py'           (180s - full table scan)
✅ GOOD: JOIN files ON path WHERE ext='.py' (0.033s - indexed lookup)
```

**This pattern likely affects:**
- All security pattern rules (JWT, SQL injection detection)
- Taint analysis source/sink discovery
- Track B pattern detection
- Any code filtering by file extension

**Architecture Insight**: The `files.ext` column was ALREADY IN THE SCHEMA, just missing the index. We weren't using our own infrastructure correctly.

### How It Works Now

```bash
# This query runs in 0.033 seconds (was 180-264s):
aud blueprint --structure

# Output shows:
Code Style Analysis (Naming Conventions):
  Python:
    Functions: snake_case (99.9% consistency)
    Classes: PascalCase (99.5% consistency)
  Javascript:
    Functions: camelCase (88.5% consistency)
    Classes: PascalCase (100.0% consistency)
```

**Query Pattern (from blueprint.py:246-286):**
```sql
SELECT COUNT(*) FROM symbols s
JOIN files f ON s.path = f.path    -- ← Uses idx_files_ext index
WHERE f.ext = '.py'                -- ← Indexed filter (fast)
  AND s.type = 'function'
  AND s.name REGEXP '^[a-z_].*$'   -- ← Regex only on filtered set
```

### Handoff Notes for Future Me

**If you're continuing this work:**

1. **Performance audit needed**: Check all queries in `theauditor/rules/` and `theauditor/taint/` for the `LIKE '%'` anti-pattern. See `regex_perf.md` for the full pattern.

2. **Prerequisite #2 next**: Architectural precedent detection. Should use similar query optimization (JOIN with files, use indexes).

3. **Database regenerated**: The `aud index` command now creates `idx_files_ext` automatically. Old databases won't have it until reindexed.

4. **Testing**: Direct query test at `tmp/test_naming_performance.py` - run this to verify sub-second performance on any machine.

**Key Files to Understand:**
- `theauditor/indexer/schema.py` - Merges all table schemas (core, python, node, etc)
- `theauditor/indexer/schemas/core_schema.py` - FILES table definition with new index
- `theauditor/indexer/database/core_database.py` - add_file() method that populates FILES table
- `theauditor/commands/blueprint.py` - _get_naming_conventions() function (lines 241-304)

**Schema Architecture:**
- 150 tables total in repo_index.db
- core_schema.py → python_schema.py → node_schema.py → etc
- All merged by schema.py into single TABLES registry
- Database regenerated fresh on every `aud index` (no migrations)

---

## Session Log: 2025-11-02 - Architectural Precedent Detection (Task 1.2)

### What We Accomplished

**✅ Prerequisite #2 Progress: Database Analysis Complete**
- Discovered plugin loader patterns can be detected from repo_index.db refs table
- Found 16 architectural precedents in TheAuditor codebase
- Resolved data format ambiguity: refs table stores BOTH file paths and module paths
- Confirmed NO import resolution needed for precedent detection
- Documented findings in `architectural_precedent_findings.md`

**🔍 Critical Database Discovery**
- refs table has TWO import formats:
  1. File paths: `theauditor/commands/init.py` (slash notation)
  2. Module paths: `schemas.core_schema` (dot notation)
- Python `from X import Y` stored as kind='from' (NOT kind='import')
- Can group by prefix/directory to find plugin loader patterns
- repo_index.db is SUFFICIENT (no need for graphs.db dependency)

**Database Comparison:**
- repo_index.db: 1,979 refs from theauditor/* (43.3% of total imports)
- graphs.db: 2,474 import edges (100% coverage)
- **Decision**: Use repo_index.db (always available, sufficient data)

### Discovered Patterns (Top 5)

1. **cli.py → commands/ (38 files)** - Central command loader
2. **schema.py → schemas/ (9 modules)** - Schema aggregator
3. **commands/graph.py → graph/ (6 files)** - Graph subsystem loader
4. **commands/graphql.py → graphql/ (3 files)** - GraphQL subsystem loader
5. **insights/__init__.py → insights/ (5 files)** - Plugin loader with __init__.py aggregator

### Key Technical Resolution

**Original Concern:**
> "refs table has module NAMES, not resolved FILE PATHS. Without import resolution, any query is just a guess."

**Resolution:**
- Don't need to know if `schemas.core_schema` resolves to `theauditor/indexer/schemas/core_schema.py`
- Only need to know: "schema.py imports 9 modules with common prefix `schemas.*`"
- The PREFIX GROUPING is the precedent, not the resolved paths
- This works for user projects too: detect patterns without knowing exact file locations

### Implementation Status

**Working Query (repo_index.db):**
```python
# Detect plugin loader patterns
cursor.execute('''
    SELECT src, value
    FROM refs
    WHERE src LIKE 'theauditor/%'
      AND kind IN ('import', 'from')
''')

# Group by (consumer, directory/prefix)
# Extract directory from file paths or prefix from module paths
# Filter for 3+ imports from same directory/prefix
```

**Next Steps:**
1. ⬜ Find refactor candidates (large files with domain clusters)
2. ⬜ Match candidates to precedents
3. ⬜ Implement in blueprint.py
4. ⬜ Test output in `aud blueprint --structure`

**Files Created:**
- `architectural_precedent_findings.md` (NEW) - Complete analysis and findings

### Handoff Notes

**Database Formats to Handle:**
```python
# Format 1: File paths (from cli.py)
'theauditor/commands/init.py'     → directory: 'commands'
'theauditor/commands/blueprint.py' → directory: 'commands'

# Format 2: Module paths (from schema.py)
'schemas.core_schema'      → prefix: 'schemas'
'schemas.python_schema'    → prefix: 'schemas'

# Format 3: Nested modules (from commands/graph.py)
'theauditor.graph.builder' → prefix: 'graph' (2nd-level)
```

**Query Performance:**
- Precedent detection: <0.1 seconds (tested on 1,979 refs)
- No regex, no file reads, pure database queries
- Scales to any codebase size

---

## Executive Summary

**Objective:** Build AI agent system for `aud planning` that enables autonomous, query-driven plan generation with zero hallucination.

**Problem:** Current AI workflow relies on manual file reading, guessing structure, and hallucinating patterns instead of querying indexed database facts.

**Solution:** Create agent workflow system that forces blueprint → query → context → synthesis workflow, anchored in database truth.

**Prerequisites:** 4 missing capabilities (1 complete, 3 remaining)

**Status:**
- ✅ Prerequisite #1: Naming convention detection (COMPLETE)
- 🔄 Prerequisite #2: Architectural precedent detection (IN PROGRESS - database analysis complete, implementation pending)
- ⬜ Prerequisite #3: aud refactor storage/exposure (TODO)
- ⬜ Prerequisite #4: Framework detection exposure (TODO)

---

## Part 1: Verification Phase (Current State Analysis)

### Hypothesis 1: Database contains all necessary data for planning
**Verification:** ❌ PARTIAL

**Evidence from repo_index.db inspection:**
```python
# Checked 150 tables in repo_index.db (v2.0 schema)
# CONFIRMED existing:
✅ frameworks table (express, next, flask detected with versions)
✅ python_orm_models table (53 models indexed)
✅ python_pytest_fixtures table (34 fixtures)
✅ findings_consolidated table (ARCHITECTURAL_HOTSPOT with churn data)
✅ files table with ext column + idx_files_ext index (ADDED 2025-11-01)

# IMPLEMENTED:
✅ Naming convention tracking (snake_case vs camelCase) - Added to blueprint.py

# STILL MISSING:
⚠️ Architectural precedent detection (data found in refs table, implementation pending)
❌ Refactor history storage (aud refactor results not persisted)
❌ Blueprint framework exposure (data exists but not shown)
```

**Location:** `.pf/repo_index.db` (91MB, 151 tables)

---

### Hypothesis 2: aud blueprint exposes necessary data for AI planning
**Verification:** ⚠️ IMPROVING (was INSUFFICIENT)

**Evidence from `aud blueprint --structure` output:**
```
Current output shows:
✅ File counts by directory/language
✅ Symbol counts by type
✅ Token estimates
✅ Naming convention analysis (ADDED 2025-11-01) - Shows consistency scores

Still missing from output:
❌ Framework detection results (data exists in DB, not shown)
❌ Hotspot/churn data (exists in findings_consolidated, not shown)
❌ ORM model inventory (exists in DB, not shown)
❌ Architectural precedents (not calculated)
```

**Location:** `theauditor/commands/blueprint.py:1-500`

---

### Hypothesis 3: aud refactor stores results for planning reference
**Verification:** ❌ FALSE

**Evidence from database schema check:**
```python
# Searched for refactor-related tables
refactor_tables = []  # No tables found
migration_tables = []  # No tables found

# aud refactor runs migration checks but doesn't persist
```

**Location:** `theauditor/commands/refactor.py` (implementation exists, no storage)

---

### Hypothesis 4: Agent system exists for triggering workflows
**Verification:** ❌ MISSING

**Evidence from filesystem check:**
```bash
# Checked for agent infrastructure
❌ No .theauditor_tools/agents/ directory
❌ No shipped_agents/ in codebase
❌ No agent trigger system in aud planning init
❌ No AGENTS.md modification logic
```

**Conclusion:** Entire agent infrastructure must be built from scratch.

---

## Part 2: Root Cause Analysis

### Surface Problem
AI generates plans by reading files manually, guessing structure, hallucinating patterns instead of querying database.

### Problem Chain
1. TheAuditor indexes code into repo_index.db (91MB of structured facts)
2. AI has aud query/blueprint/context commands available
3. **BUT:** AI doesn't know WHEN to run these commands
4. **BECAUSE:** No agent workflow system forces correct sequence
5. **RESULT:** AI defaults to file reading, makes assumptions, hallucinates

### Actual Root Cause
**Missing agent workflow system** that:
- Triggers on keywords ("refactor", "plan", "split")
- Forces blueprint → query → context sequence
- Prevents file reading, enforces database queries
- Anchors all decisions in query results

### Why This Happened
**Design Decision:** Planning system (aud planning) was built with YAML verification specs, but agent orchestration layer was never implemented.

**Missing Component:** `.theauditor_tools/agents/` workflow files + trigger system

---

## Part 3: Implementation Prerequisites (4 Required Capabilities)

### Prerequisite #1: Naming Convention Detection ✅ COMPLETE

**Status:** ✅ IMPLEMENTED (2025-11-01)

**What:** Detect and report code naming conventions (snake_case vs camelCase) across Python and Node codebases.

**Why Needed:** AI hallucinates naming style, causing API contract mismatches (backend snake_case vs frontend camelCase).

**Implementation:** Option C (blueprint integration) - CHOSEN & COMPLETED

**Location:** `theauditor/commands/blueprint.py:241-304`

**How It Works:**
```python
def _get_naming_conventions(cursor) -> Dict:
    """Analyze naming conventions using optimized SQL JOIN."""

    # CRITICAL: Uses JOIN with files table for performance
    # Before: WHERE path LIKE '%.py' (180+ seconds)
    # After: JOIN files WHERE ext = '.py' (0.033 seconds)

    cursor.execute("""
        SELECT
            -- Count matches for each pattern per language
            SUM(CASE WHEN f.ext = '.py' AND s.name REGEXP '^[a-z_]...'
                THEN 1 ELSE 0 END) AS py_snake,
            ...
        FROM symbols s
        JOIN files f ON s.path = f.path  -- Uses idx_files_ext
        WHERE s.type IN ('function', 'class')
    """)

    # Returns structured results with consistency percentages
```

**Performance:**
- Query time: 0.033 seconds
- Speedup vs naive approach: 7,900x
- Index used: `idx_files_ext` (added to core_schema.py)

**Output Format (Actual):**
```
Code Style Analysis (Naming Conventions):

  Python:
    Functions: snake_case (99.9% consistency)
    Classes: PascalCase (99.5% consistency)

  Javascript:
    Functions: camelCase (88.5% consistency)
    Classes: PascalCase (100.0% consistency)

  Typescript:
    Functions: camelCase (22.2% consistency)
    Classes: PascalCase (100.0% consistency)
```

**Data Source:** `symbols` table (55,603 symbols) + `files` table (477 files)

**Files Modified:**
1. `theauditor/indexer/schemas/core_schema.py:37-39` - Added index
2. `theauditor/commands/blueprint.py:241-336` - Implemented detection + result formatting
3. `regex_perf.md` - Documented the performance pattern for future work

---

### Prerequisite #2: Architectural Precedent Detection

**What:** Detect file/directory split patterns to guide refactoring decisions.

**Why Needed:** AI invents new split patterns instead of following existing precedents (e.g., schemas/ already domain-split, storage.py should follow).

**Current State:**
- Data exists: File paths indexed in repo_index.db
- Detection: ❌ Not implemented

**Where to Build:**
```
Location: theauditor/analysis/precedent_analyzer.py (NEW FILE)
Called by: theauditor/commands/blueprint.py:150-200
```

**Algorithm:**
```python
# Pseudo-code for precedent detection
def detect_split_precedents(root_path):
    precedents = []

    # Find directories with multiple similar files
    for dir_path in get_directories(root_path):
        files = get_files_in_dir(dir_path)

        if len(files) > 3:  # Candidate for split pattern
            # Analyze file naming patterns
            patterns = extract_naming_patterns(files)

            if patterns:
                precedents.append({
                    'directory': dir_path,
                    'split_type': infer_split_type(patterns),
                    'modules': [f.stem for f in files],
                    'pattern': describe_pattern(patterns),
                    'file_count': len(files),
                    'avg_loc': calculate_avg_loc(files)
                })

    return precedents

def infer_split_type(patterns):
    # Heuristics:
    # - *_schema.py → domain split
    # - *_extractor.py → functionality split
    # - *_handler.py → handler split
    pass
```

**Output Format:**
```json
{
  "split_precedents": [
    {
      "directory": "theauditor/indexer/schemas/",
      "split_type": "domain",
      "modules": ["core_schema", "python_schema", "node_schema", "infrastructure_schema"],
      "pattern": "Language/framework domain separation",
      "file_count": 5,
      "avg_loc": 320,
      "similar_candidates": [
        {
          "file": "theauditor/indexer/storage.py",
          "loc": 2127,
          "reason": "Monolithic file with similar domain patterns (_store_python_*, _store_react_*)"
        }
      ]
    }
  ]
}
```

**Data Source:** File system structure + symbols table for handler/function patterns

---

### Prerequisite #3: aud refactor Storage & Exposure

**What:** Persist aud refactor analysis results and expose in blueprint.

**Why Needed:** AI needs to verify refactor safety, check migration completeness before planning.

**Current State:**
- aud refactor: ✅ Runs migration checks
- Storage: ❌ Results not persisted
- Exposure: ❌ Not shown in blueprint

**Where to Build:**

**Part A: Storage**
```
Location: theauditor/commands/refactor.py:500-600 (add persistence)
Schema: New table "refactor_history"
  - id INTEGER PRIMARY KEY
  - timestamp TEXT
  - target_file TEXT
  - refactor_type TEXT (split, rename, consolidate)
  - migrations_found INTEGER
  - migrations_complete INTEGER
  - schema_consistent BOOLEAN
  - validation_status TEXT
  - details_json TEXT
```

**Part B: Exposure**
```
Location: theauditor/commands/blueprint.py:300-350
Query: refactor_history table
Show: Recent refactors, completion status, safety indicators
```

**Implementation:**
```python
# In refactor.py, after analysis completes:
def store_refactor_results(target_file, analysis_results):
    conn = sqlite3.connect('.pf/repo_index.db')
    c = conn.cursor()

    c.execute("""
        INSERT INTO refactor_history
        (timestamp, target_file, refactor_type, migrations_found,
         migrations_complete, schema_consistent, validation_status, details_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        target_file,
        analysis_results['type'],
        analysis_results['migrations_found'],
        analysis_results['migrations_complete'],
        analysis_results['schema_consistent'],
        analysis_results['status'],
        json.dumps(analysis_results['details'])
    ))

    conn.commit()
    conn.close()
```

**Output in Blueprint:**
```json
{
  "refactor_history": {
    "recent": [
      {
        "file": "schemas/",
        "date": "2024-10-15",
        "type": "domain_split",
        "status": "success",
        "migrations_complete": true
      }
    ],
    "pending": [],
    "warnings": []
  }
}
```

---

### Prerequisite #4: Framework Exposure in Blueprint

**What:** Show framework detection results in aud blueprint output.

**Why Needed:** AI guesses libraries (joi vs zod), needs to see what's actually detected.

**Current State:**
- Data exists: ✅ `frameworks` table populated
- Exposure: ❌ Not shown in blueprint output

**Where to Build:**
```
Location: theauditor/commands/blueprint.py:100-150
Query: frameworks table
```

**Implementation:**
```python
# In blueprint.py, add framework section:
def show_frameworks(format='text'):
    conn = sqlite3.connect('.pf/repo_index.db')
    c = conn.cursor()

    c.execute("""
        SELECT language, framework, version, COUNT(*) as usage_count
        FROM frameworks
        GROUP BY framework, language
        ORDER BY usage_count DESC
    """)

    results = c.fetchall()

    if format == 'json':
        return {
            'frameworks': [
                {
                    'language': row[0],
                    'name': row[1],
                    'version': row[2],
                    'files': row[3]
                }
                for row in results
            ]
        }
    else:
        # Text output
        print("Framework Detection:")
        for row in results:
            print(f"  {row[1]} v{row[2]} ({row[0]}) - {row[3]} files")
```

**Output Format:**
```json
{
  "frameworks": {
    "backend": [
      {"name": "Flask", "version": "2.3.0", "files": 12},
      {"name": "SQLAlchemy", "version": "2.0.0", "files": 8}
    ],
    "frontend": [
      {"name": "React", "version": "18.2.0", "files": 45},
      {"name": "Next.js", "version": "14.0.0", "files": 23}
    ],
    "validation": [
      {"name": "zod", "version": "3.22.0", "files": 15},
      {"name": "marshmallow", "version": "3.19.0", "files": 8}
    ]
  }
}
```

---

## Part 4: Agent System Architecture (After Prerequisites)

### Phase 1: Agent Workflow Files

**Structure:**
```
TheAuditor/
├── shipped_agents/              # NEW DIRECTORY
│   ├── planning_workflow.md     # Main orchestrator
│   ├── refactoring_workflow.md  # Refactor-specific
│   ├── security_workflow.md     # Security planning
│   └── greenfield_workflow.md   # New features
```

**Installation Flow:**
```
1. User runs: aud setup-ai --target .
2. venv_install.py copies:
   shipped_agents/*.md → .auditor_venv/.theauditor_tools/agents/
3. User runs: aud planning init
4. Command inserts trigger into root AGENTS.md and CLAUDE.md:
   <!-- PLANNING:START -->
   When keywords: refactor, plan, split, migrate
   Read: @/.theauditor_tools/agents/planning_workflow.md
   <!-- PLANNING:END -->
```

**Workflow File Format (planning_workflow.md):**
```markdown
# Planning Workflow - AI Instructions
Protocol: TeamSOP v4.20

## MANDATORY SEQUENCE (No Skipping)

### Step 1: Foundation - Run aud blueprint
REQUIRED: Always run before planning
PURPOSE: Understand architecture, find precedents

Commands:
$ aud blueprint --structure
$ aud blueprint --frameworks
$ aud blueprint --graph

OUTPUT: Store results for Step 2

### Step 2: Intelligence - Use blueprint to inform queries
BASED ON: Step 1 output
REQUIRED: Query patterns identified in blueprint

Commands:
$ aud query --file <target> --show-functions
$ aud query --symbol "<pattern>" --format json

OUTPUT: Actual counts, patterns

### Step 3: Conditional Analysis
IF security-related: Run aud context --security-rules
IF refactor-heavy: Run aud refactor --verify
IF greenfield: Find analogous patterns

### Step 4: Synthesis
ANCHOR: All decisions in Steps 1-3 query results
FORBIDDEN: File reading, guessing, hallucination
OUTPUT: Human-readable plan + YAML specs

## Prime Directives (TeamSOP v4.20)
- VERIFY EVERYTHING, ASSUME NOTHING
- Use queries as TRUTH SOURCE
- Chain facts: Step N uses Step N-1 output
- No hallucination: All counts from queries
```

---

## Part 5: Implementation Roadmap

### Phase 1: Prerequisites (Build Foundation)
**Estimated:** 4-6 hours

**Task 1.1:** Naming Convention Detection
- [ ] Add naming analyzer to blueprint.py:200-300
- [ ] Query symbols table, calculate patterns
- [ ] Output in --structure mode
- [ ] Test on TheAuditor + fixture projects

**Task 1.2:** Architectural Precedent Detection
- [ ] Create precedent_analyzer.py (new file)
- [ ] Implement split pattern detection algorithm
- [ ] Integrate into blueprint.py:150-200
- [ ] Test on schemas/ directory (known precedent)

**Task 1.3:** aud refactor Storage
- [ ] Create refactor_history table schema
- [ ] Add persistence to refactor.py:500-600
- [ ] Store results after analysis runs
- [ ] Test with existing fixtures

**Task 1.4:** Framework Exposure
- [ ] Add framework query to blueprint.py:100-150
- [ ] Format output (text + JSON)
- [ ] Test on projects with known frameworks

---

### Phase 2: Agent Infrastructure (Build Orchestration)
**Estimated:** 2-3 hours

**Task 2.1:** Create Shipped Agents
- [ ] Write shipped_agents/planning_workflow.md
- [ ] Write shipped_agents/refactoring_workflow.md
- [ ] Write shipped_agents/security_workflow.md
- [ ] Write shipped_agents/greenfield_workflow.md

**Task 2.2:** Installation Integration
- [ ] Modify venv_install.py (copy agents to toolbox)
- [ ] Test: aud setup-ai --target .

**Task 2.3:** Trigger System
- [ ] Implement AGENTS.md header insertion
- [ ] Add to aud planning init command
- [ ] Safe insertion (check for existing triggers)
- [ ] Test on clean + existing projects

---

### Phase 3: Testing & Validation
**Estimated:** 2 hours

**Task 3.1:** End-to-End Workflow Test
- [ ] Fresh project: "refactor storage.py"
- [ ] Verify: blueprint runs first
- [ ] Verify: queries execute automatically
- [ ] Verify: plan anchored in query results
- [ ] Verify: zero hallucination

**Task 3.2:** Edge Cases
- [ ] Project with no precedents
- [ ] Project with mixed conventions
- [ ] Project with incomplete refactors
- [ ] Project with no frameworks detected

---

## Part 6: Anchoring in Existing Code

### Existing Infrastructure to Leverage

**1. Database Schema:**
```
Location: theauditor/indexer/schemas/*.py
Pattern: Domain-split schema files (precedent for new tables)
Usage: Add refactor_history table following existing patterns
```

**2. Blueprint Command:**
```
Location: theauditor/commands/blueprint.py:1-500
Pattern: Drill-down modes (--structure, --graph, --security)
Usage: Add --frameworks mode, integrate naming/precedent detection
```

**3. Query Command:**
```
Location: theauditor/commands/query.py:1-400
Pattern: Database queries with JSON output
Usage: Reference for consistent query patterns
```

**4. venv_install.py:**
```
Location: theauditor/utils/venv_install.py:1-300
Pattern: Installation and setup logic
Usage: Add agent file copying to existing setup flow
```

---

## Part 7: Risk Analysis & Mitigation

### Risk 1: Schema Changes Break Existing Code
**Likelihood:** Low
**Impact:** High
**Mitigation:**
- Add refactor_history as optional table
- Graceful degradation if table doesn't exist
- No changes to existing tables

### Risk 2: Blueprint Performance Degradation
**Likelihood:** Medium
**Impact:** Low
**Mitigation:**
- Naming/precedent detection are opt-in queries
- Cache results per session
- Lazy load (only run when needed)

### Risk 3: Agent Workflows Don't Trigger
**Likelihood:** Medium
**Impact:** High
**Mitigation:**
- Explicit user documentation
- Test trigger keywords extensively
- Fallback to manual instructions if AGENTS.md missing

---

## Part 8: Success Criteria

### Must-Have (P0)
- [ ] aud blueprint shows frameworks (from DB)
- [ ] aud blueprint shows naming conventions (calculated)
- [ ] aud blueprint shows split precedents (calculated)
- [ ] aud refactor stores results in refactor_history table
- [ ] Agent workflow files shipped in codebase
- [ ] aud planning init inserts triggers into AGENTS.md

### Should-Have (P1)
- [ ] End-to-end workflow: "refactor X" → blueprint → query → plan
- [ ] Zero hallucination in generated plans
- [ ] All decisions anchored in query results

### Nice-to-Have (P2)
- [ ] Multiple agent workflows (security, greenfield)
- [ ] Agent versioning system
- [ ] Performance optimizations

---

## Part 9: Open Questions for Architect Review

**Question 1:** Naming convention detection - Option A (extractor), B (post-analysis), or C (blueprint)?
**Recommendation:** Option C (blueprint integration) - fastest, no schema changes

**Question 2:** Should refactor_history be in repo_index.db or separate planning.db?
**Recommendation:** repo_index.db - keeps all analysis data together

**Question 3:** Agent trigger keywords - start minimal or comprehensive?
**Recommendation:** Start minimal (refactor, plan, split, migrate) - expand based on usage

**Question 4:** Should aud blueprint --frameworks be separate flag or always shown?
**Recommendation:** Always show in --structure mode - critical context

---

## Confirmation of Understanding

**Verification Finding:** 4 prerequisites identified (naming, precedent, refactor storage, framework exposure). All are buildable using existing infrastructure.

**Root Cause:** Missing agent orchestration layer prevents AI from using query commands correctly.

**Implementation Logic:** Build prerequisites first (Phase 1), then agent infrastructure (Phase 2), then test (Phase 3).

**Confidence Level:** HIGH - All prerequisites have clear implementations anchored in existing code patterns.

**Protocol:** TeamSOP v4.20 followed throughout planning phase.

---

**Status:** READY FOR ARCHITECT REVIEW
**Next Step:** Approval to proceed with Phase 1 implementation
