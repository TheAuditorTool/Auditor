## ADDED Requirements

### Requirement: Rust Taint Source Pattern Registration
The system SHALL register Rust-specific source patterns in TaintRegistry for identifying user-controlled input.
Patterns MUST use categories from `TaintRegistry.CATEGORY_TO_VULN_TYPE` at `taint/core.py:27-47`.

#### Scenario: Standard input sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `std::io::stdin` with category `user_input`
- **AND** it SHALL contain source patterns for `BufReader::new(stdin())` with category `user_input`

#### Scenario: Environment sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `std::env::args` with category `user_input`
- **AND** it SHALL contain source patterns for `std::env::var` with category `user_input`
- **AND** it SHALL contain source patterns for `std::env::vars` with category `user_input`

#### Scenario: File read sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `std::fs::read` with category `user_input`
- **AND** it SHALL contain source patterns for `std::fs::read_to_string` with category `user_input`

#### Scenario: Actix-web sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `web::Json` with category `http_request`
- **AND** it SHALL contain source patterns for `web::Path` with category `http_request`
- **AND** it SHALL contain source patterns for `web::Query` with category `http_request`
- **AND** it SHALL contain source patterns for `web::Form` with category `http_request`

#### Scenario: Axum sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `axum::extract::Json` with category `http_request`
- **AND** it SHALL contain source patterns for `axum::extract::Path` with category `http_request`
- **AND** it SHALL contain source patterns for `axum::extract::Query` with category `http_request`

#### Scenario: Rocket sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `rocket::request` with category `http_request`
- **AND** it SHALL contain source patterns for `rocket::form` with category `http_request`

---

### Requirement: Rust Taint Sink Pattern Registration
The system SHALL register Rust-specific sink patterns in TaintRegistry for identifying dangerous operations.
Patterns MUST use categories from `TaintRegistry.CATEGORY_TO_VULN_TYPE` at `taint/core.py:27-47`.

#### Scenario: Command injection sinks
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain sink patterns for `std::process::Command` with category `command`
- **AND** it SHALL contain sink patterns for `Command::new` with category `command`
- **AND** it SHALL contain sink patterns for `Command::arg` with category `command`

#### Scenario: SQL injection sinks
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain sink patterns for `sqlx::query` with category `sql`
- **AND** it SHALL contain sink patterns for `sqlx::query_as` with category `sql`
- **AND** it SHALL contain sink patterns for `diesel::sql_query` with category `sql`

#### Scenario: File write sinks
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain sink patterns for `std::fs::write` with category `path`
- **AND** it SHALL contain sink patterns for `std::fs::File::create` with category `path`
- **AND** it SHALL contain sink patterns for `File::write_all` with category `path`

#### Scenario: Unsafe memory sinks
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain sink patterns for `std::ptr::write` with category `code_injection`
- **AND** it SHALL contain sink patterns for `std::mem::transmute` with category `code_injection`

---

### Requirement: Rust Pattern Registration Integration
The Rust pattern registration function SHALL be auto-discovered by the orchestrator.

#### Scenario: Function naming for auto-discovery
- **WHEN** `rust_injection_analyze.py` is loaded by orchestrator
- **THEN** it SHALL define a function named exactly `register_taint_patterns`
- **AND** the function SHALL accept a single `taint_registry` parameter
- **AND** the orchestrator at `orchestrator.py:471-495` SHALL discover and invoke it

#### Scenario: Patterns available at runtime
- **WHEN** taint analysis is run on a Rust project
- **THEN** TaintRegistry SHALL contain all registered Rust source patterns
- **AND** TaintRegistry SHALL contain all registered Rust sink patterns
- **AND** patterns SHALL be available before flow resolution begins

#### Scenario: Pattern count logging
- **WHEN** Rust patterns are registered
- **THEN** logger.debug SHALL be called with the count of source patterns
- **AND** logger.debug SHALL be called with the count of sink patterns

---

### Requirement: Rust Pattern Logging Integration
Rust pattern registration SHALL use the centralized loguru-based logging system.

#### Scenario: Logging import
- **WHEN** examining rust_injection_analyze.py source code
- **THEN** it SHALL contain `from theauditor.utils.logging import logger`
- **AND** this import uses loguru underneath (verified at `utils/logging.py:25`)

#### Scenario: No print statements
- **WHEN** examining rust_injection_analyze.py source code
- **THEN** there SHALL be no bare `print()` calls
- **AND** all diagnostic output SHALL use the logger
