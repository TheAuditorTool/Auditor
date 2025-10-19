## 0. Verification
- [x] Confirm Stage 2 and Stage 3 deduplicate states without call-site context (`theauditor/taint/interprocedural.py:93-97`, `theauditor/taint/interprocedural.py:220-223`), collapsing legitimate paths (see verification log).

## 1. Path State Model
- [ ] Specify the `CallFrame` / `CallStackSignature` structures and update worklist tuple definitions in Stage 2 (`theauditor/taint/interprocedural.py:82`) and Stage 3 (`theauditor/taint/interprocedural.py:209`) to include signatures.
- [ ] Document the new invariants for `visited` handling (signature bounding, depth capping) directly in code comments to prevent future regressions.

## 2. Stage 2 Flow-Insensitive Updates
- [ ] Refactor `trace_inter_procedural_flow_insensitive` so `visited` maps `(file, function, var)` to bounded signature sets before skipping (`theauditor/taint/interprocedural.py:93-105`).
- [ ] Extend the enqueue logic for `argument_pass` and `return_flow` steps (`theauditor/taint/interprocedural.py:143-173`) to append frames to both `call_path` and the signature while respecting `max_depth`.
- [ ] Create a regression that exercises two controllers sharing a helper and proves Stage 2 now emits two `TaintPath` objects with distinct `call_stack` entries.

## 3. Stage 3 Flow-Sensitive Updates
- [ ] Update the Stage 3 worklist / visited structures (`theauditor/taint/interprocedural.py:209-223`) to include signature tracking, mirroring Stage 2.
- [ ] Ensure `cfg_call` traversal (`theauditor/taint/interprocedural.py:378-381`) and intra-procedural findings (`theauditor/taint/interprocedural.py:271-274`) clone and extend signatures before enqueuing/recording paths.
- [ ] Add a CFG-backed regression where two controllers hit the same helper and verify both `flow_sensitive` paths retain unique `call_stack` frames.

## 4. Reporting & Tests
- [ ] Extend `TaintPath` serialization (`theauditor/taint/core.py:31-112`) and `normalize_taint_path` (`theauditor/taint/core.py:354-377`) to include ordered `call_stack` data; update `deduplicate_paths` (`theauditor/taint/propagation.py:690-707`) to treat the stack as part of the uniqueness key.
- [ ] Update or add fixture snapshots asserting the new JSON shape, then run full tests plus `openspec validate update-taint-path-history --strict`.
