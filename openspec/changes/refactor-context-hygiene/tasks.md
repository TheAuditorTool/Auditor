# Tasks: Context Hygiene Protocol

**Execution Environment:** `C:\Users\santa\Desktop\TheAuditor-cleanup\` (isolated worktree)
**Branch:** `cleanup-ruff`
**Working Directory:** All commands assume `cd C:/Users/santa/Desktop/TheAuditor-cleanup` first

---

## 0. Verification (MANDATORY FIRST)

Per teamsop.md Section 1.3 - Prime Directive: Verify Before Acting

### 0.1 Environment Verification
- [x] 0.1.1 Verify worktree exists: **CONFIRMED** - theauditor/, .pf/, etc. present
- [x] 0.1.2 Verify branch: **CONFIRMED** - cleanup-ruff
- [x] 0.1.3 Verify Python environment: **CONFIRMED** - Python 3.14.0, aud v1.6.5.dev0

### 0.2 Baseline Metrics
- [x] 0.2.1 Run ruff baseline: **COMPLETED** 2025-11-25
- [x] 0.2.2 Run pipeline baseline: **PASS** - 25/25 phases, 318.2s
- [x] 0.2.3 Document baseline in this section:

**Baseline Metrics (2025-11-25):**
```
Date: 2025-11-25
Total ruff issues: 8,403
F401 (unused imports): 742
F841 (unused variables): 72
UP006 (old type hints): 1,811
UP045 (Optional -> |): 609
UP035 (old import paths): 449
W293 (whitespace): 2,290
B905 (zip without strict): 853
```

---

## 1. Stop the Factory Defects (Generator Fix) ✓ COMPLETE

**Commit:** `9250d8d` - refactor(codegen): output modern Python 3.9+ type syntax
**Date:** 2025-11-25

**Results:**
- UP006: 1,811 → 112 (94% reduction)
- UP045: 609 → 19 (97% reduction)
- Generated files: 3,157 → 859 issues (~73% reduction)

**Note:** Proposal listed 7 locations to fix; actual implementation required 11 fixes (lines 231, 239, 254, 300 were missed in spec).

### 1.1 Read and Understand Generator
- [x] 1.1.1 Read `theauditor/indexer/schemas/codegen.py` completely (400 lines)
  ```bash
  # The file is at: theauditor/indexer/schemas/codegen.py
  # Key class: SchemaCodeGenerator
  # Key methods: generate_typed_dicts(), generate_accessor_classes(),
  #              generate_memory_cache(), generate_validators()
  ```
- [x] 1.1.2 Verify current generated output has issues: **3,157 issues confirmed**

### 1.2 Fix Generator Output Patterns

**File:** `theauditor/indexer/schemas/codegen.py`

- [x] 1.2.1 Fix line 27 - Remove unused imports from generator itself:
  ```python
  # BEFORE (line 27):
  from typing import Dict, List, Optional, Set, Any

  # AFTER:
  from typing import Any
  ```

- [x] 1.2.2 Fix line 111 - TypedDict imports in generate_typed_dicts():
  ```python
  # BEFORE (line 111):
  code.append("from typing import TypedDict, Optional, Any")

  # AFTER:
  code.append("from typing import TypedDict, Any")
  ```

- [x] 1.2.3 Fix line 122 - Optional syntax in generate_typed_dicts():
  ```python
  # BEFORE (line 122):
  field_type = f"Optional[{field_type}]"

  # AFTER:
  field_type = f"{field_type} | None"
  ```

- [x] 1.2.4 Fix line 138 - Accessor class imports in generate_accessor_classes():
  ```python
  # BEFORE (line 138):
  code.append("from typing import List, Optional, Dict, Any")

  # AFTER:
  code.append("from typing import Any")
  ```

- [x] 1.2.5 Fix lines 155, 171, 175 - Return type annotations:
  ```python
  # BEFORE:
  def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
  def get_by_{col}(cursor: sqlite3.Cursor, {col}: {type}) -> List[Dict[str, Any]]:

  # AFTER:
  def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
  def get_by_{col}(cursor: sqlite3.Cursor, {col}: {type}) -> list[dict[str, Any]]:
  ```

- [x] 1.2.6 Fix line 194 - Memory cache imports in generate_memory_cache():
  ```python
  # BEFORE (line 194):
  code.append("from typing import Dict, List, Any, Optional, DefaultDict")

  # AFTER:
  code.append("from typing import Any")
  code.append("from collections import defaultdict")
  ```

- [x] 1.2.7 Fix line 272 - Validator imports in generate_validators():
  ```python
  # BEFORE (line 272):
  code.append("from typing import Any, Callable, Dict")

  # AFTER:
  code.append("from typing import Any, Callable")
  ```

- [x] 1.2.8 Verify generator itself passes lint: **PASS** (codegen.py clean)
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  ruff check theauditor/indexer/schemas/codegen.py
  # Expected: No errors
  ```

### 1.3 Regenerate All Files
- [x] 1.3.1 Run the generator: **DONE** - all 4 files regenerated

- [x] 1.3.2 Verify generated files are clean: **859 issues remaining** (down from 3,157)
  - Note: Remaining issues are UP006/UP035/F401 in non-generated code that imports from these files

- [x] 1.3.3 Verify imports work: **PASS** - all imports successful, no F821 errors

- [x] 1.3.4 Verify pipeline still works: **PASS** - aud full --offline completed successfully

### 1.4 Commit Phase 1
- [x] 1.4.1 Commit changes: **9250d8d**
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  git add theauditor/indexer/schemas/codegen.py
  git add theauditor/indexer/schemas/generated_*.py
  git commit -m "refactor(codegen): output modern Python 3.9+ type syntax

  - Replace List/Dict/Optional with list/dict/| None
  - Update imports to use builtins instead of typing module
  - Regenerate all generated_*.py files with clean output

  Eliminates ~3,130 ruff issues from generated files."
  ```

---

## 2. The Great Purge (Dead Code Deletion)

### 2.1 Add `__all__` Declarations

These prevent false-positive F401 (unused import) warnings on intentional re-exports.

- [x] 2.1.1 `theauditor/ast_extractors/__init__.py`: **ALREADY HAS `__all__`** (verified 2025-11-25)
- [x] 2.1.2 `theauditor/indexer/__init__.py`: **ALREADY HAS `__all__`** (verified 2025-11-25)
- [x] 2.1.3 `theauditor/rules/__init__.py`: **ALREADY HAS `__all__`** (verified 2025-11-25)
- [x] 2.1.4 `theauditor/taint/__init__.py`: **ALREADY HAS `__all__`** (verified 2025-11-25)

### 2.2 Delete ZERO FALLBACK Violations

**CRITICAL:** For each file, follow this pattern:
1. Open file
2. Delete the exception handlers listed
3. Verify imports work: `python -c "import theauditor.<module>"`
4. Run: `aud full --offline`
5. If crashes, FIX THE ROOT CAUSE (don't restore the fallback)

#### 2.2.1 Clean `theauditor/fce.py`

- [x] 2.2.1.1 **ALREADY CLEAN** (verified 2025-11-26)
  - Verification: `grep -n "except.*json.JSONDecodeError" theauditor/fce.py` returned 0 matches
  - All JSON decode fallbacks removed in prior session

- [x] 2.2.1.2 **ALREADY CLEAN** (verified 2025-11-26)
  - No sqlite3.Error handlers found that violate ZERO FALLBACK policy

- [x] 2.2.1.3 Verification: **PASS** - import successful

#### 2.2.2 Clean `theauditor/context/query.py`

- [x] 2.2.2.1 **ALREADY CLEAN** (verified 2025-11-26)
  - Verification: `grep -n "except sqlite3.OperationalError" theauditor/context/query.py` returned 0 matches
  - All 32 OperationalError handlers removed in prior session

- [x] 2.2.2.2 Verification: **PASS** - import successful

#### 2.2.3 Clean `theauditor/rules/frameworks/express_analyze.py`

- [x] 2.2.3.1 **ALREADY CLEAN** (verified 2025-11-25)
  - Verification: `grep -n "except" theauditor/rules/frameworks/express_analyze.py` returned 0 matches
  - No exception handlers found in file - already compliant with ZERO FALLBACK policy

- [x] 2.2.3.2 Verification: **PASS** - import successful

#### 2.2.4 Clean `theauditor/rules/sql/sql_injection_analyze.py`

- [x] 2.2.4.1 **ALREADY CLEAN** (verified 2025-11-25)
  - Verification: `grep -n "except" theauditor/rules/sql/sql_injection_analyze.py` returned 0 matches
  - No exception handlers found in file - already compliant with ZERO FALLBACK policy

- [x] 2.2.4.2 Verification: **PASS** - import successful

### 2.3 Delete Unused Variables (F841) ✓ COMPLETE

**Date:** 2025-11-25
**Initial Count:** 70 F841 errors
**Final Count:** 0 F841 errors

- [x] 2.3.1 Initial count: **70 F841 errors**
- [x] 2.3.2 Classification per Lead Auditor Decision Log:
  - **Group 1 (Pure Deletion):** ~58 items - DELETE entire line
  - **Group 2 (Side Effect Extractors):** ~12 items - DELETE (extractors are pure readers)
  - **Group 3 (Cursors):** 6 items - DELETE `cursor = conn.cursor()` lines
  - **Group 4 (RuleContext):** 1 item - DELETE (dataclass-style context)

- [x] 2.3.3 Files Modified (manual Edit tool, file-by-file):
  ```
  theauditor\ast_extractors\python\operator_extractors.py - 3 dict literals removed
  theauditor\ast_extractors\typescript_impl_structure.py - base_name_for_enrichment
  theauditor\deps.py - 5x backup_path assignments
  theauditor\fce.py - workset variable
  theauditor\indexer\extractors\javascript.py - used_phase5_symbols
  theauditor\indexer\extractors\python.py - Exception as e -> Exception
  theauditor\rules\react\hooks_analyze.py - state_seen
  theauditor\rules\react\perf_analyze.py - expr_lower
  theauditor\rules\python\python_crypto_analyze.py - var_lower
  theauditor\rules\sql\multi_tenant_analyze.py - tenant_pattern
  theauditor\rules\vue\component_analyze.py - props_patterns
  theauditor\rules\vue\render_analyze.py - ops_placeholders
  theauditor\rules\xss\dom_xss_analyze.py - cursor
  theauditor\rules\xss\express_xss_analyze.py - cursor
  theauditor\rules\xss\react_xss_analyze.py - cursor
  theauditor\rules\xss\template_xss_analyze.py - unescaped_patterns, RENDER_FUNCTIONS
  theauditor\session\detector.py - 2x root_str
  theauditor\session\workflow_checker.py - query_run (2 occurrences)
  theauditor\taint\core.py - taint_paths
  theauditor\taint\discovery.py - query_lower
  theauditor\universal_detector.py - context (RuleContext)
  (plus ~50 additional files from prior session)
  ```

- [x] 2.3.4 Final Verification: **PASS**
  ```bash
  ruff check --select F841 theauditor
  # Result: All checks passed!
  ```

### 2.4 Delete Unused Imports (F401) - IN PROGRESS

**IMPORTANT:** Do this AFTER code deletion to avoid false positives.

**Approach:** Manual Edit tool, file-by-file with READ verification before each edit.
**Directive:** NO SCRIPTS, NO RUFF --FIX, NO AUTOMATION (Architect directive)

**Current Status (2025-11-26, Session 5):**
- Initial count: 731 F401 errors
- After Session 1: 655 F401 errors (76 fixed)
- After Session 2: 586 F401 errors (69 fixed)
- After Session 3: 274 F401 errors (312 fixed)
- After Session 4: 146 F401 errors (128 fixed)
- After Session 5 (partial): **91 F401 errors** (55 fixed this session)

**Directories COMPLETE (0 F401 errors):**
- ast_extractors/ (Session 2)
- commands/ (Session 3)
- rules/ (Session 3)
- context/ (Session 3)
- graph/ (Session 3)
- taint/ (Session 3)
- indexer/config.py (Session 3)
- indexer/schemas/ (Session 4 - Batch A)
- indexer/storage/ (Session 4 - Batch B)
- indexer/orchestrator.py (Session 4 - Batch C)
- indexer/database/ (Session 4 - Batch D partial)
- indexer/extractors/ (Session 4 - Batch D partial)

**Session 4 Commits:**
- `4a88dee` - refactor: remove unused imports from indexer/schemas and indexer/storage

**Critical Fixes Applied:**
- `typescript_impl.py`: Restored `import sys` (used 35+ times)
- `taint/__init__.py`: Fixed TaintPath import (was re-exported from core.py, moved to taint_path.py)
- Session 4: Fixed module-level `import os` in storage/base.py and storage/infrastructure_storage.py (local imports inside methods shadow module-level)
- Session 4: Moved ASTCache import from core.py to __init__.py (was re-exported, not used in core.py)

**Verification Method (Per Directive):**
1. READ file first
2. GREP for actual usage (not docstrings)
3. **GREP for re-exports** - check if other files import from this module
4. Verify imports work: `python -c "import theauditor.<module>"`
5. Run ruff check --select F401 on file

**Pipeline Verification:** `aud full --offline` - 25/25 phases PASS (2025-11-26 02:35)

- [x] 2.4.1 ast_extractors/ directory: **COMPLETE**
- [x] 2.4.2 commands/ directory: **COMPLETE**
- [x] 2.4.3 rules/ directory: **COMPLETE**
- [x] 2.4.4 context/ directory: **COMPLETE**
- [x] 2.4.5 graph/ directory: **COMPLETE**
- [x] 2.4.6 taint/ directory: **COMPLETE**
- [x] 2.4.7 indexer/ directory: **IN PROGRESS**
  - [x] 2.4.7.1 indexer/schemas/ (Batch A): **COMPLETE** - 24 errors fixed
  - [x] 2.4.7.2 indexer/storage/ (Batch B): **COMPLETE** - 21 errors fixed
  - [x] 2.4.7.3 indexer/orchestrator.py (Batch C): **COMPLETE** - 7 errors fixed
  - [x] 2.4.7.4 indexer/database/ (Batch D): **COMPLETE** - 25 errors fixed
  - [x] 2.4.7.5 indexer/extractors/ (Batch D): **COMPLETE** - 44 errors fixed
  - [ ] 2.4.7.6 indexer/core.py, metadata_collector.py, schema.py: **IN PROGRESS** - 21 errors remain
- [ ] 2.4.8 Remaining root files (~50 errors)

### 2.5 Commit Phase 2
- [ ] 2.5.1 Commit:
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  git add -A
  git commit -m "refactor: delete dead code and enforce ZERO FALLBACK policy

  - Remove ~100 silent exception handlers (fce.py, query.py, express_analyze.py, sql_injection_analyze.py)
  - Delete unused variables (F841)
  - Delete unused imports (F401)
  - Add __all__ declarations to define public APIs

  Per CLAUDE.md: One code path, crash if wrong, no safety nets."
  ```

---

## 3. Automated Modernization

### 3.1 Type Hint Modernization (UP006)
- [ ] 3.1.1 Count before: `ruff check theauditor --select UP006 --statistics`
- [ ] 3.1.2 Auto-fix: `ruff check theauditor --select UP006 --fix`
- [ ] 3.1.3 Verify: `.venv/Scripts/python.exe -c "import theauditor"`

### 3.2 Optional -> Union (UP045)
- [ ] 3.2.1 Count before: `ruff check theauditor --select UP045 --statistics`
- [ ] 3.2.2 Auto-fix: `ruff check theauditor --select UP045 --fix`
- [ ] 3.2.3 Verify: `.venv/Scripts/python.exe -c "import theauditor"`

### 3.3 Import Path Modernization (UP035)
- [ ] 3.3.1 Count before: `ruff check theauditor --select UP035 --statistics`
- [ ] 3.3.2 Auto-fix: `ruff check theauditor --select UP035 --fix`
- [ ] 3.3.3 Verify: `.venv/Scripts/python.exe -c "import theauditor"`

### 3.4 Whitespace Cleanup (W293)
- [ ] 3.4.1 Count before: `ruff check theauditor --select W293 --statistics`
- [ ] 3.4.2 Auto-fix: `ruff check theauditor --select W293 --fix`

### 3.5 Commit Phase 3
- [ ] 3.5.1 Commit:
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  git add -A
  git commit -m "refactor: modernize type hints to Python 3.9+ syntax

  - List[X] -> list[X]
  - Dict[K,V] -> dict[K,V]
  - Optional[X] -> X | None
  - from typing import List -> removed (use builtins)
  - Clean trailing whitespace"
  ```

---

## 4. Functional Integrity

### 4.1 Audit zip() Calls (B905)

- [ ] 4.1.1 Generate audit list:
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  ruff check theauditor --select B905 --output-format json > zip_audit.json
  ```

- [ ] 4.1.2 Review each call. Decision criteria:
  | Scenario | Action |
  |----------|--------|
  | `zip(list_a, list_b)` where mismatch = bug | Add `strict=True` |
  | `zip(range(n), items)` bounded iteration | Leave as-is |
  | Intentional truncation | Add comment: `# Intentional: truncates to shorter` |

- [ ] 4.1.3 Apply fixes manually (cannot auto-fix - requires judgment)

- [ ] 4.1.4 Verify: `aud full --offline`

### 4.2 Type Public API Boundaries

- [ ] 4.2.1 Type `theauditor/indexer/extractors/base.py`:
  - `BaseExtractor.extract(self, file_info: dict, content: str, tree: Any) -> dict`
  - `BaseExtractor.supported_extensions` property

- [ ] 4.2.2 Type `theauditor/indexer/database/__init__.py`:
  - Public `add_*` and `get_*` methods

- [ ] 4.2.3 Type `theauditor/graph/analyzer.py`:
  - `GraphAnalyzer.analyze()` and `GraphAnalyzer.build()`

- [ ] 4.2.4 Type `theauditor/taint/core.py`:
  - `TaintAnalyzer.analyze()` and `TaintAnalyzer.get_results()`

- [ ] 4.2.5 Type CLI commands in `theauditor/commands/*.py`

### 4.3 Commit Phase 4
- [ ] 4.3.1 Commit:
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  git add -A
  git commit -m "fix: add zip strict mode and type public API boundaries

  - Audit 853 zip() calls, add strict=True where data integrity required
  - Add type hints to public API interfaces (extractors, database, graph, taint)
  - DO NOT type internal helpers per design decision"
  ```

---

## 5. Final Validation

### 5.1 Full Pipeline Test
- [ ] 5.1.1 Run full pipeline:
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  aud full --offline
  ```

- [ ] 5.1.2 Run test suite:
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  pytest tests/ -v
  ```

- [ ] 5.1.3 Final ruff check:
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  ruff check theauditor --statistics 2>&1 | tee final_ruff.txt
  ```

### 5.2 Document Results

**Final Metrics (fill after 5.1.3):**
```
Date: ___________
Total ruff issues: ___ (was: ___)
Reduction: ___%

Phase 1 (generator): ___ issues eliminated
Phase 2 (dead code): ___ issues eliminated
Phase 3 (modernization): ___ issues eliminated
Phase 4 (integrity): ___ issues addressed
```

### 5.3 Merge Preparation
- [ ] 5.3.1 Squash if needed:
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  git rebase -i HEAD~4  # Squash 4 phase commits if desired
  ```

- [ ] 5.3.2 Create PR:
  ```bash
  cd C:/Users/santa/Desktop/TheAuditor-cleanup
  git push -u origin cleanup-ruff
  gh pr create --title "refactor: Context Hygiene Protocol cleanup" \
    --body "See openspec/changes/refactor-context-hygiene/ for full proposal"
  ```

- [ ] 5.3.3 Request review from Architect

---

## Rejected Tasks (Lead Auditor Decision)

The following were explicitly rejected as "developer fetish":

| Task | Rule | Verdict | Reason |
|------|------|---------|--------|
| Sort imports | I001 | **REJECTED** | Zero operational value, causes merge conflicts |
| Extract magic numbers | PLR2004 | **REJECTED** | Unless 3+ uses or security-critical |
| Type internal helpers | N/A | **REJECTED** | If AI can't understand 5 lines, function is the problem |
| Docstring formatting | N/A | **REJECTED** | Time sink for no AI benefit |
