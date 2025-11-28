"""Detect inefficient imports that bloat frontend bundles (database-first)."""

import sqlite3

from theauditor.indexer.schema import build_query
from theauditor.rules.base import RuleMetadata, Severity, StandardFinding, StandardRuleContext

from .config import FRONTEND_FRAMEWORKS, META_FRAMEWORKS

METADATA = RuleMetadata(
    name="bundle_size",
    category="dependency",
    target_extensions=[".js", ".ts", ".jsx", ".tsx"],
    exclude_patterns=["node_modules/", ".venv/", "backend/", "server/", "test/", "__tests__/"],
    requires_jsx_pass=False,
)


LARGE_PACKAGES = frozenset(
    ["lodash", "moment", "antd", "element-plus", "element-ui", "@mui/material", "rxjs", "recharts"]
)


PACKAGE_METADATA = {
    "lodash": ("lodash/[function]", 1.4, Severity.MEDIUM),
    "moment": ("date-fns or dayjs", 0.7, Severity.MEDIUM),
    "antd": ("antd/es/[component]", 2.0, Severity.MEDIUM),
    "element-plus": ("element-plus/es/[component]", 2.5, Severity.MEDIUM),
    "element-ui": ("element-ui/lib/[component]", 2.0, Severity.MEDIUM),
    "@mui/material": ("@mui/material/[Component]", 1.5, Severity.LOW),
    "rxjs": ("rxjs/operators", 0.5, Severity.LOW),
    "recharts": ("recharts/[Chart]", 0.8, Severity.LOW),
}


FULL_IMPORT_PATTERNS = frozenset(
    [
        "import",
        "require",
        "import-default",
    ]
)


def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect full-package imports of large libraries in frontend code."""
    findings = []

    try:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        all_frameworks = FRONTEND_FRAMEWORKS | META_FRAMEWORKS
        placeholders_fw = ",".join(["?" for _ in all_frameworks])
        query = build_query(
            "package_configs", ["package_name"], where=f"package_name IN ({placeholders_fw})"
        )
        cursor.execute(query, list(all_frameworks))

        if not cursor.fetchall():
            conn.close()
            return findings

        placeholders = ",".join(["?" for _ in LARGE_PACKAGES])
        query = build_query(
            "import_styles",
            ["file", "line", "package", "import_style"],
            where=f"package IN ({placeholders})",
        )
        cursor.execute(query, list(LARGE_PACKAGES))

        seen_issues: set[str] = set()

        for file_path, line, package, import_style in cursor.fetchall():
            if import_style not in FULL_IMPORT_PATTERNS:
                continue

            alternative, size_mb, severity = PACKAGE_METADATA.get(package, ("", 0, Severity.LOW))

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

        conn.close()

    except sqlite3.Error:
        pass

    return findings
