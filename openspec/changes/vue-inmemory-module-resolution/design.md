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

**Current Flow** (`batch_templates.js:134-180`):

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

## 3. Module Resolution Design (Post-Indexing, Database-First)

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
| `../config` | `config` | `src/config.ts` |

**Note**: `node_modules` packages (lodash, etc.) are NOT indexed, so we skip resolving them.

### 3.2 Architecture Decision: Post-Indexing Resolution

**Why NOT extraction-time?**
- During extraction, database isn't fully populated
- Would require filesystem checks (`os.path.isfile()`) - SLOW and REDUNDANT
- We already have `files` table with 868+ indexed paths

**Why post-indexing?**
- All files already indexed in `files` table
- O(1) set membership lookups vs O(N) disk I/O
- Consistent with existing pattern (`resolve_handler_file_paths`, `resolve_cross_file_parameters`)

### 3.3 Implementation Strategy

**Location**: `javascript_resolvers.py` (new static method in `JavaScriptResolversMixin`)

```python
@staticmethod
def resolve_import_paths(db_path: str):
    """
    Resolve import paths using indexed file data.

    NO FILESYSTEM I/O. Uses database to check if paths exist.
    Runs AFTER all files indexed (post-indexing phase).

    Architecture:
    1. Load all indexed JS/TS paths into a set (one query)
    2. Load path mappings from config_files table (tsconfig.json)
    3. For each relative/aliased import, resolve against indexed set
    4. Store resolved paths in import_styles.resolved_path
    """
    debug = os.getenv("THEAUDITOR_DEBUG") == "1"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Step 1: Build set of indexed paths (FAST - one query, O(1) lookups)
    cursor.execute("""
        SELECT path FROM files
        WHERE ext IN ('.ts', '.tsx', '.js', '.jsx', '.vue', '.mjs', '.cjs')
    """)
    indexed_paths = {row[0] for row in cursor.fetchall()}

    if debug:
        print(f"[IMPORT RESOLUTION] Loaded {len(indexed_paths)} indexed JS/TS paths")

    # Step 2: Load path mappings from tsconfig.json (if indexed)
    path_aliases = _load_path_aliases(cursor)

    # Step 3: Get imports to resolve (relative and aliased only)
    cursor.execute("""
        SELECT rowid, file, package FROM import_styles
        WHERE package LIKE './%'
           OR package LIKE '../%'
           OR package LIKE '@/%'
           OR package LIKE '~/%'
    """)
    imports_to_resolve = cursor.fetchall()

    if debug:
        print(f"[IMPORT RESOLUTION] Found {len(imports_to_resolve)} imports to resolve")

    # Step 4: Resolve each import
    resolved_count = 0
    for rowid, from_file, import_path in imports_to_resolve:
        resolved = _resolve_import(import_path, from_file, indexed_paths, path_aliases)
        if resolved:
            cursor.execute(
                "UPDATE import_styles SET resolved_path = ? WHERE rowid = ?",
                (resolved, rowid)
            )
            resolved_count += 1

    conn.commit()
    conn.close()

    if debug:
        print(f"[IMPORT RESOLUTION] Resolved {resolved_count}/{len(imports_to_resolve)} imports")


def _load_path_aliases(cursor) -> dict[str, str]:
    """Load path aliases from indexed tsconfig.json files."""
    aliases = {}

    # Try to find tsconfig.json in config_files
    cursor.execute("""
        SELECT path FROM files WHERE path LIKE '%tsconfig.json'
    """)
    tsconfig_paths = [row[0] for row in cursor.fetchall()]

    # For each tsconfig, extract paths from config_files if available
    # (This is a simplified version - full impl would parse JSON)
    # For now, use common conventions:
    cursor.execute("""
        SELECT DISTINCT path FROM files WHERE path LIKE '%/src/%'
    """)
    if cursor.fetchone():
        # Project uses src/ directory - set up common aliases
        cursor.execute("SELECT path FROM files LIMIT 1")
        sample = cursor.fetchone()
        if sample:
            parts = sample[0].split('/')
            if 'src' in parts:
                src_idx = parts.index('src')
                base = '/'.join(parts[:src_idx + 1])
                aliases['@/'] = base + '/'
                aliases['~/'] = base + '/'

    return aliases


def _resolve_import(
    import_path: str,
    from_file: str,
    indexed_paths: set[str],
    path_aliases: dict[str, str]
) -> str | None:
    """
    Resolve a single import path against indexed files.

    Resolution order:
    1. Path alias expansion (@/, ~/)
    2. Relative path resolution (./foo, ../bar)
    3. Extension/index file variants
    """
    resolved_base = None

    # 1. Expand path aliases
    for alias, target in path_aliases.items():
        if import_path.startswith(alias):
            resolved_base = target + import_path[len(alias):]
            break

    # 2. Resolve relative paths
    if not resolved_base and import_path.startswith('.'):
        from_dir = '/'.join(from_file.split('/')[:-1])
        if import_path.startswith('./'):
            resolved_base = from_dir + '/' + import_path[2:]
        elif import_path.startswith('../'):
            parent_dir = '/'.join(from_dir.split('/')[:-1])
            resolved_base = parent_dir + '/' + import_path[3:]
        else:
            resolved_base = from_dir + '/' + import_path[1:]

    if not resolved_base:
        return None

    # Normalize path (handle multiple ../ etc)
    resolved_base = _normalize_path(resolved_base)

    # 3. Try extension/index variants against indexed paths
    extensions = ['.ts', '.tsx', '.js', '.jsx', '.vue', '']
    index_files = ['index.ts', 'index.tsx', 'index.js', 'index.jsx']

    # Try direct match with extensions
    for ext in extensions:
        candidate = resolved_base + ext
        if candidate in indexed_paths:
            return candidate

    # Try index file variants
    for index in index_files:
        candidate = resolved_base + '/' + index
        if candidate in indexed_paths:
            return candidate

    return None


def _normalize_path(path: str) -> str:
    """Normalize path by resolving . and .. segments."""
    parts = path.split('/')
    result = []
    for part in parts:
        if part == '..':
            if result:
                result.pop()
        elif part and part != '.':
            result.append(part)
    return '/'.join(result)
```

### 3.4 Schema Change

**Current `import_styles` schema** (from repo_index.db):
```sql
CREATE TABLE import_styles (
    file TEXT,
    line INTEGER,
    package TEXT,
    import_style TEXT,
    alias_name TEXT,
    full_statement TEXT
)
```

**Add** `resolved_path` column:
```sql
CREATE TABLE import_styles (
    file TEXT,
    line INTEGER,
    package TEXT,
    import_style TEXT,
    alias_name TEXT,
    full_statement TEXT,
    resolved_path TEXT          -- NEW: stores resolved file path (NULL if unresolved)
)
```

**Location**: Schema is defined dynamically in `theauditor/indexer/database/node_database.py` via the generic batch system. The column will be added to the batch insert tuple.

No migration needed - database is regenerated on each `aud full`.

### 3.5 Integration Point

The resolver is called from `theauditor/indexer/orchestrator.py` in the post-processing phase:

```python
# Location: theauditor/indexer/orchestrator.py:467 (after resolve_handler_file_paths)
# Add this block:
if os.environ.get("THEAUDITOR_DEBUG"):
    print("[INDEXER] PHASE 6.10: Resolving import paths...", file=sys.stderr)
JavaScriptExtractor.resolve_import_paths(self.db_manager.db_path)
self.db_manager.commit()
```

**Existing resolver calls** (for reference, lines 449-466):
```python
# Line 449:
JavaScriptExtractor.resolve_cross_file_parameters(self.db_manager.db_path)
# Line 457:
JavaScriptExtractor.resolve_router_mount_hierarchy(self.db_manager.db_path)
# Line 465:
JavaScriptExtractor.resolve_handler_file_paths(self.db_manager.db_path)
# Line 467 (ADD HERE):
JavaScriptExtractor.resolve_import_paths(self.db_manager.db_path)
```

### 3.6 Performance Comparison

| Approach | File Checks | DB Queries | Performance |
|----------|-------------|------------|-------------|
| **OLD (extraction-time)** | O(N × M) disk I/O per import | None | Slow |
| **NEW (post-indexing)** | Zero | 2 queries + O(1) set lookups | Fast |

Where N = imports to resolve, M = extension variants to try.

**Benchmark estimate**: 1000 imports × 6 extensions = 6000 `os.path.isfile()` calls → 0 calls

---

## 4. Open Questions

### 4.1 Vue In-Memory

1. **Q**: Does TypeScript checker work correctly with virtual files?
   **A**: Need to test. May need to adjust type checking configuration.

2. **Q**: How to handle Vue files that import other Vue files?
   **A**: All Vue files added to `vueContentMap` before program creation.

### 4.2 Module Resolution

1. **Q**: How to handle `exports` field complexity in package.json?
   **A**: N/A - node_modules packages are not indexed, so we don't resolve them.

2. **Q**: Should resolution results be persisted to database?
   **A**: **YES** - stored in `import_styles.resolved_path` column (new schema).

3. **Q**: What about tsconfig.json path mappings?
   **A**: First version uses convention-based aliases (`@/` → `src/`). Full tsconfig parsing is a future enhancement.

---

## 5. Rollback Plan

If issues discovered after deployment:

1. **Vue In-Memory**: Revert to disk-based temp files (functional, just slower)
2. **Module Resolution**: Skip calling `resolve_import_paths()` (column stays NULL, just less accurate)

Both are backwards-compatible. Schema change is additive (new column can be ignored).

---

## 6. Document History

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-28 | 3.0 | **LINE NUMBER SYNC**: Re-verified all line numbers. prepareVueSfcFile:134-180, orchestrator integration:467 |
| 2025-11-28 | 2.1 | **IRONCLAD**: Added current schema, exact integration point |
| 2025-11-28 | 2.0 | **ARCHITECTURE REWRITE**: Section 3 rewritten for post-indexing DB-first resolution |
| 2025-11-28 | 1.1 | Line numbers updated after schema normalizations |
| 2025-11-24 | 1.0 | Initial design document |
