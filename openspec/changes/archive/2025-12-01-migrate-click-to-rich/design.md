## Context

TheAuditor CLI has 39 command files using `click.echo()` for output. The pipeline infrastructure (`theauditor/pipeline/ui.py`) already provides a Rich-based console singleton with themed styling. This migration unifies all CLI output through the Rich console.

**Stakeholders**: All CLI users, CI/CD pipelines, Windows users (CP1252 encoding)

**Constraints**:
- Must preserve output semantics (same information, enhanced styling)
- Must not break Windows Command Prompt (CP1252 encoding)
- Must be automatable (1470 calls across 39 files - manual migration impractical)

## Goals / Non-Goals

**Goals**:
- Unified console output through single Rich Console instance
- Semantic styling via Rich markup tokens (`[success]`, `[error]`, `[warning]`)
- Windows CP1252 compatibility (no emojis, no problematic Unicode)
- Automated migration via LibCST codemod

**Non-Goals**:
- Adding new output features (spinners, progress bars) - out of scope
- Changing output content/structure - only styling changes
- Migrating non-command code (engines, utilities) - commands only

## Decisions

### Decision 1: LibCST Codemod for Automated Migration

**What**: Use `scripts/rich_migration.py` LibCST-based codemod to transform all calls automatically.

**Why**:
- 1470 calls is too many for manual migration
- LibCST preserves formatting and handles edge cases
- Syntax validation before writing prevents broken code
- Consistent transformation rules across all files

**Alternatives considered**:
- Manual migration: Rejected - too error-prone at scale
- Regex-based sed/awk: Rejected - can't handle nested structures, f-strings, escaping
- AST-based without LibCST: Rejected - harder to preserve formatting

### Decision 2: Single Console Singleton Pattern

**What**: All commands import `console` from `theauditor.pipeline.ui` instead of creating their own.

**Why**:
- Consistent theming across all commands
- Single source of truth for console configuration
- TTY detection handled once, not per-command
- Already established pattern in `full.py`

**Pattern**:
```python
# Every command file
from theauditor.pipeline.ui import console

# Usage
console.print("[success]Operation completed[/success]")
console.print(f"[path]{file_path}[/path]")
console.rule()  # Instead of click.echo("=" * 60)
```

### Decision 3: Semantic Token Mapping

**What**: Map status prefixes to Rich markup tokens.

| Click Pattern | Rich Token | Theme Style |
|--------------|------------|-------------|
| `[OK]`, `[PASS]`, `[SUCCESS]` | `[success]...[/success]` | bold green |
| `[WARN]`, `[WARNING]` | `[warning]...[/warning]` | bold yellow |
| `[ERROR]`, `[FAILED]`, `[FAIL]` | `[error]...[/error]` | bold red |
| `[INFO]` | `[info]...[/info]` | bold cyan |
| `[CRITICAL]` | `[critical]...[/critical]` | bold red |
| `[HIGH]` | `[high]...[/high]` | bold yellow |
| `[MEDIUM]` | `[medium]...[/medium]` | bold blue |
| `[LOW]` | `[low]...[/low]` | cyan |

**Why**: Semantic tokens map to AUDITOR_THEME defined in `ui.py`, providing consistent severity coloring.

### Decision 4: Bracket Escaping for Safety

**What**: Escape literal `[` characters in output strings to prevent Rich markup injection.

**Why**: Rich interprets `[tag]` as markup. If output contains data like `array[0]` or `regex [a-z]`, Rich will try to parse it as a tag.

**How**: The codemod escapes `[` as `\\[` in string literals. This produces `\[` in the source file, which Rich renders as literal `[`.

**Edge case**: Variables and f-string expressions cannot be escaped at static analysis time. For these:
- Pure variables: Add `markup=False` to prevent crashes
- F-strings with variables: Add `highlight=False` to prevent markup injection

### Decision 5: Emoji Removal for Windows

**What**: Strip all emoji and problematic Unicode characters during migration.

**Why**: Windows Command Prompt uses CP1252 encoding. Emojis cause `UnicodeEncodeError: 'charmap' codec can't encode character`.

**Mapping**:
- Check marks (U+2714, U+2705) -> `[OK]`
- X marks (U+274C, U+2716) -> `[X]`
- Warning sign (U+26A0) -> `[WARN]`
- Arrows -> ASCII equivalents (`->`, `<-`)
- Decorative emojis -> removed entirely

### Decision 6: Argument Mapping

| Click | Rich console.print |
|-------|-------------------|
| `err=True` | `stderr=True` |
| `nl=False` | `end=""` |
| `file=sys.stderr` | `stderr=True` |
| `file=sys.stdout` | (dropped - default) |
| `file=<other>` | **SKIP** - manual migration |
| `color=...` | (dropped - Console handles) |

## Risks / Trade-offs

### Risk 1: Migration Script Bugs
**Risk**: Codemod produces invalid Python or incorrect transformations.
**Mitigation**:
- Script runs `compile()` on output before writing
- Dry-run mode shows diff without modifying
- Manual review of high-count files (blueprint.py, planning.py)

### Risk 2: Variable Shadowing
**Risk**: If a file already has a variable named `console`, the import will shadow it.
**Mitigation**:
- Migration script detects existing `console` usage and warns
- Manual review required for flagged files

### Risk 3: Binary Concatenation
**Risk**: Patterns like `"[ERROR] " + message` can't be fully transformed.
**Mitigation**:
- Script warns about these patterns
- Rich will render `[ERROR]` as-is (unstyled but not broken)
- Manual refactoring to f-string recommended for full styling

### Risk 4: Custom file= Streams
**Risk**: `click.echo("msg", file=custom_stream)` can't migrate to console.print.
**Mitigation**:
- Script skips these calls and warns
- Manual migration required (create new Console instance for stream)

## Migration Plan

1. **Pre-flight**: Verify dependencies, run baseline counts
2. **Dry run**: Execute codemod with `--dry-run --diff` to preview
3. **Execute**: Run codemod on all command files
4. **Validate**: Syntax check, type check, count verification
5. **Review**: Manual inspection of high-risk files
6. **Test**: Functional testing of key commands
7. **Cleanup**: Ruff formatting, unused import removal

## Rollback

**Reversibility**: Fully reversible via `git checkout -- theauditor/commands/`

**Steps**:
1. `git diff theauditor/commands/` to see changes
2. `git checkout -- theauditor/commands/` to revert all
3. Or selectively: `git checkout -- theauditor/commands/specific_file.py`

## Open Questions

None - migration script already implemented and tested. This spec documents the existing solution.
