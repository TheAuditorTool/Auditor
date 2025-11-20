"""NodeIndex: O(1) node lookup by type for AST trees."""
import ast
from collections import defaultdict
from typing import Union, Type, List, Tuple, Dict


class NodeIndex:
    """Fast AST node lookup by type.

    Builds index in single pass, enables O(1) queries.
    """

    def __init__(self, tree: ast.AST):
        """Build index of all nodes by type.

        Args:
            tree: AST tree to index
        """
        self._index: Dict[Type[ast.AST], List[ast.AST]] = defaultdict(list)
        self._line_index: Dict[Type[ast.AST], Dict[int, List[ast.AST]]] = defaultdict(lambda: defaultdict(list))

        # Single walk to build index
        for node in ast.walk(tree):
            node_type = type(node)
            self._index[node_type].append(node)

            # Also index by line number for range queries
            if hasattr(node, 'lineno'):
                self._line_index[node_type][node.lineno].append(node)

    def find_nodes(self, node_type: Union[Type[ast.AST], Tuple[Type[ast.AST], ...]]) -> List[ast.AST]:
        """Get all nodes of given type(s) with O(1) lookup.

        Args:
            node_type: Single type or tuple of types to find

        Returns:
            List of matching nodes
        """
        if isinstance(node_type, tuple):
            # Handle multiple types
            result = []
            for nt in node_type:
                result.extend(self._index.get(nt, []))
            return result
        return self._index.get(node_type, []).copy()

    def find_nodes_in_range(self, node_type: Type[ast.AST], start_line: int, end_line: int) -> List[ast.AST]:
        """Get nodes of type within line range.

        Args:
            node_type: Type of nodes to find
            start_line: Start line (inclusive)
            end_line: End line (inclusive)

        Returns:
            List of matching nodes in range
        """
        result = []
        type_lines = self._line_index.get(node_type, {})
        for line_num in range(start_line, end_line + 1):
            result.extend(type_lines.get(line_num, []))
        return result

    def get_stats(self) -> Dict[str, int]:
        """Get count of each node type.

        Returns:
            Dictionary mapping node type names to counts
        """
        return {
            node_type.__name__: len(nodes)
            for node_type, nodes in self._index.items()
        }
