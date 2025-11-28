"""JavaScript helper script templates for TypeScript AST extraction.

Phase 5 Architecture: Pre-compiled Bundle
==========================================
This module reads a pre-compiled TypeScript bundle from javascript/dist/extractor.js.
The bundle is built via esbuild and contains all extraction logic.

Build: cd theauditor/ast_extractors/javascript && npm run build

Workflow:
1. Python calls get_batch_helper()
2. Reads dist/extractor.js (pre-compiled bundle)
3. Returns complete JavaScript program as string
4. Python writes to temp file and executes via Node.js subprocess

This replaces the old Phase 4 architecture where 9 separate .js files were
concatenated at runtime via string concatenation.
"""

from pathlib import Path


def get_batch_helper(module_type: str = "esm") -> str:
    """Read pre-compiled extractor bundle.

    Reads the esbuild output from javascript/dist/extractor.js.
    The bundle contains all extraction logic compiled from TypeScript sources.

    Args:
        module_type: Ignored - bundle is always ESM/IIFE compatible for Node.
                     Kept for backward compatibility with callers.

    Returns:
        Complete JavaScript extractor bundle as a string

    Raises:
        FileNotFoundError: If the bundle is missing (needs npm run build)

    Example:
        >>> script = get_batch_helper()
        >>> # Write to temp file and execute
        >>> temp_path = Path(tempfile.mktemp(suffix='.mjs'))
        >>> temp_path.write_text(script)
        >>> subprocess.run(['node', str(temp_path), ...])
    """
    # We ignore module_type because the bundle is always ESM/IIFE compatible for Node
    bundle_path = Path(__file__).parent / "javascript" / "dist" / "extractor.cjs"

    if not bundle_path.exists():
        raise FileNotFoundError(
            f"Extractor bundle not found at {bundle_path}. "
            "Run 'npm run build' in theauditor/ast_extractors/javascript"
        )

    return bundle_path.read_text(encoding="utf-8")


def get_single_file_helper(module_type: str) -> str:
    """Get the appropriate single-file helper script.

    DEPRECATED: Single-file mode is obsolete in Phase 5. Use get_batch_helper() with 1 file instead.

    Args:
        module_type: Either "module" for ES modules or "commonjs" for CommonJS

    Returns:
        Complete JavaScript helper script as a string

    Raises:
        RuntimeError: Always raises - single-file mode removed in Phase 5
    """
    raise RuntimeError(
        "Single-file mode removed in Phase 5. "
        "Single-file templates serialize full AST (512MB crash). "
        "Use get_batch_helper() with 1 file instead (sets ast: null)."
    )


__all__ = [
    "get_single_file_helper",
    "get_batch_helper",
]
