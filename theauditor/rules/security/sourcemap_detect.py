"""Source map exposure detector for production builds - Golden Standard.

This module detects exposed source maps using a hybrid approach:
- Database queries for indexed JavaScript files
- Direct file I/O for scanning build artifacts
"""

import re
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from theauditor.utils.logger import setup_logger

logger = setup_logger(__name__)


def detect_sourcemap_patterns(db_path: str) -> List[Dict[str, Any]]:
    """
    Detect exposed source maps using hybrid database + file I/O approach.
    
    This follows the golden standard pattern while maintaining necessary file operations
    for deployment artifact scanning.
    
    Args:
        db_path: Path to the repo_index.db database
        
    Returns:
        List of security findings in StandardFinding format
    """
    findings = []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get project root from database
        cursor.execute("SELECT DISTINCT file FROM files LIMIT 1")
        sample_file = cursor.fetchone()
        if not sample_file:
            return findings
            
        project_root = Path(sample_file[0]).parent
        while project_root.parent != project_root and not (project_root / '.git').exists():
            project_root = project_root.parent
        
        # Pattern 1: Find JavaScript files with sourcemap URLs in database
        findings.extend(_find_sourcemap_urls_in_db(cursor))
        
        # Pattern 2: Find inline sourcemaps in indexed files
        findings.extend(_find_inline_sourcemaps_in_db(cursor))
        
        # Pattern 3: Scan build directories for .map files (file I/O required)
        findings.extend(_scan_build_artifacts(project_root))
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error detecting sourcemap patterns: {e}")
    
    return findings


def _find_sourcemap_urls_in_db(cursor) -> List[Dict[str, Any]]:
    """Find sourceMappingURL comments in indexed JavaScript files."""
    findings = []
    
    # Query for JavaScript files in production directories
    production_paths = ['dist/', 'build/', 'out/', 'public/', 'static/', 'bundle/', '_next/']
    
    conditions = ' OR '.join([f"f.file LIKE '%{path}%'" for path in production_paths])
    
    cursor.execute(f"""
        SELECT f.file, f.extension
        FROM files f
        WHERE f.extension IN ('js', 'mjs', 'cjs', 'jsx')
          AND ({conditions})
    """)
    
    js_files = cursor.fetchall()
    
    # Pattern for source map URLs
    url_pattern = re.compile(
        r'//[#@]\s*sourceMappingURL\s*=\s*([^\s]+\.map)',
        re.IGNORECASE
    )
    
    for file_path, ext in js_files:
        try:
            # Read last portion of file for performance
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(0, 2)  # Go to end
                file_size = f.tell()
                read_size = min(5000, file_size)
                f.seek(max(0, file_size - read_size))
                content_tail = f.read()
            
            # Check for source map URL
            url_match = url_pattern.search(content_tail)
            if url_match:
                map_url = url_match.group(1)
                
                # Check if map file exists
                map_path = Path(file_path).parent / map_url
                map_exists = map_path.exists()
                
                findings.append({
                    'rule_id': 'sourcemap-url-exposed',
                    'message': f'Source map URL in production JavaScript: {map_url}',
                    'file': file_path,
                    'line': 0,  # Would need full file scan for exact line
                    'column': 0,
                    'severity': 'high' if map_exists else 'medium',
                    'category': 'security',
                    'confidence': 'high',
                    'description': f'Source map {"exists and" if map_exists else "referenced but not found,"} may expose original source code. Remove sourceMappingURL comments from production builds.'
                })
                
        except (OSError, UnicodeDecodeError):
            continue
    
    return findings


def _find_inline_sourcemaps_in_db(cursor) -> List[Dict[str, Any]]:
    """Find inline base64 sourcemaps in indexed JavaScript files."""
    findings = []
    
    # Inline source map pattern
    inline_pattern = re.compile(
        r'//[#@]\s*sourceMappingURL\s*=\s*data:application/json[^,]*;base64,',
        re.IGNORECASE
    )
    
    # Query for production JavaScript files
    production_paths = ['dist/', 'build/', 'out/', 'public/', 'static/', 'bundle/', '_next/']
    conditions = ' OR '.join([f"f.file LIKE '%{path}%'" for path in production_paths])
    
    cursor.execute(f"""
        SELECT f.file, f.size
        FROM files f
        WHERE f.extension IN ('js', 'mjs', 'cjs', 'jsx')
          AND ({conditions})
          AND f.size > 10000
    """)
    
    large_js_files = cursor.fetchall()
    
    for file_path, size in large_js_files:
        try:
            # Read last portion of file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(0, 2)
                file_size = f.tell()
                read_size = min(5000, file_size)
                f.seek(max(0, file_size - read_size))
                content_tail = f.read()
            
            # Check for inline source map
            if inline_pattern.search(content_tail):
                findings.append({
                    'rule_id': 'inline-sourcemap-exposed',
                    'message': 'Inline source map embedded in production JavaScript',
                    'file': file_path,
                    'line': 0,
                    'column': 0,
                    'severity': 'high',
                    'category': 'security',
                    'confidence': 'high',
                    'description': 'Full source code embedded as base64 in production file. Disable inline source maps in production build configuration.'
                })
                
        except (OSError, UnicodeDecodeError):
            continue
    
    return findings


def _scan_build_artifacts(project_root: Path) -> List[Dict[str, Any]]:
    """Scan build directories for exposed .map files."""
    findings = []
    
    # Common production build directories
    build_dirs = ['dist', 'build', 'out', 'public', 'static', 'assets', 'bundle', '_next']
    
    # Find existing build directories
    existing_dirs = []
    for dir_name in build_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists() and dir_path.is_dir():
            existing_dirs.append(dir_path)
    
    # Check if project root itself is build output
    if _is_likely_build_output(project_root):
        existing_dirs.append(project_root)
    
    # Scan for .map files
    for build_dir in existing_dirs:
        try:
            # Use rglob but limit depth for performance
            for map_file in build_dir.rglob('*.map'):
                # Skip vendor and hidden directories
                if any(skip in str(map_file) for skip in ['node_modules', '.git', 'vendor', 'third_party']):
                    continue
                
                # Check if it's a JavaScript source map
                if map_file.name.endswith(('.js.map', '.mjs.map', '.cjs.map')):
                    try:
                        relative_path = map_file.relative_to(project_root)
                        
                        findings.append({
                            'rule_id': 'sourcemap-file-exposed',
                            'message': f'Source map file exposed in production: {map_file.name}',
                            'file': str(map_file),
                            'line': 0,
                            'column': 0,
                            'severity': 'high',
                            'category': 'security',
                            'confidence': 'high',
                            'description': f'Source map in {build_dir.name}/ exposes original source code structure. Remove .map files from production builds or block access via server configuration.'
                        })
                        
                    except ValueError:
                        continue
                        
        except OSError:
            continue
    
    return findings


def _is_likely_build_output(directory: Path) -> bool:
    """Check if directory contains build artifacts."""
    # Check for minified files
    minified = list(directory.glob('*.min.js')[:5])  # Limit for performance
    if minified:
        return True
    
    # Check for common bundle files
    bundle_indicators = ['main.js', 'bundle.js', 'app.js', 'vendor.js', 'chunk.js']
    for indicator in bundle_indicators:
        if (directory / indicator).exists():
            return True
    
    return False


# Compatibility wrapper for file-based callers
def find_source_maps(project_path: str) -> List[Dict[str, Any]]:
    """
    Legacy compatibility wrapper that uses file I/O.
    New code should use detect_sourcemap_patterns with database.
    """
    # Try to find database
    db_path = Path(project_path) / '.pf' / 'repo_index.db'
    if db_path.exists():
        return detect_sourcemap_patterns(str(db_path))
    
    # Fallback to pure file scanning
    findings = []
    project_root = Path(project_path)
    findings.extend(_scan_build_artifacts(project_root))
    return findings


# For direct CLI usage
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        findings = detect_sourcemap_patterns(db_path)
        for finding in findings:
            print(f"{finding['file']}:{finding['line']} - {finding['message']}")