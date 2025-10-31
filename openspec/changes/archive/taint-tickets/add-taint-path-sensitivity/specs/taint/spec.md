## ADDED Requirements
### Requirement: Stage 3 CFG Argument Binding
The taint engine MUST build caller→callee argument bindings from the indexed call graph when Stage 3 (`use_cfg=True`, `stage3=True`) is enabled so that CFG analysis receives real taint state.

#### Scenario: Controller to Helper Chain
- **GIVEN** `.pf/repo_index.db` contains `function_call_args` rows linking `controllers/account.py:AccountController.create` to `services/users.py:create_user` with `argument_expr = 'req.body'` and `param_name = 'user_data'`
- **AND** CFG metadata for `create_user` exists in `cfg_blocks`
- **WHEN** `trace_taint` runs with `use_cfg=True` and `stage3=True`
- **THEN** Stage 3 MUST seed the callee entry state with the mapped parameter tainted, traverse the callee CFG, and emit a `TaintPath` covering the helper→sink hop instead of falling back to flow-insensitive tracking
- **AND** the resulting path MUST include an element of type `inter_procedural_cfg` that lists the tainted parameters or return symbol used to reach the sink

### Requirement: Path Condition Provenance
Stage 3 interprocedural paths MUST record the CFG branch conditions and sanitizers that allowed the tainted value to flow so auditors can verify the guarded execution path.

#### Scenario: Guarded Helper with Sanitizer
- **GIVEN** a helper function whose CFG contains a branch `if validate(data):` that sanitizes the tainted parameter on the true edge and forwards it to a sink on the false edge
- **WHEN** Stage 3 reports a vulnerability for the false branch
- **THEN** the emitted `TaintPath` MUST set `flow_sensitive = true`, populate `conditions` with structured entries describing the branch (e.g., `if not (validate(data))`), and include `sanitized_vars` showing which parameters were cleaned on opposing paths
- **AND** the `condition_summary` field MUST restate the branch outcome (e.g., `"validate(data) is FALSE"`) so downstream consumers can display the guarded flow without re-deriving CFG details

### Requirement: Deterministic Fallback Guardrail
The Stage 3 engine MUST detect when CFG metadata is unavailable for a callee and revert to the Stage 2 interprocedural tracker while logging the downgrade so pipelines stay factual instead of fabricating paths.

#### Scenario: Missing CFG for Helper
- **GIVEN** a repository where `function_call_args` links a tainted controller argument to `utils/format.py:safe_format`
- **AND** `cfg_blocks` has no rows for `safe_format`
- **WHEN** `trace_taint` executes with `use_cfg=True` and `stage3=True`
- **THEN** the analyzer MUST skip the Stage 3 CFG walk, fall back to `trace_inter_procedural_flow_insensitive`, and log a `[CFG]` warning explaining that the helper lacked CFG coverage
- **AND** the resulting `TaintPath` MUST omit `flow_sensitive` metadata (matching Stage 2 structure) to reflect that the path came from the fallback engine
