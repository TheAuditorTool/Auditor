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

    # Wrapper commands that execute another command
    WRAPPER_COMMANDS = frozenset([
        "sudo", "time", "nice", "nohup", "xargs", "env", "strace",
        "timeout", "watch", "ionice", "chroot", "su", "runuser",
        "doas", "pkexec", "sg", "newgrp",
    ])

    def __init__(self, tree: Any, content: str, file_path: str):
        self.tree = tree
        self.content = content
        self.file_path = file_path
        self.lines = content.split("\n")

        # Track context during traversal
        self.current_function: str | None = None
        self.pipeline_counter = 0
        self.has_pipefail: bool = False  # Track if script uses pipefail
        self.has_errexit: bool = False   # Track if script uses -e
        self.has_nounset: bool = False   # Track if script uses -u

        # Results
        self.functions: list[dict] = []
        self.variables: list[dict] = []
        self.sources: list[dict] = []
        self.commands: list[dict] = []
        self.pipes: list[dict] = []
        self.subshells: list[dict] = []
        self.redirections: list[dict] = []
        self.control_flows: list[dict] = []  # For if/case/for/while
        self.set_options: list[dict] = []    # For set command tracking

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
            # Script-level metadata for safety flags
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
            # Handle edge case: VAR=$(cmd) parsed as concatenation of "VAR=" + $(cmd)
            self._try_extract_assignment_from_concatenation(node)
        elif node_type == "pipeline":
            self._extract_pipeline(node)
        elif node_type == "command":
            self._extract_command(node)
        elif node_type == "redirected_statement":
            self._extract_redirected_statement(node)
        elif node_type == "command_substitution":
            self._extract_subshell(node)
        # Control flow statements (Task 2.4)
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
        # Handle expansion nodes for nested command substitutions (Task 2.2.4)
        elif node_type == "expansion":
            self._extract_expansion(node)
        else:
            # Continue walking for other node types
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

    # =========================================================================
    # FUNCTION EXTRACTION
    # =========================================================================
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

            # Walk function body with context
            old_function = self.current_function
            self.current_function = name
            if body_node:
                for child in body_node.children:
                    self._walk(child)
            self.current_function = old_function

    # =========================================================================
    # VARIABLE EXTRACTION
    # =========================================================================
    def _extract_variable(self, node: Any, scope: str = "global", readonly: bool = False) -> None:
        """Extract variable assignment."""
        name = None
        value_expr = None
        capture_target = None

        for child in node.children:
            if child.type == "variable_name":
                name = self._node_text(child)
            elif child.type == "string":
                # Double-quoted string - may contain expansions with nested subshells
                value_expr = self._node_text(child)
                # Walk into string to find nested command substitutions (Task 2.2.4 DRAGON)
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
                # Walk into concatenation for nested subshells
                self._walk_for_nested_subshells_with_capture(child, name)
            elif child.type == "expansion":
                # Handle parameter expansion - may contain nested command substitution
                value_expr = self._node_text(child)
                # Walk into expansion for nested subshells (Task 2.2.4 DRAGON)
                self._extract_expansion_with_capture(child, name)
            elif child.type == "command_substitution":
                value_expr = self._node_text(child)
                capture_target = name
                # Also record the subshell
                self._extract_subshell(child, capture_target=capture_target)

        if name:
            # Use the provided scope (exported, local, global)
            # Only default to "global" if no explicit scope was given
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
            # Not an assignment pattern, continue walking
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

        # This is an assignment: VAR=value
        name = first_text[:-1]  # Remove trailing =

        # Collect the rest as value
        value_parts = []
        capture_target = None
        has_subshell = False

        for child in children[1:]:
            value_parts.append(self._node_text(child))
            if child.type == "command_substitution":
                has_subshell = True
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

    # =========================================================================
    # COMMAND EXTRACTION
    # =========================================================================
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
            # Check for source/dot commands
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
                # Check for set command (Task 2.1.4 - pipefail context)
                if command_name == "set":
                    self._check_set_command(command_name, args)
                    # Update the set_options record with correct line
                    if self.set_options:
                        self.set_options[-1]["line"] = self._get_line(node)

                # Wrapper unwrapping: detect wrapped command
                wrapped_command = None
                if command_name in self.WRAPPER_COMMANDS:
                    wrapped_command = self._find_wrapped_command(args)

                # Normalize flags in args
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

        # Continue walking for nested constructs (subshells in args)
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
            # Skip empty values
            if not value:
                continue

            # If previous was a flag that takes an argument, skip this one
            if skip_next:
                skip_next = False
                continue

            # Skip flags
            if value.startswith("-"):
                # Flags that take arguments (skip the next value too)
                if value in ("-u", "-n", "-c", "-e", "-E", "-H", "-p", "-g"):
                    skip_next = True
                continue

            # Skip common wrapper options that take arguments
            # (e.g., env VAR=val)
            if "=" in value:
                continue

            # Skip numeric values (e.g., nice priority)
            if value.isdigit():
                continue

            # This looks like a command - must start with letter or be a path
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
            # Check for combined short flags: -la, -rf, etc.
            # Must start with single dash, not double dash, and be 3+ chars
            if (
                value.startswith("-")
                and not value.startswith("--")
                and len(value) > 2
                and value[1:].isalpha()
            ):
                # Split into individual flags
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
            # Single quotes don't expand
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
            if child.type == "variable_name":
                vars_found.append(self._node_text(child))
            elif child.type == "special_variable_name":
                vars_found.append(self._node_text(child))
        return vars_found

    def _walk_for_subshells(self, node: Any) -> None:
        """Walk node looking only for command substitutions."""
        if node.type == "command_substitution":
            self._extract_subshell(node)
        for child in node.children:
            self._walk_for_subshells(child)

    # =========================================================================
    # PIPELINE EXTRACTION
    # =========================================================================
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
                # Also extract as command
                self._extract_command(child, pipeline_position=position)
                position += 1
            elif child.type == "redirected_statement":
                # Handle final command in pipeline with redirect
                self._extract_redirected_statement(child, pipeline_id=pipeline_id, position=position)
                position += 1
            elif child.type == "pipeline":
                # Nested pipeline - recursively extract
                self._extract_pipeline(child)

    # =========================================================================
    # SUBSHELL EXTRACTION
    # =========================================================================
    def _extract_subshell(self, node: Any, capture_target: str | None = None) -> None:
        """Extract command substitution."""
        syntax = "dollar_paren"
        command_text = ""

        # Determine syntax and extract command text
        for child in node.children:
            if child.type == "`":
                syntax = "backtick"
            elif child.type == "command":
                command_text = self._node_text(child)
            elif child.type == "pipeline":
                # Handle pipelines inside command substitution
                command_text = self._node_text(child)
            elif child.type == "compound_statement":
                # Handle compound statements like { cmd1; cmd2; }
                command_text = self._node_text(child)

        subshell = {
            "line": self._get_line(node),
            "col": node.start_point[1],  # Column position for uniqueness
            "syntax": syntax,
            "command_text": command_text,
            "capture_target": capture_target,
            "containing_function": self.current_function,
        }
        self.subshells.append(subshell)

        # Walk into command substitution for nested constructs
        for child in node.children:
            if child.type == "command":
                self._walk(child)

    # =========================================================================
    # REDIRECTION EXTRACTION
    # =========================================================================
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
            elif child.type == "word":
                target = self._node_text(child)
            elif child.type == "number":
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
        # Detect if delimiter is quoted (affects variable expansion)
        delimiter = ""
        is_quoted = False

        for child in node.children:
            if child.type == "heredoc_start":
                delimiter_text = self._node_text(child)
                # Check if delimiter is quoted (has quotes around it)
                is_quoted = (
                    delimiter_text.startswith("'") or
                    delimiter_text.startswith('"') or
                    delimiter_text.startswith("\\")
                )
                # Store the delimiter without quotes for target
                delimiter = delimiter_text.strip("'\"\\")
            elif child.type == "heredoc_body":
                # If unquoted, walk for expansions
                if not is_quoted:
                    self._walk_for_expansions_in_heredoc(child)

        redir = {
            "line": self._get_line(node),
            "direction": "heredoc",
            "target": delimiter,
            "fd_number": None,
            "containing_function": self.current_function,
            "heredoc_quoted": is_quoted,  # True means no variable expansion
        }
        self.redirections.append(redir)

    def _walk_for_expansions_in_heredoc(self, node: Any) -> None:
        """Walk heredoc body looking for variable expansions (Task 2.3.6)."""
        if node.type in ("simple_expansion", "expansion"):
            # Found a variable expansion in unquoted heredoc
            # This is a potential security concern
            pass  # The extraction is already recorded via normal expansion handling
        elif node.type == "command_substitution":
            self._extract_subshell(node)
        for child in node.children:
            self._walk_for_expansions_in_heredoc(child)

    # =========================================================================
    # CONTROL FLOW EXTRACTION (Task 2.4)
    # =========================================================================
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

        # Continue walking into branches
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

        # Continue walking into case items
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

        # Continue walking into loop body
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

    # =========================================================================
    # NESTED EXPANSION RECURSION (Task 2.2.4 - DRAGON)
    # =========================================================================
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
                # Found nested command substitution!
                self._extract_subshell(child, capture_target=capture_target)
            elif child.type == "expansion":
                # Recursive expansion: ${${VAR}} or nested defaults
                self._extract_expansion_with_capture(child, capture_target)
            elif child.type == "pipeline":
                # Pipeline inside expansion - walk for subshells
                self._walk(child)
            else:
                # Continue looking in other children
                self._walk_for_nested_subshells_with_capture(child, capture_target)

    def _walk_for_nested_subshells_with_capture(self, node: Any, capture_target: str | None) -> None:
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

    # =========================================================================
    # SET COMMAND TRACKING (Task 2.1.4 - pipefail context)
    # =========================================================================
    def _check_set_command(self, command_name: str, args: list[dict]) -> None:
        """Track set command options for safety flag detection."""
        if command_name != "set":
            return

        options = []
        for i, arg in enumerate(args):
            value = arg.get("value", "")
            options.append(value)

            # Track safety flags
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
            # Handle combined flags like -euo, -eu, -eux, etc.
            elif value.startswith("-") and not value.startswith("--"):
                flags = value[1:]  # Strip leading dash
                if "e" in flags:
                    self.has_errexit = True
                if "u" in flags:
                    self.has_nounset = True
                # Note: pipefail can't be in combined flags, requires -o pipefail

        # Record set command for later analysis
        set_rec = {
            "line": 0,  # Will be set by caller
            "options": ",".join(options),
            "containing_function": self.current_function,
        }
        self.set_options.append(set_rec)
