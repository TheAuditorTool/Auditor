"""Pydantic models for FCE vector-based consensus engine.

These models define the data structures for:
- Vector: The four independent analysis dimensions
- Fact: A single undeniable observation from one source
- VectorSignal: Which vectors have data for a location
- ConvergencePoint: A location where multiple vectors converge
- AIContextBundle: Package for AI/LLM consumption
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class Vector(str, Enum):
    """The four independent analysis dimensions.

    Each vector represents a fundamentally different way of analyzing code:
    - STATIC: Code quality issues detected by linters
    - FLOW: Data flow vulnerabilities from taint analysis
    - PROCESS: Change volatility from git history
    - STRUCTURAL: Complexity issues from CFG analysis

    Multiple tools within the same vector do NOT increase density.
    5 linters screaming = 1 STATIC vector, not 5 signals.
    """

    STATIC = "static"
    FLOW = "flow"
    PROCESS = "process"
    STRUCTURAL = "structural"


class Fact(BaseModel):
    """A single undeniable observation from one source.

    Facts are the atomic unit of FCE output. They capture:
    - WHAT was observed (observation)
    - WHERE it was found (file_path, line)
    - WHO reported it (source, vector)
    - THE PROOF (raw_data)

    Facts do NOT include opinions, risk levels, or recommendations.
    """

    model_config = ConfigDict(use_enum_values=True)

    vector: Vector
    source: str
    file_path: str
    line: int | None
    observation: str
    raw_data: dict


class VectorSignal(BaseModel):
    """Which vectors have data for a location.

    VectorSignal is the core metric of FCE. It answers:
    "How many INDEPENDENT analysis dimensions flagged this location?"

    Density Interpretation:
    - 4/4 (1.0): Everything is screaming - investigate immediately
    - 3/4 (0.75): Strong convergence - high priority
    - 2/4 (0.5): Multiple signals - worth attention
    - 1/4 (0.25): Single dimension - normal finding
    - 0/4 (0.0): No findings - clean location

    The density is pure math with no thresholds or opinions.
    """

    model_config = ConfigDict(use_enum_values=True)

    file_path: str
    vectors_present: set[Vector]

    @property
    def density(self) -> float:
        """Calculate density as fraction of vectors present (0.0 to 1.0)."""
        return len(self.vectors_present) / 4

    @property
    def density_label(self) -> str:
        """Human-readable density label: 'N/4 vectors'."""
        return f"{len(self.vectors_present)}/4 vectors"

    @property
    def vector_count(self) -> int:
        """Number of vectors with data for this location."""
        return len(self.vectors_present)


class ConvergencePoint(BaseModel):
    """A location where multiple vectors converge.

    ConvergencePoint packages all the facts for a specific code location
    along with its VectorSignal. This is what FCE reports to consumers.

    The line_start/line_end range covers the span of all facts at this
    convergence point (e.g., a function with findings on multiple lines).
    """

    model_config = ConfigDict(use_enum_values=True)

    file_path: str
    line_start: int
    line_end: int
    signal: VectorSignal
    facts: list[Fact]


class AIContextBundle(BaseModel):
    """Package for AI/LLM consumption.

    AIContextBundle wraps a ConvergencePoint with additional context
    from related database tables (framework info, security patterns, etc.).

    This is what gets passed to autonomous agents for analysis.
    """

    model_config = ConfigDict(use_enum_values=True)

    convergence: ConvergencePoint
    context_layers: dict[str, list[dict]]

    def to_prompt_context(self) -> str:
        """Serialize to JSON for LLM prompt inclusion."""
        return self.model_dump_json(indent=2)
