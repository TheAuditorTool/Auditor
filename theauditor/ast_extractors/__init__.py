"""AST Data Extraction Engine - Package Router.

This module provides the main ASTExtractorMixin class that routes extraction
requests to the appropriate language-specific implementation.
"""

import os
from typing import Any, List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path

# Import all implementations
from . import python_impl, typescript_impl, treesitter_impl
from .base import detect_language

# Import semantic parser if available
try:
    from ..js_semantic_parser import get_semantic_ast_batch
except ImportError:
    get_semantic_ast_batch = None

if TYPE_CHECKING:
    # For type checking only, avoid circular import
    from ..ast_parser import ASTMatch
else:
    # At runtime, ASTMatch will be available from the parent class
    @dataclass
    class ASTMatch:
        """Represents an AST pattern match."""
        node_type: str
        start_line: int
        end_line: int
        start_col: int
        snippet: str
        metadata: Dict[str, Any] = None


class ASTExtractorMixin:
    """Mixin class providing data extraction capabilities for AST analysis.
    
    This class acts as a pure router, delegating all extraction logic to
    language-specific implementation modules.
    """
    
    def extract_functions(self, tree: Any, language: str = None) -> List[Dict]:
        """Extract function definitions from AST.

        Args:
            tree: AST tree.
            language: Programming language.

        Returns:
            List of function info dictionaries.
        """
        if not tree:
            return []
        
        # Route to appropriate implementation
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_functions(tree, self)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_functions(tree, self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_functions(tree, self, language)
        
        return []

    def extract_classes(self, tree: Any, language: str = None) -> List[Dict]:
        """Extract class definitions from AST."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_classes(tree, self)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_classes(tree, self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_classes(tree, self, language)
        
        return []

    def extract_calls(self, tree: Any, language: str = None) -> List[Dict]:
        """Extract function calls from AST."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_calls(tree, self)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_calls(tree, self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_calls(tree, self, language)
        
        return []

    def extract_imports(self, tree: Any, language: str = None) -> List[Dict[str, Any]]:
        """Extract import statements from AST."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_imports(tree, self)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_imports(tree, self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_imports(tree, self, language)
        
        return []

    def extract_exports(self, tree: Any, language: str = None) -> List[Dict[str, Any]]:
        """Extract export statements from AST."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_exports(tree, self)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_exports(tree, self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_exports(tree, self, language)
        
        return []

    def extract_properties(self, tree: Any, language: str = None) -> List[Dict]:
        """Extract property accesses from AST (e.g., req.body, req.query).
        
        This is critical for taint analysis to find JavaScript property access patterns.
        """
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_properties(tree, self)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_properties(tree, self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_properties(tree, self, language)
        
        return []

    def extract_assignments(self, tree: Any, language: str = None) -> List[Dict[str, Any]]:
        """Extract variable assignments for data flow analysis."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_assignments(tree, self)
            elif tree_type == "semantic_ast":
                # The semantic result is nested in tree["tree"]
                return typescript_impl.extract_typescript_assignments(tree.get("tree", {}), self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_assignments(tree, self, language)
        
        return []

    def extract_function_calls_with_args(self, tree: Any, language: str = None) -> List[Dict[str, Any]]:
        """Extract function calls with argument mapping for data flow analysis.
        
        This is a two-pass analysis:
        1. First pass: Find all function definitions and their parameters
        2. Second pass: Find all function calls and map arguments to parameters
        """
        if not tree:
            return []
        
        # First pass: Get all function definitions with their parameters
        function_params = self._extract_function_parameters(tree, language)
        
        # Second pass: Extract calls with argument mapping
        calls_with_args = []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                calls_with_args = python_impl.extract_python_calls_with_args(tree, function_params, self)
            elif tree_type == "semantic_ast":
                calls_with_args = typescript_impl.extract_typescript_calls_with_args(tree, function_params, self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                calls_with_args = treesitter_impl.extract_treesitter_calls_with_args(
                    tree, function_params, self, language
                )
        
        return calls_with_args

    def _extract_function_parameters(self, tree: Any, language: str = None) -> Dict[str, List[str]]:
        """Extract function definitions and their parameter names.
        
        Returns:
            Dict mapping function_name -> list of parameter names
        """
        if not tree:
            return {}
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_function_params(tree, self)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_function_params(tree, self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_function_params(tree, self, language)
        
        return {}

    def extract_returns(self, tree: Any, language: str = None) -> List[Dict[str, Any]]:
        """Extract return statements for data flow analysis."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_returns(tree, self)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_returns(tree, self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_returns(tree, self, language)
        
        return []

    def extract_cfg(self, tree: Any, language: str = None) -> List[Dict[str, Any]]:
        """Extract control flow graphs for all functions in AST.

        Returns:
            List of CFG dictionaries with blocks and edges for each function
        """
        if not tree:
            return []

        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)

            if tree_type == "python_ast":
                return python_impl.extract_python_cfg(tree, self)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_cfg(tree, self)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_cfg(tree, self, language)

        return []

    def extract_object_literals(self, tree: Any) -> List[Dict[str, Any]]:
        """Extract object literal properties from AST."""
        if not tree or not isinstance(tree, dict):
            return []

        tree_type = tree.get("type")

        if tree_type == "semantic_ast":
            # The new, correct path for TypeScript/JavaScript
            return typescript_impl.extract_typescript_object_literals(tree, self)

        elif tree_type == "python_ast":
            # Python dict literal extraction
            return python_impl.extract_python_dicts(tree, self)

        return []

