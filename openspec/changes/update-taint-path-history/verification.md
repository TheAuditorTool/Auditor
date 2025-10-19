## Hypotheses
- H1: Stage 2 flow-insensitive interprocedural taint tracking collapses distinct call chains because it deduplicates states solely by `(current_file, current_function, current_var)`, causing later callers with the same signature to be skipped.
- H2: Stage 3 CFG-based flow-sensitive taint tracking uses the same fixed-point deduplication keyed only on `(current_file, current_func, tainted_vars)`, so additional entrypoints that reach the same callee lose their call history.
- H3: The emitted `TaintPath.path` sequence is built from the accumulated `call_path`, so once a converging call chain is skipped the analyzer cannot reconstruct a second path for reporting.

## Evidence
- Stage 2 seeds the worklist with `(source_var, source_function, source_file, depth, path)` at `theauditor/taint/interprocedural.py:82` and marks a state as visited using `state_key = (current_file, current_func, current_var)` at `theauditor/taint/interprocedural.py:93-97`, so another controller that reaches the same helper-variable triple is discarded the moment it dequeues.
- Stage 3 mirrors the pattern by constructing `worklist: List[tuple[str, str, frozenset, int, list]]` at `theauditor/taint/interprocedural.py:209` and deriving `state_key = (current_file, current_func, tainted_vars)` at `theauditor/taint/interprocedural.py:220-223`, preventing additional entrypoints from traversing the helper once a matching tainted-var set has already been analyzed.
- Vulnerability reporting clones the accumulated `call_path` into the emitted `TaintPath` via `vuln_path = call_path + [...]` at `theauditor/taint/interprocedural.py:271-274` and `theauditor/taint/interprocedural.py:378-381`; when a second caller is never processed, its call frames never appear in the final JSON.

## Discrepancies
- The analyzer is expected to surface every distinct controller→helper chain, yet the fixed-point deduplication drops legitimate paths whenever two entrypoints share the same helper signature, so auditors cannot trace which controllers reach a sink even though the vulnerability persists.
