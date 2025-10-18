"""Tests for Python AST fallback behavior.

This test suite verifies that Python files ALWAYS use CPython's built-in ast module,
NEVER Tree-sitter, regardless of whether Tree-sitter bindings are installed.

This is an architectural decision: Python's stdlib ast module is superior to Tree-sitter
for Python analysis, and all extractors expect ast.Module payloads.
"""

import ast
import os
import tempfile
from pathlib import Path

import pytest

from theauditor.ast_parser import ASTParser
from theauditor.indexer.extractors.python import PythonExtractor


class TestPythonASTFallback:
    """Test suite for Python CPython ast usage."""

    def test_python_not_in_treesitter_parsers(self):
        """Verify Python is NOT registered as a Tree-sitter language.

        This is the core architectural guarantee: Python should never be in
        the Tree-sitter parsers dictionary.
        """
        parser = ASTParser()

        # Even if Tree-sitter is available, Python must not be registered
        if parser.has_tree_sitter:
            assert "python" not in parser.parsers, \
                "CRITICAL: Python should NEVER be in Tree-sitter parsers dict"
            assert "python" not in parser.languages, \
                "CRITICAL: Python should NEVER be in Tree-sitter languages dict"

    def test_parse_file_returns_python_ast(self):
        """Verify parse_file returns python_ast type with ast.Module payload."""
        parser = ASTParser()

        # Create test Python file
        test_code = """import os
from pathlib import Path
import sys

def hello():
    return "world"
"""

        # Write and close file before parsing (Windows requires this)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            fname = f.name
            f.write(test_code)

        try:
            # Parse the file
            tree = parser.parse_file(Path(fname))

            # Verify type and payload
            assert tree is not None, "Parser returned None for Python file"
            assert tree['type'] == 'python_ast', \
                f"Expected python_ast, got {tree['type']} (Tree-sitter should NEVER be used for Python)"
            assert isinstance(tree['tree'], ast.Module), \
                f"Expected ast.Module, got {type(tree['tree'])}"
            assert tree['language'] == 'python'
            assert 'content' in tree

        finally:
            os.unlink(fname)

    def test_parse_content_returns_python_ast(self):
        """Verify parse_content returns python_ast for Python code."""
        parser = ASTParser()

        content = """import os
from pathlib import Path

class Example:
    pass
"""

        tree = parser.parse_content(content, "python")

        # Verify type and payload
        assert tree is not None, "Parser returned None for Python content"
        assert tree['type'] == 'python_ast', \
            f"Expected python_ast, got {tree['type']}"
        assert isinstance(tree['tree'], ast.Module), \
            f"Expected ast.Module, got {type(tree['tree'])}"

    def test_python_imports_extracted_correctly(self):
        """Verify Python import extraction works with CPython ast."""
        parser = ASTParser()

        test_code = """import os
import sys
from pathlib import Path
from typing import Dict, List
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            fname = f.name
            f.write(test_code)

        try:
            # Parse the file
            tree = parser.parse_file(Path(fname))

            # Extract using PythonExtractor
            extractor = PythonExtractor(Path('.'), parser)
            file_info = {'path': fname, 'ext': '.py'}
            extracted = extractor.extract(file_info, test_code, tree)

            # Verify imports were extracted
            imports = extracted['imports']
            assert len(imports) >= 3, \
                f"Expected at least 3 imports, got {len(imports)}: {imports}"

            # Verify format (kind, module, line)
            import_modules = [imp[1] for imp in imports]
            assert 'os' in import_modules, "Missing 'os' import"
            assert 'sys' in import_modules, "Missing 'sys' import"
            assert 'pathlib' in import_modules, "Missing 'pathlib' import"

        finally:
            os.unlink(fname)

    def test_python_symbols_extracted_correctly(self):
        """Verify Python symbol extraction works with CPython ast."""
        parser = ASTParser()

        test_code = """
class MyClass:
    def method(self):
        pass

def my_function():
    return 42

async def async_function():
    pass
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            fname = f.name
            f.write(test_code)

        try:
            tree = parser.parse_file(Path(fname))

            extractor = PythonExtractor(Path('.'), parser)
            file_info = {'path': fname, 'ext': '.py'}
            extracted = extractor.extract(file_info, test_code, tree)

            symbols = extracted['symbols']
            symbol_names = [s['name'] for s in symbols]

            # Verify key symbols extracted
            assert 'MyClass' in symbol_names, "Missing class symbol"
            assert 'my_function' in symbol_names, "Missing function symbol"
            assert 'async_function' in symbol_names, "Missing async function symbol"

        finally:
            os.unlink(fname)

    def test_python_assignments_extracted(self):
        """Verify Python assignment extraction for taint analysis."""
        parser = ASTParser()

        test_code = """
user_input = request.args.get('name')
safe_data = sanitize(user_input)
output = f"Hello {safe_data}"
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            fname = f.name
            f.write(test_code)

        try:
            tree = parser.parse_file(Path(fname))

            extractor = PythonExtractor(Path('.'), parser)
            file_info = {'path': fname, 'ext': '.py'}
            extracted = extractor.extract(file_info, test_code, tree)

            assignments = extracted['assignments']
            assert len(assignments) >= 3, \
                f"Expected at least 3 assignments, got {len(assignments)}"

            target_vars = [a['target_var'] for a in assignments]
            assert 'user_input' in target_vars, "Missing user_input assignment"
            assert 'safe_data' in target_vars, "Missing safe_data assignment"

        finally:
            os.unlink(fname)

    def test_python_supports_language(self):
        """Verify supports_language returns True for Python."""
        parser = ASTParser()

        # Python is ALWAYS supported via CPython ast
        assert parser.supports_language("python") is True

    def test_parse_files_batch_uses_python_ast(self):
        """Verify batch parsing uses CPython ast for Python files."""
        parser = ASTParser()

        test_code = """import os
from pathlib import Path
"""

        # Create two test files
        files = []
        try:
            for i in range(2):
                f = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
                f.write(test_code)
                f.close()
                files.append(Path(f.name))

            # Batch parse
            results = parser.parse_files_batch(files)

            # Verify all results use python_ast
            for file_path in files:
                file_str = str(file_path).replace("\\", "/")
                assert file_str in results, f"Missing result for {file_path}"

                result = results[file_str]
                assert result is not None, f"None result for {file_path}"
                assert result['type'] == 'python_ast', \
                    f"Expected python_ast for {file_path}, got {result['type']}"
                assert isinstance(result['tree'], ast.Module), \
                    f"Expected ast.Module for {file_path}"

        finally:
            for f in files:
                if f.exists():
                    os.unlink(f)

    def test_python_syntax_error_handled_gracefully(self):
        """Verify syntax errors in Python files are handled gracefully."""
        parser = ASTParser()

        # Invalid Python syntax
        test_code = """import os
def broken syntax here
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            fname = f.name
            f.write(test_code)

        try:
            tree = parser.parse_file(Path(fname))

            # Syntax errors return None - this is graceful handling
            # Parser doesn't crash, just returns None
            assert tree is None or (isinstance(tree, dict) and tree.get('tree') is None), \
                "Parser should return None or dict with None tree for syntax errors"

        finally:
            os.unlink(fname)


class TestArchitecturalGuarantees:
    """Tests that enforce TheAuditor's architectural decisions."""

    def test_no_treesitter_python_in_get_supported_languages(self):
        """Verify Python support is NOT listed as coming from Tree-sitter."""
        parser = ASTParser()

        supported = parser.get_supported_languages()

        # Python should be in the list
        assert 'python' in supported, "Python must be in supported languages"

        # But it should NOT be via Tree-sitter
        if parser.has_tree_sitter:
            assert 'python' not in parser.parsers, \
                "Python must NOT be supported via Tree-sitter"

    def test_extractor_receives_correct_payload_type(self):
        """Integration test: Verify extractor receives expected ast.Module payload.

        This is the critical contract: PythonExtractor expects ast.Module objects
        and will silently fail with empty results if it receives anything else.
        """
        parser = ASTParser()

        test_code = """import os
from pathlib import Path
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            fname = f.name
            f.write(test_code)

        try:
            # Full pipeline: parse -> extract
            tree = parser.parse_file(Path(fname))

            extractor = PythonExtractor(Path('.'), parser)
            file_info = {'path': fname, 'ext': '.py'}
            extracted = extractor.extract(file_info, test_code, tree)

            # The critical test: imports should NOT be empty
            # If Tree-sitter was used, this would return empty list
            imports = extracted['imports']
            assert len(imports) > 0, \
                "REGRESSION: Imports are empty! This means extractor received wrong AST type."

        finally:
            os.unlink(fname)
