# Verification Report: ZERO FALLBACK Extraction Refactor

**Per TeamSOP v4.20 Section 2.3**: This verification MUST be complete before implementation begins.

---

## 1. Hypotheses & Verification (Pre-Implementation)

### Hypothesis 1: `core_storage.py` has 3 deduplication blocks at lines 294, 388, 553

**Verification Method**: Direct file read with grep for `seen = set()`

**Command**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && grep -n "seen = set()" theauditor/indexer/storage/core_storage.py
```

**Status**: CONFIRMED (verified 2025-11-24)

**Evidence** (from grep verification):
- Line 294: `_store_assignments` dedup block (lines 294-302)
- Line 388: `_store_returns` dedup block (lines 388-396)
- Line 553: `_store_env_var_usage` dedup block (lines 553-561)

**Actual Code Found**:
```python
# _store_assignments (lines 294-305):
seen = set()
deduplicated = []
for assignment in assignments:
    key = (file_path, assignment['line'], assignment['target_var'])
    if key not in seen:
        seen.add(key)
        deduplicated.append(assignment)
    else:
        logger.debug(f"[DEDUP] Skipping duplicate assignment: {key}")
```

---

### Hypothesis 2: `core_database.py` has deduplication in `add_file` method at lines 22-31

**Verification Method**: Direct file read

**Command**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && grep -n "if not any" theauditor/indexer/database/core_database.py
```

**Status**: CONFIRMED

**Evidence**:
- Line 30: `if not any(item[0] == path for item in batch):`

**Actual Code Found**:
```python
def add_file(self, path: str, sha256: str, ext: str, bytes_size: int, loc: int):
    """Add a file record to the batch.

    Deduplicates paths to prevent UNIQUE constraint violations.
    This can happen with symlinks, junction points, or case sensitivity issues.
    """
    batch = self.generic_batches['files']
    if not any(item[0] == path for item in batch):
        batch.append((path, sha256, ext, bytes_size, loc))
```

---

### Hypothesis 3: `generated_validators.py` is unused (dead code)

**Verification Method**: Grep for imports across entire codebase

**Commands**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && grep -r "from.*generated_validators" theauditor/
cd C:/Users/santa/Desktop/TheAuditor && grep -r "import.*generated_validators" theauditor/
```

**Status**: CONFIRMED (verified 2025-11-24)

**Evidence**: Grep returned "No matches found" - zero imports across entire codebase

**Conclusion**: `generated_validators.py` is confirmed dead code. Safe to delete in Phase 2.

---

### Hypothesis 4: Existing `visited_nodes` pattern exists in `typescript_impl.py`

**Verification Method**: Direct file read

**Command**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && grep -n "visited_nodes" theauditor/ast_extractors/typescript_impl.py
```

**Status**: CONFIRMED

**Evidence** (from grep results):
- Line 493-505: First `visited_nodes` pattern
- Line 884-895: Second `visited_nodes` pattern

**Actual Code Found**:
```python
# typescript_impl.py:493-505
# Track visited nodes by (line, column, kind) to avoid processing same node multiple times
visited_nodes = set()

for node in nodes:
    node_id = (node.get('line'), node.get('col'), node.get('kind'))
    if node_id in visited_nodes:
        continue
    visited_nodes.add(node_id)
    # ... process node ...
```

---

### Hypothesis 5: Foreign keys are currently disabled (PRAGMA foreign_keys = OFF)

**Verification Method**: Search for PRAGMA statement in database code

**Command**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && grep -rn "foreign_keys" theauditor/indexer/database/
```

**Status**: CONFIRMED (by absence)

**Evidence**:
- No `PRAGMA foreign_keys = ON` found in any database file
- SQLite defaults to `foreign_keys = OFF`
- CLAUDE.md line 417 states: "Foreign keys not enforced: PRAGMA foreign_keys = 0 by design"

---

### Hypothesis 6: `flush_order` list exists in `base_database.py`

**Verification Method**: Direct file read

**Command**:
```bash
cd C:/Users/santa/Desktop/TheAuditor && grep -n "flush_order" theauditor/indexer/database/base_database.py
```

**Status**: CONFIRMED

**Evidence**:
- Lines 294-437: `flush_order = [` list with 80+ tables in dependency order

**Concern Identified**:
- Must verify `files` appears before `symbols`, `symbols` before `assignments`
- This is critical for Phase 3 FK enforcement

---

## 2. Discrepancies Found

### Discrepancy 1: Line numbers may shift

**Issue**: The line numbers documented (294, 388, 551) are based on current file state. Any prior edits will shift these.

**Mitigation**: Tasks use `grep` commands to find patterns, not hardcoded line numbers. The patterns (`seen = set()`, `if key not in seen:`) are unique enough to locate.

### Discrepancy 2: Commit 89731e0 already added some TypeErrors

**Issue**: Recent commit added TypeError checks in `_store_function_calls` for `callee_file_path` and `param_name`.

**Mitigation**: Task 2.3.1 explicitly notes "Some checks already exist from commit 89731e0 - don't duplicate"

### Discrepancy 3: Unknown extractor crash locations

**Issue**: We don't know which specific extractors will crash when deduplication is removed.

**Mitigation**: Task 1.5.2 provides the fix pattern (`visited_nodes`) and lists all potential locations to check:
- `typescript_impl.py`
- `javascript/*.js`
- `extractors/python.py`

---

## 3. Risk Assessment

| Risk | Verification Status | Mitigation |
|------|---------------------|------------|
| Wrong line numbers | MITIGATED | Use grep patterns, not hardcoded lines |
| Missing dedup locations | CONFIRMED | Found all 3 in storage + 1 in database |
| FK cascade failures | CONFIRMED | flush_order exists, will verify order |
| Test suite failures | EXPECTED | Fix extractors immediately per Architect directive |

---

## 4. Verification Checklist (Complete Before Phase 1)

- [x] Dedup block locations confirmed in `core_storage.py` (lines 294, 388, 553)
- [x] Dedup check confirmed in `core_database.py:add_file` (line 30)
- [x] `generated_validators.py` confirmed unused (grep: zero imports)
- [x] `visited_nodes` pattern confirmed in `typescript_impl.py` (lines 493-505, 884-895)
- [x] FK pragma absence confirmed (SQLite defaults OFF)
- [x] `flush_order` list existence confirmed (lines 294-437)

**ALL HYPOTHESES VERIFIED. IMPLEMENTATION MAY PROCEED.**

---

## 5. Evidence Artifacts

### Artifact 1: Current dedup pattern (to be removed)
```python
# This pattern appears 3 times in core_storage.py
# BEFORE (fallback - VIOLATES ZERO FALLBACK):
seen = set()
deduplicated = []
for item in items:
    key = (file_path, item['line'], item['name'])
    if key not in seen:
        seen.add(key)
        deduplicated.append(item)
    # else: SILENT DROP - THIS IS THE BUG
```

### Artifact 2: Replacement pattern (to be implemented)
```python
# AFTER (hard fail - COMPLIES WITH ZERO FALLBACK):
seen = set()
for item in items:
    key = (file_path, item['line'], item['name'])
    if key in seen:
        raise ValueError(
            f"EXTRACTOR BUG: Duplicate detected.\n"
            f"  File: {file_path}\n"
            f"  Identity: {key}\n"
            f"  Fix extractor to visit nodes only once.\n"
            f"  Reference: typescript_impl.py:493-505"
        )
    seen.add(key)
```

### Artifact 3: Extractor fix pattern (reference)
```python
# From typescript_impl.py:493-505 (EXISTING PATTERN TO COPY)
visited_nodes = set()
for node in nodes:
    node_id = (node.get('line'), node.get('col'), node.get('kind'))
    if node_id in visited_nodes:
        continue  # Already processed this node
    visited_nodes.add(node_id)
    # ... process node ...
```

---

## 6. Confirmation Statement

**Verification Finding**: All primary hypotheses confirmed through direct code reading. Deduplication fallbacks exist at documented locations. Existing `visited_nodes` pattern available for extractor fixes.

**Root Cause**: Codebase optimizes for "not crashing" rather than "correctness" - silent deduplication masks extractor bugs.

**Implementation Logic**: 3-phase approach (Truth Serum -> Bouncer -> Lockdown) isolates changes and allows incremental validation.

**Confidence Level**: HIGH - Based on direct code reading with grep verification.

---

**This verification is COMPLETE. Implementation may proceed per tasks.md.**
