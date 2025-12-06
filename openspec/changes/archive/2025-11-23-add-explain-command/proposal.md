## Why

AI assistants using TheAuditor default to reading files instead of querying the indexed database because query results lack code context. The "Query vs Read" gap forces AI to run 5-6 separate queries or fall back to expensive file reads. `aud explain` provides comprehensive context in ONE command, eliminating this gap.

## What Changes

- **NEW**: `aud explain <target>` command providing holistic code context
- **NEW**: `CodeSnippetManager` utility for cached line reading from disk
- **NEW**: `ExplainFormatter` for structured output rendering
- **ENHANCEMENT**: Add `--show-code` flag to existing `aud query` command
- **ENHANCEMENT**: Update AI agents (planning.md, refactor.md) to prefer `aud explain`

## Impact

- Affected specs: NEW `explain` capability
- Affected code:
  - `theauditor/commands/explain.py` (NEW)
  - `theauditor/context/explain_formatter.py` (NEW)
  - `theauditor/utils/code_snippets.py` (NEW)
  - `theauditor/commands/query.py` (MODIFY: add --show-code)
  - `theauditor/cli.py` (MODIFY: register explain command)
  - `agents/planning.md` (MODIFY: add explain workflow)
  - `agents/refactor.md` (MODIFY: add explain workflow)

## Success Criteria

1. `aud explain file.tsx` returns symbols, hooks, dependencies, dependents, calls with code snippets
2. `aud explain Symbol.method` returns definition, callers, callees with code snippets
3. AI agents reduce file reads by 80% in typical refactoring workflows
4. Query time <100ms for typical files (50 symbols)
