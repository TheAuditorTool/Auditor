## ADDED Requirements

### Requirement: Rust Language Extraction
The indexer SHALL extract Rust language constructs from .rs files using tree-sitter parsing.

#### Scenario: Struct extraction
- **WHEN** a Rust file contains a struct definition
- **THEN** the indexer SHALL extract struct name, visibility, generic parameters, and fields
- **AND** the indexer SHALL store data in rust_structs and rust_struct_fields tables

#### Scenario: Enum extraction
- **WHEN** a Rust file contains an enum definition
- **THEN** the indexer SHALL extract enum name, visibility, generic parameters, and variants
- **AND** variant types (unit, tuple, struct) SHALL be distinguished

#### Scenario: Trait extraction
- **WHEN** a Rust file contains a trait definition
- **THEN** the indexer SHALL extract trait name, supertraits, and method signatures
- **AND** the indexer SHALL store data in rust_traits and rust_trait_methods tables

#### Scenario: Impl block extraction
- **WHEN** a Rust file contains an impl block
- **THEN** the indexer SHALL extract target type, optional trait name, and methods
- **AND** inherent impls and trait impls SHALL be distinguished

#### Scenario: Function extraction
- **WHEN** a Rust file contains a function definition
- **THEN** the indexer SHALL extract function name, parameters, return type, and visibility
- **AND** async functions SHALL be marked as such

#### Scenario: Use statement extraction
- **WHEN** a Rust file contains use declarations
- **THEN** the indexer SHALL extract the full import path
- **AND** aliases (as keyword) and glob imports SHALL be handled

### Requirement: Rust Schema Tables
The indexer SHALL store Rust extraction data in dedicated normalized tables.

#### Scenario: Core entity tables exist
- **WHEN** the database is initialized
- **THEN** tables rust_structs, rust_enums, rust_traits, rust_impls, rust_functions, rust_modules SHALL exist

#### Scenario: Junction tables exist
- **WHEN** the database is initialized
- **THEN** tables rust_struct_fields, rust_enum_variants, rust_trait_methods, rust_impl_methods, rust_function_params SHALL exist

#### Scenario: Metadata tables exist
- **WHEN** the database is initialized
- **THEN** tables rust_uses, rust_macros, rust_macro_calls, rust_attributes, rust_unsafe_blocks SHALL exist

### Requirement: Rust Unsafe Block Tracking
The indexer SHALL track unsafe code blocks with context information.

#### Scenario: Unsafe block extraction
- **WHEN** a Rust file contains an unsafe block
- **THEN** the indexer SHALL extract the block location, containing function, and line range

#### Scenario: Safety comment extraction
- **WHEN** an unsafe block is preceded by a // SAFETY: comment
- **THEN** the indexer SHALL extract and store the safety justification text

#### Scenario: Unsafe function detection
- **WHEN** a function is declared with unsafe keyword
- **THEN** the indexer SHALL mark the function as unsafe in rust_functions

### Requirement: Rust Macro Tracking
The indexer SHALL track macro definitions and invocations.

#### Scenario: Macro definition extraction
- **WHEN** a Rust file contains a macro_rules! definition
- **THEN** the indexer SHALL extract the macro name and location

#### Scenario: Macro invocation extraction
- **WHEN** a Rust file contains a macro invocation (name!(...))
- **THEN** the indexer SHALL extract the macro name, call site, and containing function

#### Scenario: Derive macro tracking
- **WHEN** a struct or enum has #[derive(...)] attribute
- **THEN** the indexer SHALL extract the list of derived traits

### Requirement: Rust Framework Detection
The indexer SHALL detect common Rust web frameworks and ORMs.

#### Scenario: Actix-web detection
- **WHEN** a Rust project uses actix-web
- **THEN** the indexer SHALL detect route handlers and extract HTTP method and path

#### Scenario: Rocket detection
- **WHEN** a Rust project uses Rocket
- **THEN** the indexer SHALL detect route attributes and extract HTTP method and path

#### Scenario: Axum detection
- **WHEN** a Rust project uses Axum
- **THEN** the indexer SHALL detect Router definitions and extract route mappings

#### Scenario: Diesel/SQLx ORM detection
- **WHEN** a Rust project uses Diesel or SQLx
- **THEN** the indexer SHALL detect model definitions and query patterns

### Requirement: Rust Security Pattern Detection
The indexer SHALL detect security-relevant patterns in Rust code.

#### Scenario: Unjustified unsafe detection
- **WHEN** an unsafe block lacks a preceding SAFETY comment
- **THEN** the indexer SHALL flag it as a security finding

#### Scenario: Panic path detection
- **WHEN** code contains .unwrap(), .expect(), or panic!() outside test modules
- **THEN** the indexer SHALL record the panic site for review

#### Scenario: FFI boundary detection
- **WHEN** code contains extern "C" functions or raw pointer parameters
- **THEN** the indexer SHALL flag the FFI boundary for security review

#### Scenario: Integer overflow risk detection
- **WHEN** code contains unchecked arithmetic on external input
- **THEN** the indexer SHALL flag the operation as a potential overflow risk

#### Scenario: Drop trait risk detection
- **WHEN** code contains manual `impl Drop` implementation
- **THEN** the indexer SHALL flag it as "review required" (double-free/memory leak risk)

#### Scenario: Linker safety detection
- **WHEN** a function has `#[no_mangle]` attribute
- **THEN** the indexer SHALL flag it as exposed to linker (bypasses namespace safety)

#### Scenario: Blocking in async detection
- **WHEN** code uses std::fs, std::thread::sleep, or std::sync::Mutex inside async fn/block
- **THEN** the indexer SHALL flag it as potential async performance issue

### Requirement: Workspace/Monorepo Support
The indexer SHALL handle Rust workspaces with multiple crates.

#### Scenario: Cargo.toml parsing
- **WHEN** a Rust project contains Cargo.toml files
- **THEN** the indexer SHALL parse [package] and [workspace] sections
- **AND** link .rs files to their owning crate via rust_crates table

#### Scenario: Crate boundary awareness
- **WHEN** querying symbols via `aud context`
- **THEN** the indexer SHALL be able to distinguish library vs binary code

### Requirement: Use Resolution
The indexer SHALL resolve type aliases for cross-file querying.

#### Scenario: Alias resolution
- **WHEN** a file contains `use std::fs::File as F`
- **THEN** the indexer SHALL store both `F` and `std::fs::File` for querying

#### Scenario: Impl target resolution
- **WHEN** storing impl block target_type
- **THEN** the indexer SHALL apply use resolution to canonicalize type names

### Requirement: Macro Token Capture
The indexer SHALL extract string literals from macro invocation arguments.

#### Scenario: Macro args extraction
- **WHEN** a macro invocation contains string literals
- **THEN** the indexer SHALL capture first ~100 chars in args_sample column
- **AND** security rules can scan for hardcoded secrets/SQL patterns
