"""Bash-specific schema definitions."""

from .utils import Column, TableSchema

BASH_FUNCTIONS = TableSchema(
    name="bash_functions",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("style", "TEXT", nullable=False, default="'posix'"),
        Column("body_start_line", "INTEGER", nullable=True),
        Column("body_end_line", "INTEGER", nullable=True),
    ],
    primary_key=["file", "name", "line"],
    indexes=[
        ("idx_bash_functions_file", ["file"]),
        ("idx_bash_functions_name", ["name"]),
    ],
)


BASH_VARIABLES = TableSchema(
    name="bash_variables",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("name", "TEXT", nullable=False),
        Column("scope", "TEXT", nullable=False, default="'global'"),
        Column("readonly", "INTEGER", nullable=False, default="0"),
        Column("value_expr", "TEXT", nullable=True),
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "name", "line"],
    indexes=[
        ("idx_bash_variables_file", ["file"]),
        ("idx_bash_variables_name", ["name"]),
        ("idx_bash_variables_scope", ["scope"]),
    ],
)


BASH_SOURCES = TableSchema(
    name="bash_sources",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("sourced_path", "TEXT", nullable=False),
        Column("syntax", "TEXT", nullable=False, default="'source'"),
        Column("has_variable_expansion", "INTEGER", nullable=False, default="0"),
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_bash_sources_file", ["file"]),
        ("idx_bash_sources_sourced_path", ["sourced_path"]),
    ],
)


BASH_COMMANDS = TableSchema(
    name="bash_commands",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("command_name", "TEXT", nullable=False),
        Column("pipeline_position", "INTEGER", nullable=True),
        Column("containing_function", "TEXT", nullable=True),
        Column("wrapped_command", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "pipeline_position"],
    indexes=[
        ("idx_bash_commands_file", ["file"]),
        ("idx_bash_commands_name", ["command_name"]),
        ("idx_bash_commands_wrapped", ["wrapped_command"]),
    ],
)


BASH_COMMAND_ARGS = TableSchema(
    name="bash_command_args",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("command_line", "INTEGER", nullable=False),
        Column("command_pipeline_position", "INTEGER", nullable=True),
        Column("arg_index", "INTEGER", nullable=False),
        Column("arg_value", "TEXT", nullable=False),
        Column("is_quoted", "INTEGER", nullable=False, default="0"),
        Column("quote_type", "TEXT", nullable=False, default="'none'"),
        Column("has_expansion", "INTEGER", nullable=False, default="0"),
        Column("expansion_vars", "TEXT", nullable=True),
        Column("normalized_flags", "TEXT", nullable=True),
    ],
    primary_key=["file", "command_line", "command_pipeline_position", "arg_index"],
    indexes=[
        ("idx_bash_command_args_file_line", ["file", "command_line"]),
        ("idx_bash_command_args_expansion", ["has_expansion"]),
    ],
)


BASH_PIPES = TableSchema(
    name="bash_pipes",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("pipeline_id", "INTEGER", nullable=False),
        Column("position", "INTEGER", nullable=False),
        Column("command_text", "TEXT", nullable=False),
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "pipeline_id", "position"],
    indexes=[
        ("idx_bash_pipes_file", ["file"]),
        ("idx_bash_pipes_pipeline", ["file", "pipeline_id"]),
    ],
)


BASH_SUBSHELLS = TableSchema(
    name="bash_subshells",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("col", "INTEGER", nullable=False),
        Column("syntax", "TEXT", nullable=False, default="'dollar_paren'"),
        Column("command_text", "TEXT", nullable=False),
        Column("capture_target", "TEXT", nullable=True),
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "col"],
    indexes=[
        ("idx_bash_subshells_file", ["file"]),
        ("idx_bash_subshells_capture", ["capture_target"]),
    ],
)


BASH_REDIRECTIONS = TableSchema(
    name="bash_redirections",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("direction", "TEXT", nullable=False),
        Column("target", "TEXT", nullable=False),
        Column("fd_number", "INTEGER", nullable=True),
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line", "direction"],
    indexes=[
        ("idx_bash_redirections_file", ["file"]),
        ("idx_bash_redirections_direction", ["direction"]),
    ],
)


BASH_CONTROL_FLOWS = TableSchema(
    name="bash_control_flows",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("end_line", "INTEGER", nullable=False),
        Column("type", "TEXT", nullable=False),
        Column("condition", "TEXT", nullable=True),
        Column("has_else", "INTEGER", nullable=True),
        Column("case_value", "TEXT", nullable=True),
        Column("num_patterns", "INTEGER", nullable=True),
        Column("loop_variable", "TEXT", nullable=True),
        Column("iterable", "TEXT", nullable=True),
        Column("loop_expression", "TEXT", nullable=True),
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_bash_control_flows_file", ["file"]),
        ("idx_bash_control_flows_type", ["type"]),
    ],
)


BASH_SET_OPTIONS = TableSchema(
    name="bash_set_options",
    columns=[
        Column("file", "TEXT", nullable=False),
        Column("line", "INTEGER", nullable=False),
        Column("options", "TEXT", nullable=False),
        Column("containing_function", "TEXT", nullable=True),
    ],
    primary_key=["file", "line"],
    indexes=[
        ("idx_bash_set_options_file", ["file"]),
    ],
)


BASH_TABLES: dict[str, TableSchema] = {
    "bash_functions": BASH_FUNCTIONS,
    "bash_variables": BASH_VARIABLES,
    "bash_sources": BASH_SOURCES,
    "bash_commands": BASH_COMMANDS,
    "bash_command_args": BASH_COMMAND_ARGS,
    "bash_pipes": BASH_PIPES,
    "bash_subshells": BASH_SUBSHELLS,
    "bash_redirections": BASH_REDIRECTIONS,
    "bash_control_flows": BASH_CONTROL_FLOWS,
    "bash_set_options": BASH_SET_OPTIONS,
}
