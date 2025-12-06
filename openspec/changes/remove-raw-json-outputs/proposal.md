## Why

The `.pf/raw/` directory is vestigial infrastructure from before the database was source of truth. Originally designed to chunk JSON for AI consumption, it now serves no purpose:

1. **Claude can't read it** - 10MB+ JSON files exceed context limits
2. **Database is source of truth** - JSON files are stale immediately after any code change
3. **Commands have `--json` flags** - On-demand JSON output to stdout already exists
4. **Fallback temptation** - Having both DB and JSON files invites Zero Fallback violations
5. **Wasted I/O** - Every `aud full` writes megabytes of redundant JSON

v2.0 breaking change provides perfect cover for this cleanup.

## What Changes

- **BREAKING**: Remove all `.pf/raw/` file writers from commands
- **BREAKING**: Remove `--write` flag from `aud fce`
- **BREAKING**: Remove `--output` flags that default to `.pf/raw/`
- Add `--json` flags to commands that lack them (stdout output)
- Update `aud full` pipeline summary to remove raw file counting
- Update archive command to not reference `.pf/raw/`
- Update all manual/help text referencing `.pf/raw/`

## Impact

- Affected specs: NEW `cli-output` capability
- Affected code:
  - `theauditor/commands/*.py` (~15 files with .pf/raw/ writes)
  - `theauditor/vulnerability_scanner.py`
  - `theauditor/commands/manual_lib01.py`, `manual_lib02.py` (help text)
  - `theauditor/commands/_archive.py`
  - `theauditor/commands/full.py` (pipeline summary)
- Breaking changes: Users expecting `.pf/raw/*.json` files will find nothing
- Migration: None. v2.0 breaking change. Delete your `.pf/raw/` directory.
