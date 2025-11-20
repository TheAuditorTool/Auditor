"""Data flow extractors - I/O operations, parameter flows, closures, nonlocal.

This module contains extraction logic for data flow patterns:
- I/O operations (file, database, network, process, environment)
- Parameter to return flow tracking
- Closure variable captures
- Nonlocal variable access

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'io_type', 'operation', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
This separation ensures single source of truth for file paths.

Causal Learning Purpose:
========================
These extractors enable hypothesis generation for DIEC tool:
- "Function X writes to filesystem" → Test by mocking filesystem, verify write
- "Function X returns transformed parameter Y" → Test with known input, verify output
- "Function depends on outer variable Z" → Test closure behavior
- "Nested function modifies outer variable" → Test nonlocal mutation

Each extraction enables >3 hypothesis types per python_coverage.md requirements.
Target >70% validation rate when hypotheses are tested experimentally.

Week 2 Implementation (Priority 3 - Data Flow):
=================================================
Data flow is critical for taint analysis and security hypothesis generation.
Understanding how data moves through code enables detection of injection vulnerabilities.

Expected extraction from TheAuditor codebase:
- ~2,000 I/O operations (file, db, network, process, env)
- ~1,500 parameter return flows
- ~300 closure captures
- ~50 nonlocal accesses
Total: ~3,850 data flow records
"""
from __future__ import annotations
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
import os
from typing import Any, Dict, List, Optional, Set

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions (Internal - Duplicated for Self-Containment)
# ============================================================================

def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes.

    Handles both Python 3.8+ ast.Constant and legacy ast.Str nodes.
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if (isinstance(node, ast.Constant) and isinstance(node.value, str)):  # Python 3.7 compat (though we require 3.11+)
        return node.value
    return None


# ============================================================================
# Data Flow Extractors
# ============================================================================

def extract_io_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract all I/O operations that interact with external systems.

    Detects:
    - File operations: open(file, 'w'), Path.write_text(), file.read()
    - Database operations: db.session.commit(), cursor.execute(), connection.commit()
    - Network calls: requests.post(), urllib.request.urlopen(), httpx.get()
    - Process spawning: subprocess.run(), os.system(), os.popen()
    - Environment modifications: os.environ['KEY'] = value

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of I/O operation dicts:
        {
            'line': int,
            'io_type': str,  # 'FILE_WRITE' | 'FILE_READ' | 'DB_COMMIT' | 'DB_QUERY' | 'NETWORK' | 'PROCESS' | 'ENV_MODIFY'
            'operation': str,  # 'open' | 'requests.post' | 'subprocess.run' | etc.
            'target': str | None,  # Filename, URL, command, etc. (if static)
            'is_static': bool,  # True if target is statically known
            'in_function': str,
        }

    Enables hypothesis: "Function X writes to filesystem"
    Experiment design: Mock filesystem, call X, verify write occurred
    """
    io_operations = []
    context.tree = tree.get("tree")  # CRITICAL: Extract AST from dict

    if not isinstance(context.tree, ast.AST):
        return io_operations

    # Build function ranges for context detection
    function_ranges = []  # List of (name, start, end)

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges.append((node.name, node.lineno, node.end_lineno or node.lineno))

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    # I/O operation patterns (function name → io_type mapping)
    FILE_OPS = {
        'open': 'FILE_WRITE',  # Default to write, refined by mode
        'write': 'FILE_WRITE',
        'write_text': 'FILE_WRITE',
        'write_bytes': 'FILE_WRITE',
        'read': 'FILE_READ',
        'read_text': 'FILE_READ',
        'read_bytes': 'FILE_READ',
        'readlines': 'FILE_READ',
    }

    DB_OPS = {
        'commit': 'DB_COMMIT',
        'execute': 'DB_QUERY',
        'executemany': 'DB_QUERY',
        'rollback': 'DB_ROLLBACK',
        'query': 'DB_QUERY',
        'add': 'DB_INSERT',
        'delete': 'DB_DELETE',
        'update': 'DB_UPDATE',
    }

    NETWORK_OPS = {
        'get': 'NETWORK',
        'post': 'NETWORK',
        'put': 'NETWORK',
        'delete': 'NETWORK',
        'patch': 'NETWORK',
        'request': 'NETWORK',
        'urlopen': 'NETWORK',
        'fetch': 'NETWORK',
    }

    PROCESS_OPS = {
        'run': 'PROCESS',
        'call': 'PROCESS',
        'check_call': 'PROCESS',
        'check_output': 'PROCESS',
        'system': 'PROCESS',
        'popen': 'PROCESS',
        'spawn': 'PROCESS',
    }

    # Extract I/O operations from function calls
    for node in context.find_nodes(ast.Call):
        in_function = find_containing_function(node.lineno)
        operation_name = get_node_name(node.func)

        if not operation_name:
            continue

        # Classify I/O type
        io_type = None
        target = None
        is_static = False

        # Check for built-in open()
        if operation_name == 'open':
            io_type = 'FILE_READ'  # Default
            # Try to get filename (first arg)
            if node.args:
                target = _get_str_constant(node.args[0])
                is_static = (target is not None)

            # Check mode (second arg or 'mode' kwarg)
            mode = None
            if len(node.args) >= 2:
                mode = _get_str_constant(node.args[1])
            else:
                # Check kwargs
                for keyword in node.keywords:
                    if keyword.arg == 'mode':
                        mode = _get_str_constant(keyword.value)
                        break

            # Refine io_type based on mode
            if mode and ('w' in mode or 'a' in mode or '+' in mode):
                io_type = 'FILE_WRITE'

            io_operations.append({
                'line': node.lineno,
                'io_type': io_type,
                'operation': 'open',
                'target': target,
                'is_static': is_static,
                'in_function': in_function,
            })

        # Check for Path.write_text() / Path.read_text() etc.
        elif any(op in operation_name for op in FILE_OPS):
            for file_op, file_type in FILE_OPS.items():
                if file_op in operation_name:
                    io_type = file_type
                    # Try to extract static target
                    if node.args:
                        target = _get_str_constant(node.args[0])
                        is_static = (target is not None)

                    io_operations.append({
                        'line': node.lineno,
                        'io_type': io_type,
                        'operation': operation_name,
                        'target': target,
                        'is_static': is_static,
                        'in_function': in_function,
                    })
                    break

        # Check for database operations
        elif any(op in operation_name for op in DB_OPS):
            for db_op, db_type in DB_OPS.items():
                if db_op in operation_name:
                    io_type = db_type
                    # Try to extract query (if execute/query)
                    if db_type == 'DB_QUERY' and node.args:
                        target = _get_str_constant(node.args[0])
                        is_static = (target is not None)

                    io_operations.append({
                        'line': node.lineno,
                        'io_type': io_type,
                        'operation': operation_name,
                        'target': target,
                        'is_static': is_static,
                        'in_function': in_function,
                    })
                    break

        # Check for network operations
        elif any(op in operation_name.lower() for op in NETWORK_OPS):
            for net_op, net_type in NETWORK_OPS.items():
                if net_op in operation_name.lower():
                    io_type = net_type
                    # Try to extract URL (first arg)
                    if node.args:
                        target = _get_str_constant(node.args[0])
                        is_static = (target is not None)

                    io_operations.append({
                        'line': node.lineno,
                        'io_type': io_type,
                        'operation': operation_name,
                        'target': target,
                        'is_static': is_static,
                        'in_function': in_function,
                    })
                    break

        # Check for process operations
        elif any(op in operation_name for op in PROCESS_OPS):
            for proc_op, proc_type in PROCESS_OPS.items():
                if proc_op in operation_name:
                    io_type = proc_type
                    # Try to extract command (first arg or list)
                    if node.args:
                        first_arg = node.args[0]
                        if isinstance(first_arg, ast.List):
                            # subprocess.run(['ls', '-la'])
                            if first_arg.elts:
                                target = _get_str_constant(first_arg.elts[0])
                        else:
                            target = _get_str_constant(first_arg)
                        is_static = (target is not None)

                    io_operations.append({
                        'line': node.lineno,
                        'io_type': io_type,
                        'operation': operation_name,
                        'target': target,
                        'is_static': is_static,
                        'in_function': in_function,
                    })
                    break

    # CRITICAL: Deduplicate by (line, io_type, operation)
    seen = set()
    deduped = []
    for io_op in io_operations:
        key = (io_op['line'], io_op['io_type'], io_op['operation'])
        if key not in seen:
            seen.add(key)
            deduped.append(io_op)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(io_operations) != len(deduped):
            print(f"[AST_DEBUG] I/O operations deduplication: {len(io_operations)} -> {len(deduped)} ({len(io_operations) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_parameter_return_flow(context: FileContext) -> list[dict[str, Any]]:
    """Track how function parameters influence return values.

    Detects:
    - Direct returns: return param
    - Transformed returns: return param * 2
    - Conditional returns: return a if condition else b
    - No data flow: return constant (no parameter reference)

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of parameter flow dicts:
        {
            'line': int,
            'function_name': str,
            'parameter_name': str,  # Parameter referenced in return
            'return_expr': str,  # Full return expression
            'flow_type': str,  # 'direct' | 'transformed' | 'conditional' | 'none'
            'is_async': bool,
        }

    Enables hypothesis: "Function X returns transformed parameter Y"
    Experiment design: Call X with param=5, assert return value = 10 (if transform is *2)
    """
    param_flows = []
    context.tree = tree.get("tree")  # CRITICAL: Extract AST from dict

    if not isinstance(context.tree, ast.AST):
        return param_flows

    # Extract function definitions with their parameters
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        func_name = node.name
        is_async = isinstance(node, ast.AsyncFunctionDef)

        # Extract parameter names
        param_names = set()
        if hasattr(node, 'args') and node.args:
            args_obj = node.args
            # Regular args
            for arg in args_obj.args:
                param_names.add(arg.arg)
            # *args
            if args_obj.vararg:
                param_names.add(args_obj.vararg.arg)
            # **kwargs
            if args_obj.kwarg:
                param_names.add(args_obj.kwarg.arg)
            # kwonly args
            for arg in args_obj.kwonlyargs:
                param_names.add(arg.arg)

        # Skip self/cls
        param_names.discard('self')
        param_names.discard('cls')

        if not param_names:
            continue

        # Find return statements in this function
        for child in context.find_nodes(ast.Return):
            if child.value is None:
                continue  # return without value

            return_expr = get_node_name(child.value)
            if not return_expr:
                continue

            # Check if any parameter is referenced in return expression
            referenced_params = []
            for param in param_names:
                if param in return_expr:
                    referenced_params.append(param)

            if not referenced_params:
                # No parameter flow - return constant
                continue

            # Classify flow type
            flow_type = 'none'

            for param in referenced_params:
                # Direct return (just the parameter)
                if return_expr == param or return_expr == f"self.{param}":
                    flow_type = 'direct'
                # Conditional return (IfExp)
                elif isinstance(child.value, ast.IfExp):
                    flow_type = 'conditional'
                # Transformed return (BinOp, UnaryOp, Call, etc.)
                elif isinstance(child.value, (ast.BinOp, ast.UnaryOp, ast.Call, ast.Compare)):
                    flow_type = 'transformed'
                else:
                    flow_type = 'other'

                param_flows.append({
                    'line': child.lineno,
                    'function_name': func_name,
                    'parameter_name': param,
                    'return_expr': return_expr,
                    'flow_type': flow_type,
                    'is_async': is_async,
                })

    # CRITICAL: Deduplicate by (line, function_name, parameter_name)
    seen = set()
    deduped = []
    for pf in param_flows:
        key = (pf['line'], pf['function_name'], pf['parameter_name'])
        if key not in seen:
            seen.add(key)
            deduped.append(pf)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(param_flows) != len(deduped):
            print(f"[AST_DEBUG] Parameter flows deduplication: {len(param_flows)} -> {len(deduped)} ({len(param_flows) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_closure_captures(context: FileContext) -> list[dict[str, Any]]:
    """Identify variables captured from outer scope (closures).

    Detects:
    - Nested functions accessing outer variables
    - Lambda functions capturing variables
    - Variables from enclosing function scope

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of closure capture dicts:
        {
            'line': int,
            'inner_function': str,  # Nested function name
            'captured_variable': str,  # Variable from outer scope
            'outer_function': str,  # Enclosing function name
            'is_lambda': bool,  # True if inner function is lambda
        }

    Enables hypothesis: "Function X depends on outer variable Y"
    Experiment design: Call X with different outer variable values, verify behavior changes
    """
    closures = []
    context.tree = tree.get("tree")  # CRITICAL: Extract AST from dict

    if not isinstance(context.tree, ast.AST):
        return closures

    # Build nested function structure
    # Map: function_name → (parent_function, defined_vars, line)
    function_hierarchy = {}
    function_locals = {}  # function_name → set of local variables

    def analyze_function(node, parent_func='global'):
        """Recursively analyze function definitions."""
        func_name = node.name if hasattr(node, 'name') else f'lambda_{node.lineno}'
        is_lambda = isinstance(node, ast.Lambda)

        # Track this function's hierarchy
        function_hierarchy[func_name] = parent_func

        # Extract local variables defined in this function
        local_vars = set()

        # Add parameters as local variables
        if hasattr(node, 'args') and node.args:
            for arg in node.args.args:
                local_vars.add(arg.arg)
            if node.args.vararg:
                local_vars.add(node.args.vararg.arg)
            if node.args.kwarg:
                local_vars.add(node.args.kwarg.arg)
            for arg in node.args.kwonlyargs:
                local_vars.add(arg.arg)

        # Find assignments (define new local variables)
        if hasattr(node, 'body'):
            body = node.body if isinstance(node.body, list) else [node.body]
            for stmt in context.find_nodes(ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        local_vars.add(target.id)

        function_locals[func_name] = local_vars

        # Recursively analyze nested functions
        body = node.body if hasattr(node, 'body') else []
        if not isinstance(body, list):
            body = [body]

        for child in body:
            for nested in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if nested != node:  # Avoid re-analyzing self
                    analyze_function(nested, parent_func=func_name)

    # First pass: build function hierarchy
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        analyze_function(node, parent_func='global')

    # Second pass: find variable references and detect closures
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        func_name = node.name if hasattr(node, 'name') else f'lambda_{node.lineno}'
        is_lambda = isinstance(node, ast.Lambda)

        if func_name not in function_hierarchy:
            continue

        parent_func = function_hierarchy[func_name]
        if parent_func == 'global':
            continue  # No closure possible at top level

        local_vars = function_locals.get(func_name, set())

        # Find all Name nodes (variable references) in this function
        body = node.body if hasattr(node, 'body') else []
        if not isinstance(body, list):
            body = [body]

        for child in context.walk_tree():
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                var_name = child.id

                # Check if variable is NOT local to this function
                if var_name not in local_vars and var_name not in ('self', 'cls'):
                    # Check if variable might be from parent function
                    parent_locals = function_locals.get(parent_func, set())

                    if var_name in parent_locals:
                        # Found closure! Variable from outer scope
                        closures.append({
                            'line': node.lineno,
                            'inner_function': func_name,
                            'captured_variable': var_name,
                            'outer_function': parent_func,
                            'is_lambda': is_lambda,
                        })

    # CRITICAL: Deduplicate by (line, inner_function, captured_variable)
    seen = set()
    deduped = []
    for closure in closures:
        key = (closure['line'], closure['inner_function'], closure['captured_variable'])
        if key not in seen:
            seen.add(key)
            deduped.append(closure)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(closures) != len(deduped):
            print(f"[AST_DEBUG] Closure captures deduplication: {len(closures)} -> {len(deduped)} ({len(closures) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_nonlocal_access(context: FileContext) -> list[dict[str, Any]]:
    """Extract nonlocal variable modifications.

    Detects:
    - nonlocal x; x = value (write)
    - nonlocal x; ... usage of x (read)

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of nonlocal access dicts:
        {
            'line': int,
            'variable_name': str,  # Nonlocal variable name
            'access_type': str,  # 'read' | 'write'
            'in_function': str,  # Function containing nonlocal declaration
        }

    Enables hypothesis: "Nested function X modifies outer variable Y"
    Experiment design: Call X, verify outer Y value changed
    """
    nonlocal_accesses = []
    context.tree = tree.get("tree")  # CRITICAL: Extract AST from dict

    if not isinstance(context.tree, ast.AST):
        return nonlocal_accesses

    # Build function ranges and track nonlocal declarations
    function_ranges = []  # List of (name, start, end)
    nonlocals_by_function = {}  # {function_name: set(nonlocal_var_names)}

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        func_name = node.name
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges.append((func_name, node.lineno, node.end_lineno or node.lineno))

        # Track nonlocal declarations within this function
        nonlocal_vars = set()
        for child in context.find_nodes(ast.Nonlocal):
            nonlocal_vars.update(child.names)

        if nonlocal_vars:
            nonlocals_by_function[func_name] = nonlocal_vars

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    # Extract nonlocal variable accesses
    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                in_function = find_containing_function(node.lineno)

                if in_function != "global" and in_function in nonlocals_by_function:
                    if var_name in nonlocals_by_function[in_function]:
                        nonlocal_accesses.append({
                            'line': node.lineno,
                            'variable_name': var_name,
                            'access_type': 'write',
                            'in_function': in_function,
                        })

    # CRITICAL: Deduplicate by (line, variable_name, access_type)
    seen = set()
    deduped = []
    for nl in nonlocal_accesses:
        key = (nl['line'], nl['variable_name'], nl['access_type'])
        if key not in seen:
            seen.add(key)
            deduped.append(nl)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(nonlocal_accesses) != len(deduped):
            print(f"[AST_DEBUG] Nonlocal accesses deduplication: {len(nonlocal_accesses)} -> {len(deduped)} ({len(nonlocal_accesses) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_conditional_calls(context: FileContext) -> list[dict[str, Any]]:
    """Extract function calls made under conditional execution (Week 2 Data Flow).

    Tracks when functions are called under specific conditions - critical for
    understanding conditional behavior dependencies in causal learning.

    Detects:
    - Functions called only within if/elif/else blocks
    - Guard clauses (early returns based on validation)
    - Exception-dependent code paths
    - Nested conditional execution

    Expected extraction from TheAuditor: ~400 conditional calls

    Example hypothesis: "delete_all_users() is only called when user.is_admin is True"
    """
    context.tree = tree.get("tree")
    if not context.tree:
        return []

    conditional_calls = []

    # Build function ranges for context
    function_ranges = {}
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        function_ranges[(node.lineno, node.end_lineno)] = node.name

    def get_function_name(line: int) -> str:
        """Get function name for a given line number."""
        for (start, end), name in function_ranges.items():
            if start <= line <= end:
                return name
        return 'global'

    def get_condition_expr(test_node) -> str | None:
        """Extract condition expression as string."""
        try:
            return ast.unparse(test_node)
        except Exception:
            return None

    def walk_conditional_block(parent_node, condition_expr: str | None,
                                condition_type: str, nesting_level: int):
        """Walk conditional block and extract function calls."""
        if not hasattr(parent_node, 'body'):
            return

        for node in parent_node.body:
            # Direct function call in conditional block
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call_node = node.value
                func_name = None
                if isinstance(call_node.func, ast.Name):
                    func_name = call_node.func.id
                elif isinstance(call_node.func, ast.Attribute):
                    func_name = ast.unparse(call_node.func)

                if func_name:
                    in_function = get_function_name(node.lineno)
                    conditional_calls.append({
                        'line': node.lineno,
                        'function_call': func_name,
                        'condition_expr': condition_expr,
                        'condition_type': condition_type,
                        'in_function': in_function,
                        'nesting_level': nesting_level,
                    })

            # Assignment with function call on right side
            elif isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call):
                    call_node = node.value
                    func_name = None
                    if isinstance(call_node.func, ast.Name):
                        func_name = call_node.func.id
                    elif isinstance(call_node.func, ast.Attribute):
                        func_name = ast.unparse(call_node.func)

                    if func_name:
                        in_function = get_function_name(node.lineno)
                        conditional_calls.append({
                            'line': node.lineno,
                            'function_call': func_name,
                            'condition_expr': condition_expr,
                            'condition_type': condition_type,
                            'in_function': in_function,
                            'nesting_level': nesting_level,
                        })

            # Return statement with function call
            elif isinstance(node, ast.Return) and node.value:
                if isinstance(node.value, ast.Call):
                    call_node = node.value
                    func_name = None
                    if isinstance(call_node.func, ast.Name):
                        func_name = call_node.func.id
                    elif isinstance(call_node.func, ast.Attribute):
                        func_name = ast.unparse(call_node.func)

                    if func_name:
                        in_function = get_function_name(node.lineno)
                        conditional_calls.append({
                            'line': node.lineno,
                            'function_call': func_name,
                            'condition_expr': condition_expr,
                            'condition_type': condition_type,
                            'in_function': in_function,
                            'nesting_level': nesting_level,
                        })

            # Nested conditionals
            elif isinstance(node, ast.If):
                nested_condition = get_condition_expr(node.test)
                walk_conditional_block(node, nested_condition, 'if', nesting_level + 1)
                for elif_node in node.orelse:
                    if isinstance(elif_node, ast.If):
                        elif_condition = get_condition_expr(elif_node.test)
                        walk_conditional_block(elif_node, elif_condition, 'elif', nesting_level + 1)
                    else:
                        # else block
                        walk_conditional_block(type('obj', (), {'body': [elif_node]})(),
                                                condition_expr, 'else', nesting_level + 1)

    # Walk entire tree looking for conditionals
    for node in context.find_nodes(ast.If):
        condition = get_condition_expr(node.test)
        in_function = get_function_name(node.lineno)

        # Check for guard clause pattern (early return)
        is_guard = False
        if (len(node.body) == 1 and
            isinstance(node.body[0], (ast.Return, ast.Raise, ast.Continue, ast.Break))):
            is_guard = True

        condition_type = 'guard' if is_guard else 'if'
        walk_conditional_block(node, condition, condition_type, 1)

        # Handle elif
        for i, elif_node in enumerate(node.orelse):
            if isinstance(elif_node, ast.If):
                elif_condition = get_condition_expr(elif_node.test)
                walk_conditional_block(elif_node, elif_condition, 'elif', 1)
            else:
                # else block
                if hasattr(elif_node, 'lineno'):
                    walk_conditional_block(type('obj', (), {'body': [elif_node]})(),
                                            condition, 'else', 1)

    # CRITICAL: Deduplicate by (line, function_call)
    seen = set()
    deduped = []
    for call in conditional_calls:
        key = (call['line'], call['function_call'])
        if key not in seen:
            seen.add(key)
            deduped.append(call)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(conditional_calls) != len(deduped):
            print(f"[AST_DEBUG] Conditional calls deduplication: {len(conditional_calls)} -> {len(deduped)} ({len(conditional_calls) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped
