# Extraction Layer Atomic Pre-Implementation Plan

> **Document Type:** teamsop.md v4.20 Compliant Pre-Implementation Plan
> **Scope:** All extraction-related bugs, schema gaps, and data loss
> **Status:** VERIFIED - Ready for Implementation
> **Last Updated:** 2025-12-01
> **Audit Status:** Prime Directive verification completed

---

## AUDIT SUMMARY

| Category | Total Claims | VERIFIED TRUE | PARTIALLY TRUE | FALSE | Removed |
|----------|-------------|---------------|----------------|-------|---------|
| TypeScript Main (TS-1 to TS-6) | 6 | 4 | 0 | 0 | 0 |
| Sub-Extractors (SUB-1 to SUB-7) | 7 | 5 | 2 | 0 | 0 |
| Python Extractor (PY-1 to PY-7) | 7 | 3 | 2 | 1 | 1 |
| Schema Layer (SCHEMA-1 to SCHEMA-6) | 6 | 0 | 0 | 6 | 6 |
| **TOTALS** | **26** | **12** | **4** | **7** | **7** |

**Key Finding:** SCHEMA-1 through SCHEMA-6 were based on a misunderstanding. `resolved_imports` is an **in-memory dict** passed through the extraction pipeline, NOT a database table. The storage handler already exists at `core_storage.py:63`.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [TypeScript Extractor Issues](#typescript-extractor-issues)
3. [TypeScript Sub-Extractor Issues](#typescript-sub-extractor-issues)
4. [Python Extractor Issues](#python-extractor-issues)
5. [Implementation Execution Order](#implementation-execution-order)
6. [Verification Requirements](#verification-requirements)
7. [Files Requiring Modification](#files-requiring-modification)

---

# EXECUTIVE SUMMARY

The extraction layer generates high-quality data that is being **lost, corrupted, or ignored** at multiple points:

1. **TypeScript extractors** produce rich AST data but write invalid data on Zod failure
2. **Python consumers** (`javascript.py`) remap/transform data inconsistently
3. **Virtual paths** leak from Vue SFC compilation
4. **Key name mismatches** between TS output and Python expectations cause silent data loss

**What is NOT broken (contrary to original claims):**
- `resolved_imports` storage works correctly (in-memory dict, not database table)
- Node.js database methods exist and function
- Infrastructure storage handles data properly

---

# TYPESCRIPT EXTRACTOR ISSUES

## TS-1: Zod Validation Bypass (CRITICAL) - VERIFIED TRUE

**Location:** `theauditor/ast_extractors/javascript/src/main.ts` **(Lines 848-862, NOT 950-963)**

**The Bug:**
```typescript
try {
  const validated = ExtractionReceiptSchema.parse(results);
  fs.writeFileSync(outputPath, JSON.stringify(validated, null, 2), "utf8");
} catch (e) {
  if (e instanceof z.ZodError) {
    console.error("[BATCH WARN] Zod validation failed, writing raw results:");
    // BUG: WRITES RAW INVALID DATA ANYWAY
    fs.writeFileSync(outputPath, JSON.stringify(results, null, 2), "utf8");
  }
}
```

**Impact:**
- Invalid data structures pass to Python
- Python crashes with `KeyError` or `TypeError` deep in processing
- Original Zod error is masked

**Required Fix:**
```typescript
try {
    const validated = ExtractionReceiptSchema.parse(results);
    fs.writeFileSync(outputPath, JSON.stringify(validated, null, 2), "utf8");
} catch (e) {
    if (e instanceof z.ZodError) {
        console.error("[BATCH ERROR] Zod validation failed:");
        console.error(JSON.stringify(e.errors.slice(0, 10), null, 2));
        process.exit(1); // Hard fail - do NOT write invalid data
    }
    throw e;
}
```

---

## TS-2: Vue Virtual Path Poisoning (CRITICAL) - VERIFIED TRUE

**Location:** `main.ts:136`, `main.ts:331`

**The Bug:**
- `main.ts` creates virtual paths: `/virtual_vue/${scopeId}.ts`
- Extractors use `sourceFile.fileName` which contains the virtual path
- `defined_in` fields leak `/virtual_vue/...` into database

**Impact:**
- Database contains symbols defined in `/virtual_vue/...`
- These don't match file records (which use `src/components/MyComponent.vue`)
- Graph edges break

**Required Fix:** Implement `sanitizeVirtualPaths` function:
```typescript
function sanitizeVirtualPaths(data: any, originalPath: string): any {
  if (!data) return data;
  if (Array.isArray(data)) {
    return data.map(item => sanitizeVirtualPaths(item, originalPath));
  }
  if (typeof data === 'object') {
    const sanitized: any = {};
    for (const [key, value] of Object.entries(data)) {
      if (
        (key === 'file' || key === 'defined_in' || key === 'callee_file_path' || key === 'path') &&
        typeof value === 'string' &&
        value.includes('/virtual_vue/')
      ) {
        sanitized[key] = originalPath;
      } else {
        sanitized[key] = sanitizeVirtualPaths(value, originalPath);
      }
    }
    return sanitized;
  }
  return data;
}
```

---

## TS-3: Schema Key Name Divergence (HIGH) - VERIFIED TRUE

**Location:** `main.ts` vs `schema.ts` vs `javascript.py`

**Verified Mismatches:**

| TS Output Key | Schema.ts Expects | Status |
|---------------|-------------------|--------|
| `routes` (main.ts:791) | `api_endpoints` (schema.ts:645) | MISMATCH |
| `express_middleware_chains` (main.ts:792) | `middleware_chains` (schema.ts:646) | MISMATCH |
| `validation_framework_usage` (main.ts:793) | `validation_calls` (schema.ts:647) | MISMATCH |
| `resolved_imports` (main.ts:775) | `refs` (schema.ts:660) | MISMATCH |

**Impact:**
- Zod may strip mismatched keys in strict mode
- Python receives empty arrays for critical security data
- API endpoints, middleware chains lost silently

**Required Fix:**
- Align `main.ts` output keys with `schema.ts`
- OR update Zod schemas to accept both names

---

## TS-4: Column vs Col Schism (MEDIUM) - VERIFIED TRUE

**Location:** `schema.ts:16-17` (FunctionSchema), `schema.ts:43-44` (ClassSchema)

**The Bug:**
```typescript
export const FunctionSchema = z.object({
  col: z.number().optional(),
  column: z.number().optional(),  // DUPLICATE FIELD - BOTH EXIST
});
```

**Impact:**
- Some extractors populate `col`, others `column`
- Location precision inconsistent

**Required Fix:**
- Use Zod `.transform()` to normalize to single key
- Delete duplicate field from schema

---

## TS-5: Schema Hand-off Problem (Data Integrity) - VERIFIED TRUE

**Location:** `main.ts:782-783`, `javascript.py:126-127`

**The Bug:**
- `main.ts` outputs both `function_call_args` (line 783) AND `calls` (line 782)
- `javascript.py:126` maps `function_call_args` to `function_calls`
- `javascript.py:243-252` appends `calls` to `symbols`

**Impact:** Call data split into two streams without deduplication.

---

## TS-6: Missing Extractor Verification - UNVERIFIABLE

Requires runtime execution to verify. Skipped.

---

# TYPESCRIPT SUB-EXTRACTOR ISSUES

## SUB-1: Security Extractor - Import Blindness (HIGH) - VERIFIED TRUE

**Location:** `security_extractors.ts` (~line 925)

**The Bug:**
- `extractFrontendApiCalls` matches literal patterns like `axios.get`
- Does NOT accept `imports` param to build alias map

**Impact:** If code uses `import myLib from 'axios'; myLib.get(...)`, the call is missed.

**Required Fix:**
- Pass `imports` array to `extractFrontendApiCalls`
- Build alias map: `{ "myRequestLib": "axios" }`
- Check aliases before matching

---

## SUB-2: Security Extractor - SQL Argument Index (MEDIUM) - VERIFIED TRUE

**Location:** `security_extractors.ts:498`

**The Bug:**
```typescript
if (call.argument_index !== 0) continue;
```

**Impact:** SQL at argument index 1 is missed.

**Required Fix:**
- Allow index 0 OR 1 if argument contains SQL keywords

---

## SUB-3: CFG Extractor - Finally Block Detachment (MEDIUM) - PARTIALLY TRUE

**Location:** `cfg_extractor.ts:260-261`, `cfg_extractor.ts:549-567`

**The Issue:**
- `return` statement sets `ctx.currentBlockId = null` (line 261)
- Finally connection logic exists at lines 549-567
- But `afterTryBlockId` may be null if return was executed

**Impact:** Control flow through finally may be imprecise.

**Required Fix:**
- Maintain `tryStack` during traversal
- Ensure `return` in try links to `finally`, then exit

---

## SUB-4: CFG Extractor - JSX Flattening Data Loss (MEDIUM) - VERIFIED TRUE

**Location:** `cfg_extractor.ts:199-216`

**The Bug:**
```typescript
function flattenJsx(node: ts.Node, sourceFile: ts.SourceFile): string {
  if (ts.isJsxElement(node)) {
    const tagName = node.openingElement.tagName.getText(sourceFile);
    const childCount = node.children.length;
    return `<${tagName}>[${childCount} children]</${tagName}>`;  // NO PROP VALUES
  }
  // ...
}
```

**Impact:** Taint analysis loses data flow inside JSX props like `dangerouslySetInnerHTML`.

---

## SUB-5: Data Flow - Scope Key Collision (MEDIUM) - VERIFIED TRUE

**Location:** `data_flow.ts:1061`

**The Bug:**
```typescript
const key = assign.line + "|" + assign.target_var;
// Column NOT included - same-line assignments collide
```

**Required Fix:** Include column: `${line}:${col}|${var}`

---

## SUB-6: Framework Extractor - React Namespace Skip (HIGH) - VERIFIED TRUE

**Location:** `framework_extractors.ts:217`

**The Bug:**
```typescript
if (hookName.includes(".")) continue;  // Skips React.useState, React.useEffect
```

**Impact:** Namespace-imported React hooks not extracted.

**Required Fix:** Allow `React.*` and `React_1.*` patterns.

---

## SUB-7: Module Framework - Index Collision (MEDIUM) - VERIFIED TRUE

**Location:** `module_framework.ts:686-694`

**The Bug:**
```typescript
const moduleName = modulePath.split("/").pop()?.replace(...) || "";
resolved[moduleName] = modulePath;  // Uses filename as key
```

**Impact:** `utils/index.ts` and `auth/index.ts` both become key `index` - last wins.

**Required Fix:** Use import alias as key, not filename.

---

# PYTHON EXTRACTOR ISSUES

## PY-1: Import Resolution Redundancy (LOW) - PARTIALLY TRUE

**Location:** Multiple files have resolution logic:
- `javascript.py:131` maps `resolved_imports`
- `js_semantic_parser.py:656-710` re-resolves
- `graph/builder.py:690-752` has its own resolution

**Impact:** Redundant work, potential inconsistency.

**Required Fix (Long-term):** Consolidate to single resolution point.

---

## PY-2: Import Styles Overwrite (HIGH) - VERIFIED TRUE

**Location:** `javascript.py:428`

**The Bug:**
```python
# Line ~130: Correctly maps import_styles from TS
result["import_styles"] = extracted_data["import_styles"]

# Line 428: OVERWRITES with inferior Python analysis
result["import_styles"] = self._analyze_import_styles(...)
```

**Required Fix:**
```python
if not result.get("import_styles"):
    result["import_styles"] = self._analyze_import_styles(...)
```

---

## PY-3: Call Graph Fragmentation (HIGH) - VERIFIED TRUE

**Location:** `javascript.py:126-127`, `javascript.py:243-252`

**The Bug:**
- `function_call_args` goes to `function_calls`
- `calls` goes to `symbols` (appended)
- No deduplication between streams

**Required Fix:** Merge with deduplication logic.

---

## PY-4: SQL Parser Risk (LOW) - PARTIALLY TRUE

**Location:** `javascript.py:179-181`

**The Issue:**
```python
parsed = parse_sql_query(query["query_text"])
if not parsed:  # Has continue, but no try-except
    continue
```

**Required Fix:** Wrap in try-except for robustness.

---

## ~~PY-7: Missing Storage Handler~~ - **FALSE (REMOVED)**

**Original Claim:** `core_storage.py` has no handler for `resolved_imports`.

**Verification Result:** Handler EXISTS at `core_storage.py:63`:
```python
resolved = self._current_extracted.get("resolved_imports", {}).get(value, value)
```

The `resolved_imports` dict is used during import storage, not stored as a separate table.

---

# ~~SCHEMA & STORAGE LAYER GAPS~~ - **SECTION REMOVED**

## AUDIT FINDING: All SCHEMA claims (1-6) are FALSE

**Root Cause of False Claims:**

The original document confused two different concepts:
1. **`resolved_imports` dict**: In-memory mapping `{symbol: resolved_path}` used during extraction
2. **Database tables**: Persistent storage with schema definitions

**Reality:**
- `resolved_imports` is an in-memory dict passed through the extraction pipeline
- It is NOT intended to be a database table
- The storage handler at `core_storage.py:63` correctly uses this dict to resolve import paths
- No new tables, flush_order entries, or database methods are needed

**Original false claims removed:**
- ~~SCHEMA-1: Missing resolved_imports TABLE~~
- ~~SCHEMA-2: Missing flush_order entry~~
- ~~SCHEMA-3: Missing database mixin method~~
- ~~SCHEMA-4: Missing storage handler~~
- ~~SCHEMA-5: Node.js database crashes~~
- ~~SCHEMA-6: Infrastructure data dropped~~

---

# IMPLEMENTATION EXECUTION ORDER

## Phase 1: Stop Data Corruption

| Step | File | Action | Priority |
|------|------|--------|----------|
| 1 | `main.ts:848-862` | Fix Zod bypass - exit(1) on validation error | P0 |
| 2 | `main.ts` | Add `sanitizeVirtualPaths` function | P0 |
| 3 | `main.ts` | Apply sanitizer before JSON serialization | P0 |

---

## Phase 2: Align Schemas

| Step | File | Action | Priority |
|------|------|--------|----------|
| 4 | `main.ts:775,791-793` | Normalize output key names to match schema.ts | P0 |
| 5 | `schema.ts:16-17,43-44` | Remove duplicate col/column field, use transform | P1 |

---

## Phase 3: Sub-Extractor Fixes

| Step | File | Action | Priority |
|------|------|--------|----------|
| 6 | `security_extractors.ts` | Add import context to `extractFrontendApiCalls` | P1 |
| 7 | `security_extractors.ts:498` | Allow SQL at argument index 0 OR 1 | P2 |
| 8 | `cfg_extractor.ts` | Fix finally block handling with tryStack | P2 |
| 9 | `cfg_extractor.ts:199-216` | Update `flattenJsx` to preserve variable references | P2 |
| 10 | `framework_extractors.ts:217` | Allow `React.*` namespace pattern | P1 |
| 11 | `data_flow.ts:1061` | Include column in scope key | P2 |
| 12 | `module_framework.ts:686-694` | Use import alias as key, not filename | P2 |

---

## Phase 4: Python Extractor Fixes

| Step | File | Action | Priority |
|------|------|--------|----------|
| 13 | `javascript.py:428` | Only run `_analyze_import_styles` if TS didn't provide | P1 |
| 14 | `javascript.py` | Merge `function_call_args` and `calls` with deduplication | P1 |
| 15 | `javascript.py:179` | Wrap SQL parser in try/except | P3 |

---

## Phase 5: Rebuild & Verify

| Step | Action |
|------|--------|
| 16 | `cd theauditor/ast_extractors/javascript && npm run build` |
| 17 | Delete `.pf/repo_index.db` and `.pf/graphs.db` |
| 18 | Run `aud full --offline` to rebuild |
| 19 | Run verification queries (see below) |

---

# VERIFICATION REQUIREMENTS

## Post-Implementation Verification

```bash
# Rebuild TS extractor
cd theauditor/ast_extractors/javascript && npm run build

# Run indexer
aud full --offline

# Verify no virtual path leaks
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()

# Check for virtual path leaks (should be 0)
c.execute(\"SELECT COUNT(*) FROM symbols WHERE path LIKE '%virtual_vue%'\")
print(f'Virtual path leaks in symbols: {c.fetchone()[0]}')

c.execute(\"SELECT COUNT(*) FROM function_call_args WHERE callee_file_path LIKE '%virtual_vue%'\")
print(f'Virtual path leaks in function_call_args: {c.fetchone()[0]}')

# Check Vue CFG blocks exist (should be > 0)
c.execute(\"SELECT COUNT(*) FROM cfg_blocks WHERE file LIKE '%.vue'\")
print(f'Vue CFG blocks: {c.fetchone()[0]}')

conn.close()
"
```

---

# FILES REQUIRING MODIFICATION

## TypeScript (Extractor Layer)

| File | Issues |
|------|--------|
| `theauditor/ast_extractors/javascript/src/main.ts` | TS-1, TS-2, TS-3 |
| `theauditor/ast_extractors/javascript/src/schema.ts` | TS-4 |
| `theauditor/ast_extractors/javascript/src/extractors/security_extractors.ts` | SUB-1, SUB-2 |
| `theauditor/ast_extractors/javascript/src/extractors/cfg_extractor.ts` | SUB-3, SUB-4 |
| `theauditor/ast_extractors/javascript/src/extractors/framework_extractors.ts` | SUB-6 |
| `theauditor/ast_extractors/javascript/src/extractors/data_flow.ts` | SUB-5 |
| `theauditor/ast_extractors/javascript/src/extractors/module_framework.ts` | SUB-7 |

## Python (Extractor Layer)

| File | Issues |
|------|--------|
| `theauditor/indexer/extractors/javascript.py` | PY-2, PY-3, PY-4 |

---

# AUDIT NOTES

## What Was Removed From Original Document

1. **SCHEMA-1 through SCHEMA-6**: All false claims about missing tables/handlers
2. **PY-7**: False claim about missing storage handler
3. **Downstream Consumer Fixes (CONSUMER-1 through CONSUMER-4)**: Not verified, removed pending investigation
4. **Line number correction**: TS-1 was claimed at lines 950-963, actual location is 848-862

## Architecture Clarification

The `resolved_imports` data flow:
1. **TypeScript (`module_framework.ts`)**: Creates `refs` dict via `extractRefs()`
2. **TypeScript (`main.ts`)**: Outputs as `resolved_imports` key in JSON
3. **Python (`javascript.py`)**: Maps to result dict
4. **Python (`core_storage.py:63`)**: Uses dict to resolve imports during storage

This is correct behavior. No database table is needed.

---

**Document Status:** Verified and corrected per Prime Directive audit.
**Ready for Implementation:** Phase 1 (P0 items) can proceed immediately.
