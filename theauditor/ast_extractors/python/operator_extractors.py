"""Operator and expression extractors - All operator types and advanced expressions."""

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


def _get_node_text(node: ast.AST) -> str:
    """Convert AST node to approximate source text."""
    try:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Attribute):
            return f"{_get_node_text(node.value)}.{node.attr}"
        else:
            return f"<{type(node).__name__}>"
    except Exception:
        return "<unknown>"


def extract_operators(context: FileContext) -> list[dict[str, Any]]:
    """Extract all operator usage (arithmetic, comparison, logical, bitwise)."""
    operators = []

    if not isinstance(context.tree, ast.AST):
        return operators

    function_ranges = context.function_ranges

    arithmetic_ops = {
        ast.Add: "+",
        ast.Sub: "-",
        ast.Mult: "*",
        ast.Div: "/",
        ast.FloorDiv: "//",
        ast.Mod: "%",
        ast.Pow: "**",
        ast.MatMult: "@",
    }

    bitwise_ops = {
        ast.BitAnd: "&",
        ast.BitOr: "|",
        ast.BitXor: "^",
        ast.LShift: "<<",
        ast.RShift: ">>",
    }

    for node in context.find_nodes(ast.BinOp):
        op_type = type(node.op)

        if op_type in arithmetic_ops:
            operator_data = {
                "line": node.lineno,
                "operator_type": "arithmetic",
                "operator": arithmetic_ops[op_type],
                "in_function": _find_containing_function(node, function_ranges),
            }
            operators.append(operator_data)

        elif op_type in bitwise_ops:
            operator_data = {
                "line": node.lineno,
                "operator_type": "bitwise",
                "operator": bitwise_ops[op_type],
                "in_function": _find_containing_function(node, function_ranges),
            }
            operators.append(operator_data)

    return operators


def extract_membership_tests(context: FileContext) -> list[dict[str, Any]]:
    """Extract membership testing (in/not in) operations."""
    membership_tests = []

    if not isinstance(context.tree, ast.AST):
        return membership_tests

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Compare):
        for op in node.ops:
            if isinstance(op, (ast.In, ast.NotIn)):
                membership_data = {
                    "line": node.lineno,
                    "operator": "in" if isinstance(op, ast.In) else "not in",
                    "container_type": "unknown",
                    "in_function": _find_containing_function(node, function_ranges),
                }
                membership_tests.append(membership_data)

    return membership_tests


def extract_chained_comparisons(context: FileContext) -> list[dict[str, Any]]:
    """Extract chained comparison operations (1 < x < 10)."""
    chained_comparisons = []

    if not isinstance(context.tree, ast.AST):
        return chained_comparisons

    function_ranges = context.function_ranges

    comparison_ops = {
        ast.Lt: "<",
        ast.Gt: ">",
        ast.LtE: "<=",
        ast.GtE: ">=",
        ast.Eq: "==",
        ast.NotEq: "!=",
    }

    for node in context.find_nodes(ast.Compare):
        if len(node.ops) > 1:
            operators = [comparison_ops.get(type(op), str(type(op).__name__)) for op in node.ops]

            chained_data = {
                "line": node.lineno,
                "chain_length": len(node.ops),
                "operators": ", ".join(operators),
                "in_function": _find_containing_function(node, function_ranges),
            }
            chained_comparisons.append(chained_data)

    return chained_comparisons


def extract_ternary_expressions(context: FileContext) -> list[dict[str, Any]]:
    """Extract ternary expressions (x if condition else y)."""
    ternary_expressions = []

    if not isinstance(context.tree, ast.AST):
        return ternary_expressions

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.IfExp):
        has_complex_condition = not isinstance(node.test, (ast.Name, ast.Attribute, ast.Constant))

        ternary_data = {
            "line": node.lineno,
            "has_complex_condition": has_complex_condition,
            "in_function": _find_containing_function(node, function_ranges),
        }
        ternary_expressions.append(ternary_data)

    return ternary_expressions


def extract_walrus_operators(context: FileContext) -> list[dict[str, Any]]:
    """Extract walrus operator usage (:= assignment expressions)."""
    walrus_operators = []

    if not isinstance(context.tree, ast.AST):
        return walrus_operators

    function_ranges = context.function_ranges

    parent_map = {}
    for parent in context.walk_tree():
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent

    for node in context.find_nodes(ast.NamedExpr):
        parent = parent_map.get(node)
        if isinstance(parent, ast.If):
            used_in = "if"
        elif isinstance(parent, ast.While):
            used_in = "while"
        elif isinstance(parent, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
            used_in = "comprehension"
        else:
            used_in = "expression"

        walrus_data = {
            "line": node.lineno,
            "variable": node.target.id if isinstance(node.target, ast.Name) else "<complex>",
            "used_in": used_in,
            "in_function": _find_containing_function(node, function_ranges),
        }
        walrus_operators.append(walrus_data)

    return walrus_operators


def extract_matrix_multiplication(context: FileContext) -> list[dict[str, Any]]:
    """Extract matrix multiplication operator (@) usage."""
    matrix_mult = []

    if not isinstance(context.tree, ast.AST):
        return matrix_mult

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.BinOp):
        if isinstance(node.op, ast.MatMult):
            matrix_data = {
                "line": node.lineno,
                "in_function": _find_containing_function(node, function_ranges),
            }
            matrix_mult.append(matrix_data)

    return matrix_mult
