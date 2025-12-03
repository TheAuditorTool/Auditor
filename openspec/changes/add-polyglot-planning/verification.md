# Due Diligence: add-polyglot-planning

**Reviewed**: 2025-12-03
**Reviewer**: Claude (Opus 4.5)
**Verdict**: ~~NEEDS WORK~~ → **PASS** (Fixed 2025-12-03)

---

## Summary Table

| Category | Status | Issues Found |
|----------|--------|--------------|
| Proposal Structure | PASS | All 6 .md files present and complete |
| Schema Accuracy | ~~FAIL~~ PASS | ~~4 schema snippets have wrong columns~~ Fixed |
| Code References | ~~FAIL~~ PASS | ~~All line numbers stale~~ Updated to current |
| File Paths | ~~FAIL~~ PASS | ~~References directories~~ Corrected to single files |
| Blockers Documented | ~~PARTIAL~~ PASS | ~~Missing go_routes blocker~~ Added as BLOCKER 2 |
| Architecture Fit | PASS | Design integrates with existing systems |
| Task Breakdown | PASS | Clear, actionable steps |

---

## Critical Gaps

### 1. MISSING BLOCKER: `go_routes` Extractor Does Not Exist

**Severity**: CRITICAL

The proposal assumes `go_routes` table will be populated for boundary analysis and planning features. However:

- **go_impl.py** does NOT have `extract_go_routes()` function
- The file contains: `extract_go_functions`, `extract_go_methods`, `extract_go_goroutines`, `extract_go_captured_vars`
- NO route extraction logic exists for Go (Gin, Echo, Chi, etc.)

**Impact**: Polyglot boundary analysis for Go is impossible without this extractor.

**Required Fix**: Add `go_routes` to blockers section OR create new task for Go route extraction.

### 2. Schema Snippets Are Incorrect

**Severity**: HIGH

The design.md contains schema snippets that don't match actual implementation:

| Table | Proposal Claims | Actual Schema |
|-------|----------------|---------------|
| `go_functions` | Has `receiver_type` column | NO - receivers are in `go_methods` table |
| `bash_functions` | `body_start`, `body_end` | Actual: `body_start_line`, `body_end_line` |
| `rust_functions` | Oversimplified 6 columns | Actual has 12+ columns including visibility, async, unsafe, generic_params |

**Impact**: Anyone implementing from this spec will write wrong SQL queries.

### 3. All Code References Have Stale Line Numbers

**Severity**: MEDIUM

After 50+ commits, all line number references are off by 10-50 lines:

| Reference | Proposal Says | Actual Location |
|-----------|---------------|-----------------|
| blueprint.py naming conventions | 332-394 | 342-404 |
| blueprint.py dependencies | 1264-1366 | 1318-1420 |
| query.py framework info | 1439-1478 | 1375-1478 |
| deadcode_graph.py decorated entries | 237-268 | 237-253 (decorated) + 255-269 (framework) |

**Impact**: Developers will look at wrong code sections.

### 4. File Path References Are Wrong

**Severity**: MEDIUM

Proposal references directory structures that don't exist:

| Proposal References | Actual Path |
|--------------------|-------------|
| `theauditor/ast_extractors/go/` | `theauditor/ast_extractors/go_impl.py` |
| `theauditor/ast_extractors/rust/` | `theauditor/ast_extractors/rust_impl.py` |
| `theauditor/ast_extractors/bash/` | `theauditor/ast_extractors/bash_impl.py` |

**Impact**: File paths in proposal lead nowhere.

---

## Confirmed Blockers (Correctly Documented)

These blockers ARE correctly identified in the proposal:

1. **`rust_attributes` table** - Does not exist in rust_schema.py
2. **`cargo_package_configs` table** - Does not exist in infrastructure_schema.py
3. **`go_module_configs` table** - Does not exist (needs creation)

---

## Specific Fixes Required

### Fix 1: Add Missing Blocker to proposal.md

```markdown
## Blockers (Add to existing list)

### B4. Go Route Extraction Missing
- **File**: `theauditor/ast_extractors/go_impl.py`
- **Issue**: No `extract_go_routes()` function exists
- **Tables Affected**: `go_routes` (exists in schema but never populated)
- **Required**: Implement Go route extraction for Gin/Echo/Chi/Gorilla
- **Effort**: 2-3 hours
```

### Fix 2: Correct Schema Snippets in design.md

Replace `go_functions` snippet:
```sql
-- WRONG (in proposal)
CREATE TABLE go_functions (
    ...
    receiver_type TEXT,  -- DELETE THIS LINE
    ...
);

-- CORRECT (receivers are in go_methods)
CREATE TABLE go_functions (
    file TEXT,
    line INTEGER,
    end_line INTEGER,
    name TEXT,
    signature TEXT,
    return_type TEXT,
    is_exported INTEGER,
    package TEXT,
    doc_comment TEXT
);
```

Replace `bash_functions` snippet:
```sql
-- WRONG (in proposal)
body_start INTEGER,
body_end INTEGER,

-- CORRECT
body_start_line INTEGER,
body_end_line INTEGER,
```

### Fix 3: Update Line Number References

Update design.md code references to current line numbers:

```markdown
## Code References (Updated)

### blueprint.py
- Naming conventions: lines 342-404 (was 332-394)
- Dependencies analysis: lines 1318-1420 (was 1264-1366)

### query.py
- Framework info: lines 1375-1478 (was 1439-1478)

### deadcode_graph.py
- Decorated entry points: lines 237-253
- Framework entry points: lines 255-269
```

### Fix 4: Correct File Paths

Replace directory references with actual file paths:
```markdown
## Extractor Files

- Go: `theauditor/ast_extractors/go_impl.py` (single file, 1372 lines)
- Rust: `theauditor/ast_extractors/rust_impl.py` (single file, 1187 lines)
- Bash: `theauditor/ast_extractors/bash_impl.py` (single file)
```

---

## Files Read (Complete List)

### Proposal Documents
1. `proposal.md` - Full read
2. `design.md` - Full read
3. `tasks.md` - Full read
4. `specs/polyglot-planning/spec.md` - Full read
5. `specs/polyglot-deadcode/spec.md` - Full read
6. `specs/polyglot-boundaries/spec.md` - Full read

### Schema Verification
7. `theauditor/schemas/go_schema.py` - Full read
8. `theauditor/schemas/rust_schema.py` - Full read
9. `theauditor/schemas/bash_schema.py` - Full read
10. `theauditor/schemas/infrastructure_schema.py` - Full read

### Code Reference Verification
11. `theauditor/commands/blueprint.py` - Full read (1731 lines)
12. `theauditor/context/query.py` - Full read
13. `theauditor/context/deadcode_graph.py` - Full read (437 lines)
14. `theauditor/commands/boundaries.py` - Full read (249 lines)

### Extractor Architecture
15. `theauditor/ast_extractors/go_impl.py` - Full read (1372 lines)
16. `theauditor/ast_extractors/rust_impl.py` - Full read (1187 lines)

---

## Verdict Reasoning

**NEEDS WORK** because:

1. **Critical Missing Blocker**: The `go_routes` extractor doesn't exist, which breaks the entire polyglot boundary analysis for Go. This was not identified as a blocker.

2. **Schema Snippets Are Wrong**: A developer implementing from this spec would write incorrect SQL queries because the column names don't match actual schema.

3. **All Code References Are Stale**: The 50+ commits since this spec was written have shifted all line numbers by 10-50 lines. References point to wrong code.

4. **File Paths Don't Exist**: Directory references in the proposal lead to single files instead.

The proposal's architecture and approach are sound. The task breakdown is clear. But the spec is NOT "ironclad" - it requires detective work to reconcile claims with reality.

**Time to Fix**: ~30 minutes to update all references and add missing blocker.

---

## Fixes Applied (2025-12-03)

All issues identified above have been fixed:

### proposal.md
1. **Added BLOCKER 2** for missing `go_routes` extractor
2. **Fixed file paths** from directories to single files (go_impl.py, rust_impl.py, bash_impl.py)
3. **Updated line numbers** to current values after 50+ commits
4. **Added BLOCKER references** to affected tasks

### design.md
1. **Fixed go_functions schema** - removed incorrect `receiver_type` column, added correct columns
2. **Fixed rust_functions schema** - expanded from 6 to 14 columns matching actual schema
3. **Fixed bash_functions schema** - corrected column names (`body_start_line`/`body_end_line`)
4. **Updated line numbers** to current values
5. **Added BLOCKER note** to Decision 3 (go_routes)
6. **Updated risks table** - go_routes now HIGH risk with BLOCKER reference

### Verification Result
The proposal is now IRONCLAD:
- All schema snippets match actual code
- All line numbers verified against current codebase
- All blockers explicitly documented
- All file paths correct

## Recommendations

1. ~~Update proposal with fixes above~~ DONE
2. ~~Re-run `/check` after fixes~~ DONE - PASS
3. Consider adding a "Last Verified" timestamp to proposals
4. For future proposals: run verification immediately after creation before context drift occurs
