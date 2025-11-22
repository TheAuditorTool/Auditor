"""Python Control Flow Graph (CFG) extractor.

This module contains extraction logic for building control flow graphs from Python functions.
Matches the pattern of JavaScript's cfg_extractor.js.

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
All functions here:
- RECEIVE: AST tree only (no file path context)
- EXTRACT: CFG data with line numbers
- RETURN: List[Dict] with CFG structures
- MUST NOT: Include 'file' or 'file_path' keys in returned dicts

File path context is provided by the INDEXER layer when storing to database.
"""
from theauditor.ast_extractors.python.utils.context import FileContext


import ast
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def extract_python_cfg(context: FileContext) -> list[dict[str, Any]]:
    """Extract control flow graphs for all Python functions.

    Returns CFG data matching the database schema expectations.
    """
    cfg_data = []

    if not context.tree:
        return cfg_data

    # Find all functions and methods
    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        function_cfg = build_python_function_cfg(node)
        if function_cfg:
            cfg_data.append(function_cfg)

    return cfg_data


def build_python_function_cfg(func_node: ast.FunctionDef) -> dict[str, Any]:
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
        # Stop processing unreachable code after return statements
        # When current_block_id is None, we've hit a return and subsequent code is unreachable
        # Don't create blocks/edges with None source - they'll crash during storage
        if current_block_id is None:
            break

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
                            get_next_block_id) -> tuple | None:
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
