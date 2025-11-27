"""Dead code detection rule - finds modules never imported.

Integrated into 'aud full' pipeline via orchestrator.
Generates findings with severity='info' (quality concern, not security).

Pattern: Follows progress.md rules - analyze() function, execution_scope='database'.
"""

from theauditor.context.deadcode_graph import DEFAULT_EXCLUSIONS
from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

METADATA = RuleMetadata(
    name="deadcode",
    category="quality",
    target_extensions=[".py", ".js", ".ts", ".tsx", ".jsx"],
    exclude_patterns=["node_modules/", ".venv/", "__pycache__/", "dist/", "build/"],
    requires_jsx_pass=False,
    execution_scope="database",
)


def find_dead_code(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect dead code using database queries.

    Detection Strategy:
        1. Query symbols table for files with code definitions
        2. Query refs table for imported files
        3. Set difference identifies dead code
        4. Filter exclusions (__init__.py, tests, migrations)

    Database Tables Used:
        - symbols (read: path, name)
        - refs (read: value, kind)

    Known Limitations:
        - Does NOT detect dynamically imported modules (importlib.import_module)
        - Does NOT detect getattr() dynamic calls
        - Static analysis only

    Returns:
        List of findings with severity=INFO
    """
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
