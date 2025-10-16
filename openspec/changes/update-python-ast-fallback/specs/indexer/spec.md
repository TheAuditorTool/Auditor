## ADDED Requirements
### Requirement: Python parser must emit CPython AST payloads
- **MUST** return 	ype = "python_ast" objects wrapping CPython st.AST nodes for all Python parsing entry points (parse_file, parse_content, parse_files_batch).
- **MUST NOT** hand Tree-sitter Python structures to downstream extractors until those extractors support them.
- **MUST** document this contract so future parser changes include extractor parity work.

#### Scenario: Indexer processes a Python file with Tree-sitter installed
- **GIVEN** Tree-sitter libraries are present in the environment
- **AND** ASTParser.parse_file is invoked on xample.py
- **WHEN** the indexer asks PythonExtractor to read imports
- **THEN** the parser returns a payload where 	ree["type"] == "python_ast"
- **AND** the extractor successfully records imports in the efs table.

#### Scenario: Batch parsing respects CPython AST contract
- **GIVEN** parse_files_batch is called with a mixed-language set including Python files
- **WHEN** results are cached for the indexer
- **THEN** every Python entry in the batch exposes CPython AST metadata, ensuring downstream extractors behave as before the regression.
