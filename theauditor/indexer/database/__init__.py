"""Database operations for the indexer."""

import sqlite3
from collections import defaultdict

from .base_database import BaseDatabaseManager
from .bash_database import BashDatabaseMixin
from .core_database import CoreDatabaseMixin
from .frameworks_database import FrameworksDatabaseMixin
from .go_database import GoDatabaseMixin
from .graphql_database import GraphQLDatabaseMixin
from .infrastructure_database import InfrastructureDatabaseMixin
from .node_database import NodeDatabaseMixin
from .planning_database import PlanningDatabaseMixin
from .python_database import PythonDatabaseMixin
from .rust_database import RustDatabaseMixin
from .security_database import SecurityDatabaseMixin


class DatabaseManager(
    BaseDatabaseManager,
    CoreDatabaseMixin,
    PythonDatabaseMixin,
    NodeDatabaseMixin,
    RustDatabaseMixin,
    GoDatabaseMixin,
    BashDatabaseMixin,
    InfrastructureDatabaseMixin,
    SecurityDatabaseMixin,
    FrameworksDatabaseMixin,
    PlanningDatabaseMixin,
    GraphQLDatabaseMixin,
):
    """Complete database manager combining all language-specific capabilities."""

    pass


def create_database_schema(conn: sqlite3.Connection) -> None:
    """Create SQLite database schema - backward compatibility wrapper."""

    manager = DatabaseManager.__new__(DatabaseManager)
    manager.conn = conn
    manager.cursor = conn.cursor()
    manager.batch_size = 200

    manager.generic_batches = defaultdict(list)
    manager.cfg_id_mapping = {}
    manager.jwt_patterns_batch = []

    manager.create_schema()


__all__ = ["DatabaseManager", "create_database_schema"]
