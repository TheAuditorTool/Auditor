"""GraphQL Querier - Query GraphQL metadata from database."""

import sqlite3
from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger


class GraphQLQuerier:
    """Query GraphQL schema metadata and resolver mappings."""

    def __init__(self, db_path: Path):
        """Initialize querier with database connection."""
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

    def query_type(
        self, type_name: str, show_resolvers: bool = False, show_args: bool = False
    ) -> dict[str, Any]:
        """Query metadata for a specific GraphQL type."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT type_id, type_name, kind, implements, description
            FROM graphql_types
            WHERE type_name = ?
        """,
            (type_name,),
        )

        type_row = cursor.fetchone()
        if not type_row:
            return {"error": f"Type {type_name} not found"}

        result = {
            "type_id": type_row["type_id"],
            "type_name": type_row["type_name"],
            "kind": type_row["kind"],
            "implements": type_row["implements"],
            "description": type_row["description"],
            "fields": [],
        }

        cursor.execute(
            """
            SELECT field_id, field_name, return_type, is_list, is_nullable
            FROM graphql_fields
            WHERE type_id = ?
        """,
            (type_row["type_id"],),
        )

        for field_row in cursor.fetchall():
            field_data = {
                "field_id": field_row["field_id"],
                "field_name": field_row["field_name"],
                "return_type": field_row["return_type"],
                "is_list": bool(field_row["is_list"]),
                "is_nullable": bool(field_row["is_nullable"]),
            }

            if show_args:
                field_data["arguments"] = self._get_field_args(field_row["field_id"])

            if show_resolvers:
                field_data["resolver"] = self._get_resolver(field_row["field_id"])

            result["fields"].append(field_data)

        return result

    def query_field(self, field_name: str, show_resolvers: bool = False) -> dict[str, Any]:
        """Query metadata for a specific field across all types."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT f.field_id, f.type_id, f.field_name, f.return_type, t.type_name
            FROM graphql_fields f
            JOIN graphql_types t ON t.type_id = f.type_id
            WHERE f.field_name = ?
        """,
            (field_name,),
        )

        results = []
        for row in cursor.fetchall():
            field_data = {
                "field_id": row["field_id"],
                "type_name": row["type_name"],
                "field_name": row["field_name"],
                "return_type": row["return_type"],
            }

            if show_resolvers:
                field_data["resolver"] = self._get_resolver(row["field_id"])

            results.append(field_data)

        return {"fields": results}

    def query_all_types(self) -> dict[str, Any]:
        """Query all GraphQL types."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT type_name, kind, COUNT(*) as field_count
            FROM graphql_types t
            LEFT JOIN graphql_fields f ON f.type_id = t.type_id
            GROUP BY t.type_id, type_name, kind
            ORDER BY type_name
        """)

        types = []
        for row in cursor.fetchall():
            types.append(
                {
                    "type_name": row["type_name"],
                    "kind": row["kind"],
                    "field_count": row["field_count"] or 0,
                }
            )

        return {"types": types}

    def _get_field_args(self, field_id: int) -> list[dict[str, Any]]:
        """Get arguments for a field."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT arg_name, arg_type, has_default, default_value, is_nullable
            FROM graphql_field_args
            WHERE field_id = ?
        """,
            (field_id,),
        )

        args = []
        for row in cursor.fetchall():
            args.append(
                {
                    "arg_name": row["arg_name"],
                    "arg_type": row["arg_type"],
                    "has_default": bool(row["has_default"]),
                    "default_value": row["default_value"],
                    "is_nullable": bool(row["is_nullable"]),
                }
            )

        return args

    def _get_resolver(self, field_id: int) -> dict[str, Any]:
        """Get resolver mapping for a field."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT rm.resolver_symbol_id, rm.resolver_path, rm.resolver_line,
                   rm.binding_style, s.name
            FROM graphql_resolver_mappings rm
            LEFT JOIN symbols s ON s.symbol_id = rm.resolver_symbol_id
            WHERE rm.field_id = ?
        """,
            (field_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "symbol_id": row["resolver_symbol_id"],
            "name": row["name"],
            "file": row["resolver_path"],
            "line": row["resolver_line"],
            "binding_style": row["binding_style"],
        }

    def print_result(self, result: dict[str, Any]):
        """Pretty-print query result."""
        if "error" in result:
            logger.info(f"Error: {result['error']}")
            return

        if "types" in result:
            logger.info("\nGraphQL Types:")
            for type_data in result["types"]:
                logger.info(
                    f"  {type_data['type_name']} ({type_data['kind']}) - {type_data['field_count']} fields"
                )

        elif "fields" in result and isinstance(result["fields"], list):
            logger.info("\nFields matching query:")
            for field in result["fields"]:
                logger.info(
                    f"  {field.get('type_name', '?')}.{field['field_name']}: {field['return_type']}"
                )
                if field.get("resolver"):
                    resolver = field["resolver"]
                    logger.info(f"    → {resolver['name']} ({resolver['file']}:{resolver['line']})")

        else:
            logger.info(f"\nType: {result['type_name']} ({result['kind']})")
            logger.info(f"Fields ({len(result['fields'])}):")
            for field in result["fields"]:
                logger.info(f"  {field['field_name']}: {field['return_type']}")
                if field.get("arguments"):
                    for arg in field["arguments"]:
                        logger.info(f"    - {arg['arg_name']}: {arg['arg_type']}")
                if field.get("resolver"):
                    resolver = field["resolver"]
                    logger.info(f"    → {resolver['name']} ({resolver['binding_style']})")
