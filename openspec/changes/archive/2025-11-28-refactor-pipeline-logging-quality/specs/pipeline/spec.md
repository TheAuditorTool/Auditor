## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Graceful Degradation on Missing Files
**Reason**: This requirement allowed silent fallbacks when JSON files were missing, violating ZERO FALLBACK policy. The new architecture reads from database (covered by refactor-pipeline-reporting) and doesn't need file-based graceful degradation.

**Migration**: Code that silently handled missing JSON files is being removed. Database queries will hard-fail if data is missing, exposing bugs instead of hiding them.

### Requirement: Findings Aggregation Source
**Reason**: This requirement specified reading from JSON files. The new architecture (refactor-pipeline-reporting) reads from database. This requirement will be replaced by that change's spec delta.

**Migration**: The refactor-pipeline-reporting change handles findings aggregation from database. This change focuses on presentation layer only.
