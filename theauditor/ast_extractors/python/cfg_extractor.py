"""Python Control Flow Graph (CFG) extractor."""

import ast
from typing import Any

from theauditor.ast_extractors.python.utils.context import FileContext


def extract_python_cfg(context: FileContext) -> list[dict[str, Any]]:
    """Extract control flow graphs for all Python functions."""
    cfg_data = []

    if not context.tree:
        return cfg_data

    for node in context.find_nodes((ast.FunctionDef, ast.AsyncFunctionDef)):
        function_cfg = build_python_function_cfg(node)
        if function_cfg:
            cfg_data.append(function_cfg)

    return cfg_data


def build_python_function_cfg(func_node: ast.FunctionDef) -> dict[str, Any]:
    """Build control flow graph for a single Python function."""
    blocks = []
    edges = []
    block_id_counter = [0]

    def get_next_block_id():
        block_id_counter[0] += 1
        return block_id_counter[0]

    entry_block_id = get_next_block_id()
    blocks.append(
        {
            "id": entry_block_id,
            "type": "entry",
            "start_line": func_node.lineno,
            "end_line": func_node.lineno,
            "statements": [],
        }
    )

    current_block_id = entry_block_id
    exit_block_id = None

    for stmt in func_node.body:
        if current_block_id is None:
            break

        block_info = process_python_statement(stmt, current_block_id, get_next_block_id)

        if block_info:
            new_blocks, new_edges, next_block_id = block_info
            blocks.extend(new_blocks)
            edges.extend(new_edges)
            current_block_id = next_block_id

    if current_block_id:
        exit_block_id = get_next_block_id()
        blocks.append(
            {
                "id": exit_block_id,
                "type": "exit",
                "start_line": func_node.end_lineno or func_node.lineno,
                "end_line": func_node.end_lineno or func_node.lineno,
                "statements": [],
            }
        )
        edges.append({"source": current_block_id, "target": exit_block_id, "type": "normal"})

    return {"function_name": func_node.name, "blocks": blocks, "edges": edges}


def process_python_statement(
    stmt: ast.stmt, current_block_id: int, get_next_block_id
) -> tuple | None:
    """Process a statement and update CFG."""
    blocks = []
    edges = []

    if isinstance(stmt, ast.If):
        condition_block_id = get_next_block_id()
        blocks.append(
            {
                "id": condition_block_id,
                "type": "condition",
                "start_line": stmt.lineno,
                "end_line": stmt.lineno,
                "condition": ast.unparse(stmt.test) if hasattr(ast, "unparse") else "condition",
                "statements": [{"type": "if", "line": stmt.lineno}],
            }
        )

        edges.append({"source": current_block_id, "target": condition_block_id, "type": "normal"})

        then_block_id = get_next_block_id()
        blocks.append(
            {
                "id": then_block_id,
                "type": "basic",
                "start_line": stmt.body[0].lineno if stmt.body else stmt.lineno,
                "end_line": stmt.body[-1].end_lineno
                if stmt.body and hasattr(stmt.body[-1], "end_lineno")
                else stmt.lineno,
                "statements": [{"type": "statement", "line": s.lineno} for s in stmt.body],
            }
        )
        edges.append({"source": condition_block_id, "target": then_block_id, "type": "true"})

        if stmt.orelse:
            else_block_id = get_next_block_id()
            blocks.append(
                {
                    "id": else_block_id,
                    "type": "basic",
                    "start_line": stmt.orelse[0].lineno if stmt.orelse else stmt.lineno,
                    "end_line": stmt.orelse[-1].end_lineno
                    if stmt.orelse and hasattr(stmt.orelse[-1], "end_lineno")
                    else stmt.lineno,
                    "statements": [{"type": "statement", "line": s.lineno} for s in stmt.orelse],
                }
            )
            edges.append({"source": condition_block_id, "target": else_block_id, "type": "false"})

            merge_block_id = get_next_block_id()
            blocks.append(
                {
                    "id": merge_block_id,
                    "type": "merge",
                    "start_line": stmt.end_lineno if hasattr(stmt, "end_lineno") else stmt.lineno,
                    "end_line": stmt.end_lineno if hasattr(stmt, "end_lineno") else stmt.lineno,
                    "statements": [],
                }
            )
            edges.append({"source": then_block_id, "target": merge_block_id, "type": "normal"})
            edges.append({"source": else_block_id, "target": merge_block_id, "type": "normal"})

            return blocks, edges, merge_block_id
        else:
            next_block_id = get_next_block_id()
            blocks.append(
                {
                    "id": next_block_id,
                    "type": "merge",
                    "start_line": stmt.end_lineno if hasattr(stmt, "end_lineno") else stmt.lineno,
                    "end_line": stmt.end_lineno if hasattr(stmt, "end_lineno") else stmt.lineno,
                    "statements": [],
                }
            )
            edges.append({"source": condition_block_id, "target": next_block_id, "type": "false"})
            edges.append({"source": then_block_id, "target": next_block_id, "type": "normal"})

            return blocks, edges, next_block_id

    elif isinstance(stmt, (ast.While, ast.For)):
        loop_block_id = get_next_block_id()
        blocks.append(
            {
                "id": loop_block_id,
                "type": "loop_condition",
                "start_line": stmt.lineno,
                "end_line": stmt.lineno,
                "condition": ast.unparse(stmt.test if isinstance(stmt, ast.While) else stmt.iter)
                if hasattr(ast, "unparse")
                else "loop",
                "statements": [
                    {"type": "while" if isinstance(stmt, ast.While) else "for", "line": stmt.lineno}
                ],
            }
        )
        edges.append({"source": current_block_id, "target": loop_block_id, "type": "normal"})

        body_block_id = get_next_block_id()
        blocks.append(
            {
                "id": body_block_id,
                "type": "loop_body",
                "start_line": stmt.body[0].lineno if stmt.body else stmt.lineno,
                "end_line": stmt.body[-1].end_lineno
                if stmt.body and hasattr(stmt.body[-1], "end_lineno")
                else stmt.lineno,
                "statements": [{"type": "statement", "line": s.lineno} for s in stmt.body],
            }
        )
        edges.append({"source": loop_block_id, "target": body_block_id, "type": "true"})
        edges.append({"source": body_block_id, "target": loop_block_id, "type": "back_edge"})

        exit_block_id = get_next_block_id()
        blocks.append(
            {
                "id": exit_block_id,
                "type": "merge",
                "start_line": stmt.end_lineno if hasattr(stmt, "end_lineno") else stmt.lineno,
                "end_line": stmt.end_lineno if hasattr(stmt, "end_lineno") else stmt.lineno,
                "statements": [],
            }
        )
        edges.append({"source": loop_block_id, "target": exit_block_id, "type": "false"})

        return blocks, edges, exit_block_id

    elif isinstance(stmt, ast.Return):
        return_block_id = get_next_block_id()
        blocks.append(
            {
                "id": return_block_id,
                "type": "return",
                "start_line": stmt.lineno,
                "end_line": stmt.lineno,
                "statements": [{"type": "return", "line": stmt.lineno}],
            }
        )
        edges.append({"source": current_block_id, "target": return_block_id, "type": "normal"})

        return blocks, edges, None

    elif isinstance(stmt, ast.Try):
        try_block_id = get_next_block_id()
        blocks.append(
            {
                "id": try_block_id,
                "type": "try",
                "start_line": stmt.lineno,
                "end_line": stmt.body[-1].end_lineno
                if stmt.body and hasattr(stmt.body[-1], "end_lineno")
                else stmt.lineno,
                "statements": [{"type": "try", "line": stmt.lineno}],
            }
        )
        edges.append({"source": current_block_id, "target": try_block_id, "type": "normal"})

        handler_ids = []
        for handler in stmt.handlers:
            handler_block_id = get_next_block_id()
            blocks.append(
                {
                    "id": handler_block_id,
                    "type": "except",
                    "start_line": handler.lineno,
                    "end_line": handler.body[-1].end_lineno
                    if handler.body and hasattr(handler.body[-1], "end_lineno")
                    else handler.lineno,
                    "statements": [{"type": "except", "line": handler.lineno}],
                }
            )
            edges.append({"source": try_block_id, "target": handler_block_id, "type": "exception"})
            handler_ids.append(handler_block_id)

        if stmt.finalbody:
            finally_block_id = get_next_block_id()
            blocks.append(
                {
                    "id": finally_block_id,
                    "type": "finally",
                    "start_line": stmt.finalbody[0].lineno,
                    "end_line": stmt.finalbody[-1].end_lineno
                    if hasattr(stmt.finalbody[-1], "end_lineno")
                    else stmt.finalbody[0].lineno,
                    "statements": [{"type": "finally", "line": stmt.finalbody[0].lineno}],
                }
            )

            edges.append({"source": try_block_id, "target": finally_block_id, "type": "normal"})
            for handler_id in handler_ids:
                edges.append({"source": handler_id, "target": finally_block_id, "type": "normal"})

            return blocks, edges, finally_block_id
        else:
            merge_block_id = get_next_block_id()
            blocks.append(
                {
                    "id": merge_block_id,
                    "type": "merge",
                    "start_line": stmt.end_lineno if hasattr(stmt, "end_lineno") else stmt.lineno,
                    "end_line": stmt.end_lineno if hasattr(stmt, "end_lineno") else stmt.lineno,
                    "statements": [],
                }
            )
            edges.append({"source": try_block_id, "target": merge_block_id, "type": "normal"})
            for handler_id in handler_ids:
                edges.append({"source": handler_id, "target": merge_block_id, "type": "normal"})

            return blocks, edges, merge_block_id

    return None
