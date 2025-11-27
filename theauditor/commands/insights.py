"""Run optional insights analysis on existing audit data.

This command runs interpretive analysis modules (ML, graph health, taint severity)
on top of existing raw audit data, generating insights and predictions.
"""

import json
import sys
from pathlib import Path
from typing import Any

import click


SECURITY_SINKS = {
    "sql": ["execute", "query", "raw", "literal"],
    "command": ["exec", "system", "spawn", "popen"],
    "xss": ["innerHTML", "outerHTML", "write", "writeln", "dangerouslySetInnerHTML"],
    "path": ["open", "readFile", "writeFile", "unlink"],
    "ldap": ["search", "bind"],
    "nosql": ["find", "aggregate", "mapReduce"],
}


@click.command()
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["ml", "graph", "taint", "impact", "all"]),
    default="all",
    help="Which insights modules to run",
)
@click.option("--ml-train", is_flag=True, help="Train ML models before generating suggestions")
@click.option("--topk", default=10, type=int, help="Top K files for ML suggestions")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="./.pf/insights",
    help="Directory for insights output",
)
@click.option("--print-summary", is_flag=True, help="Print summary to console")
def insights(mode: str, ml_train: bool, topk: int, output_dir: str, print_summary: bool) -> None:
    """Add interpretive scoring and predictions to raw audit facts.

    The Insights system is TheAuditor's optional interpretation layer that
    sits ON TOP of factual data. While core modules report facts ("XSS found
    at line 42"), insights add interpretation ("This is CRITICAL severity").

    CRITICAL UNDERSTANDING - Two-Layer Architecture:
      1. Truth Couriers (Core): Report facts without judgment
         - "Data flows from req.body to res.send"
         - "Function complexity is 47"
         - "17 circular dependencies detected"

      2. Insights (Optional): Add scoring and interpretation
         - "This is HIGH severity XSS"
         - "Health score: 35/100 - Needs refactoring"
         - "Risk prediction: 87% chance of vulnerabilities"

    Available Insights Modules:

      ML (Machine Learning) - Requires pip install -e ".[ml]"
        - Trains on historical patterns in your codebase
        - Predicts which files likely contain vulnerabilities
        - Identifies root cause patterns
        - Suggests prioritized review order

      Graph (Architecture Health)
        - Calculates health score (0-100) with letter grades
        - Identifies architectural anti-patterns
        - Ranks hotspots by connectivity and churn
        - Generates refactoring recommendations

      Taint (Security Severity)
        - Adds CVSS-like severity scores to taint paths
        - Classifies vulnerability types (XSS, SQLi, etc.)
        - Calculates risk scores based on exploitability
        - Prioritizes critical security issues

      Impact (Blast Radius)
        - Analyzes change propagation patterns
        - Calculates affected file counts
        - Identifies high-risk modification points
        - Maps dependency chains

    How It Works:
      1. Reads raw facts from .pf/raw/ (immutable truth)
      2. Applies scoring algorithms and ML models
      3. Outputs insights to .pf/insights/ (interpretations)
      4. Raw facts remain unchanged - insights are additive

    Examples:
      # Run all insights with summary
      aud insights --print-summary

      # ML predictions only (top 20 risky files)
      aud insights --mode ml --topk 20

      # Train ML model first, then predict
      aud insights --mode ml --ml-train

      # Graph health with custom output
      aud insights --mode graph --output-dir ./reports/insights

      # Taint severity scoring only
      aud insights --mode taint --print-summary

    Output Files:
      .pf/insights/
        ├── unified_insights.json    # Aggregated summary
        ├── ml_suggestions.json      # ML predictions
        ├── graph_health.json        # Architecture metrics
        ├── taint_severity.json      # Security scoring
        └── impact_analysis.json     # Change impact

    Severity Levels (Taint Module):
      CRITICAL - Exploitable with high impact
      HIGH     - Exploitable with moderate impact
      MEDIUM   - Requires specific conditions
      LOW      - Minimal security impact
      INFO     - Informational only

    Health Grades (Graph Module):
      A (90-100) - Excellent architecture
      B (80-89)  - Good, minor issues
      C (70-79)  - Acceptable, needs work
      D (60-69)  - Poor, significant issues
      F (0-59)   - Critical problems

    ML Risk Scores:
      0.8-1.0 - Very high risk, review immediately
      0.6-0.8 - High risk, review soon
      0.4-0.6 - Medium risk, schedule review
      0.2-0.4 - Low risk, review if time permits
      0.0-0.2 - Very low risk

    Prerequisites:
      - Run 'aud full' first to generate raw data
      - For ML: pip install -e ".[ml]" (scikit-learn, numpy)
      - For Graph: pip install -e ".[all]" (networkx)

    Philosophy Note:
      Insights are INTERPRETATIONS, not facts. Different organizations
      may have different risk tolerances. Use insights as guidance but
      always review the raw facts in .pf/raw/ for ground truth.

    Exit Codes:
      0 - All requested insights generated successfully
      1 - One or more insights failed (see errors)"""

    pf_dir = Path(".pf")
    raw_dir = pf_dir / "raw"

    if not raw_dir.exists():
        click.echo("[ERROR] No raw audit data found. Run 'aud full' first.", err=True)
        sys.exit(1)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    click.echo(f"\n{'=' * 60}")
    click.echo(f"INSIGHTS ANALYSIS - {mode.upper()} Mode")
    click.echo(f"{'=' * 60}")
    click.echo(f"Output directory: {output_path}")

    results = {}
    errors = []

    if mode in ["ml", "all"]:
        click.echo("\n[ML] Running machine learning insights...")
        ml_result = run_ml_insights(ml_train, topk, output_path)
        results["ml"] = ml_result
        if ml_result.get("error"):
            errors.append(f"ML: {ml_result['error']}")
        else:
            click.echo(f"  ✓ ML predictions saved to {output_path}/ml_suggestions.json")

    if mode in ["graph", "all"]:
        click.echo("\n[GRAPH] Running graph health analysis...")
        graph_result = run_graph_insights(output_path)
        results["graph"] = graph_result
        if graph_result.get("error"):
            errors.append(f"Graph: {graph_result['error']}")
        else:
            click.echo(f"  ✓ Graph health saved to {output_path}/graph_health.json")

    if mode in ["taint", "all"]:
        click.echo("\n[TAINT] Running taint severity scoring...")
        taint_result = run_taint_insights(output_path)
        results["taint"] = taint_result
        if taint_result.get("error"):
            errors.append(f"Taint: {taint_result['error']}")
        else:
            click.echo(f"  ✓ Taint severity saved to {output_path}/taint_severity.json")

    if mode in ["impact", "all"]:
        click.echo("\n[IMPACT] Running impact analysis...")
        impact_result = run_impact_insights(output_path)
        results["impact"] = impact_result
        if impact_result.get("error"):
            errors.append(f"Impact: {impact_result['error']}")
        else:
            click.echo(f"  ✓ Impact analysis saved to {output_path}/impact_analysis.json")

    click.echo("\n[AGGREGATE] Creating unified insights summary...")
    summary = aggregate_insights(results, output_path)

    summary_path = output_path / "unified_insights.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    click.echo(f"  ✓ Unified summary saved to {summary_path}")

    if print_summary:
        print_insights_summary(summary)

    click.echo(f"\n{'=' * 60}")
    if errors:
        click.echo(f"[WARN] Insights completed with {len(errors)} errors:", err=True)
        for error in errors:
            click.echo(f"  • {error}", err=True)
    else:
        click.echo("[OK] All insights generated successfully")

    click.echo(f"\n[TIP] Insights are interpretive and optional.")
    click.echo(f"      Raw facts remain in .pf/raw/ unchanged.")

    sys.exit(1 if errors else 0)


def run_ml_insights(train: bool, topk: int, output_dir: Path) -> dict[str, Any]:
    """Run ML insights generation."""
    try:
        from theauditor.ml import check_ml_available, learn, suggest

        if not check_ml_available():
            return {"error": "ML module not installed. Run: pip install -e .[ml]"}

        if train:
            learn_result = learn(
                db_path="./.pf/repo_index.db",
                manifest_path="./.pf/manifest.json",
                print_stats=False,
            )
            if not learn_result.get("success"):
                return {"error": f"ML training failed: {learn_result.get('error')}"}

        suggest_result = suggest(
            db_path="./.pf/repo_index.db",
            manifest_path="./.pf/manifest.json",
            workset_path="./.pf/workset.json",
            topk=topk,
            out_path=str(output_dir / "ml_suggestions.json"),
        )

        return suggest_result

    except ImportError:
        return {"error": "ML module not available"}
    except Exception as e:
        return {"error": str(e)}


def run_graph_insights(output_dir: Path) -> dict[str, Any]:
    """Run graph health insights."""
    try:
        from theauditor.graph.insights import GraphInsights
        from theauditor.graph.analyzer import XGraphAnalyzer
        from theauditor.graph.store import XGraphStore

        store = XGraphStore(db_path="./.pf/graphs.db")
        import_graph = store.load_import_graph()

        if not import_graph or not import_graph.get("nodes"):
            return {"error": "No import graph found. Run 'aud graph build' first."}

        analysis_path = Path(".pf/raw/graph_analysis.json")
        analysis_data = {}
        if analysis_path.exists():
            with open(analysis_path) as f:
                analysis_data = json.load(f)

        insights = GraphInsights()
        analyzer = XGraphAnalyzer()

        if "cycles" in analysis_data:
            cycles = analysis_data["cycles"]
        else:
            cycles = analyzer.detect_cycles(import_graph)

        if "hotspots" in analysis_data:
            hotspots = analysis_data["hotspots"]
        else:
            hotspots = insights.rank_hotspots(import_graph)

        health = insights.calculate_health_metrics(import_graph, cycles=cycles, hotspots=hotspots)

        recommendations = insights.generate_recommendations(
            import_graph, cycles=cycles, hotspots=hotspots
        )

        output = {
            "health_metrics": health,
            "top_hotspots": hotspots[:10],
            "recommendations": recommendations,
            "cycles_found": len(cycles),
            "total_nodes": len(import_graph.get("nodes", [])),
            "total_edges": len(import_graph.get("edges", [])),
        }

        output_path = output_dir / "graph_health.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        return {"success": True, "health_score": health.get("health_score")}

    except ImportError:
        return {"error": "Graph insights module not available"}
    except Exception as e:
        return {"error": str(e)}


def run_taint_insights(output_dir: Path) -> dict[str, Any]:
    """Run taint severity insights."""
    try:
        from datetime import datetime, UTC
        from theauditor.insights.taint import (
            calculate_severity,
            classify_vulnerability,
            generate_summary,
        )

        taint_path = Path(".pf/raw/taint_analysis.json")
        if not taint_path.exists():
            return {"error": "No taint data found. Run 'aud taint-analyze' first."}

        with open(taint_path) as f:
            taint_data = json.load(f)

        if not taint_data.get("success"):
            return {"error": "Taint analysis was not successful"}

        severity_analysis = []
        enriched_paths = []
        for path in taint_data.get("taint_paths", []):
            severity = calculate_severity(path)
            vuln_type = classify_vulnerability(path.get("sink", {}), SECURITY_SINKS)

            severity_analysis.append(
                {
                    "file": path.get("sink", {}).get("file"),
                    "line": path.get("sink", {}).get("line"),
                    "severity": severity,
                    "vulnerability_type": vuln_type,
                    "path_length": len(path.get("path", [])),
                    "risk_score": 1.0
                    if severity == "critical"
                    else 0.7
                    if severity == "high"
                    else 0.4,
                }
            )

            enriched_path = dict(path)
            enriched_path["severity"] = severity
            enriched_path["vulnerability_type"] = vuln_type
            enriched_paths.append(enriched_path)

        summary = generate_summary(enriched_paths)

        output = {
            "generated_at": datetime.now(UTC).isoformat(),
            "severity_analysis": severity_analysis,
            "summary": summary,
            "total_vulnerabilities": len(severity_analysis),
            "sources_analyzed": taint_data.get("sources_found", 0),
            "sinks_analyzed": taint_data.get("sinks_found", 0),
        }

        output_path = output_dir / "taint_severity.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        return {"success": True, "risk_level": summary.get("risk_level")}

    except ImportError:
        return {"error": "Taint insights module not available"}
    except Exception as e:
        return {"error": str(e)}


def run_impact_insights(output_dir: Path) -> dict[str, Any]:
    """Run impact analysis insights."""
    try:
        workset_path = Path(".pf/workset.json")
        if not workset_path.exists():
            return {"error": "No workset found. Run 'aud workset' first."}

        with open(workset_path) as f:
            workset_data = json.load(f)

        output = {
            "files_changed": len(workset_data.get("files", [])),
            "potential_impact": "Analysis pending",
            "recommendation": "Run 'aud impact --file <file> --line <line>' for detailed analysis",
        }

        output_path = output_dir / "impact_analysis.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        return {"success": True, "files_analyzed": len(workset_data.get("files", []))}

    except Exception as e:
        return {"error": str(e)}


def aggregate_insights(results: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Aggregate all insights into unified summary."""
    summary = {
        "insights_generated": list(results.keys()),
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "output_directory": str(output_dir),
    }

    if "ml" in results and results["ml"].get("success"):
        summary["ml"] = {
            "status": "success",
            "workset_size": results["ml"].get("workset_size", 0),
            "predictions_generated": True,
        }
    elif "ml" in results:
        summary["ml"] = {"status": "error", "error": results["ml"].get("error")}

    if "graph" in results and results["graph"].get("success"):
        summary["graph"] = {
            "status": "success",
            "health_score": results["graph"].get("health_score", 0),
        }
    elif "graph" in results:
        summary["graph"] = {"status": "error", "error": results["graph"].get("error")}

    if "taint" in results and results["taint"].get("success"):
        summary["taint"] = {
            "status": "success",
            "risk_level": results["taint"].get("risk_level", "unknown"),
        }
    elif "taint" in results:
        summary["taint"] = {"status": "error", "error": results["taint"].get("error")}

    if "impact" in results and results["impact"].get("success"):
        summary["impact"] = {
            "status": "success",
            "files_analyzed": results["impact"].get("files_analyzed", 0),
        }
    elif "impact" in results:
        summary["impact"] = {"status": "error", "error": results["impact"].get("error")}

    return summary


def print_insights_summary(summary: dict[str, Any]) -> None:
    """Print insights summary to console."""
    click.echo(f"\n{'=' * 60}")
    click.echo("INSIGHTS SUMMARY")
    click.echo(f"{'=' * 60}")

    if "ml" in summary:
        if summary["ml"]["status"] == "success":
            click.echo(f"\n[ML] Machine Learning Insights:")
            click.echo(f"  • Workset size: {summary['ml'].get('workset_size', 0)} files")
            click.echo(f"  • Predictions: Generated successfully")
        else:
            click.echo(f"\n[ML] Machine Learning Insights: {summary['ml'].get('error')}")

    if "graph" in summary:
        if summary["graph"]["status"] == "success":
            health = summary["graph"].get("health_score", 0)
            grade = (
                "A"
                if health >= 90
                else "B"
                if health >= 80
                else "C"
                if health >= 70
                else "D"
                if health >= 60
                else "F"
            )
            click.echo(f"\n[GRAPH] Architecture Health:")
            click.echo(f"  • Health score: {health}/100 (Grade: {grade})")
        else:
            click.echo(f"\n[GRAPH] Architecture Health: {summary['graph'].get('error')}")

    if "taint" in summary:
        if summary["taint"]["status"] == "success":
            risk = summary["taint"].get("risk_level", "unknown")
            click.echo(f"\n[TAINT] Security Risk:")
            click.echo(f"  • Risk level: {risk.upper()}")
        else:
            click.echo(f"\n[TAINT] Security Risk: {summary['taint'].get('error')}")

    if "impact" in summary:
        if summary["impact"]["status"] == "success":
            click.echo(f"\n[IMPACT] Change Impact:")
            click.echo(f"  • Files analyzed: {summary['impact'].get('files_analyzed', 0)}")
        else:
            click.echo(f"\n[IMPACT] Change Impact: {summary['impact'].get('error')}")

    click.echo(f"\n{'=' * 60}")


insights_command = insights
