# pipeline Specification

## Purpose
Pipeline orchestration for TheAuditor, including final status reporting and findings aggregation after all analysis phases complete.
## Requirements
### Requirement: Final Status Reporting
The pipeline SHALL report final status after all analysis phases complete, indicating security findings severity.

#### Scenario: Status reflects findings severity
- **WHEN** the pipeline completes all analysis phases
- **THEN** final status SHALL indicate whether critical/high severity issues were found
- **AND** status SHALL be displayed to the user via full.py

#### Scenario: Clean status when no security issues
- **WHEN** the pipeline completes with no critical or high severity security findings
- **THEN** final status SHALL indicate "[CLEAN]"

#### Scenario: Critical status when critical issues found
- **WHEN** the pipeline completes with critical severity security findings
- **THEN** final status SHALL indicate "[CRITICAL]"
- **AND** exit code SHALL be CRITICAL_SEVERITY

### Requirement: Findings Return Structure
The pipeline SHALL return findings counts in a dict consumed by full.py and journal.py.

#### Scenario: Findings dict structure
- **WHEN** the pipeline completes
- **THEN** return dict SHALL include findings.critical, findings.high, findings.medium, findings.low
- **AND** findings.total_vulnerabilities SHALL be included for journal.py

### Requirement: Vue Component Junction Data Extraction
The JavaScript extractor pipeline SHALL extract Vue component props, emits, and setup returns as flat arrays suitable for direct database insertion.

#### Scenario: Props extraction produces flat records
- **WHEN** a Vue component uses `defineProps()` with a props definition
- **THEN** the extractor SHALL produce a `vue_component_props` array
- **AND** each record SHALL contain `component_name`, `prop_name`, `prop_type`, `is_required`, `default_value`

#### Scenario: Emits extraction produces flat records
- **WHEN** a Vue component uses `defineEmits()` with an emits definition
- **THEN** the extractor SHALL produce a `vue_component_emits` array
- **AND** each record SHALL contain `component_name`, `emit_name`, `payload_type`

#### Scenario: Setup returns extraction produces flat records
- **WHEN** a Vue component's setup function returns values
- **THEN** the extractor SHALL produce a `vue_component_setup_returns` array
- **AND** each record SHALL contain `component_name`, `return_name`, `return_type`

#### Scenario: Unparseable definitions handled gracefully
- **WHEN** a `defineProps()` or `defineEmits()` argument cannot be parsed
- **THEN** the extractor SHALL log a warning
- **AND** the extractor SHALL return an empty array for that component
- **AND** extraction SHALL continue for other components

### Requirement: Angular Component Style Path Extraction
The JavaScript extractor pipeline SHALL extract Angular component style paths as flat arrays.

#### Scenario: StyleUrls extraction produces flat records
- **WHEN** an Angular component uses `@Component` decorator with `styleUrls`
- **THEN** the extractor SHALL produce an `angular_component_styles` array
- **AND** each record SHALL contain `component_name`, `style_path`

#### Scenario: Single styleUrl handled
- **WHEN** an Angular component uses `styleUrl` (singular) instead of `styleUrls`
- **THEN** the extractor SHALL produce a single style record with that path

### Requirement: Angular Module Junction Data Extraction
The JavaScript extractor pipeline SHALL extract Angular module metadata as flat junction arrays.

#### Scenario: Module declarations extraction
- **WHEN** an Angular module uses `@NgModule` decorator with `declarations`
- **THEN** the extractor SHALL produce an `angular_module_declarations` array
- **AND** each record SHALL contain `module_name`, `declaration_name`, `declaration_type`

#### Scenario: Module imports extraction
- **WHEN** an Angular module uses `@NgModule` decorator with `imports`
- **THEN** the extractor SHALL produce an `angular_module_imports` array
- **AND** each record SHALL contain `module_name`, `imported_module`

#### Scenario: Module providers extraction
- **WHEN** an Angular module uses `@NgModule` decorator with `providers`
- **THEN** the extractor SHALL produce an `angular_module_providers` array
- **AND** each record SHALL contain `module_name`, `provider_name`, `provider_type`

#### Scenario: Module exports extraction
- **WHEN** an Angular module uses `@NgModule` decorator with `exports`
- **THEN** the extractor SHALL produce an `angular_module_exports` array
- **AND** each record SHALL contain `module_name`, `exported_name`

### Requirement: Batch Aggregation of Junction Arrays
The JavaScript batch template SHALL aggregate all junction arrays from individual extractors.

#### Scenario: Vue junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `vue_component_props`, `vue_component_emits`, `vue_component_setup_returns` keys

#### Scenario: Angular junction arrays aggregated
- **WHEN** the batch template processes extraction results
- **THEN** `extracted_data` SHALL include `angular_component_styles`, `angular_module_declarations`, `angular_module_imports`, `angular_module_providers`, `angular_module_exports` keys

### Requirement: Python Storage Direct Iteration
The Python storage layer SHALL iterate junction arrays directly without JSON parsing.

#### Scenario: Core language junction storage
- **WHEN** `func_params` array is provided to storage
- **THEN** storage SHALL call `add_func_param()` for each record
- **AND** storage SHALL NOT parse JSON strings
- **STATUS:** PENDING (Phase 9)

#### Scenario: Data flow junction storage
- **WHEN** `assignment_source_vars` array is provided to storage
- **THEN** storage SHALL call `add_assignment_source_var()` for each record
- **AND** storage SHALL NOT parse JSON strings
- **STATUS:** PENDING (Phase 9)

#### Scenario: Import junction storage
- **WHEN** `import_specifiers` array is provided to storage
- **THEN** storage SHALL call `add_import_specifier()` for each record
- **AND** storage SHALL NOT parse JSON strings
- **STATUS:** PENDING (Phase 9)

#### Scenario: Sequelize junction storage
- **WHEN** `sequelize_model_fields` array is provided to storage
- **THEN** storage SHALL call `add_sequelize_model_field()` for each record
- **AND** storage SHALL NOT parse JSON strings
- **STATUS:** PENDING (Phase 9)

### Requirement: Console Output Rendering
The pipeline SHALL render console output through a single RichRenderer instance that implements the PipelineObserver protocol.

#### Scenario: Single output authority
- **WHEN** the pipeline executes any phase
- **THEN** all console output SHALL be routed through RichRenderer
- **AND** no direct print() calls SHALL exist in pipeline execution code

#### Scenario: TTY detection for Rich mode
- **WHEN** the pipeline starts and stdout is a TTY
- **THEN** RichRenderer SHALL use Rich Live display with updating table
- **AND** refresh rate SHALL be 4 times per second

#### Scenario: Non-TTY fallback mode
- **WHEN** the pipeline starts and stdout is NOT a TTY (CI/CD)
- **THEN** RichRenderer SHALL fall back to simple sequential prints
- **AND** no Rich Live context SHALL be created

#### Scenario: Quiet mode suppression
- **WHEN** the pipeline runs with --quiet flag
- **THEN** RichRenderer SHALL suppress all non-error output
- **AND** errors SHALL still be displayed to stderr

### Requirement: Parallel Track Buffering
The pipeline SHALL buffer parallel track output and flush atomically when each track completes.

#### Scenario: Buffer creation on track start
- **WHEN** a parallel track (A, B, or C) begins execution
- **THEN** RichRenderer SHALL create a dedicated buffer for that track
- **AND** all output from that track SHALL be captured in the buffer

#### Scenario: No interleaved output during parallel execution
- **WHEN** multiple tracks are executing simultaneously
- **THEN** their outputs SHALL NOT interleave on the console
- **AND** each track's buffer SHALL remain isolated

#### Scenario: Atomic buffer flush on track completion
- **WHEN** a parallel track completes execution
- **THEN** RichRenderer SHALL flush that track's entire buffer as a single atomic block
- **AND** the block SHALL be visually separated with headers

#### Scenario: Buffer memory limit
- **WHEN** a track produces output
- **THEN** buffer size SHALL be limited to 50 lines per track
- **AND** excess lines SHALL be truncated with indication

### Requirement: Rich Live Dashboard
The pipeline SHALL display a live-updating status table during execution using the Rich library.

#### Scenario: Table structure
- **WHEN** the Rich Live display is active
- **THEN** the table SHALL have columns: Phase, Status, Time
- **AND** each registered phase SHALL have a row in the table

#### Scenario: Phase status updates
- **WHEN** a phase transitions state (pending -> running -> success/failed)
- **THEN** the corresponding table row SHALL update immediately
- **AND** elapsed time SHALL update in real-time for running phases

#### Scenario: Stage headers
- **WHEN** a new stage (1-4) begins
- **THEN** a visual header SHALL be displayed
- **AND** the header SHALL indicate stage number and name

#### Scenario: Final summary
- **WHEN** all phases complete
- **THEN** RichRenderer SHALL display a summary showing total phases, successes, and failures
- **AND** the summary SHALL indicate overall pipeline status

### Requirement: PhaseResult Data Contract
The pipeline execution functions SHALL return PhaseResult objects instead of loose dictionaries.

#### Scenario: PhaseResult structure
- **WHEN** any pipeline function completes execution
- **THEN** it SHALL return a PhaseResult with: name, status, elapsed, stdout, stderr, exit_code
- **AND** status SHALL be a TaskStatus enum value

#### Scenario: JSON serialization
- **WHEN** PhaseResult.to_dict() is called
- **THEN** the result SHALL be JSON-serializable
- **AND** status SHALL be converted to string value

#### Scenario: Success property
- **WHEN** PhaseResult.success is accessed
- **THEN** it SHALL return True only if status is TaskStatus.SUCCESS

### Requirement: Taint Analysis Output Capture
The taint analysis function SHALL capture its stdout/stderr output for buffered display.

#### Scenario: Output redirection during taint execution
- **WHEN** run_taint_sync() executes
- **THEN** stdout and stderr SHALL be redirected to StringIO buffers
- **AND** no output SHALL leak to console during execution

#### Scenario: Captured output in PhaseResult
- **WHEN** run_taint_sync() completes
- **THEN** captured stdout SHALL be in PhaseResult.stdout
- **AND** captured stderr SHALL be in PhaseResult.stderr

#### Scenario: Output appears with track results
- **WHEN** Track A (Taint) buffer is flushed
- **THEN** taint output SHALL appear within the Track A section
- **AND** output SHALL NOT appear after pipeline completion message

### Requirement: Schema Loading Silence
The schema module SHALL NOT produce console output during import.

#### Scenario: Silent schema load
- **WHEN** the schema module is imported by any subprocess
- **THEN** no "[SCHEMA] Loaded N tables" message SHALL be printed
- **AND** schema validation SHALL still occur via assert statement

### Requirement: Readthis Folder Removal
The pipeline SHALL NOT create or reference the .pf/readthis/ directory.

#### Scenario: No readthis directory creation
- **WHEN** the pipeline executes
- **THEN** .pf/readthis/ directory SHALL NOT be created
- **AND** no files SHALL be moved to readthis location

#### Scenario: No readthis references in output
- **WHEN** the pipeline displays summary or tips
- **THEN** no mention of readthis directory SHALL appear
- **AND** tips SHALL reference .pf/raw/ for artifacts instead

