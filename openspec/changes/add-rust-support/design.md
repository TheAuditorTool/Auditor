## Context

TheAuditor supports Python (35 dedicated tables, full framework detection, security rules) and JavaScript/TypeScript (37 tables, Vue/Angular/React detection). Rust has zero tables and zero extraction code (previous files were deleted, only `__pycache__` remnants remain).

Rust presents unique challenges vs Python/JS:
- **Ownership/borrowing** - data flow analysis must track lifetimes
- **Traits vs classes** - polymorphism through trait bounds, not inheritance
- **Macros** - code generation that expands at compile time
- **unsafe** - explicit escape hatch that needs security tracking
- **No runtime** - no GC, no exceptions, panics are failures

## Goals / Non-Goals

**Goals:**
- Parity with Python/JS for core extraction (symbols, calls, data flow)
- Rust-specific constructs (traits, impls, lifetimes, unsafe)
- Framework detection for major web frameworks (Actix, Rocket, Axum)
- Security rules targeting Rust-specific vulnerabilities
- Data stored in normalized tables, queryable via existing `aud context` commands

**Non-Goals:**
- Borrow checker simulation (leave that to rustc)
- Macro expansion (extract macro calls, not expanded code)
- Const generics analysis
- Procedural macro source analysis
- WASM-specific patterns

## Decisions

### Decision 1: Schema design - 18 normalized tables

| Table | Purpose |
|-------|---------|
| `rust_crates` | Crate metadata (name, version, edition) |
| `rust_modules` | Module hierarchy (mod, pub mod, mod.rs) |
| `rust_structs` | Struct definitions with visibility |
| `rust_struct_fields` | Field name, type, visibility per struct |
| `rust_enums` | Enum definitions |
| `rust_enum_variants` | Variant name, type (unit/tuple/struct) |
| `rust_traits` | Trait definitions with supertraits |
| `rust_trait_methods` | Method signatures in traits |
| `rust_impls` | impl blocks (inherent and trait) |
| `rust_impl_methods` | Methods within impl blocks |
| `rust_functions` | Free functions with signature |
| `rust_function_params` | Parameter name, type, mutability |
| `rust_macros` | Macro definitions (macro_rules!, proc_macro) |
| `rust_macro_calls` | Macro invocations with expansion site |
| `rust_unsafe_blocks` | unsafe blocks with justification comments |
| `rust_extern_fns` | FFI function declarations |
| `rust_attributes` | #[derive], #[cfg], custom attributes |
| `rust_uses` | use statements with alias tracking |

**Rationale:** Mirrors Python's normalized approach. Junction tables for many-to-many (struct_fields, enum_variants, etc.). Enables efficient queries like "find all unsafe blocks in this crate" or "what traits does this struct implement".

### Decision 2: Extraction architecture - single-pass tree-sitter

**Choice:** Single tree-sitter pass extracting all constructs, returning structured dict.

```python
def extract(self, file_info, content, tree) -> dict:
    return {
        "structs": [...],
        "enums": [...],
        "traits": [...],
        "impls": [...],
        "functions": [...],
        "macros": [...],
        "unsafe_blocks": [...],
        "uses": [...],
        "attributes": [...],
    }
```

**Rationale:** Tree-sitter gives us the full AST in one parse. Multi-pass would re-parse the same file. Current Python extractor uses this pattern successfully.

### Decision 2b: Extractor registration - auto-discovery

**Choice:** Create `theauditor/indexer/extractors/rust.py` with a class subclassing `BaseExtractor`. Registration is automatic via `ExtractorRegistry._discover()`.

```python
# theauditor/indexer/extractors/rust.py (pattern from python.py)
from . import BaseExtractor

class RustExtractor(BaseExtractor):
    """Extractor for Rust source files."""

    def supported_extensions(self) -> list[str]:
        return [".rs"]

    def extract(self, file_info: dict, content: str, tree=None) -> dict:
        # tree-sitter AST is passed via tree parameter
        return {
            "structs": [...],
            "enums": [...],
            # ... see Decision 2
        }
```

**Rationale:** ExtractorRegistry (see `theauditor/indexer/extractors/__init__.py:76-118`) auto-discovers all `.py` files in the extractors directory, imports them, finds classes subclassing `BaseExtractor`, and registers them by their `supported_extensions()`. No decorator or manual registration needed.

### Decision 3: Impl block resolution

**Choice:** Store impl blocks with target type name as string, resolve relationships at query time.

```python
# theauditor/indexer/schemas/rust_schema.py (pattern from python_schema.py)
from .utils import Column, TableSchema

RUST_IMPLS = TableSchema(
    name="rust_impls",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER"),
        Column("target_type", "TEXT", nullable=False),  # "MyStruct" or "MyStruct<T>"
        Column("trait_name", "TEXT"),                   # NULL for inherent impl, "Display" for trait impl
        Column("visibility", "TEXT"),
        Column("generics", "TEXT"),
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_rust_impls_file", ["file"]),
        ("idx_rust_impls_target", ["target_type"]),
        ("idx_rust_impls_trait", ["trait_name"]),
    ],
)
```

**Rationale:** Full type resolution requires the Rust compiler. We store the syntactic information and let queries join on name matching. This is consistent with how Python handles class inheritance (store base class name as string).

**Alternative considered:** Build type resolution graph during extraction.
**Rejected:** Would duplicate rustc work, be fragile, and still miss generics/trait bounds.

### Decision 4: Unsafe tracking granularity

**Choice:** Track at block level with context extraction.

```python
# theauditor/indexer/schemas/rust_schema.py
RUST_UNSAFE_BLOCKS = TableSchema(
    name="rust_unsafe_blocks",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER"),
        Column("function_name", "TEXT"),              # containing function
        Column("reason_comment", "TEXT"),             # extracted from preceding // SAFETY: comment
        Column("operations", "TEXT"),                 # JSON array of unsafe ops inside
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_rust_unsafe_blocks_file", ["file"]),
        ("idx_rust_unsafe_blocks_function", ["function_name"]),
    ],
)
```

**Rationale:** Security audits need to know: where is unsafe code, what does it do, is it justified? Extracting `// SAFETY:` comments follows Rust community convention.

### Decision 5: Framework detection patterns

| Framework | Detection Pattern |
|-----------|-------------------|
| Actix-web | `use actix_web::`, `#[get]`/`#[post]` macros, `HttpResponse` |
| Rocket | `use rocket::`, `#[rocket::main]`, `#[get]`/`#[post]` |
| Axum | `use axum::`, `Router::new()`, handler function patterns |
| Tokio | `#[tokio::main]`, `tokio::spawn`, async runtime |
| Diesel | `use diesel::`, `#[derive(Queryable)]`, `table!` macro |
| SQLx | `use sqlx::`, `#[derive(FromRow)]`, `query!` macro |
| Serde | `#[derive(Serialize, Deserialize)]`, `serde_json::` |

**Rationale:** Same pattern as Python framework detection - look for import patterns and decorator/attribute usage.

### Decision 6: Security rule categories

| Category | Patterns |
|----------|----------|
| Unsafe usage | `unsafe` blocks without SAFETY comment, unsafe in public API |
| FFI boundaries | `extern "C"`, raw pointer params, CString usage |
| Panic paths | `.unwrap()`, `.expect()`, `panic!()` in non-test code |
| Integer overflow | Unchecked arithmetic on user input, `as` casts |
| Memory issues | `std::mem::transmute`, `std::ptr::`, Box::leak |
| Crypto misuse | Custom crypto, weak RNG, hardcoded keys |

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Macro expansion invisible | Document limitation, track macro call sites |
| Generic type resolution incomplete | Store syntactic info, note limitation |
| Large crates slow to parse | tree-sitter is fast, same as Python/JS |
| Framework detection false positives | Require multiple signals (import + usage) |

## Migration Plan

1. **Phase 1** (Foundation): Schema + core extraction + storage - delivers queryable data
2. **Phase 2** (Advanced): Generics, lifetimes, macros, async - completes extraction
3. **Phase 3** (Frameworks): Detection patterns - enables route/handler analysis
4. **Phase 4** (Security): Taint rules - enables vulnerability detection

Each phase is independently valuable. Phase 1 alone makes Rust codebases queryable.

## Open Questions

1. Should we track Cargo.toml features and conditional compilation (`#[cfg]`)?
   - Tentative: Yes for Phase 2, extract as attributes

2. Should macro expansion be attempted for common macros (derive, serde)?
   - Tentative: No, too fragile. Track the macro call, not expansion.
