"""Extractor framework for the indexer.

This module defines the BaseExtractor abstract class and the ExtractorRegistry
for dynamic discovery and registration of language-specific extractors.
"""

import os
import re
import json
import importlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ..config import (
    IMPORT_PATTERNS, ROUTE_PATTERNS, SQL_PATTERNS, SQL_QUERY_PATTERNS,
    JWT_SIGN_PATTERN, JWT_VERIFY_PATTERN, JWT_DECODE_PATTERN, JWT_SECRET_PATTERNS
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
        for pattern in IMPORT_PATTERNS:
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
                imports.append((kind, value))
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

    def extract_jwt_patterns(self, content: str) -> List[Dict]:
        """Extract JWT patterns with metadata parsing.

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
            if 'process.env' in secret:
                secret_type = 'environment'
                env_match = re.search(r'process\.env\.(\w+)', secret)
                secret_value = env_match.group(1) if env_match else 'UNKNOWN_ENV'
            elif 'config.' in secret or 'secrets.' in secret:
                secret_type = 'config'
                secret_value = secret.split('.')[-1]
            elif secret.startswith('"') or secret.startswith("'"):
                secret_type = 'hardcoded'
                secret_value = secret.strip('"\'')[:32]  # First 32 chars only
            else:
                secret_type = 'variable'
                secret_value = secret

            # Extract algorithm
            algorithm = 'HS256'  # Default per JWT spec
            if 'algorithm' in options:
                algo_match = re.search(r'algorithm["\']?\s*:\s*["\']([\w\d]+)', options)
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

        # Find jwt.decode calls (often vulnerable)
        for match in JWT_DECODE_PATTERN.finditer(content):
            line = content[:match.start()].count('\n') + 1
            patterns.append({
                'type': 'jwt_decode',
                'line': line,
                'full_match': match.group(0)[:200]
            })

        return patterns


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