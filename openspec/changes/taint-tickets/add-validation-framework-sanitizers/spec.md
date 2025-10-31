# Taint Analysis Capability - Validation Framework Sanitizers

## MODIFIED Requirements

### Requirement: Sanitizer Detection
The taint analyzer SHALL recognize functions and methods that validate or sanitize data, stopping taint propagation when data passes through these sanitizers.

The system SHALL maintain a SANITIZERS dictionary with frozensets of known sanitization patterns, organized by category (sql, xss, path, command, validation, validation_frameworks).

The system SHALL check for sanitizers between taint sources and sinks using the `has_sanitizer_between()` function, which queries the symbols table for function calls matching known sanitizer patterns.

The system SHALL support modern validation frameworks (Zod, Joi, Yup, express-validator, class-validator, AJV) by recognizing their validation methods as sanitizers, including method-based APIs (`.parse`, `.validateAsync`, `validationResult`).

#### Scenario: Traditional sanitizer recognition
- **GIVEN** a taint source `req.body` at line 10
- **AND** a function call `sanitize(req.body)` at line 11
- **AND** a SQL sink `db.query(cleanData)` at line 12
- **WHEN** taint analysis executes
- **THEN** the sanitizer `sanitize` is recognized
- **AND** taint propagation stops at line 11
- **AND** no vulnerability is reported

#### Scenario: Zod validation method recognition
- **GIVEN** a taint source `req.body` at line 10
- **AND** a validation call `schema.parseAsync(req.body)` at line 11
- **AND** a SQL sink `db.query(validated)` at line 12
- **WHEN** taint analysis executes
- **THEN** the sanitizer `schema.parseAsync` is recognized
- **AND** taint propagation stops at line 11
- **AND** no vulnerability is reported

#### Scenario: Joi validation method recognition
- **GIVEN** a taint source `req.query` at line 10
- **AND** a validation call `schema.validateAsync(req.query)` at line 11
- **AND** an XSS sink `res.send(validated)` at line 12
- **WHEN** taint analysis executes
- **THEN** the sanitizer `schema.validateAsync` is recognized
- **AND** taint propagation stops at line 11
- **AND** no vulnerability is reported

#### Scenario: Yup validation method recognition
- **GIVEN** a taint source `req.params.id` at line 10
- **AND** a validation call `schema.validate(req.params.id)` at line 11
- **AND** a SQL sink `db.findById(validId)` at line 12
- **WHEN** taint analysis executes
- **THEN** the sanitizer `schema.validate` is recognized
- **AND** taint propagation stops at line 11
- **AND** no vulnerability is reported

#### Scenario: express-validator result extraction
- **GIVEN** a taint source `req.body` at line 10
- **AND** express-validator middleware has validated request
- **AND** a function call `matchedData(req)` at line 15
- **AND** a SQL sink `db.insert(cleanData)` at line 16
- **WHEN** taint analysis executes
- **THEN** the sanitizer `matchedData` is recognized
- **AND** taint propagation stops at line 15
- **AND** no vulnerability is reported

#### Scenario: Schema builder not recognized as sanitizer
- **GIVEN** a taint source `req.body` at line 10
- **AND** a schema construction `z.string()` at line 11
- **AND** a SQL sink `db.query(req.body)` at line 12
- **WHEN** taint analysis executes
- **THEN** the pattern `z.string()` is NOT recognized as a sanitizer
- **AND** taint propagation continues through line 11
- **AND** a vulnerability is reported (source line 10 → sink line 12)

#### Scenario: JSON.parse not recognized as sanitizer
- **GIVEN** a taint source `req.body` at line 10
- **AND** a deserialization call `JSON.parse(req.body)` at line 11
- **AND** a SQL sink `db.query(data.name)` at line 12
- **WHEN** taint analysis executes
- **THEN** the pattern `JSON.parse` is NOT recognized as a sanitizer
- **AND** taint propagation continues through line 11
- **AND** a vulnerability is reported (source line 10 → sink line 12)

#### Scenario: No sanitizer present (vulnerability detection)
- **GIVEN** a taint source `req.query.name` at line 10
- **AND** a SQL sink `db.execute(\`SELECT * FROM users WHERE name = '${req.query.name}'\`)` at line 11
- **AND** no sanitizer between lines 10 and 11
- **WHEN** taint analysis executes
- **THEN** no sanitizer is found
- **AND** taint propagation reaches the sink
- **AND** a vulnerability is reported (SQL injection)

#### Scenario: Failed validation with error handling
- **GIVEN** a taint source `req.body` at line 10
- **AND** a try-catch block wrapping `schema.parse(req.body)` at line 11
- **AND** error handler using `req.body` in catch block at line 14
- **AND** a logging sink `logger.error(req.body)` at line 14
- **WHEN** taint analysis executes
- **THEN** taint propagation through error path is NOT stopped
- **AND** a vulnerability is reported (tainted data in error handler)

#### Scenario: Partial validation of object fields
- **GIVEN** a taint source `req.body` at line 10
- **AND** a validation call `schema.parse(req.body)` extracting only `id` field at line 11
- **AND** a SQL sink using `req.body.name` (unvalidated field) at line 12
- **WHEN** taint analysis executes
- **THEN** field-level taint tracking distinguishes validated vs unvalidated fields
- **AND** `req.body.id` is sanitized
- **AND** `req.body.name` remains tainted
- **AND** a vulnerability is reported (unvalidated field usage)

## ADDED Requirements

### Requirement: Validation Framework Pattern Support
The taint analyzer SHALL maintain a `validation_frameworks` category in the SANITIZERS dictionary containing framework-specific validation patterns.

The system SHALL support the following validation frameworks with their respective patterns:
- **Zod**: `.parse`, `.parseAsync`, `.safeParse`, `z.parse`, `schema.parse`, `schema.parseAsync`, `schema.safeParse`
- **Joi**: `.validate`, `.validateAsync`, `Joi.validate`, `schema.validate`, `schema.validateAsync`
- **Yup**: `yup.validate`, `yup.validateSync`, `schema.validateSync`, `.isValid`, `schema.isValid`
- **express-validator**: `validationResult`, `matchedData`, `checkSchema`
- **class-validator**: `validate`, `validateSync`, `validateOrReject`
- **AJV**: `ajv.validate`, `ajv.compile`, `validator.validate`

The system SHALL use frozensets for O(1) lookup performance when checking sanitizer patterns.

The system SHALL NOT recognize schema builder methods (`z.string()`, `Joi.number()`, `yup.object()`) as sanitizers, as these construct schemas but do not validate data.

The system SHALL NOT recognize deserialization methods (`JSON.parse`, `url.parse`) as sanitizers, as these parse data but do not validate or sanitize it.

#### Scenario: Multiple framework support in single project
- **GIVEN** a project using both Zod and express-validator
- **AND** a taint source `req.body` validated by Zod at line 10
- **AND** a taint source `req.query` validated by express-validator at line 15
- **WHEN** taint analysis executes
- **THEN** both Zod patterns and express-validator patterns are recognized
- **AND** no false positives are reported for either framework

#### Scenario: Framework pattern priority (no conflicts)
- **GIVEN** a function named `validate` (generic pattern)
- **AND** a method named `schema.validate` (Joi pattern)
- **WHEN** sanitizer detection executes
- **THEN** both patterns are recognized independently
- **AND** no pattern takes priority over another
- **AND** both stop taint propagation

#### Scenario: Performance with expanded pattern set
- **GIVEN** SANITIZERS dictionary with ~80 total patterns (up from ~60)
- **AND** a large codebase with 10,000+ function calls
- **WHEN** taint analysis executes with sanitizer checking
- **THEN** frozenset O(1) lookup maintains performance
- **AND** total analysis time increase is <5% (negligible)
- **AND** memory usage increase is <1MB
