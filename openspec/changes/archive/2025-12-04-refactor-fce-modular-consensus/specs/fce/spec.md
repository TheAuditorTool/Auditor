# FCE Capability Specification

## Capability: fce (Factual Correlation Engine)

**Purpose:** Identify locations where multiple independent analysis VECTORS converge, without imposing subjective risk judgments.

**Philosophy:** "I am not the judge, I am the evidence locker."

---

## ADDED Requirements

### Requirement: Vector-Based Signal Density

The FCE SHALL calculate Signal Density based on independent analysis VECTORS, not tool count.

**Vectors Defined:**
- **STATIC**: Linters (ruff, eslint, patterns, bandit, etc.)
- **FLOW**: Taint analysis (taint_flows, framework_taint_patterns)
- **PROCESS**: Change history (churn-analysis, code_diffs)
- **STRUCTURAL**: Complexity (cfg-analysis)

#### Scenario: 4-Vector Convergence

- **GIVEN** a file `src/auth/login.py`
- **WHEN** the file has:
  - Ruff finding (STATIC vector)
  - Taint flow passing through (FLOW vector)
  - High churn in last 90 days (PROCESS vector)
  - Function with complexity > 10 (STRUCTURAL vector)
- **THEN** the VectorSignal for that file SHALL have:
  - `vectors_present = {STATIC, FLOW, PROCESS, STRUCTURAL}`
  - `density = 1.0` (4/4 vectors)
  - `density_label = "4/4 vectors"`

#### Scenario: Single Vector (Low Signal)

- **GIVEN** a file with only ESLint warnings
- **WHEN** no other vectors have data for the file
- **THEN** the VectorSignal SHALL have:
  - `vectors_present = {STATIC}`
  - `density = 0.25` (1/4 vectors)
- **AND** this is NOT elevated to "critical" or "high risk"

#### Scenario: Multiple Tools Same Vector

- **GIVEN** a file flagged by Ruff, ESLint, and patterns (3 tools)
- **WHEN** all 3 tools belong to STATIC vector
- **THEN** the VectorSignal SHALL have:
  - `vectors_present = {STATIC}` (NOT 3 vectors)
  - `density = 0.25` (1/4 vectors)
- **BECAUSE** multiple linters screaming ≠ multiple independent signals

---

### Requirement: Follow CodeQueryEngine Pattern

The FCEQueryEngine SHALL follow the proven architecture pattern from `theauditor/context/query.py`.

#### Scenario: Database Connection

- **WHEN** FCEQueryEngine is initialized with a project root
- **THEN** it SHALL connect to:
  - `.pf/repo_index.db` for findings data
  - `.pf/graphs.db` for graph data (if exists)
- **AND** use `sqlite3.Row` factory for dict-like access
- **AND** match the CodeQueryEngine constructor pattern

#### Scenario: Method Signatures

- **WHEN** FCEQueryEngine provides public methods
- **THEN** the following methods SHALL exist:
  - `get_vector_density(file_path: str) -> VectorSignal`
  - `get_convergence_points(min_vectors: int = 2) -> list[ConvergencePoint]`
  - `get_context_bundle(file_path: str, line: int) -> AIContextBundle`
  - `close() -> None`

---

### Requirement: Semantic Table Registry

The FCE SHALL use a Semantic Table Registry to categorize the 226 database tables.

#### Scenario: Table Categorization

- **WHEN** the registry is queried for table category
- **THEN** tables SHALL be categorized as:
  - RISK_SOURCES (7 tables): `findings_consolidated`, `taint_flows`, `*_findings`
  - CONTEXT_PROCESS (4 tables): `code_diffs`, `code_snapshots`, `refactor_*`
  - CONTEXT_STRUCTURAL (6 tables): `cfg_*`
  - CONTEXT_FRAMEWORK (36 tables): `react_*`, `angular_*`, `vue_*`, `prisma_*`, `graphql_*`, `sequelize_*`, `bullmq_*`, `express_*`
  - CONTEXT_SECURITY (6 tables): `jwt_patterns`, `sql_queries`, `api_endpoints`
  - CONTEXT_LANGUAGE (86 tables): `go_*`, `rust_*`, `python_*`, `bash_*`

#### Scenario: Context Table Selection

- **GIVEN** a Python file `src/utils/helpers.py`
- **WHEN** `get_context_tables_for_file()` is called
- **THEN** it SHALL return tables from CONTEXT_LANGUAGE starting with `python_`
- **AND** NOT return `go_*`, `rust_*`, or `bash_*` tables

---

### Requirement: Service API for Other Commands

The FCE SHALL expose a service API that other commands can import and use.

#### Scenario: Import from explain command

- **WHEN** `theauditor/commands/explain.py` wants FCE data
- **THEN** it SHALL be able to:
  ```python
  from theauditor.fce import FCEQueryEngine
  engine = FCEQueryEngine(root)
  signal = engine.get_vector_density(file_path)
  ```
- **AND** receive a properly typed `VectorSignal` object

#### Scenario: --fce flag integration

- **WHEN** a command adds `--fce` flag support
- **THEN** it SHALL:
  - Import `FCEQueryEngine` lazily (only when flag is used)
  - Add FCE data to existing output structure
  - NOT change behavior when flag is not used

---

### Requirement: Fact Stacking Without Judgment

The FCE SHALL stack facts from multiple sources without adding interpretive labels.

#### Scenario: Complexity fact stacked with taint finding

- **WHEN** a function has cyclomatic complexity of 45
- **AND** the same function has a taint flow passing through it
- **THEN** both facts SHALL be added to the ConvergencePoint:
  ```json
  {
    "facts": [
      {"vector": "struct", "source": "cfg-analysis", "observation": "Complexity: 45"},
      {"vector": "flow", "source": "taint_flows", "observation": "Untrusted input flows to SQL sink"}
    ]
  }
  ```
- **AND** there SHALL be NO "CRITICAL" or "HIGH_RISK" label added
- **AND** the user/AI decides what the convergence means

#### Scenario: Facts preserve source identity

- **WHEN** facts are collected from multiple sources
- **THEN** each Fact object SHALL have:
  - `vector`: The analysis dimension (STATIC, FLOW, PROCESS, STRUCTURAL)
  - `source`: The specific tool/table (e.g., "ruff", "taint_flows")
  - `observation`: Human-readable description
  - `raw_data`: The undeniable proof (original data from database)

---

### Requirement: Zero Hardcoded Thresholds

The FCE SHALL NOT contain hardcoded thresholds for any metric.

#### Scenario: No magic complexity numbers

- **WHEN** processing complexity data
- **THEN** there SHALL be NO code like:
  ```python
  # FORBIDDEN
  if complexity <= 20:
      ...
  if complexity > 50:
      ...
  ```
- **AND** complexity values SHALL be reported raw in facts

#### Scenario: No percentile calculations

- **WHEN** processing churn data
- **THEN** there SHALL be NO code like:
  ```python
  # FORBIDDEN
  percentile_90 = np.percentile(churn_scores, 90)
  if churn > percentile_90:
      ...
  ```
- **AND** churn values SHALL be reported raw in facts

---

### Requirement: AI Context Bundle Generation

The FCE SHALL produce AI Context Bundles for autonomous agent consumption.

#### Scenario: Bundle structure

- **WHEN** an AIContextBundle is requested for a convergence point
- **THEN** it SHALL contain:
  - `convergence`: The ConvergencePoint object
  - `context_layers`: Dict of additional context by category

#### Scenario: Bundle serialization

- **WHEN** `bundle.to_prompt_context()` is called
- **THEN** it SHALL return valid JSON
- **AND** the JSON SHALL be parseable without custom deserializers

---

## REMOVED Requirements

### Requirement: Meta Finding Generation

**Status:** REMOVED

**Reason:** Meta findings like `ARCHITECTURAL_RISK_ESCALATION`, `SYSTEMIC_DEBT_CLUSTER`, and `COMPLEXITY_RISK_CORRELATION` impose subjective risk interpretations.

**Migration:** Consumers who need risk classification should implement their own logic on top of ConvergencePoint data.

### Requirement: Severity Elevation Logic

**Status:** REMOVED

**Reason:** Automatic severity escalation (e.g., "High Churn + Critical = MEGA_CRITICAL") is opinionated and often wrong.

**Migration:** Consumers receive all facts via VectorSignal; they decide severity implications.

### Requirement: Subprocess Tool Execution

**Status:** REMOVED

**Reason:** Running pytest/npm inside FCE conflates "correlation" with "test running". These are separate concerns.

**Migration:** Test execution should be a separate command or use existing `aud test` capability.

---

## Output Schema

### VectorSignal (per file)

```json
{
  "file_path": "src/auth/login.py",
  "vectors_present": ["static", "flow", "process"],
  "density": 0.75,
  "density_label": "3/4 vectors"
}
```

### ConvergencePoint (per location)

```json
{
  "file_path": "src/auth/login.py",
  "line_start": 42,
  "line_end": 58,
  "signal": {
    "file_path": "src/auth/login.py",
    "vectors_present": ["static", "flow"],
    "density": 0.5
  },
  "facts": [
    {
      "vector": "static",
      "source": "ruff",
      "file_path": "src/auth/login.py",
      "line": 45,
      "observation": "B101: assert used in production code",
      "raw_data": {"rule": "B101", "severity": "warning"}
    },
    {
      "vector": "flow",
      "source": "taint_flows",
      "file_path": "src/auth/login.py",
      "line": 48,
      "observation": "User input flows to SQL query",
      "raw_data": {"source_type": "http_request", "sink_type": "sql_query"}
    }
  ]
}
```

### Full FCE Report

```json
{
  "summary": {
    "files_analyzed": 586,
    "convergence_points": 43,
    "max_vector_density": 0.75
  },
  "convergence_points": [
    // ConvergencePoint objects sorted by density DESC
  ],
  "metadata": {
    "generated_at": "2025-12-03T10:30:00Z",
    "min_vectors_filter": 2
  }
}
```

---

## Acceptance Criteria

1. `aud fce` outputs vector-based signal density (0-4 vectors)
2. ZERO hardcoded thresholds in new code
3. Other commands can import `FCEQueryEngine` and use `--fce` flag
4. Output format is pure facts, no "CRITICAL" or "HIGH_RISK" labels
5. Performance: <500ms for typical codebase (~500 files with findings)
6. All Pydantic models validate correctly
7. JSON output is valid and parseable
8. No emojis in output (Windows CP1252 compatibility)
