"""Control flow and import extractors - Loops, conditionals, match, imports, flow control."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext


def _find_containing_function(node: ast.AST, function_ranges: list) -> str:
    """Find the function containing this node."""
    if not hasattr(node, "lineno"):
        return "global"

    line_no = node.lineno
    for fname, start, end in function_ranges:
        if start <= line_no <= end:
            return fname
    return "global"


def _calculate_nesting_level(node: ast.AST, parent_map: dict) -> int:
    """Calculate nesting level for loops and conditionals."""
    level = 0
    current = node
    while current in parent_map:
        parent = parent_map[current]
        if isinstance(parent, (ast.For, ast.AsyncFor, ast.While, ast.If)):
            level += 1
        current = parent
    return level


def extract_for_loops(context: FileContext) -> list[dict[str, Any]]:
    """Extract for loop patterns with enumerate, zip, else clause detection."""
    for_loops = []

    if not isinstance(context.tree, ast.AST):
        return for_loops

    function_ranges = context.function_ranges
    parent_map = context.parent_map

    for node in context.find_nodes(ast.For):
        loop_type = "plain"
        if isinstance(node.iter, ast.Call):
            if isinstance(node.iter.func, ast.Name):
                func_name = node.iter.func.id
                if func_name == "enumerate":
                    loop_type = "enumerate"
                elif func_name == "zip":
                    loop_type = "zip"
                elif func_name == "range":
                    loop_type = "range"
            elif isinstance(node.iter.func, ast.Attribute):
                method_name = node.iter.func.attr
                if method_name == "items":
                    loop_type = "items"
                elif method_name == "values":
                    loop_type = "values"
                elif method_name == "keys":
                    loop_type = "keys"

        target_count = 1
        if isinstance(node.target, ast.Tuple):
            target_count = len(node.target.elts)

        for_data = {
            "line": node.lineno,
            "loop_type": loop_type,
            "has_else": len(node.orelse) > 0,
            "nesting_level": _calculate_nesting_level(node, parent_map),
            "target_count": target_count,
            "in_function": _find_containing_function(node, function_ranges),
        }
        for_loops.append(for_data)

    return for_loops


def extract_while_loops(context: FileContext) -> list[dict[str, Any]]:
    """Extract while loop patterns with infinite loop detection."""
    while_loops = []

    if not isinstance(context.tree, ast.AST):
        return while_loops

    function_ranges = context.function_ranges
    parent_map = context.parent_map

    for node in context.find_nodes(ast.While):
        is_infinite = False
        if isinstance(node.test, ast.Constant):
            if node.test.value is True or node.test.value == 1:
                is_infinite = True
        elif isinstance(node.test, ast.Name) and node.test.id == "True":
            is_infinite = True

        while_data = {
            "line": node.lineno,
            "has_else": len(node.orelse) > 0,
            "is_infinite": is_infinite,
            "nesting_level": _calculate_nesting_level(node, parent_map),
            "in_function": _find_containing_function(node, function_ranges),
        }
        while_loops.append(while_data)

    return while_loops


def extract_async_for_loops(context: FileContext) -> list[dict[str, Any]]:
    """Extract async for loop patterns."""
    async_for_loops = []

    if not isinstance(context.tree, ast.AST):
        return async_for_loops

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.AsyncFor):
        target_count = 1
        if isinstance(node.target, ast.Tuple):
            target_count = len(node.target.elts)

        async_for_data = {
            "line": node.lineno,
            "has_else": len(node.orelse) > 0,
            "target_count": target_count,
            "in_function": _find_containing_function(node, function_ranges),
        }
        async_for_loops.append(async_for_data)

    return async_for_loops


def extract_if_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract if/elif/else statement patterns."""
    if_statements = []

    if not isinstance(context.tree, ast.AST):
        return if_statements

    function_ranges = context.function_ranges
    parent_map = context.parent_map

    processed = set()

    for node in context.walk_tree():
        if isinstance(node, ast.If) and node not in processed:
            chain_length = 1
            has_elif = False
            current = node

            while current.orelse:
                if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                    has_elif = True
                    chain_length += 1
                    current = current.orelse[0]
                    processed.add(current)
                else:
                    break

            has_else = len(node.orelse) > 0 and not (
                len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
            )

            has_complex_condition = isinstance(
                node.test, (ast.BoolOp, ast.Compare, ast.UnaryOp, ast.Call)
            )

            if_data = {
                "line": node.lineno,
                "has_elif": has_elif,
                "has_else": has_else,
                "chain_length": chain_length,
                "nesting_level": _calculate_nesting_level(node, parent_map),
                "has_complex_condition": has_complex_condition,
                "in_function": _find_containing_function(node, function_ranges),
            }
            if_statements.append(if_data)

    return if_statements


def extract_match_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract match/case statement patterns (Python 3.10+)."""
    match_statements = []

    if not isinstance(context.tree, ast.AST):
        return match_statements

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Match):
        case_count = len(node.cases)
        has_wildcard = False
        has_guards = False
        pattern_types = set()

        for case in node.cases:
            if isinstance(case.pattern, ast.MatchAs) and case.pattern.name is None:
                has_wildcard = True

            if case.guard is not None:
                has_guards = True

            if isinstance(case.pattern, ast.MatchValue):
                pattern_types.add("literal")
            elif isinstance(case.pattern, ast.MatchSequence):
                pattern_types.add("sequence")
            elif isinstance(case.pattern, ast.MatchMapping):
                pattern_types.add("mapping")
            elif isinstance(case.pattern, ast.MatchClass):
                pattern_types.add("class")
            elif isinstance(case.pattern, ast.MatchOr):
                pattern_types.add("or")
            elif isinstance(case.pattern, ast.MatchAs):
                pattern_types.add("as")

        match_data = {
            "line": node.lineno,
            "case_count": case_count,
            "has_wildcard": has_wildcard,
            "has_guards": has_guards,
            "pattern_types": ", ".join(sorted(pattern_types)),
            "in_function": _find_containing_function(node, function_ranges),
        }
        match_statements.append(match_data)

    return match_statements


def extract_break_continue_pass(context: FileContext) -> list[dict[str, Any]]:
    """Extract break, continue, and pass statements."""
    flow_control = []

    if not isinstance(context.tree, ast.AST):
        return flow_control

    function_ranges = context.function_ranges
    parent_map = context.parent_map

    for node in context.find_nodes((ast.Break, ast.Continue, ast.Pass)):
        if isinstance(node, ast.Break):
            statement_type = "break"
        elif isinstance(node, ast.Continue):
            statement_type = "continue"
        else:
            statement_type = "pass"

        loop_type = "none"
        current = node
        while current in parent_map:
            parent = parent_map[current]
            if isinstance(parent, (ast.For, ast.AsyncFor)):
                loop_type = "for"
                break
            elif isinstance(parent, ast.While):
                loop_type = "while"
                break
            current = parent

        flow_data = {
            "line": node.lineno,
            "statement_type": statement_type,
            "loop_type": loop_type,
            "in_function": _find_containing_function(node, function_ranges),
        }
        flow_control.append(flow_data)

    return flow_control


def extract_assert_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract assert statement patterns."""
    assert_statements = []

    if not isinstance(context.tree, ast.AST):
        return assert_statements

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Assert):
        has_message = node.msg is not None

        condition_type = "simple"
        if isinstance(node.test, ast.Compare):
            condition_type = "comparison"
        elif isinstance(node.test, ast.Call) and isinstance(node.test.func, ast.Name):
            if node.test.func.id == "isinstance":
                condition_type = "isinstance"
            elif node.test.func.id == "callable":
                condition_type = "callable"

        assert_data = {
            "line": node.lineno,
            "has_message": has_message,
            "condition_type": condition_type,
            "in_function": _find_containing_function(node, function_ranges),
        }
        assert_statements.append(assert_data)

    return assert_statements


def extract_del_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract del statement patterns."""
    del_statements = []

    if not isinstance(context.tree, ast.AST):
        return del_statements

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Delete):
        target_count = len(node.targets)

        target_type = "name"
        if node.targets:
            first_target = node.targets[0]
            if isinstance(first_target, ast.Subscript):
                target_type = "subscript"
            elif isinstance(first_target, ast.Attribute):
                target_type = "attribute"

        del_data = {
            "line": node.lineno,
            "target_type": target_type,
            "target_count": target_count,
            "in_function": _find_containing_function(node, function_ranges),
        }
        del_statements.append(del_data)

    return del_statements


def extract_import_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract import statement patterns."""
    import_statements = []

    if not isinstance(context.tree, ast.AST):
        return import_statements

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Import):
        for alias in node.names:
            import_data = {
                "line": node.lineno,
                "import_type": "import",
                "module": alias.name,
                "has_alias": alias.asname is not None,
                "is_wildcard": False,
                "relative_level": 0,
                "imported_names": alias.name,
                "in_function": _find_containing_function(node, function_ranges),
            }
            import_statements.append(import_data)

    return import_statements


def extract_with_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract with statement patterns (context managers)."""
    with_statements = []

    if not isinstance(context.tree, ast.AST):
        return with_statements

    function_ranges = context.function_ranges

    for node in context.find_nodes((ast.With, ast.AsyncWith)):
        is_async = isinstance(node, ast.AsyncWith)
        context_count = len(node.items)
        has_alias = any(item.optional_vars is not None for item in node.items)

        with_data = {
            "line": node.lineno,
            "is_async": is_async,
            "context_count": context_count,
            "has_alias": has_alias,
            "in_function": _find_containing_function(node, function_ranges),
        }
        with_statements.append(with_data)

    return with_statements
