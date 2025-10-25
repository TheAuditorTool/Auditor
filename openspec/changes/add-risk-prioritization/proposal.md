## Why
- TheAuditor produces **insanely good results** across 7-8 domains (graph analysis, taint paths, lint, security rules, dependencies, CFG, DFG, etc.), but the output is drowning in files.
- **The chunking disaster**: Current extraction chunks raw outputs into `.pf/readthis/`, resulting in **24-27 JSON files** (2-3 chunks per original file). Nobody reads 24-27 files.
- **Lost summaries**: The original architecture had focused summaries per domain (`summary_graph.json`, `summary_taint.json`, etc.) that gave humans a quick overview. These disappeared as chunking took over.
- **No "full overview" output**: There's no single file that says "here are the top problems across ALL domains" - you have to read 24-27 chunked files OR query the database directly.
- **AI consumption shift**: Moving to `aud blueprint` / `aud query` for structured queries, but humans still need readable summaries, and AI agents need a lightweight "sync point" without parsing 24-27 files.
- **FCE does correlation, not summarization**: FCE's job is factual correlation (detecting when multiple tools flag the same location), NOT creating human-readable summaries of what each domain found.

## What Changes
- **Restore per-domain summaries** (these used to exist): Bring back focused summary outputs for each analyzer domain:
  - `summary_graph.json` - Cycles, hotspots, impact metrics + top 20 findings (≤50 KB)
  - `summary_taint.json` - High-confidence taint paths + source/sink breakdown (≤50 KB)
  - `summary_lint.json` - Lint findings by severity + file hotspots (≤50 KB)
  - `summary_rules.json` - Security rules grouped by category + critical issues (≤50 KB)
  - `summary_dependencies.json` - Vulnerable packages + outdated deps (≤50 KB)
  - `summary_fce.json` - Correlated findings + meta-findings (≤50 KB)
  - Each summary: Top N findings + key metrics + references to `.pf/raw/` for full data
  - Each summary mentions: "This domain can also be queried with: aud query --{domain}"

- **Add "The Auditor Summary"**: Create a single `The_Auditor_Summary.json` that combines insights from ALL domains:
  - Lists top 20-30 findings across ALL analyzers (severity-sorted)
  - Shows which domains found issues (e.g., "taint + rules both flag auth.py:45")
  - Provides metrics per domain (X graph cycles, Y taint paths, Z lint issues)
  - Cross-links to per-domain summaries for drill-down
  - Output location: `.pf/raw/The_Auditor_Summary.json` (any size, can be chunked by extraction)

- **Reorganize `.pf/readthis/` structure**: Replace 24-27 chunked files with ~7-8 focused summaries:
  - **Before**: 24-27 chunked JSONs (2-3 per file) - nobody reads this
  - **After**: 7-8 summary files (6-7 per-domain + 1 master summary) - human-readable
  - Raw data files stay in `.pf/raw/` only (NOT copied to /readthis/)
  - Summaries stored in `.pf/raw/` first, then extraction chunks them to `.pf/readthis/` if needed

- **Modify extraction behavior**: Update `extraction.py` to ONLY chunk summary files:
  - Raw files (taint_analysis.json, graph_analysis.json, etc.) → stay in /raw/ only
  - Summary files (summary_*.json, The_Auditor_Summary.json) → chunked to /readthis/ if >65KB
  - Users read summaries in /readthis/, query database via `aud blueprint` / `aud query` for details

- **Keep FCE as-is**: FCE continues doing factual correlation (detecting when multiple tools flag the same location). This change is about SUMMARIZATION, not correlation.

- **Update documentation**: Clarify consumption model - humans read summaries, AI uses `aud blueprint` / `aud query`, `.pf/raw/` is for archival/deep dives.

## Impact
- **Fixes information overload**: Replace 24-27 chunked files with 7-8 focused summaries (50 KB each) - actually human-readable
- **Restores old functionality**: Per-domain summaries used to exist, bringing them back gives operators the overview they need
- **Enables quick sync**: Humans can read `The_Auditor_Summary.json` (≤100 KB) to understand "what matters" across ALL domains in 30 seconds
- **Better AI integration**: AI agents get a lightweight sync point (`The_Auditor_Summary.json`) without parsing 24-27 files, PLUS structured queries via `aud blueprint` / `aud query`
- **Preserves full fidelity**: `.pf/raw/` still has everything for archival/debugging, chunking system still works, nothing breaks
- **FCE unchanged**: FCE continues doing correlation (its actual job), summaries are a separate concern
- **Backward compatible**: Legacy `aud summary` still generates `audit_summary.json`, new flow enabled by `--generate-domain-summaries` flag

## Verification Alignment
- Hypotheses, evidence, and discrepancies captured in `openspec/changes/add-risk-prioritization/verification.md` per SOP v4.20.
- Task list focuses on summary generation, extraction modification, and pipeline integration.
- Implementation details in `implementation.md` with line-by-line changes anchored in actual code.
