## ADDED Requirements

### Requirement: GraphQL Arguments Seed Taint Analysis
The taint engine MUST automatically treat GraphQL field arguments as untrusted sources mapped to resolver parameters.

#### Scenario: Resolver Parameter Receives Taint
- **GIVEN** `aud index` and `aud graphql build` have produced resolver metadata
- **AND** `aud taint` runs
- **WHEN** inspecting the taint frontier
- **THEN** entries exist for each GraphQL argument that map to the resolver parameter defined in `graphql_resolver_params`
- **AND** taint propagation follows `graphql_execution_edges` into downstream call targets without needing additional configuration.

### Requirement: Auth Coverage for Sensitive GraphQL Fields
GraphQL rules MUST flag sensitive fields whose resolvers bypass authentication/authorisation.

#### Scenario: Missing Auth Decorator on Mutation
- **GIVEN** a `Mutation.updateCreditCard` field mapped to a resolver that does not call or decorate any known auth check
- **WHEN** `aud rules --category graphql` (or the GraphQL rule track inside `aud full`) executes
- **THEN** a high-severity `graphql-mutation-no-auth` finding is inserted into `findings_consolidated` with provenance referencing the relevant `graphql_fields` and `graphql_resolver_mappings` rows
- **AND** the finding surfaces in `.pf/raw/report_summary.json` and via `aud fce`.

### Requirement: GraphQL Injection Detection Uses Execution Graph
Injection rules MUST use the resolver execution graph and taint traces to prove unsanitised argument flow into database or command sinks.

#### Scenario: Argument Flows Into ORM Query
- **GIVEN** a GraphQL query `user(id: ID!)` whose resolver concatenates `id` into a SQL string without sanitisation
- **WHEN** `aud rules --category graphql` runs
- **THEN** the rule joins taint traces (`taint_flows`) with `graphql_execution_edges` to detect the unsafe flow and records a `graphql-injection` finding with severity `critical`
- **AND** the finding cites the resolver symbol and sink call sites, notifies FCE, and appears in the courier export.

### Requirement: Detect GraphQL N+1 Patterns
GraphQL analysis MUST identify resolvers that trigger downstream database calls inside field-level loops.

#### Scenario: Child Resolver Causes N+1 Query
- **GIVEN** a list field `Query.posts` returning many posts and a `Post.author` resolver that issues a database query inside a per-item loop
- **WHEN** the GraphQL performance rule executes
- **THEN** it inspects CFG metadata joined through `graphql_execution_edges` to detect repeated DB calls and emits a medium-severity `graphql-n-plus-one` finding into `findings_consolidated`
- **AND** the courier output links the finding to the offending resolver and downstream query call site for remediation.
