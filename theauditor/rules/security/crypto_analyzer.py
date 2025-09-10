"""Cryptography security analyzer for detecting weak crypto and random number issues.

Detects cryptographic security issues in both Python and JavaScript/TypeScript code.
Replaces regex patterns from security.yml with proper AST analysis.
"""

import ast
import re
from typing import List, Dict, Any, Optional, Set


def register_taint_patterns(taint_registry):
    """Register crypto-specific patterns with the taint system.
    
    This function is called by the orchestrator before taint analysis runs,
    allowing the taint analyzer to track weak random sources and crypto sinks.
    
    Args:
        taint_registry: TaintRegistry instance to register patterns with
    """
    # Weak random sources - these produce predictable/tainted data
    WEAK_RANDOM_SOURCES = [
        # Python weak random
        "random.random",
        "random.randint", 
        "random.choice",
        "random.randbytes",
        "random.randrange",
        "random.getrandbits",
        "random.uniform",
        "random.sample",
        "random.shuffle",
        
        # JavaScript weak random
        "Math.random",
        "Math.floor(Math.random",  # Common pattern
        
        # Timestamp-based (predictable)
        "time.time",
        "datetime.now",
        "Date.now",
        "Date.getTime",
        "new Date().getTime",
        "timestamp",
        "time.clock",
        "time.perf_counter",
    ]
    
    # Weak crypto algorithm sinks - where data shouldn't flow
    WEAK_CRYPTO_SINKS = [
        # Hash functions
        "md5",
        "sha1",
        "hashlib.md5",
        "hashlib.sha1",
        "createHash('md5')",
        'createHash("md5")',
        "createHash('sha1')",
        'createHash("sha1")',
        "CryptoJS.MD5",
        "CryptoJS.SHA1",
        
        # Encryption algorithms
        "des",
        "rc4",
        "CryptoJS.DES",
        "CryptoJS.RC4",
        "DES.new",
        "ARC4.new",
        "Blowfish.new",
        
        # Weak key derivation
        "pbkdf2_hmac('md5')",
        "pbkdf2_hmac('sha1')",
    ]
    
    # Register weak random as sources (they produce tainted/weak data)
    for pattern in WEAK_RANDOM_SOURCES:
        taint_registry.register_source(pattern, "weak_random", "any")
    
    # Register weak crypto as sinks (where data shouldn't flow)
    for pattern in WEAK_CRYPTO_SINKS:
        taint_registry.register_sink(pattern, "weak_crypto", "any")


def find_crypto_issues(tree: Any, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Find cryptographic and random number security issues.
    
    Detects:
    1. insecure-random-for-security - Math.random() or random module for security
    2. weak-crypto-algorithm - MD5, SHA1, DES, RC4 usage
    3. predictable-token-generation - Timestamp or sequential tokens
    
    Args:
        tree: Python AST or ESLint/tree-sitter AST from ast_parser.py
        file_path: Path to the file being analyzed
        taint_checker: Optional taint checking function
    
    Returns:
        List of findings with details about crypto security issues
    """
    findings = []
    
    # Determine tree type and analyze accordingly
    if isinstance(tree, dict):
        tree_type = tree.get("type")
        
        if tree_type == "python_ast":
            actual_tree = tree.get("tree")
            if actual_tree:
                return _analyze_python_crypto(actual_tree, file_path, taint_checker)
        elif tree_type == "eslint_ast":
            return _analyze_javascript_crypto(tree, file_path, taint_checker)
        elif tree_type == "tree_sitter":
            return _analyze_tree_sitter_crypto(tree, file_path, taint_checker)
    elif isinstance(tree, ast.AST):
        # Direct Python AST
        return _analyze_python_crypto(tree, file_path, taint_checker)
    
    return findings


def _analyze_python_crypto(tree: ast.AST, file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Analyze Python AST for crypto security issues."""
    analyzer = PythonCryptoAnalyzer(file_path, taint_checker)
    analyzer.visit(tree)
    return analyzer.findings


class PythonCryptoAnalyzer(ast.NodeVisitor):
    """AST visitor for detecting crypto issues in Python."""
    
    def __init__(self, file_path: str = None, taint_checker=None):
        self.file_path = file_path or "unknown"
        self.taint_checker = taint_checker
        self.findings = []
        self.has_secrets_import = False
        self.has_random_import = False
        self.security_var_names = set()  # Track security-sensitive variable names
        
    def visit_Import(self, node: ast.Import):
        """Track imports to understand available modules."""
        for alias in node.names:
            if 'secrets' in alias.name:
                self.has_secrets_import = True
            elif 'random' in alias.name:
                self.has_random_import = True
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Track from imports."""
        if node.module:
            if 'secrets' in node.module:
                self.has_secrets_import = True
            elif 'random' in node.module:
                self.has_random_import = True
        self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign):
        """Track assignments to identify security-sensitive variables."""
        # Track variable names that look security-sensitive
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id.lower()
                security_keywords = ['token', 'password', 'secret', 'key', 'auth', 'session', 
                                   'salt', 'nonce', 'pin', 'otp', 'code', 'api_key', 'uuid']
                if any(keyword in var_name for keyword in security_keywords):
                    self.security_var_names.add(target.id)
                    
                    # Check if using weak generation
                    self._check_value_generation(node.value, target.id, node.lineno, node.col_offset)
        
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Check for crypto and random function calls."""
        call_name = self._get_call_name(node)
        
        # Check if any arguments are tainted
        has_tainted_input = False
        if self.taint_checker:
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    if self.taint_checker(arg.id, node.lineno):
                        has_tainted_input = True
                        break
        
        # Pattern 1: insecure-random-python
        if self.has_random_import and 'random.' in call_name:
            random_functions = ['random', 'randint', 'choice', 'randbytes', 'randrange', 'getrandbits']
            if any(func in call_name for func in random_functions):
                # Check if used in security context
                if self._is_security_context(node) or has_tainted_input:
                    self.findings.append({
                        'line': node.lineno,
                        'column': node.col_offset,
                        'type': 'insecure_random_python',
                        'function': call_name,
                        'severity': 'CRITICAL',
                        'confidence': 0.95 if has_tainted_input else 0.85,
                        'message': f'Using {call_name} for {"tainted" if has_tainted_input else "security-sensitive"} value',
                        'hint': 'Use secrets module instead: secrets.token_hex() or secrets.token_urlsafe()'
                    })
        
        # Pattern 2: weak-crypto-algorithm
        weak_algorithms = {
            'md5': 'MD5',
            'sha1': 'SHA-1',
            'des': 'DES',
            'rc4': 'RC4'
        }
        
        for weak_algo, algo_name in weak_algorithms.items():
            if weak_algo in call_name.lower():
                # Check if it's not for file hashing
                if not self._is_file_hashing_context(node):
                    # Increase severity if tainted data is being hashed
                    severity = 'CRITICAL' if has_tainted_input else 'HIGH'
                    self.findings.append({
                        'line': node.lineno,
                        'column': node.col_offset,
                        'type': 'weak_crypto_algorithm',
                        'algorithm': algo_name,
                        'severity': severity,
                        'confidence': 0.90 if has_tainted_input else 0.80,
                        'message': f'Using weak cryptographic algorithm: {algo_name}{" with tainted input" if has_tainted_input else ""}',
                        'hint': 'Use SHA-256, SHA-3, or stronger algorithms'
                    })
        
        # Check for hashlib usage
        if 'hashlib.' in call_name:
            # Check the algorithm parameter
            if node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant):
                    algo = first_arg.value
                    if isinstance(algo, str) and algo.lower() in weak_algorithms:
                        self.findings.append({
                            'line': node.lineno,
                            'column': node.col_offset,
                            'type': 'weak_crypto_algorithm',
                            'algorithm': algo.upper(),
                            'severity': 'HIGH',
                            'confidence': 0.85,
                            'message': f'Using weak hash algorithm: {algo.upper()}',
                            'hint': 'Use hashlib.sha256() or stronger'
                        })
        
        self.generic_visit(node)
    
    def _check_value_generation(self, value_node: ast.AST, var_name: str, line: int, col: int):
        """Check how a security-sensitive value is generated."""
        # Pattern 3: predictable-token-generation
        
        # Check for timestamp-based generation
        if isinstance(value_node, ast.Call):
            call_name = self._get_call_name(value_node)
            
            # Timestamp patterns
            timestamp_patterns = ['time.time', 'datetime.now', 'timestamp', 'time.clock', 'time.perf_counter']
            if any(pattern in call_name for pattern in timestamp_patterns):
                self.findings.append({
                    'line': line,
                    'column': col,
                    'type': 'predictable_token_generation',
                    'variable': var_name,
                    'method': 'timestamp',
                    'severity': 'HIGH',
                    'confidence': 0.75,
                    'message': f'Predictable token generation using timestamp for {var_name}',
                    'hint': 'Use secrets.token_hex() or uuid.uuid4() for unpredictable tokens'
                })
            
            # Check for weak random
            if 'random.' in call_name and not 'secrets.' in call_name:
                self.findings.append({
                    'line': line,
                    'column': col,
                    'type': 'insecure_random_python',
                    'variable': var_name,
                    'severity': 'CRITICAL',
                    'confidence': 0.85,
                    'message': f'Security-sensitive variable {var_name} uses insecure random',
                    'hint': 'Use secrets module for security-sensitive values'
                })
        
        # Check for sequential/incremental patterns
        elif isinstance(value_node, ast.BinOp):
            if isinstance(value_node.op, ast.Add):
                # Check if it's counter++
                if isinstance(value_node.left, ast.Name):
                    if 'counter' in value_node.left.id.lower() or 'seq' in value_node.left.id.lower():
                        self.findings.append({
                            'line': line,
                            'column': col,
                            'type': 'predictable_token_generation',
                            'variable': var_name,
                            'method': 'sequential',
                            'severity': 'HIGH',
                            'confidence': 0.70,
                            'message': f'Sequential/incremental token generation for {var_name}',
                            'hint': 'Use cryptographically secure random generation'
                        })
    
    def _is_security_context(self, node: ast.AST) -> bool:
        """Check if the node is in a security-sensitive context."""
        # Check if assigned to security-sensitive variable
        parent = self._get_parent_assign(node)
        if parent:
            for target in parent.targets:
                if isinstance(target, ast.Name):
                    if target.id in self.security_var_names:
                        return True
                    # Check variable name
                    var_lower = target.id.lower()
                    security_keywords = ['token', 'password', 'secret', 'key', 'auth', 
                                       'session', 'salt', 'nonce', 'pin', 'otp']
                    if any(keyword in var_lower for keyword in security_keywords):
                        return True
        
        return False
    
    def _is_file_hashing_context(self, node: ast.AST) -> bool:
        """Check if crypto is used for file hashing (non-security)."""
        # Look for file/content/cache/checksum keywords nearby
        context_keywords = ['file', 'content', 'cache', 'etag', 'checksum', 'integrity']
        
        # Check parent context (simplified)
        parent = self._get_parent_assign(node)
        if parent:
            for target in parent.targets:
                if isinstance(target, ast.Name):
                    if any(keyword in target.id.lower() for keyword in context_keywords):
                        return True
        
        return False
    
    def _get_parent_assign(self, node: ast.AST) -> Optional[ast.Assign]:
        """Get parent assignment node (simplified - would need proper tree tracking)."""
        # This is a simplified version - in production would track parent nodes
        return None
    
    def _get_call_name(self, node: ast.Call) -> str:
        """Extract the name of a function call."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return '.'.join(reversed(parts))
        return ''


def _analyze_javascript_crypto(tree_wrapper: Dict[str, Any], file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Analyze JavaScript/TypeScript ESLint AST for crypto security issues."""
    findings = []
    
    ast = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    
    if not ast or not isinstance(ast, dict):
        return findings
    
    # Track security-sensitive variables
    security_vars = set()
    
    def traverse_ast(node: Dict[str, Any], parent: Dict[str, Any] = None):
        nonlocal security_vars
        
        if not isinstance(node, dict):
            return
        
        node_type = node.get("type")
        
        # Track security-sensitive variable declarations
        if node_type == "VariableDeclarator":
            var_id = node.get("id", {})
            var_init = node.get("init", {})
            
            if var_id.get("type") == "Identifier":
                var_name = var_id.get("name", "").lower()
                security_keywords = ['token', 'password', 'secret', 'key', 'auth', 'session',
                                   'salt', 'nonce', 'pin', 'otp', 'code', 'api', 'uuid', 'guid']
                
                if any(keyword in var_name for keyword in security_keywords):
                    security_vars.add(var_id.get("name"))
                    
                    # Check how it's initialized
                    _check_js_value_generation(var_init, var_id.get("name"), node, findings, content)
        
        # Check for crypto operations
        if node_type == "CallExpression":
            callee = node.get("callee", {})
            call_text = _extract_call_text(callee, content)
            loc = node.get("loc", {}).get("start", {})
            line_num = loc.get("line", 0)
            
            # Check if any arguments are tainted
            has_tainted_input = False
            if taint_checker and line_num > 0:
                args = node.get("arguments", [])
                for arg in args:
                    if arg.get("type") == "Identifier":
                        if taint_checker(arg.get("name"), line_num):
                            has_tainted_input = True
                            break
            
            # Pattern 1: insecure-random-for-security (JavaScript)
            if 'Math.random' in call_text:
                # Check if in security context
                if _is_js_security_context(node, parent, security_vars, content) or has_tainted_input:
                    findings.append({
                        'line': line_num,
                        'column': loc.get("column", 0),
                        'type': 'insecure_random_javascript',
                        'function': 'Math.random()',
                        'severity': 'CRITICAL',
                        'confidence': 0.95 if has_tainted_input else 0.90,
                        'message': f'Math.random() used for {"tainted" if has_tainted_input else "security-sensitive"} value',
                        'hint': 'Use crypto.randomBytes() or crypto.getRandomValues()'
                    })
            
            # Pattern 2: weak-crypto-algorithm
            weak_patterns = {
                'createHash("md5")': 'MD5',
                'createHash(\'md5\')': 'MD5',
                'createHash("sha1")': 'SHA-1',
                'createHash(\'sha1\')': 'SHA-1',
                'CryptoJS.MD5': 'MD5',
                'CryptoJS.SHA1': 'SHA-1',
                'CryptoJS.DES': 'DES',
                'CryptoJS.RC4': 'RC4'
            }
            
            node_text = _extract_node_text(node, content)
            for pattern, algo_name in weak_patterns.items():
                if pattern in node_text:
                    # Check it's not file hashing
                    if not _is_file_hashing_js(node, parent, content):
                        # Increase severity if tainted data is being hashed
                        severity = 'CRITICAL' if has_tainted_input else 'HIGH'
                        findings.append({
                            'line': line_num,
                            'column': loc.get("column", 0),
                            'type': 'weak_crypto_algorithm',
                            'algorithm': algo_name,
                            'severity': severity,
                            'confidence': 0.90 if has_tainted_input else 0.80,
                            'message': f'Using weak cryptographic algorithm: {algo_name}{" with tainted input" if has_tainted_input else ""}',
                            'hint': 'Use SHA-256 or stronger: createHash("sha256")'
                        })
            
            # Pattern 3: predictable-token-generation
            timestamp_patterns = ['Date.now()', 'Date.getTime()', 'new Date().getTime()', 'timestamp']
            if any(pattern in call_text for pattern in timestamp_patterns):
                # Check if assigned to security variable
                if parent and parent.get("type") == "VariableDeclarator":
                    var_id = parent.get("id", {})
                    if var_id.get("type") == "Identifier":
                        if var_id.get("name") in security_vars:
                            loc = node.get("loc", {}).get("start", {})
                            findings.append({
                                'line': loc.get("line", 0),
                                'column': loc.get("column", 0),
                                'type': 'predictable_token_generation',
                                'variable': var_id.get("name"),
                                'method': 'timestamp',
                                'severity': 'HIGH',
                                'confidence': 0.75,
                                'message': f'Predictable token using timestamp: {var_id.get("name")}',
                                'hint': 'Use crypto.randomUUID() or crypto.randomBytes()'
                            })
        
        # Check for incremental patterns
        if node_type == "UpdateExpression":
            argument = node.get("argument", {})
            if argument.get("type") == "Identifier":
                var_name = argument.get("name", "")
                if var_name in security_vars or 'counter' in var_name.lower():
                    # Check if this is being assigned to a security var
                    if parent and parent.get("type") == "AssignmentExpression":
                        left = parent.get("left", {})
                        if left.get("type") == "Identifier" and left.get("name") in security_vars:
                            loc = node.get("loc", {}).get("start", {})
                            findings.append({
                                'line': loc.get("line", 0),
                                'column': loc.get("column", 0),
                                'type': 'predictable_token_generation',
                                'variable': left.get("name"),
                                'method': 'sequential',
                                'severity': 'HIGH',
                                'confidence': 0.70,
                                'message': 'Sequential/incremental token generation',
                                'hint': 'Use cryptographically secure random generation'
                            })
        
        # Recursively traverse
        for key, value in node.items():
            if key in ["type", "loc", "range", "raw", "value"]:
                continue
            
            if isinstance(value, dict):
                traverse_ast(value, node)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        traverse_ast(item, node)
    
    # Start traversal
    if ast.get("type") == "Program":
        traverse_ast(ast)
    
    return findings


def _check_js_value_generation(init_node: Dict[str, Any], var_name: str, 
                               parent_node: Dict[str, Any], findings: List[Dict[str, Any]], 
                               content: str):
    """Check how a JavaScript security-sensitive value is generated."""
    if not init_node:
        return
    
    init_text = _extract_node_text(init_node, content)
    loc = parent_node.get("loc", {}).get("start", {})
    
    # Check for Math.random()
    if 'Math.random' in init_text:
        findings.append({
            'line': loc.get("line", 0),
            'column': loc.get("column", 0),
            'type': 'insecure_random_javascript',
            'variable': var_name,
            'severity': 'CRITICAL',
            'confidence': 0.90,
            'message': f'Security variable {var_name} uses Math.random()',
            'hint': 'Use crypto.randomBytes() or crypto.getRandomValues()'
        })
    
    # Check for timestamp
    elif any(ts in init_text for ts in ['Date.now()', 'getTime()', 'timestamp']):
        findings.append({
            'line': loc.get("line", 0),
            'column': loc.get("column", 0),
            'type': 'predictable_token_generation',
            'variable': var_name,
            'method': 'timestamp',
            'severity': 'HIGH',
            'confidence': 0.75,
            'message': f'Predictable token generation for {var_name}',
            'hint': 'Use crypto.randomUUID() or crypto.randomBytes()'
        })


def _is_js_security_context(node: Dict[str, Any], parent: Dict[str, Any], 
                            security_vars: Set[str], content: str) -> bool:
    """Check if JavaScript node is in security context."""
    # Check if parent is assignment to security variable
    if parent and parent.get("type") == "VariableDeclarator":
        var_id = parent.get("id", {})
        if var_id.get("type") == "Identifier":
            if var_id.get("name") in security_vars:
                return True
            
            # Check variable name
            var_lower = var_id.get("name", "").lower()
            security_keywords = ['token', 'password', 'secret', 'key', 'auth', 'session']
            if any(keyword in var_lower for keyword in security_keywords):
                return True
    
    # Check surrounding context
    node_text = _extract_node_text(node, content).lower()
    return any(keyword in node_text for keyword in ['token', 'secret', 'password', 'auth'])


def _is_file_hashing_js(node: Dict[str, Any], parent: Dict[str, Any], content: str) -> bool:
    """Check if crypto is used for file hashing (non-security)."""
    context_keywords = ['file', 'content', 'cache', 'etag', 'checksum', 'integrity']
    
    # Check parent variable name
    if parent and parent.get("type") == "VariableDeclarator":
        var_id = parent.get("id", {})
        if var_id.get("type") == "Identifier":
            var_name = var_id.get("name", "").lower()
            if any(keyword in var_name for keyword in context_keywords):
                return True
    
    return False


def _extract_call_text(callee: Dict[str, Any], content: str) -> str:
    """Extract call text from ESLint AST node."""
    if callee.get("type") == "Identifier":
        return callee.get("name", "")
    elif callee.get("type") == "MemberExpression":
        parts = []
        current = callee
        
        while current and isinstance(current, dict):
            if current.get("type") == "MemberExpression":
                prop = current.get("property", {})
                if prop.get("type") == "Identifier":
                    parts.append(prop.get("name", ""))
                current = current.get("object", {})
            elif current.get("type") == "Identifier":
                parts.append(current.get("name", ""))
                break
            else:
                break
        
        return '.'.join(reversed(parts))
    
    return ""


def _extract_node_text(node: Dict[str, Any], content: str) -> str:
    """Extract text from node using range if available."""
    if not node or not content:
        return ""
    
    range_info = node.get("range")
    if range_info and isinstance(range_info, list) and len(range_info) == 2:
        start, end = range_info
        if 0 <= start < end <= len(content):
            return content[start:end]
    
    return ""


def _analyze_tree_sitter_crypto(tree_wrapper: Dict[str, Any], file_path: str = None, taint_checker=None) -> List[Dict[str, Any]]:
    """Analyze tree-sitter AST (simplified implementation)."""
    # Would need tree-sitter specific implementation
    # For now, return empty list
    return []