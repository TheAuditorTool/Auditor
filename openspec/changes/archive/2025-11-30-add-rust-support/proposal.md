# Rust Language Support Proposal

> **Version**: 2.0 (Revised)
> **Last Updated**: 2025-11-29
> **Status**: Ready for Implementation

## Why

Rust support does not exist in TheAuditor. Zero `rust_*` tables exist, zero Rust symbols stored, zero graph strategies for Rust patterns. TheAuditor misses critical Rust constructs: `impl` blocks, traits, generics, lifetimes, macros, `unsafe` blocks, async/await.

For a static analysis tool claiming polyglot support, this is a credibility gap. Rust codebases are increasingly common in security-critical infrastructure (crypto, networking, systems). TheAuditor needs complete Rust support across all three layers:

1. **Indexer Layer** - Extract and store Rust code facts
2. **Graph Layer** - Build data flow and analysis graphs
3. **Rules Layer** - Detect security vulnerabilities

Without the graph layer, SAST cannot function - there's no way to trace data flow or resolve method calls.

## What Changes

### Phase 1: Indexer Foundation
**Spec**: `specs/indexer/spec.md`

| Component | File | Pattern |
|-----------|------|---------|
| AST Extraction | `ast_extractors/rust/__init__.py`, `core.py` | `hcl_impl.py` |
| Schema | `schemas/rust_schema.py` | `python_schema.py` |
| Extractor | `extractors/rust.py` | `python.py` |
| Storage | `storage/rust_storage.py` | `python_storage.py` |

**Tables Created**: 7 core tables (Phase 1)
- `rust_modules`, `rust_use_statements`, `rust_functions`
- `rust_structs`, `rust_enums`, `rust_traits`, `rust_impl_blocks`

**Modifications**:
- `ast_parser.py` - Add `.rs` extension mapping (line 241-252) and Rust parser init (after line 96)
- `schema.py` - Import RUST_TABLES, update table count 170 → 177 (Phase 1)
- `storage/__init__.py` - Register RustStorage

**Deliverable**: `aud full --index` processes `.rs` files

### Phase 2: Advanced Extraction
**Spec**: `specs/indexer/spec.md` Section 6.2

**Tables Created**: 13 additional tables
- Generics: `rust_generics`, `rust_lifetimes`
- Macros: `rust_macros`, `rust_macro_invocations`
- Async: `rust_async_functions`, `rust_await_points`
- Unsafe: `rust_unsafe_blocks`, `rust_unsafe_traits`
- FFI: `rust_extern_functions`, `rust_extern_blocks`
- Relationships: `rust_struct_fields`, `rust_enum_variants`, `rust_trait_methods`

**Module Resolution** (CRITICAL for SAST):
- Build per-file alias map from `use` statements
- Store canonical paths alongside local names
- Enable cross-file symbol resolution

**Deliverable**: All 20 rust_* tables populated correctly

### Phase 3: Graph Layer
**Spec**: `specs/graph/spec.md`

| Strategy | File | Purpose |
|----------|------|---------|
| RustUnsafeStrategy | `strategies/rust_unsafe.py` | Unsafe block propagation |
| RustFFIStrategy | `strategies/rust_ffi.py` | FFI boundary tracking |
| RustAsyncStrategy | `strategies/rust_async.py` | Async/await flow |
| RustTraitStrategy | `strategies/rust_traits.py` | Trait impl resolution |

**Modifications**:
- `dfg_builder.py` - Register 4 Rust strategies
- New file: `rust_resolver.py` - Module resolution utilities

**Deliverable**: `aud graph build` includes Rust edges in graphs.db

### Phase 4: Rules & Frameworks
**Spec**: Future (depends on Phases 1-3)

**Security Rules** (`rules/rust/`):
- `unsafe_analysis.py` - Unsafe blocks without SAFETY comments
- `ffi_boundary.py` - FFI crossing analysis
- `panic_paths.py` - Unwrap/expect in non-test code
- `integer_safety.py` - Unchecked arithmetic
- `memory_safety.py` - Transmute, raw pointers

**Framework Detection** (`rules/frameworks/`):
- `actix_analyze.py` - Actix-web routes, middleware
- `rocket_analyze.py` - Rocket routes, fairings
- `axum_analyze.py` - Axum handlers, extractors
- `diesel_analyze.py` - Diesel ORM queries
- `sqlx_analyze.py` - SQLx queries

**Deliverable**: `aud rules` detects Rust security issues

## Impact

### Affected Specs
- `specs/indexer/spec.md` - 20 new tables, extractor pattern
- `specs/graph/spec.md` - 4 new strategies, resolution pattern

### New Files (by phase)

**Phase 1** (8 files):
```
theauditor/ast_extractors/rust/__init__.py
theauditor/ast_extractors/rust/core.py
theauditor/indexer/schemas/rust_schema.py
theauditor/indexer/extractors/rust.py
theauditor/indexer/storage/rust_storage.py
```

**Phase 3** (5 files):
```
theauditor/graph/strategies/rust_unsafe.py
theauditor/graph/strategies/rust_ffi.py
theauditor/graph/strategies/rust_async.py
theauditor/graph/strategies/rust_traits.py
theauditor/rust_resolver.py
```

**Phase 4** (10+ files):
```
theauditor/rules/rust/__init__.py
theauditor/rules/rust/unsafe_analysis.py
theauditor/rules/rust/ffi_boundary.py
theauditor/rules/rust/panic_paths.py
theauditor/rules/rust/integer_safety.py
theauditor/rules/rust/memory_safety.py
theauditor/rules/frameworks/actix_analyze.py
theauditor/rules/frameworks/rocket_analyze.py
theauditor/rules/frameworks/axum_analyze.py
...
```

### Modified Files

| File | Change | Phase |
|------|--------|-------|
| `ast_parser.py` | Add `.rs` to `_detect_language()`, init Rust parser | 1 |
| `schema.py` | Import RUST_TABLES, assert 170 → 190 (after Phase 2) | 1 |
| `storage/__init__.py` | Register RustStorage | 1 |
| `dfg_builder.py` | Register 4 Rust strategies | 3 |

### Breaking Changes
None - this is purely additive new capability.

### Dependencies
- `tree-sitter-rust` via `tree-sitter-language-pack` (already installed)
- No new dependencies required

### Existing Integration
- Clippy linting already exists in `linters.py`
- OSV scanning already works via `Cargo.lock` parsing
- These continue to work unchanged

## Success Criteria

### Phase 1 Complete When:
- [ ] `aud full --index` processes `.rs` files without error
- [ ] 7 core rust_* tables created in repo_index.db
- [ ] `aud blueprint --structure` shows Rust tables
- [ ] Basic symbols appear in `symbols` table with correct paths

### Phase 2 Complete When:
- [ ] All 20 rust_* tables populated
- [ ] Module resolution correctly links cross-file references
- [ ] Trait impls can be queried by target type
- [ ] Unsafe blocks have containing function metadata

### Phase 3 Complete When:
- [ ] `aud graph build` produces Rust edges
- [ ] Unsafe propagation edges are transitive
- [ ] Trait resolution enables method call graphs
- [ ] graphs.db contains all 4 Rust edge types

### Phase 4 Complete When:
- [ ] `aud rules` detects unsafe blocks without SAFETY comments
- [ ] Framework detection identifies Actix/Rocket/Axum projects
- [ ] Taint analysis traces HTTP input to SQL queries

## References

- **Design Document**: `design.md`
- **Indexer Spec**: `specs/indexer/spec.md`
- **Graph Spec**: `specs/graph/spec.md`
- **Tasks**: `tasks.md`
