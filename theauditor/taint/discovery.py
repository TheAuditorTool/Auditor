"""Database-driven source and sink discovery."""

import sqlite3
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core import TaintRegistry


def _matches_file_io_pattern(func_name: str, patterns: list[str]) -> bool:
    """Strict pattern matching for file I/O functions to avoid false positives."""
    if not func_name:
        return False

    for pattern in patterns:
        if func_name == pattern:
            return True

        if f".{pattern}" in func_name and func_name.endswith(pattern):
            return True

    return False


class TaintDiscovery:
    """Database-driven discovery of taint sources and sinks.

    Uses TaintRegistry for vulnerability type classification instead of
    hardcoding pattern lists.
    """

    def __init__(self, cache, registry: TaintRegistry | None = None):
        """Initialize with cache and optional registry for vuln type lookup."""
        self.cache = cache
        self.registry = registry

    def discover_sources(
        self, sources_dict: dict[str, list[str]] | None = None
    ) -> list[dict[str, Any]]:
        """Discover taint sources from database."""
        sources = []

        if sources_dict is None:
            sources_dict = {}

        http_request_patterns = sources_dict.get("http_request", [])
        user_input_patterns = sources_dict.get("user_input", [])
        combined_patterns = http_request_patterns + user_input_patterns

        seen_vars = set()

        for var_usage in self.cache.variable_usage:
            var_name = var_usage.get("variable_name", "")

            if (
                combined_patterns
                and any(var_name == p or var_name.startswith(p + ".") for p in combined_patterns)
                and var_name not in seen_vars
            ):
                seen_vars.add(var_name)
                sources.append(
                    {
                        "type": "http_request",
                        "name": var_name,
                        "file": var_usage.get("file", ""),
                        "line": var_usage.get("line", 0),
                        "pattern": var_name,
                        "category": "http_request",
                        "risk": "high",
                        "metadata": var_usage,
                    }
                )

        for symbol in self.cache.symbols_by_type.get("property", []):
            name = symbol.get("name", "")

            if (
                combined_patterns
                and any(name == p or name.startswith(p + ".") for p in combined_patterns)
                and name not in seen_vars
            ):
                seen_vars.add(name)
                sources.append(
                    {
                        "type": "http_request",
                        "name": name,
                        "file": symbol.get("path", ""),
                        "line": symbol.get("line", 0),
                        "pattern": name,
                        "category": "http_request",
                        "risk": "high",
                        "metadata": symbol,
                    }
                )

        for env in self.cache.env_var_usage:
            sources.append(
                {
                    "type": "environment",
                    "name": env.get("key", "unknown"),
                    "file": env.get("file", ""),
                    "line": env.get("line", 0),
                    "pattern": f"process.env.{env.get('key', '')}",
                    "category": "environment",
                    "risk": "low",
                    "metadata": env,
                }
            )

        for query in self.cache.sql_queries:
            if "SELECT" in query.get("query_text", "").upper():
                sources.append(
                    {
                        "type": "database_read",
                        "name": "sql_query_result",
                        "file": query.get("file_path", ""),
                        "line": query.get("line_number", 0),
                        "pattern": query.get("query_text", "")[:50],
                        "category": "database",
                        "risk": "low",
                        "metadata": query,
                    }
                )

        return sources

    def discover_sinks(
        self, sinks_dict: dict[str, list[str]] | None = None
    ) -> list[dict[str, Any]]:
        """Discover security sinks from database."""
        sinks = []

        if sinks_dict is None:
            sinks_dict = {}

        conn = sqlite3.connect(self.cache.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for query in self.cache.sql_queries:
            file_path = query.get("file_path", "")
            line_number = query.get("line_number", 0)
            query_text = query.get("query_text", "")

            extraction_source = query.get("extraction_source", "")
            if extraction_source == "migration_file":
                continue

            cursor.execute(
                """
                SELECT name FROM symbols
                WHERE path = ? AND type = 'function' AND line <= ?
                ORDER BY line DESC
                LIMIT 1
            """,
                (file_path, line_number),
            )
            func_row = cursor.fetchone()
            containing_function = func_row["name"] if func_row else None

            cursor.execute(
                """
                SELECT target_var, in_function
                FROM assignments
                WHERE file = ?
                  AND (in_function = ? OR (in_function IS NULL AND ? IS NULL))
                  AND line < ?
                ORDER BY line DESC
                LIMIT 1
            """,
                (file_path, containing_function, containing_function, line_number),
            )

            result_row = cursor.fetchone()
            if result_row:
                target_var = result_row["target_var"]

                pattern = target_var

                risk = self._assess_sql_risk(query_text)

                sinks.append(
                    {
                        "type": "sql",
                        "name": target_var,
                        "file": file_path,
                        "line": line_number,
                        "pattern": pattern,
                        "category": "sql",
                        "risk": risk,
                        "vulnerability_type": self._get_vulnerability_type("sql", pattern),
                        "is_parameterized": query.get("is_parameterized", False),
                        "metadata": query,
                    }
                )

        conn.close()

        conn2 = sqlite3.connect(self.cache.db_path)
        conn2.row_factory = sqlite3.Row
        cursor2 = conn2.cursor()

        raw_sql_funcs = sinks_dict.get("sql", [])
        sql_query_count = 0
        for call in self.cache.function_call_args:
            file_path = call.get("file", "")
            if (
                "/migrations/" in file_path
                or "migrations\\" in file_path
                or "/migrate/" in file_path
                or "migrate\\" in file_path
            ):
                continue

            func_name = call.get("callee_function", "")
            if raw_sql_funcs and any(raw_func in func_name for raw_func in raw_sql_funcs):
                arg_expr = call.get("argument_expr") or ""

                has_interpolation = "${" in arg_expr
                risk = "critical" if has_interpolation else "high"

                file_path = call.get("file", "")
                line_number = call.get("line", 0)
                caller_function = call.get("caller_function")

                target_variable = arg_expr.split(",")[0].strip() if arg_expr else None

                if target_variable and not (
                    target_variable.startswith('"') or target_variable.startswith("'")
                ):
                    cursor2.execute(
                        """
                        SELECT target_var, in_function
                        FROM assignments
                        WHERE file = ?
                          AND target_var = ?
                          AND (in_function = ? OR (in_function IS NULL AND ? IS NULL))
                          AND line < ?
                        ORDER BY line DESC
                        LIMIT 1
                    """,
                        (file_path, target_variable, caller_function, caller_function, line_number),
                    )
                    result_row = cursor2.fetchone()
                else:
                    result_row = None

                pattern = result_row["target_var"] if result_row else func_name

                sinks.append(
                    {
                        "type": "sql",
                        "name": func_name,
                        "file": file_path,
                        "line": line_number,
                        "pattern": pattern,
                        "category": "sql",
                        "risk": risk,
                        "vulnerability_type": self._get_vulnerability_type("sql", func_name),
                        "is_parameterized": False,
                        "has_interpolation": has_interpolation,
                        "metadata": call,
                    }
                )
                sql_query_count += 1

        model_names = set()
        cursor2.execute("SELECT model_name FROM sequelize_models")
        for row in cursor2.fetchall():
            model_names.add(row["model_name"])

        cursor2.execute("SELECT model_name FROM python_orm_models")
        for row in cursor2.fetchall():
            model_names.add(row["model_name"])

        cursor2.execute("SELECT name FROM rust_structs")
        for row in cursor2.fetchall():
            model_names.add(row["name"])

        orm_patterns = [
            ".findOne",
            ".findAll",
            ".findByPk",
            ".create",
            ".update",
            ".destroy",
            ".bulkCreate",
            ".upsert",
            ".findOrCreate",
            ".query",
            ".execute",
            "db.query",
            "db.execute",
            "knex.select",
            "knex.insert",
            "knex.update",
            "knex.delete",
        ]

        for call in self.cache.function_call_args:
            file_path = call.get("file", "")
            if (
                "/migrations/" in file_path
                or "migrations\\" in file_path
                or "/migrate/" in file_path
                or "migrate\\" in file_path
            ):
                continue

            func_name = call.get("callee_function", "")
            if not func_name:
                continue

            is_orm_method = False
            for pattern in orm_patterns:
                if pattern in func_name:
                    parts = func_name.split(".")
                    if len(parts) >= 2 and parts[-1].startswith(pattern.lstrip(".")):
                        model_or_service_name = parts[-2]

                        if model_or_service_name in model_names:
                            is_orm_method = True
                            break

            if is_orm_method:
                arg_expr = call.get("argument_expr")

                if arg_expr is None:
                    continue

                has_interpolation = "${" in arg_expr or "+" in arg_expr
                risk = "high" if has_interpolation else "medium"

                file_path = call.get("file", "")
                line_number = call.get("line", 0)

                cursor2.execute(
                    """
                    SELECT target_var, in_function
                    FROM assignments
                    WHERE file = ? AND line = ?
                    LIMIT 1
                """,
                    (file_path, line_number),
                )

                result_row = cursor2.fetchone()
                pattern = result_row["target_var"] if result_row else func_name

                sinks.append(
                    {
                        "type": "sql",
                        "name": func_name,
                        "file": file_path,
                        "line": line_number,
                        "pattern": pattern,
                        "category": "orm",
                        "risk": risk,
                        "vulnerability_type": self._get_vulnerability_type("orm", func_name),
                        "is_parameterized": not has_interpolation,
                        "has_interpolation": has_interpolation,
                        "metadata": call,
                    }
                )

        conn2.close()

        for query in getattr(self.cache, "nosql_queries", []):
            sinks.append(
                {
                    "type": "nosql",
                    "name": query.get("collection", "unknown"),
                    "file": query.get("file", ""),
                    "line": query.get("line", 0),
                    "pattern": query.get("operation", ""),
                    "category": "nosql",
                    "risk": "medium",
                    "vulnerability_type": self._get_vulnerability_type("nosql"),
                    "metadata": query,
                }
            )

        cmd_funcs = sinks_dict.get("command", [])
        for call in self.cache.function_call_args:
            func_name = call.get("callee_function", "")
            if cmd_funcs and any(cmd in func_name for cmd in cmd_funcs):
                sinks.append(
                    {
                        "type": "command",
                        "name": func_name,
                        "file": call.get("file", ""),
                        "line": call.get("line", 0),
                        "pattern": func_name,
                        "category": "command",
                        "risk": "critical",
                        "vulnerability_type": self._get_vulnerability_type("command", func_name),
                        "metadata": call,
                    }
                )

        for hook in self.cache.react_hooks:
            if "dangerouslySetInnerHTML" in str(hook):
                sinks.append(
                    {
                        "type": "xss",
                        "name": "dangerouslySetInnerHTML",
                        "file": hook.get("file", ""),
                        "line": hook.get("line", 0),
                        "pattern": "dangerouslySetInnerHTML",
                        "category": "xss",
                        "risk": "high",
                        "vulnerability_type": self._get_vulnerability_type(
                            "xss", "dangerouslySetInnerHTML"
                        ),
                        "metadata": hook,
                    }
                )

        for assignment in self.cache.assignments:
            target = assignment.get("target_var", "")
            if "innerHTML" in target or "outerHTML" in target:
                sinks.append(
                    {
                        "type": "xss",
                        "name": target,
                        "file": assignment.get("file", ""),
                        "line": assignment.get("line", 0),
                        "pattern": target,
                        "category": "xss",
                        "risk": "high",
                        "vulnerability_type": self._get_vulnerability_type("xss", target),
                        "metadata": assignment,
                    }
                )

        xss_funcs = sinks_dict.get("xss", [])
        for call in self.cache.function_call_args:
            func_name = call.get("callee_function", "")
            if xss_funcs and any(xss_func in func_name for xss_func in xss_funcs):
                arg_expr = call.get("argument_expr") or ""

                has_interpolation = "${" in arg_expr or "+" in arg_expr
                risk = "critical" if has_interpolation else "high"

                sinks.append(
                    {
                        "type": "xss",
                        "name": func_name,
                        "file": call.get("file", ""),
                        "line": call.get("line", 0),
                        "pattern": func_name,
                        "category": "xss",
                        "risk": risk,
                        "vulnerability_type": self._get_vulnerability_type("xss", func_name),
                        "has_interpolation": has_interpolation,
                        "metadata": call,
                    }
                )

        file_funcs = sinks_dict.get("path", [])
        for call in self.cache.function_call_args:
            func_name = call.get("callee_function", "")
            if file_funcs and _matches_file_io_pattern(func_name, file_funcs):
                arg = call.get("argument_expr") or ""
                file_path = call.get("file", "")

                if arg and not arg.startswith('"') and not arg.startswith("'"):
                    sinks.append(
                        {
                            "type": "path",
                            "name": func_name,
                            "file": file_path,
                            "line": call.get("line", 0),
                            "pattern": func_name,
                            "category": "path",
                            "risk": "medium",
                            "vulnerability_type": self._get_vulnerability_type("path", func_name),
                            "metadata": call,
                        }
                    )

        ldap_funcs = sinks_dict.get("ldap", [])
        for call in self.cache.function_call_args:
            func_name = call.get("callee_function", "")
            if ldap_funcs and any(
                f in func_name.lower() and "ldap" in func_name.lower() for f in ldap_funcs
            ):
                sinks.append(
                    {
                        "type": "ldap",
                        "name": func_name,
                        "file": call.get("file", ""),
                        "line": call.get("line", 0),
                        "pattern": func_name,
                        "category": "ldap",
                        "risk": "medium",
                        "vulnerability_type": self._get_vulnerability_type("ldap", func_name),
                        "metadata": call,
                    }
                )

        return sinks

    def _assess_sql_risk(self, query_text: str) -> str:
        """Assess the risk level of an SQL query based on its construction."""

        if any(op in query_text for op in ["+", "${", 'f"', "f'", "`${", '".', "'."]):
            return "critical"

        if "%s" in query_text or "%d" in query_text:
            return "high"

        if any(param in query_text for param in ["?", "$1", ":param", "@param"]):
            return "low"

        return "medium"

    def _get_vulnerability_type(self, category: str, pattern: str = "") -> str:
        """Get vulnerability type from registry. NO FALLBACKS."""
        if not self.registry:
            raise ValueError("Registry is MANDATORY. NO FALLBACKS.")

        if pattern:
            info = self.registry.get_sink_info(pattern)
            if info.get("category") != "unknown":
                return info["vulnerability_type"]

        return self.registry.get_vulnerability_type_by_category(category)

    def filter_framework_safe_sinks(self, sinks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter out sinks that are automatically safe due to framework protections."""

        safe_patterns = set()

        for safe_sink in getattr(self.cache, "framework_safe_sinks", []):
            if safe_sink.get("is_safe"):
                pattern = safe_sink.get("sink_pattern", "")
                if pattern:
                    safe_patterns.add(pattern.lower())

        filtered = []

        for sink in sinks:
            sink_name = sink.get("name", "").lower()
            sink_pattern = sink.get("pattern", "").lower()

            if sink_name in safe_patterns or sink_pattern in safe_patterns:
                continue

            if any(safe in sink_name or safe in sink_pattern for safe in safe_patterns):
                continue

            if sink.get("category") == "sql" and sink.get("is_parameterized"):
                continue

            filtered.append(sink)

        return filtered

    def discover_sanitizers(self) -> list[dict[str, Any]]:
        """Discover sanitizers from framework tables."""
        sanitizers = []

        for validator in getattr(self.cache, "validation_framework_usage", []):
            sanitizers.append(
                {
                    "type": "validator",
                    "name": validator.get("function_name", ""),
                    "framework": validator.get("framework", "unknown"),
                    "language": "javascript",
                    "file": validator.get("file", ""),
                    "line": validator.get("line", 0),
                    "pattern": validator.get("function_name", ""),
                    "metadata": validator,
                }
            )

        for validator in getattr(self.cache, "python_validators", []):
            validator_name = validator.get("validator_name", "")
            sanitizers.append(
                {
                    "type": "validator",
                    "name": validator_name,
                    "framework": "pydantic",
                    "language": "python",
                    "file": validator.get("file", ""),
                    "line": validator.get("line", 0),
                    "pattern": validator_name,
                    "validator_type": validator.get("validator_type", "field"),
                    "metadata": validator,
                }
            )

        for model in getattr(self.cache, "sequelize_models", []):
            model_name = model.get("model_name", "")

            for method in ["findOne", "findAll", "findByPk", "create", "update", "destroy"]:
                sanitizers.append(
                    {
                        "type": "orm_model",
                        "name": f"{model_name}.{method}",
                        "framework": "sequelize",
                        "language": "javascript",
                        "file": model.get("file", ""),
                        "line": model.get("line", 0),
                        "pattern": f"{model_name}.{method}",
                        "model_name": model_name,
                        "table_name": model.get("table_name"),
                        "metadata": model,
                    }
                )

        for model in getattr(self.cache, "python_orm_models", []):
            model_name = model.get("model_name", "")
            framework = model.get("framework", "sqlalchemy")

            sanitizers.append(
                {
                    "type": "orm_model",
                    "name": model_name,
                    "framework": framework,
                    "language": "python",
                    "file": model.get("file", ""),
                    "line": model.get("line", 0),
                    "pattern": model_name,
                    "table_name": model.get("table_name"),
                    "metadata": model,
                }
            )

        return sanitizers
