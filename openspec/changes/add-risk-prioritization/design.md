# Design Document - add-risk-prioritization (CORRECTED)

## Overview
Replace TheAuditor's extraction.py chunking system (generates 24-27 chunk files) with 5 intelligent summaries in `.pf/readthis/`. Keep ALL `/raw/` tool outputs UNCHANGED. This change shifts `/readthis/` from "chunked raw data" to "FCE-guided summaries for quick orientation".

## Core Principle: Immutable Raw Outputs + Smart Summaries

**CRITICAL RULE**: `/raw/` files are immutable ground truth. NEVER consolidate or modify analyzer outputs.

**Architecture**:
1. **`/raw/`** = 20+ separate tool outputs (patterns.json, taint.json, cfg.json, fce.json, etc.) - UNCHANGED
2. **`/readthis/`** = 5 intelligent summaries that READ FROM `/raw/` files
3. **Database** = Primary data source (query with `aud query`, `aud context`)

**Why this design?**:
- Raw tool outputs are "our only value" - consolidation loses ground truth fidelity
- Chunking provides no value when database queries are 100x faster
- Summaries provide quick orientation using FCE correlations

## Data Flow

```
Analyzers → /raw/ separate files (UNCHANGED)
                    ↓
               FCE reads /raw/
                    ↓
            FCE writes fce.json
                    ↓
     `aud summarize` reads /raw/ + fce.json
                    ↓
        Summaries written to /readthis/
```

**Key Points**:
- Analyzers DON'T CHANGE - they continue writing to separate /raw/ files
- Summaries READ FROM existing /raw/ files, don't modify them
- No consolidation - /raw/ structure stays 1:1 with current pipeline

## File Structure

### BEFORE (current):
```
.pf/
├── raw/
│   ├── patterns.json       (detect-patterns output)
│   ├── taint.json          (taint-analyze output)
│   ├── cfg.json            (cfg analyze output)
│   ├── deadcode.json       (deadcode output)
│   ├── frameworks.json     (detect-frameworks output)
│   ├── graph_analysis.json (graph analyze output)
│   ├── fce.json            (fce correlations)
│   └── ... (20+ separate files)
├── readthis/
│   ├── patterns_chunk01.json
│   ├── patterns_chunk02.json
│   ├── taint_chunk01.json
│   └── ... (24-27 chunked files)
└── repo_index.db
```

### AFTER (target):
```
.pf/
├── raw/
│   ├── patterns.json       (UNCHANGED - detect-patterns output)
│   ├── taint.json          (UNCHANGED - taint-analyze output)
│   ├── cfg.json            (UNCHANGED - cfg analyze output)
│   ├── deadcode.json       (UNCHANGED - deadcode output)
│   ├── frameworks.json     (UNCHANGED - detect-frameworks output)
│   ├── graph_analysis.json (UNCHANGED - graph analyze output)
│   ├── fce.json            (UNCHANGED - fce correlations)
│   └── ... (20+ separate files - ALL UNCHANGED)
├── readthis/
│   ├── SAST_Summary.json         (NEW - security findings summary)
│   ├── SCA_Summary.json          (NEW - dependency issues summary)
│   ├── Intelligence_Summary.json (NEW - code intelligence summary)
│   ├── Quick_Start.json          (NEW - FCE-guided top issues)
│   └── Query_Guide.json          (NEW - database query reference)
└── repo_index.db
```

## Implementation Design

### Phase 1: Create Summarize Command

**File**: `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\summarize.py` (NEW)

**Structure**:
```python
import json
from pathlib import Path
import click
from typing import Dict, Any

@click.command("summarize")
@click.option("--project-path", default=".", help="Root directory to analyze")
def summarize(project_path):
    """Generate 5 intelligent summaries from raw analysis files.

    Reads from .pf/raw/ files and generates summaries in .pf/readthis/.
    Summaries are truth couriers - show facts and FCE correlations only.
    """
    project_path = Path(project_path).resolve()
    raw_dir = project_path / ".pf" / "raw"
    readthis_dir = project_path / ".pf" / "readthis"

    # Create readthis directory
    readthis_dir.mkdir(parents=True, exist_ok=True)

    # Generate 5 summaries
    summaries = {
        "SAST_Summary.json": generate_sast_summary(raw_dir),
        "SCA_Summary.json": generate_sca_summary(raw_dir),
        "Intelligence_Summary.json": generate_intelligence_summary(raw_dir),
        "Quick_Start.json": generate_quick_start(raw_dir),
        "Query_Guide.json": generate_query_guide()
    }

    # Write summaries
    for filename, data in summaries.items():
        output_path = readthis_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    click.echo(f"[OK] Generated 5 summaries in {readthis_dir}")


def generate_sast_summary(raw_dir: Path) -> Dict[str, Any]:
    """Generate security findings summary."""
    # Read from patterns.json, taint.json, docker_findings.json, github_workflows.json
    patterns_path = raw_dir / "patterns.json"
    taint_path = raw_dir / "taint.json"
    fce_path = raw_dir / "fce.json"

    # Count findings
    total_findings = 0
    patterns_count = 0
    taint_count = 0
    fce_security_correlations = 0

    # Read patterns.json if exists
    if patterns_path.exists():
        with open(patterns_path, 'r') as f:
            patterns_data = json.load(f)
            patterns_count = len(patterns_data.get("findings", []))
            total_findings += patterns_count

    # Read taint.json if exists
    if taint_path.exists():
        with open(taint_path, 'r') as f:
            taint_data = json.load(f)
            taint_count = len(taint_data.get("vulnerabilities", []))
            total_findings += taint_count

    # Read FCE correlations if exists
    if fce_path.exists():
        with open(fce_path, 'r') as f:
            fce_data = json.load(f)
            # Count security-related FCE findings
            fce_security_correlations = len([
                f for f in fce_data.get("correlations", {}).get("meta_findings", [])
                if "security" in f.get("type", "").lower()
            ])

    return {
        "summary": f"{total_findings} security findings detected ({patterns_count} patterns, {taint_count} taint paths), {fce_security_correlations} FCE security correlations",
        "counts": {
            "total_findings": total_findings,
            "patterns": patterns_count,
            "taint_paths": taint_count,
            "fce_security_correlations": fce_security_correlations
        },
        "source_files": ["patterns.json", "taint.json", "fce.json"],
        "query_alternative": "aud query --tool patterns --severity critical"
    }


def generate_sca_summary(raw_dir: Path) -> Dict[str, Any]:
    """Generate dependency issues summary."""
    frameworks_path = raw_dir / "frameworks.json"

    frameworks_count = 0

    # Read frameworks.json if exists
    if frameworks_path.exists():
        with open(frameworks_path, 'r') as f:
            frameworks_data = json.load(f)
            if isinstance(frameworks_data, list):
                frameworks_count = len(frameworks_data)

    return {
        "summary": f"{frameworks_count} frameworks detected",
        "counts": {
            "frameworks_detected": frameworks_count
        },
        "source_files": ["frameworks.json"],
        "query_alternative": "aud query --symbol-type import --group-by package"
    }


def generate_intelligence_summary(raw_dir: Path) -> Dict[str, Any]:
    """Generate code intelligence summary."""
    graph_path = raw_dir / "graph_analysis.json"
    cfg_path = raw_dir / "cfg.json"
    fce_path = raw_dir / "fce.json"

    hotspots = 0
    cycles = 0
    complex_functions = 0
    fce_meta_findings = 0

    # Read graph_analysis.json if exists
    if graph_path.exists():
        with open(graph_path, 'r') as f:
            graph_data = json.load(f)
            hotspots = len(graph_data.get("hotspots", []))
            cycles = len(graph_data.get("cycles", []))

    # Read cfg.json if exists
    if cfg_path.exists():
        with open(cfg_path, 'r') as f:
            cfg_data = json.load(f)
            complex_functions = len(cfg_data.get("complex_functions", []))

    # Read fce.json for meta-findings
    if fce_path.exists():
        with open(fce_path, 'r') as f:
            fce_data = json.load(f)
            fce_meta_findings = len(fce_data.get("correlations", {}).get("meta_findings", []))

    return {
        "summary": f"{hotspots} hotspots, {cycles} cycles, {complex_functions} complex functions, {fce_meta_findings} FCE meta-findings",
        "counts": {
            "architectural_hotspots": hotspots,
            "dependency_cycles": cycles,
            "complex_functions": complex_functions,
            "fce_meta_findings": fce_meta_findings
        },
        "source_files": ["graph_analysis.json", "cfg.json", "fce.json"],
        "query_alternative": "aud context --file api.py --show-dependencies"
    }


def generate_quick_start(raw_dir: Path) -> Dict[str, Any]:
    """Generate top FCE-correlated issues."""
    fce_path = raw_dir / "fce.json"

    top_issues = []

    # Read fce.json for meta-findings
    if fce_path.exists():
        with open(fce_path, 'r') as f:
            fce_data = json.load(f)
            meta_findings = fce_data.get("correlations", {}).get("meta_findings", [])

            # Take top 10 FCE findings
            for finding in meta_findings[:10]:
                top_issues.append({
                    "type": finding.get("type", "UNKNOWN"),
                    "file": finding.get("file", "unknown"),
                    "finding_count": finding.get("finding_count", 0),
                    "message": finding.get("message", "")
                })

    return {
        "summary": f"{len(top_issues)} critical FCE correlations",
        "top_issues": top_issues,
        "guidance": "These are factual correlations identified by FCE. Query database for details.",
        "query_examples": [
            "aud query --file api.py --show-calls",
            "aud context --file api.py --show-dependencies"
        ],
        "source_files": ["fce.json"]
    }


def generate_query_guide() -> Dict[str, Any]:
    """Generate database query reference."""
    return {
        "purpose": "AI assistants should query database directly instead of parsing JSON files",
        "security_queries": [
            "aud query --tool taint --show-paths",
            "aud query --tool patterns --severity critical"
        ],
        "dependency_queries": [
            "aud query --symbol-type import --group-by package"
        ],
        "architecture_queries": [
            "aud context --file api.py --show-dependencies",
            "aud query --calls main --depth 3"
        ],
        "performance_note": "Database queries are 100x faster than parsing JSON files"
    }
```

**Register in CLI** (`C:\Users\santa\Desktop\TheAuditor\theauditor\cli.py`):
```python
# Add import at top
from theauditor.commands.summarize import summarize

# Add registration with other commands
cli.add_command(summarize)
```

### Phase 2: Modify Pipeline

**File**: `C:\Users\santa\Desktop\TheAuditor\theauditor\pipelines.py`

**Find extraction call** (around line 1462-1476):
```python
# OLD CODE - REMOVE THIS
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

**Replace with**:
```python
# NEW CODE - ADD THIS
if "factual correlation" in phase_name.lower():
    try:
        import subprocess
        import sys

        log_output("\n" + "="*60)
        log_output("[SUMMARIZE] Generating guidance summaries")
        log_output("="*60)

        # Call aud summarize
        summarize_cmd = [sys.executable, "-m", "theauditor.cli", "summarize", "--project-path", str(root)]
        summarize_result = subprocess.run(summarize_cmd, cwd=root, capture_output=True, text=True, timeout=60)

        if summarize_result.returncode == 0:
            log_output("[OK] Generated 5 guidance summaries in .pf/readthis/")
        else:
            log_output(f"[WARN] Summarize failed: {summarize_result.stderr}")
    except Exception as e:
        log_output(f"[ERROR] Summarize exception: {e}")
```

**Remove extraction import** (if it exists at top of file):
```python
# REMOVE THIS LINE
from theauditor.extraction import extract_all_to_readthis
```

### Phase 3: Deprecate Extraction System

**Rename extraction.py**:
```bash
# Windows command
move C:\Users\santa\Desktop\TheAuditor\theauditor\extraction.py C:\Users\santa\Desktop\TheAuditor\theauditor\extraction.py.bak
```

**Verify no imports remain**:
```bash
# Search for any remaining imports
grep -r "from theauditor.extraction import" C:\Users\santa\Desktop\TheAuditor\theauditor\
grep -r "import extraction" C:\Users\santa\Desktop\TheAuditor\theauditor\
# Should find ZERO matches
```

**Update .gitignore** (`C:\Users\santa\Desktop\TheAuditor\.gitignore`):
```
# Chunked files deprecated - only summaries remain
.pf/readthis/*_chunk*.json
```

### Phase 4: NO Changes to Analyzers

**CRITICAL**: Do NOT modify any analyzer commands. They continue writing to separate /raw/ files:

- ✅ `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\graph.py` - UNCHANGED
- ✅ `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\detect_patterns.py` - UNCHANGED
- ✅ `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\taint.py` - UNCHANGED
- ✅ `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\cfg.py` - UNCHANGED
- ✅ `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\deadcode.py` - UNCHANGED
- ✅ `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\detect_frameworks.py` - UNCHANGED
- ✅ `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\terraform.py` - UNCHANGED
- ✅ `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\docker_analyze.py` - UNCHANGED
- ✅ `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\workflows.py` - UNCHANGED
- ✅ `C:\Users\santa\Desktop\TheAuditor\theauditor\fce.py` - UNCHANGED

## Truth Courier Principle

**Summaries MUST follow truth courier format**:
- ✅ Show counts and metrics
- ✅ Show FCE correlations as-is
- ✅ Show file:line locations
- ✅ Cross-reference to /raw/ files
- ❌ NO severity filtering
- ❌ NO recommendations
- ❌ NO interpretation

**Example**:
```json
{
  "summary": "1250 security findings detected (890 patterns, 360 taint paths), 42 FCE security correlations",
  "counts": { "total_findings": 1250, "patterns": 890, "taint_paths": 360 },
  "query_alternative": "aud query --tool patterns --severity critical"
}
```

## Verification Strategy

**Success Criteria**:
1. ✅ All 20+ /raw/ files UNCHANGED (patterns.json, taint.json, cfg.json, etc.)
2. ✅ 5 summaries in /readthis/ (SAST, SCA, Intelligence, Quick_Start, Query_Guide)
3. ✅ NO chunks in /readthis/ (*_chunk*.json files)
4. ✅ extraction.py renamed to .bak
5. ✅ Pipeline runs without errors
6. ✅ Summaries follow truth courier model

**Test Commands**:
```bash
# Clean test
rm -rf C:\Users\santa\Desktop\TheAuditor\.pf

# Run pipeline
aud init
aud full --offline

# Verify /raw/ unchanged
dir C:\Users\santa\Desktop\TheAuditor\.pf\raw
# EXPECT: patterns.json, taint.json, cfg.json, fce.json, etc. (20+ files)

# Verify /readthis/ has summaries only
dir C:\Users\santa\Desktop\TheAuditor\.pf\readthis
# EXPECT: SAST_Summary.json, SCA_Summary.json, Intelligence_Summary.json, Quick_Start.json, Query_Guide.json (5 files)

# Verify no chunks
dir C:\Users\santa\Desktop\TheAuditor\.pf\readthis\*_chunk*.json
# EXPECT: "File Not Found"

# Test summaries
type C:\Users\santa\Desktop\TheAuditor\.pf\readthis\SAST_Summary.json
# EXPECT: JSON with counts, NO recommendations
```

## Risk Assessment

**Risk Level**: VERY LOW

**Why**:
- NO changes to analyzer commands (ground truth preserved)
- NO changes to database schema
- NO changes to /raw/ file structure
- Only ADDING new summaries to /readthis/
- Extraction removal is safe (already deprecated)

**Rollback Plan**:
```bash
# If something breaks, revert:
git checkout HEAD -- C:\Users\santa\Desktop\TheAuditor\theauditor\commands\summarize.py
git checkout HEAD -- C:\Users\santa\Desktop\TheAuditor\theauditor\pipelines.py
git checkout HEAD -- C:\Users\santa\Desktop\TheAuditor\theauditor\cli.py
move C:\Users\santa\Desktop\TheAuditor\theauditor\extraction.py.bak C:\Users\santa\Desktop\TheAuditor\theauditor\extraction.py
```

## Timeline Estimate

- Create summarize.py: 2-3 hours
- Modify pipeline: 30 minutes
- Rename extraction.py: 5 minutes
- Update documentation: 1 hour
- Testing & verification: 1-2 hours
- **Total**: 5-7 hours

## Files Modified Summary

**New Files** (1):
- `C:\Users\santa\Desktop\TheAuditor\theauditor\commands\summarize.py`

**Modified Files** (2):
- `C:\Users\santa\Desktop\TheAuditor\theauditor\pipelines.py` (remove extraction call, add summarize call)
- `C:\Users\santa\Desktop\TheAuditor\theauditor\cli.py` (register summarize command)

**Renamed Files** (1):
- `C:\Users\santa\Desktop\TheAuditor\theauditor\extraction.py` → `extraction.py.bak`

**NO Modifications**:
- All 10+ analyzer commands - UNTOUCHED
- All /raw/ file outputs - UNTOUCHED
- Database schema - UNTOUCHED
