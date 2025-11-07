# Vue + Module Resolution Design

**Status**: 🔴 DRAFT

---

## 1. Vue In-Memory Compilation

### 1.1 Current Pattern (Disk I/O)

```javascript
// 3 disk operations per .vue file
fs.writeFileSync(tempPath, vueContent);  // 35ms
const compiled = compileVueSFC(tempPath);
const result = fs.readFileSync(tempPath);  // 10ms
fs.unlinkSync(tempPath);
```

**Total**: 35-95ms per file (disk I/O dominates)

### 1.2 New Pattern (In-Memory)

```javascript
// Zero disk operations
const { script, template, styles } = parseVueSFC(vueContent);
const compiledScript = compileScriptSetup(script);
const result = ts.createSourceFile(
    `/virtual/${scopeId}.js`,  // Virtual path
    compiledScript,            // In-memory
    ts.ScriptTarget.Latest
);
```

**Total**: 10-20ms per file (60-80% faster)

---

## 2. Module Resolution Algorithm

### 2.1 TypeScript Resolution Order

1. **Relative imports** (`./foo`, `../bar`)
2. **Path mappings** (`@/components`, `~/utils`)
3. **node_modules** (`lodash`, `@types/react`)

### 2.2 Implementation

```python
def resolve_import(import_path, from_file):
    # 1. Relative
    if import_path.startswith('.'):
        return resolve_relative(import_path, from_file)

    # 2. Path mappings
    if '@' in import_path or '~' in import_path:
        return resolve_path_mapping(import_path, tsconfig)

    # 3. node_modules
    return resolve_node_modules(import_path, from_file)
```

---

## 3. Performance Impact

**Vue**: 6-10 seconds saved per 100 files

**Module Resolution**: 40-60% more imports resolved → enables cross-file taint
