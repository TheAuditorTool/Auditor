# Implementation Tasks

## 0. Verification
- [x] 0.1 Read rust_impl.py - Confirm no assignment extraction exists
- [x] 0.2 Read rust.py extractor - Confirm only rust_* keys returned
- [x] 0.3 Read dfg_builder.py - Confirm Rust strategies not loaded
- [x] 0.4 Read rust_traits.py - Confirm ZERO FALLBACK violation exists
- [x] 0.5 Read rust_async.py - Confirm ZERO FALLBACK violation exists
- [x] 0.6 Document all discrepancies in verification.md

## 1. Phase 1: Add Extraction Functions to rust_impl.py

### 1.1 Add extract_rust_assignments()
- [x] 1.1.1 Create function signature matching Python/Node pattern
- [x] 1.1.2 Query tree-sitter for `let_declaration` nodes with pattern/value
- [x] 1.1.3 Extract target_var from pattern node
- [x] 1.1.4 Extract source_expr from value node
- [x] 1.1.5 Track containing function context
- [x] 1.1.6 Return list with source_vars field (storage layer expands to assignment_sources)
- [x] 1.1.7 Handle destructuring patterns (let (a, b) = ...)
- [x] 1.1.8 Handle mutable bindings (let mut x = ...)

### 1.2 Add extract_rust_function_calls()
- [x] 1.2.1 Create function signature
- [x] 1.2.2 Query tree-sitter for `call_expression` nodes
- [x] 1.2.3 Extract callee_function from function node
- [x] 1.2.4 Extract arguments from arguments node
- [x] 1.2.5 Track argument positions (argument_index)
- [x] 1.2.6 Track containing function (caller_function)
- [x] 1.2.7 Return list matching function_call_args schema
- [x] 1.2.8 Handle method calls (receiver.method())
- [x] 1.2.9 Handle chained calls (a.b().c())

### 1.3 Add extract_rust_returns()
- [x] 1.3.1 Create function signature
- [x] 1.3.2 Query tree-sitter for `return_expression` nodes
- [x] 1.3.3 Extract return_expr from expression child
- [x] 1.3.4 Track containing function (function_name)
- [x] 1.3.5 Extract source variables from return expression
- [x] 1.3.6 Return list with return_vars field (storage layer expands to function_return_sources)
- [x] 1.3.7 Handle implicit returns (last expression without semicolon)

### 1.4 Add extract_rust_cfg()
- [x] 1.4.1 Create function signature
- [x] 1.4.2 Query tree-sitter for control flow nodes:
  - `if_expression`
  - `match_expression`
  - `loop_expression`
  - `while_expression`
  - `for_expression`
- [x] 1.4.3 Build block nodes with start_line, end_line, block_type
- [x] 1.4.4 Build edges between blocks (condition true/false branches)
- [x] 1.4.5 Track statements within each block
- [x] 1.4.6 Return list of function CFGs (storage layer expands to cfg_blocks/edges/statements)
- [x] 1.4.7 Handle nested control flow
- [x] 1.4.8 Handle early returns within blocks

## 2. Phase 2: Wire Extractor to New Functions

### 2.1 Modify RustExtractor.extract() in rust.py
- [x] 2.1.1 Import new functions from rust_impl (via rust_core alias)
- [x] 2.1.2 Call extract_rust_assignments()
- [x] 2.1.3 Call extract_rust_function_calls()
- [x] 2.1.4 Call extract_rust_returns()
- [x] 2.1.5 Call extract_rust_cfg()
- [x] 2.1.6 Add to result dict (keys match core_storage.py handlers):
  - `assignments` key
  - `function_calls` key
  - `returns` key
  - `cfg` key

## 3. Phase 3: Register Rust Strategies in DFGBuilder

### 3.1 Modify dfg_builder.py
- [x] 3.1.1 Add import: `from .strategies.rust_traits import RustTraitStrategy`
- [x] 3.1.2 Add import: `from .strategies.rust_async import RustAsyncStrategy`
- [x] 3.1.3 Add `RustTraitStrategy()` to self.strategies list
- [x] 3.1.4 Add `RustAsyncStrategy()` to self.strategies list

## 4. Phase 4: Fix ZERO FALLBACK Violations

### 4.1 Fix rust_traits.py (2 violations)
- [x] 4.1.1 Remove table existence check at lines 37-47 (`rust_impl_blocks` table)
- [x] 4.1.2 Remove table existence check at lines 174-179 (`rust_trait_methods` table)
- [x] 4.1.3 Let queries fail naturally if tables don't exist
- [x] 4.1.4 Add comment explaining ZERO FALLBACK policy at top of build() method

### 4.2 Fix rust_async.py (2 violations)
- [x] 4.2.1 Remove table existence check at lines 41-51 (`rust_async_functions` table)
- [x] 4.2.2 Remove table existence check at lines 133-138 (`rust_await_points` table)
- [x] 4.2.3 Let queries fail naturally if tables don't exist
- [x] 4.2.4 Add comment explaining ZERO FALLBACK policy at top of build() method

## 5. Testing

### 5.1 Verify Table Population
- [x] 5.1.1 Run extraction on sample Rust code (unit test - no full index needed)
- [x] 5.1.2 Query assignments table for .rs files - 5 assignments found, correct schema
- [x] 5.1.3 Query function_calls table for .rs files - 7 calls found, correct schema
- [x] 5.1.4 Query cfg_blocks table for .rs files - 3 functions, 16 blocks, 16 edges
- [x] 5.1.5 Verify non-zero counts for all - ALL PASS

### 5.2 Verify Graph Generation
- [x] 5.2.1 Verify DFGBuilder imports Rust strategies - PASS
- [x] 5.2.2 Verify RustTraitStrategy in strategies list - PASS
- [x] 5.2.3 Verify RustAsyncStrategy in strategies list - PASS
- [x] 5.2.4 Verify Rust strategies instantiate without error - PASS
- [x] 5.2.5 Verify ZERO FALLBACK compliance (no sqlite_master checks) - PASS

### 5.3 Integration Tests
- [x] 5.3.1 Run existing test suite - 608 passed, pre-existing failures unrelated
- [x] 5.3.2 Add test_rust_graph_integration.py - 20 tests created
- [x] 5.3.3 Test: Rust assignments extracted - TestRustAssignmentExtraction (4 tests)
- [x] 5.3.4 Test: Rust function calls extracted - TestRustFunctionCallExtraction (3 tests)
- [x] 5.3.5 Test: Rust CFG extracted - TestRustCFGExtraction (3 tests)
- [x] 5.3.6 Test: DFG includes Rust data - TestDFGBuilderRustStrategies + TestExtractorWiring (7 tests)
