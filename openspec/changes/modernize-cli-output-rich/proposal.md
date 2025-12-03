# Proposal: Modernize CLI Output with Rich Formatting

## Why

TheAuditor's main `aud --help` looks spectacular with Rich panels, tables, and color themes. But every subcommand help (e.g., `aud taint-analyze --help`) is a wall of poorly-wrapped plaintext that makes you want to die.

**The Problem:**
- Main help: Beautiful Rich-formatted dashboard with categorized panels
- Subcommand help: Click's default plaintext dump with horrible line wrapping
- Manual entries: Basic ASCII box formatting, no Rich
- Content: Much of the text is outdated from 5+ architecture rewrites - describes features that don't exist or uses sterile language that doesn't reflect what the tool actually does

**Current State:**
```
aud --help          -> Rich panels, tables, color themes (BEAUTIFUL)
aud taint-analyze --help -> Wall of plaintext, bad wrapping (UGLY)
aud graph --help    -> Plaintext with inconsistent formatting (UGLY)
aud manual taint    -> ASCII boxes, no syntax highlighting (MEH)
```

**Why This Matters:**
1. First impressions - users see inconsistent quality
2. AI assistants parse these help texts - better formatting = better context
3. Professional polish - we've done the hard work, now finish it

## Scope

This proposal covers CLI output modernization across **36 command files** and **16 manual entries**:

| Category | Files | Current State | Target State |
|----------|-------|---------------|--------------|
| Command docstrings | 36 files | Click plaintext | Rich-formatted sections |
| Manual entries | 16 entries | ASCII boxes | Rich panels + syntax highlighting |
| Option descriptions | ~200 options | Terse/outdated | Clear, accurate |
| Content accuracy | All text | 5+ rewrites behind | Reflects current architecture |

**In Scope:**
- Create `RichCommand` class for subcommand help formatting
- Migrate all 36 command files to structured Rich help
- Update 16 manual entries with Rich formatting
- Grammar/style cleanup pass on all text
- Update outdated descriptions to match current tool behavior
- Standardize section headers (AI CONTEXT, EXAMPLES, OPTIONS, etc.)

**Out of Scope:**
- JSON/machine output formats (already work fine)
- Pipeline progress display (already Rich-enabled)
- Log formatting (already Loguru/Rich integrated)

---

## What Changes

### 1. Create RichCommand Base Class (`cli.py`)

**ADD** `RichCommand(click.Command)` class similar to existing `RichGroup`:
- Override `format_help()` to render with Rich
- Parse docstring sections: SUMMARY, AI CONTEXT, EXAMPLES, OPTIONS
- Render each section with appropriate Rich components
- Use consistent color scheme from `AUDITOR_THEME`

```python
class RichCommand(click.Command):
    """Rich-enabled help formatter for individual commands."""

    def format_help(self, ctx, formatter):
        console = Console(theme=AUDITOR_THEME)
        # Parse docstring into sections
        # Render with Rich panels/tables
```

### 2. Standardize Docstring Format (All 36 Commands)

**DEFINE** canonical docstring structure:

```python
"""One-line summary that appears in main help.

DESCRIPTION:
  2-3 sentence expanded description of what this does.

AI ASSISTANT CONTEXT:
  Purpose: What this command does
  Input: Required files/database
  Output: What gets produced
  Prerequisites: What must run first

EXAMPLES:
  aud command --option value    # Comment
  aud command --other           # Another example

RELATED COMMANDS:
  aud other-command    Brief description
"""
```

### 3. Migrate Command Files (36 files)

**MODIFY** each command file to use new format:

| File | Lines | Priority | Notes |
|------|-------|----------|-------|
| taint.py | 583 | HIGH | Most verbose, needs heavy trim |
| graph.py | 862 | HIGH | Group command, many subcommands |
| manual.py | 1201 | HIGH | All 16 explanations need Rich |
| blueprint.py | 1728 | MEDIUM | Mostly implementation, small docstrings |
| planning.py | 1411 | MEDIUM | Heavy docstrings |
| refactor.py | 994 | MEDIUM | Verbose explanations |
| ml.py | 866 | MEDIUM | Multiple commands |
| query.py | 541 | MEDIUM | Complex options |
| deps.py | 411 | LOW | Moderate docstrings |
| impact.py | 388 | LOW | Standard format |
| (26 more) | various | LOW | Standard migration |

### 4. Update Manual Entries (`manual.py`)

**MODIFY** `EXPLANATIONS` dict entries to use Rich markup:

```python
"taint": {
    "title": "Taint Analysis",
    "summary": "...",
    "explanation": """
[bold cyan]CONCEPTS:[/bold cyan]
- [yellow]Source:[/yellow] Where untrusted data enters
- [yellow]Sink:[/yellow] Dangerous operations
...
[bold cyan]EXAMPLE VULNERABILITY:[/bold cyan]
[dim]python[/dim]
user_input = request.body.get('name')  [red]# SOURCE[/red]
query = f"SELECT * WHERE name = '{user_input}'"
db.execute(query)  [red]# SINK: SQL injection![/red]
"""
}
```

### 5. Content Modernization Pass

**UPDATE** all text to reflect current architecture:

| Issue | Example | Fix |
|-------|---------|-----|
| Outdated features | "Run `aud index` first" | "Run `aud full` (index is deprecated)" |
| Wrong table names | "function_call_args table" | Verify actual table names |
| Missing features | No mention of Go/Rust | Add polyglot support mentions |
| Sterile language | "Performs inter-procedural analysis" | "Traces data flow across functions to find where user input reaches dangerous operations" |
| Dead options | Options that no longer work | Remove or mark deprecated |

### 6. Grammar/Style Consistency

**STANDARDIZE:**
- Sentence case for all headings
- Active voice ("Detects..." not "Detection of...")
- Consistent capitalization (TheAuditor, not theauditor)
- No trailing periods in option descriptions
- Consistent terminology (finding vs issue vs vulnerability)

---

## Complete File Inventory

### Group Commands (10 files - need RichGroup)

| File | Decorator Line | Subcommands |
|------|----------------|-------------|
| graph.py | 12 | build, build-dfg, analyze, query, viz |
| session.py | 22 | analyze, list, inspect, report, activity |
| planning.py | 46 | (invoke_without_command) |
| terraform.py | 16 | analyze, scan |
| cfg.py | 12 | analyze, viz |
| tools.py | 185 | (subcommands TBD) |
| workflows.py | 20 | (subcommands TBD) |
| metadata.py | 9 | (subcommands TBD) |
| cdk.py | 16 | analyze |
| graphql.py | 12 | (subcommands TBD) |

### Standalone Commands (26 files - need RichCommand)

| File | Decorator Line | Priority |
|------|----------------|----------|
| taint.py | 14 | HIGH |
| manual.py | 1015 | HIGH |
| full.py | 67 | HIGH |
| index.py | 11 | HIGH |
| detect_patterns.py | 11 | HIGH |
| blueprint.py | 20 | MEDIUM |
| refactor.py | 44 | MEDIUM |
| query.py | 16 | MEDIUM |
| deps.py | 15 | MEDIUM |
| impact.py | 13 | MEDIUM |
| explain.py | 78 | MEDIUM |
| workset.py | 9 | MEDIUM |
| deadcode.py | 16 | LOW |
| context.py | 18 | LOW |
| boundaries.py | 17 | LOW |
| docker_analyze.py | 13 | LOW |
| lint.py | 88 | LOW |
| fce.py | 9 | LOW |
| detect_frameworks.py | 16 | LOW |
| docs.py | 11 | LOW |
| rules.py | 16 | LOW |
| setup.py | 14 | LOW |
| ml.py | 10, 398, 617 | LOW (3 commands) |
| _archive.py | 15 | LOW (hidden) |

---

## Implementation Strategy (Batched with Verification)

### Phase 0: Infrastructure (1 file, verify pattern works)
- Create `RichCommand` class at `cli.py:140` (after existing RichGroup)
- Test with `manual.py` only
- **Verify**: `aud manual --help` shows Rich output before proceeding

### Phase 1: Batch 1 - Core Commands (5 files)
- manual.py, full.py, taint.py, index.py, detect_patterns.py
- **Verify**: All 5 commands show Rich formatting

### Phase 2: Batch 2 - Graph & Session Groups (2 files, 10 subcommands)
- graph.py (5 subcommands), session.py (5 subcommands)
- **Verify**: Group and subcommand help both Rich

### Phase 3: Batch 3 - Medium Priority (8 files)
- blueprint.py, refactor.py, query.py, deps.py, impact.py, explain.py, workset.py, deadcode.py
- **Verify**: All 8 commands show Rich formatting

### Phase 4: Batch 4 - Remaining Groups (8 files)
- planning.py, terraform.py, cfg.py, tools.py, workflows.py, metadata.py, cdk.py, graphql.py
- **Verify**: All groups and subcommands Rich

### Phase 5: Batch 5 - Remaining Standalone (10 files)
- context.py, boundaries.py, docker_analyze.py, lint.py, fce.py, detect_frameworks.py, docs.py, rules.py, setup.py, ml.py
- **Verify**: All commands Rich

### Phase 6: Final Polish (1 file + review)
- _archive.py (hidden)
- Consistency review, grammar check, example verification
- **Verify**: All 36 files complete, no regressions

---

## Success Criteria

1. **Visual Consistency**: `aud <any-command> --help` looks as polished as `aud --help`
2. **Content Accuracy**: All descriptions match current tool behavior
3. **Grammar Clean**: No typos, consistent style throughout
4. **AI-Friendly**: Structured sections that AI assistants can parse

## Risks

| Risk | Mitigation |
|------|------------|
| Click formatter limitations | Test RichCommand early, fallback to manual print() |
| Docstring parsing edge cases | Define strict format, validate during migration |
| Breaking existing scripts | Help text changes don't affect exit codes/output |

---

## Files Affected

**Infrastructure (create new class):**
- `theauditor/cli.py:140` - Add RichCommand class after RichGroup (lines 24-138)

**Primary (36 command files in `theauditor/commands/`):**
- 10 group commands (need RichGroup for group + RichCommand for subcommands)
- 26 standalone commands (need RichCommand)
- See Complete File Inventory above for exact line numbers

**Manual entries (content in `theauditor/commands/manual.py`):**
- Lines 7-1012: EXPLANATIONS dict with 16 entries
- Line 1200: Remove `markup=False` to enable Rich

**Key locations:**
- Existing RichGroup pattern: `cli.py:24-138`
- AUDITOR_THEME: `pipeline/ui.py:8-21`
- Console instance: `pipeline/ui.py:24`

**Total estimated changes:** ~3,000 lines modified/reformatted across 37 files
