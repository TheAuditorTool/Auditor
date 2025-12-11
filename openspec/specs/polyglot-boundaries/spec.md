# polyglot-boundaries Specification

## Purpose
TBD - created by archiving change add-polyglot-planning. Update Purpose after archive.
## Requirements
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

### Requirement: Validation Chain Tracing

The system SHALL trace validation through the data flow from entry point to terminal operation, detecting where type safety breaks.

Chain status values:
- `intact`: Validation exists at entry AND type preserved through all hops
- `broken`: Validation exists but type safety lost at intermediate hop (cast to `any`, type assertion)
- `no_validation`: No validation detected at entry point

Chain break detection patterns:
- TypeScript: `as any`, `: any`, `as unknown`, missing generic after typed
- Python: Missing type hint after typed parameter, `# type: ignore`
- Go: `interface{}` after typed struct, unguarded type assertion
- Rust: `.unwrap()` discarding Result type information

Type detection data sources (language-specific):
- **TypeScript/JavaScript**: Query `type_annotations` table, use regex on `type_annotation` column
- **Python**: Query `type_annotations` table, use regex on `type_annotation` column
- **Go/Rust**: Query `symbols.type_annotation`, use regex

**ZERO FALLBACK DECISION**: The `type_annotations.is_any` flag is unreliable. Detection uses regex pattern matching ONLY with word boundaries:
- `r':\s*any\b'` (type annotation)
- `r'\bas\s+any\b'` (cast)
- `r'<\s*any\s*>'` (generic)
- Exclusions: `z.any()`, `Joi.any()` (validation sources, not breaks)

#### Scenario: Intact validation chain detected

- **WHEN** `aud boundaries --validated` runs on a codebase
- **AND** entry point has Zod/Joi/Pydantic validation
- **AND** type is preserved through all downstream function calls
- **THEN** chain status is "intact"
- **AND** each hop shows "[PASS] Type preserved"

#### Scenario: Broken validation chain detected

- **WHEN** `aud boundaries --validated` runs on a codebase
- **AND** entry point has validation
- **AND** intermediate function casts parameter to `any`
- **THEN** chain status is "broken"
- **AND** break hop shows "[FAIL] Cast to any"
- **AND** break_index indicates which hop broke the chain

#### Scenario: No validation chain detected

- **WHEN** `aud boundaries --validated` runs on a codebase
- **AND** entry point has no validation library call
- **THEN** chain status is "no_validation"
- **AND** first hop shows "[FAIL] No validation at entry"

#### Scenario: Type safety break detected via regex pattern

- **WHEN** `aud boundaries --validated` traces through a TypeScript function
- **AND** `type_annotations.type_annotation` matches regex `r':\s*any\b'` or `r'<\s*any\s*>'`
- **THEN** chain status is "broken"
- **AND** break hop shows "[FAIL] Type contains any"

#### Scenario: Validation source any is NOT a break

- **WHEN** `aud boundaries --validated` traces through a TypeScript function
- **AND** `type_annotations.type_annotation` contains `z.any()` or `Joi.any()`
- **THEN** chain status is NOT broken by this (it's a validation source)
- **AND** chain continues tracing downstream

---

### Requirement: Validation Chain Visualization

The system SHALL output validation chains in a visual format that teaches developers where validation fails.

Output format:
```
POST /users (body: CreateUserInput)
    | [PASS] Zod validated at entry
    v
userService.create(data: CreateUserInput)
    | [PASS] Type preserved
    v
repo.insert(data: any)        <- CHAIN BROKEN
    | [FAIL] Cast to any - validation meaningless now
    v
db.query(sql)                 <- Unvalidated data hits DB
```

Format rules:
- Vertical flow with `|` and `v` characters
- `[PASS]` for preserved type, `[FAIL]` for broken/missing
- `<- CHAIN BROKEN` annotation at break point
- ASCII only (no emojis for Windows CP1252 compatibility)

#### Scenario: Visual chain output for intact chain

- **WHEN** `aud boundaries --validated` outputs an intact chain
- **THEN** all hops show `[PASS]`
- **AND** no `<- CHAIN BROKEN` annotation appears

#### Scenario: Visual chain output for broken chain

- **WHEN** `aud boundaries --validated` outputs a broken chain
- **THEN** hops before break show `[PASS]`
- **AND** break hop shows `[FAIL]` with reason
- **AND** `<- CHAIN BROKEN` annotation appears on break line
- **AND** subsequent hops show impact (e.g., "Unvalidated data hits DB")

---

### Requirement: Security Boundary Audit

The system SHALL provide comprehensive trust boundary audit via `aud boundaries --audit` flag.

Audit categories:
- INPUT BOUNDARIES: Entry points with/without validation (Zod, Joi, Yup, Pydantic)
- OUTPUT BOUNDARIES: Response points with/without sanitization (XSS prevention)
- DATABASE BOUNDARIES: Query points with/without parameterization (SQLi prevention)
- FILE BOUNDARIES: File operations with/without path validation (traversal prevention)

Output format:
```
INPUT BOUNDARIES:
  POST /users      [PASS] Zod schema validates body
  GET /users/:id   [FAIL] No param validation

OUTPUT BOUNDARIES:
  renderUser()     [PASS] HTML escaped via React
  emailTemplate()  [FAIL] Raw HTML interpolation (XSS risk)

DATABASE BOUNDARIES:
  User.create()    [PASS] Prisma parameterized
  rawQuery()       [FAIL] String concat (SQLi risk)

FILE BOUNDARIES:
  uploadFile()     [FAIL] No path traversal check
```

#### Scenario: Input boundary audit finds missing validation

- **WHEN** `aud boundaries --audit` runs on a codebase
- **AND** an API endpoint accepts user input without validation
- **THEN** INPUT BOUNDARIES section shows `[FAIL]` for that endpoint
- **AND** observation explains "No param validation" or similar

#### Scenario: Output boundary audit finds XSS risk

- **WHEN** `aud boundaries --audit` runs on a codebase
- **AND** a function outputs user data without HTML escaping
- **THEN** OUTPUT BOUNDARIES section shows `[FAIL]` for that function
- **AND** observation explains "Raw HTML interpolation (XSS risk)"

#### Scenario: Database boundary audit finds SQLi risk

- **WHEN** `aud boundaries --audit` runs on a codebase
- **AND** a function constructs SQL via string concatenation
- **THEN** DATABASE BOUNDARIES section shows `[FAIL]` for that function
- **AND** observation explains "String concat (SQLi risk)"

---

### Requirement: Explain Command Validated Flag

The system SHALL support `--validated` flag on `aud explain` command to show validation chain status for entry points in a file.

#### Scenario: Explain with validated flag shows chain status

- **WHEN** `aud explain src/routes/users.ts --validated` runs
- **AND** the file contains API endpoints
- **THEN** output includes VALIDATION CHAINS section
- **AND** each entry point shows chain status (intact/broken/no_validation)
- **AND** broken chains show which hop broke the chain

---

### Requirement: Blueprint Command Validated Flag

The system SHALL support `--validated` flag on `aud blueprint` command to show codebase-wide validation chain health.

Output format:
```
VALIDATION CHAIN HEALTH:
  Entry Points: 47
  Chains Intact: 31 (66%)
  Chains Broken: 12 (26%)
  No Validation: 4 (8%)

  Top Break Reasons:
    - Cast to any: 8
    - Untyped intermediate: 3
    - Type assertion: 1
```

#### Scenario: Blueprint validated shows chain health summary

- **WHEN** `aud blueprint --validated` runs on a codebase
- **THEN** output shows total entry points count
- **AND** shows breakdown by chain status (intact/broken/no_validation)
- **AND** shows percentages for each status
- **AND** shows top reasons for chain breaks

---

### Requirement: Polyglot Validation Library Detection

The system SHALL detect validation libraries across supported languages.

| Language | Validation Libraries | Entry Point Table | Type Info Table |
|----------|---------------------|-------------------|-----------------|
| TypeScript/JavaScript | Zod, Joi, Yup, io-ts, runtypes, class-validator | `express_middleware_chains` (NOT `js_routes` - doesn't exist) | `type_annotations` |
| Python | Pydantic, marshmallow, cerberus, voluptuous | `python_routes` | `type_annotations` or `symbols` |
| Go | go-playground/validator, ozzo-validation | `go_routes` | `symbols` |
| Rust | validator crate, garde | `rust_attributes` | `symbols` |

#### Scenario: Zod validation detected in TypeScript

- **WHEN** `aud boundaries --validated` analyzes TypeScript code
- **AND** entry point uses `z.object().parse()` or `.safeParse()`
- **THEN** validation is detected at entry
- **AND** chain tracing begins from validated type

#### Scenario: Pydantic validation detected in Python

- **WHEN** `aud boundaries --validated` analyzes Python code
- **AND** entry point parameter uses Pydantic model type hint
- **THEN** validation is detected at entry
- **AND** chain tracing begins from Pydantic model type

