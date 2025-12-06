"""Shared resolution utilities for graph strategies.

GRAPH FIX G13: Extracted from node_express.py and interceptors.py to eliminate
code duplication. Bug fixes now only need to be applied once.
"""


def path_matches(import_package: str, symbol_path: str) -> bool:
    """Check if import package matches symbol path.

    GRAPH FIX G11: Qualifier-Aware Suffix Matching.
    Fixes G10 regression where TypeScript conventions (auth.guard.ts) broke matching.
    1. Normalizes paths.
    2. Strips extensions (.ts, .js).
    3. Strips framework qualifiers (.guard, .service) to align 'auth' with 'auth.guard'.
    4. Performs directory-sensitive suffix match.

    Args:
        import_package: The import path (e.g., './guards/auth' or '@/guards/auth')
        symbol_path: The file path where the symbol is defined (e.g., 'src/guards/auth.guard.ts')

    Returns:
        True if the import package resolves to the symbol path.
    """
    if not import_package or not symbol_path:
        return False

    def clean_path(path: str) -> str:
        p = path.replace("\\", "/").lower()

        for ext in [".ts", ".tsx", ".js", ".jsx", ".py"]:
            if p.endswith(ext):
                p = p[: -len(ext)]

        qualifiers = [
            ".guard",
            ".service",
            ".controller",
            ".interceptor",
            ".middleware",
            ".module",
            ".entity",
            ".dto",
            ".resolver",
            ".strategy",
            ".pipe",
            ".component",
            ".directive",
        ]
        for q in qualifiers:
            if p.endswith(q):
                p = p[: -len(q)]
        return p

    clean_import = clean_path(import_package)
    clean_symbol = clean_path(symbol_path)

    if clean_import.startswith("@"):
        clean_import = clean_import[1:]

    parts = [p for p in clean_import.split("/") if p not in (".", "..", "")]
    if not parts:
        return False

    import_fingerprint = "/".join(parts)

    if clean_symbol.endswith(import_fingerprint):
        match_index = clean_symbol.rfind(import_fingerprint)

        if match_index == 0 or clean_symbol[match_index - 1] == "/":
            return True

    if clean_symbol.endswith("/index"):
        clean_symbol_no_index = clean_symbol[:-6]
        if clean_symbol_no_index.endswith(import_fingerprint):
            match_index = clean_symbol_no_index.rfind(import_fingerprint)
            if match_index == 0 or clean_symbol_no_index[match_index - 1] == "/":
                return True

    return False
