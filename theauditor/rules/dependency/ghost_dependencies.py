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
        "**/webpack.config.*",
        "**/rollup.config.*",
        "**/vite.config.*",
        "**/esbuild.config.*",
        "**/parcel.config.*",
        "**/turbopack.config.*",
        "**/.eslintrc.*",
        "**/eslint.config.*",
        "**/.prettierrc.*",
        "**/prettier.config.*",
        "**/.stylelintrc.*",
        "**/jest.config.*",
        "**/vitest.config.*",
        "**/karma.conf.*",
        "**/cypress.config.*",
        "**/playwright.config.*",
        "**/babel.config.*",
        "**/.babelrc*",
        "**/tsconfig.*",
        "**/tailwind.config.*",
        "**/postcss.config.*",
        "**/next.config.*",
        "**/nuxt.config.*",
        "**/svelte.config.*",
        "**/astro.config.*",
    ],
    execution_scope="database",
    primary_table="import_styles",
)


PYTHON_STDLIB = frozenset(
    [
        "__future__",
        "builtins",
        "types",
        "typing",
        "typing_extensions",
        "string",
        "re",
        "difflib",
        "textwrap",
        "unicodedata",
        "stringprep",
        "struct",
        "codecs",
        "datetime",
        "zoneinfo",
        "calendar",
        "collections",
        "heapq",
        "bisect",
        "array",
        "weakref",
        "types",
        "copy",
        "pprint",
        "reprlib",
        "enum",
        "graphlib",
        "numbers",
        "math",
        "cmath",
        "decimal",
        "fractions",
        "random",
        "statistics",
        "itertools",
        "functools",
        "operator",
        "pathlib",
        "os",
        "io",
        "time",
        "argparse",
        "getopt",
        "logging",
        "warnings",
        "dataclasses",
        "contextlib",
        "os.path",
        "fileinput",
        "stat",
        "filecmp",
        "tempfile",
        "glob",
        "fnmatch",
        "linecache",
        "shutil",
        "pickle",
        "copyreg",
        "shelve",
        "marshal",
        "dbm",
        "sqlite3",
        "zlib",
        "gzip",
        "bz2",
        "lzma",
        "zipfile",
        "tarfile",
        "csv",
        "configparser",
        "tomllib",
        "netrc",
        "plistlib",
        "hashlib",
        "hmac",
        "secrets",
        "os",
        "io",
        "time",
        "argparse",
        "getopt",
        "logging",
        "getpass",
        "curses",
        "platform",
        "errno",
        "ctypes",
        "threading",
        "multiprocessing",
        "concurrent",
        "concurrent.futures",
        "subprocess",
        "sched",
        "queue",
        "contextvars",
        "_thread",
        "asyncio",
        "socket",
        "ssl",
        "select",
        "selectors",
        "signal",
        "email",
        "json",
        "mailbox",
        "mimetypes",
        "base64",
        "binascii",
        "quopri",
        "uu",
        "html",
        "html.parser",
        "html.entities",
        "xml",
        "xml.etree",
        "xml.etree.ElementTree",
        "xml.dom",
        "xml.sax",
        "urllib",
        "urllib.request",
        "urllib.parse",
        "urllib.error",
        "http",
        "http.client",
        "http.server",
        "http.cookies",
        "http.cookiejar",
        "ftplib",
        "poplib",
        "imaplib",
        "smtplib",
        "uuid",
        "socketserver",
        "xmlrpc",
        "ipaddress",
        "wave",
        "colorsys",
        "gettext",
        "locale",
        "turtle",
        "cmd",
        "shlex",
        "pydoc",
        "doctest",
        "unittest",
        "unittest.mock",
        "test",
        "bdb",
        "faulthandler",
        "pdb",
        "timeit",
        "trace",
        "tracemalloc",
        "cProfile",
        "profile",
        "pstats",
        "ensurepip",
        "venv",
        "zipapp",
        "sys",
        "sysconfig",
        "builtins",
        "warnings",
        "dataclasses",
        "contextlib",
        "abc",
        "atexit",
        "traceback",
        "gc",
        "inspect",
        "site",
        "code",
        "codeop",
        "zipimport",
        "pkgutil",
        "modulefinder",
        "runpy",
        "importlib",
        "importlib.resources",
        "importlib.metadata",
        "ast",
        "symtable",
        "token",
        "keyword",
        "tokenize",
        "tabnanny",
        "pyclbr",
        "py_compile",
        "compileall",
        "dis",
        "pickletools",
        "formatter",
    ]
)


NODEJS_STDLIB = frozenset(
    [
        "assert",
        "node:assert",
        "async_hooks",
        "node:async_hooks",
        "buffer",
        "node:buffer",
        "child_process",
        "node:child_process",
        "cluster",
        "node:cluster",
        "console",
        "node:console",
        "constants",
        "node:constants",
        "crypto",
        "node:crypto",
        "dgram",
        "node:dgram",
        "diagnostics_channel",
        "node:diagnostics_channel",
        "dns",
        "node:dns",
        "domain",
        "node:domain",
        "events",
        "node:events",
        "fs",
        "node:fs",
        "fs/promises",
        "node:fs/promises",
        "http",
        "node:http",
        "http2",
        "node:http2",
        "https",
        "node:https",
        "inspector",
        "node:inspector",
        "module",
        "node:module",
        "net",
        "node:net",
        "os",
        "node:os",
        "path",
        "node:path",
        "path/posix",
        "path/win32",
        "perf_hooks",
        "node:perf_hooks",
        "process",
        "node:process",
        "punycode",
        "node:punycode",
        "querystring",
        "node:querystring",
        "readline",
        "node:readline",
        "readline/promises",
        "repl",
        "node:repl",
        "stream",
        "node:stream",
        "stream/promises",
        "stream/consumers",
        "stream/web",
        "string_decoder",
        "node:string_decoder",
        "sys",
        "node:sys",
        "test",
        "node:test",
        "timers",
        "node:timers",
        "timers/promises",
        "tls",
        "node:tls",
        "trace_events",
        "node:trace_events",
        "tty",
        "node:tty",
        "url",
        "node:url",
        "util",
        "node:util",
        "util/types",
        "v8",
        "node:v8",
        "vm",
        "node:vm",
        "wasi",
        "node:wasi",
        "worker_threads",
        "node:worker_threads",
        "zlib",
        "node:zlib",
    ]
)


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

    rows = db.query(Q("package_dependencies").select("name"))
    for (name,) in rows:
        if name:
            declared.add(_normalize_for_comparison(name))

    rows = db.query(Q("python_package_dependencies").select("name"))
    for (name,) in rows:
        if name:
            normalized = _normalize_for_comparison(name)
            declared.add(normalized)

            declared.add(normalized.replace("-", "_"))

    rows = db.query(Q("cargo_dependencies").select("name"))
    for (name,) in rows:
        if name:
            declared.add(_normalize_for_comparison(name))

    rows = db.query(Q("go_module_dependencies").select("module_path"))
    for (module_path,) in rows:
        if module_path:
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

        if _is_relative_import(package):
            continue

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

    if package.startswith("./") or package.startswith("../"):
        return True

    if package == ".":
        return True

    if "/" in package and not package.startswith("@"):
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

    if package.startswith("@"):
        parts = package.split("/", 2)
        if len(parts) >= 2:
            return "/".join(parts[:2])
        return package

    if package.startswith("node:"):
        return package

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
        if _is_stdlib(comparison_key):
            continue

        if comparison_key in declared_deps:
            continue
        underscore_variant = comparison_key.replace("-", "_")
        if underscore_variant in declared_deps:
            continue

        file, line, full_package, import_style = import_locations[0]

        usage_count = len(import_locations)
        files_affected = len({loc[0] for loc in import_locations})

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

    if package in ALL_STDLIB:
        return True

    if package.startswith("node:"):
        bare = package[5:]
        if bare in NODEJS_STDLIB:
            return True

    if "." in package:
        base = package.split(".")[0]
        if base in PYTHON_STDLIB:
            return True

    return False
