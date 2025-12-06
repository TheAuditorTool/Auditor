"""Composable query builder with schema validation.

Provides a single Q class that replaces build_query() and build_join_query()
with support for CTEs, subqueries, and arbitrary complexity.

Usage:
    # Simple SELECT
    sql, params = Q("symbols").select("name", "line").where("type = ?", "function").build()

    # JOIN with FK auto-detection
    sql, params = Q("function_call_args").select("file", "line").join("symbols").build()

    # CTE query
    tainted = Q("assignments").select("file", "target_var").where("source_expr LIKE ?", "%request%")
    sql, params = Q("function_call_args").with_cte("tainted_vars", tainted).select("file", "line").join("tainted_vars", on=[("file", "file")]).build()
"""

from __future__ import annotations

from theauditor.indexer.schema import TABLES
from theauditor.indexer.schemas.utils import ForeignKey
from theauditor.utils.logging import logger


class Q:
    """Composable query builder with schema validation at build time.

    All methods return self for chaining. Validation happens at .build() time
    so errors include full query context.
    """

    def __init__(self, table: str):
        """Initialize query builder for a table.

        Args:
            table: Table name (must exist in TABLES schema)

        Raises:
            ValueError: If table not found in TABLES
        """
        if table not in TABLES:
            raise ValueError(
                f"Unknown table: {table}. Available: {', '.join(sorted(TABLES.keys()))}"
            )
        self._base_table = table
        self._alias: str | None = None
        self._parts: dict = {
            "select": [],
            "where": [],
            "joins": [],
            "ctes": [],
            "order": None,
            "limit": None,
            "group": [],
        }
        self._params: list = []

    def alias(self, name: str) -> Q:
        """Set table alias for use in complex queries.

        Args:
            name: Alias for the base table

        Returns:
            Self for chaining
        """
        self._alias = name
        return self

    def select(self, *columns: str) -> Q:
        """Specify columns to select.

        Args:
            *columns: Column names to select

        Returns:
            Self for chaining
        """
        self._parts["select"].extend(columns)
        return self

    def where(self, condition: str, *params) -> Q:
        """Add WHERE condition. Multiple calls are ANDed together.

        Args:
            condition: SQL condition with ? placeholders
            *params: Parameter values for placeholders

        Returns:
            Self for chaining
        """
        self._parts["where"].append(condition)
        self._params.extend(params)
        return self

    def where_in(self, column: str, values: list) -> Q:
        """Add WHERE column IN (...) condition with safe parameter binding.

        Args:
            column: Column name to match against
            values: List of values for IN clause

        Returns:
            Self for chaining

        Example:
            Q("function_call_args").where_in("callee_function", ["eval", "exec"])
            # Generates: WHERE callee_function IN (?, ?)
        """
        if not values:
            self._parts["where"].append("1 = 0")
            return self
        placeholders = ", ".join("?" for _ in values)
        self._parts["where"].append(f"{column} IN ({placeholders})")
        self._params.extend(values)
        return self

    def join(
        self,
        table: str,
        on: list[tuple[str, str]] | str | None = None,
        join_type: str = "INNER",
    ) -> Q:
        """Add JOIN clause.

        Args:
            table: Table to join (or CTE name)
            on: Join condition - one of:
                - None: Auto-detect from ForeignKey metadata
                - list[tuple[str, str]]: List of (base_col, join_col) pairs
                - str: Raw SQL for ON clause (no validation)
            join_type: JOIN type (INNER, LEFT, RIGHT, FULL)

        Returns:
            Self for chaining

        Raises:
            ValueError: If on=None and no FK relationship found
        """
        self._parts["joins"].append(
            {
                "table": table,
                "on": on,
                "type": join_type,
            }
        )
        return self

    def with_cte(self, name: str, subquery: Q) -> Q:
        """Add Common Table Expression (CTE).

        Args:
            name: CTE name to reference in main query
            subquery: Q object defining the CTE

        Returns:
            Self for chaining
        """
        self._parts["ctes"].append(
            {
                "name": name,
                "query": subquery,
            }
        )
        return self

    def order_by(self, clause: str) -> Q:
        """Set ORDER BY clause.

        Args:
            clause: Order clause (e.g., "file, line DESC")

        Returns:
            Self for chaining
        """
        self._parts["order"] = clause
        return self

    def limit(self, n: int) -> Q:
        """Set LIMIT clause.

        Args:
            n: Maximum rows to return

        Returns:
            Self for chaining
        """
        self._parts["limit"] = n
        return self

    def group_by(self, *columns: str) -> Q:
        """Set GROUP BY clause.

        Args:
            *columns: Columns to group by

        Returns:
            Self for chaining
        """
        self._parts["group"].extend(columns)
        return self

    def build(self) -> tuple[str, list]:
        """Build SQL query with validation.

        Validates all column references against TABLES schema.
        CTE names are treated as valid tables for join targets.

        Returns:
            Tuple of (sql_string, params_list)

        Raises:
            ValueError: If validation fails (unknown column, missing FK, etc.)
        """
        all_params = []
        sql_parts = []

        cte_names = {cte["name"] for cte in self._parts["ctes"]}

        if self._parts["ctes"]:
            cte_clauses = []
            for cte in self._parts["ctes"]:
                cte_sql, cte_params = cte["query"].build()
                cte_clauses.append(f"{cte['name']} AS (\n    {cte_sql}\n)")
                all_params.extend(cte_params)
            sql_parts.append("WITH " + ",\n".join(cte_clauses))

        select_cols = self._parts["select"] or ["*"]
        validated_cols = self._validate_columns(select_cols, cte_names)
        sql_parts.append(f"SELECT {', '.join(validated_cols)}")

        table_ref = self._base_table
        if self._alias:
            table_ref = f"{self._base_table} {self._alias}"
        sql_parts.append(f"FROM {table_ref}")

        for join in self._parts["joins"]:
            join_table = join["table"]
            join_type = join["type"]
            on_clause = join["on"]

            if on_clause is None:
                fk = self._find_fk(self._base_table, join_table)
                if fk is None and join_table not in cte_names:
                    raise ValueError(
                        f"No foreign key from '{self._base_table}' to '{join_table}'. "
                        f"Provide explicit on= parameter."
                    )
                if fk:
                    on_pairs = list(zip(fk.local_columns, fk.foreign_columns, strict=False))
                    on_sql = self._build_on_clause(join_table, on_pairs)
                else:
                    raise ValueError(f"CTE '{join_table}' requires explicit on= parameter.")
            elif isinstance(on_clause, str):
                on_sql = on_clause
            else:
                on_sql = self._build_on_clause(join_table, on_clause)

            sql_parts.append(f"{join_type} JOIN {join_table} ON {on_sql}")

        if self._parts["where"]:
            where_sql = " AND ".join(f"({w})" for w in self._parts["where"])
            sql_parts.append(f"WHERE {where_sql}")

        all_params.extend(self._params)

        if self._parts["group"]:
            sql_parts.append(f"GROUP BY {', '.join(self._parts['group'])}")

        if self._parts["order"]:
            sql_parts.append(f"ORDER BY {self._parts['order']}")

        if self._parts["limit"] is not None:
            sql_parts.append(f"LIMIT {self._parts['limit']}")

        sql = "\n".join(sql_parts)
        return sql, all_params

    def _validate_columns(self, columns: list[str], cte_names: set[str]) -> list[str]:
        """Validate column references against schema.

        Handles:
        - Simple columns: "name" -> validates against base table
        - Qualified columns: "t.name" -> validates table alias or skips if CTE
        - Expressions: "COUNT(*)" -> passes through without validation
        - Star: "*" -> passes through

        Args:
            columns: Column references to validate
            cte_names: Set of CTE names (skip validation for these)

        Returns:
            Validated column list

        Raises:
            ValueError: If column not found in schema
        """
        validated = []
        schema = TABLES[self._base_table]
        valid_cols = set(schema.column_names())

        for col in columns:
            if col == "*" or "(" in col or " " in col.upper():
                validated.append(col)
                continue

            if "." in col:
                parts = col.split(".", 1)
                table_or_alias = parts[0]
                col_name = parts[1]

                if table_or_alias in cte_names:
                    validated.append(col)
                    continue

                if table_or_alias == self._alias:
                    if col_name != "*" and col_name not in valid_cols:
                        raise ValueError(
                            f"Unknown column '{col_name}' in table '{self._base_table}'. "
                            f"Valid columns: {', '.join(sorted(valid_cols))}"
                        )
                    validated.append(col)
                    continue

                joined_tables = {j["table"] for j in self._parts["joins"]}
                if table_or_alias in joined_tables:
                    if table_or_alias in TABLES:
                        join_schema = TABLES[table_or_alias]
                        join_cols = set(join_schema.column_names())
                        if col_name != "*" and col_name not in join_cols:
                            raise ValueError(
                                f"Unknown column '{col_name}' in table '{table_or_alias}'. "
                                f"Valid columns: {', '.join(sorted(join_cols))}"
                            )
                    validated.append(col)
                    continue

                validated.append(col)
                continue

            if col not in valid_cols:
                raise ValueError(
                    f"Unknown column '{col}' in table '{self._base_table}'. "
                    f"Valid columns: {', '.join(sorted(valid_cols))}"
                )
            validated.append(col)

        return validated

    def _build_on_clause(self, join_table: str, pairs: list[tuple[str, str]]) -> str:
        """Build ON clause from column pairs.

        Args:
            join_table: Table being joined
            pairs: List of (base_col, join_col) tuples

        Returns:
            SQL ON clause string
        """
        base_prefix = self._alias or self._base_table
        conditions = []
        for base_col, join_col in pairs:
            conditions.append(f"{base_prefix}.{base_col} = {join_table}.{join_col}")
        return " AND ".join(conditions)

    def _find_fk(self, base_table: str, join_table: str) -> ForeignKey | None:
        """Find foreign key relationship between tables.

        Checks both directions:
        1. base_table has FK to join_table
        2. join_table has FK to base_table (reversed)

        Args:
            base_table: Starting table
            join_table: Target table

        Returns:
            ForeignKey if found, None otherwise
        """

        schema = TABLES.get(base_table)
        if schema:
            for fk in schema.foreign_keys:
                if fk.foreign_table == join_table:
                    return fk

        join_schema = TABLES.get(join_table)
        if join_schema:
            for fk in join_schema.foreign_keys:
                if fk.foreign_table == base_table:
                    return ForeignKey(
                        local_columns=fk.foreign_columns,
                        foreign_table=join_table,
                        foreign_columns=fk.local_columns,
                    )

        return None

    @classmethod
    def raw(cls, sql: str, params: list | None = None) -> tuple[str, list]:
        """Escape hatch for raw SQL that Q cannot express.

        Logs warning for audit trail. Use sparingly.

        Args:
            sql: Raw SQL string
            params: Optional parameter list

        Returns:
            Tuple of (sql, params)
        """
        logger.warning(f"Q.raw() bypassing validation: {sql[:50]}...")
        return (sql, params or [])
