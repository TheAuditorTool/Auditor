"""Detect inefficient imports that bloat frontend bundles (database-first).

Detects full-package imports of large libraries in frontend code and suggests
tree-shakeable alternatives to reduce bundle size. Catches:
- Full package imports (import lodash from 'lodash')
- Namespace imports (import * as _ from 'lodash')
- Dynamic imports of full packages (await import('lodash'))
- CommonJS requires of large packages

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


# Packages known to be large and have tree-shakeable alternatives
LARGE_PACKAGES = frozenset([
    # Utility libraries
    "lodash",
    "underscore",
    "ramda",
    # Date libraries
    "moment",
    "moment-timezone",
    # UI component libraries (full imports are wasteful)
    "antd",
    "element-plus",
    "element-ui",
    "@mui/material",
    "@mui/icons-material",
    "@chakra-ui/react",
    "@blueprintjs/core",
    "semantic-ui-react",
    "react-bootstrap",
    # Charting
    "recharts",
    "chart.js",
    "d3",
    "highcharts",
    "echarts",
    # Animation
    "framer-motion",
    "gsap",
    "lottie-web",
    # RxJS
    "rxjs",
    # Icon libraries
    "react-icons",
    "@fortawesome/fontawesome-svg-core",
    # Firebase (heavy)
    "firebase",
    "@firebase/app",
    # AWS SDK v2 (v3 is modular)
    "aws-sdk",
    # Three.js
    "three",
    # PDF generation/viewing
    "pdfjs-dist",
    "jspdf",
    "pdf-lib",
    # Spreadsheet processing
    "xlsx",
    "sheetjs",
    "exceljs",
    # Crypto
    "crypto-js",
    # Syntax highlighting
    "highlight.js",
    "prismjs",
    # Maps
    "mapbox-gl",
    "leaflet",
    # Legacy
    "jquery",
    "bootstrap",
])


# Alternative suggestions and estimated sizes
PACKAGE_METADATA: dict[str, tuple[str, float, Severity]] = {
    # Utility libraries
    "lodash": ("lodash-es/[function] or lodash/[function]", 1.4, Severity.MEDIUM),
    "underscore": ("Individual utility functions or lodash-es", 0.3, Severity.LOW),
    "ramda": ("ramda/src/[function]", 0.5, Severity.LOW),
    # Date libraries
    "moment": ("date-fns or dayjs (10x smaller)", 0.7, Severity.MEDIUM),
    "moment-timezone": ("date-fns-tz (much smaller)", 0.9, Severity.MEDIUM),
    # UI component libraries
    "antd": ("antd/es/[component]", 2.0, Severity.MEDIUM),
    "element-plus": ("element-plus/es/components/[component]", 2.5, Severity.MEDIUM),
    "element-ui": ("element-ui/lib/[component]", 2.0, Severity.MEDIUM),
    "@mui/material": ("@mui/material/[Component]", 1.5, Severity.LOW),
    "@mui/icons-material": ("@mui/icons-material/[IconName]", 5.0, Severity.HIGH),
    "@chakra-ui/react": ("Individual @chakra-ui/[component] packages", 1.0, Severity.LOW),
    "@blueprintjs/core": ("@blueprintjs/core/lib/esm/[component]", 1.2, Severity.LOW),
    "semantic-ui-react": ("Individual component imports", 0.8, Severity.LOW),
    "react-bootstrap": ("react-bootstrap/[Component]", 0.5, Severity.LOW),
    # Charting
    "recharts": ("recharts/es6/[Chart]", 0.8, Severity.LOW),
    "chart.js": ("chart.js/auto or specific controllers", 0.5, Severity.LOW),
    "d3": ("d3-[module] (e.g., d3-scale, d3-shape)", 0.5, Severity.MEDIUM),
    "highcharts": ("highcharts/modules/[module]", 0.8, Severity.LOW),
    "echarts": ("echarts/core + specific charts", 1.0, Severity.MEDIUM),
    # Animation
    "framer-motion": ("Consider lighter alternatives for simple animations", 0.4, Severity.LOW),
    "gsap": ("gsap/[module]", 0.3, Severity.LOW),
    "lottie-web": ("@dotlottie/player-component or lazy load", 0.3, Severity.MEDIUM),
    # RxJS
    "rxjs": ("rxjs/operators or specific imports from rxjs", 0.5, Severity.LOW),
    # Icons
    "react-icons": ("react-icons/[library]/[icon]", 2.0, Severity.HIGH),
    "@fortawesome/fontawesome-svg-core": ("@fortawesome/free-solid-svg-icons/[icon]", 1.5, Severity.MEDIUM),
    # Firebase
    "firebase": ("firebase/[module] (auth, firestore, etc.)", 1.0, Severity.HIGH),
    "@firebase/app": ("Modular Firebase SDK imports", 0.8, Severity.MEDIUM),
    # AWS
    "aws-sdk": ("@aws-sdk/client-[service] (v3 modular SDK)", 3.0, Severity.HIGH),
    # 3D
    "three": ("three/examples/jsm/[module]", 1.5, Severity.MEDIUM),
    # PDF generation/viewing
    "pdfjs-dist": ("pdfjs-dist/build/pdf.min or lazy loading", 2.0, Severity.MEDIUM),
    "jspdf": ("Server-side PDF generation or lazy loading", 2.5, Severity.HIGH),
    "pdf-lib": ("Server-side PDF generation or lazy loading", 1.5, Severity.MEDIUM),
    # Spreadsheet processing
    "xlsx": ("Server-side processing or exceljs with streaming", 4.0, Severity.HIGH),
    "sheetjs": ("Server-side processing or exceljs with streaming", 4.0, Severity.HIGH),
    "exceljs": ("Server-side processing or streaming mode", 2.0, Severity.MEDIUM),
    # Crypto
    "crypto-js": ("window.crypto.subtle (Web Crypto API) or specific modules", 1.2, Severity.MEDIUM),
    # Syntax highlighting
    "highlight.js": ("highlight.js/lib/core + specific languages", 1.0, Severity.MEDIUM),
    "prismjs": ("prismjs/components/[language] for specific languages", 0.5, Severity.LOW),
    # Maps
    "mapbox-gl": ("Lazy load or consider lighter alternatives for simple maps", 2.5, Severity.HIGH),
    "leaflet": ("Lazy load map component", 0.4, Severity.LOW),
    # Legacy
    "jquery": ("Native DOM APIs or targeted polyfills", 0.3, Severity.MEDIUM),
    "bootstrap": ("Bootstrap CSS only + native JS or react-bootstrap", 0.4, Severity.LOW),
}


# Import styles that indicate full package import (pulls entire library)
FULL_IMPORT_PATTERNS = frozenset([
    "import",           # import foo from 'bar'
    "import-default",   # import foo from 'bar' (default export)
    "import-namespace", # import * as foo from 'bar' - ALWAYS pulls everything
    "require",          # const foo = require('bar')
    "dynamic",          # await import('bar') - full package dynamic import
])

# Import styles that are typically fine (tree-shakeable)
SAFE_IMPORT_PATTERNS = frozenset([
    "import-named",     # import { specific } from 'bar' - tree-shakeable
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

        # Detect meta-frameworks (Next.js/Nuxt) for Server Component caveat
        is_meta_framework = _is_meta_framework_project(db)

        # Query for full imports of large packages
        findings.extend(_check_large_package_imports(db, is_meta_framework))

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


def _is_meta_framework_project(db: RuleDB) -> bool:
    """Check if project uses Next.js, Nuxt, or similar meta-frameworks with Server Components."""
    placeholders = ",".join(["?" for _ in META_FRAMEWORKS])

    rows = db.query(
        Q("package_configs")
        .select("package_name")
        .where(f"package_name IN ({placeholders})", *META_FRAMEWORKS)
    )

    return len(rows) > 0


def _check_large_package_imports(db: RuleDB, is_meta_framework: bool = False) -> list[StandardFinding]:
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
        # Skip safe import patterns (named imports are tree-shakeable)
        if import_style in SAFE_IMPORT_PATTERNS:
            continue

        # Skip if not a full import pattern
        if import_style not in FULL_IMPORT_PATTERNS:
            continue

        alternative, size_mb, severity = PACKAGE_METADATA.get(
            package, ("Check for modular imports", 0.5, Severity.LOW)
        )

        # De-duplicate by file:package
        issue_key = f"{file_path}:{package}"
        if issue_key in seen_issues:
            continue
        seen_issues.add(issue_key)

        # Namespace imports are particularly bad - always pull everything
        if import_style == "import-namespace":
            message = f"Namespace import of '{package}' (~{size_mb}MB) pulls entire library. Use named imports or: {alternative}"
            severity = Severity.HIGH if severity == Severity.MEDIUM else severity
        elif import_style == "dynamic":
            message = f"Dynamic import of full '{package}' (~{size_mb}MB) package. Consider: {alternative}"
        else:
            message = f"Full import of '{package}' (~{size_mb}MB) may bloat bundle. Consider: {alternative}"

        # Add caveat for meta-frameworks (Next.js/Nuxt) where Server Components don't affect client bundle
        if is_meta_framework:
            message += " (Note: If used in a Server Component, this may be a false positive)"

        findings.append(
            StandardFinding(
                file_path=file_path,
                line=line,
                rule_name="bundle-size-full-import",
                message=message,
                severity=severity,
                category="dependency",
                snippet=f"{import_style}: {package}",
            )
        )

    return findings
