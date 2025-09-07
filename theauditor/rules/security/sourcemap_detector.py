"""Source map exposure detector for production builds.

This module detects exposed source maps that can reveal original source code:
1. .map files in production directories
2. Inline source maps (base64 encoded in JS)
3. Source map URLs pointing to external files
"""

import re
from pathlib import Path
from typing import Dict, List, Any


def find_source_maps(project_path: str) -> List[Dict[str, Any]]:
    """
    Detect exposed source maps in production build artifacts.
    
    This function scans common production build directories for:
    1. .map files (external source maps)
    2. Inline source maps embedded in JavaScript files
    3. Source map URLs in JavaScript comments
    
    Args:
        project_path: Root path of the project to analyze
        
    Returns:
        List of source map exposure findings
    """
    findings = []
    project_root = Path(project_path)
    
    # Define common production build directories to scan
    build_dirs = ['dist', 'build', 'out', 'public', 'static', 'assets', 'bundle', '_next']
    
    # Regex patterns for source map detection
    # Inline source map: //# sourceMappingURL=data:application/json;base64,...
    inline_pattern = re.compile(
        r'//[#@]\s*sourceMappingURL\s*=\s*data:application/json[^,]*;base64,',
        re.IGNORECASE
    )
    
    # External source map URL: //# sourceMappingURL=bundle.js.map
    url_pattern = re.compile(
        r'//[#@]\s*sourceMappingURL\s*=\s*([^\s]+\.map)',
        re.IGNORECASE
    )
    
    # Find all build directories that exist
    existing_build_dirs = []
    for dir_name in build_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists() and dir_path.is_dir():
            existing_build_dirs.append(dir_path)
    
    # Also check if project root itself looks like a build output
    # (e.g., deployed directly from build folder)
    if _is_likely_build_output(project_root):
        existing_build_dirs.append(project_root)
    
    # If no build directories found, skip analysis
    if not existing_build_dirs:
        return findings
    
    # Scan each build directory
    for build_dir in existing_build_dirs:
        # 1. Find all .map files
        for map_file in build_dir.rglob('*.map'):
            # Skip node_modules and other vendor directories
            if 'node_modules' in str(map_file) or '.git' in str(map_file):
                continue
            
            try:
                relative_path = map_file.relative_to(project_root)
                
                # Check if it's a JavaScript source map (not CSS map)
                is_js_map = False
                if map_file.name.endswith('.js.map') or map_file.name.endswith('.mjs.map'):
                    is_js_map = True
                else:
                    # Check content to determine type
                    try:
                        with open(map_file, 'r', encoding='utf-8', errors='ignore') as f:
                            first_line = f.readline()
                            if '"sources"' in first_line or '"mappings"' in first_line:
                                is_js_map = True
                    except:
                        is_js_map = True  # Assume JS if can't read
                
                if is_js_map:
                    findings.append({
                        'pattern_name': 'SOURCE_MAP_FILE_EXPOSED',
                        'message': f'Source map file exposed in production: {map_file.name}',
                        'file': str(relative_path),
                        'line': 0,
                        'column': 0,
                        'severity': 'high',
                        'category': 'security',
                        'confidence': 0.95,
                        'details': {
                            'type': 'external_map_file',
                            'build_directory': build_dir.name,
                            'impact': 'Exposes original source code structure and logic',
                            'recommendation': 'Remove .map files from production builds or block access via server config'
                        }
                    })
                    
            except (OSError, ValueError):
                continue
        
        # 2. Scan JavaScript files for inline source maps and URLs
        js_extensions = ['*.js', '*.mjs', '*.cjs', '*.jsx']
        
        for ext in js_extensions:
            for js_file in build_dir.rglob(ext):
                # Skip node_modules and vendor files
                if 'node_modules' in str(js_file) or '.git' in str(js_file):
                    continue
                
                try:
                    relative_path = js_file.relative_to(project_root)
                    
                    # Read file content
                    with open(js_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Only check last 5000 characters for performance
                    # Source maps are typically at the end of files
                    content_tail = content[-5000:] if len(content) > 5000 else content
                    
                    # Check for inline source map
                    inline_match = inline_pattern.search(content_tail)
                    if inline_match:
                        # Find line number
                        line_num = content[:inline_match.start()].count('\n') + 1
                        
                        findings.append({
                            'pattern_name': 'INLINE_SOURCE_MAP_EXPOSED',
                            'message': 'Inline source map embedded in production JavaScript',
                            'file': str(relative_path),
                            'line': line_num,
                            'column': 0,
                            'severity': 'high',
                            'category': 'security',
                            'confidence': 0.95,
                            'details': {
                                'type': 'inline_source_map',
                                'build_directory': build_dir.name,
                                'impact': 'Full source code embedded in production file',
                                'recommendation': 'Disable inline source maps in production build config'
                            }
                        })
                    
                    # Check for external source map URL
                    url_match = url_pattern.search(content_tail)
                    if url_match:
                        map_url = url_match.group(1)
                        line_num = content[:url_match.start()].count('\n') + 1
                        
                        # Check if the referenced .map file actually exists
                        map_path = js_file.parent / map_url
                        file_exists = map_path.exists()
                        
                        findings.append({
                            'pattern_name': 'SOURCE_MAP_URL_EXPOSED',
                            'message': f'Source map URL in production JavaScript: {map_url}',
                            'file': str(relative_path),
                            'line': line_num,
                            'column': 0,
                            'severity': 'high' if file_exists else 'medium',
                            'category': 'security',
                            'confidence': 0.90,
                            'details': {
                                'type': 'source_map_url',
                                'map_url': map_url,
                                'map_exists': file_exists,
                                'build_directory': build_dir.name,
                                'impact': 'Points to source map that may expose original code',
                                'recommendation': 'Remove sourceMappingURL comments from production builds'
                            }
                        })
                        
                except (OSError, ValueError, UnicodeDecodeError):
                    continue
    
    return findings


def _is_likely_build_output(directory: Path) -> bool:
    """
    Check if a directory looks like build output.
    
    Args:
        directory: Path to check
        
    Returns:
        True if directory appears to contain build artifacts
    """
    # Check for minified files or webpack chunks
    minified_files = list(directory.glob('*.min.js')) + list(directory.glob('*.[hash].js'))
    if minified_files:
        return True
    
    # Check for common build output patterns
    build_indicators = ['main.js', 'bundle.js', 'app.js', 'vendor.js', 'index.js']
    for indicator in build_indicators:
        if (directory / indicator).exists():
            return True
    
    return False