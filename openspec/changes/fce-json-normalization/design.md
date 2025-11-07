# FCE JSON Normalization Design

**Status**: 🔴 DRAFT

---

## 1. Normalized Table Design

### 1.1 finding_taint_paths (CRITICAL - 50-500ms bottleneck)

```sql
CREATE TABLE finding_taint_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT NOT NULL,
    path_index INTEGER NOT NULL,  -- Preserves order
    source_file TEXT,
    source_line INTEGER,
    source_expr TEXT,
    sink_file TEXT,
    sink_line INTEGER,
    sink_expr TEXT,
    path_length INTEGER,
    confidence REAL,
    FOREIGN KEY (finding_id) REFERENCES findings_consolidated(id) ON DELETE CASCADE
);
CREATE INDEX idx_finding_taint_paths_finding_id ON finding_taint_paths(finding_id);
CREATE INDEX idx_finding_taint_paths_composite ON finding_taint_paths(finding_id, path_index);
```

**Rationale**:
- Taint paths are 50-500ms bottleneck (100-10K paths at 1KB+ each)
- Indexed lookup is O(1) instead of JSON parsing O(n)
- `path_index` preserves ordering (critical for display)

### 1.2 symbol_parameters

```sql
CREATE TABLE symbol_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol_id TEXT NOT NULL,
    param_index INTEGER NOT NULL,
    param_name TEXT,
    param_type TEXT,
    default_value TEXT,
    is_optional INTEGER,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
);
```

**Rationale**: Follows d8370a7 junction table pattern (AUTOINCREMENT + composite index)

---

## 2. Query Performance Comparison

### Before (JSON parsing)
```python
details = json.loads(details_json)  # 50-500ms for taint paths
taint_paths = details.get('paths', [])
```

### After (Indexed JOIN)
```python
cursor.execute("""
    SELECT * FROM finding_taint_paths
    WHERE finding_id = ?
    ORDER BY path_index
""", (finding_id,))
taint_paths = cursor.fetchall()  # <1ms
```

**Speedup**: 50-500ms → <1ms (50-500x faster)

---

## 3. Schema Validator Design

```python
def _detect_json_blobs(tables):
    violations = []
    LEGITIMATE_EXCEPTIONS = {
        ('nodes', 'metadata'),       # graphs.db intentional
        ('edges', 'metadata'),       # graphs.db intentional
        ('plan_documents', 'document_json'),  # Planning system
    }
    for table in tables:
        for col in table.columns:
            if col.type == "TEXT" and col.name.endswith(('_json', 'dependencies', 'parameters')):
                if (table.name, col.name) not in LEGITIMATE_EXCEPTIONS:
                    violations.append((table.name, col.name))
    return violations
```

**Triggers**: At schema load time (prevents violations before they spread)

---

## 4. Commit d8370a7 Reversal

**Original Decision** (Oct 23, 2025): Exempted `findings_consolidated.details_json` as "Intentional"

**New Decision**: REVERSE exemption based on measured overhead (75-700ms)

**Lesson**: Performance measurements > assumptions. JSON blobs are always cancer.
