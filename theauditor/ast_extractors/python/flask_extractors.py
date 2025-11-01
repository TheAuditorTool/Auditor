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

import ast
import logging
from typing import Any, Dict, List, Optional

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

def _get_str_constant(node: Optional[ast.AST]) -> Optional[str]:
    """Return string value for constant nodes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):
        return node.s
    return None


def _keyword_arg(call: ast.Call, name: str) -> Optional[ast.AST]:
    """Fetch keyword argument by name from AST call."""
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _get_int_constant(node: Optional[ast.AST]) -> Optional[int]:
    """Return integer value for constant nodes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Num):
        return node.n
    return None


# ============================================================================
# Flask Extractors
# ============================================================================

def extract_flask_app_factories(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return factories

    for node in ast.walk(actual_tree):
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

        for item in ast.walk(node):
            # Check for Flask() instantiation
            if isinstance(item, ast.Assign):
                if isinstance(item.value, ast.Call):
                    func_name = get_node_name(item.value.func)
                    if any(flask_id in func_name for flask_id in FLASK_APP_IDENTIFIERS):
                        creates_flask_app = True
                        # Get app variable name
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                app_var_name = target.id

            # Check for config source
            elif isinstance(item, ast.Attribute):
                if item.attr in ['from_object', 'from_pyfile', 'from_envvar', 'from_json']:
                    config_source = item.attr

            # Check for blueprint registration
            elif isinstance(item, ast.Call):
                func_name = get_node_name(item.func)
                if 'register_blueprint' in func_name:
                    registers_blueprints = True

        if creates_flask_app:
            factories.append({
                "line": node.lineno,
                "factory_name": node.name,
                "app_var_name": app_var_name,
                "config_source": config_source,
                "registers_blueprints": registers_blueprints,
            })

    return factories


def extract_flask_extensions(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return extensions

    for node in ast.walk(actual_tree):
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


def extract_flask_request_hooks(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return hooks

    for node in ast.walk(actual_tree):
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


def extract_flask_error_handlers(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return handlers

    for node in ast.walk(actual_tree):
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


def extract_flask_websocket_handlers(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return handlers

    for node in ast.walk(actual_tree):
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


def extract_flask_cli_commands(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return commands

    for node in ast.walk(actual_tree):
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


def extract_flask_cors_configs(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return configs

    for node in ast.walk(actual_tree):
        # Check for CORS() instantiation
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Call):
                func_name = get_node_name(node.value.func)
                if 'CORS' in func_name:
                    # Extract origins if specified
                    origins = None
                    resources_node = _keyword_arg(node.value, 'resources')
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

        # Check for @cross_origin decorator
        elif isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                decorator_name = get_node_name(decorator)
                if 'cross_origin' in decorator_name:
                    origins = None
                    if isinstance(decorator, ast.Call):
                        origins_node = _keyword_arg(decorator, 'origins')
                        if origins_node:
                            if isinstance(origins_node, ast.Constant) and origins_node.value == '*':
                                origins = '*'

                    configs.append({
                        "line": node.lineno,
                        "config_type": "route",
                        "origins": origins,
                        "is_permissive": origins == '*',
                    })

    return configs


def extract_flask_rate_limits(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return limits

    for node in ast.walk(actual_tree):
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


def extract_flask_cache_decorators(tree: Dict, parser_self) -> List[Dict[str, Any]]:
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
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return caches

    for node in ast.walk(actual_tree):
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
