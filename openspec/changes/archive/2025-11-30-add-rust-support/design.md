# Rust Language Support - Technical Design

> **Version**: 2.0 (Revised)
> **Last Updated**: 2025-11-29
> **Specs**:
> - Indexer: `specs/indexer/spec.md`
> - Graph: `specs/graph/spec.md`

## 1. Executive Summary

This design document describes the architecture for adding Rust language support to TheAuditor. The implementation spans **three layers**:

1. **Indexer Layer** - AST extraction and database storage
2. **Graph Layer** - Data flow graphs and analysis strategies
3. **Rules Layer** - Security analysis and detection rules

Each layer has a corresponding specification document with implementation details.

## 2. Context

TheAuditor supports Python (33 dedicated tables, full framework detection, security rules) and JavaScript/TypeScript (37 tables, Vue/Angular/React detection). Rust has zero tables and zero extraction code.

Rust presents unique challenges vs Python/JS:
- **Ownership/borrowing** - data flow analysis must track ownership transfers
- **Traits vs classes** - polymorphism through trait bounds, not inheritance
- **Macros** - code generation that expands at compile time
- **unsafe** - explicit escape hatch that needs security tracking
- **No runtime** - no GC, no exceptions, panics are failures

## 3. Architecture Overview

### 3.1 Full Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           RUST SUPPORT PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │  .rs files   │───▶│  ast_parser  │───▶│ tree-sitter  │              │
│  └──────────────┘    │    .py       │    │    rust      │              │
│                      └──────┬───────┘    └──────────────┘              │
│                             │                                           │
│                             ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      INDEXER LAYER                                │  │
│  │  See: specs/indexer/spec.md                                       │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │  │
│  │  │ ast_extractors │  │   extractors   │  │    storage     │      │  │
│  │  │ /rust/         │  │   /rust.py     │  │ /rust_storage  │      │  │
│  │  └────────────────┘  └────────────────┘  └────────────────┘      │  │
│  │                             │                                     │  │
│  │                             ▼                                     │  │
│  │                    ┌────────────────┐                            │  │
│  │                    │ repo_index.db  │  (20 rust_* tables)        │  │
│  │                    └────────────────┘                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                             │                                           │
│                             ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                       GRAPH LAYER                                 │  │
│  │  See: specs/graph/spec.md                                         │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │  │
│  │  │ rust_unsafe    │  │  rust_ffi      │  │  rust_traits   │      │  │
│  │  │ _strategy.py   │  │  _strategy.py  │  │  _strategy.py  │      │  │
│  │  └────────────────┘  └────────────────┘  └────────────────┘      │  │
│  │                             │                                     │  │
│  │                             ▼                                     │  │
│  │                    ┌────────────────┐                            │  │
│  │                    │   graphs.db    │  (edges for SAST)          │  │
│  │                    └────────────────┘                            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                             │                                           │
│                             ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                       RULES LAYER                                 │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │  │
│  │  │ rules/rust/    │  │ rules/         │  │   taint/       │      │  │
│  │  │ *.py           │  │ frameworks/    │  │   engine       │      │  │
│  │  └────────────────┘  └────────────────┘  └────────────────┘      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Inventory

| Layer | Component | New Files | Spec Reference |
|-------|-----------|-----------|----------------|
| AST | rust/ module | `ast_extractors/rust/__init__.py`, `core.py` | indexer:3.1 |
| Indexer | Schema | `schemas/rust_schema.py` | indexer:4 |
| Indexer | Extractor | `extractors/rust.py` | indexer:3.2 |
| Indexer | Storage | `storage/rust_storage.py` | indexer:5 |
| Graph | Strategies | `strategies/rust_*.py` (4 files) | graph:2 |
| Graph | Resolver | `rust_resolver.py` | graph:3 |
| Rules | Security | `rules/rust/*.py` | Phase 4 |
| Rules | Frameworks | `rules/frameworks/actix_*.py`, etc. | Phase 4 |

## 4. Goals / Non-Goals

### 4.1 Goals

- Parity with Python/JS for core extraction (symbols, calls, data flow)
- Rust-specific constructs (traits, impls, lifetimes, unsafe)
- **Module resolution** for cross-file symbol linkage (CRITICAL for SAST)
- **Graph strategies** for unsafe propagation, FFI, async flow
- Framework detection for major web frameworks (Actix, Rocket, Axum)
- Security rules targeting Rust-specific vulnerabilities
- Data stored in normalized tables, queryable via existing `aud context` commands

### 4.2 Non-Goals (True Non-Goals)

These are explicitly out of scope and will NOT be implemented:

1. **Borrow Checker Simulation** - Rustc handles memory safety validation
2. **Lifetime Inference** - Requires full type system, we store annotations only
3. **Const Evaluation** - Compile-time computation is rustc's domain
4. **Macro Expansion** - Extract macro calls and args, not expanded code
5. **Procedural Macro Analysis** - Would require running macros
6. **WASM-Specific Patterns** - Future enhancement
7. **Cargo.toml Dependency Resolution** - Different tool (cargo-audit)

### 4.3 What Resolution Means (Clarification)

**We DO implement**:
- `use` statement alias tracking → canonical crate paths
- `mod` declaration → file location mapping
- Trait impl blocks → which type implements which trait
- Method call resolution → which impl block handles the call

**We DON'T implement**:
- Generic instantiation (`Vec<T>` → concrete type)
- Lifetime inference
- Const generics evaluation

This distinction is critical: SAST needs to know "which User struct is this?" but doesn't need to know "what is the concrete type of this generic parameter?"

## 5. Key Design Decisions

### Decision 1: Tree-sitter for Parsing (Python-to-Python)

**Choice**: Use tree-sitter-rust via Python bindings, no subprocess.

**Rationale**:
- tree-sitter-rust is available in tree-sitter-language-pack
- We only need syntactic AST, not semantic analysis
- Same pattern as HCL (see `ast_extractors/hcl_impl.py`)
- No compiled Rust code or subprocess needed

**Reference Pattern**: `theauditor/ast_extractors/hcl_impl.py`

**Implementation** (spec:indexer:2.1):
```python
# In ast_parser.py:_init_tree_sitter_parsers()
from tree_sitter_language_pack import get_language
rust_lang = get_language("rust")
self.rust_parser = Parser(rust_lang)
```

### Decision 2: Single-Pass Extraction Architecture

**Choice**: Single tree-sitter pass extracting all constructs, returning structured dict.

**Rationale**: Tree-sitter gives us the full AST in one parse. Multi-pass would re-parse the same file. Current Python extractor uses this pattern successfully.

**Reference Pattern**: `theauditor/indexer/extractors/python.py`

**Implementation** (spec:indexer:3.2):
```python
def extract(self, file_info, content, tree) -> dict:
    return {
        "rust_structs": [...],
        "rust_enums": [...],
        "rust_traits": [...],
        "rust_impl_blocks": [...],
        "rust_functions": [...],
        # ... all 20 table categories
    }
```

### Decision 3: Module Resolution is REQUIRED

**Choice**: Implement lightweight module resolution for Rust.

**Rationale**:
- SAST requires knowing which symbol a name refers to
- Call graphs need to resolve method calls to implementations
- Taint analysis needs to trace data across module boundaries
- Without resolution, security rules cannot function

**Implementation** (spec:graph:3):
```sql
-- rust_use_statements schema stores BOTH raw and resolved
CREATE TABLE rust_use_statements (
    file_path TEXT,
    local_name TEXT,      -- 'User' (alias in scope)
    canonical_path TEXT,  -- 'crate::models::User' (resolved)
    is_glob BOOLEAN,
    visibility TEXT
);
```

### Decision 4: Impl Block Resolution via Alias Mapping

**Choice**: Store impl blocks with both raw and resolved type paths.

**Rationale**:
- Raw name enables local queries within file
- Resolved name enables cross-file joins
- Avoids needing rustc for type resolution

**Implementation** (spec:indexer:4.7):
```sql
CREATE TABLE rust_impl_blocks (
    file_path TEXT,
    target_type_raw TEXT,      -- 'User' as written
    target_type_resolved TEXT, -- 'crate::models::User' canonical
    trait_name TEXT,           -- NULL for inherent impl
    trait_resolved TEXT,       -- 'std::fmt::Display' canonical
);
```

### Decision 5: Graph Strategies for Rust-Specific Patterns

**Choice**: Create 4 dedicated graph strategies for Rust.

**Rationale**: Rust has unique patterns that need graph representation for SAST to work:
- Unsafe blocks and their propagation through call chains
- FFI boundaries where Rust safety guarantees end
- Async/await flow across spawn points
- Trait implementations for method resolution

**Strategies** (spec:graph:2):
1. `RustUnsafeStrategy` - unsafe block containment and propagation
2. `RustFFIStrategy` - FFI boundary tracking
3. `RustAsyncStrategy` - async/await flow
4. `RustTraitStrategy` - trait impl resolution

### Decision 6: Separation of Concerns (Polyglot Architecture)

**Choice**: All Rust code lives in Rust-specific files, no mixing with Python/Node.

**New Files Created**:
```
theauditor/
├── ast_extractors/
│   └── rust/                    # NEW directory
│       ├── __init__.py
│       └── core.py
├── indexer/
│   ├── extractors/
│   │   └── rust.py              # NEW file
│   ├── schemas/
│   │   └── rust_schema.py       # NEW file
│   └── storage/
│       └── rust_storage.py      # NEW file
├── graph/
│   └── strategies/
│       ├── rust_unsafe.py       # NEW file
│       ├── rust_ffi.py          # NEW file
│       ├── rust_async.py        # NEW file
│       └── rust_traits.py       # NEW file
├── rust_resolver.py             # NEW file
└── rules/
    └── rust/                    # NEW directory
        ├── __init__.py
        ├── unsafe_analysis.py
        └── ...
```

**Files Modified**:
```
theauditor/
├── ast_parser.py                # Add .rs to ext_map, init rust parser
├── indexer/
│   ├── schema.py                # Import RUST_TABLES, assert 170→190
│   └── storage/__init__.py      # Register RustStorage
└── graph/
    └── dfg_builder.py           # Register Rust strategies
```

## 6. Database Schema

### 6.1 Table Count Update

| Domain | Current | After Rust | Tables |
|--------|---------|------------|--------|
| Python | 33 | 33 | python_* |
| Node | 37 | 37 | node_*, react_*, express_* |
| Core | 24 | 24 | symbols, imports, etc. |
| Terraform | 8 | 8 | terraform_* |
| Other | 68 | 68 | various |
| **Rust** | 0 | **20** | rust_* |
| **Total** | **170** | **190** | |

### 6.2 Rust Tables Summary

Full schemas in `specs/indexer/spec.md` Section 4.

**Core Tables** (Phase 1 - 7 tables):
1. `rust_modules` - Module/crate structure
2. `rust_use_statements` - Use declarations with resolution
3. `rust_functions` - Function definitions
4. `rust_structs` - Struct definitions
5. `rust_enums` - Enum definitions
6. `rust_traits` - Trait definitions
7. `rust_impl_blocks` - Impl block metadata

**Advanced Tables** (Phase 2 - 9 tables):
8. `rust_generics` - Generic parameters
9. `rust_lifetimes` - Lifetime annotations
10. `rust_macros` - Macro definitions
11. `rust_macro_invocations` - Macro call sites
12. `rust_async_functions` - Async fn metadata
13. `rust_await_points` - Await expression locations
14. `rust_unsafe_blocks` - Unsafe block locations
15. `rust_unsafe_traits` - Unsafe trait impls
16. `rust_extern_blocks` - Extern block metadata

**Relationship Tables** (Phase 2 - 4 tables):
17. `rust_struct_fields` - Struct field details
18. `rust_enum_variants` - Enum variant details
19. `rust_trait_methods` - Trait method signatures
20. `rust_extern_functions` - FFI declarations

## 7. Framework Detection Patterns

| Framework | Detection Pattern |
|-----------|-------------------|
| Actix-web | `use actix_web::`, `#[get]`/`#[post]` macros, `HttpResponse` |
| Rocket | `use rocket::`, `#[rocket::main]`, `#[get]`/`#[post]` |
| Axum | `use axum::`, `Router::new()`, handler function patterns |
| Tokio | `#[tokio::main]`, `tokio::spawn`, async runtime |
| Diesel | `use diesel::`, `#[derive(Queryable)]`, `table!` macro |
| SQLx | `use sqlx::`, `#[derive(FromRow)]`, `query!` macro |
| Serde | `#[derive(Serialize, Deserialize)]`, `serde_json::` |

## 8. Security Rule Categories

| Category | Patterns |
|----------|----------|
| Unsafe usage | `unsafe` blocks without SAFETY comment, unsafe in public API |
| FFI boundaries | `extern "C"`, raw pointer params, CString usage |
| Panic paths | `.unwrap()`, `.expect()`, `panic!()` in non-test code |
| Integer overflow | Unchecked arithmetic on user input, `as` casts |
| Memory issues | `std::mem::transmute`, `std::ptr::*`, `Box::leak` |
| Crypto misuse | Custom crypto, weak RNG, hardcoded keys |
| Drop trait risks | Manual `impl Drop` (double-free, memory leak source) |
| Linker safety | `#[no_mangle]` bypassing namespace safety |
| Blocking in async | `std::fs`, `std::thread::sleep` in async context |

## 9. Risk Analysis

### Risk 1: Resolution Accuracy

**Problem**: String-based resolution may fail for complex cases.

**Mitigation**:
- Store both raw and resolved paths
- Log resolution failures for debugging
- Accept that external crate types resolve to `external::crate_name::Type`

### Risk 2: Graph Strategy Performance

**Problem**: Large Rust codebases may have many unsafe blocks/traits.

**Mitigation**:
- Use indexed queries (file_path, line)
- Batch processing with progress bars
- Skip strategies if no relevant data found

### Risk 3: Tree-sitter Grammar Changes

**Problem**: tree-sitter-rust grammar may change between versions.

**Mitigation**:
- Pin tree-sitter-language-pack version
- Document expected node types in spec
- Integration tests against Rust samples

## 10. Implementation Phases

### Phase 1: Foundation (Indexer Core)
- AST extraction infrastructure (`ast_extractors/rust/`)
- Core tables (7 tables)
- Basic storage handlers
- Parser integration (`ast_parser.py`)

**Deliverable**: `aud full --index` processes `.rs` files
**Spec**: indexer:6.1

### Phase 2: Advanced Extraction
- Advanced tables (9 tables)
- Relationship tables (4 tables)
- Full storage handlers
- Module resolver

**Deliverable**: All 20 tables populated correctly
**Spec**: indexer:6.2

### Phase 3: Graph Layer
- 4 graph strategies
- DFG builder integration
- Resolution queries

**Deliverable**: `aud graph build` includes Rust edges
**Spec**: graph:2, graph:4

### Phase 4: Rules & Frameworks
- Security rules (unsafe, FFI, memory)
- Framework detection (Actix, Rocket, etc.)
- Taint sources/sinks

**Deliverable**: `aud rules` detects Rust security issues

## 11. References

- **Indexer Spec**: `specs/indexer/spec.md` - Table schemas, extractor patterns
- **Graph Spec**: `specs/graph/spec.md` - Strategy definitions, resolution
- **Python Pattern**: `indexer/schemas/python_schema.py`, `extractors/python.py`
- **HCL Pattern**: `ast_extractors/hcl_impl.py`, `extractors/terraform.py`
- **Tree-sitter Rust**: https://github.com/tree-sitter/tree-sitter-rust
