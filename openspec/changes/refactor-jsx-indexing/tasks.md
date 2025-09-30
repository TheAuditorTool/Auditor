## 1. Analysis
- [x] 1.1 Capture current indexer outputs on the `plant` sample (baseline DB + notes)
- [x] 1.2 Document precise false-positive patterns and missing-table inserts in extractor + database layers

## 2. Dual-Pass Pipeline Hardening
- [x] 2.1 Ensure AST parser batches support explicit jsx_mode switching and cache separation
- [x] 2.2 Update indexer orchestration to persist pass metadata and avoid duplicate inserts
- [x] 2.3 Verify `_jsx` tables populate with preserved-mode data and expose unified views as expected

## 3. Extractor Accuracy
- [x] 3.1 Refine React/Vue heuristics to drop backend/controller false positives
- [x] 3.2 Scope hook detection so only real `use*` calls inside React components are captured
- [x] 3.3 Fix SQL detector to ignore non-SQL strings and tag real queries with command + tables
- [x] 3.4 Store imports/api endpoints (refs table population) during extraction and indexing

## 4. Framework Detection Persistence
- [x] 4.1 Run inline framework detection before indexing and persist results + safe sinks inside the same transaction
- [x] 4.2 Maintain backward-compatible JSON artefacts for older tooling

## 5. Validation
- [x] 5.1 Add automated regression covering dual-pass outputs on fixture project
- [x] 5.2 Run full `aud index`, `aud taint-analyze`, and rules smoke tests to confirm db contract stability
