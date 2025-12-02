"""Generate comprehensive audit summary from all analysis phases."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import click

from theauditor.pipeline.ui import console


def _get_findings_by_tools(db_path: Path, tools: tuple[str, ...]) -> dict[str, dict[str, int]]:
    """Query findings_consolidated for counts grouped by tool and severity.

    ZERO FALLBACK: No try/except. If DB query fails, crash is correct.
    This exposes bugs instead of hiding them with stale JSON data.

    Args:
        db_path: Path to repo_index.db
        tools: Tuple of tool names to query

    Returns:
        Dict of {tool: {severity: count}}
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    placeholders = ",".join("?" * len(tools))
    cursor.execute(
        f"""
        SELECT tool, severity, COUNT(*)
        FROM findings_consolidated
        WHERE tool IN ({placeholders})
        GROUP BY tool, severity
    """,
        tools,
    )

    results: dict[str, dict[str, int]] = {}
    for tool, severity, count in cursor.fetchall():
        if tool not in results:
            results[tool] = {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0,
                "error": 0,
                "warning": 0,
            }
        if severity in results[tool]:
            results[tool][severity] = count

    conn.close()
    return results


@click.command()
@click.option("--root", default=".", help="Root directory")
@click.option("--raw-dir", default="./.pf/raw", help="Raw outputs directory")
@click.option("--out", default="./.pf/raw/audit_summary.json", help="Output path for summary")
def summary(root, raw_dir, out):
    """Aggregate statistics from all analysis phases into machine-readable executive summary JSON.

    Post-audit reporting command that consolidates findings from all completed analysis phases
    into a single JSON summary with severity breakdowns, phase completion status, and overall
    audit health metrics. Designed for CI/CD integration and programmatic consumption (not human
    reading - use 'aud report' for AI-optimized markdown).

    AI ASSISTANT CONTEXT:
      Purpose: Aggregate audit statistics for CI/CD and metrics tracking
      Input: .pf/raw/*.json (all analysis phase outputs)
      Output: .pf/raw/audit_summary.json (consolidated statistics)
      Prerequisites: aud full (or multiple analysis commands)
      Integration: CI/CD pass/fail gates, monitoring dashboards, metrics
      Performance: ~1-2 seconds (JSON aggregation, no analysis)

    WHAT IT AGGREGATES:
      Severity Counts:
        - CRITICAL findings count
        - HIGH findings count
        - MEDIUM/LOW findings count
        - Total findings across all phases

      Phase Completion:
        - Which analysis phases ran successfully
        - Phases that failed or skipped
        - Execution time per phase

      Audit Health Metrics:
        - Files analyzed count
        - Overall status (PASS/FAIL/WARNING)
        - Code coverage percentage (if available)
        - Dead code percentage

    OUTPUT FORMAT (audit_summary.json):
      {
        "overall_status": "FAIL",
        "total_findings": 45,
        "severity_breakdown": {
          "critical": 3,
          "high": 12,
          "medium": 20,
          "low": 10
        },
        "phases_completed": {
          "index": true,
          "taint": true,
          "deadcode": true,
          "fce": false
        },
        "metrics": {
          "files_analyzed": 120,
          "execution_time_seconds": 45.2
        }
      }

    EXAMPLES:
      aud full && aud summary
      aud summary --out ./build/audit_results.json
      aud summary && jq '.severity_breakdown.critical' .pf/raw/audit_summary.json

    PERFORMANCE: ~1-2 seconds (JSON aggregation only)

    EXIT CODES:
      0 = Success
      1 = No analysis output found (run 'aud full' first)

    RELATED COMMANDS:
      aud full    # Runs all analysis phases
      aud report  # AI-optimized markdown report

    NOTE: This is for machine consumption (CI/CD). For human-readable reports
    optimized for LLM context windows, use 'aud report' instead.

    OUTPUT:
      .pf/raw/audit_summary.json       # Executive summary

    STATUS LEVELS:
    - CRITICAL: Has critical findings
    - HIGH: Has high findings (no critical)
    - MEDIUM: Has medium findings (no high/critical)
    - LOW: Only low findings
    - CLEAN: No findings

    RELATED:
      aud full      # Run all analysis first
      aud report    # Generate AI chunks
    """
    start_time = time.time()
    raw_path = Path(raw_dir)

    audit_summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "UNKNOWN",
        "total_runtime_seconds": 0,
        "total_findings_by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        "metrics_by_phase": {},
        "key_statistics": {},
    }

    def load_json(file_path: Path) -> dict[str, Any]:
        if file_path.exists():
            try:
                with open(file_path, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    manifest_path = Path(root) / "manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        if isinstance(manifest, list):
            audit_summary["metrics_by_phase"]["index"] = {
                "files_indexed": len(manifest),
                "total_size_bytes": sum(f.get("size", 0) for f in manifest),
            }

    framework_list = _load_frameworks_from_db(Path(root))
    if framework_list:
        audit_summary["metrics_by_phase"]["detect_frameworks"] = {
            "frameworks_detected": len(framework_list),
            "languages": list({f.get("language", "") for f in framework_list}),
        }

    deps = load_json(raw_path / "deps.json")
    deps_latest = load_json(raw_path / "deps_latest.json")
    if deps or deps_latest:
        outdated_count = 0
        vulnerability_count = 0
        total_deps = 0

        if isinstance(deps, dict):
            total_deps = len(deps.get("dependencies", []))
        elif isinstance(deps, list):
            total_deps = len(deps)

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
            "vulnerabilities": vulnerability_count,
        }

    db_path = Path(root) / ".pf" / "repo_index.db"

    lint_tools = ("ruff", "mypy", "eslint")
    lint_findings = _get_findings_by_tools(db_path, lint_tools)
    lint_by_severity = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
        "error": 0,
        "warning": 0,
    }
    total_lint_issues = 0
    for tool_counts in lint_findings.values():
        for sev, count in tool_counts.items():
            if sev in lint_by_severity:
                lint_by_severity[sev] += count
                total_lint_issues += count

    if total_lint_issues > 0:
        audit_summary["metrics_by_phase"]["lint"] = {
            "total_issues": total_lint_issues,
            "by_severity": lint_by_severity,
        }

        for sev in ("critical", "high", "medium", "low", "info"):
            audit_summary["total_findings_by_severity"][sev] += lint_by_severity.get(sev, 0)

    pattern_findings = _get_findings_by_tools(db_path, ("patterns",))
    pattern_by_severity = pattern_findings.get(
        "patterns", {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    )
    total_patterns = sum(pattern_by_severity.values())

    if total_patterns > 0:
        audit_summary["metrics_by_phase"]["patterns"] = {
            "total_patterns_matched": total_patterns,
            "by_severity": pattern_by_severity,
        }

        for sev in ("critical", "high", "medium", "low", "info"):
            audit_summary["total_findings_by_severity"][sev] += pattern_by_severity.get(sev, 0)

    graph_analysis = load_json(raw_path / "graph_analysis.json")
    if graph_analysis:
        summary_data = graph_analysis.get("summary", {})
        audit_summary["metrics_by_phase"]["graph"] = {
            "import_nodes": summary_data.get("import_graph", {}).get("nodes", 0),
            "import_edges": summary_data.get("import_graph", {}).get("edges", 0),
            "cycles_detected": len(graph_analysis.get("cycles", [])),
            "hotspots_identified": len(graph_analysis.get("hotspots", [])),
            "graph_density": summary_data.get("import_graph", {}).get("density", 0),
        }

        if "health_metrics" in summary_data:
            audit_summary["metrics_by_phase"]["graph"]["health_grade"] = summary_data[
                "health_metrics"
            ].get("health_grade", "N/A")
            audit_summary["metrics_by_phase"]["graph"]["fragility_score"] = summary_data[
                "health_metrics"
            ].get("fragility_score", 0)

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
            "by_severity": taint_by_severity,
        }

        for sev, count in taint_by_severity.items():
            if sev in audit_summary["total_findings_by_severity"]:
                audit_summary["total_findings_by_severity"][sev] += count

    terraform_findings = _get_findings_by_tools(db_path, ("terraform",))
    terraform_by_severity = terraform_findings.get(
        "terraform", {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    )
    total_terraform = sum(terraform_by_severity.values())

    if total_terraform > 0:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, COUNT(*) FROM findings_consolidated
            WHERE tool = 'terraform' GROUP BY category
        """)
        terraform_by_category = dict(cursor.fetchall())

        cursor.execute("""
            SELECT COUNT(DISTINCT tf_resource_id) FROM findings_consolidated
            WHERE tool = 'terraform' AND tf_resource_id IS NOT NULL AND tf_resource_id != ''
        """)
        resources_analyzed = cursor.fetchone()[0] or 0
        conn.close()

        audit_summary["metrics_by_phase"]["terraform"] = {
            "total_findings": total_terraform,
            "by_severity": terraform_by_severity,
            "by_category": terraform_by_category,
            "resources_analyzed": resources_analyzed,
        }

        for sev, count in terraform_by_severity.items():
            if sev in audit_summary["total_findings_by_severity"]:
                audit_summary["total_findings_by_severity"][sev] += count

    fce = load_json(raw_path / "fce.json")
    if fce:
        correlations = fce.get("correlations", {})
        summary_block = fce.get("summary", {})
        audit_summary["metrics_by_phase"]["fce"] = {
            "raw_findings": summary_block.get("raw_findings", len(fce.get("all_findings", []))),
            "test_failures": summary_block.get(
                "test_failures", len(fce.get("test_results", {}).get("failures", []))
            ),
            "meta_findings": summary_block.get(
                "meta_findings", len(correlations.get("meta_findings", []))
            ),
            "factual_clusters": summary_block.get(
                "factual_clusters", len(correlations.get("factual_clusters", []))
            ),
            "path_clusters": summary_block.get(
                "path_clusters", correlations.get("total_path_clusters", 0)
            ),
            "hotspots_correlated": correlations.get("total_hotspots", 0),
        }

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

    audit_summary["key_statistics"] = {
        "total_findings": sum(severity_counts.values()),
        "phases_with_findings": len(
            [p for p in audit_summary["metrics_by_phase"] if audit_summary["metrics_by_phase"][p]]
        ),
        "total_phases_run": len(audit_summary["metrics_by_phase"]),
    }

    elapsed = time.time() - start_time
    audit_summary["summary_generation_time"] = elapsed

    pipeline_log = Path(root) / ".pf" / "pipeline.log"
    if pipeline_log.exists():
        try:
            with open(pipeline_log) as f:
                for line in f:
                    if "[TIME] Total time:" in line:
                        parts = line.split(":")[-1].strip().replace("s", "").split("(")[0]
                        audit_summary["total_runtime_seconds"] = float(parts)
                        break
        except Exception:
            pass

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, indent=2)

    console.print(f"[success]Audit summary generated in {elapsed:.1f}s[/success]")
    console.print(f"  Overall status: {audit_summary['overall_status']}", highlight=False)
    console.print(
        f"  Total findings: {audit_summary['key_statistics']['total_findings']}", highlight=False
    )
    console.print(
        f"  Critical: {severity_counts['critical']}, High: {severity_counts['high']}, Medium: {severity_counts['medium']}, Low: {severity_counts['low']}",
        highlight=False,
    )


def _load_frameworks_from_db(project_path: Path) -> list[dict]:
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
            frameworks.append(
                {"framework": name, "version": version, "language": language, "path": path}
            )

        conn.close()
        return frameworks

    except sqlite3.Error:
        return []
