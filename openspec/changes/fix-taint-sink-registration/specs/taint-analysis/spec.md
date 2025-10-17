## MODIFIED Requirements

### Requirement: Sink Pattern Registration
Rules MAY register sink patterns via `register_taint_patterns(registry)`. Patterns MUST represent code-level constructs (function calls, method invocations, property accesses), NOT domain-level concepts (URL paths, keywords, categories).

**Validation Rules**:
1. Pattern length SHALL be ≥4 characters (unless uppercase acronym like SQL, XSS)
2. Pattern SHOULD NOT match common variable names (user, token, password, admin, config, key, secret, data, result, value)
3. Pattern SHOULD include object qualifiers when language-specific (e.g., `db.query` not `query`)
4. Registry SHALL log warnings for patterns failing validation rules
5. Registry MAY reject patterns in strict mode (opt-in via `--strict-registry`)

#### Scenario: Valid function pattern registration
- **GIVEN** a rule implementing `register_taint_patterns()`
- **WHEN** calling `registry.register_sink("executeQuery", "sql", "java")`
- **THEN** pattern is registered without warnings
- **AND** taint analyzer matches `symbols` table entries with name="executeQuery"

#### Scenario: Invalid generic pattern registration
- **GIVEN** a rule implementing `register_taint_patterns()`
- **WHEN** calling `registry.register_sink("user", "sensitive_operation", "api")`
- **THEN** registry logs warning: "Sink pattern 'user' matches common variable name"
- **AND** pattern is registered (warning only, not error)
- **AND** in strict mode (`--strict-registry`), registration fails

#### Scenario: URL pattern rejected for taint sinks
- **GIVEN** api_auth_analyze.py rule
- **WHEN** rule has `SENSITIVE_OPERATIONS = frozenset(['user', 'admin', 'token'])`
- **THEN** these patterns MUST NOT be passed to `registry.register_sink()`
- **AND** these patterns SHALL only be used for endpoint detection (database queries on `api_endpoints` table)

## ADDED Requirements

### Requirement: Pattern Validation at Registration
The registry SHALL validate sink patterns at registration time, providing immediate feedback to rule authors.

**Validation Checks**:
1. **Length check**: Patterns <4 chars trigger warning (unless uppercase)
2. **Common name check**: Patterns matching COMMON_VARIABLE_NAMES frozenset trigger warning
3. **Naming convention check**: Patterns without camelCase/snake_case/dot notation trigger warning
4. **Language consistency**: Patterns should match language parameter (e.g., Python patterns use snake_case)

**Feedback Mechanism**:
- **Warning level** (default): Log warning, allow registration
- **Error level** (strict mode): Log error, reject registration
- **Context**: Include rule file, line number, category in log message

#### Scenario: Registry warns on short pattern
- **GIVEN** registry in default mode
- **WHEN** `registry.register_sink("id", "sensitive_operation", "api")`
- **THEN** registry logs: "Sink pattern 'id' is very short (category=sensitive_operation)"
- **AND** pattern is registered
- **AND** taint analyzer uses pattern normally

#### Scenario: Strict mode rejects invalid pattern
- **GIVEN** registry with `--strict-registry` enabled
- **WHEN** `registry.register_sink("token", "sensitive_operation", "api")`
- **THEN** registry logs: "REJECTED: Sink pattern 'token' matches common variable name"
- **AND** registration fails (pattern NOT added to registry)
- **AND** taint analyzer never sees pattern

### Requirement: Rule Pattern Audit
All rules with `register_taint_patterns()` method MUST pass pattern validation audit.

**Audit Criteria**:
1. Patterns represent code-level constructs (functions, methods, properties)
2. Patterns do NOT represent domain concepts (URLs, keywords, categories)
3. Patterns have language-appropriate naming (camelCase for JS, snake_case for Python)
4. Patterns have unit test coverage

**Audit Process**:
1. Grep for all `register_taint_patterns` implementations
2. For each rule, verify patterns pass validation rules
3. Document findings in `audit_taint_patterns.md`
4. Fix violations or suppress with justification

#### Scenario: Successful audit completion
- **GIVEN** 22 rules with `register_taint_patterns()`
- **WHEN** audit script runs on all rules
- **THEN** each rule's patterns are validated
- **AND** violations are documented with severity (critical/warning/info)
- **AND** critical violations block merge
- **AND** audit report shows pass/fail/skip status per rule

## MODIFIED Requirements

### Requirement: API Auth Pattern Usage
The api_auth_analyze.py rule SHALL use SENSITIVE_OPERATIONS patterns for endpoint detection ONLY, NOT for taint sink registration.

**Pattern Sets**:
1. `SENSITIVE_URL_PATTERNS` - Used for querying `api_endpoints` table (existing behavior)
2. `SENSITIVE_FUNCTIONS` - Used for `register_taint_patterns()` (NEW, may be empty if no relevant patterns)

**Rationale**: URL path segments are not equivalent to variable/function names. Taint analysis tracks data flow through code constructs, not domain concepts.

#### Scenario: Endpoint detection uses URL patterns
- **GIVEN** api_auth_analyze.py rule
- **WHEN** rule queries `SELECT * FROM api_endpoints WHERE path LIKE '%/user%'`
- **THEN** SENSITIVE_URL_PATTERNS is used (contains "user", "admin", "token")
- **AND** findings report missing authentication on `/user` endpoint

#### Scenario: Taint registration uses function patterns
- **GIVEN** api_auth_analyze.py rule
- **WHEN** `register_taint_patterns()` is called
- **THEN** SENSITIVE_FUNCTIONS is used (may be empty set)
- **AND** only function/method patterns are registered as sinks
- **AND** NO URL patterns like "user"/"token"/"admin" are registered

#### Scenario: Pattern separation prevents false positives
- **GIVEN** code with `const user = req.body.name;`
- **WHEN** taint analysis runs
- **THEN** "user" variable is NOT treated as sink (not in SENSITIVE_FUNCTIONS)
- **AND** no false positive reported for `req.body → user` flow
