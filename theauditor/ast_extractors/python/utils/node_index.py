"""NodeIndex: O(1) node lookup by type for AST trees."""

import ast
from collections import defaultdict


class NodeIndex:
    """Fast AST node lookup by type."""

    def __init__(self, tree: ast.AST):
        """Build index of all nodes by type."""
        self._index: dict[type[ast.AST], list[ast.AST]] = defaultdict(list)
        self._line_index: dict[type[ast.AST], dict[int, list[ast.AST]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for node in ast.walk(tree):
            node_type = type(node)
            self._index[node_type].append(node)

            if hasattr(node, "lineno"):
                self._line_index[node_type][node.lineno].append(node)

    def find_nodes(self, node_type: type[ast.AST] | tuple[type[ast.AST], ...]) -> list[ast.AST]:
        """Get all nodes of given type(s) with O(1) lookup."""
        if isinstance(node_type, tuple):
            result = []
            for nt in node_type:
                result.extend(self._index.get(nt, []))
            return result
        return self._index.get(node_type, []).copy()

    def find_nodes_in_range(
        self, node_type: type[ast.AST], start_line: int, end_line: int
    ) -> list[ast.AST]:
        """Get nodes of type within line range."""
        result = []
        type_lines = self._line_index.get(node_type, {})
        for line_num in range(start_line, end_line + 1):
            result.extend(type_lines.get(line_num, []))
        return result

    def get_stats(self) -> dict[str, int]:
        """Get count of each node type."""
        return {node_type.__name__: len(nodes) for node_type, nodes in self._index.items()}
