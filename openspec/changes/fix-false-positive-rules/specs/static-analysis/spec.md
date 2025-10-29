# Static Analysis Capability - Normalized Rule Matching

## ADDED Requirements

### Requirement: Rules leverage normalized metadata for sensitive pattern checks
SAST rules that identify secrets, cryptographic usage, or PII exposure SHALL use the normalized assignment and call metadata produced by the indexer (value type, literal value, callee identifier, argument tokens) instead of raw substring matches.

The system SHALL treat non-literal sources (e.g., header readers, framework helper methods) as non-secrets when their value type is not a literal string.

The system SHALL evaluate cryptographic algorithms using the resolved callee/function name to avoid collisions with similarly named utility methods.

The system SHALL classify API routes and payload fields using normalized API endpoint metadata, ensuring that generic words embedded in property names (e.g., `message`, `package.json`) do not trigger PII findings.

#### Scenario: Header-derived API key is not flagged as literal secret
- **GIVEN** the indexer records `const apiKey = request.headers.get('X-API-Key')` with value type `call`
- **AND** the secret detection rule queries the assignment metadata
- **WHEN** the rule evaluates the assignment
- **THEN** the rule observes the value type is not `string_literal`
- **AND** no `secret-hardcoded-assignment` finding is emitted

#### Scenario: Framework helper `includes()` does not trigger DES weak crypto finding
- **GIVEN** the call graph records `changes.some(c => c.path.includes('robots.txt'))`
- **AND** the resolved callee is `String.prototype.includes`
- **WHEN** the weak crypto rule evaluates the call metadata
- **THEN** the rule identifies the callee is not a DES algorithm
- **AND** no `crypto-weak-encryption` finding is emitted

#### Scenario: Response payload `message` does not trigger PII exposure
- **GIVEN** the API endpoint table records `GET /api/dashboard` returning `{ message: 'Site updated successfully' }`
- **AND** the normalized payload metadata treats `message` as a generic response key
- **WHEN** the PII exposure rule evaluates the endpoint
- **THEN** the rule observes no PII tokens in the normalized metadata
- **AND** no `pii-api-exposure` or `pii-error-response` finding is emitted
