# Proposal: Add Polyglot Package Managers Module

## Status

**DRAFT** (Session: 2025-12-03)

## Why

`deps.py` is 1620 lines and `docs_fetch.py` is 646 lines. Both are monoliths handling multiple package ecosystems inline. Adding Go and Rust (full crates.io support) would push deps.py to 2300+ lines - unmaintainable.

Current state:
- npm: Full support (DB storage, version check, docs fetch, upgrade)
- Python: Full support (DB storage, version check, docs fetch, upgrade)
- Docker: Partial support (file parsing, version check, upgrade) - NO DB storage
- Cargo/Rust: Partial support (file parsing only) - NO version check, NO docs fetch, NO DB storage
- Go: Zero support

Additional issues found during Prime Directive investigation:
1. `docs_fetch.py` has ZERO imports from `theauditor.utils.logging` or `theauditor.pipeline.ui` - completely unwired from infrastructure

## What Changes

### New Module: `theauditor/package_managers/`

```
theauditor/package_managers/
    __init__.py      # Registry + orchestrator entry point
    base.py          # Abstract interface (BasePackageManager)
    docker.py        # Extract ~200 lines from deps.py
    cargo.py         # NEW: crates.io API, Cargo.toml upgrade, docs.rs docs
    go.py            # NEW: proxy.golang.org API, go.mod parsing/upgrade, pkg.go.dev docs
```

### Extraction: Docker from deps.py

Extract these functions from `deps.py` into `package_managers/docker.py`:
- `_parse_docker_compose()` (lines 279-322)
- `_parse_dockerfile()` (lines 325-375)
- `_fetch_docker_async()` (lines 483-535)
- `_parse_docker_tag()` (lines 863-912)
- `_extract_base_preference()` (lines 915-939)
- `_upgrade_docker_compose()` (lines 1300-1380)
- `_upgrade_dockerfile()` (lines 1383-1477)

Total: ~399 lines extracted, deps.py drops to ~1220 lines.

### Minimal Wiring Changes

**deps.py** (~20 lines changed):
- Import orchestrator
- Delegate cargo/go/docker calls to package_managers module

**docs_fetch.py** (~15 lines changed):
- Import orchestrator
- Add cargo/go to manager dispatch
- Wire up logging and console imports

**manifest_extractor.py** (~100 lines added):
- Add `_extract_cargo_toml()` method
- Add `_extract_go_mod()` method
- Add to `should_extract()` check

### New Language Support

**Cargo/Rust (cargo.py)**:
- Registry API: `https://crates.io/api/v1/crates/{name}`
- Docs API: `https://docs.rs/{name}/{version}/`
- File: Cargo.toml parsing (leverage existing `manifest_parser.py:185-238`)
- Upgrade: Cargo.toml version replacement

**Go (go.py)**:
- Registry API: `https://proxy.golang.org/{module}/@latest`
- Docs API: `https://pkg.go.dev/{module}@{version}`
- File: go.mod parsing (NEW)
- Upgrade: go.mod version replacement

### NOT Changing (Explicit)

- npm logic stays in deps.py/docs_fetch.py (future migration)
- Python logic stays in deps.py/docs_fetch.py (future migration)
- Database schema unchanged
- Command interface unchanged
- Output format unchanged

## Impact

- **Affected specs**: NEW capability `package-managers`
- **Affected code**:
  - `theauditor/package_managers/` (NEW)
  - `theauditor/deps.py` (minimal wiring + docker extraction)
  - `theauditor/docs_fetch.py` (minimal wiring)
  - `theauditor/indexer/extractors/manifest_extractor.py` (add Cargo/Go)
  - `theauditor/utils/rate_limiter.py` (add cargo/go rate limits)

## Non-Goals

- NOT extracting npm.py or python.py (future tech debt)
- NOT refactoring deps.py architecture
- NOT refactoring docs_fetch.py architecture
- NOT changing CLI interface
- NOT adding new commands
- NOT changing database schema

## Success Criteria

1. `aud deps --check-latest` works for Cargo packages (crates.io)
2. `aud deps --check-latest` works for Go modules (proxy.golang.org)
3. Docker logic extracted to `package_managers/docker.py`
4. deps.py reduced from 1620 to ~1220 lines
5. docs_fetch.py properly wired to logger/console
6. `aud full --index` extracts Cargo.toml and go.mod to database
7. All existing npm/Python functionality unchanged
