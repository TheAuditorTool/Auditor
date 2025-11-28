## Why

Rust support does not exist. Previous extraction files were deleted (only `__pycache__` remnants remain). Zero `rust_*` tables exist, zero Rust symbols stored. TheAuditor misses critical Rust constructs: `impl` blocks, generics, lifetimes, macros, `unsafe` blocks, async/await. For a static analysis tool claiming polyglot support, this is a gap that undermines credibility.

Rust codebases are increasingly common in security-critical infrastructure (crypto, networking, systems). TheAuditor needs real Rust support to be useful for these projects.

## What Changes

**Phase 1: Foundation (Schema + Core Extraction)**
- Create 18 `rust_*` schema tables in `theauditor/indexer/schemas/rust_schema.py` (Python TableSchema pattern)
- Create `theauditor/indexer/extractors/rust.py` with RustExtractor class (auto-discovered via ExtractorRegistry)
- Create `theauditor/indexer/storage/rust_storage.py` with storage handlers
- Wire extraction output to storage layer via indexer pipeline
- Clean up `__pycache__` remnants from deleted Rust files

**Phase 2: Advanced Extraction**
- Generics and type parameters
- Lifetimes and borrowing patterns
- Macro definitions and invocations
- async/await and Future types
- `unsafe` blocks and raw pointers
- Attributes and derives

**Phase 3: Framework Detection**
- Actix-web route handlers and middleware
- Rocket routes and fairings
- Axum handlers and extractors
- Tokio runtime patterns
- Diesel/SQLx ORM models and queries
- Serde serialization boundaries

**Phase 4: Security Rules**
- `unsafe` code block tracking and justification
- FFI boundary analysis (extern functions, raw pointers crossing boundaries)
- Panic path detection (unwrap, expect, panic! in critical paths)
- Integer overflow patterns (unchecked arithmetic)
- Memory safety violations (use-after-free patterns, double-free risks)

## Impact

- Affected specs: `indexer` (new language support)
- Affected code:
  - `theauditor/indexer/schemas/rust_schema.py` - NEW: 18 TableSchema definitions (pattern: `python_schema.py`)
  - `theauditor/indexer/extractors/rust.py` - NEW: RustExtractor class (pattern: `python.py`, auto-discovered)
  - `theauditor/indexer/storage/rust_storage.py` - NEW: storage handlers (pattern: `python_storage.py`)
  - `theauditor/rules/rust/` - NEW: directory with security rules (pattern: `theauditor/rules/python/`)
    - `unsafe_analyze.py`, `ffi_boundary_analyze.py`, `panic_path_analyze.py`, `integer_safety_analyze.py`, `crypto_analyze.py`
  - `theauditor/rules/frameworks/rust_analyze.py` - NEW: Actix/Rocket/Axum detection (pattern: `flask_analyze.py`)
- Breaking changes: None (new capability)
- Dependencies: tree-sitter-rust (already installed via tree-sitter-language-pack)
- Linting: Clippy integration already exists in linters.py
- OSV scanning: Already works via Cargo.lock parsing
