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

        # Extract SQL DDL objects (CREATE TABLE, CREATE INDEX, etc.)
        # This is legitimate use of string patterns for .sql files
        result['sql_objects'] = self.extract_sql_objects(content)

        # For .sql files, we don't extract individual queries
        # These files contain DDL statements and migrations, not runtime queries
        # SQL injection detection happens in code files (Python/JS), not .sql files
        result['sql_queries'] = []

        return result