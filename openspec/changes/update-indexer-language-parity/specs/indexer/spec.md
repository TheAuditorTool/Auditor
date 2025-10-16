## MODIFIED Requirements
### Requirement: Python AST Extraction Guarantees
Python parsing MUST return CPython AST payloads so downstream extractors (imports, assignments, CFG) operate on `ast.AST` nodes regardless of tree-sitter availability.

#### Scenario: Tree-sitter present
- **GIVEN** the environment has tree-sitter libraries installed
- **WHEN** `ASTParser.parse_file` processes a Python file
- **THEN** the returned payload MUST have `"type": "python_ast"`
- **AND** control-flow data MUST populate `cfg_blocks` / `cfg_edges` for that file

### Requirement: JavaScript Object Literal Persistence
JavaScript/TypeScript object literal metadata MUST be stored in `object_literals` with file path, property details, and function context.

#### Scenario: TypeScript service map
- **GIVEN** `JavaScriptExtractor` processes a file defining inline service maps (e.g., `order.service.ts`)
- **WHEN** the indexer flushes batches
- **THEN** every discovered property MUST be persisted to `object_literals`
- **AND** queries against the table MUST return those records without error
