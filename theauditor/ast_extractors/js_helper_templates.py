"""JavaScript helper script templates for TypeScript AST extraction."""

from importlib.resources import files
from pathlib import Path


def get_batch_helper(module_type: str = "esm") -> str:
    """Read pre-compiled extractor bundle.

    Uses importlib.resources for pip-installed packages, falls back to
    Path(__file__) for editable installs.
    """
    # Try importlib.resources first (pip installs)
    try:
        dist_package = files("theauditor.ast_extractors.javascript.dist")
        bundle_resource = dist_package.joinpath("extractor.cjs")
        return bundle_resource.read_text(encoding="utf-8")
    except Exception:
        # Fallback to file path (editable installs)
        bundle_path = Path(__file__).parent / "javascript" / "dist" / "extractor.cjs"

        if not bundle_path.exists():
            raise FileNotFoundError(
                f"Extractor bundle not found at {bundle_path}. "
                "Run 'npm run build' in theauditor/ast_extractors/javascript"
            ) from None

        return bundle_path.read_text(encoding="utf-8")


def get_single_file_helper(module_type: str) -> str:
    """Get the appropriate single-file helper script."""
    raise RuntimeError(
        "Single-file mode removed in Phase 5. "
        "Single-file templates serialize full AST (512MB crash). "
        "Use get_batch_helper() with 1 file instead (sets ast: null)."
    )


__all__ = [
    "get_single_file_helper",
    "get_batch_helper",
]
