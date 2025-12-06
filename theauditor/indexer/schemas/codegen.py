"""Schema-driven code generation for taint analysis."""

import hashlib
from pathlib import Path

from theauditor.utils.logging import logger

from ..schema import TABLES


class SchemaCodeGenerator:
    """Generates code from schema definitions."""

    @staticmethod
    def get_schema_hash() -> str:
        """Get a SHA256 hash of all schema files to detect changes."""
        hasher = hashlib.sha256()

        schemas_dir = Path(__file__).parent

        schema_files = [
            schemas_dir.parent / "schema.py",
            schemas_dir / "core_schema.py",
            schemas_dir / "security_schema.py",
            schemas_dir / "frameworks_schema.py",
            schemas_dir / "python_schema.py",
            schemas_dir / "node_schema.py",
            schemas_dir / "rust_schema.py",
            schemas_dir / "go_schema.py",
            schemas_dir / "bash_schema.py",
            schemas_dir / "infrastructure_schema.py",
            schemas_dir / "planning_schema.py",
            schemas_dir / "graphql_schema.py",
            schemas_dir / "utils.py",
            Path(__file__),
        ]

        for schema_file in sorted(schema_files):
            if schema_file.exists():
                hasher.update(schema_file.name.encode())
                hasher.update(schema_file.read_bytes())

        return hasher.hexdigest()

    @staticmethod
    def _to_pascal_case(snake_str: str) -> str:
        """Convert snake_case to PascalCase."""
        return "".join(word.capitalize() for word in snake_str.split("_"))

    @staticmethod
    def _python_type(sql_type: str) -> str:
        """Convert SQL type to Python type hint."""
        sql_type = sql_type.upper()
        if "INT" in sql_type:
            return "int"
        elif "TEXT" in sql_type or "VARCHAR" in sql_type:
            return "str"
        elif "REAL" in sql_type or "FLOAT" in sql_type or "DOUBLE" in sql_type:
            return "float"
        elif "BLOB" in sql_type:
            return "bytes"
        elif "BOOLEAN" in sql_type or "BOOL" in sql_type:
            return "bool"
        else:
            return "Any"

    @classmethod
    def generate_typed_dicts(cls) -> str:
        """Generate TypedDict for each table."""
        code = []
        code.append("# Auto-generated TypedDict definitions from schema")
        code.append("from typing import Any, TypedDict")
        code.append("")
        code.append("")
        for table_name, schema in sorted(TABLES.items()):
            class_name = f"{cls._to_pascal_case(table_name)}Row"
            code.append(f"class {class_name}(TypedDict):")
            code.append(f'    """Row type for {table_name} table."""')

            for col in schema.columns:
                field_type = cls._python_type(col.type)
                if col.nullable and not col.primary_key:
                    field_type = f"{field_type} | None"
                code.append(f"    {col.name}: {field_type}")

            code.append("")

        return "\n".join(code)

    @classmethod
    def generate_accessor_classes(cls) -> str:
        """Generate accessor class for each table."""
        code = []
        code.append("# Auto-generated accessor classes from schema")
        code.append("import sqlite3")
        code.append("from typing import Any")
        code.append("")
        code.append("from ..schema import build_query")
        code.append("")
        code.append("")
        for table_name, schema in sorted(TABLES.items()):
            class_name = f"{cls._to_pascal_case(table_name)}Table"

            code.append(f"class {class_name}:")
            code.append(f'    """Accessor class for {table_name} table."""')
            code.append("")

            col_names = [col.name for col in schema.columns]
            col_list_str = str(col_names)
            code.append("    @staticmethod")
            code.append("    def get_all(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:")
            code.append(f'        """Get all rows from {table_name}."""')
            code.append(f"        query = build_query('{table_name}', {col_list_str})")
            code.append("        cursor.execute(query)")
            code.append(
                f"        return [dict(zip({col_list_str}, row, strict=True)) for row in cursor.fetchall()]"
            )
            code.append("")

            for idx_def in schema.indexes:
                _idx_name, idx_cols = idx_def[0], idx_def[1]
                if len(idx_cols) == 1:
                    col_name = idx_cols[0]

                    col_def = next((c for c in schema.columns if c.name == col_name), None)
                    if col_def:
                        param_type = cls._python_type(col_def.type)
                        code.append("    @staticmethod")
                        code.append(
                            f"    def get_by_{col_name}(cursor: sqlite3.Cursor, {col_name}: {param_type}) -> list[dict[str, Any]]:"
                        )
                        code.append(f'        """Get rows by {col_name}."""')
                        code.append(
                            f"        query = build_query('{table_name}', {col_list_str}, where=\"{col_name} = ?\")"
                        )
                        code.append(f"        cursor.execute(query, ({col_name},))")
                        code.append(
                            f"        return [dict(zip({col_list_str}, row, strict=True)) for row in cursor.fetchall()]"
                        )
                        code.append("")

            code.append("")

        return "\n".join(code)

    @classmethod
    def generate_memory_cache(cls) -> str:
        """Generate SchemaMemoryCache class."""
        code = []

        schema_hash = cls.get_schema_hash()
        code.append("# AUTO-GENERATED FILE - DO NOT EDIT")
        code.append(f"# SCHEMA_HASH: {schema_hash}")
        code.append("import sqlite3")
        code.append("from collections import defaultdict")
        code.append("from typing import Any")
        code.append("")
        code.append("from ..schema import TABLES, build_query")
        code.append("")
        code.append("")
        code.append("class SchemaMemoryCache:")
        code.append('    """Auto-generated memory cache that loads ALL tables."""')
        code.append("")
        code.append("    def __init__(self, db_path: str):")
        code.append('        """Initialize cache by loading all tables from database."""')
        code.append("        self.db_path = db_path")
        code.append("        conn = sqlite3.connect(db_path)")
        code.append("        cursor = conn.cursor()")
        code.append("")
        code.append("        # Get list of existing tables in database")
        code.append("        cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")")
        code.append("        existing_tables = {row[0] for row in cursor.fetchall()}")
        code.append("")
        code.append("        # Auto-load ALL tables that exist")
        code.append("        for table_name, schema in TABLES.items():")
        code.append("            if table_name in existing_tables:")
        code.append("                data = self._load_table(cursor, table_name, schema)")
        code.append("            else:")
        code.append("                # Table doesn't exist yet, use empty list")
        code.append("                data = []")
        code.append("            setattr(self, table_name, data)")
        code.append("")
        code.append(
            "            # Auto-build indexes for indexed columns (always create, even if empty)"
        )
        code.append("            for idx_def in schema.indexes:")
        code.append(
            "                _idx_name, idx_cols = idx_def[0], idx_def[1]  # Handle 2 or 3 element tuples"
        )
        code.append("                if len(idx_cols) == 1:  # Single column index")
        code.append("                    col_name = idx_cols[0]")
        code.append(
            "                    index = self._build_index(data, table_name, col_name, schema)"
        )
        code.append('                    setattr(self, f"{table_name}_by_{col_name}", index)')
        code.append("")
        code.append("        conn.close()")
        code.append("")
        code.append(
            "    def _load_table(self, cursor: sqlite3.Cursor, table_name: str, schema: Any) -> list[dict[str, Any]]:"
        )
        code.append('        """Load a table into memory as list of dicts."""')
        code.append("        col_names = [col.name for col in schema.columns]")
        code.append("        query = build_query(table_name, col_names)")
        code.append("        cursor.execute(query)")
        code.append("        rows = cursor.fetchall()")
        code.append("        return [dict(zip(col_names, row, strict=True)) for row in rows]")
        code.append("")
        code.append(
            "    def _build_index(self, data: list[dict[str, Any]], table_name: str, col_name: str, schema: Any) -> dict[Any, list[dict[str, Any]]]:"
        )
        code.append('        """Build an index on a column for fast lookups."""')
        code.append("        index = defaultdict(list)")
        code.append("        for row in data:")
        code.append("            key = row.get(col_name)")
        code.append("            if key is not None:")
        code.append("                index[key].append(row)")
        code.append("        return dict(index)")
        code.append("")
        code.append("    def get_table_size(self, table_name: str) -> int:")
        code.append('        """Get the number of rows in a table."""')
        code.append("        if hasattr(self, table_name):")
        code.append("            return len(getattr(self, table_name))")
        code.append("        return 0")
        code.append("")
        code.append("    def get_cache_stats(self) -> dict[str, int]:")
        code.append('        """Get statistics about cached data."""')
        code.append("        stats = {}")
        code.append("        for table_name in TABLES:")
        code.append("            stats[table_name] = self.get_table_size(table_name)")
        code.append("        return stats")
        code.append("")
        code.append("    def get_memory_usage_mb(self) -> float:")
        code.append('        """Estimate memory usage of the cache in MB."""')
        code.append("        import sys")
        code.append("        total_bytes = 0")
        code.append("        for _attr, value in self.__dict__.items():")
        code.append("            total_bytes += sys.getsizeof(value)")
        code.append("            if isinstance(value, list):")
        code.append("                total_bytes += sum(sys.getsizeof(i) for i in value)")
        code.append("            elif isinstance(value, dict):")
        code.append(
            "                total_bytes += sum(sys.getsizeof(k) + sys.getsizeof(v) for k, v in value.items())"
        )
        code.append("        return total_bytes / (1024 * 1024)")
        code.append("")

        return "\n".join(code)

    @classmethod
    def generate_validators(cls) -> str:
        """Generate validation decorators for storage methods."""
        code = []
        code.append("# Auto-generated validators from schema")
        code.append("from collections.abc import Callable")
        code.append("from functools import wraps")
        code.append("from typing import Any")
        code.append("")
        code.append("from ..schema import TABLES")
        code.append("from .codegen import SchemaCodeGenerator")
        code.append("")
        code.append("")
        code.append("def validate_storage(table_name: str):")
        code.append('    """Decorator to validate data before storage."""')
        code.append("    def decorator(func: Callable) -> Callable:")
        code.append("        @wraps(func)")
        code.append("        def wrapper(*args, **kwargs) -> Any:")
        code.append("            # Get the table schema")
        code.append("            if table_name not in TABLES:")
        code.append("                raise ValueError(f'Unknown table: {table_name}')")
        code.append("")
        code.append("            schema = TABLES[table_name]")
        code.append(
            "            required_cols = {col.name for col in schema.columns if not col.nullable}"
        )
        code.append("")
        code.append("            # Validate that required columns are present in kwargs")
        code.append("            for col_name in required_cols:")
        code.append("                if col_name not in kwargs:")
        code.append(
            "                    raise ValueError(f'Missing required column {col_name} for table {table_name}')"
        )
        code.append("")
        code.append("            return func(*args, **kwargs)")
        code.append("        return wrapper")
        code.append("    return decorator")
        code.append("")
        code.append("")
        code.append("def validate_column_types(table_name: str, data: dict[str, Any]) -> None:")
        code.append('    """Validate column types match schema."""')
        code.append("    if table_name not in TABLES:")
        code.append("        raise ValueError(f'Unknown table: {table_name}')")
        code.append("")
        code.append("    schema = TABLES[table_name]")
        code.append("    for col in schema.columns:")
        code.append("        if col.name in data:")
        code.append("            value = data[col.name]")
        code.append("            if value is not None:")
        code.append("                # Basic type checking")
        code.append("                expected_type = SchemaCodeGenerator._python_type(col.type)")
        code.append("                if expected_type == 'int' and not isinstance(value, int):")
        code.append(
            "                    raise TypeError(f'Column {col.name} expects int, got {type(value).__name__}')"
        )
        code.append("                elif expected_type == 'str' and not isinstance(value, str):")
        code.append(
            "                    raise TypeError(f'Column {col.name} expects str, got {type(value).__name__}')"
        )
        code.append(
            "                elif expected_type == 'float' and not isinstance(value, (int, float)):"
        )
        code.append(
            "                    raise TypeError(f'Column {col.name} expects float, got {type(value).__name__}')"
        )
        code.append("                elif expected_type == 'bool' and not isinstance(value, bool):")
        code.append(
            "                    raise TypeError(f'Column {col.name} expects bool, got {type(value).__name__}')"
        )
        code.append("")

        return "\n".join(code)

    @classmethod
    def generate_all(cls) -> dict[str, str]:
        """Generate all code components."""
        return {
            "typed_dicts": cls.generate_typed_dicts(),
            "accessors": cls.generate_accessor_classes(),
            "memory_cache": cls.generate_memory_cache(),
            "validators": cls.generate_validators(),
        }

    @classmethod
    def write_generated_code(cls, output_dir: str = None) -> None:
        """Write generated code to files."""
        output_dir = Path(__file__).parent if output_dir is None else Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        components = cls.generate_all()

        typed_dicts_path = output_dir / "generated_types.py"
        with open(typed_dicts_path, "w") as f:
            f.write(components["typed_dicts"])

        accessors_path = output_dir / "generated_accessors.py"
        with open(accessors_path, "w") as f:
            f.write(components["accessors"])

        cache_path = output_dir / "generated_cache.py"
        with open(cache_path, "w") as f:
            f.write(components["memory_cache"])

        validators_path = output_dir / "generated_validators.py"
        with open(validators_path, "w") as f:
            f.write(components["validators"])

        logger.info(f"Generated code written to {output_dir}")


def generate_complete_module() -> str:
    """Generate a complete module with all components."""
    code = []
    code.append('"""')
    code.append("Auto-generated schema code.")
    code.append("DO NOT EDIT MANUALLY - Generated by SchemaCodeGenerator")
    code.append('"""')
    code.append("")

    components = SchemaCodeGenerator.generate_all()

    code.append(components["typed_dicts"])
    code.append("\n\n")
    code.append(components["accessors"])
    code.append("\n\n")
    code.append(components["memory_cache"])
    code.append("\n\n")
    code.append(components["validators"])

    return "\n".join(code)
