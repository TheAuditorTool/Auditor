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

### Requirement: Findings Aggregation Source
The pipeline final status SHALL be determined by reading JSON artifact files from .pf/raw/ directory.

#### Scenario: JSON files read for aggregation
- **WHEN** the pipeline generates final status
- **THEN** the pipeline SHALL read taint_analysis.json, vulnerabilities.json, and findings.json
- **AND** severity counts SHALL be aggregated from these files

### Requirement: Graceful Degradation on Missing Files
The pipeline SHALL gracefully handle missing or malformed JSON files during aggregation.

#### Scenario: Missing JSON file handling
- **WHEN** a JSON artifact file does not exist
- **THEN** the pipeline SHALL treat that file's findings as empty
- **AND** the pipeline SHALL continue processing other files

#### Scenario: Missing junction arrays handled
- **WHEN** junction arrays are not present in extraction output (legacy format)
- **THEN** storage SHALL check for new keys first
- **AND** storage SHALL fall back to legacy nested format if new keys absent
- **AND** a deprecation warning SHALL be logged for legacy format

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

