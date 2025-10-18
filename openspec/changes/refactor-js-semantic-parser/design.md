# Design Document - JavaScript Semantic Parser Refactor

## Context

### Problem Statement
The JavaScript semantic parser infrastructure has three interconnected problems:

1. **Discoverability Crisis**: `js_semantic_parser.py` lives in `theauditor/` (root) instead of `theauditor/ast_extractors/` where all other AST parsing implementations live. AI assistants regularly fail to find this module, treating it as non-existent during analysis.

2. **Context Window Overflow**: `typescript_impl.py` is a 2000+ line monolith that cannot fit in AI context windows. The file mixes high-level API functions (what to extract) with low-level implementation details (how to traverse AST nodes), violating separation of concerns.

3. **Maintenance Risk**: 50% of TheAuditor's value depends on accurate JavaScript/TypeScript analysis. These infrastructure problems make the most critical component the hardest to maintain.

### Current State
```
theauditor/
├── js_semantic_parser.py           # ← WRONG LOCATION (root instead of ast_extractors/)
├── ast_extractors/
│   ├── __init__.py                 # Does NOT export js_semantic_parser
│   ├── typescript_impl.py          # ← TOO BIG (2000+ lines, monolith)
│   ├── js_helper_templates.py
│   └── base.py
└── indexer/
    └── extractors/
        └── javascript.py           # Imports from theauditor.js_semantic_parser
```

### Constraints
1. **ZERO BREAKING CHANGES**: All existing imports must continue working
2. **No Schema Changes**: This is pure Python module organization, database untouched
3. **No Functional Changes**: Behavior remains identical, only structure changes
4. **AI-First**: Both resulting files must fit in AI context windows (<2000 lines each)
5. **Industry Standards**: Follow Python packaging best practices

### Stakeholders
- **Architect**: Approves strategic direction, ensures alignment with project goals
- **Lead Auditor (Gemini)**: Reviews technical approach, validates no regressions
- **AI Coder (Claude)**: Implements changes following verification protocol
- **Future Maintainers**: Benefit from improved discoverability and modularity

---

## Goals / Non-Goals

### Goals
1. **Move** `js_semantic_parser.py` to logical location (`ast_extractors/`) while maintaining backward compatibility via shim
2. **Split** `typescript_impl.py` into API layer (~1200 lines) and implementation layer (~800 lines)
3. **Improve** AI discoverability of JavaScript parsing infrastructure
4. **Maintain** 100% backward compatibility for all consumers
5. **Document** new structure in `ast_extractors/__init__.py`

### Non-Goals
1. **NOT** changing any function behavior or signatures
2. **NOT** modifying database schema or storage
3. **NOT** adding new features or capabilities
4. **NOT** refactoring internal algorithms or logic
5. **NOT** updating consumers (they continue using existing imports)

---

## Decisions

### Decision 1: Use Shim Pattern for js_semantic_parser.py Move

**What**: Leave a pure re-export module at `theauditor/js_semantic_parser.py` that imports from new location.

**Why**:
- Industry-standard pattern for module migrations (used by NumPy, Pandas, Django)
- Zero breaking changes - all existing imports work unchanged
- Allows gradual migration if needed (can update consumers over time)
- Clear deprecation path for future (add warnings if desired)

**Implementation**:
```python
# theauditor/js_semantic_parser.py (SHIM)
"""Backward compatibility shim.

This module has moved to theauditor.ast_extractors.js_semantic_parser.
This shim ensures existing imports continue working.
"""
from theauditor.ast_extractors.js_semantic_parser import (
    JSSemanticParser,
    get_semantic_ast,
    get_semantic_ast_batch,
)

__all__ = ['JSSemanticParser', 'get_semantic_ast', 'get_semantic_ast_batch']
```

**Alternatives Considered**:
1. **Hard Move + Update All Consumers**: Rejected - high risk, many files to update, potential for missing imports
2. **Symlink**: Rejected - not portable across Windows/Unix, confusing in version control
3. **__path__ Manipulation**: Rejected - too magical, harder to understand and debug

**Trade-offs**:
- **Pro**: Zero breakage, gradual migration path, well-understood pattern
- **Con**: One extra file to maintain (minimal - 10 lines)
- **Verdict**: Pro vastly outweighs con

---

### Decision 2: Split typescript_impl.py by Separation of Concerns

**What**: Extract low-level helpers into `typescript_ast_utils.py`, keep high-level API in `typescript_impl.py`.

**Why**:
- **Separation of Concerns**: API layer ("what to extract") vs Implementation layer ("how to traverse")
- **AI Context**: Each file fits in context window independently
- **Discoverability**: Public API is immediately visible without scrolling past 1000 lines of helpers
- **Maintainability**: Changes to traversal logic don't touch API, and vice versa

**File Split Criteria**:

**typescript_impl.py** (API Layer - ~1200 lines):
- All `extract_*` functions (public API)
- High-level orchestration logic
- Imports helpers from `typescript_ast_utils`

**typescript_ast_utils.py** (Implementation Layer - ~800 lines):
- Low-level node helpers (prefixed with `_`)
- Core AST traversal (`extract_semantic_ast_symbols`)
- JSX-specific logic (entire JSX subsystem)
- Complex algorithms (`build_scope_map`, `build_typescript_function_cfg`)

**Rationale**: A consumer wants to know "what can I extract?", not "how does scope mapping work?". Separate these concerns.

**Alternatives Considered**:
1. **Split by Language Feature**: Rejected - creates artificial boundaries, functions still too large
2. **Split Alphabetically**: Rejected - meaningless division, doesn't solve context window problem
3. **Multiple Small Files**: Rejected - over-engineering, harder to navigate, import complexity

**Trade-offs**:
- **Pro**: Clear responsibility boundaries, each file has single purpose, both fit in AI context
- **Con**: One additional file, slightly more imports
- **Verdict**: Industry standard pattern (api.py + impl.py, or public + private modules)

---

### Decision 3: Import Pattern - Namespace Alias

**What**: Use `from . import typescript_ast_utils as ast_utils` in `typescript_impl.py`.

**Why**:
- **Clarity**: `ast_utils.build_scope_map()` makes it clear this is a utility function
- **Namespace Control**: All utils accessed via single namespace, easy to identify
- **Readability**: Short alias (`ast_utils`) doesn't clutter code
- **Standard**: Common Python pattern (e.g., `import numpy as np`)

**Alternatives Considered**:
1. **Direct Imports**: `from .typescript_ast_utils import build_scope_map, ...`
   - Rejected: 15+ imports pollute namespace, unclear which are utils vs locals
2. **Full Module Name**: `from . import typescript_ast_utils` (no alias)
   - Rejected: `typescript_ast_utils.function()` is too verbose
3. **Star Import**: `from .typescript_ast_utils import *`
   - Rejected: BANNED by Python best practices, namespace pollution, hides dependencies

**Trade-offs**:
- **Pro**: Clean namespace, clear distinction, short and readable
- **Con**: None significant
- **Verdict**: Industry best practice for internal utilities

---

### Decision 4: Update ast_extractors/__init__.py

**What**: Add `from . import js_semantic_parser` to package exports.

**Why**:
- **Consistency**: All AST extractors should be accessible from package namespace
- **Discoverability**: `import theauditor.ast_extractors` reveals available extractors
- **Convention**: Standard Python package pattern (expose public modules in __init__)

**Implementation**:
```python
# theauditor/ast_extractors/__init__.py
from . import js_semantic_parser  # ADD THIS
# ... existing exports ...
```

**Alternatives Considered**:
1. **No Update**: Rejected - perpetuates discoverability problem
2. **Re-export Classes**: `from .js_semantic_parser import JSSemanticParser`
   - Rejected: creates two import paths, confusing which to use

**Trade-offs**:
- **Pro**: Standard pattern, improves discoverability
- **Con**: None
- **Verdict**: Clear win

---

### Decision 5: Preserve All Function Signatures EXACTLY

**What**: ZERO changes to function signatures, parameters, return types, or docstrings.

**Why**:
- **Backward Compatibility**: Consumers depend on exact signatures
- **Type Safety**: Any signature change could break type checking
- **Documentation**: Existing docs remain accurate
- **Testing**: Tests continue working unchanged

**Enforcement**:
- Verification phase MUST document all signatures before move
- Post-implementation testing MUST verify signatures unchanged
- Import testing MUST confirm both old and new locations work

**Non-Negotiable**: Any signature change requires separate proposal and is OUT OF SCOPE.

---

## Architecture

### Before Refactor
```
theauditor/
├── js_semantic_parser.py (950 lines)
│   └── Imports: ast_extractors.js_helper_templates
│
├── ast_extractors/
│   ├── __init__.py (does NOT export js_semantic_parser)
│   ├── typescript_impl.py (2000 lines - MONOLITH)
│   │   ├── Public API: extract_* functions (14)
│   │   ├── Helpers: _canonical_*, _identifier_*, etc. (4)
│   │   ├── JSX Logic: JSX_NODE_KINDS, detect_jsx_in_node, etc. (5)
│   │   └── Big Algorithms: build_scope_map, build_typescript_function_cfg
│   └── base.py
│
└── indexer/extractors/
    └── javascript.py
        └── Imports: from theauditor.js_semantic_parser import ...
```

### After Refactor
```
theauditor/
├── js_semantic_parser.py (10 lines - SHIM)
│   └── Re-exports: from ast_extractors.js_semantic_parser import *
│
├── ast_extractors/
│   ├── __init__.py (UPDATED - exports js_semantic_parser)
│   │
│   ├── js_semantic_parser.py (950 lines - MOVED)
│   │   └── Imports: .js_helper_templates (relative import now)
│   │
│   ├── typescript_impl.py (1200 lines - API LAYER)
│   │   ├── Imports: from . import typescript_ast_utils as ast_utils
│   │   ├── Public API: extract_* functions (14)
│   │   └── Calls: ast_utils.build_scope_map(), ast_utils.detect_jsx_in_node(), etc.
│   │
│   ├── typescript_ast_utils.py (800 lines - NEW - IMPLEMENTATION LAYER)
│   │   ├── Helpers: _canonical_*, _identifier_*, etc. (4)
│   │   ├── JSX Logic: JSX_NODE_KINDS, detect_jsx_in_node, etc. (5)
│   │   └── Big Algorithms: build_scope_map, build_typescript_function_cfg
│   │
│   └── base.py
│
└── indexer/extractors/
    └── javascript.py (UNCHANGED)
        └── Imports: from theauditor.js_semantic_parser import ...
            ↓
            (via shim) → from theauditor.ast_extractors.js_semantic_parser import ...
```

### Import Flow After Refactor
```
Consumer Code (javascript.py):
  from theauditor.js_semantic_parser import JSSemanticParser
         ↓
  Shim (theauditor/js_semantic_parser.py):
    from theauditor.ast_extractors.js_semantic_parser import JSSemanticParser
         ↓
  Actual Implementation (theauditor/ast_extractors/js_semantic_parser.py):
    class JSSemanticParser: ...

typescript_impl.py (API layer):
  from . import typescript_ast_utils as ast_utils

  def extract_typescript_assignments(...):
      scope_map = ast_utils.build_scope_map(ast_root)  # ← Calls util
         ↓
  typescript_ast_utils.py (Implementation layer):
    def build_scope_map(ast_root): ...
```

---

## Risks / Trade-offs

### Risk 1: Shim Import Overhead
**Risk**: Adding one extra import hop could slow down module loading.

**Likelihood**: MINIMAL - Python caches imports, overhead is negligible (microseconds).

**Mitigation**:
- Shim is pure re-export (no logic)
- Python import system optimizes this pattern
- No runtime performance impact (happens once at import time)

**Measurement**: Time imports before and after, verify <1ms difference.

**Verdict**: Not a real concern.

---

### Risk 2: Missed Import Site During Verification
**Risk**: If we miss a consumer during verification, it could break when we move the file.

**Likelihood**: LOW - systematic grep will find all imports.

**Mitigation**:
- Comprehensive grep for all import patterns:
  - `from theauditor.js_semantic_parser`
  - `from theauditor import js_semantic_parser`
  - `import theauditor.js_semantic_parser`
- Read EVERY importing file to confirm usage
- Full test suite run catches any missed cases
- Shim prevents breakage even if we miss one

**Verdict**: Shim pattern makes this non-critical.

---

### Risk 3: Circular Import from Split
**Risk**: If `typescript_impl.py` and `typescript_ast_utils.py` depend on each other, we create circular imports.

**Likelihood**: ZERO - by design, utils are pure helpers with no dependencies on API layer.

**Mitigation**:
- Verification MUST map all function dependencies
- Utils layer is leaf nodes (no imports from impl layer)
- One-way dependency: impl → utils (never utils → impl)

**Verification**:
```
typescript_ast_utils.py imports:
  - os, typing (stdlib)
  - .base (shared utilities)
  - NO imports from typescript_impl.py

typescript_impl.py imports:
  - os, typing (stdlib)
  - . import typescript_ast_utils as ast_utils (one-way)
  - .base (shared utilities)
```

**Verdict**: Impossible by design.

---

### Risk 4: Line Count Estimates Wrong
**Risk**: Files don't split 60/40 as estimated, one remains too large for AI context.

**Likelihood**: MEDIUM - estimates are based on reading the refactor plan, not actual code.

**Mitigation**:
- Verification phase will count actual lines
- If split is unbalanced, adjust what moves to utils
- Goal is BOTH files <1500 lines, not exact 60/40
- Can iterate on what goes where if needed

**Fallback**: If one file still too large, consider third file (typescript_ast_jsx.py for JSX-specific logic).

**Verdict**: Handle during verification, adjust as needed.

---

### Risk 5: Test Coverage Gaps
**Risk**: Existing tests don't cover all import paths, refactor breaks untested code.

**Likelihood**: MEDIUM - test coverage may be incomplete.

**Mitigation**:
- Verification identifies existing tests
- Create import validation test specifically for this refactor:
  ```python
  def test_backward_compat_imports():
      # Old location still works
      from theauditor.js_semantic_parser import JSSemanticParser as Old
      # New location works
      from theauditor.ast_extractors.js_semantic_parser import JSSemanticParser as New
      # They're the same object
      assert Old is New
  ```
- Run full pipeline on test project (end-to-end validation)
- Run all existing tests to catch regressions

**Verdict**: Comprehensive testing strategy mitigates this.

---

## Migration Plan

### Pre-Implementation (Verification Phase - 4-6 hours)
1. **Read Source Code** (~2 hours):
   - Complete read of `js_semantic_parser.py` (950 lines)
   - Complete read of `typescript_impl.py` (2000 lines)
   - Read `ast_extractors/__init__.py`
   - Read `indexer/extractors/javascript.py`

2. **Test Hypotheses** (~2 hours):
   - Execute all verifications from `verification.md`
   - Document exact findings (line numbers, signatures)
   - Identify ALL import sites via grep
   - Map ALL function dependencies in typescript_impl.py

3. **Resolve Discrepancies** (~1 hour):
   - Update estimates if actual differs from hypothesis
   - Adjust plan if major discrepancies found
   - Document decisions in verification.md

4. **Approval Gate**: DO NOT PROCEED until Architect and Lead Auditor review verification findings.

---

### Implementation Phase (2-3 hours)

**Step 1: Backup** (5 minutes):
```bash
# Create backup branch
git checkout -b backup/pre-js-parser-refactor
git add .
git commit -m "Backup before js_semantic_parser refactor"
git checkout v1.1  # Return to working branch
```

**Step 2: Move js_semantic_parser.py** (20 minutes):
```bash
# Move file
git mv theauditor/js_semantic_parser.py theauditor/ast_extractors/js_semantic_parser.py

# Update internal imports (if any) to be relative
# Edit: theauditor/ast_extractors/js_semantic_parser.py
#   Change: from theauditor.ast_extractors import js_helper_templates
#   To: from . import js_helper_templates
```

**Step 3: Create Shim** (10 minutes):
```bash
# Create shim at old location
cat > theauditor/js_semantic_parser.py << 'EOF'
"""Backward compatibility shim - imports from new location."""
from theauditor.ast_extractors.js_semantic_parser import (
    JSSemanticParser,
    get_semantic_ast,
    get_semantic_ast_batch,
)

__all__ = ['JSSemanticParser', 'get_semantic_ast', 'get_semantic_ast_batch']
EOF
```

**Step 4: Update ast_extractors/__init__.py** (5 minutes):
```python
# Add to theauditor/ast_extractors/__init__.py
from . import js_semantic_parser
```

**Step 5: Test Move** (15 minutes):
```bash
# Run import test
python -c "
from theauditor.js_semantic_parser import JSSemanticParser as Old
from theauditor.ast_extractors.js_semantic_parser import JSSemanticParser as New
assert Old is New, 'Import shim broken!'
print('✓ Import shim working')
"

# Run basic functionality test
aud index --exclude-self
```

**Step 6: Create typescript_ast_utils.py** (45 minutes):
1. Create new file: `theauditor/ast_extractors/typescript_ast_utils.py`
2. Copy header comment and imports from `typescript_impl.py`
3. Move functions (based on verification.md findings):
   - Low-level helpers: `_strip_comment_prefix`, `_identifier_from_node`, `_canonical_member_name`, `_canonical_callee_from_call`
   - Core extractor: `extract_semantic_ast_symbols`
   - JSX logic: `JSX_NODE_KINDS`, `detect_jsx_in_node`, `extract_jsx_tag_name`, `analyze_create_element_component`, `check_for_jsx`
   - Big algorithms: `build_scope_map`, `build_typescript_function_cfg` (with ALL internal helpers)
4. Add module docstring explaining this is internal implementation layer

**Step 7: Update typescript_impl.py** (30 minutes):
1. Add import: `from . import typescript_ast_utils as ast_utils`
2. Remove moved function definitions
3. Update ALL call sites (based on verification.md call site map):
   - `build_scope_map(...)` → `ast_utils.build_scope_map(...)`
   - `detect_jsx_in_node(...)` → `ast_utils.detect_jsx_in_node(...)`
   - etc. for all moved functions
4. Verify no syntax errors: `python -m py_compile theauditor/ast_extractors/typescript_impl.py`

**Step 8: Test Split** (20 minutes):
```bash
# Verify imports work
python -c "
from theauditor.ast_extractors.typescript_impl import extract_typescript_functions
from theauditor.ast_extractors import typescript_ast_utils
print('✓ Imports successful')
"

# Run indexer on JS/TS project
aud index --exclude-self

# Check for errors in logs
cat .pf/pipeline.log | grep -i error
```

**Step 9: Commit Checkpoint** (5 minutes):
```bash
git add .
git commit -m "refactor(ast): reorganize js_semantic_parser and split typescript_impl

- Move js_semantic_parser.py to ast_extractors/ (logical location)
- Create backward compatibility shim at original location
- Split typescript_impl.py into API layer (1200 lines) and utils layer (800 lines)
- Update ast_extractors/__init__.py to export js_semantic_parser

BACKWARD COMPATIBLE: All existing imports continue working via shim.
"
```

---

### Testing Phase (1-2 hours)

**Test 1: Import Validation** (15 minutes):
Create `tests/test_js_parser_refactor.py`:
```python
"""Test backward compatibility of js_semantic_parser refactor."""

def test_shim_imports():
    """Verify old import location still works via shim."""
    from theauditor.js_semantic_parser import (
        JSSemanticParser,
        get_semantic_ast,
        get_semantic_ast_batch,
    )
    assert JSSemanticParser is not None
    assert callable(get_semantic_ast)
    assert callable(get_semantic_ast_batch)

def test_new_imports():
    """Verify new import location works."""
    from theauditor.ast_extractors.js_semantic_parser import (
        JSSemanticParser,
        get_semantic_ast,
        get_semantic_ast_batch,
    )
    assert JSSemanticParser is not None
    assert callable(get_semantic_ast)
    assert callable(get_semantic_ast_batch)

def test_import_equivalence():
    """Verify old and new imports resolve to same objects."""
    from theauditor.js_semantic_parser import JSSemanticParser as Old
    from theauditor.ast_extractors.js_semantic_parser import JSSemanticParser as New
    assert Old is New, "Shim does not preserve object identity"

def test_typescript_impl_split():
    """Verify typescript_impl can access utils."""
    from theauditor.ast_extractors import typescript_impl
    from theauditor.ast_extractors import typescript_ast_utils

    # Verify impl imports utils
    assert hasattr(typescript_impl, 'ast_utils')

    # Verify utils has expected functions
    assert hasattr(typescript_ast_utils, 'build_scope_map')
    assert hasattr(typescript_ast_utils, 'build_typescript_function_cfg')
```

Run: `pytest tests/test_js_parser_refactor.py -v`

**Test 2: Full Pipeline** (30 minutes):
```bash
# Run on a JavaScript/TypeScript project
cd /path/to/test/project
aud full

# Verify no errors
cat .pf/pipeline.log | grep -i error

# Verify JS/TS files were indexed
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM symbols WHERE file LIKE '%.ts' OR file LIKE '%.js';"
```

**Test 3: Taint Analysis** (15 minutes):
```bash
# Verify taint analysis still works on JS/TS
aud taint-analyze

# Check for JS/TS taint paths
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE tool='taint' AND (file LIKE '%.ts' OR file LIKE '%.js');"
```

**Test 4: Pattern Detection** (15 minutes):
```bash
# Verify pattern rules still work on JS/TS
aud detect-patterns

# Check for JS/TS pattern findings
sqlite3 .pf/repo_index.db "SELECT COUNT(*) FROM findings_consolidated WHERE tool='patterns' AND (file LIKE '%.ts' OR file LIKE '%.js');"
```

**Test 5: Regression Test Suite** (15 minutes):
```bash
# Run ALL existing tests
pytest tests/ -v

# Verify no new failures
```

---

### Rollback Plan

**If ANY test fails**:

```bash
# Option 1: Revert commit
git revert HEAD

# Option 2: Restore from backup branch
git checkout backup/pre-js-parser-refactor
git checkout -b v1.1-rollback
git branch -D v1.1  # Delete failed attempt
git checkout -b v1.1
```

**Reversibility**: Fully reversible via git. No database changes, so no data loss possible.

---

### Success Criteria

✅ **Phase 1 Complete** when:
- [ ] `js_semantic_parser.py` exists at `theauditor/ast_extractors/js_semantic_parser.py`
- [ ] Shim exists at `theauditor/js_semantic_parser.py`
- [ ] `ast_extractors/__init__.py` exports `js_semantic_parser`
- [ ] All imports work from both locations
- [ ] Import test passes
- [ ] Basic `aud index` run succeeds

✅ **Phase 2 Complete** when:
- [ ] `typescript_ast_utils.py` created with ~800 lines
- [ ] `typescript_impl.py` reduced to ~1200 lines
- [ ] All moved functions work in new location
- [ ] All call sites updated to use `ast_utils.` prefix
- [ ] No import errors
- [ ] TypeScript indexing still works

✅ **Refactor Complete** when:
- [ ] All tests pass (import, pipeline, taint, patterns, regression)
- [ ] Both files fit in AI context window (<1500 lines each)
- [ ] Documentation updated
- [ ] Committed to version control
- [ ] Architect and Lead Auditor approve

---

## Open Questions

1. **Q**: Should we add deprecation warnings to the shim?
   **A**: No, not in this change. The shim is intended for long-term backward compatibility, not temporary migration. If we later decide to deprecate, that's a separate proposal.

2. **Q**: Should we update existing consumers to use new import path?
   **A**: No, out of scope. Consumers continue using old path via shim. Updating them is optional and can happen gradually.

3. **Q**: What if we find circular dependencies during verification?
   **A**: Redesign the split to break the cycle. Likely means moving a function to a third module or keeping it in impl.

4. **Q**: What if line counts are way off (e.g., utils is 1500 lines)?
   **A**: Consider splitting utils into two files (typescript_ast_jsx.py for JSX-specific logic). Consult with Architect.

5. **Q**: Should we update CLAUDE.md documentation?
   **A**: Yes, after implementation, update file structure diagrams to reflect new locations. Include in tasks.md.

---

## References

- **teamsop.md**: SOP v4.20 - Verification protocol and reporting standards
- **CLAUDE.md**: Project conventions and architecture patterns
- **openspec/AGENTS.md**: OpenSpec workflow and validation
- **openspec/project.md**: TheAuditor architectural constraints

---

**Document Status**: DRAFT - Awaiting verification findings and approval
