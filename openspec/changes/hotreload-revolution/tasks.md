# Implementation Tasks: Hot Reload Revolution

**Change ID**: `hotreload-revolution`
**Tracking**: 3-phase implementation with validation gates
**Estimated Time**: 1-2 weeks (foundation 2-3 days, watching 3-4 days, hardening 2-3 days)

---

## 0. Pre-Implementation Verification

- [ ] 0.1 Read `proposal.md` (understand Why/What/Impact)
- [ ] 0.2 Read `design.md` (understand technical decisions)
- [ ] 0.3 Read `ANALYSIS.md` (understand feasibility analysis)
- [ ] 0.4 Read `TEAMSOP.md` (understand Prime Directives and protocols)
- [ ] 0.5 Verify AST extractors are READ-ONLY (check git attributes)
- [ ] 0.6 Verify database schema is IMMUTABLE (no ALTER TABLE allowed)
- [ ] 0.7 Verify full rebuild works: `aud index` on medium project
- [ ] 0.8 Profile baseline performance: time `aud index` on 2,000-file project
- [ ] 0.9 Receive Architect approval
- [ ] 0.10 Create implementation branch: `git checkout -b hotreload-revolution`

**Gate**: DO NOT proceed to Phase 1 until approval received

---

## Phase 1: Hash-Based Incremental (Days 1-3)

**Objective**: `aud index --incremental` flag that skips unchanged files
**Risk Level**: LOW (opt-in, full rebuild still default)

### 1.1 File Change Detection Infrastructure

- [ ] 1.1.1 Create `theauditor/indexer/change_detector.py` (new file)
- [ ] 1.1.2 Add `ChangeSet` dataclass:
  ```python
  @dataclass
  class ChangeSet:
      new: List[str]          # New files
      modified: List[str]      # Modified files
      deleted: List[str]       # Deleted files
      unchanged: List[str]     # Unchanged files
  ```
- [ ] 1.1.3 Implement `FileChangeDetector` class
- [ ] 1.1.4 Implement `detect_changes()` method (compare manifests)
- [ ] 1.1.5 Implement `_load_manifest()` helper (load previous manifest)
- [ ] 1.1.6 Implement `_save_manifest_as_previous()` helper
- [ ] 1.1.7 Test: Create dummy manifests, verify detection works
- [ ] 1.1.8 Test: Edge case - no previous manifest (first run)
- [ ] 1.1.9 Test: Edge case - all files unchanged
- [ ] 1.1.10 Test: Edge case - all files changed

### 1.2 Database Deletion Infrastructure

- [ ] 1.2.1 Open `theauditor/indexer/database/base_database.py`
- [ ] 1.2.2 Add `delete_file_data(file_path: str)` method
- [ ] 1.2.3 Implement deletion for file-scoped tables (118 tables):
  - [ ] Core tables: symbols, refs, assignments, function_call_args, function_returns
  - [ ] JSX tables: symbols_jsx, assignments_jsx, function_call_args_jsx, function_returns_jsx
  - [ ] Variable usage: variable_usage
  - [ ] API endpoints: api_endpoints
  - [ ] SQL queries: sql_queries, orm_queries
  - [ ] React: react_components, react_hooks
  - [ ] Python: python_orm_models, python_routes, python_validators
  - [ ] Security: jwt_patterns, env_var_usage
  - [ ] CFG: cfg_blocks, cfg_edges, cfg_block_statements (special handling)
- [ ] 1.2.4 Implement junction table cascade (6 junction tables):
  - [ ] assignment_sources, assignment_sources_jsx
  - [ ] function_return_sources, function_return_sources_jsx
  - [ ] sql_query_tables
  - [ ] api_endpoint_controls
  - [ ] react_component_hooks
  - [ ] react_hook_dependencies
- [ ] 1.2.5 Implement `_delete_cfg_records(cursor, file_path)` helper:
  - [ ] Find all cfg_blocks IDs for file
  - [ ] Delete cfg_edges referencing these blocks
  - [ ] Delete cfg_block_statements
  - [ ] Delete cfg_blocks
- [ ] 1.2.6 Add transaction commit
- [ ] 1.2.7 Test: Delete data for single file, verify rows removed
- [ ] 1.2.8 Test: Verify no orphaned junction table rows
- [ ] 1.2.9 Test: Verify CFG edges still reference valid blocks

### 1.3 Incremental Indexing Logic

- [ ] 1.3.1 Create `theauditor/indexer/incremental.py` (new file)
- [ ] 1.3.2 Implement `run_incremental_index()` main function
- [ ] 1.3.3 Load previous manifest
- [ ] 1.3.4 Detect changed files using `FileChangeDetector`
- [ ] 1.3.5 Delete old data for changed/modified files
- [ ] 1.3.6 Delete data for deleted files
- [ ] 1.3.7 Re-extract changed files (call orchestrator per-file)
- [ ] 1.3.8 Rebuild JavaScript global cache from database (not batch parsing)
- [ ] 1.3.9 Re-run cross-file parameter resolution
- [ ] 1.3.10 Save current manifest as previous
- [ ] 1.3.11 Test: Change 5 files, verify only 5 files re-extracted
- [ ] 1.3.12 Test: Delete 2 files, verify data removed from database
- [ ] 1.3.13 Test: Add 3 new files, verify data inserted

### 1.4 JavaScript Global Cache Rebuild

- [ ] 1.4.1 Open `theauditor/indexer/extractors/javascript.py`
- [ ] 1.4.2 Add `rebuild_global_cache_from_database(db_path)` function
- [ ] 1.4.3 Query symbols table for all functions:
  ```sql
  SELECT name, metadata FROM symbols
  WHERE type = 'function' AND ext IN ('.js', '.ts', '.jsx', '.tsx')
  ```
- [ ] 1.4.4 Parse metadata JSON, extract params
- [ ] 1.4.5 Build `{function_name: [param1, param2, ...]}` dict
- [ ] 1.4.6 Return global cache
- [ ] 1.4.7 Update `orchestrator.py` to call this in incremental mode
- [ ] 1.4.8 Test: Verify global cache matches batch-parsing result
- [ ] 1.4.9 Test: Verify cross-file parameter resolution still works

### 1.5 Command Line Interface

- [ ] 1.5.1 Open `theauditor/commands/index.py`
- [ ] 1.5.2 Add `--incremental` flag:
  ```python
  @click.option('--incremental', is_flag=True, help='Incremental index (skip unchanged files)')
  ```
- [ ] 1.5.3 Add conditional logic:
  ```python
  if incremental:
      from theauditor.indexer.incremental import run_incremental_index
      run_incremental_index(root_path, db_path)
  else:
      # Existing full rebuild logic
  ```
- [ ] 1.5.4 Add `--full` flag (explicit full rebuild):
  ```python
  @click.option('--full', is_flag=True, help='Force full rebuild (default)')
  ```
- [ ] 1.5.5 Update help text to clarify default behavior
- [ ] 1.5.6 Test: `aud index --help` shows new flags
- [ ] 1.5.7 Test: `aud index` (default) runs full rebuild
- [ ] 1.5.8 Test: `aud index --full` runs full rebuild
- [ ] 1.5.9 Test: `aud index --incremental` runs incremental

### 1.6 Validation & Testing

- [ ] 1.6.1 Create `tests/test_incremental_indexing.py`
- [ ] 1.6.2 Test: Detect changed files (hash comparison)
- [ ] 1.6.3 Test: Delete file data (118 tables + junctions)
- [ ] 1.6.4 Test: Incremental index (5 changed files)
- [ ] 1.6.5 Test: Database content identical (full vs incremental):
  ```python
  full_db = run_full_index()
  incremental_db = run_incremental_index()
  assert databases_identical(full_db, incremental_db)
  ```
- [ ] 1.6.6 Test: Performance (should be 15-30x faster)
- [ ] 1.6.7 Test: Edge case - no previous manifest (first run)
- [ ] 1.6.8 Test: Edge case - all files unchanged (no-op)
- [ ] 1.6.9 Test: Edge case - deleted files removed from database
- [ ] 1.6.10 Test: CFG edges still valid after incremental update
- [ ] 1.6.11 Test: Junction tables have no orphaned rows

### 1.7 Phase 1 Validation Gate

- [ ] 1.7.1 All tests pass: `pytest tests/test_incremental_indexing.py -v`
- [ ] 1.7.2 Incremental result === Full rebuild result (byte-for-byte)
- [ ] 1.7.3 Performance 15-30x faster for 5 changed files
- [ ] 1.7.4 No orphaned junction table rows
- [ ] 1.7.5 CFG edges reference valid blocks
- [ ] 1.7.6 All existing tests pass: `pytest tests/ -v`
- [ ] 1.7.7 AST extractors unchanged: `git diff theauditor/ast_extractors/` (empty)
- [ ] 1.7.8 Database schema unchanged (all 151 tables identical)

**Gate**: DO NOT proceed to Phase 2 until all Phase 1 validation passes

---

## Phase 2: File Watching Service (Days 4-7)

**Objective**: `aud watch` command that auto-indexes on file changes
**Risk Level**: MEDIUM (background daemon, cross-platform)

### 2.1 Watchdog Dependency

- [ ] 2.1.1 Add watchdog to dependencies in `pyproject.toml`:
  ```toml
  watchdog = "^3.0.0"  # Cross-platform file system events
  ```
- [ ] 2.1.2 Install watchdog: `pip install watchdog`
- [ ] 2.1.3 Verify installation: `python -c "import watchdog; print(watchdog.__version__)"`
- [ ] 2.1.4 Test on Windows: Verify works with ReadDirectoryChangesW
- [ ] 2.1.5 Test on Linux (if available): Verify works with inotify
- [ ] 2.1.6 Test on macOS (if available): Verify works with FSEvents

### 2.2 File Watcher Infrastructure

- [ ] 2.2.1 Create `theauditor/indexer/file_watcher.py` (new file)
- [ ] 2.2.2 Import watchdog:
  ```python
  from watchdog.observers import Observer
  from watchdog.events import FileSystemEventHandler
  ```
- [ ] 2.2.3 Implement `IncrementalIndexHandler(FileSystemEventHandler)` class
- [ ] 2.2.4 Implement `on_modified(event)` method (handle file changes)
- [ ] 2.2.5 Implement `_is_source_file(file_path)` filter (only .py, .js, .ts, etc.)
- [ ] 2.2.6 Add change queue: `self.change_queue = Queue()`
- [ ] 2.2.7 Add debounce tracking: `self.last_change_time = None`
- [ ] 2.2.8 Test: Modify file, verify event received
- [ ] 2.2.9 Test: Modify non-source file, verify filtered out

### 2.3 Daemon Implementation

- [ ] 2.3.1 Implement `FileWatcherDaemon` class in `file_watcher.py`
- [ ] 2.3.2 Implement `start()` method:
  - [ ] Schedule observer to watch root directory recursively
  - [ ] Start observer thread
  - [ ] Start indexer thread (processes change queue)
- [ ] 2.3.3 Implement `stop()` method:
  - [ ] Stop observer
  - [ ] Wait for observer thread to join
  - [ ] Stop indexer thread
- [ ] 2.3.4 Implement `_process_changes()` method (indexer thread):
  - [ ] Sleep for debounce period (default 1 second)
  - [ ] Collect all changes from queue
  - [ ] Wait additional time if still receiving changes
  - [ ] Call `_incremental_index(changed_files)`
- [ ] 2.3.5 Implement `_incremental_index(changed_files)` method:
  - [ ] Call `run_incremental_index()` from incremental.py
  - [ ] Handle exceptions (log error, don't crash daemon)
- [ ] 2.3.6 Test: Start daemon, modify file, verify auto-indexed
- [ ] 2.3.7 Test: Modify multiple files rapidly, verify debounced (single index run)
- [ ] 2.3.8 Test: Stop daemon, verify graceful shutdown

### 2.4 Watch Command

- [ ] 2.4.1 Create `theauditor/commands/watch.py` (new file)
- [ ] 2.4.2 Import Click and FileWatcherDaemon
- [ ] 2.4.3 Implement `watch()` command:
  ```python
  @click.command()
  @click.option('--debounce', default=1.0, help='Seconds to wait before indexing')
  def watch(debounce):
      """Watch for file changes and automatically index incrementally."""
  ```
- [ ] 2.4.4 Create daemon instance
- [ ] 2.4.5 Start daemon
- [ ] 2.4.6 Print status message: "Watching for changes (Ctrl+C to stop)..."
- [ ] 2.4.7 Infinite loop with KeyboardInterrupt handler
- [ ] 2.4.8 Stop daemon on Ctrl+C
- [ ] 2.4.9 Register command in `theauditor/cli.py`:
  ```python
  from theauditor.commands import watch
  cli.add_command(watch.watch)
  ```
- [ ] 2.4.10 Test: `aud watch --help` shows help
- [ ] 2.4.11 Test: `aud watch` starts daemon, watches for changes
- [ ] 2.4.12 Test: Ctrl+C stops daemon gracefully

### 2.5 Cross-File Dependency Tracking

- [ ] 2.5.1 Implement `find_dependent_files(db_path, changed_file)` in `incremental.py`
- [ ] 2.5.2 Query refs table for reverse dependencies:
  ```sql
  SELECT DISTINCT src FROM refs
  WHERE value = ? OR value LIKE ?
  ```
- [ ] 2.5.3 Return list of dependent files
- [ ] 2.5.4 Update `run_incremental_index()` to re-index dependents:
  ```python
  affected_files = changed_files + find_dependent_files(db_path, changed_file)
  ```
- [ ] 2.5.5 Test: Change file B, verify file A (imports B) re-indexed
- [ ] 2.5.6 Test: Change file with no dependents, verify only that file indexed

### 2.6 Lock File Mechanism (Prevent Concurrent Indexing)

- [ ] 2.6.1 Add `acquire_index_lock(db_path)` function in `incremental.py`
- [ ] 2.6.2 Create lock file: `.pf/.index.lock` with PID
- [ ] 2.6.3 Check if lock file exists:
  - [ ] If exists: Read PID, check if process still running
  - [ ] If process running: Raise exception (index already running)
  - [ ] If process dead: Remove stale lock, acquire new lock
- [ ] 2.6.4 Add `release_index_lock(db_path)` function
- [ ] 2.6.5 Remove lock file on completion
- [ ] 2.6.6 Add try/finally to ensure lock always released
- [ ] 2.6.7 Test: Run two index commands simultaneously, verify second fails
- [ ] 2.6.8 Test: Lock released after successful index
- [ ] 2.6.9 Test: Lock released after failed index (exception)
- [ ] 2.6.10 Test: Stale lock removed if process dead

### 2.7 Phase 2 Validation Gate

- [ ] 2.7.1 Daemon runs for 1+ hour without crashes
- [ ] 2.7.2 File changes detected within 1-2 seconds
- [ ] 2.7.3 Debouncing works (rapid changes = single index run)
- [ ] 2.7.4 Dependency tracking works (file A updated when file B changes)
- [ ] 2.7.5 Lock file prevents concurrent indexing
- [ ] 2.7.6 All tests pass: `pytest tests/ -v`
- [ ] 2.7.7 Watchdog works on Windows
- [ ] 2.7.8 AST extractors unchanged

**Gate**: DO NOT proceed to Phase 3 until all Phase 2 validation passes

---

## Phase 3: Production Hardening (Days 8-10)

**Objective**: Safety mechanisms and AI integration
**Risk Level**: LOW (polish and validation)

### 3.1 Periodic Full Rebuild

- [ ] 3.1.1 Create `.pf/incremental_metadata.json` file structure:
  ```json
  {
    "incremental_count": 0,
    "last_full_rebuild": "2025-11-02T12:00:00"
  }
  ```
- [ ] 3.1.2 Implement `should_force_full_rebuild()` in `incremental.py`
- [ ] 3.1.3 Check incremental count (threshold: 50)
- [ ] 3.1.4 Check time since last full rebuild (threshold: 24 hours)
- [ ] 3.1.5 Return True if either threshold exceeded
- [ ] 3.1.6 Implement `record_incremental_update()`
- [ ] 3.1.7 Increment incremental_count in metadata
- [ ] 3.1.8 Implement `record_full_rebuild()`
- [ ] 3.1.9 Reset incremental_count to 0, update last_full_rebuild timestamp
- [ ] 3.1.10 Update `run_incremental_index()` to call these functions
- [ ] 3.1.11 Test: After 50 incremental updates, full rebuild triggered
- [ ] 3.1.12 Test: After 24 hours, full rebuild triggered
- [ ] 3.1.13 Test: Metadata persisted across runs

### 3.2 Validation Checks

- [ ] 3.2.1 Implement `validate_incremental_consistency(db_path)` in `incremental.py`
- [ ] 3.2.2 Check: No orphaned junction table rows
  ```sql
  SELECT COUNT(*) FROM assignment_sources
  WHERE assignment_file NOT IN (SELECT file FROM assignments)
  ```
- [ ] 3.2.3 Check: All file FKs point to existing files
  ```sql
  SELECT COUNT(*) FROM symbols
  WHERE path NOT IN (SELECT path FROM files)
  ```
- [ ] 3.2.4 Check: SHA256 hashes in database match manifest
- [ ] 3.2.5 Check: CFG edges reference valid blocks
  ```sql
  SELECT COUNT(*) FROM cfg_edges
  WHERE source_block_id NOT IN (SELECT id FROM cfg_blocks)
  ```
- [ ] 3.2.6 If any check fails: Log warning, force full rebuild
- [ ] 3.2.7 Run validation after every incremental update
- [ ] 3.2.8 Test: Insert orphaned row, verify validation catches it
- [ ] 3.2.9 Test: Corrupt SHA256, verify validation catches it

### 3.3 AI Integration (Claude Code Hooks)

- [ ] 3.3.1 Create `.claude/hooks/post-edit.sh` template:
  ```bash
  #!/bin/bash
  # Triggered after Claude edits a file
  aud index --incremental --files "$CHANGED_FILES"
  ```
- [ ] 3.3.2 Document setup in README or docs
- [ ] 3.3.3 Test: Manually trigger hook, verify incremental index runs
- [ ] 3.3.4 Test: Edit file via Claude Code, verify hook triggers
- [ ] 3.3.5 Document alternative: `aud watch` daemon (preferred)

### 3.4 Documentation

- [ ] 3.4.1 Update `CLAUDE.md`:
  - [ ] Add section on incremental indexing
  - [ ] Add section on file watching daemon
  - [ ] Add performance comparison (full vs incremental)
- [ ] 3.4.2 Update `README.md` (if applicable):
  - [ ] Add `aud index --incremental` to commands list
  - [ ] Add `aud watch` to commands list
  - [ ] Add usage examples
- [ ] 3.4.3 Create `docs/incremental-indexing.md` (detailed guide):
  - [ ] How incremental indexing works
  - [ ] When to use `--incremental` vs `--full`
  - [ ] How to set up file watching daemon
  - [ ] Troubleshooting guide
- [ ] 3.4.4 Add docstrings to all new functions
- [ ] 3.4.5 Update type hints (if using mypy)

### 3.5 Final Testing

- [ ] 3.5.1 Test on small project (500 files): Full vs Incremental
- [ ] 3.5.2 Test on medium project (2,000 files): Full vs Incremental
- [ ] 3.5.3 Test on large project (10,000 files): Full vs Incremental
- [ ] 3.5.4 Test: Change 1 file, verify only 1 file re-indexed
- [ ] 3.5.5 Test: Change 10 files, verify only 10 files re-indexed
- [ ] 3.5.6 Test: Change 100 files, verify only 100 files re-indexed
- [ ] 3.5.7 Test: Delete 5 files, verify data removed from database
- [ ] 3.5.8 Test: Add 5 new files, verify data inserted
- [ ] 3.5.9 Test: Rename file (shows as delete + add), verify handled correctly
- [ ] 3.5.10 Test: `aud watch` runs 24+ hours without issues
- [ ] 3.5.11 Profile memory usage (daemon mode): Should be <100MB overhead
- [ ] 3.5.12 Profile CPU usage (daemon idle): Should be <1%

### 3.6 Phase 3 Validation Gate

- [ ] 3.6.1 Periodic full rebuild works (every 50 updates or 24 hours)
- [ ] 3.6.2 Validation catches inconsistencies
- [ ] 3.6.3 Lock file prevents concurrent indexing
- [ ] 3.6.4 Documentation complete and accurate
- [ ] 3.6.5 All tests pass (100% existing + new incremental tests)
- [ ] 3.6.6 Performance improvement verified (15-30x faster)
- [ ] 3.6.7 Memory usage acceptable (<100MB daemon overhead)
- [ ] 3.6.8 AST extractors unchanged

**Gate**: DO NOT commit until all Phase 3 validation passes

---

## 4. Final Integration & Commit

### 4.1 Code Quality

- [ ] 4.1.1 Run linter: `ruff check theauditor/indexer/ theauditor/commands/`
- [ ] 4.1.2 Run formatter: `ruff format theauditor/indexer/ theauditor/commands/`
- [ ] 4.1.3 Fix any linting/formatting issues
- [ ] 4.1.4 Run type checker (if using mypy): `mypy theauditor/indexer/ --strict`
- [ ] 4.1.5 Fix any type errors

### 4.2 Test Coverage

- [ ] 4.2.1 Run full test suite: `pytest tests/ -v`
- [ ] 4.2.2 Run with coverage: `pytest tests/ --cov=theauditor --cov-report=html`
- [ ] 4.2.3 Verify incremental code has >80% coverage
- [ ] 4.2.4 Add tests for uncovered edge cases

### 4.3 Performance Benchmarking

- [ ] 4.3.1 Benchmark full rebuild on 5 projects (small, medium, large)
- [ ] 4.3.2 Benchmark incremental (5 changed files) on same 5 projects
- [ ] 4.3.3 Calculate speedup ratios
- [ ] 4.3.4 Document results in verification or completion report
- [ ] 4.3.5 Verify 15-30x speedup achieved

### 4.4 Git Preparation

- [ ] 4.4.1 Review changes: `git status`
- [ ] 4.4.2 Verify files modified/added:
  - M  theauditor/commands/index.py
  - A  theauditor/commands/watch.py
  - M  theauditor/indexer/orchestrator.py
  - A  theauditor/indexer/incremental.py
  - A  theauditor/indexer/change_detector.py
  - A  theauditor/indexer/file_watcher.py
  - M  theauditor/indexer/database/base_database.py
  - M  theauditor/indexer/extractors/javascript.py
  - A  tests/test_incremental_indexing.py
  - M  CLAUDE.md (documentation updates)
- [ ] 4.4.3 Verify AST extractors UNCHANGED: `git diff theauditor/ast_extractors/`
- [ ] 4.4.4 Verify no schema changes: `git diff theauditor/indexer/schema.py`
- [ ] 4.4.5 Review diff: `git diff`
- [ ] 4.4.6 Stage files: `git add theauditor/ tests/`

### 4.5 Commit Message

- [ ] 4.5.1 Write comprehensive commit message:
  ```
  feat(indexer): add incremental indexing and file watching

  Implements hotreload-revolution OpenSpec change:
  - Add `aud index --incremental` flag (15-30x faster for small changesets)
  - Add `aud watch` daemon (auto-index on file changes)
  - Hash-based change detection via manifest comparison
  - Selective table deletion (only changed files)
  - JavaScript global cache rebuild from database
  - Cross-file dependency tracking
  - Periodic full rebuild safety valve
  - Validation checks for database consistency

  Performance:
  - Small project (500 files): 10-15x faster
  - Medium project (2,000 files): 15-30x faster
  - Large project (10,000 files): 30-40x faster

  Testing:
  - 100% existing tests pass
  - New incremental tests added (400+ lines)
  - Tested on Windows/Linux/macOS

  BREAKING CHANGES: None (incremental is opt-in, full rebuild remains default)

  OpenSpec: openspec/changes/hotreload-revolution
  ```
- [ ] 4.5.2 Create commit: `git commit`
- [ ] 4.5.3 Verify commit created successfully
- [ ] 4.5.4 Tag commit: `git tag hotreload-revolution-v1.0`

### 4.6 Post-Commit Validation

- [ ] 4.6.1 Fresh clone test: Clone repo in new directory
- [ ] 4.6.2 Install dependencies: `pip install -e ".[dev]"`
- [ ] 4.6.3 Run full test suite: `pytest tests/ -v`
- [ ] 4.6.4 Test `aud index` (default full rebuild)
- [ ] 4.6.5 Test `aud index --incremental`
- [ ] 4.6.6 Test `aud watch`
- [ ] 4.6.7 Smoke test on production project

---

## 5. OpenSpec Archiving (After Deployment)

- [ ] 5.1 Verify change is deployed and working
- [ ] 5.2 Move to archive:
  ```bash
  openspec archive hotreload-revolution --yes
  ```
- [ ] 5.3 Verify archive created: `openspec/changes/archive/2025-11-02-hotreload-revolution/`
- [ ] 5.4 Update specs (if any capability specs affected)
- [ ] 5.5 Run validation: `openspec validate --strict`

---

## Summary Statistics

**Total Tasks**: 200+ discrete implementation steps
**Estimated Time**: 1-2 weeks
  - Phase 1 (Hash-Based Incremental): 2-3 days
  - Phase 2 (File Watching): 3-4 days
  - Phase 3 (Hardening): 2-3 days
**Risk Level**: MEDIUM (opt-in feature, full rebuild safety valve)
**Validation Gates**: 3 (one per phase)

**Critical Path**:
1. Phase 1 (incremental logic) → 2. Phase 2 (file watching) → 3. Phase 3 (hardening) → 4. Commit

**Rollback Points**:
- After Phase 1: Disable `--incremental` flag
- After Phase 2: Don't run `aud watch` daemon
- After Phase 3: Revert commit

---

**Created By**: Claude Sonnet 4.5 (Lead Architect)
**Date**: 2025-11-02
**Status**: READY FOR EXECUTION
