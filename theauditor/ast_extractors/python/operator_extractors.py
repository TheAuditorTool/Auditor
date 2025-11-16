"""Operator and expression extractors - All operator types and advanced expressions.

This module contains extraction logic for operators and expressions:
- All operator types (arithmetic, comparison, logical, bitwise, membership)
- Chained comparisons (1 < x < 10)
- Ternary expressions (x if y else z)
- Walrus operators (:= assignments)
- Matrix multiplication (@)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with pattern-specific keys
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

Week 2 Implementation (Python Coverage V2):
============================================
Implements 15 operator and expression patterns:
- Binary operators: +, -, *, /, //, %, **, @
- Comparison operators: <, >, <=, >=, ==, !=, is, is not
- Logical operators: and, or, not
- Bitwise operators: &, |, ^, ~, <<, >>
- Membership tests: in, not in
- Chained comparisons: 1 < x < 10
- Ternary expressions: x if condition else y
- Walrus operators: x := expression

Expected extraction from TheAuditor codebase:
- ~500 binary operators
- ~300 comparison operators
- ~200 logical operators
- ~50 bitwise operators
- ~100 membership tests
- ~30 chained comparisons
- ~50 ternary expressions
- ~20 walrus operators
Total: ~1,250 operator pattern records
"""

import ast
import logging
from typing import Any, Dict, List, Optional

from ..base import get_node_name

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def _build_function_ranges(tree: ast.AST) -> List:
    """Build list of function ranges for context tracking."""
    function_ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                function_ranges.append((
                    node.name,
                    node.lineno,
                    node.end_lineno or node.lineno
                ))
    return function_ranges


def _find_containing_function(node: ast.AST, function_ranges: List) -> str:
    """Find the function containing this node."""
    if not hasattr(node, 'lineno'):
        return 'global'

    line_no = node.lineno
    for fname, start, end in function_ranges:
        if start <= line_no <= end:
            return fname
    return 'global'


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
    except:
        return "<unknown>"


# ============================================================================
# Operator Extractors
# ============================================================================

def extract_operators(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract all operator usage (arithmetic, comparison, logical, bitwise).

    Detects:
    - Arithmetic: +, -, *, /, //, %, **
    - Comparison: <, >, <=, >=, ==, !=
    - Logical: and, or, not
    - Bitwise: &, |, ^, ~, <<, >>
    - Matrix multiplication: @

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of operator dicts:
        {
            'line': int,
            'operator_type': str,  # 'arithmetic' | 'comparison' | 'logical' | 'bitwise' | 'unary'
            'operator': str,  # The actual operator symbol
            'in_function': str,
        }
    """
    operators = []
    actual_tree = tree.get("tree")

    if not isinstance(actual_tree, ast.AST):
        return operators

    function_ranges = _build_function_ranges(actual_tree)

    # Operator type mappings
    arithmetic_ops = {
        ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/',
        ast.FloorDiv: '//', ast.Mod: '%', ast.Pow: '**', ast.MatMult: '@',
    }

    comparison_ops = {
        ast.Lt: '<', ast.Gt: '>', ast.LtE: '<=', ast.GtE: '>=',
        ast.Eq: '==', ast.NotEq: '!=', ast.Is: 'is', ast.IsNot: 'is not',
    }

    logical_ops = {
        ast.And: 'and', ast.Or: 'or',
    }

    bitwise_ops = {
        ast.BitAnd: '&', ast.BitOr: '|', ast.BitXor: '^',
        ast.LShift: '<<', ast.RShift: '>>',
    }

    unary_ops = {
        ast.Not: 'not', ast.UAdd: '+', ast.USub: '-', ast.Invert: '~',
    }

    for node in ast.walk(actual_tree):
        # Binary operators (arithmetic, bitwise, matrix mult)
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)

            if op_type in arithmetic_ops:
                operator_data = {
                    'line': node.lineno,
                    'operator_type': 'arithmetic',
                    'operator': arithmetic_ops[op_type],
                    'in_function': _find_containing_function(node, function_ranges),
                }
                operators.append(operator_data)

            elif op_type in bitwise_ops:
                operator_data = {
                    'line': node.lineno,
                    'operator_type': 'bitwise',
                    'operator': bitwise_ops[op_type],
                    'in_function': _find_containing_function(node, function_ranges),
                }
                operators.append(operator_data)

        # Comparison operators
        elif isinstance(node, ast.Compare):
            for op in node.ops:
                op_type = type(op)
                if op_type in comparison_ops:
                    operator_data = {
                        'line': node.lineno,
                        'operator_type': 'comparison',
                        'operator': comparison_ops[op_type],
                        'in_function': _find_containing_function(node, function_ranges),
                    }
                    operators.append(operator_data)

        # Logical operators (and, or)
        elif isinstance(node, ast.BoolOp):
            op_type = type(node.op)
            if op_type in logical_ops:
                operator_data = {
                    'line': node.lineno,
                    'operator_type': 'logical',
                    'operator': logical_ops[op_type],
                    'in_function': _find_containing_function(node, function_ranges),
                }
                operators.append(operator_data)

        # Unary operators (not, -, +, ~)
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type in unary_ops:
                operator_data = {
                    'line': node.lineno,
                    'operator_type': 'unary',
                    'operator': unary_ops[op_type],
                    'in_function': _find_containing_function(node, function_ranges),
                }
                operators.append(operator_data)

    return operators


# ============================================================================
# Membership Test Extractors
# ============================================================================

def extract_membership_tests(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract membership testing (in/not in) operations.

    Detects:
    - in operator: x in list
    - not in operator: y not in dict

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of membership test dicts:
        {
            'line': int,
            'operator': str,  # 'in' | 'not in'
            'container_type': str,  # Inferred type if possible
            'in_function': str,
        }
    """
    membership_tests = []
    actual_tree = tree.get("tree")

    if not isinstance(actual_tree, ast.AST):
        return membership_tests

    function_ranges = _build_function_ranges(actual_tree)

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Compare):
            for op in node.ops:
                if isinstance(op, (ast.In, ast.NotIn)):
                    membership_data = {
                        'line': node.lineno,
                        'operator': 'in' if isinstance(op, ast.In) else 'not in',
                        'container_type': 'unknown',  # Could analyze but expensive
                        'in_function': _find_containing_function(node, function_ranges),
                    }
                    membership_tests.append(membership_data)

    return membership_tests


# ============================================================================
# Chained Comparison Extractors
# ============================================================================

def extract_chained_comparisons(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract chained comparison operations (1 < x < 10).

    Detects:
    - Chained comparisons: 1 < x < 10
    - Multiple operators: a <= b <= c

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of chained comparison dicts:
        {
            'line': int,
            'chain_length': int,  # Number of comparisons
            'operators': List[str],  # List of operators in chain
            'in_function': str,
        }
    """
    chained_comparisons = []
    actual_tree = tree.get("tree")

    if not isinstance(actual_tree, ast.AST):
        return chained_comparisons

    function_ranges = _build_function_ranges(actual_tree)

    comparison_ops = {
        ast.Lt: '<', ast.Gt: '>', ast.LtE: '<=', ast.GtE: '>=',
        ast.Eq: '==', ast.NotEq: '!=',
    }

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.Compare):
            # Chained if more than one operator
            if len(node.ops) > 1:
                operators = [comparison_ops.get(type(op), str(type(op).__name__))
                           for op in node.ops]

                chained_data = {
                    'line': node.lineno,
                    'chain_length': len(node.ops),
                    'operators': ', '.join(operators),  # Store as comma-separated string
                    'in_function': _find_containing_function(node, function_ranges),
                }
                chained_comparisons.append(chained_data)

    return chained_comparisons


# ============================================================================
# Ternary Expression Extractors
# ============================================================================

def extract_ternary_expressions(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract ternary expressions (x if condition else y).

    Detects:
    - Conditional expressions: x if y else z

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of ternary expression dicts:
        {
            'line': int,
            'has_complex_condition': bool,  # True if condition is not simple variable
            'in_function': str,
        }
    """
    ternary_expressions = []
    actual_tree = tree.get("tree")

    if not isinstance(actual_tree, ast.AST):
        return ternary_expressions

    function_ranges = _build_function_ranges(actual_tree)

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.IfExp):
            # Check if condition is complex (not just a simple variable/attribute)
            has_complex_condition = not isinstance(node.test, (ast.Name, ast.Attribute, ast.Constant))

            ternary_data = {
                'line': node.lineno,
                'has_complex_condition': has_complex_condition,
                'in_function': _find_containing_function(node, function_ranges),
            }
            ternary_expressions.append(ternary_data)

    return ternary_expressions


# ============================================================================
# Walrus Operator Extractors
# ============================================================================

def extract_walrus_operators(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract walrus operator usage (:= assignment expressions).

    Detects:
    - Assignment expressions: (x := value)
    - Common in if statements: if (n := len(items)) > 0

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of walrus operator dicts:
        {
            'line': int,
            'variable': str,  # Variable being assigned
            'used_in': str,  # 'if' | 'while' | 'comprehension' | 'expression'
            'in_function': str,
        }
    """
    walrus_operators = []
    actual_tree = tree.get("tree")

    if not isinstance(actual_tree, ast.AST):
        return walrus_operators

    function_ranges = _build_function_ranges(actual_tree)

    # Track parent nodes to determine context
    parent_map = {}
    for parent in ast.walk(actual_tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.NamedExpr):  # Walrus operator (:=)
            # Determine context
            parent = parent_map.get(node)
            if isinstance(parent, ast.If):
                used_in = 'if'
            elif isinstance(parent, ast.While):
                used_in = 'while'
            elif isinstance(parent, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                used_in = 'comprehension'
            else:
                used_in = 'expression'

            walrus_data = {
                'line': node.lineno,
                'variable': node.target.id if isinstance(node.target, ast.Name) else '<complex>',
                'used_in': used_in,
                'in_function': _find_containing_function(node, function_ranges),
            }
            walrus_operators.append(walrus_data)

    return walrus_operators


# ============================================================================
# Matrix Multiplication Extractor
# ============================================================================

def extract_matrix_multiplication(tree: Dict, parser_self) -> List[Dict[str, Any]]:
    """Extract matrix multiplication operator (@) usage.

    Detects:
    - Matrix multiplication: A @ B

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of matrix multiplication dicts:
        {
            'line': int,
            'in_function': str,
        }
    """
    matrix_mult = []
    actual_tree = tree.get("tree")

    if not isinstance(actual_tree, ast.AST):
        return matrix_mult

    function_ranges = _build_function_ranges(actual_tree)

    for node in ast.walk(actual_tree):
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.MatMult):
                matrix_data = {
                    'line': node.lineno,
                    'in_function': _find_containing_function(node, function_ranges),
                }
                matrix_mult.append(matrix_data)

    return matrix_mult
