"""
Temporary stub for sources.py during refactor.
The real implementation has been moved to discovery.py for database-driven discovery.
This file provides backward compatibility during the transition.
"""

import platform

# Minimal definitions to prevent import errors
# These will be removed once the refactor is complete

IS_WINDOWS = platform.system() == 'Windows'

TAINT_SOURCES = {
    'http_request': [],
    'file_read': [],
    'environment': [],
    'database': []
}

SECURITY_SINKS = {
    'sql': [],
    'command': [],
    'xss': [],
    'path': [],
    'ldap': [],
    'nosql': []
}

SANITIZERS = {
    'html_escape': [],
    'sql_escape': [],
    'shell_escape': []
}