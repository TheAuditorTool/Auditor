"""Python AST extraction implementations.

This module contains all Python-specific extraction logic using the built-in ast module.
"""

import ast
from typing import Any, List, Dict, Optional

from .base import (
    get_node_name,
    extract_vars_from_expr,
    find_containing_function_python
)


def extract_python_functions(tree: Dict, parser_self) -> List[Dict]:
    """Extract function definitions from Python AST.
    
    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance for accessing methods
        
    Returns:
        List of function info dictionaries
    """
    functions = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return functions
    
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "async": isinstance(node, ast.AsyncFunctionDef),
                "args": [arg.arg for arg in node.args.args],
            })
    
    return functions


def extract_python_classes(tree: Dict, parser_self) -> List[Dict]:
    """Extract class definitions from Python AST."""
    classes = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return classes
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.ClassDef):
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "column": node.col_offset,
                "bases": [get_node_name(base) for base in node.bases],
            })
    
    return classes


def extract_python_calls(tree: Dict, parser_self) -> List[Dict]:
    """Extract function calls from Python AST."""
    calls = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return calls
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Call):
            func_name = get_node_name(node.func)
            if func_name:
                calls.append({
                    "name": func_name,
                    "line": node.lineno,
                    "column": node.col_offset,
                    "args_count": len(node.args),
                })
    
    return calls


def extract_python_imports(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract import statements from Python AST."""
    imports = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return imports
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "source": "import",
                    "target": alias.name,
                    "type": "import",
                    "line": node.lineno,
                    "as": alias.asname,
                    "specifiers": []
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append({
                    "source": "from",
                    "target": module,
                    "type": "from",
                    "line": node.lineno,
                    "imported": alias.name,
                    "as": alias.asname,
                    "specifiers": [alias.name]
                })
    
    return imports


def extract_python_exports(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract export statements from Python AST.
    
    In Python, all top-level functions, classes, and assignments are "exported".
    """
    exports = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return exports
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.FunctionDef) and node.col_offset == 0:
            exports.append({
                "name": node.name,
                "type": "function",
                "line": node.lineno,
                "default": False
            })
        elif isinstance(node, ast.ClassDef) and node.col_offset == 0:
            exports.append({
                "name": node.name,
                "type": "class",
                "line": node.lineno,
                "default": False
            })
        elif isinstance(node, ast.Assign) and node.col_offset == 0:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    exports.append({
                        "name": target.id,
                        "type": "variable",
                        "line": node.lineno,
                        "default": False
                    })
    
    return exports


def extract_python_assignments(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract variable assignments from Python AST for data flow analysis."""
    import os
    assignments = []
    actual_tree = tree.get("tree")
    
    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        print(f"[AST_DEBUG] extract_python_assignments called", file=sys.stderr)
    
    if not actual_tree:
        return assignments
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Assign):
            # Extract target variable(s)
            for target in node.targets:
                target_var = get_node_name(target)
                source_expr = ast.unparse(node.value) if hasattr(ast, "unparse") else str(node.value)
                
                # Find containing function
                in_function = find_containing_function_python(actual_tree, node.lineno)
                
                # CRITICAL FIX: Check if this is a class instantiation
                # BeautifulSoup(html) is ast.Call with func.id = "BeautifulSoup"
                is_instantiation = isinstance(node.value, ast.Call)
                
                assignments.append({
                    "target_var": target_var,
                    "source_expr": source_expr,
                    "line": node.lineno,
                    "in_function": in_function or "global",
                    "source_vars": extract_vars_from_expr(node.value),
                    "is_instantiation": is_instantiation  # Track for taint analysis
                })
        
        elif isinstance(node, ast.AnnAssign) and node.value:
            # Handle annotated assignments (x: int = 5)
            target_var = get_node_name(node.target)
            source_expr = ast.unparse(node.value) if hasattr(ast, "unparse") else str(node.value)
            
            in_function = find_containing_function_python(actual_tree, node.lineno)
            
            assignments.append({
                "target_var": target_var,
                "source_expr": source_expr,
                "line": node.lineno,
                "in_function": in_function or "global",
                "source_vars": extract_vars_from_expr(node.value)
            })
    
    return assignments


def extract_python_function_params(tree: Dict, parser_self) -> Dict[str, List[str]]:
    """Extract function definitions and their parameter names from Python AST."""
    func_params = {}
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return func_params
    
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = [arg.arg for arg in node.args.args]
            func_params[node.name] = params
    
    return func_params


def extract_python_calls_with_args(tree: Dict, function_params: Dict[str, List[str]], parser_self) -> List[Dict[str, Any]]:
    """Extract Python function calls with argument mapping."""
    calls = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return calls
    
    # Find containing function for each call
    function_ranges = {}
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)
    
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Call):
            func_name = get_node_name(node.func)
            
            # Find caller function
            caller_function = "global"
            for fname, (start, end) in function_ranges.items():
                if start <= node.lineno <= end:
                    caller_function = fname
                    break
            
            # Get callee parameters
            callee_params = function_params.get(func_name.split(".")[-1], [])
            
            # Map arguments to parameters
            for i, arg in enumerate(node.args):
                arg_expr = ast.unparse(arg) if hasattr(ast, "unparse") else str(arg)
                param_name = callee_params[i] if i < len(callee_params) else f"arg{i}"
                
                calls.append({
                    "line": node.lineno,
                    "caller_function": caller_function,
                    "callee_function": func_name,
                    "argument_index": i,
                    "argument_expr": arg_expr,
                    "param_name": param_name
                })
    
    return calls


def extract_python_returns(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract return statements from Python AST."""
    returns = []
    actual_tree = tree.get("tree")
    
    if not actual_tree:
        return returns
    
    # First, map all functions
    function_ranges = {}
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)
    
    # Extract return statements
    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Return):
            # Find containing function
            function_name = "global"
            for fname, (start, end) in function_ranges.items():
                if start <= node.lineno <= end:
                    function_name = fname
                    break
            
            # Extract return expression
            if node.value:
                return_expr = ast.unparse(node.value) if hasattr(ast, "unparse") else str(node.value)
                return_vars = extract_vars_from_expr(node.value)
            else:
                return_expr = "None"
                return_vars = []
            
            returns.append({
                "function_name": function_name,
                "line": node.lineno,
                "return_expr": return_expr,
                "return_vars": return_vars
            })
    
    return returns


# Python doesn't have property accesses in the same way as JS
# This is a placeholder for consistency
def extract_python_properties(tree: Dict, parser_self) -> List[Dict]:
    """Extract property accesses from Python AST.
    
    In Python, these would be attribute accesses.
    Currently returns empty list for consistency.
    """
    return []