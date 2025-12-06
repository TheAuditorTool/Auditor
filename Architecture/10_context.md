# TheAuditor Context & Query System

## Overview

A **database-first approach** to code navigation. Instead of re-reading files, the system queries indexed relationships through SQLite.

**Key Components:**
- **CodeQueryEngine**: Direct SQL queries against repo_index.db + graphs.db
- **Explain Command**: High-level briefing packets
- **Dead Code Detection**: Graph-based reachability analysis
- **Semantic Context**: Business logic classification layer

---

## CodeQueryEngine

### Database Architecture
```python
repo_db = sqlite3.connect(".pf/repo_index.db")   # Raw facts (181MB)
graph_db = sqlite3.connect(".pf/graphs.db")       # Pre-computed graphs (126MB)
```

### Key Methods

**Symbol Resolution:**
```python
def _resolve_symbol(self, name: str) -> list[str]:
    # Priority 1: Exact match
    # Priority 2: Suffix match (*.name)
    # Priority 3: Last segment match
    # Returns helpful "Did you mean?" on no match
```

**Call Tracing (Recursive CTE):**
```sql
WITH RECURSIVE caller_graph AS (
    SELECT ... FROM function_call_args
    WHERE callee_function IN (targets)

    UNION ALL

    SELECT ... FROM function_call_args
    JOIN caller_graph ON ...
    WHERE depth < depth_limit
)
```

**Variable Flow:**
- BFS through assignments table
- Tracks def-use chains
- Depth-limited to 5 levels

### Context Bundles

**File Context:**
```python
def get_file_context_bundle(file_path):
    return {
        "symbols": get_file_symbols(file_path),
        "hooks": get_file_hooks(file_path),
        "imports": get_file_imports(file_path),
        "importers": get_file_importers(file_path),
        "outgoing_calls": get_file_outgoing_calls(file_path),
        "incoming_calls": get_file_incoming_calls(file_path),
        "framework_info": get_file_framework_info(file_path),
    }
```

**Symbol Context:**
```python
def get_symbol_context_bundle(symbol_name, depth=2):
    return {
        "definition": find_symbol(symbol_name),
        "callers": get_callers(symbol_name, depth),
        "callees": get_callees(symbol_name),
    }
```

---

## Dead Code Detection

### Three Detection Methods

**1. Isolated Modules**
- Graph-based reachability from entry points
- Entry points: `__main__.py`, `cli.py`, `index.ts`, framework patterns
- Confidence: HIGH (never imported), MEDIUM (migration script), LOW (init)

**2. Dead Symbols**
- Defined but never called within live modules
- Confidence: HIGH (never called), MEDIUM (private `_name`), LOW (test_*, __init__)

**3. Ghost Imports**
- Imported but never used
- Cross-database: graphs.db imports vs repo_index.db calls

### Implementation
```sql
WITH RECURSIVE reachable(file_path) AS (
    SELECT source FROM edges WHERE source IN (entry_points)
    UNION ALL
    SELECT e.target FROM edges e
    JOIN reachable r ON e.source = r.file_path
)
-- Dead modules = all_nodes - reachable
```

---

## Explain System

### Target Type Detection
```python
def detect_target_type(target):
    # 1. Known extension → file
    # 2. Path separator → file
    # 3. PascalCase.method → symbol
    # 4. PascalCase in react_components → component
    # 5. Default → symbol
```

### Output Aggregation

**For Files:**
- Symbols defined, hooks used
- Dependencies (imports), dependents (importers)
- Outgoing/incoming calls
- Framework info (routes, middleware, models)

**For Symbols:**
- Definition (file:line, type, signature)
- Callers (transitive depth 1-5)
- Callees (direct only)

**For Components:**
- Component metadata (name, type, props)
- Hooks used, child components

---

## Semantic Context

### Purpose
Apply business logic to classify findings:
- **Obsolete**: Old pattern, should migrate
- **Current**: Correct pattern in use
- **Transitional**: Temporarily allowed

### Pattern Matching
```python
@dataclass
class ContextPattern:
    id: str               # "jwt_deprecated"
    pattern: str          # Regex pattern
    reason: str           # Why this matters
    category: str         # obsolete | current | transitional
    severity: str | None
    replacement: str | None
    expires: str | None   # For transitional (YYYY-MM-DD)
```

### Migration Progress
```python
def get_migration_progress(self) -> dict:
    return {
        "total_files": ...,
        "files_need_migration": ...,
        "files_fully_migrated": ...,
        "migration_percentage": 100 * (migrated / total)
    }
```

---

## Query Command

```bash
# Symbol lookup
aud query --symbol validateUser --show-callers --depth 2

# File analysis
aud query --file src/auth.ts --show-dependents

# API endpoints
aud query --api "/users/:id"

# Component tree
aud query --component Dashboard --show-tree

# Variable flow
aud query --variable userId --show-flow --depth 3
```

---

## Key Principles

1. **Zero Fallback**: Hard fail if query wrong
2. **Database-First**: Never re-parse files
3. **Recursive CTEs**: Graph traversal in SQL, not Python
4. **Limits at SQL Level**: Performance enforced in database
5. **Error Messages Expose Fix**: "Did you mean?" suggestions
