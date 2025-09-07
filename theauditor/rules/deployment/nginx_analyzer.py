"""Database-aware Nginx configuration security analyzer.

This module queries the nginx_configs table to detect common Nginx
security misconfigurations. It follows the pattern established by other
database-aware rules in TheAuditor.
"""

import json
import sqlite3
import re
from typing import List, Dict, Any


def find_nginx_issues(db_path: str) -> List[Dict[str, Any]]:
    """
    Analyze Nginx configurations stored in the database for security issues.
    
    This function queries the nginx_configs table populated by the indexer
    and detects the following critical Nginx misconfigurations:
    
    - proxy_pass without rate limiting
    - Missing critical security headers
    - Exposed hidden directories like .git
    - SSL misconfigurations (deprecated protocols)
    
    Args:
        db_path: Path to the repo_index.db database
        
    Returns:
        List of security findings in normalized format
    """
    findings = []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query all nginx configuration blocks from the database
        cursor.execute("""
            SELECT file_path, block_type, block_context, directives, level
            FROM nginx_configs
            ORDER BY file_path, level
        """)
        
        nginx_blocks = cursor.fetchall()
        
        # Build a structure to track rate limiting and proxy_pass configurations
        proxy_pass_blocks = []
        rate_limit_zones = []
        rate_limited_locations = []
        security_headers = {}
        ssl_configs = []
        location_blocks = []
        
        for row in nginx_blocks:
            file_path = row[0]
            block_type = row[1]
            block_context = row[2]
            directives_json = row[3]
            level = row[4]
            
            # Parse JSON directives
            try:
                directives = json.loads(directives_json) if directives_json else {}
            except json.JSONDecodeError:
                directives = {}
            
            # Track proxy_pass directives
            if 'proxy_pass' in directives:
                proxy_pass_blocks.append({
                    'file': file_path,
                    'block_type': block_type,
                    'context': block_context,
                    'proxy_pass': directives['proxy_pass'],
                    'directives': directives
                })
            
            # Track rate limiting zones
            if 'limit_req_zone' in directives:
                rate_limit_zones.append({
                    'file': file_path,
                    'context': block_context,
                    'zone': directives['limit_req_zone']
                })
            
            # Track rate limited locations
            if 'limit_req' in directives:
                rate_limited_locations.append({
                    'file': file_path,
                    'context': block_context,
                    'limit': directives['limit_req']
                })
            
            # Track security headers
            if 'add_header' in directives:
                headers = directives['add_header']
                if not isinstance(headers, list):
                    headers = [headers]
                
                for header in headers:
                    # Parse header name from the directive
                    header_match = re.match(r'(\S+)\s+', header)
                    if header_match:
                        header_name = header_match.group(1)
                        if file_path not in security_headers:
                            security_headers[file_path] = set()
                        security_headers[file_path].add(header_name)
            
            # Track SSL configurations
            if 'ssl_protocols' in directives or 'ssl_ciphers' in directives:
                ssl_configs.append({
                    'file': file_path,
                    'context': block_context,
                    'protocols': directives.get('ssl_protocols', ''),
                    'ciphers': directives.get('ssl_ciphers', '')
                })
            
            # Track location blocks
            if block_type == 'location':
                location_blocks.append({
                    'file': file_path,
                    'context': block_context,
                    'directives': directives
                })
        
        # Detection 1: proxy_pass without rate limiting
        for proxy_block in proxy_pass_blocks:
            # Check if this proxy_pass location has rate limiting
            has_rate_limit = False
            
            # Check if the same context has rate limiting
            for rate_limited in rate_limited_locations:
                if (proxy_block['file'] == rate_limited['file'] and 
                    proxy_block['context'] == rate_limited['context']):
                    has_rate_limit = True
                    break
            
            # Check if rate limiting is in the directives
            if 'limit_req' in proxy_block['directives']:
                has_rate_limit = True
            
            if not has_rate_limit:
                findings.append({
                    'pattern_name': 'NGINX_PROXY_NO_RATE_LIMIT',
                    'message': f'proxy_pass without rate limiting in {proxy_block["context"]}',
                    'file': proxy_block['file'],
                    'line': 0,
                    'column': 0,
                    'severity': 'high',
                    'snippet': f'proxy_pass {proxy_block["proxy_pass"]}',
                    'category': 'security',
                    'confidence': 0.85,
                    'details': {
                        'context': proxy_block['context'],
                        'vulnerability': 'Proxy endpoint vulnerable to DoS attacks',
                        'fix': 'Add limit_req directive to protect the endpoint'
                    }
                })
        
        # Detection 2: Missing security headers
        critical_headers = {
            'Strict-Transport-Security': 'HSTS header for HTTPS enforcement',
            'X-Frame-Options': 'Clickjacking protection',
            'X-Content-Type-Options': 'MIME sniffing protection',
            'Content-Security-Policy': 'XSS and injection protection',
            'X-XSS-Protection': 'XSS protection for older browsers',
            'Referrer-Policy': 'Control referrer information'
        }
        
        # Check each file for missing headers
        processed_files = set()
        for block in nginx_blocks:
            file_path = block[0]
            if file_path in processed_files:
                continue
            processed_files.add(file_path)
            
            file_headers = security_headers.get(file_path, set())
            
            for header_name, description in critical_headers.items():
                if header_name not in file_headers:
                    findings.append({
                        'pattern_name': 'NGINX_MISSING_SECURITY_HEADER',
                        'message': f'Missing security header: {header_name}',
                        'file': file_path,
                        'line': 0,
                        'column': 0,
                        'severity': 'medium',
                        'snippet': f'Missing: add_header {header_name}',
                        'category': 'security',
                        'confidence': 0.90,
                        'details': {
                            'header': header_name,
                            'description': description,
                            'fix': f'Add "add_header {header_name} <value>;" to server block'
                        }
                    })
        
        # Detection 3: Exposed hidden directories
        sensitive_patterns = [
            '.git', '.svn', '.hg', '.bzr',  # Version control
            '.env', '.htaccess', '.htpasswd',  # Configuration files
            'wp-admin', 'phpmyadmin', 'admin',  # Admin interfaces
            '.DS_Store', 'Thumbs.db',  # OS files
            'backup', '.backup', '.bak'  # Backup files
        ]
        
        for location in location_blocks:
            # Extract location pattern from context
            location_pattern = location['context'].split('>')[-1].strip() if '>' in location['context'] else location['context']
            
            # Check if location is trying to protect or expose sensitive paths
            for sensitive in sensitive_patterns:
                if sensitive in location_pattern.lower():
                    # Check if it's properly denied
                    directives = location['directives']
                    is_denied = False
                    
                    if 'deny' in directives:
                        deny_value = directives['deny']
                        if 'all' in str(deny_value).lower():
                            is_denied = True
                    
                    if 'return' in directives:
                        return_value = str(directives['return'])
                        if '403' in return_value or '404' in return_value:
                            is_denied = True
                    
                    if not is_denied:
                        findings.append({
                            'pattern_name': 'NGINX_EXPOSED_SENSITIVE_PATH',
                            'message': f'Potentially exposed sensitive path: {location_pattern}',
                            'file': location['file'],
                            'line': 0,
                            'column': 0,
                            'severity': 'high',
                            'snippet': f'location {location_pattern}',
                            'category': 'security',
                            'confidence': 0.80,
                            'details': {
                                'path': location_pattern,
                                'vulnerability': 'Sensitive directory may be accessible',
                                'fix': 'Add "deny all;" or "return 404;" to this location block'
                            }
                        })
        
        # Detection 4: SSL misconfigurations
        deprecated_protocols = ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.0', 'TLSv1.1']
        weak_ciphers = ['RC4', 'DES', 'MD5', 'NULL', 'EXPORT', 'aNULL', 'eNULL']
        
        for ssl_config in ssl_configs:
            protocols = ssl_config['protocols']
            ciphers = ssl_config['ciphers']
            
            # Check for deprecated protocols
            for deprecated in deprecated_protocols:
                if deprecated in protocols:
                    findings.append({
                        'pattern_name': 'NGINX_DEPRECATED_SSL_PROTOCOL',
                        'message': f'Using deprecated SSL/TLS protocol: {deprecated}',
                        'file': ssl_config['file'],
                        'line': 0,
                        'column': 0,
                        'severity': 'critical',
                        'snippet': f'ssl_protocols {protocols}',
                        'category': 'security',
                        'confidence': 0.95,
                        'details': {
                            'protocol': deprecated,
                            'context': ssl_config['context'],
                            'vulnerability': 'Vulnerable to known SSL/TLS attacks',
                            'fix': 'Use only TLSv1.2 and TLSv1.3: ssl_protocols TLSv1.2 TLSv1.3;'
                        }
                    })
            
            # Check for weak ciphers
            for weak_cipher in weak_ciphers:
                if weak_cipher in ciphers:
                    findings.append({
                        'pattern_name': 'NGINX_WEAK_SSL_CIPHER',
                        'message': f'Using weak SSL cipher: {weak_cipher}',
                        'file': ssl_config['file'],
                        'line': 0,
                        'column': 0,
                        'severity': 'high',
                        'snippet': f'ssl_ciphers {ciphers[:100]}...' if len(ciphers) > 100 else f'ssl_ciphers {ciphers}',
                        'category': 'security',
                        'confidence': 0.90,
                        'details': {
                            'cipher': weak_cipher,
                            'context': ssl_config['context'],
                            'vulnerability': 'Weak cipher vulnerable to cryptographic attacks',
                            'fix': 'Use strong cipher suites: ssl_ciphers HIGH:!aNULL:!MD5;'
                        }
                    })
        
        # Additional detection: Server tokens disclosure
        for row in nginx_blocks:
            directives = json.loads(row[3]) if row[3] else {}
            
            # Check if server_tokens is on (default) or missing
            if 'server_tokens' in directives:
                if directives['server_tokens'].lower() != 'off':
                    findings.append({
                        'pattern_name': 'NGINX_SERVER_TOKENS_ON',
                        'message': 'Server version disclosure enabled',
                        'file': row[0],
                        'line': 0,
                        'column': 0,
                        'severity': 'low',
                        'snippet': f'server_tokens {directives["server_tokens"]}',
                        'category': 'security',
                        'confidence': 0.95,
                        'details': {
                            'vulnerability': 'Nginx version exposed in headers',
                            'fix': 'Set "server_tokens off;" in http block'
                        }
                    })
        
        conn.close()
        
    except sqlite3.Error as e:
        # Return empty findings if database is not accessible
        return []
    except Exception as e:
        # Catch any other unexpected errors
        return []
    
    return findings