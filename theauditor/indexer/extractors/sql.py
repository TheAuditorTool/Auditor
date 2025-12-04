"""SQL file extractor."""

from typing import Any

from ..fidelity_utils import FidelityToken
from . import BaseExtractor


def parse_sql_query(query_text: str) -> tuple[str, list[str]] | None:
    """Parse SQL query to extract command type and table names."""
    try:
        import sqlparse
    except ImportError as e:
        raise ImportError(
            "sqlparse is required for SQL query parsing. Install with: pip install sqlparse"
        ) from e

    try:
        parsed = sqlparse.parse(query_text)
        if not parsed:
            return None

        statement = parsed[0]
        command = statement.get_type()

        if not command or command == "UNKNOWN":
            return None

        tables = []
        tokens = list(statement.flatten())
        for i, token in enumerate(tokens):
            if token.ttype is None and token.value.upper() in [
                "FROM",
                "INTO",
                "UPDATE",
                "TABLE",
                "JOIN",
            ]:
                for j in range(i + 1, len(tokens)):
                    next_token = tokens[j]
                    if not next_token.is_whitespace:
                        if next_token.ttype in [None, sqlparse.tokens.Name]:
                            table_name = next_token.value.strip("\"'`")
                            if "." in table_name:
                                table_name = table_name.split(".")[-1]
                            if table_name and table_name.upper() not in [
                                "SELECT",
                                "WHERE",
                                "SET",
                                "VALUES",
                            ]:
                                tables.append(table_name)
                        break

        return (command, tables)

    except Exception:
        return None


class SQLExtractor(BaseExtractor):
    """Extractor for SQL files."""

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return [".sql", ".psql", ".ddl"]

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract all relevant information from a SQL file."""
        result = {"sql_objects": [], "sql_queries": []}

        result["sql_objects"] = self.extract_sql_objects(content)

        result["sql_queries"] = []

        return FidelityToken.attach_manifest(result)
