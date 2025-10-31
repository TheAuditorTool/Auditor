## ADDED Requirements

### Requirement: GraphQL Auth Detection Patterns
GraphQL auth rules MUST use frozen pattern sets for consistent detection of authentication mechanisms.

#### Scenario: Auth Middleware Pattern Detection
- **GIVEN** a GraphQL resolver mapped to a backend function
- **WHEN** the auth rule inspects `graphql_resolver_mappings` joined with `function_call_args`
- **THEN** it checks function calls against GRAPHQL_AUTH_PATTERNS frozenset including: `@authenticated`, `@requiresAuth`, `@UseGuards(AuthGuard)`, `@login_required`, `authenticate()`, `verifyToken()`, `checkAuth()`, etc.
- **AND** it checks schema directives against GRAPHQL_AUTH_DIRECTIVES frozenset including: `@auth`, `@authenticated`, `@requiresAuth`, `@requiresRole`, `@hasPermission`, `@private`, etc.
- **AND** detection uses EXACT SQL matches joined with Python-side pattern filtering (NO LIKE in WHERE clause)

### Requirement: GraphQL Injection Detection Query Pattern
Injection rules MUST query taint flows from GraphQL arguments to sinks with proper table JOINs.

#### Scenario: Taint Flow SQL Query Structure
- **GIVEN** the injection rule needs to detect argument→sink flows
- **WHEN** building the detection query
- **THEN** it uses this pattern:
```python
# Step 1: Get taint sources from GraphQL field arguments
query = build_query('graphql_fields',
    ['field_id', 'type_id', 'field_name', 'line'])
cursor.execute(query)

for field_id, type_id, field_name, line in cursor.fetchall():
    # Step 2: Get resolver mapping
    resolver_query = build_query('graphql_resolver_mappings',
        ['resolver_symbol_id', 'resolver_path', 'resolver_line'],
        where=f"field_id = {field_id}")
    # Step 3: Check taint_flows for this resolver→sink
    # Step 4: Verify no sanitization calls in between
```
- **AND** uses JOINs with `graphql_execution_edges` for downstream call chains
- **AND** checks `function_call_args` for sanitization functions (parameterized queries, escape functions)
- **AND** filters test files in Python AFTER fetch (NOT in SQL WHERE)

### Requirement: GraphQL N+1 Detection CFG Query Pattern
N+1 detection MUST inspect resolver execution edges joined with CFG loop detection.

#### Scenario: N+1 Loop Detection Query
- **GIVEN** a GraphQL field that returns a list
- **WHEN** checking for N+1 queries
- **THEN** the rule queries:
```python
# Step 1: Find list-returning fields
query = build_query('graphql_fields',
    ['field_id', 'type_id', 'field_name', 'is_list'],
    where="is_list = 1")

for field_id, type_id, field_name, is_list in cursor.fetchall():
    # Step 2: Get child field resolvers
    child_query = build_query('graphql_fields',
        ['field_id', 'field_name'],
        where=f"type_id = (SELECT return_type FROM graphql_fields WHERE field_id = {field_id})")

    # Step 3: For each child resolver, check if it calls DB inside loop
    # JOIN graphql_resolver_mappings → symbols → cfg_blocks
    # Look for cfg_blocks with kind='loop' containing DB call edges
```
- **AND** uses `cfg_blocks.kind = 'loop'` to detect loops
- **AND** checks for ORM queries (`orm_queries`) or SQL queries (`sql_queries`) inside loop blocks
- **AND** emits finding with resolver path, line, and offending query location

### Requirement: GraphQL Sensitive Field Patterns
Overfetch detection MUST define sensitive field patterns for PII/credentials flagging.

#### Scenario: Sensitive Field Pattern Matching
- **GIVEN** GraphQL schema contains fields with sensitive names
- **WHEN** the overfetch rule inspects field exposure
- **THEN** it checks against GRAPHQL_SENSITIVE_FIELDS frozenset including:
  - PII: `ssn`, `social_security`, `credit_card`, `creditCard`, `cardNumber`, `cvv`, `password`, `passwordHash`, `apiKey`, `api_key`, `secretKey`, `secret_key`, `privateKey`, `private_key`
  - Auth: `token`, `accessToken`, `refreshToken`, `sessionId`, `session_id`, `jwt`, `bearer`
  - Financial: `bankAccount`, `bank_account`, `routingNumber`, `accountNumber`, `balance`, `salary`
  - Health: `medicalRecord`, `diagnosis`, `prescription`, `healthRecord`
- **AND** checks if resolver returns these fields but schema doesn't expose them
- **AND** uses case-insensitive matching via Python `.lower()` AFTER SQL fetch

### Requirement: GraphQL Rule Severity Mappings
All GraphQL rules MUST follow consistent severity levels based on exploitability.

#### Scenario: Severity Assignment
- **GIVEN** a GraphQL finding is detected
- **WHEN** assigning severity
- **THEN** it follows this mapping:
  - `CRITICAL`: Unauthenticated mutation exposing PII/financial data + proven injection path with no sanitization
  - `HIGH`: Mutation without auth + taint flow to sink (partial sanitization) OR N+1 with >100 potential iterations
  - `MEDIUM`: Query without expected auth + sensitive field exposure OR N+1 with 10-100 iterations
  - `LOW`: Public endpoint pattern mismatch (field not marked public but acts public) OR N+1 with <10 iterations
  - `INFO`: Missing directive that should be present (schema quality issue, not exploitable)
- **AND** includes CWE references: CWE-285 (Improper Authorization), CWE-89 (SQL Injection), CWE-200 (Information Exposure)

### Requirement: GraphQL Rule File Filtering
GraphQL rules MUST use RuleMetadata for file exclusions, NOT SQL WHERE clauses.

#### Scenario: Test File Exclusion
- **GIVEN** a GraphQL rule needs to skip test files
- **WHEN** the rule is initialized
- **THEN** it defines RuleMetadata with exclude_patterns:
```python
METADATA = RuleMetadata(
    rule_id="graphql-mutation-no-auth",
    name="GraphQL Mutation Missing Authentication",
    category="security",
    severity=Severity.HIGH,
    confidence=Confidence.HIGH,
    description="Detects GraphQL mutations without authentication",
    tags=["graphql", "authentication", "mutation", "authorization"],
    cwe_ids=["CWE-285", "CWE-306"],
    owasp_category="A01:2021 - Broken Access Control",
    exclude_patterns=[
        "test/", "__tests__/", "*.test.js", "*.spec.js",
        "*.test.ts", "*.spec.ts", "*.test.py", "test_*.py",
        "tests/", "spec/", "mocks/", "fixtures/"
    ]
)
```
- **AND** orchestrator applies exclusions BEFORE rule runs
- **AND** rule SQL queries do NOT contain `file NOT LIKE '%test%'` patterns

### Requirement: GraphQL Rule Detection Logic Structure
All GraphQL rules MUST follow the verified pattern from progress.md refactor.

#### Scenario: Rule Implementation Pattern
- **GIVEN** implementing a new GraphQL rule
- **WHEN** writing detection logic
- **THEN** it follows this structure:
```python
from dataclasses import dataclass
from theauditor.rules.base import StandardRuleContext, StandardFinding, RuleMetadata
from theauditor.indexer.schema import build_query

@dataclass(frozen=True)
class GraphQLAuthPatterns:
    """Immutable pattern definitions for GraphQL auth detection."""

    # Auth decorators/middleware
    AUTH_DECORATORS = frozenset([
        '@authenticated', '@requiresAuth', '@login_required',
        '@UseGuards', 'AuthGuard', 'JwtGuard', ...
    ])

    # Schema directives
    AUTH_DIRECTIVES = frozenset([
        '@auth', '@authenticated', '@requiresRole', '@hasPermission', ...
    ])

    # Functions that indicate auth checks
    AUTH_FUNCTIONS = frozenset([
        'authenticate', 'verifyToken', 'checkAuth', ...
    ])

METADATA = RuleMetadata(...)

def analyze(context: StandardRuleContext) -> List[StandardFinding]:
    findings = []
    patterns = GraphQLAuthPatterns()

    # Step 1: SQL query with EXACT matches only
    query = build_query('graphql_resolver_mappings',
        ['field_id', 'resolver_symbol_id', 'resolver_path', 'resolver_line'])
    context.cursor.execute(query)

    # Step 2: Python-side filtering AFTER fetch
    for field_id, symbol_id, path, line in context.cursor.fetchall():
        # Filter test files in Python
        if any(p in path for p in ['test/', 'spec.', '__tests__']):
            continue

        # Check for auth patterns
        has_auth = check_auth_patterns(context, symbol_id, patterns)

        if not has_auth:
            findings.append(StandardFinding(...))

    return findings
```
- **AND** uses frozen dataclasses for pattern definitions
- **AND** separates SQL queries (exact match) from Python filtering (patterns)
- **AND** anchors ALL table/column references to schema.py via build_query
