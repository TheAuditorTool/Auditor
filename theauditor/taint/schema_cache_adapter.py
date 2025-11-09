"""
Adapter to make SchemaMemoryCache compatible with existing MemoryCache interface.

This is a Phase 2 temporary adapter that allows SchemaMemoryCache to work
with the existing taint code that expects the old MemoryCache interface.
This will be removed in Phase 4 when we refactor the taint code directly.
"""

from typing import Dict, List, Any, Optional
import sys


class SchemaMemoryCacheAdapter:
    """Adapter to make SchemaMemoryCache work with existing taint code."""

    def __init__(self, schema_cache):
        """Initialize with a SchemaMemoryCache instance."""
        self._cache = schema_cache
        # Map old attribute names to new ones for compatibility
        self._setup_compatibility_attributes()

    def _setup_compatibility_attributes(self):
        """Setup attributes expected by old code."""
        # Direct pass-through of table data
        if hasattr(self._cache, 'symbols'):
            self.symbols = self._cache.symbols
        if hasattr(self._cache, 'assignments'):
            self.assignments = self._cache.assignments
        if hasattr(self._cache, 'function_call_args'):
            self.function_call_args = self._cache.function_call_args
        if hasattr(self._cache, 'cfg_blocks'):
            self.cfg_blocks = self._cache.cfg_blocks
        if hasattr(self._cache, 'cfg_edges'):
            self.cfg_edges = self._cache.cfg_edges
        if hasattr(self._cache, 'python_orm_models'):
            self.python_orm_models = self._cache.python_orm_models
        if hasattr(self._cache, 'python_orm_fields'):
            self.python_orm_fields = self._cache.python_orm_fields
        if hasattr(self._cache, 'orm_relationships'):
            self.orm_relationships = self._cache.orm_relationships
        if hasattr(self._cache, 'api_endpoints'):
            self.api_endpoints = self._cache.api_endpoints
        if hasattr(self._cache, 'sql_queries'):
            self.sql_queries = self._cache.sql_queries
        if hasattr(self._cache, 'nosql_queries'):
            self.nosql_queries = self._cache.nosql_queries
        if hasattr(self._cache, 'react_hooks'):
            self.react_hooks = self._cache.react_hooks
        if hasattr(self._cache, 'object_literals'):
            self.object_literals = self._cache.object_literals

        # Indexed attributes
        if hasattr(self._cache, 'symbols_by_path'):
            self.symbols_by_file = self._cache.symbols_by_path
        if hasattr(self._cache, 'assignments_by_file'):
            self.assignments_by_file = self._cache.assignments_by_file
        if hasattr(self._cache, 'function_call_args_by_file'):
            self.function_call_args_by_file = self._cache.function_call_args_by_file

    def get_memory_usage_mb(self) -> float:
        """Get memory usage in MB."""
        # Estimate based on number of loaded rows
        stats = self._cache.get_cache_stats()
        total_rows = sum(stats.values())
        # Rough estimate: 1KB per row average
        return (total_rows * 1024) / (1024 * 1024)

    def find_taint_sources_cached(self, sources_dict: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """Find taint sources using cache - adapter method."""
        sources = []

        # If no patterns specified, return all potential sources
        if not sources_dict:
            # Return all API endpoints as potential sources
            if hasattr(self._cache, 'api_endpoints'):
                for endpoint in self._cache.api_endpoints:
                    sources.append({
                        'name': endpoint.get('handler_function', 'unknown'),
                        'file': endpoint.get('file', ''),
                        'line': endpoint.get('line', 0),
                        'pattern': f"{endpoint.get('method', 'GET')} {endpoint.get('path', '/')}",
                        'category': 'http_request',
                        'metadata': endpoint
                    })
            return sources

        # Search for patterns in the cached data
        for category, patterns in sources_dict.items():
            for pattern in patterns:
                # Check symbols for matching patterns
                if hasattr(self._cache, 'symbols'):
                    for symbol in self._cache.symbols:
                        if pattern in symbol.get('name', ''):
                            sources.append({
                                'name': symbol.get('name', ''),
                                'file': symbol.get('path', ''),
                                'line': symbol.get('line', 0),
                                'pattern': pattern,
                                'category': category,
                                'metadata': symbol
                            })

                # Check API endpoints
                if category == 'http_request' and hasattr(self._cache, 'api_endpoints'):
                    for endpoint in self._cache.api_endpoints:
                        sources.append({
                            'name': endpoint.get('handler_function', 'unknown'),
                            'file': endpoint.get('file', ''),
                            'line': endpoint.get('line', 0),
                            'pattern': pattern,
                            'category': category,
                            'metadata': endpoint
                        })

        return sources

    def find_security_sinks_cached(self, sinks_dict: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """Find security sinks using cache - adapter method.

        ZERO FALLBACK POLICY: Use sinks_dict from TaintRegistry, no hardcoded patterns.
        This adapter is temporary (will be removed in Phase 4).
        """
        sinks = []

        # SQL sinks from sql_queries table (database-driven)
        if hasattr(self._cache, 'sql_queries'):
            for query in self._cache.sql_queries:
                sinks.append({
                    'name': 'sql_query',
                    'file': query.get('file_path', ''),
                    'line': query.get('line_number', 0),
                    'pattern': query.get('query_text', ''),
                    'category': 'sql',
                    'metadata': query
                })

        # NoSQL sinks (database-driven)
        if hasattr(self._cache, 'nosql_queries'):
            for query in self._cache.nosql_queries:
                sinks.append({
                    'name': 'nosql_query',
                    'file': query.get('file', ''),
                    'line': query.get('line', 0),
                    'pattern': query.get('operation', ''),
                    'category': 'nosql',
                    'metadata': query
                })

        # ZERO FALLBACK: If sinks_dict provided, use patterns from TaintRegistry
        # Otherwise return only database sinks (sql_queries, nosql_queries)
        if not sinks_dict:
            return sinks

        # Command execution sinks from registry patterns
        cmd_patterns = sinks_dict.get('command', [])
        if cmd_patterns and hasattr(self._cache, 'function_call_args'):
            for call in self._cache.function_call_args:
                func_name = call.get('callee_function', '')
                if any(pattern in func_name for pattern in cmd_patterns):
                    sinks.append({
                        'name': func_name,
                        'file': call.get('file', ''),
                        'line': call.get('line', 0),
                        'pattern': func_name,
                        'category': 'command',
                        'metadata': call
                    })

        # XSS sinks from registry patterns
        xss_patterns = sinks_dict.get('xss', [])
        if xss_patterns and hasattr(self._cache, 'react_hooks'):
            for hook in self._cache.react_hooks:
                hook_str = str(hook)
                for pattern in xss_patterns:
                    if pattern in hook_str:
                        sinks.append({
                            'name': 'react_dangerous_html',
                            'file': hook.get('file', ''),
                            'line': hook.get('line', 0),
                            'pattern': pattern,
                            'category': 'xss',
                            'metadata': hook
                        })
                        break  # Only add once per hook

        return sinks

    def __getattr__(self, name):
        """Forward any other attribute access to the underlying cache."""
        return getattr(self._cache, name)