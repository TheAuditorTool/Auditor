"""AST-based CORS misconfiguration detector.

This module provides high-fidelity detection of dangerous CORS configurations
by analyzing the AST structure of CORS middleware configurations and response headers.
"""

import re
import ast
from typing import Any, List, Dict


def find_cors_issues(tree: Any, file_path: str) -> List[Dict[str, Any]]:
    """
    Detect common CORS misconfigurations using AST analysis.
    
    This is a file-based AST rule designed to be called by universal_detector
    for each JavaScript/TypeScript/Python file. It detects:
    
    - Wildcard origin with credentials enabled
    - Dynamic origin reflection without validation
    - Null origin allowed
    - Manual OPTIONS handling (pre-flight bypass)
    
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
                # Analyze Python AST for Flask-CORS patterns
                _analyze_python_ast(actual_tree, findings, file_path)
    
    # Direct Python AST (backward compatibility)
    elif isinstance(tree, ast.AST) and is_python:
        _analyze_python_ast(tree, findings, file_path)
    
    # Fallback to pattern-based detection if no AST available
    if not findings and (is_javascript or is_python):
        _analyze_with_patterns(file_path, findings, is_javascript, is_python)
    
    return findings


def _analyze_tree_sitter_node(node, findings, file_path, lines, depth=0):
    """Recursively analyze Tree-sitter AST nodes for CORS issues in JavaScript/TypeScript."""
    
    # Prevent infinite recursion
    if depth > 100:
        return
    
    # Check for call expressions
    if node.type == "call_expression":
        func_node = node.child_by_field_name('function')
        if func_node:
            func_text = func_node.text.decode('utf-8', errors='ignore')
            
            # Check for CORS middleware configuration
            if 'cors' in func_text.lower():
                args_node = node.child_by_field_name('arguments')
                if args_node:
                    config = _extract_object_properties(args_node)
                    line_num = node.start_point[0] + 1
                    
                    # Detection 1: Wildcard origin with credentials
                    if config.get('origin') == '*' and config.get('credentials') == 'true':
                        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else func_text[:200]
                        findings.append({
                            'pattern_name': 'CORS_WILDCARD_WITH_CREDENTIALS',
                            'message': 'CORS wildcard origin (*) with credentials enabled - allows any site to read authenticated data',
                            'file': file_path,
                            'line': line_num,
                            'column': node.start_point[1],
                            'severity': 'critical',
                            'snippet': snippet,
                            'category': 'security',
                            'details': {
                                'vulnerability': 'Any website can read authenticated user data',
                                'fix': 'Use specific origins whitelist instead of wildcard when credentials are enabled'
                            }
                        })
                    
                    # Detection 3: Null origin allowed
                    origin_value = config.get('origin', '')
                    if 'null' in str(origin_value).lower():
                        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else func_text[:200]
                        findings.append({
                            'pattern_name': 'CORS_NULL_ORIGIN_ALLOWED',
                            'message': 'CORS configuration allows "null" origin - enables sandbox iframe attacks',
                            'file': file_path,
                            'line': line_num,
                            'column': node.start_point[1],
                            'severity': 'high',
                            'snippet': snippet,
                            'category': 'security',
                            'details': {
                                'vulnerability': 'Sandboxed iframes can bypass origin restrictions',
                                'fix': 'Never allow "null" origin in production'
                            }
                        })
            
            # Check for response header manipulation
            elif 'setHeader' in func_text or 'header' in func_text or 'set' in func_text:
                args_node = node.child_by_field_name('arguments')
                if args_node:
                    args_text = args_node.text.decode('utf-8', errors='ignore')
                    
                    # Detection 2: Dynamic origin reflection
                    if 'Access-Control-Allow-Origin' in args_text:
                        # Check if origin is being reflected from request
                        parent_context = _get_parent_context(node, lines, 5)
                        if any(pattern in parent_context for pattern in ['req.headers.origin', 'req.header(\'origin\')', 'request.headers.origin', 'request.headers[\'origin\']']):
                            # Check if there's validation
                            if not any(validation in parent_context for validation in ['whitelist', 'allowedOrigins', 'includes(', 'indexOf(', 'match(', 'test(']):
                                line_num = node.start_point[0] + 1
                                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else args_text[:200]
                                findings.append({
                                    'pattern_name': 'CORS_REFLECTED_ORIGIN',
                                    'message': 'Origin header reflected without validation - enables targeted CORS bypass',
                                    'file': file_path,
                                    'line': line_num,
                                    'column': node.start_point[1],
                                    'severity': 'critical',
                                    'snippet': snippet,
                                    'category': 'security',
                                    'details': {
                                        'vulnerability': 'Attacker can make their malicious site an allowed origin',
                                        'fix': 'Validate origin against a strict whitelist before reflecting'
                                    }
                                })
            
            # Detection 4: Manual OPTIONS handling (pre-flight bypass)
            elif any(method in func_text for method in ['.options(', 'app.options', 'router.options', 'route(\'OPTIONS\'']):
                line_num = node.start_point[0] + 1
                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else func_text[:200]
                
                # Check if it's setting CORS headers manually
                parent_context = _get_parent_context(node, lines, 10)
                if 'Access-Control' in parent_context:
                    findings.append({
                        'pattern_name': 'CORS_MANUAL_PREFLIGHT',
                        'message': 'Manual OPTIONS handling detected - may bypass CORS middleware security',
                        'file': file_path,
                        'line': line_num,
                        'column': node.start_point[1],
                        'severity': 'medium',
                        'snippet': snippet,
                        'category': 'security',
                        'details': {
                            'risk': 'Manual pre-flight handling can introduce inconsistencies with middleware',
                            'fix': 'Use CORS middleware for all CORS handling instead of manual OPTIONS routes'
                        }
                    })
    
    # Check for assignment expressions (for configuration objects)
    elif node.type == "assignment_expression":
        left_node = node.child_by_field_name('left')
        right_node = node.child_by_field_name('right')
        
        if left_node and right_node:
            var_name = left_node.text.decode('utf-8', errors='ignore')
            if 'cors' in var_name.lower() and right_node.type == "object":
                config = _extract_object_properties(right_node)
                line_num = node.start_point[0] + 1
                
                # Apply same checks as for cors() function calls
                if config.get('origin') == '*' and config.get('credentials') == 'true':
                    snippet = lines[line_num - 1].strip() if line_num <= len(lines) else var_name[:200]
                    findings.append({
                        'pattern_name': 'CORS_WILDCARD_WITH_CREDENTIALS',
                        'message': 'CORS configuration with wildcard and credentials in object',
                        'file': file_path,
                        'line': line_num,
                        'column': node.start_point[1],
                        'severity': 'critical',
                        'snippet': snippet,
                        'category': 'security'
                    })
    
    # Recursively analyze children
    for child in node.children:
        _analyze_tree_sitter_node(child, findings, file_path, lines, depth + 1)


def _analyze_python_ast(tree: ast.AST, findings: List[Dict[str, Any]], file_path: str):
    """Analyze Python AST for Flask-CORS and similar patterns."""
    
    # Read file for snippets
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.read().split('\n')
    except:
        lines = []
    
    for node in ast.walk(tree):
        # Check for CORS() initialization or cors_init_app calls
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            
            if 'CORS' in func_name or 'cors' in func_name.lower():
                # Extract keyword arguments
                config = {}
                for keyword in node.keywords:
                    key = keyword.arg
                    value = None
                    
                    if isinstance(keyword.value, ast.Constant):
                        value = keyword.value.value
                    elif isinstance(keyword.value, (ast.Str, ast.Num)):
                        value = keyword.value.s if hasattr(keyword.value, 's') else keyword.value.n
                    elif isinstance(keyword.value, ast.NameConstant):
                        value = keyword.value.value
                    elif isinstance(keyword.value, ast.Name):
                        value = keyword.value.id
                    
                    if key and value is not None:
                        config[key] = str(value)
                
                line_num = getattr(node, 'lineno', 0)
                
                # Detection 1: Wildcard with credentials (Flask-CORS style)
                if (config.get('origins') == '*' or config.get('resources') == '*') and config.get('supports_credentials') == 'True':
                    snippet = lines[line_num - 1].strip() if line_num <= len(lines) else str(node)[:200]
                    findings.append({
                        'pattern_name': 'CORS_WILDCARD_WITH_CREDENTIALS',
                        'message': 'Flask-CORS wildcard origin with credentials enabled',
                        'file': file_path,
                        'line': line_num,
                        'column': getattr(node, 'col_offset', 0),
                        'severity': 'critical',
                        'snippet': snippet,
                        'category': 'security',
                        'details': {
                            'vulnerability': 'Any website can read authenticated user data',
                            'fix': 'Use specific origins list instead of wildcard when supports_credentials=True'
                        }
                    })
                
                # Detection 3: Null origin in Flask-CORS
                origins_value = config.get('origins', '')
                if 'null' in origins_value.lower():
                    snippet = lines[line_num - 1].strip() if line_num <= len(lines) else str(node)[:200]
                    findings.append({
                        'pattern_name': 'CORS_NULL_ORIGIN_ALLOWED',
                        'message': 'Flask-CORS configuration allows "null" origin',
                        'file': file_path,
                        'line': line_num,
                        'column': getattr(node, 'col_offset', 0),
                        'severity': 'high',
                        'snippet': snippet,
                        'category': 'security'
                    })
        
        # Check for response header setting in Python
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                # Check for response.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
                if node.func.attr in ['set_header', 'add_header'] or 'header' in node.func.attr:
                    # Check arguments for CORS headers
                    if len(node.args) >= 2:
                        first_arg = node.args[0]
                        if isinstance(first_arg, ast.Constant) and 'Access-Control-Allow-Origin' in str(first_arg.value):
                            # Check if reflecting origin
                            second_arg = node.args[1]
                            if 'origin' in ast.unparse(second_arg).lower() if hasattr(ast, 'unparse') else False:
                                line_num = getattr(node, 'lineno', 0)
                                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else str(node)[:200]
                                findings.append({
                                    'pattern_name': 'CORS_REFLECTED_ORIGIN',
                                    'message': 'Python: Origin header potentially reflected without validation',
                                    'file': file_path,
                                    'line': line_num,
                                    'column': getattr(node, 'col_offset', 0),
                                    'severity': 'critical',
                                    'snippet': snippet,
                                    'category': 'security'
                                })


def _extract_object_properties(node) -> Dict[str, str]:
    """Extract properties from a JavaScript object literal in Tree-sitter AST."""
    properties = {}
    
    if not node:
        return properties
    
    # Navigate through the AST to find object properties
    for child in node.children:
        if child.type == "object":
            for prop_child in child.children:
                if prop_child.type == "pair":
                    key_node = prop_child.child_by_field_name('key')
                    value_node = prop_child.child_by_field_name('value')
                    
                    if key_node and value_node:
                        key = key_node.text.decode('utf-8', errors='ignore').strip('"\'')
                        value = value_node.text.decode('utf-8', errors='ignore').strip('"\'')
                        properties[key] = value
                elif prop_child.type == "property":
                    # Alternative property format
                    for subchild in prop_child.children:
                        if subchild.type == "property_identifier":
                            key = subchild.text.decode('utf-8', errors='ignore')
                        elif subchild.type in ["string", "true", "false", "null"]:
                            value = subchild.text.decode('utf-8', errors='ignore').strip('"\'')
                            if key:
                                properties[key] = value
    
    # Also check direct children if it's an arguments list
    if node.type == "arguments":
        for child in node.children:
            if child.type == "object":
                return _extract_object_properties(child)
    
    return properties


def _get_parent_context(node, lines, context_lines=5) -> str:
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
        # Pattern 1: Wildcard with credentials in JavaScript
        pattern_wildcard_creds = re.compile(
            r'cors\s*\(\s*\{[^}]*origin\s*:\s*["\']?\*["\']?[^}]*credentials\s*:\s*true',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in pattern_wildcard_creds.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
            findings.append({
                'pattern_name': 'CORS_WILDCARD_WITH_CREDENTIALS',
                'message': 'CORS wildcard with credentials (regex fallback)',
                'file': file_path,
                'line': line_num,
                'column': 0,
                'severity': 'critical',
                'snippet': snippet,
                'category': 'security'
            })
        
        # Pattern 2: Origin reflection without validation
        pattern_reflect = re.compile(
            r'res\.(setHeader|set|header)\s*\(["\']Access-Control-Allow-Origin["\'],\s*req\.(headers\[?["\']origin|\s*header\(["\']origin)',
            re.IGNORECASE
        )
        
        for match in pattern_reflect.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            # Check for validation in surrounding lines
            context_start = max(0, line_num - 5)
            context_end = min(len(lines), line_num + 5)
            context = '\n'.join(lines[context_start:context_end])
            
            if not any(word in context for word in ['whitelist', 'allowed', 'includes', 'indexOf']):
                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
                findings.append({
                    'pattern_name': 'CORS_REFLECTED_ORIGIN',
                    'message': 'Origin reflected without validation (regex fallback)',
                    'file': file_path,
                    'line': line_num,
                    'column': 0,
                    'severity': 'critical',
                    'snippet': snippet,
                    'category': 'security'
                })
        
        # Pattern 3: Null origin allowed
        pattern_null = re.compile(
            r'cors\s*\(\s*\{[^}]*origin\s*:\s*[^}]*null',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in pattern_null.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
            findings.append({
                'pattern_name': 'CORS_NULL_ORIGIN_ALLOWED',
                'message': 'Null origin allowed (regex fallback)',
                'file': file_path,
                'line': line_num,
                'column': 0,
                'severity': 'high',
                'snippet': snippet,
                'category': 'security'
            })
        
        # Pattern 4: Manual OPTIONS handling
        pattern_options = re.compile(
            r'(app|router)\.(options|route\(["\']OPTIONS)|method\s*===?\s*["\']OPTIONS',
            re.IGNORECASE
        )
        
        for match in pattern_options.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            # Check if setting CORS headers nearby
            context_start = max(0, line_num - 10)
            context_end = min(len(lines), line_num + 10)
            context = '\n'.join(lines[context_start:context_end])
            
            if 'Access-Control' in context:
                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
                findings.append({
                    'pattern_name': 'CORS_MANUAL_PREFLIGHT',
                    'message': 'Manual OPTIONS handling (regex fallback)',
                    'file': file_path,
                    'line': line_num,
                    'column': 0,
                    'severity': 'medium',
                    'snippet': snippet,
                    'category': 'security'
                })
    
    elif is_python:
        # Pattern 1: Flask-CORS wildcard with credentials
        pattern_flask_wildcard = re.compile(
            r'CORS\([^)]*origins\s*=\s*["\']?\*[^)]*supports_credentials\s*=\s*True',
            re.IGNORECASE | re.DOTALL
        )
        
        for match in pattern_flask_wildcard.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
            findings.append({
                'pattern_name': 'CORS_WILDCARD_WITH_CREDENTIALS',
                'message': 'Flask-CORS wildcard with credentials (regex fallback)',
                'file': file_path,
                'line': line_num,
                'column': 0,
                'severity': 'critical',
                'snippet': snippet,
                'category': 'security'
            })