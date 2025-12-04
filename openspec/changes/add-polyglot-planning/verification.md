# Due Diligence: add-polyglot-planning

**Reviewed**: 2025-12-05
**Last Flight Check**: 2025-12-05 (third pass - post-refactor sanity check)
**Reviewer**: Claude (Opus 4.5)
**Verdict**: **NEEDS WORK** (Line numbers stale, blockers still valid)

---

## Summary Table

| Category | Status | Issues Found |
|----------|--------|--------------|
| Proposal Structure | PASS | All 7 .md files present and complete |
| Schema Accuracy | PASS | All schema snippets match actual code |
| Code References | **FAIL** | Line numbers for blueprint.py are 20 lines off |
| File Paths | PASS | All file paths are correct |
| Blockers Documented | PASS | Both blockers accurately reflect reality |
| Architecture Fit | PASS | Design integrates with existing systems |
| Task Breakdown | PASS | Clear, actionable steps |
| Loguru/Rich Logging | PASS | No conflicts, CP1252-safe implementation |
| Database State | PASS | Tables exist, blockers correctly identify missing data |

---

## Flight Check #3 (2025-12-05) - Post-Refactor Sanity Check

### Verification Method

1. Full read of all 7 proposal .md files
2. Full read of all 4 schema files (go, rust, bash, infrastructure)
3. Database queries to verify table existence and population
4. Grep verification of function line numbers
5. Loguru/Rich logging implementation review

### Database State Verification

```
=== go_routes table ===
Total: 5 rows (all gin framework) - WORKING

=== Go main functions ===
3 found in go_functions - WORKING

=== Rust main functions ===
3 found in rust_functions - WORKING

=== rust_attributes table ===
EXISTS: NO - BLOCKER 1 STILL VALID

=== symbols table (polyglot) ===
.py: 54,698
.ts: 7,636
.js: 5,369
.go: 0      <- BLOCKER 2 STILL VALID
.rs: 0      <- BLOCKER 2 STILL VALID
.sh: 0      <- BLOCKER 2 STILL VALID

=== refs table (polyglot) ===
.py: 8,870
.ts: 496
.js: 250
.go: 0      <- BLOCKER 2 STILL VALID
.rs: 0      <- BLOCKER 2 STILL VALID
.sh: 0      <- BLOCKER 2 STILL VALID

=== cargo_package_configs ===
EXISTS: YES (in rust_schema.py)
ROWS: 0 - Schema exists but not populated

=== go_module_configs ===
EXISTS: YES (in go_schema.py)
ROWS: 0 - Schema exists but not populated
```

### Line Number Verification (STALE)

| Function | Proposal Says | Actual Location | Delta |
|----------|---------------|-----------------|-------|
| `_get_naming_conventions` | 342-404 | **362**-424 | +20 lines |
| `_get_dependencies` | 1318-1420 | **1338**-1440 | +20 lines |
| `get_file_framework_info` | 1375-1478 | 1375-1478 | MATCH |
| `_find_decorated_entry_points` | 237-253 | 237-253 | MATCH |
| `_find_framework_entry_points` | 255-269 | 255-269 | MATCH |

### Schema File Locations

| Schema | Proposal Location | Actual Location | Status |
|--------|-------------------|-----------------|--------|
| `CARGO_PACKAGE_CONFIGS` | infrastructure_schema.py | **rust_schema.py:347-359** | WRONG FILE |
| `CARGO_DEPENDENCIES` | (not mentioned) | rust_schema.py:361-374 | NEW TABLE |
| `GO_MODULE_CONFIGS` | go_schema.py | go_schema.py:362-373 | MATCH |
| `GO_MODULE_DEPENDENCIES` | (not mentioned) | go_schema.py:375-387 | NEW TABLE |
| `rust_attributes` | needs creation | does not exist | BLOCKER |

### Loguru/Rich Logging Compatibility

**Status: PASS - No conflicts**

Evidence from `theauditor/utils/logging.py`:
- Line 81: `# Human-readable format (no emojis - Windows CP1252 compatibility)`
- Format uses ASCII-safe characters only
- No emoji usage in logging that would cause `UnicodeEncodeError`
- Rich integration properly implemented with `swap_to_rich_sink()` and `restore_stderr_sink()`

The polyglot-planning proposal does NOT touch logging infrastructure - no conflicts.

---

## Critical Gaps

### 1. LINE NUMBERS ARE STALE (Again)

**Severity**: MEDIUM

Since the last verification, more commits have shifted blueprint.py line numbers by 20 lines:

**Required Fix in proposal.md and design.md:**
```markdown
## blueprint.py Line Numbers (Updated 2025-12-05)
- Naming conventions: lines 362-424 (was 342-404)
- Dependencies analysis: lines 1338-1440 (was 1318-1420)
```

### 2. SCHEMA LOCATION INCORRECT

**Severity**: LOW (doesn't affect implementation)

Proposal says `cargo_package_configs` should be added to `infrastructure_schema.py`.

**Reality**: It already exists in `rust_schema.py:347-359` along with `cargo_dependencies`.

**Required Fix in proposal.md:**
```markdown
## Cargo Tables Location
- cargo_package_configs: ALREADY EXISTS in rust_schema.py (NOT infrastructure_schema.py)
- cargo_dependencies: ALREADY EXISTS in rust_schema.py
- No new table creation needed for Cargo
```

### 3. TASKS.MD HAS STALE TASK 2.1-2.2

**Severity**: MEDIUM

Tasks 2.1 (add cargo_package_configs schema) and 2.2 (add go_module_configs schema) are marked as TODO but the schemas **already exist**. These tasks should be marked as DONE or updated to focus on **populating** the tables.

---

## Blockers Still Valid

| Blocker | Status | Evidence |
|---------|--------|----------|
| BLOCKER 1 (rust_attributes) | STILL BLOCKED | `rust_attributes` table does not exist |
| BLOCKER 2 (unified tables) | STILL BLOCKED | symbols: .go=0, .rs=0, .sh=0 |

**BLOCKER 2 Impact:**
- Task 1.x (blueprint naming) - BLOCKED (queries symbols table)
- Task 6.x (graph edges) - BLOCKED (graph builder uses refs table)

---

## What's Working

1. **go_routes table** - 5 rows populated (gin framework)
2. **Go/Rust main function detection** - `go_functions` and `rust_functions` have main entries
3. **Schema definitions** - All required tables exist in schema files
4. **Loguru/Rich logging** - CP1252-safe, no emoji conflicts
5. **boundary_analyzer.py structure** - Correct file path, ready for Go/Rust additions

---

## Specific Fixes Required

### Fix 1: Update Line Numbers in proposal.md

**Location**: proposal.md Section "What Changes"
**Current**: References lines 342-404 and 1318-1420
**Required**: Update to 362-424 and 1338-1440

### Fix 2: Correct Schema Location in proposal.md

**Location**: proposal.md Section "Impact" > affected code
**Current**: `theauditor/indexer/schemas/infrastructure_schema.py (new table)`
**Required**: Remove - cargo tables already exist in rust_schema.py

### Fix 3: Update tasks.md Task 2.1-2.2

**Location**: tasks.md Section "2. Blueprint Dependencies"
**Current**:
```
- [ ] 2.1.1 Add CARGO_PACKAGE_CONFIGS TableSchema definition
- [ ] 2.2.1 Add GO_MODULE_CONFIGS TableSchema definition
```
**Required**:
```
- [x] 2.1.1 CARGO_PACKAGE_CONFIGS already exists (rust_schema.py:347)
- [x] 2.2.1 GO_MODULE_CONFIGS already exists (go_schema.py:362)
```

Focus should shift to Task 2.3/2.4 - **populating** these tables during indexing.

---

## Files Read (Complete List)

### Proposal Documents
1. `proposal.md` - Full read (254 lines)
2. `design.md` - Full read (496 lines)
3. `verification.md` - Full read (original 322 lines)
4. `tasks.md` - Full read (580 lines)
5. `specs/polyglot-planning/spec.md` - Full read (193 lines)
6. `specs/polyglot-deadcode/spec.md` - Full read (168 lines)
7. `specs/polyglot-boundaries/spec.md` - Full read (232 lines)

### Schema Verification
8. `theauditor/indexer/schemas/go_schema.py` - Full read (416 lines)
9. `theauditor/indexer/schemas/rust_schema.py` - Full read (401 lines)
10. `theauditor/indexer/schemas/bash_schema.py` - Full read (209 lines)
11. `theauditor/indexer/schemas/infrastructure_schema.py` - Full read (664 lines)

### Code Reference Verification
12. `theauditor/commands/blueprint.py` - Grep for function locations
13. `theauditor/context/query.py` - Grep for function locations
14. `theauditor/context/deadcode_graph.py` - Full read lines 230-290
15. `theauditor/boundaries/boundary_analyzer.py` - Full read (211 lines)

### Logging/Infrastructure
16. `theauditor/utils/logging.py` - Full read (265 lines)
17. OpenSpec AGENTS.md - Full read (457 lines)

### Database Verification
18. `.pf/repo_index.db` - Direct SQL queries for table state

---

## Verdict Reasoning

**NEEDS WORK** because:

1. **Line numbers are stale** - blueprint.py functions shifted +20 lines since last verification. A developer implementing Task 1.x would look at wrong code.

2. **Schema location is wrong** - Proposal says add to infrastructure_schema.py but cargo tables already exist in rust_schema.py. Minor but creates confusion.

3. **Tasks 2.1-2.2 are already done** - These tasks tell the developer to create schemas that already exist. Should be marked complete with focus on population tasks.

**NOT blocking because:**
- All blockers are correctly identified
- Core architecture and approach are sound
- Loguru/Rich logging has no conflicts
- Database state matches proposal expectations

**Time to Fix**: ~15 minutes to update line numbers, schema location, and task statuses.

---

## Recommendations

1. **Update proposal.md** with correct blueprint.py line numbers (362, 1338)
2. **Update proposal.md** to note cargo tables already exist in rust_schema.py
3. **Update tasks.md** to mark schema creation tasks as complete
4. Add a "Last Verified Date" field to proposal.md header
5. Consider adding automated line number validation to `/check` command
