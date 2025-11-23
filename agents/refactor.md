# Refactor Agent - TheAuditor

**Protocol:** Phase -> Task -> Job hierarchy with problem decomposition. See `AGENTS.md` for routing and principles.

**Purpose:** File refactoring orchestrator. Detects split states, follows precedents, checks safety.

**Triggers:** refactor, split, extract, break apart, modularize, merge, consolidate

---

## ⚠️ MANDATORY TOOL USAGE - NON-NEGOTIABLE ⚠️

**CRITICAL:** Run TheAuditor commands autonomously. NO file reading until Phase 3 Task 3.4. ALL structure from database first.

**For AI Assistants:**
1. **Database-first:** Use `aud query`, `aud deadcode`, `aud blueprint` BEFORE reading files
2. **NO file reading** until Phase 3 Task 3.4 (after database structure analysis)
3. **Chunked reading mandatory** for files >2150 lines (1500-line chunks)
4. **Zero Recommendation Policy:** Present facts only, let user decide
5. **Follow precedents:** Use blueprint patterns, DON'T invent new ones

**Correct Behavior:**
- ✅ Agent: *runs `aud explain <file>`* → *runs `aud deadcode`* → *runs `aud blueprint`* → *then reads file in chunks if >2150 lines*
- ✅ Agent cites all database queries in findings
- ✅ Agent ends with "What do you want to do?" (NO recommendations)

---

## STEP 0: Context Gathering (ALWAYS FIRST)

Before any refactoring analysis, gather comprehensive context with ONE command:

**For files being refactored:**
```bash
aud explain <file>
```
This returns: symbols defined, hooks used, dependencies, dependents, outgoing calls, incoming calls.

**For specific functions being modified:**
```bash
aud explain <Symbol.method>
```
This returns: definition, all callers (who to update), all callees (dependencies).

**Why this matters:**
- Single command replaces 5-6 separate queries
- Shows impact of changes (who imports this file, who calls these functions)
- Includes code snippets by default
- Saves context window tokens

Only read files directly if `aud explain` output is insufficient.

---

## PHASE 1: Verify File is Active

**Description:** Determine if file is actively used or deprecated before refactoring.

**Success Criteria:** Deprecated files identified. Cleanup tasks separated from refactor tasks.

### T1.1: Read Command Help
- `aud --help`, `aud query --help`, `aud deadcode --help`
- **Audit:** Syntax understood

### T1.2: Run Deadcode Analysis
- `aud deadcode 2>&1 | grep <target>`
- Check confidence: [HIGH]/[MEDIUM]/[LOW]
- Check import count
- Note: 0 imports + [HIGH] = truly unused
- **Audit:** Deadcode status determined

### T1.3: Check File Header
- Read first 50 lines for: DEPRECATED, Phase 2.1, kept for rollback
- Cross-reference with deadcode result
- If DEPRECATED: identify replacement files
- **Audit:** Header analyzed

### T1.4: Phase 1 Audit
- Verify status: ACTIVE or DEPRECATED
- If DEPRECATED: document replacements, STOP refactor
- If ACTIVE: proceed to Phase 2
- **Audit:** File status determined with database evidence

---

## PHASE 2: Load Architectural Context

**Description:** Extract naming, patterns, frameworks from database to follow existing precedents.

**Success Criteria:** Precedents identified. NO invented patterns.

### T2.1: Run Blueprint
- `aud blueprint --structure`
- `aud structure --monoliths`
- Store outputs
- **Audit:** Both successful

**Monoliths check:** >2150 lines need 1500-line chunks. Know UP FRONT.

### T2.2: Extract Naming
- Find "Naming Conventions"
- Extract snake_case %, camelCase %
- Note: 99% snake_case → use snake_case
- **Audit:** Conventions extracted

### T2.3: Extract Precedents
- Find "Architectural Precedents"
- Identify split patterns (schemas/, commands/)
- Calculate avg file sizes
- DON'T invent new patterns
- **Audit:** Precedents identified

### T2.4: Extract Frameworks
- Find "Framework Detection"
- List libraries (zod, SQLAlchemy, etc.)
- Note validation/ORM libs
- **Audit:** Frameworks identified

### T2.5: Phase 2 Audit
- Verify blueprint + monoliths complete
- Confirm naming, precedents, frameworks extracted
- **Audit:** Architectural context loaded + large file detection complete

---

## PHASE 3: Query Target File Structure

**Description:** Get symbol list from database. Analyze clustering. Read file if needed.

**Success Criteria:** Database structure retrieved. Natural split boundaries identified. File content understood (if >2150 lines).

### T3.1: List All Symbols
- `aud query --file <target> --list all`
- Store symbol list
- Count functions, classes, variables
- **Audit:** Symbol list retrieved

### T3.2: Analyze Clustering
- Group by prefix (_store_python*, _store_react*)
- Group by domain (auth*, user*)
- Calculate cluster sizes (count + %)
- Identify natural split boundaries
- **Audit:** Clustering complete

### T3.3: Query Relationships
- For major clusters: `aud query --symbol <cluster_func> --show-callers`
- For major clusters: `aud query --symbol <cluster_func> --show-callees`
- Identify high-coupling vs low-coupling
- Note: Low coupling = safer to extract
- **Audit:** Relationships analyzed

### T3.4: Assess Blast Radius (NEW)
- Run `aud impact --file <target> --planning-context`
- Store: coupling score, dependency categories (prod/test/config), risk level
- Note suggested phases from impact output
- If coupling >70: Flag "tightly coupled, consider interface extraction"
- If affected files >30: Flag "large blast radius, phase the refactor"
- **Audit:** Blast radius quantified with coupling score

**Coupling Score Interpretation:**
- <30: LOW - File can be safely split with minimal coordination
- 30-70: MEDIUM - Notify dependent teams, consider phased rollout
- >70: HIGH - Extract interface first, then refactor implementation

### T3.5: Read Large Files in Chunks (MANDATORY for >2150 lines)

**When Required:** File >2150 lines (check Task 3.1 line count)

**Jobs:**
- Check line count: `aud query --file <target> --show-functions | grep "Lines:"`
- If ≤2150: Read normally
- If >2150: MANDATORY chunked reading:
  - Read(target, offset=0, limit=1500)
  - Read(target, offset=1500, limit=1500)
  - Read(target, offset=3000, limit=1500) if >3000
  - Continue until entire file covered
- Use function boundaries from T3.1 to guide chunks
- Synthesize understanding across chunks
- **Audit:** Entire file content read and understood

**Critical:** Chunking is MANDATORY, not optional. Database = structure, file reading = implementation detail.

### T3.6: Phase 3 Audit
- Verify symbols listed
- Confirm clustering analysis complete
- Confirm relationships queried
- Confirm impact analysis run with coupling score noted
- Confirm file content read (chunked if >2150, normal otherwise)
- **Audit:** Target file structure understood from database + impact assessed + file content

---

## PHASE 4: Detect Split State

**Description:** Check if partial split exists. Calculate completion percentage.

**Success Criteria:** Ambiguous splits (10-90%) identified. User chooses direction (FINISH or REVERT).

### T4.1: Check for Split Files
- If target = "storage.py", check: `ls storage_*.py`
- List matching split files
- If none: proceed to Phase 5
- If found: continue to T4.2
- **Audit:** Split file detection complete

### T4.2: Query Functions in Both
- `aud query --file <target> --list functions | grep <pattern>`
- `aud query --file <target>_<split>.py --list functions`
- Count overlapping patterns
- **Audit:** Function counts retrieved

### T4.3: Calculate Completion %
- Formula: new_file_funcs / (new_file_funcs + old_file_overlapping_funcs)
- <10%: Barely started, easy to revert
- >90%: Nearly done, easy to finish
- 10-90%: AMBIGUOUS
- **Audit:** Completion % calculated

### T4.4: Handle Ambiguous State
If 10-90%:
```
Split state detected:
  storage_python.py: 234 lines (34% complete)
  storage.py (python code): 456 lines (66% remaining)

Cannot determine intent. Choose:
  A) FINISH split (move 456 lines to storage_python.py)
  B) REVERT split (move 234 lines back to storage.py)

Reply: 'A' or 'B'
```
- STOP and WAIT
- **Audit:** Ambiguous state handled

### T4.5: Phase 4 Audit
- Verify split detection ran
- If split exists, confirm completion % calculated
- If ambiguous, confirm user choice requested
- **Audit:** Split state determined (none, clean, or ambiguous)

---

## PHASE 5: Check Refactor History

**Description:** Query history to check recent analysis. Review risk level, migrations.

**Success Criteria:** Recent checks reviewed. Duplicate work avoided. Previous decisions respected.

### T5.1: Query History
- `aud blueprint --structure | grep -A 10 "Refactor History"`
- Search for <target>
- Extract: timestamp, risk level, migrations_found, migrations_complete
- **Audit:** History queried

### T5.2: Evaluate Recent History
- If <7 days ago AND HIGH risk: warn to review migrations first
- If migrations_complete < migrations_found: incomplete migration
- If no recent check: proceed
- **Audit:** History evaluated

### T5.3: Phase 5 Audit
- Verify history checked
- If recent HIGH risk, confirm user warned
- **Audit:** Refactor history reviewed

---

## PHASE 6: Present Findings (NO RECOMMENDATIONS)

**Description:** Compile facts from database. Present evidence. NO suggestions.

**Success Criteria:** Facts only. User makes decision. Zero Recommendation Policy.

### T6.1: File Analysis Section
- Location, size (lines), symbol count
- Deadcode status (ACTIVE/DEPRECATED + confidence)
- Header status (if DEPRECATED)
- **Audit:** File analysis complete

### T6.2: Architectural Context Section
- Precedents (schemas/, commands/)
- Naming (snake_case %, camelCase %)
- Frameworks (zod, marshmallow, etc.)
- **Audit:** Context complete

### T6.3: Clustering Analysis Section
- Function clusters (prefix, domain)
- Cluster sizes (count + %)
- Coupling analysis (high vs low)
- **Audit:** Clustering complete

### T6.4: Impact Assessment Section (NEW)
- Coupling score (e.g., "45/100 MEDIUM")
- Dependency breakdown (e.g., "12 prod, 4 test, 2 config")
- Affected files count
- Risk level (LOW/MEDIUM/HIGH)
- If HIGH coupling: note "consider interface extraction"
- **Audit:** Impact complete

### T6.5: Split State Section
- If detected: completion %
- New file size vs old file remaining
- If ambiguous: include choice prompt (A or B)
- **Audit:** Split state complete

### T6.6: History Section
- Last check timestamp (or "None")
- Risk level, migration status
- If HIGH risk: include warning
- **Audit:** History complete

### T6.7: Evidence Citations
- List all queries: `aud deadcode`, `aud query`, `aud blueprint`, `aud impact`
- Example: "aud deadcode: [HIGH] confidence, 0 imports"
- Example: "aud query: 45 functions, 12 python-prefixed (27%)"
- Example: "aud impact: Coupling 45/100 MEDIUM, 16 affected files"
- **Audit:** Evidence complete

### T6.8: Present Report
- Output complete report
- End with: "What do you want to do?"
- STOP and WAIT
- DO NOT suggest actions
- **Audit:** Report presented correctly

### T6.9: Phase 6 Audit
- Verify all sections compiled (including impact)
- Confirm NO recommendations made
- Confirm ends with "What do you want to do?"
- **Audit:** Findings presented as facts, user decision requested

---

## KEY PRINCIPLES

1. **Zero Hallucination:** Read `--help` FIRST
2. **Database-First:** Use `aud query`, `aud deadcode`, `aud blueprint`, `aud impact` - NO file reading until Phase 3 Task 3.5
3. **Assess Impact First:** Run `aud impact --planning-context` before any refactor decision
4. **Follow Precedents:** Detect patterns, don't invent
5. **Deterministic Split Detection:** 34% complete = fact, not guess
6. **Zero Recommendation Policy:** Facts only, let user decide
7. **Audit Loops:** Every task/phase ends with audit
8. **Problem Decomposition:** Each phase solves specific sub-problem

---

## EXAMPLE (Compressed)

```
User: "refactor storage.py by domain"

Phase 1: Verify Active
  deadcode → Not flagged (actively imported)
  header → No deprecation notice
  Result: ACTIVE

Phase 2: Load Context
  blueprint → snake_case 99%, schemas/ (domain split, 9 files, 320 avg lines)

Phase 3: Query Structure
  query → 45 functions
  clustering → 12 _store_python* (27%), 9 _store_react* (20%), 8 _store_node* (18%)

Phase 4: Detect Split
  ls storage_*.py → No split files found

Phase 5: History
  No recent checks

Phase 6: Present Findings

Refactor Investigation: storage.py

File Analysis:
- 2127 lines, 45 functions
- Deadcode: Not flagged
- Active file

Context:
- Precedent: schemas/ (domain split, 9 files, 320 avg)
- Naming: snake_case 99%

Clusters:
- 12 python-prefixed (27%)
- 9 react-prefixed (20%)
- 8 node-prefixed (18%)

Split State: None

History: No recent checks

Evidence:
- aud deadcode: Not flagged
- aud query: 45 functions
- aud blueprint: schemas/ precedent

What do you want to do?
```

---

**Version:** 2.1 (Condensed Format)
**Last Updated:** 2025-11-05
**Protocol:** Phase → Task → Job with problem decomposition
