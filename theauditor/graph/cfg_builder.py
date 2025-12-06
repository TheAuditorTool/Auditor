"""Control Flow Graph Builder - reads CFG data from database."""

import sqlite3
from collections import defaultdict
from typing import Any

from theauditor.utils.logging import logger


class CFGBuilder:
    """Build and analyze control flow graphs from database."""

    def __init__(self, db_path: str):
        """Initialize CFG builder with database connection."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def load_file_cfgs(self, file_path: str) -> dict[str, dict[str, Any]]:
        """Batch load ALL CFG data for a file with exactly 2 queries."""
        cursor = self.conn.cursor()

        blocks_by_func = defaultdict(list)
        cursor.execute(
            """
            SELECT * FROM cfg_blocks
            WHERE file = ?
            ORDER BY function_name, start_line
        """,
            (file_path,),
        )

        for row in cursor.fetchall():
            blocks_by_func[row["function_name"]].append(
                {
                    "id": row["id"],
                    "type": row["block_type"],
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                    "condition": row["condition_expr"],
                    "statements": [],
                }
            )

        edges_by_func = defaultdict(list)
        cursor.execute(
            """
            SELECT * FROM cfg_edges
            WHERE file = ?
        """,
            (file_path,),
        )

        for row in cursor.fetchall():
            edges_by_func[row["function_name"]].append(
                {
                    "source": row["source_block_id"],
                    "target": row["target_block_id"],
                    "type": row["edge_type"],
                }
            )

        results = {}
        for func_name in blocks_by_func:
            blocks = blocks_by_func[func_name]
            edges = edges_by_func.get(func_name, [])

            if edges and not blocks:
                logger.warning(
                    f"[CFG SANITY] {file_path}::{func_name} has {len(edges)} edges but 0 blocks"
                )

            results[func_name] = {
                "function_name": func_name,
                "file": file_path,
                "blocks": blocks,
                "edges": edges,
                "metrics": self._calculate_metrics(blocks, edges),
            }

        total_blocks = sum(len(blocks_by_func[f]) for f in blocks_by_func)
        total_edges = sum(len(edges_by_func.get(f, [])) for f in blocks_by_func)
        logger.debug(
            f"[CFG] Loaded {file_path}: {len(results)} functions, "
            f"{total_blocks} blocks, {total_edges} edges"
        )

        return results

    def get_function_cfg(self, file_path: str, function_name: str) -> dict[str, Any]:
        """Get control flow graph for a specific function."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT * FROM cfg_blocks
            WHERE file = ? AND function_name = ?
            ORDER BY start_line
        """,
            (file_path, function_name),
        )

        blocks = []
        block_map = {}
        for row in cursor.fetchall():
            block = {
                "id": row["id"],
                "type": row["block_type"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "condition": row["condition_expr"],
                "statements": [],
            }
            blocks.append(block)
            block_map[row["id"]] = block

        for block in blocks:
            cursor.execute(
                """
                SELECT * FROM cfg_block_statements
                WHERE block_id = ?
                ORDER BY line
            """,
                (block["id"],),
            )

            for row in cursor.fetchall():
                block["statements"].append(
                    {
                        "type": row["statement_type"],
                        "line": row["line"],
                        "text": row["statement_text"],
                    }
                )

        cursor.execute(
            """
            SELECT * FROM cfg_edges
            WHERE file = ? AND function_name = ?
        """,
            (file_path, function_name),
        )

        edges = []
        for row in cursor.fetchall():
            edges.append(
                {
                    "source": row["source_block_id"],
                    "target": row["target_block_id"],
                    "type": row["edge_type"],
                }
            )

        if edges and not blocks:
            logger.warning(
                f"[CFG SANITY] {file_path}::{function_name} has {len(edges)} edges but 0 blocks"
            )

        logger.debug(
            f"[CFG] Loaded {file_path}::{function_name}: {len(blocks)} blocks, {len(edges)} edges"
        )

        return {
            "function_name": function_name,
            "file": file_path,
            "blocks": blocks,
            "edges": edges,
            "metrics": self._calculate_metrics(blocks, edges),
        }

    def get_all_functions(self, file_path: str | None = None) -> list[dict[str, str]]:
        """Get list of all functions with CFG data."""
        cursor = self.conn.cursor()

        if file_path:
            cursor.execute(
                """
                SELECT DISTINCT file, function_name, COUNT(*) as block_count
                FROM cfg_blocks
                WHERE file = ?
                GROUP BY file, function_name
            """,
                (file_path,),
            )
        else:
            cursor.execute("""
                SELECT DISTINCT file, function_name, COUNT(*) as block_count
                FROM cfg_blocks
                GROUP BY file, function_name
            """)

        functions = []
        for row in cursor.fetchall():
            functions.append(
                {
                    "file": row["file"],
                    "function_name": row["function_name"],
                    "block_count": row["block_count"],
                }
            )

        return functions

    def analyze_complexity(
        self, file_path: str | None = None, threshold: int = 10
    ) -> list[dict[str, Any]]:
        """Find functions with high cyclomatic complexity."""
        cursor = self.conn.cursor()
        complex_functions = []

        if file_path:
            files = [file_path]
        else:
            cursor.execute("SELECT DISTINCT file FROM cfg_blocks")
            files = [row["file"] for row in cursor.fetchall()]

        for f in files:
            file_cfgs = self.load_file_cfgs(f)

            for func_name, cfg in file_cfgs.items():
                complexity = cfg["metrics"]["cyclomatic_complexity"]

                if complexity >= threshold:
                    valid_starts = [
                        b["start_line"] for b in cfg["blocks"] if b["start_line"] is not None
                    ]
                    valid_ends = [b["end_line"] for b in cfg["blocks"] if b["end_line"] is not None]
                    start_line = min(valid_starts) if valid_starts else 0
                    end_line = max(valid_ends) if valid_ends else 0

                    complex_functions.append(
                        {
                            "file": f,
                            "function": func_name,
                            "complexity": complexity,
                            "start_line": start_line,
                            "end_line": end_line,
                            "block_count": len(cfg["blocks"]),
                            "edge_count": len(cfg["edges"]),
                            "has_loops": cfg["metrics"]["has_loops"],
                            "max_nesting": cfg["metrics"]["max_nesting_depth"],
                        }
                    )

        complex_functions.sort(key=lambda x: x["complexity"], reverse=True)
        return complex_functions

    def find_dead_code(self, file_path: str | None = None) -> list[dict[str, Any]]:
        """Find unreachable code blocks."""
        cursor = self.conn.cursor()
        dead_blocks = []

        if file_path:
            files = [file_path]
        else:
            cursor.execute("SELECT DISTINCT file FROM cfg_blocks")
            files = [row["file"] for row in cursor.fetchall()]

        for f in files:
            file_cfgs = self.load_file_cfgs(f)

            for func_name, cfg in file_cfgs.items():
                unreachable = self._find_unreachable_blocks(cfg["blocks"], cfg["edges"])

                for block_id in unreachable:
                    block = next((b for b in cfg["blocks"] if b["id"] == block_id), None)
                    if block and block["type"] not in ["entry", "exit"]:
                        dead_blocks.append(
                            {
                                "file": f,
                                "function": func_name,
                                "block_id": block_id,
                                "block_type": block["type"],
                                "start_line": block["start_line"],
                                "end_line": block["end_line"],
                            }
                        )

        return dead_blocks

    def _calculate_metrics(self, blocks: list[dict], edges: list[dict]) -> dict[str, Any]:
        """Calculate CFG metrics."""

        cyclomatic = len(edges) - len(blocks) + 2

        has_loops = any(e["type"] == "back_edge" for e in edges)

        max_nesting = self._calculate_max_nesting(blocks, edges)

        decision_points = sum(1 for b in blocks if b["type"] in ["condition", "loop_condition"])

        return {
            "cyclomatic_complexity": cyclomatic,
            "has_loops": has_loops,
            "max_nesting_depth": max_nesting,
            "decision_points": decision_points,
            "block_count": len(blocks),
            "edge_count": len(edges),
        }

    def _find_unreachable_blocks(self, blocks: list[dict], edges: list[dict]) -> set[int]:
        """Find blocks that cannot be reached from entry."""

        graph = defaultdict(list)
        for edge in edges:
            graph[edge["source"]].append(edge["target"])

        entry_blocks = [b["id"] for b in blocks if b["type"] == "entry"]
        if not entry_blocks:
            return set()

        reachable = set()
        stack = entry_blocks.copy()

        while stack:
            current = stack.pop()
            if current not in reachable:
                reachable.add(current)
                stack.extend(graph[current])

        all_blocks = {b["id"] for b in blocks}
        unreachable = all_blocks - reachable

        return unreachable

    def _calculate_max_nesting(self, blocks: list[dict], edges: list[dict]) -> int:
        """Calculate maximum nesting depth in the CFG."""

        graph = defaultdict(list)
        for edge in edges:
            graph[edge["source"]].append(edge["target"])

        max_depth = 0
        entry_blocks = [b["id"] for b in blocks if b["type"] == "entry"]

        if not entry_blocks:
            return 0

        queue = [(entry_blocks[0], 0)]
        visited = set()

        while queue:
            block_id, depth = queue.pop(0)

            if block_id in visited:
                continue
            visited.add(block_id)

            block = next((b for b in blocks if b["id"] == block_id), None)
            if not block:
                continue

            new_depth = depth
            if block["type"] in ["condition", "loop_condition", "try"]:
                new_depth = depth + 1
                max_depth = max(max_depth, new_depth)

            for neighbor in graph[block_id]:
                if neighbor not in visited:
                    queue.append((neighbor, new_depth))

        return max_depth

    def get_execution_paths(
        self, file_path: str, function_name: str, max_paths: int = 100
    ) -> list[list[int]]:
        """Get all execution paths through a function."""
        cfg = self.get_function_cfg(file_path, function_name)

        graph = defaultdict(list)
        for edge in cfg["edges"]:
            if edge["type"] != "back_edge":
                graph[edge["source"]].append(edge["target"])

        entry_blocks = [b["id"] for b in cfg["blocks"] if b["type"] == "entry"]
        exit_blocks = [b["id"] for b in cfg["blocks"] if b["type"] in ["exit", "return"]]

        if not entry_blocks or not exit_blocks:
            return []

        paths = []
        stack = [(entry_blocks[0], [entry_blocks[0]])]

        while stack and len(paths) < max_paths:
            current, path = stack.pop()

            if current in exit_blocks:
                paths.append(path)
                continue

            for neighbor in graph[current]:
                if neighbor not in path:
                    stack.append((neighbor, path + [neighbor]))

        return paths

    def export_dot(self, file_path: str, function_name: str) -> str:
        """Export CFG as Graphviz DOT format."""
        cfg = self.get_function_cfg(file_path, function_name)

        dot_lines = ["digraph CFG {"]
        dot_lines.append("  rankdir=TB;")
        dot_lines.append("  node [shape=box];")

        for block in cfg["blocks"]:
            start = block["start_line"] if block["start_line"] is not None else "?"
            end = block["end_line"] if block["end_line"] is not None else "?"
            label = f"{block['type']}\\n{start}-{end}"
            if block["condition"]:
                label += f"\\n{block['condition'][:20]}..."

            color = "lightblue"
            if block["type"] == "entry":
                color = "lightgreen"
            elif block["type"] in ["exit", "return"]:
                color = "lightcoral"
            elif block["type"] in ["condition", "loop_condition"]:
                color = "lightyellow"

            dot_lines.append(f'  {block["id"]} [label="{label}", fillcolor={color}, style=filled];')

        for edge in cfg["edges"]:
            label = edge["type"]
            style = "solid"
            if edge["type"] == "back_edge":
                style = "dashed"
            elif edge["type"] in ["true", "false"]:
                label = "T" if edge["type"] == "true" else "F"

            dot_lines.append(
                f'  {edge["source"]} -> {edge["target"]} [label="{label}", style={style}];'
            )

        dot_lines.append("}")

        return "\n".join(dot_lines)

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
