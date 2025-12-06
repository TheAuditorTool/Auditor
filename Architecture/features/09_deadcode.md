# TheAuditor Dead Code Detection

## Overview

Dead code detection is far more sophisticated than naive "not imported" analysis. TheAuditor employs a **multi-layered graph-based approach** combining:

1. **Isolated Module Detection** - Files never imported anywhere
2. **Dead Symbol Detection** - Functions defined but never called
3. **Ghost Import Detection** - Imports present but never used

---

## Why Sophisticated Detection Matters

- **Naive approach**: Flags CLI entry points, test files, dynamic code as false positives
- **TheAuditor approach**: Uses graph reachability + entry point awareness + confidence scoring
- **Key insight**: A file is only truly dead if unreachable from ALL entry points

---

## Three Detection Methods

### 1. Isolated Module Detection

**What**: Modules with code that are never imported

**Algorithm**:
```
1. Build import graph from graphs.db
2. Identify entry points (CLI, tests, routes, components)
3. Compute reachability via SQL Recursive CTE
4. Dead = All nodes - Reachable - Excluded patterns
```

### 2. Dead Symbol Detection

**What**: Functions/classes defined in *live* modules but never called

**Algorithm**:
```
1. Filter to non-isolated modules
2. Build call graph
3. Query symbols table for definitions
4. Query function_call_args for actual calls
5. Dead = Defined - Called - Referenced
```

### 3. Ghost Import Detection

**What**: Imports that exist but are never used

**Algorithm**:
```
1. Get all import edges from graphs.db
2. Check if target file functions are ever called
3. Ghost = Imported but no function calls detected
```

---

## Confidence Levels

### HIGH Confidence
- Regular module with ≥1 symbol
- Never imported anywhere
- Not special file type (CLI, test, migration)

**Decision**: Safe to remove

### MEDIUM Confidence
- CLI entry point (`cli.py`, `main.py`)
- Test file (`test_*.py`, `*.spec.ts`)
- Migration script
- Private function (`_name`)

**Decision**: Manual review required

### LOW Confidence
- Empty `__init__.py`
- Generated code
- Magic methods (`__init__`, `__str__`)
- Type-hint-only imports

**Decision**: Likely false positive

---

## Entry Point Detection

TheAuditor identifies these as entry points (never dead):

1. **File Names**: `cli.py`, `main.py`, `__main__.py`, `index.ts`, `App.tsx`
2. **Test Files**: `test_*.py`, `*.test.js`, `*.spec.ts`
3. **Decorators**: `@route`, `@task`, `@command`
4. **Framework Components**: React/Vue components, routes
5. **Special Files**: `main.go`, `main.rs`, `lib.rs`

---

## CLI Usage

```bash
# Find all dead code
aud full && aud deadcode

# Analyze specific directory
aud deadcode --path-filter 'src/features/%'

# Export for review
aud deadcode --format json --save ./dead_code_report.json

# Strict CI/CD mode
aud deadcode --exclude test --fail-on-dead-code

# Summary statistics
aud deadcode --format summary
```

---

## Output Format

```
================================================================================
Dead Code Analysis Report
================================================================================
Total dead code items: 5

Isolated Modules (never imported):
--------------------------------------------------------------------------------
[HIGH] src/deprecated_feature.py
   Symbols: 15
   Confidence: HIGH
   Reason: No imports found

[MEDIUM] scripts/old_migration.py
   Symbols: 8
   Confidence: MEDIUM
   Reason: Migration script (may be external entry)
```

---

## False Positive Mitigation

### Strategy 1: Entry Point Awareness
Proactively identify CLI, test, route files before computing dead code.

### Strategy 2: Confidence Scoring
Three-tier system (HIGH/MEDIUM/LOW) for actionable review.

### Strategy 3: Zombie Clustering
Group related dead files into connected components.

### Strategy 4: Ghost Import Intelligence
Apply semantics (type imports, config imports → LOW confidence).

### Strategy 5: Reference Graph Fallback
Catch callbacks and dynamically referenced functions.

---

## Performance

| Codebase | Time | RAM |
|----------|------|-----|
| <5K LOC | ~0.5s | ~50MB |
| 20K LOC | ~1s | ~100MB |
| 100K+ LOC | ~2s | ~150MB |
