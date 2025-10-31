"""Framework-specific database operations.

This module contains add_* methods for FRAMEWORKS_TABLES defined in schemas/frameworks_schema.py.
Handles 5 framework tables including API endpoints, ORM relationships, and Prisma models.
"""

from typing import List, Optional


class FrameworksDatabaseMixin:
    """Mixin providing add_* methods for FRAMEWORKS_TABLES.

    CRITICAL: This mixin assumes self.generic_batches exists (from BaseDatabaseManager).
    DO NOT instantiate directly - only use as mixin for DatabaseManager.
    """

    # ========================================================
    # API ENDPOINT BATCH METHODS
    # ========================================================

    def add_endpoint(self, file_path: str, method: str, pattern: str, controls: List[str],
                     line: Optional[int] = None, path: Optional[str] = None,
                     has_auth: bool = False, handler_function: Optional[str] = None):
        """Add an API endpoint record to the batch.

        ARCHITECTURE: Normalized many-to-many relationship.
        - Phase 1: Batch endpoint record (without controls column)
        - Phase 2: Batch junction records for each control/middleware

        NO FALLBACKS. If controls is malformed, hard fail.
        """
        # Phase 1: Add endpoint record (6 params, no controls column)
        self.generic_batches['api_endpoints'].append((file_path, line, method, pattern, path,
                                                      has_auth, handler_function))

        # Phase 2: Add junction records for each control/middleware
        if controls:
            for control_name in controls:
                if not control_name:  # Skip empty strings (data validation, not fallback)
                    continue
                self.generic_batches['api_endpoint_controls'].append((file_path, line, control_name))

    # ========================================================
    # ORM BATCH METHODS
    # ========================================================

    def add_orm_relationship(self, file: str, line: int, source_model: str, target_model: str,
                            relationship_type: str, foreign_key: Optional[str] = None,
                            cascade_delete: bool = False, as_name: Optional[str] = None):
        """Add an ORM relationship record to the batch.

        Args:
            file: File containing the relationship definition
            line: Line number of the relationship
            source_model: Source model name (e.g., "User")
            target_model: Target model name (e.g., "Account")
            relationship_type: Type of relationship - "hasMany", "belongsTo", "hasOne", etc.
            foreign_key: Foreign key column name (e.g., "account_id")
            cascade_delete: Whether CASCADE delete is enabled
            as_name: Association alias (e.g., "owner")
        """
        self.generic_batches['orm_relationships'].append((
            file, line, source_model, target_model, relationship_type,
            foreign_key, 1 if cascade_delete else 0, as_name
        ))

    def add_orm_query(self, file_path: str, line: int, query_type: str, includes: Optional[str],
                      has_limit: bool, has_transaction: bool):
        """Add an ORM query record to the batch."""
        self.generic_batches['orm_queries'].append((file_path, line, query_type, includes, has_limit, has_transaction))

    # ========================================================
    # PRISMA BATCH METHODS
    # ========================================================

    def add_prisma_model(self, model_name: str, field_name: str, field_type: str,
                        is_indexed: bool, is_unique: bool, is_relation: bool):
        """Add a Prisma model field record to the batch."""
        self.generic_batches['prisma_models'].append((model_name, field_name, field_type,
                                                      is_indexed, is_unique, is_relation))
