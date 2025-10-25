## Overview
Reorganize TheAuditor's output architecture to make results consumable by humans and AI agents. The change shifts from "dump everything to `.pf/raw/` and chunk it" to a two-tier model: `.pf/raw/` remains the data warehouse (full fidelity), while `.pf/readthis/` becomes the primary consumption layer with focused per-analyzer summaries. FCE evolves from a correlation engine into a "command center" that both correlates findings and generates a master combined summary. This aligns with the new `aud blueprint` / `aud query` AI interaction model where structured queries replace raw JSON parsing.

## Data Model & Persistence

**Primary Storage**: All findings and analysis results already exist in `findings_consolidated`, graph tables, taint tables, etc. **No new database tables required** for core functionality.

**Optional Enhancement** (Coverage-based flagging - Phase 2):
If we want to optionally flag findings based on test coverage later, we can add:
- `test_coverage_summary` - Per-file coverage percentages (if `aud metadata analyze --coverage` is run)
- Simple join in FCE to highlight untested critical findings

**Core Implementation**: This change is **summary generation focused**, not database schema focused. We're reorganizing how data flows from database → JSON summaries → `.pf/readthis/` consumption.

## Per-Analyzer Summary Generation

**Goal**: Each major analyzer gets a dedicated summary file in `.pf/readthis/` that provides:
- Top N findings (sorted by severity, optionally by count/frequency)
- Key metrics (total issues, critical count, files affected)
- Cross-references to `.pf/raw/` for full detail
- Size limit: ≤50 KB per summary

**Implementation Pattern** (Apply to each analyzer):

```python
# Example: theauditor/commands/summary.py (or dedicated summary module)

def generate_graph_summary(db_path, output_dir):
    """Generate graph analysis summary."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query graph findings from findings_consolidated
    cursor.execute("""
        SELECT file, line, rule, severity, message
        FROM findings_consolidated
        WHERE tool = 'graph-analysis'
        ORDER BY severity_priority DESC
        LIMIT 20
    """)

    top_findings = [dict(row) for row in cursor.fetchall()]

    # Load graph metrics
    graph_analysis = json.load(open('.pf/raw/graph_analysis.json'))

    summary = {
        "analyzer": "graph",
        "metrics": {
            "cycles_found": len(graph_analysis.get('cycles', [])),
            "hotspots_identified": len(graph_analysis.get('hotspots', [])),
            "total_findings": len(top_findings)
        },
        "top_findings": top_findings,
        "detail_location": ".pf/raw/graph_analysis.json"
    }

    # Write to readthis
    with open(f"{output_dir}/summary_graph.json", 'w') as f:
        json.dump(summary, f, indent=2)
```

**Summaries to Generate**:
1. `summary_graph.json` - Cycles, hotspots, impact analysis
2. `summary_taint.json` - High-confidence taint paths (top 20)
3. `summary_lint.json` - Lint findings by severity
4. `summary_rules.json` - Security rules grouped by category
5. `summary_dependencies.json` - Vulnerable deps + outdated packages
6. `summary_cfg.json` - CFG complexity metrics (optional)

**CLI Integration**:
- Extend `aud summary` command to generate all per-analyzer summaries
- OR: Each analyzer generates its own summary (e.g., `aud graph analyze` writes `summary_graph.json`)
- Summaries always go to `.pf/readthis/`, raw data stays in `.pf/raw/`

## Pipeline & Summary Integration

**How Summaries Get Generated**:

**Option A: `aud summary` command generates all summaries**:
- Run at the end of `aud full` pipeline (Stage 4)
- Queries database for findings from each domain
- Generates all 7-8 summaries in one pass
- Example: `aud summary` → writes all `summary_*.json` files to `.pf/readthis/`

**Option B: Each analyzer generates its own summary**:
- Each analyzer writes summary at the end of its run
- Example: `aud graph analyze` writes both:
  - `.pf/raw/graph_analysis.json` (full data)
  - `.pf/readthis/summary_graph.json` (top 20 findings + metrics)
- `aud summary` just generates `summary_full.json` by combining existing per-domain summaries

**Recommended: Option A** (centralized, easier to maintain)

**Full Summary Structure** (`summary_full.json`):
```json
{
  "overview": {
    "total_findings": 147,
    "critical": 5,
    "high": 23,
    "medium": 89,
    "low": 30
  },
  "per_domain_metrics": {
    "graph": {"cycles": 3, "hotspots": 12, "findings": 15},
    "taint": {"paths_found": 8, "high_confidence": 5, "findings": 8},
    "lint": {"total": 89, "critical": 2, "findings": 89},
    "rules": {"security_issues": 15, "critical": 3, "findings": 15},
    "dependencies": {"vulnerable": 12, "outdated": 8, "findings": 20}
  },
  "top_findings_all_domains": [
    {
      "rank": 1,
      "severity": "critical",
      "domain": "taint",
      "file": "auth.py",
      "line": 45,
      "message": "SQL injection: user input flows to query",
      "also_flagged_by": ["rules"],
      "details": ".pf/readthis/summary_taint.json"
    }
  ],
  "per_domain_summaries": {
    "graph": ".pf/readthis/summary_graph.json",
    "taint": ".pf/readthis/summary_taint.json",
    "lint": ".pf/readthis/summary_lint.json",
    "rules": ".pf/readthis/summary_rules.json",
    "dependencies": ".pf/readthis/summary_dependencies.json"
  }
}

## Summary & Report Outputs

**BEFORE** (Current - The Problem):
```
.pf/readthis/
├── graph_analysis_part1.json      # Chunk 1/3
├── graph_analysis_part2.json      # Chunk 2/3
├── graph_analysis_part3.json      # Chunk 3/3
├── taint_paths_part1.json         # Chunk 1/3
├── taint_paths_part2.json         # Chunk 2/3
├── taint_paths_part3.json         # Chunk 3/3
├── lint_results_part1.json        # Chunk 1/2
├── lint_results_part2.json        # Chunk 2/2
└── ... (24-27 total chunked files) ❌ NOBODY READS THIS
```

**AFTER** (Proposed - The Solution):
```
.pf/
├── raw/                           # Full data warehouse (archival/debugging)
│   ├── graph_analysis.json        # Full graph data (still here!)
│   ├── taint_paths.json           # All taint paths (still here!)
│   ├── lint_results.json          # All lint findings (still here!)
│   └── ... (chunking still works if needed)
│
└── readthis/                      # Human/AI consumption layer (FIXED)
    ├── summary_full.json          # "Full summary of all problems" (≤100 KB) ⭐
    ├── summary_graph.json         # Graph domain summary (≤50 KB)
    ├── summary_taint.json         # Taint domain summary (≤50 KB)
    ├── summary_lint.json          # Lint domain summary (≤50 KB)
    ├── summary_rules.json         # Rules domain summary (≤50 KB)
    ├── summary_dependencies.json  # Dependencies domain summary (≤50 KB)
    ├── summary_cfg.json           # CFG domain summary (≤50 KB)
    └── summary_imports.json       # Import analysis summary (≤50 KB)

    Total: 7-8 files (not 24-27!) ✅ ACTUALLY READABLE
```

**Consumption Flow**:
1. **Humans start here**: Read `summary_full.json` (100 KB, 30 seconds) - understand "what matters"
2. **Drill into domain**: Read `summary_<domain>.json` (50 KB) - see top 20 findings for that analyzer
3. **Full detail needed**: Query `.pf/raw/` OR use `aud blueprint` / `aud query` for structured access
4. **AI agents**: Start with `summary_full.json` for sync, use `aud blueprint` / `aud query` for deep analysis

**Documentation Updates**:
- README: Explain `.pf/readthis/` is for human overview, `.pf/raw/` is archival
- CLI help: `aud summary --help` documents what summaries are generated
- Make clear: Summary system for humans/quick sync, `aud blueprint` / `aud query` for AI structured access

## Verification & Testing Strategy

**Automated Tests**:
1. **Summary generation tests** (`tests/test_summary_generation.py`):
   - Verify each analyzer writes to `.pf/readthis/summary_<analyzer>.json`
   - Assert summaries are ≤50 KB each
   - Validate JSON structure (top_findings, metrics, detail_location)

2. **FCE combination test** (`tests/test_fce_combining.py`):
   - Verify FCE loads per-analyzer summaries
   - Assert combined summary generated in `.pf/readthis/`
   - Check cross-referencing between combined + per-analyzer summaries

3. **Pipeline integration test**:
   - Run `aud full` and assert all summaries exist in `.pf/readthis/`
   - Verify `.pf/raw/` still has full data (no regressions)

**Manual Verification**:
1. Run `aud full` on a test project
2. Check `.pf/readthis/` contains 5-6 summary files + combined summary
3. Verify each summary is human-readable (≤50 KB, top 20 findings)
4. Confirm combined summary cross-links to per-analyzer summaries
5. Validate AI can start with `summary_combined.json` and drill down

**Success Criteria**:
- ✅ `.pf/readthis/` becomes the "start here" directory
- ✅ Each summary is ≤50 KB and actionable
- ✅ Combined summary answers "what are top 20 things to fix?"
- ✅ `.pf/raw/` remains untouched (full fidelity preserved)
