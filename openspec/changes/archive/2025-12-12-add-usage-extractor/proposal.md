# Proposal: add-usage-extractor

## Why

TheAuditor already fetches version-correct documentation from package registries (NPM, PyPI, crates.io, pkg.go.dev) and caches it as markdown in `.pf/context/docs/{manager}/{name}@{version}/`. However, there is NO mechanism to parse these cached docs back into usable code snippets. AI agents cannot query "show me how to use axios" and get injectable code - they get raw markdown or nothing.

This is the "last mile" problem: we have version-pinned intelligence (exact versions from lock files) and cached docs, but no refinery to extract the gold (usage examples).

## What Changes

- **ADDED**: New Python module `theauditor/package_managers/usage_extractor.py` (~150 lines)
  - Parses markdown files for fenced code blocks
  - Scores snippets by quality heuristics (demote installs, promote imports/usage)
  - Returns ranked list of `CodeSnippet` dataclasses

- **ADDED**: New CLI option `aud deps --usage <package>`
  - Queries cached docs for a specific package
  - Returns top 3-5 scored code snippets
  - Auto-triggers `docs_fetch` if cache is cold

- **ADDED**: JSON output mode for AI consumption (`--format json`)

## Impact

- **Affected specs**: NEW capability `package-docs` (does not modify existing specs)
- **Affected code**:
  - `theauditor/package_managers/usage_extractor.py` (NEW)
  - `theauditor/commands/deps.py` (add `--usage` option)
- **No breaking changes**: Additive feature only
- **No polyglot concern**: Python-only implementation (no Node/Rust needed - this operates on cached markdown files, not AST extraction)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Regex fails on edge-case markdown | Medium | Low | Conservative parsing, skip malformed blocks |
| Scoring heuristics miss good examples | Medium | Low | Heuristics are tunable, start conservative |
| Cache miss with no network | Low | Low | Clear error message, suggest `aud full` |

## Success Criteria

1. `aud deps --usage axios` returns 3+ code snippets with import statements
2. `aud deps --usage requests --format json` returns structured JSON for AI agents
3. Install commands (`npm install`, `pip install`) are NOT in top results
4. Works offline with existing cache (no network required)
