"""Security rules for detecting hardcoded secrets in source code.

Supports:
- Python (via native `ast` module)
- JavaScript/TypeScript (via `tree-sitter` AST)
"""

import ast
import re
from typing import List, Dict, Any

from theauditor.rules.common.util import (
    calculate_entropy,
    is_sequential,
    is_keyboard_walk,
    decode_and_verify_base64
)


def is_likely_secret(value: str) -> bool:
    """Determine if a string value is likely a secret based on patterns and entropy.
    
    Checks for:
    - High entropy (randomness)
    - Minimum length requirements
    - Common secret patterns (hex, base64, etc.)
    """
    # Skip empty or very short strings
    # COURIER PHILOSOPHY: We set thresholds but don't judge - if it matches, we report it
    if len(value) < 32:  # Increased from 20 to reduce false positives
        return False
    
    # Skip obvious non-secrets
    if value.lower() in ['true', 'false', 'none', 'null', 'undefined', 'development', 'production', 'test',
                         'staging', 'localhost', '127.0.0.1', '0.0.0.0', 'example', 'sample', 'demo']:
        return False
    
    # Skip URLs and paths (common false positives)
    if value.startswith(('http://', 'https://', '/', './', '../', 'file://', 'ftp://', 'ssh://')):
        return False
    
    # Skip module imports and package names
    if value.startswith(('theauditor.', 'from ', 'import ', '__')):
        return False
    
    # Skip template strings or placeholders
    if '${' in value or '{{' in value or '<' in value or '>' in value:
        return False
    
    # Check for Base64 pattern FIRST (before entropy check)
    # This is important because Base64 strings often have high entropy
    # even when their decoded content is simple/sequential
    base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
    if re.match(base64_pattern, value):
        # For Base64, only rely on decode-and-verify, not the encoded string's entropy
        return decode_and_verify_base64(value)
    
    # Check for high entropy (indicates randomness)
    entropy = calculate_entropy(value)
    if entropy > 4.5:  # Increased from 4.2 to reduce false positives
        # Check for false positive patterns before concluding it's a secret
        if not (is_sequential(value) or is_keyboard_walk(value)):
            return True
    
    # Other secret patterns
    secret_patterns = [
        r'^[a-fA-F0-9]{32,}$',  # Hex strings (MD5, SHA, etc.)
        r'^[A-Z0-9]{20,}$',  # All caps alphanumeric (common for API keys)
        r'^sk_[a-zA-Z0-9]{24,}$',  # Stripe secret key pattern
        r'^pk_[a-zA-Z0-9]{24,}$',  # Stripe public key pattern
        r'^[a-zA-Z0-9]{40}$',  # GitHub token pattern
        r'^AKIA[0-9A-Z]{16}$',  # AWS access key pattern
    ]
    
    for pattern in secret_patterns:
        if re.match(pattern, value):
            # Additional check: reject if too few unique characters (likely repetitive)
            unique_chars = len(set(value))
            if unique_chars < 3 and len(value) >= 32:  # Updated to match new minimum length
                # Skip patterns with < 3 unique chars (repetitive strings)
                continue
            return True
    
    # If entropy is moderately high and string contains mixed case/numbers/symbols
    if entropy > 3.5:
        has_upper = any(c.isupper() for c in value)
        has_lower = any(c.islower() for c in value)
        has_digit = any(c.isdigit() for c in value)
        has_symbol = any(not c.isalnum() and not c.isspace() for c in value)
        
        # Likely a secret if it has significant character diversity
        # Requires at least 3 out of 4 character categories
        if sum([has_upper, has_lower, has_digit, has_symbol]) >= 3:
            # Final validation: exclude predictable patterns
            if not (is_sequential(value) or is_keyboard_walk(value)):
                return True
    
    return False


def find_hardcoded_secrets(tree: Any) -> List[Dict[str, Any]]:
    """Find hardcoded secrets in AST (language-aware).
    
    Detects:
    - Variables with security-related names containing string literals
    - High-entropy strings that look like API keys or tokens
    - Common secret patterns in assignments
    
    Supports:
    - Python (native ast.AST)
    - JavaScript/TypeScript (tree-sitter or regex fallback)
    
    Args:
        tree: Either a Python ast.AST object (legacy) or a wrapped AST dict from ast_parser.py
    
    Returns:
        List of findings with line, column, variable name, and confidence score
    """
    # Handle both legacy (direct ast.AST) and new wrapped format
    if isinstance(tree, ast.AST):
        # Legacy format - direct Python AST
        return _find_hardcoded_secrets_python(tree)
    elif isinstance(tree, dict):
        # New wrapped format from ast_parser.py
        tree_type = tree.get("type")
        language = tree.get("language", "")  # Empty not unknown
        
        if tree_type == "python_ast":
            return _find_hardcoded_secrets_python(tree["tree"])
        elif tree_type == "tree_sitter":
            return _find_hardcoded_secrets_tree_sitter(tree)
        elif tree_type == "regex_ast":
            return _find_hardcoded_secrets_regex_ast(tree)
        else:
            # Unknown tree type
            return []
    else:
        # Unknown format
        return []


def _find_hardcoded_secrets_python(tree: ast.AST) -> List[Dict[str, Any]]:
    """Find hardcoded secrets in Python AST (original implementation).
    
    This is the original Python-specific implementation.
    """
    findings = []
    
    # Security-related variable name keywords
    secret_keywords = [
        'secret', 'token', 'password', 'passwd', 'pwd',
        'api_key', 'apikey', 'auth_token', 'credential', 'private_key',
        'access_token', 'refresh_token', 'bearer', 'oauth', 'jwt',
        'session_id', 'cookie', 'signature', 'salt',
        'encryption_key', 'decrypt', 'encrypt', 'cipher',
        'aws_secret', 'azure_key', 'gcp_key', 'stripe', 'github_token', 'gitlab_token'
    ]
    
    # Walk the AST looking for assignments
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            # Check each target of the assignment
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id.lower()
                    
                    # Check if variable name contains security keywords
                    has_secret_keyword = any(keyword in var_name for keyword in secret_keywords)
                    
                    # Check the assigned value
                    if isinstance(node.value, (ast.Constant, ast.Str)):
                        # Get the string value
                        if isinstance(node.value, ast.Constant):
                            value = node.value.value
                        else:  # ast.Str for older Python versions
                            value = node.value.s
                        
                        # Only check string values
                        if isinstance(value, str):
                            is_suspicious = False
                            confidence = 0.0
                            
                            # High confidence if variable name is suspicious AND value looks like a secret
                            if has_secret_keyword and is_likely_secret(value):
                                is_suspicious = True
                                confidence = 0.95
                            # Medium-high confidence if variable name is very suspicious
                            elif var_name in ['password', 'secret', 'api_key', 'private_key', 'access_token']:
                                if len(value) > 10 and value not in ['placeholder', 'changeme', 'your_password_here']:
                                    # For Base64 strings with suspicious names, still verify the decoded content
                                    base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                                    if re.match(base64_pattern, value):
                                        # Only flag if decoded content is secret-like
                                        if decode_and_verify_base64(value):
                                            is_suspicious = True
                                            confidence = 0.85
                                    else:
                                        # Non-Base64 suspicious variable names
                                        is_suspicious = True
                                        confidence = 0.85
                            # Medium confidence if only the value looks like a secret
                            elif is_likely_secret(value):
                                is_suspicious = True
                                confidence = 0.70 if has_secret_keyword else 0.60
                            
                            if is_suspicious:
                                # Check if this is a Base64 encoded secret
                                base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                                is_base64 = re.match(base64_pattern, value) is not None
                                
                                # Redact the actual secret value for security
                                if is_base64:
                                    snippet = f"{target.id} = {'*' * min(len(value), 20)}... (Base64 encoded secret, decoded content appears random)"
                                else:
                                    snippet = f"{target.id} = {'*' * min(len(value), 20)}..."
                                
                                findings.append({
                                    'line': getattr(node, 'lineno', 0),
                                    'column': getattr(node, 'col_offset', 0),
                                    'variable': target.id,
                                    'snippet': snippet,
                                    'confidence': confidence,
                                    'severity': 'CRITICAL',
                                    'type': 'hardcoded_secret',
                                    'hint': f'Move {target.id} to environment variables or secure vault'
                                })
        
        # Also check for dictionary literals with secret keys
        elif isinstance(node, ast.Dict):
            for key_node, value_node in zip(node.keys, node.values):
                if isinstance(key_node, (ast.Constant, ast.Str)):
                    # Get key name
                    if isinstance(key_node, ast.Constant):
                        key_name = str(key_node.value).lower()
                    else:
                        key_name = str(key_node.s).lower()
                    
                    # Check if key name is suspicious
                    has_secret_keyword = any(keyword in key_name for keyword in secret_keywords)
                    
                    if isinstance(value_node, (ast.Constant, ast.Str)):
                        # Get value
                        if isinstance(value_node, ast.Constant):
                            value = value_node.value
                        else:
                            value = value_node.s
                        
                        if isinstance(value, str):
                            is_suspicious = False
                            confidence = 0.0
                            
                            # High confidence if key name is suspicious AND value looks like a secret
                            if has_secret_keyword and is_likely_secret(value):
                                is_suspicious = True
                                confidence = 0.90
                            # Medium-high confidence if key name is very suspicious
                            elif key_name in ['password', 'secret', 'api_key', 'private_key', 'access_token']:
                                if len(value) > 10 and value not in ['placeholder', 'changeme', 'your_password_here']:
                                    # For Base64 strings with suspicious names, still verify the decoded content
                                    base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                                    if re.match(base64_pattern, value):
                                        # Only flag if decoded content is secret-like
                                        if decode_and_verify_base64(value):
                                            is_suspicious = True
                                            confidence = 0.80
                                    else:
                                        # Non-Base64 suspicious key names
                                        is_suspicious = True
                                        confidence = 0.80
                            # Medium confidence if only the value looks like a secret
                            elif is_likely_secret(value):
                                is_suspicious = True
                                confidence = 0.60 if has_secret_keyword else 0.50
                            
                            if is_suspicious:
                                # Check if this is a Base64 encoded secret
                                base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                                is_base64 = re.match(base64_pattern, value) is not None
                                
                                if is_base64:
                                    snippet = f'"{key_name}": {"*" * min(len(value), 20)}... (Base64 encoded secret, decoded content appears random)'
                                else:
                                    snippet = f'"{key_name}": {"*" * min(len(value), 20)}...'
                                
                                findings.append({
                                    'line': getattr(node, 'lineno', 0),
                                    'column': getattr(node, 'col_offset', 0),
                                    'variable': f'dict[{key_name}]',
                                    'snippet': snippet,
                                    'confidence': confidence,
                                    'severity': 'CRITICAL',
                                    'type': 'hardcoded_secret',
                                    'hint': f'Move secret value for "{key_name}" to environment variables'
                                })
    
    return findings


def _find_hardcoded_secrets_tree_sitter(tree_wrapper: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find hardcoded secrets in JavaScript/TypeScript using tree-sitter AST.
    
    Uses tree-sitter queries to find variable declarations and assignments
    that might contain hardcoded secrets.
    """
    findings = []
    
    # Security-related variable name keywords (same as Python)
    secret_keywords = [
        'key', 'secret', 'token', 'password', 'passwd', 'pwd',
        'api', 'auth', 'credential', 'private', 'priv',
        'access', 'refresh', 'bearer', 'oauth', 'jwt',
        'session', 'cookie', 'signature', 'salt', 'hash',
        'encryption', 'decrypt', 'encrypt', 'cipher',
        'aws', 'azure', 'gcp', 'stripe', 'github', 'gitlab'
    ]
    
    tree = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    language = tree_wrapper.get("language", "javascript")
    
    if not tree:
        return findings
    
    # Try to use tree-sitter for proper traversal
    try:
        # Import tree-sitter dynamically (since it might not be available)
        import tree_sitter
        from tree_sitter_language_pack import get_language
        
        lang = get_language(language)
        
        # Query for variable declarations with string values
        # This captures const/let/var declarations with string literals
        var_query = lang.query("""
            (variable_declaration
              (variable_declarator
                name: (identifier) @var_name
                value: (string) @var_value))
        """)
        
        # Query for object properties with string values
        # This captures { key: "value" } patterns
        obj_query = lang.query("""
            (pair
              key: [(property_identifier) (string)] @key_name
              value: (string) @key_value)
        """)
        
        # Query for assignment expressions
        # This captures variable = "value" patterns
        assign_query = lang.query("""
            (assignment_expression
              left: (identifier) @var_name
              right: (string) @var_value)
        """)
        
        # Process variable declarations
        for capture in var_query.captures(tree.root_node):
            node, capture_name = capture
            
            if capture_name == "var_name":
                var_name_node = node
                # Find the corresponding value node
                parent = node.parent
                if parent and parent.type == "variable_declarator":
                    for child in parent.children:
                        if child.type == "string":
                            value_node = child
                            var_name = var_name_node.text.decode("utf-8", errors="ignore").lower()
                            value_text = value_node.text.decode("utf-8", errors="ignore")
                            
                            # Remove quotes from string literal
                            if len(value_text) >= 2 and value_text[0] in ['"', "'", "`"]:
                                value = value_text[1:-1]
                            else:
                                value = value_text
                            
                            # Apply same detection logic as Python
                            has_secret_keyword = any(keyword in var_name for keyword in secret_keywords)
                            is_suspicious = False
                            confidence = 0.0
                            
                            if has_secret_keyword and is_likely_secret(value):
                                is_suspicious = True
                                confidence = 0.95
                            elif var_name in ['password', 'secret', 'api_key', 'apikey', 'private_key', 'privatekey', 'access_token', 'accesstoken']:
                                if len(value) > 10 and value not in ['placeholder', 'changeme', 'your_password_here']:
                                    base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                                    if re.match(base64_pattern, value):
                                        if decode_and_verify_base64(value):
                                            is_suspicious = True
                                            confidence = 0.85
                                    else:
                                        is_suspicious = True
                                        confidence = 0.85
                            elif is_likely_secret(value):
                                is_suspicious = True
                                confidence = 0.70 if has_secret_keyword else 0.60
                            
                            if is_suspicious:
                                # Check if this is a Base64 encoded secret
                                base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                                is_base64 = re.match(base64_pattern, value) is not None
                                
                                var_name_text = var_name_node.text.decode('utf-8', errors='ignore')
                                if is_base64:
                                    snippet = f"{var_name_text} = {'*' * min(len(value), 20)}... (Base64 encoded secret, decoded content appears random)"
                                else:
                                    snippet = f"{var_name_text} = {'*' * min(len(value), 20)}..."
                                
                                findings.append({
                                    'line': var_name_node.start_point[0] + 1,
                                    'column': var_name_node.start_point[1],
                                    'variable': var_name_text,
                                    'snippet': snippet,
                                    'confidence': confidence,
                                    'severity': 'CRITICAL',
                                    'type': 'hardcoded_secret',
                                    'hint': f'Move {var_name_text} to environment variables or secure vault'
                                })
        
        # Process object properties
        for capture in obj_query.captures(tree.root_node):
            node, capture_name = capture
            
            if capture_name == "key_name":
                key_node = node
                # Find the corresponding value node
                parent = node.parent
                if parent and parent.type == "pair":
                    for child in parent.children:
                        if child.type == "string" and child != key_node:
                            value_node = child
                            key_text = key_node.text.decode("utf-8", errors="ignore")
                            
                            # Remove quotes if it's a string key
                            if len(key_text) >= 2 and key_text[0] in ['"', "'", "`"]:
                                key_name = key_text[1:-1].lower()
                            else:
                                key_name = key_text.lower()
                            
                            value_text = value_node.text.decode("utf-8", errors="ignore")
                            # Remove quotes from string value
                            if len(value_text) >= 2 and value_text[0] in ['"', "'", "`"]:
                                value = value_text[1:-1]
                            else:
                                value = value_text
                            
                            # Apply detection logic
                            has_secret_keyword = any(keyword in key_name for keyword in secret_keywords)
                            is_suspicious = False
                            confidence = 0.0
                            
                            if has_secret_keyword and is_likely_secret(value):
                                is_suspicious = True
                                confidence = 0.90
                            elif key_name in ['password', 'secret', 'api_key', 'apikey', 'private_key', 'privatekey', 'access_token', 'accesstoken']:
                                if len(value) > 10 and value not in ['placeholder', 'changeme', 'your_password_here']:
                                    base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                                    if re.match(base64_pattern, value):
                                        if decode_and_verify_base64(value):
                                            is_suspicious = True
                                            confidence = 0.80
                                    else:
                                        is_suspicious = True
                                        confidence = 0.80
                            elif is_likely_secret(value):
                                is_suspicious = True
                                confidence = 0.60 if has_secret_keyword else 0.50
                            
                            if is_suspicious:
                                # Check if this is a Base64 encoded secret
                                base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                                is_base64 = re.match(base64_pattern, value) is not None
                                
                                if is_base64:
                                    snippet = f'"{key_name}": {"*" * min(len(value), 20)}... (Base64 encoded secret, decoded content appears random)'
                                else:
                                    snippet = f'"{key_name}": {"*" * min(len(value), 20)}...'
                                
                                findings.append({
                                    'line': key_node.start_point[0] + 1,
                                    'column': key_node.start_point[1],
                                    'variable': f'object[{key_name}]',
                                    'snippet': snippet,
                                    'confidence': confidence,
                                    'severity': 'CRITICAL',
                                    'type': 'hardcoded_secret',
                                    'hint': f'Move secret value for "{key_name}" to environment variables'
                                })
        
        # Process assignment expressions
        for capture in assign_query.captures(tree.root_node):
            node, capture_name = capture
            
            if capture_name == "var_name":
                var_name_node = node
                # Find the corresponding value node
                parent = node.parent
                if parent and parent.type == "assignment_expression":
                    for child in parent.children:
                        if child.type == "string":
                            value_node = child
                            var_name = var_name_node.text.decode("utf-8", errors="ignore").lower()
                            value_text = value_node.text.decode("utf-8", errors="ignore")
                            
                            # Remove quotes from string literal
                            if len(value_text) >= 2 and value_text[0] in ['"', "'", "`"]:
                                value = value_text[1:-1]
                            else:
                                value = value_text
                            
                            # Apply detection logic
                            has_secret_keyword = any(keyword in var_name for keyword in secret_keywords)
                            is_suspicious = False
                            confidence = 0.0
                            
                            if has_secret_keyword and is_likely_secret(value):
                                is_suspicious = True
                                confidence = 0.95
                            elif var_name in ['password', 'secret', 'api_key', 'apikey', 'private_key', 'privatekey', 'access_token', 'accesstoken']:
                                if len(value) > 10 and value not in ['placeholder', 'changeme', 'your_password_here']:
                                    base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                                    if re.match(base64_pattern, value):
                                        if decode_and_verify_base64(value):
                                            is_suspicious = True
                                            confidence = 0.85
                                    else:
                                        is_suspicious = True
                                        confidence = 0.85
                            elif is_likely_secret(value):
                                is_suspicious = True
                                confidence = 0.70 if has_secret_keyword else 0.60
                            
                            if is_suspicious:
                                # Check if this is a Base64 encoded secret
                                base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                                is_base64 = re.match(base64_pattern, value) is not None
                                
                                var_name_text = var_name_node.text.decode('utf-8', errors='ignore')
                                if is_base64:
                                    snippet = f"{var_name_text} = {'*' * min(len(value), 20)}... (Base64 encoded secret, decoded content appears random)"
                                else:
                                    snippet = f"{var_name_text} = {'*' * min(len(value), 20)}..."
                                
                                findings.append({
                                    'line': var_name_node.start_point[0] + 1,
                                    'column': var_name_node.start_point[1],
                                    'variable': var_name_text,
                                    'snippet': snippet,
                                    'confidence': confidence,
                                    'severity': 'CRITICAL',
                                    'type': 'hardcoded_secret',
                                    'hint': f'Move {var_name_text} to environment variables or secure vault'
                                })
    
    except (ImportError, Exception):
        # Tree-sitter not available or query failed, fall back to regex_ast logic
        return _find_hardcoded_secrets_regex_ast(tree_wrapper)
    
    return findings


def _find_hardcoded_secrets_regex_ast(tree_wrapper: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find hardcoded secrets using regex-based fallback AST.
    
    This is used when tree-sitter is not available for JavaScript/TypeScript.
    It uses regex patterns to find potential secrets in the code.
    """
    findings = []
    
    # Security-related variable name keywords
    secret_keywords = [
        'secret', 'token', 'password', 'passwd', 'pwd',
        'api_key', 'apikey', 'auth_token', 'credential', 'private_key',
        'access_token', 'refresh_token', 'bearer', 'oauth', 'jwt',
        'session_id', 'cookie', 'signature', 'salt',
        'encryption_key', 'decrypt', 'encrypt', 'cipher',
        'aws_secret', 'azure_key', 'gcp_key', 'stripe', 'github_token', 'gitlab_token'
    ]
    
    content = tree_wrapper.get("content", "")
    
    if not content:
        return findings
    
    lines = content.split('\n')
    
    # Regex patterns for JavaScript/TypeScript variable assignments
    patterns = [
        # const/let/var variable = "string"
        (r'(?:const|let|var)\s+(\w+)\s*=\s*["\']([^"\']+)["\']', 'variable'),
        # variable = "string" (reassignment)
        (r'^(\w+)\s*=\s*["\']([^"\']+)["\']', 'variable'),
        # { key: "value" } in objects
        (r'["\']?(\w+)["\']?\s*:\s*["\']([^"\']+)["\']', 'object_property'),
        # Template literals with static content
        (r'(?:const|let|var)\s+(\w+)\s*=\s*`([^`]+)`', 'template_literal'),
    ]
    
    for line_num, line in enumerate(lines, 1):
        for pattern, pattern_type in patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                if len(match.groups()) >= 2:
                    var_or_key = match.group(1).lower()
                    value = match.group(2)
                    
                    # Check if variable/key name contains security keywords
                    has_secret_keyword = any(keyword in var_or_key for keyword in secret_keywords)
                    
                    # Determine if this is suspicious
                    is_suspicious = False
                    confidence = 0.0
                    
                    if has_secret_keyword and is_likely_secret(value):
                        is_suspicious = True
                        confidence = 0.85  # Slightly lower confidence for regex-based detection
                    elif var_or_key in ['password', 'secret', 'api_key', 'apikey', 'private_key', 'privatekey', 'access_token', 'accesstoken']:
                        if len(value) > 10 and value not in ['placeholder', 'changeme', 'your_password_here']:
                            base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                            if re.match(base64_pattern, value):
                                if decode_and_verify_base64(value):
                                    is_suspicious = True
                                    confidence = 0.75
                            else:
                                is_suspicious = True
                                confidence = 0.75
                    elif is_likely_secret(value):
                        is_suspicious = True
                        confidence = 0.60 if has_secret_keyword else 0.50
                    
                    if is_suspicious:
                        # Check if this is a Base64 encoded secret
                        base64_pattern = r'^(?!([A-Za-z0-9+/])\1{19,})[A-Za-z0-9+/]{20,}={0,2}$'
                        is_base64 = re.match(base64_pattern, value) is not None
                        
                        if pattern_type == 'object_property':
                            if is_base64:
                                snippet = f'"{var_or_key}": {"*" * min(len(value), 20)}... (Base64 encoded secret, decoded content appears random)'
                            else:
                                snippet = f'"{var_or_key}": {"*" * min(len(value), 20)}...'
                            variable_name = f'object[{var_or_key}]'
                        else:
                            if is_base64:
                                snippet = f"{match.group(1)} = {'*' * min(len(value), 20)}... (Base64 encoded secret, decoded content appears random)"
                            else:
                                snippet = f"{match.group(1)} = {'*' * min(len(value), 20)}..."
                            variable_name = match.group(1)
                        
                        findings.append({
                            'line': line_num,
                            'column': match.start(),
                            'variable': variable_name,
                            'snippet': snippet,
                            'confidence': confidence * 0.9,  # Lower confidence for regex-based detection
                            'severity': 'CRITICAL',
                            'type': 'hardcoded_secret',
                            'hint': f'Move {variable_name} to environment variables or secure vault'
                        })
    
    return findings