"""Extractor framework for the indexer.

This module defines the BaseExtractor abstract class and the ExtractorRegistry
for dynamic discovery and registration of language-specific extractors.
"""

import os
import re
import importlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ..config import (
    IMPORT_PATTERNS, ROUTE_PATTERNS, SQL_PATTERNS, SQL_QUERY_PATTERNS
)

# Optional SQL parsing support
try:
    import sqlparse
    HAS_SQLPARSE = True
except ImportError:
    HAS_SQLPARSE = False


class BaseExtractor(ABC):
    """Abstract base class for all language extractors."""
    
    def __init__(self, root_path: Path, ast_parser: Optional[Any] = None):
        """Initialize the extractor.
        
        Args:
            root_path: Project root path
            ast_parser: Optional AST parser instance
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
    
    def extract_imports(self, content: str, file_ext: str) -> List[Tuple[str, str]]:
        """Extract import statements from file content.
        
        Args:
            content: File content
            file_ext: File extension
            
        Returns:
            List of (kind, value) tuples for imports
        """
        imports = []
        seen = set()

        js_like_exts = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}
        if file_ext in js_like_exts:
            patterns = IMPORT_PATTERNS[:3]  # JavaScript/TypeScript specific
        else:
            patterns = IMPORT_PATTERNS

        for pattern in patterns:
            for match in pattern.finditer(content):
                value = match.group(1) if match.lastindex else match.group(0)
                # Determine kind based on pattern
                if "require" in pattern.pattern:
                    kind = "require"
                elif "from" in pattern.pattern and "import" in pattern.pattern:
                    kind = "from"
                elif "package" in pattern.pattern:
                    kind = "package"
                else:
                    kind = "import"
                if file_ext in js_like_exts:
                    value = value.strip().strip("'\"")
                if value not in seen:
                    imports.append((kind, value))
                    seen.add(value)
        return imports
    
    def extract_routes(self, content: str) -> List[Tuple[str, str]]:
        """Extract route definitions from file content.
        
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
        """Extract SQL object definitions from file content.
        
        Args:
            content: File content
            
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
    
    def extract_sql_queries(self, content: str) -> List[Dict]:
        """Extract and parse SQL queries from code.
        
        Args:
            content: File content
            
        Returns:
            List of query dictionaries
        """
        if not HAS_SQLPARSE:
            return []
        
        queries = []
        
        # Find all potential SQL query strings
        for pattern in SQL_QUERY_PATTERNS:
            for match in pattern.finditer(content):
                query_text = match.group(1) if match.lastindex else match.group(0)

                # Calculate line number
                line = content[:match.start()].count('\n') + 1
                
                # Clean up the query text
                query_text = query_text.strip()
                if not query_text:
                    continue
                
                try:
                    # Parse the SQL query
                    parsed = sqlparse.parse(query_text)
                    if not parsed:
                        continue
                    
                    for statement in parsed:
                        # Extract command type
                        command = statement.get_type()
                        if not command:
                            # Try to extract manually from first token
                            tokens = statement.tokens
                            for token in tokens:
                                if not token.is_whitespace:
                                    command = str(token).upper()
                                    break
                        
                        # Extract table names
                        tables = []
                        tokens = list(statement.flatten())
                        for i, token in enumerate(tokens):
                            if token.ttype is None and token.value.upper() in ['FROM', 'INTO', 'UPDATE', 'TABLE', 'JOIN']:
                                # Look for the next non-whitespace token
                                for j in range(i + 1, len(tokens)):
                                    next_token = tokens[j]
                                    if not next_token.is_whitespace:
                                        if next_token.ttype in [None, sqlparse.tokens.Name]:
                                            table_name = next_token.value
                                            # Clean up table name
                                            table_name = table_name.strip('"\'`')
                                            if '.' in table_name:
                                                table_name = table_name.split('.')[-1]
                                            if table_name and not table_name.upper() in ['SELECT', 'WHERE', 'SET', 'VALUES']:
                                                tables.append(table_name)
                                        break
                        
                        tables = tables or self._extract_sql_tables(query_text)

                        queries.append({
                            'line': line,
                            'query_text': query_text[:1000],  # Limit length
                            'command': command or 'UNKNOWN',
                            'tables': tables
                        })
                except Exception:
                    # Skip queries that can't be parsed
                    continue
        
        return queries

    @staticmethod
    def _extract_sql_tables(query_text: str) -> List[str]:
        """Best-effort extraction of table names from SQL text."""
        tables: List[str] = []
        upper = query_text.upper()
        patterns = [
            r'FROM\s+([A-Z0-9_\.\"`]+)',
            r'JOIN\s+([A-Z0-9_\.\"`]+)',
            r'INTO\s+([A-Z0-9_\.\"`]+)',
            r'UPDATE\s+([A-Z0-9_\.\"`]+)'
        ]

        def clean(name: str) -> str:
            for ch in ['"', "'", '`']:
                name = name.replace(ch, '')
            if '.' in name:
                name = name.split('.')[-1]
            return name.strip()

        seen = set()
        for pattern in patterns:
            for match in re.finditer(pattern, upper):
                raw = clean(match.group(1))
                if raw and raw not in seen:
                    seen.add(raw)
                    tables.append(raw)

        return tables


class ExtractorRegistry:
    """Registry for dynamic discovery and management of extractors."""
    
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
        """Auto-discover and register all extractor modules."""
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
    
    def get_extractor(self, file_extension: str) -> Optional[BaseExtractor]:
        """Get the appropriate extractor for a file extension.
        
        Args:
            file_extension: File extension (e.g., '.py')
            
        Returns:
            Extractor instance or None if not supported
        """
        return self.extractors.get(file_extension)
    
    def supported_extensions(self) -> List[str]:
        """Get list of all supported file extensions.
        
        Returns:
            List of supported extensions
        """
        return list(self.extractors.keys())
