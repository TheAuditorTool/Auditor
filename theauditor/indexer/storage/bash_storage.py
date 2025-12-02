"""Bash storage handlers for shell script patterns."""

from .base import BaseStorage


class BashStorage(BaseStorage):
    """Bash-specific storage handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        super().__init__(db_manager, counts)

        self.handlers = {
            "bash_functions": self._store_bash_functions,
            "bash_variables": self._store_bash_variables,
            "bash_sources": self._store_bash_sources,
            "bash_commands": self._store_bash_commands,
            "bash_pipes": self._store_bash_pipes,
            "bash_subshells": self._store_bash_subshells,
            "bash_redirections": self._store_bash_redirections,
            "bash_control_flows": self._store_bash_control_flows,
            "bash_set_options": self._store_bash_set_options,
        }

    def _store_bash_functions(self, file_path: str, bash_functions: list, jsx_pass: bool) -> None:
        """Store Bash function definitions."""
        for func in bash_functions:
            self.db_manager.add_bash_function(
                file_path,
                func.get("line", 0),
                func.get("end_line", 0),
                func.get("name", ""),
                func.get("style", "posix"),
                func.get("body_start_line"),
                func.get("body_end_line"),
            )
            if "bash_functions" not in self.counts:
                self.counts["bash_functions"] = 0
            self.counts["bash_functions"] += 1

    def _store_bash_variables(self, file_path: str, bash_variables: list, jsx_pass: bool) -> None:
        """Store Bash variable assignments."""
        for var in bash_variables:
            self.db_manager.add_bash_variable(
                file_path,
                var.get("line", 0),
                var.get("name", ""),
                var.get("scope", "global"),
                var.get("readonly", False),
                var.get("value_expr"),
                var.get("containing_function"),
            )
            if "bash_variables" not in self.counts:
                self.counts["bash_variables"] = 0
            self.counts["bash_variables"] += 1

    def _store_bash_sources(self, file_path: str, bash_sources: list, jsx_pass: bool) -> None:
        """Store Bash source/dot statements."""
        for src in bash_sources:
            self.db_manager.add_bash_source(
                file_path,
                src.get("line", 0),
                src.get("sourced_path", ""),
                src.get("syntax", "source"),
                src.get("has_variable_expansion", False),
                src.get("containing_function"),
            )
            if "bash_sources" not in self.counts:
                self.counts["bash_sources"] = 0
            self.counts["bash_sources"] += 1

    def _store_bash_commands(self, file_path: str, bash_commands: list, jsx_pass: bool) -> None:
        """Store Bash command invocations and their arguments."""
        for cmd in bash_commands:
            line = cmd.get("line", 0)
            pipeline_position = cmd.get("pipeline_position")
            self.db_manager.add_bash_command(
                file_path,
                line,
                cmd.get("command_name", ""),
                pipeline_position,
                cmd.get("containing_function"),
                cmd.get("wrapped_command"),
            )
            if "bash_commands" not in self.counts:
                self.counts["bash_commands"] = 0
            self.counts["bash_commands"] += 1

            for idx, arg in enumerate(cmd.get("args", [])):
                normalized_flags = arg.get("normalized_flags")
                if normalized_flags and isinstance(normalized_flags, list):
                    normalized_flags = ",".join(normalized_flags)

                self.db_manager.add_bash_command_arg(
                    file_path,
                    line,
                    pipeline_position,
                    idx,
                    arg.get("value", ""),
                    arg.get("is_quoted", False),
                    arg.get("quote_type", "none"),
                    arg.get("has_expansion", False),
                    arg.get("expansion_vars"),
                    normalized_flags,
                )
                if "bash_command_args" not in self.counts:
                    self.counts["bash_command_args"] = 0
                self.counts["bash_command_args"] += 1

    def _store_bash_pipes(self, file_path: str, bash_pipes: list, jsx_pass: bool) -> None:
        """Store Bash pipeline connections."""
        for pipe in bash_pipes:
            self.db_manager.add_bash_pipe(
                file_path,
                pipe.get("line", 0),
                pipe.get("pipeline_id", 0),
                pipe.get("position", 0),
                pipe.get("command_text", ""),
                pipe.get("containing_function"),
            )
            if "bash_pipes" not in self.counts:
                self.counts["bash_pipes"] = 0
            self.counts["bash_pipes"] += 1

    def _store_bash_subshells(self, file_path: str, bash_subshells: list, jsx_pass: bool) -> None:
        """Store Bash command substitutions."""
        for sub in bash_subshells:
            self.db_manager.add_bash_subshell(
                file_path,
                sub.get("line", 0),
                sub.get("col", 0),
                sub.get("syntax", "dollar_paren"),
                sub.get("command_text", ""),
                sub.get("capture_target"),
                sub.get("containing_function"),
            )
            if "bash_subshells" not in self.counts:
                self.counts["bash_subshells"] = 0
            self.counts["bash_subshells"] += 1

    def _store_bash_redirections(
        self, file_path: str, bash_redirections: list, jsx_pass: bool
    ) -> None:
        """Store Bash I/O redirections."""
        for redir in bash_redirections:
            self.db_manager.add_bash_redirection(
                file_path,
                redir.get("line", 0),
                redir.get("direction", "output"),
                redir.get("target", ""),
                redir.get("fd_number"),
                redir.get("containing_function"),
            )
            if "bash_redirections" not in self.counts:
                self.counts["bash_redirections"] = 0
            self.counts["bash_redirections"] += 1

    def _store_bash_control_flows(
        self, file_path: str, bash_control_flows: list, jsx_pass: bool
    ) -> None:
        """Store Bash control flow statements (if, case, for, while, until)."""
        for cf in bash_control_flows:
            self.db_manager.add_bash_control_flow(
                file_path,
                cf.get("line", 0),
                cf.get("end_line", 0),
                cf.get("type", ""),
                cf.get("condition"),
                cf.get("has_else"),
                cf.get("case_value"),
                cf.get("num_patterns"),
                cf.get("loop_variable"),
                cf.get("iterable"),
                cf.get("loop_expression"),
                cf.get("containing_function"),
            )
            if "bash_control_flows" not in self.counts:
                self.counts["bash_control_flows"] = 0
            self.counts["bash_control_flows"] += 1

    def _store_bash_set_options(
        self, file_path: str, bash_set_options: list, jsx_pass: bool
    ) -> None:
        """Store Bash set command options."""
        for opt in bash_set_options:
            self.db_manager.add_bash_set_option(
                file_path,
                opt.get("line", 0),
                opt.get("options", ""),
                opt.get("containing_function"),
            )
            if "bash_set_options" not in self.counts:
                self.counts["bash_set_options"] = 0
            self.counts["bash_set_options"] += 1
