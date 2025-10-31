"""Database operations for the indexer.

This module contains the DatabaseManager class which handles all database
operations including schema creation, batch inserts, and transaction management.

ARCHITECTURE: Schema-Driven Database Layer
- schema.py is the Single Source of Truth for all table definitions
- This module consumes schema.py TABLES registry to generate SQL dynamically
- NO hardcoded CREATE TABLE or INSERT statements (except CFG special case)
- Generic batching system replaces 58 individual batch lists

CRITICAL ARCHITECTURE RULE: NO FALLBACKS ALLOWED.
The database is generated fresh every run. It MUST exist and MUST be correct.
NO graceful degradation, NO try/except around schema operations, NO migrations.
Hard failure is the only acceptable behavior for missing data or schema errors.

REFACTORED ARCHITECTURE:
- BaseDatabaseManager: Core infrastructure (transactions, schema, batching)
- CoreDatabaseMixin: Language-agnostic core methods (files, symbols, CFG, JSX)
- PythonDatabaseMixin: Python-specific methods (ORM, routes, decorators, etc.)
- NodeDatabaseMixin: Node.js/TypeScript/React/Vue methods
- InfrastructureDatabaseMixin: Docker, Terraform, CDK, GitHub Actions
- SecurityDatabaseMixin: SQL injection, JWT, env vars
- FrameworksDatabaseMixin: API endpoints, ORM, Prisma
- PlanningDatabaseMixin: Planning system (stub for future iteration)
- GraphQLDatabaseMixin: GraphQL schemas, types, fields, resolvers, execution graph

DatabaseManager uses multiple inheritance to combine all capabilities.
"""

import sqlite3
from collections import defaultdict
from typing import Optional

from .base_database import BaseDatabaseManager
from .core_database import CoreDatabaseMixin
from .python_database import PythonDatabaseMixin
from .node_database import NodeDatabaseMixin
from .infrastructure_database import InfrastructureDatabaseMixin
from .security_database import SecurityDatabaseMixin
from .frameworks_database import FrameworksDatabaseMixin
from .planning_database import PlanningDatabaseMixin
from .graphql_database import GraphQLDatabaseMixin


class DatabaseManager(
    BaseDatabaseManager,
    CoreDatabaseMixin,
    PythonDatabaseMixin,
    NodeDatabaseMixin,
    InfrastructureDatabaseMixin,
    SecurityDatabaseMixin,
    FrameworksDatabaseMixin,
    PlanningDatabaseMixin,
    GraphQLDatabaseMixin
):
    """Complete database manager combining all language-specific capabilities.

    This class uses multiple inheritance to combine:
    - BaseDatabaseManager: Core infrastructure (schema, transactions, batching)
    - 8 Mixin classes: Language-specific and domain-specific add_* methods

    Method Resolution Order (MRO):
    1. DatabaseManager (this class)
    2. BaseDatabaseManager (core infrastructure)
    3. CoreDatabaseMixin (21 core tables, 16 methods)
    4. PythonDatabaseMixin (34 Python tables, 34 methods)
    5. NodeDatabaseMixin (17 Node tables, 14 methods)
    6. InfrastructureDatabaseMixin (18 infrastructure tables, 18 methods)
    7. SecurityDatabaseMixin (5 security tables, 4 methods)
    8. FrameworksDatabaseMixin (5 framework tables, 4 methods)
    9. PlanningDatabaseMixin (5 planning tables, 0 methods - stub)
    10. GraphQLDatabaseMixin (8 GraphQL tables, 7 methods)

    Total: 116 tables, 97 methods
    """
    pass


# Standalone function for backward compatibility
def create_database_schema(conn: sqlite3.Connection) -> None:
    """Create SQLite database schema - backward compatibility wrapper.

    This function exists for backward compatibility with code that expects
    to create schema without instantiating a DatabaseManager.

    Args:
        conn: SQLite connection (remains open after schema creation)
    """
    # Create temporary manager using existing connection
    manager = DatabaseManager.__new__(DatabaseManager)
    manager.conn = conn
    manager.cursor = conn.cursor()
    manager.batch_size = 200

    # Initialize generic batch system
    manager.generic_batches = defaultdict(list)
    manager.cfg_id_mapping = {}
    manager.jwt_patterns_batch = []

    # Create the schema using the existing connection
    manager.create_schema()
    # Don't close - let caller handle connection lifecycle


# Public exports
__all__ = ['DatabaseManager', 'create_database_schema']
