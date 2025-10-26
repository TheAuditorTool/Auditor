## 0. Verification
- [x] Document baseline behaviour for Stage 3 taint CFG integration.

## 1. Argument Binding & Call Graph
- [ ] Design deterministic caller→callee argument mapping using `function_call_args`, `function_params`, and call graph edges.
- [ ] Add helpers (and optional `MemoryCache` indexes) so Stage 3 can fetch mappings without ad-hoc SQL.

## 2. CFG Path Propagation
- [ ] Extend `InterProceduralCFGAnalyzer` to seed callee entry taint state from mapped arguments, walk CFG paths, and accumulate tainted returns/param effects with condition tracking.
- [ ] Implement recursion/loop safeguards (depth limit, widening) and fall back to Stage 2 when CFG metadata is missing or exceeds limits.

## 3. Output & Integration
- [ ] Ensure Stage 3 paths surface `flow_sensitive`, `conditions`, and `condition_summary` metadata in `TaintPath` plus provenance for parameter/return decisions.
- [ ] Update pipeline logging/documentation so architects know when Stage 3 activated, including guidance for projects missing CFG coverage.

## 4. Validation & Review
- [ ] Add regression fixtures/tests covering multi-function taint flows with guarded branches plus sanitizer bypass, validating new metadata.
- [ ] Run `openspec validate add-taint-path-sensitivity --strict` and secure architect approval for the proposal.
