"""Dead code detection rule - finds modules never imported."""

from theauditor.context.deadcode_graph import DEFAULT_EXCLUSIONS
from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="deadcode",
    category="quality",
    target_extensions=[".py", ".js", ".ts", ".tsx", ".jsx"],
    exclude_patterns=["node_modules/", ".venv/", "__pycache__/", "dist/", "build/"],
    execution_scope="database")


def find_dead_code(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect dead code using database queries."""
    findings = []

    if not context.db_path:
        return findings

    try:
        from pathlib import Path

        from theauditor.context.deadcode_graph import GraphDeadCodeDetector

        graphs_db = Path(context.db_path).parent / "graphs.db"

        if not graphs_db.exists():
            raise FileNotFoundError(
                f"graphs.db not found: {graphs_db}\nRun 'aud graph build' to create it."
            )

        detector = GraphDeadCodeDetector(str(graphs_db), context.db_path, debug=False)

        modules = detector.analyze(exclude_patterns=DEFAULT_EXCLUSIONS, analyze_symbols=False)

        for module in modules:
            findings.append(
                StandardFinding(
                    rule_name="deadcode",
                    message=f"Module never imported: {module.path}",
                    file_path=str(module.path),
                    line=1,
                    severity=Severity.INFO,
                    category="quality",
                    snippet="",
                    additional_info={
                        "type": "isolated_module",
                        "symbol_count": module.symbol_count,
                        "lines_estimated": module.lines_estimated,
                        "confidence": module.confidence,
                        "reason": module.reason,
                        "cluster_id": module.cluster_id,
                    },
                )
            )

    except Exception:
        raise

    return findings
