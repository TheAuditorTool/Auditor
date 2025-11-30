# STORAGE.md - Pre-Implementation Plan

> **Document Version:** 1.0
> **Last Updated:** 2025-12-01
> **Status:** Pre-Implementation Analysis
> **Compliance:** teamsop.md v4.20

---

## Executive Summary

This document consolidates ALL storage-related findings from the comprehensive system audit (issue.md, issue2.md, issue3.md, issue4.md). The storage layer is the **critical bridge** between Extractors (data producers) and Graph/Taint engines (data consumers). Current state: **systematically broken** due to schema drift, missing handlers, and tuple alignment failures.

---

## Part 1: Architecture Overview

### 1.1 The Storage Flow

```
Extractor (TS/Python) --> Storage Layer --> Database Manager --> SQLite DB
                              |
                              v
                     Schema Validation
```

**Three-Layer Design:**
1. **Schema (`*_schema.py`)**: Defines table structures (columns, types, indexes)
2. **Storage (`*_storage.py`)**: Receives raw data, normalizes it, routes to handlers
3. **Database Manager (`*_database.py`)**: Batches records, performs bulk INSERTs

### 1.2 Database Files

| Database | Location | Purpose |
|----------|----------|---------|
| `repo_index.db` | `.pf/repo_index.db` | Raw extracted facts from AST parsing |
| `graphs.db` | `.pf/graphs.db` | Pre-computed graph structures |

**Key Insight:** FCE reads from `repo_index.db`, NOT `graphs.db`. Graph database is optional for visualization only.

---

## Part 2: Critical Storage Bugs

### 2.1 The "Tuple Alignment" Risk (CRITICAL)

**Location:** All `*_database.py` files
**Impact:** Data written to wrong columns OR immediate crash

The system relies on `base_database.py` -> `flush_generic_batch` to map tuples directly to SQL columns. The `add_*` methods MUST match the exact order and count of TableSchema definitions.

**Confirmed Mismatches:**

| Method | Schema | Tuple Size | Status |
|--------|--------|------------|--------|
| `add_symbol` (core_database.py:47) | SYMBOLS (9 cols) | 8 items | **MISMATCH** - missing `is_typed` |
| `add_cfg_block_jsx` (core_database.py:175) | CFG_BLOCKS_JSX (9 cols) | 9 items with temp_id | **RISK** - ID handling |
| `add_react_hook` (node_database.py:126) | REACT_HOOKS (8 cols) | 8 items | OK |

**Fix Required:**
```python
# core_database.py -> add_symbol
# Must include is_typed (default 0) as 9th element in tuple
```

### 2.2 Missing Handler Registration (SILENT DATA LOSS)

**Location:** `*_storage.py` files
**Impact:** Extracted data silently dropped

When a storage class receives data for a key without a registered handler, the data is **silently ignored**.

**Confirmed Missing Handlers:**

| Storage Class | Missing Handler | Source Key |
|--------------|-----------------|------------|
| `core_storage.py` | `_store_resolved_imports` | `resolved_imports` |
| `node_storage.py` | `_store_import_styles` | `import_styles` |
| `infrastructure_storage.py` | Docker handlers | `docker_images`, `dockerfile_ports` |

**Fix Required:**
```python
# In core_storage.py __init__
self.handlers = {
    # ... existing ...
    "resolved_imports": self._store_resolved_imports,  # ADD THIS
}
```

### 2.3 Missing Database Methods (CRASH)

**Location:** `*_database.py` mixin files
**Impact:** AttributeError crash at runtime

Storage handlers call database methods that don't exist in the corresponding mixin.

**Confirmed Missing Methods:**

| Storage Calls | Expected In | Status |
|--------------|-------------|--------|
| `add_react_component` | `node_database.py` | **MISSING** |
| `add_resolved_import` | `core_database.py` | **MISSING** |
| `add_terraform_file` | `infrastructure_database.py` | **MISSING** |
| `add_dockerfile_port` | `infrastructure_database.py` | **MISSING** |

### 2.4 Missing Schema Table Definitions

**Location:** `theauditor/indexer/schemas/*_schema.py`
**Impact:** ValueError or silent data drop

**Confirmed Missing Tables:**

| Table Name | Should Be In | Used By |
|------------|--------------|---------|
| `resolved_imports` | `core_schema.py` | Graph resolution |
| `function_call_args_detailed` | `core_schema.py` | Detailed call tracking |

**Fix Required:**
```python
# In core_schema.py
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
```

### 2.5 The `flush_order` Omission

**Location:** `base_database.py` -> `flush_batch`
**Impact:** Data never written to disk

The `flush_order` list determines which batches get flushed. If a table is not in this list, its data is never persisted.

**Confirmed Missing from flush_order:**
- `resolved_imports`
- `function_call_args_detailed`

---

## Part 3: Storage Layer Fragility

### 3.1 Schema Contract Time Bomb

**Location:** `schema.py:22`
```python
assert len(TABLES) == 170, f"Schema contract violation..."
```

**Risk:** Adding ANY new table crashes the entire application on startup.
**Fix:** Remove assertion or check for minimum required tables only.

### 3.2 The "Silent Swallow" of Batch Errors

**Location:** `base_database.py` -> `flush_batch`
**Impact:** Transaction rollback loses 50+ files of data

When `flush_batch` fails (e.g., integrity error), the entire batch is lost. No row-by-row fallback exists.

**Recommended Fix:**
```python
def flush_generic_batch(self, table_name: str, insert_mode: str = "INSERT") -> None:
    try:
        cursor.executemany(query, batch)
    except sqlite3.Error as e:
        self.conn.rollback()
        print(f"[DB] Batch failed for {table_name}. Retrying row-by-row...", file=sys.stderr)
        for row in batch:
            try:
                cursor.execute(query, row)
            except sqlite3.Error:
                pass  # Log and skip bad row
        self.conn.commit()
```

### 3.3 Database Caching Mutability Bug

**Location:** `db_cache.py`
**Impact:** Non-deterministic bugs across graph build runs

```python
@lru_cache(maxsize=IMPORTS_CACHE_SIZE)
def get_imports(self, file_path: str) -> tuple[dict[str, Any], ...]:
    # Returns tuple of dicts - dicts are MUTABLE
```

**Risk:** If any consumer modifies the returned dict, the modification persists in cache.
**Fix:** Return frozen dataclasses or deepcopy on access.

### 3.4 Path Normalization Inconsistencies

**Location:** `builder.py`, `store.py`
**Impact:** Ghost nodes (duplicates with different slash directions)

- `store.py` deletes nodes using `DELETE ... WHERE file = ?`
- `builder.py` uses `str(Path(x).relative_to(y))`
- Windows uses backslashes, Unix uses forward slashes
- `.replace("\\", "/")` applied inconsistently

**Result:** Incremental builds fail to clean up old nodes.

### 3.5 SQLite Variable Limit Crash

**Location:** `python_orm.py`
**Impact:** Crash on projects with >250 models

```python
placeholders = ",".join("?" * len(model_patterns))
cursor.execute(f"... WHERE target_var IN ({placeholders})", list(model_patterns))
```

SQLite default limit: 999 variables. Large projects exceed this.

**Fix:** Batch queries in chunks of 500:
```python
chunk_size = 500
for i in range(0, len(patterns_list), chunk_size):
    chunk = patterns_list[i:i + chunk_size]
    placeholders = ",".join("?" * len(chunk))
    cursor.execute(query, chunk)
```

### 3.6 Transaction Nesting Bug

**Location:** `store.py:46`
```python
cursor.execute("BEGIN TRANSACTION")
```

**Risk:** SQLite throws `OperationalError: cannot start a transaction within a transaction`.
**Fix:** Use `conn.commit()` strictly or set `isolation_level=None`.

---

## Part 4: The _noop Handlers Risk

**Location:** `node_storage.py`

```python
def _noop_cfg_edges(self, file_path: str, cfg_edges: list, jsx_pass: bool):
    pass

def _noop_cfg_block_statements(self, ...):
    pass
```

**Purpose:** CFG edges/statements are stored via `_store_cfg_flat` which handles them atomically.

**Risk:** If orchestrator changes to output `cfg_edges` independently, data is silently dropped.

---

## Part 5: Fidelity System Weaknesses

### 5.1 False Positive Confidence

**Location:** `fidelity.py` -> `reconcile_fidelity`

**The Bug:**
1. `result['functions']` is empty (key mismatch)
2. `manifest['functions']` calculated as 0
3. Fidelity compares "Extracted 0" vs "Stored 0" = **PASS**

**Reality:** Data was lost, but fidelity reports success.

**Fix:** Manifest should come from TypeScript extractor (source of truth), not Python post-processing.

### 5.2 Deferred Execution Gap

Fidelity checks pass BEFORE `flush_batch` executes. If `flush_batch` fails after fidelity passes, data is lost but check reported OK.

---

## Part 6: JSON Serialization Risks

### 6.1 React Hook Data Corruption

**Location:** `node_database.py` -> `add_react_hook`
```python
deps_array_json = json.dumps(dependency_array) if dependency_array is not None else None
```

**Risk:** If `dependency_array` contains non-serializable objects (e.g., circular references), the entire batch fails.

**Fix:**
```python
def safe_json_dumps(obj):
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return json.dumps(str(obj))
```

### 6.2 Inconsistent NULL Handling

**Location:** `core_storage.py:245`
```python
parameters_json = json.dumps(symbol["parameters"])
```

If `symbol["parameters"]` is `None`, `json.dumps` returns `"null"` (string).
Schema expects SQL `NULL` or string `"null"` - downstream consumers may not handle both.

---

## Part 7: Implementation Priority

### Phase 1: Stop the Crashes (IMMEDIATE)

1. **`core_database.py`**: Update `add_symbol` to include `is_typed` (9th element)
2. **`node_database.py`**: Add missing `add_react_component` method
3. **`schema.py`**: Comment out `assert len(TABLES) == 170`
4. **`infrastructure_database.py`**: Add `add_terraform_file` method

### Phase 2: Restore Data Flow (HIGH)

1. **`core_schema.py`**: Add `RESOLVED_IMPORTS` table definition
2. **`base_database.py`**: Add `resolved_imports` to `flush_order`
3. **`core_database.py`**: Add `add_resolved_import` method
4. **`core_storage.py`**: Register `resolved_imports` handler
5. **`node_storage.py`**: Add `_store_import_styles` handler

### Phase 3: Harden Against Failures (MEDIUM)

1. **`base_database.py`**: Implement "Safe Flush" with row-by-row fallback
2. **`db_cache.py`**: Return immutable structures from cache
3. **Path normalization**: Enforce forward slashes at entry points
4. **`python_orm.py`**: Batch SQLite queries in chunks of 500

### Phase 4: Schema Alignment Verification (ONGOING)

Run automated checks comparing:
- `add_*` method argument counts vs `TableSchema` column counts
- Handler registration vs extractor output keys
- `flush_order` coverage vs all defined tables

---

## Part 8: File-by-File Action Items

### `base_database.py`
- [ ] Add `resolved_imports` to `flush_order`
- [ ] Implement Safe Flush row-by-row fallback
- [ ] Add column count validation on startup

### `core_database.py`
- [ ] Fix `add_symbol` to include `is_typed`
- [ ] Add `add_resolved_import` method

### `core_storage.py`
- [ ] Add `resolved_imports` handler to `handlers` dict
- [ ] Implement `_store_resolved_imports` method

### `core_schema.py`
- [ ] Add `RESOLVED_IMPORTS` table definition
- [ ] Add to `CORE_TABLES` dictionary

### `node_database.py`
- [ ] Add `add_react_component` method
- [ ] Verify all `add_*` methods match schema column counts

### `node_storage.py`
- [ ] Add `import_styles` handler
- [ ] Implement `_store_import_styles` method

### `infrastructure_database.py`
- [ ] Add `add_terraform_file` method
- [ ] Add `add_dockerfile_port` method
- [ ] Add `add_dockerfile_env_var` method

### `infrastructure_storage.py`
- [ ] Add Docker handlers to `handlers` dict

### `schema.py`
- [ ] Remove or update `assert len(TABLES) == 170`

### `db_cache.py`
- [ ] Return immutable/frozen structures from cached methods

### `store.py` (Graph Layer)
- [ ] Remove manual `BEGIN TRANSACTION` calls
- [ ] Use connection context manager properly

### `python_orm.py`
- [ ] Add `from __future__ import annotations` at line 1
- [ ] Batch SQLite queries to avoid 999 variable limit

---

## Part 9: Verification Protocol

Before implementation, verify each fix by:

1. **Hypothesis:** State what you expect to be broken
2. **Read Code:** Confirm the actual state matches hypothesis
3. **Implement Fix:** Apply the specific change
4. **Post-Audit:** Re-read modified file to confirm correctness
5. **Test:** Run `aud full --index` and check for crashes/warnings

---

## Part 10: Risk Assessment

| Risk | Severity | Likelihood | Current Status |
|------|----------|------------|----------------|
| Tuple misalignment crash | CRITICAL | HIGH | Confirmed in `add_symbol` |
| Silent data loss (missing handlers) | HIGH | HIGH | Confirmed for `resolved_imports` |
| Schema assertion crash | MEDIUM | HIGH | Will crash on table count change |
| Batch failure data loss | MEDIUM | MEDIUM | No row-by-row fallback |
| SQLite variable limit crash | MEDIUM | LOW | Only affects large projects |
| Cache mutation bugs | LOW | MEDIUM | Non-deterministic behavior |

---

## Appendix A: Storage Layer Class Hierarchy

```
BaseDatabaseManager
    |
    +-- CoreDatabaseMixin
    +-- NodeDatabaseMixin
    +-- PythonDatabaseMixin
    +-- InfrastructureDatabaseMixin
    +-- FrameworksDatabaseMixin
    |
    v
DatabaseManager (composition of all mixins)
    |
    v
DataStorer (routes data to storage handlers)
    |
    +-- CoreStorage
    +-- NodeStorage
    +-- PythonStorage
    +-- InfrastructureStorage
```

---

## Appendix B: Table Count by Domain

| Domain | Table Count | Key Tables |
|--------|-------------|------------|
| Core | 24 | symbols, files, imports, function_call_args |
| Python | 35 | python_functions, python_classes, decorators |
| Node | 37 | react_hooks, vue_components, express_middleware |
| Security | ~20 | sql_queries, resolved_flow_paths, env_var_usage |
| Infrastructure | ~15 | docker_images, terraform_resources |
| GraphQL | ~10 | graphql_resolvers, graphql_types |
| Planning | ~5 | analysis_results, metadata |

**Total:** ~144-170 tables (varies by configuration)

---

**Document End**

*This document serves as the authoritative pre-implementation reference for all storage layer fixes. All modifications must follow the teamsop.md Prime Directive: Verify Before Acting.*
