"""Go AST extraction using tree-sitter."""

from typing import Any


def _get_node_text(node: Any, content: str) -> str:
    """Extract text from a tree-sitter node."""
    if node is None:
        return ""
    return node.text.decode("utf-8", errors="ignore")


def _is_exported(name: str) -> bool:
    """Check if a Go identifier is exported (starts with uppercase)."""
    return bool(name) and name[0].isupper()


def _find_child_by_type(node: Any, child_type: str) -> Any | None:
    """Find first child of given type."""
    if node is None:
        return None
    for child in node.children:
        if child.type == child_type:
            return child
    return None


def _find_children_by_type(node: Any, child_type: str) -> list[Any]:
    """Find all children of given type."""
    if node is None:
        return []
    return [child for child in node.children if child.type == child_type]


def _get_preceding_comment(node: Any, content: str) -> str | None:
    """Get doc comment preceding a declaration."""

    if node.prev_sibling and node.prev_sibling.type == "comment":
        return _get_node_text(node.prev_sibling, content)
    return None


def extract_go_package(tree: Any, content: str, file_path: str) -> dict | None:
    """Extract package declaration from a Go file."""
    root = tree.root_node
    pkg_clause = _find_child_by_type(root, "package_clause")
    if not pkg_clause:
        return None

    pkg_id = _find_child_by_type(pkg_clause, "package_identifier")
    if not pkg_id:
        return None

    return {
        "file_path": file_path,
        "line": pkg_clause.start_point[0] + 1,
        "name": _get_node_text(pkg_id, content),
        "import_path": None,
    }


def extract_go_imports(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract import declarations from a Go file."""
    root = tree.root_node
    imports = []

    for import_decl in _find_children_by_type(root, "import_declaration"):
        single_spec = _find_child_by_type(import_decl, "import_spec")
        if single_spec:
            imports.append(_parse_import_spec(single_spec, content, file_path))
            continue

        spec_list = _find_child_by_type(import_decl, "import_spec_list")
        if spec_list:
            for spec in _find_children_by_type(spec_list, "import_spec"):
                imports.append(_parse_import_spec(spec, content, file_path))

    return [i for i in imports if i is not None]


def _parse_import_spec(spec: Any, content: str, file_path: str) -> dict | None:
    """Parse a single import spec."""
    path_node = _find_child_by_type(spec, "interpreted_string_literal")
    if not path_node:
        return None

    path = _get_node_text(path_node, content).strip('"')

    dot_node = _find_child_by_type(spec, "dot")
    is_dot_import = dot_node is not None

    alias_node = _find_child_by_type(spec, "identifier")
    alias = _get_node_text(alias_node, content) if alias_node else None

    return {
        "file_path": file_path,
        "line": spec.start_point[0] + 1,
        "path": path,
        "alias": alias,
        "is_dot_import": is_dot_import,
    }


def extract_go_structs(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract struct definitions from a Go file."""
    root = tree.root_node
    structs = []

    for type_decl in _find_children_by_type(root, "type_declaration"):
        type_spec = _find_child_by_type(type_decl, "type_spec")
        if not type_spec:
            continue

        struct_type = _find_child_by_type(type_spec, "struct_type")
        if not struct_type:
            continue

        name_node = _find_child_by_type(type_spec, "type_identifier")
        if not name_node:
            continue

        name = _get_node_text(name_node, content)
        doc = _get_preceding_comment(type_decl, content)

        structs.append(
            {
                "file_path": file_path,
                "line": type_decl.start_point[0] + 1,
                "name": name,
                "is_exported": _is_exported(name),
                "doc_comment": doc,
            }
        )

    return structs


def extract_go_struct_fields(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract struct field definitions from a Go file."""
    root = tree.root_node
    fields = []

    for type_decl in _find_children_by_type(root, "type_declaration"):
        type_spec = _find_child_by_type(type_decl, "type_spec")
        if not type_spec:
            continue

        struct_type = _find_child_by_type(type_spec, "struct_type")
        if not struct_type:
            continue

        struct_name_node = _find_child_by_type(type_spec, "type_identifier")
        if not struct_name_node:
            continue

        struct_name = _get_node_text(struct_name_node, content)

        field_list = _find_child_by_type(struct_type, "field_declaration_list")
        if not field_list:
            continue

        for field_decl in _find_children_by_type(field_list, "field_declaration"):
            field_info = _parse_field_declaration(field_decl, content, file_path, struct_name)
            if field_info:
                fields.extend(field_info)

    return fields


def _parse_field_declaration(
    field_decl: Any, content: str, file_path: str, struct_name: str
) -> list[dict]:
    """Parse a field declaration which may have multiple names."""
    fields = []

    field_type = None
    for child in field_decl.children:
        if child.type in (
            "type_identifier",
            "pointer_type",
            "slice_type",
            "array_type",
            "map_type",
            "channel_type",
            "interface_type",
            "struct_type",
            "function_type",
            "qualified_type",
        ):
            field_type = _get_node_text(child, content)
            break

    tag_node = _find_child_by_type(field_decl, "raw_string_literal")
    tag = _get_node_text(tag_node, content) if tag_node else None

    field_names = _find_children_by_type(field_decl, "field_identifier")

    if not field_names:
        if field_type:
            embedded_name = field_type.lstrip("*")
            fields.append(
                {
                    "file_path": file_path,
                    "struct_name": struct_name,
                    "field_name": embedded_name,
                    "field_type": field_type,
                    "tag": tag,
                    "is_embedded": True,
                    "is_exported": _is_exported(embedded_name),
                }
            )
    else:
        for name_node in field_names:
            name = _get_node_text(name_node, content)
            fields.append(
                {
                    "file_path": file_path,
                    "struct_name": struct_name,
                    "field_name": name,
                    "field_type": field_type or "",
                    "tag": tag,
                    "is_embedded": False,
                    "is_exported": _is_exported(name),
                }
            )

    return fields


def extract_go_interfaces(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract interface definitions from a Go file."""
    root = tree.root_node
    interfaces = []

    for type_decl in _find_children_by_type(root, "type_declaration"):
        type_spec = _find_child_by_type(type_decl, "type_spec")
        if not type_spec:
            continue

        interface_type = _find_child_by_type(type_spec, "interface_type")
        if not interface_type:
            continue

        name_node = _find_child_by_type(type_spec, "type_identifier")
        if not name_node:
            continue

        name = _get_node_text(name_node, content)
        doc = _get_preceding_comment(type_decl, content)

        interfaces.append(
            {
                "file_path": file_path,
                "line": type_decl.start_point[0] + 1,
                "name": name,
                "is_exported": _is_exported(name),
                "doc_comment": doc,
            }
        )

    return interfaces


def extract_go_interface_methods(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract interface method declarations from a Go file."""
    root = tree.root_node
    methods = []

    for type_decl in _find_children_by_type(root, "type_declaration"):
        type_spec = _find_child_by_type(type_decl, "type_spec")
        if not type_spec:
            continue

        interface_type = _find_child_by_type(type_spec, "interface_type")
        if not interface_type:
            continue

        interface_name_node = _find_child_by_type(type_spec, "type_identifier")
        if not interface_name_node:
            continue

        interface_name = _get_node_text(interface_name_node, content)

        for method_elem in _find_children_by_type(interface_type, "method_elem"):
            method_text = _get_node_text(method_elem, content)

            method_name = method_text.split("(")[0].strip()

            methods.append(
                {
                    "file_path": file_path,
                    "interface_name": interface_name,
                    "method_name": method_name,
                    "signature": method_text,
                }
            )

    return methods


def extract_go_functions(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract function declarations from a Go file."""
    root = tree.root_node
    functions = []

    for func_decl in _find_children_by_type(root, "function_declaration"):
        name_node = _find_child_by_type(func_decl, "identifier")
        if not name_node:
            continue

        name = _get_node_text(name_node, content)

        params = _find_child_by_type(func_decl, "parameter_list")
        signature = _get_node_text(params, content) if params else "()"

        result_types = []
        for child in func_decl.children:
            if child.type in (
                "type_identifier",
                "pointer_type",
                "slice_type",
                "array_type",
                "map_type",
                "parameter_list",
            ):
                if child.type == "parameter_list" and child == params:
                    continue
                result_types.append(_get_node_text(child, content))

        if result_types:
            signature += " " + " ".join(result_types)

        doc = _get_preceding_comment(func_decl, content)

        functions.append(
            {
                "file_path": file_path,
                "line": func_decl.start_point[0] + 1,
                "name": name,
                "signature": signature,
                "is_exported": _is_exported(name),
                "is_async": False,
                "doc_comment": doc,
            }
        )

    return functions


def extract_go_methods(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract method declarations (functions with receivers) from a Go file."""
    root = tree.root_node
    methods = []

    for method_decl in _find_children_by_type(root, "method_declaration"):
        param_lists = _find_children_by_type(method_decl, "parameter_list")
        if not param_lists:
            continue

        receiver_list = param_lists[0]
        receiver_param = _find_child_by_type(receiver_list, "parameter_declaration")

        receiver_name = None
        receiver_type = None
        is_pointer = False

        if receiver_param:
            name_node = _find_child_by_type(receiver_param, "identifier")
            receiver_name = _get_node_text(name_node, content) if name_node else None

            ptr_type = _find_child_by_type(receiver_param, "pointer_type")
            if ptr_type:
                is_pointer = True
                type_id = _find_child_by_type(ptr_type, "type_identifier")
                receiver_type = _get_node_text(type_id, content) if type_id else ""
            else:
                type_id = _find_child_by_type(receiver_param, "type_identifier")
                receiver_type = _get_node_text(type_id, content) if type_id else ""

        name_node = _find_child_by_type(method_decl, "field_identifier")
        if not name_node:
            continue

        name = _get_node_text(name_node, content)

        sig_param_list = param_lists[1] if len(param_lists) > 1 else None
        signature = _get_node_text(sig_param_list, content) if sig_param_list else "()"

        methods.append(
            {
                "file_path": file_path,
                "line": method_decl.start_point[0] + 1,
                "receiver_type": receiver_type or "",
                "receiver_name": receiver_name,
                "is_pointer_receiver": is_pointer,
                "name": name,
                "signature": signature,
                "is_exported": _is_exported(name),
            }
        )

    return methods


def extract_go_func_params(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract function/method parameters from a Go file."""
    root = tree.root_node
    params = []

    for func_decl in _find_children_by_type(root, "function_declaration"):
        name_node = _find_child_by_type(func_decl, "identifier")
        if not name_node:
            continue

        func_name = _get_node_text(name_node, content)
        func_line = func_decl.start_point[0] + 1

        param_list = _find_child_by_type(func_decl, "parameter_list")
        if param_list:
            params.extend(_parse_param_list(param_list, content, file_path, func_name, func_line))

    for method_decl in _find_children_by_type(root, "method_declaration"):
        name_node = _find_child_by_type(method_decl, "field_identifier")
        if not name_node:
            continue

        func_name = _get_node_text(name_node, content)
        func_line = method_decl.start_point[0] + 1

        param_lists = _find_children_by_type(method_decl, "parameter_list")

        if len(param_lists) > 1:
            params.extend(
                _parse_param_list(param_lists[1], content, file_path, func_name, func_line)
            )

    return params


def _parse_param_list(
    param_list: Any, content: str, file_path: str, func_name: str, func_line: int
) -> list[dict]:
    """Parse a parameter list into individual parameter records."""
    params = []
    param_index = 0

    for param_decl in _find_children_by_type(param_list, "parameter_declaration"):
        param_type = None
        is_variadic = False

        variadic_node = _find_child_by_type(param_decl, "variadic_parameter_declaration")
        if variadic_node:
            is_variadic = True
            param_type = "..." + _get_node_text(variadic_node, content)
        else:
            for child in param_decl.children:
                if child.type in (
                    "type_identifier",
                    "pointer_type",
                    "slice_type",
                    "array_type",
                    "map_type",
                    "channel_type",
                    "interface_type",
                    "function_type",
                    "qualified_type",
                ):
                    param_type = _get_node_text(child, content)
                    break

        name_nodes = _find_children_by_type(param_decl, "identifier")

        if name_nodes:
            for name_node in name_nodes:
                params.append(
                    {
                        "file_path": file_path,
                        "func_name": func_name,
                        "func_line": func_line,
                        "param_index": param_index,
                        "param_name": _get_node_text(name_node, content),
                        "param_type": param_type or "",
                        "is_variadic": is_variadic,
                    }
                )
                param_index += 1
        else:
            params.append(
                {
                    "file_path": file_path,
                    "func_name": func_name,
                    "func_line": func_line,
                    "param_index": param_index,
                    "param_name": None,
                    "param_type": param_type or "",
                    "is_variadic": is_variadic,
                }
            )
            param_index += 1

    return params


def extract_go_func_returns(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract function return types from a Go file."""
    root = tree.root_node
    returns = []

    for func_decl in _find_children_by_type(root, "function_declaration"):
        name_node = _find_child_by_type(func_decl, "identifier")
        if not name_node:
            continue

        func_name = _get_node_text(name_node, content)
        func_line = func_decl.start_point[0] + 1

        returns.extend(_extract_return_types(func_decl, content, file_path, func_name, func_line))

    for method_decl in _find_children_by_type(root, "method_declaration"):
        name_node = _find_child_by_type(method_decl, "field_identifier")
        if not name_node:
            continue

        func_name = _get_node_text(name_node, content)
        func_line = method_decl.start_point[0] + 1

        returns.extend(_extract_return_types(method_decl, content, file_path, func_name, func_line))

    return returns


def _extract_return_types(
    func_decl: Any, content: str, file_path: str, func_name: str, func_line: int
) -> list[dict]:
    """Extract return types from a function/method declaration."""
    returns = []
    return_index = 0

    param_lists = _find_children_by_type(func_decl, "parameter_list")

    result_list = None
    for i, pl in enumerate(param_lists):
        if (
            func_decl.type == "method_declaration"
            and i == 2
            or func_decl.type == "function_declaration"
            and i == 1
        ):
            result_list = pl

    if result_list:
        for param_decl in _find_children_by_type(result_list, "parameter_declaration"):
            return_type = None
            for child in param_decl.children:
                if child.type in (
                    "type_identifier",
                    "pointer_type",
                    "slice_type",
                    "array_type",
                    "map_type",
                    "interface_type",
                    "qualified_type",
                    "channel_type",
                ):
                    return_type = _get_node_text(child, content)
                    break

            name_nodes = _find_children_by_type(param_decl, "identifier")
            if name_nodes:
                for name_node in name_nodes:
                    returns.append(
                        {
                            "file_path": file_path,
                            "func_name": func_name,
                            "func_line": func_line,
                            "return_index": return_index,
                            "return_name": _get_node_text(name_node, content),
                            "return_type": return_type or "",
                        }
                    )
                    return_index += 1
            else:
                returns.append(
                    {
                        "file_path": file_path,
                        "func_name": func_name,
                        "func_line": func_line,
                        "return_index": return_index,
                        "return_name": None,
                        "return_type": return_type or "",
                    }
                )
                return_index += 1
    else:
        for child in func_decl.children:
            if child.type in (
                "type_identifier",
                "pointer_type",
                "slice_type",
                "array_type",
                "map_type",
                "interface_type",
                "qualified_type",
                "channel_type",
            ):
                returns.append(
                    {
                        "file_path": file_path,
                        "func_name": func_name,
                        "func_line": func_line,
                        "return_index": return_index,
                        "return_name": None,
                        "return_type": _get_node_text(child, content),
                    }
                )
                return_index += 1

    return returns


def extract_go_goroutines(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract goroutine spawns from a Go file."""
    goroutines = []

    def visit(node: Any, containing_func: str | None):
        if node.type == "function_declaration":
            name_node = _find_child_by_type(node, "identifier")
            containing_func = _get_node_text(name_node, content) if name_node else None
        elif node.type == "method_declaration":
            name_node = _find_child_by_type(node, "field_identifier")
            containing_func = _get_node_text(name_node, content) if name_node else None

        if node.type == "go_statement":
            spawned_expr = ""
            is_anonymous = False

            for child in node.children:
                if child.type == "call_expression":
                    spawned_expr = _get_node_text(child, content)

                    func_lit = _find_child_by_type(child, "func_literal")
                    is_anonymous = func_lit is not None
                    break

            goroutines.append(
                {
                    "file_path": file_path,
                    "line": node.start_point[0] + 1,
                    "containing_func": containing_func,
                    "spawned_expr": spawned_expr[:200] if spawned_expr else "",
                    "is_anonymous": is_anonymous,
                }
            )

        for child in node.children:
            visit(child, containing_func)

    visit(tree.root_node, None)
    return goroutines


def extract_go_channels(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract channel declarations from a Go file."""
    channels = []

    def visit(node: Any):
        if node.type == "call_expression":
            func_node = node.children[0] if node.children else None
            if func_node and _get_node_text(func_node, content) == "make":
                args = _find_child_by_type(node, "argument_list")
                if args:
                    for arg in args.children:
                        if arg.type == "channel_type":
                            chan_text = _get_node_text(arg, content)

                            parts = chan_text.split()
                            element_type = parts[1] if len(parts) > 1 else None

                            buffer_size = None
                            int_lit = _find_child_by_type(args, "int_literal")
                            if int_lit:
                                try:
                                    buffer_size = int(_get_node_text(int_lit, content))
                                except ValueError:
                                    pass

                            name = ""
                            parent = node.parent
                            if parent and parent.type == "short_var_declaration":
                                id_list = parent.children[0] if parent.children else None
                                if id_list:
                                    name = _get_node_text(id_list, content).split(",")[0].strip()

                            channels.append(
                                {
                                    "file_path": file_path,
                                    "line": node.start_point[0] + 1,
                                    "name": name,
                                    "element_type": element_type,
                                    "direction": "bidirectional",
                                    "buffer_size": buffer_size,
                                }
                            )
                            break

        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return channels


def extract_go_channel_ops(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract channel send/receive operations from a Go file."""
    ops = []

    def visit(node: Any, containing_func: str | None):
        if node.type == "function_declaration":
            name_node = _find_child_by_type(node, "identifier")
            containing_func = _get_node_text(name_node, content) if name_node else None
        elif node.type == "method_declaration":
            name_node = _find_child_by_type(node, "field_identifier")
            containing_func = _get_node_text(name_node, content) if name_node else None

        if node.type == "send_statement":
            channel_name = _get_node_text(node.children[0], content) if node.children else None
            ops.append(
                {
                    "file_path": file_path,
                    "line": node.start_point[0] + 1,
                    "channel_name": channel_name,
                    "operation": "send",
                    "containing_func": containing_func,
                }
            )

        if node.type == "unary_expression":
            op = node.children[0] if node.children else None
            if op and _get_node_text(op, content) == "<-":
                channel = node.children[1] if len(node.children) > 1 else None
                channel_name = _get_node_text(channel, content) if channel else None
                ops.append(
                    {
                        "file_path": file_path,
                        "line": node.start_point[0] + 1,
                        "channel_name": channel_name,
                        "operation": "receive",
                        "containing_func": containing_func,
                    }
                )

        for child in node.children:
            visit(child, containing_func)

    visit(tree.root_node, None)
    return ops


def extract_go_defer_statements(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract defer statements from a Go file."""
    defers = []

    def visit(node: Any, containing_func: str | None):
        if node.type == "function_declaration":
            name_node = _find_child_by_type(node, "identifier")
            containing_func = _get_node_text(name_node, content) if name_node else None
        elif node.type == "method_declaration":
            name_node = _find_child_by_type(node, "field_identifier")
            containing_func = _get_node_text(name_node, content) if name_node else None

        if node.type == "defer_statement":
            deferred_expr = ""
            for child in node.children:
                if child.type != "defer":
                    deferred_expr = _get_node_text(child, content)
                    break

            defers.append(
                {
                    "file_path": file_path,
                    "line": node.start_point[0] + 1,
                    "containing_func": containing_func,
                    "deferred_expr": deferred_expr[:200] if deferred_expr else "",
                }
            )

        for child in node.children:
            visit(child, containing_func)

    visit(tree.root_node, None)
    return defers


def extract_go_constants(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract constant declarations from a Go file."""
    root = tree.root_node
    constants = []

    for const_decl in _find_children_by_type(root, "const_declaration"):
        for spec in _find_children_by_type(const_decl, "const_spec"):
            constants.extend(_parse_const_spec(spec, content, file_path))

    return constants


def _parse_const_spec(spec: Any, content: str, file_path: str) -> list[dict]:
    """Parse a const spec which may have multiple names."""
    constants = []

    const_type = None
    for child in spec.children:
        if child.type == "type_identifier":
            const_type = _get_node_text(child, content)
            break

    expr_list = _find_child_by_type(spec, "expression_list")
    value = _get_node_text(expr_list, content) if expr_list else None

    name_nodes = _find_children_by_type(spec, "identifier")
    for name_node in name_nodes:
        name = _get_node_text(name_node, content)
        constants.append(
            {
                "file_path": file_path,
                "line": spec.start_point[0] + 1,
                "name": name,
                "value": value,
                "type": const_type,
                "is_exported": _is_exported(name),
            }
        )

    return constants


def extract_go_variables(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract variable declarations from a Go file.

    Extracts both package-level and local function variables:
    - Package-level: var x = expr (at file scope)
    - Local: var x = expr or x := expr (inside functions)

    Local variables are CRITICAL for SQL injection detection:
        query := fmt.Sprintf("SELECT * FROM users WHERE id = %s", id)
        db.Exec(query)  // SQL injection if id is user input
    """
    root = tree.root_node
    variables = []

    for var_decl in _find_children_by_type(root, "var_declaration"):
        for var_spec in _find_children_by_type(var_decl, "var_spec"):
            variables.extend(
                _parse_var_spec(
                    var_spec, content, file_path, is_package_level=True, containing_func=None
                )
            )

    def visit(node: Any, containing_func: str | None):
        if node.type == "function_declaration":
            name_node = _find_child_by_type(node, "identifier")
            containing_func = _get_node_text(name_node, content) if name_node else None
        elif node.type == "method_declaration":
            name_node = _find_child_by_type(node, "field_identifier")
            containing_func = _get_node_text(name_node, content) if name_node else None

        if node.type == "var_declaration" and containing_func is not None:
            for var_spec in _find_children_by_type(node, "var_spec"):
                variables.extend(
                    _parse_var_spec(
                        var_spec,
                        content,
                        file_path,
                        is_package_level=False,
                        containing_func=containing_func,
                    )
                )

        if node.type == "short_var_declaration" and containing_func is not None:
            variables.extend(_parse_short_var_decl(node, content, file_path, containing_func))

        for child in node.children:
            visit(child, containing_func)

    visit(root, None)
    return variables


def _parse_short_var_decl(
    node: Any, content: str, file_path: str, containing_func: str
) -> list[dict]:
    """Parse a short variable declaration: x := expr or x, y := expr1, expr2"""
    variables = []

    left = node.children[0] if node.children else None

    right = node.children[2] if len(node.children) > 2 else None

    names = []
    if left:
        if left.type == "expression_list":
            for child in left.children:
                if child.type == "identifier":
                    names.append(_get_node_text(child, content))
        elif left.type == "identifier":
            names.append(_get_node_text(left, content))

    initial_value = _get_node_text(right, content) if right else None

    for name in names:
        if name == "_":
            continue
        variables.append(
            {
                "file_path": file_path,
                "line": node.start_point[0] + 1,
                "name": name,
                "type": None,
                "initial_value": initial_value[:500] if initial_value else None,
                "is_exported": _is_exported(name),
                "is_package_level": False,
                "containing_func": containing_func,
            }
        )

    return variables


def _parse_var_spec(
    spec: Any, content: str, file_path: str, is_package_level: bool, containing_func: str | None
) -> list[dict]:
    """Parse a var spec which may have multiple names."""
    variables = []

    var_type = None
    for child in spec.children:
        if child.type in (
            "type_identifier",
            "pointer_type",
            "slice_type",
            "array_type",
            "map_type",
            "channel_type",
            "interface_type",
        ):
            var_type = _get_node_text(child, content)
            break

    expr_list = _find_child_by_type(spec, "expression_list")
    initial_value = _get_node_text(expr_list, content) if expr_list else None

    name_nodes = _find_children_by_type(spec, "identifier")
    for name_node in name_nodes:
        name = _get_node_text(name_node, content)
        variables.append(
            {
                "file_path": file_path,
                "line": spec.start_point[0] + 1,
                "name": name,
                "type": var_type,
                "initial_value": initial_value[:500] if initial_value else None,
                "is_exported": _is_exported(name),
                "is_package_level": is_package_level,
                "containing_func": containing_func,
            }
        )

    return variables


def extract_go_type_params(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract type parameters (generics) from a Go file."""
    root = tree.root_node
    type_params = []

    for func_decl in _find_children_by_type(root, "function_declaration"):
        name_node = _find_child_by_type(func_decl, "identifier")
        if not name_node:
            continue

        parent_name = _get_node_text(name_node, content)
        line = func_decl.start_point[0] + 1

        tp_list = _find_child_by_type(func_decl, "type_parameter_list")
        if tp_list:
            type_params.extend(
                _parse_type_param_list(tp_list, content, file_path, parent_name, "function", line)
            )

    for type_decl in _find_children_by_type(root, "type_declaration"):
        type_spec = _find_child_by_type(type_decl, "type_spec")
        if not type_spec:
            continue

        name_node = _find_child_by_type(type_spec, "type_identifier")
        if not name_node:
            continue

        parent_name = _get_node_text(name_node, content)
        line = type_decl.start_point[0] + 1

        tp_list = _find_child_by_type(type_spec, "type_parameter_list")
        if tp_list:
            type_params.extend(
                _parse_type_param_list(tp_list, content, file_path, parent_name, "type", line)
            )

    return type_params


def _parse_type_param_list(
    tp_list: Any, content: str, file_path: str, parent_name: str, parent_kind: str, line: int
) -> list[dict]:
    """Parse a type parameter list."""
    params = []
    param_index = 0

    for tp_decl in _find_children_by_type(tp_list, "type_parameter_declaration"):
        constraint = None
        constraint_node = _find_child_by_type(tp_decl, "type_constraint")
        if constraint_node:
            constraint = _get_node_text(constraint_node, content)

        name_nodes = _find_children_by_type(tp_decl, "identifier")
        for name_node in name_nodes:
            params.append(
                {
                    "file_path": file_path,
                    "line": line,
                    "parent_name": parent_name,
                    "parent_kind": parent_kind,
                    "param_index": param_index,
                    "param_name": _get_node_text(name_node, content),
                    "constraint": constraint,
                }
            )
            param_index += 1

    return params


def extract_go_type_assertions(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract type assertions and type switches from a Go file."""
    assertions = []

    def visit(node: Any, containing_func: str | None):
        if node.type == "function_declaration":
            name_node = _find_child_by_type(node, "identifier")
            containing_func = _get_node_text(name_node, content) if name_node else None
        elif node.type == "method_declaration":
            name_node = _find_child_by_type(node, "field_identifier")
            containing_func = _get_node_text(name_node, content) if name_node else None

        if node.type == "type_assertion_expression":
            expr = ""
            asserted_type = ""

            for child in node.children:
                if child.type == "identifier" or child.type == "selector_expression":
                    expr = _get_node_text(child, content)
                elif child.type == "type_identifier" or child.type == "pointer_type":
                    asserted_type = _get_node_text(child, content)

            assertions.append(
                {
                    "file_path": file_path,
                    "line": node.start_point[0] + 1,
                    "expr": expr,
                    "asserted_type": asserted_type,
                    "is_type_switch": False,
                    "containing_func": containing_func,
                }
            )

        if node.type == "type_switch_statement":
            guard = _find_child_by_type(node, "type_switch_guard")
            if guard:
                expr = _get_node_text(guard, content)
                assertions.append(
                    {
                        "file_path": file_path,
                        "line": node.start_point[0] + 1,
                        "expr": expr,
                        "asserted_type": "type",
                        "is_type_switch": True,
                        "containing_func": containing_func,
                    }
                )

        for child in node.children:
            visit(child, containing_func)

    visit(tree.root_node, None)
    return assertions


def extract_go_error_returns(tree: Any, content: str, file_path: str) -> list[dict]:
    """Extract functions that return error type."""
    root = tree.root_node
    error_returns = []

    for func_decl in _find_children_by_type(root, "function_declaration"):
        name_node = _find_child_by_type(func_decl, "identifier")
        if not name_node:
            continue

        func_name = _get_node_text(name_node, content)
        line = func_decl.start_point[0] + 1

        returns_error = _check_returns_error(func_decl, content)
        if returns_error:
            error_returns.append(
                {
                    "file_path": file_path,
                    "line": line,
                    "func_name": func_name,
                    "returns_error": True,
                }
            )

    for method_decl in _find_children_by_type(root, "method_declaration"):
        name_node = _find_child_by_type(method_decl, "field_identifier")
        if not name_node:
            continue

        func_name = _get_node_text(name_node, content)
        line = method_decl.start_point[0] + 1

        returns_error = _check_returns_error(method_decl, content)
        if returns_error:
            error_returns.append(
                {
                    "file_path": file_path,
                    "line": line,
                    "func_name": func_name,
                    "returns_error": True,
                }
            )

    return error_returns


def _check_returns_error(func_decl: Any, content: str) -> bool:
    """Check if a function/method declaration returns error."""

    func_text = _get_node_text(func_decl, content)

    paren_count = 0
    in_returns = False
    for char in func_text:
        if char == "(":
            paren_count += 1
        elif char == ")":
            paren_count -= 1
            if paren_count == 0:
                in_returns = True
        elif char == "{":
            break

    if in_returns:
        return_portion = func_text.split(")")[1].split("{")[0] if ")" in func_text else ""
        return "error" in return_portion

    return False


def extract_go_captured_vars(
    tree: Any, content: str, file_path: str, goroutines: list[dict]
) -> list[dict]:
    """Extract variables captured by anonymous goroutine closures.

    This is CRITICAL for race condition detection. The #1 source of data races
    in Go is captured loop variables in goroutines:

        for i, v := range items {
            go func() {
                process(v)  // v is captured from loop - RACE CONDITION!
            }()
        }

    Args:
        tree: Tree-sitter parse tree
        content: Source code content
        file_path: Path to the file
        goroutines: List of goroutine dicts from extract_go_goroutines

    Returns:
        List of captured variable records with is_loop_var flag
    """
    captured_vars = []
    goroutine_id = 0

    def _collect_identifiers_in_node(node: Any) -> set[str]:
        """Recursively collect all identifier names used in a node."""
        identifiers = set()

        if node.type == "identifier":
            identifiers.add(_get_node_text(node, content))

        for child in node.children:
            identifiers.update(_collect_identifiers_in_node(child))

        return identifiers

    def _collect_declared_in_params(param_list: Any) -> set[str]:
        """Collect parameter names from a function's parameter list."""
        declared = set()
        if not param_list:
            return declared

        for param_decl in _find_children_by_type(param_list, "parameter_declaration"):
            for id_node in _find_children_by_type(param_decl, "identifier"):
                declared.add(_get_node_text(id_node, content))

        return declared

    def _collect_declared_in_block(block: Any) -> set[str]:
        """Collect variables declared within a block (local scope)."""
        declared = set()
        if not block:
            return declared

        def visit_for_decl(node: Any):
            if node.type == "short_var_declaration":
                left = node.children[0] if node.children else None
                if left and left.type == "expression_list":
                    for child in left.children:
                        if child.type == "identifier":
                            declared.add(_get_node_text(child, content))
                elif left and left.type == "identifier":
                    declared.add(_get_node_text(left, content))

            if node.type == "var_declaration":
                for var_spec in _find_children_by_type(node, "var_spec"):
                    for id_node in _find_children_by_type(var_spec, "identifier"):
                        declared.add(_get_node_text(id_node, content))

            for child in node.children:
                visit_for_decl(child)

        visit_for_decl(block)
        return declared

    def _get_loop_variables(node: Any) -> set[str]:
        """Get variables declared in a for/range loop header."""
        loop_vars = set()

        if node.type in ("for_statement", "for_range_statement"):
            range_clause = _find_child_by_type(node, "range_clause")
            if range_clause:
                left = range_clause.children[0] if range_clause.children else None
                if left and left.type == "expression_list":
                    for child in left.children:
                        if child.type == "identifier":
                            loop_vars.add(_get_node_text(child, content))
                elif left and left.type == "identifier":
                    loop_vars.add(_get_node_text(left, content))

            for_clause = _find_child_by_type(node, "for_clause")
            if for_clause:
                init = for_clause.children[0] if for_clause.children else None
                if init and init.type == "short_var_declaration":
                    left = init.children[0] if init.children else None
                    if left and left.type == "expression_list":
                        for child in left.children:
                            if child.type == "identifier":
                                loop_vars.add(_get_node_text(child, content))
                    elif left and left.type == "identifier":
                        loop_vars.add(_get_node_text(left, content))

        return loop_vars

    def _find_enclosing_loops(node: Any) -> list[set[str]]:
        """Walk up the tree to find all enclosing for/range loops and their variables."""
        loop_var_sets = []
        current = node.parent

        while current is not None:
            if current.type in ("for_statement", "for_range_statement"):
                loop_vars = _get_loop_variables(current)
                if loop_vars:
                    loop_var_sets.append(loop_vars)
            current = current.parent

        return loop_var_sets

    def visit(node: Any):
        nonlocal goroutine_id

        if node.type == "go_statement":
            call_expr = _find_child_by_type(node, "call_expression")
            if call_expr:
                func_lit = _find_child_by_type(call_expr, "func_literal")
                if func_lit:
                    enclosing_loop_vars = set()
                    for loop_var_set in _find_enclosing_loops(node):
                        enclosing_loop_vars.update(loop_var_set)

                    param_list = _find_child_by_type(func_lit, "parameter_list")
                    func_params = _collect_declared_in_params(param_list)

                    func_body = _find_child_by_type(func_lit, "block")
                    if func_body:
                        used_in_body = _collect_identifiers_in_node(func_body)

                        declared_in_body = _collect_declared_in_block(func_body)

                        builtins = {
                            "nil",
                            "true",
                            "false",
                            "iota",
                            "make",
                            "new",
                            "len",
                            "cap",
                            "append",
                            "copy",
                            "delete",
                            "close",
                            "panic",
                            "recover",
                            "print",
                            "println",
                            "error",
                            "string",
                            "int",
                            "int8",
                            "int16",
                            "int32",
                            "int64",
                            "uint",
                            "uint8",
                            "uint16",
                            "uint32",
                            "uint64",
                            "float32",
                            "float64",
                            "complex64",
                            "complex128",
                            "bool",
                            "byte",
                            "rune",
                            "uintptr",
                        }

                        captured = used_in_body - declared_in_body - func_params - builtins

                        for var_name in captured:
                            if "." in var_name:
                                continue

                            is_loop_var = var_name in enclosing_loop_vars

                            captured_vars.append(
                                {
                                    "file_path": file_path,
                                    "line": node.start_point[0] + 1,
                                    "goroutine_id": goroutine_id,
                                    "var_name": var_name,
                                    "var_type": None,
                                    "is_loop_var": is_loop_var,
                                }
                            )

                    goroutine_id += 1

        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return captured_vars
