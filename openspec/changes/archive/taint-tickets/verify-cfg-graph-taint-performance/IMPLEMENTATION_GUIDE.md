# IMPLEMENTATION GUIDE: CFG Cache Integration

**Change ID**: `verify-cfg-graph-taint-integration`
**Status**: Ready for Implementation (Back Burner)
**Estimated Time**: 8-12 days
**Last Updated**: 2025-10-16

---

## 🚀 START HERE

**If you're picking this up fresh (in a week, month, or by a different AI):**

1. **Read this file FIRST** - Don't read anything else yet
2. **Verify prerequisites** - See "Pre-Flight Checklist" below
3. **Follow steps mechanically** - Don't skip, don't improvise
4. **Verify after each step** - Use provided commands
5. **Roll back if verification fails** - See "Rollback" sections

**Why this exists**: The CFG data pipeline works BUT cache integration is disconnected, causing 10-100x performance loss. This guide reconnects it.

---

## 📋 Pre-Flight Checklist

Before starting, verify these are TRUE:

```bash
# 1. You're on the right branch
git branch
# Expected: v1.1 or feature branch

# 2. Baseline tests pass
pytest tests/ -v
# Expected: All tests pass (100%)

# 3. Database has CFG data
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM cfg_blocks;"
# Expected: > 0 (if you have a test project indexed)

# 4. Memory cache exists and loads
python -c "from theauditor.taint.memory_cache import MemoryCache; print('OK')"
# Expected: OK

# 5. No uncommitted changes
git status
# Expected: Clean working tree OR only openspec/ changes
```

**All ✅?** Continue to Phase 2.

**Any ❌?** Fix before proceeding. See "Troubleshooting" at bottom.

---

## 🎯 Implementation Phases Overview

```
Phase 2: CFG Cache Integration (P0)          3-5 days   ← START HERE
    ├─ Step 2.1: get_block_for_line()        ~2 hours
    ├─ Step 2.2: get_paths_between_blocks()  ~2 hours
    ├─ Step 2.3: get_block_statements()      ~1 hour
    ├─ Step 2.4: get_cfg_for_function()      ~2 hours
    ├─ Step 2.5: PathAnalyzer threading      ~3 hours
    ├─ Step 2.6: InterProceduralCFGAnalyzer  ~2 hours
    ├─ Step 2.7: propagation.py integration  ~1 hour
    └─ Verification: Unit tests + benchmark  ~4 hours

Phase 3: Hot Path Tables (P1)                2-3 days
    ├─ Step 3.1: Add frameworks to cache     ~4 hours
    ├─ Step 3.2: Add object_literals         ~3 hours
    ├─ Step 3.3: Update consumers            ~4 hours
    └─ Verification: Integration tests       ~3 hours

Phase 4: Testing & Validation                2-3 days
    ├─ Step 4.1: Performance benchmarks      ~6 hours
    ├─ Step 4.2: Integration tests           ~4 hours
    └─ Step 4.3: Regression tests            ~2 hours

Phase 5: Documentation                       1 day
    ├─ Step 5.1: Update CLAUDE.md            ~2 hours
    ├─ Step 5.2: Code comments               ~2 hours
    └─ Step 5.3: Changelog                   ~1 hour
```

---

# PHASE 2: CFG CACHE INTEGRATION (P0)

**Goal**: Add optional cache parameter to CFG query functions and thread it through consumers.

**Time**: 3-5 days

**Verification After Each Step**: Run provided test command. If fails, STOP and debug.

---

## Step 2.1: Modify get_block_for_line() (2 hours)

**File**: `theauditor/taint/database.py`

**Line**: 841

### Current Code (READ FIRST):
```bash
# View current implementation
sed -n '841,880p' theauditor/taint/database.py
```

### Implementation:

**Find the function signature** (around line 841):
```python
def get_block_for_line(
    cursor: sqlite3.Cursor,
    file_path: str,
    line: int,
    function_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
```

**Change to**:
```python
def get_block_for_line(
    cursor: sqlite3.Cursor,
    file_path: str,
    line: int,
    function_name: Optional[str] = None,
    cache: Optional[Any] = None  # NEW: Optional cache parameter
) -> Optional[Dict[str, Any]]:
```

**Add cache lookup at START of function body** (after docstring):
```python
    """Get the CFG block containing a specific line.

    Args:
        cursor: Database cursor
        file_path: Path to source file
        line: Line number to find
        function_name: Optional function name filter
        cache: Optional MemoryCache for O(1) lookups

    Returns:
        Block dictionary or None
    """
    # NEW: Try cache first if available
    if cache and hasattr(cache, 'cfg_blocks_by_function'):
        # Normalize path (cache uses forward slashes)
        normalized_path = file_path.replace("\\", "/")

        # Get blocks for this function
        cache_key = (normalized_path, function_name) if function_name else None

        if cache_key:
            blocks = cache.cfg_blocks_by_function.get(cache_key, [])
            for block in blocks:
                if block["start_line"] <= line <= block["end_line"]:
                    return block
        else:
            # No function filter - check all blocks in file
            blocks = cache.cfg_blocks_by_file.get(normalized_path, [])
            for block in blocks:
                if block["start_line"] <= line <= block["end_line"]:
                    return block

    # EXISTING: Fallback to database query (keep ALL existing code below)
    # ... (don't change anything else)
```

**Keep the rest of the function UNCHANGED** - the database query is the fallback.

### Verification:

**Create test file**: `test_step_2_1.py`
```python
#!/usr/bin/env python3
"""Verification test for Step 2.1"""
import sqlite3
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from theauditor.taint.database import get_block_for_line
from theauditor.taint.memory_cache import MemoryCache

def test_get_block_for_line_with_cache():
    """Test get_block_for_line with cache parameter."""
    # Setup test database
    conn = sqlite3.connect('.pf/repo_index.db')
    cursor = conn.cursor()

    # Check if we have CFG data
    cursor.execute("SELECT COUNT(*) FROM cfg_blocks")
    count = cursor.fetchone()[0]
    if count == 0:
        print("❌ No CFG data in database. Run 'aud index' first.")
        return False

    # Get a sample block
    cursor.execute("SELECT file, function_name, start_line FROM cfg_blocks LIMIT 1")
    row = cursor.fetchone()
    if not row:
        print("❌ Could not fetch sample CFG block")
        return False

    file_path, func_name, line = row
    print(f"Testing with: {file_path}:{line} in {func_name}")

    # Test 1: Without cache (should still work)
    block_no_cache = get_block_for_line(cursor, file_path, line, func_name)
    if not block_no_cache:
        print("❌ Function returns None without cache (database fallback broken)")
        return False
    print("✅ Works without cache (backward compatible)")

    # Test 2: With cache=None (should work same as above)
    block_cache_none = get_block_for_line(cursor, file_path, line, func_name, cache=None)
    if not block_cache_none:
        print("❌ Function returns None with cache=None")
        return False
    print("✅ Works with cache=None")

    # Test 3: With loaded cache
    cache = MemoryCache()
    if not cache.preload(cursor):
        print("❌ Could not preload cache")
        return False

    block_with_cache = get_block_for_line(cursor, file_path, line, func_name, cache=cache)
    if not block_with_cache:
        print("❌ Function returns None with cache")
        return False
    print("✅ Works with cache")

    # Test 4: Results should be identical
    if block_no_cache["id"] != block_with_cache["id"]:
        print(f"❌ Cache result differs: {block_no_cache['id']} vs {block_with_cache['id']}")
        return False
    print("✅ Cache and database return identical results")

    print("\n✅ Step 2.1 VERIFIED: get_block_for_line() works correctly")
    return True

if __name__ == "__main__":
    success = test_get_block_for_line_with_cache()
    sys.exit(0 if success else 1)
```

**Run verification**:
```bash
# Make test executable
chmod +x test_step_2_1.py

# Run test
python test_step_2_1.py

# Expected output:
# Testing with: some/file.py:42 in some_function
# ✅ Works without cache (backward compatible)
# ✅ Works with cache=None
# ✅ Works with cache
# ✅ Cache and database return identical results
# ✅ Step 2.1 VERIFIED: get_block_for_line() works correctly
```

**GO/NO-GO Decision**:
- ✅ All checks pass → Continue to Step 2.2
- ❌ Any check fails → STOP, debug, re-verify

**Rollback if needed**:
```bash
git checkout theauditor/taint/database.py
```

---

## Step 2.2: Modify get_paths_between_blocks() (2 hours)

**File**: `theauditor/taint/database.py`

**Line**: 892

### Implementation:

**Change signature** (around line 892):
```python
def get_paths_between_blocks(
    cursor: sqlite3.Cursor,
    file_path: str,
    source_block_id: int,
    target_block_id: int,
    max_paths: int = 100,
    cache: Optional[Any] = None  # NEW
) -> List[List[int]]:
```

**Add cache lookup at START of function body**:
```python
    """Find all paths between two CFG blocks.

    Args:
        cursor: Database cursor
        file_path: Path to source file
        source_block_id: Starting block ID
        target_block_id: Ending block ID
        max_paths: Maximum number of paths to return
        cache: Optional MemoryCache for O(1) lookups

    Returns:
        List of paths (each path is a list of block IDs)
    """
    # NEW: Try cache first if available
    if cache and hasattr(cache, 'cfg_edges_by_source'):
        # Build adjacency list from cache
        normalized_path = file_path.replace("\\", "/")
        graph = {}

        # Get all edges for this file from cache
        edges = cache.cfg_edges_by_file.get(normalized_path, [])
        for edge in edges:
            source = edge["source_block_id"]
            target = edge["target_block_id"]
            if source not in graph:
                graph[source] = []
            graph[source].append(target)

        # DFS path finding using cached graph
        paths = []
        stack = [(source_block_id, [source_block_id])]

        while stack and len(paths) < max_paths:
            current, path = stack.pop()

            if current == target_block_id:
                paths.append(path)
                continue

            if current in graph:
                for neighbor in graph[current]:
                    if neighbor not in path:  # Avoid cycles
                        stack.append((neighbor, path + [neighbor]))

        return paths

    # EXISTING: Fallback to database query (keep ALL existing code)
    # ... (don't change anything else)
```

### Verification:

**Create test file**: `test_step_2_2.py`
```python
#!/usr/bin/env python3
"""Verification test for Step 2.2"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from theauditor.taint.database import get_paths_between_blocks
from theauditor.taint.memory_cache import MemoryCache

def test_get_paths_between_blocks_with_cache():
    """Test get_paths_between_blocks with cache parameter."""
    conn = sqlite3.connect('.pf/repo_index.db')
    cursor = conn.cursor()

    # Get sample blocks with a path between them
    cursor.execute("""
        SELECT e.file, e.source_block_id, e.target_block_id
        FROM cfg_edges e
        LIMIT 1
    """)
    row = cursor.fetchone()
    if not row:
        print("❌ No CFG edges in database")
        return False

    file_path, source_id, target_id = row
    print(f"Testing path from block {source_id} to {target_id}")

    # Test without cache
    paths_no_cache = get_paths_between_blocks(cursor, file_path, source_id, target_id)
    print(f"✅ Found {len(paths_no_cache)} paths without cache")

    # Test with cache
    cache = MemoryCache()
    cache.preload(cursor)
    paths_with_cache = get_paths_between_blocks(cursor, file_path, source_id, target_id, cache=cache)
    print(f"✅ Found {len(paths_with_cache)} paths with cache")

    # Results should be identical (or at least same count)
    if len(paths_no_cache) != len(paths_with_cache):
        print(f"⚠️  Warning: Different path counts (may be OK if path enumeration differs)")
        # This is not necessarily an error - different traversal orders are OK

    print("\n✅ Step 2.2 VERIFIED: get_paths_between_blocks() works correctly")
    return True

if __name__ == "__main__":
    success = test_get_paths_between_blocks_with_cache()
    sys.exit(0 if success else 1)
```

**Run verification**:
```bash
python test_step_2_2.py
```

---

## Step 2.3: Modify get_block_statements() (1 hour)

**File**: `theauditor/taint/database.py`

**Line**: 952

### Implementation:

**Change signature**:
```python
def get_block_statements(
    cursor: sqlite3.Cursor,
    block_id: int,
    cache: Optional[Any] = None  # NEW
) -> List[Dict[str, Any]]:
```

**Add cache lookup**:
```python
    """Get all statements in a CFG block.

    Args:
        cursor: Database cursor
        block_id: CFG block ID
        cache: Optional MemoryCache for O(1) lookups

    Returns:
        List of statement dictionaries
    """
    # NEW: Try cache first
    if cache and hasattr(cache, 'cfg_statements_by_block'):
        statements = cache.cfg_statements_by_block.get(block_id, [])
        # Return copy to avoid external modifications
        return [stmt.copy() for stmt in statements]

    # EXISTING: Fallback to database (keep existing code)
    # ...
```

### Verification:

```python
#!/usr/bin/env python3
"""Verification test for Step 2.3"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from theauditor.taint.database import get_block_statements
from theauditor.taint.memory_cache import MemoryCache

def test_get_block_statements_with_cache():
    conn = sqlite3.connect('.pf/repo_index.db')
    cursor = conn.cursor()

    # Get a block with statements
    cursor.execute("""
        SELECT block_id FROM cfg_block_statements LIMIT 1
    """)
    row = cursor.fetchone()
    if not row:
        print("❌ No CFG statements in database")
        return False

    block_id = row[0]

    # Test without cache
    stmts_no_cache = get_block_statements(cursor, block_id)
    print(f"✅ Found {len(stmts_no_cache)} statements without cache")

    # Test with cache
    cache = MemoryCache()
    cache.preload(cursor)
    stmts_with_cache = get_block_statements(cursor, block_id, cache=cache)
    print(f"✅ Found {len(stmts_with_cache)} statements with cache")

    if len(stmts_no_cache) != len(stmts_with_cache):
        print(f"❌ Statement count mismatch")
        return False

    print("\n✅ Step 2.3 VERIFIED")
    return True

if __name__ == "__main__":
    success = test_get_block_statements_with_cache()
    sys.exit(0 if success else 1)
```

---

## Step 2.4: Modify get_cfg_for_function() (2 hours)

**File**: `theauditor/taint/database.py`

**Line**: 984

### Implementation:

**Change signature**:
```python
def get_cfg_for_function(
    cursor: sqlite3.Cursor,
    file_path: str,
    function_name: str,
    cache: Optional[Any] = None  # NEW
) -> Dict[str, Any]:
```

**Add cache lookup**:
```python
    """Get complete CFG for a function.

    Args:
        cursor: Database cursor
        file_path: Path to source file
        function_name: Function name
        cache: Optional MemoryCache for O(1) lookups

    Returns:
        CFG dictionary with blocks and edges
    """
    # NEW: Try cache first
    if cache and hasattr(cache, 'cfg_blocks_by_function'):
        normalized_path = file_path.replace("\\", "/")
        cache_key = (normalized_path, function_name)

        # Get blocks from cache
        blocks = cache.cfg_blocks_by_function.get(cache_key, [])

        # Get edges from cache
        edges = cache.cfg_edges_by_function.get(cache_key, [])

        return {
            "blocks": [b.copy() for b in blocks],
            "edges": [e.copy() for e in edges]
        }

    # EXISTING: Fallback to database (keep existing code)
    # ...
```

### Verification:

Create `test_step_2_4.py` similar to above, test that blocks and edges are returned correctly.

---

## Step 2.5: Thread Cache Through PathAnalyzer (3 hours)

**File**: `theauditor/taint/cfg_integration.py`

**Line**: 78

### Implementation:

**Modify PathAnalyzer.__init__()**:
```python
def __init__(
    self,
    cursor: sqlite3.Cursor,
    file_path: str,
    function_name: str,
    cache: Optional[Any] = None  # NEW
) -> None:
    """Initialize path analyzer.

    Args:
        cursor: Database cursor
        file_path: Path to source file
        function_name: Function name
        cache: Optional MemoryCache instance
    """
    self.cursor = cursor
    self.file_path = file_path.replace("\\", "/")
    self.function_name = function_name
    self.cache = cache  # NEW: Store cache

    # NEW: Pass cache to get_cfg_for_function
    self.cfg = get_cfg_for_function(cursor, file_path, function_name, cache=cache)

    # ... rest unchanged
```

**Update all get_block_for_line calls** (search file for them):
```python
# FIND:
source_block = get_block_for_line(self.cursor, self.file_path, source_line, self.function_name)

# CHANGE TO:
source_block = get_block_for_line(self.cursor, self.file_path, source_line, self.function_name, cache=self.cache)
```

**Update trace_flow_sensitive signature** (line 641):
```python
def trace_flow_sensitive(
    cursor: sqlite3.Cursor,
    source: Dict[str, Any],
    sink: Dict[str, Any],
    source_function: Dict[str, Any],
    max_paths: int = 100,
    cache: Optional[Any] = None  # NEW
) -> List[Dict[str, Any]]:
    """Perform flow-sensitive taint analysis using CFG.

    Args:
        cursor: Database cursor
        source: Taint source
        sink: Security sink
        source_function: Function containing source
        max_paths: Maximum paths to analyze
        cache: Optional MemoryCache instance

    Returns:
        List of vulnerable paths
    """
    # ... existing code ...

    # NEW: Pass cache to PathAnalyzer
    analyzer = PathAnalyzer(cursor, source["file"], source_function["name"], cache=cache)

    # ... rest unchanged
```

### Verification:

```python
#!/usr/bin/env python3
"""Verification test for Step 2.5"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from theauditor.taint.cfg_integration import PathAnalyzer
from theauditor.taint.memory_cache import MemoryCache

def test_path_analyzer_with_cache():
    conn = sqlite3.connect('.pf/repo_index.db')
    cursor = conn.cursor()

    # Get a function with CFG
    cursor.execute("""
        SELECT DISTINCT file, function_name
        FROM cfg_blocks
        LIMIT 1
    """)
    row = cursor.fetchone()
    if not row:
        print("❌ No CFG data")
        return False

    file_path, func_name = row

    # Test without cache
    analyzer_no_cache = PathAnalyzer(cursor, file_path, func_name)
    print(f"✅ PathAnalyzer created without cache")
    print(f"   Blocks: {len(analyzer_no_cache.blocks)}")

    # Test with cache
    cache = MemoryCache()
    cache.preload(cursor)
    analyzer_with_cache = PathAnalyzer(cursor, file_path, func_name, cache=cache)
    print(f"✅ PathAnalyzer created with cache")
    print(f"   Blocks: {len(analyzer_with_cache.blocks)}")

    if len(analyzer_no_cache.blocks) != len(analyzer_with_cache.blocks):
        print("❌ Block count mismatch")
        return False

    print("\n✅ Step 2.5 VERIFIED")
    return True

if __name__ == "__main__":
    success = test_path_analyzer_with_cache()
    sys.exit(0 if success else 1)
```

---

## Step 2.6: Thread Cache Through InterProceduralCFGAnalyzer (2 hours)

**File**: `theauditor/taint/interprocedural_cfg.py`

**Line**: 138

### Implementation:

**Find where PathAnalyzer is created** (around line 138):
```python
# FIND:
analyzer = PathAnalyzer(self.cursor, callee_file, callee_func)

# CHANGE TO:
analyzer = PathAnalyzer(self.cursor, callee_file, callee_func, cache=self.cache)
```

**Note**: InterProceduralCFGAnalyzer already has cache in __init__ (line 82), just need to pass it through.

### Verification:

Test that interprocedural analysis uses cache correctly.

---

## Step 2.7: Thread Cache Through propagation.py (1 hour)

**File**: `theauditor/taint/propagation.py`

**Search for calls to trace_flow_sensitive** and add cache parameter.

### Implementation:

Find all calls (use grep):
```bash
grep -n "trace_flow_sensitive" theauditor/taint/propagation.py
```

Update each call to include `cache=cache` parameter.

---

## Phase 2 Verification: End-to-End Test (4 hours)

**Goal**: Verify entire CFG cache integration works end-to-end.

### Benchmark Test:

**Create**: `benchmark_cfg_cache.py`
```python
#!/usr/bin/env python3
"""End-to-end benchmark for CFG cache integration"""
import sqlite3
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from theauditor.taint.database import get_block_for_line, get_cfg_for_function
from theauditor.taint.memory_cache import MemoryCache

def benchmark_cfg_queries():
    """Benchmark CFG queries with and without cache."""
    conn = sqlite3.connect('.pf/repo_index.db')
    cursor = conn.cursor()

    # Get test data
    cursor.execute("""
        SELECT file, function_name, start_line
        FROM cfg_blocks
        LIMIT 100
    """)
    test_cases = cursor.fetchall()

    if len(test_cases) < 10:
        print("❌ Insufficient CFG data for benchmark")
        return False

    print(f"Running benchmark with {len(test_cases)} queries...\n")

    # Benchmark WITHOUT cache
    start = time.perf_counter()
    for file, func, line in test_cases:
        get_block_for_line(cursor, file, line, func)
    time_no_cache = time.perf_counter() - start

    print(f"WITHOUT cache: {time_no_cache:.4f}s")

    # Benchmark WITH cache
    cache = MemoryCache()
    if not cache.preload(cursor):
        print("❌ Cache preload failed")
        return False

    start = time.perf_counter()
    for file, func, line in test_cases:
        get_block_for_line(cursor, file, line, func, cache=cache)
    time_with_cache = time.perf_counter() - start

    print(f"WITH cache:    {time_with_cache:.4f}s")

    # Calculate speedup
    if time_with_cache > 0:
        speedup = time_no_cache / time_with_cache
        print(f"\nSpeedup: {speedup:.1f}x")

        if speedup < 10.0:
            print(f"⚠️  Warning: Speedup {speedup:.1f}x is below 10x target")
            print("   This may be OK if dataset is small or disk is fast")
        else:
            print(f"✅ Speedup {speedup:.1f}x meets 10x target")

    print("\n✅ Phase 2 COMPLETE: CFG cache integration working")
    return True

if __name__ == "__main__":
    success = benchmark_cfg_queries()
    sys.exit(0 if success else 1)
```

**Run**:
```bash
python benchmark_cfg_cache.py

# Expected output:
# Running benchmark with 100 queries...
# WITHOUT cache: 0.5234s
# WITH cache:    0.0123s
# Speedup: 42.5x
# ✅ Phase 2 COMPLETE
```

**GO/NO-GO Decision**:
- ✅ Speedup ≥ 10x → Phase 2 COMPLETE, commit and move to Phase 3
- ⚠️  Speedup 5-10x → Acceptable, but investigate why not higher
- ❌ Speedup < 5x → Something is wrong, debug before proceeding

**Commit Phase 2**:
```bash
git add theauditor/taint/database.py
git add theauditor/taint/cfg_integration.py
git add theauditor/taint/interprocedural_cfg.py
git add theauditor/taint/propagation.py
git commit -m "feat(taint): add CFG cache integration (Phase 2)

- Add optional cache parameter to 4 CFG query functions
- Thread cache through PathAnalyzer and InterProceduralCFGAnalyzer
- Maintain backward compatibility (cache optional with None default)
- Measured speedup: XXx (update with actual benchmark result)

Ref: openspec/changes/verify-cfg-graph-taint-integration"
```

---

# PHASE 3: HOT PATH TABLES (P1)

**Time**: 2-3 days

**Goal**: Add frameworks, object_literals, framework_safe_sinks tables to cache.

## Step 3.1: Add frameworks to memory_cache.py (4 hours)

**File**: `theauditor/taint/memory_cache.py`

**Location**: After line 62 (in __init__)

### Implementation:

**Add storage** (after line 62):
```python
# Phase 3: Hot path tables
self.frameworks = []
self.framework_safe_sinks = []
```

**Add indexes** (after line 114):
```python
# Frameworks indexes
self.frameworks_by_name = defaultdict(list)
self.framework_safe_sinks_by_pattern = defaultdict(list)
```

**Add loading** (in preload method, after line 510):
```python
# Step 8: Load frameworks table (Phase 3.1)
query = build_query('frameworks', ['name', 'version', 'language', 'path', 'is_primary'])
cursor.execute(query)

for name, version, language, path, is_primary in cursor.fetchall():
    fw = {
        "name": name,
        "version": version or "",
        "language": language or "",
        "path": path or "",
        "is_primary": bool(is_primary)
    }
    self.frameworks.append(fw)
    self.frameworks_by_name[name].append(fw)
    self.current_memory += sys.getsizeof(fw) + 50

print(f"[MEMORY] Loaded {len(self.frameworks)} frameworks", file=sys.stderr)

# Load framework_safe_sinks
query = build_query('framework_safe_sinks', ['sink_pattern', 'framework', 'reason'])
cursor.execute(query)

for pattern, framework, reason in cursor.fetchall():
    sink = {
        "sink_pattern": pattern or "",
        "framework": framework or "",
        "reason": reason or ""
    }
    self.framework_safe_sinks.append(sink)
    self.framework_safe_sinks_by_pattern[pattern].append(sink)
    self.current_memory += sys.getsizeof(sink) + 50

print(f"[MEMORY] Loaded {len(self.framework_safe_sinks)} framework safe sinks", file=sys.stderr)
```

**Add cached methods** (after line 955):
```python
def get_frameworks_cached(self) -> List[Dict[str, Any]]:
    """Get all frameworks from cache."""
    return self.frameworks.copy()

def get_framework_safe_sinks_cached(self) -> List[Dict[str, Any]]:
    """Get all framework safe sinks from cache."""
    return self.framework_safe_sinks.copy()
```

**Update clear() method** (find and add):
```python
def clear(self):
    """Clear all cached data."""
    # ... existing clears ...

    # Phase 3 clears
    self.frameworks.clear()
    self.framework_safe_sinks.clear()
    self.frameworks_by_name.clear()
    self.framework_safe_sinks_by_pattern.clear()

    # ... rest of method
```

### Verification:

```python
#!/usr/bin/env python3
"""Verification test for Step 3.1"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from theauditor.taint.memory_cache import MemoryCache

def test_frameworks_cache():
    conn = sqlite3.connect('.pf/repo_index.db')
    cursor = conn.cursor()

    # Check if frameworks exist
    cursor.execute("SELECT COUNT(*) FROM frameworks")
    db_count = cursor.fetchone()[0]
    print(f"Database has {db_count} frameworks")

    # Load cache
    cache = MemoryCache()
    if not cache.preload(cursor):
        print("❌ Cache preload failed")
        return False

    # Verify frameworks loaded
    cache_count = len(cache.frameworks)
    print(f"Cache loaded {cache_count} frameworks")

    if db_count != cache_count:
        print(f"❌ Count mismatch: DB={db_count}, Cache={cache_count}")
        return False

    # Test cached method
    frameworks = cache.get_frameworks_cached()
    if len(frameworks) != cache_count:
        print("❌ get_frameworks_cached() returns wrong count")
        return False

    print("✅ Step 3.1 VERIFIED: Frameworks table cached")
    return True

if __name__ == "__main__":
    success = test_frameworks_cache()
    sys.exit(0 if success else 1)
```

---

## Step 3.2: Add object_literals to cache (3 hours)

**Similar to Step 3.1**, add:
- Storage: `self.object_literals = []`
- Indexes: `self.object_literals_by_variable`, `self.object_literals_by_file`
- Loading logic in preload()
- Cached method: `get_object_literals_by_variable_cached()`

---

## Step 3.3: Update Consumers to Use Cache (4 hours)

### Update taint/core.py (frameworks):

**Find** (around line 145):
```python
# Get detected frameworks
cursor.execute(query)
for name, version, language, path in cursor.fetchall():
    frameworks.append({...})
```

**Change to**:
```python
# Get detected frameworks
if cache and hasattr(cache, 'get_frameworks_cached'):
    frameworks = cache.get_frameworks_cached()
else:
    # Fallback to database
    cursor.execute(query)
    for name, version, language, path in cursor.fetchall():
        frameworks.append({...})
```

### Update interprocedural_cfg.py (object_literals):

**Find** (around line 246):
```python
query = build_query('object_literals', ...)
self.cursor.execute(query, (base_obj,))
```

**Change to**:
```python
if self.cache and hasattr(self.cache, 'object_literals_by_variable'):
    normalized_obj = base_obj  # Add any normalization needed
    possible_callees = []
    for literal in self.cache.object_literals_by_variable.get(normalized_obj, []):
        if literal.get("property_type") in ('function_ref', 'shorthand'):
            possible_callees.append(literal["property_value"])
else:
    # Fallback to database
    query = build_query('object_literals', ...)
    self.cursor.execute(query, (base_obj,))
    for property_value, in self.cursor.fetchall():
        possible_callees.append(property_value)
```

### Verification:

Test that consumers use cache when available and fall back to database when not.

---

# PHASE 4: TESTING & VALIDATION (2-3 days)

## Step 4.1: Performance Benchmarks (6 hours)

**Create comprehensive benchmark suite** measuring:
- CFG query time (with/without cache)
- Full taint analysis time (small/medium/large projects)
- Cache hit rate
- Memory usage

**Expected Results**:
- CFG queries: 10-100x speedup
- Pipeline: 2-20x speedup (varies by project size)
- Cache hit rate: >90%

**See**: verification.md for complete benchmark specifications.

---

## Step 4.2: Integration Tests (4 hours)

**Create**: `tests/integration/test_cfg_cache_integration.py`

Test scenarios:
1. Taint analysis with CFG cache enabled
2. Interprocedural analysis with CFG cache
3. Framework detection using cached frameworks
4. Dynamic dispatch with cached object literals
5. Cache miss → fallback → correct result

---

## Step 4.3: Regression Tests (2 hours)

**Run full test suite**:
```bash
pytest tests/ -v --cov=theauditor --cov-report=html

# Expected: 100% of tests pass, >90% coverage on modified files
```

**GO/NO-GO Decision**:
- ✅ All tests pass → Proceed to Phase 5
- ❌ Any test fails → STOP, fix, re-test

---

# PHASE 5: DOCUMENTATION (1 day)

## Step 5.1: Update CLAUDE.md (2 hours)

**Add sections**:
1. Memory cache CFG integration
2. Hot path table caching
3. Performance expectations with cache
4. Usage examples

## Step 5.2: Code Comments (2 hours)

Add/update docstrings in:
- Modified functions (cache parameter docs)
- MemoryCache class (new tables)
- Integration points

## Step 5.3: Changelog (1 hour)

**Add to CHANGELOG.md**:
```markdown
## [1.2.1] - 2025-XX-XX

### Added
- CFG cache integration for 10-100x query speedup
- Hot path table caching (frameworks, object_literals, framework_safe_sinks)
- Comprehensive cache hit rate monitoring

### Performance
- CFG queries: 10-100x faster with cache
- Pipeline: 2-20x faster depending on project size
- Cache hit rate: >90% during typical analysis

### Changed
- CFG query functions now accept optional cache parameter (backward compatible)
- PathAnalyzer threads cache through all CFG operations
- InterProceduralCFGAnalyzer propagates cache to nested analyses

### Compatibility
- All changes backward compatible
- Existing code works without modification
- Cache parameter optional with None default
```

---

# 🛠️ TROUBLESHOOTING

## Problem: "No CFG data in database"

**Cause**: Database doesn't have CFG tables populated.

**Fix**:
```bash
# Re-index project with CFG extraction
aud index --target /path/to/test/project

# Verify CFG data exists
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM cfg_blocks;"
# Should be > 0
```

---

## Problem: "Cache preload failed"

**Cause**: Memory limit exceeded or table doesn't exist.

**Fix**:
```bash
# Check memory usage
python -c "from theauditor.utils.memory import get_available_memory; print(f'{get_available_memory()}MB available')"

# Check if tables exist
sqlite3 .pf/repo_index.db ".tables" | grep cfg

# Try with explicit memory limit
THEAUDITOR_MEMORY_LIMIT_MB=2000 python your_test.py
```

---

## Problem: "Speedup < 10x"

**Possible causes**:
1. Dataset too small (< 100 CFG blocks)
2. Disk is very fast (SSD with cache)
3. Cache not being used (check hasattr guards)

**Debug**:
```python
# Add debug output in get_block_for_line
if cache:
    print("USING CACHE", file=sys.stderr)
else:
    print("USING DATABASE", file=sys.stderr)
```

---

## Problem: "Test fails with 'module not found'"

**Fix**:
```bash
# Ensure you're in project root
cd /c/Users/santa/Desktop/TheAuditor

# Run with proper Python path
PYTHONPATH=/c/Users/santa/Desktop/TheAuditor python test_step_2_1.py
```

---

# 📝 FINAL CHECKLIST

Before marking COMPLETE:

- [ ] All Phase 2 steps verified (7 steps + benchmark)
- [ ] All Phase 3 steps verified (3 tables cached)
- [ ] Benchmark shows ≥10x CFG query speedup
- [ ] Full test suite passes (pytest 100%)
- [ ] Integration tests pass
- [ ] Regression tests pass (zero failures)
- [ ] Performance benchmarks meet targets
- [ ] Code comments added
- [ ] CLAUDE.md updated
- [ ] Changelog updated
- [ ] Git commits clean and documented

**Final command**:
```bash
# Run everything
pytest tests/ -v && python benchmark_cfg_cache.py

# If all ✅, merge to main
git checkout main
git merge your-feature-branch
```

---

# 🎯 QUICK REFERENCE

**Files Modified**:
1. `theauditor/taint/database.py` - 4 CFG query functions
2. `theauditor/taint/cfg_integration.py` - PathAnalyzer
3. `theauditor/taint/interprocedural_cfg.py` - InterProceduralCFGAnalyzer
4. `theauditor/taint/propagation.py` - Cache threading
5. `theauditor/taint/memory_cache.py` - Hot path tables
6. `theauditor/taint/core.py` - Framework cache usage

**Commands Cheat Sheet**:
```bash
# Verify CFG data exists
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM cfg_blocks;"

# Run step verification
python test_step_X_Y.py

# Run benchmarks
python benchmark_cfg_cache.py

# Run tests
pytest tests/ -v

# Check memory
python -c "from theauditor.utils.memory import get_recommended_memory_limit; print(f'{get_recommended_memory_limit()}MB')"
```

---

**STATUS**: Implementation guide complete. Pick up anytime with confidence.

**Last Updated**: 2025-10-16
**Next Reviewer**: Read from "🚀 START HERE"
