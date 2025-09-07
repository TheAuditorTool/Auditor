"""SQL injection detection rule definitions."""

from .sql_injection_analyzer import find_sql_injection

__all__ = ['find_sql_injection']