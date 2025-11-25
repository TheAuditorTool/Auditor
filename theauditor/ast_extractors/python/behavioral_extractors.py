"""Behavioral pattern extractors - Recursion, generators, properties, dynamic attributes.

This module contains extraction logic for behavioral patterns:
- Recursion patterns (direct, mutual, tail recursion)
- Generator yield patterns (extends core_extractors.py generators)
- Property access patterns (computed properties, validated setters)
- Dynamic attribute access (__getattr__, __setattr__, __getattribute__)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'recursion_type', 'property_name', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
This separation ensures single source of truth for file paths.

Causal Learning Purpose:
========================
These extractors enable hypothesis generation for DIEC tool:
- "Function X uses recursion with base case Y" → Test recursive behavior
- "Generator X yields when condition Y" → Test lazy evaluation
- "Property X computes value rather than storing" → Test computed properties
- "Class uses dynamic attribute interception" → Test __getattr__ behavior

Each extraction enables >3 hypothesis types per python_coverage.md requirements.
Target >70% validation rate when hypotheses are tested experimentally.

Week 3 Implementation (Priority 5 - Behavioral):
=================================================
Behavioral patterns reveal algorithm characteristics that can only be verified through testing.

Expected extraction from TheAuditor codebase:
- ~80 recursion patterns (direct, mutual, tail)
- ~200 generator yields (enhanced from existing extractor)
- ~150 property patterns
- ~10 dynamic attribute patterns
Total: ~430 behavioral pattern records
"""
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
import os
from typing import Any

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
# Behavioral Pattern Extractors
# ============================================================================

def extract_recursion_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Detect recursion patterns including direct, mutual, and tail recursion.

    Detects:
    - Direct recursion: function calls itself
    - Mutual recursion: function A calls B, B calls A
    - Tail recursion: recursive call is last operation (return recursive_call())
    - Base cases: conditions that stop recursion

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of recursion pattern dicts:
        {
            'line': int,
            'function_name': str,
            'recursion_type': str,  # 'direct' | 'tail' | 'mutual'
            'calls_function': str,  # Function being called (same as function_name for direct)
            'base_case_line': int | None,  # Line number of base case condition
            'is_async': bool,
        }

    Enables hypothesis: "Function X uses recursion with base case Y"
    Experiment design: Call X with known input, verify recursive behavior and termination
    """
    recursion_patterns = []

    if not isinstance(context.tree, ast.AST):
        return recursion_patterns

    # Build map of function definitions and their call sites
    function_definitions = {}  # function_name → (node, is_async)
    function_calls = {}  # function_name → [(line, called_function)]

    # First pass: collect all function definitions
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        func_name = node.name
        is_async = isinstance(node, ast.AsyncFunctionDef)
        function_definitions[func_name] = (node, is_async)

    # Second pass: find all function calls within each function
    for func_name, (func_node, is_async) in function_definitions.items():
        calls_in_function = []

        # Walk the function body to find calls
        for child in context.find_nodes(ast.Call):
            called_func = get_node_name(child.func)
            if called_func:
                # Extract simple function name (strip module paths)
                if '.' in called_func:
                    called_func = called_func.split('.')[-1]
                calls_in_function.append((child.lineno, called_func))

        function_calls[func_name] = calls_in_function

    # Third pass: analyze recursion patterns
    for func_name, (func_node, is_async) in function_definitions.items():
        calls_in_func = function_calls.get(func_name, [])

        # Check for direct recursion (function calls itself)
        direct_recursive_calls = [(line, called) for line, called in calls_in_func if called == func_name]

        for call_line, called_func in direct_recursive_calls:
            # Check if this is tail recursion
            is_tail = False

            # Find Return nodes in function
            for return_node in context.find_nodes(ast.Return):
                if return_node.value and isinstance(return_node.value, ast.Call):
                    # Check if return calls the same function
                    returned_func = get_node_name(return_node.value.func)
                    if returned_func and func_name in returned_func:
                        is_tail = True
                        break

            recursion_type = 'tail' if is_tail else 'direct'

            # Try to find base case (if/elif with return or raise)
            base_case_line = None
            for child in context.find_nodes(ast.If):
                # Check if if body has return (potential base case)
                for stmt in child.body:
                    if isinstance(stmt, ast.Return):
                        base_case_line = child.lineno
                        break
                if base_case_line:
                    break

            recursion_patterns.append({
                'line': call_line,
                'function_name': func_name,
                'recursion_type': recursion_type,
                'calls_function': func_name,
                'base_case_line': base_case_line,
                'is_async': is_async,
            })

    # Fourth pass: detect mutual recursion (A calls B, B calls A)
    analyzed_pairs = set()

    for func_a in function_definitions:
        calls_from_a = function_calls.get(func_a, [])

        for line_a, func_b in calls_from_a:
            if func_b not in function_definitions:
                continue

            if func_a == func_b:
                continue  # Skip direct recursion (already handled)

            # Check if func_b calls func_a back
            calls_from_b = function_calls.get(func_b, [])
            calls_back_to_a = [(line, called) for line, called in calls_from_b if called == func_a]

            if calls_back_to_a:
                # Mutual recursion detected
                pair = tuple(sorted([func_a, func_b]))
                if pair not in analyzed_pairs:
                    analyzed_pairs.add(pair)

                    is_async_a = function_definitions[func_a][1]

                    recursion_patterns.append({
                        'line': line_a,
                        'function_name': func_a,
                        'recursion_type': 'mutual',
                        'calls_function': func_b,
                        'base_case_line': None,  # Mutual recursion base cases harder to detect
                        'is_async': is_async_a,
                    })

    # CRITICAL: Deduplicate by (line, function_name, calls_function)
    seen = set()
    deduped = []
    for rp in recursion_patterns:
        key = (rp['line'], rp['function_name'], rp['calls_function'])
        if key not in seen:
            seen.add(key)
            deduped.append(rp)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(recursion_patterns) != len(deduped):
            print(f"[AST_DEBUG] Recursion patterns deduplication: {len(recursion_patterns)} -> {len(deduped)} ({len(recursion_patterns) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_generator_yields(context: FileContext) -> list[dict[str, Any]]:
    """Extract generator yield patterns (ENHANCED from core_extractors.py).

    NOTE: core_extractors.py:998-1097 already extracts basic generators.
    This extractor ENHANCES that by adding:
    - Yield conditions (if x > 0: yield value)
    - Yield expressions (what is being yielded)
    - Yield from delegation tracking

    Detects:
    - Simple yield: yield value
    - Conditional yield: if condition: yield value
    - Yield from: yield from other_generator()
    - Yield in loops: for x in data: yield x

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of generator yield dicts:
        {
            'line': int,
            'generator_function': str,
            'yield_type': str,  # 'yield' | 'yield_from'
            'yield_expr': str,  # Expression being yielded
            'condition': str | None,  # Condition if inside if statement
            'in_loop': bool,  # True if yield is inside a loop
        }

    Enables hypothesis: "Generator X yields when condition Y"
    Experiment design: Iterate generator, verify yield conditions and values
    """
    yields = []

    if not isinstance(context.tree, ast.AST):
        return yields

    # Build function ranges and loop ranges
    function_ranges = []  # List of (name, start, end)
    loop_ranges = []  # List of (start, end)

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            function_ranges.append((node.name, node.lineno, node.end_lineno or node.lineno))

    def find_containing_function(line_no):
        """Find the function containing this line."""
        for fname, start, end in function_ranges:
            if start <= line_no <= end:
                return fname
        return "global"

    def is_in_loop(line_no):
        """Check if line is inside a loop."""
        for start, end in loop_ranges:
            if start <= line_no <= end:
                return True
        return False

    # Extract yield expressions
    for node in context.find_nodes(ast.Yield):
        generator_function = find_containing_function(node.lineno)
        if generator_function == "global":
            continue  # Yield outside function (syntax error, skip)

        yield_expr = get_node_name(node.value) if node.value else None
        in_loop = is_in_loop(node.lineno)

        yields.append({
            'line': node.lineno,
            'generator_function': generator_function,
            'yield_type': 'yield',
            'yield_expr': yield_expr,
            'condition': None,  # TODO: Detect parent If node (requires parent tracking)
            'in_loop': in_loop,
        })

    # CRITICAL: Deduplicate by (line, generator_function, yield_type)
    seen = set()
    deduped = []
    for y in yields:
        key = (y['line'], y['generator_function'], y['yield_type'])
        if key not in seen:
            seen.add(key)
            deduped.append(y)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(yields) != len(deduped):
            print(f"[AST_DEBUG] Generator yields deduplication: {len(yields)} -> {len(deduped)} ({len(yields) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_property_patterns(context: FileContext) -> list[dict[str, Any]]:
    """Extract property patterns including computed properties and validated setters.

    Detects:
    - @property getters (computed properties)
    - @property.setter setters (with validation)
    - @property.deleter deleters
    - Computed properties (getters with logic, not just return self._x)

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of property pattern dicts:
        {
            'line': int,
            'property_name': str,
            'access_type': str,  # 'getter' | 'setter' | 'deleter'
            'in_class': str,  # Class name containing property
            'has_computation': bool,  # True if getter has computation (not just return self._x)
            'has_validation': bool,  # True if setter has validation (if/raise)
        }

    Enables hypothesis: "Property X computes value rather than returning stored attribute"
    Experiment design: Access property, verify computation occurs vs simple attribute return
    """
    properties = []

    if not isinstance(context.tree, ast.AST):
        return properties

    # Build class ranges
    class_ranges = {}  # class_name → (start, end)

    for node in context.find_nodes(ast.ClassDef):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            class_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    def find_containing_class(line_no):
        """Find the class containing this line."""
        for cname, (start, end) in class_ranges.items():
            if start <= line_no <= end:
                return cname
        return None

    # Extract property decorators
    for node in context.find_nodes(ast.FunctionDef):
        # Check for @property decorator
        is_property_getter = False
        is_property_setter = False
        is_property_deleter = False

        for decorator in node.decorator_list:
            dec_name = get_node_name(decorator)
            if dec_name:
                if dec_name == 'property':
                    is_property_getter = True
                elif '.setter' in dec_name:
                    is_property_setter = True
                elif '.deleter' in dec_name:
                    is_property_deleter = True

        if not (is_property_getter or is_property_setter or is_property_deleter):
            continue

        property_name = node.name
        in_class = find_containing_class(node.lineno)

        if not in_class:
            continue  # Property must be in a class

        # Analyze getter for computation
        has_computation = False
        if is_property_getter:
            # Check if getter just returns self._property (simple)
            # vs has computation (complex)
            for child in context.find_nodes(ast.Return):
                if child.value:
                    # Simple return: return self._x
                    if isinstance(child.value, ast.Attribute):
                        if isinstance(child.value.value, ast.Name) and child.value.value.id == 'self':
                            # Check if returned attribute is just _property_name
                            if child.value.attr == f"_{property_name}":
                                has_computation = False
                            else:
                                has_computation = True
                    # Any other return expression = computation
                    elif isinstance(child.value, (ast.BinOp, ast.Call, ast.Compare, ast.IfExp)):
                        has_computation = True

        # Analyze setter for validation
        has_validation = False
        if is_property_setter:
            # Check for validation (if statement with raise)
            for child in context.find_nodes(ast.If):
                # Check if if body has raise
                for stmt in child.body:
                    if isinstance(stmt, ast.Raise):
                        has_validation = True
                        break
                if has_validation:
                    break

        # Determine access type
        if is_property_getter:
            access_type = 'getter'
        elif is_property_setter:
            access_type = 'setter'
        else:
            access_type = 'deleter'

        properties.append({
            'line': node.lineno,
            'property_name': property_name,
            'access_type': access_type,
            'in_class': in_class,
            'has_computation': has_computation,
            'has_validation': has_validation,
        })

    # CRITICAL: Deduplicate by (line, property_name, access_type)
    seen = set()
    deduped = []
    for prop in properties:
        key = (prop['line'], prop['property_name'], prop['access_type'])
        if key not in seen:
            seen.add(key)
            deduped.append(prop)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(properties) != len(deduped):
            print(f"[AST_DEBUG] Property patterns deduplication: {len(properties)} -> {len(deduped)} ({len(properties) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_dynamic_attributes(context: FileContext) -> list[dict[str, Any]]:
    """Extract dynamic attribute access patterns (__getattr__, __setattr__, __getattribute__).

    Detects:
    - __getattr__ implementation (fallback attribute access)
    - __setattr__ implementation (attribute assignment interception)
    - __getattribute__ implementation (all attribute access interception)
    - __delattr__ implementation (attribute deletion)

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of dynamic attribute dicts:
        {
            'line': int,
            'method_name': str,  # '__getattr__' | '__setattr__' | '__getattribute__' | '__delattr__'
            'in_class': str,  # Class name containing method
            'has_delegation': bool,  # True if method delegates to another object
            'has_validation': bool,  # True if method validates (for setattr)
        }

    Enables hypothesis: "Class uses dynamic attribute interception"
    Experiment design: Access/set attributes on instance, verify interception occurs
    """
    dynamic_attrs = []

    if not isinstance(context.tree, ast.AST):
        return dynamic_attrs

    # Build class ranges
    class_ranges = {}  # class_name → (start, end)

    for node in context.find_nodes(ast.ClassDef):
        if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            class_ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)

    def find_containing_class(line_no):
        """Find the class containing this line."""
        for cname, (start, end) in class_ranges.items():
            if start <= line_no <= end:
                return cname
        return None

    # Target magic methods
    DYNAMIC_METHODS = {'__getattr__', '__setattr__', '__getattribute__', '__delattr__'}

    # Extract dynamic attribute methods
    for node in context.find_nodes(ast.FunctionDef):
        if node.name not in DYNAMIC_METHODS:
            continue

        in_class = find_containing_class(node.lineno)
        if not in_class:
            continue  # Must be in a class

        # Analyze for delegation pattern (accessing self._data or similar)
        has_delegation = False
        for child in context.find_nodes(ast.Attribute):
            if isinstance(child.value, ast.Name) and child.value.id == 'self':
                # Check for self._data, self._attrs, etc.
                if child.attr.startswith('_'):
                    has_delegation = True
                    break

        # Analyze for validation (if/raise in setattr)
        has_validation = False
        if node.name == '__setattr__':
            for child in context.find_nodes(ast.If):
                for stmt in child.body:
                    if isinstance(stmt, ast.Raise):
                        has_validation = True
                        break
                if has_validation:
                    break

        dynamic_attrs.append({
            'line': node.lineno,
            'method_name': node.name,
            'in_class': in_class,
            'has_delegation': has_delegation,
            'has_validation': has_validation,
        })

    # CRITICAL: Deduplicate by (line, method_name, in_class)
    seen = set()
    deduped = []
    for da in dynamic_attrs:
        key = (da['line'], da['method_name'], da['in_class'])
        if key not in seen:
            seen.add(key)
            deduped.append(da)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(dynamic_attrs) != len(deduped):
            print(f"[AST_DEBUG] Dynamic attributes deduplication: {len(dynamic_attrs)} -> {len(deduped)} ({len(dynamic_attrs) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped
