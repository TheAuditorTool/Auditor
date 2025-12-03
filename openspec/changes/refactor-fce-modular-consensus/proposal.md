# Proposal: Refactor FCE to Vector-Based Consensus Engine

## Status

**Brainstorming → FORMALIZED** (Session: 2025-12-03)

Refined through Architect + Lead Auditor (Gemini) + AI Coder (Opus) collaboration.

## Why

The Factual Correlation Engine (FCE) is a 1500-line monolithic "God Script" that grew organically. It does database IO, subprocess management, log parsing, and complex heuristic logic all in one file. This makes it unmaintainable, memory-hungry, and hard to extend.

More critically, the current design has THREE problems:

1. **Wrong Architecture** - Doesn't follow existing patterns (`CodeQueryEngine` in `aud explain`)
2. **Wrong Metric** - Counts tools (noise) instead of vectors (signal)
3. **Risk Judgment** - Hardcoded thresholds like `if complexity <= 20:` (opinionated)

The FCE's true value is being a **Consensus Engine** - showing when multiple INDEPENDENT ANALYSIS VECTORS converge on the same location - NOT being a "Nanny Engine" that tells developers what to do.

**Philosophy**: "I am not the judge, I am the evidence locker."

## The Key Insight (from Lead Auditor)

**Tool Count = Noise**
- Ruff, Flake8, and Pylint all screaming about the same syntax error
- Density: 3 tools. Real Value: Low (it's just one syntax error)

**Vector Count = Signal**
- Group sources into INDEPENDENT VECTORS:
  - **Static Vector**: Linters (Ruff, ESLint, patterns)
  - **Flow Vector**: Taint analysis (taint_flows)
  - **Process Vector**: Git Churn (code_diffs, churn-analysis)
  - **Structural Vector**: Complexity (cfg-analysis)

If Static + Flow + Process + Structural all flag a file → **4/4 Vector Convergence**

*"This file is a 4-Vector convergence: It's buggy (Static), vulnerable (Flow), volatile (Process), and complex (Structural). Focus here first."*

## What Changes

### Architecture Correction

**OLD PROPOSAL (WRONG):**
```
theauditor/fce/
    collectors/       # <- Over-engineered, doesn't match existing patterns
    analyzers/
    resolver.py
```

**NEW PROPOSAL (CORRECT):**
```
theauditor/fce/
    __init__.py       # Public API: run_fce(), FCEQueryEngine
    schema.py         # Pydantic models (Fact, ConvergencePoint, VectorSignal)
    query.py          # FCEQueryEngine (follows CodeQueryEngine pattern)
    formatter.py      # FCEFormatter for text/json output
    registry.py       # Semantic Table Registry (Risk vs Context tables)
```

**WHY**: Follow the proven `CodeQueryEngine` pattern from `aud explain`. Same databases (repo_index.db, graphs.db), same query approach, different purpose (convergence/fishbone).

### Signal Density Algorithm

**OLD (Tool Count - Noise):**
```python
signal_density = len(unique_tools) / total_tools  # 5/9 = 0.55
```

**NEW (Vector Count - Signal):**
```python
vectors_present = 0
if has_static_findings: vectors_present += 1    # Linters
if has_flow_findings: vectors_present += 1      # Taint
if has_process_data: vectors_present += 1       # Churn
if has_structural_data: vectors_present += 1    # Complexity

vector_density = vectors_present / 4  # 3/4 = 0.75 (3-vector convergence)
```

### Semantic Table Registry

**The Problem**: 226 tables in repo_index.db. Can't write custom queries for each.

**The Solution**: Categorize tables by their role in the fishbone:

| Category | Tables | Purpose |
|----------|--------|---------|
| **Risk Sources** | 7 | findings_consolidated, taint_flows, *_findings |
| **Context: Process** | 4 | code_diffs, code_snapshots, refactor_* |
| **Context: Structural** | 6 | cfg_*, complexity data |
| **Context: Framework** | 36 | react_*, angular_*, vue_*, prisma_*, graphql_*, sequelize_*, bullmq_*, express_* |
| **Context: Security** | 6 | jwt_patterns, sql_queries, api_endpoints |
| **Context: Language** | 86 | go_*, rust_*, python_*, bash_* |
| **Context: Core** | 79 | symbols, imports, refs, calls |

**Query Strategy** (from Lead Auditor):
1. **Risk Query (Fast)**: Query ONLY Risk Sources first
2. **Vector Calculation**: Check which vectors have data for that file
3. **Context Expansion (Lazy)**: Only if vector_density > 0 AND requested, load context tables

### Service API (--fce flags)

FCE becomes a SERVICE that other commands can consume:

```python
# In theauditor/fce/__init__.py
from theauditor.fce.query import FCEQueryEngine

# Other commands import and use:
engine = FCEQueryEngine(root)
density = engine.get_vector_density(file_path)  # Returns VectorSignal
bundle = engine.get_context_bundle(file_path, line)  # Returns AIContextBundle
```

**Integration Points:**
- `aud fce` → standalone fishbone correlation view
- `aud explain target --fce` → adds convergence data to explain output
- `aud blueprint --fce` → adds hotspot overlay to architecture view

### Breaking Changes

- **BREAKING**: FCE output format changes from risk-scored findings to vector-stacked facts
- **BREAKING**: Old `results["correlations"]["meta_findings"]` format REMOVED
- **BREAKING**: Signal density now reports vectors (0-4), not tool count

### What Gets DELETED

- ALL hardcoded thresholds (`if complexity <= 20:`, `if coverage >= 50:`)
- Meta-finding opinions (`ARCHITECTURAL_RISK_ESCALATION`, `SYSTEMIC_DEBT_CLUSTER`)
- Subprocess test execution (pytest/npm) - separate concern
- `register_meta` function and meta_registry
- All severity elevation logic

## Impact

- **Affected code**:
  - `theauditor/fce.py` → refactored into `theauditor/fce/` package
  - `theauditor/commands/fce.py` → updated imports, new --format options
  - `.pf/raw/fce.json` → new output schema (vector-based)

- **Affected commands** (future integration):
  - `theauditor/commands/explain.py` → add `--fce` flag
  - `theauditor/commands/blueprint.py` → add `--fce` flag

- **NO changes to**:
  - Database schema (repo_index.db, graphs.db stay same)
  - Other analysis engines (taint, graph, cfg)
  - Indexing pipeline

## Non-Goals (Explicit Scope Limits)

- NOT adding new analysis capabilities
- NOT changing taint/graph/cfg engines
- NOT integrating external scanners
- NOT changing database schema
- NOT adding async (keep sync, match CodeQueryEngine)
- NOT over-engineering with collector abstraction layers

## Verification (Per teamsop.md)

Hypotheses verified during brainstorming:

1. **Hypothesis**: FCE should follow CodeQueryEngine pattern
   - **Verified**: YES - `aud explain` uses this pattern successfully

2. **Hypothesis**: Tables share spatial coordinates (file, line)
   - **Verified**: YES - 200/226 tables have file/path columns, 115 have `line` column

3. **Hypothesis**: Data can be joined across vectors
   - **Verified**: YES - Prototype query confirmed 43 files have 2+ vector convergence

4. **Hypothesis**: Current FCE has hardcoded thresholds
   - **Verified**: YES - `complexity <= 20`, `coverage >= 50`, `percentile_90` found in code

## Success Criteria

1. FCE reports Vector Density (0-4) instead of tool count
2. ZERO hardcoded thresholds in new code
3. Other commands can import `FCEQueryEngine` and use `--fce` flag
4. Output format is pure facts, no opinions
5. Performance: <500ms for typical codebase
