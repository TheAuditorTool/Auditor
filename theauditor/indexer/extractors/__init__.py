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
3. JWT API patterns (well-defined, low false positive rate)

FORBIDDEN:
- Regex-based import extraction (use AST)
- Regex-based SQL query extraction in code files (use AST to find db.execute() calls)
"""

import os
import re
import importlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ..config import (
    ROUTE_PATTERNS,
    SQL_PATTERNS,
    JWT_SIGN_PATTERN,
    JWT_VERIFY_PATTERN,
    JWT_DECODE_PATTERN
)


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

    def __init__(self, root_path: Path, ast_parser: Optional[Any] = None):
        """Initialize the extractor.

        Args:
            root_path: Project root path
            ast_parser: Optional AST parser instance (for language extractors)
        """
        self.root_path = root_path
        self.ast_parser = ast_parser

    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports.

        Returns:
            List of file extensions (e.g., ['.py', '.pyx'])
        """
        pass

    @abstractmethod
    def extract(self, file_info: Dict[str, Any], content: str,
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all relevant information from a file.

        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree

        Returns:
            Dictionary containing all extracted data
        """
        pass

    # =========================================================================
    # STRING-BASED EXTRACTION METHODS
    # These are for config files without AST parsers. Language extractors
    # (Python, JavaScript) should use AST instead of calling these methods.
    # =========================================================================

    def extract_routes(self, content: str) -> List[Tuple[str, str]]:
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

    def extract_sql_objects(self, content: str) -> List[Tuple[str, str]]:
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
                # Determine kind from pattern
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

    def extract_jwt_patterns(self, content: str) -> List[Dict]:
        """Extract JWT API patterns with metadata parsing.

        Detects JWT library usage:
        - jwt.sign(payload, secret, options)
        - jwt.verify(token, secret, options)
        - jwt.decode(token)

        This has a low false positive rate because:
        1. Matches specific JWT library API calls
        2. Extracts structured metadata (algorithm, expiry, etc.)
        3. Categorizes secrets (hardcoded vs environment)

        Both Python (PyJWT) and JavaScript (jsonwebtoken) use similar APIs,
        making this pattern applicable across languages.

        Args:
            content: File content

        Returns:
            List of JWT pattern dictionaries with categorized metadata
        """
        patterns = []

        # Find jwt.sign calls and categorize
        for match in JWT_SIGN_PATTERN.finditer(content):
            line = content[:match.start()].count('\n') + 1
            payload = match.group(1).strip()
            secret = match.group(2).strip()
            options = match.group(3).strip() if match.group(3) else '{}'

            # Categorize secret type
            secret_type = 'unknown'
            secret_value = ''
            if 'process.env' in secret or 'os.environ' in secret or 'os.getenv' in secret:
                secret_type = 'environment'
                # Extract environment variable name
                env_match = re.search(r'(?:process\.env\.|os\.environ\[|os\.getenv\()[\'"]*(\w+)', secret)
                secret_value = env_match.group(1) if env_match else 'UNKNOWN_ENV'
            elif 'config.' in secret or 'secrets.' in secret or 'settings.' in secret:
                secret_type = 'config'
                secret_value = secret.split('.')[-1].strip('"\' )')
            elif secret.startswith('"') or secret.startswith("'"):
                secret_type = 'hardcoded'
                secret_value = secret.strip('"\'')[:32]  # First 32 chars only
            else:
                secret_type = 'variable'
                secret_value = secret

            # Extract algorithm
            algorithm = 'HS256'  # Default per JWT spec
            if 'algorithm' in options:
                algo_match = re.search(r'algorithm["\']?\s*[:=]\s*["\']([\w\d]+)', options)
                if algo_match:
                    algorithm = algo_match.group(1)

            # Check for expiration
            has_expiry = any(exp in options for exp in ['expiresIn', 'exp', 'notBefore', 'maxAge'])

            # Check for sensitive data in payload
            sensitive_fields = []
            for field in ['password', 'secret', 'creditCard', 'ssn', 'apiKey']:
                if field.lower() in payload.lower():
                    sensitive_fields.append(field)

            patterns.append({
                'type': 'jwt_sign',
                'line': line,
                'secret_type': secret_type,
                'secret_value': secret_value,
                'algorithm': algorithm,
                'has_expiry': has_expiry,
                'sensitive_fields': sensitive_fields,
                'full_match': match.group(0)[:500]  # Limit for storage
            })

        # Find jwt.verify calls
        for match in JWT_VERIFY_PATTERN.finditer(content):
            line = content[:match.start()].count('\n') + 1
            token = match.group(1).strip()
            secret = match.group(2).strip()
            options = match.group(3).strip() if match.group(3) else '{}'

            # Check for dangerous 'none' algorithm
            allows_none = False
            if 'algorithms' in options:
                if 'none' in options.lower() or '"none"' in options.lower():
                    allows_none = True

            # Check for algorithm confusion (both symmetric and asymmetric)
            algorithms_found = []
            for algo in ['HS256', 'HS384', 'HS512', 'RS256', 'RS384', 'RS512', 'ES256', 'PS256']:
                if algo in options:
                    algorithms_found.append(algo)

            has_confusion = False
            if algorithms_found:
                has_symmetric = any(a.startswith('HS') for a in algorithms_found)
                has_asymmetric = any(a.startswith(('RS', 'ES', 'PS')) for a in algorithms_found)
                has_confusion = has_symmetric and has_asymmetric

            patterns.append({
                'type': 'jwt_verify',
                'line': line,
                'allows_none': allows_none,
                'has_confusion': has_confusion,
                'algorithms': algorithms_found,
                'full_match': match.group(0)[:500]
            })

        # Find jwt.decode calls (often vulnerable - decodes without verification)
        for match in JWT_DECODE_PATTERN.finditer(content):
            line = content[:match.start()].count('\n') + 1
            patterns.append({
                'type': 'jwt_decode',
                'line': line,
                'full_match': match.group(0)[:200]
            })

        return patterns


class ExtractorRegistry:
    """Registry for dynamic discovery and management of extractors.

    Automatically discovers all extractor modules in the extractors/ directory
    and registers them by their supported file extensions.

    Design:
    - One extractor class per file (python.py → PythonExtractor)
    - Extractors register themselves via supported_extensions()
    - No hardcoded mapping - pure discovery pattern
    """

    def __init__(self, root_path: Path, ast_parser: Optional[Any] = None):
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

        # Find all Python files in the extractors directory
        for file_path in extractor_dir.glob("*.py"):
            if file_path.name.startswith('_'):
                continue  # Skip __init__.py and private modules

            module_name = file_path.stem

            try:
                # Import the module
                module = importlib.import_module(f'.{module_name}', package='theauditor.indexer.extractors')

                # Find extractor class (looking for subclasses of BaseExtractor)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        issubclass(attr, BaseExtractor) and
                        attr != BaseExtractor):

                        # Instantiate the extractor
                        extractor = attr(self.root_path, self.ast_parser)

                        # Register for all supported extensions
                        for ext in extractor.supported_extensions():
                            self.extractors[ext] = extractor

                        break  # One extractor per module

            except (ImportError, AttributeError) as e:
                # Skip modules that can't be imported or don't have extractors
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"Debug: Failed to load extractor {module_name}: {e}")
                continue

    def get_extractor(self, file_path: str, file_extension: str) -> Optional[BaseExtractor]:
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

        # Enforce should_extract() filter if extractor provides it
        # This allows extractors like JsonConfigExtractor to handle specific files
        # (e.g., package.json) without processing all files of that extension (.json)
        if hasattr(extractor, 'should_extract'):
            if not extractor.should_extract(file_path):
                return None

        return extractor

    def supported_extensions(self) -> List[str]:
        """Get list of all supported file extensions.

        Returns:
            List of supported extensions
        """
        return list(self.extractors.keys())
