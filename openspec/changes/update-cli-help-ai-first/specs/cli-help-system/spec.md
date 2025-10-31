# Capability: CLI Help System

**Capability ID**: cli-help-system
**Status**: Added
**Version**: 1.0.0
**Owner**: Opus AI (Lead Coder)

---

## Overview

The CLI Help System provides AI-first, machine-optimized help documentation for all TheAuditor commands. It dynamically generates command categorization, validates documentation completeness, and ensures consistent quality across all CLI commands.

---

## ADDED Requirements

### Requirement 1: Dynamic VerboseGroup Generation

**ID**: CLI-001
**Priority**: CRITICAL
**Type**: Enhancement

The CLI must dynamically generate help text from registered commands instead of using hardcoded strings, ensuring all commands are visible and categorized.

**Acceptance Criteria**:
- VerboseGroup queries `cli.commands` dict at runtime
- Command help text extracted dynamically from command docstrings
- Categories defined in COMMAND_CATEGORIES dictionary
- Warning displayed if any commands are uncategorized
- Internal commands (prefix `_`) automatically excluded from help output

#### Scenario: New command added and automatically appears in help

**Given**: A new command is registered via `cli.add_command(new_command)`

**And**: The command is added to COMMAND_CATEGORIES under appropriate category

**When**: User runs `aud --help`

**Then**: The new command appears in the help output under its category

**And**: No "ungrouped commands" warning is displayed

**Example**:
```python
# New command in theauditor/commands/new_feature.py
@click.command()
def new_feature():
    """Performs new feature analysis."""
    pass

# Registration in cli.py
cli.add_command(new_feature)

# Categorization in VerboseGroup.COMMAND_CATEGORIES
'SECURITY_SCANNING': {
    'commands': [..., 'new-feature'],  # Added here
}

# Result: aud --help now shows new-feature automatically
```

---

#### Scenario: Ungrouped command triggers warning

**Given**: A command is registered via `cli.add_command(orphan_command)`

**And**: The command is NOT added to any COMMAND_CATEGORIES category

**When**: User runs `aud --help`

**Then**: Help output contains warning section

**And**: Warning lists "orphan-command" as uncategorized

**Example Output**:
```
================================================================================
WARNING: The following commands are not categorized:
================================================================================
  - orphan-command
^ Report this to maintainers - all commands should be categorized
```

---

### Requirement 2: AI-First Help Text Structure

**ID**: CLI-002
**Priority**: HIGH
**Type**: Enhancement

All command help text must follow a standardized AI-first template with required sections optimized for machine parsing and human readability.

**Acceptance Criteria**:
- All commands have AI ASSISTANT CONTEXT section with 6 required fields
- Minimum 4 examples per command (common, workset, CI/CD, advanced)
- COMMON WORKFLOWS section with 3 scenario categories
- OUTPUT FORMAT with JSON schema
- PERFORMANCE EXPECTATIONS with small/medium/large project timings
- FLAG INTERACTIONS (if command has 3+ flags)

#### Scenario: AI extracts structured context from help text

**Given**: Command help text contains AI ASSISTANT CONTEXT section

**When**: AI assistant reads `aud <command> --help`

**Then**: AI can parse structured fields:
- Purpose (what command does)
- Input (files/tables read)
- Output (files/tables written)
- Prerequisites (commands to run first)
- Integration (workflow positioning)
- Performance (expected runtime)

**Example**:
```python
@click.command()
def example():
    """One-line summary of command.

    Extended purpose explanation...

    AI ASSISTANT CONTEXT:
      Purpose: Indexes source files into SQLite database
      Input: Source files (*.py, *.js, *.ts)
      Output: .pf/repo_index.db, .pf/manifest.json
      Prerequisites: None (run first)
      Integration: Foundation for all analysis commands
      Performance: Small ~30s, Medium ~5min, Large ~20min

    ...
    """
```

**And**: AI can directly answer questions like:
- "What does this command read?" → Source files
- "How long will this take?" → Check Performance field
- "What do I run first?" → Check Prerequisites

---

#### Scenario: Command has 4+ AI-consumable examples

**Given**: Command help text with EXAMPLES section

**When**: User runs `aud <command> --help`

**Then**: Help text contains minimum 4 examples

**And**: Each example has context comment (# Use Case N: Description)

**And**: Examples cover categories:
1. Most common usage
2. With workset (targeted analysis)
3. CI/CD integration (exit codes)
4. Advanced usage (multiple flags)

**Example**:
```
EXAMPLES (AI-CONSUMABLE):
  # Use Case 1: Most common usage
  aud detect-patterns

  # Use Case 2: With workset (after code changes)
  aud workset --diff HEAD~1 && aud detect-patterns --workset

  # Use Case 3: CI/CD integration (fail on errors)
  aud detect-patterns --quiet || exit $?

  # Use Case 4: Advanced usage (specific patterns only)
  aud detect-patterns --patterns security --severity critical
```

---

### Requirement 3: Command Categorization Taxonomy

**ID**: CLI-003
**Priority**: HIGH
**Type**: Enhancement

Commands must be organized into semantic categories with AI-specific context explaining when and why to use each category.

**Acceptance Criteria**:
- 9 defined categories: PROJECT_SETUP, CORE_ANALYSIS, SECURITY_SCANNING, DEPENDENCIES, CODE_QUALITY, DATA_REPORTING, ADVANCED_QUERIES, INSIGHTS_ML, UTILITIES
- Each category has title, description, commands list, and ai_context field
- No command appears in multiple categories
- All user-facing commands (except internal `_*`) are categorized
- Categories ordered by typical workflow sequence

#### Scenario: AI selects correct category for user task

**Given**: User asks "I want to check for security vulnerabilities"

**When**: AI reads `aud --help` and sees category descriptions

**Then**: AI identifies SECURITY_SCANNING category

**And**: AI reads ai_context: "Security-focused analysis. detect-patterns=rules, taint-analyze=data flow."

**And**: AI recommends commands from that category:
- `aud detect-patterns` for pattern-based rules
- `aud taint-analyze` for data flow analysis

**Example AI Reasoning**:
```
User task: Security vulnerabilities
↓
Match category: SECURITY_SCANNING
↓
Read ai_context: "Security-focused analysis..."
↓
Select commands: detect-patterns, taint-analyze
↓
Explain to user: "For security vulnerabilities, run:
  1. aud detect-patterns  # 100+ security rules
  2. aud taint-analyze    # Data flow from sources to sinks"
```

---

#### Scenario: Categories guide workflow ordering

**Given**: User is setting up TheAuditor for first time

**When**: AI reads category order in `aud --help`

**Then**: AI sees PROJECT_SETUP first

**And**: AI sees ai_context: "Run these FIRST in new projects. Creates .pf/ structure, installs tools."

**And**: AI recommends workflow:
1. PROJECT_SETUP commands (init, setup-ai)
2. CORE_ANALYSIS commands (index, workset)
3. SECURITY_SCANNING commands (detect-patterns, taint-analyze)

**Example**:
```
Category Order → Workflow Order:
1. PROJECT_SETUP: aud init && aud setup-ai
2. CORE_ANALYSIS: aud index
3. SECURITY_SCANNING: aud detect-patterns --workset
```

---

### Requirement 4: Minimum Help Text Quality Enforcement

**ID**: CLI-004
**Priority**: MEDIUM
**Type**: Quality Assurance

All commands must meet minimum documentation line count based on complexity tier, enforced via CI tests.

**Acceptance Criteria**:
- Complex commands (fce, taint-analyze, graph, insights, query): 200+ lines
- Medium commands (detect-patterns, deps, lint, full, index): 150+ lines
- Simple commands (init, workset, tool-versions, init-config, init-js): 80+ lines
- Utility commands (explain, planning): 50+ lines
- CI test fails if any command below minimum
- Exception allowlist for internal commands

#### Scenario: CI rejects insufficient documentation

**Given**: Developer creates new command with 30 lines of help text

**And**: Command classified as "medium" complexity (should be 150+ lines)

**When**: Developer commits and CI runs `pytest tests/test_cli_help_ai_first.py`

**Then**: Test `test_help_text_minimum_quality()` fails

**And**: Error message: "command-name has 30 lines (minimum 150 for medium)"

**And**: CI pipeline fails, blocking merge

**Example CI Output**:
```bash
$ pytest tests/test_cli_help_ai_first.py::test_help_text_minimum_quality -v

tests/test_cli_help_ai_first.py::test_help_text_minimum_quality FAILED

AssertionError: new-command has 30 lines (minimum 150 for medium)

Expected: help text ≥150 lines
Actual: 30 lines

Fix: Add required sections to command help text:
  - AI ASSISTANT CONTEXT (6 fields)
  - EXAMPLES (4 minimum)
  - COMMON WORKFLOWS (3 scenarios)
  - OUTPUT FORMAT, PERFORMANCE EXPECTATIONS, etc.
```

---

#### Scenario: Existing command below threshold gets flagged

**Given**: Existing command `tool-versions` has only 9 lines

**And**: Minimum for "simple" tier is 80 lines

**When**: CI runs after this change is merged

**Then**: Test fails for `tool-versions`

**And**: Developer must enhance before next merge

**Validation**:
```python
# Test code
def test_help_text_minimum_quality():
    MINIMUM_LINES = {'simple': 80, ...}
    COMMAND_TIERS = {'simple': ['tool-versions', ...]}

    for tier, commands in COMMAND_TIERS.items():
        for cmd_name in commands:
            cmd = cli.commands[cmd_name]
            help_lines = len(cmd.help.split('\n'))
            min_lines = MINIMUM_LINES[tier]
            assert help_lines >= min_lines, \
                f"{cmd_name} has {help_lines} lines (minimum {min_lines})"
```

---

### Requirement 5: Flag Interaction Documentation

**ID**: CLI-005
**Priority**: MEDIUM
**Type**: Enhancement

Commands with 3 or more flags must document interactions, conflicts, and recommended combinations.

**Acceptance Criteria**:
- FLAG INTERACTIONS section required if command has 3+ flags
- Three subsections: Mutually Exclusive, Recommended Combinations, Flag Modifiers
- Clear explanation of what happens when flags combined
- Examples of invalid and valid combinations
- CI test validates section exists for applicable commands

#### Scenario: AI avoids invalid flag combination

**Given**: Command `aud full` has FLAG INTERACTIONS section

**And**: Section lists: "Mutually Exclusive: --offline and --vuln-scan cannot be used together (vuln-scan requires network)"

**When**: User asks AI "Run full audit offline with vulnerability scan"

**Then**: AI detects conflict

**And**: AI explains: "Cannot use --offline with --vuln-scan (requires network)"

**And**: AI suggests alternative: "Use `aud full --offline` OR `aud full --vuln-scan` (not both)"

**Example**:
```
FLAG INTERACTIONS:
  Mutually Exclusive:
    --offline and --check-latest cannot be used together
    (--check-latest requires network to query registries)

  Recommended Combinations:
    Use --workset with --quiet for fast CI checks
    Use --verbose with --max-depth 3 for debugging

  Flag Modifiers:
    --quiet suppresses all output except errors
    --workset limits analysis to .pf/workset.json files
    --offline uses cached databases (no network calls)
```

**AI Decision Tree**:
```
User request: "aud full --offline --check-latest"
                          ↓
   Check FLAG INTERACTIONS: Mutually Exclusive found
                          ↓
          Reject combination, explain conflict
                          ↓
   Suggest alternatives: "aud full --offline" OR "aud full --check-latest"
```

---

#### Scenario: AI recommends optimal flag combination

**Given**: Command help text with "Recommended Combinations" section

**When**: User asks "I want comprehensive analysis but it's slow"

**Then**: AI checks PERFORMANCE EXPECTATIONS + FLAG INTERACTIONS

**And**: AI finds: "Use --workset with --quiet for fast CI checks"

**And**: AI recommends: "aud workset --diff HEAD~1 && aud full --workset --quiet"

**Rationale**: --workset limits scope (faster), --quiet reduces output overhead

---

### Requirement 6: Automated Validation Tests

**ID**: CLI-006
**Priority**: HIGH
**Type**: Quality Assurance

Automated CI tests must validate help text completeness, command categorization, and documentation standards.

**Acceptance Criteria**:
- Test: All commands categorized (no ungrouped)
- Test: Help text minimum quality (line counts)
- Test: AI ASSISTANT CONTEXT section exists
- Test: Minimum 4 examples per command
- Test: No duplicate categories
- Test: FLAG INTERACTIONS exists (if 3+ flags)
- All tests in `tests/test_cli_help_ai_first.py`
- CI runs tests on every PR

#### Scenario: Test suite catches missing AI CONTEXT section

**Given**: Developer creates new command without AI ASSISTANT CONTEXT

**When**: CI runs `pytest tests/test_cli_help_ai_first.py::test_ai_context_section_exists`

**Then**: Test fails with message: "new-command missing AI ASSISTANT CONTEXT section"

**And**: PR cannot merge until fixed

**Test Code**:
```python
def test_ai_context_section_exists():
    """Ensure all commands have AI ASSISTANT CONTEXT section."""
    from theauditor.cli import cli

    for cmd_name, cmd in cli.commands.items():
        if cmd_name.startswith('_'):
            continue  # Skip internal commands
        help_text = cmd.help or ""
        assert "AI ASSISTANT CONTEXT:" in help_text, \
            f"{cmd_name} missing AI ASSISTANT CONTEXT section"
```

**CI Output**:
```
FAILED tests/test_cli_help_ai_first.py::test_ai_context_section_exists
AssertionError: new-command missing AI ASSISTANT CONTEXT section

To fix: Add AI ASSISTANT CONTEXT section to command help text
Required fields:
  Purpose: [one sentence]
  Input: [files/tables read]
  Output: [files/tables written]
  Prerequisites: [commands to run first]
  Integration: [workflow positioning]
  Performance: [expected runtime]
```

---

#### Scenario: Test suite catches duplicate categorization

**Given**: Developer accidentally adds command to two categories

**When**: CI runs `pytest tests/test_cli_help_ai_first.py::test_no_duplicate_categories`

**Then**: Test fails with message: "Commands in multiple categories: ['duplicate-cmd']"

**Test Code**:
```python
def test_no_duplicate_categories():
    """Ensure no command appears in multiple categories."""
    from theauditor.cli import VerboseGroup
    from collections import Counter

    all_commands = []
    for cat_data in VerboseGroup.COMMAND_CATEGORIES.values():
        all_commands.extend(cat_data['commands'])

    duplicates = [cmd for cmd, count in Counter(all_commands).items() if count > 1]
    assert not duplicates, f"Commands in multiple categories: {duplicates}"
```

---

### Requirement 7: Backwards Compatibility

**ID**: CLI-007
**Priority**: CRITICAL
**Type**: Non-Functional

All changes must maintain 100% backwards compatibility with existing command syntax, behavior, and output formats.

**Acceptance Criteria**:
- Command flags unchanged (all options identical)
- Command behavior unchanged (same logic)
- Exit codes unchanged (same return values)
- Output formats unchanged (JSON schemas identical)
- Existing scripts continue to work without modification

#### Scenario: Existing script using aud commands continues to work

**Given**: User has shell script:
```bash
#!/bin/bash
aud init
aud index --exclude-self
aud full --offline || exit 1
```

**When**: CLI help system is updated

**Then**: Script runs successfully with no changes

**And**: Commands behave identically (same files created, same exit codes)

**And**: Only `--help` output differs (enhanced documentation)

**Validation**:
- Run existing test suite → All tests pass
- Check command registration → No changes to decorators/options
- Verify output files → Same paths, same formats
- Compare exit codes → Identical for success/failure cases

---

#### Scenario: CI pipeline with aud commands unaffected

**Given**: CI pipeline uses commands:
```yaml
- run: aud workset --diff ${{ github.base_ref }}..${{ github.head_ref }}
- run: aud detect-patterns --workset --quiet
- run: if [ $? -ne 0 ]; then exit 1; fi
```

**When**: Help system updated

**Then**: Pipeline continues to work

**And**: Exit codes remain same (0=success, 1=findings, 2=critical, 3=failed)

**And**: Workset file format unchanged (.pf/workset.json schema identical)

---

## Validation Criteria

### Success Metrics

| Metric | Baseline | Target | Method |
|--------|----------|--------|--------|
| Commands visible | 33/35 (94%) | 35/35 (100%) | `aud --help \| grep "aud " \| wc -l` |
| Min lines per command | 3 | 50+ | CI test `test_help_text_minimum_quality()` |
| Commands with AI CONTEXT | 0/35 (0%) | 35/35 (100%) | CI test `test_ai_context_section_exists()` |
| Commands with 4+ examples | ~21/35 (60%) | 35/35 (100%) | CI test `test_examples_exist()` |
| Commands with FLAG INTERACTIONS | 0/18 (0%) | 18/18 (100%) | CI test for commands with 3+ flags |
| Ungrouped commands | 2 | 0 | `aud --help \| grep "WARNING"` (should be empty) |

### Acceptance Tests

**Test 1**: All commands discoverable
```bash
# Count registered commands
registered=$(grep -c "cli.add_command" theauditor/cli.py)

# Count visible commands in help (excluding internal _*)
visible=$(aud --help | grep "  aud " | grep -v "_" | wc -l)

# Should match
test $registered -eq $visible || echo "FAIL: Commands missing from help"
```

**Test 2**: Help text quality
```bash
# Run full validation suite
pytest tests/test_cli_help_ai_first.py -v

# Expected: All tests pass
# - test_all_commands_categorized
# - test_help_text_minimum_quality
# - test_ai_context_section_exists
# - test_examples_exist
# - test_no_duplicate_categories
```

**Test 3**: AI usability (manual)
- Open new Claude/GPT session
- Provide only `aud --help` output
- Ask: "How do I analyze security vulnerabilities?"
- Expect: AI can answer using only help text (no source code needed)

**Test 4**: Backwards compatibility
```bash
# Run existing test suite
pytest tests/ -v

# All existing tests should pass (no regressions)
# Command behavior unchanged
```

---

## Dependencies

**External**: None

**Internal**:
- Python 3.11+ (existing requirement)
- Click 8.0+ (existing requirement)
- pytest (for CI tests)

**Files Modified**:
- `theauditor/cli.py` (VerboseGroup implementation)
- All `theauditor/commands/*.py` files (help text enhancements)
- `tests/test_cli_help_ai_first.py` (new validation tests)

**New Files**:
- `docs/CLI_DOCUMENTATION_STANDARD.md` (template and guidelines)
- `.github/CHECKLIST_CLI_DOCS.md` (reviewer checklist)

---

## Migration Path

**Phase 1**: Update VerboseGroup (no user impact)
**Phase 2**: Add validation tests (catches future regressions)
**Phase 3**: Enhance command help text (progressive improvement)
**Phase 4**: Enable CI enforcement (prevents quality decay)

**Rollback**: Revert commits per phase (each phase independent)

---

## Notes

- All scenarios tested with manual validation during development
- CI tests prevent regression after initial deployment
- Template provides consistency for future commands
- AI-first design means primary audience is AI assistants, secondary is humans
- No breaking changes - 100% backwards compatible
