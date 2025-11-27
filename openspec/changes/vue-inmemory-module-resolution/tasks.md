# Vue + Module Resolution Implementation Tasks

**Status**: VERIFICATION PHASE

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
  - **Location**: `theauditor/indexer/extractors/javascript.py:855-858`
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

- [ ] 3.1.2 Read `prepareVueSfcFile()` function (CommonJS: lines 700-760)
  - **What to understand**: CommonJS variant of same function
  - **Note**: Both variants must be modified identically

- [ ] 3.1.3 Read Vue file processing loop (ES Module: lines 255-265)
  - **What to understand**: How `vueMeta` is used to set `fileEntry.absolute`
  - **Key variables**: `fileEntry.absolute`, `fileEntry.cleanup`

- [ ] 3.1.4 Read Vue file processing loop (CommonJS: lines 850-870)
  - **What to understand**: CommonJS variant of same loop

- [ ] 3.1.5 Read cleanup code (ES Module: lines 590-600, CommonJS: lines 1120-1130)
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

- [ ] 3.4.1 Apply same changes as 3.3.1-3.3.4 to CommonJS variant (lines 646-700)

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

- [ ] 3.5.4 Remove cleanup block (lines 541-544)
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

## Task 4: Node Module Resolution

**Estimated Time**: 8-16 hours
**Files Modified**: `theauditor/indexer/extractors/javascript.py`

### 4.1 Read and Understand Current Implementation

- [ ] 4.1.1 Read current import resolution (lines 840-860)
  - **What to understand**: How imports are extracted and stored
  - **Key variables**: `import_entry`, `imp_path`, `resolved_imports`

- [ ] 4.1.2 Read TypeScript module resolution docs
  - **URL**: https://www.typescriptlang.org/docs/handbook/module-resolution.html
  - **What to understand**: Node resolution algorithm, path mappings

- [ ] 4.1.3 Read Node.js module resolution docs
  - **URL**: https://nodejs.org/api/modules.html#all-together
  - **What to understand**: node_modules lookup, package.json exports

### 4.2 Implement ModuleResolver Class

- [ ] 4.2.1 Create `ModuleResolver` class in `javascript.py`
  - **Location**: Add before `JavaScriptExtractor` class
  - **Reference**: See `design.md` section 3.3

- [ ] 4.2.2 Implement `__init__()` method
  - **Parameters**: `project_root: str`
  - **Initialize**: `tsconfig_cache`, `resolution_cache`

- [ ] 4.2.3 Implement `resolve()` method (public entry point)
  - **Parameters**: `import_path: str`, `from_file: str`
  - **Returns**: `str | None` (resolved path or None)
  - **Logic**: Check cache, delegate to `_resolve_uncached()`

### 4.3 Implement Relative Import Resolution

- [ ] 4.3.1 Implement `_resolve_relative()` method
  - **Input**: `./utils/validation`, `src/components/Button.tsx`
  - **Output**: `src/utils/validation.ts`

- [ ] 4.3.2 Handle extension resolution
  - **Extensions to try**: `.ts`, `.tsx`, `.js`, `.jsx`, `.d.ts`
  - **Order matters**: TypeScript prefers `.ts` over `.js`

- [ ] 4.3.3 Handle index file resolution
  - **Index files**: `index.ts`, `index.tsx`, `index.js`, `index.jsx`
  - **Example**: `./utils` -> `./utils/index.ts`

### 4.4 Implement Path Mapping Resolution

- [ ] 4.4.1 Implement `_get_tsconfig()` method
  - **Logic**: Walk up directory tree from file, find nearest `tsconfig.json`
  - **Cache**: Store parsed config in `tsconfig_cache`

- [ ] 4.4.2 Implement `_find_tsconfig_path()` method
  - **Logic**: Walk up until project root, check for `tsconfig.json`

- [ ] 4.4.3 Implement `_resolve_path_mapping()` method
  - **Input**: `@/components/Button`, parsed tsconfig
  - **Output**: `src/components/Button.tsx`

- [ ] 4.4.4 Handle wildcard patterns
  - **Pattern**: `@/*` maps to `src/*`
  - **Example**: `@/utils/foo` -> `src/utils/foo.ts`

- [ ] 4.4.5 Handle exact patterns
  - **Pattern**: `@types` maps to `src/types/index.ts`
  - **Example**: `@types` -> `src/types/index.ts`

### 4.5 Implement node_modules Resolution

- [ ] 4.5.1 Implement `_resolve_node_modules()` method
  - **Logic**: Walk up directory tree, check each `node_modules/`

- [ ] 4.5.2 Handle scoped packages
  - **Pattern**: `@vue/reactivity` -> `node_modules/@vue/reactivity/`
  - **Split**: First two segments for scoped packages

- [ ] 4.5.3 Implement `_resolve_package()` method
  - **Logic**: Check `package.json` for entry point

- [ ] 4.5.4 Handle `exports` field in package.json
  - **Priority**: `exports` > `module` > `main`
  - **Handle**: String and object formats

- [ ] 4.5.5 Handle package subpaths
  - **Example**: `lodash/fp` -> `node_modules/lodash/fp/index.js`

### 4.6 Implement Helper Methods

- [ ] 4.6.1 Implement `_try_extensions()` method
  - **Logic**: Try path with various extensions, return first match

### 4.7 Integrate with Existing Code

- [ ] 4.7.1 Replace basename logic (lines 855-858)
  - **Before**:
    ```python
    module_name = imp_path.split('/')[-1].replace('.js', '').replace('.ts', '')
    if module_name:
        result['resolved_imports'][module_name] = imp_path
    ```
  - **After**:
    ```python
    resolver = ModuleResolver(project_root)
    resolved = resolver.resolve(imp_path, file_info.get('path', ''))
    if resolved:
        result['resolved_imports'][imp_path] = resolved
    else:
        # Fallback to basename for unresolvable imports
        module_name = imp_path.split('/')[-1].replace('.js', '').replace('.ts', '')
        result['resolved_imports'][module_name] = imp_path
    ```

- [ ] 4.7.2 Pass `project_root` to extractor
  - **Check**: `file_info` dict contains project root
  - **Alternative**: Use `self.project_root` if stored in extractor

### 4.8 Testing Module Resolution

- [ ] 4.8.1 Create resolution test fixtures
  - **Location**: `tests/fixtures/js/module-resolution/`
  - **Files needed**:
    - `tsconfig.json` with path mappings
    - `src/utils/validation.ts`
    - `src/components/Button.tsx`
    - `package.json` in fake node_modules

- [ ] 4.8.2 Create unit tests for ModuleResolver
  - **Test cases**:
    - Relative: `./utils/validation` from `src/components/Button.tsx`
    - Parent: `../config` from `src/utils/foo.ts`
    - Path mapping: `@/utils` with tsconfig paths
    - node_modules: `lodash`
    - Scoped: `@vue/reactivity`
    - Index: `./utils` -> `./utils/index.ts`

- [ ] 4.8.3 Create integration test
  - **Purpose**: Verify resolution rate improves
  - **Method**: Count resolved vs total imports before/after

- [ ] 4.8.4 Create taint analysis test
  - **Purpose**: Verify cross-file taint flows work
  - **Method**: Create multi-file vulnerability, verify detection

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
| 2025-11-24 | 2.0 | Complete rewrite with verified paths and atomic tasks |
| Original | 1.0 | Initial tasks (OBSOLETE - wrong paths) |
