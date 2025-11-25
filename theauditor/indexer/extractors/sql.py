"""SQL file extractor.

Handles extraction of SQL-specific elements including:
- SQL object definitions (tables, indexes, views, functions)
- SQL queries and their structure
"""


from typing import Any

from . import BaseExtractor


def parse_sql_query(query_text: str) -> tuple[str, list[str]] | None:
    """Parse SQL query to extract command type and table names.

    Shared helper used by Python and JavaScript extractors to maintain
    consistent SQL parsing logic across languages.

    Args:
        query_text: Raw SQL query string

    Returns:
        Tuple of (command, tables) if parseable, None if unparseable
        - command: SQL command type (SELECT, INSERT, UPDATE, etc.)
        - tables: List of table names referenced in query

    Raises:
        ImportError: If sqlparse is not installed (hard failure)
    """
    try:
        import sqlparse
    except ImportError:
        raise ImportError(
            "sqlparse is required for SQL query parsing. "
            "Install with: pip install sqlparse"
        )

    try:
        parsed = sqlparse.parse(query_text)
        if not parsed:
            return None

        statement = parsed[0]
        command = statement.get_type()

        # Skip UNKNOWN commands
        if not command or command == 'UNKNOWN':
            return None

        # Extract table names
        tables = []
        tokens = list(statement.flatten())
        for i, token in enumerate(tokens):
            if token.ttype is None and token.value.upper() in ['FROM', 'INTO', 'UPDATE', 'TABLE', 'JOIN']:
                # Look for next non-whitespace token
                for j in range(i + 1, len(tokens)):
                    next_token = tokens[j]
                    if not next_token.is_whitespace:
                        if next_token.ttype in [None, sqlparse.tokens.Name]:
                            table_name = next_token.value.strip('"\'`')
                            if '.' in table_name:
                                table_name = table_name.split('.')[-1]
                            if table_name and table_name.upper() not in ['SELECT', 'WHERE', 'SET', 'VALUES']:
                                tables.append(table_name)
                        break

        return (command, tables)

    except Exception:
        return None


class SQLExtractor(BaseExtractor):
    """Extractor for SQL files."""
    
    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return ['.sql', '.psql', '.ddl']
    
    def extract(self, file_info: dict[str, Any], content: str, 
                tree: Any | None = None) -> dict[str, Any]:
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