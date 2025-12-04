# rich-cli-help Specification

## Purpose

Modernize all CLI help output to use Rich formatting, matching the quality of the main `aud --help` dashboard. Update content to reflect current architecture and fix grammar/style inconsistencies.

## Current State (Broken)

**Main help (`aud --help`):** Beautiful Rich panels with categorized commands
**Subcommand help (`aud <cmd> --help`):** Plain Click text with bad line wrapping
**Manual entries (`aud manual <topic>`):** ASCII boxes, no Rich markup

---

## ADDED Requirements

### Requirement: RichCommand Class for Subcommand Help

The system SHALL provide a `RichCommand` Click class that renders subcommand help with Rich formatting.

Features:
- Parses docstring into sections (AI CONTEXT, EXAMPLES, etc.)
- Renders sections with appropriate Rich components (Panel, Table, Syntax)
- Formats options in clean table layout
- Detects terminal width and TTY status

#### Scenario: Subcommand help displays with Rich formatting

- **WHEN** user runs `aud taint-analyze --help`
- **THEN** output displays with Rich panels and colored sections
- **AND** examples are syntax highlighted in green
- **AND** options are displayed in a clean table format
- **AND** output respects terminal width

#### Scenario: Non-TTY output falls back gracefully

- **WHEN** user pipes help to another command (`aud taint-analyze --help | cat`)
- **THEN** output displays without ANSI color codes
- **AND** content remains readable and structured

---

### Requirement: Canonical Docstring Format

All command docstrings SHALL follow a standardized format with these sections:

1. One-line summary (first line)
2. AI ASSISTANT CONTEXT (for AI tools)
3. EXAMPLES (usage examples)
4. EXIT CODES (meaningful codes)
5. RELATED COMMANDS (cross-references)

#### Scenario: AI assistant extracts context from help

- **WHEN** an AI assistant parses `aud taint-analyze --help` output
- **THEN** AI ASSISTANT CONTEXT section provides structured metadata
- **AND** metadata includes: Purpose, Input, Output, Prerequisites

---

### Requirement: Rich Manual Entries

Manual entries (`aud manual <topic>`) SHALL render with Rich formatting:

- Section headers in bold cyan
- Code examples with syntax highlighting
- Bullet lists properly indented
- Concept terms highlighted

#### Scenario: Manual entry displays with Rich formatting

- **WHEN** user runs `aud manual taint`
- **THEN** output displays with Rich panels for each section
- **AND** code examples have syntax highlighting
- **AND** key terms (Source, Sink, Taint) are highlighted

---

### Requirement: Update Outdated Command Descriptions

All command docstrings SHALL accurately describe current tool behavior.

Updates required:
- Replace "aud index" references with "aud full"
- Update pipeline stage counts (now 20+ phases, 4 stages)
- Add polyglot language support mentions (Go, Rust, Bash)
- Fix database paths (.pf/repo_index.db)

#### Scenario: No outdated command references

- **WHEN** user reads any command help
- **THEN** all referenced commands exist and work as described
- **AND** no deprecated commands are recommended
- **AND** file paths match actual output locations

---

### Requirement: Grammar and Style Consistency

All command help text SHALL follow consistent grammar and style:

- Sentence case for headings
- Active voice ("Detects" not "Detection of")
- No trailing periods in option descriptions
- Consistent terminology (finding, not issue/vulnerability/problem)
- TheAuditor capitalization (not theauditor)

#### Scenario: Consistent terminology across commands

- **WHEN** user reads help from multiple commands
- **THEN** same concepts use same terminology
- **AND** style is consistent across all 36 commands

---

## Files Affected

**New Code:**
- `theauditor/cli.py` - Add RichCommand class

**Modified Commands (36 files):**
- `theauditor/commands/*.py` - All command docstrings

**Modified Content:**
- `theauditor/commands/manual.py` - 16 explanation entries
