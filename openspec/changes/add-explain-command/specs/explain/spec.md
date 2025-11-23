## ADDED Requirements

### Requirement: Explain Command

The system SHALL provide an `aud explain <target>` command that returns comprehensive context about a file, symbol, or React component in a single invocation.

#### Scenario: Explain file target

- **WHEN** user runs `aud explain path/to/file.ts`
- **THEN** output includes:
  - SYMBOLS DEFINED: All functions, classes, variables in file with line numbers and code snippets
  - REACT HOOKS USED: All hooks called in file (if React file)
  - DEPENDENCIES: Files imported by this file (outgoing imports)
  - DEPENDENTS: Files that import this file (incoming imports)
  - OUTGOING CALLS: Functions called from this file with line and arguments
  - INCOMING CALLS: Functions in this file called by other files
- **AND** each section is limited to 20 items with count shown
- **AND** response time is less than 100ms for files with fewer than 50 symbols

#### Scenario: Explain symbol target

- **WHEN** user runs `aud explain ClassName.methodName`
- **THEN** output includes:
  - DEFINITION: File, line, type, signature with code snippet
  - CALLERS: Who calls this symbol with file:line and code context
  - CALLEES: What this symbol calls with file:line
  - RELATED SYMBOLS: Sibling methods, related types
- **AND** uses symbol resolution to find qualified names from partial input

#### Scenario: Explain component target

- **WHEN** user runs `aud explain ComponentName` where ComponentName is a React component
- **THEN** output includes:
  - COMPONENT INFO: File, type (function/class), props type
  - HOOKS USED: All React hooks with line numbers
  - CHILD COMPONENTS: Components rendered by this component
  - DEPENDENCIES: Files imported by component file
- **AND** checks react_components table before falling back to symbol search

#### Scenario: Target auto-detection

- **WHEN** user provides a target argument
- **THEN** system auto-detects target type:
  - Files: Target ends with `.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `.rs`
  - Symbols: Target contains `.` with uppercase first character OR no extension
  - Components: Target is PascalCase and found in react_components table
- **AND** no explicit `--type` flag is required for common cases

#### Scenario: JSON output format

- **WHEN** user runs `aud explain <target> --format json`
- **THEN** output is valid JSON with structure:
  ```json
  {
    "target": "path/to/file.ts",
    "target_type": "file",
    "symbols": [...],
    "hooks": [...],
    "dependencies": [...],
    "dependents": [...],
    "outgoing_calls": [...],
    "incoming_calls": [...],
    "metadata": {
      "query_time_ms": 42,
      "truncated_sections": []
    }
  }
  ```
- **AND** JSON is parseable by standard JSON parsers

#### Scenario: Section filtering

- **WHEN** user runs `aud explain <target> --section deps`
- **THEN** output includes only the DEPENDENCIES section
- **AND** other sections are omitted

#### Scenario: Code snippets included by default

- **WHEN** user runs `aud explain <target>` without `--no-code` flag
- **THEN** each symbol and call includes source code snippet
- **AND** snippets use indentation-based block detection (max 15 lines)
- **AND** lines longer than 120 characters are truncated with `...`

#### Scenario: Code snippets disabled

- **WHEN** user runs `aud explain <target> --no-code`
- **THEN** output excludes source code snippets
- **AND** only file:line references are shown
- **AND** response time is reduced

### Requirement: Code Snippet Manager

The system SHALL provide a `CodeSnippetManager` utility class for reading source code lines with caching and safety limits.

#### Scenario: Line retrieval with cache

- **WHEN** `get_snippet(file, line)` is called multiple times for same file
- **THEN** file is read from disk only once
- **AND** subsequent calls use cached lines
- **AND** cache evicts oldest file when capacity (20 files) is exceeded

#### Scenario: Block expansion

- **WHEN** snippet is requested for a line ending with `{` or `:`
- **THEN** snippet includes subsequent lines with deeper indentation
- **AND** snippet includes closing brace/bracket if present
- **AND** total snippet is capped at 15 lines

#### Scenario: Binary file handling

- **WHEN** file cannot be decoded as UTF-8
- **THEN** `get_snippet()` returns `"[Binary file - no preview]"`
- **AND** no exception is raised

#### Scenario: Missing file handling

- **WHEN** file does not exist on disk
- **THEN** `get_snippet()` returns `"[File not found on disk]"`
- **AND** no exception is raised
- **AND** indexed data is still shown

#### Scenario: Large file skipping

- **WHEN** file size exceeds 1MB
- **THEN** `get_snippet()` returns `"[File too large to preview]"`
- **AND** no memory exhaustion occurs

### Requirement: Query Show-Code Flag

The system SHALL provide a `--show-code` flag on `aud query` command to include source code snippets in caller/callee output.

#### Scenario: Show code for callers

- **WHEN** user runs `aud query --symbol foo --show-callers --show-code`
- **THEN** each caller entry includes the source code line
- **AND** format is:
  ```
  1. file.ts:42
     callerFunc -> foo
     Code: const result = foo(arg1, arg2);
  ```

#### Scenario: Show code for callees

- **WHEN** user runs `aud query --symbol foo --show-callees --show-code`
- **THEN** each callee entry includes the source code line
- **AND** format includes the call expression
