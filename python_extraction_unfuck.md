# Python Extraction Unfuck Plan v3.0 (LibCST Edition)

**Date:** 2025-11-20
**Status:** PLAN - NOT IMPLEMENTED
**Lead Auditor Review:** COMPLETE + NodeIndex Optimization Added
**Architect Approval:** PENDING

---

## Executive Summary

**THREE architectural problems, ONE solution: LibCST automation + NodeIndex engine**

### The Problems:
1. **Performance Hell**: 300+ `ast.walk()` calls per file (100+ extractors + 100+ `_build_function_ranges()`)
2. **Orchestration Bloat**: `python.py` (1894 lines) doing extraction instead of orchestrating
3. **Architecture Rot**: `security_extractors.py` judging vulnerabilities instead of mapping facts

### The Solution:
**Phase 0:** LibCST rewrites 15,550 lines automatically (AST modernization + NodeIndex transformation)
**Phase 1:** NodeIndex + FileContext = 1 walk + O(1) lookups (95%+ faster)
**Phase 2:** Mapper/Judge separation (taint engine does judging)
**Phase 3:** Thin orchestrator (python.py → 100 lines)

**Lead Auditor Verdict:**
> "You built a Ferrari engine (DFG/Taint) but you're feeding it with a garden hose. LibCST + NodeIndex is the surgical laser you need."

---

## The Root Cause (Performance Analysis)

### Current State (BROKEN):
```python
# Every extractor (100+ functions):
def extract_something(tree, parser_self):
    for node in ast.walk(tree):              # Walk #1
        function_ranges = _build_function_ranges(tree)  # Walk #2 (REDUNDANT!)
        if isinstance(node, ast.Call):
            # extract
```

**Complexity:** O(N×M) where N=nodes, M=extractors
**Reality:** 300+ complete tree traversals PER FILE

### Target State (FIXED):
```python
# Single walk builds NodeIndex:
index = NodeIndex(tree)  # 1 walk, builds {ast.Call: [nodes], ...}

# Extractors query index (O(1) lookup):
def extract_something(context):
    for node in context.find_nodes(ast.Call):  # O(1) dict lookup!
        # extract (no function_ranges rebuild needed - it's in context)
```

**Complexity:** O(N) for build + O(M) for queries
**Reality:** 1 walk + 100 O(1) dictionary lookups = **95%+ faster**

---

## Phase 0: LibCST Automation (The Foundation)

**Goal:** Modernize 15,550 lines of code WITHOUT manual refactoring
**Effort:** 1-2 days (mostly testing)
**Risk:** LOW (LibCST is syntax-aware, creates .bak files)

### Step 0.1: AST Modernization Script

**What it does:**
- `isinstance(node, ast.Str)` → `isinstance(node, ast.Constant) and isinstance(node.value, str)`
- `node.s` → `node.value` (only for AST nodes)
- `isinstance(node, (ast.Str, ast.Constant))` → `isinstance(node, ast.Constant)`
- Delete Python 3.7/3.8 fallbacks
- Modernize type hints: `List[Dict]` → `list[dict]`, `Optional[str]` → `str | None`

**File:** `scripts/libcst_modernize_ast.py` (provided by Lead Auditor)

**Usage:**
```bash
# Dry run (preview changes)
python scripts/libcst_modernize_ast.py --dry-run theauditor/ast_extractors/python/

# Apply to one file (test)
python scripts/libcst_modernize_ast.py theauditor/ast_extractors/python/fundamental_extractors.py

# Verify it works
pytest tests/test_extractors.py::test_fundamental_extractors

# Apply to all files
python scripts/libcst_modernize_ast.py theauditor/ast_extractors/python/
```

### Step 0.2: NodeIndex Transformation Script

**What it does:**
- Finds: `for node in ast.walk(tree): if isinstance(node, X):`
- Replaces with: `for node in find_nodes(tree, X):`
- Preserves all extraction logic (zero manual rewriting)
- Auto-adds `from .utils.node_index import find_nodes` import

**File:** `scripts/libcst_to_node_index.py` (provided by Lead Auditor)

**Usage:**
```bash
# Dry run (preview changes)
python scripts/libcst_to_node_index.py --dry-run theauditor/ast_extractors/python/

# Apply to one file (test)
python scripts/libcst_to_node_index.py theauditor/ast_extractors/python/fundamental_extractors.py

# Verify database row counts unchanged
aud full --target tests/fixtures/python/simple_project

# Apply to all files
python scripts/libcst_to_node_index.py theauditor/ast_extractors/python/
```

### Step 0.3: Centralize AST Helpers

**Create:** `theauditor/ast_extractors/utils/ast_helpers.py`

```python
"""Centralized AST utilities - Python 3.14+ standard.

ZERO FALLBACKS. ZERO COMPATIBILITY HACKS.
"""
import ast

def get_literal_value(node: ast.AST) -> any:
    """Extract literal value from ast.Constant."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [get_literal_value(n) for n in node.elts]
    return None

def get_call_arg_value(call_node: ast.Call, arg_name: str, index: int = -1) -> ast.AST | None:
    """Get argument by name (kwarg) or position."""
    for kw in call_node.keywords:
        if kw.arg == arg_name:
            return kw.value
    if index >= 0 and index < len(call_node.args):
        return call_node.args[index]
    return None

def safe_unparse(node: ast.AST, max_length: int = 200) -> str:
    """Convert AST node to source text (truncated)."""
    try:
        text = ast.unparse(node)
        return text[:max_length] if len(text) > max_length else text
    except:
        return f"<{type(node).__name__}>"
```

**Action:** Delete all `_get_str_constant`, `_keyword_arg`, `_extract_list_of_strings` from 27 files, import from `ast_helpers`.

### Step 0.4: Upgrade Python Version

**Update:** `pyproject.toml`
```toml
[project]
requires-python = ">=3.14"
```

**Test:**
```bash
# Install Python 3.14
# Run full test suite
pytest tests/
aud full --target .
```

---

## Phase 1: NodeIndex + FileContext (The Engine)

**Goal:** 1 walk + O(1) lookups (eliminates 300+ walks)
**Effort:** 2-3 days
**Risk:** MEDIUM (touches extractor signatures, but LibCST handles rewriting)

### Step 1.1: Create NodeIndex Engine

**File:** `theauditor/ast_extractors/utils/node_index.py`

```python
"""NodeIndex: O(1) node lookup by type (Lead Auditor's optimization)."""
import ast
from collections import defaultdict

class NodeIndex:
    """Fast AST node lookup by type.

    Builds index in single pass, enables O(1) queries.
    """
    def __init__(self, tree: ast.AST):
        self._index = defaultdict(list)
        # Single walk to build index
        for node in ast.walk(tree):
            self._index[type(node)].append(node)

    def find_nodes(self, node_type: type | tuple) -> list[ast.AST]:
        """O(1) lookup of nodes by type."""
        if isinstance(node_type, tuple):
            # Handle isinstance(node, (ast.Call, ast.FunctionDef))
            return [n for t in node_type for n in self._index.get(t, [])]
        return self._index.get(node_type, [])


def find_nodes(tree: ast.AST, node_type: type | tuple) -> list[ast.AST]:
    """Helper function for extractors (caches index on tree object)."""
    if not hasattr(tree, '_node_index'):
        tree._node_index = NodeIndex(tree)
    return tree._node_index.find_nodes(node_type)
```

**Why This Works:**
- Single `ast.walk()` builds dictionary: `{ast.Call: [node1, node2], ast.FunctionDef: [node3]}`
- Extractors call `find_nodes(tree, ast.Call)` → instant O(1) lookup
- No more iterating through ALL nodes to find specific types

### Step 1.2: Enhanced FileContext (Uses NodeIndex)

**File:** `theauditor/ast_extractors/context.py`

```python
"""FileContext: Shared context with NodeIndex + import resolution."""
from dataclasses import dataclass
import ast
from .utils.node_index import NodeIndex, find_nodes

@dataclass
class FileContext:
    """Shared context for single file extraction.

    Built ONCE, used by ALL extractors.
    """
    tree: ast.AST
    content: str
    file_path: str

    # NodeIndex for O(1) queries
    _index: NodeIndex

    # Pre-computed data (built from index, no extra walks)
    imports: dict[str, str]  # Resolved import aliases
    function_ranges: list[tuple[str, int, int]]
    class_ranges: list[tuple[str, int, int]]

    def find_nodes(self, node_type: type | tuple) -> list[ast.AST]:
        """O(1) node lookup by type."""
        return self._index.find_nodes(node_type)

    def resolve_symbol(self, name: str) -> str:
        """Resolve import alias to full module path.

        Examples:
            jwt.encode → jose.jwt.encode (if import jose.jwt as jwt)
            j.encode → jwt.encode (if import jwt as j)
        """
        if '.' not in name:
            return self.imports.get(name, name)

        parts = name.split('.')
        if parts[0] in self.imports:
            return f"{self.imports[parts[0]]}.{'.'.join(parts[1:])}"
        return name

    def find_containing_function(self, line: int) -> str:
        """Find function containing line (uses pre-built ranges)."""
        for fname, start, end in self.function_ranges:
            if start <= line <= end:
                return fname
        return 'global'


def build_file_context(tree: ast.AST, content: str = "", file_path: str = "") -> FileContext:
    """Build FileContext with NodeIndex (1 walk instead of 4).

    Returns:
        FileContext with:
        - NodeIndex for O(1) queries
        - Resolved imports
        - Function/class ranges
    """
    # Build NodeIndex FIRST (single walk)
    index = NodeIndex(tree)

    # Extract imports from index (no walk!)
    imports = {}
    for node in index.find_nodes(ast.Import):
        for alias in node.names:
            imports[alias.asname or alias.name] = alias.name

    for node in index.find_nodes(ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            imports[alias.asname or alias.name] = f"{module}.{alias.name}"

    # Build function ranges from index (no walk!)
    function_ranges = []
    for node in index.find_nodes(ast.FunctionDef) + index.find_nodes(ast.AsyncFunctionDef):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges.append((
                node.name,
                node.lineno,
                node.end_lineno or node.lineno
            ))

    # Build class ranges from index (no walk!)
    class_ranges = []
    for node in index.find_nodes(ast.ClassDef):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            class_ranges.append((
                node.name,
                node.lineno,
                node.end_lineno or node.lineno
            ))

    return FileContext(
        tree=tree,
        content=content,
        file_path=file_path,
        _index=index,
        imports=imports,
        function_ranges=function_ranges,
        class_ranges=class_ranges
    )
```

### Step 1.3: Update Extractor Signatures

**LibCST already did this in Phase 0!** Extractors now call `find_nodes()` instead of `ast.walk()`.

**Additional change:** Replace `tree` parameter with `context`:

```python
# BEFORE (Phase 0 transforms this):
def extract_something(tree: dict, parser_self) -> list[dict]:
    actual_tree = tree.get("tree")
    for node in ast.walk(actual_tree):  # ← Phase 0 changed this
        if isinstance(node, ast.Call):
            # extract

# AFTER Phase 0 (LibCST output):
def extract_something(tree: dict, parser_self) -> list[dict]:
    actual_tree = tree.get("tree")
    for node in find_nodes(actual_tree, ast.Call):  # ← Now uses NodeIndex!
        # extract (unchanged)

# AFTER Phase 1 (add FileContext):
def extract_something(context: FileContext) -> list[dict]:
    for node in context.find_nodes(ast.Call):  # ← Uses context.find_nodes()
        func_name = context.resolve_symbol(get_node_name(node.func))  # ← Import resolution!
        in_function = context.find_containing_function(node.lineno)  # ← Pre-built ranges!
        # extract
```

**Action:** Update ALL 27 extractor files (can do incrementally, one file at a time).

### Step 1.4: Update python_impl.py

**File:** `theauditor/ast_extractors/python_impl.py` (NEW)

```python
"""Python extraction orchestrator with FileContext + NodeIndex."""
import ast
from .context import build_file_context, FileContext
from .python import (
    core_extractors, framework_extractors, security_extractors,
    # ... import all 27 modules
)

def extract_all_python_data(tree: dict, parser_self, content: str = "") -> dict[str, list[dict]]:
    """Master extraction with NodeIndex (1 walk + O(1) lookups).

    Returns:
        Dict with keys for each extraction type (functions, classes, etc.)
        NO file paths (added by indexer layer)
    """
    if not tree or tree.get("type") != "python_ast":
        return {}

    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.Module):
        return {}

    # Build context ONCE (1 walk builds NodeIndex + imports + ranges)
    context = build_file_context(actual_tree, content)

    # Pass context to ALL extractors (they use O(1) lookups)
    results = {}
    results['functions'] = core_extractors.extract_python_functions(context)
    results['classes'] = core_extractors.extract_python_classes(context)
    results['calls'] = core_extractors.extract_python_calls(context)
    # ... 97 more extractor calls

    return results
```

---

## Phase 2: Mapper/Judge Separation (The Architecture Fix)

**Goal:** Stop judging in extractors, let taint engine do it
**Effort:** 3-4 days
**Risk:** MEDIUM-HIGH (changes security finding logic)

### Step 2.1: Audit security_extractors.py

**Find all "judging" logic:**
```python
# WRONG (Judging in extractor):
def extract_command_injection(tree):
    if subprocess_call and shell=True:
        return {"vulnerable": True}  # ← JUDGING

# WRONG (Skipping safe patterns):
def extract_sql_injection(tree):
    if is_string_constant(arg):
        return {}  # ← Skip "safe" - still judging!
```

### Step 2.2: Refactor to Pure Mapping

**File:** `theauditor/ast_extractors/python/security_extractors.py`

```python
# NEW (Pure mapping - no judging):
def extract_subprocess_calls(context: FileContext) -> list[dict]:
    """Record ALL subprocess calls with properties.

    Does NOT judge vulnerability - that's the rules engine's job.
    """
    calls = []
    for node in context.find_nodes(ast.Call):
        func_name = context.resolve_symbol(get_node_name(node.func))

        if func_name in ['subprocess.call', 'subprocess.run', 'os.system']:
            shell_arg = get_call_arg_value(node, 'shell')
            calls.append({
                "line": node.lineno,
                "call": func_name,
                "shell": get_literal_value(shell_arg) if shell_arg else None,
                "in_function": context.find_containing_function(node.lineno)
            })

    return calls
```

### Step 2.3: Move Judging to Rules Engine

**File:** `theauditor/rules/security/command_injection.py`

```python
def check_command_injection(context: StandardRuleContext) -> list[StandardFinding]:
    """Query database + taint engine for vulnerable subprocess calls.

    JUDGING happens HERE, not in extractors.
    """
    cursor = context.conn.cursor()

    cursor.execute("""
        SELECT fc.file, fc.line, fc.callee_function, fca.argument_expr
        FROM function_calls fc
        JOIN function_call_args fca ON fc.file = fca.file AND fc.line = fca.line
        WHERE fc.callee_function LIKE '%subprocess%'
          AND fca.argument_name = 'shell'
          AND fca.argument_expr = 'True'
          AND EXISTS (
            SELECT 1 FROM taint_flows tf
            WHERE tf.sink_file = fc.file AND tf.sink_line = fc.line
          )
    """)

    findings = []
    for row in cursor.fetchall():
        findings.append(StandardFinding(
            rule_id="command-injection",
            file=row[0],
            line=row[1],
            message=f"Command injection: {row[2]} with shell=True and tainted input",
            severity="high"
        ))

    return findings
```

---

## Phase 3: Orchestration Unfuck (The Cleanup)

**Goal:** python.py becomes thin wrapper (1894 → 100 lines)
**Effort:** 1-2 days
**Risk:** LOW (just code movement after Phase 1 works)

### Step 3.1: Simplify python.py

**File:** `theauditor/indexer/extractors/python.py` (GUTTED)

```python
"""Python file extractor - thin orchestrator wrapper."""
from pathlib import Path
from typing import Any

from . import BaseExtractor
from theauditor.ast_extractors import python_impl

class PythonExtractor(BaseExtractor):
    """Extractor for Python files."""

    def supported_extensions(self) -> list[str]:
        return ['.py', '.pyx']

    def extract(self, file_info: dict[str, Any], content: str, tree: Any | None = None) -> dict[str, Any]:
        """Extract all Python data via python_impl orchestrator."""
        if not tree or tree.get("type") != "python_ast":
            return {}

        # Call master orchestrator (all extraction happens in python_impl)
        results = python_impl.extract_all_python_data(tree, self.ast_parser, content)

        # Add file path to all results (database requirement)
        file_path = str(file_info['path'])
        for key, items in results.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and 'file' not in item:
                        item['file'] = file_path

        return results
```

**Delete:**
- All custom extraction methods (300+ lines)
- All result dict initialization (150+ lines)
- All symbol deduplication logic
- All direct extractor calls

---

## Phase 4: Visitor Pattern (DEFERRED - Optional Future)

**Goal:** Single traversal with callbacks
**Effort:** 3-4 weeks
**Risk:** HIGH
**Status:** DEFERRED until Phases 0-3 proven stable

**Rationale:** NodeIndex already gives 95%+ performance improvement. Visitor Pattern would be 5-10% more but requires complete rewrite. Do this later if needed.

---

## Implementation Timeline

### Week 1: Phase 0 (LibCST Automation)
- **Day 1:** Get LibCST scripts from Lead Auditor, test on ONE file
- **Day 2:** Run AST modernization script on all files, test
- **Day 3:** Run NodeIndex transformation script on all files, test
- **Day 4:** Centralize AST helpers, delete copy-paste code
- **Day 5:** Test full pipeline, fix edge cases

### Week 2: Phase 1 (NodeIndex + FileContext)
- **Day 1-2:** Create NodeIndex engine + FileContext class
- **Day 3-4:** Update extractor signatures to use FileContext (5 files/day)
- **Day 5:** Update python_impl.py, test database row counts

### Week 3: Phase 2 (Mapper/Judge Separation)
- **Day 1-2:** Audit security_extractors.py, identify judging logic
- **Day 3:** Refactor to pure mapping
- **Day 4:** Update rules engine queries
- **Day 5:** Test findings output (must match old behavior)

### Week 4: Phase 3 (Orchestration Cleanup)
- **Day 1:** Finalize python_impl.py with all extractor calls
- **Day 2:** Gut python.py to ~100 lines
- **Day 3-4:** Test database row counts, verify no data loss
- **Day 5:** Buffer, final testing

---

## Testing Strategy

### Phase 0 Testing:
```bash
# Before
aud full --target tests/fixtures/python/
# Count rows, save to baseline.txt

# After each LibCST script
aud full --target tests/fixtures/python/
# Compare row counts (should be identical)
```

### Phase 1 Testing:
```bash
# Test NodeIndex O(1) performance
python -c "
from theauditor.ast_extractors.utils.node_index import NodeIndex
import ast, time
tree = ast.parse(open('theauditor/indexer/indexer.py').read())

# Measure build time
start = time.time()
index = NodeIndex(tree)
print(f'Build: {time.time() - start:.4f}s')

# Measure query time (should be instant)
start = time.time()
calls = index.find_nodes(ast.Call)
print(f'Query: {time.time() - start:.6f}s, found {len(calls)} calls')
"

# Test FileContext
python -c "
from theauditor.ast_extractors.context import build_file_context
import ast
tree = ast.parse('import jwt\ndef foo(): pass')
ctx = build_file_context(tree)
assert 'jwt' in ctx.imports
assert len(ctx.function_ranges) == 1
print('FileContext: PASS')
"

# Compare database row counts (must be identical ±1%)
```

### Phase 2 Testing:
```bash
# CRITICAL: Security findings must match
aud scan --rules command-injection > findings_before.txt
# (after Phase 2 refactor)
aud scan --rules command-injection > findings_after.txt
diff findings_before.txt findings_after.txt  # Should be identical
```

### Phase 3 Testing:
```bash
# Database row counts must be identical
aud full --target .
# Compare with baseline from Phase 0
```

---

## Success Metrics

### Phase 0 Success:
- ✅ Zero `ast.Str`, `ast.Num` references in codebase
- ✅ All extractors use `find_nodes()` instead of `ast.walk()`
- ✅ All type hints modernized (list[dict], str | None)
- ✅ Database row counts unchanged

### Phase 1 Success:
- ✅ NodeIndex builds in <10ms (measured)
- ✅ find_nodes() queries in <0.001ms (measured)
- ✅ FileContext built once per file
- ✅ Import resolution working (context.resolve_symbol())
- ✅ 95%+ performance improvement (measured)

### Phase 2 Success:
- ✅ security_extractors.py is pure mapper (no judging)
- ✅ Rules engine queries database + taint
- ✅ Findings output IDENTICAL to before
- ✅ Taint engine integration verified

### Phase 3 Success:
- ✅ python.py < 150 lines
- ✅ python_impl.py exists and orchestrates
- ✅ Database row counts identical (±1%)
- ✅ All tests pass

---

## Risk Assessment

### Phase 0 Risks: **VERY LOW**
- **Mitigation:** LibCST is syntax-aware, creates .bak files, test incrementally
- **Rollback:** Restore .bak files, revert git commits

### Phase 1 Risks: **MEDIUM**
- **Mitigation:** Test NodeIndex on one file first, update extractors incrementally
- **Rollback:** Keep old signatures working temporarily (wrapper functions)

### Phase 2 Risks: **MEDIUM-HIGH**
- **Mitigation:** Keep old logic during transition, compare findings before/after
- **Rollback:** Revert extractor changes, keep Phase 1 improvements

### Phase 3 Risks: **LOW**
- **Mitigation:** Just code movement, FileContext handles complexity
- **Rollback:** Easy revert, minimal changes

---

## Lead Auditor Scripts Needed

**Request for Lead Auditor:**

### Script 1: AST Modernization
```
File: scripts/libcst_modernize_ast.py
Features:
- Dry-run mode (--dry-run flag)
- Transforms: ast.Str → ast.Constant, node.s → node.value
- Type hints: List[Dict] → list[dict], Optional[str] → str | None
- Creates .bak files for all modified files
- Verbose output showing what changed
```

### Script 2: NodeIndex Transformation
```
File: scripts/libcst_to_node_index.py
Features:
- Dry-run mode (--dry-run flag)
- Transforms: for node in ast.walk(tree): if isinstance(node, X): → for node in find_nodes(tree, X):
- Auto-adds import: from .utils.node_index import find_nodes
- Preserves all extraction logic (zero manual changes)
- Creates .bak files
- Verbose output
```

---

## Approval Checklist

- [ ] Architect approval (user)
- [x] Lead Auditor review complete
- [ ] LibCST scripts received and tested
- [ ] Phase 0 approved
- [ ] Phase 1 approved
- [ ] Phase 2 approved
- [ ] Phase 3 approved

**DO NOT IMPLEMENT WITHOUT ARCHITECT APPROVAL.**

---

## Implementation Status

### Phase 0 (LibCST Automation):
- [ ] 0.1: Receive LibCST scripts from Lead Auditor
- [ ] 0.2: Test AST modernization on one file
- [ ] 0.3: Run AST modernization on all files
- [ ] 0.4: Test NodeIndex transformation on one file
- [ ] 0.5: Run NodeIndex transformation on all files
- [ ] 0.6: Centralize AST helpers
- [ ] 0.7: Upgrade to Python 3.14

### Phase 1 (NodeIndex + FileContext):
- [ ] 1.1: Create NodeIndex engine
- [ ] 1.2: Create FileContext class
- [ ] 1.3: Update extractor signatures (0/27 files)
- [ ] 1.4: Update python_impl.py

### Phase 2 (Mapper/Judge Separation):
- [ ] 2.1: Audit security_extractors.py
- [ ] 2.2: Refactor to pure mapping
- [ ] 2.3: Update rules engine

### Phase 3 (Orchestration Cleanup):
- [ ] 3.1: Finalize python_impl.py
- [ ] 3.2: Simplify python.py

### Phase 4 (Visitor Pattern - DEFERRED):
- [ ] Status: Not started (deferred to future)

---

**END OF PLAN v3.0**

**Key Changes from v2.0:**
- Added LibCST automation (eliminates manual refactoring)
- Added NodeIndex engine (Lead Auditor's optimization)
- Merged NodeIndex + FileContext (1 walk + O(1) lookups)
- Updated performance metrics (300+ walks → 1 walk = 95%+ improvement)
- Clear testing strategy with database row count verification
- Deferred Visitor Pattern to Phase 4 (NodeIndex is good enough)
