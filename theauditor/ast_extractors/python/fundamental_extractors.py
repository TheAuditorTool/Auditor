"""Fundamental Python pattern extractors - Core language constructs.

This module contains extraction logic for fundamental Python patterns:
- Comprehensions (list, dict, set, generator)
- Lambda functions with closure detection
- Slice operations (start:stop:step)
- Tuple operations (pack/unpack)
- Unpacking patterns (extended unpacking)
- None handling patterns
- Truthiness patterns
- String formatting (f-strings, %, format())

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with pattern-specific keys
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
This separation ensures single source of truth for file paths.

Week 1 Implementation (Python Coverage V2):
============================================
Implements 25 patterns for Python fundamentals:
- Comprehensions: All 4 types with nesting and filter detection
- Lambda functions: With closure variable capture
- Slices: All slice notation patterns
- Tuples: Pack and unpack operations
- Unpacking: Extended unpacking with *rest patterns
- None patterns: is None vs == None detection
- String formatting: All format types (f-string, %, format(), Template)

Expected extraction from TheAuditor codebase:
- ~200 comprehensions (list/dict/set/generator)
- ~100 lambda functions
- ~150 slice operations
- ~300 tuple operations
- ~50 unpacking patterns
- ~200 None patterns
- ~100 string formatting patterns
Total: ~1,100 fundamental pattern records
"""

import ast
import logging
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext

from ..base import get_node_name

logger = logging.getLogger(__name__)


def _get_str_constant(node: ast.AST | None) -> str | None:
    """Return string value for constant nodes.

    Handles both Python 3.8+ ast.Constant and legacy ast.Str nodes.
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _get_node_text(node: ast.AST) -> str:
    """Convert AST node to approximate source text.

    This is a best-effort reconstruction. For accurate source text,
    use ast.get_source_segment() with original source code.
    """
    try:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Attribute):
            return f"{_get_node_text(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            func_name = _get_node_text(node.func)
            return f"{func_name}(...)"
        elif isinstance(node, ast.BinOp):
            left = _get_node_text(node.left)
            right = _get_node_text(node.right)
            op_map = {
                ast.Add: "+",
                ast.Sub: "-",
                ast.Mult: "*",
                ast.Div: "/",
                ast.FloorDiv: "//",
                ast.Mod: "%",
                ast.Pow: "**",
            }
            op_symbol = op_map.get(type(node.op), "?")
            return f"{left} {op_symbol} {right}"
        else:
            return f"<{type(node).__name__}>"
    except Exception:
        return "<unknown>"


def _find_containing_function(node: ast.AST, function_ranges: list) -> str:
    """Find the function containing this node.

    Args:
        node: AST node to locate
        function_ranges: List of (name, start, end) tuples

    Returns:
        Function name or 'global'
    """
    if not hasattr(node, "lineno"):
        return "global"

    line_no = node.lineno
    for fname, start, end in function_ranges:
        if start <= line_no <= end:
            return fname
    return "global"


def _detect_closure_captures(
    lambda_node: ast.Lambda, function_ranges: list, all_nodes: list[ast.AST]
) -> list[str]:
    """Detect variables captured from outer scope in lambda.

    Args:
        lambda_node: The lambda AST node
        function_ranges: List of function ranges for context
        all_nodes: All AST nodes in the tree (for scope analysis)

    Returns:
        List of variable names captured from outer scope
    """

    lambda_params = set()
    if lambda_node.args:
        for arg in lambda_node.args.args:
            lambda_params.add(arg.arg)
        if lambda_node.args.vararg:
            lambda_params.add(lambda_node.args.vararg.arg)
        if lambda_node.args.kwarg:
            lambda_params.add(lambda_node.args.kwarg.arg)

    referenced_names = set()
    for node in ast.walk(lambda_node.body):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            referenced_names.add(node.id)

    builtins = {
        "True",
        "False",
        "None",
        "len",
        "range",
        "str",
        "int",
        "float",
        "list",
        "dict",
        "set",
        "tuple",
        "bool",
    }

    captured = referenced_names - lambda_params - builtins
    return sorted(captured)


def extract_comprehensions(context: FileContext) -> list[dict[str, Any]]:
    """Extract all comprehension types from Python code.

    Detects:
    - List comprehensions: [x for x in items]
    - Dict comprehensions: {k: v for k, v in items}
    - Set comprehensions: {x for x in items}
    - Generator expressions: (x for x in items)

    Also detects:
    - Nested comprehensions (nesting_level)
    - Filter conditions (has_filter, filter_expr)
    - Multiple iteration sources

    Args:
        tree: AST tree dictionary with 'tree' key containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of comprehension dicts:
        {
            'line': int,
            'comp_type': str,  # 'list' | 'dict' | 'set' | 'generator'
            'result_expr': str,  # Expression being collected
            'iteration_var': str,  # Primary iteration variable
            'iteration_source': str,  # What we're iterating over
            'has_filter': bool,  # Has 'if' condition
            'filter_expr': str,  # Filter condition if present
            'nesting_level': int,  # 1 for simple, 2+ for nested
            'in_function': str,  # Containing function name
        }

    Enables curriculum: Chapter 9 - Comprehensions and generators
    """
    comprehensions = []

    if not isinstance(context.tree, ast.AST):
        return comprehensions

    function_ranges = context.function_ranges

    def calculate_nesting_level(comp_node):
        """Calculate comprehension nesting depth."""
        level = 1
        for child in ast.walk(comp_node):
            if child == comp_node:
                continue
            if isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                level = 2
                break
        return level

    for node in context.walk_tree():
        comp_data = None

        if isinstance(node, ast.ListComp):
            comp_data = {
                "line": node.lineno,
                "comp_type": "list",
                "result_expr": _get_node_text(node.elt),
                "nesting_level": calculate_nesting_level(node),
                "in_function": _find_containing_function(node, function_ranges),
            }

        elif isinstance(node, ast.DictComp):
            key_text = _get_node_text(node.key)
            value_text = _get_node_text(node.value)
            comp_data = {
                "line": node.lineno,
                "comp_type": "dict",
                "result_expr": f"{key_text}: {value_text}",
                "nesting_level": calculate_nesting_level(node),
                "in_function": _find_containing_function(node, function_ranges),
            }

        elif isinstance(node, ast.SetComp):
            comp_data = {
                "line": node.lineno,
                "comp_type": "set",
                "result_expr": _get_node_text(node.elt),
                "nesting_level": calculate_nesting_level(node),
                "in_function": _find_containing_function(node, function_ranges),
            }

        elif isinstance(node, ast.GeneratorExp):
            comp_data = {
                "line": node.lineno,
                "comp_type": "generator",
                "result_expr": _get_node_text(node.elt),
                "nesting_level": calculate_nesting_level(node),
                "in_function": _find_containing_function(node, function_ranges),
            }

        if comp_data and hasattr(node, "generators") and node.generators:
            gen = node.generators[0]

            if isinstance(gen.target, ast.Name):
                comp_data["iteration_var"] = gen.target.id
            elif isinstance(gen.target, ast.Tuple):
                var_names = []
                for elt in gen.target.elts:
                    if isinstance(elt, ast.Name):
                        var_names.append(elt.id)
                comp_data["iteration_var"] = ", ".join(var_names)
            else:
                comp_data["iteration_var"] = _get_node_text(gen.target)

            comp_data["iteration_source"] = _get_node_text(gen.iter)

            if gen.ifs:
                comp_data["has_filter"] = True

                filter_parts = [_get_node_text(if_clause) for if_clause in gen.ifs]
                comp_data["filter_expr"] = " and ".join(filter_parts)
            else:
                comp_data["has_filter"] = False
                comp_data["filter_expr"] = None

            comprehensions.append(comp_data)

    return comprehensions


def extract_lambda_functions(context: FileContext) -> list[dict[str, Any]]:
    """Extract lambda function definitions with closure detection.

    Detects:
    - Lambda expressions: lambda x: x + 1
    - Multi-parameter lambdas: lambda x, y: x + y
    - Closure captures: lambda x: x + outer_var
    - Usage context: map, filter, sorted, direct assignment

    Args:
        tree: AST tree dictionary with 'tree' key
        parser_self: Parser instance (unused)

    Returns:
        List of lambda dicts:
        {
            'line': int,
            'parameters': List[str],  # ['x', 'y']
            'parameter_count': int,
            'body': str,  # Body expression as text
            'captures_closure': bool,  # True if references outer variables
            'captured_vars': List[str],  # Variables from outer scope
            'used_in': str,  # 'map' | 'filter' | 'sorted_key' | 'assignment' | 'argument'
            'in_function': str,
        }

    Enables curriculum: Chapter 8 - Lambda functions and closures
    """
    lambda_functions = []

    if not isinstance(context.tree, ast.AST):
        return lambda_functions

    function_ranges = context.function_ranges
    all_nodes = list(ast.walk(context.tree))

    for node in all_nodes:
        if not isinstance(node, ast.Lambda):
            continue

        parameters = []
        if node.args:
            for arg in node.args.args:
                parameters.append(arg.arg)
            if node.args.vararg:
                parameters.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg:
                parameters.append(f"**{node.args.kwarg.arg}")

        captured_vars = _detect_closure_captures(node, function_ranges, all_nodes)

        usage_context = "assignment"

        for parent in all_nodes:
            for _child_field, child_value in ast.iter_fields(parent):
                if isinstance(child_value, list):
                    if node in child_value:
                        if isinstance(parent, ast.Call):
                            func_name = get_node_name(parent.func)
                            if func_name == "map":
                                usage_context = "map"
                            elif func_name == "filter":
                                usage_context = "filter"
                            elif func_name == "sorted" or func_name == "sort":
                                for keyword in parent.keywords:
                                    if keyword.arg == "key" and keyword.value == node:
                                        usage_context = "sorted_key"
                            else:
                                usage_context = "argument"
                        break
                elif child_value == node:
                    if isinstance(parent, ast.Call):
                        usage_context = "argument"
                    break

        lambda_data = {
            "line": node.lineno,
            "parameters": parameters,
            "parameter_count": len(parameters),
            "body": _get_node_text(node.body),
            "captures_closure": len(captured_vars) > 0,
            "captured_vars": captured_vars,
            "used_in": usage_context,
            "in_function": _find_containing_function(node, function_ranges),
        }

        lambda_functions.append(lambda_data)

    return lambda_functions


def extract_slice_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract slice operations (start:stop:step patterns).

    Detects:
    - Simple slices: list[1:10]
    - Step slices: list[::2]
    - Negative indices: list[-5:]
    - Slice assignments: list[0:5] = [1, 2, 3]

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of slice dicts:
        {
            'line': int,
            'target': str,  # Variable being sliced
            'has_start': bool,
            'has_stop': bool,
            'has_step': bool,
            'is_assignment': bool,
            'in_function': str,
        }
    """
    slices = []

    if not isinstance(context.tree, ast.AST):
        return slices

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Subscript):
        if isinstance(node.slice, ast.Slice):
            slice_data = {
                "line": node.lineno,
                "target": _get_node_text(node.value),
                "has_start": node.slice.lower is not None,
                "has_stop": node.slice.upper is not None,
                "has_step": node.slice.step is not None,
                "is_assignment": isinstance(node.ctx, ast.Store),
                "in_function": _find_containing_function(node, function_ranges),
            }
            slices.append(slice_data)

    return slices


def extract_tuple_operations(context: FileContext) -> list[dict[str, Any]]:
    """Extract tuple pack/unpack operations.

    Detects:
    - Tuple literals: (1, 2, 3)
    - Tuple packing: x = 1, 2, 3
    - Tuple unpacking: a, b, c = tuple_var

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of tuple operation dicts:
        {
            'line': int,
            'operation': str,  # 'pack' | 'unpack' | 'literal'
            'element_count': int,
            'in_function': str,
        }
    """
    tuple_ops = []

    if not isinstance(context.tree, ast.AST):
        return tuple_ops

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Tuple):
        element_count = len(node.elts)

        if isinstance(node.ctx, ast.Store):
            operation = "unpack"
        elif isinstance(node.ctx, ast.Load):
            operation = "literal"
        else:
            operation = "pack"

        tuple_data = {
            "line": node.lineno,
            "operation": operation,
            "element_count": element_count,
            "in_function": _find_containing_function(node, function_ranges),
        }
        tuple_ops.append(tuple_data)

    return tuple_ops


def extract_unpacking_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract extended unpacking patterns (a, *rest, b = ...).

    Detects:
    - Extended unpacking: a, *rest, b = [1, 2, 3, 4, 5]
    - Nested unpacking: (a, (b, c)) = (1, (2, 3))
    - List unpacking: [a, b, c] = some_list

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of unpacking pattern dicts:
        {
            'line': int,
            'unpack_type': str,  # 'tuple' | 'list' | 'extended' | 'nested'
            'target_count': int,
            'has_rest': bool,  # True if has *rest
            'in_function': str,
        }
    """
    unpacking = []

    if not isinstance(context.tree, ast.AST):
        return unpacking

    function_ranges = context.function_ranges

    def has_starred(node):
        """Check if unpacking has *rest pattern."""
        if isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                if isinstance(elt, ast.Starred):
                    return True

                if has_starred(elt):
                    return True
        return False

    def is_nested(node):
        """Check if unpacking is nested."""
        if isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                if isinstance(elt, (ast.Tuple, ast.List)):
                    return True
        return False

    for node in context.find_nodes(ast.Assign):
        for target in node.targets:
            if isinstance(target, (ast.Tuple, ast.List)):
                target_count = len(target.elts)

                if is_nested(target):
                    unpack_type = "nested"
                elif has_starred(target):
                    unpack_type = "extended"
                elif isinstance(target, ast.List):
                    unpack_type = "list"
                else:
                    unpack_type = "tuple"

                unpacking_data = {
                    "line": node.lineno,
                    "unpack_type": unpack_type,
                    "target_count": target_count,
                    "has_rest": has_starred(target),
                    "in_function": _find_containing_function(node, function_ranges),
                }
                unpacking.append(unpacking_data)

    return unpacking


def extract_none_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract None handling patterns (is None vs == None).

    Detects:
    - None checks: if x is None
    - None assignments: x = None
    - None defaults: def func(x=None)
    - None returns: return None
    - Incorrect comparisons: x == None (should use 'is')

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of None pattern dicts:
        {
            'line': int,
            'pattern': str,  # 'is_none_check' | 'none_assignment' | 'none_default' | 'none_return'
            'uses_is': bool,  # True if uses 'is None' (correct)
            'in_function': str,
        }
    """
    none_patterns = []

    if not isinstance(context.tree, ast.AST):
        return none_patterns

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Compare):
        for i, op in enumerate(node.ops):
            comparator = node.comparators[i]
            if isinstance(comparator, ast.Constant) and comparator.value is None:
                none_data = {
                    "line": node.lineno,
                    "pattern": "is_none_check",
                    "uses_is": isinstance(op, (ast.Is, ast.IsNot)),
                    "in_function": _find_containing_function(node, function_ranges),
                }
                none_patterns.append(none_data)

    return none_patterns


def extract_truthiness_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract truthiness patterns (implicit bool conversion).

    Detects:
    - Implicit bool: if x:
    - Explicit bool: bool(x)
    - Short circuit: x and y, x or y

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of truthiness dicts:
        {
            'line': int,
            'pattern': str,  # 'implicit_bool' | 'explicit_bool' | 'short_circuit'
            'expression': str,
            'in_function': str,
        }
    """
    truthiness = []

    if not isinstance(context.tree, ast.AST):
        return truthiness

    function_ranges = context.function_ranges

    for node in context.find_nodes((ast.If, ast.While)):
        if not isinstance(node.test, (ast.Compare, ast.UnaryOp)) and not isinstance(
            node.test, ast.BoolOp
        ):
            truthiness_data = {
                "line": node.lineno,
                "pattern": "implicit_bool",
                "expression": _get_node_text(node.test),
                "in_function": _find_containing_function(node, function_ranges),
            }
            truthiness.append(truthiness_data)

    return truthiness


def extract_string_formatting(context: FileContext) -> list[dict[str, Any]]:
    """Extract string formatting patterns (f-strings, %, format()).

    Detects:
    - F-strings: f"Hello {name}"
    - %-formatting: "Hello %s" % name
    - .format(): "Hello {}".format(name)
    - Template strings: Template("Hello $name")

    Args:
        tree: AST tree dictionary
        parser_self: Parser instance (unused)

    Returns:
        List of string formatting dicts:
        {
            'line': int,
            'format_type': str,  # 'f_string' | 'percent' | 'format_method' | 'template'
            'has_expressions': bool,  # True if has expressions (f"{x + 1}")
            'var_count': int,  # Number of interpolated variables
            'in_function': str,
        }
    """
    formatting = []

    if not isinstance(context.tree, ast.AST):
        return formatting

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.JoinedStr):
        var_count = sum(1 for part in node.values if isinstance(part, ast.FormattedValue))

        has_expressions = False
        for part in node.values:
            if isinstance(part, ast.FormattedValue) and not isinstance(part.value, ast.Name):
                has_expressions = True

        formatting_data = {
            "line": node.lineno,
            "format_type": "f_string",
            "has_expressions": has_expressions,
            "var_count": var_count,
            "in_function": _find_containing_function(node, function_ranges),
        }
        formatting.append(formatting_data)

    return formatting
