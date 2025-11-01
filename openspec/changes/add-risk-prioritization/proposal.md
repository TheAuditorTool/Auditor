## Why
- TheAuditor has **database-first query commands** (`aud query`, `aud context`, `aud planning`) that enable AI assistants to interact directly with indexed code data.
- **The chunking system is obsolete**: The current `.pf/readthis/` extraction system generates 24-27 chunked JSON files by parsing `/raw/` outputs, but direct database queries are 100x faster and eliminate token waste.
- **Chunking provides no value**: With database queries available, chunking raw outputs into smaller files is redundant and creates maintenance burden.
- **Missing guidance layer**: TheAuditor produces excellent ground truth in `/raw/` but lacks **5 focused summary documents** in `/readthis/` that highlight FCE correlations and provide quick orientation.
- **AI interaction shift**: AIs should **query the database directly** (repo_index.db + graphs.db) instead of parsing JSON files. The `/readthis/` directory should contain summaries that guide what to query, not chunks of raw data.

## What Changes
- **Deprecate extraction.py chunking system**: Remove the code that generates 24-27 chunk files by parsing `/raw/` outputs.
- **Keep ALL `/raw/` files unchanged**: Do NOT consolidate tool outputs. Each analyzer (patterns, taint, cfg, graph, etc.) continues writing to its own separate JSON file in `/raw/`.
  - ✅ `patterns.json` - Output from detect-patterns
  - ✅ `taint.json` - Output from taint-analyze
  - ✅ `cfg.json` - Output from cfg analyze
  - ✅ `deadcode.json` - Output from deadcode
  - ✅ `frameworks.json` - Output from detect-frameworks
  - ✅ `graph_analysis.json` - Output from graph analyze
  - ✅ `fce.json` - Output from fce
  - ✅ All other 20+ tool outputs remain separate
  - **Rationale**: Raw tool outputs are "our only value" - consolidation breaks the pipeline and loses ground truth fidelity.

- **Add 5 intelligent summaries to `/readthis/`** (replaces chunks):
  - **`SAST_Summary.json`** - Security findings overview
    - Reads from: patterns.json, taint.json, docker_findings.json, github_workflows.json
    - Shows: Total findings count, FCE-correlated security hotspots, files with multiple tools flagging issues
    - Truth courier format: "X patterns detected, Y taint paths found, Z in FCE hotspots" (NO recommendations)

  - **`SCA_Summary.json`** - Dependency issues overview
    - Reads from: deps.json, frameworks.json
    - Shows: Outdated packages count, detected frameworks, dependency tree depth
    - Truth courier format: "X packages analyzed, Y frameworks detected, Z outdated" (NO recommendations)

  - **`Intelligence_Summary.json`** - Code intelligence overview
    - Reads from: graph_analysis.json, cfg.json, fce.json
    - Shows: Hotspot count, cycle count, complex function count, FCE meta-findings
    - Truth courier format: "X hotspots, Y cycles, Z complex functions, W FCE correlations" (NO recommendations)

  - **`Quick_Start.json`** - Critical issues across all domains
    - Reads from: All /raw/ files + fce.json for FCE correlations
    - Shows: Top issues guided by FCE (architectural risks, complexity risks, churn risks, etc.)
    - Truth courier format: Lists FCE findings (ARCHITECTURAL_RISK_ESCALATION, COMPLEXITY_RISK_CORRELATION, etc.) with file:line locations

  - **`Query_Guide.json`** - Database query reference
    - Static reference document
    - Shows: Example `aud query` and `aud context` commands for each analysis domain
    - Guides AIs on how to query database instead of parsing JSON

- **Summaries are truth couriers ONLY** (NO interpretation):
  - Show counts, file locations, and FCE correlations
  - Present findings exactly as FCE identified them
  - **Never use "severity" filtering** - show what FCE found, not what we think is important
  - **Never recommend fixes** - just present facts: "X found in Y locations, Z correlated by FCE"
  - Let AI consumer decide what's important using database queries

- **Update pipeline**:
  - Remove extraction trigger (no more chunking to /readthis/)
  - Add `aud summarize` call after FCE phase
  - Rename `extraction.py` to `extraction.py.bak` (preserve but deprecate)

- **Update documentation**:
  - Make clear: **AIs should query database via `aud query`**, NOT read JSON files
  - Summaries are for **quick orientation only** - database queries provide full detail
  - Raw `/raw/` files are **immutable ground truth** - never modified or consolidated

## Impact
- **Eliminates /readthis/ bloat**: 24-27 chunked files → 5 summaries (82% reduction)
- **Preserves raw outputs**: ALL 20+ /raw/ files unchanged (ground truth fidelity maintained)
- **Adds guidance layer**: 5 summaries provide FCE-guided quick orientation
- **Enables database-first workflow**: AIs query directly with `aud query` (100x faster)
- **Maintains backward compatibility**: audit_summary.json still generated, /raw/ structure unchanged
- **Reduces complexity**: No consolidation logic needed, analyzers unchanged
- **Follows truth courier model**: Summaries present facts and FCE correlations, never interpret

## Verification Alignment
- Hypotheses, evidence, and discrepancies captured in `openspec/changes/add-risk-prioritization/verification.md` per SOP v4.20.
- **Critical correction applied**: Previous proposal wanted to consolidate /raw/ files - this was WRONG and broke the pipeline.
- **Correct architecture verified**: Keep all /raw/ files separate, add summaries to /readthis/, deprecate chunking.
- Task list focuses on summary generation and extraction deprecation only - NO changes to analyzer outputs.
- Implementation details in `design.md` with line-by-line changes for summarize command creation.
