## ADDED Requirements

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
