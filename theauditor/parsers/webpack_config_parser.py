"""Parser for webpack.config.js files.

This module provides regex-based parsing of webpack configuration files
to extract security-relevant settings without executing JavaScript code.
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional


class WebpackConfigParser:
    """Parser for webpack.config.js files."""
    
    def __init__(self):
        """Initialize the webpack config parser."""
        pass
    
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a webpack.config.js file and extract security-relevant configuration.
        
        Args:
            file_path: Path to the webpack.config.js file
            
        Returns:
            Dictionary with parsed webpack configuration:
            {
                'devtool': 'source-map',  # or 'hidden-source-map', false, etc.
                'mode': 'production'  # or 'development'
            }
            
            Returns empty dict for keys not found.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._extract_config(content)
            
        except FileNotFoundError:
            return {'error': f'File not found: {file_path}'}
        except PermissionError:
            return {'error': f'Permission denied: {file_path}'}
        except Exception as e:
            return {'error': f'Error reading file: {str(e)}'}
    
    def parse_content(self, content: str, file_path: str = 'unknown') -> Dict[str, Any]:
        """
        Parse webpack configuration content string.
        
        Args:
            content: webpack.config.js content as string
            file_path: Optional file path for reference
            
        Returns:
            Dictionary with parsed webpack configuration
        """
        try:
            return self._extract_config(content)
        except Exception as e:
            return {'error': f'Parsing error: {str(e)}'}
    
    def _extract_config(self, content: str) -> Dict[str, Any]:
        """
        Extract configuration values from webpack config content.
        
        Args:
            content: JavaScript content to parse
            
        Returns:
            Dictionary with extracted configuration values
        """
        result = {}
        
        # Extract devtool setting
        devtool_value = self._extract_devtool(content)
        if devtool_value is not None:
            result['devtool'] = devtool_value
        
        # Extract mode setting
        mode_value = self._extract_mode(content)
        if mode_value is not None:
            result['mode'] = mode_value
        
        return result
    
    def _extract_devtool(self, content: str) -> Optional[str]:
        """
        Extract devtool setting from webpack config.
        
        Handles various formats:
        - devtool: 'source-map'
        - devtool: "eval-source-map"
        - devtool: false
        - devtool: process.env.NODE_ENV === 'production' ? false : 'source-map'
        
        Args:
            content: JavaScript content to parse
            
        Returns:
            The devtool value or None if not found
        """
        # Pattern to match devtool setting
        # Handles: devtool: 'value', devtool: "value", devtool: false, devtool: true
        patterns = [
            # Simple string value with single or double quotes
            r"devtool\s*:\s*['\"]([^'\"]+)['\"]",
            # Boolean value (false/true)
            r"devtool\s*:\s*(false|true)",
            # Ternary operator (capture the production value)
            r"devtool\s*:\s*[^?]+\?\s*['\"]?([^'\":]+)['\"]?\s*:\s*['\"]?([^'\":,}]+)",
            # Variable or expression (capture as-is)
            r"devtool\s*:\s*([a-zA-Z_$][a-zA-Z0-9_$.]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:
                    # Ternary operator - return the production value (first capture)
                    return match.group(1).strip()
                else:
                    # Simple value
                    value = match.group(1).strip()
                    # Clean up the value
                    value = value.replace('"', '').replace("'", '')
                    return value
        
        return None
    
    def _extract_mode(self, content: str) -> Optional[str]:
        """
        Extract mode setting from webpack config.
        
        Handles various formats:
        - mode: 'production'
        - mode: "development"  
        - mode: process.env.NODE_ENV || 'development'
        
        Args:
            content: JavaScript content to parse
            
        Returns:
            The mode value or None if not found
        """
        # Pattern to match mode setting
        patterns = [
            # Simple string value with single or double quotes
            r"mode\s*:\s*['\"]([^'\"]+)['\"]",
            # With OR operator (capture the fallback value)
            r"mode\s*:\s*[^|]+\|\|\s*['\"]([^'\"]+)['\"]",
            # Ternary operator (capture the production value)
            r"mode\s*:\s*[^?]+\?\s*['\"]([^'\"]+)['\"]",
            # Variable reference (capture as-is)
            r"mode\s*:\s*([a-zA-Z_$][a-zA-Z0-9_$.]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # Clean up the value
                value = value.replace('"', '').replace("'", '')
                # Validate it's a known mode
                if value.lower() in ['production', 'development', 'none']:
                    return value.lower()
                # If it's a variable, return as-is
                elif re.match(r'^[a-zA-Z_$]', value):
                    return value
        
        return None
    
    def find_security_issues(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze extracted configuration for security issues.
        
        Args:
            config: Extracted webpack configuration
            
        Returns:
            Dictionary of security findings
        """
        issues = {
            'source_maps_exposed': False,
            'development_mode': False,
            'findings': []
        }
        
        # Check devtool setting for exposed source maps
        devtool = config.get('devtool')
        if devtool and devtool not in ['false', 'none', 'hidden-source-map', 'nosources-source-map']:
            if 'source-map' in str(devtool).lower() and 'hidden' not in str(devtool).lower():
                issues['source_maps_exposed'] = True
                issues['findings'].append({
                    'type': 'source_map_exposure',
                    'severity': 'medium',
                    'value': devtool,
                    'description': 'Source maps are exposed in production, revealing source code structure'
                })
        
        # Check mode setting
        mode = config.get('mode')
        if mode == 'development':
            issues['development_mode'] = True
            issues['findings'].append({
                'type': 'development_mode',
                'severity': 'high',
                'value': mode,
                'description': 'Webpack is configured in development mode for production build'
            })
        
        return issues