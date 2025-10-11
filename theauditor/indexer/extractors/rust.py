"""Rust file extractor.

Handles extraction of Rust-specific elements including:
- Rust use statements (imports)
- Symbols via rust-analyzer LSP (functions, structs, enums, traits, impls)
- Semantic analysis using Language Server Protocol
"""

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from . import BaseExtractor
from theauditor.lsp.rust_analyzer_client import RustAnalyzerClient, parse_lsp_symbols
from theauditor.toolboxes.rust import get_rust_analyzer_path

logger = logging.getLogger(__name__)


class RustExtractor(BaseExtractor):
    """Extractor for Rust files using rust-analyzer LSP."""

    def __init__(self, root_path: Path, ast_parser: Optional[Any] = None):
        """Initialize the Rust extractor.

        Args:
            root_path: Project root path
            ast_parser: Optional AST parser (unused for Rust)
        """
        super().__init__(root_path, ast_parser)
        self._lsp_client: Optional[RustAnalyzerClient] = None
        self._temp_workspace: Optional[Path] = None
        self._file_counter: int = 0  # Counter for unique file names

    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports."""
        return ['.rs']

    def extract(self, file_info: Dict[str, Any], content: str,
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all relevant information from a Rust file.

        Args:
            file_info: File metadata dictionary with 'path', 'ext', etc.
            content: File content
            tree: Ignored (LSP provides semantic analysis)

        Returns:
            Dictionary containing all extracted data:
            {
                'imports': [(kind, value), ...],
                'symbols': [{'name': str, 'type': str, 'line': int, 'col': int}, ...]
            }
        """
        result = {
            'imports': [],
            'symbols': []
        }

        # Extract imports using regex (rust-analyzer LSP doesn't provide imports)
        result['imports'] = self._extract_rust_imports(content)

        # Extract symbols using rust-analyzer LSP
        try:
            symbols = self._extract_symbols_lsp(file_info['path'], content)
            result['symbols'] = symbols
        except FileNotFoundError as e:
            # rust-analyzer not installed
            logger.warning(f"rust-analyzer not installed: {e}")
            # Return empty symbols (not an error - just missing tooling)
            result['symbols'] = []
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            # LSP communication or file operation errors
            logger.error(f"Rust extraction failed for {file_info['path']}: {e}")
            result['symbols'] = []

        return result

    def _extract_rust_imports(self, content: str) -> List[Tuple[str, str]]:
        """Extract use statements from Rust code.

        Args:
            content: File content

        Returns:
            List of ('use', import_path) tuples
        """
        imports = []

        # Pattern matches:
        # use std::fs::File;
        # use crate::storage::StateManager;
        # pub use commands::start;
        # use serde::{Serialize, Deserialize};
        use_pattern = re.compile(
            r'^\s*(?:pub\s+)?use\s+([^;]+);',
            re.MULTILINE
        )

        for match in use_pattern.finditer(content):
            import_path = match.group(1).strip()
            imports.append(('use', import_path))

        return imports

    def _get_or_create_lsp_client(self) -> RustAnalyzerClient:
        """Get or create persistent LSP client.

        Returns:
            Persistent LSP client instance
        """
        if self._lsp_client is not None:
            return self._lsp_client

        # Get rust-analyzer binary
        try:
            binary_path = get_rust_analyzer_path()
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"rust-analyzer not installed. Run: aud setup-ai --target . ({e})"
            )

        # Create temporary workspace (reused for all files)
        # rust-analyzer requires a Cargo workspace even for single files
        self._temp_workspace = Path(tempfile.mkdtemp(prefix='rust_workspace_'))

        # Create minimal Cargo.toml
        cargo_toml = self._temp_workspace / 'Cargo.toml'
        cargo_toml.write_text(
            '[package]\nname = "temp"\nversion = "0.1.0"\nedition = "2021"\n'
        )

        # Create src directory
        src_dir = self._temp_workspace / 'src'
        src_dir.mkdir()

        # Initialize LSP client (persistent session)
        self._lsp_client = RustAnalyzerClient(binary_path, self._temp_workspace)
        self._lsp_client.initialize()

        return self._lsp_client

    def _extract_symbols_lsp(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """Extract symbols using rust-analyzer LSP.

        Args:
            file_path: Path to Rust file
            content: File content

        Returns:
            List of symbol dicts with name, type, line, col
        """
        # Get or create persistent LSP client
        client = self._get_or_create_lsp_client()

        # Use unique filename for each file (avoids LSP file management issues)
        self._file_counter += 1
        temp_file = self._temp_workspace / 'src' / f'file_{self._file_counter}.rs'
        temp_file.write_text(content)

        file_uri = f'file://{temp_file}'

        # Open file and query symbols (no need to close - unique URI each time)
        client.did_open(file_uri, content)
        lsp_symbols = client.document_symbol(file_uri)

        # Parse LSP symbols to TheAuditor format
        symbols = parse_lsp_symbols(lsp_symbols, content)

        return symbols

    def cleanup(self) -> None:
        """Clean up persistent LSP session and temporary workspace."""
        if self._lsp_client is not None:
            try:
                self._lsp_client.shutdown()
            except Exception:
                pass  # Best effort cleanup
            finally:
                self._lsp_client = None

        if self._temp_workspace is not None and self._temp_workspace.exists():
            try:
                shutil.rmtree(self._temp_workspace)
            except Exception:
                pass  # Best effort cleanup
            finally:
                self._temp_workspace = None
