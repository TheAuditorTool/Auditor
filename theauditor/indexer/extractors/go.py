"""Go file extractor."""

from pathlib import Path
from typing import Any

from theauditor.utils.logging import logger

from ..fidelity_utils import FidelityToken
from . import BaseExtractor


class GoExtractor(BaseExtractor):
    """Extractor for Go source files."""

    def __init__(self, root_path: Path, ast_parser: Any | None = None):
        """Initialize Go extractor."""
        super().__init__(root_path, ast_parser)

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return [".go"]

    def extract(
        self, file_info: dict[str, Any], content: str, tree: Any | None = None
    ) -> dict[str, Any]:
        """Extract all relevant information from a Go file."""
        file_path = file_info["path"]

        if file_path.endswith("_test.go"):
            return {}

        if not (tree and tree.get("type") == "tree_sitter" and tree.get("tree")):
            logger.error(
                "Tree-sitter failed to parse Go file: %s. "
                "Check tree-sitter-language-pack installation or file syntax.",
                file_path,
            )
            return {}

        from ...ast_extractors import go_impl
        from ...ast_extractors.base import check_tree_sitter_parse_quality

        ts_tree = tree["tree"]
        check_tree_sitter_parse_quality(ts_tree.root_node, file_path, logger)

        package = go_impl.extract_go_package(ts_tree, content, file_path)
        imports = go_impl.extract_go_imports(ts_tree, content, file_path)
        structs = go_impl.extract_go_structs(ts_tree, content, file_path)
        struct_fields = go_impl.extract_go_struct_fields(ts_tree, content, file_path)
        interfaces = go_impl.extract_go_interfaces(ts_tree, content, file_path)
        interface_methods = go_impl.extract_go_interface_methods(ts_tree, content, file_path)
        functions = go_impl.extract_go_functions(ts_tree, content, file_path)
        methods = go_impl.extract_go_methods(ts_tree, content, file_path)
        func_params = go_impl.extract_go_func_params(ts_tree, content, file_path)
        func_returns = go_impl.extract_go_func_returns(ts_tree, content, file_path)
        goroutines = go_impl.extract_go_goroutines(ts_tree, content, file_path)
        channels = go_impl.extract_go_channels(ts_tree, content, file_path)
        channel_ops = go_impl.extract_go_channel_ops(ts_tree, content, file_path)
        defer_statements = go_impl.extract_go_defer_statements(ts_tree, content, file_path)
        constants = go_impl.extract_go_constants(ts_tree, content, file_path)
        variables = go_impl.extract_go_variables(ts_tree, content, file_path)
        type_params = go_impl.extract_go_type_params(ts_tree, content, file_path)
        type_assertions = go_impl.extract_go_type_assertions(ts_tree, content, file_path)
        error_returns = go_impl.extract_go_error_returns(ts_tree, content, file_path)

        routes = self._detect_routes(imports, ts_tree, content, file_path)
        middleware = self._detect_middleware(imports, ts_tree, content, file_path)

        captured_vars = go_impl.extract_go_captured_vars(ts_tree, content, file_path, goroutines)

        symbols = []
        for func in functions:
            symbols.append(
                {
                    "path": file_path,
                    "name": func.get("name", ""),
                    "type": "function",
                    "line": func.get("line", 0),
                    "col": 0,
                    "end_line": func.get("end_line"),
                    "parameters": func.get("signature"),
                }
            )
        for method in methods:
            symbols.append(
                {
                    "path": file_path,
                    "name": method.get("name", ""),
                    "type": "function",
                    "line": method.get("line", 0),
                    "col": 0,
                    "end_line": method.get("end_line"),
                    "parameters": method.get("signature"),
                }
            )
        for struct in structs:
            symbols.append(
                {
                    "path": file_path,
                    "name": struct.get("name", ""),
                    "type": "class",
                    "line": struct.get("line", 0),
                    "col": 0,
                    "end_line": struct.get("end_line"),
                }
            )
        for iface in interfaces:
            symbols.append(
                {
                    "path": file_path,
                    "name": iface.get("name", ""),
                    "type": "class",
                    "line": iface.get("line", 0),
                    "col": 0,
                    "end_line": iface.get("end_line"),
                }
            )

        imports_for_refs = []
        for imp in imports:
            imports_for_refs.append(
                {
                    "kind": "import",
                    "value": imp.get("path", ""),
                    "line": imp.get("line"),
                }
            )

        result = {
            "symbols": symbols,
            "imports": imports_for_refs,
            "assignments": self._extract_assignments(ts_tree, file_path, content),
            "function_calls": self._extract_function_calls(ts_tree, file_path, content),
            "returns": self._extract_returns(ts_tree, file_path, content),
            "go_packages": [package] if package else [],
            "go_imports": imports,
            "go_structs": structs,
            "go_struct_fields": struct_fields,
            "go_interfaces": interfaces,
            "go_interface_methods": interface_methods,
            "go_functions": functions,
            "go_methods": methods,
            "go_func_params": func_params,
            "go_func_returns": func_returns,
            "go_goroutines": goroutines,
            "go_channels": channels,
            "go_channel_ops": channel_ops,
            "go_defer_statements": defer_statements,
            "go_constants": constants,
            "go_variables": variables,
            "go_type_params": type_params,
            "go_type_assertions": type_assertions,
            "go_error_returns": error_returns,
            "go_routes": routes,
            "go_middleware": middleware,
            "go_captured_vars": captured_vars,
        }

        total_items = sum(len(v) for v in result.values() if isinstance(v, list))
        loop_var_captures = sum(1 for cv in captured_vars if cv.get("is_loop_var"))
        dfg_assignments = len(result.get("assignments", []))
        dfg_calls = len(result.get("function_calls", []))
        dfg_returns = len(result.get("returns", []))
        logger.debug(
            f"Extracted Go: {file_path} -> "
            f"{len(functions)} funcs, {len(structs)} structs, "
            f"{len(goroutines)} goroutines, {len(captured_vars)} captured vars "
            f"({loop_var_captures} loop vars), "
            f"DFG: {dfg_assignments} assigns, {dfg_calls} calls, {dfg_returns} returns, "
            f"{total_items} total items"
        )

        return FidelityToken.attach_manifest(result)

    def _detect_routes(
        self, imports: list[dict], tree: Any, content: str, file_path: str
    ) -> list[dict]:
        """Detect HTTP route registrations from web frameworks."""
        routes = []
        framework = self._detect_web_framework(imports)

        if not framework:
            return routes

        route_patterns = self._get_framework_route_patterns(framework)

        for pattern in route_patterns:
            routes.extend(self._find_route_calls(tree, content, file_path, framework, pattern))

        return routes

    def _detect_web_framework(self, imports: list[dict]) -> str | None:
        """Detect which web framework is being used from imports."""
        framework_imports = {
            "github.com/gin-gonic/gin": "gin",
            "github.com/labstack/echo": "echo",
            "github.com/labstack/echo/v4": "echo",
            "github.com/gofiber/fiber": "fiber",
            "github.com/gofiber/fiber/v2": "fiber",
            "github.com/go-chi/chi": "chi",
            "github.com/go-chi/chi/v5": "chi",
            "net/http": "net_http",
            "google.golang.org/grpc": "grpc",
        }

        for imp in imports:
            path = imp.get("path", "")
            for import_path, framework in framework_imports.items():
                if path == import_path or path.startswith(import_path + "/"):
                    return framework

        return None

    def _get_framework_route_patterns(self, framework: str) -> list[str]:
        """Get route method names for each framework."""
        patterns = {
            "gin": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "Handle", "Any"],
            "echo": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "Add", "Any"],
            "fiber": ["Get", "Post", "Put", "Delete", "Patch", "Head", "Options", "All"],
            "chi": ["Get", "Post", "Put", "Delete", "Patch", "Head", "Options", "Handle", "Method"],
            "net_http": ["HandleFunc", "Handle"],
            "grpc": ["RegisterServiceServer", "RegisterService"],
        }
        return patterns.get(framework, [])

    def _find_route_calls(
        self, tree: Any, content: str, file_path: str, framework: str, method: str
    ) -> list[dict]:
        """Find route registration calls in the AST."""
        routes = []

        def visit(node: Any):
            if node.type == "call_expression":
                func_node = node.children[0] if node.children else None
                if func_node and func_node.type == "selector_expression":
                    selector_text = func_node.text.decode("utf-8", errors="ignore")
                    if selector_text.endswith(f".{method}"):
                        args = None
                        for child in node.children:
                            if child.type == "argument_list":
                                args = child
                                break

                        if args and args.children:
                            path = None
                            handler = None
                            for arg in args.children:
                                if arg.type == "interpreted_string_literal":
                                    path = arg.text.decode("utf-8", errors="ignore").strip('"')
                                elif arg.type in (
                                    "identifier",
                                    "selector_expression",
                                    "func_literal",
                                ):
                                    if path is not None:
                                        handler = arg.text.decode("utf-8", errors="ignore")[:100]

                            if path:
                                routes.append(
                                    {
                                        "file_path": file_path,
                                        "line": node.start_point[0] + 1,
                                        "framework": framework,
                                        "method": method.upper()
                                        if method not in ("HandleFunc", "Handle")
                                        else "GET",
                                        "path": path,
                                        "handler_func": handler,
                                    }
                                )

            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return routes

    def _detect_middleware(
        self, imports: list[dict], tree: Any, content: str, file_path: str
    ) -> list[dict]:
        """Detect middleware registrations from web frameworks."""
        middleware = []
        framework = self._detect_web_framework(imports)

        if not framework:
            return middleware

        middleware_patterns = self._get_framework_middleware_patterns(framework)

        for pattern in middleware_patterns:
            middleware.extend(
                self._find_middleware_calls(tree, content, file_path, framework, pattern)
            )

        return middleware

    def _get_framework_middleware_patterns(self, framework: str) -> list[str]:
        """Get middleware method names for each framework."""
        patterns = {
            "gin": ["Use", "Group"],
            "echo": ["Use", "Pre", "Group"],
            "fiber": ["Use", "Group"],
            "chi": ["Use", "With", "Group"],
            "net_http": [],
            "grpc": [
                "UnaryInterceptor",
                "StreamInterceptor",
                "ChainUnaryInterceptor",
                "ChainStreamInterceptor",
            ],
        }
        return patterns.get(framework, [])

    def _find_middleware_calls(
        self, tree: Any, content: str, file_path: str, framework: str, method: str
    ) -> list[dict]:
        """Find middleware registration calls in the AST."""
        middleware = []

        def visit(node: Any):
            if node.type == "call_expression":
                func_node = node.children[0] if node.children else None
                if func_node and func_node.type == "selector_expression":
                    selector_text = func_node.text.decode("utf-8", errors="ignore")
                    if selector_text.endswith(f".{method}"):
                        parts = selector_text.split(".")
                        router_var = parts[0] if parts else None

                        middleware_func = None
                        for child in node.children:
                            if child.type == "argument_list":
                                for arg in child.children:
                                    if arg.type in (
                                        "identifier",
                                        "selector_expression",
                                        "call_expression",
                                    ):
                                        middleware_func = arg.text.decode("utf-8", errors="ignore")[
                                            :100
                                        ]
                                        break

                        if middleware_func:
                            middleware.append(
                                {
                                    "file_path": file_path,
                                    "line": node.start_point[0] + 1,
                                    "framework": framework,
                                    "router_var": router_var,
                                    "middleware_func": middleware_func,
                                    "is_global": method == "Use",
                                }
                            )

            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return middleware

    def _find_all_nodes(self, root_node: Any, node_type: str) -> list[Any]:
        """Recursively find all nodes of given type in the AST.

        Args:
            root_node: Tree-sitter root node to search from
            node_type: Type string to match (e.g., "short_var_declaration")

        Returns:
            List of matching tree-sitter nodes
        """
        results = []

        def visit(node: Any) -> None:
            if node.type == node_type:
                results.append(node)
            for child in node.children:
                visit(child)

        visit(root_node)
        return results

    def _extract_assignments(self, tree: Any, file_path: str, content: str) -> list[dict[str, Any]]:
        """Extract variable assignments for language-agnostic DFG tables.

        Handles:
        - Short variable declaration: x := expr
        - Regular assignment: x = expr
        - Multiple assignment targets: a, b := getPair()
        - Skips blank identifier (_)

        Storage handler: core_storage._store_assignments()
        Target table: assignments (with assignment_sources populated from source_vars)

        Args:
            tree: Tree-sitter tree object
            file_path: Path to the Go file
            content: File content string

        Returns:
            List of assignment dicts with keys matching storage handler expectations
        """
        assignments: list[dict[str, Any]] = []

        def get_node_text(node: Any) -> str:
            """Extract text from a tree-sitter node."""
            if node is None:
                return ""
            return node.text.decode("utf-8", errors="ignore")

        def get_containing_function(node: Any) -> str:
            """Walk up tree to find containing function/method name."""
            current = node.parent
            while current:
                if current.type == "function_declaration":
                    name_node = current.child_by_field_name("name")
                    if name_node:
                        return get_node_text(name_node)
                elif current.type == "method_declaration":
                    for child in current.children:
                        if child.type == "field_identifier":
                            return get_node_text(child)
                current = current.parent
            return "<module>"

        def extract_source_vars(expr_node: Any) -> list[str]:
            """Extract variable names referenced in expression.

            Filters out Go keywords/literals: nil, true, false
            """
            vars_list: list[str] = []

            def visit_expr(n: Any) -> None:
                if n.type == "identifier":
                    name = get_node_text(n)

                    if name and name not in ("nil", "true", "false"):
                        vars_list.append(name)
                elif n.type == "selector_expression":
                    text = get_node_text(n)
                    if text:
                        vars_list.append(text)
                    return
                for child in n.children:
                    visit_expr(child)

            if expr_node:
                visit_expr(expr_node)
            return list(dict.fromkeys(vars_list))

        def extract_targets(left_node: Any) -> list[Any]:
            """Extract target identifier nodes from left side of assignment."""
            targets = []
            if left_node is None:
                return targets

            if left_node.type == "identifier":
                targets.append(left_node)
            elif left_node.type == "expression_list":
                for child in left_node.children:
                    if child.type == "identifier":
                        targets.append(child)
            return targets

        for node in self._find_all_nodes(tree.root_node, "short_var_declaration"):
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")

            if not (left and right):
                continue

            in_function = get_containing_function(node)
            source_expr = get_node_text(right)
            source_vars = extract_source_vars(right)

            for target in extract_targets(left):
                target_name = get_node_text(target)
                if target_name == "_":
                    continue

                assignments.append(
                    {
                        "file": file_path,
                        "line": node.start_point[0] + 1,
                        "col": node.start_point[1],
                        "target_var": target_name,
                        "source_expr": source_expr[:500] if source_expr else "",
                        "in_function": in_function,
                        "property_path": None,
                        "source_vars": source_vars,
                    }
                )

        for node in self._find_all_nodes(tree.root_node, "assignment_statement"):
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")

            if not (left and right):
                continue

            in_function = get_containing_function(node)
            source_expr = get_node_text(right)
            source_vars = extract_source_vars(right)

            for target in extract_targets(left):
                target_name = get_node_text(target)
                if target_name == "_":
                    continue

                assignments.append(
                    {
                        "file": file_path,
                        "line": node.start_point[0] + 1,
                        "col": node.start_point[1],
                        "target_var": target_name,
                        "source_expr": source_expr[:500] if source_expr else "",
                        "in_function": in_function,
                        "property_path": None,
                        "source_vars": source_vars,
                    }
                )

        if assignments:
            logger.debug(f"Go: extracted {len(assignments)} assignments from {file_path}")

        return assignments

    def _extract_function_calls(
        self, tree: Any, file_path: str, content: str
    ) -> list[dict[str, Any]]:
        """Extract function calls for language-agnostic call graph tables.

        Handles:
        - Simple function calls: foo(a, b)
        - Method calls: obj.Method(x)
        - Chained calls: a.B().C()

        Storage handler: core_storage._store_function_calls()
        Target table: function_call_args

        IMPORTANT: Return dict key must be "function_calls" (handler name),
        NOT "function_call_args" (table name). See core_storage.py:39.

        Args:
            tree: Tree-sitter tree object
            file_path: Path to the Go file
            content: File content string

        Returns:
            List of function call dicts with keys matching storage handler expectations
        """
        calls: list[dict[str, Any]] = []

        def get_node_text(node: Any) -> str:
            """Extract text from a tree-sitter node."""
            if node is None:
                return ""
            return node.text.decode("utf-8", errors="ignore")

        def get_containing_function(node: Any) -> str:
            """Walk up tree to find containing function/method name."""
            current = node.parent
            while current:
                if current.type == "function_declaration":
                    name_node = current.child_by_field_name("name")
                    if name_node:
                        return get_node_text(name_node)
                elif current.type == "method_declaration":
                    for child in current.children:
                        if child.type == "field_identifier":
                            return get_node_text(child)
                current = current.parent
            return "<module>"

        def get_callee_name(func_node: Any) -> str:
            """Extract the function/method name being called."""
            if func_node is None:
                return ""

            if func_node.type == "identifier" or func_node.type == "selector_expression":
                return get_node_text(func_node)
            elif func_node.type == "call_expression":
                inner_func = func_node.child_by_field_name("function")
                return get_callee_name(inner_func)
            else:
                return get_node_text(func_node)

        for node in self._find_all_nodes(tree.root_node, "call_expression"):
            func_node = node.child_by_field_name("function")
            args_node = node.child_by_field_name("arguments")

            callee_function = get_callee_name(func_node)
            caller_function = get_containing_function(node)
            line = node.start_point[0] + 1

            if not callee_function:
                continue

            args = []
            if args_node:
                for child in args_node.children:
                    if child.type not in ("(", ")", ","):
                        args.append(child)

            if not args:
                calls.append(
                    {
                        "file": file_path,
                        "line": line,
                        "caller_function": caller_function,
                        "callee_function": callee_function,
                        "argument_index": 0,
                        "argument_expr": "",
                        "param_name": "",
                        "callee_file_path": None,
                    }
                )
            else:
                for i, arg in enumerate(args):
                    arg_expr = get_node_text(arg)
                    calls.append(
                        {
                            "file": file_path,
                            "line": line,
                            "caller_function": caller_function,
                            "callee_function": callee_function,
                            "argument_index": i,
                            "argument_expr": arg_expr[:500] if arg_expr else "",
                            "param_name": "",
                            "callee_file_path": None,
                        }
                    )

        if calls:
            logger.debug(f"Go: extracted {len(calls)} function calls from {file_path}")

        return calls

    def _extract_returns(self, tree: Any, file_path: str, content: str) -> list[dict[str, Any]]:
        """Extract return statements for language-agnostic DFG tables.

        Handles:
        - Single return value: return x
        - Multiple return values: return a, b, nil
        - Naked returns (empty return in functions with named returns)

        Storage handler: core_storage._store_returns()
        Target table: function_returns (with function_return_sources populated from return_vars)

        IMPORTANT: Return dict key must be "returns" (handler name),
        NOT "function_returns" (table name). See core_storage.py:40.

        Args:
            tree: Tree-sitter tree object
            file_path: Path to the Go file
            content: File content string

        Returns:
            List of return dicts with keys matching storage handler expectations
        """
        returns: list[dict[str, Any]] = []

        def get_node_text(node: Any) -> str:
            """Extract text from a tree-sitter node."""
            if node is None:
                return ""
            return node.text.decode("utf-8", errors="ignore")

        def get_containing_function(node: Any) -> str:
            """Walk up tree to find containing function/method name."""
            current = node.parent
            while current:
                if current.type == "function_declaration":
                    name_node = current.child_by_field_name("name")
                    if name_node:
                        return get_node_text(name_node)
                elif current.type == "method_declaration":
                    for child in current.children:
                        if child.type == "field_identifier":
                            return get_node_text(child)
                current = current.parent
            return "<module>"

        def extract_return_vars(expr_node: Any) -> list[str]:
            """Extract variable names referenced in return expression.

            Filters out Go keywords/literals: nil, true, false
            """
            vars_list: list[str] = []

            def visit_expr(n: Any) -> None:
                if n.type == "identifier":
                    name = get_node_text(n)

                    if name and name not in ("nil", "true", "false"):
                        vars_list.append(name)
                elif n.type == "selector_expression":
                    text = get_node_text(n)
                    if text:
                        vars_list.append(text)
                    return
                for child in n.children:
                    visit_expr(child)

            if expr_node:
                visit_expr(expr_node)
            return list(dict.fromkeys(vars_list))

        for node in self._find_all_nodes(tree.root_node, "return_statement"):
            function_name = get_containing_function(node)
            line = node.start_point[0] + 1
            col = node.start_point[1]

            expr_list = None
            for child in node.children:
                if child.type == "expression_list" or child.type not in ("return",):
                    expr_list = child
                    break

            if expr_list:
                return_expr = get_node_text(expr_list)
                return_vars = extract_return_vars(expr_list)
            else:
                return_expr = ""
                return_vars = []

            returns.append(
                {
                    "file": file_path,
                    "line": line,
                    "col": col,
                    "function_name": function_name,
                    "return_expr": return_expr[:500] if return_expr else "",
                    "return_vars": return_vars,
                }
            )

        if returns:
            logger.debug(f"Go: extracted {len(returns)} returns from {file_path}")

        return returns
