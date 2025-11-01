"""
Database-driven source and sink discovery.

Phase 3 implementation that discovers sources and sinks from the database
instead of using hardcoded patterns. This eliminates the need for manual
pattern maintenance and automatically discovers new sources/sinks as the
database evolves.
"""

from typing import Dict, List, Any, Optional
import sys


def _matches_file_io_pattern(func_name: str, patterns: List[str]) -> bool:
    """
    Strict pattern matching for file I/O functions to avoid false positives.

    Prevents substring matches like 'open' in 'openSgIpv4.addIngressRule'.

    Args:
        func_name: Function name to check (e.g., 'fs.readFile', 'open', 'openSgIpv4.addIngressRule')
        patterns: List of file I/O function names (e.g., ['open', 'readFile'])

    Returns:
        True if func_name is a file I/O function, False for false positives

    Examples:
        >>> _matches_file_io_pattern('open', ['open'])
        True
        >>> _matches_file_io_pattern('fs.open', ['open'])
        True
        >>> _matches_file_io_pattern('openSgIpv4.addIngressRule', ['open'])
        False
    """
    if not func_name:
        return False

    for pattern in patterns:
        # Exact match: 'open' == 'open'
        if func_name == pattern:
            return True

        # Module-qualified suffix: 'fs.open', 'path.open'
        # Ensures '.open' exists and function ends with pattern
        if f'.{pattern}' in func_name and func_name.endswith(pattern):
            return True

    return False


class TaintDiscovery:
    """Database-driven discovery of taint sources and sinks."""

    def __init__(self, cache):
        """Initialize with a cache (either old MemoryCache or SchemaMemoryCache)."""
        self.cache = cache

    def discover_sources(self, sources_dict: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """
        Discover taint sources from database.

        Instead of searching for hardcoded patterns, we discover actual sources
        that exist in the codebase by querying the database tables directly.

        Returns:
            List of source dictionaries with metadata
        """
        sources = []

        # HTTP Request Sources: Query api_endpoints table for actual endpoints
        if hasattr(self.cache, 'api_endpoints'):
            for endpoint in self.cache.api_endpoints:
                # Public endpoints without auth are higher risk
                risk = 'high' if not endpoint.get('has_auth', True) else 'medium'

                sources.append({
                    'type': 'http_request',
                    'name': endpoint.get('handler_function', 'unknown'),
                    'file': endpoint.get('file', ''),
                    'line': endpoint.get('line', 0),
                    'pattern': f"{endpoint.get('method', 'GET')} {endpoint.get('path', '/')}",
                    'category': 'http_request',
                    'risk': risk,
                    'has_auth': endpoint.get('has_auth', True),
                    'metadata': endpoint
                })

        # User Input Sources: Property access patterns that indicate user input
        if hasattr(self.cache, 'symbols'):
            input_patterns = ['req.', 'request.', 'body.', 'query.', 'params.', 'args.', 'form.', 'cookies.']
            for symbol in self.cache.symbols:
                if symbol.get('type') == 'property':
                    name = symbol.get('name', '')
                    if any(pattern in name.lower() for pattern in input_patterns):
                        sources.append({
                            'type': 'user_input',
                            'name': name,
                            'file': symbol.get('path', ''),
                            'line': symbol.get('line', 0),
                            'pattern': name,
                            'category': 'user_input',
                            'risk': 'high',
                            'metadata': symbol
                        })

        # REMOVED: File Read Sources
        # Reason: File operations (open, readFile) are SINKS (path traversal), not SOURCES
        # Reading file contents doesn't create user-controlled data - the path is the vulnerability
        # Sources should be things like HTTP request params, user input, environment vars
        # If file contents need to be tracked as tainted, that's a different analysis (second-order)

        # Environment Variable Sources
        if hasattr(self.cache, 'env_accesses'):
            for env in self.cache.env_accesses:
                sources.append({
                    'type': 'environment',
                    'name': env.get('key', 'unknown'),
                    'file': env.get('file', ''),
                    'line': env.get('line', 0),
                    'pattern': f"process.env.{env.get('key', '')}",
                    'category': 'environment',
                    'risk': 'low',
                    'metadata': env
                })

        # Database Query Results as Sources (for second-order injection)
        if hasattr(self.cache, 'sql_queries'):
            for query in self.cache.sql_queries:
                if 'SELECT' in query.get('query_text', '').upper():
                    sources.append({
                        'type': 'database_read',
                        'name': 'sql_query_result',
                        'file': query.get('file_path', ''),
                        'line': query.get('line_number', 0),
                        'pattern': query.get('query_text', '')[:50],
                        'category': 'database',
                        'risk': 'low',
                        'metadata': query
                    })

        return sources

    def discover_sinks(self, sinks_dict: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """
        Discover security sinks from database.

        Instead of searching for hardcoded patterns, we discover actual sinks
        that exist in the codebase by querying the database tables directly.

        Returns:
            List of sink dictionaries with metadata
        """
        sinks = []

        # SQL Injection Sinks: Direct from sql_queries table
        if hasattr(self.cache, 'sql_queries'):
            for query in self.cache.sql_queries:
                # Assess risk based on query construction
                query_text = query.get('query_text', '')
                risk = self._assess_sql_risk(query_text)

                sinks.append({
                    'type': 'sql',
                    'name': 'sql_query',
                    'file': query.get('file_path', ''),
                    'line': query.get('line_number', 0),
                    'pattern': query_text[:100],
                    'category': 'sql',
                    'risk': risk,
                    'is_parameterized': query.get('is_parameterized', False),
                    'metadata': query
                })

        # NoSQL Injection Sinks
        if hasattr(self.cache, 'nosql_queries'):
            for query in self.cache.nosql_queries:
                sinks.append({
                    'type': 'nosql',
                    'name': query.get('collection', 'unknown'),
                    'file': query.get('file', ''),
                    'line': query.get('line', 0),
                    'pattern': query.get('operation', ''),
                    'category': 'nosql',
                    'risk': 'medium',
                    'metadata': query
                })

        # Command Injection Sinks: exec, eval, spawn, etc.
        if hasattr(self.cache, 'function_call_args'):
            cmd_funcs = ['exec', 'execSync', 'spawn', 'spawnSync', 'eval', 'system', 'execFile', 'shell']
            for call in self.cache.function_call_args:
                func_name = call.get('callee_function', '')
                if any(cmd in func_name for cmd in cmd_funcs):
                    sinks.append({
                        'type': 'command',
                        'name': func_name,
                        'file': call.get('file', ''),
                        'line': call.get('line', 0),
                        'pattern': func_name,
                        'category': 'command',
                        'risk': 'critical',
                        'metadata': call
                    })

        # XSS Sinks: React dangerouslySetInnerHTML
        if hasattr(self.cache, 'react_hooks'):
            for hook in self.cache.react_hooks:
                # Check if hook uses dangerous HTML setting
                if 'dangerouslySetInnerHTML' in str(hook):
                    sinks.append({
                        'type': 'xss',
                        'name': 'dangerouslySetInnerHTML',
                        'file': hook.get('file', ''),
                        'line': hook.get('line', 0),
                        'pattern': 'dangerouslySetInnerHTML',
                        'category': 'xss',
                        'risk': 'high',
                        'metadata': hook
                    })

        # XSS Sinks: Direct innerHTML assignments
        if hasattr(self.cache, 'assignments'):
            for assignment in self.cache.assignments:
                target = assignment.get('target_var', '')
                if 'innerHTML' in target or 'outerHTML' in target:
                    sinks.append({
                        'type': 'xss',
                        'name': target,
                        'file': assignment.get('file', ''),
                        'line': assignment.get('line', 0),
                        'pattern': target,
                        'category': 'xss',
                        'risk': 'high',
                        'metadata': assignment
                    })

        # Path Traversal Sinks: File operations
        # CRITICAL: Use strict matching to avoid false positives like 'open' in 'openSgIpv4'
        if hasattr(self.cache, 'function_call_args'):
            file_funcs = ['readFile', 'writeFile', 'open', 'unlink', 'mkdir', 'rmdir', 'access']
            for call in self.cache.function_call_args:
                func_name = call.get('callee_function', '')
                if _matches_file_io_pattern(func_name, file_funcs):
                    # Check if first argument could be user-controlled
                    arg = call.get('argument_expr', '')
                    if arg and not arg.startswith('"') and not arg.startswith("'"):
                        sinks.append({
                            'type': 'path',
                            'name': func_name,
                            'file': call.get('file', ''),
                            'line': call.get('line', 0),
                            'pattern': func_name,
                            'category': 'path',
                            'risk': 'medium',
                            'metadata': call
                        })

        # LDAP Injection Sinks
        if hasattr(self.cache, 'function_call_args'):
            ldap_funcs = ['search', 'bind', 'add', 'modify', 'delete']
            for call in self.cache.function_call_args:
                func_name = call.get('callee_function', '')
                if any(f in func_name.lower() and 'ldap' in func_name.lower() for f in ldap_funcs):
                    sinks.append({
                        'type': 'ldap',
                        'name': func_name,
                        'file': call.get('file', ''),
                        'line': call.get('line', 0),
                        'pattern': func_name,
                        'category': 'ldap',
                        'risk': 'medium',
                        'metadata': call
                    })

        return sinks

    def _assess_sql_risk(self, query_text: str) -> str:
        """
        Assess the risk level of an SQL query based on its construction.

        Args:
            query_text: The SQL query text

        Returns:
            Risk level: 'critical', 'high', 'medium', or 'low'
        """
        query_lower = query_text.lower()

        # Critical: String concatenation with user input
        if any(op in query_text for op in ['+', '${', 'f"', "f'", '`${', '".', "'."]):
            return 'critical'

        # High: Direct string interpolation
        if '%s' in query_text or '%d' in query_text:
            return 'high'

        # Low: Parameterized queries
        if any(param in query_text for param in ['?', '$1', ':param', '@param']):
            return 'low'

        # Medium: Can't determine
        return 'medium'

    def filter_framework_safe_sinks(self, sinks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out sinks that are automatically safe due to framework protections.

        For example:
        - res.json() in Express automatically escapes data
        - React components escape by default (unless dangerouslySetInnerHTML)
        - Parameterized queries are safe from SQL injection

        Args:
            sinks: List of discovered sinks

        Returns:
            Filtered list of sinks that are actually vulnerable
        """
        filtered = []

        for sink in sinks:
            # Skip parameterized SQL queries
            if sink.get('category') == 'sql' and sink.get('is_parameterized'):
                continue

            # Skip React components that don't use dangerouslySetInnerHTML
            if sink.get('category') == 'xss' and sink.get('type') == 'react':
                if 'dangerouslySetInnerHTML' not in sink.get('pattern', ''):
                    continue

            # Keep all other sinks
            filtered.append(sink)

        return filtered