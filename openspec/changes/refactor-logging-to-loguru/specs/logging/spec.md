# Logging Capability Specification

**Capability**: `logging`
**Purpose**: Centralized, polyglot logging infrastructure for TheAuditor

---

## ADDED Requirements

### Requirement: Centralized Python Logging Configuration

The system SHALL provide a centralized logging configuration using Loguru that replaces all scattered print statements with structured logger calls.

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

### Requirement: Python Structured Log Format

The system SHALL output Python logs in a consistent, human-readable format with timestamps, log levels, and source location.

#### Scenario: Console log format
- **WHEN** a log message is emitted to stderr
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

The system SHALL convert existing print statement tags to appropriate log levels via automated codemod.

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

### Requirement: TypeScript Logger

The system SHALL provide a lightweight custom logger for the TypeScript extractor that respects the same environment variables as Python.

#### Scenario: Environment variable consistency
- **WHEN** the TypeScript extractor runs
- **THEN** it respects THEAUDITOR_LOG_LEVEL environment variable
- **AND** it respects THEAUDITOR_LOG_JSON environment variable
- **AND** log level values match Python (DEBUG, INFO, WARNING, ERROR)

#### Scenario: Stderr output
- **WHEN** a TypeScript log message is emitted
- **THEN** it is written to stderr (not stdout)
- **AND** stdout remains reserved for JSON data output
- **AND** no corruption of stdout JSON occurs

### Requirement: TypeScript Tag-to-Level Migration

The system SHALL convert existing console.error statements with tags to appropriate logger calls.

#### Scenario: TypeScript debug tag conversion
- **WHEN** a console.error statement contains DEBUG JS BATCH or DEBUG JS tag
- **THEN** it is converted to logger.debug() call
- **AND** the tag is removed from the message

#### Scenario: TypeScript error statements
- **WHEN** a console.error statement has no debug tag
- **THEN** it is converted to logger.error() call

### Requirement: JSON Structured Output

The system SHALL support JSON structured output for log aggregation systems (ELK, Splunk, DataDog).

#### Scenario: Python JSON output
- **WHEN** THEAUDITOR_LOG_JSON=1 is set
- **AND** a Python log message is emitted
- **THEN** the output is valid JSON
- **AND** the format includes time, level, message, module, function, line

#### Scenario: TypeScript JSON output
- **WHEN** THEAUDITOR_LOG_JSON=1 is set
- **AND** a TypeScript log message is emitted
- **THEN** the output is valid JSON
- **AND** the format includes time, level, message

#### Scenario: JSON parsing validation
- **WHEN** JSON output mode is enabled
- **THEN** all log lines are parseable by json.loads()
- **AND** no plain text is mixed with JSON

### Requirement: Rich UI Preservation

The system SHALL preserve the existing Rich-based pipeline UI without modification.

#### Scenario: Pipeline progress display
- **WHEN** aud full command runs
- **THEN** the Rich live table displays phase progress
- **AND** the visual appearance is unchanged from before migration
- **AND** RichRenderer remains the sole authority for pipeline UI

#### Scenario: Logging and UI separation
- **WHEN** internal logging occurs during pipeline execution
- **THEN** Loguru output goes to stderr
- **AND** Rich pipeline UI continues to stdout
- **AND** the two outputs do not interfere

### Requirement: Automated Migration via LibCST

The system SHALL provide a LibCST codemod for automated migration of Python print statements.

#### Scenario: Codemod dry run
- **WHEN** the codemod is run with --no-format flag
- **THEN** a diff is displayed showing proposed changes
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
