"""FCE Formatter for JSON output and data serialization.

Text rendering is handled directly in the command using Rich.
This module focuses on JSON serialization only.

IMPORTANT: NO EMOJIS - Windows CP1252 encoding will crash on emojis.
"""

import json
from typing import Any

from theauditor.fce.schema import (
    ConvergencePoint,
    Vector,
    VectorSignal,
)


class FCEFormatter:
    """Formats FCE data for JSON output.

    Text rendering is done directly in commands using Rich.
    This class handles JSON serialization for --format json and --write modes.
    """

    # Vector display names (no emojis)
    VECTOR_LABELS: dict[Vector, str] = {
        Vector.STATIC: "STATIC",
        Vector.FLOW: "FLOW",
        Vector.PROCESS: "PROCESS",
        Vector.STRUCTURAL: "STRUCTURAL",
    }

    # Vector short codes for compact display
    VECTOR_CODES: dict[Vector, str] = {
        Vector.STATIC: "S",
        Vector.FLOW: "F",
        Vector.PROCESS: "P",
        Vector.STRUCTURAL: "T",  # T for sTructural (S taken)
    }

    @staticmethod
    def get_vector_code_string(signal: VectorSignal) -> str:
        """Get compact vector code string like 'SF-T'.

        Args:
            signal: The VectorSignal

        Returns:
            4-char string with vector codes or dashes
        """
        codes = []
        code_map = {
            Vector.STATIC: "S",
            Vector.FLOW: "F",
            Vector.PROCESS: "P",
            Vector.STRUCTURAL: "T",
        }
        for vector in [Vector.STATIC, Vector.FLOW, Vector.PROCESS, Vector.STRUCTURAL]:
            if vector in signal.vectors_present:
                codes.append(code_map[vector])
            else:
                codes.append("-")
        return "".join(codes)

    def format_json(self, data: Any) -> str:
        """Format data as JSON string.

        Handles Pydantic models and standard types.

        Args:
            data: Any JSON-serializable data or Pydantic model

        Returns:
            JSON string with 2-space indentation
        """
        return json.dumps(self._to_json_serializable(data), indent=2)

    def _to_json_serializable(self, data: Any) -> Any:
        """Convert data to JSON-serializable format.

        Handles Pydantic models, sets, enums, and nested structures.
        """
        # Handle None
        if data is None:
            return None

        # Handle Pydantic models
        if hasattr(data, "model_dump"):
            dumped = data.model_dump()
            return self._to_json_serializable(dumped)

        # Handle sets (convert to sorted lists)
        if isinstance(data, set):
            return sorted([self._to_json_serializable(item) for item in data])

        # Handle enums
        if isinstance(data, Vector):
            return data.value

        # Handle dicts
        if isinstance(data, dict):
            return {k: self._to_json_serializable(v) for k, v in data.items()}

        # Handle lists
        if isinstance(data, list):
            return [self._to_json_serializable(item) for item in data]

        # Primitives
        return data

    def point_to_dict(self, point: ConvergencePoint) -> dict:
        """Convert ConvergencePoint to serializable dict.

        Args:
            point: ConvergencePoint to convert

        Returns:
            Dict suitable for JSON serialization
        """
        # Handle both enum objects and string values (use_enum_values=True)
        vectors = []
        for v in point.signal.vectors_present:
            if hasattr(v, "value"):
                vectors.append(v.value)
            else:
                vectors.append(str(v))

        facts = []
        for f in point.facts:
            vector_val = f.vector.value if hasattr(f.vector, "value") else str(f.vector)
            facts.append({
                "vector": vector_val,
                "source": f.source,
                "file_path": f.file_path,
                "line": f.line,
                "observation": f.observation,
                "raw_data": f.raw_data,
            })

        return {
            "file_path": point.file_path,
            "line_start": point.line_start,
            "line_end": point.line_end,
            "signal": {
                "file_path": point.signal.file_path,
                "vectors_present": sorted(vectors),
                "vector_count": point.signal.vector_count,
                "density": point.signal.density,
                "density_label": point.signal.density_label,
            },
            "facts": facts,
        }
