# 🚀 Incremental Indexing System - Comprehensive Feasibility Analysis

**VERBATIM ANALYSIS FROM EXPLORATION** - This document contains the complete feasibility analysis exactly as delivered. Use this as the authoritative reference for scope, complexity, and implementation strategy.

---

## Executive Summary

**TL;DR**: Highly feasible, medium complexity, significant impact. You already have 70% of the infrastructure built - workset system, SHA256 tracking, AST cache, and git integration. The missing pieces are: file watching, incremental database updates, and dependency invalidation logic.

**Estimated effort**: 3-5 days for basic implementation, 1-2 weeks for production-ready with all edge cases handled.

**ROI**: For typical dev loops (5-10 file changes), this would reduce `aud index` time from 15-30 seconds to 1-2 seconds (15-30x speedup).

---

## 📊 Scope Assessment

### What Already Exists (70% Foundation)

1. **Workset System** (`theauditor/workset.py`)
   - Git diff integration via subprocess
   - SHA256 file hashing
   - Dependency graph traversal (forward/reverse imports)
   - Manifest.json file inventory
   - 12 commands support `--workset` flag

2. **AST Cache** (`theauditor/cache/ast_cache.py`)
   - SHA256-keyed persistent cache
   - LRU eviction (1GB/20K files)
   - Hit rate tracking (70% speedup on re-index)

3. **Database Schema** (151 tables)
   - 118 file-scoped tables (incrementally updatable)
   - Files table tracks SHA256 (not currently used for change detection)
   - No CASCADE DELETE (manual cleanup required)

4. **Extractor Architecture**
   - Already per-file isolated (no cross-file dependencies during extraction)
   - File-local: symbols, calls, assignments, routes, SQL, ORM, validation
   - Cross-file: JavaScript parameter resolution, import graph

### What Needs Building (30% New Work)

1. **File Watching Service** (NEW)
   - Detect file changes in real-time (watchdog library)
   - Queue changed files for incremental update
   - Debouncing logic (don't index on every keystroke)

2. **Incremental Database Update** (NEW)
   - `delete_file_records(file_path)` - Remove old data for changed file
   - Selective table deletion (118 file-scoped tables)
   - Junction table cascade (6 normalized junction tables)
   - CFG ID remapping (AUTOINCREMENT handling)

3. **Dependency Invalidation** (REFACTOR)
   - Track "which files import file X" to re-resolve imports
   - Rebuild JavaScript global function cache from database (not batch parsing)
   - Re-run cross-file parameter resolution after incremental update

4. **Change Detection Service** (NEW)
   - Compare current SHA256 with previous manifest
   - Detect new/deleted/modified files
   - Track timestamp of last index for staleness checks

5. **Automatic Index Trigger** (NEW)
   - Hook into file save events (VS Code extension, CLI daemon, or git hooks)
   - Integration with AI workflow (auto-index after each edit)
   - Background indexing (non-blocking)

---

## 🧩 Complexity Analysis

### Easy Components (1-2 days)

**File Change Detection**
```python
# Already have manifest.json with SHA256 hashes
def detect_changed_files(current_manifest, previous_manifest):
    changed = []
    for file in current_manifest:
        old_hash = previous_manifest.get(file['path'], {}).get('sha256')
        new_hash = file['sha256']
        if old_hash != new_hash:
            changed.append(file['path'])
    return changed
```

**Simple Table Deletion**
```python
# Already have table schema with file column metadata
def delete_file_records(db_path, file_path):
    conn = sqlite3.connect(db_path)
    file_scoped_tables = [t for t in TABLES if 'file' in t.columns]
    for table in file_scoped_tables:
        conn.execute(f"DELETE FROM {table} WHERE file = ?", (file_path,))
    conn.commit()
```

**AST Cache Integration**
```python
# Already have SHA256-based cache, just need to leverage it
if old_hash == new_hash:
    skip_extraction()  # Keep existing database rows
else:
    ast = ast_cache.get(new_hash)  # May hit cache even if file "changed"
    extract_and_insert(ast)
```

### Medium Components (2-3 days)

**Junction Table Cascade**
```python
# 6 normalized junction tables need manual deletion
JUNCTION_TABLES = {
    'assignments': ['assignment_sources', 'assignment_sources_jsx'],
    'function_returns': ['function_return_sources', 'function_return_sources_jsx'],
    'sql_queries': ['sql_query_tables'],
    'api_endpoints': ['api_endpoint_controls'],
    'react_components': ['react_component_hooks'],
    'react_hooks': ['react_hook_dependencies'],
}

def delete_with_cascade(db_path, file_path):
    for parent_table, junction_tables in JUNCTION_TABLES.items():
        for junction_table in junction_tables:
            conn.execute(f"DELETE FROM {junction_table} WHERE {parent}_file = ?", (file_path,))
        conn.execute(f"DELETE FROM {parent_table} WHERE file = ?", (file_path,))
```

**File Watching Service**
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class IncrementalIndexHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory or not self._is_source_file(event.src_path):
            return
        self.change_queue.put(event.src_path)  # Debounced processing
```

**Workset Integration**
```python
# Reuse existing dependency expansion logic
def compute_incremental_workset(changed_files, db_path):
    conn = sqlite3.connect(db_path)
    # Use existing get_forward_deps() and get_reverse_deps()
    affected_files = expand_dependencies(conn, changed_files, max_depth=2)
    return affected_files
```

### Hard Components (3-5 days)

**CFG ID Remapping**
```python
# Problem: cfg_blocks uses AUTOINCREMENT PRIMARY KEY
# Deleting + reinserting changes IDs, breaks cfg_edges foreign keys

def update_cfg_incrementally(db_path, file_path):
    # 1. Find all old block IDs for file
    old_ids = query("SELECT id FROM cfg_blocks WHERE file = ?", file_path)

    # 2. Delete edges referencing old blocks
    delete_cfg_edges(old_ids)

    # 3. Delete old blocks
    delete("DELETE FROM cfg_blocks WHERE file = ?", file_path)

    # 4. Insert new blocks (get new IDs from database)
    new_blocks = extract_cfg_blocks(file_path)
    new_ids = insert_cfg_blocks(new_blocks)  # Returns AUTOINCREMENT IDs

    # 5. Insert new edges with remapped IDs
    insert_cfg_edges(new_edges, id_mapping={old: new})
```

**JavaScript Global Function Cache Rebuild**
```python
# Current: Built from batch-parsing ALL JS/TS files
# Need: Rebuild from database instead

# BEFORE (orchestrator.py:258-288)
js_ts_files = [all JS/TS files]
batch_trees = ast_parser.parse_files_batch(js_ts_files)
global_function_params = extract_params_from_asts(batch_trees)

# AFTER (incremental mode)
def rebuild_function_cache_from_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, params FROM symbols WHERE type = 'function'")
    return {name: json.loads(params) for name, params in cursor.fetchall()}
```

**Cross-File Dependency Tracking**
```python
# Problem: If file A imports file B, changing B should re-index A
# Need: Track reverse dependencies and invalidate dependent files

def find_dependent_files(db_path, changed_file):
    conn = sqlite3.connect(db_path)
    # Query refs table for files that import changed_file
    cursor = conn.execute("""
        SELECT DISTINCT src
        FROM refs
        WHERE value = ? OR value LIKE ?
    """, (changed_file, f"%{changed_file}%"))
    return [row[0] for row in cursor.fetchall()]
```

### Very Hard Components (5-7 days)

**Background Daemon Mode**
```python
# Run indexer as background service that watches for changes
# Challenges:
# - Process lifecycle management (start/stop/restart)
# - Resource limits (CPU/memory throttling)
# - Race conditions (file modified during indexing)
# - Error recovery (crashes, corrupted database)

class IncrementalIndexDaemon:
    def __init__(self, root_path, db_path):
        self.observer = Observer()
        self.handler = IncrementalIndexHandler(db_path)
        self.queue = Queue()  # Thread-safe change queue
        self.indexer_thread = Thread(target=self._process_changes)

    def start(self):
        self.observer.schedule(self.handler, self.root_path, recursive=True)
        self.observer.start()
        self.indexer_thread.start()

    def _process_changes(self):
        while True:
            changed_files = self.queue.get(timeout=1.0)  # Debounce
            self._incremental_index(changed_files)
```

**Conflict Resolution**
```python
# Problem: User manually runs `aud index` while daemon is running
# Need: Locking mechanism to prevent concurrent writes

def acquire_index_lock(db_path):
    lock_file = Path(db_path).parent / ".index.lock"
    if lock_file.exists():
        raise Exception("Index already running")
    lock_file.write_text(str(os.getpid()))
```

---

## 🎯 Difficulty Assessment

### Skill Level Required
- **Python**: Advanced (threading, file I/O, subprocess)
- **SQLite**: Intermediate (foreign keys, transactions, ID remapping)
- **Git**: Basic (diff parsing, subprocess integration)
- **Architecture**: Advanced (event-driven systems, caching, dependency graphs)

### Key Challenges

1. **Database Consistency** (CRITICAL)
   - TheAuditor philosophy: "Database is regenerated FRESH every run. It MUST exist and MUST be correct."
   - Incremental updates introduce risk of "database got into bad state N runs ago"
   - Need robust validation: periodic full rebuild to detect drift

2. **Cross-File Dependencies** (HARD)
   - JavaScript parameter resolution depends on ALL files' function definitions
   - Import graph traversal needs to be transitive (A imports B imports C)
   - Changing B may affect A and all files importing A

3. **Junction Table Cascade** (MEDIUM)
   - 6 normalized junction tables need manual deletion (no CASCADE DELETE)
   - Easy to forget one and leave orphaned rows
   - Schema changes (new junction tables) need incremental logic updates

4. **CFG AUTOINCREMENT IDs** (HARD)
   - Deleting + reinserting CFG blocks changes IDs
   - Edges reference blocks by ID (foreign keys)
   - Need ID remapping logic or switch to content-based keys

5. **Race Conditions** (HARD)
   - File modified while being indexed
   - Multiple file changes in rapid succession (debouncing required)
   - User runs `aud index` manually while daemon running

### Gotchas

**Gotcha 1: AST Cache False Positives**
- File renamed → SHA256 same → cache hit → wrong file path in database
- Solution: Include file path in cache key, or validate path on cache hit

**Gotcha 2: Deleted Files**
- File deleted → no longer on disk → how to detect and remove from database?
- Solution: Compare current file list vs database file list, delete missing

**Gotcha 3: Framework Detection**
- Currently scans for package.json, requirements.txt on every index
- With incremental, framework detection may be stale
- Solution: Hash package.json and re-detect only if changed

**Gotcha 4: View Staleness**
- `symbols_unified` and `function_returns_unified` views are UNION ALL
- Incremental updates may create inconsistent view results
- Solution: Views are auto-updated (no materialization), but cached queries stale

**Gotcha 5: Graph Database**
- `graphs.db` built FROM `repo_index.db` via full traversal
- Cannot incrementally update graph database
- Solution: Mark graphs.db as stale, require `aud graph build` to rebuild

---

## 🏗️ Recommended Architecture

### Phase 1: Hash-Based Incremental (No File Watching)

**Goal**: `aud index --incremental` flag that skips unchanged files

**Implementation**:
```python
# 1. Save previous manifest as .pf/manifest.previous.json
# 2. On index:
def index_incremental(root_path, db_path):
    current_manifest = generate_manifest(root_path)
    previous_manifest = load_manifest_previous()

    changed_files = detect_changed_files(current_manifest, previous_manifest)
    deleted_files = detect_deleted_files(current_manifest, previous_manifest)

    # Delete old data
    for file in changed_files + deleted_files:
        delete_file_records(db_path, file)

    # Re-extract changed files
    for file in changed_files:
        extract_and_insert(db_path, file)

    # Rebuild cross-file links (JavaScript only)
    JavaScriptExtractor.resolve_cross_file_parameters(db_path)

    # Save new manifest as previous
    save_manifest_previous(current_manifest)
```

**Pros**:
- Simple, low risk
- No daemon, no file watching complexity
- 15-30x speedup for small changesets

**Cons**:
- User must manually run `aud index --incremental`
- No real-time updates during AI dev loop

### Phase 2: File Watching Service

**Goal**: `aud watch` command that auto-indexes on file changes

**Implementation**:
```python
# theauditor/commands/watch.py
@click.command()
@click.option('--debounce', default=1.0, help='Seconds to wait before indexing')
def watch(debounce):
    """Watch for file changes and automatically index incrementally."""
    daemon = IncrementalIndexDaemon(root_path=".", debounce=debounce)
    daemon.start()
    click.echo("Watching for changes (Ctrl+C to stop)...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        daemon.stop()
```

**Pros**:
- Real-time updates (1-2 second lag after save)
- Perfect for AI dev loop (fix issues → auto-indexed → ready for next analysis)

**Cons**:
- Requires watchdog library (new dependency)
- Background process management (start/stop/restart)
- Resource usage (CPU/memory for file watching)

### Phase 3: AI Integration (Ultimate Goal)

**Goal**: Seamless integration with Claude Code workflow

**Workflow**:
```
1. Claude: "I found 10 security issues. Let me fix them."
2. Claude: <edits 10 files via Edit tool>
3. Claude: <waits 2 seconds for auto-index to complete>
4. Claude: "Fixes applied. Running analysis to verify..."
5. Claude: <runs `aud taint --workset` on fixed files>
6. Claude: "All issues resolved!"
```

**Implementation Options**:

**Option A: Hook System (Minimal)**
```python
# .claude/hooks/post-edit.sh
#!/bin/bash
# Triggered after Claude edits a file
aud index --incremental --files "$CHANGED_FILES"
```

**Option B: Daemon Mode (Optimal)**
```bash
# User runs once at start of session
aud watch &

# Claude edits files
# Daemon auto-indexes in background (1-2 sec lag)
# Claude runs analysis immediately (database up-to-date)
```

**Option C: Embedded Mode (Future)**
```python
# Claude Code extension integrates directly
# No separate daemon process needed
# Index runs in same Python process as Claude
```

---

## 📈 Performance Impact

### Current State (Full Rebuild)

**Medium Codebase** (2,000 files, 500K LOC):
- Parse all files: 10-15 seconds (70% AST cache hit)
- Extract data: 5-8 seconds
- Store to database: 2-3 seconds
- **Total: 15-30 seconds**

### With Incremental Updates (5 files changed)

**Changed Files Only**:
- Parse 5 files: 0.1 seconds (cache miss)
- Extract 5 files: 0.3 seconds
- Delete + insert database: 0.2 seconds
- Cross-file resolution: 0.5 seconds (query database, not re-parse)
- **Total: 1-2 seconds (15-30x speedup)**

**Dependency Expansion** (5 changed → 20 affected):
- Parse 20 files: 0.5 seconds
- Extract 20 files: 1.0 seconds
- Database operations: 0.5 seconds
- Cross-file resolution: 0.5 seconds
- **Total: 2.5-3 seconds (6-10x speedup)**

### File Watching Overhead

**Daemon Mode**:
- Watchdog library: ~10-20 MB memory
- File system events: negligible CPU (<1%)
- Indexing triggered on save: 1-2 seconds (same as manual incremental)

**Total Cost**: ~20 MB RAM, <1% CPU idle, 1-2 seconds on file save

---

## ⚖️ Trade-offs

### Pros

1. **Massive Speedup** - 15-30x faster for small changesets
2. **Perfect for AI Loop** - Claude fixes issues → auto-indexed → ready for analysis
3. **Developer Experience** - No manual `aud index` every 30 seconds
4. **Existing Infrastructure** - 70% already built (workset, AST cache, git diff)
5. **Low Risk** - Can implement as opt-in `--incremental` flag first

### Cons

1. **Complexity** - 30% new code (file watching, incremental update, dependency invalidation)
2. **Consistency Risk** - Incremental bugs may compound over multiple runs
3. **Validation Required** - Need periodic full rebuilds to detect drift
4. **New Dependency** - Watchdog library (adds ~500 KB to install size)
5. **Platform Specific** - File watching APIs differ (Linux inotify, macOS FSEvents, Windows ReadDirectoryChangesW)

### Risk Mitigation

**Safety Valve 1: Force Full Rebuild**
```bash
# Always available as escape hatch
aud index --full  # Ignores incremental, regenerates everything
```

**Safety Valve 2: Periodic Full Rebuild**
```python
# Auto-trigger full rebuild every N incremental updates
if incremental_count > 50 or last_full_rebuild > 24_hours:
    run_full_rebuild()
```

**Safety Valve 3: Validation**
```python
# After incremental update, run consistency checks
def validate_incremental_consistency(db_path):
    # Check: No orphaned junction table rows
    # Check: All file FKs point to existing files
    # Check: SHA256 hashes match manifest
    # If validation fails: Force full rebuild
```

---

## 🚦 Implementation Plan

### Week 1: Foundation (2-3 days)

**Day 1-2: Hash-Based Incremental**
- [ ] Add `--incremental` flag to `aud index` command
- [ ] Implement `detect_changed_files()` (compare manifests)
- [ ] Implement `delete_file_records()` (118 file-scoped tables)
- [ ] Save previous manifest as `.pf/manifest.previous.json`
- [ ] Test: Change 5 files, verify database updated correctly

**Day 3: Junction Table Cascade**
- [ ] Identify 6 junction tables (assignment_sources, function_return_sources, etc.)
- [ ] Implement `delete_with_cascade()` (manual deletion)
- [ ] Test: Verify no orphaned rows after incremental update

### Week 2: File Watching (3-4 days)

**Day 4-5: Watchdog Integration**
- [ ] Add watchdog to dependencies (`pip install watchdog`)
- [ ] Create `IncrementalIndexHandler` (file system event handler)
- [ ] Implement debouncing (wait 1 second after last change before indexing)
- [ ] Add `aud watch` command

**Day 6: Cross-File Dependencies**
- [ ] Refactor JavaScript global function cache to rebuild from database
- [ ] Implement `find_dependent_files()` (reverse import lookup)
- [ ] Test: Change file B, verify file A (imports B) re-indexed

**Day 7: CFG ID Remapping**
- [ ] Implement `update_cfg_incrementally()` (delete + reinsert with ID mapping)
- [ ] Test: Verify cfg_edges still valid after incremental update

### Week 3: Production Hardening (optional, 2-3 days)

**Day 8: Validation & Safety**
- [ ] Implement `validate_incremental_consistency()` checks
- [ ] Add auto-trigger for full rebuild (every 50 incremental updates)
- [ ] Add lock file mechanism (prevent concurrent index runs)

**Day 9-10: AI Integration**
- [ ] Create post-edit hook for Claude Code
- [ ] Test with real AI workflow (fix 10 files → auto-index → re-analyze)
- [ ] Document setup instructions for users

---

## 🎯 Final Recommendation

**Should you build this?** **STRONG YES**

**Why:**
1. **High Impact** - Transforms TheAuditor from batch tool to interactive dev tool
2. **Medium Complexity** - You already have 70% of infrastructure built
3. **Low Risk** - Can implement as opt-in `--incremental` flag with full rebuild safety valve
4. **Perfect for AI** - Enables seamless Claude Code integration (fix → auto-index → verify loop)
5. **User Demand** - Every developer wants faster feedback loops

**Start Small:**
1. Phase 1: `aud index --incremental` (hash-based, no file watching) - **2-3 days**
2. Test thoroughly with real workloads
3. Phase 2: `aud watch` (file watching daemon) - **3-4 days** if Phase 1 successful
4. Phase 3: Claude Code integration - **2-3 days** for polish

**Total Time: 1-2 weeks** for production-ready incremental indexing with AI integration.

**ROI: 15-30x speedup** for typical dev loops where 5-10 files change. Worth every minute of dev time.
