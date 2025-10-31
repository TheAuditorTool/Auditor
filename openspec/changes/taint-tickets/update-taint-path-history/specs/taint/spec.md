## ADDED Requirements
### Requirement: Flow-Insensitive Path Context Tracking
Stage 2 interprocedural taint analysis MUST preserve distinct controller→helper call chains even when they share the same helper signature, and emit separate `TaintPath.path` sequences for each entrypoint.

#### Scenario: Two Controllers Share a Helper
- **GIVEN** `.pf/repo_index.db` contains `function_call_args` rows showing both `controllers/admin.js:createAdmin` and `controllers/user.js:createUser` call `services/accounts.js:createAccount` on different lines
- **AND** `function_returns` / `assignments` rows map `createAccount` back into each controller via distinct `line` values
- **WHEN** Stage 2 (`trace_inter_procedural_flow_insensitive`) runs during taint analysis
- **THEN** the analyzer MUST record ≥2 `TaintPath` objects whose `path` arrays include `argument_pass` / `return_flow` elements identifying each controller and call-site line
- **AND** the Stage 2 visited-state logic MUST treat the two controllers as unique, even though they share the same helper variable name, so the second controller is not skipped.

### Requirement: Flow-Sensitive Path Context Tracking
Stage 3 CFG-based taint analysis MUST retain unique call stacks for each entrypoint, allowing multiple controllers that reach the same helper to surface separate `cfg_call` sequences with accurate line metadata.

#### Scenario: CFG Propagation with Shared Helper
- **GIVEN** Stage 3 (`trace_inter_procedural_flow_cfg`) processes two tainted controllers that both invoke `services/payments.js:chargeCard`
- **AND** `cfg_blocks` contains the helper’s CFG so the analyzer can traverse it
- **WHEN** both controllers lead to the same sink inside `chargeCard`
- **THEN** the emitted `TaintPath` list MUST include ≥2 entries whose `path` segments retain the correct caller function names, file paths, and call-site lines for each controller within the `cfg_call` elements
- **AND** the Stage 3 visited-state logic MUST differentiate the controllers via their call-stack signatures so both traversals execute even if `(file, function, tainted_vars)` is identical.

### Requirement: Serialized Call Stack Metadata
All emitted `TaintPath` dictionaries MUST include a normalized `call_stack` array that mirrors the recorded call frames and is respected by downstream deduplication.

#### Scenario: JSON Export Contains Controller Frames
- **GIVEN** the analyzer surfaces two controller→helper paths (via Stage 2 or Stage 3)
- **WHEN** `save_taint_analysis` writes `.pf/taint_analysis.json`
- **THEN** each `TaintPath` entry MUST contain a `call_stack` array ordered from entrypoint to sink, where each frame includes `file`, `function`, and `line` attributes
- **AND** `deduplicate_paths` MUST treat two entries with identical source/sink coordinates but different `call_stack` frames as distinct, so both controller-specific records remain in the final JSON.
