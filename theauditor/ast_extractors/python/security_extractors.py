"""Python security pattern extractors - OWASP Top 10 focus.

This module contains extraction logic for security-critical patterns:
- Authentication decorators
- Password hashing
- JWT operations
- SQL injection patterns
- Command injection
- Path traversal
- Dangerous eval/exec
- Cryptography operations

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
# Security Pattern Constants
# ============================================================================

AUTH_DECORATORS = {
    'login_required',
    'permission_required',
    'requires_auth',
    'authenticated',
    'staff_member_required',
    'superuser_required',
}

PASSWORD_HASH_LIBS = {
    'bcrypt',
    'pbkdf2',
    'argon2',
    'scrypt',
    'hashlib',
}

JWT_FUNCTIONS = {
    'encode',
    'decode',
    'sign',
    'verify',
}

DANGEROUS_FUNCTIONS = {
    'eval',
    'exec',
    'compile',
    '__import__',
}


# ============================================================================
# Security Extractors
# ============================================================================

def extract_auth_decorators(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract authentication and authorization decorators.

    Detects:
    - @login_required
    - @permission_required
    - @requires_auth
    - Custom auth decorators

    Security relevance:
    - Missing auth decorators = unauthorized access
    - Functions without auth = attack surface
    - Inconsistent auth patterns = security gaps
    """
    auth_patterns = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return auth_patterns

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check decorators for auth patterns
        for dec in node.decorator_list:
            decorator_name = get_node_name(dec)

            # Check if decorator matches known auth patterns
            is_auth = False
            for auth_dec in AUTH_DECORATORS:
                if auth_dec in decorator_name.lower():
                    is_auth = True
                    break

            if is_auth:
                # Extract permissions if present
                permissions = None
                if isinstance(dec, ast.Call) and dec.args:
                    first_arg = dec.args[0]
                    if isinstance(first_arg, ast.Constant):
                        permissions = first_arg.value
                    elif isinstance(first_arg, ast.Str):
                        permissions = first_arg.s

                auth_patterns.append({
                    "line": node.lineno,
                    "function_name": node.name,
                    "decorator_name": decorator_name,
                    "permissions": permissions,
                })

    return auth_patterns


def extract_password_hashing(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract password hashing operations.

    Detects:
    - bcrypt.hashpw()
    - pbkdf2_hmac()
    - argon2.hash()
    - Weak hashing (md5, sha1)

    Security relevance:
    - Weak hashing = credential theft
    - Missing salt = rainbow table attacks
    - Hardcoded passwords = critical vulnerability
    """
    hash_patterns = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return hash_patterns

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        # Check for password hashing libraries
        hash_lib = None
        hash_method = None
        is_weak = False

        for lib in PASSWORD_HASH_LIBS:
            if lib in func_name.lower():
                hash_lib = lib
                break

        # Extract method name
        if '.' in func_name:
            parts = func_name.split('.')
            hash_method = parts[-1]

        # Check for weak hashing
        if any(weak in func_name.lower() for weak in ['md5', 'sha1', 'crc32']):
            is_weak = True
            hash_lib = 'weak'

        if hash_lib or is_weak:
            # Check for hardcoded password
            has_hardcoded_value = False
            if node.args:
                for arg in node.args:
                    if isinstance(arg, (ast.Constant, ast.Str)):
                        has_hardcoded_value = True

            hash_patterns.append({
                "line": node.lineno,
                "hash_library": hash_lib,
                "hash_method": hash_method,
                "is_weak": is_weak,
                "has_hardcoded_value": has_hardcoded_value,
            })

    return hash_patterns


def extract_jwt_operations(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract JWT (JSON Web Token) operations.

    Detects:
    - jwt.encode()
    - jwt.decode()
    - Token verification
    - Algorithm specification

    Security relevance:
    - Missing verification = token forgery
    - Weak algorithms (HS256 with public key)
    - None algorithm = critical bypass
    """
    jwt_patterns = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return jwt_patterns

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        # Check if this is a JWT operation
        if 'jwt' not in func_name.lower():
            continue

        operation = None
        for jwt_func in JWT_FUNCTIONS:
            if jwt_func in func_name.lower():
                operation = jwt_func
                break

        if not operation:
            continue

        # Extract algorithm if specified
        algorithm = None
        verify = None

        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == 'algorithm':
                    if isinstance(keyword.value, ast.Constant):
                        algorithm = keyword.value.value
                    elif isinstance(keyword.value, ast.Str):
                        algorithm = keyword.value.s
                elif keyword.arg in ['verify', 'verify_signature']:
                    if isinstance(keyword.value, ast.Constant):
                        verify = keyword.value.value
                    elif isinstance(keyword.value, ast.NameConstant):
                        verify = keyword.value.value

        jwt_patterns.append({
            "line": node.lineno,
            "operation": operation,
            "algorithm": algorithm,
            "verify": verify,
            "is_insecure": algorithm == 'none' or verify is False,
        })

    return jwt_patterns


def extract_sql_injection_patterns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract SQL injection vulnerability patterns.

    Detects:
    - String formatting in SQL queries
    - f-strings in SQL
    - % formatting in SQL
    - .format() in SQL

    Security relevance:
    - String interpolation in SQL = SQL injection
    - Missing parameterization = critical vulnerability
    - User input in queries = attack vector
    """
    sql_patterns = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return sql_patterns

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        # Check if this is a database execution method
        if not any(db_method in func_name.lower() for db_method in ['execute', 'executemany', 'raw']):
            continue

        # Check if query is passed as argument
        if not node.args:
            continue

        query_arg = node.args[0]
        is_vulnerable = False
        interpolation_type = None

        # Check for f-string (JoinedStr)
        if isinstance(query_arg, ast.JoinedStr):
            is_vulnerable = True
            interpolation_type = 'f-string'

        # Check for % formatting (BinOp with Mod)
        elif isinstance(query_arg, ast.BinOp) and isinstance(query_arg.op, ast.Mod):
            is_vulnerable = True
            interpolation_type = '%-formatting'

        # Check for .format() method call
        elif isinstance(query_arg, ast.Call):
            query_func = get_node_name(query_arg.func)
            if 'format' in query_func:
                is_vulnerable = True
                interpolation_type = '.format()'

        if is_vulnerable:
            sql_patterns.append({
                "line": node.lineno,
                "db_method": func_name,
                "interpolation_type": interpolation_type,
                "is_vulnerable": is_vulnerable,
            })

    return sql_patterns


def extract_command_injection_patterns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract command injection vulnerability patterns.

    Detects:
    - subprocess.call/run with shell=True
    - os.system() calls
    - os.popen() calls
    - eval() on shell commands

    Security relevance:
    - shell=True with user input = command injection
    - os.system = always vulnerable
    - Command string concatenation = critical risk
    """
    cmd_patterns = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return cmd_patterns

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        # Check for subprocess calls
        if 'subprocess' in func_name.lower():
            shell_true = False
            for keyword in node.keywords:
                if keyword.arg == 'shell':
                    if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        shell_true = True
                    elif isinstance(keyword.value, ast.NameConstant) and keyword.value.value is True:
                        shell_true = True

            if shell_true:
                cmd_patterns.append({
                    "line": node.lineno,
                    "function": func_name,
                    "shell_true": shell_true,
                    "is_vulnerable": True,
                })

        # Check for os.system/popen
        elif func_name in ['os.system', 'os.popen', 'commands.getoutput']:
            cmd_patterns.append({
                "line": node.lineno,
                "function": func_name,
                "shell_true": True,  # Always uses shell
                "is_vulnerable": True,
            })

    return cmd_patterns


def extract_path_traversal_patterns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract path traversal vulnerability patterns.

    Detects:
    - open() with user input
    - Path concatenation with user input
    - Missing path validation
    - os.path.join with untrusted input

    Security relevance:
    - Unvalidated paths = arbitrary file access
    - Path traversal (../) = directory escape
    - Reading arbitrary files = information disclosure
    """
    path_patterns = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return path_patterns

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        # Check for file operations
        if func_name in ['open', 'pathlib.Path']:
            # Check if path uses string concatenation
            has_concatenation = False
            if node.args:
                arg = node.args[0]
                if isinstance(arg, (ast.BinOp, ast.JoinedStr)):
                    has_concatenation = True

            path_patterns.append({
                "line": node.lineno,
                "function": func_name,
                "has_concatenation": has_concatenation,
                "is_vulnerable": has_concatenation,
            })

        # Check for os.path.join
        elif 'path.join' in func_name:
            path_patterns.append({
                "line": node.lineno,
                "function": func_name,
                "has_concatenation": False,
                "is_vulnerable": False,  # os.path.join is safe but still track it
            })

    return path_patterns


def extract_dangerous_eval_exec(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract dangerous eval/exec/compile calls.

    Detects:
    - eval() with user input
    - exec() calls
    - compile() calls
    - __import__() dynamic imports

    Security relevance:
    - eval/exec = arbitrary code execution
    - Most critical vulnerability class
    - No safe use of eval with untrusted input
    """
    dangerous_patterns = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return dangerous_patterns

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        # Check for dangerous functions
        is_dangerous = False
        for danger_func in DANGEROUS_FUNCTIONS:
            if danger_func in func_name.lower():
                is_dangerous = True
                break

        if is_dangerous:
            # Check if input is a constant (less dangerous)
            is_constant_input = False
            if node.args:
                arg = node.args[0]
                if isinstance(arg, (ast.Constant, ast.Str, ast.Num)):
                    is_constant_input = True

            dangerous_patterns.append({
                "line": node.lineno,
                "function": func_name,
                "is_constant_input": is_constant_input,
                "is_critical": not is_constant_input,
            })

    return dangerous_patterns


def extract_crypto_operations(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract cryptography operations and weak algorithms.

    Detects:
    - AES/DES encryption
    - RSA key generation
    - Weak algorithms (DES, RC4)
    - Hardcoded keys
    - ECB mode usage

    Security relevance:
    - Weak algorithms = broken crypto
    - ECB mode = pattern leakage
    - Hardcoded keys = key compromise
    - Small key sizes = brute force
    """
    crypto_patterns = []
    actual_tree = tree.get("tree")
    if not isinstance(actual_tree, ast.AST):
        return crypto_patterns

    for node in ast.walk(actual_tree):
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        # Check for crypto library usage
        if not any(crypto_lib in func_name for crypto_lib in ['Crypto', 'cryptography', 'cipher']):
            continue

        # Extract algorithm
        algorithm = None
        mode = None
        key_size = None

        if 'AES' in func_name:
            algorithm = 'AES'
        elif 'DES' in func_name:
            algorithm = 'DES'
        elif 'RSA' in func_name:
            algorithm = 'RSA'
        elif 'RC4' in func_name:
            algorithm = 'RC4'

        # Check for mode
        if 'ECB' in func_name:
            mode = 'ECB'
        elif 'CBC' in func_name:
            mode = 'CBC'
        elif 'GCM' in func_name:
            mode = 'GCM'

        # Check for weak algorithms
        is_weak = algorithm in ['DES', 'RC4'] or mode == 'ECB'

        # Check for hardcoded key
        has_hardcoded_key = False
        if node.args:
            for arg in node.args:
                if isinstance(arg, (ast.Constant, ast.Str, ast.Bytes)):
                    has_hardcoded_key = True

        if algorithm:
            crypto_patterns.append({
                "line": node.lineno,
                "algorithm": algorithm,
                "mode": mode,
                "is_weak": is_weak,
                "has_hardcoded_key": has_hardcoded_key,
            })

    return crypto_patterns
