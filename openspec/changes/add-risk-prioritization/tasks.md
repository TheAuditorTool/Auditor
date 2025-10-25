## 0. Verification (SOP v4.20 alignment)
- [ ] 0.1 Record hypotheses, evidence, and discrepancies in `verification.md` before implementation.
- [ ] 0.2 Review `theauditor/commands/summary.py` (301 lines) to confirm current summary generation behavior.
- [ ] 0.3 Review `theauditor/extraction.py` (534 lines) to confirm current chunking behavior.
- [ ] 0.4 Capture current `.pf/readthis/` file structure (baseline: 24-27 chunked files).

## 1. Add Per-Domain Summary Generation Functions
- [ ] 1.1 Add `generate_taint_summary(raw_path, db_path)` function to `summary.py` (after line 297).
- [ ] 1.2 Add `generate_graph_summary(raw_path, db_path)` function to `summary.py`.
- [ ] 1.3 Add `generate_lint_summary(raw_path, db_path)` function to `summary.py`.
- [ ] 1.4 Add `generate_rules_summary(raw_path, db_path)` function to `summary.py`.
- [ ] 1.5 Add `generate_dependencies_summary(raw_path, db_path)` function to `summary.py`.
- [ ] 1.6 Add `generate_fce_summary(raw_path, db_path)` function to `summary.py`.
- [ ] 1.7 Add `generate_master_summary(raw_path, db_path, domain_summaries)` function to `summary.py`.
- [ ] 1.8 Verify all functions load from JSON files (not database queries) and include `query_alternative` field.

## 2. Modify Main Summary Command
- [ ] 2.1 Add `--generate-domain-summaries` flag to `summary()` command (line 15 in summary.py).
- [ ] 2.2 Implement new flow: if flag is set, call all 7 summary generation functions.
- [ ] 2.3 Write per-domain summaries to `.pf/raw/summary_<domain>.json`.
- [ ] 2.4 Write master summary to `.pf/raw/The_Auditor_Summary.json`.
- [ ] 2.5 Preserve legacy flow: without flag, generate `audit_summary.json` as before (backward compat).
- [ ] 2.6 Add import for `defaultdict` from `collections` (needed for file_counts in lint summary).

## 3. Modify Extraction Behavior
- [ ] 3.1 Update `extract_all_to_readthis()` file discovery (lines 413-427 in extraction.py).
- [ ] 3.2 Add logic to identify summary files: `filename.startswith("summary_")` or `filename == "The_Auditor_Summary.json"`.
- [ ] 3.3 Build extraction strategy: summary files → chunk if needed, raw files → skip (extractor=None).
- [ ] 3.4 Update extraction loop (after line 443): skip files with `extractor=None`, log as "raw data file (kept in /raw/ only)".
- [ ] 3.5 Verify extraction result: summary files in /readthis/, raw files stay in /raw/ only.

## 4. Pipeline Integration
- [ ] 4.1 Identify pipeline file (likely `theauditor/pipelines.py` or similar).
- [ ] 4.2 Add Stage 13 (Generate per-domain summaries) after FCE (Stage 12).
- [ ] 4.3 Invoke `aud summary --generate-domain-summaries` using Click runner or subprocess.
- [ ] 4.4 Verify stage ordering: FCE → Summary generation → Extraction.
- [ ] 4.5 Test pipeline runs without errors and summaries appear in correct locations.

## 5. Testing & Verification
- [ ] 5.1 Create `tests/test_summary_generation.py` with unit tests for all 7 summary functions.
- [ ] 5.2 Test `generate_taint_summary()` structure, size, and content.
- [ ] 5.3 Test `generate_master_summary()` combines all domains correctly.
- [ ] 5.4 Create `tests/test_extraction_skip_raw.py` to verify extraction skips raw files.
- [ ] 5.5 Run integration test: `aud full` → check `.pf/raw/` has summaries, `.pf/readthis/` has 7-8 files.
- [ ] 5.6 Verify backward compatibility: `aud summary` without flag still generates `audit_summary.json`.
- [ ] 5.7 Manual verification: check file sizes, JSON structure, query_alternative fields.

## 6. Documentation & Cleanup
- [ ] 6.1 Update CLI help text for `aud summary --help` to document `--generate-domain-summaries` flag.
- [ ] 6.2 Update README or docs to explain new consumption flow: /readthis/ for summaries, /raw/ for raw data.
- [ ] 6.3 Document master summary structure (`The_Auditor_Summary.json` format).
- [ ] 6.4 Verify OpenSpec ticket passes validation: `openspec validate add-risk-prioritization`.
- [ ] 6.5 Run project test suites: `pytest`, `ruff`, `mypy` (if applicable).

## Completion Criteria
- ✅ 7 per-domain summary functions implemented in `summary.py`
- ✅ Master summary function combines all domains
- ✅ `--generate-domain-summaries` flag generates all summaries to `.pf/raw/`
- ✅ Extraction only chunks summary files (7-8 files in /readthis/, not 24-27)
- ✅ Raw data files stay in /raw/ only
- ✅ Pipeline Stage 13 generates summaries after FCE
- ✅ Backward compatible (legacy `audit_summary.json` still generated)
- ✅ Unit tests pass for summary generation
- ✅ Integration tests pass for extraction behavior
- ✅ Manual verification confirms 7-8 files in /readthis/
- ✅ Documentation updated
