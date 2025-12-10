"""FCE Engine - Main entry point for running vector-based convergence analysis.

Provides run_fce() function that wraps FCEQueryEngine.
Text rendering is done by the command using Rich.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from theauditor.fce.formatter import FCEFormatter
from theauditor.fce.query import FCEQueryEngine


def run_fce(
    root_path: str = ".",
    min_vectors: int = 2,
) -> dict[str, Any]:
    """Run FCE vector-based convergence analysis.

    Args:
        root_path: Project root directory
        min_vectors: Minimum vectors required for convergence (1-4, default 2)

    Returns:
        Dict with:
            - success: bool
            - convergence_points: list[ConvergencePoint] (Pydantic models)
            - summary: dict (summary stats)
            - error: str (if success=False)
    """
    root = Path(root_path).resolve()

    try:
        engine = FCEQueryEngine(root)
    except FileNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "summary": {},
            "convergence_points": [],
        }

    try:
        points = engine.get_convergence_points(min_vectors=min_vectors)
        summary = engine.get_summary()

        return {
            "success": True,
            "convergence_points": points,
            "summary": summary,
            "error": None,
        }

    finally:
        engine.close()


def get_fce_json(
    root_path: str = ".",
    min_vectors: int = 2,
) -> str:
    """Run FCE and return JSON string.

    Args:
        root_path: Project root directory
        min_vectors: Minimum vectors required

    Returns:
        JSON string with full FCE report
    """
    root = Path(root_path).resolve()
    result = run_fce(root_path=root_path, min_vectors=min_vectors)

    if not result["success"]:
        return json.dumps({"error": result["error"]}, indent=2)

    formatter = FCEFormatter()
    points = result["convergence_points"]
    summary = result["summary"]

    output_data = {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "min_vectors_filter": min_vectors,
            "root_path": str(root),
        },
        "summary": summary,
        "convergence_points": [formatter.point_to_dict(p) for p in points],
    }

    return formatter.format_json(output_data)
