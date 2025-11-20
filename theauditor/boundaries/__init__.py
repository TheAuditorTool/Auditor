"""Boundary Analysis Module.

Detects and analyzes security boundaries in code:
- Input validation boundaries
- Authorization boundaries
- Multi-tenant isolation boundaries
- Sanitization boundaries
- Output encoding boundaries

Key Concept: Boundary Distance
    Measures how many function calls separate an entry point from its control point.

    Distance 0 = Perfect (control at entry)
    Distance 1-2 = Acceptable (control nearby)
    Distance 3+ = Risky (control too late)
    None = Critical (no control found)
"""

from theauditor.boundaries.distance import (
    calculate_distance,
    find_all_paths_to_controls,
    measure_boundary_quality
)

__all__ = [
    'calculate_distance',
    'find_all_paths_to_controls',
    'measure_boundary_quality'
]
