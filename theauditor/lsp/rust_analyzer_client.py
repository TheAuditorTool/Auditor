"""rust-analyzer LSP client for semantic Rust code analysis.

================== PRESERVATION NOTICE ==================
STATUS: Currently unused (tree-sitter approach in production)
PRESERVED FOR: Potential future hybrid LSP + tree-sitter approach

This LSP client provides semantic analysis capabilities:
- Type information and inference
- Symbol references and definitions
- Semantic navigation

CURRENT USAGE: None (indexer/extractors/rust.py uses tree-sitter)
PRESERVED USAGE: See indexer/extractors/rust_lsp_backup.py for example

TO USE IN HYBRID APPROACH:
1. Use tree-sitter for AST extraction (structure)
2. Use this LSP client for semantic info (types)
3. Combine both for complete analysis

PRESERVED: 2025-10-11
===========================================================
"""


import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# LSP timing constants (in seconds unless otherwise noted)
LSP_ANALYSIS_DELAY_SEC = 0.2  # Time to wait for rust-analyzer to analyze file
LSP_REQUEST_TIMEOUT_SEC = 5   # Timeout for document symbol requests
LSP_SHUTDOWN_TIMEOUT_SEC = 2  # Timeout for graceful shutdown
LSP_READ_TIMEOUT_SEC = 10     # Max attempts to find matching response ID


class RustAnalyzerClient:
    """JSON-RPC LSP client for rust-analyzer."""

    def __init__(self, binary_path: Path, workspace_dir: Path):
        """
        Initialize LSP client.

        Args:
            binary_path: Path to rust-analyzer binary
            workspace_dir: Workspace root directory (must contain Cargo.toml)
        """
        self.binary_path = binary_path
        self.workspace_dir = workspace_dir
        self.process: subprocess.Popen | None = None
        self.request_id = 0

    def start(self) -> None:
        """Start rust-analyzer LSP process."""
        if self.process is not None:
            return  # Already started

        self.process = subprocess.Popen(
            [str(self.binary_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def initialize(self) -> dict[str, Any]:
        """
        Send initialize request to LSP server.

        Returns:
            Server capabilities dict
        """
        if self.process is None:
            self.start()

        request = self._build_request('initialize', {
            'processId': os.getpid(),
            'rootUri': f'file://{self.workspace_dir}',
            'capabilities': {}
        })

        self._send_request(request)
        response = self._read_response_with_id(request['id'])

        # Send initialized notification
        self._send_notification(self._build_notification('initialized', {}))

        return response.get('result', {})

    def did_open(self, file_uri: str, content: str) -> None:
        """
        Send didOpen notification for a file.

        Args:
            file_uri: File URI (e.g., file:///path/to/file.rs)
            content: File content
        """
        self._send_notification(self._build_notification('textDocument/didOpen', {
            'textDocument': {
                'uri': file_uri,
                'languageId': 'rust',
                'version': 1,
                'text': content
            }
        }))

        # Give rust-analyzer time to analyze
        time.sleep(LSP_ANALYSIS_DELAY_SEC)

    def did_close(self, file_uri: str) -> None:
        """
        Send didClose notification for a file.

        Args:
            file_uri: File URI (e.g., file:///path/to/file.rs)
        """
        self._send_notification(self._build_notification('textDocument/didClose', {
            'textDocument': {'uri': file_uri}
        }))

    def document_symbol(self, file_uri: str) -> list[dict[str, Any]]:
        """
        Query document symbols.

        Args:
            file_uri: File URI (e.g., file:///path/to/file.rs)

        Returns:
            List of DocumentSymbol objects
        """
        request = self._build_request('textDocument/documentSymbol', {
            'textDocument': {'uri': file_uri}
        })

        self._send_request(request)
        response = self._read_response_with_id(request['id'], timeout=LSP_REQUEST_TIMEOUT_SEC)

        return response.get('result', [])

    def shutdown(self) -> None:
        """Gracefully shutdown LSP server."""
        if self.process is None:
            return

        try:
            # Send shutdown request
            request = self._build_request('shutdown', None)
            self._send_request(request)
            self._read_response_with_id(request['id'], timeout=LSP_SHUTDOWN_TIMEOUT_SEC)

            # Send exit notification
            self._send_notification(self._build_notification('exit', {}))

            # Wait for process to terminate
            self.process.wait(timeout=LSP_SHUTDOWN_TIMEOUT_SEC)

        except Exception:
            # Force kill if graceful shutdown fails
            if self.process:
                self.process.kill()
        finally:
            self.process = None

    def _next_id(self) -> int:
        """Get next request ID."""
        self.request_id += 1
        return self.request_id

    def _build_request(self, method: str, params: Any) -> dict[str, Any]:
        """Build LSP request dict.

        Args:
            method: LSP method name
            params: Request parameters

        Returns:
            Complete LSP request dict with jsonrpc, id, method, params
        """
        return {
            'jsonrpc': '2.0',
            'id': self._next_id(),
            'method': method,
            'params': params
        }

    def _build_notification(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Build LSP notification dict.

        Args:
            method: LSP method name
            params: Notification parameters

        Returns:
            Complete LSP notification dict with jsonrpc, method, params
        """
        return {
            'jsonrpc': '2.0',
            'method': method,
            'params': params
        }

    def _send_message(self, message_dict: dict[str, Any]) -> None:
        """Send LSP message (request or notification) with Content-Length header.

        Args:
            message_dict: LSP message dict (request with 'id' or notification without)
        """
        message_json = json.dumps(message_dict)
        content_length = len(message_json.encode('utf-8'))
        message = f'Content-Length: {content_length}\r\n\r\n{message_json}'

        self.process.stdin.write(message)
        self.process.stdin.flush()

    def _send_request(self, request: dict[str, Any]) -> None:
        """Send LSP request with Content-Length header."""
        self._send_message(request)

    def _send_notification(self, notification: dict[str, Any]) -> None:
        """Send LSP notification (no response expected)."""
        self._send_message(notification)

    def _read_response(self) -> dict[str, Any]:
        """Read single LSP response with Content-Length header."""
        # Read Content-Length header
        header_line = self.process.stdout.readline()
        if not header_line.startswith('Content-Length:'):
            raise ValueError(f'Expected Content-Length header, got: {header_line}')

        content_length = int(header_line.split(':')[1].strip())

        # Read empty line
        self.process.stdout.readline()

        # Read JSON body
        response_json = self.process.stdout.read(content_length)
        return json.loads(response_json)

    def _read_response_with_id(self, expected_id: int, timeout: int = LSP_READ_TIMEOUT_SEC) -> dict[str, Any]:
        """
        Read LSP response with specific ID, skipping notifications.

        Args:
            expected_id: Expected response ID
            timeout: Max attempts to find matching response

        Returns:
            Response dict with matching ID

        Raises:
            TimeoutError: If response not found after max attempts
        """
        max_attempts = timeout * 2  # ~500ms per attempt with read overhead

        for attempt in range(max_attempts):
            response = self._read_response()

            # Skip notifications (no 'id' field)
            if 'id' not in response:
                continue

            # Return response with matching ID
            if response.get('id') == expected_id:
                return response

        raise TimeoutError(
            f'Did not receive response with id={expected_id} after {max_attempts} attempts'
        )


def parse_lsp_symbols(lsp_symbols: list[dict], content: str) -> list[dict[str, Any]]:
    """
    Parse LSP DocumentSymbol list into flat symbol list.

    Args:
        lsp_symbols: LSP DocumentSymbol array (possibly nested)
        content: Source code content for visibility detection

    Returns:
        Flat list of symbol dicts with keys: name, type, line, col
    """
    if not lsp_symbols:
        return []

    result = []
    lines = content.splitlines()

    for symbol in lsp_symbols:
        # Extract location
        location = symbol.get('location', symbol.get('range', {}))
        if 'range' in symbol:
            # DocumentSymbol format
            start = symbol['range']['start']
        else:
            # SymbolInformation format
            start = location.get('range', {}).get('start', {})

        line_num = start.get('line', 0)
        col_num = start.get('character', 0)

        # Map LSP SymbolKind to TheAuditor type
        kind = symbol.get('kind', 0)
        symbol_type = _lsp_kind_to_type(kind)

        # Basic symbol info
        parsed = {
            'name': symbol.get('name', 'unknown'),
            'type': symbol_type,
            'line': line_num + 1,  # LSP is 0-indexed, convert to 1-indexed
            'col': col_num
        }

        result.append(parsed)

        # Recursively process children (struct fields, impl methods)
        if 'children' in symbol:
            child_symbols = parse_lsp_symbols(symbol['children'], content)
            result.extend(child_symbols)

    return result


def _lsp_kind_to_type(kind: int) -> str:
    """
    Convert LSP SymbolKind integer to TheAuditor type string.

    LSP SymbolKind values (partial):
    2=Module, 5=Class, 6=Method, 8=Field, 10=Enum, 11=Interface, 12=Function,
    13=Variable, 14=Constant, 23=Struct, 26=TypeParameter
    """
    kind_map = {
        2: 'module',    # Module declarations (mod foo;)
        5: 'impl',      # Class maps to impl blocks in Rust
        6: 'method',
        8: 'field',
        10: 'enum',
        11: 'trait',    # Interface maps to trait in Rust
        12: 'function',
        13: 'variable',
        14: 'const',
        23: 'struct',
        26: 'type'
    }
    return kind_map.get(kind, 'unknown')
