# Verification Report - add-risk-prioritization (UPDATED)
Generated: 2025-11-01
SOP Reference: Standard Operating Procedure v4.20

## Proposal Evolution

**ORIGINAL PROPOSAL** (Pre-aud query/context era):
- Per-domain summaries (summary_taint.json, summary_graph.json, etc.)
- Keep `/readthis/` but with only summaries (7-8 files)
- Chunk summaries if >65KB

**NEW PROPOSAL** (Database-first era):
- Deprecate `/readthis/` entirely
- Consolidate `/raw/` outputs (20+ files → 6 consolidated groups)
- Add 3-5 guidance summaries (SAST, SCA, Intelligence, Quick Start, Query Guide)
- AIs query database directly via `aud query` / `aud context` / `aud planning`

## Hypotheses & Evidence

### 1. TheAuditor has database-first query commands
- **Hypothesis**: `aud query`, `aud context`, and `aud planning` commands exist and enable direct database interaction.
- **Evidence**: `theauditor/commands/query.py` exists (1024 lines) - SQL queries over indexed code relationships.
- **Evidence**: `theauditor/commands/context.py` exists (390 lines) - Semantic classification via YAML rules.
- **Evidence**: CLI help shows all 3 commands with database-first descriptions.
- **Result**: **TRUE** — Database-first commands are fully implemented and production-ready.

### 2. Current pipeline generates 20+ separate JSON files
- **Hypothesis**: `aud full` currently outputs 20+ separate JSON files in `.pf/raw/`.
- **Evidence**: Pipeline (theauditor/pipelines.py:430-457) has 26 phases, many generate separate output files.
- **Evidence**: Graph analyzer generates: graph_analysis.json, graph_cycles.json, graph_hotspots.json, graph_layers.json, call_graph.json (5 files).
- **Evidence**: Security analyzers generate: patterns.json, taint_analysis.json (2 files minimum).
- **Evidence**: Quality analyzers generate: lint.json, cfg.json, deadcode.json (3 files).
- **Evidence**: Infrastructure analyzers generate: terraform_findings.json, cdk_findings.json, docker_findings.json, workflows_findings.json (4 files).
- **Evidence**: Other outputs: deps.json, docs.json, frameworks.json, fce.json, audit_summary.json (5+ files).
- **Result**: **TRUE** — Current pipeline generates 20+ separate files, confirming fragmentation problem.

### 3. Extraction system chunks everything to /readthis/
- **Hypothesis**: Pipeline triggers extraction after FCE, chunking ALL files from /raw/ to /readthis/.
- **Evidence**: `theauditor/pipelines.py:1462-1476` triggers extraction after FCE phase.
- **Evidence**: `theauditor/extraction.py:378` implements `extract_all_to_readthis()` - chunks ALL files >65KB.
- **Evidence**: Original proposal verification noted "24-27 chunked files in /readthis/".
- **Result**: **TRUE** — Extraction system is active and creates bloated output.

### 4. No consolidated group files exist
- **Hypothesis**: Analyzers write separate files, not consolidated group files.
- **Evidence**: Checked graph.py, detect_patterns.py, taint_analyze.py - all write to separate JSON files.
- **Evidence**: No `write_to_group()` or consolidated output helper exists.
- **Evidence**: No files named `security_analysis.json`, `quality_analysis.json`, etc. exist.
- **Result**: **TRUE** — No consolidation exists, each analyzer writes independently.

### 5. No guidance summaries exist
- **Hypothesis**: No SAST_Summary.json, SCA_Summary.json, Intelligence_Summary.json, Quick_Start.json, or Query_Guide.json exist.
- **Evidence**: Only `audit_summary.json` exists (stats only, not findings).
- **Evidence**: No `theauditor/commands/summarize.py` file exists.
- **Evidence**: No guidance summaries mentioned in CLI help or README.
- **Result**: **TRUE** — Guidance layer does not exist.

### 6. /readthis/ directory is generated on every full run
- **Hypothesis**: `.pf/readthis/` is created and populated during `aud full`.
- **Evidence**: Pipeline calls `extract_all_to_readthis(root)` after FCE phase.
- **Evidence**: Extraction creates /readthis/ directory and populates with chunks.
- **Evidence**: README mentions "`.pf/readthis/` - AI-optimized chunks (<65KB each)".
- **Result**: **TRUE** — /readthis/ is currently active and generated.

### 7. Database is the primary data source
- **Hypothesis**: repo_index.db and graphs.db contain all indexed code data.
- **Evidence**: `repo_index.db` (91MB) - 108 normalized tables with symbols, calls, assignments.
- **Evidence**: `graphs.db` (79MB) - Pre-computed graph structures.
- **Evidence**: `aud query` command documentation: "Direct SQL queries over indexed code relationships."
- **Evidence**: README states "Database-first queries - 100x faster than file-based search".
- **Result**: **TRUE** — Database is the authoritative data source, JSON files are secondary.

### 8. Analyzers can be modified to write to consolidated files
- **Hypothesis**: It's technically feasible to modify analyzers to append to consolidated group files instead of writing separate files.
- **Evidence**: Current pattern: `with open(".pf/raw/patterns.json", 'w') as f: json.dump(data, f)`.
- **Evidence**: Proposed pattern: `write_to_group("security_analysis", "patterns", data)` - load existing, append, write back.
- **Evidence**: JSON structure supports nested analyses: `{"analyses": {"patterns": {...}, "taint": {...}}}`.
- **Result**: **TRUE** — Consolidation is straightforward refactoring of output logic.

## Discrepancies & Alignment Notes

### Discrepancy 1: Original proposal is obsolete
- **Original Design**: Per-domain summaries with chunking to /readthis/ (7-8 summary files).
- **Current Reality**: Database-first commands (`aud query`, `aud context`) make chunking redundant.
- **Impact**: Entire original proposal needs pivot to database-first + consolidated outputs.

### Discrepancy 2: No consolidation exists
- **Current**: 20+ separate JSON files in /raw/.
- **Required**: 6 consolidated group files (graph, security, quality, dependency, infrastructure, correlation).
- **Impact**: Need to create consolidation helper and modify all analyzers.

### Discrepancy 3: No guidance layer exists
- **Current**: Only `audit_summary.json` with stats.
- **Required**: 5 guidance summaries (SAST, SCA, Intelligence, Quick Start, Query Guide).
- **Impact**: Need to create `aud summarize` command with 5 summary generators.

### Discrepancy 4: Extraction is still active
- **Current**: Pipeline triggers extraction after FCE, creates /readthis/ bloat.
- **Required**: Remove extraction trigger, replace with `aud summarize` call.
- **Impact**: Modify pipelines.py:1462-1476 to call summarize instead of extraction.

### Discrepancy 5: Documentation reflects old architecture
- **Current**: README mentions /readthis/ as AI-optimized output.
- **Required**: Update to emphasize database queries + consolidated /raw/ + guidance summaries.
- **Impact**: README, CLI help, and migration guide need updates.

## Baseline Metrics (Before Implementation)

**Current /raw/ structure** (expected after `aud full`):
- **Total files**: 20+ separate JSON files
- **Graph outputs**: graph_analysis.json, graph_cycles.json, graph_hotspots.json, graph_layers.json, call_graph.json (5 files)
- **Security outputs**: patterns.json, taint_analysis.json (2 files)
- **Quality outputs**: lint.json, cfg.json, deadcode.json (3 files)
- **Dependency outputs**: deps.json, docs.json, frameworks.json (3 files)
- **Infrastructure outputs**: terraform_findings.json, cdk_findings.json, docker_findings.json, workflows_findings.json (4 files)
- **Other**: fce.json, audit_summary.json, metadata.json, etc. (3+ files)
- **Total**: ~20+ files

**Current /readthis/ structure**:
- **Total files**: 24-27 chunked JSON files (per original verification)
- **Format**: *_chunk01.json, *_chunk02.json, etc.
- **Problem**: Too many files, nobody reads them

**Current pipeline behavior**:
- **Phase 26**: summary (generates audit_summary.json)
- **After FCE**: extraction (chunks everything to /readthis/)
- **No summarize phase**: Guidance summaries don't exist

## Target Metrics (After Implementation)

**Target /raw/ structure**:
- **Consolidated files (6)**:
  - graph_analysis.json
  - security_analysis.json
  - quality_analysis.json
  - dependency_analysis.json
  - infrastructure_analysis.json
  - correlation_analysis.json

- **Guidance summaries (5)**:
  - SAST_Summary.json
  - SCA_Summary.json
  - Intelligence_Summary.json
  - Quick_Start.json
  - Query_Guide.json

- **Total**: 11 files (down from 20+)

**Target /readthis/ structure**:
- **NO FILES** - directory not created

**Target pipeline behavior**:
- **Phase 26**: summary (still generates audit_summary.json for backward compat)
- **After FCE**: summarize (generates 5 guidance summaries)
- **No extraction**: Deprecated, not called

## Implementation Verification Checkpoints

### Checkpoint 1: Consolidation Helper Created
- **Verify**: `theauditor/utils/consolidated_output.py` exists
- **Verify**: `write_to_group()` function accepts (group_name, analysis_type, data)
- **Verify**: Function validates group_name is one of 6 valid groups
- **Test**: Call with sample data, confirm JSON structure

### Checkpoint 2: Analyzers Modified
- **Verify**: Graph analyzers call `write_to_group("graph_analysis", ...)`
- **Verify**: Security analyzers call `write_to_group("security_analysis", ...)`
- **Verify**: Quality analyzers call `write_to_group("quality_analysis", ...)`
- **Verify**: Dependency analyzers call `write_to_group("dependency_analysis", ...)`
- **Verify**: Infrastructure analyzers call `write_to_group("infrastructure_analysis", ...)`
- **Test**: Run individual commands, check consolidated files exist

### Checkpoint 3: Summarize Command Created
- **Verify**: `theauditor/commands/summarize.py` exists
- **Verify**: 5 generator functions implemented (generate_sast_summary, generate_sca_summary, etc.)
- **Verify**: Command registered in `theauditor/cli.py`
- **Test**: `aud summarize` creates 5 JSON files in /raw/

### Checkpoint 4: Pipeline Modified
- **Verify**: `theauditor/pipelines.py:1462-1476` no longer calls extraction
- **Verify**: Pipeline calls `aud summarize` after FCE
- **Verify**: Log message shows "[SUMMARIZE]" instead of "[EXTRACTION]"
- **Test**: `aud full --offline` runs without errors

### Checkpoint 5: Extraction Deprecated
- **Verify**: `theauditor/extraction.py` has deprecation comment at top
- **Verify**: `extract_all_to_readthis()` logs deprecation warning
- **Verify**: `.gitignore` excludes `.pf/readthis/`
- **Test**: No /readthis/ directory created after `aud full`

### Checkpoint 6: Documentation Updated
- **Verify**: README shows new /raw/ structure (6 + 5 files)
- **Verify**: README emphasizes database queries as primary interaction
- **Verify**: CLI help mentions deprecated /readthis/
- **Verify**: Migration guide exists for legacy scripts
- **Test**: Read README, confirm clarity

## Conclusion

**Current State**:
- 20+ fragmented JSON files in /raw/
- Extraction system creates 24-27 chunks in /readthis/
- No consolidated outputs
- No guidance summaries
- Database-first commands exist but JSON files still primary consumption model

**Target State**:
- 6 consolidated group files + 5 guidance summaries = 11 total files
- No /readthis/ directory (deprecated)
- Database queries via `aud query` / `aud context` are primary interaction
- Guidance summaries provide quick orientation
- Truth courier principle: summaries highlight findings, never recommend

**Implementation Scope**:
- Create consolidation helper
- Modify 12+ analyzer commands to write to consolidated files
- Create `aud summarize` command with 5 generators
- Modify pipeline to call summarize instead of extraction
- Deprecate extraction system
- Update documentation

**Risk Assessment**:
- **LOW** - This is pure output refactoring, no database schema changes
- **LOW** - Database queries unaffected
- **LOW** - Backward compatible (audit_summary.json still generated)
- **MEDIUM** - Requires modifying many analyzer files (but pattern is simple)

**Expected Timeline**:
- Consolidation helper: 1 hour
- Modify analyzers: 4-6 hours (12+ files)
- Create summarize command: 3-4 hours (5 generators)
- Modify pipeline: 1 hour
- Deprecate extraction: 1 hour
- Update documentation: 2 hours
- Testing & verification: 2-3 hours
- **Total**: 14-18 hours of implementation

**Verification Success Criteria**:
- ✅ 6 consolidated files in /raw/
- ✅ 5 guidance summaries in /raw/
- ✅ No /readthis/ directory created
- ✅ Database queries work correctly
- ✅ Summaries are truth couriers (no recommendations)
- ✅ Pipeline runs without errors
- ✅ Documentation reflects new architecture
