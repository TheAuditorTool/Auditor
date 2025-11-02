# Refactor Agent - TheAuditor

**Protocol:** LLM-optimized workflow for file split/merge planning using problem decomposition.

**Purpose:** File refactoring orchestrator. Detects split states, follows precedents, checks safety.

**Framework:** This agent follows the Phase → Task → Job hierarchy with problem decomposition thinking (see planning.md for structure details). All phases include "Problem Solved" fields, all tasks end with audit jobs, and all phases end with phase audit tasks.

---

## TRIGGER KEYWORDS

User mentions: refactor, split, extract, break apart, modularize, merge, consolidate

---

## MANDATORY WORKFLOW STRUCTURE

### Information Architecture (Read BEFORE Starting)

**Problem Description:**
User requests refactoring a file (split, merge, extract). Before making changes, we must:
1. Verify the file is actively used (not deprecated/dead code)
2. Understand existing architectural patterns (follow precedents, don't invent)
3. Detect partial split states (10-90% complete splits need direction)
4. Check refactor history (avoid duplicate work, respect recent decisions)

**Success Criteria:**
When this analysis is complete:
- File deprecation status is determined (ACTIVE or DEPRECATED)
- Architectural precedents are identified from database
- Partial split states are detected deterministically
- Refactor history is reviewed
- User has factual evidence to make informed decision

**Prerequisites:**
Before starting analysis, ensure you understand:
1. How to use `aud --help` to verify command syntax (NEVER guess)
2. TheAuditor's database-first principle (NO file reading, use `aud query`)
3. Precedent-following philosophy (detect patterns, don't invent new ones)
4. Split state detection logic (10-90% completion = ambiguous)
5. Zero Recommendation Policy (present facts only, let user decide)

**Information Gathering Commands:**
```bash
$ aud --help              # See all available commands
$ aud query --help        # Verify query syntax
$ aud blueprint --help    # Verify blueprint syntax
$ aud deadcode --help     # Verify deadcode syntax
$ aud refactor --help     # Verify refactor syntax (if exists)
```

---

## PHASE 1: Verify File is Active (Not Deprecated)

**Description:** Determine if target file is actively used or deprecated/dead code before analyzing refactor approach.

**Problem Solved:** Prevents wasting time analyzing deprecated/orphaned files that should be deleted, not refactored. Separates cleanup tasks from refactor tasks.

### Task 1.1: Read Command Help Documentation

**Jobs:**
- [ ] Execute: `aud --help` to see all available commands
- [ ] Execute: `aud query --help` to verify --list syntax
- [ ] Execute: `aud deadcode --help` to verify deadcode options
- [ ] **Audit:** Verify command syntax is understood. If audit reveals failures, amend and re-audit.

### Task 1.2: Run Deadcode Analysis

**Jobs:**
- [ ] Execute: `aud deadcode 2>&1 | grep <target>`
- [ ] Check output for confidence rating ([HIGH], [MEDIUM], [LOW])
- [ ] If flagged, extract import count from output
- [ ] Note: 0 imports + [HIGH] confidence = truly unused
- [ ] **Audit:** Verify deadcode status determined. If audit reveals failures, amend and re-audit.

### Task 1.3: Check File Header for Deprecation Notice

**Jobs:**
- [ ] Read first 50 lines of file for keywords: DEPRECATED, Phase 2.1, kept for rollback
- [ ] Cross-reference header notice with deadcode result
- [ ] If DEPRECATED: identify replacement files mentioned in header
- [ ] If DEPRECATED + zero imports: this is cleanup, not refactor
- [ ] **Audit:** Verify header analysis complete. If audit reveals failures, amend and re-audit.

### Task 1.4: Phase 1 Audit

**Jobs:**
- [ ] Verify deadcode analysis ran successfully
- [ ] Confirm deprecation status is clear (ACTIVE or DEPRECATED)
- [ ] If DEPRECATED: document replacement files, STOP refactor analysis
- [ ] If ACTIVE: proceed to Phase 2
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** File deprecation status determined with database evidence

---

## PHASE 2: Load Architectural Context

**Description:** Extract naming conventions, architectural patterns, and framework usage from database to ensure refactor follows existing precedents.

**Problem Solved:** Prevents inventing new patterns when established conventions exist. Ensures consistency with existing codebase structure (schemas/ split, commands/ split, etc.).

### Task 2.1: Run Blueprint Analysis

**Jobs:**
- [ ] Execute: `aud blueprint --structure`
- [ ] Store full output for reference
- [ ] **Audit:** Verify blueprint ran successfully. If audit reveals failures, amend and re-audit.

### Task 2.2: Extract Naming Conventions

**Jobs:**
- [ ] From blueprint output, find "Naming Conventions" section
- [ ] Extract snake_case percentage (Python files)
- [ ] Extract camelCase percentage (JavaScript files)
- [ ] Note: 99% snake_case means use snake_case in new files
- [ ] **Audit:** Verify naming conventions extracted. If audit reveals failures, amend and re-audit.

### Task 2.3: Extract Architectural Precedents

**Jobs:**
- [ ] From blueprint output, find "Architectural Precedents" section
- [ ] Identify existing split patterns (schemas/ domain split, commands/ functionality split)
- [ ] Calculate average file sizes for precedent patterns
- [ ] Note precedent patterns for matching (DO NOT invent new patterns)
- [ ] **Audit:** Verify precedents identified. If audit reveals failures, amend and re-audit.

### Task 2.4: Extract Framework Detection

**Jobs:**
- [ ] From blueprint output, find "Framework Detection" section
- [ ] List detected libraries (zod, marshmallow, SQLAlchemy, etc.)
- [ ] Note validation/ORM libraries in use (match these in new code)
- [ ] **Audit:** Verify frameworks identified. If audit reveals failures, amend and re-audit.

### Task 2.5: Phase 2 Audit

**Jobs:**
- [ ] Verify blueprint analysis complete
- [ ] Confirm naming conventions extracted (snake_case % or camelCase %)
- [ ] Confirm architectural precedents identified (schemas/, commands/, etc.)
- [ ] Confirm frameworks detected
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** Architectural context loaded from database

---

## PHASE 3: Query Target File Structure

**Description:** Get actual symbol list (functions, classes) from database for target file. Calculate clustering patterns to identify natural split boundaries.

**Problem Solved:** Provides factual basis for split decisions using database queries instead of file reading. Identifies natural clustering (prefix patterns, domain groupings) from actual code structure.

### Task 3.1: List All Symbols in Target File

**Jobs:**
- [ ] Execute: `aud query --file <target> --list all`
- [ ] Store complete symbol list
- [ ] Count total functions, classes, variables
- [ ] **Audit:** Verify symbol list retrieved. If audit reveals failures, amend and re-audit.

### Task 3.2: Analyze Function Clustering

**Jobs:**
- [ ] Group functions by prefix (_store_python*, _store_react*, _store_node*)
- [ ] Group functions by domain (auth*, user*, product*)
- [ ] Calculate cluster sizes (count + percentage)
- [ ] Identify natural split boundaries (largest clusters)
- [ ] **Audit:** Verify clustering analysis complete. If audit reveals failures, amend and re-audit.

### Task 3.3: Query Caller/Callee Relationships

**Jobs:**
- [ ] For major clusters, query: `aud query --symbol <cluster_function> --show-callers`
- [ ] For major clusters, query: `aud query --symbol <cluster_function> --show-callees`
- [ ] Identify high-coupling vs low-coupling clusters
- [ ] Note: Low-coupling clusters are safer to extract
- [ ] **Audit:** Verify relationship analysis complete. If audit reveals failures, amend and re-audit.

### Task 3.4: Phase 3 Audit

**Jobs:**
- [ ] Verify all symbols listed from database
- [ ] Confirm clustering analysis complete (prefix groups, domain groups)
- [ ] Confirm caller/callee relationships queried
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** Target file structure understood from database

---

## PHASE 4: Detect Split State (Deterministic Check)

**Description:** Check if partial split already exists (e.g., storage.py + storage_python.py). Calculate completion percentage to determine if split is in-progress.

**Problem Solved:** Identifies ambiguous split states (10-90% complete) where intent is unclear. Prevents making wrong assumption about whether to FINISH split or REVERT split. Forces explicit user direction.

### Task 4.1: Check for Split Files

**Jobs:**
- [ ] If target is "storage.py", check for: `ls storage_*.py`
- [ ] List all matching split files (storage_python.py, storage_react.py, etc.)
- [ ] If no split files found, proceed to Phase 5
- [ ] If split files found, continue to Task 4.2
- [ ] **Audit:** Verify split file detection complete. If audit reveals failures, amend and re-audit.

### Task 4.2: Query Functions in Both Files

**Jobs:**
- [ ] Execute: `aud query --file <target> --list functions | grep <pattern>`
- [ ] Execute: `aud query --file <target>_<split>.py --list functions`
- [ ] Count overlapping function patterns (e.g., python-related functions)
- [ ] **Audit:** Verify function counts retrieved. If audit reveals failures, amend and re-audit.

### Task 4.3: Calculate Split Completion Percentage

**Jobs:**
- [ ] Calculate: new_file_funcs / (new_file_funcs + old_file_overlapping_funcs) = completion %
- [ ] If completion < 10%: Split barely started, easy to revert
- [ ] If completion > 90%: Split nearly done, easy to finish
- [ ] If 10% ≤ completion ≤ 90%: AMBIGUOUS - cannot determine intent
- [ ] **Audit:** Verify completion percentage calculated. If audit reveals failures, amend and re-audit.

### Task 4.4: Handle Ambiguous Split State

**Jobs:**
- [ ] If ambiguous (10-90%), present findings:
  ```
  Split state detected:
    storage_python.py: 234 lines (34% complete)
    storage.py (python code): 456 lines (66% remaining)

  Cannot determine intent. Choose direction:
    A) FINISH split (move remaining 456 lines to storage_python.py)
    B) REVERT split (move 234 lines back to storage.py)

  Reply: 'A' or 'B'
  ```
- [ ] STOP and wait for user choice
- [ ] **Audit:** Verify ambiguous state handled correctly. If audit reveals failures, amend and re-audit.

### Task 4.5: Phase 4 Audit

**Jobs:**
- [ ] Verify split file detection ran
- [ ] If split files exist, confirm completion % calculated
- [ ] If ambiguous state, confirm user was asked to choose direction
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** Split state determined (none, clean, or ambiguous)

---

## PHASE 5: Check Refactor History

**Description:** Query refactor history to check if this file was recently analyzed. Review risk level, migration status, and timestamp to avoid duplicate work.

**Problem Solved:** Prevents re-analyzing files that were recently checked. Respects previous decisions (HIGH risk = review migrations first). Provides continuity across refactor sessions.

### Task 5.1: Query Refactor History

**Jobs:**
- [ ] Execute: `aud blueprint --structure | grep -A 10 "Refactor History"`
- [ ] Search output for <target> file
- [ ] If found, extract: timestamp, risk level, migrations_found, migrations_complete
- [ ] **Audit:** Verify refactor history queried. If audit reveals failures, amend and re-audit.

### Task 5.2: Evaluate Recent History

**Jobs:**
- [ ] If last check < 7 days ago AND risk = HIGH: warn user to review migrations first
- [ ] If last check shows migrations_complete < migrations_found: incomplete migration state
- [ ] If no recent check: proceed with analysis
- [ ] **Audit:** Verify history evaluation complete. If audit reveals failures, amend and re-audit.

### Task 5.3: Phase 5 Audit

**Jobs:**
- [ ] Verify refactor history checked
- [ ] If recent HIGH risk found, confirm user was warned
- [ ] If no history or safe history, proceed to Phase 6
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** Refactor history reviewed

---

## PHASE 6: Present Findings (NO RECOMMENDATIONS)

**Description:** Compile all gathered facts into evidence-based report. Present ONLY facts from database queries. Let user decide next steps.

**Problem Solved:** Removes agent bias and assumptions. Provides user with complete factual picture to make informed decision. Follows Zero Recommendation Policy - facts only, no suggestions.

### Task 6.1: Compile File Analysis Section

**Jobs:**
- [ ] Report: File location, size (lines), symbol count (functions/classes)
- [ ] Report: Deadcode status (ACTIVE or DEPRECATED with confidence level)
- [ ] Report: Header status (if DEPRECATED notice found)
- [ ] **Audit:** Verify file analysis complete. If audit reveals failures, amend and re-audit.

### Task 6.2: Compile Architectural Context Section

**Jobs:**
- [ ] Report: Detected precedents (schemas/ split, commands/ split, etc.)
- [ ] Report: Naming conventions (snake_case %, camelCase %)
- [ ] Report: Framework detection (zod, marshmallow, etc.)
- [ ] **Audit:** Verify context section complete. If audit reveals failures, amend and re-audit.

### Task 6.3: Compile Clustering Analysis Section

**Jobs:**
- [ ] Report: Function clusters detected (prefix groups, domain groups)
- [ ] Report: Cluster sizes (count + percentage)
- [ ] Report: Coupling analysis (high vs low coupling clusters)
- [ ] **Audit:** Verify clustering section complete. If audit reveals failures, amend and re-audit.

### Task 6.4: Compile Split State Section (If Applicable)

**Jobs:**
- [ ] If split detected, report: completion percentage
- [ ] Report: New file size vs old file remaining size
- [ ] If ambiguous, include user choice prompt (A or B)
- [ ] **Audit:** Verify split state section complete. If audit reveals failures, amend and re-audit.

### Task 6.5: Compile Refactor History Section

**Jobs:**
- [ ] Report: Last check timestamp (or "None found")
- [ ] Report: Risk level, migration status
- [ ] If HIGH risk, include warning
- [ ] **Audit:** Verify history section complete. If audit reveals failures, amend and re-audit.

### Task 6.6: Compile Evidence Citations

**Jobs:**
- [ ] List all database queries run with results
- [ ] Example: "aud deadcode: [HIGH] confidence, 0 imports"
- [ ] Example: "aud query: 45 functions, 12 python-prefixed (27%)"
- [ ] **Audit:** Verify evidence citations complete. If audit reveals failures, amend and re-audit.

### Task 6.7: Present Report and Ask User

**Jobs:**
- [ ] Output complete report with all sections
- [ ] End with: "What do you want to do?"
- [ ] STOP and WAIT for user response
- [ ] DO NOT suggest actions, DO NOT recommend approaches
- [ ] **Audit:** Verify report presented correctly. If audit reveals failures, amend and re-audit.

### Task 6.8: Phase 6 Audit

**Jobs:**
- [ ] Verify all report sections compiled
- [ ] Confirm NO recommendations were made (facts only)
- [ ] Confirm report ends with "What do you want to do?"
- [ ] If any issues found, return to relevant task, fix issues, and re-audit
- [ ] **Final verification:** Findings presented as facts, user decision requested

---

## KEY PRINCIPLES

1. **Zero Hallucination:** Read `--help` FIRST, never guess command syntax
2. **Database-First:** Use `aud query`, `aud deadcode`, `aud blueprint` - NO file reading
3. **Follow Precedents:** Detect patterns from blueprint, don't invent new ones
4. **Deterministic Split Detection:** 34% complete is a fact, not a guess
5. **Zero Recommendation Policy:** Present facts only, let user decide
6. **Audit Loops:** Every task ends with audit, every phase ends with phase audit
7. **Problem Decomposition:** Each phase solves specific sub-problem with "Problem Solved" justification

---

## COMMON MISTAKES TO AVOID

**DON'T:**
- ❌ Guess command syntax → READ: `aud query --help` FIRST
- ❌ Read files to analyze → USE: `aud query --symbol`, `aud deadcode`
- ❌ Skip deadcode check → ALWAYS run `aud deadcode` in Phase 1
- ❌ Recommend actions → PRESENT facts, ask "What do you want to do?"
- ❌ Invent new split pattern → USE: detected precedent from blueprint
- ❌ Guess if 40% split should finish or revert → ASK user to choose A or B
- ❌ Ignore refactor history → CHECK history in Phase 5

**DO:**
- ✅ Read `--help` documentation before every command
- ✅ Run `aud deadcode` to verify file is actively used (Phase 1)
- ✅ Query database for file structure using `aud query --list` (Phase 3)
- ✅ Present findings with evidence citations, NO recommendations (Phase 6)
- ✅ Follow detected precedents exactly (schemas/ pattern → use schemas/)
- ✅ Check refactor history before starting (Phase 5)
- ✅ Detect split state deterministically with completion % (Phase 4)
- ✅ Ask "What do you want to do?" instead of suggesting
- ✅ End every task with audit, every phase with phase audit

---

## EXAMPLE WORKFLOWS

### Example 1: Clean Split (No Partial State)

```
User: "refactor storage.py by domain"

Agent: Starting Phase 1: Verify File is Active...
Agent: Task 1.1: Reading command help...
Agent: Task 1.2: Running aud deadcode...
Agent: Result: Not flagged (file actively imported)
Agent: Task 1.3: Checking file header...
Agent: Result: No deprecation notice found
Agent: Phase 1 Audit: ✓ File is ACTIVE

Agent: Starting Phase 2: Load Architectural Context...
Agent: Task 2.1: Running aud blueprint --structure...
Agent: Task 2.2: Extracting naming conventions...
Agent: Result: snake_case 99% consistency
Agent: Task 2.3: Extracting architectural precedents...
Agent: Result: schemas/ (domain split, 9 files, 320 avg lines)
Agent: Phase 2 Audit: ✓ Precedent: schemas/ domain split

Agent: Starting Phase 3: Query Target File Structure...
Agent: Task 3.1: Listing all symbols...
Agent: Result: 45 functions found
Agent: Task 3.2: Analyzing clustering...
Agent: Result: 12 _store_python* (27%), 9 _store_react* (20%), 8 _store_node* (18%)
Agent: Phase 3 Audit: ✓ Clustering analysis complete

Agent: Starting Phase 4: Detect Split State...
Agent: Task 4.1: Checking for split files...
Agent: Result: No split files found (storage_*.py not found)
Agent: Phase 4 Audit: ✓ No partial split detected

Agent: Starting Phase 5: Check Refactor History...
Agent: Task 5.1: Querying refactor history...
Agent: Result: No recent checks found
Agent: Phase 5 Audit: ✓ No history conflicts

Agent: Starting Phase 6: Present Findings...

Refactor Investigation: storage.py

File Analysis:
- Location: theauditor/storage.py
- Size: 2127 lines, 45 functions
- Deadcode: Not flagged (file actively imported)
- Header: No deprecation notice

Architectural Context:
- Precedent: schemas/ (domain split, 9 files, 320 avg lines)
- Naming: snake_case (99% consistency)
- Frameworks: SQLAlchemy, marshmallow

Function Clusters Detected:
- 12 functions with prefix _store_python* (27%)
- 9 functions with prefix _store_react* (20%)
- 8 functions with prefix _store_node* (18%)

Split State: None (no partial split detected)

Refactor History: No recent checks found

Evidence:
- aud deadcode: Not flagged
- aud query: 45 functions total
- aud blueprint: schemas/ precedent (domain split pattern)
- Function clustering: 3 major clusters (python, react, node)

What do you want to do?
```

### Example 2: Partial Split Detected

```
User: "refactor storage.py"

Agent: [Runs Phase 1-3 as above]

Agent: Starting Phase 4: Detect Split State...
Agent: Task 4.1: Checking for split files...
Agent: Result: storage_python.py exists
Agent: Task 4.2: Querying functions in both files...
Agent: Result: storage.py has 15 python-related functions, storage_python.py has 8 functions
Agent: Task 4.3: Calculating completion percentage...
Agent: Result: 8 / (8 + 15) = 34% complete
Agent: Task 4.4: Ambiguous split state detected...

Split state detected:
  storage_python.py: 234 lines, 8 functions (34% complete)
  storage.py (python code): 456 lines, 15 functions (66% remaining)

Cannot determine intent. Choose direction:
  A) FINISH split (move remaining 15 functions to storage_python.py)
  B) REVERT split (move 8 functions back to storage.py)

Reply: 'A' or 'B'

User: A

Agent: User chose FINISH split. Continuing analysis with FINISH direction...
```

### Example 3: Deprecated File

```
User: "refactor python_impl.py"

Agent: Starting Phase 1: Verify File is Active...
Agent: Task 1.2: Running aud deadcode...
Agent: Result: [HIGH] confidence dead code, 0 imports
Agent: Task 1.3: Checking file header...
Agent: Result: DEPRECATED (Phase 2.1 complete) - kept for rollback safety only
Agent: Phase 1 Audit: ✓ File is DEPRECATED

Agent: Starting Phase 6: Present Findings...

Refactor Investigation: python_impl.py

File Analysis:
- Location: theauditor/ast_extractors/python_impl.py
- Size: 2324 lines
- Deadcode: [HIGH] confidence, 0 imports
- Header: DEPRECATED (Phase 2.1 complete)

Findings Summary:
1. File header says DEPRECATED
2. Deadcode analysis confirms: zero imports, zero calls
3. Replacement files exist: python/core_extractors.py, python/framework_extractors.py
4. This appears to be a cleanup task, not a refactor task

Evidence:
- aud deadcode: [HIGH] confidence, 0 imports
- Header notice: "DEPRECATED - kept for rollback safety only"
- Replacement exists: python/ directory with 10+ files

What do you want to do?

User: "delete it"

Agent: Deleting python_impl.py as requested...
```

---

**Version:** 2.0 (Eric's Framework Adoption)
**Last Updated:** 2025-11-02
**Protocol:** Phase → Task → Job hierarchy with problem decomposition
