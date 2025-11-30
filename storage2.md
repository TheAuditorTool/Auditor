# STOR.md - Storage Layer Pre-Implementation Plan

> **Document Type**: teamsop.md v4.20 Compliant Pre-Implementation Analysis
> **Status**: VERIFICATION REQUIRED
> **Scope**: Complete Storage Layer Architecture Audit

---

## Executive Summary

The Storage Layer is the critical intermediary between Extractors (Producers) and Graph/Taint Engines (Consumers). Analysis reveals a **systemic "Tower of Babel" problem**: layers are not speaking the same language, causing data loss, crashes, and graph fragmentation.

---

## Part 1: Architecture Overview

### 1.1 Storage Layer Flow

```
Schema (*_schema.py) -> Storage (*_storage.py) -> Database Manager (*_database.py)
```

1. **Schema**: Defines table structures
2. **Storage**: Receives raw analysis data from AST extractors, normalizes it, sends to Database Manager
3. **Database Manager**: Batches records into generic lists, performs bulk INSERT operations

### 1.2 Key Files

| Component | File | Purpose |
|-----------|------|---------|
| Base Database | `base_database.py` | Generic batch flushing, schema validation |
| Core Database | `core_database.py` | Symbol/assignment insertion methods |
| Node Database | `node_database.py` | React/Vue/Express-specific insertion |
| Infrastructure Database | `infrastructure_database.py` | Docker/Terraform/GraphQL insertion |
| Core Storage | `core_storage.py` | Handler mapping for core data types |
| Node Storage | `node_storage.py` | Handler mapping for Node.js data |
| Infrastructure Storage | `infrastructure_storage.py` | Handler mapping for infra data |
| Schema | `schema.py` | Master schema aggregation |

### 1.3 Two Database Architecture

| Database | Location | Purpose | Size |
|----------|----------|---------|------|
| repo_index.db | `.pf/repo_index.db` | Raw AST facts (144 tables) | ~181MB |
| graphs.db | `.pf/graphs.db` | Pre-computed graph structures | ~126MB |

---

## Part 2: Critical Bugs Identified

### 2.1 CATEGORY A: The "Tuple Alignment" Risk

**Severity: CRITICAL (Crash/Data Corruption)**

The system relies on `base_database.py` -> `flush_generic_batch` to map tuples directly to SQL columns. Tuple order and count MUST match TableSchema definitions exactly.

#### Known Mismatches:

**A1. `core_database.py` -> `add_symbol`**
- Line 47: Appends **8** items
- `core_schema.py` -> `SYMBOLS`: Has **9** columns (includes `is_typed`)
- **Status**: MISMATCH - `is_typed` not provided
- **Risk**: Relies on implicit behavior if `is_typed` is last column

**A2. `core_database.py` -> `add_cfg_block_jsx`**
- Line 175: Appends **9** items (including `temp_id`)
- `core_schema.py` -> `CFG_BLOCKS_JSX`: Has **9** columns (including `id`)
- **Risk**: `flush_generic_batch` (line 137) strips `id` column from INSERT
- **Bug**: If tuple contains ID but INSERT strips it, ID goes into `file` column

**A3. React Hook Alignment**
- `node_database.py` -> `add_react_hook`: Line 126 appends **8** items
- `node_schema.py` -> `REACT_HOOKS`: Has **8** columns
- **Status**: MATCHES (Verified)

### 2.2 CATEGORY B: The Import Resolution "Black Hole"

**Severity: CRITICAL (Silent Data Loss)**

TypeScript compiler resolves imports perfectly, but data never reaches Graph layer.

#### Chain of Failure:

1. **Schema Gap**: `core_schema.py` MISSING `resolved_imports` table definition
2. **Flush Gap**: `base_database.py` does NOT list `resolved_imports` in `flush_order`
3. **Storage Gap**: `core_storage.py` has NO handler mapped to `resolved_imports` key
4. **Graph Gap**: `builder.py` ignores database, guesses paths via string manipulation

### 2.3 CATEGORY C: The "Generic Batch" Blind Spot

**Severity: HIGH (Data Loss)**

**File**: `base_database.py` -> `flush_generic_batch` (Line 132)

**Issues**:
- Dynamically maps input tuples to table columns - extremely brittle
- If `flush_order` (Line 173) or schema changes, method silently fails or crashes
- `flush_order` is manually maintained (100+ tables)
- Missing tables never get flushed even if extractor adds them to batch

**Column Mismatch Behavior** (Line 153):
```python
if len(columns) != tuple_size:
    raise RuntimeError(f"Column mismatch for table '{table_name}'...")
```

### 2.4 CATEGORY D: Missing Database Methods

**Severity: HIGH (Crashes)**

#### D1. `node_database.py` Missing Methods:
| Method Needed | Called By | Status |
|---------------|-----------|--------|
| `add_react_component` | `node_storage.py` | MISSING - Causes AttributeError |
| `add_vue_component` | `node_storage.py` | MISSING |

#### D2. `core_database.py` Missing Methods:
| Method Needed | Purpose | Status |
|---------------|---------|--------|
| `add_resolved_import` | Store TS compiler resolutions | MISSING |

#### D3. `infrastructure_database.py` Missing Methods:
| Method Needed | Schema Exists | Status |
|---------------|---------------|--------|
| `add_dockerfile_port` | DOCKERFILE_PORTS defined | MISSING |
| `add_dockerfile_env` | DOCKERFILE_ENV defined | MISSING |

### 2.5 CATEGORY E: Storage Handler Gaps

**Severity: HIGH (Silent Data Loss)**

#### E1. `core_storage.py` Missing Handlers:
```python
# Missing from handlers map:
"resolved_imports": self._store_resolved_imports
```

#### E2. `node_storage.py` Missing Handlers:
```python
# Missing from handlers map:
"import_styles": self._store_import_styles
```
**Impact**: Import aliasing data (e.g., `import { sanitize as s }`) extracted but discarded, breaking sanitizer detection.

#### E3. `infrastructure_storage.py` Missing Handlers:
```python
# Missing from handlers map:
"docker_images": self._store_docker_images
"dockerfile_ports": self._store_dockerfile_ports
"compose_services": self._store_compose_services
```

### 2.6 CATEGORY F: CFG Flat Storage Logic

**File**: `node_storage.py` -> `_store_cfg_flat` (Lines 772+)

**Issue**: Reconstructs graph from flat list using composite keys.

```python
# Line 808
source_id = block_id_map.get((function_id, from_block))
target_id = block_id_map.get((function_id, to_block))

if source_id is None or target_id is None:
    continue  # PHASE 1 FIX: Use None as sentinel
```

**Refactor Risk**: If extractor changes `function_id` generation (e.g., separating file path differently), `rsplit(":", 2)` logic (lines 783, 801) fails. Windows paths with colons (`C:\...`) split incorrectly.

**Result**: Orphaned edges - blocks exist but no connections.

### 2.7 CATEGORY G: JSON Serialization Inconsistencies

**Risk Level: MEDIUM**

**node_database.py -> add_react_hook**:
- Manually dumps `deps_array_json` (Good)

**core_storage.py -> _store_symbols** (Line 245):
```python
parameters_json = json.dumps(symbol["parameters"])
```
**Risk**: If `symbol["parameters"]` is `None`, `json.dumps` returns `"null"` (string). Downstream must expect SQL NULL vs string `"null"`.

### 2.8 CATEGORY H: Schema Validation Weakness

**File**: `base_database.py`

```python
def validate_schema(self) -> bool:
    # ...
    print("[SCHEMA] Note: Some mismatches may be due to migration columns (expected)", file=sys.stderr)
```

**Issue**: Validation is SOFT. Prints warnings but returns `False`, allowing program to continue and potentially corrupt data.

**Recommendation**: Change to HARD FAIL if column counts don't match.

### 2.9 CATEGORY I: Transaction Nesting Crash

**File**: `store.py` (Graph Layer) - Line 46

```python
cursor.execute("BEGIN TRANSACTION")
```

**Risk**: Python's `sqlite3` module manages transactions automatically. Manual `BEGIN TRANSACTION` often throws:
```
sqlite3.OperationalError: cannot start a transaction within a transaction
```

**Fix**: Use `conn.commit()` strictly, or set `isolation_level=None` for manual management.

### 2.10 CATEGORY J: Schema Contract Time Bomb

**File**: `schema.py` - Line 22

```python
assert len(TABLES) == 170, f"Schema contract violation: Expected 170 tables, got {len(TABLES)}"
```

**Issue**: Hardcoded assertion. Adding ONE table crashes entire application on startup.

**Fix**: Remove assertion or check for MINIMUM required tables, not exact count.

### 2.11 CATEGORY K: Fidelity Check False Confidence

**File**: `fidelity.py` -> `reconcile_fidelity`

**Logic**: Compares `manifest` (from Extractor) vs `receipt` (from DataStorer).

**Bug**:
1. If extractor returns empty data due to bug, Python calculates "0 items found"
2. Compares to "0 items stored" -> Check PASSES
3. Data silently lost, fidelity confirms "consistency" not "correctness"

**Secondary Bug**: `flush_batch` executes deferred SQL. If flush fails AFTER fidelity check passes, check gave false positive.

### 2.12 CATEGORY L: Batch Error Handling

**File**: `base_database.py` -> `flush_batch`

```python
except sqlite3.IntegrityError as e:
    # ... checks for UNIQUE constraint ...
    if batch_idx is not None:
        raise RuntimeError(...)
```

**Issue**: `flush_batch` called at END of file processing loop. If batch 50 fails, indexer crashes, loses progress of current transaction (50 files).

**Fix**: Implement "Bad Record Isolation" - retry individual rows on batch failure.

### 2.13 CATEGORY M: The _noop Handlers

**File**: `node_storage.py`

```python
def _noop_cfg_edges(self, file_path: str, cfg_edges: list, jsx_pass: bool):
    pass

def _noop_cfg_block_statements(self, file_path: str, statements: list, jsx_pass: bool):
    pass
```

**Purpose**: Data stored via `_store_cfg_flat` which handles blocks, edges, statements together for ID referential integrity.

**Risk**: If orchestrator changes to output `cfg_edges` independently, data silently dropped because handler is no-op.

---

## Part 3: Storage Layer Repair Plan

### Phase 1: Schema Fixes

**Step 1.1**: Update `core_schema.py` - Add missing table:
```python
RESOLVED_IMPORTS = TableSchema(
    name="resolved_imports",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("import_specifier", "TEXT", nullable=False),
        Column("resolved_path", "TEXT", nullable=False),
        Column("package_name", "TEXT"),
        Column("is_external", "BOOLEAN", default="0"),
    ],
    primary_key=["file", "import_specifier"],
    indexes=[
        ("idx_resolved_imports_file", ["file"]),
        ("idx_resolved_imports_pkg", ["package_name"]),
    ],
)

# Add to CORE_TABLES
CORE_TABLES = {
    # ... existing ...
    "resolved_imports": RESOLVED_IMPORTS,
}
```

**Step 1.2**: Update `schema.py` - Remove assertion:
```python
# DELETE THIS LINE:
# assert len(TABLES) == 170, f"Schema contract violation..."
```

### Phase 2: Database Manager Fixes

**Step 2.1**: Update `base_database.py` - Add to `flush_order`:
```python
flush_order = [
    # ... existing tables ...
    ("resolved_imports", "INSERT OR REPLACE"),
    # ...
]
```

**Step 2.2**: Update `base_database.py` - Implement Safe Flush:
```python
def flush_generic_batch(self, table_name: str, insert_mode: str = "INSERT") -> None:
    # ... setup code ...
    try:
        cursor.executemany(query, batch)
    except sqlite3.Error as e:
        self.conn.rollback()
        print(f"[DB] Batch failed for {table_name}. Retrying row-by-row...", file=sys.stderr)

        for row in batch:
            try:
                cursor.execute(query, row)
            except sqlite3.Error:
                pass  # Log bad row, keep going
        self.conn.commit()
    finally:
        self.generic_batches[table_name] = []
```

**Step 2.3**: Update `core_database.py` - Add missing method:
```python
def add_resolved_import(self, file_path: str, import_specifier: str, resolved_path: str):
    """Add a resolved import mapping to the batch."""
    self.generic_batches["resolved_imports"].append(
        (file_path, import_specifier, resolved_path)
    )
```

**Step 2.4**: Update `core_database.py` - Fix `add_symbol`:
```python
# Add is_typed (default 0) to tuple - currently missing
# Must match SYMBOLS schema column count (9)
```

**Step 2.5**: Update `node_database.py` - Add missing methods:
```python
def add_react_component(self, file_path: str, ...):
    """Add React component to batch."""
    self.generic_batches["react_components"].append(...)

def add_vue_component(self, file_path: str, ...):
    """Add Vue component to batch."""
    self.generic_batches["vue_components"].append(...)
```

**Step 2.6**: Update `infrastructure_database.py` - Add missing methods:
```python
def add_dockerfile_port(self, file_path: str, port: int, protocol: str):
    self.generic_batches["dockerfile_ports"].append((file_path, port, protocol))
```

### Phase 3: Storage Handler Fixes

**Step 3.1**: Update `core_storage.py` - Add handler:
```python
# In __init__
self.handlers = {
    # ... existing handlers ...
    "resolved_imports": self._store_resolved_imports,
}

def _store_resolved_imports(self, file_path: str, resolved: dict, jsx_pass: bool):
    for specifier, path in resolved.items():
        self.db_manager.add_resolved_import(file_path, specifier, path)
    self.counts["resolved_imports"] += len(resolved)
```

**Step 3.2**: Update `node_storage.py` - Add handler:
```python
# In __init__
self.handlers = {
    # ... existing handlers ...
    "import_styles": self._store_import_styles,
}
```

**Step 3.3**: Update `infrastructure_storage.py` - Add handlers:
```python
# In __init__
self.handlers = {
    # ... existing handlers ...
    "docker_images": self._store_docker_images,
    "dockerfile_ports": self._store_dockerfile_ports,
    "compose_services": self._store_compose_services,
}
```

### Phase 4: JSON Safety

**Step 4.1**: Add JSON safety wrapper to `node_database.py`:
```python
def safe_json_dumps(obj):
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return json.dumps(str(obj))  # Fallback to string representation

# Usage:
deps_array_json = safe_json_dumps(dependency_array) if dependency_array else None
```

---

## Part 4: Verification Checklist

### Pre-Implementation Hypotheses

| ID | Hypothesis | Verification Method |
|----|------------|---------------------|
| H1 | `resolved_imports` table does not exist | Query `sqlite_master` |
| H2 | `add_symbol` tuple has 8 items, schema has 9 | Count columns in both |
| H3 | `flush_order` missing `resolved_imports` | Read `base_database.py` L173+ |
| H4 | `node_storage.py` missing `import_styles` handler | Read `handlers` dict |
| H5 | `node_database.py` missing `add_react_component` | Grep for method def |
| H6 | Schema assertion will fail if tables added | Read `schema.py` L22 |

### Post-Implementation Tests

1. Run `aud full --index` - should complete without crashes
2. Query `SELECT COUNT(*) FROM resolved_imports` - should have rows
3. Query `SELECT COUNT(*) FROM import_styles` - should have rows
4. Verify no `AttributeError` on React file processing
5. Verify no `Column mismatch` RuntimeErrors

---

## Part 5: Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Schema migration corrupts existing data | HIGH | MEDIUM | Backup `.pf/` before changes |
| Tuple alignment still wrong after fix | HIGH | LOW | Automated column count tests |
| Handler registration missed | MEDIUM | MEDIUM | Integration test coverage |
| Transaction nesting in store.py | MEDIUM | HIGH | Remove manual BEGIN |

---

## Part 6: Execution Order

**CRITICAL**: Fix in this order - earlier phases block later ones.

1. **Schema Fixes** (Phase 1) - Table must exist before anything else
2. **Database Manager** (Phase 2) - Methods must exist before Storage calls them
3. **Storage Handlers** (Phase 3) - Wiring between Extractor output and DB methods
4. **JSON Safety** (Phase 4) - Prevent crash on malformed data
5. **Migration** - Delete `.pf/graphs.db`, run `aud full --index`

---

## Appendix A: File Locations

```
theauditor/indexer/
    database/
        base_database.py      # flush_generic_batch, flush_order
        core_database.py      # add_symbol, add_assignment
        node_database.py      # add_react_hook (missing add_react_component)
        infrastructure_database.py
    storage/
        core_storage.py       # handlers map (missing resolved_imports)
        node_storage.py       # _store_cfg_flat, handlers map
        infrastructure_storage.py
    schemas/
        core_schema.py        # SYMBOLS, (missing RESOLVED_IMPORTS)
        node_schema.py        # REACT_HOOKS, REACT_COMPONENTS
        infrastructure_schema.py
    schema.py                 # TABLES aggregation, assertion
    fidelity.py               # reconcile_fidelity
    orchestrator.py           # index() main loop
```

---

## Appendix B: Related Integration Issues

The Storage Layer bugs cascade into:

1. **Graph Layer** (`builder.py`) - Can't resolve imports because data never saved
2. **Taint Layer** (`sanitizer_util.py`) - Can't detect sanitizers from `symbols` table
3. **Discovery** (`discovery.py`) - Misses sinks stored as generic symbols

These downstream issues are documented separately. Fixing Storage Layer is prerequisite.

---

*Document generated as part of TheAuditor Large-Scale Refactor Audit*
*Prime Directive: Verify Before Acting - All claims require code evidence*
