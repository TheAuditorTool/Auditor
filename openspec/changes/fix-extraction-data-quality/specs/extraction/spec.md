## MODIFIED Requirements

### Requirement: Data Type Validation
The extraction system SHALL validate all extracted data types before storage, ensuring params are strings, relationships are deduplicated, and no defensive type conversions occur. The system MUST hard fail on type mismatches per the ZERO FALLBACK POLICY.

#### Scenario: Valid parameter extraction
- **WHEN** extracting function parameters from any language
- **THEN** param_name MUST be a string, never a dict or object
- **AND** the extraction fails immediately if wrong type is produced

#### Scenario: ORM relationship deduplication
- **WHEN** extracting ORM relationships from any language
- **THEN** duplicate relationships with same key (file:line:source:target:type) are filtered
- **AND** both forward and inverse relationships are generated for bidirectional associations

#### Scenario: Type validation at storage boundary
- **WHEN** storage layer receives extracted data
- **THEN** all fields are validated against expected types
- **AND** assertion fails immediately on type mismatch without conversion

## ADDED Requirements

### Requirement: Extraction Schema Contract
The extraction system SHALL enforce a strict schema contract defining the exact structure and types of all extracted data, with validation at extraction and storage boundaries.

#### Scenario: GraphQL resolver parameter validation
- **WHEN** extracting GraphQL resolver parameters
- **THEN** params array contains only strings
- **AND** no nested objects with param_name fields are created

#### Scenario: Bidirectional relationship generation
- **WHEN** extracting ORM associations like hasMany/belongsTo
- **THEN** both forward (User→Post) and inverse (Post→User) relationships are created
- **AND** cascade flags are properly set for both directions

### Requirement: Parallel Extraction Consistency
The extraction system SHALL ensure consistent behavior across JavaScript and Python extractors, with identical deduplication strategies and type handling.

#### Scenario: Cross-language deduplication parity
- **WHEN** JavaScript and Python extract the same relationship pattern
- **THEN** both use identical deduplication keys and strategies
- **AND** produce the same number of unique relationships

#### Scenario: Parameter type consistency
- **WHEN** extracting parameters from TypeScript or JavaScript
- **THEN** nested AST nodes are fully unwrapped to strings
- **AND** no dict/object structures remain in param fields