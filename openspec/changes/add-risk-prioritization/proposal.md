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
  - `summary_cfg.json` - CFG complexity metrics + problematic functions (≤50 KB)
  - `summary_imports.json` - Import analysis + circular deps (≤50 KB)
  - Each summary: Top N findings + key metrics + references to `.pf/raw/` for full data

- **Add "full summary of all problems"**: Create a single `summary_full.json` that combines insights from ALL domains:
  - Lists top 20-30 findings across ALL analyzers (severity-sorted)
  - Shows which domains found issues (e.g., "taint + rules both flag auth.py:45")
  - Provides metrics per domain (X graph cycles, Y taint paths, Z lint issues)
  - Cross-links to per-domain summaries for drill-down
  - Output location: `.pf/readthis/summary_full.json` (≤100 KB)

- **Reorganize `.pf/readthis/` structure**: Replace 24-27 chunked files with ~7-8 focused summaries:
  - **Before**: 24-27 chunked JSONs (2-3 per file) - nobody reads this
  - **After**: 7-8 summary files (6-7 per-domain + 1 full summary) - human-readable
  - Chunked raw data still available in `.pf/raw/` if needed

- **Keep FCE as-is**: FCE continues doing factual correlation (detecting when multiple tools flag the same location). This change is about SUMMARIZATION, not correlation.

- **Update documentation**: Clarify consumption model - humans read summaries, AI uses `aud blueprint` / `aud query`, `.pf/raw/` is for archival/deep dives.

## Impact
- **Fixes information overload**: Replace 24-27 chunked files with 7-8 focused summaries (50 KB each) - actually human-readable
- **Restores old functionality**: Per-domain summaries used to exist, bringing them back gives operators the overview they need
- **Enables quick sync**: Humans can read `summary_full.json` (100 KB) to understand "what matters" across ALL domains in 30 seconds
- **Better AI integration**: AI agents get a lightweight sync point (`summary_full.json`) without parsing 24-27 files, PLUS structured queries via `aud blueprint` / `aud query`
- **Preserves full fidelity**: `.pf/raw/` still has everything for archival/debugging, chunking system still works, nothing breaks
- **FCE unchanged**: FCE continues doing correlation (its actual job), summaries are a separate concern

## Verification Alignment
- Hypotheses, evidence, and discrepancies captured in `openspec/changes/add-risk-prioritization/verification.md` per SOP v4.20.
- Task list front-loads schema verification and requires regression coverage for pipeline, FCE, and summary flows before completion.
