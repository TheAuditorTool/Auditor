# Specification: Package Managers

## ADDED Requirements

### Requirement: Package Manager Registry

The system SHALL provide a centralized registry for package manager implementations that routes operations by manager name.

#### Scenario: Get manager by name
- **WHEN** `get_manager("cargo")` is called
- **THEN** return a `CargoPackageManager` instance

#### Scenario: Unknown manager
- **WHEN** `get_manager("unknown")` is called
- **THEN** return `None`

#### Scenario: Get all managers
- **WHEN** `get_all_managers()` is called
- **THEN** return list of all registered package manager instances

---

### Requirement: Base Package Manager Interface

The system SHALL define an abstract base class `BasePackageManager` that all package manager implementations MUST inherit from.

#### Scenario: Required properties
- **WHEN** a class inherits from `BasePackageManager`
- **THEN** it MUST implement `manager_name` property returning a string identifier
- **AND** it MUST implement `file_patterns` property returning list of glob patterns

#### Scenario: Required methods
- **WHEN** a class inherits from `BasePackageManager`
- **THEN** it MUST implement `parse_manifest(path)` returning list of dependency dicts
- **AND** it MUST implement `fetch_latest_async(client, dep)` returning version string or None
- **AND** it MUST implement `fetch_docs_async(client, dep, output_path, allowlist)` returning status string
- **AND** it MUST implement `upgrade_file(path, latest_info, deps)` returning upgrade count

---

### Requirement: Docker Package Manager

The system SHALL provide a Docker package manager implementation that handles Docker Compose and Dockerfile base images.

#### Scenario: Parse docker-compose.yml
- **WHEN** `parse_manifest()` is called with a docker-compose.yml path
- **THEN** return list of dependency dicts with `manager: "docker"` for each service image

#### Scenario: Parse Dockerfile
- **WHEN** `parse_manifest()` is called with a Dockerfile path
- **THEN** return list of dependency dicts for each FROM instruction
- **AND** skip `scratch` and build stage references

#### Scenario: Fetch latest Docker tag
- **WHEN** `fetch_latest_async()` is called with a Docker dependency
- **THEN** query Docker Hub API for available tags
- **AND** return latest stable tag matching current tag's base variant (alpine, slim, etc.)

#### Scenario: Upgrade docker-compose.yml
- **WHEN** `upgrade_file()` is called with docker-compose.yml
- **THEN** create versioned backup
- **AND** update image tags to latest versions
- **AND** return count of images upgraded

#### Scenario: Upgrade Dockerfile
- **WHEN** `upgrade_file()` is called with Dockerfile
- **THEN** create versioned backup
- **AND** update FROM instructions to latest versions
- **AND** preserve AS clauses for multi-stage builds
- **AND** return count of images upgraded

---

### Requirement: Cargo Package Manager

The system SHALL provide a Cargo package manager implementation that handles Rust Cargo.toml files.

#### Scenario: Parse Cargo.toml
- **WHEN** `parse_manifest()` is called with a Cargo.toml path
- **THEN** return list of dependency dicts with `manager: "cargo"`
- **AND** include dependencies from `[dependencies]` section
- **AND** include dev-dependencies from `[dev-dependencies]` section with `dev: true`
- **AND** handle workspace dependencies with `workspace: true` marker

#### Scenario: Fetch latest crate version
- **WHEN** `fetch_latest_async()` is called with a Cargo dependency
- **THEN** query crates.io API at `https://crates.io/api/v1/crates/{name}`
- **AND** return `crate.max_version` for stable version
- **AND** respect 1-second rate limit

#### Scenario: Fetch crate documentation
- **WHEN** `fetch_docs_async()` is called with a Cargo dependency
- **THEN** fetch README from crates.io API `data["crate"]["readme"]` field (same endpoint as version check)
- **AND** if readme is null, return "skipped" (NO FALLBACK to GitHub)
- **AND** save to output directory as markdown
- **AND** return "fetched", "cached", "skipped", or "error"

#### Scenario: Upgrade Cargo.toml
- **WHEN** `upgrade_file()` is called with Cargo.toml
- **THEN** create versioned backup
- **AND** update version strings in `[dependencies]` and `[dev-dependencies]`
- **AND** skip workspace dependencies
- **AND** return count of dependencies upgraded

---

### Requirement: Go Package Manager

The system SHALL provide a Go package manager implementation that handles go.mod files.

#### Scenario: Parse go.mod
- **WHEN** `parse_manifest()` is called with a go.mod path
- **THEN** return list of dependency dicts with `manager: "go"`
- **AND** parse `require` block for dependencies
- **AND** parse single-line `require` statements
- **AND** include module path and version for each dependency

#### Scenario: Fetch latest Go module version
- **WHEN** `fetch_latest_async()` is called with a Go dependency
- **THEN** encode module path per Go proxy spec (uppercase to !lowercase)
- **AND** query Go proxy at `https://proxy.golang.org/{encoded_module}/@latest`
- **AND** return `Version` field from JSON response
- **AND** respect 0.5-second rate limit

#### Scenario: Fetch Go module documentation
- **WHEN** `fetch_docs_async()` is called with a Go dependency
- **THEN** fetch documentation from pkg.go.dev at `https://pkg.go.dev/{module}@{version}`
- **AND** extract Documentation section using regex (single code path, NO FALLBACKS)
- **AND** convert HTML to markdown format
- **AND** save to output directory
- **AND** return "fetched", "cached", "skipped", or "error"

#### Scenario: Upgrade go.mod
- **WHEN** `upgrade_file()` is called with go.mod
- **THEN** create versioned backup
- **AND** update version strings in require block
- **AND** update single-line require statements
- **AND** return count of modules upgraded

---

### Requirement: Rate Limiting for Package Registries

The system SHALL enforce rate limits for package registry API calls.

#### Scenario: Cargo rate limit
- **WHEN** making requests to crates.io
- **THEN** enforce minimum 1 second between requests

#### Scenario: Go rate limit
- **WHEN** making requests to proxy.golang.org
- **THEN** enforce minimum 0.5 seconds between requests

#### Scenario: Rate limiter reuse
- **WHEN** multiple calls use same registry
- **THEN** share rate limiter instance via `get_rate_limiter(service)`

---

### Requirement: Manifest Extraction to Database

The system SHALL extract Cargo.toml and go.mod manifests to the database during indexing.

#### Scenario: Extract Cargo.toml to database
- **WHEN** indexer encounters Cargo.toml file
- **THEN** store package config to `cargo_package_configs` table
- **AND** store dependencies to `cargo_dependencies` table
- **AND** include package name, version, edition
- **AND** include dependency name, version spec, is_dev flag, features

#### Scenario: Extract go.mod to database
- **WHEN** indexer encounters go.mod file
- **THEN** store module config to `go_module_configs` table
- **AND** store dependencies to `go_module_dependencies` table
- **AND** include module path, go version
- **AND** include dependency module path, version, is_indirect flag

---

### Requirement: Logging Infrastructure Compliance

The system SHALL use centralized logging and UI infrastructure.

#### Scenario: Use loguru logger
- **WHEN** any package manager module needs to log
- **THEN** import from `theauditor.utils.logging import logger`
- **AND** use `logger.info()`, `logger.error()`, etc.
- **AND** NEVER create local `logging.getLogger()` instances

#### Scenario: Use Rich console
- **WHEN** any package manager module needs CLI output
- **THEN** import from `theauditor.pipeline.ui import console`
- **AND** use `console.print()` for user-facing output

#### Scenario: No emojis in output
- **WHEN** generating any output strings
- **THEN** use ASCII-only characters
- **AND** use `[OK]`, `[FAIL]`, `->` instead of emojis
