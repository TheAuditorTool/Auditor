# Vue + Module Resolution Implementation Tasks

**CRITICAL**: Do NOT start implementation until:
1. ✅ Architect approves `proposal.md`
2. ✅ Verification phase completed (see `verification.md`)
3. ✅ Architect approves verification findings

---

## 0. Verification Phase (MANDATORY)

- [ ] 0.1 Read Investigation Report sections 4.1-4.2
- [ ] 0.2 Read Design Document
- [ ] 0.3 Execute Verification Protocol
- [ ] 0.4 Document Findings in verification.md
- [ ] 0.5 Get Architect Approval

---

## Task 3: Vue In-Memory Compilation

**Estimated Time**: 4-6 hours

### 3.1 Read Current Vue SFC Compilation Flow
- [ ] 3.1.1 Read `theauditor/extractors/js/batch_templates.js:119-175`
- [ ] 3.1.2 Verify disk I/O pattern (writeFileSync → compile → unlinkSync)
- [ ] 3.1.3 Measure baseline performance on 100 .vue files

### 3.2 Research TypeScript API for In-Memory Compilation
- [ ] 3.2.1 Verify `ts.createSourceFile(filename, content, ...)` accepts string content
- [ ] 3.2.2 Confirm no file path dependency (can use virtual paths)
- [ ] 3.2.3 Test with simple example

### 3.3 Refactor `prepareVueSfcFile()` for In-Memory
- [ ] 3.3.1 Remove `fs.writeFileSync()` call
- [ ] 3.3.2 Pass compiled content directly to TypeScript API
- [ ] 3.3.3 Use virtual path (e.g., `/virtual/${scopeId}.js`)
- [ ] 3.3.4 Remove `fs.unlinkSync()` cleanup

### 3.4 Test on Vue Fixture Projects
- [ ] 3.4.1 Test Vue 2 SFC syntax
- [ ] 3.4.2 Test Vue 3 `<script setup>` with TypeScript
- [ ] 3.4.3 Test empty `<script>` blocks
- [ ] 3.4.4 Verify extraction output matches original (byte-for-byte)

### 3.5 Measure Speedup
- [ ] 3.5.1 Benchmark on 100 .vue files
- [ ] 3.5.2 Document: Before ___s, After ___s, Speedup ___x
- [ ] 3.5.3 Target: 9s → 3s (3x speedup)

---

## Task 4: Node Module Resolution

**Estimated Time**: 1-2 weeks

### 4.1 Research TypeScript Module Resolution
- [ ] 4.1.1 Read TypeScript source: `moduleNameResolver.ts`
- [ ] 4.1.2 Understand Node.js resolution (node_modules, package.json exports)
- [ ] 4.1.3 Document algorithm steps

### 4.2 Read Current Implementation
- [ ] 4.2.1 Read `theauditor/indexer/extractors/javascript.py:748-768`
- [ ] 4.2.2 Verify simplistic basename extraction
- [ ] 4.2.3 Identify gaps (relative imports, path mappings, node_modules)

### 4.3 Implement Relative Import Resolution
- [ ] 4.3.1 Handle `./utils/validation` → `src/utils/validation.ts`
- [ ] 4.3.2 Handle `../config` → `src/config.ts`
- [ ] 4.3.3 Respect file extensions (.js, .ts, .tsx, .jsx)
- [ ] 4.3.4 Handle index.js/ts resolution

### 4.4 Implement tsconfig.json Path Mapping
- [ ] 4.4.1 Parse tsconfig.json "paths" field
- [ ] 4.4.2 Map `@/utils` → `src/utils`
- [ ] 4.4.3 Map `~components` → `src/components`
- [ ] 4.4.4 Test on projects with custom path mappings

### 4.5 Implement node_modules Resolution
- [ ] 4.5.1 Resolve `lodash` → `node_modules/lodash/index.js`
- [ ] 4.5.2 Respect package.json "exports" field
- [ ] 4.5.3 Handle scoped packages `@types/react`
- [ ] 4.5.4 Walk up directory tree for node_modules

### 4.6 Add Caching
- [ ] 4.6.1 Cache: `(import_path, from_file) → resolved_path`
- [ ] 4.6.2 Avoid re-resolving same import multiple times

### 4.7 Testing
- [ ] 4.7.1 Test on 10 TypeScript projects with various import styles
- [ ] 4.7.2 Measure import resolution rate before/after
- [ ] 4.7.3 Target: 40-60% → 80-90% resolved

---

## Task 5: Integration & Coordination

### 5.1 Coordinate with AI #4 on javascript.py
- [ ] 5.1.1 Communicate line number shifts after AI #3's changes
- [ ] 5.1.2 AI #4's line 1288 becomes line ___ after module resolution changes
- [ ] 5.1.3 Merge strategy: Apply both changes sequentially

### 5.2 Final Testing
- [ ] 5.2.1 Run all JavaScript/TypeScript extraction tests
- [ ] 5.2.2 Run cross-file taint analysis tests
- [ ] 5.2.3 Verify no regressions

---

## Completion Checklist

- [ ] All tasks 3.1-3.5 completed (Vue in-memory)
- [ ] All tasks 4.1-4.7 completed (module resolution)
- [ ] Vue: 9s → ≤3s per 100 files
- [ ] Module resolution: ≥80% resolved
- [ ] All tests passing
- [ ] Coordinated merge with AI #4
- [ ] Architect approval

---

**Status**: 🔴 VERIFICATION PHASE

**Estimated Time**: 3-4 days
