"""Schema utility classes - Foundation for all schema definitions."""

import sqlite3
from dataclasses import dataclass, field


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

            if self.autoincrement and self.type.upper() == "INTEGER":
                parts.append("AUTOINCREMENT")
        if self.check:
            parts.append(f"CHECK({self.check})")
        return " ".join(parts)


@dataclass
class ForeignKey:
    """Foreign key relationship metadata for JOIN query generation."""

    local_columns: list[str]
    foreign_table: str
    foreign_columns: list[str]

    def validate(self, local_table: str, all_tables: dict[str, TableSchema]) -> list[str]:
        """Validate foreign key definition against schema."""
        errors = []

        if self.foreign_table not in all_tables:
            errors.append(f"Foreign table '{self.foreign_table}' does not exist")
            return errors

        local_schema = all_tables[local_table]
        foreign_schema = all_tables[self.foreign_table]

        local_col_names = set(local_schema.column_names())
        for col in self.local_columns:
            if col not in local_col_names:
                errors.append(f"Local column '{col}' not found in table '{local_table}'")

        foreign_col_names = set(foreign_schema.column_names())
        for col in self.foreign_columns:
            if col not in foreign_col_names:
                errors.append(f"Foreign column '{col}' not found in table '{self.foreign_table}'")

        if len(self.local_columns) != len(self.foreign_columns):
            errors.append(
                f"Column count mismatch: {len(self.local_columns)} local vs "
                f"{len(self.foreign_columns)} foreign"
            )

        return errors


@dataclass
class TableSchema:
    """Represents a complete table schema."""

    name: str
    columns: list[Column]
    indexes: list[tuple[str, list[str]]] = field(default_factory=list)
    primary_key: list[str] | None = None
    unique_constraints: list[list[str]] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)

    def column_names(self) -> list[str]:
        """Get list of column names in definition order."""
        return [col.name for col in self.columns]

    def create_table_sql(self) -> str:
        """Generate CREATE TABLE statement."""

        column_pks = [col.name for col in self.columns if col.primary_key]
        if column_pks and self.primary_key:
            raise ValueError(
                f"PRIMARY KEY conflict in table '{self.name}': "
                f"Column-level PRIMARY KEY on {column_pks} AND table-level PRIMARY KEY on {self.primary_key}. "
                f"Use only ONE: either Column(primary_key=True) OR TableSchema(primary_key=[...])."
            )

        col_defs = [col.to_sql() for col in self.columns]

        if self.primary_key:
            pk_cols = ", ".join(self.primary_key)
            col_defs.append(f"PRIMARY KEY ({pk_cols})")

        for unique_cols in self.unique_constraints:
            unique_str = ", ".join(unique_cols)
            col_defs.append(f"UNIQUE({unique_str})")

        for fk in self.foreign_keys:
            if isinstance(fk, ForeignKey):
                local_cols = ", ".join(fk.local_columns)
                foreign_cols = ", ".join(fk.foreign_columns)
                col_defs.append(
                    f"FOREIGN KEY ({local_cols}) REFERENCES {fk.foreign_table} ({foreign_cols})"
                )
            elif isinstance(fk, tuple) and len(fk) >= 3:
                local_col, foreign_table, foreign_col = fk[0], fk[1], fk[2]
                col_defs.append(
                    f"FOREIGN KEY ({local_col}) REFERENCES {foreign_table} ({foreign_col})"
                )

        return f"CREATE TABLE IF NOT EXISTS {self.name} (\n    " + ",\n    ".join(col_defs) + "\n)"

    def create_indexes_sql(self) -> list[str]:
        """Generate CREATE INDEX statements."""
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
        """Validate that actual database table matches this schema.

        Checks:
        1. Table exists
        2. All columns exist with correct types
        3. UNIQUE constraints exist (using PRAGMA, not string matching)
        4. Foreign key constraints exist (using PRAGMA foreign_key_list)
        """
        errors = []

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (self.name,))
        if not cursor.fetchone():
            errors.append(f"Table {self.name} does not exist")
            return False, errors

        cursor.execute(f"PRAGMA table_info({self.name})")
        actual_cols = {row[1]: row[2] for row in cursor.fetchall()}

        for col in self.columns:
            if col.name not in actual_cols:
                errors.append(f"Column {self.name}.{col.name} missing in database")
            elif actual_cols[col.name].upper() != col.type.upper():
                errors.append(
                    f"Column {self.name}.{col.name} type mismatch: "
                    f"expected {col.type}, got {actual_cols[col.name]}"
                )

        if self.unique_constraints:
            cursor.execute(f"PRAGMA index_list({self.name})")
            db_unique_sets: list[set[str]] = []

            for idx_row in cursor.fetchall():
                idx_name = idx_row[1]
                is_unique = idx_row[2]

                if is_unique:
                    cursor.execute(f"PRAGMA index_info({idx_name})")
                    idx_cols = {row[2] for row in cursor.fetchall()}
                    db_unique_sets.append(idx_cols)

            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (self.name,)
            )
            result = cursor.fetchone()
            create_sql = (result[0] or "").upper() if result else ""

            for unique_cols in self.unique_constraints:
                expected_set = set(unique_cols)

                found = any(expected_set == db_set for db_set in db_unique_sets)

                if not found:
                    normalized_cols = [c.strip('"').strip("'") for c in unique_cols]
                    for variant in [
                        f"UNIQUE({', '.join(normalized_cols)})",
                        f"UNIQUE ({', '.join(normalized_cols)})",
                        f'UNIQUE("{'", "'.join(normalized_cols)}")',
                    ]:
                        if variant.upper() in create_sql:
                            found = True
                            break

                if not found:
                    errors.append(
                        f"UNIQUE constraint on ({', '.join(unique_cols)}) missing in database table {self.name}"
                    )

        if self.foreign_keys:
            cursor.execute(f"PRAGMA foreign_key_list({self.name})")

            db_fks: dict[str, list[tuple[str, str]]] = {}

            for fk_row in cursor.fetchall():
                fk_id = fk_row[0]
                foreign_table = fk_row[2]
                local_col = fk_row[3]
                foreign_col = fk_row[4]

                key = (fk_id, foreign_table)
                if key not in db_fks:
                    db_fks[key] = []
                db_fks[key].append((local_col, foreign_col))

            for fk in self.foreign_keys:
                if isinstance(fk, ForeignKey):
                    expected_table = fk.foreign_table
                    expected_pairs = list(zip(fk.local_columns, fk.foreign_columns, strict=True))

                    found = False
                    for (_fk_id, db_table), db_pairs in db_fks.items():
                        if db_table == expected_table and set(db_pairs) == set(expected_pairs):
                            found = True
                            break

                    if not found:
                        local_str = ", ".join(fk.local_columns)
                        foreign_str = ", ".join(fk.foreign_columns)
                        errors.append(
                            f"FOREIGN KEY ({local_str}) REFERENCES {expected_table}({foreign_str}) "
                            f"missing in database table {self.name}"
                        )

        return len(errors) == 0, errors
