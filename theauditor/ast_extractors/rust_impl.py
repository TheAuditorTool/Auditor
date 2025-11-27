"""Rust AST extraction implementation using tree-sitter.

This module provides the 12 required extraction methods for Rust,
matching the interface of python_impl.py and typescript_impl.py.

All extraction is AST-based using tree-sitter-rust. NO REGEX.

Tree-sitter Rust Node Types:
- function_item: fn declarations
- struct_item: struct definitions
- enum_item: enum definitions
- impl_item: impl blocks
- trait_item: trait definitions
- use_declaration: use statements
- let_declaration: variable bindings
- call_expression: function calls
- field_expression: struct.field access
- return_expression: return statements
- unsafe_block: unsafe { } blocks
- macro_invocation: macro!() calls
"""

from .base import extract_vars_from_rust_node


def extract_rust_functions(tree, content: str, file_path: str) -> list[dict]:
    """Extract function definitions from Rust AST.

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file

    Returns:
        List of function dicts with name, line, params, return_type
    """
    functions = []

    def traverse(node, depth=0):
        if depth > 100:
            return

        if node.type == "function_item":
            func_dict = _extract_function_details(node, content, file_path)
            if func_dict:
                functions.append(func_dict)

        if node.type == "function_signature_item":
            func_dict = _extract_function_details(node, content, file_path)
            if func_dict:
                functions.append(func_dict)

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return functions


def _extract_function_details(node, content: str, file_path: str) -> dict | None:
    """Extract details from a function_item node."""

    if node.has_error or node.type == "ERROR":
        return None

    name_node = node.child_by_field_name("name")
    if not name_node or name_node.type == "ERROR":
        return None

    name = _get_node_text(name_node, content)

    if not name or not _is_valid_identifier(name):
        return None

    is_public = False
    for child in node.children:
        if child.type == "visibility_modifier":
            is_public = True
            break

    params = []
    params_node = node.child_by_field_name("parameters")
    if params_node:
        for param in params_node.children:
            if param.type == "parameter":
                param_name = None
                param_type = None

                pattern_node = param.child_by_field_name("pattern")
                type_node = param.child_by_field_name("type")

                if pattern_node:
                    param_name = _get_node_text(pattern_node, content)
                if type_node:
                    param_type = _get_node_text(type_node, content)

                if param_name:
                    params.append({"name": param_name, "type": param_type})

    return_type = None
    return_type_node = node.child_by_field_name("return_type")
    if return_type_node:
        return_type = _get_node_text(return_type_node, content)

    return {
        "name": name,
        "type": "function",
        "line": node.start_point[0] + 1,
        "col": node.start_point[1],
        "end_line": node.end_point[0] + 1,
        "is_public": is_public,
        "params": params,
        "return_type": return_type,
    }


def extract_rust_classes(tree, content: str, file_path: str) -> list[dict]:
    """Extract struct, enum, and trait definitions.

    In Rust, 'classes' are represented by:
    - struct items
    - enum items
    - trait items

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file

    Returns:
        List of class/struct/enum dicts
    """
    classes = []

    def traverse(node, depth=0):
        if depth > 100:
            return

        if node.type in ["struct_item", "enum_item", "trait_item"]:
            class_dict = _extract_class_details(node, content, file_path)
            if class_dict:
                classes.append(class_dict)

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return classes


def _extract_class_details(node, content: str, file_path: str) -> dict | None:
    """Extract details from struct/enum/trait node."""

    if node.has_error or node.type == "ERROR":
        return None

    name_node = node.child_by_field_name("name")
    if not name_node or name_node.type == "ERROR":
        return None

    name = _get_node_text(name_node, content)

    if not name or not _is_valid_identifier(name):
        return None

    is_public = False
    for child in node.children:
        if child.type == "visibility_modifier":
            is_public = True
            break

    type_map = {"struct_item": "struct", "enum_item": "enum", "trait_item": "trait"}
    class_type = type_map.get(node.type, "class")

    fields = []
    if node.type == "struct_item":
        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                if child.type == "field_declaration":
                    field_name_node = child.child_by_field_name("name")
                    field_type_node = child.child_by_field_name("type")

                    if field_name_node:
                        fields.append(
                            {
                                "name": _get_node_text(field_name_node, content),
                                "type": _get_node_text(field_type_node, content)
                                if field_type_node
                                else None,
                            }
                        )

    return {
        "name": name,
        "type": class_type,
        "line": node.start_point[0] + 1,
        "col": node.start_point[1],
        "end_line": node.end_point[0] + 1,
        "is_public": is_public,
        "fields": fields,
    }


def extract_rust_imports(tree, content: str, file_path: str) -> list[tuple[str, str]]:
    """Extract use declarations from Rust AST.

    CRITICAL: NO REGEX - pure AST traversal.
    This replaces the forbidden regex pattern from rust_lsp_backup.py.

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file

    Returns:
        List of ('use', import_path) tuples
    """
    imports = []

    def traverse(node, depth=0):
        if depth > 100:
            return

        if node.type == "ERROR" or node.has_error:
            return

        if node.type == "use_declaration":
            argument_node = node.child_by_field_name("argument")
            if argument_node and argument_node.type != "ERROR":
                import_path = _get_node_text(argument_node, content)

                if import_path and not any(
                    keyword in import_path for keyword in [" fn ", " let ", " struct "]
                ):
                    imports.append(("use", import_path))

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return imports


def extract_rust_exports(tree, content: str, file_path: str) -> list[dict]:
    """Extract pub items (Rust's export mechanism).

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file

    Returns:
        List of export dicts
    """
    exports = []

    def traverse(node, depth=0):
        if depth > 100:
            return

        if node.type == "visibility_modifier":
            parent = node.parent
            if parent:
                name_node = parent.child_by_field_name("name")
                if name_node:
                    exports.append(
                        {
                            "name": _get_node_text(name_node, content),
                            "type": parent.type,
                            "line": parent.start_point[0] + 1,
                            "visibility": _get_node_text(node, content),
                        }
                    )

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return exports


def extract_rust_calls(tree, content: str, file_path: str) -> list[dict]:
    """Extract function calls and macro invocations.

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file

    Returns:
        List of call dicts
    """
    calls = []

    def traverse(node, depth=0):
        if depth > 100:
            return

        if node.type == "call_expression":
            function_node = node.child_by_field_name("function")
            if function_node:
                call_name = _get_node_text(function_node, content)
                calls.append(
                    {
                        "name": call_name,
                        "type": "call",
                        "line": node.start_point[0] + 1,
                        "column": node.start_point[1],
                    }
                )

        if node.type == "macro_invocation":
            macro_node = node.child_by_field_name("macro")
            if macro_node:
                macro_name = _get_node_text(macro_node, content)
                calls.append(
                    {
                        "name": macro_name + "!",
                        "type": "macro",
                        "line": node.start_point[0] + 1,
                        "column": node.start_point[1],
                    }
                )

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return calls


def extract_rust_properties(tree, content: str, file_path: str) -> list[dict]:
    """Extract field access expressions.

    Examples: obj.field, self.value, request.body

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file

    Returns:
        List of property access dicts
    """
    properties = []

    def traverse(node, depth=0):
        if depth > 100:
            return

        if node.type == "field_expression":
            value_node = node.child_by_field_name("value")
            field_node = node.child_by_field_name("field")

            if value_node and field_node:
                full_name = (
                    f"{_get_node_text(value_node, content)}.{_get_node_text(field_node, content)}"
                )
                properties.append(
                    {
                        "name": full_name,
                        "type": "property",
                        "line": node.start_point[0] + 1,
                        "column": node.start_point[1],
                    }
                )

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return properties


def extract_rust_assignments(tree, content: str, file_path: str) -> list[dict]:
    """Extract let bindings and assignment expressions.

    Examples:
    - let x = 5;
    - let mut y = foo();
    - x = y + 1;

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file

    Returns:
        List of assignment dicts with target_var, source_expr, line, in_function
    """
    assignments = []

    scope_map = _build_function_scope_map(tree, content)

    def traverse(node, depth=0):
        if depth > 100:
            return

        if node.type == "let_declaration":
            pattern_node = node.child_by_field_name("pattern")
            value_node = node.child_by_field_name("value")

            if pattern_node and value_node:
                target_var = _get_node_text(pattern_node, content)
                source_expr = _get_node_text(value_node, content)
                line = node.start_point[0] + 1

                in_function = scope_map.get(line, "global")

                source_vars = extract_vars_from_rust_node(value_node, content)

                assignments.append(
                    {
                        "target_var": target_var,
                        "source_expr": source_expr,
                        "line": line,
                        "in_function": in_function,
                        "source_vars": source_vars,
                    }
                )

        if node.type == "assignment_expression":
            left_node = node.child_by_field_name("left")
            right_node = node.child_by_field_name("right")

            if left_node and right_node:
                target_var = _get_node_text(left_node, content)
                source_expr = _get_node_text(right_node, content)
                line = node.start_point[0] + 1

                in_function = scope_map.get(line, "global")
                source_vars = extract_vars_from_rust_node(right_node, content)

                assignments.append(
                    {
                        "target_var": target_var,
                        "source_expr": source_expr,
                        "line": line,
                        "in_function": in_function,
                        "source_vars": source_vars,
                    }
                )

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return assignments


def extract_rust_function_params(tree, content: str, file_path: str) -> dict[str, list[str]]:
    """Extract function parameter names.

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file

    Returns:
        Dict mapping function_name -> [param_names]
    """
    func_params = {}

    def traverse(node, depth=0):
        if depth > 100:
            return

        if node.type == "function_item":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")

            if name_node and params_node:
                func_name = _get_node_text(name_node, content)
                params = []

                for param in params_node.children:
                    if param.type == "parameter":
                        pattern_node = param.child_by_field_name("pattern")
                        if pattern_node:
                            param_name = _get_node_text(pattern_node, content)

                            if ":" in param_name:
                                param_name = param_name.split(":")[0].strip()
                            params.append(param_name)

                if params:
                    func_params[func_name] = params

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return func_params


def extract_rust_calls_with_args(
    tree, content: str, file_path: str, function_params: dict[str, list[str]]
) -> list[dict]:
    """Extract function calls with their arguments.

    CRITICAL for taint analysis.

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file
        function_params: Dict of function_name -> param_names

    Returns:
        List of call dicts with caller, callee, arguments
    """
    calls = []

    scope_map = _build_function_scope_map(tree, content)

    def traverse(node, depth=0):
        if depth > 100:
            return

        if node.type == "call_expression":
            function_node = node.child_by_field_name("function")
            arguments_node = node.child_by_field_name("arguments")

            if function_node and arguments_node:
                callee = _get_node_text(function_node, content)
                line = node.start_point[0] + 1
                caller = scope_map.get(line, "global")

                arg_index = 0
                for child in arguments_node.children:
                    if child.type in ["(", ")", ","]:
                        continue

                    arg_expr = _get_node_text(child, content)

                    callee_simple = callee.split("::")[-1].split(".")[-1]
                    params = function_params.get(callee_simple, [])
                    param_name = params[arg_index] if arg_index < len(params) else f"arg{arg_index}"

                    calls.append(
                        {
                            "line": line,
                            "caller_function": caller,
                            "callee_function": callee,
                            "argument_index": arg_index,
                            "argument_expr": arg_expr,
                            "param_name": param_name,
                        }
                    )

                    arg_index += 1

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return calls


def extract_rust_returns(tree, content: str, file_path: str) -> list[dict]:
    """Extract return expressions (both explicit and implicit).

    Rust has two types of returns:
    1. Explicit: return x;
    2. Implicit: last expression without semicolon

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file

    Returns:
        List of return dicts with function_name, return_expr, line
    """
    returns = []

    scope_map = _build_function_scope_map(tree, content)

    def traverse_explicit(node, depth=0):
        if depth > 100:
            return

        if node.type == "return_expression":
            line = node.start_point[0] + 1
            function_name = scope_map.get(line, "global")

            return_expr = ""
            return_vars = []
            for child in node.children:
                if child.type != "return":
                    return_expr = _get_node_text(child, content)
                    return_vars = extract_vars_from_rust_node(child, content)
                    break

            returns.append(
                {
                    "function_name": function_name,
                    "line": line,
                    "return_expr": return_expr,
                    "return_vars": return_vars,
                    "is_implicit": False,
                }
            )

        for child in node.children:
            traverse_explicit(child, depth + 1)

    traverse_explicit(tree.root_node)

    def traverse_functions(node, depth=0):
        if depth > 100:
            return

        if node.type == "ERROR" or node.has_error:
            return

        if node.type == "function_item":
            name_node = node.child_by_field_name("name")
            body_node = node.child_by_field_name("body")

            if name_node and body_node and body_node.type == "block":
                func_name = _get_node_text(name_node, content)

                if not func_name or not _is_valid_identifier(func_name):
                    return

                last_expr = None
                for child in reversed(body_node.children):
                    if child.type in ["{", "}", "line_comment", "block_comment"]:
                        continue

                    if child.type in [
                        "expression_statement",
                        "let_declaration",
                        "let_statement",
                        "use_declaration",
                    ]:
                        continue

                    if child.type.endswith("_expression") or child.type in [
                        "identifier",
                        "block",
                        "if",
                        "match",
                        "loop",
                        "while",
                        "for",
                        "struct_expression",
                        "tuple_expression",
                        "array_expression",
                        "call_expression",
                        "macro_invocation",
                    ]:
                        last_expr = child
                        break

                    break

                if last_expr:
                    if last_expr.type == "ERROR" or last_expr.has_error:
                        return

                    line = last_expr.start_point[0] + 1
                    return_expr = _get_node_text(last_expr, content)
                    return_vars = extract_vars_from_rust_node(last_expr, content)

                    if not return_expr or len(return_expr) > 500:
                        return

                    if not any(
                        r["line"] == line and r["function_name"] == func_name for r in returns
                    ):
                        returns.append(
                            {
                                "function_name": func_name,
                                "line": line,
                                "return_expr": return_expr,
                                "return_vars": return_vars,
                                "is_implicit": True,
                            }
                        )

        for child in node.children:
            traverse_functions(child, depth + 1)

    traverse_functions(tree.root_node)
    return returns


def extract_rust_cfg(tree, content: str, file_path: str) -> list[dict]:
    """Extract control flow graph information.

    Placeholder implementation - full CFG extraction is complex.
    Returns basic control flow structure for now.

    Args:
        tree: tree-sitter parse tree
        content: File content
        file_path: Path to source file

    Returns:
        List of CFG dicts (basic structure)
    """
    cfgs = []

    return cfgs


def _get_node_text(node, content: str) -> str:
    """Extract text for a tree-sitter node.

    Args:
        node: tree-sitter node
        content: File content

    Returns:
        Text content of the node
    """
    if node is None:
        return ""

    if node.type == "ERROR" or node.has_error:
        return ""

    start_byte = node.start_byte
    end_byte = node.end_byte
    return content[start_byte:end_byte]


def _is_valid_identifier(text: str) -> bool:
    """Check if text is a valid Rust identifier.

    Rust identifiers:
    - Start with letter or underscore
    - Contain only letters, digits, underscores
    - Not just underscores

    Args:
        text: Text to validate

    Returns:
        True if valid identifier
    """
    if not text or len(text) > 200:
        return False

    invalid_chars = ["\n", " ", "{", "}", "(", ")", "[", "]", "<", ">", ";", ":", ","]
    if any(char in text for char in invalid_chars):
        return False

    if not (text[0].isalpha() or text[0] == "_"):
        return False

    if not all(c.isalnum() or c == "_" for c in text):
        return False

    return text.strip("_") != ""


def _build_function_scope_map(tree, content: str) -> dict[int, str]:
    """Build a map of line numbers to containing function names.

    Args:
        tree: tree-sitter parse tree
        content: File content

    Returns:
        Dict mapping line_number -> function_name
    """
    scope_map = {}

    def traverse(node, depth=0):
        if depth > 100:
            return

        if node.type == "function_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = _get_node_text(name_node, content)
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                for line in range(start_line, end_line + 1):
                    scope_map[line] = func_name

        for child in node.children:
            traverse(child, depth + 1)

    traverse(tree.root_node)
    return scope_map
