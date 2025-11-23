## Context

TheAuditor's CLI help system evolved organically over time:
1. Original: Simple click-generated help
2. v1.x: Added "AI-Optimized Categorization" in `VerboseGroup.format_help()`
3. Later: Added massive docstrings to main `cli()` function
4. Result: Two competing help systems in one output (366 lines!)

Current stakeholders:
- AI assistants (primary consumers of help text)
- Human developers (need quick command discovery)
- CI/CD systems (need reliable command interface)

## Goals / Non-Goals

**Goals:**
- Reduce `aud --help` from 366 lines to <80 lines
- Make help scannable in 5 seconds
- Move educational content to `aud manual`
- Remove dead/confusing commands
- Hide internal/dev flags

**Non-Goals:**
- Changing command behavior
- Adding new commands (explain is in-progress separately)
- Modifying subcommand --help text (except removing bloat options)

## Decisions

### Decision 1: Single Help Section
**What:** Remove the PURPOSE/WORKFLOWS docstring from `cli()` at `cli.py:154-221`, keep only categorization.
**Why:** Eliminates redundancy. The categorization IS the help.
**Implementation:** Replace 65-line docstring with 10-line version.

### Decision 2: No Inline Options in Main Help
**What:** Remove lines 123-127 in `VerboseGroup.format_help()` that show first 3 params per command.
**Why:** Bloats output by 100+ lines. Options belong in `aud <cmd> --help`.
**Implementation:** Delete the for-loop that iterates `cmd.params[:3]`.

### Decision 3: Deprecate (Not Delete) init-config and init-js
**What:** Add deprecation warnings, hide from help, keep functional for 1 release.
**Why:** Safer than immediate deletion. May have external users.
**Implementation:**
- Add `hidden=True` to command decorator
- Print warning on execution: `"DEPRECATED: 'aud init-config' will be removed in v2.0. This functionality is not part of security auditing."`

### Decision 4: Absorb tool-versions into setup-ai
**What:** Add `--show-versions` flag to `setup.py`, deprecate standalone command.
**Why:** tool-versions only useful after setup-ai runs. Natural place for it.
**Implementation:**
- Add flag: `@click.option("--show-versions", is_flag=True, hidden=False, help="Show installed tool versions")`
- Copy version detection logic from `tool_versions.py`
- Deprecate `tool-versions` command with warning

### Decision 5: Fix Hidden Command Bug
**What:** Filter hidden commands from uncategorized warning at `cli.py:135`.
**Why:** Commands with `hidden=True` still appear in warning.
**Implementation:** Change `ungrouped = set(registered.keys()) - all_categorized` to filter `cmd.hidden`.

### Decision 6: Hide Dev Flags Using Click's hidden Parameter
**What:** Add `hidden=True` to dev-only options.
**Syntax:**
```python
# Before
@click.option("--exclude-self", is_flag=True, help="Exclude TheAuditor's own files")

# After
@click.option("--exclude-self", is_flag=True, hidden=True, help="Exclude TheAuditor's own files")
```
**Flags to hide:**
- `full.py:13` - `--exclude-self` (dev testing only)
- `full.py:15` - `--subprocess-taint` (debugging only)

**Flags to KEEP visible:**
- `--offline` (CI/CD use)
- `--quiet` (CI/CD use)
- `--wipecache` (recovery use)
- `--index` (common workflow)

### Decision 7: Resolved Open Questions

**Q1: Should --output-json be hidden globally?**
**A:** NO. Keep visible on all commands. JSON output is legitimate for scripting/automation.

**Q2: Should setup-ai --show-versions run detection or read cache?**
**A:** Read cache if `.pf/raw/tools.json` exists, run detection if not. Same behavior as current `tool-versions`.

## Target Output: `aud --help`

```
Usage: aud [OPTIONS] COMMAND [ARGS]...

  TheAuditor - Security & Code Intelligence Platform

  QUICK START:
    aud full                    # Complete security audit
    aud full --offline          # Air-gapped analysis
    aud manual --list           # Learn concepts

Options:
  --version   Show the version and exit.
  -h, --help  Show this message and exit.

Commands:
  PROJECT SETUP:
    setup-ai             Create isolated analysis environment

  CORE ANALYSIS:
    full                 Run comprehensive security audit (20 phases)
    workset              Compute targeted file subset for incremental analysis

  SECURITY SCANNING:
    detect-patterns      Detect security vulnerabilities and code quality issues
    taint-analyze        Trace data flow from sources to sinks
    boundaries           Analyze security boundary enforcement
    ...

  [remaining categories with command + one-line description only]

For detailed options: aud <command> --help
For concepts: aud manual --list
```

Target: ~60-70 lines (down from 366).

## Deprecation Warning Text

Exact text for deprecated commands:

```python
# init-config
click.echo("WARNING: 'aud init-config' is deprecated and will be removed in v2.0.")
click.echo("         Mypy configuration is not part of security auditing.")
click.echo("")

# init-js
click.echo("WARNING: 'aud init-js' is deprecated and will be removed in v2.0.")
click.echo("         Package.json scaffolding is not part of security auditing.")
click.echo("")

# tool-versions
click.echo("WARNING: 'aud tool-versions' is deprecated. Use 'aud setup-ai --show-versions' instead.")
click.echo("")
```

## New Manual Concepts Content

### `overview` concept
Content: Move PURPOSE and OUTPUT STRUCTURE from cli.py docstring.
~40 lines explaining what TheAuditor is and .pf/ structure.

### `workflows` concept
Content: Move COMMON WORKFLOWS from cli.py docstring.
~30 lines with git diff, PR review, CI/CD examples.

### `exit-codes` concept
Content: Move EXIT CODES from cli.py docstring.
~10 lines: 0=success, 1=high, 2=critical, 3=failed.

### `env-vars` concept
Content: Move ENVIRONMENT VARIABLES from cli.py docstring.
~15 lines: THEAUDITOR_LIMITS_*, THEAUDITOR_TIMEOUT_*, etc.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Breaking scripts using init-config/init-js | Deprecation warnings for 1 release, commands still work |
| Users can't find educational content | Clear "aud manual --list" pointer in help footer |
| Hiding too many options | Only hide 2 clearly dev-only options |

## File Change Summary

| File | Change Type | Lines Affected |
|------|-------------|----------------|
| `cli.py` | Edit | 88-145, 154-221 |
| `commands/full.py` | Edit | 13, 15 (add hidden=True) |
| `commands/manual.py` | Edit | 8-516 (add 4 concepts to EXPLANATIONS dict) |
| `commands/init_config.py` | Edit | Add hidden=True, deprecation warning |
| `commands/init_js.py` | Edit | Add hidden=True, deprecation warning |
| `commands/tool_versions.py` | Edit | Add hidden=True, deprecation warning |
| `commands/setup.py` | Edit | Add --show-versions flag |
