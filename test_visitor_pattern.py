"""
Test file to verify the AST modernizer v4 handles visitor pattern correctly.

This file contains various AST visitor patterns that should be transformed:
- visit_Str methods should have their node.s transformed to node.value
- visit_Num methods should have their node.n transformed to node.value
- from ast import Str should be removed and import ast ensured
"""

from ast import Str, Num, Bytes, NameConstant
import ast


class MyVisitor(ast.NodeVisitor):
    """Test visitor with various visit_ methods."""

    def visit_Str(self, node):
        """This should transform node.s to node.value."""
        print(node.value)  # Should become node.value
        return node.value  # Should become node.value

    def visit_Num(self, node):
        """This should transform node.n to node.value."""
        value = node.value  # Should become node.value
        if (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))):  # Should become complex isinstance check
            return node.value  # Should become node.value

    def visit_Bytes(self, node):
        """Mixed usage."""
        # These should all transform
        data = node.value  # Should become node.value
        print(f"Bytes: {node.value}")  # Should become node.value

    def visit_NameConstant(self, node):
        """Handle True/False/None constants."""
        # This doesn't have .s or .n, but isinstance checks should update
        if isinstance(node, ast.Constant):  # Should become ast.Constant
            return node.value  # Already correct


class AnotherExtractor:
    """Test non-visitor class that shouldn't be affected."""

    def extract_strings(self, tree):
        """Old-style ast.walk pattern."""
        strings = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)):  # Should transform
                strings.append(node.value)  # Should transform in this context
        return strings

    def process_item(self, item):
        """Non-AST context - should NOT transform."""
        # These should NOT be transformed (not AST context)
        if (isinstance(item, ast.Constant) and isinstance(item.value, str)):
            return item.s  # Should stay as-is (not AST node)
        if (isinstance(item, ast.Constant) and isinstance(item.value, (int, float))):
            return item.n  # Should stay as-is (not AST node)


def test_isinstance_patterns():
    """Test various isinstance patterns."""
    tree = ast.parse("x = 1")

    for node in ast.walk(tree):
        # Single type checks
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)):  # Should transform
            print(node.value)  # Should transform

        if (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))):  # Should transform
            print(node.value)  # Should transform

        # Tuple checks
        if isinstance(node, ast.Constant):  # Should become ast.Constant
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)):  # Should transform
                print(node.value)  # Should transform
            elif (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))):  # Should transform
                print(node.value)  # Should transform

        # Mixed tuple with Constant
        if isinstance(node, ast.Constant):  # Should simplify to ast.Constant
            print(node.value)  # Already correct


def test_hasattr_patterns():
    """Test hasattr patterns."""
    tree = ast.parse("'hello'")

    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)):  # Should transform to isinstance checks
            value = node.value  # Should transform

        if (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))):  # Should transform to isinstance checks
            value = node.value  # Should transform


# Edge case: function not starting with visit_ but still in AST context
def process_ast_nodes(tree):
    """This should still work with ast.walk context."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)):  # Should transform
            print(node.value)  # Should transform (in ast.walk context)


# Test indirect ast.walk pattern
def indirect_walk_pattern(tree):
    """Test indirect ast.walk assignment."""
    nodes = list(ast.walk(tree))
    for node in nodes:
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)):  # Should still work
            print(node.value)  # Should transform


if __name__ == "__main__":
    print("This is a test file for AST modernizer v4")