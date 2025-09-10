"""FastAPI framework-specific security analyzer using AST."""

import ast
from typing import Any, Dict, List


def find_fastapi_issues(tree: Any, file_path: str = None, content: str = None, **kwargs) -> List[Dict[str, Any]]:
    """Find FastAPI security issues using AST analysis.
    
    Args:
        tree: AST tree from parser
        file_path: Path to the file being analyzed
        content: File content
        **kwargs: Additional context
        
    Returns:
        List of security findings
    """
    findings = []
    
    if not content:
        return findings
    
    # Check if this is a FastAPI file
    is_fastapi = (
        'from fastapi' in content or
        'import fastapi' in content or
        'FastAPI()' in content or
        '@app.get' in content or
        '@app.post' in content or
        '@router.' in content
    )
    
    if not is_fastapi:
        return findings
    
    # For Python files, use native AST if available
    if isinstance(tree, ast.AST):
        python_tree = tree
    else:
        try:
            python_tree = ast.parse(content)
        except SyntaxError:
            python_tree = None
    
    # Pattern 1: Sync operations in async routes
    sync_in_async = _find_sync_in_async(content)
    for line_num, operation in sync_in_async:
        findings.append({
            "pattern_name": "fastapi-sync-in-async-route",
            "type": "FASTAPI_SYNC_IN_ASYNC",
            "message": f"Synchronous {operation} in async route - blocks event loop",
            "file": file_path,
            "line": line_num,
            "severity": "high",
            "category": "performance"
        })
    
    # Pattern 2: Missing dependency injection
    if _has_direct_db_access(content):
        findings.append({
            "pattern_name": "fastapi-missing-dependency-injection",
            "type": "FASTAPI_MISSING_DI",
            "message": "Direct database access without dependency injection",
            "file": file_path,
            "line": 1,
            "severity": "medium",
            "category": "architecture"
        })
    
    # Pattern 3: Unvalidated path parameters
    if _has_unvalidated_path_params(content):
        findings.append({
            "pattern_name": "fastapi-unvalidated-path-param",
            "type": "FASTAPI_UNVALIDATED_PATH",
            "message": "Path parameter used without type validation",
            "file": file_path,
            "line": 1,
            "severity": "medium",
            "category": "validation"
        })
    
    # Pattern 4: Missing CORS middleware
    if _has_missing_cors(content):
        findings.append({
            "pattern_name": "fastapi-missing-cors",
            "type": "FASTAPI_MISSING_CORS",
            "message": "FastAPI app without CORS middleware",
            "file": file_path,
            "line": 1,
            "severity": "low",
            "category": "security"
        })
    
    # Pattern 5: Blocking file operations
    blocking_ops = _find_blocking_file_ops(content)
    for line_num in blocking_ops:
        findings.append({
            "pattern_name": "fastapi-blocking-file-operation",
            "type": "FASTAPI_BLOCKING_FILE_OP",
            "message": "Blocking file I/O in async route - use aiofiles",
            "file": file_path,
            "line": line_num,
            "severity": "high",
            "category": "performance"
        })
    
    # Pattern 6: Raw SQL in routes
    if _has_sql_in_route(content):
        findings.append({
            "pattern_name": "fastapi-sql-in-route",
            "type": "FASTAPI_SQL_IN_ROUTE",
            "message": "Raw SQL query in route handler - use ORM or repository pattern",
            "file": file_path,
            "line": 1,
            "severity": "high",
            "category": "architecture"
        })
    
    # Pattern 7: Background tasks without exception handling
    if _has_unhandled_background_task(content):
        findings.append({
            "pattern_name": "fastapi-background-task-exception",
            "type": "FASTAPI_BACKGROUND_TASK_ERROR",
            "message": "Background task without exception handling - failures will be silent",
            "file": file_path,
            "line": 1,
            "severity": "high",
            "category": "error-handling"
        })
    
    # Pattern 8: WebSocket without auth
    if _has_websocket_no_auth(content):
        findings.append({
            "pattern_name": "fastapi-websocket-no-auth",
            "type": "FASTAPI_WEBSOCKET_NO_AUTH",
            "message": "WebSocket endpoint without authentication",
            "file": file_path,
            "line": 1,
            "severity": "critical",
            "category": "security"
        })
    
    # Pattern 9: Missing request validation
    if _has_missing_validation(content):
        findings.append({
            "pattern_name": "fastapi-missing-request-validation",
            "type": "FASTAPI_MISSING_VALIDATION",
            "message": "Endpoint without Pydantic model validation",
            "file": file_path,
            "line": 1,
            "severity": "high",
            "category": "validation"
        })
    
    # Pattern 10: Exposed debug endpoints
    debug_endpoints = _find_debug_endpoints(content)
    for line_num, endpoint in debug_endpoints:
        findings.append({
            "pattern_name": "fastapi-exposed-debug-endpoint",
            "type": "FASTAPI_DEBUG_ENDPOINT",
            "message": f"Debug endpoint '{endpoint}' exposed",
            "file": file_path,
            "line": line_num,
            "severity": "high",
            "category": "security"
        })
    
    # Pattern 11: Form data injection
    if _has_form_data_injection(content):
        findings.append({
            "pattern_name": "fastapi-form-data-injection",
            "type": "FASTAPI_FORM_INJECTION",
            "message": "Form data used in file operations - path traversal risk",
            "file": file_path,
            "line": 1,
            "severity": "critical",
            "category": "injection"
        })
    
    # Pattern 12: Middleware order issue
    if _has_middleware_order_issue(content):
        findings.append({
            "pattern_name": "fastapi-middleware-order-issue",
            "type": "FASTAPI_MIDDLEWARE_ORDER",
            "message": "Security middleware added after routes - won't protect existing routes",
            "file": file_path,
            "line": 1,
            "severity": "high",
            "category": "security"
        })
    
    return findings


def register_taint_patterns(taint_registry):
    """Register FastAPI-specific taint patterns."""
    
    # FastAPI response sinks
    FASTAPI_SINKS = [
        "JSONResponse",
        "HTMLResponse",
        "PlainTextResponse",
        "StreamingResponse",
        "FileResponse",
        "RedirectResponse"
    ]
    
    for pattern in FASTAPI_SINKS:
        taint_registry.register_sink(pattern, "response", "python")
    
    # FastAPI input sources
    FASTAPI_SOURCES = [
        "Request",
        "Body(",
        "Query(",
        "Path(",
        "Form(",
        "File(",
        "Header(",
        "Cookie(",
        "Depends("
    ]
    
    for pattern in FASTAPI_SOURCES:
        taint_registry.register_source(pattern, "user_input", "python")


# Helper functions
def _find_sync_in_async(content: str) -> List[tuple]:
    """Find synchronous operations in async functions."""
    import re
    findings = []
    lines = content.split('\n')
    
    sync_operations = ['time.sleep', 'requests.', 'urllib.', 'open(', 'input(']
    
    # Track if we're in an async function
    in_async = False
    async_start = 0
    
    for i, line in enumerate(lines, 1):
        if 'async def' in line:
            in_async = True
            async_start = i
        
        if in_async:
            for op in sync_operations:
                if op in line and 'await' not in line:
                    findings.append((i, op))
        
        # Exit async context
        if in_async and i > async_start + 1 and line and not line.startswith((' ', '\t')):
            in_async = False
    
    return findings


def _has_direct_db_access(content: str) -> bool:
    """Check for direct database access without dependency injection."""
    import re
    # Look for route with direct db access
    route_pattern = r'@(?:app|router)\.(?:get|post|put|delete)'
    db_pattern = r'(?:db\.|session\.|conn\.)'
    
    if re.search(route_pattern, content) and re.search(db_pattern, content):
        return 'Depends' not in content
    return False


def _has_unvalidated_path_params(content: str) -> bool:
    """Check for unvalidated path parameters."""
    import re
    # Look for path params without type hints
    pattern = r'\{(\w+)\}.*?def\s+\w+\([^)]*\1(?:\s*,|\s*\))'
    return bool(re.search(pattern, content))


def _has_missing_cors(content: str) -> bool:
    """Check if CORS middleware is missing."""
    if 'FastAPI()' in content:
        return 'CORSMiddleware' not in content
    return False


def _find_blocking_file_ops(content: str) -> List[int]:
    """Find blocking file operations in async functions."""
    findings = []
    lines = content.split('\n')
    
    in_async = False
    for i, line in enumerate(lines, 1):
        if 'async def' in line:
            in_async = True
        
        if in_async and 'open(' in line and 'aiofiles' not in content:
            findings.append(i)
        
        if in_async and line and not line.startswith((' ', '\t')):
            in_async = False
    
    return findings


def _has_sql_in_route(content: str) -> bool:
    """Check for raw SQL in route handlers."""
    import re
    sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE']
    route_pattern = r'@(?:app|router)\.(?:get|post|put|delete)'
    
    if re.search(route_pattern, content):
        for keyword in sql_keywords:
            if keyword + ' ' in content.upper():
                return True
    return False


def _has_unhandled_background_task(content: str) -> bool:
    """Check for background tasks without exception handling."""
    if 'BackgroundTasks' in content and '.add_task(' in content:
        return 'try' not in content or 'except' not in content
    return False


def _has_websocket_no_auth(content: str) -> bool:
    """Check for WebSocket endpoints without authentication."""
    import re
    if re.search(r'@(?:app|router)\.websocket', content):
        auth_patterns = ['token', 'auth', 'verify', 'check_permission', 'current_user', 'get_current']
        return not any(pattern in content.lower() for pattern in auth_patterns)
    return False


def _has_missing_validation(content: str) -> bool:
    """Check for endpoints without Pydantic validation."""
    import re
    # Look for functions with dict/Any parameters
    pattern = r'async\s+def\s+\w+\([^)]*(?:dict|Dict\[|Any)'
    if re.search(pattern, content):
        return 'BaseModel' not in content and 'Pydantic' not in content
    return False


def _find_debug_endpoints(content: str) -> List[tuple]:
    """Find exposed debug endpoints."""
    import re
    findings = []
    lines = content.split('\n')
    
    debug_paths = ['/debug', '/test', '/health/full', '/metrics/internal', '/_debug', '/_test']
    
    for i, line in enumerate(lines, 1):
        for path in debug_paths:
            if f'"{path}"' in line or f"'{path}'" in line:
                if '@app.' in line or '@router.' in line:
                    findings.append((i, path))
    
    return findings


def _has_form_data_injection(content: str) -> bool:
    """Check for form data used in file operations."""
    if 'Form()' in content:
        return any(op in content for op in ['open(', 'Path(', 'os.path', 'pathlib'])
    return False


def _has_middleware_order_issue(content: str) -> bool:
    """Check for middleware added after routes."""
    if 'app.include_router' in content and 'app.add_middleware' in content:
        # Simple check: middleware should come before routers
        router_pos = content.find('app.include_router')
        middleware_pos = content.find('app.add_middleware')
        return middleware_pos > router_pos
    return False