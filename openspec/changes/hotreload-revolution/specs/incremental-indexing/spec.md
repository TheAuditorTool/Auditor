## ADDED Requirements

### Requirement: Hash-Based Incremental Indexing
The indexer SHALL support incremental mode that only re-indexes files whose SHA256 hash has changed since the last index run.

#### Scenario: Incremental index with changed files
- **WHEN** user runs `aud index --incremental` after modifying 5 files out of 2000
- **THEN** only the 5 modified files SHALL be re-extracted and stored
- **AND** unchanged files SHALL NOT be re-processed
- **AND** the resulting database SHALL be identical to a full rebuild

#### Scenario: Incremental index detects new files
- **WHEN** a new file is added to the project
- **THEN** incremental index SHALL detect it as new (not in previous manifest)
- **AND** the new file SHALL be fully indexed

#### Scenario: Incremental index detects deleted files
- **WHEN** a file is deleted from the project
- **THEN** incremental index SHALL detect it as deleted
- **AND** all database records for that file SHALL be removed

#### Scenario: First run without previous manifest
- **WHEN** `aud index --incremental` runs with no previous manifest
- **THEN** it SHALL perform a full index (all files treated as new)
- **AND** it SHALL save the manifest for future incremental runs

### Requirement: Selective Database Deletion
The indexer SHALL delete only the changed file's data from the database, not truncate entire tables.

#### Scenario: Delete file data preserves other files
- **WHEN** file A is modified and re-indexed
- **THEN** only file A's rows SHALL be deleted from all tables
- **AND** file B's rows SHALL remain untouched

#### Scenario: CFG records deleted with proper cascade
- **WHEN** a file with CFG data is re-indexed
- **THEN** cfg_blocks for that file SHALL be deleted
- **AND** cfg_edges referencing those blocks SHALL be deleted
- **AND** cfg_block_statements for those blocks SHALL be deleted

### Requirement: File Watching Daemon
The system SHALL provide a background daemon that watches for file changes and auto-triggers incremental indexing.

#### Scenario: Daemon starts and watches directory
- **WHEN** user runs `aud watch`
- **THEN** a background daemon SHALL start watching the project directory
- **AND** it SHALL print confirmation message

#### Scenario: Daemon triggers on file save
- **WHEN** user saves a source file while daemon is running
- **THEN** daemon SHALL detect the change within 2 seconds
- **AND** daemon SHALL trigger incremental index on that file

#### Scenario: Daemon debounces rapid changes
- **WHEN** user saves multiple files in quick succession (< 1 second apart)
- **THEN** daemon SHALL wait for changes to settle (1 second debounce)
- **AND** daemon SHALL batch all changes into single incremental index

### Requirement: Periodic Full Rebuild Safety Valve
The system SHALL automatically trigger a full rebuild after threshold incremental updates to prevent drift.

#### Scenario: Auto full rebuild after 50 incrementals
- **WHEN** 50 incremental updates have occurred since last full rebuild
- **THEN** next index SHALL automatically perform full rebuild
- **AND** incremental counter SHALL reset to 0

#### Scenario: Auto full rebuild after 24 hours
- **WHEN** 24 hours have passed since last full rebuild
- **THEN** next index SHALL automatically perform full rebuild
- **AND** timestamp SHALL be updated

#### Scenario: User can force full rebuild
- **WHEN** user runs `aud index --full`
- **THEN** full rebuild SHALL occur regardless of incremental state
- **AND** incremental metadata SHALL be reset

### Requirement: JavaScript Global Cache from Database
After incremental indexing, the JavaScript global function cache SHALL be rebuilt from the database, not by re-parsing all files.

#### Scenario: Global cache rebuilt from symbols table
- **WHEN** incremental index completes
- **THEN** global function parameter cache SHALL be rebuilt by querying symbols table
- **AND** cross-file parameter resolution SHALL work correctly

#### Scenario: Changed function definition updates callers
- **WHEN** file A defines function `foo(x, y)` and file B calls `foo()`
- **AND** file A is modified to change signature to `foo(x, y, z)`
- **THEN** incremental index SHALL update the global cache
- **AND** file B's call resolution SHALL reflect the new signature
