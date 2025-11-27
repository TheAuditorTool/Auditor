"""Tree-sitter generic AST extraction implementations.

This module contains Tree-sitter extraction logic that works across multiple languages.

CRITICAL: Tree-sitter is FORBIDDEN for JavaScript/TypeScript files.
It produces corrupted data (e.g., "anonymous" function names).
JS/TS MUST use TypeScript Compiler API (semantic parser) - NO EXCEPTIONS.
"""

from typing import Any

from .base import (
    find_containing_function_tree_sitter,
    sanitize_call_name,
)


def _check_js_ts_forbidden(language: str) -> None:
    """Enforce that Tree-sitter is NEVER used for JavaScript/TypeScript.

    Tree-sitter produces corrupted data for JS/TS (e.g., "anonymous" function names).
    These languages MUST use the TypeScript Compiler API semantic parser.

    Args:
        language: The programming language being parsed

    Raises:
        RuntimeError: If language is JavaScript or TypeScript
    """
    if language in ["javascript", "typescript"]:
        raise RuntimeError(
            f"FATAL: Tree-sitter is FORBIDDEN for {language} files.\n"
            f"Tree-sitter produces corrupted data (anonymous function names, broken call graphs).\n"
            f"JavaScript/TypeScript MUST use TypeScript Compiler API semantic parser.\n"
            f"This is a bug in the parser selection logic - tree-sitter should never be called for JS/TS.\n"
            f"Ensure ast_parser.py fails loudly if semantic parser is unavailable."
        )


def extract_treesitter_functions(tree: dict, parser_self, language: str) -> list[dict]:
    """Extract function definitions from Tree-sitter AST."""
    _check_js_ts_forbidden(language)

    actual_tree = tree.get("tree")
    if not actual_tree:
        return []

    if not parser_self.has_tree_sitter:
        return []

    return _extract_tree_sitter_functions(actual_tree.root_node, language)


def _extract_tree_sitter_functions(node: Any, language: str) -> list[dict]:
    """Extract functions from Tree-sitter AST."""
    functions = []

    if node is None:
        return functions

    function_types = {
        "python": ["function_definition"],
        "javascript": [
            "function_declaration",
            "arrow_function",
            "function_expression",
            "method_definition",
        ],
        "typescript": [
            "function_declaration",
            "arrow_function",
            "function_expression",
            "method_definition",
        ],
    }

    node_types = function_types.get(language, [])

    if node.type in node_types:
        name = "anonymous"
        for child in node.children:
            if child.type in ["identifier", "property_identifier"]:
                name = child.text.decode("utf-8", errors="ignore")
                break

        functions.append(
            {
                "name": name,
                "line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "type": node.type,
            }
        )

    for child in node.children:
        functions.extend(_extract_tree_sitter_functions(child, language))

    seen = set()
    deduped = []
    for f in functions:
        key = (f["name"], f["line"], f["type"])
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    return deduped


def extract_treesitter_classes(tree: dict, parser_self, language: str) -> list[dict]:
    """Extract class definitions from Tree-sitter AST."""
    _check_js_ts_forbidden(language)

    actual_tree = tree.get("tree")
    if not actual_tree:
        return []

    if not parser_self.has_tree_sitter:
        return []

    return _extract_tree_sitter_classes(actual_tree.root_node, language)


def _extract_tree_sitter_classes(node: Any, language: str) -> list[dict]:
    """Extract classes from Tree-sitter AST."""
    classes = []

    if node is None:
        return classes

    class_types = {
        "python": ["class_definition"],
        "javascript": ["class_declaration"],
        "typescript": ["class_declaration", "interface_declaration"],
    }

    node_types = class_types.get(language, [])

    if node.type in node_types:
        name = "anonymous"
        for child in node.children:
            if child.type in ["identifier", "type_identifier"]:
                name = child.text.decode("utf-8", errors="ignore")
                break

        classes.append(
            {
                "name": name,
                "line": node.start_point[0] + 1,
                "column": node.start_point[1],
                "type": node.type,
            }
        )

    for child in node.children:
        classes.extend(_extract_tree_sitter_classes(child, language))

    seen = set()
    deduped = []
    for c in classes:
        key = (c["name"], c["line"], c["type"], c["column"])
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    return deduped


def extract_treesitter_calls(tree: dict, parser_self, language: str) -> list[dict]:
    """Extract function calls from Tree-sitter AST."""
    _check_js_ts_forbidden(language)

    actual_tree = tree.get("tree")
    if not actual_tree:
        return []

    if not parser_self.has_tree_sitter:
        return []

    return _extract_tree_sitter_calls(actual_tree.root_node, language)


def _extract_tree_sitter_calls(node: Any, language: str) -> list[dict]:
    """Extract function calls from Tree-sitter AST."""
    calls = []

    if node is None:
        return calls

    call_types = {
        "python": ["call"],
        "javascript": ["call_expression"],
        "typescript": ["call_expression"],
    }

    node_types = call_types.get(language, [])

    if node.type in node_types:
        name = "unknown"
        for child in node.children:
            if child.type in ["identifier", "member_expression", "attribute"]:
                name = child.text.decode("utf-8", errors="ignore")
                break

            elif child.type == "member_access_expression":
                name = child.text.decode("utf-8", errors="ignore")
                break

        calls.append(
            {
                "name": name,
                "line": node.start_point[0] + 1,
                "column": node.start_point[1],
                "type": "call",
            }
        )

    for child in node.children:
        calls.extend(_extract_tree_sitter_calls(child, language))

    return calls


def extract_treesitter_imports(tree: dict, parser_self, language: str) -> list[dict[str, Any]]:
    """Extract import statements from Tree-sitter AST."""
    _check_js_ts_forbidden(language)

    actual_tree = tree.get("tree")
    if not actual_tree:
        return []

    if not parser_self.has_tree_sitter:
        return []

    return _extract_tree_sitter_imports(actual_tree.root_node, language)


def _extract_tree_sitter_imports(node: Any, language: str) -> list[dict[str, Any]]:
    """Extract imports from Tree-sitter AST with language-specific handling."""
    imports = []

    if node is None:
        return imports

    import_types = {
        "javascript": ["import_statement", "import_clause", "require_call"],
        "typescript": ["import_statement", "import_clause", "require_call", "import_type"],
        "python": ["import_statement", "import_from_statement"],
    }

    node_types = import_types.get(language, [])

    if node.type in node_types:
        if node.type == "import_statement":
            module_name = None
            default_import = None
            namespace_import = None
            named_imports = []

            for child in node.children:
                if child.type == "string":
                    module_name = child.text.decode("utf-8", errors="ignore").strip("\"'")
                elif child.type == "import_clause":
                    for spec_child in child.children:
                        if spec_child.type == "identifier" and default_import is None:
                            default_import = spec_child.text.decode("utf-8", errors="ignore")
                        elif spec_child.type == "namespace_import":
                            name_node = spec_child.child_by_field_name("name")
                            if name_node and name_node.text:
                                namespace_import = name_node.text.decode("utf-8", errors="ignore")
                        elif spec_child.type == "named_imports":
                            for element in spec_child.children:
                                if element.type == "import_specifier":
                                    name_node = element.child_by_field_name("name")
                                    if name_node and name_node.text:
                                        named_imports.append(
                                            name_node.text.decode("utf-8", errors="ignore")
                                        )

            if module_name:
                imports.append(
                    {
                        "source": "import",
                        "target": module_name,
                        "type": "import",
                        "line": node.start_point[0] + 1,
                        "specifiers": named_imports,
                        "namespace": namespace_import,
                        "default": default_import,
                        "names": named_imports,
                        "text": None,
                    }
                )

        elif node.type == "require_call":
            for child in node.children:
                if child.type == "string":
                    target = child.text.decode("utf-8", errors="ignore").strip("\"'")
                    imports.append(
                        {
                            "source": "require",
                            "target": target,
                            "type": "require",
                            "line": node.start_point[0] + 1,
                            "specifiers": [],
                            "names": [],
                            "namespace": None,
                            "default": None,
                            "text": None,
                        }
                    )

    for child in node.children:
        imports.extend(_extract_tree_sitter_imports(child, language))

    return imports


def extract_treesitter_exports(tree: dict, parser_self, language: str) -> list[dict[str, Any]]:
    """Extract export statements from Tree-sitter AST."""
    _check_js_ts_forbidden(language)

    actual_tree = tree.get("tree")
    if not actual_tree:
        return []

    if not parser_self.has_tree_sitter:
        return []

    return _extract_tree_sitter_exports(actual_tree.root_node, language)


def _extract_tree_sitter_exports(node: Any, language: str) -> list[dict[str, Any]]:
    """Extract exports from Tree-sitter AST."""
    exports = []

    if node is None:
        return exports

    export_types = {
        "javascript": ["export_statement", "export_default_declaration"],
        "typescript": ["export_statement", "export_default_declaration", "export_type"],
    }

    node_types = export_types.get(language, [])

    if node.type in node_types:
        is_default = "default" in node.type

        name = "unknown"
        export_type = "unknown"

        for child in node.children:
            if child.type in ["identifier", "type_identifier"]:
                name = child.text.decode("utf-8", errors="ignore")
            elif child.type == "function_declaration":
                export_type = "function"
                for subchild in child.children:
                    if subchild.type == "identifier":
                        name = subchild.text.decode("utf-8", errors="ignore")
                        break
            elif child.type == "class_declaration":
                export_type = "class"
                for subchild in child.children:
                    if subchild.type in ["identifier", "type_identifier"]:
                        name = subchild.text.decode("utf-8", errors="ignore")
                        break

        exports.append(
            {
                "name": name,
                "type": export_type,
                "line": node.start_point[0] + 1,
                "default": is_default,
            }
        )

    for child in node.children:
        exports.extend(_extract_tree_sitter_exports(child, language))

    return exports


def extract_treesitter_properties(tree: dict, parser_self, language: str) -> list[dict]:
    """Extract property accesses from Tree-sitter AST."""
    _check_js_ts_forbidden(language)

    actual_tree = tree.get("tree")
    if not actual_tree:
        return []

    if not parser_self.has_tree_sitter:
        return []

    return _extract_tree_sitter_properties(actual_tree.root_node, language)


def _extract_tree_sitter_properties(node: Any, language: str) -> list[dict]:
    """Extract property accesses from Tree-sitter AST."""
    properties = []

    if node is None:
        return properties

    property_types = {
        "javascript": ["member_expression", "property_access_expression"],
        "typescript": ["member_expression", "property_access_expression"],
        "python": ["attribute"],
    }

    node_types = property_types.get(language, [])

    if node.type in node_types:
        prop_text = node.text.decode("utf-8", errors="ignore") if node.text else ""

        if any(
            pattern in prop_text
            for pattern in [
                "req.",
                "request.",
                "ctx.",
                "body",
                "query",
                "params",
                "headers",
                "cookies",
            ]
        ):
            properties.append(
                {
                    "name": prop_text,
                    "line": node.start_point[0] + 1,
                    "column": node.start_point[1],
                    "type": "property",
                }
            )

    for child in node.children:
        properties.extend(_extract_tree_sitter_properties(child, language))

    return properties


def extract_treesitter_assignments(tree: dict, parser_self, language: str) -> list[dict[str, Any]]:
    """Extract variable assignments from Tree-sitter AST."""
    _check_js_ts_forbidden(language)

    actual_tree = tree.get("tree")
    content = tree.get("content", "")

    if not actual_tree:
        return []

    if not parser_self.has_tree_sitter:
        return []

    return _extract_tree_sitter_assignments(actual_tree.root_node, language, content)


def _extract_tree_sitter_assignments(
    node: Any, language: str, content: str
) -> list[dict[str, Any]]:
    """Extract assignments from Tree-sitter AST."""
    import os
    import sys

    debug = os.environ.get("THEAUDITOR_DEBUG")
    assignments = []

    if node is None:
        return assignments

    assignment_types = {
        "javascript": ["assignment_expression", "lexical_declaration", "variable_declaration"],
        "typescript": ["assignment_expression", "lexical_declaration", "variable_declaration"],
        "python": ["assignment"],
    }

    node_types = assignment_types.get(language, [])

    if node.type in node_types:
        target_var = None
        source_expr = None
        source_vars = []

        if node.type in ["lexical_declaration", "variable_declaration"]:
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    value_node = child.child_by_field_name("value")

                    if name_node and value_node:
                        in_function = (
                            find_containing_function_tree_sitter(child, content, language)
                            or "global"
                        )
                        if debug:
                            print(
                                f"[DEBUG] Found assignment: {name_node.text.decode('utf-8')} = {value_node.text.decode('utf-8')[:50]}",
                                file=sys.stderr,
                            )
                        assignments.append(
                            {
                                "target_var": name_node.text.decode("utf-8", errors="ignore"),
                                "source_expr": value_node.text.decode("utf-8", errors="ignore"),
                                "line": child.start_point[0] + 1,
                                "in_function": in_function,
                                "source_vars": [],
                            }
                        )

        elif node.type == "assignment_expression":
            left_node = node.child_by_field_name("left")
            right_node = node.child_by_field_name("right")

            if left_node:
                target_var = left_node.text.decode("utf-8", errors="ignore")
            if right_node:
                source_expr = right_node.text.decode("utf-8", errors="ignore")

                source_vars = []

        elif node.type == "assignment":
            left_node = None
            right_node = None
            for child in node.children:
                if child.type != "=" and left_node is None:
                    left_node = child
                elif child.type != "=" and left_node is not None:
                    right_node = child

            if left_node:
                target_var = (
                    left_node.text.decode("utf-8", errors="ignore") if left_node.text else ""
                )
            if right_node:
                source_expr = (
                    right_node.text.decode("utf-8", errors="ignore") if right_node.text else ""
                )

        if (
            target_var
            and source_expr
            and node.type not in ["lexical_declaration", "variable_declaration"]
        ):
            in_function = find_containing_function_tree_sitter(node, content, language)

            assignments.append(
                {
                    "target_var": target_var,
                    "source_expr": source_expr,
                    "line": node.start_point[0] + 1,
                    "in_function": in_function or "global",
                    "source_vars": source_vars if source_vars else [],
                }
            )

    for child in node.children:
        assignments.extend(_extract_tree_sitter_assignments(child, language, content))

    seen = set()
    deduped = []
    for a in assignments:
        key = (a["line"], a["target_var"], a["in_function"])
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    return deduped


def extract_treesitter_function_params(
    tree: dict, parser_self, language: str
) -> dict[str, list[str]]:
    """Extract function parameters from Tree-sitter AST."""
    _check_js_ts_forbidden(language)

    actual_tree = tree.get("tree")
    if not actual_tree:
        return {}

    if not parser_self.has_tree_sitter:
        return {}

    return _extract_tree_sitter_function_params(actual_tree.root_node, language)


def _extract_tree_sitter_function_params(node: Any, language: str) -> dict[str, list[str]]:
    """Extract function parameters from Tree-sitter AST."""
    func_params = {}

    if node is None:
        return func_params

    if language in ["javascript", "typescript"]:
        if node.type in [
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
        ]:
            func_name = "anonymous"
            params = []

            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")

            if name_node:
                func_name = name_node.text.decode("utf-8", errors="ignore")

            if not params_node:
                for child in node.children:
                    if child.type in ["formal_parameters", "parameters"]:
                        params_node = child
                        break

            if params_node:
                for param_child in params_node.children:
                    if param_child.type in [
                        "identifier",
                        "required_parameter",
                        "optional_parameter",
                    ]:
                        if param_child.type == "identifier":
                            params.append(param_child.text.decode("utf-8", errors="ignore"))
                        else:
                            pattern_node = param_child.child_by_field_name("pattern")
                            if pattern_node and pattern_node.type == "identifier":
                                params.append(pattern_node.text.decode("utf-8", errors="ignore"))

            if func_name and params:
                func_params[func_name] = params

    elif language == "python":
        if node.type == "function_definition":
            func_name = None
            params = []

            for child in node.children:
                if child.type == "identifier":
                    func_name = child.text.decode("utf-8", errors="ignore")
                elif child.type == "parameters":
                    for param_child in child.children:
                        if param_child.type == "identifier":
                            params.append(param_child.text.decode("utf-8", errors="ignore"))

            if func_name:
                func_params[func_name] = params

    for child in node.children:
        func_params.update(_extract_tree_sitter_function_params(child, language))

    return func_params


def extract_treesitter_calls_with_args(
    tree: dict, function_params: dict[str, list[str]], parser_self, language: str
) -> list[dict[str, Any]]:
    """Extract function calls with arguments from Tree-sitter AST."""
    _check_js_ts_forbidden(language)

    actual_tree = tree.get("tree")
    content = tree.get("content", "")

    if not actual_tree:
        return []

    if not parser_self.has_tree_sitter:
        return []

    return _extract_tree_sitter_calls_with_args(
        actual_tree.root_node, language, content, function_params
    )


def _extract_tree_sitter_calls_with_args(
    node: Any, language: str, content: str, function_params: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """Extract function calls with arguments from Tree-sitter AST."""
    calls = []

    if node is None:
        return calls

    if language in ["javascript", "typescript"] and node.type == "call_expression":
        func_node = node.child_by_field_name("function")
        func_name = "unknown"

        if func_node:
            func_name = (
                func_node.text.decode("utf-8", errors="ignore") if func_node.text else "unknown"
            )
        else:
            for child in node.children:
                if child.type in ["identifier", "member_expression"]:
                    func_name = (
                        child.text.decode("utf-8", errors="ignore") if child.text else "unknown"
                    )
                    break

        func_name = sanitize_call_name(func_name)

        caller_function = find_containing_function_tree_sitter(node, content, language) or "global"

        callee_params = function_params.get(func_name.split(".")[-1], [])

        args_node = node.child_by_field_name("arguments")
        arg_index = 0

        if args_node:
            for arg_child in args_node.children:
                if arg_child.type not in ["(", ")", ","]:
                    arg_expr = (
                        arg_child.text.decode("utf-8", errors="ignore") if arg_child.text else ""
                    )
                    param_name = (
                        callee_params[arg_index]
                        if arg_index < len(callee_params)
                        else f"arg{arg_index}"
                    )

                    calls.append(
                        {
                            "line": node.start_point[0] + 1,
                            "caller_function": caller_function,
                            "callee_function": func_name,
                            "argument_index": arg_index,
                            "argument_expr": arg_expr,
                            "param_name": param_name,
                        }
                    )
                    arg_index += 1

    elif language == "python" and node.type == "call":
        func_name = "unknown"
        for child in node.children:
            if child.type in ["identifier", "attribute"]:
                func_name = child.text.decode("utf-8", errors="ignore") if child.text else "unknown"
                break

        func_name = sanitize_call_name(func_name)

        caller_function = find_containing_function_tree_sitter(node, content, language) or "global"
        callee_params = function_params.get(func_name.split(".")[-1], [])

        arg_index = 0
        for child in node.children:
            if child.type == "argument_list":
                for arg_child in child.children:
                    if arg_child.type not in ["(", ")", ","]:
                        arg_expr = (
                            arg_child.text.decode("utf-8", errors="ignore")
                            if arg_child.text
                            else ""
                        )
                        param_name = (
                            callee_params[arg_index]
                            if arg_index < len(callee_params)
                            else f"arg{arg_index}"
                        )

                        calls.append(
                            {
                                "line": node.start_point[0] + 1,
                                "caller_function": caller_function,
                                "callee_function": func_name,
                                "argument_index": arg_index,
                                "argument_expr": arg_expr,
                                "param_name": param_name,
                            }
                        )
                        arg_index += 1

    for child in node.children:
        calls.extend(
            _extract_tree_sitter_calls_with_args(child, language, content, function_params)
        )

    return calls


def extract_treesitter_returns(tree: dict, parser_self, language: str) -> list[dict[str, Any]]:
    """Extract return statements from Tree-sitter AST."""
    _check_js_ts_forbidden(language)

    actual_tree = tree.get("tree")
    content = tree.get("content", "")

    if not actual_tree:
        return []

    if not parser_self.has_tree_sitter:
        return []

    return _extract_tree_sitter_returns(actual_tree.root_node, language, content)


def _extract_tree_sitter_returns(node: Any, language: str, content: str) -> list[dict[str, Any]]:
    """Extract return statements from Tree-sitter AST."""
    returns = []

    if node is None:
        return returns

    if language in ["javascript", "typescript"] and node.type == "return_statement":
        function_name = find_containing_function_tree_sitter(node, content, language) or "global"

        return_expr = ""
        for child in node.children:
            if child.type != "return":
                return_expr = child.text.decode("utf-8", errors="ignore") if child.text else ""
                break

        if not return_expr:
            return_expr = "undefined"

        returns.append(
            {
                "function_name": function_name,
                "line": node.start_point[0] + 1,
                "return_expr": return_expr,
                "return_vars": [],
            }
        )

    elif language == "python" and node.type == "return_statement":
        function_name = find_containing_function_tree_sitter(node, content, language) or "global"

        return_expr = ""
        for child in node.children:
            if child.type != "return":
                return_expr = child.text.decode("utf-8", errors="ignore") if child.text else ""
                break

        if not return_expr:
            return_expr = "None"

        returns.append(
            {
                "function_name": function_name,
                "line": node.start_point[0] + 1,
                "return_expr": return_expr,
                "return_vars": [],
            }
        )

    for child in node.children:
        returns.extend(_extract_tree_sitter_returns(child, language, content))

    seen = set()
    deduped = []
    for r in returns:
        key = (r["line"], r["function_name"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return deduped


def extract_treesitter_cfg(tree: dict, parser_self, language: str) -> list[dict[str, Any]]:
    """Extract control flow graph from tree-sitter AST.

    NOTE: CFG extraction not implemented for generic tree-sitter.
    Python projects should use Python's ast module (type="python_ast").
    TypeScript projects should use semantic parser (type="semantic_ast").
    Both have language-specific CFG implementations.

    This stub prevents extraction failures when tree-sitter is used as fallback.

    Args:
        tree: Parsed AST tree dictionary
        parser_self: ASTParser instance (for compatibility)
        language: Source language (for compatibility)

    Returns:
        Empty list (no CFG data from generic tree-sitter)
    """
    _check_js_ts_forbidden(language)

    return []
