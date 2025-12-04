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

