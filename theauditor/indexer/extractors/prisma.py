"""Prisma schema extractor - Fidelity Protocol Compliant."""

import re
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger

from ..fidelity_utils import FidelityToken
from . import BaseExtractor


class PrismaExtractor(BaseExtractor):
    """Extractor for Prisma schema files."""

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return []

    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file."""
        file_name_lower = Path(file_path).name.lower()
        return file_name_lower == "schema.prisma"

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract Prisma models and return data dict with manifest."""
        file_path_str = str(file_info["path"])

        result: dict[str, Any] = {
            "prisma_models": [],
        }

        try:
            models = self._parse_schema(content)

            for model in models:
                for field in model["fields"]:
                    result["prisma_models"].append(
                        {
                            "model_name": model["name"],
                            "field_name": field["name"],
                            "field_type": field["type"],
                            "is_indexed": field["is_indexed"],
                            "is_unique": field["is_unique"],
                            "is_relation": field["is_relation"],
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to parse Prisma schema {file_path_str}: {e}")

        return FidelityToken.attach_manifest(result)

    def _parse_schema(self, content: str) -> list[dict[str, Any]]:
        """Parse Prisma schema content to extract models."""
        models = []

        model_pattern = re.compile(r"model\s+(\w+)\s*\{([^}]*)\}", re.DOTALL)

        for match in model_pattern.finditer(content):
            model_name = match.group(1)
            model_content = match.group(2)

            model = {"name": model_name, "fields": self._parse_fields(model_content)}

            models.append(model)

        return models

    def _parse_fields(self, content: str) -> list[dict[str, Any]]:
        """Parse fields within a model block."""
        fields = []
        lines = content.strip().split("\n")

        for line in lines:
            line = line.strip()

            if not line or line.startswith("//"):
                continue

            if line.startswith("@@"):
                continue

            field_match = re.match(r"^(\w+)\s+(\w+(?:\[\])?(?:\?)?)", line)
            if field_match:
                field_name = field_match.group(1)
                field_type = field_match.group(2)

                field = {
                    "name": field_name,
                    "type": field_type,
                    "is_indexed": False,
                    "is_unique": False,
                    "is_relation": False,
                }

                if "@id" in line:
                    field["is_indexed"] = True
                    field["is_unique"] = True

                if "@unique" in line:
                    field["is_unique"] = True
                    field["is_indexed"] = True

                if "@index" in line:
                    field["is_indexed"] = True

                if "@relation" in line:
                    field["is_relation"] = True

                primitives = {
                    "String",
                    "Int",
                    "BigInt",
                    "Float",
                    "Boolean",
                    "DateTime",
                    "Json",
                    "Bytes",
                    "Decimal",
                }
                base_type = field_type.replace("[]", "").replace("?", "")
                if base_type and base_type[0].isupper() and base_type not in primitives:
                    field["is_relation"] = True

                fields.append(field)

        for line in lines:
            line = line.strip()
            if line.startswith("@@index"):
                index_match = re.search(r"@@index\s*\(\s*\[([^\]]+)\]", line)
                if index_match:
                    indexed_fields = index_match.group(1).split(",")
                    for indexed_field in indexed_fields:
                        indexed_field = indexed_field.strip().strip('"').strip("'")

                        for field in fields:
                            if field["name"] == indexed_field:
                                field["is_indexed"] = True

            elif line.startswith("@@unique"):
                unique_match = re.search(r"@@unique\s*\(\s*\[([^\]]+)\]", line)
                if unique_match:
                    unique_fields = unique_match.group(1).split(",")
                    for unique_field in unique_fields:
                        unique_field = unique_field.strip().strip('"').strip("'")

                        for field in fields:
                            if field["name"] == unique_field:
                                field["is_unique"] = True
                                field["is_indexed"] = True

        return fields
