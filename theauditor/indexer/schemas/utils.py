"""
Schema utility classes - Foundation for all schema definitions.

This module contains the core class definitions used by ALL schema modules:
- Column: Represents a database column with type and constraints
- ForeignKey: Foreign key relationship metadata for JOIN query generation
- TableSchema: Complete table schema definition

Design Philosophy:
- Zero dependencies on table definitions (avoids circular imports)
- Used by all language-specific schema modules
- Pure class definitions only (no table registries)
"""


from dataclasses import dataclass, field
import sqlite3


@dataclass
class Column:
    """Represents a database column with type and constraints."""
    name: str
    type: str
    nullable: bool = True
    default: str | None = None
    primary_key: bool = False
    autoincrement: bool = False
    check: str | None = None

    def to_sql(self) -> str:
        """Generate SQL column definition."""
        parts = [self.name, self.type]
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        if self.primary_key:
            parts.append("PRIMARY KEY")
            # AUTOINCREMENT only valid for INTEGER PRIMARY KEY
            if self.autoincrement and self.type.upper() == "INTEGER":
                parts.append("AUTOINCREMENT")
        if self.check:
            parts.append(f"CHECK({self.check})")
        return " ".join(parts)


@dataclass
class ForeignKey:
    """Foreign key relationship metadata for JOIN query generation.

    Purpose: Enables build_join_query() to validate and construct JOINs.
    NOT used for CREATE TABLE generation (database.py defines FKs).

    Attributes:
        local_columns: Column names in this table (e.g., ['query_file', 'query_line'])
        foreign_table: Referenced table name (e.g., 'sql_queries')
        foreign_columns: Column names in foreign table (e.g., ['file_path', 'line_number'])

    Example:
        ForeignKey(
            local_columns=['query_file', 'query_line'],
            foreign_table='sql_queries',
            foreign_columns=['file_path', 'line_number']
        )
    """
    local_columns: list[str]
    foreign_table: str
    foreign_columns: list[str]

    def validate(self, local_table: str, all_tables: dict[str, "TableSchema"]) -> list[str]:
        """Validate foreign key definition against schema.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check foreign table exists
        if self.foreign_table not in all_tables:
            errors.append(f"Foreign table '{self.foreign_table}' does not exist")
            return errors

        local_schema = all_tables[local_table]
        foreign_schema = all_tables[self.foreign_table]

        # Check local columns exist
        local_col_names = set(local_schema.column_names())
        for col in self.local_columns:
            if col not in local_col_names:
                errors.append(f"Local column '{col}' not found in table '{local_table}'")

        # Check foreign columns exist
        foreign_col_names = set(foreign_schema.column_names())
        for col in self.foreign_columns:
            if col not in foreign_col_names:
                errors.append(f"Foreign column '{col}' not found in table '{self.foreign_table}'")

        # Check column count matches
        if len(self.local_columns) != len(self.foreign_columns):
            errors.append(
                f"Column count mismatch: {len(self.local_columns)} local vs "
                f"{len(self.foreign_columns)} foreign"
            )

        return errors


@dataclass
class TableSchema:
    """Represents a complete table schema.

    Design Pattern - Foreign Key Constraints:
        Foreign keys serve TWO purposes in this schema:

        1. JOIN Query Generation (NEW):
           The foreign_keys field provides metadata for build_join_query() to:
           - Validate JOIN conditions reference correct tables/columns
           - Auto-generate proper JOIN ON clauses
           - Enable type-safe relational queries

        2. Database Integrity (UNCHANGED):
           Actual FOREIGN KEY constraints in CREATE TABLE statements are still
           defined exclusively in database.py. This separation maintains backward
           compatibility and avoids circular dependencies during table creation.

        The foreign_keys field is OPTIONAL and backward compatible. Tables without
        foreign keys can still be queried normally with build_query().

    Attributes:
        name: Table name
        columns: List of column definitions
        indexes: List of (index_name, [column_names]) tuples
        primary_key: Composite primary key column list (for multi-column PKs)
        unique_constraints: List of UNIQUE constraint column lists
        foreign_keys: List of ForeignKey definitions (for JOIN generation)
    """
    name: str
    columns: list["Column"]
    indexes: list[tuple[str, list[str]]] = field(default_factory=list)
    primary_key: list[str] | None = None  # Composite primary keys
    unique_constraints: list[list[str]] = field(default_factory=list)  # UNIQUE constraints
    foreign_keys: list["ForeignKey"] = field(default_factory=list)  # For JOIN query generation

    def column_names(self) -> list[str]:
        """Get list of column names in definition order."""
        return [col.name for col in self.columns]

    def create_table_sql(self) -> str:
        """Generate CREATE TABLE statement."""
        col_defs = [col.to_sql() for col in self.columns]

        # Add composite primary key if defined
        if self.primary_key:
            pk_cols = ", ".join(self.primary_key)
            col_defs.append(f"PRIMARY KEY ({pk_cols})")

        # Add unique constraints if defined
        for unique_cols in self.unique_constraints:
            unique_str = ", ".join(unique_cols)
            col_defs.append(f"UNIQUE({unique_str})")

        return f"CREATE TABLE IF NOT EXISTS {self.name} (\n    " + ",\n    ".join(col_defs) + "\n)"

    def create_indexes_sql(self) -> list[str]:
        """Generate CREATE INDEX statements.

        Supports both regular and partial indexes:
        - Regular: (idx_name, [cols])
        - Partial: (idx_name, [cols], where_clause)
        """
        stmts = []
        for idx_def in self.indexes:
            if len(idx_def) == 2:
                idx_name, idx_cols = idx_def
                where_clause = None
            else:
                idx_name, idx_cols, where_clause = idx_def

            cols_str = ", ".join(idx_cols)
            stmt = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {self.name} ({cols_str})"
            if where_clause:
                stmt += f" WHERE {where_clause}"
            stmts.append(stmt)
        return stmts

    def validate_against_db(self, cursor: sqlite3.Cursor) -> tuple[bool, list[str]]:
        """
        Validate that actual database table matches this schema.

        Returns:
            (is_valid, [error_messages])
        """
        errors = []

        # Check table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (self.name,)
        )
        if not cursor.fetchone():
            errors.append(f"Table {self.name} does not exist")
            return False, errors

        # Get actual columns
        cursor.execute(f"PRAGMA table_info({self.name})")
        actual_cols = {row[1]: row[2] for row in cursor.fetchall()}  # {name: type}

        # Validate columns (only check required columns, allow extra for migrations)
        for col in self.columns:
            if col.name not in actual_cols:
                errors.append(f"Column {self.name}.{col.name} missing in database")
            elif actual_cols[col.name].upper() != col.type.upper():
                errors.append(
                    f"Column {self.name}.{col.name} type mismatch: "
                    f"expected {col.type}, got {actual_cols[col.name]}"
                )

        # Validate UNIQUE constraints if defined in schema
        if self.unique_constraints:
            # Get the CREATE TABLE SQL from sqlite_master
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (self.name,)
            )
            result = cursor.fetchone()
            if result:
                create_sql = result[0] or ""
                # Check each expected UNIQUE constraint exists in the SQL
                for unique_cols in self.unique_constraints:
                    unique_str = ", ".join(unique_cols)
                    # Match both "UNIQUE(col1, col2)" and "UNIQUE (col1, col2)" formats
                    if f"UNIQUE({unique_str})" not in create_sql and f"UNIQUE ({unique_str})" not in create_sql:
                        errors.append(
                            f"UNIQUE constraint on ({unique_str}) missing in database table {self.name}"
                        )

        return len(errors) == 0, errors
