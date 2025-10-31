# Spec Delta: Code Quality Analysis

**Change ID**: `add-dead-code-detection`
**Capability**: code-quality (NEW)
**Operation**: ADDED Requirements

---

## ADDED Requirements

### Requirement: Dead Code Detection via CLI

The system SHALL provide a CLI command `aud deadcode` that detects modules never imported and functions never called using database-only analysis.

#### Scenario: Detect isolated module
- **WHEN** user runs `aud deadcode`
- **THEN** the system queries the database for files with symbols
- **AND** queries the database for imported files
- **AND** computes set difference to identify isolated modules
- **AND** displays results with file path, symbol count, and confidence level

#### Scenario: JSON output for CI/CD
- **WHEN** user runs `aud deadcode --format json`
- **THEN** the system outputs valid JSON with summary and isolated_modules arrays
- **AND** JSON includes confidence, recommendation, and reason for each module

#### Scenario: Fail on dead code for CI/CD
- **WHEN** user runs `aud deadcode --fail-on-dead-code`
- **AND** dead code is detected
- **THEN** the command exits with code 1
- **AND** prints error message with count of dead code files

#### Scenario: Path filtering
- **WHEN** user runs `aud deadcode --path-filter 'theauditor/%'`
- **THEN** the system ONLY analyzes files matching the path filter
- **AND** excludes all other files from analysis

#### Scenario: Exclusion patterns
- **WHEN** user runs `aud deadcode --exclude test --exclude migration`
- **THEN** the system skips files containing "test" or "migration" in path
- **AND** does not report them as dead code

---

### Requirement: Confidence Classification

The system SHALL classify isolated modules with confidence levels (high, medium, low) based on likelihood of false positive.

#### Scenario: High confidence for regular modules
- **WHEN** a module has ≥1 symbol and is not a special file type
- **AND** is never imported
- **THEN** the system assigns confidence="high"
- **AND** reason="No imports found"

#### Scenario: Medium confidence for test files
- **WHEN** a module path contains "test"
- **AND** is never imported
- **THEN** the system assigns confidence="medium"
- **AND** reason="Test file (might be entry point)"

#### Scenario: Medium confidence for CLI entry points
- **WHEN** a module path ends with "cli.py", "__main__.py", or "main.py"
- **AND** is never imported
- **THEN** the system assigns confidence="medium"
- **AND** reason="CLI entry point (external invocation)"

#### Scenario: Low confidence for empty package markers
- **WHEN** a module path ends with "__init__.py"
- **AND** has zero symbols
- **THEN** the system assigns confidence="low"
- **AND** reason="Empty package marker"

---

### Requirement: Actionable Recommendations

The system SHALL provide actionable recommendations (remove vs investigate) based on confidence and symbol count.

#### Scenario: Remove recommendation for high-confidence large modules
- **WHEN** confidence="high"
- **AND** symbol_count ≥ 10
- **THEN** the system recommends "remove"

#### Scenario: Investigate recommendation for edge cases
- **WHEN** confidence="medium" OR confidence="low"
- **THEN** the system recommends "investigate"

#### Scenario: Investigate recommendation for small modules
- **WHEN** confidence="high"
- **AND** symbol_count < 10
- **THEN** the system recommends "investigate"

---

### Requirement: Graph Analyzer Integration

The system SHALL extend `aud graph analyze` with `--show-isolated` flag to list isolated nodes from dependency graph.

#### Scenario: List isolated nodes
- **WHEN** user runs `aud graph analyze --show-isolated`
- **THEN** the system computes isolated nodes (nodes with zero edges)
- **AND** displays list of isolated node IDs
- **AND** includes count in statistics

#### Scenario: Empty isolated list
- **WHEN** user runs `aud graph analyze --show-isolated`
- **AND** all nodes have at least one connection
- **THEN** the system displays "(none)" for isolated nodes

#### Scenario: Backwards compatibility
- **WHEN** user runs `aud graph analyze` WITHOUT `--show-isolated` flag
- **THEN** the system ONLY shows count in statistics (not list)
- **AND** maintains backwards compatibility with existing tooling

---

### Requirement: Quality Rule Integration

The system SHALL integrate dead code detection as a quality rule executed during `aud full` pipeline.

#### Scenario: Quality rule discovery
- **WHEN** orchestrator scans rules directory
- **THEN** the system discovers `find_dead_code` function via prefix matching
- **AND** loads METADATA for file targeting

#### Scenario: Database-scope execution
- **WHEN** orchestrator executes quality rule with execution_scope="database"
- **THEN** the system runs rule ONCE per database (not per file)
- **AND** generates findings for all isolated modules in single pass

#### Scenario: Severity classification
- **WHEN** quality rule detects isolated module
- **THEN** the system creates finding with severity="info"
- **AND** category="quality"
- **AND** writes to findings_consolidated table

#### Scenario: No false negatives from exclusions
- **WHEN** quality rule filters exclusions (tests, migrations, __init__.py)
- **THEN** the system ONLY excludes files matching patterns
- **AND** does NOT exclude regular modules accidentally

---

### Requirement: Database-Only Analysis

The system SHALL perform dead code detection using ONLY database queries with NO file reading, NO AST parsing, and NO regex.

#### Scenario: Query symbols table
- **WHEN** system detects dead code
- **THEN** it executes `SELECT DISTINCT path FROM symbols`
- **AND** does NOT read file content
- **AND** does NOT parse AST

#### Scenario: Query refs table
- **WHEN** system detects dead code
- **THEN** it executes `SELECT DISTINCT value FROM refs WHERE kind IN ('import', 'from')`
- **AND** does NOT use regex on file content
- **AND** does NOT grep through source files

#### Scenario: Hard failure on missing table
- **WHEN** database query fails due to missing table
- **THEN** the system raises exception immediately
- **AND** does NOT fall back to regex or file parsing
- **AND** does NOT attempt to recover gracefully

---

### Requirement: Impact Analysis

The system SHALL estimate wasted lines of code (LOC) and development time for dead code modules.

#### Scenario: LOC estimation
- **WHEN** system detects isolated module with N symbols
- **THEN** it estimates LOC as N × 10 lines per symbol
- **AND** includes estimate in report

#### Scenario: Summary statistics
- **WHEN** system completes dead code analysis
- **THEN** it reports total files analyzed
- **AND** reports total dead code files
- **AND** reports estimated wasted LOC (sum of all isolated modules)

#### Scenario: Symbol count per module
- **WHEN** system reports isolated module
- **THEN** it queries `SELECT COUNT(*) FROM symbols WHERE path=?`
- **AND** displays exact symbol count (not estimate)

---

### Requirement: Output Formatting

The system SHALL support multiple output formats (text, json, summary) for different use cases.

#### Scenario: Text format with ASCII table
- **WHEN** user runs `aud deadcode --format text`
- **THEN** the system outputs human-readable ASCII table
- **AND** uses plain text markers ([HIGH], [MED], [LOW]) instead of emojis
- **AND** includes header with "=" separator

#### Scenario: JSON format for automation
- **WHEN** user runs `aud deadcode --format json`
- **THEN** the system outputs valid JSON parseable by `jq`
- **AND** includes summary object with counts
- **AND** includes isolated_modules array with full details

#### Scenario: Summary format for quick checks
- **WHEN** user runs `aud deadcode --format summary`
- **THEN** the system outputs counts only (3 lines)
- **AND** omits detailed module list
- **AND** shows files analyzed, dead code files, estimated LOC

---

### Requirement: Windows Compatibility

The system SHALL produce output compatible with Windows Command Prompt (CP1252 encoding).

#### Scenario: No emoji characters in output
- **WHEN** system formats dead code report
- **THEN** it uses ONLY ASCII characters (bytes 0-127)
- **AND** does NOT use emoji (✅, ❌, 🔴, etc.)
- **AND** uses plain text markers instead ([OK], [HIGH], [MED])

#### Scenario: No encoding errors
- **WHEN** user runs `aud deadcode` on Windows
- **THEN** the output does NOT raise `UnicodeEncodeError`
- **AND** displays correctly in Command Prompt
- **AND** works with CP1252 encoding

---

### Requirement: DRY Architecture

The system SHALL implement dead code detection using separation of concerns with NO code duplication across layers.

#### Scenario: Shared query layer
- **WHEN** CLI command, quality rule, and graph analyzer need database queries
- **THEN** they ALL use `theauditor/queries/dead_code.py`
- **AND** do NOT duplicate SQL query logic
- **AND** do NOT write separate queries for same data

#### Scenario: Analysis layer reuse
- **WHEN** classification logic is needed
- **THEN** it exists ONLY in `theauditor/analysis/isolation.py`
- **AND** is NOT duplicated in CLI or rules
- **AND** provides single source of truth for confidence scoring

#### Scenario: Presentation layer separation
- **WHEN** formatting output for users
- **THEN** logic exists ONLY in `theauditor/commands/deadcode.py`
- **AND** does NOT exist in analysis or data layers
- **AND** maintains clear separation of concerns

---

### Requirement: Error Handling

The system SHALL fail fast with clear error messages when prerequisites are missing.

#### Scenario: Database not found
- **WHEN** user runs `aud deadcode` without running `aud index` first
- **THEN** the system prints "Error: Database not found. Run 'aud index' first."
- **AND** exits with code 2
- **AND** does NOT attempt to create database

#### Scenario: Invalid path filter
- **WHEN** user provides path filter that matches zero files
- **THEN** the system reports zero dead code files
- **AND** does NOT error out
- **AND** shows total_files_analyzed=0 in summary

#### Scenario: Save path parent missing
- **WHEN** user runs `aud deadcode --save /path/to/nonexistent/dir/report.json`
- **THEN** the system creates parent directories automatically
- **AND** writes file successfully
- **AND** prints "Saved to: /path/to/nonexistent/dir/report.json"

---

### Requirement: Performance

The system SHALL complete dead code analysis in <50ms for codebases up to 100,000 lines of code.

#### Scenario: Fast database queries
- **WHEN** system executes `SELECT DISTINCT path FROM symbols`
- **THEN** query completes in <10ms using indexed lookup
- **AND** does NOT perform table scan

#### Scenario: Efficient set operations
- **WHEN** system computes isolated = files_with_code - imported_files
- **THEN** uses Python set difference (O(n) hash operation)
- **AND** completes in <1ms for 1000 files

#### Scenario: No file I/O during analysis
- **WHEN** system detects dead code
- **THEN** it performs ONLY database queries
- **AND** does NOT read any source files
- **AND** does NOT parse any ASTs

---

### Requirement: Documentation

The system SHALL provide comprehensive help text and examples for all CLI options.

#### Scenario: Help text includes algorithm
- **WHEN** user runs `aud deadcode --help`
- **THEN** the help text explains the detection algorithm
- **AND** lists prerequisites (aud index)
- **AND** provides examples for all major options

#### Scenario: Exit codes documented
- **WHEN** user reads help text
- **THEN** it documents exit code 0 (success)
- **AND** documents exit code 1 (dead code found with --fail-on-dead-code)
- **AND** documents exit code 2 (error)

#### Scenario: Output formats documented
- **WHEN** user reads help text
- **THEN** it explains text format (human-readable)
- **AND** explains json format (CI/CD)
- **AND** explains summary format (quick checks)
