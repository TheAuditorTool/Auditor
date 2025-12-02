# Proposal: Refactor FCE to Modular Consensus Engine

## Why

The Factual Correlation Engine (FCE) is a 1500-line monolithic "God Script" that grew organically. It does database IO, subprocess management, log parsing, and complex heuristic logic all in one file. This makes it unmaintainable, memory-hungry, and hard to extend.

More critically, the current design mixes two concerns:
1. **Fact Collection** - Loading data from various sources (good)
2. **Risk Judgment** - Hardcoded thresholds like `if complexity <= 20:` (bad)

The FCE's true value is being a **Consensus Engine** - showing when multiple independent tools point at the same location - NOT being a "Nanny Engine" that tells developers what to do.

**Philosophy Shift**: "I am not the judge, I am the evidence locker."

## What Changes

### Core Rewrite
- **NEW**: Create `theauditor/fce/` directory with modular architecture
- **NEW**: `schema.py` - Pydantic models for strict typing ("Truth Courier" pattern)
- **NEW**: `collectors/` - Async database loaders (graph, cfg, taint, coverage, churn)
- **NEW**: `analyzers/` - Pure signal stacking logic (no hardcoded thresholds)
- **NEW**: `resolver.py` - AI context bundle assembly for autonomous agent handoff
- **REMOVED**: Hardcoded heuristics (complexity thresholds, churn percentiles, coverage checks)
- **REMOVED**: All "Risk Calculation" logic - replaced with "Signal Density" metric

### Signal Density Algorithm
Instead of: "This is Critical because churn is high" (subjective)
Report: "5/9 tools flagged this location" (objective, undeniable)

```python
# The "Motherfucker Look Here" metric
signal_density = len(unique_sources) / total_available_tools
```

### Breaking Changes
- **BREAKING**: FCE output format changes from risk-scored findings to convergence-stacked facts
- **BREAKING**: Old `results["correlations"]["meta_findings"]` format retired
- **BREAKING**: Import path changes from `theauditor.fce` to `theauditor.fce.engine`

## Impact

- Affected specs: `fce` (new spec to be created)
- Affected code:
  - `theauditor/fce.py` -> archived, replaced by `theauditor/fce/` package
  - `theauditor/commands/fce.py` -> updated imports
  - `.pf/raw/fce.json` -> new output schema
- No changes to other commands or specs (FCE is isolated)

## Non-Goals (Explicit Scope Limits)

- NOT adding new analysis capabilities
- NOT changing taint/graph/cfg engines
- NOT integrating external scanners
- NOT changing database schema (repo_index.db stays same)
