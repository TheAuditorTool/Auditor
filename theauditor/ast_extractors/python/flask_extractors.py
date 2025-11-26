"""Flask framework extractors.

This module contains extraction logic for Flask web framework patterns:
- Application factories (create_app pattern)
- Flask extensions (SQLAlchemy, Login, etc.)
- Request/response hooks (before_request, after_request)
- Error handlers (@app.errorhandler)
- WebSocket handlers (Flask-SocketIO)
- CLI commands (@click.command)
- CORS configurations
- Rate limiting decorators
- Caching decorators

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
"""
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
from typing import Any

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Flask Detection Constants
# ============================================================================

FLASK_APP_IDENTIFIERS = {
    "Flask",
    "flask.Flask",
}

FLASK_EXTENSIONS = {
    "SQLAlchemy",
    "LoginManager",
    "Migrate",
    "Mail",
    "Bcrypt",
    "CORS",
    "Limiter",
    "Cache",
    "SocketIO",
    "JWT",
    "Marshmallow",
    "Admin",
}

FLASK_HOOK_DECORATORS = {
    "before_request",
    "after_request",
    "before_first_request",
    "teardown_request",
    "teardown_appcontext",
}


# ============================================================================
# Helper Functions
# ============================================================================

def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if (isinstance(node, ast.Constant) and isinstance(node.value, str)):
        return node.value
    return None


def _keyword_arg(call: ast.Call, name: str) -> ast.AST | None:
    """Fetch keyword argument by name from AST call."""
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _get_int_constant(node: ast.AST | None) -> int | None:
    """Return integer value for constant nodes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))):
        return node.value
    return None


# ============================================================================
# Flask Extractors
# ============================================================================

def extract_flask_app_factories(context: FileContext) -> list[dict[str, Any]]:
    """Extract Flask application factory patterns.

    Detects:
    - create_app() functions
    - Flask() instantiations
    - app.config updates
    - Blueprint registrations

    Security relevance:
    - Factory pattern security configuration
    - Config source tracking (environment, file, hardcoded)
    - Blueprint registration = attack surface
    """
    factories = []
    if not isinstance(context.tree, ast.AST):
        return factories

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        # Look for factory pattern (usually create_app or make_app)
        if 'app' not in node.name.lower():
            continue

        # Check if function creates Flask app
        creates_flask_app = False
        app_var_name = None
        config_source = None
        registers_blueprints = False

        for item in context.find_nodes(ast.Assign):
            if isinstance(item.value, ast.Call):
                func_name = get_node_name(item.value.func)
                if any(flask_id in func_name for flask_id in FLASK_APP_IDENTIFIERS):
                    creates_flask_app = True
                    # Get app variable name
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            app_var_name = target.id

        if creates_flask_app:
            factories.append({
                "line": node.lineno,
                "factory_name": node.name,
                "app_var_name": app_var_name,
                "config_source": config_source,
                "registers_blueprints": registers_blueprints,
            })

    return factories


def extract_flask_extensions(context: FileContext) -> list[dict[str, Any]]:
    """Extract Flask extension registrations.

    Detects:
    - Extension instantiations (db = SQLAlchemy())
    - init_app() calls
    - Extension configuration

    Security relevance:
    - SQLAlchemy = SQL injection vector
    - LoginManager = auth bypass risk
    - CORS = cross-origin policy
    """
    extensions = []
    if not isinstance(context.tree, ast.AST):
        return extensions

    for node in context.walk_tree():
        if not isinstance(node, ast.Assign):
            continue

        if not isinstance(node.value, ast.Call):
            continue

        func_name = get_node_name(node.value.func)

        # Check if this is a Flask extension
        extension_type = None
        for ext in FLASK_EXTENSIONS:
            if ext in func_name:
                extension_type = ext
                break

        if not extension_type:
            continue

        # Get variable name
        var_name = None
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id

        # Check if app is passed directly
        app_passed = False
        if node.value.args:
            app_passed = True

        extensions.append({
            "line": node.lineno,
            "extension_type": extension_type,
            "var_name": var_name,
            "app_passed_to_constructor": app_passed,
        })

    return extensions


def extract_flask_request_hooks(context: FileContext) -> list[dict[str, Any]]:
    """Extract Flask request/response hooks.

    Detects:
    - @app.before_request
    - @app.after_request
    - @app.teardown_request
    - @app.before_first_request
    - @app.teardown_appcontext

    Security relevance:
    - before_request = authentication/authorization checkpoint
    - after_request = response header injection point
    - Missing auth in before_request = bypass risk
    """
    hooks = []
    if not isinstance(context.tree, ast.AST):
        return hooks

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check decorators for hook patterns
        for decorator in node.decorator_list:
            decorator_name = get_node_name(decorator)

            hook_type = None
            for hook_dec in FLASK_HOOK_DECORATORS:
                if hook_dec in decorator_name:
                    hook_type = hook_dec
                    break

            if hook_type:
                # Extract app instance name (e.g., 'app' from @app.before_request)
                app_var = None
                if isinstance(decorator, ast.Attribute):
                    if isinstance(decorator.value, ast.Name):
                        app_var = decorator.value.id

                hooks.append({
                    "line": node.lineno,
                    "hook_type": hook_type,
                    "function_name": node.name,
                    "app_var": app_var,
                })

    return hooks


def extract_flask_error_handlers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Flask error handler decorators.

    Detects:
    - @app.errorhandler(404)
    - @app.errorhandler(Exception)
    - Custom exception handlers

    Security relevance:
    - Error handlers = information disclosure risk
    - Debug info in error messages = vulnerability
    - Generic exception handlers = hiding errors
    """
    handlers = []
    if not isinstance(context.tree, ast.AST):
        return handlers

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check decorators for errorhandler pattern
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            decorator_name = get_node_name(decorator.func)
            if 'errorhandler' not in decorator_name:
                continue

            # Extract error code/exception type
            error_code = None
            exception_type = None

            if decorator.args:
                arg = decorator.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                    error_code = arg.value
                else:
                    exception_type = get_node_name(arg)

            handlers.append({
                "line": node.lineno,
                "function_name": node.name,
                "error_code": error_code,
                "exception_type": exception_type,
            })

    return handlers


def extract_flask_websocket_handlers(context: FileContext) -> list[dict[str, Any]]:
    """Extract Flask-SocketIO WebSocket handlers.

    Detects:
    - @socketio.on('event')
    - emit() calls
    - join_room/leave_room

    Security relevance:
    - WebSocket events = unvalidated input
    - emit() without auth = unauthorized broadcast
    - Room management = access control issue
    """
    handlers = []
    if not isinstance(context.tree, ast.AST):
        return handlers

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check decorators for socketio.on pattern
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            decorator_name = get_node_name(decorator.func)
            if '.on' not in decorator_name or 'socketio' not in decorator_name.lower():
                continue

            # Extract event name
            event_name = None
            if decorator.args:
                event_name = _get_str_constant(decorator.args[0])

            # Check for namespace
            namespace = None
            namespace_node = _keyword_arg(decorator, 'namespace')
            if namespace_node:
                namespace = _get_str_constant(namespace_node)

            handlers.append({
                "line": node.lineno,
                "function_name": node.name,
                "event_name": event_name,
                "namespace": namespace,
            })

    return handlers


def extract_flask_cli_commands(context: FileContext) -> list[dict[str, Any]]:
    """Extract Flask CLI commands.

    Detects:
    - @app.cli.command()
    - @click.command() with Flask context
    - click.option decorators

    Security relevance:
    - CLI commands = admin interface
    - Commands without auth = privilege escalation
    - Dangerous operations (db drop, user delete)
    """
    commands = []
    if not isinstance(context.tree, ast.AST):
        return commands

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check decorators for CLI command patterns
        is_cli_command = False
        command_name = None
        has_options = False

        for decorator in node.decorator_list:
            decorator_name = get_node_name(decorator)

            if 'cli.command' in decorator_name or 'click.command' in decorator_name:
                is_cli_command = True
                # Try to extract command name from decorator args
                if isinstance(decorator, ast.Call) and decorator.args:
                    command_name = _get_str_constant(decorator.args[0])

            if 'click.option' in decorator_name or 'click.argument' in decorator_name:
                has_options = True

        if is_cli_command:
            if not command_name:
                command_name = node.name

            commands.append({
                "line": node.lineno,
                "command_name": command_name,
                "function_name": node.name,
                "has_options": has_options,
            })

    return commands


def extract_flask_cors_configs(context: FileContext) -> list[dict[str, Any]]:
    """Extract Flask CORS configurations.

    Detects:
    - CORS() instantiation
    - @cross_origin decorator
    - CORS configuration dictionaries

    Security relevance:
    - CORS(*) = unrestricted cross-origin access
    - Missing CORS = functional issue
    - Overly permissive origins = CSRF risk
    """
    configs = []
    if not isinstance(context.tree, ast.AST):
        return configs

    for node in context.find_nodes(ast.Assign):
        if isinstance(node.value, ast.Call):
            func_name = get_node_name(node.value.func)
            if 'CORS' in func_name:
                # Extract origins if specified
                origins = None
                origins_node = _keyword_arg(node.value, 'origins')

                if origins_node:
                    if isinstance(origins_node, ast.Constant) and origins_node.value == '*':
                        origins = '*'
                    elif isinstance(origins_node, ast.List):
                        origin_list = []
                        for elt in origins_node.elts:
                            origin_str = _get_str_constant(elt)
                            if origin_str:
                                origin_list.append(origin_str)
                        origins = ','.join(origin_list)

                configs.append({
                    "line": node.lineno,
                    "config_type": "global",
                    "origins": origins,
                    "is_permissive": origins == '*',
                })

    return configs


def extract_flask_rate_limits(context: FileContext) -> list[dict[str, Any]]:
    """Extract Flask rate limiting decorators.

    Detects:
    - @limiter.limit() decorators
    - Rate limit configurations
    - Per-route vs global limits

    Security relevance:
    - Missing rate limits = DoS vulnerability
    - Overly permissive limits = abuse risk
    - Login endpoints without limits = brute force risk
    """
    limits = []
    if not isinstance(context.tree, ast.AST):
        return limits

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check decorators for limiter.limit pattern
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue

            decorator_name = get_node_name(decorator.func)
            if 'limit' not in decorator_name.lower():
                continue

            # Extract rate limit string (e.g., "100 per hour")
            limit_string = None
            if decorator.args:
                limit_string = _get_str_constant(decorator.args[0])

            limits.append({
                "line": node.lineno,
                "function_name": node.name,
                "limit_string": limit_string,
            })

    return limits


def extract_flask_cache_decorators(context: FileContext) -> list[dict[str, Any]]:
    """Extract Flask caching decorators.

    Detects:
    - @cache.cached() decorators
    - @cache.memoize() decorators
    - Cache timeout values

    Security relevance:
    - Caching user-specific data = privacy leak
    - Long cache timeouts on auth checks = stale permissions
    - Cache key collisions = data leakage
    """
    caches = []
    if not isinstance(context.tree, ast.AST):
        return caches

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check decorators for cache patterns
        for decorator in node.decorator_list:
            decorator_name = get_node_name(decorator)
            if 'cache' not in decorator_name.lower():
                continue

            cache_type = None
            timeout = None

            if 'cached' in decorator_name:
                cache_type = 'cached'
            elif 'memoize' in decorator_name:
                cache_type = 'memoize'

            if cache_type and isinstance(decorator, ast.Call):
                # Extract timeout
                timeout_node = _keyword_arg(decorator, 'timeout')
                if timeout_node:
                    timeout = _get_int_constant(timeout_node)

            if cache_type:
                caches.append({
                    "line": node.lineno,
                    "function_name": node.name,
                    "cache_type": cache_type,
                    "timeout": timeout,
                })

    return caches


# HTTP Methods for FastAPI
FASTAPI_HTTP_METHODS = frozenset(['get', 'post', 'put', 'delete', 'patch', 'options', 'head'])

# Auth decorator patterns
AUTH_DECORATORS = frozenset([
    'login_required', 'auth_required', 'permission_required',
    'require_auth', 'authenticated', 'authorize', 'requires_auth',
    'jwt_required', 'token_required', 'verify_jwt', 'check_auth'
])


def _extract_fastapi_dependencies(node: ast.FunctionDef) -> list[str]:
    """Extract FastAPI dependency injection from function signature.
    
    Args:
        node: AST FunctionDef node
        
    Returns:
        List of dependency names (e.g., ['Depends(get_current_user)'])
    """
    dependencies = []
    for arg in node.args.args:
        # Check if annotation is a Depends() call
        if arg.annotation and isinstance(arg.annotation, ast.Call):
            dep_name = get_node_name(arg.annotation.func)
            if dep_name == 'Depends' and arg.annotation.args:
                inner_dep = get_node_name(arg.annotation.args[0])
                if inner_dep:
                    dependencies.append(f"Depends({inner_dep})")
    return dependencies


def extract_flask_routes(context: FileContext) -> list[dict[str, Any]]:
    """Extract Flask/FastAPI routes using Python AST.

    Detects:
    - Flask @app.route() decorators
    - Flask @blueprint.route() decorators
    - FastAPI @app.get/post/put/delete() decorators
    - Authentication decorators
    - Dependency injection (FastAPI)

    Returns:
        List of route dictionaries with method, pattern, auth, etc.
    """
    routes = []

    # Check if we have a Python AST tree
    if not isinstance(context.tree, ast.AST):
        return routes

    # Walk the AST to find decorated functions
    for node in context.walk_tree():
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            has_auth = False
            controls: list[str] = []
            framework = None
            blueprint_name = None
            method = 'GET'
            pattern = ''
            route_found = False

            for decorator in node.decorator_list:
                dec_identifier = get_node_name(decorator)

                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                    method_name = decorator.func.attr
                    owner_name = get_node_name(decorator.func.value)

                    if method_name in ['route'] or method_name in FASTAPI_HTTP_METHODS:
                        pattern = ''
                        if decorator.args:
                            path_node = decorator.args[0]
                            if isinstance(path_node, ast.Constant):
                                pattern = str(path_node.value)

                        if method_name == 'route':
                            method = 'GET'
                            for keyword in decorator.keywords:
                                if keyword.arg == 'methods' and isinstance(keyword.value, ast.List) and keyword.value.elts:
                                    element = keyword.value.elts[0]
                                    if isinstance(element, ast.Constant):
                                        method = str(element.value).upper()
                        else:
                            method = method_name.upper()

                        framework = 'flask' if method_name == 'route' else 'fastapi'
                        blueprint_name = owner_name
                        route_found = True
                        dec_identifier = method_name

                if dec_identifier and dec_identifier in AUTH_DECORATORS:
                    has_auth = True
                elif dec_identifier and dec_identifier not in ['route'] and dec_identifier not in FASTAPI_HTTP_METHODS:
                    controls.append(dec_identifier)

            if route_found:
                dependencies = []
                if framework == 'fastapi':
                    dependencies = _extract_fastapi_dependencies(node)

                routes.append({
                    'line': node.lineno,
                    'method': method,
                    'pattern': pattern,
                    'has_auth': has_auth,
                    'handler_function': node.name,
                    'controls': controls,
                    'framework': framework or 'flask',
                    'dependencies': dependencies,
                    'blueprint': blueprint_name if framework == 'flask' else None,
                })

    return routes
