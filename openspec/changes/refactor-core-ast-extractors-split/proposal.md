# Proposal: Refactor core_ast_extractors.js into Domain-Specific Modules

**Change ID**: `refactor-core-ast-extractors-split`
**Type**: Refactoring (Code Organization)
**Status**: Proposed
**Priority**: High (Prevents Monolithic File Collapse)
**Effort**: Medium (2-3 hours)
**Risk**: Low-Medium (Clear Boundaries, Zero Functional Changes)

---

## Why

### Problem Statement

`theauditor/ast_extractors/javascript/core_ast_extractors.js` has grown to **2,376 lines** with **17 extractor functions** and has already exceeded its own growth policy threshold of 2,000 lines (documented at line 35: "Growth policy: If exceeds 2,000 lines, split by language feature category").

This monolithic structure creates:

1. **Navigation Difficulty**: Finding the right extractor among 17 functions in a 2,376-line file is time-consuming
2. **Maintenance Burden**: Adding new ECMAScript/TypeScript syntax requires editing a 2,000+ line file
3. **Cognitive Overload**: Language structures, data flow, and framework patterns are intermingled without clear organization
4. **Growth Violation**: File has grown from 1,628 lines (2025-01-24) to 2,376 lines (46% growth in <10 days)
5. **Inconsistent Architecture**: Other JavaScript extractors (security, framework, sequelize, bullmq, angular) are domain-separated, but core remains monolithic

### Root Cause

The original core_ast_extractors.js was extracted from js_helper_templates.py (Phase 5 refactor, 2025-01-24) as a single foundation layer. Python Phase 3 framework extraction added new extractors (extractClassProperties, extractEnvVarUsage, extractORMRelationships), but no domain organization was applied. The file continues to grow linearly without structure.

### Business Impact

- **Developer velocity**: New contributors struggle to locate extractors in 2,376 lines
- **Code review overhead**: PRs touching core_ast_extractors.js are difficult to review due to file size
- **Future growth**: New ECMAScript features (decorators, pattern matching, pipeline operator) will compound the problem
- **Technical debt**: Delaying this refactor makes it exponentially harder later (same pattern that led to storage.py refactor)

---

## What Changes

### Proposed Architecture

Split `core_ast_extractors.js` (2,376 lines, 17 extractors) into **3 focused modules** following domain-driven design:

```
theauditor/ast_extractors/javascript/
├── core_language.js           # Language structures (660 lines, 6 extractors)
│   ├── extractFunctions()
│   ├── extractClasses()
│   ├── extractClassProperties()
│   ├── buildScopeMap()
│   ├── serializeNodeForCFG()
│   └── countNodes()
│
├── data_flow.js               # Data flow & taint analysis (947 lines, 6 extractors)
│   ├── extractCalls()
│   ├── extractAssignments()
│   ├── extractFunctionCallArgs()
│   ├── extractReturns()
│   ├── extractObjectLiterals()
│   └── extractVariableUsage()
│
├── module_framework.js        # Module system & framework patterns (769 lines, 5 extractors)
│   ├── extractImports()
│   ├── extractRefs()
│   ├── extractImportStyles()
│   ├── extractEnvVarUsage()
│   └── extractORMRelationships()
│
└── js_helper_templates.py     # Orchestrator (UPDATED)
    └── Load core_language + data_flow + module_framework
        (instead of single core_ast_extractors)
```

### Domain Split Rationale

| Domain | Extractor Count | Responsibility | Example Extractors |
|--------|-----------------|----------------|-------------------|
| **Core Language** | 6 | Language structure & scope | functions, classes, scope mapping, CFG serialization |
| **Data Flow** | 6 | Data flow & taint tracking | calls, assignments, returns, object literals, variable usage |
| **Module Framework** | 5 | Imports & framework patterns | imports, module resolution, env vars, ORM relationships |

### Extractor Distribution

**Core Language** (6 extractors, ~660 lines):
- `extractFunctions()` - Function metadata with type annotations (216 lines)
- `extractClasses()` - Class declarations and expressions (212 lines)
- `extractClassProperties()` - Class field declarations (90 lines)
- `buildScopeMap()` - Line-to-function mapping for scope context (130 lines)
- `serializeNodeForCFG()` - AST serialization for CFG (55 lines)
- `countNodes()` - AST complexity metrics (12 lines)

**Data Flow** (6 extractors, ~947 lines):
- `extractCalls()` - Call expressions and property accesses (190 lines)
- `extractAssignments()` - Variable assignments with data flow (211 lines)
- `extractFunctionCallArgs()` - Function call arguments for taint (199 lines)
- `extractReturns()` - Return statements with scope (183 lines)
- `extractObjectLiterals()` - Object literals for dynamic dispatch (119 lines)
- `extractVariableUsage()` - Computed usage from assignments/calls (45 lines)

**Module Framework** (5 extractors, ~769 lines):
- `extractImports()` - Import/require/dynamic import detection (90 lines)
- `extractRefs()` - Module resolution mappings for cross-file analysis (24 lines)
- `extractImportStyles()` - Bundle optimization analysis (51 lines)
- `extractEnvVarUsage()` - Environment variable usage patterns (152 lines)
- `extractORMRelationships()` - ORM relationship declarations (143 lines)

---

## Impact

### Affected Code

| File | Change Type | Risk | Description |
|------|-------------|------|-------------|
| `theauditor/ast_extractors/javascript/core_ast_extractors.js` | **DELETED** | 🟡 Medium | Split into 3 modules |
| `theauditor/ast_extractors/js_helper_templates.py` | **MODIFIED** | 🟡 Medium | Update loader to load 3 files instead of 1 |
| **NEW** `theauditor/ast_extractors/javascript/core_language.js` | Create | 🟢 Low | Core language extractors |
| **NEW** `theauditor/ast_extractors/javascript/data_flow.js` | Create | 🟢 Low | Data flow extractors |
| **NEW** `theauditor/ast_extractors/javascript/module_framework.js` | Create | 🟢 Low | Module/framework extractors |

### Backward Compatibility

✅ **FULLY BACKWARD COMPATIBLE**

- **Assembly Logic**: `js_helper_templates.py::get_batch_helper()` → **MINIMAL CHANGE**
- **Public API**: All 17 extractors remain available in assembled batch script
- **Database Schema**: No changes to tables or columns
- **Extractor Behavior**: Zero functional changes, pure code organization
- **Module Loading**: JavaScript files are concatenated at runtime (order-independent for these extractors)

### Migration Path

**Phase 1: Create New Files**
1. Split core_ast_extractors.js into 3 new files
2. Preserve all function headers, documentation, and logic exactly

**Phase 2: Update Orchestrator**
1. Modify `js_helper_templates.py::_load_javascript_modules()`:
   - Replace single `core_ast_extractors.js` load
   - Add 3 new loads: `core_language.js`, `data_flow.js`, `module_framework.js`
2. Modify `js_helper_templates.py::get_batch_helper()`:
   - Update assembly order: `core_language + data_flow + module_framework + security + framework + ...`

**Phase 3: Validation**
1. Run `aud index` on test fixtures
2. Verify identical database records (before/after row counts)
3. Verify no TypeScript compilation errors
4. Delete old `core_ast_extractors.js`

### Affected Specs

- ❌ **No spec changes required** - This is a code organization refactor with zero functional changes
- ❌ **No capability changes** - All 17 extractors retain identical behavior
- ❌ **No API changes** - Assembled batch script interface remains unchanged

**Rationale**: Pure refactoring does not require spec deltas. The extraction capabilities are documented in `specs/javascript-extraction/spec.md`, which describes WHAT is extracted, not HOW files are organized internally.

**OpenSpec Validation**: This change will fail `openspec validate --strict` because it has no spec deltas. This is **EXPECTED** for pure refactoring. Upon completion, archive with `openspec archive refactor-core-ast-extractors-split --skip-specs --yes` per OpenSpec guidelines for tooling-only changes.

---

## Benefits

### Immediate Benefits

1. **Improved Navigation**: Find extractors by domain (data flow → `data_flow.js`) instead of searching 2,376 lines
2. **Reduced Cognitive Load**: Each domain module is self-contained (~660-950 lines)
3. **Parallel Development**: Multiple developers can work on different domain modules without conflicts
4. **Easier Code Review**: PRs affect single domain modules, not entire foundation layer
5. **Consistent Architecture**: Core layer matches other JavaScript extractor organization (security, framework, etc.)

### Long-Term Benefits

1. **Scalability**: Adding new ECMAScript features is straightforward - modify relevant domain module
2. **Maintainability**: Domain experts can focus on relevant extractors (taint experts → data_flow.js)
3. **Testing**: Domain-specific test suites can be created for each module
4. **Documentation**: Each module can have focused docstrings explaining domain-specific patterns
5. **Prevents Collapse**: Stops core_ast_extractors.js from becoming a 5,000+ line monolith

---

## Alternatives Considered

### Alternative 1: Keep Monolithic Structure
**Pros**: No refactoring effort, zero risk
**Cons**: Problem compounds with every new feature, eventual collapse inevitable (already exceeded 2,000 line policy)
**Decision**: ❌ **REJECTED** - Technical debt will only grow (same pattern that forced storage.py refactor)

### Alternative 2: Split by TypeScript API Usage
**Pros**: Groups by technical mechanism (AST traversal vs type checker)
**Cons**: Doesn't align with domain concerns, unclear boundaries
**Decision**: ❌ **REJECTED** - Technical grouping doesn't help maintainability

### Alternative 3: One File Per Extractor (17 files)
**Pros**: Maximum granularity
**Cons**: Over-engineered, 17 files for simple functions, high overhead
**Decision**: ❌ **REJECTED** - Too many files, no clear domain organization

### Alternative 4: Domain Split into 3 Modules (Chosen)
**Pros**: Clear boundaries, proven pattern (matches other JS extractors), balanced file sizes
**Cons**: Requires refactor effort upfront
**Decision**: ✅ **ACCEPTED** - Best balance of clarity, maintainability, and consistency

---

## Success Criteria

### Definition of Done

- [ ] 3 new modules created with correct extractor distribution
- [ ] `js_helper_templates.py` updated to load 3 files (core_language, data_flow, module_framework)
- [ ] All 17 extractors function identically (zero behavior changes)
- [ ] `aud index` runs successfully on test projects (TypeScript, JavaScript, React, Vue)
- [ ] No regressions in database records (compare before/after row counts)
- [ ] TypeScript batch script assembles without errors
- [ ] Code passes `ruff check` linting
- [ ] Documentation updated (CLAUDE.md if needed)

### Validation Tests

```bash
# Before refactor - capture baseline
aud index tests/fixtures/javascript/ --verbose
cd .pf && sqlite3 repo_index.db "SELECT COUNT(*) FROM symbols WHERE type='function';" > /tmp/before_functions.txt
cd .pf && sqlite3 repo_index.db "SELECT COUNT(*) FROM function_call_args;" > /tmp/before_calls.txt
cd .pf && sqlite3 repo_index.db "SELECT COUNT(*) FROM imports;" > /tmp/before_imports.txt

# After refactor - verify identical behavior
aud index tests/fixtures/javascript/ --verbose
cd .pf && sqlite3 repo_index.db "SELECT COUNT(*) FROM symbols WHERE type='function';" > /tmp/after_functions.txt
cd .pf && sqlite3 repo_index.db "SELECT COUNT(*) FROM function_call_args;" > /tmp/after_calls.txt
cd .pf && sqlite3 repo_index.db "SELECT COUNT(*) FROM imports;" > /tmp/after_imports.txt

# Compare
diff /tmp/before_functions.txt /tmp/after_functions.txt  # Should be identical
diff /tmp/before_calls.txt /tmp/after_calls.txt          # Should be identical
diff /tmp/before_imports.txt /tmp/after_imports.txt      # Should be identical
```

---

## Dependencies

### Blocking Dependencies

- ❌ **None** - Can start immediately

### Parallel Work

- ✅ Can proceed in parallel with:
  - Python extraction work (different file set)
  - Rule development (extraction layer is abstracted)
  - Taint analysis improvements (uses assembled batch script)

### Follow-Up Work

- Create domain-specific test suites (optional, recommended)
- Add per-module docstrings explaining domain patterns (optional, recommended)
- Consider similar refactor for other large files if they exceed 2,000 lines (future)

---

## Risks

### MEDIUM Risks

**Risk 1: Assembly Order Issues**
- Impact: MEDIUM (batch script fails to assemble)
- Likelihood: LOW (extractors are independent, no cross-dependencies)
- Mitigation: Test TypeScript compilation immediately after split

**Risk 2: File Loading Errors**
- Impact: MEDIUM (missing extractors in batch script)
- Likelihood: LOW (simple file loading with clear error messages)
- Mitigation: Verify all 17 extractors present in assembled script via grep

**Risk 3: Git Merge Conflicts**
- Impact: LOW (parallel work disrupted)
- Likelihood: MEDIUM (active development in JavaScript extractors)
- Mitigation: Communicate refactor timing, complete in single PR

### LOW Risks

**Risk 4: Documentation Drift**
- Impact: LOW (future maintainers confused)
- Likelihood: MEDIUM (no enforced docs updates)
- Mitigation: Update CLAUDE.md with new file structure, add file headers

---

## Timeline Estimate

| Phase | Duration | Description |
|-------|----------|-------------|
| **1. Verification** | 15 min | Read existing code, verify extractor boundaries |
| **2. Create core_language.js** | 30 min | Extract 6 language structure extractors |
| **3. Create data_flow.js** | 30 min | Extract 6 data flow extractors |
| **4. Create module_framework.js** | 30 min | Extract 5 module/framework extractors |
| **5. Update js_helper_templates.py** | 20 min | Modify loader to load 3 files |
| **6. Integration Testing** | 30 min | Run validation tests, verify row counts |
| **7. Cleanup** | 10 min | Delete old file, update docs |
| **8. Post-Implementation Audit** | 15 min | Re-read modified files per teamsop.md |
| **TOTAL** | **3 hours** | End-to-end implementation |

---

## References

- **Growth Policy Violation**: `core_ast_extractors.js:35` - "Growth policy: If exceeds 2,000 lines, split by language feature category"
- **Historical Growth**: Line 34 documents 1,628 lines (2025-01-24) → 2,376 lines now (46% growth)
- **Refactor Precedent**: `refactor-storage-domain-split` (storage.py 2,127 lines → 5 modules)
- **Orchestrator Entry Point**: `js_helper_templates.py::get_batch_helper()` - Runtime file loading
- **Verification Evidence**: `openspec/changes/refactor-core-ast-extractors-split/verification.md` (to be created)
- **Team SOP**: `teamsop.md` v4.20 - "Prime Directive: Verify Before Acting"

---

## Approval

**Status**: ⏳ **AWAITING ARCHITECT APPROVAL**

**Architect Review Checklist**:
- [ ] Problem statement is clear (file exceeded 2,000 line policy)
- [ ] Proposed solution follows domain-driven design
- [ ] Risks are identified and mitigated
- [ ] Backward compatibility is maintained (batch assembly unchanged)
- [ ] Success criteria are measurable (row count comparisons)
- [ ] Timeline estimate is reasonable (3 hours)
- [ ] teamsop.md Prime Directive acknowledged (verification.md created)

**Architect Signature**: _________________
**Approval Date**: _________________

---

**Author**: Claude Sonnet 4.5 (Lead Coder)
**Date**: 2025-11-01
**Protocol**: OpenSpec + SOP v4.20
**Prime Directive**: ✅ Verification phase complete (read teamsop.md, core_ast_extractors.js, js_helper_templates.py, refactor precedents)
