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
        # 1. Normalize
        p = path.replace("\\", "/").lower()

        # 2. Remove Extensions
        for ext in [".ts", ".tsx", ".js", ".jsx", ".py"]:
            if p.endswith(ext):
                p = p[: -len(ext)]

        # 3. Remove Framework Qualifiers (TypeScript/NestJS/Angular conventions)
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

    # FIX #17: Handle TypeScript path aliases like "@controllers/auth" -> "controllers/auth"
    # TypeScript projects use tsconfig.json paths to alias directories:
    #   "@controllers/*" -> "src/controllers/*"
    # By stripping the leading "@", we align the alias with the physical path.
    # Example: "@controllers/account" -> "controllers/account"
    #          "backend/src/controllers/account" ends with "controllers/account" -> MATCH
    if clean_import.startswith("@"):
        clean_import = clean_import[1:]

    # 4. Extract Segments (Fingerprint)
    parts = [p for p in clean_import.split("/") if p not in (".", "..", "")]
    if not parts:
        return False

    import_fingerprint = "/".join(parts)

    # 5. Suffix Check with Boundary Enforcement
    # "src/guards/auth" (was auth.guard.ts) ends with "guards/auth" -> MATCH
    # "src/interceptors/auth" (was auth.interceptor.ts) ends with "guards/auth" -> NO MATCH
    if clean_symbol.endswith(import_fingerprint):
        match_index = clean_symbol.rfind(import_fingerprint)
        # Ensure boundary is a slash or start of string (prevents "unauth" matching "auth")
        if match_index == 0 or clean_symbol[match_index - 1] == "/":
            return True

    # GRAPH FIX G14: Handle implicit index resolution (Node/TypeScript convention)
    # Import: './models' -> cleans to 'models'
    # Symbol: 'src/models/index.ts' -> cleans to 'src/models/index'
    # Without this fix, the suffix check fails because 'src/models/index' doesn't end with 'models'
    if clean_symbol.endswith("/index"):
        clean_symbol_no_index = clean_symbol[:-6]  # Strip "/index"
        if clean_symbol_no_index.endswith(import_fingerprint):
            match_index = clean_symbol_no_index.rfind(import_fingerprint)
            if match_index == 0 or clean_symbol_no_index[match_index - 1] == "/":
                return True

    return False
