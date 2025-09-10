"""Express.js framework-specific security analyzer using AST."""

from typing import Any, Dict, List, Optional


def find_express_issues(tree: Any, file_path: str = None, content: str = None, **kwargs) -> List[Dict[str, Any]]:
    """Find Express.js security issues using AST analysis.
    
    Args:
        tree: AST tree from parser
        file_path: Path to the file being analyzed
        content: File content
        **kwargs: Additional context
        
    Returns:
        List of security findings
    """
    findings = []
    
    if not tree or not content:
        return findings
    
    # Get AST parser if available
    ast_parser = kwargs.get('ast_parser')
    
    # Check for Express app initialization
    has_express = 'require("express")' in content or "require('express')" in content or 'from "express"' in content
    if not has_express:
        return findings  # Not an Express app
    
    # Pattern 1: Check for missing Helmet middleware
    if not _has_helmet_middleware(content):
        findings.append({
            "pattern_name": "express-missing-helmet",
            "type": "EXPRESS_MISSING_HELMET",
            "message": "Express app without Helmet security middleware - missing critical security headers",
            "file": file_path,
            "line": 1,
            "column": 0,
            "severity": "high",
            "category": "security",
            "snippet": "Missing: app.use(helmet())"
        })
    
    # Pattern 2: Check for missing error handler
    if _has_routes_without_error_handler(content):
        route_lines = _find_route_lines(content)
        for line_num in route_lines:
            findings.append({
                "pattern_name": "express-missing-error-handler",
                "type": "EXPRESS_MISSING_ERROR_HANDLER",
                "message": "Express route without error handling",
                "file": file_path,
                "line": line_num,
                "column": 0,
                "severity": "high",
                "category": "error-handling",
                "snippet": "Route handler missing try/catch"
            })
    
    # Pattern 3: Check for synchronous file operations in routes
    sync_ops = _find_sync_operations_in_routes(content)
    for line_num, operation in sync_ops:
        findings.append({
            "pattern_name": "express-sync-in-async",
            "type": "EXPRESS_SYNC_IN_ASYNC",
            "message": f"Synchronous operation {operation} blocking event loop in route",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "high",
            "category": "performance",
            "snippet": f"Replace {operation} with async version"
        })
    
    # Pattern 4: Check for direct output of user input (XSS)
    xss_risks = _find_xss_vulnerabilities(content)
    for line_num, input_source in xss_risks:
        findings.append({
            "pattern_name": "express-xss-direct-send",
            "type": "EXPRESS_XSS_DIRECT_SEND",
            "message": f"Potential XSS - {input_source} directly in response without sanitization",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "critical",
            "category": "xss",
            "snippet": f"Sanitize {input_source} before sending"
        })
    
    # Pattern 5: Check for missing rate limiting on API endpoints
    if _has_api_without_rate_limit(content):
        findings.append({
            "pattern_name": "express-missing-rate-limit",
            "type": "EXPRESS_MISSING_RATE_LIMIT",
            "message": "API endpoints without rate limiting - vulnerable to DoS/brute force",
            "file": file_path,
            "line": 1,
            "column": 0,
            "severity": "high",
            "category": "security",
            "snippet": "Add express-rate-limit middleware"
        })
    
    # Pattern 6: Check for body parser without size limit
    if _has_body_parser_without_limit(content):
        findings.append({
            "pattern_name": "express-body-parser-limit",
            "type": "EXPRESS_BODY_PARSER_LIMIT",
            "message": "Body parser without size limit - vulnerable to DoS",
            "file": file_path,
            "line": 1,
            "column": 0,
            "severity": "low",
            "category": "security",
            "snippet": "Add limit option to bodyParser"
        })
    
    # Pattern 7: Check for database queries directly in route handlers
    db_in_routes = _find_db_queries_in_routes(content)
    for line_num, query_type in db_in_routes:
        findings.append({
            "pattern_name": "express-direct-db-query",
            "type": "EXPRESS_DIRECT_DB_QUERY",
            "message": f"Database {query_type} directly in route handler - consider using service layer",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "severity": "medium",
            "category": "architecture",
            "snippet": f"Move {query_type} to service/repository layer"
        })
    
    return findings


def register_taint_patterns(taint_registry):
    """Register Express.js-specific taint patterns.
    
    Args:
        taint_registry: TaintRegistry instance from theauditor.taint.registry
    """
    # Express response methods that could lead to XSS
    EXPRESS_XSS_SINKS = [
        "res.send", "res.json", "res.jsonp", "res.render",
        "res.write", "res.end", "res.redirect",
        "res.status().send", "res.status().json"
    ]
    
    for pattern in EXPRESS_XSS_SINKS:
        taint_registry.register_sink(pattern, "xss", "javascript")
    
    # Express methods that could lead to header injection
    EXPRESS_HEADER_SINKS = [
        "res.set", "res.header", "res.setHeader",
        "res.cookie", "res.location", "res.type"
    ]
    
    for pattern in EXPRESS_HEADER_SINKS:
        taint_registry.register_sink(pattern, "header_injection", "javascript")
    
    # Express file operations that could lead to path traversal
    EXPRESS_PATH_SINKS = [
        "res.sendFile", "res.download", "res.attachment"
    ]
    
    for pattern in EXPRESS_PATH_SINKS:
        taint_registry.register_sink(pattern, "path", "javascript")


# Helper functions for pattern detection
def _has_helmet_middleware(content: str) -> bool:
    """Check if Helmet middleware is being used."""
    helmet_patterns = [
        "require('helmet')",
        'require("helmet")',
        "import helmet",
        "app.use(helmet",
        ".use(helmet()"
    ]
    return any(pattern in content for pattern in helmet_patterns)


def _has_routes_without_error_handler(content: str) -> bool:
    """Check if there are routes without try/catch."""
    import re
    # Look for route handlers
    route_pattern = r'app\.(get|post|put|delete|patch)\s*\([^)]*\([^)]*\)\s*(?:=>|function)'
    routes = re.findall(route_pattern, content)
    
    if not routes:
        return False
    
    # Check if any route lacks try/catch
    # This is simplified - a more thorough check would parse the AST
    return "try" not in content or "catch" not in content


def _find_route_lines(content: str) -> List[int]:
    """Find line numbers of route definitions."""
    import re
    lines = content.split('\n')
    route_lines = []
    
    for i, line in enumerate(lines, 1):
        if re.search(r'app\.(get|post|put|delete|patch)\s*\(', line):
            route_lines.append(i)
    
    return route_lines


def _find_sync_operations_in_routes(content: str) -> List[tuple]:
    """Find synchronous file operations in route handlers."""
    import re
    findings = []
    lines = content.split('\n')
    
    sync_ops = ['readFileSync', 'writeFileSync', 'appendFileSync', 'unlinkSync', 'mkdirSync']
    
    for i, line in enumerate(lines, 1):
        for op in sync_ops:
            if op in line and re.search(r'app\.(get|post|put|delete)', content[:content.find(line)]):
                findings.append((i, op))
    
    return findings


def _find_xss_vulnerabilities(content: str) -> List[tuple]:
    """Find potential XSS vulnerabilities."""
    import re
    findings = []
    lines = content.split('\n')
    
    # Look for direct output of user input
    xss_pattern = r'res\.(send|json|write|render)\s*\([^)]*req\.(body|query|params|cookies|headers)\.[\w\.]+'
    
    for i, line in enumerate(lines, 1):
        match = re.search(xss_pattern, line)
        if match and not any(san in line for san in ['sanitize', 'escape', 'encode', 'DOMPurify']):
            input_source = match.group(0).split('req.')[1].split(')')[0]
            findings.append((i, f"req.{input_source}"))
    
    return findings


def _has_api_without_rate_limit(content: str) -> bool:
    """Check if API endpoints lack rate limiting."""
    import re
    
    # Check for API routes
    has_api = bool(re.search(r'app\.(get|post|put|delete|patch)\s*\([\'"`]/api/', content))
    
    if not has_api:
        return False
    
    # Check for rate limiting
    rate_limit_patterns = [
        'rateLimit',
        'RateLimit',
        'express-rate-limit',
        'rate-limiter',
        'slowDown'
    ]
    
    has_rate_limit = any(pattern in content for pattern in rate_limit_patterns)
    
    return has_api and not has_rate_limit


def _has_body_parser_without_limit(content: str) -> bool:
    """Check if body parser lacks size limit."""
    import re
    
    # Look for body parser usage
    parser_pattern = r'bodyParser\.(json|urlencoded)\('
    
    if not re.search(parser_pattern, content):
        return False
    
    # Check if limit is specified
    return 'limit' not in content


def _find_db_queries_in_routes(content: str) -> List[tuple]:
    """Find database queries directly in route handlers."""
    import re
    findings = []
    lines = content.split('\n')
    
    db_operations = ['query', 'find', 'findOne', 'findById', 'insert', 'update', 'delete', 'save']
    
    # Simple heuristic: if DB operation appears shortly after route definition
    in_route = False
    route_start = 0
    
    for i, line in enumerate(lines, 1):
        # Check if entering a route
        if re.search(r'app\.(get|post|put|delete|patch)\s*\(', line):
            in_route = True
            route_start = i
        
        # Check for DB operations in route
        if in_route and i - route_start < 20:  # Within 20 lines of route start
            for op in db_operations:
                if f'.{op}(' in line or f' {op}(' in line:
                    findings.append((i, op))
        
        # Exit route context
        if in_route and ('}' in line or i - route_start > 30):
            in_route = False
    
    return findings