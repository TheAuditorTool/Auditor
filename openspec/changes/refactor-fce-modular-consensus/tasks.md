# Tasks: FCE Vector-Based Consensus Engine Refactor

## 0. Verification (Per teamsop.md - COMPLETE BEFORE IMPLEMENTATION)

- [x] 0.1 Read current `theauditor/fce.py` to understand existing structure
- [x] 0.2 Read `theauditor/context/query.py` to understand CodeQueryEngine pattern
- [x] 0.3 Audit database schema - identify table coordinate columns (file, line)
- [x] 0.4 Categorize 226 tables into Semantic Registry categories
- [x] 0.5 Prototype Universal Query - verify data can be joined across vectors
- [x] 0.6 Identify all hardcoded thresholds in current fce.py
- [x] 0.7 Document verification findings in verification.md

**Verification Status**: COMPLETE (Session 2025-12-03)
- 200/226 tables have file/path columns
- 115 tables have `line` column
- 43 files have 2+ vector convergence (data joins work)
- Hardcoded thresholds found: `complexity <= 20`, `coverage >= 50`, `percentile_90`

---

## 1. Foundation - Package Structure

- [ ] 1.1 Create `theauditor/fce/` package directory
- [ ] 1.2 Create `theauditor/fce/__init__.py` with public API exports
- [ ] 1.3 Create `theauditor/fce/schema.py` with Pydantic models:
  - `Vector` enum (STATIC, FLOW, PROCESS, STRUCTURAL)
  - `Fact` model
  - `VectorSignal` model with `density` property
  - `ConvergencePoint` model
  - `AIContextBundle` model
- [ ] 1.4 Write unit tests in `tests/fce/test_schema.py`:
  - Test Vector enum values
  - Test VectorSignal.density property returns 0.0-1.0
  - Test VectorSignal.density_label format
  - Test Pydantic validation for all models

**Acceptance Criteria:**
- All models validate correctly with sample data
- `VectorSignal.density` returns 0.0-1.0 based on vectors present
- No hardcoded thresholds in any model

---

## 2. Semantic Table Registry

- [ ] 2.1 Create `theauditor/fce/registry.py` with `SemanticTableRegistry` class
- [ ] 2.2 Populate RISK_SOURCES set (7 tables):
  ```
  findings_consolidated, taint_flows, cdk_findings,
  terraform_findings, graphql_findings_cache,
  python_security_findings, framework_taint_patterns
  ```
- [ ] 2.3 Populate CONTEXT_PROCESS set (4 tables)
- [ ] 2.4 Populate CONTEXT_STRUCTURAL set (15 tables)
- [ ] 2.5 Populate CONTEXT_FRAMEWORK set (29 tables)
- [ ] 2.6 Populate CONTEXT_SECURITY set (6 tables)
- [ ] 2.7 Populate CONTEXT_LANGUAGE set (86 tables)
- [ ] 2.8 Implement `get_context_tables_for_file(file_path)` method
- [ ] 2.9 Write unit tests in `tests/fce/test_registry.py`:
  - Test RISK_SOURCES contains expected tables
  - Test get_context_tables_for_file returns Python tables for .py files
  - Test get_context_tables_for_file returns React tables for .tsx files
  - Test all table sets are disjoint (no overlaps)

**Acceptance Criteria:**
- All 226 tables categorized (or explicitly excluded)
- `get_context_tables_for_file` returns relevant tables by extension
- Registry is static data, no database queries

---

## 3. FCEQueryEngine (Core)

- [ ] 3.1 Create `theauditor/fce/query.py` with `FCEQueryEngine` class
- [ ] 3.2 Implement `__init__(root: Path)` - connect to repo_index.db and graphs.db
- [ ] 3.3 Implement `_has_static_findings(file_path)` - query findings_consolidated
- [ ] 3.4 Implement `_has_flow_findings(file_path)` - query taint_flows
- [ ] 3.5 Implement `_has_process_data(file_path)` - query churn-analysis findings
- [ ] 3.6 Implement `_has_structural_data(file_path)` - query cfg-analysis findings
- [ ] 3.7 Implement `get_vector_density(file_path) -> VectorSignal`
- [ ] 3.8 Implement `get_convergence_points(min_vectors=2) -> list[ConvergencePoint]`
- [ ] 3.9 Implement `get_context_bundle(file_path, line) -> AIContextBundle`
- [ ] 3.10 Implement `close()` method for database connections
- [ ] 3.11 Write integration tests in `tests/fce/test_query.py`:
  - Test FCEQueryEngine.__init__ raises FileNotFoundError if no database
  - Test get_vector_density returns VectorSignal with correct vectors
  - Test get_convergence_points returns files with min_vectors met
  - Test _normalize_path handles relative and absolute paths
  - Test all SQL queries use parameterized inputs (no injection)

**Acceptance Criteria:**
- Follows CodeQueryEngine pattern exactly
- ZERO hardcoded thresholds
- Returns Pydantic models (not dicts)
- All queries use parameterized SQL (no injection)

---

## 4. FCE Formatter

- [ ] 4.1 Create `theauditor/fce/formatter.py` with `FCEFormatter` class
- [ ] 4.2 Implement `format_convergence_report(points: list[ConvergencePoint]) -> str`
- [ ] 4.3 Implement `format_vector_summary(signal: VectorSignal) -> str`
- [ ] 4.4 Implement `format_json(data) -> str` for JSON output mode
- [ ] 4.5 Write unit tests in `tests/fce/test_formatter.py`:
  - Test format_convergence_report produces readable text
  - Test format_vector_summary shows density correctly
  - Test format_json produces valid JSON
  - Test no emojis in any output

**Acceptance Criteria:**
- Text output is human-readable (terminal-friendly)
- JSON output is valid JSON
- No emojis in output (Windows CP1252 compatibility)

---

## 5. Command Integration

- [ ] 5.1 Update `theauditor/commands/fce.py`:
  - Import from `theauditor.fce` package
  - Add `--format [text|json]` option
  - Add `--min-vectors [1-4]` option (default: 2)
  - Remove all legacy code paths
- [ ] 5.2 Update `theauditor/fce/__init__.py` to export `run_fce()` function
- [ ] 5.3 Run `aud fce` end-to-end test
- [ ] 5.4 Verify output format matches spec

**Acceptance Criteria:**
- `aud fce` produces vector-based output
- `aud fce --format json` produces valid JSON
- No breaking changes to command interface (flags are additive)

---

## 6. Cleanup Legacy

- [ ] 6.1 Delete `theauditor/fce.py` (old monolith)
- [ ] 6.2 Search codebase for any imports from old location
- [ ] 6.3 Update any references to old meta-finding types
- [ ] 6.4 Remove subprocess tool execution code (if not already moved)
- [ ] 6.5 Final test: `aud fce` still works after cleanup

**Acceptance Criteria:**
- Old fce.py is deleted
- No orphaned imports
- All tests pass

---

## 7. Service API Integration (Phase 2 - Future)

- [ ] 7.1 Add `--fce` flag to `aud explain`
- [ ] 7.2 Add `--fce` flag to `aud blueprint`
- [ ] 7.3 Document service API usage for other commands
- [ ] 7.4 Write integration tests for `--fce` flags

**Note:** Phase 2 tasks depend on Phase 1 (1-6) completion.

---

## 8. Documentation

- [ ] 8.1 Update `aud fce --help` docstring with new options
- [ ] 8.2 Document new output format schema
- [ ] 8.3 Add migration notes for users of old format
- [ ] 8.4 Update CLAUDE.md if any new conventions

**Acceptance Criteria:**
- Help text explains vector-based signal density
- JSON schema is documented
- Migration path is clear

---

## Dependencies

```
0 (Verification)
    ↓
1 (Schema) → 2 (Registry)
    ↓           ↓
    └─────┬─────┘
          ↓
    3 (QueryEngine)
          ↓
    4 (Formatter)
          ↓
    5 (Command)
          ↓
    6 (Cleanup)
          ↓
    7 (Phase 2) → 8 (Docs)
```

---

## Effort Estimates

| Phase | Tasks | Complexity | Notes |
|-------|-------|------------|-------|
| 0 | Verification | LOW | Already done in brainstorm |
| 1 | Schema | LOW | Pydantic boilerplate |
| 2 | Registry | LOW | Static data categorization |
| 3 | QueryEngine | MEDIUM | Core logic, database queries |
| 4 | Formatter | LOW | String formatting |
| 5 | Command | LOW | Wire up existing code |
| 6 | Cleanup | LOW | Delete code |
| 7 | Phase 2 | MEDIUM | Cross-command integration |
| 8 | Docs | LOW | Documentation |

**Critical Path:** 1 → 3 → 5 (Schema → QueryEngine → Command)
