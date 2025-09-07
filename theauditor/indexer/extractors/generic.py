"""Generic file extractor.

Handles extraction for files that don't have specialized extractors:
- Webpack configurations
- Docker Compose files
- Nginx configurations
- Other configuration files
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import BaseExtractor
from ..config import COMPOSE_PATTERNS, NGINX_PATTERNS

# Check for optional custom parsers
try:
    from theauditor.parsers.webpack_config_parser import WebpackConfigParser
    from theauditor.parsers.compose_parser import ComposeParser
    from theauditor.parsers.nginx_parser import NginxParser
    HAS_CUSTOM_PARSERS = True
except ImportError:
    HAS_CUSTOM_PARSERS = False


class GenericExtractor(BaseExtractor):
    """Generic extractor for configuration and other files."""
    
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports."""
        # This extractor handles files by name pattern, not extension
        return []
    
    def should_extract(self, file_path: str) -> bool:
        """Check if this extractor should handle the file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if this extractor should handle the file
        """
        file_name = Path(file_path).name.lower()
        
        # Check for specific file patterns
        if file_name.endswith('webpack.config.js'):
            return True
        if file_name in COMPOSE_PATTERNS:
            return True
        if file_name in NGINX_PATTERNS or file_name.endswith('.conf'):
            return True
        
        return False
    
    def extract(self, file_info: Dict[str, Any], content: str, 
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract information from generic configuration files.
        
        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree
            
        Returns:
            Dictionary containing all extracted data
        """
        result = {
            'config_data': {},
            'imports': [],
            'routes': [],
            'sql_queries': []
        }
        
        file_path = self.root_path / file_info['path']
        file_name = file_path.name.lower()
        
        # Handle webpack configuration
        if HAS_CUSTOM_PARSERS and file_name.endswith('webpack.config.js'):
            try:
                parser = WebpackConfigParser()
                webpack_data = parser.parse_file(file_path)
                if webpack_data and not webpack_data.get('error'):
                    result['config_data']['webpack'] = webpack_data
            except Exception:
                pass
        
        # Handle Docker Compose files
        if HAS_CUSTOM_PARSERS and file_name in COMPOSE_PATTERNS:
            try:
                parser = ComposeParser()
                compose_data = parser.parse_file(file_path)
                if compose_data and not compose_data.get('error'):
                    result['config_data']['docker_compose'] = compose_data
            except Exception:
                pass
        
        # Handle Nginx configuration
        if HAS_CUSTOM_PARSERS and (file_name in NGINX_PATTERNS or file_name.endswith('.conf')):
            try:
                parser = NginxParser()
                nginx_data = parser.parse_file(file_path)
                if nginx_data and not nginx_data.get('error'):
                    result['config_data']['nginx'] = nginx_data
                    # Extract routes from nginx location blocks
                    if 'locations' in nginx_data:
                        for location in nginx_data['locations']:
                            result['routes'].append((
                                'ANY',  # Nginx handles all methods by default
                                location.get('path', '/'),
                                []  # No middleware concept in nginx
                            ))
            except Exception:
                pass
        
        # For all files, try to extract common patterns
        result['imports'].extend(self.extract_imports(content, file_info['ext']))
        result['routes'].extend([(m, p, []) for m, p in self.extract_routes(content)])
        result['sql_queries'].extend(self.extract_sql_queries(content))
        
        return result