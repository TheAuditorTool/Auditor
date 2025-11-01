"""
Temporary stub for config.py during refactor.
Configuration is now handled directly in core.py.
"""

from typing import Dict, List


class TaintConfig:
    """Minimal taint configuration for backward compatibility."""

    def __init__(self):
        self.sources = {}
        self.sinks = {}
        self.sanitizers = {}

    @classmethod
    def from_defaults(cls):
        """Create config with default patterns."""
        config = cls()
        config.sources = {
            'http_request': [],
            'file_read': [],
            'environment': [],
            'database': []
        }
        config.sinks = {
            'sql': [],
            'command': [],
            'xss': [],
            'path': [],
            'ldap': [],
            'nosql': []
        }
        return config

    def with_registry(self, registry):
        """Merge with registry patterns."""
        # Just return self for now
        return self