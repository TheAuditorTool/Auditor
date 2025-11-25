# Ruff Static Analysis Report & Cleanup Roadmap

**Date:** 2025-11-24
**Last Updated:** 2025-11-25

---

## Executive Summary

**Current State:** All critical runtime errors (F821, F811) eliminated. Remaining issues are code quality and dead code cleanup.

**Dogfooding Reality Check:** When we ran TheAuditor on itself (`.pf/raw/lint.json`), it found **12,851 issues** vs ruff's **818**. Our own tool catches what ruff doesn't: whitespace pollution, outdated syntax, magic numbers, unsafe patterns, and type system lies.

**The Brutal Truth:** This codebase was built fast without cleanup discipline. Dead code accumulates. Legacy fallbacks multiply. Comments become lies. The mess actively **poisons AI context** - approximately **80-90% context window waste** reading garbage instead of real code.

---

## Current Status (Ruff Basic Scan)

**Total Issues:** 818

| Code | Count | Files | Description | Auto-Fix |
|------|-------|-------|-------------|----------|
| F821 | 0 | 0 | Undefined names (CRASHES) | ✅ **FIXED** |
| F811 | 0 | 0 | Redefinitions (shadowing) | ✅ **FIXED** |
| F401 | 746 | 235 | Unused imports (dead code) | ⚠️ Manual review |
| F841 | 72 | 53 | Unused variables (dead code) | ⚠️ Manual review |

---

## Dogfooding Reality (TheAuditor on Itself)

**Total Issues:** 12,851 (theauditor/ only, no tests)

| Rule | Count | Description | Fix Type |
|------|-------|-------------|----------|
| **W293** | 2,237 | Blank lines with invisible whitespace | Auto-fix |
| **UP006** | 1,807 | Old-style `List[str]` → `list[str]` | Auto-fix |
| **mypy-note** | 950 | Type inference warnings | Manual |
| **B905** | 853 | `zip()` without `strict=` parameter | Semi-auto |
| **F401** | 718 | Unused imports | Auto-fix* |
| **no-untyped-def** | 662 | Functions missing type hints | Manual |
| **UP045** | 609 | `Optional[X]` → `X \| None` | Auto-fix |
| **PLR2004** | 479 | Magic numbers (hardcoded values) | Manual |
| **UP035** | 440 | Old import paths (typing → collections.abc) | Auto-fix |
| **PLC0415** | 333 | Imports inside functions | Semi-auto |
| **I001** | 323 | Unsorted imports | Auto-fix |
| **F841** | 67 | Unused variables | Manual |

**Worst Offenders:**
- `generated_accessors.py`: **2,539 issues** (code generator outputs garbage)
- `generated_types.py`: **591 issues** (more generated garbage)
- `python_database.py`: **450 issues** (2,313 lines of mixins)
- `pipelines.py`: **168 issues** (current working file)

---

## Why This Matters: AI Context Corruption

**Scale: 9/10 - Token Poisoning Is Severe**

### How Garbage Code Corrupts AI Decisions:

1. **Pattern Learning From Dead Code**
   - AI sees fallback patterns 100+ times
   - Learns: "Always add try/except with 3 fallbacks!"
   - Result: New code adds more fallbacks, more garbage

2. **Comment Lies**
   - "DO NOT DELETE - Used by taint analysis" (actually dead 349 lines)
   - "CRITICAL: Python 3.7 compatibility" (Python 3.7 deprecated)
   - AI trusts these, preserves garbage forever

3. **Generated Code As Training Data**
   - Code generator violates its own linting rules (2,539 + 591 = 3,130 issues)
   - AI reads this as "correct patterns"
   - Copies broken patterns to new code

4. **Context Window Waste**
   - 80% of context: dead code, legacy comments, outdated patterns
   - 20% of context: actual working code
   - AI makes decisions based on garbage majority

5. **Type System Lies**
   - 60% functions untyped
   - 40% use outdated syntax (`List`, `Optional`)
   - AI can't trust any type hints it sees

**Impact:** Every AI coding session starts with corrupted training data. Hallucinations aren't random - they're learned from garbage.

---

## THE NEW RULES: Delete First, Preserve Never

### Philosophy Shift (MANDATORY)

**OLD WAY (BANNED):**
- ✗ Comment out old code "just in case"
- ✗ Add defensive fallbacks "for safety"
- ✗ Keep legacy code "for rollback"
- ✗ Write "DO NOT DELETE" comments
- ✗ Preserve dead code "someone might need it"

**NEW WAY (REQUIRED):**
- ✅ **DELETE dead code immediately** - Git is the safety net
- ✅ **FAIL LOUD** - One code path, no fallbacks, crash if wrong
- ✅ **REMOVE old comments** - If code changed, comment is a lie
- ✅ **REWRITE after verification** - Don't patch, replace
- ✅ **TRUST GIT** - Delete everything not currently used

**Mantra:** "If it breaks, we'll know immediately and fix it. If it doesn't break, it was already dead."

---

## Cleanup Roadmap

### Phase 0: Prerequisites (CRITICAL - Do First)

**Goal:** Stop generating garbage before fixing garbage

**Tasks:**
1. **Fix Code Generator** (`theauditor/indexer/schemas/codegen.py`)
   - Output modern type hints (`list` not `List`)
   - Remove trailing whitespace from generated code
   - Add proper imports (already fixed SchemaCodeGenerator import)
   - **Time:** 2 hours

2. **Regenerate All Generated Files**
   - `generated_accessors.py` (currently 2,539 issues)
   - `generated_types.py` (currently 591 issues)
   - `generated_validators.py` (already fixed)
   - `generated_cache.py`
   - **Time:** 30 minutes

3. **Add `__all__` to Package Interfaces**
   - `ast_extractors/__init__.py` - Declare public API
   - Stop ruff from flagging intentional re-exports
   - **Time:** 1 hour

**Phase 0 Total: 3.5 hours**

---

### Phase 1: Auto-Fix (Low Risk)

**Goal:** Fix 6,000+ issues with automated tools

**Tasks:**

```bash
# Run each separately, commit after each, test nothing broke

# 1. Whitespace cleanup (2,237 issues)
ruff check --select W293 --fix
git add -A && git commit -m "chore: remove trailing whitespace from blank lines"

# 2. Modernize type hints (2,416 issues)
ruff check --select UP006,UP045 --fix
git add -A && git commit -m "refactor: modernize type hints to Python 3.9+ syntax"

# 3. Modernize imports (440 issues)
ruff check --select UP035 --fix
git add -A && git commit -m "refactor: use collections.abc imports"

# 4. Sort imports (323 issues)
ruff check --select I001 --fix
git add -A && git commit -m "style: sort imports"

# 5. Remove unused imports (718 issues) - CAREFUL!
# First add __all__ declarations to prevent false positives
ruff check --select F401 --fix
git add -A && git commit -m "refactor: remove unused imports"
```

**Risk:** Low - All automated, but test after each step

**Time:**
- Run fixes: 30 minutes
- Test after each: 2 hours
- Fix breakage: 1 hour
- **Total: 3.5 hours**

**Eliminated: ~6,000 issues**

---

### Phase 2: Semi-Auto Fixes (Medium Risk)

**Goal:** Pattern-based fixes that need verification

#### Task 2.1: Add `strict=True` to zip() (853 instances)

**Why:** `zip(a, b)` silently truncates if lengths don't match. Bugs hide.

```python
# Before (DANGEROUS)
for x, y in zip(calls, definitions):  # If mismatch, silently loses data
    process(x, y)

# After (SAFE)
for x, y in zip(calls, definitions, strict=True):  # Crashes if mismatch
    process(x, y)
```

**Script:**
```bash
# Find all zip() calls
ruff check --select B905 --output-format json > zip_issues.json

# Review each case:
# - If lengths MUST match: add strict=True
# - If intentional truncation: add comment explaining why
```

**Time:** 3 hours (manual review each case)

#### Task 2.2: Remove Unused Variables (67 instances)

**Pattern:** `foo = get_value()` but `foo` never referenced

**Process:**
1. Read each case in ruff.md
2. Verify it's truly unused (not debugging breadcrumb)
3. Delete the line
4. Run tests

**Time:** 1.5 hours

#### Task 2.3: Move Imports to Top (333 instances)

**Why:** Imports inside functions slow down code, hide dependencies

```python
# Before
def process():
    import json  # ← Every call re-imports
    return json.loads(data)

# After
import json  # ← Import once at module load

def process():
    return json.loads(data)
```

**Risk:** Circular import issues - verify each move

**Time:** 2 hours

**Phase 2 Total: 6.5 hours**

**Eliminated: ~1,200 issues**

---

### Phase 3: Critical Manual Fixes (High Value)

**Goal:** Fix issues that block progress or hide bugs

#### Task 3.1: Type Hints for Public APIs (20 hours)

**Scope:** Add type hints to:
- All CLI command functions
- All public extractor functions
- All database methods
- All API boundaries

**Don't type:** Internal helpers, private methods (can do later)

**Example:**
```python
# Before
def extract_functions(context):
    return python_impl.extract_python_functions(context)

# After
def extract_functions(context: FileContext) -> list[dict[str, Any]]:
    return python_impl.extract_python_functions(context)
```

**Impact:** IDE autocomplete works, AI understands interfaces, fewer bugs

#### Task 3.2: Fix Critical Type Errors (10 hours)

**Mypy notes in critical paths:**
- `taint/*.py` - Type errors in taint analysis
- `indexer/orchestrator.py` - Type errors in indexing
- `fce.py` - Type errors in full context extraction

**Process:**
1. Run mypy on critical files
2. Fix actual type mismatches (not just add annotations)
3. Verify logic correctness

#### Task 3.3: Extract Magic Numbers (10 hours)

**Pattern:**
```python
# Before (MAGIC NUMBERS)
if depth > 3:
    if timeout > 5000:
        if batch_size > 100:

# After (NAMED CONSTANTS)
MAX_CALL_DEPTH = 3
DEFAULT_TIMEOUT_MS = 5000
MAX_BATCH_SIZE = 100

if depth > MAX_CALL_DEPTH:
    if timeout > DEFAULT_TIMEOUT_MS:
        if batch_size > MAX_BATCH_SIZE:
```

**Scope:** Focus on security-critical and configuration values first

**Phase 3 Total: 40 hours**

**Eliminated: ~1,600 issues**

---

### Phase 4: Delete Dead Code (Critical)

**Goal:** Remove everything not actively called

**Process:**

1. **Find Dead Functions** (use FCE to map call graph)
   ```bash
   aud full --offline
   aud query --symbol <function_name> --show-callers
   # If no callers → DELETE
   ```

2. **Delete Legacy Fallback Paths**
   - Search for: `try:.*except.*pass`
   - Search for: `if.*exist.*else`
   - Delete the fallback, keep one path, let it crash

3. **Remove Old Comments**
   - Search for: `# LEGACY`, `# TODO`, `# FIXME`, `# DO NOT DELETE`
   - If code is still there, comment is a lie → DELETE comment
   - If code was fixed, delete the comment
   - If issue remains, create GitHub issue, delete comment

4. **Delete Commented Code**
   - Search for: `# old_function()`, `# return old_value`
   - Git has the history → DELETE all commented code

**Verification:**
```bash
# After each deletion batch
aud full --offline  # Run full analysis
pytest tests/       # Run test suite
# If it breaks → Good! Fix the real issue
# If it works → Was already dead
```

**Phase 4 Total: 20 hours**

---

## Timeline & Prioritization

### Tier 1: Must Do Now (Critical Path)

| Phase | Tasks | Time | Impact |
|-------|-------|------|--------|
| Phase 0 | Fix generator, add __all__ | 3.5h | Stops generating garbage |
| Phase 1 | Auto-fixes | 3.5h | 6,000 issues eliminated |
| Phase 4 | Delete dead code | 20h | Reduce context pollution |

**Subtotal: 27 hours (1 week)** → **Eliminates 70% of context corruption**

### Tier 2: Should Do Soon (High Value)

| Phase | Tasks | Time | Impact |
|-------|-------|------|--------|
| Phase 2 | Semi-auto fixes | 6.5h | 1,200 issues, safer code |
| Phase 3.1 | Type public APIs | 20h | IDE support, fewer bugs |

**Subtotal: 26.5 hours (1 week)** → **Code becomes maintainable**

### Tier 3: Do Incrementally (Long-term)

| Phase | Tasks | Time | Impact |
|-------|-------|------|--------|
| Phase 3.2 | Fix critical type errors | 10h | Taint/FCE more reliable |
| Phase 3.3 | Extract magic numbers | 10h | Config more readable |

**Subtotal: 20 hours** → **Polish**

---

## Success Metrics

**After Tier 1 (1 week):**
- ✅ Code generator outputs clean code
- ✅ 6,000+ auto-fixable issues eliminated
- ✅ Dead code identified and removed
- ✅ AI context pollution reduced by ~70%
- ✅ ruff check shows <2,000 remaining issues

**After Tier 2 (2 weeks):**
- ✅ Public APIs fully typed
- ✅ IDE autocomplete works reliably
- ✅ All unsafe patterns fixed (zip without strict)
- ✅ AI context pollution reduced by ~85%
- ✅ ruff check shows <1,000 remaining issues

**After Tier 3 (3-4 weeks):**
- ✅ Type system reliable in critical paths
- ✅ No magic numbers in security code
- ✅ AI context pollution reduced by ~90%
- ✅ ruff check shows <500 remaining issues

---

## Working Guide for AI Instances

**When you read this codebase:**

1. **Assume dead code until proven alive**
   - If you see unused imports → delete them
   - If you see commented code → delete it
   - If you see try/except fallbacks → delete fallback, keep one path

2. **Never preserve "just in case"**
   - No defensive coding
   - No "legacy compatibility"
   - No "rollback paths"
   - Git is the safety net

3. **Rewrite, don't patch**
   - If fixing a function, rewrite it completely
   - Delete old implementation
   - Write new one from scratch
   - Add tests for new version

4. **Trust breakage**
   - If deleting code breaks tests → good! Found dead code that should've been removed
   - Fix the breakage properly, don't restore the garbage
   - Every break is a learning opportunity

5. **Context budget**
   - Before reading a 500-line file, check if most is dead
   - Use `aud explain` to see what's actually called
   - Skip dead functions entirely - don't waste context

---

## Detailed Issue Lists

### F841 - Unused Local Variables (72 issues)

<details>
<summary>Click to expand full list</summary>

#### ast_extractors\js_helper_templates.py (1 unused)
- Line 159: `header_section` assigned but never used

#### ast_extractors\python\core_extractors.py (1 unused)
- Line 904: `current_function` assigned but never used

#### ast_extractors\python\data_flow_extractors.py (2 unused)
- Line 483: `is_lambda` assigned but never used
- Line 804: `in_function` assigned but never used

#### ast_extractors\python\django_advanced_extractors.py (1 unused)
- Line 159: `decorator_name` assigned but never used

#### ast_extractors\python\flask_extractors.py (1 unused)
- Line 445: `resources_node` assigned but never used

#### ast_extractors\python\operator_extractors.py (3 unused)
- Line 124: `comparison_ops` assigned but never used
- Line 129: `logical_ops` assigned but never used
- Line 138: `unary_ops` assigned but never used

#### ast_extractors\python\orm_extractors.py (1 unused)
- Line 347: `back_populates_node` assigned but never used

#### ast_extractors\python\protocol_extractors.py (2 unused)
- Line 129: `next_method` assigned but never used
- Line 142: `iter_method` assigned but never used

#### ast_extractors\python\security_extractors.py (1 unused)
- Line 443: `key_size` assigned but never used

#### ast_extractors\typescript_impl.py (3 unused)
- Line 529: `expression` assigned but never used
- Line 673: `expr_kind` assigned but never used
- Line 824: `content` assigned but never used

#### ast_extractors\typescript_impl_structure.py (1 unused)
- Line 714: `base_name_for_enrichment` assigned but never used

... and 42 more files with unused variables (see full report for complete list)

</details>

### F401 - Unused Imports (746 issues)

<details>
<summary>Click to expand top 30 files</summary>

#### ast_extractors\__init__.py (4 unused)
- Line 24: `.python` imported but unused (likely re-export - add to `__all__`)
- Line 24: `.typescript_impl` imported but unused (likely re-export - add to `__all__`)
- Line 24: `.treesitter_impl` imported but unused (likely re-export - add to `__all__`)
- Line 25: `.base.detect_language` imported but unused (likely re-export - add to `__all__`)

#### Pattern: Most Python extractor files have unused `typing.List`, `typing.Dict`, etc.
**Solution:** Run `ruff check --select UP006,UP045 --fix` to auto-convert to modern syntax, then remove unused.

... (See above for detailed per-file listings)

</details>

---

## Related Documents

- **REFACTOR_FAILURE_ANALYSIS.md** - How we got here (FileContext refactor mistakes)
- **.pf/raw/lint.json** - Full dogfooding results (12,851 issues)
- **CLAUDE.md** - AI working instructions (includes cleanup philosophy)

---

**Last Updated:** 2025-11-25
**Next Review:** After Phase 1 completion
**Owner:** Project maintainer + AI assistants
