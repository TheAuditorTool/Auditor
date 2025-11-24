"""Graph strategies for language-specific DFG construction.

This package contains strategy implementations for different languages/frameworks:
- PythonOrmStrategy: SQLAlchemy/Django ORM relationship expansion
- NodeExpressStrategy: Express middleware chains and controller resolution

Architecture:
- All strategies implement GraphStrategy base class
- Strategies are stateless and receive DB path at build time
- Returns standard dict with nodes, edges, metadata
"""

from .base import GraphStrategy

__all__ = ["GraphStrategy"]
