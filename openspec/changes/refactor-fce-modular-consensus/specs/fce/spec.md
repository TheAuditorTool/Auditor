## ADDED Requirements

### Requirement: Signal Density Calculation

The FCE SHALL calculate Signal Density as the ratio of unique tool sources flagging a location to the total available tools, without applying subjective risk thresholds.

#### Scenario: Multiple tools flag same line
- **WHEN** 5 different tools report findings on the same file:line location
- **AND** the system has 9 total analysis tools available
- **THEN** the ConvergencePoint for that location SHALL have signal_density = 0.555 (5/9)

#### Scenario: Single tool finding
- **WHEN** only 1 tool reports a finding at a location
- **THEN** the signal_density SHALL be 1/N where N is total available tools
- **AND** no "risk escalation" or "severity elevation" SHALL be applied

### Requirement: Fact Stacking Without Judgment

The FCE SHALL stack facts from multiple sources without adding interpretive labels like "CRITICAL" or "HIGH_RISK". Each fact SHALL preserve its source identity and raw observation data.

#### Scenario: Complexity finding stacked with taint finding
- **WHEN** a function has cyclomatic complexity of 45
- **AND** the same function has a taint flow passing through it
- **THEN** both facts SHALL be added to the ConvergencePoint
- **AND** the complexity fact SHALL NOT trigger automatic severity escalation
- **AND** the output SHALL contain `source: "cfg"` and `source: "taint"` as separate facts

#### Scenario: High churn file with security finding
- **WHEN** a file has 50 commits in 90 days
- **AND** the file contains a security finding
- **THEN** the churn data SHALL be recorded as a fact: `{source: "git", observation: "50 commits in 90d"}`
- **AND** the security finding severity SHALL NOT be elevated
- **AND** the user decides what the convergence means

### Requirement: Modular Collector Architecture

The FCE SHALL use separate collector modules for each data source, each returning Pydantic-validated Fact objects.

#### Scenario: Graph collector isolation
- **WHEN** the graph collector loads hotspot data
- **THEN** it SHALL query graphs.db independently
- **AND** return `list[Fact]` with source="graph-analysis"
- **AND** NOT access taint, cfg, or other data sources

#### Scenario: Collector failure isolation
- **WHEN** one collector fails (e.g., coverage data missing)
- **THEN** other collectors SHALL continue operating
- **AND** the final output SHALL include facts from successful collectors only
- **AND** no fallback logic SHALL attempt alternative data sources

### Requirement: AI Context Bundle Generation

The FCE SHALL produce AI Context Bundles that package finding + context for autonomous agent consumption.

#### Scenario: Bundle for taint finding
- **WHEN** a taint flow finding exists from source to sink
- **AND** the sink file is in a CDK stack
- **THEN** the AIContextBundle SHALL contain:
  - The original finding (file, line, message)
  - Context layers (CDK construct tree, deployment status)
  - A suggested_action hint (NOT a command)

#### Scenario: Bundle serialization for LLM
- **WHEN** an AIContextBundle is requested
- **THEN** `bundle.to_prompt_context()` SHALL return valid JSON
- **AND** the JSON SHALL be parseable by any LLM system prompt

### Requirement: Zero Hardcoded Thresholds

The FCE SHALL NOT contain hardcoded thresholds for complexity, churn, coverage, or severity mapping.

#### Scenario: No magic complexity numbers
- **WHEN** processing complexity data
- **THEN** the collector SHALL report raw complexity values
- **AND** there SHALL be no `if complexity <= 20:` or similar checks
- **AND** all threshold decisions are deferred to the consumer

#### Scenario: No percentile calculations for churn
- **WHEN** processing churn data
- **THEN** the collector SHALL report raw commit counts
- **AND** there SHALL be no `percentile_90` calculations
- **AND** no files are filtered out based on churn thresholds

## REMOVED Requirements

### Requirement: Meta Finding Generation
**Reason**: Meta findings like `ARCHITECTURAL_RISK_ESCALATION` and `SYSTEMIC_DEBT_CLUSTER` impose subjective risk interpretations. Replaced by neutral Signal Density metric.
**Migration**: Consumers who need risk classification should implement their own logic on top of ConvergencePoint data.

### Requirement: Severity Elevation Logic
**Reason**: Automatic severity escalation (e.g., "High Churn + Critical = MEGA_CRITICAL") is opinionated and often wrong. Facts should be presented, not judged.
**Migration**: Consumers receive all facts; they decide severity implications.

### Requirement: Subprocess Tool Execution
**Reason**: Running pytest/npm inside FCE conflates "correlation" with "test running". These are separate concerns.
**Migration**: Test execution moves to a separate command or the existing `aud test` capability.
