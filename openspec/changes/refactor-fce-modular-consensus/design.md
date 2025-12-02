# Design: FCE Modular Consensus Engine

## Context

The FCE is TheAuditor's "brain" - it correlates findings from all analysis tools to identify compound risks. Current implementation is a 1500-line monolith that:
1. Loads ALL findings into memory (RAM hog)
2. Runs synchronously (blocks on subprocess calls)
3. Uses hardcoded magic numbers (`if complexity <= 20:`)
4. Mixes data collection with risk judgment

The rewrite transforms it from a "Risk Calculator" to a "Consensus Aggregator" that strictly reports factual convergence without opinion.

## Goals / Non-Goals

**Goals:**
- Modular package structure with clear separation of concerns
- Strict Pydantic typing ("Stringly Typed" -> "Strongly Typed")
- Signal Density metric replaces Risk Scoring
- Async-ready collectors for parallel data loading
- AI Context Bundle format for autonomous agent integration
- Zero hardcoded thresholds

**Non-Goals:**
- Adding new analysis tools
- Changing database schemas
- Building a frontend/UI
- Real-time streaming (batch processing is fine)

## Architecture Decisions

### Decision 1: Package Structure
```
theauditor/fce/
    __init__.py          # Public API: run_fce()
    schema.py            # Pydantic models (Fact, ConvergencePoint, AIContextBundle)
    engine.py            # Main orchestrator (replaces fce.py)
    collectors/
        __init__.py
        base.py          # Abstract collector interface
        graph.py         # Hotspots, cycles from graphs.db
        cfg.py           # Complexity from cfg analysis
        taint.py         # Taint flows
        coverage.py      # Test coverage
        churn.py         # Git churn
        findings.py      # All findings from repo_index.db
    analyzers/
        __init__.py
        convergence.py   # Signal stacking algorithm
        path_correlation.py  # CFG-based path analysis
    resolver.py          # AI context bundle builder
```

**Rationale:** Standard Python package pattern. Each concern isolated. Easy to test. Easy to extend (add new collector = add new file).

### Decision 2: Pydantic Models (The "Truth Courier")
```python
class Fact(BaseModel):
    source: str       # e.g., "TaintEngine", "GitHistory", "Linter"
    observation: str  # e.g., "Untrusted Input", "Changed 10 mins ago"
    raw_data: dict    # The undeniable proof

class ConvergencePoint(BaseModel):
    file_path: str
    line_start: int
    line_end: int
    unique_sources: set[str]
    facts: list[Fact]

    @property
    def signal_density(self) -> float:
        """Pure math. No opinion."""
        return len(self.unique_sources) / TOTAL_AVAILABLE_TOOLS
```

**Rationale:**
- Strict typing catches bugs at development time
- Pydantic validation ensures data integrity
- `signal_density` is pure math - can't be wrong

### Decision 3: Signal Density Instead of Risk Scores
**OLD (Opinion):**
```python
if churn_score > 0.8 and finding.severity == "critical":
    finding["elevated_severity"] = "MEGA_CRITICAL"  # Made-up category
```

**NEW (Fact):**
```python
point.unique_sources.add("Git")
point.facts.append(Fact(source="Git", observation=f"High Churn ({churn_score})"))
# No judgment. Just stack the fact.
```

**Rationale:**
- Developers hate tools that think they're smarter than them
- They can't argue with: "Semgrep, Sonar, Dependabot, and Git logs all point at line 42"
- Senior devs feel smart deducing the risk themselves
- "New dev safety net" - you're never wrong because you only report counts

### Decision 4: Async-Ready Collectors
```python
class BaseCollector(ABC):
    @abstractmethod
    async def collect(self, context: CollectionContext) -> list[Fact]:
        """Load facts from data source."""
        pass

# Usage
results = await asyncio.gather(
    graph_collector.collect(ctx),
    cfg_collector.collect(ctx),
    churn_collector.collect(ctx),
)
```

**Rationale:**
- Currently all DB queries are synchronous and serial
- Async allows parallel loading of independent data sources
- Even if DB operations aren't truly async, the structure allows future optimization
- Subprocess calls (tests, builds) become non-blocking

### Decision 5: AI Context Bundle
```python
class AIContextBundle(BaseModel):
    finding: Finding
    context_layers: list[ContextLayer]
    suggested_action: str  # e.g., "Generate CDK patch" or "Investigate"

    def to_prompt_context(self) -> str:
        return self.model_dump_json(indent=2)
```

**Rationale:**
- The tool integrates with AI autonomously - "Claude runs the tool, that's the fix button"
- Bundle packages Signal + Context for LLM consumption
- Strict schema ensures consistent prompt structure
- `suggested_action` is guidance, not a command

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Breaking output format | Document migration clearly, version the schema |
| Async complexity | Start with sync wrappers, add true async later |
| Over-engineering | Keep collectors simple, single DB query each |
| Performance regression | Benchmark before/after on same codebase |

## Migration Plan

1. Create `theauditor/fce/` package with new structure
2. Implement schema.py first (all Pydantic models)
3. Port collectors one at a time (graph -> cfg -> taint -> ...)
4. Implement convergence analyzer
5. Wire up in engine.py
6. Update commands/fce.py to import from new location
7. Archive old `theauditor/fce.py`
8. Update output format documentation

**Rollback:** Keep old fce.py around during transition with deprecation warning.

## Open Questions

1. Should `signal_density` include a weighting factor for tool reliability?
   - Current answer: No. Pure count is simpler and more honest.

2. Should we stream findings instead of loading all into memory?
   - Current answer: Defer. Pydantic models are fine for typical repos (<100k findings).

3. Should collectors be truly async or just structured for future async?
   - Current answer: Structure for async, use sync initially. Don't over-engineer.
