"""Detect inefficient imports that bloat frontend bundles (database-first).

Detects full-package imports of large libraries in frontend code and suggests
tree-shakeable alternatives to reduce bundle size.

CWE: N/A (Performance/Best Practice)
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

from .config import FRONTEND_FRAMEWORKS, META_FRAMEWORKS

METADATA = RuleMetadata(
    name="bundle_size",
    category="dependency",
    target_extensions=[".js", ".ts", ".jsx", ".tsx"],
    exclude_patterns=["node_modules/", ".venv/", "backend/", "server/", "test/", "__tests__/"],
    execution_scope="database",
    primary_table="import_styles",
)


LARGE_PACKAGES = frozenset([
    "lodash",
    "moment",
    "antd",
    "element-plus",
    "element-ui",
    "@mui/material",
    "rxjs",
    "recharts",
])


PACKAGE_METADATA: dict[str, tuple[str, float, Severity]] = {
    "lodash": ("lodash/[function]", 1.4, Severity.MEDIUM),
    "moment": ("date-fns or dayjs", 0.7, Severity.MEDIUM),
    "antd": ("antd/es/[component]", 2.0, Severity.MEDIUM),
    "element-plus": ("element-plus/es/[component]", 2.5, Severity.MEDIUM),
    "element-ui": ("element-ui/lib/[component]", 2.0, Severity.MEDIUM),
    "@mui/material": ("@mui/material/[Component]", 1.5, Severity.LOW),
    "rxjs": ("rxjs/operators", 0.5, Severity.LOW),
    "recharts": ("recharts/[Chart]", 0.8, Severity.LOW),
}


FULL_IMPORT_PATTERNS = frozenset([
    "import",
    "require",
    "import-default",
    # TODO(quality): Missing patterns - "import-namespace" for `import * as` style
])


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect full-package imports of large libraries in frontend code.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        findings = []

        # Check if project uses frontend frameworks
        if not _is_frontend_project(db):
            return RuleResult(findings=findings, manifest=db.get_manifest())

        # Query for full imports of large packages
        findings.extend(_check_large_package_imports(db))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _is_frontend_project(db: RuleDB) -> bool:
    """Check if project has frontend framework dependencies."""
    all_frameworks = FRONTEND_FRAMEWORKS | META_FRAMEWORKS
    placeholders = ",".join(["?" for _ in all_frameworks])

    rows = db.query(
        Q("package_configs")
        .select("package_name")
        .where(f"package_name IN ({placeholders})", *all_frameworks)
    )

    return len(rows) > 0


def _check_large_package_imports(db: RuleDB) -> list[StandardFinding]:
    """Check for full imports of large packages."""
    findings = []
    placeholders = ",".join(["?" for _ in LARGE_PACKAGES])

    rows = db.query(
        Q("import_styles")
        .select("file", "line", "package", "import_style")
        .where(f"package IN ({placeholders})", *LARGE_PACKAGES)
        .order_by("file, line")
    )

    seen_issues: set[str] = set()

    for file_path, line, package, import_style in rows:
        if import_style not in FULL_IMPORT_PATTERNS:
            continue

        alternative, size_mb, severity = PACKAGE_METADATA.get(
            package, ("", 0, Severity.LOW)
        )

        # De-duplicate by file:package
        issue_key = f"{file_path}:{package}"
        if issue_key in seen_issues:
            continue
        seen_issues.add(issue_key)

        findings.append(
            StandardFinding(
                file_path=file_path,
                line=line,
                rule_name="bundle-size-full-import",
                message=f"Full import of '{package}' (~{size_mb}MB) may bloat bundle. Consider using: {alternative}",
                severity=severity,
                category="dependency",
                snippet=f"import ... from '{package}'",
            )
        )

    return findings
