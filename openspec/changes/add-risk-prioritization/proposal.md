## Why
- TheAuditor now has **database-first query commands** (`aud query`, `aud context`, `aud planning`) that enable AI assistants to interact directly with indexed code data.
- **The chunking system is obsolete**: The original `.pf/readthis/` architecture (24-27 chunked JSON files) was designed for AI token limitations, but direct database queries are 100x faster and eliminate token waste.
- **Output file explosion**: Current pipeline outputs **20+ separate JSON files** from a 26-phase pipeline - nobody manually reads 20+ files.
- **Missing consolidation**: Raw outputs are fragmented across domains (taint, graph, lint, patterns, deps, terraform, workflows, cfg, fce) with no cohesive grouping.
- **No guidance layer**: TheAuditor produces excellent ground truth data but lacks **3-5 focused summary documents** that highlight hotspots, FCE findings, and actionable insights for quick orientation.
- **AI interaction shift**: With `aud query` / `aud context` / `aud planning`, AIs should **query the database directly** (repo_index.db + graphs.db) instead of parsing JSON files.

## What Changes
- **Deprecate `.pf/readthis/` entirely**: Remove the extraction/chunking system - it's redundant with database queries.
- **Consolidate `.pf/raw/` to 1 document per group** (instead of 20+ files):
  - **`graph_analysis.json`** - Combined: call graphs, import graphs, hotspots, cycles, layers (consolidates 5 current graph outputs)
  - **`security_analysis.json`** - Combined: patterns, taint flows, vulnerabilities (consolidates patterns.json + taint_analysis.json)
  - **`quality_analysis.json`** - Combined: lint, cfg, deadcode (consolidates lint.json + cfg.json + deadcode.json)
  - **`dependency_analysis.json`** - Combined: deps, docs, frameworks (consolidates deps.json + docs.json + frameworks.json)
  - **`infrastructure_analysis.json`** - Combined: terraform, cdk, docker, workflows (consolidates 4 infrastructure files)
  - **`correlation_analysis.json`** - FCE meta-findings only (replaces fce.json)

- **Add 3-5 guidance summaries** (new files in `.pf/raw/`):
  - **`SAST_Summary.json`** - Top 20 security findings across all analyzers (patterns + taint + infrastructure), grouped by severity
  - **`SCA_Summary.json`** - Top 20 dependency issues (CVEs, outdated packages, vulnerable deps)
  - **`Intelligence_Summary.json`** - Top 20 code intelligence insights (hotspots, cycles, complexity, FCE correlations)
  - **`Quick_Start.json`** - Ultra-condensed: "Read this first" - top 10 most critical issues across ALL domains with pointers to full data
  - **`Query_Guide.json`** - Reference guide showing how to query each analysis domain via `aud query` / `aud context` commands

- **Summaries are truth couriers only** (NO recommendations):
  - Highlight critical findings by severity
  - Point to hotspots and FCE-correlated issues
  - Show actionable metrics (X vulnerabilities, Y cycles, Z outdated deps)
  - Cross-reference to consolidated files for full detail
  - **Never recommend fixes** - just present facts and locations

- **Update pipeline to generate consolidated outputs**:
  - Each analyzer writes to its consolidated group file (not separate files per sub-analysis)
  - After FCE, generate 3-5 summary documents
  - Remove extraction stage entirely (no more chunking to /readthis/)

- **Update documentation**:
  - Make clear: **AIs should query database via `aud query` / `aud context`**, NOT read JSON files
  - Summaries are for **quick orientation only** - database queries provide full detail
  - Raw consolidated files are for **archival/debugging** - database is the primary data source

## Impact
- **Eliminates /readthis/ bloat**: No more 24-27 chunked files - entire directory deprecated
- **Consolidates raw outputs**: 20+ files → 6 consolidated group files (5x cleaner)
- **Adds guidance layer**: 3-5 summaries provide quick orientation without drowning in data
- **Enables database-first AI workflow**: AIs query directly with `aud query` (100x faster, zero token waste)
- **Maintains ground truth fidelity**: All data still preserved in consolidated files + database
- **Aligns with modern architecture**: Post-`aud query` / `aud context` / `aud planning` world - database is the source of truth
- **Reduces cognitive load**: 6 consolidated files + 3-5 summaries = 9-11 total files (down from 24-27 chunks + 20+ raw files)

## Verification Alignment
- Hypotheses, evidence, and discrepancies captured in `openspec/changes/add-risk-prioritization/verification.md` per SOP v4.20.
- Task list focuses on output consolidation, summary generation, and deprecation of extraction.
- Implementation details in `design.md` with line-by-line changes anchored in actual code.
