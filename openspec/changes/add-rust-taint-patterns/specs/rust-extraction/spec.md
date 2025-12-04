## ADDED Requirements

### Requirement: Rust Taint Source Pattern Registration
The system SHALL register Rust-specific source patterns in TaintRegistry for identifying user-controlled input.

#### Scenario: Standard input sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `std::io::stdin`
- **AND** it SHALL contain source patterns for `BufReader::new(stdin())`

#### Scenario: Environment sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `std::env::args`
- **AND** it SHALL contain source patterns for `std::env::var`
- **AND** it SHALL contain source patterns for `std::env::vars`

#### Scenario: File read sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `std::fs::read`
- **AND** it SHALL contain source patterns for `std::fs::read_to_string`

#### Scenario: Actix-web sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `web::Json`
- **AND** it SHALL contain source patterns for `web::Path`
- **AND** it SHALL contain source patterns for `web::Query`
- **AND** it SHALL contain source patterns for `web::Form`

#### Scenario: Axum sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `axum::extract::Json`
- **AND** it SHALL contain source patterns for `axum::extract::Path`
- **AND** it SHALL contain source patterns for `axum::extract::Query`

#### Scenario: Rocket sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `rocket::request`
- **AND** it SHALL contain source patterns for `rocket::form`

---

### Requirement: Rust Taint Sink Pattern Registration
The system SHALL register Rust-specific sink patterns in TaintRegistry for identifying dangerous operations.

#### Scenario: Command injection sinks
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain sink patterns for `std::process::Command`
- **AND** it SHALL contain sink patterns for `Command::new`
- **AND** it SHALL contain sink patterns for `Command::arg`

#### Scenario: SQL injection sinks
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain sink patterns for `sqlx::query`
- **AND** it SHALL contain sink patterns for `sqlx::query_as`
- **AND** it SHALL contain sink patterns for `diesel::sql_query`

#### Scenario: File write sinks
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain sink patterns for `std::fs::write`
- **AND** it SHALL contain sink patterns for `std::fs::File::create`
- **AND** it SHALL contain sink patterns for `File::write_all`

#### Scenario: Unsafe memory sinks
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain sink patterns for `std::ptr::write`
- **AND** it SHALL contain sink patterns for `std::mem::transmute`

---

### Requirement: Rust Pattern Registration Integration
The Rust pattern registration function SHALL be called during taint pipeline initialization.

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
Rust pattern registration SHALL use the centralized logging system.

#### Scenario: Logging import
- **WHEN** examining rust_injection_analyze.py source code
- **THEN** it SHALL contain `from theauditor.utils.logging import logger`

#### Scenario: No print statements
- **WHEN** examining rust_injection_analyze.py source code
- **THEN** there SHALL be no bare `print()` calls
- **AND** all diagnostic output SHALL use the logger
