"""AST-based rate limiting misconfiguration detector.

This module provides high-fidelity detection of dangerous rate limiting configurations
by analyzing the AST structure to understand middleware ordering, route protection,
key generation strategies, and storage configurations.
"""

import re
import ast
from typing import Any, List, Dict


def find_rate_limit_issues(tree: Any, file_path: str) -> List[Dict[str, Any]]:
    """
    Detect common rate limiting misconfigurations using AST analysis.
    
    This is a file-based AST rule designed to be called by universal_detector
    for each JavaScript/TypeScript/Python file. It detects:
    
    - Inefficient middleware order (expensive operations before rate limiting)
    - Missing rate limiting on critical endpoints (/login, /register, /reset-password)
    - Bypassable key generation (single header like X-Forwarded-For)
    - Non-persistent storage (in-memory store in distributed environment)
    
    Args:
        tree: AST tree from ast_parser (Tree-sitter, semantic, or Python AST)
        file_path: Path to the file being analyzed
        
    Returns:
        List of security findings in normalized format
    """
    findings = []
    
    if not tree:
        return findings
    
    # Determine file type from extension
    file_ext = file_path.lower().split('.')[-1] if '.' in file_path else ''
    is_javascript = file_ext in ['js', 'jsx', 'ts', 'tsx']
    is_python = file_ext in ['py']
    
    # Handle different AST types
    if isinstance(tree, dict):
        tree_type = tree.get("type")
        
        # Handle Tree-sitter AST for JavaScript/TypeScript
        if tree_type == "tree_sitter" and is_javascript:
            actual_tree = tree.get("tree")
            if actual_tree and hasattr(actual_tree, 'root_node'):
                # Read file content for context
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        lines = content.split('\n')
                except:
                    lines = []
                
                # Analyze Tree-sitter AST for Node.js patterns
                _analyze_tree_sitter_node(actual_tree.root_node, findings, file_path, lines)
        
        # Handle Python AST
        elif tree_type == "python_ast" and is_python:
            actual_tree = tree.get("tree")
            if actual_tree:
                # Analyze Python AST for Flask/Django patterns
                _analyze_python_ast(actual_tree, findings, file_path)
    
    # Direct Python AST (backward compatibility)
    elif isinstance(tree, ast.AST) and is_python:
        _analyze_python_ast(tree, findings, file_path)
    
    # Fallback to pattern-based detection if no AST available
    if not findings and (is_javascript or is_python):
        _analyze_with_patterns(file_path, findings, is_javascript, is_python)
    
    return findings


def _analyze_tree_sitter_node(node, findings, file_path, lines, depth=0):
    """Recursively analyze Tree-sitter AST nodes for rate limiting issues in JavaScript/TypeScript."""
    
    # Prevent infinite recursion
    if depth > 100:
        return
    
    # Track middleware registration order
    middleware_stack = []
    rate_limiter_position = -1
    auth_middleware_position = -1
    expensive_middleware_positions = []
    
    # Common rate limiting library patterns
    rate_limit_patterns = [
        'express-rate-limit', 'rateLimit', 'RateLimit', 'rate-limit',
        'express-slow-down', 'slowDown', 'SlowDown',
        'express-brute', 'ExpressBrute', 'brute',
        'rate-limiter-flexible', 'RateLimiterMemory', 'RateLimiterRedis'
    ]
    
    # Authentication middleware patterns
    auth_patterns = [
        'authenticate', 'auth', 'requireAuth', 'isAuthenticated',
        'passport.authenticate', 'jwt.verify', 'verifyToken',
        'ensureAuthenticated', 'requireLogin', 'checkAuth'
    ]
    
    # Expensive operation patterns
    expensive_patterns = [
        'database', 'query', 'findOne', 'findAll', 'select',
        'bcrypt', 'hash', 'compare', 'crypto', 'encrypt',
        'sendEmail', 'sendMail', 'mailer', 'fetch', 'axios'
    ]
    
    # Critical endpoints that must have rate limiting
    critical_endpoints = [
        '/login', '/signin', '/auth',
        '/register', '/signup', '/create-account',
        '/reset-password', '/forgot-password', '/password-reset',
        '/verify', '/confirm', '/validate',
        '/api/auth', '/api/login', '/api/register'
    ]
    
    # Check for middleware registration patterns
    if node.type == "call_expression":
        func_node = node.child_by_field_name('function')
        args_node = node.child_by_field_name('arguments')
        
        if func_node:
            func_text = func_node.text.decode('utf-8', errors='ignore')
            
            # Detection 1: Middleware ordering analysis
            if 'app.use' in func_text or 'router.use' in func_text:
                if args_node:
                    args_text = args_node.text.decode('utf-8', errors='ignore')
                    
                    # Track position of different middleware types
                    position = node.start_point[0]
                    
                    # Check if this is rate limiting middleware
                    if any(pattern in args_text for pattern in rate_limit_patterns):
                        rate_limiter_position = position
                        
                        # Check configuration for storage type
                        if 'MemoryStore' in args_text or 'memory' in args_text.lower():
                            # Detection 4: Non-persistent storage
                            line_num = node.start_point[0] + 1
                            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else args_text[:200]
                            findings.append({
                                'pattern_name': 'RATE_LIMIT_MEMORY_STORE',
                                'message': 'Rate limiter using in-memory storage - ineffective in distributed/serverless environment',
                                'file': file_path,
                                'line': line_num,
                                'column': node.start_point[1],
                                'severity': 'high',
                                'snippet': snippet,
                                'category': 'security',
                                'details': {
                                    'vulnerability': 'Memory store resets on restart and is not shared across instances',
                                    'fix': 'Use Redis, MongoDB, or other persistent storage for rate limiting'
                                }
                            })
                        
                        # Check for bypassable key generation
                        if 'keyGenerator' in args_text or 'key:' in args_text:
                            # Detection 3: Single header key generation
                            if ('x-forwarded-for' in args_text.lower() or 
                                'x-real-ip' in args_text.lower() or
                                'cf-connecting-ip' in args_text.lower()):
                                # Check if it's the only source (no fallback)
                                if 'req.ip' not in args_text and '||' not in args_text:
                                    line_num = node.start_point[0] + 1
                                    snippet = lines[line_num - 1].strip() if line_num <= len(lines) else args_text[:200]
                                    findings.append({
                                        'pattern_name': 'RATE_LIMIT_BYPASSABLE_KEY',
                                        'message': 'Rate limiter relies on spoofable header for key generation',
                                        'file': file_path,
                                        'line': line_num,
                                        'column': node.start_point[1],
                                        'severity': 'critical',
                                        'snippet': snippet,
                                        'category': 'security',
                                        'details': {
                                            'vulnerability': 'Attacker can bypass rate limiting by spoofing header values',
                                            'fix': 'Use multiple sources with fallback: req.headers["x-forwarded-for"] || req.ip'
                                        }
                                    })
                    
                    # Check if this is authentication middleware
                    elif any(pattern in args_text for pattern in auth_patterns):
                        auth_middleware_position = position
                    
                    # Check if this is expensive middleware
                    elif any(pattern in args_text for pattern in expensive_patterns):
                        expensive_middleware_positions.append(position)
            
            # Detection 2: Missing rate limiting on critical endpoints
            elif any(method in func_text for method in ['app.post', 'app.get', 'router.post', 'router.get']):
                if args_node:
                    # Extract route pattern
                    route_text = ""
                    for child in args_node.children:
                        if child.type == "string":
                            route_text = child.text.decode('utf-8', errors='ignore').strip('"\'`')
                            break
                    
                    # Check if this is a critical endpoint
                    if any(endpoint in route_text.lower() for endpoint in critical_endpoints):
                        # Check if rate limiting is applied to this route
                        parent_context = _get_parent_context(node, lines, 20)
                        has_rate_limit = any(pattern in parent_context for pattern in rate_limit_patterns)
                        
                        if not has_rate_limit:
                            line_num = node.start_point[0] + 1
                            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else func_text[:200]
                            findings.append({
                                'pattern_name': 'RATE_LIMIT_MISSING_CRITICAL',
                                'message': f'Critical endpoint {route_text} lacks rate limiting protection',
                                'file': file_path,
                                'line': line_num,
                                'column': node.start_point[1],
                                'severity': 'critical',
                                'snippet': snippet,
                                'category': 'security',
                                'details': {
                                    'endpoint': route_text,
                                    'vulnerability': 'Endpoint vulnerable to brute force attacks',
                                    'fix': 'Apply rate limiting middleware to authentication endpoints'
                                }
                            })
    
    # After processing all middleware, check ordering
    if rate_limiter_position > 0:
        # Detection 1: Check if auth middleware comes before rate limiter
        if auth_middleware_position > 0 and auth_middleware_position < rate_limiter_position:
            findings.append({
                'pattern_name': 'RATE_LIMIT_AFTER_AUTH',
                'message': 'Authentication middleware runs before rate limiting - expensive operation not protected',
                'file': file_path,
                'line': auth_middleware_position + 1,
                'column': 0,
                'severity': 'high',
                'snippet': 'Auth middleware registered before rate limiter',
                'category': 'security',
                'details': {
                    'vulnerability': 'Authentication logic (DB queries, bcrypt) runs before rate limiting',
                    'fix': 'Register rate limiting middleware before authentication middleware'
                }
            })
        
        # Check if any expensive middleware comes before rate limiter
        for exp_pos in expensive_middleware_positions:
            if exp_pos < rate_limiter_position:
                findings.append({
                    'pattern_name': 'RATE_LIMIT_AFTER_EXPENSIVE',
                    'message': 'Expensive operation (DB/crypto) runs before rate limiting',
                    'file': file_path,
                    'line': exp_pos + 1,
                    'column': 0,
                    'severity': 'high',
                    'snippet': 'Expensive middleware before rate limiter',
                    'category': 'security',
                    'details': {
                        'vulnerability': 'Resource-intensive operations not protected by rate limiting',
                        'fix': 'Move rate limiting middleware earlier in the middleware stack'
                    }
                })
    
    # Recursively analyze children
    for child in node.children:
        _analyze_tree_sitter_node(child, findings, file_path, lines, depth + 1)


def _analyze_python_ast(tree: ast.AST, findings: List[Dict[str, Any]], file_path: str):
    """Analyze Python AST for Flask/Django rate limiting patterns."""
    
    # Read file for snippets
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.read().split('\n')
    except:
        lines = []
    
    # Track decorator order and rate limiting presence
    has_rate_limit = False
    auth_before_rate_limit = False
    critical_endpoints = []
    
    for node in ast.walk(tree):
        # Check for Flask-Limiter or Django-ratelimit decorators
        if isinstance(node, ast.FunctionDef):
            decorators = []
            for decorator in node.decorator_list:
                decorator_name = ""
                if isinstance(decorator, ast.Name):
                    decorator_name = decorator.id
                elif isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Name):
                        decorator_name = decorator.func.id
                    elif isinstance(decorator.func, ast.Attribute):
                        decorator_name = decorator.func.attr
                
                decorators.append(decorator_name.lower())
            
            # Check decorator order
            rate_limit_index = -1
            auth_index = -1
            
            for i, dec in enumerate(decorators):
                if 'limit' in dec or 'ratelimit' in dec or 'throttle' in dec:
                    rate_limit_index = i
                    has_rate_limit = True
                elif 'login_required' in dec or 'auth' in dec or 'authenticated' in dec:
                    auth_index = i
            
            # Detection 1: Auth decorator before rate limit
            if rate_limit_index >= 0 and auth_index >= 0 and auth_index < rate_limit_index:
                line_num = getattr(node, 'lineno', 0)
                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else node.name
                findings.append({
                    'pattern_name': 'RATE_LIMIT_AFTER_AUTH',
                    'message': f'Authentication decorator runs before rate limiting in {node.name}',
                    'file': file_path,
                    'line': line_num,
                    'column': getattr(node, 'col_offset', 0),
                    'severity': 'high',
                    'snippet': snippet,
                    'category': 'security',
                    'details': {
                        'function': node.name,
                        'vulnerability': 'Authentication logic runs before rate limiting check',
                        'fix': 'Place rate limiting decorator before authentication decorator'
                    }
                })
            
            # Check if this is a critical endpoint without rate limiting
            func_name = node.name.lower()
            critical_names = ['login', 'signin', 'register', 'signup', 'reset_password', 
                            'forgot_password', 'verify', 'authenticate']
            
            if any(crit in func_name for crit in critical_names):
                if rate_limit_index < 0:  # No rate limiting
                    line_num = getattr(node, 'lineno', 0)
                    snippet = lines[line_num - 1].strip() if line_num <= len(lines) else node.name
                    findings.append({
                        'pattern_name': 'RATE_LIMIT_MISSING_CRITICAL',
                        'message': f'Critical endpoint {node.name} lacks rate limiting protection',
                        'file': file_path,
                        'line': line_num,
                        'column': getattr(node, 'col_offset', 0),
                        'severity': 'critical',
                        'snippet': snippet,
                        'category': 'security',
                        'details': {
                            'function': node.name,
                            'vulnerability': 'Authentication endpoint vulnerable to brute force',
                            'fix': 'Add rate limiting decorator (e.g., @limiter.limit("5/minute"))'
                        }
                    })
        
        # Check Flask-Limiter configuration
        elif isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            
            if func_name == 'Limiter':
                # Check configuration arguments
                config = {}
                for keyword in node.keywords:
                    if keyword.arg == 'storage_uri':
                        if isinstance(keyword.value, ast.Constant):
                            storage = keyword.value.value
                            # Detection 4: Memory storage
                            if not storage or 'memory' in str(storage).lower():
                                line_num = getattr(node, 'lineno', 0)
                                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else 'Limiter config'
                                findings.append({
                                    'pattern_name': 'RATE_LIMIT_MEMORY_STORE',
                                    'message': 'Flask-Limiter using in-memory storage - ineffective in production',
                                    'file': file_path,
                                    'line': line_num,
                                    'column': getattr(node, 'col_offset', 0),
                                    'severity': 'high',
                                    'snippet': snippet,
                                    'category': 'security',
                                    'details': {
                                        'vulnerability': 'Memory storage not shared across workers/processes',
                                        'fix': 'Use Redis backend: storage_uri="redis://localhost:6379"'
                                    }
                                })
                    
                    elif keyword.arg == 'key_func':
                        # Detection 3: Check for weak key generation
                        # This would need more complex analysis of the function
                        pass


def _get_parent_context(node, lines, context_lines=10) -> str:
    """Get surrounding context lines for better analysis."""
    line_num = node.start_point[0]
    start = max(0, line_num - context_lines)
    end = min(len(lines), line_num + context_lines + 1)
    return '\n'.join(lines[start:end])


def _analyze_with_patterns(file_path: str, findings: List[Dict[str, Any]], is_javascript: bool, is_python: bool):
    """Fallback pattern-based detection when AST is not available."""
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
    except:
        return
    
    if is_javascript:
        # Pattern 1: Express rate limiter after auth middleware
        auth_middleware_line = -1
        rate_limit_line = -1
        
        for i, line in enumerate(lines, 1):
            # Track auth middleware registration
            if re.search(r'app\.use\([^)]*(?:auth|authenticate|passport\.authenticate)', line, re.IGNORECASE):
                auth_middleware_line = i
            # Track rate limit middleware
            elif re.search(r'app\.use\([^)]*(?:rateLimit|rate-limit|limiter)', line, re.IGNORECASE):
                rate_limit_line = i
        
        if auth_middleware_line > 0 and rate_limit_line > auth_middleware_line:
            findings.append({
                'pattern_name': 'RATE_LIMIT_AFTER_AUTH',
                'message': 'Rate limiting registered after authentication (regex fallback)',
                'file': file_path,
                'line': rate_limit_line,
                'column': 0,
                'severity': 'high',
                'snippet': lines[rate_limit_line - 1].strip() if rate_limit_line <= len(lines) else '',
                'category': 'security'
            })
        
        # Pattern 2: Critical endpoints without rate limiting
        critical_route_pattern = re.compile(
            r'(app|router)\.(post|get|put)\s*\(["\'](/api)?/(login|signin|register|signup|password|reset)',
            re.IGNORECASE
        )
        
        for match in critical_route_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            # Check if rate limiting is nearby (within 10 lines)
            context_start = max(0, line_num - 10)
            context_end = min(len(lines), line_num + 10)
            context = '\n'.join(lines[context_start:context_end])
            
            if not re.search(r'rate.*limit|limiter|throttle', context, re.IGNORECASE):
                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
                findings.append({
                    'pattern_name': 'RATE_LIMIT_MISSING_CRITICAL',
                    'message': 'Critical endpoint without rate limiting (regex fallback)',
                    'file': file_path,
                    'line': line_num,
                    'column': 0,
                    'severity': 'critical',
                    'snippet': snippet,
                    'category': 'security'
                })
        
        # Pattern 3: Bypassable key generation
        pattern_weak_key = re.compile(
            r'keyGenerator[^}]*headers\[["\']x-forwarded-for["\'](?![^}]*\|\|)',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in pattern_weak_key.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
            findings.append({
                'pattern_name': 'RATE_LIMIT_BYPASSABLE_KEY',
                'message': 'Rate limiter uses single spoofable header (regex fallback)',
                'file': file_path,
                'line': line_num,
                'column': 0,
                'severity': 'critical',
                'snippet': snippet,
                'category': 'security'
            })
        
        # Pattern 4: Memory store
        pattern_memory = re.compile(
            r'(MemoryStore|store\s*:\s*new\s+Memory|store\s*:\s*["\']memory)',
            re.IGNORECASE
        )
        
        for match in pattern_memory.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
            findings.append({
                'pattern_name': 'RATE_LIMIT_MEMORY_STORE',
                'message': 'Rate limiter using memory storage (regex fallback)',
                'file': file_path,
                'line': line_num,
                'column': 0,
                'severity': 'high',
                'snippet': snippet,
                'category': 'security'
            })
    
    elif is_python:
        # Pattern 1: Flask critical endpoints without rate limiting
        pattern_flask_endpoint = re.compile(
            r'@app\.route\(["\'].*/(login|register|reset|password|auth)',
            re.IGNORECASE
        )
        
        for match in pattern_flask_endpoint.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            # Check next 5 lines for rate limiting decorator
            context_end = min(len(lines), line_num + 5)
            context = '\n'.join(lines[line_num - 1:context_end])
            
            if not re.search(r'@.*limit|@.*throttle|@.*ratelimit', context, re.IGNORECASE):
                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
                findings.append({
                    'pattern_name': 'RATE_LIMIT_MISSING_CRITICAL',
                    'message': 'Flask endpoint without rate limiting (regex fallback)',
                    'file': file_path,
                    'line': line_num,
                    'column': 0,
                    'severity': 'critical',
                    'snippet': snippet,
                    'category': 'security'
                })
        
        # Pattern 2: Flask-Limiter with default memory storage
        pattern_limiter_memory = re.compile(
            r'Limiter\([^)]*\)',
            re.IGNORECASE
        )
        
        for match in pattern_limiter_memory.finditer(content):
            config_text = match.group(0)
            if 'storage_uri' not in config_text or 'memory' in config_text.lower():
                line_num = content[:match.start()].count('\n') + 1
                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
                findings.append({
                    'pattern_name': 'RATE_LIMIT_MEMORY_STORE',
                    'message': 'Flask-Limiter using default memory storage (regex fallback)',
                    'file': file_path,
                    'line': line_num,
                    'column': 0,
                    'severity': 'high',
                    'snippet': snippet,
                    'category': 'security'
                })