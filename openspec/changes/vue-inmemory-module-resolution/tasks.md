# Vue + Module Resolution Implementation Tasks

**Status**: VERIFICATION PHASE

**Note on Task Numbering**: Tasks are numbered 3, 4, 5 (not 1, 2, 3) because this proposal was originally part of a parent proposal that was never created. Numbering preserved for historical consistency with verification.md references.

**CRITICAL**: Do NOT start implementation until:
1. [x] Architect approves `proposal.md`
2. [x] Verification phase completed (see `verification.md`)
3. [ ] Architect approves verification findings

---

## 0. Verification Phase (COMPLETED 2025-11-24)

- [x] 0.1 Verify Vue disk I/O pattern exists
  - **Location**: `theauditor/ast_extractors/javascript/batch_templates.js:147`
  - **Evidence**: `fs.writeFileSync(tempFilePath, compiledScript.content, 'utf8');`
  - **Confirmed**: YES - Disk I/O exists exactly as described

- [x] 0.2 Verify import resolution uses basename only
  - **Location**: `theauditor/indexer/extractors/javascript.py:747-749`
  - **Evidence**: `module_name = imp_path.split('/')[-1].replace('.js', '').replace('.ts', '')`
  - **Confirmed**: YES - Basename extraction only

- [x] 0.3 Verify correct file paths (ORIGINAL PROPOSAL WAS WRONG)
  - **WRONG in original**: `theauditor/extractors/js/batch_templates.js`
  - **CORRECT path**: `theauditor/ast_extractors/javascript/batch_templates.js`
  - **FIXED in v2.0 proposal**: YES

- [x] 0.4 Document Findings in verification.md
  - **Status**: Complete

- [ ] 0.5 Get Architect Approval for Verification Results
  - **Status**: PENDING

---

## Task 3: Vue In-Memory Compilation

**Estimated Time**: 4-8 hours
**Files Modified**: `theauditor/ast_extractors/javascript/batch_templates.js`

### 3.1 Read and Understand Current Implementation

- [ ] 3.1.1 Read `prepareVueSfcFile()` function (ES Module: lines 119-175)
  - **What to understand**: How Vue SFC is parsed, compiled, and temp file created
  - **Key variables**: `tempFilePath`, `compiledScript.content`, `scopeId`

- [ ] 3.1.2 Read `prepareVueSfcFile()` function (CommonJS: lines 703-760)
  - **What to understand**: CommonJS variant of same function
  - **Note**: Both variants must be modified identically

- [ ] 3.1.3 Read Vue file processing loop (ES Module: lines 255-265)
  - **What to understand**: How `vueMeta` is used to set `fileEntry.absolute`
  - **Key variables**: `fileEntry.absolute`, `fileEntry.cleanup`

- [ ] 3.1.4 Read Vue file processing loop (CommonJS: lines 870-890)
  - **What to understand**: CommonJS variant of same loop

- [ ] 3.1.5 Read cleanup code (ES Module: lines 618-621, CommonJS: lines 1220-1223)
  - **What to understand**: How temp files are cleaned up
  - **Key function**: `safeUnlink(fileInfo.cleanup)`

- [ ] 3.1.6 Read `createVueAwareCompilerHost()` pattern in TypeScript docs
  - **URL**: https://github.com/Microsoft/TypeScript/wiki/Using-the-Compiler-API
  - **What to understand**: How to create custom CompilerHost

### 3.2 Implement Custom CompilerHost

- [ ] 3.2.1 Create `createVueAwareCompilerHost()` function
  - **Location**: Add before `main()` function in batch_templates.js
  - **Parameters**: `compilerOptions`, `vueContentMap` (Map<string, string>)
  - **Returns**: Custom CompilerHost that serves Vue files from memory

- [ ] 3.2.2 Implement `fileExists()` override
  - **Logic**: Return true if fileName is in vueContentMap, else use defaultHost

- [ ] 3.2.3 Implement `readFile()` override
  - **Logic**: Return content from vueContentMap if exists, else use defaultHost

- [ ] 3.2.4 Implement `getSourceFile()` override
  - **Logic**: Create SourceFile from vueContentMap content if exists, else use defaultHost

### 3.3 Modify `prepareVueSfcFile()` - ES Module Variant

- [ ] 3.3.1 Remove `fs.writeFileSync()` call (line 147)
  - **Before**: `fs.writeFileSync(tempFilePath, compiledScript.content, 'utf8');`
  - **After**: (delete line)

- [ ] 3.3.2 Create virtual path instead of temp file path
  - **Add**: `const virtualPath = \`/virtual/vue_${scopeId}.${isTs ? 'ts' : 'js'}\`;`
  - **Where**: After `const langHint = ...` line

- [ ] 3.3.3 Update return object
  - **Before**: `{ tempFilePath, descriptor, compiledScript, ... }`
  - **After**: `{ virtualPath, scriptContent: compiledScript.content, descriptor, compiledScript, ... }`

- [ ] 3.3.4 Remove `createVueTempPath()` call
  - **Line to remove**: `const tempFilePath = createVueTempPath(scopeId, langHint || 'js');`

### 3.4 Modify `prepareVueSfcFile()` - CommonJS Variant

- [ ] 3.4.1 Apply same changes as 3.3.1-3.3.4 to CommonJS variant (lines 703-760)

### 3.5 Modify File Processing Loop - ES Module

- [ ] 3.5.1 Update Vue file handling (lines 255-265)
  - **Before**:
    ```javascript
    fileEntry.absolute = vueMeta.tempFilePath;
    fileEntry.cleanup = vueMeta.tempFilePath;
    ```
  - **After**:
    ```javascript
    fileEntry.vueMeta = vueMeta;  // Store for later use
    fileEntry.isVirtual = true;   // Flag as virtual file
    ```

- [ ] 3.5.2 Build vueContentMap before creating program
  - **Where**: Before `ts.createProgram()` call (line 327)
  - **Code**:
    ```javascript
    const vueContentMap = new Map();
    for (const fileInfo of groupedFiles) {
        if (fileInfo.vueMeta) {
            vueContentMap.set(fileInfo.vueMeta.virtualPath, fileInfo.vueMeta.scriptContent);
        }
    }
    ```

- [ ] 3.5.3 Use custom CompilerHost when creating program
  - **Before**: `program = ts.createProgram(groupedFiles.map(f => f.absolute), compilerOptions);`
  - **After**:
    ```javascript
    const customHost = vueContentMap.size > 0
        ? createVueAwareCompilerHost(compilerOptions, vueContentMap)
        : undefined;
    program = ts.createProgram(
        groupedFiles.map(f => f.vueMeta?.virtualPath || f.absolute),
        compilerOptions,
        customHost
    );
    ```

- [ ] 3.5.4 Remove cleanup block (lines 618-621)
  - **Before**:
    ```javascript
    finally {
        if (fileInfo.cleanup) {
            safeUnlink(fileInfo.cleanup);
        }
    }
    ```
  - **After**: Keep finally block but remove cleanup for virtual files
    ```javascript
    finally {
        if (fileInfo.cleanup && !fileInfo.isVirtual) {
            safeUnlink(fileInfo.cleanup);
        }
    }
    ```

### 3.6 Modify File Processing Loop - CommonJS Variant

- [ ] 3.6.1 Apply same changes as 3.5.1-3.5.4 to CommonJS variant

### 3.7 Testing Vue In-Memory

- [ ] 3.7.1 Create Vue test fixtures
  - **Location**: `tests/fixtures/vue/`
  - **Files needed**:
    - `options-api.vue` - Vue 2 style Options API
    - `composition-api.vue` - Vue 3 Composition API
    - `script-setup.vue` - `<script setup>` syntax
    - `typescript.vue` - TypeScript in Vue file
    - `empty-script.vue` - No script content

- [ ] 3.7.2 Create extraction comparison test
  - **Purpose**: Verify extraction output is identical before/after
  - **Method**: Run extraction on fixtures, compare JSON output

- [ ] 3.7.3 Create performance benchmark test
  - **Purpose**: Measure speedup
  - **Method**: Time extraction of 100 .vue files, compare before/after

- [ ] 3.7.4 Verify no temp files created
  - **Method**: Monitor `os.tmpdir()` during extraction, confirm no `theauditor_vue_*` files

---

## Task 4: Node Module Resolution (Post-Indexing, Database-First)

**Estimated Time**: 4-8 hours (reduced - simpler architecture)
**Files Modified**: `theauditor/indexer/extractors/javascript_resolvers.py`

**Architecture**: Post-indexing resolver using database queries (NO filesystem I/O)

### 4.1 Read and Understand Current Architecture

- [ ] 4.1.1 Read existing resolvers in `javascript_resolvers.py`
  - **What to understand**: Pattern used by `resolve_handler_file_paths`, `resolve_cross_file_parameters`
  - **Key pattern**: Load data from DB, process, update DB

- [ ] 4.1.2 Read `import_styles` table schema
  - **Command**: `aud blueprint --structure` or check database.py
  - **What to understand**: Current columns, what needs to be added

- [ ] 4.1.3 Read `files` table structure
  - **What to understand**: How indexed file paths are stored
  - **Key column**: `path` - the resolved file path

### 4.2 Schema Change

- [ ] 4.2.1 Add `resolved_path` column to `import_styles` table definition
  - **Location**: `theauditor/indexer/database.py` (schema definition)
  - **Type**: TEXT, nullable (NULL = unresolved)
  - **Note**: No migration - DB regenerated on each `aud full`

### 4.3 Implement resolve_import_paths() Method

- [ ] 4.3.1 Add `resolve_import_paths()` static method to `JavaScriptResolversMixin`
  - **Location**: `javascript_resolvers.py` after `resolve_cross_file_parameters`
  - **Signature**: `@staticmethod def resolve_import_paths(db_path: str):`

- [ ] 4.3.2 Implement Step 1: Load indexed paths
  - **Query**: `SELECT path FROM files WHERE ext IN ('.ts', '.tsx', '.js', '.jsx', '.vue')`
  - **Store**: `indexed_paths = {row[0] for row in cursor.fetchall()}`

- [ ] 4.3.3 Implement Step 2: Load path aliases
  - **Logic**: Detect `src/` directory pattern, set up `@/` and `~/` aliases
  - **Future**: Parse actual tsconfig.json paths field

- [ ] 4.3.4 Implement Step 3: Query imports to resolve
  - **Query**: `SELECT rowid, file, package FROM import_styles WHERE package LIKE './%' OR ...`
  - **Filter**: Only relative (`./`, `../`) and aliased (`@/`, `~/`) imports

- [ ] 4.3.5 Implement Step 4: Resolution loop
  - **For each import**: Call `_resolve_import()`, update DB if resolved

### 4.4 Implement Helper Functions

- [ ] 4.4.1 Implement `_load_path_aliases()` function
  - **Input**: cursor
  - **Output**: `dict[str, str]` mapping aliases to base paths
  - **Logic**: Detect src/ directory, set up common aliases

- [ ] 4.4.2 Implement `_resolve_import()` function
  - **Input**: `import_path`, `from_file`, `indexed_paths`, `path_aliases`
  - **Output**: `str | None` (resolved path or None)
  - **Steps**:
    1. Expand path aliases
    2. Resolve relative paths
    3. Try extension/index variants
    4. Check against `indexed_paths` set

- [ ] 4.4.3 Implement `_normalize_path()` function
  - **Input**: path string with potential `..` segments
  - **Output**: normalized path
  - **Logic**: Handle `..` by popping parent directories

### 4.5 Integrate with Indexer Pipeline

- [ ] 4.5.1 Add `resolve_import_paths()` call to orchestrator
  - **File**: `theauditor/indexer/orchestrator.py`
  - **Location**: Line 491 (after `resolve_handler_file_paths` call at line 490)
  - **Code to add**:
    ```python
    JavaScriptExtractor.resolve_import_paths(self.db_manager.db_path)
    ```
  - **Context** (existing lines 474-490 for reference):
    ```python
    # Line 474:
    JavaScriptExtractor.resolve_cross_file_parameters(self.db_manager.db_path)
    # Line 490:
    JavaScriptExtractor.resolve_handler_file_paths(self.db_manager.db_path)
    # Line 491 (ADD HERE):
    JavaScriptExtractor.resolve_import_paths(self.db_manager.db_path)
    ```

### 4.6 Testing

- [ ] 4.6.1 Create unit test for `_resolve_import()`
  - **Test cases**:
    - `./utils` from `src/components/Button.tsx` → `src/components/utils.ts`
    - `../config` from `src/utils/foo.ts` → `src/config.ts`
    - `@/utils` with alias → `src/utils.ts`
    - Index resolution: `./utils` → `src/components/utils/index.ts`

- [ ] 4.6.2 Create integration test
  - **Method**: Index a test project, verify `resolved_path` populated
  - **Metric**: Count non-NULL `resolved_path` vs total relative imports

- [ ] 4.6.3 Verify no filesystem I/O
  - **Method**: Mock `os.path.isfile()` to raise, ensure no calls

---

## Task 5: Final Integration & Testing

**Estimated Time**: 2-4 hours

### 5.1 Run Existing Tests

- [ ] 5.1.1 Run all JavaScript extraction tests
  - **Command**: `pytest tests/test_javascript_extractor.py -v`
  - **Expected**: All pass

- [ ] 5.1.2 Run all taint analysis tests
  - **Command**: `pytest tests/test_taint_analyzer.py -v`
  - **Expected**: All pass

- [ ] 5.1.3 Run full test suite
  - **Command**: `pytest tests/ -v`
  - **Expected**: All pass (or only pre-existing failures)

### 5.2 Performance Benchmarks

- [ ] 5.2.1 Benchmark Vue compilation
  - **Before**: Record time for 100 .vue files
  - **After**: Record time for 100 .vue files
  - **Target**: 60%+ improvement

- [ ] 5.2.2 Benchmark import resolution
  - **Before**: Count resolved imports
  - **After**: Count resolved imports
  - **Target**: 80%+ resolved (up from 40-60%)

### 5.3 Documentation

- [ ] 5.3.1 Update inline code comments
  - **What**: Add comments explaining new architecture

- [ ] 5.3.2 Update this tasks.md with results
  - **What**: Fill in benchmark numbers, mark completion

---

## Completion Checklist

- [ ] All Task 3 items completed (Vue in-memory)
- [ ] All Task 4 items completed (module resolution)
- [ ] All Task 5 items completed (integration)
- [ ] Vue: No temp files created during extraction
- [ ] Vue: 60%+ speedup on 100-file benchmark
- [ ] Module resolution: 80%+ imports resolved
- [ ] All existing tests pass
- [ ] Performance benchmarks documented
- [ ] Architect approval

---

## Document History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-28 | 3.1 | **IRONCLAD**: Task 4.5.1 now action task with exact file:line, added numbering note |
| 2025-11-28 | 3.0 | **ARCHITECTURE REWRITE**: Task 4 now post-indexing DB-first (not filesystem) |
| 2025-11-28 | 2.1 | Line numbers updated after schema normalizations |
| 2025-11-24 | 2.0 | Complete rewrite with verified paths and atomic tasks |
| Original | 1.0 | Initial tasks (OBSOLETE - wrong paths) |
