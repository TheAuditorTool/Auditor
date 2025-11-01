"""
Temporary stub for registry.py during refactor.
Registry functionality is now integrated into discovery.py.
"""

from typing import Dict, List, Any


class TaintRegistry:
    """Minimal registry for backward compatibility."""

    def __init__(self):
        self.sources = {}
        self.sinks = {}
        self.sanitizers = {}

    def is_sanitizer(self, function_name: str) -> bool:
        """Check if a function is a sanitizer."""
        return False

    def register_source(self, pattern: str, category: str):
        """Register a taint source pattern."""
        pass

    def register_sink(self, pattern: str, category: str):
        """Register a security sink pattern."""
        pass

    def register_sanitizer(self, function: str, types: List[str]):
        """Register a sanitizer function."""
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about registered patterns."""
        return {
            'sources': len(self.sources),
            'sinks': len(self.sinks),
            'sanitizers': len(self.sanitizers),
            'total': len(self.sources) + len(self.sinks) + len(self.sanitizers),
            'total_sources': len(self.sources),
            'total_sinks': len(self.sinks),
            'total_sanitizers': len(self.sanitizers)
        }