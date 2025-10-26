## Why
- Stage 3 CFG taint tracing is surfaced in the pipeline (`trace_taint(..., use_cfg=True, stage3=True)`) but returns empty flows because the interprocedural analyzer never maps caller arguments to callee parameters.
- Without functional path-sensitive propagation across functions, Express/Flask style controller → helper → sink chains never produce evidence, leaving major false negatives in Track A.
- The current stub leaves `args_mapping = {}` while `_map_taint_to_params` and `_extract_effects` expect populated entries, so we must finish the implementation instead of relying on flow-insensitive fallbacks.

## What Changes
- Implement deterministic argument binding for Stage 3 by querying `function_call_args`, `function_params`, and the call graph to build caller→callee parameter maps and pass taint state into `InterProceduralCFGAnalyzer`.
- Extend the analyzer to walk CFG paths in the callee (and subsequent callees) extracting tainted returns, parameter mutations, sanitation, and branch conditions, then surface those as `flow_sensitive` `TaintPath` metadata.
- Add guardrails for missing CFG data (fallback to the existing Stage 2 engine), emit structured condition summaries for interprocedural paths, and capture the behaviour with regression fixtures/tests plus updated taint documentation.

## Impact
- Restores cross-function taint coverage for real-world controller/helper stacks while reducing false positives by honoring branch-sanitation preconditions.
- Aligns pipeline output with product messaging about path-sensitive taint, giving architects evidence-rich flows to consume in `.pf/raw/taint_analysis.json`.
- Provides a documented contract for future contributors on how Stage 3 is activated, cached, and how condition metadata is expected to look.

## Verification Alignment
- Evidence of the current Stage 3 gap is captured in `openspec/changes/add-taint-path-sensitivity/verification.md`.
