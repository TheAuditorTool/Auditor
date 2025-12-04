"""Detect ghost dependencies - packages imported but not declared."""

import json

from theauditor.rules.base import RuleMetadata, RuleResult, Severity, StandardFinding, StandardRuleContext
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
    ])


PYTHON_STDLIB = frozenset(
    [
        "os",
        "sys",
        "json",
        "time",
        "datetime",
        "math",
        "random",
        "collections",
        "itertools",
        "functools",
        "operator",
        "re",
        "string",
        "unicodedata",
        "pathlib",
        "glob",
        "fnmatch",
        "tempfile",
        "shutil",
        "subprocess",
        "threading",
        "multiprocessing",
        "queue",
        "socket",
        "ssl",
        "http",
        "urllib",
        "email",
        "base64",
        "hashlib",
        "hmac",
        "secrets",
        "uuid",
        "logging",
        "warnings",
        "traceback",
        "inspect",
        "ast",
        "typing",
        "dataclasses",
        "enum",
        "abc",
        "io",
        "pickle",
        "csv",
        "xml",
        "html",
        "sqlite3",
    ]
)


NODEJS_STDLIB = frozenset(
    [
        "fs",
        "path",
        "os",
        "util",
        "events",
        "stream",
        "buffer",
        "crypto",
        "http",
        "https",
        "net",
        "dns",
        "tls",
        "dgram",
        "url",
        "querystring",
        "zlib",
        "readline",
        "repl",
        "child_process",
        "cluster",
        "worker_threads",
        "assert",
        "console",
        "process",
        "timers",
        "module",
        "vm",
        "v8",
        "inspector",
        "async_hooks",
        "perf_hooks",
        "node:fs",
        "node:path",
        "node:os",
        "node:util",
        "node:events",
        "node:stream",
        "node:buffer",
        "node:crypto",
        "node:http",
        "node:https",
        "node:net",
        "node:dns",
        "node:tls",
        "node:url",
        "node:zlib",
        "node:child_process",
        "node:cluster",
    ]
)


ALL_STDLIB = PYTHON_STDLIB | NODEJS_STDLIB


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect packages imported in code but not declared in package files."""
    findings = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, "ghost_dependencies") as db:
        declared_deps = _get_declared_dependencies(db)
        imported_packages = _get_imported_packages(db)
        findings = _find_ghost_dependencies(imported_packages, declared_deps)

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _get_declared_dependencies(db: RuleDB) -> set[str]:
    """Extract all declared package names from package_dependencies table."""
    declared = set()

    # Get Node.js package dependencies
    rows = db.query(Q("package_dependencies").select("name"))
    for (name,) in rows:
        if name:
            declared.add(name.lower())

    # Get Python package dependencies
    rows = db.query(Q("python_package_dependencies").select("name"))
    for (name,) in rows:
        if name:
            declared.add(name.lower())

    # Get Cargo dependencies
    rows = db.query(Q("cargo_dependencies").select("name"))
    for (name,) in rows:
        if name:
            declared.add(name.lower())

    # Get Go module dependencies
    rows = db.query(Q("go_module_dependencies").select("module_path"))
    for (module_path,) in rows:
        if module_path:
            # Extract package name from module path
            parts = module_path.split("/")
            declared.add(parts[-1].lower() if parts else module_path.lower())

    return declared


def _get_imported_packages(db: RuleDB) -> dict:
    """Extract all imported package names from import_styles table."""
    imports = {}

    rows = db.query(
        Q("import_styles")
        .select("file", "line", "package", "import_style")
        .order_by("package, file, line")
    )

    for file, line, package, import_style in rows:
        if not package:
            continue

        base_package = _normalize_package_name(package)

        if base_package not in imports:
            imports[base_package] = []

        imports[base_package].append((file, line, package, import_style))

    return imports


def _normalize_package_name(package: str) -> str:
    """Normalize package name for comparison."""

    if package.startswith("@"):
        parts = package.split("/", 2)
        if len(parts) >= 2:
            return "/".join(parts[:2]).lower()
        return package.lower()

    if package.startswith("node:"):
        return package.lower()

    base = package.split("/")[0].split(".")[0]

    return base.lower()


def _find_ghost_dependencies(
    imported_packages: dict, declared_deps: set[str]
) -> list[StandardFinding]:
    """Find packages that are imported but not declared."""
    findings = []
    seen = set()

    for package, import_locations in imported_packages.items():
        if package in ALL_STDLIB:
            continue

        if package in declared_deps:
            continue

        if package in seen:
            continue
        seen.add(package)

        file, line, full_package, import_style = import_locations[0]

        findings.append(
            StandardFinding(
                rule_name="ghost-dependency",
                message=f"Package '{package}' imported but not declared in dependencies",
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category="dependency",
                snippet=f"import: {full_package} (style: {import_style})",
                cwe_id="CWE-1104",
            )
        )

    return findings
