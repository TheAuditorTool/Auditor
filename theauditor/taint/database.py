"""
Temporary stub for database.py during refactor.
Database queries are now handled by discovery.py and analysis.py.
"""

from typing import Dict, List, Any, Optional
import sqlite3


def find_taint_sources(cursor: sqlite3.Cursor, sources_dict: Optional[Dict] = None,
                       cache: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Stub for backward compatibility."""
    if cache and hasattr(cache, 'find_taint_sources_cached'):
        return cache.find_taint_sources_cached(sources_dict)
    return []


def find_security_sinks(cursor: sqlite3.Cursor, sinks_dict: Optional[Dict] = None,
                        cache: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Stub for backward compatibility."""
    if cache and hasattr(cache, 'find_security_sinks_cached'):
        return cache.find_security_sinks_cached(sinks_dict)
    return []


def build_call_graph(cursor: sqlite3.Cursor) -> Dict[str, List[str]]:
    """Stub for backward compatibility."""
    return {}


def get_containing_function(cursor: sqlite3.Cursor, node: Dict[str, Any]) -> Optional[Dict]:
    """Stub for backward compatibility."""
    return None


def filter_framework_safe_sinks(cursor: sqlite3.Cursor, sinks: List[Dict]) -> List[Dict]:
    """Stub for backward compatibility."""
    return sinks


def get_function_boundaries(cursor: sqlite3.Cursor, file_path: str, function_name: str) -> Optional[Dict]:
    """Stub for backward compatibility."""
    return {'start_line': 1, 'end_line': 1000}


def get_code_snippet(cursor: sqlite3.Cursor, file_path: str, start_line: int, end_line: int) -> str:
    """Stub for backward compatibility."""
    return ""


def check_cfg_available(cursor: sqlite3.Cursor) -> bool:
    """Stub for backward compatibility."""
    return False


def resolve_function_identity(cursor: sqlite3.Cursor, file_path: str, function_name: str) -> Optional[str]:
    """Stub for backward compatibility."""
    return function_name


def resolve_object_literal_properties(cursor: sqlite3.Cursor, *args, **kwargs) -> Dict:
    """Stub for backward compatibility."""
    return {}


def find_dynamic_dispatch_targets(cursor: sqlite3.Cursor, *args, **kwargs) -> List:
    """Stub for backward compatibility."""
    return []


def check_object_literals_available(cursor: sqlite3.Cursor) -> bool:
    """Stub for backward compatibility."""
    return False