"""Source Map Exposure Analyzer.

Detects source map exposure vulnerabilities:
- Webpack devtool configurations that expose source code
- TypeScript sourceMap settings in production
- Exposed .map files in build directories
- Inline source maps embedded in production JS
- Static file serving without .map filtering

CWE-540: Inclusion of Sensitive Information in Source Code
"""

from dataclasses import dataclass
from pathlib import Path

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="sourcemap_exposure",
    category="security",
    execution_scope="database",
    target_extensions=[".js", ".ts", ".mjs", ".cjs", ".map"],
    exclude_patterns=["node_modules/", "test/", "spec/", "__tests__/"],
    primary_table="assignments",
)


@dataclass(frozen=True)
class SourcemapPatterns:
    """Immutable pattern definitions for source map detection."""

    PRODUCTION_PATHS = frozenset(
        [
            "dist",
            "build",
            "out",
            "public",
            "static",
            "assets",
            "bundle",
            "_next",
            ".next",
            "output",
            "www",
            "web",
            "compiled",
            "generated",
            "release",
        ]
    )

    MAP_EXTENSIONS = frozenset(
        [
            ".js.map",
            ".mjs.map",
            ".cjs.map",
            ".jsx.map",
            ".ts.map",
            ".tsx.map",
            ".min.js.map",
            ".bundle.js.map",
        ]
    )

    DANGEROUS_DEVTOOLS = frozenset(
        [
            "eval",
            "eval-source-map",
            "eval-cheap-source-map",
            "eval-cheap-module-source-map",
            "inline-source-map",
            "inline-cheap-source-map",
            "inline-cheap-module-source-map",
            "hidden-source-map",
            "nosources-source-map",
        ]
    )

    SAFE_DEVTOOLS = frozenset(["false", "none", "source-map", "hidden-source-map"])

    BUILD_CONFIGS = frozenset(
        [
            "webpack.config",
            "webpack.prod",
            "webpack.production",
            "rollup.config",
            "vite.config",
            "next.config",
            "tsconfig",
            "jsconfig",
            "babel.config",
            "parcel",
        ]
    )

    JS_EXTENSIONS = frozenset([".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"])

    SOURCEMAP_URL_PATTERNS = frozenset(
        [
            "sourceMappingURL=",
            "sourceURL=",
            "# sourceMappingURL",
            "@ sourceMappingURL",
            "//# sourceMappingURL",
            "//@ sourceURL",
        ]
    )

    INLINE_MAP_INDICATORS = frozenset(
        [
            "data:application/json;base64,",
            "data:application/json;charset=utf-8;base64,",
            'sourcesContent":',
            '"mappings":"',
        ]
    )

    SKIP_PATTERNS = frozenset(
        [
            "node_modules",
            ".git",
            "vendor",
            "third_party",
            "external",
            "lib",
            "bower_components",
            "jspm_packages",
        ]
    )


class SourcemapAnalyzer:
    """Analyzer for source map exposure vulnerabilities."""

    def __init__(self, context: StandardRuleContext, db: RuleDB):
        """Initialize analyzer with context and database connection."""
        self.context = context
        self.db = db
        self.patterns = SourcemapPatterns()
        self.findings = []
        self.seen_files = set()

    def run(self) -> list[StandardFinding]:
        """Main analysis entry point using hybrid approach."""
        self._check_webpack_configs()
        self._check_typescript_configs()
        self._check_build_tool_configs()
        self._check_sourcemap_plugins()
        self._check_express_static()
        self._check_sourcemap_generation()

        if hasattr(self.context, "project_path") and self.context.project_path:
            self._analyze_build_artifacts()

        return self.findings

    def _check_webpack_configs(self):
        """Check webpack configurations for source map settings."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, var, expr in rows:
            if "devtool" not in var.lower():
                continue

            file_lower = file.lower()
            if not ("webpack" in file_lower or "config" in file_lower):
                continue

            expr_lower = expr.lower().strip().strip("\"'")

            for dangerous in self.patterns.DANGEROUS_DEVTOOLS:
                if dangerous in expr_lower:
                    is_eval = "eval" in dangerous
                    is_inline = "inline" in dangerous

                    severity = Severity.CRITICAL if (is_eval or is_inline) else Severity.HIGH

                    self.findings.append(
                        StandardFinding(
                            rule_name="webpack-dangerous-devtool",
                            message=f'Webpack devtool "{dangerous}" exposes source code',
                            file_path=file,
                            line=line,
                            severity=severity,
                            category="security",
                            snippet=f'devtool: "{dangerous}"',
                            confidence=Confidence.HIGH,
                            cwe_id="CWE-540",
                        )
                    )
                    break

            if (
                "production" in file.lower()
                and expr_lower not in ["false", "none", ""]
                and expr_lower not in self.patterns.SAFE_DEVTOOLS
            ):
                self.findings.append(
                    StandardFinding(
                        rule_name="production-sourcemap-enabled",
                        message="Source maps enabled in production webpack config",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category="security",
                        snippet=f"devtool: {expr[:50]}",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-540",
                    )
                )

    def _check_typescript_configs(self):
        """Check TypeScript configurations for source map settings."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, var, expr in rows:
            var_lower = var.lower()
            if not ("sourcemap" in var_lower or "inlinesourcemap" in var_lower):
                continue

            if "tsconfig" not in file.lower():
                continue

            if expr and "true" in expr.lower():
                is_inline = "inline" in var_lower

                self.findings.append(
                    StandardFinding(
                        rule_name="typescript-sourcemap-enabled",
                        message=f"TypeScript {'inline ' if is_inline else ''}source maps enabled",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH if is_inline else Severity.MEDIUM,
                        category="security",
                        snippet=f"{var}: true",
                        confidence=Confidence.HIGH,
                        cwe_id="CWE-540",
                    )
                )

    def _check_build_tool_configs(self):
        """Check other build tool configurations."""
        rows = self.db.query(
            Q("assignments")
            .select("file", "line", "target_var", "source_expr")
            .where("target_var IS NOT NULL")
            .where("source_expr IS NOT NULL")
            .order_by("file, line")
        )

        for file, line, var, expr in rows:
            if "sourcemap" not in var.lower():
                continue

            file_lower = file.lower()
            if not ("vite" in file_lower or "rollup" in file_lower):
                continue

            if expr and any(val in expr.lower() for val in ["true", "inline", "hidden"]):
                self.findings.append(
                    StandardFinding(
                        rule_name="build-tool-sourcemap",
                        message="Source map generation enabled in build config",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category="security",
                        snippet=f"{var}: {expr[:50]}",
                        confidence=Confidence.MEDIUM,
                        cwe_id="CWE-540",
                    )
                )

    def _check_sourcemap_plugins(self):
        """Check for source map plugins in build tools."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function IS NOT NULL")
            .order_by("file, line")
        )

        plugin_patterns = frozenset(["SourceMapDevToolPlugin", "SourceMapPlugin", "sourceMaps"])

        for file, line, func, args in rows:
            if not any(plugin in func for plugin in plugin_patterns):
                continue

            if "webpack" not in file.lower():
                continue

            self.findings.append(
                StandardFinding(
                    rule_name="sourcemap-plugin-used",
                    message=f"Source map plugin {func} detected",
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category="security",
                    snippet=f"{func}({args[:50] if args else ''}...)",
                    confidence=Confidence.HIGH,
                    cwe_id="CWE-540",
                )
            )

    def _check_express_static(self):
        """Check if Express static serving might expose .map files."""
        rows = self.db.query(
            Q("function_call_args")
            .select("file", "line", "callee_function", "argument_expr")
            .where("callee_function IS NOT NULL")
            .order_by("file, line")
        )

        static_patterns = frozenset(["express.static", "serve-static", "koa-static"])

        for file, line, func, args in rows:
            if not any(pattern in func for pattern in static_patterns):
                continue

            if args and ".map" not in str(args) and "filter" not in str(args):
                self.findings.append(
                    StandardFinding(
                        rule_name="static-serving-maps",
                        message="Static file serving may expose .map files",
                        file_path=file,
                        line=line,
                        severity=Severity.LOW,
                        category="security",
                        snippet=f"{func}({args[:50] if args else ''})",
                        confidence=Confidence.LOW,
                        cwe_id="CWE-540",
                    )
                )

    def _check_sourcemap_generation(self):
        """Check for source map generation in code."""
        rows = self.db.query(
            Q("symbols")
            .select("path", "line", "name")
            .where("name IS NOT NULL")
            .order_by("path, line")
        )

        generation_patterns = frozenset(
            ["generateSourceMap", "createSourceMap", "writeSourceMap", "sourceMappingURL"]
        )
        test_patterns = frozenset(["test", "spec"])

        for file, line, name in rows:
            if not any(pattern in name for pattern in generation_patterns):
                continue

            file_lower = file.lower()
            if any(test_pattern in file_lower for test_pattern in test_patterns):
                continue

            if "sourceMappingURL" in name:
                confidence = Confidence.MEDIUM
                message = "Source map URL generation detected"
            else:
                confidence = Confidence.LOW
                message = "Source map generation function detected"

            self.findings.append(
                StandardFinding(
                    rule_name="sourcemap-generation-code",
                    message=message,
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category="security",
                    snippet=name,
                    confidence=confidence,
                    cwe_id="CWE-540",
                )
            )

    def _analyze_build_artifacts(self):
        """Analyze build artifacts for exposed source maps."""
        project_root = Path(self.context.project_path)

        build_dirs = self._find_build_directories(project_root)

        if not build_dirs:
            return

        for build_dir in build_dirs:
            self._scan_map_files(build_dir, project_root)

            self._scan_javascript_files(build_dir, project_root)

    def _find_build_directories(self, project_root: Path) -> list[Path]:
        """Find production build directories."""
        build_dirs = []

        for dir_name in self.patterns.PRODUCTION_PATHS:
            dir_path = project_root / dir_name
            if dir_path.exists() and dir_path.is_dir():
                ts_files = list(dir_path.glob("**/*.ts")) + list(dir_path.glob("**/*.tsx"))
                if len(ts_files) > 5:
                    continue
                build_dirs.append(dir_path)

        if self._is_likely_build_output(project_root):
            build_dirs.append(project_root)

        return build_dirs

    def _is_likely_build_output(self, directory: Path) -> bool:
        """Check if directory contains build artifacts."""

        minified = list(directory.glob("*.min.js"))[:5]
        if minified:
            return True

        chunks = list(directory.glob("*.[hash].js"))[:5] + list(directory.glob("chunk.*.js"))[:5]
        if chunks:
            return True

        bundle_files = ["bundle.js", "main.js", "app.js", "vendor.js"]
        return any((directory / bundle).exists() for bundle in bundle_files)

    def _scan_map_files(self, build_dir: Path, project_root: Path):
        """Scan for exposed .map files."""
        map_count = 0

        for ext in self.patterns.MAP_EXTENSIONS:
            pattern = f"*{ext}"
            for map_file in build_dir.rglob(pattern):
                if any(skip in str(map_file) for skip in self.patterns.SKIP_PATTERNS):
                    continue

                map_count += 1
                if map_count > 50:
                    return

                try:
                    relative_path = map_file.relative_to(project_root)
                    file_size = map_file.stat().st_size

                    is_js_map = False
                    try:
                        with open(map_file, encoding="utf-8", errors="ignore") as f:
                            first_line = f.read(200)
                            if '"sources"' in first_line or '"mappings"' in first_line:
                                is_js_map = True
                    except Exception:
                        is_js_map = True

                    if is_js_map:
                        if file_size > 1000000:
                            severity = Severity.CRITICAL
                            confidence = Confidence.HIGH
                        elif file_size > 100000:
                            severity = Severity.HIGH
                            confidence = Confidence.HIGH
                        else:
                            severity = Severity.MEDIUM
                            confidence = Confidence.MEDIUM

                        self.findings.append(
                            StandardFinding(
                                rule_name="sourcemap-file-exposed",
                                message=f"Source map file exposed ({file_size:,} bytes)",
                                file_path=str(relative_path),
                                line=1,
                                severity=severity,
                                category="security",
                                snippet=map_file.name,
                                confidence=confidence,
                                cwe_id="CWE-540",
                            )
                        )

                except (OSError, ValueError):
                    continue

    def _scan_javascript_files(self, build_dir: Path, project_root: Path):
        """Scan JavaScript files for source map references."""
        js_count = 0

        for ext in self.patterns.JS_EXTENSIONS:
            for js_file in build_dir.glob(f"**/*{ext}"):
                if any(skip in str(js_file) for skip in self.patterns.SKIP_PATTERNS):
                    continue

                js_count += 1
                if js_count > 100:
                    return

                if str(js_file) in self.seen_files:
                    continue
                self.seen_files.add(str(js_file))

                try:
                    relative_path = js_file.relative_to(project_root)

                    file_size = js_file.stat().st_size
                    with open(js_file, "rb") as f:
                        read_size = min(5000, file_size)
                        f.seek(max(0, file_size - read_size))
                        content_bytes = f.read()

                    try:
                        content_tail = content_bytes.decode("utf-8", errors="ignore")
                    except Exception:
                        continue

                    has_external_map = False
                    has_inline_map = False
                    map_reference = None

                    for pattern in self.patterns.SOURCEMAP_URL_PATTERNS:
                        if pattern in content_tail:
                            for indicator in self.patterns.INLINE_MAP_INDICATORS:
                                if indicator in content_tail:
                                    has_inline_map = True
                                    break

                            if not has_inline_map:
                                has_external_map = True

                                if "sourceMappingURL=" in content_tail:
                                    start = content_tail.find("sourceMappingURL=") + len(
                                        "sourceMappingURL="
                                    )
                                    end = content_tail.find("\n", start)
                                    if end == -1:
                                        end = content_tail.find(" ", start)
                                    if end == -1:
                                        end = len(content_tail)
                                    map_reference = content_tail[start:end].strip()
                            break

                    if has_inline_map:
                        self.findings.append(
                            StandardFinding(
                                rule_name="inline-sourcemap-exposed",
                                message="Inline source map embedded in production JavaScript",
                                file_path=str(relative_path),
                                line=1,
                                severity=Severity.CRITICAL,
                                category="security",
                                snippet="//# sourceMappingURL=data:application/json;base64,...",
                                confidence=Confidence.HIGH,
                                cwe_id="CWE-540",
                            )
                        )

                    elif has_external_map:
                        map_exists = False
                        if map_reference and not map_reference.startswith("data:"):
                            map_path = js_file.parent / map_reference
                            map_exists = map_path.exists()

                        self.findings.append(
                            StandardFinding(
                                rule_name="sourcemap-url-exposed",
                                message=f"Source map URL in production JS: {map_reference or 'unknown'}",
                                file_path=str(relative_path),
                                line=1,
                                severity=Severity.HIGH if map_exists else Severity.MEDIUM,
                                category="security",
                                snippet=f"//# sourceMappingURL={map_reference or '...'}",
                                confidence=Confidence.HIGH if map_exists else Confidence.MEDIUM,
                                cwe_id="CWE-540",
                            )
                        )

                except (OSError, ValueError):
                    continue


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect source map exposure vulnerabilities.

    Checks for:
    1. Webpack devtool configurations exposing source code
    2. TypeScript sourceMap settings in production
    3. Build tool source map generation
    4. Exposed .map files in build directories
    5. Static file serving without .map filtering

    Returns RuleResult with findings and fidelity manifest.
    """
    if not context.db_path:
        return RuleResult(findings=[], manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        analyzer = SourcemapAnalyzer(context, db)
        findings = analyzer.run()
        return RuleResult(findings=findings, manifest=db.get_manifest())


def register_taint_patterns(taint_registry):
    """Register source map related taint patterns."""
    patterns = SourcemapPatterns()

    taint_sinks = [
        "generateSourceMap",
        "createSourceMap",
        "writeSourceMap",
        "SourceMapGenerator",
        "SourceMapDevToolPlugin",
    ]

    for sink in taint_sinks:
        taint_registry.register_sink(sink, "sourcemap_generation", "javascript")

    for devtool in patterns.DANGEROUS_DEVTOOLS:
        taint_registry.register_sink(f'devtool: "{devtool}"', "dangerous_config", "javascript")
