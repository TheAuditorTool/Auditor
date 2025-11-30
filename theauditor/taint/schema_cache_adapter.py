"""Adapter to make SchemaMemoryCache compatible with existing MemoryCache interface."""


class SchemaMemoryCacheAdapter:
    """Adapter to make SchemaMemoryCache work with existing taint code.

    This adapter provides compatibility layer between the new SchemaMemoryCache
    and legacy code that expects specific attribute names.

    NOTE: Discovery logic lives in discovery.py (TaintDiscovery class).
    This adapter ONLY handles attribute mapping - no business logic.
    """

    def __init__(self, schema_cache):
        """Initialize with a SchemaMemoryCache instance."""
        self._cache = schema_cache

        self._setup_compatibility_attributes()

    def _setup_compatibility_attributes(self):
        """Setup attributes expected by old code."""

        if hasattr(self._cache, "symbols"):
            self.symbols = self._cache.symbols
        if hasattr(self._cache, "assignments"):
            self.assignments = self._cache.assignments
        if hasattr(self._cache, "function_call_args"):
            self.function_call_args = self._cache.function_call_args
        if hasattr(self._cache, "cfg_blocks"):
            self.cfg_blocks = self._cache.cfg_blocks
        if hasattr(self._cache, "cfg_edges"):
            self.cfg_edges = self._cache.cfg_edges
        if hasattr(self._cache, "python_orm_models"):
            self.python_orm_models = self._cache.python_orm_models
        if hasattr(self._cache, "python_orm_fields"):
            self.python_orm_fields = self._cache.python_orm_fields
        if hasattr(self._cache, "orm_relationships"):
            self.orm_relationships = self._cache.orm_relationships
        if hasattr(self._cache, "api_endpoints"):
            self.api_endpoints = self._cache.api_endpoints
        if hasattr(self._cache, "sql_queries"):
            self.sql_queries = self._cache.sql_queries
        if hasattr(self._cache, "nosql_queries"):
            self.nosql_queries = self._cache.nosql_queries
        if hasattr(self._cache, "react_hooks"):
            self.react_hooks = self._cache.react_hooks
        if hasattr(self._cache, "object_literals"):
            self.object_literals = self._cache.object_literals

        if hasattr(self._cache, "variable_usage"):
            self.variable_usage = self._cache.variable_usage
        if hasattr(self._cache, "env_var_usage"):
            self.env_var_usage = self._cache.env_var_usage
        if hasattr(self._cache, "express_middleware_chains"):
            self.express_middleware_chains = self._cache.express_middleware_chains
        if hasattr(self._cache, "import_styles"):
            self.import_styles = self._cache.import_styles

        if hasattr(self._cache, "symbols_by_path"):
            self.symbols_by_file = self._cache.symbols_by_path
        if hasattr(self._cache, "assignments_by_file"):
            self.assignments_by_file = self._cache.assignments_by_file
        if hasattr(self._cache, "function_call_args_by_file"):
            self.function_call_args_by_file = self._cache.function_call_args_by_file

    def get_memory_usage_mb(self) -> float:
        """Get memory usage in MB."""

        stats = self._cache.get_cache_stats()
        total_rows = sum(stats.values())

        return (total_rows * 1024) / (1024 * 1024)

    def __getattr__(self, name):
        """Forward any other attribute access to the underlying cache."""
        return getattr(self._cache, name)
