# Auto-generated validators from schema
from collections.abc import Callable
from functools import wraps
from typing import Any

from ..schema import TABLES
from .codegen import SchemaCodeGenerator


def validate_storage(table_name: str):
    """Decorator to validate data before storage."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Get the table schema
            if table_name not in TABLES:
                raise ValueError(f'Unknown table: {table_name}')

            schema = TABLES[table_name]
            required_cols = {col.name for col in schema.columns if not col.nullable}

            # Validate that required columns are present in kwargs
            for col_name in required_cols:
                if col_name not in kwargs:
                    raise ValueError(f'Missing required column {col_name} for table {table_name}')

            return func(*args, **kwargs)
        return wrapper
    return decorator


def validate_column_types(table_name: str, data: dict[str, Any]) -> None:
    """Validate column types match schema."""
    if table_name not in TABLES:
        raise ValueError(f'Unknown table: {table_name}')

    schema = TABLES[table_name]
    for col in schema.columns:
        if col.name in data:
            value = data[col.name]
            if value is not None:
                # Basic type checking
                expected_type = SchemaCodeGenerator._python_type(col.type)
                if expected_type == 'int' and not isinstance(value, int):
                    raise TypeError(f'Column {col.name} expects int, got {type(value).__name__}')
                elif expected_type == 'str' and not isinstance(value, str):
                    raise TypeError(f'Column {col.name} expects str, got {type(value).__name__}')
                elif expected_type == 'float' and not isinstance(value, (int, float)):
                    raise TypeError(f'Column {col.name} expects float, got {type(value).__name__}')
                elif expected_type == 'bool' and not isinstance(value, bool):
                    raise TypeError(f'Column {col.name} expects bool, got {type(value).__name__}')
