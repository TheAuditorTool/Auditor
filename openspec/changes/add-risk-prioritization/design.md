## Overview
Reorganize TheAuditor's output architecture to make results consumable by humans and AI agents. The change shifts from "chunk everything in `.pf/readthis/`" (24-27 files) to "generate focused summaries" (7-8 files). `.pf/raw/` remains the data warehouse (full fidelity), while `.pf/readthis/` becomes the primary consumption layer with per-analyzer summaries. FCE remains unchanged (correlation only). This aligns with the new `aud blueprint` / `aud query` AI interaction model where structured queries replace raw JSON parsing.

## Data Model & Persistence

**Primary Storage**: All findings and analysis results already exist in `findings_consolidated`, graph tables, taint tables, etc. **No new database tables required** - this change is purely about output generation.

**Core Implementation**: This change is **summary generation focused**, not database schema focused. We're reorganizing how data flows from raw JSON outputs → summary JSON files → `.pf/readthis/` consumption.

**Key Principle**: Load from existing JSON files in `.pf/raw/`, not from database queries. Current architecture (summary.py:94-168) already does this.

## Per-Analyzer Summary Generation

**Goal**: Each major analyzer gets a dedicated summary file that provides:
- Top N findings (sorted by severity, typically top 20)
- Key metrics (total issues, critical count, files affected)
- Cross-references to `.pf/raw/` for full detail
- Reference to `aud query` alternatives for structured access
- Size target: ≤50 KB per summary (but can be any size in /raw/, extraction will chunk if needed)

**Implementation Pattern** (Apply to each analyzer):

```python
# File: theauditor/commands/summary.py

def generate_taint_summary(raw_path: Path, db_path: Path) -> Dict[str, Any]:
    """Generate taint analysis domain summary."""
    # Load raw taint data from JSON file
    taint = {}
    if (raw_path / "taint_analysis.json").exists():
        with open(raw_path / "taint_analysis.json", 'r', encoding='utf-8') as f:
            taint = json.load(f)

    # Extract top 20 taint paths by severity
    taint_paths = taint.get("taint_paths", [])
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_paths = sorted(
        taint_paths,
        key=lambda p: severity_order.get(p.get("severity", "low"), 99)
    )[:20]

    # Build summary
    summary = {
        "analyzer": "taint",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "metrics": {
            "total_taint_paths": len(taint_paths),
            "total_vulnerabilities": taint.get("total_vulnerabilities", 0),
            "sources_found": taint.get("sources_found", 0),
            "sinks_found": taint.get("sinks_found", 0),
            "by_severity": {
                "critical": sum(1 for p in taint_paths if p.get("severity") == "critical"),
                "high": sum(1 for p in taint_paths if p.get("severity") == "high"),
                "medium": sum(1 for p in taint_paths if p.get("severity") == "medium"),
                "low": sum(1 for p in taint_paths if p.get("severity") == "low")
            }
        },
        "top_findings": sorted_paths,
        "detail_location": ".pf/raw/taint_analysis.json",
        "query_alternative": "This domain can also be queried with: aud query --taint"
    }

    return summary
```

**Summaries to Generate**:
1. `summary_graph.json` - Cycles, hotspots, impact analysis
2. `summary_taint.json` - High-confidence taint paths (top 20)
3. `summary_lint.json` - Lint findings by severity + file hotspots
4. `summary_rules.json` - Security rules grouped by category
5. `summary_dependencies.json` - Vulnerable deps + outdated packages
6. `summary_fce.json` - Correlated findings + meta-findings

**Master Summary**: `The_Auditor_Summary.json`
- Combines top findings from ALL domains
- Severity-sorted across all analyzers (top 20-30)
- Per-domain metrics + cross-links to per-domain summaries
- Single entry point for "what matters most"

**CLI Integration**:
- Extend `aud summary` command with `--generate-domain-summaries` flag
- Generates all per-analyzer summaries + master summary in one pass
- Summaries written to `.pf/raw/` first (any size allowed)
- Backward compatible: `aud summary` without flag still generates legacy `audit_summary.json`

## Pipeline & Summary Integration

**How Summaries Get Generated**:

**Stage 13** (NEW): Generate per-domain summaries
- Runs at end of `aud full` pipeline, after FCE (Stage 12)
- Invokes `aud summary --generate-domain-summaries`
- Reads from JSON files in `.pf/raw/`: taint_analysis.json, graph_analysis.json, lint.json, patterns.json, fce.json, deps.json
- Generates 6-7 per-domain summaries + 1 master summary
- Outputs to `.pf/raw/summary_*.json` and `.pf/raw/The_Auditor_Summary.json`

**Stage 14** (MODIFIED): Extract to readthis
- Already exists (extraction.py), now modified to be selective
- **NEW BEHAVIOR**: Only chunk summary files (summary_*.json, The_Auditor_Summary.json)
- Raw data files (taint_analysis.json, graph_analysis.json, etc.) stay in /raw/ only
- Result: 7-8 files in `/readthis/` instead of 24-27

**Master Summary Structure** (`The_Auditor_Summary.json`):
```json
{
  "analyzer": "THE_AUDITOR_MASTER",
  "generated_at": "2025-10-26 12:34:56",
  "overview": {
    "total_findings": 147,
    "by_severity": {
      "critical": 5,
      "high": 23,
      "medium": 89,
      "low": 30,
      "info": 0
    },
    "domains_analyzed": 6
  },
  "per_domain_metrics": {
    "graph": {"cycles_detected": 3, "hotspots_identified": 12},
    "taint": {"total_taint_paths": 8, "total_vulnerabilities": 8},
    "lint": {"total_issues": 89},
    "rules": {"total_patterns_matched": 15},
    "dependencies": {"vulnerable_packages": 12, "outdated_packages": 8},
    "fce": {"raw_findings": 147, "meta_findings": 23}
  },
  "top_findings_all_domains": [
    {
      "rank": 1,
      "domain": "taint",
      "severity": "critical",
      "file": "auth.py",
      "line": 45,
      "message": "Taint path: auth.py -> db.py (SQL injection)",
      "detail": { ... }
    }
  ],
  "per_domain_summaries": {
    "graph": ".pf/raw/summary_graph.json",
    "taint": ".pf/raw/summary_taint.json",
    "lint": ".pf/raw/summary_lint.json",
    "rules": ".pf/raw/summary_rules.json",
    "dependencies": ".pf/raw/summary_dependencies.json",
    "fce": ".pf/raw/summary_fce.json"
  },
  "detail_locations": {
    "taint": ".pf/raw/taint_analysis.json",
    "graph": ".pf/raw/graph_analysis.json",
    "lint": ".pf/raw/lint.json",
    "rules": ".pf/raw/patterns.json",
    "dependencies": ".pf/raw/deps.json",
    "fce": ".pf/raw/fce.json"
  },
  "query_alternatives": {
    "structured_queries": "Use 'aud blueprint' or 'aud query' for structured database queries",
    "per_domain": "See per_domain_summaries section for domain-specific summaries"
  }
}
```

## Summary & Report Outputs

**BEFORE** (Current - The Problem):
```
.pf/
├── raw/ (18 files, NO summaries)
│   ├── taint_analysis.json (2.1 MB)
│   ├── graph_analysis.json (890 KB)
│   ├── lint.json (1.5 MB)
│   ├── patterns.json (780 KB)
│   ├── fce.json (3.2 MB)
│   └── audit_summary.json (8 KB)
│
└── readthis/ (29 files, EVERYTHING chunked)
    ├── taint_analysis_chunk01.json
    ├── taint_analysis_chunk02.json
    ├── taint_analysis_chunk03.json
    ├── graph_analysis_chunk01.json
    ├── graph_analysis_chunk02.json
    ├── fce_chunk01.json
    ├── fce_chunk02.json
    └── ... (24-27 total chunked files) ❌ NOBODY READS THIS
```

**AFTER** (Proposed - The Solution):
```
.pf/
├── raw/ (25 files, includes summaries + raw data)
│   ├── taint_analysis.json (2.1 MB) [RAW DATA - stays here]
│   ├── graph_analysis.json (890 KB) [RAW DATA - stays here]
│   ├── lint.json (1.5 MB) [RAW DATA - stays here]
│   ├── patterns.json (780 KB) [RAW DATA - stays here]
│   ├── fce.json (3.2 MB) [RAW DATA - stays here]
│   ├── deps.json (120 KB) [RAW DATA - stays here]
│   ├── audit_summary.json (8 KB) [LEGACY - still generated]
│   ├── summary_taint.json (45 KB) ⭐ [NEW - summary]
│   ├── summary_graph.json (38 KB) ⭐ [NEW - summary]
│   ├── summary_lint.json (42 KB) ⭐ [NEW - summary]
│   ├── summary_rules.json (35 KB) ⭐ [NEW - summary]
│   ├── summary_dependencies.json (28 KB) ⭐ [NEW - summary]
│   ├── summary_fce.json (41 KB) ⭐ [NEW - summary]
│   └── The_Auditor_Summary.json (95 KB) ⭐⭐ [NEW - master summary]
│
└── readthis/ (7-8 files, ONLY summaries)
    ├── summary_taint.json (45 KB, or chunked if >65KB)
    ├── summary_graph.json (38 KB)
    ├── summary_lint.json (42 KB)
    ├── summary_rules.json (35 KB)
    ├── summary_dependencies.json (28 KB)
    ├── summary_fce.json (41 KB)
    └── The_Auditor_Summary.json (95 KB, or chunked if >65KB)

    Total: 7-8 files ✅ ACTUALLY READABLE
```

**Consumption Flow**:
1. **Humans start here**: Read `The_Auditor_Summary.json` from /readthis/ (~100 KB, 30 seconds) - understand "what matters"
2. **Drill into domain**: Read `summary_<domain>.json` (~50 KB) - see top 20 findings for that analyzer
3. **Full detail needed**: Check `.pf/raw/` for complete data OR use `aud blueprint` / `aud query` for structured database access
4. **AI agents**: Start with `The_Auditor_Summary.json` for quick sync, use `aud blueprint` / `aud query` for deep analysis

**Key Behavior Change in extraction.py**:
- **OLD**: Chunk ALL files in /raw/ → 24-27 files in /readthis/
- **NEW**: Chunk ONLY summary files → 7-8 files in /readthis/
- Raw data files never copied to /readthis/ (stay in /raw/ only)

**Documentation Updates**:
- README: Explain `.pf/readthis/` is for human overview, `.pf/raw/` is archival + raw data
- CLI help: `aud summary --help` documents `--generate-domain-summaries` flag
- Make clear: Summary system for humans/quick sync, `aud blueprint` / `aud query` for AI structured access

## Verification & Testing Strategy

**Automated Tests**:
1. **Summary generation tests** (`tests/test_summary_generation.py`):
   - Verify each analyzer function generates correct structure
   - Assert summaries contain: analyzer, metrics, top_findings, query_alternative
   - Validate JSON structure matches expected schema
   - Check size is reasonable (≤100 KB for most summaries)

2. **Extraction skip test** (`tests/test_extraction_skip_raw.py`):
   - Verify extraction skips raw files (taint_analysis.json stays in /raw/ only)
   - Assert summary files are extracted to /readthis/
   - Check file count in /readthis/ is 7-8 (not 24-27)

3. **Pipeline integration test**:
   - Run `aud full` and assert all summaries exist in `.pf/raw/`
   - Verify `.pf/readthis/` has only summary files
   - Confirm backward compatibility (legacy `audit_summary.json` still generated)

**Manual Verification**:
1. Run `aud full` on a test project
2. Check `.pf/raw/` contains 7 summary files + 1 master summary
3. Check `.pf/readthis/` contains 7-8 files (no raw data files)
4. Verify each summary is human-readable (top 20 findings visible)
5. Confirm master summary cross-links to per-domain summaries

**Success Criteria**:
- ✅ `.pf/readthis/` becomes the "start here" directory (7-8 files, not 24-27)
- ✅ Each summary is actionable and references `aud query` alternative
- ✅ Master summary answers "what are top 20-30 things to fix?"
- ✅ `.pf/raw/` has full data preserved (nothing lost)
- ✅ FCE unchanged (still does correlation, not summarization)
- ✅ Backward compatible (legacy `aud summary` still works)
