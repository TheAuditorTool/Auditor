# Design: Wire Rust Graph Integration

## Context

TheAuditor's graph engine (DFG, CFG, call graph) is language-agnostic by design. It queries normalized tables (`assignments`, `function_call_args`, `cfg_blocks`) that any language extractor can populate. Python and Node extractors follow this pattern. Rust extractor does not.

**Stakeholders:**
- Graph engine consumers (taint analysis, dead code detection, impact analysis)
- Rust codebase users expecting graph queries to work

**Constraints:**
- Must not break existing Python/Node graph functionality
- Must follow existing extraction patterns (no special-casing in graph engine)
- Must comply with ZERO FALLBACK policy

## Goals / Non-Goals

**Goals:**
- Rust files produce data in language-agnostic graph tables
- DFGBuilder executes Rust-specific strategies
- Graph queries return results for .rs files
- Remove ZERO FALLBACK violations in Rust strategies

**Non-Goals:**
- Modifying graph engine query logic
- Adding Rust-specific tables (already exist)
- Supporting all Rust syntax edge cases (iterative improvement)

## Decisions

### Decision 1: Add extraction functions to rust_impl.py (not new file)

**What:** Add 4 new functions to existing `theauditor/ast_extractors/rust_impl.py`

**Why:**
- Follows existing pattern (all Rust extraction in one file)
- Functions share helper utilities (_get_child_by_type, _get_text, etc.)
- Keeps Rust extraction cohesive

**Alternatives Considered:**
- Create `rust_graph_impl.py` - Rejected: splits Rust logic unnecessarily
- Add to `rust.py` extractor - Rejected: extractor is thin wrapper, extraction logic belongs in rust_impl.py

### Decision 2: Return language-agnostic keys from RustExtractor.extract()

**What:** Modify `theauditor/indexer/extractors/rust.py` to return both rust_* AND language-agnostic keys

**Why:**
- Orchestrator already handles language-agnostic keys (assignments, function_call_args, etc.)
- Storage layer already knows how to persist these
- No changes needed to orchestrator or storage

**Implementation:**
```python
# In RustExtractor.extract()
assignments, assignment_sources = rust_core.extract_rust_assignments(root, file_path)
function_calls = rust_core.extract_rust_function_calls(root, file_path)
returns, return_sources = rust_core.extract_rust_returns(root, file_path)
cfg_blocks, cfg_edges, cfg_statements = rust_core.extract_rust_cfg(root, file_path)

result = {
    # Existing rust_* keys...
    "rust_modules": ...,
    # NEW language-agnostic keys
    "assignments": assignments,
    "assignment_sources": assignment_sources,
    "function_call_args": function_calls,
    "function_returns": returns,
    "function_return_sources": return_sources,
    "cfg_blocks": cfg_blocks,
    "cfg_edges": cfg_edges,
    "cfg_block_statements": cfg_statements,
}
```

### Decision 3: Register only RustTraitStrategy and RustAsyncStrategy initially

**What:** Add 2 of 4 existing Rust strategies to DFGBuilder

**Why:**
- RustTraitStrategy: Trait impl resolution is core to Rust data flow
- RustAsyncStrategy: Async/await flow tracking is essential for modern Rust
- RustUnsafeStrategy/RustFFIStrategy: Lower priority, can add later

**Alternatives Considered:**
- Register all 4 - Rejected: incremental approach, validate 2 work first
- Register none - Rejected: strategies already exist and are tested

### Decision 4: Remove table existence checks (ZERO FALLBACK)

**What:** Remove ALL 4 table existence checks:

| File | Lines | Table Checked |
|------|-------|---------------|
| `rust_traits.py` | 37-47 | `rust_impl_blocks` |
| `rust_traits.py` | 174-179 | `rust_trait_methods` |
| `rust_async.py` | 41-51 | `rust_async_functions` |
| `rust_async.py` | 133-138 | `rust_await_points` |

**Why:**
- ZERO FALLBACK policy: fail loud, not silent
- If tables don't exist, that's a bug to surface, not hide
- Silent empty returns mask configuration/indexing problems

**Before (WRONG):**
```python
# rust_traits.py:37-47
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rust_impl_blocks'")
if not cursor.fetchone():
    return {"nodes": [], "edges": [], ...}  # SILENT FAILURE

# rust_traits.py:174-179
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rust_trait_methods'")
if not cursor.fetchone():
    return  # SILENT FAILURE
```

**After (CORRECT):**
```python
# No check - query directly, let it crash if table missing
# ZERO FALLBACK: Tables MUST exist. If missing, crash to expose the bug.
cursor.execute("SELECT ... FROM rust_impl_blocks ...")
```

### Decision 5: Tree-sitter queries for Rust extraction

**What:** Use tree-sitter node types for extraction, following Python extraction patterns.

**Reference Implementations** (copy these patterns):

| Extraction | Reference File | Function |
|------------|----------------|----------|
| Assignments | `theauditor/ast_extractors/python/core_extractors.py:368-410` | `extract_python_assignments()` |
| Function calls | `theauditor/ast_extractors/python/core_extractors.py:427-500` | `extract_python_calls_with_args()` |
| CFG | `theauditor/ast_extractors/python/cfg_extractor.py:12-200` | `extract_python_cfg()` |

**Assignment extraction:**
- Node type: `let_declaration`
- Pattern child: target variable(s)
- Value child: source expression
- Reference: See `extract_python_assignments()` for dict structure

**Function call extraction:**
- Node type: `call_expression`
- Function child: callee name
- Arguments child: argument list
- Reference: See `extract_python_calls_with_args()` for argument handling

**Return extraction:**
- Node type: `return_expression`
- Expression child: return value
- Also handle implicit returns (last expression without semicolon)

**CFG extraction:**
- Node types: `if_expression`, `match_expression`, `loop_expression`, `while_expression`, `for_expression`
- Build blocks from branch structures
- Connect edges based on control flow
- Reference: See `extract_python_cfg()` for block/edge structure

### Decision 6: Infrastructure Compliance (Fidelity, Logging)

**What:** Ensure new extraction functions comply with recent infrastructure work.

**Fidelity Integration:**
- `rust.py:84` already calls `FidelityToken.attach_manifest(result)`
- This function is **polymorphic** - iterates ALL keys in result dict
- New language-agnostic keys (`assignments`, `function_call_args`, etc.) are **automatically tracked**
- **No additional fidelity code required** - just add keys to result dict

**Why this works:**
```python
# fidelity_utils.py:80-105 - attach_manifest() auto-processes all keys
for key, value in extracted_data.items():
    if key.startswith("_"):
        continue
    token = FidelityToken.create_manifest(value)  # Handles lists/dicts
    if token:
        manifest[key] = token
```

**Logging Pattern:**
- Use `from theauditor.utils.logging import logger`
- Pattern: `logger.debug()` for tracing, `logger.warning()` for recoverable issues
- **No emojis** - Windows CP1252 encoding causes UnicodeEncodeError

**Guards (Automatic):**
Storage layer enforces via `reconcile_fidelity()` in `theauditor/indexer/fidelity.py`:
- LEGACY FORMAT VIOLATION: Rejects int format
- TRANSACTION MISMATCH: tx_id echo verification
- SCHEMA VIOLATION: Column preservation check
- COUNT CHECK: Row count verification

**Rich CLI:**
- Not applicable - extraction functions don't interact with CLI
- Rich is in `pipeline/renderer.py` for display only

## Risks / Trade-offs

### Risk 1: Implicit returns in Rust
**Risk:** Rust functions can return without `return` keyword (last expression)
**Mitigation:** Track function body's last expression if no semicolon
**Trade-off:** May miss some implicit returns initially - iterative improvement

### Risk 2: Complex destructuring patterns
**Risk:** Rust has complex patterns: `let (Some(x), [a, b, ..]) = ...`
**Mitigation:** Start with simple patterns, log warnings for complex ones
**Trade-off:** Incomplete extraction initially, but no false positives

### Risk 3: Method call resolution
**Risk:** `receiver.method()` - callee is "method" but full path unknown without type info
**Mitigation:** Extract method name only (matches Python/Node behavior)
**Trade-off:** Less precise than full type resolution, but consistent

### Risk 4: ZERO FALLBACK fix exposes bugs
**Risk:** Removing table checks may crash on repos not fully indexed
**Mitigation:** This is intentional - crash exposes the bug
**Trade-off:** Short-term pain for long-term correctness

## Migration Plan

**No migration needed.** Changes are additive:
1. New extraction functions don't affect existing data
2. New keys in extract() result are handled by existing storage
3. Strategy registration is additive to strategies list
4. ZERO FALLBACK fix only affects error handling

**Rollback:** `git revert <commit_hash>` - fully reversible

## Open Questions

1. **Q: Should we register RustUnsafeStrategy and RustFFIStrategy too?**
   A: Defer to Phase 2 - validate core strategies work first

2. **Q: How to handle macro-generated code?**
   A: Out of scope - macros expand at compile time, tree-sitter sees unexpanded source

3. **Q: Should implicit returns be in function_returns or separate table?**
   A: Same table - return is a return, explicit or implicit
