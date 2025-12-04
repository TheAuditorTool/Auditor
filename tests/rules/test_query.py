"""Tests for the Q query builder class.

Tests cover:
- 5.1 Single table SELECT operations
- 5.2 JOIN operations
- 5.3 CTE (Common Table Expression) operations
- 5.4 Q.raw() escape hatch
"""

import pytest
from unittest.mock import patch

from theauditor.rules.query import Q


class TestQSingleTableSelect:
    """5.1 Test Q class single table SELECT."""

    def test_basic_select_with_columns(self):
        """Basic select with explicit columns."""
        sql, params = Q("symbols").select("name", "line").build()

        assert "SELECT name, line" in sql
        assert "FROM symbols" in sql
        assert params == []

    def test_select_star_default(self):
        """Select * when no columns specified."""
        sql, params = Q("symbols").build()

        assert "SELECT *" in sql
        assert "FROM symbols" in sql

    def test_select_with_where_clause_and_params(self):
        """Select with WHERE clause and parameters."""
        sql, params = Q("symbols").select("name", "line").where("type = ?", "function").build()

        assert "SELECT name, line" in sql
        assert "FROM symbols" in sql
        assert "WHERE (type = ?)" in sql
        assert params == ["function"]

    def test_multiple_where_clauses_anded(self):
        """Multiple WHERE clauses are ANDed together."""
        sql, params = (
            Q("symbols")
            .select("name")
            .where("type = ?", "function")
            .where("name LIKE ?", "%test%")
            .build()
        )

        assert "WHERE (type = ?) AND (name LIKE ?)" in sql
        assert params == ["function", "%test%"]

    def test_select_with_order_by(self):
        """Select with ORDER BY clause."""
        sql, params = Q("symbols").select("name").order_by("line DESC").build()

        assert "ORDER BY line DESC" in sql

    def test_select_with_limit(self):
        """Select with LIMIT clause."""
        sql, params = Q("symbols").select("name").limit(10).build()

        assert "LIMIT 10" in sql

    def test_select_with_group_by(self):
        """Select with GROUP BY clause."""
        sql, params = (
            Q("symbols")
            .select("type", "COUNT(*)")
            .group_by("type")
            .build()
        )

        assert "GROUP BY type" in sql

    def test_unknown_table_raises_error(self):
        """Unknown table raises ValueError on construction."""
        with pytest.raises(ValueError) as exc_info:
            Q("nonexistent_table")

        assert "Unknown table: nonexistent_table" in str(exc_info.value)
        assert "Available:" in str(exc_info.value)

    def test_unknown_column_raises_error_at_build(self):
        """Unknown column raises ValueError at build time."""
        with pytest.raises(ValueError) as exc_info:
            Q("symbols").select("invalid_column_xyz").build()

        assert "Unknown column 'invalid_column_xyz'" in str(exc_info.value)
        assert "Valid columns:" in str(exc_info.value)

    def test_expression_columns_pass_validation(self):
        """Expressions like COUNT(*) pass validation."""
        sql, params = Q("symbols").select("COUNT(*)", "MAX(line)").build()

        assert "SELECT COUNT(*), MAX(line)" in sql

    def test_chaining_returns_self(self):
        """All methods return self for chaining."""
        q = Q("symbols")
        assert q.select("name") is q
        assert q.where("type = ?", "function") is q
        assert q.order_by("line") is q
        assert q.limit(10) is q
        assert q.group_by("type") is q


class TestQJoin:
    """5.2 Test Q class JOIN operations."""

    def test_join_with_explicit_on_list_of_tuples(self):
        """JOIN with explicit ON condition as list of tuples."""
        sql, params = (
            Q("function_call_args")
            .select("function_call_args.file", "function_call_args.line")
            .join("assignments", on=[("file", "file")])
            .build()
        )

        assert "INNER JOIN assignments ON" in sql
        assert "function_call_args.file = assignments.file" in sql

    def test_join_with_explicit_on_raw_string(self):
        """JOIN with explicit ON condition as raw string (escape hatch)."""
        sql, params = (
            Q("function_call_args")
            .select("file", "line")
            .join("assignments", on="function_call_args.file = assignments.file AND function_call_args.line < assignments.line")
            .build()
        )

        assert "INNER JOIN assignments ON function_call_args.file = assignments.file AND function_call_args.line < assignments.line" in sql

    def test_join_type_left(self):
        """LEFT JOIN type."""
        sql, params = (
            Q("symbols")
            .select("symbols.name")
            .join("refs", on=[("name", "symbol_name")], join_type="LEFT")
            .build()
        )

        assert "LEFT JOIN refs ON" in sql

    def test_join_without_on_requires_fk(self):
        """JOIN without ON requires FK relationship, raises if not found."""
        # Use tables that definitely don't have FK relationship
        # sql_queries and symbols have no FK between them
        with pytest.raises(ValueError) as exc_info:
            Q("sql_queries").join("symbols").build()

        assert "No foreign key" in str(exc_info.value) or "requires explicit on=" in str(exc_info.value)

    def test_multiple_join_conditions(self):
        """JOIN with multiple column pairs."""
        sql, params = (
            Q("function_call_args")
            .select("file")
            .join("assignments", on=[("file", "file"), ("line", "line")])
            .build()
        )

        assert "function_call_args.file = assignments.file" in sql
        assert "function_call_args.line = assignments.line" in sql


class TestQCTE:
    """5.3 Test Q class CTE (Common Table Expression) operations."""

    def test_single_cte(self):
        """Single CTE query."""
        subquery = Q("assignments").select("file", "target_var").where("source_expr LIKE ?", "%request%")

        sql, params = (
            Q("function_call_args")
            .with_cte("tainted_vars", subquery)
            .select("file", "line")
            .build()
        )

        assert sql.startswith("WITH tainted_vars AS")
        # Check components exist (SQL may have newlines)
        assert "SELECT file, target_var" in sql
        assert "FROM assignments" in sql
        assert "WHERE (source_expr LIKE ?)" in sql
        assert params == ["%request%"]

    def test_multiple_ctes(self):
        """Multiple CTEs in order."""
        cte1 = Q("assignments").select("file", "target_var").where("source_expr LIKE ?", "%input%")
        cte2 = Q("symbols").select("name", "path").where("type = ?", "function")

        sql, params = (
            Q("function_call_args")
            .with_cte("tainted", cte1)
            .with_cte("funcs", cte2)
            .select("file", "line")
            .build()
        )

        assert "WITH tainted AS" in sql
        assert "funcs AS" in sql
        # CTE params come before main query params
        assert params == ["%input%", "function"]

    def test_cte_joined_to_main_query(self):
        """CTE can be joined to main query."""
        subquery = Q("assignments").select("file", "target_var").where("source_expr LIKE ?", "%request%")

        sql, params = (
            Q("function_call_args")
            .with_cte("tainted", subquery)
            .select("function_call_args.file", "function_call_args.line")
            .join("tainted", on=[("file", "file")])
            .build()
        )

        assert "WITH tainted AS" in sql
        assert "JOIN tainted ON" in sql

    def test_cte_params_before_main_params(self):
        """CTE parameters come before main query parameters."""
        subquery = Q("assignments").select("file").where("source_expr LIKE ?", "%cte_param%")

        sql, params = (
            Q("function_call_args")
            .with_cte("sub", subquery)
            .select("file")
            .where("callee_function LIKE ?", "%main_param%")
            .build()
        )

        # CTE param first, then main query param
        assert params == ["%cte_param%", "%main_param%"]


class TestQRaw:
    """5.4 Test Q.raw() escape hatch."""

    def test_raw_returns_sql_and_params_unchanged(self):
        """Q.raw() returns sql and params unchanged."""
        sql, params = Q.raw("SELECT * FROM custom WHERE x = ?", ["value"])

        assert sql == "SELECT * FROM custom WHERE x = ?"
        assert params == ["value"]

    def test_raw_with_empty_params(self):
        """Q.raw() with no params returns empty list."""
        sql, params = Q.raw("SELECT 1")

        assert sql == "SELECT 1"
        assert params == []

    def test_raw_logs_warning(self):
        """Q.raw() logs warning for audit trail."""
        with patch("theauditor.rules.query.logger") as mock_logger:
            Q.raw("SELECT * FROM bypass WHERE dangerous = 1", [])

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "Q.raw() bypassing validation" in call_args
