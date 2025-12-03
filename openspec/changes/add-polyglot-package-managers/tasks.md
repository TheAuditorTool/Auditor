# Tasks: Add Polyglot Package Managers Module

## 0. Verification (Prime Directive)

- [x] 0.1 Read deps.py fully - confirm 1623 lines, identify Docker extraction points
- [x] 0.2 Read docs_fetch.py fully - confirm missing logger/console imports
- [x] 0.3 Read manifest_extractor.py - confirm Cargo/Go extraction missing
- [x] 0.4 Read manifest_parser.py - confirm Cargo.toml parser exists
- [x] 0.5 Read utils/logging.py - confirm loguru setup
- [x] 0.6 Read pipeline/ui.py - confirm Rich console setup
- [x] 0.7 Read utils/rate_limiter.py - confirm rate limiter pattern

## 1. Infrastructure: Base Module

- [ ] 1.1 Create `theauditor/package_managers/__init__.py` with registry pattern
- [ ] 1.2 Create `theauditor/package_managers/base.py` with `BasePackageManager` abstract class
  - Methods: `parse_manifest()`, `fetch_latest_async()`, `fetch_docs_async()`, `upgrade_file()`
  - Properties: `manager_name`, `file_patterns`, `registry_url`

## 2. Docker Extraction

- [ ] 2.1 Create `theauditor/package_managers/docker.py` extending BasePackageManager
- [ ] 2.2 Extract `_parse_docker_compose()` from deps.py:279-323 -> `parse_manifest()` for compose files
- [ ] 2.3 Extract `_parse_dockerfile()` from deps.py:325-376 -> `parse_manifest()` for Dockerfiles
- [ ] 2.4 Extract `_fetch_docker_async()` from deps.py:486-538 -> `fetch_latest_async()`
- [ ] 2.5 Extract `_parse_docker_tag()` from deps.py:866-915 -> private `_parse_docker_tag()`
- [ ] 2.6 Extract `_extract_base_preference()` from deps.py:918-943 -> private `_extract_base_preference()`
- [ ] 2.7 Extract `_upgrade_docker_compose()` from deps.py:1303-1384 -> `upgrade_file()` for compose
- [ ] 2.8 Extract `_upgrade_dockerfile()` from deps.py:1386-1480 -> `upgrade_file()` for Dockerfiles
- [ ] 2.9 Update deps.py imports and wiring:
  - Add `from theauditor.package_managers import get_manager` at line ~20
  - Replace Docker parsing at lines 81-103 (see design.md Decision 9)
  - Replace Docker version fetch at lines 575-590 (see design.md Decision 9)
  - Replace Docker upgrade at lines 1099-1143 (see design.md Decision 9)
- [ ] 2.10 Delete extracted functions from deps.py (279-323, 325-376, 486-538, 866-943, 1303-1480)
- [ ] 2.11 Verify: `aud deps` with docker-compose.yml still works
- [ ] 2.12 Verify: `aud deps --check-latest` still works for Docker images
- [ ] 2.13 Verify: `aud deps --upgrade-docker` still works

## 3. Cargo/Rust Support

- [ ] 3.1 Create `theauditor/package_managers/cargo.py` extending BasePackageManager
- [ ] 3.2 Implement `parse_manifest()` - reuse `theauditor/manifest_parser.py:185-238` parse_cargo_toml()
- [ ] 3.3 Implement `fetch_latest_async()` using crates.io API (see design.md Decision 4)
  - Endpoint: `https://crates.io/api/v1/crates/{name}`
  - Parse `data["crate"]["max_version"]` for stable
  - User-Agent header: `TheAuditor/{__version__} (dependency checker)`
- [ ] 3.4 Implement `fetch_docs_async()` using crates.io API `readme` field (see design.md Decision 12)
  - Primary: `data["crate"]["readme"]` from version check response
  - Fallback: GitHub README via `data["crate"]["repository"]`
  - NO docs.rs scraping needed
- [ ] 3.5 Implement `upgrade_file()` for Cargo.toml using regex (see design.md Decision 11)
  - Pattern 1: `name = "version"` simple string
  - Pattern 2: `name = { version = "..." }` table format
- [ ] 3.6 Add rate limiter constant `RATE_LIMIT_CARGO = 1.0` to `theauditor/utils/rate_limiter.py`
- [ ] 3.7 Add "cargo" to `delays` dict in `get_rate_limiter()` at rate_limiter.py:59-65
- [ ] 3.8 Wire cargo version check at deps.py:575-590 (see design.md Decision 9)
- [ ] 3.9 Wire cargo docs at docs_fetch.py:170-180 (see design.md Decision 10)

## 4. Go Support

- [ ] 4.1 Create `theauditor/package_managers/go.py` extending BasePackageManager
- [ ] 4.2 Implement `parse_manifest()` for go.mod (see design.md Decision 6)
  - Parse `module` directive for module path
  - Parse `require (...)` block with regex
  - Parse single-line `require module version` statements
  - Return `{"name": module, "version": version, "manager": "go", "source": path}`
- [ ] 4.3 Implement `encode_go_module()` helper for proxy URL encoding (see design.md Decision 5)
  - Uppercase letters become `!lowercase` (e.g., `Azure` -> `!azure`)
- [ ] 4.4 Implement `fetch_latest_async()` using Go proxy (see design.md Decision 5)
  - Endpoint: `https://proxy.golang.org/{encoded_module}/@latest`
  - Parse `data["Version"]` from JSON response
- [ ] 4.5 Implement `fetch_docs_async()` using pkg.go.dev (see design.md Decision 13)
  - Endpoint: `https://pkg.go.dev/{module}@{version}`
  - Extract `<section class="Documentation">` HTML
  - Convert to markdown with BeautifulSoup + markdownify (fallback: regex)
- [ ] 4.6 Implement `upgrade_file()` for go.mod using regex
  - Update version in `require (...)` blocks
  - Update single-line `require` statements
- [ ] 4.7 Add rate limiter constant `RATE_LIMIT_GO = 0.5` to `theauditor/utils/rate_limiter.py`
- [ ] 4.8 Add "go" to `delays` dict in `get_rate_limiter()` at rate_limiter.py:59-65
- [ ] 4.9 Wire go parsing at deps.py:~110 (see design.md Decision 9) - add go.mod discovery loop
- [ ] 4.10 Wire go version check at deps.py:575-590 (see design.md Decision 9)
- [ ] 4.11 Wire go docs at docs_fetch.py:170-180 (see design.md Decision 10)

## 5. Manifest Extractor (DB Storage)

- [ ] 5.1 Add `_extract_cargo_toml()` to `theauditor/indexer/extractors/manifest_extractor.py`
  - Call `self.db_manager.add_cargo_package_config()`
  - Call `self.db_manager.add_cargo_dependency()` for each dep
- [ ] 5.2 Add `_extract_go_mod()` to `theauditor/indexer/extractors/manifest_extractor.py`
  - Call `self.db_manager.add_go_module_config()`
  - Call `self.db_manager.add_go_dependency()` for each dep
- [ ] 5.3 Update `should_extract()` at manifest_extractor.py:92-106 to match Cargo.toml and go.mod
- [ ] 5.4 Add `add_cargo_package_config()` and `add_cargo_dependency()` to `theauditor/indexer/database/rust_database.py:401+`
- [ ] 5.5 Add `add_go_module_config()` and `add_go_dependency()` to `theauditor/indexer/database/go_database.py:356+`
- [ ] 5.6 Add table schemas to `theauditor/indexer/tables/` (see design.md Decision 7 for SQL)

## 6. Logging/UI Fixes

- [ ] 6.1 Fix deps.py:407-411 - remove local logger shadow in `_parse_cargo_toml()`
- [ ] 6.2 Add `from theauditor.utils.logging import logger` to docs_fetch.py
- [ ] 6.3 Add `from theauditor.pipeline.ui import console` to docs_fetch.py
- [ ] 6.4 Replace silent error returns with proper logging in docs_fetch.py

## 7. Testing & Validation

- [ ] 7.1 Test: `aud deps` with Cargo.toml present
- [ ] 7.2 Test: `aud deps --check-latest` with Cargo packages
- [ ] 7.3 Test: `aud deps` with go.mod present
- [ ] 7.4 Test: `aud deps --check-latest` with Go modules
- [ ] 7.5 Test: `aud full --index` extracts Cargo.toml to DB
- [ ] 7.6 Test: `aud full --index` extracts go.mod to DB
- [ ] 7.7 Test: All existing npm/Python functionality unchanged
- [ ] 7.8 Test: Docker functionality unchanged after extraction

## 8. Post-Implementation Audit

- [ ] 8.1 Re-read all modified files for correctness
- [ ] 8.2 Verify no ZERO FALLBACK violations introduced
- [ ] 8.3 Verify no emojis in Python output (Windows CP1252)
- [ ] 8.4 Run `aud full --offline` end-to-end
