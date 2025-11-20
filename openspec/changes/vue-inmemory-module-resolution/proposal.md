# Vue In-Memory Compilation + Node Module Resolution

**Status**: 🔴 PROPOSAL - Awaiting Architect approval

**Parent Proposal**: `performance-revolution-now` (TIER 1 Tasks 3 & 4)

**Assigned to**: AI #3 (Sonnet recommended - medium complexity)

**Timeline**: 3-4 days (2-3 days implementation + 1 day testing)

**Impact**: 🟡 **MEDIUM** - Vue: 6-10 seconds saved per 100 files + Module resolution: 40-60% accuracy improvement

---

## Why

### **Problem 1: Vue SFC Compilation Disk I/O Overhead**

Vue Single File Component (SFC) compilation currently writes to disk, compiles, reads back, then deletes:

```javascript
// BEFORE (3 disk operations per .vue file):
fs.writeFileSync(tempPath, vueContent);           // 35ms
const compiled = compileVueSFC(tempPath);        // 50ms
const result = fs.readFileSync(tempPath);        // 10ms
fs.unlinkSync(tempPath);                         // (cleanup)
// Total: 35-95ms per file (disk I/O dominates)
```

**Impact**: On 100 Vue files → 3.5-9.5 seconds wasted on unnecessary disk I/O

### **Problem 2: Broken Import Resolution**

JavaScript/TypeScript import resolution is broken, resolving only 40-60% of imports:

```python
# BEFORE (javascript.py:748-768):
imp_path.split('/')[-1]  # Only gets basename, misses:
# - Relative imports (./utils/validation)
# - Path mappings (@/components)
# - node_modules (lodash, react)
# - index.js/ts resolution
```

**Impact**: 40-60% of imports unresolved → cross-file taint analysis fails → false negatives (missed vulnerabilities)

---

## What Changes

### **Task 3: Vue In-Memory Compilation** (4-6 hours)

**File**: `theauditor/extractors/js/batch_templates.js:119-175`

**Change**: Pass compiled code directly to TypeScript API (no disk writes)

```javascript
// BEFORE (3 disk operations):
fs.writeFileSync(tempPath, compiled);
const result = ts.createSourceFile(tempPath, ...);
fs.unlinkSync(tempPath);

// AFTER (in-memory):
const compiled = compileVueSFC(vueContent);  // In-memory compilation
const result = ts.createSourceFile(
    `/virtual/${scopeId}.js`,  // Virtual path
    compiled.script,           // In-memory content
    ts.ScriptTarget.Latest
);
```

**Impact**: 35-95ms → 10-20ms per .vue file (60-80% faster)

### **Task 4: Node Module Resolution** (1-2 weeks)

**File**: `theauditor/indexer/extractors/javascript.py:748-768`

**Change**: Implement proper TypeScript module resolution algorithm

```python
# BEFORE (basename only):
target = imp_path.split('/')[-1]  # 40-60% resolution rate

# AFTER (full resolution):
def resolve_import(import_path, from_file):
    # 1. Relative imports (./foo, ../bar)
    if import_path.startswith('.'):
        return resolve_relative(import_path, from_file)

    # 2. Path mappings (@/components → src/components)
    if '@' in import_path or '~' in import_path:
        return resolve_path_mapping(import_path, tsconfig)

    # 3. node_modules lookup
    return resolve_node_modules(import_path, from_file)
```

**Impact**: 40-60% → 80-90% import resolution rate (critical for cross-file taint)

---

## Impact

### **Affected Code**

**Modified Files**:
- `theauditor/extractors/js/batch_templates.js` - Vue compilation (50 lines modified)
- `theauditor/indexer/extractors/javascript.py:748-768` - Module resolution (200 lines modified)

**Read-Only** (for understanding):
- `theauditor/extractors/js/js_helper_templates.py` - Template system
- `theauditor/extractors/js/typescript_impl.js` - TypeScript API

### **Breaking Changes**

**None** - External API preserved:
- Vue extraction output format unchanged
- Import resolution format unchanged (just more imports resolved)
- Database schema unchanged

### **Coordination Point with AI #4**

⚠️ **CONFLICT**: Both AI #3 and AI #4 touch `javascript.py`
- **AI #3**: Lines 748-768 (module resolution)
- **AI #4**: Line 1288 (parameters normalization)

**Merge Strategy**: Apply both changes, different line ranges (safe)

### **Performance Targets**

**Vue Compilation**:
- Before: 9 seconds per 100 .vue files
- After: 3 seconds per 100 .vue files
- Speedup: 3x (70% improvement)

**Module Resolution**:
- Before: 40-60% imports resolved
- After: 80-90% imports resolved
- Improvement: 40-60% more imports (critical for taint accuracy)

### **Risk Assessment**

**Complexity**: 🟡 **MEDIUM** - Requires JavaScript/TypeScript knowledge

**Risks**:
1. **Vue**: In-memory compilation might miss edge cases (script setup, TypeScript)
2. **Module Resolution**: TypeScript algorithm is complex (100+ edge cases)

**Mitigation**:
- Test on 10+ Vue fixture projects (Vue 2, Vue 3, TypeScript)
- Test module resolution on diverse projects (monorepos, path mappings, etc.)

---

## Dependencies

**Prerequisites**:
- ✅ TypeScript API available (`typescript_impl.js`)
- ✅ Vue SFC compiler available

**Required Reading** (BEFORE coding):
1. `performance-revolution-now/INVESTIGATION_REPORT.md` sections 4.1-4.2 (JavaScript findings)
2. `performance-revolution-now/design.md` sections 3.1-3.2 (Vue + module resolution design)
3. This proposal's `tasks.md` sections 3.1-3.5 (Vue) and 4.1-4.7 (module resolution)
4. `teamsop.md` v4.20 (Prime Directive verification protocols)

**Blocking**: None - Can start immediately after approval (TIER 0 not required)

**Blocked by this**: None - Can run in parallel with other proposals

---

## Testing Strategy

### **Vue Compilation Testing**

1. **Fixture validation**: Test on 10 Vue projects
   - Vue 2 vs Vue 3 syntax
   - `<script setup>` with TypeScript
   - Empty `<script>` blocks
   - Complex `<template>` with directives
2. **Output comparison**: Verify extraction output matches original (byte-for-byte)
3. **Performance measurement**: Measure speedup on 100 .vue files

### **Module Resolution Testing**

1. **Resolution rate measurement**:
   - Before: Count % of imports resolved
   - After: Count % of imports resolved
   - Target: 40-60% improvement
2. **Edge cases**:
   - Relative imports (./foo, ../bar)
   - Path mappings (@/components, ~/utils)
   - node_modules (lodash, @types/react)
   - Scoped packages (@vue/reactivity)
   - index.js/ts resolution
3. **Integration testing**: Run taint analysis, verify cross-file flows detected

---

## Success Criteria

**MUST MEET ALL** before merging:

1. ✅ Vue compilation: 9s → ≤3s per 100 files (3x+ speedup)
2. ✅ Module resolution: 40-60% → ≥80% resolved
3. ✅ All Vue extraction tests pass (zero regressions)
4. ✅ Fixtures byte-for-byte identical (Vue extraction output)
5. ✅ Cross-file taint analysis works (test on known multi-file vulnerabilities)

---

## Approval Gates

**Stage 1**: Proposal Review (Current Stage)
- [ ] Architect reviews proposal
- [ ] Architect approves scope and timeline

**Stage 2**: Verification Phase (Before Implementation)
- [ ] Coder reads INVESTIGATION_REPORT.md sections 4.1-4.2
- [ ] Coder reads design.md sections 3.1-3.2
- [ ] Coder completes verification protocol (see `verification.md`)
- [ ] Architect approves verification results

**Stage 3**: Implementation
- [ ] Vue in-memory compilation implemented (tasks 3.1-3.5)
- [ ] Module resolution implemented (tasks 4.1-4.7)
- [ ] All tests passing
- [ ] Coordinate merge with AI #4 on javascript.py

**Stage 4**: Deployment
- [ ] Performance benchmarks validated
- [ ] Architect approves deployment
- [ ] Merged to main

---

## Related Changes

**Parent**: `performance-revolution-now` (PAUSED AND SPLIT)

**Siblings** (can run in parallel):
- `taint-analysis-spatial-indexes` (AI #1, TIER 0) - Zero file conflicts
- `fix-python-ast-orchestrator` (AI #2, TIER 0) - Zero file conflicts
- `fce-json-normalization` (AI #4, TIER 1.5) - 1 file conflict (coordinate merge)
- `database-indexes-cleanup` (TIER 2) - Zero file conflicts

**Merge Strategy**: Coordinate with AI #4 on `javascript.py` (lines 748-768 vs line 1288)

---

**Next Step**: Architect reviews and approves/rejects/modifies this proposal
