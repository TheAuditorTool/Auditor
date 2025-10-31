# Implementation Tasks: Schema-Driven Taint Architecture

**Change ID**: `refactor-taint-schema-driven-architecture`
**Tracking**: 4-phase staged rollout with validation gates
**Status**: Pending Approval

---

## 0. Verification & Approval (Pre-Implementation)

- [x] 0.1 Read teamsop.md and understand Template C-4.20 requirements
- [x] 0.2 Read taint/database.py complete (1,447 lines verified)
- [x] 0.3 Read memory_cache.py and python_memory_cache.py (79KB verified)
- [x] 0.4 Read interprocedural*.py and cfg_integration.py (3 files verified)
- [x] 0.5 Verify 40+ manual loaders (confirmed)
- [x] 0.6 Verify hardcoded patterns (50+ patterns confirmed)
- [x] 0.7 Verify fallback logic never used (performance data confirms)
- [x] 0.8 Create verification.md with hypothesis verification
- [x] 0.9 Create design.md with technical decisions
- [x] 0.10 Create proposal.md with Why/What/Impact
- [x] 0.11 Create tasks.md (this file)
- [ ] 0.12 Receive Architect approval (User)
- [ ] 0.13 Receive Lead Auditor approval (Gemini)

**Gate**: DO NOT proceed to Phase 1 until approvals received

---

## Phase 1: Schema Auto-Generation (Week 1 - Non-Breaking)

**Objective**: Add code generation infrastructure without touching taint code
**Risk Level**: LOW (additive only, no existing code changes)

### 1.1 Schema Code Generator Infrastructure

- [ ] 1.1.1 Create `theauditor/indexer/schemas/codegen.py` (new file)
- [ ] 1.1.2 Add `SchemaCodeGenerator` class with base structure
- [ ] 1.1.3 Add utility functions (`_to_pascal_case`, `_python_type`, etc.)
- [ ] 1.1.4 Verify file structure: `python -m py_compile theauditor/indexer/schemas/codegen.py`

### 1.2 TypedDict Generation

- [ ] 1.2.1 Implement `generate_typed_dicts()` method
- [ ] 1.2.2 Test generation for `symbols` table (simple case)
- [ ] 1.2.3 Test generation for `python_orm_models` (complex case)
- [ ] 1.2.4 Test generation for all 70 tables (loop validation)
- [ ] 1.2.5 Verify generated TypedDicts: `mypy generated_types.py --strict`
- [ ] 1.2.6 Add docstrings to generated TypedDicts

### 1.3 Accessor Class Generation

- [ ] 1.3.1 Implement `generate_accessor_classes()` method
- [ ] 1.3.2 Generate `get_all()` for all tables
- [ ] 1.3.3 Generate `get_by_{column}()` for indexed columns
- [ ] 1.3.4 Test accessor for `symbols` table (simple case)
- [ ] 1.3.5 Test accessor for `python_orm_models` (complex case)
- [ ] 1.3.6 Test accessors for all 70 tables
- [ ] 1.3.7 Verify accessors: `python -c "from generated import SymbolsTable; print('OK')"`

### 1.4 Memory Cache Generation

- [ ] 1.4.1 Implement `generate_memory_cache()` method
- [ ] 1.4.2 Implement `SchemaMemoryCache.__init__()` (loads all tables)
- [ ] 1.4.3 Implement `_load_table()` generic loader
- [ ] 1.4.4 Implement `_build_index()` for indexed columns
- [ ] 1.4.5 Test cache instantiation: `cache = SchemaMemoryCache('test.db')`
- [ ] 1.4.6 Verify all 70 tables loaded: `assert len(cache.symbols) > 0`
- [ ] 1.4.7 Verify indexes built: `assert 'symbols_by_path' in dir(cache)`

### 1.5 Validation Decorator Generation

- [ ] 1.5.1 Implement `generate_validators()` method
- [ ] 1.5.2 Create `@validate_storage(table_name)` decorator
- [ ] 1.5.3 Test validator catches missing columns
- [ ] 1.5.4 Test validator catches type mismatches
- [ ] 1.5.5 Add validators to indexer storage methods (optional for Phase 1)

### 1.6 Integration & Testing

- [ ] 1.6.1 Add generation call to schema.py (on import or explicit)
- [ ] 1.6.2 Verify generated code doesn't break existing imports
- [ ] 1.6.3 Run full test suite: `pytest tests/ -v`
- [ ] 1.6.4 Profile SchemaMemoryCache memory usage (small project)
- [ ] 1.6.5 Profile SchemaMemoryCache memory usage (medium project)
- [ ] 1.6.6 Profile SchemaMemoryCache memory usage (large project)
- [ ] 1.6.7 Document memory usage in verification.md

### 1.7 Phase 1 Validation Gate

- [ ] 1.7.1 All generated code compiles
- [ ] 1.7.2 TypedDicts pass mypy --strict
- [ ] 1.7.3 Accessors return correct data
- [ ] 1.7.4 SchemaMemoryCache loads all 70 tables
- [ ] 1.7.5 Memory usage within 500MB for large project
- [ ] 1.7.6 Zero impact on existing taint code (not used yet)
- [ ] 1.7.7 All tests pass: `pytest tests/ -v`

**Gate**: DO NOT proceed to Phase 2 until all Phase 1 validation passes

---

## Phase 2: Replace Memory Cache (Week 2 - Internal Change)

**Objective**: Replace manual cache loaders with SchemaMemoryCache
**Risk Level**: MEDIUM (internal refactor, feature flagged)

### 2.1 Feature Flag Infrastructure

- [ ] 2.1.1 Add feature flag: `THEAUDITOR_SCHEMA_CACHE` environment variable
- [ ] 2.1.2 Update taint/core.py to check feature flag
- [ ] 2.1.3 Test flag detection: `export THEAUDITOR_SCHEMA_CACHE=1 && aud taint-analyze --help`

### 2.2 Update TaintAnalyzer to Use SchemaMemoryCache

- [ ] 2.2.1 Modify `taint/core.py` TaintAnalyzer.__init__()
- [ ] 2.2.2 Add conditional: if feature flag, use SchemaMemoryCache
- [ ] 2.2.3 Add conditional: else use old memory_cache.py
- [ ] 2.2.4 Update cache attribute access: `cache.symbols` instead of `cache.get_symbols()`
- [ ] 2.2.5 Update indexed access: `cache.symbols_by_path[file]` instead of dict building

### 2.3 Update Taint Modules to Use Cache Attributes

- [ ] 2.3.1 Update `taint/propagation.py` cache access patterns
- [ ] 2.3.2 Update `taint/interprocedural.py` cache access patterns
- [ ] 2.3.3 Update `taint/interprocedural_cfg.py` cache access patterns
- [ ] 2.3.4 Update `taint/cfg_integration.py` cache access patterns
- [ ] 2.3.5 Update `taint/orm_utils.py` cache access patterns (if needed)

### 2.4 Parallel Validation (Old vs New Cache)

- [ ] 2.4.1 Run taint with old cache on fixture project → save results
- [ ] 2.4.2 Run taint with new cache (feature flag) → save results
- [ ] 2.4.3 Compare results: taint paths identical
- [ ] 2.4.4 Compare results: source count identical
- [ ] 2.4.5 Compare results: sink count identical
- [ ] 2.4.6 Profile performance: old cache baseline
- [ ] 2.4.7 Profile performance: new cache (should be same or better)

### 2.5 Smoke Testing

- [ ] 2.5.1 Test with feature flag ON: `aud taint-analyze` on small project
- [ ] 2.5.2 Test with feature flag ON: `aud taint-analyze` on medium project
- [ ] 2.5.3 Test with feature flag ON: `aud full` pipeline
- [ ] 2.5.4 Test with feature flag OFF: `aud taint-analyze` (old cache)
- [ ] 2.5.5 Verify no regressions in old cache path

### 2.6 Phase 2 Validation Gate

- [ ] 2.6.1 Taint results IDENTICAL (old vs new cache)
- [ ] 2.6.2 Memory usage within limits (<=500MB)
- [ ] 2.6.3 Performance same or better
- [ ] 2.6.4 All tests pass with feature flag ON
- [ ] 2.6.5 All tests pass with feature flag OFF
- [ ] 2.6.6 Zero schema cache errors in logs
- [ ] 2.6.7 Feature flag toggle works correctly

**Gate**: DO NOT proceed to Phase 3 until all Phase 2 validation passes

---

## Phase 3: Database-Driven Discovery (Week 3 - Delete Patterns)

**Objective**: Replace hardcoded patterns with database-driven discovery
**Risk Level**: MEDIUM (behavior change, feature flagged)

### 3.1 Implement Database-Driven Source Discovery

- [ ] 3.1.1 Add `discover_sources()` method to TaintAnalyzer
- [ ] 3.1.2 Implement HTTP request source discovery (query api_endpoints)
- [ ] 3.1.3 Implement user input source discovery (query symbols for property access)
- [ ] 3.1.4 Implement file read source discovery (query function_call_args)
- [ ] 3.1.5 Implement environment variable source discovery (query symbols)
- [ ] 3.1.6 Add risk classification logic (high/medium/low)
- [ ] 3.1.7 Add metadata enrichment (API context, auth flags)

### 3.2 Implement Database-Driven Sink Discovery

- [ ] 3.2.1 Add `discover_sinks()` method to TaintAnalyzer
- [ ] 3.2.2 Implement SQL sink discovery (query sql_queries table)
- [ ] 3.2.3 Implement SQL risk assessment (check for concatenation vs parameterization)
- [ ] 3.2.4 Implement ORM sink discovery (query orm_queries table)
- [ ] 3.2.5 Implement command sink discovery (query function_call_args)
- [ ] 3.2.6 Implement XSS sink discovery (query react_hooks + function_call_args)
- [ ] 3.2.7 Implement path traversal sink discovery (query function_call_args)

### 3.3 Feature Flag for Discovery Method

- [ ] 3.3.1 Add feature flag: `THEAUDITOR_DISCOVER_SOURCES` environment variable
- [ ] 3.3.2 Update core.py to choose discovery method based on flag
- [ ] 3.3.3 Conditional: if flag ON, use discover_sources/discover_sinks
- [ ] 3.3.4 Conditional: if flag OFF, use old hardcoded patterns

### 3.4 Parallel Validation (Hardcoded vs Database-Driven)

- [ ] 3.4.1 Run with hardcoded patterns on fixture project → save sources/sinks
- [ ] 3.4.2 Run with database-driven (feature flag) → save sources/sinks
- [ ] 3.4.3 Compare: Are all previous sources still found? (no false negatives)
- [ ] 3.4.4 Compare: Are any new sources found? (document as improvements)
- [ ] 3.4.5 Compare: Are all previous sinks still found? (no false negatives)
- [ ] 3.4.6 Compare: Are any new sinks found? (document as improvements)
- [ ] 3.4.7 Analyze false positives: acceptable rate? (document threshold)

### 3.5 Update Tests to Use Database-Driven Discovery

- [ ] 3.5.1 Update test fixtures to populate tables (not just hardcoded patterns)
- [ ] 3.5.2 Update test assertions (sources found = query result, not pattern match)
- [ ] 3.5.3 Add tests for discovery classification logic
- [ ] 3.5.4 Add tests for risk assessment logic

### 3.6 Phase 3 Validation Gate

- [ ] 3.6.1 All previous sources still discovered (no false negatives)
- [ ] 3.6.2 All previous sinks still discovered (no false negatives)
- [ ] 3.6.3 False positive rate acceptable (documented threshold)
- [ ] 3.6.4 Performance same or better (discovery vs pattern matching)
- [ ] 3.6.5 All tests pass with discovery flag ON
- [ ] 3.6.6 All tests pass with discovery flag OFF
- [ ] 3.6.7 Feature flag toggle works correctly

**Gate**: DO NOT proceed to Phase 4 until all Phase 3 validation passes

---

## Phase 4: Delete Fallback & Unify CFG (Week 4 - Complete Refactor)

**Objective**: Delete dead code and unify CFG implementations
**Risk Level**: HIGH (massive deletion, single implementation)

### 4.1 Delete taint/database.py (1,447 lines)

- [ ] 4.1.1 Grep for all imports of taint.database: `rg "from.*taint.*database import"`
- [ ] 4.1.2 Verify NO references remain (all migrated to cache)
- [ ] 4.1.3 Backup file: `cp taint/database.py taint/database.py.backup`
- [ ] 4.1.4 Delete file: `git rm theauditor/taint/database.py`
- [ ] 4.1.5 Verify no import errors: `python -c "import theauditor.taint; print('OK')"`

### 4.2 Delete Manual Cache Loaders

- [ ] 4.2.1 Grep for references to memory_cache.py: `rg "memory_cache import"`
- [ ] 4.2.2 Verify NO references remain (all use SchemaMemoryCache)
- [ ] 4.2.3 Backup: `cp taint/memory_cache.py taint/memory_cache.py.backup`
- [ ] 4.2.4 Delete: `git rm theauditor/taint/memory_cache.py`
- [ ] 4.2.5 Backup: `cp taint/python_memory_cache.py taint/python_memory_cache.py.backup`
- [ ] 4.2.6 Delete: `git rm theauditor/taint/python_memory_cache.py`

### 4.3 Delete Hardcoded Registries

- [ ] 4.3.1 Grep for TAINT_SOURCES usage: `rg "TAINT_SOURCES"`
- [ ] 4.3.2 Verify NO references remain (all use discover_sources)
- [ ] 4.3.3 Backup: `cp taint/sources.py taint/sources.py.backup`
- [ ] 4.3.4 Delete: `git rm theauditor/taint/sources.py`
- [ ] 4.3.5 Grep for SECURITY_SINKS usage: `rg "SECURITY_SINKS"`
- [ ] 4.3.6 Verify NO references remain (all use discover_sinks)
- [ ] 4.3.7 Backup: `cp taint/config.py taint/config.py.backup`
- [ ] 4.3.8 Delete: `git rm theauditor/taint/config.py`

### 4.4 Delete Registry System

- [ ] 4.4.1 Grep for registry.py usage: `rg "from.*registry import"`
- [ ] 4.4.2 Verify NO references remain (registry no longer needed)
- [ ] 4.4.3 Backup: `cp taint/registry.py taint/registry.py.backup`
- [ ] 4.4.4 Delete: `git rm theauditor/taint/registry.py`

### 4.5 Create Unified analysis.py

- [ ] 4.5.1 Create `theauditor/taint/analysis.py` (new file)
- [ ] 4.5.2 Define `TaintFlowAnalyzer` class structure
- [ ] 4.5.3 Copy CFG utilities from cfg_integration.py (BlockTaintState, PathAnalyzer)
- [ ] 4.5.4 Copy interprocedural logic from interprocedural_cfg.py
- [ ] 4.5.5 Merge with CFG entry point from interprocedural.py
- [ ] 4.5.6 Remove flow-insensitive implementation (never used)
- [ ] 4.5.7 Update to use cache attributes directly (no database queries)

### 4.6 Delete Old CFG Files

- [ ] 4.6.1 Grep for interprocedural.py imports: `rg "interprocedural import"`
- [ ] 4.6.2 Update imports to point to analysis.py
- [ ] 4.6.3 Backup: `cp taint/interprocedural.py taint/interprocedural.py.backup`
- [ ] 4.6.4 Delete: `git rm theauditor/taint/interprocedural.py`
- [ ] 4.6.5 Backup: `cp taint/interprocedural_cfg.py taint/interprocedural_cfg.py.backup`
- [ ] 4.6.6 Delete: `git rm theauditor/taint/interprocedural_cfg.py`
- [ ] 4.6.7 Backup: `cp taint/cfg_integration.py taint/cfg_integration.py.backup`
- [ ] 4.6.8 Delete: `git rm theauditor/taint/cfg_integration.py`

### 4.7 Update core.py to Use Unified Analyzer

- [ ] 4.7.1 Import TaintFlowAnalyzer from analysis.py
- [ ] 4.7.2 Remove old interprocedural imports
- [ ] 4.7.3 Update analysis calls to use TaintFlowAnalyzer
- [ ] 4.7.4 Remove feature flags (schema cache + discovery now mandatory)
- [ ] 4.7.5 Simplify TaintAnalyzer.__init__ (no conditional logic)

### 4.8 Update propagation.py

- [ ] 4.8.1 Remove any database query fallbacks
- [ ] 4.8.2 Use cache attributes exclusively
- [ ] 4.8.3 Simplify logic (no optional cache parameter)

### 4.9 Update __init__.py Exports

- [ ] 4.9.1 Remove exports for deleted modules
- [ ] 4.9.2 Add export for TaintFlowAnalyzer (if public)
- [ ] 4.9.3 Verify public API unchanged: TaintAnalyzer entry point

### 4.10 Comprehensive Testing

- [ ] 4.10.1 Run full test suite: `pytest tests/ -v`
- [ ] 4.10.2 Test on small project: `aud taint-analyze`
- [ ] 4.10.3 Test on medium project: `aud taint-analyze`
- [ ] 4.10.4 Test on large project: `aud taint-analyze`
- [ ] 4.10.5 Run full pipeline: `aud full`
- [ ] 4.10.6 Verify taint findings match baseline (golden tests)
- [ ] 4.10.7 Profile performance: compare to baseline

### 4.11 Phase 4 Validation Gate

- [ ] 4.11.1 All 9 files successfully deleted (database, caches, patterns, CFG)
- [ ] 4.11.2 analysis.py created and functional (~800 lines)
- [ ] 4.11.3 100% test pass rate
- [ ] 4.11.4 Taint findings match baseline (no regressions)
- [ ] 4.11.5 Performance same or better (should be faster)
- [ ] 4.11.6 Memory usage within 500MB
- [ ] 4.11.7 No import errors across codebase
- [ ] 4.11.8 Public API unchanged (`aud taint-analyze`)

**Gate**: DO NOT commit until all Phase 4 validation passes

---

## 5. Final Integration & Documentation

### 5.1 Code Quality

- [ ] 5.1.1 Run linter: `ruff check theauditor/indexer/schemas/ theauditor/taint/`
- [ ] 5.1.2 Run formatter: `ruff format theauditor/indexer/schemas/ theauditor/taint/`
- [ ] 5.1.3 Run type checker: `mypy theauditor/taint/ --strict` (if type hints added)
- [ ] 5.1.4 Fix any linting/formatting issues

### 5.2 Documentation Updates

- [ ] 5.2.1 Update CLAUDE.md (remove references to deleted files)
- [ ] 5.2.2 Update CLAUDE.md (add schema generation section)
- [ ] 5.2.3 Update docstrings in TaintAnalyzer
- [ ] 5.2.4 Update docstrings in TaintFlowAnalyzer
- [ ] 5.2.5 Document schema generation in schema.py header

### 5.3 Performance Benchmarking

- [ ] 5.3.1 Benchmark baseline (old architecture) on 5 projects
- [ ] 5.3.2 Benchmark new architecture on same 5 projects
- [ ] 5.3.3 Calculate speedup (should be same or faster)
- [ ] 5.3.4 Document results in verification.md
- [ ] 5.3.5 Profile memory usage (verify <=500MB)

### 5.4 Regression Testing

- [ ] 5.4.1 Run golden test suite (known vulnerabilities)
- [ ] 5.4.2 Verify all known vulnerabilities still detected
- [ ] 5.4.3 Document any differences (improvements or regressions)
- [ ] 5.4.4 Test edge cases: empty project, no sources, no sinks

### 5.5 Developer Velocity Test

- [ ] 5.5.1 Add test feature: Vue v-model XSS detection
- [ ] 5.5.2 Count layers changed (should be 3, not 8)
- [ ] 5.5.3 Time implementation (should be faster)
- [ ] 5.5.4 Document experience in verification.md
- [ ] 5.5.5 Verify feature works correctly

---

## 6. Commit & Post-Implementation

### 6.1 Git Preparation

- [ ] 6.1.1 Review changes: `git status`
- [ ] 6.1.2 Verify files modified/added/deleted:
  - M  theauditor/indexer/schema.py
  - A  theauditor/indexer/schemas/codegen.py
  - M  theauditor/taint/core.py
  - M  theauditor/taint/propagation.py
  - A  theauditor/taint/analysis.py
  - D  theauditor/taint/database.py
  - D  theauditor/taint/memory_cache.py
  - D  theauditor/taint/python_memory_cache.py
  - D  theauditor/taint/sources.py
  - D  theauditor/taint/config.py
  - D  theauditor/taint/registry.py
  - D  theauditor/taint/interprocedural.py
  - D  theauditor/taint/interprocedural_cfg.py
  - D  theauditor/taint/cfg_integration.py
- [ ] 6.1.3 Review diff: `git diff theauditor/`
- [ ] 6.1.4 Stage files: `git add theauditor/`

### 6.2 Commit Message (teamsop.md Compliance)

- [ ] 6.2.1 Write comprehensive commit message following template
- [ ] 6.2.2 Include verification findings summary
- [ ] 6.2.3 Include root cause analysis (schema maturity, architectural debt)
- [ ] 6.2.4 Include implementation summary (4 phases)
- [ ] 6.2.5 Include performance metrics (before/after)
- [ ] 6.2.6 Reference OpenSpec change ID: `refactor-taint-schema-driven-architecture`

### 6.3 Final Commit

- [ ] 6.3.1 Create atomic commit: `git commit`
- [ ] 6.3.2 Verify commit created successfully
- [ ] 6.3.3 Tag commit: `git tag refactor-taint-schema-driven`
- [ ] 6.3.4 Document rollback plan: save commit hash

### 6.4 Post-Commit Validation

- [ ] 6.4.1 Fresh clone test: Clone repo and run `aud full`
- [ ] 6.4.2 Clean install test: Fresh virtualenv and `pip install -e .`
- [ ] 6.4.3 Smoke test: `aud taint-analyze` on production project
- [ ] 6.4.4 Monitor for errors in first 24 hours

---

## 7. Post-Implementation Audit (teamsop.md Section 5)

### 7.1 File Integrity Audit

- [ ] 7.1.1 Re-read schema.py (verify generation code correct)
- [ ] 7.1.2 Re-read taint/analysis.py (verify unified CFG correct)
- [ ] 7.1.3 Re-read taint/core.py (verify SchemaMemoryCache usage correct)
- [ ] 7.1.4 Verify no syntax errors across all modified files
- [ ] 7.1.5 Verify no logical flaws introduced
- [ ] 7.1.6 Verify no unintended side effects

### 7.2 Success Metrics Verification (From proposal.md)

- [ ] 7.2.1 ✅ 8-layer changes reduced to 3-layer changes (verified with test feature)
- [ ] 7.2.2 ✅ Zero manual cache loaders (auto-generated from schema)
- [ ] 7.2.3 ✅ Zero hardcoded registries (database-driven discovery)
- [ ] 7.2.4 ✅ Single CFG implementation (3 files → 1 file)
- [ ] 7.2.5 ✅ 62% code reduction (6,447 → 2,447 lines verified)
- [ ] 7.2.6 ✅ taint/database.py deleted (1,447 lines eliminated)
- [ ] 7.2.7 ✅ 100% test pass rate
- [ ] 7.2.8 ✅ Performance improvement (faster or equal)
- [ ] 7.2.9 ✅ Memory usage acceptable (<500MB)
- [ ] 7.2.10 ✅ Developer velocity improved (fewer layers to change)

### 7.3 Completion Report (teamsop.md Template C-4.20)

- [ ] 7.3.1 Write completion report in verification.md (append)
- [ ] 7.3.2 Document final verification findings
- [ ] 7.3.3 Document root cause confirmation
- [ ] 7.3.4 Document implementation summary (4 phases completed)
- [ ] 7.3.5 Document performance improvement metrics
- [ ] 7.3.6 Document developer experience improvement
- [ ] 7.3.7 Submit report to Architect (User) and Lead Auditor (Gemini)

---

## Summary Statistics

**Total Tasks**: 250+ discrete implementation steps
**Estimated Time**: 4 weeks (1 week per phase)
**Risk Level**: CRITICAL (massive refactor, 12 files deleted)
**Validation Gates**: 4 (one per phase)

**Task Breakdown**:
- Verification & Approval: 13 tasks
- Phase 1 (Schema Generation): 45 tasks
- Phase 2 (Replace Cache): 35 tasks
- Phase 3 (Database-Driven): 40 tasks
- Phase 4 (Delete & Unify): 70 tasks
- Final Integration: 25 tasks
- Commit & Audit: 25 tasks

**Critical Path**:
1. Approval → 2. Phase 1 (generation) → 3. Phase 2 (cache) → 4. Phase 3 (discovery) → 5. Phase 4 (delete) → 6. Commit

**Rollback Points**:
- After Phase 1: Revert schema generation (no impact)
- After Phase 2: Flip feature flag to old cache
- After Phase 3: Flip feature flag to hardcoded patterns
- After Phase 4: Revert entire commit

---

**Created By**: Claude Opus (Lead Coder)
**Date**: 2025-10-31
**Status**: AWAITING APPROVAL
