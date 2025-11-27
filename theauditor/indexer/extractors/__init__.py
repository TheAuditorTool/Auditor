"""Extractor framework for the indexer.

This module defines the BaseExtractor abstract class and the ExtractorRegistry
for dynamic discovery and registration of language-specific extractors.

CRITICAL ARCHITECTURE PRINCIPLE:
BaseExtractor provides MINIMAL string-based fallback methods for configuration
files (JSON, YAML, Nginx) that lack AST parsers.

Language extractors (Python, JavaScript) MUST use AST-based extraction.
String/regex extraction is ONLY for:
1. Route definitions (inherently string literals in all frameworks)
2. SQL DDL (CREATE TABLE etc in .sql files)

CRITICAL ARCHITECTURAL MANDATE: NO REGEX FOR ANYTHING ELSE. USE AST.

FORBIDDEN:
- Regex-based import extraction (use AST)
- Regex-based SQL query extraction in code files (use AST to find db.execute() calls)
- Regex-based JWT extraction (use AST via function_calls data)
"""

import importlib
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..config import ROUTE_PATTERNS, SQL_PATTERNS


class BaseExtractor(ABC):
    """Abstract base class for all language extractors.

    Provides minimal string-based fallback methods for files without AST parsers
    (configuration files, etc.). Language-specific extractors should use AST-based
    extraction instead of these methods.

    Design Philosophy:
    - AST-first: Language extractors (Python, JS) should use AST parsers
    - String fallback: Only for config files (webpack, nginx, docker-compose)
    - Pattern quality: Only include patterns with low false positive rates
    """

    def __init__(self, root_path: Path, ast_parser: Any | None = None):
        """Initialize the extractor.

        Args:
            root_path: Project root path
            ast_parser: Optional AST parser instance (for language extractors)
        """
        self.root_path = root_path
        self.ast_parser = ast_parser

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports.

        Returns:
            List of file extensions (e.g., ['.py', '.pyx'])
        """
        pass

    @abstractmethod
    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract all relevant information from a file.

        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree

        Returns:
            Dictionary containing all extracted data
        """
        pass

    def extract_routes(self, content: str) -> list[tuple[str, str]]:
        """Extract route definitions from file content.

        Routes are inherently string-based in all frameworks:
        - Express: app.get('/path', ...)
        - Flask: @app.route('/path')
        - Django: path('/path', ...)

        This is a legitimate use of regex as routes are string literals.

        Args:
            content: File content

        Returns:
            List of (method, path) tuples
        """
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
        """Extract SQL object definitions from .sql files.

        This method detects DDL statements (CREATE TABLE, CREATE INDEX, etc.)
        in actual SQL files, not code files.

        For SQL queries embedded in code (Python, JavaScript), language extractors
        should use AST-based extraction to find db.execute() calls.

        Args:
            content: SQL file content

        Returns:
            List of (kind, name) tuples
        """
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

    def cleanup(self) -> None:
        """Clean up extractor resources after all files processed.

        Override this if extractor maintains persistent resources
        (LSP sessions, database connections, temp directories).

        Default: no-op.
        """
        pass


class ExtractorRegistry:
    """Registry for dynamic discovery and management of extractors.

    Automatically discovers all extractor modules in the extractors/ directory
    and registers them by their supported file extensions.

    Design:
    - One extractor class per file (python.py → PythonExtractor)
    - Extractors register themselves via supported_extensions()
    - No hardcoded mapping - pure discovery pattern
    """

    def __init__(self, root_path: Path, ast_parser: Any | None = None):
        """Initialize the registry and discover extractors.

        Args:
            root_path: Project root path
            ast_parser: Optional AST parser instance
        """
        self.root_path = root_path
        self.ast_parser = ast_parser
        self.extractors = {}
        self._discover()

    def _discover(self):
        """Auto-discover and register all extractor modules.

        Scans the extractors/ directory for Python files, imports them,
        and registers any BaseExtractor subclasses found.
        """
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
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"Debug: Failed to load extractor {module_name}: {e}")
                continue

    def get_extractor(self, file_path: str, file_extension: str) -> BaseExtractor | None:
        """Get the appropriate extractor for a file.

        Args:
            file_path: Full file path
            file_extension: File extension (e.g., '.py')

        Returns:
            Extractor instance or None if not supported
        """
        extractor = self.extractors.get(file_extension)
        if not extractor:
            return None

        if hasattr(extractor, "should_extract"):
            if not extractor.should_extract(file_path):
                return None

        return extractor

    def supported_extensions(self) -> list[str]:
        """Get list of all supported file extensions.

        Returns:
            List of supported extensions
        """
        return list(self.extractors.keys())
