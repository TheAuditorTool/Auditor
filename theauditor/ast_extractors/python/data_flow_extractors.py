"""Data flow extractors - I/O operations, parameter flows, closures, nonlocal."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext
from theauditor.utils.logging import logger

from ..base import get_node_name

FILE_OPS = {
    "open": "FILE_WRITE",
    "write": "FILE_WRITE",
    "write_text": "FILE_WRITE",
    "write_bytes": "FILE_WRITE",
    "read": "FILE_READ",
    "read_text": "FILE_READ",
    "read_bytes": "FILE_READ",
    "readlines": "FILE_READ",
}

DB_OPS = {
    "commit": "DB_COMMIT",
    "execute": "DB_QUERY",
    "executemany": "DB_QUERY",
    "rollback": "DB_ROLLBACK",
    "query": "DB_QUERY",
    "add": "DB_INSERT",
    "delete": "DB_DELETE",
    "update": "DB_UPDATE",
}

NETWORK_OPS = {
    "get": "NETWORK",
    "post": "NETWORK",
    "put": "NETWORK",
    "delete": "NETWORK",
    "patch": "NETWORK",
    "request": "NETWORK",
    "urlopen": "NETWORK",
    "fetch": "NETWORK",
}

PROCESS_OPS = {
    "run": "PROCESS",
    "call": "PROCESS",
    "check_call": "PROCESS",
    "check_output": "PROCESS",
    "system": "PROCESS",
    "popen": "PROCESS",
    "spawn": "PROCESS",
}


def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_io_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract all I/O operations that interact with external systems."""
    io_operations = []

    if not isinstance(context.tree, ast.AST):
        return io_operations

    function_ranges = []

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges.append((node.name, node.lineno, node.end_lineno or node.lineno))

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    for node in context.find_nodes(ast.Call):
        in_function = find_containing_function(node.lineno)
        operation_name = get_node_name(node.func)

        if not operation_name:
            continue

        io_type = None
        target = None
        is_static = False

        if operation_name == "open":
            io_type = "FILE_READ"

            if node.args:
                target = _get_str_constant(node.args[0])
                is_static = target is not None

            mode = None
            if len(node.args) >= 2:
                mode = _get_str_constant(node.args[1])
            else:
                for keyword in node.keywords:
                    if keyword.arg == "mode":
                        mode = _get_str_constant(keyword.value)
                        break

            if mode and ("w" in mode or "a" in mode or "+" in mode):
                io_type = "FILE_WRITE"

            io_operations.append(
                {
                    "line": node.lineno,
                    "io_type": io_type,
                    "operation": "open",
                    "target": target,
                    "is_static": is_static,
                    "in_function": in_function,
                }
            )

        elif any(op in operation_name for op in FILE_OPS):
            for file_op, file_type in FILE_OPS.items():
                if file_op in operation_name:
                    io_type = file_type

                    if node.args:
                        target = _get_str_constant(node.args[0])
                        is_static = target is not None

                    io_operations.append(
                        {
                            "line": node.lineno,
                            "io_type": io_type,
                            "operation": operation_name,
                            "target": target,
                            "is_static": is_static,
                            "in_function": in_function,
                        }
                    )
                    break

        elif any(op in operation_name for op in DB_OPS):
            for db_op, db_type in DB_OPS.items():
                if db_op in operation_name:
                    io_type = db_type

                    if db_type == "DB_QUERY" and node.args:
                        target = _get_str_constant(node.args[0])
                        is_static = target is not None

                    io_operations.append(
                        {
                            "line": node.lineno,
                            "io_type": io_type,
                            "operation": operation_name,
                            "target": target,
                            "is_static": is_static,
                            "in_function": in_function,
                        }
                    )
                    break

        elif any(op in operation_name.lower() for op in NETWORK_OPS):
            for net_op, net_type in NETWORK_OPS.items():
                if net_op in operation_name.lower():
                    io_type = net_type

                    if node.args:
                        target = _get_str_constant(node.args[0])
                        is_static = target is not None

                    io_operations.append(
                        {
                            "line": node.lineno,
                            "io_type": io_type,
                            "operation": operation_name,
                            "target": target,
                            "is_static": is_static,
                            "in_function": in_function,
                        }
                    )
                    break

        elif any(op in operation_name for op in PROCESS_OPS):
            for proc_op, proc_type in PROCESS_OPS.items():
                if proc_op in operation_name:
                    io_type = proc_type

                    if node.args:
                        first_arg = node.args[0]
                        if isinstance(first_arg, ast.List):
                            if first_arg.elts:
                                target = _get_str_constant(first_arg.elts[0])
                        else:
                            target = _get_str_constant(first_arg)
                        is_static = target is not None

                    io_operations.append(
                        {
                            "line": node.lineno,
                            "io_type": io_type,
                            "operation": operation_name,
                            "target": target,
                            "is_static": is_static,
                            "in_function": in_function,
                        }
                    )
                    break

    seen = set()
    deduped = []
    for io_op in io_operations:
        key = (io_op["line"], io_op["io_type"], io_op["operation"])
        if key not in seen:
            seen.add(key)
            deduped.append(io_op)

    if len(io_operations) != len(deduped):
        logger.debug(
            f"I/O operations deduplication: {len(io_operations)} -> {len(deduped)} ({len(io_operations) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_parameter_return_flow(context: FileContext) -> list[dict[str, Any]]:
    """Track how function parameters influence return values."""
    param_flows = []

    if not isinstance(context.tree, ast.AST):
        return param_flows

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        func_name = node.name
        is_async = isinstance(node, ast.AsyncFunctionDef)

        param_names = set()
        if hasattr(node, "args") and node.args:
            args_obj = node.args

            for arg in args_obj.args:
                param_names.add(arg.arg)

            if args_obj.vararg:
                param_names.add(args_obj.vararg.arg)

            if args_obj.kwarg:
                param_names.add(args_obj.kwarg.arg)

            for arg in args_obj.kwonlyargs:
                param_names.add(arg.arg)

        param_names.discard("self")
        param_names.discard("cls")

        if not param_names:
            continue

        for child in context.find_nodes(ast.Return):
            if child.value is None:
                continue

            return_expr = get_node_name(child.value)
            if not return_expr:
                continue

            referenced_params = []
            for param in param_names:
                if param in return_expr:
                    referenced_params.append(param)

            if not referenced_params:
                continue

            flow_type = "none"

            for param in referenced_params:
                if return_expr == param or return_expr == f"self.{param}":
                    flow_type = "direct"

                elif isinstance(child.value, ast.IfExp):
                    flow_type = "conditional"

                elif isinstance(child.value, (ast.BinOp, ast.UnaryOp, ast.Call, ast.Compare)):
                    flow_type = "transformed"
                else:
                    flow_type = "other"

                param_flows.append(
                    {
                        "line": child.lineno,
                        "function_name": func_name,
                        "parameter_name": param,
                        "return_expr": return_expr,
                        "flow_type": flow_type,
                        "is_async": is_async,
                    }
                )

    seen = set()
    deduped = []
    for pf in param_flows:
        key = (pf["line"], pf["function_name"], pf["parameter_name"])
        if key not in seen:
            seen.add(key)
            deduped.append(pf)

    if len(param_flows) != len(deduped):
        logger.debug(
            f"Parameter flows deduplication: {len(param_flows)} -> {len(deduped)} ({len(param_flows) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_closure_captures(context: FileContext) -> list[dict[str, Any]]:
    """Identify variables captured from outer scope (closures)."""
    closures = []

    if not isinstance(context.tree, ast.AST):
        return closures

    function_hierarchy = {}
    function_locals = {}
    analyzed_functions = set()

    def analyze_function(node, parent_func="global"):
        """Recursively analyze function definitions."""

        if node in analyzed_functions:
            return
        analyzed_functions.add(node)

        func_name = node.name if hasattr(node, "name") else f"lambda_{node.lineno}"

        function_hierarchy[func_name] = parent_func

        local_vars = set()

        if hasattr(node, "args") and node.args:
            for arg in node.args.args:
                local_vars.add(arg.arg)
            if node.args.vararg:
                local_vars.add(node.args.vararg.arg)
            if node.args.kwarg:
                local_vars.add(node.args.kwarg.arg)
            for arg in node.args.kwonlyargs:
                local_vars.add(arg.arg)

        if hasattr(node, "body"):
            body = node.body if isinstance(node.body, list) else [node.body]

            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            local_vars.add(target.id)

        function_locals[func_name] = local_vars

        body = node.body if hasattr(node, "body") else []
        if not isinstance(body, list):
            body = [body]

        for child in ast.walk(node):
            if (
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                and child != node
            ):
                is_direct_child = False
                for body_item in body:
                    if child in ast.walk(body_item):
                        is_direct_child = True
                        break
                if is_direct_child and child not in analyzed_functions:
                    analyzed_functions.add(child)
                    analyze_function(child, parent_func=func_name)

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        analyze_function(node, parent_func="global")

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        func_name = node.name if hasattr(node, "name") else f"lambda_{node.lineno}"
        is_lambda = isinstance(node, ast.Lambda)

        if func_name not in function_hierarchy:
            continue

        parent_func = function_hierarchy[func_name]
        if parent_func == "global":
            continue

        local_vars = function_locals.get(func_name, set())

        body = node.body if hasattr(node, "body") else []
        if not isinstance(body, list):
            body = [body]

        for child in context.walk_tree():
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                var_name = child.id

                if var_name not in local_vars and var_name not in ("self", "cls"):
                    parent_locals = function_locals.get(parent_func, set())

                    if var_name in parent_locals:
                        closures.append(
                            {
                                "line": node.lineno,
                                "inner_function": func_name,
                                "captured_variable": var_name,
                                "outer_function": parent_func,
                                "is_lambda": is_lambda,
                            }
                        )

    seen = set()
    deduped = []
    for closure in closures:
        key = (closure["line"], closure["inner_function"], closure["captured_variable"])
        if key not in seen:
            seen.add(key)
            deduped.append(closure)

    if len(closures) != len(deduped):
        logger.debug(
            f"Closure captures deduplication: {len(closures)} -> {len(deduped)} ({len(closures) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_nonlocal_access(context: FileContext) -> list[dict[str, Any]]:
    """Extract nonlocal variable modifications."""
    nonlocal_accesses = []

    if not isinstance(context.tree, ast.AST):
        return nonlocal_accesses

    function_ranges = []
    nonlocals_by_function = {}

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        func_name = node.name
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges.append((func_name, node.lineno, node.end_lineno or node.lineno))

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

    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                in_function = find_containing_function(node.lineno)

                if (
                    in_function != "global"
                    and in_function in nonlocals_by_function
                    and var_name in nonlocals_by_function[in_function]
                ):
                    nonlocal_accesses.append(
                        {
                            "line": node.lineno,
                            "variable_name": var_name,
                            "access_type": "write",
                            "in_function": in_function,
                        }
                    )

    seen = set()
    deduped = []
    for nl in nonlocal_accesses:
        key = (nl["line"], nl["variable_name"], nl["access_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(nl)

    if len(nonlocal_accesses) != len(deduped):
        logger.debug(
            f"Nonlocal accesses deduplication: {len(nonlocal_accesses)} -> {len(deduped)} ({len(nonlocal_accesses) - len(deduped)} duplicates removed)"
        )

    return deduped


def extract_conditional_calls(context: FileContext) -> list[dict[str, Any]]:
    """Extract function calls made under conditional execution (Week 2 Data Flow)."""
    if not context.tree:
        return []

    conditional_calls = []

    function_ranges = {}
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        function_ranges[(node.lineno, node.end_lineno)] = node.name

    def get_function_name(line: int) -> str:
        """Get function name for a given line number."""
        for (start, end), name in function_ranges.items():
            if start <= line <= end:
                return name
        return "global"

    def get_condition_expr(test_node) -> str | None:
        """Extract condition expression as string."""
        try:
            return ast.unparse(test_node)
        except Exception:
            return None

    def walk_conditional_block(
        parent_node, condition_expr: str | None, condition_type: str, nesting_level: int
    ):
        """Walk conditional block and extract function calls."""
        if not hasattr(parent_node, "body"):
            return

        for node in parent_node.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call_node = node.value
                func_name = None
                if isinstance(call_node.func, ast.Name):
                    func_name = call_node.func.id
                elif isinstance(call_node.func, ast.Attribute):
                    func_name = ast.unparse(call_node.func)

                if func_name:
                    in_function = get_function_name(node.lineno)
                    conditional_calls.append(
                        {
                            "line": node.lineno,
                            "function_call": func_name,
                            "condition_expr": condition_expr,
                            "condition_type": condition_type,
                            "in_function": in_function,
                            "nesting_level": nesting_level,
                        }
                    )

            elif isinstance(node, ast.Assign) or isinstance(node, ast.Return) and node.value:
                if isinstance(node.value, ast.Call):
                    call_node = node.value
                    func_name = None
                    if isinstance(call_node.func, ast.Name):
                        func_name = call_node.func.id
                    elif isinstance(call_node.func, ast.Attribute):
                        func_name = ast.unparse(call_node.func)

                    if func_name:
                        in_function = get_function_name(node.lineno)
                        conditional_calls.append(
                            {
                                "line": node.lineno,
                                "function_call": func_name,
                                "condition_expr": condition_expr,
                                "condition_type": condition_type,
                                "in_function": in_function,
                                "nesting_level": nesting_level,
                            }
                        )

            elif isinstance(node, ast.If):
                nested_condition = get_condition_expr(node.test)
                walk_conditional_block(node, nested_condition, "if", nesting_level + 1)
                for elif_node in node.orelse:
                    if isinstance(elif_node, ast.If):
                        elif_condition = get_condition_expr(elif_node.test)
                        walk_conditional_block(elif_node, elif_condition, "elif", nesting_level + 1)
                    else:
                        walk_conditional_block(
                            type("obj", (), {"body": [elif_node]})(),
                            condition_expr,
                            "else",
                            nesting_level + 1,
                        )

    for node in context.find_nodes(ast.If):
        condition = get_condition_expr(node.test)

        is_guard = False
        if len(node.body) == 1 and isinstance(
            node.body[0], (ast.Return, ast.Raise, ast.Continue, ast.Break)
        ):
            is_guard = True

        condition_type = "guard" if is_guard else "if"
        walk_conditional_block(node, condition, condition_type, 1)

        for _i, elif_node in enumerate(node.orelse):
            if isinstance(elif_node, ast.If):
                elif_condition = get_condition_expr(elif_node.test)
                walk_conditional_block(elif_node, elif_condition, "elif", 1)
            else:
                if hasattr(elif_node, "lineno"):
                    walk_conditional_block(
                        type("obj", (), {"body": [elif_node]})(), condition, "else", 1
                    )

    seen = set()
    deduped = []
    for call in conditional_calls:
        key = (call["line"], call["function_call"])
        if key not in seen:
            seen.add(key)
            deduped.append(call)

    if len(conditional_calls) != len(deduped):
        logger.debug(
            f"Conditional calls deduplication: {len(conditional_calls)} -> {len(deduped)} ({len(conditional_calls) - len(deduped)} duplicates removed)"
        )

    return deduped
