"""Source Map Exposure Detector - Pure Database Implementation.

This module detects exposed source maps using ONLY indexed database data.
NO AST TRAVERSAL. NO FILE I/O. Just efficient SQL queries.
"""

import sqlite3
from typing import List
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_sourcemap_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect exposed source maps using indexed database.
    
    Returns:
        List of source map exposure findings
    """
    findings = []
    
    if not context.db_path:
        return findings
    
    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()
    
    try:
        # Pattern 1: Find sourceMappingURL references in symbols
        findings.extend(_find_sourcemap_urls(cursor))
        
        # Pattern 2: Find .map files in production directories
        findings.extend(_find_map_files(cursor))
        
        # Pattern 3: Find inline source maps in JavaScript files
        findings.extend(_find_inline_sourcemaps(cursor))
        
        # Pattern 4: Find source map generation in build configs
        findings.extend(_find_sourcemap_config(cursor))
        
        # Pattern 5: Find webpack devtool settings
        findings.extend(_find_webpack_sourcemap_settings(cursor))
        
        # Pattern 6: Find source map headers in server configs
        findings.extend(_find_sourcemap_headers(cursor))
        
    finally:
        conn.close()
    
    return findings


def _find_sourcemap_urls(cursor) -> List[StandardFinding]:
    """Find sourceMappingURL comments in production JavaScript."""
    findings = []
    
    # Look for sourceMappingURL in symbols and strings
    cursor.execute("""
        SELECT s.file, s.line, s.name
        FROM symbols s
        WHERE s.file LIKE '%.js' 
          AND (s.name LIKE '%sourceMappingURL%'
               OR s.name LIKE '%sourceURL%'
               OR s.name LIKE '%.map%')
          AND (s.file LIKE '%dist/%'
               OR s.file LIKE '%build/%'
               OR s.file LIKE '%public/%'
               OR s.file LIKE '%static/%'
               OR s.file LIKE '%bundle/%'
               OR s.file LIKE '%_next/%'
               OR s.file LIKE '%out/%')
        ORDER BY s.file, s.line
    """)
    
    for file, line, name in cursor.fetchall():
        # Check if it's a source map reference
        if 'sourceMappingURL' in name or '.map' in name:
            findings.append(StandardFinding(
                rule_name='sourcemap-url-exposed',
                message='Source map URL reference in production JavaScript',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                category='security',
                snippet=name[:100],
                fix_suggestion='Remove sourceMappingURL comments from production builds',
                cwe_id='CWE-200'
            ))
    
    # Also check in assignments for dynamically generated URLs
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%sourceMappingURL%'
               OR a.source_expr LIKE '%sourceURL%'
               OR a.source_expr LIKE '%.map%')
          AND (a.file LIKE '%webpack%'
               OR a.file LIKE '%rollup%'
               OR a.file LIKE '%vite%'
               OR a.file LIKE '%build%')
    """)
    
    for file, line, var, expr in cursor.fetchall():
        if expr and ('sourceMappingURL' in expr or '.map' in expr):
            findings.append(StandardFinding(
                rule_name='sourcemap-generation',
                message='Source map generation detected in build configuration',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                snippet=f'{var} = {expr[:50]}...' if len(expr) > 50 else f'{var} = {expr}',
                fix_suggestion='Disable source map generation for production builds',
                cwe_id='CWE-200'
            ))
    
    return findings


def _find_map_files(cursor) -> List[StandardFinding]:
    """Find .map files in production directories."""
    findings = []
    
    # Query for .map files in production paths
    cursor.execute("""
        SELECT f.file, f.size
        FROM files f
        WHERE f.extension = 'map'
          AND (f.file LIKE '%dist/%'
               OR f.file LIKE '%build/%'
               OR f.file LIKE '%public/%'
               OR f.file LIKE '%static/%'
               OR f.file LIKE '%bundle/%'
               OR f.file LIKE '%_next/%'
               OR f.file LIKE '%out/%'
               OR f.file LIKE '%assets/%')
          AND f.file NOT LIKE '%node_modules/%'
          AND f.file NOT LIKE '%vendor/%'
        ORDER BY f.file
    """)
    
    for file, size in cursor.fetchall():
        # Check if it's a JavaScript source map (ends with .js.map, .mjs.map, etc.)
        if any(file.endswith(ext) for ext in ['.js.map', '.mjs.map', '.cjs.map', '.jsx.map', '.ts.map', '.tsx.map']):
            # Large map files are more concerning
            severity = Severity.CRITICAL if size > 100000 else Severity.HIGH
            
            findings.append(StandardFinding(
                rule_name='sourcemap-file-exposed',
                message=f'Source map file in production directory ({size} bytes)',
                file_path=file,
                line=1,
                severity=severity,
                category='security',
                snippet=file.split('/')[-1],
                fix_suggestion='Remove .map files from production or block access via server config',
                cwe_id='CWE-200'
            ))
    
    return findings


def _find_inline_sourcemaps(cursor) -> List[StandardFinding]:
    """Find inline base64 source maps in JavaScript files."""
    findings = []
    
    # Look for data:application/json base64 patterns
    cursor.execute("""
        SELECT s.file, s.line, s.name
        FROM symbols s
        WHERE s.symbol_type = 'string'
          AND (s.name LIKE '%data:application/json%base64%'
               OR s.name LIKE '%sourceMap:%'
               OR s.name LIKE '%sourcesContent%')
          AND s.file LIKE '%.js'
          AND (s.file LIKE '%dist/%'
               OR s.file LIKE '%build/%'
               OR s.file LIKE '%public/%')
    """)
    
    for file, line, content in cursor.fetchall():
        if 'data:application/json' in content and 'base64' in content:
            findings.append(StandardFinding(
                rule_name='inline-sourcemap-exposed',
                message='Inline source map embedded in production JavaScript',
                file_path=file,
                line=line,
                severity=Severity.CRITICAL,
                category='security',
                snippet=content[:50] + '...',
                fix_suggestion='Disable inline source maps in production build configuration',
                cwe_id='CWE-200'
            ))
    
    # Check for large string assignments that might be inline maps
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, LENGTH(a.source_expr) as expr_len
        FROM assignments a
        WHERE a.target_var LIKE '%sourceMap%'
          AND LENGTH(a.source_expr) > 10000
          AND a.file LIKE '%.js'
    """)
    
    for file, line, var, expr_len in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='large-inline-sourcemap',
            message=f'Large inline source map detected ({expr_len} characters)',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=f'{var} = <large base64 data>',
            fix_suggestion='Use external source maps or disable them in production',
            cwe_id='CWE-200'
        ))
    
    return findings


def _find_sourcemap_config(cursor) -> List[StandardFinding]:
    """Find source map generation in build configurations."""
    findings = []
    
    # Check for source map settings in config files
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE (a.target_var LIKE '%sourceMap%'
               OR a.target_var LIKE '%devtool%'
               OR a.target_var LIKE '%sourcemap%')
          AND (a.source_expr LIKE '%true%'
               OR a.source_expr LIKE '%inline%'
               OR a.source_expr LIKE '%eval%'
               OR a.source_expr LIKE '%cheap%')
          AND (a.file LIKE '%webpack%'
               OR a.file LIKE '%rollup%'
               OR a.file LIKE '%vite%'
               OR a.file LIKE '%tsconfig%'
               OR a.file LIKE '%next.config%')
    """)
    
    for file, line, var, expr in cursor.fetchall():
        # Check if it's enabling source maps
        if expr and any(val in expr.lower() for val in ['true', 'inline', 'eval', 'cheap-source-map']):
            # Check if it's a production config
            is_prod = 'prod' in file.lower() or 'production' in expr.lower()
            
            if is_prod:
                severity = Severity.HIGH
                message = 'Source maps enabled in production configuration'
            else:
                severity = Severity.MEDIUM
                message = 'Source maps enabled - ensure disabled for production'
            
            findings.append(StandardFinding(
                rule_name='sourcemap-config-enabled',
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category='security',
                snippet=f'{var} = {expr[:50]}...' if len(expr) > 50 else f'{var} = {expr}',
                fix_suggestion='Set sourceMap: false or devtool: false for production builds',
                cwe_id='CWE-200'
            ))
    
    return findings


def _find_webpack_sourcemap_settings(cursor) -> List[StandardFinding]:
    """Find webpack devtool settings that generate source maps."""
    findings = []
    
    # Dangerous devtool values for production
    dangerous_devtools = [
        'eval', 'eval-source-map', 'eval-cheap-source-map',
        'eval-cheap-module-source-map', 'inline-source-map',
        'inline-cheap-source-map', 'inline-cheap-module-source-map'
    ]
    
    cursor.execute("""
        SELECT a.file, a.line, a.target_var, a.source_expr
        FROM assignments a
        WHERE a.target_var LIKE '%devtool%'
          AND a.file LIKE '%webpack%'
    """)
    
    for file, line, var, expr in cursor.fetchall():
        if expr:
            expr_lower = expr.lower()
            for dangerous in dangerous_devtools:
                if dangerous in expr_lower:
                    findings.append(StandardFinding(
                        rule_name='webpack-dangerous-devtool',
                        message=f'Webpack devtool "{dangerous}" exposes source code',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        category='security',
                        snippet=f'devtool: "{dangerous}"',
                        fix_suggestion='Use devtool: false or source-map for production (external files)',
                        cwe_id='CWE-200'
                    ))
                    break
    
    # Check for SourceMapDevToolPlugin
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function
        FROM function_call_args f
        WHERE f.callee_function LIKE '%SourceMapDevToolPlugin%'
          AND f.file LIKE '%webpack%'
    """)
    
    for file, line, func in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='webpack-sourcemap-plugin',
            message='SourceMapDevToolPlugin detected - may expose source maps',
            file_path=file,
            line=line,
            severity=Severity.MEDIUM,
            category='security',
            snippet=func,
            fix_suggestion='Remove SourceMapDevToolPlugin from production webpack config',
            cwe_id='CWE-200'
        ))
    
    return findings


def _find_sourcemap_headers(cursor) -> List[StandardFinding]:
    """Find source map headers in server configurations."""
    findings = []
    
    # Check for X-SourceMap headers
    cursor.execute("""
        SELECT a.file, a.line, a.source_expr
        FROM assignments a
        WHERE (a.source_expr LIKE '%X-SourceMap%'
               OR a.source_expr LIKE '%SourceMap:%'
               OR a.source_expr LIKE '%source-map%')
          AND (a.file LIKE '%nginx%'
               OR a.file LIKE '%apache%'
               OR a.file LIKE '%server%'
               OR a.file LIKE '%express%')
    """)
    
    for file, line, expr in cursor.fetchall():
        findings.append(StandardFinding(
            rule_name='sourcemap-http-header',
            message='Source map HTTP header configuration detected',
            file_path=file,
            line=line,
            severity=Severity.HIGH,
            category='security',
            snippet=expr[:100],
            fix_suggestion='Remove X-SourceMap headers from production server configuration',
            cwe_id='CWE-200'
        ))
    
    # Check for Express static middleware serving .map files
    cursor.execute("""
        SELECT f.file, f.line, f.callee_function, f.argument_expr
        FROM function_call_args f
        WHERE f.callee_function LIKE '%express.static%'
           OR f.callee_function LIKE '%serve-static%'
    """)
    
    for file, line, func, args in cursor.fetchall():
        # Check if there's filtering to exclude .map files
        if args and '.map' not in args:
            findings.append(StandardFinding(
                rule_name='static-serving-maps',
                message='Static file serving may expose .map files',
                file_path=file,
                line=line,
                severity=Severity.MEDIUM,
                category='security',
                snippet=f'{func}({args[:50]}...)' if len(args) > 50 else f'{func}({args})',
                fix_suggestion='Add middleware to block .map file access in production',
                cwe_id='CWE-200'
            ))
    
    return findings