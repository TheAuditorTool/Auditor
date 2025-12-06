# Proposal: AI-Optimized CLI Help Annotations

## Why

AI agents interact with CLI tools differently than humans. They tokenize entire help output, map intent to tools via few-shot learning, and hallucinate arguments when confused. Current CLI help:

1. **Root help lacks discriminative routing** - No "USE WHEN" / "GIVES" annotations to help AI pick correct command
2. **Subcommands lack negative constraints** - No "Anti-Patterns" to prevent common AI mistakes
3. **Examples not formatted for few-shot learning** - AI learns better from explicit "Copy These Patterns" headers
4. **Output format documentation inconsistent** - AI parses structured data more reliably when format is explicit
5. **`aud query --help` too verbose** - 400+ lines truncates AI context windows

This is **Phase 2** of the CLI help optimization (Phase 1: `refactor-cli-help` archived as `cli` spec).

**Foundation Document**: `/help_ai.md` contains complete strategy and mockups.

## What Changes

### 1. Root Help AI Annotations (**BREAKING** for automated parsers expecting current format)

Add per-command routing metadata to `aud --help`:

**BEFORE** (current):
```
Commands:
  PROJECT SETUP:
    setup-ai             Create isolated analysis environment with offline...
```

**AFTER** (proposed):
```
Commands:
  PROJECT SETUP:
    setup-ai      Create isolated analysis environment.
                  > RUN: Once per project, before first 'aud full'.
```

Each command gets:
- One-liner description (already exists)
- `> USE WHEN:` or `> RUN:` annotation (NEW)
- Optional `> GIVES:` annotation for query commands (NEW)

### 2. Subcommand Anti-Patterns Sections

Add explicit "DO NOT DO THIS" sections to prevent AI hallucination.

**Example for `aud query --help`**:
```
ANTI-PATTERNS (Do NOT Do This)
------------------------------
  X  aud query "how does auth work?"
     -> Use 'aud explain' or 'aud manual' for conceptual questions

  X  aud query --file "main.py"
     -> Use 'aud explain main.py' for file summaries

  X  aud query --symbol "foo" (without --show-callers or --show-callees)
     -> Always specify what relationship you want
```

### 3. Standardized Examples Format

Replace current varied example sections with consistent "Copy These Patterns" format.

**Format**:
```
EXAMPLES (Copy These Patterns)
------------------------------
  # [USE CASE DESCRIPTION in comment]
  aud command --flag value

  # [ANOTHER USE CASE]
  aud command --other-flag
```

### 4. Explicit Output Format Documentation

Each subcommand help gets OUTPUT FORMAT section showing both text and JSON.

**Format**:
```
OUTPUT FORMAT
-------------
Text mode:
  [exact example output]

JSON mode (--format json):
  [exact example JSON]
```

### 5. `aud query --help` Trimming

Current: ~400+ lines (truncates in 8K context windows)
Target: <150 lines

**Removal targets**:
- Redundant ARCHITECTURE section (moved to `aud manual`)
- Excessive SQL examples (moved to `aud manual database`)
- TROUBLESHOOTING section (moved to `aud manual`)
- Duplicate explanations

**Retention**:
- Core flag descriptions
- Anti-Patterns section
- 5-6 Copy These Patterns examples
- Output Format section

## Impact

### Affected Specs

- `cli` - MODIFIED: 4 new requirements for AI annotations

### Affected Code

| File | Change Type | Description |
|------|-------------|-------------|
| `theauditor/cli.py` | MODIFIED | Extend `COMMAND_CATEGORIES` with `command_meta`, modify `format_help()` |
| `theauditor/commands/explain.py` | MODIFIED | Add Anti-Patterns, Output Format sections to docstring |
| `theauditor/commands/query.py` | MODIFIED | Trim docstring, add Anti-Patterns, Output Format sections |
| `theauditor/commands/manual.py` | MODIFIED | Add new concepts: `database`, `troubleshooting`, `architecture` |
| `theauditor/commands/structure.py` | MODIFIED | Add Anti-Patterns, Output Format sections |
| `theauditor/commands/graph.py` | MODIFIED | Add Anti-Patterns, Output Format sections |
| `theauditor/commands/taint.py` | MODIFIED | Add Anti-Patterns, Output Format sections |

### Breaking Changes

1. **Automated help parsers** - Any script parsing `aud --help` output will see new `>` prefixed lines
2. **Help string length** - Subcommand docstrings change significantly
3. **Character encoding** - CRITICAL: Must remain ASCII-only (Windows CP1252 compatibility per CLAUDE.md)

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Root help formatting breaks CI scripts | MEDIUM | Check for existing grep/awk patterns in .github/ |
| Anti-Patterns section too long | LOW | Limit to 3-4 patterns per command |
| New manual concepts missing | LOW | Create skeleton, expand later |
| Unicode in examples | HIGH | Enforce ASCII-only in all docstrings |

## Verification Checklist (Pre-Implementation)

Per teamsop.md Prime Directive, verify BEFORE implementation:

- [ ] Confirm current `aud --help` line count: `aud --help 2>&1 | wc -l`
- [ ] Confirm current `aud query --help` line count: `aud query --help 2>&1 | wc -l`
- [ ] Search for existing help parsing in CI: `rg "aud.*--help" .github/`
- [ ] Verify VerboseGroup.COMMAND_CATEGORIES exists: Read `theauditor/cli.py:34-90`
- [ ] Verify no emojis in current help: `aud --help 2>&1 | grep -P '[^\x00-\x7F]'`
- [ ] Confirm `format_help()` structure: Read `theauditor/cli.py:92-122`

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| `aud --help` line count | ~75 | <60 |
| `aud query --help` line count | ~400 | <150 |
| Commands with USE WHEN/GIVES | 0% | 100% primary commands |
| Commands with Anti-Patterns | 0% | 100% query/analysis commands |
| Commands with Output Format | ~10% | 100% |
| ASCII-only enforcement | N/A | 100% |

## References

- Foundation document: `/help_ai.md`
- Team SOP: `/teamsop.md` (Prime Directive, verification-first workflow)
- Project conventions: `/openspec/project.md`
- Archived Phase 1: `openspec/specs/cli/spec.md`
- Click documentation: https://click.palletsprojects.com/en/8.1.x/api/#click.HelpFormatter
