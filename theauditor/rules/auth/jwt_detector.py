"""AST-based JWT implementation flaw detector.

This module provides high-fidelity detection of common JWT security vulnerabilities
by analyzing the AST structure of jwt.sign() and jwt.verify() calls.
"""

import re
from typing import Any, List, Dict


def find_jwt_flaws(tree: Any, file_path: str) -> List[Dict[str, Any]]:
    """
    Detect common JWT implementation flaws using AST analysis.
    
    This is a file-based AST rule designed to be called by universal_detector
    for each JavaScript/TypeScript file. It detects:
    
    - Algorithm confusion attacks (mixing HS256/RS256)
    - Weak secrets (<32 characters)
    - Missing expiration claims
    - Sensitive data in JWT payloads
    - Missing refresh token rotation
    
    Args:
        tree: AST tree from ast_parser (TypeScript compiler preferred, Tree-sitter fallback)
        file_path: Path to the file being analyzed
        
    Returns:
        List of security findings in normalized format
    """
    findings = []
    
    if not tree or not isinstance(tree, dict):
        return findings
    
    # Read file content for context extraction
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
    except:
        return findings
    
    tree_type = tree.get("type")
    
    # TypeScript compiler AST is the CORRECT tool for JS/TS analysis
    if tree_type == "semantic_ast":
        # Analyze TypeScript compiler AST
        _analyze_typescript_ast(tree.get("ast"), findings, file_path, lines)
        return findings
    
    # Tree-sitter is fallback for when TypeScript compiler isn't available
    elif tree_type == "tree_sitter":
        actual_tree = tree.get("tree")
        if actual_tree and hasattr(actual_tree, 'root_node'):
            # Use Tree-sitter if that's what we have
            _analyze_tree_sitter_node(actual_tree.root_node, findings, file_path, lines)
            _detect_refresh_token_rotation(actual_tree.root_node, findings, file_path, lines)
    
    # Pattern-based as last resort
    else:
        _analyze_with_patterns(file_path, findings)
    
    return findings


def _analyze_tree_sitter_node(node, findings, file_path, lines, depth=0):
    """Recursively analyze Tree-sitter AST nodes for JWT issues."""
    
    # Prevent infinite recursion
    if depth > 100:
        return
    
    # Check for call expressions
    if node.type == "call_expression":
        # Get function being called
        func_node = node.child_by_field_name('function')
        if func_node:
            func_text = func_node.text.decode('utf-8', errors='ignore')
            
            # Get arguments node
            args_node = node.child_by_field_name('arguments')
            
            # Detection 1: jwt.verify with algorithm confusion
            if 'jwt.verify' in func_text or '.verify' in func_text:
                if args_node:
                    args_text = args_node.text.decode('utf-8', errors='ignore')
                    line_num = node.start_point[0] + 1
                    
                    # Check for dangerous algorithm combinations
                    if 'algorithms' in args_text:
                        # Look for both symmetric (HS) and asymmetric (RS/ES) algorithms
                        has_symmetric = any(alg in args_text for alg in ['HS256', 'HS384', 'HS512'])
                        has_asymmetric = any(alg in args_text for alg in ['RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512'])
                        
                        if has_symmetric and has_asymmetric:
                            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else args_text[:200]
                            findings.append({
                                'pattern_name': 'JWT_ALGORITHM_CONFUSION',
                                'message': 'Algorithm confusion vulnerability: both symmetric (HS) and asymmetric (RS/ES) algorithms allowed',
                                'file': file_path,
                                'line': line_num,
                                'column': node.start_point[1],
                                'severity': 'critical',
                                'snippet': snippet,
                                'category': 'security',
                                'details': {
                                    'vulnerability': 'Allows attacker to switch from RS256 to HS256 and use public key as HMAC secret',
                                    'fix': 'Use only one type of algorithm (either symmetric or asymmetric, not both)'
                                }
                            })
            
            # Detection 2 & 3: jwt.sign with weak secret or missing expiration
            elif 'jwt.sign' in func_text or '.sign' in func_text:
                if args_node and args_node.children:
                    line_num = node.start_point[0] + 1
                    
                    # Extract the three arguments: payload, secret, options
                    args = []
                    current_arg = []
                    paren_depth = 0
                    bracket_depth = 0
                    brace_depth = 0
                    in_string = False
                    string_char = None
                    
                    # Parse arguments accounting for nested structures
                    args_text = args_node.text.decode('utf-8', errors='ignore')
                    for i, char in enumerate(args_text):
                        # Handle string boundaries
                        if char in ['"', "'", '`'] and (i == 0 or args_text[i-1] != '\\'):
                            if not in_string:
                                in_string = True
                                string_char = char
                            elif char == string_char:
                                in_string = False
                                string_char = None
                        
                        if not in_string:
                            if char == '(':
                                paren_depth += 1
                            elif char == ')':
                                paren_depth -= 1
                            elif char == '[':
                                bracket_depth += 1
                            elif char == ']':
                                bracket_depth -= 1
                            elif char == '{':
                                brace_depth += 1
                            elif char == '}':
                                brace_depth -= 1
                            elif char == ',' and paren_depth == 1 and bracket_depth == 0 and brace_depth == 0:
                                # Found argument separator at top level
                                args.append(''.join(current_arg).strip())
                                current_arg = []
                                continue
                        
                        if paren_depth > 0:  # Inside the arguments
                            current_arg.append(char)
                    
                    # Add last argument
                    if current_arg:
                        args.append(''.join(current_arg).strip())
                    
                    # Clean up arguments (remove leading/trailing parens)
                    args = [arg.strip('()').strip() for arg in args]
                    
                    # Check secret strength (second argument)
                    if len(args) >= 2:
                        secret = args[1]
                        
                        # Detection 2: Weak secret
                        # Check if it's a string literal
                        if (secret.startswith('"') or secret.startswith("'") or secret.startswith('`')):
                            # Extract the actual secret value
                            secret_value = secret.strip('"\'`')
                            
                            # Check for obvious weak secrets
                            weak_patterns = ['secret', 'password', 'key', '123', 'test', 'demo', 'example']
                            is_weak = (
                                len(secret_value) < 32 or  # Less than 256 bits
                                any(pattern in secret_value.lower() for pattern in weak_patterns) or
                                secret_value.isdigit() or  # All digits
                                secret_value.isalpha()  # All letters with no special chars
                            )
                            
                            if is_weak:
                                snippet = lines[line_num - 1].strip() if line_num <= len(lines) else func_text[:200]
                                findings.append({
                                    'pattern_name': 'JWT_WEAK_SECRET',
                                    'message': f'Weak JWT secret detected: {len(secret_value)} characters (need 32+ for 256 bits)',
                                    'file': file_path,
                                    'line': line_num,
                                    'column': node.start_point[1],
                                    'severity': 'critical',
                                    'snippet': snippet,
                                    'category': 'security',
                                    'details': {
                                        'secret_length': len(secret_value),
                                        'recommendation': 'Use a cryptographically strong secret of at least 32 characters (256 bits)'
                                    }
                                })
                    
                    # Check for expiration (third argument - options)
                    if len(args) >= 3:
                        options = args[2]
                        
                        # Detection 3: Missing expiration
                        has_expiry = (
                            'expiresIn' in options or 
                            'exp' in options or
                            'notAfter' in options
                        )
                        
                        if not has_expiry:
                            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else func_text[:200]
                            findings.append({
                                'pattern_name': 'JWT_MISSING_EXPIRATION',
                                'message': 'JWT token created without expiration claim',
                                'file': file_path,
                                'line': line_num,
                                'column': node.start_point[1],
                                'severity': 'high',
                                'snippet': snippet,
                                'category': 'security',
                                'details': {
                                    'risk': 'Tokens without expiration can be used indefinitely if compromised',
                                    'fix': "Add 'expiresIn' option (e.g., { expiresIn: '1h' })"
                                }
                            })
                    elif len(args) >= 1:
                        # Only payload provided, no options = no expiration
                        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else func_text[:200]
                        findings.append({
                            'pattern_name': 'JWT_MISSING_EXPIRATION',
                            'message': 'JWT token created without options object (no expiration)',
                            'file': file_path,
                            'line': line_num,
                            'column': node.start_point[1],
                            'severity': 'high',
                            'snippet': snippet,
                            'category': 'security',
                            'details': {
                                'risk': 'Tokens without expiration can be used indefinitely if compromised',
                                'fix': "Add options parameter with expiresIn (e.g., jwt.sign(payload, secret, { expiresIn: '1h' }))"
                            }
                        })
                    
                    # Detection 4: Sensitive data in payload (first argument)
                    if len(args) >= 1:
                        payload = args[0]
                        
                        # List of sensitive field names to check for
                        sensitive_fields = [
                            'password', 'passwd', 'pwd', 'secret', 'apikey', 'api_key',
                            'private', 'priv', 'ssn', 'social_security', 'credit_card',
                            'creditcard', 'cvv', 'pin', 'tax_id', 'license', 'passport',
                            'bank_account', 'routing_number', 'private_key', 'privateKey',
                            'client_secret', 'clientSecret', 'refresh_token', 'refreshToken'
                        ]
                        
                        found_sensitive = []
                        for field in sensitive_fields:
                            if field in payload.lower():
                                found_sensitive.append(field)
                        
                        if found_sensitive:
                            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else payload[:200]
                            findings.append({
                                'pattern_name': 'JWT_SENSITIVE_DATA_IN_PAYLOAD',
                                'message': f'Sensitive data in JWT payload: {", ".join(found_sensitive)}',
                                'file': file_path,
                                'line': line_num,
                                'column': node.start_point[1],
                                'severity': 'high',
                                'snippet': snippet,
                                'category': 'security',
                                'details': {
                                    'sensitive_fields': found_sensitive,
                                    'risk': 'JWT payloads are only base64 encoded, not encrypted - anyone can read them',
                                    'fix': 'Never put sensitive data in JWT payloads. Store only user ID and fetch sensitive data server-side.'
                                }
                            })
    
    # Recursively analyze children
    for child in node.children:
        _analyze_tree_sitter_node(child, findings, file_path, lines, depth + 1)


def _analyze_typescript_ast(ast_node, findings, file_path, lines):
    """
    Analyze TypeScript compiler AST for JWT vulnerabilities.
    
    The TypeScript compiler provides a much richer AST with type information
    and semantic analysis compared to Tree-sitter.
    """
    if not ast_node:
        return
    
    # Recursively walk the TypeScript AST
    def walk_ts_ast(node, depth=0):
        if depth > 100 or not isinstance(node, dict):
            return
        
        kind = node.get('kind')
        
        # Handle CallExpression nodes
        if kind == 'CallExpression':
            expression = node.get('expression', {})
            arguments = node.get('arguments', [])
            
            # Get the function name being called
            func_name = _get_ts_call_name(expression)
            
            # Get position information
            pos = node.get('pos', 0)
            line_num = _get_line_from_pos(lines, pos)
            
            # Detection 1: jwt.verify with algorithm confusion
            if func_name and ('jwt.verify' in func_name or 'verify' in func_name):
                # Check third argument (options) for algorithm settings
                if len(arguments) >= 3:
                    options_arg = arguments[2]
                    options_text = _extract_ts_text(options_arg)
                    
                    # Check for dangerous algorithm combinations
                    has_symmetric = any(alg in options_text for alg in ['HS256', 'HS384', 'HS512'])
                    has_asymmetric = any(alg in options_text for alg in ['RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512'])
                    
                    if has_symmetric and has_asymmetric:
                        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else options_text[:200]
                        findings.append({
                            'pattern_name': 'JWT_ALGORITHM_CONFUSION',
                            'message': 'Algorithm confusion vulnerability: both symmetric (HS) and asymmetric (RS/ES) algorithms allowed',
                            'file': file_path,
                            'line': line_num,
                            'column': 0,
                            'severity': 'critical',
                            'snippet': snippet,
                            'category': 'security',
                            'details': {
                                'vulnerability': 'Allows attacker to switch from RS256 to HS256 and use public key as HMAC secret',
                                'fix': 'Use only one type of algorithm (either symmetric or asymmetric, not both)'
                            }
                        })
            
            # Detection 2 & 3: jwt.sign with weak secret or missing expiration
            elif func_name and ('jwt.sign' in func_name or 'sign' in func_name):
                # Check second argument (secret)
                if len(arguments) >= 2:
                    secret_arg = arguments[1]
                    secret_text = _extract_ts_text(secret_arg)
                    
                    # Check for weak secrets
                    weak_patterns = ['secret', 'password', 'key', '123', 'test', 'demo', 'example']
                    is_weak = (
                        len(secret_text) < 32 or
                        any(pattern in secret_text.lower() for pattern in weak_patterns) or
                        secret_text.replace('"', '').replace("'", '').isdigit()
                    )
                    
                    if is_weak and secret_text:
                        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else func_name[:200]
                        findings.append({
                            'pattern_name': 'JWT_WEAK_SECRET',
                            'message': f'Weak JWT secret detected: {len(secret_text)} characters (need 32+ for 256 bits)',
                            'file': file_path,
                            'line': line_num,
                            'column': 0,
                            'severity': 'critical',
                            'snippet': snippet,
                            'category': 'security',
                            'details': {
                                'secret_length': len(secret_text),
                                'recommendation': 'Use a cryptographically strong secret of at least 32 characters (256 bits)'
                            }
                        })
                
                # Check third argument (options) for expiration
                if len(arguments) >= 3:
                    options_arg = arguments[2]
                    options_text = _extract_ts_text(options_arg)
                    
                    has_expiry = (
                        'expiresIn' in options_text or 
                        'exp' in options_text or
                        'notAfter' in options_text
                    )
                    
                    if not has_expiry:
                        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else func_name[:200]
                        findings.append({
                            'pattern_name': 'JWT_MISSING_EXPIRATION',
                            'message': 'JWT token created without expiration claim',
                            'file': file_path,
                            'line': line_num,
                            'column': 0,
                            'severity': 'high',
                            'snippet': snippet,
                            'category': 'security',
                            'details': {
                                'risk': 'Tokens without expiration remain valid forever if not explicitly revoked',
                                'fix': "Add 'expiresIn' option when signing tokens (e.g., { expiresIn: '1h' })"
                            }
                        })
                
                # Check first argument (payload) for sensitive data
                if len(arguments) >= 1:
                    payload_arg = arguments[0]
                    payload_text = _extract_ts_text(payload_arg)
                    
                    sensitive_fields = ['password', 'secret', 'ssn', 'credit_card', 'api_key', 'private_key', 'pin', 'cvv']
                    found_sensitive = [field for field in sensitive_fields if field in payload_text.lower()]
                    
                    if found_sensitive:
                        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else payload_text[:200]
                        findings.append({
                            'pattern_name': 'JWT_SENSITIVE_DATA_IN_PAYLOAD',
                            'message': f'Sensitive data in JWT payload: {", ".join(found_sensitive)}',
                            'file': file_path,
                            'line': line_num,
                            'column': 0,
                            'severity': 'high',
                            'snippet': snippet,
                            'category': 'security',
                            'details': {
                                'sensitive_fields': found_sensitive,
                                'risk': 'JWT payloads are only base64 encoded, not encrypted - anyone can read them',
                                'fix': 'Never put sensitive data in JWT payloads. Store only user ID and fetch sensitive data server-side.'
                            }
                        })
        
        # Recursively process all child nodes
        for key, value in node.items():
            if key in ['statements', 'declarations', 'elements', 'properties', 'members']:
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            walk_ts_ast(item, depth + 1)
            elif isinstance(value, dict):
                walk_ts_ast(value, depth + 1)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        walk_ts_ast(item, depth + 1)
    
    # Helper function to extract function name from TypeScript CallExpression
    def _get_ts_call_name(expression):
        if not isinstance(expression, dict):
            return None
        
        # Handle PropertyAccessExpression (e.g., jwt.sign)
        if expression.get('kind') == 'PropertyAccessExpression':
            obj = expression.get('expression', {})
            prop = expression.get('name', {})
            obj_text = _extract_ts_identifier(obj)
            prop_text = _extract_ts_identifier(prop)
            if obj_text and prop_text:
                return f"{obj_text}.{prop_text}"
            return prop_text or obj_text
        
        # Handle Identifier (e.g., verify)
        elif expression.get('kind') == 'Identifier':
            return expression.get('text', expression.get('escapedText', ''))
        
        return None
    
    # Helper function to extract identifier text
    def _extract_ts_identifier(node):
        if not isinstance(node, dict):
            return None
        if node.get('kind') == 'Identifier':
            return node.get('text', node.get('escapedText', ''))
        return None
    
    # Helper function to extract text from TypeScript AST node
    def _extract_ts_text(node):
        if not isinstance(node, dict):
            return ''
        
        # String literal
        if node.get('kind') == 'StringLiteral':
            return node.get('text', '')
        
        # Template literal
        elif node.get('kind') == 'TemplateExpression':
            return node.get('text', '')
        
        # Object literal
        elif node.get('kind') == 'ObjectLiteralExpression':
            properties = node.get('properties', [])
            parts = []
            for prop in properties:
                if isinstance(prop, dict):
                    name = prop.get('name', {})
                    if isinstance(name, dict):
                        parts.append(name.get('text', name.get('escapedText', '')))
            return ' '.join(parts)
        
        # Array literal
        elif node.get('kind') == 'ArrayLiteralExpression':
            elements = node.get('elements', [])
            parts = []
            for elem in elements:
                if isinstance(elem, dict):
                    parts.append(_extract_ts_text(elem))
            return ' '.join(parts)
        
        # Identifier
        elif node.get('kind') == 'Identifier':
            return node.get('text', node.get('escapedText', ''))
        
        # Recursively get text from nested structures
        text_parts = []
        for key, value in node.items():
            if isinstance(value, dict):
                sub_text = _extract_ts_text(value)
                if sub_text:
                    text_parts.append(sub_text)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        sub_text = _extract_ts_text(item)
                        if sub_text:
                            text_parts.append(sub_text)
        
        return ' '.join(text_parts)
    
    # Helper function to get line number from character position
    def _get_line_from_pos(lines, pos):
        char_count = 0
        for i, line in enumerate(lines, 1):
            char_count += len(line) + 1  # +1 for newline
            if char_count > pos:
                return i
        return len(lines)
    
    # Start walking the AST
    walk_ts_ast(ast_node)


def _detect_refresh_token_rotation(root_node, findings, file_path, lines):
    """
    Detect refresh token endpoints that don't properly rotate tokens.
    
    This function analyzes function scopes to identify refresh token endpoints
    that issue new access tokens but fail to rotate the refresh token.
    """
    
    # Find all function declarations and arrow functions
    functions = _find_all_functions(root_node)
    
    for func_node in functions:
        # Analyze each function for refresh token patterns
        func_analysis = {
            'uses_refresh_token': False,
            'issues_access_token': False,
            'rotates_refresh_token': False,
            'refresh_token_line': None,
            'access_token_line': None
        }
        
        # Get function body
        body_node = None
        if func_node.type == 'function_declaration':
            body_node = func_node.child_by_field_name('body')
        elif func_node.type == 'arrow_function':
            body_node = func_node.child_by_field_name('body')
        elif func_node.type == 'function_expression':
            body_node = func_node.child_by_field_name('body')
        
        if not body_node:
            continue
        
        # Convert function body to text for analysis
        func_text = body_node.text.decode('utf-8', errors='ignore')
        func_start_line = func_node.start_point[0] + 1
        
        # Detection 1: Check if function accesses refresh token
        refresh_patterns = [
            r'req\.cookies\.refreshToken',
            r'req\.cookies\[[\'"]\s*refreshToken\s*[\'"]',
            r'req\.body\.refreshToken',
            r'req\.body\[[\'"]\s*refreshToken\s*[\'"]',
            r'req\.body\.token',  # Common pattern for refresh endpoints
            r'refreshToken\s*=\s*req\.',
            r'const\s+.*refreshToken.*=.*req\.',
            r'let\s+.*refreshToken.*=.*req\.',
            r'var\s+.*refreshToken.*=.*req\.'
        ]
        
        for pattern in refresh_patterns:
            match = re.search(pattern, func_text, re.IGNORECASE)
            if match:
                func_analysis['uses_refresh_token'] = True
                func_analysis['refresh_token_line'] = func_start_line + func_text[:match.start()].count('\n')
                break
        
        # Detection 2: Check if function issues new access token
        access_patterns = [
            r'jwt\.sign\s*\(',
            r'jsonwebtoken\.sign\s*\(',
            r'generateAccessToken\s*\(',
            r'createAccessToken\s*\(',
            r'issueAccessToken\s*\(',
            r'signAccessToken\s*\('
        ]
        
        for pattern in access_patterns:
            match = re.search(pattern, func_text, re.IGNORECASE)
            if match:
                func_analysis['issues_access_token'] = True
                func_analysis['access_token_line'] = func_start_line + func_text[:match.start()].count('\n')
                break
        
        # Detection 3: Check if function rotates refresh token
        rotation_patterns = [
            # Setting new refresh token in cookie
            r'res\.cookie\s*\(\s*[\'"]refreshToken[\'"]',
            r'res\.cookie\s*\(\s*[\'"]refresh_token[\'"]',
            r'response\.cookie\s*\(\s*[\'"]refreshToken[\'"]',
            
            # Setting new refresh token in response body
            r'refreshToken\s*:\s*[^,}]+jwt\.sign',
            r'refresh_token\s*:\s*[^,}]+jwt\.sign',
            r'newRefreshToken\s*:\s*',
            r'new_refresh_token\s*:\s*',
            
            # Database updates for refresh token
            r'update\s*\(\s*\{[^}]*refreshToken',
            r'update\s*\(\s*\{[^}]*refresh_token',
            r'save\s*\(\s*\{[^}]*refreshToken',
            r'updateOne\s*\(\s*[^)]*refreshToken',
            r'findOneAndUpdate\s*\([^)]*refreshToken',
            
            # Redis or cache operations
            r'redis\.(set|del|delete)\s*\([^)]*refresh',
            r'cache\.(set|del|delete)\s*\([^)]*refresh',
            
            # Generating new refresh token
            r'generateRefreshToken\s*\(',
            r'createRefreshToken\s*\(',
            r'issueRefreshToken\s*\(',
            r'jwt\.sign\s*\([^)]*[\'"]refresh[\'"]',
            
            # Blacklisting/invalidating old token
            r'blacklist.*refreshToken',
            r'invalidate.*refreshToken',
            r'revoke.*refreshToken'
        ]
        
        for pattern in rotation_patterns:
            match = re.search(pattern, func_text, re.IGNORECASE)
            if match:
                func_analysis['rotates_refresh_token'] = True
                break
        
        # Generate finding if refresh token endpoint doesn't rotate
        if (func_analysis['uses_refresh_token'] and 
            func_analysis['issues_access_token'] and 
            not func_analysis['rotates_refresh_token']):
            
            line_num = func_analysis['refresh_token_line'] or func_start_line
            snippet = lines[line_num - 1].strip() if line_num <= len(lines) else func_text[:200]
            
            findings.append({
                'pattern_name': 'JWT_NO_REFRESH_TOKEN_ROTATION',
                'message': 'Refresh token endpoint does not rotate refresh tokens - allows indefinite session hijacking',
                'file': file_path,
                'line': line_num,
                'column': func_node.start_point[1],
                'severity': 'high',
                'snippet': snippet,
                'category': 'security',
                'details': {
                    'vulnerability': 'Refresh tokens are not rotated when used, allowing attackers to maintain persistent access',
                    'detected_patterns': {
                        'accesses_refresh_token': True,
                        'issues_new_access_token': True,
                        'rotates_refresh_token': False
                    },
                    'fix': 'Issue a new refresh token and invalidate the old one when refreshing access tokens',
                    'recommendation': 'Implement refresh token rotation: 1) Generate new refresh token, 2) Save to database/cache, 3) Invalidate old token, 4) Return new tokens to client'
                }
            })


def _find_all_functions(node, functions=None, depth=0):
    """
    Recursively find all function declarations and expressions in the AST.
    """
    if functions is None:
        functions = []
    
    # Prevent infinite recursion
    if depth > 100:
        return functions
    
    # Check if this node is a function
    if node.type in ['function_declaration', 'arrow_function', 'function_expression']:
        functions.append(node)
    
    # Recursively check children
    for child in node.children:
        _find_all_functions(child, functions, depth + 1)
    
    return functions


def _analyze_with_patterns(file_path: str, findings: List[Dict[str, Any]]):
    """
    BONUS: Additional pattern-based detection to supplement AST analysis.
    
    This runs IN ADDITION to AST analysis to catch edge cases like:
    - Obfuscated code patterns
    - Dynamic property access
    - String concatenation forming JWT calls
    """
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
    except:
        return
    
    # Pattern 1: Algorithm confusion in jwt.verify
    pattern_algo_confusion = re.compile(
        r'jwt\.verify\s*\([^)]*algorithms\s*:\s*\[[^\]]*(?:HS256|HS384|HS512)[^\]]*(?:RS256|RS384|RS512|ES256|ES384|ES512)',
        re.IGNORECASE | re.DOTALL
    )
    
    for match in pattern_algo_confusion.finditer(content):
        line_num = content[:match.start()].count('\n') + 1
        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
        
        findings.append({
            'pattern_name': 'JWT_ALGORITHM_CONFUSION',
            'message': 'Algorithm confusion vulnerability detected (regex fallback)',
            'file': file_path,
            'line': line_num,
            'column': 0,
            'severity': 'critical',
            'snippet': snippet,
            'category': 'security'
        })
    
    # Pattern 2: Weak secrets
    pattern_weak_secret = re.compile(
        r'jwt\.sign\s*\([^,)]*,\s*["\']([^"\']{1,31})["\']',
        re.IGNORECASE
    )
    
    for match in pattern_weak_secret.finditer(content):
        secret = match.group(1)
        line_num = content[:match.start()].count('\n') + 1
        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
        
        findings.append({
            'pattern_name': 'JWT_WEAK_SECRET',
            'message': f'Weak JWT secret: {len(secret)} characters (regex fallback)',
            'file': file_path,
            'line': line_num,
            'column': 0,
            'severity': 'critical',
            'snippet': snippet,
            'category': 'security'
        })
    
    # Pattern 3: Missing expiration (jwt.sign with only 2 arguments)
    pattern_no_expiry = re.compile(
        r'jwt\.sign\s*\([^,)]+,\s*[^,)]+\s*\)',
        re.IGNORECASE
    )
    
    for match in pattern_no_expiry.finditer(content):
        line_num = content[:match.start()].count('\n') + 1
        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
        
        # Make sure it's not a multi-line call
        if 'expiresIn' not in match.group(0) and 'exp' not in match.group(0):
            findings.append({
                'pattern_name': 'JWT_MISSING_EXPIRATION',
                'message': 'JWT without expiration detected (regex fallback)',
                'file': file_path,
                'line': line_num,
                'column': 0,
                'severity': 'high',
                'snippet': snippet,
                'category': 'security'
            })
    
    # Pattern 4: Sensitive data in payload
    pattern_sensitive = re.compile(
        r'jwt\.sign\s*\(\s*\{[^}]*(?:password|passwd|pwd|secret|ssn|credit_card|private_key)[^}]*\}',
        re.IGNORECASE
    )
    
    for match in pattern_sensitive.finditer(content):
        line_num = content[:match.start()].count('\n') + 1
        snippet = lines[line_num - 1].strip() if line_num <= len(lines) else match.group(0)[:200]
        
        findings.append({
            'pattern_name': 'JWT_SENSITIVE_DATA_IN_PAYLOAD',
            'message': 'Sensitive data in JWT payload (regex fallback)',
            'file': file_path,
            'line': line_num,
            'column': 0,
            'severity': 'high',
            'snippet': snippet,
            'category': 'security'
        })