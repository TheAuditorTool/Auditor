## Overview
Finish the Stage 3, CFG-backed interprocedural taint engine so path-sensitive flows survive across function boundaries. The implementation will build deterministic caller→callee bindings from the indexed call graph, seed the callee CFG analyzer with real taint state, and emit rich `TaintPath` metadata describing branch conditions, sanitizer effects, and return taint.

## Key Decisions
- Build argument bindings exclusively from `function_call_args`, `function_params`, and existing call graph edges (no string heuristics) and cache them with `MemoryCache` lookups to keep Stage 3 analysis in-memory.
- Reuse `PathAnalyzer` primitives to walk callee CFG blocks and merge taint states, extending it to record parameter/return effects and condition summaries suitable for interprocedural paths.
- Add guardrails: depth-limited recursion, widening for loops, and deterministic fallback to Stage 2 flow-insensitive tracking when CFG metadata is missing or incomplete.
- Surface interprocedural provenance by attaching a `flow_sensitive` flag plus condition/parameter annotations to every Stage 3 `TaintPath`, and emit trace-level logs so auditors can confirm when Stage 3 activated.

## Open Questions
- How should we resolve dynamic dispatch (object maps, higher-order functions) without regex? We may need to constrain the initial scope to direct call expressions and document gaps.
- Do we need new indexes in `MemoryCache` (e.g., calls keyed by callee) to keep Stage 3 performant on million-line repositories?
- What additional metadata (e.g., branch probability, sanitizer provenance) do downstream consumers require beyond the planned condition summaries?
