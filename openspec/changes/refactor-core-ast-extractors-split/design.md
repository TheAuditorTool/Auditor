# Design: refactor-core-ast-extractors-split

**Type**: Pure Refactoring (Zero Functional Changes)
**Complexity**: Low-Medium (File splitting, no algorithm changes)
**Risk**: Low (Fully reversible, automated validation)

---

## Context

### Background

`core_ast_extractors.js` was created during Phase 5 refactor (2025-01-24) by extracting JavaScript extraction logic from Python into standalone JavaScript files. The file started at 1,628 lines with 14 extractor functions.

**Current State** (2025-11-01):
- **Size**: 2,376 lines (46% growth in 9 days)
- **Extractors**: 17 functions (3 undocumented additions)
- **Growth Rate**: ~83 lines/day
- **Policy Violation**: Exceeded 2,000 line threshold documented at line 35

**Growth Pattern**:
- 2025-01-24: 1,628 lines (Phase 5 baseline)
- 2025-11-01: 2,376 lines (+748 lines, +3 extractors from Python Phase 3)
- Projected: 3,000+ lines by 2025-11-09 if trend continues

### Constraints

**SACRED** (Read-Only):
- Function logic and signatures (zero functional changes allowed)
- JSDoc comments (must be preserved exactly)
- Function names (all 17 must remain identical)
- Assembly order (must work in any concatenation order)

**ALLOWED**:
- File organization (split into domain modules)
- File headers (update to reflect new structure)
- Orchestrator loading logic (load 3 files instead of 1)

### Stakeholders

- **Architect**: Requires ironclad implementation with no functional changes
- **Future AIs**: Must be able to execute mechanically from tasks.md
- **Taint Analysis**: Depends on data flow extractors (must remain functional)
- **Framework Extractors**: Depend on core language extractors (must remain available)

---

## Goals / Non-Goals

### Goals

1. **Maintainability**: Reduce cognitive load by splitting 2,376-line file into ~660-950 line domain modules
2. **Scalability**: Enable independent growth of each domain without hitting 2,000 line limit
3. **Consistency**: Match existing JavaScript extractor organization (security, framework, sequelize, etc. are domain-separated)
4. **Zero Regressions**: Database row counts must be identical before/after (automated validation)

### Non-Goals

1. ❌ Change extraction logic (zero functional changes)
2. ❌ Optimize performance (pure organization refactor)
3. ❌ Add new extractors (preserve existing 17)
4. ❌ Modify database schema (no table changes)
5. ❌ Change public API (batch assembly interface unchanged)

---

## Decisions

### Decision 1: 3-File Split (Core Language, Data Flow, Module/Framework)

**Options Considered**:
1. Keep monolithic (1 file, 2,376 lines)
2. Split by extractor (17 files, ~140 lines each)
3. Split by domain (3 files, ~660-950 lines each) ← **CHOSEN**
4. Split by API usage (2 files: TypeChecker vs AST-only)

**Decision**: 3-file domain split

**Reasoning**:
- **Clear boundaries**: Language structure vs data flow vs imports/frameworks align with domain expertise
- **Balanced sizes**: ~660-950 lines per file (none exceed 1,000 line threshold)
- **Proven pattern**: Matches existing JavaScript extractor organization (security, framework, sequelize, bullmq, angular)
- **Maintainability**: Developers can locate extractors by domain without scanning 2,376 lines

**Alternatives Rejected**:
- **Option 1 (Monolithic)**: Technical debt compounds, file growing at 83 lines/day, same pattern that forced storage.py refactor
- **Option 2 (17 files)**: Over-engineered, excessive file count for simple pure functions
- **Option 4 (API split)**: Doesn't align with domain concerns, unclear boundaries

**Trade-offs**:
- **Benefit**: Developer productivity (find extractors faster)
- **Cost**: Upfront refactor effort (estimated 3 hours)

---

### Decision 2: Grep-Based Extraction (No Line Numbers)

**Options Considered**:
1. Manual extraction by line numbers (tasks.md specifies lines 215-440, etc.)
2. Grep-based extraction by JSDoc comments ← **CHOSEN**
3. Script-based extraction (write Python script to parse and split file)

**Decision**: Grep-based extraction by JSDoc comments

**Reasoning**:
- **Resilient**: File can change between proposal and implementation without breaking extraction
- **Mechanical**: AI can search for "Extract function metadata" JSDoc and copy to closing brace
- **Verifiable**: Function signatures can be verified after extraction (no judgment calls)

**Alternatives Rejected**:
- **Option 1 (Line numbers)**: Fragile - if anyone adds a comment, line numbers are wrong
- **Option 3 (Script)**: Over-engineered for one-time refactor, adds maintenance burden

**Implementation**:
```bash
# Search for JSDoc comment pattern
# Example: "Extract function metadata directly from TypeScript AST"
# Copy from /** to closing } of function
# Verify function signature matches: function extractFunctions(sourceFile, checker, ts)
```

---

### Decision 3: Database Row Count Validation (MANDATORY)

**Options Considered**:
1. Manual testing (run `aud index`, eyeball results)
2. Database row count comparison (before/after diffs) ← **CHOSEN**
3. Full regression test suite (write unit tests for each extractor)

**Decision**: Automated database row count comparison

**Reasoning**:
- **Comprehensive**: Covers all 7 tables populated by extractors
- **Automated**: `diff` command shows ANY difference (zero tolerance)
- **Fast**: Run in <2 minutes (vs hours for full test suite)
- **Objective**: No interpretation needed - identical counts = success

**Implementation**:
```bash
# Before refactor
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM function_call_args;" > /tmp/before_calls.txt

# After refactor
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM function_call_args;" > /tmp/after_calls.txt

# Validation (MUST show no output)
diff /tmp/before_calls.txt /tmp/after_calls.txt
```

**Fail-Fast**: If ANY diff shows output, ROLLBACK immediately and investigate bug

---

### Decision 4: Windows Path Standardization (Backslashes in Docs)

**Options Considered**:
1. Use forward slashes (POSIX-style: `C:/Users/santa/...`)
2. Use backslashes (Windows-style: `C:\Users\santa\...`) ← **CHOSEN**
3. Mixed usage (forward in code, backslashes in docs)

**Decision**: Backslashes in all documentation

**Reasoning**:
- **Architect Mandate**: "always use complete absolute Windows paths with drive letters and backslashes"
- **Consistency**: Match architect's preferred format in all docs
- **Clarity**: No confusion about when to use which style

**Note**: In actual bash execution, forward slashes work fine (WSL environment). Backslashes are for documentation only.

---

## Technical Architecture

### File Distribution

| File | Lines | Extractors | Domain | Dependencies |
|------|-------|------------|--------|--------------|
| `core_language.js` | ~660 | 6 | Language structure & scope | None (foundation) |
| `data_flow.js` | ~947 | 6 | Data flow & taint analysis | core_language (scopeMap) |
| `module_framework.js` | ~769 | 5 | Imports & framework patterns | None (standalone) |

### Extractor Assignments

**core_language.js** (Language Structure):
1. `extractFunctions()` - Function metadata with type annotations
2. `extractClasses()` - Class declarations and expressions
3. `extractClassProperties()` - Class field declarations
4. `buildScopeMap()` - Line-to-function mapping for scope context
5. `serializeNodeForCFG()` - AST serialization (legacy, minimal)
6. `countNodes()` - AST complexity metrics (utility)

**data_flow.js** (Data Flow):
1. `extractCalls()` - Call expressions and property accesses
2. `extractAssignments()` - Variable assignments with data flow
3. `extractFunctionCallArgs()` - Function call arguments (foundation for taint)
4. `extractReturns()` - Return statements with scope
5. `extractObjectLiterals()` - Object literals for dynamic dispatch
6. `extractVariableUsage()` - Variable reference tracking (utility)

**module_framework.js** (Imports & Frameworks):
1. `extractImports()` - Import/require/dynamic import detection
2. `extractEnvVarUsage()` - Environment variable usage patterns
3. `extractORMRelationships()` - ORM relationship declarations
4. `extractImportStyles()` - Bundle optimization analysis (utility)
5. `extractRefs()` - Module resolution mappings for cross-file analysis

### Assembly Flow

```
js_helper_templates.py::get_batch_helper()
  ↓
Load core_language.js (foundation layer)
  ↓
Load data_flow.js (analysis layer - depends on scopeMap from core_language)
  ↓
Load module_framework.js (integration layer - standalone)
  ↓
Concatenate: core_language + data_flow + module_framework + security + framework + ... + batch_template
  ↓
Return assembled JavaScript batch script
```

**Order Independence**: All 17 extractors are pure functions with no inter-dependencies. `buildScopeMap()` is called externally by batch template, and result is passed as argument to extractors that need it. Therefore, concatenation order does not affect correctness (only matters for readability).

---

## Data Flow

### Current (Monolithic)

```
orchestrator.py
  ↓ call get_batch_helper('module')
js_helper_templates.py
  ↓ load core_ast_extractors.js (single file)
_JS_CACHE['core_ast_extractors']
  ↓ concatenate with security, framework, etc.
Assembled batch script (17 extractors available)
  ↓ execute via Node.js subprocess
TypeScript API extraction
  ↓ write to database
repo_index.db (7 tables populated)
```

### After Refactor

```
orchestrator.py
  ↓ call get_batch_helper('module')
js_helper_templates.py
  ↓ load 3 files (core_language, data_flow, module_framework)
_JS_CACHE['core_language'] + _JS_CACHE['data_flow'] + _JS_CACHE['module_framework']
  ↓ concatenate with security, framework, etc.
Assembled batch script (17 extractors available - SAME AS BEFORE)
  ↓ execute via Node.js subprocess
TypeScript API extraction (IDENTICAL LOGIC)
  ↓ write to database
repo_index.db (7 tables populated - IDENTICAL COUNTS)
```

**Verification Point**: Database row counts MUST be identical. This proves zero functional changes.

---

## Risks / Trade-offs

### Risk 1: Copy-Paste Extraction Errors

**Risk**: Manual extraction could introduce syntax errors or miss nested functions

**Impact**: Medium (TypeScript compilation fails, extractors missing)

**Likelihood**: Low (grep-based approach with function signature verification)

**Mitigation**:
- Section 2.8, 3.8, 4.7: Count functions and verify names after each extraction
- Section 6.1: TypeScript compilation errors will be visible in `aud index --verbose` output
- Section 6.4: Grep assembled script for all 17 function definitions

**Rollback**: If extraction fails, delete partial file and retry from step 2.1/3.1/4.1

---

### Risk 2: Orchestrator Update Breaks Loading

**Risk**: Python string replacements in js_helper_templates.py could be incorrect

**Impact**: High (batch script fails to assemble, extraction broken)

**Likelihood**: Low (exact string match with Edit tool, Python syntax validation)

**Mitigation**:
- Section 5.5: `python -m py_compile` catches syntax errors before testing
- Section 6.4: Assembled script verification shows if extractors missing
- Section 5 uses Edit tool with exact string matching (no manual typing)

**Rollback**: Restore js_helper_templates.py from git checkout

---

### Risk 3: Database Row Count Regression

**Risk**: Subtle logic change during extraction alters behavior

**Impact**: Critical (false negatives in security analysis, data loss)

**Likelihood**: Very Low (pure copy-paste, no logic changes)

**Mitigation**:
- Section 6.3: Mandatory before/after diff for 7 tables (zero tolerance)
- Section 6.5: Test on additional fixtures (React, Vue, TypeScript)
- FAIL-FAST: Any difference triggers immediate rollback

**Rollback**: Full rollback via Appendix A (restore .bak, revert orchestrator)

---

## Migration Plan

### Phase 1: State Verification (Section 0.5)
- Verify file line count (2,376 ± 50 lines)
- Verify extractor count (17 functions)
- Verify growth policy documented (line ~35)
- **GATE**: If any check fails, STOP and re-verify proposal

### Phase 2: Pre-Flight (Section 1)
- Create backup file (.bak)
- Capture baseline database counts (7 tables)
- Verify git working directory clean

### Phase 3: Extraction (Sections 2-4)
- Create 3 new files (core_language, data_flow, module_framework)
- Extract 17 functions using grep-based JSDoc search
- Verify function counts and signatures after each file
- **ROLLBACK POINTS**: Delete partial file and retry if extraction fails

### Phase 4: Orchestrator Update (Section 5)
- Update _JS_CACHE dictionary (3 new entries)
- Update _load_javascript_modules() (load 3 files)
- Update get_batch_helper() assembly (concatenate 3 files)
- Verify Python syntax with py_compile

### Phase 5: Validation (Section 6)
- Re-run `aud index` with new extractors
- Capture post-refactor database counts
- **CRITICAL**: Diff all 7 tables (MUST be identical)
- Verify assembled script contains all 17 extractors
- **GATE**: If ANY diff or missing extractor, ROLLBACK and investigate

### Phase 6: Audit & Cleanup (Sections 7-8)
- Re-read all modified files (teamsop.md compliance)
- Delete original core_ast_extractors.js
- Create git commit (no Claude co-author per architect mandate)

---

## Rollback Strategy

### Immediate Rollback (Mid-Phase Failure)

**Phase 2 Failure** (Extraction):
```bash
rm theauditor\ast_extractors\javascript\core_language.js
# Retry from step 2.1
```

**Phase 5 Failure** (Validation regression):
```bash
# Restore orchestrator
git checkout theauditor\ast_extractors\js_helper_templates.py

# Delete new files
rm theauditor\ast_extractors\javascript\core_language.js
rm theauditor\ast_extractors\javascript\data_flow.js
rm theauditor\ast_extractors\javascript\module_framework.js

# Restore original
cp theauditor\ast_extractors\javascript\core_ast_extractors.js.bak theauditor\ast_extractors\javascript\core_ast_extractors.js
```

### Full Rollback (Complete Reversion)

See **Appendix A** in tasks.md for complete rollback procedure.

**Verification After Rollback**:
```bash
# Clean database
rm -rf .pf

# Re-index with original file
aud index tests\fixtures\javascript\ --verbose

# Verify identical to baseline
diff /tmp/before_calls.txt /tmp/after_rollback_calls.txt  # Should be empty
```

---

## Open Questions

**Q1**: Should we create a Python script to automate extraction?

**A1**: NO. Grep-based manual extraction is sufficient for one-time refactor. Script adds maintenance burden.

**Q2**: Should we create unit tests for each extractor?

**A2**: NO (out of scope). Database row count comparison is sufficient validation for refactor. Unit tests would be useful for future changes, but not required for this refactor.

**Q3**: Should we update file headers in core_ast_extractors.js before splitting?

**A3**: NO. File will be deleted after refactor. New files get updated headers during creation.

**Q4**: Should we use Windows backslashes in actual bash commands?

**A4**: NO. WSL bash environment requires forward slashes in commands. Backslashes are for documentation paths only (per architect preference).

---

## Success Metrics

1. ✅ All 7 database row count diffs show ZERO differences
2. ✅ TypeScript compiles with zero errors
3. ✅ Assembled batch script contains all 17 extractors (verified by grep)
4. ✅ File sizes reasonable (~660-950 lines, all under 1,000 line threshold)
5. ✅ Post-implementation audit finds no syntax errors
6. ✅ Git commit created without Claude co-author tag

---

## References

- **Original File**: `theauditor/ast_extractors/javascript/core_ast_extractors.js` (2,376 lines)
- **Orchestrator**: `theauditor/ast_extractors/js_helper_templates.py` (259 lines)
- **Growth Policy**: Line 35 of core_ast_extractors.js
- **Refactor Precedents**:
  - `refactor-storage-domain-split` (storage.py 2,127 lines → 5 modules)
  - `refactor-taint-schema-driven-architecture` (taint 8,691 lines → 3 layers)
- **Team SOP**: teamsop.md v4.20 Template C-4.20
