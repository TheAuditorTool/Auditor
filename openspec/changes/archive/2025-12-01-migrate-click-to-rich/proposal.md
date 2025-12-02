## Why

All 39 command files in `theauditor/commands/` use `click.echo()` for console output (1470 calls total). The pipeline infrastructure already uses Rich (`theauditor/pipeline/ui.py` with themed console singleton), but commands don't leverage it. This creates:

1. **Inconsistent output styling** - Pipeline has themed status panels, commands have plain text
2. **No semantic markup** - `[OK]`, `[ERROR]`, `[WARN]` prefixes are just strings, not styled tokens
3. **Windows CP1252 crashes** - Emojis in output cause `UnicodeEncodeError` on Windows Command Prompt
4. **Duplicate console instances** - Each command could create its own Console vs using shared singleton

A LibCST codemod (`scripts/rich_migration.py`) already exists and handles all transformation patterns.

## What Changes

- **39 command files** migrated from `click.echo()` to `console.print()` via automated codemod
- **Import updates**: Add `from theauditor.pipeline.ui import console`, remove unused `click` imports
- **Status prefix transformation**: `[OK]` -> `[success]`, `[WARN]` -> `[warning]`, `[ERROR]` -> `[error]`
- **Separator transformation**: `"=" * 60` -> `console.rule()`
- **Emoji removal**: All Unicode emojis stripped for Windows CP1252 compatibility
- **Bracket escaping**: Literal `[` in output escaped to prevent Rich markup injection
- **Safety flags**: `markup=False` for variables, `highlight=False` for f-strings with runtime values

## Impact

- **Affected specs**: `cli`, `pipeline`
- **Affected code**: All 39 files in `theauditor/commands/` (1470 click.echo calls)
- **Risk level**: MEDIUM - automated migration with syntax validation, but high file count
- **Breaking changes**: None - output semantics preserved, only styling enhanced
- **Dependencies**: `rich>=13.0.0` (already in pyproject.toml), `libcst` (dev dependency for migration)
