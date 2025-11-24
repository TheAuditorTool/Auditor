# cli Specification

## Purpose
CLI help system for TheAuditor, providing AI-optimized command routing and documentation.

## Requirements

### Requirement: AI Routing Annotations in Root Help
The `aud --help` command SHALL include discriminative routing annotations for AI agents.

#### Scenario: Primary commands have USE WHEN annotations
- **WHEN** user runs `aud --help`
- **THEN** output includes `> USE WHEN:` annotation for commands: explain, query, structure
- **AND** annotations describe when AI should select each command

#### Scenario: Primary commands have GIVES annotations
- **WHEN** user runs `aud --help`
- **THEN** output includes `> GIVES:` annotation for commands: explain, query, structure
- **AND** annotations describe what output each command provides

#### Scenario: Maintenance commands have RUN annotations
- **WHEN** user runs `aud --help`
- **THEN** output includes `> RUN:` annotation for commands: full, setup-ai, graph
- **AND** annotations describe when to run each command

#### Scenario: Annotations use ASCII only
- **WHEN** user runs `aud --help` on Windows
- **THEN** output renders without UnicodeEncodeError
- **AND** all annotation text is ASCII-only (no emojis or Unicode characters)

### Requirement: Anti-Patterns Sections in Subcommand Help
Subcommands that accept user queries SHALL include ANTI-PATTERNS section to prevent common AI mistakes.

#### Scenario: explain command has anti-patterns
- **WHEN** user runs `aud explain --help`
- **THEN** output includes `ANTI-PATTERNS (Do NOT Do This)` section
- **AND** section lists common mistakes with redirect suggestions

#### Scenario: query command has anti-patterns
- **WHEN** user runs `aud query --help`
- **THEN** output includes `ANTI-PATTERNS (Do NOT Do This)` section
- **AND** section lists at least 3 common mistakes
- **AND** each mistake includes `-> Use ...` redirect suggestion

#### Scenario: structure command has anti-patterns
- **WHEN** user runs `aud structure --help`
- **THEN** output includes `ANTI-PATTERNS (Do NOT Do This)` section

#### Scenario: taint-analyze command has anti-patterns
- **WHEN** user runs `aud taint-analyze --help`
- **THEN** output includes `ANTI-PATTERNS (Do NOT Do This)` section

### Requirement: Copy These Patterns Examples Format
Subcommand help examples SHALL use standardized format for AI few-shot learning.

#### Scenario: explain command examples format
- **WHEN** user runs `aud explain --help`
- **THEN** output includes `EXAMPLES (Copy These Patterns)` section
- **AND** each example has comment describing use case
- **AND** each example shows complete command

#### Scenario: query command examples format
- **WHEN** user runs `aud query --help`
- **THEN** output includes `EXAMPLES (Copy These Patterns)` section
- **AND** section contains 5-6 examples maximum
- **AND** each example has comment describing use case

### Requirement: Output Format Documentation
Subcommands that produce structured output SHALL include OUTPUT FORMAT section.

#### Scenario: explain command output format
- **WHEN** user runs `aud explain --help`
- **THEN** output includes `OUTPUT FORMAT` section
- **AND** section shows example text mode output
- **AND** section shows example JSON mode output

#### Scenario: query command output format
- **WHEN** user runs `aud query --help`
- **THEN** output includes `OUTPUT FORMAT` section
- **AND** section shows example text mode output
- **AND** section shows example JSON mode output

### Requirement: Concise Main Help Output
The `aud --help` command SHALL produce output of less than 150 lines (with AI annotations).

#### Scenario: Main help is scannable
- **WHEN** user runs `aud --help`
- **THEN** output contains:
  - One-liner description
  - Quick start (3 example commands)
  - Categorized command list (name + short description only)
  - AI routing annotations (USE WHEN, GIVES, RUN)
  - Footer with "aud <command> --help" and "aud manual --list" pointers
- **AND** output does NOT contain:
  - Inline option lists for commands
  - PURPOSE, WORKFLOWS, OUTPUT STRUCTURE blocks
  - ENVIRONMENT VARIABLES section
  - Uncategorized command warnings

#### Scenario: Root help line count
- **WHEN** user runs `aud --help`
- **THEN** output line count is less than 150 lines (includes AI routing annotations)

### Requirement: Hidden Commands Not Displayed
Commands with `hidden=True` SHALL NOT appear in `aud --help` output.

#### Scenario: Deprecated commands hidden
- **WHEN** user runs `aud --help`
- **THEN** output does NOT list `index`, `init`, or `setup-claude`
- **AND** output does NOT show "WARNING: uncategorized" section for hidden commands

### Requirement: Deprecated Commands Show Warnings
Deprecated commands SHALL print a warning when executed.

#### Scenario: init-config deprecation warning
- **WHEN** user runs `aud init-config`
- **THEN** output includes deprecation warning
- **AND** command executes normally (for backward compatibility)

#### Scenario: init-js deprecation warning
- **WHEN** user runs `aud init-js`
- **THEN** output includes deprecation warning
- **AND** command executes normally (for backward compatibility)

#### Scenario: tool-versions deprecation warning
- **WHEN** user runs `aud tool-versions`
- **THEN** output includes deprecation warning pointing to `aud setup-ai --show-versions`
- **AND** command executes normally (for backward compatibility)

### Requirement: Dev Flags Hidden from Help
Internal/development flags SHALL be hidden from command help but still functional.

#### Scenario: exclude-self flag hidden but works
- **WHEN** user runs `aud full --help`
- **THEN** output does NOT show `--exclude-self` option
- **AND** `aud full --exclude-self` still works correctly

### Requirement: Manual Contains Moved Content
The `aud manual` command SHALL include concepts for content moved from main help and subcommand help.

#### Scenario: Overview concept available
- **WHEN** user runs `aud manual overview`
- **THEN** output shows PURPOSE and OUTPUT STRUCTURE information

#### Scenario: Workflows concept available
- **WHEN** user runs `aud manual workflows`
- **THEN** output shows COMMON WORKFLOWS examples

#### Scenario: Environment variables concept available
- **WHEN** user runs `aud manual env-vars`
- **THEN** output shows ENVIRONMENT VARIABLES documentation

#### Scenario: Database concept available
- **WHEN** user runs `aud manual database`
- **THEN** output shows DATABASE SCHEMA REFERENCE
- **AND** output shows table descriptions
- **AND** output shows manual SQL query examples

#### Scenario: Troubleshooting concept available
- **WHEN** user runs `aud manual troubleshooting`
- **THEN** output shows common errors and solutions
- **AND** output shows symptoms and causes

#### Scenario: Architecture concept available
- **WHEN** user runs `aud manual architecture`
- **THEN** output shows CLI architecture explanation
- **AND** output shows two-database design rationale

### Requirement: setup-ai Shows Tool Versions
The `aud setup-ai` command SHALL support `--show-versions` flag.

#### Scenario: Show versions flag
- **WHEN** user runs `aud setup-ai --show-versions`
- **THEN** output shows installed tool versions (same as old `aud tool-versions`)
- **AND** does NOT run full setup unless `--target` also provided

### Requirement: Query Help Brevity
The `aud query --help` command SHALL be concise for AI context window efficiency.

#### Scenario: Query help line count
- **WHEN** user runs `aud query --help`
- **THEN** output line count is less than 200 lines

#### Scenario: Query help content hierarchy
- **WHEN** user runs `aud query --help`
- **THEN** output contains (in order):
  1. One-line description
  2. Arguments/options listing
  3. Anti-patterns section
  4. Examples section (5-6 examples max)
  5. Output format section
- **AND** output does NOT contain:
  - Database schema reference (moved to manual)
  - Troubleshooting section (moved to manual)
  - Architecture explanation (moved to manual)
  - Performance characteristics (moved to manual)
  - Manual SQL query examples (moved to manual)

### Requirement: ASCII-Only CLI Output
All CLI help output SHALL be ASCII-only for Windows CP1252 compatibility.

#### Scenario: No Unicode in docstrings
- **WHEN** tests run `pytest tests/test_cli_ascii.py`
- **THEN** all docstrings in CLI files pass ASCII encoding test
- **AND** COMMAND_METADATA values pass ASCII encoding test

#### Scenario: Help output on Windows
- **WHEN** user runs any `aud` command on Windows Command Prompt
- **THEN** no UnicodeEncodeError occurs
- **AND** all output characters are within CP1252 range
