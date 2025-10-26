# Verification Report - add-risk-prioritization
Generated: 2025-10-26
SOP Reference: Standard Operating Procedure v4.20

## Hypotheses & Evidence

### 1. Current summary generation produces per-domain summaries
- **Hypothesis**: `theauditor/commands/summary.py` already generates per-domain summaries like `summary_taint.json`, `summary_graph.json`, etc.
- **Evidence**: `theauditor/commands/summary.py:15-259` generates ONE file only: `audit_summary.json` with aggregated stats.
- **Evidence**: No functions named `generate_taint_summary()`, `generate_graph_summary()`, etc. exist in summary.py.
- **Result**: **FALSE** — only a single aggregated summary exists, no per-domain summaries.

### 2. Extraction already selectively chunks only certain files
- **Hypothesis**: `theauditor/extraction.py` has logic to skip raw files and only chunk summaries.
- **Evidence**: `theauditor/extraction.py:413-427` builds extraction strategy with same treatment for ALL files: `extraction_strategy.append((filename, 100, _copy_as_is))`.
- **Evidence**: `theauditor/extraction.py:437-464` processes all files in /raw/ without discrimination.
- **Result**: **FALSE** — extraction chunks ALL files >65KB, resulting in 24-27 chunked files in /readthis/.

### 3. Master summary combining all domains already exists
- **Hypothesis**: There's a master summary file that combines top findings across all domains.
- **Evidence**: `theauditor/commands/summary.py:21-34` creates `audit_summary` with overall stats only (total_findings_by_severity, metrics_by_phase).
- **Evidence**: No file named `The_Auditor_Summary.json` or `summary_full.json` exists in output.
- **Evidence**: Current `audit_summary.json` is statistics-only, not a findings list.
- **Result**: **FALSE** — no master summary with top findings across domains exists.

### 4. Raw data files are not copied to /readthis/
- **Hypothesis**: Raw data files (taint_analysis.json, graph_analysis.json) stay in /raw/ only.
- **Evidence**: `theauditor/extraction.py:413-427` discovers ALL files in /raw/ and adds them to extraction strategy.
- **Evidence**: Manual check of test project shows files like `taint_analysis_chunk01.json`, `fce_chunk01.json` in /readthis/.
- **Result**: **FALSE** — all raw files are currently chunked and copied to /readthis/.

### 5. Current /readthis/ contains 7-8 summary files
- **Hypothesis**: `/readthis/` already has focused summaries instead of many chunked files.
- **Evidence**: Manual check shows 24-27 files in /readthis/ with names like `taint_analysis_chunk01.json`, `fce_chunk02.json`, `lint_chunk01.json`.
- **Evidence**: `theauditor/extraction.py:470-506` creates `extraction_summary.json` listing all extracted files (count: 24-27).
- **Result**: **FALSE** — /readthis/ has 24-27 chunked files, not 7-8 summaries.

### 6. Summary functions load from database queries
- **Hypothesis**: Summary generation should query the database directly for findings.
- **Evidence**: `theauditor/commands/summary.py:94-168` loads from JSON files: `raw_path / "lint.json"`, `raw_path / "patterns.json"`, `raw_path / "graph_analysis.json"`, etc.
- **Evidence**: Only one database query exists: `_load_frameworks_from_db()` at lines 261-297.
- **Result**: **FALSE** (but this is CORRECT) — current architecture loads from JSON files, not database. This should be preserved in new implementation.

### 7. Pipeline includes stage to generate summaries
- **Hypothesis**: Pipeline already has a stage that generates per-domain summaries.
- **Evidence**: Need to check pipeline file (likely `theauditor/pipelines.py`).
- **Evidence**: Current `audit_summary.json` is generated, but timing unclear.
- **Result**: **UNKNOWN** — requires pipeline file inspection. Likely needs NEW Stage 13 to generate per-domain summaries.

### 8. Each summary references aud query alternatives
- **Hypothesis**: Existing summaries already mention "This domain can also be queried with: aud query --{domain}".
- **Evidence**: `theauditor/commands/summary.py` generates `audit_summary.json` with no such references.
- **Evidence**: No JSON files in /raw/ or /readthis/ contain "query_alternative" or "aud query" text.
- **Result**: **FALSE** — no query alternatives mentioned in current output.

## Discrepancies & Alignment Notes

### Discrepancy 1: No per-domain summaries exist
- **Current**: Single `audit_summary.json` with aggregated stats only.
- **Required**: 6-7 per-domain summaries (`summary_taint.json`, `summary_graph.json`, etc.) + 1 master summary (`The_Auditor_Summary.json`).
- **Impact**: Need to create 7 new summary generation functions in `summary.py`.

### Discrepancy 2: Extraction chunks everything
- **Current**: All files in /raw/ are chunked to /readthis/ (24-27 files).
- **Required**: Only summary files chunked, raw files stay in /raw/ (7-8 files in /readthis/).
- **Impact**: Modify extraction strategy building (lines 413-427) and extraction loop (lines 437-464) to skip non-summary files.

### Discrepancy 3: No master summary combining domains
- **Current**: `audit_summary.json` has stats only, no top findings list.
- **Required**: `The_Auditor_Summary.json` with top 20-30 findings across ALL domains, sorted by severity.
- **Impact**: Create `generate_master_summary()` function that aggregates findings from all per-domain summaries.

### Discrepancy 4: No pipeline stage for summary generation
- **Current**: `audit_summary.json` generation timing unclear (possibly after extraction?).
- **Required**: Stage 13 runs after FCE (Stage 12), before extraction (Stage 14).
- **Impact**: Add new pipeline stage to invoke `aud summary --generate-domain-summaries`.

### Discrepancy 5: No query alternative references
- **Current**: No mention of `aud blueprint` or `aud query` in any output files.
- **Required**: Each summary includes "query_alternative" field referencing structured query commands.
- **Impact**: Add `query_alternative` field to all summary generation functions.

## Baseline Metrics (Before Implementation)

**Current /readthis/ structure** (manual inspection):
- Total files: 24-27 chunked JSON files
- Examples: `taint_analysis_chunk01.json`, `taint_analysis_chunk02.json`, `fce_chunk01.json`, `lint_chunk01.json`, etc.
- Size: Varies, typically 200-500 KB per chunk
- **Problem**: Too many files, nobody reads them

**Current /raw/ structure**:
- Total files: ~18 raw JSON files
- Examples: `taint_analysis.json`, `graph_analysis.json`, `lint.json`, `patterns.json`, `fce.json`, `deps.json`, `audit_summary.json`
- Size: Raw files 500KB-3MB, `audit_summary.json` is ~8 KB
- **No summaries**: Only stats file (`audit_summary.json`), no per-domain summaries

**Current summary.py behavior**:
- Function: `summary(root, raw_dir, out)` at lines 15-259
- Loads from: lint.json, patterns.json, graph_analysis.json, taint_analysis.json, fce.json, deps.json (JSON files)
- Aggregates: By severity (critical, high, medium, low, info)
- Output: Single `audit_summary.json` with metrics_by_phase, total_findings_by_severity
- **Missing**: Per-domain summaries, master findings list, query alternatives

**Current extraction.py behavior**:
- Function: `extract_all_to_readthis(root_path_str, budget_kb)` at lines 378-534
- Strategy: Chunk ALL files in /raw/ if >65KB (lines 413-427)
- Chunker: `_chunk_large_file(raw_path, max_chunk_size)` at lines 28-363
- Result: 24-27 files in /readthis/ (all raw outputs chunked)
- **Problem**: No selectivity, everything chunked

## Target Metrics (After Implementation)

**Target /readthis/ structure**:
- Total files: 7-8 summary files
- Examples: `summary_taint.json`, `summary_graph.json`, `summary_lint.json`, `summary_rules.json`, `summary_dependencies.json`, `summary_fce.json`, `The_Auditor_Summary.json`
- Size: ≤50 KB per domain summary, ≤100 KB for master summary (can be chunked if larger)
- **Fixed**: Human-readable, focused summaries only

**Target /raw/ structure**:
- Total files: ~25 files (18 raw + 7 summaries)
- New files: `summary_taint.json`, `summary_graph.json`, `summary_lint.json`, `summary_rules.json`, `summary_dependencies.json`, `summary_fce.json`, `The_Auditor_Summary.json`
- Existing files: Unchanged (taint_analysis.json, graph_analysis.json, etc.)
- **Enhanced**: Summaries stored alongside raw data

**Target summary.py behavior**:
- New flag: `--generate-domain-summaries`
- New functions: 7 summary generators (`generate_taint_summary()`, `generate_graph_summary()`, etc.)
- Output: 7 per-domain summaries + 1 master summary to `.pf/raw/`
- Backward compat: Legacy `aud summary` (no flag) still generates `audit_summary.json`
- **Feature**: Each summary includes `query_alternative` field

**Target extraction.py behavior**:
- Modified strategy: Identify summary files, skip raw files
- Logic: `if filename.startswith("summary_") or filename == "The_Auditor_Summary.json"` → chunk, else skip
- Result: 7-8 files in /readthis/ (only summaries)
- **Fixed**: Raw data stays in /raw/ only

## Conclusion

The repository currently lacks:
1. Per-domain summary generation functions (need to create 7 functions)
2. Master summary combining all domains (need `generate_master_summary()`)
3. Selective extraction (need to modify strategy building to skip raw files)
4. Pipeline stage for summary generation (need Stage 13)
5. Query alternative references in output (need to add field to all summaries)

Current state produces 24-27 chunked files in /readthis/ because extraction chunks everything. This change will:
- Generate focused summaries in /raw/ (7 files)
- Generate master summary in /raw/ (1 file)
- Modify extraction to ONLY chunk summaries (7-8 files in /readthis/)
- Keep raw data in /raw/ only (not copied to /readthis/)
- Result: 7-8 readable summaries instead of 24-27 chunks

Implementation is purely output generation — no database schema changes, no FCE modifications, no analyzer changes. Only summary.py, extraction.py, and pipeline integration affected.
