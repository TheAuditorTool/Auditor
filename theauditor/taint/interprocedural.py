"""
Temporary stub for interprocedural.py during refactor.
Interprocedural analysis is now handled by analysis.py.
"""

from typing import List, Dict, Any
import sqlite3


def trace_inter_procedural_flow_insensitive(cursor: sqlite3.Cursor, *args, **kwargs) -> List[Any]:
    """Stub for backward compatibility."""
    return []