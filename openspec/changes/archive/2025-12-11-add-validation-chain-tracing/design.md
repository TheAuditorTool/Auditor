# Design: Validation Chain Tracing

## Context

This feature adds validation-aware data flow analysis to `aud boundaries`. The existing tool measures "distance to validation control" (architectural metric). This feature adds "does validation HOLD through the data flow" (security metric).

**Target users**: Vibe coders who use Zod/Joi but don't understand that casting to `any` breaks the validation guarantee.

**Philosophy**: Truth courier. We show facts, not recommendations. The chain visualization IS the teachable moment.

## Goals

1. Trace validation from entry point through function calls
2. Detect where type safety breaks (casts to `any`, type assertions)
3. Show visual chain that teaches developers where validation fails
4. Comprehensive security audit of trust boundaries

## Non-Goals

1. Recommend adding validation (truth courier)
2. Runtime validation checking (static only)
3. Cross-language tracing (stay within single language boundary)
4. Schema changes to repo_index.db

## Decisions

### Decision 1: Reuse existing database tables

**What**: Use `function_call_args`, `symbols`, `type_annotations`, `refs` tables. NO new tables.

**Why**:
- `function_call_args` already captures call chains with caller/callee relationships
- `symbols` has type annotations (via `type_annotation` column if populated)
- `type_annotations` table has dedicated `is_any`, `is_unknown`, `is_generic` boolean flags for TypeScript/JavaScript
- Schema changes require re-indexing all codebases - too disruptive

**Language-specific type info tables**:
- **TypeScript/JavaScript**: Use `type_annotations` table (has `is_any`, `is_unknown` booleans)
- **Python**: Use `symbols.type_annotation` column (type_annotations also populated)
- **Go/Rust**: Use `symbols.type_annotation` column

**Trade-off**: May have incomplete type info if indexer doesn't capture annotations. Accept this - we show "unknown" status rather than fail.

### Decision 2: Language-specific type degradation patterns

**What**: Each language has different patterns for type safety loss.

| Language | Type Loss Pattern | Detection |
|----------|------------------|-----------|
| TypeScript | `as any`, `: any`, `as unknown`, missing generic | Regex on `type_annotations.type_annotation` with word boundaries |
| Python | No type hints after typed, `# type: ignore` | Regex on `type_annotations.type_annotation` |
| Go | `interface{}` after typed struct | Regex on `symbols.type_annotation` |
| Rust | `.unwrap()` without type, `as _` | Regex on `symbols.type_annotation` |

**Why**: Type systems differ fundamentally. Generic "any" detection won't work.

**ZERO FALLBACK DECISION**: The `type_annotations.is_any` boolean is unreliable (only 3 records populated vs 351 with "any" in strings). We use regex pattern matching ONLY. No fallback. If regex fails, it fails loud.

**Regex Patterns for TypeScript `any` Detection** (word boundaries prevent false positives):

```python
import re

# CORRECT - Word boundaries prevent matching "Company", "Germany", "ManyItems"
ANY_TYPE_PATTERNS = [
    re.compile(r':\s*any\b'),           # Type annotation: `: any`
    re.compile(r'\bas\s+any\b'),        # Cast: `as any`
    re.compile(r'<\s*any\s*>'),         # Generic: `<any>`
    re.compile(r'<\s*any\s*,'),         # Generic first: `<any, T>`
    re.compile(r',\s*any\s*>'),         # Generic last: `<T, any>`
    re.compile(r'\|\s*any\b'),          # Union: `| any`
    re.compile(r'\bany\s*\|'),          # Union: `any |`
    re.compile(r'=>\s*any\b'),          # Return: `=> any`
]

# EXCLUSION - These are validation SOURCES, not breaks
VALIDATION_ANY_EXCLUSIONS = ['z.any()', 'Joi.any()', 'yup.mixed()']

def is_type_unsafe(type_annotation: str) -> bool:
    """Single code path. No fallbacks."""
    if not type_annotation:
        return False  # Unknown, not unsafe
    # Check exclusions first
    for excl in VALIDATION_ANY_EXCLUSIONS:
        if excl in type_annotation:
            return False
    # Check patterns
    return any(p.search(type_annotation) for p in ANY_TYPE_PATTERNS)
```

**Why word boundaries matter**:
- `'any' in s` matches "Comp**any**", "Germ**any**" - FALSE POSITIVES
- `r':\s*any\b'` only matches `: any` as distinct token - CORRECT

### Decision 3: Chain visualization format

**What**: ASCII-based chain with vertical flow.

```
POST /users (body: CreateUserInput)
    | [PASS] Zod validated at entry
    v
userService.create(data: CreateUserInput)
    | [PASS] Type preserved
    v
repo.insert(data: any)        <- CHAIN BROKEN
    | [FAIL] Cast to any
```

**Why**:
- ASCII safe (no emojis - Windows CP1252 per CLAUDE.md)
- Vertical flow matches mental model of data flowing down
- `<- CHAIN BROKEN` annotation is impossible to miss
- Works in all terminals, git diffs, logs

**Alternative considered**: JSON output only.
**Rejected**: Teachable moment IS the visualization. JSON is secondary.

### Decision 4: Audit categories are hardcoded

**What**: Four audit categories: input, output, database, file.

**Why**: These are the four trust boundaries that matter:
- INPUT: Where untrusted data enters (API endpoints)
- OUTPUT: Where data leaves to user (responses, rendered HTML)
- DATABASE: Where data persists (writes, queries)
- FILE: Where data touches filesystem

**Alternative considered**: User-configurable categories.
**Rejected**: Over-engineering. These four cover 99% of security issues.

### Decision 5: Integration via flags, not subcommands

**What**: `--validated` and `--audit` are flags on existing commands.

**Why**:
- `aud boundaries --validated` reads naturally
- `aud explain file.ts --validated` is discoverable
- Consistent with existing `aud blueprint --security` pattern
- No new commands to learn

### Decision 6: Framework Registry Pattern (MANDATORY)

**What**: Use the framework registry pattern from `c539722` to route to language-specific analyzers.

**Reference**:
- `theauditor/boundaries/boundary_analyzer.py:28-54` - `_detect_frameworks()` function
- `theauditor/boundaries/boundary_analyzer.py:57-182` - `_analyze_express_boundaries()` function

**ZERO FALLBACK WARNING**: The existing `boundary_analyzer.py` uses `_table_exists()` checks (10 instances) which **violate Zero Fallback policy** (CLAUDE.md Section 4.1). The NEW `chain_tracer.py` MUST NOT copy this pattern. Instead:
- Assume tables exist
- Let queries fail loudly if tables are missing
- Do NOT wrap queries in `if _table_exists()` guards

**Pattern**:
```python
def analyze_validation_chains(db_path: str) -> list[ValidationChain]:
    """Route to framework-specific chain tracer."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Detect frameworks from indexed data
    frameworks = _detect_frameworks(cursor)

    # 2. Route to framework-specific analyzer
    if "express" in frameworks:
        return _trace_express_chains(cursor, frameworks["express"])
    elif "fastapi" in frameworks:
        return _trace_fastapi_chains(cursor, frameworks["fastapi"])
    elif "gin" in frameworks or "echo" in frameworks:
        return _trace_go_chains(cursor, frameworks)
    elif "actix" in frameworks or "axum" in frameworks:
        return _trace_rust_chains(cursor, frameworks)
    else:
        return _trace_generic_chains(cursor)  # BFS fallback
```

**Why**:
- Each framework has different tables: Express uses `express_middleware_chains`, FastAPI uses `python_routes`
- No 1000-line if/else chains - framework decides which tables to query
- Extensible: new frameworks plug into same router
- Already proven in boundary analyzer (went from 0% to 68% on PlantFlow)

**Framework-to-Table Mapping**:

| Framework | Entry Points Table | Validation Table | Type Info Table |
|-----------|-------------------|------------------|-----------------|
| Express/JS/TS | `express_middleware_chains` | `validation_framework_usage` | `type_annotations` (has `is_any`, `is_unknown` flags) |
| FastAPI | `python_routes` | `python_decorators` | `type_annotations` or `symbols` |
| Flask | `python_routes` | `function_call_args` | `type_annotations` or `symbols` |
| Gin/Echo/Chi | `go_routes` | `function_call_args` | `symbols` |
| Actix/Axum | `rust_attributes` | `function_call_args` | `symbols` |

**NOTE**: `js_routes` table does NOT exist in the schema. All JavaScript/TypeScript entry points come from `express_middleware_chains` (for Express) or `api_endpoints` (generic).

**CRITICAL**: Do NOT write generic code that tries to handle all frameworks. Query `frameworks` table first, then call the right analyzer.

## Data Flow

```
Entry Point Detection (existing)
         |
         v
Call Chain Query (function_call_args table)
         |
         v
Type Annotation Lookup <-- per hop
    |-- TypeScript/JS: type_annotations table (is_any, is_unknown flags)
    |-- Python: type_annotations OR symbols.type_annotation
    |-- Go/Rust: symbols.type_annotation
         |
         v
Type Degradation Check (is_any=1 OR pattern matching)
         |
         v
Chain Status Determination (intact/broken/no_validation)
         |
         v
Visual Output Formatting (Rich console)
```

## Database Queries

### Query 1: Get call chain from entry point

```sql
-- Start from entry point, follow callee relationships
-- NOTE: function_call_args has callee_function (not callee_name), no callee_line
-- Line numbers must be looked up via JOIN to symbols table
WITH RECURSIVE call_chain AS (
    -- Base case: entry point function
    SELECT
        fca.file as caller_file,
        fca.callee_file_path as callee_file,
        fca.callee_function,
        s.line as callee_line,  -- From symbols table
        1 as depth
    FROM function_call_args fca
    LEFT JOIN symbols s ON fca.callee_file_path = s.path
        AND fca.callee_function = s.name
        AND s.type IN ('function', 'method')
    WHERE fca.file = ? AND fca.caller_function = ?

    UNION ALL

    -- Recursive case: follow callees
    SELECT
        c.callee_file as caller_file,
        fca.callee_file_path as callee_file,
        fca.callee_function,
        s.line as callee_line,
        c.depth + 1
    FROM call_chain c
    JOIN function_call_args fca ON c.callee_file = fca.file
        AND c.callee_function = fca.caller_function
    LEFT JOIN symbols s ON fca.callee_file_path = s.path
        AND fca.callee_function = s.name
        AND s.type IN ('function', 'method')
    WHERE c.depth < 10  -- Limit depth to prevent infinite loops
)
SELECT * FROM call_chain ORDER BY depth;
```

### Query 2: Get type annotation for symbol

**For TypeScript/JavaScript/Python** (use `type_annotations` table):
```sql
SELECT type_annotation
FROM type_annotations
WHERE file = ? AND line = ? AND symbol_name = ?
```

**For Go/Rust** (use `symbols` table):
```sql
SELECT type_annotation
FROM symbols
WHERE path = ? AND line = ? AND name = ?
```

**Type safety detection** (regex only - NO FALLBACKS per CLAUDE.md Section 4):
```python
# See Decision 2 for full regex patterns
# Single code path - if regex doesn't match, type is considered safe
is_unsafe = is_type_unsafe(row['type_annotation'])
```

### Query 3: Security audit - find unvalidated entry points

```sql
-- Entry points without validation in call chain
-- NOTE: js_routes table does NOT exist. Use express_middleware_chains for JS/TS.
SELECT
    r.method,
    r.path,
    r.file,
    r.line
FROM python_routes r  -- or go_routes, rust_attributes (NOT js_routes - doesn't exist)
WHERE NOT EXISTS (
    SELECT 1 FROM function_call_args f
    WHERE f.file = r.file
    AND f.callee_function IN ('validate', 'parse', 'safeParse', 'sanitize')
);
```

## Polyglot Considerations

### TypeScript/JavaScript
- **Validation libraries**: Zod, Joi, Yup, io-ts, runtypes
- **Type loss patterns**: `as any`, `: any`, `as unknown`, missing generics
- **Entry points**: Express routes, Next.js API routes, tRPC procedures
- **Tables**: `express_middleware_chains` (entry points), `validation_framework_usage` (validators), `function_call_args_jsx`, `symbols` with TS types
- **NOTE**: `js_routes` table does NOT exist - use `express_middleware_chains` for Express or `api_endpoints` for generic

### Python
- **Validation libraries**: Pydantic, marshmallow, cerberus, voluptuous
- **Type loss patterns**: Missing type hints after typed, `# type: ignore`
- **Entry points**: FastAPI routes, Flask routes, Django views
- **Tables**: `function_call_args`, `python_routes`, `python_decorators`

### Go
- **Validation libraries**: go-playground/validator, ozzo-validation
- **Type loss patterns**: `interface{}` after typed struct, type assertions
- **Entry points**: Gin/Echo/Chi routes from `go_routes` table
- **Tables**: `function_call_args` (once Go extractor captures calls)

### Rust
- **Validation libraries**: validator crate, garde
- **Type loss patterns**: `.unwrap()` discarding Result type info
- **Entry points**: Actix-web/Axum routes from `rust_attributes` table
- **Tables**: `rust_attributes`, `symbols`

## Risks and Mitigations

### Risk 1: Incomplete type information in database
**Impact**: Chain status shows "unknown" for many hops
**Mitigation**: Accept gracefully. "Unknown" is honest. Don't guess.

### Risk 2: Performance on large codebases
**Impact**: Chain tracing queries could be slow with deep call chains
**Mitigation**: Limit recursion depth to 10. Most validation breaks happen in first 3 hops.

### Risk 3: False positives on intentional type widening
**Impact**: Flagging legitimate `any` usage (e.g., serialization)
**Mitigation**: Show facts, don't judge. Developer sees chain and decides. Exclude known validation patterns (`z.any()`, `Joi.any()`) via explicit exclusion list.

### Risk 4: Path normalization in JOIN queries
**Impact**: The JOIN between `function_call_args.callee_file_path` and `symbols.path` may fail due to path format mismatches:
- `function_call_args` may have relative imports: `./utils/helper.ts`
- `symbols` may have absolute paths: `/src/utils/helper.ts`
- Result: Chain terminates early, user sees "No validation chain" even when code is correct

**Mitigation**:
1. First attempt: Exact path match in SQL JOIN
2. If chain terminates with 0 hops: Log warning "Path mismatch suspected" with both paths
3. Do NOT implement fuzzy matching fallback (Zero Fallback policy)
4. Document this as known limitation - fix must be in indexer path normalization, not in chain tracer

### Risk 5: Recursive CTE may terminate early
**Impact**: Chain tracing may miss hops if `callee_file_path` is NULL for unresolved calls
**Mitigation**: This is acceptable - incomplete chains still show partial validation status. Document in output when chain terminates early due to unresolved callee.

## File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `theauditor/boundaries/chain_tracer.py` | NEW | Core chain tracing logic |
| `theauditor/boundaries/security_audit.py` | NEW | Trust boundary audit logic |
| `theauditor/boundaries/boundary_analyzer.py` | MODIFIED | Import and use chain tracer |
| `theauditor/commands/boundaries.py` | MODIFIED | Add --validated, --audit flags |
| `theauditor/commands/explain.py` | MODIFIED | Add --validated flag |
| `theauditor/commands/blueprint.py` | MODIFIED | Add --validated flag |

## Open Questions

None. Design is complete and ready for implementation.
