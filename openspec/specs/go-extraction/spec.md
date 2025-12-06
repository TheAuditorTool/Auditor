# go-extraction Specification

## Purpose
TBD - created by archiving change add-go-taint-extraction. Update Purpose after archive.
## Requirements
### Requirement: Go Assignment Extraction for DFG
The Go extractor SHALL populate the language-agnostic `assignments` and `assignment_sources` tables for all variable bindings in Go source files.

#### Scenario: Short variable declaration
- **WHEN** a Go file contains `x := 42`
- **THEN** the `assignments` table SHALL contain a row with target_var="x", source_expr="42"
- **AND** the row SHALL include file path, line number, and containing function

#### Scenario: Regular assignment
- **WHEN** a Go file contains `x = compute()`
- **THEN** the `assignments` table SHALL contain a row with target_var="x", source_expr="compute()"

#### Scenario: Multiple assignment targets
- **WHEN** a Go file contains `a, b := getPair()`
- **THEN** the `assignments` table SHALL contain rows for both "a" and "b"
- **AND** `assignment_sources` SHALL link both to "getPair()"

#### Scenario: Blank identifier skipped
- **WHEN** a Go file contains `_, err := doSomething()`
- **THEN** the `assignments` table SHALL contain a row for "err" only
- **AND** no row SHALL exist for "_"

#### Scenario: Compound assignment
- **WHEN** a Go file contains `counter += 1`
- **THEN** the `assignments` table SHALL contain a row with target_var="counter", source_expr="counter + 1"

#### Scenario: Assignment with source variable
- **WHEN** a Go file contains `y := x + 1`
- **THEN** the `assignment_sources` table SHALL contain a row linking target "y" to source "x"

---

### Requirement: Go Function Call Extraction for Call Graph
The Go extractor SHALL populate the language-agnostic `function_call_args` table for all function and method calls in Go source files.

#### Scenario: Simple function call
- **WHEN** a Go file contains `process(data)` inside function `main`
- **THEN** the `function_call_args` table SHALL contain a row with caller_function="main", callee_function="process", argument_expr="data"

#### Scenario: Method call
- **WHEN** a Go file contains `slice.Append(item)`
- **THEN** the `function_call_args` table SHALL contain a row with callee_function="slice.Append", argument_expr="item"

#### Scenario: Chained method calls
- **WHEN** a Go file contains `builder.WithName(name).Build()`
- **THEN** the `function_call_args` table SHALL contain rows for WithName() and Build()

#### Scenario: Multiple arguments
- **WHEN** a Go file contains `calculate(a, b, c)`
- **THEN** the `function_call_args` table SHALL contain 3 rows with argument_index 0, 1, 2

#### Scenario: Variadic call
- **WHEN** a Go file contains `fmt.Printf(format, args...)`
- **THEN** the `function_call_args` table SHALL contain rows for format and the expanded args

---

### Requirement: Go Return Extraction for DFG
The Go extractor SHALL populate the language-agnostic `function_returns` and `function_return_sources` tables for all return statements in Go source files.

#### Scenario: Single return value
- **WHEN** a Go file contains `return result` in function `compute`
- **THEN** the `function_returns` table SHALL contain a row with function_name="compute", return_expr="result"
- **AND** `function_return_sources` SHALL link the return to source variable "result"

#### Scenario: Multiple return values
- **WHEN** a Go file contains `return data, nil` in function `fetch`
- **THEN** the `function_returns` table SHALL contain a row with return_expr="data, nil"
- **AND** `function_return_sources` SHALL link to "data"

#### Scenario: Named return with naked return
- **WHEN** a Go file contains `func foo() (result int) { result = 42; return }`
- **THEN** the `function_returns` table SHALL contain a row for the naked return
- **AND** `function_return_sources` SHALL link to "result"

---

### Requirement: Go Parameter Extraction (Language-Specific)
Go function parameters SHALL be stored in the Go-specific `go_func_params` table (NOT the language-agnostic `func_params` table). This is because Go has richer parameter semantics (receivers, variadic, grouped params) that require dedicated schema.

**Note:** This extraction is ALREADY IMPLEMENTED via `go_impl.extract_go_func_params()` and stored via `go_storage._store_go_func_params()`. No new work required for this proposal.

#### Scenario: Simple parameter
- **WHEN** a Go file contains `func process(data string)`
- **THEN** the `go_func_params` table SHALL contain a row with function_name="process", param_name="data", param_index=0

#### Scenario: Grouped parameters
- **WHEN** a Go file contains `func process(a, b int)`
- **THEN** the `go_func_params` table SHALL contain rows for "a" (index 0) and "b" (index 1)

#### Scenario: Variadic parameter
- **WHEN** a Go file contains `func process(args ...string)`
- **THEN** the `go_func_params` table SHALL contain a row with param_name="args", param_index=0, is_variadic=true

#### Scenario: Receiver method
- **WHEN** a Go file contains `func (s *Server) Handle(req Request)`
- **THEN** the `go_func_params` table SHALL contain a row for "req" with param_index=0
- **AND** the receiver "s" SHALL be tracked in `go_methods` table (receiver_type, receiver_name fields)

---

### Requirement: Go Logging Integration
The Go extractor SHALL use the centralized logging system for all debug and info messages.

#### Scenario: Logging import
- **WHEN** examining go.py source code
- **THEN** it SHALL contain `from theauditor.utils.logging import logger`

#### Scenario: Debug logging for extraction counts
- **WHEN** Go extraction completes for a file
- **THEN** logger.debug SHALL be called with extraction statistics
- **AND** the message SHALL include file path and counts per table

#### Scenario: No print statements
- **WHEN** examining go.py and go_impl.py source code
- **THEN** there SHALL be no bare `print()` calls for status output
- **AND** all output SHALL use the logger

---

### Requirement: Go Extractor Return Dict Format
The Go extractor SHALL return data using dict keys that match core_storage.py handler names (NOT table names).

#### Scenario: Extractor return dict keys match storage handlers
- **WHEN** Go extraction completes
- **THEN** the return dict SHALL use key `"assignments"` (handler name)
- **AND** the return dict SHALL use key `"function_calls"` (NOT `"function_call_args"`)
- **AND** the return dict SHALL use key `"returns"` (NOT `"function_returns"`)

#### Scenario: Source variables embedded in assignments
- **WHEN** an assignment dict is created
- **THEN** it SHALL contain a `"source_vars"` array property (list of variable names)
- **AND** the storage layer SHALL write these to `assignment_sources` table automatically

#### Scenario: Return variables embedded in returns
- **WHEN** a return dict is created
- **THEN** it SHALL contain a `"return_vars"` array property (list of variable names)
- **AND** the storage layer SHALL write these to `function_return_sources` table automatically

#### Scenario: All required columns present in dicts
- **WHEN** an assignment dict is created
- **THEN** it SHALL contain: file, line, col, target_var, source_expr, in_function, property_path, source_vars
- **WHEN** a function_call dict is created
- **THEN** it SHALL contain: file, line, caller_function, callee_function, argument_index, argument_expr, param_name, callee_file_path
- **WHEN** a return dict is created
- **THEN** it SHALL contain: file, line, col, function_name, return_expr, return_vars

---

### Requirement: ZERO FALLBACK Compliance for Go Extraction
The Go extractor SHALL NOT use fallback logic when extracting data. Missing or malformed AST nodes SHALL be skipped with debug logging, NOT silently ignored or substituted.

#### Scenario: Malformed AST node
- **WHEN** a tree-sitter node is missing expected children
- **THEN** the extractor SHALL log a debug message with the file and line
- **AND** SHALL skip that node
- **AND** SHALL NOT substitute default values or guess the structure

#### Scenario: No try-except fallbacks
- **WHEN** examining go.py extraction logic
- **THEN** there SHALL be no try-except blocks that swallow errors and return defaults
- **AND** parsing errors SHALL propagate or be logged explicitly

---

