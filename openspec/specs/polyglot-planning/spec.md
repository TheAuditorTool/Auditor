# polyglot-planning Specification

## Purpose
TBD - created by archiving change add-polyglot-planning. Update Purpose after archive.
## Requirements
### Requirement: Go Naming Convention Analysis

The system SHALL analyze Go source files for naming convention patterns in `aud blueprint --structure` output.

Go naming conventions detected:
- Functions: snake_case (private), PascalCase (exported)
- Structs: PascalCase (exported), lowercase (private)
- Variables: camelCase (common), snake_case (acceptable)

#### Scenario: Go functions analyzed for naming patterns

- **WHEN** `aud blueprint --structure` runs on a repository with `.go` files
- **THEN** output includes a `"go"` key in the naming conventions section
- **AND** `"go.functions"` shows snake_case/camelCase/PascalCase breakdown
- **AND** `"go.structs"` shows naming pattern breakdown for struct definitions

#### Scenario: Empty Go codebase handled gracefully

- **WHEN** `aud blueprint --structure` runs on a repository with no `.go` files
- **THEN** `"go"` key is present but shows empty results
- **AND** no error is raised

---

### Requirement: Rust Naming Convention Analysis

The system SHALL analyze Rust source files for naming convention patterns in `aud blueprint --structure` output.

Rust naming conventions detected:
- Functions: snake_case (standard)
- Structs: PascalCase (standard)
- Enums: PascalCase (standard)

#### Scenario: Rust functions analyzed for naming patterns

- **WHEN** `aud blueprint --structure` runs on a repository with `.rs` files
- **THEN** output includes a `"rust"` key in the naming conventions section
- **AND** `"rust.functions"` shows snake_case/camelCase/PascalCase breakdown
- **AND** `"rust.structs"` shows naming pattern breakdown for struct definitions

#### Scenario: Empty Rust codebase handled gracefully

- **WHEN** `aud blueprint --structure` runs on a repository with no `.rs` files
- **THEN** `"rust"` key is present but shows empty results
- **AND** no error is raised

---

### Requirement: Bash Naming Convention Analysis

The system SHALL analyze Bash source files for naming convention patterns in `aud blueprint --structure` output.

Bash naming conventions detected:
- Functions: snake_case (standard), SCREAMING_CASE (for constants)
- No class/struct concept in Bash

#### Scenario: Bash functions analyzed for naming patterns

- **WHEN** `aud blueprint --structure` runs on a repository with `.sh` files
- **THEN** output includes a `"bash"` key in the naming conventions section
- **AND** `"bash.functions"` shows snake_case/camelCase/SCREAMING_CASE breakdown
- **AND** no `"bash.classes"` key exists (Bash has no class concept)

#### Scenario: Empty Bash codebase handled gracefully

- **WHEN** `aud blueprint --structure` runs on a repository with no `.sh` files
- **THEN** `"bash"` key is present but shows empty results
- **AND** no error is raised

---

### Requirement: Cargo Dependency Analysis

The system SHALL include Rust Cargo.toml dependencies in `aud blueprint --deps` output.

#### Scenario: Cargo.toml dependencies surfaced

- **WHEN** `aud blueprint --deps` runs on a repository with `Cargo.toml`
- **THEN** output includes `"cargo"` in `by_manager` breakdown
- **AND** `workspaces` list includes entry with `"manager": "cargo"`
- **AND** packages list includes Cargo dependencies with versions

#### Scenario: Cargo workspace with multiple crates

- **WHEN** `aud blueprint --deps` runs on a Cargo workspace
- **THEN** each crate's `Cargo.toml` is listed separately in workspaces
- **AND** total dependency count aggregates all crates

#### Scenario: No Cargo.toml present

- **WHEN** `aud blueprint --deps` runs on a repository without `Cargo.toml`
- **THEN** `"cargo"` key is absent from `by_manager`
- **AND** no error is raised

---

### Requirement: Go Module Dependency Analysis

The system SHALL include Go go.mod dependencies in `aud blueprint --deps` output.

#### Scenario: go.mod dependencies surfaced

- **WHEN** `aud blueprint --deps` runs on a repository with `go.mod`
- **THEN** output includes `"go"` in `by_manager` breakdown
- **AND** `workspaces` list includes entry with `"manager": "go"`
- **AND** packages list includes Go module dependencies with versions

#### Scenario: Go module with replace directives

- **WHEN** `aud blueprint --deps` runs on a go.mod with `replace` directives
- **THEN** replaced modules show the replacement path/version
- **AND** original module path is preserved for reference

#### Scenario: No go.mod present

- **WHEN** `aud blueprint --deps` runs on a repository without `go.mod`
- **THEN** `"go"` key is absent from `by_manager`
- **AND** no error is raised

---

### Requirement: Go Handler Detection in Explain

The system SHALL detect Go web framework handlers in `aud explain <file.go>` output.

Supported frameworks: gin, echo, chi, fiber, net/http

#### Scenario: Gin handler detected

- **WHEN** `aud explain api/handlers.go` runs on a file with gin handlers
- **THEN** output includes `"framework": "gin"` in framework info
- **AND** handler functions with `*gin.Context` parameter are listed
- **AND** each handler shows function name and line number

#### Scenario: Echo handler detected

- **WHEN** `aud explain` runs on a file with echo handlers
- **THEN** output includes `"framework": "echo"` in framework info
- **AND** handler functions with `echo.Context` parameter are listed

#### Scenario: Standard net/http handler detected

- **WHEN** `aud explain` runs on a file with net/http handlers
- **THEN** output includes `"framework": "net/http"` in framework info
- **AND** functions matching `func(w http.ResponseWriter, r *http.Request)` pattern are listed

#### Scenario: No Go handlers in file

- **WHEN** `aud explain` runs on a `.go` file without handler patterns
- **THEN** framework info section is empty or absent
- **AND** other file context (symbols, imports, calls) is still shown

---

### Requirement: Rust Handler Detection in Explain

The system SHALL detect Rust web framework handlers in `aud explain <file.rs>` output.

Supported frameworks: actix-web, axum, rocket, warp

#### Scenario: Actix-web handler detected

- **WHEN** `aud explain src/routes.rs` runs on a file with actix-web handlers
- **THEN** output includes `"framework": "actix-web"` in framework info
- **AND** functions with `#[get]`, `#[post]` attributes are listed as handlers
- **AND** each handler shows route path if present in attribute

#### Scenario: Axum handler detected

- **WHEN** `aud explain` runs on a file with axum handlers
- **THEN** output includes `"framework": "axum"` in framework info
- **AND** functions with axum extractor parameters (`Json<T>`, `Path<T>`) are listed

#### Scenario: Rocket handler detected

- **WHEN** `aud explain` runs on a file with rocket handlers
- **THEN** output includes `"framework": "rocket"` in framework info
- **AND** functions with `#[get("/path")]`, `#[post("/path")]` macros are listed

#### Scenario: No Rust handlers in file

- **WHEN** `aud explain` runs on a `.rs` file without handler patterns
- **THEN** framework info section is empty or absent
- **AND** other file context (symbols, imports, calls) is still shown

