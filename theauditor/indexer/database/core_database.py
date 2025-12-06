"""Core database operations for language-agnostic patterns."""

import os

from theauditor.utils.logging import logger


class CoreDatabaseMixin:
    """Mixin providing add_* methods for CORE_TABLES."""

    def add_file(self, path: str, sha256: str, ext: str, bytes_size: int, loc: int):
        """Add a file record to the batch."""
        self.generic_batches["files"].append((path, sha256, ext, bytes_size, loc))

    def add_ref(self, src: str, kind: str, value: str, line: int | None = None):
        """Add a reference record to the batch."""
        self.generic_batches["refs"].append((src, kind, value, line))

    def add_symbol(
        self,
        path: str,
        name: str,
        symbol_type: str,
        line: int,
        col: int,
        end_line: int | None = None,
        type_annotation: str | None = None,
        parameters: str | None = None,
        is_typed: bool | None = None,
    ):
        """Add a symbol record to the batch."""

        symbol_key = (path, name, symbol_type, line, col)

        for s in reversed(self.generic_batches["symbols"]):
            if (s[0], s[1], s[2], s[3], s[4]) == symbol_key:
                logger.debug(
                    f"[CoreDatabase] DEDUP: Dropping duplicate symbol: {path}:{line} {name} ({symbol_type})"
                )
                return

        self.generic_batches["symbols"].append(
            (path, name, symbol_type, line, col, end_line, type_annotation, parameters, is_typed)
        )

    def add_assignment(
        self,
        file_path: str,
        line: int,
        target_var: str,
        source_expr: str,
        source_vars: list[str],
        in_function: str,
        property_path: str | None = None,
        col: int = 0,
    ):
        """Add a variable assignment record to the batch."""

        if os.environ.get("THEAUDITOR_TRACE_DUPLICATES"):
            batch_idx = len(self.generic_batches["assignments"])

            logger.trace(
                f"add_assignment() call #{batch_idx}: {file_path}:{line}:{col} {target_var} in {in_function}"
            )

        self.generic_batches["assignments"].append(
            (file_path, line, col, target_var, source_expr, in_function, property_path)
        )

        if source_vars:
            for source_var in source_vars:
                if not source_var:
                    continue
                self.generic_batches["assignment_sources"].append(
                    (file_path, line, col, target_var, source_var)
                )

    def add_function_call_arg(
        self,
        file_path: str,
        line: int,
        caller_function: str,
        callee_function: str,
        arg_index: int,
        arg_expr: str,
        param_name: str,
        callee_file_path: str | None = None,
    ):
        """Add a function call argument record to the batch."""
        self.generic_batches["function_call_args"].append(
            (
                file_path,
                line,
                caller_function,
                callee_function,
                arg_index,
                arg_expr,
                param_name,
                callee_file_path,
            )
        )

    def add_function_return(
        self,
        file_path: str,
        line: int,
        function_name: str,
        return_expr: str,
        return_vars: list[str],
        col: int = 0,
    ):
        """Add a function return statement record to the batch."""

        self.generic_batches["function_returns"].append(
            (file_path, line, col, function_name, return_expr)
        )

        if return_vars:
            for return_var in return_vars:
                if not return_var:
                    continue
                self.generic_batches["function_return_sources"].append(
                    (file_path, line, col, function_name, return_var)
                )

    def add_config_file(self, path: str, content: str, file_type: str, context: str | None = None):
        """Add a configuration file content to the batch."""
        self.generic_batches["config_files"].append((path, content, file_type, context))

    def add_cfg_block(
        self,
        file_path: str,
        function_name: str,
        block_type: str,
        start_line: int,
        end_line: int,
        condition_expr: str | None = None,
    ) -> int:
        """Add a CFG block to the batch and return its temporary ID."""

        batch = self.generic_batches["cfg_blocks"]
        temp_id = -(len(batch) + 1)
        batch.append(
            (file_path, function_name, block_type, start_line, end_line, condition_expr, temp_id)
        )
        return temp_id

    def add_cfg_edge(
        self,
        file_path: str,
        function_name: str,
        source_block_id: int,
        target_block_id: int,
        edge_type: str,
    ):
        """Add a CFG edge to the batch."""
        self.generic_batches["cfg_edges"].append(
            (file_path, function_name, source_block_id, target_block_id, edge_type)
        )

    def add_cfg_statement(
        self, block_id: int, statement_type: str, line: int, statement_text: str | None = None
    ):
        """Add a CFG block statement to the batch."""
        self.generic_batches["cfg_block_statements"].append(
            (block_id, statement_type, line, statement_text)
        )

    def add_cfg_block_jsx(
        self,
        file_path: str,
        function_name: str,
        block_type: str,
        start_line: int,
        end_line: int,
        condition_expr: str | None = None,
        jsx_mode: str = "preserved",
        extraction_pass: int = 2,
    ) -> int:
        """Add a CFG block to the JSX batch and return its temporary ID."""
        batch = self.generic_batches["cfg_blocks_jsx"]
        temp_id = -(len(batch) + 1)
        batch.append(
            (
                file_path,
                function_name,
                block_type,
                start_line,
                end_line,
                condition_expr,
                jsx_mode,
                extraction_pass,
                temp_id,
            )
        )
        return temp_id

    def add_cfg_edge_jsx(
        self,
        file_path: str,
        function_name: str,
        source_block_id: int,
        target_block_id: int,
        edge_type: str,
        jsx_mode: str = "preserved",
        extraction_pass: int = 2,
    ):
        """Add a CFG edge to the JSX batch."""
        self.generic_batches["cfg_edges_jsx"].append(
            (
                file_path,
                function_name,
                source_block_id,
                target_block_id,
                edge_type,
                jsx_mode,
                extraction_pass,
            )
        )

    def add_cfg_statement_jsx(
        self,
        block_id: int,
        statement_type: str,
        line: int,
        statement_text: str | None = None,
        jsx_mode: str = "preserved",
        extraction_pass: int = 2,
    ):
        """Add a CFG block statement to the JSX batch."""
        self.generic_batches["cfg_block_statements_jsx"].append(
            (block_id, statement_type, line, statement_text, jsx_mode, extraction_pass)
        )

    def add_variable_usage(
        self,
        file_path: str,
        line: int,
        variable_name: str,
        usage_type: str,
        in_component: str | None = None,
        in_hook: str | None = None,
        scope_level: int = 0,
    ):
        """Add a variable usage record to the batch."""
        self.generic_batches["variable_usage"].append(
            (
                file_path,
                line,
                variable_name,
                usage_type,
                in_component or "",
                in_hook or "",
                scope_level,
            )
        )

    def add_object_literal(
        self,
        file_path: str,
        line: int,
        variable_name: str,
        property_name: str,
        property_value: str,
        property_type: str,
        nested_level: int = 0,
        in_function: str = "",
    ):
        """Add object literal property-function mapping to batch."""
        self.generic_batches["object_literals"].append(
            (
                file_path,
                line,
                variable_name,
                property_name,
                property_value,
                property_type,
                nested_level,
                in_function,
            )
        )

    def add_function_return_jsx(
        self,
        file_path: str,
        line: int,
        function_name: str,
        return_expr: str,
        return_vars: list[str],
        has_jsx: bool = False,
        returns_component: bool = False,
        cleanup_operations: str | None = None,
        jsx_mode: str = "preserved",
        extraction_pass: int = 1,
    ):
        """Add a JSX function return record for preserved JSX extraction."""

        self.generic_batches["function_returns_jsx"].append(
            (
                file_path,
                line,
                function_name,
                return_expr,
                has_jsx,
                returns_component,
                cleanup_operations,
                jsx_mode,
                extraction_pass,
            )
        )

        if return_vars:
            for return_var in return_vars:
                if not return_var:
                    continue

                self.generic_batches["function_return_sources_jsx"].append(
                    (file_path, line, function_name, jsx_mode, return_var, extraction_pass)
                )

    def add_symbol_jsx(
        self,
        path: str,
        name: str,
        symbol_type: str,
        line: int,
        col: int,
        jsx_mode: str = "preserved",
        extraction_pass: int = 1,
    ):
        """Add a JSX symbol record for preserved JSX extraction."""
        self.generic_batches["symbols_jsx"].append(
            (path, name, symbol_type, line, col, jsx_mode, extraction_pass)
        )

    def add_assignment_jsx(
        self,
        file_path: str,
        line: int,
        target_var: str,
        source_expr: str,
        source_vars: list[str],
        in_function: str,
        property_path: str | None = None,
        jsx_mode: str = "preserved",
        extraction_pass: int = 1,
    ):
        """Add a JSX assignment record for preserved JSX extraction."""

        self.generic_batches["assignments_jsx"].append(
            (
                file_path,
                line,
                target_var,
                source_expr,
                in_function,
                property_path,
                jsx_mode,
                extraction_pass,
            )
        )

        if source_vars:
            for source_var in source_vars:
                if not source_var:
                    continue
                self.generic_batches["assignment_sources_jsx"].append(
                    (file_path, line, target_var, jsx_mode, source_var)
                )

    def add_function_call_arg_jsx(
        self,
        file_path: str,
        line: int,
        caller_function: str,
        callee_function: str,
        arg_index: int,
        arg_expr: str,
        param_name: str,
        jsx_mode: str = "preserved",
        extraction_pass: int = 1,
    ):
        """Add a JSX function call argument record for preserved JSX extraction."""
        self.generic_batches["function_call_args_jsx"].append(
            (
                file_path,
                line,
                caller_function,
                callee_function,
                arg_index,
                arg_expr,
                param_name,
                jsx_mode,
                extraction_pass,
            )
        )
