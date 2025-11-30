"""Go file extractor."""

from pathlib import Path
from typing import Any

from ...utils.logger import setup_logger
from . import BaseExtractor

logger = setup_logger(__name__)


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
                "Tree-sitter Go parser unavailable for %s. Run 'aud setup-ai' to install language support.",
                file_path,
            )
            return {}

        from ...ast_extractors import go_impl

        ts_tree = tree["tree"]

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

        result = {
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
        logger.debug(
            f"Extracted Go: {file_path} -> "
            f"{len(functions)} funcs, {len(structs)} structs, "
            f"{len(goroutines)} goroutines, {len(captured_vars)} captured vars "
            f"({loop_var_captures} loop vars), {total_items} total items"
        )

        return result

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
