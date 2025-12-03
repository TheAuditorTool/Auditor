# Verification Report

## Summary

All pre-implementation hypotheses were verified by reading actual source code. This document provides the evidence.

---

## Hypothesis 1: Rust extractor does NOT populate assignments table

**Result**: CONFIRMED

**Evidence**: Read `theauditor/ast_extractors/rust_impl.py` (1187 lines)

Grep for assignment-related functions:
```
$ grep "def extract_rust" rust_impl.py
```

Found 20 extraction functions, NONE of which populate language-agnostic tables:
- `extract_rust_modules` (line 73)
- `extract_rust_use_statements` (line 113)
- `extract_rust_functions` (line 236)
- `extract_rust_structs` (line 293)
- `extract_rust_enums` (line 335)
- `extract_rust_traits` (line 370)
- `extract_rust_impl_blocks` (line 424)
- `extract_rust_struct_fields` (line 491)
- `extract_rust_enum_variants` (line 554)
- `extract_rust_trait_methods` (line 606)
- `extract_rust_macros` (line 654)
- `extract_rust_macro_invocations` (line 678)
- `extract_rust_async_functions` (line 725)
- `extract_rust_await_points` (line 769)
- `extract_rust_unsafe_blocks` (line 809)
- `extract_rust_unsafe_traits` (line 952)
- `extract_rust_extern_blocks` (line 997)
- `extract_rust_extern_functions` (line 1026)
- `extract_rust_generics` (line 1080)
- `extract_rust_lifetimes` (line 1152)

**Missing functions** (required for graph integration):
- `extract_rust_assignments` - DOES NOT EXIST
- `extract_rust_function_calls` - DOES NOT EXIST
- `extract_rust_returns` - DOES NOT EXIST
- `extract_rust_cfg` - DOES NOT EXIST

---

## Hypothesis 2: RustExtractor only returns rust_* keys

**Result**: CONFIRMED

**Evidence**: Read `theauditor/indexer/extractors/rust.py` (84 lines)

```python
# rust.py:52-73
result = {
    "rust_modules": rust_core.extract_rust_modules(root, file_path),
    "rust_use_statements": rust_core.extract_rust_use_statements(root, file_path),
    "rust_functions": rust_core.extract_rust_functions(root, file_path),
    "rust_structs": rust_core.extract_rust_structs(root, file_path),
    "rust_enums": rust_core.extract_rust_enums(root, file_path),
    "rust_traits": rust_core.extract_rust_traits(root, file_path),
    "rust_impl_blocks": rust_core.extract_rust_impl_blocks(root, file_path),
    "rust_generics": rust_core.extract_rust_generics(root, file_path),
    "rust_lifetimes": rust_core.extract_rust_lifetimes(root, file_path),
    "rust_macros": rust_core.extract_rust_macros(root, file_path),
    "rust_macro_invocations": rust_core.extract_rust_macro_invocations(root, file_path),
    "rust_async_functions": rust_core.extract_rust_async_functions(root, file_path),
    "rust_await_points": rust_core.extract_rust_await_points(root, file_path),
    "rust_unsafe_blocks": rust_core.extract_rust_unsafe_blocks(root, file_path),
    "rust_unsafe_traits": rust_core.extract_rust_unsafe_traits(root, file_path),
    "rust_struct_fields": rust_core.extract_rust_struct_fields(root, file_path),
    "rust_enum_variants": rust_core.extract_rust_enum_variants(root, file_path),
    "rust_trait_methods": rust_core.extract_rust_trait_methods(root, file_path),
    "rust_extern_functions": rust_core.extract_rust_extern_functions(root, file_path),
    "rust_extern_blocks": rust_core.extract_rust_extern_blocks(root, file_path),
}
```

**Missing keys** (required for graph integration):
- `assignments` - NOT RETURNED
- `assignment_sources` - NOT RETURNED
- `function_call_args` - NOT RETURNED
- `function_returns` - NOT RETURNED
- `function_return_sources` - NOT RETURNED
- `cfg_blocks` - NOT RETURNED
- `cfg_edges` - NOT RETURNED
- `cfg_block_statements` - NOT RETURNED

---

## Hypothesis 3: DFGBuilder does NOT load Rust strategies

**Result**: CONFIRMED

**Evidence**: Read `theauditor/graph/dfg_builder.py:13-36`

```python
# dfg_builder.py:13-18 - Imports
from .strategies.bash_pipes import BashPipeStrategy
from .strategies.interceptors import InterceptorStrategy
from .strategies.node_express import NodeExpressStrategy
from .strategies.node_orm import NodeOrmStrategy
from .strategies.python_orm import PythonOrmStrategy
from .types import DFGEdge, DFGNode, create_bidirectional_edges

# dfg_builder.py:30-36 - Strategy list
self.strategies = [
    PythonOrmStrategy(),
    NodeOrmStrategy(),
    NodeExpressStrategy(),
    InterceptorStrategy(),
    BashPipeStrategy(),
]
```

**Missing imports**:
- `from .strategies.rust_traits import RustTraitStrategy` - NOT IMPORTED
- `from .strategies.rust_async import RustAsyncStrategy` - NOT IMPORTED

**Missing registrations**:
- `RustTraitStrategy()` - NOT IN LIST
- `RustAsyncStrategy()` - NOT IN LIST

---

## Hypothesis 4: Rust strategies have ZERO FALLBACK violations

**Result**: CONFIRMED - Found 4 violations (not 2)

### rust_traits.py - Violation 1

**Location**: `theauditor/graph/strategies/rust_traits.py:37-47`

```python
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='rust_impl_blocks'
""")
if not cursor.fetchone():
    conn.close()
    return {
        "nodes": [],
        "edges": [],
        "metadata": {"graph_type": "rust_traits", "stats": stats},
    }
```

### rust_traits.py - Violation 2

**Location**: `theauditor/graph/strategies/rust_traits.py:174-179`

```python
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='rust_trait_methods'
""")
if not cursor.fetchone():
    return
```

### rust_async.py - Violation 1

**Location**: `theauditor/graph/strategies/rust_async.py:41-51`

```python
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='rust_async_functions'
""")
if not cursor.fetchone():
    conn.close()
    return {
        "nodes": [],
        "edges": [],
        "metadata": {"graph_type": "rust_async", "stats": stats},
    }
```

### rust_async.py - Violation 2

**Location**: `theauditor/graph/strategies/rust_async.py:133-138`

```python
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='rust_await_points'
""")
if not cursor.fetchone():
    return
```

---

## Root Cause Analysis

The Rust extractor was designed for **Rust-specific metadata extraction** (Phase 1 of language support). The language-agnostic graph infrastructure (Phase 2) was never wired up:

1. **rust_impl.py** - Extracts Rust AST data into rust_* tables (structs, traits, impls, etc.)
2. **rust.py** - Thin wrapper that calls rust_impl functions and returns rust_* keys
3. **DFGBuilder** - Only loads Python/Node strategies, ignores existing Rust strategies
4. **RustTraitStrategy/RustAsyncStrategy** - Exist but are orphaned (never imported/registered)

The fix is additive: add new extraction functions, return new keys, register strategies, remove fallbacks.
