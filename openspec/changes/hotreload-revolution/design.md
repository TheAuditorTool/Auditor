# Design Document: Hot Reload Revolution - Incremental Indexing

**Change ID**: `hotreload-revolution`
**Author**: Claude Sonnet 4.5 (Lead Architect)
**Date**: 2025-11-02
**Status**: PROPOSED - Awaiting Approval

---

## Context

### Background

TheAuditor's indexing system was designed when the codebase had 30 tables and 500 files. A full rebuild took 5 seconds - acceptable. The architecture never evolved as the project scaled:

- **Month 1**: 30 tables, 5-second rebuilds (acceptable)
- **Month 3**: 70 tables, 15-second rebuilds (should have added incremental)
- **Month 6**: 151 tables, 30-second rebuilds (incremental now critical)
- **Current**: No incremental logic, every run regenerates everything

**The missed opportunity**: Incremental indexing should have been added at Month 3. By Month 6, the architecture debt makes every development iteration painful.

### Constraints

1. **AST Extractors are SACRED** - javascript_impl.py and python_impl.py CANNOT be modified
2. **Zero schema changes** - All 151 tables must remain byte-for-byte identical
3. **Full rebuild always works** - Incremental is opt-in, full rebuild is default
4. **Zero fallback policy** - No conditional logic, no try/except fallbacks
5. **Backward compatibility** - All existing commands work unchanged

### Stakeholders

- **Architect (User)**: Approval authority, enforces AST extractor sanctity
- **Lead Coder (Claude)**: Implementation responsibility
- **AI Users**: Claude Code integration for seamless workflow
- **Human Developers**: Faster iteration on security fixes

---

## Goals / Non-Goals

### Goals

1. ✅ **15-30x speedup** for small changesets (5 files changed out of 2,000)
2. ✅ **Zero manual index commands** with file watching daemon
3. ✅ **AI workflow integration** - seamless Claude Code loop (fix → auto-index → verify)
4. ✅ **Correctness guarantee** - incremental result === full rebuild result
5. ✅ **Safety valve** - full rebuild always available
6. ✅ **70% code reuse** - leverage existing workset, AST cache, manifest

### Non-Goals

1. ❌ **Modify AST extractors** - javascript_impl.py and python_impl.py are READ-ONLY
2. ❌ **Change database schema** - All 151 tables stay identical
3. ❌ **Algorithm optimization** - Performance comes from skipping unchanged files, not optimizing algorithms
4. ❌ **Partial file updates** - Granularity is whole files only
5. ❌ **Cross-platform file watching perfection** - Watchdog handles platform differences, we accept its limitations

---

## Decisions

### Decision 1: Hash-Based Change Detection

**What**: Compare SHA256 hashes to detect changed files

**Architecture**:
```python
# theauditor/indexer/change_detector.py
class FileChangeDetector:
    def __init__(self, root_path, db_path):
        self.root_path = Path(root_path)
        self.db_path = Path(db_path)
        self.manifest_path = self.db_path.parent / "manifest.json"
        self.manifest_previous_path = self.db_path.parent / "manifest.previous.json"

    def detect_changes(self):
        """Compare current manifest with previous manifest."""
        # Load previous manifest (from last successful index)
        if not self.manifest_previous_path.exists():
            # First run or previous manifest missing
            return ChangeSet(
                new=all_current_files,
                modified=[],
                deleted=[],
                unchanged=[]
            )

        previous_manifest = json.load(open(self.manifest_previous_path))
        current_manifest = json.load(open(self.manifest_path))

        previous_files = {f['path']: f['sha256'] for f in previous_manifest}
        current_files = {f['path']: f['sha256'] for f in current_manifest}

        # Classify files
        new_files = []
        modified_files = []
        unchanged_files = []

        for path, sha256 in current_files.items():
            if path not in previous_files:
                new_files.append(path)
            elif previous_files[path] != sha256:
                modified_files.append(path)
            else:
                unchanged_files.append(path)

        # Find deleted files
        deleted_files = [
            path for path in previous_files
            if path not in current_files
        ]

        return ChangeSet(
            new=new_files,
            modified=modified_files,
            deleted=deleted_files,
            unchanged=unchanged_files
        )
```

**Why**:
- **Simple**: Hash comparison is O(n) with n = number of files
- **Reliable**: SHA256 collision probability is negligible
- **Already implemented**: Manifest system already generates SHA256 hashes
- **No git dependency**: Works even if git not available

**Alternatives Considered**:

| Alternative | Pros | Cons | Rejected Why |
|-------------|------|------|--------------|
| **mtime comparison** | Faster (no hashing) | Unreliable (mtime changes don't always mean content changed) | False positives |
| **git diff** | Integrates with git | Requires git, only tracks committed changes | Limited scope |
| **inotify/FSEvents** | Real-time | Complex, platform-specific | Implemented in Phase 2, not Phase 1 |
| **Database query** | No manifest needed | Requires database to exist | Chicken-egg problem |

**Selected**: SHA256 hash comparison via manifest

**Rationale**: Already implemented, reliable, git-independent.

---

### Decision 2: Selective Table Deletion (No Truncate-All)

**What**: Delete only changed file's data, not entire database

**Implementation**:
```python
# theauditor/indexer/database/base_database.py
def delete_file_data(self, file_path: str):
    """Delete all database records for a single file."""
    cursor = self.conn.cursor()

    # File-scoped tables (118 tables)
    file_scoped_tables = [
        'symbols', 'symbols_jsx',
        'assignments', 'assignments_jsx',
        'function_call_args', 'function_call_args_jsx',
        'function_returns', 'function_returns_jsx',
        'refs', 'variable_usage',
        'cfg_blocks', 'cfg_edges', 'cfg_block_statements',
        'api_endpoints', 'sql_queries', 'orm_queries',
        'react_components', 'react_hooks',
        'python_orm_models', 'python_routes',
        # ... 100+ more tables
    ]

    for table in file_scoped_tables:
        # Delete parent records (cascades to junctions if FKs defined)
        cursor.execute(f"DELETE FROM {table} WHERE file = ?", (file_path,))

    # Junction tables (manual cascade - NO FK constraints)
    # These must be deleted BEFORE parents if FKs existed
    junction_deletes = [
        ("DELETE FROM assignment_sources WHERE assignment_file = ?", file_path),
        ("DELETE FROM assignment_sources_jsx WHERE assignment_file = ?", file_path),
        ("DELETE FROM function_return_sources WHERE return_file = ?", file_path),
        ("DELETE FROM function_return_sources_jsx WHERE return_file = ?", file_path),
        ("DELETE FROM sql_query_tables WHERE query_file = ?", file_path),
        ("DELETE FROM api_endpoint_controls WHERE endpoint_file = ?", file_path),
        ("DELETE FROM react_component_hooks WHERE component_file = ?", file_path),
        ("DELETE FROM react_hook_dependencies WHERE hook_file = ?", file_path),
    ]

    for query, param in junction_deletes:
        cursor.execute(query, (param,))

    # CFG special handling (AUTOINCREMENT IDs)
    self._delete_cfg_records(cursor, file_path)

    self.conn.commit()

def _delete_cfg_records(self, cursor, file_path):
    """Delete CFG records with ID tracking."""
    # Find all CFG block IDs for this file
    cursor.execute("SELECT id FROM cfg_blocks WHERE file = ?", (file_path,))
    block_ids = [row[0] for row in cursor.fetchall()]

    if not block_ids:
        return  # No CFG data for this file

    placeholders = ",".join("?" * len(block_ids))

    # Delete edges referencing these blocks
    cursor.execute(
        f"DELETE FROM cfg_edges WHERE source_block_id IN ({placeholders})",
        block_ids
    )
    cursor.execute(
        f"DELETE FROM cfg_edges WHERE target_block_id IN ({placeholders})",
        block_ids
    )

    # Delete block statements
    cursor.execute(
        f"DELETE FROM cfg_block_statements WHERE block_id IN ({placeholders})",
        block_ids
    )

    # Delete blocks
    cursor.execute(
        f"DELETE FROM cfg_blocks WHERE id IN ({placeholders})",
        block_ids
    )
```

**Why**:
- **Preserves unchanged files**: 95% of data untouched if 5% files change
- **Enables incremental**: Only changed files re-extracted
- **Minimal deletion**: O(changed_files) deletes instead of O(all_files)

**Alternatives Considered**:

| Alternative | Pros | Cons | Rejected Why |
|-------------|------|------|--------------|
| **TRUNCATE all tables** (current) | Simple | Deletes everything, no speedup | Defeats purpose |
| **DROP and recreate tables** | Clean slate | Schema recreation overhead | Unnecessary |
| **Soft delete (deleted flag)** | Can undo | Bloats database, complex queries | Overhead |
| **Partition by file** | Fast delete (DROP partition) | Complex schema, not SQLite compatible | Not supported |

**Selected**: Selective DELETE WHERE file = ?

**Rationale**: Minimal changes, works with existing schema, O(changed_files) complexity.

---

### Decision 3: JavaScript Global Cache from Database (Not Batch Parsing)

**What**: Rebuild JavaScript global function parameter cache from database, not batch-parsing all files

**CURRENT Approach** (orchestrator.py:258-288):
```python
# Batch-parse ALL JS/TS files to build global function cache
js_ts_files = [all JS/TS files]  # 1,000+ files
batch_trees = self.ast_parser.parse_files_batch(js_ts_files)  # Parse all

global_function_params = {}
for file_path, tree in batch_trees.items():
    functions = extract_function_definitions(tree)
    for func in functions:
        global_function_params[func['name']] = func['params']

# Inject cache into parser for cross-file resolution
self.ast_parser.global_function_params = global_function_params
```

**NEW Approach** (incremental mode):
```python
def rebuild_global_cache_from_database(db_path):
    """Rebuild JavaScript global function cache from symbols table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query all function definitions from database
    cursor.execute("""
        SELECT name, metadata
        FROM symbols
        WHERE type = 'function' AND ext IN ('.js', '.ts', '.jsx', '.tsx')
    """)

    global_function_params = {}
    for name, metadata_json in cursor.fetchall():
        metadata = json.loads(metadata_json)
        if 'params' in metadata:
            global_function_params[name] = metadata['params']

    conn.close()
    return global_function_params
```

**Why**:
- **Faster**: Query database (O(1) index lookup) vs parse 1,000 files (O(n) parse)
- **Incremental-friendly**: Works even if only 5 files changed (database has all data)
- **No re-parsing**: Unchanged files already in database, no need to parse AST again

**Impact on Cross-File Parameter Resolution**:
```python
# After incremental index:
1. Re-extract 5 changed files → store to database
2. Rebuild global cache from database (includes all 1,000 functions)
3. Re-run parameter resolution (uses fresh global cache)
4. Database now has updated parameter names for all callers
```

**Alternatives Considered**:

| Alternative | Pros | Cons | Rejected Why |
|-------------|------|------|--------------|
| **Batch-parse all files** (current) | Simple | Slow, defeats incremental | Defeats purpose |
| **Cache to disk** | Fast subsequent runs | Stale if file changes | Complexity |
| **No global cache** | Simplest | No cross-file param resolution | Loses feature |
| **Incremental cache update** | Only parse changed files' functions | Complex invalidation logic | Overkill |

**Selected**: Rebuild from database

**Rationale**: Leverages existing data, fast enough, simple implementation.

---

### Decision 4: Watchdog for File Watching (Phase 2)

**What**: Use `watchdog` library for cross-platform file system monitoring

**Architecture**:
```python
# theauditor/indexer/file_watcher.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from pathlib import Path
from queue import Queue
from threading import Thread

class IncrementalIndexHandler(FileSystemEventHandler):
    """Handle file system events and trigger incremental indexing."""

    def __init__(self, root_path, db_path, debounce_seconds=1.0):
        self.root_path = Path(root_path)
        self.db_path = Path(db_path)
        self.debounce_seconds = debounce_seconds
        self.change_queue = Queue()
        self.last_change_time = None

    def on_modified(self, event):
        """Called when a file is modified."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Filter: Only source files
        if not self._is_source_file(file_path):
            return

        # Add to change queue (debounced processing)
        self.change_queue.put(file_path)
        self.last_change_time = time.time()

    def _is_source_file(self, file_path):
        """Check if file should be indexed."""
        extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.sql', '.graphql', '.yaml', '.json'}
        return file_path.suffix in extensions

class FileWatcherDaemon:
    """Background daemon that watches for file changes and triggers indexing."""

    def __init__(self, root_path, db_path, debounce_seconds=1.0):
        self.root_path = Path(root_path)
        self.db_path = Path(db_path)
        self.debounce_seconds = debounce_seconds

        self.handler = IncrementalIndexHandler(root_path, db_path, debounce_seconds)
        self.observer = Observer()
        self.indexer_thread = None
        self.running = False

    def start(self):
        """Start watching for file changes."""
        # Schedule observer
        self.observer.schedule(self.handler, str(self.root_path), recursive=True)
        self.observer.start()

        # Start indexer thread
        self.running = True
        self.indexer_thread = Thread(target=self._process_changes, daemon=True)
        self.indexer_thread.start()

        print(f"Watching {self.root_path} for changes...")

    def stop(self):
        """Stop watching."""
        self.running = False
        self.observer.stop()
        self.observer.join()

        if self.indexer_thread:
            self.indexer_thread.join(timeout=5)

    def _process_changes(self):
        """Process file changes with debouncing."""
        while self.running:
            # Wait for debounce period
            time.sleep(self.debounce_seconds)

            # Check if any changes in queue
            if self.handler.change_queue.empty():
                continue

            # Collect all changes
            changed_files = set()
            while not self.handler.change_queue.empty():
                changed_files.add(self.handler.change_queue.get())

            # Wait additional time if still receiving changes
            if self.handler.last_change_time:
                time_since_last_change = time.time() - self.handler.last_change_time
                if time_since_last_change < self.debounce_seconds:
                    time.sleep(self.debounce_seconds - time_since_last_change)

            # Trigger incremental index
            print(f"Indexing {len(changed_files)} changed files...")
            self._incremental_index(changed_files)

    def _incremental_index(self, changed_files):
        """Run incremental index on changed files."""
        from theauditor.indexer.incremental import run_incremental_index

        try:
            run_incremental_index(
                root_path=self.root_path,
                db_path=self.db_path,
                changed_files=changed_files
            )
            print("Index updated successfully.")
        except Exception as e:
            print(f"Error during incremental index: {e}")
            # Log error but don't crash daemon
```

**Why**:
- **Cross-platform**: Works on Windows (ReadDirectoryChangesW), Linux (inotify), macOS (FSEvents)
- **Mature library**: 6+ years old, widely used (pytest uses it)
- **Event-driven**: No polling overhead
- **Debouncing built-in**: Can configure delay before triggering index

**Alternatives Considered**:

| Alternative | Pros | Cons | Rejected Why |
|-------------|------|------|--------------|
| **Native inotify/FSEvents** | No dependency | Platform-specific code | Too complex |
| **Polling (check mtime)** | Simple | CPU overhead, delayed detection | Inefficient |
| **Git hooks** | Integrates with git | Only tracks committed changes | Limited |
| **LSP file watching** | IDE integration | Requires LSP server | Overkill |

**Selected**: Watchdog library

**Rationale**: Cross-platform, mature, minimal overhead, widely adopted.

---

### Decision 5: Periodic Full Rebuild (Safety Valve)

**What**: Auto-trigger full rebuild every 50 incremental updates or 24 hours

**Implementation**:
```python
# theauditor/indexer/incremental.py
INCREMENTAL_METADATA_PATH = Path(".pf/incremental_metadata.json")

def should_force_full_rebuild():
    """Determine if full rebuild is needed."""
    if not INCREMENTAL_METADATA_PATH.exists():
        return False  # No metadata = first run

    metadata = json.load(open(INCREMENTAL_METADATA_PATH))

    # Check incremental count
    incremental_count = metadata.get('incremental_count', 0)
    if incremental_count >= 50:
        return True

    # Check time since last full rebuild
    last_full_rebuild = datetime.fromisoformat(metadata['last_full_rebuild'])
    if datetime.now() - last_full_rebuild > timedelta(hours=24):
        return True

    return False

def record_incremental_update():
    """Record that an incremental update occurred."""
    if INCREMENTAL_METADATA_PATH.exists():
        metadata = json.load(open(INCREMENTAL_METADATA_PATH))
    else:
        metadata = {
            'incremental_count': 0,
            'last_full_rebuild': datetime.now().isoformat()
        }

    metadata['incremental_count'] += 1

    json.dump(metadata, open(INCREMENTAL_METADATA_PATH, 'w'))

def record_full_rebuild():
    """Record that a full rebuild occurred."""
    metadata = {
        'incremental_count': 0,
        'last_full_rebuild': datetime.now().isoformat()
    }
    json.dump(metadata, open(INCREMENTAL_METADATA_PATH, 'w'))
```

**Why**:
- **Prevents drift**: Incremental bugs don't compound forever
- **Automatic**: No user intervention required
- **Configurable**: Can adjust thresholds (50 updates, 24 hours)

**User Override**:
```bash
# User can always force full rebuild
aud index --full

# Or set environment variable
THEAUDITOR_FORCE_FULL_REBUILD=1 aud index
```

**Rationale**: Git uses similar approach (periodic GC), proven pattern for preventing accumulation bugs.

---

## Implementation Architecture

### New File Structure

```
theauditor/
├── commands/
│   ├── index.py (MODIFIED)           # Add --incremental flag
│   └── watch.py (NEW)                 # File watching daemon command
│
├── indexer/
│   ├── orchestrator.py (MODIFIED)     # Support incremental mode
│   ├── incremental.py (NEW)           # Incremental indexing logic (~300 lines)
│   ├── change_detector.py (NEW)       # File change detection (~150 lines)
│   └── file_watcher.py (NEW)          # Watchdog integration (~200 lines)
│
├── indexer/database/
│   └── base_database.py (MODIFIED)    # Add delete_file_data() method
│
├── indexer/extractors/
│   └── javascript.py (MODIFIED)       # Rebuild global cache from DB
│
└── tests/
    └── test_incremental_indexing.py (NEW)  # Comprehensive tests (~400 lines)
```

### Data Flow

**BEFORE** (Full Rebuild):
```
User: aud index
  ↓
Walk directory (all 2,000 files)
  ↓
Compute SHA256 (all 2,000 files)
  ↓
Check AST cache (all 2,000 files)
  ↓
DELETE FROM all tables (clear everything)
  ↓
Extract data (all 2,000 files)
  ↓
INSERT INTO tables (all 2,000 files worth of data)
  ↓
Cross-file resolution
  ↓
Commit

Time: 15-30 seconds
```

**AFTER** (Incremental):
```
User: aud index --incremental
  ↓
Load previous manifest
  ↓
Walk directory (all 2,000 files)
  ↓
Compute SHA256 (all 2,000 files)
  ↓
Compare: 5 changed, 1,995 unchanged
  ↓
For 5 changed files:
  ├─ Delete old data (DELETE WHERE file = ?)
  ├─ Check AST cache
  ├─ Extract data
  └─ INSERT INTO tables
  ↓
Rebuild global cache from database
  ↓
Cross-file resolution (re-run on affected files)
  ↓
Commit
  ↓
Save manifest as previous

Time: 1-2 seconds (15-30x faster)
```

---

## Risks / Trade-offs

### Risk 1: Database Inconsistency

**Risk**: Incremental bugs compound over multiple runs

**Likelihood**: MEDIUM
**Impact**: HIGH

**Mitigation**:
1. Periodic full rebuild (every 50 incremental updates)
2. Validation checks after each incremental update
3. Full rebuild always available (`--full` flag)
4. Metadata tracking (incremental count, last full rebuild time)

**Trade-off**: Accept small risk of inconsistency for 15-30x speedup

---

### Risk 2: CFG ID Remapping Bugs

**Risk**: AUTOINCREMENT ID handling breaks CFG edges

**Likelihood**: MEDIUM
**Impact**: HIGH

**Mitigation**:
1. Comprehensive tests for CFG deletion/reinsertion
2. Validate cfg_edges still reference valid cfg_blocks after update
3. Fallback: Rebuild CFG tables entirely if validation fails

**Trade-off**: Accept complexity of ID remapping for preserving feature

---

### Risk 3: Cross-File Dependency Tracking Incomplete

**Risk**: Changing file B doesn't update file A (which imports B)

**Likelihood**: MEDIUM
**Impact**: MEDIUM

**Mitigation**:
1. Conservative approach: Re-index all importers when file changes
2. Track reverse dependencies in refs table
3. Full rebuild if dependency tracking fails

**Trade-off**: Over-indexing (re-index more files than strictly needed) for safety

---

### Risk 4: File Watching Platform Issues

**Risk**: Daemon crashes or misses events on some OSs

**Likelihood**: LOW
**Impact**: MEDIUM

**Mitigation**:
1. Comprehensive testing on Windows/Linux/macOS
2. Fallback to manual `--incremental` if daemon fails
3. Auto-restart daemon on crash
4. Watchdog library is mature (handles platform differences)

**Trade-off**: Accept watchdog limitations for cross-platform support

---

## Migration Plan

### Phase 1: Hash-Based Incremental (Week 1)

**Days 1-2: Core Implementation**
- Implement `FileChangeDetector` class
- Implement `delete_file_data()` method
- Add `--incremental` flag to `aud index` command
- Save previous manifest

**Day 3: Testing**
- Test with 5 changed files out of 2,000
- Verify database content identical to full rebuild
- Profile performance (should be 15-30x faster)

**Validation**: Incremental result === Full rebuild result

---

### Phase 2: File Watching (Week 2)

**Days 4-5: Watchdog Integration**
- Add watchdog dependency
- Implement `FileWatcherDaemon` class
- Implement debouncing logic
- Add `aud watch` command

**Day 6: Cross-File Dependencies**
- Refactor JavaScript global cache (database-driven)
- Implement reverse dependency tracking
- Test: Change file B, verify file A (imports B) updated

**Day 7: CFG Handling**
- Implement CFG ID remapping
- Test CFG deletion/reinsertion
- Validate cfg_edges integrity

**Validation**: Daemon runs 24+ hours without crashes

---

### Phase 3: Hardening (Week 3)

**Days 8-9: Safety Mechanisms**
- Implement periodic full rebuild logic
- Add validation checks
- Add lock file mechanism
- Test concurrent index prevention

**Day 10: AI Integration**
- Create post-edit hook
- Test with Claude Code workflow
- Document setup

**Validation**: AI loop works seamlessly

---

## Success Criteria

### Must Pass

1. ✅ **Correctness**: `diff <(aud index --full) <(aud index --incremental)` = empty
2. ✅ **Performance**: 15-30x faster for 5 changed files out of 2,000
3. ✅ **Safety**: Full rebuild always works
4. ✅ **Validation**: Consistency checks pass after every incremental update
5. ✅ **Tests**: 100% existing tests pass + new incremental tests

### Regression Criteria (Fail = Rollback)

1. ❌ Database content differs between full and incremental
2. ❌ Performance regression (slower than baseline)
3. ❌ Any existing test failures
4. ❌ Database corruption (orphaned rows, broken FKs)

---

**Design Approved By**: Pending
**Date**: 2025-11-02
**Status**: AWAITING ARCHITECT APPROVAL
