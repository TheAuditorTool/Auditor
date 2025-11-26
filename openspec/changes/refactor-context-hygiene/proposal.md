# Proposal: Context Hygiene Protocol - AI Dataset Cleanup

## Why

**The Core Problem:** TheAuditor's codebase has become a poisoned dataset for AI assistants.

When Opus (the Coder) reads this codebase, **80% of the context window is garbage**:
- Dead code that hasn't been called in months
- Try/except fallback patterns that violate CLAUDE.md's ZERO FALLBACK policy
- Generated files producing 3,130 lint issues (20% of total)
- Outdated type syntax (`List[str]` instead of `list[str]`)
- Comments that lie ("DO NOT DELETE" on dead code)

**The Result:** AI learns from garbage, replicates garbage patterns, hallucinates based on dead code.

**Scale of Contamination:**
- **ruff scan:** 818 issues
- **TheAuditor dogfooding:** 12,851 issues
- **Worst offender:** `generated_accessors.py` with 2,539 issues alone

This is not a "code style" problem. This is an **operational failure** in an AI-centric workflow. If we read trash, we generate trash.

### Lead Auditor's Verdict: 80% Critical Survival / 20% Purist Fetish

The Lead Auditor has reviewed the original `ruff.md` plan and issued corrections. Key insight: **Dead code removal and generator fixes are survival necessities. Import sorting is developer vanity.**

---

## What Changes

### Phase 1: Stop the Factory Defects (CRITICAL)

**Rationale:** Cannot clean the floor while the ceiling is leaking.

**Target File:** `theauditor/indexer/schemas/codegen.py`

**Specific Lines to Fix:**
| Line | Current Output | Required Output |
|------|----------------|-----------------|
| 27 | `from typing import Dict, List, Optional, Set, Any` | Remove unused, use builtins |
| 111 | `from typing import TypedDict, Optional, Any` | `from typing import TypedDict, Any` + use `\| None` |
| 122 | `Optional[{field_type}]` | `{field_type} \| None` |
| 138 | `from typing import List, Optional, Dict, Any` | Remove, use builtins |
| 155, 171, 175 | `List[Dict[str, Any]]` | `list[dict[str, Any]]` |
| 194 | `from typing import Dict, List, Any, Optional, DefaultDict` | `from collections import defaultdict` + builtins |
| 272 | `from typing import Any, Callable, Dict` | `from typing import Any, Callable` + `dict` builtin |

**Generated Files to Regenerate (exact paths):**
- `theauditor/indexer/schemas/generated_types.py` (591 issues)
- `theauditor/indexer/schemas/generated_accessors.py` (2,539 issues)
- `theauditor/indexer/schemas/generated_cache.py`
- `theauditor/indexer/schemas/generated_validators.py`

**How to Regenerate:**
```python
cd C:/Users/santa/Desktop/TheAuditor-cleanup
.venv/Scripts/python.exe -c "
from theauditor.indexer.schemas.codegen import SchemaCodeGenerator
SchemaCodeGenerator.write_generated_code()
print('Done - check theauditor/indexer/schemas/generated_*.py')
"
```

---

### Phase 2: The Great Purge (HIGH ROI)

**Rationale:** Dead code is the #1 context polluter. This phase moved UP from original Phase 4.

**ZERO FALLBACK Violations (exact file:line references):**

#### `theauditor/fce.py` - 30+ Exception Handlers
| Lines | Pattern | Action |
|-------|---------|--------|
| 66-67, 93-94, 134-135, 173-174, 212-213, 272-273, 405-406 | `except (json.JSONDecodeError, TypeError): pass` | DELETE - silent data loss |
| 98-99, 139-140, 178-179, 217-218, 277-278, 350-351, 422-423, 579-580 | `except sqlite3.Error: print(...)` | CONVERT to hard fail |
| 583-584, 669-670, 847-848, 868-869, 877-878, 992-996, 1050-1051 | Various silent catches | DELETE or hard fail |
| 1217-1218, 1224-1225, 1750-1753, 1839-1840 | Complex fallbacks | Audit case-by-case |

#### `theauditor/context/query.py` - 35+ OperationalError Handlers
| Lines | Pattern | Action |
|-------|---------|--------|
| 248-249, 316-317, 328-329, 358-359, 390-391, 453-454 | `except OperationalError: continue/pass` | DELETE - table should exist |
| 580-581, 627-628, 816-817, 821-822 | `except OperationalError: return []` | DELETE - crash if table missing |
| 894-895, 992-993, 1066-1067, 1158-1159, 1272-1273 | `if 'no such table' in str(e)` | DELETE - contract violation |
| 1354-1355, 1406-1407, 1419-1420, 1505-1506, 1563-1564 | Table existence fallbacks | DELETE |
| 1612-1613, 1629-1630, 1664-1665, 1700-1701, 1769-1770 | More fallbacks | DELETE |
| 1829-1830, 1834-1835, 1873-1874, 1887-1888, 1902-1903 | JSX table fallbacks | DELETE |
| 1916-1917, 1931-1932, 1943-1944, 1957-1958 | Final batch | DELETE |

#### `theauditor/rules/frameworks/express_analyze.py` - 10 Exception Handlers
| Lines | Pattern | Action |
|-------|---------|--------|
| 202, 244, 286, 332, 384, 447, 491, 525, 575, 625 | `except (sqlite3.Error, Exception):` | DELETE - hard fail |

#### `theauditor/rules/sql/sql_injection_analyze.py` - 2 Exception Handlers
| Lines | Pattern | Action |
|-------|---------|--------|
| 34 | `except Exception:` | DELETE |
| 273 | `except sqlite3.OperationalError:` | DELETE |

**`__all__` Declarations to Add:**

These packages have re-exports that ruff flags as F401. Add `__all__` to declare public API:

| File | Current Imports | `__all__` Content |
|------|-----------------|-------------------|
| `theauditor/ast_extractors/__init__.py:24-25` | `python_impl`, `typescript_impl`, `treesitter_impl`, `detect_language` | `['python_impl', 'typescript_impl', 'treesitter_impl', 'detect_language', 'get_semantic_ast_batch']` |
| `theauditor/indexer/__init__.py` | TBD - read file first | Export public orchestrator interface |
| `theauditor/rules/__init__.py` | TBD - read file first | Export public rule interfaces |
| `theauditor/taint/__init__.py` | TBD - read file first | Export TaintAnalyzer and public API |

**How to Find Dead Functions:**
```bash
# Step 1: Get all function names from database
cd C:/Users/santa/Desktop/TheAuditor-cleanup
.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('''SELECT DISTINCT name FROM symbols WHERE type = \"function\" ORDER BY name''')
for row in c.fetchall():
    print(row[0])
conn.close()
" > all_functions.txt

# Step 2: For each function, check if it has callers
aud query --symbol <function_name> --show-callers

# If "Callers: (none)" -> DELETE the function
```

---

### Phase 3: Automated Modernization (LOW RISK)

**Rationale:** Modern syntax is cheaper on tokens and easier for models trained on modern Python.

**Exact Commands (run in order):**
```bash
cd C:/Users/santa/Desktop/TheAuditor-cleanup

# 1. Type hints: List[str] -> list[str] (1,807 issues)
ruff check theauditor --select UP006 --statistics  # Count before
ruff check theauditor --select UP006 --fix
python -c "import theauditor"  # Verify

# 2. Optional -> Union: Optional[X] -> X | None (609 issues)
ruff check theauditor --select UP045 --statistics
ruff check theauditor --select UP045 --fix
python -c "import theauditor"

# 3. Import paths: typing -> collections.abc (440 issues)
ruff check theauditor --select UP035 --statistics
ruff check theauditor --select UP035 --fix
python -c "import theauditor"

# 4. Whitespace: trailing whitespace on blank lines (2,237 issues)
ruff check theauditor --select W293 --statistics
ruff check theauditor --select W293 --fix
# No verification needed
```

---

### Phase 4: Functional Integrity (MANDATORY)

**Rationale:** These are actual bugs, not style preferences.

**zip() Audit (853 instances):**
```bash
# Generate audit list
ruff check theauditor --select B905 --output-format json > zip_audit.json

# Review criteria for each:
# - MUST add strict=True: parallel data structures where mismatch = data corruption
# - OK without strict: zip(range(n), items) - intentional bounded iteration
# - Document if leaving without strict: add comment explaining why
```

**Public API Typing Scope (exact files):**

| File | Public Methods to Type |
|------|------------------------|
| `theauditor/indexer/extractors/base.py` | `BaseExtractor.extract()`, `BaseExtractor.supported_extensions` |
| `theauditor/indexer/database/__init__.py` | `DatabaseManager.add_*()`, `DatabaseManager.get_*()` |
| `theauditor/graph/analyzer.py` | `GraphAnalyzer.analyze()`, `GraphAnalyzer.build()` |
| `theauditor/taint/core.py` | `TaintAnalyzer.analyze()`, `TaintAnalyzer.get_results()` |
| `theauditor/commands/*.py` | All `@click.command()` decorated functions |

**DO NOT TYPE:**
- Private methods (`_helper_function`)
- Internal module functions
- `**kwargs` handlers
- Functions under 5 lines where types are obvious

---

### Phase 5: Explicitly Ignored (REJECTED)

**Rationale:** Zero operational value, high merge conflict risk.

| Rule | Count | Verdict | Reason |
|------|-------|---------|--------|
| I001 (import sorting) | 323 | **REJECTED** | Python interpreter doesn't care, creates merge conflicts |
| PLR2004 (magic numbers) | 479 | **REJECTED** | Unless 3+ uses or security-critical |
| Aggressive docstrings | N/A | **REJECTED** | Time sink for no AI benefit |
| Type all internals | N/A | **REJECTED** | If AI can't understand 5 lines, the function is the problem |

---

## Impact

### Affected Code (by phase)

| Phase | Files | Changes |
|-------|-------|---------|
| 1 | 5 files | Fix `codegen.py`, regenerate 4 `generated_*.py` |
| 2 | ~50+ files | Delete ~100 exception handlers, add 4 `__all__` declarations |
| 3 | ~200 files | Automated type hint modernization |
| 4 | ~50 files | zip() audit (853 calls), type ~20 public API methods |

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Deleting "dead" code that's actually used | MEDIUM | HIGH | Run `aud full --offline` + test suite after each batch |
| Breaking imports after F401 cleanup | LOW | MEDIUM | Delete code FIRST, then imports |
| Type hint conversion breaks runtime | LOW | LOW | Python 3.9+ handles all modern syntax |

### Affected Specs
- None directly. This is internal cleanup, not API changes.

### Relationship to Existing Changes
- `refactor-extraction-zero-fallback`: Complementary. That spec targets extraction pipeline fallbacks specifically. This spec targets codebase-wide context hygiene.

---

## Success Metrics

**After Phase 1-2 (Core Cleanup):**
- Code generator outputs clean code (0 issues in generated files)
- Dead code removed (~70% context pollution eliminated)
- `ruff check` shows <2,000 remaining issues

**After Phase 3-4 (Modernization + Integrity):**
- All public APIs typed
- All `zip()` calls audited
- `ruff check` shows <500 remaining issues
- AI context pollution reduced by ~85%

---

## Execution Environment

**CRITICAL:** This work executes in an **isolated git worktree**:
```
C:\Users\santa\Desktop\TheAuditor\         <- dev branch (main work)
C:\Users\santa\Desktop\TheAuditor-cleanup\ <- cleanup-ruff branch (this work)
```

No risk to main development. Full isolation. Merge when complete and tested.

---

## NOT Changing

- Database schemas (no migrations)
- CLI commands (no user-facing changes)
- Extractor interfaces (contract unchanged)
- Test files (cleanup scope is `theauditor/` only)
- External dependencies

---

## Reference Documents

- `ruff.md` - Original cleanup analysis with F841 detailed list (72 items with file:line)
- `CLAUDE.md` - ZERO FALLBACK policy definition
- `teamsop.md` - Verification-first workflow requirements
