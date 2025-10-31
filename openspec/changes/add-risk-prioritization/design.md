## Overview
Reorganize TheAuditor's output architecture from fragmented file explosion (20+ files) to consolidated group outputs (6 files) + guidance summaries (3-5 files). Deprecate the `.pf/readthis/` chunking system entirely in favor of database-first AI interaction via `aud query` / `aud context`. This change shifts consumption from "parse 20+ JSON files" to "query database directly + read 3-5 summaries for orientation".

## Core Principle: Database-First Architecture

**CRITICAL SHIFT**: The original proposal (per-domain summaries) is **obsolete** because we now have:
- `aud query` - Direct SQL queries over indexed code (100x faster than file parsing)
- `aud context` - Semantic classification of findings via YAML rules
- `aud planning` - Database-centric task management

**AI Consumption Model**:
1. **Primary**: Query database directly via `aud query --symbol X`, `aud context`, etc.
2. **Secondary**: Read 3-5 guidance summaries for quick orientation
3. **Fallback**: Read consolidated group files for archival/debugging only

**Key Insight**: Why chunk 20+ files into 24-27 smaller files when AIs can query the database directly in <10ms?

## Data Model & Persistence

**Primary Storage**: All findings and analysis results already exist in:
- `repo_index.db` (91MB) - Raw AST facts, symbols, calls, assignments
- `graphs.db` (79MB) - Pre-computed graph structures

**NO NEW DATABASE TABLES REQUIRED** - this change is purely about output file organization.

**Output Consolidation Targets**:
| Current (20+ files) | Consolidated (6 files) | Purpose |
|---------------------|------------------------|---------|
| graph_analysis.json<br>graph_cycles.json<br>graph_hotspots.json<br>graph_layers.json<br>call_graph.json | **graph_analysis.json** | All graph outputs combined |
| patterns.json<br>taint_analysis.json<br>vulnerabilities.json | **security_analysis.json** | All security findings combined |
| lint.json<br>cfg.json<br>deadcode.json | **quality_analysis.json** | All code quality findings combined |
| deps.json<br>docs.json<br>frameworks.json | **dependency_analysis.json** | All dependency data combined |
| terraform_findings.json<br>cdk_findings.json<br>docker_findings.json<br>workflows_findings.json | **infrastructure_analysis.json** | All IaC/CI findings combined |
| fce.json | **correlation_analysis.json** | FCE meta-findings only |

## Output Consolidation Strategy

### Phase 1: Modify Analyzers to Write to Consolidated Files

Each analyzer should append its findings to the appropriate consolidated group file instead of creating separate files.

**Example: Graph Analyzers** (theauditor/commands/graph.py):

**CURRENT** (creates 5 separate files):
```python
# graph build → graph_analysis.json
# graph analyze → graph_cycles.json, graph_hotspots.json
# graph viz → call_graph.json, graph_layers.json
```

**NEW** (all write to 1 file):
```python
def write_graph_output(analysis_type: str, data: Dict[str, Any]):
    """Append graph analysis to consolidated file."""
    consolidated_path = Path('.pf/raw/graph_analysis.json')

    # Load existing data if file exists
    if consolidated_path.exists():
        with open(consolidated_path, 'r') as f:
            consolidated = json.load(f)
    else:
        consolidated = {
            "analyzer": "graph",
            "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "analyses": {}
        }

    # Add new analysis section
    consolidated["analyses"][analysis_type] = data
    consolidated["last_updated"] = time.strftime('%Y-%m-%d %H:%M:%S')

    # Write back
    with open(consolidated_path, 'w') as f:
        json.dump(consolidated, f, indent=2)
```

**Apply this pattern to**:
- `theauditor/commands/graph.py` → `graph_analysis.json`
- `theauditor/commands/detect_patterns.py` + `theauditor/commands/taint_analyze.py` → `security_analysis.json`
- `theauditor/commands/lint.py` + `theauditor/commands/cfg.py` + `theauditor/commands/deadcode.py` → `quality_analysis.json`
- `theauditor/commands/deps.py` + `theauditor/commands/docs.py` + `theauditor/commands/detect_frameworks.py` → `dependency_analysis.json`
- `theauditor/commands/terraform.py` + `theauditor/commands/cdk.py` + `theauditor/commands/docker_analyze.py` + `theauditor/commands/workflows.py` → `infrastructure_analysis.json`

### Phase 2: Add Guidance Summary Generation

Create new command `aud summarize` (not to be confused with existing `aud summary` which generates stats).

**File**: `theauditor/commands/summarize.py` (NEW)

```python
import json
from pathlib import Path
import click
from theauditor.utils.error_handler import handle_exceptions

@click.command()
@handle_exceptions
def summarize():
    """Generate 3-5 guidance summaries from consolidated analysis files.

    Reads consolidated group files and generates focused summaries for quick
    orientation. These are truth courier documents - highlight findings, show
    metrics, point to hotspots, but NEVER recommend fixes.
    """
    raw_dir = Path('.pf/raw')

    # Generate SAST Summary
    sast = generate_sast_summary(raw_dir)
    with open(raw_dir / 'SAST_Summary.json', 'w') as f:
        json.dump(sast, f, indent=2)

    # Generate SCA Summary
    sca = generate_sca_summary(raw_dir)
    with open(raw_dir / 'SCA_Summary.json', 'w') as f:
        json.dump(sca, f, indent=2)

    # Generate Intelligence Summary
    intelligence = generate_intelligence_summary(raw_dir)
    with open(raw_dir / 'Intelligence_Summary.json', 'w') as f:
        json.dump(intelligence, f, indent=2)

    # Generate Quick Start
    quick_start = generate_quick_start(raw_dir)
    with open(raw_dir / 'Quick_Start.json', 'w') as f:
        json.dump(quick_start, f, indent=2)

    # Generate Query Guide
    query_guide = generate_query_guide()
    with open(raw_dir / 'Query_Guide.json', 'w') as f:
        json.dump(query_guide, f, indent=2)

    print("[OK] Generated 5 guidance summaries in .pf/raw/")


def generate_sast_summary(raw_dir: Path) -> Dict[str, Any]:
    """Generate SAST summary from security_analysis.json."""
    security_path = raw_dir / 'security_analysis.json'
    if not security_path.exists():
        return {"error": "security_analysis.json not found"}

    with open(security_path, 'r') as f:
        security = json.load(f)

    # Extract top 20 security findings by severity
    all_findings = []

    # Patterns
    if "patterns" in security.get("analyses", {}):
        patterns = security["analyses"]["patterns"]
        for category, findings in patterns.get("findings_by_category", {}).items():
            all_findings.extend(findings)

    # Taint flows
    if "taint" in security.get("analyses", {}):
        taint = security["analyses"]["taint"]
        all_findings.extend(taint.get("vulnerabilities", []))

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_findings = sorted(
        all_findings,
        key=lambda f: severity_order.get(f.get("severity", "low"), 99)
    )[:20]

    return {
        "summary_type": "SAST",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "total_vulnerabilities": len(all_findings),
        "by_severity": {
            "critical": sum(1 for f in all_findings if f.get("severity") == "critical"),
            "high": sum(1 for f in all_findings if f.get("severity") == "high"),
            "medium": sum(1 for f in all_findings if f.get("severity") == "medium"),
            "low": sum(1 for f in all_findings if f.get("severity") == "low")
        },
        "top_20_findings": sorted_findings,
        "detail_location": ".pf/raw/security_analysis.json",
        "query_alternative": "Use 'aud query --category jwt' or 'aud context' for structured queries"
    }


def generate_sca_summary(raw_dir: Path) -> Dict[str, Any]:
    """Generate SCA summary from dependency_analysis.json."""
    # Similar pattern - load dependency_analysis.json, extract top 20 CVEs/outdated deps
    pass


def generate_intelligence_summary(raw_dir: Path) -> Dict[str, Any]:
    """Generate intelligence summary from graph + correlation analysis."""
    # Load graph_analysis.json + correlation_analysis.json
    # Extract top 20 hotspots, cycles, FCE correlations
    pass


def generate_quick_start(raw_dir: Path) -> Dict[str, Any]:
    """Generate ultra-condensed top 10 across ALL domains."""
    # Load all 3 summaries, pick top 10 critical issues
    pass


def generate_query_guide() -> Dict[str, Any]:
    """Generate query reference guide."""
    return {
        "guide_type": "Query Reference",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "purpose": "AI assistants should query database directly instead of parsing JSON files",
        "queries_by_domain": {
            "Security Patterns": [
                "aud query --category jwt",
                "aud query --category oauth",
                "aud query --pattern 'password%'"
            ],
            "Taint Analysis": [
                "aud query --variable user_input --show-flow",
                "aud query --symbol db.execute --show-callers"
            ],
            "Graph Analysis": [
                "aud query --file api.py --show-dependencies",
                "aud query --symbol authenticate --show-callers --depth 3"
            ],
            "Code Quality": [
                "aud query --symbol calculate_total --show-callees",
                "aud cfg analyze --complexity-threshold 20"
            ],
            "Dependencies": [
                "aud deps --vuln-scan",
                "aud docs fetch"
            ],
            "Infrastructure": [
                "aud terraform analyze",
                "aud workflows analyze"
            ],
            "Semantic Classification": [
                "aud context --file refactor_rules.yaml"
            ]
        },
        "performance": {
            "database_query": "<10ms per query",
            "json_parsing": "1-2s to read multiple files",
            "token_savings": "5,000-10,000 tokens per refactoring iteration"
        }
    }
```

### Phase 3: Deprecate Extraction System

**Remove from pipeline** (theauditor/pipelines.py:1462-1476):

**BEFORE**:
```python
# CRITICAL: Run extraction AFTER FCE and BEFORE report
if "factual correlation" in phase_name.lower():
    try:
        from theauditor.extraction import extract_all_to_readthis

        log_output("\n" + "="*60)
        log_output("[EXTRACTION] Creating AI-consumable chunks from raw data")
        log_output("="*60)

        extraction_start = time.time()
        extraction_success = extract_all_to_readthis(root)
        extraction_elapsed = time.time() - extraction_start
```

**AFTER**:
```python
# CRITICAL: Run summarize AFTER FCE
if "factual correlation" in phase_name.lower():
    try:
        log_output("\n" + "="*60)
        log_output("[SUMMARIZE] Generating guidance summaries")
        log_output("="*60)

        # Call aud summarize
        summarize_cmd = [sys.executable, "-m", "theauditor.cli", "summarize"]
        summarize_result = subprocess.run(summarize_cmd, cwd=root, capture_output=True, text=True)

        if summarize_result.returncode == 0:
            log_output("[OK] Generated 5 guidance summaries in .pf/raw/")
        else:
            log_output(f"[WARN] Summarize failed: {summarize_result.stderr}")
```

**Mark extraction.py as deprecated**:
- Add comment at top of file: `# DEPRECATED: Extraction system obsolete - use 'aud query' for database-first AI interaction`
- Keep file for backward compatibility but log warning when called

**Update .gitignore**:
```
# Deprecated - no longer generated
.pf/readthis/
```

### Phase 4: Update Documentation

**Update README.md OUTPUT STRUCTURE section**:

**BEFORE**:
```
.pf/
├── raw/          # Immutable tool outputs (ground truth)
├── readthis/     # AI-optimized chunks (<65KB each)
│   ├── *_chunk01.json
│   └── summary.json
```

**AFTER**:
```
.pf/
├── raw/
│   ├── Consolidated Analysis (6 files):
│   │   ├── graph_analysis.json        # All graph outputs
│   │   ├── security_analysis.json     # Patterns + taint + vulnerabilities
│   │   ├── quality_analysis.json      # Lint + cfg + deadcode
│   │   ├── dependency_analysis.json   # Deps + docs + frameworks
│   │   ├── infrastructure_analysis.json # Terraform + CDK + Docker + Workflows
│   │   └── correlation_analysis.json  # FCE meta-findings
│   │
│   └── Guidance Summaries (5 files):
│       ├── SAST_Summary.json         # Top 20 security findings
│       ├── SCA_Summary.json          # Top 20 dependency issues
│       ├── Intelligence_Summary.json # Top 20 code intelligence insights
│       ├── Quick_Start.json          # Top 10 critical issues
│       └── Query_Guide.json          # How to query via aud commands
│
├── repo_index.db   # PRIMARY DATA SOURCE - query via 'aud query'
└── graphs.db       # Graph structures - query via 'aud graph'
```

## Verification & Testing Strategy

**Verification Goals**:
1. Verify analyzers write to consolidated files (not separate files)
2. Verify summaries are generated after FCE
3. Verify extraction is no longer called
4. Verify 6 consolidated files exist in .pf/raw/
5. Verify 5 guidance summaries exist in .pf/raw/
6. Verify .pf/readthis/ is NOT created

**Manual Test**:
```bash
# Clean slate
rm -rf .pf/

# Run full pipeline
aud full --offline

# Check outputs
ls .pf/raw/
# EXPECTED:
#   graph_analysis.json
#   security_analysis.json
#   quality_analysis.json
#   dependency_analysis.json
#   infrastructure_analysis.json
#   correlation_analysis.json
#   SAST_Summary.json
#   SCA_Summary.json
#   Intelligence_Summary.json
#   Quick_Start.json
#   Query_Guide.json

# Verify readthis NOT created
ls .pf/readthis/ 2>&1
# EXPECTED: "No such file or directory"

# Test database queries work
aud query --symbol authenticate
aud query --category jwt
aud context --file test_rules.yaml
```

**Success Criteria**:
- ✅ 6 consolidated files in .pf/raw/ (not 20+)
- ✅ 5 guidance summaries in .pf/raw/
- ✅ .pf/readthis/ directory NOT created
- ✅ All data preserved in consolidated files
- ✅ Database queries return correct results
- ✅ Summaries are truth couriers (no recommendations)
- ✅ Pipeline runs without extraction stage
