"""Extractor framework for the indexer."""

import importlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger

from ..config import ROUTE_PATTERNS, SQL_PATTERNS


class BaseExtractor(ABC):
    """Abstract base class for all language extractors."""

    def __init__(self, root_path: Path, ast_parser: Any | None = None):
        """Initialize the extractor."""
        self.root_path = root_path
        self.ast_parser = ast_parser

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        pass

    @abstractmethod
    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract all relevant information from a file."""
        pass

    def extract_routes(self, content: str) -> list[tuple[str, str]]:
        """Extract route definitions from file content."""
        routes = []
        for pattern in ROUTE_PATTERNS:
            for match in pattern.finditer(content):
                if match.lastindex == 2:
                    method = match.group(1).upper()
                    path = match.group(2)
                else:
                    method = "ANY"
                    path = match.group(1) if match.lastindex else match.group(0)
                routes.append((method, path))
        return routes

    def extract_sql_objects(self, content: str) -> list[tuple[str, str]]:
        """Extract SQL object definitions from .sql files."""
        objects = []
        for pattern in SQL_PATTERNS:
            for match in pattern.finditer(content):
                name = match.group(1)

                pattern_text = pattern.pattern.lower()
                if "table" in pattern_text:
                    kind = "table"
                elif "index" in pattern_text:
                    kind = "index"
                elif "view" in pattern_text:
                    kind = "view"
                elif "function" in pattern_text:
                    kind = "function"
                elif "policy" in pattern_text:
                    kind = "policy"
                elif "constraint" in pattern_text:
                    kind = "constraint"
                else:
                    kind = "unknown"
                objects.append((kind, name))
        return objects

    def cleanup(self) -> None:  # noqa: B027
        """Clean up extractor resources after all files processed.

        Default no-op. Override in subclasses that need cleanup.
        """


class ExtractorRegistry:
    """Registry for dynamic discovery and management of extractors."""

    def __init__(self, root_path: Path, ast_parser: Any | None = None):
        """Initialize the registry and discover extractors."""
        self.root_path = root_path
        self.ast_parser = ast_parser
        self.extractors = {}
        self._discover()

    def _discover(self):
        """Auto-discover and register all extractor modules."""
        extractor_dir = Path(__file__).parent

        for file_path in extractor_dir.glob("*.py"):
            if file_path.name.startswith("_"):
                continue

            module_name = file_path.stem

            try:
                module = importlib.import_module(
                    f".{module_name}", package="theauditor.indexer.extractors"
                )

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseExtractor)
                        and attr != BaseExtractor
                    ):
                        extractor = attr(self.root_path, self.ast_parser)

                        for ext in extractor.supported_extensions():
                            self.extractors[ext] = extractor

                        break

            except (ImportError, AttributeError) as e:
                logger.error(f"EXTRACTOR LOAD FAILED: {module_name} - {e}")
                raise

    def get_extractor(self, file_path: str, file_extension: str) -> BaseExtractor | None:
        """Get the appropriate extractor for a file."""
        extractor = self.extractors.get(file_extension)
        if not extractor:
            return None

        if hasattr(extractor, "should_extract") and not extractor.should_extract(file_path):
            return None

        return extractor

    def supported_extensions(self) -> list[str]:
        """Get list of all supported file extensions."""
        return list(self.extractors.keys())
