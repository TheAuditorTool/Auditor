# Implementation Plan: Risk Prioritization (Summary System Overhaul)

**Goal**: Replace 24-27 chunked files with focused per-domain summaries + one master summary

## Current Architecture (ACTUAL CODE)

### File: `theauditor/commands/summary.py` (301 lines)
**Current Behavior**:
- Generates ONE file: `.pf/raw/audit_summary.json` (overall stats only)
- Loads from: lint.json, patterns.json, graph_analysis.json, taint_analysis.json, fce.json, deps.json
- Function: `summary(root, raw_dir, out)` - lines 15-259
- Helper: `_load_frameworks_from_db(project_path)` - lines 261-297
- Aggregates by severity: critical, high, medium, low, info
- Output: Single summary with overall stats, no per-domain files

### File: `theauditor/extraction.py` (534 lines)
**Current Behavior**:
- Pure courier model - chunks ALL files in /raw/
- Main: `extract_all_to_readthis(root_path_str, budget_kb)` - lines 378-534
- Chunker: `_chunk_large_file(raw_path, max_chunk_size)` - lines 28-363
- Chunks files > 65KB into: `filename_chunk01.json`, `filename_chunk02.json`, etc.
- Result: 24-27 chunked files in `/readthis/`

## Problem Statement (USER CONFIRMED)

**Current**: 24-27 chunked files in /readthis/ (call_graph_chunk01-03, taint_analysis_chunk01-02, etc.) - nobody reads this

**Desired**:
1. Per-domain summaries (summary_graph.json, summary_taint.json, etc.)
2. ONE master summary: The_Auditor_Summary.json
3. Store summaries in /raw/ (any size, NOT chunked initially)
4. Chunk ONLY the summaries in extraction.py (leave raw outputs alone)
5. Each summary mentions: "This could also have been queried with: aud query --{domain}"

---

## PHASE 1: Modify `theauditor/commands/summary.py`

### 1.1 Add Per-Domain Summary Generation Functions

**INSERT AFTER line 297** (after `_load_frameworks_from_db()` function):

```python
def generate_taint_summary(raw_path: Path, db_path: Path) -> Dict[str, Any]:
    """Generate taint analysis domain summary.

    Returns top findings + key metrics from taint analysis.
    Designed to be human-readable and AI-consumable.
    """
    # Load raw taint data
    taint = {}
    if (raw_path / "taint_analysis.json").exists():
        with open(raw_path / "taint_analysis.json", 'r', encoding='utf-8') as f:
            taint = json.load(f)

    # Extract top 20 taint paths by severity
    taint_paths = taint.get("taint_paths", [])

    # Sort by severity (critical > high > medium > low)
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


def generate_graph_summary(raw_path: Path, db_path: Path) -> Dict[str, Any]:
    """Generate graph analysis domain summary.

    Returns cycles, hotspots, impact metrics from graph analysis.
    """
    # Load raw graph data
    graph_analysis = {}
    if (raw_path / "graph_analysis.json").exists():
        with open(raw_path / "graph_analysis.json", 'r', encoding='utf-8') as f:
            graph_analysis = json.load(f)

    # Extract top cycles and hotspots
    cycles = graph_analysis.get("cycles", [])[:20]  # Top 20 cycles
    hotspots = graph_analysis.get("hotspots", [])[:20]  # Top 20 hotspots

    summary_data = graph_analysis.get("summary", {})

    summary = {
        "analyzer": "graph",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "metrics": {
            "cycles_detected": len(graph_analysis.get("cycles", [])),
            "hotspots_identified": len(graph_analysis.get("hotspots", [])),
            "import_nodes": summary_data.get("import_graph", {}).get("nodes", 0),
            "import_edges": summary_data.get("import_graph", {}).get("edges", 0),
            "graph_density": summary_data.get("import_graph", {}).get("density", 0)
        },
        "top_cycles": cycles,
        "top_hotspots": hotspots,
        "detail_location": ".pf/raw/graph_analysis.json",
        "query_alternative": "This domain can also be queried with: aud blueprint or aud graph query"
    }

    if "health_metrics" in summary_data:
        summary["metrics"]["health_grade"] = summary_data["health_metrics"].get("health_grade", "N/A")
        summary["metrics"]["fragility_score"] = summary_data["health_metrics"].get("fragility_score", 0)

    return summary


def generate_lint_summary(raw_path: Path, db_path: Path) -> Dict[str, Any]:
    """Generate lint analysis domain summary.

    Returns top lint findings by severity + file hotspots.
    """
    # Load raw lint data
    lint_data = {}
    if (raw_path / "lint.json").exists():
        with open(raw_path / "lint.json", 'r', encoding='utf-8') as f:
            lint_data = json.load(f)

    findings = lint_data.get("findings", [])

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        findings,
        key=lambda f: severity_order.get(f.get("severity", "info").lower(), 99)
    )[:20]

    # Count by severity
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for finding in findings:
        severity = finding.get("severity", "info").lower()
        if severity in by_severity:
            by_severity[severity] += 1

    # Count file hotspots (files with most issues)
    file_counts = defaultdict(int)
    for finding in findings:
        file_counts[finding.get("file", "unknown")] += 1

    top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    summary = {
        "analyzer": "lint",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "metrics": {
            "total_issues": len(findings),
            "by_severity": by_severity,
            "files_affected": len(file_counts)
        },
        "top_findings": sorted_findings,
        "file_hotspots": [{"file": f, "issue_count": c} for f, c in top_files],
        "detail_location": ".pf/raw/lint.json",
        "query_alternative": "This domain can also be queried with: aud blueprint or directly from lint.json"
    }

    return summary


def generate_rules_summary(raw_path: Path, db_path: Path) -> Dict[str, Any]:
    """Generate security rules domain summary.

    Returns pattern matches grouped by category + critical issues.
    """
    # Load raw patterns data
    patterns = {}
    patterns_path = raw_path / "patterns.json"
    if not patterns_path.exists():
        patterns_path = raw_path / "findings.json"

    if patterns_path.exists():
        with open(patterns_path, 'r', encoding='utf-8') as f:
            patterns = json.load(f)

    findings = patterns.get("findings", [])

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        findings,
        key=lambda f: severity_order.get(f.get("severity", "info").lower(), 99)
    )[:20]

    # Count by severity
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for finding in findings:
        severity = finding.get("severity", "info").lower()
        if severity in by_severity:
            by_severity[severity] += 1

    # Group by rule/category
    by_rule = defaultdict(int)
    for finding in findings:
        rule = finding.get("rule", "unknown")
        by_rule[rule] += 1

    summary = {
        "analyzer": "rules",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "metrics": {
            "total_patterns_matched": len(findings),
            "by_severity": by_severity,
            "unique_rules": len(by_rule)
        },
        "top_findings": sorted_findings,
        "rules_breakdown": dict(sorted(by_rule.items(), key=lambda x: x[1], reverse=True)[:15]),
        "detail_location": ".pf/raw/patterns.json",
        "query_alternative": "This domain can also be queried with: aud blueprint or from patterns.json"
    }

    return summary


def generate_dependencies_summary(raw_path: Path, db_path: Path) -> Dict[str, Any]:
    """Generate dependencies domain summary.

    Returns vulnerable packages + outdated deps.
    """
    # Load raw dependency data
    deps = {}
    deps_latest = {}
    if (raw_path / "deps.json").exists():
        with open(raw_path / "deps.json", 'r', encoding='utf-8') as f:
            deps = json.load(f)

    if (raw_path / "deps_latest.json").exists():
        with open(raw_path / "deps_latest.json", 'r', encoding='utf-8') as f:
            deps_latest = json.load(f)

    # Extract vulnerability info
    vulnerable_packages = []
    outdated_packages = []

    if isinstance(deps_latest, dict) and "packages" in deps_latest:
        for pkg in deps_latest["packages"]:
            if isinstance(pkg, dict):
                if pkg.get("vulnerabilities"):
                    vulnerable_packages.append({
                        "name": pkg.get("name"),
                        "version": pkg.get("version"),
                        "vulnerabilities": pkg["vulnerabilities"]
                    })
                if pkg.get("outdated"):
                    outdated_packages.append({
                        "name": pkg.get("name"),
                        "current": pkg.get("version"),
                        "latest": pkg.get("latest_version")
                    })

    # Count total dependencies
    total_deps = 0
    if isinstance(deps, dict):
        total_deps = len(deps.get("dependencies", []))
    elif isinstance(deps, list):
        total_deps = len(deps)

    summary = {
        "analyzer": "dependencies",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "metrics": {
            "total_dependencies": total_deps,
            "vulnerable_packages": len(vulnerable_packages),
            "outdated_packages": len(outdated_packages),
            "total_vulnerabilities": sum(len(p["vulnerabilities"]) for p in vulnerable_packages)
        },
        "vulnerable_packages": vulnerable_packages[:20],  # Top 20
        "outdated_packages": outdated_packages[:20],  # Top 20
        "detail_location": ".pf/raw/deps.json and .pf/raw/deps_latest.json",
        "query_alternative": "This domain can also be queried with: aud deps or from deps.json"
    }

    return summary


def generate_fce_summary(raw_path: Path, db_path: Path) -> Dict[str, Any]:
    """Generate FCE (Factual Correlation Engine) domain summary.

    Returns correlated findings + meta-findings + hotspots.
    """
    # Load raw FCE data
    fce = {}
    if (raw_path / "fce.json").exists():
        with open(raw_path / "fce.json", 'r', encoding='utf-8') as f:
            fce = json.load(f)

    correlations = fce.get("correlations", {})
    summary_block = fce.get("summary", {})

    # Extract top meta-findings (multiple tools flagged same issue)
    meta_findings = correlations.get("meta_findings", [])[:20]

    # Extract top factual clusters
    factual_clusters = correlations.get("factual_clusters", [])[:20]

    summary = {
        "analyzer": "fce",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "metrics": {
            "raw_findings": summary_block.get("raw_findings", len(fce.get("all_findings", []))),
            "meta_findings": summary_block.get("meta_findings", len(meta_findings)),
            "factual_clusters": summary_block.get("factual_clusters", len(factual_clusters)),
            "path_clusters": correlations.get("total_path_clusters", 0),
            "hotspots_correlated": correlations.get("total_hotspots", 0)
        },
        "top_meta_findings": meta_findings,
        "top_clusters": factual_clusters,
        "detail_location": ".pf/raw/fce.json",
        "query_alternative": "This domain represents correlated findings - see fce.json for full correlation data"
    }

    return summary


def generate_master_summary(raw_path: Path, db_path: Path, domain_summaries: Dict[str, Dict]) -> Dict[str, Any]:
    """Generate THE AUDITOR SUMMARY - master summary combining all domains.

    The mother of all summaries. Top 20-30 findings across ALL analyzers.
    Shows cross-domain correlation and provides single entry point.
    """
    # Aggregate all findings from domain summaries
    all_findings = []

    # Taint findings
    if "taint" in domain_summaries:
        for finding in domain_summaries["taint"].get("top_findings", []):
            all_findings.append({
                "domain": "taint",
                "severity": finding.get("severity", "medium"),
                "file": finding.get("source", {}).get("file", "unknown"),
                "line": finding.get("source", {}).get("line", 0),
                "message": f"Taint path: {finding.get('source', {}).get('file', '?')} -> {finding.get('sink', {}).get('file', '?')}",
                "detail": finding
            })

    # Lint findings
    if "lint" in domain_summaries:
        for finding in domain_summaries["lint"].get("top_findings", [])[:10]:  # Limit lint to 10
            all_findings.append({
                "domain": "lint",
                "severity": finding.get("severity", "info").lower(),
                "file": finding.get("file", "unknown"),
                "line": finding.get("line", 0),
                "message": finding.get("message", ""),
                "detail": finding
            })

    # Rules findings
    if "rules" in domain_summaries:
        for finding in domain_summaries["rules"].get("top_findings", [])[:10]:
            all_findings.append({
                "domain": "rules",
                "severity": finding.get("severity", "info").lower(),
                "file": finding.get("file", "unknown"),
                "line": finding.get("line", 0),
                "message": finding.get("message", ""),
                "detail": finding
            })

    # Dependencies findings (vulnerabilities)
    if "dependencies" in domain_summaries:
        for pkg in domain_summaries["dependencies"].get("vulnerable_packages", [])[:5]:
            all_findings.append({
                "domain": "dependencies",
                "severity": "high",  # Vulnerabilities are always high
                "file": "package dependencies",
                "line": 0,
                "message": f"Vulnerable package: {pkg.get('name')} ({len(pkg.get('vulnerabilities', []))} CVEs)",
                "detail": pkg
            })

    # Sort all findings by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(
        all_findings,
        key=lambda f: severity_order.get(f.get("severity", "info"), 99)
    )[:30]  # Top 30 findings across ALL domains

    # Calculate overall metrics
    total_findings_by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for finding in all_findings:
        severity = finding.get("severity", "info")
        if severity in total_findings_by_severity:
            total_findings_by_severity[severity] += 1

    # Per-domain metrics
    per_domain_metrics = {}
    for domain, summary in domain_summaries.items():
        metrics = summary.get("metrics", {})
        per_domain_metrics[domain] = metrics

    # Build master summary
    master = {
        "analyzer": "THE_AUDITOR_MASTER",
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "overview": {
            "total_findings": len(all_findings),
            "by_severity": total_findings_by_severity,
            "domains_analyzed": len(domain_summaries)
        },
        "per_domain_metrics": per_domain_metrics,
        "top_findings_all_domains": sorted_findings,
        "per_domain_summaries": {
            domain: f".pf/raw/summary_{domain}.json"
            for domain in domain_summaries.keys()
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

    return master
```

### 1.2 Modify Main `summary()` Function

**REPLACE lines 15-259** with:

```python
@click.command()
@click.option("--root", default=".", help="Root directory")
@click.option("--raw-dir", default="./.pf/raw", help="Raw outputs directory")
@click.option("--out", default="./.pf/raw/audit_summary.json", help="Output path for summary")
@click.option("--generate-domain-summaries", is_flag=True, help="Generate per-domain summaries")
def summary(root, raw_dir, out, generate_domain_summaries):
    """Generate comprehensive audit summary from all phases.

    If --generate-domain-summaries is set, generates:
    - Per-domain summaries: summary_taint.json, summary_graph.json, etc.
    - Master summary: The_Auditor_Summary.json

    Otherwise, generates only the legacy audit_summary.json (backward compat).
    """
    start_time = time.time()
    raw_path = Path(raw_dir)
    root_path = Path(root)
    db_path = root_path / ".pf" / "repo_index.db"

    if generate_domain_summaries:
        # NEW FLOW: Generate per-domain summaries + master summary
        print("[SUMMARY] Generating per-domain summaries...")

        domain_summaries = {}

        # Generate taint summary
        if (raw_path / "taint_analysis.json").exists():
            print("  [OK] Generating summary_taint.json")
            domain_summaries["taint"] = generate_taint_summary(raw_path, db_path)
            taint_out = raw_path / "summary_taint.json"
            with open(taint_out, 'w', encoding='utf-8') as f:
                json.dump(domain_summaries["taint"], f, indent=2)

        # Generate graph summary
        if (raw_path / "graph_analysis.json").exists():
            print("  [OK] Generating summary_graph.json")
            domain_summaries["graph"] = generate_graph_summary(raw_path, db_path)
            graph_out = raw_path / "summary_graph.json"
            with open(graph_out, 'w', encoding='utf-8') as f:
                json.dump(domain_summaries["graph"], f, indent=2)

        # Generate lint summary
        if (raw_path / "lint.json").exists():
            print("  [OK] Generating summary_lint.json")
            domain_summaries["lint"] = generate_lint_summary(raw_path, db_path)
            lint_out = raw_path / "summary_lint.json"
            with open(lint_out, 'w', encoding='utf-8') as f:
                json.dump(domain_summaries["lint"], f, indent=2)

        # Generate rules summary
        patterns_path = raw_path / "patterns.json"
        if not patterns_path.exists():
            patterns_path = raw_path / "findings.json"
        if patterns_path.exists():
            print("  [OK] Generating summary_rules.json")
            domain_summaries["rules"] = generate_rules_summary(raw_path, db_path)
            rules_out = raw_path / "summary_rules.json"
            with open(rules_out, 'w', encoding='utf-8') as f:
                json.dump(domain_summaries["rules"], f, indent=2)

        # Generate dependencies summary
        if (raw_path / "deps.json").exists() or (raw_path / "deps_latest.json").exists():
            print("  [OK] Generating summary_dependencies.json")
            domain_summaries["dependencies"] = generate_dependencies_summary(raw_path, db_path)
            deps_out = raw_path / "summary_dependencies.json"
            with open(deps_out, 'w', encoding='utf-8') as f:
                json.dump(domain_summaries["dependencies"], f, indent=2)

        # Generate FCE summary
        if (raw_path / "fce.json").exists():
            print("  [OK] Generating summary_fce.json")
            domain_summaries["fce"] = generate_fce_summary(raw_path, db_path)
            fce_out = raw_path / "summary_fce.json"
            with open(fce_out, 'w', encoding='utf-8') as f:
                json.dump(domain_summaries["fce"], f, indent=2)

        # Generate MASTER summary
        print("  [OK] Generating The_Auditor_Summary.json")
        master_summary = generate_master_summary(raw_path, db_path, domain_summaries)
        master_out = raw_path / "The_Auditor_Summary.json"
        with open(master_out, 'w', encoding='utf-8') as f:
            json.dump(master_summary, f, indent=2)

        elapsed = time.time() - start_time
        print(f"\n[OK] Per-domain summaries generated in {elapsed:.1f}s")
        print(f"  Domains: {len(domain_summaries)}")
        print(f"  Master summary: {master_out}")
        print(f"  Total findings: {master_summary['overview']['total_findings']}")
        print(f"  Critical: {master_summary['overview']['by_severity']['critical']}, "
              f"High: {master_summary['overview']['by_severity']['high']}, "
              f"Medium: {master_summary['overview']['by_severity']['medium']}")

        return master_summary

    else:
        # LEGACY FLOW: Generate audit_summary.json (backward compat)
        # ... [KEEP EXISTING CODE FROM LINES 20-259] ...
        # (All existing audit_summary.json generation logic stays unchanged)
        audit_summary = {
            "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "overall_status": "UNKNOWN",
            # ... rest of existing logic ...
        }
        # ... existing code continues unchanged ...
```

**NOTE**: The legacy flow (lines 20-259) stays EXACTLY as-is for backward compatibility. Only NEW flow added with flag.

---

## PHASE 2: Modify `theauditor/extraction.py`

### 2.1 Update `extract_all_to_readthis()` Function

**MODIFY lines 413-427** (file discovery and strategy building):

**REPLACE**:
```python
    # Discover ALL files in raw directory dynamically (courier model)
    raw_files = []
    for file_path in raw_dir.iterdir():
        if file_path.is_file():
            raw_files.append(file_path.name)

    print(f"[DISCOVERED] Found {len(raw_files)} files in raw directory")

    # Pure courier model - no smart extraction, just chunking if needed
    # Build extraction strategy dynamically
    extraction_strategy = []
    for filename in sorted(raw_files):
        # All files get same treatment: chunk if needed
        extraction_strategy.append((filename, 100, _copy_as_is))
```

**WITH**:
```python
    # Discover ALL files in raw directory dynamically (courier model)
    raw_files = []
    summary_files = []  # Track summary files separately

    for file_path in raw_dir.iterdir():
        if file_path.is_file():
            filename = file_path.name
            raw_files.append(filename)

            # Identify summary files (these WILL be chunked)
            if filename.startswith("summary_") or filename == "The_Auditor_Summary.json":
                summary_files.append(filename)

    print(f"[DISCOVERED] Found {len(raw_files)} files in raw directory")
    print(f"[SUMMARY FILES] {len(summary_files)} summary files will be chunked")
    print(f"[RAW FILES] {len(raw_files) - len(summary_files)} raw files will be copied as-is")

    # Build extraction strategy dynamically
    # NEW RULE: Only chunk summary files, copy raw files as-is
    extraction_strategy = []
    for filename in sorted(raw_files):
        if filename in summary_files:
            # Summary files: chunk if >65KB
            extraction_strategy.append((filename, 100, _copy_as_is))
        else:
            # Raw files: skip extraction entirely (leave in /raw/ only)
            # Users read summaries in /readthis/, query database for details
            extraction_strategy.append((filename, 0, None))  # 0 budget = skip
```

### 2.2 Update Extraction Loop to Skip Non-Summary Files

**MODIFY lines 437-464** (extraction loop):

**ADD CHECK** after line 443:
```python
        print(f"[PROCESSING] {filename}")

        # NEW: Skip non-summary files (extractor=None)
        if extractor is None:
            print(f"  [SKIPPED] {filename} - raw data file (not chunked, kept in /raw/ only)")
            skipped_files.append(filename)
            continue

        # Just chunk everything - ignore budget for chunking
        # ... rest of existing code ...
```

**RESULT**:
- Summary files (summary_*.json, The_Auditor_Summary.json) → chunked to /readthis/
- Raw files (taint_analysis.json, graph_analysis.json, etc.) → stay in /raw/ only, NOT copied to /readthis/

---

## PHASE 3: Integration with Pipeline

### 3.1 Modify Pipeline to Generate Domain Summaries

**File**: `theauditor/pipeline.py` (or wherever `aud full` is defined)

**ADD** after FCE stage (Stage 12):

```python
# Stage 13: Generate per-domain summaries
print("\n[Stage 13] Generating per-domain summaries...")
try:
    from theauditor.commands.summary import summary
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(summary, [
        '--root', root_path,
        '--raw-dir', str(raw_dir),
        '--generate-domain-summaries'  # Enable new flow
    ])

    if result.exit_code == 0:
        print("[OK] Per-domain summaries generated")
    else:
        print(f"[WARNING] Summary generation failed: {result.output}")
except Exception as e:
    print(f"[ERROR] Summary generation error: {e}")
```

**OR** if using subprocess:

```python
# Stage 13: Generate per-domain summaries
print("\n[Stage 13] Generating per-domain summaries...")
import subprocess
result = subprocess.run(
    ['aud', 'summary', '--root', root_path, '--generate-domain-summaries'],
    capture_output=True,
    text=True
)
if result.returncode == 0:
    print("[OK] Per-domain summaries generated")
else:
    print(f"[WARNING] Summary failed: {result.stderr}")
```

### 3.2 Ensure Extraction Runs After Summary

**VERIFY** extraction stage order:
1. Stage 12: FCE correlation
2. Stage 13: Generate summaries (NEW)
3. Stage 14: Extract to readthis (existing, now modified)

**Extraction must run AFTER summary generation** so summary files exist in /raw/ before chunking.

---

## PHASE 4: Testing & Verification

### 4.1 Unit Tests

**File**: `tests/test_summary_generation.py` (NEW)

```python
import json
from pathlib import Path
from theauditor.commands.summary import (
    generate_taint_summary,
    generate_graph_summary,
    generate_lint_summary,
    generate_master_summary
)

def test_taint_summary_generation(tmp_path):
    """Verify taint summary structure and size."""
    # Create mock taint_analysis.json
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    mock_taint = {
        "taint_paths": [
            {"severity": "critical", "source": {"file": "auth.py", "line": 10}, "sink": {"file": "db.py", "line": 20}}
        ],
        "total_vulnerabilities": 1,
        "sources_found": 1,
        "sinks_found": 1
    }

    with open(raw_dir / "taint_analysis.json", 'w') as f:
        json.dump(mock_taint, f)

    # Generate summary
    db_path = tmp_path / "repo_index.db"
    summary = generate_taint_summary(raw_dir, db_path)

    # Assertions
    assert summary["analyzer"] == "taint"
    assert "metrics" in summary
    assert "top_findings" in summary
    assert "query_alternative" in summary
    assert summary["metrics"]["total_taint_paths"] == 1

    # Size check (should be small)
    summary_json = json.dumps(summary)
    assert len(summary_json) < 100_000  # <100KB

def test_master_summary_combines_domains(tmp_path):
    """Verify master summary combines all domains."""
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "repo_index.db"

    domain_summaries = {
        "taint": {"top_findings": [], "metrics": {}},
        "lint": {"top_findings": [], "metrics": {}},
        "graph": {"top_findings": [], "metrics": {}}
    }

    master = generate_master_summary(raw_dir, db_path, domain_summaries)

    assert master["analyzer"] == "THE_AUDITOR_MASTER"
    assert "overview" in master
    assert "per_domain_metrics" in master
    assert "per_domain_summaries" in master
    assert len(master["per_domain_summaries"]) == 3
```

### 4.2 Integration Test

**File**: `tests/test_extraction_skip_raw.py` (NEW)

```python
def test_extraction_skips_raw_files(tmp_path):
    """Verify extraction skips raw files and only chunks summaries."""
    raw_dir = tmp_path / ".pf" / "raw"
    readthis_dir = tmp_path / ".pf" / "readthis"
    raw_dir.mkdir(parents=True)

    # Create mock files
    with open(raw_dir / "taint_analysis.json", 'w') as f:
        json.dump({"taint_paths": []}, f)

    with open(raw_dir / "summary_taint.json", 'w') as f:
        json.dump({"analyzer": "taint", "top_findings": []}, f)

    # Run extraction
    from theauditor.extraction import extract_all_to_readthis
    result = extract_all_to_readthis(str(tmp_path))

    # Assertions
    assert result == True

    # Raw file should NOT be in readthis
    assert not (readthis_dir / "taint_analysis.json").exists()
    assert not (readthis_dir / "taint_analysis_chunk01.json").exists()

    # Summary file SHOULD be in readthis
    assert (readthis_dir / "summary_taint.json").exists()
```

### 4.3 Manual Verification Steps

```bash
# 1. Run full pipeline
cd C:/Users/santa/Desktop/TheAuditor
.venv/Scripts/aud.exe full

# 2. Check /raw/ contains summaries
ls .pf/raw/summary_*.json
ls .pf/raw/The_Auditor_Summary.json

# 3. Check /readthis/ contains ONLY summaries (not raw files)
ls .pf/readthis/
# Should see: summary_taint_chunk01.json, summary_graph.json, The_Auditor_Summary.json
# Should NOT see: taint_analysis_chunk01.json, graph_analysis_chunk02.json

# 4. Verify summary size
C:/Users/santa/Desktop/TheAuditor/.venv/Scripts/python.exe -c "
import json
with open('.pf/raw/summary_taint.json') as f:
    data = json.load(f)
print(f\"Taint summary size: {len(json.dumps(data))} bytes\")
print(f\"Top findings count: {len(data['top_findings'])}\")
"

# 5. Verify master summary combines domains
C:/Users/santa/Desktop/TheAuditor/.venv/Scripts/python.exe -c "
import json
with open('.pf/raw/The_Auditor_Summary.json') as f:
    master = json.load(f)
print(f\"Domains: {list(master['per_domain_metrics'].keys())}\")
print(f\"Total findings: {master['overview']['total_findings']}\")
print(f\"Critical: {master['overview']['by_severity']['critical']}\")
"
```

---

## File Structure BEFORE vs AFTER

### BEFORE (Current):
```
.pf/
├── raw/ (18 files, NO summaries)
│   ├── taint_analysis.json (2.1 MB)
│   ├── graph_analysis.json (890 KB)
│   ├── lint.json (1.5 MB)
│   ├── patterns.json (780 KB)
│   ├── fce.json (3.2 MB)
│   ├── deps.json (120 KB)
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
    ├── fce_chunk03.json
    ├── lint_chunk01.json
    ├── lint_chunk02.json
    ├── lint_chunk03.json
    └── ... (24-27 total files) ❌ PROBLEM
```

### AFTER (Proposed):
```
.pf/
├── raw/ (25 files, includes summaries)
│   ├── taint_analysis.json (2.1 MB) [RAW DATA]
│   ├── graph_analysis.json (890 KB) [RAW DATA]
│   ├── lint.json (1.5 MB) [RAW DATA]
│   ├── patterns.json (780 KB) [RAW DATA]
│   ├── fce.json (3.2 MB) [RAW DATA]
│   ├── deps.json (120 KB) [RAW DATA]
│   ├── audit_summary.json (8 KB) [LEGACY]
│   ├── summary_taint.json (45 KB) ⭐ [SUMMARY]
│   ├── summary_graph.json (38 KB) ⭐ [SUMMARY]
│   ├── summary_lint.json (42 KB) ⭐ [SUMMARY]
│   ├── summary_rules.json (35 KB) ⭐ [SUMMARY]
│   ├── summary_dependencies.json (28 KB) ⭐ [SUMMARY]
│   ├── summary_fce.json (41 KB) ⭐ [SUMMARY]
│   └── The_Auditor_Summary.json (95 KB) ⭐⭐ [MASTER]
│
└── readthis/ (7-8 files, ONLY summaries)
    ├── summary_taint.json (45 KB, or chunked if >65KB)
    ├── summary_graph.json (38 KB)
    ├── summary_lint.json (42 KB)
    ├── summary_rules.json (35 KB)
    ├── summary_dependencies.json (28 KB)
    ├── summary_fce.json (41 KB)
    └── The_Auditor_Summary.json (95 KB, or chunked if >65KB)

    Total: 7-8 files ✅ FIXED
```

---

## Summary of Changes

### Files Modified:
1. **theauditor/commands/summary.py** - Add 7 new functions + modify main function
2. **theauditor/extraction.py** - Modify file discovery + skip non-summary files
3. **theauditor/pipeline.py** - Add Stage 13 (summary generation)

### Files Created:
1. **tests/test_summary_generation.py** - Unit tests for summary functions
2. **tests/test_extraction_skip_raw.py** - Integration test for extraction

### New Outputs:
1. `.pf/raw/summary_taint.json` - Taint domain summary
2. `.pf/raw/summary_graph.json` - Graph domain summary
3. `.pf/raw/summary_lint.json` - Lint domain summary
4. `.pf/raw/summary_rules.json` - Rules domain summary
5. `.pf/raw/summary_dependencies.json` - Dependencies domain summary
6. `.pf/raw/summary_fce.json` - FCE domain summary
7. `.pf/raw/The_Auditor_Summary.json` - Master summary (all domains)

### Backward Compatibility:
- `aud summary` without flag: generates legacy `audit_summary.json` (unchanged)
- `aud summary --generate-domain-summaries`: generates new per-domain summaries
- All existing raw files (taint_analysis.json, etc.) remain unchanged
- Extraction behavior: backward compatible (still chunks if no summaries exist)

---

## Effort Estimate

- **Phase 1** (summary.py modifications): 4-6 hours
- **Phase 2** (extraction.py modifications): 2-3 hours
- **Phase 3** (pipeline integration): 1-2 hours
- **Phase 4** (testing): 3-4 hours
- **Documentation**: 1-2 hours

**Total: 11-17 hours (1.5-2 days)**

---

## Success Criteria

✅ Per-domain summaries generated in `.pf/raw/`
✅ Master summary (`The_Auditor_Summary.json`) combines all domains
✅ `/readthis/` contains 7-8 files (not 24-27)
✅ Raw data files stay in `/raw/` only (not chunked to /readthis/)
✅ Each summary ≤50 KB and human-readable
✅ Each summary mentions `aud query` alternative
✅ Pipeline runs without errors
✅ Tests pass (unit + integration)
✅ Backward compatible with existing `aud summary` command
