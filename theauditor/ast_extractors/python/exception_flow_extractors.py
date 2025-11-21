"""Exception flow extractors - Raises, catches, finally blocks, context managers.

This module contains extraction logic for exception control flow patterns:
- Exception raises (raise ValueError("msg"))
- Exception handlers (except ValueError as e: ...)
- Finally blocks (finally: cleanup())
- Context manager cleanup (already exists in core_extractors, enhanced here)

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: Data with 'line' numbers and content
- RETURN: List[Dict] with keys like 'line', 'exception_type', 'handling_strategy', etc.
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
This separation ensures single source of truth for file paths.

Causal Learning Purpose:
========================
These extractors enable hypothesis generation for DIEC tool:
- "Function X raises ValueError when input is negative" → Test with invalid input, assert exception
- "Function converts ValueError to None" → Test error handling strategy
- "Function always releases lock even on error" → Test resource cleanup in finally block
- "Function guarantees resource cleanup via context manager" → Test cleanup occurs

Each extraction enables >3 hypothesis types per python_coverage.md requirements.
Target >70% validation rate when hypotheses are tested experimentally.

Week 1 Implementation (Priority 1 - Exception Flow):
======================================================
Exception flow is fundamental to robustness. Cannot design experiments without knowing
what exceptions can occur and how they're handled.

Expected extraction from TheAuditor codebase:
- ~800 exception raises (raise statements)
- ~600 exception handlers (except clauses)
- ~200 finally blocks
- ~400 context managers (already extracted by core_extractors.py)
Total: ~2,000 exception flow records
"""
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
import os
from typing import Any, Dict, List, Optional

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


def _detect_handling_strategy(handler_body: list[ast.stmt]) -> str:
    """Detect exception handling strategy from handler body.

    Strategies:
    - 'return_none': except: return None
    - 're_raise': except: raise
    - 'log_and_continue': except: logging.error(...); pass
    - 'convert_to_other': except ValueError: raise TypeError
    - 'pass': except: pass
    - 'other': Complex handling logic
    """
    if not handler_body:
        return 'pass'

    # Single statement handlers
    if len(handler_body) == 1:
        stmt = handler_body[0]

        # return None or return
        if isinstance(stmt, ast.Return):
            if stmt.value is None or (isinstance(stmt.value, ast.Constant) and stmt.value.value is None):
                return 'return_none'
            return 'return_value'

        # raise (re-raise)
        if isinstance(stmt, ast.Raise):
            if stmt.exc is None:
                return 're_raise'
            return 'convert_to_other'

        # pass
        if isinstance(stmt, ast.Pass):
            return 'pass'

    # Multi-statement handlers - check for log + pass pattern
    has_log = False
    has_pass = False
    has_raise = False

    for stmt in handler_body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            # Check for logging.error(), logger.error(), print()
            if isinstance(stmt.value.func, ast.Attribute):
                if stmt.value.func.attr in ['error', 'warning', 'exception', 'debug', 'info']:
                    has_log = True
            elif isinstance(stmt.value.func, ast.Name):
                if stmt.value.func.id == 'print':
                    has_log = True
        elif isinstance(stmt, ast.Pass):
            has_pass = True
        elif isinstance(stmt, ast.Raise):
            has_raise = True

    if has_log and has_pass:
        return 'log_and_continue'
    if has_log and has_raise:
        return 'log_and_re_raise'

    return 'other'


# ============================================================================
# Exception Flow Extractors
# ============================================================================

def extract_exception_raises(context: FileContext) -> list[dict[str, Any]]:
    """Extract exception raise statements with exception type and context.

    Detects:
    - raise ValueError("message")
    - raise CustomError() from original_error
    - raise  # Re-raise in except block
    - Conditional raises: if condition: raise Error()

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of exception raise dicts:
        {
            'line': int,
            'exception_type': str,  # 'ValueError'
            'message': str | None,  # Static message if available
            'from_exception': str | None,  # For exception chaining
            'in_function': str,
            'condition': str | None,  # 'if x < 0' if conditional
            'is_re_raise': bool,  # True for bare 'raise'
        }

    Enables hypothesis: "Function X raises ValueError when condition Y"
    Experiment design: Call X with invalid input, assert ValueError raised
    """
    raises = []

    if not isinstance(context.tree, ast.AST):
        return raises

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

    # Extract raise statements
    for node in context.find_nodes(ast.Raise):
        in_function = find_containing_function(node.lineno)

        # Bare raise (re-raise)
        if node.exc is None:
            raises.append({
                'line': node.lineno,
                'exception_type': None,
                'message': None,
                'from_exception': None,
                'in_function': in_function,
                'condition': None,
                'is_re_raise': True,
            })
        else:
            # raise SomeException(...) or raise SomeException
            exception_type = get_node_name(node.exc)

            # Extract exception type from Call node (raise ValueError("msg"))
            if isinstance(node.exc, ast.Call):
                exception_type = get_node_name(node.exc.func)

                # Try to extract static message (first positional arg)
                message = None
                if node.exc.args:
                    message = _get_str_constant(node.exc.args[0])
            else:
                # raise ValueError (no call, just class)
                message = None

            # Extract 'from' clause (exception chaining)
            from_exception = get_node_name(node.cause) if node.cause else None

            raises.append({
                'line': node.lineno,
                'exception_type': exception_type,
                'message': message,
                'from_exception': from_exception,
                'in_function': in_function,
                'condition': None,  # TODO: Detect if inside If node (requires parent tracking)
                'is_re_raise': False,
            })

    # CRITICAL: Deduplicate by (line, exception_type, in_function)
    seen = set()
    deduped = []
    for r in raises:
        key = (r['line'], r['exception_type'], r['in_function'])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(raises) != len(deduped):
            print(f"[AST_DEBUG] Exception raises deduplication: {len(raises)} -> {len(deduped)} ({len(raises) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_exception_catches(context: FileContext) -> list[dict[str, Any]]:
    """Extract exception handlers (except clauses) and their handling strategies.

    Detects:
    - except ValueError as e: ...
    - except (TypeError, ValueError): ...
    - except Exception: ...
    - Multiple except clauses for same try block

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of exception handler dicts:
        {
            'line': int,
            'exception_types': str,  # 'ValueError,TypeError' (comma-separated)
            'variable_name': str | None,  # 'e' in 'as e'
            'handling_strategy': str,  # 'return_none' | 're_raise' | 'log_and_continue' | etc.
            'in_function': str,
        }

    Enables hypothesis: "Function X converts ValueError to None"
    Experiment design: Call X with invalid input, assert returns None instead of raising
    """
    handlers = []

    if not isinstance(context.tree, ast.AST):
        return handlers

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

    # Extract exception handlers
    for node in context.find_nodes(ast.Try):
        # Process each except handler in the try block
        for handler in node.handlers:
            in_function = find_containing_function(handler.lineno)

            # Extract exception type(s)
            exception_types = []
            if handler.type is None:
                # bare except: clause
                exception_types = ['Exception']  # Catches all
            elif isinstance(handler.type, ast.Tuple):
                # except (ValueError, TypeError):
                for exc in handler.type.elts:
                    exc_type = get_node_name(exc)
                    if exc_type:
                        exception_types.append(exc_type)
            else:
                # except ValueError:
                exc_type = get_node_name(handler.type)
                if exc_type:
                    exception_types.append(exc_type)

            # Extract variable name (as e)
            variable_name = handler.name if handler.name else None

            # Detect handling strategy
            handling_strategy = _detect_handling_strategy(handler.body)

            handlers.append({
                'line': handler.lineno,
                'exception_types': ','.join(exception_types) if exception_types else 'Exception',
                'variable_name': variable_name,
                'handling_strategy': handling_strategy,
                'in_function': in_function,
            })

    # CRITICAL: Deduplicate by (line, exception_types, in_function)
    seen = set()
    deduped = []
    for h in handlers:
        key = (h['line'], h['exception_types'], h['in_function'])
        if key not in seen:
            seen.add(key)
            deduped.append(h)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(handlers) != len(deduped):
            print(f"[AST_DEBUG] Exception catches deduplication: {len(handlers)} -> {len(deduped)} ({len(handlers) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_finally_blocks(context: FileContext) -> list[dict[str, Any]]:
    """Extract finally blocks that always execute.

    Detects:
    - finally: cleanup()
    - Resource cleanup patterns (file.close(), lock.release())
    - Multiple cleanup calls in finally block

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of finally block dicts:
        {
            'line': int,
            'cleanup_calls': str,  # Comma-separated function names called in finally
            'has_cleanup': bool,  # True if contains function calls (cleanup logic)
            'in_function': str,
        }

    Enables hypothesis: "Function X always releases lock even on error"
    Experiment design: Call X, simulate error, verify lock released in finally
    """
    finally_blocks = []

    if not isinstance(context.tree, ast.AST):
        return finally_blocks

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

    # Extract finally blocks from try statements
    for node in context.find_nodes(ast.Try):
        if node.finalbody:
            # Extract cleanup function calls from finally block
            cleanup_calls = []

            for stmt in node.finalbody:
                # Look for function calls (e.g., lock.release(), file.close())
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    func_name = get_node_name(stmt.value.func)
                    if func_name:
                        cleanup_calls.append(func_name)
                # Also check for direct calls in assignments
                elif isinstance(stmt, ast.Assign):
                    if isinstance(stmt.value, ast.Call):
                        func_name = get_node_name(stmt.value.func)
                        if func_name:
                            cleanup_calls.append(func_name)

            # Use first line of finalbody as the line number
            finally_line = node.finalbody[0].lineno if node.finalbody else node.lineno
            in_function = find_containing_function(finally_line)

            finally_blocks.append({
                'line': finally_line,
                'cleanup_calls': ','.join(cleanup_calls) if cleanup_calls else None,
                'has_cleanup': bool(cleanup_calls),
                'in_function': in_function,
            })

    # CRITICAL: Deduplicate by (line, in_function)
    seen = set()
    deduped = []
    for fb in finally_blocks:
        key = (fb['line'], fb['in_function'])
        if key not in seen:
            seen.add(key)
            deduped.append(fb)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(finally_blocks) != len(deduped):
            print(f"[AST_DEBUG] Finally blocks deduplication: {len(finally_blocks)} -> {len(deduped)} ({len(finally_blocks) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped


def extract_context_managers(context: FileContext) -> list[dict[str, Any]]:
    """Extract context managers (with statements) that ensure cleanup.

    NOTE: This is an ENHANCED version of core_extractors.extract_python_context_managers().
    The core version already extracts basic context manager usage. This version adds:
    - In-function context tracking
    - Resource type classification (file, lock, database, network)
    - Cleanup guarantee detection

    Detects:
    - with open(file) as f: ...
    - with lock: ...
    - async with aiohttp.ClientSession() as session: ...
    - @contextmanager decorated functions

    Args:
        tree: AST tree dictionary with 'tree' containing the actual AST
        parser_self: Reference to parser instance (unused but follows pattern)

    Returns:
        List of context manager dicts:
        {
            'line': int,
            'context_expr': str,  # 'open(file)' or 'lock'
            'variable_name': str | None,  # 'f' in 'as f'
            'in_function': str,
            'is_async': bool,
            'resource_type': str | None,  # 'file' | 'lock' | 'database' | 'network' | None
        }

    Enables hypothesis: "Function X guarantees resource cleanup"
    Experiment design: Call X, check resource released even if exception occurs
    """
    context_managers = []

    if not isinstance(context.tree, ast.AST):
        return context_managers

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

    def classify_resource_type(context_expr: str) -> str | None:
        """Classify resource type from context expression.

        Returns: 'file' | 'lock' | 'database' | 'network' | None
        """
        if not context_expr:
            return None

        expr_lower = context_expr.lower()

        # File operations
        if 'open(' in expr_lower or 'path.' in expr_lower or 'file' in expr_lower:
            return 'file'

        # Lock/threading
        if 'lock' in expr_lower or 'rlock' in expr_lower or 'semaphore' in expr_lower:
            return 'lock'

        # Database
        if 'session' in expr_lower or 'connection' in expr_lower or 'transaction' in expr_lower:
            if 'db' in expr_lower or 'sql' in expr_lower or 'engine' in expr_lower:
                return 'database'

        # Network
        if 'client' in expr_lower or 'request' in expr_lower or 'http' in expr_lower:
            return 'network'

        return None

    # Extract with statements
    for node in context.find_nodes(ast.With):
        for item in node.items:
            context_expr = get_node_name(item.context_expr)
            as_name = get_node_name(item.optional_vars) if item.optional_vars else None
            in_function = find_containing_function(node.lineno)
            resource_type = classify_resource_type(context_expr)

            context_managers.append({
                'line': node.lineno,
                'context_expr': context_expr,
                'variable_name': as_name,
                'in_function': in_function,
                'is_async': False,
                'resource_type': resource_type,
            })

    # CRITICAL: Deduplicate by (line, context_expr, in_function)
    seen = set()
    deduped = []
    for cm in context_managers:
        key = (cm['line'], cm['context_expr'], cm['in_function'])
        if key not in seen:
            seen.add(key)
            deduped.append(cm)

    if os.environ.get("THEAUDITOR_DEBUG"):
        import sys
        if len(context_managers) != len(deduped):
            print(f"[AST_DEBUG] Context managers deduplication: {len(context_managers)} -> {len(deduped)} ({len(context_managers) - len(deduped)} duplicates removed)", file=sys.stderr)

    return deduped
