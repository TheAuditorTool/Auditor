## 0. Verification & Cleanup
- [ ] 0.1 Verify no rust_* tables exist in repo_index.db schema
- [ ] 0.2 Document tree-sitter-rust node types available (run `tree-sitter parse` on sample .rs file)
- [ ] 0.3 Clean up `__pycache__` remnants: `theauditor/indexer/extractors/__pycache__/rust.cpython-*.pyc`
- [ ] 0.4 Clean up `__pycache__` remnants: `theauditor/ast_extractors/__pycache__/rust_impl.cpython-*.pyc`

## 1. Phase 1: Foundation (Schema + Core Extraction)

### 1.1 Schema Creation
- [ ] 1.1.1 Create `theauditor/indexer/schemas/rust_schema.py` with 18 TableSchema definitions (pattern: `python_schema.py`)
- [ ] 1.1.2 Add rust tables to schema registry in `theauditor/indexer/schemas/__init__.py`
- [ ] 1.1.3 Register rust schemas in `theauditor/indexer/schemas/core_schema.py` ALL_SCHEMAS list
- [ ] 1.1.4 Verify tables created on fresh `aud full --index`

### 1.2 Core Extraction - Structs & Enums
- [ ] 1.2.1 Create `theauditor/indexer/extractors/rust.py` with RustExtractor class
  - Subclass `BaseExtractor` from `theauditor/indexer/extractors/__init__.py:12`
  - Implement `supported_extensions()` returning `[".rs"]`
  - Implement `extract(file_info, content, tree)` signature per `__init__.py:26-29`
  - Auto-registration via ExtractorRegistry._discover() (`__init__.py:86-118`)
- [ ] 1.2.2 Extract struct definitions (name, visibility, generics)
- [ ] 1.2.3 Extract struct fields (name, type, visibility, attributes)
- [ ] 1.2.4 Extract enum definitions (name, visibility, generics)
- [ ] 1.2.5 Extract enum variants (unit, tuple, struct variants)

### 1.3 Core Extraction - Traits & Impls
- [ ] 1.3.1 Extract trait definitions (name, supertraits, visibility)
- [ ] 1.3.2 Extract trait method signatures
- [ ] 1.3.3 Extract impl blocks (inherent and trait impls)
- [ ] 1.3.4 Extract impl methods with signatures
- [ ] 1.3.5 Link impl to target type (string matching)

### 1.4 Core Extraction - Functions & Modules
- [ ] 1.4.1 Extract free function definitions
- [ ] 1.4.2 Extract function parameters (name, type, mutability, self)
- [ ] 1.4.3 Extract return types
- [ ] 1.4.4 Extract module declarations (mod, pub mod)
- [ ] 1.4.5 Track module hierarchy from file path

### 1.5 Core Extraction - Uses & Calls
- [ ] 1.5.1 Extract use statements with full path
- [ ] 1.5.2 Handle use aliases (as keyword)
- [ ] 1.5.3 Handle glob imports (use foo::*)
- [ ] 1.5.4 Extract function calls with arguments
- [ ] 1.5.5 Extract method calls with receiver

### 1.6 Storage Layer
- [ ] 1.6.1 Create `theauditor/indexer/storage/rust_storage.py` (pattern: `python_storage.py`)
- [ ] 1.6.2 Implement store_rust_struct() with field junction
- [ ] 1.6.3 Implement store_rust_enum() with variant junction
- [ ] 1.6.4 Implement store_rust_trait() with method junction
- [ ] 1.6.5 Implement store_rust_impl() with method junction
- [ ] 1.6.6 Implement store_rust_function() with param junction
- [ ] 1.6.7 Implement store_rust_use()
- [ ] 1.6.8 Wire RustExtractor output to storage in indexer pipeline
  - Add import in `theauditor/indexer/storage/__init__.py`
  - Call storage handlers from extractor's extract() method (see `python.py` for pattern)
  - Use batch insert methods from `base.py` for performance

### 1.7 Phase 1 Verification
- [ ] 1.7.1 Run `aud full --index` on a Rust project
- [ ] 1.7.2 Verify rust_* tables populated with correct data
- [ ] 1.7.3 Test `aud context query --symbol <rust_fn>` works
- [ ] 1.7.4 Verify no regression on Python/JS extraction

## 2. Phase 2: Advanced Extraction

### 2.1 Generics & Lifetimes
- [ ] 2.1.1 Extract generic type parameters from structs/enums/functions
- [ ] 2.1.2 Extract trait bounds on generics
- [ ] 2.1.3 Extract lifetime parameters
- [ ] 2.1.4 Extract where clauses
- [ ] 2.1.5 Store in dedicated columns/tables

### 2.2 Macros
- [ ] 2.2.1 Extract macro_rules! definitions
- [ ] 2.2.2 Extract proc_macro definitions (detect #[proc_macro])
- [ ] 2.2.3 Extract macro invocations (name!(...))
- [ ] 2.2.4 Track macro call site (file, line, containing function)
- [ ] 2.2.5 Link common derives to their effects

### 2.3 Async/Await
- [ ] 2.3.1 Detect async functions
- [ ] 2.3.2 Extract .await expressions
- [ ] 2.3.3 Detect async blocks
- [ ] 2.3.4 Track Future types in return positions

### 2.4 Unsafe & Raw Pointers
- [ ] 2.4.1 Extract unsafe blocks with line ranges
- [ ] 2.4.2 Extract preceding // SAFETY: comments
- [ ] 2.4.3 Catalog unsafe operations within block
- [ ] 2.4.4 Extract unsafe fn declarations
- [ ] 2.4.5 Track raw pointer usage (*const, *mut)

### 2.5 Attributes
- [ ] 2.5.1 Extract #[derive(...)] with trait list
- [ ] 2.5.2 Extract #[cfg(...)] conditions
- [ ] 2.5.3 Extract #[allow(...)], #[deny(...)], #[warn(...)]
- [ ] 2.5.4 Extract custom attributes
- [ ] 2.5.5 Extract doc comments as attributes

## 3. Phase 3: Framework Detection

### 3.1 Web Framework Detection
- [ ] 3.1.1 Create `theauditor/rules/frameworks/rust_analyze.py` (pattern: `flask_analyze.py`, `express_analyze.py`)
- [ ] 3.1.2 Detect Actix-web (imports, route macros, HttpResponse)
- [ ] 3.1.3 Detect Rocket (imports, route attributes, #[rocket::main])
- [ ] 3.1.4 Detect Axum (imports, Router patterns, handler signatures)
- [ ] 3.1.5 Detect Warp (imports, filter combinators)

### 3.2 Route Extraction
- [ ] 3.2.1 Extract Actix route handlers (#[get], #[post], web::resource)
- [ ] 3.2.2 Extract Rocket routes (#[get("/path")], #[post])
- [ ] 3.2.3 Extract Axum routes (Router::new().route())
- [ ] 3.2.4 Map routes to handler functions
- [ ] 3.2.5 Store in rust_routes table

### 3.3 ORM Detection
- [ ] 3.3.1 Detect Diesel (imports, table! macro, derive(Queryable))
- [ ] 3.3.2 Detect SQLx (imports, query! macro, derive(FromRow))
- [ ] 3.3.3 Detect SeaORM (imports, derive(DeriveEntityModel))
- [ ] 3.3.4 Extract model definitions
- [ ] 3.3.5 Extract query patterns

### 3.4 Runtime Detection
- [ ] 3.4.1 Detect Tokio runtime (#[tokio::main], tokio::spawn)
- [ ] 3.4.2 Detect async-std runtime
- [ ] 3.4.3 Track spawn points for async tasks

## 4. Phase 4: Security Rules

### 4.1 Unsafe Analysis
- [ ] 4.1.1 Create `theauditor/rules/rust/` directory (pattern: `theauditor/rules/python/`)
- [ ] 4.1.2 Create `theauditor/rules/rust/__init__.py`
- [ ] 4.1.3 Create `theauditor/rules/rust/unsafe_analyze.py` - flag unsafe blocks without SAFETY comment
- [ ] 4.1.4 Flag unsafe in public API surface
- [ ] 4.1.5 Flag transmute usage
- [ ] 4.1.6 Flag std::mem::forget usage

### 4.2 FFI Boundary Analysis
- [ ] 4.2.1 Create `theauditor/rules/rust/ffi_boundary_analyze.py`
- [ ] 4.2.2 Detect extern "C" blocks
- [ ] 4.2.3 Flag raw pointer parameters in extern fns
- [ ] 4.2.4 Track CString/CStr usage patterns
- [ ] 4.2.5 Flag callback function pointers

### 4.3 Panic Path Detection
- [ ] 4.3.1 Create `theauditor/rules/rust/panic_path_analyze.py`
- [ ] 4.3.2 Find .unwrap() calls outside tests
- [ ] 4.3.3 Find .expect() calls outside tests
- [ ] 4.3.4 Find panic!() macro usage
- [ ] 4.3.5 Find unreachable!() macro usage
- [ ] 4.3.6 Flag panics in async contexts

### 4.4 Integer Safety
- [ ] 4.4.1 Create `theauditor/rules/rust/integer_safety_analyze.py`
- [ ] 4.4.2 Detect unchecked arithmetic on external input
- [ ] 4.4.3 Flag `as` casts that may truncate
- [ ] 4.4.4 Detect array index without bounds check
- [ ] 4.4.5 Suggest checked_* alternatives

### 4.5 Crypto Misuse
- [ ] 4.5.1 Create `theauditor/rules/rust/crypto_analyze.py`
- [ ] 4.5.2 Detect custom crypto implementations
- [ ] 4.5.3 Flag weak RNG usage (rand::thread_rng in crypto context)
- [ ] 4.5.4 Detect hardcoded keys/secrets
- [ ] 4.5.5 Flag deprecated crypto crates

## 5. Integration & Testing

### 5.1 Test Coverage
- [ ] 5.1.1 Unit tests for each extractor function
- [ ] 5.1.2 Integration test with sample Rust project
- [ ] 5.1.3 Test framework detection accuracy
- [ ] 5.1.4 Test security rule precision/recall

### 5.2 Documentation
- [ ] 5.2.1 Update indexer spec with Rust capability
- [ ] 5.2.2 Document rust_* table schemas
- [ ] 5.2.3 Add Rust examples to `aud context` help
- [ ] 5.2.4 Document security rule rationale
