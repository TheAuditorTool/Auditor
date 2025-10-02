"""Source Map Exposure Analyzer - Hybrid Database + File I/O Approach.

Detects exposed source maps using a JUSTIFIED HYBRID approach because:
1. Source maps are BUILD ARTIFACTS not indexed in database
2. .map files exist only in dist/build directories
3. Inline maps are added by bundlers, not in source
4. sourceMappingURL comments are in generated files

Follows golden standard patterns from bundle_analyze.py:
- Frozensets for all patterns
- Table existence checks
- Graceful degradation
- Proper confidence levels
- Minimal file I/O (last 5KB only)
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Set
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata


# ============================================================================
# METADATA (Orchestrator Discovery)
# ============================================================================

METADATA = RuleMetadata(
    name="sourcemap_exposure",
    category="security",
    target_extensions=['.js', '.js.map', '.ts.map', '.mjs', '.cjs'],
    exclude_patterns=['node_modules/', 'test/', 'spec/', '__tests__/'],
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class SourcemapPatterns:
    """Immutable pattern definitions for source map detection."""

    # Production build directories to scan
    PRODUCTION_PATHS = frozenset([
        'dist', 'build', 'out', 'public', 'static',
        'assets', 'bundle', '_next', '.next', 'output',
        'www', 'web', 'compiled', 'generated', 'release'
    ])

    # Source map file extensions
    MAP_EXTENSIONS = frozenset([
        '.js.map', '.mjs.map', '.cjs.map', '.jsx.map',
        '.ts.map', '.tsx.map', '.min.js.map', '.bundle.js.map'
    ])

    # Dangerous webpack devtool values for production
    DANGEROUS_DEVTOOLS = frozenset([
        'eval', 'eval-source-map', 'eval-cheap-source-map',
        'eval-cheap-module-source-map', 'inline-source-map',
        'inline-cheap-source-map', 'inline-cheap-module-source-map',
        'hidden-source-map', 'nosources-source-map'
    ])

    # Safe devtool values (external maps or none)
    SAFE_DEVTOOLS = frozenset([
        'false', 'none', 'source-map', 'hidden-source-map'
    ])

    # Build tool config files
    BUILD_CONFIGS = frozenset([
        'webpack.config', 'webpack.prod', 'webpack.production',
        'rollup.config', 'vite.config', 'next.config',
        'tsconfig', 'jsconfig', 'babel.config', 'parcel'
    ])

    # JavaScript file extensions to check
    JS_EXTENSIONS = frozenset([
        '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx'
    ])

    # Source map URL patterns
    SOURCEMAP_URL_PATTERNS = frozenset([
        'sourceMappingURL=', 'sourceURL=', '# sourceMappingURL',
        '@ sourceMappingURL', '//# sourceMappingURL', '//@ sourceURL'
    ])

    # Inline map indicators
    INLINE_MAP_INDICATORS = frozenset([
        'data:application/json;base64,',
        'data:application/json;charset=utf-8;base64,',
        'sourcesContent":', '"mappings":"'
    ])

    # Files to skip
    SKIP_PATTERNS = frozenset([
        'node_modules', '.git', 'vendor', 'third_party',
        'external', 'lib', 'bower_components', 'jspm_packages'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

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
        self.existing_tables = set()
        self.seen_files = set()  # Deduplication

    def analyze(self) -> List[StandardFinding]:
        """Main analysis entry point using hybrid approach.

        Returns:
            List of source map exposure findings
        """
        # Part 1: Database Analysis (Configurations)
        if self.context.db_path:
            self._analyze_database()

        # Part 2: File I/O Analysis (Build Artifacts)
        # This is REQUIRED because build outputs aren't in database
        if self.context.project_path:
            self._analyze_build_artifacts()

        return self.findings

    # ========================================================================
    # PART 1: DATABASE ANALYSIS (Configurations)
    # ========================================================================

    def _analyze_database(self):
        """Analyze database for source map configurations."""
        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Check available tables
            self._check_table_availability()

            # Run database checks
            if 'assignments' in self.existing_tables:
                self._check_webpack_configs()
                self._check_typescript_configs()
                self._check_build_tool_configs()

            if 'function_call_args' in self.existing_tables:
                self._check_sourcemap_plugins()
                self._check_express_static()

            if 'symbols' in self.existing_tables:
                self._check_sourcemap_generation()

        finally:
            conn.close()

    def _check_table_availability(self):
        """Check which tables exist for graceful degradation."""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'assignments', 'function_call_args', 'symbols',
                'files', 'api_endpoints', 'config_files'
            )
        """)
        self.existing_tables = {row[0] for row in self.cursor.fetchall()}

    def _check_webpack_configs(self):
        """Check webpack configurations for source map settings."""
        # Check for dangerous devtool settings
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var LIKE '%devtool%'
              AND (file LIKE '%webpack%' OR file LIKE '%config%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            if not expr:
                continue

            expr_lower = expr.lower().strip().strip('"\'')

            # Check against dangerous patterns
            for dangerous in self.patterns.DANGEROUS_DEVTOOLS:
                if dangerous in expr_lower:
                    # Higher severity for eval-based (exposes source in browser)
                    is_eval = 'eval' in dangerous
                    is_inline = 'inline' in dangerous

                    severity = Severity.CRITICAL if (is_eval or is_inline) else Severity.HIGH

                    self.findings.append(StandardFinding(
                        rule_name='webpack-dangerous-devtool',
                        message=f'Webpack devtool "{dangerous}" exposes source code',
                        file_path=file,
                        line=line,
                        severity=severity,
                        category='security',
                        snippet=f'devtool: "{dangerous}"',
                        confidence=Confidence.HIGH,
                        cwe_id='CWE-540'  # Inclusion of Sensitive Information in Source Code
                    ))
                    break

            # Check for any source map generation in production
            if 'production' in file.lower() and expr_lower not in ['false', 'none', '']:
                if expr_lower not in self.patterns.SAFE_DEVTOOLS:
                    self.findings.append(StandardFinding(
                        rule_name='production-sourcemap-enabled',
                        message='Source maps enabled in production webpack config',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='security',
                        snippet=f'devtool: {expr[:50]}',
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-540'
                    ))

    def _check_typescript_configs(self):
        """Check TypeScript configurations for source map settings."""
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (target_var LIKE '%sourceMap%' OR target_var LIKE '%inlineSourceMap%')
              AND file LIKE '%tsconfig%'
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            if expr and 'true' in expr.lower():
                is_inline = 'inline' in var.lower()

                self.findings.append(StandardFinding(
                    rule_name='typescript-sourcemap-enabled',
                    message=f'TypeScript {"inline " if is_inline else ""}source maps enabled',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH if is_inline else Severity.MEDIUM,
                    category='security',
                    snippet=f'{var}: true',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-540'
                ))

    def _check_build_tool_configs(self):
        """Check other build tool configurations."""
        # Check Vite configs
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE target_var LIKE '%sourcemap%'
              AND (file LIKE '%vite%' OR file LIKE '%rollup%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            if expr and any(val in expr.lower() for val in ['true', 'inline', 'hidden']):
                self.findings.append(StandardFinding(
                    rule_name='build-tool-sourcemap',
                    message='Source map generation enabled in build config',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='security',
                    snippet=f'{var}: {expr[:50]}',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-540'
                ))

    def _check_sourcemap_plugins(self):
        """Check for source map plugins in build tools."""
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE (callee_function LIKE '%SourceMapDevToolPlugin%'
                   OR callee_function LIKE '%SourceMapPlugin%'
                   OR callee_function LIKE '%sourceMaps%')
              AND file LIKE '%webpack%'
            ORDER BY file, line
        """)

        for file, line, func, args in self.cursor.fetchall():
            self.findings.append(StandardFinding(
                rule_name='sourcemap-plugin-used',
                message=f'Source map plugin {func} detected',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                snippet=f'{func}({args[:50] if args else ""}...)',
                confidence=Confidence.HIGH,
                cwe_id='CWE-540'
            ))

    def _check_express_static(self):
        """Check if Express static serving might expose .map files."""
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE (callee_function LIKE '%express.static%'
                   OR callee_function LIKE '%serve-static%'
                   OR callee_function LIKE '%koa-static%')
            ORDER BY file, line
        """)

        for file, line, func, args in self.cursor.fetchall():
            # Check if there's filtering to exclude .map files
            if args and '.map' not in str(args) and 'filter' not in str(args):
                self.findings.append(StandardFinding(
                    rule_name='static-serving-maps',
                    message='Static file serving may expose .map files',
                    file_path=file,
                    line=line,
                    severity=Severity.LOW,
                    category='security',
                    snippet=f'{func}({args[:50] if args else ""})',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-540'
                ))

    def _check_sourcemap_generation(self):
        """Check for source map generation in code."""
        self.cursor.execute("""
            SELECT path, line, name
            FROM symbols
            WHERE (name LIKE '%generateSourceMap%'
                   OR name LIKE '%createSourceMap%'
                   OR name LIKE '%writeSourceMap%'
                   OR name LIKE '%sourceMappingURL%')
              AND path NOT LIKE '%test%'
              AND path NOT LIKE '%spec%'
            ORDER BY path, line
        """)

        for file, line, name in self.cursor.fetchall():
            if 'sourceMappingURL' in name:
                confidence = Confidence.MEDIUM
                message = 'Source map URL generation detected'
            else:
                confidence = Confidence.LOW
                message = 'Source map generation function detected'

            self.findings.append(StandardFinding(
                rule_name='sourcemap-generation-code',
                message=message,
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='security',
                snippet=name,
                confidence=confidence,
                cwe_id='CWE-540'
            ))

    # ========================================================================
    # PART 2: FILE I/O ANALYSIS (Build Artifacts) - REQUIRED
    # ========================================================================

    def _analyze_build_artifacts(self):
        """Analyze build artifacts for exposed source maps.

        This MUST use file I/O because build outputs are not in the database.
        """
        project_root = Path(self.context.project_path)

        # Find production build directories
        build_dirs = self._find_build_directories(project_root)

        if not build_dirs:
            return  # No build directories found

        for build_dir in build_dirs:
            # 1. Scan for .map files
            self._scan_map_files(build_dir, project_root)

            # 2. Check JavaScript files for source map references
            self._scan_javascript_files(build_dir, project_root)

    def _find_build_directories(self, project_root: Path) -> List[Path]:
        """Find production build directories."""
        build_dirs = []

        for dir_name in self.patterns.PRODUCTION_PATHS:
            dir_path = project_root / dir_name
            if dir_path.exists() and dir_path.is_dir():
                # Skip if it's a source directory (has .ts/.tsx files)
                ts_files = list(dir_path.glob('**/*.ts')) + list(dir_path.glob('**/*.tsx'))
                if len(ts_files) > 5:  # Likely source, not build
                    continue
                build_dirs.append(dir_path)

        # Also check if project root itself is build output
        if self._is_likely_build_output(project_root):
            build_dirs.append(project_root)

        return build_dirs

    def _is_likely_build_output(self, directory: Path) -> bool:
        """Check if directory contains build artifacts."""
        # Check for minified files
        minified = list(directory.glob('*.min.js'))[:5]
        if minified:
            return True

        # Check for webpack chunks
        chunks = list(directory.glob('*.[hash].js'))[:5] + list(directory.glob('chunk.*.js'))[:5]
        if chunks:
            return True

        # Check for common bundle files
        bundle_files = ['bundle.js', 'main.js', 'app.js', 'vendor.js']
        for bundle in bundle_files:
            if (directory / bundle).exists():
                return True

        return False

    def _scan_map_files(self, build_dir: Path, project_root: Path):
        """Scan for exposed .map files."""
        map_count = 0

        for ext in self.patterns.MAP_EXTENSIONS:
            pattern = f'*{ext}'
            for map_file in build_dir.rglob(pattern):
                # Skip vendor/node_modules
                if any(skip in str(map_file) for skip in self.patterns.SKIP_PATTERNS):
                    continue

                map_count += 1
                if map_count > 50:  # Limit to prevent overwhelming output
                    return

                try:
                    relative_path = map_file.relative_to(project_root)
                    file_size = map_file.stat().st_size

                    # Check if it's a JavaScript source map by reading first line
                    is_js_map = False
                    try:
                        with open(map_file, 'r', encoding='utf-8', errors='ignore') as f:
                            first_line = f.read(200)  # Read first 200 chars
                            if '"sources"' in first_line or '"mappings"' in first_line:
                                is_js_map = True
                    except:
                        is_js_map = True  # Assume JS if can't read

                    if is_js_map:
                        # Larger files are more concerning (more source exposed)
                        if file_size > 1000000:  # > 1MB
                            severity = Severity.CRITICAL
                            confidence = Confidence.HIGH
                        elif file_size > 100000:  # > 100KB
                            severity = Severity.HIGH
                            confidence = Confidence.HIGH
                        else:
                            severity = Severity.MEDIUM
                            confidence = Confidence.MEDIUM

                        self.findings.append(StandardFinding(
                            rule_name='sourcemap-file-exposed',
                            message=f'Source map file exposed ({file_size:,} bytes)',
                            file_path=str(relative_path),
                            line=1,
                            severity=severity,
                            category='security',
                            snippet=map_file.name,
                            confidence=confidence,
                            cwe_id='CWE-540'
                        ))

                except (OSError, ValueError):
                    continue

    def _scan_javascript_files(self, build_dir: Path, project_root: Path):
        """Scan JavaScript files for source map references."""
        js_count = 0

        for ext in self.patterns.JS_EXTENSIONS:
            for js_file in build_dir.glob(f'**/*{ext}'):
                # Skip vendor/node_modules
                if any(skip in str(js_file) for skip in self.patterns.SKIP_PATTERNS):
                    continue

                js_count += 1
                if js_count > 100:  # Limit file scanning
                    return

                # Skip if already seen
                if str(js_file) in self.seen_files:
                    continue
                self.seen_files.add(str(js_file))

                try:
                    relative_path = js_file.relative_to(project_root)

                    # Smart reading: only last 5KB for performance
                    file_size = js_file.stat().st_size
                    with open(js_file, 'rb') as f:
                        # Seek to last 5KB
                        read_size = min(5000, file_size)
                        f.seek(max(0, file_size - read_size))
                        content_bytes = f.read()

                    # Decode with error handling
                    try:
                        content_tail = content_bytes.decode('utf-8', errors='ignore')
                    except:
                        continue

                    # Check for source map URL comment
                    has_external_map = False
                    has_inline_map = False
                    map_reference = None

                    for pattern in self.patterns.SOURCEMAP_URL_PATTERNS:
                        if pattern in content_tail:
                            # Check if inline or external
                            for indicator in self.patterns.INLINE_MAP_INDICATORS:
                                if indicator in content_tail:
                                    has_inline_map = True
                                    break

                            if not has_inline_map:
                                has_external_map = True
                                # Try to extract map filename
                                import re
                                match = re.search(r'sourceMappingURL=([^\s\n]+)', content_tail)
                                if match:
                                    map_reference = match.group(1)
                            break

                    if has_inline_map:
                        self.findings.append(StandardFinding(
                            rule_name='inline-sourcemap-exposed',
                            message='Inline source map embedded in production JavaScript',
                            file_path=str(relative_path),
                            line=1,  # Can't determine exact line efficiently
                            severity=Severity.CRITICAL,
                            category='security',
                            snippet='//# sourceMappingURL=data:application/json;base64,...',
                            confidence=Confidence.HIGH,
                            cwe_id='CWE-540'
                        ))

                    elif has_external_map:
                        # Check if referenced .map file exists
                        map_exists = False
                        if map_reference and not map_reference.startswith('data:'):
                            map_path = js_file.parent / map_reference
                            map_exists = map_path.exists()

                        self.findings.append(StandardFinding(
                            rule_name='sourcemap-url-exposed',
                            message=f'Source map URL in production JS: {map_reference or "unknown"}',
                            file_path=str(relative_path),
                            line=1,
                            severity=Severity.HIGH if map_exists else Severity.MEDIUM,
                            category='security',
                            snippet=f'//# sourceMappingURL={map_reference or "..."}',
                            confidence=Confidence.HIGH if map_exists else Confidence.MEDIUM,
                            cwe_id='CWE-540'
                        ))

                except (OSError, ValueError):
                    continue


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_sourcemap_issues(context: StandardRuleContext) -> List[StandardFinding]:
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


# ============================================================================
# TAINT REGISTRATION (For Orchestrator)
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register source map related taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = SourcemapPatterns()

    # Register source map generation as a sink
    taint_sinks = [
        'generateSourceMap', 'createSourceMap', 'writeSourceMap',
        'SourceMapGenerator', 'SourceMapDevToolPlugin'
    ]

    for sink in taint_sinks:
        taint_registry.register_sink(sink, 'sourcemap_generation', 'javascript')

    # Register devtool configs as sensitive
    for devtool in patterns.DANGEROUS_DEVTOOLS:
        taint_registry.register_sink(f'devtool: "{devtool}"', 'dangerous_config', 'javascript')