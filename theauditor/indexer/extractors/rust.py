"""Rust file extractor using tree-sitter.

This implementation uses tree-sitter-rust for complete AST traversal,
replacing the previous LSP-based approach (see rust_lsp_backup.py).

Why tree-sitter over LSP:
- Complete AST access (LSP only provides symbol locations)
- No regex needed (LSP required regex for imports - forbidden pattern)
- Faster (~10ms vs ~200ms per file)
- No temporary workspace or binary installation required
- Provides all 12 required extraction methods

LSP code preserved in:
- theauditor/indexer/extractors/rust_lsp_backup.py
- theauditor/lsp/rust_analyzer_client.py
- theauditor/toolboxes/rust.py
"""


import logging
from pathlib import Path
from typing import Any

from . import BaseExtractor

logger = logging.getLogger(__name__)


class RustExtractor(BaseExtractor):
    """Extractor for Rust files using tree-sitter AST parser."""

    def __init__(self, root_path: Path, ast_parser: Any | None = None):
        """Initialize the Rust extractor.

        Args:
            root_path: Project root path
            ast_parser: Optional AST parser (unused, tree-sitter manages its own)
        """
        super().__init__(root_path, ast_parser)
        self._parser = None  # Lazy initialization

    def _get_parser(self):
        """Get or create tree-sitter parser for Rust.

        Lazy initialization to avoid import overhead if not used.
        """
        if self._parser is not None:
            return self._parser

        try:
            # Use tree-sitter-language-pack (same as ast_parser.py for JS/TS/HCL)
            from tree_sitter_language_pack import get_parser

            self._parser = get_parser("rust")
            return self._parser

        except ImportError as e:
            logger.error(
                f"tree-sitter-language-pack not installed or missing Rust support: {e}\n"
                f"Install with: pip install tree-sitter-language-pack"
            )
            raise

    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this extractor supports."""
        return ['.rs']

    def extract(self, file_info: dict[str, Any], content: str,
                tree: Any | None = None) -> dict[str, Any]:
        """Extract all relevant information from a Rust file.

        Args:
            file_info: File metadata dictionary with 'path', 'ext', etc.
            content: File content
            tree: Ignored (tree-sitter manages its own parsing)

        Returns:
            Dictionary containing all extracted data matching the 12-method interface:
            {
                'symbols': [...],         # Functions, structs, enums, traits
                'imports': [...],         # use declarations
                'exports': [...],         # pub items
                'calls': [...],           # Function calls
                'properties': [...],      # Field accesses
                'assignments': [...],     # let bindings
                'returns': [...],         # return expressions
                'function_params': {...}, # Function parameter mapping
                'function_calls_with_args': [...],  # Calls with arguments
                'cfg': [...]              # Control flow graphs
            }
        """
        result = {
            'symbols': [],
            'imports': [],
            'exports': [],
            'calls': [],
            'properties': [],
            'assignments': [],
            'returns': [],
            'function_params': {},
            'function_calls': [],  # CRITICAL: Must match orchestrator expectation (not function_calls_with_args)
            'cfg': []
        }

        try:
            # Parse file with tree-sitter
            parser = self._get_parser()
            tree = parser.parse(bytes(content, 'utf8'))

            # Import rust_impl for extraction methods
            from theauditor.ast_extractors import rust_impl

            # Extract all features using the 12 required methods
            # Symbols (functions + structs/enums)
            functions = rust_impl.extract_rust_functions(tree, content, file_info['path'])
            classes = rust_impl.extract_rust_classes(tree, content, file_info['path'])
            result['symbols'] = functions + classes

            # Imports (use declarations) - NO REGEX, pure AST
            result['imports'] = rust_impl.extract_rust_imports(tree, content, file_info['path'])

            # Exports (pub items)
            result['exports'] = rust_impl.extract_rust_exports(tree, content, file_info['path'])

            # Function calls - add to symbols table with type='call' for taint analysis
            calls = rust_impl.extract_rust_calls(tree, content, file_info['path'])
            result['calls'] = calls
            for call in calls:
                result['symbols'].append({
                    'name': call.get('name', ''),
                    'type': 'call',
                    'line': call.get('line', 0),
                    'col': call.get('col', 0)
                })

            # Properties (field access) - add to symbols table with type='property' for taint analysis
            properties = rust_impl.extract_rust_properties(tree, content, file_info['path'])
            result['properties'] = properties
            for prop in properties:
                result['symbols'].append({
                    'name': prop.get('name', ''),
                    'type': 'property',
                    'line': prop.get('line', 0),
                    'col': prop.get('col', 0)
                })

            # Assignments (let bindings)
            result['assignments'] = rust_impl.extract_rust_assignments(tree, content, file_info['path'])

            # Returns
            result['returns'] = rust_impl.extract_rust_returns(tree, content, file_info['path'])

            # Function parameters
            result['function_params'] = rust_impl.extract_rust_function_params(tree, content, file_info['path'])

            # Function calls with arguments (CRITICAL for taint analysis)
            # MUST use key 'function_calls' to match orchestrator's expectation at __init__.py:342
            raw_calls = rust_impl.extract_rust_calls_with_args(
                tree, content, file_info['path'], result['function_params']
            )
            # Filter out calls with empty callee_function (violates CHECK constraint)
            result['function_calls'] = [
                call for call in raw_calls
                if call.get('callee_function', '').strip()
            ]

            # Control flow graphs
            result['cfg'] = rust_impl.extract_rust_cfg(tree, content, file_info['path'])

        except ImportError as e:
            logger.error(f"Rust extraction failed - missing dependencies: {e}")
            logger.error("Install with: pip install tree-sitter tree-sitter-rust")
            # Return empty results (graceful degradation)
        except Exception as e:
            logger.error(f"Rust extraction failed for {file_info['path']}: {e}")
            logger.debug(f"Full traceback:", exc_info=True)

            # Count what we extracted before failure
            counts = {k: len(v) if isinstance(v, (list, dict)) else 0
                     for k, v in result.items()}
            logger.warning(
                f"Partial extraction for {file_info['path']}: "
                f"symbols={counts['symbols']}, imports={counts['imports']}, "
                f"calls={counts['calls']}, returns={counts['returns']}"
            )
            # Return partial results (may be useful even with errors)

        return result

    def cleanup(self) -> None:
        """Clean up resources.

        tree-sitter doesn't require cleanup, but method provided for interface compatibility.
        """
        self._parser = None
