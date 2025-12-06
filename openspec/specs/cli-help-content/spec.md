# cli-help-content Specification

## Purpose
TBD - created by archiving change optimize-cli-help-v2. Update Purpose after archive.
## Requirements
### Requirement: AI-Optimized Help Content

All CLI command help text SHALL be written primarily for AI assistant consumption, with secondary consideration for human readability.

#### Scenario: AI assistant parses help for command usage

- **WHEN** an AI assistant runs `aud <command> --help`
- **THEN** output contains AI ASSISTANT CONTEXT section with structured metadata
- **AND** metadata includes: Purpose, Input, Output, Prerequisites, Integration
- **AND** all examples are copy-paste executable
- **AND** all described options actually exist and work

#### Scenario: No deprecated command references

- **WHEN** any help text references prerequisite commands
- **THEN** the reference uses current commands only ("aud full" not "aud index")
- **AND** no deprecated command names appear except in explicit deprecation notices

---

### Requirement: Verified Command Examples

All examples in help text SHALL be verified to work with current tool behavior.

#### Scenario: Example execution succeeds

- **WHEN** an AI assistant copies an example from `--help` output
- **AND** executes it in a properly indexed repository
- **THEN** the command succeeds without error
- **AND** produces the output type described

#### Scenario: Example prerequisites stated

- **WHEN** an example requires prior commands to be run
- **THEN** the example explicitly states prerequisites
- **AND** prerequisites use current command names

---

### Requirement: Workflow Context in Help

All command help SHALL include guidance on WHEN and WHY to use the command, not just WHAT it does.

#### Scenario: Help includes workflow positioning

- **WHEN** an AI assistant reads command help
- **THEN** help includes COMMON WORKFLOWS section showing usage patterns
- **AND** help includes RELATED COMMANDS section with brief descriptions
- **AND** help references relevant `aud manual` topics in SEE ALSO section

#### Scenario: AI understands command sequencing

- **WHEN** an AI assistant needs to perform a multi-step analysis
- **THEN** each command's help explains what comes before and after
- **AND** prerequisite commands are accurately stated

---

### Requirement: Complete AI ASSISTANT CONTEXT Coverage

Every CLI command SHALL have an AI ASSISTANT CONTEXT section in its docstring.

#### Scenario: Context section format

- **WHEN** AI ASSISTANT CONTEXT section is present
- **THEN** format follows this exact structure:
  ```
  AI ASSISTANT CONTEXT:
    Purpose: <single line describing what this command accomplishes>
    Input: <files/databases consumed, with paths like .pf/repo_index.db>
    Output: <files/data produced, with paths like .pf/raw/analysis.json>
    Prerequisites: <commands that must run first, always "aud full" not "aud index">
    Integration: <how this fits in typical workflow, 1-2 sentences>
  ```
- **AND** each field is on its own line, indented 2 spaces from the section header
- **AND** field names use Title Case followed by colon and space
- **AND** Prerequisites always uses "aud full" (never "aud index")

#### Scenario: All commands covered

- **WHEN** counting commands with AI ASSISTANT CONTEXT
- **THEN** count equals total command file count minus excluded files
- **AND** excluded files are: `__init__.py`, `config.py`, `manual_lib01.py`, `manual_lib02.py`
- **AND** total requiring AI ASSISTANT CONTEXT is 34 files (38 total - 4 excluded)

---

### Requirement: Cross-Reference Accuracy

All cross-references between commands and manual topics SHALL be verified accurate.

#### Scenario: Manual references valid

- **WHEN** help text says "See: aud manual <topic>"
- **THEN** that topic exists in `aud manual --list`
- **AND** running `aud manual <topic>` succeeds

#### Scenario: Command references valid

- **WHEN** help text references another command
- **THEN** that command exists and is callable
- **AND** the description of that command is accurate

---

### Requirement: RichCommand Section Compliance

All docstrings SHALL use section headers recognized by RichCommand parser.

#### Scenario: Valid section headers used

- **WHEN** a docstring contains section headers
- **THEN** headers are from the recognized list:
  - AI ASSISTANT CONTEXT
  - DESCRIPTION
  - EXAMPLES
  - COMMON WORKFLOWS
  - OUTPUT FILES
  - PERFORMANCE
  - EXIT CODES
  - RELATED COMMANDS
  - SEE ALSO
  - TROUBLESHOOTING
  - NOTE
  - WHAT IT DETECTS
  - DATA FLOW ANALYSIS METHOD
- **AND** headers are ALL CAPS, optionally followed by colon
- **AND** content follows immediately after header line

#### Scenario: RichCommand parses sections correctly

- **WHEN** running `aud <command> --help`
- **THEN** RichCommand (theauditor/cli.py:141-350) parses and renders sections
- **AND** AI ASSISTANT CONTEXT appears in a cyan-bordered panel
- **AND** EXAMPLES use green syntax highlighting for commands

---

