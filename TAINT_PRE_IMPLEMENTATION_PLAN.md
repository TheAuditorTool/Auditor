# Taint Analysis Pre-Implementation Plan

> **Document Type**: Prime Directive Compliant Pre-Implementation Analysis
> **Date**: 2025-11-29
> **Status**: VERIFICATION PHASE - Pending Approval

---

## 1. EXECUTIVE SUMMARY

This document synthesizes the complete discussion from `taint.md` into an actionable implementation plan. The core problem is architectural: **Python code is guessing where JavaScript/TypeScript symbols live using regex, while the TypeScript extractor has TypeChecker access and KNOWS exactly where they are.**

### The Core Insight
```
"Stop Guessing, Start Asking"
- Current: Python guesses paths via regex patterns
- Fix: TypeScript tells Python the exact resolved paths
```

### Scope
- **14 discrete bugs** identified across 9 files
- **3 architectural improvements** required
- **4 verification queries** to measure progress

---

## 2. VERIFICATION PHASE - HYPOTHESES

### Hypothesis H1: TypeScript Extractor Not Resolving Paths
**Location**: `theauditor/ast_extractors/javascript/src/extractors/data_flow.ts:84-112`

**Claim**: The TS extractor uses `checker.getSymbolAtLocation()` but only extracts `resolvedName`, not the file path where the symbol is defined.

**Evidence from code**:
```typescript
// data_flow.ts lines 84-104
if (checker) {
  let symbol = checker.getSymbolAtLocation(callExpr.expression);
  // ... gets symbol ...
  if (symbol) {
    resolvedName = checker.getFullyQualifiedName(symbol);  // ← Name only!

    const declarations = symbol.getDeclarations();
    if (declarations && declarations.length > 0) {
      const declSourceFile = declarations[0].getSourceFile();
      if (projectRoot) {
        definedIn = path.relative(projectRoot, declSourceFile.fileName);  // ← FILE PATH EXISTS!
      }
    }
  }
}
```

**Verdict**: PARTIALLY VERIFIED - `definedIn` IS extracted for `calls` table, but NOT for `function_call_args`. The `extractFunctionCallArgs` function at line 548-562 does the same thing but stores in `callee_file_path`.

### Hypothesis H2: Python Resolver Uses Regex Guesswork
**Location**: `theauditor/indexer/extractors/javascript_resolvers.py`

**Claim**: Python code contains hardcoded path aliases and wrapper function lists.

**Evidence from code**:
```python
# javascript_resolvers.py (from my read)
# Hardcoded wrapper whitelist
type_wrappers = {'handler', 'fileHandler', 'asyncHandler', 'safeHandler', 'catchErrors'}

# Hardcoded path aliases
path_aliases = {
    '@controllers': '/src/controllers',
    '@services': '/src/services',
    # ...
}
```

**Verdict**: NEEDS VERIFICATION - Must read javascript_resolvers.py to confirm exact line numbers.

### Hypothesis H3: NodeExpressStrategy Mandates Import Style
**Location**: `theauditor/graph/strategies/node_express.py`

**Claim**: Lines 222-225 require a specific import style, rejecting valid middleware patterns.

**Evidence from code**:
```python
# node_express.py lines 223-238
def _resolve_middleware_handler(self, handler_expr: str, file_path: str) -> Optional[str]:
    """Resolve middleware expression to handler function name."""
    if not handler_expr:
        return None

    # Skip if it's an inline function
    if '=>' in handler_expr or 'function' in handler_expr:
        return None

    # Try to resolve as imported function
    # ...
```

**Verdict**: VERIFIED - Code does skip inline arrow functions, but this is intentional. The bug is that it doesn't link inline functions to parent scope.

### Hypothesis H4: NodeOrmStrategy Only Checks Sequelize
**Location**: `theauditor/graph/strategies/node_orm.py:36-40`

**Claim**: ORM detection only recognizes Sequelize, ignoring Prisma, TypeORM, raw SQL.

**Evidence from code**:
```python
# node_orm.py lines 34-56
def discover_edges(self) -> List[GraphEdge]:
    """Discover ORM-related edges."""
    edges = []

    # Get Sequelize model relationships
    cursor = self.conn.cursor()
    cursor.execute("""
        SELECT source_model, target_model, association_type, file
        FROM node_sequelize_associations
    """)
    # ONLY Sequelize!
```

**Verdict**: VERIFIED - Only queries `node_sequelize_associations`, no Prisma/TypeORM support.

### Hypothesis H5: Super-Node Path Explosion
**Location**: Graph traversal in `theauditor/graph/dfg_builder.py`

**Claim**: Generic services like Logger, PrismaService create "super nodes" with 50+ incoming edges, causing path explosion.

**Evidence**: Need to run verification query:
```sql
SELECT target, COUNT(*) as in_degree
FROM edges
WHERE graph_type = 'call'
GROUP BY target
HAVING in_degree > 20
ORDER BY in_degree DESC LIMIT 5;
```

**Verdict**: PENDING VERIFICATION

### Hypothesis H6: Air Gap in Route-to-Handler Links
**Location**: `theauditor/graph/strategies/node_express.py`

**Claim**: Express middleware chains have broken handler_file links, severing taint flow.

**Evidence**: Need to run verification query:
```sql
SELECT COUNT(*) as total_routes,
       SUM(CASE WHEN handler_file IS NULL THEN 1 ELSE 0 END) as broken_routes
FROM express_middleware_chains;
```

**Verdict**: PENDING VERIFICATION

---

## 3. IDENTIFIED BUGS (Prioritized)

### CRITICAL - Architecture Bugs

#### BUG-001: Python Guessing Instead of TypeScript Knowing
**Files Affected**:
- `javascript_resolvers.py` (consumer of wrong data)
- `data_flow.ts` (producer that COULD provide right data)
- `schema.ts` (needs new fields)

**Root Cause**: `function_call_args.callee_file_path` IS extracted in TypeScript but Python resolvers don't trust it and re-guess.

**Fix**:
1. Add `resolved_file_path` to schema for all relevant tables
2. Python code: DELETE regex resolution, USE TS-provided paths
3. Zero fallback: if TS says null, it's null (don't guess)

#### BUG-002: Cross-Boundary Link Severed for Anonymous Functions
**File**: `theauditor/graph/dfg_builder.py`

**Root Cause**: When `handler_function` is an anonymous arrow function, resolution returns `None`, breaking the taint chain from route → handler → sink.

**Fix**:
1. TypeScript: Synthesize names for anonymous functions (e.g., `<anonymous@routes.ts:42>`)
2. DFG Builder: Handle synthetic names in cross-boundary linking

### HIGH - Resolution Bugs

#### BUG-003: Hardcoded Wrapper Whitelist
**File**: `javascript_resolvers.py`

**Root Cause**: `type_wrappers = {'handler', 'fileHandler', 'asyncHandler', ...}` only recognizes these 5 patterns.

**Fix**:
1. TypeScript: Resolve wrapper calls to actual handler via TypeChecker
2. Python: Delete whitelist, trust TS resolution

#### BUG-004: Hardcoded Path Aliases
**File**: `javascript_resolvers.py`

**Root Cause**: `@controllers -> /src/controllers` is hardcoded, not read from tsconfig.json.

**Fix**:
1. TypeScript: Already has tsconfig loaded, just use resolved paths
2. Python: Delete alias guessing entirely

#### BUG-005: `.bind()` Pattern Only
**File**: `javascript_resolvers.py`

**Root Cause**: Regex for `.bind(` misses arrow functions and class properties.

**Fix**: Same as BUG-001 - TypeScript resolves all patterns

### MEDIUM - Strategy Bugs

#### BUG-006: NodeOrmStrategy Only Sequelize
**File**: `node_orm.py:34-56`

**Root Cause**: Only queries `node_sequelize_associations`, ignores other ORMs.

**Fix**:
1. Add queries for Prisma (`prisma.$queryRaw`, `prisma.model.findMany`)
2. Add queries for TypeORM (`repository.find`, `connection.query`)
3. Add raw SQL pattern detection from `sql_queries` table

#### BUG-007: Discovery Missing Repository Pattern
**File**: `discovery.py`

**Root Cause**: ORM sink detection uses model name matching, misses `userRepo.findAll()` pattern.

**Fix**:
1. Add repository pattern detection: `*Repo.find*`, `*Repository.query*`
2. Use function_call_args to find actual DB calls

#### BUG-008: Type Resolver Filename Pattern Fragility
**File**: `type_resolver.py`

**Root Cause**: `is_controller_file()` uses hardcoded patterns like `*controller.ts`.

**Fix**:
1. Use decorator detection: `@Controller`, `@RestController`
2. Use route registration: files that call `router.get/post/etc`

### LOW - Graph Quality Bugs

#### BUG-009: Super-Node Path Explosion
**File**: Graph traversal logic

**Root Cause**: Generic services (Logger, DB) have 50+ edges, creating bow-tie graphs.

**Fix**:
1. Add fan-in threshold (default: 50)
2. Mark high fan-in nodes as "utility" and exclude from path enumeration
3. Keep edges in graph but skip in taint propagation

#### BUG-010: Interceptors vs NodeExpress Conflicting Architectures
**Files**: `interceptors.py`, `node_express.py`

**Root Cause**: Both try to map middleware chains, may produce disconnected graphs.

**Fix**:
1. Audit both strategies for overlap
2. Ensure `input` node bridges to `req.body` node
3. Single source of truth for middleware chain discovery

---

## 4. IMPLEMENTATION PLAN

### Phase 1: TypeScript Patch (Foundation)
**Goal**: Make TS extractor the single source of truth for symbol resolution.

#### Task 1.1: Enhance `extractCalls` in data_flow.ts
```typescript
// Add to ICallSymbol interface in schema.ts
definition_file: z.string().nullable().optional(),
definition_line: z.number().nullable().optional(),

// Already exists but ensure it's populated
defined_in: z.string().nullable().optional(),
```

#### Task 1.2: Enhance `extractFunctionCallArgs` in data_flow.ts
**Current**: `callee_file_path` IS extracted (lines 548-562)
**Verify**: Confirm this data reaches Python storage layer

#### Task 1.3: Add Anonymous Function Naming
```typescript
// Synthesize names for arrow functions
if (ts.isArrowFunction(node)) {
  const line = sourceFile.getLineAndCharacterOfPosition(node.getStart()).line;
  return `<anonymous@${path.basename(sourceFile.fileName)}:${line + 1}>`;
}
```

### Phase 2: Schema Patch (Contract)
**Goal**: Ensure normalized schema captures resolved paths.

#### Task 2.1: Verify Node Schema Tables
Check these tables have file path columns:
- `node_function_call_args.callee_file_path` ✓ (exists in schema)
- `node_calls.defined_in` ✓ (exists in schema)
- `node_express_middleware_chains.handler_file` (NEEDS VERIFICATION)

#### Task 2.2: Add Missing Columns
If missing, add via migration:
```sql
ALTER TABLE node_express_middleware_chains
ADD COLUMN handler_file TEXT;
```

### Phase 3: Python Patch (Delete Guessing)
**Goal**: Remove all regex-based resolution, trust TS data.

#### Task 3.1: Audit javascript_resolvers.py
1. Find all regex patterns
2. Find all hardcoded lists
3. DOCUMENT before deleting

#### Task 3.2: Replace with DB Queries
```python
# OLD (guessing)
if handler_name in type_wrappers:
    # regex magic...

# NEW (trusting TS)
cursor.execute("""
    SELECT callee_file_path
    FROM node_function_call_args
    WHERE callee_function = ? AND callee_file_path IS NOT NULL
""", (handler_name,))
result = cursor.fetchone()
# If null, it's null. No fallback.
```

### Phase 4: Strategy Fixes
**Goal**: Fix individual strategy bugs.

#### Task 4.1: NodeOrmStrategy Multi-ORM Support
Add queries for:
- Prisma: `prisma.*` methods from `function_call_args`
- TypeORM: `repository.*` methods
- Raw SQL: Use `sql_queries` table

#### Task 4.2: Discovery Repository Pattern
Add detection for:
- `*Repo.*` → potential DB access
- `*Repository.*` → potential DB access
- `*Service.query*` → potential DB access

#### Task 4.3: Type Resolver Decorator Detection
Use decorator data:
```python
cursor.execute("""
    SELECT file, class_name
    FROM node_class_decorators
    WHERE decorator_name IN ('Controller', 'RestController', 'ApiController')
""")
```

### Phase 5: Graph Quality
**Goal**: Prevent path explosion, improve traversal.

#### Task 5.1: Super-Node Detection
```python
def is_super_node(node_id: str, threshold: int = 50) -> bool:
    cursor.execute("""
        SELECT COUNT(*) FROM edges WHERE target = ?
    """, (node_id,))
    return cursor.fetchone()[0] > threshold
```

#### Task 5.2: Utility Node Marking
Add `is_utility` column to nodes table, mark high fan-in nodes.

---

## 5. VERIFICATION QUERIES

These queries measure the health of taint analysis. Run BEFORE and AFTER fixes.

### Query V1: Air Gap Detection
```sql
-- Count broken route-to-handler links
SELECT
    COUNT(*) as total_chains,
    SUM(CASE WHEN handler_function IS NULL THEN 1 ELSE 0 END) as broken_handler,
    SUM(CASE WHEN handler_file IS NULL THEN 1 ELSE 0 END) as broken_file
FROM node_express_middleware_chains
WHERE handler_type = 'controller';
```

### Query V2: Super-Node Detection
```sql
-- Find nodes with excessive incoming edges
SELECT target, COUNT(*) as in_degree
FROM edges
WHERE graph_type = 'call'
GROUP BY target
HAVING in_degree > 20
ORDER BY in_degree DESC
LIMIT 10;
```

### Query V3: Missing Sink Detection
```sql
-- Find potential DB calls not marked as sinks
SELECT DISTINCT callee_function
FROM node_function_call_args
WHERE (
    callee_function LIKE '%find%'
    OR callee_function LIKE '%query%'
    OR callee_function LIKE '%execute%'
    OR callee_function LIKE '%.save%'
)
AND callee_function NOT IN (SELECT name FROM sinks)
LIMIT 20;
```

### Query V4: TypeScript Resolution Coverage
```sql
-- Check how many calls have resolved paths
SELECT
    COUNT(*) as total_calls,
    SUM(CASE WHEN callee_file_path IS NOT NULL THEN 1 ELSE 0 END) as resolved,
    ROUND(100.0 * SUM(CASE WHEN callee_file_path IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as pct_resolved
FROM node_function_call_args;
```

---

## 6. DEPENDENCIES AND ORDER

```
Phase 1 (TS Patch)
    ↓
Phase 2 (Schema Patch)
    ↓
Phase 3 (Python Patch) ← Depends on 1 & 2
    ↓
Phase 4 (Strategy Fixes) ← Can parallel with 3
    ↓
Phase 5 (Graph Quality) ← Depends on 4
```

### Critical Path
1. **MUST DO FIRST**: Task 1.2 (verify callee_file_path flows to DB)
2. **MUST DO SECOND**: Task 3.1 (audit javascript_resolvers.py before deleting)
3. **MUST DO THIRD**: Task 3.2 (replace guessing with DB queries)

---

## 7. RISK ASSESSMENT

### High Risk
- **Phase 3 (Python Patch)**: Deleting "working" code. Must have TS resolution verified first.
- **BUG-002 (Anonymous Functions)**: Synthetic names may break downstream parsing.

### Medium Risk
- **Phase 4 (Strategy Fixes)**: New queries may have performance impact on large codebases.

### Low Risk
- **Phase 1 (TS Patch)**: Additive changes, existing behavior preserved.
- **Phase 5 (Graph Quality)**: Filtering, not breaking existing paths.

---

## 8. SUCCESS CRITERIA

| Metric | Current (Estimated) | Target |
|--------|---------------------|--------|
| V1: Air Gap (broken handlers) | ~30% | < 5% |
| V2: Super-nodes (in_degree > 50) | Unknown | 0 (marked as utility) |
| V3: Missing sinks | Unknown | < 10 |
| V4: Resolution coverage | ~60% | > 90% |

---

## 9. NEXT STEPS

1. **IMMEDIATE**: Run V1-V4 queries against current repo_index.db to baseline
2. **IMMEDIATE**: Verify `callee_file_path` population in node_function_call_args
3. **APPROVAL NEEDED**: Confirm Phase 1 approach before implementation
4. **DECISION NEEDED**: Anonymous function naming convention

---

## 10. APPENDIX: FILES TO MODIFY

| File | Phase | Change Type |
|------|-------|-------------|
| `ast_extractors/javascript/src/schema.ts` | 1 | ADD fields |
| `ast_extractors/javascript/src/extractors/data_flow.ts` | 1 | ENHANCE extraction |
| `indexer/extractors/javascript_resolvers.py` | 3 | DELETE guessing |
| `graph/strategies/node_orm.py` | 4 | ADD Prisma/TypeORM |
| `graph/strategies/node_express.py` | 4 | FIX handler linking |
| `taint/discovery.py` | 4 | ADD repository pattern |
| `taint/type_resolver.py` | 4 | ADD decorator detection |
| `graph/dfg_builder.py` | 2, 5 | FIX anonymous, ADD utility marking |

---

**Document End**
