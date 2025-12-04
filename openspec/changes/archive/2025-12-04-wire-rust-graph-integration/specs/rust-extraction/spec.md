## Schema Context

Target tables are defined in `theauditor/indexer/schemas/core_schema.py`. Extraction functions MUST produce dictionaries matching these schemas exactly.

### assignments table (core_schema.py:92-113)

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| file | TEXT | NO | - | FK to files.path |
| line | INTEGER | NO | - | |
| col | INTEGER | NO | 0 | Column offset |
| target_var | TEXT | NO | - | Variable name being assigned |
| source_expr | TEXT | NO | - | RHS expression as string |
| in_function | TEXT | NO | - | Containing function or "global" |
| property_path | TEXT | YES | - | For nested assignments |

**Primary Key**: (file, line, col, target_var)

### assignment_sources table (core_schema.py:233-263)

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | INTEGER | NO | auto | Primary key |
| assignment_file | TEXT | NO | - | FK to assignments |
| assignment_line | INTEGER | NO | - | |
| assignment_col | INTEGER | NO | 0 | Column offset |
| assignment_target | TEXT | NO | - | |
| source_var_name | TEXT | NO | - | Variable referenced in source_expr |

### function_call_args table (core_schema.py:138-162)

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| file | TEXT | NO | - | FK to files.path |
| line | INTEGER | NO | - | |
| caller_function | TEXT | NO | - | Function containing the call |
| callee_function | TEXT | NO | - | Function being called (CHECK != '') |
| argument_index | INTEGER | YES | - | 0-based argument position |
| argument_expr | TEXT | YES | - | Argument expression as string |
| param_name | TEXT | YES | - | Named parameter if known |
| callee_file_path | TEXT | YES | - | Resolved path to callee |

### function_returns table (core_schema.py:187-206)

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| file | TEXT | NO | - | FK to files.path |
| line | INTEGER | NO | - | |
| col | INTEGER | NO | 0 | |
| function_name | TEXT | NO | - | |
| return_expr | TEXT | NO | - | Return expression as string |
| has_jsx | BOOLEAN | - | 0 | N/A for Rust |
| returns_component | BOOLEAN | - | 0 | N/A for Rust |
| cleanup_operations | TEXT | YES | - | |

**Primary Key**: (file, line, col, function_name)

### function_return_sources table (core_schema.py:293-318)

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | INTEGER | NO | auto | Primary key |
| return_file | TEXT | NO | - | FK to function_returns |
| return_line | INTEGER | NO | - | |
| return_col | INTEGER | NO | 0 | Column offset |
| return_function | TEXT | NO | - | |
| return_var_name | TEXT | NO | - | Variable referenced in return_expr |

### cfg_blocks table (core_schema.py:392-410)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | INTEGER | NO | Primary key (auto-increment) |
| file | TEXT | NO | FK to files.path |
| function_name | TEXT | NO | |
| block_type | TEXT | NO | "if", "match", "loop", "while", "for", etc. |
| start_line | INTEGER | YES | |
| end_line | INTEGER | YES | |
| condition_expr | TEXT | YES | Condition expression for branches |

### cfg_edges table (core_schema.py:412-431)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | INTEGER | NO | Primary key |
| file | TEXT | NO | FK to files.path |
| function_name | TEXT | NO | |
| source_block_id | INTEGER | NO | FK to cfg_blocks.id |
| target_block_id | INTEGER | NO | FK to cfg_blocks.id |
| edge_type | TEXT | NO | "true", "false", "unconditional", "back" |

### cfg_block_statements table (core_schema.py:433-447)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| block_id | INTEGER | NO | FK to cfg_blocks.id |
| statement_type | TEXT | NO | |
| line | INTEGER | NO | |
| statement_text | TEXT | YES | |

---

## Reference Implementations

Follow these Python extraction patterns in `theauditor/ast_extractors/python/`:

| Function | Location | Pattern |
|----------|----------|---------|
| Assignment extraction | `core_extractors.py:368-410` | `extract_python_assignments()` |
| Function call extraction | `core_extractors.py:427-500` | `extract_python_calls_with_args()` |
| CFG extraction | `cfg_extractor.py:12-200` | `extract_python_cfg()` |

---

## Infrastructure Compliance

### Logging Requirement

All new extraction functions SHALL use the standard loguru logger for tracing:

```python
from theauditor.utils.logging import logger

def extract_rust_assignments(root_node: Any, file_path: str) -> list[dict]:
    """Extract variable assignments from Rust AST."""
    logger.debug(f"extract_rust_assignments: processing {file_path}")
    # ... implementation
```

**Pattern**: Use `logger.debug()` for entry/exit tracing, `logger.warning()` for recoverable issues.

### Return Value Requirements

Extraction functions return dicts that map to schema columns. The orchestrator adds certain fields automatically:

| Field | Provided By | Notes |
|-------|-------------|-------|
| `file` | Orchestrator | Added from file_info, NOT returned by extraction function |
| `col` | Extraction function OR default | Defaults to 0 if not provided |
| All other columns | Extraction function | Must match schema column names exactly |

**Example - assignments extraction return value:**
```python
# Extraction function returns (NO 'file' key):
{
    "target_var": "x",
    "source_expr": "42",
    "line": 10,
    "col": 0,           # Optional, defaults to 0
    "in_function": "main",
    "property_path": None,  # Optional
}
# Orchestrator adds 'file' before storage
```

### Fidelity Integration (Automatic)

**No manual fidelity code required.** The rust.py extractor (line 84) already calls:

```python
return FidelityToken.attach_manifest(result)
```

This polymorphic function:
1. Iterates ALL keys in result dict (except those starting with `_`)
2. For each list of dicts, generates `{tx_id, columns, count, bytes}` manifest
3. Storage layer creates matching receipt
4. `reconcile_fidelity()` enforces guards automatically

**New language-agnostic keys are automatically tracked** - no additional wiring needed.

Guards enforced at storage layer (`theauditor/indexer/fidelity.py`):
- LEGACY FORMAT VIOLATION: Rejects int format, requires dict manifest
- TRANSACTION MISMATCH: tx_id echo verification
- SCHEMA VIOLATION: Column preservation check
- COUNT CHECK: Row count verification

---

## ADDED Requirements

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
