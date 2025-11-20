"""AST Data Extraction Engine - Package Router.

This module provides the main ASTExtractorMixin class that routes extraction
requests to the appropriate language-specific implementation.

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
This module is part of a 3-layer extraction architecture:

1. **Indexer Layer** (indexer/__init__.py):
   - PROVIDES: file_path (absolute or relative path to source file)
   - CALLS: extractor.extract(file_info, content, tree)
   - STORES: Database records with file_path context

2. **Extractor Layer** (indexer/extractors/*.py):
   - RECEIVES: file_info dict (contains 'path' key)
   - DELEGATES: To ast_parser.extract_X(tree) methods
   - RETURNS: Extracted data WITHOUT file_path keys

3. **Implementation Layer** (ast_extractors/*_impl.py):
   - RECEIVES: AST tree only
   - EXTRACTS: Data with 'line' numbers and content
   - RETURNS: List[Dict] with keys like 'line', 'name', 'type', etc.
   - MUST NOT: Include 'file' or 'file_path' keys in returned dicts

CRITICAL: All extraction functions in *_impl.py files return data with 'line'
numbers only. The indexer layer adds file_path when storing to database.

Example flow for object literals:
  indexer/__init__.py:952 → Uses file_path parameter
  javascript.py:290 → Calls ast_parser.extract_object_literals(tree)
  __init__.py:277 → Routes to typescript_impl.extract_typescript_object_literals()
  typescript_impl.py:1293 → Returns {"line": 42, "variable_name": "x", ...}
  indexer/__init__.py:952 → Stores with add_object_literal(file_path, obj_lit['line'], ...)

WHY: This separation ensures single source of truth for file paths and prevents
architectural violations where implementations incorrectly attempt to track files.
"""


import os
from typing import Any, List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path

# Import all implementations
# CRITICAL: python_impl is aliased to the NEW modular python/ package (Phase 2.1 refactor)
# OLD: python_impl.py (1594-line monolithic file) - DEPRECATED, kept for rollback only
# NEW: python/ package (core_extractors.py, framework_extractors.py, cfg_extractor.py, cdk_extractor.py)
# This import ensures ALL code paths (base AST parser + indexer extractors) use the same module
# See: theauditor/ast_extractors/python/__init__.py for re-export orchestration
from . import python as python_impl, typescript_impl, treesitter_impl
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
        metadata: dict[str, Any] = None


class ASTExtractorMixin:
    """Mixin class providing data extraction capabilities for AST analysis.
    
    This class acts as a pure router, delegating all extraction logic to
    language-specific implementation modules.
    """
    
    def extract_functions(self, tree: Any, language: str = None) -> list[dict]:
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
                return python_impl.extract_python_functions(context)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_functions(context)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_functions(tree, self, language)
        
        return []

    def extract_classes(self, tree: Any, language: str = None) -> list[dict]:
        """Extract class definitions from AST."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_classes(context)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_classes(context)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_classes(tree, self, language)
        
        return []

    def extract_calls(self, tree: Any, language: str = None) -> list[dict]:
        """Extract function calls from AST."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_calls(context)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_calls(context)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_calls(tree, self, language)
        
        return []

    def extract_imports(self, tree: Any, language: str = None) -> list[dict[str, Any]]:
        """Extract import statements from AST."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_imports(context)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_imports(context)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_imports(tree, self, language)
        
        return []

    def extract_exports(self, tree: Any, language: str = None) -> list[dict[str, Any]]:
        """Extract export statements from AST."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_exports(context)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_exports(context)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_exports(tree, self, language)
        
        return []

    def extract_properties(self, tree: Any, language: str = None) -> list[dict]:
        """Extract property accesses from AST (e.g., req.body, req.query).
        
        This is critical for taint analysis to find JavaScript property access patterns.
        """
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_properties(context)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_properties(context)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_properties(tree, self, language)
        
        return []

    def extract_assignments(self, tree: Any, language: str = None) -> list[dict[str, Any]]:
        """Extract variable assignments for data flow analysis."""
        if not tree:
            return []

        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)

            import os, sys
            if os.environ.get("THEAUDITOR_TRACE_DUPLICATES"):
                print(f"[TRACE] extract_assignments() tree_type={tree_type}, language={language}", file=sys.stderr)

            if tree_type == "python_ast":
                return python_impl.extract_python_assignments(context)
            elif tree_type == "semantic_ast":
                # The semantic result is nested in tree["tree"]
                result = typescript_impl.extract_typescript_assignments(tree.get("tree", {}), self)
                if os.environ.get("THEAUDITOR_TRACE_DUPLICATES"):
                    print(f"[TRACE] extract_typescript_assignments returned {len(result)} assignments", file=sys.stderr)
                return result
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_assignments(tree, self, language)

        return []

    def extract_function_calls_with_args(self, tree: Any, language: str = None) -> list[dict[str, Any]]:
        """Extract function calls with argument mapping for data flow analysis.

        This is a two-pass analysis:
        1. First pass: Find all function definitions and their parameters
        2. Second pass: Find all function calls and map arguments to parameters
        """
        if not tree:
            return []

        # DEBUG: Check tree structure
        import sys, os
        if os.environ.get("THEAUDITOR_DEBUG"):
            tree_type_debug = tree.get('type') if isinstance(tree, dict) else type(tree).__name__
            print(f"[DEBUG __init__.py:225] extract_function_calls_with_args: tree type = {tree_type_debug}", file=sys.stderr)
            if isinstance(tree, dict) and tree.get('type') == 'semantic_ast':
                if 'tree' in tree:
                    nested_keys = list(tree['tree'].keys())[:10] if isinstance(tree.get('tree'), dict) else 'not a dict'
                    print(f"[DEBUG __init__.py:225] Nested tree keys: {nested_keys}", file=sys.stderr)

        # First pass: Get all function definitions with their parameters
        function_params = self._extract_function_parameters(tree, language)

        # DEBUG: Log extracted function params
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG __init__.py:229] function_params extracted: {len(function_params)} functions", file=sys.stderr)
            if function_params:
                sample = list(function_params.items())[:3]
                print(f"[DEBUG __init__.py:229] Sample function_params: {sample}", file=sys.stderr)
            else:
                print(f"[DEBUG __init__.py:229] WARNING: function_params is EMPTY", file=sys.stderr)

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

        # DEBUG: Log result
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG __init__.py:246] calls_with_args returned: {len(calls_with_args)} calls", file=sys.stderr)
            if calls_with_args:
                sample_call = calls_with_args[0]
                print(f"[DEBUG __init__.py:246] Sample call: {sample_call}", file=sys.stderr)

        return calls_with_args

    def _extract_function_parameters(self, tree: Any, language: str = None) -> dict[str, list[str]]:
        """Extract function definitions and their parameter names.

        Returns:
            Dict mapping function_name -> list of parameter names
        """
        import sys, os
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG __init__.py:274] _extract_function_parameters called", file=sys.stderr)

        # CRITICAL FIX (Bug #3): Use global cache if available
        # The global cache is populated during batch processing (indexer/__init__.py:268-291)
        # and contains ALL function parameters from ALL JS/TS files in the project.
        # This enables cross-file parameter name resolution for taint analysis.
        if hasattr(self, 'global_function_params') and self.global_function_params:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG __init__.py:274] Using global function params cache ({len(self.global_function_params)} entries)", file=sys.stderr)
            return self.global_function_params

        # Fallback: extract from current tree only (backward compatibility for Python, non-batch files)
        if not tree:
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG __init__.py:274] WARNING: tree is None/empty, returning empty dict", file=sys.stderr)
            return {}

        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)

            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG __init__.py:274] tree_type = {tree_type}, language = {language}", file=sys.stderr)

            if tree_type == "python_ast":
                result = python_impl.extract_python_function_params(context)
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG __init__.py:274] Python extraction returned {len(result)} functions", file=sys.stderr)
                return result
            elif tree_type == "semantic_ast":
                result = typescript_impl.extract_typescript_function_params(context)
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG __init__.py:274] TypeScript extraction returned {len(result)} functions", file=sys.stderr)
                    if result:
                        sample = list(result.items())[:2]
                        print(f"[DEBUG __init__.py:274] Sample TS params: {sample}", file=sys.stderr)
                return result
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                result = treesitter_impl.extract_treesitter_function_params(tree, self, language)
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG __init__.py:274] Tree-sitter extraction returned {len(result)} functions", file=sys.stderr)
                return result

        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG __init__.py:274] WARNING: No matching tree type, returning empty dict", file=sys.stderr)

        return {}

    def extract_returns(self, tree: Any, language: str = None) -> list[dict[str, Any]]:
        """Extract return statements for data flow analysis."""
        if not tree:
            return []
        
        if isinstance(tree, dict):
            tree_type = tree.get("type")
            language = tree.get("language", language)
            
            if tree_type == "python_ast":
                return python_impl.extract_python_returns(context)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_returns(context)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_returns(tree, self, language)
        
        return []

    def extract_cfg(self, tree: Any, language: str = None) -> list[dict[str, Any]]:
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
                return python_impl.extract_python_cfg(context)
            elif tree_type == "semantic_ast":
                return typescript_impl.extract_typescript_cfg(context)
            elif tree_type == "tree_sitter" and self.has_tree_sitter:
                return treesitter_impl.extract_treesitter_cfg(tree, self, language)

        return []

    def extract_object_literals(self, tree: Any) -> list[dict[str, Any]]:
        """Extract object literal properties from AST."""
        if not tree or not isinstance(tree, dict):
            return []

        tree_type = tree.get("type")

        if tree_type == "semantic_ast":
            # The new, correct path for TypeScript/JavaScript
            return typescript_impl.extract_typescript_object_literals(context)

        elif tree_type == "python_ast":
            # Python dict literal extraction
            return python_impl.extract_python_dicts(context)

        return []

