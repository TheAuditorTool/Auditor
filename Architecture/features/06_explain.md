# TheAuditor Explain Command

## Overview

The **EXPLAIN** command provides a comprehensive "briefing packet" for any code target (file, symbol, or component) in a single operation. It eliminates the need to run 5-6 separate queries and automatically returns relevant context optimized for AI workflows.

### Key Characteristics
- **Single Command**: Replaces multiple query commands
- **Auto-Detection**: Automatically detects file vs symbol vs component
- **Deterministic Context**: Provides ground truth facts, saving 5,000-10,000 context tokens per task
- **Fast**: <100ms for files with <50 symbols
- **Database-First**: No file re-parsing

---

## Target Type Detection

```
1. Check for known file extensions → TYPE = "file"
2. Check for path separators (/ or \) → TYPE = "file"
3. Check for PascalCase.method pattern → TYPE = "symbol"
4. Check if in react_components table → TYPE = "component"
5. Default → TYPE = "symbol"
```

### Examples
```bash
aud explain src/auth.ts           # FILE
aud explain authenticateUser      # SYMBOL
aud explain User.create           # SYMBOL
aud explain Dashboard             # COMPONENT
```

---

## Context Bundles

### For FILE Targets

```python
{
    "target": "path/to/file.ts",
    "target_type": "file",
    "symbols": [...],           # Defined functions/classes
    "hooks": [...],             # React/Vue hooks used
    "imports": [...],           # Dependencies (outgoing)
    "importers": [...],         # Dependents (incoming)
    "outgoing_calls": [...],    # Function calls made
    "incoming_calls": [...],    # Calls to this file's symbols
    "framework_info": {...}     # Routes, middleware, models
}
```

### For SYMBOL Targets

```python
{
    "target": "authenticateUser",
    "resolved_as": ["UserService.authenticateUser"],
    "target_type": "symbol",
    "definition": {...},        # File, line, signature
    "callers": [...],           # Who calls this
    "callees": [...]            # What this calls
}
```

### For COMPONENT Targets

```python
{
    "target": "Dashboard",
    "target_type": "component",
    "name": "Dashboard",
    "type": "functional",
    "file": "src/components/Dashboard.tsx",
    "hooks": ["useState", "useEffect"],
    "children": [...]           # Child components
}
```

---

## CLI Usage

```bash
# Explain a file
aud explain src/auth/service.ts

# Explain a symbol
aud explain authenticateUser

# JSON format for AI
aud explain Dashboard --format json

# Suppress code snippets
aud explain src/auth.ts --no-code

# Limit output size
aud explain utils/helpers.py --limit 10

# Show specific section only
aud explain src/auth.ts --section symbols
aud explain src/auth.ts --section callers

# Control call graph depth
aud explain authenticateUser --depth 3

# Include FCE signal analysis
aud explain src/auth.ts --fce
```

---

## Output Formats

### Text Mode (Default)
```
================================================================================
EXPLAIN: src/auth/service.ts
================================================================================

SYMBOLS DEFINED (5):
  1. authenticate (function) - line 42-58
      async authenticate(user: User): Promise<Token>

DEPENDENCIES (3 imports):
  1. ./utils/crypto.py (internal) - line 5

INCOMING CALLS (3):
  1. src/api/login.ts:15 - loginHandler() calls authenticate

================================================================================
```

### JSON Mode
Machine-readable output with full context bundle structure.

---

## Database vs File Re-reading

**Primary Source**: SQLite databases in `.pf/`
- `repo_index.db` - Symbols, calls, imports
- `graphs.db` - Dependency graph

**Fallback to Disk**: Code snippets only
- Uses `CodeSnippetManager` with LRU cache
- Max 20 files, 1MB size limit

---

## Symbol Resolution Strategy

```sql
-- Priority 1: Exact match
SELECT name FROM symbols WHERE name = ?

-- Priority 2: Suffix match
SELECT name FROM symbols WHERE name LIKE '%.input_name'

-- Priority 3: Last segment match
SELECT name FROM symbols WHERE name LIKE '%.last_segment'

-- If no matches: Suggest similar names
SELECT name FROM symbols WHERE name LIKE '%input_name%'
```

---

## Integration with CodeQueryEngine

The EXPLAIN command uses `CodeQueryEngine` methods:

```python
# File-level context
engine.get_file_context_bundle(file_path, limit)

# Symbol-level context
engine.get_symbol_context_bundle(symbol_name, limit, depth)

# Component-level context
engine.get_component_tree(component_name)
```
