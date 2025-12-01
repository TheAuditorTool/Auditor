## ADDED Requirements

### Requirement: Async Linter Orchestration
The linter orchestration SHALL execute all linters in parallel using asyncio.

#### Scenario: Parallel linter execution
- **WHEN** the linter orchestrator runs with multiple linter types
- **THEN** all applicable linters SHALL execute concurrently via asyncio.gather()
- **AND** total execution time SHALL be approximately the duration of the slowest linter

#### Scenario: Exception isolation per linter
- **WHEN** one linter fails with an exception during parallel execution
- **THEN** other linters SHALL continue to completion
- **AND** the failed linter's exception SHALL be logged
- **AND** partial results from successful linters SHALL be returned

### Requirement: Typed Finding Results
The linter pipeline SHALL return typed Finding dataclass objects instead of loose dictionaries.

#### Scenario: Finding dataclass structure
- **WHEN** a linter produces findings
- **THEN** each finding SHALL be a Finding dataclass with: tool, file, line, column, rule, message, severity, category
- **AND** severity SHALL be a Literal type constrained to "error", "warning", "info"

#### Scenario: Backward compatible serialization
- **WHEN** findings are written to database or JSON
- **THEN** Finding.to_dict() SHALL produce the same structure as the previous dict format
- **AND** lint.json output format SHALL remain unchanged

### Requirement: Tool-Specific Batching Strategy
The linter orchestrator SHALL apply appropriate batching strategies per tool type.

#### Scenario: Ruff runs without batching
- **WHEN** Ruff linter executes
- **THEN** all Python files SHALL be passed in a single invocation
- **AND** no Python-level batching loop SHALL be used

#### Scenario: Mypy runs without batching
- **WHEN** Mypy linter executes
- **THEN** all Python files SHALL be passed in a single invocation
- **AND** Mypy SHALL have full project context for cross-file type inference

#### Scenario: ESLint uses dynamic batching
- **WHEN** ESLint linter executes on many files
- **THEN** files SHALL be chunked to avoid OS command line length limits
- **AND** chunk size SHALL be calculated dynamically based on path lengths

#### Scenario: Clippy runs at crate level
- **WHEN** Clippy linter executes
- **THEN** cargo clippy SHALL run on the entire crate
- **AND** output SHALL be filtered to match requested file list

#### Scenario: golangci-lint runs without batching
- **WHEN** golangci-lint linter executes on Go files
- **THEN** all Go files SHALL be processed in a single invocation
- **AND** golangci-lint SHALL handle file discovery internally

#### Scenario: shellcheck runs without batching
- **WHEN** shellcheck linter executes on Bash files
- **THEN** all .sh/.bash files SHALL be passed in a single invocation
- **AND** shellcheck SHALL handle multiple files efficiently

### Requirement: Go and Bash Linter Support
The pipeline SHALL support linting for Go and Bash files when tools are available.

#### Scenario: Go linting with golangci-lint
- **WHEN** Go files exist in the project AND golangci-lint is available
- **THEN** GolangciLinter SHALL execute golangci-lint with JSON output
- **AND** findings SHALL be parsed into Finding objects

#### Scenario: Bash linting with shellcheck
- **WHEN** Bash files (.sh, .bash) exist in the project AND shellcheck is available
- **THEN** ShellcheckLinter SHALL execute shellcheck with JSON output
- **AND** findings SHALL be parsed into Finding objects

#### Scenario: Optional tools graceful skip
- **WHEN** golangci-lint or shellcheck is not installed
- **THEN** the respective linter SHALL be silently skipped
- **AND** no error SHALL be raised
- **AND** other linters SHALL continue execution

### Requirement: Toolbox Path Resolution
The pipeline SHALL use a centralized Toolbox class for all runtime path resolution.

#### Scenario: Binary path resolution
- **WHEN** a linter needs to find its binary (ruff, eslint, mypy)
- **THEN** Toolbox.get_binary(name) SHALL return the correct platform-specific path
- **AND** Windows .exe extensions SHALL be handled automatically

#### Scenario: Config path resolution
- **WHEN** a linter needs its config file (pyproject.toml, eslint.config.cjs)
- **THEN** Toolbox.get_config(name) SHALL return the path within .theauditor_tools

#### Scenario: Health check
- **WHEN** the orchestrator initializes
- **THEN** Toolbox.is_healthy SHALL verify the venv and tools exist
- **AND** a clear error message SHALL be displayed if setup is required

### Requirement: Sync Wrapper Backward Compatibility
The linter orchestrator SHALL provide a synchronous wrapper for the async implementation.

#### Scenario: run_all_linters signature unchanged
- **WHEN** external code calls LinterOrchestrator.run_all_linters(workset_files)
- **THEN** the method SHALL accept the same parameters as before
- **AND** the method SHALL return list[dict[str, Any]] for compatibility

#### Scenario: asyncio.run used internally
- **WHEN** run_all_linters() is called from sync context
- **THEN** it SHALL wrap the async implementation with asyncio.run()
- **AND** callers SHALL not need to use async/await
