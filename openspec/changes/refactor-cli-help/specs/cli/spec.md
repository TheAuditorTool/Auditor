## ADDED Requirements

### Requirement: Concise Main Help Output
The `aud --help` command SHALL produce output of less than 80 lines.

#### Scenario: Main help is scannable
- **WHEN** user runs `aud --help`
- **THEN** output contains:
  - One-liner description
  - Quick start (3 example commands)
  - Categorized command list (name + short description only)
  - Footer with "aud <command> --help" and "aud manual --list" pointers
- **AND** output does NOT contain:
  - Inline option lists for commands
  - PURPOSE, WORKFLOWS, OUTPUT STRUCTURE blocks
  - ENVIRONMENT VARIABLES section
  - Uncategorized command warnings

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
The `aud manual` command SHALL include concepts for content moved from main help.

#### Scenario: Overview concept available
- **WHEN** user runs `aud manual overview`
- **THEN** output shows PURPOSE and OUTPUT STRUCTURE information

#### Scenario: Workflows concept available
- **WHEN** user runs `aud manual workflows`
- **THEN** output shows COMMON WORKFLOWS examples

#### Scenario: Environment variables concept available
- **WHEN** user runs `aud manual env-vars`
- **THEN** output shows ENVIRONMENT VARIABLES documentation

### Requirement: setup-ai Shows Tool Versions
The `aud setup-ai` command SHALL support `--show-versions` flag.

#### Scenario: Show versions flag
- **WHEN** user runs `aud setup-ai --show-versions`
- **THEN** output shows installed tool versions (same as old `aud tool-versions`)
- **AND** does NOT run full setup unless `--target` also provided
