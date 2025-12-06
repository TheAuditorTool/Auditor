# Design: Context Hygiene Protocol

## Context

### The Problem We're Solving

TheAuditor is an **AI-centric** SAST tool. The codebase is not just code - it's a **dataset** that AI assistants (Opus, Gemini, etc.) read to understand patterns and make decisions.

When 80% of that dataset is garbage:
- Dead functions that haven't been called in months
- Try/except fallbacks that violate ZERO FALLBACK policy
- Generated files with 3,130 lint issues
- Comments that lie about what code does

...the AI learns garbage patterns and replicates them.

**This is not code style. This is operational integrity.**

### Stakeholders

- **Opus (AI Coder):** Reads this codebase constantly. Every dead function pollutes the context window.
- **Lead Auditor (Gemini):** Reviews code quality. Can't trust patterns if most are deprecated.
- **Architect (Human):** Pays for tokens. 80% waste is unacceptable.
- **Future contributors:** Will learn from whatever patterns exist today.

### Constraints

1. **Isolated Execution:** All work in `C:\Users\santa\Desktop\TheAuditor-cleanup\` worktree
2. **No API Changes:** This is internal cleanup only
3. **No Schema Changes:** Database contracts unchanged (251 tables in repo_index.db)
4. **Zero Fallback Policy:** Must remain compliant with CLAUDE.md
5. **Python 3.14 Target:** Can use all modern syntax (`list[str]`, `X | None`)

---

## Goals / Non-Goals

### Goals
- Reduce AI context pollution by 85%+
- Stop the code generator from producing garbage
- Delete all dead code (git is the safety net)
- Modernize syntax for cheaper token usage
- Fix actual bugs (`zip()` without strict)

### Non-Goals
- Making the code "pretty" (import sorting = vanity)
- 100% type coverage (diminishing returns)
- Extracting every magic number (indirection for indirection's sake)
- Satisfying linter score fetishes

---

## Technical Architecture

### Code Generator System (`theauditor/indexer/schemas/codegen.py`)

**What It Does:**
The `SchemaCodeGenerator` class auto-generates Python code from schema definitions:
1. `generate_typed_dicts()` → `generated_types.py` (TypedDict for each table)
2. `generate_accessor_classes()` → `generated_accessors.py` (get_all, get_by_X methods)
3. `generate_memory_cache()` → `generated_cache.py` (SchemaMemoryCache class)
4. `generate_validators()` → `generated_validators.py` (runtime validation)

**Current Problem (lines with old syntax):**

```python
# codegen.py line 111 - TypedDict file header
code.append("from typing import TypedDict, Optional, Any")

# codegen.py line 122 - Optional field syntax
field_type = f"Optional[{field_type}]"

# codegen.py line 138 - Accessor file header
code.append("from typing import List, Optional, Dict, Any")

# codegen.py lines 155, 171, 175 - Return type annotations
"def get_all(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:"

# codegen.py line 194 - Memory cache file header
code.append("from typing import Dict, List, Any, Optional, DefaultDict")
```

**Required Fix:**

```python
# line 111 - Remove Optional import
code.append("from typing import TypedDict, Any")

# line 122 - Use union syntax
field_type = f"{field_type} | None"

# line 138 - Use builtins
code.append("from typing import Any")

# lines 155, 171, 175 - Lowercase builtins
"def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:"

# line 194 - Minimal imports
code.append("from typing import Any")
code.append("from collections import defaultdict")
```

**How to Regenerate:**
```python
from theauditor.indexer.schemas.codegen import SchemaCodeGenerator
SchemaCodeGenerator.write_generated_code()
# Output: theauditor/indexer/schemas/generated_*.py
```

### ZERO FALLBACK Violation Patterns

**Pattern 1: Silent JSON Decode** (fce.py)
```python
# CURRENT (BANNED):
try:
    data = json.loads(row[1])
except (json.JSONDecodeError, TypeError):
    pass  # Silent data loss!

# REQUIRED:
data = json.loads(row[1])  # Crash if malformed
```

**Pattern 2: Table Existence Fallback** (context/query.py)
```python
# CURRENT (BANNED):
try:
    cursor.execute("SELECT * FROM react_components")
except sqlite3.OperationalError:
    return []  # Hides schema bugs!

# REQUIRED:
cursor.execute("SELECT * FROM react_components")  # Crash if missing
# Schema contract guarantees table exists
```

**Pattern 3: Broad Exception Catch** (express_analyze.py)
```python
# CURRENT (BANNED):
try:
    findings = analyze_routes(cursor)
except (sqlite3.Error, Exception):
    return []  # Hides ALL bugs!

# REQUIRED:
findings = analyze_routes(cursor)  # Let it crash
```

### Database Architecture (Context)

**Two Databases:**
- `repo_index.db` (181MB): 251 tables across 8 schema domains - raw facts from AST
- `graphs.db` (126MB): 4 polymorphic tables - pre-computed graph structures

**Schema Contract:** Tables are GUARANTEED to exist after indexing. Any "table not found" error is a schema violation, not a runtime condition to handle.

---

## Decisions

### Decision 1: Phase Order - Dead Code FIRST

**What:** Move dead code deletion (original Phase 4) to Phase 2, immediately after generator fix.

**Why:** The original `ruff.md` had dead code deletion at the end. This is backwards. Every subsequent phase would waste effort fixing code that should be deleted.

**Lead Auditor Directive:** "Run the Dead Code Deletion (Phase 4) immediately after Phase 0. Do not wait until the end. We need the context window clear now."

**Alternatives Considered:**
- Follow original ruff.md order - REJECTED: Wastes effort fixing dead code
- Do everything in parallel - REJECTED: Creates false positives (can't delete imports before deleting code)

### Decision 2: Generator Fix is Prerequisite

**What:** Fix `codegen.py` before any cleanup.

**Why:** The generator produces 20% of all issues (3,130 from 2 files). If we clean without fixing the generator, the next regeneration recreates the garbage.

**Lead Auditor Directive:** "You cannot have a clean house if the faucet is pumping sewage into the living room."

### Decision 3: Import Sorting REJECTED

**What:** Do NOT run `ruff check --select I001 --fix`.

**Why:**
1. Python interpreter doesn't care about import order
2. AI doesn't care about import order
3. Creates merge conflicts when multiple people edit same file
4. Zero operational value

**Lead Auditor Directive:** "TOTAL FETISH. Waste of time."

### Decision 4: Type Only Public APIs

**What:** Add type hints to public interfaces ONLY. Do NOT type internal helpers.

**Why:**
1. Public APIs are contracts - types help AI verify inputs
2. Internal helpers are implementation details - over-typing adds noise
3. If AI can't understand a 5-line internal function without types, the function is the problem

**Scope (IN) - Files to Type:**

| File | Public Methods |
|------|---------------|
| `theauditor/indexer/extractors/base.py` | `BaseExtractor.extract()`, `supported_extensions` |
| `theauditor/indexer/database/__init__.py` | `DatabaseManager.add_*()`, `get_*()` |
| `theauditor/graph/analyzer.py` | `GraphAnalyzer.analyze()`, `build()` |
| `theauditor/taint/core.py` | `TaintAnalyzer.analyze()`, `get_results()` |
| `theauditor/commands/*.py` | All `@click.command()` decorated functions |

**Scope (OUT):**
- Private methods (`_helper_function`)
- Internal module functions
- Dynamic `**kwargs` handlers
- Complex generic gymnastics

### Decision 5: zip(strict=True) is Mandatory

**What:** Audit all 853 `zip()` calls and add `strict=True` where data loss is unacceptable.

**Why:** `zip(a, b)` silently truncates if lengths don't match. In a data-heavy tool processing thousands of AST nodes, this causes "ghost bugs" - data disappears with no error.

**Lead Auditor Directive:** "This is functional correctness, not style."

**Decision Criteria:**
| Scenario | Action |
|----------|--------|
| `zip(calls, definitions)` where mismatch = data corruption | `strict=True` |
| `zip(range(n), items)` bounded iteration | Leave as-is |
| Intentional truncation | Comment: `# Intentional: truncates to shorter` |

### Decision 6: Magic Numbers - Selective Only

**What:** Extract magic numbers ONLY if:
1. Used in 3+ places, OR
2. Security-critical threshold

**Why:** Changing `if depth > 3` to `if depth > MAX_RECURSION_DEPTH` adds indirection. If that number never changes and is only used once, you're making code harder to read.

---

## Risks / Trade-offs

### Risk: Deleting "Dead" Code That's Actually Used

**Likelihood:** MEDIUM
**Impact:** HIGH (runtime errors)

**Mitigation:**
1. Use `aud query --symbol X --show-callers` to verify no callers
2. Run `aud full --offline` after each deletion batch
3. Run full test suite (`pytest tests/ -v`)
4. If it breaks, GOOD - we found the bug. Fix it properly, don't restore garbage.

**How to Find All Functions:**
```python
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute('SELECT DISTINCT name FROM symbols WHERE type = "function"')
for row in c.fetchall():
    print(row[0])
```

### Risk: Breaking Imports After F401 Cleanup

**Likelihood:** LOW
**Impact:** MEDIUM (import errors)

**Mitigation:**
1. Delete CODE first, then imports
2. Add `__all__` to packages to declare public API
3. Run `python -c "import theauditor"` after each batch

### Risk: Type Hint Conversion Breaks Runtime

**Likelihood:** VERY LOW
**Impact:** LOW

**Mitigation:**
- Python 3.9+ handles all modern syntax natively
- We're targeting Python 3.14
- No `from __future__ import annotations` games needed

---

## Migration Plan

### Execution Sequence

```
Phase 0: Verification (Baseline Metrics)
    |
    v
Phase 1: Fix Generator (codegen.py + regenerate)
    |
    v
Phase 2: Delete Dead Code (fallbacks, F841, F401)
    |
    v
Phase 3: Automated Modernization (UP006, UP045, UP035, W293)
    |
    v
Phase 4: Functional Integrity (B905 zip audit, public API types)
    |
    v
Phase 5: Final Validation + PR
```

### Rollback Strategy

Each phase commits separately. Rollback is:
```bash
git revert <phase-commit-hash>
```

If entire cleanup is problematic:
```bash
git worktree remove ../TheAuditor-cleanup
# main dev branch unaffected
```

### Verification at Each Phase

After EVERY phase:
1. `python -c "import theauditor"` - imports work
2. `aud full --offline` - pipeline works
3. `ruff check theauditor --statistics` - issues decreasing

---

## Open Questions

1. **Q:** Should we also clean `tests/` directory?
   **A:** DEFERRED. Scope is `theauditor/` only for now. Tests can be a separate proposal.

2. **Q:** What about the 333 `PLC0415` (imports inside functions)?
   **A:** DEFERRED. Some are intentional (circular import avoidance). Needs case-by-case analysis in future proposal.

3. **Q:** Should we enable mypy strict mode?
   **A:** NO. Mypy strict on a dynamic Python codebase creates `Any`/`cast` gymnastics that makes code HARDER to read. Type the boundaries, not everything.

4. **Q:** What about the 950 `mypy-note` type inference warnings?
   **A:** DEFERRED. These are notes, not errors. Address as part of Phase 4 public API typing only.

---

## Philosophy Summary

**The New Rules (from ruff.md, endorsed by Lead Auditor):**

1. **DELETE dead code immediately** - Git is the safety net
2. **FAIL LOUD** - One code path, no fallbacks, crash if wrong
3. **REMOVE old comments** - If code changed, comment is a lie
4. **REWRITE after verification** - Don't patch, replace
5. **TRUST GIT** - Delete everything not currently used

**Mantra:** "If it breaks, we'll know immediately and fix it. If it doesn't break, it was already dead."

---

## Reference: Exception Handler Counts

| File | Handlers | Action |
|------|----------|--------|
| `theauditor/fce.py` | 30+ | Delete silent JSON catches, convert sqlite3.Error to hard fail |
| `theauditor/context/query.py` | 35+ | Delete ALL OperationalError handlers |
| `theauditor/rules/frameworks/express_analyze.py` | 10 | Delete ALL (sqlite3.Error, Exception) handlers |
| `theauditor/rules/sql/sql_injection_analyze.py` | 2 | Delete both exception handlers |

**Total Exception Handlers to Remove/Convert:** ~77
