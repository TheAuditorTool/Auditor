## Hypotheses
- H1: Stage 3 CFG-based interprocedural taint analysis does not yet propagate taint because the argument mapping between caller variables and callee parameters is unimplemented.
- H2: The main pipeline already invokes taint analysis with both `use_cfg` and `stage3` enabled, so the missing Stage 3 propagation currently produces empty results for cross-function flows.

## Evidence
- `theauditor/taint/propagation.py:418` conditionally calls `trace_inter_procedural_flow_cfg` when `use_cfg` and `stage3` are true, proving the Stage 3 path is expected to execute.
- `theauditor/pipelines.py:894` runs `trace_taint(..., use_cfg=True, stage3=True, ...)`, so production runs always route through the Stage 3 path-sensitive implementation.
- `theauditor/taint/interprocedural.py:285` constructs `args_mapping = {}` before calling `InterProceduralCFGAnalyzer.analyze_function_call`, leaving the analyzer without any caller→callee mapping to evaluate.
- `theauditor/taint/interprocedural_cfg.py:332` shows `_map_taint_to_params` requires populated `args_mapping` entries to taint callee parameters; with the current empty mapping no parameters become tainted, so Stage 3 never reports flows.

## Discrepancies
- The code advertises Stage 3 path-sensitive, interprocedural taint tracing, yet the analyzer receives empty argument mappings and therefore cannot propagate taint, leaving cross-function path sensitivity effectively disabled.
