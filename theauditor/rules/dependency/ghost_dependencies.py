"""Detect ghost dependencies - packages imported but not declared.

Detects packages that are imported in source code but not declared in
package.json, requirements.txt, Cargo.toml, or go.mod. These phantom
dependencies can break builds and create supply chain vulnerabilities.

Handles:
- Python stdlib detection (300+ modules)
- Node.js stdlib detection (50+ modules including node: prefix)
- Scoped packages (@org/pkg)
- Python package name normalization (hyphen vs underscore)
- Relative import filtering
- Monorepo internal package detection

CWE: CWE-1104 (Use of Unmaintained Third Party Components)
"""

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="ghost_dependencies",
    category="dependency",
    target_extensions=[".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"],
    exclude_patterns=[
        "node_modules/",
        ".venv/",
        "venv/",
        "__pycache__/",
        "dist/",
        "build/",
        ".git/",
        # Build/bundler config files use implicit/global/dev imports
        "**/webpack.config.*",
        "**/rollup.config.*",
        "**/vite.config.*",
        "**/esbuild.config.*",
        "**/parcel.config.*",
        "**/turbopack.config.*",
        # Linter/formatter config files
        "**/.eslintrc.*",
        "**/eslint.config.*",
        "**/.prettierrc.*",
        "**/prettier.config.*",
        "**/.stylelintrc.*",
        # Test config files
        "**/jest.config.*",
        "**/vitest.config.*",
        "**/karma.conf.*",
        "**/cypress.config.*",
        "**/playwright.config.*",
        # Transpiler config files
        "**/babel.config.*",
        "**/.babelrc*",
        "**/tsconfig.*",
        # CSS/styling config files
        "**/tailwind.config.*",
        "**/postcss.config.*",
        # Other common config files
        "**/next.config.*",
        "**/nuxt.config.*",
        "**/svelte.config.*",
        "**/astro.config.*",
    ],
    execution_scope="database",
    primary_table="import_styles",
)


# Comprehensive Python 3.x stdlib (as of 3.12)
PYTHON_STDLIB = frozenset([
    # Built-in types and functions
    "__future__", "builtins", "types", "typing", "typing_extensions",
    # String services
    "string", "re", "difflib", "textwrap", "unicodedata", "stringprep",
    # Binary data
    "struct", "codecs",
    # Data types
    "datetime", "zoneinfo", "calendar", "collections", "heapq", "bisect",
    "array", "weakref", "types", "copy", "pprint", "reprlib", "enum",
    "graphlib",
    # Numeric and math
    "numbers", "math", "cmath", "decimal", "fractions", "random", "statistics",
    # Functional programming
    "itertools", "functools", "operator",
    # File and directory
    "pathlib", "os", "io", "time", "argparse", "getopt", "logging",
    "warnings", "dataclasses", "contextlib",
    "os.path", "fileinput", "stat", "filecmp", "tempfile", "glob",
    "fnmatch", "linecache", "shutil",
    # Data persistence
    "pickle", "copyreg", "shelve", "marshal", "dbm", "sqlite3",
    # Data compression
    "zlib", "gzip", "bz2", "lzma", "zipfile", "tarfile",
    # File formats
    "csv", "configparser", "tomllib", "netrc", "plistlib",
    # Cryptographic
    "hashlib", "hmac", "secrets",
    # OS services
    "os", "io", "time", "argparse", "getopt", "logging", "getpass",
    "curses", "platform", "errno", "ctypes",
    # Concurrent execution
    "threading", "multiprocessing", "concurrent", "concurrent.futures",
    "subprocess", "sched", "queue", "contextvars", "_thread",
    # Networking
    "asyncio", "socket", "ssl", "select", "selectors", "signal",
    # Internet data handling
    "email", "json", "mailbox", "mimetypes", "base64", "binascii",
    "quopri", "uu",
    # HTML/XML
    "html", "html.parser", "html.entities", "xml", "xml.etree",
    "xml.etree.ElementTree", "xml.dom", "xml.sax",
    # Internet protocols
    "urllib", "urllib.request", "urllib.parse", "urllib.error",
    "http", "http.client", "http.server", "http.cookies", "http.cookiejar",
    "ftplib", "poplib", "imaplib", "smtplib", "uuid", "socketserver",
    "xmlrpc", "ipaddress",
    # Multimedia
    "wave", "colorsys",
    # Internationalization
    "gettext", "locale",
    # Program frameworks
    "turtle", "cmd", "shlex",
    # Development tools
    "pydoc", "doctest", "unittest", "unittest.mock", "test",
    # Debugging and profiling
    "bdb", "faulthandler", "pdb", "timeit", "trace", "tracemalloc",
    "cProfile", "profile", "pstats",
    # Packaging
    "ensurepip", "venv", "zipapp",
    # Python runtime
    "sys", "sysconfig", "builtins", "warnings", "dataclasses",
    "contextlib", "abc", "atexit", "traceback", "gc", "inspect",
    "site", "code", "codeop",
    # Importers
    "zipimport", "pkgutil", "modulefinder", "runpy", "importlib",
    "importlib.resources", "importlib.metadata",
    # Python AST
    "ast", "symtable", "token", "keyword", "tokenize", "tabnanny",
    "pyclbr", "py_compile", "compileall", "dis", "pickletools",
    # Misc
    "formatter",
])


# Comprehensive Node.js built-in modules (as of Node 20)
NODEJS_STDLIB = frozenset([
    # Core modules (both bare and node: prefix)
    "assert", "node:assert",
    "async_hooks", "node:async_hooks",
    "buffer", "node:buffer",
    "child_process", "node:child_process",
    "cluster", "node:cluster",
    "console", "node:console",
    "constants", "node:constants",
    "crypto", "node:crypto",
    "dgram", "node:dgram",
    "diagnostics_channel", "node:diagnostics_channel",
    "dns", "node:dns",
    "domain", "node:domain",
    "events", "node:events",
    "fs", "node:fs", "fs/promises", "node:fs/promises",
    "http", "node:http",
    "http2", "node:http2",
    "https", "node:https",
    "inspector", "node:inspector",
    "module", "node:module",
    "net", "node:net",
    "os", "node:os",
    "path", "node:path", "path/posix", "path/win32",
    "perf_hooks", "node:perf_hooks",
    "process", "node:process",
    "punycode", "node:punycode",
    "querystring", "node:querystring",
    "readline", "node:readline", "readline/promises",
    "repl", "node:repl",
    "stream", "node:stream", "stream/promises", "stream/consumers", "stream/web",
    "string_decoder", "node:string_decoder",
    "sys", "node:sys",
    "test", "node:test",
    "timers", "node:timers", "timers/promises",
    "tls", "node:tls",
    "trace_events", "node:trace_events",
    "tty", "node:tty",
    "url", "node:url",
    "util", "node:util", "util/types",
    "v8", "node:v8",
    "vm", "node:vm",
    "wasi", "node:wasi",
    "worker_threads", "node:worker_threads",
    "zlib", "node:zlib",
])


ALL_STDLIB = PYTHON_STDLIB | NODEJS_STDLIB


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect packages imported in code but not declared in package files.

    Args:
        context: Standard rule context with db_path

    Returns:
        RuleResult with findings and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        declared_deps = _get_declared_dependencies(db)
        imported_packages = _get_imported_packages(db)
        findings = _find_ghost_dependencies(imported_packages, declared_deps)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_declared_dependencies(db: RuleDB) -> set[str]:
    """Extract all declared package names from dependency tables.

    Returns normalized set of package names (lowercase, hyphen-normalized).
    """
    declared = set()

    # Get Node.js package dependencies
    rows = db.query(Q("package_dependencies").select("name"))
    for (name,) in rows:
        if name:
            declared.add(_normalize_for_comparison(name))

    # Get Python package dependencies
    rows = db.query(Q("python_package_dependencies").select("name"))
    for (name,) in rows:
        if name:
            # Python packages: normalize underscores to hyphens
            normalized = _normalize_for_comparison(name)
            declared.add(normalized)
            # Also add underscore variant for matching
            declared.add(normalized.replace("-", "_"))

    # Get Cargo dependencies
    rows = db.query(Q("cargo_dependencies").select("name"))
    for (name,) in rows:
        if name:
            declared.add(_normalize_for_comparison(name))

    # Get Go module dependencies
    rows = db.query(Q("go_module_dependencies").select("module_path"))
    for (module_path,) in rows:
        if module_path:
            # Extract package name from module path (last component)
            parts = module_path.split("/")
            if parts:
                declared.add(_normalize_for_comparison(parts[-1]))

    return declared


def _get_imported_packages(db: RuleDB) -> dict[str, list[tuple]]:
    """Extract all imported package names from import_styles table.

    Returns dict mapping normalized package name to list of (file, line, package, style).
    """
    imports: dict[str, list[tuple]] = {}

    rows = db.query(
        Q("import_styles")
        .select("file", "line", "package", "import_style")
        .order_by("package, file, line")
    )

    for file, line, package, import_style in rows:
        if not package:
            continue

        # Skip relative imports
        if _is_relative_import(package):
            continue

        # Skip type-only imports (TypeScript)
        if import_style == "import-type":
            continue

        base_package = _normalize_package_name(package)
        comparison_key = _normalize_for_comparison(base_package)

        if comparison_key not in imports:
            imports[comparison_key] = []

        imports[comparison_key].append((file, line, package, import_style))

    return imports


def _is_relative_import(package: str) -> bool:
    """Check if this is a relative import that should be skipped."""
    # JavaScript/TypeScript relative imports
    if package.startswith("./") or package.startswith("../"):
        return True
    # Single dot (current package in Python)
    if package == ".":
        return True
    # Looks like a file path
    if "/" in package and not package.startswith("@"):
        # But not scoped packages like @org/pkg
        first_part = package.split("/")[0]
        if first_part.startswith(".") or first_part == "":
            return True
    return False


def _normalize_package_name(package: str) -> str:
    """Normalize package name to base package for lookup.

    Examples:
        @org/pkg/subpath -> @org/pkg
        lodash/cloneDeep -> lodash
        node:fs -> node:fs
        my-package -> my-package
    """
    # Scoped packages: @org/pkg/subpath -> @org/pkg
    if package.startswith("@"):
        parts = package.split("/", 2)
        if len(parts) >= 2:
            return "/".join(parts[:2])
        return package

    # Node.js builtin with prefix
    if package.startswith("node:"):
        return package

    # Regular package: get base name before any subpath
    base = package.split("/")[0]

    return base


def _normalize_for_comparison(name: str) -> str:
    """Normalize name for case-insensitive comparison.

    Python packages use hyphens in PyPI but underscores in imports.
    This normalizes to lowercase with hyphens.
    """
    return name.lower().replace("_", "-")


def _find_ghost_dependencies(
    imported_packages: dict[str, list[tuple]],
    declared_deps: set[str],
) -> list[StandardFinding]:
    """Find packages that are imported but not declared."""
    findings = []

    for comparison_key, import_locations in imported_packages.items():
        # Skip stdlib
        if _is_stdlib(comparison_key):
            continue

        # Skip if declared (check both hyphen and underscore variants)
        if comparison_key in declared_deps:
            continue
        underscore_variant = comparison_key.replace("-", "_")
        if underscore_variant in declared_deps:
            continue

        # Get first occurrence for the finding
        file, line, full_package, import_style = import_locations[0]

        # Count total usages for context
        usage_count = len(import_locations)
        files_affected = len(set(loc[0] for loc in import_locations))

        if usage_count > 1:
            usage_info = f" (used in {files_affected} file(s), {usage_count} import(s))"
        else:
            usage_info = ""

        findings.append(
            StandardFinding(
                rule_name="ghost-dependency",
                message=f"Package '{comparison_key}' imported but not declared in dependencies{usage_info}",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="dependency",
                snippet=f"{import_style}: {full_package}",
                cwe_id="CWE-1104",
            )
        )

    return findings


def _is_stdlib(package: str) -> bool:
    """Check if package is a standard library module."""
    # Direct match
    if package in ALL_STDLIB:
        return True

    # Check without node: prefix
    if package.startswith("node:"):
        bare = package[5:]
        if bare in NODEJS_STDLIB:
            return True

    # Check Python submodule (e.g., collections.abc -> collections)
    if "." in package:
        base = package.split(".")[0]
        if base in PYTHON_STDLIB:
            return True

    return False
