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
- [ ] 1.1.1 Create function signature matching Python/Node pattern
- [ ] 1.1.2 Query tree-sitter for `let_declaration` nodes with pattern/value
- [ ] 1.1.3 Extract target_var from pattern node
- [ ] 1.1.4 Extract source_expr from value node
- [ ] 1.1.5 Track containing function context
- [ ] 1.1.6 Return tuple: (assignments_list, assignment_sources_list)
- [ ] 1.1.7 Handle destructuring patterns (let (a, b) = ...)
- [ ] 1.1.8 Handle mutable bindings (let mut x = ...)

### 1.2 Add extract_rust_function_calls()
- [ ] 1.2.1 Create function signature
- [ ] 1.2.2 Query tree-sitter for `call_expression` nodes
- [ ] 1.2.3 Extract callee_function from function node
- [ ] 1.2.4 Extract arguments from arguments node
- [ ] 1.2.5 Track argument positions (argument_index)
- [ ] 1.2.6 Track containing function (caller_function)
- [ ] 1.2.7 Return list matching function_call_args schema
- [ ] 1.2.8 Handle method calls (receiver.method())
- [ ] 1.2.9 Handle chained calls (a.b().c())

### 1.3 Add extract_rust_returns()
- [ ] 1.3.1 Create function signature
- [ ] 1.3.2 Query tree-sitter for `return_expression` nodes
- [ ] 1.3.3 Extract return_expr from expression child
- [ ] 1.3.4 Track containing function (function_name)
- [ ] 1.3.5 Extract source variables from return expression
- [ ] 1.3.6 Return tuple: (function_returns_list, function_return_sources_list)
- [ ] 1.3.7 Handle implicit returns (last expression without semicolon)

### 1.4 Add extract_rust_cfg()
- [ ] 1.4.1 Create function signature
- [ ] 1.4.2 Query tree-sitter for control flow nodes:
  - `if_expression`
  - `match_expression`
  - `loop_expression`
  - `while_expression`
  - `for_expression`
- [ ] 1.4.3 Build block nodes with start_line, end_line, block_type
- [ ] 1.4.4 Build edges between blocks (condition true/false branches)
- [ ] 1.4.5 Track statements within each block
- [ ] 1.4.6 Return tuple: (cfg_blocks_list, cfg_edges_list, cfg_block_statements_list)
- [ ] 1.4.7 Handle nested control flow
- [ ] 1.4.8 Handle early returns within blocks

## 2. Phase 2: Wire Extractor to New Functions

### 2.1 Modify RustExtractor.extract() in rust.py
- [ ] 2.1.1 Import new functions from rust_impl
- [ ] 2.1.2 Call extract_rust_assignments() and unpack tuple
- [ ] 2.1.3 Call extract_rust_function_calls()
- [ ] 2.1.4 Call extract_rust_returns() and unpack tuple
- [ ] 2.1.5 Call extract_rust_cfg() and unpack tuple
- [ ] 2.1.6 Add to result dict:
  - `assignments` key
  - `assignment_sources` key
  - `function_call_args` key (or `function_calls` - check Python extractor pattern)
  - `function_returns` key
  - `function_return_sources` key
  - `cfg_blocks` key
  - `cfg_edges` key
  - `cfg_block_statements` key

## 3. Phase 3: Register Rust Strategies in DFGBuilder

### 3.1 Modify dfg_builder.py
- [ ] 3.1.1 Add import: `from .strategies.rust_traits import RustTraitStrategy`
- [ ] 3.1.2 Add import: `from .strategies.rust_async import RustAsyncStrategy`
- [ ] 3.1.3 Add `RustTraitStrategy()` to self.strategies list
- [ ] 3.1.4 Add `RustAsyncStrategy()` to self.strategies list

## 4. Phase 4: Fix ZERO FALLBACK Violations

### 4.1 Fix rust_traits.py (2 violations)
- [ ] 4.1.1 Remove table existence check at lines 37-47 (`rust_impl_blocks` table)
- [ ] 4.1.2 Remove table existence check at lines 174-179 (`rust_trait_methods` table)
- [ ] 4.1.3 Let queries fail naturally if tables don't exist
- [ ] 4.1.4 Add comment explaining ZERO FALLBACK policy at top of build() method

### 4.2 Fix rust_async.py (2 violations)
- [ ] 4.2.1 Remove table existence check at lines 41-51 (`rust_async_functions` table)
- [ ] 4.2.2 Remove table existence check at lines 133-138 (`rust_await_points` table)
- [ ] 4.2.3 Let queries fail naturally if tables don't exist
- [ ] 4.2.4 Add comment explaining ZERO FALLBACK policy at top of build() method

## 5. Testing

### 5.1 Verify Table Population
- [ ] 5.1.1 Run `aud full --offline` on a Rust codebase
- [ ] 5.1.2 Query assignments table for .rs files
- [ ] 5.1.3 Query function_call_args table for .rs files
- [ ] 5.1.4 Query cfg_blocks table for .rs files
- [ ] 5.1.5 Verify non-zero counts for all

### 5.2 Verify Graph Generation
- [ ] 5.2.1 Run `aud graph build`
- [ ] 5.2.2 Query DFG for Rust variable flow
- [ ] 5.2.3 Query call graph for Rust function calls
- [ ] 5.2.4 Verify Rust strategies produce edges

### 5.3 Integration Tests
- [ ] 5.3.1 Run existing test suite
- [ ] 5.3.2 Add test_rust_graph_integration.py
- [ ] 5.3.3 Test: Rust assignments extracted
- [ ] 5.3.4 Test: Rust function calls extracted
- [ ] 5.3.5 Test: Rust CFG extracted
- [ ] 5.3.6 Test: DFG includes Rust data
