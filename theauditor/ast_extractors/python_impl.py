"""Python AST extraction implementations.

This module contains all Python-specific extraction logic using the built-in ast module.

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
This is an IMPLEMENTATION layer module. All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'name', 'type', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer (indexer/__init__.py)
when storing to database. See indexer/__init__.py:952 for example.

This separation ensures single source of truth for file paths.
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
            # CRITICAL FIX: Add end_line for proper function boundaries
            end_line = getattr(node, 'end_lineno', node.lineno)
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "end_line": end_line,
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

    # CRITICAL FIX: Deduplicate assignments by (line, target_var, in_function)
    # WHY: ast.walk() can visit nodes multiple times if they appear in tree multiple times.
    # Same issue as TypeScript extractor, same solution.
    seen = set()
    deduped = []
    for a in assignments:
        key = (a['line'], a['target_var'], a['in_function'])
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(assignments) != len(deduped):
            print(f"[AST_DEBUG] Python deduplication: {len(assignments)} -> {len(deduped)} assignments ({len(assignments) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


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

    # CRITICAL FIX: Deduplicate returns by (line, function_name)
    # WHY: ast.walk() can visit nodes multiple times
    # NOTE: PRIMARY KEY is (file, line, function_name) but file is added by orchestrator
    seen = set()
    deduped = []
    for r in returns:
        key = (r['line'], r['function_name'])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(returns) != len(deduped):
            print(f"[AST_DEBUG] Python returns deduplication: {len(returns)} -> {len(deduped)} ({len(returns) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


# Python doesn't have property accesses in the same way as JS
# This is a placeholder for consistency
def extract_python_properties(tree: Dict, parser_self) -> List[Dict]:
    """Extract property accesses from Python AST.

    In Python, these would be attribute accesses.
    Currently returns empty list for consistency.
    """
    return []


def extract_python_dicts(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract dict literal structures from Python AST.

    This is the centralized, correct implementation for dict literal extraction.
    Extracts patterns like:
    - {'key': value}
    - {'key': func_ref}
    - {**spread_dict}

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to the parser instance

    Returns:
        List of dict property records matching object_literals schema
    """
    object_literals = []
    actual_tree = tree.get("tree")

    if not actual_tree or not isinstance(actual_tree, ast.Module):
        return object_literals

    # Build function ranges for scope detection
    function_ranges = {}
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, (start, end) in function_ranges.items():
            if start <= line_no <= end:
                return fname
        return "global"

    def extract_dict_properties(dict_node, variable_name, line_no):
        """Extract properties from a dict node."""
        records = []
        in_function = find_containing_function(line_no)

        # Handle dict with explicit keys
        if dict_node.keys:
            for i, (key, value) in enumerate(zip(dict_node.keys, dict_node.values)):
                # Skip None keys (these are **spread operations)
                if key is None:
                    # This is a dict unpacking: {**other_dict}
                    spread_name = get_node_name(value)
                    records.append({
                        "line": line_no,
                        "variable_name": variable_name,
                        "property_name": "**spread",
                        "property_value": spread_name,
                        "property_type": "spread",
                        "nested_level": 0,
                        "in_function": in_function
                    })
                    continue

                # Extract key name
                property_name = None
                if isinstance(key, ast.Constant):
                    property_name = str(key.value)
                elif isinstance(key, ast.Str):  # Python 3.7 compat
                    property_name = key.s
                elif isinstance(key, ast.Name):
                    property_name = key.id
                else:
                    property_name = get_node_name(key) or f"<key_{i}>"

                # Extract value
                property_value = ""
                property_type = "value"

                if isinstance(value, ast.Name):
                    # Variable reference (could be function)
                    property_value = value.id
                    property_type = "function_ref"
                elif isinstance(value, (ast.Lambda, ast.FunctionDef)):
                    # Function/lambda
                    property_value = "<lambda>" if isinstance(value, ast.Lambda) else value.name
                    property_type = "function"
                elif isinstance(value, ast.Constant):
                    property_value = str(value.value)[:250]
                    property_type = "literal"
                elif isinstance(value, ast.Str):  # Python 3.7
                    property_value = value.s[:250]
                    property_type = "literal"
                elif isinstance(value, ast.Dict):
                    property_value = "{...}"
                    property_type = "object"
                elif isinstance(value, ast.List):
                    property_value = "[...]"
                    property_type = "array"
                else:
                    # Complex expression
                    property_value = ast.unparse(value)[:250] if hasattr(ast, "unparse") else str(value)[:250]
                    property_type = "expression"

                records.append({
                    "line": line_no,
                    "variable_name": variable_name,
                    "property_name": property_name,
                    "property_value": property_value,
                    "property_type": property_type,
                    "nested_level": 0,
                    "in_function": in_function
                })

        return records

    # Traverse AST to find all dict literals
    for node in ast.walk(actual_tree):
        # Pattern 1: Variable assignment with dict
        # x = {'key': 'value'}
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(node.value, ast.Dict):
                    var_name = get_node_name(target)
                    records = extract_dict_properties(node.value, var_name, node.lineno)
                    object_literals.extend(records)

        # Pattern 2: Return statement with dict
        # return {'key': 'value'}
        elif isinstance(node, ast.Return):
            if node.value and isinstance(node.value, ast.Dict):
                var_name = f"<return_dict_line_{node.lineno}>"
                records = extract_dict_properties(node.value, var_name, node.lineno)
                object_literals.extend(records)

        # Pattern 3: Function call arguments with dict
        # func({'key': 'value'})
        elif isinstance(node, ast.Call):
            for i, arg in enumerate(node.args):
                if isinstance(arg, ast.Dict):
                    var_name = f"<arg_dict_line_{arg.lineno}>"
                    records = extract_dict_properties(arg, var_name, arg.lineno)
                    object_literals.extend(records)

        # Pattern 4: List elements with dict
        # [{'key': 'value'}]
        elif isinstance(node, ast.List):
            for elem in node.elts:
                if isinstance(elem, ast.Dict) and hasattr(elem, 'lineno'):
                    var_name = f"<list_dict_line_{elem.lineno}>"
                    records = extract_dict_properties(elem, var_name, elem.lineno)
                    object_literals.extend(records)

    return object_literals


def extract_python_cfg(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract control flow graphs for all Python functions.

    Returns CFG data matching the database schema expectations.
    """
    cfg_data = []
    actual_tree = tree.get("tree")

    if not actual_tree:
        return cfg_data

    # Find all functions and methods
    for node in ast.walk(actual_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_cfg = build_python_function_cfg(node)
            if function_cfg:
                cfg_data.append(function_cfg)

    return cfg_data


def build_python_function_cfg(func_node: ast.FunctionDef) -> Dict[str, Any]:
    """Build control flow graph for a single Python function.

    Args:
        func_node: Function AST node

    Returns:
        CFG data dictionary
    """
    blocks = []
    edges = []
    block_id_counter = [0]  # Use list to allow mutation in nested function

    def get_next_block_id():
        block_id_counter[0] += 1
        return block_id_counter[0]

    # Entry block
    entry_block_id = get_next_block_id()
    blocks.append({
        'id': entry_block_id,
        'type': 'entry',
        'start_line': func_node.lineno,
        'end_line': func_node.lineno,
        'statements': []
    })

    # Process function body
    current_block_id = entry_block_id
    exit_block_id = None

    for stmt in func_node.body:
        block_info = process_python_statement(stmt, current_block_id, get_next_block_id)

        if block_info:
            new_blocks, new_edges, next_block_id = block_info
            blocks.extend(new_blocks)
            edges.extend(new_edges)
            current_block_id = next_block_id

    # Exit block
    if current_block_id:
        exit_block_id = get_next_block_id()
        blocks.append({
            'id': exit_block_id,
            'type': 'exit',
            'start_line': func_node.end_lineno or func_node.lineno,
            'end_line': func_node.end_lineno or func_node.lineno,
            'statements': []
        })
        edges.append({
            'source': current_block_id,
            'target': exit_block_id,
            'type': 'normal'
        })

    return {
        'function_name': func_node.name,
        'blocks': blocks,
        'edges': edges
    }


def process_python_statement(stmt: ast.stmt, current_block_id: int,
                            get_next_block_id) -> Optional[tuple]:
    """Process a statement and update CFG.

    Args:
        stmt: Statement AST node
        current_block_id: Current block ID
        get_next_block_id: Function to get next block ID

    Returns:
        Tuple of (new_blocks, new_edges, next_block_id) or None
    """
    blocks = []
    edges = []

    if isinstance(stmt, ast.If):
        # Create condition block
        condition_block_id = get_next_block_id()
        blocks.append({
            'id': condition_block_id,
            'type': 'condition',
            'start_line': stmt.lineno,
            'end_line': stmt.lineno,
            'condition': ast.unparse(stmt.test) if hasattr(ast, 'unparse') else 'condition',
            'statements': [{'type': 'if', 'line': stmt.lineno}]
        })

        # Connect current to condition
        edges.append({
            'source': current_block_id,
            'target': condition_block_id,
            'type': 'normal'
        })

        # Then branch
        then_block_id = get_next_block_id()
        blocks.append({
            'id': then_block_id,
            'type': 'basic',
            'start_line': stmt.body[0].lineno if stmt.body else stmt.lineno,
            'end_line': stmt.body[-1].end_lineno if stmt.body and hasattr(stmt.body[-1], 'end_lineno') else stmt.lineno,
            'statements': [{'type': 'statement', 'line': s.lineno} for s in stmt.body]
        })
        edges.append({
            'source': condition_block_id,
            'target': then_block_id,
            'type': 'true'
        })

        # Else branch (if exists)
        if stmt.orelse:
            else_block_id = get_next_block_id()
            blocks.append({
                'id': else_block_id,
                'type': 'basic',
                'start_line': stmt.orelse[0].lineno if stmt.orelse else stmt.lineno,
                'end_line': stmt.orelse[-1].end_lineno if stmt.orelse and hasattr(stmt.orelse[-1], 'end_lineno') else stmt.lineno,
                'statements': [{'type': 'statement', 'line': s.lineno} for s in stmt.orelse]
            })
            edges.append({
                'source': condition_block_id,
                'target': else_block_id,
                'type': 'false'
            })

            # Merge point
            merge_block_id = get_next_block_id()
            blocks.append({
                'id': merge_block_id,
                'type': 'merge',
                'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'statements': []
            })
            edges.append({'source': then_block_id, 'target': merge_block_id, 'type': 'normal'})
            edges.append({'source': else_block_id, 'target': merge_block_id, 'type': 'normal'})

            return blocks, edges, merge_block_id
        else:
            # No else branch - false goes to next block
            next_block_id = get_next_block_id()
            blocks.append({
                'id': next_block_id,
                'type': 'merge',
                'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'statements': []
            })
            edges.append({'source': condition_block_id, 'target': next_block_id, 'type': 'false'})
            edges.append({'source': then_block_id, 'target': next_block_id, 'type': 'normal'})

            return blocks, edges, next_block_id

    elif isinstance(stmt, (ast.While, ast.For)):
        # Loop condition block
        loop_block_id = get_next_block_id()
        blocks.append({
            'id': loop_block_id,
            'type': 'loop_condition',
            'start_line': stmt.lineno,
            'end_line': stmt.lineno,
            'condition': ast.unparse(stmt.test if isinstance(stmt, ast.While) else stmt.iter) if hasattr(ast, 'unparse') else 'loop',
            'statements': [{'type': 'while' if isinstance(stmt, ast.While) else 'for', 'line': stmt.lineno}]
        })
        edges.append({'source': current_block_id, 'target': loop_block_id, 'type': 'normal'})

        # Loop body
        body_block_id = get_next_block_id()
        blocks.append({
            'id': body_block_id,
            'type': 'loop_body',
            'start_line': stmt.body[0].lineno if stmt.body else stmt.lineno,
            'end_line': stmt.body[-1].end_lineno if stmt.body and hasattr(stmt.body[-1], 'end_lineno') else stmt.lineno,
            'statements': [{'type': 'statement', 'line': s.lineno} for s in stmt.body]
        })
        edges.append({'source': loop_block_id, 'target': body_block_id, 'type': 'true'})
        edges.append({'source': body_block_id, 'target': loop_block_id, 'type': 'back_edge'})

        # Exit from loop
        exit_block_id = get_next_block_id()
        blocks.append({
            'id': exit_block_id,
            'type': 'merge',
            'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
            'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
            'statements': []
        })
        edges.append({'source': loop_block_id, 'target': exit_block_id, 'type': 'false'})

        return blocks, edges, exit_block_id

    elif isinstance(stmt, ast.Return):
        # Return statement - no successors
        return_block_id = get_next_block_id()
        blocks.append({
            'id': return_block_id,
            'type': 'return',
            'start_line': stmt.lineno,
            'end_line': stmt.lineno,
            'statements': [{'type': 'return', 'line': stmt.lineno}]
        })
        edges.append({'source': current_block_id, 'target': return_block_id, 'type': 'normal'})

        return blocks, edges, None  # No successor after return

    elif isinstance(stmt, ast.Try):
        # Try-except block
        try_block_id = get_next_block_id()
        blocks.append({
            'id': try_block_id,
            'type': 'try',
            'start_line': stmt.lineno,
            'end_line': stmt.body[-1].end_lineno if stmt.body and hasattr(stmt.body[-1], 'end_lineno') else stmt.lineno,
            'statements': [{'type': 'try', 'line': stmt.lineno}]
        })
        edges.append({'source': current_block_id, 'target': try_block_id, 'type': 'normal'})

        # Exception handlers
        handler_ids = []
        for handler in stmt.handlers:
            handler_block_id = get_next_block_id()
            blocks.append({
                'id': handler_block_id,
                'type': 'except',
                'start_line': handler.lineno,
                'end_line': handler.body[-1].end_lineno if handler.body and hasattr(handler.body[-1], 'end_lineno') else handler.lineno,
                'statements': [{'type': 'except', 'line': handler.lineno}]
            })
            edges.append({'source': try_block_id, 'target': handler_block_id, 'type': 'exception'})
            handler_ids.append(handler_block_id)

        # Finally block (if exists)
        if stmt.finalbody:
            finally_block_id = get_next_block_id()
            blocks.append({
                'id': finally_block_id,
                'type': 'finally',
                'start_line': stmt.finalbody[0].lineno,
                'end_line': stmt.finalbody[-1].end_lineno if hasattr(stmt.finalbody[-1], 'end_lineno') else stmt.finalbody[0].lineno,
                'statements': [{'type': 'finally', 'line': stmt.finalbody[0].lineno}]
            })

            # All paths lead to finally
            edges.append({'source': try_block_id, 'target': finally_block_id, 'type': 'normal'})
            for handler_id in handler_ids:
                edges.append({'source': handler_id, 'target': finally_block_id, 'type': 'normal'})

            return blocks, edges, finally_block_id
        else:
            # Merge after exception handling
            merge_block_id = get_next_block_id()
            blocks.append({
                'id': merge_block_id,
                'type': 'merge',
                'start_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'end_line': stmt.end_lineno if hasattr(stmt, 'end_lineno') else stmt.lineno,
                'statements': []
            })
            edges.append({'source': try_block_id, 'target': merge_block_id, 'type': 'normal'})
            for handler_id in handler_ids:
                edges.append({'source': handler_id, 'target': merge_block_id, 'type': 'normal'})

            return blocks, edges, merge_block_id

    # Default: basic statement, no branching
    return None