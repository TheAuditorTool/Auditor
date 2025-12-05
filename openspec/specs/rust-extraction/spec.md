# rust-extraction Specification

## Purpose
TBD - created by archiving change wire-rust-graph-integration. Update Purpose after archive.
## Requirements
### Requirement: Rust Assignment Extraction for DFG
The Rust extractor SHALL populate the language-agnostic `assignments` and `assignment_sources` tables for all variable bindings in Rust source files.

#### Scenario: Simple let binding
- **WHEN** a Rust file contains `let x = 42;`
- **THEN** the `assignments` table SHALL contain a row with target_var="x", source_expr="42"
- **AND** the row SHALL include file path, line number, and containing function

#### Scenario: Let binding with type annotation
- **WHEN** a Rust file contains `let x: i32 = compute();`
- **THEN** the `assignments` table SHALL contain a row with target_var="x", source_expr="compute()"

#### Scenario: Mutable binding
- **WHEN** a Rust file contains `let mut counter = 0;`
- **THEN** the `assignments` table SHALL contain a row with target_var="counter"

#### Scenario: Destructuring pattern
- **WHEN** a Rust file contains `let (a, b) = get_pair();`
- **THEN** the `assignments` table SHALL contain rows for both "a" and "b"
- **AND** `assignment_sources` SHALL link both to "get_pair()"

#### Scenario: Assignment with source variable
- **WHEN** a Rust file contains `let y = x + 1;`
- **THEN** the `assignment_sources` table SHALL contain a row linking target "y" to source "x"

---

### Requirement: Rust Function Call Extraction for Call Graph
The Rust extractor SHALL populate the language-agnostic `function_call_args` table for all function and method calls in Rust source files.

#### Scenario: Simple function call
- **WHEN** a Rust file contains `process(data);` inside function `main`
- **THEN** the `function_call_args` table SHALL contain a row with caller_function="main", callee_function="process", argument_expr="data"

#### Scenario: Method call
- **WHEN** a Rust file contains `vec.push(item);`
- **THEN** the `function_call_args` table SHALL contain a row with callee_function="push", argument_expr="item"

#### Scenario: Chained method calls
- **WHEN** a Rust file contains `items.iter().filter(|x| x > 0).collect();`
- **THEN** the `function_call_args` table SHALL contain rows for iter(), filter(), and collect()

#### Scenario: Multiple arguments
- **WHEN** a Rust file contains `calculate(a, b, c);`
- **THEN** the `function_call_args` table SHALL contain 3 rows with argument_index 0, 1, 2

---

### Requirement: Rust Return Extraction for DFG
The Rust extractor SHALL populate the language-agnostic `function_returns` and `function_return_sources` tables for all return statements in Rust source files.

#### Scenario: Explicit return
- **WHEN** a Rust file contains `return result;` in function `compute`
- **THEN** the `function_returns` table SHALL contain a row with function_name="compute", return_expr="result"
- **AND** `function_return_sources` SHALL link the return to source variable "result"

#### Scenario: Implicit return
- **WHEN** a Rust file contains a function ending with `x + y` (no semicolon)
- **THEN** the `function_returns` table SHALL contain a row with return_expr="x + y"
- **AND** `function_return_sources` SHALL link to both "x" and "y"

---

### Requirement: Rust CFG Extraction
The Rust extractor SHALL populate the language-agnostic `cfg_blocks`, `cfg_edges`, and `cfg_block_statements` tables for control flow in Rust source files.

#### Scenario: If expression
- **WHEN** a Rust file contains `if condition { a } else { b }`
- **THEN** the `cfg_blocks` table SHALL contain blocks for condition, then-branch, else-branch
- **AND** `cfg_edges` SHALL connect condition to both branches

#### Scenario: Match expression
- **WHEN** a Rust file contains `match x { A => ..., B => ... }`
- **THEN** the `cfg_blocks` table SHALL contain blocks for the scrutinee and each arm
- **AND** `cfg_edges` SHALL connect scrutinee to all arms

#### Scenario: Loop expression
- **WHEN** a Rust file contains `loop { ... }`
- **THEN** the `cfg_blocks` table SHALL contain a block with block_type="loop"
- **AND** `cfg_edges` SHALL include back-edge for loop continuation

#### Scenario: While loop
- **WHEN** a Rust file contains `while condition { body }`
- **THEN** the `cfg_blocks` table SHALL contain blocks for condition and body
- **AND** `cfg_edges` SHALL connect body back to condition

#### Scenario: For loop
- **WHEN** a Rust file contains `for item in items { ... }`
- **THEN** the `cfg_blocks` table SHALL contain blocks for iterator and body

---

### Requirement: Rust Strategy Registration in DFGBuilder
The DFGBuilder SHALL load and execute Rust-specific graph strategies to produce Rust-aware DFG edges.

#### Scenario: RustTraitStrategy loaded
- **WHEN** DFGBuilder is instantiated
- **THEN** RustTraitStrategy SHALL be present in self.strategies list
- **AND** build_unified_flow_graph() SHALL execute RustTraitStrategy.build()

#### Scenario: RustAsyncStrategy loaded
- **WHEN** DFGBuilder is instantiated
- **THEN** RustAsyncStrategy SHALL be present in self.strategies list
- **AND** build_unified_flow_graph() SHALL execute RustAsyncStrategy.build()

#### Scenario: Trait implementation edges
- **WHEN** a Rust file contains `impl Trait for Type`
- **THEN** RustTraitStrategy SHALL produce "implements_trait" edges linking impl to trait

#### Scenario: Async await edges
- **WHEN** a Rust file contains an async function with .await points
- **THEN** RustAsyncStrategy SHALL produce "await_point" edges linking function to await expressions

---

### Requirement: ZERO FALLBACK Compliance for Rust Strategies
Rust graph strategies SHALL NOT check for table existence before querying. They SHALL fail immediately if required tables are missing.

#### Scenario: Missing table causes immediate failure
- **WHEN** rust_impl_blocks table does not exist
- **AND** RustTraitStrategy.build() is called
- **THEN** the strategy SHALL raise an exception
- **AND** SHALL NOT return empty results silently

#### Scenario: No table existence checks
- **WHEN** examining RustTraitStrategy or RustAsyncStrategy source code
- **THEN** there SHALL be no queries to sqlite_master checking table existence
- **AND** there SHALL be no conditional returns based on table presence

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

#### Scenario: Warp sources
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain source patterns for `warp::body::json` with category `http_request`
- **AND** it SHALL contain source patterns for `warp::path::param` with category `http_request`

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

#### Scenario: Network sinks (SSRF)
- **WHEN** TaintRegistry is initialized with Rust patterns
- **THEN** it SHALL contain sink patterns for `TcpStream::connect` with category `ssrf`

---

### Requirement: Rust Pattern Registration Integration
The Rust pattern registration module SHALL be auto-discovered by the orchestrator.
Discovery requires BOTH a `find_*` function (for module discovery) AND `register_taint_patterns()` function (for pattern registration).

#### Scenario: Module discovery via find_* function
- **WHEN** orchestrator runs `_discover_all_rules()` at `orchestrator.py:68-100`
- **THEN** `rust_injection_analyze.py` SHALL define a function named `find_rust_injection_issues`
- **AND** the function SHALL accept a `StandardRuleContext` parameter
- **AND** the function SHALL return `list[StandardFinding]`
- **AND** the orchestrator at `orchestrator.py:93` SHALL discover the module via this function

#### Scenario: Pattern registration function
- **WHEN** `rust_injection_analyze.py` is discovered by orchestrator
- **THEN** it SHALL define a function named exactly `register_taint_patterns`
- **AND** the function SHALL accept a single `taint_registry` parameter
- **AND** the orchestrator at `orchestrator.py:471-495` SHALL invoke it via `collect_rule_patterns()`

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
- **AND** the logging module uses loguru underneath (configured at `utils/logging.py:25-28`)

#### Scenario: No print statements
- **WHEN** examining rust_injection_analyze.py source code
- **THEN** there SHALL be no bare `print()` calls
- **AND** all diagnostic output SHALL use the logger

