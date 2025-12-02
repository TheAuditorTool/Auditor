# Logging Capability Specification

**Capability**: `logging`
**Purpose**: Centralized, polyglot logging infrastructure for TheAuditor using Loguru (Python) and Pino (TypeScript)

---

## ADDED Requirements

### Requirement: Centralized Python Logging Configuration (Loguru 0.7.3)

The system SHALL provide a centralized logging configuration using Loguru 0.7.3 that replaces all scattered print statements with structured logger calls outputting Pino-compatible NDJSON.

#### Scenario: Default logging level
- **WHEN** no environment variable is set
- **THEN** the logging level defaults to INFO
- **AND** debug messages are suppressed
- **AND** info, warning, and error messages are displayed

#### Scenario: Custom logging level via environment
- **WHEN** THEAUDITOR_LOG_LEVEL environment variable is set to DEBUG
- **THEN** all log levels including debug are displayed
- **AND** trace messages are suppressed unless level is TRACE

#### Scenario: Error-only logging
- **WHEN** THEAUDITOR_LOG_LEVEL is set to ERROR
- **THEN** only error and critical messages are displayed
- **AND** info, debug, and warning messages are suppressed

### Requirement: Unified NDJSON Format (Pino-Compatible)

The system SHALL output logs in Pino-compatible NDJSON format from both Python (Loguru) and TypeScript (Pino) components.

#### Scenario: Python NDJSON output
- **WHEN** THEAUDITOR_LOG_JSON=1 is set
- **AND** a Python log message is emitted
- **THEN** the output is valid JSON on a single line
- **AND** the format includes `level` as integer (10=trace, 20=debug, 30=info, 40=warn, 50=error)
- **AND** the format includes `time` as Unix epoch milliseconds
- **AND** the format includes `msg` (not `message`) as the log text
- **AND** the format includes `pid` as process ID
- **AND** the format includes `request_id` for correlation

#### Scenario: TypeScript NDJSON output
- **WHEN** a TypeScript log message is emitted via Pino
- **THEN** the output is valid JSON on a single line (NDJSON)
- **AND** the format includes `level` as integer
- **AND** the format includes `time` as Unix epoch milliseconds
- **AND** the format includes `msg` as the log text
- **AND** the format includes `request_id` from environment variable

#### Scenario: Format compatibility verification
- **WHEN** logs from Python and TypeScript are combined
- **THEN** both can be parsed by the same JSON parser
- **AND** both can be viewed with pino-pretty
- **AND** the format fields are identical between languages

### Requirement: Python Human-Readable Format

The system SHALL output Python logs in a consistent, human-readable format when JSON mode is disabled.

#### Scenario: Console log format (non-JSON mode)
- **WHEN** THEAUDITOR_LOG_JSON is not set or is 0
- **AND** a log message is emitted to stderr
- **THEN** the format includes timestamp (HH:MM:SS)
- **AND** the format includes log level (padded to 8 chars)
- **AND** the format includes module name and function
- **AND** colors are applied based on log level
- **AND** no emojis are used (Windows CP1252 compatibility)

#### Scenario: File log format
- **WHEN** file logging is enabled via THEAUDITOR_LOG_FILE
- **THEN** the format includes full timestamp (YYYY-MM-DD HH:MM:SS)
- **AND** the format includes log level
- **AND** the format includes module, function, and line number
- **AND** no ANSI color codes are included

### Requirement: Python Log Rotation

The system SHALL support automatic log rotation when file logging is enabled.

#### Scenario: Size-based rotation
- **WHEN** file logging is enabled
- **AND** the log file exceeds 10 MB
- **THEN** the log file is rotated
- **AND** a new log file is created

#### Scenario: Retention policy
- **WHEN** log files are rotated
- **THEN** log files older than 7 days are automatically deleted
- **AND** the most recent rotated files are preserved

### Requirement: Python Tag-to-Level Migration

The system SHALL convert existing print statement tags to appropriate log levels via automated codemod using LibCST 1.8.6.

#### Scenario: Debug tag conversion
- **WHEN** a print statement contains [DEBUG], [TRACE], or [INDEXER_DEBUG] tag
- **THEN** it is converted to logger.debug() call
- **AND** the tag is removed from the message

#### Scenario: Info tag conversion
- **WHEN** a print statement contains [INFO], [Indexer], [TAINT], or [SCHEMA] tag
- **THEN** it is converted to logger.info() call
- **AND** the tag is removed from the message

#### Scenario: Error tag conversion
- **WHEN** a print statement contains [ERROR] tag
- **THEN** it is converted to logger.error() call
- **AND** the tag is removed from the message

#### Scenario: Debug guard elimination
- **WHEN** code contains if os.environ.get THEAUDITOR_DEBUG print
- **THEN** the if guard is removed
- **AND** the print is converted to logger.debug()
- **AND** the conditional wrapper is eliminated

### Requirement: TypeScript Logger (Pino 10.1.0)

The system SHALL provide a Pino-based logger for the TypeScript extractor that outputs NDJSON to stderr and respects the same environment variables as Python.

#### Scenario: Environment variable consistency
- **WHEN** the TypeScript extractor runs
- **THEN** it respects THEAUDITOR_LOG_LEVEL environment variable
- **AND** log level values match Python (DEBUG, INFO, WARNING, ERROR)
- **AND** output is always NDJSON (Pino native format)

#### Scenario: Stderr output preservation
- **WHEN** a TypeScript log message is emitted
- **THEN** it is written to stderr (file descriptor 2)
- **AND** stdout remains reserved for JSON data output
- **AND** no corruption of stdout JSON occurs

#### Scenario: Pino child logger with request_id
- **WHEN** the TypeScript logger is initialized
- **THEN** it creates a child logger with request_id bound
- **AND** the request_id comes from THEAUDITOR_REQUEST_ID environment variable
- **AND** all log messages include the request_id field

### Requirement: TypeScript Tag-to-Level Migration

The system SHALL convert existing console.error statements with tags to appropriate Pino logger calls.

#### Scenario: TypeScript debug tag conversion
- **WHEN** a console.error statement contains DEBUG JS BATCH or DEBUG JS tag
- **THEN** it is converted to logger.debug() call
- **AND** the tag is removed from the message

#### Scenario: TypeScript error statements
- **WHEN** a console.error statement has no debug tag
- **THEN** it is converted to logger.error() call

### Requirement: Cross-Language Correlation (REQUEST_ID)

The system SHALL support log correlation across Python and TypeScript via THEAUDITOR_REQUEST_ID environment variable.

#### Scenario: REQUEST_ID generation in Python
- **WHEN** Python orchestrator starts
- **AND** THEAUDITOR_REQUEST_ID is not set
- **THEN** a new UUID is generated as request_id
- **AND** the request_id is bound to all Python log messages

#### Scenario: REQUEST_ID threading to subprocess
- **WHEN** Python orchestrator spawns TypeScript extractor
- **THEN** THEAUDITOR_REQUEST_ID is passed as environment variable
- **AND** the TypeScript extractor binds this request_id to all logs

#### Scenario: Unified log correlation
- **WHEN** logs from Python and TypeScript are viewed together
- **THEN** messages from the same pipeline run share the same request_id
- **AND** logs can be filtered by request_id to see full pipeline trace

### Requirement: Developer Experience (pino-pretty)

The system SHALL support human-readable log viewing during development via pino-pretty.

#### Scenario: pino-pretty for Python logs
- **WHEN** THEAUDITOR_LOG_JSON=1 is set
- **AND** Python logs are piped to npx pino-pretty
- **THEN** logs are displayed in colorful, human-readable format
- **AND** timestamps, levels, and messages are clearly formatted

#### Scenario: pino-pretty for TypeScript logs
- **WHEN** TypeScript extractor logs are piped to npx pino-pretty
- **THEN** logs are displayed in colorful, human-readable format
- **AND** format matches Python pino-pretty output

#### Scenario: Unified log viewing
- **WHEN** logs from both Python and TypeScript are combined
- **AND** piped to npx pino-pretty
- **THEN** all logs are displayed in unified, readable format
- **AND** request_id enables visual correlation

### Requirement: Rich UI Preservation

The system SHALL preserve the existing Rich-based pipeline UI without modification.

#### Scenario: Pipeline progress display
- **WHEN** aud full command runs
- **THEN** the Rich live table displays phase progress
- **AND** the visual appearance is unchanged from before migration
- **AND** RichRenderer remains the sole authority for pipeline UI

#### Scenario: Logging and UI separation
- **WHEN** internal logging occurs during pipeline execution
- **THEN** Loguru/Pino output goes to stderr
- **AND** Rich pipeline UI continues to stdout
- **AND** the two outputs do not interfere

### Requirement: Automated Migration via LibCST 1.8.6

The system SHALL provide a LibCST 1.8.6 codemod for automated migration of Python print statements.

#### Scenario: Codemod dry run
- **WHEN** the codemod is run with --dry-run flag
- **THEN** a summary is displayed showing proposed changes
- **AND** no files are modified
- **AND** the transformation can be reviewed before applying

#### Scenario: Codemod execution
- **WHEN** the codemod is applied
- **THEN** all tagged print statements are converted to logger calls
- **AND** the loguru import is added to modified files
- **AND** formatting is preserved (comments, whitespace)

#### Scenario: Import management
- **WHEN** print statements are converted to logger calls
- **THEN** from theauditor.utils.logging import logger is added
- **AND** unused sys imports are candidates for removal
- **AND** no duplicate imports are created

### Requirement: Exact Dependency Versions

The system SHALL use exact dependency versions to ensure reproducibility.

#### Scenario: Python dependencies
- **WHEN** the logging system is installed
- **THEN** loguru version is exactly 0.7.3
- **AND** libcst version is exactly 1.8.6 (dev dependency)

#### Scenario: TypeScript dependencies
- **WHEN** the TypeScript extractor is built
- **THEN** pino version is exactly 10.1.0
- **AND** pino-pretty version is exactly 13.0.0 (dev dependency)

### Requirement: ZERO FALLBACK Compliance

The system SHALL comply with the ZERO FALLBACK policy from CLAUDE.md.

#### Scenario: No fallback logging paths
- **WHEN** the logging system is configured
- **THEN** there is exactly one logging path per language
- **AND** Python uses only Loguru (no fallback to print)
- **AND** TypeScript uses only Pino (no fallback to console)

#### Scenario: Hard fail on configuration errors
- **WHEN** an invalid log level is specified
- **THEN** the system fails immediately with clear error
- **AND** no silent fallback to default level occurs

#### Scenario: Hard fail on missing REQUEST_ID threading
- **WHEN** subprocess is spawned without REQUEST_ID
- **THEN** the system generates a new UUID (not silent failure)
- **AND** logs indicate the new correlation chain
