# Vue + Module Resolution Technical Design

**Status**: DRAFT - Pending Implementation

**Last Updated**: 2025-11-24

---

## 1. Architecture Context

### 1.1 Current JavaScript Extraction Flow

```
                                    PHASE 5 ARCHITECTURE
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  orchestrator.py                                                            │
│  └─► javascript.py (extractor)                                              │
│      └─► subprocess: node batch_templates.js                                │
│          ├─► prepareVueSfcFile()     ◄── DISK I/O HERE                      │
│          │   ├─► fs.writeFileSync()                                         │
│          │   └─► tempFilePath returned                                      │
│          │                                                                  │
│          ├─► ts.createProgram()       ◄── Uses temp file path               │
│          │   └─► getSourceFile(tempFilePath)                                │
│          │                                                                  │
│          ├─► extractFunctions()                                             │
│          ├─► extractCalls()                                                 │
│          ├─► extractVueComponents()                                         │
│          ├─► extractCFG()                                                   │
│          │                                                                  │
│          └─► safeUnlink()             ◄── Cleanup temp file                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Files Involved

| File | Role | LOC |
|------|------|-----|
| `theauditor/indexer/extractors/javascript.py` | Python extractor, module resolution | ~820 |
| `theauditor/ast_extractors/javascript/batch_templates.js` | JS batch processing, Vue handling | ~1095 |
| `theauditor/ast_extractors/javascript/core_language.js` | Extraction functions | ~600 |
| `theauditor/ast_extractors/javascript/framework_extractors.js` | Vue/React/Angular extractors | ~800 |

### 1.3 Key Data Structures

**Vue SFC Metadata** (`vueMeta` object):
```javascript
{
    tempFilePath: string,       // Path to temp file (TO BE ELIMINATED)
    descriptor: VueSFCDescriptor,
    compiledScript: {
        content: string,        // Compiled JS/TS code (IN-MEMORY)
        bindings: object,
        ...
    },
    templateAst: object | null,
    scopeId: string,
    hasStyle: boolean
}
```

**Resolved Imports** (`resolved_imports` dict):
```python
{
    "Button": "@/components/Button",        # Path mapping
    "validation": "./utils/validation",     # Relative
    "lodash": "lodash",                      # node_modules
    # Currently: Only basename stored, original path discarded
}
```

---

## 2. Vue In-Memory Compilation Design

### 2.1 Problem Analysis

**Current Flow** (`batch_templates.js:119-175`):

```javascript
function prepareVueSfcFile(filePath) {
    // 1. Parse Vue SFC
    const source = fs.readFileSync(filePath, 'utf8');  // NECESSARY - read source
    const { descriptor, errors } = parseVueSfc(source, { filename: filePath });

    // 2. Compile script
    const compiledScript = compileVueScript(descriptor, { id: scopeId });

    // 3. PROBLEM: Write to disk for TypeScript
    const tempFilePath = createVueTempPath(scopeId, langHint);
    fs.writeFileSync(tempFilePath, compiledScript.content, 'utf8');  // UNNECESSARY

    return { tempFilePath, ... };  // TypeScript uses this path
}
```

**Why disk write exists**: TypeScript's `ts.createProgram()` expects file paths. The original implementation wrote temp files to satisfy this API.

**Why it's unnecessary**: TypeScript API provides mechanisms for in-memory source files.

### 2.2 Solution: Custom CompilerHost

TypeScript's `CompilerHost` interface allows intercepting file reads:

```javascript
// Create custom host that serves Vue files from memory
function createVueAwareCompilerHost(compilerOptions, vueContentMap) {
    const defaultHost = ts.createCompilerHost(compilerOptions);

    return {
        ...defaultHost,

        // Override file existence check
        fileExists: (fileName) => {
            if (vueContentMap.has(fileName)) {
                return true;
            }
            return defaultHost.fileExists(fileName);
        },

        // Override file read
        readFile: (fileName) => {
            if (vueContentMap.has(fileName)) {
                return vueContentMap.get(fileName);  // Return in-memory content
            }
            return defaultHost.readFile(fileName);
        },

        // Override source file retrieval
        getSourceFile: (fileName, languageVersion, onError, shouldCreateNewSourceFile) => {
            if (vueContentMap.has(fileName)) {
                const content = vueContentMap.get(fileName);
                return ts.createSourceFile(fileName, content, languageVersion, true);
            }
            return defaultHost.getSourceFile(fileName, languageVersion, onError, shouldCreateNewSourceFile);
        }
    };
}
```

### 2.3 Implementation Strategy

**Step 1**: Modify `prepareVueSfcFile()` to return content, not file path

```javascript
// BEFORE
function prepareVueSfcFile(filePath) {
    // ...
    fs.writeFileSync(tempFilePath, compiledScript.content, 'utf8');
    return { tempFilePath, descriptor, compiledScript, ... };
}

// AFTER
function prepareVueSfcFile(filePath) {
    // ...
    // NO DISK WRITE
    const virtualPath = `/virtual/vue_${scopeId}.${isTs ? 'ts' : 'js'}`;
    return {
        virtualPath,           // Virtual path (not real file)
        scriptContent: compiledScript.content,  // In-memory content
        descriptor,
        compiledScript,
        ...
    };
}
```

**Step 2**: Create program with custom host

```javascript
// Collect all Vue file contents before creating program
const vueContentMap = new Map();
for (const fileInfo of groupedFiles) {
    if (fileInfo.vueMeta) {
        vueContentMap.set(fileInfo.vueMeta.virtualPath, fileInfo.vueMeta.scriptContent);
    }
}

// Create program with custom host
const customHost = createVueAwareCompilerHost(compilerOptions, vueContentMap);
const program = ts.createProgram(
    groupedFiles.map(f => f.absolute || f.vueMeta?.virtualPath),
    compilerOptions,
    customHost
);
```

**Step 3**: Remove cleanup code

```javascript
// REMOVE THIS BLOCK
finally {
    if (fileInfo.cleanup) {
        safeUnlink(fileInfo.cleanup);
    }
}
```

### 2.4 Edge Cases

| Edge Case | Current Behavior | New Behavior | Risk |
|-----------|-----------------|--------------|------|
| `<script setup>` | Works (compileScript handles) | Same | LOW |
| TypeScript in Vue | Works (lang="ts" detected) | Same | LOW |
| Empty `<script>` | Error thrown | Same | LOW |
| Template-only Vue | Error thrown | Same | LOW |
| Multiple `<script>` | First used | Same | LOW |
| Source maps | Not generated | Not generated | LOW |

### 2.5 Testing Requirements

1. **Functional tests**:
   - Extract same Vue file before/after
   - Compare all output fields
   - Ensure bit-for-bit equality

2. **Performance tests**:
   - Benchmark 100 .vue files
   - Measure wall-clock time
   - Verify no temp files created

3. **Edge case tests**:
   - Each Vue syntax variant
   - TypeScript in Vue files
   - Error conditions

---

## 3. Module Resolution Design

### 3.1 Problem Analysis

**Current Implementation** (`javascript.py:747-749`):

```python
for import_entry in result.get('imports', []):
    # ...extract imp_path...

    # PROBLEM: Only extracts basename
    module_name = imp_path.split('/')[-1].replace('.js', '').replace('.ts', '')
    if module_name:
        result['resolved_imports'][module_name] = imp_path
```

**What's lost**:
| Import | Current Result | Should Be |
|--------|---------------|-----------|
| `./utils/validation` | `validation` | `src/utils/validation.ts` |
| `@/components/Button` | `Button` | `src/components/Button.tsx` |
| `lodash/fp` | `fp` | `node_modules/lodash/fp/index.js` |
| `../config` | `config` | `src/config.ts` |

### 3.2 TypeScript Module Resolution Algorithm

Per TypeScript documentation, resolution order is:

1. **Relative imports** (`./`, `../`):
   - Start from importing file's directory
   - Try extensions: `.ts`, `.tsx`, `.d.ts`, `.js`, `.jsx`
   - Try index files: `index.ts`, `index.tsx`, `index.js`

2. **Path mappings** (from tsconfig.json):
   - Check `compilerOptions.paths` field
   - Map aliases like `@/*` to `src/*`

3. **node_modules**:
   - Walk up directory tree
   - Check `node_modules/{package}/package.json`
   - Use `main`, `module`, or `exports` field

4. **Ambient modules**:
   - Check `@types/{package}` (for type definitions)

### 3.3 Implementation Strategy

**Location**: `javascript.py` after line 749

```python
class ModuleResolver:
    """
    TypeScript-style module resolution.

    Resolves import paths to actual file paths following Node.js/TypeScript algorithm.
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.tsconfig_cache: dict[str, dict] = {}
        self.resolution_cache: dict[tuple[str, str], str | None] = {}

    def resolve(self, import_path: str, from_file: str) -> str | None:
        """
        Resolve import path to actual file path.

        Args:
            import_path: The import specifier (e.g., './utils', '@/components/Button')
            from_file: The file containing the import

        Returns:
            Resolved file path or None if unresolvable
        """
        cache_key = (import_path, from_file)
        if cache_key in self.resolution_cache:
            return self.resolution_cache[cache_key]

        result = self._resolve_uncached(import_path, from_file)
        self.resolution_cache[cache_key] = result
        return result

    def _resolve_uncached(self, import_path: str, from_file: str) -> str | None:
        # 1. Relative imports
        if import_path.startswith('.'):
            return self._resolve_relative(import_path, from_file)

        # 2. Path mappings
        tsconfig = self._get_tsconfig(from_file)
        if tsconfig and 'paths' in tsconfig.get('compilerOptions', {}):
            resolved = self._resolve_path_mapping(import_path, tsconfig, from_file)
            if resolved:
                return resolved

        # 3. node_modules
        return self._resolve_node_modules(import_path, from_file)

    def _resolve_relative(self, import_path: str, from_file: str) -> str | None:
        """Resolve relative import (./foo, ../bar)."""
        from_dir = os.path.dirname(from_file)
        target = os.path.normpath(os.path.join(from_dir, import_path))

        # Try with extensions
        for ext in ['.ts', '.tsx', '.js', '.jsx', '.d.ts', '']:
            candidate = target + ext
            if os.path.isfile(candidate):
                return os.path.relpath(candidate, self.project_root)

        # Try index files
        for index in ['index.ts', 'index.tsx', 'index.js', 'index.jsx']:
            candidate = os.path.join(target, index)
            if os.path.isfile(candidate):
                return os.path.relpath(candidate, self.project_root)

        return None

    def _resolve_path_mapping(self, import_path: str, tsconfig: dict, from_file: str) -> str | None:
        """Resolve path mapping from tsconfig.json."""
        paths = tsconfig.get('compilerOptions', {}).get('paths', {})
        base_url = tsconfig.get('compilerOptions', {}).get('baseUrl', '.')
        tsconfig_dir = os.path.dirname(self._find_tsconfig_path(from_file) or self.project_root)
        base = os.path.join(tsconfig_dir, base_url)

        for pattern, targets in paths.items():
            if pattern.endswith('/*'):
                prefix = pattern[:-2]
                if import_path.startswith(prefix):
                    suffix = import_path[len(prefix):]
                    for target in targets:
                        if target.endswith('/*'):
                            resolved_target = target[:-2] + suffix
                            full_path = os.path.join(base, resolved_target)
                            result = self._try_extensions(full_path)
                            if result:
                                return os.path.relpath(result, self.project_root)
            elif pattern == import_path:
                for target in targets:
                    full_path = os.path.join(base, target)
                    result = self._try_extensions(full_path)
                    if result:
                        return os.path.relpath(result, self.project_root)

        return None

    def _resolve_node_modules(self, import_path: str, from_file: str) -> str | None:
        """Resolve from node_modules walking up directory tree."""
        current_dir = os.path.dirname(from_file)

        while True:
            node_modules = os.path.join(current_dir, 'node_modules')
            if os.path.isdir(node_modules):
                # Split package name (handle scoped packages)
                parts = import_path.split('/')
                if import_path.startswith('@') and len(parts) >= 2:
                    package_name = '/'.join(parts[:2])
                    subpath = '/'.join(parts[2:]) if len(parts) > 2 else ''
                else:
                    package_name = parts[0]
                    subpath = '/'.join(parts[1:]) if len(parts) > 1 else ''

                package_dir = os.path.join(node_modules, package_name)
                if os.path.isdir(package_dir):
                    resolved = self._resolve_package(package_dir, subpath)
                    if resolved:
                        return resolved

            # Walk up
            parent = os.path.dirname(current_dir)
            if parent == current_dir:
                break
            current_dir = parent

        return None

    def _resolve_package(self, package_dir: str, subpath: str) -> str | None:
        """Resolve within a package directory."""
        if subpath:
            # Direct subpath
            target = os.path.join(package_dir, subpath)
            return self._try_extensions(target)

        # Check package.json
        pkg_json = os.path.join(package_dir, 'package.json')
        if os.path.isfile(pkg_json):
            try:
                with open(pkg_json, 'r', encoding='utf-8') as f:
                    pkg = json.load(f)
                    # Try exports, module, main in order
                    entry = pkg.get('exports', {}).get('.') or pkg.get('module') or pkg.get('main', 'index.js')
                    if isinstance(entry, dict):
                        entry = entry.get('import') or entry.get('default') or entry.get('require')
                    if entry:
                        return os.path.join(package_dir, entry)
            except (json.JSONDecodeError, IOError):
                pass

        # Fallback to index.js
        return self._try_extensions(os.path.join(package_dir, 'index'))

    def _try_extensions(self, path: str) -> str | None:
        """Try path with various extensions."""
        for ext in ['', '.ts', '.tsx', '.js', '.jsx', '.d.ts']:
            candidate = path + ext
            if os.path.isfile(candidate):
                return candidate
        for index in ['index.ts', 'index.tsx', 'index.js']:
            candidate = os.path.join(path, index)
            if os.path.isfile(candidate):
                return candidate
        return None

    def _get_tsconfig(self, from_file: str) -> dict | None:
        """Find and parse nearest tsconfig.json."""
        config_path = self._find_tsconfig_path(from_file)
        if not config_path:
            return None

        if config_path not in self.tsconfig_cache:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.tsconfig_cache[config_path] = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.tsconfig_cache[config_path] = None

        return self.tsconfig_cache[config_path]

    def _find_tsconfig_path(self, from_file: str) -> str | None:
        """Find nearest tsconfig.json walking up from file."""
        current = os.path.dirname(from_file)
        while True:
            candidate = os.path.join(current, 'tsconfig.json')
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(current)
            if parent == current or not current.startswith(self.project_root):
                break
            current = parent
        return None
```

### 3.4 Integration Point

Replace current basename logic in `javascript.py`:

```python
# BEFORE (lines 747-749):
module_name = imp_path.split('/')[-1].replace('.js', '').replace('.ts', '')
if module_name:
    result['resolved_imports'][module_name] = imp_path

# AFTER:
resolver = ModuleResolver(project_root)
for import_entry in result.get('imports', []):
    # ... extract imp_path ...
    if imp_path:
        resolved = resolver.resolve(imp_path, file_info.get('path', ''))
        if resolved:
            result['resolved_imports'][imp_path] = resolved
        else:
            # Fallback to basename for unresolvable imports
            module_name = imp_path.split('/')[-1].replace('.js', '').replace('.ts', '')
            result['resolved_imports'][module_name] = imp_path
```

### 3.5 Performance Considerations

| Concern | Mitigation |
|---------|------------|
| Disk I/O for file existence checks | Cache results in `resolution_cache` |
| tsconfig.json parsing | Cache in `tsconfig_cache` |
| node_modules traversal | Walk up only until project root |
| Large projects | Resolution is per-import, not per-file |

---

## 4. Open Questions

### 4.1 Vue In-Memory

1. **Q**: Does TypeScript checker work correctly with virtual files?
   **A**: Need to test. May need to adjust type checking configuration.

2. **Q**: How to handle Vue files that import other Vue files?
   **A**: All Vue files added to `vueContentMap` before program creation.

### 4.2 Module Resolution

1. **Q**: How to handle `exports` field complexity in package.json?
   **A**: Support basic cases (string, object with import/default). Complex conditional exports TBD.

2. **Q**: Should resolution results be persisted to database?
   **A**: Currently stored in `resolved_imports` dict per file. Database schema unchanged.

---

## 5. Rollback Plan

If issues discovered after deployment:

1. **Vue In-Memory**: Revert to disk-based temp files (functional, just slower)
2. **Module Resolution**: Revert to basename extraction (functional, just less accurate)

Both are backwards-compatible. No data migration required.

---

## 6. Document History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-28 | 1.1 | Line numbers updated after schema normalizations |
| 2025-11-24 | 1.0 | Initial design document |
