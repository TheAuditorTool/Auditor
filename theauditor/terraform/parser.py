"""Deprecated Terraform parser placeholder."""

from pathlib import Path
from typing import Any


class TerraformParser:
    """Legacy parser stub."""

    def __init__(self) -> None:  # pragma: no cover - legacy stub
        pass

    def parse_file(self, file_path: str) -> dict[str, Any]:  # pragma: no cover
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Terraform file not found: {file_path}")
        raise RuntimeError(
            "TerraformParser is deprecated. Terraform extraction now uses the "
            "tree-sitter pipeline via 'aud index'."
        )
