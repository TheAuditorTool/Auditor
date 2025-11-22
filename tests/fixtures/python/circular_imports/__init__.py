"""
Circular Imports Package

This package intentionally contains circular import dependencies to test
that TheAuditor's import resolution handles them correctly without:
- Infinite loops during indexing
- Crashing the indexer
- Missing symbols due to import failures

Circular dependency structure:
- models.py ↔ services.py (bidirectional)
- controllers.py imports both (triangle)
- utils.py imports controllers (4-way chain)
"""

# Note: We don't import anything here to avoid triggering circular imports at package level
# Each module handles its own imports with appropriate guards

__all__ = ["models", "services", "controllers", "utils"]
