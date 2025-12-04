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

- [x] 1.1 Create `theauditor/package_managers/__init__.py` with registry pattern
- [x] 1.2 Create `theauditor/package_managers/base.py` with `BasePackageManager` abstract class
  - Methods: `parse_manifest()`, `fetch_latest_async()`, `fetch_docs_async()`, `upgrade_file()`
  - Properties: `manager_name`, `file_patterns`, `registry_url`

## 2. Docker Extraction

- [x] 2.1 Create `theauditor/package_managers/docker.py` extending BasePackageManager
- [x] 2.2 Extract `_parse_docker_compose()` from deps.py -> `parse_manifest()` for compose files
- [x] 2.3 Extract `_parse_dockerfile()` from deps.py -> `parse_manifest()` for Dockerfiles
- [x] 2.4 Extract `_fetch_docker_async()` from deps.py -> `fetch_latest_async()`
- [x] 2.5 Extract `_parse_docker_tag()` from deps.py -> private `_parse_docker_tag()`
- [x] 2.6 Extract `_extract_base_preference()` from deps.py -> private `_extract_base_preference()`
- [x] 2.7 Extract `_upgrade_docker_compose()` from deps.py -> `upgrade_file()` for compose
- [x] 2.8 Extract `_upgrade_dockerfile()` from deps.py -> `upgrade_file()` for Dockerfiles
- [x] 2.9 Update deps.py imports and wiring:
  - Add `from theauditor.package_managers import get_manager` at line ~18
  - Replace Docker parsing to use docker_mgr.parse_manifest()
  - Replace Docker version fetch to use docker_mgr.fetch_latest_async()
  - Replace Docker upgrade to use docker_mgr.upgrade_file()
- [x] 2.10 Delete extracted functions from deps.py (405 lines removed, now 1284 lines)
- [x] 2.11 Verify: docker-compose.yml parsing works (tested: 2 deps found)
- [x] 2.12 Verify: Docker Hub fetch_latest_async works (tested: nginx 1.24 -> 1.29.3)
- [x] 2.13 Verify: Docker upgrade_file works (tested: both images upgraded)

## 3. Cargo/Rust Support

- [x] 3.1 Create `theauditor/package_managers/cargo.py` extending BasePackageManager
- [x] 3.2 Implement `parse_manifest()` for Cargo.toml
- [x] 3.3 Implement `fetch_latest_async()` using crates.io API
  - Endpoint: `https://crates.io/api/v1/crates/{name}`
  - Parse `data["crate"]["max_version"]` for stable
  - User-Agent header: `TheAuditor/{__version__} (dependency checker)`
- [x] 3.4 Implement `fetch_docs_async()` using crates.io API `readme` field + GitHub
  - Primary: `data["crate"]["readme"]` from crates.io
  - Secondary: GitHub README via `data["crate"]["repository"]`
- [x] 3.5 Implement `upgrade_file()` for Cargo.toml using regex
  - Pattern 1: `name = "version"` simple string
  - Pattern 2: `name = { version = "..." }` table format
- [x] 3.6 Add rate limiter constant `RATE_LIMIT_CARGO = 1.0` to rate_limiter.py
- [x] 3.7 Add "cargo" to `delays` dict in `get_rate_limiter()`
- [x] 3.8 Wire cargo version check in deps.py
- [x] 3.9 Wire cargo docs in docs_fetch.py

## 4. Go Support

- [x] 4.1 Create `theauditor/package_managers/go.py` extending BasePackageManager
- [x] 4.2 Implement `parse_manifest()` for go.mod
  - Parse `module` directive for module path
  - Parse `require (...)` block with regex
  - Parse single-line `require module version` statements
- [x] 4.3 Implement `_encode_go_module()` helper for proxy URL encoding
  - Uppercase letters become `!lowercase` (e.g., `Azure` -> `!azure`)
- [x] 4.4 Implement `fetch_latest_async()` using Go proxy
  - Endpoint: `https://proxy.golang.org/{encoded_module}/@latest`
  - Parse `data["Version"]` from JSON response
- [x] 4.5 Implement `fetch_docs_async()` using pkg.go.dev
  - Endpoint: `https://pkg.go.dev/{module}@{version}`
  - Extract Documentation section using regex
  - Convert HTML to markdown
- [x] 4.6 Implement `upgrade_file()` for go.mod using regex
- [x] 4.7 Add rate limiter constant `RATE_LIMIT_GO = 0.5` to rate_limiter.py
- [x] 4.8 Add "go" to `delays` dict in `get_rate_limiter()`
- [x] 4.9 Wire go parsing in deps.py (go.mod discovery loop)
- [x] 4.10 Wire go version check in deps.py
- [x] 4.11 Wire go docs in docs_fetch.py

## 5. Manifest Extractor (DB Storage)

- [x] 5.1 Add `_extract_cargo_toml()` to manifest_extractor.py
- [x] 5.2 Add `_extract_go_mod()` to manifest_extractor.py
- [x] 5.3 Update `should_extract()` to match Cargo.toml and go.mod
- [x] 5.4 Add `add_cargo_package_config()` and `add_cargo_dependency()` to rust_database.py
- [x] 5.5 Add `add_go_module_config()` and `add_go_module_dependency()` to go_database.py
- [x] 5.6 Add table schemas (cargo_package_configs, cargo_dependencies, go_module_configs, go_module_dependencies)

## 6. Logging/UI Fixes

- [x] 6.1 Add `from theauditor.utils.logging import logger` to docs_fetch.py
- [x] 6.2 Add cargo/go to ALLOWLIST_URLS in docs_fetch.py
- [x] 6.3 Wire cargo/go dispatch in docs_fetch.py

## 7. Testing & Validation

- [x] 7.1 Test: Package managers registry loads 3 managers (docker, cargo, go)
- [x] 7.2 Test: deps.py imports correctly
- [x] 7.3 Test: docs_fetch.py imports correctly
- [x] 7.4 Test: Rate limiters configured (cargo=1.0s, go=0.5s)
- [x] 7.5 Test: Database methods exist (add_cargo_*, add_go_module_*)
- [x] 7.6 Test: ManifestExtractor handles Cargo.toml and go.mod
- [x] 7.7 Test: Schema tables created
- [x] 7.8 Test: Docker functionality unchanged after extraction

## 8. Post-Implementation Audit

- [x] 8.1 Re-read deps.py - confirmed 1284 lines, no Docker functions
- [x] 8.2 Verify no ZERO FALLBACK violations - GitHub is legitimate source, not fallback
- [x] 8.3 Verify no emojis in Python output - using [OK] and ->
- [x] 8.4 Run `aud full --offline` end-to-end (PASSED - storage handlers wired)

## Notes

- deps.py reduced from 1689 to 1284 lines (405 lines extracted to docker.py)
- Fixed pre-existing bug in docker.py `_parse_dockerfile()` with relative paths
- Storage handlers for cargo/go were missing - added to rust_storage.py and go_storage.py
- `aud full --offline` now completes successfully (all 22 phases pass)
