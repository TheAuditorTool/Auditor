"""Bash AST extraction implementation using tree-sitter."""

from typing import Any


def extract_all_bash_data(tree: Any, content: str, file_path: str) -> dict[str, Any]:
    """Extract all Bash constructs from a tree-sitter parse tree.

    Args:
        tree: tree-sitter Tree object
        content: Original file content string
        file_path: Path to the file being parsed

    Returns:
        Dictionary with keys matching storage handler expectations:
        - bash_functions: List of function definitions
        - bash_variables: List of variable assignments
        - bash_sources: List of source/dot statements
        - bash_commands: List of command invocations with args
        - bash_pipes: List of pipeline connections
        - bash_subshells: List of command substitutions
        - bash_redirections: List of I/O redirections
    """
    extractor = BashExtractor(tree, content, file_path)
    return extractor.extract()


class BashExtractor:
    """Extracts Bash constructs from tree-sitter AST."""

    WRAPPER_COMMANDS = frozenset(
        [
            "sudo",
            "time",
            "nice",
            "nohup",
            "xargs",
            "env",
            "strace",
            "timeout",
            "watch",
            "ionice",
            "chroot",
            "su",
            "runuser",
            "doas",
            "pkexec",
            "sg",
            "newgrp",
        ]
    )

    def __init__(self, tree: Any, content: str, file_path: str):
        self.tree = tree
        self.content = content
        self.file_path = file_path
        self.lines = content.split("\n")

        self.current_function: str | None = None
        self.pipeline_counter = 0
        self.has_pipefail: bool = False
        self.has_errexit: bool = False
        self.has_nounset: bool = False

        self.functions: list[dict] = []
        self.variables: list[dict] = []
        self.sources: list[dict] = []
        self.commands: list[dict] = []
        self.pipes: list[dict] = []
        self.subshells: list[dict] = []
        self.redirections: list[dict] = []
        self.control_flows: list[dict] = []
        self.set_options: list[dict] = []

    def extract(self) -> dict[str, Any]:
        """Walk the tree and extract all constructs."""
        self._walk(self.tree.root_node)
        return {
            "bash_functions": self.functions,
            "bash_variables": self.variables,
            "bash_sources": self.sources,
            "bash_commands": self.commands,
            "bash_pipes": self.pipes,
            "bash_subshells": self.subshells,
            "bash_redirections": self.redirections,
            "bash_control_flows": self.control_flows,
            "bash_set_options": self.set_options,
            "_bash_metadata": {
                "has_pipefail": self.has_pipefail,
                "has_errexit": self.has_errexit,
                "has_nounset": self.has_nounset,
            },
        }

    def _walk(self, node: Any) -> None:
        """Recursively walk the AST."""
        node_type = node.type

        if node_type == "function_definition":
            self._extract_function(node)
        elif node_type == "variable_assignment":
            self._extract_variable(node)
        elif node_type == "declaration_command":
            self._extract_declaration(node)
        elif node_type == "concatenation":
            self._try_extract_assignment_from_concatenation(node)
        elif node_type == "pipeline":
            self._extract_pipeline(node)
        elif node_type == "command":
            self._extract_command(node)
        elif node_type == "redirected_statement":
            self._extract_redirected_statement(node)
        elif node_type == "command_substitution":
            self._extract_subshell(node)

        elif node_type == "if_statement":
            self._extract_if_statement(node)
        elif node_type == "case_statement":
            self._extract_case_statement(node)
        elif node_type == "for_statement":
            self._extract_for_statement(node)
        elif node_type == "c_style_for_statement":
            self._extract_c_style_for_statement(node)
        elif node_type == "while_statement":
            self._extract_while_statement(node)
        elif node_type == "until_statement":
            self._extract_until_statement(node)

        elif node_type == "expansion":
            self._extract_expansion(node)
        else:
            for child in node.children:
                self._walk(child)

    def _node_text(self, node: Any) -> str:
        """Get text content of a node."""
        return node.text.decode("utf-8") if node.text else ""

    def _get_line(self, node: Any) -> int:
        """Get 1-based line number of a node."""
        return node.start_point[0] + 1

    def _get_end_line(self, node: Any) -> int:
        """Get 1-based end line number of a node."""
        return node.end_point[0] + 1

    def _extract_function(self, node: Any) -> None:
        """Extract function definition."""
        name = None
        style = "posix"
        body_node = None

        for child in node.children:
            if child.type == "function":
                style = "bash"
            elif child.type == "word":
                name = self._node_text(child)
            elif child.type == "compound_statement":
                body_node = child

        if name:
            func = {
                "line": self._get_line(node),
                "end_line": self._get_end_line(node),
                "name": name,
                "style": style,
                "body_start_line": self._get_line(body_node) if body_node else None,
                "body_end_line": self._get_end_line(body_node) if body_node else None,
            }
            self.functions.append(func)

            old_function = self.current_function
            self.current_function = name
            if body_node:
                for child in body_node.children:
                    self._walk(child)
            self.current_function = old_function

    def _extract_variable(self, node: Any, scope: str = "global", readonly: bool = False) -> None:
        """Extract variable assignment."""
        name = None
        value_expr = None
        capture_target = None

        for child in node.children:
            if child.type == "variable_name":
                name = self._node_text(child)
            elif child.type == "string":
                value_expr = self._node_text(child)

                self._walk_for_nested_subshells_with_capture(child, name)
            elif child.type in (
                "raw_string",
                "word",
                "number",
                "simple_expansion",
                "array",
            ):
                value_expr = self._node_text(child)
            elif child.type == "concatenation":
                value_expr = self._node_text(child)

                self._walk_for_nested_subshells_with_capture(child, name)
            elif child.type == "expansion":
                value_expr = self._node_text(child)

                self._extract_expansion_with_capture(child, name)
            elif child.type == "command_substitution":
                value_expr = self._node_text(child)
                capture_target = name

                self._extract_subshell(child, capture_target=capture_target)

        if name:
            var = {
                "line": self._get_line(node),
                "name": name,
                "scope": scope,
                "readonly": readonly,
                "value_expr": value_expr,
                "containing_function": self.current_function,
            }
            self.variables.append(var)

    def _extract_declaration(self, node: Any) -> None:
        """Extract declaration command (local, readonly, export, etc.)."""
        scope = "global"
        readonly = False

        for child in node.children:
            if child.type in ("local", "declare"):
                scope = "local"
            elif child.type == "readonly":
                readonly = True
            elif child.type == "export":
                scope = "exported"
            elif child.type == "variable_assignment":
                self._extract_variable(child, scope=scope, readonly=readonly)

    def _try_extract_assignment_from_concatenation(self, node: Any) -> None:
        """Handle concatenation nodes that are actually variable assignments.

        tree-sitter-bash parses `VAR=$(cmd)` as a concatenation of:
        - word: "VAR="
        - command_substitution: $(cmd)

        We detect this pattern and extract it as a variable assignment.
        """
        children = list(node.children)
        if len(children) < 2:
            for child in children:
                self._walk(child)
            return

        first_child = children[0]
        if first_child.type != "word":
            for child in children:
                self._walk(child)
            return

        first_text = self._node_text(first_child)
        if not first_text.endswith("="):
            for child in children:
                self._walk(child)
            return

        name = first_text[:-1]

        value_parts = []
        capture_target = None

        for child in children[1:]:
            value_parts.append(self._node_text(child))
            if child.type == "command_substitution":
                capture_target = name
                self._extract_subshell(child, capture_target=capture_target)

        value_expr = "".join(value_parts)

        var = {
            "line": self._get_line(node),
            "name": name,
            "scope": "local" if self.current_function else "global",
            "readonly": False,
            "value_expr": value_expr,
            "containing_function": self.current_function,
        }
        self.variables.append(var)

    def _extract_command(self, node: Any, pipeline_position: int | None = None) -> None:
        """Extract command invocation."""
        command_name = None
        args: list[dict] = []

        for child in node.children:
            if child.type == "command_name":
                name_node = child.children[0] if child.children else None
                if name_node:
                    command_name = self._node_text(name_node)
            elif child.type in (
                "word",
                "string",
                "raw_string",
                "expansion",
                "simple_expansion",
                "concatenation",
                "number",
            ):
                arg_info = self._extract_arg_info(child)
                args.append(arg_info)

        if command_name:
            if command_name in ("source", "."):
                sourced_path = args[0]["value"] if args else ""
                has_expansion = any(a["has_expansion"] for a in args)
                source_rec = {
                    "line": self._get_line(node),
                    "sourced_path": sourced_path,
                    "syntax": "source" if command_name == "source" else "dot",
                    "has_variable_expansion": has_expansion,
                    "containing_function": self.current_function,
                }
                self.sources.append(source_rec)
            else:
                if command_name == "set":
                    self._check_set_command(command_name, args)

                    if self.set_options:
                        self.set_options[-1]["line"] = self._get_line(node)

                wrapped_command = None
                if command_name in self.WRAPPER_COMMANDS:
                    wrapped_command = self._find_wrapped_command(args)

                normalized_args = self._normalize_args(args)

                cmd = {
                    "line": self._get_line(node),
                    "command_name": command_name,
                    "pipeline_position": pipeline_position,
                    "containing_function": self.current_function,
                    "args": normalized_args,
                    "wrapped_command": wrapped_command,
                }
                self.commands.append(cmd)

        for child in node.children:
            if child.type == "command_substitution":
                self._extract_subshell(child)
            elif child.type in ("string", "concatenation"):
                self._walk_for_subshells(child)

    def _find_wrapped_command(self, args: list[dict]) -> str | None:
        """Find the wrapped command in a wrapper command's arguments.

        For 'sudo rm -rf /tmp', the wrapped command is 'rm'.
        Skip flags (starting with -) to find the actual command.
        """
        skip_next = False
        for arg in args:
            value = arg.get("value", "")

            if not value:
                continue

            if skip_next:
                skip_next = False
                continue

            if value.startswith("-"):
                if value in ("-u", "-n", "-c", "-e", "-E", "-H", "-p", "-g"):
                    skip_next = True
                continue

            if "=" in value:
                continue

            if value.isdigit():
                continue

            if value[0].isalpha() or value.startswith("/") or value.startswith("./"):
                return value

        return None

    def _normalize_args(self, args: list[dict]) -> list[dict]:
        """Normalize arguments, splitting combined short flags.

        Converts '-la' into ['-l', '-a'] for consistent querying.
        """
        normalized = []
        for arg in args:
            value = arg.get("value", "")

            if (
                value.startswith("-")
                and not value.startswith("--")
                and len(value) > 2
                and value[1:].isalpha()
            ):
                arg["normalized_flags"] = [f"-{c}" for c in value[1:]]
            else:
                arg["normalized_flags"] = None
            normalized.append(arg)
        return normalized

    def _extract_arg_info(self, node: Any) -> dict:
        """Extract argument information."""
        value = self._node_text(node)
        is_quoted = node.type in ("string", "raw_string")
        quote_type = "none"
        has_expansion = False
        expansion_vars: list[str] = []

        if node.type == "string":
            quote_type = "double"
            has_expansion, expansion_vars = self._check_expansions(node)
        elif node.type == "raw_string":
            quote_type = "single"

        elif node.type in ("expansion", "simple_expansion"):
            has_expansion = True
            expansion_vars = self._get_expansion_vars(node)
        elif node.type == "concatenation":
            has_expansion, expansion_vars = self._check_expansions(node)

        return {
            "value": value,
            "is_quoted": is_quoted,
            "quote_type": quote_type,
            "has_expansion": has_expansion,
            "expansion_vars": ",".join(expansion_vars) if expansion_vars else None,
        }

    def _check_expansions(self, node: Any) -> tuple[bool, list[str]]:
        """Check if node contains variable expansions."""
        vars_found: list[str] = []

        def walk(n: Any) -> None:
            if n.type in ("simple_expansion", "expansion"):
                vars_found.extend(self._get_expansion_vars(n))
            for child in n.children:
                walk(child)

        walk(node)
        return len(vars_found) > 0, vars_found

    def _get_expansion_vars(self, node: Any) -> list[str]:
        """Get variable names from expansion node."""
        vars_found = []
        for child in node.children:
            if child.type == "variable_name" or child.type == "special_variable_name":
                vars_found.append(self._node_text(child))
        return vars_found

    def _walk_for_subshells(self, node: Any) -> None:
        """Walk node looking only for command substitutions."""
        if node.type == "command_substitution":
            self._extract_subshell(node)
        for child in node.children:
            self._walk_for_subshells(child)

    def _extract_pipeline(self, node: Any) -> None:
        """Extract pipeline (piped commands)."""
        self.pipeline_counter += 1
        pipeline_id = self.pipeline_counter
        position = 0

        for child in node.children:
            if child.type == "command":
                command_text = self._node_text(child)
                pipe_rec = {
                    "line": self._get_line(child),
                    "pipeline_id": pipeline_id,
                    "position": position,
                    "command_text": command_text,
                    "containing_function": self.current_function,
                }
                self.pipes.append(pipe_rec)

                self._extract_command(child, pipeline_position=position)
                position += 1
            elif child.type == "redirected_statement":
                self._extract_redirected_statement(
                    child, pipeline_id=pipeline_id, position=position
                )
                position += 1
            elif child.type == "pipeline":
                self._extract_pipeline(child)

    def _extract_subshell(self, node: Any, capture_target: str | None = None) -> None:
        """Extract command substitution."""
        syntax = "dollar_paren"
        command_text = ""

        for child in node.children:
            if child.type == "`":
                syntax = "backtick"
            elif child.type == "command" or child.type == "pipeline" or child.type == "compound_statement":
                command_text = self._node_text(child)

        subshell = {
            "line": self._get_line(node),
            "col": node.start_point[1],
            "syntax": syntax,
            "command_text": command_text,
            "capture_target": capture_target,
            "containing_function": self.current_function,
        }
        self.subshells.append(subshell)

        for child in node.children:
            if child.type == "command":
                self._walk(child)

    def _extract_redirected_statement(
        self, node: Any, pipeline_id: int | None = None, position: int | None = None
    ) -> None:
        """Extract redirected statement with redirections."""
        for child in node.children:
            if child.type == "command":
                self._extract_command(child, pipeline_position=position)
                if pipeline_id is not None:
                    command_text = self._node_text(child)
                    pipe_rec = {
                        "line": self._get_line(child),
                        "pipeline_id": pipeline_id,
                        "position": position,
                        "command_text": command_text,
                        "containing_function": self.current_function,
                    }
                    self.pipes.append(pipe_rec)
            elif child.type == "pipeline":
                self._extract_pipeline(child)
            elif child.type == "file_redirect":
                self._extract_redirect(child)
            elif child.type == "heredoc_redirect":
                self._extract_heredoc_redirect(child)

    def _extract_redirect(self, node: Any) -> None:
        """Extract file redirect."""
        direction = "output"
        target = ""
        fd_number = None

        for child in node.children:
            if child.type == "file_descriptor":
                fd_number = int(self._node_text(child))
            elif child.type in (">", ">>"):
                direction = "output"
            elif child.type == "<":
                direction = "input"
            elif child.type == ">&":
                direction = "fd_dup"
            elif child.type == "word" or child.type == "number":
                target = self._node_text(child)

        redir = {
            "line": self._get_line(node),
            "direction": direction,
            "target": target,
            "fd_number": fd_number,
            "containing_function": self.current_function,
        }
        self.redirections.append(redir)

    def _extract_heredoc_redirect(self, node: Any) -> None:
        """Extract heredoc redirect with quoting detection (Task 2.3.6)."""

        delimiter = ""
        is_quoted = False

        for child in node.children:
            if child.type == "heredoc_start":
                delimiter_text = self._node_text(child)

                is_quoted = (
                    delimiter_text.startswith("'")
                    or delimiter_text.startswith('"')
                    or delimiter_text.startswith("\\")
                )

                delimiter = delimiter_text.strip("'\"\\")
            elif child.type == "heredoc_body":
                if not is_quoted:
                    self._walk_for_expansions_in_heredoc(child)

        redir = {
            "line": self._get_line(node),
            "direction": "heredoc",
            "target": delimiter,
            "fd_number": None,
            "containing_function": self.current_function,
            "heredoc_quoted": is_quoted,
        }
        self.redirections.append(redir)

    def _walk_for_expansions_in_heredoc(self, node: Any) -> None:
        """Walk heredoc body looking for variable expansions (Task 2.3.6)."""
        if node.type in ("simple_expansion", "expansion"):
            pass
        elif node.type == "command_substitution":
            self._extract_subshell(node)
        for child in node.children:
            self._walk_for_expansions_in_heredoc(child)

    def _extract_if_statement(self, node: Any) -> None:
        """Extract if statement control flow."""
        condition_text = ""
        has_else = False

        for child in node.children:
            if child.type == "test_command":
                condition_text = self._node_text(child)
            elif child.type in ("elif_clause", "else_clause"):
                has_else = True

        cf = {
            "line": self._get_line(node),
            "end_line": self._get_end_line(node),
            "type": "if",
            "condition": condition_text,
            "has_else": has_else,
            "containing_function": self.current_function,
        }
        self.control_flows.append(cf)

        for child in node.children:
            self._walk(child)

    def _extract_case_statement(self, node: Any) -> None:
        """Extract case statement control flow."""
        case_value = ""
        num_patterns = 0

        for child in node.children:
            if child.type == "word":
                case_value = self._node_text(child)
            elif child.type == "case_item":
                num_patterns += 1

        cf = {
            "line": self._get_line(node),
            "end_line": self._get_end_line(node),
            "type": "case",
            "case_value": case_value,
            "num_patterns": num_patterns,
            "containing_function": self.current_function,
        }
        self.control_flows.append(cf)

        for child in node.children:
            self._walk(child)

    def _extract_for_statement(self, node: Any) -> None:
        """Extract for loop control flow."""
        loop_var = ""
        iterable = ""

        for child in node.children:
            if child.type == "variable_name":
                loop_var = self._node_text(child)
            elif child.type in ("word", "string", "concatenation", "expansion"):
                if not iterable:
                    iterable = self._node_text(child)

        cf = {
            "line": self._get_line(node),
            "end_line": self._get_end_line(node),
            "type": "for",
            "loop_variable": loop_var,
            "iterable": iterable,
            "containing_function": self.current_function,
        }
        self.control_flows.append(cf)

        for child in node.children:
            self._walk(child)

    def _extract_c_style_for_statement(self, node: Any) -> None:
        """Extract C-style for loop."""
        cf = {
            "line": self._get_line(node),
            "end_line": self._get_end_line(node),
            "type": "c_for",
            "loop_expression": self._node_text(node),
            "containing_function": self.current_function,
        }
        self.control_flows.append(cf)

        for child in node.children:
            self._walk(child)

    def _extract_while_statement(self, node: Any) -> None:
        """Extract while loop control flow."""
        condition_text = ""

        for child in node.children:
            if child.type == "test_command":
                condition_text = self._node_text(child)

        cf = {
            "line": self._get_line(node),
            "end_line": self._get_end_line(node),
            "type": "while",
            "condition": condition_text,
            "containing_function": self.current_function,
        }
        self.control_flows.append(cf)

        for child in node.children:
            self._walk(child)

    def _extract_until_statement(self, node: Any) -> None:
        """Extract until loop control flow."""
        condition_text = ""

        for child in node.children:
            if child.type == "test_command":
                condition_text = self._node_text(child)

        cf = {
            "line": self._get_line(node),
            "end_line": self._get_end_line(node),
            "type": "until",
            "condition": condition_text,
            "containing_function": self.current_function,
        }
        self.control_flows.append(cf)

        for child in node.children:
            self._walk(child)

    def _extract_expansion(self, node: Any) -> None:
        """Handle parameter expansion with possible nested command substitution.

        Handles patterns like: ${VAR:-$(cat file | grep "stuff")}
        The command substitution inside must be recursively extracted.
        """
        self._extract_expansion_with_capture(node, capture_target=None)

    def _extract_expansion_with_capture(self, node: Any, capture_target: str | None) -> None:
        """Walk expansion looking for nested command substitutions.

        Args:
            node: The expansion node to walk
            capture_target: The variable name that captures the result (if any)
        """
        for child in node.children:
            if child.type == "command_substitution":
                self._extract_subshell(child, capture_target=capture_target)
            elif child.type == "expansion":
                self._extract_expansion_with_capture(child, capture_target)
            elif child.type == "pipeline":
                self._walk(child)
            else:
                self._walk_for_nested_subshells_with_capture(child, capture_target)

    def _walk_for_nested_subshells_with_capture(
        self, node: Any, capture_target: str | None
    ) -> None:
        """Recursively walk looking for command substitutions with capture context."""
        if node.type == "command_substitution":
            self._extract_subshell(node, capture_target=capture_target)
        elif node.type == "expansion":
            self._extract_expansion_with_capture(node, capture_target)
        else:
            for child in node.children:
                self._walk_for_nested_subshells_with_capture(child, capture_target)

    def _walk_for_nested_subshells(self, node: Any) -> None:
        """Recursively walk looking for command substitutions in any context."""
        if node.type == "command_substitution":
            self._extract_subshell(node)
        elif node.type == "expansion":
            self._extract_expansion(node)
        else:
            for child in node.children:
                self._walk_for_nested_subshells(child)

    def _check_set_command(self, command_name: str, args: list[dict]) -> None:
        """Track set command options for safety flag detection."""
        if command_name != "set":
            return

        options = []
        for i, arg in enumerate(args):
            value = arg.get("value", "")
            options.append(value)

            if value in ("-e", "-o errexit"):
                self.has_errexit = True
            elif value in ("-u", "-o nounset"):
                self.has_nounset = True
            elif value == "-o" and i + 1 < len(args):
                next_arg = args[i + 1].get("value", "")
                if next_arg == "pipefail":
                    self.has_pipefail = True
                elif next_arg == "errexit":
                    self.has_errexit = True
                elif next_arg == "nounset":
                    self.has_nounset = True
            elif "pipefail" in value:
                self.has_pipefail = True

            elif value.startswith("-") and not value.startswith("--"):
                flags = value[1:]
                if "e" in flags:
                    self.has_errexit = True
                if "u" in flags:
                    self.has_nounset = True

        set_rec = {
            "line": 0,
            "options": ",".join(options),
            "containing_function": self.current_function,
        }
        self.set_options.append(set_rec)
