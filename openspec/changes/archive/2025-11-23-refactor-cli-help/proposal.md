## Why

The current `aud --help` output is **366 lines** of unreadable chaos:
- Two redundant sections: CLI docstring (PURPOSE/WORKFLOWS/EXIT CODES) AND "AI-Optimized Categorization"
- Every command shows 3 inline options, bloating output massively
- Deprecated commands (`index`, `init`, `setup-claude`) pollute the warning section
- Mystery commands (`init-config`, `init-js`) confuse users
- Dev flags (`--exclude-self`) exposed in public help
- `aud manual` exists but is barely referenced

The help was designed for AI but is unusable by BOTH humans AND AI. It's so verbose that context windows get filled with noise.

## What Changes

### Phase 1: Clean Main Help (reduce 366 lines to ~60 lines)
- Remove PURPOSE block, WORKFLOWS, OUTPUT STRUCTURE, EXIT CODES, ENV VARS from main docstring
- Move this content to `aud manual overview` (new concept)
- Keep ONLY: one-liner description + QUICK START (3 lines) + command categories (no inline options)
- Remove inline option display from `format_help()` (params belong in subcommand --help)

### Phase 2: Remove Deprecated/Questionable Commands
- **REMOVE** `init-config` command entirely (mypy config has nothing to do with auditing)
- **REMOVE** `init-js` command entirely (package.json scaffolding belongs in setup-ai or nowhere)
- **REMOVE** `tool-versions` from main help (move to `aud setup-ai --show-versions` flag)
- **HIDE** deprecated commands properly (fix the uncategorized warning bug)

### Phase 3: Hide Dev/Internal Flags
- Remove `--exclude-self` from `aud full` public help (keep in click, hide from help)
- Remove `--db` and `--output-json` bloat from most commands (use defaults)
- Review all commands for similar bloat

### Phase 4: Enhance `aud manual`
- Add `overview` concept (contains current PURPOSE, WORKFLOWS, OUTPUT STRUCTURE, etc.)
- Add `commands` concept (command reference moved here)
- Add `env-vars` concept
- Cross-reference from main help to manual

## Impact
- Affected specs: None (no specs exist yet)
- Affected code:
  - `theauditor/cli.py` (main changes)
  - `theauditor/commands/init_config.py` (delete)
  - `theauditor/commands/init_js.py` (delete)
  - `theauditor/commands/tool_versions.py` (refactor to flag)
  - `theauditor/commands/manual.py` (add concepts)
  - `theauditor/commands/full.py` (hide dev flags)
  - `theauditor/commands/setup.py` (add --show-versions)

## Success Criteria
- `aud --help` output is <80 lines
- All commands discoverable via `aud --help`
- No deprecation warnings in help output
- `aud manual overview` contains moved content
- Dev flags hidden from public --help
