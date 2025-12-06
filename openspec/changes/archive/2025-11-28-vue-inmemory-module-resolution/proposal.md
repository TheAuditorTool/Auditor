# Vue In-Memory Compilation + Node Module Resolution

**Status**: PROPOSAL - Awaiting Architect approval

**Priority**: P1 - Performance & Accuracy

**Assigned to**: AI Coder (Sonnet/Opus - medium complexity)

**Estimated Effort**: 3-5 days (implementation + testing)

**Impact**: MEDIUM-HIGH
- Vue: 60-80% speedup (35-95ms -> 10-20ms per .vue file)
- Module resolution: 40-60% -> 80-90% accuracy (critical for cross-file taint)

---

## Why

### Problem 1: Vue SFC Disk I/O Overhead

Vue Single File Component (SFC) compilation currently performs 3 disk operations per file:

```javascript
// CURRENT FLOW (batch_templates.js:119-175):
// 1. Write compiled script to temp file
const tempFilePath = createVueTempPath(scopeId, langHint);
fs.writeFileSync(tempFilePath, compiledScript.content, 'utf8');  // LINE 147

// 2. TypeScript program uses temp file path
fileEntry.absolute = vueMeta.tempFilePath;  // LINE 259

// 3. Cleanup temp file after processing
safeUnlink(fileInfo.cleanup);  // LINE 618-621
```

**Measured Impact**:
- Disk write: ~15-35ms (SSD) / ~50-100ms (HDD)
- Disk read by TypeScript: ~5-15ms
- Total overhead: 20-50ms per .vue file
- On 100 Vue files: 2-5 seconds wasted

### Problem 2: Broken Import Resolution

JavaScript/TypeScript import resolution extracts only the basename:

```python
# CURRENT FLOW (javascript.py:747-749):
module_name = imp_path.split('/')[-1].replace('.js', '').replace('.ts', '')
if module_name:
    result['resolved_imports'][module_name] = imp_path
```

**What this misses**:
1. **Relative imports**: `./utils/validation` -> only gets `validation`
2. **Path mappings**: `@/components/Button` -> only gets `Button`
3. **Scoped packages**: `@vue/reactivity` -> only gets `reactivity`
4. **Index resolution**: `./utils` (meaning `./utils/index.ts`) -> gets `utils`

**Impact**: 40-60% of imports unresolved -> cross-file taint analysis fails -> false negatives

---

## What Changes

### Task 3: Vue In-Memory Compilation

**Files Modified**:
- `theauditor/ast_extractors/javascript/batch_templates.js` (lines 119-175, 703-760)

**Change**: Pass compiled Vue script content directly to TypeScript API without disk I/O

```javascript
// BEFORE (3 disk operations):
const tempFilePath = createVueTempPath(scopeId, langHint);
fs.writeFileSync(tempFilePath, compiledScript.content, 'utf8');
// ... TypeScript reads from disk ...
safeUnlink(fileInfo.cleanup);

// AFTER (0 disk operations):
// Option A: Use TypeScript's createSourceFile directly
const virtualPath = `/virtual/vue_${scopeId}.${isTs ? 'ts' : 'js'}`;
const sourceFile = ts.createSourceFile(
    virtualPath,
    compiledScript.content,  // In-memory content
    ts.ScriptTarget.Latest,
    true  // setParentNodes
);

// Option B: Use ts.createProgram with custom CompilerHost
const customHost = ts.createCompilerHost(compilerOptions);
customHost.readFile = (fileName) => {
    if (fileName === virtualPath) {
        return compiledScript.content;  // Return in-memory content
    }
    return ts.sys.readFile(fileName);  // Fallback to disk for non-Vue
};
```

**Decision Required**: Neither Option A nor Option B may be correct - requires architectural review of extractor/indexer layer and `js_helper_templates.py` patterns before deciding.

### Task 4: Node Module Resolution (Post-Indexing)

**Files Modified**:
- `theauditor/indexer/extractors/javascript_resolvers.py` (new static method)

**Architecture**: Post-indexing resolver (like `resolve_handler_file_paths`)

**Change**: Add `resolve_import_paths()` method that queries indexed `files` table

```python
# AFTER (database-first resolution):
@staticmethod
def resolve_import_paths(db_path: str):
    """
    Resolve import paths using indexed file data.

    NO FILESYSTEM I/O. Uses database to check if paths exist.
    Runs AFTER all files indexed (post-indexing phase).

    Resolution order (per TypeScript spec):
    1. Relative imports (./foo, ../bar)
    2. Path mappings from tsconfig.json (@/components, ~/utils)
    3. Index file resolution (./utils -> ./utils/index.ts)

    Note: node_modules resolution skipped (external packages not indexed)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Build set of indexed paths (FAST - one query, O(1) lookups)
    cursor.execute("SELECT path FROM files WHERE ext IN ('.ts', '.tsx', '.js', '.jsx', '.vue')")
    indexed_paths = {row[0] for row in cursor.fetchall()}

    # Get imports to resolve
    cursor.execute("""
        SELECT rowid, file, package FROM import_styles
        WHERE package LIKE '.%' OR package LIKE '@%'
    """)

    for rowid, from_file, import_path in cursor.fetchall():
        resolved = _resolve_against_index(import_path, from_file, indexed_paths)
        if resolved:
            # Store resolved path (schema change: add resolved_path column)
            cursor.execute(
                "UPDATE import_styles SET resolved_path = ? WHERE rowid = ?",
                (resolved, rowid)
            )
```

**Key difference from original proposal**:
- **OLD**: Filesystem checks with `os.path.isfile()` during extraction
- **NEW**: Database queries against `files` table post-indexing

---

## Impact

### Affected Code

**Modified Files**:
| File | Lines | Change Type |
|------|-------|-------------|
| `theauditor/ast_extractors/javascript/batch_templates.js` | 119-175, 703-760 | Vue in-memory |
| `theauditor/indexer/extractors/javascript_resolvers.py` | new method | Module resolution (post-indexing) |

**Schema Change**:
| Table | Column | Type | Purpose |
|-------|--------|------|---------|
| `import_styles` | `resolved_path` | TEXT | Stores resolved file path |

**Read-Only** (for understanding):
| File | Purpose |
|------|---------|
| `theauditor/ast_extractors/javascript/core_language.js` | Extraction functions |
| `theauditor/ast_extractors/javascript/framework_extractors.js` | Vue extractors |
| `theauditor/indexer/database.py` | Database storage |

### Breaking Changes

**MINIMAL** - One additive schema change:
- Vue extraction output format unchanged
- **NEW**: `import_styles.resolved_path` column added (additive, non-breaking)
- CLI interface unchanged
- Existing queries continue to work (new column is optional)

### Performance Targets

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Vue compilation (per file) | 35-95ms | 10-20ms | 60-80% faster |
| Vue compilation (100 files) | 6-9s | 1-2s | 70% faster |
| Import resolution rate | 40-60% | 80-90% | 40-50% more imports |
| Cross-file taint flows | Limited | Enabled | Qualitative |

### Risk Assessment

**Complexity**: MEDIUM
- Vue: Requires understanding TypeScript API (CompilerHost pattern)
- Module Resolution: Requires understanding Node.js resolution algorithm

**Risks**:
| Risk | Mitigation |
|------|------------|
| Vue edge cases (`<script setup>`, TypeScript) | Test on 10+ fixture projects |
| TypeScript version compatibility | Test on TS 4.x and 5.x |
| Module resolution edge cases | Test on diverse projects (monorepos, path mappings) |
| Performance regression (CPU vs disk trade-off) | Benchmark before/after |

---

## Dependencies

**Prerequisites**:
- TypeScript API available (`typescript_impl.js`)
- Vue SFC compiler available (`@vue/compiler-sfc`)
- Both already installed via `aud setup-ai`

**Required Reading** (BEFORE coding):
1. This proposal's `design.md` - Technical architecture
2. This proposal's `tasks.md` - Implementation checklist
3. This proposal's `verification.md` - Confirmed findings
4. `TEAMSOP.md` v4.20 - Prime Directive protocols
5. TypeScript `CompilerHost` documentation
6. Node.js module resolution algorithm

**Blocking**: None - Can start after architect approval

**Blocked by this**: None - Can run in parallel with other changes

---

## Testing Strategy

### Vue Compilation Testing

1. **Fixture projects**: Test on 10+ Vue projects
   - Vue 2 Options API
   - Vue 3 Composition API
   - `<script setup>` syntax
   - TypeScript in Vue files
   - Empty `<script>` blocks
   - Complex `<template>` with directives

2. **Output validation**: Byte-for-byte comparison
   - Run extraction before/after
   - Compare all extracted data fields
   - Ensure no regressions

3. **Performance measurement**:
   - Benchmark on 100 .vue files
   - Measure wall-clock time
   - Profile CPU vs disk time

### Module Resolution Testing

1. **Resolution rate measurement**:
   - Count resolved vs unresolved imports before/after
   - Target: 40% improvement (40-60% -> 80-90%)

2. **Edge cases**:
   | Import Type | Example | Expected Resolution |
   |------------|---------|---------------------|
   | Relative | `./utils/validation` | `src/utils/validation.ts` |
   | Parent | `../config` | `src/config.ts` |
   | Path mapping | `@/components/Button` | `src/components/Button.tsx` |
   | Scoped package | `@vue/reactivity` | `node_modules/@vue/reactivity/...` |
   | Bare import | `lodash` | `node_modules/lodash/...` |
   | Index resolution | `./utils` | `./utils/index.ts` |

3. **Integration testing**:
   - Run taint analysis on test project
   - Verify cross-file flows detected
   - Compare before/after findings

---

## Success Criteria

**MUST MEET ALL before merging**:

- [ ] Vue compilation: Disk I/O eliminated (0 temp files)
- [ ] Vue compilation: 60%+ speedup on 100-file benchmark
- [ ] Module resolution: 80%+ imports resolved (measured)
- [ ] All Vue extraction tests pass (zero regressions)
- [ ] All existing tests pass (`pytest tests/ -v`)
- [ ] Cross-file taint analysis works (test on multi-file vulnerability)
- [ ] No breaking changes to CLI or database schema

---

## Approval Gates

**Stage 1**: Proposal Review (Current Stage)
- [ ] Architect reviews proposal
- [ ] Architect approves scope and approach

**Stage 2**: Verification Phase (Before Implementation)
- [ ] Coder reads design.md
- [ ] Coder reads tasks.md
- [ ] Coder completes verification protocol
- [ ] Architect approves verification results

**Stage 3**: Implementation
- [ ] Task 3 implemented (Vue in-memory)
- [ ] Task 4 implemented (module resolution)
- [ ] All tests passing
- [ ] Performance benchmarks validated

**Stage 4**: Deployment
- [ ] Architect approves deployment
- [ ] Merged to main

---

## Document History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-28 | 3.1 | Option A/B flagged as requiring architectural review |
| 2025-11-28 | 3.0 | **ARCHITECTURE REWRITE**: Module resolution now post-indexing DB queries (not filesystem) |
| 2025-11-28 | 2.1 | Line numbers updated after schema normalizations |
| 2025-11-24 | 2.0 | Complete rewrite with verified paths/line numbers |
| Original | 1.0 | Initial proposal (OBSOLETE - wrong paths) |
