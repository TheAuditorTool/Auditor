# TheAuditor Indexer + Fidelity System

## Overview

The indexer is a sophisticated multi-language code analysis system that extracts semantic information from source code into a transactionally-safe SQLite database. It processes 7+ languages using a unified extraction and storage pipeline with **built-in data integrity verification**.

**Key Stats:**
- ~2,000 lines across orchestrator, core, and storage
- 70+ database tables spanning 10 schema modules
- 8 domain-specific storage handlers
- Polymorphic fidelity system supporting both list and dict extraction formats

---

## The "Holy Trio" Fidelity System

### 1. Manifest Generation (`fidelity_utils.py`)

Every extraction creates a manifest token capturing:
- `count`: Number of items extracted
- `tx_id`: UUID for transactional integrity
- `columns`: Sorted column names (schema verification)
- `bytes`: Approximate byte size of data

```python
token = {
    "count": len(data),
    "tx_id": str(uuid.uuid4()),
    "columns": sorted(first_row.keys()),
    "bytes": sum(len(str(v)) for row in data for v in row.values()),
}
```

### 2. Receipt Generation (DataStorer)

For each data type processed, storage creates a receipt echoing back manifest tx_id:
```python
receipt[data_type] = FidelityToken.create_receipt(
    count=len(data),
    columns=sorted(data[0].keys()),
    tx_id=tx_id,
    data_bytes=sum(...)
)
```

### 3. Reconciliation (`fidelity.py`)

Compares manifest (what extractor found) vs receipt (what storage saved):

**Error Conditions (STRICT MODE):**
- Transaction Mismatch: `m_tx != r_tx` → Pipeline cross-talk
- Schema Violation: dropped columns
- 100% Data Loss: `m_count > 0 && r_count == 0`

---

## Architecture

### Three-Layer Stack

**Layer 1: Orchestration** (`orchestrator.py`)
- Coordinates entire indexing workflow
- Manages file discovery, AST parsing, extractor selection
- Two-pass JSX system (standard + preserved)

**Layer 2: Storage Orchestration** (`storage/__init__.py`)
- Aggregates 7 domain-specific handler modules
- Implements PRIORITY_ORDER for parent-before-child processing
- Attaches fidelity manifests to extraction results

**Layer 3: Domain-Specific Handlers**
- `CoreStorage`: Language-agnostic (imports, routes, SQL, symbols)
- `PythonStorage`: Django, FastAPI, SQLAlchemy, decorators
- `NodeStorage`: React hooks, Angular, Sequelize, Vue.js
- `RustStorage`: Modules, traits, async/await, lifetimes
- `GoStorage`: Goroutines, channels, error handling
- `BashStorage`: Variables, commands, control flow
- `InfrastructureStorage`: Docker, Compose, Terraform, CDK

---

## Transaction & Rollback Safety

### WAL Mode + Batch Transactions
```python
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA foreign_keys = ON")
```

### Gatekeeper Pattern (FK Validation)
```python
if construct_id not in self._valid_construct_ids:
    logger.warning(f"GATEKEEPER: Skipping orphaned property...")
    continue
```

### Rollback on Error
```python
def commit(self) -> None:
    try:
        self.conn.commit()
    except sqlite3.Error as e:
        self.conn.rollback()
        raise
```

---

## Performance Optimizations

1. **Batch JS/TS Parsing**: 50 files per Node.js invocation
2. **AST Caching**: SHA256-keyed cache in `.pf/.cache/`
3. **Schema-Driven Batch Flush**: Generic INSERT for 70+ tables
4. **Monorepo Detection**: Early detection prevents scanning irrelevant directories

---

## Key Design Decisions

1. **Zero-Fallback Policy**: No retry logic on FK violations, fidelity errors are FATAL
2. **Manifest-Receipt Pairing**: Every extraction paired with receipt for verification
3. **Two-Pass JSX System**: Separate `_jsx` tables for preserved syntax
4. **Domain-Specific Storage Modules**: Each language gets dedicated handler
5. **Schema Validation on Startup**: Auto-regenerates if YAML definitions change
