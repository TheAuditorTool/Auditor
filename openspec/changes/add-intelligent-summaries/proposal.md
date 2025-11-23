# Proposal: Add Intelligent Summaries to `.pf/summary/`

## Why

**Problem**: `aud full` generates 20+ raw JSON files in `.pf/raw/` totaling 5-50MB. AI agents consuming this output face:
1. **Context window saturation**: Reading all raw files exhausts token budgets
2. **Signal-to-noise ratio**: Critical intersections (SAST + high churn + complexity) buried in data
3. **No triage guidance**: AI must parse every file to find high-priority items
4. **Database query ignorance**: AIs don't know how to query `repo_index.db` directly

**Root Cause**: Raw files are ground truth preservation (immutable), not AI consumption optimization.

**Solution**: Add 5 "Truth Courier" summary files to `.pf/summary/` that aggregate raw findings with FCE correlation metadata, guiding AI agents to high-priority intersections without interpretation or recommendations.

## What Changes

### New Directory: `.pf/summary/`

5 JSON files generated during Stage 4 (after FCE, before report):

| File | Purpose | Reads From |
|------|---------|------------|
| `SAST_Summary.json` | Security findings by type with FCE correlation | `patterns.json`, `taint.json`, `github_workflows.json` |
| `SCA_Summary.json` | Dependency issues (direct vs transitive) | `deps.json`, `vulnerabilities.json`, `frameworks.json` |
| `Intelligence_Summary.json` | Code health metrics (hotspots, cycles, complexity) | `graph_analysis.json`, `cfg.json`, `churn_analysis.json` |
| `Quick_Start.json` | **Intersection map** - files with MULTIPLE signals | All raw files + FCE meta-findings |
| `Query_Guide.json` | Database schema + CLI examples (static reference) | N/A (generated once per run) |

### Key Design Principles

1. **Truth Courier ONLY**: Show counts and locations, never recommendations or severity filtering
2. **FCE Correlation**: Every entry includes `fce_correlated: true/false` to indicate architectural significance
3. **Database-First**: `Query_Guide.json` teaches AI to query `repo_index.db` instead of parsing JSON
4. **Intersection Logic**: `Quick_Start.json` only shows files where 2+ independent signals converge
5. **ZERO FALLBACK**: Hard fail if source files missing (exposes pipeline bugs)

### New CLI Integration

- New command: `aud summary generate` (generates all 5 files)
- New phase in `aud full` pipeline: Stage 4 runs summary generation after FCE
- Existing `aud summary` command enhanced to read from new files

## Impact

### Affected Specs
- `specs/summary/spec.md` (NEW capability)

### Affected Code
- `theauditor/commands/summary.py` - New subcommand `generate`
- `theauditor/pipelines.py` - Add summary generation to Stage 4
- `theauditor/summary/` - New module (4 files: `__init__.py`, `generators.py`, `schemas.py`, `query_guide.py`)

### Risk Assessment
- **Breaking Changes**: None - adds new directory, doesn't modify `/raw/`
- **Performance**: ~500ms added to Stage 4 (reads existing JSON, no new analysis)
- **Backwards Compatibility**: Old pipelines work unchanged; summary dir is additive
- **ZERO FALLBACK Risk**: If raw files missing, summary generation will crash (correct behavior)

### Dependencies
- Requires FCE to run first (uses `fce.json` for meta-findings)
- Requires all Stage 3 tracks to complete (needs raw outputs)

## Success Criteria

1. `aud full` creates `.pf/summary/` with all 5 files
2. `Quick_Start.json` contains ONLY files with 2+ intersecting signals
3. All entries include `fce_correlated` boolean
4. `Query_Guide.json` includes accurate schema from live `repo_index.db`
5. AI agents can triage findings using only `Quick_Start.json` (no raw file parsing)
