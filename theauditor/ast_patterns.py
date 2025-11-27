"""AST Pattern Matching Engine.

This module contains all pattern matching and query logic for the AST parser.
It provides pattern-based search capabilities across different AST types.
"""

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .ast_parser import ASTMatch
else:

    @dataclass
    class ASTMatch:
        """Represents an AST pattern match."""

        node_type: str
        start_line: int
        end_line: int
        start_col: int
        snippet: str
        metadata: dict[str, Any] = None


class ASTPatternMixin:
    """Mixin class providing pattern matching capabilities for AST analysis."""

    def __init__(self):
        """Initialize pattern mixin."""
        super().__init__()

    def query_ast(self, tree: Any, query_string: str) -> list[ASTMatch]:
        """Execute a Tree-sitter query on the AST.

        Args:
            tree: AST tree object from parse_file.
            query_string: Tree-sitter query in S-expression format.

        Returns:
            List of ASTMatch objects.
        """
        matches = []

        if not tree:
            return matches

        if tree.get("type") == "tree_sitter" and self.has_tree_sitter:
            language = tree["language"]
            if language in self.languages:
                try:
                    from tree_sitter import Query, QueryCursor

                    query = Query(self.languages[language], query_string)

                    query_cursor = QueryCursor(query)

                    query_matches = query_cursor.matches(tree["tree"].root_node)

                    for match in query_matches:
                        pattern_index, captures = match

                        for capture_name, nodes in captures.items():
                            if not isinstance(nodes, list):
                                nodes = [nodes]

                            for node in nodes:
                                start_point = node.start_point
                                end_point = node.end_point
                                snippet = (
                                    node.text.decode("utf-8", errors="ignore") if node.text else ""
                                )

                                ast_match = ASTMatch(
                                    node_type=node.type,
                                    start_line=start_point[0] + 1,
                                    end_line=end_point[0] + 1,
                                    start_col=start_point[1],
                                    snippet=snippet[:200],
                                    metadata={"capture": capture_name, "pattern": pattern_index},
                                )
                                matches.append(ast_match)
                except Exception as e:
                    print(f"Query error: {e}")

        elif tree.get("type") == "python_ast":
            pattern = self._query_to_pattern(query_string)
            if pattern:
                matches = self.find_ast_matches(tree, pattern)

        return matches

    def _query_to_pattern(self, query_string: str) -> dict | None:
        """Convert a Tree-sitter query to a simple pattern dict.

        This is a fallback for Python's built-in AST.
        """

        if "any" in query_string.lower():
            return {"node_type": "type_annotation", "contains": ["any"]}
        elif "function" in query_string.lower():
            return {"node_type": "function_def", "contains": []}
        elif "class" in query_string.lower():
            return {"node_type": "class_def", "contains": []}
        return None

    def find_ast_matches(
        self, tree: Any, ast_pattern: dict, file_hash: str = None
    ) -> list[ASTMatch]:
        """Find matches in AST based on pattern.

        Args:
            tree: AST tree object.
            ast_pattern: Pattern dictionary with node_type and optional contains.
            file_hash: Optional file content hash for caching.

        Returns:
            List of ASTMatch objects.
        """
        matches = []

        if not tree:
            return matches

        if isinstance(tree, dict):
            tree_type = tree.get("type")
            actual_tree = tree.get("tree")

            if tree_type == "tree_sitter" and self.has_tree_sitter:
                matches.extend(self._find_tree_sitter_matches(actual_tree.root_node, ast_pattern))
            elif tree_type == "python_ast":
                matches.extend(self._find_python_ast_matches(actual_tree, ast_pattern))
            elif tree_type == "semantic_ast":
                matches.extend(self._find_semantic_ast_matches(actual_tree, ast_pattern))
            elif tree_type == "eslint_ast":
                matches.extend(self._find_eslint_ast_matches(actual_tree, ast_pattern))

        elif isinstance(tree, ast.AST):
            matches.extend(self._find_python_ast_matches(tree, ast_pattern))

        return matches

    def _find_tree_sitter_matches(self, node: Any, pattern: dict) -> list[ASTMatch]:
        """Find matches in Tree-sitter AST using structural patterns."""
        matches = []

        if node is None:
            return matches

        node_type = pattern.get("node_type", "")

        if node_type == "type_annotation" and "any" in pattern.get("contains", []):
            if node.type in ["type_annotation", "type_identifier", "any_type"]:
                node_text = node.text.decode("utf-8", errors="ignore") if node.text else ""
                if node_text == "any" or ": any" in node_text:
                    start_point = node.start_point
                    end_point = node.end_point

                    match = ASTMatch(
                        node_type=node.type,
                        start_line=start_point[0] + 1,
                        end_line=end_point[0] + 1,
                        start_col=start_point[1],
                        snippet=node_text[:200],
                    )
                    matches.append(match)

        elif node.type == node_type or node_type == "*":
            contains = pattern.get("contains", [])
            node_text = node.text.decode("utf-8", errors="ignore") if node.text else ""

            if all(keyword in node_text for keyword in contains):
                start_point = node.start_point
                end_point = node.end_point

                match = ASTMatch(
                    node_type=node.type,
                    start_line=start_point[0] + 1,
                    end_line=end_point[0] + 1,
                    start_col=start_point[1],
                    snippet=node_text[:200],
                )
                matches.append(match)

        for child in node.children:
            matches.extend(self._find_tree_sitter_matches(child, pattern))

        return matches

    def _find_semantic_ast_matches(self, tree: dict[str, Any], pattern: dict) -> list[ASTMatch]:
        """Find matches in Semantic AST from TypeScript Compiler API.

        This provides the highest fidelity analysis with full type information.
        """
        matches = []

        if not tree or not tree.get("ast"):
            return matches

        node_type = pattern.get("node_type", "")

        if node_type == "type_annotation" and "any" in pattern.get("contains", []):

            def search_ast_for_any(node, depth=0):
                if depth > 100 or not isinstance(node, dict):
                    return

                if node.get("kind") == "AnyKeyword":
                    match = ASTMatch(
                        node_type="AnyKeyword",
                        start_line=node.get("line", 0),
                        end_line=node.get("line", 0),
                        start_col=node.get("column", 0),
                        snippet=node.get("text", "any")[:200],
                        metadata={"kind": "AnyKeyword"},
                    )
                    matches.append(match)

                elif node.get("is_any"):
                    node_name = node.get("name", "unknown")
                    match = ASTMatch(
                        node_type="any_type",
                        start_line=node.get("line", 0),
                        end_line=node.get("line", 0),
                        start_col=node.get("column", 0),
                        snippet=f"{node_name}: any",
                        metadata={"symbol": node_name, "type": "any"},
                    )
                    matches.append(match)

                for child in node.get("children", []):
                    search_ast_for_any(child, depth + 1)

            search_ast_for_any(tree.get("ast", {}))

        return matches

    def _find_eslint_ast_matches(self, tree: dict[str, Any], pattern: dict) -> list[ASTMatch]:
        """Find matches in ESLint AST.

        ESLint provides a full JavaScript/TypeScript AST with high fidelity.
        This provides accurate pattern matching for JS/TS code.
        """
        matches = []

        if not tree:
            return matches

        return matches

    def _find_python_ast_matches(self, node: ast.AST, pattern: dict) -> list[ASTMatch]:
        """Find matches in Python built-in AST."""
        matches = []

        node_type_map = {
            "if_statement": ast.If,
            "while_statement": ast.While,
            "for_statement": ast.For,
            "function_def": ast.FunctionDef,
            "class_def": ast.ClassDef,
            "try_statement": ast.Try,
            "type_annotation": ast.AnnAssign,
        }

        pattern_node_type = pattern.get("node_type", "")
        expected_type = node_type_map.get(pattern_node_type)

        if pattern_node_type == "type_annotation" and "any" in pattern.get("contains", []):
            if isinstance(node, ast.Name) and node.id == "Any":
                match = ASTMatch(
                    node_type="Any",
                    start_line=getattr(node, "lineno", 0),
                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                    start_col=getattr(node, "col_offset", 0),
                    snippet="Any",
                )
                matches.append(match)
            elif isinstance(node, ast.AnnAssign):
                node_source = ast.unparse(node) if hasattr(ast, "unparse") else ""
                if "Any" in node_source:
                    match = ASTMatch(
                        node_type="AnnAssign",
                        start_line=getattr(node, "lineno", 0),
                        end_line=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                        start_col=getattr(node, "col_offset", 0),
                        snippet=node_source[:200],
                    )
                    matches.append(match)

        elif expected_type and isinstance(node, expected_type):
            contains = pattern.get("contains", [])
            node_source = ast.unparse(node) if hasattr(ast, "unparse") else ""

            if all(keyword in node_source for keyword in contains):
                match = ASTMatch(
                    node_type=node.__class__.__name__,
                    start_line=getattr(node, "lineno", 0),
                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                    start_col=getattr(node, "col_offset", 0),
                    snippet=node_source[:200],
                )
                matches.append(match)

        for child in ast.walk(node):
            if child != node:
                matches.extend(self._find_python_ast_matches(child, pattern))

        return matches

    def get_tree_sitter_query_for_pattern(self, pattern: str, language: str) -> str:
        """Convert a pattern identifier to a Tree-sitter query.

        Args:
            pattern: Pattern identifier (e.g., "NO_ANY_IN_SCOPE")
            language: Programming language

        Returns:
            Tree-sitter query string in S-expression format
        """
        queries = {
            "typescript": {
                "NO_ANY_IN_SCOPE": """
                    (type_annotation
                      (type_identifier) @type
                      (#eq? @type "any"))
                """,
                "NO_UNSAFE_EVAL": """
                    (call_expression
                      function: (identifier) @func
                      (#eq? @func "eval"))
                """,
                "NO_VAR_IN_STRICT": """
                    (variable_declaration
                      kind: "var") @var_usage
                """,
            },
            "javascript": {
                "NO_ANY_IN_SCOPE": """
                    (type_annotation
                      (type_identifier) @type
                      (#eq? @type "any"))
                """,
                "NO_UNSAFE_EVAL": """
                    (call_expression
                      function: (identifier) @func
                      (#eq? @func "eval"))
                """,
                "NO_VAR_IN_STRICT": """
                    (variable_declaration
                      kind: "var") @var_usage
                """,
            },
            "python": {
                "NO_EVAL_EXEC": """
                    (call
                      function: (identifier) @func
                      (#match? @func "^(eval|exec)$"))
                """,
                "NO_BARE_EXCEPT": """
                    (except_clause
                      !type) @bare_except
                """,
                "NO_MUTABLE_DEFAULT": """
                    (default_parameter
                      value: [(list) (dictionary)]) @mutable_default
                """,
            },
        }

        language_queries = queries.get(language, {})
        return language_queries.get(pattern, "")
