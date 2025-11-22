"""Python file extractor - Thin wrapper for Python AST extraction.

This module is the entry point for Python file extraction. It:
1. Builds a FileContext from the AST
2. Delegates all extraction to python_impl.py
3. Handles special cases (imports, routes, SQL, JWT, variable usage)
4. Returns the unified result

ARCHITECTURAL CONTRACT: File Path Responsibility
=================================================
This is an EXTRACTOR layer module. It:
- RECEIVES: file_info dict (contains 'path' key from indexer)
- DELEGATES: To python_impl.extract_all_python_data(context)
- RETURNS: Extracted data WITHOUT file_path keys

The INDEXER layer (indexer/__init__.py) provides file_path and stores to database.
This separation ensures single source of truth for file paths.
"""

import ast
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import BaseExtractor
from .sql import parse_sql_query
from theauditor.ast_extractors.python_impl import extract_all_python_data
from theauditor.ast_extractors.python.utils.context import build_file_context
from theauditor.ast_extractors import python as python_impl
from theauditor.ast_extractors.base import get_node_name


class PythonExtractor(BaseExtractor):
    """Extractor for Python files."""

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return ['.py', '.pyx']

    def extract(self, file_info: dict[str, Any], content: str,
                tree: Any | None = None) -> dict[str, Any]:
        """Extract all relevant information from a Python file.

        Args:
            file_info: File metadata dictionary
            content: File content
            tree: Optional pre-parsed AST tree

        Returns:
            Dictionary containing all extracted data
        """
        # ALWAYS LOG - NO DEBUG FLAG NEEDED
        import sys

        # Track processed files to detect double-processing
        if not hasattr(self.__class__, '_processed_files'):
            self.__class__._processed_files = set()

        file_path = file_info['path']
        # DEBUG: Duplicate file detection (commented out for clean merge)
        # if file_path in self.__class__._processed_files:
        #     print(f"\n{'!'*80}", file=sys.stderr)
        #     print(f"[PYTHON.PY WARNING] File processed TWICE: {file_path}", file=sys.stderr)
        #     print(f"{'!'*80}\n", file=sys.stderr)
        self.__class__._processed_files.add(file_path)

        # DEBUG: Entry logging (commented out for clean merge)
        # print(f"\n{'='*80}", file=sys.stderr)
        # print(f"[PYTHON.PY ENTRY] File: {file_path} (total files processed: {len(self.__class__._processed_files)})", file=sys.stderr)
        # print(f"[PYTHON.PY ENTRY] Content length: {len(content)} bytes", file=sys.stderr)
        # print(f"[PYTHON.PY ENTRY] Tree is None: {tree is None}", file=sys.stderr)
        # DEBUG: Log tree info (commented out for clean merge)
        # if tree:
        #     print(f"[PYTHON.PY ENTRY] Tree type: {tree.get('type') if isinstance(tree, dict) else type(tree)}", file=sys.stderr)
        #     print(f"[PYTHON.PY ENTRY] Tree keys: {list(tree.keys())[:5] if isinstance(tree, dict) else 'not dict'}", file=sys.stderr)

        # Build FileContext for optimized extraction
        context = None
        if tree and isinstance(tree, dict) and tree.get("type") == "python_ast":
            # print(f"[PYTHON.PY BUILD] Tree type matches python_ast", file=sys.stderr)
            actual_tree = tree.get("tree")
            if actual_tree:
                # print(f"[PYTHON.PY BUILD] actual_tree exists: {type(actual_tree)}", file=sys.stderr)
                try:
                    context = build_file_context(actual_tree, content, str(file_info['path']))
                    # print(f"[PYTHON.PY BUILD] ✓ Context built successfully", file=sys.stderr)
                except Exception as e:
                    # print(f"[PYTHON.PY BUILD] ✗ build_file_context FAILED: {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
            # else:
            #     print(f"[PYTHON.PY BUILD] ✗ No actual_tree in tree dict", file=sys.stderr)
        # else:
        #     if tree:
        #         tree_type = tree.get("type") if isinstance(tree, dict) else "not a dict"
        #         print(f"[PYTHON.PY BUILD] ✗ Tree check failed - type is '{tree_type}', expected 'python_ast'", file=sys.stderr)
        #     else:
        #         print(f"[PYTHON.PY BUILD] ✗ Tree is None/empty", file=sys.stderr)

        # If no context, we can't extract anything meaningful
        if not context:
            # print(f"[PYTHON.PY EXIT] ✗ No context - returning EMPTY result", file=sys.stderr)
            # print(f"{'='*80}\n", file=sys.stderr)
            return self._empty_result()

        # Delegate all extraction to python_impl
        # print(f"[PYTHON.PY DELEGATE] Calling python_impl.extract_all_python_data()", file=sys.stderr)
        result = extract_all_python_data(context)
        # print(f"[PYTHON.PY DELEGATE] ✓ Returned from python_impl", file=sys.stderr)

        # Log extraction results (commented out for clean merge)
        # print(f"[PYTHON.PY RESULT] Symbols: {len(result.get('symbols', []))}", file=sys.stderr)
        # print(f"[PYTHON.PY RESULT] Assignments: {len(result.get('assignments', []))}", file=sys.stderr)
        # print(f"[PYTHON.PY RESULT] Function calls: {len(result.get('function_calls', []))}", file=sys.stderr)
        # print(f"[PYTHON.PY RESULT] Imports: {len(result.get('imports', []))}", file=sys.stderr)

        # Resolve imports to file paths (imports themselves extracted by python_impl)
        if tree and isinstance(tree, dict):
            resolved = self._resolve_imports(file_info, tree)
            if resolved:
                result['resolved_imports'] = resolved
                # print(f"[PYTHON.PY RESULT] Resolved imports: {len(resolved)}", file=sys.stderr)

        # print(f"[PYTHON.PY EXIT] ✓ Returning result with {len(result.get('symbols', []))} symbols", file=sys.stderr)
        # print(f"{'='*80}\n", file=sys.stderr)
        return result

    def _empty_result(self) -> dict[str, Any]:
        """Return an empty result structure."""
        return {
            'imports': [],
            'routes': [],
            'symbols': [],
            'assignments': [],
            'function_calls': [],
            'returns': [],
            'variable_usage': [],
            'cfg': [],
            'object_literals': [],
            'sql_queries': [],
            'jwt_patterns': [],
            'type_annotations': [],
            'resolved_imports': {},
        }

    def _resolve_imports(self, file_info: dict[str, Any], tree: dict[str, Any]) -> dict[str, str]:
        """Resolve Python import targets to absolute module/file paths."""
        resolved: dict[str, str] = {}
        actual_tree = tree.get("tree")

        if not isinstance(actual_tree, ast.AST):
            return resolved

        # Determine current module parts from file path
        file_path = Path(file_info['path'])
        module_parts = list(file_path.with_suffix('').parts)
        package_parts = module_parts[:-1]  # directory components

        def normalize_path(path: Path) -> str:
            return str(path).replace("\\", "/")

        def module_parts_to_path(parts: list[str]) -> str | None:
            if not parts:
                return None
            candidate_file = Path(*parts).with_suffix('.py')
            candidate_init = Path(*parts) / '__init__.py'

            if (self.root_path / candidate_file).exists():
                return normalize_path(candidate_file)
            if (self.root_path / candidate_init).exists():
                return normalize_path(candidate_init)
            return None

        def resolve_dotted(module_name: str) -> str | None:
            if not module_name:
                return None
            return module_parts_to_path(module_name.split('.'))

        for node in ast.walk(actual_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    resolved_target = resolve_dotted(module_name) or module_name

                    local_name = alias.asname or module_name.split('.')[-1]

                    resolved[module_name] = resolved_target
                    resolved[local_name] = resolved_target

            elif isinstance(node, ast.ImportFrom):
                level = getattr(node, 'level', 0) or 0
                base_parts = package_parts.copy()

                if level:
                    if level <= len(base_parts):
                        base_parts = base_parts[:-level]
                    else:
                        base_parts = []

                module_name = node.module or ""
                module_name_parts = module_name.split('.') if module_name else []
                target_base = base_parts + module_name_parts

                # Resolve module itself
                module_key = '.'.join(part for part in target_base if part)
                module_path = module_parts_to_path(target_base)
                if module_key:
                    resolved[module_key] = module_path or module_key
                elif module_path:
                    resolved[module_path] = module_path

                for alias in node.names:
                    imported_name = alias.name
                    local_name = alias.asname or imported_name

                    full_parts = target_base + [imported_name]
                    symbol_path = module_parts_to_path(full_parts)

                    if symbol_path:
                        resolved_value = symbol_path
                    elif module_path:
                        resolved_value = module_path
                    elif module_key:
                        resolved_value = f"{module_key}.{imported_name}"
                    else:
                        resolved_value = local_name

                    resolved[local_name] = resolved_value

        return resolved

    def _extract_imports_ast(self, tree: dict[str, Any]) -> list[tuple]:
        """Extract imports from Python AST.

        Uses Python's ast module to accurately extract import statements,
        avoiding false matches in comments, strings, or docstrings.

        Args:
            tree: Parsed AST tree dictionary

        Returns:
            List of (kind, module, line_number) tuples:
            - ('import', 'os', 15)
            - ('from', 'pathlib', 23)
        """
        imports = []

        # Handle None or non-dict input gracefully
        if not tree or not isinstance(tree, dict):
            return imports

        actual_tree = tree.get("tree")

        import os
        if os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG]   _extract_imports_ast: tree type={type(tree)}, has 'tree' key={('tree' in tree) if isinstance(tree, dict) else False}")
            if isinstance(tree, dict) and 'tree' in tree:
                print(f"[DEBUG]   actual_tree type={type(actual_tree)}, isinstance(ast.Module)={isinstance(actual_tree, ast.Module)}")

        if not actual_tree or not isinstance(actual_tree, ast.Module):
            if os.environ.get("THEAUDITOR_DEBUG"):
                print(f"[DEBUG]   Returning empty - actual_tree check failed")
            return imports
