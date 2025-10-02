"""Generate comprehensive audit summary from all analysis phases."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List
import click


@click.command()
@click.option("--root", default=".", help="Root directory")
@click.option("--raw-dir", default="./.pf/raw", help="Raw outputs directory")
@click.option("--out", default="./.pf/raw/audit_summary.json", help="Output path for summary")
def summary(root, raw_dir, out):
    """Generate comprehensive audit summary from all phases."""
    start_time = time.time()
    raw_path = Path(raw_dir)
    
    # Initialize summary structure
    audit_summary = {
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "overall_status": "UNKNOWN",
        "total_runtime_seconds": 0,
        "total_findings_by_severity": {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0
        },
        "metrics_by_phase": {},
        "key_statistics": {}
    }
    
    # Helper function to safely load JSON
    def load_json(file_path: Path) -> Dict[str, Any]:
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    # Phase 1: Index metrics
    manifest_path = Path(root) / "manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        if isinstance(manifest, list):
            audit_summary["metrics_by_phase"]["index"] = {
                "files_indexed": len(manifest),
                "total_size_bytes": sum(f.get("size", 0) for f in manifest)
            }
    
    # Phase 2: Framework detection (read from database, not output files)
    framework_list = _load_frameworks_from_db(Path(root))
    if framework_list:
        audit_summary["metrics_by_phase"]["detect_frameworks"] = {
            "frameworks_detected": len(framework_list),
            "languages": list(set(f.get("language", "") for f in framework_list))
        }
    
    # Phase 3: Dependencies
    deps = load_json(raw_path / "deps.json")
    deps_latest = load_json(raw_path / "deps_latest.json")
    if deps or deps_latest:
        outdated_count = 0
        vulnerability_count = 0
        total_deps = 0
        
        # Handle deps being either dict or list
        if isinstance(deps, dict):
            total_deps = len(deps.get("dependencies", []))
        elif isinstance(deps, list):
            total_deps = len(deps)
        
        # Handle deps_latest structure
        if isinstance(deps_latest, dict) and "packages" in deps_latest:
            for pkg in deps_latest["packages"]:
                if isinstance(pkg, dict):
                    if pkg.get("outdated"):
                        outdated_count += 1
                    if pkg.get("vulnerabilities"):
                        vulnerability_count += len(pkg["vulnerabilities"])
        
        audit_summary["metrics_by_phase"]["dependencies"] = {
            "total_dependencies": total_deps,
            "outdated_packages": outdated_count,
            "vulnerabilities": vulnerability_count
        }
    
    # Phase 7: Linting
    lint_data = load_json(raw_path / "lint.json")
    if lint_data and "findings" in lint_data:
        lint_by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in lint_data["findings"]:
            severity = finding.get("severity", "info").lower()
            if severity in lint_by_severity:
                lint_by_severity[severity] += 1
        
        audit_summary["metrics_by_phase"]["lint"] = {
            "total_issues": len(lint_data["findings"]),
            "by_severity": lint_by_severity
        }
        
        # Add to total
        for sev, count in lint_by_severity.items():
            audit_summary["total_findings_by_severity"][sev] += count
    
    # Phase 8: Pattern detection
    patterns = load_json(raw_path / "patterns.json")
    if not patterns:
        patterns = load_json(raw_path / "findings.json")
    
    if patterns and "findings" in patterns:
        pattern_by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in patterns["findings"]:
            severity = finding.get("severity", "info").lower()
            if severity in pattern_by_severity:
                pattern_by_severity[severity] += 1
        
        audit_summary["metrics_by_phase"]["patterns"] = {
            "total_patterns_matched": len(patterns["findings"]),
            "by_severity": pattern_by_severity
        }
        
        # Add to total
        for sev, count in pattern_by_severity.items():
            audit_summary["total_findings_by_severity"][sev] += count
    
    # Phase 9-10: Graph analysis
    graph_analysis = load_json(raw_path / "graph_analysis.json")
    graph_metrics = load_json(raw_path / "graph_metrics.json")
    if graph_analysis:
        summary_data = graph_analysis.get("summary", {})
        audit_summary["metrics_by_phase"]["graph"] = {
            "import_nodes": summary_data.get("import_graph", {}).get("nodes", 0),
            "import_edges": summary_data.get("import_graph", {}).get("edges", 0),
            "cycles_detected": len(graph_analysis.get("cycles", [])),
            "hotspots_identified": len(graph_analysis.get("hotspots", [])),
            "graph_density": summary_data.get("import_graph", {}).get("density", 0)
        }
        
        if "health_metrics" in summary_data:
            audit_summary["metrics_by_phase"]["graph"]["health_grade"] = summary_data["health_metrics"].get("health_grade", "N/A")
            audit_summary["metrics_by_phase"]["graph"]["fragility_score"] = summary_data["health_metrics"].get("fragility_score", 0)
    
    # Phase 11: Taint analysis
    taint = load_json(raw_path / "taint_analysis.json")
    if taint:
        taint_by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        if "taint_paths" in taint:
            for path in taint["taint_paths"]:
                severity = path.get("severity", "medium").lower()
                if severity in taint_by_severity:
                    taint_by_severity[severity] += 1
        
        audit_summary["metrics_by_phase"]["taint_analysis"] = {
            "taint_paths_found": len(taint.get("taint_paths", [])),
            "total_vulnerabilities": taint.get("total_vulnerabilities", 0),
            "by_severity": taint_by_severity
        }
        
        # Add to total
        for sev, count in taint_by_severity.items():
            if sev in audit_summary["total_findings_by_severity"]:
                audit_summary["total_findings_by_severity"][sev] += count
    
    # Phase 12: FCE (Factual Correlation Engine)
    fce = load_json(raw_path / "fce.json")
    if fce:
        correlations = fce.get("correlations", {})
        audit_summary["metrics_by_phase"]["fce"] = {
            "total_findings": len(fce.get("all_findings", [])),
            "test_failures": len(fce.get("test_results", {}).get("failures", [])),
            "hotspots_correlated": correlations.get("total_hotspots", 0),
            "factual_clusters": len(correlations.get("factual_clusters", []))
        }
    
    # Calculate overall status based on severity counts
    severity_counts = audit_summary["total_findings_by_severity"]
    if severity_counts["critical"] > 0:
        audit_summary["overall_status"] = "CRITICAL"
    elif severity_counts["high"] > 0:
        audit_summary["overall_status"] = "HIGH"
    elif severity_counts["medium"] > 0:
        audit_summary["overall_status"] = "MEDIUM"
    elif severity_counts["low"] > 0:
        audit_summary["overall_status"] = "LOW"
    else:
        audit_summary["overall_status"] = "CLEAN"
    
    # Add key statistics
    audit_summary["key_statistics"] = {
        "total_findings": sum(severity_counts.values()),
        "phases_with_findings": len([p for p in audit_summary["metrics_by_phase"] if audit_summary["metrics_by_phase"][p]]),
        "total_phases_run": len(audit_summary["metrics_by_phase"])
    }
    
    # Calculate runtime
    elapsed = time.time() - start_time
    audit_summary["summary_generation_time"] = elapsed
    
    # Read pipeline.log for total runtime if available
    pipeline_log = Path(root) / ".pf" / "pipeline.log"
    if pipeline_log.exists():
        try:
            with open(pipeline_log, 'r') as f:
                for line in f:
                    if "[TIME] Total time:" in line:
                        # Extract seconds from line like "[TIME] Total time: 73.0s"
                        parts = line.split(":")[-1].strip().replace("s", "").split("(")[0]
                        audit_summary["total_runtime_seconds"] = float(parts)
                        break
        except:
            pass
    
    # Save the summary
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(audit_summary, f, indent=2)
    
    # Output results
    click.echo(f"[OK] Audit summary generated in {elapsed:.1f}s")
    click.echo(f"  Overall status: {audit_summary['overall_status']}")
    click.echo(f"  Total findings: {audit_summary['key_statistics']['total_findings']}")
    click.echo(f"  Critical: {severity_counts['critical']}, High: {severity_counts['high']}, Medium: {severity_counts['medium']}, Low: {severity_counts['low']}")


def _load_frameworks_from_db(project_path: Path) -> List[Dict]:
    """Load frameworks from database (not output files).

    Args:
        project_path: Project root directory

    Returns:
        List of framework dictionaries or empty list
    """
    db_path = project_path / ".pf" / "repo_index.db"
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name, version, language, path
            FROM frameworks
            ORDER BY is_primary DESC, name
        """)

        frameworks = []
        for name, version, language, path in cursor.fetchall():
            frameworks.append({
                "framework": name,
                "version": version,
                "language": language,
                "path": path
            })

        conn.close()
        return frameworks

    except sqlite3.Error:
        return []
    click.echo(f"  Summary saved to: {out_path}")
    
    return audit_summary