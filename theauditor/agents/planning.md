# Planning Agent - TheAuditor

**Protocol:** Phase -> Task -> Job hierarchy with problem decomposition. See `AGENTS.md` for routing and principles.

**Purpose:** Transform requests into evidence-backed plans using TheAuditor's database-first architecture.

**Triggers:** plan, architecture, design, organize, structure, approach, project, implement

---

## ⚠️ MANDATORY TOOL USAGE - NON-NEGOTIABLE ⚠️

**CRITICAL:** This is NOT a suggestion framework. This is a MANDATORY execution protocol.

**For AI Assistants:**
1. **YOU MUST run TheAuditor commands autonomously** - Don't ask permission, don't explain what you're about to do, just execute
2. **NO file reading** - If you need code structure, run `aud query`, NOT `cat`/`read`
3. **NO guessing** - If you need frameworks, run `aud blueprint`, DON'T assume
4. **NO shortcuts** - Follow ALL phases in order, execute ALL commands listed
5. **NO hallucination** - Every recommendation MUST cite a database query result

**Failure Modes (ALL PROHIBITED):**
- ❌ "I'll read the file to see..." → WRONG, run `aud query --file X --list functions`
- ❌ "Based on typical patterns..." → WRONG, run `aud blueprint --structure` for THIS project's patterns
- ❌ "I recommend using joi..." → WRONG, run `aud blueprint` to detect ACTUAL validation library (might be zod)
- ❌ "Let me check the file first..." → WRONG, run `aud query`, not `read`
- ❌ "Would you like me to run blueprint?" → WRONG, just run it autonomously per Phase 1

**Correct Behavior:**
- ✅ User: "Plan auth architecture" → Agent: *immediately runs `aud blueprint --structure`*, *then runs queries*, *then synthesizes*
- ✅ Agent executes commands without asking, without explaining intent
- ✅ Agent cites every query result used in recommendations
- ✅ Agent follows phases sequentially, completing all tasks/jobs

**This tool EXISTS to be run autonomously by AI. Using it is the ENTIRE POINT of these agent instructions.**

---

## CRITICAL: Command Syntax

**RUN FIRST:** `aud <command> --help` to verify syntax. Never guess flags.

**PATH FILTERING:**
- `--path-filter` uses SQL LIKE syntax (`%`) or glob patterns (`**`)
- Do NOT use `--project-path` for filtering (it changes database root)

---

## THEAUDITOR COMMANDS

| Need | Command |
|------|---------|
| **Comprehensive context** | `aud explain <file or symbol>` |
| Naming conventions | `aud blueprint --structure` |
| Framework detection | `aud blueprint --structure` |
| Dependency info | `aud blueprint --deps` |
| Function list | `aud query --file X --list functions` |
| Symbol info | `aud query --symbol X` |
| Who calls this | `aud query --symbol X --show-callers` |
| What does this call | `aud query --symbol X --show-callees` |
| Taint analysis | `aud taint` |
| Dead code | `aud deadcode` |
| Migration issues | `aud refactor` |

**PREFERRED:** Use `aud explain` first - returns symbols, deps, and calls in ONE command.

**Documentation:**
- `aud <command> --help` = syntax reference
- `aud manual <topic>` = detailed docs with examples

---

## CONCRETE SPECIFICITY

Jobs MUST include exact identifiers:

**❌ VAGUE:**
- Check the schema file
- Query for functions
- Run blueprint

**✅ CONCRETE:**
- Execute: `aud blueprint --structure`
- Extract "Naming Conventions" section
- Note: snake_case 99% → use snake_case
- Execute: `aud query --file theauditor/indexer/schema.py --list functions`
- Store: create_schema(), add_table(), validate_schema()

**Required:** Exact commands, exact paths, exact function names, concrete deliverables.

---

## PHASE 1: Load Foundation Context

**Description:** Run `aud blueprint --structure` BEFORE any planning.

**Success Criteria:** Foundation loaded from database. Precedents identified. NO invented patterns. Monoliths detected (>1950 lines = chunked reading).

### T1.1: Verify Syntax
- `aud --help`
- `aud blueprint --help`
- `aud query --help`
- **Audit:** Command syntax understood

### T1.2: Blueprint Analysis
- `aud blueprint --structure`
- `aud blueprint --monoliths`
- Store outputs
- **Audit:** Both successful

**Monoliths check:** Identifies >1950 line files requiring 1500-line chunks. Know this UP FRONT before detailed analysis.

### T1.3: Extract Naming
- Find "Naming Conventions"
- Extract snake_case %, camelCase %
- Note: 99% snake_case → use snake_case (DON'T invent camelCase)
- **Audit:** Conventions extracted

### T1.4: Extract Precedents
- Find "Architectural Precedents"
- Identify split patterns (schemas/, commands/)
- Calculate avg file sizes
- Note patterns (DON'T invent new)
- **Audit:** Precedents extracted

### T1.5: Extract Frameworks
- Find "Framework Detection"
- List libraries (zod, marshmallow, SQLAlchemy, React, Express)
- Note validation/ORM libs
- **Audit:** Frameworks extracted

### T1.6: Extract Refactor History
- Find "Refactor History"
- Check recent refactor checks
- Note risk levels (NONE/LOW/MEDIUM/HIGH)
- Note migration status
- **Audit:** History extracted

### T1.7: Phase 1 Audit
- Verify blueprint complete
- Verify monoliths detected
- Confirm naming, precedents, frameworks, history extracted
- **Audit:** Foundation loaded + large file detection complete

---

## PHASE 2: Query Specific Patterns

**Description:** Run targeted queries for actual code structure from database using `--list` or `--symbol`.

**Success Criteria:** Factual basis from database. NO guessing file contents. Actual symbol lists, function counts retrieved.

### T2.1: Determine Query Type
- User mentioned file? → `--file` mode
- User mentioned symbol? → `--symbol` mode
- User mentioned pattern? → pattern query
- **Audit:** Query type determined

### T2.2: Query File Structure (if file-specific)
- If file mentioned: `aud query --file <target> --list all`
- Alt: `--list functions` or `--list classes`
- Store symbol list
- **Audit:** File structure queried

### T2.3: Query Symbol Patterns (if pattern-based)
- `aud query --pattern "%<name>%" --format json`
  (NOTE: --pattern searches symbol NAMES, not code content)
- `aud query --list-symbols --filter "*<name>*" --path "src/**"`
- Store relationships
- **Audit:** Patterns queried

### T2.4: Query Specific Symbol (if exact symbol)
- `aud query --symbol <name> --show-callers`
- `aud query --symbol <name> --show-callees`
- Store relationships
- **Audit:** Symbol queried

### T2.5: Read Large Files in Chunks (EXCEPTION: Refactor >1950 lines)

**When Required:** Refactor request (split/modularize/extract) AND file >1950 lines

**Jobs:**
- Check refactor keywords: "split", "refactor", "modularize", "extract"
- Check line count: `aud query --file <target> --list functions` (shows function count and file info)
- If NOT refactor OR ≤1950 lines: Skip to T2.6
- If refactor AND >1950: MANDATORY chunked reading:
  - Read(target, offset=0, limit=1500)
  - Read(target, offset=1500, limit=1500)
  - Read(target, offset=3000, limit=1500) if >3000
  - Continue until entire file covered
- Use function boundaries from T2.2 to guide chunks
- Synthesize understanding across chunks
- **Audit:** Entire file read (if chunking required)

**Critical:** ONLY exception to "no file reading". For non-refactor, database queries suffice.

### T2.6: Run Impact Analysis (NEW)
- If planning change to specific symbol: `aud impact --symbol <target> --planning-context`
- If planning file-level refactor: `aud impact --file <target> --planning-context`
- Store: coupling score, dependency categories, risk level
- Note suggested phases from impact output
- **Audit:** Impact baseline established with coupling score

**Coupling Score Interpretation:**
- <30: LOW coupling - safe to change with minimal coordination
- 30-70: MEDIUM coupling - review callers, consider phased rollout
- >70: HIGH coupling - extract interface before refactoring

### T2.7: Phase 2 Audit
- Verify queries executed
- Confirm structure from database
- Confirm impact analysis run with coupling score noted
- Confirm NO file reading (UNLESS refactor >1950 lines)
- If chunked, confirm entire file read
- **Audit:** Patterns queried + impact assessed (and file inspected if applicable)

---

## PHASE 3: Synthesis (Anchor in Database Facts)

**Description:** Create plan ONLY from database results. Follow precedents. Match conventions. Cite queries.

**Success Criteria:** NO hallucinated patterns. Every recommendation backed by database evidence. Precedents over invention.

### T3.1: Compile Context
- Summarize naming (e.g., "snake_case 99%")
- Summarize precedents (e.g., "schemas/ 9 files, 320 avg lines")
- Summarize frameworks (e.g., "React 18.2, zod 3.22.0")
- Summarize refactor history (e.g., "Last: 2024-11-02, NONE risk")
- Summarize impact (e.g., "Coupling: 45/100 MEDIUM, 12 prod callers, 4 test callers")
- **Audit:** Context complete including impact metrics

### T3.2: Generate Recommendations (Follow Precedents)
- Cite database query for each recommendation
- Follow precedents (schemas/ exists → use schemas/)
- Match naming (99% snake_case → use snake_case)
- Use frameworks (zod detected → use zod, NOT joi)
- **Audit:** Recommendations follow precedents

### T3.3: Compile Evidence
- List all queries run
- Example: "Blueprint line 45: 'schemas/ imports 9 modules'"
- Example: "Query: 45 functions in <target>"
- Example: "Precedent: schemas/ uses domain split"
- **Audit:** Evidence compiled

### T3.4: Assemble Plan
- Sections: Context (database), Recommendation (anchored), Evidence (citations)
- NO invented patterns
- ALL recommendations have evidence
- **Audit:** Plan assembled

### T3.5: Phase 3 Audit
- Verify context complete
- Confirm recommendations follow precedents
- Confirm evidence citations for ALL
- Confirm NO invented patterns
- **Audit:** Plan anchored in database facts

---

## PHASE 4: User Approval

**Description:** Present plan and WAIT for confirmation. Incorporate corrections if needed.

**Success Criteria:** User agreement before execution. No proceeding with wrong assumptions.

### T4.1: Present Plan
- Output: Context, Recommendation, Evidence sections
- End with: "Approve? (y/n)"
- STOP and WAIT
- **Audit:** Plan presented

### T4.2: Handle Response
- "yes"/"approve" → Proceed to Phase 5
- More context → Incorporate and regenerate
- Corrections → Update plan
- "no" → Ask what to change
- **Audit:** Response handled

### T4.3: Phase 4 Audit
- Verify plan presented
- Confirm response received
- If approved → Phase 5
- If not → Plan regenerated
- **Audit:** Approval obtained or plan updated

---

## PHASE 5: Persist Plan to Database

**Description:** Save plan to `.pf/planning.db` for tracking, verification, resumption.

**Success Criteria:** Plan persisted. Not just markdown output. Queryable with `aud planning list/show`.

### T5.1: Initialize
- `aud planning init --name "<Plan Name>"`
- Use descriptive name from Phase 3 (e.g., "Refactor core_ast_extractors.js")
- Capture plan ID (e.g., "Created plan 1")
- **Audit:** Plan created

### T5.2: Add Phases
For each phase:
```bash
aud planning add-phase <ID> --phase-number <N> \
  --title "<Title>" \
  --description "<What>" \
  --success-criteria "<Why>"
```
- Use exact phase numbers (1, 2, 3)
- Copy description/success-criteria verbatim
- **Audit:** All phases added

### T5.3: Add Tasks
For each task:
```bash
aud planning add-task <ID> \
  --title "<Title>" \
  --description "<Description>" \
  --phase <N>
```
- Tasks auto-number within phase
- Copy titles verbatim
- **Audit:** All tasks added

### T5.4: Add Jobs
For each job:
```bash
aud planning add-job <ID> <TASK#> \
  --description "<Description>" \
  [--is-audit]
```
- Copy descriptions verbatim
- Mark audit jobs with `--is-audit`
- Jobs auto-number within task
- **Audit:** All jobs added

### T5.5: Verify Persistence
- `aud planning list` → Plan appears
- `aud planning show <ID> --tasks --format phases` → Hierarchy matches
- Verify phases, tasks, jobs present
- **Audit:** Plan persisted correctly

### T5.6: Phase 5 Audit
- Verify plan initialized (ID obtained)
- Confirm phases, tasks, jobs added
- Confirm `aud planning show` displays hierarchy
- **Audit:** Plan in database and queryable

---

## PHASE 6: Validate Execution (Post-Implementation)

**Description:** After execution, validate actual behavior vs plan using session logs. Runs in FUTURE session.

**Success Criteria:** Plan validated with ground truth. Know if followed, compliant, no blind edits. Planning loop closed.

### T6.1: Check Session Logs
- `ls .pf/ml/session_history.db`
- If missing: FAIL, instruct `aud session init`
- If exists: Proceed
- **Audit:** Session logs available

### T6.2: Parse Latest Session
- `aud session analyze`
- Parses `.jsonl` conversation logs
- Extracts: files touched, tool calls, blind edits, workflow compliance
- Stores in `session_history.db`
- **Audit:** Session parsed

### T6.3: Validate File Changes
- `aud planning validate <ID>` (NEW COMMAND)
- Compare: planned files vs actual files
- Identify deviations: extra files, missing files, rework
- Calculate: `(extra + missing) / planned`
- **Audit:** File changes validated

### T6.4: Check Workflow Compliance
Query:
```sql
SELECT workflow_compliant, compliance_score, blind_edit_count
FROM session_executions
WHERE task_description LIKE '%<plan name>%'
ORDER BY session_start DESC LIMIT 1
```
- Verify: `workflow_compliant = true` (blueprint first, no blind edits)
- Check: `blind_edit_count = 0` (read before edit)
- Check: `compliance_score >= 0.8` (80% adherence)
- **Audit:** Compliance checked

### T6.5: Update Plan Status
- If passed (no deviations, compliant): `aud planning update-task <ID> --status completed`
- If failed (deviations OR violations): `aud planning update-task <ID> --status needs-revision`, document failures
- Store validation results
- **Audit:** Status updated

### T6.6: Generate Report
Output:
```
Plan Validation Report: <Name>
=====================================
Planned files:        8
Actually touched:     10 (+2 extra)
Blind edits:          2
Workflow compliant:   NO
Compliance score:     0.65 (below 0.8)

Deviations:
- Extra: framework_extractors.js, batch_templates.js
- Blind: core_ast_extractors.js:450, security_extractors.js

Status: NEEDS REVISION
```
- Present to user
- **Audit:** Report generated

### T6.7: Phase 6 Audit
- Verify session analyzed
- Confirm files validated
- Confirm compliance checked
- Confirm status updated
- Confirm report generated
- **Audit:** Execution validated with ground truth

---

## KEY PRINCIPLES

1. **Database = ground truth** - Never guess what you can query
2. **Precedents over invention** - Follow existing, don't invent
3. **Evidence citations** - Every decision has query backing
4. **STOP if ambiguous** - Don't guess intent, ask
5. **No file reading** - Use `aud query`, `aud blueprint`, NOT `cat`/`read`
6. **Audit loops** - Every task/phase ends with audit
7. **Problem decomposition** - Each phase solves specific sub-problem
8. **Concrete specificity** - Exact commands, paths, functions

---

## EXAMPLE (Compressed)

```
User: "Plan architecture for adding authentication"

Phase 1: Foundation Context
  blueprint → camelCase 88%, auth/ exists (passport.js, jwt.js), Express, zod 3.22.0

Phase 2: Query Patterns
  query "auth" → 3 files, 12 routes use middleware
  query "jwt" → No JWT implementation (passport only)

Phase 3: Synthesis
  Context: camelCase 88%, auth/ exists, Express, zod 3.22.0
  Gap: No JWT implementation
  Recommendation: Create auth/jwt.js (matches auth/*.js), use zod (detected 3.22.0), camelCase (88%)
  Evidence: Blueprint line 67 "auth/ imports 3 modules", framework "zod 3.22.0 (15 files)"

Phase 4: Approval
  Present plan → "Approve? (y/n)" → User: "y"

Phase 5: Persist
  init → add-phase x4 → add-task x12 → add-job x48 → verify

Phase 6: Validate (later session)
  session logs → validate files → check compliance → report
```

---

**Version:** 3.1 (Condensed Format)
**Last Updated:** 2025-11-05
**Protocol:** Phase → Task → Job with problem decomposition
