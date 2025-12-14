# TheAuditor FCE (Factual Correlation Engine)

## Overview

The **evidence convergence system** that identifies locations where multiple independent analysis vectors converge without imposing subjective risk judgments.

**Core Philosophy:** "I am not the judge, I am the evidence locker."

---

## The 4 Independent Vectors

| Vector | Source | Measures |
|--------|--------|----------|
| **STATIC (S)** | Linters (ruff, eslint, bandit) | Code quality, security patterns |
| **FLOW (F)** | Taint analysis | Source-to-sink data flow risks |
| **PROCESS (P)** | Git history (churn-analysis) | File volatility, change patterns |
| **STRUCTURAL (T)** | CFG analysis | Cyclomatic complexity, nesting depth |

**Critical Rule**: Multiple tools within the SAME vector do NOT increase density. 5 linters screaming about the same issue = 1 STATIC vector, not 5 signals.

---

## Convergence Scoring

**Density Interpretation:**

| Density | Meaning |
|---------|---------|
| 4/4 (1.0) | Everything is screaming - investigate immediately |
| 3/4 (0.75) | Strong convergence - high priority |
| 2/4 (0.5) | Multiple signals - worth attention |
| 1/4 (0.25) | Single dimension - normal finding |

**Pure Math, No Opinions**:
```python
density = len(vectors_present) / 4
```

---

## Core Concepts

### VectorSignal
```python
class VectorSignal:
    file_path: str
    vectors_present: set[Vector]  # {STATIC, FLOW, PROCESS, STRUCTURAL}

    @property
    def density(self) -> float:
        return len(self.vectors_present) / 4

    @property
    def density_label(self) -> str:
        return f"{len(self.vectors_present)}/4 vectors"
```

### ConvergencePoint
```python
class ConvergencePoint:
    file_path: str
    line_start: int
    line_end: int
    signal: VectorSignal
    facts: list[Fact]  # The evidence
```

### Fact
```python
class Fact:
    vector: Vector       # Which vector detected this
    source: str          # Which tool (ruff, taint_flows, etc.)
    file_path: str
    line: int
    observation: str     # Human-readable (NO opinions)
    raw_data: dict       # Full structured data
```

---

## Vector Detection Logic

```python
def _build_vector_index(self) -> dict[str, set[Vector]]:
    # Query 1: findings_consolidated for STATIC, PROCESS, STRUCTURAL
    for row in cursor.execute("SELECT file, tool FROM findings_consolidated"):
        if tool == "cfg-analysis":
            index[file].add(Vector.STRUCTURAL)
        elif tool == "churn-analysis":
            index[file].add(Vector.PROCESS)
        else:
            index[file].add(Vector.STATIC)

    # Query 2: taint_flows for FLOW vector
    for row in cursor.execute("SELECT source_file, sink_file FROM taint_flows"):
        index[row["source_file"]].add(Vector.FLOW)
        index[row["sink_file"]].add(Vector.FLOW)
```

---

## AIContextBundle

Wraps ConvergencePoint with additional context for LLM consumption:

```python
class AIContextBundle:
    convergence: ConvergencePoint
    context_layers: dict  # Related tables' data

    # Registry includes ~148 categorized tables:
    # - RISK_SOURCES: 7 tables
    # - CONTEXT_FRAMEWORK: 34 framework tables
    # - CONTEXT_SECURITY: 6 security tables
    # - CONTEXT_LANGUAGE: 93 language-specific tables
```

---

## How FCE Differs

| Traditional Tools | FCE |
|------------------|-----|
| Risk scoring (CRITICAL/HIGH) | Pure fact reporting |
| Individual tool findings | Vector-based aggregation |
| Single dimension | 4 orthogonal vectors |
| Human-focused output | Deterministic context bundles |

---

## CLI Usage

```bash
aud fce --min-vectors 2    # Default: 2+ vectors
aud fce --format json      # Machine-readable
aud fce --detailed         # Include facts
aud fce --write            # Save to .pf/raw/fce.json
```

**Output Legend:**
```
[3/4] [SF-T] src/auth/login.py
  |     |    |
  |     |    +-- File path
  |     +------- Vectors: S=Static, F=Flow, P=Process, T=Structural
  +------------- Density: 3 of 4 vectors
```

---

## Key Design Principles

1. **No Fallback Logic**: Hard fail if data missing
2. **Bulk Loading**: 2 queries to build index, not N+1
3. **Pure Math**: Density = vectors / 4, no thresholds
4. **Evidence Aggregation**: Package facts + context for AI
5. **Signal != Noise**: Vector count is signal, tool count is noise
