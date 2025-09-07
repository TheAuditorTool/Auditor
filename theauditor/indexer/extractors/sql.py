"""SQL file extractor.

Handles extraction of SQL-specific elements including:
- SQL object definitions (tables, indexes, views, functions)
- SQL queries and their structure
"""

from pathlib import Path
from typing import Dict, Any, List, Optional

from . import BaseExtractor


class SQLExtractor(BaseExtractor):
    """Extractor for SQL files."""
    
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports."""
        return ['.sql', '.psql', '.ddl']
    
    def extract(self, file_info: Dict[str, Any], content: str, 
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all relevant information from a SQL file.
        
        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree (not used for SQL)
            
        Returns:
            Dictionary containing all extracted data
        """
        result = {
            'sql_objects': [],
            'sql_queries': []
        }
        
        # Extract SQL objects (CREATE statements)
        result['sql_objects'] = self.extract_sql_objects(content)
        
        # Extract and parse SQL queries
        result['sql_queries'] = self.extract_sql_queries(content)
        
        return result