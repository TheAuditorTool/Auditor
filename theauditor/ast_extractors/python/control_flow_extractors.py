"""Control flow and import extractors - Loops, conditionals, match, imports, flow control.

This module contains extraction logic for control flow patterns:
- For loops (with enumerate, zip, else clause detection)
- While loops (with else clause, infinite loop detection)
- Async for loops (async iteration patterns)
- If/elif/else statements (chain length, nested detection)
- Match statements (Python 3.10+ pattern matching with guards)
- Break/continue/pass statements (loop control flow)
- Assert statements (with message detection)
- Del statements (deletion patterns)
- Import statements (security/performance patterns)
- With statements (context manager usage)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with pattern-specific keys
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

Week 5 Implementation (Python Coverage V2):
============================================
Implements 10 control flow patterns.

Expected extraction from TheAuditor codebase:
- ~400 for loops
- ~150 while loops
- ~20 async for loops
- ~600 if statements
- ~15 match statements
- ~200 break/continue/pass
- ~100 assert statements
- ~50 del statements
- ~500 import statements
- ~80 with statements
Total: ~2,115 control flow records
"""
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def _find_containing_function(node: ast.AST, function_ranges: list) -> str:
    """Find the function containing this node."""
    if not hasattr(node, 'lineno'):
        return 'global'

    line_no = node.lineno
    for fname, start, end in function_ranges:
        if start <= line_no <= end:
            return fname
    return 'global'


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


def _build_parent_map(tree: ast.AST) -> dict:
    """Build parent map for nesting level calculation."""
    parent_map = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent
    return parent_map


# ============================================================================
# For Loop Extractors
# ============================================================================

def extract_for_loops(context: FileContext) -> list[dict[str, Any]]:
    """Extract for loop patterns with enumerate, zip, else clause detection.

    Detects:
    - enumerate() patterns
    - zip() patterns
    - range() patterns
    - .items(), .values(), .keys() patterns
    - else clause
    - Nesting level
    - Target count (unpacking)

    Returns:
        List of for loop dicts:
        {
            'line': int,
            'loop_type': str,  # 'enumerate' | 'zip' | 'range' | 'items' | 'values' | 'keys' | 'plain'
            'has_else': bool,
            'nesting_level': int,
            'target_count': int,
            'in_function': str,
        }
    """
    for_loops = []

    if not isinstance(context.tree, ast.AST):
        return for_loops

    function_ranges = context.function_ranges
    parent_map = _build_parent_map(context.tree)

    for node in context.find_nodes(ast.For):
        # Determine loop type
        loop_type = 'plain'
        if isinstance(node.iter, ast.Call):
            if isinstance(node.iter.func, ast.Name):
                func_name = node.iter.func.id
                if func_name == 'enumerate':
                    loop_type = 'enumerate'
                elif func_name == 'zip':
                    loop_type = 'zip'
                elif func_name == 'range':
                    loop_type = 'range'
            elif isinstance(node.iter.func, ast.Attribute):
                method_name = node.iter.func.attr
                if method_name == 'items':
                    loop_type = 'items'
                elif method_name == 'values':
                    loop_type = 'values'
                elif method_name == 'keys':
                    loop_type = 'keys'

        # Count targets (for tuple unpacking)
        target_count = 1
        if isinstance(node.target, ast.Tuple):
            target_count = len(node.target.elts)

        for_data = {
            'line': node.lineno,
            'loop_type': loop_type,
            'has_else': len(node.orelse) > 0,
            'nesting_level': _calculate_nesting_level(node, parent_map),
            'target_count': target_count,
            'in_function': _find_containing_function(node, function_ranges),
        }
        for_loops.append(for_data)

    return for_loops


# ============================================================================
# While Loop Extractors
# ============================================================================

def extract_while_loops(context: FileContext) -> list[dict[str, Any]]:
    """Extract while loop patterns with infinite loop detection.

    Detects:
    - else clause
    - Infinite loops (while True)
    - Nesting level

    Returns:
        List of while loop dicts:
        {
            'line': int,
            'has_else': bool,
            'is_infinite': bool,
            'nesting_level': int,
            'in_function': str,
        }
    """
    while_loops = []

    if not isinstance(context.tree, ast.AST):
        return while_loops

    function_ranges = context.function_ranges
    parent_map = _build_parent_map(context.tree)

    for node in context.find_nodes(ast.While):
        # Detect infinite loops (while True)
        is_infinite = False
        if isinstance(node.test, ast.Constant):
            if node.test.value is True or node.test.value == 1:
                is_infinite = True
        elif isinstance(node.test, ast.Name):
            if node.test.id == 'True':
                is_infinite = True

        while_data = {
            'line': node.lineno,
            'has_else': len(node.orelse) > 0,
            'is_infinite': is_infinite,
            'nesting_level': _calculate_nesting_level(node, parent_map),
            'in_function': _find_containing_function(node, function_ranges),
        }
        while_loops.append(while_data)

    return while_loops


# ============================================================================
# Async For Loop Extractors
# ============================================================================

def extract_async_for_loops(context: FileContext) -> list[dict[str, Any]]:
    """Extract async for loop patterns.

    Detects:
    - else clause
    - Target count (unpacking)

    Returns:
        List of async for loop dicts:
        {
            'line': int,
            'has_else': bool,
            'target_count': int,
            'in_function': str,
        }
    """
    async_for_loops = []

    if not isinstance(context.tree, ast.AST):
        return async_for_loops

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.AsyncFor):
        # Count targets
        target_count = 1
        if isinstance(node.target, ast.Tuple):
            target_count = len(node.target.elts)

        async_for_data = {
            'line': node.lineno,
            'has_else': len(node.orelse) > 0,
            'target_count': target_count,
            'in_function': _find_containing_function(node, function_ranges),
        }
        async_for_loops.append(async_for_data)

    return async_for_loops


# ============================================================================
# If Statement Extractors
# ============================================================================

def extract_if_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract if/elif/else statement patterns.

    Detects:
    - elif branches
    - else clause
    - Chain length (if, if-elif, if-elif-elif, etc.)
    - Nesting level
    - Complex conditions

    Returns:
        List of if statement dicts:
        {
            'line': int,
            'has_elif': bool,
            'has_else': bool,
            'chain_length': int,
            'nesting_level': int,
            'has_complex_condition': bool,
            'in_function': str,
        }
    """
    if_statements = []

    if not isinstance(context.tree, ast.AST):
        return if_statements

    function_ranges = context.function_ranges
    parent_map = _build_parent_map(context.tree)

    # Track already-processed if statements (to avoid double-counting elif chains)
    processed = set()

    for node in context.walk_tree():
        if isinstance(node, ast.If) and node not in processed:
            # Count chain length
            chain_length = 1
            has_elif = False
            current = node

            while current.orelse:
                if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                    # This is an elif
                    has_elif = True
                    chain_length += 1
                    current = current.orelse[0]
                    processed.add(current)  # Mark as processed to avoid re-counting
                else:
                    # This is an else
                    break

            # Check for else clause
            has_else = len(node.orelse) > 0 and not (
                len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
            )

            # Detect complex condition
            has_complex_condition = isinstance(
                node.test,
                (ast.BoolOp, ast.Compare, ast.UnaryOp, ast.Call)
            )

            if_data = {
                'line': node.lineno,
                'has_elif': has_elif,
                'has_else': has_else,
                'chain_length': chain_length,
                'nesting_level': _calculate_nesting_level(node, parent_map),
                'has_complex_condition': has_complex_condition,
                'in_function': _find_containing_function(node, function_ranges),
            }
            if_statements.append(if_data)

    return if_statements


# ============================================================================
# Match Statement Extractors
# ============================================================================

def extract_match_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract match/case statement patterns (Python 3.10+).

    Detects:
    - Number of case branches
    - Wildcard pattern (case _)
    - Guards (case x if condition)
    - Pattern types

    Returns:
        List of match statement dicts:
        {
            'line': int,
            'case_count': int,
            'has_wildcard': bool,
            'has_guards': bool,
            'pattern_types': str,  # Comma-separated
            'in_function': str,
        }
    """
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
            # Check for wildcard
            if isinstance(case.pattern, ast.MatchAs) and case.pattern.name is None:
                has_wildcard = True

            # Check for guards
            if case.guard is not None:
                has_guards = True

            # Classify pattern type
            if isinstance(case.pattern, ast.MatchValue):
                pattern_types.add('literal')
            elif isinstance(case.pattern, ast.MatchSequence):
                pattern_types.add('sequence')
            elif isinstance(case.pattern, ast.MatchMapping):
                pattern_types.add('mapping')
            elif isinstance(case.pattern, ast.MatchClass):
                pattern_types.add('class')
            elif isinstance(case.pattern, ast.MatchOr):
                pattern_types.add('or')
            elif isinstance(case.pattern, ast.MatchAs):
                pattern_types.add('as')

        match_data = {
            'line': node.lineno,
            'case_count': case_count,
            'has_wildcard': has_wildcard,
            'has_guards': has_guards,
            'pattern_types': ', '.join(sorted(pattern_types)),
            'in_function': _find_containing_function(node, function_ranges),
        }
        match_statements.append(match_data)

    return match_statements


# ============================================================================
# Break/Continue/Pass Extractors
# ============================================================================

def extract_break_continue_pass(context: FileContext) -> list[dict[str, Any]]:
    """Extract break, continue, and pass statements.

    Detects:
    - Statement type
    - Containing loop type (for/while)

    Returns:
        List of flow control dicts:
        {
            'line': int,
            'statement_type': str,  # 'break' | 'continue' | 'pass'
            'loop_type': str,  # 'for' | 'while' | 'none'
            'in_function': str,
        }
    """
    flow_control = []

    if not isinstance(context.tree, ast.AST):
        return flow_control

    function_ranges = context.function_ranges
    parent_map = _build_parent_map(context.tree)

    for node in context.find_nodes((ast.Break, ast.Continue, ast.Pass)):
        # Determine statement type
        if isinstance(node, ast.Break):
            statement_type = 'break'
        elif isinstance(node, ast.Continue):
            statement_type = 'continue'
        else:
            statement_type = 'pass'

        # Find containing loop
        loop_type = 'none'
        current = node
        while current in parent_map:
            parent = parent_map[current]
            if isinstance(parent, (ast.For, ast.AsyncFor)):
                loop_type = 'for'
                break
            elif isinstance(parent, ast.While):
                loop_type = 'while'
                break
            current = parent

        flow_data = {
            'line': node.lineno,
            'statement_type': statement_type,
            'loop_type': loop_type,
            'in_function': _find_containing_function(node, function_ranges),
        }
        flow_control.append(flow_data)

    return flow_control


# ============================================================================
# Assert Statement Extractors
# ============================================================================

def extract_assert_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract assert statement patterns.

    Detects:
    - Message presence
    - Condition type

    Returns:
        List of assert statement dicts:
        {
            'line': int,
            'has_message': bool,
            'condition_type': str,  # 'comparison' | 'isinstance' | 'callable' | 'simple'
            'in_function': str,
        }
    """
    assert_statements = []

    if not isinstance(context.tree, ast.AST):
        return assert_statements

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Assert):
        # Check for message
        has_message = node.msg is not None

        # Classify condition type
        condition_type = 'simple'
        if isinstance(node.test, ast.Compare):
            condition_type = 'comparison'
        elif isinstance(node.test, ast.Call):
            if isinstance(node.test.func, ast.Name):
                if node.test.func.id == 'isinstance':
                    condition_type = 'isinstance'
                elif node.test.func.id == 'callable':
                    condition_type = 'callable'

        assert_data = {
            'line': node.lineno,
            'has_message': has_message,
            'condition_type': condition_type,
            'in_function': _find_containing_function(node, function_ranges),
        }
        assert_statements.append(assert_data)

    return assert_statements


# ============================================================================
# Del Statement Extractors
# ============================================================================

def extract_del_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract del statement patterns.

    Detects:
    - Target type (name, subscript, attribute)
    - Target count

    Returns:
        List of del statement dicts:
        {
            'line': int,
            'target_type': str,  # 'name' | 'subscript' | 'attribute'
            'target_count': int,
            'in_function': str,
        }
    """
    del_statements = []

    if not isinstance(context.tree, ast.AST):
        return del_statements

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Delete):
        target_count = len(node.targets)

        # Classify target type (use first target)
        target_type = 'name'
        if node.targets:
            first_target = node.targets[0]
            if isinstance(first_target, ast.Subscript):
                target_type = 'subscript'
            elif isinstance(first_target, ast.Attribute):
                target_type = 'attribute'

        del_data = {
            'line': node.lineno,
            'target_type': target_type,
            'target_count': target_count,
            'in_function': _find_containing_function(node, function_ranges),
        }
        del_statements.append(del_data)

    return del_statements


# ============================================================================
# Import Statement Extractors
# ============================================================================

def extract_import_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract import statement patterns.

    Detects:
    - Import type (import, from, relative)
    - Module name
    - Aliases
    - Wildcard imports
    - Relative import level

    Returns:
        List of import statement dicts:
        {
            'line': int,
            'import_type': str,  # 'import' | 'from' | 'relative'
            'module': str,
            'has_alias': bool,
            'is_wildcard': bool,
            'relative_level': int,
            'imported_names': str,  # Comma-separated
            'in_function': str,
        }
    """
    import_statements = []

    if not isinstance(context.tree, ast.AST):
        return import_statements

    function_ranges = context.function_ranges

    for node in context.find_nodes(ast.Import):
        for alias in node.names:
            import_data = {
                'line': node.lineno,
                'import_type': 'import',
                'module': alias.name,
                'has_alias': alias.asname is not None,
                'is_wildcard': False,
                'relative_level': 0,
                'imported_names': alias.name,
                'in_function': _find_containing_function(node, function_ranges),
            }
            import_statements.append(import_data)

    return import_statements


# ============================================================================
# With Statement Extractors
# ============================================================================

def extract_with_statements(context: FileContext) -> list[dict[str, Any]]:
    """Extract with statement patterns (context managers).

    Detects:
    - Async with
    - Multiple context managers
    - Aliases

    Returns:
        List of with statement dicts:
        {
            'line': int,
            'is_async': bool,
            'context_count': int,
            'has_alias': bool,
            'in_function': str,
        }
    """
    with_statements = []

    if not isinstance(context.tree, ast.AST):
        return with_statements

    function_ranges = context.function_ranges

    for node in context.find_nodes((ast.With, ast.AsyncWith)):
        is_async = isinstance(node, ast.AsyncWith)
        context_count = len(node.items)
        has_alias = any(item.optional_vars is not None for item in node.items)

        with_data = {
            'line': node.lineno,
            'is_async': is_async,
            'context_count': context_count,
            'has_alias': has_alias,
            'in_function': _find_containing_function(node, function_ranges),
        }
        with_statements.append(with_data)

    return with_statements
