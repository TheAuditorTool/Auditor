# polyglot-boundaries Specification

## Purpose

Enable `aud boundaries` to analyze security boundary enforcement in Go and Rust codebases by detecting entry points, control points, and measuring distance between them.

## Current State (Hardcoded Python/JS)

`aud boundaries` help text mentions:
- Entry Points: `python_routes`, `js_routes` (HTTP endpoints)
- Control Patterns: `validate()`, `parse()`, `check()`, `sanitize()`

**Missing:** Go routes, Rust handlers, Go/Rust validation patterns

---

## ADDED Requirements

### Requirement: Go Entry Point Detection for Boundaries

The system SHALL detect Go HTTP entry points in `aud boundaries` analysis.

Go entry point patterns:
- Gin: `r.GET("/path", handler)`, `r.POST("/path", handler)`
- Echo: `e.GET("/path", handler)`, `e.POST("/path", handler)`
- Chi: `r.Get("/path", handler)`, `r.Post("/path", handler)`
- Fiber: `app.Get("/path", handler)`, `app.Post("/path", handler)`
- net/http: `http.HandleFunc("/path", handler)`

#### Scenario: Gin route detected as entry point

- **WHEN** `aud boundaries --type input-validation` runs on a Go codebase
- **THEN** routes from `go_routes` table are detected as entry points
- **AND** entry_file shows the Go file path
- **AND** entry_line shows the route registration line

#### Scenario: Go handler parameter types analyzed

- **WHEN** `aud boundaries` analyzes a Go handler function
- **THEN** handler functions with `*gin.Context`, `echo.Context` are recognized
- **AND** distance calculation starts from handler function

---

### Requirement: Rust Entry Point Detection for Boundaries

The system SHALL detect Rust HTTP entry points in `aud boundaries` analysis.

Rust entry point patterns:
- Actix-web: `#[get("/path")]`, `#[post("/path")]` attributes
- Axum: Router definitions with handler functions
- Rocket: `#[get("/path")]`, `#[post("/path")]` macros
- Warp: Filter chain definitions

#### Scenario: Actix-web route detected as entry point

- **WHEN** `aud boundaries --type input-validation` runs on a Rust codebase
- **THEN** functions with route attributes from `rust_attributes` are entry points
- **AND** entry_file shows the Rust file path
- **AND** route path is extracted from attribute args

**DEPENDS ON:** `rust_attributes` table (BLOCKER 1 - Task 0.3)

#### Scenario: Axum handler detected as entry point

- **WHEN** `aud boundaries` analyzes an Axum router
- **THEN** handler functions referenced in Router definitions are entry points
- **AND** extractor types (`Json<T>`, `Path<T>`) are recognized as input sources

---

### Requirement: Go Validation Control Detection

The system SHALL detect Go validation patterns as control points.

Go validation patterns:
- Struct validators: `validator.Struct()`, `validate.Struct()`
- JSON binding: `c.ShouldBindJSON()`, `c.BindJSON()` (gin)
- Custom validators: Functions matching `validate*`, `check*`, `sanitize*`
- Error checking: `if err != nil` patterns after validation

#### Scenario: Gin binding detected as validation control

- **WHEN** `aud boundaries` analyzes a Go gin handler
- **THEN** `c.ShouldBindJSON(&req)` is detected as validation control
- **AND** distance is measured from route to binding call

#### Scenario: Go validator library detected

- **WHEN** `aud boundaries` analyzes Go code using `go-playground/validator`
- **THEN** `validator.Struct()` calls are detected as control points
- **AND** control pattern shows "struct_validation"

---

### Requirement: Rust Validation Control Detection

The system SHALL detect Rust validation patterns as control points.

Rust validation patterns:
- Serde validation: `#[validate]` derive macros
- Actix extractors: `web::Json<T>`, `web::Path<T>` (implicit validation)
- Custom validators: Functions matching `validate*`, `check*`
- Result handling: `?` operator after validation

#### Scenario: Actix extractor detected as validation control

- **WHEN** `aud boundaries` analyzes a Rust actix-web handler
- **THEN** `web::Json<CreateUser>` extractor is detected as validation control
- **AND** distance is 0 (validation at entry via type system)

#### Scenario: Validator derive macro detected

- **WHEN** `aud boundaries` analyzes Rust code with `#[derive(Validate)]`
- **THEN** structs with Validate derive are tracked
- **AND** `.validate()` calls on those structs are control points

---

### Requirement: Go Multi-Tenant Boundary Detection

The system SHALL detect Go multi-tenant isolation patterns.

Go multi-tenant patterns:
- Context tenant: `ctx.Value("tenant_id")`, middleware injection
- Query scoping: `WHERE tenant_id = ?` in SQL queries
- ORM scoping: GORM/sqlx scopes with tenant filter

#### Scenario: Go tenant middleware detected

- **WHEN** `aud boundaries --type multi-tenant` runs on a Go codebase
- **THEN** middleware functions that inject tenant_id are detected
- **AND** distance from entry to tenant check is measured

---

### Requirement: Rust Multi-Tenant Boundary Detection

The system SHALL detect Rust multi-tenant isolation patterns.

Rust multi-tenant patterns:
- Request extensions: `req.extensions().get::<TenantId>()`
- Middleware injection: Tower/actix middleware
- Query scoping: Diesel/sqlx queries with tenant filter

#### Scenario: Rust tenant extractor detected

- **WHEN** `aud boundaries --type multi-tenant` runs on a Rust codebase
- **THEN** extractors that provide TenantId are detected as control points
- **AND** database queries without tenant filter are flagged

---

## Implementation Location

**Primary file:** `theauditor/boundaries/boundary_analyzer.py`

**Functions to add/modify:**
- `analyze_input_validation_boundaries()` - Add Go/Rust route queries to entry point detection
- Add Go/Rust validation pattern detection to `VALIDATION_PATTERNS` or create language-specific lists
- `find_all_paths_to_controls()` in `distance.py` - Ensure call graph traversal works for Go/Rust

**Tables to query:**
| Language | Entry Point Table | Purpose |
|----------|-------------------|---------|
| Go | `go_routes` | HTTP route handlers |
| Go | `go_func_params` | Handler parameter types |
| Rust | `rust_attributes` | Route attribute detection |
| Rust | `rust_functions` | Handler function info |

**Control Pattern Tables:**
| Language | Table | Pattern |
|----------|-------|---------|
| Go | `function_calls` | `ShouldBindJSON`, `validator.Struct` |
| Go | `go_func_params` | Context parameter detection |
| Rust | `rust_macro_invocations` | Validation macro calls |
| Rust | `rust_attributes` | `#[validate]` derive detection |

---

## Verification Queries

After implementation, run these to verify:

```sql
-- Go entry points for boundaries
SELECT framework, method, path, handler_func, line
FROM go_routes
LIMIT 10;

-- Go validation patterns (function calls)
SELECT file, line, callee_name
FROM function_calls
WHERE callee_name LIKE '%Bind%' OR callee_name LIKE '%validate%'
LIMIT 10;

-- Rust entry points (requires rust_attributes)
SELECT file_path, attribute_name, args, target_name
FROM rust_attributes
WHERE attribute_name IN ('get', 'post', 'put', 'delete')
LIMIT 10;
```

---

## Output Format Extension

Current output includes Python/JS entries. Add Go/Rust:

```json
{
  "entry_point": "POST /api/users",
  "entry_file": "internal/handlers/users.go",
  "entry_line": 45,
  "language": "go",
  "framework": "gin",
  "controls": [
    {
      "control_function": "ShouldBindJSON",
      "control_file": "internal/handlers/users.go",
      "control_line": 48,
      "distance": 0,
      "pattern": "json_binding"
    }
  ],
  "quality": {
    "quality": "clear",
    "reason": "Validation at entry via ShouldBindJSON"
  }
}
```
