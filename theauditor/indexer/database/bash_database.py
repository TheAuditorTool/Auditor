"""Bash-specific database operations."""


class BashDatabaseMixin:
    """Mixin providing add_* methods for BASH_TABLES."""

    def add_bash_function(
        self,
        file_path: str,
        line: int,
        end_line: int,
        name: str,
        style: str,
        body_start_line: int | None,
        body_end_line: int | None,
    ) -> None:
        """Add a Bash function definition to the batch."""
        self.generic_batches["bash_functions"].append(
            (
                file_path,
                line,
                end_line,
                name,
                style,
                body_start_line,
                body_end_line,
            )
        )

    def add_bash_variable(
        self,
        file_path: str,
        line: int,
        name: str,
        scope: str,
        readonly: bool,
        value_expr: str | None,
        containing_function: str | None,
    ) -> None:
        """Add a Bash variable assignment to the batch."""
        self.generic_batches["bash_variables"].append(
            (
                file_path,
                line,
                name,
                scope,
                1 if readonly else 0,
                value_expr,
                containing_function,
            )
        )

    def add_bash_source(
        self,
        file_path: str,
        line: int,
        sourced_path: str,
        syntax: str,
        has_variable_expansion: bool,
        containing_function: str | None,
    ) -> None:
        """Add a Bash source/dot statement to the batch."""
        self.generic_batches["bash_sources"].append(
            (
                file_path,
                line,
                sourced_path,
                syntax,
                1 if has_variable_expansion else 0,
                containing_function,
            )
        )

    def add_bash_command(
        self,
        file_path: str,
        line: int,
        command_name: str,
        pipeline_position: int | None,
        containing_function: str | None,
        wrapped_command: str | None,
    ) -> None:
        """Add a Bash command invocation to the batch."""
        self.generic_batches["bash_commands"].append(
            (
                file_path,
                line,
                command_name,
                pipeline_position,
                containing_function,
                wrapped_command,
            )
        )

    def add_bash_command_arg(
        self,
        file_path: str,
        command_line: int,
        command_pipeline_position: int | None,
        arg_index: int,
        arg_value: str,
        is_quoted: bool,
        quote_type: str,
        has_expansion: bool,
        expansion_vars: str | None,
        normalized_flags: str | None,
    ) -> None:
        """Add a Bash command argument to the batch."""
        self.generic_batches["bash_command_args"].append(
            (
                file_path,
                command_line,
                command_pipeline_position,
                arg_index,
                arg_value,
                1 if is_quoted else 0,
                quote_type,
                1 if has_expansion else 0,
                expansion_vars,
                normalized_flags,
            )
        )

    def add_bash_pipe(
        self,
        file_path: str,
        line: int,
        pipeline_id: int,
        position: int,
        command_text: str,
        containing_function: str | None,
    ) -> None:
        """Add a Bash pipeline component to the batch."""
        self.generic_batches["bash_pipes"].append(
            (
                file_path,
                line,
                pipeline_id,
                position,
                command_text,
                containing_function,
            )
        )

    def add_bash_subshell(
        self,
        file_path: str,
        line: int,
        col: int,
        syntax: str,
        command_text: str,
        capture_target: str | None,
        containing_function: str | None,
    ) -> None:
        """Add a Bash command substitution to the batch."""
        self.generic_batches["bash_subshells"].append(
            (
                file_path,
                line,
                col,
                syntax,
                command_text,
                capture_target,
                containing_function,
            )
        )

    def add_bash_redirection(
        self,
        file_path: str,
        line: int,
        direction: str,
        target: str,
        fd_number: int | None,
        containing_function: str | None,
    ) -> None:
        """Add a Bash I/O redirection to the batch."""
        self.generic_batches["bash_redirections"].append(
            (
                file_path,
                line,
                direction,
                target,
                fd_number,
                containing_function,
            )
        )

    def add_bash_control_flow(
        self,
        file_path: str,
        line: int,
        end_line: int,
        flow_type: str,
        condition: str | None,
        has_else: bool | None,
        case_value: str | None,
        num_patterns: int | None,
        loop_variable: str | None,
        iterable: str | None,
        loop_expression: str | None,
        containing_function: str | None,
    ) -> None:
        """Add a Bash control flow statement to the batch."""
        self.generic_batches["bash_control_flows"].append(
            (
                file_path,
                line,
                end_line,
                flow_type,
                condition,
                1 if has_else else (0 if has_else is not None else None),
                case_value,
                num_patterns,
                loop_variable,
                iterable,
                loop_expression,
                containing_function,
            )
        )

    def add_bash_set_option(
        self,
        file_path: str,
        line: int,
        options: str,
        containing_function: str | None,
    ) -> None:
        """Add a Bash set command options to the batch."""
        self.generic_batches["bash_set_options"].append(
            (
                file_path,
                line,
                options,
                containing_function,
            )
        )
