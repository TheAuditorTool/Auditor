## Why
- Stage 2’s worklist de-duplicates states on `(current_file, current_func, current_var)` before processing (`theauditor/taint/interprocedural.py:82-97`), so the first controller that enters a shared helper suppresses every subsequent caller even though their `call_path` differs.
- Stage 3 repeats the pattern with `(current_file, current_func, tainted_vars)` (`theauditor/taint/interprocedural.py:209-223`), dropping additional entrypoints that send the same tainted parameter set into the helper and leaving only a single CFG trace in `taint_analysis.json`.
- `TaintPath` objects are populated from the accumulated `call_path` (`theauditor/taint/interprocedural.py:271-379`), yet serialization currently has no place to persist a call stack, so losing the traversal means auditors cannot reconstruct which controllers reach the sink.
- Downstream deduplication only keys on the source/sink coordinates (`theauditor/taint/propagation.py:690-707`), so even when we record multiple paths we must keep the shortest per controller instead of collapsing all evidence into one generic chain.

## Current Behavior (Verified)
- Stage 2 enqueues `(source_var, source_function, source_file, depth, path)` at `theauditor/taint/interprocedural.py:82` and appends `{"type": "argument_pass", ...}` per hop at `theauditor/taint/interprocedural.py:143-144`, but because `visited` ignores the call-site (`theauditor/taint/interprocedural.py:93-97`) a second controller never executes the helper loop.
- Stage 3 builds `call_path` frames via `cfg_call` entries at `theauditor/taint/interprocedural.py:378-381`, yet the fixed-point guard stops new paths after the first `(file, func, tainted_vars)` tuple, so `call_path` never contains the alternate controller frames.
- `TaintPath` and `normalize_taint_path` lack a `call_stack` payload (`theauditor/taint/core.py:31-112` and `theauditor/taint/core.py:354-377`), so even if we retained multiple paths the JSON output would not expose the ordered frames for automated consumers.

## Goals
1. Preserve unique controller→helper call stacks for both Stage 2 (flow-insensitive) and Stage 3 (CFG flow-sensitive) analyses without reintroducing uncontrolled path explosion.
2. Emit structured call-context metadata in each `TaintPath` so auditors can attribute vulnerabilities to specific entrypoints, including file, function, and call-site line numbers.
3. Maintain existing termination guarantees (`max_depth`, recursion limits) while bounding memory usage of call-stack signatures.
4. Keep downstream interfaces stable by documenting and normalizing the new metadata through `TaintPath.to_dict`, `normalize_taint_path`, and JSON serialization.

## Non-Goals
- Do not redesign the taint data model beyond call-context tracking; classifications, severity, and sanitizer logic remain untouched.
- Do not alter Stage 1 source discovery or Stage 2/Stage 3 taint propagation heuristics outside of the path-tracking fix.
- Do not modify `deduplicate_paths` semantics beyond recognizing distinct call stacks when selecting representative paths.

## Detailed Implementation Plan

### 1. Path Context Signature Model
- Introduce a lightweight `CallFrame` structure (tuple or `NamedTuple`) capturing `(file, function, line)` for each hop captured today in `call_path` (Stage 2 `argument_pass` / `return_flow`, Stage 3 `cfg_call`) with data sourced from existing dictionary payloads.
- Define `CallStackSignature = tuple[CallFrame, ...]` and construct it incrementally whenever we extend `call_path`. The signature MUST be order-sensitive and trimmed to `max_depth + 1` frames to respect existing termination limits (`theauditor/taint/interprocedural.py:90-91`).
- Persist the signature alongside taint state in the worklist entries and include it in the `state_key` deduplication logic so distinct call stacks reach helpers even if `(file, function, varset)` matches.

### 2. Stage 2 Engine Updates (`trace_inter_procedural_flow_insensitive`)
- Expand the worklist tuple to `(current_var, current_function, current_file, depth, call_path, call_signature)` and initialize the seed signature with the source frame (`theauditor/taint/interprocedural.py:82`).
- Replace `visited: Set[tuple[str, str, str]]` with a dictionary mapping `(current_file, current_func, current_var)` to a set of signatures; a new state is only skipped when its signature already exists for that triple.
- When appending `argument_pass` entries at `theauditor/taint/interprocedural.py:143-144`, generate the corresponding `CallFrame` from `current_file`, `current_func`, and `call_line`, append it to both `call_path` and the signature (respecting depth limit), and enqueue the callee with the new signature.
- Apply the same strategy to return propagation at `theauditor/taint/interprocedural.py:172-173`, including `(caller_file, caller_func, call_line)` so controllers collecting helper return values remain distinguishable.
- Ensure `paths.append(TaintPath(...))` receives the enriched `call_path`, preserving the per-entrypoint context Stage 2 generates.

### 3. Stage 3 Engine Updates (`trace_inter_procedural_flow_cfg`)
- Extend the Stage 3 worklist tuple defined at `theauditor/taint/interprocedural.py:209` to carry the call-stack signature and propagate it through recursive calls.
- Update `visited` (currently `Set[tuple[str, str, frozenset]]` at `theauditor/taint/interprocedural.py:211-223`) to map `(current_file, current_func, frozenset(tainted_vars))` to a bounded set of signatures, mirroring the Stage 2 approach.
- When constructing `new_path = call_path + [...]` at `theauditor/taint/interprocedural.py:378-381`, derive a `CallFrame` from `(current_file, current_func, call_line)` and append it to both `call_path` and the signature before pushing the callee onto the worklist.
- Guarantee that intra-procedural findings at `theauditor/taint/interprocedural.py:271-274` also carry the current signature so `TaintPath` accurately reflects the controller that initiated the helper traversal.
- Preserve existing recursion guards (`self.max_recursion` in `theauditor/taint/interprocedural_cfg.py:64-75` and Stage 3 `depth > max_depth` check at `theauditor/taint/interprocedural.py:217-218`) to avoid runaway path growth.

### 4. Shared Utilities & Serialization
- Extend `TaintPath` (`theauditor/taint/core.py:31-112`) with a `call_stack` attribute populated from the final signature. Update `to_dict` to emit `call_stack` as an ordered list of frames containing `file`, `function`, and `line` values.
- Update `normalize_taint_path` (`theauditor/taint/core.py:354-377`) to ensure `call_stack` exists and defaults to an empty list for backward compatibility.
- Enhance `deduplicate_paths` (`theauditor/taint/propagation.py:690-707`) so it treats `call_stack` as part of the uniqueness key, allowing multiple controller-specific paths to coexist even for the same source/sink coordinate.
- Document the new metadata in `openspec/changes/update-taint-path-history/specs/taint/spec.md` and adjust any downstream serializers or exporters under `theauditor/taint/__init__.py:16-148` that expose `TaintPath` objects.

### 5. Performance, Safety, and Observability
- Bound the maximum number of stored signatures per `(file, function, varset)` using an LRU or simple length check anchored to `max_depth` to prevent memory spikes in large call graphs.
- Emit debug logs under `THEAUDITOR_TAINT_DEBUG` when signature pruning occurs, mirroring existing diagnostic patterns at `theauditor/taint/interprocedural.py:98-355`.
- Update developer documentation (`openspec/changes/update-taint-path-history/specs/taint/spec.md`) to state that Stage 2/Stage 3 now rely on signature-aware deduplication so future contributors maintain the invariant.

## Testing Strategy
1. Unit/regression fixture where two controllers reach the same helper and Stage 2 must emit two `TaintPath` entries with different `call_stack` frames; verify via golden JSON in `tests/`.
2. CFG-backed fixture covering Stage 3 to ensure `cfg_call` sequences retain both controllers’ frames and `flow_sensitive` metadata remains intact.
3. Performance regression test on an existing large project to confirm signature tracking does not materially change runtime or memory (budget: ±5%).
4. JSON schema assertion to guarantee `call_stack` is always present and correctly ordered.

## Rollout & Tooling
- Update developer notes in this change directory, then run `openspec validate update-taint-path-history --strict` prior to requesting Architect review.
- Ensure CI includes the new regression fixtures and expand lint/type coverage if new helper types or dataclasses are introduced.

## Verification Alignment
- Verification findings and line-level evidence are recorded in `openspec/changes/update-taint-path-history/verification.md`, providing traceability back to the current implementation.
