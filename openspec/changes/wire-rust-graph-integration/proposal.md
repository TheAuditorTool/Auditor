# Wire Rust Graph Integration

## Why

Rust extractor exists and works (20 tables, 19 functions) but writes ONLY to Rust-specific tables (`rust_functions`, `rust_structs`, etc.). The graph engine (DFG, CFG, call graph) queries language-agnostic tables (`assignments`, `function_call_args`, `cfg_blocks`) which Rust NEVER populates. Result: Zero graph data for Rust files.

Additionally, four Rust graph strategies exist (`RustTraitStrategy`, `RustAsyncStrategy`, `RustUnsafeStrategy`, `RustFFIStrategy`) but are orphaned - never imported or registered in `DFGBuilder`.

## What Changes

### Phase 1: Extraction Functions (rust_impl.py)
- **ADD** `extract_rust_assignments()` - Populates `assignments` + `assignment_sources` tables
- **ADD** `extract_rust_function_calls()` - Populates `function_call_args` table
- **ADD** `extract_rust_returns()` - Populates `function_returns` + `function_return_sources` tables
- **ADD** `extract_rust_cfg()` - Populates `cfg_blocks` + `cfg_edges` + `cfg_block_statements` tables

### Phase 2: Extractor Integration (rust.py)
- **MODIFY** `RustExtractor.extract()` - Call new extraction functions and return language-agnostic keys

### Phase 3: Strategy Registration (dfg_builder.py)
- **ADD** Import `RustTraitStrategy` from `theauditor/graph/strategies/rust_traits.py`
- **ADD** Import `RustAsyncStrategy` from `theauditor/graph/strategies/rust_async.py`
- **ADD** Register both strategies in `DFGBuilder.__init__()` strategies list

### Phase 4: ZERO FALLBACK Fix (rust_traits.py, rust_async.py)
Remove all 4 table existence checks that violate ZERO FALLBACK policy:

**rust_traits.py:**
- **REMOVE** `rust_traits.py:37-47` - Table check for `rust_impl_blocks`
- **REMOVE** `rust_traits.py:174-179` - Table check for `rust_trait_methods`

**rust_async.py:**
- **REMOVE** `rust_async.py:41-51` - Table check for `rust_async_functions`
- **REMOVE** `rust_async.py:133-138` - Table check for `rust_await_points`

Strategies must CRASH if tables don't exist, not silently return empty.

## Impact

- **Affected Files:**
  - `theauditor/ast_extractors/rust_impl.py` (4 new functions, ~400 lines)
  - `theauditor/indexer/extractors/rust.py` (modify extract() return dict)
  - `theauditor/graph/dfg_builder.py` (2 imports + 2 strategy registrations)
  - `theauditor/graph/strategies/rust_traits.py` (remove 2 table existence checks at lines 37-47, 174-179)
  - `theauditor/graph/strategies/rust_async.py` (remove 2 table existence checks at lines 41-51, 133-138)

- **Downstream Effects:**
  - `aud graph query` returns results for `.rs` files
  - `DFGBuilder.build_unified_flow_graph()` includes Rust data
  - `CFGBuilder` can analyze Rust control flow
  - `XGraphBuilder.build_call_graph()` includes Rust function calls

- **Risk Level:** MEDIUM
  - New extraction functions are additive (no breaking changes)
  - Strategy registration is additive
  - ZERO FALLBACK fix could expose hidden bugs (intentional - fail loud)

## Verification Summary

All hypotheses from the pre-implementation investigation were verified by reading actual source code:

| Hypothesis | Result | Evidence |
|------------|--------|----------|
| Rust extractor populates assignments table | REJECTED | Read rust_impl.py (1187 lines) - no extract_rust_assignments() function |
| Rust extractor populates function_call_args | REJECTED | No function call extraction to language-agnostic tables |
| Rust extractor populates cfg_blocks | REJECTED | No CFG extraction exists |
| DFGBuilder loads Rust strategies | REJECTED | dfg_builder.py:30-36 only loads Python/Node strategies |

Root Cause: Rust extraction was built for Rust-specific metadata extraction (Phase 1), never wired to language-agnostic graph infrastructure (Phase 2 was missing).
