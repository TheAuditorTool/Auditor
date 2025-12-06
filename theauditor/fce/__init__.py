"""FCE - Factual Correlation Engine with Vector-Based Consensus.

The FCE identifies WHERE multiple independent analysis vectors converge,
without imposing subjective risk judgments.

Philosophy: "I am not the judge, I am the evidence locker."

Four Independent Vectors:
    STATIC: Linters (ruff, eslint, patterns, bandit)
    FLOW: Taint analysis (taint_flows, framework_taint_patterns)
    PROCESS: Change history (churn-analysis, code_diffs)
    STRUCTURAL: Complexity (cfg-analysis)

Usage:
    from theauditor.fce import FCEQueryEngine, VectorSignal

    engine = FCEQueryEngine(root)
    signal = engine.get_vector_density("src/auth/login.py")
    print(signal.density_label)  # "3/4 vectors"
"""

from theauditor.fce.formatter import FCEFormatter
from theauditor.fce.schema import (
    AIContextBundle,
    ConvergencePoint,
    Fact,
    Vector,
    VectorSignal,
)

__all__ = [
    "Vector",
    "Fact",
    "VectorSignal",
    "ConvergencePoint",
    "AIContextBundle",
    "FCEQueryEngine",
    "FCEFormatter",
    "run_fce",
]


def __getattr__(name: str):
    """Lazy import for FCEQueryEngine and run_fce to avoid circular imports."""
    if name == "FCEQueryEngine":
        from theauditor.fce.query import FCEQueryEngine

        return FCEQueryEngine
    if name == "run_fce":
        from theauditor.fce.engine import run_fce

        return run_fce
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
