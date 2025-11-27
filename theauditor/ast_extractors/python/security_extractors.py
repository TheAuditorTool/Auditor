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
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext

from ..base import get_node_name

logger = logging.getLogger(__name__)


AUTH_DECORATORS = {
    "login_required",
    "permission_required",
    "requires_auth",
    "authenticated",
    "staff_member_required",
    "superuser_required",
}

PASSWORD_HASH_LIBS = {
    "bcrypt",
    "pbkdf2",
    "argon2",
    "scrypt",
    "hashlib",
}

JWT_FUNCTIONS = {
    "encode",
    "decode",
    "sign",
    "verify",
}

DANGEROUS_FUNCTIONS = {
    "eval",
    "exec",
    "compile",
    "__import__",
}

# SQL method names for query extraction
SQL_METHODS = frozenset([
    "execute",
    "executemany",
    "executescript",
    "query",
    "raw",
    "exec_driver_sql",
    "select",
    "insert",
    "update",
    "delete",
])

# JWT operation methods
JWT_ENCODE_METHODS = frozenset(["encode"])
JWT_DECODE_METHODS = frozenset(["decode"])


def extract_auth_decorators(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return auth_patterns

    for node in context.walk_tree():
        if not isinstance(node, ast.FunctionDef):
            continue

        for dec in node.decorator_list:
            decorator_name = get_node_name(dec)

            is_auth = False
            for auth_dec in AUTH_DECORATORS:
                if auth_dec in decorator_name.lower():
                    is_auth = True
                    break

            if is_auth:
                permissions = None
                if isinstance(dec, ast.Call) and dec.args:
                    first_arg = dec.args[0]
                    if (
                        isinstance(first_arg, ast.Constant)
                        or isinstance(first_arg, ast.Constant)
                        and isinstance(first_arg.value, str)
                    ):
                        permissions = first_arg.value

                auth_patterns.append(
                    {
                        "line": node.lineno,
                        "function_name": node.name,
                        "decorator_name": decorator_name,
                        "permissions": permissions,
                    }
                )

    return auth_patterns


def extract_password_hashing(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return hash_patterns

    for node in context.walk_tree():
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        hash_lib = None
        hash_method = None
        is_weak = False

        for lib in PASSWORD_HASH_LIBS:
            if lib in func_name.lower():
                hash_lib = lib
                break

        if "." in func_name:
            parts = func_name.split(".")
            hash_method = parts[-1]

        if any(weak in func_name.lower() for weak in ["md5", "sha1", "crc32"]):
            is_weak = True
            hash_lib = "weak"

        if hash_lib or is_weak:
            has_hardcoded_value = False
            if node.args:
                for arg in node.args:
                    if isinstance(arg, ast.Constant):
                        has_hardcoded_value = True

            hash_patterns.append(
                {
                    "line": node.lineno,
                    "hash_library": hash_lib,
                    "hash_method": hash_method,
                    "is_weak": is_weak,
                    "has_hardcoded_value": has_hardcoded_value,
                }
            )

    return hash_patterns


def extract_sql_injection_patterns(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return sql_patterns

    for node in context.walk_tree():
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        if not any(
            db_method in func_name.lower() for db_method in ["execute", "executemany", "raw"]
        ):
            continue

        if not node.args:
            continue

        query_arg = node.args[0]
        is_vulnerable = False
        interpolation_type = None

        if isinstance(query_arg, ast.JoinedStr):
            is_vulnerable = True
            interpolation_type = "f-string"

        elif isinstance(query_arg, ast.BinOp) and isinstance(query_arg.op, ast.Mod):
            is_vulnerable = True
            interpolation_type = "%-formatting"

        elif isinstance(query_arg, ast.Call):
            query_func = get_node_name(query_arg.func)
            if "format" in query_func:
                is_vulnerable = True
                interpolation_type = ".format()"

        if is_vulnerable:
            sql_patterns.append(
                {
                    "line": node.lineno,
                    "db_method": func_name,
                    "interpolation_type": interpolation_type,
                    "is_vulnerable": is_vulnerable,
                }
            )

    return sql_patterns


def extract_command_injection_patterns(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return cmd_patterns

    for node in context.walk_tree():
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        if "subprocess" in func_name.lower():
            shell_true = False
            for keyword in node.keywords:
                if keyword.arg == "shell" and (
                    isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                    or isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ):
                    shell_true = True

            if shell_true:
                cmd_patterns.append(
                    {
                        "line": node.lineno,
                        "function": func_name,
                        "shell_true": shell_true,
                        "is_vulnerable": True,
                    }
                )

        elif func_name in ["os.system", "os.popen", "commands.getoutput"]:
            cmd_patterns.append(
                {
                    "line": node.lineno,
                    "function": func_name,
                    "shell_true": True,
                    "is_vulnerable": True,
                }
            )

    return cmd_patterns


def extract_path_traversal_patterns(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return path_patterns

    for node in context.walk_tree():
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        if func_name in ["open", "pathlib.Path"]:
            has_concatenation = False
            if node.args:
                arg = node.args[0]
                if isinstance(arg, (ast.BinOp, ast.JoinedStr)):
                    has_concatenation = True

            path_patterns.append(
                {
                    "line": node.lineno,
                    "function": func_name,
                    "has_concatenation": has_concatenation,
                    "is_vulnerable": has_concatenation,
                }
            )

        elif "path.join" in func_name:
            path_patterns.append(
                {
                    "line": node.lineno,
                    "function": func_name,
                    "has_concatenation": False,
                    "is_vulnerable": False,
                }
            )

    return path_patterns


def extract_dangerous_eval_exec(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return dangerous_patterns

    for node in context.walk_tree():
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        is_dangerous = False
        for danger_func in DANGEROUS_FUNCTIONS:
            if danger_func in func_name.lower():
                is_dangerous = True
                break

        if is_dangerous:
            is_constant_input = False
            if node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant):
                    is_constant_input = True

            dangerous_patterns.append(
                {
                    "line": node.lineno,
                    "function": func_name,
                    "is_constant_input": is_constant_input,
                    "is_critical": not is_constant_input,
                }
            )

    return dangerous_patterns


def extract_crypto_operations(context: FileContext) -> list[dict[str, Any]]:
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
    if not isinstance(context.tree, ast.AST):
        return crypto_patterns

    for node in context.walk_tree():
        if not isinstance(node, ast.Call):
            continue

        func_name = get_node_name(node.func)

        if not any(crypto_lib in func_name for crypto_lib in ["Crypto", "cryptography", "cipher"]):
            continue

        algorithm = None
        mode = None

        if "AES" in func_name:
            algorithm = "AES"
        elif "DES" in func_name:
            algorithm = "DES"
        elif "RSA" in func_name:
            algorithm = "RSA"
        elif "RC4" in func_name:
            algorithm = "RC4"

        if "ECB" in func_name:
            mode = "ECB"
        elif "CBC" in func_name:
            mode = "CBC"
        elif "GCM" in func_name:
            mode = "GCM"

        is_weak = algorithm in ["DES", "RC4"] or mode == "ECB"

        has_hardcoded_key = False
        if node.args:
            for arg in node.args:
                if isinstance(arg, ast.Constant):
                    has_hardcoded_key = True

        if algorithm:
            crypto_patterns.append(
                {
                    "line": node.lineno,
                    "algorithm": algorithm,
                    "mode": mode,
                    "is_weak": is_weak,
                    "has_hardcoded_key": has_hardcoded_key,
                }
            )

    return crypto_patterns


def extract_sql_queries(context: FileContext) -> list[dict[str, Any]]:
    """Extract SQL queries from database execution calls using AST.

    Detects SQL queries in:
    - sqlite3.execute()
    - psycopg2.execute()
    - SQLAlchemy session.execute()
    - Django ORM .raw()

    Returns:
        List of SQL query dicts with command, tables, and source info
    """
    from theauditor.indexer.extractors.sql import parse_sql_query

    queries = []
    if not isinstance(context.tree, ast.AST):
        return queries

    for node in context.walk_tree():
        if not isinstance(node, ast.Call):
            continue

        method_name = None
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr

        if method_name not in SQL_METHODS:
            continue

        if not node.args:
            continue

        first_arg = node.args[0]

        query_text = None
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            query_text = first_arg.value

        if not query_text:
            continue

        parsed = parse_sql_query(query_text)
        if not parsed:
            continue

        command, tables = parsed

        extraction_source = "manual"
        if "test" in context.file_path.lower():
            extraction_source = "test_fixture"
        elif "migration" in context.file_path.lower():
            extraction_source = "migration"

        queries.append(
            {
                "line": node.lineno,
                "query_text": query_text[:1000],
                "command": command,
                "tables": tables,
                "extraction_source": extraction_source,
            }
        )

    return queries


def extract_jwt_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract JWT patterns from PyJWT library calls using AST.

    NO REGEX. This uses Python AST analysis to detect JWT library usage.

    Detects:
    - jwt.encode() - Token signing
    - jwt.decode() - Token validation
    - Hardcoded secrets (security risk)
    - Weak algorithms

    Returns:
        List of JWT pattern dicts with type, secret_type, and algorithm
    """
    patterns = []
    if not isinstance(context.tree, ast.AST):
        return patterns

    for node in context.walk_tree():
        if not isinstance(node, ast.Call):
            continue

        method_name = None
        is_jwt_call = False

        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr

            if isinstance(node.func.value, ast.Name) and node.func.value.id == "jwt":
                is_jwt_call = True

        if not is_jwt_call or not method_name:
            continue

        pattern_type = None
        if method_name in JWT_ENCODE_METHODS:
            pattern_type = "jwt_sign"
        elif method_name in JWT_DECODE_METHODS:
            pattern_type = "jwt_decode"

        if not pattern_type:
            continue

        line = node.lineno

        if pattern_type == "jwt_sign":
            secret_node = None
            algorithm = "HS256"

            if len(node.args) >= 2:
                secret_node = node.args[1]

            for keyword in node.keywords:
                if (keyword.arg == "algorithm" and
                    isinstance(keyword.value, ast.Constant)):
                    algorithm = keyword.value.value

            secret_type = "unknown"
            if secret_node:
                if isinstance(secret_node, ast.Constant):
                    secret_type = "hardcoded"
                elif isinstance(secret_node, ast.Subscript):
                    if isinstance(secret_node.value, ast.Attribute):
                        if (hasattr(secret_node.value, "attr") and
                            secret_node.value.attr == "environ"):
                            secret_type = "environment"
                    elif (isinstance(secret_node.value, ast.Name) and
                        secret_node.value.id in ["config", "settings", "secrets"]):
                        secret_type = "config"
                elif isinstance(secret_node, ast.Call):
                    if isinstance(secret_node.func, ast.Attribute):
                        if secret_node.func.attr == "getenv":
                            secret_type = "environment"
                    elif (isinstance(secret_node.func, ast.Name) and
                        secret_node.func.id == "getenv"):
                        secret_type = "environment"
                elif isinstance(secret_node, ast.Attribute):
                    if (isinstance(secret_node.value, ast.Name) and
                        secret_node.value.id in ["config", "settings", "secrets"]):
                        secret_type = "config"
                elif isinstance(secret_node, ast.Name):
                    secret_type = "variable"

            full_match = "jwt.encode(...)"

            patterns.append(
                {
                    "line": line,
                    "type": pattern_type,
                    "full_match": full_match,
                    "secret_type": secret_type,
                    "algorithm": algorithm,
                }
            )

        elif pattern_type == "jwt_decode":
            algorithm = None

            for keyword in node.keywords:
                if (keyword.arg == "algorithms" and
                    isinstance(keyword.value, ast.List) and
                    keyword.value.elts):
                    first_algo = keyword.value.elts[0]
                    if isinstance(first_algo, ast.Constant):
                        algorithm = first_algo.value

            full_match = "jwt.decode(...)"

            patterns.append(
                {
                    "line": line,
                    "type": pattern_type,
                    "full_match": full_match,
                    "secret_type": None,
                    "algorithm": algorithm,
                }
            )

    return patterns
