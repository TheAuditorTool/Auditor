# manual-content Specification

## Purpose
TBD - created by archiving change optimize-manual-content-v2. Update Purpose after archive.
## Requirements
### Requirement: Workflow-Centric Manual Entries

All manual entries SHALL be written as step-by-step workflow guides, not just concept explanations.

#### Scenario: AI assistant learns how to perform analysis

- **WHEN** an AI assistant runs `aud manual <topic>`
- **THEN** output includes "HOW TO USE IT" section with numbered steps
- **AND** steps include actual command sequences
- **AND** each step explains expected outcome
- **AND** examples are copy-paste executable

#### Scenario: Prerequisites clearly stated

- **WHEN** a workflow requires prior commands
- **THEN** PREREQUISITES section lists required commands
- **AND** `aud full` is always mentioned as database creation step
- **AND** no deprecated commands are referenced

---

### Requirement: Database-First Philosophy Emphasized

All manual entries SHALL emphasize the database-first analysis approach.

#### Scenario: Entry references database

- **WHEN** a topic involves analysis commands
- **THEN** entry explains that analysis reads from `.pf/repo_index.db`
- **AND** entry states `aud full` must run first
- **AND** entry explains what database tables are relevant

#### Scenario: No analysis without indexing

- **WHEN** entry shows analysis commands
- **THEN** prerequisites always include database creation
- **AND** troubleshooting includes "database not found" error

---

### Requirement: Agent System Integration

All relevant manual entries SHALL reference the agent system for runtime workflows.

#### Scenario: Security topics reference security agent

- **WHEN** topic relates to security analysis (taint, patterns, boundaries)
- **THEN** entry references `.auditor_venv/.theauditor_tools/agents/security.md`
- **AND** explains how agent workflows use this capability

#### Scenario: Refactor topics reference refactor agent

- **WHEN** topic relates to refactoring (refactor, deadcode)
- **THEN** entry references `.auditor_venv/.theauditor_tools/agents/refactor.md`
- **AND** explains agent-driven refactoring workflow

---

### Requirement: Command Combination Guidance

All manual entries SHALL explain how to combine commands for complete workflows.

#### Scenario: Entry shows command combinations

- **WHEN** a topic's analysis is enhanced by other commands
- **THEN** entry includes "COMBINING WITH OTHER TOOLS" section
- **AND** section explains complementary commands
- **AND** shows example command sequences

#### Scenario: Cross-references are bidirectional

- **WHEN** topic A references topic B
- **THEN** topic B also references topic A
- **AND** both explain the relationship

---

### Requirement: Consistent Entry Structure

All manual entries SHALL follow a consistent structure.

#### Scenario: Entry structure validation

- **WHEN** any manual entry is displayed
- **THEN** it includes sections in order: WHAT IT IS, WHEN TO USE IT, HOW TO USE IT, RELATED
- **AND** HOW TO USE IT includes PREREQUISITES, STEPS, EXAMPLE
- **AND** RELATED includes Commands and Topics subsections

#### Scenario: No orphan entries

- **WHEN** counting manual entries
- **THEN** every command with --help has corresponding manual topic
- **AND** every manual topic references at least one command

---

### Requirement: Verified Working Examples

All examples in manual entries SHALL be verified to work.

#### Scenario: Example execution succeeds

- **WHEN** an AI assistant copies an example from manual entry
- **AND** executes it in a properly indexed repository
- **THEN** the command succeeds without error
- **AND** produces output matching description

#### Scenario: Examples show expected output

- **WHEN** example includes command execution
- **THEN** entry shows or describes expected output
- **AND** explains how to interpret output

---

### Requirement: Common Mistakes Documentation

All manual entries SHALL document common pitfalls and their solutions.

#### Scenario: Entry includes error prevention

- **WHEN** a topic has known failure modes
- **THEN** entry includes "COMMON MISTAKES" section
- **AND** lists 2-3 most common errors
- **AND** provides solution for each

#### Scenario: Deprecated command warnings

- **WHEN** a deprecated command exists for this capability
- **THEN** entry mentions the deprecated form
- **AND** directs to correct command
- **AND** example: "aud index is deprecated, use aud full"

---

