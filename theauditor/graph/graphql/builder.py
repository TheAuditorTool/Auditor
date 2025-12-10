"""GraphQL Builder - Correlates SDL schemas with resolver implementations."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from theauditor.utils.logging import logger


@dataclass
class GraphQLType:
    """GraphQL type metadata from SDL."""

    type_id: int
    schema_path: str
    type_name: str
    kind: str


@dataclass
class GraphQLField:
    """GraphQL field metadata from SDL."""

    field_id: int
    type_id: int
    field_name: str
    return_type: str
    is_list: bool
    is_nullable: bool


@dataclass
class ResolverCandidate:
    """Potential resolver function from symbols table."""

    name: str
    file_path: str
    line: int
    type: str
    col: int = 0


class GraphQLBuilder:
    """Correlates GraphQL schemas with resolver implementations."""

    def __init__(self, db_path: Path, verbose: bool = False):
        """Initialize builder with database connection."""
        self.db_path = db_path
        self.verbose = verbose
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

        self.types: dict[int, GraphQLType] = {}
        self.fields: dict[int, GraphQLField] = {}
        self.resolvers: list[ResolverCandidate] = []

        self.mappings: list[tuple[int, int, str, str, int, str, str]] = []
        self.edges: list[tuple[int, int, str]] = []

        self.stats = {
            "schemas_loaded": 0,
            "types_loaded": 0,
            "fields_loaded": 0,
            "resolvers_found": 0,
            "mappings_created": 0,
            "edges_created": 0,
            "missing_resolvers": 0,
        }

    def load_schemas(self) -> int:
        """Load GraphQL schemas from graphql_schemas table."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT type_id, schema_path, type_name, kind
            FROM graphql_types
            ORDER BY type_id
        """)

        for row in cursor.fetchall():
            gql_type = GraphQLType(
                type_id=row["type_id"],
                schema_path=row["schema_path"],
                type_name=row["type_name"],
                kind=row["kind"],
            )
            self.types[gql_type.type_id] = gql_type

        self.stats["types_loaded"] = len(self.types)

        cursor.execute("""
            SELECT field_id, type_id, field_name, return_type, is_list, is_nullable
            FROM graphql_fields
            ORDER BY field_id
        """)

        for row in cursor.fetchall():
            field = GraphQLField(
                field_id=row["field_id"],
                type_id=row["type_id"],
                field_name=row["field_name"],
                return_type=row["return_type"],
                is_list=bool(row["is_list"]),
                is_nullable=bool(row["is_nullable"]),
            )
            self.fields[field.field_id] = field

        self.stats["fields_loaded"] = len(self.fields)

        cursor.execute("SELECT COUNT(DISTINCT schema_path) FROM graphql_types")
        self.stats["schemas_loaded"] = cursor.fetchone()[0]

        return self.stats["schemas_loaded"]

    def load_resolver_candidates(self) -> int:
        """Load potential resolver functions from symbols table."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT name, path, line, type, col
            FROM symbols
            WHERE type IN ('function', 'method', 'async_function', 'async_method')
            ORDER BY path, name, line
        """)

        for row in cursor.fetchall():
            name = row["name"]

            is_resolver_candidate = (
                "resolve" in name.lower()
                or "resolver" in name.lower()
                or "query" in name.lower()
                or "mutation" in name.lower()
                or row["type"] in ("method", "async_method")
            )

            if is_resolver_candidate:
                candidate = ResolverCandidate(
                    name=name,
                    file_path=row["path"],
                    line=row["line"],
                    type=row["type"],
                    col=row["col"],
                )
                self.resolvers.append(candidate)

        self.stats["resolvers_found"] = len(self.resolvers)
        return self.stats["resolvers_found"]

    def correlate_resolvers(self) -> int:
        """Correlate GraphQL fields with resolver functions."""
        conn = self.conn
        cursor = conn.cursor()

        for _field_id, field in self.fields.items():
            parent_type = self.types.get(field.type_id)
            if not parent_type:
                continue

            matched_resolver = self._find_matching_resolver(parent_type, field)

            if matched_resolver:
                binding_style = self._infer_binding_style(
                    matched_resolver.name, parent_type.type_name
                )

                resolver_symbol_id = self._generate_symbol_id(
                    matched_resolver.file_path, matched_resolver.name, matched_resolver.line
                )

                mapping = (
                    field.field_id,
                    resolver_symbol_id,
                    matched_resolver.file_path,
                    matched_resolver.line,
                    self._detect_language(matched_resolver.file_path),
                    binding_style,
                    None,
                )
                self.mappings.append(mapping)

                if self.verbose:
                    logger.info(
                        f"Mapped {parent_type.type_name}.{field.field_name} → {matched_resolver.name}"
                    )
            else:
                self.stats["missing_resolvers"] += 1
                if self.verbose:
                    logger.warning(
                        f"No resolver found for {parent_type.type_name}.{field.field_name}"
                    )

        if self.mappings:
            cursor.executemany(
                """
                INSERT INTO graphql_resolver_mappings
                (field_id, resolver_symbol_id, resolver_path, resolver_line,
                 resolver_language, binding_style, resolver_export)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                self.mappings,
            )
            conn.commit()

            self._build_resolver_params(cursor)

        self.stats["mappings_created"] = len(self.mappings)
        return self.stats["mappings_created"]

    def _find_matching_resolver(
        self, parent_type: GraphQLType, field: GraphQLField
    ) -> ResolverCandidate | None:
        """Find resolver function matching a GraphQL field."""
        field_name = field.field_name
        field_name_lower = field_name.lower()

        for resolver in self.resolvers:
            if resolver.name == f"resolve_{field_name}":
                return resolver

        for resolver in self.resolvers:
            if resolver.name == field_name:
                return resolver

        for resolver in self.resolvers:
            if resolver.name == f"{field_name}Resolver":
                return resolver

        field_name_camel = field_name[0].upper() + field_name[1:] if field_name else ""
        for resolver in self.resolvers:
            if resolver.name == f"resolve{field_name_camel}":
                return resolver

        for resolver in self.resolvers:
            if field_name_lower in resolver.name.lower() and "resolve" in resolver.name.lower():
                return resolver

        return None

    def _infer_binding_style(self, resolver_name: str, type_name: str) -> str:
        """Infer GraphQL binding style from resolver name and context."""
        if resolver_name.startswith("resolve_"):
            return "graphene-method"
        elif "Resolver" in resolver_name and resolver_name.endswith("Resolver"):
            return "apollo-function"
        elif resolver_name.startswith("resolve") and resolver_name[7:8].isupper():
            return "ariadne-decorator"
        else:
            return "unknown"

    def _detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        if file_path.endswith(".py"):
            return "python"
        elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
            return "javascript"
        else:
            return "unknown"

    def _generate_symbol_id(self, file_path: str, name: str, line: int) -> int:
        """Generate synthetic symbol ID from path + name + line."""

        hash_input = f"{file_path}:{name}:{line}"
        return abs(hash(hash_input)) & 0x7FFFFFFF

    def _build_resolver_params(self, cursor):
        """Build GraphQL argument to resolver parameter mappings."""
        import json

        param_mappings = []

        for mapping in self.mappings:
            field_id = mapping[0]
            resolver_symbol_id = mapping[1]
            resolver_path = mapping[2]
            resolver_line = mapping[3]

            cursor.execute(
                """
                SELECT arg_name, arg_type
                FROM graphql_field_args
                WHERE field_id = ?
                ORDER BY arg_name
            """,
                (field_id,),
            )

            graphql_args = cursor.fetchall()
            if not graphql_args:
                continue

            cursor.execute(
                """
                SELECT parameters
                FROM symbols
                WHERE path = ? AND line = ?
                LIMIT 1
            """,
                (resolver_path, resolver_line),
            )

            result = cursor.fetchone()
            if not result or not result[0]:
                continue

            try:
                params = json.loads(result[0])
            except json.JSONDecodeError:
                continue

            framework_params = {"self", "info", "parent", "root", "context", "obj", "value"}
            func_params = [p for p in params if p not in framework_params]

            for i, (arg_name, arg_type) in enumerate(graphql_args):
                if i < len(func_params):
                    param_name = func_params[i]
                    param_index = params.index(param_name)

                    is_kwargs = param_name in ("input", "args", "kwargs", "data")
                    is_list_input = "[" in arg_type

                    param_mappings.append(
                        (
                            resolver_symbol_id,
                            arg_name,
                            param_name,
                            param_index,
                            1 if is_kwargs else 0,
                            1 if is_list_input else 0,
                        )
                    )

                    if self.verbose:
                        logger.info(
                            f"Mapped arg '{arg_name}' → param '{param_name}' (index {param_index})"
                        )

        if param_mappings:
            cursor.executemany(
                """
                INSERT INTO graphql_resolver_params
                (resolver_symbol_id, arg_name, param_name, param_index, is_kwargs, is_list_input)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                param_mappings,
            )
            self.conn.commit()

            if self.verbose:
                logger.info(f"Created {len(param_mappings)} parameter mappings")

    def build_execution_graph(self) -> int:
        """Build execution graph edges from resolvers to downstream calls."""
        cursor = self.conn.cursor()

        for mapping in self.mappings:
            field_id, symbol_id = mapping[0], mapping[1]
            edge = (field_id, symbol_id, "resolver")
            self.edges.append(edge)

        for mapping in self.mappings:
            field_id = mapping[0]
            resolver_path = mapping[2]
            resolver_line = mapping[3]

            cursor.execute(
                """
                SELECT name
                FROM symbols
                WHERE path = ? AND line = ?
                LIMIT 1
            """,
                (resolver_path, resolver_line),
            )

            resolver_row = cursor.fetchone()
            if not resolver_row:
                continue

            resolver_name = resolver_row[0]

            cursor.execute(
                """
                SELECT DISTINCT callee_function
                FROM function_call_args
                WHERE caller_function = ?
                  AND file = ?
            """,
                (resolver_name, resolver_path),
            )

            for row in cursor.fetchall():
                callee = row[0]

                cursor.execute(
                    """
                    SELECT path, name, line
                    FROM symbols
                    WHERE name = ? AND path = ?
                    LIMIT 1
                """,
                    (callee, resolver_path),
                )

                callee_row = cursor.fetchone()
                if callee_row:
                    callee_path, callee_name, callee_line = callee_row
                    callee_symbol_id = self._generate_symbol_id(
                        callee_path, callee_name, callee_line
                    )
                    edge = (field_id, callee_symbol_id, "downstream_call")
                    self.edges.append(edge)

        if self.edges:
            cursor.executemany(
                """
                INSERT OR IGNORE INTO graphql_execution_edges
                (from_field_id, to_symbol_id, edge_kind)
                VALUES (?, ?, ?)
            """,
                self.edges,
            )
            self.conn.commit()

        self.stats["edges_created"] = len(self.edges)
        return self.stats["edges_created"]

    def get_coverage_percent(self) -> float:
        """Calculate resolver coverage percentage."""
        total_fields = self.stats["fields_loaded"]
        if total_fields == 0:
            return 0.0
        mapped = self.stats["mappings_created"]
        return (mapped / total_fields) * 100.0

    def get_missing_count(self) -> int:
        """Get count of fields without resolvers."""
        return self.stats["missing_resolvers"]

    def print_summary(self):
        """Print detailed summary statistics."""
        logger.info("\n=== GraphQL Build Summary ===")
        logger.info(f"Schemas loaded:      {self.stats['schemas_loaded']}")
        logger.info(f"Types loaded:        {self.stats['types_loaded']}")
        logger.info(f"Fields loaded:       {self.stats['fields_loaded']}")
        logger.info(f"Resolver candidates: {self.stats['resolvers_found']}")
        logger.info(f"Mappings created:    {self.stats['mappings_created']}")
        logger.info(f"Execution edges:     {self.stats['edges_created']}")
        logger.info(f"Coverage:            {self.get_coverage_percent():.1f}%")
        logger.info(f"Missing resolvers:   {self.stats['missing_resolvers']}")


    def _export_schema_data(self) -> dict:
        """Export GraphQL schema data with provenance."""
        cursor = self.conn.cursor()

        types_data = []
        for type_id, gql_type in self.types.items():
            cursor.execute(
                """
                SELECT field_id, field_name, return_type, is_list, is_nullable, directives_json, line
                FROM graphql_fields
                WHERE type_id = ?
                ORDER BY field_name
            """,
                (type_id,),
            )

            fields = []
            for row in cursor.fetchall():
                field = {
                    "field_name": row[1],
                    "return_type": row[2],
                    "is_list": bool(row[3]),
                    "is_nullable": bool(row[4]),
                    "directives": json.loads(row[5]) if row[5] else [],
                    "line": row[6],
                    "provenance": {"table": "graphql_fields", "field_id": row[0]},
                }

                cursor.execute(
                    """
                    SELECT arg_name, arg_type, has_default, default_value, is_nullable
                    FROM graphql_field_args
                    WHERE field_id = ?
                    ORDER BY arg_name
                """,
                    (row[0],),
                )

                args = []
                for arg_row in cursor.fetchall():
                    args.append(
                        {
                            "arg_name": arg_row[0],
                            "arg_type": arg_row[1],
                            "has_default": bool(arg_row[2]),
                            "default_value": arg_row[3],
                            "is_nullable": bool(arg_row[4]),
                        }
                    )

                if args:
                    field["arguments"] = args

                fields.append(field)

            type_entry = {
                "type_name": gql_type.type_name,
                "kind": gql_type.kind,
                "schema_path": gql_type.schema_path,
                "fields": fields,
                "provenance": {"table": "graphql_types", "type_id": type_id},
            }
            types_data.append(type_entry)

        return {
            "metadata": {
                "generated_by": "aud graphql build",
                "total_types": len(types_data),
                "total_fields": self.stats["fields_loaded"],
            },
            "types": types_data,
        }

    def _export_execution_data(self) -> dict:
        """Export execution graph data with provenance."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                rm.field_id,
                rm.resolver_symbol_id,
                rm.resolver_path,
                rm.resolver_line,
                rm.resolver_language,
                rm.binding_style,
                f.field_name,
                t.type_name
            FROM graphql_resolver_mappings rm
            JOIN graphql_fields f ON f.field_id = rm.field_id
            JOIN graphql_types t ON t.type_id = f.type_id
            ORDER BY t.type_name, f.field_name
        """)

        mappings = []
        for row in cursor.fetchall():
            mapping = {
                "field": f"{row[7]}.{row[6]}",
                "resolver": {
                    "path": row[2],
                    "line": row[3],
                    "language": row[4],
                    "binding_style": row[5],
                },
                "provenance": {
                    "table": "graphql_resolver_mappings",
                    "field_id": row[0],
                    "resolver_symbol_id": row[1],
                },
            }
            mappings.append(mapping)

        cursor.execute("""
            SELECT
                from_field_id,
                to_symbol_id,
                edge_kind
            FROM graphql_execution_edges
            ORDER BY from_field_id, edge_kind
        """)

        edges = []
        for row in cursor.fetchall():
            edge = {
                "from_field_id": row[0],
                "to_symbol_id": row[1],
                "edge_kind": row[2],
                "provenance": {"table": "graphql_execution_edges"},
            }
            edges.append(edge)

        return {
            "metadata": {
                "generated_by": "aud graphql build",
                "total_mappings": len(mappings),
                "total_edges": len(edges),
                "coverage_percent": self.get_coverage_percent(),
            },
            "resolver_mappings": mappings,
            "execution_edges": edges,
        }
