# polyglot-deadcode Specification

## Purpose

Enable `aud deadcode` to detect isolated modules and unreachable code in Go, Rust, and Bash codebases by wiring polyglot entry point detection into the graph-based dead code analyzer.

## Current State (Hardcoded Python/JS)

`theauditor/context/deadcode_graph.py:237-268` only queries:
- `python_decorators` (route, get, post, etc.)
- `python_routes`
- `react_components`
- `vue_components`

**Missing:** Go routes, Rust handlers, Go/Rust main functions

---

## ADDED Requirements

### Requirement: Go Entry Point Detection for Deadcode

The system SHALL detect Go entry points to prevent false positives in `aud deadcode` output.

Go entry point patterns:
- Web handlers: Functions in `go_routes` table
- Main functions: `func main()` in `main` package
- CLI commands: Functions with cobra/urfave-cli patterns
- Test functions: `func Test*`, `func Benchmark*`

#### Scenario: Go web handler excluded from dead code

- **WHEN** `aud deadcode` runs on a repository with Go gin/echo handlers
- **THEN** files containing functions listed in `go_routes` are marked as entry points
- **AND** these files are NOT reported as dead code
- **AND** modules reachable from these entry points are also excluded

#### Scenario: Go main package excluded from dead code

- **WHEN** `aud deadcode` runs on a repository with `cmd/*/main.go` files
- **THEN** files with `package main` and `func main()` are marked as entry points
- **AND** confidence is "low" (external invocation)

#### Scenario: Go test files handled correctly

- **WHEN** `aud deadcode` runs on a repository with `*_test.go` files
- **THEN** test files are marked as entry points (invoked by `go test`)
- **AND** confidence is "medium" (test runner invocation)

---

### Requirement: Rust Entry Point Detection for Deadcode

The system SHALL detect Rust entry points to prevent false positives in `aud deadcode` output.

Rust entry point patterns:
- Web handlers: Functions with `#[get]`, `#[post]` attributes (actix-web, rocket)
- Main functions: `fn main()` in `main.rs` or `lib.rs`
- Binary crates: Files in `src/bin/*.rs`
- Test functions: `#[test]`, `#[tokio::test]`

#### Scenario: Rust web handler excluded from dead code

- **WHEN** `aud deadcode` runs on a repository with actix-web handlers
- **THEN** files containing functions with route attributes are marked as entry points
- **AND** these files are NOT reported as dead code

**DEPENDS ON:** `rust_attributes` table (BLOCKER 1 - Task 0.3)

#### Scenario: Rust main.rs excluded from dead code

- **WHEN** `aud deadcode` runs on a repository with `src/main.rs`
- **THEN** `main.rs` is marked as entry point
- **AND** `src/bin/*.rs` files are also marked as entry points

#### Scenario: Rust test modules handled correctly

- **WHEN** `aud deadcode` runs on a repository with `#[cfg(test)]` modules
- **THEN** test modules are marked as entry points
- **AND** confidence is "medium" (test runner invocation)

---

### Requirement: Bash Entry Point Detection for Deadcode

The system SHALL detect Bash entry points to prevent false positives in `aud deadcode` output.

Bash entry point patterns:
- Executable scripts: Files with shebang (`#!/bin/bash`, `#!/usr/bin/env bash`)
- Sourced libraries: Files sourced by other scripts (via `source` or `.`)

#### Scenario: Bash executable script excluded from dead code

- **WHEN** `aud deadcode` runs on a repository with `*.sh` files
- **THEN** files with shebang lines are marked as entry points
- **AND** these files are NOT reported as dead code

#### Scenario: Bash sourced library handled correctly

- **WHEN** `aud deadcode` runs and `utils.sh` is sourced by `deploy.sh`
- **THEN** `utils.sh` is reachable from `deploy.sh` entry point
- **AND** `utils.sh` is NOT reported as dead code

---

### Requirement: Graph Edge Population for Go/Rust/Bash

The system SHALL populate `graphs.db` with import/call edges from Go, Rust, and Bash files.

#### Scenario: Go import edges in graphs.db

- **WHEN** `aud graph build` runs on a repository with Go files
- **THEN** `edges` table contains Go import edges (type='import', graph_type='import')
- **AND** Go call edges are populated (type='call', graph_type='call')

#### Scenario: Rust use edges in graphs.db

- **WHEN** `aud graph build` runs on a repository with Rust files
- **THEN** `edges` table contains Rust `use` statement edges
- **AND** Rust function call edges are populated

#### Scenario: Bash source edges in graphs.db

- **WHEN** `aud graph build` runs on a repository with Bash files
- **THEN** `edges` table contains Bash `source`/`.` statement edges
- **AND** Bash function call edges are populated

---

## Implementation Location

**Primary file:** `theauditor/context/deadcode_graph.py`

**Functions to modify:**
- `_find_decorated_entry_points()` - Add Go/Rust attribute queries
- `_find_framework_entry_points()` - Add `go_routes`, `rust_attributes` queries
- `_find_entry_points()` - Add Go/Rust/Bash file pattern detection

**Tables to query:**
| Language | Entry Point Table | Column |
|----------|-------------------|--------|
| Go | `go_routes` | `file` |
| Go | `go_functions` | `file` (where name='main') |
| Rust | `rust_attributes` | `file_path` (where attribute_name in route attrs) |
| Rust | `rust_functions` | `file_path` (where name='main') |
| Bash | `bash_functions` | `file` (shebang detection via files table) |

---

## Verification Queries

After implementation, run these to verify:

```sql
-- Go entry points detected
SELECT COUNT(DISTINCT file) FROM go_routes;

-- Rust entry points detected (requires rust_attributes)
SELECT COUNT(DISTINCT file_path) FROM rust_attributes
WHERE attribute_name IN ('get', 'post', 'put', 'delete', 'route');

-- Graph edges for Go
SELECT COUNT(*) FROM edges WHERE source LIKE '%.go' AND graph_type = 'import';

-- Graph edges for Rust
SELECT COUNT(*) FROM edges WHERE source LIKE '%.rs' AND graph_type = 'import';
```
