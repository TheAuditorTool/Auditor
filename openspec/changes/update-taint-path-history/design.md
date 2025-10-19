# Design: update-taint-path-history

## Overview
Multi-hop taint analysis currently drops alternate controller→helper paths because both Stage 2 and Stage 3 deduplicate solely on the helper’s `(file, function, var)` state. The change introduces signature-aware worklists so each distinct call stack is preserved and serialized back to `.pf/taint_analysis.json`.

## Current Implementation (Evidence)
- Stage 2 seeds `(source_var, source_function, source_file, depth, path)` and marks `visited` on `(current_file, current_func, current_var)` (`theauditor/taint/interprocedural.py:82-97`), so only the first controller that reaches a helper is processed.
- Stage 2 appends `argument_pass` and `return_flow` frames to `call_path` (`theauditor/taint/interprocedural.py:143-173`), yet these frames never surface when later controllers are skipped.
- Stage 3 worklist entries are `(current_file, current_func, tainted_vars, depth, call_path)` with dedupe key `(current_file, current_func, tainted_vars)` (`theauditor/taint/interprocedural.py:209-223`); the first controller to taint a helper prevents all subsequent ones from being analysed.
- Stage 3 records intra-procedural hits and cross-function hops by cloning `call_path` (`theauditor/taint/interprocedural.py:271-381`), meaning that skipping a controller directly removes its evidence.
- `TaintPath` lacks an explicit call-stack field (`theauditor/taint/core.py:31-112`), and `normalize_taint_path` does not emit one (`theauditor/taint/core.py:354-377`), so even newly preserved stacks must be surfaced via schema updates.
- `deduplicate_paths` only keys on the source/sink coordinates (`theauditor/taint/propagation.py:690-707`), collapsing controller-specific records even if they differed upstream.

## Proposed Architecture

### Path Context Signature
- Introduce `CallFrame = NamedTuple("CallFrame", [("file", str), ("function", str), ("line", int)])`.
- Define `CallStackSignature = tuple[CallFrame, ...]` with ordering identical to the traversal order.
- Maintain signatures alongside `call_path` in both stages. Signatures are truncated to `max_depth + 1` frames to align with the existing depth guard (`theauditor/taint/interprocedural.py:90-91,217-218`).
- `visited` becomes `Dict[StateKey, Set[CallStackSignature]]`, where `StateKey` is `(file, function, var)` for Stage 2 and `(file, function, frozenset(vars))` for Stage 3. A new work item is skipped only if its signature already exists in the set.

### Stage 2 Changes (`trace_inter_procedural_flow_insensitive`)
1. Expand the worklist tuple to `(current_var, current_func, current_file, depth, call_path, call_signature)`.
2. When processing a state, fetch/create the signature set from `visited[state_key]`.
3. For each `argument_pass` at `theauditor/taint/interprocedural.py:143-144`, append a new `CallFrame(current_file, current_func, call_line)` to both `call_path` and `call_signature`, respecting the depth bound, then enqueue the callee with the updated signature.
4. Apply the same logic to `return_flow` transitions at `theauditor/taint/interprocedural.py:172-173` so return-driven propagation stays uniquely attributed.
5. Persist the enriched `call_path` when instantiating `TaintPath`, ensuring serialized results carry the controller context.

### Stage 3 Changes (`trace_inter_procedural_flow_cfg`)
1. Expand the Stage 3 worklist to `(current_file, current_func, tainted_vars, depth, call_path, call_signature)`.
2. Track signatures in `visited[(file, func, frozenset(vars))]` exactly as Stage 2 does.
3. When generating `cfg_call` entries at `theauditor/taint/interprocedural.py:378-381`, append `CallFrame(current_file, current_func, call_line)` to both the path and signature before enqueueing the callee.
4. Ensure intra-procedural path construction at `theauditor/taint/interprocedural.py:271-274` embeds the current signature so sink hits can be traced back to the initiating controller.
5. Preserve recursion/loop guards (`max_depth`, `max_recursion` in `theauditor/taint/interprocedural_cfg.py:64-75`) while optionally logging when signatures are dropped due to bounding.

### Serialization & Deduplication
- Extend `TaintPath` with `self.call_stack` seeded from the final signature (`theauditor/taint/core.py:31-112`) and emit it in `to_dict`.
- Update `normalize_taint_path` to guarantee a `call_stack` list in every serialized object (`theauditor/taint/core.py:354-377`).
- Modify `deduplicate_paths` to include `tuple(call_stack)` in its uniqueness key so controller-specific paths are preserved (`theauditor/taint/propagation.py:690-707`).

### Observability & Safety
- Cap the number of stored signatures per state (e.g., 32) to avoid memory spikes in large graphs; document this cap near the visited management code.
- Reuse existing debug logging (`THEAUDITOR_TAINT_DEBUG`) to report when signatures are pruned or when alternate controllers are processed, aiding future incident reviews.

## Edge Cases
- **Recursive helpers**: Signature bounding ensures repeated frames do not accumulate indefinitely; the depth guard still halts analysis at `max_depth`.
- **High-fan-out controllers**: Signature cap prevents uncontrolled memory growth; when the cap is exceeded we retain the earliest frames deterministically (document deterministic policy).
- **Missing CFG metadata**: Stage 3 continues to fall back to Stage 2 (`theauditor/taint/interprocedural.py:280-294`), and Stage 2 already records `argument_pass` frames, so the new metadata still appears.

## Testing Strategy
- Stage 2 fixture: Two controllers calling the same helper; assert two JSON entries with distinct `call_stack` frames and stable runtime.
- Stage 3 fixture: CFG-covered helper hit by two controllers; assert both `flow_sensitive` outputs carry unique stacks and no dedupe collapse.
- Performance benchmark on an existing medium project to ensure runtime/memory regression is within tolerance.
- Unit test covering `deduplicate_paths` to verify two paths identical in source/sink but different in `call_stack` are kept.

## Rollout
- Implement feature flag-free; behaviour change is deterministic improvement with no configuration surface.
- Document the new `call_stack` field in developer docs after implementation, then seek Architect review with `openspec validate update-taint-path-history --strict`.
