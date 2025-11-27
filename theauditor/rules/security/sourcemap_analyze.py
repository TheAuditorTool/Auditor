"""Source Map Exposure Analyzer - Hybrid Database + File I/O Approach.

Detects exposed source maps using a JUSTIFIED HYBRID approach because:
1. Source maps are BUILD ARTIFACTS not indexed in database
2. .map files exist only in dist/build directories
3. Inline maps are added by bundlers, not in source
4. sourceMappingURL comments are in generated files

Follows v1.1+ schema contract compliance for database queries:
- Frozensets for all patterns (O(1) lookups)
- Direct database queries (assumes all tables exist per schema contract)
- Uses parameterized queries (no SQL injection)
- Proper confidence levels
- Minimal file I/O (last 5KB only for build artifacts)
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    Severity,
    StandardFinding,
    StandardRuleContext,
)

METADATA = RuleMetadata(
    name="sourcemap_exposure",
    category="security",
    execution_scope="database",
    target_extensions=[".js", ".ts", ".mjs", ".cjs", ".map"],
    exclude_patterns=["node_modules/", "test/", "spec/", "__tests__/"],
    requires_jsx_pass=False,
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

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with context.

        Args:
            context: Rule context containing database and project paths
        """
        self.context = context
        self.patterns = SourcemapPatterns()
        self.findings = []
        self.seen_files = set()

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point using hybrid approach.

        Returns:
            List of source map exposure findings
        """

        if self.context.db_path:
            self._analyze_database()

        if hasattr(self.context, "project_path") and self.context.project_path:
            self._analyze_build_artifacts()

        return self.findings

    def _analyze_database(self):
        """Analyze database for source map configurations."""
        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            self._check_webpack_configs()
            self._check_typescript_configs()
            self._check_build_tool_configs()
            self._check_sourcemap_plugins()
            self._check_express_static()
            self._check_sourcemap_generation()

        finally:
            conn.close()

    def _check_webpack_configs(self):
        """Check webpack configurations for source map settings."""

        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
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
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
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

        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var IS NOT NULL
              AND source_expr IS NOT NULL
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
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
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
            ORDER BY file, line
        """)

        plugin_patterns = frozenset(["SourceMapDevToolPlugin", "SourceMapPlugin", "sourceMaps"])

        for file, line, func, args in self.cursor.fetchall():
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
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IS NOT NULL
            ORDER BY file, line
        """)

        static_patterns = frozenset(["express.static", "serve-static", "koa-static"])

        for file, line, func, args in self.cursor.fetchall():
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
        self.cursor.execute("""
            SELECT path, line, name
            FROM symbols
            WHERE name IS NOT NULL
            ORDER BY path, line
        """)

        generation_patterns = frozenset(
            ["generateSourceMap", "createSourceMap", "writeSourceMap", "sourceMappingURL"]
        )
        test_patterns = frozenset(["test", "spec"])

        for file, line, name in self.cursor.fetchall():
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
        """Analyze build artifacts for exposed source maps.

        This MUST use file I/O because build outputs are not in the database.
        """
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


def find_sourcemap_issues(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect source map exposure vulnerabilities.

    Uses hybrid approach:
    - Database: Build configurations, webpack settings
    - File I/O: Actual .map files and JavaScript in build directories

    Args:
        context: Standardized rule context with database and project paths

    Returns:
        List of source map exposure findings
    """
    analyzer = SourcemapAnalyzer(context)
    return analyzer.analyze()


def register_taint_patterns(taint_registry):
    """Register source map related taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
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
