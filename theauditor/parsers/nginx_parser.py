"""Parser for nginx configuration files.

This module provides parsing of nginx.conf files to extract
security-relevant configuration from blocks and directives.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


class NginxParser:
    """Parser for nginx configuration files."""
    
    def __init__(self):
        """Initialize the nginx parser."""
        self.blocks = []
        self.current_file = None
    
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse an nginx configuration file and extract security-relevant information.
        
        Args:
            file_path: Path to the nginx.conf file
            
        Returns:
            Dictionary with parsed nginx configuration blocks and directives
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            self.current_file = str(file_path)
            self.blocks = []
            
            # Parse the configuration
            self._parse_content(content)
            
            return {
                'file': str(file_path),
                'blocks': self.blocks
            }
            
        except (FileNotFoundError, PermissionError) as e:
            return {'file': str(file_path), 'blocks': [], 'error': str(e)}
    
    def parse_content(self, content: str, file_path: str = 'unknown') -> Dict[str, Any]:
        """
        Parse nginx configuration content string.
        
        Args:
            content: Nginx configuration content as string
            file_path: Optional file path for reference
            
        Returns:
            Dictionary with parsed nginx configuration
        """
        self.current_file = file_path
        self.blocks = []
        
        try:
            self._parse_content(content)
            return {
                'file': file_path,
                'blocks': self.blocks
            }
        except Exception as e:
            return {'file': file_path, 'blocks': [], 'error': str(e)}
    
    def _parse_content(self, content: str):
        """
        Parse nginx configuration content recursively.
        
        Args:
            content: Configuration content to parse
        """
        # Remove comments
        content = self._remove_comments(content)
        
        # Parse blocks recursively
        self._parse_blocks(content, block_type='root', parent_context='')
    
    def _remove_comments(self, content: str) -> str:
        """Remove comments from nginx configuration."""
        # Remove single-line comments (lines starting with #)
        lines = []
        for line in content.split('\n'):
            # Find comment position (but not within quotes)
            comment_pos = -1
            in_quotes = False
            quote_char = None
            
            for i, char in enumerate(line):
                if char in ['"', "'"] and (i == 0 or line[i-1] != '\\'):
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char:
                        in_quotes = False
                        quote_char = None
                elif char == '#' and not in_quotes:
                    comment_pos = i
                    break
            
            if comment_pos >= 0:
                lines.append(line[:comment_pos])
            else:
                lines.append(line)
        
        return '\n'.join(lines)
    
    def _parse_blocks(self, content: str, block_type: str = 'root', parent_context: str = '', level: int = 0):
        """
        Recursively parse nginx blocks and directives.
        
        Args:
            content: Content to parse
            block_type: Type of current block (root, http, server, location, etc.)
            parent_context: Context from parent blocks
            level: Nesting level
        """
        # Pattern to match blocks: block_name [optional_params] { ... }
        block_pattern = re.compile(
            r'(\w+)(?:\s+([^{;]+?))?\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
            re.MULTILINE | re.DOTALL
        )
        
        # First, extract directives at this level (not within sub-blocks)
        directives = self._extract_directives(content)
        
        if directives or block_type != 'root':
            block_info = {
                'block_type': block_type,
                'block_context': parent_context,
                'directives': directives,
                'level': level
            }
            self.blocks.append(block_info)
        
        # Find and parse nested blocks
        for match in block_pattern.finditer(content):
            nested_block_type = match.group(1)
            nested_block_params = match.group(2) if match.group(2) else ''
            nested_block_content = match.group(3)
            
            # Clean up parameters
            nested_block_params = nested_block_params.strip()
            
            # Determine context based on block type
            if nested_block_type == 'server':
                # Extract server_name if present
                server_name_match = re.search(r'server_name\s+([^;]+);', nested_block_content)
                context = server_name_match.group(1).strip() if server_name_match else 'default'
            elif nested_block_type == 'location':
                # Location context is the pattern (e.g., "/api", "~ \.php$")
                context = nested_block_params
            elif nested_block_type == 'upstream':
                # Upstream context is the name
                context = nested_block_params
            else:
                context = nested_block_params if nested_block_params else nested_block_type
            
            # Build full context path
            if parent_context:
                full_context = f"{parent_context} > {context}" if context else parent_context
            else:
                full_context = context
            
            # Recursively parse the nested block
            self._parse_blocks(
                nested_block_content,
                block_type=nested_block_type,
                parent_context=full_context,
                level=level + 1
            )
    
    def _extract_directives(self, content: str) -> Dict[str, Any]:
        """
        Extract directives from content (not within nested blocks).
        
        Args:
            content: Content to extract directives from
            
        Returns:
            Dictionary of directives
        """
        directives = {}
        
        # Remove nested blocks to only process directives at this level
        block_pattern = re.compile(
            r'\w+(?:\s+[^{;]+?)?\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            re.MULTILINE | re.DOTALL
        )
        content_without_blocks = block_pattern.sub('', content)
        
        # Pattern to match directives: directive_name value1 [value2 ...];
        directive_pattern = re.compile(r'(\w+)\s+([^;]+);', re.MULTILINE)
        
        for match in directive_pattern.finditer(content_without_blocks):
            directive_name = match.group(1)
            directive_value = match.group(2).strip()
            
            # Handle multiple values for the same directive
            if directive_name in directives:
                # Convert to list if not already
                if not isinstance(directives[directive_name], list):
                    directives[directive_name] = [directives[directive_name]]
                directives[directive_name].append(directive_value)
            else:
                directives[directive_name] = directive_value
        
        return directives
    
    def find_security_directives(self, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract security-relevant directives from parsed blocks.
        
        Args:
            blocks: List of parsed nginx blocks
            
        Returns:
            Dictionary of security-relevant findings
        """
        security_info = {
            'ssl_protocols': [],
            'security_headers': [],
            'proxy_passes': [],
            'rate_limits': [],
            'exposed_paths': [],
            'ssl_ciphers': []
        }
        
        security_headers = [
            'add_header Strict-Transport-Security',
            'add_header X-Frame-Options',
            'add_header X-Content-Type-Options',
            'add_header Content-Security-Policy',
            'add_header X-XSS-Protection',
            'add_header Referrer-Policy'
        ]
        
        for block in blocks:
            directives = block.get('directives', {})
            block_type = block.get('block_type', '')
            block_context = block.get('block_context', '')
            
            # Check for SSL protocols
            if 'ssl_protocols' in directives:
                security_info['ssl_protocols'].append({
                    'context': block_context,
                    'protocols': directives['ssl_protocols']
                })
            
            # Check for SSL ciphers
            if 'ssl_ciphers' in directives:
                security_info['ssl_ciphers'].append({
                    'context': block_context,
                    'ciphers': directives['ssl_ciphers']
                })
            
            # Check for security headers
            if 'add_header' in directives:
                headers = directives['add_header']
                if not isinstance(headers, list):
                    headers = [headers]
                
                for header in headers:
                    security_info['security_headers'].append({
                        'context': block_context,
                        'header': header
                    })
            
            # Check for proxy_pass directives
            if 'proxy_pass' in directives:
                security_info['proxy_passes'].append({
                    'context': block_context,
                    'proxy_pass': directives['proxy_pass'],
                    'block_type': block_type
                })
            
            # Check for rate limiting
            if 'limit_req' in directives or 'limit_req_zone' in directives:
                security_info['rate_limits'].append({
                    'context': block_context,
                    'limit': directives.get('limit_req', directives.get('limit_req_zone'))
                })
            
            # Check for exposed sensitive paths
            if block_type == 'location':
                # Extract the location pattern from context
                location_pattern = block_context.split('>')[-1].strip() if '>' in block_context else block_context
                
                # Check for sensitive paths
                sensitive_patterns = ['.git', '.svn', '.hg', '.env', 'wp-admin', 'phpmyadmin', '.DS_Store', '.htaccess']
                for pattern in sensitive_patterns:
                    if pattern in location_pattern:
                        security_info['exposed_paths'].append({
                            'context': block_context,
                            'pattern': location_pattern,
                            'directives': directives
                        })
        
        return security_info